# Location: `/src/listings-api/k8s_health.py`

"""
Kubernetes health check utilities for the listings API
"""

import logging
import time
import psycopg2
import redis
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)

class HealthChecker:
    """Health checker for Kubernetes probes"""
    
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL', 'postgresql://kubeestatehub:password@postgresql-db:5432/kubeestatehub')
        self.redis_url = os.getenv('REDIS_URL', 'redis://redis-service:6379/0')
        self.startup_time = time.time()
        self.ready = False
        
    def check_database(self) -> Dict[str, Any]:
        """Check database connectivity"""
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return {
                'status': 'healthy',
                'response_time_ms': 0,  # Could measure actual response time
                'details': 'Database connection successful'
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'details': 'Database connection failed'
            }
    
    def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity"""
        try:
            redis_client = redis.from_url(self.redis_url)
            redis_client.ping()
            
            return {
                'status': 'healthy',
                'details': 'Redis connection successful'
            }
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return {
                'status': 'degraded',
                'error': str(e),
                'details': 'Redis connection failed - service will continue without caching'
            }
    
    def liveness_probe(self) -> Dict[str, Any]:
        """
        Liveness probe - indicates if the application is running
        Should restart the container if this fails
        """
        try:
            # Basic application health checks
            db_health = self.check_database()
            
            # If database is down, application is not live
            if db_health['status'] == 'unhealthy':
                return {
                    'status': 'unhealthy',
                    'checks': {
                        'database': db_health
                    },
                    'message': 'Critical dependency failed'
                }
            
            return {
                'status': 'healthy',
                'uptime_seconds': time.time() - self.startup_time,
                'checks': {
                    'database': db_health
                },
                'message': 'Application is alive'
            }
        except Exception as e:
            logger.error(f"Liveness probe failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'message': 'Liveness probe exception'
            }
    
    def readiness_probe(self) -> Dict[str, Any]:
        """
        Readiness probe - indicates if the application is ready to serve traffic
        Should remove from service if this fails
        """
        try:
            # More comprehensive checks for readiness
            db_health = self.check_database()
            redis_health = self.check_redis()
            
            # Check if application has finished initialization
            if not self.ready and time.time() - self.startup_time < 30:
                return {
                    'status': 'not_ready',
                    'message': 'Application still initializing',
                    'uptime_seconds': time.time() - self.startup_time
                }
            
            self.ready = True
            
            # Determine overall readiness
            if db_health['status'] == 'unhealthy':
                return {
                    'status': 'not_ready',
                    'checks': {
                        'database': db_health,
                        'redis': redis_health
                    },
                    'message': 'Critical dependency not ready'
                }
            
            return {
                'status': 'ready',
                'uptime_seconds': time.time() - self.startup_time,
                'checks': {
                    'database': db_health,
                    'redis': redis_health
                },
                'message': 'Application ready to serve traffic'
            }
        except Exception as e:
            logger.error(f"Readiness probe failed: {e}")
            return {
                'status': 'not_ready',
                'error': str(e),
                'message': 'Readiness probe exception'
            }
    
    def startup_probe(self) -> Dict[str, Any]:
        """
        Startup probe - indicates if the application has started successfully
        Gives more time for slow-starting applications
        """
        try:
            startup_timeout = 120  # 2 minutes startup timeout
            current_uptime = time.time() - self.startup_time
            
            if current_uptime > startup_timeout:
                return {
                    'status': 'failed',
                    'uptime_seconds': current_uptime,
                    'message': f'Application failed to start within {startup_timeout} seconds'
                }
            
            # Check basic connectivity
            db_health = self.check_database()
            
            if db_health['status'] == 'healthy':
                return {
                    'status': 'started',
                    'uptime_seconds': current_uptime,
                    'checks': {
                        'database': db_health
                    },
                    'message': 'Application started successfully'
                }
            else:
                return {
                    'status': 'starting',
                    'uptime_seconds': current_uptime,
                    'checks': {
                        'database': db_health
                    },
                    'message': 'Application still starting - waiting for dependencies'
                }
        except Exception as e:
            logger.error(f"Startup probe failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'message': 'Startup probe exception'
            }
    
    def get_detailed_health(self) -> Dict[str, Any]:
        """Get comprehensive health information"""
        return {
            'application': {
                'name': 'kubeestatehub-listings-api',
                'version': '1.0.0',
                'uptime_seconds': time.time() - self.startup_time,
                'startup_time': self.startup_time
            },
            'liveness': self.liveness_probe(),
            'readiness': self.readiness_probe(),
            'startup': self.startup_probe(),
            'dependencies': {
                'database': self.check_database(),
                'redis': self.check_redis()
            }
        }

# Global health checker instance
health_checker = HealthChecker()