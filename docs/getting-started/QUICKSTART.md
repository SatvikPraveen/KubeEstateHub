# KubeEstateHub - Quick Start Guide

## Prerequisites

Before deploying, ensure you have:

- Kubernetes cluster (1.25+) with kubectl configured
- Docker installed (for building images locally)
- Helm 3.0+ (if using Helm deployment)
- At least 20GB disk space for development, 100GB for production

## Development Environment Setup

### 1. Clone and Navigate to Project

```bash
git clone https://github.com/SatvikPraveen/KubeEstateHub.git
cd KubeEstateHub
```

### 2. Create Development Namespace

```bash
kubectl create namespace kubeestatehub
kubectl config set-context --current --namespace=kubeestatehub
```

### 3. Deploy Using Manifests (Recommended for First Time)

```bash
# Option A: Using deploy script
chmod +x scripts/deploy-all.sh
./scripts/deploy-all.sh -e development

# Option B: Manual deployment
kubectl apply -f manifests/
```

### 4. Deploy Using Helm

```bash
# Install from charts
helm install kubeestatehub ./helm-charts/kubeestatehub \
  --namespace kubeestatehub \
  --values helm-charts/kubeestatehub/values-development.yaml
```

### 5. Deploy Using Kustomize

```bash
# Apply with Kustomize overlay
kubectl apply -k kustomize/overlays/development
```

## Accessing the Application

### Port Forwarding

```bash
# Frontend Dashboard (usually runs on port 3000)
kubectl port-forward svc/frontend-dashboard-service 3000:80

# API Service (usually runs on port 8080)
kubectl port-forward svc/listings-api-service 8080:8080

# Database (PostgreSQL on port 5432)
kubectl port-forward svc/postgresql-db 5432:5432

# Prometheus Metrics (if enabled)
kubectl port-forward svc/prometheus-service 9090:9090

# Grafana Dashboards (if enabled)
kubectl port-forward svc/grafana-service 3001:3000
```

Then access in browser:
- Frontend: http://localhost:3000
- API: http://localhost:8080/api/v1/listings
- API Health: http://localhost:8080/health
- Metrics: http://localhost:8080/metrics

### Using Ingress (Production)

Once ingress is set up with external IP:
- Frontend: https://kubeestatehub.io
- API: https://api.kubeestatehub.io

## Production Deployment

### 1. Update Configuration

Edit `helm-charts/kubeestatehub/values-production.yaml`:
- Change database passwords
- Update image repositories
- Configure ingress domain names
- Set up SSL certificates

### 2. Deploy to Production

```bash
./scripts/deploy-all.sh -e production --use-helm

# Or with Helm directly
helm install kubeestatehub ./helm-charts/kubeestatehub \
  --namespace kubeestatehub \
  -f helm-charts/kubeestatehub/values-production.yaml \
  --create-namespace
```

### 3. Verify Deployment

```bash
kubectl get pods -n kubeestatehub
kubectl get services -n kubeestatehub
kubectl describe deployment listings-api -n kubeestatehub
```

## Common Operations

### View Logs

```bash
# View logs from a specific pod
kubectl logs -n kubeestatehub <pod-name>

# Follow logs in real-time
kubectl logs -n kubeestatehub -f <pod-name>

# View logs from a specific container in a pod
kubectl logs -n kubeestatehub <pod-name> -c <container-name>

# View logs from all pods with a label
kubectl logs -n kubeestatehub -l app=listings-api --all-containers=true
```

### Check Pod Status

```bash
# List all pods with detailed info
kubectl get pods -n kubeestatehub -o wide

# Describe a specific pod for troubleshooting
kubectl describe pod -n kubeestatehub <pod-name>

# Check pod resource usage
kubectl top pods -n kubeestatehub
```

### Database Access

```bash
# Connect to PostgreSQL pod
kubectl exec -it postgresql-db-0 -n kubeestatehub -- psql -U kubeestatehub -d kubeestatehub

# Run migrations or initialization
kubectl exec -i postgresql-db-0 -n kubeestatehub -- psql -U kubeestatehub -d kubeestatehub < scripts/init-db.sql
```

### Scaling

```bash
# Scale a deployment
kubectl scale deployment listings-api -n kubeestatehub --replicas=5

# Check HPA status (if enabled)
kubectl get hpa -n kubeestatehub
```

### Update Configuration

```bash
# Update ConfigMap
kubectl create configmap listings-configmap --from-literal=LOG_LEVEL=debug -n kubeestatehub --dry-run=client -o yaml | kubectl apply -f -

# Update Secret
kubectl create secret generic db-secret --from-literal=password=newpassword -n kubeestatehub --dry-run=client -o yaml | kubectl apply -f -
```

## Monitoring and Observability

### Prometheus Metrics

All services expose Prometheus metrics:
- Listings API: `http://listings-api-service:8080/metrics`
- Analytics Worker: `http://analytics-worker:9090/metrics`
- Database: `http://postgresql-db:9187/metrics`

### Health Checks

```bash
# Check API health
curl http://localhost:8080/health

# Check readiness
curl http://localhost:8080/ready

# Check startup status
curl http://localhost:8080/startup
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod events
kubectl describe pod -n kubeestatehub <pod-name>

# Check logs
kubectl logs -n kubeestatehub <pod-name>

# Check resource limits
kubectl top pods -n kubeestatehub
```

### Database Connection Issues

```bash
# Check if database pod is running
kubectl get pods -n kubeestatehub -l app=postgresql-db

# Verify database service
kubectl get svc postgresql-db -n kubeestatehub

# Test database connection from pod
kubectl exec -it <pod-name> -n kubeestatehub -- psql -h postgresql-db -U kubeestatehub -d kubeestatehub -c "SELECT 1"
```

### API Not Responding

```bash
# Check if service is reachable
kubectl get svc listings-api-service -n kubeestatehub

# Test connectivity from a pod
kubectl exec -it <pod-name> -n kubeestatehub -- wget -q -O - http://listings-api-service:8080/health
```

### Image Pull Errors

```bash
# Check image availability locally
docker images | grep kubeestatehub

# Build images if not available
./scripts/deploy-all.sh --skip-build=false -e development

# Check image pull events
kubectl describe pod -n kubeestatehub <pod-name> | grep -A 5 "Events:"
```

## Cleanup and Teardown

```bash
# Delete entire namespace (removes everything)
kubectl delete namespace kubeestatehub

# Or using helm
helm uninstall kubeestatehub -n kubeestatehub

# Or using script
./scripts/teardown-all.sh -n kubeestatehub
```

## Performance Tuning

### Database Optimization

```bash
# Connect to database
kubectl exec -it postgresql-db-0 -n kubeestatehub -- psql -U kubeestatehub -d kubeestatehub

# Check query performance
EXPLAIN ANALYZE SELECT * FROM listings WHERE city = 'Austin';

# Analyze table statistics
ANALYZE listings;
```

### Resource Limits

Adjust resource requests/limits in:
- `manifests/base/` YAML files
- `helm-charts/kubeestatehub/values-*.yaml`

### Horizontal Scaling

Enable HPA for automatic scaling:
- Edit `manifests/autoscaling/hpa-listings-api.yaml`
- Or update Helm values: `listingsApi.autoscaling.enabled: true`

## Documentation

For more detailed information, see:
- [Architecture Overview](docs/architecture-overview.md)
- [Security Best Practices](docs/security-best-practices.md)
- [Debugging Guide](docs/debugging-guide.md)
- [Monitoring Guide](docs/monitoring-guide.md)
- [Scaling Guide](docs/scaling-guide.md)
- [FAQ](docs/faq.md)

## Support

If you encounter issues:

1. Check the [Debugging Guide](docs/debugging-guide.md)
2. Review pod logs: `kubectl logs -n kubeestatehub <pod-name>`
3. Check events: `kubectl get events -n kubeestatehub`
4. Verify configuration: `kubectl describe deployment <deployment-name> -n kubeestatehub`
5. Open an issue on GitHub with logs and detailed description
