"""Command-line entry point: ``python -m analytics_worker <command>``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

from . import __version__, logconfig


def _repo():
    from .repository import PostgresRepository

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("DATABASE_URL is not set")
    return PostgresRepository(dsn)


def _push_metrics(result_metrics: dict, job: str) -> None:
    gateway = os.getenv("PUSHGATEWAY_URL")
    if not gateway:
        return
    from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

    registry = CollectorRegistry()
    Gauge(
        "kubeestatehub_pipeline_last_success_timestamp_seconds",
        "Last successful run",
        registry=registry,
    ).set_to_current_time()
    Gauge("kubeestatehub_pipeline_duration_seconds", "Pipeline wall time", registry=registry).set(
        result_metrics.get("duration_seconds", 0)
    )
    cv = result_metrics.get("cross_validation", {}).get("hedonic_conformal", {})
    for key in ("median_ape", "coverage"):
        if key in cv:
            Gauge(
                f"kubeestatehub_avm_{key}", f"Hedonic AVM cross-validated {key}", registry=registry
            ).set(cv[key])
    push_to_gateway(gateway, job=job, registry=registry)


def cmd_pipeline(args: argparse.Namespace) -> int:
    from .pipeline import PipelineConfig, run_pipeline

    cfg = PipelineConfig(
        as_of=args.as_of,
        seed=args.seed,
        cv_folds=args.folds,
        alpha=args.alpha,
        min_sales_for_model=args.min_sales,
    )
    result = run_pipeline(_repo(), cfg, code_version=os.getenv("CODE_VERSION", __version__))
    _push_metrics(result.metrics, "analytics-pipeline")
    print(json.dumps({"run_id": result.run_id, "metrics": result.metrics}, default=str))
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    from .sync import SyncFilters, run_sync

    filters = SyncFilters(
        property_types=frozenset(t for t in (args.property_types or "").split(",") if t),
        price_min=args.price_min,
        price_max=args.price_max,
        city=args.city,
        state=args.state,
    )
    headers = {}
    if token := os.getenv("SOURCE_API_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    result = run_sync(
        _repo(),
        args.source_type,
        args.endpoint,
        batch_size=args.batch_size,
        filters=filters,
        timeout=args.timeout,
        headers=headers,
    )
    print(json.dumps(result.__dict__))
    return 0 if result.failed <= args.max_failures else 1


def cmd_seed(args: argparse.Namespace) -> int:
    from .synthetic import generate_market

    df, _ = generate_market(args.n, seed=args.seed, start=args.start, months=args.months)
    written = _repo().upsert_listings(df.to_dict("records"))
    print(json.dumps({"written": written, "seed": args.seed}))
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from .benchmark import run_benchmark, to_markdown

    result = run_benchmark(
        replications=args.replications, n=args.n, seed=args.seed, folds=args.folds
    )
    print(to_markdown(result) if args.format == "markdown" else json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="analytics_worker", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    pipe = sub.add_parser("pipeline", help="run the market analytics batch pipeline")
    pipe.add_argument("--as-of", type=date.fromisoformat, default=None)
    pipe.add_argument("--seed", type=int, default=int(os.getenv("PIPELINE_SEED", "0")))
    pipe.add_argument("--folds", type=int, default=5)
    pipe.add_argument("--alpha", type=float, default=0.10)
    pipe.add_argument("--min-sales", type=int, default=200)
    pipe.set_defaults(func=cmd_pipeline)

    sync = sub.add_parser("sync", help="ingest listings from an external feed")
    sync.add_argument("--source-type", choices=["csv", "api"], required=True)
    sync.add_argument("--endpoint", required=True)
    sync.add_argument("--batch-size", type=int, default=100)
    sync.add_argument("--timeout", type=float, default=30.0)
    sync.add_argument("--max-failures", type=int, default=0)
    sync.add_argument("--property-types", default="")
    sync.add_argument("--price-min", type=float)
    sync.add_argument("--price-max", type=float)
    sync.add_argument("--city")
    sync.add_argument("--state")
    sync.set_defaults(func=cmd_sync)

    seed = sub.add_parser("seed", help="load a reproducible synthetic market into the database")
    seed.add_argument("--n", type=int, default=3000)
    seed.add_argument("--seed", type=int, default=42)
    seed.add_argument("--start", type=date.fromisoformat, default=date(2024, 10, 1))
    seed.add_argument("--months", type=int, default=24)
    seed.set_defaults(func=cmd_seed)

    bench = sub.add_parser("benchmark", help="Monte Carlo validation on synthetic markets")
    bench.add_argument("--replications", type=int, default=20)
    bench.add_argument("--n", type=int, default=3000)
    bench.add_argument("--seed", type=int, default=42)
    bench.add_argument("--folds", type=int, default=5)
    bench.add_argument("--format", choices=["json", "markdown"], default="json")
    bench.set_defaults(func=cmd_benchmark)
    return p


def main(argv: list[str] | None = None) -> int:
    logconfig.configure()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
