package kubernetes.combined_test

import rego.v1

import data.kubernetes.combined

deny_all := {"kind": "NetworkPolicy", "metadata": {"name": "deny"}, "spec": {"podSelector": {}, "policyTypes": ["Ingress", "Egress"]}}

allow_api := {"kind": "NetworkPolicy", "metadata": {"name": "api"}, "spec": {"podSelector": {"matchLabels": {"app.kubernetes.io/name": "api"}}}}

deployment(replicas) := {
	"kind": "Deployment",
	"metadata": {"name": "api"},
	"spec": {"replicas": replicas, "template": {"metadata": {"labels": {"app.kubernetes.io/name": "api"}}, "spec": {"containers": [{"name": "c", "env": [{"name": "X", "valueFrom": {"secretKeyRef": {"name": "db-secret", "key": "k"}}}]}]}}},
}

pdb := {"kind": "PodDisruptionBudget", "metadata": {"name": "api"}, "spec": {"selector": {"matchLabels": {"app.kubernetes.io/name": "api"}}}}

external_secret := {"kind": "ExternalSecret", "metadata": {"name": "db"}, "spec": {"target": {"name": "db-secret"}}}

limit_range := {"kind": "LimitRange", "metadata": {"name": "defaults"}, "spec": {"limits": [{
	"type": "Container",
	"min": {"cpu": "10m", "memory": "16Mi"},
	"max": {"cpu": "4", "memory": "4Gi"},
	"default": {"cpu": "1", "memory": "256Mi"},
	"defaultRequest": {"cpu": "50m", "memory": "64Mi"},
}]}}

quota := {"kind": "ResourceQuota", "metadata": {"name": "quota"}, "spec": {"hard": {
	"requests.cpu": "8", "requests.memory": "16Gi", "limits.cpu": "64", "limits.memory": "32Gi",
}}}

guard_rails := [limit_range, quota]

wrap(docs) := [{"path": "x", "contents": d} | some d in array.concat(guard_rails, docs)]

wrap_raw(docs) := [{"path": "x", "contents": d} | some d in docs]

test_complete_overlay_passes if {
	count(combined.deny) == 0 with input as wrap([deny_all, allow_api, deployment(2), pdb, external_secret])
}

test_missing_limit_range if {
	some msg in combined.deny with input as wrap_raw([quota, deny_all, allow_api, deployment(1), external_secret])
	contains(msg, "LimitRange")
}

test_limit_range_without_cpu_default if {
	lr := json.patch(limit_range, [{"op": "remove", "path": "/spec/limits/0/default/cpu"}])
	some msg in combined.deny with input as wrap_raw([lr, quota, deny_all, allow_api, deployment(1), external_secret])
	contains(msg, "LimitRange")
}

test_quota_without_cpu_limit if {
	rq := json.patch(quota, [{"op": "remove", "path": "/spec/hard/limits.cpu"}])
	some msg in combined.deny with input as wrap_raw([limit_range, rq, deny_all, allow_api, deployment(1), external_secret])
	contains(msg, "ResourceQuota")
}

test_missing_default_deny if {
	"namespace must have a default-deny-all NetworkPolicy covering ingress and egress" in combined.deny with input as wrap([allow_api, deployment(1), external_secret])
}

test_unselected_deployment if {
	some msg in combined.deny with input as wrap([deny_all, deployment(1), external_secret])
	contains(msg, "not selected by any NetworkPolicy")
}

test_replicated_without_pdb if {
	some msg in combined.deny with input as wrap([deny_all, allow_api, deployment(3), external_secret])
	contains(msg, "no PodDisruptionBudget")
}

test_missing_secret if {
	some msg in combined.deny with input as wrap([deny_all, allow_api, deployment(1)])
	contains(msg, "db-secret")
}
