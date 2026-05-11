from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_A_DIR = BASE_DIR.parent / "01_target_performance_monitoring_and_remediation_support"
SOURCE_B_DIR = BASE_DIR.parent / "02_senior_performance_analysis_and_reporting"
EXTRACTS_DIR = BASE_DIR / "extracts"
METRICS_DIR = BASE_DIR / "metrics"


def ensure_dirs() -> None:
    EXTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]:
    target_monitoring = pd.read_parquet(
        SOURCE_A_DIR / "extracts" / "target_performance_monitoring_v1.parquet"
    )
    shortfall_summary = pd.read_parquet(
        SOURCE_A_DIR / "extracts" / "target_shortfall_summary_v1.parquet"
    )
    trend_summary = pd.read_parquet(
        SOURCE_B_DIR / "extracts" / "trend_and_trajectory_summary_v1.parquet"
    )
    fact_pack_a = json.loads(
        (SOURCE_A_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    fact_pack_b = json.loads(
        (SOURCE_B_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    return (
        target_monitoring,
        shortfall_summary,
        trend_summary,
        fact_pack_a,
        fact_pack_b,
    )


def build_findings(
    target_monitoring: pd.DataFrame,
    shortfall_summary: pd.DataFrame,
    fact_pack_a: dict,
) -> pd.DataFrame:
    comparator_complete = int(
        shortfall_summary["peer_case_open_rate"].notna().all()
        and shortfall_summary["peer_case_truth_rate"].notna().all()
    )
    focus_band = str(shortfall_summary["amount_band"].iloc[-1])
    current = shortfall_summary.sort_values("month_start_date").iloc[-1]
    target_reference = str(target_monitoring["target_reference_type"].iloc[-1])
    findings = [
        {
            "finding_id": "F1",
            "finding_area": "target_reference_continuity",
            "finding_type": "strength",
            "severity": "low",
            "weak_point_flag": 0,
            "finding_statement": "The governed target lane keeps one stable target-reference posture across the full three-month window, which stops the current performance reading from shifting between incompatible baselines.",
            "evidence_measure": "target_reference_count",
            "evidence_value": str(int(target_monitoring["target_reference_type"].nunique())),
            "quality_meaning": "whole-lane performance remains comparable month to month.",
        },
        {
            "finding_id": "F2",
            "finding_area": "focus_band_peer_comparator_continuity",
            "finding_type": "strength",
            "severity": "low",
            "weak_point_flag": 0,
            "finding_statement": "The same focus band remains present with complete peer-comparator coverage across all shortfall rows, which keeps the current underperformance signal reviewable rather than anecdotal.",
            "evidence_measure": "complete_peer_comparator_rows",
            "evidence_value": str(int(comparator_complete * len(shortfall_summary))),
            "quality_meaning": f"the `{focus_band}` shortfall remains supported by like-for-like peer comparison through the full window.",
        },
        {
            "finding_id": "F3",
            "finding_area": "implicit_validity_dependency",
            "finding_type": "validity_dependency",
            "severity": "medium",
            "weak_point_flag": 1,
            "finding_statement": "The shortfall reading depends on stable focus-band identity and uninterrupted peer-comparator continuity, but that dependency previously lived implicitly inside the target pack rather than as a dedicated validity control surface.",
            "evidence_measure": "current_focus_gap_pair",
            "evidence_value": f"{current['case_open_gap_pp']:+.2f} pp case-open gap and {current['truth_quality_gap_pp']:+.2f} pp truth-quality gap under `{target_reference}`",
            "quality_meaning": "if the comparator or band definition drifts, the remediation priority could be misdirected even while the topline lane still looks stable.",
        },
    ]
    return pd.DataFrame(findings)


def build_validity_impact(
    shortfall_summary: pd.DataFrame,
    target_monitoring: pd.DataFrame,
    trend_summary: pd.DataFrame,
) -> pd.DataFrame:
    current_shortfall = shortfall_summary.sort_values("month_start_date").iloc[-1]
    current_monitoring = target_monitoring.sort_values("month_start_date").iloc[-1]
    current_trend = trend_summary.sort_values("month_start_date").iloc[-1]
    return pd.DataFrame(
        [
            {
                "reporting_window_start": str(pd.to_datetime(target_monitoring["month_start_date"]).min().date()),
                "reporting_window_end": str(pd.to_datetime(target_monitoring["month_start_date"]).max().date()),
                "protected_lane_status": str(current_monitoring["target_monitoring_status"]),
                "validity_sensitive_condition": "stable focus-band identity plus complete peer-comparator continuity",
                "focus_band": str(current_shortfall["amount_band"]),
                "current_case_open_gap_pp": float(current_shortfall["case_open_gap_pp"]),
                "current_truth_quality_gap_pp": float(current_shortfall["truth_quality_gap_pp"]),
                "current_lane_case_open_rate": float(current_monitoring["case_open_rate"]),
                "current_lane_truth_quality": float(current_monitoring["case_truth_rate"]),
                "interpretation_risk_if_condition_breaks": "the concentrated shortfall could no longer be trusted as a like-for-like priority signal",
                "performance_consequence": "management attention and remediation could be misdirected away from or toward the wrong pocket",
                "current_direction_of_travel": str(current_trend["near_term_trajectory"]),
            }
        ]
    )


def build_improvement_actions(
    shortfall_summary: pd.DataFrame,
    target_monitoring: pd.DataFrame,
) -> pd.DataFrame:
    focus_band = str(shortfall_summary["amount_band"].iloc[-1])
    target_reference = str(target_monitoring["target_reference_type"].iloc[-1])
    actions = [
        {
            "action_id": "A1",
            "improvement_area": "target_reference_control",
            "action_priority": "high",
            "recommended_action": "freeze the target-reference definition as an explicit controlled input to the target pack before issue or reuse",
            "why_it_matters": "the lane should not silently switch between incompatible baselines while being read as one stable performance view",
        },
        {
            "action_id": "A2",
            "improvement_area": "peer_comparator_operability",
            "action_priority": "high",
            "recommended_action": f"require complete peer-case and peer-truth comparator coverage for every `{focus_band}` shortfall row before the pack is issued as remediation support",
            "why_it_matters": "the shortfall signal is only valid while the comparison remains like for like across the full reporting window",
        },
        {
            "action_id": "A3",
            "improvement_area": "focus_band_continuity",
            "action_priority": "medium",
            "recommended_action": f"hold the shortfall pack for review if the persistent focus band changes or the `{target_reference}` lane stops preserving one consistent pocket through the trend summary",
            "why_it_matters": "a shifted pocket can look like performance movement when it is actually a validity drift in the target-reading surface",
        },
    ]
    return pd.DataFrame(actions)


def build_release_checks(
    target_monitoring: pd.DataFrame,
    shortfall_summary: pd.DataFrame,
    trend_summary: pd.DataFrame,
    improvement_actions: pd.DataFrame,
    findings: pd.DataFrame,
    fact_pack_a: dict,
) -> pd.DataFrame:
    shortfall_focus_band = shortfall_summary["amount_band"].astype(str)
    trend_focus_band = trend_summary["amount_band"].astype(str)
    comparator_complete = int(
        shortfall_summary["peer_case_open_rate"].notna().all()
        and shortfall_summary["peer_case_truth_rate"].notna().all()
    )
    checks = [
        {
            "check_name": "target_lane_covers_expected_months",
            "actual_value": float(len(target_monitoring)),
            "expected_rule": "= 3 monthly target-lane rows present",
            "passed_flag": int(len(target_monitoring) == 3),
        },
        {
            "check_name": "peer_comparator_coverage_is_complete",
            "actual_value": float(comparator_complete * len(shortfall_summary)),
            "expected_rule": "= 3 shortfall rows with complete peer comparator coverage",
            "passed_flag": int(comparator_complete == 1),
        },
        {
            "check_name": "shortfall_pack_preserves_single_focus_band",
            "actual_value": float(shortfall_focus_band.nunique()),
            "expected_rule": "= 1 focus band carried through the shortfall pack",
            "passed_flag": int(shortfall_focus_band.nunique() == 1),
        },
        {
            "check_name": "target_lane_preserves_single_reference_type",
            "actual_value": float(target_monitoring["target_reference_type"].nunique()),
            "expected_rule": "= 1 target-reference type carried through the target lane",
            "passed_flag": int(target_monitoring["target_reference_type"].nunique() == 1),
        },
        {
            "check_name": "senior_trend_pack_preserves_same_focus_band",
            "actual_value": float(len(set(shortfall_focus_band.unique()) & set(trend_focus_band.unique()))),
            "expected_rule": "= 1 shared focus band across shortfall and senior-trend packs",
            "passed_flag": int(
                shortfall_focus_band.nunique() == 1
                and trend_focus_band.nunique() == 1
                and shortfall_focus_band.iloc[0] == trend_focus_band.iloc[0]
            ),
        },
        {
            "check_name": "explicit_validity_dependency_is_recorded",
            "actual_value": float((findings["weak_point_flag"] == 1).sum()),
            "expected_rule": "= 1 explicit validity dependency surfaced in the findings pack",
            "passed_flag": int((findings["weak_point_flag"] == 1).sum() == 1),
        },
        {
            "check_name": "inherited_target_pack_remains_green",
            "actual_value": float(fact_pack_a["release_checks_passed"]),
            "expected_rule": "= 6 inherited target-pack checks passed",
            "passed_flag": int(fact_pack_a["release_checks_passed"] == fact_pack_a["release_check_count"]),
        },
    ]
    return pd.DataFrame(checks)


def build_fact_pack(
    target_monitoring: pd.DataFrame,
    shortfall_summary: pd.DataFrame,
    findings: pd.DataFrame,
    validity_impact: pd.DataFrame,
    improvement_actions: pd.DataFrame,
    release_checks: pd.DataFrame,
    fact_pack_a: dict,
) -> dict:
    current_shortfall = shortfall_summary.sort_values("month_start_date").iloc[-1]
    return {
        "slice": "hertfordshire_partnership_university_nhs_ft/03_data_quality_and_performance_validity",
        "reporting_window_count": int(len(target_monitoring)),
        "reporting_window_start": str(pd.to_datetime(target_monitoring["month_start_date"]).min().date()),
        "reporting_window_end": str(pd.to_datetime(target_monitoring["month_start_date"]).max().date()),
        "validity_findings_count": int(len(findings)),
        "explicit_weak_point_count": int((findings["weak_point_flag"] == 1).sum()),
        "validity_impact_output_count": int(len(validity_impact)),
        "improvement_action_count": int(len(improvement_actions)),
        "complete_peer_comparator_rows": int(
            shortfall_summary["peer_case_open_rate"].notna().all()
            and shortfall_summary["peer_case_truth_rate"].notna().all()
        ) * int(len(shortfall_summary)),
        "focus_band_count": int(shortfall_summary["amount_band"].nunique()),
        "target_reference_count": int(target_monitoring["target_reference_type"].nunique()),
        "focus_band": str(current_shortfall["amount_band"]),
        "current_focus_case_open_gap_to_peer_pp": float(current_shortfall["case_open_gap_pp"]),
        "current_focus_truth_gap_to_peer_pp": float(current_shortfall["truth_quality_gap_pp"]),
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "inherited_target_release_checks_passed": int(fact_pack_a["release_checks_passed"]),
        "priority_improvement_area": "implicit_validity_dependency",
    }


def write_notes(fact_pack: dict, findings: pd.DataFrame, validity_impact: pd.DataFrame) -> None:
    weak_point = findings.loc[findings["weak_point_flag"] == 1].iloc[0]
    impact = validity_impact.iloc[0]
    files = {
        BASE_DIR / "performance_validity_scope_note_v1.md": f"""# Performance Validity Scope Note v1

Bounded scope:
- one governed target-performance lane
- one explicit validity-sensitive condition inside that lane
- one compact validity-impact reading
- one bounded improvement action set

Window:
- `{fact_pack['reporting_window_start']}` to `{fact_pack['reporting_window_end']}`
""",
        BASE_DIR / "performance_validity_findings_note_v1.md": f"""# Performance Validity Findings Note v1

Explicit weak point:
- {weak_point['finding_statement']}

Why it matters:
- the current shortfall remains concentrated in `{fact_pack['focus_band']}`
- that focus reading is only trustworthy while comparator continuity and band identity remain controlled
""",
        BASE_DIR / "validity_to_performance_note_v1.md": f"""# Validity To Performance Note v1

Performance consequence:
- {impact['performance_consequence']}

Interpretation risk:
- {impact['interpretation_risk_if_condition_breaks']}

Current protected reading:
- case-open gap to peers: `{fact_pack['current_focus_case_open_gap_to_peer_pp']:+.2f} pp`
- truth-quality gap to peers: `{fact_pack['current_focus_truth_gap_to_peer_pp']:+.2f} pp`
""",
        BASE_DIR / "performance_validity_improvement_note_v1.md": """# Performance Validity Improvement Note v1

Bounded improvement posture:
- freeze the target-reference definition as a controlled input
- require complete peer-comparator coverage before issuing the shortfall pack
- hold the pack for review if the persistent focus band changes across the reporting window

This is a protection improvement for the governed target lane, not a claim that service-process correction has already been delivered.
""",
        BASE_DIR / "performance_validity_caveats_v1.md": """# Performance Validity Caveats v1

Caveats:
- this slice proves one validity-sensitive dependency inside a governed target lane only
- it does not prove literal service-entry defects or clinical-recording ownership
- it does not prove full governance ownership or whole-service data-quality administration
""",
        BASE_DIR / "README_performance_validity_regeneration.md": """# Performance Validity Regeneration

Regeneration steps:
1. confirm the Hertfordshire `01` and `02` artefacts exist
2. run `models/build_data_quality_and_performance_validity.py`
3. review the findings pack, validity-impact pack, improvement-actions pack, and release checks
4. use the execution report to decide whether any analytical figure is actually needed
""",
        BASE_DIR / "CHANGELOG_performance_validity.md": """# Changelog - Performance Validity

- v1: initial bounded performance-validity pack built from the Hertfordshire target and senior-performance lanes
""",
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")


def main() -> None:
    start = time.perf_counter()
    ensure_dirs()
    (
        target_monitoring,
        shortfall_summary,
        trend_summary,
        fact_pack_a,
        fact_pack_b,
    ) = load_inputs()
    findings = build_findings(target_monitoring, shortfall_summary, fact_pack_a)
    validity_impact = build_validity_impact(shortfall_summary, target_monitoring, trend_summary)
    improvement_actions = build_improvement_actions(shortfall_summary, target_monitoring)
    release_checks = build_release_checks(
        target_monitoring,
        shortfall_summary,
        trend_summary,
        improvement_actions,
        findings,
        fact_pack_a,
    )
    fact_pack = build_fact_pack(
        target_monitoring,
        shortfall_summary,
        findings,
        validity_impact,
        improvement_actions,
        release_checks,
        fact_pack_a,
    )
    fact_pack["regeneration_seconds"] = time.perf_counter() - start
    fact_pack["inherited_senior_release_checks_passed"] = int(fact_pack_b["release_checks_passed"])

    findings.to_parquet(EXTRACTS_DIR / "performance_validity_findings_v1.parquet", index=False)
    validity_impact.to_parquet(EXTRACTS_DIR / "performance_validity_impact_v1.parquet", index=False)
    improvement_actions.to_parquet(
        EXTRACTS_DIR / "performance_validity_improvement_actions_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS_DIR / "performance_validity_release_checks_v1.parquet", index=False
    )
    (METRICS_DIR / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2),
        encoding="utf-8",
    )
    write_notes(fact_pack, findings, validity_impact)


if __name__ == "__main__":
    main()
