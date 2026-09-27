# Cross-resource invariants over a whole rendered overlay.
#   conftest test --combine --policy policy --namespace kubernetes.combined rendered.yaml
package kubernetes.combined

import rego.v1

docs := [d.contents | some d in input]

by_kind(kind) := [d | some d in docs; d.kind == kind]

deny contains "namespace must have a default-deny-all NetworkPolicy covering ingress and egress" if {
	not default_deny
}

default_deny if {
	some np in by_kind("NetworkPolicy")
	np.spec.podSelector == {}
	"Ingress" in np.spec.policyTypes
	"Egress" in np.spec.policyTypes
	not np.spec.ingress
	not np.spec.egress
}

# Every workload must be selected by at least one allow policy, otherwise default-deny
# silently isolates it.
deny contains msg if {
	some w in by_kind("Deployment")
	app := w.spec.template.metadata.labels["app.kubernetes.io/name"]
	not selected(app)
	msg := sprintf("Deployment/%s is not selected by any NetworkPolicy", [w.metadata.name])
}

selected(app) if {
	some np in by_kind("NetworkPolicy")
	np.spec.podSelector.matchLabels["app.kubernetes.io/name"] == app
}

selected(app) if {
	some np in by_kind("NetworkPolicy")
	some expr in np.spec.podSelector.matchExpressions
	expr.key == "app.kubernetes.io/name"
	expr.operator == "In"
	app in expr.values
}

# Replicated services need a PDB so node drains cannot take them down.
deny contains msg if {
	some w in by_kind("Deployment")
	object.get(w.spec, "replicas", 1) > 1
	app := w.spec.template.metadata.labels["app.kubernetes.io/name"]
	not has_pdb(app)
	msg := sprintf("Deployment/%s has %d replicas but no PodDisruptionBudget", [w.metadata.name, w.spec.replicas])
}

has_pdb(app) if {
	some pdb in by_kind("PodDisruptionBudget")
	pdb.spec.selector.matchLabels["app.kubernetes.io/name"] == app
}

# Every Secret a workload references must be produced by the overlay (Secret or ExternalSecret).
deny contains msg if {
	some ref in secret_refs
	not provided(ref)
	msg := sprintf("Secret %q is referenced but not provided by the overlay", [ref])
}

secret_refs contains ref if {
	some d in docs
	walk(d, [path, value])
	path[count(path) - 1] == "secretKeyRef"
	ref := value.name
	not d.kind == "CustomResourceDefinition"
}

provided(ref) if {
	some s in by_kind("Secret")
	s.metadata.name == ref
}

provided(ref) if {
	some s in by_kind("ExternalSecret")
	s.spec.target.name == ref
}

# Secrets referenced only by operator-generated Jobs are supplied by users per resource.
provided(ref) if not ref in {"db-secret", "api-secret"}
