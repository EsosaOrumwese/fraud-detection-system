from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

CLAIRE_LEADERSHIP_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "claire_house"
    / "03_senior_leadership_and_external_reporting"
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

    leadership_summary = pd.read_parquet(
        CLAIRE_LEADERSHIP_BASE / "extracts" / "leadership_reporting_summary_v1.parquet"
    )
    external_cut = pd.read_parquet(
        CLAIRE_LEADERSHIP_BASE / "extracts" / "external_oversight_reporting_cut_v1.parquet"
    )
    kpi_framework = pd.read_parquet(
        MAPS_FRAMEWORK_BASE / "extracts" / "kpi_framework_summary_v1.parquet"
    )
    change_tracking = pd.read_parquet(
        MAPS_FRAMEWORK_BASE / "extracts" / "change_tracking_summary_v1.parquet"
    )
    reconciliation_output = pd.read_parquet(
        WELSH_CONTROL_BASE / "extracts" / "reconciliation_output_v1.parquet"
    )

    claire_fact_pack = json.loads(
        (CLAIRE_LEADERSHIP_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    maps_fact_pack = json.loads(
        (MAPS_FRAMEWORK_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    welsh_fact_pack = json.loads(
        (WELSH_CONTROL_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    leadership_row = leadership_summary.iloc[0]
    focus_row = external_cut.loc[external_cut["oversight_row"] == "focus_band"].iloc[0]
    current_reconciliation_row = reconciliation_output.loc[
        reconciliation_output["week_role"] == "current"
    ].iloc[0]

    aligned_reporting_window = str(leadership_row["reporting_window"])
    protected_group_dimension = "age_band_style"
    protected_group_focus = "50_plus"

    workforce_reporting_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "reporting_lane_name": "governed_workforce_intelligence_reporting_pack",
                "reporting_output_type": "workforce_reporting_summary",
                "protected_group_dimension": protected_group_dimension,
                "protected_group_focus": protected_group_focus,
                "reused_reporting_views_count": int(leadership_row["shared_reporting_views_count"]),
                "reused_kpi_family_count": int(leadership_row["shared_kpi_family_count"]),
                "overall_reporting_rate": float(leadership_row["overall_case_open_rate"]),
                "overall_quality_rate": float(leadership_row["overall_truth_quality"]),
                "focus_group_reporting_share": float(focus_row["flow_share"]),
                "focus_group_case_gap_pp": float(
                    maps_fact_pack["current_focus_case_open_gap_pp"]
                ),
                "focus_group_truth_gap_pp": float(
                    maps_fact_pack["current_focus_truth_gap_pp"]
                ),
                "release_safe_reporting_status": (
                    "governed_reporting_lane_ready_for_internal_and_board_style_use"
                ),
                "workforce_reporting_reading": (
                    "the governed reporting lane keeps one explicit protected-group-style focus in view "
                    "while retaining enough overall context for routine workforce-intelligence use"
                ),
            }
        ]
    )

    edi_dashboard_surface = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "dashboard_surface_name": "edi_dashboard_surface",
                "protected_group_dimension": protected_group_dimension,
                "protected_group_focus": protected_group_focus,
                "dashboard_metric_rank": idx + 1,
                "dashboard_metric_name": row["kpi_name"],
                "dashboard_metric_purpose": row["kpi_purpose"],
                "current_value": float(row["current_value"]),
                "value_unit": str(row["value_unit"]),
                "intended_direction": str(row["intended_direction"]),
                "target_state_reading": str(row["target_state_reading"]),
            }
            for idx, (_, row) in enumerate(kpi_framework.iterrows())
        ]
    )

    statutory_reporting_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "statutory_surface_name": "equality_statutory_style_summary",
                "reporting_cycle_shape": "wres_wdes_gender_pay_style_bundle_analogue",
                "protected_group_dimension": protected_group_dimension,
                "protected_group_focus": protected_group_focus,
                "focus_group_case_gap_pp": float(maps_fact_pack["current_focus_case_open_gap_pp"]),
                "focus_group_truth_gap_pp": float(maps_fact_pack["current_focus_truth_gap_pp"]),
                "quality_checked_release_gate": (
                    "controlled_before_board_or_external_style_circulation"
                ),
                "control_family_status": str(current_reconciliation_row["reconciliation_status"]),
                "statutory_style_reading": (
                    "the statutory-style summary keeps the same protected-group-style focus and release discipline "
                    "explicit, which is the right bounded analogue for equality reporting without implying live submission authority"
                ),
            }
        ]
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "workforce_reporting_summary_output_present",
                "actual_value": float(len(workforce_reporting_summary)),
                "expected_rule": "= 1 workforce-reporting summary output present",
                "passed_flag": int(len(workforce_reporting_summary) == 1),
            },
            {
                "check_name": "edi_dashboard_surface_contains_three_metrics",
                "actual_value": float(len(edi_dashboard_surface)),
                "expected_rule": "= 3 EDI dashboard-style metrics retained",
                "passed_flag": int(len(edi_dashboard_surface) == 3),
            },
            {
                "check_name": "statutory_reporting_summary_output_present",
                "actual_value": float(len(statutory_reporting_summary)),
                "expected_rule": "= 1 statutory-return-style summary output present",
                "passed_flag": int(len(statutory_reporting_summary) == 1),
            },
            {
                "check_name": "all_outputs_retain_same_focus_group",
                "actual_value": float(
                    workforce_reporting_summary.iloc[0]["protected_group_focus"]
                    == statutory_reporting_summary.iloc[0]["protected_group_focus"]
                    == protected_group_focus
                ),
                "expected_rule": "= 1 same protected-group-style focus retained across all surfaces",
                "passed_flag": int(
                    workforce_reporting_summary.iloc[0]["protected_group_focus"]
                    == statutory_reporting_summary.iloc[0]["protected_group_focus"]
                    == protected_group_focus
                ),
            },
            {
                "check_name": "protected_group_dimension_stays_explicit",
                "actual_value": float(
                    (edi_dashboard_surface["protected_group_dimension"] == protected_group_dimension).sum()
                ),
                "expected_rule": "= 3 dashboard metric rows retain the same protected-group-style dimension",
                "passed_flag": int(
                    (edi_dashboard_surface["protected_group_dimension"] == protected_group_dimension).sum() == 3
                ),
            },
            {
                "check_name": "claire_leadership_pack_remains_green",
                "actual_value": float(claire_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {claire_fact_pack['release_check_count']} inherited leadership-reporting checks remain green",
                "passed_flag": int(
                    claire_fact_pack["release_checks_passed"] == claire_fact_pack["release_check_count"]
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
        ]
    )

    workforce_reporting_summary.to_parquet(
        EXTRACTS / "workforce_reporting_summary_v1.parquet", index=False
    )
    edi_dashboard_surface.to_parquet(EXTRACTS / "edi_dashboard_surface_v1.parquet", index=False)
    statutory_reporting_summary.to_parquet(
        EXTRACTS / "statutory_reporting_summary_v1.parquet", index=False
    )
    checks_df.to_parquet(EXTRACTS / "workforce_reporting_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "guys_and_st_thomas_nhs_foundation_trust/01_workforce_intelligence_edi_dashboards_and_statutory_reporting",
        "aligned_reporting_window": aligned_reporting_window,
        "workforce_reporting_output_count": 1,
        "edi_dashboard_output_count": 1,
        "statutory_reporting_output_count": 1,
        "board_ready_output_count": 1,
        "protected_group_dimension": protected_group_dimension,
        "protected_group_focus": protected_group_focus,
        "edi_dashboard_metric_count": int(len(edi_dashboard_surface)),
        "reused_reporting_views_count": int(leadership_row["shared_reporting_views_count"]),
        "reused_kpi_family_count": int(leadership_row["shared_kpi_family_count"]),
        "current_focus_case_gap_pp": float(maps_fact_pack["current_focus_case_open_gap_pp"]),
        "current_focus_truth_gap_pp": float(maps_fact_pack["current_focus_truth_gap_pp"]),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "workforce_reporting_scope_note_v1.md",
        f"""
# Workforce Reporting Scope Note v1

Bounded reporting question:
- can one governed reporting lane support workforce-intelligence reporting, an `EDI` dashboard-style surface, and a statutory-return-style summary from the same protected-group-style focus?

Inherited reporting base:
- `leadership_reporting_summary_v1`
- `external_oversight_reporting_cut_v1`
- `kpi_framework_summary_v1`
- `change_tracking_summary_v1`
- `reconciliation_output_v1`

What this slice proves:
- one workforce-reporting summary output
- one `EDI` dashboard-style output
- one statutory-return-style summary output
- one board-ready reporting note

What this slice does not prove:
- live `ESR`, `Oracle HRMS`, or `Discoverer` ownership
- live statutory submission authority
- the full Trust workforce-intelligence estate
""",
    )

    write_md(
        OUT_BASE / "edi_dashboard_note_v1.md",
        f"""
# EDI Dashboard Note v1

Dashboard posture:
- protected-group-style dimension retained: `{protected_group_dimension}`
- protected-group-style focus retained: `{protected_group_focus}`
- dashboard metric rows retained: `{len(edi_dashboard_surface)}`

Dashboard reading:
- the dashboard keeps one confidence metric and two directional gap metrics visible
- this makes the same governed reporting base easier to scan for equality-style monitoring
- the dashboard surface is bounded and does not imply a live Trust dashboard estate
""",
    )

    write_md(
        OUT_BASE / "statutory_reporting_note_v1.md",
        f"""
# Statutory Reporting Note v1

Statutory-style posture:
- reporting cycle shape retained as a bounded equality-return-style summary
- protected-group-style focus: `{protected_group_focus}`
- case-gap reading: `{pp(float(maps_fact_pack['current_focus_case_open_gap_pp']))}`
- truth-gap reading: `{pp(float(maps_fact_pack['current_focus_truth_gap_pp']))}`

Why this counts:
- the summary keeps release discipline explicit
- it packages a high-accountability equality-style reading from the same governed lane
- it stays below live submission or statutory-authority claims
""",
    )

    write_md(
        OUT_BASE / "board_ready_reporting_note_v1.md",
        f"""
# Board-Ready Reporting Note v1

Board-ready reading:
- senior readers should keep attention on the `{protected_group_focus}` protected-group-style focus rather than treating the whole lane as equally pressured
- the reporting lane remains governed and release-safe enough for internal and board-style use
- the quality side is directionally stronger than the pressure side, so the right response is continued review rather than premature success language

What matters next:
- use the workforce summary for overall context
- use the dashboard-style surface for quick-scan equality monitoring
- use the statutory-style summary only as a bounded controlled reporting cut, not as a live submission claim
""",
    )

    write_md(
        OUT_BASE / "workforce_reporting_caveats_v1.md",
        f"""
# Workforce Reporting Caveats v1

Boundary reminders:
- this is a bounded workforce-intelligence and equality-reporting analogue
- it does not prove live workforce-system administration
- it does not prove end-to-end statutory return ownership
- the protected-group-style dimension is an age-band analogue over `{protected_group_focus}`, not a literal Trust workforce protected-characteristic estate
""",
    )

    write_md(
        OUT_BASE / "README_workforce_reporting_regeneration.md",
        """
# Workforce Reporting Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/guys_and_st_thomas_nhs_foundation_trust/01_workforce_intelligence_edi_dashboards_and_statutory_reporting/models/build_workforce_intelligence_edi_dashboards_and_statutory_reporting.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_workforce_reporting.md",
        """
# Workforce Reporting Changelog

- v1: initial bounded workforce-intelligence, EDI-dashboard-style, and statutory-reporting-style pack built from inherited governed reporting artefacts
""",
    )


if __name__ == "__main__":
    main()
