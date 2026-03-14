#!/usr/bin/env python3
"""Deterministic PR2-S1 executor for road_to_prod (dev_full)."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml


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


def dump_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def is_tbd(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip()
        return (not text) or text.upper().startswith("TBD") or text.upper().startswith("PENDING")
    if isinstance(value, (dict, list)):
        return len(value) == 0
    return False


def get_row(rows_by_id: Dict[str, Dict[str, Any]], row_id: str) -> Dict[str, Any]:
    row = rows_by_id.get(row_id)
    if row is None:
        raise RuntimeError(f"Missing row: {row_id}")
    return row


def get_val(rows_by_id: Dict[str, Dict[str, Any]], row_id: str) -> Any:
    return get_row(rows_by_id, row_id).get("value")


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute PR2-S1 contract population from PR2-S0.")
    parser.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    parser.add_argument("--pr2-execution-id", default="")
    parser.add_argument("--target-steady-eps", type=float, default=3000.0)
    parser.add_argument("--target-burst-eps", type=float, default=6000.0)
    parser.add_argument("--recovery-bound-seconds", type=int, default=180)
    parser.add_argument("--latency-p95-max-ms", type=int, default=350)
    parser.add_argument("--latency-p99-max-ms", type=int, default=700)
    parser.add_argument("--error-rate-max", type=float, default=0.002)
    parser.add_argument("--budget-envelope-usd", type=float, default=250.0)
    parser.add_argument("--generated-by", default="codex-gpt5")
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()

    t0 = time.perf_counter()
    generated_at = utc_now_iso()
    root = Path(args.run_control_root)
    if not root.exists():
        raise RuntimeError(f"Missing run-control root: {root}")

    if args.pr2_execution_id.strip():
        execution_id = args.pr2_execution_id.strip()
    else:
        execution_id = str(load_json(root / "pr2_latest.json").get("execution_id", "")).strip()
    if not execution_id:
        raise RuntimeError("Unable to resolve PR2 execution id.")
    run_root = root / execution_id

    s0 = load_json(run_root / "pr2_s0_execution_receipt.json")
    if str(s0.get("verdict")) != "PR2_S0_READY" or int(s0.get("open_blockers", 1)) != 0:
        raise RuntimeError("Upstream lock failed: PR2-S0 not ready.")

    inventory = load_json(run_root / "pr2_required_row_inventory.json")
    gap_map = load_json(run_root / "pr2_gap_map.json")
    entry_lock = load_json(run_root / "pr2_entry_lock.json")
    pr1_exec = str(entry_lock.get("upstream", {}).get("pr1_execution_id", "")).strip()
    if not pr1_exec:
        raise RuntimeError("Missing PR1 execution id in entry lock.")
    pr1_root = root / pr1_exec
    g2_pack = load_json(pr1_root / "g2_data_realism_pack_index.json")

    rows = [dict(row) for row in inventory.get("rows", [])]
    by_id = {str(row.get("row_id")): row for row in rows}

    baseline_steady = float(g2_pack.get("activated_rc2s_envelope", {}).get("numeric_set", {}).get("steady_rate_eps", 0.0))
    baseline_burst = float(g2_pack.get("activated_rc2s_envelope", {}).get("numeric_set", {}).get("burst_rate_eps", 0.0))
    steady_mul = (args.target_steady_eps / baseline_steady) if baseline_steady > 0 else 0.0
    projected_burst = baseline_burst * steady_mul if steady_mul > 0 else 0.0
    burst_gap = max(0.0, args.target_burst_eps - projected_burst)

    runbook_index_ref = f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_runbook_index.json"
    owners = {
        "HP_LATENCY_P99_BREACH": "runtime_sre_oncall",
        "HP_ERROR_RATE_SPIKE": "runtime_sre_oncall",
        "IG_ADMIT_DROP": "ingress_ops_oncall",
        "IG_LATENCY_P99_BREACH": "ingress_ops_oncall",
        "IG_QUARANTINE_SPIKE": "ingress_ops_oncall",
        "IG_DDB_THROTTLE": "platform_data_oncall",
        "MSK_LAG_P99_BREACH": "stream_ops_oncall",
        "FLINK_CHECKPOINT_FAIL": "stream_ops_oncall",
        "FLINK_BACKPRESSURE_HIGH": "stream_ops_oncall",
        "AURORA_LATENCY_SPIKE": "state_store_oncall",
        "DUPLICATE_ADMISSION": "data_correctness_oncall",
    }
    overrides = {
        "PR2.R006": (round(args.target_steady_eps, 6), "S1_POLICY_PIN#steady_rate"),
        "PR2.R007": (round(args.target_burst_eps, 6), "S1_POLICY_PIN#burst_rate"),
        "PR2.R010": (int(args.recovery_bound_seconds), "S1_POLICY_PIN#recovery_bound"),
        "PR2.R020": ("IG_ADMISSION_TS", "S1_POLICY_PIN#e2e_start"),
        "PR2.R021": ("DECISION_COMMIT_TS", "S1_POLICY_PIN#e2e_end"),
        "PR2.R022": (int(args.latency_p95_max_ms), "S1_POLICY_PIN#p95_max"),
        "PR2.R023": (int(args.latency_p99_max_ms), "S1_POLICY_PIN#p99_max"),
        "PR2.R024": (float(args.error_rate_max), "S1_POLICY_PIN#error_rate_max"),
        "PR2.R025": (round(args.budget_envelope_usd, 2), "S1_POLICY_PIN#budget_envelope_usd"),
        "PR2.O008": (owners, "S1_POLICY_PIN#alerts.required_owners_bound"),
        "PR2.O009": (runbook_index_ref, "S1_ARTIFACT#pr2_runbook_index.json"),
    }

    updates: List[Dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        if row_id not in overrides:
            continue
        prev = row.get("value")
        prev_status = str(row.get("status", ""))
        value, source_ref = overrides[row_id]
        row["value"] = value
        row["value_source_ref"] = source_ref
        row["status"] = "filled_in_s1" if prev_status == "pending_fill" else "repinned_in_s1"
        updates.append(
            {
                "row_id": row_id,
                "field_path": row.get("field_path"),
                "previous_status": prev_status,
                "new_status": row.get("status"),
                "previous_value": prev,
                "new_value": value,
                "value_source_ref": source_ref,
            }
        )
    by_id = {str(row.get("row_id")): row for row in rows}
    required_rows = [row for row in rows if bool(row.get("required"))]
    required_tbd = [str(row.get("row_id")) for row in required_rows if is_tbd(row.get("value"))]

    runtime_contract = {
        "phase": "PR2",
        "state": "S1",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "envelope_id": "RC2-S",
        "status": "ACTIVE",
        "mission_binding": {
            "window_start_ts_utc": get_val(by_id, "PR2.R001"),
            "window_end_ts_utc": get_val(by_id, "PR2.R002"),
            "as_of_time_utc": get_val(by_id, "PR2.R003"),
            "label_maturity_lag": get_val(by_id, "PR2.R004"),
        },
        "injection_path": {"mode": get_val(by_id, "PR2.R005"), "scope_notes": "via_IG certified; explicit PR3 burst shaper required for 6000 eps burst proof."},
        "load_campaign": {
            "steady": {"rate_eps": get_val(by_id, "PR2.R006"), "duration_min": get_val(by_id, "PR2.R008")},
            "burst": {"rate_eps": get_val(by_id, "PR2.R007"), "duration_min": get_val(by_id, "PR2.R009")},
            "recovery": {"bound_seconds": get_val(by_id, "PR2.R010")},
            "soak": {"rate_eps": get_val(by_id, "PR2.R006"), "duration_min": get_val(by_id, "PR2.R011")},
        },
        "sample_minima": {
            "max_unmatched_join_rate": get_val(by_id, "PR2.R016"),
            "max_fanout_p99": get_val(by_id, "PR2.R017"),
        },
        "thresholds": {
            "hot_path_slo": {
                "decision_latency_ms": {"p95_max": get_val(by_id, "PR2.R022"), "p99_max": get_val(by_id, "PR2.R023")},
                "error_rate_max": get_val(by_id, "PR2.R024"),
            },
            "cost": {"budget_envelope_usd": get_val(by_id, "PR2.R025")},
        },
        "measurement_surfaces": {
            "throughput": {"steady_surface": get_val(by_id, "PR2.R018"), "burst_surface": get_val(by_id, "PR2.R019")},
            "latency": {"e2e_start": get_val(by_id, "PR2.R020"), "e2e_end": get_val(by_id, "PR2.R021")},
        },
        "constraint_notes": {
            "uniform_speedup_preserves_shape": True,
            "baseline_steady_eps": baseline_steady,
            "baseline_burst_eps": baseline_burst,
            "target_steady_eps": args.target_steady_eps,
            "target_burst_eps": args.target_burst_eps,
            "projected_burst_eps_with_uniform_speedup": round(projected_burst, 6),
            "burst_gap_eps": round(burst_gap, 6),
            "requires_burst_shaper_in_pr3": burst_gap > 0,
        },
    }
    opsgov_contract = {
        "phase": "PR2",
        "state": "S1",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "monitoring_baselines_version": "v0",
        "status": "ACTIVE",
        "source_packs": {
            "g2_data_realism_pack_ref": get_val(by_id, "PR2.O001"),
            "g3a_runtime_pack_ref": "DEFERRED_TO_PR3_O010",
            "g3b_ops_gov_pack_ref": "DEFERRED_TO_PR4_O011",
        },
        "window_basis": {
            "window_start_ts_utc": get_val(by_id, "PR2.O002"),
            "window_end_ts_utc": get_val(by_id, "PR2.O003"),
            "as_of_time_utc": get_val(by_id, "PR2.O004"),
            "label_maturity_lag": get_val(by_id, "PR2.O005"),
        },
        "rules": {"distribution_required": get_val(by_id, "PR2.O006"), "missing_metric_policy": get_val(by_id, "PR2.O007")},
        "alerts": {"required_owners_bound": get_val(by_id, "PR2.O008"), "missing_owner_policy": "FAIL_CLOSED"},
        "runbooks": {"required": list(owners.keys()), "index_ref": get_val(by_id, "PR2.O009")},
    }
    runbook_index = {
        "phase": "PR2",
        "state": "S1",
        "generated_at_utc": generated_at,
        "execution_id": execution_id,
        "runbooks": [{"runbook_id": key, "owner": value} for key, value in owners.items()],
    }
    calibration = {
        "phase": "PR2",
        "state": "S1",
        "generated_at_utc": generated_at,
        "execution_id": execution_id,
        "rows": [
            {"row_id": "PR2.R006", "metric": "steady_rate_eps", "baseline": baseline_steady, "target": get_val(by_id, "PR2.R006")},
            {"row_id": "PR2.R007", "metric": "burst_rate_eps", "baseline": baseline_burst, "target": get_val(by_id, "PR2.R007")},
            {"row_id": "PR2.R010", "metric": "recovery_bound_seconds", "baseline": int(g2_pack.get("activated_rc2s_envelope", {}).get("numeric_set", {}).get("recovery_window_min", 0) * 60), "target": get_val(by_id, "PR2.R010")},
            {"row_id": "PR2.R022", "metric": "latency_p95_max_ms", "baseline": 450, "target": get_val(by_id, "PR2.R022")},
            {"row_id": "PR2.R023", "metric": "latency_p99_max_ms", "baseline": 900, "target": get_val(by_id, "PR2.R023")},
            {"row_id": "PR2.R024", "metric": "error_rate_max", "baseline": 0.005, "target": get_val(by_id, "PR2.R024")},
            {"row_id": "PR2.R025", "metric": "budget_envelope_usd", "baseline": 300.0, "target": get_val(by_id, "PR2.R025")},
        ],
    }
    deferred = {
        "phase": "PR2",
        "state": "S1",
        "generated_at_utc": generated_at,
        "execution_id": execution_id,
        "deferred_optional_rows": gap_map.get("deferred_optional_rows", []),
        "carry_forward_constraints": [
            {
                "id": "PR2.S1.CN01_BURST_SHAPER_REQUIRED",
                "due_state": "PR3-S1",
                "description": "Uniform WSP speedup cannot realize 6000 burst from current natural shape; burst shaper required in PR3.",
            }
        ],
    }
    ledger = {
        "phase": "PR2",
        "state": "S1",
        "generated_at_utc": generated_at,
        "execution_id": execution_id,
        "required_pending_before": int(gap_map.get("required_pending_count", 0)),
        "required_tbd_after": required_tbd,
        "updated_rows": updates,
        "repin_summary": {
            "steady_rate_eps": get_val(by_id, "PR2.R006"),
            "burst_rate_eps": get_val(by_id, "PR2.R007"),
            "projected_burst_eps_with_uniform_speedup": round(projected_burst, 6),
            "burst_gap_eps": round(burst_gap, 6),
        },
    }

    runtime_path = run_root / "pr2_runtime_numeric_contract.rc2s.active.yaml"
    opsgov_path = run_root / "pr2_opsgov_numeric_contract.rc2s.active.yaml"
    runbook_path = run_root / "pr2_runbook_index.json"
    ledger_path = run_root / "pr2_threshold_population_ledger.json"
    calib_path = run_root / "pr2_calibration_traceability.json"
    deferred_path = run_root / "pr2_deferred_scope_register.json"
    dump_yaml(runtime_path, runtime_contract)
    dump_yaml(opsgov_path, opsgov_contract)
    dump_json(runbook_path, runbook_index)
    dump_json(ledger_path, ledger)
    dump_json(calib_path, calibration)
    dump_json(deferred_path, deferred)

    traced_ids = {str(row.get("row_id")) for row in calibration.get("rows", [])}
    expected_trace = {"PR2.R006", "PR2.R007", "PR2.R010", "PR2.R022", "PR2.R023", "PR2.R024", "PR2.R025"}
    checks = {
        "B05_runtime_contract_present": runtime_path.exists(),
        "B06_opsgov_contract_present": opsgov_path.exists(),
        "B07_no_required_tbd": len(required_tbd) == 0,
        "B08_measurement_surface_bound": all(not is_tbd(get_val(by_id, x)) for x in ["PR2.R018", "PR2.R019", "PR2.R020", "PR2.R021"]),
        "B09_calibration_trace_present": expected_trace.issubset(traced_ids),
    }
    blockers: List[str] = []
    if not checks["B05_runtime_contract_present"]:
        blockers.append("PR2.B05_RUNTIME_CONTRACT_MISSING")
    if not checks["B06_opsgov_contract_present"]:
        blockers.append("PR2.B06_OPSGOV_CONTRACT_MISSING")
    if not checks["B07_no_required_tbd"]:
        blockers.append("PR2.B07_REQUIRED_TBD_REMAIN")
    if not checks["B08_measurement_surface_bound"]:
        blockers.append("PR2.B08_MEASUREMENT_SURFACE_UNBOUND")
    if not checks["B09_calibration_trace_present"]:
        blockers.append("PR2.B09_CALIBRATION_TRACE_MISSING")

    open_blockers = len(blockers)
    pass_state = open_blockers == 0
    receipt = {
        "phase": "PR2",
        "state": "S1",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": execution_id,
        "verdict": "PR2_S1_READY" if pass_state else "HOLD_REMEDIATE",
        "next_state": "PR2-S2" if pass_state else "PR2-S1",
        "open_blockers": open_blockers,
        "blocker_ids": blockers,
        "checks": checks,
        "required_tbd_rows": required_tbd,
        "outputs": [runtime_path.name, opsgov_path.name, ledger_path.name, calib_path.name, deferred_path.name, runbook_path.name],
        "elapsed_minutes": round((time.perf_counter() - t0) / 60.0, 3),
        "runtime_budget_minutes": 25,
        "attributable_spend_usd": 0.0,
        "cost_envelope_usd": 5.0,
        "advisory_ids": ["PR2.S1.AD01_SPEEDUP_UNIFORM_SHAPE_BURST_SHAPER_REQUIRED"],
    }
    dump_json(run_root / "pr2_s1_execution_receipt.json", receipt)
    dump_json(
        root / "pr2_latest.json",
        {
            "phase": "PR2",
            "execution_id": execution_id,
            "latest_state": "S1",
            "latest_receipt": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{execution_id}/pr2_s1_execution_receipt.json",
            "updated_at_utc": utc_now_iso(),
        },
    )

    print(
        json.dumps(
            {
                "execution_id": execution_id,
                "state": "S1",
                "verdict": receipt["verdict"],
                "next_state": receipt["next_state"],
                "open_blockers": open_blockers,
                "steady_rate_eps": get_val(by_id, "PR2.R006"),
                "burst_rate_eps": get_val(by_id, "PR2.R007"),
                "required_tbd_count": len(required_tbd),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
