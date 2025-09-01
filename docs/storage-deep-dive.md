# Location: `/docs/storage-deep-dive.md`

# Storage Deep Dive Guide

Comprehensive guide to storage architecture, management, and optimization in KubeEstateHub.

## Storage Architecture Overview

### Storage Components

```yaml
Storage Stack:
├── Storage Classes
│   ├── fast-ssd (database workloads)
│   ├── standard (general purpose)
│   └── backup-storage (long-term retention)
├── Persistent Volumes (PV)
│   ├── Database volumes (ReadWriteOnce)
│   └── Shared storage (ReadWriteMany)
├── Persistent Volume Claims (PVC)
│   ├── postgres-pvc (20Gi)
│   └── image-store-pvc (50Gi)
└── Volume Mounts
    ├── Application data
    └── Configuration files
```

### Storage Classes

#### Fast SSD Storage Class

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
  fsType: ext4
allowVolumeExpansion: true
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
```

#### Standard Storage Class

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp2
  fsType: ext4
allowVolumeExpansion: true
reclaimPolicy: Delete
volumeBindingMode: Immediate
```

## Database Storage Configuration

### PostgreSQL StatefulSet Storage

```bash
# Check current database storage
kubectl get pvc postgres-pvc -n kubeestatehub
kubectl describe pvc postgres-pvc -n kubeestatehub

# Monitor database disk usage
kubectl exec postgres-0 -n kubeestatehub -- df -h /var/lib/postgresql/data
kubectl exec postgres-0 -n kubeestatehub -- du -sh /var/lib/postgresql/data/*
```

### Database Storage Optimization

#### PostgreSQL Configuration Tuning

```bash
# Access PostgreSQL configuration
kubectl exec -it postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub

# Optimize storage-related settings
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET checkpoint_timeout = '15min';
ALTER SYSTEM SET max_wal_size = '4GB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET wal_compression = on;
ALTER SYSTEM SET wal_buffers = '32MB';
SELECT pg_reload_conf();
```

#### Database Storage Monitoring

```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('kubeestatehub'));

-- Check table sizes
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check WAL usage
SELECT pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0'));

-- Check unused space
SELECT schemaname, tablename,
       n_dead_tup,
       n_live_tup,
       round(n_dead_tup::numeric / (n_live_tup + n_dead_tup) * 100, 2) as dead_pct
FROM pg_stat_user_tables
WHERE n_dead_tup > 0
ORDER BY dead_pct DESC;
```

## Volume Management

### PVC Operations

#### Creating PVCs

```bash
# Create new PVC from manifest
kubectl apply -f manifests/storage/additional-pvc.yaml

# Create PVC imperatively
kubectl create pvc my-pvc --size=10Gi --storage-class=standard -n kubeestatehub
```

#### Expanding PVCs

```bash
# Check if storage class supports expansion
kubectl get storageclass standard -o yaml | grep allowVolumeExpansion

# Expand existing PVC
kubectl patch pvc postgres-pvc -n kubeestatehub -p '{"spec":{"resources":{"requests":{"storage":"40Gi"}}}}'

# Monitor expansion progress
kubectl get pvc postgres-pvc -n kubeestatehub -w
kubectl describe pvc postgres-pvc -n kubeestatehub
```

#### PVC Troubleshooting

```bash
# Check PVC status
kubectl get pvc -n kubeestatehub
kubectl describe pvc <pvc-name> -n kubeestatehub

# Check associated PV
kubectl get pv
kubectl describe pv <pv-name>

# Check storage class
kubectl get storageclass
kubectl describe storageclass <storage-class-name>
```

### Volume Snapshots

#### Creating Volume Snapshots

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: postgres-snapshot
  namespace: kubeestatehub
spec:
  volumeSnapshotClassName: csi-aws-vsc
  source:
    persistentVolumeClaimName: postgres-pvc
```

#### Restoring from Snapshots

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-restored-pvc
  namespace: kubeestatehub
spec:
  storageClassName: fast-ssd
  dataSource:
    name: postgres-snapshot
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
```

## File Storage Solutions

### Shared Storage (ReadWriteMany)

#### NFS Storage for Shared Files

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: shared-storage-pv
spec:
  capacity:
    storage: 100Gi
  accessModes:
    - ReadWriteMany
  nfs:
    path: /shared
    server: nfs-server.example.com
  persistentVolumeReclaimPolicy: Retain
```

#### EFS Storage Class (AWS)

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: efs-sc
provisioner: efs.csi.aws.com
parameters:
  provisioningMode: efs-ap
  fileSystemId: fs-92107410
  directoryPerms: "0755"
  gidRangeStart: "1000"
  gidRangeEnd: "2000"
allowVolumeExpansion: false
```

### Object Storage Integration

#### S3 Integration for Backups

```bash
# Install s3cmd in pods
kubectl exec -it postgres-0 -n kubeestatehub -- apt-get update
kubectl exec -it postgres-0 -n kubeestatehub -- apt-get install -y s3cmd

# Configure S3 access
kubectl create secret generic s3-credentials -n kubeestatehub \
  --from-literal=access-key=YOUR_ACCESS_KEY \
  --from-literal=secret-key=YOUR_SECRET_KEY

# Backup to S3
kubectl exec -it postgres-0 -n kubeestatehub -- pg_dump -U admin kubeestatehub | \
kubectl exec -i postgres-0 -n kubeestatehub -- s3cmd put - s3://your-bucket/backups/kubeestatehub-$(date +%Y%m%d).sql
```

## Performance Optimization

### I/O Performance Tuning

#### Storage I/O Monitoring

```bash
# Monitor disk I/O in pods
kubectl exec postgres-0 -n kubeestatehub -- iostat -x 1 5
kubectl exec postgres-0 -n kubeestatehub -- iotop -a -o

# Check disk performance
kubectl exec postgres-0 -n kubeestatehub -- dd if=/dev/zero of=/var/lib/postgresql/data/testfile bs=1M count=1000 oflag=direct
kubectl exec postgres-0 -n kubeestatehub -- dd if=/var/lib/postgresql/data/testfile of=/dev/null bs=1M iflag=direct
```

#### Optimizing for Database Workloads

```yaml
# PostgreSQL StatefulSet with optimized storage
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: kubeestatehub
spec:
  serviceName: postgres-service
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:13
          env:
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: db-secret
                  key: POSTGRES_USER
          volumeMounts:
            - name: postgres-storage
              mountPath: /var/lib/postgresql/data
            - name: postgres-wal
              mountPath: /var/lib/postgresql/wal
          resources:
            requests:
              cpu: 1
              memory: 2Gi
            limits:
              cpu: 2
              memory: 4Gi
  volumeClaimTemplates:
    - metadata:
        name: postgres-storage
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: fast-ssd
        resources:
          requests:
            storage: 20Gi
    - metadata:
        name: postgres-wal
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: fast-ssd
        resources:
          requests:
            storage: 10Gi
```

### Cache and Temporary Storage

```yaml
# Memory-based storage for cache
apiVersion: v1
kind: Pod
spec:
  containers:
    - name: api
      volumeMounts:
        - name: cache-volume
          mountPath: /tmp/cache
  volumes:
    - name: cache-volume
      emptyDir:
        medium: Memory
        sizeLimit: 1Gi
```

## Backup and Recovery

### Automated Database Backups

```yaml
# Database backup CronJob
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: kubeestatehub
spec:
  schedule: "0 2 * * *"
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
                  pg_dump -h postgres-service -U admin kubeestatehub | gzip > /backup/kubeestatehub_$(date +%Y%m%d_%H%M%S).sql.gz
                  find /backup -name "kubeestatehub_*.sql.gz" -mtime +7 -delete
              volumeMounts:
                - name: backup-storage
                  mountPath: /backup
          volumes:
            - name: backup-storage
              persistentVolumeClaim:
                claimName: backup-pvc
          restartPolicy: OnFailure
```

### Point-in-Time Recovery

```bash
# Enable WAL archiving
kubectl exec -it postgres-0 -n kubeestatehub -- psql -U admin -d kubeestatehub

ALTER SYSTEM SET wal_level = replica;
ALTER SYSTEM SET archive_mode = on;
ALTER SYSTEM SET archive_command = 'cp %p /var/lib/postgresql/wal_archive/%f';
ALTER SYSTEM SET max_wal_senders = 3;
SELECT pg_reload_conf();

# Restart PostgreSQL
kubectl rollout restart statefulset/postgres -n kubeestatehub
```

### Storage Migration

#### Migrating to Different Storage Class

```bash
# 1. Create new PVC with desired storage class
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc-new
  namespace: kubeestatehub
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: fast-ssd
  resources:
    requests:
      storage: 40Gi
EOF

# 2. Scale down StatefulSet
kubectl scale statefulset postgres --replicas=0 -n kubeestatehub

# 3. Copy data using job
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: data-migration
  namespace: kubeestatehub
spec:
  template:
    spec:
      containers:
      - name: data-copy
        image: busybox
        command: ['sh', '-c', 'cp -a /old-data/. /new-data/']
        volumeMounts:
        - name: old-volume
          mountPath: /old-data
        - name: new-volume
          mountPath: /new-data
      volumes:
      - name: old-volume
        persistentVolumeClaim:
          claimName: postgres-pvc
      - name: new-volume
        persistentVolumeClaim:
          claimName: postgres-pvc-new
      restartPolicy: Never
EOF

# 4. Update StatefulSet to use new PVC
kubectl patch statefulset postgres -n kubeestatehub -p '{"spec":{"volumeClaimTemplates":[{"metadata":{"name":"postgres-storage"},"spec":{"accessModes":["ReadWriteOnce"],"storageClassName":"fast-ssd","resources":{"requests":{"storage":"40Gi"}}}}]}}'

# 5. Scale up StatefulSet
kubectl scale statefulset postgres --replicas=1 -n kubeestatehub
```

## Storage Security

### Encryption at Rest

```yaml
# Encrypted storage class
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: encrypted-ssd
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  encrypted: "true"
  kmsKeyId: arn:aws:kms:us-west-2:123456789012:key/12345678-1234-1234-1234-123456789012
allowVolumeExpansion: true
reclaimPolicy: Delete
```

### Access Control

```bash
# Set proper file permissions in init container
initContainers:
- name: set-permissions
  image: busybox
  command: ['sh', '-c', 'chmod 700 /var/lib/postgresql/data && chown 999:999 /var/lib/postgresql/data']
  volumeMounts:
  - name: postgres-storage
    mountPath: /var/lib/postgresql/data
  securityContext:
    runAsUser: 0
```

## Storage Monitoring

### Metrics Collection

```bash
# Storage metrics from Prometheus
# Disk usage
container_fs_usage_bytes{namespace="kubeestatehub"}

# Disk I/O
rate(container_fs_reads_total{namespace="kubeestatehub"}[5m])
rate(container_fs_writes_total{namespace="kubeestatehub"}[5m])

# PVC usage
kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes
```

### Alerting Rules

```yaml
groups:
  - name: storage.rules
    rules:
      - alert: HighDiskUsage
        expr: (container_fs_usage_bytes{namespace="kubeestatehub"} / container_fs_limit_bytes) > 0.85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High disk usage detected"
          description: "Disk usage is above 85% in namespace kubeestatehub"

      - alert: PVCNearlyFull
        expr: (kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes) > 0.90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "PVC nearly full"
          description: "PVC {{ $labels.persistentvolumeclaim }} is over 90% full"
```

## Disaster Recovery

### Multi-Zone Deployment

```yaml
# Database with zone anti-affinity
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: kubeestatehub
spec:
  template:
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchExpressions:
                  - key: app
                    operator: In
                    values:
                      - postgres
              topologyKey: failure-domain.beta.kubernetes.io/zone
```

### Cross-Region Backup

```bash
# Backup to multiple regions
kubectl create job backup-to-s3 --image=postgres:13 -n kubeestatehub -- /bin/bash -c "
pg_dump -h postgres-service -U admin kubeestatehub |
gzip |
tee >(aws s3 cp - s3://primary-backup-bucket/kubeestatehub-$(date +%Y%m%d).sql.gz) |
aws s3 cp - s3://secondary-backup-bucket/kubeestatehub-$(date +%Y%m%d).sql.gz"
```

## Storage Best Practices

### Resource Planning

- Size PVCs with 20% growth buffer
- Use appropriate storage classes for workload types
- Monitor storage usage trends
- Plan for backup storage requirements

### Performance Optimization

- Use SSD storage for database workloads
- Separate WAL from data directory
- Monitor I/O patterns and adjust accordingly
- Use local storage for temporary data

### Cost Management

- Use storage tiers appropriately
- Implement data lifecycle policies
- Regular cleanup of unused volumes
- Monitor storage costs and usage

### Security Measures

- Enable encryption at rest
- Use proper access controls
- Regular security audits
- Secure backup storage

This storage guide provides comprehensive coverage of storage management in KubeEstateHub, from basic concepts to advanced optimization and disaster recovery scenarios.
