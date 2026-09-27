from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from realestate_sync_operator.resources import (
    OperatorConfig,
    SpecError,
    build_cronjob,
    derive_status,
    job_args,
    parse_duration,
)

CFG = OperatorConfig(image="ghcr.io/example/analytics-worker:2.0.0")
SPEC = {
    "source": {
        "type": "csv",
        "endpoint": "https://feeds.example.com/x.csv",
        "credentials": {"secretRef": {"name": "feed", "key": "token"}},
    },
    "schedule": "0 2 * * *",
    "syncConfig": {
        "batchSize": 500,
        "retryLimit": 2,
        "timeout": "1h30m",
        "maxFailedRecords": 5,
        "filters": {
            "propertyTypes": ["residential", "land"],
            "priceRange": {"min": 1, "max": 9},
            "location": {"city": "Austin", "state": "TX"},
        },
    },
}
NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("value", "seconds"), [("45m", 2700), ("1h30m", 5400), ("90s", 90), ("1.5h", 5400)]
)
def test_parse_duration(value, seconds):
    assert parse_duration(value) == seconds


@pytest.mark.parametrize("value", ["", "10", "5 m", "1d", "500ms", "1h foo"])
def test_parse_duration_rejects(value):
    with pytest.raises(SpecError):
        parse_duration(value)


def test_job_args_translate_filters():
    args = job_args(SPEC)
    assert args[:4] == ["sync", "--source-type", "csv", "--endpoint"]
    joined = " ".join(args)
    assert "--property-types residential,land" in joined
    assert "--price-min 1 --price-max 9" in joined
    assert "--city Austin --state TX" in joined
    assert "--max-failures 5" in joined


def test_job_args_reject_inverted_price_range():
    bad = {**SPEC, "syncConfig": {"filters": {"priceRange": {"min": 10, "max": 1}}}}
    with pytest.raises(SpecError, match="priceRange"):
        job_args(bad)


def test_cronjob_is_hardened_and_mapped():
    cj = build_cronjob("feed", "kubeestatehub", SPEC, CFG)
    assert cj["metadata"]["name"] == "sync-feed"
    spec = cj["spec"]
    assert spec["schedule"] == "0 2 * * *"
    assert spec["concurrencyPolicy"] == "Forbid"
    job = spec["jobTemplate"]["spec"]
    assert job["backoffLimit"] == 2
    assert job["activeDeadlineSeconds"] == 5400
    pod = job["template"]["spec"]
    assert pod["automountServiceAccountToken"] is False
    assert pod["securityContext"]["runAsNonRoot"] is True
    container = pod["containers"][0]
    assert container["image"] == CFG.image
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["capabilities"] == {"drop": ["ALL"]}
    env = {e["name"]: e for e in container["env"]}
    assert env["SOURCE_API_TOKEN"]["valueFrom"]["secretKeyRef"] == {"name": "feed", "key": "token"}
    assert env["DATABASE_URL"]["valueFrom"]["secretKeyRef"]["name"] == "db-secret"


def test_cronjob_defaults_and_name_truncation():
    spec = {"source": {"type": "api", "endpoint": "https://x"}, "schedule": "@hourly"}
    cj = build_cronjob("a" * 80, "ns", spec, CFG)
    assert len(cj["metadata"]["name"]) <= 52  # CronJob names must leave room for job suffixes
    assert cj["spec"]["jobTemplate"]["spec"]["activeDeadlineSeconds"] == 1800
    names = [
        e["name"]
        for e in cj["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["env"]
    ]
    assert "SOURCE_API_TOKEN" not in names


@pytest.mark.parametrize(
    ("status", "suspended", "phase", "ready"),
    [
        (None, False, "Pending", "True"),
        ({}, True, "Paused", "False"),
        (
            {"active": [{"name": "j"}], "lastScheduleTime": "2026-01-01T00:00:00Z"},
            False,
            "Running",
            "True",
        ),
        (
            {
                "lastScheduleTime": "2026-01-01T02:00:00Z",
                "lastSuccessfulTime": "2026-01-01T02:03:00Z",
            },
            False,
            "Completed",
            "True",
        ),
        (
            {
                "lastScheduleTime": "2026-01-02T02:00:00Z",
                "lastSuccessfulTime": "2026-01-01T02:03:00Z",
            },
            False,
            "Failed",
            "False",
        ),
    ],
)
def test_derive_status(status, suspended, phase, ready):
    out = derive_status(status, suspended=suspended, generation=3, now=NOW)
    assert out["phase"] == phase
    assert out["conditions"][0]["status"] == ready
    assert out["observedGeneration"] == 3


def test_example_resources_reconcile_and_match_crd_enums():
    root = Path(__file__).resolve().parents[3] / "manifests"
    crd = yaml.safe_load((root / "components" / "operator" / "crd.yaml").read_text())
    schema = crd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"][
        "properties"
    ]
    allowed = set(schema["source"]["properties"]["type"]["enum"])
    for cr in yaml.safe_load_all((root / "examples" / "realestatesync.yaml").read_text()):
        assert cr["spec"]["source"]["type"] in allowed
        cj = build_cronjob(cr["metadata"]["name"], cr["metadata"]["namespace"], cr["spec"], CFG)
        assert cj["spec"]["suspend"] == cr["spec"].get("suspend", False)
