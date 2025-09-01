# Location: `/docs/debugging-guide.md`

# KubeEstateHub Debugging Guide

Comprehensive troubleshooting guide for diagnosing and resolving common issues in KubeEstateHub.

## Quick Diagnosis Commands

### System Status Check

```bash
# Overall cluster health
kubectl get nodes
kubectl get pods -n kubeestatehub
kubectl get services -n kubeestatehub
kubectl get pvc -n kubeestatehub

# Quick status script
./scripts/kubectl-aliases.sh && keh-full-status
```

### Resource Usage

```bash
# Check resource consumption
kubectl top nodes
kubectl top pods -n kubeestatehub

# Check resource limits
kubectl describe quota -n kubeestatehub
kubectl get limitrange -n kubeestatehub
```

## Common Issues and Solutions

### 1. Pod Issues

#### Pod Stuck in Pending State

**Symptoms:**

```bash
NAME                     READY   STATUS    RESTARTS   AGE
listings-api-xxx         0/1     Pending   0          5m
```

**Diagnosis:**

```bash
kubectl describe pod <pod-name> -n kubeestatehub
kubectl get events -n kubeestatehub --sort-by='.lastTimestamp'
```

**Common Causes & Solutions:**

- **Insufficient Resources**: Scale down other pods or add cluster capacity
- **PVC Not Bound**: Check storage class and available storage
- **Node Selector Issues**: Verify node labels match pod requirements
- **Image Pull Issues**: Check image repository access and credentials

#### Pod CrashLoopBackOff

**Symptoms:**

```bash
NAME                     READY   STATUS             RESTARTS   AGE
analytics-worker-xxx     0/1     CrashLoopBackOff   5          5m
```

**Diagnosis:**

```bash
kubectl logs <pod-name> -n kubeestatehub --previous
kubectl describe pod <pod-name> -n kubeestatehub
```

**Common Solutions:**

```bash
# Check application logs
kubectl logs <pod-name> -n kubeestatehub

# Verify configuration
kubectl get configmap -n kubeestatehub
kubectl get secret -n kubeestatehub

# Test with debug container
kubectl debug <pod-name> -n kubeestatehub --image=busybox
```

#### Pod ImagePullBackOff

**Symptoms:**

```bash
NAME                     READY   STATUS             RESTARTS   AGE
frontend-dashboard-xxx   0/1     ImagePullBackOff   0          2m
```

**Solutions:**

```bash
# Check image exists and is accessible
docker pull <image-name>

# Verify image secrets
kubectl get secret regcred -n kubeestatehub

# Update image pull policy
kubectl patch deployment <deployment-name> -n kubeestatehub -p '{"spec":{"template":{"spec":{"containers":[{"name":"<container-name>","imagePullPolicy":"Always"}]}}}}'
```

### 2. Service Connectivity Issues

#### Service Unreachable

**Diagnosis:**

```bash
# Check service endpoints
kubectl get endpoints -n kubeestatehub
kubectl describe service <service-name> -n kubeestatehub

# Test from within cluster
kubectl run debug --image=busybox -n kubeestatehub --rm -it -- sh
# Inside debug pod:
nslookup <service-name>
wget -qO- <service-name>:<port>/health
```

**Solutions:**

```bash
# Verify selector labels
kubectl get pods --show-labels -n kubeestatehub
kubectl get service <service-name> -o yaml -n kubeestatehub

# Check port mappings
kubectl describe service <service-name> -n kubeestatehub
```

#### Ingress Not Working

**Diagnosis:**

```bash
kubectl get ingress -n kubeestatehub
kubectl describe ingress kubeestatehub-ingress -n kubeestatehub
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

**Solutions:**

```bash
# Check ingress controller
kubectl get pods -n ingress-nginx

# Verify DNS and routing
curl -H "Host: your-domain.com" http://<ingress-ip>/

# Test backend service directly
kubectl port-forward svc/frontend-dashboard-service 3000:80 -n kubeestatehub
```

### 3. Database Issues

#### PostgreSQL Connection Failures

**Symptoms:**

```bash
# In application logs:
psycopg2.OperationalError: could not connect to server
```

**Diagnosis:**

```bash
# Check PostgreSQL pod status
kubectl get pods -l app=postgres -n kubeestatehub
kubectl logs postgres-0 -n kubeestatehub

# Test database connectivity
kubectl exec postgres-0 -n kubeestatehub -- pg_isready -U admin
```

**Solutions:**

```bash
# Verify database credentials
kubectl get secret db-secret -n kubeestatehub -o yaml

# Check database configuration
kubectl get configmap db-configmap -n kubeestatehub -o yaml

# Access database directly
kubectl exec -it postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub

# Check database processes
kubectl exec postgres-0 -n kubeestatehub -- ps aux
```

#### Database Performance Issues

**Diagnosis:**

```bash
# Check database metrics
kubectl exec postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub -c "SELECT * FROM pg_stat_activity;"

# Monitor queries
kubectl exec postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub -c "SELECT query, state, query_start FROM pg_stat_activity WHERE state != 'idle';"
```

**Solutions:**

```bash
# Analyze slow queries
kubectl exec postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub -c "SELECT query, calls, total_time, mean_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Check database size and vacuum status
kubectl exec postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub -c "SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del, last_vacuum, last_autovacuum FROM pg_stat_user_tables;"
```

### 4. Storage Issues

#### PVC Stuck in Pending

**Diagnosis:**

```bash
kubectl get pvc -n kubeestatehub
kubectl describe pvc <pvc-name> -n kubeestatehub
kubectl get storageclass
```

**Solutions:**

```bash
# Check storage class exists
kubectl get storageclass

# Verify node has available storage
kubectl describe nodes

# Check PV availability
kubectl get pv
```

#### Storage Full

**Diagnosis:**

```bash
# Check disk usage in pods
kubectl exec <pod-name> -n kubeestatehub -- df -h

# Check PVC usage
kubectl exec postgres-0 -n kubeestatehub -- du -sh /var/lib/postgresql/data
```

**Solutions:**

```bash
# Clean up logs and temporary files
kubectl exec <pod-name> -n kubeestatehub -- find /tmp -type f -atime +7 -delete

# Expand PVC (if supported)
kubectl patch pvc postgres-pvc -n kubeestatehub -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'

# Database cleanup
kubectl exec postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub -c "VACUUM FULL;"
```

### 5. Performance Issues

#### High CPU Usage

**Diagnosis:**

```bash
kubectl top pods -n kubeestatehub --containers
kubectl top nodes

# Check CPU throttling
kubectl describe pod <pod-name> -n kubeestatehub | grep -A 5 -B 5 -i throttl
```

**Solutions:**

```bash
# Increase CPU limits
kubectl patch deployment <deployment-name> -n kubeestatehub -p '{"spec":{"template":{"spec":{"containers":[{"name":"<container-name>","resources":{"limits":{"cpu":"1000m"}}}]}}}}'

# Scale horizontally
kubectl scale deployment <deployment-name> -n kubeestatehub --replicas=3

# Enable HPA
kubectl autoscale deployment <deployment-name> -n kubeestatehub --cpu-percent=70 --min=1 --max=5
```

#### Memory Issues

**Diagnosis:**

```bash
# Check memory usage
kubectl top pods -n kubeestatehub --containers

# Check for OOM kills
kubectl get events -n kubeestatehub | grep OOMKilled
dmesg | grep -i "killed process"
```

**Solutions:**

```bash
# Increase memory limits
kubectl patch deployment <deployment-name> -n kubeestatehub -p '{"spec":{"template":{"spec":{"containers":[{"name":"<container-name>","resources":{"limits":{"memory":"512Mi"}}}]}}}}'

# Analyze memory usage in application
kubectl exec <pod-name> -n kubeestatehub -- ps aux --sort=-%mem | head
```

### 6. Network Issues

#### DNS Resolution Problems

**Diagnosis:**

```bash
# Test DNS from pod
kubectl exec <pod-name> -n kubeestatehub -- nslookup kubernetes.default
kubectl exec <pod-name> -n kubeestatehub -- nslookup <service-name>.<namespace>.svc.cluster.local

# Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns
```

**Solutions:**

```bash
# Restart CoreDNS
kubectl delete pods -n kube-system -l k8s-app=kube-dns

# Check DNS policy
kubectl get pod <pod-name> -n kubeestatehub -o yaml | grep dnsPolicy

# Test with custom DNS
kubectl exec <pod-name> -n kubeestatehub -- nslookup google.com 8.8.8.8
```

#### Network Policy Blocking Traffic

**Diagnosis:**

```bash
kubectl get networkpolicies -n kubeestatehub
kubectl describe networkpolicy <policy-name> -n kubeestatehub

# Test connectivity
kubectl exec <source-pod> -n kubeestatehub -- nc -zv <target-service> <port>
```

**Solutions:**

```bash
# Temporarily disable network policy
kubectl delete networkpolicy <policy-name> -n kubeestatehub

# Add allowed traffic rules
kubectl patch networkpolicy <policy-name> -n kubeestatehub --type='merge' -p='{"spec":{"ingress":[{"from":[{"namespaceSelector":{"matchLabels":{"name":"kubeestatehub"}}}]}]}}'
```

## Application-Specific Debugging

### API Service Issues

#### API Returning 500 Errors

**Diagnosis:**

```bash
# Check API logs
kubectl logs -l app=listings-api -n kubeestatehub --tail=100

# Test API endpoints
kubectl port-forward svc/listings-api-service 8080:8080 -n kubeestatehub
curl http://localhost:8080/health
curl http://localhost:8080/api/v1/listings
```

**Solutions:**

```bash
# Check database connection
kubectl exec deployment/listings-api -n kubeestatehub -- python -c "import psycopg2; print('DB connection OK')"

# Verify environment variables
kubectl exec deployment/listings-api -n kubeestatehub -- env | grep DATABASE_URL

# Restart API service
kubectl rollout restart deployment/listings-api -n kubeestatehub
```

#### Slow API Response Times

**Diagnosis:**

```bash
# Check API metrics
kubectl port-forward svc/metrics-service 8081:8080 -n kubeestatehub
curl http://localhost:8081/metrics | grep api_response_time

# Monitor database queries
kubectl exec postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub -c "SELECT query, state, query_start, now() - query_start as runtime FROM pg_stat_activity WHERE state != 'idle' ORDER BY runtime DESC;"
```

### Frontend Issues

#### Frontend Not Loading

**Diagnosis:**

```bash
# Check frontend pod status
kubectl get pods -l app=frontend-dashboard -n kubeestatehub

# Check frontend logs
kubectl logs -l app=frontend-dashboard -n kubeestatehub

# Test frontend service
kubectl port-forward svc/frontend-dashboard-service 3000:80 -n kubeestatehub
curl http://localhost:3000
```

**Solutions:**

```bash
# Check static file serving
kubectl exec deployment/frontend-dashboard -n kubeestatehub -- ls -la /usr/share/nginx/html/

# Verify nginx configuration
kubectl exec deployment/frontend-dashboard -n kubeestatehub -- nginx -t

# Restart frontend
kubectl rollout restart deployment/frontend-dashboard -n kubeestatehub
```

#### JavaScript Errors

**Access browser developer tools or check frontend logs for:**

- CORS errors (check API service configuration)
- Network errors (check service connectivity)
- Authentication errors (check token handling)

### Analytics Worker Issues

#### Worker Jobs Not Processing

**Diagnosis:**

```bash
# Check worker pod status
kubectl get pods -l app=analytics-worker -n kubeestatehub

# Check job queue (if using external queue)
kubectl logs -l app=analytics-worker -n kubeestatehub --tail=50

# Check CronJob status
kubectl get cronjobs -n kubeestatehub
kubectl get jobs -n kubeestatehub
```

## Monitoring and Alerting Issues

### Prometheus Not Scraping Metrics

**Diagnosis:**

```bash
# Check Prometheus targets
kubectl port-forward svc/prometheus-service 9090:9090 -n kubeestatehub
# Visit http://localhost:9090/targets

# Check ServiceMonitor
kubectl get servicemonitor -n kubeestatehub
kubectl describe servicemonitor <servicemonitor-name> -n kubeestatehub
```

### Grafana Dashboard Issues

**Diagnosis:**

```bash
# Check Grafana pod status
kubectl get pods -l app=grafana -n kubeestatehub

# Access Grafana
kubectl port-forward svc/grafana-service 3001:3000 -n kubeestatehub
# Visit http://localhost:3001 (admin/admin)

# Check datasource connection
curl -u admin:admin http://localhost:3001/api/datasources
```

## Emergency Procedures

### Complete System Recovery

```bash
# 1. Scale down all deployments
kubectl scale deployment --all --replicas=0 -n kubeestatehub

# 2. Restart database first
kubectl scale statefulset postgres --replicas=1 -n kubeestatehub
kubectl wait --for=condition=Ready pod/postgres-0 -n kubeestatehub --timeout=300s

# 3. Scale up core services
kubectl scale deployment listings-api --replicas=2 -n kubeestatehub
kubectl scale deployment frontend-dashboard --replicas=2 -n kubeestatehub

# 4. Scale up supporting services
kubectl scale deployment --all --replicas=1 -n kubeestatehub
```

### Data Recovery

```bash
# Database backup
kubectl exec postgres-0 -n kubeestatehub -- pg_dump -U admin kubeestatehub > emergency-backup.sql

# Restore from backup
cat backup.sql | kubectl exec -i postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub
```

### Resource Cleanup

```bash
# Clean up failed pods
kubectl delete pods --field-selector=status.phase=Failed -n kubeestatehub

# Clean up completed jobs
kubectl delete jobs --field-selector=status.conditions[0].type=Complete -n kubeestatehub

# Restart all deployments
kubectl rollout restart deployment --all -n kubeestatehub
```

## Useful Debugging Commands

### Log Analysis

```bash
# Search for errors across all pods
kubectl logs -l app.kubernetes.io/name=kubeestatehub -n kubeestatehub | grep -i error

# Get logs from last hour
kubectl logs <pod-name> -n kubeestatehub --since=1h

# Follow logs from multiple pods
kubectl logs -f -l app=listings-api -n kubeestatehub --max-log-requests=5
```

### Resource Investigation

```bash
# Get detailed resource usage
kubectl describe nodes | grep -A 15 "Allocated resources"

# Check for resource pressure
kubectl get events --field-selector reason=FailedScheduling -n kubeestatehub

# Monitor resource usage over time
watch kubectl top pods -n kubeestatehub
```

### Configuration Verification

```bash
# Validate all manifests
kubectl apply --dry-run=client --validate=true -f manifests/

# Check security contexts
kubectl get pods -n kubeestatehub -o jsonpath='{range .items[*]}{.metadata.name}{": "}{.spec.securityContext}{"\n"}{end}'

# Verify environment variables
kubectl get pods -n kubeestatehub -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{range .spec.containers[*]}  {.name}{": "}{.env[*].name}{"\n"}{end}{end}'
```

This debugging guide provides systematic approaches to identify and resolve common issues in KubeEstateHub. Always start with the quick diagnosis commands to understand the current state before diving into specific troubleshooting procedures.
