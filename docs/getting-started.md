# Getting started

## Option 1: docker compose (about 3 minutes, no Kubernetes)

```bash
make up          # builds images; postgres -> migrate -> seed (synthetic, seed 42) -> pipeline
open http://localhost:3000            # dashboard
curl localhost:8080/openapi.json      # API contract
curl localhost:9100/metrics | grep kubeestatehub_avm
make e2e         # 13 end-to-end checks on a fresh stack
make down
```

Writes need the token, which defaults to `local-dev-token`:

```bash
curl -X POST localhost:8080/api/v1/listings -H 'Authorization: Bearer local-dev-token' \
  -H 'Content-Type: application/json' -d '{"mls_number":"A-1","title":"Test","property_type":"residential",
  "price":450000,"address":"1 Main","city":"Austin","state":"TX","zip_code":"78701","square_feet":1800}'
```

## Option 2: local Kubernetes with kind

```bash
make tools        # pinned helm, kubeconform, conftest, kube-linter, kind, kubectl into ./bin
make kind-e2e     # cluster + ingress-nginx + locally built images + deploy + assertions
# keep it running instead:
hack/kind-e2e.sh up && hack/kind-e2e.sh test
curl -H 'Host: kubeestatehub.localtest.me' http://127.0.0.1:18088/api/v1/market/summary
```

## Option 3: an existing cluster (Kubernetes 1.30 or later)

1. Install the prerequisites: `helmfile -f platform/helmfile.yaml sync`. See
   [platform/README.md](../platform/README.md).
2. Deploy with either tool:
   ```bash
   kubectl apply -k kustomize/overlays/staging        # needs the ExternalSecret store
   # or
   helm install keh helm-charts/kubeestatehub -n kubeestatehub --create-namespace \
     -f helm-charts/kubeestatehub/values-production.yaml
   ```
3. Load data. Point a `RealEstateSync` at your feed
   (`manifests/examples/realestatesync.yaml`), or seed a synthetic market:
   `kubectl -n kubeestatehub create job seed --image=ghcr.io/satvikpraveen/kubeestatehub/analytics-worker:main -- python -m analytics_worker seed`.
   A Job created this way must still satisfy the admission policy. See `run_job` in
   `hack/kind-e2e.sh` for a compliant spec.
4. Run the pipeline now:
   `kubectl -n kubeestatehub create job analytics-now --from=cronjob/analytics-pipeline`.

## Development

```bash
make install      # .venv with all service and dev dependencies
make lint test    # ruff, yamllint; unit tests with coverage
make validate     # everything cluster-facing (see tests/README.md)
make benchmark    # regenerate docs/research/results-table.md
make generate     # after editing db/, observability/ or components copied into the chart
```
