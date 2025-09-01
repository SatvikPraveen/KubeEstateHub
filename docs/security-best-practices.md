# Location: `/docs/security-best-practices.md`

# Security Best Practices Guide

Comprehensive security guide for KubeEstateHub covering Pod Security Standards, RBAC, network policies, and security monitoring.

## Pod Security Standards

### Security Contexts

```yaml
# Restrictive security context
apiVersion: v1
kind: Pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 2000
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: app
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop:
            - ALL
        runAsNonRoot: true
```

### Pod Security Policy

```yaml
# Apply pod security standards
kubectl apply -f manifests/security/pod-security-standards.yaml
kubectl apply -f manifests/security/security-contexts.yaml

# Label namespace for pod security
kubectl label namespace kubeestatehub pod-security.kubernetes.io/enforce=restricted
kubectl label namespace kubeestatehub pod-security.kubernetes.io/audit=restricted
kubectl label namespace kubeestatehub pod-security.kubernetes.io/warn=restricted
```

## RBAC Configuration

### Service Accounts

```bash
# Create service accounts with minimal permissions
kubectl apply -f manifests/configs/service-accounts.yaml
kubectl apply -f manifests/configs/rbac-admin.yaml
kubectl apply -f manifests/configs/rbac-readonly.yaml

# Verify RBAC
kubectl auth can-i get pods --as=system:serviceaccount:kubeestatehub:api-service-account
kubectl auth can-i create secrets --as=system:serviceaccount:kubeestatehub:readonly-account
```

### Role-Based Access Control

```yaml
# Principle of least privilege
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: kubeestatehub
  name: listings-api-role
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
```

## Network Security

### Network Policies

```bash
# Apply network policies
kubectl apply -f manifests/network/network-policy-frontend.yaml
kubectl apply -f manifests/network/network-policy-db.yaml

# Verify network policies
kubectl get networkpolicies -n kubeestatehub
kubectl describe networkpolicy frontend-netpol -n kubeestatehub
```

### Network Policy Examples

```yaml
# Database isolation policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: postgres-netpol
  namespace: kubeestatehub
spec:
  podSelector:
    matchLabels:
      app: postgres
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: listings-api
        - podSelector:
            matchLabels:
              app: analytics-worker
      ports:
        - protocol: TCP
          port: 5432
```

## Secrets Management

### Secret Creation and Rotation

```bash
# Create secrets securely
kubectl create secret generic db-secret \
  --from-literal=POSTGRES_USER=admin \
  --from-literal=POSTGRES_PASSWORD=$(openssl rand -base64 32) \
  -n kubeestatehub

# Rotate secrets
kubectl patch secret db-secret -n kubeestatehub -p '{"data":{"POSTGRES_PASSWORD":"'$(echo -n $(openssl rand -base64 32) | base64 -w 0)'"}}'
kubectl rollout restart deployment/listings-api -n kubeestatehub
```

### Encrypted Secrets at Rest

```bash
# Enable encryption at rest (cluster-level configuration)
# Add to kube-apiserver configuration:
--encryption-provider-config=/etc/kubernetes/encryption/config.yaml
```

## Image Security

### Image Scanning

```bash
# Scan images for vulnerabilities
docker scout cves kubeestatehub/listings-api:latest
docker scout quickview kubeestatehub/listings-api:latest

# Use distroless base images
FROM gcr.io/distroless/python3-debian11:latest
```

### Image Policy

```yaml
# Admission controller for image policies
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-image-signature
spec:
  validationFailureAction: enforce
  background: false
  rules:
    - name: check-image-signature
      match:
        any:
          - resources:
              kinds:
                - Pod
              namespaces:
                - kubeestatehub
      verifyImages:
        - imageReferences:
            - "kubeestatehub/*"
          attestors:
            - entries:
                - keys:
                    publicKeys: |
                      -----BEGIN PUBLIC KEY-----
                      YOUR_PUBLIC_KEY_HERE
                      -----END PUBLIC KEY-----
```

## Runtime Security

### Security Monitoring

```bash
# Monitor security events
kubectl get events --field-selector type=Warning -n kubeestatehub
kubectl logs -l app=security-scanner -n kubeestatehub

# Check for privilege escalation attempts
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{": "}{.spec.securityContext.runAsUser}{"\n"}{end}' -n kubeestatehub
```

### Falco Integration

```yaml
# Falco security rules
- rule: Unauthorized Process in Container
  desc: Detect unauthorized process execution
  condition: >
    spawned_process and
    k8s_ns=kubeestatehub and
    not proc.name in (python, sh, bash, pg_dump, psql)
  output: >
    Unauthorized process spawned (user=%user.name command=%proc.cmdline 
    container=%container.name image=%container.image.repository)
  priority: WARNING
```

## Data Protection

### Database Security

```sql
-- Create restricted database users
CREATE ROLE app_readonly WITH LOGIN PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE kubeestatehub TO app_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;

-- Enable row-level security
ALTER TABLE listings ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_listings ON listings FOR ALL TO app_user USING (user_id = current_user_id());
```

### Data Encryption

```yaml
# Encrypt data at rest using CSI driver
apiVersion: v1
kind: StorageClass
metadata:
  name: encrypted-gp2
provisioner: ebs.csi.aws.com
parameters:
  type: gp2
  encrypted: "true"
  kmsKeyId: arn:aws:kms:us-west-2:123456789012:key/12345678-1234-1234-1234-123456789012
```

## Vulnerability Management

### Security Scanning Pipeline

```yaml
# GitHub Actions security scan
name: Security Scan
on:
  push:
    branches: [main]
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: "kubeestatehub/listings-api:latest"
          format: "sarif"
          output: "trivy-results.sarif"
```

### Security Auditing

```bash
# Regular security audits
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.securityContext}{"\n"}{end}' -n kubeestatehub
kubectl get networkpolicies --all-namespaces
kubectl get rolebindings,clusterrolebindings --all-namespaces -o wide
```

## Compliance and Governance

### CIS Kubernetes Benchmark

```bash
# Run CIS benchmark checks
kube-bench run --targets master,node,etcd,policies
kube-bench run --check 1.2.1,1.2.2,4.1.1,4.1.2
```

### Policy Enforcement

```yaml
# OPA Gatekeeper constraints
apiVersion: templates.gatekeeper.sh/v1beta1
kind: ConstraintTemplate
metadata:
  name: k8srequiredsecuritycontext
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredSecurityContext
      validation:
        properties:
          runAsNonRoot:
            type: boolean
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8srequiredsecuritycontext

        violation[{"msg": msg}] {
          input.review.object.spec.securityContext.runAsNonRoot != true
          msg := "Container must run as non-root user"
        }
```

## Security Incident Response

### Incident Detection

```bash
# Monitor for security incidents
kubectl get events --field-selector type=Warning --all-namespaces
kubectl logs -l app=falco -n falco-system

# Check for suspicious activities
kubectl get pods --field-selector=status.phase=Failed --all-namespaces
kubectl get events --field-selector reason=FailedMount --all-namespaces
```

### Response Procedures

1. **Isolate**: Scale down affected deployments
2. **Investigate**: Collect logs and examine affected resources
3. **Contain**: Apply network policies to prevent spread
4. **Remediate**: Patch vulnerabilities and update configurations
5. **Recovery**: Restore services with security fixes

### Forensics

```bash
# Collect forensic data
kubectl get events --sort-by=.metadata.creationTimestamp --all-namespaces > events.log
kubectl logs --previous deployment/listings-api -n kubeestatehub > app.log
kubectl describe pod suspicious-pod -n kubeestatehub > pod-details.yaml
```

## Security Automation

### Automated Security Checks

```bash
# Regular security validation
kubectl apply --dry-run=server -f manifests/security/
polaris audit --format=json kubeestatehub > security-report.json
```

### Continuous Compliance

```yaml
# Automated compliance checking
apiVersion: batch/v1
kind: CronJob
metadata:
  name: security-compliance-check
  namespace: kubeestatehub
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: compliance-checker
              image: aquasec/kube-bench:latest
              command: ["kube-bench", "run", "--json"]
              volumeMounts:
                - name: results
                  mountPath: /results
          volumes:
            - name: results
              persistentVolumeClaim:
                claimName: compliance-results-pvc
          restartPolicy: OnFailure
```

## Security Metrics and Monitoring

### Security Dashboards

```yaml
# Security metrics for Grafana
- Security events by severity
- RBAC violations
- Network policy denials
- Failed authentication attempts
- Pod security standard violations
```

### Security Alerts

```yaml
# Prometheus alerting rules
- alert: PrivilegedPodDetected
  expr: increase(falco_events{rule_name="Privileged Pod Created"}[5m]) > 0
  labels:
    severity: critical
  annotations:
    summary: "Privileged pod detected"

- alert: NetworkPolicyViolation
  expr: increase(network_policy_drops_total[5m]) > 10
  labels:
    severity: warning
  annotations:
    summary: "High number of network policy violations"
```

This security guide provides comprehensive protection for KubeEstateHub across all layers of the Kubernetes stack, from container security to network policies and data protection.
