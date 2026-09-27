"""kopf handlers. Run with::

    kopf run -m realestate_sync_operator.handlers --all-namespaces \
        --liveness=http://0.0.0.0:8081/healthz
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

import kopf
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from . import GROUP, PLURAL, VERSION
from .resources import OperatorConfig, SpecError, build_cronjob, derive_status

log = logging.getLogger(__name__)


def operator_config() -> OperatorConfig:
    return OperatorConfig(
        image=os.environ.get(
            "SYNC_IMAGE", "ghcr.io/satvikpraveen/kubeestatehub/analytics-worker:latest"
        ),
        database_secret=os.getenv("DATABASE_CREDENTIALS_REF", "db-secret"),
        database_secret_key=os.getenv("DATABASE_CREDENTIALS_KEY", "database-url"),
        service_account=os.getenv("SYNC_SERVICE_ACCOUNT", "realestate-sync-job"),
    )


@kopf.on.startup()
def startup(settings: kopf.OperatorSettings, **_: Any) -> None:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    # a single replica with a Recreate strategy; kopf peering prevents double processing
    settings.peering.standalone = os.getenv("KOPF_STANDALONE", "true").lower() == "true"
    settings.posting.level = logging.INFO
    settings.watching.server_timeout = 300
    settings.persistence.progress_storage = kopf.AnnotationsProgressStorage(prefix=GROUP)
    settings.persistence.diffbase_storage = kopf.AnnotationsDiffBaseStorage(prefix=GROUP)


@kopf.on.probe(id="now")
def probe_now(**_: Any) -> str:
    return datetime.now(UTC).isoformat()


def apply_cronjob(body: kopf.Body) -> None:
    batch = client.BatchV1Api()
    name = body["metadata"]["name"]
    namespace = body["metadata"]["namespace"]
    try:
        manifest = build_cronjob(name, namespace, dict(body["spec"]), operator_config())
    except (SpecError, KeyError) as exc:
        raise kopf.PermanentError(f"invalid spec: {exc}") from exc
    kopf.adopt(manifest, owner=body)  # ownerReference: CronJob is garbage-collected with the CR
    cj_name = manifest["metadata"]["name"]
    try:
        batch.replace_namespaced_cron_job(cj_name, namespace, manifest)
        log.info("updated cronjob %s/%s", namespace, cj_name)
    except ApiException as exc:
        if exc.status != 404:
            raise
        batch.create_namespaced_cron_job(namespace, manifest)
        log.info("created cronjob %s/%s", namespace, cj_name)


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL, field="spec")
@kopf.on.resume(GROUP, VERSION, PLURAL)
def reconcile(body: kopf.Body, patch: kopf.Patch, **_: Any) -> None:
    apply_cronjob(body)
    patch.status.update(
        derive_status(
            None,
            suspended=bool(body["spec"].get("suspend")),
            generation=body["metadata"].get("generation", 0),
            now=datetime.now(UTC),
        )
    )


@kopf.timer(GROUP, VERSION, PLURAL, interval=60, initial_delay=30, idle=0)
def refresh_status(body: kopf.Body, patch: kopf.Patch, **_: Any) -> None:
    name = f"sync-{body['metadata']['name']}"[:52]
    namespace = body["metadata"]["namespace"]
    try:
        cj = client.BatchV1Api().read_namespaced_cron_job_status(name, namespace)
        cj_status = client.ApiClient().sanitize_for_serialization(cj.status) or {}
    except ApiException as exc:
        if exc.status == 404:  # drifted: somebody deleted the CronJob; recreate it
            apply_cronjob(body)
            cj_status = {}
        else:
            raise
    patch.status.update(
        derive_status(
            cj_status,
            suspended=bool(body["spec"].get("suspend")),
            generation=body["metadata"].get("generation", 0),
            now=datetime.now(UTC),
        )
    )
