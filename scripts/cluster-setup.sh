# Location: `/scripts/cluster-setup.sh`

#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="kubeestatehub"
KUBECTL_VERSION="v1.28.0"
HELM_VERSION="v3.12.0"

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  KubeEstateHub Cluster Setup   ${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    print_step "Checking prerequisites..."
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi
    
    # Check if helm is installed
    if ! command -v helm &> /dev/null; then
        print_error "helm is not installed"
        exit 1
    fi
    
    # Check if docker is running
    if ! docker info &> /dev/null; then
        print_error "Docker is not running"
        exit 1
    fi
    
    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    echo -e "${GREEN}✓${NC} All prerequisites met"
}

create_namespace() {
    print_step "Creating namespace: $NAMESPACE"
    
    if kubectl get namespace $NAMESPACE &> /dev/null; then
        print_warning "Namespace $NAMESPACE already exists"
    else
        kubectl create namespace $NAMESPACE
        echo -e "${GREEN}✓${NC} Namespace created"
    fi
    
    # Set as default namespace
    kubectl config set-context --current --namespace=$NAMESPACE
}

setup_rbac() {
    print_step "Setting up RBAC..."
    
    kubectl apply -f ../manifests/configs/service-accounts.yaml
    kubectl apply -f ../manifests/configs/rbac-admin.yaml
    kubectl apply -f ../manifests/configs/rbac-readonly.yaml
    
    echo -e "${GREEN}✓${NC} RBAC configured"
}

setup_storage() {
    print_step "Setting up storage..."
    
    kubectl apply -f ../manifests/storage/storage-class.yaml
    kubectl apply -f ../manifests/storage/db-persistent-volume.yaml
    kubectl apply -f ../manifests/storage/db-persistent-volume-claim.yaml
    kubectl apply -f ../manifests/storage/image-store-pv.yaml
    kubectl apply -f ../manifests/storage/image-store-pvc.yaml
    
    # Wait for PVCs to be bound
    echo "Waiting for PVCs to be bound..."
    kubectl wait --for=condition=Bound pvc/postgres-pvc --timeout=60s
    kubectl wait --for=condition=Bound pvc/image-store-pvc --timeout=60s
    
    echo -e "${GREEN}✓${NC} Storage configured"
}

setup_secrets_and_configs() {
    print_step "Setting up secrets and configmaps..."
    
    # Check if secrets exist, create if not
    if ! kubectl get secret db-secret &> /dev/null; then
        kubectl create secret generic db-secret \
            --from-literal=POSTGRES_USER=admin \
            --from-literal=POSTGRES_PASSWORD=secretpassword \
            --from-literal=POSTGRES_DB=kubeestatehub
    fi
    
    if ! kubectl get secret global-env-secret &> /dev/null; then
        kubectl create secret generic global-env-secret \
            --from-literal=REDIS_URL=redis://redis-service:6379/0 \
            --from-literal=DATABASE_URL=postgresql://admin:secretpassword@postgres-service:5432/kubeestatehub
    fi
    
    kubectl apply -f ../manifests/configs/listings-configmap.yaml
    kubectl apply -f ../manifests/configs/analytics-configmap.yaml
    kubectl apply -f ../manifests/configs/db-configmap.yaml
    kubectl apply -f ../manifests/configs/frontend-configmap.yaml
    
    echo -e "${GREEN}✓${NC} Secrets and ConfigMaps created"
}

deploy_database() {
    print_step "Deploying PostgreSQL database..."
    
    kubectl apply -f ../manifests/base/db-statefulset.yaml
    kubectl apply -f ../manifests/base/db-service.yaml
    
    # Wait for database to be ready
    echo "Waiting for database to be ready..."
    kubectl wait --for=condition=Ready pod/postgres-0 --timeout=300s
    
    echo -e "${GREEN}✓${NC} Database deployed and ready"
}

deploy_core_services() {
    print_step "Deploying core services..."
    
    # Deploy listings API
    kubectl apply -f ../manifests/base/listings-api-deployment.yaml
    kubectl apply -f ../manifests/base/listings-api-service.yaml
    
    # Deploy analytics worker
    kubectl apply -f ../manifests/base/analytics-worker-deployment.yaml
    kubectl apply -f ../manifests/base/analytics-worker-cronjob.yaml
    
    # Deploy frontend dashboard
    kubectl apply -f ../manifests/base/frontend-dashboard-deployment.yaml
    kubectl apply -f ../manifests/base/frontend-dashboard-service.yaml
    
    # Deploy image store
    kubectl apply -f ../manifests/base/image-store-deployment.yaml
    kubectl apply -f ../manifests/base/image-store-service.yaml
    
    echo "Waiting for services to be ready..."
    kubectl wait --for=condition=Available deployment/listings-api --timeout=300s
    kubectl wait --for=condition=Available deployment/frontend-dashboard --timeout=300s
    kubectl wait --for=condition=Available deployment/image-store --timeout=300s
    
    echo -e "${GREEN}✓${NC} Core services deployed"
}

setup_networking() {
    print_step "Setting up networking..."
    
    kubectl apply -f ../manifests/network/network-policy-frontend.yaml
    kubectl apply -f ../manifests/network/network-policy-db.yaml
    kubectl apply -f ../manifests/network/dns-configmap.yaml
    kubectl apply -f ../manifests/base/ingress.yaml
    
    echo -e "${GREEN}✓${NC} Networking configured"
}

setup_monitoring() {
    print_step "Setting up monitoring stack..."
    
    # Deploy Prometheus
    kubectl apply -f ../manifests/monitoring/prometheus-deployment.yaml
    kubectl apply -f ../manifests/monitoring/prometheus-service.yaml
    
    # Deploy Grafana
    kubectl apply -f ../manifests/monitoring/grafana-deployment.yaml
    kubectl apply -f ../manifests/monitoring/grafana-service.yaml
    kubectl apply -f ../manifests/monitoring/grafana-dashboard-configmap.yaml
    
    # Deploy ServiceMonitors
    kubectl apply -f ../manifests/monitoring/service-monitor-listings.yaml
    kubectl apply -f ../manifests/monitoring/alertmanager-config.yaml
    
    echo "Waiting for monitoring services..."
    kubectl wait --for=condition=Available deployment/prometheus --timeout=300s
    kubectl wait --for=condition=Available deployment/grafana --timeout=300s
    
    echo -e "${GREEN}✓${NC} Monitoring stack deployed"
}

setup_autoscaling() {
    print_step "Setting up autoscaling..."
    
    kubectl apply -f ../manifests/autoscaling/hpa-listings-api.yaml
    kubectl apply -f ../manifests/autoscaling/hpa-frontend-dashboard.yaml
    kubectl apply -f ../manifests/autoscaling/vpa-listings-api.yaml
    kubectl apply -f ../manifests/autoscaling/resource-quotas.yaml
    
    echo -e "${GREEN}✓${NC} Autoscaling configured"
}

setup_jobs() {
    print_step "Setting up jobs and cronjobs..."
    
    kubectl apply -f ../manifests/jobs/db-backup-cronjob.yaml
    kubectl apply -f ../manifests/jobs/image-cleanup-job.yaml
    
    echo -e "${GREEN}✓${NC} Jobs configured"
}

verify_deployment() {
    print_step "Verifying deployment..."
    
    echo "Checking pod status..."
    kubectl get pods -o wide
    
    echo ""
    echo "Checking services..."
    kubectl get services
    
    echo ""
    echo "Checking ingress..."
    kubectl get ingress
    
    echo ""
    echo "Checking PVCs..."
    kubectl get pvc
    
    # Check if all critical pods are running
    FAILED_PODS=$(kubectl get pods --field-selector=status.phase!=Running --no-headers 2>/dev/null | wc -l)
    
    if [ $FAILED_PODS -eq 0 ]; then
        echo -e "${GREEN}✓${NC} All pods are running successfully"
    else
        print_warning "$FAILED_PODS pods are not in Running state"
        kubectl get pods --field-selector=status.phase!=Running
    fi
}

print_access_info() {
    print_step "Access Information"
    
    echo ""
    echo "To access your KubeEstateHub application:"
    echo ""
    
    # Get ingress IP/hostname
    INGRESS_IP=$(kubectl get ingress kubeestatehub-ingress -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
    INGRESS_HOST=$(kubectl get ingress kubeestatehub-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")
    
    if [ "$INGRESS_IP" != "pending" ] && [ "$INGRESS_IP" != "" ]; then
        echo "🌐 Application URL: http://$INGRESS_IP"
    elif [ "$INGRESS_HOST" != "" ]; then
        echo "🌐 Application URL: http://$INGRESS_HOST"
    else
        echo "🔗 Use port-forwarding to access services:"
        echo "   kubectl port-forward svc/frontend-dashboard-service 3000:80"
        echo "   Then visit: http://localhost:3000"
    fi
    
    echo ""
    echo "📊 Grafana Dashboard:"
    echo "   kubectl port-forward svc/grafana-service 3001:3000"
    echo "   Then visit: http://localhost:3001 (admin/admin)"
    echo ""
    echo "📈 Prometheus:"
    echo "   kubectl port-forward svc/prometheus-service 9090:9090"
    echo "   Then visit: http://localhost:9090"
    echo ""
    echo "💾 Database Access:"
    echo "   kubectl port-forward svc/postgres-service 5432:5432"
    echo "   Connection: postgresql://admin:secretpassword@localhost:5432/kubeestatehub"
}

cleanup_on_error() {
    print_error "Setup failed. Cleaning up..."
    kubectl delete namespace $NAMESPACE --ignore-not-found=true
    exit 1
}

main() {
    trap cleanup_on_error ERR
    
    print_header
    
    check_prerequisites
    create_namespace
    setup_rbac
    setup_storage
    setup_secrets_and_configs
    deploy_database
    deploy_core_services
    setup_networking
    setup_monitoring
    setup_autoscaling
    setup_jobs
    verify_deployment
    print_access_info
    
    echo ""
    echo -e "${GREEN}🎉 KubeEstateHub cluster setup completed successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Run './port-forwarding.sh' to set up port forwards"
    echo "2. Run './grafana-dashboard-import.sh' to import Grafana dashboards"
    echo "3. Check the docs/ folder for guides and troubleshooting"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --skip-monitoring)
            SKIP_MONITORING=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -n, --namespace NAME    Set namespace (default: kubeestatehub)"
            echo "  --skip-monitoring       Skip monitoring stack deployment"
            echo "  --dry-run              Show what would be done without executing"
            echo "  -h, --help             Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main