# Helm chart

`helm-charts/kubeestatehub` packages the same resources as the production kustomize
overlay. CI checks that the two render identical resource sets. The chart is
self-contained with no subchart dependencies, validates its values against
`values.schema.json`, and ships the CRD in `crds/`.

```bash
kubectl create namespace kubeestatehub
kubectl label namespace kubeestatehub pod-security.kubernetes.io/enforce=restricted
helm install keh helm-charts/kubeestatehub -n kubeestatehub -f helm-charts/kubeestatehub/values-development.yaml
helm test keh -n kubeestatehub
```

| Values file | Purpose |
|---|---|
| `values.yaml` | Defaults. Expects pre-created `db-secret` and `api-secret` |
| `values-development.yaml` | Renders development credentials, 1 replica, admission policy in Warn |
| `values-staging.yaml` | ExternalSecrets, monitoring, backups |
| `values-production.yaml` | ExternalSecrets, TLS, HA sizing, monitoring, backups, admission policy Deny |

**Design choices.**

* Resource names are fixed, not release-prefixed, for two reasons. The dashboard proxies to
  the Service `listings-api`, and the NetworkPolicies select pods by
  `app.kubernetes.io/name`. Install one release per namespace.
* Migrations run as a `post-install,post-upgrade` hook with `before-hook-creation`, so
  every upgrade re-runs the idempotent migration runner.
* The chart copies several files from their single sources: the SQL migrations, alert
  rules, dashboards, CRD, admission policy and backup CronJob. `hack/generate.py` produces
  these copies, and CI fails if they drift.
