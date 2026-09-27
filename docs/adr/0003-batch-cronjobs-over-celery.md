# 0003. Batch CronJobs with provenance instead of a Celery worker

* Status: accepted (2026-09)

## Context
v1 ran a long-lived Celery worker with an in-process `schedule` thread. Nothing ever
enqueued Celery tasks, the broker added an operational dependency, and results were
written without any record of which code or data produced them.

## Decision
Analytics is a batch program (`python -m analytics_worker pipeline`) run by a Kubernetes
CronJob with `concurrencyPolicy: Forbid`. Each run writes a `model_runs` row (code
version, seed, parameters, metrics, error), and every derived row references it. Pipeline
metrics can optionally be pushed to a Pushgateway. Staleness is detected from
`model_runs` through the metrics service.

## Consequences
* There is no broker and no idle pods. Retries, history and deadlines are native Job
  features.
* Every number the product shows can be traced to a reproducible run.
* On-demand analytics would need a queue later. The CLI entry points make adding one
  straightforward.
