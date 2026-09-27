#!/usr/bin/env bash
# Static validation of everything that ships to a cluster. Used by `make validate` and CI.
#
#  1. generated files are up to date (hack/generate.py)
#  2. every kustomize overlay and every Helm values file renders
#  3. kubeconform: strict schema validation against Kubernetes $K8S_VERSION (+ CRD catalog)
#  4. kube-linter: best-practice lint
#  5. conftest: policy unit tests, per-document and cross-resource policies
#  6. promtool: alert/recording rule syntax and unit tests
#  7. parity: kustomize (production) and Helm render the same set of resources
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BIN="${BIN:-$ROOT/bin}"
export PATH="$BIN:$PATH"
K8S_VERSION="${K8S_VERSION:-1.31.0}"
PROMETHEUS_IMAGE="${PROMETHEUS_IMAGE:-prom/prometheus:v3.5.0}"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

step "generated files"
snapshot() { find manifests helm-charts observability -type f -print0 | sort -z | xargs -0 shasum | shasum; }
before="$(snapshot)"
python3 hack/generate.py
[[ "$before" == "$(snapshot)" ]] || { echo "generated files were stale: review and commit the changes above" >&2; exit 1; }
echo "up to date"

step "render"
for overlay in kustomize/overlays/*/; do
  name="$(basename "$overlay")"
  kubectl kustomize "$overlay" > "$OUT/kustomize-$name.yaml"
  echo "kustomize/$name: $(grep -c '^kind:' "$OUT/kustomize-$name.yaml") resources"
done
for values in helm-charts/kubeestatehub/values*.yaml; do
  name="$(basename "$values" .yaml)"
  extra=()
  # the bare defaults expect pre-created Secrets; render them so the output is self-contained
  [[ "$name" == values ]] && extra=(--set secrets.create=true --set secrets.dbPassword=ci-only --set secrets.writeToken=ci-only)
  helm lint --strict helm-charts/kubeestatehub -f "$values" ${extra[@]+"${extra[@]}"} >/dev/null
  helm template kubeestatehub helm-charts/kubeestatehub -n kubeestatehub --include-crds -f "$values" ${extra[@]+"${extra[@]}"} \
    > "$OUT/helm-$name.yaml"
  echo "helm/$name: $(grep -c '^kind:' "$OUT/helm-$name.yaml") resources"
done

step "kubeconform (Kubernetes $K8S_VERSION)"
kubeconform -strict -summary -kubernetes-version "$K8S_VERSION" \
  -skip CustomResourceDefinition \
  -schema-location default \
  -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' \
  "$OUT"/*.yaml

step "kube-linter"
# one render at a time: cross-file matching would pair e.g. a production PDB with a dev Deployment
for f in "$OUT"/*.yaml; do
  printf '%s: ' "$(basename "$f")"
  kube-linter lint --config .kube-linter.yaml "$f" | tail -1
done

step "conftest"
conftest verify --policy policy --no-color
for f in "$OUT"/*.yaml; do
  conftest test --no-color --policy policy --namespace kubernetes.workloads --namespace kubernetes.rbac "$f" | tail -1
  conftest test --no-color --policy policy --combine --namespace kubernetes.combined "$f" | tail -1
done

step "promtool"
docker run --rm -v "$ROOT/observability/prometheus:/rules:ro" -w /rules --entrypoint promtool "$PROMETHEUS_IMAGE" \
  check rules rules.yaml
docker run --rm -v "$ROOT/observability/prometheus:/rules:ro" -w /rules --entrypoint promtool "$PROMETHEUS_IMAGE" \
  test rules rules.test.yaml

step "kustomize/helm parity (production)"
# Namespace: Helm installs into an existing namespace. Pod: the `helm test` hook.
python3 hack/resource_ids.py "$OUT/kustomize-production.yaml" | grep -v '^Namespace/' > "$OUT/ids-kustomize"
python3 hack/resource_ids.py "$OUT/helm-values-production.yaml" | grep -v '^Pod/' > "$OUT/ids-helm"
diff "$OUT/ids-kustomize" "$OUT/ids-helm"
echo "identical resource sets ($(wc -l < "$OUT/ids-helm" | tr -d ' ') resources)"

echo; echo "validation passed"
