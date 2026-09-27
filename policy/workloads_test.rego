package kubernetes.workloads_test

import rego.v1

import data.kubernetes.workloads

good := {
	"kind": "Deployment",
	"metadata": {"name": "api"},
	"spec": {"template": {
		"metadata": {"labels": {"app.kubernetes.io/name": "api"}},
		"spec": {
			"automountServiceAccountToken": false,
			"securityContext": {"runAsNonRoot": true, "seccompProfile": {"type": "RuntimeDefault"}},
			"containers": [{
				"name": "api",
				"image": "ghcr.io/x/api:1.2.3",
				"resources": {"requests": {"cpu": "100m"}, "limits": {"memory": "128Mi"}},
				"securityContext": {
					"allowPrivilegeEscalation": false,
					"readOnlyRootFilesystem": true,
					"capabilities": {"drop": ["ALL"]},
				},
				"livenessProbe": {"httpGet": {"path": "/livez", "port": 8080}},
				"readinessProbe": {"httpGet": {"path": "/readyz", "port": 8080}},
			}],
		},
	}},
}

test_compliant_deployment_passes if {
	count(workloads.deny) == 0 with input as good
}

test_latest_tag_denied if {
	bad := json.patch(good, [{"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "nginx:latest"}])
	some msg in workloads.deny with input as bad
	contains(msg, "must be pinned")
}

test_untagged_registry_port_image_denied if {
	bad := json.patch(good, [{"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "registry:5000/app"}])
	some msg in workloads.deny with input as bad
	contains(msg, "must be pinned")
}

test_digest_allowed if {
	ok := json.patch(good, [{"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "app@sha256:abc"}])
	count(workloads.deny) == 0 with input as ok
}

test_writable_rootfs_denied if {
	bad := json.patch(good, [{"op": "replace", "path": "/spec/template/spec/containers/0/securityContext/readOnlyRootFilesystem", "value": false}])
	some msg in workloads.deny with input as bad
	contains(msg, "read-only root filesystem")
}

test_host_path_denied if {
	bad := json.patch(good, [{"op": "add", "path": "/spec/template/spec/volumes", "value": [{"name": "sock", "hostPath": {"path": "/var/run/docker.sock"}}]}])
	some msg in workloads.deny with input as bad
	contains(msg, "hostPath")
}

test_missing_memory_limit_denied if {
	bad := json.patch(good, [{"op": "remove", "path": "/spec/template/spec/containers/0/resources/limits"}])
	some msg in workloads.deny with input as bad
	contains(msg, "memory limit")
}

test_token_mount_denied_for_non_operator if {
	bad := json.patch(good, [{"op": "remove", "path": "/spec/template/spec/automountServiceAccountToken"}])
	some msg in workloads.deny with input as bad
	contains(msg, "automountServiceAccountToken")
}

test_operator_may_mount_token if {
	op := json.patch(good, [
		{"op": "remove", "path": "/spec/template/spec/automountServiceAccountToken"},
		{"op": "add", "path": "/spec/template/metadata/labels/app.kubernetes.io~1component", "value": "operator"},
	])
	count(workloads.deny) == 0 with input as op
}

test_cronjob_pod_spec_is_checked if {
	cj := {
		"kind": "CronJob",
		"metadata": {"name": "job"},
		"spec": {"jobTemplate": {"spec": {"template": good.spec.template}}},
	}
	count(workloads.deny) == 0 with input as cj
	bad := json.patch(cj, [{"op": "add", "path": "/spec/jobTemplate/spec/template/spec/hostNetwork", "value": true}])
	some msg in workloads.deny with input as bad
	contains(msg, "hostNetwork")
}

test_non_workloads_ignored if {
	count(workloads.deny) == 0 with input as {"kind": "ConfigMap", "metadata": {"name": "x"}}
}
