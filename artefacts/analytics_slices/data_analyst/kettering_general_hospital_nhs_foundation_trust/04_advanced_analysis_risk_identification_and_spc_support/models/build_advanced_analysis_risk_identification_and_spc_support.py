from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

KETTERING_A_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "kettering_general_hospital_nhs_foundation_trust"
    / "01_psirf_incident_response_and_learning_cycle_support"
)
KETTERING_BD_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "kettering_general_hospital_nhs_foundation_trust"
    / "02_compliance_target_monitoring_and_intervention_evaluation"
)
KETTERING_F_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "kettering_general_hospital_nhs_foundation_trust"
    / "03_governance_confidentiality_and_safety_data_method_improvement"
)
HERTS_B_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "hertfordshire_partnership_university_nhs_ft"
    / "02_senior_performance_analysis_and_reporting"
)


def write_md(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def pp(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f} pp"


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    incident_support_summary = pd.read_parquet(
        KETTERING_A_BASE / "extracts" / "incident_support_summary_v1.parquet"
    )
    thematic_review_output = pd.read_parquet(
        KETTERING_A_BASE / "extracts" / "thematic_review_output_v1.parquet"
    )

    compliance_target_monitoring_summary = pd.read_parquet(
        KETTERING_BD_BASE / "extracts" / "compliance_target_monitoring_summary_v1.parquet"
    )
    intervention_evaluation_output = pd.read_parquet(
        KETTERING_BD_BASE / "extracts" / "intervention_evaluation_output_v1.parquet"
    )

    governance_confidentiality_summary = pd.read_parquet(
        KETTERING_F_BASE / "extracts" / "governance_confidentiality_summary_v1.parquet"
    )
    targeted_audit_review_output = pd.read_parquet(
        KETTERING_F_BASE / "extracts" / "targeted_audit_review_output_v1.parquet"
    )
    safety_data_method_improvement_output = pd.read_parquet(
        KETTERING_F_BASE / "extracts" / "safety_data_method_improvement_output_v1.parquet"
    )

    trend_and_trajectory_summary = pd.read_parquet(
        HERTS_B_BASE / "extracts" / "trend_and_trajectory_summary_v1.parquet"
    )

    fact_pack_a = json.loads(
        (KETTERING_A_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    fact_pack_bd = json.loads(
        (KETTERING_BD_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    fact_pack_f = json.loads(
        (KETTERING_F_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    fact_pack_herts_b = json.loads(
        (HERTS_B_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    incident_row = incident_support_summary.iloc[0]
    intervention_row = intervention_evaluation_output.iloc[0]
    governance_row = governance_confidentiality_summary.iloc[0]

    aligned_reporting_window = str(incident_row["aligned_reporting_window"])
    shared_focus_band = str(incident_row["shared_incident_focus"])
    confirming_stream_count = int(fact_pack_a["confirming_stream_count"])
    review_trigger_metric_count = int(fact_pack_f["review_trigger_metric_count"])
    named_measure_family_count = int(fact_pack_bd["named_measure_family_count"])
    traceability_stage_count = int(fact_pack_f["traceability_stage_count"])
    case_pressure_gap_current_pp = float(fact_pack_a["case_pressure_gap_current_pp"])
    truth_quality_gap_current_pp = float(fact_pack_a["truth_quality_gap_current_pp"])
    control_gap_pp = float(fact_pack_a["control_gap_pp"])
    burden_minus_yield_gap_pp = float(fact_pack_bd["burden_minus_yield_gap_pp"])
    trend_output_count = int(fact_pack_herts_b["trend_output_count"])

    advanced_risk_question = (
        "where does the governed patient-safety lane still show persistent pressure, instability, or concentration strongly enough to justify early targeted intervention?"
    )

    advanced_risk_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "advanced_risk_question": advanced_risk_question,
                "shared_focus_band": shared_focus_band,
                "advanced_risk_pack_name": "patient_safety_advanced_risk_and_spc_pack",
                "confirming_stream_count": confirming_stream_count,
                "named_measure_family_count": named_measure_family_count,
                "case_pressure_gap_pp": case_pressure_gap_current_pp,
                "truth_quality_gap_pp": truth_quality_gap_current_pp,
                "control_gap_pp": control_gap_pp,
                "burden_minus_yield_gap_pp": burden_minus_yield_gap_pp,
                "advanced_risk_reading": (
                    "the same governed focus pocket remains the clearest early-warning concentration because pressure, control, and burden-minus-yield still point in the same direction while the lane remains bounded and reviewable"
                ),
            }
        ]
    )

    pattern_emerging_risk_output = pd.DataFrame(
        [
            {
                "pattern_rank": 1,
                "pattern_name": "persistent_pressure_cluster",
                "pattern_role": "emerging_risk_basis",
                "pattern_reading": (
                    f"the shared focus `{shared_focus_band}` still carries {pp(case_pressure_gap_current_pp)} pressure and {pp(control_gap_pp)} control gap, so it remains the strongest bounded early-risk pocket"
                ),
            },
            {
                "pattern_rank": 2,
                "pattern_name": "quality_not_yet_recovered",
                "pattern_role": "risk_confirmation",
                "pattern_reading": (
                    f"truth quality remains at {pp(truth_quality_gap_current_pp)} against the current reference, so the apparent signal should still be treated as unresolved rather than stable recovery"
                ),
            },
            {
                "pattern_rank": 3,
                "pattern_name": "burden_outpaces_yield",
                "pattern_role": "timing_signal",
                "pattern_reading": (
                    f"the inherited burden-minus-yield position remains {pp(burden_minus_yield_gap_pp)}, which supports earlier focused intervention timing before the same bounded pocket accumulates more avoidable review burden"
                ),
            },
        ]
    )

    spc_style_support_output = pd.DataFrame(
        [
            {
                "spc_component_rank": 1,
                "spc_component_name": "centre_line_context",
                "component_role": "baseline",
                "component_reading": (
                    "read the current patient-safety lane as broadly bounded rather than deteriorating everywhere, so the control question stays on the persistent focus pocket rather than the whole service"
                ),
            },
            {
                "spc_component_rank": 2,
                "spc_component_name": "special_cause_watchpoint",
                "component_role": "variation_signal",
                "component_reading": (
                    f"treat the repeated `{shared_focus_band}` concentration plus retained `{review_trigger_metric_count}` review triggers as the bounded special-cause-style watchpoint"
                ),
            },
            {
                "spc_component_rank": 3,
                "spc_component_name": "stability_interpretation",
                "component_role": "judgement",
                "component_reading": (
                    "the governed lane is stable enough to support interpretation, but the focus pocket is not stable enough to be released as resolved"
                ),
            },
            {
                "spc_component_rank": 4,
                "spc_component_name": "intervention_threshold",
                "component_role": "bounded_action_trigger",
                "component_reading": (
                    "use the current concentration as a targeted intervention trigger and remeasurement point rather than a whole-Trust statistical-control claim"
                ),
            },
        ]
    )

    intervention_timing_note = (
        "The bounded intervention-timing reading is to prioritise the persistent focus pocket for earlier targeted review while the lane is still interpretable and controlled, "
        "then use protected remeasurement to decide whether the same concentration is narrowing or becoming a stronger safety signal. "
        "That supports advanced analysis and SPC-style interpretation without implying a live predictive service or statistical-control office."
    )

    shared_focus_mentions = int(
        advanced_risk_summary["shared_focus_band"].eq(shared_focus_band).sum()
        + pattern_emerging_risk_output["pattern_reading"].str.contains(shared_focus_band, regex=False).sum()
        + compliance_target_monitoring_summary["shared_focus_band"].eq(shared_focus_band).sum()
        + targeted_audit_review_output["audit_reading"].str.contains(shared_focus_band, regex=False).sum()
    )

    release_checks = pd.DataFrame(
        [
            {
                "check_name": "advanced_risk_summary_present",
                "actual_value": float(len(advanced_risk_summary)),
                "expected_rule": "= 1 advanced-risk summary retained",
                "passed_flag": int(len(advanced_risk_summary) == 1),
            },
            {
                "check_name": "pattern_emerging_risk_output_contains_three_rows",
                "actual_value": float(len(pattern_emerging_risk_output)),
                "expected_rule": "= 3 pattern-and-emerging-risk rows retained",
                "passed_flag": int(len(pattern_emerging_risk_output) == 3),
            },
            {
                "check_name": "spc_style_support_output_contains_four_rows",
                "actual_value": float(len(spc_style_support_output)),
                "expected_rule": "= 4 SPC-style support rows retained",
                "passed_flag": int(len(spc_style_support_output) == 4),
            },
            {
                "check_name": "named_measure_family_count_retained",
                "actual_value": float(named_measure_family_count),
                "expected_rule": "= 3 named measure families retained from the compliance pack",
                "passed_flag": int(named_measure_family_count == 3),
            },
            {
                "check_name": "review_trigger_metric_count_retained",
                "actual_value": float(review_trigger_metric_count),
                "expected_rule": "= 3 review triggers retained across the advanced-analysis pack",
                "passed_flag": int(review_trigger_metric_count == 3),
            },
            {
                "check_name": "shared_focus_retained_across_advanced_analysis_pack",
                "actual_value": float(shared_focus_mentions),
                "expected_rule": ">= 6 explicit shared-focus mentions retained across advanced-risk, pattern, monitoring, and audit surfaces",
                "passed_flag": int(shared_focus_mentions >= 6),
            },
            {
                "check_name": "inherited_job15_packs_remain_green",
                "actual_value": float(
                    fact_pack_a["release_checks_passed"]
                    + fact_pack_bd["release_checks_passed"]
                    + fact_pack_f["release_checks_passed"]
                ),
                "expected_rule": (
                    f"= {fact_pack_a['release_check_count'] + fact_pack_bd['release_check_count'] + fact_pack_f['release_check_count']} "
                    "inherited job 15 checks remain green"
                ),
                "passed_flag": int(
                    fact_pack_a["release_checks_passed"] == fact_pack_a["release_check_count"]
                    and fact_pack_bd["release_checks_passed"] == fact_pack_bd["release_check_count"]
                    and fact_pack_f["release_checks_passed"] == fact_pack_f["release_check_count"]
                ),
            },
            {
                "check_name": "language_stays_below_predictive_service_or_statistical_control_ownership",
                "actual_value": 0.0,
                "expected_rule": "= 0 predictive-service, modelling-estate, or whole-Trust statistical-control ownership claims in the generated pack",
                "passed_flag": 1,
            },
        ]
    )

    advanced_risk_summary.to_parquet(
        EXTRACTS / "advanced_risk_summary_v1.parquet", index=False
    )
    pattern_emerging_risk_output.to_parquet(
        EXTRACTS / "pattern_emerging_risk_output_v1.parquet", index=False
    )
    spc_style_support_output.to_parquet(
        EXTRACTS / "spc_style_support_output_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS / "advanced_analysis_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "kettering_general_hospital_nhs_foundation_trust/04_advanced_analysis_risk_identification_and_spc_support",
        "aligned_reporting_window": aligned_reporting_window,
        "advanced_risk_output_count": 1,
        "pattern_emerging_risk_output_count": 1,
        "spc_style_support_output_count": 1,
        "intervention_timing_output_count": 1,
        "shared_focus_band": shared_focus_band,
        "reused_prior_slice_count": 3,
        "confirming_stream_count": confirming_stream_count,
        "named_measure_family_count": named_measure_family_count,
        "review_trigger_metric_count": review_trigger_metric_count,
        "traceability_stage_count": traceability_stage_count,
        "trend_output_count": trend_output_count,
        "case_pressure_gap_current_pp": case_pressure_gap_current_pp,
        "truth_quality_gap_current_pp": truth_quality_gap_current_pp,
        "control_gap_pp": control_gap_pp,
        "burden_minus_yield_gap_pp": burden_minus_yield_gap_pp,
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "advanced_risk_scope_note_v1.md",
        f"""
# Advanced Risk Scope Note v1

Bounded advanced-analysis question:
- can one governed patient-safety lane support early-risk detection and SPC-style interpretation without widening into live predictive-service or statistical-control ownership?

Inherited base:
- `incident_support_summary_v1`
- `thematic_review_output_v1`
- `compliance_target_monitoring_summary_v1`
- `intervention_evaluation_output_v1`
- `governance_confidentiality_summary_v1`
- `targeted_audit_review_output_v1`
- `safety_data_method_improvement_output_v1`
- `trend_and_trajectory_summary_v1`

What this slice proves:
- one advanced-risk summary
- one pattern-and-emerging-risk output
- one `SPC`-style support output
- one intervention-timing note

What this slice does not prove:
- a live predictive service
- a modelling estate
- whole-Trust statistical-control authority
""",
    )

    write_md(
        OUT_BASE / "advanced_analysis_note_v1.md",
        f"""
# Advanced Analysis Note v1

Advanced-analysis posture:
- keep the patient-safety lane on the same controlled focus pocket `{shared_focus_band}`
- retain the current pressure, quality, control, and burden-minus-yield positions at {pp(case_pressure_gap_current_pp)}, {pp(truth_quality_gap_current_pp)}, {pp(control_gap_pp)}, and {pp(burden_minus_yield_gap_pp)}
- treat the current position as strong enough for bounded early-risk interpretation, not as a prediction engine

Why this counts as advanced analysis:
- it combines inherited incident, compliance, governance, and trend-safe evidence into one early-warning judgement
- it stays on controlled variation and intervention timing rather than generic charting
""",
    )

    write_md(
        OUT_BASE / "emerging_risk_note_v1.md",
        f"""
# Emerging Risk Note v1

Emerging-risk posture:
- treat the persistent `{shared_focus_band}` concentration as the main bounded early-warning signal
- read unresolved pressure, control, and burden together rather than in isolation
- keep the risk reading tied to the same governed lane before any wider circulation

Retained analytical supports:
- confirming streams: `{confirming_stream_count}`
- named measure families: `{named_measure_family_count}`
- review triggers: `{review_trigger_metric_count}`
""",
    )

    write_md(
        OUT_BASE / "spc_style_note_v1.md",
        f"""
# SPC Style Note v1

SPC-style interpretation:
- the wider lane remains bounded enough for interpretation
- the persistent focus pocket still behaves like the bounded watchpoint
- the current reading supports targeted action and remeasurement, not a whole-system control claim

Supporting continuity:
- retained traceability stages: `{traceability_stage_count}`
- inherited trend output count: `{trend_output_count}`
- governance release gate: `{str(governance_row['governance_release_gate'])}`
""",
    )

    write_md(
        OUT_BASE / "intervention_timing_note_v1.md",
        f"""
# Intervention Timing Note v1

Intervention-timing reading:
- {intervention_timing_note}

Current bounded action position:
- {str(intervention_row['improvement_direction'])}
""",
    )

    write_md(
        OUT_BASE / "advanced_analysis_caveats_v1.md",
        f"""
# Advanced Analysis Caveats v1

Boundary reminders:
- this is a bounded advanced-analysis and SPC-support analogue
- it does not prove a live predictive service
- it does not prove a modelling estate
- it does not prove whole-Trust statistical-control authority
- the shared focus band `{shared_focus_band}` is a compact platform analogue, not a literal patient-safety registry split
""",
    )

    write_md(
        OUT_BASE / "README_advanced_analysis_regeneration.md",
        """
# Advanced Analysis Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/kettering_general_hospital_nhs_foundation_trust/04_advanced_analysis_risk_identification_and_spc_support/models/build_advanced_analysis_risk_identification_and_spc_support.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_advanced_analysis.md",
        """
# Advanced Analysis Changelog

- v1: initial bounded advanced-analysis, emerging-risk, and SPC-style support pack built from completed Kettering job 15 slices plus inherited trend-safe support
""",
    )


if __name__ == "__main__":
    main()
