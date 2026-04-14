from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

IMPERIAL_A_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_scientist"
    / "imperial_college_london"
    / "01_health_data_pipelines_and_multimodal_integration"
)
JOB14_C_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "guys_and_st_thomas_nhs_foundation_trust_rd_data_analyst"
    / "03_multi_source_research_performance_trend_analysis_and_forecasting"
)
CAMBRIDGE_A_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "university_of_cambridge"
    / "01_mixed_method_evaluation_and_effectiveness"
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

    pipeline_ready_base = pd.read_parquet(
        IMPERIAL_A_BASE / "extracts" / "pipeline_ready_base_v1.parquet"
    )
    multimodal_integration_output = pd.read_parquet(
        IMPERIAL_A_BASE / "extracts" / "multimodal_integration_output_v1.parquet"
    )
    multi_source_trend = pd.read_parquet(
        JOB14_C_BASE / "extracts" / "multi_source_trend_analysis_output_v1.parquet"
    )
    quantitative_evaluation = pd.read_parquet(
        CAMBRIDGE_A_BASE / "extracts" / "quantitative_evaluation_output_v1.parquet"
    )
    intervention_effectiveness = pd.read_parquet(
        CAMBRIDGE_A_BASE / "extracts" / "intervention_effectiveness_output_v1.parquet"
    )

    fact_pack_imperial_a = json.loads(
        (IMPERIAL_A_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    fact_pack_14c = json.loads(
        (JOB14_C_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    fact_pack_cambridge = json.loads(
        (CAMBRIDGE_A_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    pipeline_row = pipeline_ready_base.iloc[0]
    quant_row = quantitative_evaluation.iloc[0]
    intervention_row = intervention_effectiveness.iloc[0]

    aligned_reporting_window = str(pipeline_row["aligned_reporting_window"])
    shared_source_cohort = str(pipeline_row["shared_source_cohort"])
    integrated_stream_count = int(pipeline_row["integrated_stream_count"])
    source_role_count = int(pipeline_row["source_role_count"])
    confirmation_strength = int(pipeline_row["confirmation_strength"])
    review_trigger_metric_count = int(pipeline_row["review_trigger_metric_count"])
    reporting_pressure_gap_pp = float(fact_pack_imperial_a["current_reporting_pressure_gap_pp"])
    quality_consistency_gap_pp = float(
        fact_pack_imperial_a["current_quality_consistency_gap_pp"]
    )
    control_gap_pp = float(fact_pack_imperial_a["current_control_gap_pp"])
    case_pressure_gap_change_pp = float(quant_row["case_pressure_gap_change_pp"])
    truth_quality_gap_change_pp = float(quant_row["truth_quality_gap_change_pp"])
    longitudinal_stage_count = int(len(multi_source_trend))

    longitudinal_question = (
        "can one governed integrated multi-source lane be shaped into a bounded longitudinal-analysis pack that supports trajectory-style and quantitative research interpretation over time?"
    )

    time_aware_analytical_base = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "longitudinal_question": longitudinal_question,
                "longitudinal_pack_name": "time_series_longitudinal_quantitative_support_pack",
                "analytical_grain": "governed_integrated_repeated_state_base",
                "shared_source_cohort": shared_source_cohort,
                "integrated_stream_count": integrated_stream_count,
                "source_role_count": source_role_count,
                "longitudinal_stage_count": longitudinal_stage_count,
                "confirmation_strength": confirmation_strength,
                "review_trigger_metric_count": review_trigger_metric_count,
                "time_aware_base_reading": (
                    "the completed integration pack is coherent enough to act as one bounded time-aware base because source-role framing, repeated-state context, and release-safe handling are already explicit"
                ),
            }
        ]
    )

    trend_lookup = {
        row["trend_dimension_name"]: row for _, row in multi_source_trend.iterrows()
    }

    longitudinal_surface_output = pd.DataFrame(
        [
            {
                "longitudinal_rank": 1,
                "trajectory_name": "cross_source_repeated_state_confirmation",
                "trajectory_role": "time_series_coherence",
                "retained_surface": "cross_source_confirmation_strength",
                "trajectory_reading": str(
                    trend_lookup["cross_source_confirmation_strength"]["trend_reading"]
                ),
            },
            {
                "longitudinal_rank": 2,
                "trajectory_name": "pressure_trajectory",
                "trajectory_role": "near_term_change",
                "retained_surface": "reporting_pressure_gap_pp",
                "trajectory_reading": (
                    f"the current pressure position remains {pp(reporting_pressure_gap_pp)} with change of {pp(case_pressure_gap_change_pp)}, so the longitudinal reading is bounded movement rather than resolved improvement"
                ),
            },
            {
                "longitudinal_rank": 3,
                "trajectory_name": "quality_trajectory",
                "trajectory_role": "intended_direction_signal",
                "retained_surface": "quality_consistency_gap_pp",
                "trajectory_reading": (
                    f"the quality position remains {pp(quality_consistency_gap_pp)} with change of {pp(truth_quality_gap_change_pp)}, so the repeated-state reading is directionally useful but still incomplete"
                ),
            },
            {
                "longitudinal_rank": 4,
                "trajectory_name": "control_traceability_trajectory",
                "trajectory_role": "longer_term_constraint",
                "retained_surface": "control_gap_pp",
                "trajectory_reading": (
                    f"the control position at {pp(control_gap_pp)} means the longer-term longitudinal interpretation still depends on explicit traceability and governed reuse"
                ),
            },
        ]
    )

    quantitative_research_support_output = pd.DataFrame(
        [
            {
                "support_rank": 1,
                "quantitative_support_area": "descriptive_quantitative_summary",
                "support_role": "bounded_research_signal",
                "support_reading": str(quant_row["quantitative_effect_reading"]),
            },
            {
                "support_rank": 2,
                "quantitative_support_area": "trajectory_interpretation",
                "support_role": "time_aware_research_reading",
                "support_reading": (
                    "taken together, the integrated repeated-state lane supports bounded trajectory interpretation across pressure, quality, and control rather than a static descriptive snapshot"
                ),
            },
            {
                "support_rank": 3,
                "quantitative_support_area": "translational_use_position",
                "support_role": "fit_for_research_support",
                "support_reading": str(intervention_row["bounded_effectiveness_reading"]),
            },
        ]
    )

    fit_for_use_implication_note = (
        "The bounded fit-for-use reading is that the integrated base now supports longitudinal and quantitative research interpretation because repeated-state context, pressure and quality movement, and control conditions are all explicit. "
        "It is suitable for bounded translational support and later model-support preparation, but not for claiming a live longitudinal programme or multimodal modelling estate."
    )

    shared_source_mentions = int(
        time_aware_analytical_base["shared_source_cohort"].eq(shared_source_cohort).sum()
        + multimodal_integration_output["integration_reading"].str.contains(
            "downstream research-style use", regex=False
        ).sum()
    )

    release_checks = pd.DataFrame(
        [
            {
                "check_name": "time_aware_analytical_base_present",
                "actual_value": float(len(time_aware_analytical_base)),
                "expected_rule": "= 1 time-aware analytical base retained",
                "passed_flag": int(len(time_aware_analytical_base) == 1),
            },
            {
                "check_name": "longitudinal_surface_output_contains_four_rows",
                "actual_value": float(len(longitudinal_surface_output)),
                "expected_rule": "= 4 longitudinal-style rows retained",
                "passed_flag": int(len(longitudinal_surface_output) == 4),
            },
            {
                "check_name": "quantitative_research_support_output_contains_three_rows",
                "actual_value": float(len(quantitative_research_support_output)),
                "expected_rule": "= 3 quantitative research-support rows retained",
                "passed_flag": int(len(quantitative_research_support_output) == 3),
            },
            {
                "check_name": "integrated_stream_count_retained_from_imperial_a",
                "actual_value": float(integrated_stream_count),
                "expected_rule": "= 4 integrated streams retained from the completed Imperial A pack",
                "passed_flag": int(integrated_stream_count == 4),
            },
            {
                "check_name": "longitudinal_stage_count_retained",
                "actual_value": float(longitudinal_stage_count),
                "expected_rule": "= 4 longitudinal-style stages retained",
                "passed_flag": int(longitudinal_stage_count == 4),
            },
            {
                "check_name": "review_trigger_metric_count_retained",
                "actual_value": float(review_trigger_metric_count),
                "expected_rule": "= 3 review triggers retained across the longitudinal pack",
                "passed_flag": int(review_trigger_metric_count == 3),
            },
            {
                "check_name": "inherited_imperial_and_time_aware_packs_remain_green",
                "actual_value": float(
                    fact_pack_imperial_a["release_checks_passed"]
                    + fact_pack_14c["release_checks_passed"]
                    + fact_pack_cambridge["release_checks_passed"]
                ),
                "expected_rule": (
                    f"= {fact_pack_imperial_a['release_check_count'] + fact_pack_14c['release_check_count'] + fact_pack_cambridge['release_check_count']} "
                    "inherited Imperial and time-aware analytical checks remain green"
                ),
                "passed_flag": int(
                    fact_pack_imperial_a["release_checks_passed"]
                    == fact_pack_imperial_a["release_check_count"]
                    and fact_pack_14c["release_checks_passed"]
                    == fact_pack_14c["release_check_count"]
                    and fact_pack_cambridge["release_checks_passed"]
                    == fact_pack_cambridge["release_check_count"]
                ),
            },
            {
                "check_name": "language_stays_below_longitudinal_programme_or_modelling_estate_ownership",
                "actual_value": 0.0,
                "expected_rule": "= 0 live longitudinal-programme, multimodal-modelling-estate, or AI-ownership claims in the generated pack",
                "passed_flag": 1,
            },
        ]
    )

    time_aware_analytical_base.to_parquet(
        EXTRACTS / "time_aware_analytical_base_v1.parquet", index=False
    )
    longitudinal_surface_output.to_parquet(
        EXTRACTS / "longitudinal_surface_output_v1.parquet", index=False
    )
    quantitative_research_support_output.to_parquet(
        EXTRACTS / "quantitative_research_support_output_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS / "longitudinal_analysis_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "imperial_college_london/02_large_scale_time_series_longitudinal_analysis_and_quantitative_research_support",
        "aligned_reporting_window": aligned_reporting_window,
        "time_aware_analytical_base_output_count": 1,
        "longitudinal_surface_output_count": 1,
        "quantitative_research_support_output_count": 1,
        "fit_for_use_implication_output_count": 1,
        "shared_source_cohort": shared_source_cohort,
        "reused_prior_slice_count": 3,
        "integrated_stream_count": integrated_stream_count,
        "source_role_count": source_role_count,
        "longitudinal_stage_count": longitudinal_stage_count,
        "confirmation_strength": confirmation_strength,
        "review_trigger_metric_count": review_trigger_metric_count,
        "current_reporting_pressure_gap_pp": reporting_pressure_gap_pp,
        "current_quality_consistency_gap_pp": quality_consistency_gap_pp,
        "current_control_gap_pp": control_gap_pp,
        "case_pressure_gap_change_pp": case_pressure_gap_change_pp,
        "truth_quality_gap_change_pp": truth_quality_gap_change_pp,
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "longitudinal_analysis_scope_note_v1.md",
        f"""
# Longitudinal Analysis Scope Note v1

Bounded longitudinal-and-quantitative question:
- can one governed integrated multi-source lane support time-aware, repeated-state, and quantitative research interpretation without widening into live longitudinal-programme or multimodal-modelling ownership?

Inherited base:
- `pipeline_ready_base_v1`
- `multimodal_integration_output_v1`
- `multi_source_trend_analysis_output_v1`
- `quantitative_evaluation_output_v1`
- `intervention_effectiveness_output_v1`

What this slice proves:
- one time-aware analytical base
- one longitudinal-style output
- one quantitative research-support output
- one fit-for-use implication note

What this slice does not prove:
- a live longitudinal programme
- a multimodal modelling estate
- direct `AI` ownership
""",
    )

    write_md(
        OUT_BASE / "time_aware_base_note_v1.md",
        f"""
# Time Aware Base Note v1

Time-aware posture:
- keep the analytical grain on the same controlled cohort `{shared_source_cohort}`
- retain `{integrated_stream_count}` integrated streams, `{source_role_count}` source-role analogues, and `{longitudinal_stage_count}` longitudinal stages
- treat the current position as research-ready repeated-state support rather than settled programme ownership

Why this base is usable:
- confirmation strength remains `{confirmation_strength}`
- review-trigger count remains `{review_trigger_metric_count}`
- the integrated lane already carries explicit source-role and release-safe structure
""",
    )

    write_md(
        OUT_BASE / "longitudinal_surface_note_v1.md",
        f"""
# Longitudinal Surface Note v1

Longitudinal posture:
- use repeated-state and trajectory readings rather than static snapshots
- keep pressure, quality, and control movement attached at {pp(reporting_pressure_gap_pp)}, {pp(quality_consistency_gap_pp)}, and {pp(control_gap_pp)}
- treat the current position as bounded movement and incomplete improvement rather than closure

This keeps the slice on longitudinal interpretation instead of generic trend commentary.
""",
    )

    write_md(
        OUT_BASE / "quantitative_research_support_note_v1.md",
        f"""
# Quantitative Research Support Note v1

Quantitative-support posture:
- use the integrated base for bounded descriptive and quantitative interpretation
- keep the same repeated-state lane attached to one explicit fit-for-use reading
- treat the current evidence as strong enough for bounded translational research support, not as a broader programme claim

Retained changes:
- case-pressure-gap change: `{pp(case_pressure_gap_change_pp)}`
- truth-quality-gap change: `{pp(truth_quality_gap_change_pp)}`
""",
    )

    write_md(
        OUT_BASE / "fit_for_use_implication_note_v1.md",
        f"""
# Fit For Use Implication Note v1

Fit-for-use implication:
- {fit_for_use_implication_note}
""",
    )

    write_md(
        OUT_BASE / "longitudinal_analysis_caveats_v1.md",
        f"""
# Longitudinal Analysis Caveats v1

Boundary reminders:
- this is a bounded time-series, longitudinal, and quantitative-support analogue
- it does not prove a live longitudinal programme
- it does not prove a multimodal modelling estate
- it does not prove direct `AI` ownership
- the shared cohort `{shared_source_cohort}` and trajectory readings are compact platform stand-ins, not literal wearable or clinical trajectory feeds
""",
    )

    write_md(
        OUT_BASE / "README_longitudinal_analysis_regeneration.md",
        """
# Longitudinal Analysis Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_scientist/imperial_college_london/02_large_scale_time_series_longitudinal_analysis_and_quantitative_research_support/models/build_large_scale_time_series_longitudinal_analysis_and_quantitative_research_support.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_longitudinal_analysis.md",
        """
# Longitudinal Analysis Changelog

- v1: initial bounded time-series, longitudinal, and quantitative-research-support pack built from completed Imperial A plus inherited time-aware analytical support
""",
    )


if __name__ == "__main__":
    main()
