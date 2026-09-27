# Runbooks

Every alert in `observability/prometheus/rules.yaml` links to a section here. Commands
assume `kubectl config set-context --current --namespace kubeestatehub`.

## availability-budget-burn

**Meaning.** The listings API returns 5xx fast enough to exhaust the 30-day budget in
days (page) or weeks (ticket).

1. Find which routes fail:
   `sum by (route, status) (rate(http_requests_total{job="listings-api",status=~"5.."}[5m]))`.
2. Check the logs. Every error log carries `request_id`, and clients receive it as
   `X-Request-ID`:
   `kubectl logs deploy/listings-api --since=15m | jq 'select(.level=="error")'`.
3. Check the database. If `/readyz` is failing, pods leave the Service and the Ingress
   returns 503s. See [postgres-down](#postgres-down).
4. If a deploy caused it, run `kubectl rollout undo deploy/listings-api`.
   `maxUnavailable: 0` keeps the old ReplicaSet serving during the rollback.

## latency-budget-burn

1. `kubeestatehub:api_latency_seconds:p95_5m` and the per-route latency panel show which
   route is slow.
2. **CPU saturation.** Compare the HPA's current and max replicas
   (`kubectl get hpa listings-api`). The load test puts the knee near 300–600 rps per two
   replicas.
3. **Slow queries.** PostgreSQL logs statements over 500 ms
   (`log_min_duration_statement`), and the API's statement timeout is 5 s.
4. **Connection pool exhaustion.** `DB_POOL_MAX` is 10 per worker. Check
   `pg_stat_activity_count`.

## analytics-pipeline-stale

1. `kubectl get cronjob analytics-pipeline`, then `kubectl get jobs --sort-by=.status.startTime`.
2. Read the logs of the last failed job. The `model_runs` table records the error:
   `SELECT started_at, status, error FROM model_runs ORDER BY started_at DESC LIMIT 5;`.
3. Re-run manually with `kubectl create job analytics-manual --from=cronjob/analytics-pipeline`.
4. `model_skipped` in the run metrics means fewer than 200 complete sales. That is a data
   problem, not a code problem.

## valuation-model-degraded

The conformal coverage or median APE alert has fired.

1. Inspect recent runs:
   `SELECT finished_at, metrics->'cross_validation'->'hedonic_conformal' FROM model_runs WHERE status='succeeded' ORDER BY finished_at DESC LIMIT 10;`.
2. **Sudden drop.** Look for a data-quality event, such as a feed importing wrong prices.
   Check the RealEstateSync status and look for outliers in `listings.sale_price`.
3. **Gradual drop.** This usually means a market regime change, where the pooled time
   dummies no longer fit (see methodology §8). Consider shortening the training window.
4. Until resolved, treat the valuation intervals shown in the UI as unreliable, and
   consider a banner.

## exporter-down

`kubeestatehub_exporter_up == 0`: metrics-service cannot query PostgreSQL. It keeps
serving the last snapshot. Check `kubectl logs deploy/metrics-service`. The usual causes
are NetworkPolicy changes and secret rotation. Pods read `db-secret` only at start, so
run `kubectl rollout restart deploy/metrics-service` after a rotation.

## api-down

No listings-api target is up.

1. Check `kubectl get pods -l app.kubernetes.io/name=listings-api`.
2. Look at events for image pull or admission errors. The admission policy rejects
   unpinned images and missing limits.
3. Check whether the pods are running but unready. Readiness fails until the schema
   version the build requires is migrated: `kubectl get job db-migrate`,
   `SELECT * FROM schema_migrations;`.

## postgres-down

1. `kubectl describe pod postgres-0` shows PVC, OOM or node problems.
2. `kubectl logs postgres-0 -c postgres`.
3. If the data volume is lost, restore from backup; see [database.md](database.md#restore).

## postgres-connections

Connections are above 80% of `max_connections`. There are 200 connections in total, and
each API worker process holds up to `DB_POOL_MAX`. Replicas × workers × pool size must
stay below the limit. Scale the pool down, or put PgBouncer in front of PostgreSQL.
