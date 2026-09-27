# Database operations

## Topology

The kustomize base and the chart run a single-primary PostgreSQL 16 StatefulSet with the
following settings:

* `scram-sha-256` authentication and data checksums enabled at initdb.
* A read-only root filesystem.
* A postgres-exporter sidecar.

This is appropriate for development and small deployments. For production HA, point
`db-secret.database-url` at a managed service (RDS, Cloud SQL, Azure Database) or at a
CloudNativePG cluster, and remove the StatefulSet with a kustomize patch. The application
only needs the `database-url`.

## Migrations

Migrations live in `db/migrations`. They are forward-only, and each is applied once with
a recorded checksum; see `db/README.md`.

* **Kustomize:** the `db-migrate` Job runs on every apply. The API is unready until
  `REQUIRED_SCHEMA_VERSION` is present.
* **Helm:** a `post-install,post-upgrade` hook.
* **Writing a migration:** add `NNNN_description.sql` and bump
  `REQUIRED_SCHEMA_VERSION`. A unit test enforces the bump. Then run `make generate` and
  keep the migration backward compatible with the previous API version, because pods
  roll gradually.

## Backups

The backup component runs `pg_dump --format=custom` nightly at 01:00 UTC to the
`db-backups` PVC. It verifies each archive with `pg_restore --list` before renaming it
into place and keeps `BACKUP_RETENTION_DAYS` (14). This gives logical backups with an RPO
of about 24 h. For point-in-time recovery, use WAL archiving (CloudNativePG with object
storage, or the managed service's PITR).

## Restore

```bash
kubectl scale deploy/listings-api deploy/metrics-service --replicas=0
kubectl run pg-restore --rm -it --image=postgres:16.4-alpine --restart=Never \
  --overrides='{"spec":{"volumes":[{"name":"b","persistentVolumeClaim":{"claimName":"db-backups"}}],
  "containers":[{"name":"pg-restore","image":"postgres:16.4-alpine","stdin":true,"tty":true,
  "volumeMounts":[{"name":"b","mountPath":"/backups"}]}]}}' -- sh
# inside the pod:
export PGHOST=postgres PGUSER=kubeestatehub PGDATABASE=kubeestatehub PGPASSWORD=...
pg_restore --clean --if-exists --no-owner -d kubeestatehub /backups/kubeestatehub-<timestamp>.dump
exit
kubectl scale deploy/listings-api --replicas=2 && kubectl scale deploy/metrics-service --replicas=1
```

Test restores regularly. A backup that has never been restored is not a backup.
