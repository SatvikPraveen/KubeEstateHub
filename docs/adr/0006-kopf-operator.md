# 0006. RealEstateSync operator in Python (kopf)

* Status: accepted (2026-09)

## Context
The CRD and an operator Deployment existed, but no operator code did. The sync logic
itself (validation, upsert) is Python and shared with the analytics worker.

## Decision
Implement the operator with kopf. Reconciliation renders a CronJob from the spec with a
pure function (unit-tested without a cluster) and adopts it through ownerReferences. A
timer mirrors CronJob status into the CR's status subresource and repairs drift.

## Consequences
* One language across services, and sync jobs reuse the validated ingestion code.
* A Go/controller-runtime operator would scale further and offer typed clients. At this
  size, one replica in standalone mode (`Recreate` strategy) is sufficient.
* The operator needs cluster-wide read access to CRDs and namespaces. Everything else is
  namespaced.
