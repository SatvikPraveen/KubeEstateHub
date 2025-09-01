# Location: `/helm-charts/README.md`

# KubeEstateHub Helm Charts

This directory contains Helm charts for deploying KubeEstateHub on Kubernetes clusters.

## Installation

### Prerequisites

- Kubernetes 1.19+
- Helm 3.8+
- PV provisioner support in the underlying infrastructure

### Add Helm Repository

```bash
helm repo add kubeestatehub https://charts.kubeestatehub.io
helm repo update
```

### Install Chart

```bash
# Install with default values
helm install kubeestatehub kubeestatehub/kubeestatehub

# Install with custom values
helm install kubeestatehub kubeestatehub/kubeestatehub -f custom-values.yaml

# Install in specific namespace
helm install kubeestatehub kubeestatehub/kubeestatehub -n kubeestatehub --create-namespace
```

## Configuration

### Common Configuration Options

| Parameter                               | Description             | Default               |
| --------------------------------------- | ----------------------- | --------------------- |
| `listingsApi.replicaCount`              | Number of API replicas  | `3`                   |
| `listingsApi.resources.requests.cpu`    | CPU request for API     | `200m`                |
| `listingsApi.resources.requests.memory` | Memory request for API  | `256Mi`               |
| `postgresql.enabled`                    | Enable PostgreSQL       | `true`                |
| `redis.enabled`                         | Enable Redis            | `true`                |
| `monitoring.enabled`                    | Enable monitoring stack | `true`                |
| `ingress.enabled`                       | Enable ingress          | `true`                |
| `ingress.hosts[0].host`                 | Hostname for ingress    | `kubeestatehub.local` |

### Security Configuration

| Parameter                               | Description                  | Default      |
| --------------------------------------- | ---------------------------- | ------------ |
| `security.podSecurityPolicy.enabled`    | Enable Pod Security Policy   | `true`       |
| `security.networkPolicies.enabled`      | Enable Network Policies      | `true`       |
| `security.podSecurityStandards.enforce` | Pod Security Standards level | `restricted` |

### Storage Configuration

| Parameter                             | Description             | Default |
| ------------------------------------- | ----------------------- | ------- |
| `global.storageClass`                 | Default storage class   | `""`    |
| `postgresql.primary.persistence.size` | PostgreSQL storage size | `50Gi`  |
| `imageStore.persistence.size`         | MinIO storage size      | `100Gi` |

## Examples

### Development Environment

```yaml
# dev-values.yaml
listingsApi:
  replicaCount: 1
  resources:
    requests:
      cpu: 100m
      memory: 128Mi

postgresql:
  primary:
    persistence:
      size: 10Gi

monitoring:
  prometheus:
    server:
      retention: "7d"
```

### Production Environment

```yaml
# prod-values.yaml
listingsApi:
  replicaCount: 5
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 15

postgresql:
  primary:
    persistence:
      size: 100Gi
    resources:
      requests:
        cpu: 1000m
        memory: 2Gi

monitoring:
  prometheus:
    server:
      retention: "30d"
      persistentVolume:
        size: 50Gi
```

### High Availability Setup

```yaml
# ha-values.yaml
listingsApi:
  replicaCount: 5
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchExpressions:
              - key: app.kubernetes.io/component
                operator: In
                values:
                  - listings-api
          topologyKey: kubernetes.io/hostname

postgresql:
  architecture: replication
  primary:
    persistence:
      size: 200Gi
  readReplicas:
    replicaCount: 2
```

## Upgrading

```bash
# Upgrade to latest version
helm upgrade kubeestatehub kubeestatehub/kubeestatehub

# Upgrade with new values
helm upgrade kubeestatehub kubeestatehub/kubeestatehub -f new-values.yaml
```

## Uninstallation

```bash
# Uninstall release
helm uninstall kubeestatehub

# Uninstall with namespace cleanup
helm uninstall kubeestatehub -n kubeestatehub
kubectl delete namespace kubeestatehub
```

## Troubleshooting

### Common Issues

1. **Pod Security Policy errors**: Ensure cluster supports PSP or disable with `security.podSecurityPolicy.enabled=false`
2. **Storage issues**: Verify storage class availability
3. **Ingress not working**: Check ingress controller installation
4. **Database connection issues**: Verify PostgreSQL is running and accessible

### Debug Commands

```bash
# Check release status
helm status kubeestatehub

# Get all resources
kubectl get all -l app.kubernetes.io/instance=kubeestatehub

# Check pod logs
kubectl logs -l app.kubernetes.io/component=listings-api

# Debug helm template
helm template kubeestatehub ./kubeestatehub --debug
```

## Development

### Testing Charts Locally

```bash
# Lint charts
helm lint ./kubeestatehub

# Template with debug
helm template test ./kubeestatehub --debug --dry-run

# Install from local chart
helm install kubeestatehub ./kubeestatehub --dry-run
```

### Chart Dependencies

```bash
# Update dependencies
helm dependency update ./kubeestatehub

# Build dependencies
helm dependency build ./kubeestatehub
```
