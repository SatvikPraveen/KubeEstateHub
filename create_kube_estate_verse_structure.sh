#!/bin/bash

# KubeEstateHub - Complete Project Structure Setup Script
# This script creates the entire project structure with all Tier 1 additions

set -e  # Exit on any error

PROJECT_NAME="kubeestatehub"
echo "🏗️  Creating KubeEstateHub project structure..."

# Create main project directory
mkdir -p "$PROJECT_NAME"
cd "$PROJECT_NAME"

# Create root files
echo "📄 Creating root files..."
touch README.md LICENSE .gitignore .kubeignore .dockerignore

# Create CI/CD structure (.github)
echo "🚀 Creating CI/CD structure..."
mkdir -p .github/workflows
touch .github/workflows/k8s-deploy.yaml
touch .github/workflows/security-scan.yaml
touch .github/workflows/manifest-validation.yaml

# Create manifests structure
echo "📋 Creating manifests structure..."
mkdir -p manifests/{base,storage,configs,network,security,daemonsets,monitoring,autoscaling,operators,jobs}

# Base manifests
echo "🔧 Creating base manifests..."
cd manifests/base
touch listings-api-deployment.yaml
touch listings-api-service.yaml
touch analytics-worker-deployment.yaml
touch analytics-worker-cronjob.yaml
touch frontend-dashboard-deployment.yaml
touch frontend-dashboard-service.yaml
touch db-statefulset.yaml
touch db-service.yaml
touch image-store-deployment.yaml
touch image-store-service.yaml
touch ingress.yaml
touch namespace.yaml
cd ../..

# Storage manifests
echo "💾 Creating storage manifests..."
cd manifests/storage
touch storage-class.yaml
touch db-persistent-volume.yaml
touch db-persistent-volume-claim.yaml
touch image-store-pv.yaml
touch image-store-pvc.yaml
cd ../..

# Config manifests
echo "⚙️  Creating config manifests..."
cd manifests/configs
touch listings-configmap.yaml
touch analytics-configmap.yaml
touch db-configmap.yaml
touch frontend-configmap.yaml
touch global-env-secret.yaml
touch db-secret.yaml
touch rbac-admin.yaml
touch rbac-readonly.yaml
touch service-accounts.yaml
cd ../..

# Network manifests
echo "🌐 Creating network manifests..."
cd manifests/network
touch ingress-controller.yaml
touch network-policy-frontend.yaml
touch network-policy-db.yaml
touch dns-configmap.yaml
cd ../..

# Security manifests (NEW - Tier 1)
echo "🔒 Creating security manifests..."
cd manifests/security
touch pod-security-policy.yaml
touch pod-security-standards.yaml
touch security-contexts.yaml
touch admission-controllers.yaml
cd ../..

# DaemonSets (NEW - Tier 1)
echo "⚙️  Creating daemonset manifests..."
cd manifests/daemonsets
touch log-collector-daemonset.yaml
touch node-exporter-daemonset.yaml
touch security-scanner-daemonset.yaml
cd ../..

# Monitoring manifests
echo "📊 Creating monitoring manifests..."
cd manifests/monitoring
touch prometheus-deployment.yaml
touch prometheus-service.yaml
touch grafana-deployment.yaml
touch grafana-service.yaml
touch grafana-dashboard-configmap.yaml
touch service-monitor-listings.yaml
touch alertmanager-config.yaml
cd ../..

# Autoscaling manifests
echo "📈 Creating autoscaling manifests..."
cd manifests/autoscaling
touch hpa-listings-api.yaml
touch hpa-frontend-dashboard.yaml
touch vpa-listings-api.yaml
touch cluster-autoscaler.yaml
touch resource-quotas.yaml
cd ../..

# Operators manifests
echo "🤖 Creating operators manifests..."
cd manifests/operators
touch realestate-sync-crd.yaml
touch realestate-sync-cr.yaml
touch realestate-sync-operator-deployment.yaml
touch operator-rbac.yaml
cd ../..

# Jobs manifests
echo "⏰ Creating jobs manifests..."
cd manifests/jobs
touch db-backup-cronjob.yaml
touch image-cleanup-job.yaml
touch db-migration-job.yaml
cd ../..

# Create Kustomize structure (NEW - Tier 1)
echo "🔄 Creating kustomize structure..."
mkdir -p kustomize/{base,overlays/{development,staging,production}}
touch kustomize/base/kustomization.yaml
touch kustomize/overlays/development/kustomization.yaml
touch kustomize/overlays/staging/kustomization.yaml
touch kustomize/overlays/production/kustomization.yaml
touch kustomize/README.md

# Create Helm charts structure
echo "⛵ Creating helm charts structure..."
mkdir -p helm-charts/kubeestatehub/{templates,charts}
cd helm-charts/kubeestatehub
touch Chart.yaml values.yaml
cd templates
touch deployments.yaml services.yaml ingress.yaml configmaps.yaml secrets.yaml hpa.yaml pvc.yaml prometheus.yaml grafana.yaml
cd ../../..
touch helm-charts/README.md

# Create source code structure
echo "💻 Creating source code structure..."
mkdir -p src/{listings-api,analytics-worker,frontend-dashboard,metrics-service}

cd src/listings-api
touch app.py requirements.txt Dockerfile k8s_health.py README.md
cd ../..

cd src/analytics-worker
touch worker.py requirements.txt Dockerfile README.md
cd ../..

cd src/frontend-dashboard
touch index.html app.js styles.css Dockerfile README.md
cd ../..

cd src/metrics-service
touch metrics_exporter.py requirements.txt Dockerfile README.md
cd ../..

# Create scripts
echo "📜 Creating scripts..."
mkdir -p scripts
cd scripts
touch cluster-setup.sh deploy-all.sh teardown-all.sh kubectl-aliases.sh port-forwarding.sh backup-db.sh grafana-dashboard-import.sh
cd ..

# Make scripts executable
chmod +x scripts/*.sh

# Create documentation
echo "📚 Creating documentation..."
mkdir -p docs
cd docs
touch architecture-diagram.svg architecture-overview.md kubectl-cheatsheet.md debugging-guide.md scaling-guide.md storage-deep-dive.md operators-guide.md monitoring-guide.md security-best-practices.md gitops-with-argocd.md faq.md
cd ..

# Create tests structure
echo "🧪 Creating tests structure..."
mkdir -p tests/{k8s-lint-tests/conftest,integration-tests}

cd tests/k8s-lint-tests
touch kube-score.yaml kubeval.yaml
cd conftest
touch deployment.rego security.rego
cd ../../..

cd tests/integration-tests
touch listings-api-test.py db-connection-test.py ingress-routing-test.py
cd ../..

touch tests/README.md

# Create basic .gitignore content
echo "📝 Creating .gitignore content..."
cat > .gitignore << 'EOF'
# Dependencies
node_modules/
__pycache__/
*.pyc
venv/
.env

# Build artifacts
*.log
dist/
build/

# IDE files
.vscode/
.idea/
*.swp
*.swo

# OS files
.DS_Store
Thumbs.db

# Kubernetes secrets (local development)
*-secret.yaml
*.key
*.crt

# Helm
*.tgz
charts/

# Temporary files
*.tmp
*.temp
EOF

# Create basic .kubeignore content
echo "📝 Creating .kubeignore content..."
cat > .kubeignore << 'EOF'
# Development files
README.md
.git/
.github/
docs/
tests/
scripts/

# Build artifacts
Dockerfile
requirements.txt
*.log

# IDE files
.vscode/
.idea/
EOF

# Create basic .dockerignore content
echo "📝 Creating .dockerignore content..."
cat > .dockerignore << 'EOF'
.git
.github
README.md
LICENSE
docs/
tests/
scripts/
helm-charts/
kustomize/
manifests/
*.md
.DS_Store
EOF

# Create basic README.md content
echo "📝 Creating README.md content..."
cat > README.md << 'EOF'
# KubeEstateHub 🏡

*"A One‑Stop Kubernetes Mastery Hub — From Pods to Operators"*

## 🎯 Project Overview

KubeEstateHub is a comprehensive Kubernetes learning project that covers **every major K8s concept** through a realistic real-estate microservices application. This project serves as both a hands-on playground and a complete reference hub for mastering Kubernetes.

## 🏗️ Architecture

- **4 Microservices**: Listings API, Analytics Worker, Frontend Dashboard, Metrics Service
- **Full Monitoring Stack**: Prometheus, Grafana, AlertManager
- **Custom Operator**: Real-estate data synchronization with CRDs
- **Multi-Environment**: Development, Staging, Production configurations
- **Security-First**: Pod Security Standards, RBAC, Network Policies
- **Production-Ready**: Autoscaling, Storage, Networking, CI/CD

## 🚀 Quick Start

```bash
# Setup cluster
./scripts/cluster-setup.sh

# Deploy all components
./scripts/deploy-all.sh

# Access dashboard
kubectl port-forward svc/frontend-dashboard 8080:80
```

## 📚 Learning Objectives

This project demonstrates mastery of:

- Core Resources (Pods, Deployments, Services, ConfigMaps)
- Storage Management (PVs, PVCs, StatefulSets)
- Networking (Ingress, NetworkPolicies, DNS)
- Security (RBAC, PSP, Admission Controllers)
- Monitoring & Observability (Prometheus, Grafana)
- Autoscaling (HPA, VPA, Cluster Autoscaler)
- Custom Resources & Operators
- GitOps & CI/CD Integration

## 🗂️ Project Structure

See [Architecture Overview](docs/architecture-overview.md) for detailed component descriptions.

## 📖 Documentation

- [kubectl Cheatsheet](docs/kubectl-cheatsheet.md)
- [Debugging Guide](docs/debugging-guide.md)
- [Security Best Practices](docs/security-best-practices.md)
- [Monitoring Guide](docs/monitoring-guide.md)

## 🤝 Contributing

This project is designed for learning. Feel free to experiment, modify, and extend!

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.
EOF

# Final summary
echo ""
echo "✅ KubeEstateHub project structure created successfully!"
echo ""
echo "📊 Project Statistics:"
echo "   • Total directories: $(find . -type d | wc -l)"
echo "   • Total files: $(find . -type f | wc -l)"
echo ""
echo "🎯 Next Steps:"
echo "   1. cd $PROJECT_NAME"
echo "   2. Initialize git: git init"
echo "   3. Start implementing manifests in manifests/ directory"
echo "   4. Review docs/ for implementation guidance"
echo ""
echo "🏗️  Project structure is now ready for Kubernetes mastery!"
echo ""
echo "Structure created:"
echo "📁 kubeestatehub/"
echo "├── 🚀 .github/workflows/ (CI/CD)"
echo "├── 📋 manifests/ (K8s resources)"
echo "│   ├── base/ (core workloads)"
echo "│   ├── security/ (PSP, contexts) 🆕"
echo "│   ├── daemonsets/ (system services) 🆕"
echo "│   └── monitoring/ (observability)"
echo "├── 🔄 kustomize/ (environment management) 🆕"
echo "├── ⛵ helm-charts/ (packaging)"
echo "├── 💻 src/ (application code)"
echo "├── 📜 scripts/ (automation)"
echo "├── 📚 docs/ (documentation)"
echo "└── 🧪 tests/ (validation)"