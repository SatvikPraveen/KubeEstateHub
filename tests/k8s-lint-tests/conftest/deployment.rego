# File location: tests/k8s-lint-tests/conftest/deployment.rego
# Open Policy Agent rules for Deployment validation

package kubernetes.deployment

# Deny deployments without resource limits
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.resources.limits.memory
  msg := sprintf("Container '%s' must have memory limits defined", [container.name])
}

deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.resources.limits.cpu
  msg := sprintf("Container '%s' must have CPU limits defined", [container.name])
}

# Deny deployments without resource requests
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.resources.requests.memory
  msg := sprintf("Container '%s' must have memory requests defined", [container.name])
}

deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.resources.requests.cpu
  msg := sprintf("Container '%s' must have CPU requests defined", [container.name])
}

# Deny deployments without liveness probes
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.livenessProbe
  msg := sprintf("Container '%s' must have a liveness probe", [container.name])
}

# Deny deployments without readiness probes
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.readinessProbe
  msg := sprintf("Container '%s' must have a readiness probe", [container.name])
}

# Deny deployments using latest tag
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  endswith(container.image, ":latest")
  msg := sprintf("Container '%s' should not use 'latest' tag", [container.name])
}

# Deny deployments without image pull policy
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.imagePullPolicy
  msg := sprintf("Container '%s' must specify imagePullPolicy", [container.name])
}

# Deny deployments with privileged containers
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  container.securityContext.privileged == true
  msg := sprintf("Container '%s' should not run as privileged", [container.name])
}

# Deny deployments without security context
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.securityContext
  msg := sprintf("Container '%s' must have a security context", [container.name])
}

# Deny deployments running as root
deny[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  container.securityContext.runAsUser == 0
  msg := sprintf("Container '%s' should not run as root (UID 0)", [container.name])
}

# Require specific labels
required_labels := {"app", "version", "component"}

deny[msg] {
  input.kind == "Deployment"
  missing_labels := required_labels - set(object.keys(input.metadata.labels))
  count(missing_labels) > 0
  msg := sprintf("Deployment must have labels: %v", [missing_labels])
}

# Require replica count >= 2 for production
deny[msg] {
  input.kind == "Deployment"
  input.metadata.namespace == "kubeestatehub-prod"
  input.spec.replicas < 2
  msg := "Production deployments must have at least 2 replicas"
}

# Validate pod disruption budget exists for multi-replica deployments
warn[msg] {
  input.kind == "Deployment"
  input.spec.replicas > 1
  not input.metadata.annotations["pdb.kubernetes.io/created"]
  msg := sprintf("Deployment '%s' with %d replicas should have a PodDisruptionBudget", [input.metadata.name, input.spec.replicas])
}

# Validate proper resource ratios (CPU:Memory should be reasonable)
warn[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  
  # Convert memory to MB for comparison
  memory_limit := to_number(trim_suffix(container.resources.limits.memory, "Mi"))
  cpu_limit := to_number(trim_suffix(container.resources.limits.cpu, "m")) / 1000
  
  # CPU to Memory ratio should be between 1:2 and 1:8 (1 CPU core : 2-8 GB RAM)
  ratio := memory_limit / (cpu_limit * 1000)
  ratio < 2
  msg := sprintf("Container '%s' has low memory to CPU ratio (%.2f:1). Consider increasing memory.", [container.name, ratio])
}

warn[msg] {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  
  memory_limit := to_number(trim_suffix(container.resources.limits.memory, "Mi"))
  cpu_limit := to_number(trim_suffix(container.resources.limits.cpu, "m")) / 1000
  
  ratio := memory_limit / (cpu_limit * 1000)
  ratio > 8
  msg := sprintf("Container '%s' has high memory to CPU ratio (%.2f:1). Consider reducing memory or increasing CPU.", [container.name, ratio])
}

# Validate environment-specific rules
deny[msg] {
  input.kind == "Deployment"
  input.metadata.namespace == "kubeestatehub-dev"
  container := input.spec.template.spec.containers[_]
  to_number(trim_suffix(container.resources.limits.memory, "Mi")) > 1000
  msg := sprintf("Development environment: Container '%s' memory limit should not exceed 1Gi", [container.name])
}