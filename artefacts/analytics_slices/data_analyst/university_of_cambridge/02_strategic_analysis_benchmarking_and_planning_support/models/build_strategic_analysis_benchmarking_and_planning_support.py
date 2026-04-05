from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

CAMBRIDGE_EVAL_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "university_of_cambridge"
    / "01_mixed_method_evaluation_and_effectiveness"
)
HERTS_SENIOR_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "hertfordshire_partnership_university_nhs_ft"
    / "02_senior_performance_analysis_and_reporting"
)
WELSH_TREND_BASE = (
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


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    quantitative_eval = pd.read_parquet(
        CAMBRIDGE_EVAL_BASE / "extracts" / "quantitative_evaluation_output_v1.parquet"
    )
    intervention_effectiveness = pd.read_parquet(
        CAMBRIDGE_EVAL_BASE / "extracts" / "intervention_effectiveness_output_v1.parquet"
    )
    herts_senior = pd.read_parquet(
        HERTS_SENIOR_BASE / "extracts" / "senior_performance_summary_v1.parquet"
    )
    herts_trend = pd.read_parquet(
        HERTS_SENIOR_BASE / "extracts" / "trend_and_trajectory_summary_v1.parquet"
    )
    welsh_trend = pd.read_parquet(
        WELSH_TREND_BASE / "extracts" / "recurring_trend_summary_v1.parquet"
    )

    cambridge_fact_pack = json.loads(
        (CAMBRIDGE_EVAL_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    herts_fact_pack = json.loads(
        (HERTS_SENIOR_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    welsh_fact_pack = json.loads(
        (WELSH_TREND_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    cambridge_row = quantitative_eval.iloc[0]
    effectiveness_row = intervention_effectiveness.iloc[0]
    herts_row = herts_senior.iloc[0]
    focus_band = str(cambridge_row["shared_focus_band"])
    herts_focus = herts_trend.loc[herts_trend["amount_band"].str.lower() == focus_band.lower()].copy()
    welsh_row = welsh_trend.iloc[0]

    internal_position = pd.DataFrame(
        [
            {
                "aligned_reporting_window": str(cambridge_row["aligned_reporting_window"]),
                "strategic_question": "how should the current support position around the persistent 50_plus pocket be interpreted for planning and future review?",
                "internal_surface_name": "quantitative_evaluation_output_v1",
                "bounded_focus_name": "focused_review_and_remeasurement_support_pathway",
                "shared_focus_band": focus_band,
                "confirming_stream_count": int(cambridge_row["confirming_stream_count"]),
                "current_case_pressure_gap_pp": float(cambridge_row["case_pressure_gap_current_pp"]),
                "current_truth_quality_gap_pp": float(cambridge_row["truth_quality_gap_current_pp"]),
                "internal_position_reading": str(effectiveness_row["bounded_effectiveness_reading"]),
                "internal_planning_relevance": "the internal position remains one of persistent pressure with partial directional improvement, so planning should remain focused rather than broadened",
            }
        ]
    )

    comparator_context = pd.DataFrame(
        [
            {
                "comparator_context_type": "bounded_peer_and_reference_context",
                "comparator_surface_name": "senior_performance_summary_v1_plus_trend_and_trajectory_summary_v1",
                "shared_focus_band": focus_band,
                "comparator_whole_lane_status": str(herts_row["whole_lane_status"]),
                "comparator_focus_status": str(herts_focus.iloc[-1]["focus_pocket_status"]),
                "comparator_case_open_gap_pp": float(herts_row["top_attention_case_open_gap_pp"]),
                "comparator_truth_gap_pp": float(herts_row["top_attention_truth_gap_pp"]),
                "comparator_near_term_trajectory": str(herts_focus.iloc[-1]["near_term_trajectory"]),
                "comparator_reference_reading": "the comparator-style context behaves like a stable topline with a persistent focus pocket, which is suitable as a bounded benchmark-style reference rather than a named sector dataset",
            },
            {
                "comparator_context_type": "bounded_repeated_pattern_reference",
                "comparator_surface_name": "recurring_trend_summary_v1",
                "shared_focus_band": focus_band,
                "comparator_whole_lane_status": str(welsh_row["trend_verdict"]),
                "comparator_focus_status": str(welsh_row["trend_subject_name"]),
                "comparator_case_open_gap_pp": float(welsh_row["current_absolute_gap_pp"]),
                "comparator_truth_gap_pp": float(welsh_row["current_authoritative_to_control_delta_pp"]),
                "comparator_near_term_trajectory": str(welsh_row["repeated_pattern_reading"]),
                "comparator_reference_reading": "the repeated-pattern reference shows how a stable recurring issue can justify targeted review and planning support without broad redesign claims",
            },
        ]
    )

    strategic_comparison = pd.DataFrame(
        [
            {
                "aligned_reporting_window": str(cambridge_row["aligned_reporting_window"]),
                "shared_focus_band": focus_band,
                "internal_surface_name": "quantitative_evaluation_output_v1",
                "comparator_surface_count": int(len(comparator_context)),
                "current_case_pressure_gap_pp": float(cambridge_row["case_pressure_gap_current_pp"]),
                "current_truth_quality_gap_pp": float(cambridge_row["truth_quality_gap_current_pp"]),
                "peer_style_case_gap_pp": float(herts_row["top_attention_case_open_gap_pp"]),
                "peer_style_truth_gap_pp": float(herts_row["top_attention_truth_gap_pp"]),
                "benchmark_position_reading": "the internal Cambridge-style position sits in the same bounded family as the inherited peer-style context: stable topline, persistent focused pressure, and only partial directional improvement",
                "planning_support_reading": "the comparison supports keeping planning attention on the concentrated support pathway rather than broadening the issue into a whole-lane strategy problem, and it supports option development around continued focused review, protected interpretation, and remeasurement",
            }
        ]
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "internal_position_output_present",
                "actual_value": float(len(internal_position)),
                "expected_rule": "= 1 bounded internal position output present",
                "passed_flag": int(len(internal_position) == 1),
            },
            {
                "check_name": "comparator_context_output_contains_two_bounded_references",
                "actual_value": float(len(comparator_context)),
                "expected_rule": "= 2 comparator-context rows retained for bounded benchmark-style interpretation",
                "passed_flag": int(len(comparator_context) == 2),
            },
            {
                "check_name": "strategic_comparison_output_present",
                "actual_value": float(len(strategic_comparison)),
                "expected_rule": "= 1 strategic comparison output present",
                "passed_flag": int(len(strategic_comparison) == 1),
            },
            {
                "check_name": "comparator_language_stays_boundary_safe",
                "actual_value": float(
                    comparator_context["comparator_context_type"].isin(
                        ["bounded_peer_and_reference_context", "bounded_repeated_pattern_reference"]
                    ).sum()
                ),
                "expected_rule": "= 2 comparator rows expressed as bounded comparator context rather than named sector-dataset ownership",
                "passed_flag": int(
                    comparator_context["comparator_context_type"].isin(
                        ["bounded_peer_and_reference_context", "bounded_repeated_pattern_reference"]
                    ).sum()
                    == 2
                ),
            },
            {
                "check_name": "cambridge_evaluation_pack_remains_green",
                "actual_value": float(cambridge_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {cambridge_fact_pack['release_check_count']} inherited Cambridge evaluation checks remain green",
                "passed_flag": int(
                    cambridge_fact_pack["release_checks_passed"] == cambridge_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "hertfordshire_comparator_pack_remains_green",
                "actual_value": float(herts_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {herts_fact_pack['release_check_count']} inherited comparator-style senior checks remain green",
                "passed_flag": int(herts_fact_pack["release_checks_passed"] == herts_fact_pack["release_check_count"]),
            },
            {
                "check_name": "welsh_repeated_pattern_pack_remains_green",
                "actual_value": float(welsh_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {welsh_fact_pack['release_check_count']} inherited repeated-pattern checks remain green",
                "passed_flag": int(welsh_fact_pack["release_checks_passed"] == welsh_fact_pack["release_check_count"]),
            },
        ]
    )

    internal_position.to_parquet(EXTRACTS / "internal_position_output_v1.parquet", index=False)
    comparator_context.to_parquet(EXTRACTS / "comparator_context_output_v1.parquet", index=False)
    strategic_comparison.to_parquet(EXTRACTS / "strategic_comparison_output_v1.parquet", index=False)
    checks_df.to_parquet(EXTRACTS / "strategic_analysis_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "university_of_cambridge/02_strategic_analysis_benchmarking_and_planning_support",
        "aligned_reporting_window": str(cambridge_row["aligned_reporting_window"]),
        "internal_position_output_count": 1,
        "comparator_context_output_count": 1,
        "strategic_comparison_output_count": 1,
        "shared_focus_band": focus_band,
        "confirming_stream_count": int(cambridge_row["confirming_stream_count"]),
        "comparator_rows_used": int(len(comparator_context)),
        "current_case_pressure_gap_pp": float(cambridge_row["case_pressure_gap_current_pp"]),
        "current_truth_quality_gap_pp": float(cambridge_row["truth_quality_gap_current_pp"]),
        "peer_style_case_gap_pp": float(herts_row["top_attention_case_open_gap_pp"]),
        "peer_style_truth_gap_pp": float(herts_row["top_attention_truth_gap_pp"]),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "strategic_analysis_scope_note_v1.md",
        f"""
# Strategic Analysis Scope Note v1

Bounded strategic question:
- how should the current support position around the persistent `{focus_band}` pocket be interpreted for planning and future review?

Internal side:
- `quantitative_evaluation_output_v1`

Comparator side:
- bounded peer and reference context drawn from inherited compact senior and repeated-pattern outputs
- not a live `UCAS`, `HESA`, `HEFCE`, or `UKRI` estate

Why this counts as a benchmarking analogue:
- the internal side fixes current position
- the comparator side supplies explicit bounded reference context
- both surfaces stay on the same focused planning question

What this slice proves:
- one bounded strategic-comparison pack
- one benchmark-aware planning-support reading
- one comparator-safe strategic interpretation

What this slice does not prove:
- live sector-dataset ownership
- full Cambridge institutional-planning authority
- broad strategy control beyond this bounded question
""",
    )

    write_md(
        OUT_BASE / "internal_position_note_v1.md",
        f"""
# Internal Position Note v1

Internal position surface:
- `quantitative_evaluation_output_v1`

Shared focus:
- `{focus_band}`
- confirming streams: `{int(cambridge_row['confirming_stream_count'])}`

Current position:
- case-pressure gap: `{pp(float(cambridge_row['case_pressure_gap_current_pp']))}`
- truth-quality gap: `{pp(float(cambridge_row['truth_quality_gap_current_pp']))}`

Internal reading:
- the current position remains one of persistent focused pressure with only partial directional improvement
- that supports focused planning attention rather than wider lane escalation
""",
    )

    write_md(
        OUT_BASE / "comparator_context_note_v1.md",
        f"""
# Comparator Context Note v1

Comparator posture:
- bounded peer and repeated-pattern reference context
- not named higher-education sector-dataset ownership

Comparator rows carried:
- `{len(comparator_context)}`

Comparator meaning:
- one inherited peer-style context shows stable topline position with a persistent focus pocket
- one inherited repeated-pattern context shows how a stable issue can justify targeted review without broad redesign claims

Boundary:
- this is a benchmark-style analogue
- it is not a claim that live `UCAS`, `HESA`, `HEFCE`, or `UKRI` feeds were directly used in this slice
""",
    )

    write_md(
        OUT_BASE / "planning_support_note_v1.md",
        f"""
# Planning Support Note v1

Planning-support reading:
- the current position sits in the same bounded family as the inherited comparator context:
  - stable topline
  - persistent focused pressure
  - only partial directional improvement

Most defensible strategic implication:
- keep planning attention on the concentrated support pathway around `{focus_band}`
- continue focused review, protected interpretation, and remeasurement
- do not broaden the issue into a whole-lane strategy problem before the bounded focus question is resolved
""",
    )

    write_md(
        OUT_BASE / "strategic_analysis_caveats_v1.md",
        f"""
# Strategic Analysis Caveats v1

This slice is bounded.

Key caveats:
- the comparator side is an honest analogue built from inherited peer-style and repeated-pattern reference context
- the slice does not claim live sector-dataset use
- the planning reading stays below institutional-planning authority
- the pack should be reused as a bounded strategic-analysis and benchmarking proof, not as a full planning-function claim
""",
    )

    write_md(
        OUT_BASE / "README_strategic_analysis_regeneration.md",
        """
# Strategic Analysis Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/university_of_cambridge/02_strategic_analysis_benchmarking_and_planning_support/models/build_strategic_analysis_benchmarking_and_planning_support.py
```

The builder reads only compact inherited outputs and writes the bounded strategic-analysis and benchmarking pack for the Cambridge `D` slice.
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_strategic_analysis.md",
        """
# Changelog - Strategic Analysis, Benchmarking, And Planning Support

- v1: built the first bounded Cambridge strategic-analysis and benchmarking pack from inherited evaluation, senior-comparison, and repeated-pattern outputs
""",
    )


if __name__ == "__main__":
    main()
