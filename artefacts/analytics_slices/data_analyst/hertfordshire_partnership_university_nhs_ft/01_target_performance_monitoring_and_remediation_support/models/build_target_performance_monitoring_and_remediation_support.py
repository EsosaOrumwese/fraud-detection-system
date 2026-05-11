from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_ANALYST_DIR = BASE_DIR.parent.parent
SOURCE_D_DIR = DATA_ANALYST_DIR / "inhealth_group" / "03_trend_risk_and_opportunity_identification"
SOURCE_E_DIR = DATA_ANALYST_DIR / "inhealth_group" / "04_process_and_efficiency_improvement_support"
SOURCE_CB_DIR = DATA_ANALYST_DIR / "claire_house" / "02_reporting_dashboards_and_visualisation"
EXTRACTS_DIR = BASE_DIR / "extracts"
METRICS_DIR = BASE_DIR / "metrics"


def ensure_dirs() -> None:
    EXTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]:
    monthly_trend = pd.read_parquet(
        SOURCE_D_DIR / "extracts" / "monthly_trend_compare_v1.parquet"
    )
    monthly_focus = pd.read_parquet(
        SOURCE_D_DIR / "extracts" / "monthly_risk_opportunity_focus_v1.parquet"
    )
    targeted_review = pd.read_parquet(
        SOURCE_E_DIR / "extracts" / "targeted_review_support_v1.parquet"
    )
    claire_detail = pd.read_parquet(
        SOURCE_CB_DIR / "extracts" / "trusted_reporting_ad_hoc_detail_v1.parquet"
    )
    fact_pack_d = json.loads(
        (SOURCE_D_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    fact_pack_e = json.loads(
        (SOURCE_E_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    return monthly_trend, monthly_focus, targeted_review, claire_detail, fact_pack_d, fact_pack_e


def build_target_monitoring(
    monthly_trend: pd.DataFrame,
    targeted_review: pd.DataFrame,
) -> pd.DataFrame:
    baseline = monthly_trend.sort_values("month_start_date").iloc[0]
    review = targeted_review.sort_values("month_start_date").reset_index(drop=True)
    merged = monthly_trend.sort_values("month_start_date").reset_index(drop=True).merge(
        review[
            [
                "month_start_date",
                "focus_band",
                "flow_share",
                "case_open_share",
                "truth_share",
                "burden_minus_yield_share",
            ]
        ],
        on="month_start_date",
        how="inner",
        validate="one_to_one",
    )
    merged["target_reference_type"] = "stable_overall_baseline_and_peer_comparison"
    merged["overall_case_open_rate_reference"] = float(baseline["case_open_rate"])
    merged["overall_truth_rate_reference"] = float(baseline["case_truth_rate"])
    merged["overall_case_open_delta_to_reference"] = (
        merged["case_open_rate"] - merged["overall_case_open_rate_reference"]
    )
    merged["overall_truth_delta_to_reference"] = (
        merged["case_truth_rate"] - merged["overall_truth_rate_reference"]
    )
    merged["target_monitoring_status"] = "stable_lane_with_focus_shortfall"
    return merged[
        [
            "month_start_date",
            "target_reference_type",
            "flow_rows",
            "case_open_rate",
            "overall_case_open_rate_reference",
            "overall_case_open_delta_to_reference",
            "case_truth_rate",
            "overall_truth_rate_reference",
            "overall_truth_delta_to_reference",
            "fifty_plus_share",
            "focus_band",
            "flow_share",
            "case_open_share",
            "truth_share",
            "burden_minus_yield_share",
            "target_monitoring_status",
        ]
    ]


def build_shortfall_summary(monthly_focus: pd.DataFrame) -> pd.DataFrame:
    focus = (
        monthly_focus.loc[monthly_focus["priority_attention_flag"] == 1]
        .sort_values("month_start_date")
        .reset_index(drop=True)
        .copy()
    )
    focus["shortfall_reference_type"] = "peer_band_average"
    focus["case_open_gap_pp"] = focus["case_open_gap_to_peer"] * 100
    focus["truth_quality_gap_pp"] = focus["case_truth_gap_to_peer"] * 100
    focus["shortfall_signal"] = "higher_case_pressure_and_lower_truth_quality_than_peers"
    focus["shortfall_status"] = "requires_remediation_attention"
    return focus[
        [
            "month_start_date",
            "amount_band",
            "flow_share",
            "case_open_rate",
            "peer_case_open_rate",
            "case_open_gap_pp",
            "case_truth_rate",
            "peer_case_truth_rate",
            "truth_quality_gap_pp",
            "shortfall_reference_type",
            "shortfall_signal",
            "shortfall_status",
        ]
    ]


def build_remediation_support_summary(
    targeted_review: pd.DataFrame,
    shortfall_summary: pd.DataFrame,
    claire_detail: pd.DataFrame,
) -> pd.DataFrame:
    current = targeted_review.sort_values("month_start_date").iloc[-1]
    claire_focus = claire_detail.sort_values("priority_rank").iloc[0]
    window_start = pd.to_datetime(targeted_review["month_start_date"]).min()
    window_end = pd.to_datetime(targeted_review["month_start_date"]).max()
    return pd.DataFrame(
        [
            {
                "reporting_window_start": str(window_start.date()),
                "reporting_window_end": str(window_end.date()),
                "focus_band": str(current["focus_band"]),
                "target_reference_type": "stable_overall_baseline_and_peer_comparison",
                "whole_lane_case_open_change_from_start_pp": float(
                    current["case_open_change_from_start"] * 100
                ),
                "whole_lane_truth_change_from_start_pp": float(
                    current["truth_change_from_start"] * 100
                ),
                "current_focus_case_open_gap_to_peer_pp": float(
                    current["case_open_gap_to_peer"] * 100
                ),
                "current_focus_truth_gap_to_peer_pp": float(
                    current["case_truth_gap_to_peer"] * 100
                ),
                "current_focus_burden_minus_yield_gap_pp": float(
                    current["burden_minus_yield_share"] * 100
                ),
                "current_focus_case_open_rate": float(claire_focus["case_open_rate"]),
                "current_focus_truth_quality": float(claire_focus["case_truth_rate"]),
                "recommended_follow_up": "review focused queue rules or escalation handling before broad service-wide intervention",
                "remediation_support_logic": "whole-lane movement remains small while the focus pocket stays materially worse than peers",
                "follow_up_scope": "targeted_remediation_support",
            }
        ]
    )


def build_release_checks(
    target_monitoring: pd.DataFrame,
    shortfall_summary: pd.DataFrame,
    remediation_support: pd.DataFrame,
) -> pd.DataFrame:
    current = remediation_support.iloc[0]
    checks = [
        {
            "check_name": "target_monitoring_covers_expected_months",
            "actual_value": float(len(target_monitoring)),
            "expected_rule": "= 3 monthly target-monitoring rows present",
            "passed_flag": int(len(target_monitoring) == 3),
        },
        {
            "check_name": "shortfall_summary_covers_persistent_focus_months",
            "actual_value": float(len(shortfall_summary)),
            "expected_rule": "= 3 shortfall rows for the persistent focus pocket",
            "passed_flag": int(len(shortfall_summary) == 3),
        },
        {
            "check_name": "focus_band_is_consistent_across_shortfall_pack",
            "actual_value": float(shortfall_summary["amount_band"].nunique()),
            "expected_rule": "= 1 focus band carried through the shortfall pack",
            "passed_flag": int(shortfall_summary["amount_band"].nunique() == 1),
        },
        {
            "check_name": "current_focus_burden_gap_remains_positive",
            "actual_value": float(current["current_focus_burden_minus_yield_gap_pp"]),
            "expected_rule": "> 0 current focus burden-minus-yield gap remains positive",
            "passed_flag": int(current["current_focus_burden_minus_yield_gap_pp"] > 0),
        },
        {
            "check_name": "whole_lane_case_open_change_remains_small",
            "actual_value": float(abs(current["whole_lane_case_open_change_from_start_pp"])),
            "expected_rule": "< 0.10 pp whole-lane case-open movement remains small",
            "passed_flag": int(abs(current["whole_lane_case_open_change_from_start_pp"]) < 0.10),
        },
        {
            "check_name": "whole_lane_truth_change_remains_small",
            "actual_value": float(abs(current["whole_lane_truth_change_from_start_pp"])),
            "expected_rule": "< 0.10 pp whole-lane truth-quality movement remains small",
            "passed_flag": int(abs(current["whole_lane_truth_change_from_start_pp"]) < 0.10),
        },
    ]
    return pd.DataFrame(checks)


def build_fact_pack(
    target_monitoring: pd.DataFrame,
    shortfall_summary: pd.DataFrame,
    remediation_support: pd.DataFrame,
    release_checks: pd.DataFrame,
    fact_pack_d: dict,
) -> dict:
    current = remediation_support.iloc[0]
    return {
        "slice": "hertfordshire_partnership_university_nhs_ft/01_target_performance_monitoring_and_remediation_support",
        "reporting_window_count": int(len(target_monitoring)),
        "reporting_window_start": str(pd.to_datetime(target_monitoring["month_start_date"]).min().date()),
        "reporting_window_end": str(pd.to_datetime(target_monitoring["month_start_date"]).max().date()),
        "kpi_family_count": 4,
        "target_reference_count": 2,
        "shortfall_pocket_count": int(shortfall_summary["amount_band"].nunique()),
        "focus_band": str(current["focus_band"]),
        "current_focus_case_open_gap_to_peer_pp": float(current["current_focus_case_open_gap_to_peer_pp"]),
        "current_focus_truth_gap_to_peer_pp": float(current["current_focus_truth_gap_to_peer_pp"]),
        "current_focus_burden_minus_yield_gap_pp": float(current["current_focus_burden_minus_yield_gap_pp"]),
        "whole_lane_case_open_change_from_start_pp": float(current["whole_lane_case_open_change_from_start_pp"]),
        "whole_lane_truth_change_from_start_pp": float(current["whole_lane_truth_change_from_start_pp"]),
        "remediation_support_output_count": int(len(remediation_support)),
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "inherited_trend_release_checks_passed": int(fact_pack_d["release_checks_passed"]),
    }


def write_notes(fact_pack: dict) -> None:
    files = {
        BASE_DIR / "target_performance_scope_note_v1.md": f"""# Target Performance Scope Note v1

Bounded scope:
- one governed three-month service-performance lane
- one target-style monitoring pack
- one explicit shortfall pocket
- one remediation-support reading

Window:
- `{fact_pack['reporting_window_start']}` to `{fact_pack['reporting_window_end']}`
""",
        BASE_DIR / "target_kpi_definition_note_v1.md": """# Target KPI Definition Note v1

Target-style KPI families:
- overall case-open rate
- overall truth quality
- focus-band workload share
- focus-band burden-versus-peer gap

Reference posture:
- stable overall baseline for whole-lane monitoring
- peer-band average for the shortfall pocket

This is a platform-side target analogue, not a literal NHS access-threshold copy.
""",
        BASE_DIR / "target_shortfall_note_v1.md": f"""# Target Shortfall Note v1

Selected shortfall pocket:
- `{fact_pack['focus_band']}`

Current-month shortfall evidence:
- case-open gap to peers: `{fact_pack['current_focus_case_open_gap_to_peer_pp']:+.2f} pp`
- truth-quality gap to peers: `{fact_pack['current_focus_truth_gap_to_peer_pp']:+.2f} pp`
- burden-minus-yield gap: `{fact_pack['current_focus_burden_minus_yield_gap_pp']:+.2f} pp`

Shortfall meaning:
- the lane is broadly stable overall
- the shortfall is concentrated in the focus pocket rather than spread across the whole lane
""",
        BASE_DIR / "remediation_support_note_v1.md": f"""# Remediation Support Note v1

Bounded follow-up supported by the slice:
- review focused queue rules or escalation handling before broad service-wide intervention

Why that follow-up is proportionate:
- whole-lane case-open movement from start is only `{fact_pack['whole_lane_case_open_change_from_start_pp']:+.2f} pp`
- whole-lane truth-quality movement from start is only `{fact_pack['whole_lane_truth_change_from_start_pp']:+.2f} pp`
- the focus pocket remains materially worse than peers on both pressure and truth quality
""",
        BASE_DIR / "target_performance_caveats_v1.md": """# Target Performance Caveats v1

Caveats:
- this slice proves one target-style service-performance analogue only
- it does not prove literal NHS waiting-time threshold ownership
- it does not prove service-delivery ownership or a completed operational turnaround
""",
        BASE_DIR / "README_target_performance_regeneration.md": """# Target Performance Regeneration

Regeneration steps:
1. confirm the inherited InHealth and Claire House compact outputs exist
2. run `models/build_target_performance_monitoring_and_remediation_support.py`
3. review the target-monitoring output, shortfall summary, remediation-support summary, and release checks
4. use the execution report to decide whether analytical plots are needed
""",
        BASE_DIR / "CHANGELOG_target_performance.md": """# Changelog - Target Performance Monitoring

- v1: initial target-style performance monitoring and remediation-support pack built from inherited governed monthly outputs
""",
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")


def main() -> None:
    start = time.perf_counter()
    ensure_dirs()
    monthly_trend, monthly_focus, targeted_review, claire_detail, fact_pack_d, fact_pack_e = load_inputs()
    target_monitoring = build_target_monitoring(monthly_trend, targeted_review)
    shortfall_summary = build_shortfall_summary(monthly_focus)
    remediation_support = build_remediation_support_summary(
        targeted_review, shortfall_summary, claire_detail
    )
    release_checks = build_release_checks(
        target_monitoring, shortfall_summary, remediation_support
    )
    fact_pack = build_fact_pack(
        target_monitoring, shortfall_summary, remediation_support, release_checks, fact_pack_d
    )
    fact_pack["regeneration_seconds"] = time.perf_counter() - start
    fact_pack["inherited_improvement_support_output_count"] = int(len(targeted_review))

    target_monitoring.to_parquet(
        EXTRACTS_DIR / "target_performance_monitoring_v1.parquet", index=False
    )
    shortfall_summary.to_parquet(EXTRACTS_DIR / "target_shortfall_summary_v1.parquet", index=False)
    remediation_support.to_parquet(
        EXTRACTS_DIR / "remediation_support_summary_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS_DIR / "target_performance_release_checks_v1.parquet", index=False
    )
    (METRICS_DIR / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2),
        encoding="utf-8",
    )
    write_notes(fact_pack)


if __name__ == "__main__":
    main()
