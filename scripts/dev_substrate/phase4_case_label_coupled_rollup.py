#!/usr/bin/env python3
"""Score a bounded Phase 4 coupled-network validation slice."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path: Path) -> dict[str, Any] | None:
    return load_json(path) if path.exists() else None


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summary_value(snapshot: dict[str, Any], component: str, field: str) -> float | None:
    return to_float((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get(field))


def summary_text(snapshot: dict[str, Any], component: str, field: str) -> str:
    value = ((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get(field))
    return str(value or "").strip()


def health_state(snapshot: dict[str, Any], component: str) -> str:
    return str((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get("health_state") or "UNKNOWN")


def health_reasons(snapshot: dict[str, Any], component: str) -> list[str]:
    raw = ((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get("health_reasons"))
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def is_missing(snapshot: dict[str, Any], component: str) -> bool:
    payloads = ((snapshot.get("components") or {}).get(component) or {})
    for key in ("metrics_payload", "health_payload"):
        payload = payloads.get(key) or {}
        if payload.get("__missing__") or payload.get("__unreadable__"):
            return True
    return False


def delta(pre: dict[str, Any], post: dict[str, Any], component: str, field: str) -> float | None:
    start = summary_value(pre, component, field)
    end = summary_value(post, component, field)
    if end is None:
        return None
    if start is None:
        start = 0.0
    return float(end - start)


def replay_advisory_only(snapshot: dict[str, Any], component: str, max_checkpoint: float, max_lag: float) -> bool:
    if component not in {"csfb", "ieg", "ofp"}:
        return False
    if health_state(snapshot, component).upper() not in {"RED", "FAILED", "UNHEALTHY"}:
        return False
    reasons = set(health_reasons(snapshot, component))
    checkpoint = summary_value(snapshot, component, "checkpoint_age_seconds")
    if checkpoint is None:
        return False
    lag = summary_value(snapshot, component, "lag_seconds")
    if component != "csfb" and lag is not None and lag > max_lag:
        return False
    if component == "csfb":
        if not reasons or not reasons.issubset({"WATERMARK_TOO_OLD", "CHECKPOINT_TOO_OLD", "CHECKPOINT_OLD"}):
            return False
        return (summary_value(snapshot, component, "join_misses") or 0.0) == 0.0 and (
            summary_value(snapshot, component, "binding_conflicts") or 0.0
        ) == 0.0 and (summary_value(snapshot, component, "apply_failures_hard") or 0.0) == 0.0
    if checkpoint > max_checkpoint:
        return False
    if component == "ofp":
        if reasons == {"WATERMARK_TOO_OLD"}:
            return lag is not None and lag <= max_lag
        if reasons == {"WATERMARK_TOO_OLD", "STALE_GRAPH_VERSION_RED"}:
            if (summary_value(snapshot, component, "missing_features") or 0.0) > 0.0:
                return False
            if (summary_value(snapshot, component, "snapshot_failures") or 0.0) > 0.0:
                return False
            return lag is not None and lag <= max_lag
        if reasons != {"WATERMARK_TOO_OLD", "MISSING_FEATURES_RED"}:
            return False
        if (summary_value(snapshot, component, "snapshot_failures") or 0.0) > 0.0:
            return False
        if (summary_value(snapshot, "df", "missing_context_total") or 0.0) > 0.0:
            return False
        if (summary_value(snapshot, "df", "hard_fail_closed_total") or 0.0) > 0.0:
            return False
        if summary_text(snapshot, "dl", "decision_mode").upper() not in {"NORMAL", "STEP_UP_ONLY"}:
            return False
        return lag is not None and lag <= max_lag
    if reasons != {"WATERMARK_TOO_OLD"}:
        return False
    return (summary_value(snapshot, component, "apply_failure_count") or 0.0) == 0.0 and (
        summary_value(snapshot, component, "backpressure_hits") or 0.0
    ) == 0.0


def latest_snapshot(snapshots: list[dict[str, Any]], label: str) -> dict[str, Any]:
    target = str(label).strip().lower()
    for row in reversed(snapshots):
        if str(row.get("snapshot_label", "")).strip().lower() == target:
            return row
    return snapshots[-1]


def select_snapshots(root: Path, *, state_id: str, platform_run_id: str) -> list[dict[str, Any]]:
    snapshots = sorted(
        [
            load_json(path)
            for path in root.glob(f"g3a_{str(state_id).strip().lower()}_component_snapshot_*.json")
            if str(load_json(path).get("platform_run_id") or "").strip() == platform_run_id
        ],
        key=lambda row: str(row.get("generated_at_utc", "")),
    )
    labels = {str(row.get("snapshot_label", "")).strip().lower() for row in snapshots}
    if not snapshots or "pre" not in labels or "post" not in labels:
        raise RuntimeError("PHASE4.B22_COMPONENT_SNAPSHOTS_INCOMPLETE")
    return snapshots


def main() -> None:
    ap = argparse.ArgumentParser(description="Build Phase 4 coupled-network validation rollup.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--state-id", default="P4")
    ap.add_argument("--artifact-prefix", default="phase4_coupled")
    ap.add_argument("--bootstrap-summary-name", default="phase4_control_plane_bootstrap.json")
    ap.add_argument("--max-lag-p99-seconds", type=float, default=5.0)
    ap.add_argument("--max-checkpoint-p99-seconds", type=float, default=120.0)
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    prefix = str(args.artifact_prefix).strip()
    envelope = load_optional_json(root / f"{prefix}_envelope_summary.json")
    envelope_windows = load_optional_json(root / f"{prefix}_envelope_windows.json")
    bootstrap = load_optional_json(root / str(args.bootstrap_summary_name).strip()) or {"overall_pass": False}
    charter = load_optional_json(root / "g4a_run_charter.active.json") or {}
    timing_probe = load_optional_json(root / f"{prefix}_timing_probe.json")

    platform_run_id = str((((envelope or {}).get("identity") or {}).get("platform_run_id") or "")).strip()
    if not platform_run_id:
        platform_run_id = str(bootstrap.get("platform_run_id") or "").strip()

    blockers: list[str] = []
    notes: list[str] = [
        "Phase 4 rollup is coupled-network scoped: it scores the enlarged Control + Ingress + RTDL + Case + Label network only.",
        "Learning and ops/governance remain later coupled proofs and are intentionally not closure prerequisites here.",
        "Direct coupled timing must be evidenced honestly; if it cannot yet be derived from the exported run surfaces, it remains an explicit blocker.",
    ]

    if envelope is None or envelope_windows is None:
        blockers.append("PHASE4.B21_ENVELOPE_NOT_EXECUTED")
    if not bool(bootstrap.get("overall_pass")):
        blockers.append("PHASE4.B20_CONTROL_BOOTSTRAP_FAIL")
    if envelope is not None and str(envelope.get("verdict") or "").strip().upper() != "PHASE4B_READY":
        blockers.append("PHASE4.B21_ENVELOPE_RED")

    selected: list[dict[str, Any]] = []
    pre: dict[str, Any] = {}
    post: dict[str, Any] = {}
    if not any(item.startswith("PHASE4.B21") for item in blockers):
        try:
            selected = select_snapshots(root, state_id=args.state_id, platform_run_id=platform_run_id)
            pre = latest_snapshot(selected, "pre")
            post = latest_snapshot(selected, "post")
        except RuntimeError as exc:
            blockers.append(str(exc))

    windows = dict((envelope or {}).get("windows") or {})
    steady = dict(windows.get("steady") or {})
    burst = dict(windows.get("burst") or {})
    recovery = dict(windows.get("recovery") or {})
    recovery_analysis = dict((envelope or {}).get("recovery_analysis") or {})

    metrics: dict[str, float | None] = {}
    integrity: dict[str, float | None] = {}
    coupled_path = {
        "control_bootstrap": "PASS" if bool(bootstrap.get("overall_pass")) else "HOLD_REMEDIATE",
        "ingress_envelope": "PASS" if envelope and str(envelope.get("verdict") or "").strip().upper() == "PHASE4B_READY" else "HOLD_REMEDIATE",
        "rtdl_base": "HOLD_REMEDIATE",
        "case_trigger": "HOLD_REMEDIATE",
        "case_management": "HOLD_REMEDIATE",
        "label_store": "HOLD_REMEDIATE",
        "timing_visibility": "HOLD_REMEDIATE",
    }
    timing_metrics: dict[str, Any] = {}

    if pre and post:
        for component in ("csfb", "ieg", "ofp", "df", "al", "dla", "case_trigger", "case_mgmt", "label_store"):
            if is_missing(post, component):
                blockers.append(f"PHASE4.B22_COMPONENT_MISSING:{component}")
                continue
            state = health_state(post, component).upper()
            if state in {"RED", "FAILED", "UNHEALTHY"} and not replay_advisory_only(
                post, component, float(args.max_checkpoint_p99_seconds), float(args.max_lag_p99_seconds)
            ):
                blockers.append(f"PHASE4.B22_COMPONENT_HEALTH_RED:{component}:{state}")

        metrics = {
            "df_decisions_total_delta": delta(pre, post, "df", "decisions_total"),
            "al_intake_total_delta": delta(pre, post, "al", "intake_total"),
            "dla_append_success_total_delta": delta(pre, post, "dla", "append_success_total"),
            "case_trigger_triggers_seen_delta": delta(pre, post, "case_trigger", "triggers_seen"),
            "case_trigger_published_delta": delta(pre, post, "case_trigger", "published"),
            "case_mgmt_case_triggers_delta": delta(pre, post, "case_mgmt", "case_triggers"),
            "case_mgmt_cases_created_delta": delta(pre, post, "case_mgmt", "cases_created"),
            "case_mgmt_timeline_events_appended_delta": delta(pre, post, "case_mgmt", "timeline_events_appended"),
            "case_mgmt_labels_accepted_delta": delta(pre, post, "case_mgmt", "labels_accepted"),
            "label_store_accepted_delta": delta(pre, post, "label_store", "accepted"),
            "label_store_timeline_rows_delta": delta(pre, post, "label_store", "timeline_rows"),
        }
        integrity = {
            "df_hard_fail_closed_delta": delta(pre, post, "df", "hard_fail_closed_total"),
            "df_publish_quarantine_delta": delta(pre, post, "df", "publish_quarantine_total"),
            "al_publish_quarantine_delta": delta(pre, post, "al", "publish_quarantine_total"),
            "al_publish_ambiguous_delta": delta(pre, post, "al", "publish_ambiguous_total"),
            "dla_append_failure_delta": delta(pre, post, "dla", "append_failure_total"),
            "dla_replay_divergence_delta": delta(pre, post, "dla", "replay_divergence_total"),
            "case_trigger_duplicates_delta": delta(pre, post, "case_trigger", "duplicates"),
            "case_trigger_quarantine_delta": delta(pre, post, "case_trigger", "quarantine"),
            "case_trigger_publish_ambiguous_delta": delta(pre, post, "case_trigger", "publish_ambiguous_total"),
            "case_trigger_payload_mismatch_delta": delta(pre, post, "case_trigger", "payload_mismatch_total"),
            "case_mgmt_payload_mismatches_delta": delta(pre, post, "case_mgmt", "payload_mismatches"),
            "case_mgmt_anomalies_total_delta": delta(pre, post, "case_mgmt", "anomalies_total"),
            "case_mgmt_labels_rejected_delta": delta(pre, post, "case_mgmt", "labels_rejected"),
            "case_mgmt_evidence_pending_delta": delta(pre, post, "case_mgmt", "evidence_pending"),
            "case_mgmt_evidence_unavailable_delta": delta(pre, post, "case_mgmt", "evidence_unavailable"),
            "label_store_pending_delta": delta(pre, post, "label_store", "pending"),
            "label_store_rejected_delta": delta(pre, post, "label_store", "rejected"),
            "label_store_duplicate_delta": delta(pre, post, "label_store", "duplicate"),
            "label_store_payload_hash_mismatch_delta": delta(pre, post, "label_store", "payload_hash_mismatch"),
            "label_store_dedupe_tuple_collision_delta": delta(pre, post, "label_store", "dedupe_tuple_collision"),
            "label_store_missing_evidence_refs_delta": delta(pre, post, "label_store", "missing_evidence_refs"),
            "label_store_anomalies_total_delta": delta(pre, post, "label_store", "anomalies_total"),
        }

        if (metrics.get("al_intake_total_delta") or 0.0) <= 0.0:
            blockers.append("PHASE4.B23_STARVATION_AL_DARK")
        if (metrics.get("df_decisions_total_delta") or 0.0) <= 0.0:
            blockers.append("PHASE4.B23_STARVATION_DF_DARK")
        if (metrics.get("df_decisions_total_delta") or 0.0) > 0.0 and (metrics.get("case_trigger_triggers_seen_delta") or 0.0) <= 0.0:
            blockers.append("PHASE4.B23_STARVATION_CASE_TRIGGER_DARK")
        if (metrics.get("case_trigger_triggers_seen_delta") or 0.0) > 0.0 and (metrics.get("case_mgmt_cases_created_delta") or 0.0) <= 0.0:
            blockers.append("PHASE4.B23_STARVATION_CASE_MGMT_DARK")
        if (metrics.get("case_mgmt_cases_created_delta") or 0.0) > 0.0 and (metrics.get("label_store_accepted_delta") or 0.0) <= 0.0:
            blockers.append("PHASE4.B23_STARVATION_LABEL_STORE_DARK")
        if (metrics.get("case_mgmt_cases_created_delta") or 0.0) > (metrics.get("case_mgmt_case_triggers_delta") or 0.0):
            blockers.append("PHASE4.B24_CASE_IDEMPOTENCY_UNPROVEN:cases_created_exceeds_triggers")
        if (metrics.get("label_store_accepted_delta") or 0.0) < (metrics.get("case_mgmt_labels_accepted_delta") or 0.0):
            blockers.append("PHASE4.B24_LABEL_COMMIT_UNDERCOUNT:label_store_below_case_mgmt")

        for key, value in integrity.items():
            if value is None:
                blockers.append(f"PHASE4.B24_INTEGRITY_SIGNAL_UNREADABLE:{key}")
                continue
            if key in {"case_mgmt_evidence_pending_delta", "label_store_pending_delta"}:
                if value > 0.0:
                    blockers.append(f"PHASE4.B24_INTEGRITY_BREACH:{key}:{value:.0f}")
                continue
            if value > 0.0:
                blockers.append(f"PHASE4.B24_INTEGRITY_BREACH:{key}:{value:.0f}")

        if not any(item.startswith("PHASE4.B22") or item.startswith("PHASE4.B23") for item in blockers if ":case_trigger" not in item):
            coupled_path["rtdl_base"] = "PASS"
        if (metrics.get("case_trigger_triggers_seen_delta") or 0.0) > 0.0 and (
            (integrity.get("case_trigger_duplicates_delta") or 0.0) == 0.0
            and (integrity.get("case_trigger_quarantine_delta") or 0.0) == 0.0
            and (integrity.get("case_trigger_publish_ambiguous_delta") or 0.0) == 0.0
            and (integrity.get("case_trigger_payload_mismatch_delta") or 0.0) == 0.0
        ):
            coupled_path["case_trigger"] = "PASS"
        if (metrics.get("case_mgmt_cases_created_delta") or 0.0) > 0.0 and (
            (integrity.get("case_mgmt_payload_mismatches_delta") or 0.0) == 0.0
            and (integrity.get("case_mgmt_anomalies_total_delta") or 0.0) == 0.0
            and (integrity.get("case_mgmt_labels_rejected_delta") or 0.0) == 0.0
            and (integrity.get("case_mgmt_evidence_pending_delta") or 0.0) == 0.0
            and (integrity.get("case_mgmt_evidence_unavailable_delta") or 0.0) == 0.0
        ):
            coupled_path["case_management"] = "PASS"
        if (metrics.get("label_store_accepted_delta") or 0.0) > 0.0 and (
            (integrity.get("label_store_pending_delta") or 0.0) == 0.0
            and (integrity.get("label_store_rejected_delta") or 0.0) == 0.0
            and (integrity.get("label_store_duplicate_delta") or 0.0) == 0.0
            and (integrity.get("label_store_payload_hash_mismatch_delta") or 0.0) == 0.0
            and (integrity.get("label_store_dedupe_tuple_collision_delta") or 0.0) == 0.0
            and (integrity.get("label_store_missing_evidence_refs_delta") or 0.0) == 0.0
            and (integrity.get("label_store_anomalies_total_delta") or 0.0) == 0.0
        ):
            coupled_path["label_store"] = "PASS"

    if timing_probe is None:
        blockers.append("PHASE4.B24_TIMING_PROBE_MISSING")
    else:
        timing_metrics = {
            "decision_to_case": dict(timing_probe.get("decision_to_case") or {}),
            "case_to_label": dict(timing_probe.get("case_to_label") or {}),
            "thresholds": dict(timing_probe.get("thresholds") or {}),
        }
        timing_blockers = [str(item).strip() for item in (timing_probe.get("blocker_ids") or []) if str(item).strip()]
        blockers.extend(timing_blockers)
        if bool(timing_probe.get("overall_pass")):
            coupled_path["timing_visibility"] = "PASS"

    overall_pass = len(set(blockers)) == 0
    assessment = (
        "Phase 4 bounded coupled-network validation is green on the enlarged promoted network."
        if overall_pass
        else "Phase 4 bounded coupled-network validation is not green yet; only the failed coupled boundary should be remediated."
    )

    scorecard = {
        "phase": "PHASE4",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "platform_run_id": platform_run_id,
        "window_label": prefix,
        "control_bootstrap": {
            "overall_pass": bool(bootstrap.get("overall_pass")),
            "scenario_run_id": bootstrap.get("scenario_run_id"),
            "facts_view_ref": ((bootstrap.get("sr") or {}).get("facts_view_ref")),
            "status_ref": ((bootstrap.get("sr") or {}).get("status_ref")),
        },
        "envelope": {
            "verdict": (envelope or {}).get("verdict"),
            "steady": steady,
            "burst": burst,
            "recovery": recovery,
            "recovery_analysis": recovery_analysis,
        },
        "component_deltas": metrics,
        "integrity": integrity,
        "timing": timing_metrics,
        "coupled_path": coupled_path,
        "charter": {
            "mission_binding": dict(charter.get("mission_binding") or {}),
            "slice": dict(charter.get("phase4_slice") or {}),
        },
        "assessment": assessment,
        "overall_pass": overall_pass,
        "blocker_ids": sorted(set(blockers)),
        "notes": notes,
    }
    receipt = {
        "phase": "PHASE4",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "platform_run_id": platform_run_id,
        "verdict": "PHASE4_READY" if overall_pass else "HOLD_REMEDIATE",
        "next_phase": "PHASE5" if overall_pass else "PHASE4",
        "open_blockers": len(sorted(set(blockers))),
        "blocker_ids": sorted(set(blockers)),
    }
    dump_json(root / f"{prefix}_scorecard.json", scorecard)
    dump_json(root / f"{prefix}_readiness_receipt.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
