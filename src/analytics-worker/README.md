# Analytics worker

Batch analytics for KubeEstateHub. It runs as Kubernetes CronJobs, not as a
long-running daemon.

| Command | Purpose | Scheduled by |
|---|---|---|
| `python -m analytics_worker pipeline` | Market indicators, hedonic price index, AVM cross-validation, valuations of open listings | `analytics-pipeline` CronJob (nightly) |
| `python -m analytics_worker sync --source-type csv\|api --endpoint URL` | Validate and upsert listings from an external feed | CronJobs created by the RealEstateSync operator |
| `python -m analytics_worker seed --n 3000 --seed 42` | Load a reproducible synthetic market | Demo / e2e environments |
| `python -m analytics_worker benchmark --format markdown` | Monte Carlo validation of the estimators | Developers, CI |

Every pipeline run inserts a `model_runs` row with code version, seed, parameters and
evaluation metrics; all derived rows reference it. See
[`docs/research/methodology.md`](../../docs/research/methodology.md) for the statistical
details and [`docs/research/results.md`](../../docs/research/results.md) for the validation
study.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | (required) | libpq connection string |
| `PIPELINE_SEED` | `0` | Seed for bootstrap, CV folds and calibration split |
| `CODE_VERSION` | image build arg | Recorded in `model_runs.code_version` |
| `PUSHGATEWAY_URL` | unset | If set, pipeline duration and AVM accuracy are pushed to Prometheus |
| `SOURCE_API_TOKEN` | unset | Bearer token for `sync` against authenticated feeds |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `json` | Structured logging |

## Development

```bash
pip install -r requirements-dev.txt        # from the repository root
pytest tests/unit/analytics                # unit and statistical tests
DATABASE_URL=postgresql://... pytest -m integration tests/integration
```
