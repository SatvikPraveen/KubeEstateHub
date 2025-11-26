# KubeEstateHub - Advanced Features & Enhancements

This document describes advanced features and optimization techniques for KubeEstateHub.

## 1. Service Mesh Integration (Istio)

### Enable Istio Service Mesh

```bash
# Install Istio
istioctl install --set profile=demo -y

# Enable sidecar injection in kubeestatehub namespace
kubectl label namespace kubeestatehub istio-injection=enabled

# Redeploy applications
kubectl rollout restart deployment -n kubeestatehub
```

### Create Virtual Services and Destination Rules

```yaml
# manifests/networking/listings-api-virtualservice.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: listings-api
  namespace: kubeestatehub
spec:
  hosts:
  - listings-api-service
  http:
  - match:
    - uri:
        prefix: /api/v1
    route:
    - destination:
        host: listings-api-service
        port:
          number: 8080
      weight: 100
    timeout: 10s
    retries:
      attempts: 3
      perTryTimeout: 2s
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: listings-api
  namespace: kubeestatehub
spec:
  host: listings-api-service
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 50
        http2MaxRequests: 100
    loadBalancer:
      simple: LEAST_REQUEST
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 30s
```

## 2. Advanced Caching with Redis

### Cache Layer Implementation

```python
# In listings-api/app.py
class CacheManager:
    def __init__(self, redis_client, ttl=3600):
        self.redis = redis_client
        self.ttl = ttl
    
    def cache_key(self, *args):
        return ":".join(str(arg) for arg in args)
    
    def get(self, key):
        return json.loads(self.redis.get(key) or 'null')
    
    def set(self, key, value, ttl=None):
        self.redis.setex(
            key, 
            ttl or self.ttl, 
            json.dumps(value, default=str)
        )
    
    def delete(self, pattern):
        for key in self.redis.scan_iter(match=pattern):
            self.redis.delete(key)

# Cache warming strategy
@celery_app.task
def warm_cache():
    cache = CacheManager(redis_client)
    cities = ['Austin', 'Houston', 'Dallas', 'San Antonio']
    
    for city in cities:
        key = cache.cache_key('listings', city, 'summary')
        data = get_listings_summary(city)
        cache.set(key, data, ttl=86400)  # 24 hours
```

### Redis Cluster for High Availability

```yaml
# manifests/storage/redis-cluster.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: redis-cluster-config
  namespace: kubeestatehub
data:
  redis-cluster-nodes.conf: |
    port 6379
    cluster-enabled yes
    cluster-config-file nodes.conf
    cluster-node-timeout 5000
    appendonly yes
```

## 3. Database Connection Pooling and Optimization

### PgBouncer Connection Pooling

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: pgbouncer-config
  namespace: kubeestatehub
data:
  pgbouncer.ini: |
    [databases]
    kubeestatehub = host=postgresql-db port=5432 dbname=kubeestatehub
    
    [pgbouncer]
    pool_mode = transaction
    max_client_conn = 1000
    default_pool_size = 25
    min_pool_size = 10
    reserve_pool_size = 5
    reserve_pool_timeout = 3
    max_db_connections = 100
    max_user_connections = 100
    ignore_startup_parameters = extra_float_digits
```

### Query Optimization Example

```python
# Optimize market trends calculation with materialized view
@app.route('/api/v1/market-trends')
def get_market_trends():
    """Use materialized view for faster queries"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Query materialized view instead of computing on the fly
    cursor.execute("""
        REFRESH MATERIALIZED VIEW CONCURRENTLY market_trends_summary;
        SELECT * FROM market_trends_summary 
        WHERE period_end >= CURRENT_DATE - INTERVAL '90 days'
        ORDER BY city, period_end DESC
    """)
    
    trends = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify([dict(row) for row in trends])
```

## 4. GraphQL API Layer

### Add GraphQL Support

```python
# src/listings-api/graphql_schema.py
from graphene import ObjectType, String, Int, Float, List, Schema, Field

class ListingType(ObjectType):
    id = Int()
    title = String()
    price = Float()
    bedrooms = Int()
    bathrooms = Float()
    city = String()
    property_type = String()

class Query(ObjectType):
    listings = List(ListingType, city=String(), min_price=Float(), max_price=Float())
    listing = Field(ListingType, id=Int())
    
    def resolve_listings(self, info, city=None, min_price=None, max_price=None):
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        query = "SELECT * FROM listings WHERE status = 'active'"
        params = []
        
        if city:
            query += " AND city = %s"
            params.append(city)
        if min_price:
            query += " AND price >= %s"
            params.append(min_price)
        if max_price:
            query += " AND price <= %s"
            params.append(max_price)
        
        cursor.execute(query, params)
        return cursor.fetchall()

schema = Schema(query=Query)

# Add GraphQL endpoint to Flask
from flask_graphql import GraphQLView

@app.route('/graphql', methods=['GET', 'POST'])
def graphql():
    return GraphQLView.as_view('graphql', schema=schema)(request)
```

## 5. Real-time Notifications with WebSockets

### WebSocket Support

```python
# src/listings-api/websocket_handler.py
from flask_socketio import SocketIO, emit, join_room, leave_room
import json

socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('subscribe_listings')
def on_subscribe(data):
    city = data.get('city')
    join_room(f"listings_{city}")
    emit('subscribed', {'message': f'Subscribed to listings in {city}'})

@socketio.on('unsubscribe_listings')
def on_unsubscribe(data):
    city = data.get('city')
    leave_room(f"listings_{city}")
    emit('unsubscribed', {'message': f'Unsubscribed from listings in {city}'})

# Broadcast new listings when created
def broadcast_new_listing(listing):
    socketio.emit('new_listing', listing, room=f"listings_{listing['city']}")
```

## 6. Machine Learning - Property Valuation

### ML Model Integration

```python
# src/analytics-worker/ml_valuation.py
import joblib
import numpy as np
from sklearn.preprocessing import StandardScaler

class PropertyValuationModel:
    def __init__(self, model_path):
        self.model = joblib.load(model_path)
        self.scaler = joblib.load(model_path.replace('.pkl', '_scaler.pkl'))
    
    def predict_value(self, property_data):
        """Predict property value using ML model"""
        features = np.array([[
            property_data['bedrooms'],
            property_data['bathrooms'],
            property_data['square_feet'],
            property_data['lot_size'],
            property_data['latitude'],
            property_data['longitude'],
        ]])
        
        scaled_features = self.scaler.transform(features)
        predicted_value = self.model.predict(scaled_features)[0]
        
        return float(predicted_value)

# Use in Celery task
@celery_app.task
def estimate_property_value(listing_id):
    model = PropertyValuationModel('/models/property_valuation_model.pkl')
    
    # Get listing details
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM listings WHERE id = %s", (listing_id,))
    property_data = cursor.fetchone()
    
    # Predict value
    predicted_value = model.predict_value(property_data)
    
    # Store valuation
    cursor.execute("""
        INSERT INTO property_valuations (listing_id, valuation_date, estimated_value, confidence_level)
        VALUES (%s, CURRENT_DATE, %s, 0.85)
    """, (listing_id, predicted_value))
    
    conn.commit()
    cursor.close()
    conn.close()
```

## 7. Distributed Tracing with Jaeger

### Enable Distributed Tracing

```bash
# Install Jaeger operator
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm install jaeger jaegertracing/jaeger -n kubeestatehub
```

### Add Tracing to Applications

```python
# src/listings-api/app.py
from jaeger_client import Config
from flask_opentracing import FlaskTracing

def init_tracer(service_name):
    config = Config(
        config={
            'sampler': {'type': 'const', 'param': 1},
            'logging': True,
        },
        service_name=service_name,
    )
    return config.initialize_tracer()

tracer = init_tracer('listings-api')
tracing = FlaskTracing(tracer, True, app)
```

## 8. Blue-Green Deployments

### Blue-Green Deployment Strategy

```bash
#!/bin/bash
# scripts/blue-green-deploy.sh

NAMESPACE="kubeestatehub"
SERVICE="listings-api-service"
NEW_VERSION=$1

# 1. Deploy new version (green)
kubectl set image deployment/listings-api-green \
    listings-api=kubeestatehub/listings-api:$NEW_VERSION \
    -n $NAMESPACE

# 2. Wait for green deployment to be ready
kubectl wait --for=condition=Available deployment/listings-api-green \
    --timeout=300s -n $NAMESPACE

# 3. Switch traffic from blue to green
kubectl patch service $SERVICE -p '{"spec":{"selector":{"version":"green"}}}' -n $NAMESPACE

# 4. Monitor for issues (wait 5 minutes)
sleep 300

# 5. If all good, make green the new blue
kubectl set env deployment/listings-api-blue \
    VERSION=blue -n $NAMESPACE
```

## 9. Cost Optimization Strategies

### Implement Spot Instances

```yaml
# manifests/autoscaling/spot-instance-nodepool.yaml
apiVersion: v1
kind: Node
metadata:
  labels:
    cloud.google.com/gke-nodepool: spot-pool
    workload-type: analytics
spec:
  taints:
  - key: cloud.google.com/gke-spot
    value: "true"
    effect: NoSchedule
```

### Resource Right-Sizing

```python
# Analyze resource utilization
def recommend_resources(pod_name, namespace):
    metrics = get_pod_metrics(pod_name, namespace)
    cpu_used = metrics['cpu_usage_percent']
    mem_used = metrics['memory_usage_percent']
    
    recommendations = {}
    if cpu_used < 20:
        recommendations['cpu_limit'] = 'can_be_reduced'
    if mem_used < 30:
        recommendations['memory_limit'] = 'can_be_reduced'
    
    return recommendations
```

## 10. Disaster Recovery & Backup

### Automated Backup Strategy

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: db-backup
  namespace: kubeestatehub
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:15.4-alpine
            command:
            - /bin/sh
            - -c
            - |
              pg_dump -h postgresql-db -U kubeestatehub kubeestatehub | \
              gzip > /backup/kubeestatehub-$(date +%Y%m%d-%H%M%S).sql.gz
            volumeMounts:
            - name: backup
              mountPath: /backup
          volumes:
          - name: backup
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
```

## 11. Performance Monitoring Dashboard

Create custom Grafana dashboards tracking:
- Request latency percentiles (p50, p95, p99)
- Database connection pool utilization
- Cache hit rates
- Error rates by endpoint
- Market trend calculation performance

## 12. API Documentation with Swagger/OpenAPI

```python
# src/listings-api/swagger.py
from flasgger import Swagger

swagger = Swagger(app)

@app.route('/api/v1/listings', methods=['GET'])
def get_listings():
    """
    Get all property listings with filters
    ---
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 20
      - name: city
        in: query
        type: string
    responses:
      200:
        description: List of properties
    """
    # Implementation
    pass
```

## Summary

These advanced features enable:
- ✅ Higher availability and reliability (Service Mesh)
- ✅ Better performance (Caching, Connection Pooling)
- ✅ Enhanced analytics (ML models)
- ✅ Better observability (Distributed Tracing)
- ✅ Safer deployments (Blue-Green)
- ✅ Cost optimization (Spot instances)
- ✅ Business continuity (Disaster Recovery)

Start implementing these features incrementally based on your requirements.
