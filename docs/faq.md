# Location: `/docs/faq.md`

# Frequently Asked Questions

Common questions and solutions for KubeEstateHub deployment and operations.

## Deployment Issues

### Q: Pods are stuck in Pending state

**A:** Check the following:

```bash
kubectl describe pod <pod-name> -n kubeestatehub
kubectl get events -n kubeestatehub --sort-by='.lastTimestamp'
kubectl get nodes  # Check node capacity
kubectl get pvc -n kubeestatehub  # Check storage claims
```

Common causes:

- Insufficient cluster resources (CPU/memory)
- PVC not bound to storage
- Node selector constraints not met
- Image pull failures

### Q: Database connection failures

**A:** Verify database status and connectivity:

```bash
kubectl get pods -l app=postgres -n kubeestatehub
kubectl logs postgres-0 -n kubeestatehub
kubectl exec postgres-0 -n kubeestatehub -- pg_isready -U admin

# Test connectivity from API pod
kubectl exec deployment/listings-api -n kubeestatehub -- nc -zv postgres-service 5432
```

### Q: How to access the application?

**A:** Use port forwarding for development:

```bash
# Frontend
kubectl port-forward svc/frontend-dashboard-service 3000:80 -n kubeestatehub

# API
kubectl port-forward svc/listings-api-service 8080:8080 -n kubeestatehub

# Or use the automated script
./scripts/port-forwarding.sh
```

## Configuration Problems

### Q: How to update application configuration?

**A:** Update ConfigMaps and restart deployments:

```bash
kubectl edit configmap listings-configmap -n kubeestatehub
kubectl rollout restart deployment/listings-api -n kubeestatehub
```

### Q: How to change database credentials?

**A:** Update secrets and restart affected services:

```bash
kubectl patch secret db-secret -n kubeestatehub -p '{"data":{"POSTGRES_PASSWORD":"'$(echo -n "new_password" | base64 -w 0)'"}}'
kubectl rollout restart statefulset/postgres -n kubeestatehub
kubectl rollout restart deployment/listings-api -n kubeestatehub
```

### Q: Environment-specific configurations?

**A:** Use Kustomize overlays or Helm values:

```bash
# Deploy to different environments
kubectl apply -k kustomize/overlays/development
kubectl apply -k kustomize/overlays/production

# Or with Helm
helm install kubeestatehub-dev helm-charts/kubeestatehub -f values-dev.yaml
helm install kubeestatehub-prod helm-charts/kubeestatehub -f values-prod.yaml
```

## Performance and Scaling

### Q: How to scale services for high traffic?

**A:** Use manual scaling or configure autoscaling:

```bash
# Manual scaling
kubectl scale deployment listings-api --replicas=5 -n kubeestatehub
kubectl scale deployment frontend-dashboard --replicas=3 -n kubeestatehub

# Configure HPA
kubectl apply -f manifests/autoscaling/hpa-listings-api.yaml
kubectl get hpa -n kubeestatehub
```

### Q: Database performance optimization?

**A:** Optimize PostgreSQL configuration and resources:

```bash
# Connect to database
kubectl exec -it postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub

# Optimize settings
ALTER SYSTEM SET shared_buffers = '1GB';
ALTER SYSTEM SET effective_cache_size = '3GB';
ALTER SYSTEM SET maintenance_work_mem = '256MB';
SELECT pg_reload_conf();

# Increase database resources
kubectl patch statefulset postgres -n kubeestatehub -p '{"spec":{"template":{"spec":{"containers":[{"name":"postgres","resources":{"limits":{"cpu":"2","memory":"4Gi"}}}]}}}}'
```

### Q: How to monitor application performance?

**A:** Use Grafana dashboards and Prometheus metrics:

```bash
# Access monitoring
./scripts/grafana-dashboard-import.sh --all
kubectl port-forward svc/grafana-service 3001:3000 -n kubeestatehub

# Custom metrics
kubectl port-forward svc/metrics-service 8081:8080 -n kubeestatehub
curl http://localhost:8081/metrics/json
```

## Storage Issues

### Q: How to expand storage volumes?

**A:** Expand PVCs if storage class supports it:

```bash
# Check if expansion is supported
kubectl get storageclass -o yaml | grep allowVolumeExpansion

# Expand PVC
kubectl patch pvc postgres-pvc -n kubeestatehub -p '{"spec":{"resources":{"requests":{"storage":"40Gi"}}}}'

# Monitor expansion
kubectl get pvc postgres-pvc -n kubeestatehub -w
```

### Q: Storage full issues?

**A:** Clean up data and expand storage:

```bash
# Check disk usage
kubectl exec postgres-0 -n kubeestatehub -- df -h /var/lib/postgresql/data

# Database cleanup
kubectl exec postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub -c "VACUUM FULL;"

# Clean up logs
kubectl exec <pod-name> -n kubeestatehub -- find /tmp -type f -atime +7 -delete
```

## Networking Problems

### Q: Services not reachable?

**A:** Check service configuration and endpoints:

```bash
kubectl get services -n kubeestatehub
kubectl get endpoints -n kubeestatehub
kubectl describe service <service-name> -n kubeestatehub

# Test from within cluster
kubectl run debug --image=busybox -n kubeestatehub --rm -it -- sh
# Inside debug pod:
nslookup <service-name>
wget -qO- <service-name>:<port>/health
```

### Q: Ingress not working?

**A:** Verify ingress controller and configuration:

```bash
kubectl get ingress -n kubeestatehub
kubectl describe ingress kubeestatehub-ingress -n kubeestatehub
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller

# Test ingress backend
curl -H "Host: your-domain.com" http://<ingress-ip>/
```

## Security Questions

### Q: How to implement proper security?

**A:** Apply security best practices:

```bash
# Apply security policies
kubectl apply -f manifests/security/
kubectl label namespace kubeestatehub pod-security.kubernetes.io/enforce=restricted

# Check security contexts
kubectl get pods -n kubeestatehub -o jsonpath='{range .items[*]}{.metadata.name}{": "}{.spec.securityContext.runAsNonRoot}{"\n"}{end}'

# Verify RBAC
kubectl auth can-i get pods --as=system:serviceaccount:kubeestatehub:api-service-account
```

### Q: How to rotate secrets?

**A:** Update secrets and restart services:

```bash
# Generate new password
NEW_PASSWORD=$(openssl rand -base64 32)

# Update secret
kubectl patch secret db-secret -n kubeestatehub -p '{"data":{"POSTGRES_PASSWORD":"'$(echo -n $NEW_PASSWORD | base64 -w 0)'"}}'

# Restart services
kubectl rollout restart statefulset/postgres -n kubeestatehub
kubectl rollout restart deployment/listings-api -n kubeestatehub
```

## Backup and Recovery

### Q: How to backup the database?

**A:** Use the backup script or manual backup:

```bash
# Automated backup
./scripts/backup-db.sh

# Manual backup
kubectl exec postgres-0 -n kubeestatehub -- pg_dump -U admin kubeestatehub > backup-$(date +%Y%m%d).sql

# Backup to cloud storage
kubectl exec postgres-0 -n kubeestatehub -- pg_dump -U admin kubeestatehub | gzip | aws s3 cp - s3://backup-bucket/kubeestatehub-$(date +%Y%m%d).sql.gz
```

### Q: How to restore from backup?

**A:** Restore database from backup file:

```bash
# Using backup script
./scripts/backup-db.sh --restore backup-file.sql.gz

# Manual restore
cat backup.sql | kubectl exec -i postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub

# From cloud storage
aws s3 cp s3://backup-bucket/kubeestatehub-20240101.sql.gz - | gunzip | kubectl exec -i postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub
```

## Troubleshooting

### Q: How to debug failing pods?

**A:** Use systematic debugging approach:

```bash
# Check pod status and events
kubectl describe pod <pod-name> -n kubeestatehub
kubectl get events -n kubeestatehub | grep <pod-name>

# Check logs
kubectl logs <pod-name> -n kubeestatehub --previous
kubectl logs <pod-name> -c <container-name> -n kubeestatehub

# Debug with shell access
kubectl exec -it <pod-name> -n kubeestatehub -- /bin/bash
kubectl debug <pod-name> -n kubeestatehub --image=busybox
```

### Q: How to check resource usage?

**A:** Monitor resource consumption:

```bash
# Node and pod resources
kubectl top nodes
kubectl top pods -n kubeestatehub --containers

# Detailed resource information
kubectl describe nodes
kubectl describe pod <pod-name> -n kubeestatehub | grep -A 10 -B 10 -i resources
```

### Q: Application logs showing errors?

**A:** Analyze and resolve application errors:

```bash
# Search for errors
kubectl logs -l app=listings-api -n kubeestatehub | grep -i error

# Real-time log monitoring
kubectl logs -f deployment/listings-api -n kubeestatehub

# Export logs for analysis
kubectl logs deployment/listings-api -n kubeestatehub --since=1h > api-logs.txt
```

## Maintenance Operations

### Q: How to update the application?

**A:** Perform rolling updates:

```bash
# Update image
kubectl set image deployment/listings-api listings-api=kubeestatehub/listings-api:v2.0.0 -n kubeestatehub

# Monitor rollout
kubectl rollout status deployment/listings-api -n kubeestatehub

# Rollback if needed
kubectl rollout undo deployment/listings-api -n kubeestatehub
```

### Q: How to clean up resources?

**A:** Use the teardown script or manual cleanup:

```bash
# Complete cleanup
./scripts/teardown-all.sh

# Keep data but remove applications
./scripts/teardown-all.sh --keep-pvs

# Manual selective cleanup
kubectl delete deployment --all -n kubeestatehub
kubectl delete service --all -n kubeestatehub
```

### Q: Regular maintenance tasks?

**A:** Implement regular maintenance schedule:

```bash
# Daily tasks
./scripts/backup-db.sh
kubectl get pods -n kubeestatehub | grep -v Running

# Weekly tasks
kubectl delete pods --field-selector=status.phase=Succeeded -n kubeestatehub
kubectl get events -n kubeestatehub --sort-by='.lastTimestamp' | head -20

# Monthly tasks
kubectl get pvc -n kubeestatehub  # Check storage usage
kubectl top nodes  # Monitor cluster capacity
```

## Development and CI/CD

### Q: How to set up development environment?

**A:** Use development-specific configurations:

```bash
# Deploy development environment
kubectl apply -k kustomize/overlays/development

# Port forward for development
./scripts/port-forwarding.sh --namespace kubeestatehub-dev

# Local development with port forwarding
kubectl port-forward svc/postgres-service 5432:5432 -n kubeestatehub-dev &
# Run local API against remote database
```

### Q: How to implement CI/CD?

**A:** Use GitHub Actions with ArgoCD:

```bash
# Set up ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Configure ArgoCD applications
kubectl apply -f .github/argocd/applications.yaml

# GitHub Actions will update manifests on successful builds
# ArgoCD will automatically deploy changes
```

This FAQ covers the most common scenarios encountered when deploying and operating KubeEstateHub. For additional support, refer to the specific guides in the docs/ directory.
