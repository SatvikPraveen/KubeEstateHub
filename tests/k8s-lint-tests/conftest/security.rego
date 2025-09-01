# File location: tests/k8s-lint-tests/conftest/security.rego
# Open Policy Agent security rules for Kubernetes resources

package kubernetes.security

# Security Context Rules
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.securityContext.runAsNonRoot
  msg := sprintf("Container '%s' must set runAsNonRoot: true", [container.name])
}

deny[msg] {
  input.kind == "Deployment" 
  container := input.spec.template.spec.containers[_]
  container.securityContext.allowPrivilegeEscalation == true
  msg := sprintf("Container '%s' must not allow privilege escalation", [container.name])
}

deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.securityContext.readOnlyRootFilesystem
  msg := sprintf("Container '%s' should use read-only root filesystem", [container.name])
}

deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  "SYS_ADMIN" in container.securityContext.capabilities.add
  msg := sprintf("Container '%s' should not have SYS_ADMIN capability", [container.name])
}

# Pod Security Standards
deny[msg] {
  input.kind == "Deployment"
  input.spec.template.spec.hostNetwork == true
  msg := "Pods should not use host network"
}

deny[msg] {
  input.kind == "Deployment" 
  input.spec.template.spec.hostPID == true
  msg := "Pods should not use host PID namespace"
}

deny[msg] {
  input.kind == "Deployment"
  input.spec.template.spec.hostIPC == true
  msg := "Pods should not use host IPC namespace"
}

# Volume Security
deny[msg] {
  input.kind == "Deployment"
  volume := input.spec.template.spec.volumes[_]
  volume.hostPath
  msg := sprintf("Volume '%s' should not use hostPath", [volume.name])
}

deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  volume_mount := container.volumeMounts[_]
  volume_mount.mountPath == "/"
  msg := sprintf("Container '%s' should not mount volumes at root path", [container.name])
}

# Secret and ConfigMap Security
deny[msg] {
  input.kind == "Secret"
  input.type == "Opaque"
  not input.metadata.annotations["kubernetes.io/managed-by"]
  msg := "Secrets should be managed by a controller or operator"
}

warn[msg] {
  input.kind == "ConfigMap"
  value := input.data[key]
  regex.match("(?i)(password|secret|key|token)", key)
  msg := sprintf("ConfigMap contains potentially sensitive key '%s', consider using Secret instead", [key])
}

# Service Account Security
deny[msg] {
  input.kind == "Deployment"
  not input.spec.template.spec.serviceAccountName
  msg := "Deployment should specify a service account"
}

deny[msg] {
  input.kind == "ServiceAccount"
  input.automountServiceAccountToken == true
  input.metadata.name != "default"
  not input.metadata.annotations["kubernetes.io/enforce-mountable-secrets"]
  msg := sprintf("ServiceAccount '%s' should not auto-mount tokens without restrictions", [input.metadata.name])
}

# Network Security
deny[msg] {
  input.kind == "Service"
  input.spec.type == "LoadBalancer"
  not input.metadata.annotations["service.beta.kubernetes.io/aws-load-balancer-internal"]
  input.metadata.namespace != "kube-system"
  msg := "LoadBalancer services should be internal unless explicitly required"
}

deny[msg] {
  input.kind == "Ingress"
  not input.spec.tls
  msg := "Ingress should enforce TLS/SSL"
}

deny[msg] {
  input.kind == "NetworkPolicy"
  policy_type := input.spec.policyTypes[_]
  policy_type == "Ingress"
  count(input.spec.ingress) == 0
  msg := "NetworkPolicy with Ingress type should define ingress rules"
}

# RBAC Security
deny[msg] {
  input.kind == "ClusterRole"
  rule := input.rules[_]
  "*" in rule.resources
  "*" in rule.verbs
  msg := sprintf("ClusterRole '%s' should not have wildcard permissions", [input.metadata.name])
}

deny[msg] {
  input.kind == "Role"
  rule := input.rules[_]
  "secrets" in rule.resources
  "get" in rule.verbs
  rule.resourceNames == []
  msg := sprintf("Role '%s' should specify resourceNames when accessing secrets", [input.metadata.name])
}

# Image Security
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not regex.match("^.+/.+:.+$", container.image)
  msg := sprintf("Container '%s' image should include registry and tag", [container.name])
}

deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  startswith(container.image, "docker.io/library/")
  msg := sprintf("Container '%s' should not use Docker Hub official images directly", [container.name])
}

# Resource Limits Security
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.resources.limits
  msg := sprintf("Container '%s' must define resource limits", [container.name])
}

warn[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  memory_limit := to_number(trim_suffix(container.resources.limits.memory, "Mi"))
  memory_limit > 8000
  msg := sprintf("Container '%s' has very high memory limit (>8Gi), verify if necessary", [container.name])
}

# Environment Variable Security
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  env := container.env[_]
  regex.match("(?i)(password|secret|key|token)", env.name)
  not env.valueFrom.secretKeyRef
  msg := sprintf("Environment variable '%s' appears sensitive, should reference a Secret", [env.name])
}

# Pod Security Context
deny[msg] {
  input.kind == "Deployment"
  not input.spec.template.spec.securityContext.runAsNonRoot
  msg := "Pod should set runAsNonRoot: true in security context"
}

deny[msg] {
  input.kind == "Deployment"
  input.spec.template.spec.securityContext.fsGroup == 0
  msg := "Pod should not use root group (fsGroup: 0)"
}

# Admission Controller Integration
deny[msg] {
  input.kind == "Deployment"
  not input.metadata.annotations["admission.policy/validated"]
  input.metadata.namespace != "kube-system"
  msg := "Deployment should be validated by admission controllers"
}

# Security Scanning
warn[msg] {
  input.kind == "Deployment"
  not input.metadata.annotations["security.scan/last-scanned"]
  msg := sprintf("Deployment '%s' images should be regularly security scanned", [input.metadata.name])
}

# Compliance Labels
required_security_labels := {"security.policy/level", "compliance.framework/required"}

warn[msg] {
  input.kind == "Deployment"
  input.metadata.namespace == "kubeestatehub-prod"
  missing_labels := required_security_labels - set(object.keys(input.metadata.labels))
  count(missing_labels) > 0
  msg := sprintf("Production deployment should have security labels: %v", [missing_labels])
}