"""Runtime provenance helpers for service/environment/revision stamping."""

from __future__ import annotations

import os
from typing import Any


def runtime_provenance(
    *,
    component: str,
    environment: str | None = None,
    config_revision: str | None = None,
    run_config_digest: str | None = None,
    service_release_id: str | None = None,
) -> dict[str, Any]:
    component_key = _component_key(component)
    release = (
        _clean(service_release_id)
        or _clean(os.getenv(f"{component_key}_SERVICE_RELEASE_ID"))
        or _clean(os.getenv(f"{component_key}_RELEASE_ID"))
        or _clean(os.getenv("SERVICE_RELEASE_ID"))
        or "dev-local"
    )
    env_name = (
        _clean(environment)
        or _clean(os.getenv("PLATFORM_ENVIRONMENT"))
        or _clean(os.getenv("PLATFORM_PROFILE_ID"))
        or _clean(os.getenv("PLATFORM_PROFILE"))
        or "unknown"
    )
    cfg_revision = _clean(config_revision) or _clean(os.getenv("PLATFORM_CONFIG_REVISION"))
    payload: dict[str, Any] = {
        "service_release_id": release,
        "environment": env_name,
    }
    if cfg_revision:
        payload["config_revision"] = cfg_revision
    digest = _clean(run_config_digest)
    if digest:
        payload["run_config_digest"] = digest
    return payload


def with_runtime_provenance(
    details: dict[str, Any],
    *,
    component: str,
    environment: str | None = None,
    config_revision: str | None = None,
    run_config_digest: str | None = None,
    service_release_id: str | None = None,
) -> dict[str, Any]:
    payload = dict(details)
    payload["provenance"] = runtime_provenance(
        component=component,
        environment=environment,
        config_revision=config_revision,
        run_config_digest=run_config_digest,
        service_release_id=service_release_id,
    )
    return payload


def _component_key(value: str) -> str:
    text = "".join(ch if ch.isalnum() else "_" for ch in str(value or "").strip().upper())
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_") or "SERVICE"


def _clean(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None
