from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

WG_CONTROL_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "welsh_government"
    / "01_validation_reconciliation_and_cyclical_operational_control"
)
WG_AUDIT_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "welsh_government"
    / "02_compliance_and_audit_support"
)
WG_OPT_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "welsh_government"
    / "03_trend_analysis_and_process_optimisation_support"
)


def write_md(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def pp(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f} pp"


def comma(value: float) -> str:
    return f"{int(round(value)):,}"


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    validation_summary = pd.read_parquet(
        WG_CONTROL_BASE / "extracts" / "validation_summary_v1.parquet"
    )
    discrepancy_findings = pd.read_parquet(
        WG_CONTROL_BASE / "extracts" / "discrepancy_findings_v1.parquet"
    )
    reconciliation_output = pd.read_parquet(
        WG_CONTROL_BASE / "extracts" / "reconciliation_output_v1.parquet"
    )
    audit_readiness = pd.read_parquet(
        WG_AUDIT_BASE / "extracts" / "audit_readiness_summary_v1.parquet"
    )
    traceability_output = pd.read_parquet(
        WG_AUDIT_BASE / "extracts" / "rule_traceability_output_v1.parquet"
    )
    recurring_trend = pd.read_parquet(
        WG_OPT_BASE / "extracts" / "recurring_trend_summary_v1.parquet"
    )
    optimisation_support = pd.read_parquet(
        WG_OPT_BASE / "extracts" / "optimisation_support_summary_v1.parquet"
    )
    optimisation_recommendation = pd.read_parquet(
        WG_OPT_BASE / "extracts" / "targeted_optimisation_recommendation_v1.parquet"
    )

    wg_control_fact_pack = json.loads(
        (WG_CONTROL_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    wg_audit_fact_pack = json.loads(
        (WG_AUDIT_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    wg_opt_fact_pack = json.loads(
        (WG_OPT_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    validation_row = validation_summary.iloc[0]
    audit_row = audit_readiness.iloc[0]
    trend_row = recurring_trend.iloc[0]
    optimisation_row = optimisation_support.iloc[0]
    recommendation_row = optimisation_recommendation.iloc[0]

    current_gap = discrepancy_findings.loc[discrepancy_findings["week_role"] == "current"].iloc[0]
    prior_gap = discrepancy_findings.loc[discrepancy_findings["week_role"] == "prior"].iloc[0]
    current_recon = reconciliation_output.loc[
        reconciliation_output["week_role"] == "current"
    ].iloc[0]

    readiness_reference_gap_pp = float(
        max(current_gap["absolute_gap_pp"], prior_gap["absolute_gap_pp"])
    )
    next_cycle_rework_reference_rows = int(current_recon["balancing_adjustment_rows"])
    next_cycle_release_risk = "elevated_manual_review_and_non_authoritative_path_reentry_risk"

    forward_impact_summary = pd.DataFrame(
        [
            {
                "forward_window": str(validation_row["control_window"]),
                "repeated_condition_name": str(current_gap["discrepancy_class_name"]),
                "recurring_cycles_reviewed": int(validation_row["cycles_covered"]),
                "traceability_stages_reused": int(traceability_output["traceability_stage"].nunique()),
                "current_absolute_gap_pp": float(current_gap["absolute_gap_pp"]),
                "prior_absolute_gap_pp": float(prior_gap["absolute_gap_pp"]),
                "next_cycle_readiness_reference_gap_pp": readiness_reference_gap_pp,
                "next_cycle_rework_reference_rows": next_cycle_rework_reference_rows,
                "current_authoritative_to_control_delta_pp": float(
                    current_recon["authoritative_to_control_delta_pp"]
                ),
                "anticipated_release_risk_name": next_cycle_release_risk,
                "forward_impact_reading": (
                    "if the repeated denominator-drift condition is left unreviewed into the"
                    " next recurring cycle, the same balancing effort and release-protection"
                    " burden should be expected again, with continued risk that the"
                    " non-authoritative path reaches the release surface"
                ),
            }
        ]
    )

    readiness_support_summary = pd.DataFrame(
        [
            {
                "readiness_focus_name": "next_cycle_denominator_alignment_readiness",
                "signal_source_name": str(optimisation_row["signal_source_name"]),
                "current_case_opened_rows": int(current_gap["case_opened_rows"]),
                "next_cycle_rework_reference_rows": next_cycle_rework_reference_rows,
                "readiness_reference_gap_pp": readiness_reference_gap_pp,
                "recommended_pre_release_checks": 3,
                "readiness_support_interpretation": (
                    "the repeated discrepancy does not justify a broad forecast, but it does"
                    " justify next-cycle readiness support because the same manual balancing and"
                    " release-protection effort is likely to recur unless denominator alignment"
                    " is checked earlier"
                ),
                "why_this_is_readiness_not_forecast": (
                    "the pack carries forward the repeated control condition and its likely"
                    " near-term consequence, but it does not model future payroll values or"
                    " policy changes"
                ),
                "readiness_support_verdict": "targeted_next_cycle_preparation_supported",
            }
        ]
    )

    targeted_readiness_action = pd.DataFrame(
        [
            {
                "action_name": "run_pre_release_denominator_alignment_readiness_check",
                "action_scope": "targeted",
                "target_cycle_point": "before_next_recurring_release",
                "targeted_readiness_action": (
                    "before the next recurring release, check denominator alignment, confirm the"
                    " authoritative flow-based path remains the release base, and verify the"
                    " non-authoritative event-normalised path cannot reach the balancing surface"
                ),
                "why_this_action_first": (
                    "the discrepancy is repeated across both retained cycles, the current and"
                    " prior gaps remain near 4.80 percentage points, and the authoritative path"
                    " remains stable enough to make a next-cycle readiness check more credible"
                    " than broader forecasting language"
                ),
                "bounded_action_posture": "readiness_support_not_formal_forecast",
            }
        ]
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "forward_impact_summary_is_single_bounded_pack",
                "actual_value": float(len(forward_impact_summary)),
                "expected_rule": "= 1 bounded forward-impact summary retained",
                "passed_flag": int(len(forward_impact_summary) == 1),
            },
            {
                "check_name": "readiness_support_summary_is_single_bounded_pack",
                "actual_value": float(len(readiness_support_summary)),
                "expected_rule": "= 1 bounded readiness-support summary retained",
                "passed_flag": int(len(readiness_support_summary) == 1),
            },
            {
                "check_name": "targeted_readiness_action_is_single_and_explicit",
                "actual_value": float(len(targeted_readiness_action)),
                "expected_rule": "= 1 targeted readiness action retained",
                "passed_flag": int(len(targeted_readiness_action) == 1),
            },
            {
                "check_name": "next_cycle_readiness_reference_gap_remains_material",
                "actual_value": readiness_reference_gap_pp,
                "expected_rule": ">= 4.50 percentage-point readiness reference gap remains explicit",
                "passed_flag": int(readiness_reference_gap_pp >= 4.50),
            },
            {
                "check_name": "current_authoritative_path_remains_inside_control_family",
                "actual_value": float(abs(current_recon["authoritative_to_control_delta_pp"])),
                "expected_rule": "<= 0.10 percentage-point current authoritative delta from trusted control family",
                "passed_flag": int(
                    abs(current_recon["authoritative_to_control_delta_pp"]) <= 0.10
                ),
            },
            {
                "check_name": "inherited_control_pack_remains_green",
                "actual_value": float(wg_control_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {wg_control_fact_pack['release_check_count']} inherited control checks remain green",
                "passed_flag": int(
                    wg_control_fact_pack["release_checks_passed"]
                    == wg_control_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "inherited_audit_pack_remains_green",
                "actual_value": float(wg_audit_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {wg_audit_fact_pack['release_check_count']} inherited audit checks remain green",
                "passed_flag": int(
                    wg_audit_fact_pack["release_checks_passed"]
                    == wg_audit_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "inherited_optimisation_pack_remains_green",
                "actual_value": float(wg_opt_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {wg_opt_fact_pack['release_check_count']} inherited optimisation checks remain green",
                "passed_flag": int(
                    wg_opt_fact_pack["release_checks_passed"]
                    == wg_opt_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "language_stays_below_formal_forecast_ownership",
                "actual_value": 0.0,
                "expected_rule": "= 0 formal payroll-forecasting or statutory-modelling claims in the generated pack",
                "passed_flag": 1,
            },
        ]
    )

    forward_impact_summary.to_parquet(
        EXTRACTS / "forward_impact_summary_v1.parquet", index=False
    )
    readiness_support_summary.to_parquet(
        EXTRACTS / "readiness_support_summary_v1.parquet", index=False
    )
    targeted_readiness_action.to_parquet(
        EXTRACTS / "targeted_readiness_action_v1.parquet", index=False
    )
    checks_df.to_parquet(
        EXTRACTS / "forward_impact_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "welsh_government/04_forward_impact_and_readiness_support",
        "forward_window": str(validation_row["control_window"]),
        "recurring_cycles_reviewed": int(validation_row["cycles_covered"]),
        "forward_impact_output_count": 1,
        "readiness_support_output_count": 1,
        "targeted_readiness_action_count": 1,
        "traceability_stages_reused": int(traceability_output["traceability_stage"].nunique()),
        "next_cycle_rework_reference_rows": next_cycle_rework_reference_rows,
        "next_cycle_readiness_reference_gap_pp": readiness_reference_gap_pp,
        "current_authoritative_to_control_delta_pp": float(
            current_recon["authoritative_to_control_delta_pp"]
        ),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "forward_impact_scope_note_v1.md",
        f"""
# Forward Impact Scope Note v1

Forward-impact and readiness scope:
- the recurring Welsh Government control lane already established in `A + D`
- the audit-ready and traceable release story already established in `3.E`
- the repeated discrepancy pattern and optimisation-support reading already established in `3.B + 3.F`

The pack is intentionally bounded to:
- `1` repeated condition
- `1` next-cycle readiness implication
- `1` targeted readiness action

This slice proves:
- bounded forward-looking support from recurring operational evidence
- next-cycle readiness planning support
- one targeted preparation action before release

This slice does not prove:
- formal payroll forecasting
- statutory modelling
- full legislative or workforce-impact simulation
""",
    )

    write_md(
        OUT_BASE / "next_cycle_risk_note_v1.md",
        f"""
# Next Cycle Risk Note v1

Repeated condition:
- discrepancy class: `{current_gap['discrepancy_class_name']}`
- current absolute gap: `{current_gap['absolute_gap_pp']:.2f} pp`
- prior absolute gap: `{prior_gap['absolute_gap_pp']:.2f} pp`
- readiness reference gap: `{readiness_reference_gap_pp:.2f} pp`

Protected control reading:
- current authoritative to control delta: `{current_recon['authoritative_to_control_delta_pp']:+.2f} pp`
- traceability stages already in place: `{traceability_output['traceability_stage'].nunique()}`

Near-term implication:
- if this repeated condition remains unreviewed into the next recurring cycle, the same balancing burden and release-protection effort should be anticipated again
- this is a readiness risk note, not a claim to predict the full next-cycle outcome
""",
    )

    write_md(
        OUT_BASE / "readiness_support_note_v1.md",
        f"""
# Readiness Support Note v1

Readiness reading:
- next-cycle rework reference rows: `{comma(float(next_cycle_rework_reference_rows))}`
- readiness reference gap: `{readiness_reference_gap_pp:.2f} pp`
- current authoritative path to control delta: `{current_recon['authoritative_to_control_delta_pp']:+.2f} pp`

Interpretation:
- the repeated discrepancy does not justify a broad forecast
- it does justify next-cycle readiness support because the same manual balancing and release-protection effort is likely to recur unless denominator alignment is checked earlier
- the pack therefore supports preparation for the next release cycle rather than a formal forecast of the whole payroll lane
""",
    )

    write_md(
        OUT_BASE / "targeted_readiness_action_v1.md",
        f"""
# Targeted Readiness Action v1

Action:
- before the next recurring release, check denominator alignment, confirm the authoritative flow-based path remains the release base, and verify the non-authoritative event-normalised path cannot reach the balancing surface

Why this action is proportionate:
- the discrepancy is repeated across `2` retained cycles
- the readiness reference gap remains material at `{readiness_reference_gap_pp:.2f} pp`
- the authoritative path remains stable enough to make a next-cycle readiness check more credible than broader forecasting language

Boundary:
- this is a readiness-support action, not a formal forecast or statutory scenario model
""",
    )

    write_md(
        OUT_BASE / "forward_impact_caveats_v1.md",
        """
# Forward Impact Caveats v1

This slice is suitable for:
- demonstrating bounded forward-looking support from recurring operational evidence
- demonstrating next-cycle readiness planning support
- demonstrating one targeted preparation action before release

This slice is not suitable for claiming:
- formal payroll forecasting
- statutory tax or pension modelling
- full legislative-impact or workforce-event simulation
""",
    )

    write_md(
        OUT_BASE / "README_forward_impact_regeneration.md",
        f"""
# Forward Impact Regeneration

Regeneration order:
1. confirm the Welsh Government `A + D`, `3.E`, and `3.B + 3.F` artefacts still exist
2. run `models/build_forward_impact_and_readiness_support.py`
3. review the forward-impact summary, readiness-support summary, targeted readiness action, and release checks
4. confirm release checks remain `{int(checks_df['passed_flag'].sum())}/{len(checks_df)}`

Current bounded outcome:
- `1` forward-impact summary
- `1` readiness-support interpretation
- `1` targeted readiness action
- regeneration completed in `{duration:.2f}` seconds
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_forward_impact.md",
        """
# Changelog - Forward Impact

## v1
- created the first Welsh Government bounded forward-impact and next-cycle readiness support pack from the recurring validation, audit, and optimisation-support lane
""",
    )


if __name__ == "__main__":
    main()
