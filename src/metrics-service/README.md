# Metrics Service

Custom Prometheus metrics exporter for KubeEstateHub that collects and exposes business and technical metrics from the real estate platform.

## Features

- **Custom Business Metrics** - Real estate specific metrics (market trends, inventory levels)
- **Database Monitoring** - PostgreSQL connection and query performance metrics
- **API Health Monitoring** - Service availability and response time tracking
- **Market Analytics** - Price trends, days on market, inventory calculations
- **Prometheus Export** - Standard Prometheus metrics format
- **Health Endpoints** - Kubernetes-ready health and readiness probes
- **JSON Metrics** - Human-readable metrics endpoint for debugging

## Metrics Exported

### Database Metrics

- `kubeestatehub_db_connections_active` - Active database connections
- `kubeestatehub_db_query_duration_seconds` - Database query duration by type

### Business Metrics

- `kubeestatehub_listings_total` - Total listings by status and property type
- `kubeestatehub_listings_price_average` - Average listing price by city/type
- `kubeestatehub_listings_days_on_market_average` - Average days on market
- `kubeestatehub_market_trend_score` - Market trend indicator (-1 to 1)
- `kubeestatehub_inventory_levels_months` - Months of inventory supply
- `kubeestatehub_price_per_sqft_average` - Average price per square foot

### System Health Metrics

- `kubeestatehub_service_up` - Service availability (1=up, 0=down)
- `kubeestatehub_last_scrape_timestamp` - Last successful metrics collection
- `kubeestatehub_app_info` - Application version and build information

### API Metrics

- `kubeestatehub_api_requests_total` - Total API requests by endpoint/status
- `kubeestatehub_api_response_time_seconds` - API response time distribution

## Environment Variables

| Variable               | Description                           | Default                        |
| ---------------------- | ------------------------------------- | ------------------------------ |
| `DATABASE_URL`         | PostgreSQL connection string          | `postgresql://...`             |
| `REDIS_URL`            | Redis connection string               | `redis://redis-service:6379/0` |
| `METRICS_PORT`         | HTTP server port                      | `8080`                         |
| `SCRAPE_INTERVAL`      | Metrics collection interval (seconds) | `30`                           |
| `LOG_LEVEL`            | Logging level                         | `INFO`                         |
| `LISTINGS_API_URL`     | Listings API base URL                 | `http://listings-api:80`       |
| `ANALYTICS_WORKER_URL` | Analytics worker URL                  | `http://analytics-worker:9090` |

## API Endpoints

### Prometheus Metrics

- `GET /metrics` - Prometheus metrics format
- `GET /metrics/json` - JSON formatted metrics (debugging)

### Health Checks

- `GET /health` - Health check with service status
- `GET /ready` - Kubernetes readiness probe

## Development

### Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost:5432/kubeestatehub"
export REDIS_URL="redis://localhost:6379/0"

# Run metrics service
python metrics_exporter.py
```

### Docker Build

```bash
# Build image
docker build -t kubeestatehub/metrics-service .

# Run container
docker run -p 8080:8080 \
  -e DATABASE_URL="postgresql://..." \
  kubeestatehub/metrics-service
```

### Testing Metrics

```bash
# Get Prometheus metrics
curl http://localhost:8080/metrics

# Get JSON metrics (human readable)
curl http://localhost:8080/metrics/json

# Check health
curl http://localhost:8080/health
```

## Metric Collection Process

### Collection Cycle (every 30 seconds)

1. **Database Metrics** - Query PostgreSQL for business and system metrics
2. **API Health Checks** - Test service availability and response times
3. **Redis Metrics** - Check Redis connection and basic info
4. **Business Calculations** - Calculate market trends and inventory levels
5. **Metric Export** - Update Prometheus metrics registry
6. **Error Handling** - Log failures and maintain service availability

### Database Queries

The metrics service executes the following SQL queries to collect business metrics:

```sql
-- Total listings by status
SELECT status, property_type, COUNT(*) FROM listings GROUP BY status, property_type;

-- Average prices by city
SELECT city, property_type, AVG(price) FROM listings WHERE status = 'active' GROUP BY city, property_type;

-- Days on market calculation
SELECT AVG(EXTRACT(days FROM (CURRENT_DATE - listing_date))) FROM listings WHERE status = 'active';

-- Price per square foot
SELECT AVG(price / NULLIF(square_feet, 0)) FROM listings WHERE square_feet > 0 AND status = 'active';
```

### Market Trend Calculation

The market trend score is calculated using a 30-day moving average:

```python
def calculate_market_trend():
    # Get price data for last 60 days
    current_avg = get_avg_price_last_30_days()
    previous_avg = get_avg_price_30_60_days_ago()

    # Calculate percentage change and normalize to -1 to 1 scale
    if previous_avg > 0:
        change_pct = (current_avg - previous_avg) / previous_avg
        # Cap at +/-20% for normalization
        trend_score = max(-1, min(1, change_pct / 0.2))
    else:
        trend_score = 0

    return trend_score
```

### Inventory Levels

Months of inventory supply is calculated based on current listings and average sales rate:

```python
def calculate_inventory_months():
    active_listings = get_active_listings_count()
    avg_monthly_sales = get_avg_monthly_sales_last_6_months()

    if avg_monthly_sales > 0:
        months_supply = active_listings / avg_monthly_sales
    else:
        months_supply = 0

    return months_supply
```

## Monitoring and Alerting

### Recommended Prometheus Alerts

```yaml
# High inventory levels
- alert: HighInventoryLevels
  expr: kubeestatehub_inventory_levels_months > 6
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High inventory levels detected"
    description: "Inventory levels are {{ $value }} months, indicating oversupply"

# Service down
- alert: MetricsServiceDown
  expr: kubeestatehub_service_up == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Metrics service is down"
    description: "KubeEstateHub metrics service is not responding"

# Database connection issues
- alert: DatabaseConnectionIssues
  expr: kubeestatehub_db_connections_active < 1
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "No active database connections"
    description: "Metrics service cannot connect to the database"
```

### Grafana Dashboard

Import the provided Grafana dashboard (`grafana-dashboard.json`) for visualization:

- **Business Metrics Panel** - Key real estate indicators
- **API Performance Panel** - Response times and error rates
- **Database Health Panel** - Connection and query performance
- **Market Trends Panel** - Price trends and inventory levels

## Troubleshooting

### Common Issues

**Metrics service not starting:**

- Check database connection string
- Verify required environment variables are set
- Review logs for connection errors

**Missing business metrics:**

- Ensure database contains listing data
- Check SQL query permissions
- Verify table schema matches expected format

**High memory usage:**

- Reduce `SCRAPE_INTERVAL` if set too low
- Monitor for database connection leaks
- Check for large result sets in business queries

**API health checks failing:**

- Verify service URLs in environment variables
- Check network connectivity between services
- Review firewall and security group settings

### Logging

The service uses structured logging with configurable levels:

```python
# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=DEBUG python metrics_exporter.py
```

### Performance Considerations

- **Database Connection Pooling** - Uses connection pooling to minimize overhead
- **Caching** - Business metrics are cached for 30 seconds to reduce database load
- **Async Operations** - API health checks run asynchronously to prevent blocking
- **Resource Limits** - Configure appropriate CPU/memory limits in Kubernetes

## Security

### Database Access

- Use read-only database user for metrics collection
- Limit database access to required tables only
- Use connection pooling with maximum connection limits

### API Security

- Internal service communication only (no external exposure)
- Use Kubernetes network policies to restrict access
- Implement proper RBAC for service account

## Deployment

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metrics-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: metrics-service
  template:
    metadata:
      labels:
        app: metrics-service
    spec:
      containers:
        - name: metrics-service
          image: kubeestatehub/metrics-service:latest
          ports:
            - containerPort: 8080
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: database-secret
                  key: url
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
```

### Service Monitor (Prometheus Operator)

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: kubeestatehub-metrics
spec:
  selector:
    matchLabels:
      app: metrics-service
  endpoints:
    - port: http-metrics
      interval: 30s
      path: /metrics
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new metrics
4. Update documentation
5. Submit a pull request

### Adding New Metrics

To add a new business metric:

1. Define the metric in `metrics_collector.py`
2. Add the collection logic in `collect_business_metrics()`
3. Update this README with metric description
4. Add appropriate unit tests

### Testing

```bash
# Run unit tests
python -m pytest tests/

# Run integration tests (requires database)
python -m pytest tests/integration/

# Load testing
python tests/load_test.py
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
