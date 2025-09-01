# Location: `/docs/kubectl-cheatsheet.md`

# Kubectl Cheatsheet for KubeEstateHub

Quick reference guide for managing KubeEstateHub with kubectl commands.

## Environment Setup

```bash
# Set default namespace
kubectl config set-context --current --namespace=kubeestatehub

# Source kubectl aliases
source scripts/kubectl-aliases.sh

# Verify cluster connection
kubectl cluster-info
kubectl get nodes
```

## Pod Management

### View Pods

```bash
# Get all pods in namespace
kubectl get pods
kubectl get pods -o wide
kubectl get pods --show-labels

# Get pods with specific labels
kubectl get pods -l app=listings-api
kubectl get pods -l app.kubernetes.io/name=kubeestatehub

# Watch pod status
kubectl get pods -w
```

### Pod Details and Debugging

```bash
# Describe a pod
kubectl describe pod <pod-name>

# Get pod logs
kubectl logs <pod-name>
kubectl logs <pod-name> -f --tail=100
kubectl logs <pod-name> -c <container-name>

# Previous container logs
kubectl logs <pod-name> --previous

# Execute commands in pod
kubectl exec -it <pod-name> -- /bin/bash
kubectl exec -it <pod-name> -- sh
kubectl exec <pod-name> -- ls /app
```

## Deployment Management

### View Deployments

```bash
# Get deployments
kubectl get deployments
kubectl get deployments -o wide

# Describe deployment
kubectl describe deployment <deployment-name>

# Get deployment YAML
kubectl get deployment <deployment-name> -o yaml
```

### Scaling and Updates

```bash
# Scale deployment
kubectl scale deployment <deployment-name> --replicas=3

# Update image
kubectl set image deployment/<deployment-name> <container-name>=<new-image>

# Rollout commands
kubectl rollout status deployment/<deployment-name>
kubectl rollout history deployment/<deployment-name>
kubectl rollout undo deployment/<deployment-name>
kubectl rollout restart deployment/<deployment-name>
```

## Service Management

### View Services

```bash
# Get services
kubectl get services
kubectl get svc -o wide

# Describe service
kubectl describe service <service-name>

# Get service endpoints
kubectl get endpoints
kubectl get endpoints <service-name>
```

### Port Forwarding

```bash
# Port forward to service
kubectl port-forward svc/<service-name> <local-port>:<service-port>

# Port forward to pod
kubectl port-forward pod/<pod-name> <local-port>:<container-port>

# KubeEstateHub specific port forwards
kubectl port-forward svc/frontend-dashboard-service 3000:80
kubectl port-forward svc/listings-api-service 8080:8080
kubectl port-forward svc/postgres-service 5432:5432
kubectl port-forward svc/grafana-service 3001:3000
```

## Configuration Management

### ConfigMaps and Secrets

```bash
# Get configmaps and secrets
kubectl get configmaps
kubectl get secrets

# Describe configuration
kubectl describe configmap <configmap-name>
kubectl describe secret <secret-name>

# View secret data (base64 decoded)
kubectl get secret <secret-name> -o jsonpath='{.data.<key>}' | base64 -d

# Create secret from literal
kubectl create secret generic <secret-name> --from-literal=key=value

# Create configmap from file
kubectl create configmap <configmap-name> --from-file=path/to/file
```

### Edit Resources

```bash
# Edit deployment
kubectl edit deployment <deployment-name>

# Edit service
kubectl edit service <service-name>

# Edit configmap
kubectl edit configmap <configmap-name>
```

## Storage Management

### Persistent Volumes

```bash
# Get persistent volumes
kubectl get pv
kubectl get pvc

# Describe storage
kubectl describe pv <pv-name>
kubectl describe pvc <pvc-name>

# Storage usage
kubectl get pvc -o custom-columns=NAME:.metadata.name,STATUS:.status.phase,CAPACITY:.spec.resources.requests.storage
```

## Monitoring and Troubleshooting

### Resource Usage

```bash
# Resource usage (requires metrics-server)
kubectl top nodes
kubectl top pods
kubectl top pods --containers

# Resource limits and requests
kubectl describe nodes
kubectl get pods -o custom-columns=NAME:.metadata.name,CPU_REQ:.spec.containers[*].resources.requests.cpu,MEM_REQ:.spec.containers[*].resources.requests.memory
```

### Events and Logs

```bash
# Get events
kubectl get events
kubectl get events --sort-by=.metadata.creationTimestamp
kubectl get events --field-selector type=Warning

# Cluster events
kubectl get events --all-namespaces
kubectl get events -w
```

### Debugging Commands

```bash
# Check pod readiness
kubectl get pods -o custom-columns=NAME:.metadata.name,READY:.status.containerStatuses[*].ready,STATUS:.status.phase

# Get pod restart count
kubectl get pods -o custom-columns=NAME:.metadata.name,RESTARTS:.status.containerStatuses[*].restartCount

# Find pods not running
kubectl get pods --field-selector=status.phase!=Running

# Get pod IP addresses
kubectl get pods -o custom-columns=NAME:.metadata.name,IP:.status.podIP,NODE:.spec.nodeName
```

## Network Debugging

### DNS and Connectivity

```bash
# Test DNS resolution
kubectl exec -it <pod-name> -- nslookup kubernetes.default
kubectl exec -it <pod-name> -- nslookup <service-name>

# Test connectivity
kubectl exec -it <pod-name> -- wget -qO- <service-name>:<port>
kubectl exec -it <pod-name> -- curl -v <service-name>:<port>/health

# Network policies
kubectl get networkpolicies
kubectl describe networkpolicy <policy-name>
```

### Ingress

```bash
# Get ingress resources
kubectl get ingress
kubectl describe ingress <ingress-name>

# Get ingress controller pods
kubectl get pods -n ingress-nginx
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

## Security and RBAC

### Service Accounts and RBAC

```bash
# Get service accounts
kubectl get serviceaccounts
kubectl get sa

# Get roles and role bindings
kubectl get roles
kubectl get rolebindings
kubectl get clusterroles
kubectl get clusterrolebindings

# Check permissions
kubectl auth can-i get pods
kubectl auth can-i create deployments
kubectl auth can-i '*' '*' --as=system:serviceaccount:default:my-sa
```

### Security Contexts

```bash
# Check security contexts
kubectl get pods -o custom-columns=NAME:.metadata.name,SECURITY_CONTEXT:.spec.securityContext
kubectl get pods <pod-name> -o jsonpath='{.spec.containers[*].securityContext}'
```

## Backup and Restore

### ETCD Backup (if access available)

```bash
# Create etcd backup
kubectl get all --all-namespaces -o yaml > cluster-backup.yaml

# Backup specific namespace
kubectl get all -n kubeestatehub -o yaml > kubeestatehub-backup.yaml
```

### Database Backup

```bash
# Backup PostgreSQL database
kubectl exec -it postgres-0 -- pg_dump -U admin kubeestatehub > backup.sql

# Restore database
cat backup.sql | kubectl exec -i postgres-0 -- psql -U admin -d kubeestatehub
```

## KubeEstateHub Specific Commands

### Application Health Checks

```bash
# Check API health
kubectl exec deployment/listings-api -- curl localhost:8080/health

# Check database connectivity
kubectl exec postgres-0 -- pg_isready -U admin

# Check frontend
kubectl exec deployment/frontend-dashboard -- wget -qO- localhost:80/
```

### Quick Status Overview

```bash
# All KubeEstateHub resources
kubectl get all -l app.kubernetes.io/name=kubeestatehub

# Pod status with restart counts
kubectl get pods -o custom-columns=NAME:.metadata.name,STATUS:.status.phase,RESTARTS:.status.containerStatuses[*].restartCount,AGE:.metadata.creationTimestamp

# Service endpoints
kubectl get endpoints -o wide

# Storage status
kubectl get pvc -o custom-columns=NAME:.metadata.name,STATUS:.status.phase,CAPACITY:.spec.resources.requests.storage,STORAGECLASS:.spec.storageClassName
```

### Scaling Operations

```bash
# Scale API service
kubectl scale deployment listings-api --replicas=3

# Scale frontend
kubectl scale deployment frontend-dashboard --replicas=2

# Scale based on CPU
kubectl autoscale deployment listings-api --cpu-percent=70 --min=1 --max=10
```

### Log Analysis

```bash
# Tail logs from all API pods
kubectl logs -l app=listings-api -f --tail=50

# Get logs from multiple containers
kubectl logs -l app=listings-api --all-containers=true

# Search logs for errors
kubectl logs deployment/listings-api | grep -i error

# Export logs to file
kubectl logs deployment/listings-api --since=1h > api-logs.txt
```

## Useful One-liners

### Resource Queries

```bash
# Get pod names only
kubectl get pods -o name | cut -d/ -f2

# Get pod IPs
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.podIP}{"\n"}{end}'

# Get node resource allocation
kubectl describe nodes | grep -A 5 "Allocated resources"

# Find largest pods by memory request
kubectl get pods -o custom-columns=NAME:.metadata.name,MEMORY:.spec.containers[*].resources.requests.memory --sort-by=.spec.containers[0].resources.requests.memory
```

### Cleanup Commands

```bash
# Delete failed pods
kubectl delete pods --field-selector=status.phase=Failed

# Delete evicted pods
kubectl get pods | grep Evicted | awk '{print $1}' | xargs kubectl delete pod

# Force delete stuck pods
kubectl delete pod <pod-name> --force --grace-period=0
```

### Bulk Operations

```bash
# Restart all deployments
kubectl get deployments -o name | xargs -I {} kubectl rollout restart {}

# Get all container images
kubectl get pods -o jsonpath='{range .items[*]}{.spec.containers[*].image}{"\n"}{end}' | sort -u

# Delete all resources in namespace
kubectl delete all --all -n <namespace>
```

## Advanced Debugging

### Container Analysis

```bash
# Get container specifications
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[*]}'

# Check resource limits
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[*].resources}'

# Get environment variables
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[*].env[*]}'
```

### Network Analysis

```bash
# Get all service cluster IPs
kubectl get services -o custom-columns=NAME:.metadata.name,CLUSTER-IP:.spec.clusterIP,TYPE:.spec.type

# Check ingress backends
kubectl get ingress -o custom-columns=NAME:.metadata.name,HOSTS:.spec.rules[*].host,PATHS:.spec.rules[*].http.paths[*].path

# Get network policies affecting pods
kubectl get networkpolicy -o yaml
```

### Performance Analysis

```bash
# Resource usage over time
watch kubectl top pods

# Monitor deployment rollout
kubectl rollout status deployment/<deployment-name> --watch=true

# Check horizontal pod autoscaler status
kubectl get hpa
kubectl describe hpa <hpa-name>
```

## Shortcuts and Aliases

After sourcing `scripts/kubectl-aliases.sh`:

```bash
# Basic shortcuts
k get pods                    # kubectl get pods
kehp                          # kubectl get pods -n kubeestatehub
keh-api                       # kubectl get pods -n kubeestatehub -l app=listings-api

# Log shortcuts
keh-api-logs                  # kubectl logs -n kubeestatehub -l app=listings-api -f
keh-fe-logs                   # kubectl logs -n kubeestatehub -l app=frontend-dashboard -f

# Port forward shortcuts
keh-pf-api                    # kubectl port-forward -n kubeestatehub svc/listings-api-service 8080:8080
keh-pf-fe                     # kubectl port-forward -n kubeestatehub svc/frontend-dashboard-service 3000:80

# Status shortcuts
keh-full-status               # Complete status report
keh-health-check              # Health check all services
```

This cheatsheet covers the most common kubectl operations for managing KubeEstateHub. Use these commands for daily operations, troubleshooting, and maintenance tasks.
