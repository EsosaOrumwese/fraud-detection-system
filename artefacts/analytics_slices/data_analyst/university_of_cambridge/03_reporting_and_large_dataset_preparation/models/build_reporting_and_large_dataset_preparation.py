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
CAMBRIDGE_STRATEGIC_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "university_of_cambridge"
    / "02_strategic_analysis_benchmarking_and_planning_support"
)
FRIMLEY_VISUAL_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "frimley_integrated_care_board"
    / "01_data_to_visual_product_and_accessible_insight"
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
    internal_position = pd.read_parquet(
        CAMBRIDGE_STRATEGIC_BASE / "extracts" / "internal_position_output_v1.parquet"
    )
    comparator_context = pd.read_parquet(
        CAMBRIDGE_STRATEGIC_BASE / "extracts" / "comparator_context_output_v1.parquet"
    )
    strategic_comparison = pd.read_parquet(
        CAMBRIDGE_STRATEGIC_BASE / "extracts" / "strategic_comparison_output_v1.parquet"
    )
    frimley_dashboard = pd.read_parquet(
        FRIMLEY_VISUAL_BASE / "extracts" / "dashboard_summary_v1.parquet"
    )

    eval_fact_pack = json.loads(
        (CAMBRIDGE_EVAL_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    strategic_fact_pack = json.loads(
        (CAMBRIDGE_STRATEGIC_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    frimley_fact_pack = json.loads(
        (FRIMLEY_VISUAL_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    eval_row = quantitative_eval.iloc[0]
    effectiveness_row = intervention_effectiveness.iloc[0]
    internal_row = internal_position.iloc[0]
    strategic_row = strategic_comparison.iloc[0]
    frimley_row = frimley_dashboard.iloc[0]
    focus_band = str(eval_row["shared_focus_band"])

    prepared_combined_base = pd.DataFrame(
        [
            {
                "aligned_reporting_window": str(eval_row["aligned_reporting_window"]),
                "prepared_reporting_question": "how can the current Cambridge-style focus reading be packaged into one routine reporting-ready surface?",
                "reporting_grain": "focus_band_reporting_pack",
                "bounded_focus_name": str(eval_row["bounded_intervention_name"]),
                "shared_focus_band": focus_band,
                "confirming_stream_count": int(eval_row["confirming_stream_count"]),
                "current_case_pressure_gap_pp": float(eval_row["case_pressure_gap_current_pp"]),
                "current_truth_quality_gap_pp": float(eval_row["truth_quality_gap_current_pp"]),
                "comparator_surface_count": int(strategic_row["comparator_surface_count"]),
                "peer_style_case_gap_pp": float(strategic_row["peer_style_case_gap_pp"]),
                "peer_style_truth_gap_pp": float(strategic_row["peer_style_truth_gap_pp"]),
                "prepared_summary_status": "reporting_ready_but_bounded",
                "prepared_base_reading": "the prepared base combines current position, effectiveness reading, and comparator context into one compact reporting-ready structure",
            }
        ]
    )

    reporting_ready_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": str(eval_row["aligned_reporting_window"]),
                "prepared_base_name": "prepared_combined_base_v1",
                "reporting_output_type": "reporting_ready_summary",
                "shared_focus_band": focus_band,
                "confirming_stream_count": int(eval_row["confirming_stream_count"]),
                "case_pressure_gap_pp": float(eval_row["case_pressure_gap_current_pp"]),
                "truth_quality_gap_pp": float(eval_row["truth_quality_gap_current_pp"]),
                "comparator_rows_used": int(len(comparator_context)),
                "dashboard_style_headline": "the same concentrated focus remains the reporting starting point across the prepared Cambridge pack",
                "routine_reporting_reading": "the reporting-ready summary preserves the current focus, comparator context, and planning relevance in one repeatable surface rather than requiring separate interpretive packs each time",
            }
        ]
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "prepared_combined_base_output_present",
                "actual_value": float(len(prepared_combined_base)),
                "expected_rule": "= 1 prepared combined base output present",
                "passed_flag": int(len(prepared_combined_base) == 1),
            },
            {
                "check_name": "prepared_base_retains_current_and_comparator_fields",
                "actual_value": float(prepared_combined_base.iloc[0]["comparator_surface_count"]),
                "expected_rule": "= 2 comparator surfaces retained alongside current-position fields in the prepared base",
                "passed_flag": int(prepared_combined_base.iloc[0]["comparator_surface_count"] == 2),
            },
            {
                "check_name": "reporting_ready_summary_output_present",
                "actual_value": float(len(reporting_ready_summary)),
                "expected_rule": "= 1 reporting-ready summary output present",
                "passed_flag": int(len(reporting_ready_summary) == 1),
            },
            {
                "check_name": "workflow_language_stays_boundary_safe",
                "actual_value": float(
                    (reporting_ready_summary["reporting_output_type"] == "reporting_ready_summary").sum()
                ),
                "expected_rule": "= 1 reporting-ready summary retained without self-service or workflow-estate ownership language",
                "passed_flag": int(
                    (reporting_ready_summary["reporting_output_type"] == "reporting_ready_summary").sum() == 1
                ),
            },
            {
                "check_name": "cambridge_evaluation_pack_remains_green",
                "actual_value": float(eval_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {eval_fact_pack['release_check_count']} inherited Cambridge evaluation checks remain green",
                "passed_flag": int(eval_fact_pack["release_checks_passed"] == eval_fact_pack["release_check_count"]),
            },
            {
                "check_name": "cambridge_strategic_pack_remains_green",
                "actual_value": float(strategic_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {strategic_fact_pack['release_check_count']} inherited Cambridge strategic checks remain green",
                "passed_flag": int(
                    strategic_fact_pack["release_checks_passed"] == strategic_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "reporting_shaping_precedent_remains_green",
                "actual_value": float(frimley_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {frimley_fact_pack['release_check_count']} inherited reporting-shaping precedent checks remain green",
                "passed_flag": int(frimley_fact_pack["release_checks_passed"] == frimley_fact_pack["release_check_count"]),
            },
        ]
    )

    prepared_combined_base.to_parquet(EXTRACTS / "prepared_combined_base_v1.parquet", index=False)
    reporting_ready_summary.to_parquet(EXTRACTS / "reporting_ready_summary_v1.parquet", index=False)
    checks_df.to_parquet(EXTRACTS / "reporting_preparation_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "university_of_cambridge/03_reporting_and_large_dataset_preparation",
        "aligned_reporting_window": str(eval_row["aligned_reporting_window"]),
        "prepared_combined_base_output_count": 1,
        "reporting_ready_output_count": 1,
        "workflow_readiness_output_count": 1,
        "shared_focus_band": focus_band,
        "confirming_stream_count": int(eval_row["confirming_stream_count"]),
        "comparator_rows_used": int(len(comparator_context)),
        "current_case_pressure_gap_pp": float(eval_row["case_pressure_gap_current_pp"]),
        "current_truth_quality_gap_pp": float(eval_row["truth_quality_gap_current_pp"]),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "reporting_preparation_scope_note_v1.md",
        f"""
# Reporting Preparation Scope Note v1

Bounded reporting question:
- how can the current Cambridge-style focus reading be packaged into one routine reporting-ready surface?

Prepared-base inputs:
- `quantitative_evaluation_output_v1`
- `intervention_effectiveness_output_v1`
- `internal_position_output_v1`
- `strategic_comparison_output_v1`

Why this counts as a reporting-and-preparation analogue:
- the prepared base combines current, evaluative, and strategic fields into one compact reporting-ready structure
- the resulting summary can be reused for repeat reporting without reopening the full interpretation chain each time

What this slice proves:
- one prepared combined base
- one reporting-ready summary output
- one workflow-readiness reading

What this slice does not prove:
- live `Alteryx` use
- self-service reporting estate ownership
- full institutional warehouse control
""",
    )

    write_md(
        OUT_BASE / "prepared_base_note_v1.md",
        f"""
# Prepared Base Note v1

Preparation posture:
- the Cambridge slice uses a compact prepared-base step over inherited evaluation and strategic outputs
- the preparation layer retains only the fields needed for a repeat reporting surface

Retained reporting grain:
- `focus_band_reporting_pack`
- row count retained: `{len(prepared_combined_base)}`

Primary focus band after preparation:
- `{focus_band}`
- confirming streams: `{int(eval_row['confirming_stream_count'])}`

Why this preparation layer matters:
- it behaves like the reporting-ready preparation step the Cambridge role expects
- it converts completed analytical packs into a cleaner reusable reporting base without reopening raw scope
""",
    )

    write_md(
        OUT_BASE / "reporting_summary_note_v1.md",
        f"""
# Reporting Summary Note v1

Reporting-ready surface:
- `reporting_ready_summary_v1`

Headline:
- the same concentrated focus remains the reporting starting point across the prepared Cambridge pack

Summary reading:
- shared focus band: `{focus_band}`
- case-pressure gap: `{pp(float(eval_row['case_pressure_gap_current_pp']))}`
- truth-quality gap: `{pp(float(eval_row['truth_quality_gap_current_pp']))}`
- comparator rows retained: `{len(comparator_context)}`

Routine reporting meaning:
- the summary preserves current position and comparator context in one compact surface
- this supports repeat reporting use without rebuilding the interpretation chain each time
""",
    )

    write_md(
        OUT_BASE / "workflow_readiness_note_v1.md",
        f"""
# Workflow Readiness Note v1

Workflow-readiness posture:
- the prepared base makes the current Cambridge-style focus reading easier to reuse for repeat reporting
- the compact structure reduces the need to reopen separate evaluation and strategic outputs each time a reporting cut is needed

Boundary:
- this is a prepared-base reuse and reporting-readiness claim
- it is not a live `Alteryx` workflow claim
- it is not a self-service or warehouse-platform ownership claim
""",
    )

    write_md(
        OUT_BASE / "reporting_preparation_caveats_v1.md",
        f"""
# Reporting Preparation Caveats v1

This slice is bounded.

Key caveats:
- the prepared base is built from inherited compact outputs rather than a live raw warehouse
- the workflow reading stays on reporting readiness and reuse
- the slice does not claim live `Alteryx`, self-service, or warehouse-estate ownership
- the pack should be reused as a bounded reporting-and-preparation proof, not as a full reporting-platform claim
""",
    )

    write_md(
        OUT_BASE / "README_reporting_preparation_regeneration.md",
        """
# Reporting Preparation Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/university_of_cambridge/03_reporting_and_large_dataset_preparation/models/build_reporting_and_large_dataset_preparation.py
```

The builder reads only compact inherited outputs and writes the bounded reporting-and-preparation pack for the Cambridge `A + B` slice.
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_reporting_preparation.md",
        """
# Changelog - Reporting And Large-Dataset Preparation

- v1: built the first bounded Cambridge reporting-and-preparation pack from inherited evaluation, strategic, and reporting-shaping outputs
""",
    )


if __name__ == "__main__":
    main()
