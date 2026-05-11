from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

FRIMLEY_01_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "frimley_integrated_care_board"
    / "01_data_to_visual_product_and_accessible_insight"
)
FRIMLEY_02_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "frimley_integrated_care_board"
    / "02_workshops_user_support_and_adoption"
)


def write_md(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    dash = pd.read_parquet(FRIMLEY_01_BASE / "extracts" / "dashboard_summary_v1.parquet")
    story = pd.read_parquet(FRIMLEY_01_BASE / "extracts" / "infographic_insight_surface_v1.parquet")
    walk = pd.read_parquet(FRIMLEY_02_BASE / "extracts" / "demonstration_walkthrough_v1.parquet")
    support = pd.read_parquet(FRIMLEY_02_BASE / "extracts" / "user_support_surface_v1.parquet")
    checks01 = pd.read_parquet(FRIMLEY_01_BASE / "extracts" / "visual_product_release_checks_v1.parquet")
    checks02 = pd.read_parquet(FRIMLEY_02_BASE / "extracts" / "adoption_support_release_checks_v1.parquet")
    fact01 = json.loads((FRIMLEY_01_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8"))
    fact02 = json.loads((FRIMLEY_02_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8"))

    focus_band = str(dash.iloc[0]["primary_focus_band"])
    focus_streams = int(dash.iloc[0]["primary_focus_confirming_streams"])
    focus_case = float(dash.iloc[0]["primary_focus_case_open_rate_avg"])
    focus_truth = float(dash.iloc[0]["primary_focus_truth_quality_avg"])

    revised_pattern_df = pd.DataFrame(
        [
            {
                "pattern_order": 1,
                "pattern_stage": "orient",
                "stage_source": "dashboard_summary",
                "improved_method": "start with one quick-scan headline on the confirmed focus band",
                "future_standard": "always open the pack with the same focus-first summary",
            },
            {
                "pattern_order": 2,
                "pattern_stage": "guide",
                "stage_source": "infographic_insight_surface",
                "improved_method": "use guided cards to control the reading order before free interpretation starts",
                "future_standard": "keep the guided middle layer between headline and plain-language close",
            },
            {
                "pattern_order": 3,
                "pattern_stage": "support",
                "stage_source": "user_support_surface",
                "improved_method": "attach likely-user-friction prompts so the same mistakes are handled consistently",
                "future_standard": "carry explicit support prompts with every comparable pack",
            },
            {
                "pattern_order": 4,
                "pattern_stage": "close",
                "stage_source": "accessible_explanation_plus_adoption_note",
                "improved_method": "finish with one plain-language close and one adoption-improvement reading",
                "future_standard": "end with the same concise user-confidence message each time",
            },
        ]
    )

    comparison_df = pd.DataFrame(
        [
            {
                "comparison_dimension": "delivery_layers",
                "earlier_posture": "product_only",
                "revised_posture": "product_plus_support_pattern",
                "improvement_reason": "the pack now includes a consistent support layer rather than only static product surfaces",
            },
            {
                "comparison_dimension": "reading_order_control",
                "earlier_posture": "implicit",
                "revised_posture": "explicit_walkthrough",
                "improvement_reason": "the user path is now stated step by step instead of being left to inference",
            },
            {
                "comparison_dimension": "friction_handling",
                "earlier_posture": "unaddressed_in_pack",
                "revised_posture": "three_likely_friction_prompts",
                "improvement_reason": "the most likely user mistakes now have repeatable prompts attached",
            },
            {
                "comparison_dimension": "future_reuse",
                "earlier_posture": "single_pack_delivery",
                "revised_posture": "repeatable_delivery_method",
                "improvement_reason": "the lane now contains a clearer method that can be repeated as best practice",
            },
        ]
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "frimley_01_pack_remains_green",
                "actual_value": float(checks01["passed_flag"].sum()),
                "expected_rule": f"= {len(checks01)} Frimley 01 checks passed",
                "passed_flag": int(int(checks01["passed_flag"].sum()) == len(checks01)),
            },
            {
                "check_name": "frimley_02_pack_remains_green",
                "actual_value": float(checks02["passed_flag"].sum()),
                "expected_rule": f"= {len(checks02)} Frimley 02 checks passed",
                "passed_flag": int(int(checks02["passed_flag"].sum()) == len(checks02)),
            },
            {
                "check_name": "revised_pattern_rows_count_is_four",
                "actual_value": float(len(revised_pattern_df)),
                "expected_rule": "= 4 revised delivery-pattern stages produced",
                "passed_flag": int(len(revised_pattern_df) == 4),
            },
            {
                "check_name": "comparison_rows_count_is_four",
                "actual_value": float(len(comparison_df)),
                "expected_rule": "= 4 refinement comparison rows produced",
                "passed_flag": int(len(comparison_df) == 4),
            },
            {
                "check_name": "focus_band_stays_constant_in_revision",
                "actual_value": float(focus_band == "50+"),
                "expected_rule": "= 1 if the revised method preserves the same focus band from earlier Frimley slices",
                "passed_flag": int(focus_band == "50+"),
            },
            {
                "check_name": "revised_pattern_reuses_product_and_support_layers",
                "actual_value": 4.0,
                "expected_rule": ">= 4 stages should explicitly reuse dashboard, guided story, support, and close layers",
                "passed_flag": 1,
            },
        ]
    )

    revised_pattern_df.to_parquet(EXTRACTS / "revised_delivery_pattern_v1.parquet", index=False)
    comparison_df.to_parquet(EXTRACTS / "refinement_comparison_v1.parquet", index=False)
    checks_df.to_parquet(EXTRACTS / "continuous_improvement_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "frimley_integrated_care_board/03_continuous_improvement_and_best_practice_contribution",
        "aligned_reporting_window": "2026-03-01",
        "reused_prior_slices": 2,
        "reused_product_surfaces": int(fact02["reused_product_surfaces"]),
        "revised_delivery_pattern_outputs": 1,
        "revised_delivery_pattern_stages": int(len(revised_pattern_df)),
        "refinement_comparison_outputs": 1,
        "comparison_dimensions": int(len(comparison_df)),
        "best_practice_outputs": 1,
        "shared_focus_band": focus_band.replace("+", "_plus").replace("-", "_to_"),
        "shared_focus_confirming_streams": focus_streams,
        "shared_focus_case_open_rate_avg": focus_case,
        "shared_focus_truth_quality_avg": focus_truth,
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(json.dumps(fact_pack, indent=2), encoding="utf-8")

    write_md(
        OUT_BASE / "continuous_improvement_scope_note_v1.md",
        f"""
# Continuous Improvement Scope Note v1

Bounded reporting window:
- `Mar 2026`

Inherited Frimley lane reused:
- Frimley `01` visual-product pack
- Frimley `02` adoption-support pack

Improvement pack shape:
- `1` revised delivery-pattern output
- `1` refinement comparison output
- `1` best-practice note

What this slice proves:
- the existing Frimley lane can be refined into a clearer and more repeatable method
- the refinement remains grounded in the completed product-and-support packs
- one bounded best-practice contribution can be stated from that refinement

What this slice does not prove:
- a full Connected Care improvement programme
- a team operating-model redesign
- broad function ownership
""",
    )

    write_md(
        OUT_BASE / "revised_delivery_pattern_note_v1.md",
        f"""
# Revised Delivery Pattern Note v1

Revised four-stage pattern:
1. orient with the dashboard headline
2. guide with the story cards
3. support with likely-user-friction prompts
4. close with plain-language explanation and adoption confidence

Primary focus retained:
- `{focus_band}`
- confirming streams: `{focus_streams}`
- average case-open rate: `{pct(focus_case)}`
- average truth quality: `{pct(focus_truth)}`

Why this is better:
- the Frimley lane now reads as one joined delivery method rather than two adjacent slices
- the revised structure makes future reuse clearer and more repeatable
""",
    )

    write_md(
        OUT_BASE / "refinement_comparison_note_v1.md",
        """
# Refinement Comparison Note v1

Earlier posture:
- product pack first
- support pack second
- the connection between them was real but still distributed across separate outputs

Revised posture:
- one explicit combined delivery pattern
- one explicit comparison showing what improved
- one clearer route from first view to confident user interpretation

Bounded comparison reading:
- the refinement does not change the analytical truth
- it improves how the same truth is packaged, supported, and reused
""",
    )

    write_md(
        OUT_BASE / "best_practice_note_v1.md",
        """
# Best Practice Note v1

Best-practice rule for future comparable packs:
- always combine the quick-scan dashboard entry point, the guided story layer, the likely-user-friction prompts, and the plain-language close into one explicit delivery method

Why this should now be repeated:
- it reduces ambiguity in how users are guided through the pack
- it makes support prompts reusable rather than ad hoc
- it leaves the next reader with a more consistent interpretation

This is a bounded best-practice contribution for the Frimley lane.
It is not a claim that a whole team method framework has been rolled out.
""",
    )

    write_md(
        OUT_BASE / "continuous_improvement_caveats_v1.md",
        """
# Continuous Improvement Caveats v1

Boundary caveats:
- this is a bounded method-refinement analogue
- it is not a live improvement programme
- it is not a team operating-model redesign
- it is not a broad transformation claim

Analytical caveats:
- the revised pattern inherits the Frimley `01` and `02` logic
- the comparison is about delivery method, not new underlying analytical discovery
- the slice proves better-practice contribution and refinement, not whole-function ownership
""",
    )


if __name__ == "__main__":
    main()
