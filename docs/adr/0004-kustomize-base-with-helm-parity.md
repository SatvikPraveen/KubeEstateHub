# 0004. One kustomize base plus a Helm chart, with CI-enforced parity

* Status: accepted (2026-09)

## Context
v1 shipped raw manifests, kustomize overlays and a Helm chart that had drifted apart.
None of them rendered.

## Decision
The kustomize base plus components are the reference. The Helm chart renders the same
resources with fixed names. Files that must be identical, such as SQL, rules, dashboards,
the CRD, the admission policy and the backup job, are generated into the chart by
`hack/generate.py`. `hack/validate.sh` fails if the production overlay and
`values-production.yaml` render different resource sets, or if any generated file is
stale.

## Consequences
* Users can choose either tool without behavioural differences.
* Resource names are not release-prefixed, so a namespace holds one installation. This is
  required anyway because nginx proxies to the Service `listings-api`.
* Chart templates for hand-written resources still need care. The parity check catches
  missing or extra resources, not field-level drift.
