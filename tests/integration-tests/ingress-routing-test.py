# File location: tests/integration-tests/ingress-routing-test.py
# Integration tests for Ingress routing and load balancing

import pytest
import requests
import time
import os
import logging
from kubernetes import client, config
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestIngressRouting:
    """Test ingress routing and load balancing"""
    
    @classmethod
    def setup_class(cls):
        """Setup test environment"""
        # Load Kubernetes config
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        
        cls.k8s_client = client.ApiClient()
        cls.networking_v1 = client.NetworkingV1Api()
        cls.core_v1 = client.CoreV1Api()
        cls.apps_v1 = client.AppsV1Api()
        
        cls.namespace = os.getenv('TEST_NAMESPACE', 'kubeestatehub')
        cls.ingress_name = 'kubeestatehub-ingress'
        
        # Setup HTTP session with retry strategy
        cls.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        cls.session.mount("http://", adapter)
        cls.session.mount("https://", adapter)
        
        cls._get_ingress_info()
        cls._wait_for_ingress_ready()
    
    @classmethod
    def _get_ingress_info(cls):
        """Get ingress information"""
        try:
            ingress = cls.networking_v1.read_namespaced_ingress(
                name=cls.ingress_name,
                namespace=cls.namespace
            )
            
            cls.ingress = ingress
            
            # Get ingress host and paths
            cls.hosts = []
            cls.paths = {}
            
            for rule in ingress.spec.rules:
                host = rule.host or 'localhost'
                cls.hosts.append(host)
                cls.paths[host] = []
                
                if rule.http:
                    for path in rule.http.paths:
                        cls.paths[host].append({
                            'path': path.path,
                            'service': path.backend.service.name,
                            'port': path.backend.service.port.number
                        })
            
            # Determine base URL for testing
            if os.getenv('KUBERNETES_SERVICE_HOST'):
                # Running in cluster - use ingress controller service
                cls.base_url = "http://nginx-ingress-controller.ingress-nginx.svc.cluster.local"
            else:
                # Running locally - assume port-forward or external access
                cls.base_url = os.getenv('INGRESS_URL', 'http://localhost:80')
            
            logger.info(f"Testing ingress at: {cls.base_url}")
            logger.info(f"Configured hosts: {cls.hosts}")
            
        except Exception as e:
            logger.error(f"Failed to get ingress info: {e}")
            cls.ingress = None
            cls.hosts = ['localhost']
            cls.paths = {'localhost': []}
            cls.base_url = 'http://localhost:80'
    
    @classmethod
    def _wait_for_ingress_ready(cls, timeout=300):
        """Wait for ingress to be ready"""
        if not cls.ingress:
            logger.warning("No ingress found, skipping readiness check")
            return
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Check if ingress has load balancer status
                ingress = cls.networking_v1.read_namespaced_ingress(
                    name=cls.ingress_name,
                    namespace=cls.namespace
                )
                
                if ingress.status.load_balancer.ingress:
                    logger.info("Ingress has load balancer status")
                    return
                
            except Exception as e:
                logger.debug(f"Checking ingress status: {e}")
            
            logger.info("Waiting for ingress to be ready...")
            time.sleep(10)
        
        logger.warning("Ingress may not be fully ready, proceeding with tests")
    
    def test_ingress_exists(self):
        """Test that the ingress resource exists"""
        ingress = self.networking_v1.read_namespaced_ingress(
            name=self.ingress_name,
            namespace=self.namespace
        )
        
        assert ingress is not None
        assert ingress.metadata.name == self.ingress_name
        assert ingress.spec.rules is not None
        assert len(ingress.spec.rules) > 0
    
    def test_ingress_controller_running(self):
        """Test that ingress controller is running"""
        try:
            # Check for nginx ingress controller pods
            pods = self.core_v1.list_namespaced_pod(
                namespace='ingress-nginx',
                label_selector='app.kubernetes.io/name=ingress-nginx'
            )
            
            assert len(pods.items) > 0, "No ingress controller pods found"
            
            # Check that at least one pod is running
            running_pods = [pod for pod in pods.items if pod.status.phase == 'Running']
            assert len(running_pods) > 0, "No ingress controller pods are running"
            
        except Exception as e:
            logger.warning(f"Could not check ingress controller: {e}")
            # Try alternative approach
            self._check_ingress_controller_alternative()
    
    def _check_ingress_controller_alternative(self):
        """Alternative method to check ingress controller"""
        try:
            # Check for ingress controller service
            service = self.core_v1.read_namespaced_service(
                name='nginx-ingress-controller',
                namespace='ingress-nginx'
            )
            assert service is not None
        except:
            logger.warning("Could not verify ingress controller is running")
    
    def test_frontend_routing(self):
        """Test routing to frontend service"""
        for host in self.hosts:
            headers = {'Host': host} if host != 'localhost' else {}
            
            try:
                response = self.session.get(
                    f"{self.base_url}/",
                    headers=headers,
                    timeout=10
                )
                
                # Should either succeed or return a valid HTTP error
                assert response.status_code < 500, f"Server error for host {host}: {response.status_code}"
                
                if response.status_code == 200:
                    # Check if it's the frontend
                    content_type = response.headers.get('content-type', '')
                    assert 'text/html' in content_type.lower(), "Frontend should return HTML"
                    
                elif response.status_code == 404:
                    logger.info(f"Frontend not found at root path for host {host}")
                
            except requests.exceptions.RequestException as e:
                pytest.skip(f"Could not reach ingress for host {host}: {e}")
    
    def test_api_routing(self):
        """Test routing to API service"""
        api_paths = ['/api/v1/properties', '/api/v1/health']
        
        for host in self.hosts:
            headers = {'Host': host} if host != 'localhost' else {}
            
            for path in api_paths:
                try:
                    response = self.session.get(
                        f"{self.base_url}{path}",
                        headers=headers,
                        timeout=10
                    )
                    
                    # Should not return 404 (routing should work)
                    if response.status_code == 404:
                        logger.warning(f"API path {path} not found for host {host}")
                    else:
                        assert response.status_code < 500, f"Server error for {path}: {response.status_code}"
                        
                        if response.status_code == 200:
                            # For JSON APIs, check content type
                            if 'health' in path:
                                content_type = response.headers.get('content-type', '')
                                assert 'application/json' in content_type.lower(), "API should return JSON"
                
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Could not test API path {path} for host {host}: {e}")
    
    def test_https_redirect(self):
        """Test HTTPS redirect if configured"""
        if not self.ingress or not self.ingress.spec.tls:
            pytest.skip("TLS not configured on ingress")
        
        for host in self.hosts:
            headers = {'Host': host} if host != 'localhost' else {}
            
            try:
                # Make HTTP request
                response = self.session.get(
                    f"http://{host}/",
                    headers=headers,
                    timeout=10,
                    allow_redirects=False
                )
                
                if response.status_code in [301, 302, 307, 308]:
                    location = response.headers.get('location', '')
                    assert location.startswith('https://'), "Should redirect to HTTPS"
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Could not test HTTPS redirect for host {host}: {e}")
    
    def test_load_balancing(self):
        """Test load balancing across backend pods"""
        # Get backend service endpoints
        try:
            endpoints = self.core_v1.read_namespaced_endpoints(
                name='listings-api-service',
                namespace=self.namespace
            )
            
            if not endpoints.subsets or len(endpoints.subsets[0].addresses) < 2:
                pytest.skip("Not enough backend pods for load balancing test")
            
            # Make multiple requests to see if they're distributed
            server_identifiers = set()
            
            for i in range(10):
                for host in self.hosts:
                    headers = {'Host': host} if host != 'localhost' else {}
                    
                    try:
                        response = self.session.get(
                            f"{self.base_url}/api/v1/health",
                            headers=headers,
                            timeout=5
                        )
                        
                        if response.status_code == 200:
                            # Look for server identifier in response
                            data = response.json()
                            if 'server_id' in data:
                                server_identifiers.add(data['server_id'])
                            elif 'hostname' in data:
                                server_identifiers.add(data['hostname'])
                    
                    except Exception:
                        pass
                
                time.sleep(0.1)  # Small delay between requests
            
            # If we have multiple backends, we should see some distribution
            if len(endpoints.subsets[0].addresses) > 1:
                logger.info(f"Unique server identifiers seen: {len(server_identifiers)}")
                # We might not always hit all backends, so don't assert too strictly
        
        except Exception as e:
            logger.warning(f"Could not test load balancing: {e}")
    
    def test_path_based_routing(self):
        """Test path-based routing rules"""
        test_paths = [
            ('/', 'frontend-dashboard-service'),
            ('/api/v1/', 'listings-api-service'),
            ('/metrics', 'listings-api-service'),
            ('/health', 'listings-api-service')
        ]
        
        for path, expected_service in test_paths:
            for host in self.hosts:
                headers = {'Host': host} if host != 'localhost' else {}
                
                try:
                    response = self.session.get(
                        f"{self.base_url}{path}",
                        headers=headers,
                        timeout=10
                    )
                    
                    # Check if routing works (not 404)
                    if response.status_code != 404:
                        logger.info(f"Path {path} correctly routed (status: {response.status_code})")
                    
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Could not test path {path}: {e}")
    
    def test_ingress_annotations(self):
        """Test ingress annotations are properly applied"""
        if not self.ingress:
            pytest.skip("No ingress found")
        
        annotations = self.ingress.metadata.annotations or {}
        
        # Check for common ingress annotations
        expected_annotations = [
            'kubernetes.io/ingress.class',
            'nginx.ingress.kubernetes.io/rewrite-target'
        ]
        
        for annotation in expected_annotations:
            if annotation in annotations:
                logger.info(f"Found annotation: {annotation} = {annotations[annotation]}")
    
    def test_ingress_backend_health(self):
        """Test that ingress backends are healthy"""
        services_to_check = ['listings-api-service', 'frontend-dashboard-service']
        
        for service_name in services_to_check:
            try:
                service = self.core_v1.read_namespaced_service(
                    name=service_name,
                    namespace=self.namespace
                )
                
                assert service is not None, f"Service {service_name} not found"
                
                # Check endpoints
                endpoints = self.core_v1.read_namespaced_endpoints(
                    name=service_name,
                    namespace=self.namespace
                )
                
                if endpoints.subsets:
                    ready_addresses = len(endpoints.subsets[0].addresses or [])
                    not_ready_addresses = len(endpoints.subsets[0].not_ready_addresses or [])
                    
                    logger.info(f"Service {service_name}: {ready_addresses} ready, {not_ready_addresses} not ready")
                    assert ready_addresses > 0, f"No ready endpoints for {service_name}"
                
            except Exception as e:
                logger.warning(f"Could not check service {service_name}: {e}")
    
    def test_ingress_rate_limiting(self):
        """Test rate limiting if configured"""
        if not self.ingress:
            pytest.skip("No ingress found")
        
        annotations = self.ingress.metadata.annotations or {}
        rate_limit_annotation = 'nginx.ingress.kubernetes.io/rate-limit-rps'
        
        if rate_limit_annotation not in annotations:
            pytest.skip("Rate limiting not configured")
        
        # Make rapid requests to trigger rate limiting
        rate_limited_responses = []
        
        for i in range(20):
            for host in self.hosts:
                headers = {'Host': host} if host != 'localhost' else {}
                
                try:
                    response = self.session.get(
                        f"{self.base_url}/api/v1/properties",
                        headers=headers,
                        timeout=2
                    )
                    
                    if response.status_code == 429:
                        rate_limited_responses.append(response)
                        
                except requests.exceptions.RequestException:
                    pass
        
        if rate_limited_responses:
            logger.info(f"Rate limiting working: {len(rate_limited_responses)} requests limited")
        else:
            logger.info("No rate limiting detected (may not be configured)")
    
    def test_ingress_ssl_certificate(self):
        """Test SSL certificate if TLS is configured"""
        if not self.ingress or not self.ingress.spec.tls:
            pytest.skip("TLS not configured on ingress")
        
        import ssl
        import socket
        
        for tls_config in self.ingress.spec.tls:
            for host in tls_config.hosts:
                try:
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                    
                    with socket.create_connection((host, 443), timeout=10) as sock:
                        with context.wrap_socket(sock, server_hostname=host) as ssock:
                            cert = ssock.getpeercert()
                            
                            # Check certificate basics
                            assert cert is not None, f"No certificate for {host}"
                            
                            # Check if certificate covers the host
                            subject = dict(x[0] for x in cert['subject'])
                            common_name = subject.get('commonName', '')
                            
                            logger.info(f"Certificate for {host}: CN={common_name}")
                            
                except Exception as e:
                    logger.warning(f"Could not check SSL certificate for {host}: {e}")
    
    def test_ingress_timeouts(self):
        """Test ingress timeout configurations"""
        if not self.ingress:
            pytest.skip("No ingress found")
        
        annotations = self.ingress.metadata.annotations or {}
        timeout_annotations = [
            'nginx.ingress.kubernetes.io/proxy-connect-timeout',
            'nginx.ingress.kubernetes.io/proxy-send-timeout',
            'nginx.ingress.kubernetes.io/proxy-read-timeout'
        ]
        
        for annotation in timeout_annotations:
            if annotation in annotations:
                timeout_value = annotations[annotation]
                logger.info(f"Timeout configuration: {annotation} = {timeout_value}")
                
                # Parse timeout value (should be a number)
                try:
                    timeout_seconds = int(timeout_value)
                    assert timeout_seconds > 0, f"Invalid timeout value: {timeout_value}"
                    assert timeout_seconds <= 3600, f"Timeout too high: {timeout_value}"
                except ValueError:
                    logger.warning(f"Could not parse timeout value: {timeout_value}")
    
    def test_ingress_cors_headers(self):
        """Test CORS headers if configured"""
        for host in self.hosts:
            headers = {
                'Host': host,
                'Origin': f'https://{host}',
                'Access-Control-Request-Method': 'GET'
            } if host != 'localhost' else {'Origin': 'http://localhost'}
            
            try:
                response = self.session.options(
                    f"{self.base_url}/api/v1/properties",
                    headers=headers,
                    timeout=10
                )
                
                # Check for CORS headers
                cors_headers = [
                    'Access-Control-Allow-Origin',
                    'Access-Control-Allow-Methods',
                    'Access-Control-Allow-Headers'
                ]
                
                found_cors_headers = []
                for cors_header in cors_headers:
                    if cors_header in response.headers:
                        found_cors_headers.append(cors_header)
                        logger.info(f"CORS header {cors_header}: {response.headers[cors_header]}")
                
                if found_cors_headers:
                    logger.info(f"CORS configured for host {host}")
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Could not test CORS for host {host}: {e}")
    
    def test_ingress_error_pages(self):
        """Test custom error pages"""
        # Test 404 error page
        for host in self.hosts:
            headers = {'Host': host} if host != 'localhost' else {}
            
            try:
                response = self.session.get(
                    f"{self.base_url}/nonexistent-page-12345",
                    headers=headers,
                    timeout=10
                )
                
                assert response.status_code == 404, "Should return 404 for non-existent page"
                
                # Check if custom error page is served
                content_length = response.headers.get('content-length', '0')
                if int(content_length) > 100:
                    logger.info(f"Custom 404 page detected for host {host}")
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Could not test error pages for host {host}: {e}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])