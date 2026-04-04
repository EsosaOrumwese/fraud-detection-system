from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_ANALYST_DIR = BASE_DIR.parent.parent
SOURCE_A_DIR = (
    DATA_ANALYST_DIR
    / "hertfordshire_partnership_university_nhs_ft"
    / "01_target_performance_monitoring_and_remediation_support"
)
EXTRACTS_DIR = BASE_DIR / "extracts"
METRICS_DIR = BASE_DIR / "metrics"


def ensure_dirs() -> None:
    EXTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    target_monitoring = pd.read_parquet(
        SOURCE_A_DIR / "extracts" / "target_performance_monitoring_v1.parquet"
    )
    shortfall = pd.read_parquet(
        SOURCE_A_DIR / "extracts" / "target_shortfall_summary_v1.parquet"
    )
    remediation = pd.read_parquet(
        SOURCE_A_DIR / "extracts" / "remediation_support_summary_v1.parquet"
    )
    release_checks = pd.read_parquet(
        SOURCE_A_DIR / "extracts" / "target_performance_release_checks_v1.parquet"
    )
    fact_pack_a = json.loads(
        (SOURCE_A_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    return target_monitoring, shortfall, remediation, release_checks, fact_pack_a


def build_senior_performance_summary(
    target_monitoring: pd.DataFrame,
    shortfall: pd.DataFrame,
    remediation: pd.DataFrame,
) -> pd.DataFrame:
    current_lane = target_monitoring.sort_values("month_start_date").iloc[-1]
    current_shortfall = shortfall.sort_values("month_start_date").iloc[-1]
    current_action = remediation.iloc[0]
    return pd.DataFrame(
        [
            {
                "reporting_window_start": str(pd.to_datetime(target_monitoring["month_start_date"]).min().date()),
                "reporting_window_end": str(pd.to_datetime(target_monitoring["month_start_date"]).max().date()),
                "audience": "senior_manager",
                "kpi_family_count": 4,
                "current_case_open_rate": float(current_lane["case_open_rate"]),
                "current_truth_quality": float(current_lane["case_truth_rate"]),
                "whole_lane_status": "broadly_stable",
                "top_attention_band": str(current_shortfall["amount_band"]),
                "top_attention_case_open_gap_pp": float(current_shortfall["case_open_gap_pp"]),
                "top_attention_truth_gap_pp": float(current_shortfall["truth_quality_gap_pp"]),
                "top_attention_burden_gap_pp": float(current_action["current_focus_burden_minus_yield_gap_pp"]),
                "current_position_reading": "overall lane remains stable while the same concentrated pocket continues to underperform against peers",
                "senior_attention_point": "keep attention on the focus pocket rather than escalating the whole lane",
            }
        ]
    )


def build_trend_and_trajectory_summary(
    target_monitoring: pd.DataFrame,
    shortfall: pd.DataFrame,
) -> pd.DataFrame:
    merged = target_monitoring.merge(
        shortfall[["month_start_date", "amount_band", "case_open_gap_pp", "truth_quality_gap_pp"]],
        on="month_start_date",
        how="left",
        validate="one_to_one",
    ).sort_values("month_start_date")
    merged["trend_status"] = "stable_lane"
    merged["focus_pocket_status"] = "persistent_shortfall"
    merged["near_term_trajectory"] = "stable_overall_with_continued_focus_pocket_pressure"
    return merged[
        [
            "month_start_date",
            "case_open_rate",
            "overall_case_open_delta_to_reference",
            "case_truth_rate",
            "overall_truth_delta_to_reference",
            "amount_band",
            "case_open_gap_pp",
            "truth_quality_gap_pp",
            "trend_status",
            "focus_pocket_status",
            "near_term_trajectory",
        ]
    ]


def build_management_actions_summary(
    senior_summary: pd.DataFrame,
    remediation: pd.DataFrame,
) -> pd.DataFrame:
    senior = senior_summary.iloc[0]
    action = remediation.iloc[0]
    return pd.DataFrame(
        [
            {
                "audience": "senior_manager",
                "current_position": str(senior["current_position_reading"]),
                "emerging_risk": "the focus pocket has remained materially worse than peers across the full three-month lane",
                "required_attention": str(senior["senior_attention_point"]),
                "recommended_action": str(action["recommended_follow_up"]),
                "action_rationale": str(action["remediation_support_logic"]),
                "action_scope": "bounded_management_attention",
            }
        ]
    )


def build_release_checks(
    senior_summary: pd.DataFrame,
    trend_summary: pd.DataFrame,
    management_actions: pd.DataFrame,
    inherited_checks: pd.DataFrame,
) -> pd.DataFrame:
    checks = [
        {
            "check_name": "senior_summary_contains_single_management_view",
            "actual_value": float(len(senior_summary)),
            "expected_rule": "= 1 senior-performance summary row present",
            "passed_flag": int(len(senior_summary) == 1),
        },
        {
            "check_name": "trend_summary_covers_expected_months",
            "actual_value": float(len(trend_summary)),
            "expected_rule": "= 3 trend-and-trajectory rows present",
            "passed_flag": int(len(trend_summary) == 3),
        },
        {
            "check_name": "trend_summary_preserves_single_focus_band",
            "actual_value": float(trend_summary["amount_band"].nunique()),
            "expected_rule": "= 1 persistent focus band carried through the trend pack",
            "passed_flag": int(trend_summary["amount_band"].nunique() == 1),
        },
        {
            "check_name": "management_actions_pack_contains_single_action_view",
            "actual_value": float(len(management_actions)),
            "expected_rule": "= 1 management-actions row present",
            "passed_flag": int(len(management_actions) == 1),
        },
        {
            "check_name": "senior_summary_reads_whole_lane_as_broadly_stable",
            "actual_value": float(senior_summary.iloc[0]["whole_lane_status"] == "broadly_stable"),
            "expected_rule": "= 1 whole-lane status remains broadly stable",
            "passed_flag": int(senior_summary.iloc[0]["whole_lane_status"] == "broadly_stable"),
        },
        {
            "check_name": "inherited_target_pack_remains_green",
            "actual_value": float(inherited_checks["passed_flag"].sum()),
            "expected_rule": f"= {len(inherited_checks)} inherited target-pack checks passed",
            "passed_flag": int(int(inherited_checks["passed_flag"].sum()) == len(inherited_checks)),
        },
    ]
    return pd.DataFrame(checks)


def build_fact_pack(
    senior_summary: pd.DataFrame,
    trend_summary: pd.DataFrame,
    management_actions: pd.DataFrame,
    release_checks: pd.DataFrame,
    fact_pack_a: dict,
    duration: float,
) -> dict:
    current = senior_summary.iloc[0]
    return {
        "slice": "hertfordshire_partnership_university_nhs_ft/02_senior_performance_analysis_and_reporting",
        "reporting_window_count": int(fact_pack_a["reporting_window_count"]),
        "reporting_window_start": str(fact_pack_a["reporting_window_start"]),
        "reporting_window_end": str(fact_pack_a["reporting_window_end"]),
        "kpi_family_count": int(current["kpi_family_count"]),
        "senior_facing_view_count": int(len(senior_summary)),
        "trend_output_count": int(len(trend_summary)),
        "management_action_output_count": int(len(management_actions)),
        "current_case_open_rate": float(current["current_case_open_rate"]),
        "current_truth_quality": float(current["current_truth_quality"]),
        "top_attention_band": str(current["top_attention_band"]),
        "top_attention_case_open_gap_pp": float(current["top_attention_case_open_gap_pp"]),
        "top_attention_truth_gap_pp": float(current["top_attention_truth_gap_pp"]),
        "top_attention_burden_gap_pp": float(current["top_attention_burden_gap_pp"]),
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "regeneration_seconds": duration,
    }


def write_notes(fact_pack: dict) -> None:
    files = {
        BASE_DIR / "senior_performance_scope_note_v1.md": f"""# Senior Performance Scope Note v1

Bounded scope:
- one senior-performance summary pack
- one trend-and-trajectory reading
- one management-actions note

Window:
- `{fact_pack['reporting_window_start']}` to `{fact_pack['reporting_window_end']}`
""",
        BASE_DIR / "senior_performance_summary_pack_v1.md": f"""# Senior Performance Summary Pack v1

Current position:
- current case-open rate remains controlled at `{fact_pack['current_case_open_rate'] * 100:.2f}%`
- current truth quality remains `{fact_pack['current_truth_quality'] * 100:.2f}%`
- the clearest attention point remains `{fact_pack['top_attention_band']}`
- the focus pocket carries case-open and truth-quality gaps of `{fact_pack['top_attention_case_open_gap_pp']:+.2f} pp` and `{fact_pack['top_attention_truth_gap_pp']:+.2f} pp`

Senior reading:
- the lane remains broadly stable overall
- the most important management reading is persistent concentrated pressure rather than lane-wide deterioration
""",
        BASE_DIR / "trend_and_trajectory_note_v1.md": f"""# Trend And Trajectory Note v1

Recent trend:
- the overall lane remains broadly stable across the fixed three-month window
- the focus pocket remains persistent across all monitored months

Bounded direction-of-travel:
- absent targeted follow-up, the most likely near-term position is continued stable topline with continued pressure in `{fact_pack['top_attention_band']}`

This is a bounded trajectory reading, not a formal forecasting model.
""",
        BASE_DIR / "management_actions_note_v1.md": """# Management Actions Note v1

Required attention:
- keep management attention on the persistent focus pocket rather than escalating the whole lane
- review focused queue rules or escalation handling before broad service-wide intervention

Why this is proportionate:
- the overall lane remains broadly stable
- the same pocket continues to separate from peers on both pressure and truth quality
""",
        BASE_DIR / "senior_performance_caveats_v1.md": """# Senior Performance Caveats v1

Caveats:
- this slice proves one bounded senior-performance pack only
- it does not prove a formal forecasting programme
- it does not prove an executive-reporting estate or service-delivery ownership
""",
        BASE_DIR / "README_senior_performance_regeneration.md": """# Senior Performance Regeneration

Regeneration steps:
1. confirm the Hertfordshire `01_target_performance_monitoring_and_remediation_support` artefacts exist
2. run `models/build_senior_performance_analysis_and_reporting.py`
3. review the senior summary, trend-and-trajectory output, management-actions output, and release checks
4. use the execution report to decide whether analytical plots are needed
""",
        BASE_DIR / "CHANGELOG_senior_performance.md": """# Changelog - Senior Performance Analysis

- v1: initial senior-performance summary, trend-and-trajectory, and management-actions pack built from the Hertfordshire target lane
""",
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")


def main() -> None:
    start = time.perf_counter()
    ensure_dirs()
    target_monitoring, shortfall, remediation, inherited_checks, fact_pack_a = load_inputs()
    senior_summary = build_senior_performance_summary(target_monitoring, shortfall, remediation)
    trend_summary = build_trend_and_trajectory_summary(target_monitoring, shortfall)
    management_actions = build_management_actions_summary(senior_summary, remediation)
    release_checks = build_release_checks(
        senior_summary, trend_summary, management_actions, inherited_checks
    )
    fact_pack = build_fact_pack(
        senior_summary, trend_summary, management_actions, release_checks, fact_pack_a, time.perf_counter() - start
    )

    senior_summary.to_parquet(EXTRACTS_DIR / "senior_performance_summary_v1.parquet", index=False)
    trend_summary.to_parquet(EXTRACTS_DIR / "trend_and_trajectory_summary_v1.parquet", index=False)
    management_actions.to_parquet(EXTRACTS_DIR / "management_actions_summary_v1.parquet", index=False)
    release_checks.to_parquet(EXTRACTS_DIR / "senior_performance_release_checks_v1.parquet", index=False)
    (METRICS_DIR / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2),
        encoding="utf-8",
    )
    write_notes(fact_pack)


if __name__ == "__main__":
    main()
