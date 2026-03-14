#!/usr/bin/env python3
"""Deterministic PR2-S2 executor for road_to_prod (dev_full)."""

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


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        obj = yaml.safe_load(f)
    if not isinstance(obj, dict):
        raise RuntimeError(f"Expected YAML mapping at {path}")
    return obj


def is_nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def is_tbd(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        t = v.strip().upper()
        return (not t) or t.startswith("TBD") or t.startswith("PENDING")
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return False


def collect_tbd(v: Any, p: str = "$") -> List[str]:
    out: List[str] = []
    if isinstance(v, dict):
        for k, c in v.items():
            out.extend(collect_tbd(c, f"{p}.{k}"))
    elif isinstance(v, list):
        for i, c in enumerate(v):
            out.extend(collect_tbd(c, f"{p}[{i}]"))
    elif is_tbd(v):
        out.append(p)
    return out


def to_float(v: Any, default: float = 0.0) -> float:
    try:
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            return float(v.strip())
    except Exception:
        pass
    return default


def runtime_validator(runtime: Dict[str, Any]) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(k: str, ok: bool, obs: Any, why: str) -> None:
        checks.append({"check_id": k, "pass": ok, "observed": obs, "reason": why})

    status = runtime.get("status")
    add("RV01_STATUS_ACTIVE", status == "ACTIVE", status, "status must be ACTIVE")
    add("RV02_ENVELOPE_VALID", runtime.get("envelope_id") in {"RC2-S", "RC2-L"}, runtime.get("envelope_id"), "envelope id must be valid")
    for key in ["window_start_ts_utc", "window_end_ts_utc", "as_of_time_utc", "label_maturity_lag"]:
        v = runtime.get("mission_binding", {}).get(key)
        add(f"RV03_MISSION_{key}", is_nonempty_str(v), v, "mission binding field required")

    mode = runtime.get("injection_path", {}).get("mode")
    add("RV04_INJECTION_MODE", mode in {"via_IG", "via_MSK"}, mode, "injection mode must be via_IG or via_MSK")
    notes = runtime.get("injection_path", {}).get("scope_notes")
    add("RV05_SCOPE_NOTES", is_nonempty_str(notes), notes, "scope notes required")

    steady = to_float(runtime.get("load_campaign", {}).get("steady", {}).get("rate_eps"))
    burst = to_float(runtime.get("load_campaign", {}).get("burst", {}).get("rate_eps"))
    burst_min = to_float(runtime.get("load_campaign", {}).get("burst", {}).get("duration_min"))
    soak_min = to_float(runtime.get("load_campaign", {}).get("soak", {}).get("duration_min"))
    rec = to_float(runtime.get("load_campaign", {}).get("recovery", {}).get("bound_seconds"))
    add("RV06_STEADY_POSITIVE", steady > 0, steady, "steady rate >0")
    add("RV07_BURST_NOT_BELOW_STEADY", burst >= steady > 0, {"steady": steady, "burst": burst}, "burst>=steady")
    add("RV08_RECOVERY_POSITIVE", rec > 0, rec, "recovery >0")
    add("RV09_SOAK_VS_BURST", soak_min >= 3 * burst_min, {"soak_min": soak_min, "burst_min": burst_min}, "soak >= 3x burst")

    p95 = to_float(runtime.get("thresholds", {}).get("hot_path_slo", {}).get("decision_latency_ms", {}).get("p95_max"))
    p99 = to_float(runtime.get("thresholds", {}).get("hot_path_slo", {}).get("decision_latency_ms", {}).get("p99_max"))
    err = to_float(runtime.get("thresholds", {}).get("hot_path_slo", {}).get("error_rate_max"))
    unmatched = to_float(runtime.get("sample_minima", {}).get("max_unmatched_join_rate"))
    fanout = to_float(runtime.get("sample_minima", {}).get("max_fanout_p99"))
    add("RV10_LATENCY_ORDER", p95 <= p99, {"p95": p95, "p99": p99}, "p95<=p99")
    add("RV11_ERROR_BOUND", 0 <= err <= 1, err, "error bound [0,1]")
    add("RV12_UNMATCHED_BOUND", 0 <= unmatched <= 1, unmatched, "unmatched bound [0,1]")
    add("RV13_FANOUT_POSITIVE", fanout > 0, fanout, "fanout >0")

    allowed_t = {
        "IG_ADMITTED", "IG_ADMITTED_EVENTS_PER_SEC", "MSK_CONSUMED", "MSK_CONSUMED_EVENTS_PER_SEC",
        "FLINK_PROCESSED", "FLINK_PROCESSED_EVENTS_PER_SEC", "DECISION_COMMITTED", "DECISION_COMMITTED_EVENTS_PER_SEC",
        "SINK_WRITTEN", "SINK_WRITTEN_EVENTS_PER_SEC",
    }
    steady_s = runtime.get("measurement_surfaces", {}).get("throughput", {}).get("steady_surface")
    burst_s = runtime.get("measurement_surfaces", {}).get("throughput", {}).get("burst_surface")
    start_s = runtime.get("measurement_surfaces", {}).get("latency", {}).get("e2e_start")
    end_s = runtime.get("measurement_surfaces", {}).get("latency", {}).get("e2e_end")
    add("RV14_STEADY_SURFACE", steady_s in allowed_t, steady_s, "canonical throughput surface")
    add("RV15_BURST_SURFACE", burst_s in allowed_t, burst_s, "canonical throughput surface")
    add("RV16_LAT_START", start_s in {"IG_ADMISSION_TS", "MSK_INJECT_TS"}, start_s, "canonical latency start")
    add("RV17_LAT_END", end_s in {"DECISION_COMMIT_TS", "ACTION_COMMIT_TS"}, end_s, "canonical latency end")

    tbd_paths = collect_tbd(runtime)
    add("RV18_NO_TBD", len(tbd_paths) == 0, {"required_tbd_paths": tbd_paths}, "ACTIVE runtime contract must contain no TBD")
    failed = [c for c in checks if not c["pass"]]
    return {"checks": checks, "overall_valid": len(failed) == 0, "failed_checks": failed, "required_tbd_paths": tbd_paths}


def opsgov_validator(opsgov: Dict[str, Any], run_root: Path) -> Tuple[Dict[str, Any], bool]:
    checks: List[Dict[str, Any]] = []

    def add(k: str, ok: bool, obs: Any, why: str) -> None:
        checks.append({"check_id": k, "pass": ok, "observed": obs, "reason": why})

    add("OV01_STATUS_ACTIVE", opsgov.get("status") == "ACTIVE", opsgov.get("status"), "status must be ACTIVE")
    add("OV02_VERSION", is_nonempty_str(opsgov.get("monitoring_baselines_version")), opsgov.get("monitoring_baselines_version"), "version required")
    g2_ref = opsgov.get("source_packs", {}).get("g2_data_realism_pack_ref")
    add("OV03_G2_REF", is_nonempty_str(g2_ref), g2_ref, "G2 source ref required")

    for key in ["window_start_ts_utc", "window_end_ts_utc", "as_of_time_utc", "label_maturity_lag"]:
        v = opsgov.get("window_basis", {}).get(key)
        add(f"OV04_WINDOW_{key}", is_nonempty_str(v), v, "window binding required")

    d = opsgov.get("rules", {}).get("distribution_required", [])
    dset = {str(x).lower() for x in d} if isinstance(d, list) else set()
    add("OV05_DISTRIBUTION_P95_P99", {"p95", "p99"}.issubset(dset), d, "must include p95/p99")
    add("OV06_MISSING_POLICY", opsgov.get("rules", {}).get("missing_metric_policy") == "FAIL_CLOSED", opsgov.get("rules", {}).get("missing_metric_policy"), "missing policy must be FAIL_CLOSED")

    owners = opsgov.get("alerts", {}).get("required_owners_bound", {})
    owner_ok = isinstance(owners, dict) and len(owners) > 0 and all(is_nonempty_str(v) for v in owners.values())
    add("OV07_ALERT_OWNER_BINDINGS", owner_ok, owners, "alert owners must be fully bound")

    req = opsgov.get("runbooks", {}).get("required", [])
    req_ids = {str(x).strip() for x in req if str(x).strip()}
    add("OV08_RUNBOOK_REQUIRED", isinstance(req, list) and len(req_ids) > 0, req, "runbooks.required must be non-empty")
    ref = opsgov.get("runbooks", {}).get("index_ref")
    add("OV09_RUNBOOK_INDEX_REF", is_nonempty_str(ref), ref, "runbook index ref must be set")

    indexed: set[str] = set()
    readable = False
    if is_nonempty_str(ref):
        p = Path(str(ref))
        if not p.exists():
            p = run_root / str(ref)
        if p.exists():
            try:
                idx = load_json(p)
                readable = True
                for r in idx.get("runbooks", []):
                    if isinstance(r, dict):
                        rid = str(r.get("runbook_id", "")).strip()
                        if rid:
                            indexed.add(rid)
            except Exception:
                readable = False
        add("OV10_RUNBOOK_INDEX_READABLE", readable, str(p), "index must be readable")

    missing = sorted(req_ids - indexed)
    owner_keys = {str(k).strip() for k in owners.keys()} if isinstance(owners, dict) else set()
    add("OV11_RUNBOOK_RESOLVED", len(missing) == 0, {"missing": missing}, "all required runbooks must resolve")
    add("OV12_OWNER_FOR_REQUIRED", len(req_ids - owner_keys) == 0, {"missing_owner_for": sorted(req_ids - owner_keys)}, "all required runbooks must have owner")

    tbd_paths = collect_tbd(opsgov)
    add("OV13_NO_TBD", len(tbd_paths) == 0, {"required_tbd_paths": tbd_paths}, "ACTIVE opsgov contract must contain no TBD")
    failed = [c for c in checks if not c["pass"]]
    alert_binding_valid = all(
        c["pass"] for c in checks if c["check_id"] in {"OV07_ALERT_OWNER_BINDINGS", "OV08_RUNBOOK_REQUIRED", "OV09_RUNBOOK_INDEX_REF", "OV10_RUNBOOK_INDEX_READABLE", "OV11_RUNBOOK_RESOLVED", "OV12_OWNER_FOR_REQUIRED"}
    )
    return {"checks": checks, "overall_valid": len(failed) == 0, "failed_checks": failed, "required_tbd_paths": tbd_paths}, alert_binding_valid


def main() -> None:
    ap = argparse.ArgumentParser(description="Execute PR2-S2 activation validation and anti-gaming checks.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr2-execution-id", default="")
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    t0 = time.perf_counter()
    ts = now_utc()
    root = Path(args.run_control_root)
    if not root.exists():
        raise RuntimeError(f"Missing run-control root: {root}")
    eid = args.pr2_execution_id.strip() or str(load_json(root / "pr2_latest.json").get("execution_id", "")).strip()
    if not eid:
        raise RuntimeError("Unable to resolve PR2 execution id")
    run_root = root / eid

    s1 = load_json(run_root / "pr2_s1_execution_receipt.json")
    if str(s1.get("verdict")) != "PR2_S1_READY" or int(s1.get("open_blockers", 1)) != 0:
        raise RuntimeError("Upstream lock failed: PR2-S1 not READY")

    runtime = load_yaml(run_root / "pr2_runtime_numeric_contract.rc2s.active.yaml")
    opsgov = load_yaml(run_root / "pr2_opsgov_numeric_contract.rc2s.active.yaml")
    inventory = load_json(run_root / "pr2_required_row_inventory.json")
    calibration = load_json(run_root / "pr2_calibration_traceability.json")
    deferred = load_json(run_root / "pr2_deferred_scope_register.json")

    rv = runtime_validator(runtime)
    ov, alert_binding = opsgov_validator(opsgov, run_root)

    p95 = to_float(runtime.get("thresholds", {}).get("hot_path_slo", {}).get("decision_latency_ms", {}).get("p95_max"))
    p99 = to_float(runtime.get("thresholds", {}).get("hot_path_slo", {}).get("decision_latency_ms", {}).get("p99_max"))
    err = to_float(runtime.get("thresholds", {}).get("hot_path_slo", {}).get("error_rate_max"))
    unmatched = to_float(runtime.get("sample_minima", {}).get("max_unmatched_join_rate"))
    fanout = to_float(runtime.get("sample_minima", {}).get("max_fanout_p99"))
    budget = to_float(runtime.get("thresholds", {}).get("cost", {}).get("budget_envelope_usd"))
    rec = to_float(runtime.get("load_campaign", {}).get("recovery", {}).get("bound_seconds"))
    soak = to_float(runtime.get("load_campaign", {}).get("soak", {}).get("duration_min")) * 60.0
    cal_rows = {str(r.get("row_id")) for r in calibration.get("rows", []) if isinstance(r, dict)}
    req_rows = {"PR2.R006", "PR2.R007", "PR2.R010", "PR2.R022", "PR2.R023", "PR2.R024", "PR2.R025"}
    ts_checks = [
        {"check_id": "TS01_LATENCY_ORDER", "pass": p95 <= p99, "observed": {"p95": p95, "p99": p99}, "reason": "p95<=p99"},
        {"check_id": "TS02_ERROR_BOUND", "pass": 0 <= err <= 1, "observed": err, "reason": "error bound [0,1]"},
        {"check_id": "TS03_UNMATCHED_BOUND", "pass": 0 <= unmatched <= 1, "observed": unmatched, "reason": "unmatched bound [0,1]"},
        {"check_id": "TS04_FANOUT_POSITIVE", "pass": fanout > 0, "observed": fanout, "reason": "fanout >0"},
        {"check_id": "TS05_RECOVERY_FRACTION", "pass": rec <= 0.25 * soak, "observed": {"recovery_bound_seconds": rec, "soak_seconds": soak}, "reason": "recovery <= 25% soak"},
        {"check_id": "TS06_BUDGET_POSITIVE", "pass": budget > 0, "observed": budget, "reason": "budget >0"},
        {"check_id": "TS07_CALIBRATION_COVERAGE", "pass": req_rows.issubset(cal_rows), "observed": {"required": sorted(req_rows), "present": sorted(cal_rows)}, "reason": "required calibration rows present"},
    ]
    ts_failed = [c for c in ts_checks if not c["pass"]]
    threshold_report = {
        "phase": "PR2",
        "state": "S2",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": eid,
        "checks": ts_checks,
        "overall_pass": len(ts_failed) == 0,
        "failed_checks": ts_failed,
    }

    rows = {str(r.get("row_id")): r for r in inventory.get("rows", []) if isinstance(r, dict)}
    r016 = rows.get("PR2.R016", {}).get("value")
    r017 = rows.get("PR2.R017", {}).get("value")
    d = opsgov.get("rules", {}).get("distribution_required", [])
    dset = {str(x).lower() for x in d} if isinstance(d, list) else set()
    steady_s = runtime.get("measurement_surfaces", {}).get("throughput", {}).get("steady_surface", "")
    burst_s = runtime.get("measurement_surfaces", {}).get("throughput", {}).get("burst_surface", "")
    start_s = runtime.get("measurement_surfaces", {}).get("latency", {}).get("e2e_start", "")
    end_s = runtime.get("measurement_surfaces", {}).get("latency", {}).get("e2e_end", "")
    no_proxy = all(not any(t in str(x).lower() for t in {"proxy", "estimated", "derived"}) for x in [steady_s, burst_s, start_s, end_s])
    cn = runtime.get("constraint_notes", {})
    projected = to_float(cn.get("projected_burst_eps_with_uniform_speedup"))
    target = to_float(cn.get("target_burst_eps"))
    carry_ok = any(
        isinstance(x, dict) and str(x.get("id")) == "PR2.S1.CN01_BURST_SHAPER_REQUIRED" and str(x.get("due_state")) == "PR3-S1"
        for x in deferred.get("carry_forward_constraints", [])
    )
    ag_checks = [
        {"check_id": "AG01_DISTRIBUTION_P50_P95_P99", "pass": {"p50", "p95", "p99"}.issubset(dset), "observed": d, "reason": "distribution requirements include p50/p95/p99"},
        {"check_id": "AG02_NON_PROXY_SURFACES", "pass": no_proxy, "observed": {"steady": steady_s, "burst": burst_s, "start": start_s, "end": end_s}, "reason": "measurement surfaces are non-proxy"},
        {"check_id": "AG03_SAMPLE_MINIMA_NO_DRIFT", "pass": (r016 == runtime.get("sample_minima", {}).get("max_unmatched_join_rate")) and (r017 == runtime.get("sample_minima", {}).get("max_fanout_p99")), "observed": {"inventory_r016": r016, "inventory_r017": r017}, "reason": "sample minima unchanged from S0 inventory"},
        {"check_id": "AG04_BURST_GAP_ROUTED_TO_PR3", "pass": (projected >= target) or (bool(cn.get("requires_burst_shaper_in_pr3")) and carry_ok), "observed": {"projected_burst_eps": projected, "target_burst_eps": target, "carry_forward_present": carry_ok}, "reason": "burst gap explicitly disclosed and routed"},
    ]
    ag_failed = [c for c in ag_checks if not c["pass"]]
    anti_gaming = {"checks": ag_checks, "overall_pass": len(ag_failed) == 0, "failed_checks": ag_failed}
    threshold_report["anti_gaming"] = anti_gaming

    b10 = bool(rv["overall_valid"])
    b11 = bool(ov["overall_valid"])
    b12 = bool(threshold_report["overall_pass"])
    b13 = bool(alert_binding)
    b14 = bool(anti_gaming["overall_pass"])
    blockers: List[str] = []
    if not b10:
        blockers.append("PR2.B10_ENV_NOT_ACTIVATABLE")
    if not b11:
        blockers.append("PR2.B11_BASELINES_NOT_ACTIVATABLE")
    if not b12:
        blockers.append("PR2.B12_THRESHOLD_SANITY_FAIL")
    if not b13:
        blockers.append("PR2.B13_ALERT_RUNBOOK_BINDING_MISSING")
    if not b14:
        blockers.append("PR2.B14_ANTI_GAMING_GUARD_FAIL")

    runtime_payload = {
        "phase": "PR2", "state": "S2", "generated_at_utc": ts, "generated_by": args.generated_by, "version": args.version, "execution_id": eid,
        "contract_ref": "pr2_runtime_numeric_contract.rc2s.active.yaml", **rv
    }
    ops_payload = {
        "phase": "PR2", "state": "S2", "generated_at_utc": ts, "generated_by": args.generated_by, "version": args.version, "execution_id": eid,
        "contract_ref": "pr2_opsgov_numeric_contract.rc2s.active.yaml", **ov, "alert_runbook_binding_valid": alert_binding
    }
    matrix = {
        "phase": "PR2",
        "state": "S2",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": eid,
        "checks": {
            "B10_env_activatable": b10,
            "B11_baselines_activatable": b11,
            "B12_threshold_sanity": b12,
            "B13_alert_runbook_binding": b13,
            "B14_anti_gaming_guard": b14,
        },
        "blocker_ids": blockers,
        "open_blockers": len(blockers),
        "overall_pass": len(blockers) == 0,
        "validator_refs": {
            "runtime_validator": "pr2_runtime_contract_validator.json",
            "opsgov_validator": "pr2_opsgov_contract_validator.json",
            "threshold_sanity": "pr2_threshold_sanity_report.json",
        },
    }
    dump_json(run_root / "pr2_runtime_contract_validator.json", runtime_payload)
    dump_json(run_root / "pr2_opsgov_contract_validator.json", ops_payload)
    dump_json(run_root / "pr2_threshold_sanity_report.json", threshold_report)
    dump_json(run_root / "pr2_activation_validation_matrix.json", matrix)

    receipt = {
        "phase": "PR2",
        "state": "S2",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": eid,
        "verdict": "PR2_S2_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "next_state": "PR2-S3" if len(blockers) == 0 else "PR2-S2",
        "open_blockers": len(blockers),
        "blocker_ids": blockers,
        "checks": matrix["checks"],
        "outputs": [
            "pr2_runtime_contract_validator.json",
            "pr2_opsgov_contract_validator.json",
            "pr2_threshold_sanity_report.json",
            "pr2_activation_validation_matrix.json",
        ],
        "elapsed_minutes": round((time.perf_counter() - t0) / 60.0, 3),
        "runtime_budget_minutes": 20,
        "attributable_spend_usd": 0.0,
        "cost_envelope_usd": 5.0,
        "advisory_ids": ["PR2.S2.AD01_BURST_GAP_EXPLICITLY_ROUTED_TO_PR3"],
    }
    dump_json(run_root / "pr2_s2_execution_receipt.json", receipt)
    dump_json(
        root / "pr2_latest.json",
        {
            "phase": "PR2",
            "execution_id": eid,
            "latest_state": "S2",
            "latest_receipt": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{eid}/pr2_s2_execution_receipt.json",
            "updated_at_utc": now_utc(),
        },
    )

    print(
        json.dumps(
            {
                "execution_id": eid,
                "state": "S2",
                "verdict": receipt["verdict"],
                "next_state": receipt["next_state"],
                "open_blockers": receipt["open_blockers"],
                "blocker_ids": blockers,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
