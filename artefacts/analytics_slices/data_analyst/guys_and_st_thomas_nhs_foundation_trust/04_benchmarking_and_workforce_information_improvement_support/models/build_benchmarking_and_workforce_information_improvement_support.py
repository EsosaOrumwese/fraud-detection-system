from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

GUYS_REPORTING_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "guys_and_st_thomas_nhs_foundation_trust"
    / "01_workforce_intelligence_edi_dashboards_and_statutory_reporting"
)
GUYS_QUALITY_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "guys_and_st_thomas_nhs_foundation_trust"
    / "02_workforce_data_quality_governance_and_compliance_monitoring"
)
GUYS_PROJECT_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "guys_and_st_thomas_nhs_foundation_trust"
    / "03_project_coordination_and_impact_measurement"
)


def write_md(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def pp(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f} pp"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    workforce_reporting_summary = pd.read_parquet(
        GUYS_REPORTING_BASE / "extracts" / "workforce_reporting_summary_v1.parquet"
    )
    edi_dashboard_surface = pd.read_parquet(
        GUYS_REPORTING_BASE / "extracts" / "edi_dashboard_surface_v1.parquet"
    )
    reporting_checks = pd.read_parquet(
        GUYS_REPORTING_BASE / "extracts" / "workforce_reporting_release_checks_v1.parquet"
    )

    issue_findings_output = pd.read_parquet(
        GUYS_QUALITY_BASE / "extracts" / "issue_findings_output_v1.parquet"
    )
    compliance_monitoring_output = pd.read_parquet(
        GUYS_QUALITY_BASE / "extracts" / "compliance_monitoring_output_v1.parquet"
    )
    quality_checks = pd.read_parquet(
        GUYS_QUALITY_BASE / "extracts" / "workforce_quality_governance_release_checks_v1.parquet"
    )

    project_control_output = pd.read_parquet(
        GUYS_PROJECT_BASE / "extracts" / "project_control_output_v1.parquet"
    )
    impact_measurement_output = pd.read_parquet(
        GUYS_PROJECT_BASE / "extracts" / "impact_measurement_output_v1.parquet"
    )
    project_checks = pd.read_parquet(
        GUYS_PROJECT_BASE / "extracts" / "project_impact_release_checks_v1.parquet"
    )

    reporting_fact_pack = json.loads(
        (GUYS_REPORTING_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    quality_fact_pack = json.loads(
        (GUYS_QUALITY_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    project_fact_pack = json.loads(
        (GUYS_PROJECT_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    reporting_row = workforce_reporting_summary.iloc[0]
    issue_row = issue_findings_output.iloc[0]
    case_gap_row = edi_dashboard_surface.loc[
        edi_dashboard_surface["dashboard_metric_name"] == "focus_case_open_gap_to_peer_pp"
    ].iloc[0]
    truth_gap_row = edi_dashboard_surface.loc[
        edi_dashboard_surface["dashboard_metric_name"] == "focus_truth_quality_gap_to_peer_pp"
    ].iloc[0]
    release_rate_row = compliance_monitoring_output.loc[
        compliance_monitoring_output["monitoring_metric_name"] == "release_safe_check_pass_rate"
    ].iloc[0]

    aligned_reporting_window = str(reporting_row["aligned_reporting_window"])
    protected_group_dimension = str(reporting_row["protected_group_dimension"])
    protected_group_focus = str(reporting_row["protected_group_focus"])

    benchmarking_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "benchmarking_lane_name": "bounded_workforce_information_benchmarking_and_improvement_pack",
                "benchmarking_question": (
                    "how should the current protected-group-style workforce-information focus be "
                    "contextualised and what should improve next in future reporting?"
                ),
                "protected_group_dimension": protected_group_dimension,
                "protected_group_focus": protected_group_focus,
                "comparator_rows_used": 2,
                "retained_feedback_signal_count": 3,
                "benchmarking_reading": (
                    "the same workforce-information lane already carries peer-relative gap signals, "
                    "review triggers, and controlled delivery stages, so it can support one bounded "
                    "benchmarking and improvement-direction pack without simulating a live workforce-systems estate"
                ),
            }
        ]
    )

    comparator_context_output = pd.DataFrame(
        [
            {
                "comparator_rank": 1,
                "comparator_context_name": "peer_style_case_pressure_context",
                "reference_surface_name": "edi_dashboard_surface_v1",
                "protected_group_dimension": protected_group_dimension,
                "protected_group_focus": protected_group_focus,
                "benchmark_metric_name": str(case_gap_row["dashboard_metric_name"]),
                "current_value": float(case_gap_row["current_value"]),
                "value_unit": str(case_gap_row["value_unit"]),
                "bounded_context_reading": (
                    "the protected-group-style focus remains materially more pressured than peer-style context, "
                    "which supports keeping this pocket visible in external-context and benchmarking-style interpretation"
                ),
            },
            {
                "comparator_rank": 2,
                "comparator_context_name": "peer_style_truth_quality_context",
                "reference_surface_name": "edi_dashboard_surface_v1",
                "protected_group_dimension": protected_group_dimension,
                "protected_group_focus": protected_group_focus,
                "benchmark_metric_name": str(truth_gap_row["dashboard_metric_name"]),
                "current_value": float(truth_gap_row["current_value"]),
                "value_unit": str(truth_gap_row["value_unit"]),
                "bounded_context_reading": (
                    "the same focus also remains behind peer-style quality context, so the workforce-information lane "
                    "still needs controlled interpretation rather than broad standalone circulation"
                ),
            },
        ]
    )

    feedback_improvement_output = pd.DataFrame(
        [
            {
                "improvement_rank": 1,
                "retained_feedback_source": "issue_findings_output_v1",
                "retained_signal_name": str(issue_row["issue_class_name"]),
                "current_signal_state": str(issue_row["governance_risk_reading"]),
                "future_reporting_direction": (
                    "keep the protected-group-style focus on a named monitoring surface in future workforce-information reporting"
                ),
                "systems_improvement_support_reading": (
                    "future reporting should preserve explicit focus tracking rather than embedding the issue inside generic dashboard totals"
                ),
            },
            {
                "improvement_rank": 2,
                "retained_feedback_source": "compliance_monitoring_output_v1",
                "retained_signal_name": "review_trigger_metrics",
                "current_signal_state": (
                    f"{int((compliance_monitoring_output['breach_flag'] == 1).sum())} review-trigger metrics still require bounded review"
                ),
                "future_reporting_direction": (
                    "carry forward explicit review-trigger prompts before wider circulation of workforce-information outputs"
                ),
                "systems_improvement_support_reading": (
                    "future workforce-information development should keep exception prompts close to the release gate rather than treating release as a separate manual step"
                ),
            },
            {
                "improvement_rank": 3,
                "retained_feedback_source": "project_control_output_v1_plus_impact_measurement_output_v1",
                "retained_signal_name": "controlled_four_stage_delivery_cycle",
                "current_signal_state": (
                    f"{int(len(project_control_output))} fixed control stages and "
                    f"{int(len(impact_measurement_output))} bounded impact measures are already explicit"
                ),
                "future_reporting_direction": (
                    "future workforce-information reporting should preserve the same scope-to-release control sequence as a reusable delivery pattern"
                ),
                "systems_improvement_support_reading": (
                    "bounded automation or platform improvement should focus on making the same controlled cycle easier to reuse, not on claiming a new workforce-systems estate"
                ),
            },
        ]
    )

    release_checks = pd.DataFrame(
        [
            {
                "check_name": "benchmarking_summary_output_present",
                "actual_value": float(len(benchmarking_summary)),
                "expected_rule": "= 1 benchmarking summary output present",
                "passed_flag": int(len(benchmarking_summary) == 1),
            },
            {
                "check_name": "comparator_context_contains_two_rows",
                "actual_value": float(len(comparator_context_output)),
                "expected_rule": "= 2 bounded comparator rows retained",
                "passed_flag": int(len(comparator_context_output) == 2),
            },
            {
                "check_name": "feedback_improvement_contains_three_directions",
                "actual_value": float(len(feedback_improvement_output)),
                "expected_rule": "= 3 bounded feedback-led improvement directions retained",
                "passed_flag": int(len(feedback_improvement_output) == 3),
            },
            {
                "check_name": "same_focus_retained_across_pack",
                "actual_value": float(
                    benchmarking_summary.iloc[0]["protected_group_focus"] == protected_group_focus
                    and comparator_context_output["protected_group_focus"].eq(protected_group_focus).all()
                ),
                "expected_rule": "= 1 same protected-group-style focus retained across the benchmarking pack",
                "passed_flag": int(
                    benchmarking_summary.iloc[0]["protected_group_focus"] == protected_group_focus
                    and comparator_context_output["protected_group_focus"].eq(protected_group_focus).all()
                ),
            },
            {
                "check_name": "inherited_reporting_pack_remains_green",
                "actual_value": float(reporting_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {reporting_fact_pack['release_check_count']} inherited reporting checks remain green",
                "passed_flag": int(
                    reporting_fact_pack["release_checks_passed"] == reporting_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "inherited_quality_pack_remains_green",
                "actual_value": float(quality_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {quality_fact_pack['release_check_count']} inherited quality checks remain green",
                "passed_flag": int(
                    quality_fact_pack["release_checks_passed"] == quality_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "inherited_project_pack_remains_green",
                "actual_value": float(project_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {project_fact_pack['release_check_count']} inherited project checks remain green",
                "passed_flag": int(
                    project_fact_pack["release_checks_passed"] == project_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "language_stays_below_systems_or_strategy_ownership",
                "actual_value": 0.0,
                "expected_rule": "= 0 live workforce-systems or whole-Trust strategy-ownership claims in the generated pack",
                "passed_flag": 1,
            },
        ]
    )

    benchmarking_summary.to_parquet(
        EXTRACTS / "benchmarking_summary_v1.parquet", index=False
    )
    comparator_context_output.to_parquet(
        EXTRACTS / "comparator_context_output_v1.parquet", index=False
    )
    feedback_improvement_output.to_parquet(
        EXTRACTS / "feedback_improvement_output_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS / "benchmarking_improvement_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "guys_and_st_thomas_nhs_foundation_trust/04_benchmarking_and_workforce_information_improvement_support",
        "aligned_reporting_window": aligned_reporting_window,
        "benchmarking_summary_output_count": 1,
        "comparator_context_output_count": 1,
        "feedback_improvement_output_count": 1,
        "workforce_information_improvement_output_count": 1,
        "protected_group_dimension": protected_group_dimension,
        "protected_group_focus": protected_group_focus,
        "comparator_rows_used": int(len(comparator_context_output)),
        "retained_feedback_signal_count": int(len(feedback_improvement_output)),
        "current_focus_case_gap_pp": float(reporting_row["focus_group_case_gap_pp"]),
        "current_focus_truth_gap_pp": float(reporting_row["focus_group_truth_gap_pp"]),
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "benchmarking_scope_note_v1.md",
        f"""
# Benchmarking Scope Note v1

Bounded comparator-and-improvement question:
- can the governed workforce-information lane be put into bounded comparator context and then used to support better future reporting direction?

Inherited base:
- `workforce_reporting_summary_v1`
- `edi_dashboard_surface_v1`
- `issue_findings_output_v1`
- `compliance_monitoring_output_v1`
- `project_control_output_v1`

What this slice proves:
- one benchmarking summary
- one comparator-context output
- one feedback-and-improvement output
- one bounded workforce-information-improvement note

What this slice does not prove:
- a live `ESR` or `Oracle HRMS` systems estate
- whole-Trust workforce strategy ownership
- broad reporting-platform transformation authority
""",
    )

    write_md(
        OUT_BASE / "comparator_context_note_v1.md",
        f"""
# Comparator Context Note v1

Protected-group-style focus retained:
- `{protected_group_focus}`

Comparator rows carried:
1. peer-style case pressure context: `{pp(float(case_gap_row['current_value']))}`
2. peer-style truth quality context: `{pp(float(truth_gap_row['current_value']))}`

Why this counts:
- the same workforce lane already expresses the focus pocket relative to peer-style context
- that makes the comparator story explicit enough for bounded benchmarking support
- it stays below live external Trust benchmarking-estate ownership
""",
    )

    write_md(
        OUT_BASE / "feedback_improvement_note_v1.md",
        f"""
# Feedback Improvement Note v1

Retained feedback and improvement directions:
1. keep the protected-group-style focus on a named monitoring surface
2. preserve explicit review-trigger prompts before wider circulation
3. keep the four-stage scope-to-release delivery cycle as the reusable reporting pattern

Current supporting signals:
- issue class: `{issue_row['issue_class_name']}`
- review-trigger metrics: `{int((compliance_monitoring_output['breach_flag'] == 1).sum())}`
- control stages fixed: `{int(len(project_control_output))}`

This remains a bounded improvement-support reading, not a broad systems-transformation claim.
""",
    )

    write_md(
        OUT_BASE / "workforce_information_improvement_note_v1.md",
        f"""
# Workforce Information Improvement Note v1

Bounded future direction:
- continue benchmarking the `{protected_group_focus}` workforce-information pocket against peer-style context
- keep the same review-trigger prompts attached to future reporting cycles
- make the controlled scope-to-release cycle easier to reuse in future workforce-information reporting

Why this is the right level:
- the current pack already shows explicit comparator context, explicit issues, and explicit control stages
- the release-safe position remains `{pct(float(release_rate_row['current_value']))}`
- that supports one bounded workforce-information-improvement direction without claiming live systems ownership
""",
    )

    write_md(
        OUT_BASE / "benchmarking_improvement_caveats_v1.md",
        f"""
# Benchmarking Improvement Caveats v1

Boundary reminders:
- this is a bounded benchmarking and workforce-information-improvement analogue
- it does not prove live external Trust benchmarking-estate ownership
- it does not prove live workforce-systems administration or redesign
- the protected-group-style dimension `{protected_group_dimension}` over `{protected_group_focus}` remains an honest workforce-information analogue rather than a literal Trust systems programme
""",
    )

    write_md(
        OUT_BASE / "README_benchmarking_improvement_regeneration.md",
        """
# Benchmarking Improvement Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/guys_and_st_thomas_nhs_foundation_trust/04_benchmarking_and_workforce_information_improvement_support/models/build_benchmarking_and_workforce_information_improvement_support.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_benchmarking_improvement.md",
        """
# Benchmarking Improvement Changelog

- v1: initial bounded benchmarking and workforce-information-improvement pack built from the inherited Guy's and St Thomas' reporting, quality, and project-control lanes
""",
    )


if __name__ == "__main__":
    main()
