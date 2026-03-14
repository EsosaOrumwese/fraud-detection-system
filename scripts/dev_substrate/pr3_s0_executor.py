#!/usr/bin/env python3
"""Deterministic PR3-S0 executor for road_to_prod (dev_full)."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stamp_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    return payload if isinstance(payload, dict) else {}


def dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def parse_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def is_text(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def safe_json(path: Path) -> Tuple[bool, Dict[str, Any], str]:
    if not path.exists():
        return False, {}, f"missing:{path}"
    try:
        return True, load_json(path), ""
    except Exception as exc:  # pragma: no cover
        return False, {}, f"unreadable:{path}:{exc}"


def resolve_pr2_id(root: Path, explicit: str) -> str:
    if explicit.strip():
        return explicit.strip()
    latest = load_json(root / "pr2_latest.json")
    eid = str(latest.get("execution_id", "")).strip()
    if not eid:
        raise RuntimeError("Unable to resolve PR2 execution id from pr2_latest.json")
    return eid


def main() -> None:
    ap = argparse.ArgumentParser(description="Execute PR3-S0 from strict PR2 closure.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--upstream-pr2-execution-id", default="")
    ap.add_argument("--pr3-execution-id", default="")
    ap.add_argument(
        "--m13-summary-ref",
        default="runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m13_stress_s5_20260305T111321Z/stress/m13_execution_summary.json",
    )
    ap.add_argument(
        "--m14e-cutover-summary-ref",
        default="runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m14e_msf_cutover_20260305T113525Z/stress/m14e_msf_cutover_execution_summary.json",
    )
    ap.add_argument(
        "--m14e-projection-summary-ref",
        default="runs/dev_substrate/dev_full/m14/m14e_rtdl_projection_20260305T114720Z/m14e_execution_summary.json",
    )
    ap.add_argument(
        "--m14e-projection-snapshot-ref",
        default="runs/dev_substrate/dev_full/m14/m14e_rtdl_projection_20260305T114720Z/m14e_rtdl_projection_snapshot.json",
    )
    ap.add_argument(
        "--m14f-archive-summary-ref",
        default="runs/dev_substrate/dev_full/m14/m14f_archive_connector_20260302T051741Z/m14f_execution_summary.json",
    )
    ap.add_argument(
        "--m14f-archive-snapshot-ref",
        default="runs/dev_substrate/dev_full/m14/m14f_archive_connector_20260302T051741Z/m14f_archive_connector_snapshot.json",
    )
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    t0 = time.perf_counter()
    ts = now_utc()
    root = Path(args.run_control_root)
    if not root.exists():
        raise RuntimeError(f"Run-control root missing: {root}")

    pr2_id = resolve_pr2_id(root, args.upstream_pr2_execution_id)
    pr2_root = root / pr2_id
    pr2_s3 = load_json(pr2_root / "pr2_s3_execution_receipt.json")
    pr2_summary = load_json(pr2_root / "pr2_execution_summary.json")
    pr2_runtime = load_yaml(pr2_root / "pr2_runtime_numeric_contract.rc2s.active.yaml")
    pr2_opsgov = load_yaml(pr2_root / "pr2_opsgov_numeric_contract.rc2s.active.yaml")
    pr2_matrix = load_json(pr2_root / "pr2_activation_validation_matrix.json")
    pr2_deferred = load_json(pr2_root / "pr2_deferred_scope_register.json")

    pr3_id = args.pr3_execution_id.strip() or f"pr3_{stamp_utc()}"
    pr3_root = root / pr3_id
    pr3_root.mkdir(parents=True, exist_ok=True)

    upstream_checks = {
        "receipt_ready": (
            str(pr2_s3.get("verdict", "")) == "PR2_S3_READY"
            and int(pr2_s3.get("open_blockers", 1)) == 0
            and str(pr2_s3.get("next_gate", "")) == "PR3_READY"
        ),
        "summary_ready": (
            str(pr2_summary.get("verdict", "")) == "PR3_READY"
            and int(pr2_summary.get("open_blockers", 1)) == 0
            and str(pr2_summary.get("next_gate", "")) == "PR3_READY"
        ),
        "runtime_contract_active": str(pr2_runtime.get("status", "")).upper() == "ACTIVE",
        "opsgov_contract_active": str(pr2_opsgov.get("status", "")).upper() == "ACTIVE",
        "activation_matrix_pass": bool(pr2_matrix.get("overall_pass", False)),
    }
    upstream_ready = all(upstream_checks.values())

    mb = pr2_runtime.get("mission_binding", {})
    inj = pr2_runtime.get("injection_path", {})
    lc = pr2_runtime.get("load_campaign", {})
    th = pr2_runtime.get("thresholds", {})
    sm = pr2_runtime.get("sample_minima", {})
    ms = pr2_runtime.get("measurement_surfaces", {})
    rules = pr2_opsgov.get("rules", {})

    steady_rate = parse_float(lc.get("steady", {}).get("rate_eps"), 0.0)
    steady_min = parse_int(lc.get("steady", {}).get("duration_min"), 0)
    burst_rate = parse_float(lc.get("burst", {}).get("rate_eps"), 0.0)
    burst_min = parse_int(lc.get("burst", {}).get("duration_min"), 0)
    soak_rate = parse_float(lc.get("soak", {}).get("rate_eps"), 0.0)
    soak_min = parse_int(lc.get("soak", {}).get("duration_min"), 0)
    recovery_bound = parse_int(lc.get("recovery", {}).get("bound_seconds"), 0)
    budget = parse_float(th.get("cost", {}).get("budget_envelope_usd"), 0.0)
    steady_events = int(steady_rate * steady_min * 60)
    burst_events = int(burst_rate * burst_min * 60)
    soak_events = int(soak_rate * soak_min * 60)

    charter = {
        "phase": "PR3",
        "state": "S0",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr3_id,
        "mission_id": "dev_full_rc2s_road_to_prod_g3a",
        "upstream": {
            "pr2_execution_id": pr2_id,
            "receipt_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr2_id}/pr2_s3_execution_receipt.json",
            "summary_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr2_id}/pr2_execution_summary.json",
        },
        "injection_path": {
            "mode": inj.get("mode"),
            "scope_notes": inj.get("scope_notes", ""),
            "policy": {
                "via_IG_is_production_claim_path": True,
                "via_MSK_requires_explicit_scope_limitations": True,
            },
        },
        "mission_binding": {
            "window_start_ts_utc": mb.get("window_start_ts_utc"),
            "window_end_ts_utc": mb.get("window_end_ts_utc"),
            "as_of_time_utc": mb.get("as_of_time_utc"),
            "label_maturity_lag": mb.get("label_maturity_lag"),
        },
        "envelope": {
            "id": pr2_runtime.get("envelope_id", "RC2-S"),
            "runtime_contract_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr2_id}/pr2_runtime_numeric_contract.rc2s.active.yaml",
            "opsgov_contract_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr2_id}/pr2_opsgov_numeric_contract.rc2s.active.yaml",
            "activation_matrix_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr2_id}/pr2_activation_validation_matrix.json",
        },
        "load_campaign": {
            "steady": {"rate_eps": steady_rate, "duration_min": steady_min, "min_processed_events": steady_events},
            "burst": {"rate_eps": burst_rate, "duration_min": burst_min, "min_processed_events": burst_events},
            "recovery": {"bound_seconds": recovery_bound},
            "soak": {"rate_eps": soak_rate, "duration_min": soak_min, "min_processed_events": soak_events},
            "minima_source": "derived_from_pr2_active_runtime_contract",
        },
        "runtime_thresholds": th,
        "sample_minima": {"from_pr2_contract": sm},
        "cohorts_required": ["duplicates", "out_of_order", "hot_key", "payload_extremes", "mixed_event_types"],
        "runtime_drills_required": [
            "replay_integrity",
            "lag_recovery",
            "schema_evolution",
            "dependency_degrade",
            "cost_guardrail_idle_safe",
        ],
        "distribution_requirements": rules.get("distribution_required", ["p95", "p99"]),
        "missing_metric_policy": rules.get("missing_metric_policy", "FAIL_CLOSED"),
        "budget_envelope_usd": budget,
        "carry_forward_constraints": pr2_deferred.get("carry_forward_constraints", []),
    }

    surface_map = {
        "phase": "PR3",
        "state": "S0",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr3_id,
        "source_contract_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr2_id}/pr2_runtime_numeric_contract.rc2s.active.yaml",
        "required_metric_surfaces": [
            {"metric_id": "throughput_steady_eps", "surface": ms.get("throughput", {}).get("steady_surface"), "source": "PR2"},
            {"metric_id": "throughput_burst_eps", "surface": ms.get("throughput", {}).get("burst_surface"), "source": "PR2"},
            {"metric_id": "e2e_latency_ms", "surface": {"start": ms.get("latency", {}).get("e2e_start"), "end": ms.get("latency", {}).get("e2e_end")}, "source": "PR2"},
            {"metric_id": "error_timeout_rate", "surface": "DECISION_ERROR_TIMEOUT_RATE", "source": "PR3_POLICY_PIN"},
            {"metric_id": "consumer_lag", "surface": "RUNSCOPED_OFP_LAG_SECONDS", "source": "PR3_EKS_RUNTIME_PIN"},
            {"metric_id": "checkpoint_health", "surface": "RUNSCOPED_IEG_OFP_DLA_CHECKPOINT_AGE_SECONDS", "source": "PR3_EKS_RUNTIME_PIN"},
            {"metric_id": "runtime_backpressure", "surface": "RUNSCOPED_IEG_BACKPRESSURE_HITS", "source": "PR3_EKS_RUNTIME_PIN"},
            {"metric_id": "archive_sink_backlog", "surface": "RUNSCOPED_ARCHIVE_BACKLOG_EVENTS", "source": "PR3_EKS_RUNTIME_PIN"},
            {"metric_id": "duplicate_admission_and_dedupe", "surface": "IG_DUPLICATE_AND_IDEMPOTENCY_METRICS", "source": "PR3_POLICY_PIN"},
            {"metric_id": "quarantine_posture", "surface": "IG_QUARANTINE_REASON_DISTRIBUTION", "source": "PR3_POLICY_PIN"},
            {"metric_id": "runtime_trace_coverage", "surface": "CORRELATION_TRACE_COVERAGE", "source": "PR3_POLICY_PIN"},
            {"metric_id": "runtime_unit_cost", "surface": "RUNTIME_COST_PER_EVENTS", "source": "PR3_POLICY_PIN"},
        ],
    }

    m13_ok, m13, m13_err = safe_json(Path(args.m13_summary_ref))
    c_ok, cutover, c_err = safe_json(Path(args.m14e_cutover_summary_ref))
    p_ok, proj, p_err = safe_json(Path(args.m14e_projection_summary_ref))
    s_ok, snap, s_err = safe_json(Path(args.m14e_projection_snapshot_ref))
    a_ok, arch_sum, a_err = safe_json(Path(args.m14f_archive_summary_ref))
    b_ok, arch_snap, b_err = safe_json(Path(args.m14f_archive_snapshot_ref))
    runbook_ref = str(pr2_opsgov.get("runbooks", {}).get("index_ref", "")).strip()
    runbook_ok = bool(runbook_ref) and Path(runbook_ref).exists()
    sink = arch_snap.get("sink_parity", {}) if b_ok else {}
    missing_ids = sink.get("missing_event_ids", []) if isinstance(sink, dict) else []
    canonical = snap.get("msf_probe", {}).get("canonical_app_surface", {}) if s_ok else {}

    deps = [
        {
            "check_id": "DP01_M13_PLATFORM_BASELINE",
            "pass": m13_ok and bool(m13.get("overall_pass")) and str(m13.get("verdict", "")).startswith("ADVANCE_TO_M14"),
            "observed": m13.get("verdict") if m13_ok else m13_err,
            "reason": "platform baseline must be green before runtime certification",
            "evidence_ref": args.m13_summary_ref,
        },
        {
            "check_id": "DP02_M14E_CUTOVER_READY",
            "pass": c_ok and bool(cutover.get("overall_pass")) and str(cutover.get("runtime_path_active", "")) in {"MSF_MANAGED", "EKS_FLINK_OPERATOR"},
            "observed": cutover.get("runtime_path_active") if c_ok else c_err,
            "reason": "runtime path cutover must be green",
            "evidence_ref": args.m14e_cutover_summary_ref,
        },
        {
            "check_id": "DP03_M14E_PROJECTION_READY",
            "pass": p_ok and bool(proj.get("overall_pass")),
            "observed": proj.get("m14e_verdict") if p_ok else p_err,
            "reason": "RTDL projection lane must be green",
            "evidence_ref": args.m14e_projection_summary_ref,
        },
        {
            "check_id": "DP04_M14E_CANONICAL_APP_SURFACE",
            "pass": s_ok and bool(canonical.get("list_ok")) and bool(canonical.get("describe_ok")) and str(canonical.get("application_status", "")) in {"READY", "RUNNING"},
            "observed": {
                "list_ok": canonical.get("list_ok"),
                "describe_ok": canonical.get("describe_ok"),
                "application_status": canonical.get("application_status"),
                "error": s_err,
            },
            "reason": "canonical runtime app surface must be readable and ready",
            "evidence_ref": args.m14e_projection_snapshot_ref,
        },
        {
            "check_id": "DP05_M14F_ARCHIVE_PARITY",
            "pass": a_ok and bool(arch_sum.get("overall_pass")) and b_ok and isinstance(missing_ids, list) and len(missing_ids) == 0 and parse_int(sink.get("new_object_count"), 0) > 0,
            "observed": {"overall_pass": arch_sum.get("overall_pass") if a_ok else False, "new_object_count": sink.get("new_object_count"), "missing_event_ids": missing_ids, "errors": [a_err, b_err]},
            "reason": "archive connector parity must show no missing sink writes",
            "evidence_ref": args.m14f_archive_snapshot_ref,
        },
        {
            "check_id": "DP06_PR2_RUNBOOK_INDEX",
            "pass": runbook_ok,
            "observed": runbook_ref or "__missing__",
            "reason": "opsgov runbook index must be readable",
            "evidence_ref": runbook_ref or "__missing__",
        },
        {
            "check_id": "DP07_PR2_ALERT_OWNER_BINDINGS",
            "pass": isinstance(pr2_opsgov.get("alerts", {}).get("required_owners_bound"), dict)
            and len(pr2_opsgov.get("alerts", {}).get("required_owners_bound", {})) > 0
            and all(is_text(v) for v in pr2_opsgov.get("alerts", {}).get("required_owners_bound", {}).values()),
            "observed": pr2_opsgov.get("alerts", {}).get("required_owners_bound", {}),
            "reason": "required runtime alerts must remain owner-bound",
            "evidence_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr2_id}/pr2_opsgov_numeric_contract.rc2s.active.yaml",
        },
        {
            "check_id": "DP08_PR2_DISTRIBUTION_POLICY",
            "pass": isinstance(rules.get("distribution_required"), list)
            and "p95" in rules.get("distribution_required", [])
            and "p99" in rules.get("distribution_required", [])
            and str(rules.get("missing_metric_policy", "")).upper() == "FAIL_CLOSED",
            "observed": {"distribution_required": rules.get("distribution_required"), "missing_metric_policy": rules.get("missing_metric_policy")},
            "reason": "distribution and missing-metric policies must remain fail-closed",
            "evidence_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr2_id}/pr2_opsgov_numeric_contract.rc2s.active.yaml",
        },
    ]
    failed_dep = [d for d in deps if not d["pass"]]
    preflight_pass = len(failed_dep) == 0

    preflight = {
        "phase": "PR3",
        "state": "S0",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr3_id,
        "preflight_mode": "EVIDENCE_ONLY_NO_LOCAL_ORCHESTRATION",
        "dependency_checks": deps,
        "summary": {
            "total_checks": len(deps),
            "passed_checks": len(deps) - len(failed_dep),
            "failed_checks": len(failed_dep),
            "failed_check_ids": [d["check_id"] for d in failed_dep],
        },
    }

    archive_design = {
        "phase": "PR3",
        "state": "S0",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr3_id,
        "target_id": "TGT-09",
        "decision_id": "PR3.S0.D09_ARCHIVE_SINK_BACKPRESSURE_PIN",
        "status": "PINNED_FOR_PR3_VALIDATION" if preflight_pass else "HOLD_REMEDIATE",
        "design": {
            "sink_mode": "MANAGED_ARCHIVE_CONNECTOR_TO_S3",
            "runtime_path_dependency": cutover.get("runtime_path_active") if c_ok else "",
            "validation_boundaries": {"burst_window_boundary": "PR3-S2", "soak_window_boundary": "PR3-S4"},
        },
        "evidence_refs": {
            "m14f_archive_summary_ref": args.m14f_archive_summary_ref,
            "m14f_archive_snapshot_ref": args.m14f_archive_snapshot_ref,
            "m14e_projection_snapshot_ref": args.m14e_projection_snapshot_ref,
        },
        "current_observed_posture": {
            "archive_summary_overall_pass": arch_sum.get("overall_pass") if a_ok else False,
            "sink_parity_new_object_count": sink.get("new_object_count"),
            "sink_parity_missing_event_ids": missing_ids,
            "runtime_path_active": cutover.get("runtime_path_active") if c_ok else "",
        },
    }

    charter_complete = all(
        [
            is_text(charter["injection_path"].get("mode")),
            is_text(charter["mission_binding"].get("window_start_ts_utc")),
            is_text(charter["mission_binding"].get("window_end_ts_utc")),
            is_text(charter["mission_binding"].get("as_of_time_utc")),
            is_text(charter["mission_binding"].get("label_maturity_lag")),
            steady_rate > 0.0,
            burst_rate > 0.0,
            soak_rate > 0.0,
            recovery_bound > 0,
            budget > 0.0,
        ]
    )
    required_metric_ids = {
        "throughput_steady_eps",
        "throughput_burst_eps",
        "e2e_latency_ms",
        "error_timeout_rate",
        "consumer_lag",
        "checkpoint_health",
        "runtime_backpressure",
        "archive_sink_backlog",
        "duplicate_admission_and_dedupe",
        "quarantine_posture",
        "runtime_trace_coverage",
        "runtime_unit_cost",
    }
    present_ids = {r.get("metric_id") for r in surface_map.get("required_metric_surfaces", []) if isinstance(r, dict)}
    map_complete = required_metric_ids.issubset(present_ids) and all(
        r.get("surface") not in (None, "", {}) for r in surface_map.get("required_metric_surfaces", []) if r.get("metric_id") in required_metric_ids
    )
    archive_pinned = archive_design.get("status") == "PINNED_FOR_PR3_VALIDATION" and isinstance(missing_ids, list) and len(missing_ids) == 0

    b = {
        "B01_entry_lock_present": True,
        "B02_upstream_pr2_ready": upstream_ready,
        "B03_run_charter_complete": charter_complete,
        "B04_measurement_surface_map_complete": map_complete,
        "B05_preflight_dependency_ready": preflight_pass,
        "B06_archive_sink_design_pinned": archive_pinned,
    }
    blockers: List[str] = []
    if not b["B01_entry_lock_present"]:
        blockers.append("PR3.B01_ENTRY_LOCK_MISSING")
    if not b["B02_upstream_pr2_ready"]:
        blockers.append("PR3.B02_UPSTREAM_PR2_NOT_READY")
    if not b["B03_run_charter_complete"]:
        blockers.append("PR3.B03_CHARTER_INCOMPLETE")
    if not b["B04_measurement_surface_map_complete"]:
        blockers.append("PR3.B04_MEASUREMENT_SURFACE_MAP_MISSING")
    if not b["B05_preflight_dependency_ready"]:
        blockers.append("PR3.B05_PREFLIGHT_DEPENDENCY_UNREADY")
    if not b["B06_archive_sink_design_pinned"]:
        blockers.append("PR3.B06_ARCHIVE_SINK_DESIGN_UNPINNED")

    entry_lock = {
        "phase": "PR3",
        "state": "S0",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr3_id,
        "upstream": {
            "pr2_execution_id": pr2_id,
            "required_receipt_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr2_id}/pr2_s3_execution_receipt.json",
            "required_summary_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr2_id}/pr2_execution_summary.json",
            "required_receipt_verdict": "PR2_S3_READY",
            "required_next_gate": "PR3_READY",
        },
        "strict_upstream_ready": b["B02_upstream_pr2_ready"],
        "upstream_checks": upstream_checks,
        "authorities": [
            "docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md",
            "docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR3.road_to_prod.md",
            "docs/model_spec/platform/pre-design_decisions/dev-full_road-to-production-ready.md",
            "docs/model_spec/data-engine/interface_pack/",
        ],
    }

    elapsed = round((time.perf_counter() - t0) / 60.0, 3)
    receipt = {
        "phase": "PR3",
        "state": "S0",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr3_id,
        "verdict": "PR3_S0_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "next_state": "PR3-S1" if len(blockers) == 0 else "PR3-S0",
        "next_gate": "PR3_RUNTIME_S0_READY" if len(blockers) == 0 else "PR3_REMEDIATE_S0",
        "open_blockers": len(blockers),
        "blocker_ids": blockers,
        "outputs": [
            "pr3_entry_lock.json",
            "g3a_run_charter.active.json",
            "g3a_measurement_surface_map.json",
            "g3a_preflight_snapshot.json",
            "g3a_archive_sink_design_decision.json",
        ],
        "checks": b,
        "tgt_updates": [
            {
                "target_id": "TGT-08",
                "status": "IN_PROGRESS" if len(blockers) == 0 else "OPEN",
                "evidence_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr3_id}/g3a_measurement_surface_map.json",
                "notes": "Runtime threshold-family measurement surfaces bound at PR3-S0; full closure due at PR3-S5.",
            },
            {
                "target_id": "TGT-09",
                "status": "IN_PROGRESS" if len(blockers) == 0 else "OPEN",
                "evidence_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr3_id}/g3a_archive_sink_design_decision.json",
                "notes": "Archive sink design pinned for S2/S4 validation; full closure due at PR3-S5.",
            },
        ],
        "elapsed_minutes": elapsed,
        "runtime_budget_minutes": 20,
        "attributable_spend_usd": 0.0,
        "cost_envelope_usd": budget if budget > 0 else 250.0,
        "advisory_ids": [
            c.get("id")
            for c in charter.get("carry_forward_constraints", [])
            if isinstance(c, dict) and is_text(c.get("id"))
        ],
    }

    dump_json(pr3_root / "pr3_entry_lock.json", entry_lock)
    dump_json(pr3_root / "g3a_run_charter.active.json", charter)
    dump_json(pr3_root / "g3a_measurement_surface_map.json", surface_map)
    dump_json(pr3_root / "g3a_preflight_snapshot.json", preflight)
    dump_json(pr3_root / "g3a_archive_sink_design_decision.json", archive_design)
    dump_json(pr3_root / "pr3_s0_execution_receipt.json", receipt)
    dump_json(
        root / "pr3_latest.json",
        {
            "phase": "PR3",
            "execution_id": pr3_id,
            "latest_state": "S0",
            "latest_receipt": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr3_id}/pr3_s0_execution_receipt.json",
            "updated_at_utc": now_utc(),
        },
    )

    print(
        json.dumps(
            {
                "execution_id": pr3_id,
                "state": "S0",
                "verdict": receipt["verdict"],
                "next_state": receipt["next_state"],
                "next_gate": receipt["next_gate"],
                "open_blockers": receipt["open_blockers"],
                "blocker_ids": blockers,
                "preflight_failed_checks": [d["check_id"] for d in failed_dep],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
