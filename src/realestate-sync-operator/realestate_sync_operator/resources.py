"""Pure functions that translate a RealEstateSync spec into Kubernetes objects.

Keeping them free of I/O makes the reconciliation logic unit-testable without a cluster.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

MANAGED_BY = "realestate-sync-operator"
_DURATION = re.compile(r"(\d+(?:\.\d+)?)(ms|s|m|h)")
_UNIT_SECONDS = {"ms": 0.001, "s": 1, "m": 60, "h": 3600}


class SpecError(ValueError):
    """The custom resource is syntactically valid but cannot be reconciled."""


@dataclass(frozen=True)
class OperatorConfig:
    image: str
    database_secret: str = "db-secret"  # noqa: S105 - Secret name, not a secret value
    database_secret_key: str = "database-url"  # noqa: S105 - key name
    service_account: str = "realestate-sync-job"
    successful_jobs_history: int = 3
    failed_jobs_history: int = 3


def parse_duration(value: str) -> int:
    """Go-style duration (``1h30m``, ``45m``, ``90s``) to whole seconds."""
    value = value.strip()
    parts = _DURATION.findall(value)
    if not parts or "".join(n + u for n, u in parts) != value:
        raise SpecError(f"invalid duration {value!r}")
    seconds = sum(float(n) * _UNIT_SECONDS[u] for n, u in parts)
    if seconds < 1:
        raise SpecError(f"duration {value!r} is shorter than one second")
    return int(seconds)


def job_args(spec: dict[str, Any]) -> list[str]:
    source = spec["source"]
    cfg = spec.get("syncConfig", {})
    args = [
        "sync",
        "--source-type",
        source["type"],
        "--endpoint",
        source["endpoint"],
        "--batch-size",
        str(cfg.get("batchSize", 100)),
        "--max-failures",
        str(cfg.get("maxFailedRecords", 0)),
    ]
    filters = cfg.get("filters", {})
    if types := filters.get("propertyTypes"):
        args += ["--property-types", ",".join(types)]
    price = filters.get("priceRange", {})
    if "min" in price:
        args += ["--price-min", str(price["min"])]
    if "max" in price:
        args += ["--price-max", str(price["max"])]
    if "min" in price and "max" in price and price["min"] > price["max"]:
        raise SpecError("syncConfig.filters.priceRange.min exceeds max")
    location = filters.get("location", {})
    if city := location.get("city"):
        args += ["--city", city]
    if state := location.get("state"):
        args += ["--state", state]
    return args


def build_cronjob(
    name: str, namespace: str, spec: dict[str, Any], cfg: OperatorConfig
) -> dict[str, Any]:
    sync_cfg = spec.get("syncConfig", {})
    env: list[dict[str, Any]] = [
        {
            "name": "DATABASE_URL",
            "valueFrom": {
                "secretKeyRef": {"name": cfg.database_secret, "key": cfg.database_secret_key}
            },
        },
        {"name": "LOG_FORMAT", "value": "json"},
    ]
    secret_ref = spec["source"].get("credentials", {}).get("secretRef")
    if secret_ref:
        env.append(
            {
                "name": "SOURCE_API_TOKEN",
                "valueFrom": {
                    "secretKeyRef": {"name": secret_ref["name"], "key": secret_ref["key"]}
                },
            }
        )
    labels = {
        "app.kubernetes.io/name": "realestate-sync",
        "app.kubernetes.io/instance": name,
        "app.kubernetes.io/component": "sync-job",
        "app.kubernetes.io/part-of": "kubeestatehub",
        "app.kubernetes.io/managed-by": MANAGED_BY,
    }
    container = {
        "name": "sync",
        "image": cfg.image,
        "imagePullPolicy": "IfNotPresent",
        "args": job_args(spec),
        "env": env,
        "resources": {
            "requests": {"cpu": "100m", "memory": "256Mi"},
            "limits": {"memory": "512Mi"},
        },
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "runAsNonRoot": True,
            "capabilities": {"drop": ["ALL"]},
        },
        "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}],  # noqa: S108 - emptyDir mount
    }
    return {
        "apiVersion": "batch/v1",
        "kind": "CronJob",
        "metadata": {"name": f"sync-{name}"[:52], "namespace": namespace, "labels": labels},
        "spec": {
            "schedule": spec["schedule"],
            "timeZone": spec.get("timeZone", "Etc/UTC"),
            "suspend": bool(spec.get("suspend", False)),
            "concurrencyPolicy": "Forbid",
            "startingDeadlineSeconds": 300,
            "successfulJobsHistoryLimit": cfg.successful_jobs_history,
            "failedJobsHistoryLimit": cfg.failed_jobs_history,
            "jobTemplate": {
                "metadata": {"labels": labels},
                "spec": {
                    "backoffLimit": int(sync_cfg.get("retryLimit", 3)),
                    "activeDeadlineSeconds": parse_duration(sync_cfg.get("timeout", "30m")),
                    "ttlSecondsAfterFinished": 86400,
                    "template": {
                        "metadata": {"labels": labels},
                        "spec": {
                            "restartPolicy": "Never",
                            "serviceAccountName": cfg.service_account,
                            "automountServiceAccountToken": False,
                            "securityContext": {
                                "runAsNonRoot": True,
                                "runAsUser": 10001,
                                "runAsGroup": 10001,
                                "seccompProfile": {"type": "RuntimeDefault"},
                            },
                            "containers": [container],
                            "volumes": [{"name": "tmp", "emptyDir": {"sizeLimit": "64Mi"}}],
                        },
                    },
                },
            },
        },
    }


def _ts(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def derive_status(
    cronjob_status: dict[str, Any] | None, *, suspended: bool, generation: int, now: datetime
) -> dict[str, Any]:
    """Map CronJob status onto the RealEstateSync status subresource."""
    st = cronjob_status or {}
    last_schedule = _ts(st.get("lastScheduleTime"))
    last_success = _ts(st.get("lastSuccessfulTime"))
    active = len(st.get("active") or [])
    if suspended:
        phase, ready, reason = "Paused", "False", "Suspended"
    elif active:
        phase, ready, reason = "Running", "True", "JobActive"
    elif last_schedule is None:
        phase, ready, reason = "Pending", "True", "AwaitingFirstRun"
    elif last_success is not None and last_success >= last_schedule:
        phase, ready, reason = "Completed", "True", "LastRunSucceeded"
    else:
        phase, ready, reason = "Failed", "False", "LastRunFailed"
    status: dict[str, Any] = {
        "phase": phase,
        "observedGeneration": generation,
        "activeJobs": active,
        "conditions": [
            {
                "type": "Ready",
                "status": ready,
                "reason": reason,
                "lastTransitionTime": now.isoformat().replace("+00:00", "Z"),
            }
        ],
    }
    if last_schedule:
        status["lastScheduleTime"] = last_schedule.isoformat().replace("+00:00", "Z")
    if last_success:
        status["lastSyncTime"] = last_success.isoformat().replace("+00:00", "Z")
    return status
