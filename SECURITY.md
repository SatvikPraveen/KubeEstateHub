# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 2.x | yes |
| 1.x | no. It was never deployable as published; upgrade to 2.x |

## Reporting a vulnerability

Report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/SatvikPraveen/KubeEstateHub/security/advisories/new)
or by email to satvikpraveen707@gmail.com. Please include affected components, versions
or commits, and reproduction steps. You can expect an acknowledgement within 3 working
days and a fix or mitigation plan within 30 days for confirmed high-severity issues.

## What is in place

The [threat model](docs/security/threat-model.md) covers the controls and residual risks.
Release images are signed with cosign (keyless, GitHub OIDC) and carry SBOM and SLSA
provenance attestations:

```bash
cosign verify ghcr.io/satvikpraveen/kubeestatehub/listings-api:main \
  --certificate-identity-regexp 'https://github.com/SatvikPraveen/KubeEstateHub/.github/workflows/images.yaml@.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```
