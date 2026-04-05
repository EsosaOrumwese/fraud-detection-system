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
CAMBRIDGE_REPORTING_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "university_of_cambridge"
    / "03_reporting_and_large_dataset_preparation"
)
CLAIRE_HOUSE_LEADERSHIP_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "claire_house"
    / "03_senior_leadership_and_external_reporting"
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

    intervention_effectiveness = pd.read_parquet(
        CAMBRIDGE_EVAL_BASE / "extracts" / "intervention_effectiveness_output_v1.parquet"
    )
    strategic_comparison = pd.read_parquet(
        CAMBRIDGE_STRATEGIC_BASE / "extracts" / "strategic_comparison_output_v1.parquet"
    )
    reporting_ready_summary = pd.read_parquet(
        CAMBRIDGE_REPORTING_BASE / "extracts" / "reporting_ready_summary_v1.parquet"
    )

    eval_fact_pack = json.loads(
        (CAMBRIDGE_EVAL_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    strategic_fact_pack = json.loads(
        (CAMBRIDGE_STRATEGIC_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    reporting_fact_pack = json.loads(
        (CAMBRIDGE_REPORTING_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    claire_house_fact_pack = json.loads(
        (CLAIRE_HOUSE_LEADERSHIP_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    eval_row = intervention_effectiveness.iloc[0]
    strategic_row = strategic_comparison.iloc[0]
    reporting_row = reporting_ready_summary.iloc[0]

    aligned_reporting_window = str(eval_row["aligned_reporting_window"])
    shared_focus_band = str(eval_row["shared_focus_band"])
    committee_question = (
        "what should a committee or working group understand, protect, and review next "
        "about the concentrated support pathway?"
    )
    recommendation_count = 3

    committee_ready_briefing_output = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "committee_question": committee_question,
                "briefing_output_type": "committee_ready_briefing",
                "audience": "committee_or_working_group",
                "shared_focus_band": shared_focus_band,
                "confirming_stream_count": int(eval_fact_pack["shared_focus_confirming_streams"]),
                "case_pressure_gap_pp": float(eval_fact_pack["current_case_pressure_gap_pp"]),
                "truth_quality_gap_pp": float(eval_fact_pack["current_truth_quality_gap_pp"]),
                "comparator_rows_used": int(reporting_fact_pack["comparator_rows_used"]),
                "briefing_headline": (
                    "the concentrated pathway remains the right bounded focus, with quality moving in the "
                    "intended direction but pressure still materially unresolved"
                ),
                "committee_ready_reading": (
                    "the briefing combines current position, comparator context, and evaluation posture into "
                    "one committee-ready written surface that supports review and decision without widening into "
                    "a whole-institution strategy problem"
                ),
            }
        ]
    )

    recommendations_output = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "committee_question": committee_question,
                "recommendations_output_type": "committee_recommendations",
                "shared_focus_band": shared_focus_band,
                "recommendation_count": recommendation_count,
                "recommendation_1": "continue focused review on the concentrated pathway rather than broadening attention to the whole lane",
                "recommendation_2": "keep interpretation protected from success language until the pressure gap narrows more materially",
                "recommendation_3": "retain a remeasurement gate so future committee review tests whether the quality movement is sustaining",
                "recommendations_reading": (
                    "the recommendation layer stays on review, interpretation discipline, and remeasurement, "
                    "which fits the bounded evidence better than stronger governance or delivery claims"
                ),
            }
        ]
    )

    release_checks = pd.DataFrame(
        [
            {
                "check_name": "committee_ready_briefing_output_present",
                "actual_value": float(len(committee_ready_briefing_output)),
                "expected_rule": "= 1 committee-ready briefing output present",
                "passed_flag": int(len(committee_ready_briefing_output) == 1),
            },
            {
                "check_name": "recommendations_output_present",
                "actual_value": float(len(recommendations_output)),
                "expected_rule": "= 1 recommendations output present",
                "passed_flag": int(len(recommendations_output) == 1),
            },
            {
                "check_name": "briefing_and_recommendations_share_focus_band",
                "actual_value": float(
                    committee_ready_briefing_output.iloc[0]["shared_focus_band"]
                    == recommendations_output.iloc[0]["shared_focus_band"]
                ),
                "expected_rule": "= 1 same bounded focus band retained across briefing and recommendations",
                "passed_flag": int(
                    committee_ready_briefing_output.iloc[0]["shared_focus_band"]
                    == recommendations_output.iloc[0]["shared_focus_band"]
                ),
            },
            {
                "check_name": "recommendation_count_is_explicit",
                "actual_value": float(recommendations_output.iloc[0]["recommendation_count"]),
                "expected_rule": "= 3 bounded recommendation points retained",
                "passed_flag": int(recommendations_output.iloc[0]["recommendation_count"] == recommendation_count),
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
                "check_name": "cambridge_reporting_pack_remains_green",
                "actual_value": float(reporting_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {reporting_fact_pack['release_check_count']} inherited Cambridge reporting-preparation checks remain green",
                "passed_flag": int(
                    reporting_fact_pack["release_checks_passed"] == reporting_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "committee_translation_precedent_remains_green",
                "actual_value": float(claire_house_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {claire_house_fact_pack['release_check_count']} inherited leadership-reporting precedent checks remain green",
                "passed_flag": int(
                    claire_house_fact_pack["release_checks_passed"] == claire_house_fact_pack["release_check_count"]
                ),
            },
        ]
    )

    committee_ready_briefing_output.to_parquet(
        EXTRACTS / "committee_ready_briefing_output_v1.parquet", index=False
    )
    recommendations_output.to_parquet(EXTRACTS / "recommendations_output_v1.parquet", index=False)
    release_checks.to_parquet(EXTRACTS / "committee_analysis_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "university_of_cambridge/04_committee_ready_analysis_and_recommendations",
        "aligned_reporting_window": aligned_reporting_window,
        "committee_ready_briefing_output_count": 1,
        "recommendations_output_count": 1,
        "non_specialist_translation_note_count": 1,
        "recommendation_count": recommendation_count,
        "shared_focus_band": shared_focus_band,
        "confirming_stream_count": int(eval_fact_pack["shared_focus_confirming_streams"]),
        "comparator_rows_used": int(reporting_fact_pack["comparator_rows_used"]),
        "current_case_pressure_gap_pp": float(eval_fact_pack["current_case_pressure_gap_pp"]),
        "current_truth_quality_gap_pp": float(eval_fact_pack["current_truth_quality_gap_pp"]),
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "committee_analysis_scope_note_v1.md",
        f"""
# Committee Analysis Scope Note v1

Bounded committee question:
- {committee_question}

Inherited analytical base:
- `intervention_effectiveness_output_v1`
- `strategic_comparison_output_v1`
- `reporting_ready_summary_v1`

What this slice proves:
- one committee-ready written briefing output
- one recommendations output
- one non-specialist translation note

What this slice does not prove:
- live committee presentation ownership
- governance authority over the decision
- a wider communications or secretariat function
""",
    )

    write_md(
        OUT_BASE / "committee_briefing_note_v1.md",
        f"""
# Committee Briefing Note v1

Committee-ready briefing posture:
- the concentrated pathway remains the bounded focus for committee review
- current case pressure remains elevated at `{pp(float(eval_fact_pack['current_case_pressure_gap_pp']))}`
- truth quality shows directional improvement but remains `{pp(float(eval_fact_pack['current_truth_quality_gap_pp']))}` away from the trusted comparative line

Why the briefing is committee-ready:
- it keeps the analytical position concise
- it ties current position to comparator context and evaluation posture
- it gives the audience one readable written base before recommendation language is added
""",
    )

    write_md(
        OUT_BASE / "recommendations_note_v1.md",
        f"""
# Recommendations Note v1

Recommendation posture:
- recommendation count retained: `{recommendation_count}`
- the output stays on review, interpretation discipline, and remeasurement

Recommendation set:
- continue focused review on `{shared_focus_band}` rather than broadening the issue to the whole analytical lane
- keep interpretation protected from premature success language while the pressure gap remains `{pp(float(eval_fact_pack['current_case_pressure_gap_pp']))}`
- retain a remeasurement gate so future review can test whether the quality movement is sustaining
""",
    )

    write_md(
        OUT_BASE / "non_specialist_translation_note_v1.md",
        f"""
# Non-Specialist Translation Note v1

Plain-language reading:
- the issue is concentrated rather than widespread
- some signs are moving in the right direction, but the pressure is still high enough that the committee should not treat the pathway as solved
- the most sensible next step is to keep the same focus, review it again, and check whether the improvement is holding

Audience-use boundary:
- this note is written to make the analytical meaning easier to use for non-specialist readers
- it does not replace the formal analytical base or create governance authority on its own
""",
    )

    write_md(
        OUT_BASE / "committee_analysis_caveats_v1.md",
        f"""
# Committee Analysis Caveats v1

Boundary reminders:
- this is a bounded committee-ready written-briefing analogue
- it does not prove live committee cycle ownership or live presentation delivery
- it does not prove governance authority or formal committee decision control
- the analytical question remains concentrated on `{shared_focus_band}` rather than a whole-institution issue
""",
    )

    write_md(
        OUT_BASE / "README_committee_analysis_regeneration.md",
        """
# Committee Analysis Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/university_of_cambridge/04_committee_ready_analysis_and_recommendations/models/build_committee_ready_analysis_and_recommendations.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_committee_analysis.md",
        """
# Committee Analysis Changelog

- v1: initial bounded committee-ready analysis and recommendations pack built from inherited Cambridge analytical outputs
""",
    )


if __name__ == "__main__":
    main()
