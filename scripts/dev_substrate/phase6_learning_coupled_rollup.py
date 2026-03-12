#!/usr/bin/env python3
"""Score Phase 6 coupled runtime-learning adoption, rollback, and restore readiness."""

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
        raise RuntimeError("PHASE6.B22_COMPONENT_SNAPSHOTS_INCOMPLETE")
    return snapshots


def extract_explicit_bundle(df_probe: dict[str, Any], scope_key: str) -> str:
    explicit = dict(df_probe.get("explicit_fallback_by_scope") or {})
    bundle_ref = dict(explicit.get(scope_key) or {})
    bundle_id = str(bundle_ref.get("bundle_id") or "").strip()
    bundle_version = str(bundle_ref.get("bundle_version") or "").strip()
    if not bundle_id or not bundle_version:
        return ""
    return f"bundle://{bundle_id}@{bundle_version}"


def warm_gate_transition_advisory(payload: dict[str, Any]) -> bool:
    blockers = {str(item).strip() for item in (payload.get("blocker_ids") or []) if str(item).strip()}
    return bool(blockers) and blockers.issubset({"PR3.S4.WARM.B12K_OFP_NOT_OPERATIONALLY_READY"})


def main() -> None:
    ap = argparse.ArgumentParser(description="Build Phase 6 coupled-learning readiness rollup.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--phase5-execution-id", required=True)
    ap.add_argument("--state-id", default="P6")
    ap.add_argument("--artifact-prefix", default="phase6_coupled")
    ap.add_argument("--max-lag-p99-seconds", type=float, default=5.0)
    ap.add_argument("--max-checkpoint-p99-seconds", type=float, default=120.0)
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    phase5_root = Path(args.run_control_root) / args.phase5_execution_id
    prefix = str(args.artifact_prefix).strip()

    phase5_receipt = load_optional_json(phase5_root / "phase5_learning_managed_receipt.json")
    if phase5_receipt is None:
        phase5_receipt = load_optional_json(phase5_root / "phase5_learning_managed_train_eval_receipt.json")
    if phase5_receipt is None:
        phase5_receipt = load_optional_json(phase5_root / "phase5_learning_managed_receipt.json")
    if phase5_receipt is None:
        phase5_receipt = {
            "verdict": "HOLD_REMEDIATE",
            "blocker_ids": ["PHASE6.A00_PHASE5_RECEIPT_MISSING"],
        }
    phase5_summary = load_json(phase5_root / "phase5_learning_managed_summary.json")

    envelope = load_optional_json(root / f"{prefix}_envelope_summary.json")
    bootstrap = load_optional_json(root / "phase6_control_plane_bootstrap.json") or {"overall_pass": False}
    timing_probe = load_optional_json(root / f"{prefix}_timing_probe.json")
    candidate_probe = load_optional_json(root / "phase6_candidate_bundle_probe.json")
    rollback_probe = load_optional_json(root / "phase6_rollback_bundle_probe.json")
    restore_probe = load_optional_json(root / "phase6_restore_bundle_probe.json")
    candidate_warm = load_optional_json(root / "phase6_candidate_runtime_warm_gate.json")
    rollback_warm = load_optional_json(root / "phase6_rollback_runtime_warm_gate.json")
    restore_warm = load_optional_json(root / "phase6_restore_runtime_warm_gate.json")
    candidate_manifest = load_optional_json(root / "phase6_candidate_runtime_materialization_manifest.json")
    rollback_manifest = load_optional_json(root / "phase6_rollback_runtime_materialization_manifest.json")
    restore_manifest = load_optional_json(root / "phase6_restore_runtime_materialization_manifest.json")
    charter = load_optional_json(root / "g6a_run_charter.active.json") or {}

    expected_bundle = f"bundle://{phase5_summary['governance']['bundle_id']}@{phase5_summary['governance']['bundle_version']}"
    previous_bundle = dict(phase5_summary.get("governance", {}).get("previous_active_bundle") or {})
    previous_bundle_uri = ""
    if previous_bundle.get("bundle_id") and previous_bundle.get("bundle_version"):
        previous_bundle_uri = f"bundle://{previous_bundle['bundle_id']}@{previous_bundle['bundle_version']}"

    platform_run_id = str((((envelope or {}).get("identity") or {}).get("platform_run_id") or "")).strip()
    if not platform_run_id:
        platform_run_id = str((candidate_probe or {}).get("platform_run_id") or "").strip()

    blockers: list[str] = []
    notes: list[str] = [
        "Phase 6 only closes if runtime decisions on the enlarged network can be attributed to the promoted learning bundle and that active truth can be rolled back and restored without ambiguity.",
        "The learning corridor remains anchored to the accepted Phase 5 evidence chain; the new work here is runtime adoption, bounded regression safety, and deterministic rollback/restore.",
    ]

    if str(phase5_receipt.get("verdict") or "").strip().upper() != "PHASE5_READY":
        blockers.append("PHASE6.A01_SOURCE_PHASE5_NOT_GREEN")

    if envelope is None or str(envelope.get("verdict") or "").strip().upper() != "PHASE6B_READY":
        blockers.append("PHASE6.B20_ENVELOPE_RED")
    if not bool(bootstrap.get("overall_pass")):
        blockers.append("PHASE6.B21_CONTROL_BOOTSTRAP_FAIL")

    selected: list[dict[str, Any]] = []
    pre: dict[str, Any] = {}
    post: dict[str, Any] = {}
    if platform_run_id:
        try:
            selected = select_snapshots(root, state_id=args.state_id, platform_run_id=platform_run_id)
            pre = latest_snapshot(selected, "pre")
            post = latest_snapshot(selected, "post")
        except RuntimeError as exc:
            blockers.append(str(exc))
    else:
        blockers.append("PHASE6.B22_PLATFORM_RUN_ID_UNRESOLVED")

    metrics: dict[str, float | None] = {}
    integrity: dict[str, float | None] = {}
    if pre and post:
        for component in ("csfb", "ieg", "ofp", "df", "al", "dla", "case_trigger", "case_mgmt", "label_store"):
            if is_missing(post, component):
                blockers.append(f"PHASE6.B23_COMPONENT_MISSING:{component}")
                continue
            state = health_state(post, component).upper()
            if state in {"RED", "FAILED", "UNHEALTHY"} and not replay_advisory_only(
                post, component, float(args.max_checkpoint_p99_seconds), float(args.max_lag_p99_seconds)
            ):
                blockers.append(f"PHASE6.B24_COMPONENT_HEALTH_RED:{component}:{state}")

        metrics = {
            "df_decisions_total_delta": delta(pre, post, "df", "decisions_total"),
            "al_intake_total_delta": delta(pre, post, "al", "intake_total"),
            "dla_append_success_total_delta": delta(pre, post, "dla", "append_success_total"),
            "case_trigger_triggers_seen_delta": delta(pre, post, "case_trigger", "triggers_seen"),
            "case_mgmt_cases_created_delta": delta(pre, post, "case_mgmt", "cases_created"),
            "label_store_accepted_delta": delta(pre, post, "label_store", "accepted"),
        }
        integrity = {
            "df_hard_fail_closed_delta": delta(pre, post, "df", "hard_fail_closed_total"),
            "df_publish_quarantine_delta": delta(pre, post, "df", "publish_quarantine_total"),
            "al_publish_quarantine_delta": delta(pre, post, "al", "publish_quarantine_total"),
            "dla_append_failure_delta": delta(pre, post, "dla", "append_failure_total"),
            "dla_replay_divergence_delta": delta(pre, post, "dla", "replay_divergence_total"),
            "case_trigger_quarantine_delta": delta(pre, post, "case_trigger", "quarantine"),
            "case_mgmt_anomalies_total_delta": delta(pre, post, "case_mgmt", "anomalies_total"),
            "label_store_pending_delta": delta(pre, post, "label_store", "pending"),
            "label_store_rejected_delta": delta(pre, post, "label_store", "rejected"),
        }
        if (metrics.get("df_decisions_total_delta") or 0.0) <= 0.0:
            blockers.append("PHASE6.B25_RUNTIME_DF_DARK")
        if (metrics.get("al_intake_total_delta") or 0.0) <= 0.0:
            blockers.append("PHASE6.B26_RUNTIME_AL_DARK")
        if (metrics.get("case_trigger_triggers_seen_delta") or 0.0) <= 0.0:
            blockers.append("PHASE6.B27_RUNTIME_CASE_TRIGGER_DARK")
        if (metrics.get("case_mgmt_cases_created_delta") or 0.0) <= 0.0:
            blockers.append("PHASE6.B28_RUNTIME_CASE_MGMT_DARK")
        if (metrics.get("label_store_accepted_delta") or 0.0) <= 0.0:
            blockers.append("PHASE6.B29_RUNTIME_LABEL_STORE_DARK")
        for key, value in integrity.items():
            if value is None:
                blockers.append(f"PHASE6.B30_INTEGRITY_SIGNAL_UNREADABLE:{key}")
            elif value > 0.0:
                blockers.append(f"PHASE6.B30_INTEGRITY_BREACH:{key}:{value:.0f}")

    if timing_probe is None or not bool(timing_probe.get("overall_pass")):
        blockers.append("PHASE6.B31_TIMING_NOT_GREEN")

    for label, warm, manifest, expected_uri, expected_policy in (
        ("candidate", candidate_warm, candidate_manifest, expected_bundle, str((candidate_probe or {}).get("expected_policy_ref") or "")),
        ("rollback", rollback_warm, rollback_manifest, previous_bundle_uri, str((rollback_probe or {}).get("expected_policy_ref") or "")),
        ("restore", restore_warm, restore_manifest, expected_bundle, str((restore_probe or {}).get("expected_policy_ref") or "")),
    ):
        if warm is None:
            blockers.append(f"PHASE6.B32_{label.upper()}_WARM_GATE_RED")
            continue
        if not bool(warm.get("overall_pass")) and not (label in {"rollback", "restore"} and warm_gate_transition_advisory(warm)):
            blockers.append(f"PHASE6.B32_{label.upper()}_WARM_GATE_RED")
            continue
        if manifest is None:
            blockers.append(f"PHASE6.B33_{label.upper()}_MATERIALIZATION_MISSING")
            continue
        df_probe = dict(warm.get("df_probe") or {})
        fraud_bundle = extract_explicit_bundle(df_probe, "dev_full|fraud|primary|")
        baseline_bundle = extract_explicit_bundle(df_probe, "dev_full|baseline|primary|")
        if expected_uri and (fraud_bundle != expected_uri or baseline_bundle != expected_uri):
            blockers.append(f"PHASE6.B34_{label.upper()}_DF_POLICY_DRIFT")
        if expected_policy and str(df_probe.get("policy_id") or "").strip():
            actual_policy = f"policy://{str(df_probe.get('policy_id') or '').strip()}@{str(df_probe.get('policy_revision') or '').strip()}"
            if actual_policy != expected_policy:
                blockers.append(f"PHASE6.B35_{label.upper()}_DF_POLICY_REV_DRIFT:{actual_policy}")

    for label, probe, expected_uri in (
        ("candidate", candidate_probe, expected_bundle),
        ("rollback", rollback_probe, previous_bundle_uri),
        ("restore", restore_probe, expected_bundle),
    ):
        if probe is None or not bool(probe.get("overall_pass")):
            blockers.append(f"PHASE6.B36_{label.upper()}_BUNDLE_PROBE_RED")
            continue
        governance = dict(probe.get("governance") or {})
        bundle_refs = [str(item).strip() for item in (governance.get("bundle_refs") or []) if str(item).strip()]
        if expected_uri and bundle_refs != [expected_uri]:
            blockers.append(f"PHASE6.B37_{label.upper()}_BUNDLE_ATTRIBUTION_DRIFT:{'|'.join(bundle_refs)}")

    overall_pass = len(sorted(set(blockers))) == 0
    scorecard = {
        "phase": "PHASE6",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "platform_run_id": platform_run_id,
        "source_phase5_execution_id": args.phase5_execution_id,
        "expected_bundle_ref": expected_bundle,
        "previous_bundle_ref": previous_bundle_uri,
        "charter": dict(charter.get("phase6_slice") or {}),
        "envelope": {
            "verdict": (envelope or {}).get("verdict"),
            "windows": dict((envelope or {}).get("windows") or {}),
            "recovery_analysis": dict((envelope or {}).get("recovery_analysis") or {}),
        },
        "component_deltas": metrics,
        "integrity": integrity,
        "timing": dict(timing_probe or {}),
        "candidate": {
            "materialization": candidate_manifest,
            "warm_gate": candidate_warm,
            "bundle_probe": candidate_probe,
        },
        "rollback": {
            "materialization": rollback_manifest,
            "warm_gate": rollback_warm,
            "bundle_probe": rollback_probe,
        },
        "restore": {
            "materialization": restore_manifest,
            "warm_gate": restore_warm,
            "bundle_probe": restore_probe,
        },
        "learning_authority": {
            "phase5_receipt": phase5_receipt,
            "phase5_governance": dict(phase5_summary.get("governance") or {}),
            "phase5_metrics": dict(phase5_summary.get("metrics") or {}),
            "phase5_refs": dict(phase5_summary.get("refs") or {}),
        },
        "overall_pass": overall_pass,
        "blocker_ids": sorted(set(blockers)),
        "notes": notes,
    }
    receipt = {
        "phase": "PHASE6",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "platform_run_id": platform_run_id,
        "verdict": "PHASE6_READY" if overall_pass else "HOLD_REMEDIATE",
        "next_phase": "PHASE7" if overall_pass else "PHASE6",
        "open_blockers": len(sorted(set(blockers))),
        "blocker_ids": sorted(set(blockers)),
    }
    dump_json(root / f"{prefix}_scorecard.json", scorecard)
    dump_json(root / "phase6_learning_coupled_summary.json", scorecard)
    dump_json(root / "phase6_learning_coupled_receipt.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
