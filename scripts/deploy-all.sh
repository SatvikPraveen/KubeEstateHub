# Location: `/scripts/deploy-all.sh`

#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
NAMESPACE="kubeestatehub"
ENVIRONMENT="development"
SKIP_BUILD=false
FORCE_RECREATE=false
TIMEOUT=300

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}   KubeEstateHub Deployment     ${NC}"
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

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -n, --namespace NAME       Set target namespace (default: kubeestatehub)"
    echo "  -e, --environment ENV      Set environment (development|staging|production)"
    echo "  -s, --skip-build          Skip Docker image builds"
    echo "  -f, --force-recreate      Force recreate all resources"
    echo "  -t, --timeout SECONDS     Set deployment timeout (default: 300)"
    echo "  --use-kustomize           Use Kustomize overlays for deployment"
    echo "  --use-helm                Use Helm charts for deployment"
    echo "  -h, --help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                              # Deploy to development"
    echo "  $0 -e production -n prod        # Deploy to production namespace"
    echo "  $0 --use-helm -e staging        # Deploy using Helm to staging"
    echo "  $0 --skip-build --force-recreate # Deploy without building images"
}

check_prerequisites() {
    print_step "Checking prerequisites..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi
    
    # Check Docker (if not skipping build)
    if [ "$SKIP_BUILD" = false ] && ! docker info &> /dev/null; then
        print_error "Docker is not running and build is required"
        exit 1
    fi
    
    # Check Helm (if using helm)
    if [ "$USE_HELM" = true ] && ! command -v helm &> /dev/null; then
        print_error "Helm is not installed but --use-helm was specified"
        exit 1
    fi
    
    # Check Kustomize (if using kustomize)
    if [ "$USE_KUSTOMIZE" = true ] && ! command -v kustomize &> /dev/null; then
        print_error "Kustomize is not installed but --use-kustomize was specified"
        exit 1
    fi
    
    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    echo -e "${GREEN}✓${NC} Prerequisites check passed"
}

build_images() {
    if [ "$SKIP_BUILD" = true ]; then
        print_warning "Skipping image builds as requested"
        return
    fi
    
    print_step "Building Docker images..."
    
    # Get the script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    SRC_DIR="$PROJECT_DIR/src"
    
    # Build listings API
    echo "Building listings-api..."
    docker build -t kubeestatehub/listings-api:latest "$SRC_DIR/listings-api"
    
    # Build analytics worker
    echo "Building analytics-worker..."
    docker build -t kubeestatehub/analytics-worker:latest "$SRC_DIR/analytics-worker"
    
    # Build frontend dashboard
    echo "Building frontend-dashboard..."
    docker build -t kubeestatehub/frontend-dashboard:latest "$SRC_DIR/frontend-dashboard"
    
    # Build metrics service
    echo "Building metrics-service..."
    docker build -t kubeestatehub/metrics-service:latest "$SRC_DIR/metrics-service"
    
    echo -e "${GREEN}✓${NC} All images built successfully"
}

prepare_namespace() {
    print_step "Preparing namespace: $NAMESPACE"
    
    if kubectl get namespace $NAMESPACE &> /dev/null; then
        if [ "$FORCE_RECREATE" = true ]; then
            print_warning "Force recreate enabled - deleting existing namespace"
            kubectl delete namespace $NAMESPACE
            sleep 5
        else
            print_warning "Namespace $NAMESPACE already exists"
        fi
    fi
    
    if ! kubectl get namespace $NAMESPACE &> /dev/null; then
        kubectl create namespace $NAMESPACE
    fi
    
    # Set context
    kubectl config set-context --current --namespace=$NAMESPACE
    echo -e "${GREEN}✓${NC} Namespace prepared"
}

deploy_with_manifests() {
    print_step "Deploying with raw manifests..."
    
    # Get the script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    MANIFESTS_DIR="$PROJECT_DIR/manifests"
    
    # Apply in order for dependencies
    kubectl apply -f "$MANIFESTS_DIR/storage/"
    kubectl apply -f "$MANIFESTS_DIR/configs/db-configmap.yaml"
    kubectl apply -f "$MANIFESTS_DIR/configs/db-secret.yaml"
    kubectl apply -f "$MANIFESTS_DIR/configs/global-env-secret.yaml"
    kubectl apply -f "$MANIFESTS_DIR/base/namespace.yaml"
    kubectl apply -f "$MANIFESTS_DIR/base/db-statefulset.yaml"
    kubectl apply -f "$MANIFESTS_DIR/base/db-service.yaml"
    kubectl apply -f "$MANIFESTS_DIR/base/postgresql-db-headless-service.yaml"
    
    # Wait for database
    echo "Waiting for database to be ready..."
    kubectl wait --for=condition=Ready pod/postgresql-db-0 --timeout=${TIMEOUT}s -n $NAMESPACE || true
    
    # Run database initialization
    echo "Initializing database schema..."
    kubectl apply -f "$MANIFESTS_DIR/jobs/db-init-job.yaml"
    kubectl wait --for=condition=complete job/db-init --timeout=${TIMEOUT}s -n $NAMESPACE || true
    
    # Deploy application services
    kubectl apply -f "$MANIFESTS_DIR/base/listings-api-deployment.yaml"
    kubectl apply -f "$MANIFESTS_DIR/base/listings-api-service.yaml"
    kubectl apply -f "$MANIFESTS_DIR/base/analytics-worker-deployment.yaml"
    kubectl apply -f "$MANIFESTS_DIR/base/analytics-worker-cronjob.yaml"
    kubectl apply -f "$MANIFESTS_DIR/base/frontend-dashboard-deployment.yaml"
    kubectl apply -f "$MANIFESTS_DIR/base/frontend-dashboard-service.yaml"
    kubectl apply -f "$MANIFESTS_DIR/base/image-store-deployment.yaml"
    kubectl apply -f "$MANIFESTS_DIR/base/image-store-service.yaml"
    
    # Apply networking
    kubectl apply -f "$MANIFESTS_DIR/network/"
    kubectl apply -f "$MANIFESTS_DIR/base/ingress.yaml"
    
    # Apply monitoring
    kubectl apply -f "$MANIFESTS_DIR/monitoring/" || true
    
    # Apply autoscaling
    kubectl apply -f "$MANIFESTS_DIR/autoscaling/" || true
    
    # Apply jobs
    kubectl apply -f "$MANIFESTS_DIR/jobs/" || true
}

deploy_with_kustomize() {
    print_step "Deploying with Kustomize..."
    
    # Get the script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    KUSTOMIZE_DIR="$PROJECT_DIR/kustomize/overlays/$ENVIRONMENT"
    
    kubectl apply -k "$KUSTOMIZE_DIR"
}

deploy_with_helm() {
    print_step "Deploying with Helm..."
    
    # Get the script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    HELM_CHART_DIR="$PROJECT_DIR/helm-charts/kubeestatehub"
    
    # Add dependencies if needed
    helm dependency update "$HELM_CHART_DIR/"
    
    # Install or upgrade
    if helm list -n $NAMESPACE | grep -q kubeestatehub; then
        print_warning "Existing Helm release found, upgrading..."
        helm upgrade kubeestatehub "$HELM_CHART_DIR/" \
            --namespace $NAMESPACE \
            --values "$HELM_CHART_DIR/values-$ENVIRONMENT.yaml" \
            --timeout ${TIMEOUT}s \
            --wait
    else
        helm install kubeestatehub "$HELM_CHART_DIR/" \
            --namespace $NAMESPACE \
            --values "$HELM_CHART_DIR/values-$ENVIRONMENT.yaml" \
            --timeout ${TIMEOUT}s \
            --wait \
            --create-namespace
    fi
}

wait_for_deployments() {
    print_step "Waiting for deployments to be ready..."
    
    local deployments=(
        "listings-api"
        "frontend-dashboard" 
        "image-store"
        "prometheus"
        "grafana"
    )
    
    for deployment in "${deployments[@]}"; do
        echo "Waiting for deployment/$deployment..."
        if kubectl get deployment $deployment &> /dev/null; then
            kubectl wait --for=condition=Available deployment/$deployment --timeout=${TIMEOUT}s
        else
            print_warning "Deployment $deployment not found, skipping wait"
        fi
    done
    
    echo -e "${GREEN}✓${NC} All deployments are ready"
}

run_post_deployment_tests() {
    print_step "Running post-deployment tests..."
    
    # Wait a bit for services to stabilize
    sleep 10
    
    # Test database connectivity
    echo "Testing database connectivity..."
    kubectl exec -it postgres-0 -- psql -U admin -d kubeestatehub -c "SELECT version();" > /dev/null
    
    # Test API endpoints
    echo "Testing API endpoints..."
    API_POD=$(kubectl get pod -l app=listings-api -o jsonpath='{.items[0].metadata.name}')
    kubectl exec $API_POD -- wget -q --spider http://localhost:8080/health
    
    # Test frontend
    echo "Testing frontend..."
    FRONTEND_POD=$(kubectl get pod -l app=frontend-dashboard -o jsonpath='{.items[0].metadata.name}')
    kubectl exec $FRONTEND_POD -- wget -q --spider http://localhost:80/
    
    echo -e "${GREEN}✓${NC} Post-deployment tests passed"
}

verify_deployment() {
    print_step "Verifying deployment..."
    
    echo ""
    echo "=== Pods ==="
    kubectl get pods -o wide
    
    echo ""
    echo "=== Services ==="
    kubectl get services
    
    echo ""
    echo "=== Ingress ==="
    kubectl get ingress
    
    echo ""
    echo "=== PVCs ==="
    kubectl get pvc
    
    echo ""
    echo "=== ConfigMaps ==="
    kubectl get configmaps
    
    echo ""
    echo "=== Secrets ==="
    kubectl get secrets
    
    # Check for any failed pods
    FAILED_PODS=$(kubectl get pods --field-selector=status.phase!=Running --no-headers 2>/dev/null | wc -l)
    
    if [ $FAILED_PODS -eq 0 ]; then
        echo -e "${GREEN}✓${NC} All pods are running successfully"
    else
        print_warning "$FAILED_PODS pods are not in Running state"
        kubectl get pods --field-selector=status.phase!=Running
        
        # Show logs for failed pods
        kubectl get pods --field-selector=status.phase!=Running --no-headers | while read pod rest; do
            echo ""
            echo "=== Logs for failed pod: $pod ==="
            kubectl logs $pod --tail=20 || true
        done
    fi
}

show_access_info() {
    print_step "Access Information"
    
    echo ""
    echo "🎉 Deployment completed successfully!"
    echo ""
    
    # Get service endpoints
    echo "📱 Application Services:"
    
    # Frontend
    if kubectl get svc frontend-dashboard-service -n $NAMESPACE &> /dev/null; then
        FRONTEND_PORT=$(kubectl get svc frontend-dashboard-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].port}')
        echo "  Frontend: kubectl port-forward svc/frontend-dashboard-service -n $NAMESPACE 3000:$FRONTEND_PORT"
    fi
    
    # API
    if kubectl get svc listings-api-service -n $NAMESPACE &> /dev/null; then
        API_PORT=$(kubectl get svc listings-api-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].port}')
        echo "  API: kubectl port-forward svc/listings-api-service -n $NAMESPACE 8080:$API_PORT"
    fi
    
    # Database
    if kubectl get svc postgresql-db -n $NAMESPACE &> /dev/null; then
        DB_PORT=$(kubectl get svc postgresql-db -n $NAMESPACE -o jsonpath='{.spec.ports[0].port}')
        echo "  Database: kubectl port-forward svc/postgresql-db -n $NAMESPACE 5432:$DB_PORT"
    fi
    
    echo ""
    echo "📊 Monitoring:"
    
    # Grafana
    if kubectl get svc grafana-service -n $NAMESPACE &> /dev/null; then
        GRAFANA_PORT=$(kubectl get svc grafana-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || echo "3000")
        echo "  Grafana: kubectl port-forward svc/grafana-service -n $NAMESPACE 3001:$GRAFANA_PORT"
    fi
    
    # Prometheus
    if kubectl get svc prometheus-service -n $NAMESPACE &> /dev/null; then
        PROMETHEUS_PORT=$(kubectl get svc prometheus-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || echo "9090")
        echo "  Prometheus: kubectl port-forward svc/prometheus-service -n $NAMESPACE 9090:$PROMETHEUS_PORT"
    fi
    
    # Check ingress
    echo ""
    if kubectl get ingress kubeestatehub-ingress -n $NAMESPACE &> /dev/null; then
        INGRESS_IP=$(kubectl get ingress kubeestatehub-ingress -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
        if [ "$INGRESS_IP" != "pending" ] && [ "$INGRESS_IP" != "" ]; then
            echo "🌐 External Access: http://$INGRESS_IP"
        else
            echo "⏳ External IP is pending, check ingress status"
        fi
    fi
    
    echo ""
    echo "🚀 Quick Start Commands:"
    echo "  kubectl get pods -n $NAMESPACE            # Check pod status"
    echo "  kubectl logs -n $NAMESPACE -l app=listings-api  # View logs"
}

cleanup_on_failure() {
    print_error "Deployment failed!"
    echo ""
    echo "Troubleshooting steps:"
    echo "1. Check pod logs: kubectl logs <pod-name>"
    echo "2. Check events: kubectl get events --sort-by=.metadata.creationTimestamp"
    echo "3. Check resource usage: kubectl top pods"
    echo "4. Verify configurations: kubectl describe deployment <deployment-name>"
    echo ""
    echo "To clean up: ./teardown-all.sh"
}

main() {
    trap cleanup_on_failure ERR
    
    print_header
    
    check_prerequisites
    build_images
    prepare_namespace
    
    # Choose deployment method
    if [ "$USE_HELM" = true ]; then
        deploy_with_helm
    elif [ "$USE_KUSTOMIZE" = true ]; then
        deploy_with_kustomize
    else
        deploy_with_manifests
    fi
    
    wait_for_deployments
    run_post_deployment_tests
    verify_deployment
    show_access_info
    
    echo -e "${GREEN}✅ KubeEstateHub deployed successfully!${NC}"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -s|--skip-build)
            SKIP_BUILD=true
            shift
            ;;
        -f|--force-recreate)
            FORCE_RECREATE=true
            shift
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --use-kustomize)
            USE_KUSTOMIZE=true
            shift
            ;;
        --use-helm)
            USE_HELM=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(development|staging|production)$ ]]; then
    print_error "Invalid environment: $ENVIRONMENT. Must be development, staging, or production"
    exit 1
fi

# Run main function
main