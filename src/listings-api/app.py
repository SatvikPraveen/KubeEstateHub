# Location: `/src/listings-api/app.py`

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import psycopg2
import psycopg2.extras
import redis
import logging
import json
from datetime import datetime
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time
import traceback

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config.update(
    DATABASE_URL=os.getenv('DATABASE_URL', 'postgresql://kubeestatehub:password@postgresql-db:5432/kubeestatehub'),
    REDIS_URL=os.getenv('REDIS_URL', 'redis://redis-service:6379/0'),
    DEBUG=os.getenv('DEBUG', 'false').lower() == 'true',
    LOG_LEVEL=os.getenv('LOG_LEVEL', 'info').upper(),
    MAX_PAGE_SIZE=int(os.getenv('MAX_PAGE_SIZE', '100')),
    DEFAULT_PAGE_SIZE=int(os.getenv('DEFAULT_PAGE_SIZE', '20'))
)

# Setup logging
logging.basicConfig(
    level=getattr(logging, app.config['LOG_LEVEL']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiting
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"]
)

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status_code'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')

# Redis connection
try:
    redis_client = redis.from_url(app.config['REDIS_URL'])
    redis_client.ping()
    logger.info("Connected to Redis successfully")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(app.config['DATABASE_URL'])
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    # Record metrics
    duration = time.time() - g.start_time
    REQUEST_DURATION.observe(duration)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.endpoint or 'unknown',
        status_code=response.status_code
    ).inc()
    
    # Add headers
    response.headers['X-Response-Time'] = f'{duration:.3f}s'
    return response

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.close()
        conn.close()
        
        # Check Redis connection
        redis_status = 'connected' if redis_client and redis_client.ping() else 'disconnected'
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'database': 'connected',
            'redis': redis_status
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route('/ready', methods=['GET'])
def readiness_check():
    """Readiness check endpoint"""
    return jsonify({'status': 'ready', 'timestamp': datetime.utcnow().isoformat()}), 200

@app.route('/startup', methods=['GET'])
def startup_check():
    """Startup check endpoint"""
    return jsonify({'status': 'started', 'timestamp': datetime.utcnow().isoformat()}), 200

@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/api/v1/listings', methods=['GET'])
@limiter.limit("100 per minute")
def get_listings():
    """Get property listings with pagination and filtering"""
    try:
        # Parse query parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', app.config['DEFAULT_PAGE_SIZE'])), app.config['MAX_PAGE_SIZE'])
        
        # Filters
        property_type = request.args.get('property_type')
        min_price = request.args.get('min_price', type=int)
        max_price = request.args.get('max_price', type=int)
        city = request.args.get('city')
        status = request.args.get('status', 'active')
        
        # Build cache key
        cache_key = f"listings:{page}:{per_page}:{property_type}:{min_price}:{max_price}:{city}:{status}"
        
        # Try to get from cache
        if redis_client:
            try:
                cached_result = redis_client.get(cache_key)
                if cached_result:
                    logger.info(f"Cache hit for key: {cache_key}")
                    return jsonify(json.loads(cached_result)), 200
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
        
        # Database query
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build WHERE clause
        where_conditions = ["status = %s"]
        params = [status]
        
        if property_type:
            where_conditions.append("property_type = %s")
            params.append(property_type)
        
        if min_price:
            where_conditions.append("price >= %s")
            params.append(min_price)
            
        if max_price:
            where_conditions.append("price <= %s")
            params.append(max_price)
            
        if city:
            where_conditions.append("LOWER(city) = LOWER(%s)")
            params.append(city)
        
        where_clause = " AND ".join(where_conditions)
        
        # Count query
        count_query = f"SELECT COUNT(*) FROM listings WHERE {where_clause}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()['count']
        
        # Main query with pagination
        offset = (page - 1) * per_page
        query = f"""
            SELECT id, mls_number, title, description, property_type, price, 
                   bedrooms, bathrooms, square_feet, lot_size, address, 
                   city, state, zip_code, latitude, longitude, listing_date,
                   status, agent_name, agent_email, image_url, thumbnail_url,
                   created_at, updated_at
            FROM listings 
            WHERE {where_clause}
            ORDER BY listing_date DESC, created_at DESC
            LIMIT %s OFFSET %s
        """
        
        cursor.execute(query, params + [per_page, offset])
        listings = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Build response
        response_data = {
            'listings': [dict(listing) for listing in listings],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'pages': (total_count + per_page - 1) // per_page
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Cache the result
        if redis_client:
            try:
                redis_client.setex(cache_key, 300, json.dumps(response_data, default=str))
            except Exception as e:
                logger.warning(f"Cache write error: {e}")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error getting listings: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/listings/<int:listing_id>', methods=['GET'])
@limiter.limit("200 per minute")
def get_listing(listing_id):
    """Get a specific listing by ID"""
    try:
        # Check cache first
        cache_key = f"listing:{listing_id}"
        if redis_client:
            try:
                cached_result = redis_client.get(cache_key)
                if cached_result:
                    return jsonify(json.loads(cached_result)), 200
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        query = """
            SELECT * FROM listings WHERE id = %s AND status != 'deleted'
        """
        cursor.execute(query, (listing_id,))
        listing = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not listing:
            return jsonify({'error': 'Listing not found'}), 404
        
        response_data = {
            'listing': dict(listing),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Cache the result
        if redis_client:
            try:
                redis_client.setex(cache_key, 600, json.dumps(response_data, default=str))
            except Exception as e:
                logger.warning(f"Cache write error: {e}")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error getting listing {listing_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/listings', methods=['POST'])
@limiter.limit("10 per minute")
def create_listing():
    """Create a new listing"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Validate required fields
        required_fields = ['mls_number', 'title', 'property_type', 'price', 'address', 'city', 'state', 'zip_code']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert query
        insert_query = """
            INSERT INTO listings (mls_number, title, description, property_type, price, 
                                bedrooms, bathrooms, square_feet, lot_size, address, 
                                city, state, zip_code, latitude, longitude, listing_date,
                                agent_name, agent_email, agent_phone, image_url, thumbnail_url)
            VALUES (%(mls_number)s, %(title)s, %(description)s, %(property_type)s, %(price)s,
                   %(bedrooms)s, %(bathrooms)s, %(square_feet)s, %(lot_size)s, %(address)s,
                   %(city)s, %(state)s, %(zip_code)s, %(latitude)s, %(longitude)s, 
                   COALESCE(%(listing_date)s, CURRENT_DATE),
                   %(agent_name)s, %(agent_email)s, %(agent_phone)s, %(image_url)s, %(thumbnail_url)s)
            RETURNING id
        """
        
        cursor.execute(insert_query, data)
        listing_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Clear relevant cache entries
        if redis_client:
            try:
                # Clear listings cache
                for key in redis_client.scan_iter(match="listings:*"):
                    redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Cache clear error: {e}")
        
        return jsonify({
            'id': listing_id,
            'message': 'Listing created successfully',
            'timestamp': datetime.utcnow().isoformat()
        }), 201
        
    except psycopg2.IntegrityError as e:
        logger.error(f"Database integrity error: {e}")
        return jsonify({'error': 'Duplicate MLS number or invalid data'}), 400
    except Exception as e:
        logger.error(f"Error creating listing: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded', 'retry_after': e.retry_after}), 429

@app.errorhandler(404)
def not_found_handler(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error_handler(e):
    logger.error(f"Internal server error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])