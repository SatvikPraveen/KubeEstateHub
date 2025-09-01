# Location: `/docs/monitoring-guide.md`

# Monitoring and Observability Guide

Comprehensive guide to monitoring KubeEstateHub with Prometheus, Grafana, and custom metrics.

## Monitoring Stack Overview

### Components

- **Prometheus**: Metrics collection and alerting
- **Grafana**: Visualization and dashboards
- **Metrics Service**: Custom business metrics
- **Node Exporter**: System-level metrics
- **AlertManager**: Alert routing and management

### Architecture

```
Applications → Metrics Service → Prometheus → Grafana
     ↓              ↓              ↓
   Logs         Custom KPIs    Alerts
```

## Prometheus Configuration

### Setup and Deployment

```bash
# Deploy Prometheus
kubectl apply -f manifests/monitoring/prometheus-deployment.yaml
kubectl apply -f manifests/monitoring/prometheus-service.yaml

# Verify deployment
kubectl get pods -l app=prometheus -n kubeestatehub
kubectl port-forward svc/prometheus-service 9090:9090 -n kubeestatehub
```

### Service Discovery

```yaml
# Prometheus configuration for service discovery
scrape_configs:
  - job_name: "kubeestatehub-api"
    kubernetes_sd_configs:
      - role: endpoints
    relabel_configs:
      - source_labels: [__meta_kubernetes_service_label_app]
        action: keep
        regex: listings-api
      - source_labels: [__meta_kubernetes_endpoint_port_name]
        action: keep
        regex: metrics

  - job_name: "kubeestatehub-metrics"
    kubernetes_sd_configs:
      - role: endpoints
    relabel_configs:
      - source_labels: [__meta_kubernetes_service_label_app]
        action: keep
        regex: metrics-service
```

### Custom Metrics Collection

```bash
# Access custom metrics
kubectl port-forward svc/metrics-service 8081:8080 -n kubeestatehub
curl http://localhost:8081/metrics

# Key metrics available:
# - kubeestatehub_listings_total
# - kubeestatehub_listings_price_average
# - kubeestatehub_market_trend_score
# - kubeestatehub_api_requests_total
# - kubeestatehub_db_connections_active
```

## Grafana Dashboards

### Setup and Import

```bash
# Deploy Grafana
kubectl apply -f manifests/monitoring/grafana-deployment.yaml
kubectl apply -f manifests/monitoring/grafana-service.yaml

# Import dashboards
./scripts/grafana-dashboard-import.sh --all

# Access Grafana
kubectl port-forward svc/grafana-service 3001:3000 -n kubeestatehub
# Login: admin/admin
```

### Key Dashboards

#### Business Metrics Dashboard

- Total listings by status and type
- Average listing prices by city
- Market trend indicators
- Days on market analysis
- Price per square foot trends

#### System Performance Dashboard

- Pod CPU and memory usage
- API request rates and latency
- Database connection pool status
- Storage usage and I/O metrics
- Network traffic patterns

#### Infrastructure Dashboard

- Node resource utilization
- Kubernetes cluster health
- Pod restart counts
- PVC usage and availability
- Network policy effectiveness

## Alerting Configuration

### Alert Rules

```yaml
# Critical alerts for service availability
groups:
  - name: kubeestatehub.rules
    rules:
      - alert: ServiceDown
        expr: kubeestatehub_service_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "KubeEstateHub service is down"
          description: "{{ $labels.service }} has been down for more than 1 minute"

      - alert: HighAPILatency
        expr: histogram_quantile(0.95, rate(kubeestatehub_api_response_time_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API response times"
          description: "95th percentile latency is {{ $value }}s"

      - alert: DatabaseConnectionsHigh
        expr: kubeestatehub_db_connections_active > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High database connection usage"
          description: "Database has {{ $value }} active connections"
```

### AlertManager Configuration

```yaml
global:
  slack_api_url: "YOUR_SLACK_WEBHOOK_URL"

route:
  group_by: ["alertname"]
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: "web.hook"

receivers:
  - name: "web.hook"
    slack_configs:
      - channel: "#kubeestatehub-alerts"
        title: "KubeEstateHub Alert"
        text: "{{ range .Alerts }}{{ .Annotations.description }}{{ end }}"
```

## Performance Monitoring

### Application Performance Metrics

```bash
# API performance monitoring
curl http://localhost:8081/metrics | grep api_
# - api_requests_total
# - api_response_time_seconds
# - api_errors_total

# Database performance
curl http://localhost:8081/metrics | grep db_
# - db_connections_active
# - db_query_duration_seconds
# - db_connection_pool_size
```

### Resource Usage Monitoring

```bash
# Container metrics
kubectl top pods -n kubeestatehub --containers
kubectl top nodes

# Storage metrics
kubectl get pvc -n kubeestatehub
df -h # within pods for disk usage
```

## Business Metrics Monitoring

### Real Estate KPIs

```bash
# Access business metrics
curl http://localhost:8081/metrics/json

# Key business metrics:
# - Total listings by status
# - Average prices by city and type
# - Market trend score (-1 to 1)
# - Inventory levels (months of supply)
# - Days on market average
```

### Market Analysis Dashboards

- Price trend analysis over time
- Geographic market performance
- Property type distribution
- Seasonal market patterns
- Inventory turnover rates

## Log Management

### Centralized Logging Setup

```yaml
# Fluentd DaemonSet for log collection
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluentd
  namespace: kubeestatehub
spec:
  selector:
    matchLabels:
      name: fluentd
  template:
    metadata:
      labels:
        name: fluentd
    spec:
      containers:
        - name: fluentd
          image: fluent/fluentd-kubernetes-daemonset:v1-debian-elasticsearch
          env:
            - name: FLUENT_ELASTICSEARCH_HOST
              value: "elasticsearch.logging.svc.cluster.local"
            - name: FLUENT_ELASTICSEARCH_PORT
              value: "9200"
          volumeMounts:
            - name: varlog
              mountPath: /var/log
            - name: varlibdockercontainers
              mountPath: /var/lib/docker/containers
              readOnly: true
      volumes:
        - name: varlog
          hostPath:
            path: /var/log
        - name: varlibdockercontainers
          hostPath:
            path: /var/lib/docker/containers
```

### Application Logging

```python
# Structured logging in applications
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            'timestamp': record.created,
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'service': 'listings-api'
        }
        return json.dumps(log_record)

# Configure logging
logging.basicConfig(level=logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger = logging.getLogger()
logger.addHandler(handler)
```

## Health Checks and SLIs

### Service Level Indicators

```yaml
# SLI definitions
SLIs:
  availability:
    description: "Percentage of successful requests"
    query: "rate(kubeestatehub_api_requests_total{status!~'5..'}[5m]) / rate(kubeestatehub_api_requests_total[5m])"
    target: 99.9%

  latency:
    description: "95th percentile response time"
    query: "histogram_quantile(0.95, rate(kubeestatehub_api_response_time_seconds_bucket[5m]))"
    target: < 500ms

  throughput:
    description: "Requests per second"
    query: "rate(kubeestatehub_api_requests_total[5m])"
    target: > 10 rps
```

### Health Check Endpoints

```python
# Health check implementation
@app.route('/health')
def health():
    try:
        # Check database connection
        db.session.execute('SELECT 1')

        # Check dependencies
        redis_client.ping()

        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {
                'database': 'ok',
                'cache': 'ok'
            }
        }, 200
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }, 500
```

## Troubleshooting Monitoring Issues

### Prometheus Not Scraping

```bash
# Check Prometheus targets
kubectl port-forward svc/prometheus-service 9090:9090 -n kubeestatehub
# Visit http://localhost:9090/targets

# Verify ServiceMonitor
kubectl get servicemonitor -n kubeestatehub
kubectl describe servicemonitor kubeestatehub-metrics

# Check metrics endpoint
kubectl exec deployment/listings-api -n kubeestatehub -- curl localhost:8080/metrics
```

### Grafana Dashboard Issues

```bash
# Check Grafana datasource
kubectl logs deployment/grafana -n kubeestatehub

# Test Prometheus connection
kubectl exec deployment/grafana -n kubeestatehub -- wget -qO- http://prometheus-service:9090/api/v1/query?query=up
```

### Missing Metrics

```bash
# Verify metrics service
kubectl get pods -l app=metrics-service -n kubeestatehub
kubectl logs deployment/metrics-service -n kubeestatehub

# Check custom metrics endpoint
curl http://localhost:8081/metrics/json
```

## Monitoring Best Practices

### Metrics Strategy

- Use RED method (Rate, Errors, Duration) for services
- Use USE method (Utilization, Saturation, Errors) for resources
- Define SLIs and SLOs for critical services
- Monitor both technical and business metrics

### Alert Management

- Alert on symptoms, not causes
- Use multiple severity levels
- Implement alert fatigue prevention
- Document runbooks for common alerts

### Dashboard Design

- Focus on user experience metrics
- Use appropriate time ranges
- Group related metrics together
- Include both current and historical views

This monitoring guide provides comprehensive observability for KubeEstateHub, covering both technical infrastructure and business metrics essential for real estate operations.
