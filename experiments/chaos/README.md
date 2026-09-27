# Chaos experiments

These are hypothesis-driven fault-injection experiments using
[Chaos Mesh](https://chaos-mesh.org) (`helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh`).
Run them in staging, under steady load (`make load-test RATE=100 DURATION=10m`), and only
while more than 50% of the error budget remains (see `docs/research/slo.md`). **They have
not been executed in CI.** Each file states a falsifiable hypothesis and the PromQL that
decides it.

| Experiment | Fault | Hypothesis | Verdict query (over the experiment window) |
|---|---|---|---|
| `api-pod-kill.yaml` | kill one listings-api pod every 2 min for 10 min | availability ≥ 99.5%, because readiness, preStop drain, PDB and ≥ 2 replicas mask pod loss | `1 - kubeestatehub:api_error_ratio:rate5m` stays ≥ 0.995 |
| `redis-pod-failure.yaml` | Redis unavailable for 5 min | no 5xx and p99 < 500 ms: the cache degrades to a no-op and the rate limiter fails open | error ratio unchanged; `listings_cache_events_total{outcome="error"}` rises |
| `postgres-latency.yaml` | +300 ms (±50 ms jitter) on API→PostgreSQL traffic for 5 min | the latency SLO is **breached**: a list query makes two round trips, so requests exceed 500 ms. This confirms the latency burn-rate page fires within its short window | `kubeestatehub:api_slow_ratio:rate5m` > 0.144 and `KubeEstateHubLatencyBudgetBurnFast` fires |

Record each run with its date, commit, load profile, results and verdict, appended
below. A falsified hypothesis is a finding. Open an issue with the evidence.
