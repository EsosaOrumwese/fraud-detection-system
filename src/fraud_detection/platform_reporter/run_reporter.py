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
from fraud_detection.postgres_runtime import postgres_threadlocal_connection

from fraud_detection.context_store_flow_binding.intake import CsfbInletPolicy
from fraud_detection.context_store_flow_binding.observability import CsfbObservabilityReporter
from fraud_detection.identity_entity_graph.query import IdentityGraphQuery
from fraud_detection.ingestion_gate.config import WiringProfile
from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn
from fraud_detection.online_feature_plane.observability import OfpObservabilityReporter
from fraud_detection.platform_conformance.checker import run_environment_conformance
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
        archive = self._collect_archive()
        case_labels = self._collect_case_labels()
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
            "archive": archive,
            "case_labels": case_labels,
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

    def _collect_case_labels(self) -> dict[str, Any]:
        run_root = RUNS_ROOT / self.platform_run_id

        case_trigger_metrics = _load_json_file(run_root / "case_trigger" / "metrics" / "last_metrics.json")
        case_trigger_health = _load_json_file(run_root / "case_trigger" / "health" / "last_health.json")
        case_mgmt_metrics = _load_json_file(run_root / "case_mgmt" / "metrics" / "last_metrics.json")
        case_mgmt_health = _load_json_file(run_root / "case_mgmt" / "health" / "last_health.json")
        label_store_metrics = _load_json_file(run_root / "label_store" / "metrics" / "last_metrics.json")
        label_store_health = _load_json_file(run_root / "label_store" / "health" / "last_health.json")

        notes: list[str] = []
        if not case_trigger_metrics:
            notes.append("CaseTrigger metrics unavailable for run.")
        if not case_mgmt_metrics:
            notes.append("CaseMgmt metrics unavailable for run.")
        if not label_store_metrics:
            notes.append("LabelStore metrics unavailable for run.")

        ct_metrics = _mapping(case_trigger_metrics.get("metrics"))
        cm_metrics = _mapping(case_mgmt_metrics.get("metrics"))
        ls_metrics = _mapping(label_store_metrics.get("metrics"))
        cm_anomalies = _mapping(case_mgmt_health.get("anomalies"))
        ls_anomalies = _mapping(label_store_health.get("anomalies"))

        anomalies_total = int(cm_anomalies.get("total", 0)) + int(ls_anomalies.get("total", 0))
        summary = {
            "triggers_seen": int(ct_metrics.get("triggers_seen", 0)),
            "cases_created": int(cm_metrics.get("cases_created", 0)),
            "labels_pending": int(ls_metrics.get("pending", 0)),
            "labels_accepted": int(ls_metrics.get("accepted", 0)),
            "labels_rejected": int(ls_metrics.get("rejected", 0)),
            "anomalies_total": anomalies_total,
        }
        return {
            "summary": summary,
            "health_states": {
                "case_trigger": str(case_trigger_health.get("health_state") or "UNKNOWN"),
                "case_mgmt": str(case_mgmt_health.get("health_state") or "UNKNOWN"),
                "label_store": str(label_store_health.get("health_state") or "UNKNOWN"),
            },
            "component_metrics": {
                "case_trigger": ct_metrics,
                "case_mgmt": cm_metrics,
                "label_store": ls_metrics,
            },
            "basis_notes": notes,
        }

    def export(self) -> dict[str, Any]:
        payload = self.collect()
        self._emit_evidence_resolution_events(payload)
        run_root = RUNS_ROOT / self.platform_run_id
        local_path = run_root / "obs" / "platform_run_report.json"
        _write_json_file(local_path, payload)

        store_path = f"{_run_prefix_for_store(self.store, self.platform_run_id)}/obs/platform_run_report.json"
        self.store.write_json(store_path, payload)
        self._emit_report_generated_event(payload)
        closure_bundle_refs = self._emit_closure_bundle(payload=payload, run_root=run_root, report_store_path=store_path)
        payload["artifact_refs"] = {
            "local_path": str(local_path),
            "object_store_path": store_path,
            "closure_bundle": closure_bundle_refs,
        }
        return payload

    def _emit_closure_bundle(
        self,
        *,
        payload: dict[str, Any],
        run_root: Path,
        report_store_path: str,
    ) -> dict[str, dict[str, str]]:
        run_prefix = _run_prefix_for_store(self.store, self.platform_run_id)
        local_run_completed_path = run_root / "run_completed.json"
        local_run_report_path = run_root / "obs" / "run_report.json"
        local_reconciliation_path = run_root / "obs" / "reconciliation.json"
        local_replay_anchors_path = run_root / "obs" / "replay_anchors.json"
        local_environment_conformance_path = run_root / "obs" / "environment_conformance.json"
        local_anomaly_summary_path = run_root / "obs" / "anomaly_summary.json"

        store_run_completed_path = f"{run_prefix}/run_completed.json"
        store_run_report_path = f"{run_prefix}/obs/run_report.json"
        store_reconciliation_path = f"{run_prefix}/obs/reconciliation.json"
        store_replay_anchors_path = f"{run_prefix}/obs/replay_anchors.json"
        store_environment_conformance_path = f"{run_prefix}/obs/environment_conformance.json"
        store_anomaly_summary_path = f"{run_prefix}/obs/anomaly_summary.json"

        run_report_payload = dict(payload)
        reconciliation_payload = _build_reconciliation_payload(payload)
        replay_anchors_payload = _build_replay_anchors_payload(
            store=self.store,
            platform_run_id=self.platform_run_id,
            run_prefix=run_prefix,
            report_store_path=report_store_path,
        )
        environment_conformance_payload = self._build_environment_conformance_payload(
            output_path=local_environment_conformance_path
        )
        anomaly_summary_payload = _build_anomaly_summary_payload(payload)
        run_completed_payload = _build_run_completed_payload(
            platform_run_id=self.platform_run_id,
            run_report_ref=store_run_report_path,
            reconciliation_ref=store_reconciliation_path,
            replay_anchors_ref=store_replay_anchors_path,
            environment_conformance_ref=store_environment_conformance_path,
            anomaly_summary_ref=store_anomaly_summary_path,
            governance_events_ref=f"{run_prefix}/obs/governance/events.jsonl",
        )

        _write_json_file(local_run_report_path, run_report_payload)
        _write_json_file(local_reconciliation_path, reconciliation_payload)
        _write_json_file(local_replay_anchors_path, replay_anchors_payload)
        _write_json_file(local_environment_conformance_path, environment_conformance_payload)
        _write_json_file(local_anomaly_summary_path, anomaly_summary_payload)
        _write_json_file(local_run_completed_path, run_completed_payload)

        self.store.write_json(store_run_report_path, run_report_payload)
        self.store.write_json(store_reconciliation_path, reconciliation_payload)
        self.store.write_json(store_replay_anchors_path, replay_anchors_payload)
        self.store.write_json(store_environment_conformance_path, environment_conformance_payload)
        self.store.write_json(store_anomaly_summary_path, anomaly_summary_payload)
        self.store.write_json(store_run_completed_path, run_completed_payload)

        return {
            "run_completed": {
                "local_path": str(local_run_completed_path),
                "object_store_path": store_run_completed_path,
            },
            "run_report": {
                "local_path": str(local_run_report_path),
                "object_store_path": store_run_report_path,
            },
            "reconciliation": {
                "local_path": str(local_reconciliation_path),
                "object_store_path": store_reconciliation_path,
            },
            "replay_anchors": {
                "local_path": str(local_replay_anchors_path),
                "object_store_path": store_replay_anchors_path,
            },
            "environment_conformance": {
                "local_path": str(local_environment_conformance_path),
                "object_store_path": store_environment_conformance_path,
            },
            "anomaly_summary": {
                "local_path": str(local_anomaly_summary_path),
                "object_store_path": store_anomaly_summary_path,
            },
        }

    def _build_environment_conformance_payload(self, *, output_path: Path) -> dict[str, Any]:
        local_parity_profile = os.getenv(
            "PLATFORM_CONFORMANCE_LOCAL_PARITY_PROFILE",
            "config/platform/profiles/local_parity.yaml",
        )
        dev_profile = os.getenv(
            "PLATFORM_CONFORMANCE_DEV_PROFILE",
            "config/platform/profiles/dev.yaml",
        )
        prod_profile = os.getenv(
            "PLATFORM_CONFORMANCE_PROD_PROFILE",
            "config/platform/profiles/prod.yaml",
        )
        try:
            result = run_environment_conformance(
                local_parity_profile=local_parity_profile,
                dev_profile=dev_profile,
                prod_profile=prod_profile,
                platform_run_id=self.platform_run_id,
                output_path=str(output_path),
            )
            return dict(result.payload)
        except Exception as exc:
            return {
                "generated_at_utc": _utc_now(),
                "platform_run_id": self.platform_run_id,
                "status": "DEGRADED",
                "error": f"ENV_CONFORMANCE_UNAVAILABLE:{str(exc)[:256]}",
                "profiles": {
                    "local_parity_profile": local_parity_profile,
                    "dev_profile": dev_profile,
                    "prod_profile": prod_profile,
                },
            }

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

    def _collect_archive(self) -> dict[str, Any]:
        run_root = RUNS_ROOT / self.platform_run_id
        metrics_payload = _load_json_file(run_root / "archive_writer" / "metrics" / "last_metrics.json")
        health_payload = _load_json_file(run_root / "archive_writer" / "health" / "last_health.json")
        reconciliation_payload = _load_json_file(
            run_root / "archive" / "reconciliation" / "archive_writer_reconciliation.json"
        )
        metrics = _mapping(metrics_payload.get("metrics"))
        return {
            "summary": {
                "seen_total": int(metrics.get("seen_total", 0)),
                "archived_total": int(metrics.get("archived_total", 0)),
                "duplicate_total": int(metrics.get("duplicate_total", 0)),
                "payload_mismatch_total": int(metrics.get("payload_mismatch_total", 0)),
                "write_error_total": int(metrics.get("write_error_total", 0)),
            },
            "health_state": str(health_payload.get("health_state") or "UNKNOWN"),
            "reconciliation_totals": _mapping(reconciliation_payload.get("totals")),
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
        with postgres_threadlocal_connection(locator) as conn:
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
        with postgres_threadlocal_connection(locator) as conn:
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
        with postgres_threadlocal_connection(locator) as conn:
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
        root / "archive" / "reconciliation" / "archive_writer_reconciliation.json",
        root / "ofs" / "reconciliation" / "last_reconciliation.json",
        root / "learning" / "reconciliation" / "ofs_reconciliation.json",
        root / "decision_fabric" / "reconciliation" / "reconciliation.json",
        root / "case_trigger" / "reconciliation" / "reconciliation.json",
        root / "case_mgmt" / "reconciliation" / "last_reconciliation.json",
        root / "label_store" / "reconciliation" / "last_reconciliation.json",
        root / "case_labels" / "reconciliation" / "case_mgmt_reconciliation.json",
        root / "case_labels" / "reconciliation" / "label_store_reconciliation.json",
        root / "decision_log_audit" / "reconciliation" / "last_reconciliation.json",
    ]
    return [str(path) for path in candidates if path.exists()]


def _build_reconciliation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    ingress = _mapping(payload.get("ingress"))
    rtdl = _mapping(payload.get("rtdl"))
    archive = _mapping(payload.get("archive"))
    archive_summary = _mapping(archive.get("summary"))
    case_labels = _mapping(payload.get("case_labels"))
    case_summary = _mapping(case_labels.get("summary"))
    checks = {
        "sent_ge_received": int(ingress.get("sent", 0)) >= int(ingress.get("received", 0)),
        "received_ge_admit": int(ingress.get("received", 0)) >= int(ingress.get("admit", 0)),
        "decision_ge_outcome": int(rtdl.get("decision", 0)) >= int(rtdl.get("outcome", 0)),
        "archive_seen_ge_archived": int(archive_summary.get("seen_total", 0)) >= int(archive_summary.get("archived_total", 0)),
    }
    status = "PASS" if all(bool(value) for value in checks.values()) else "WARN"
    return {
        "generated_at_utc": _utc_now(),
        "platform_run_id": str(payload.get("platform_run_id") or "").strip() or None,
        "status": status,
        "checks": checks,
        "inputs": {
            "ingress": ingress,
            "rtdl": rtdl,
            "archive_summary": archive_summary,
            "case_labels_summary": case_summary,
        },
        "deltas": {
            "sent_minus_received": int(ingress.get("sent", 0)) - int(ingress.get("received", 0)),
            "received_minus_admit": int(ingress.get("received", 0)) - int(ingress.get("admit", 0)),
            "decision_minus_outcome": int(rtdl.get("decision", 0)) - int(rtdl.get("outcome", 0)),
        },
        "basis": {
            "component_reconciliation_refs": list(_mapping(payload.get("evidence_refs")).get("component_reconciliation_refs") or []),
        },
    }


def _build_replay_anchors_payload(
    *,
    store: ObjectStore,
    platform_run_id: str,
    run_prefix: str,
    report_store_path: str,
) -> dict[str, Any]:
    ingest_offsets_ref = f"{run_prefix}/ingest/kafka_offsets_snapshot.json"
    rtdl_offsets_ref = f"{run_prefix}/rtdl_core/offsets_snapshot.json"
    ingest_payload = _store_json_if_exists(store, ingest_offsets_ref)
    rtdl_payload = _store_json_if_exists(store, rtdl_offsets_ref)
    ingest_offsets = _collect_topic_partition_offsets(ingest_payload)
    rtdl_offsets = _collect_topic_partition_offsets(rtdl_payload)
    return {
        "generated_at_utc": _utc_now(),
        "platform_run_id": platform_run_id,
        "anchors": {
            "ingest": ingest_offsets,
            "rtdl_core": rtdl_offsets,
        },
        "source_refs": {
            "ingest_offsets_ref": ingest_offsets_ref,
            "rtdl_offsets_ref": rtdl_offsets_ref,
            "run_report_ref": report_store_path,
        },
        "counts": {
            "ingest_anchors": len(ingest_offsets),
            "rtdl_anchors": len(rtdl_offsets),
        },
    }


def _build_anomaly_summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    ingress = _mapping(payload.get("ingress"))
    rtdl = _mapping(payload.get("rtdl"))
    case_labels = _mapping(payload.get("case_labels"))
    case_summary = _mapping(case_labels.get("summary"))
    anomaly_counts = {
        "ingress_publish_ambiguous": int(ingress.get("publish_ambiguous", 0)),
        "ingress_receipt_write_failed": int(ingress.get("receipt_write_failed", 0)),
        "rtdl_degraded": int(rtdl.get("degraded", 0)),
        "case_labels_anomalies_total": int(case_summary.get("anomalies_total", 0)),
    }
    total = sum(anomaly_counts.values())
    return {
        "generated_at_utc": _utc_now(),
        "platform_run_id": str(payload.get("platform_run_id") or "").strip() or None,
        "status": "PASS" if total == 0 else "WARN",
        "anomaly_counts": anomaly_counts,
        "anomaly_total": total,
    }


def _build_run_completed_payload(
    *,
    platform_run_id: str,
    run_report_ref: str,
    reconciliation_ref: str,
    replay_anchors_ref: str,
    environment_conformance_ref: str,
    anomaly_summary_ref: str,
    governance_events_ref: str,
) -> dict[str, Any]:
    return {
        "generated_at_utc": _utc_now(),
        "platform_run_id": platform_run_id,
        "status": "COMPLETED",
        "closure_refs": {
            "run_report_ref": run_report_ref,
            "reconciliation_ref": reconciliation_ref,
            "replay_anchors_ref": replay_anchors_ref,
            "environment_conformance_ref": environment_conformance_ref,
            "anomaly_summary_ref": anomaly_summary_ref,
            "governance_events_ref": governance_events_ref,
        },
    }


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


def _store_json_if_exists(store: ObjectStore, relative_path: str) -> dict[str, Any]:
    try:
        if not store.exists(relative_path):
            return {}
        payload = store.read_json(relative_path)
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _collect_topic_partition_offsets(payload: Any) -> list[dict[str, Any]]:
    offsets: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            topic = node.get("topic")
            partition = node.get("partition")
            offset = node.get("offset")
            if topic is not None and partition is not None and offset is not None:
                key = (str(topic), str(partition), str(offset))
                if key not in seen:
                    seen.add(key)
                    offsets.append(
                        {
                            "topic": str(topic),
                            "partition": int(partition) if str(partition).isdigit() else partition,
                            "offset": str(offset),
                        }
                    )
            for value in node.values():
                visit(value)
            return
        if isinstance(node, list):
            for item in node:
                visit(item)

    visit(payload)
    return offsets


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


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


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

