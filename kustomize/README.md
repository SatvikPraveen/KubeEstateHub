# Location: `/kustomize/README.md`

# Kustomize Environment Management

This directory contains Kustomize configurations for managing KubeEstateHub deployments across different environments.

## Directory Structure

```
kustomize/
├── base/
│   └── kustomization.yaml          # Base configuration
├── overlays/
│   ├── development/
│   │   ├── kustomization.yaml      # Development overrides
│   │   └── patches/                # Development patches
│   ├── staging/
│   │   ├── kustomization.yaml      # Staging overrides
│   │   └── patches/                # Staging patches
│   └── production/
│       ├── kustomization.yaml      # Production overrides
│       ├── patches/                # Production patches
│       ├── secrets/                # Production secrets
│       └── transformers/           # Production transformers
└── README.md
```

## Quick Start

### Deploy to Development

```bash
kubectl apply -k kustomize/overlays/development/
```

### Deploy to Staging

```bash
kubectl apply -k kustomize/overlays/staging/
```

### Deploy to Production

```bash
kubectl apply -k kustomize/overlays/production/
```

## Environment Differences

### Development

- **Namespace**: `kubeestatehub-dev`
- **Replicas**: Single replica for all services
- **Resources**: Minimal resource allocation
- **Debugging**: Enabled with verbose logging
- **Image Tags**: `develop` branch builds
- **Features**: Development tools enabled

### Staging

- **Namespace**: `kubeestatehub-staging`
- **Replicas**: Reduced replicas (2 for critical services)
- **Resources**: Medium resource allocation
- **Monitoring**: Full monitoring enabled
- **Image Tags**: `staging` branch builds
- **Features**: Production-like environment

### Production

- **Namespace**: `kubeestatehub`
- **Replicas**: Full high-availability setup
- **Resources**: Production resource allocation
- **Security**: Enhanced security policies
- **Image Tags**: Versioned releases (e.g., `v1.0.0`)
- **Features**: Full production features

## Customization

### Adding New Environment

1. Create new overlay directory: `overlays/[environment]/`
2. Add `kustomization.yaml` with environment-specific configs
3. Create patches for environment-specific changes
4. Add secrets and configmaps as needed

### Modifying Resources

- **Base changes**: Edit `base/kustomization.yaml`
- **Environment-specific**: Add patches in respective overlay

### Managing Secrets

```bash
# Generate secret files for production
echo -n 'your-jwt-secret' > overlays/production/secrets/jwt-secret.key
echo -n 'your-db-password' > overlays/production/secrets/db-password.key
```

## Validation

### Dry Run

```bash
kubectl apply -k kustomize/overlays/production/ --dry-run=client -o yaml
```

### Diff Against Current

```bash
kubectl diff -k kustomize/overlays/production/
```

### Validate Build

```bash
kustomize build kustomize/overlays/production/ > /tmp/production.yaml
kubectl apply --dry-run=client -f /tmp/production.yaml
```

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Deploy to staging
  run: |
    kubectl apply -k kustomize/overlays/staging/
    kubectl rollout status deployment/staging-listings-api-staging -n kubeestatehub-staging
```

### ArgoCD Application

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kubeestatehub-production
spec:
  source:
    repoURL: https://github.com/your-org/kubeestatehub
    path: kustomize/overlays/production
    targetRevision: main
  destination:
    server: https://kubernetes.default.svc
    namespace: kubeestatehub
```

## Best Practices

1. **Use semantic versioning** for production image tags
2. **Keep secrets encrypted** in git (use sealed-secrets or external secret managers)
3. **Test overlays** in lower environments before production
4. **Use consistent naming** across environments
5. **Document environment differences** clearly
6. **Automate deployments** through CI/CD pipelines

## Troubleshooting

### Common Issues

- **Resource conflicts**: Check for duplicate names across environments
- **Missing secrets**: Ensure all required secrets are generated
- **Image pull errors**: Verify image tags exist in registry
- **RBAC issues**: Check service account permissions

### Debug Commands

```bash
# View generated manifests
kustomize build kustomize/overlays/production/

# Check kustomization syntax
kustomize cfg fmt kustomize/overlays/production/

# Validate against cluster
kubectl apply -k kustomize/overlays/production/ --dry-run=server
```
