#!/usr/bin/env python3
"""Deterministic PR2-S0 executor for road_to_prod (dev_full)."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def add_row(
    rows: List[Dict[str, Any]],
    row_id: str,
    contract: str,
    field_path: str,
    required: bool,
    status: str,
    owner_lane: str,
    due_state: str,
    value: Any = None,
    value_source_ref: str = "",
    notes: str = "",
) -> None:
    rows.append(
        {
            "row_id": row_id,
            "contract": contract,
            "field_path": field_path,
            "required": required,
            "status": status,
            "owner_lane": owner_lane,
            "due_state": due_state,
            "value": value,
            "value_source_ref": value_source_ref,
            "notes": notes,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute PR2-S0 inventory and gap mapping from PR1 closure.")
    parser.add_argument(
        "--run-control-root",
        default="runs/dev_substrate/dev_full/road_to_prod/run_control",
        help="Road-to-prod run control root.",
    )
    parser.add_argument(
        "--upstream-pr1-execution-id",
        default="",
        help="Optional PR1 execution id. If empty, resolve from pr1_latest.json.",
    )
    parser.add_argument("--pr2-execution-id", default="", help="Optional PR2 execution id; auto-generated if empty.")
    parser.add_argument("--generated-by", default="codex-gpt5")
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()

    t0 = time.perf_counter()
    generated_at = utc_now_iso()

    run_control_root = Path(args.run_control_root)
    if not run_control_root.exists():
        raise RuntimeError(f"Run control root does not exist: {run_control_root}")

    if args.upstream_pr1_execution_id:
        pr1_execution_id = args.upstream_pr1_execution_id
    else:
        pr1_latest = load_json(run_control_root / "pr1_latest.json")
        pr1_execution_id = str(pr1_latest.get("execution_id", "")).strip()
        if not pr1_execution_id:
            raise RuntimeError("Unable to resolve PR1 execution id from pr1_latest.json")

    pr1_root = run_control_root / pr1_execution_id
    pr1_s5 = load_json(pr1_root / "pr1_s5_execution_receipt.json")
    pr1_summary = load_json(pr1_root / "pr1_execution_summary.json")
    g2_pack = load_json(pr1_root / "g2_data_realism_pack_index.json")
    cohort = load_json(pr1_root / "pr1_g2_cohort_profile.json")
    join_matrix = load_json(pr1_root / "pr1_join_matrix.json")
    late_policy = load_json(pr1_root / "pr1_late_event_policy_receipt.json")
    monitoring = load_json(pr1_root / "g2_monitoring_baselines.json")

    upstream_ready = (
        str(pr1_s5.get("verdict", "")) == "PR1_S5_READY"
        and int(pr1_s5.get("open_blockers", 1)) == 0
    )

    pr2_execution_id = args.pr2_execution_id.strip() or f"pr2_{utc_stamp()}"
    pr2_root = run_control_root / pr2_execution_id
    pr2_root.mkdir(parents=True, exist_ok=True)

    window_basis = g2_pack.get("window_basis", {})
    envelope = g2_pack.get("activated_rc2s_envelope", {})
    numeric = envelope.get("numeric_set", {})
    surfaces = envelope.get("measurement_surfaces", {})
    cohort_min = cohort.get("cohort_minima", {})
    join_thr = join_matrix.get("thresholds", {})
    monitoring_window = monitoring.get("window_basis", {})

    rows: List[Dict[str, Any]] = []
    # Runtime RC2-S required rows (prefilled where PR1 pinned, pending where PR2-S1 must decide).
    add_row(
        rows,
        "PR2.R001",
        "runtime_rc2s",
        "mission_binding.window_start_ts_utc",
        True,
        "prefilled",
        "runtime_perf",
        "S0",
        value=window_basis.get("window_start_ts_utc"),
        value_source_ref="g2_data_realism_pack_index.json#window_basis.window_start_ts_utc",
    )
    add_row(
        rows,
        "PR2.R002",
        "runtime_rc2s",
        "mission_binding.window_end_ts_utc",
        True,
        "prefilled",
        "runtime_perf",
        "S0",
        value=window_basis.get("window_end_ts_utc"),
        value_source_ref="g2_data_realism_pack_index.json#window_basis.window_end_ts_utc",
    )
    add_row(
        rows,
        "PR2.R003",
        "runtime_rc2s",
        "mission_binding.as_of_time_utc",
        True,
        "prefilled",
        "runtime_perf",
        "S0",
        value=window_basis.get("as_of_time_utc"),
        value_source_ref="g2_data_realism_pack_index.json#window_basis.as_of_time_utc",
    )
    add_row(
        rows,
        "PR2.R004",
        "runtime_rc2s",
        "mission_binding.label_maturity_lag",
        True,
        "prefilled",
        "learning_truth",
        "S0",
        value=f"{numeric.get('label_maturity_lag_days')}d",
        value_source_ref="g2_data_realism_pack_index.json#activated_rc2s_envelope.numeric_set.label_maturity_lag_days",
    )
    add_row(
        rows,
        "PR2.R005",
        "runtime_rc2s",
        "injection_path.mode",
        True,
        "prefilled",
        "runtime_perf",
        "S0",
        value=window_basis.get("injection_path_mode"),
        value_source_ref="g2_data_realism_pack_index.json#window_basis.injection_path_mode",
    )
    add_row(
        rows,
        "PR2.R006",
        "runtime_rc2s",
        "load_campaign.steady.rate_eps",
        True,
        "prefilled",
        "runtime_perf",
        "S0",
        value=numeric.get("steady_rate_eps"),
        value_source_ref="g2_data_realism_pack_index.json#activated_rc2s_envelope.numeric_set.steady_rate_eps",
    )
    add_row(
        rows,
        "PR2.R007",
        "runtime_rc2s",
        "load_campaign.burst.rate_eps",
        True,
        "prefilled",
        "runtime_perf",
        "S0",
        value=numeric.get("burst_rate_eps"),
        value_source_ref="g2_data_realism_pack_index.json#activated_rc2s_envelope.numeric_set.burst_rate_eps",
    )
    add_row(
        rows,
        "PR2.R008",
        "runtime_rc2s",
        "load_campaign.steady.duration_min",
        True,
        "prefilled",
        "runtime_perf",
        "S0",
        value=numeric.get("steady_duration_min"),
        value_source_ref="g2_data_realism_pack_index.json#activated_rc2s_envelope.numeric_set.steady_duration_min",
    )
    add_row(
        rows,
        "PR2.R009",
        "runtime_rc2s",
        "load_campaign.burst.duration_min",
        True,
        "prefilled",
        "runtime_perf",
        "S0",
        value=numeric.get("burst_duration_min"),
        value_source_ref="g2_data_realism_pack_index.json#activated_rc2s_envelope.numeric_set.burst_duration_min",
    )
    add_row(
        rows,
        "PR2.R010",
        "runtime_rc2s",
        "load_campaign.recovery.bound_seconds",
        True,
        "pending_fill",
        "runtime_perf",
        "S1",
        notes="Requires policy target/guardband pinning for recovery bound.",
    )
    add_row(
        rows,
        "PR2.R011",
        "runtime_rc2s",
        "load_campaign.soak.duration_min",
        True,
        "prefilled",
        "runtime_perf",
        "S0",
        value=numeric.get("soak_duration_min"),
        value_source_ref="g2_data_realism_pack_index.json#activated_rc2s_envelope.numeric_set.soak_duration_min",
    )
    add_row(
        rows,
        "PR2.R012",
        "runtime_rc2s",
        "cohorts.duplicates.min_duplicate_attempt_rate",
        True,
        "prefilled",
        "data_realism",
        "S0",
        value=cohort_min.get("duplicate_replay", {}).get("min_pct"),
        value_source_ref="pr1_g2_cohort_profile.json#cohort_minima.duplicate_replay.min_pct",
    )
    add_row(
        rows,
        "PR2.R013",
        "runtime_rc2s",
        "cohorts.out_of_order.min_late_event_rate",
        True,
        "prefilled",
        "data_realism",
        "S0",
        value=cohort_min.get("late_out_of_order", {}).get("min_pct"),
        value_source_ref="pr1_g2_cohort_profile.json#cohort_minima.late_out_of_order.min_pct",
    )
    add_row(
        rows,
        "PR2.R014",
        "runtime_rc2s",
        "cohorts.out_of_order.allowed_lateness_seconds",
        True,
        "prefilled",
        "rtdl_semantics",
        "S0",
        value=late_policy.get("policy", {}).get("allowed_lateness_seconds"),
        value_source_ref="pr1_late_event_policy_receipt.json#policy.allowed_lateness_seconds",
    )
    add_row(
        rows,
        "PR2.R015",
        "runtime_rc2s",
        "cohorts.hot_keys.top_0_1pct_volume_share_min",
        True,
        "prefilled",
        "data_realism",
        "S0",
        value=cohort_min.get("hotkey_skew", {}).get("top1_min_pct"),
        value_source_ref="pr1_g2_cohort_profile.json#cohort_minima.hotkey_skew.top1_min_pct",
    )
    add_row(
        rows,
        "PR2.R016",
        "runtime_rc2s",
        "sample_minima.max_unmatched_join_rate",
        True,
        "prefilled",
        "data_realism",
        "S0",
        value=join_thr.get("max_unmatched_join_rate", {}).get("value"),
        value_source_ref="pr1_join_matrix.json#thresholds.max_unmatched_join_rate.value",
    )
    add_row(
        rows,
        "PR2.R017",
        "runtime_rc2s",
        "sample_minima.max_fanout_p99",
        True,
        "prefilled",
        "data_realism",
        "S0",
        value=join_thr.get("max_fanout_p99", {}).get("value"),
        value_source_ref="pr1_join_matrix.json#thresholds.max_fanout_p99.value",
    )
    add_row(
        rows,
        "PR2.R018",
        "runtime_rc2s",
        "measurement_surfaces.throughput.steady_surface",
        True,
        "prefilled",
        "runtime_perf",
        "S0",
        value=surfaces.get("steady_rate_surface"),
        value_source_ref="g2_data_realism_pack_index.json#activated_rc2s_envelope.measurement_surfaces.steady_rate_surface",
    )
    add_row(
        rows,
        "PR2.R019",
        "runtime_rc2s",
        "measurement_surfaces.throughput.burst_surface",
        True,
        "prefilled",
        "runtime_perf",
        "S0",
        value=surfaces.get("burst_rate_surface"),
        value_source_ref="g2_data_realism_pack_index.json#activated_rc2s_envelope.measurement_surfaces.burst_rate_surface",
    )
    add_row(
        rows,
        "PR2.R020",
        "runtime_rc2s",
        "measurement_surfaces.latency.e2e_start",
        True,
        "pending_fill",
        "runtime_perf",
        "S1",
        notes="Must be pinned to IG_ADMISSION_TS or MSK_INJECT_TS per injection mode and claim scope.",
    )
    add_row(
        rows,
        "PR2.R021",
        "runtime_rc2s",
        "measurement_surfaces.latency.e2e_end",
        True,
        "pending_fill",
        "runtime_perf",
        "S1",
        notes="Must be pinned to DECISION_COMMIT_TS or ACTION_COMMIT_TS for hot-path claim.",
    )
    add_row(
        rows,
        "PR2.R022",
        "runtime_rc2s",
        "thresholds.hot_path_slo.decision_latency_ms.p95_max",
        True,
        "pending_fill",
        "runtime_perf",
        "S1",
    )
    add_row(
        rows,
        "PR2.R023",
        "runtime_rc2s",
        "thresholds.hot_path_slo.decision_latency_ms.p99_max",
        True,
        "pending_fill",
        "runtime_perf",
        "S1",
    )
    add_row(
        rows,
        "PR2.R024",
        "runtime_rc2s",
        "thresholds.hot_path_slo.error_rate_max",
        True,
        "pending_fill",
        "runtime_perf",
        "S1",
    )
    add_row(
        rows,
        "PR2.R025",
        "runtime_rc2s",
        "thresholds.cost.budget_envelope_usd",
        True,
        "pending_fill",
        "cost_governance",
        "S1",
    )

    # Ops/Gov baseline required rows.
    add_row(
        rows,
        "PR2.O001",
        "opsgov_rc2s",
        "source_packs.g2_data_realism_pack_ref",
        True,
        "prefilled",
        "ops_gov_observability",
        "S0",
        value=f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr1_execution_id}/g2_data_realism_pack_index.json",
        value_source_ref="pr1_execution_summary.json#evidence_refs.g2_data_realism_pack_index",
    )
    add_row(
        rows,
        "PR2.O002",
        "opsgov_rc2s",
        "window_basis.window_start_ts_utc",
        True,
        "prefilled",
        "ops_gov_observability",
        "S0",
        value=monitoring_window.get("window_start_ts_utc"),
        value_source_ref="g2_monitoring_baselines.json#window_basis.window_start_ts_utc",
    )
    add_row(
        rows,
        "PR2.O003",
        "opsgov_rc2s",
        "window_basis.window_end_ts_utc",
        True,
        "prefilled",
        "ops_gov_observability",
        "S0",
        value=monitoring_window.get("window_end_ts_utc"),
        value_source_ref="g2_monitoring_baselines.json#window_basis.window_end_ts_utc",
    )
    add_row(
        rows,
        "PR2.O004",
        "opsgov_rc2s",
        "window_basis.as_of_time_utc",
        True,
        "prefilled",
        "ops_gov_observability",
        "S0",
        value=monitoring_window.get("as_of_time_utc"),
        value_source_ref="g2_monitoring_baselines.json#window_basis.as_of_time_utc",
    )
    add_row(
        rows,
        "PR2.O005",
        "opsgov_rc2s",
        "window_basis.label_maturity_lag",
        True,
        "prefilled",
        "learning_truth",
        "S0",
        value=monitoring_window.get("label_maturity_lag"),
        value_source_ref="g2_monitoring_baselines.json#window_basis.label_maturity_lag",
    )
    add_row(
        rows,
        "PR2.O006",
        "opsgov_rc2s",
        "rules.distribution_required",
        True,
        "prefilled",
        "ops_gov_observability",
        "S0",
        value=monitoring.get("rules", {}).get("distribution_required"),
        value_source_ref="g2_monitoring_baselines.json#rules.distribution_required",
    )
    add_row(
        rows,
        "PR2.O007",
        "opsgov_rc2s",
        "rules.missing_metric_policy",
        True,
        "prefilled",
        "ops_gov_observability",
        "S0",
        value=monitoring.get("rules", {}).get("missing_metric_policy"),
        value_source_ref="g2_monitoring_baselines.json#rules.missing_metric_policy",
    )
    add_row(
        rows,
        "PR2.O008",
        "opsgov_rc2s",
        "alerts.required_owners_bound",
        True,
        "pending_fill",
        "ops_gov_observability",
        "S1",
        notes="Populate required alert owner bindings for active metric families.",
    )
    add_row(
        rows,
        "PR2.O009",
        "opsgov_rc2s",
        "runbooks.index_ref",
        True,
        "pending_fill",
        "ops_gov_observability",
        "S1",
        notes="Required by C.1 validator checklist.",
    )
    add_row(
        rows,
        "PR2.O010",
        "opsgov_rc2s",
        "source_packs.g3a_runtime_pack_ref",
        False,
        "deferred_out_of_scope",
        "runtime_perf",
        "PR3",
        notes="Optional in C.1 at PR2 stage; to be set during PR3 closure.",
    )
    add_row(
        rows,
        "PR2.O011",
        "opsgov_rc2s",
        "source_packs.g3b_ops_gov_pack_ref",
        False,
        "deferred_out_of_scope",
        "ops_gov_observability",
        "PR4",
        notes="Optional in C.1 at PR2 stage; to be set during PR4 closure.",
    )

    required_rows = [r for r in rows if r.get("required")]
    pending_required = [r for r in required_rows if r.get("status") == "pending_fill"]
    owner_gaps = [
        r["row_id"]
        for r in pending_required
        if not str(r.get("owner_lane", "")).strip() or not str(r.get("due_state", "")).strip()
    ]

    b01_entry_lock = True
    b02_upstream_ready = upstream_ready
    b03_inventory_present = len(required_rows) > 0 and len(rows) > 0
    b04_owner_gaps = len(owner_gaps) == 0

    blockers: List[str] = []
    if not b01_entry_lock:
        blockers.append("PR2.B01_ENTRY_LOCK_MISSING")
    if not b02_upstream_ready:
        blockers.append("PR2.B02_UPSTREAM_PR1_NOT_READY")
    if not b03_inventory_present:
        blockers.append("PR2.B03_REQUIRED_ROW_INVENTORY_MISSING")
    if not b04_owner_gaps:
        blockers.append("PR2.B04_REQUIRED_ROW_OWNER_GAP")

    entry_lock = {
        "phase": "PR2",
        "state": "S0",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr2_execution_id,
        "upstream": {
            "pr1_execution_id": pr1_execution_id,
            "required_receipt": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr1_execution_id}/pr1_s5_execution_receipt.json",
            "required_verdict": "PR1_S5_READY",
        },
        "authorities": [
            "docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md",
            "docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.PR2.road_to_prod.md",
            "docs/model_spec/platform/pre-design_decisions/dev-full_road-to-production-ready.md",
            "docs/model_spec/data-engine/interface_pack/",
        ],
        "strict_upstream_ready": b02_upstream_ready,
    }

    required_inventory = {
        "phase": "PR2",
        "state": "S0",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr2_execution_id,
        "active_scope": "RC2-S required numeric contract rows only",
        "source_refs": {
            "pr1_summary": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr1_execution_id}/pr1_execution_summary.json",
            "g2_pack": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr1_execution_id}/g2_data_realism_pack_index.json",
            "g2_baselines": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr1_execution_id}/g2_monitoring_baselines.json",
            "authority_a1_c1": "docs/model_spec/platform/pre-design_decisions/dev-full_road-to-production-ready.md",
        },
        "summary": {
            "row_count_total": len(rows),
            "row_count_required": len(required_rows),
            "row_count_prefilled_required": len([r for r in required_rows if r["status"] == "prefilled"]),
            "row_count_pending_required": len(pending_required),
            "row_count_deferred_optional": len(
                [r for r in rows if (not r["required"]) and r["status"] == "deferred_out_of_scope"]
            ),
        },
        "rows": rows,
    }

    pending_by_state: Dict[str, List[str]] = {}
    pending_by_owner: Dict[str, List[str]] = {}
    for row in pending_required:
        due = str(row["due_state"])
        owner = str(row["owner_lane"])
        pending_by_state.setdefault(due, []).append(row["row_id"])
        pending_by_owner.setdefault(owner, []).append(row["row_id"])

    gap_map = {
        "phase": "PR2",
        "state": "S0",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr2_execution_id,
        "required_pending_rows": pending_required,
        "required_pending_count": len(pending_required),
        "required_pending_by_due_state": pending_by_state,
        "required_pending_by_owner_lane": pending_by_owner,
        "owner_gap_row_ids": owner_gaps,
        "deferred_optional_rows": [
            r for r in rows if (not r["required"]) and r["status"] == "deferred_out_of_scope"
        ],
    }

    elapsed_minutes = round((time.perf_counter() - t0) / 60.0, 3)
    open_blockers = len(blockers)
    overall_pass = open_blockers == 0
    receipt = {
        "phase": "PR2",
        "state": "S0",
        "generated_at_utc": generated_at,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr2_execution_id,
        "verdict": "PR2_S0_READY" if overall_pass else "HOLD_REMEDIATE",
        "next_state": "PR2-S1" if overall_pass else "PR2-S0",
        "open_blockers": open_blockers,
        "blocker_ids": blockers,
        "outputs": [
            "pr2_entry_lock.json",
            "pr2_required_row_inventory.json",
            "pr2_gap_map.json",
        ],
        "checks": {
            "B01_entry_lock_present": b01_entry_lock,
            "B02_upstream_pr1_ready": b02_upstream_ready,
            "B03_required_inventory_present": b03_inventory_present,
            "B04_required_pending_owner_bound": b04_owner_gaps,
        },
        "tgt_updates": [],
        "elapsed_minutes": elapsed_minutes,
        "runtime_budget_minutes": 10,
        "attributable_spend_usd": 0.0,
        "cost_envelope_usd": 2.0,
        "advisory_ids": ["PR1.S4.AD01_LABEL_TS_PROXY_SEMANTICS"],
    }

    dump_json(pr2_root / "pr2_entry_lock.json", entry_lock)
    dump_json(pr2_root / "pr2_required_row_inventory.json", required_inventory)
    dump_json(pr2_root / "pr2_gap_map.json", gap_map)
    dump_json(pr2_root / "pr2_s0_execution_receipt.json", receipt)

    latest = {
        "phase": "PR2",
        "execution_id": pr2_execution_id,
        "latest_state": "S0",
        "latest_receipt": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr2_execution_id}/pr2_s0_execution_receipt.json",
        "updated_at_utc": utc_now_iso(),
    }
    dump_json(run_control_root / "pr2_latest.json", latest)

    print(
        json.dumps(
            {
                "execution_id": pr2_execution_id,
                "state": "S0",
                "verdict": receipt["verdict"],
                "next_state": receipt["next_state"],
                "open_blockers": open_blockers,
                "blocker_ids": blockers,
                "required_rows": len(required_rows),
                "pending_required_rows": len(pending_required),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
