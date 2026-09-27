# 0005. Pod Security Admission plus a CEL ValidatingAdmissionPolicy

* Status: accepted (2026-09)

## Context
v1 defined PodSecurityPolicies, an API removed in Kubernetes 1.25. It also defined
invented `ValidatingAdmissionWebhook` / `MutatingAdmissionWebhook` kinds backed by an
image that never existed.

## Decision
* Label the namespace with Pod Security Admission `restricted` for enforce, audit and
  warn.
* Add platform rules PSA cannot express with a ValidatingAdmissionPolicy (GA in 1.30).
  The rules require pinned image tags or digests, a read-only root filesystem, memory
  limits and CPU requests.
* The policy runs in `Deny` mode in production and `Warn,Audit` in development and
  staging.

## Consequences
* There is no webhook to operate, certificates to rotate, or availability risk from a
  webhook being down. Evaluation happens in the API server.
* The minimum supported Kubernetes version is 1.30.
* The kind e2e test proves the policy denies a PSA-compliant pod that uses `:latest`.
