package kubernetes.rbac_test

import rego.v1

import data.kubernetes.rbac

test_wildcards_denied if {
	role := {"kind": "ClusterRole", "metadata": {"name": "r"}, "rules": [{"apiGroups": [""], "resources": ["*"], "verbs": ["get"]}]}
	count(rbac.deny) == 1 with input as role
}

test_secret_access_denied if {
	role := {"kind": "Role", "metadata": {"name": "r"}, "rules": [{"apiGroups": [""], "resources": ["secrets"], "verbs": ["get"]}]}
	count(rbac.deny) == 1 with input as role
}

test_least_privilege_role_allowed if {
	role := {"kind": "Role", "metadata": {"name": "r"}, "rules": [{"apiGroups": ["batch"], "resources": ["cronjobs"], "verbs": ["get", "create"]}]}
	count(rbac.deny) == 0 with input as role
}

test_cluster_admin_binding_denied if {
	b := {"kind": "ClusterRoleBinding", "metadata": {"name": "b"}, "roleRef": {"name": "cluster-admin"}}
	count(rbac.deny) == 1 with input as b
}
