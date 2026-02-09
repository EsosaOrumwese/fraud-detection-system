"""Decision Log & Audit runtime worker CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import logging
import os
from pathlib import Path
import re
import time
from typing import Any

import psycopg
import sqlite3
import yaml

from fraud_detection.platform_runtime import resolve_platform_run_id, resolve_run_scoped_path

from .config import load_intake_policy
from .intake import DecisionLogAuditBusConsumer, DecisionLogAuditIntakeRuntimeConfig
from .observability import DecisionLogAuditObservabilityReporter
from .storage import DecisionLogAuditIntakeStore, build_storage_layout


logger = logging.getLogger("fraud_detection.dla.worker")
_ENV_PATTERN = re.compile(r"^\$\{([^}:]+)(?::-([^}]*))?\}$")


@dataclass(frozen=True)
class DlaWorkerConfig:
    profile_path: Path
    policy_ref: Path
    storage_profile_id: str
    index_locator: str
    event_bus_kind: str
    event_bus_root: str
    event_bus_stream: str | None
    event_bus_region: str | None
    event_bus_endpoint_url: str | None
    event_bus_start_position: str
    poll_max_records: int
    poll_sleep_seconds: float
    stream_id: str
    platform_run_id: str | None
    required_platform_run_id: str | None


class DecisionLogAuditWorker:
    def __init__(self, config: DlaWorkerConfig) -> None:
        self.config = config
        self.policy = load_intake_policy(config.policy_ref)
        if (
            config.required_platform_run_id
            and self.policy.required_platform_run_id != config.required_platform_run_id
        ):
            self.policy = replace(
                self.policy,
                required_platform_run_id=config.required_platform_run_id,
            )
        self.store = DecisionLogAuditIntakeStore(locator=config.index_locator, stream_id=config.stream_id)
        self.consumer = DecisionLogAuditBusConsumer(
            policy=self.policy,
            store=self.store,
            runtime=DecisionLogAuditIntakeRuntimeConfig(
                event_bus_kind=config.event_bus_kind,
                event_bus_root=config.event_bus_root,
                event_bus_stream=config.event_bus_stream,
                event_bus_region=config.event_bus_region,
                event_bus_endpoint_url=config.event_bus_endpoint_url,
                event_bus_start_position=config.event_bus_start_position,
                poll_max_records=config.poll_max_records,
                poll_sleep_seconds=config.poll_sleep_seconds,
            ),
        )
        self._last_export_at = 0.0
        self._scenario_run_id: str | None = os.getenv("DLA_SCENARIO_RUN_ID") or None

    def run_once(self) -> int:
        processed = self.consumer.run_once()
        self._maybe_export_observability(force=(processed > 0))
        return processed

    def run_forever(self) -> None:
        while True:
            processed = self.run_once()
            if processed == 0:
                time.sleep(self.config.poll_sleep_seconds)

    def _maybe_export_observability(self, *, force: bool) -> None:
        if not self.config.platform_run_id:
            return
        now = time.time()
        interval_seconds = max(1.0, float(os.getenv("DLA_OBSERVABILITY_EXPORT_SECONDS") or "10"))
        if not force and (now - self._last_export_at) < interval_seconds:
            return
        if not self._scenario_run_id:
            self._scenario_run_id = _latest_scenario_run_id(
                locator=self.config.index_locator,
                backend=self.store.backend,
                stream_id=self.config.stream_id,
                platform_run_id=self.config.platform_run_id,
            )
        if not self._scenario_run_id:
            return
        reporter = DecisionLogAuditObservabilityReporter(
            store=self.store,
            platform_run_id=self.config.platform_run_id,
            scenario_run_id=self._scenario_run_id,
        )
        reporter.export()
        self._last_export_at = now


def load_worker_config(profile_path: Path) -> DlaWorkerConfig:
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("DLA_PROFILE_INVALID")

    profile_id = str(payload.get("profile_id") or "local")
    dl_payload = payload.get("dla") if isinstance(payload.get("dla"), dict) else {}
    policy = dl_payload.get("policy") if isinstance(dl_payload.get("policy"), dict) else {}
    wiring = dl_payload.get("wiring") if isinstance(dl_payload.get("wiring"), dict) else {}

    top_wiring = payload.get("wiring") if isinstance(payload.get("wiring"), dict) else {}
    top_event_bus = top_wiring.get("event_bus") if isinstance(top_wiring.get("event_bus"), dict) else {}

    policy_ref = Path(
        _resolve_env_token(
            policy.get("intake_policy_ref")
            or os.getenv("DLA_INTAKE_POLICY_REF")
            or "config/platform/dla/intake_policy_v0.yaml"
        )
    )

    storage_profile_id = str(
        _resolve_env_token(
            policy.get("storage_profile_id")
            or os.getenv("DLA_STORAGE_PROFILE_ID")
            or profile_id
        )
    ).strip() or profile_id

    storage_layout = build_storage_layout(
        {
            "profile_id": storage_profile_id,
            "index_locator": _resolve_env_token(
                wiring.get("index_locator") or os.getenv("DLA_INDEX_DSN") or os.getenv("PARITY_DLA_INDEX_DSN")
            ),
            "storage_policy_path": _resolve_env_token(
                policy.get("storage_policy_ref")
                or os.getenv("DLA_STORAGE_POLICY_REF")
                or "config/platform/dla/storage_policy_v0.yaml"
            ),
        }
    )

    event_bus_kind = str(
        _resolve_env_token(
            wiring.get("event_bus_kind")
            or top_wiring.get("event_bus_kind")
            or os.getenv("DLA_EVENT_BUS_KIND")
            or "file"
        )
    ).strip().lower()

    event_bus_root = str(
        _resolve_env_token(
            wiring.get("event_bus_root")
            or top_event_bus.get("root")
            or top_event_bus.get("path")
            or os.getenv("DLA_EVENT_BUS_ROOT")
            or "runs/fraud-platform/eb"
        )
    ).strip()

    event_bus_stream = _none_if_blank(
        _resolve_env_token(
            wiring.get("event_bus_stream")
            or top_event_bus.get("stream")
            or os.getenv("DLA_EVENT_BUS_STREAM")
            or "auto"
        )
    )
    event_bus_region = _none_if_blank(
        _resolve_env_token(
            wiring.get("event_bus_region")
            or top_event_bus.get("region")
            or os.getenv("DLA_EVENT_BUS_REGION")
        )
    )
    event_bus_endpoint_url = _none_if_blank(
        _resolve_env_token(
            wiring.get("event_bus_endpoint_url")
            or top_event_bus.get("endpoint_url")
            or os.getenv("DLA_EVENT_BUS_ENDPOINT_URL")
        )
    )
    event_bus_start_position = str(
        _resolve_env_token(
            wiring.get("event_bus_start_position")
            or top_event_bus.get("start_position")
            or os.getenv("DLA_EVENT_BUS_START_POSITION")
            or "trim_horizon"
        )
    ).strip().lower()

    poll_max_records = int(
        _resolve_env_token(wiring.get("poll_max_records") or os.getenv("DLA_POLL_MAX_RECORDS") or 200)
    )
    poll_sleep_seconds = float(
        _resolve_env_token(wiring.get("poll_sleep_seconds") or os.getenv("DLA_POLL_SLEEP_SECONDS") or 0.5)
    )

    platform_run_id = _resolve_platform_run_id()
    required_platform_run_id = _none_if_blank(
        _resolve_env_token(
            wiring.get("required_platform_run_id")
            or os.getenv("DLA_REQUIRED_PLATFORM_RUN_ID")
            or platform_run_id
        )
    )
    stream_id = _none_if_blank(_resolve_env_token(wiring.get("stream_id") or os.getenv("DLA_STREAM_ID")))
    if not stream_id:
        stream_id = "dla.intake.v0"
        if platform_run_id:
            stream_id = f"{stream_id}::{platform_run_id}"

    return DlaWorkerConfig(
        profile_path=profile_path,
        policy_ref=policy_ref,
        storage_profile_id=storage_profile_id,
        index_locator=storage_layout.index_locator,
        event_bus_kind=event_bus_kind,
        event_bus_root=event_bus_root,
        event_bus_stream=event_bus_stream,
        event_bus_region=event_bus_region,
        event_bus_endpoint_url=event_bus_endpoint_url,
        event_bus_start_position=event_bus_start_position,
        poll_max_records=max(1, poll_max_records),
        poll_sleep_seconds=max(0.05, poll_sleep_seconds),
        stream_id=stream_id,
        platform_run_id=platform_run_id,
        required_platform_run_id=required_platform_run_id,
    )


def _resolve_platform_run_id() -> str | None:
    explicit = (os.getenv("ACTIVE_PLATFORM_RUN_ID") or os.getenv("PLATFORM_RUN_ID") or "").strip()
    if explicit:
        return explicit
    return resolve_platform_run_id(create_if_missing=False)


def _resolve_env_token(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    token = value.strip()
    match = _ENV_PATTERN.fullmatch(token)
    if not match:
        return value
    key = match.group(1)
    default = match.group(2) or ""
    return os.getenv(key, default)


def _none_if_blank(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _latest_scenario_run_id(
    *,
    locator: str,
    backend: str,
    stream_id: str,
    platform_run_id: str,
) -> str | None:
    sql = (
        "SELECT scenario_run_id FROM dla_intake_attempts "
        "WHERE stream_id = ? AND platform_run_id = ? AND scenario_run_id IS NOT NULL "
        "ORDER BY created_at_utc DESC LIMIT 1"
    )
    params = (stream_id, platform_run_id)
    if backend == "sqlite":
        with sqlite3.connect(locator) as conn:
            row = conn.execute(sql, params).fetchone()
            return str(row[0]).strip() if row and row[0] not in (None, "") else None

    pg_sql = sql.replace("?", "%s")
    with psycopg.connect(locator) as conn:
        with conn.cursor() as cur:
            cur.execute(pg_sql, params)
            row = cur.fetchone()
            return str(row[0]).strip() if row and row[0] not in (None, "") else None


def main() -> None:
    parser = argparse.ArgumentParser(description="DLA bus worker")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Process one poll cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    config = load_worker_config(Path(args.profile))
    worker = DecisionLogAuditWorker(config)
    if args.once:
        processed = worker.run_once()
        logger.info("DLA worker processed=%s", processed)
        return
    worker.run_forever()


if __name__ == "__main__":
    main()
