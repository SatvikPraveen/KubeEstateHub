#!/usr/bin/env bash
# End-to-end test on a real Kubernetes cluster (kind).
#   hack/kind-e2e.sh all    create cluster, build+load images, deploy, test, delete cluster
#   hack/kind-e2e.sh up     create cluster and deploy (leave running)
#   hack/kind-e2e.sh test   run the assertions against an existing deployment
#   hack/kind-e2e.sh down   delete the cluster
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="${BIN:-$ROOT/bin}:$PATH"
CLUSTER="${CLUSTER:-kubeestatehub-e2e}"
NODE_IMAGE="${NODE_IMAGE:-kindest/node:v1.31.2}"
INGRESS_NGINX_VERSION="${INGRESS_NGINX_VERSION:-controller-v1.11.3}"
HTTP_PORT="${HTTP_PORT:-18088}"
NS=kubeestatehub
HOST=kubeestatehub.localtest.me
SERVICES=(listings-api frontend-dashboard metrics-service analytics-worker realestate-sync-operator)

log() { printf '\033[1m[kind-e2e]\033[0m %s\n' "$*"; }
fail() { echo "FAIL: $*" >&2; kubectl -n "$NS" get pods,jobs,events --sort-by=.metadata.creationTimestamp 2>&1 | tail -40 >&2; exit 1; }
check() { local d=$1; shift; if "$@"; then echo "ok   $d"; else fail "$d"; fi; }
http() { curl -fsS --retry 5 --retry-all-errors --retry-delay 2 -H "Host: $HOST" "http://127.0.0.1:${HTTP_PORT}$1"; }
json() { python3 -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1], {}, {'d': d}))" "$1"; }

create_cluster() {
  kind get clusters | grep -qx "$CLUSTER" && return
  log "creating cluster $CLUSTER ($NODE_IMAGE)"
  kind create cluster --name "$CLUSTER" --image "$NODE_IMAGE" --wait 120s --config - <<YAML
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    labels: {ingress-ready: "true"}
    extraPortMappings:
      - {containerPort: 80, hostPort: ${HTTP_PORT}, listenAddress: 127.0.0.1, protocol: TCP}
YAML
  log "installing ingress-nginx $INGRESS_NGINX_VERSION"
  kubectl apply -f "https://raw.githubusercontent.com/kubernetes/ingress-nginx/${INGRESS_NGINX_VERSION}/deploy/static/provider/kind/deploy.yaml" >/dev/null
  kubectl -n ingress-nginx rollout status deploy/ingress-nginx-controller --timeout=180s
  kubectl -n ingress-nginx wait --for=condition=complete job --all --timeout=120s >/dev/null 2>&1 || true
}

build_and_load() {
  for svc in "${SERVICES[@]}"; do
    log "building $svc"
    docker build -q --build-arg CODE_VERSION="$(git rev-parse --short HEAD)" -t "kubeestatehub/$svc:e2e" "src/$svc" >/dev/null
    kind load docker-image --name "$CLUSTER" "kubeestatehub/$svc:e2e" >/dev/null
  done
}

deploy() {
  log "deploying overlay e2e"
  kubectl apply --server-side -k kustomize/overlays/e2e >/dev/null
  kubectl -n "$NS" rollout status statefulset/postgres --timeout=240s
  kubectl -n "$NS" wait --for=condition=complete job/db-migrate --timeout=240s
  for d in redis listings-api frontend metrics-service realestate-sync-operator; do
    kubectl -n "$NS" rollout status "deploy/$d" --timeout=240s
  done
}

run_job() {  # name, args...
  local name=$1; shift
  kubectl -n "$NS" delete job "$name" --ignore-not-found >/dev/null
  kubectl -n "$NS" apply -f - >/dev/null <<YAML
apiVersion: batch/v1
kind: Job
metadata: {name: $name}
spec:
  backoffLimit: 0
  template:
    metadata: {labels: {app.kubernetes.io/name: analytics-pipeline}}
    spec:
      restartPolicy: Never
      serviceAccountName: analytics
      automountServiceAccountToken: false
      securityContext: {runAsNonRoot: true, runAsUser: 10001, seccompProfile: {type: RuntimeDefault}}
      containers:
        - name: worker
          image: kubeestatehub/analytics-worker:e2e
          args: [$(printf '"%s",' "$@" | sed 's/,$//')]
          env: [{name: DATABASE_URL, valueFrom: {secretKeyRef: {name: $(kubectl -n "$NS" get secret -o name | grep db-secret | head -1 | cut -d/ -f2), key: database-url}}}]
          resources: {requests: {cpu: 100m, memory: 256Mi}, limits: {memory: 1Gi}}
          securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {drop: [ALL]}}
          volumeMounts: [{name: tmp, mountPath: /tmp}]
      volumes: [{name: tmp, emptyDir: {}}]
YAML
  kubectl -n "$NS" wait --for=condition=complete "job/$name" --timeout=300s || fail "job $name"
}

run_tests() {
  log "seeding synthetic market and running the analytics CronJob"
  run_job e2e-seed seed --n 3000 --seed 42
  kubectl -n "$NS" delete job e2e-pipeline --ignore-not-found >/dev/null
  kubectl -n "$NS" create job e2e-pipeline --from=cronjob/analytics-pipeline >/dev/null
  kubectl -n "$NS" wait --for=condition=complete job/e2e-pipeline --timeout=300s || fail "pipeline CronJob"

  check "dashboard via ingress"       test "$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $HOST" "http://127.0.0.1:${HTTP_PORT}/")" = 200
  check "api readiness via ingress"   test "$(http /readyz | json 'd["status"]')" = ready
  total=$(http "/api/v1/listings?per_page=1" | json 'd["pagination"]["total"]')
  check "listings served ($total)"    test "$total" -gt 100
  coverage=$(http /api/v1/model-runs/latest | json 'd["model_run"]["metrics"]["cross_validation"]["hedonic_conformal"]["coverage"]')
  check "conformal coverage ($coverage)" python3 -c "import sys; sys.exit(0 if 0.85 <= $coverage <= 0.95 else 1)"
  check "price index published"       test "$(http /api/v1/market/price-index | json 'len(d["series"])')" -gt 6

  log "operator: reconcile a RealEstateSync into a CronJob"
  kubectl -n "$NS" apply -f - >/dev/null <<'YAML'
apiVersion: realestate.kubeestatehub.io/v1
kind: RealEstateSync
metadata: {name: e2e-feed}
spec:
  source: {type: csv, endpoint: "https://feeds.example.com/listings.csv"}
  schedule: "@daily"
  suspend: true
  syncConfig: {timeout: 5m, retryLimit: 1}
YAML
  for _ in $(seq 1 30); do kubectl -n "$NS" get cronjob sync-e2e-feed >/dev/null 2>&1 && break; sleep 2; done
  check "operator created owned CronJob" test "$(kubectl -n "$NS" get cronjob sync-e2e-feed -o jsonpath='{.metadata.ownerReferences[0].kind}')" = RealEstateSync
  check "CronJob suspended per spec"      test "$(kubectl -n "$NS" get cronjob sync-e2e-feed -o jsonpath='{.spec.suspend}')" = true
  for _ in $(seq 1 30); do [[ "$(kubectl -n "$NS" get res e2e-feed -o jsonpath='{.status.phase}')" == Paused ]] && break; sleep 2; done
  check "status subresource reports Paused" test "$(kubectl -n "$NS" get res e2e-feed -o jsonpath='{.status.phase}')" = Paused
  kubectl -n "$NS" delete res e2e-feed >/dev/null
  for _ in $(seq 1 30); do kubectl -n "$NS" get cronjob sync-e2e-feed >/dev/null 2>&1 || break; sleep 2; done
  check "CronJob garbage-collected with its owner" bash -c "! kubectl -n $NS get cronjob sync-e2e-feed >/dev/null 2>&1"

  log "admission policy: a PSA-compliant pod with a :latest image must be rejected"
  out=$(kubectl -n "$NS" apply --dry-run=server -f - 2>&1 <<'YAML' || true
apiVersion: v1
kind: Pod
metadata: {name: policy-probe}
spec:
  securityContext: {runAsNonRoot: true, runAsUser: 10001, seccompProfile: {type: RuntimeDefault}}
  containers:
    - name: c
      image: busybox:latest
      resources: {requests: {cpu: 10m}, limits: {memory: 16Mi}}
      securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {drop: [ALL]}}
YAML
)
  check "ValidatingAdmissionPolicy denies :latest" grep -q "kubeestatehub-workload-standards" <<<"$out"
  echo "kind e2e: all checks passed"
}

case "${1:-all}" in
  up) create_cluster; build_and_load; deploy ;;
  test) run_tests ;;
  down) kind delete cluster --name "$CLUSTER" ;;
  all)
    trap '[[ "${KEEP:-0}" == 1 ]] || kind delete cluster --name "$CLUSTER" >/dev/null 2>&1' EXIT
    create_cluster; build_and_load; deploy; run_tests ;;
  *) echo "usage: $0 all|up|test|down" >&2; exit 2 ;;
esac
