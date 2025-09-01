# Location: `/docs/gitops-with-argocd.md`

# GitOps with ArgoCD

Guide to implementing GitOps practices for KubeEstateHub using ArgoCD for continuous deployment and configuration management.

## ArgoCD Setup

### Installation

```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for deployment
kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd

# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Port forward to access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

### ArgoCD Configuration

```yaml
# ArgoCD application for KubeEstateHub
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kubeestatehub
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/kubeestatehub.git
    targetRevision: HEAD
    path: manifests/base
  destination:
    server: https://kubernetes.default.svc
    namespace: kubeestatehub
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true
  revisionHistoryLimit: 10
```

## Multi-Environment Management

### Environment Structure

```
environments/
├── development/
│   ├── kustomization.yaml
│   └── values.yaml
├── staging/
│   ├── kustomization.yaml
│   └── values.yaml
└── production/
    ├── kustomization.yaml
    └── values.yaml
```

### Development Environment

```yaml
# ArgoCD app for development
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kubeestatehub-dev
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/kubeestatehub.git
    targetRevision: HEAD
    path: kustomize/overlays/development
  destination:
    server: https://kubernetes.default.svc
    namespace: kubeestatehub-dev
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### Production Environment

```yaml
# Production requires manual sync
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kubeestatehub-prod
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/kubeestatehub.git
    targetRevision: v1.0.0 # Specific tag/version
    path: kustomize/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: kubeestatehub-prod
  syncPolicy:
    automated:
      prune: false # Manual approval for production
      selfHeal: false
```

## GitOps Workflow

### Development Workflow

1. Developers push code changes to feature branches
2. CI pipeline builds and tests applications
3. CI updates image tags in development manifests
4. ArgoCD automatically syncs development environment
5. Integration tests run in development

### Staging Workflow

1. Pull request merged to main branch
2. CI builds production-ready images
3. CI updates staging manifests with new image tags
4. ArgoCD syncs staging environment
5. QA testing and validation

### Production Workflow

1. Tag release with semantic version
2. Manually update production manifests
3. Create pull request for production changes
4. Review and approve changes
5. ArgoCD syncs production after manual approval

## Application Management

### ArgoCD CLI Usage

```bash
# Login to ArgoCD
argocd login localhost:8080

# List applications
argocd app list

# Get application details
argocd app get kubeestatehub

# Sync application
argocd app sync kubeestatehub

# Monitor sync status
argocd app wait kubeestatehub

# Rollback to previous version
argocd app rollback kubeestatehub 1
```

### Application Health Monitoring

```yaml
# Custom health check for KubeEstateHub
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  resource.customizations.health.argoproj.io_Application: |
    hs = {}
    hs.status = "Progressing"
    hs.message = ""
    if obj.status ~= nil then
      if obj.status.health ~= nil then
        hs.status = obj.status.health.status
        hs.message = obj.status.health.message
      end
    end
    return hs
```

## Security and RBAC

### ArgoCD RBAC Configuration

```yaml
# ArgoCD RBAC policy
policy.default: role:readonly
policy.csv: |
  p, role:admin, applications, *, */*, allow
  p, role:admin, clusters, *, *, allow
  p, role:admin, repositories, *, *, allow

  p, role:dev, applications, get, */*, allow
  p, role:dev, applications, sync, kubeestatehub-dev, allow

  g, kubeestatehub-admins, role:admin
  g, kubeestatehub-developers, role:dev
```

### Secret Management

```yaml
# External secrets with ArgoCD
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: database-secret
  namespace: kubeestatehub
spec:
  refreshInterval: 15s
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: db-secret
    creationPolicy: Owner
  data:
    - secretKey: password
      remoteRef:
        key: secret/database
        property: password
```

## Monitoring and Alerts

### ArgoCD Metrics

```yaml
# ServiceMonitor for ArgoCD
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: argocd-metrics
  namespace: argocd
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: argocd-server-metrics
  endpoints:
    - port: metrics
```

### GitOps Alerts

```yaml
# Prometheus alerting rules for GitOps
groups:
  - name: argocd.rules
    rules:
      - alert: ArgoAppSyncFailed
        expr: argocd_app_health_status{health_status!="Healthy"} == 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "ArgoCD app sync failed"
          description: "Application {{ $labels.name }} is not healthy"

      - alert: ArgoAppOutOfSync
        expr: argocd_app_sync_total{phase!="Succeeded"} == 1
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "ArgoCD app out of sync"
          description: "Application {{ $labels.name }} is out of sync"
```

## Best Practices

### Repository Structure

- Keep application code and deployment manifests in separate repositories
- Use semantic versioning for releases
- Implement branch protection rules
- Require pull request reviews for production changes

### Application Configuration

- Use Kustomize or Helm for environment-specific configurations
- Implement progressive delivery patterns
- Use health checks and readiness probes
- Define resource limits and requests

### Security Practices

- Use least-privilege RBAC policies
- Implement secret management with external secret operators
- Enable audit logging for all ArgoCD operations
- Regularly update ArgoCD and associated components

This GitOps guide establishes a robust continuous deployment pipeline for KubeEstateHub using ArgoCD, ensuring consistent and reliable deployments across environments.
