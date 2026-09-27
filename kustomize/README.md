# Kustomize deployment

```
manifests/base/                  application: namespace (PSA restricted), quota, Postgres,
                                 Redis, migrate Job, API, dashboard, exporter, analytics
                                 CronJob, Ingress, default-deny NetworkPolicies
manifests/components/
  monitoring/                    ServiceMonitors, PrometheusRule (SLOs + model quality), dashboards
  operator/                      RealEstateSync CRD, operator, least-privilege RBAC
  admission-policy/              CEL ValidatingAdmissionPolicy (pinned images, RO rootfs, limits)
  backup/                        nightly verified pg_dump with retention
kustomize/overlays/
  development/                   kind/minikube: 1 replica, generated dev credentials
  staging/                       all components, ExternalSecrets, policy in Warn/Audit
  production/                    all components, ExternalSecrets, TLS, HA sizing, policy Deny
  e2e/                           development + locally built images (hack/kind-e2e.sh)
```

```bash
kubectl apply -k kustomize/overlays/development     # needs ingress-nginx for the Ingress
kubectl -n kubeestatehub create job analytics-now --from=cronjob/analytics-pipeline
```

## Secrets contract

Every overlay must provide two Secrets. `hack/validate.sh` fails if one is missing (conftest
`kubernetes.combined`).

| Secret | Keys |
|---|---|
| `db-secret` | `username`, `password`, `database-url` |
| `api-secret` | `write-token` |

The development overlay generates throwaway values. Staging and production obtain them
through External Secrets Operator from `kubeestatehub/<env>/{postgres,api}`.

## Ordering without hooks

Kustomize has no install hooks. The `db-migrate` Job runs alongside the Deployments, and
the listings API stays **unready** until the schema version it requires is recorded in
`schema_migrations`. The Job uses `ttlSecondsAfterFinished`, so the next `kubectl apply`
recreates the otherwise immutable Job for a new release.

## Validation

`make validate` renders every overlay and runs these checks:

* kubeconform (strict, Kubernetes 1.31, CRD catalog)
* kube-linter
* conftest workload, RBAC and cross-resource policies
* promtool rule tests
* a kustomize/Helm resource-parity check

`make kind-e2e` deploys the e2e overlay to a real cluster and asserts behaviour end to end.
