# RealEstateSync operator

A [kopf](https://kopf.readthedocs.io) operator for the
`realestatesyncs.realestate.kubeestatehub.io/v1` custom resource.

**Reconciliation.** On create, spec update or operator restart, the operator renders an
owned CronJob (`sync-<name>`). The CronJob runs `python -m analytics_worker sync` from the
analytics-worker image. The CronJob carries an ownerReference, so deleting the custom
resource garbage-collects it and no finalizer is needed. A 60 s timer mirrors the CronJob
status into `.status` (`phase`, `lastScheduleTime`, `lastSyncTime`, a `Ready` condition)
and recreates the CronJob if someone deleted it (drift repair).

| Spec field | CronJob mapping |
|---|---|
| `schedule`, `timeZone`, `suspend` | `spec.schedule`, `spec.timeZone`, `spec.suspend` |
| `syncConfig.retryLimit` | `jobTemplate.spec.backoffLimit` |
| `syncConfig.timeout` (Go duration) | `jobTemplate.spec.activeDeadlineSeconds` |
| `source.credentials.secretRef` | `SOURCE_API_TOKEN` from the referenced Secret (never inline) |
| `syncConfig.filters`, `batchSize`, `maxFailedRecords` | CLI arguments of the sync job |

The CronJob uses `concurrencyPolicy: Forbid`, and its pods run as non-root with a
read-only root filesystem, all capabilities dropped and no service-account token.

```bash
kubectl apply -f manifests/examples/realestatesync.yaml
kubectl get res            # short name
```

| Phase | Meaning |
|---|---|
| `Pending` | Scheduled, but no job has run yet |
| `Running` | A job is active |
| `Completed` | The last scheduled job succeeded |
| `Failed` | The last scheduled job did not succeed |
| `Paused` | `spec.suspend: true` |
