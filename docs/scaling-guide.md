# Location: `/docs/scaling-guide.md`

# KubeEstateHub Scaling Guide

Complete guide for scaling KubeEstateHub components both horizontally and vertically to handle increased load and usage.

## Scaling Overview

### Scaling Types

- **Horizontal Scaling**: Increasing number of replicas
- **Vertical Scaling**: Increasing resources per pod
- **Cluster Scaling**: Adding/removing nodes
- **Storage Scaling**: Expanding persistent volumes

### Monitoring Scaling Metrics

```bash
# Resource utilization
kubectl top pods -n kubeestatehub
kubectl top nodes

# HPA status
kubectl get hpa -n kubeestatehub

# Custom metrics
curl http://localhost:8081/metrics/json  # Metrics service
```

## Horizontal Scaling

### Manual Scaling

```bash
# Scale API service
kubectl scale deployment listings-api --replicas=5 -n kubeestatehub

# Scale frontend
kubectl scale deployment frontend-dashboard --replicas=3 -n kubeestatehub

# Scale analytics worker
kubectl scale deployment analytics-worker --replicas=4 -n kubeestatehub

# Verify scaling
kubectl get pods -l app=listings-api -n kubeestatehub
```

### Horizontal Pod Autoscaler (HPA)

#### Basic CPU-based HPA

```yaml
# Apply existing HPA manifest
kubectl apply -f manifests/autoscaling/hpa-listings-api.yaml

# Create custom HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: listings-api-hpa
  namespace: kubeestatehub
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: listings-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### Advanced HPA with Custom Metrics

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: advanced-listings-api-hpa
  namespace: kubeestatehub
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: listings-api
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: api_requests_per_second
        target:
          type: AverageValue
          averageValue: "100"
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
```

### HPA Management Commands

```bash
# Create HPA
kubectl autoscale deployment listings-api --cpu-percent=70 --min=2 --max=10 -n kubeestatehub

# Monitor HPA
kubectl get hpa -w -n kubeestatehub
kubectl describe hpa listings-api-hpa -n kubeestatehub

# Delete HPA
kubectl delete hpa listings-api-hpa -n kubeestatehub
```

## Vertical Scaling

### Vertical Pod Autoscaler (VPA)

#### VPA Configuration

```yaml
# Apply VPA manifest
kubectl apply -f manifests/autoscaling/vpa-listings-api.yaml

# Custom VPA example
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: listings-api-vpa
  namespace: kubeestatehub
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: listings-api
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: listings-api
      minAllowed:
        cpu: 100m
        memory: 128Mi
      maxAllowed:
        cpu: 2
        memory: 2Gi
      controlledResources: ["cpu", "memory"]
```

#### VPA Modes

- **Off**: Only provide recommendations
- **Initial**: Set resources when pods are created
- **Auto**: Update resources automatically (requires pod restart)

### Manual Resource Updates

```bash
# Update CPU limits
kubectl patch deployment listings-api -n kubeestatehub -p '{"spec":{"template":{"spec":{"containers":[{"name":"listings-api","resources":{"limits":{"cpu":"1000m"},"requests":{"cpu":"500m"}}}]}}}}'

# Update memory limits
kubectl patch deployment listings-api -n kubeestatehub -p '{"spec":{"template":{"spec":{"containers":[{"name":"listings-api","resources":{"limits":{"memory":"1Gi"},"requests":{"memory":"512Mi"}}}]}}}}'

# Apply resource changes from file
kubectl apply -f updated-deployment.yaml
```

## Component-Specific Scaling

### API Service Scaling

#### Performance Characteristics

- **CPU**: Moderate CPU usage, scales with request volume
- **Memory**: Moderate memory usage, scales with concurrent connections
- **Network**: High network I/O, database-bound operations

#### Scaling Strategies

```bash
# For increased API load
kubectl scale deployment listings-api --replicas=5 -n kubeestatehub

# Increase resources per pod
kubectl patch deployment listings-api -n kubeestatehub -p '{"spec":{"template":{"spec":{"containers":[{"name":"listings-api","resources":{"limits":{"cpu":"1.5","memory":"1Gi"},"requests":{"cpu":"750m","memory":"512Mi"}}}]}}}}'

# Monitor API performance
kubectl logs -f deployment/listings-api -n kubeestatehub | grep -E "(response_time|request_count)"
```

#### Connection Pool Tuning

```bash
# Update database connection pool in ConfigMap
kubectl patch configmap listings-configmap -n kubeestatehub -p '{"data":{"DB_POOL_SIZE":"20","DB_MAX_OVERFLOW":"30"}}'

# Restart deployment to apply changes
kubectl rollout restart deployment/listings-api -n kubeestatehub
```

### Frontend Scaling

#### Characteristics

- **CPU**: Low CPU usage
- **Memory**: Low memory usage
- **Network**: Serving static content

#### Scaling Approach

```bash
# Scale for high traffic
kubectl scale deployment frontend-dashboard --replicas=6 -n kubeestatehub

# Add CDN caching headers (update ConfigMap)
kubectl patch configmap frontend-configmap -n kubeestatehub -p '{"data":{"CACHE_CONTROL":"public, max-age=3600"}}'
```

### Analytics Worker Scaling

#### Characteristics

- **CPU**: High CPU for data processing
- **Memory**: Variable based on dataset size
- **I/O**: Database and queue intensive

#### Queue-based Scaling

```bash
# Scale based on queue length
kubectl scale deployment analytics-worker --replicas=8 -n kubeestatehub

# Resource-intensive processing
kubectl patch deployment analytics-worker -n kubeestatehub -p '{"spec":{"template":{"spec":{"containers":[{"name":"analytics-worker","resources":{"limits":{"cpu":"2","memory":"2Gi"},"requests":{"cpu":"1","memory":"1Gi"}}}]}}}}'

# Monitor queue metrics
kubectl exec deployment/analytics-worker -n kubeestatehub -- python -c "from worker import check_queue_length; print(check_queue_length())"
```

### Database Scaling

#### PostgreSQL Scaling Options

##### Vertical Scaling (Recommended for single instance)

```bash
# Increase database resources
kubectl patch statefulset postgres -n kubeestatehub -p '{"spec":{"template":{"spec":{"containers":[{"name":"postgres","resources":{"limits":{"cpu":"4","memory":"8Gi"},"requests":{"cpu":"2","memory":"4Gi"}}}]}}}}'

# Expand storage
kubectl patch pvc postgres-pvc -n kubeestatehub -p '{"spec":{"resources":{"requests":{"storage":"100Gi"}}}}'
```

##### Read Replicas (Advanced)

```yaml
# Read replica StatefulSet
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres-read-replica
  namespace: kubeestatehub
spec:
  serviceName: postgres-read-service
  replicas: 2
  selector:
    matchLabels:
      app: postgres
      role: replica
  template:
    metadata:
      labels:
        app: postgres
        role: replica
    spec:
      containers:
        - name: postgres
          image: postgres:13
          env:
            - name: POSTGRES_REPLICA_MODE
              value: "replica"
            - name: POSTGRES_MASTER_SERVICE
              value: "postgres-service"
          resources:
            requests:
              cpu: 1
              memory: 2Gi
            limits:
              cpu: 2
              memory: 4Gi
```

#### Database Performance Tuning

```bash
# Connect to database
kubectl exec -it postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub

# Optimize PostgreSQL settings
ALTER SYSTEM SET shared_buffers = '1GB';
ALTER SYSTEM SET effective_cache_size = '3GB';
ALTER SYSTEM SET maintenance_work_mem = '256MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
SELECT pg_reload_conf();

# Create indexes for better performance
CREATE INDEX CONCURRENTLY idx_listings_city_status ON listings(city, status);
CREATE INDEX CONCURRENTLY idx_listings_price_range ON listings(price) WHERE price > 0;
```

## Cluster Scaling

### Node Scaling

#### Manual Node Management

```bash
# Check node capacity
kubectl describe nodes | grep -A 15 "Allocated resources"

# Get node utilization
kubectl top nodes

# Cordoning and draining nodes
kubectl cordon <node-name>
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
```

#### Cluster Autoscaler

```yaml
# Apply cluster autoscaler
kubectl apply -f manifests/autoscaling/cluster-autoscaler.yaml

# Monitor cluster autoscaler
kubectl logs -f deployment/cluster-autoscaler -n kube-system
kubectl get events | grep cluster-autoscaler
```

### Resource Quotas and Limits

```bash
# Apply resource quotas
kubectl apply -f manifests/autoscaling/resource-quotas.yaml

# Check quota usage
kubectl describe quota -n kubeestatehub

# Monitor resource usage against quotas
kubectl get resourcequota -n kubeestatehub -o yaml
```

## Storage Scaling

### PVC Expansion

```bash
# Check if storage class supports expansion
kubectl get storageclass -o yaml | grep allowVolumeExpansion

# Expand PVC
kubectl patch pvc postgres-pvc -n kubeestatehub -p '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'

# Monitor expansion
kubectl get pvc postgres-pvc -n kubeestatehub -w
```

### Storage Performance Optimization

```bash
# Check I/O performance
kubectl exec postgres-0 -n kubeestatehub -- dd if=/dev/zero of=/var/lib/postgresql/data/test bs=1M count=100 oflag=direct

# Monitor storage metrics
kubectl exec postgres-0 -n kubeestatehub -- iostat -x 1 5
```

## Load Testing

### API Load Testing

```bash
# Install hey load testing tool
curl -L https://github.com/rakyll/hey/releases/download/v0.1.4/hey_linux_amd64 -o hey
chmod +x hey

# Port forward API service
kubectl port-forward svc/listings-api-service 8080:8080 -n kubeestatehub &

# Run load tests
./hey -n 1000 -c 10 http://localhost:8080/api/v1/listings
./hey -n 5000 -c 50 -m POST -H "Content-Type: application/json" -d '{"title":"Test Listing","price":500000}' http://localhost:8080/api/v1/listings
```

### Database Load Testing

```bash
# Use pgbench for database load testing
kubectl exec -it postgres-0 -n kubeestatehub -- pgbench -i -s 10 kubeestatehub
kubectl exec -it postgres-0 -n kubeestatehub -- pgbench -c 10 -j 2 -t 1000 kubeestatehub
```

### Frontend Load Testing

```bash
# Use curl to test frontend
kubectl port-forward svc/frontend-dashboard-service 3000:80 -n kubeestatehub &

# Test static content delivery
for i in {1..100}; do curl -o /dev/null -s -w "%{time_total}\n" http://localhost:3000/; done | awk '{sum+=$1; count++} END{print "Average response time:", sum/count, "seconds"}'
```

## Monitoring Scaling Operations

### Scaling Metrics Dashboard

```bash
# Access Grafana
kubectl port-forward svc/grafana-service 3001:3000 -n kubeestatehub

# Key metrics to monitor:
# - Pod replica count over time
# - Resource utilization (CPU/Memory)
# - Request latency and throughput
# - Queue lengths and processing times
# - Database connections and query performance
```

### Scaling Alerts

```bash
# Example Prometheus alerts for scaling
# High CPU usage
expr: avg(rate(container_cpu_usage_seconds_total{namespace="kubeestatehub"}[5m])) > 0.8

# High memory usage
expr: avg(container_memory_usage_bytes{namespace="kubeestatehub"} / container_spec_memory_limit_bytes) > 0.9

# API response time degradation
expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{namespace="kubeestatehub"}[5m])) > 2.0
```

## Scaling Best Practices

### Resource Planning

1. **Baseline Metrics**: Establish performance baselines under normal load
2. **Growth Projections**: Plan for 2x, 5x, 10x traffic growth
3. **Resource Buffering**: Maintain 20-30% resource headroom
4. **Cost Optimization**: Balance performance with infrastructure costs

### Scaling Strategies

1. **Gradual Scaling**: Scale incrementally rather than large jumps
2. **Monitoring**: Continuously monitor performance during scaling
3. **Testing**: Test scaling scenarios in staging environment
4. **Rollback Plans**: Have procedures to quickly scale down if needed

### Common Scaling Patterns

```bash
# Predictive scaling for known traffic patterns
# Scale up before peak hours
kubectl scale deployment listings-api --replicas=8 -n kubeestatehub

# Reactive scaling based on metrics
# Monitor and scale based on queue length, response time, etc.

# Mixed scaling approach
# Use HPA for automatic scaling within bounds
# Manual scaling for planned events
```

## Troubleshooting Scaling Issues

### HPA Not Scaling

```bash
# Check metrics availability
kubectl top pods -n kubeestatehub
kubectl get --raw /apis/metrics.k8s.io/v1beta1/nodes
kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods

# Check HPA conditions
kubectl describe hpa -n kubeestatehub

# Verify resource requests are set
kubectl get pods -n kubeestatehub -o jsonpath='{range .items[*]}{.metadata.name}{": "}{.spec.containers[*].resources.requests}{"\n"}{end}'
```

### Resource Constraints

```bash
# Check resource quotas
kubectl describe quota -n kubeestatehub

# Check node capacity
kubectl describe nodes | grep -E "(Name:|Allocated resources:)" -A 5

# Identify resource bottlenecks
kubectl get events --sort-by='.lastTimestamp' | grep -i failedscheduling
```

This scaling guide provides comprehensive strategies for handling growth in KubeEstateHub, from basic manual scaling to advanced autoscaling configurations. Regular monitoring and testing ensure optimal performance as the system scales.
