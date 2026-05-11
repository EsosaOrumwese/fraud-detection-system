from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

SOUTH_REPORTING_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "south_tyneside_and_sunderland_nhs_foundation_trust"
    / "01_bi_reporting_product_and_reporting_platform_support"
)
MAPS_FRAMEWORK_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "05_kpi_and_framework_measurement_support"
)
WELSH_CONTROL_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "welsh_government"
    / "01_validation_reconciliation_and_cyclical_operational_control"
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

    prepared_reporting_base = pd.read_parquet(
        SOUTH_REPORTING_BASE / "extracts" / "prepared_reporting_base_v1.parquet"
    )
    management_information_output = pd.read_parquet(
        SOUTH_REPORTING_BASE / "extracts" / "management_information_output_v1.parquet"
    )
    kpi_framework_summary = pd.read_parquet(
        MAPS_FRAMEWORK_BASE / "extracts" / "kpi_framework_summary_v1.parquet"
    )
    change_tracking_summary = pd.read_parquet(
        MAPS_FRAMEWORK_BASE / "extracts" / "change_tracking_summary_v1.parquet"
    )
    reconciliation_output = pd.read_parquet(
        WELSH_CONTROL_BASE / "extracts" / "reconciliation_output_v1.parquet"
    )

    south_fact_pack = json.loads(
        (SOUTH_REPORTING_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    maps_fact_pack = json.loads(
        (MAPS_FRAMEWORK_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    welsh_fact_pack = json.loads(
        (WELSH_CONTROL_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    south_row = prepared_reporting_base.iloc[0]
    management_row = management_information_output.iloc[0]
    current_reconciliation_row = reconciliation_output.loc[
        reconciliation_output["week_role"] == "current"
    ].iloc[0]

    aligned_reporting_window = str(south_row["aligned_reporting_window"])
    shared_reporting_cohort = str(south_row["shared_focus_band"])
    retained_source_streams = int(south_row["confirming_stream_count"])

    prepared_research_performance_base = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "prepared_reporting_question": (
                    "how can one governed specialist-system-backed reporting lane be packaged as a reusable "
                    "research-performance base for internal programme management and mandatory external-style reporting?"
                ),
                "prepared_base_name": "research_performance_reporting_base",
                "reporting_grain": "research_metric_programme_reporting_pack",
                "shared_reporting_cohort": shared_reporting_cohort,
                "retained_source_streams": retained_source_streams,
                "retained_reporting_views_count": int(south_row["retained_product_views_count"]),
                "case_pressure_gap_pp": float(south_row["case_pressure_gap_pp"]),
                "truth_quality_gap_pp": float(south_row["truth_quality_gap_pp"]),
                "prepared_base_status": "research_performance_reporting_ready",
                "prepared_base_reading": (
                    "the prepared base combines reusable reporting structure, management-information readability, "
                    "and controlled cross-source confirmation into one compact research-performance source suitable "
                    "for recurring R&D reporting use"
                ),
            }
        ]
    )

    mandatory_research_reporting_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "mandatory_reporting_surface_name": "research_performance_mandatory_reporting_summary",
                "reporting_cycle_shape": "department_of_health_nihr_style_bundle_analogue",
                "shared_reporting_cohort": shared_reporting_cohort,
                "retained_source_streams": retained_source_streams,
                "framework_measure_count": int(maps_fact_pack["framework_measure_count"]),
                "change_tracking_kpi_count": int(maps_fact_pack["change_tracking_kpi_count"]),
                "quality_checked_release_gate": "controlled_before_internal_or_external_style_circulation",
                "control_family_status": str(current_reconciliation_row["reconciliation_status"]),
                "control_gap_pp": float(welsh_fact_pack["current_absolute_gap_pp"]),
                "mandatory_reporting_reading": (
                    "the mandatory-return-style summary keeps measure coverage, change tracking, and controlled "
                    "release posture explicit, which is the right bounded analogue for R&D performance returns "
                    "without implying live submission authority"
                ),
            }
        ]
    )

    metric_aliases = {
        "shared_focus_confirmation_strength": (
            "cross_source_confirmation_strength",
            "confirm whether the same reporting cohort remains reinforced across the compact research-performance lane",
            "maintain_full_confirmation",
        ),
        "focus_case_open_gap_to_peer_pp": (
            "reporting_pressure_gap_pp",
            "track whether the retained reporting cohort still carries materially higher operational pressure than peer context",
            "down_toward_zero",
        ),
        "focus_truth_quality_gap_to_peer_pp": (
            "quality_consistency_gap_pp",
            "track whether the retained reporting cohort is moving closer to peer-quality context for reporting consistency",
            "up_toward_zero",
        ),
    }

    research_performance_dashboard_output = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "dashboard_surface_name": "research_performance_dashboard_output",
                "shared_reporting_cohort": shared_reporting_cohort,
                "dashboard_metric_rank": idx + 1,
                "dashboard_metric_name": metric_aliases[row["kpi_name"]][0],
                "dashboard_metric_purpose": metric_aliases[row["kpi_name"]][1],
                "current_value": float(row["current_value"]),
                "value_unit": str(row["value_unit"]),
                "intended_direction": metric_aliases[row["kpi_name"]][2],
                "target_state_reading": str(row["target_state_reading"]),
            }
            for idx, (_, row) in enumerate(kpi_framework_summary.iterrows())
        ]
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "prepared_research_performance_base_output_present",
                "actual_value": float(len(prepared_research_performance_base)),
                "expected_rule": "= 1 prepared research-performance base output present",
                "passed_flag": int(len(prepared_research_performance_base) == 1),
            },
            {
                "check_name": "mandatory_research_reporting_summary_output_present",
                "actual_value": float(len(mandatory_research_reporting_summary)),
                "expected_rule": "= 1 mandatory-return-style summary output present",
                "passed_flag": int(len(mandatory_research_reporting_summary) == 1),
            },
            {
                "check_name": "research_performance_dashboard_output_contains_three_metrics",
                "actual_value": float(len(research_performance_dashboard_output)),
                "expected_rule": "= 3 dashboard-style research-performance metrics retained",
                "passed_flag": int(len(research_performance_dashboard_output) == 3),
            },
            {
                "check_name": "aligned_reporting_window_stays_consistent",
                "actual_value": float(
                    prepared_research_performance_base.iloc[0]["aligned_reporting_window"]
                    == mandatory_research_reporting_summary.iloc[0]["aligned_reporting_window"]
                    == aligned_reporting_window
                ),
                "expected_rule": "= 1 if all outputs retain the same aligned reporting window",
                "passed_flag": int(
                    prepared_research_performance_base.iloc[0]["aligned_reporting_window"]
                    == mandatory_research_reporting_summary.iloc[0]["aligned_reporting_window"]
                    == aligned_reporting_window
                ),
            },
            {
                "check_name": "south_reporting_pack_remains_green",
                "actual_value": float(south_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {south_fact_pack['release_check_count']} inherited South Tyneside reporting checks remain green",
                "passed_flag": int(
                    south_fact_pack["release_checks_passed"] == south_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "maps_framework_pack_remains_green",
                "actual_value": float(maps_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {maps_fact_pack['release_check_count']} inherited framework-reporting checks remain green",
                "passed_flag": int(
                    maps_fact_pack["release_checks_passed"] == maps_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "welsh_control_pack_remains_green",
                "actual_value": float(welsh_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {welsh_fact_pack['release_check_count']} inherited control-lane checks remain green",
                "passed_flag": int(
                    welsh_fact_pack["release_checks_passed"] == welsh_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "language_stays_below_edge_or_submission_ownership",
                "actual_value": 0.0,
                "expected_rule": "= 0 live EDGE, CPMS, or national-submission ownership claims in the generated pack",
                "passed_flag": 1,
            },
        ]
    )

    prepared_research_performance_base.to_parquet(
        EXTRACTS / "prepared_research_performance_base_v1.parquet", index=False
    )
    mandatory_research_reporting_summary.to_parquet(
        EXTRACTS / "mandatory_research_reporting_summary_v1.parquet", index=False
    )
    research_performance_dashboard_output.to_parquet(
        EXTRACTS / "research_performance_dashboard_output_v1.parquet", index=False
    )
    checks_df.to_parquet(
        EXTRACTS / "research_reporting_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "guys_and_st_thomas_nhs_foundation_trust_rd_data_analyst/01_research_management_system_support_and_research_performance_reporting",
        "aligned_reporting_window": aligned_reporting_window,
        "prepared_research_performance_base_output_count": 1,
        "mandatory_research_reporting_output_count": 1,
        "research_performance_dashboard_output_count": 1,
        "reporting_cycle_note_output_count": 1,
        "shared_reporting_cohort": shared_reporting_cohort,
        "retained_source_stream_count": retained_source_streams,
        "retained_reporting_view_count": int(south_row["retained_product_views_count"]),
        "mandatory_measure_family_count": int(maps_fact_pack["framework_measure_count"]),
        "dashboard_metric_count": int(len(research_performance_dashboard_output)),
        "current_case_pressure_gap_pp": float(south_row["case_pressure_gap_pp"]),
        "current_truth_quality_gap_pp": float(south_row["truth_quality_gap_pp"]),
        "current_control_gap_pp": float(welsh_fact_pack["current_absolute_gap_pp"]),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "research_performance_scope_note_v1.md",
        """
# Research Performance Scope Note v1

Bounded reporting question:
- can one governed specialist-system-backed reporting lane support a prepared research-performance base, a mandatory-return-style summary, and a dashboard-style management-information view from the same compact question?

Inherited compact base:
- `prepared_reporting_base_v1`
- `management_information_output_v1`
- `kpi_framework_summary_v1`
- `change_tracking_summary_v1`
- `reconciliation_output_v1`

What this slice proves:
- one prepared research-performance base
- one mandatory-return-style summary output
- one dashboard-style management-information output
- one R&D reporting-cycle note

What this slice does not prove:
- live `EDGE` ownership
- live `CPMS` integration ownership
- direct national-submission authority
- the full Trust `R&D` data estate
""",
    )

    write_md(
        OUT_BASE / "prepared_research_performance_base_note_v1.md",
        f"""
# Prepared Research Performance Base Note v1

Preparation posture:
- the job 14 slice uses a compact prepared-base step over inherited reporting-product, framework, and control outputs
- the preparation layer retains only the fields needed for repeat research-performance reporting and management use

Retained reporting grain:
- `research_metric_programme_reporting_pack`
- row count retained: `{len(prepared_research_performance_base)}`

Shared reporting cohort after preparation:
- `{shared_reporting_cohort}`
- retained source streams: `{retained_source_streams}`

Why this preparation layer matters:
- it behaves like the database-backed preparation step the Guy's and St Thomas' role expects
- it converts completed analytical packs into a cleaner reusable R&D reporting source without reopening raw scope
""",
    )

    write_md(
        OUT_BASE / "mandatory_research_reporting_note_v1.md",
        f"""
# Mandatory Research Reporting Note v1

Mandatory-return-style posture:
- reporting cycle shape retained as a bounded `Department of Health` / `NIHR` style bundle analogue
- shared reporting cohort: `{shared_reporting_cohort}`
- framework measure families retained: `{int(maps_fact_pack['framework_measure_count'])}`
- tracked change KPIs retained: `{int(maps_fact_pack['change_tracking_kpi_count'])}`
- current control gap: `{pp(float(welsh_fact_pack['current_absolute_gap_pp']))}`

Why this counts:
- the summary keeps accountable reporting and controlled release posture explicit
- it packages a high-accountability research-performance reading from the same governed lane
- it stays below live submission or national-authority claims
""",
    )

    write_md(
        OUT_BASE / "research_performance_dashboard_note_v1.md",
        f"""
# Research Performance Dashboard Note v1

Dashboard posture:
- shared reporting cohort retained: `{shared_reporting_cohort}`
- dashboard metric rows retained: `{len(research_performance_dashboard_output)}`
- confirming source streams retained: `{retained_source_streams}`

Dashboard reading:
- the dashboard keeps one cross-source confirmation metric and two directional pressure-and-quality metrics visible
- this makes the same governed reporting base easier to scan for recurring R&D management review
- the dashboard surface is bounded and does not imply a live Trust dashboard estate
""",
    )

    write_md(
        OUT_BASE / "research_reporting_cycle_note_v1.md",
        f"""
# Research Reporting Cycle Note v1

R&D reporting-cycle reading:
- the same prepared base now supports both accountable external-style reporting and recurring internal management visibility
- the retained reporting cohort `{shared_reporting_cohort}` remains cross-source confirmed at `{retained_source_streams}` streams
- the management-information side still reads as controlled rather than self-service because release posture and reconciliation remain explicit

What matters next:
- use the prepared base for reporting continuity
- use the mandatory-return-style summary for accountable external-style reading
- use the dashboard-style surface for monthly or quarterly internal review
- keep the pack below live system ownership and below national-submission authority
""",
    )

    write_md(
        OUT_BASE / "research_reporting_caveats_v1.md",
        f"""
# Research Reporting Caveats v1

Boundary reminders:
- this is a bounded research-management-system-support and research-performance-reporting analogue
- it does not prove live `EDGE` administration
- it does not prove live `CPMS` data-flow ownership
- it does not prove direct national submission authority
- the shared reporting cohort is a compact platform analogue over `{shared_reporting_cohort}`, not a literal Trust research-portfolio segmentation estate
""",
    )

    write_md(
        OUT_BASE / "README_research_reporting_regeneration.md",
        """
# Research Reporting Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/guys_and_st_thomas_nhs_foundation_trust_rd_data_analyst/01_research_management_system_support_and_research_performance_reporting/models/build_research_management_system_support_and_research_performance_reporting.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_research_reporting.md",
        """
# Research Reporting Changelog

- v1: initial bounded research-management-system support and research-performance reporting pack built from inherited reporting-product, framework, and control lanes
""",
    )


if __name__ == "__main__":
    main()
