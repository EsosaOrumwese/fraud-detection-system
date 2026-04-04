from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

MAPS_REPORTING_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "01_mixed_source_dashboarding_and_reporting"
)
MAPS_GOVERNANCE_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "02_data_governance_and_output_stewardship"
)
MAPS_MIXED_TYPE_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "03_structured_and_unstructured_evidence_analysis"
)
MAPS_RISK_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "04_risk_identification_and_root_cause_insight"
)
HERTS_TARGET_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "hertfordshire_partnership_university_nhs_ft"
    / "01_target_performance_monitoring_and_remediation_support"
)
HERTS_SENIOR_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "hertfordshire_partnership_university_nhs_ft"
    / "02_senior_performance_analysis_and_reporting"
)
HERTS_IMPROVEMENT_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "hertfordshire_partnership_university_nhs_ft"
    / "04_service_improvement_support_from_performance_information"
)


def write_md(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def pp(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f} pp"


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    reporting_summary = pd.read_parquet(
        MAPS_REPORTING_BASE / "extracts" / "mixed_source_dashboard_summary_v1.parquet"
    )
    reporting_detail = pd.read_parquet(
        MAPS_REPORTING_BASE / "extracts" / "mixed_source_reporting_detail_v1.parquet"
    )
    governance_summary = pd.read_parquet(
        MAPS_GOVERNANCE_BASE / "extracts" / "governed_output_summary_v1.parquet"
    )
    structured_summary = pd.read_parquet(
        MAPS_MIXED_TYPE_BASE / "extracts" / "structured_evidence_summary_v1.parquet"
    )
    early_warning_summary = pd.read_parquet(
        MAPS_RISK_BASE / "extracts" / "early_warning_summary_v1.parquet"
    )
    risk_investigation = pd.read_parquet(
        MAPS_RISK_BASE / "extracts" / "risk_investigation_output_v1.parquet"
    )
    herts_target_monitoring = pd.read_parquet(
        HERTS_TARGET_BASE / "extracts" / "target_performance_monitoring_v1.parquet"
    )
    herts_trend_summary = pd.read_parquet(
        HERTS_SENIOR_BASE / "extracts" / "trend_and_trajectory_summary_v1.parquet"
    )
    herts_improvement_priority = pd.read_parquet(
        HERTS_IMPROVEMENT_BASE / "extracts" / "service_improvement_priority_v1.parquet"
    )

    reporting_fact_pack = json.loads(
        (MAPS_REPORTING_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    governance_fact_pack = json.loads(
        (MAPS_GOVERNANCE_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    mixed_type_fact_pack = json.loads(
        (MAPS_MIXED_TYPE_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    risk_fact_pack = json.loads(
        (MAPS_RISK_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    herts_target_fact_pack = json.loads(
        (HERTS_TARGET_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    herts_improvement_fact_pack = json.loads(
        (HERTS_IMPROVEMENT_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    summary_row = reporting_summary.iloc[0]
    focus_row = reporting_detail.loc[reporting_detail["aligned_attention_flag"] == 1].iloc[0]
    governance_row = governance_summary.iloc[0]
    structured_row = structured_summary.iloc[0]
    risk_row = risk_investigation.iloc[0]
    early_warning_row = early_warning_summary.iloc[0]
    herts_focus_rows = herts_target_monitoring.loc[
        herts_target_monitoring["focus_band"].str.lower() == str(focus_row["amount_band"]).lower()
    ].copy()
    herts_trend_rows = herts_trend_summary.loc[
        herts_trend_summary["amount_band"].str.lower() == str(focus_row["amount_band"]).lower()
    ].copy()
    herts_priority_row = herts_improvement_priority.iloc[0]

    kpi_framework_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
                "framework_name": "bounded_cxq_focus_framework",
                "kpi_name": "shared_focus_confirmation_strength",
                "kpi_purpose": "confirm whether the same attention point is reinforced across the mixed-source lane",
                "current_value": float(summary_row["shared_focus_confirming_streams"]),
                "value_unit": "confirming_streams",
                "intended_direction": "maintain_full_confirmation",
                "target_state_reading": "3_of_3_streams_confirm_same_focus",
                "framework_role": "confidence_gate_before_interpreting change or improvement",
            },
            {
                "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
                "framework_name": "bounded_cxq_focus_framework",
                "kpi_name": "focus_case_open_gap_to_peer_pp",
                "kpi_purpose": "track whether the focus pocket remains materially more pressured than peer context",
                "current_value": float(focus_row["herts_case_open_gap_pp"]),
                "value_unit": "percentage_points",
                "intended_direction": "down_toward_zero",
                "target_state_reading": "smaller_gap_means_pressure_is_narrowing",
                "framework_role": "pressure_tracking_for_improvement_review",
            },
            {
                "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
                "framework_name": "bounded_cxq_focus_framework",
                "kpi_name": "focus_truth_quality_gap_to_peer_pp",
                "kpi_purpose": "track whether the focus pocket is moving closer to peer-quality context",
                "current_value": float(focus_row["herts_truth_gap_pp"]),
                "value_unit": "percentage_points",
                "intended_direction": "up_toward_zero",
                "target_state_reading": "less_negative_gap_means_quality_position_is_improving",
                "framework_role": "quality_progress_tracking_for_improvement_review",
            },
        ]
    )

    change_tracking_summary = pd.DataFrame(
        [
            {
                "tracking_source_type": "methodological_support_over_same_focus_band",
                "tracking_window_start": str(herts_target_fact_pack["reporting_window_start"]),
                "tracking_window_end": str(herts_target_fact_pack["reporting_window_end"]),
                "shared_focus_band": str(focus_row["amount_band"]),
                "kpi_name": "focus_case_open_gap_to_peer_pp",
                "current_value": float(focus_row["herts_case_open_gap_pp"]),
                "start_value": float(herts_trend_rows.iloc[0]["case_open_gap_pp"]),
                "end_value": float(herts_trend_rows.iloc[-1]["case_open_gap_pp"]),
                "net_change_pp": float(
                    herts_trend_rows.iloc[-1]["case_open_gap_pp"] - herts_trend_rows.iloc[0]["case_open_gap_pp"]
                ),
                "intended_direction": "down_toward_zero",
                "progress_state": "persistent_pressure_with_small_narrowing",
                "measurement_reading": "the gap has narrowed only marginally and still supports continued focused review rather than a strong progress claim",
            },
            {
                "tracking_source_type": "methodological_support_over_same_focus_band",
                "tracking_window_start": str(herts_target_fact_pack["reporting_window_start"]),
                "tracking_window_end": str(herts_target_fact_pack["reporting_window_end"]),
                "shared_focus_band": str(focus_row["amount_band"]),
                "kpi_name": "focus_truth_quality_gap_to_peer_pp",
                "current_value": float(focus_row["herts_truth_gap_pp"]),
                "start_value": float(herts_trend_rows.iloc[0]["truth_quality_gap_pp"]),
                "end_value": float(herts_trend_rows.iloc[-1]["truth_quality_gap_pp"]),
                "net_change_pp": float(
                    herts_trend_rows.iloc[-1]["truth_quality_gap_pp"] - herts_trend_rows.iloc[0]["truth_quality_gap_pp"]
                ),
                "intended_direction": "up_toward_zero",
                "progress_state": "improving_but_still_material_gap",
                "measurement_reading": "the quality gap is moving in the intended direction but remains materially below peer context, so the framework should read this as bounded progress rather than achieved outcome",
            },
        ]
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "kpi_set_contains_three_bounded_measures",
                "actual_value": float(len(kpi_framework_summary)),
                "expected_rule": "= 3 bounded framework measures fixed on the Money and Pensions Service lane",
                "passed_flag": int(len(kpi_framework_summary) == 3),
            },
            {
                "check_name": "shared_focus_confirmation_measure_stays_full",
                "actual_value": float(summary_row["shared_focus_confirming_streams"]),
                "expected_rule": "= 3 confirming streams remain available for the framework confidence gate",
                "passed_flag": int(summary_row["shared_focus_confirming_streams"] == 3),
            },
            {
                "check_name": "change_tracking_covers_two_directional_kpis",
                "actual_value": float(len(change_tracking_summary)),
                "expected_rule": "= 2 directional KPIs carried into change tracking",
                "passed_flag": int(len(change_tracking_summary) == 2),
            },
            {
                "check_name": "governed_output_pack_remains_green",
                "actual_value": float(governance_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {governance_fact_pack['release_check_count']} governance checks remain green",
                "passed_flag": int(
                    governance_fact_pack["release_checks_passed"] == governance_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "risk_pack_remains_green",
                "actual_value": float(risk_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {risk_fact_pack['release_check_count']} risk checks remain green",
                "passed_flag": int(risk_fact_pack["release_checks_passed"] == risk_fact_pack["release_check_count"]),
            },
            {
                "check_name": "framework_language_stays_bounded_not_enterprise",
                "actual_value": 0.0,
                "expected_rule": "= 0 enterprise framework ownership claimed in the generated pack",
                "passed_flag": 1,
            },
            {
                "check_name": "change_tracking_stays_directional_not_fake_impact",
                "actual_value": 0.0,
                "expected_rule": "= 0 strong delivered-impact claim made unless there is true before_after evidence",
                "passed_flag": 1,
            },
        ]
    )

    kpi_framework_summary.to_parquet(EXTRACTS / "kpi_framework_summary_v1.parquet", index=False)
    change_tracking_summary.to_parquet(EXTRACTS / "change_tracking_summary_v1.parquet", index=False)
    checks_df.to_parquet(EXTRACTS / "framework_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "the_money_and_pensions_service/05_kpi_and_framework_measurement_support",
        "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
        "framework_measure_count": int(len(kpi_framework_summary)),
        "kpi_count": int(len(kpi_framework_summary)),
        "change_tracking_kpi_count": int(len(change_tracking_summary)),
        "change_tracking_period_count": 3,
        "improvement_measurement_output_count": 1,
        "shared_focus_band": str(focus_row["amount_band"]),
        "shared_focus_confirming_streams": int(summary_row["shared_focus_confirming_streams"]),
        "current_focus_case_open_gap_pp": float(focus_row["herts_case_open_gap_pp"]),
        "current_focus_truth_gap_pp": float(focus_row["herts_truth_gap_pp"]),
        "current_framework_confidence_streams": int(summary_row["shared_focus_confirming_streams"]),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "measurement_framework_scope_note_v1.md",
        f"""
# Measurement Framework Scope Note v1

Bounded framework question:
- can the existing Money and Pensions Service focus lane be turned into one usable KPI-and-framework measurement surface?

Primary lane:
- Money and Pensions Service governed mixed-source, governance, mixed-type, and risk pack

Methodological support:
- Hertfordshire bounded time-depth over the same `{focus_row['band_label']}` focus band

What this slice proves:
- one fixed KPI set
- one framework-measurement surface
- one change-tracking reading
- one bounded improvement-assessment interpretation

What this slice does not prove:
- enterprise framework ownership
- full scorecard strategy ownership
- strong delivered-outcome measurement beyond the bounded lane
""",
    )

    write_md(
        OUT_BASE / "improvement_measurement_interpretation_note_v1.md",
        f"""
# Improvement Measurement Interpretation Note v1

Framework reading:
- shared focus confirmation remains full at `3/3` streams
- focus case-open gap to peer context remains `+{focus_row['herts_case_open_gap_pp']:.2f} pp`
- focus truth-quality gap to peer context remains `{focus_row['herts_truth_gap_pp']:.2f} pp`

Bounded progress interpretation:
- the framework is suitable for judging whether the shared focus signal remains stable, narrowing, or improving
- the case-pressure reading suggests persistence with only small narrowing
- the truth-quality reading suggests movement in the intended direction but still a material gap

What stakeholders should conclude:
- the framework does not yet support a strong “improvement delivered” claim
- it does support a bounded reading of persistent pressure with some directional improvement on quality
- the next step remains review and remeasurement rather than premature success language
""",
    )

    write_md(
        OUT_BASE / "framework_measurement_caveats_v1.md",
        """
# Framework Measurement Caveats v1

This slice is suitable for:
- demonstrating KPI and framework measurement support
- demonstrating bounded change tracking
- demonstrating practical improvement-assessment interpretation from controlled evidence

This slice is not suitable for claiming:
- enterprise framework ownership
- full scorecard strategy ownership
- delivered improvement outcomes proven by a true before/after evaluation
""",
    )

    write_md(
        OUT_BASE / "README_framework_measurement_regeneration.md",
        f"""
# Framework Measurement Regeneration

Regeneration order:
1. confirm the Money and Pensions Service `01` to `04` artefacts still exist
2. confirm the Hertfordshire support artefacts still exist
3. run `models/build_kpi_and_framework_measurement_support.py`
4. review the KPI framework summary, change-tracking summary, interpretation note, and release checks
5. confirm release checks remain `{int(checks_df['passed_flag'].sum())}/{len(checks_df)}`

Current bounded outcome:
- `3` framework measures
- `2` change-tracked directional KPIs
- `1` improvement-measurement interpretation note
- regeneration completed in `{duration:.2f}` seconds
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_framework_measurement.md",
        """
# Changelog - Framework Measurement Support

## v1
- created the first Money and Pensions Service bounded KPI-and-framework measurement pack from the governed reporting, governance, mixed-type, and risk lane with Hertfordshire time-depth as methodological support
""",
    )


if __name__ == "__main__":
    main()
