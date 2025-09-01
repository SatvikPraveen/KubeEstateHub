# Location: `/scripts/kubectl-aliases.sh`

#!/bin/bash

# KubeEstateHub kubectl aliases and shortcuts
# Source this file to add helpful aliases to your shell
# Usage: source kubectl-aliases.sh

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Loading KubeEstateHub kubectl aliases...${NC}"

# Set default namespace
export KUBEESTATEHUB_NS=${KUBEESTATEHUB_NS:-kubeestatehub}

# Basic kubectl shortcuts
alias k='kubectl'
alias kns='kubectl config set-context --current --namespace'
alias kctx='kubectl config use-context'

# Namespace shortcuts
alias keh='kubectl --namespace $KUBEESTATEHUB_NS'
alias kehns='kubectl config set-context --current --namespace=$KUBEESTATEHUB_NS'

# Pod management
alias kgp='kubectl get pods'
alias kgpo='kubectl get pods -o wide'
alias kgpa='kubectl get pods --all-namespaces'
alias kehp='kubectl get pods -n $KUBEESTATEHUB_NS'
alias kehpo='kubectl get pods -n $KUBEESTATEHUB_NS -o wide'
alias kdp='kubectl describe pod'
alias kdelp='kubectl delete pod'

# Deployment management
alias kgd='kubectl get deployments'
alias kgdo='kubectl get deployments -o wide'
alias kehd='kubectl get deployments -n $KUBEESTATEHUB_NS'
alias kdd='kubectl describe deployment'
alias keld='kubectl edit deployment'
alias kscaled='kubectl scale deployment'
alias krolloutd='kubectl rollout status deployment'
alias krestartd='kubectl rollout restart deployment'

# Service management  
alias kgs='kubectl get services'
alias kgso='kubectl get services -o wide'
alias kehs='kubectl get services -n $KUBEESTATEHUB_NS'
alias kds='kubectl describe service'
alias kels='kubectl edit service'

# ConfigMap and Secret management
alias kgcm='kubectl get configmaps'
alias kehcm='kubectl get configmaps -n $KUBEESTATEHUB_NS'
alias kdcm='kubectl describe configmap'
alias kelcm='kubectl edit configmap'
alias kgsec='kubectl get secrets'
alias kehsec='kubectl get secrets -n $KUBEESTATEHUB_NS'
alias kdsec='kubectl describe secret'

# StatefulSet management
alias kgss='kubectl get statefulsets'
alias kehss='kubectl get statefulsets -n $KUBEESTATEHUB_NS'
alias kdss='kubectl describe statefulset'
alias kelss='kubectl edit statefulset'

# Persistent Volume management
alias kgpv='kubectl get persistentvolumes'
alias kgpvc='kubectl get persistentvolumeclaims'
alias kehpvc='kubectl get persistentvolumeclaims -n $KUBEESTATEHUB_NS'
alias kdpv='kubectl describe persistentvolume'
alias kdpvc='kubectl describe persistentvolumeclaim'

# Ingress management
alias kgi='kubectl get ingress'
alias kehi='kubectl get ingress -n $KUBEESTATEHUB_NS'
alias kdi='kubectl describe ingress'
alias keli='kubectl edit ingress'

# Job and CronJob management
alias kgj='kubectl get jobs'
alias kehj='kubectl get jobs -n $KUBEESTATEHUB_NS'
alias kdj='kubectl describe job'
alias kgcj='kubectl get cronjobs'
alias kehcj='kubectl get cronjobs -n $KUBEESTATEHUB_NS'
alias kdcj='kubectl describe cronjob'

# Logs and debugging
alias kl='kubectl logs'
alias klf='kubectl logs -f'
alias kexec='kubectl exec -it'
alias kpf='kubectl port-forward'

# KubeEstateHub specific shortcuts
alias kehall='kubectl get all -n $KUBEESTATEHUB_NS'
alias kehpods='kubectl get pods -n $KUBEESTATEHUB_NS'
alias kehsvcs='kubectl get services -n $KUBEESTATEHUB_NS'

# KubeEstateHub application specific aliases
alias keh-api='kubectl get pods -n $KUBEESTATEHUB_NS -l app=listings-api'
alias keh-fe='kubectl get pods -n $KUBEESTATEHUB_NS -l app=frontend-dashboard'
alias keh-db='kubectl get pods -n $KUBEESTATEHUB_NS -l app=postgres'
alias keh-worker='kubectl get pods -n $KUBEESTATEHUB_NS -l app=analytics-worker'
alias keh-metrics='kubectl get pods -n $KUBEESTATEHUB_NS -l app=metrics-service'

# Logs for specific services
alias keh-api-logs='kubectl logs -n $KUBEESTATEHUB_NS -l app=listings-api -f'
alias keh-fe-logs='kubectl logs -n $KUBEESTATEHUB_NS -l app=frontend-dashboard -f'
alias keh-db-logs='kubectl logs -n $KUBEESTATEHUB_NS -l app=postgres -f'
alias keh-worker-logs='kubectl logs -n $KUBEESTATEHUB_NS -l app=analytics-worker -f'
alias keh-metrics-logs='kubectl logs -n $KUBEESTATEHUB_NS -l app=metrics-service -f'

# Port forwarding shortcuts
alias keh-pf-api='kubectl port-forward -n $KUBEESTATEHUB_NS svc/listings-api-service 8080:8080'
alias keh-pf-fe='kubectl port-forward -n $KUBEESTATEHUB_NS svc/frontend-dashboard-service 3000:80'
alias keh-pf-db='kubectl port-forward -n $KUBEESTATEHUB_NS svc/postgres-service 5432:5432'
alias keh-pf-grafana='kubectl port-forward -n $KUBEESTATEHUB_NS svc/grafana-service 3001:3000'
alias keh-pf-prometheus='kubectl port-forward -n $KUBEESTATEHUB_NS svc/prometheus-service 9090:9090'

# Shell access to pods
alias keh-shell-api='kubectl exec -it -n $KUBEESTATEHUB_NS deployment/listings-api -- /bin/bash'
alias keh-shell-fe='kubectl exec -it -n $KUBEESTATEHUB_NS deployment/frontend-dashboard -- /bin/sh'
alias keh-shell-db='kubectl exec -it -n $KUBEESTATEHUB_NS statefulset/postgres -- psql -U admin -d kubeestatehub'

# Resource monitoring
alias keh-top-pods='kubectl top pods -n $KUBEESTATEHUB_NS'
alias keh-top-nodes='kubectl top nodes'

# Events and troubleshooting
alias keh-events='kubectl get events -n $KUBEESTATEHUB_NS --sort-by=.metadata.creationTimestamp'
alias keh-events-follow='kubectl get events -n $KUBEESTATEHUB_NS --watch'

# Resource creation shortcuts
alias keh-create-secret='kubectl create secret generic -n $KUBEESTATEHUB_NS'
alias keh-create-cm='kubectl create configmap -n $KUBEESTATEHUB_NS'

# Scaling shortcuts
alias keh-scale-api='kubectl scale deployment listings-api -n $KUBEESTATEHUB_NS --replicas'
alias keh-scale-fe='kubectl scale deployment frontend-dashboard -n $KUBEESTATEHUB_NS --replicas'

# Restart deployments
alias keh-restart-api='kubectl rollout restart deployment/listings-api -n $KUBEESTATEHUB_NS'
alias keh-restart-fe='kubectl rollout restart deployment/frontend-dashboard -n $KUBEESTATEHUB_NS'
alias keh-restart-worker='kubectl rollout restart deployment/analytics-worker -n $KUBEESTATEHUB_NS'

# Utility functions
keh-pod-status() {
    echo -e "${BLUE}KubeEstateHub Pod Status:${NC}"
    kubectl get pods -n $KUBEESTATEHUB_NS -o custom-columns=NAME:.metadata.name,STATUS:.status.phase,READY:.status.containerStatuses[0].ready,RESTARTS:.status.containerStatuses[0].restartCount,AGE:.metadata.creationTimestamp
}

keh-service-endpoints() {
    echo -e "${BLUE}KubeEstateHub Service Endpoints:${NC}"
    kubectl get endpoints -n $KUBEESTATEHUB_NS
}

keh-resource-usage() {
    echo -e "${BLUE}KubeEstateHub Resource Usage:${NC}"
    kubectl top pods -n $KUBEESTATEHUB_NS 2>/dev/null || echo "Metrics server not available"
}

keh-deployment-status() {
    echo -e "${BLUE}KubeEstateHub Deployment Status:${NC}"
    kubectl get deployments -n $KUBEESTATEHUB_NS -o custom-columns=NAME:.metadata.name,READY:.status.readyReplicas,UP-TO-DATE:.status.updatedReplicas,AVAILABLE:.status.availableReplicas
}

keh-pvc-status() {
    echo -e "${BLUE}KubeEstateHub Storage Status:${NC}"
    kubectl get pvc -n $KUBEESTATEHUB_NS
    echo ""
    kubectl get pv | grep -E "(kubeestatehub|$KUBEESTATEHUB_NS)" 2>/dev/null || echo "No matching PVs found"
}

keh-ingress-status() {
    echo -e "${BLUE}KubeEstateHub Ingress Status:${NC}"
    kubectl get ingress -n $KUBEESTATEHUB_NS
}

keh-secrets-list() {
    echo -e "${BLUE}KubeEstateHub Secrets:${NC}"
    kubectl get secrets -n $KUBEESTATEHUB_NS --exclude=default-token
}

keh-configmaps-list() {
    echo -e "${BLUE}KubeEstateHub ConfigMaps:${NC}"
    kubectl get configmaps -n $KUBEESTATEHUB_NS --exclude=kube-root-ca.crt
}

keh-health-check() {
    echo -e "${BLUE}KubeEstateHub Health Check:${NC}"
    echo ""
    
    echo -e "${YELLOW}Checking API Service...${NC}"
    kubectl exec -n $KUBEESTATEHUB_NS deployment/listings-api -- curl -s http://localhost:8080/health 2>/dev/null || echo "API health check failed"
    
    echo -e "${YELLOW}Checking Database Connection...${NC}"
    kubectl exec -n $KUBEESTATEHUB_NS statefulset/postgres -- pg_isready -U admin 2>/dev/null || echo "Database check failed"
    
    echo -e "${YELLOW}Checking Frontend...${NC}"
    kubectl exec -n $KUBEESTATEHUB_NS deployment/frontend-dashboard -- wget -q --spider http://localhost:80/ 2>/dev/null || echo "Frontend check failed"
    
    echo ""
    echo "For detailed status, run: keh-pod-status"
}

keh-full-status() {
    echo -e "${BLUE}KubeEstateHub Full Status Report:${NC}"
    echo ""
    
    keh-pod-status
    echo ""
    keh-deployment-status
    echo ""
    keh-service-endpoints
    echo ""
    keh-pvc-status
    echo ""
    keh-ingress-status
    echo ""
    keh-resource-usage
}

keh-logs-all() {
    echo -e "${BLUE}Tailing logs from all KubeEstateHub services...${NC}"
    kubectl logs -n $KUBEESTATEHUB_NS -l app.kubernetes.io/name=kubeestatehub -f --max-log-requests=10
}

keh-describe-failing-pods() {
    echo -e "${BLUE}Describing pods not in Running state:${NC}"
    kubectl get pods -n $KUBEESTATEHUB_NS --field-selector=status.phase!=Running --no-headers | while read pod rest; do
        echo -e "${YELLOW}Describing pod: $pod${NC}"
        kubectl describe pod $pod -n $KUBEESTATEHUB_NS
        echo ""
    done
}

# Help function
keh-help() {
    echo -e "${BLUE}KubeEstateHub kubectl aliases:${NC}"
    echo ""
    echo -e "${YELLOW}Basic shortcuts:${NC}"
    echo "  k                    - kubectl"
    echo "  keh                  - kubectl --namespace $KUBEESTATEHUB_NS"
    echo "  kehns                - switch to KubeEstateHub namespace"
    echo ""
    echo -e "${YELLOW}Pod management:${NC}"
    echo "  kehp                 - get pods in KubeEstateHub namespace"
    echo "  keh-api              - get API pods"
    echo "  keh-fe               - get frontend pods"
    echo "  keh-db               - get database pods"
    echo "  keh-worker           - get worker pods"
    echo "  keh-metrics          - get metrics pods"
    echo ""
    echo -e "${YELLOW}Logs:${NC}"
    echo "  keh-api-logs         - tail API logs"
    echo "  keh-fe-logs          - tail frontend logs"
    echo "  keh-db-logs          - tail database logs"
    echo "  keh-logs-all         - tail all service logs"
    echo ""
    echo -e "${YELLOW}Port forwarding:${NC}"
    echo "  keh-pf-api           - port forward API (localhost:8080)"
    echo "  keh-pf-fe            - port forward frontend (localhost:3000)"
    echo "  keh-pf-db            - port forward database (localhost:5432)"
    echo "  keh-pf-grafana       - port forward Grafana (localhost:3001)"
    echo ""
    echo -e "${YELLOW}Shell access:${NC}"
    echo "  keh-shell-api        - shell into API pod"
    echo "  keh-shell-fe         - shell into frontend pod"
    echo "  keh-shell-db         - psql into database"
    echo ""
    echo -e "${YELLOW}Status and monitoring:${NC}"
    echo "  keh-full-status      - comprehensive status report"
    echo "  keh-health-check     - health check all services"
    echo "  keh-pod-status       - detailed pod status"
    echo "  keh-top-pods         - resource usage by pods"
    echo ""
    echo -e "${YELLOW}Scaling and restarts:${NC}"
    echo "  keh-scale-api        - scale API deployment"
    echo "  keh-restart-api      - restart API deployment"
    echo "  keh-restart-fe       - restart frontend deployment"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "  keh-events           - show namespace events"
    echo "  keh-describe-failing-pods - describe non-running pods"
}

echo -e "${GREEN}✓${NC} KubeEstateHub kubectl aliases loaded!"
echo -e "Run ${YELLOW}keh-help${NC} to see all available commands"
echo -e "Current namespace: ${YELLOW}$KUBEESTATEHUB_NS${NC}"