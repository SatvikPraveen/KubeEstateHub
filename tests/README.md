# File location: tests/README.md

# KubeEstateHub Testing Suite

This directory contains comprehensive tests for validating the KubeEstateHub Kubernetes deployment.

## Test Categories

### 1. K8s Lint Tests (`k8s-lint-tests/`)

#### Kube-Score Tests

- **File**: `kube-score.yaml`
- **Purpose**: Validates Kubernetes manifests against security and best practices
- **Checks**:
  - Security contexts
  - Resource limits and requests
  - Container image policies
  - Pod network policies
  - Probes (liveness/readiness)
  - Required labels and annotations

#### Kubeval Tests

- **File**: `kubeval.yaml`
- **Purpose**: Validates Kubernetes YAML syntax and API schema compliance
- **Features**:
  - Multi-manifest validation
  - Kubernetes version compatibility
  - Schema validation against official APIs
  - Custom Resource Definition support

#### Conftest/OPA Tests

Policy-as-Code validation using Open Policy Agent:

- **deployment.rego**: Deployment-specific policies

  - Resource requirements
  - Security contexts
  - Image policies
  - Probe requirements
  - Label compliance

- **security.rego**: Security-focused policies
  - Pod Security Standards
  - RBAC validation
  - Secret management
  - Network security
  - Image security

### 2. Integration Tests (`integration-tests/`)

#### API Integration Tests

- **File**: `listings-api-test.py`
- **Coverage**:
  - Health endpoints
  - CRUD operations
  - Search functionality
  - Input validation
  - Rate limiting
  - Database connectivity
  - Kubernetes integration
  - Concurrent request handling

#### Database Tests

- **File**: `db-connection-test.py`
- **Coverage**:
  - Connection pooling
  - CRUD operations
  - Transactions
  - Performance benchmarks
  - Schema validation
  - Backup readiness
  - Kubernetes integration

#### Ingress/Routing Tests

- **File**: `ingress-routing-test.py`
- **Coverage**:
  - Path-based routing
  - Load balancing
  - SSL/TLS configuration
  - CORS headers
  - Rate limiting
  - Error pages
  - Backend health

## Running Tests

### Prerequisites

```bash
# Install required packages
pip install -r requirements.txt

# Ensure kubectl access to cluster
kubectl get nodes
```

### Lint Tests

```bash
# Run kube-score tests
kubectl apply -f tests/k8s-lint-tests/kube-score.yaml

# Run kubeval tests
kubectl apply -f tests/k8s-lint-tests/kubeval.yaml

# Run conftest/OPA tests
conftest test manifests/ --policy tests/k8s-lint-tests/conftest/
```

### Integration Tests

```bash
# Set test environment
export TEST_NAMESPACE=kubeestatehub

# Run all integration tests
pytest tests/integration-tests/ -v

# Run specific test files
pytest tests/integration-tests/listings-api-test.py -v
pytest tests/integration-tests/db-connection-test.py -v
pytest tests/integration-tests/ingress-routing-test.py -v
```

### Test Configuration

#### Environment Variables

```bash
# Test configuration
export TEST_NAMESPACE=kubeestatehub
export INGRESS_URL=http://localhost:80
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=kubeestatehub
export DB_USER=postgres
export DB_PASSWORD=postgres123
```

#### Running in Different Environments

**Local Development:**

```bash
# Port forward services
kubectl port-forward svc/listings-api-service 8080:8080 -n kubeestatehub
kubectl port-forward svc/postgres-service 5432:5432 -n kubeestatehub

# Run tests
pytest tests/integration-tests/ -v
```

**In-Cluster Testing:**

```bash
# Create test job
apiVersion: batch/v1
kind: Job
metadata:
  name: integration-tests
spec:
  template:
    spec:
      containers:
      - name: pytest
        image: python:3.9
        command: ["pytest", "/tests/", "-v"]
        volumeMounts:
        - name: tests
          mountPath: /tests
```

## Test Reports

### Generating Reports

```bash
# Generate HTML report
pytest tests/ --html=reports/test-report.html --self-contained-html

# Generate JUnit XML
pytest tests/ --junitxml=reports/junit.xml

# Generate coverage report
pytest tests/ --cov=src --cov-report=html:reports/coverage
```

### Continuous Integration

```bash
# CI pipeline test command
pytest tests/ \
  --junitxml=reports/junit.xml \
  --html=reports/report.html \
  --cov=src \
  --cov-report=xml:reports/coverage.xml \
  --tb=short
```

## Test Data Management

### Database Test Data

- Tests create and clean up their own data
- Use transaction rollbacks where possible
- Isolated test namespaces for parallel execution

### Test Isolation

- Each test class uses separate resources
- Kubernetes objects have unique names
- Cleanup methods ensure resource removal

## Troubleshooting

### Common Issues

1. **Service Not Ready**

   ```bash
   kubectl get pods -n kubeestatehub
   kubectl logs -f deployment/listings-api -n kubeestatehub
   ```

2. **Database Connection Failed**

   ```bash
   kubectl get statefulset postgres -n kubeestatehub
   kubectl logs postgres-0 -n kubeestatehub
   ```

3. **Ingress Not Accessible**
   ```bash
   kubectl get ingress -n kubeestatehub
   kubectl describe ingress kubeestatehub-ingress -n kubeestatehub
   ```

### Test Debugging

```bash
# Run tests with debug output
pytest tests/ -v -s --tb=long

# Run single test with debugging
pytest tests/integration-tests/listings-api-test.py::TestListingsAPI::test_health_endpoint -v -s

# Check test environment
kubectl get all -n kubeestatehub
kubectl get configmaps,secrets -n kubeestatehub
```

## Performance Testing

### Load Testing

For performance testing, consider using:

- K6 for API load testing
- Artillery for comprehensive scenarios
- Kubernetes HPA testing with load

### Benchmarks

Current performance expectations:

- API response time: < 200ms
- Database queries: < 100ms
- Concurrent connections: 100+
- Ingress throughput: 1000+ req/s

## Security Testing

### Security Scans

- Container image vulnerability scanning
- Kubernetes security benchmarks
- RBAC validation
- Network policy testing

### Compliance

Tests verify compliance with:

- Pod Security Standards
- CIS Kubernetes Benchmarks
- OWASP security guidelines
- Industry best practices

## Contributing

### Adding New Tests

1. Follow existing test patterns
2. Include proper setup/teardown
3. Use descriptive test names
4. Add comprehensive assertions
5. Update this README

### Test Naming Convention

- Test files: `*-test.py`
- Test classes: `Test*`
- Test methods: `test_*`
- Policy files: `*.rego`

### Code Quality

- Use pytest fixtures for common setup
- Mock external dependencies appropriately
- Include error handling and timeouts
- Log relevant information for debugging
