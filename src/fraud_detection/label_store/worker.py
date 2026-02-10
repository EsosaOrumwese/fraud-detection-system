"""Label Store runtime reporter worker CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Mapping

import psycopg
from fraud_detection.postgres_runtime import postgres_threadlocal_connection
import yaml

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn
from fraud_detection.platform_runtime import resolve_platform_run_id, resolve_run_scoped_path

from .observability import LabelStoreRunReporter


logger = logging.getLogger("fraud_detection.label_store.worker")
_ENV_PATTERN = re.compile(r"^\$\{([^}:]+)(?::-([^}]*))?\}$")


@dataclass(frozen=True)
class LabelStoreWorkerConfig:
    profile_path: Path
    locator: str
    stream_id: str
    platform_run_id: str | None
    required_platform_run_id: str | None
    scenario_run_id: str | None
    poll_seconds: float


class LabelStoreWorker:
    def __init__(self, config: LabelStoreWorkerConfig) -> None:
        self.config = config
        self.backend = "postgres" if is_postgres_dsn(config.locator) else "sqlite"
        self._scenario_run_id = config.scenario_run_id

    def run_once(self) -> int:
        platform_run_id = self.config.platform_run_id
        if not platform_run_id:
            return 0
        if self.config.required_platform_run_id and platform_run_id != self.config.required_platform_run_id:
            return 0
        scenario_run_id = self._scenario_run_id or self._discover_scenario_run_id(platform_run_id=platform_run_id)
        if not scenario_run_id:
            logger.debug("LabelStore worker idle: scenario_run_id unresolved for platform_run_id=%s", platform_run_id)
            return 0
        self._scenario_run_id = scenario_run_id
        try:
            reporter = LabelStoreRunReporter(
                locator=self.config.locator,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
            )
            reporter.export()
        except sqlite3.OperationalError as exc:
            text = str(exc).lower()
            if "no such table" in text:
                logger.warning("LabelStore worker deferred: schema not ready yet (%s)", str(exc)[:256])
                return 0
            raise
        return 1

    def run_forever(self) -> None:
        while True:
            processed = self.run_once()
            if processed == 0:
                time.sleep(self.config.poll_seconds)
                continue
            time.sleep(self.config.poll_seconds)

    def _discover_scenario_run_id(self, *, platform_run_id: str) -> str | None:
        sql = (
            "SELECT assertion_json FROM ls_label_assertions "
            "WHERE platform_run_id = %s "
            "ORDER BY last_committed_at_utc DESC LIMIT 200"
        )
        params = (platform_run_id,)
        rows: list[Any] = []
        if self.backend == "sqlite":
            sql = sql.replace("%s", "?")
            try:
                with sqlite3.connect(self.config.locator) as conn:
                    rows = conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError as exc:
                text = str(exc).lower()
                if "no such table" in text:
                    return None
                raise
        else:
            try:
                with postgres_threadlocal_connection(self.config.locator) as conn:
                    with conn.cursor() as cur:
                        cur.execute(sql, params)
                        rows = cur.fetchall()
            except psycopg.Error as exc:
                if "does not exist" in str(exc).lower():
                    return None
                raise
        for row in rows:
            raw = row[0] if isinstance(row, (tuple, list)) else None
            if raw in (None, ""):
                continue
            try:
                payload = json.loads(str(raw))
            except Exception:
                continue
            pins = payload.get("pins") if isinstance(payload, Mapping) else {}
            scenario_run_id = str((pins or {}).get("scenario_run_id") or "").strip()
            if scenario_run_id:
                return scenario_run_id
        return None


def load_worker_config(profile_path: Path) -> LabelStoreWorkerConfig:
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("LABEL_STORE_PROFILE_INVALID")

    profile_id = str(payload.get("profile_id") or "local")
    ls = payload.get("label_store") if isinstance(payload.get("label_store"), Mapping) else {}
    ls_wiring = ls.get("wiring") if isinstance(ls.get("wiring"), Mapping) else {}
    platform_run_id = _platform_run_id()
    stream_id = _with_scope(str(_env(ls_wiring.get("stream_id") or "label_store.v0")).strip(), platform_run_id)
    return LabelStoreWorkerConfig(
        profile_path=profile_path,
        locator=_locator(ls_wiring.get("locator"), "label_store/writer.sqlite"),
        stream_id=stream_id,
        platform_run_id=platform_run_id,
        required_platform_run_id=_none_if_blank(
            _env(ls_wiring.get("required_platform_run_id") or os.getenv("LABEL_STORE_REQUIRED_PLATFORM_RUN_ID") or platform_run_id)
        ),
        scenario_run_id=_none_if_blank(_env(ls_wiring.get("scenario_run_id") or os.getenv("LABEL_STORE_SCENARIO_RUN_ID"))),
        poll_seconds=max(0.1, float(_env(ls_wiring.get("poll_seconds") or 2.0))),
    )


def _env(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    token = value.strip()
    match = _ENV_PATTERN.fullmatch(token)
    if not match:
        return value
    return os.getenv(match.group(1), match.group(2) or "")


def _locator(value: Any, suffix: str) -> str:
    raw = str(_env(value) or "").strip()
    path = resolve_run_scoped_path(raw or None, suffix=suffix, create_if_missing=True)
    if not path:
        raise RuntimeError(f"LABEL_STORE_LOCATOR_MISSING:{suffix}")
    if not (path.startswith("postgres://") or path.startswith("postgresql://") or path.startswith("s3://")):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


def _platform_run_id() -> str | None:
    explicit = (os.getenv("ACTIVE_PLATFORM_RUN_ID") or os.getenv("PLATFORM_RUN_ID") or "").strip()
    if explicit:
        return explicit
    return resolve_platform_run_id(create_if_missing=False)


def _with_scope(base_stream: str, run_id: str | None) -> str:
    if run_id and "::" not in base_stream:
        return f"{base_stream}::{run_id}"
    return base_stream


def _none_if_blank(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def main() -> None:
    parser = argparse.ArgumentParser(description="Label Store runtime worker")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    worker = LabelStoreWorker(load_worker_config(Path(args.profile)))
    if args.once:
        processed = worker.run_once()
        logger.info("LabelStore worker processed=%s", processed)
        return
    worker.run_forever()


if __name__ == "__main__":
    main()

