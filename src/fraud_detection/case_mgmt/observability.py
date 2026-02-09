"""Case Management observability, governance, and reconciliation helpers (Phase 7)."""

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


class CaseMgmtObservabilityError(ValueError):
    """Raised when CM observability inputs are invalid."""


@dataclass(frozen=True)
class CaseMgmtHealthThresholds:
    amber_anomalies_total: int = 1
    red_anomalies_total: int = 10
    amber_pending_actions: int = 10
    red_pending_actions: int = 50
    amber_pending_labels: int = 10
    red_pending_labels: int = 50


@dataclass
class CaseMgmtRunReporter:
    locator: str
    platform_run_id: str
    scenario_run_id: str
    thresholds: CaseMgmtHealthThresholds = CaseMgmtHealthThresholds()

    def __post_init__(self) -> None:
        self.locator = _required(self.locator, "locator")
        self.platform_run_id = _required(self.platform_run_id, "platform_run_id")
        self.scenario_run_id = _required(self.scenario_run_id, "scenario_run_id")
        self.backend = "postgres" if is_postgres_dsn(self.locator) else "sqlite"

    def collect(self) -> dict[str, Any]:
        with self._connect() as conn:
            case_rows = _query_all(
                conn,
                self.backend,
                "SELECT case_id, pins_json FROM cm_cases ORDER BY case_id ASC",
                tuple(),
            )
            case_ids = {
                str(row[0])
                for row in case_rows
                if _pins_match_run(
                    _json_to_dict(row[1]),
                    platform_run_id=self.platform_run_id,
                    scenario_run_id=self.scenario_run_id,
                )
            }

            trigger_rows = _query_all(
                conn,
                self.backend,
                "SELECT case_trigger_id, case_id FROM cm_case_trigger_intake",
                tuple(),
            )
            timeline_rows = _query_all(
                conn,
                self.backend,
                """
                SELECT case_timeline_event_id, case_id, timeline_event_type, source_ref_id, observed_time, event_json
                FROM cm_case_timeline
                ORDER BY observed_time ASC, case_timeline_event_id ASC
                """,
                tuple(),
            )
            trigger_mismatch_rows = _query_all(
                conn,
                self.backend,
                "SELECT case_trigger_id FROM cm_case_trigger_mismatches",
                tuple(),
            )
            timeline_mismatch_rows = _query_all(
                conn,
                self.backend,
                "SELECT case_timeline_event_id FROM cm_case_timeline_mismatches",
                tuple(),
            )
            label_rows = _query_all_optional(
                conn,
                self.backend,
                "SELECT label_assertion_id, case_id, status FROM cm_label_emissions",
                tuple(),
            )
            label_mismatch_rows = _query_all_optional(
                conn,
                self.backend,
                "SELECT label_assertion_id FROM cm_label_emission_mismatches",
                tuple(),
            )
            action_rows = _query_all_optional(
                conn,
                self.backend,
                """
                SELECT action_idempotency_key, case_id, status, action_outcome_id
                FROM cm_action_intents
                """,
                tuple(),
            )
            action_mismatch_rows = _query_all_optional(
                conn,
                self.backend,
                "SELECT action_idempotency_key FROM cm_action_intent_mismatches",
                tuple(),
            )
            evidence_requests = _query_all_optional(
                conn,
                self.backend,
                """
                SELECT request_id, case_id
                FROM cm_evidence_resolution_requests
                """,
                tuple(),
            )
            evidence_latest = _query_all_optional(
                conn,
                self.backend,
                """
                SELECT e.request_id, e.status
                FROM cm_evidence_resolution_events e
                INNER JOIN (
                    SELECT request_id, MAX(seq) AS max_seq
                    FROM cm_evidence_resolution_events
                    GROUP BY request_id
                ) latest
                  ON latest.request_id = e.request_id
                 AND latest.max_seq = e.seq
                """,
                tuple(),
            )

        timeline_by_event_id = {str(row[0]): str(row[1]) for row in timeline_rows}
        trigger_case_by_id = {str(row[0]): str(row[1]) for row in trigger_rows}
        label_case_by_id = {str(row[0]): str(row[1]) for row in label_rows}
        action_case_by_key = {str(row[0]): str(row[1]) for row in action_rows}
        evidence_case_by_request = {str(row[0]): str(row[1]) for row in evidence_requests}
        evidence_status_by_request = {str(row[0]): str(row[1]).upper() for row in evidence_latest}

        trigger_count = sum(1 for row in trigger_rows if str(row[1]) in case_ids)
        timeline_filtered = [row for row in timeline_rows if str(row[1]) in case_ids]
        timeline_count = len(timeline_filtered)
        label_rows_filtered = [row for row in label_rows if str(row[1]) in case_ids]
        action_rows_filtered = [row for row in action_rows if str(row[1]) in case_ids]

        timeline_type_counts = _count_values(str(row[2]) for row in timeline_filtered)
        label_status_counts = _count_values(str(row[2]).upper() for row in label_rows_filtered)
        action_status_counts = _count_values(str(row[2]).upper() for row in action_rows_filtered)

        action_outcome_attached_total = sum(
            1
            for row in action_rows_filtered
            if str(row[3] or "").strip()
        )

        trigger_payload_mismatch_total = sum(
            1
            for row in trigger_mismatch_rows
            if trigger_case_by_id.get(str(row[0])) in case_ids
        )
        timeline_payload_mismatch_total = sum(
            1
            for row in timeline_mismatch_rows
            if timeline_by_event_id.get(str(row[0])) in case_ids
        )
        label_payload_mismatch_total = sum(
            1
            for row in label_mismatch_rows
            if label_case_by_id.get(str(row[0])) in case_ids
        )
        action_payload_mismatch_total = sum(
            1
            for row in action_mismatch_rows
            if action_case_by_key.get(str(row[0])) in case_ids
        )
        evidence_forbidden_total = sum(
            1
            for request_id, status in evidence_status_by_request.items()
            if evidence_case_by_request.get(request_id) in case_ids and status == "FORBIDDEN"
        )
        evidence_unavailable_total = sum(
            1
            for request_id, status in evidence_status_by_request.items()
            if evidence_case_by_request.get(request_id) in case_ids and status == "UNAVAILABLE"
        )
        evidence_pending_total = sum(
            1
            for request_id, status in evidence_status_by_request.items()
            if evidence_case_by_request.get(request_id) in case_ids and status == "PENDING"
        )

        anomalies = _build_anomaly_summary(
            trigger_payload_mismatch_total=trigger_payload_mismatch_total,
            timeline_payload_mismatch_total=timeline_payload_mismatch_total,
            label_payload_mismatch_total=label_payload_mismatch_total,
            action_payload_mismatch_total=action_payload_mismatch_total,
            evidence_forbidden_total=evidence_forbidden_total,
            evidence_unavailable_total=evidence_unavailable_total,
        )

        label_assertions_total = len(label_rows_filtered)
        labels_pending_total = int(label_status_counts.get("PENDING", 0))
        labels_accepted_total = int(label_status_counts.get("ACCEPTED", 0))
        labels_rejected_total = int(label_status_counts.get("REJECTED", 0))
        label_submitted_total = int(timeline_type_counts.get("LABEL_PENDING", 0))

        metrics = {
            "case_triggers": trigger_count,
            "cases_created": len(case_ids),
            "timeline_events_appended": timeline_count,
            "label_assertions": label_assertions_total,
            "labels_pending": labels_pending_total,
            "labels_accepted": labels_accepted_total,
            "labels_rejected": labels_rejected_total,
            # Backward-compatible aliases retained for earlier matrix/test wiring.
            "timeline_events": timeline_count,
            "label_pending": label_submitted_total,
            "label_accepted": int(timeline_type_counts.get("LABEL_ACCEPTED", 0)),
            "label_rejected": int(timeline_type_counts.get("LABEL_REJECTED", 0)),
            "action_requested": int(timeline_type_counts.get("ACTION_INTENT_REQUESTED", 0)),
            "action_outcome_attached": int(timeline_type_counts.get("ACTION_OUTCOME_ATTACHED", 0)),
            "action_pending": int(action_status_counts.get("SUBMIT_FAILED_RETRYABLE", 0))
            + int(action_status_counts.get("REQUESTED", 0)),
            "action_submitted": int(action_status_counts.get("SUBMITTED", 0)),
            "action_precheck_rejected": int(action_status_counts.get("PRECHECK_REJECTED", 0)),
            "action_submit_failed_fatal": int(action_status_counts.get("SUBMIT_FAILED_FATAL", 0)),
            "label_status_pending": labels_pending_total,
            "label_status_accepted": labels_accepted_total,
            "label_status_rejected": labels_rejected_total,
            "action_outcome_bound": action_outcome_attached_total,
            "evidence_pending": evidence_pending_total,
            "evidence_forbidden": evidence_forbidden_total,
            "evidence_unavailable": evidence_unavailable_total,
        }

        health = _derive_health(
            metrics=metrics,
            anomalies_total=anomalies["total"],
            thresholds=self.thresholds,
        )
        lifecycle_events = _lifecycle_events_from_timeline(
            rows=timeline_filtered,
            platform_run_id=self.platform_run_id,
            scenario_run_id=self.scenario_run_id,
        )
        generated_at_utc = _utc_now()
        return {
            "generated_at_utc": generated_at_utc,
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
        component_root = run_root / "case_mgmt"

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
            "component": "case_mgmt",
            "metrics_ref": "case_mgmt/metrics/last_metrics.json",
            "reconciliation_ref": "case_mgmt/reconciliation/last_reconciliation.json",
            "governance_ref": "case_mgmt/governance/events.jsonl",
            "summary": {
                "case_triggers": int(payload["metrics"]["case_triggers"]),
                "cases_created": int(payload["metrics"]["cases_created"]),
                "timeline_events_appended": int(payload["metrics"]["timeline_events_appended"]),
                "label_assertions": int(payload["metrics"]["label_assertions"]),
                "labels_pending": int(payload["metrics"]["labels_pending"]),
                "labels_accepted": int(payload["metrics"]["labels_accepted"]),
                "labels_rejected": int(payload["metrics"]["labels_rejected"]),
                "action_submitted": int(payload["metrics"]["action_submitted"]),
                "action_outcome_attached": int(payload["metrics"]["action_outcome_attached"]),
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
            case_labels_reconciliation_dir / "case_mgmt_reconciliation.json",
            case_labels_contribution,
        )
        return payload

    def _connect(self) -> Any:
        if self.backend == "sqlite":
            conn = sqlite3.connect(_sqlite_path(self.locator))
            conn.row_factory = sqlite3.Row
            return conn
        return psycopg.connect(self.locator)


def _pins_match_run(pins: Mapping[str, Any], *, platform_run_id: str, scenario_run_id: str) -> bool:
    return (
        str(pins.get("platform_run_id") or "").strip() == platform_run_id
        and str(pins.get("scenario_run_id") or "").strip() == scenario_run_id
    )


def _build_anomaly_summary(
    *,
    trigger_payload_mismatch_total: int,
    timeline_payload_mismatch_total: int,
    label_payload_mismatch_total: int,
    action_payload_mismatch_total: int,
    evidence_forbidden_total: int,
    evidence_unavailable_total: int,
) -> dict[str, Any]:
    lanes: list[dict[str, Any]] = []
    for kind, total in (
        ("TRIGGER_PAYLOAD_MISMATCH", trigger_payload_mismatch_total),
        ("TIMELINE_PAYLOAD_MISMATCH", timeline_payload_mismatch_total),
        ("LABEL_PAYLOAD_MISMATCH", label_payload_mismatch_total),
        ("ACTION_PAYLOAD_MISMATCH", action_payload_mismatch_total),
        ("EVIDENCE_FORBIDDEN", evidence_forbidden_total),
        ("EVIDENCE_UNAVAILABLE", evidence_unavailable_total),
    ):
        if int(total) > 0:
            lanes.append({"kind": kind, "count": int(total)})
    lanes.sort(key=lambda item: (item["kind"], item["count"]))
    return {
        "total": sum(int(item["count"]) for item in lanes),
        "lanes": lanes,
    }


def _derive_health(
    *,
    metrics: Mapping[str, Any],
    anomalies_total: int,
    thresholds: CaseMgmtHealthThresholds,
) -> dict[str, Any]:
    state = "GREEN"
    reasons: list[str] = []

    pending_actions = int(metrics.get("action_pending", 0))
    pending_labels = int(metrics.get("label_pending", 0))

    if anomalies_total >= thresholds.red_anomalies_total:
        state = "RED"
        reasons.append("ANOMALIES_RED")
    elif anomalies_total >= thresholds.amber_anomalies_total:
        if state != "RED":
            state = "AMBER"
        reasons.append("ANOMALIES_AMBER")

    if pending_actions >= thresholds.red_pending_actions:
        state = "RED"
        reasons.append("ACTION_PENDING_RED")
    elif pending_actions >= thresholds.amber_pending_actions and state != "RED":
        state = "AMBER"
        reasons.append("ACTION_PENDING_AMBER")

    if pending_labels >= thresholds.red_pending_labels:
        state = "RED"
        reasons.append("LABEL_PENDING_RED")
    elif pending_labels >= thresholds.amber_pending_labels and state != "RED":
        state = "AMBER"
        reasons.append("LABEL_PENDING_AMBER")

    return {"state": state, "reasons": reasons}


def _lifecycle_events_from_timeline(
    *,
    rows: list[Any],
    platform_run_id: str,
    scenario_run_id: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        case_timeline_event_id = str(row[0])
        case_id = str(row[1])
        timeline_event_type = str(row[2])
        source_ref_id = str(row[3])
        observed_time = str(row[4])
        event_json = _json_to_dict(row[5])
        pins = _json_to_dict(event_json.get("pins"))
        evidence_refs = _evidence_refs(event_json.get("evidence_refs"))
        timeline_payload = event_json.get("timeline_payload")
        payload = dict(timeline_payload) if isinstance(timeline_payload, Mapping) else {}
        actor_id = str(payload.get("actor_id") or "SYSTEM::unknown")
        source_type = str(payload.get("source_type") or "SYSTEM").upper()

        lifecycle_type = _map_lifecycle_type(timeline_event_type=timeline_event_type, timeline_payload=payload)
        if lifecycle_type is None:
            continue
        event_family = "LABEL_LIFECYCLE" if lifecycle_type.startswith("LABEL_") else "CASE_LIFECYCLE"

        dedupe_basis = f"{platform_run_id}|{case_timeline_event_id}|{lifecycle_type}"
        event_id = hashlib.sha256(dedupe_basis.encode("utf-8")).hexdigest()
        events.append(
            {
                "event_id": event_id,
                "event_family": event_family,
                "lifecycle_type": lifecycle_type,
                "ts_utc": observed_time,
                "actor": {
                    "actor_id": actor_id,
                    "source_type": source_type,
                    "source_component": "case_mgmt",
                },
                "pins": _governance_pins(
                    pins=pins,
                    platform_run_id=platform_run_id,
                    scenario_run_id=scenario_run_id,
                ),
                "details": {
                    "case_id": case_id,
                    "case_timeline_event_id": case_timeline_event_id,
                    "timeline_event_type": timeline_event_type,
                    "source_ref_id": source_ref_id,
                    "evidence_refs": evidence_refs,
                },
            }
        )
    return events


def _map_lifecycle_type(*, timeline_event_type: str, timeline_payload: Mapping[str, Any]) -> str | None:
    if timeline_event_type == "LABEL_PENDING":
        return "LABEL_SUBMITTED"
    if timeline_event_type == "LABEL_ACCEPTED":
        return "LABEL_ACCEPTED"
    if timeline_event_type == "LABEL_REJECTED":
        return "LABEL_REJECTED"
    if timeline_event_type == "ACTION_INTENT_REQUESTED":
        submit_status = str(timeline_payload.get("submit_status") or "").strip().upper()
        if submit_status == "SUBMITTED":
            return "ACTION_INTENT_SUBMITTED"
        if submit_status == "PRECHECK_REJECTED":
            return "ACTION_REQUEST_REJECTED"
        if submit_status == "SUBMIT_FAILED_RETRYABLE":
            return "ACTION_SUBMIT_RETRYABLE"
        if submit_status == "SUBMIT_FAILED_FATAL":
            return "ACTION_SUBMIT_FATAL"
        return "ACTION_REQUESTED"
    if timeline_event_type == "ACTION_OUTCOME_ATTACHED":
        return "ACTION_OUTCOME_ATTACHED"
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


def _evidence_refs(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    refs: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        ref_type = str(item.get("ref_type") or "").strip().upper()
        ref_id = str(item.get("ref_id") or "").strip()
        if ref_type and ref_id:
            refs.append({"ref_type": ref_type, "ref_id": ref_id})
    refs.sort(key=lambda item: (item["ref_type"], item["ref_id"]))
    return refs


def _day_stamp(ts_utc: Any) -> str:
    text = str(ts_utc or "").strip()
    if "T" in text:
        return text.split("T", 1)[0]
    return _utc_now().split("T", 1)[0]


def _count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "").strip().upper()
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _json_to_dict(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _required(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CaseMgmtObservabilityError(f"{field_name} is required")
    return text


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator[len("sqlite:///") :]
    if locator.startswith("sqlite://"):
        return locator[len("sqlite://") :]
    return locator


def _render_sql(sql: str, backend: str) -> str:
    rendered = sql
    if backend == "postgres":
        for idx in range(1, 51):
            rendered = rendered.replace(f"{{p{idx}}}", f"${idx}")
    else:
        for idx in range(1, 51):
            rendered = rendered.replace(f"{{p{idx}}}", "?")
    return rendered


def _query_all(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> list[Any]:
    rendered = _render_sql(sql, backend)
    cur = conn.execute(rendered, params) if backend == "sqlite" else conn.cursor().execute(rendered, params)
    return list(cur.fetchall())


def _query_all_optional(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> list[Any]:
    try:
        return _query_all(conn, backend, sql, params)
    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise


def _is_missing_table_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "no such table" in text
        or "does not exist" in text
        or "undefinedtable" in text
        or "relation" in text and "does not exist" in text
    )
