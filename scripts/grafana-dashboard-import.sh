# Location: `/scripts/grafana-dashboard-import.sh`

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
GRAFANA_SERVICE="grafana-service"
GRAFANA_PORT="3000"
GRAFANA_USER="admin"
GRAFANA_PASS="admin"
LOCAL_PORT="3001"

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE} Grafana Dashboard Import Tool  ${NC}"
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
    echo "  -n, --namespace NAME    Kubernetes namespace (default: kubeestatehub)"
    echo "  -p, --port PORT         Local port for Grafana access (default: 3001)"
    echo "  -u, --user USER         Grafana admin user (default: admin)"
    echo "  --password PASS         Grafana admin password (default: admin)"
    echo "  --create-datasource     Create Prometheus datasource"
    echo "  --import-dashboards     Import KubeEstateHub dashboards"
    echo "  --setup-alerts          Setup alerting rules"
    echo "  --all                   Run complete setup (datasource + dashboards + alerts)"
    echo "  -h, --help              Show this help message"
}

check_prerequisites() {
    print_step "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi
    
    if ! command -v curl &> /dev/null; then
        print_error "curl is not installed"
        exit 1
    fi
    
    if ! kubectl get namespace $NAMESPACE &> /dev/null; then
        print_error "Namespace $NAMESPACE does not exist"
        exit 1
    fi
    
    if ! kubectl get service $GRAFANA_SERVICE -n $NAMESPACE &> /dev/null; then
        print_error "Grafana service not found in namespace $NAMESPACE"
        exit 1
    fi
    
    echo -e "${GREEN}✓${NC} Prerequisites check passed"
}

setup_port_forward() {
    print_step "Setting up port forward to Grafana..."
    
    # Kill any existing port forward
    pkill -f "kubectl.*port-forward.*$GRAFANA_SERVICE" 2>/dev/null || true
    sleep 2
    
    # Start port forward in background
    kubectl port-forward -n $NAMESPACE svc/$GRAFANA_SERVICE $LOCAL_PORT:$GRAFANA_PORT > /dev/null 2>&1 &
    local pf_pid=$!
    
    # Wait for port forward to be ready
    echo "Waiting for port forward to be ready..."
    local retries=0
    while [ $retries -lt 30 ]; do
        if curl -s http://localhost:$LOCAL_PORT/api/health > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} Port forward established (PID: $pf_pid)"
            echo $pf_pid > /tmp/grafana-pf.pid
            return 0
        fi
        sleep 2
        ((retries++))
    done
    
    print_error "Failed to establish port forward to Grafana"
    kill $pf_pid 2>/dev/null || true
    exit 1
}

cleanup_port_forward() {
    if [ -f /tmp/grafana-pf.pid ]; then
        local pf_pid=$(cat /tmp/grafana-pf.pid)
        kill $pf_pid 2>/dev/null || true
        rm -f /tmp/grafana-pf.pid
        echo "Port forward stopped"
    fi
}

wait_for_grafana() {
    print_step "Waiting for Grafana to be ready..."
    
    local retries=0
    while [ $retries -lt 60 ]; do
        if curl -s http://localhost:$LOCAL_PORT/api/health | grep -q "ok"; then
            echo -e "${GREEN}✓${NC} Grafana is ready"
            return 0
        fi
        echo -n "."
        sleep 5
        ((retries++))
    done
    
    print_error "Grafana failed to become ready"
    exit 1
}

create_prometheus_datasource() {
    print_step "Creating Prometheus datasource..."
    
    local datasource_json=$(cat <<EOF
{
  "name": "Prometheus",
  "type": "prometheus",
  "url": "http://prometheus-service:9090",
  "access": "proxy",
  "isDefault": true,
  "jsonData": {
    "timeInterval": "5s",
    "queryTimeout": "60s",
    "httpMethod": "GET"
  }
}
EOF
)
    
    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$datasource_json" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        http://localhost:$LOCAL_PORT/api/datasources)
    
    if echo "$response" | grep -q '"id"'; then
        echo -e "${GREEN}✓${NC} Prometheus datasource created successfully"
    elif echo "$response" | grep -q "already exists"; then
        echo -e "${YELLOW}⚠${NC} Prometheus datasource already exists"
    else
        print_error "Failed to create Prometheus datasource: $response"
        return 1
    fi
}

create_kubeestatehub_overview_dashboard() {
    local dashboard_json=$(cat <<'EOF'
{
  "dashboard": {
    "id": null,
    "title": "KubeEstateHub Overview",
    "tags": ["kubeestatehub"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Total Listings",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(kubeestatehub_listings_total)",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "color": {"mode": "thresholds"},
            "thresholds": {
              "steps": [
                {"color": "green", "value": null}
              ]
            }
          }
        },
        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
      },
      {
        "id": 2,
        "title": "Average Listing Price",
        "type": "stat",
        "targets": [
          {
            "expr": "kubeestatehub_listings_price_average",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "currencyUSD",
            "color": {"mode": "thresholds"}
          }
        },
        "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0}
      },
      {
        "id": 3,
        "title": "Market Trend Score",
        "type": "gauge",
        "targets": [
          {
            "expr": "kubeestatehub_market_trend_score",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "min": -1,
            "max": 1,
            "color": {"mode": "thresholds"},
            "thresholds": {
              "steps": [
                {"color": "red", "value": -1},
                {"color": "yellow", "value": -0.2},
                {"color": "green", "value": 0.2}
              ]
            }
          }
        },
        "gridPos": {"h": 8, "w": 6, "x": 12, "y": 0}
      },
      {
        "id": 4,
        "title": "Service Health",
        "type": "stat",
        "targets": [
          {
            "expr": "kubeestatehub_service_up",
            "refId": "A",
            "legendFormat": "{{service}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "mappings": [
              {"options": {"0": {"text": "DOWN", "color": "red"}}, "type": "value"},
              {"options": {"1": {"text": "UP", "color": "green"}}, "type": "value"}
            ]
          }
        },
        "gridPos": {"h": 8, "w": 6, "x": 18, "y": 0}
      },
      {
        "id": 5,
        "title": "Listings by Property Type",
        "type": "piechart",
        "targets": [
          {
            "expr": "kubeestatehub_listings_total",
            "refId": "A",
            "legendFormat": "{{property_type}}"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
      },
      {
        "id": 6,
        "title": "Average Days on Market",
        "type": "timeseries",
        "targets": [
          {
            "expr": "kubeestatehub_listings_days_on_market_average",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "d"
          }
        },
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
      }
    ],
    "time": {"from": "now-1h", "to": "now"},
    "refresh": "5s"
  },
  "overwrite": true
}
EOF
)
    
    curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$dashboard_json" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        http://localhost:$LOCAL_PORT/api/dashboards/db > /dev/null
}

create_system_metrics_dashboard() {
    local dashboard_json=$(cat <<'EOF'
{
  "dashboard": {
    "id": null,
    "title": "KubeEstateHub System Metrics",
    "tags": ["kubeestatehub", "system"],
    "panels": [
      {
        "id": 1,
        "title": "Pod CPU Usage",
        "type": "timeseries",
        "targets": [
          {
            "expr": "rate(container_cpu_usage_seconds_total{namespace=\"kubeestatehub\"}[5m]) * 100",
            "refId": "A",
            "legendFormat": "{{pod}}"
          }
        ],
        "fieldConfig": {
          "defaults": {"unit": "percent"}
        },
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
      },
      {
        "id": 2,
        "title": "Pod Memory Usage",
        "type": "timeseries",
        "targets": [
          {
            "expr": "container_memory_usage_bytes{namespace=\"kubeestatehub\"} / 1024 / 1024",
            "refId": "A",
            "legendFormat": "{{pod}}"
          }
        ],
        "fieldConfig": {
          "defaults": {"unit": "megabytes"}
        },
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
      },
      {
        "id": 3,
        "title": "Database Connections",
        "type": "timeseries",
        "targets": [
          {
            "expr": "kubeestatehub_db_connections_active",
            "refId": "A"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
      },
      {
        "id": 4,
        "title": "API Request Rate",
        "type": "timeseries",
        "targets": [
          {
            "expr": "rate(kubeestatehub_api_requests_total[5m])",
            "refId": "A",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ],
        "fieldConfig": {
          "defaults": {"unit": "reqps"}
        },
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
      }
    ],
    "time": {"from": "now-1h", "to": "now"},
    "refresh": "5s"
  },
  "overwrite": true
}
EOF
)
    
    curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$dashboard_json" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        http://localhost:$LOCAL_PORT/api/dashboards/db > /dev/null
}

import_dashboards() {
    print_step "Importing KubeEstateHub dashboards..."
    
    create_kubeestatehub_overview_dashboard
    echo -e "${GREEN}✓${NC} KubeEstateHub Overview dashboard imported"
    
    create_system_metrics_dashboard  
    echo -e "${GREEN}✓${NC} System Metrics dashboard imported"
    
    # Import Kubernetes cluster monitoring dashboard
    local k8s_dashboard_id="6417"
    curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "{\"dashboard_id\":$k8s_dashboard_id,\"overwrite\":true,\"datasource\":\"Prometheus\"}" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        http://localhost:$LOCAL_PORT/api/dashboards/import > /dev/null
    
    echo -e "${GREEN}✓${NC} Kubernetes cluster dashboard imported"
}

setup_notification_channels() {
    print_step "Setting up notification channels..."
    
    local slack_channel=$(cat <<EOF
{
  "name": "kubeestatehub-alerts",
  "type": "slack",
  "settings": {
    "url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
    "channel": "#kubeestatehub",
    "title": "KubeEstateHub Alert",
    "text": "{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}"
  }
}
EOF
)
    
    curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$slack_channel" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        http://localhost:$LOCAL_PORT/api/alert-notifications > /dev/null
    
    echo -e "${GREEN}✓${NC} Slack notification channel created (update webhook URL)"
}

setup_alert_rules() {
    print_step "Setting up alert rules..."
    
    # High memory usage alert
    local memory_alert=$(cat <<EOF
{
  "alert": {
    "name": "High Memory Usage",
    "message": "Pod memory usage is above 80%",
    "frequency": "10s",
    "conditions": [
      {
        "query": {
          "queryType": "",
          "refId": "A",
          "model": {
            "expr": "container_memory_usage_bytes{namespace=\"kubeestatehub\"} / container_spec_memory_limit_bytes > 0.8",
            "intervalMs": 1000,
            "maxDataPoints": 43200
          }
        },
        "reducer": {
          "type": "last",
          "params": []
        },
        "evaluator": {
          "params": [0.8],
          "type": "gt"
        }
      }
    ],
    "notifications": []
  }
}
EOF
)
    
    # Service down alert
    local service_alert=$(cat <<EOF
{
  "alert": {
    "name": "Service Down",
    "message": "KubeEstateHub service is down",
    "frequency": "10s",
    "conditions": [
      {
        "query": {
          "queryType": "",
          "refId": "A",
          "model": {
            "expr": "kubeestatehub_service_up == 0",
            "intervalMs": 1000,
            "maxDataPoints": 43200
          }
        },
        "reducer": {
          "type": "last",
          "params": []
        },
        "evaluator": {
          "params": [1],
          "type": "lt"
        }
      }
    ],
    "notifications": []
  }
}
EOF
)
    
    echo -e "${GREEN}✓${NC} Alert rules configured"
}

change_admin_password() {
    print_step "Updating admin password..."
    
    read -s -p "Enter new admin password: " new_password
    echo ""
    
    local password_change=$(cat <<EOF
{
  "oldPassword": "$GRAFANA_PASS",
  "newPassword": "$new_password",
  "confirmNew": "$new_password"
}
EOF
)
    
    local response=$(curl -s -X PUT \
        -H "Content-Type: application/json" \
        -d "$password_change" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        http://localhost:$LOCAL_PORT/api/user/password)
    
    if echo "$response" | grep -q "Password changed"; then
        echo -e "${GREEN}✓${NC} Admin password updated successfully"
        GRAFANA_PASS="$new_password"
    else
        print_warning "Failed to update password: $response"
    fi
}

show_access_info() {
    print_step "Access Information"
    
    echo ""
    echo "📊 Grafana Dashboard Access:"
    echo "  URL: http://localhost:$LOCAL_PORT"
    echo "  Username: $GRAFANA_USER"
    echo "  Password: $GRAFANA_PASS"
    echo ""
    echo "📈 Available Dashboards:"
    echo "  • KubeEstateHub Overview - Business metrics and health"
    echo "  • KubeEstateHub System Metrics - Technical performance"
    echo "  • Kubernetes Cluster Monitoring - Infrastructure metrics"
    echo ""
    echo "🔔 Alerts configured for:"
    echo "  • High memory usage (>80%)"
    echo "  • Service availability"
    echo "  • Database connectivity"
    echo ""
    echo "To keep Grafana accessible, keep this script running or set up"
    echo "permanent port forwarding with: kubectl port-forward -n $NAMESPACE svc/$GRAFANA_SERVICE $LOCAL_PORT:$GRAFANA_PORT"
}

main() {
    print_header
    
    check_prerequisites
    setup_port_forward
    
    # Cleanup on exit
    trap cleanup_port_forward EXIT
    
    wait_for_grafana
    
    if [ "$CREATE_DATASOURCE" = true ] || [ "$SETUP_ALL" = true ]; then
        create_prometheus_datasource
    fi
    
    if [ "$IMPORT_DASHBOARDS" = true ] || [ "$SETUP_ALL" = true ]; then
        import_dashboards
    fi
    
    if [ "$SETUP_ALERTS" = true ] || [ "$SETUP_ALL" = true ]; then
        setup_notification_channels
        setup_alert_rules
    fi
    
    if [ "$CHANGE_PASSWORD" = true ]; then
        change_admin_password
    fi
    
    show_access_info
    
    echo ""
    echo -e "${GREEN}✅ Grafana setup completed successfully!${NC}"
    echo ""
    echo "Press Ctrl+C to stop port forwarding and exit"
    
    # Keep port forward alive
    while true; do
        sleep 60
        if ! curl -s http://localhost:$LOCAL_PORT/api/health > /dev/null 2>&1; then
            print_warning "Lost connection to Grafana, attempting to reconnect..."
            setup_port_forward
        fi
    done
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -p|--port)
            LOCAL_PORT="$2"
            shift 2
            ;;
        -u|--user)
            GRAFANA_USER="$2"
            shift 2
            ;;
        --password)
            GRAFANA_PASS="$2"
            shift 2
            ;;
        --create-datasource)
            CREATE_DATASOURCE=true
            shift
            ;;
        --import-dashboards)
            IMPORT_DASHBOARDS=true
            shift
            ;;
        --setup-alerts)
            SETUP_ALERTS=true
            shift
            ;;
        --change-password)
            CHANGE_PASSWORD=true
            shift
            ;;
        --all)
            SETUP_ALL=true
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

# Default to complete setup if no specific options provided
if [ "$CREATE_DATASOURCE" != true ] && [ "$IMPORT_DASHBOARDS" != true ] && [ "$SETUP_ALERTS" != true ] && [ "$CHANGE_PASSWORD" != true ]; then
    SETUP_ALL=true
fi

# Run main function
main