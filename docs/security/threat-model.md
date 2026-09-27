# Threat model

This uses the STRIDE method over the data flows in [../architecture.md](../architecture.md).
Assets, in order of sensitivity:

1. Database credentials and the API write token.
2. Integrity of listings and valuations.
3. Availability of the API.
4. Integrity of the supply chain: images, chart and CI.

| # | Threat (STRIDE) | Where | Mitigation | Verified by |
|---|---|---|---|---|
| 1 | **S**poofed writer creates or edits listings | API write routes | Bearer token (`API_WRITE_TOKEN`) compared in constant time; separate write rate limit | unit tests (`TestAuthAndLimits`) |
| 2 | **T**ampering via SQL injection | API filters, sync ingestion | All values parameterised; column and sort names come from allow-lists; pydantic validation rejects unknown fields and parameters | unit test `test_build_filters_is_parameterised`, strict schemas |
| 3 | **T**ampering: stored XSS from listing titles | dashboard | DOM built with `textContent` only; strict CSP (`script-src 'self' cdnjs`), SRI on CDN assets, `X-Frame-Options: DENY` | nginx headers asserted in e2e |
| 4 | **T**ampering with schema history | migrations | SHA-256 per applied migration; the runner refuses edited files | CI integration job tamper test |
| 5 | **T**ampering: malicious or garbage external feed | sync jobs | pydantic row validation, `maxFailedRecords` threshold, upsert by MLS number, HTTPS only (CRD pattern), egress limited to public 443 | unit tests (sync), NetworkPolicy |
| 6 | **R**epudiation | writes and batch results | request-ID access logs; `model_runs` provenance for every derived number | integration tests |
| 7 | **I**nformation disclosure: credentials in git | manifests, chart | no committed secrets; External Secrets in staging/production; gitleaks over full history in CI | `security` workflow |
| 8 | **I**nformation disclosure: lateral movement | cluster network | default-deny NetworkPolicies with an explicit allow per flow; sync-job egress excludes RFC 1918 and link-local ranges, which blocks SSRF to cluster and metadata IPs | conftest cross-resource policy; kind e2e |
| 9 | **I**nformation disclosure: service-account token theft | pods | `automountServiceAccountToken: false` everywhere except the operator; operator RBAC is namespaced and least-privilege | conftest `kubernetes.rbac`, kube-linter |
| 10 | **D**enial of service | API | per-client and write rate limits, 256 KiB body limit, statement timeout, HPA, PDB; the rate limiter fails open if Redis is down | load test, chaos experiments |
| 11 | **E**levation of privilege: container escape | all pods | PSA `restricted`, non-root UIDs, read-only rootfs, all capabilities dropped, seccomp RuntimeDefault; admission policy rejects deviations | conftest, admission policy (kind e2e) |
| 12 | Supply chain: compromised dependency or image | build | pinned dependencies (updated manually), Trivy gate on fixable HIGH/CRITICAL, SBOM + SLSA provenance, cosign keyless signatures; actions pinned by commit SHA | `images` workflow |
| 13 | Supply chain: malicious CI change | workflows | least-privilege `permissions:` per job; `id-token` only where signing needs it; CodeQL on the `actions` language | `security` workflow |

## Residual risks and next steps

* **In-cluster TLS.** Traffic between services is plaintext inside the cluster. Add a
  service mesh or mTLS (Linkerd or Istio ambient), or enable TLS on PostgreSQL, if the
  cluster network is not trusted.
* **Signature verification.** Images are signed but signatures are not *verified* at
  admission. Add a Sigstore policy-controller or Kyverno `verifyImages` policy for the
  `kubeestatehub` namespace.
* **Single shared write token.** For multi-user write access, replace it with OIDC (for
  example oauth2-proxy at the Ingress) and per-user audit logs.
* **Sync jobs reach arbitrary public HTTPS endpoints.** An egress gateway with an
  allow-list per `RealEstateSync` would tighten this.
