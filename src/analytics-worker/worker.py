# Location: `/src/analytics-worker/worker.py`

import os
import sys
import logging
import time
import signal
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any
import psycopg2
import psycopg2.extras
import redis
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, start_http_server
import numpy as np
import pandas as pd
from celery import Celery
from threading import Thread
import schedule

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://kubeestatehub:password@postgresql-db:5432/kubeestatehub')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis-service:6379/1')
BROKER_URL = os.getenv('BROKER_URL', 'redis://redis-service:6379/2')
WORKER_CONCURRENCY = int(os.getenv('WORKER_CONCURRENCY', '4'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
METRICS_PORT = int(os.getenv('METRICS_PORT', '9090'))
BATCH_SIZE = int(os.getenv('ANALYSIS_BATCH_SIZE', '100'))
MARKET_TREND_WINDOW_DAYS = int(os.getenv('MARKET_TREND_WINDOW_DAYS', '30'))

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/worker.log')
    ]
)
logger = logging.getLogger(__name__)

# Celery app configuration
celery_app = Celery('analytics_worker')
celery_app.conf.update(
    broker_url=BROKER_URL,
    result_backend=REDIS_URL,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'analytics_worker.analyze_market_trends': {'queue': 'analytics'},
        'analytics_worker.generate_property_report': {'queue': 'reports'},
        'analytics_worker.update_property_valuations': {'queue': 'valuations'}
    }
)

# Prometheus metrics
TASKS_PROCESSED = Counter('analytics_tasks_processed_total', 'Total processed tasks', ['task_type', 'status'])
TASK_DURATION = Histogram('analytics_task_duration_seconds', 'Task processing duration', ['task_type'])
ACTIVE_TASKS = Gauge('analytics_active_tasks', 'Currently active tasks')
DB_CONNECTIONS = Gauge('analytics_db_connections', 'Active database connections')
LISTINGS_PROCESSED = Counter('analytics_listings_processed_total', 'Total listings processed')
MARKET_TRENDS_CALCULATED = Counter('analytics_market_trends_calculated_total', 'Total market trends calculated')

# Database connection pool
def get_db_connection():
    """Get database connection with retry logic"""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = False
            return conn
        except Exception as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise

# Redis connection
redis_client = redis.from_url(REDIS_URL)

class AnalyticsWorker:
    """Main analytics worker class"""
    
    def __init__(self):
        self.running = True
        self.start_time = time.time()
        
    def start_metrics_server(self):
        """Start Prometheus metrics server"""
        try:
            start_http_server(METRICS_PORT)
            logger.info(f"Metrics server started on port {METRICS_PORT}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")

    def health_check(self) -> Dict[str, Any]:
        """Health check for Kubernetes probes"""
        try:
            # Check database connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            cursor.close()
            conn.close()
            
            # Check Redis connection
            redis_client.ping()
            
            return {
                'status': 'healthy',
                'uptime_seconds': time.time() - self.start_time,
                'active_tasks': ACTIVE_TASKS._value._value,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    def calculate_market_trends(self, city: str, property_type: str = None) -> Dict[str, Any]:
        """Calculate market trends for a specific city and property type"""
        with TASK_DURATION.labels(task_type='market_trends').time():
            ACTIVE_TASKS.inc()
            try:
                conn = get_db_connection()
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # Date range for analysis
                end_date = datetime.now()
                start_date = end_date - timedelta(days=MARKET_TREND_WINDOW_DAYS)
                
                # Build query
                where_conditions = ["city = %s", "listing_date BETWEEN %s AND %s", "status = 'sold'"]
                params = [city, start_date.date(), end_date.date()]
                
                if property_type:
                    where_conditions.append("property_type = %s")
                    params.append(property_type)
                
                where_clause = " AND ".join(where_conditions)
                
                # Calculate metrics
                query = f"""
                    SELECT 
                        COUNT(*) as total_sales,
                        AVG(price) as avg_price,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) as median_price,
                        AVG(EXTRACT(EPOCH FROM (updated_at - listing_date))/86400) as avg_days_on_market,
                        AVG(price::float / NULLIF(square_feet, 0)) as avg_price_per_sqft,
                        MIN(price) as min_price,
                        MAX(price) as max_price,
                        STDDEV(price) as price_stddev
                    FROM listings 
                    WHERE {where_clause}
                """
                
                cursor.execute(query, params)
                result = cursor.fetchone()
                
                # Weekly trend analysis
                weekly_query = f"""
                    SELECT 
                        DATE_TRUNC('week', listing_date) as week,
                        COUNT(*) as weekly_sales,
                        AVG(price) as weekly_avg_price
                    FROM listings 
                    WHERE {where_clause}
                    GROUP BY DATE_TRUNC('week', listing_date)
                    ORDER BY week
                """
                
                cursor.execute(weekly_query, params)
                weekly_trends = cursor.fetchall()
                
                cursor.close()
                conn.close()
                
                # Calculate trend direction
                if len(weekly_trends) >= 2:
                    recent_avg = sum(w['weekly_avg_price'] or 0 for w in weekly_trends[-2:]) / 2
                    older_avg = sum(w['weekly_avg_price'] or 0 for w in weekly_trends[:2]) / 2 if len(weekly_trends) >= 4 else recent_avg
                    price_trend = 'up' if recent_avg > older_avg * 1.05 else 'down' if recent_avg < older_avg * 0.95 else 'stable'
                else:
                    price_trend = 'insufficient_data'
                
                trend_data = {
                    'city': city,
                    'property_type': property_type or 'all',
                    'period_start': start_date.date().isoformat(),
                    'period_end': end_date.date().isoformat(),
                    'total_sales': result['total_sales'] or 0,
                    'avg_price': float(result['avg_price'] or 0),
                    'median_price': float(result['median_price'] or 0),
                    'avg_days_on_market': float(result['avg_days_on_market'] or 0),
                    'avg_price_per_sqft': float(result['avg_price_per_sqft'] or 0),
                    'min_price': float(result['min_price'] or 0),
                    'max_price': float(result['max_price'] or 0),
                    'price_stddev': float(result['price_stddev'] or 0),
                    'price_trend': price_trend,
                    'weekly_trends': [dict(w) for w in weekly_trends],
                    'calculated_at': datetime.utcnow().isoformat()
                }
                
                # Store in database
                self.store_market_trends(trend_data)
                
                # Cache results
                cache_key = f"market_trends:{city}:{property_type or 'all'}"
                redis_client.setex(cache_key, 3600, json.dumps(trend_data, default=str))
                
                MARKET_TRENDS_CALCULATED.inc()
                TASKS_PROCESSED.labels(task_type='market_trends', status='success').inc()
                
                logger.info(f"Market trends calculated for {city} ({property_type or 'all types'})")
                return trend_data
                
            except Exception as e:
                logger.error(f"Market trends calculation failed: {e}")
                logger.error(traceback.format_exc())
                TASKS_PROCESSED.labels(task_type='market_trends', status='error').inc()
                raise
            finally:
                ACTIVE_TASKS.dec()

    def store_market_trends(self, trend_data: Dict[str, Any]):
        """Store market trend data in database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Upsert market trends
            query = """
                INSERT INTO market_trends (
                    city, state, property_type, period_start, period_end,
                    avg_price, median_price, total_listings, total_sales,
                    days_on_market_avg, price_per_sqft_avg, updated_at
                ) VALUES (
                    %(city)s, 'TX', %(property_type)s, %(period_start)s, %(period_end)s,
                    %(avg_price)s, %(median_price)s, %(total_sales)s, %(total_sales)s,
                    %(avg_days_on_market)s, %(avg_price_per_sqft)s, CURRENT_TIMESTAMP
                )
                ON CONFLICT (city, state, property_type, period_start, period_end)
                DO UPDATE SET
                    avg_price = EXCLUDED.avg_price,
                    median_price = EXCLUDED.median_price,
                    total_sales = EXCLUDED.total_sales,
                    days_on_market_avg = EXCLUDED.days_on_market_avg,
                    price_per_sqft_avg = EXCLUDED.price_per_sqft_avg,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            cursor.execute(query, trend_data)
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to store market trends: {e}")
            raise

    def generate_property_report(self, listing_id: int) -> Dict[str, Any]:
        """Generate comprehensive report for a property"""
        with TASK_DURATION.labels(task_type='property_report').time():
            ACTIVE_TASKS.inc()
            try:
                conn = get_db_connection()
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # Get property details
                cursor.execute("SELECT * FROM listings WHERE id = %s", (listing_id,))
                property_data = cursor.fetchone()
                
                if not property_data:
                    raise ValueError(f"Property {listing_id} not found")
                
                # Get comparable properties
                comp_query = """
                    SELECT * FROM listings 
                    WHERE city = %s 
                    AND property_type = %s 
                    AND price BETWEEN %s AND %s
                    AND square_feet BETWEEN %s AND %s
                    AND id != %s
                    AND status = 'sold'
                    ORDER BY ABS(price - %s) ASC
                    LIMIT 10
                """
                
                price_range = property_data['price'] * 0.2  # 20% range
                sqft_range = (property_data['square_feet'] or 0) * 0.2
                
                cursor.execute(comp_query, (
                    property_data['city'],
                    property_data['property_type'],
                    property_data['price'] - price_range,
                    property_data['price'] + price_range,
                    (property_data['square_feet'] or 0) - sqft_range,
                    (property_data['square_feet'] or 0) + sqft_range,
                    listing_id,
                    property_data['price']
                ))
                
                comparables = cursor.fetchall()
                
                cursor.close()
                conn.close()
                
                # Calculate property insights
                if comparables:
                    comp_prices = [c['price'] for c in comparables]
                    avg_comp_price = sum(comp_prices) / len(comp_prices)
                    price_position = 'above_market' if property_data['price'] > avg_comp_price * 1.1 else 'below_market' if property_data['price'] < avg_comp_price * 0.9 else 'market_rate'
                else:
                    avg_comp_price = None
                    price_position = 'insufficient_data'
                
                report = {
                    'listing_id': listing_id,
                    'property': dict(property_data),
                    'comparables': [dict(c) for c in comparables],
                    'analysis': {
                        'comparable_count': len(comparables),
                        'avg_comparable_price': avg_comp_price,
                        'price_position': price_position,
                        'price_per_sqft': property_data['price'] / (property_data['square_feet'] or 1),
                        'estimated_days_on_market': self.estimate_days_on_market(property_data),
                    },
                    'generated_at': datetime.utcnow().isoformat()
                }
                
                LISTINGS_PROCESSED.inc()
                TASKS_PROCESSED.labels(task_type='property_report', status='success').inc()
                
                return report
                
            except Exception as e:
                logger.error(f"Property report generation failed: {e}")
                TASKS_PROCESSED.labels(task_type='property_report', status='error').inc()
                raise
            finally:
                ACTIVE_TASKS.dec()

    def estimate_days_on_market(self, property_data: Dict) -> int:
        """Estimate days on market based on similar properties"""
        try:
            # Simple estimation based on property type and price range
            base_days = {
                'residential': 45,
                'commercial': 90,
                'industrial': 120,
                'land': 180
            }.get(property_data['property_type'], 60)
            
            # Adjust based on price (higher price = longer on market)
            if property_data['price'] > 1000000:
                base_days *= 1.5
            elif property_data['price'] > 500000:
                base_days *= 1.2
            
            return int(base_days)
        except:
            return 60  # Default estimate

    def run_scheduled_tasks(self):
        """Run scheduled background tasks"""
        def job_wrapper(func, *args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Scheduled job failed: {e}")
        
        # Schedule market trend analysis for major cities
        schedule.every().day.at("02:00").do(job_wrapper, self.analyze_all_markets)
        schedule.every().hour.do(job_wrapper, self.cleanup_old_cache)
        
        while self.running:
            schedule.run_pending()
            time.sleep(60)

    def analyze_all_markets(self):
        """Analyze market trends for all major cities"""
        cities = ['Austin', 'Houston', 'Dallas', 'San Antonio', 'Fort Worth']
        property_types = ['residential', 'commercial']
        
        for city in cities:
            for prop_type in property_types:
                try:
                    self.calculate_market_trends(city, prop_type)
                except Exception as e:
                    logger.error(f"Failed to analyze {city} {prop_type}: {e}")

    def cleanup_old_cache(self):
        """Clean up old cache entries"""
        try:
            # Remove expired cache entries
            for key in redis_client.scan_iter(match="market_trends:*"):
                ttl = redis_client.ttl(key)
                if ttl == -1:  # No expiration set
                    redis_client.expire(key, 3600)
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

def main():
    """Main worker entry point"""
    worker = AnalyticsWorker()
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, worker.signal_handler)
    signal.signal(signal.SIGINT, worker.signal_handler)
    
    # Start metrics server
    worker.start_metrics_server()
    
    # Start scheduled tasks in background thread
    scheduler_thread = Thread(target=worker.run_scheduled_tasks, daemon=True)
    scheduler_thread.start()
    
    logger.info("Analytics worker started")
    
    try:
        # Run Celery worker
        celery_app.worker_main([
            'worker',
            '--loglevel=info',
            '--concurrency=%d' % WORKER_CONCURRENCY,
            '--queues=analytics,reports,valuations'
        ])
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()