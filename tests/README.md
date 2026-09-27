# Test suite

| Layer | Location | Runs in CI | What it proves |
|---|---|---|---|
| Unit | `tests/unit/` (118 tests) | `ci / unit` on Python 3.12 and 3.13 | API contract, validation, caching, auth, rate limits, metrics labelling; exporter behaviour; operator reconciliation; statistical estimators, including cross-checks against SciPy, size and power tests and coverage tests |
| Integration | `tests/integration/` | `ci / integration` against a PostgreSQL 16 service | real SQL: migrations, repository round-trips, the full API, pipeline provenance, exporter queries, readiness gating |
| Migration runner | `db/migrate.sh` | `ci / integration` | idempotency and tamper detection |
| Estimators | `python -m analytics_worker benchmark` | `ci / benchmark` | bias and coverage within statistical tolerance (`hack/check_benchmark.py`) |
| Policy | `policy/*_test.rego` (20 tests) | `kubernetes / validate` | conftest rules behave as specified |
| Alerting | `observability/prometheus/rules.test.yaml` | `kubernetes / validate` | SLO burn-rate and model-quality alerts fire exactly when intended |
| Manifests | `hack/validate.sh` | `kubernetes / validate` | all 8 renders are schema-valid, linted and policy-compliant; Helm and kustomize are in parity |
| System (compose) | `scripts/e2e-compose.sh` | `kubernetes / compose-e2e` | 13 HTTP-level checks on a fresh stack |
| System (Kubernetes) | `hack/kind-e2e.sh` | `kubernetes / kind-e2e` | real cluster: Ingress, CronJob, operator lifecycle, admission denial |
| Load | `tests/load/listings-api.js` (k6) | manual (`make load-test`) | SLO thresholds under open-model load |
| Chaos | `experiments/chaos/` | manual, staging only | resilience hypotheses tied to SLOs |

```bash
make test                                       # unit tests + coverage
DATABASE_URL=postgresql://… make test-integration  # the schema is dropped and recreated!
make validate e2e kind-e2e
```

**Statistical tests are deterministic.** Every random draw is seeded, so a failure is
reproducible, not flaky. Tests marked `slow` (Monte Carlo size and coverage checks) run
by default. Deselect them with `-m "not slow"`.
