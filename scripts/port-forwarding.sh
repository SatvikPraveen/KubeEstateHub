# Location: `/scripts/port-forwarding.sh`

#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
NAMESPACE="kubeestatehub"
BACKGROUND=false
TMUX_SESSION="keh-portforward"

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  KubeEstateHub Port Forwarding ${NC}"
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
    echo "  -n, --namespace NAME    Target namespace (default: kubeestatehub)"
    echo "  -b, --background        Run port forwards in background"
    echo "  -t, --tmux              Use tmux session for port forwards"
    echo "  -s, --stop              Stop all port forwards"
    echo "  --api-only              Only forward API service"
    echo "  --frontend-only         Only forward frontend service"
    echo "  --monitoring-only       Only forward monitoring services"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Port mappings:"
    echo "  Frontend:     localhost:3000  -> frontend-dashboard-service:80"
    echo "  API:          localhost:8080  -> listings-api-service:8080"
    echo "  Database:     localhost:5432  -> postgres-service:5432"
    echo "  Grafana:      localhost:3001  -> grafana-service:3000"
    echo "  Prometheus:   localhost:9090  -> prometheus-service:9090"
    echo "  Metrics:      localhost:8081  -> metrics-service:8080"
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
    
    if ! kubectl get namespace $NAMESPACE &> /dev/null; then
        print_error "Namespace $NAMESPACE does not exist"
        exit 1
    fi
    
    if [ "$USE_TMUX" = true ] && ! command -v tmux &> /dev/null; then
        print_error "tmux is not installed but --tmux was specified"
        exit 1
    fi
    
    echo -e "${GREEN}✓${NC} Prerequisites check passed"
}

check_service_exists() {
    local service="$1"
    if ! kubectl get service $service -n $NAMESPACE &> /dev/null; then
        print_warning "Service $service does not exist in namespace $NAMESPACE"
        return 1
    fi
    return 0
}

check_port_availability() {
    local port="$1"
    local service_name="$2"
    
    if netstat -tuln 2>/dev/null | grep -q ":$port "; then
        print_warning "Port $port is already in use (needed for $service_name)"
        return 1
    fi
    return 0
}

stop_existing_port_forwards() {
    print_step "Stopping existing port forwards..."
    
    # Kill existing kubectl port-forward processes
    pkill -f "kubectl.*port-forward" 2>/dev/null || true
    
    # Kill tmux session if it exists
    if command -v tmux &> /dev/null; then
        tmux kill-session -t $TMUX_SESSION 2>/dev/null || true
    fi
    
    # Wait for processes to terminate
    sleep 2
    
    echo -e "${GREEN}✓${NC} Existing port forwards stopped"
}

start_port_forward() {
    local service="$1"
    local local_port="$2"
    local remote_port="$3"
    local service_name="$4"
    
    if ! check_service_exists "$service"; then
        return 1
    fi
    
    if ! check_port_availability "$local_port" "$service_name"; then
        print_warning "Skipping $service_name port forward due to port conflict"
        return 1
    fi
    
    local cmd="kubectl port-forward -n $NAMESPACE svc/$service $local_port:$remote_port"
    
    if [ "$USE_TMUX" = true ]; then
        # Create tmux session if it doesn't exist
        if ! tmux has-session -t $TMUX_SESSION 2>/dev/null; then
            tmux new-session -d -s $TMUX_SESSION
        fi
        
        # Create new window for this port forward
        tmux new-window -t $TMUX_SESSION -n "$service_name" "$cmd"
        
    elif [ "$BACKGROUND" = true ]; then
        # Run in background
        nohup $cmd > /tmp/pf-$service_name.log 2>&1 &
        local pid=$!
        echo $pid > /tmp/pf-$service_name.pid
        
    else
        # Run in foreground (will be managed by parent script)
        $cmd &
        local pid=$!
        echo $pid > /tmp/pf-$service_name.pid
    fi
    
    # Wait a moment and verify the port forward is working
    sleep 2
    if netstat -tuln 2>/dev/null | grep -q ":$local_port "; then
        echo -e "${GREEN}✓${NC} $service_name: localhost:$local_port -> $service:$remote_port"
        return 0
    else
        print_error "Failed to establish port forward for $service_name"
        return 1
    fi
}

start_frontend_port_forward() {
    if [ "$API_ONLY" = true ] || [ "$MONITORING_ONLY" = true ]; then
        return
    fi
    
    print_step "Setting up frontend port forward..."
    start_port_forward "frontend-dashboard-service" "3000" "80" "frontend"
}

start_api_port_forward() {
    if [ "$FRONTEND_ONLY" = true ] || [ "$MONITORING_ONLY" = true ]; then
        return
    fi
    
    print_step "Setting up API port forward..."
    start_port_forward "listings-api-service" "8080" "8080" "api"
}

start_database_port_forward() {
    if [ "$API_ONLY" = true ] || [ "$FRONTEND_ONLY" = true ] || [ "$MONITORING_ONLY" = true ]; then
        return
    fi
    
    print_step "Setting up database port forward..."
    start_port_forward "postgres-service" "5432" "5432" "database"
}

start_monitoring_port_forwards() {
    if [ "$API_ONLY" = true ] || [ "$FRONTEND_ONLY" = true ]; then
        return
    fi
    
    print_step "Setting up monitoring port forwards..."
    
    # Grafana
    start_port_forward "grafana-service" "3001" "3000" "grafana"
    
    # Prometheus
    start_port_forward "prometheus-service" "9090" "9090" "prometheus"
    
    # Metrics service
    start_port_forward "metrics-service" "8081" "8080" "metrics"
}

show_access_info() {
    print_step "Port Forward Status"
    
    echo ""
    echo "🌐 Application Access URLs:"
    echo ""
    
    if netstat -tuln 2>/dev/null | grep -q ":3000 "; then
        echo -e "  ${GREEN}Frontend Dashboard:${NC} http://localhost:3000"
    fi
    
    if netstat -tuln 2>/dev/null | grep -q ":8080 "; then
        echo -e "  ${GREEN}API Service:${NC}        http://localhost:8080"
        echo -e "                          http://localhost:8080/health (health check)"
        echo -e "                          http://localhost:8080/docs (API docs)"
    fi
    
    if netstat -tuln 2>/dev/null | grep -q ":5432 "; then
        echo -e "  ${GREEN}Database:${NC}           postgresql://admin:secretpassword@localhost:5432/kubeestatehub"
    fi
    
    echo ""
    echo "📊 Monitoring Access URLs:"
    echo ""
    
    if netstat -tuln 2>/dev/null | grep -q ":3001 "; then
        echo -e "  ${GREEN}Grafana:${NC}            http://localhost:3001 (admin/admin)"
    fi
    
    if netstat -tuln 2>/dev/null | grep -q ":9090 "; then
        echo -e "  ${GREEN}Prometheus:${NC}         http://localhost:9090"
    fi
    
    if netstat -tuln 2>/dev/null | grep -q ":8081 "; then
        echo -e "  ${GREEN}Metrics Service:${NC}    http://localhost:8081/metrics"
        echo -e "                          http://localhost:8081/metrics/json"
    fi
    
    echo ""
    
    if [ "$USE_TMUX" = true ]; then
        echo "🖥️  Port forwards are running in tmux session: $TMUX_SESSION"
        echo "   View session: tmux attach-session -t $TMUX_SESSION"
        echo "   List windows: tmux list-windows -t $TMUX_SESSION"
        echo "   Stop all: tmux kill-session -t $TMUX_SESSION"
    elif [ "$BACKGROUND" = true ]; then
        echo "🔄 Port forwards are running in background"
        echo "   Stop all: $0 --stop"
        echo "   View logs: tail -f /tmp/pf-*.log"
    else
        echo "⚠️  Press Ctrl+C to stop all port forwards"
    fi
}

show_status() {
    print_step "Port Forward Status"
    
    echo ""
    echo "Active port forwards:"
    
    local ports=(3000 8080 5432 3001 9090 8081)
    local services=("frontend" "api" "database" "grafana" "prometheus" "metrics")
    local found=false
    
    for i in "${!ports[@]}"; do
        local port="${ports[$i]}"
        local service="${services[$i]}"
        
        if netstat -tuln 2>/dev/null | grep -q ":$port "; then
            echo -e "  ${GREEN}✓${NC} $service: localhost:$port"
            found=true
        fi
    done
    
    if [ "$found" = false ]; then
        echo "  No active port forwards found"
    fi
    
    echo ""
    
    # Show tmux session status
    if command -v tmux &> /dev/null && tmux has-session -t $TMUX_SESSION 2>/dev/null; then
        echo "Tmux session '$TMUX_SESSION' is active:"
        tmux list-windows -t $TMUX_SESSION
    fi
}

wait_for_interrupt() {
    if [ "$BACKGROUND" = false ] && [ "$USE_TMUX" = false ]; then
        print_step "Port forwards are running. Press Ctrl+C to stop."
        
        # Trap interrupt signal
        trap 'echo ""; print_step "Stopping port forwards..."; stop_existing_port_forwards; exit 0' INT
        
        # Wait indefinitely
        while true; do
            sleep 60
            # Check if any port forwards are still running
            if ! pgrep -f "kubectl.*port-forward" > /dev/null; then
                print_warning "All port forwards have stopped unexpectedly"
                break
            fi
        done
    fi
}

main() {
    print_header
    
    if [ "$STOP_FORWARDS" = true ]; then
        stop_existing_port_forwards
        show_status
        exit 0
    fi
    
    check_prerequisites
    stop_existing_port_forwards
    
    # Start port forwards based on options
    start_frontend_port_forward
    start_api_port_forward
    start_database_port_forward
    start_monitoring_port_forwards
    
    show_access_info
    wait_for_interrupt
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -b|--background)
            BACKGROUND=true
            shift
            ;;
        -t|--tmux)
            USE_TMUX=true
            shift
            ;;
        -s|--stop)
            STOP_FORWARDS=true
            shift
            ;;
        --api-only)
            API_ONLY=true
            shift
            ;;
        --frontend-only)
            FRONTEND_ONLY=true
            shift
            ;;
        --monitoring-only)
            MONITORING_ONLY=true
            shift
            ;;
        --status)
            show_status
            exit 0
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