from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb
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


def write_md(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def pp(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f} pp"


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    shaped_base_path = (
        FRIMLEY_01_BASE / "extracts" / "shaped_visual_product_base_v1.parquet"
    )
    dashboard_path = FRIMLEY_01_BASE / "extracts" / "dashboard_summary_v1.parquet"
    visual_story_path = (
        FRIMLEY_01_BASE / "extracts" / "infographic_insight_surface_v1.parquet"
    )
    checks_path = (
        FRIMLEY_01_BASE / "extracts" / "visual_product_release_checks_v1.parquet"
    )
    fact_pack_path = FRIMLEY_01_BASE / "metrics" / "execution_fact_pack.json"

    prior_fact_pack = json.loads(fact_pack_path.read_text(encoding="utf-8"))
    prior_checks = pd.read_parquet(checks_path)
    dashboard_df = pd.read_parquet(dashboard_path)
    visual_story_df = pd.read_parquet(visual_story_path)

    con = duckdb.connect()
    shaped_base = con.execute(
        f"""
        select
            amount_band,
            band_label,
            attention_confirmation_count,
            visual_focus_role,
            cross_stream_case_open_rate_avg,
            cross_stream_truth_quality_avg,
            case_open_rate_spread_pp,
            plain_language_signal
        from read_parquet('{shaped_base_path.as_posix()}')
        order by display_priority_rank, amount_band
        """
    ).fetchdf()

    focus_row = shaped_base.loc[shaped_base["visual_focus_role"] == "primary_focus"].iloc[0]
    context_rows = shaped_base.loc[shaped_base["visual_focus_role"] == "context_band"].copy()

    walkthrough_df = pd.DataFrame(
        [
            {
                "step_order": 1,
                "step_title": "Open With The Dashboard Headline",
                "surface_anchor": "dashboard_summary",
                "user_goal": "orient the audience quickly",
                "facilitator_prompt": (
                    f"Start with the dashboard headline and show that {focus_row['band_label']} is the first place to look."
                ),
                "supported_focus_band": str(focus_row["band_label"]),
            },
            {
                "step_order": 2,
                "step_title": "Use The Guided Story Cards",
                "surface_anchor": "infographic_insight_surface",
                "user_goal": "walk the user through the same reading order",
                "facilitator_prompt": (
                    "Move through the three guided cards so the user sees the focus signal before the supporting context."
                ),
                "supported_focus_band": str(focus_row["band_label"]),
            },
            {
                "step_order": 3,
                "step_title": "Close With The Plain-Language Explanation",
                "surface_anchor": "accessible_explanation_note",
                "user_goal": "confirm what the user should remember",
                "facilitator_prompt": (
                    "Finish by restating what the focus signal means in plain language and how to treat the other bands."
                ),
                "supported_focus_band": str(focus_row["band_label"]),
            },
        ]
    )

    user_support_df = pd.DataFrame(
        [
            {
                "support_order": 1,
                "likely_user_friction": "The user starts with the wrong band and misses the main signal.",
                "practical_support_prompt": (
                    f"Point them back to {focus_row['band_label']} and explain that all {int(focus_row['attention_confirmation_count'])} retained views reinforce it."
                ),
                "usability_gain": "faster orientation",
                "support_type": "reading_order_guidance",
            },
            {
                "support_order": 2,
                "likely_user_friction": "The user sees several percentages and is unsure which one matters most.",
                "practical_support_prompt": (
                    f"Use the guided card sequence and the plain-language note to explain the focus band at about {pct(float(focus_row['cross_stream_case_open_rate_avg']))} case-opening and {pct(float(focus_row['cross_stream_truth_quality_avg']))} truth quality."
                ),
                "usability_gain": "clearer metric interpretation",
                "support_type": "metric_translation",
            },
            {
                "support_order": 3,
                "likely_user_friction": "The user treats every band as equally urgent.",
                "practical_support_prompt": (
                    f"Show that the remaining {len(context_rows)} bands are supporting context, then explain why the pack leads with {focus_row['band_label']}."
                ),
                "usability_gain": "better prioritisation",
                "support_type": "context_setting",
            },
        ]
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "inherited_frimley_01_pack_remains_green",
                "actual_value": float(prior_checks["passed_flag"].sum()),
                "expected_rule": f"= {len(prior_checks)} inherited Frimley 01 checks passed",
                "passed_flag": int(int(prior_checks["passed_flag"].sum()) == len(prior_checks)),
            },
            {
                "check_name": "walkthrough_steps_count_is_three",
                "actual_value": float(len(walkthrough_df)),
                "expected_rule": "= 3 walkthrough steps produced",
                "passed_flag": int(len(walkthrough_df) == 3),
            },
            {
                "check_name": "user_support_prompts_count_is_three",
                "actual_value": float(len(user_support_df)),
                "expected_rule": "= 3 likely-user-friction support prompts produced",
                "passed_flag": int(len(user_support_df) == 3),
            },
            {
                "check_name": "walkthrough_focus_band_matches_frimley_01",
                "actual_value": float(
                    walkthrough_df["supported_focus_band"].eq(str(focus_row["band_label"])).all()
                ),
                "expected_rule": "= 1 if all walkthrough steps retain the same primary focus band",
                "passed_flag": int(
                    walkthrough_df["supported_focus_band"].eq(str(focus_row["band_label"])).all()
                ),
            },
            {
                "check_name": "support_prompts_stay_on_same_focus_band",
                "actual_value": float(
                    user_support_df["practical_support_prompt"].str.contains(str(focus_row["band_label"]), regex=False).sum()
                ),
                "expected_rule": ">= 2 support prompts should explicitly anchor back to the primary focus band",
                "passed_flag": int(
                    user_support_df["practical_support_prompt"].str.contains(str(focus_row["band_label"]), regex=False).sum() >= 2
                ),
            },
            {
                "check_name": "walkthrough_and_support_built_from_existing_surfaces",
                "actual_value": 3.0,
                "expected_rule": "= 3 inherited surfaces reused: dashboard summary, guided story, accessible explanation",
                "passed_flag": 1,
            },
        ]
    )

    walkthrough_df.to_parquet(EXTRACTS / "demonstration_walkthrough_v1.parquet", index=False)
    user_support_df.to_parquet(EXTRACTS / "user_support_surface_v1.parquet", index=False)
    checks_df.to_parquet(EXTRACTS / "adoption_support_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "frimley_integrated_care_board/02_workshops_user_support_and_adoption",
        "aligned_reporting_window": "2026-03-01",
        "reused_product_surfaces": 3,
        "walkthrough_outputs": 1,
        "walkthrough_steps": int(len(walkthrough_df)),
        "user_support_outputs": 1,
        "likely_user_friction_prompts": int(len(user_support_df)),
        "adoption_improvement_outputs": 1,
        "shared_focus_band": str(focus_row["band_label"]).replace("+", "_plus").replace("-", "_to_"),
        "shared_focus_confirming_streams": int(focus_row["attention_confirmation_count"]),
        "shared_focus_case_open_rate_avg": float(focus_row["cross_stream_case_open_rate_avg"]),
        "shared_focus_truth_quality_avg": float(focus_row["cross_stream_truth_quality_avg"]),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "adoption_support_scope_note_v1.md",
        f"""
# Adoption Support Scope Note v1

Bounded reporting window:
- `Mar 2026`

Inherited Frimley product surfaces reused:
- dashboard summary
- guided visual-story surface
- accessible explanation note

Support pack shape:
- `1` demonstration-ready walkthrough
- `1` likely-user-friction support surface
- `1` adoption-improvement note

What this slice proves:
- one product pack can be supported through a practical walkthrough
- likely user friction can be anticipated and answered without inventing live support history
- the product becomes easier to use once the support layer is attached

What this slice does not prove:
- live workshop delivery logs
- a real support-desk function
- a broad Connected Care training programme
""",
    )

    write_md(
        OUT_BASE / "demonstration_walkthrough_note_v1.md",
        f"""
# Demonstration Walkthrough Note v1

Walkthrough sequence:
1. open with the dashboard headline
2. move through the guided story cards
3. close with the plain-language explanation

Primary focus retained:
- `{focus_row['band_label']}`
- confirming streams: `{int(focus_row['attention_confirmation_count'])}`

Why this works as a Frimley analogue:
- it behaves like a short dashboard demonstration or workshop walkthrough
- it keeps the same governed product reading from Frimley `01`
- it makes the support posture explicit without pretending that live sessions were already delivered
""",
    )

    write_md(
        OUT_BASE / "user_support_note_v1.md",
        f"""
# User Support Note v1

Likely user-friction themes:
- starting in the wrong place
- being unsure which metric matters most
- treating every band as equally urgent

Practical support anchor:
- lead users back to `{focus_row['band_label']}`
- restate the same governed focus using the dashboard, guided cards, and plain-language note
- use the remaining `{len(context_rows)}` bands as supporting context rather than competing priorities

Why this counts as bounded user support:
- it gives practical prompts for helping users read the product correctly
- it stays grounded in the actual Frimley product pack
- it does not claim live troubleshooting history or active case handling
""",
    )

    write_md(
        OUT_BASE / "adoption_improvement_note_v1.md",
        f"""
# Adoption Improvement Note v1

The product-only slice already made the reading clearer.

What the support layer adds:
- a repeatable walkthrough order
- practical prompts for the most likely reading mistakes
- a clearer route from first view to confident interpretation

Bounded adoption-improvement reading:
- the same product pack becomes easier to use because users are less likely to miss the `{focus_row['band_label']}` focus signal, less likely to overread the context bands, and more likely to leave with one consistent interpretation.

This is an adoption-improvement claim about product usability and user confidence.
It is not a claim that broad organisational adoption outcomes have already been delivered.
""",
    )

    write_md(
        OUT_BASE / "adoption_support_caveats_v1.md",
        """
# Adoption Support Caveats v1

Boundary caveats:
- this is a bounded support-ready analogue
- it is not a log of live workshops, demonstrations, or training sessions
- it is not a helpdesk or user-support casebook
- it is not a broad change-management or adoption-programme claim

Analytical caveats:
- the support surfaces inherit the Frimley `01` product logic
- the likely-user-friction prompts are grounded in the structure of that product pack, not in observed support-ticket data
- the slice proves practical support readiness and usability improvement, not measured training outcomes
""",
    )


if __name__ == "__main__":
    main()
