package kubernetes.rbac

import rego.v1

role_kinds := {"Role", "ClusterRole"}

deny contains msg if {
	role_kinds[input.kind]
	some rule in input.rules
	some field in ["verbs", "resources", "apiGroups"]
	"*" in rule[field]
	msg := sprintf("%s/%s: wildcard in %s is forbidden", [input.kind, input.metadata.name, field])
}

deny contains msg if {
	role_kinds[input.kind]
	some rule in input.rules
	"secrets" in rule.resources
	msg := sprintf("%s/%s: application roles must not read Secrets", [input.kind, input.metadata.name])
}

deny contains msg if {
	input.kind in {"ClusterRoleBinding", "RoleBinding"}
	input.roleRef.name == "cluster-admin"
	msg := sprintf("%s/%s: binding to cluster-admin is forbidden", [input.kind, input.metadata.name])
}

deny contains msg if {
	role_kinds[input.kind]
	some rule in input.rules
	"pods" in rule.resources
	some verb in ["create", "update", "patch"]
	verb in rule.verbs
	msg := sprintf("%s/%s: creating or modifying pods directly is forbidden", [input.kind, input.metadata.name])
}
