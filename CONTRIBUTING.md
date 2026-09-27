# Contributing

Thank you for helping. This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## Setup

```bash
make install          # .venv with runtime + dev dependencies (Python 3.12+)
make tools            # pinned Kubernetes tooling into ./bin
pre-commit install    # ruff, yamllint, gitleaks and basic hygiene on every commit
```

## Before opening a pull request

| Change touches | Run |
|---|---|
| Python | `make lint test`; with a database: `DATABASE_URL=… make test-integration` |
| `db/migrations` | add a **new** file (never edit an applied one), bump `REQUIRED_SCHEMA_VERSION`, run `make generate` |
| manifests, chart, policies, alert rules | `make generate validate` |
| anything user-visible | `make e2e`; for cluster-level changes, `make kind-e2e` |
| statistical code | add a test against a known answer (SciPy reference, synthetic ground truth, or a coverage/size simulation) and rerun `make benchmark` if results change |

CI runs all of the above. Every check gates, and nothing is `continue-on-error`.

## Conventions

* **Commits** follow [Conventional Commits](https://www.conventionalcommits.org):
  `feat(api): …`, `fix(operator): …`, `docs: …`. Explain *why* in the body.
* **Python:** ruff formatting (100 columns), type hints, mypy-clean per service, no
  unparameterised SQL.
* **Kubernetes:** every pod must pass `policy/`. Run non-root with a read-only rootfs, no
  capabilities, pinned images, a CPU request and a memory limit. New flows need an
  explicit NetworkPolicy.
* **Observability:** new endpoints get RED metrics automatically. New alerts need a
  runbook section in `docs/operations/runbooks.md` and a `promtool` test.
* **Decisions** that change architecture or methodology get an ADR in `docs/adr/`.

## Reporting issues

* **Bugs:** use GitHub issues with steps to reproduce, expected and actual behaviour, and
  the `X-Request-ID` of failing API calls where relevant.
* **Security issues:** follow [SECURITY.md](SECURITY.md). Do not open a public issue.
