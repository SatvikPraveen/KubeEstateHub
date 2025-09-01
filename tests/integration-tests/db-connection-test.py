# File location: tests/integration-tests/db-connection-test.py
# Database connection and integration tests

import pytest
import os
import time
import psycopg2
import logging
from kubernetes import client, config
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestDatabaseConnection:
    """Test database connectivity and operations"""
    
    @classmethod
    def setup_class(cls):
        """Setup test environment"""
        # Load Kubernetes config
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        
        cls.k8s_client = client.ApiClient()
        cls.core_v1 = client.CoreV1Api()
        cls.apps_v1 = client.AppsV1Api()
        
        cls.namespace = os.getenv('TEST_NAMESPACE', 'kubeestatehub')
        cls._get_database_credentials()
        cls._wait_for_database_ready()
    
    @classmethod
    def _get_database_credentials(cls):
        """Get database credentials from Kubernetes secrets"""
        try:
            # Get database secret
            secret = cls.core_v1.read_namespaced_secret(
                name='db-secret',
                namespace=cls.namespace
            )
            
            # Decode base64 values
            import base64
            cls.db_host = base64.b64decode(secret.data['host']).decode('utf-8')
            cls.db_port = int(base64.b64decode(secret.data['port']).decode('utf-8'))
            cls.db_name = base64.b64decode(secret.data['database']).decode('utf-8')
            cls.db_user = base64.b64decode(secret.data['username']).decode('utf-8')
            cls.db_password = base64.b64decode(secret.data['password']).decode('utf-8')
            
        except Exception as e:
            logger.warning(f"Could not get credentials from K8s secret: {e}")
            # Fallback to environment variables or defaults
            cls.db_host = os.getenv('DB_HOST', 'postgres-service.kubeestatehub.svc.cluster.local')
            cls.db_port = int(os.getenv('DB_PORT', '5432'))
            cls.db_name = os.getenv('DB_NAME', 'kubeestatehub')
            cls.db_user = os.getenv('DB_USER', 'postgres')
            cls.db_password = os.getenv('DB_PASSWORD', 'postgres123')
        
        # Create connection strings
        cls.connection_string = f"postgresql://{cls.db_user}:{cls.db_password}@{cls.db_host}:{cls.db_port}/{cls.db_name}"
        cls.psycopg2_params = {
            'host': cls.db_host,
            'port': cls.db_port,
            'database': cls.db_name,
            'user': cls.db_user,
            'password': cls.db_password
        }
    
    @classmethod
    def _wait_for_database_ready(cls, timeout=300):
        """Wait for database to be ready"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                conn = psycopg2.connect(**cls.psycopg2_params, connect_timeout=5)
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                cursor.fetchone()
                cursor.close()
                conn.close()
                logger.info("Database is ready")
                return
            except Exception as e:
                logger.info(f"Waiting for database: {e}")
                time.sleep(5)
        
        raise Exception("Database failed to become ready within timeout")
    
    def test_basic_connection(self):
        """Test basic database connection"""
        conn = psycopg2.connect(**self.psycopg2_params)
        assert conn is not None
        
        cursor = conn.cursor()
        cursor.execute('SELECT version()')
        version = cursor.fetchone()[0]
        assert 'PostgreSQL' in version
        
        cursor.close()
        conn.close()
    
    def test_database_exists(self):
        """Test that the required database exists"""
        conn = psycopg2.connect(**self.psycopg2_params)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT datname FROM pg_catalog.pg_database 
            WHERE datname = %s
        """, (self.db_name,))
        
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == self.db_name
        
        cursor.close()
        conn.close()
    
    def test_sqlalchemy_connection(self):
        """Test SQLAlchemy connection"""
        engine = create_engine(self.connection_string)
        
        with engine.connect() as connection:
            result = connection.execute(text('SELECT 1 as test'))
            assert result.fetchone()[0] == 1
    
    def test_connection_pool(self):
        """Test database connection pooling"""
        engine = create_engine(
            self.connection_string,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600
        )
        
        # Test multiple concurrent connections
        connections = []
        try:
            for i in range(3):
                conn = engine.connect()
                connections.append(conn)
                
                result = conn.execute(text(f'SELECT {i+1} as test'))
                assert result.fetchone()[0] == i+1
            
            # Check pool status
            pool = engine.pool
            assert pool.size() <= 5  # Should not exceed pool_size
            
        finally:
            for conn in connections:
                conn.close()
    
    def test_database_schema(self):
        """Test that required database schema exists"""
        conn = psycopg2.connect(**self.psycopg2_params)
        cursor = conn.cursor()
        
        # Check if properties table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'properties'
            )
        """)
        
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            # Create table for testing
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS properties (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    price DECIMAL(12,2),
                    bedrooms INTEGER,
                    bathrooms INTEGER,
                    square_feet INTEGER,
                    address JSONB,
                    property_type VARCHAR(50),
                    status VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        
        # Verify table structure
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'properties'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        column_names = [col[0] for col in columns]
        
        required_columns = ['id', 'title', 'price', 'created_at']
        for required_col in required_columns:
            assert required_col in column_names, f"Missing required column: {required_col}"
        
        cursor.close()
        conn.close()
    
    def test_crud_operations(self):
        """Test basic CRUD operations"""
        conn = psycopg2.connect(**self.psycopg2_params)
        cursor = conn.cursor()
        
        # Ensure table exists
        self.test_database_schema()
        
        # Create
        cursor.execute("""
            INSERT INTO properties (title, price, bedrooms, bathrooms, property_type, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, ("Test Property", 250000, 3, 2, "single_family", "active"))
        
        property_id = cursor.fetchone()[0]
        conn.commit()
        
        # Read
        cursor.execute("SELECT title, price FROM properties WHERE id = %s", (property_id,))
        result = cursor.fetchone()
        assert result[0] == "Test Property"
        assert float(result[1]) == 250000.0
        
        # Update
        cursor.execute("""
            UPDATE properties SET price = %s WHERE id = %s
        """, (275000, property_id))
        conn.commit()
        
        cursor.execute("SELECT price FROM properties WHERE id = %s", (property_id,))
        updated_price = cursor.fetchone()[0]
        assert float(updated_price) == 275000.0
        
        # Delete
        cursor.execute("DELETE FROM properties WHERE id = %s", (property_id,))
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM properties WHERE id = %s", (property_id,))
        count = cursor.fetchone()[0]
        assert count == 0
        
        cursor.close()
        conn.close()
    
    def test_transactions(self):
        """Test database transactions"""
        conn = psycopg2.connect(**self.psycopg2_params)
        cursor = conn.cursor()
        
        try:
            # Begin transaction
            cursor.execute("""
                INSERT INTO properties (title, price)
                VALUES ('Transaction Test 1', 100000)
                RETURNING id
            """)
            id1 = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO properties (title, price)
                VALUES ('Transaction Test 2', 200000)
                RETURNING id
            """)
            id2 = cursor.fetchone()[0]
            
            # Rollback transaction
            conn.rollback()
            
            # Verify rollback
            cursor.execute("SELECT COUNT(*) FROM properties WHERE id IN (%s, %s)", (id1, id2))
            count = cursor.fetchone()[0]
            assert count == 0
            
            # Test commit
            cursor.execute("""
                INSERT INTO properties (title, price)
                VALUES ('Transaction Test Commit', 150000)
                RETURNING id
            """)
            commit_id = cursor.fetchone()[0]
            conn.commit()
            
            cursor.execute("SELECT title FROM properties WHERE id = %s", (commit_id,))
            result = cursor.fetchone()
            assert result[0] == 'Transaction Test Commit'
            
            # Cleanup
            cursor.execute("DELETE FROM properties WHERE id = %s", (commit_id,))
            conn.commit()
            
        finally:
            cursor.close()
            conn.close()
    
    def test_database_performance(self):
        """Test basic database performance"""
        conn = psycopg2.connect(**self.psycopg2_params)
        cursor = conn.cursor()
        
        # Test bulk insert performance
        start_time = time.time()
        
        test_data = []
        for i in range(100):
            test_data.append((
                f"Performance Test Property {i}",
                100000 + (i * 1000),
                3, 2, "single_family", "active"
            ))
        
        cursor.executemany("""
            INSERT INTO properties (title, price, bedrooms, bathrooms, property_type, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, test_data)
        
        conn.commit()
        insert_time = time.time() - start_time
        
        # Test query performance
        start_time = time.time()
        cursor.execute("SELECT COUNT(*) FROM properties WHERE price > %s", (150000,))
        count = cursor.fetchone()[0]
        query_time = time.time() - start_time
        
        # Performance assertions (adjust thresholds as needed)
        assert insert_time < 5.0, f"Bulk insert took too long: {insert_time}s"
        assert query_time < 1.0, f"Query took too long: {query_time}s"
        assert count > 0, "No results returned from performance query"
        
        # Cleanup
        cursor.execute("DELETE FROM properties WHERE title LIKE 'Performance Test Property%'")
        conn.commit()
        
        cursor.close()
        conn.close()
    
    def test_kubernetes_database_integration(self):
        """Test Kubernetes database integration"""
        # Check if PostgreSQL StatefulSet is running
        statefulset = self.apps_v1.read_namespaced_stateful_set(
            name='postgres',
            namespace=self.namespace
        )
        
        assert statefulset.status.ready_replicas > 0
        assert statefulset.status.ready_replicas == statefulset.status.replicas
        
        # Check if database service exists
        service = self.core_v1.read_namespaced_service(
            name='postgres-service',
            namespace=self.namespace
        )
        
        assert service.spec.ports[0].port == 5432
        
        # Check if persistent volume claim exists
        pvc = self.core_v1.read_namespaced_persistent_volume_claim(
            name='postgres-pvc',
            namespace=self.namespace
        )
        
        assert pvc.status.phase == 'Bound'
    
    def test_database_backup_readiness(self):
        """Test if database is ready for backup operations"""
        conn = psycopg2.connect(**self.psycopg2_params)
        cursor = conn.cursor()
        
        # Check if pg_dump would work
        cursor.execute("SELECT current_user")
        current_user = cursor.fetchone()[0]
        
        # Check permissions
        cursor.execute("""
            SELECT has_database_privilege(current_user, current_database(), 'CONNECT')
        """)
        can_connect = cursor.fetchone()[0]
        assert can_connect, "User should have CONNECT privilege"
        
        cursor.execute("""
            SELECT has_database_privilege(current_user, current_database(), 'CREATE')
        """)
        can_create = cursor.fetchone()[0]
        # Log create permission (not always required)
        logger.info(f"User {current_user} has CREATE privilege: {can_create}")
        
        cursor.close()
        conn.close()
    
    def test_connection_limits(self):
        """Test database connection limits"""
        conn = psycopg2.connect(**self.psycopg2_params)
        cursor = conn.cursor()
        
        # Check current connections
        cursor.execute("""
            SELECT count(*) FROM pg_stat_activity 
            WHERE state = 'active'
        """)
        active_connections = cursor.fetchone()[0]
        
        # Check max connections
        cursor.execute("SHOW max_connections")
        max_connections = int(cursor.fetchone()[0])
        
        logger.info(f"Active connections: {active_connections}, Max: {max_connections}")
        
        # Ensure we're not close to the limit
        assert active_connections < max_connections * 0.8, "Too many active connections"
        
        cursor.close()
        conn.close()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])