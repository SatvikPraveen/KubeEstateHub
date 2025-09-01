# Location: `/scripts/backup-db.sh`

#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default configuration
NAMESPACE="kubeestatehub"
DB_SERVICE="postgres-service"
DB_USER="admin"
DB_NAME="kubeestatehub"
BACKUP_DIR="/tmp/kubeestatehub-backups"
RETENTION_DAYS=7
COMPRESS=true
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}   KubeEstateHub DB Backup      ${NC}"
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
    echo "  -d, --backup-dir DIR    Backup directory (default: /tmp/kubeestatehub-backups)"
    echo "  -r, --retention DAYS    Retention period in days (default: 7)"
    echo "  -u, --db-user USER      Database user (default: admin)"
    echo "  --db-name NAME          Database name (default: kubeestatehub)"
    echo "  --no-compress           Don't compress backup files"
    echo "  --restore FILE          Restore from backup file"
    echo "  --list-backups          List available backups"
    echo "  --cleanup               Clean old backups only"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                              # Create backup with defaults"
    echo "  $0 -d /backups -r 30           # Backup to /backups, keep 30 days"
    echo "  $0 --restore backup.sql.gz     # Restore from backup file"
    echo "  $0 --list-backups              # List available backups"
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
    
    if ! kubectl get service $DB_SERVICE -n $NAMESPACE &> /dev/null; then
        print_error "Database service $DB_SERVICE not found in namespace $NAMESPACE"
        exit 1
    fi
    
    # Check if database pod is ready
    local db_pod=$(kubectl get pods -n $NAMESPACE -l app=postgres -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -z "$db_pod" ]; then
        print_error "No database pods found"
        exit 1
    fi
    
    if ! kubectl get pod $db_pod -n $NAMESPACE -o jsonpath='{.status.phase}' | grep -q "Running"; then
        print_error "Database pod is not running"
        exit 1
    fi
    
    echo -e "${GREEN}✓${NC} Prerequisites check passed"
}

create_backup_directory() {
    print_step "Creating backup directory..."
    
    mkdir -p "$BACKUP_DIR"
    
    if [ ! -w "$BACKUP_DIR" ]; then
        print_error "Backup directory $BACKUP_DIR is not writable"
        exit 1
    fi
    
    echo -e "${GREEN}✓${NC} Backup directory ready: $BACKUP_DIR"
}

get_database_pod() {
    kubectl get pods -n $NAMESPACE -l app=postgres -o jsonpath='{.items[0].metadata.name}'
}

create_backup() {
    print_step "Creating database backup..."
    
    local db_pod=$(get_database_pod)
    local backup_file="kubeestatehub_backup_${TIMESTAMP}.sql"
    local backup_path="$BACKUP_DIR/$backup_file"
    
    echo "Database pod: $db_pod"
    echo "Backup file: $backup_path"
    
    # Create the backup using pg_dump
    kubectl exec -n $NAMESPACE $db_pod -- pg_dump -U $DB_USER -d $DB_NAME --clean --if-exists > "$backup_path"
    
    if [ $? -ne 0 ]; then
        print_error "Database backup failed"
        rm -f "$backup_path"
        exit 1
    fi
    
    # Get backup size
    local backup_size=$(du -h "$backup_path" | cut -f1)
    echo "Backup created: $backup_size"
    
    # Compress if requested
    if [ "$COMPRESS" = true ]; then
        print_step "Compressing backup..."
        gzip "$backup_path"
        backup_path="${backup_path}.gz"
        local compressed_size=$(du -h "$backup_path" | cut -f1)
        echo "Compressed to: $compressed_size"
    fi
    
    # Verify backup integrity
    if [ "$COMPRESS" = true ]; then
        if ! gzip -t "$backup_path"; then
            print_error "Backup compression verification failed"
            exit 1
        fi
    fi
    
    echo -e "${GREEN}✓${NC} Backup completed: $backup_path"
    
    # Show backup info
    echo ""
    echo "Backup Information:"
    echo "  File: $(basename $backup_path)"
    echo "  Size: $(du -h $backup_path | cut -f1)"
    echo "  Path: $backup_path"
    echo "  Created: $(date)"
}

list_backups() {
    print_step "Available backups in $BACKUP_DIR:"
    echo ""
    
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A $BACKUP_DIR/kubeestatehub_backup_* 2>/dev/null)" ]; then
        echo "No backups found"
        return
    fi
    
    printf "%-30s %-10s %-20s\n" "BACKUP FILE" "SIZE" "DATE"
    printf "%-30s %-10s %-20s\n" "$(printf '%*s' 30 | tr ' ' '-')" "$(printf '%*s' 10 | tr ' ' '-')" "$(printf '%*s' 20 | tr ' ' '-')"
    
    for backup in $BACKUP_DIR/kubeestatehub_backup_*; do
        if [ -f "$backup" ]; then
            local filename=$(basename "$backup")
            local size=$(du -h "$backup" | cut -f1)
            local date=$(stat -c %y "$backup" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1 || date -r "$backup" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "Unknown")
            printf "%-30s %-10s %-20s\n" "$filename" "$size" "$date"
        fi
    done
}

restore_backup() {
    local restore_file="$1"
    
    print_step "Restoring database from backup..."
    
    # Check if restore file exists
    if [ ! -f "$restore_file" ]; then
        # Check if file exists in backup directory
        if [ -f "$BACKUP_DIR/$restore_file" ]; then
            restore_file="$BACKUP_DIR/$restore_file"
        else
            print_error "Backup file not found: $restore_file"
            exit 1
        fi
    fi
    
    local db_pod=$(get_database_pod)
    echo "Database pod: $db_pod"
    echo "Restore file: $restore_file"
    
    # Confirm restoration
    echo ""
    read -p "This will overwrite the current database. Continue? [y/N]: " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        echo "Restoration cancelled"
        exit 0
    fi
    
    # Create a backup before restore
    print_step "Creating safety backup before restore..."
    local safety_backup="$BACKUP_DIR/pre_restore_backup_${TIMESTAMP}.sql"
    kubectl exec -n $NAMESPACE $db_pod -- pg_dump -U $DB_USER -d $DB_NAME > "$safety_backup"
    if [ "$COMPRESS" = true ]; then
        gzip "$safety_backup"
        safety_backup="${safety_backup}.gz"
    fi
    echo "Safety backup created: $safety_backup"
    
    # Restore database
    print_step "Restoring database..."
    
    if [[ "$restore_file" == *.gz ]]; then
        # Restore from compressed file
        zcat "$restore_file" | kubectl exec -i -n $NAMESPACE $db_pod -- psql -U $DB_USER -d $DB_NAME
    else
        # Restore from uncompressed file
        cat "$restore_file" | kubectl exec -i -n $NAMESPACE $db_pod -- psql -U $DB_USER -d $DB_NAME
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Database restored successfully"
        
        # Verify restoration
        print_step "Verifying restoration..."
        local table_count=$(kubectl exec -n $NAMESPACE $db_pod -- psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" | tr -d ' ')
        echo "Tables in restored database: $table_count"
        
    else
        print_error "Database restoration failed"
        echo "Safety backup available at: $safety_backup"
        exit 1
    fi
}

cleanup_old_backups() {
    print_step "Cleaning up backups older than $RETENTION_DAYS days..."
    
    if [ ! -d "$BACKUP_DIR" ]; then
        echo "No backup directory found"
        return
    fi
    
    local deleted_count=0
    
    # Find and delete old backups
    find "$BACKUP_DIR" -name "kubeestatehub_backup_*" -type f -mtime +$RETENTION_DAYS -print0 | while IFS= read -r -d '' file; do
        echo "Deleting old backup: $(basename "$file")"
        rm -f "$file"
        ((deleted_count++))
    done
    
    if [ $deleted_count -eq 0 ]; then
        echo "No old backups to clean up"
    else
        echo -e "${GREEN}✓${NC} Cleaned up $deleted_count old backups"
    fi
}

verify_database_connection() {
    print_step "Verifying database connection..."
    
    local db_pod=$(get_database_pod)
    
    # Test connection
    if kubectl exec -n $NAMESPACE $db_pod -- pg_isready -U $DB_USER; then
        echo -e "${GREEN}✓${NC} Database connection verified"
        
        # Show basic database info
        local db_size=$(kubectl exec -n $NAMESPACE $db_pod -- psql -U $DB_USER -d $DB_NAME -t -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME'));" | tr -d ' ')
        local table_count=$(kubectl exec -n $NAMESPACE $db_pod -- psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" | tr -d ' ')
        
        echo "Database size: $db_size"
        echo "Number of tables: $table_count"
    else
        print_error "Database connection failed"
        exit 1
    fi
}

schedule_backup_cronjob() {
    print_step "Creating backup CronJob..."
    
    local cronjob_yaml="/tmp/kubeestatehub-backup-cronjob.yaml"
    
    cat > "$cronjob_yaml" << EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: kubeestatehub-db-backup
  namespace: $NAMESPACE
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: postgres-backup
            image: postgres:13
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-secret
                  key: POSTGRES_PASSWORD
            command:
            - /bin/bash
            - -c
            - |
              pg_dump -h postgres-service -U admin -d kubeestatehub > /backup/kubeestatehub_\$(date +%Y%m%d_%H%M%S).sql
              gzip /backup/kubeestatehub_\$(date +%Y%m%d_%H%M%S).sql
              find /backup -name "kubeestatehub_*.sql.gz" -mtime +7 -delete
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
EOF
    
    kubectl apply -f "$cronjob_yaml"
    rm -f "$cronjob_yaml"
    
    echo -e "${GREEN}✓${NC} Backup CronJob created (runs daily at 2 AM)"
}

main() {
    print_header
    
    if [ "$LIST_BACKUPS" = true ]; then
        list_backups
        exit 0
    fi
    
    if [ "$CLEANUP_ONLY" = true ]; then
        cleanup_old_backups
        exit 0
    fi
    
    check_prerequisites
    verify_database_connection
    
    if [ -n "$RESTORE_FILE" ]; then
        restore_backup "$RESTORE_FILE"
    else
        create_backup_directory
        create_backup
    fi
    
    cleanup_old_backups
    
    echo ""
    echo -e "${GREEN}✅ Database backup operation completed!${NC}"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -d|--backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        -r|--retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        -u|--db-user)
            DB_USER="$2"
            shift 2
            ;;
        --db-name)
            DB_NAME="$2"
            shift 2
            ;;
        --no-compress)
            COMPRESS=false
            shift
            ;;
        --restore)
            RESTORE_FILE="$2"
            shift 2
            ;;
        --list-backups)
            LIST_BACKUPS=true
            shift
            ;;
        --cleanup)
            CLEANUP_ONLY=true
            shift
            ;;
        --schedule-cronjob)
            SCHEDULE_CRONJOB=true
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

# Run main function
main