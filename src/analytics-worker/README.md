# Location: `/src/analytics-worker/README.md`

# Analytics Worker Service

Celery-based analytics worker for processing real estate market data, generating insights, and calculating property valuations in the KubeEstateHub platform.

## Features

- **Market Trend Analysis** - Calculate city/property type market trends
- **Property Valuation** - Generate comparable market analysis (CMA)
- **Scheduled Analytics** - Automated daily/hourly market analysis
- **Celery Integration** - Distributed task processing
- **Prometheus Metrics** - Comprehensive monitoring
- **Database Integration** - PostgreSQL with connection pooling
- **Redis Caching** - Performance optimization
- **Health Monitoring** - Kubernetes-ready health checks

## Core Functions

### Market Trend Analysis

- Calculates 30-day rolling market statistics
- Price trends (average, median, min/max, standard deviation)
- Days on market analysis
- Price per square foot calculations
- Weekly trend direction analysis

### Property Reports

- Comparable property analysis
- Market position assessment
- Days on market estimation
- Price recommendation insights

### Scheduled Tasks

- Daily market analysis for major Texas cities
- Hourly cache cleanup operations
- Automated trend updates

## Environment Variables

| Variable                   | Description                  | Default                        |
| -------------------------- | ---------------------------- | ------------------------------ |
| `DATABASE_URL`             | PostgreSQL connection string | `postgresql://...`             |
| `REDIS_URL`                | Redis connection for caching | `redis://redis-service:6379/1` |
| `BROKER_URL`               | Celery broker URL            | `redis://redis-service:6379/2` |
| `WORKER_CONCURRENCY`       | Number of worker processes   | `4`                            |
| `LOG_LEVEL`                | Logging level                | `INFO`                         |
| `METRICS_PORT`             | Prometheus metrics port      | `9090`                         |
| `ANALYSIS_BATCH_SIZE`      | Batch size for processing    | `100`                          |
| `MARKET_TREND_WINDOW_DAYS` | Analysis window              | `30`                           |

## Celery Tasks

### Queue Configuration

- `analytics` - Market trend calculations
- `reports` - Property report generation
- `valuations` - Property valuation updates

### Task Types

```python
# Market trend analysis
calculate_market_trends.delay(city="Austin", property_type="residential")

# Property report generation
generate_property_report.delay(listing_id=123)

# Batch property valuation updates
update_property_valuations.delay(city="Houston")
```

## Development

### Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis (required for Celery)
redis-server

# Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost:5432/kubeestatehub"
export REDIS_URL="redis://localhost:6379/1"
export BROKER_URL="redis://localhost:6379/2"

# Run worker
python worker.py
```

### Docker Setup

```bash
# Build image
docker build -t kubeestatehub/analytics-worker .

# Run container
docker run -d \
  -e DATABASE_URL="postgresql://..." \
  -e REDIS_URL="redis://redis:6379/1" \
  kubeestatehub/analytics-worker
```

### Testing Tasks

```python
from celery import Celery

app = Celery('analytics_worker')
app.config_from_object('celeryconfig')

# Test market trends
result = app.send_task('analytics_worker.calculate_market_trends',
                      args=['Austin', 'residential'])

# Check result
print(result.get())
```

## Monitoring & Metrics

### Prometheus Metrics

- `analytics_tasks_processed_total` - Task completion counters
- `analytics_task_duration_seconds` - Task processing time
- `analytics_active_tasks` - Currently running tasks
- `analytics_listings_processed_total` - Listings processed
- `analytics_market_trends_calculated_total` - Trends calculated

### Health Endpoints

- `http://localhost:9090` - Metrics endpoint
- Health checks via worker status monitoring

### Logging

- Structured JSON logging to stdout and `/tmp/worker.log`
- Error tracking with full stack traces
- Performance metrics logging

## Data Models

### Market Trends Output

```json
{
  "city": "Austin",
  "property_type": "residential",
  "period_start": "2024-01-01",
  "period_end": "2024-01-31",
  "total_sales": 1250,
  "avg_price": 485000,
  "median_price": 425000,
  "avg_days_on_market": 35,
  "avg_price_per_sqft": 285,
  "price_trend": "up",
  "weekly_trends": [...],
  "calculated_at": "2024-01-31T10:00:00Z"
}
```

### Property Report Output

```json
{
  "listing_id": 123,
  "property": {...},
  "comparables": [...],
  "analysis": {
    "comparable_count": 8,
    "avg_comparable_price": 475000,
    "price_position": "market_rate",
    "estimated_days_on_market": 42
  }
}
```

## Dependencies

- **celery 5.3.4** - Distributed task queue
- **redis 5.0.1** - Message broker and caching
- **pandas 2.1.3** - Data analysis
- **numpy 1.25.2** - Numerical computing
- **psycopg2-binary** - PostgreSQL adapter
- **prometheus-client** - Metrics export
- **schedule** - Task scheduling

## Kubernetes Integration

- **Non-root execution** with user ID 1001
- **Health checks** for container management
- **Graceful shutdown** handling
- **Resource monitoring** via Prometheus
- **Horizontal scaling** ready
- **ConfigMap/Secret** integration
