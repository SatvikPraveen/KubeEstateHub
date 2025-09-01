# Location: `/src/metrics-service/metrics_exporter.py`

import os
import time
import logging
import threading
import signal
import sys
from typing import Dict, Any, List
import psycopg2
import psycopg2.extras
import redis
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge, Info, start_http_server, generate_latest, CONTENT_TYPE_LATEST
from flask import Flask, Response
import requests
import json
from datetime import datetime, timedelta

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://kubeestatehub:password@postgresql-db:5432/kubeestatehub')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis-service:6379/0')
METRICS_PORT = int(os.getenv('METRICS_PORT', '8080'))
SCRAPE_INTERVAL = int(os.getenv('SCRAPE_INTERVAL', '30'))  # seconds
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LISTINGS_API_URL = os.getenv('LISTINGS_API_URL', 'http://listings-api:80')
ANALYTICS_WORKER_URL = os.getenv('ANALYTICS_WORKER_URL', 'http://analytics-worker:9090')

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app for health endpoints
app = Flask(__name__)

class KubeEstateHubMetricsExporter:
    """Custom Prometheus metrics exporter for KubeEstateHub"""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        self.running = True
        
        # Database metrics
        self.db_connections = Gauge(
            'kubeestatehub_db_connections_active',
            'Number of active database connections',
            registry=self.registry
        )
        
        self.db_query_duration = Histogram(
            'kubeestatehub_db_query_duration_seconds',
            'Database query duration in seconds',
            ['query_type'],
            registry=self.registry
        )
        
        self.listings_total = Gauge(
            'kubeestatehub_listings_total',
            'Total number of property listings',
            ['status', 'property_type'],
            registry=self.registry
        )
        
        self.listings_price_avg = Gauge(
            'kubeestatehub_listings_price_average',
            'Average listing price',
            ['city', 'property_type'],
            registry=self.registry
        )
        
        self.listings_days_on_market_avg = Gauge(
            'kubeestatehub_listings_days_on_market_average',
            'Average days on market',
            ['city', 'property_type'],
            registry=self.registry
        )
        
        # API metrics
        self.api_requests_total = Counter(
            'kubeestatehub_api_requests_total',
            'Total API requests',
            ['endpoint', 'method', 'status'],
            registry=self.registry
        )
        
        self.api_response_time = Histogram(
            'kubeestatehub_api_response_time_seconds',
            'API response time in seconds',
            ['endpoint'],
            registry=self.registry
        )
        
        # Business metrics
        self.market_trend_score = Gauge(
            'kubeestatehub_market_trend_score',
            'Market trend score (-1 to 1, where 1 is strong upward trend)',
            ['city'],
            registry=self.registry
        )
        
        self.inventory_levels = Gauge(
            'kubeestatehub_inventory_levels_months',
            'Months of inventory available',
            ['city', 'property_type'],
            registry=self.registry
        )
        
        self.price_per_sqft_avg = Gauge(
            'kubeestatehub_price_per_sqft_average',
            'Average price per square foot',
            ['city', 'property_type'],
            registry=self.registry
        )
        
        # System health metrics
        self.service_up = Gauge(
            'kubeestatehub_service_up',
            'Service availability (1 = up, 0 = down)',
            ['service'],
            registry=self.registry
        )
        
        self.last_scrape_timestamp = Gauge(
            'kubeestatehub_last_scrape_timestamp',
            'Timestamp of last successful metrics scrape',
            registry=self.registry
        )
        
        # Application info
        self.app_info = Info(
            'kubeestatehub_app_info',
            'Application information',
            registry=self.registry
        )
        
        # Set application info
        self.app_info.info({
            'version': '1.0.0',
            'build_date': datetime.utcnow().isoformat(),
            'environment': os.getenv('ENVIRONMENT', 'production')
        })
        
        # Initialize connections
        self.init_connections()
    
    def init_connections(self):
        """Initialize database and Redis connections"""
        try:
            # Test database connection
            conn = psycopg2.connect(DATABASE_URL)
            conn.close()
            logger.info("Database connection successful")
            
            # Test Redis connection
            self.redis_client = redis.from_url(REDIS_URL)
            self.redis_client.ping()
            logger.info("Redis connection successful")
            
        except Exception as e:
            logger.error(f"Connection initialization failed: {e}")
            raise
    
    def get_db_connection(self):
        """Get database connection with error handling"""
        try:
            return psycopg2.connect(DATABASE_URL)
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            self.service_up.labels(service='database').set(0)
            raise
    
    def collect_database_metrics(self):
        """Collect metrics from PostgreSQL database"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Database connections
            with self.db_query_duration.labels(query_type='connection_count').time():
                cursor.execute("""
                    SELECT count(*) as active_connections 
                    FROM pg_stat_activity 
                    WHERE state = 'active'
                """)
                result = cursor.fetchone()
                self.db_connections.set(result['active_connections'])
            
            # Listings metrics by status and type
            with self.db_query_duration.labels(query_type='listings_count').time():
                cursor.execute("""
                    SELECT status, property_type, COUNT(*) as count
                    FROM listings
                    GROUP BY status, property_type
                """)
                for row in cursor.fetchall():
                    self.listings_total.labels(
                        status=row['status'],
                        property_type=row['property_type']
                    ).set(row['count'])
            
            # Average prices by city and property type
            with self.db_query_duration.labels(query_type='price_analytics').time():
                cursor.execute("""
                    SELECT city, property_type, 
                           AVG(price) as avg_price,
                           AVG(price::float / NULLIF(square_feet, 0)) as avg_price_per_sqft,
                           AVG(EXTRACT(EPOCH FROM (COALESCE(updated_at, created_at) - listing_date))/86400) as avg_days_on_market
                    FROM listings 
                    WHERE status = 'active' 
                    AND price > 0
                    GROUP BY city, property_type
                    HAVING COUNT(*) >= 5
                """)
                
                for row in cursor.fetchall():
                    city = row['city']
                    prop_type = row['property_type']
                    
                    self.listings_price_avg.labels(
                        city=city,
                        property_type=prop_type
                    ).set(float(row['avg_price'] or 0))
                    
                    if row['avg_price_per_sqft']:
                        self.price_per_sqft_avg.labels(
                            city=city,
                            property_type=prop_type
                        ).set(float(row['avg_price_per_sqft']))
                    
                    if row['avg_days_on_market']:
                        self.listings_days_on_market_avg.labels(
                            city=city,
                            property_type=prop_type
                        ).set(float(row['avg_days_on_market']))
            
            # Market trend analysis
            with self.db_query_duration.labels(query_type='market_trends').time():
                cursor.execute("""
                    SELECT city, property_type,
                           avg_price,
                           (avg_price - LAG(avg_price) OVER (PARTITION BY city, property_type ORDER BY period_end)) / 
                           LAG(avg_price) OVER (PARTITION BY city, property_type ORDER BY period_end) as price_change
                    FROM market_trends
                    WHERE period_end >= CURRENT_DATE - INTERVAL '60 days'
                    ORDER BY city, property_type, period_end DESC
                """)
                
                city_trends = {}
                for row in cursor.fetchall():
                    city = row['city']
                    if row['price_change'] is not None:
                        if city not in city_trends:
                            city_trends[city] = []
                        city_trends[city].append(float(row['price_change']))
                
                # Calculate trend scores
                for city, changes in city_trends.items():
                    if changes:
                        # Simple trend score: average of recent price changes
                        trend_score = sum(changes) / len(changes)
                        # Normalize to -1 to 1 range
                        trend_score = max(-1, min(1, trend_score * 10))
                        self.market_trend_score.labels(city=city).set(trend_score)
            
            cursor.close()
            conn.close()
            
            self.service_up.labels(service='database').set(1)
            logger.debug("Database metrics collected successfully")
            
        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
            self.service_up.labels(service='database').set(0)
    
    def collect_api_metrics(self):
        """Collect metrics from API services"""
        services = [
            ('listings-api', LISTINGS_API_URL),
            ('analytics-worker', ANALYTICS_WORKER_URL)
        ]
        
        for service_name, base_url in services:
            try:
                # Health check
                response = requests.get(f"{base_url}/health", timeout=5)
                if response.status_code == 200:
                    self.service_up.labels(service=service_name).set(1)
                else:
                    self.service_up.labels(service=service_name).set(0)
                
                # Try to get metrics from service
                try:
                    metrics_response = requests.get(f"{base_url}/metrics", timeout=5)
                    if metrics_response.status_code == 200:
                        # Parse and re-export relevant metrics
                        # This is a simplified approach - in production, you might parse the Prometheus format
                        logger.debug(f"Retrieved metrics from {service_name}")
                except:
                    pass  # Metrics endpoint might not exist
                    
            except Exception as e:
                logger.warning(f"Failed to collect metrics from {service_name}: {e}")
                self.service_up.labels(service=service_name).set(0)
    
    def collect_redis_metrics(self):
        """Collect metrics from Redis"""
        try:
            info = self.redis_client.info()
            
            # Redis connection status
            if info:
                self.service_up.labels(service='redis').set(1)
            else:
                self.service_up.labels(service='redis').set(0)
                
        except Exception as e:
            logger.warning(f"Failed to collect Redis metrics: {e}")
            self.service_up.labels(service='redis').set(0)
    
    def calculate_inventory_levels(self):
        """Calculate inventory levels (months of supply)"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Calculate months of inventory for each city/property type
            cursor.execute("""
                WITH recent_sales AS (
                    SELECT city, property_type, COUNT(*) as monthly_sales
                    FROM listings
                    WHERE status = 'sold' 
                    AND updated_at >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY city, property_type
                ),
                current_inventory AS (
                    SELECT city, property_type, COUNT(*) as active_listings
                    FROM listings
                    WHERE status = 'active'
                    GROUP BY city, property_type
                )
                SELECT ci.city, ci.property_type,
                       ci.active_listings,
                       COALESCE(rs.monthly_sales, 1) as monthly_sales,
                       ci.active_listings::float / NULLIF(rs.monthly_sales, 0) as months_supply
                FROM current_inventory ci
                LEFT JOIN recent_sales rs ON ci.city = rs.city AND ci.property_type = rs.property_type
                WHERE ci.active_listings > 0
            """)
            
            for row in cursor.fetchall():
                if row['months_supply']:
                    self.inventory_levels.labels(
                        city=row['city'],
                        property_type=row['property_type']
                    ).set(float(row['months_supply']))
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error calculating inventory levels: {e}")
    
    def collect_all_metrics(self):
        """Collect all metrics"""
        start_time = time.time()
        
        try:
            logger.debug("Starting metrics collection cycle")
            
            # Collect metrics from various sources
            self.collect_database_metrics()
            self.collect_api_metrics()
            self.collect_redis_metrics()
            self.calculate_inventory_levels()
            
            # Update last scrape timestamp
            self.last_scrape_timestamp.set(time.time())
            
            duration = time.time() - start_time
            logger.info(f"Metrics collection completed in {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Error in metrics collection cycle: {e}")
    
    def run_collector_loop(self):
        """Main collector loop"""
        logger.info("Starting metrics collector loop")
        
        while self.running:
            try:
                self.collect_all_metrics()
                time.sleep(SCRAPE_INTERVAL)
            except Exception as e:
                logger.error(f"Error in collector loop: {e}")
                time.sleep(5)  # Short sleep before retry
    
    def stop(self):
        """Stop the collector"""
        self.running = False
        logger.info("Metrics collector stopped")

# Global exporter instance
exporter = KubeEstateHubMetricsExporter()

# Flask routes for health checks and metrics
@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Basic health checks
        conn = psycopg2.connect(DATABASE_URL)
        conn.close()
        
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'database': 'connected',
                'redis': 'connected' if exporter.redis_client.ping() else 'disconnected'
            }
        }
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 500

@app.route('/ready')
def readiness_check():
    """Readiness check endpoint"""
    return {'status': 'ready', 'timestamp': datetime.utcnow().isoformat()}

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    from prometheus_client import generate_latest
    return Response(generate_latest(exporter.registry), mimetype=CONTENT_TYPE_LATEST)

@app.route('/metrics/json')
def metrics_json():
    """JSON formatted metrics for debugging"""
    try:
        # Get basic metrics in JSON format
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'active') as active_listings,
                COUNT(*) FILTER (WHERE status = 'sold') as sold_listings,
                AVG(price) FILTER (WHERE status = 'active') as avg_active_price,
                COUNT(DISTINCT city) as cities_count
            FROM listings
        """)
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'summary': dict(result),
            'services': {
                'database': 'up',
                'redis': 'up' if exporter.redis_client.ping() else 'down'
            }
        }
    except Exception as e:
        return {'error': str(e)}, 500

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    exporter.stop()
    sys.exit(0)

def main():
    """Main application entry point"""
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start metrics collector in background thread
    collector_thread = threading.Thread(target=exporter.run_collector_loop, daemon=True)
    collector_thread.start()
    
    logger.info(f"Starting metrics service on port {METRICS_PORT}")
    
    # Start Flask app
    app.run(host='0.0.0.0', port=METRICS_PORT, debug=False)

if __name__ == '__main__':
    main()