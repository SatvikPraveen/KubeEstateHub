# Platform prerequisites

KubeEstateHub runs on any conformant Kubernetes ≥ 1.30. That version is the minimum
because ValidatingAdmissionPolicy went GA in 1.30. The application expects the cluster
services below. They are installed from upstream charts at pinned versions instead of being
vendored as hand-maintained manifests.

| Component | Why | Used by |
|---|---|---|
| ingress-nginx | HTTP entry point | `Ingress/kubeestatehub` |
| kube-prometheus-stack | Prometheus Operator, Alertmanager, Grafana | `components/monitoring` (ServiceMonitors, PrometheusRule, dashboards) |
| prometheus-pushgateway | Metrics from the batch pipeline (optional) | `PUSHGATEWAY_URL` of the analytics CronJob |
| metrics-server | Resource metrics | HorizontalPodAutoscalers |
| external-secrets | Credentials from a secret manager | staging and production overlays (`ExternalSecret`) |
| cert-manager | TLS certificates | production Ingress |

```bash
helmfile -f platform/helmfile.yaml sync
```

The network policies assume ingress-nginx runs in the `ingress-nginx` namespace and
Prometheus in `monitoring`. For a throwaway local cluster, `make kind-e2e` installs only
ingress-nginx.
