"""Platform-level run reporter (4.6.D)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import psycopg

from fraud_detection.context_store_flow_binding.intake import CsfbInletPolicy
from fraud_detection.context_store_flow_binding.observability import CsfbObservabilityReporter
from fraud_detection.identity_entity_graph.query import IdentityGraphQuery
from fraud_detection.ingestion_gate.config import WiringProfile
from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn
from fraud_detection.online_feature_plane.observability import OfpObservabilityReporter
from fraud_detection.platform_governance import (
    EvidenceRefResolutionRequest,
    build_evidence_ref_resolution_corridor,
    emit_platform_governance_event,
)
from fraud_detection.platform_provenance import runtime_provenance
from fraud_detection.platform_runtime import RUNS_ROOT, resolve_platform_run_id
from fraud_detection.scenario_runner.storage import (
    LocalObjectStore,
    ObjectStore,
    S3ObjectStore,
    build_object_store,
)


class PlatformRunReporterError(RuntimeError):
    """Raised when platform run reporter inputs are invalid."""


@dataclass
class PlatformRunReporter:
    profile_path: Path
    platform_run_id: str
    store: ObjectStore
    ig_admission_locator: str
    evidence_allowlist: tuple[str, ...]
    profile_id: str
    config_revision: str

    @classmethod
    def build(
        cls,
        *,
        profile_path: str,
        platform_run_id: str | None = None,
    ) -> "PlatformRunReporter":
        path = Path(profile_path)
        if not path.exists():
            raise PlatformRunReporterError(f"profile not found: {path}")
        ig_wiring = WiringProfile.load(path)
        run_id = str(platform_run_id or resolve_platform_run_id(create_if_missing=False) or "").strip()
        if not run_id:
            raise PlatformRunReporterError("platform_run_id is required")
        store = build_object_store(
            ig_wiring.object_store_root,
            s3_endpoint_url=ig_wiring.object_store_endpoint,
            s3_region=ig_wiring.object_store_region,
            s3_path_style=ig_wiring.object_store_path_style,
        )
        return cls(
            profile_path=path,
            platform_run_id=run_id,
            store=store,
            ig_admission_locator=ig_wiring.admission_db_path,
            evidence_allowlist=_evidence_allowlist_from_env(),
            profile_id=ig_wiring.profile_id,
            config_revision=ig_wiring.policy_rev,
        )

    def collect(self) -> dict[str, Any]:
        ingress = self._collect_ingress()
        scenario_run_ids = sorted(
            {
                *(ingress["scenario_run_ids"]),
                *(ingress["wsp_scenario_run_ids"]),
            }
        )
        rtdl = self._collect_rtdl(scenario_run_ids=scenario_run_ids, ingress=ingress)
        reconciliation_refs = _component_reconciliation_refs(self.platform_run_id)
        evidence_refs = {
            "receipt_refs_sample": ingress["receipt_refs_sample"],
            "quarantine_refs_sample": ingress["quarantine_refs_sample"],
            "component_reconciliation_refs": reconciliation_refs,
        }
        payload = {
            "generated_at_utc": _utc_now(),
            "platform_run_id": self.platform_run_id,
            "scenario_run_ids": scenario_run_ids,
            "ingress": ingress["counters"],
            "rtdl": rtdl,
            "evidence_refs": evidence_refs,
            "basis": {
                "profile_path": str(self.profile_path),
                "ig_admission_locator": self.ig_admission_locator,
                "run_prefix": _run_prefix_for_store(self.store, self.platform_run_id),
                "provenance": runtime_provenance(
                    component="platform_run_reporter",
                    environment=self.profile_id,
                    config_revision=self.config_revision,
                ),
            },
        }
        return payload

    def export(self) -> dict[str, Any]:
        payload = self.collect()
        self._emit_evidence_resolution_events(payload)
        run_root = RUNS_ROOT / self.platform_run_id
        local_path = run_root / "obs" / "platform_run_report.json"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        store_path = f"{_run_prefix_for_store(self.store, self.platform_run_id)}/obs/platform_run_report.json"
        self.store.write_json(store_path, payload)
        self._emit_report_generated_event(payload)
        payload["artifact_refs"] = {
            "local_path": str(local_path),
            "object_store_path": store_path,
        }
        return payload

    def _collect_ingress(self) -> dict[str, Any]:
        ready_summary = _collect_wsp_ready_summary(self.store, self.platform_run_id)
        ops = _query_ops_receipts(self.ig_admission_locator, self.platform_run_id)
        admission = _query_admissions(self.ig_admission_locator, self.platform_run_id)
        received_total = int(ops["total"]) + int(admission["receipt_write_failed"])
        counters = {
            "sent": int(ready_summary["sent"]),
            "received": received_total,
            "admit": int(ops["decision_counts"].get("ADMIT", 0)),
            "duplicate": int(ops["decision_counts"].get("DUPLICATE", 0)),
            "quarantine": int(ops["decision_counts"].get("QUARANTINE", 0)),
            "publish_ambiguous": int(admission["publish_ambiguous"]),
            "receipt_write_failed": int(admission["receipt_write_failed"]),
        }
        return {
            "counters": counters,
            "scenario_run_ids": ops["scenario_run_ids"],
            "wsp_scenario_run_ids": ready_summary["scenario_run_ids"],
            "receipt_event_type_counts": ops["event_type_counts"],
            "receipt_refs_sample": ops["receipt_refs_sample"],
            "quarantine_refs_sample": ops["quarantine_refs_sample"],
        }

    def _collect_rtdl(self, *, scenario_run_ids: list[str], ingress: dict[str, Any]) -> dict[str, Any]:
        notes: list[str] = []
        ieg_inlet_seen = 0
        ofp_inlet_seen = 0
        deduped_total = 0
        degraded_total = 0

        try:
            ieg_query = IdentityGraphQuery.from_profile(str(self.profile_path))
            for scenario_run_id in scenario_run_ids:
                status = ieg_query.status(scenario_run_id=scenario_run_id)
                metrics = _mapping(status.get("metrics"))
                ieg_inlet_seen += int(metrics.get("events_seen", 0))
                deduped_total += int(metrics.get("duplicate", 0))
                degraded_total += int(status.get("apply_failure_count", 0))
        except Exception as exc:
            notes.append(f"IEG metrics unavailable: {str(exc)[:256]}")

        try:
            ofp_reporter = OfpObservabilityReporter.build(str(self.profile_path))
            for scenario_run_id in scenario_run_ids:
                snapshot = ofp_reporter.collect(scenario_run_id=scenario_run_id)
                metrics = _mapping(snapshot.get("metrics"))
                ofp_inlet_seen += int(metrics.get("events_seen", 0))
                deduped_total += int(metrics.get("duplicates", 0))
                degraded_total += int(metrics.get("payload_hash_mismatch", 0))
                degraded_total += int(metrics.get("missing_features", 0))
                degraded_total += int(metrics.get("stale_graph_version", 0))
        except Exception as exc:
            notes.append(f"OFP metrics unavailable: {str(exc)[:256]}")

        try:
            csfb_policy = CsfbInletPolicy.load(self.profile_path)
            csfb_reporter = CsfbObservabilityReporter.build(
                locator=csfb_policy.projection_db_dsn,
                stream_id=csfb_policy.stream_id,
            )
            for scenario_run_id in scenario_run_ids:
                snapshot = csfb_reporter.collect(
                    platform_run_id=self.platform_run_id,
                    scenario_run_id=scenario_run_id,
                )
                metrics = _mapping(snapshot.get("metrics"))
                degraded_total += int(metrics.get("apply_failures_hard", metrics.get("apply_failures", 0)))
        except Exception as exc:
            notes.append(f"CSFB metrics unavailable: {str(exc)[:256]}")

        dla_append = _load_dla_append_success_total(self.platform_run_id)
        if dla_append == 0:
            notes.append("DLA append counter defaults to zero unless decision_log_audit metrics artifact exists for this run.")

        event_type_counts = ingress["receipt_event_type_counts"]
        decision_total = int(event_type_counts.get("decision_response", 0))
        outcome_total = int(event_type_counts.get("action_outcome", 0))

        return {
            "inlet_seen": max(ieg_inlet_seen, ofp_inlet_seen),
            "deduped": deduped_total,
            "degraded": degraded_total,
            "decision": decision_total,
            "outcome": outcome_total,
            "audit_append": dla_append,
            "basis_notes": notes,
            "component_bases": {
                "ieg_events_seen": ieg_inlet_seen,
                "ofp_events_seen": ofp_inlet_seen,
            },
        }

    def _emit_evidence_resolution_events(self, payload: dict[str, Any]) -> None:
        corridor = build_evidence_ref_resolution_corridor(
            store=self.store,
            actor_allowlist=list(self.evidence_allowlist),
        )
        evidence = _mapping(payload.get("evidence_refs"))
        refs: list[tuple[str, str]] = []
        for ref in list(evidence.get("receipt_refs_sample") or []):
            refs.append(("receipt_ref", str(ref)))
        for ref in list(evidence.get("quarantine_refs_sample") or []):
            refs.append(("quarantine_ref", str(ref)))
        for ref in list(evidence.get("component_reconciliation_refs") or []):
            refs.append(("reconciliation_ref", str(ref)))
        scenario_run_ids = list(payload.get("scenario_run_ids") or [])
        scenario_run_id = str(scenario_run_ids[0]) if scenario_run_ids else None
        resolved = 0
        denied = 0
        for ref_type, ref_id in refs[:50]:
            result = corridor.resolve(
                EvidenceRefResolutionRequest(
                    actor_id="SYSTEM::platform_run_reporter",
                    source_type="SYSTEM",
                    source_component="platform_run_reporter",
                    purpose="platform_run_report",
                    ref_type=ref_type,
                    ref_id=ref_id,
                    platform_run_id=self.platform_run_id,
                    scenario_run_id=scenario_run_id,
                )
            )
            if result.resolution_status == "RESOLVED":
                resolved += 1
            else:
                denied += 1
        basis = _mapping(payload.get("basis"))
        basis["evidence_ref_resolution"] = {
            "attempted": min(len(refs), 50),
            "resolved": resolved,
            "denied": denied,
            "allowlist_size": len(self.evidence_allowlist),
        }
        payload["basis"] = basis

    def _emit_report_generated_event(self, payload: dict[str, Any]) -> None:
        emit_platform_governance_event(
            store=self.store,
            event_family="RUN_REPORT_GENERATED",
            actor_id="SYSTEM::platform_run_reporter",
            source_type="SYSTEM",
            source_component="platform_run_reporter",
            platform_run_id=self.platform_run_id,
            dedupe_key=f"run_report_generated:{self.platform_run_id}",
            details={
                "ingress": payload.get("ingress"),
                "rtdl": payload.get("rtdl"),
                "run_config_digest": self.config_revision,
                "provenance": runtime_provenance(
                    component="platform_run_reporter",
                    environment=self.profile_id,
                    config_revision=self.config_revision,
                    run_config_digest=self.config_revision,
                ),
            },
        )


def _evidence_allowlist_from_env() -> tuple[str, ...]:
    raw = (os.getenv("EVIDENCE_REF_RESOLVER_ALLOWLIST") or "").strip()
    if not raw:
        return ("SYSTEM::platform_run_reporter",)
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    if values:
        return values
    return ("SYSTEM::platform_run_reporter",)


def _collect_wsp_ready_summary(store: ObjectStore, platform_run_id: str) -> dict[str, Any]:
    run_prefix = _run_prefix_for_store(store, platform_run_id)
    directory = f"{run_prefix}/wsp/ready_runs"
    try:
        files = store.list_files(directory)
    except Exception:
        return {"sent": 0, "scenario_run_ids": []}
    sent_by_message_id: dict[str, int] = {}
    scenario_run_ids: set[str] = set()
    for file_path in files:
        text = _read_store_text(store, file_path)
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            status = str(payload.get("status") or "").upper()
            if status != "STREAMED":
                continue
            message_id = str(payload.get("message_id") or "")
            if not message_id:
                continue
            emitted = int(payload.get("emitted") or 0)
            prior = sent_by_message_id.get(message_id, 0)
            if emitted > prior:
                sent_by_message_id[message_id] = emitted
            run_id = str(payload.get("run_id") or "").strip()
            if run_id:
                scenario_run_ids.add(run_id)
    return {"sent": sum(sent_by_message_id.values()), "scenario_run_ids": sorted(scenario_run_ids)}


def _query_ops_receipts(locator: str, platform_run_id: str) -> dict[str, Any]:
    rows = _query_ops_receipt_rows(locator)
    decision_counts: dict[str, int] = {}
    event_type_counts: dict[str, int] = {}
    scenario_run_ids: set[str] = set()
    receipt_refs: list[str] = []
    quarantine_refs: list[str] = []
    total = 0
    for row in rows:
        pins = _json_object(row.get("pins_json"))
        pins_platform_run_id = str(pins.get("platform_run_id") or "").strip()
        if pins_platform_run_id != platform_run_id:
            continue
        total += 1
        decision = str(row.get("decision") or "").upper()
        if decision:
            decision_counts[decision] = int(decision_counts.get(decision, 0)) + 1
        event_type = str(row.get("event_type") or "").strip()
        if event_type:
            event_type_counts[event_type] = int(event_type_counts.get(event_type, 0)) + 1
        scenario_run_id = str(pins.get("scenario_run_id") or "").strip()
        if scenario_run_id:
            scenario_run_ids.add(scenario_run_id)
        receipt_ref = str(row.get("receipt_ref") or "").strip()
        if receipt_ref:
            receipt_refs.append(receipt_ref)
        for ref in _evidence_ref_values(row.get("evidence_refs_json")):
            quarantine_refs.append(ref)
    for row in _query_ops_quarantine_rows(locator):
        pins = _json_object(row.get("pins_json"))
        pins_platform_run_id = str(pins.get("platform_run_id") or "").strip()
        if pins_platform_run_id != platform_run_id:
            continue
        ref = str(row.get("evidence_ref") or "").strip()
        if ref:
            quarantine_refs.append(ref)
    return {
        "total": total,
        "decision_counts": decision_counts,
        "event_type_counts": event_type_counts,
        "scenario_run_ids": sorted(scenario_run_ids),
        "receipt_refs_sample": receipt_refs[:50],
        "quarantine_refs_sample": quarantine_refs[:50],
    }


def _query_admissions(locator: str, platform_run_id: str) -> dict[str, int]:
    publish_ambiguous = 0
    receipt_write_failed = 0
    if is_postgres_dsn(locator):
        with psycopg.connect(locator) as conn:
            rows = conn.execute(
                """
                SELECT state, receipt_write_failed
                FROM admissions
                WHERE platform_run_id = %s
                """,
                (platform_run_id,),
            ).fetchall()
    else:
        path = _sqlite_path(locator)
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                """
                SELECT state, receipt_write_failed
                FROM admissions
                WHERE platform_run_id = ?
                """,
                (platform_run_id,),
            ).fetchall()
    for state_raw, failed_raw in rows:
        state = str(state_raw or "").upper()
        if state == "PUBLISH_AMBIGUOUS":
            publish_ambiguous += 1
        if int(failed_raw or 0) > 0:
            receipt_write_failed += 1
    return {
        "publish_ambiguous": publish_ambiguous,
        "receipt_write_failed": receipt_write_failed,
    }


def _query_ops_receipt_rows(locator: str) -> list[dict[str, Any]]:
    query = """
        SELECT decision, event_type, receipt_ref, pins_json, evidence_refs_json
        FROM receipts
    """
    if is_postgres_dsn(locator):
        with psycopg.connect(locator) as conn:
            rows = conn.execute(query).fetchall()
        return [
            {
                "decision": row[0],
                "event_type": row[1],
                "receipt_ref": row[2],
                "pins_json": row[3],
                "evidence_refs_json": row[4],
            }
            for row in rows
        ]
    path = _sqlite_path(locator)
    with sqlite3.connect(path) as conn:
        rows = conn.execute(query).fetchall()
    return [
        {
            "decision": row[0],
            "event_type": row[1],
            "receipt_ref": row[2],
            "pins_json": row[3],
            "evidence_refs_json": row[4],
        }
        for row in rows
    ]


def _query_ops_quarantine_rows(locator: str) -> list[dict[str, Any]]:
    query = """
        SELECT evidence_ref, pins_json
        FROM quarantines
    """
    if is_postgres_dsn(locator):
        with psycopg.connect(locator) as conn:
            rows = conn.execute(query).fetchall()
        return [{"evidence_ref": row[0], "pins_json": row[1]} for row in rows]
    path = _sqlite_path(locator)
    with sqlite3.connect(path) as conn:
        rows = conn.execute(query).fetchall()
    return [{"evidence_ref": row[0], "pins_json": row[1]} for row in rows]


def _component_reconciliation_refs(platform_run_id: str) -> list[str]:
    root = RUNS_ROOT / platform_run_id
    candidates = [
        root / "identity_entity_graph" / "reconciliation" / "reconciliation.json",
        root / "context_store_flow_binding" / "reconciliation" / "last_reconciliation.json",
        root / "decision_fabric" / "reconciliation" / "reconciliation.json",
        root / "case_trigger" / "reconciliation" / "reconciliation.json",
        root / "decision_log_audit" / "reconciliation" / "last_reconciliation.json",
    ]
    return [str(path) for path in candidates if path.exists()]


def _load_dla_append_success_total(platform_run_id: str) -> int:
    path = RUNS_ROOT / platform_run_id / "decision_log_audit" / "metrics" / "last_metrics.json"
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    metrics = _mapping(payload.get("metrics"))
    return int(metrics.get("append_success_total", 0))


def _read_store_text(store: ObjectStore, path: str) -> str:
    if isinstance(store, S3ObjectStore):
        return store.read_text(_s3_relative_path(store, path))
    return store.read_text(path)


def _s3_relative_path(store: S3ObjectStore, absolute_path: str) -> str:
    text = str(absolute_path or "").strip()
    if not text.startswith("s3://"):
        return text
    prefix = f"s3://{store.bucket}/"
    if not text.startswith(prefix):
        return text
    key = text[len(prefix) :]
    store_prefix = f"{store.prefix}/" if store.prefix else ""
    if store_prefix and key.startswith(store_prefix):
        return key[len(store_prefix) :]
    return key


def _run_prefix_for_store(store: ObjectStore, platform_run_id: str) -> str:
    if isinstance(store, S3ObjectStore):
        return platform_run_id
    if isinstance(store, LocalObjectStore) and store.root.name == "fraud-platform":
        return platform_run_id
    return f"fraud-platform/{platform_run_id}"


def _sqlite_path(locator: str) -> str:
    text = str(locator or "").strip()
    if text.startswith("sqlite:///"):
        return text[len("sqlite:///") :]
    if text.startswith("sqlite://"):
        return text[len("sqlite://") :]
    return text


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _json_object(raw: Any) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    try:
        payload = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _evidence_ref_values(raw: Any) -> list[str]:
    if raw in (None, ""):
        return []
    try:
        payload = json.loads(str(raw))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    refs: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or "").strip()
        if ref:
            refs.append(ref)
    return refs


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
