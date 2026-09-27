# Architecture decision records

| ADR | Decision |
|---|---|
| [0001](0001-statistical-trend-classification.md) | Classify market trends with Mann–Kendall and Theil–Sen instead of a ±5% threshold |
| [0002](0002-conformal-prediction-intervals.md) | Report valuation uncertainty with split-conformal intervals |
| [0003](0003-batch-cronjobs-over-celery.md) | Run analytics as batch CronJobs with provenance, not a Celery worker |
| [0004](0004-kustomize-base-with-helm-parity.md) | One kustomize base plus a Helm chart, with parity checked in CI |
| [0005](0005-cel-admission-policy.md) | Replace PodSecurityPolicy and custom webhooks with PSA plus a CEL ValidatingAdmissionPolicy |
| [0006](0006-kopf-operator.md) | Implement the RealEstateSync operator in Python with kopf |
| [0007](0007-probe-semantics-and-schema-gating.md) | Liveness is process-only; readiness gates on database and schema version |
