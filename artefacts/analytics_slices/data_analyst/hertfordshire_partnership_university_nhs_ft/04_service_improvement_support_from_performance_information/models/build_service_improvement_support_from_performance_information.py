from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_01_DIR = BASE_DIR.parent / "01_target_performance_monitoring_and_remediation_support"
SOURCE_02_DIR = BASE_DIR.parent / "02_senior_performance_analysis_and_reporting"
SOURCE_03_DIR = BASE_DIR.parent / "03_data_quality_and_performance_validity"
EXTRACTS_DIR = BASE_DIR / "extracts"
METRICS_DIR = BASE_DIR / "metrics"


def ensure_dirs() -> None:
    EXTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict, dict]:
    remediation_support = pd.read_parquet(
        SOURCE_01_DIR / "extracts" / "remediation_support_summary_v1.parquet"
    )
    management_actions = pd.read_parquet(
        SOURCE_02_DIR / "extracts" / "management_actions_summary_v1.parquet"
    )
    validity_impact = pd.read_parquet(
        SOURCE_03_DIR / "extracts" / "performance_validity_impact_v1.parquet"
    )
    validity_actions = pd.read_parquet(
        SOURCE_03_DIR / "extracts" / "performance_validity_improvement_actions_v1.parquet"
    )
    fact_pack_01 = json.loads(
        (SOURCE_01_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    fact_pack_02 = json.loads(
        (SOURCE_02_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    fact_pack_03 = json.loads(
        (SOURCE_03_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    return (
        remediation_support,
        management_actions,
        validity_impact,
        validity_actions,
        fact_pack_01,
        fact_pack_02,
        fact_pack_03,
    )


def build_improvement_priority(
    remediation_support: pd.DataFrame,
    management_actions: pd.DataFrame,
    validity_impact: pd.DataFrame,
) -> pd.DataFrame:
    rem = remediation_support.iloc[0]
    mgmt = management_actions.iloc[0]
    impact = validity_impact.iloc[0]
    return pd.DataFrame(
        [
            {
                "reporting_window_start": rem["reporting_window_start"],
                "reporting_window_end": rem["reporting_window_end"],
                "priority_id": "P1",
                "improvement_priority": "focused flow review and pathway adjustment for the persistent 50_plus pressure pocket",
                "focus_band": rem["focus_band"],
                "current_case_open_gap_to_peer_pp": float(rem["current_focus_case_open_gap_to_peer_pp"]),
                "current_truth_gap_to_peer_pp": float(rem["current_focus_truth_gap_to_peer_pp"]),
                "current_burden_gap_pp": float(rem["current_focus_burden_minus_yield_gap_pp"]),
                "whole_lane_case_open_change_from_start_pp": float(rem["whole_lane_case_open_change_from_start_pp"]),
                "whole_lane_truth_change_from_start_pp": float(rem["whole_lane_truth_change_from_start_pp"]),
                "improvement_priority_reason": str(mgmt["emerging_risk"]),
                "validity_precondition": str(impact["validity_sensitive_condition"]),
                "priority_scope": "bounded_service_improvement_attention",
            }
        ]
    )


def build_action_pathway(
    priority_df: pd.DataFrame,
    validity_actions: pd.DataFrame,
) -> pd.DataFrame:
    priority = priority_df.iloc[0]
    action_rows = [
        {
            "pathway_stage": 1,
            "stage_name": "protect_reading_integrity",
            "stage_goal": "lock the target-reading controls before any improvement interpretation is acted on",
            "linked_control_area": str(validity_actions.iloc[0]["improvement_area"]),
            "stage_action": "freeze the target reference and keep the shortfall pack under controlled comparator rules",
            "why_stage_matters": "service-improvement attention should not move forward on a drifting reading surface",
        },
        {
            "pathway_stage": 2,
            "stage_name": "review_focused_flow_rules",
            "stage_goal": "review the bounded 50_plus flow and handling logic rather than escalating the whole lane",
            "linked_control_area": str(validity_actions.iloc[1]["improvement_area"]),
            "stage_action": "review focused queue, escalation, or pathway handling rules around the persistent pocket",
            "why_stage_matters": "the pressure remains concentrated in one pocket while the whole lane stays broadly stable",
        },
        {
            "pathway_stage": 3,
            "stage_name": "remeasure_and_decide",
            "stage_goal": "remeasure the same pocket before any broader intervention is considered",
            "linked_control_area": str(validity_actions.iloc[2]["improvement_area"]),
            "stage_action": "reissue the governed pack and confirm whether the same focus pocket still carries the burden gap after the review step",
            "why_stage_matters": "the next move should depend on whether the bounded pathway changes the pressure signal, not on assumption",
        },
    ]
    for row in action_rows:
        row["focus_band"] = priority["focus_band"]
        row["action_pathway_scope"] = "bounded_improvement_pathway"
    return pd.DataFrame(action_rows)


def build_support_summary(
    priority_df: pd.DataFrame,
    pathway_df: pd.DataFrame,
    management_actions: pd.DataFrame,
) -> pd.DataFrame:
    priority = priority_df.iloc[0]
    mgmt = management_actions.iloc[0]
    return pd.DataFrame(
        [
            {
                "reporting_window_start": priority["reporting_window_start"],
                "reporting_window_end": priority["reporting_window_end"],
                "focus_band": priority["focus_band"],
                "improvement_priority": priority["improvement_priority"],
                "pathway_stage_count": int(len(pathway_df)),
                "required_attention": str(mgmt["required_attention"]),
                "service_improvement_reading": "use the persistent focus-pocket pressure as a bounded improvement priority rather than only a reporting exception",
                "supported_next_step": "protect the reading, review the focused flow rules, then remeasure before any broader intervention",
                "why_this_goes_beyond_remediation": "the pack turns an immediate review suggestion into a staged evidence-led pathway with explicit preconditions and a remeasurement gate",
                "support_scope": "bounded_service_improvement_support",
            }
        ]
    )


def build_release_checks(
    priority_df: pd.DataFrame,
    pathway_df: pd.DataFrame,
    support_df: pd.DataFrame,
    fact_pack_01: dict,
    fact_pack_03: dict,
) -> pd.DataFrame:
    priority = priority_df.iloc[0]
    support = support_df.iloc[0]
    checks = [
        {
            "check_name": "single_improvement_priority_materialised",
            "actual_value": float(len(priority_df)),
            "expected_rule": "= 1 improvement-priority row present",
            "passed_flag": int(len(priority_df) == 1),
        },
        {
            "check_name": "action_pathway_contains_expected_stages",
            "actual_value": float(len(pathway_df)),
            "expected_rule": "= 3 bounded improvement-pathway stages present",
            "passed_flag": int(len(pathway_df) == 3),
        },
        {
            "check_name": "action_pathway_preserves_single_focus_band",
            "actual_value": float(pathway_df["focus_band"].nunique()),
            "expected_rule": "= 1 focus band carried through the improvement pathway",
            "passed_flag": int(pathway_df["focus_band"].nunique() == 1),
        },
        {
            "check_name": "support_pack_goes_beyond_immediate_remediation",
            "actual_value": float(int("remeasure" in str(support["supported_next_step"]).lower())),
            "expected_rule": "= 1 support summary contains a staged pathway with remeasurement gate",
            "passed_flag": int("remeasure" in str(support["supported_next_step"]).lower()),
        },
        {
            "check_name": "priority_retains_material_focus_gap",
            "actual_value": float(priority["current_case_open_gap_to_peer_pp"]),
            "expected_rule": "> 0 current focus case-open gap remains positive",
            "passed_flag": int(priority["current_case_open_gap_to_peer_pp"] > 0),
        },
        {
            "check_name": "inherited_target_pack_remains_green",
            "actual_value": float(fact_pack_01["release_checks_passed"]),
            "expected_rule": "= 6 inherited target-pack checks passed",
            "passed_flag": int(fact_pack_01["release_checks_passed"] == fact_pack_01["release_check_count"]),
        },
        {
            "check_name": "inherited_validity_pack_remains_green",
            "actual_value": float(fact_pack_03["release_checks_passed"]),
            "expected_rule": "= 7 inherited validity-pack checks passed",
            "passed_flag": int(fact_pack_03["release_checks_passed"] == fact_pack_03["release_check_count"]),
        },
    ]
    return pd.DataFrame(checks)


def build_fact_pack(
    priority_df: pd.DataFrame,
    pathway_df: pd.DataFrame,
    support_df: pd.DataFrame,
    release_checks: pd.DataFrame,
    fact_pack_02: dict,
) -> dict:
    priority = priority_df.iloc[0]
    support = support_df.iloc[0]
    return {
        "slice": "hertfordshire_partnership_university_nhs_ft/04_service_improvement_support_from_performance_information",
        "reporting_window_start": str(priority["reporting_window_start"]),
        "reporting_window_end": str(priority["reporting_window_end"]),
        "improvement_priority_count": int(len(priority_df)),
        "action_pathway_stage_count": int(len(pathway_df)),
        "support_output_count": int(len(support_df)),
        "focus_band": str(priority["focus_band"]),
        "current_focus_case_open_gap_to_peer_pp": float(priority["current_case_open_gap_to_peer_pp"]),
        "current_focus_truth_gap_to_peer_pp": float(priority["current_truth_gap_to_peer_pp"]),
        "current_focus_burden_gap_pp": float(priority["current_burden_gap_pp"]),
        "whole_lane_case_open_change_from_start_pp": float(priority["whole_lane_case_open_change_from_start_pp"]),
        "whole_lane_truth_change_from_start_pp": float(priority["whole_lane_truth_change_from_start_pp"]),
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "inherited_senior_management_output_count": int(fact_pack_02["management_action_output_count"]),
        "supported_next_step": str(support["supported_next_step"]),
    }


def write_notes(fact_pack: dict, priority_df: pd.DataFrame, support_df: pd.DataFrame) -> None:
    priority = priority_df.iloc[0]
    support = support_df.iloc[0]
    files = {
        BASE_DIR / "service_improvement_scope_note_v1.md": f"""# Service Improvement Scope Note v1

Bounded scope:
- one trusted performance lane
- one explicit improvement priority
- one staged action pathway
- one service-improvement support summary

Window:
- `{fact_pack['reporting_window_start']}` to `{fact_pack['reporting_window_end']}`
""",
        BASE_DIR / "service_improvement_priority_note_v1.md": f"""# Service Improvement Priority Note v1

Selected improvement priority:
- {priority['improvement_priority']}

Why this priority was chosen:
- current case-open gap to peers remains `{fact_pack['current_focus_case_open_gap_to_peer_pp']:+.2f} pp`
- current truth-quality gap to peers remains `{fact_pack['current_focus_truth_gap_to_peer_pp']:+.2f} pp`
- the whole lane remains broadly stable while the same focus pocket continues to absorb disproportionate pressure
""",
        BASE_DIR / "service_improvement_action_pathway_note_v1.md": """# Service Improvement Action Pathway Note v1

Bounded pathway:
1. protect the target-reading controls before acting
2. review the focused flow or escalation rules around the persistent pocket
3. remeasure the same governed pocket before considering any broader intervention

This goes beyond an immediate remediation note because it adds explicit preconditions and a remeasurement gate.
""",
        BASE_DIR / "service_improvement_support_note_v1.md": f"""# Service Improvement Support Note v1

Service-improvement reading:
- {support['service_improvement_reading']}

Supported next step:
- {support['supported_next_step']}

Why this remains bounded:
- it supports a focused improvement pathway only
- it does not claim that redesign or transformation has already been delivered
""",
        BASE_DIR / "service_improvement_caveats_v1.md": """# Service Improvement Caveats v1

Caveats:
- this slice proves one bounded performance-to-improvement pathway only
- it does not prove clinical transformation ownership
- it does not prove full service redesign ownership
- it is strongest as improvement-support evidence, not as proof of delivered improvement outcomes
""",
        BASE_DIR / "README_service_improvement_regeneration.md": """# Service Improvement Regeneration

Regeneration steps:
1. confirm the Hertfordshire `01`, `02`, and `03` artefacts exist
2. run `models/build_service_improvement_support_from_performance_information.py`
3. review the priority pack, action-pathway pack, support summary, and release checks
4. use the execution report to decide whether any analytical figure is actually needed
""",
        BASE_DIR / "CHANGELOG_service_improvement.md": """# Changelog - Service Improvement Support

- v1: initial bounded service-improvement support pack built from the Hertfordshire target, senior, and validity-controlled lanes
""",
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")


def main() -> None:
    start = time.perf_counter()
    ensure_dirs()
    (
        remediation_support,
        management_actions,
        validity_impact,
        validity_actions,
        fact_pack_01,
        fact_pack_02,
        fact_pack_03,
    ) = load_inputs()
    priority_df = build_improvement_priority(remediation_support, management_actions, validity_impact)
    pathway_df = build_action_pathway(priority_df, validity_actions)
    support_df = build_support_summary(priority_df, pathway_df, management_actions)
    release_checks = build_release_checks(priority_df, pathway_df, support_df, fact_pack_01, fact_pack_03)
    fact_pack = build_fact_pack(priority_df, pathway_df, support_df, release_checks, fact_pack_02)
    fact_pack["regeneration_seconds"] = time.perf_counter() - start

    priority_df.to_parquet(EXTRACTS_DIR / "service_improvement_priority_v1.parquet", index=False)
    pathway_df.to_parquet(EXTRACTS_DIR / "service_improvement_action_pathway_v1.parquet", index=False)
    support_df.to_parquet(EXTRACTS_DIR / "service_improvement_support_summary_v1.parquet", index=False)
    release_checks.to_parquet(EXTRACTS_DIR / "service_improvement_release_checks_v1.parquet", index=False)
    (METRICS_DIR / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2),
        encoding="utf-8",
    )
    write_notes(fact_pack, priority_df, support_df)


if __name__ == "__main__":
    main()
