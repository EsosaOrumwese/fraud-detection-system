#!/usr/bin/env python3
"""Deterministic PR1-S5 rollup executor for road_to_prod (dev_full)."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def to_bool(value: Any) -> bool:
    return bool(value)


def to_float(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def is_target_pinned(target_id: str, receipt: Dict[str, Any]) -> bool:
    for row in receipt.get("tgt_updates", []):
        if row.get("target_id") == target_id and str(row.get("status", "")).upper() == "PINNED":
            return True
    return False


def classify_role(name: str) -> str:
    if name.endswith("_execution_receipt.json"):
        return "state_receipt"
    if name.endswith("_support_receipt.json"):
        return "support_receipt"
    if name.endswith(".yaml"):
        return "policy_contract"
    if name == "pr1_evidence_index.json":
        return "evidence_catalog"
    if name == "g2_data_realism_pack_index.json":
        return "pack_index"
    if name == "g2_data_realism_verdict.json":
        return "gate_verdict"
    if name == "pr1_blocker_register.json":
        return "blocker_register"
    if name == "pr1_execution_summary.json":
        return "phase_summary"
    return "artifact"


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute PR1-S5 deterministic rollup and verdict.")
    parser.add_argument(
        "--run-root",
        required=True,
        help="Path to PR1 run root, e.g. runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_.../",
    )
    parser.add_argument("--generated-by", default="codex-gpt5")
    parser.add_argument("--version", default="1.1.0")
    args = parser.parse_args()

    t0 = time.perf_counter()
    run_root = Path(args.run_root)
    if not run_root.exists():
        raise RuntimeError(f"Run root does not exist: {run_root}")

    s0 = load_json(run_root / "pr1_s0_execution_receipt.json")
    s1 = load_json(run_root / "pr1_s1_execution_receipt.json")
    s2 = load_json(run_root / "pr1_s2_execution_receipt.json")
    s3 = load_json(run_root / "pr1_s3_execution_receipt.json")
    s4 = load_json(run_root / "pr1_s4_execution_receipt.json")
    window_charter = load_json(run_root / "pr1_window_charter.json")
    s1_profile = load_json(run_root / "pr1_g2_profile_summary.json")
    cohort_profile = load_json(run_root / "pr1_g2_cohort_profile.json")
    seed = load_json(run_root / "g2_load_campaign_seed.json")
    join_matrix = load_json(run_root / "pr1_join_matrix.json")
    s3_policy = load_json(run_root / "pr1_late_event_policy_receipt.json")
    s4_maturity = load_json(run_root / "pr1_label_maturity_report.json")
    s4_window = load_json(run_root / "pr1_learning_window_spec.json")
    s4_leakage = load_json(run_root / "pr1_leakage_guardrail_report.json")
    s4_baseline = load_json(run_root / "g2_monitoring_baselines.json")

    execution_id = str(s4.get("execution_id", ""))
    if not execution_id:
        raise RuntimeError("Missing execution_id in S4 receipt.")
    if str(s4.get("verdict", "")) != "PR1_S4_READY" or int(s4.get("open_blockers", 1)) != 0:
        raise RuntimeError("S5 upstream lock failed: S4 is not PR1_S4_READY with open_blockers=0.")

    generated_at = utc_now_iso()
    window = window_charter.get("window_charter", {})
    rc2_candidate = seed.get("rc2s_envelope_candidate", {})

    # Finalize RC2-S envelope (TGT-02) from measured S1 profile + seeded candidate + cohort mix.
    steady_rate = float(rc2_candidate.get("steady_rate_eps", s1_profile.get("observed_profile", {}).get("steady_rate_eps_observed", 0.0)))
    burst_rate = float(rc2_candidate.get("burst_rate_eps", 0.0))
    steady_duration = int(rc2_candidate.get("steady_duration_min", 0))
    burst_duration = int(rc2_candidate.get("burst_duration_min", 0))
    recovery_duration = int(rc2_candidate.get("recovery_window_min", 0))
    soak_duration = int(rc2_candidate.get("soak_duration_min", 0))
    min_processed_events = int(rc2_candidate.get("min_processed_events", 0))
    min_unique_event_types = int(rc2_candidate.get("min_unique_event_types", 0))

    rc2s_checks = {
        "steady_rate_positive": steady_rate > 0.0,
        "burst_rate_not_below_steady": burst_rate >= steady_rate,
        "durations_positive": all(x > 0 for x in [steady_duration, burst_duration, recovery_duration, soak_duration]),
        "min_processed_events_positive": min_processed_events > 0,
        "min_unique_event_types_positive": min_unique_event_types > 0,
        "cohort_contract_present": bool(cohort_profile.get("overall_pass")),
        "profile_basis_present": bool(s1_profile.get("overall_pass")),
    }
    tgt02_pinned = all(rc2s_checks.values())

    activated_rc2s_envelope = {
        "status": "ACTIVE" if tgt02_pinned else "HOLD_REMEDIATE",
        "window_basis": {
            "window_start_ts_utc": window.get("window_start_ts_utc"),
            "window_end_ts_utc": window.get("window_end_ts_utc"),
            "as_of_time_utc": window.get("as_of_time_utc"),
            "injection_path_mode": window_charter.get("injection_path", {}).get("mode", "via_IG"),
        },
        "measurement_surfaces": {
            "steady_rate_surface": "IG_ADMITTED_EVENTS_PER_SEC",
            "burst_rate_surface": "IG_ADMITTED_EVENTS_PER_SEC",
            "join_integrity_surface": "JOIN_MATRIX_OBSERVED_RATES",
            "time_causality_surface": "FUTURE_ROW_BOUNDARY_CHECKS",
        },
        "numeric_set": {
            "steady_rate_eps": round(steady_rate, 6),
            "burst_rate_eps": round(burst_rate, 6),
            "steady_duration_min": steady_duration,
            "burst_duration_min": burst_duration,
            "recovery_window_min": recovery_duration,
            "soak_duration_min": soak_duration,
            "min_processed_events": min_processed_events,
            "min_unique_event_types": min_unique_event_types,
            "cohort_requirements_ref": "pr1_g2_cohort_profile.json",
            "label_maturity_lag_days": s4_window.get("window_basis", {}).get("label_maturity_lag_days"),
        },
        "derivation": {
            "source_seed_ref": "g2_load_campaign_seed.json",
            "source_profile_ref": "pr1_g2_profile_summary.json",
            "source_cohort_ref": "pr1_g2_cohort_profile.json",
            "finalization_state": "S5",
        },
        "checks": rc2s_checks,
    }

    # Derive target status map.
    tgt_status_map = {
        "TGT-02": "PINNED" if tgt02_pinned else "INCOMPLETE",
        "TGT-03": "PINNED" if (to_bool(s3.get("checks", {}).get("B12_lateness_policy_pinned")) and is_target_pinned("TGT-03", s3)) else "INCOMPLETE",
        "TGT-04": "PINNED" if (to_bool(s3.get("checks", {}).get("B11_ieg_scope_pinned")) and is_target_pinned("TGT-04", s3)) else "INCOMPLETE",
        "TGT-05": "PINNED" if (to_bool(s4.get("checks", {}).get("B13_label_maturity_pinned")) and is_target_pinned("TGT-05", s4)) else "INCOMPLETE",
        "TGT-06": "PINNED" if (to_bool(s2.get("checks", {}).get("B09_thresholds_pinned")) and is_target_pinned("TGT-06", s2)) else "INCOMPLETE",
        "TGT-07": "PINNED" if (to_bool(s4.get("checks", {}).get("B15_monitoring_baseline_present")) and is_target_pinned("TGT-07", s4)) else "INCOMPLETE",
    }

    blockers: List[Dict[str, Any]] = []

    incomplete_targets = [k for k, v in tgt_status_map.items() if v != "PINNED"]
    if incomplete_targets:
        blockers.append(
            {
                "blocker_id": "PR1.B16_TGT_G2_SET_INCOMPLETE",
                "severity": "mission_blocking",
                "reason": "one_or_more_required_targets_not_pinned",
                "incomplete_targets": incomplete_targets,
                "rerun_boundary": "S5",
            }
        )

    required_artifacts_pre_s5 = [
        "pr1_entry_lock.json",
        "pr1_window_charter.json",
        "pr1_evidence_inventory.json",
        "pr1_g2_profile_summary.json",
        "pr1_g2_cohort_profile.json",
        "g2_load_campaign_seed.json",
        "pr1_join_matrix.json",
        "pr1_join_decision_register.json",
        "g2_rtdl_allowlist.yaml",
        "g2_rtdl_denylist.yaml",
        "pr1_ieg_scope_decisions.json",
        "pr1_late_event_policy_receipt.json",
        "pr1_label_maturity_report.json",
        "pr1_learning_window_spec.json",
        "pr1_leakage_guardrail_report.json",
        "g2_monitoring_baselines.json",
    ]
    missing_pre_s5 = [name for name in required_artifacts_pre_s5 if not (run_root / name).exists()]
    if missing_pre_s5:
        blockers.append(
            {
                "blocker_id": "PR1.B17_PACK_INDEX_MISSING",
                "severity": "mission_blocking",
                "reason": "required_upstream_artifacts_missing",
                "missing_artifacts": missing_pre_s5,
                "rerun_boundary": "S5",
            }
        )

    # Build S5 artifacts.
    pack_index = {
        "phase": "PR1",
        "state": "S5",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "pack_id": f"G2_DATA_REALISM_PACK_{execution_id}",
        "pack_version": "v1",
        "status": "ACTIVE" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "window_basis": {
            "window_start_ts_utc": window.get("window_start_ts_utc"),
            "window_end_ts_utc": window.get("window_end_ts_utc"),
            "as_of_time_utc": window.get("as_of_time_utc"),
            "injection_path_mode": window_charter.get("injection_path", {}).get("mode", "via_IG"),
        },
        "target_status_map": tgt_status_map,
        "activated_rc2s_envelope": activated_rc2s_envelope,
        "policy_refs": {
            "rtdl_allowlist": "g2_rtdl_allowlist.yaml",
            "rtdl_denylist": "g2_rtdl_denylist.yaml",
            "ieg_scope_decisions": "pr1_ieg_scope_decisions.json",
            "late_event_policy": "pr1_late_event_policy_receipt.json",
            "learning_window_spec": "pr1_learning_window_spec.json",
            "leakage_guardrail_report": "pr1_leakage_guardrail_report.json",
            "monitoring_baselines": "g2_monitoring_baselines.json",
        },
        "core_artifact_refs": required_artifacts_pre_s5,
        "upstream_state_receipts": [
            "pr1_s0_execution_receipt.json",
            "pr1_s1_execution_receipt.json",
            "pr1_s2_execution_receipt.json",
            "pr1_s3_execution_receipt.json",
            "pr1_s4_execution_receipt.json",
        ],
    }

    # Write pack first so evidence/verdict can reference it.
    dump_json(run_root / "g2_data_realism_pack_index.json", pack_index)

    required_artifacts_all = required_artifacts_pre_s5 + [
        "g2_data_realism_pack_index.json",
        "g2_data_realism_verdict.json",
        "pr1_blocker_register.json",
        "pr1_execution_summary.json",
        "pr1_evidence_index.json",
    ]

    # Evidence index (deterministic: sorted names, include self hash by rewrite).
    evidence_entries: List[Dict[str, Any]] = []
    for name in sorted(required_artifacts_all):
        if name == "pr1_evidence_index.json":
            continue
        p = run_root / name
        if p.exists():
            evidence_entries.append(
                {
                    "artifact": name,
                    "role": classify_role(name),
                    "size_bytes": p.stat().st_size,
                    "sha256": sha256_file(p),
                }
            )
        else:
            evidence_entries.append(
                {
                    "artifact": name,
                    "role": classify_role(name),
                    "missing": True,
                }
            )

    evidence_index = {
        "phase": "PR1",
        "state": "S5",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "artifact_count": len(evidence_entries),
        "artifacts": evidence_entries,
    }
    dump_json(run_root / "pr1_evidence_index.json", evidence_index)
    # Append self entry and rewrite deterministically.
    evidence_entries.append(
        {
            "artifact": "pr1_evidence_index.json",
            "role": "evidence_catalog",
            "size_bytes": (run_root / "pr1_evidence_index.json").stat().st_size,
            "sha256": sha256_file(run_root / "pr1_evidence_index.json"),
        }
    )
    evidence_index["artifact_count"] = len(evidence_entries)
    evidence_index["artifacts"] = evidence_entries
    dump_json(run_root / "pr1_evidence_index.json", evidence_index)

    # Emit provisional outputs so post-emit completeness check is meaningful.
    provisional_overall_pass = len(blockers) == 0
    provisional_blocker_ids = [b["blocker_id"] for b in blockers]

    provisional_verdict = {
        "phase": "PR1",
        "state": "S5",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "overall_pass": provisional_overall_pass,
        "verdict": "PASS" if provisional_overall_pass else "HOLD_REMEDIATE",
        "open_blockers": len(blockers),
        "blocker_ids": provisional_blocker_ids,
        "next_gate": "PR2_READY" if provisional_overall_pass else "PR1_S5_REMEDIATE",
        "gate_id": "G2",
    }
    dump_json(run_root / "g2_data_realism_verdict.json", provisional_verdict)

    provisional_summary = {
        "phase": "PR1",
        "state": "S5",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "verdict": "PR2_READY" if provisional_overall_pass else "HOLD_REMEDIATE",
        "next_gate": "PR2_READY" if provisional_overall_pass else "PR1_S5_REMEDIATE",
        "open_blockers": len(blockers),
        "blocker_ids": provisional_blocker_ids,
        "tgt_status_map": tgt_status_map,
        "evidence_refs": {
            "g2_data_realism_pack_index": "g2_data_realism_pack_index.json",
            "g2_data_realism_verdict": "g2_data_realism_verdict.json",
            "pr1_blocker_register": "pr1_blocker_register.json",
            "pr1_evidence_index": "pr1_evidence_index.json",
        },
        "runtime_cost_rollup": {
            "elapsed_minutes_total_s0_to_s5": 0.0,
            "runtime_budget_minutes_total": 85,
            "attributable_spend_usd_total_s1_to_s5": 0.0,
            "cost_envelope_usd_total": 90.0,
        },
        "activated_rc2s_envelope_ref": "g2_data_realism_pack_index.json#activated_rc2s_envelope",
    }
    dump_json(run_root / "pr1_execution_summary.json", provisional_summary)

    provisional_blocker_register = {
        "phase": "PR1",
        "state": "S5",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "overall_pass": provisional_overall_pass,
        "open_blockers": len(blockers),
        "blocker_ids": provisional_blocker_ids,
        "blockers": blockers,
    }
    dump_json(run_root / "pr1_blocker_register.json", provisional_blocker_register)

    missing_after_write = [name for name in required_artifacts_all if not (run_root / name).exists()]
    if missing_after_write:
        blockers.append(
            {
                "blocker_id": "PR1.B17_PACK_INDEX_MISSING",
                "severity": "mission_blocking",
                "reason": "required_s5_artifacts_missing_after_emit",
                "missing_artifacts": missing_after_write,
                "rerun_boundary": "S5",
            }
        )

    # Final verdict and blocker synthesis.
    if len(blockers) > 0:
        blockers.append(
            {
                "blocker_id": "PR1.B18_G2_VERDICT_NOT_PASS",
                "severity": "mission_blocking",
                "reason": "g2_verdict_not_pass_due_to_open_blockers",
                "rerun_boundary": "S5",
            }
        )
        blockers.append(
            {
                "blocker_id": "PR1.B19_OPEN_BLOCKERS_NONZERO",
                "severity": "mission_blocking",
                "reason": "open_blockers_nonzero",
                "open_blockers": len(blockers),
                "rerun_boundary": "S5",
            }
        )

    blocker_ids = [b["blocker_id"] for b in blockers]
    open_blockers = len(blockers)
    overall_pass = open_blockers == 0
    verdict_value = "PASS" if overall_pass else "HOLD_REMEDIATE"

    # Rollup runtime + cost from S0..S5.
    s5_elapsed = round((time.perf_counter() - t0) / 60.0, 3)
    s5_spend = 0.0
    elapsed_total = (
        to_float(s0.get("elapsed_minutes"))
        + to_float(s1.get("elapsed_minutes"))
        + to_float(s2.get("elapsed_minutes"))
        + to_float(s3.get("elapsed_minutes"))
        + to_float(s4.get("elapsed_minutes"))
        + s5_elapsed
    )
    spend_total = (
        to_float(s1.get("attributable_spend_usd"))
        + to_float(s2.get("attributable_spend_usd"))
        + to_float(s3.get("attributable_spend_usd"))
        + to_float(s4.get("attributable_spend_usd"))
        + s5_spend
    )

    g2_verdict = {
        "phase": "PR1",
        "state": "S5",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "overall_pass": overall_pass,
        "verdict": verdict_value,
        "open_blockers": open_blockers,
        "blocker_ids": blocker_ids,
        "next_gate": "PR2_READY" if overall_pass else "PR1_S5_REMEDIATE",
        "gate_id": "G2",
    }
    dump_json(run_root / "g2_data_realism_verdict.json", g2_verdict)

    blocker_register = {
        "phase": "PR1",
        "state": "S5",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "overall_pass": overall_pass,
        "open_blockers": open_blockers,
        "blocker_ids": blocker_ids,
        "blockers": blockers,
    }
    dump_json(run_root / "pr1_blocker_register.json", blocker_register)

    execution_summary = {
        "phase": "PR1",
        "state": "S5",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "verdict": "PR2_READY" if overall_pass else "HOLD_REMEDIATE",
        "next_gate": "PR2_READY" if overall_pass else "PR1_S5_REMEDIATE",
        "open_blockers": open_blockers,
        "blocker_ids": blocker_ids,
        "tgt_status_map": tgt_status_map,
        "evidence_refs": {
            "g2_data_realism_pack_index": "g2_data_realism_pack_index.json",
            "g2_data_realism_verdict": "g2_data_realism_verdict.json",
            "pr1_blocker_register": "pr1_blocker_register.json",
            "pr1_evidence_index": "pr1_evidence_index.json",
        },
        "runtime_cost_rollup": {
            "elapsed_minutes_total_s0_to_s5": round(elapsed_total, 3),
            "runtime_budget_minutes_total": 85,
            "attributable_spend_usd_total_s1_to_s5": round(spend_total, 6),
            "cost_envelope_usd_total": 90.0,
        },
        "activated_rc2s_envelope_ref": "g2_data_realism_pack_index.json#activated_rc2s_envelope",
    }
    dump_json(run_root / "pr1_execution_summary.json", execution_summary)

    s5_receipt = {
        "phase": "PR1",
        "state": "S5",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "verdict": "PR1_S5_READY" if overall_pass else "HOLD_REMEDIATE",
        "next_state": "PR2-S0" if overall_pass else "PR1-S5",
        "open_blockers": open_blockers,
        "blocker_ids": blocker_ids,
        "outputs": [
            "g2_data_realism_pack_index.json",
            "g2_data_realism_verdict.json",
            "pr1_blocker_register.json",
            "pr1_execution_summary.json",
            "pr1_evidence_index.json",
        ],
        "checks": {
            "B16_tgt_set_complete": len(incomplete_targets) == 0,
            "B17_pack_index_present": len(missing_after_write) == 0 and len(missing_pre_s5) == 0,
            "B18_g2_verdict_pass": overall_pass,
            "B19_open_blockers_zero": open_blockers == 0,
        },
        "tgt_updates": (
            [
                {
                    "target_id": "TGT-02",
                    "status": "PINNED",
                    "note": "RC2-S envelope numeric set finalized from PR1 measured profile + cohort contract evidence.",
                }
            ]
            if tgt02_pinned
            else []
        ),
        "elapsed_minutes": s5_elapsed,
        "runtime_budget_minutes": 10,
        "attributable_spend_usd": s5_spend,
        "cost_envelope_usd": 5.0,
        "advisory_ids": ["PR1.S4.AD01_LABEL_TS_PROXY_SEMANTICS"],
    }
    dump_json(run_root / "pr1_s5_execution_receipt.json", s5_receipt)

    latest_path = run_root.parent / "pr1_latest.json"
    latest_payload = {
        "phase": "PR1",
        "execution_id": execution_id,
        "latest_state": "S5",
        "latest_receipt": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr1_s5_execution_receipt.json",
        "updated_at_utc": utc_now_iso(),
    }
    dump_json(latest_path, latest_payload)

    print(
        json.dumps(
            {
                "execution_id": execution_id,
                "state": "S5",
                "verdict": s5_receipt["verdict"],
                "next_state": s5_receipt["next_state"],
                "open_blockers": open_blockers,
                "blocker_ids": blocker_ids,
                "tgt_status_map": tgt_status_map,
                "elapsed_minutes": s5_elapsed,
                "attributable_spend_usd": s5_spend,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
