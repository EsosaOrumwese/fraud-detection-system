"""Label Store observability, governance, and access-audit helpers (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn
from fraud_detection.platform_runtime import RUNS_ROOT


class LabelStoreObservabilityError(ValueError):
    """Raised when Label Store observability inputs are invalid."""


@dataclass(frozen=True)
class LabelStoreHealthThresholds:
    amber_anomalies_total: int = 1
    red_anomalies_total: int = 10
    amber_rejected_total: int = 1
    red_rejected_total: int = 10
    amber_pending_total: int = 1
    red_pending_total: int = 10


@dataclass(frozen=True)
class LabelStoreEvidenceAccessAuditRequest:
    actor_id: str
    source_type: str
    purpose: str
    ref_type: str
    ref_id: str
    platform_run_id: str
    scenario_run_id: str | None = None
    resolution_status: str = "ALLOWED"
    reason_code: str | None = None
    source_component: str = "label_store"
    observed_time: str | None = None
    dedupe_key: str | None = None


@dataclass(frozen=True)
class LabelStoreEvidenceAccessAuditResult:
    event_id: str
    emitted: bool
    resolution_status: str
    reason_code: str | None
    events_path: str


@dataclass
class LabelStoreEvidenceAccessAuditor:
    """Append-only evidence access-audit hook writer for LS consumers."""

    def audit(
        self,
        request: LabelStoreEvidenceAccessAuditRequest,
        *,
        output_root: Path | None = None,
    ) -> LabelStoreEvidenceAccessAuditResult:
        normalized = _normalize_access_request(request)
        run_root = Path(output_root) if output_root is not None else RUNS_ROOT / normalized.platform_run_id
        component_root = run_root / "label_store" / "access_audit"
        events_path = component_root / "events.jsonl"
        markers_dir = component_root / "markers"
        markers_dir.mkdir(parents=True, exist_ok=True)

        dedupe_basis = normalized.dedupe_key or (
            f"{normalized.platform_run_id}|{normalized.scenario_run_id or ''}|"
            f"{normalized.actor_id}|{normalized.purpose}|{normalized.ref_type}|{normalized.ref_id}|"
            f"{normalized.resolution_status}|{normalized.reason_code or ''}"
        )
        event_id = hashlib.sha256(dedupe_basis.encode("utf-8")).hexdigest()
        marker_path = markers_dir / f"{event_id}.json"
        if marker_path.exists():
            return LabelStoreEvidenceAccessAuditResult(
                event_id=event_id,
                emitted=False,
                resolution_status=normalized.resolution_status,
                reason_code=normalized.reason_code,
                events_path=str(events_path),
            )

        payload = {
            "event_id": event_id,
            "event_family": "EVIDENCE_ACCESS",
            "ts_utc": normalized.observed_time or _utc_now(),
            "actor": {
                "actor_id": normalized.actor_id,
                "source_type": normalized.source_type,
                "source_component": normalized.source_component,
            },
            "pins": {
                "platform_run_id": normalized.platform_run_id,
                "scenario_run_id": normalized.scenario_run_id,
            },
            "details": {
                "purpose": normalized.purpose,
                "ref_type": normalized.ref_type,
                "ref_id": normalized.ref_id,
                "resolution_status": normalized.resolution_status,
                "reason_code": normalized.reason_code,
            },
        }
        marker_path.write_text(
            json.dumps(
                {
                    "event_id": event_id,
                    "event_family": "EVIDENCE_ACCESS",
                    "ts_utc": payload["ts_utc"],
                },
                sort_keys=True,
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        _append_jsonl(events_path, payload)
        return LabelStoreEvidenceAccessAuditResult(
            event_id=event_id,
            emitted=True,
            resolution_status=normalized.resolution_status,
            reason_code=normalized.reason_code,
            events_path=str(events_path),
        )


@dataclass
class LabelStoreRunReporter:
    locator: str
    platform_run_id: str
    scenario_run_id: str
    thresholds: LabelStoreHealthThresholds = LabelStoreHealthThresholds()

    def __post_init__(self) -> None:
        self.locator = _required(self.locator, "locator")
        self.platform_run_id = _required(self.platform_run_id, "platform_run_id")
        self.scenario_run_id = _required(self.scenario_run_id, "scenario_run_id")
        self.backend = "postgres" if is_postgres_dsn(self.locator) else "sqlite"

    def collect(self) -> dict[str, Any]:
        with self._connect() as conn:
            assertion_rows = _query_all(
                conn,
                self.backend,
                """
                SELECT label_assertion_id, platform_run_id, event_id, label_type, replay_count, mismatch_count,
                       assertion_json, first_committed_at_utc, assertion_ref
                FROM ls_label_assertions
                ORDER BY first_committed_at_utc ASC, label_assertion_id ASC
                """,
                tuple(),
            )
            mismatch_rows = _query_all(
                conn,
                self.backend,
                """
                SELECT label_assertion_id, platform_run_id, event_id, label_type, observed_payload_hash,
                       stored_payload_hash, observed_at_utc
                FROM ls_label_assertion_mismatches
                ORDER BY observed_at_utc ASC
                """,
                tuple(),
            )
            timeline_rows = _query_all(
                conn,
                self.backend,
                """
                SELECT label_assertion_id, event_id, label_type, observed_time, source_type, actor_id,
                       evidence_refs_json, assertion_json, assertion_ref
                FROM ls_label_timeline
                ORDER BY observed_time ASC, effective_time ASC, label_assertion_id ASC
                """,
                tuple(),
            )

        filtered_assertions: list[Any] = []
        assertion_subject: dict[str, tuple[str, str, str]] = {}
        assertion_pins: dict[str, dict[str, Any]] = {}
        for row in assertion_rows:
            assertion_json = _json_to_dict(row[6])
            pins = _json_to_dict(assertion_json.get("pins"))
            if not _pins_match_run(
                pins,
                platform_run_id=self.platform_run_id,
                scenario_run_id=self.scenario_run_id,
            ):
                continue
            filtered_assertions.append(row)
            assertion_id = str(row[0])
            assertion_subject[assertion_id] = (str(row[1]), str(row[2]), str(row[3]))
            assertion_pins[assertion_id] = pins

        accepted_total = len(filtered_assertions)
        duplicate_total = sum(int(row[4] or 0) for row in filtered_assertions)
        rejected_total = sum(int(row[5] or 0) for row in filtered_assertions)
        pending_total = 0

        payload_hash_mismatch_total = 0
        dedupe_tuple_collision_total = 0
        mismatch_rows_total = 0
        for row in mismatch_rows:
            assertion_id = str(row[0])
            expected_subject = assertion_subject.get(assertion_id)
            if expected_subject is None:
                continue
            mismatch_rows_total += 1
            observed_subject = (str(row[1]), str(row[2]), str(row[3]))
            if observed_subject != expected_subject:
                dedupe_tuple_collision_total += 1
            else:
                payload_hash_mismatch_total += 1

        anomalies = _build_anomaly_summary(
            payload_hash_mismatch_total=payload_hash_mismatch_total,
            dedupe_tuple_collision_total=dedupe_tuple_collision_total,
            mismatch_rows_total=mismatch_rows_total,
        )
        metrics = {
            "accepted": accepted_total,
            "rejected": rejected_total,
            "duplicate": duplicate_total,
            "pending": pending_total,
            "timeline_rows": sum(
                1 for row in timeline_rows if str(row[0]) in assertion_subject
            ),
            "payload_hash_mismatch": payload_hash_mismatch_total,
            "dedupe_tuple_collision": dedupe_tuple_collision_total,
            "mismatch_rows": mismatch_rows_total,
            "contract_invalid": 0,
            "missing_evidence_refs": 0,
        }
        health = _derive_health(metrics=metrics, anomalies_total=anomalies["total"], thresholds=self.thresholds)
        lifecycle_events = _lifecycle_events_from_timeline(
            rows=timeline_rows,
            assertion_subject=assertion_subject,
            assertion_pins=assertion_pins,
            platform_run_id=self.platform_run_id,
            scenario_run_id=self.scenario_run_id,
        )

        return {
            "generated_at_utc": _utc_now(),
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "metrics": metrics,
            "anomalies": anomalies,
            "health_state": health["state"],
            "health_reasons": health["reasons"],
            "lifecycle_governance_events": lifecycle_events,
        }

    def export(self, *, output_root: Path | None = None) -> dict[str, Any]:
        payload = self.collect()
        run_root = Path(output_root) if output_root is not None else RUNS_ROOT / self.platform_run_id
        component_root = run_root / "label_store"

        lifecycle_summary = _write_lifecycle_events(
            run_root=component_root,
            events=payload["lifecycle_governance_events"],
        )
        payload["governance"] = lifecycle_summary

        metrics_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "platform_run_id": payload["platform_run_id"],
            "scenario_run_id": payload["scenario_run_id"],
            "metrics": payload["metrics"],
        }
        health_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "platform_run_id": payload["platform_run_id"],
            "scenario_run_id": payload["scenario_run_id"],
            "health_state": payload["health_state"],
            "health_reasons": payload["health_reasons"],
            "metrics": payload["metrics"],
            "anomalies": payload["anomalies"],
        }
        reconciliation_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "platform_run_id": payload["platform_run_id"],
            "scenario_run_id": payload["scenario_run_id"],
            "reconciliation": {
                "metrics": payload["metrics"],
                "anomaly_lanes": payload["anomalies"]["lanes"],
                "anomalies_total": payload["anomalies"]["total"],
                "governance_events_emitted_total": lifecycle_summary["emitted_total"],
            },
            "health_state": payload["health_state"],
            "health_reasons": payload["health_reasons"],
        }

        _write_json(component_root / "metrics" / "last_metrics.json", metrics_payload)
        _write_json(component_root / "health" / "last_health.json", health_payload)
        _write_json(component_root / "reconciliation" / "last_reconciliation.json", reconciliation_payload)

        case_labels_contribution = {
            "generated_at_utc": payload["generated_at_utc"],
            "platform_run_id": payload["platform_run_id"],
            "scenario_run_id": payload["scenario_run_id"],
            "component": "label_store",
            "metrics_ref": "label_store/metrics/last_metrics.json",
            "reconciliation_ref": "label_store/reconciliation/last_reconciliation.json",
            "governance_ref": "label_store/governance/events.jsonl",
            "summary": {
                "accepted": int(payload["metrics"]["accepted"]),
                "rejected": int(payload["metrics"]["rejected"]),
                "duplicate": int(payload["metrics"]["duplicate"]),
                "pending": int(payload["metrics"]["pending"]),
                "anomalies_total": int(payload["anomalies"]["total"]),
            },
        }
        day_stamp = _day_stamp(payload["generated_at_utc"])
        case_labels_reconciliation_dir = run_root / "case_labels" / "reconciliation"
        _write_json(
            case_labels_reconciliation_dir / f"{day_stamp}.json",
            case_labels_contribution,
        )
        _write_json(
            case_labels_reconciliation_dir / "label_store_reconciliation.json",
            case_labels_contribution,
        )
        return payload

    def _connect(self) -> Any:
        if self.backend == "sqlite":
            conn = sqlite3.connect(_sqlite_path(self.locator))
            conn.row_factory = sqlite3.Row
            return conn
        return psycopg.connect(self.locator)


def _normalize_access_request(request: LabelStoreEvidenceAccessAuditRequest) -> LabelStoreEvidenceAccessAuditRequest:
    actor_id = _required(request.actor_id, "actor_id")
    source_type = _required(request.source_type, "source_type").upper()
    purpose = _required(request.purpose, "purpose")
    ref_type = _required(request.ref_type, "ref_type").upper()
    ref_id = _required(request.ref_id, "ref_id")
    platform_run_id = _required(request.platform_run_id, "platform_run_id")
    scenario_run_id = _optional(request.scenario_run_id)
    source_component = _required(request.source_component, "source_component")
    status = _required(request.resolution_status, "resolution_status").upper()
    if status not in {"ALLOWED", "DENIED"}:
        raise LabelStoreObservabilityError("resolution_status must be ALLOWED or DENIED")
    reason_code = _optional(request.reason_code)
    observed_time = _optional(request.observed_time)
    dedupe_key = _optional(request.dedupe_key)
    return LabelStoreEvidenceAccessAuditRequest(
        actor_id=actor_id,
        source_type=source_type,
        purpose=purpose,
        ref_type=ref_type,
        ref_id=ref_id,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        resolution_status=status,
        reason_code=reason_code,
        source_component=source_component,
        observed_time=observed_time,
        dedupe_key=dedupe_key,
    )


def _pins_match_run(pins: Mapping[str, Any], *, platform_run_id: str, scenario_run_id: str) -> bool:
    return (
        str(pins.get("platform_run_id") or "").strip() == platform_run_id
        and str(pins.get("scenario_run_id") or "").strip() == scenario_run_id
    )


def _build_anomaly_summary(
    *,
    payload_hash_mismatch_total: int,
    dedupe_tuple_collision_total: int,
    mismatch_rows_total: int,
) -> dict[str, Any]:
    lanes: list[dict[str, Any]] = []
    for kind, count in (
        ("PAYLOAD_HASH_MISMATCH", payload_hash_mismatch_total),
        ("DEDUPE_TUPLE_COLLISION", dedupe_tuple_collision_total),
        ("MISMATCH_ROWS", mismatch_rows_total),
    ):
        if int(count) > 0:
            lanes.append({"kind": kind, "count": int(count)})
    lanes.sort(key=lambda item: (item["kind"], item["count"]))
    return {
        "total": sum(int(item["count"]) for item in lanes),
        "lanes": lanes,
    }


def _derive_health(
    *,
    metrics: Mapping[str, Any],
    anomalies_total: int,
    thresholds: LabelStoreHealthThresholds,
) -> dict[str, Any]:
    state = "GREEN"
    reasons: list[str] = []
    rejected_total = int(metrics.get("rejected", 0))
    pending_total = int(metrics.get("pending", 0))

    if anomalies_total >= thresholds.red_anomalies_total:
        state = "RED"
        reasons.append("ANOMALIES_RED")
    elif anomalies_total >= thresholds.amber_anomalies_total:
        if state != "RED":
            state = "AMBER"
        reasons.append("ANOMALIES_AMBER")

    if rejected_total >= thresholds.red_rejected_total:
        state = "RED"
        reasons.append("REJECTED_RED")
    elif rejected_total >= thresholds.amber_rejected_total and state != "RED":
        state = "AMBER"
        reasons.append("REJECTED_AMBER")

    if pending_total >= thresholds.red_pending_total:
        state = "RED"
        reasons.append("PENDING_RED")
    elif pending_total >= thresholds.amber_pending_total and state != "RED":
        state = "AMBER"
        reasons.append("PENDING_AMBER")

    return {"state": state, "reasons": reasons}


def _lifecycle_events_from_timeline(
    *,
    rows: list[Any],
    assertion_subject: Mapping[str, tuple[str, str, str]],
    assertion_pins: Mapping[str, Mapping[str, Any]],
    platform_run_id: str,
    scenario_run_id: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        assertion_id = str(row[0])
        if assertion_id not in assertion_subject:
            continue
        event_id = str(row[1])
        label_type = str(row[2])
        observed_time = str(row[3])
        source_type = str(row[4] or "SYSTEM").upper()
        actor_id = str(row[5] or "SYSTEM::label_store")
        evidence_refs = _evidence_refs(row[6])
        pins = assertion_pins.get(assertion_id, {})
        subject = assertion_subject[assertion_id]
        dedupe_basis = f"{platform_run_id}|{assertion_id}|LABEL_ACCEPTED"
        lifecycle_event_id = hashlib.sha256(dedupe_basis.encode("utf-8")).hexdigest()
        events.append(
            {
                "event_id": lifecycle_event_id,
                "event_family": "LABEL_LIFECYCLE",
                "lifecycle_type": "LABEL_ACCEPTED",
                "ts_utc": observed_time,
                "actor": {
                    "actor_id": actor_id,
                    "source_type": source_type,
                    "source_component": "label_store",
                },
                "pins": _governance_pins(
                    pins=pins,
                    platform_run_id=platform_run_id,
                    scenario_run_id=scenario_run_id,
                ),
                "details": {
                    "label_assertion_id": assertion_id,
                    "event_id": event_id,
                    "label_type": label_type,
                    "subject_platform_run_id": subject[0],
                    "subject_event_id": subject[1],
                    "source_ref_id": f"label_assertion:{assertion_id}",
                    "evidence_refs": evidence_refs,
                },
            }
        )
    return events


def _governance_pins(
    *,
    pins: Mapping[str, Any],
    platform_run_id: str,
    scenario_run_id: str,
) -> dict[str, Any]:
    merged = {
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
    }
    for field in ("manifest_fingerprint", "parameter_hash", "scenario_id"):
        value = str(pins.get(field) or "").strip()
        if value:
            merged[field] = value
    seed = str(pins.get("seed") or "").strip()
    if seed:
        merged["seed"] = seed
    return merged


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


def _evidence_refs(value: Any) -> list[dict[str, str]]:
    if value in (None, ""):
        return []
    payload: list[Any]
    if isinstance(value, list):
        payload = list(value)
    else:
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        payload = list(parsed)

    refs: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        ref_type = str(item.get("ref_type") or "").strip().upper()
        ref_id = str(item.get("ref_id") or "").strip()
        if ref_type and ref_id:
            refs.append({"ref_type": ref_type, "ref_id": ref_id})
    refs.sort(key=lambda item: (item["ref_type"], item["ref_id"]))
    return refs


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), sort_keys=True, ensure_ascii=True) + "\n")


def _query_all(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> list[Any]:
    rendered = _render_sql(sql, backend)
    cur = conn.execute(rendered, params) if backend == "sqlite" else conn.cursor().execute(rendered, params)
    return list(cur.fetchall())


def _render_sql(sql: str, backend: str) -> str:
    rendered = sql
    if backend == "postgres":
        for idx in range(1, 21):
            rendered = rendered.replace(f"{{p{idx}}}", f"${idx}")
    else:
        for idx in range(1, 21):
            rendered = rendered.replace(f"{{p{idx}}}", "?")
    return rendered


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


def _day_stamp(ts_utc: Any) -> str:
    text = str(ts_utc or "").strip()
    if "T" in text:
        return text.split("T", 1)[0]
    return _utc_now().split("T", 1)[0]


def _required(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise LabelStoreObservabilityError(f"{field_name} is required")
    return text


def _optional(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

