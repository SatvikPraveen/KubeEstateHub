# Location: `/docs/operators-guide.md`

# Kubernetes Operators Guide

Guide to custom operators and operator-based automation in KubeEstateHub.

## Real Estate Sync Operator

### Custom Resource Definition

```yaml
# Location: manifests/operators/realestate-sync-crd.yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: realestatesyncs.kubeestatehub.io
spec:
  group: kubeestatehub.io
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                source:
                  type: string
                schedule:
                  type: string
                enabled:
                  type: boolean
            status:
              type: object
              properties:
                lastSync:
                  type: string
                syncCount:
                  type: integer
                phase:
                  type: string
  scope: Namespaced
  names:
    plural: realestatesyncs
    singular: realestatesync
    kind: RealEstateSync
```

### Custom Resource Example

```yaml
# Location: manifests/operators/realestate-sync-cr.yaml
apiVersion: kubeestatehub.io/v1
kind: RealEstateSync
metadata:
  name: mls-sync
  namespace: kubeestatehub
spec:
  source: "mls-api-endpoint"
  schedule: "*/30 * * * *"
  enabled: true
```

### Operator Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: realestate-sync-operator
  namespace: kubeestatehub
spec:
  replicas: 1
  selector:
    matchLabels:
      name: realestate-sync-operator
  template:
    metadata:
      labels:
        name: realestate-sync-operator
    spec:
      containers:
        - name: operator
          image: kubeestatehub/realestate-sync-operator:latest
          env:
            - name: WATCH_NAMESPACE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.namespace
          resources:
            limits:
              cpu: 200m
              memory: 256Mi
            requests:
              cpu: 100m
              memory: 128Mi
```

## Operator Management

### Install Operator

```bash
# Apply CRD
kubectl apply -f manifests/operators/realestate-sync-crd.yaml

# Apply RBAC
kubectl apply -f manifests/operators/operator-rbac.yaml

# Deploy operator
kubectl apply -f manifests/operators/realestate-sync-operator-deployment.yaml

# Verify operator
kubectl get pods -l name=realestate-sync-operator -n kubeestatehub
kubectl logs -f deployment/realestate-sync-operator -n kubeestatehub
```

### Create Custom Resources

```bash
# Create sync job
kubectl apply -f manifests/operators/realestate-sync-cr.yaml

# List custom resources
kubectl get realestatesyncs -n kubeestatehub
kubectl describe realestatesync mls-sync -n kubeestatehub
```

### Monitor Operator

```bash
# Check operator status
kubectl get deployment realestate-sync-operator -n kubeestatehub
kubectl logs deployment/realestate-sync-operator -n kubeestatehub

# Check custom resource status
kubectl get realestatesyncs -o yaml -n kubeestatehub
```

## Operator Best Practices

### Resource Management

- Set appropriate resource limits
- Use health checks and readiness probes
- Implement graceful shutdown handling
- Monitor operator performance metrics

### Error Handling

- Implement retry logic with exponential backoff
- Use status conditions to report errors
- Log errors appropriately for debugging
- Handle edge cases and validation

### Security

- Use least privilege RBAC permissions
- Validate custom resource specifications
- Implement admission webhooks for validation
- Use service accounts with minimal permissions

This operators guide provides foundation for extending KubeEstateHub with custom automation through Kubernetes operators.
