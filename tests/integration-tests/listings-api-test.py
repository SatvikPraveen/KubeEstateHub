# File location: tests/integration-tests/listings-api-test.py
# Integration tests for the Listings API service

import pytest
import requests
import time
import json
import os
from datetime import datetime, timedelta
from kubernetes import client, config
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestListingsAPI:
    """Integration tests for Listings API"""
    
    @classmethod
    def setup_class(cls):
        """Setup test environment"""
        # Load Kubernetes config
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        
        cls.k8s_client = client.ApiClient()
        cls.apps_v1 = client.AppsV1Api()
        cls.core_v1 = client.CoreV1Api()
        
        # Get service endpoint
        cls.namespace = os.getenv('TEST_NAMESPACE', 'kubeestatehub')
        cls.service_name = 'listings-api-service'
        cls.base_url = cls._get_service_url()
        
        # Wait for service to be ready
        cls._wait_for_service_ready()
    
    @classmethod
    def _get_service_url(cls):
        """Get the service URL for testing"""
        try:
            service = cls.core_v1.read_namespaced_service(
                name=cls.service_name,
                namespace=cls.namespace
            )
            
            # If running in cluster, use service DNS
            if os.getenv('KUBERNETES_SERVICE_HOST'):
                return f"http://{cls.service_name}.{cls.namespace}.svc.cluster.local:8080"
            
            # If running locally, use port-forward or NodePort
            if service.spec.type == 'NodePort':
                node_port = service.spec.ports[0].node_port
                # Get node IP (simplified for testing)
                return f"http://localhost:{node_port}"
            else:
                return "http://localhost:8080"  # Assumes port-forward
                
        except Exception as e:
            logger.error(f"Failed to get service URL: {e}")
            return "http://localhost:8080"
    
    @classmethod
    def _wait_for_service_ready(cls, timeout=300):
        """Wait for the service to be ready"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{cls.base_url}/health", timeout=5)
                if response.status_code == 200:
                    logger.info("Service is ready")
                    return
            except requests.exceptions.RequestException:
                pass
            
            logger.info("Waiting for service to be ready...")
            time.sleep(5)
        
        raise Exception("Service failed to become ready within timeout")
    
    def test_health_endpoint(self):
        """Test the health check endpoint"""
        response = requests.get(f"{self.base_url}/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data['status'] == 'healthy'
        assert 'timestamp' in health_data
        assert 'version' in health_data
    
    def test_metrics_endpoint(self):
        """Test the metrics endpoint"""
        response = requests.get(f"{self.base_url}/metrics")
        assert response.status_code == 200
        
        # Check for Prometheus metrics format
        metrics_text = response.text
        assert 'http_requests_total' in metrics_text
        assert 'http_request_duration_seconds' in metrics_text
    
    def test_list_properties_empty(self):
        """Test listing properties when database is empty"""
        response = requests.get(f"{self.base_url}/api/v1/properties")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 0  # Could be empty initially
    
    def test_create_property(self):
        """Test creating a new property"""
        property_data = {
            "title": "Test Property",
            "description": "A beautiful test property",
            "price": 250000,
            "bedrooms": 3,
            "bathrooms": 2,
            "square_feet": 1500,
            "address": {
                "street": "123 Test St",
                "city": "Test City",
                "state": "TX",
                "zip_code": "12345"
            },
            "property_type": "single_family",
            "status": "active"
        }
        
        response = requests.post(
            f"{self.base_url}/api/v1/properties",
            json=property_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 201
        created_property = response.json()
        assert created_property['title'] == property_data['title']
        assert created_property['price'] == property_data['price']
        assert 'id' in created_property
        assert 'created_at' in created_property
        
        # Store property ID for other tests
        self.test_property_id = created_property['id']
    
    def test_get_property_by_id(self):
        """Test retrieving a specific property"""
        if not hasattr(self, 'test_property_id'):
            self.test_create_property()
        
        response = requests.get(f"{self.base_url}/api/v1/properties/{self.test_property_id}")
        assert response.status_code == 200
        
        property_data = response.json()
        assert property_data['id'] == self.test_property_id
        assert property_data['title'] == "Test Property"
    
    def test_get_nonexistent_property(self):
        """Test retrieving a non-existent property"""
        response = requests.get(f"{self.base_url}/api/v1/properties/99999")
        assert response.status_code == 404
        
        error_data = response.json()
        assert 'error' in error_data
        assert 'not found' in error_data['error'].lower()
    
    def test_update_property(self):
        """Test updating a property"""
        if not hasattr(self, 'test_property_id'):
            self.test_create_property()
        
        update_data = {
            "price": 275000,
            "description": "Updated beautiful test property"
        }
        
        response = requests.put(
            f"{self.base_url}/api/v1/properties/{self.test_property_id}",
            json=update_data,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 200
        updated_property = response.json()
        assert updated_property['price'] == 275000
        assert "Updated" in updated_property['description']
    
    def test_search_properties(self):
        """Test property search functionality"""
        # Create test data first
        if not hasattr(self, 'test_property_id'):
            self.test_create_property()
        
        # Test search by city
        response = requests.get(
            f"{self.base_url}/api/v1/properties/search",
            params={'city': 'Test City'}
        )
        assert response.status_code == 200
        
        search_results = response.json()
        assert isinstance(search_results, list)
        assert len(search_results) >= 1
        
        # Test search by price range
        response = requests.get(
            f"{self.base_url}/api/v1/properties/search",
            params={'min_price': 200000, 'max_price': 300000}
        )
        assert response.status_code == 200
        
        search_results = response.json()
        assert isinstance(search_results, list)
    
    def test_property_validation(self):
        """Test property data validation"""
        # Test missing required fields
        invalid_property = {
            "title": "Incomplete Property"
            # Missing required fields
        }
        
        response = requests.post(
            f"{self.base_url}/api/v1/properties",
            json=invalid_property,
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400
        error_data = response.json()
        assert 'error' in error_data
        assert 'validation' in error_data['error'].lower()
    
    def test_rate_limiting(self):
        """Test rate limiting (if implemented)"""
        # Make multiple rapid requests
        responses = []
        for i in range(10):
            response = requests.get(f"{self.base_url}/api/v1/properties")
            responses.append(response.status_code)
        
        # Check if any requests were rate limited (429 status)
        # This test might pass if rate limiting is not implemented
        rate_limited = any(status == 429 for status in responses)
        logger.info(f"Rate limiting test - Rate limited requests: {rate_limited}")
    
    def test_database_connection(self):
        """Test database connectivity"""
        response = requests.get(f"{self.base_url}/health/database")
        assert response.status_code == 200
        
        db_health = response.json()
        assert db_health['database'] == 'connected'
        assert 'connection_pool' in db_health
    
    def test_kubernetes_integration(self):
        """Test Kubernetes-specific functionality"""
        # Check if deployment exists and is ready
        deployment = self.apps_v1.read_namespaced_deployment(
            name='listings-api',
            namespace=self.namespace
        )
        
        assert deployment.status.ready_replicas > 0
        assert deployment.status.ready_replicas == deployment.status.replicas
        
        # Check if service exists
        service = self.core_v1.read_namespaced_service(
            name='listings-api-service',
            namespace=self.namespace
        )
        
        assert service.spec.ports[0].port == 8080
    
    def test_concurrent_requests(self):
        """Test handling concurrent requests"""
        import threading
        import queue
        
        results = queue.Queue()
        
        def make_request():
            try:
                response = requests.get(f"{self.base_url}/api/v1/properties", timeout=10)
                results.put(response.status_code)
            except Exception as e:
                results.put(f"Error: {e}")
        
        # Create 10 concurrent threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        status_codes = []
        while not results.empty():
            result = results.get()
            if isinstance(result, int):
                status_codes.append(result)
        
        # Most requests should succeed
        success_count = sum(1 for code in status_codes if code == 200)
        assert success_count >= 8, f"Only {success_count} out of {len(status_codes)} concurrent requests succeeded"
    
    def test_cleanup_test_data(self):
        """Clean up test data"""
        if hasattr(self, 'test_property_id'):
            response = requests.delete(f"{self.base_url}/api/v1/properties/{self.test_property_id}")
            # Don't assert here as delete might not be implemented
            logger.info(f"Cleanup attempt for property {self.test_property_id}: {response.status_code}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])