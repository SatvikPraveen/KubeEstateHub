# Location: `/src/listings-api/README.md`

# Listings API Service

Flask-based REST API service for managing real estate property listings in the KubeEstateHub platform.

## Features

- **RESTful API** for property listings management
- **PostgreSQL integration** with connection pooling
- **Redis caching** for improved performance
- **Prometheus metrics** export
- **Rate limiting** and security controls
- **Kubernetes-ready** health checks
- **Comprehensive logging** with structured output

## API Endpoints

### Health & Monitoring

- `GET /health` - Application health check
- `GET /ready` - Kubernetes readiness probe
- `GET /startup` - Kubernetes startup probe
- `GET /metrics` - Prometheus metrics

### Listings API

- `GET /api/v1/listings` - List properties with pagination & filtering
- `GET /api/v1/listings/{id}` - Get specific property
- `POST /api/v1/listings` - Create new property listing

### Query Parameters

- `page` - Page number (default: 1)
- `per_page` - Items per page (default: 20, max: 100)
- `property_type` - Filter by property type
- `min_price` - Minimum price filter
- `max_price` - Maximum price filter
- `city` - Filter by city
- `status` - Filter by status (default: active)

## Environment Variables

| Variable        | Description                  | Default                        |
| --------------- | ---------------------------- | ------------------------------ |
| `DATABASE_URL`  | PostgreSQL connection string | `postgresql://...`             |
| `REDIS_URL`     | Redis connection string      | `redis://redis-service:6379/0` |
| `PORT`          | Server port                  | `8080`                         |
| `DEBUG`         | Enable debug mode            | `false`                        |
| `LOG_LEVEL`     | Logging level                | `info`                         |
| `MAX_PAGE_SIZE` | Maximum items per page       | `100`                          |

## Development

### Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost:5432/kubeestatehub"
export REDIS_URL="redis://localhost:6379/0"

# Run application
python app.py
```

### Docker Build

```bash
# Build image
docker build -t kubeestatehub/listings-api .

# Run container
docker run -p 8080:8080 \
  -e DATABASE_URL="postgresql://..." \
  kubeestatehub/listings-api
```

### Testing

```bash
# Health check
curl http://localhost:8080/health

# List properties
curl http://localhost:8080/api/v1/listings

# Get specific property
curl http://localhost:8080/api/v1/listings/1

# Create property
curl -X POST http://localhost:8080/api/v1/listings \
  -H "Content-Type: application/json" \
  -d '{"mls_number":"ABC123","title":"Beautiful Home",...}'
```

## Dependencies

- **Flask 3.0.0** - Web framework
- **psycopg2-binary** - PostgreSQL adapter
- **redis** - Redis client
- **prometheus-client** - Metrics export
- **gunicorn** - WSGI server
- **Flask-CORS** - Cross-origin requests
- **Flask-Limiter** - Rate limiting

## Security Features

- Non-root container execution
- Read-only filesystem
- Rate limiting (1000 req/hour default)
- Input validation and sanitization
- SQL injection protection via parameterized queries
- CORS configuration

## Performance

- **Redis caching** for frequently accessed data
- **Connection pooling** for database efficiency
- **Gunicorn** multi-worker deployment
- **Prometheus metrics** for monitoring
- **Structured logging** for observability

## Kubernetes Integration

- **Health checks** for liveness/readiness/startup probes
- **Graceful shutdown** handling
- **Resource limits** and requests
- **Security contexts** with non-root user
- **ConfigMap/Secret** integration for configuration
