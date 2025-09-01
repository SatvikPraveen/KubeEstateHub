# Location: `/scripts/teardown-all.sh`

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
FORCE=false
KEEP_PVS=false
KEEP_IMAGES=false
CLEANUP_CRDS=false

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}     KubeEstateHub Teardown     ${NC}"
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
    echo "  -n, --namespace NAME      Target namespace to teardown (default: kubeestatehub)"
    echo "  -f, --force              Skip confirmation prompts"
    echo "  --keep-pvs               Keep Persistent Volumes (data will be preserved)"
    echo "  --keep-images            Keep Docker images"
    echo "  --cleanup-crds           Also cleanup Custom Resource Definitions"
    echo "  --all-namespaces         Remove KubeEstateHub from all namespaces"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                       # Interactive teardown of default namespace"
    echo "  $0 -f --keep-pvs         # Force teardown but keep data"
    echo "  $0 -n production -f      # Force teardown of production namespace"
    echo "  $0 --cleanup-crds        # Full cleanup including CRDs"
}

confirm_action() {
    if [ "$FORCE" = true ]; then
        return 0
    fi
    
    local message="$1"
    local default_response="${2:-n}"
    
    while true; do
        if [ "$default_response" = "y" ]; then
            read -p "$message [Y/n]: " response
            response=${response:-y}
        else
            read -p "$message [y/N]: " response
            response=${response:-n}
        fi
        
        case $response in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

check_prerequisites() {
    print_step "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    echo -e "${GREEN}✓${NC} Prerequisites check passed"
}

show_what_will_be_deleted() {
    print_step "Analyzing resources in namespace: $NAMESPACE"
    
    if ! kubectl get namespace $NAMESPACE &> /dev/null; then
        print_warning "Namespace $NAMESPACE does not exist"
        return
    fi
    
    echo ""
    echo "The following resources will be deleted:"
    echo ""
    
    # Deployments
    local deployments=$(kubectl get deployments -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
    echo "📦 Deployments: $deployments"
    kubectl get deployments -n $NAMESPACE --no-headers 2>/dev/null | sed 's/^/   /' || true
    
    # StatefulSets
    local statefulsets=$(kubectl get statefulsets -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
    echo "🗂️  StatefulSets: $statefulsets"
    kubectl get statefulsets -n $NAMESPACE --no-headers 2>/dev/null | sed 's/^/   /' || true
    
    # Services
    local services=$(kubectl get services -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
    echo "🌐 Services: $services"
    kubectl get services -n $NAMESPACE --no-headers 2>/dev/null | sed 's/^/   /' || true
    
    # PVCs
    local pvcs=$(kubectl get pvc -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
    echo "💾 Persistent Volume Claims: $pvcs"
    kubectl get pvc -n $NAMESPACE --no-headers 2>/dev/null | sed 's/^/   /' || true
    
    # ConfigMaps
    local configmaps=$(kubectl get configmaps -n $NAMESPACE --no-headers 2>/dev/null | grep -v kube-root-ca.crt | wc -l)
    echo "⚙️  ConfigMaps: $configmaps"
    kubectl get configmaps -n $NAMESPACE --no-headers 2>/dev/null | grep -v kube-root-ca.crt | sed 's/^/   /' || true
    
    # Secrets
    local secrets=$(kubectl get secrets -n $NAMESPACE --no-headers 2>/dev/null | grep -v default-token | wc -l)
    echo "🔐 Secrets: $secrets"
    kubectl get secrets -n $NAMESPACE --no-headers 2>/dev/null | grep -v default-token | sed 's/^/   /' || true
    
    # CronJobs
    local cronjobs=$(kubectl get cronjobs -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
    if [ $cronjobs -gt 0 ]; then
        echo "⏰ CronJobs: $cronjobs"
        kubectl get cronjobs -n $NAMESPACE --no-headers 2>/dev/null | sed 's/^/   /' || true
    fi
    
    # Jobs
    local jobs=$(kubectl get jobs -n $NAMESPACE --no-headers 2>/dev/null | wc -l)
    if [ $jobs -gt 0 ]; then
        echo "🏃 Jobs: $jobs"
        kubectl get jobs -n $NAMESPACE --no-headers 2>/dev/null | sed 's/^/   /' || true
    fi
    
    echo ""
    
    # Show PVs if they will be affected
    if [ "$KEEP_PVS" = false ]; then
        local pvs=$(kubectl get pv --no-headers 2>/dev/null | grep -E "(kubeestatehub|$NAMESPACE)" | wc -l)
        if [ $pvs -gt 0 ]; then
            print_warning "The following Persistent Volumes will also be deleted:"
            kubectl get pv --no-headers 2>/dev/null | grep -E "(kubeestatehub|$NAMESPACE)" | sed 's/^/   /' || true
            echo ""
        fi
    fi
}

delete_helm_releases() {
    print_step "Checking for Helm releases..."
    
    if ! command -v helm &> /dev/null; then
        print_warning "Helm not installed, skipping Helm cleanup"
        return
    fi
    
    local releases=$(helm list -n $NAMESPACE --short 2>/dev/null || true)
    
    if [ -n "$releases" ]; then
        echo "Found Helm releases in namespace $NAMESPACE:"
        echo "$releases" | sed 's/^/   /'
        
        if confirm_action "Delete Helm releases?"; then
            for release in $releases; do
                echo "Deleting Helm release: $release"
                helm uninstall $release -n $NAMESPACE
            done
        fi
    else
        echo "No Helm releases found in namespace $NAMESPACE"
    fi
}

delete_jobs_and_cronjobs() {
    print_step "Deleting Jobs and CronJobs..."
    
    # Delete CronJobs first
    kubectl delete cronjobs --all -n $NAMESPACE --ignore-not-found=true
    
    # Delete Jobs
    kubectl delete jobs --all -n $NAMESPACE --ignore-not-found=true
    
    echo -e "${GREEN}✓${NC} Jobs and CronJobs deleted"
}

delete_workloads() {
    print_step "Deleting workloads..."
    
    # Delete Deployments
    kubectl delete deployments --all -n $NAMESPACE --ignore-not-found=true --timeout=60s
    
    # Delete StatefulSets
    kubectl delete statefulsets --all -n $NAMESPACE --ignore-not-found=true --timeout=120s
    
    # Delete DaemonSets
    kubectl delete daemonsets --all -n $NAMESPACE --ignore-not-found=true --timeout=60s
    
    # Delete ReplicaSets (in case any are left)
    kubectl delete replicasets --all -n $NAMESPACE --ignore-not-found=true --timeout=30s
    
    echo -e "${GREEN}✓${NC} Workloads deleted"
}

delete_networking() {
    print_step "Deleting networking resources..."
    
    # Delete Services (except kubernetes default)
    kubectl delete services --all -n $NAMESPACE --ignore-not-found=true
    
    # Delete Ingress
    kubectl delete ingress --all -n $NAMESPACE --ignore-not-found=true
    
    # Delete NetworkPolicies
    kubectl delete networkpolicies --all -n $NAMESPACE --ignore-not-found=true
    
    echo -e "${GREEN}✓${NC} Networking resources deleted"
}

delete_storage() {
    print_step "Handling storage resources..."
    
    if [ "$KEEP_PVS" = true ]; then
        print_warning "Keeping Persistent Volumes as requested"
        # Change PV reclaim policy to Retain to prevent data loss
        local pvs=$(kubectl get pv --no-headers 2>/dev/null | grep -E "(kubeestatehub|$NAMESPACE)" | awk '{print $1}' || true)
        for pv in $pvs; do
            kubectl patch pv $pv -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
        done
    fi
    
    # Delete PVCs
    kubectl delete pvc --all -n $NAMESPACE --ignore-not-found=true
    
    if [ "$KEEP_PVS" = false ]; then
        # Wait for PVCs to be deleted, then clean up PVs
        sleep 10
        
        echo "Cleaning up associated Persistent Volumes..."
        local orphaned_pvs=$(kubectl get pv --no-headers 2>/dev/null | grep -E "(Released|Failed)" | awk '{print $1}' || true)
        for pv in $orphaned_pvs; do
            echo "Deleting orphaned PV: $pv"
            kubectl delete pv $pv --ignore-not-found=true
        done
    fi
    
    echo -e "${GREEN}✓${NC} Storage resources handled"
}

delete_configs_and_secrets() {
    print_step "Deleting configurations and secrets..."
    
    # Delete ConfigMaps (except system ones)
    kubectl get configmaps -n $NAMESPACE --no-headers 2>/dev/null | grep -v kube-root-ca.crt | awk '{print $1}' | while read cm; do
        kubectl delete configmap $cm -n $NAMESPACE --ignore-not-found=true
    done
    
    # Delete Secrets (except system ones)
    kubectl get secrets -n $NAMESPACE --no-headers 2>/dev/null | grep -v default-token | awk '{print $1}' | while read secret; do
        kubectl delete secret $secret -n $NAMESPACE --ignore-not-found=true
    done
    
    echo -e "${GREEN}✓${NC} Configurations and secrets deleted"
}

delete_rbac() {
    print_step "Cleaning up RBAC resources..."
    
    # Delete ServiceAccounts
    kubectl delete serviceaccounts --all -n $NAMESPACE --ignore-not-found=true
    
    # Delete namespace-scoped RoleBindings
    kubectl delete rolebindings --all -n $NAMESPACE --ignore-not-found=true
    
    # Delete namespace-scoped Roles
    kubectl delete roles --all -n $NAMESPACE --ignore-not-found=true
    
    # Clean up cluster-wide RBAC resources (be careful here)
    if confirm_action "Delete cluster-wide RBAC resources related to KubeEstateHub?"; then
        kubectl delete clusterrolebindings -l app.kubernetes.io/name=kubeestatehub --ignore-not-found=true
        kubectl delete clusterroles -l app.kubernetes.io/name=kubeestatehub --ignore-not-found=true
    fi
    
    echo -e "${GREEN}✓${NC} RBAC resources cleaned up"
}

delete_crds() {
    if [ "$CLEANUP_CRDS" = false ]; then
        return
    fi
    
    print_step "Cleaning up Custom Resource Definitions..."
    
    # List KubeEstateHub related CRDs
    local crds=$(kubectl get crds --no-headers 2>/dev/null | grep -i kubeestatehub | awk '{print $1}' || true)
    
    if [ -n "$crds" ]; then
        echo "Found KubeEstateHub CRDs:"
        echo "$crds" | sed 's/^/   /'
        
        if confirm_action "Delete these CRDs? (This will affect all namespaces)"; then
            for crd in $crds; do
                echo "Deleting CRD: $crd"
                kubectl delete crd $crd --ignore-not-found=true
            done
        fi
    else
        echo "No KubeEstateHub CRDs found"
    fi
}

delete_namespace() {
    print_step "Deleting namespace: $NAMESPACE"
    
    if kubectl get namespace $NAMESPACE &> /dev/null; then
        kubectl delete namespace $NAMESPACE --timeout=300s
        
        # Wait for namespace to be fully deleted
        echo "Waiting for namespace to be fully deleted..."
        while kubectl get namespace $NAMESPACE &> /dev/null; do
            echo -n "."
            sleep 2
        done
        echo ""
        
        echo -e "${GREEN}✓${NC} Namespace deleted successfully"
    else
        print_warning "Namespace $NAMESPACE does not exist"
    fi
}

cleanup_docker_images() {
    if [ "$KEEP_IMAGES" = true ]; then
        print_warning "Keeping Docker images as requested"
        return
    fi
    
    print_step "Cleaning up Docker images..."
    
    if ! command -v docker &> /dev/null; then
        print_warning "Docker not available, skipping image cleanup"
        return
    fi
    
    if ! docker info &> /dev/null; then
        print_warning "Docker daemon not running, skipping image cleanup"
        return
    fi
    
    local images=(
        "kubeestatehub/listings-api"
        "kubeestatehub/analytics-worker"
        "kubeestatehub/frontend-dashboard"
        "kubeestatehub/metrics-service"
    )
    
    for image in "${images[@]}"; do
        if docker images --format "table {{.Repository}}" | grep -q "^$image$"; then
            if confirm_action "Delete Docker image: $image?"; then
                docker rmi $image:latest --force 2>/dev/null || true
                # Also remove any other tags
                docker images --format "table {{.Repository}}:{{.Tag}}" | grep "^$image:" | while read img_tag; do
                    docker rmi $img_tag --force 2>/dev/null || true
                done
            fi
        fi
    done
    
    # Clean up dangling images
    if confirm_action "Clean up dangling Docker images?"; then
        docker image prune -f
    fi
    
    echo -e "${GREEN}✓${NC} Docker images cleaned up"
}

verify_cleanup() {
    print_step "Verifying cleanup..."
    
    if kubectl get namespace $NAMESPACE &> /dev/null; then
        print_error "Namespace $NAMESPACE still exists!"
        return 1
    fi
    
    # Check for any remaining cluster-wide resources
    local remaining_crbs=$(kubectl get clusterrolebindings -l app.kubernetes.io/name=kubeestatehub --no-headers 2>/dev/null | wc -l)
    local remaining_crs=$(kubectl get clusterroles -l app.kubernetes.io/name=kubeestatehub --no-headers 2>/dev/null | wc -l)
    
    if [ $remaining_crbs -gt 0 ] || [ $remaining_crs -gt 0 ]; then
        print_warning "Some cluster-wide resources may still exist"
    fi
    
    echo -e "${GREEN}✓${NC} Cleanup verification completed"
}

show_cleanup_summary() {
    print_step "Cleanup Summary"
    
    echo ""
    echo "🧹 KubeEstateHub teardown completed!"
    echo ""
    echo "What was removed:"
    echo "  ✓ Namespace: $NAMESPACE"
    echo "  ✓ All workloads (deployments, statefulsets, etc.)"
    echo "  ✓ All services and networking resources"
    echo "  ✓ All jobs and cronjobs"
    echo "  ✓ All configmaps and secrets"
    
    if [ "$KEEP_PVS" = true ]; then
        echo "  ⚠️  Persistent Volumes: PRESERVED"
    else
        echo "  ✓ Persistent Volumes and Claims"
    fi
    
    if [ "$KEEP_IMAGES" = true ]; then
        echo "  ⚠️  Docker Images: PRESERVED"
    else
        echo "  ✓ Docker images"
    fi
    
    if [ "$CLEANUP_CRDS" = true ]; then
        echo "  ✓ Custom Resource Definitions"
    fi
    
    echo ""
    echo "Your Kubernetes cluster is now clean of KubeEstateHub resources."
    
    if [ "$KEEP_PVS" = true ]; then
        echo ""
        print_warning "Data preserved in Persistent Volumes."
        echo "If you redeploy, the existing data will be reused."
    fi
}

main() {
    print_header
    
    check_prerequisites
    show_what_will_be_deleted
    
    echo ""
    if ! confirm_action "⚠️  Are you sure you want to teardown KubeEstateHub from namespace '$NAMESPACE'?"; then
        echo "Teardown cancelled."
        exit 0
    fi
    
    # Perform teardown
    delete_helm_releases
    delete_jobs_and_cronjobs
    delete_workloads
    delete_networking
    delete_storage
    delete_configs_and_secrets
    delete_rbac
    delete_crds
    delete_namespace
    cleanup_docker_images
    verify_cleanup
    show_cleanup_summary
    
    echo ""
    echo -e "${GREEN}✅ Teardown completed successfully!${NC}"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        --keep-pvs)
            KEEP_PVS=true
            shift
            ;;
        --keep-images)
            KEEP_IMAGES=true
            shift
            ;;
        --cleanup-crds)
            CLEANUP_CRDS=true
            shift
            ;;
        --all-namespaces)
            print_error "All-namespaces teardown not implemented for safety"
            exit 1
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

# Run main function
main