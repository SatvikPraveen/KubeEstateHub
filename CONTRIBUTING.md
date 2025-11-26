# Contributing to KubeEstateHub

Thank you for your interest in contributing to KubeEstateHub! This document provides guidelines and instructions for contributing to the project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Documentation](#documentation)
- [Issue Reporting](#issue-reporting)
- [Project Structure](#project-structure)
- [Contact](#contact)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors. We pledge to:

- Be respectful and professional in all interactions
- Welcome contributors of all experience levels
- Provide constructive feedback
- Focus on the work, not the person

### Expected Behavior

- Use welcoming and inclusive language
- Be respectful of differing opinions and experiences
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards other community members

### Unacceptable Behavior

- Harassment or discrimination of any kind
- Trolling, insulting/derogatory comments
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

---

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Git** installed (v2.30+)
- **Kubernetes** knowledge (basic understanding recommended)
- **Docker** (for building images)
- **kubectl** (v1.28+)
- **Helm** (v3.0+) - optional but recommended
- **Python 3.8+** (for services)

### Fork & Clone

1. **Fork the repository** on GitHub
   ```bash
   Click "Fork" button on https://github.com/SatvikPraveen/KubeEstateHub
   ```

2. **Clone your fork locally**
   ```bash
   git clone https://github.com/YOUR-USERNAME/KubeEstateHub.git
   cd KubeEstateHub
   ```

3. **Add upstream remote**
   ```bash
   git remote add upstream https://github.com/SatvikPraveen/KubeEstateHub.git
   ```

---

## Development Setup

### 1. Set Up Local Environment

```bash
# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt
```

### 2. Set Up Local Kubernetes (if needed)

```bash
# Using Docker Desktop, minikube, or kind
# Example with kind:
kind create cluster --name kubeestatehub-dev

# Or use minikube:
minikube start --cpus=4 --memory=8192
```

### 3. Deploy Locally

```bash
# Using provided scripts
chmod +x scripts/deploy-all.sh
./scripts/deploy-all.sh -e development

# Or with kubectl directly
kubectl apply -k kustomize/overlays/development/
```

### 4. Verify Setup

```bash
# Check all pods are running
kubectl get pods -n kubeestatehub

# Port forward to test services
kubectl port-forward svc/listings-api-service 8080:8080 -n kubeestatehub
kubectl port-forward svc/frontend-dashboard-service 3000:80 -n kubeestatehub
```

---

## Making Changes

### Branch Naming Convention

Create branches with descriptive names following this pattern:

```
feature/description          # New feature
fix/description             # Bug fix
docs/description            # Documentation
test/description            # Tests
refactor/description        # Code refactoring
security/description        # Security improvements
perf/description            # Performance improvements
chore/description           # Maintenance tasks
```

### Examples

```bash
git checkout -b feature/add-pagination-listings-api
git checkout -b fix/database-connection-timeout
git checkout -b docs/update-deployment-guide
git checkout -b test/add-health-check-tests
```

### Code Style Guidelines

#### Python (Flask Services)

- Follow **PEP 8** style guide
- Use type hints where applicable
- Maximum line length: 100 characters
- Use meaningful variable names

```python
# Good
def get_property_by_id(property_id: int) -> dict:
    """Fetch property details by ID."""
    property_data = database.query(property_id)
    return property_data

# Avoid
def get(id):
    d = db.q(id)
    return d
```

#### YAML (Kubernetes Manifests)

- Use 2-space indentation
- Use meaningful names for resources
- Include labels and annotations
- Specify resource limits

```yaml
# Good
apiVersion: apps/v1
kind: Deployment
metadata:
  name: listings-api
  labels:
    app: listings-api
    version: v1
spec:
  replicas: 3
  resources:
    requests:
      memory: "256Mi"
      cpu: "250m"
    limits:
      memory: "512Mi"
      cpu: "500m"
```

#### Helm Charts

- Use descriptive comments
- Validate with `helm lint`
- Keep values organized
- Document configuration options

#### Shell Scripts

- Start with shebang: `#!/bin/bash`
- Set error handling: `set -euo pipefail`
- Use meaningful variable names
- Add comments for complex logic

```bash
#!/bin/bash
set -euo pipefail

# Description of what the script does
NAMESPACE="${NAMESPACE:-kubeestatehub}"
TIMEOUT="${TIMEOUT:-300}"

main() {
    echo "Starting deployment..."
    # Implementation
}

main "$@"
```

### File Organization

```
src/
├── listings-api/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/

manifests/
├── base/
│   ├── listings-api-deployment.yaml
│   ├── listings-api-service.yaml
│   └── kustomization.yaml

docs/
├── guides/
└── (other documentation)

scripts/
├── deploy-all.sh
└── (utility scripts)
```

---

## Commit Guidelines

### Commit Message Format

Follow the conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type

Must be one of:
- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that don't affect code meaning
- **refactor**: Code change without feature or bug fix
- **perf**: Performance improvement
- **test**: Adding or updating tests
- **chore**: Build process, dependencies, etc.
- **ci**: CI/CD workflow changes
- **security**: Security-related changes

### Scope

Specify the area affected:
- `listings-api`, `analytics-worker`, `frontend-dashboard`, `metrics-service`
- `manifests`, `helm-charts`, `kustomize`
- `scripts`, `docs`, `tests`
- `github-actions`

### Examples

```bash
git commit -m "feat(listings-api): Add pagination support for property listings"
git commit -m "fix(manifests): Correct resource limits in deployment spec"
git commit -m "docs(github-actions): Add workflow debugging guide"
git commit -m "test(listings-api): Add integration tests for health endpoint"
git commit -m "ci(github-actions): Improve CodeQL upload error handling"
```

### Good Commit Messages

- ✅ Descriptive and specific
- ✅ Reference related issues: `Fixes #123`
- ✅ Keep subject line under 50 characters
- ✅ Provide context in the body

---

## Pull Request Process

### Before Creating a PR

1. **Sync with upstream**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run tests locally**
   ```bash
   # Run all tests
   pytest tests/

   # Or specific test
   pytest tests/test_listings_api.py
   ```

3. **Check linting**
   ```bash
   # Python
   pylint src/
   flake8 src/
   
   # YAML
   yamllint manifests/
   ```

4. **Validate Kubernetes manifests**
   ```bash
   # Dry-run validation
   kubectl apply -k kustomize/overlays/development/ --dry-run=client
   
   # Helm validation
   helm lint helm-charts/kubeestatehub/
   ```

### Creating a PR

1. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open PR on GitHub**
   - Use descriptive title
   - Reference related issues
   - Provide clear description
   - Include screenshots for UI changes

### PR Description Template

```markdown
## Description
Brief description of changes.

## Related Issues
Fixes #123
Related to #456

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Configuration change

## Testing
Describe testing performed:
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally
- [ ] Manifests validated
```

### Review Process

1. **Automated Checks**
   - GitHub Actions workflows run automatically
   - Security scans are performed
   - Tests must pass

2. **Code Review**
   - At least one maintainer review required
   - Address review comments
   - Push changes to same branch

3. **Merge**
   - After approval, PR can be merged
   - Use "Squash and merge" for single commits
   - Ensure branch is up-to-date with main

---

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_listings_api.py

# Run with coverage
pytest --cov=src tests/

# Run specific test
pytest tests/test_listings_api.py::test_get_listings
```

### Integration Tests

```bash
# Deploy to test namespace
kubectl create namespace test
kubectl apply -k kustomize/overlays/development/ -n test

# Run integration tests
pytest tests/integration-tests/

# Cleanup
kubectl delete namespace test
```

### Kubernetes Manifest Validation

```bash
# Dry-run validation
kubectl apply -k kustomize/overlays/development/ --dry-run=client

# Validate specific manifest
kubectl apply -f manifests/base/listings-api-deployment.yaml --dry-run=client

# Check helm chart
helm lint helm-charts/kubeestatehub/
helm template kubeestatehub helm-charts/kubeestatehub/
```

### Docker Image Tests

```bash
# Build image
docker build -t listings-api:test ./src/listings-api

# Run container tests
docker run --rm -v $(pwd):/app listings-api:test pytest tests/
```

---

## Documentation

### Documentation Structure

Documentation is organized in `docs/` with subdirectories:

- `docs/getting-started/` - Quick start guides
- `docs/guides/` - Advanced topics
- `docs/github-actions/` - CI/CD documentation
- `docs/internal/` - Development documentation

### Adding Documentation

1. **Place in appropriate subdirectory**
2. **Use clear, descriptive titles**
3. **Include code examples**
4. **Add to docs/INDEX.md**
5. **Link from README.md if relevant**

### Documentation Standards

- Use markdown format
- Include table of contents for long documents
- Add code blocks with language specification
- Include diagrams where helpful
- Keep language clear and concise
- Proofread before committing

### Example Documentation File

```markdown
# Feature Title

Brief description of the feature.

## Table of Contents
- [Overview](#overview)
- [Setup](#setup)
- [Usage](#usage)

## Overview
Detailed explanation...

## Setup
Step-by-step setup instructions...

## Usage
Code examples and usage...

## Troubleshooting
Common issues and solutions...

## See Also
- [Related Guide](related-guide.md)
```

---

## Issue Reporting

### Before Creating an Issue

- Check existing issues (open and closed)
- Search documentation
- Try latest version
- Gather relevant information

### Issue Template

**Title:** Clear, descriptive title

**Description:**
```markdown
## Description
What is the issue?

## Steps to Reproduce
1. Step 1
2. Step 2
3. Step 3

## Expected Behavior
What should happen?

## Actual Behavior
What actually happens?

## Environment
- OS: 
- Kubernetes version:
- kubectl version:
- Docker version:

## Logs/Errors
Relevant log output or error messages

## Additional Context
Any other relevant information
```

### Issue Labels

- `bug` - Something isn't working
- `feature` - Feature request
- `documentation` - Documentation issue
- `question` - Question or discussion
- `good first issue` - Good for new contributors
- `help wanted` - Need assistance
- `security` - Security-related

---

## Project Structure

### Key Directories

```
KubeEstateHub/
├── src/                    # Application source code
│   ├── listings-api/       # Main API service
│   ├── analytics-worker/   # Background jobs
│   ├── frontend-dashboard/ # Web UI
│   └── metrics-service/    # Metrics exporter
│
├── manifests/              # Kubernetes resources
│   ├── base/              # Core components
│   ├── configs/           # ConfigMaps & Secrets
│   ├── security/          # RBAC & Policies
│   └── monitoring/        # Prometheus & Grafana
│
├── kustomize/             # Kustomize overlays
│   └── overlays/
│       ├── development/
│       ├── staging/
│       └── production/
│
├── helm-charts/           # Helm packages
│   └── kubeestatehub/
│
├── scripts/               # Automation scripts
├── tests/                 # Test suites
├── docs/                  # Documentation
└── .github/workflows/     # GitHub Actions
```

### Adding New Features

1. **Create feature branch**
   ```bash
   git checkout -b feature/new-feature
   ```

2. **Implement feature**
   - Add code to appropriate service
   - Add tests
   - Update manifests if needed

3. **Update documentation**
   - Add to relevant docs
   - Update README if needed
   - Include examples

4. **Create PR**
   - Reference related issues
   - Provide clear description
   - Ensure tests pass

---

## Contact

### Getting Help

- **Questions:** Check [FAQ](docs/faq.md)
- **Documentation:** See [docs/INDEX.md](docs/INDEX.md)
- **Issues:** Open a GitHub issue
- **Security:** Email security concerns (do not open public issue)

### Communication Channels

- **GitHub Issues** - Bug reports and feature requests
- **GitHub Discussions** - Questions and ideas
- **Pull Requests** - Code contributions

---

## Additional Resources

- [Project README](README.md)
- [Documentation Index](docs/INDEX.md)
- [Quick Start Guide](docs/getting-started/QUICKSTART.md)
- [Architecture Overview](docs/architecture-overview.md)
- [Security Best Practices](docs/security-best-practices.md)
- [GitHub Actions Guide](docs/github-actions/GITHUB_ACTIONS_QUICK_FIX.md)

---

## License

By contributing to KubeEstateHub, you agree that your contributions will be licensed under its MIT License.

---

## Acknowledgments

Thank you for contributing to KubeEstateHub! Your help makes this project better.

---

**Last Updated:** November 26, 2025
