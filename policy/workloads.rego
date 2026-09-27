# Workload hardening rules, evaluated per rendered manifest document.
#   conftest test --policy policy --namespace kubernetes.workloads rendered.yaml
package kubernetes.workloads

import rego.v1

workload_kinds := {"Deployment", "StatefulSet", "DaemonSet", "Job", "ReplicaSet"}

pod_spec := input.spec.template.spec if workload_kinds[input.kind]

pod_spec := input.spec.jobTemplate.spec.template.spec if input.kind == "CronJob"

pod_meta := input.spec.template.metadata if workload_kinds[input.kind]

pod_meta := input.spec.jobTemplate.spec.template.metadata if input.kind == "CronJob"

containers contains c if some c in pod_spec.containers

containers contains c if some c in pod_spec.initContainers

name := sprintf("%s/%s", [input.kind, input.metadata.name])

deny contains msg if {
	some c in containers
	not c.resources.requests.cpu
	msg := sprintf("%s: container %q must request CPU", [name, c.name])
}

deny contains msg if {
	some c in containers
	not c.resources.limits.memory
	msg := sprintf("%s: container %q must set a memory limit", [name, c.name])
}

deny contains msg if {
	some c in containers
	not c.securityContext.allowPrivilegeEscalation == false
	msg := sprintf("%s: container %q must set allowPrivilegeEscalation=false", [name, c.name])
}

deny contains msg if {
	some c in containers
	not c.securityContext.readOnlyRootFilesystem == true
	msg := sprintf("%s: container %q must use a read-only root filesystem", [name, c.name])
}

deny contains msg if {
	some c in containers
	not "ALL" in object.get(c, ["securityContext", "capabilities", "drop"], [])
	msg := sprintf("%s: container %q must drop ALL capabilities", [name, c.name])
}

deny contains msg if {
	some c in containers
	c.securityContext.privileged == true
	msg := sprintf("%s: container %q must not be privileged", [name, c.name])
}

deny contains msg if {
	pod_spec
	not pod_spec.securityContext.runAsNonRoot == true
	msg := sprintf("%s: pod must set securityContext.runAsNonRoot=true", [name])
}

deny contains msg if {
	pod_spec
	not pod_spec.securityContext.seccompProfile.type == "RuntimeDefault"
	msg := sprintf("%s: pod must use the RuntimeDefault seccomp profile", [name])
}

deny contains msg if {
	some field in ["hostNetwork", "hostPID", "hostIPC"]
	pod_spec[field] == true
	msg := sprintf("%s: %s is forbidden", [name, field])
}

deny contains msg if {
	some v in pod_spec.volumes
	v.hostPath
	msg := sprintf("%s: hostPath volume %q is forbidden", [name, v.name])
}

deny contains msg if {
	some c in containers
	not pinned(c.image)
	msg := sprintf("%s: container %q image %q must be pinned to a non-latest tag or digest", [name, c.name, c.image])
}

pinned(image) if contains(image, "@sha256:")

pinned(image) if {
	parts := split(image, "/")
	last := parts[count(parts) - 1]
	contains(last, ":")
	not endswith(image, ":latest")
}

# Only the operator talks to the Kubernetes API.
deny contains msg if {
	pod_spec
	not pod_meta.labels["app.kubernetes.io/component"] == "operator"
	not pod_spec.automountServiceAccountToken == false
	msg := sprintf("%s: pod must set automountServiceAccountToken=false", [name])
}

# Long-running services must be health-checked.
deny contains msg if {
	input.kind in {"Deployment", "StatefulSet"}
	some c in pod_spec.containers
	not c.livenessProbe
	msg := sprintf("%s: container %q needs a livenessProbe", [name, c.name])
}

deny contains msg if {
	input.kind in {"Deployment", "StatefulSet"}
	not pod_meta.labels["app.kubernetes.io/component"] == "operator"
	some c in pod_spec.containers
	not c.readinessProbe
	msg := sprintf("%s: container %q needs a readinessProbe", [name, c.name])
}

# Recommended labels make ownership, dashboards and network policies work.
deny contains msg if {
	pod_spec
	not pod_meta.labels["app.kubernetes.io/name"]
	msg := sprintf("%s: pod template must carry app.kubernetes.io/name", [name])
}
