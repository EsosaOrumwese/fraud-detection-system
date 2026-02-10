"""Offline Feature Plane observability, governance, and reconciliation helpers (Phase 9)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

import psycopg
from fraud_detection.postgres_runtime import postgres_threadlocal_connection

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn
from fraud_detection.platform_runtime import RUNS_ROOT
from fraud_detection.scenario_runner.storage import (
    LocalObjectStore,
    ObjectStore,
    S3ObjectStore,
    build_object_store,
)


class OfsObservabilityError(ValueError):
    """Raised when OFS observability inputs are invalid."""


@dataclass(frozen=True)
class OfsHealthThresholds:
    amber_pending_total: int = 1
    red_failed_total: int = 1
    amber_anomalies_total: int = 1
    red_anomalies_total: int = 10


@dataclass
class OfsRunReporter:
    locator: str
    platform_run_id: str
    object_store_root: str
    object_store_endpoint: str | None = None
    object_store_region: str | None = None
    object_store_path_style: bool | None = True
    thresholds: OfsHealthThresholds = OfsHealthThresholds()
    source_component: str = "offline_feature_plane"

    def __post_init__(self) -> None:
        self.locator = _required(self.locator, "locator")
        self.platform_run_id = _required(self.platform_run_id, "platform_run_id")
        self.object_store_root = _required(self.object_store_root, "object_store_root")
        self.backend = "postgres" if is_postgres_dsn(self.locator) else "sqlite"
        self.store = build_object_store(
            self.object_store_root,
            s3_endpoint_url=self.object_store_endpoint,
            s3_region=self.object_store_region,
            s3_path_style=self.object_store_path_style,
        )

    def collect(self) -> dict[str, Any]:
        with self._connect() as conn:
            run_rows = _query_all(
                conn,
                self.backend,
                """
                SELECT run_key, request_id, intent_kind, status, last_error_code, result_ref,
                       input_summary_json, provenance_json, created_at_utc, updated_at_utc
                FROM ofs_run_ledger
                ORDER BY created_at_utc ASC, run_key ASC
                """,
                tuple(),
            )
            event_rows = _query_all(
                conn,
                self.backend,
                """
                SELECT run_key, seq, event_type, status, event_at_utc, reason_code, detail_json
                FROM ofs_run_events
                ORDER BY run_key ASC, seq ASC
                """,
                tuple(),
            )

        run_by_key: dict[str, dict[str, Any]] = {}
        for row in run_rows:
            input_summary = _json_to_dict(row[6])
            if str(input_summary.get("platform_run_id") or "").strip() != self.platform_run_id:
                continue
            run_key = str(row[0])
            run_by_key[run_key] = {
                "run_key": run_key,
                "request_id": str(row[1]),
                "intent_kind": str(row[2]),
                "status": str(row[3]).upper(),
                "last_error_code": _optional(row[4]),
                "result_ref": _optional(row[5]),
                "input_summary": input_summary,
                "provenance": _json_to_dict(row[7]),
                "created_at_utc": str(row[8]),
                "updated_at_utc": str(row[9]),
            }

        run_events = [row for row in event_rows if str(row[0]) in run_by_key]

        metrics = _build_metrics(run_by_key=run_by_key)
        anomalies = _build_anomaly_summary(run_events=run_events, run_by_key=run_by_key)
        evidence_ref_resolution = self._collect_evidence_resolution_audit()
        health = _derive_health(metrics=metrics, anomalies_total=anomalies["total"], thresholds=self.thresholds)
        lifecycle_events = _build_lifecycle_events(
            run_events=run_events,
            run_by_key=run_by_key,
            platform_run_id=self.platform_run_id,
            source_component=self.source_component,
        )
        generated_at_utc = _utc_now()
        return {
            "generated_at_utc": generated_at_utc,
            "platform_run_id": self.platform_run_id,
            "metrics": metrics,
            "anomalies": anomalies,
            "health_state": health["state"],
            "health_reasons": health["reasons"],
            "lifecycle_governance_events": lifecycle_events,
            "evidence_ref_resolution": evidence_ref_resolution,
        }

    def export(self, *, output_root: Path | None = None) -> dict[str, Any]:
        payload = self.collect()
        run_root = Path(output_root) if output_root is not None else RUNS_ROOT / self.platform_run_id
        component_root = run_root / "ofs"

        lifecycle_summary = _write_lifecycle_events(
            run_root=component_root,
            events=payload["lifecycle_governance_events"],
        )
        payload["governance"] = lifecycle_summary

        metrics_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "platform_run_id": payload["platform_run_id"],
            "metrics": payload["metrics"],
            "evidence_ref_resolution": payload["evidence_ref_resolution"],
        }
        health_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "platform_run_id": payload["platform_run_id"],
            "health_state": payload["health_state"],
            "health_reasons": payload["health_reasons"],
            "metrics": payload["metrics"],
            "anomalies": payload["anomalies"],
        }
        reconciliation_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "platform_run_id": payload["platform_run_id"],
            "reconciliation": {
                "metrics": payload["metrics"],
                "anomaly_lanes": payload["anomalies"]["lanes"],
                "anomalies_total": payload["anomalies"]["total"],
                "governance_events_emitted_total": lifecycle_summary["emitted_total"],
                "evidence_ref_resolution": payload["evidence_ref_resolution"],
            },
            "health_state": payload["health_state"],
            "health_reasons": payload["health_reasons"],
        }

        _write_json(component_root / "metrics" / "last_metrics.json", metrics_payload)
        _write_json(component_root / "health" / "last_health.json", health_payload)
        _write_json(component_root / "reconciliation" / "last_reconciliation.json", reconciliation_payload)

        learning_reconciliation = {
            "generated_at_utc": payload["generated_at_utc"],
            "platform_run_id": payload["platform_run_id"],
            "component": "offline_feature_plane",
            "metrics_ref": "ofs/metrics/last_metrics.json",
            "reconciliation_ref": "ofs/reconciliation/last_reconciliation.json",
            "governance_ref": "ofs/governance/events.jsonl",
            "summary": {
                "build_requested": int(payload["metrics"]["build_requested"]),
                "build_completed": int(payload["metrics"]["build_completed"]),
                "build_failed": int(payload["metrics"]["build_failed"]),
                "datasets_built": int(payload["metrics"]["datasets_built"]),
                "parity_requested": int(payload["metrics"]["parity_requested"]),
                "parity_completed": int(payload["metrics"]["parity_completed"]),
                "parity_failed": int(payload["metrics"]["parity_failed"]),
                "anomalies_total": int(payload["anomalies"]["total"]),
            },
        }
        learning_dir = run_root / "learning" / "reconciliation"
        _write_json(learning_dir / "ofs_reconciliation.json", learning_reconciliation)
        _write_json(learning_dir / f"{_day_stamp(payload['generated_at_utc'])}.json", learning_reconciliation)
        return payload

    def _collect_evidence_resolution_audit(self) -> dict[str, int]:
        events = _load_governance_events(store=self.store, platform_run_id=self.platform_run_id)
        attempted = 0
        resolved = 0
        denied = 0
        for item in events:
            if str(item.get("event_family") or "").upper() != "EVIDENCE_REF_RESOLVED":
                continue
            actor = item.get("actor")
            if not isinstance(actor, Mapping):
                continue
            source_component = str(actor.get("source_component") or "").strip()
            if source_component != self.source_component:
                continue
            attempted += 1
            details = item.get("details")
            status = str((details or {}).get("resolution_status") or "").upper() if isinstance(details, Mapping) else ""
            if status == "RESOLVED":
                resolved += 1
            else:
                denied += 1
        return {"attempted": attempted, "resolved": resolved, "denied": denied}

    def _connect(self) -> Any:
        if self.backend == "sqlite":
            conn = sqlite3.connect(_sqlite_path(self.locator))
            conn.row_factory = sqlite3.Row
            return conn
        return postgres_threadlocal_connection(self.locator)


def _build_metrics(*, run_by_key: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    build_requested = 0
    build_completed = 0
    build_failed = 0
    build_publish_pending = 0
    datasets_built = 0
    parity_requested = 0
    parity_completed = 0
    parity_failed = 0
    parity_publish_pending = 0
    forensic_requested = 0
    forensic_completed = 0
    forensic_failed = 0

    for run in run_by_key.values():
        intent_kind = str(run["intent_kind"])
        status = str(run["status"])
        result_ref = _optional(run.get("result_ref"))
        if intent_kind == "dataset_build":
            build_requested += 1
            if status == "DONE":
                build_completed += 1
                if result_ref:
                    datasets_built += 1
            elif status == "FAILED":
                build_failed += 1
            elif status == "PUBLISH_PENDING":
                build_publish_pending += 1
        elif intent_kind == "parity_rebuild":
            parity_requested += 1
            if status == "DONE":
                parity_completed += 1
            elif status == "FAILED":
                parity_failed += 1
            elif status == "PUBLISH_PENDING":
                parity_publish_pending += 1
        elif intent_kind == "forensic_rebuild":
            forensic_requested += 1
            if status == "DONE":
                forensic_completed += 1
            elif status == "FAILED":
                forensic_failed += 1

    return {
        "build_requested": build_requested,
        "build_completed": build_completed,
        "build_failed": build_failed,
        "build_publish_pending": build_publish_pending,
        "datasets_built": datasets_built,
        "parity_requested": parity_requested,
        "parity_completed": parity_completed,
        "parity_failed": parity_failed,
        "parity_publish_pending": parity_publish_pending,
        "forensic_requested": forensic_requested,
        "forensic_completed": forensic_completed,
        "forensic_failed": forensic_failed,
    }


def _build_anomaly_summary(
    *,
    run_events: list[Any],
    run_by_key: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    for row in run_events:
        run_key = str(row[0])
        if run_key not in run_by_key:
            continue
        reason = _optional(row[5])
        if not reason:
            continue
        reason_counts[reason] = int(reason_counts.get(reason, 0)) + 1
    lanes = [
        {"kind": str(kind), "count": int(count)}
        for kind, count in sorted(reason_counts.items(), key=lambda item: (str(item[0]), int(item[1])))
    ]
    return {
        "total": sum(int(item["count"]) for item in lanes),
        "lanes": lanes,
    }


def _derive_health(
    *,
    metrics: Mapping[str, Any],
    anomalies_total: int,
    thresholds: OfsHealthThresholds,
) -> dict[str, Any]:
    state = "GREEN"
    reasons: list[str] = []
    failed_total = int(metrics.get("build_failed", 0)) + int(metrics.get("parity_failed", 0)) + int(metrics.get("forensic_failed", 0))
    pending_total = int(metrics.get("build_publish_pending", 0)) + int(metrics.get("parity_publish_pending", 0))

    if failed_total >= thresholds.red_failed_total:
        state = "RED"
        reasons.append("FAILED_TOTAL_RED")
    if anomalies_total >= thresholds.red_anomalies_total:
        state = "RED"
        reasons.append("ANOMALIES_RED")
    elif anomalies_total >= thresholds.amber_anomalies_total and state != "RED":
        state = "AMBER"
        reasons.append("ANOMALIES_AMBER")

    if pending_total >= thresholds.amber_pending_total and state != "RED":
        state = "AMBER"
        reasons.append("PUBLISH_PENDING_AMBER")
    return {"state": state, "reasons": sorted(set(reasons))}


def _build_lifecycle_events(
    *,
    run_events: list[Any],
    run_by_key: Mapping[str, Mapping[str, Any]],
    platform_run_id: str,
    source_component: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in run_events:
        run_key = str(row[0])
        run = run_by_key.get(run_key)
        if run is None:
            continue
        seq = int(row[1])
        event_type = str(row[2]).upper()
        observed_status = str(row[3]).upper()
        event_at_utc = str(row[4])
        reason_code = _optional(row[5])
        lifecycle_type = _map_lifecycle_type(intent_kind=str(run["intent_kind"]), event_type=event_type, observed_status=observed_status)
        if lifecycle_type is None:
            continue
        outcome: str | None = None
        if lifecycle_type == "PARITY_RESULT":
            outcome = "COMPLETED" if observed_status == "DONE" else "FAILED"

        dedupe_basis = f"{platform_run_id}|{run_key}|{seq}|{lifecycle_type}"
        event_id = hashlib.sha256(dedupe_basis.encode("utf-8")).hexdigest()
        details: dict[str, Any] = {
            "run_key": run_key,
            "request_id": str(run["request_id"]),
            "intent_kind": str(run["intent_kind"]),
            "status": observed_status,
        }
        if reason_code:
            details["reason_code"] = reason_code
        result_ref = _optional(run.get("result_ref"))
        if result_ref:
            details["result_ref"] = result_ref
            details["evidence_refs"] = [{"ref_type": "artifact_ref", "ref_id": result_ref}]
        if outcome:
            details["parity_outcome"] = outcome

        events.append(
            {
                "event_id": event_id,
                "event_family": "LEARNING_LIFECYCLE",
                "lifecycle_type": lifecycle_type,
                "ts_utc": event_at_utc,
                "actor": {
                    "actor_id": "SYSTEM::ofs_worker",
                    "source_type": "SYSTEM",
                    "source_component": source_component,
                },
                "pins": {"platform_run_id": platform_run_id},
                "details": details,
            }
        )
    return events


def _map_lifecycle_type(*, intent_kind: str, event_type: str, observed_status: str) -> str | None:
    if intent_kind == "dataset_build":
        if event_type == "INTENT_QUEUED":
            return "DATASET_BUILD_REQUESTED"
        if event_type == "RUN_DONE" and observed_status == "DONE":
            return "DATASET_BUILD_COMPLETED"
        if event_type == "RUN_FAILED" and observed_status == "FAILED":
            return "DATASET_BUILD_FAILED"
        return None
    if intent_kind == "parity_rebuild":
        if event_type == "INTENT_QUEUED":
            return "PARITY_REQUESTED"
        if event_type in {"RUN_DONE", "RUN_FAILED"} and observed_status in {"DONE", "FAILED"}:
            return "PARITY_RESULT"
        return None
    if intent_kind == "forensic_rebuild":
        if event_type == "INTENT_QUEUED":
            return "FORENSIC_REBUILD_REQUESTED"
        if event_type == "RUN_DONE" and observed_status == "DONE":
            return "FORENSIC_REBUILD_COMPLETED"
        if event_type == "RUN_FAILED" and observed_status == "FAILED":
            return "FORENSIC_REBUILD_FAILED"
    return None


def _write_lifecycle_events(*, run_root: Path, events: list[Mapping[str, Any]]) -> dict[str, Any]:
    events_path = run_root / "governance" / "events.jsonl"
    markers_dir = run_root / "governance" / "markers"
    markers_dir.mkdir(parents=True, exist_ok=True)

    emitted = 0
    skipped = 0
    lines: list[str] = []
    for item in events:
        event_id = str(item.get("event_id") or "").strip()
        if not event_id:
            continue
        marker_path = markers_dir / f"{event_id}.json"
        if marker_path.exists():
            skipped += 1
            continue
        marker_path.write_text(
            json.dumps(
                {
                    "event_id": event_id,
                    "event_family": str(item.get("event_family") or ""),
                    "ts_utc": str(item.get("ts_utc") or _utc_now()),
                },
                sort_keys=True,
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        lines.append(json.dumps(dict(item), sort_keys=True, ensure_ascii=True))
        emitted += 1
    if lines:
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with events_path.open("a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line + "\n")
    return {
        "emitted_total": emitted,
        "duplicate_skipped_total": skipped,
        "events_path": str(events_path),
    }


def _load_governance_events(*, store: ObjectStore, platform_run_id: str) -> list[dict[str, Any]]:
    path = f"{_run_prefix_for_store(store, platform_run_id)}/obs/governance/events.jsonl"
    if not store.exists(path):
        return []
    text = store.read_text(path)
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            rows.append(dict(payload))
    return rows


def _run_prefix_for_store(store: ObjectStore, platform_run_id: str) -> str:
    if isinstance(store, S3ObjectStore):
        return platform_run_id
    if isinstance(store, LocalObjectStore):
        root: Path = store.root
        if root.name == "fraud-platform":
            return platform_run_id
    return f"fraud-platform/{platform_run_id}"


def _query_all(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> list[Any]:
    rendered, ordered_params = _render_sql_with_params(sql, backend, params)
    if backend == "sqlite":
        cur = conn.execute(rendered, ordered_params)
        return list(cur.fetchall())
    cur = conn.cursor()
    cur.execute(rendered, ordered_params)
    rows = list(cur.fetchall())
    cur.close()
    return rows


def _render_sql_with_params(sql: str, backend: str, params: tuple[Any, ...]) -> tuple[str, tuple[Any, ...]]:
    ordered_params: list[Any] = []
    placeholder = "%s" if backend == "postgres" else "?"

    def _replace(match: re.Match[str]) -> str:
        index = int(match.group("index"))
        if index <= 0 or index > len(params):
            raise OfsObservabilityError(f"SQL placeholder index p{index} out of range for {len(params)} params")
        ordered_params.append(params[index - 1])
        return placeholder

    rendered = _SQL_PARAM_PATTERN.sub(_replace, sql)
    return rendered, tuple(ordered_params)


_SQL_PARAM_PATTERN = re.compile(r"\{p(?P<index>\d+)\}")


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator[len("sqlite:///") :]
    if locator.startswith("sqlite://"):
        return locator[len("sqlite://") :]
    return locator


def _json_to_dict(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), sort_keys=True, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _required(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise OfsObservabilityError(f"{field_name} is required")
    return text


def _optional(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _day_stamp(ts_utc: Any) -> str:
    text = str(ts_utc or "").strip()
    if "T" in text:
        return text.split("T", 1)[0]
    return _utc_now().split("T", 1)[0]


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

