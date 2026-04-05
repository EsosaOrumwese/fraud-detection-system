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

MPS_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "01_mixed_source_dashboarding_and_reporting"
)

BAND_ORDER = ["under_10", "10_to_25", "25_to_50", "50_plus"]


def write_md(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def pp(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f} pp"


def mean_across(row: pd.Series, cols: list[str]) -> float:
    values = [float(row[col]) for col in cols if pd.notna(row[col])]
    return float(sum(values) / len(values)) if values else float("nan")


def spread_across(row: pd.Series, cols: list[str]) -> float:
    values = [float(row[col]) for col in cols if pd.notna(row[col])]
    return float(max(values) - min(values)) if len(values) >= 2 else 0.0


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    detail_path = (
        MPS_BASE / "extracts" / "mixed_source_reporting_detail_v1.parquet"
    )
    summary_path = (
        MPS_BASE / "extracts" / "mixed_source_dashboard_summary_v1.parquet"
    )
    checks_path = (
        MPS_BASE / "extracts" / "mixed_source_release_checks_v1.parquet"
    )
    fact_pack_path = MPS_BASE / "metrics" / "execution_fact_pack.json"

    source_fact_pack = json.loads(fact_pack_path.read_text(encoding="utf-8"))
    source_checks = pd.read_parquet(checks_path)
    source_summary = pd.read_parquet(summary_path)

    con = duckdb.connect()
    shaped_base = con.execute(
        f"""
        select
            amount_band,
            band_label,
            stream_coverage_count,
            attention_confirmation_count,
            aligned_attention_flag,
            cross_source_reading,
            huc_current_case_open_rate,
            claire_case_open_rate,
            herts_case_open_rate,
            huc_current_truth_quality,
            claire_truth_quality,
            herts_truth_quality,
            huc_avg_lifecycle_hours,
            claire_case_open_gap_pp,
            herts_case_open_gap_pp,
            claire_truth_gap_pp,
            herts_truth_gap_pp,
            shortfall_status
        from read_parquet('{detail_path.as_posix()}')
        order by case amount_band
            when 'under_10' then 1
            when '10_to_25' then 2
            when '25_to_50' then 3
            when '50_plus' then 4
            else 99 end
        """
    ).fetchdf()

    case_rate_cols = [
        "huc_current_case_open_rate",
        "claire_case_open_rate",
        "herts_case_open_rate",
    ]
    truth_cols = [
        "huc_current_truth_quality",
        "claire_truth_quality",
        "herts_truth_quality",
    ]

    shaped_base["sql_preparation_flag"] = 1
    shaped_base["visual_focus_role"] = shaped_base["aligned_attention_flag"].map(
        {1: "primary_focus", 0: "context_band"}
    )
    shaped_base["cross_stream_case_open_rate_avg"] = shaped_base.apply(
        lambda row: mean_across(row, case_rate_cols), axis=1
    )
    shaped_base["cross_stream_truth_quality_avg"] = shaped_base.apply(
        lambda row: mean_across(row, truth_cols), axis=1
    )
    shaped_base["case_open_rate_spread_pp"] = shaped_base.apply(
        lambda row: spread_across(row, case_rate_cols), axis=1
    )
    shaped_base["truth_quality_spread_pp"] = shaped_base.apply(
        lambda row: spread_across(row, truth_cols), axis=1
    )
    shaped_base["display_priority_rank"] = (
        shaped_base["attention_confirmation_count"]
        .rank(ascending=False, method="dense")
        .astype(int)
    )
    shaped_base["plain_language_signal"] = shaped_base.apply(
        lambda row: (
            "Start here because every retained view points to this band."
            if row["visual_focus_role"] == "primary_focus"
            else "Use this band as supporting context after the main focus has been explained."
        ),
        axis=1,
    )
    shaped_base["visual_reading_caption"] = shaped_base.apply(
        lambda row: (
            "shared_focus_across_retained_views"
            if row["visual_focus_role"] == "primary_focus"
            else "background_context_for_the_main_story"
        ),
        axis=1,
    )

    focus_row = shaped_base.sort_values(
        ["attention_confirmation_count", "stream_coverage_count"],
        ascending=[False, False],
    ).iloc[0]

    dashboard_df = pd.DataFrame(
        [
            {
                "aligned_reporting_window": "Mar 2026",
                "source_evidence_stream_count": int(
                    source_fact_pack["evidence_stream_count"]
                ),
                "shaped_base_row_count": int(len(shaped_base)),
                "dashboard_output_count": 1,
                "visual_story_output_count": 1,
                "primary_focus_band": str(focus_row["band_label"]),
                "primary_focus_confirming_streams": int(
                    focus_row["attention_confirmation_count"]
                ),
                "primary_focus_case_open_rate_avg": float(
                    focus_row["cross_stream_case_open_rate_avg"]
                ),
                "primary_focus_truth_quality_avg": float(
                    focus_row["cross_stream_truth_quality_avg"]
                ),
                "dashboard_headline": (
                    "the combined view keeps one clear starting point for non-technical readers"
                ),
                "summary_reading": (
                    "50+ remains the only band reinforced across all retained evidence streams while the remaining bands provide supporting context"
                ),
            }
        ]
    )

    infographic_df = pd.DataFrame(
        [
            {
                "card_order": 1,
                "card_title": "Start Here",
                "focus_band": str(focus_row["band_label"]),
                "card_message": (
                    f"Begin with {focus_row['band_label']} because it is the only band confirmed by all "
                    f"{int(focus_row['attention_confirmation_count'])} retained evidence streams."
                ),
                "support_metric_label": "Confirming streams",
                "support_metric_value": str(
                    int(focus_row["attention_confirmation_count"])
                ),
            },
            {
                "card_order": 2,
                "card_title": "What The Numbers Say",
                "focus_band": str(focus_row["band_label"]),
                "card_message": (
                    f"Across the retained views, the focus band sits around {pct(float(focus_row['cross_stream_case_open_rate_avg']))} "
                    f"case-opening and {pct(float(focus_row['cross_stream_truth_quality_avg']))} truth quality."
                ),
                "support_metric_label": "Cross-stream case-open spread",
                "support_metric_value": pp(float(focus_row["case_open_rate_spread_pp"])),
            },
            {
                "card_order": 3,
                "card_title": "How To Read The Rest",
                "focus_band": str(focus_row["band_label"]),
                "card_message": (
                    "Treat the remaining bands as context bands. They help show that the wider picture is comparatively stable rather than competing for equal attention."
                ),
                "support_metric_label": "Context bands",
                "support_metric_value": str(int(len(shaped_base) - 1)),
            },
        ]
    )

    checks = pd.DataFrame(
        [
            {
                "check_name": "inherited_mixed_source_pack_remains_green",
                "actual_value": float(source_checks["passed_flag"].sum()),
                "expected_rule": f"= {len(source_checks)} inherited mixed-source checks passed",
                "passed_flag": int(
                    int(source_checks["passed_flag"].sum()) == len(source_checks)
                ),
            },
            {
                "check_name": "shaped_base_row_count_matches_common_grain",
                "actual_value": float(len(shaped_base)),
                "expected_rule": "= 4 shaped rows retained for the shared amount-band grain",
                "passed_flag": int(len(shaped_base) == 4),
            },
            {
                "check_name": "dashboard_summary_row_count_is_one",
                "actual_value": float(len(dashboard_df)),
                "expected_rule": "= 1 dashboard summary row produced",
                "passed_flag": int(len(dashboard_df) == 1),
            },
            {
                "check_name": "visual_story_card_count_is_three",
                "actual_value": float(len(infographic_df)),
                "expected_rule": "= 3 guided visual-story cards produced",
                "passed_flag": int(len(infographic_df) == 3),
            },
            {
                "check_name": "primary_focus_band_matches_inherited_pack",
                "actual_value": float(
                    str(focus_row["amount_band"]) == str(source_fact_pack["shared_focus_band"])
                ),
                "expected_rule": "= 1 if the Frimley primary focus band matches the inherited mixed-source focus band",
                "passed_flag": int(
                    str(focus_row["amount_band"]) == str(source_fact_pack["shared_focus_band"])
                ),
            },
            {
                "check_name": "primary_focus_confirming_streams_match_inherited_pack",
                "actual_value": float(focus_row["attention_confirmation_count"]),
                "expected_rule": f"= {source_fact_pack['shared_focus_confirming_streams']} confirming streams on the primary focus band",
                "passed_flag": int(
                    int(focus_row["attention_confirmation_count"])
                    == int(source_fact_pack["shared_focus_confirming_streams"])
                ),
            },
            {
                "check_name": "dashboard_and_visual_story_share_same_focus_band",
                "actual_value": float(
                    infographic_df["focus_band"].eq(dashboard_df.iloc[0]["primary_focus_band"]).all()
                ),
                "expected_rule": "= 1 if all visual-story cards reference the same primary focus band as the dashboard summary",
                "passed_flag": int(
                    infographic_df["focus_band"].eq(
                        dashboard_df.iloc[0]["primary_focus_band"]
                    ).all()
                ),
            },
        ]
    )

    shaped_base.to_parquet(
        EXTRACTS / "shaped_visual_product_base_v1.parquet", index=False
    )
    dashboard_df.to_parquet(EXTRACTS / "dashboard_summary_v1.parquet", index=False)
    infographic_df.to_parquet(
        EXTRACTS / "infographic_insight_surface_v1.parquet", index=False
    )
    checks.to_parquet(EXTRACTS / "visual_product_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "frimley_integrated_care_board/01_data_to_visual_product_and_accessible_insight",
        "aligned_reporting_window": "2026-03-01",
        "source_evidence_stream_count": int(source_fact_pack["evidence_stream_count"]),
        "shaped_base_rows": int(len(shaped_base)),
        "dashboard_output_count": 1,
        "visual_story_output_count": 1,
        "guided_story_stage_count": int(len(infographic_df)),
        "shared_focus_band": str(focus_row["amount_band"]),
        "shared_focus_confirming_streams": int(
            focus_row["attention_confirmation_count"]
        ),
        "shared_focus_case_open_rate_avg": float(
            focus_row["cross_stream_case_open_rate_avg"]
        ),
        "shared_focus_truth_quality_avg": float(
            focus_row["cross_stream_truth_quality_avg"]
        ),
        "shared_focus_case_open_spread_pp": float(
            focus_row["case_open_rate_spread_pp"]
        ),
        "release_checks_passed": int(checks["passed_flag"].sum()),
        "release_check_count": int(len(checks)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "visual_product_scope_note_v1.md",
        f"""
# Visual Product Scope Note v1

Bounded reporting window:
- `Mar 2026`

Inherited governed base:
- reused from Money and Pensions Service `3.B`
- `3` retained evidence streams on one shared `amount_band` grain
- first-pass shaping kept strictly on static analytical surfaces, not multimedia production

Product surfaces:
- `1` dashboard-style summary
- `1` infographic-style guided insight surface
- `1` accessible explanation note

What this slice proves:
- shaped governed data into a user-facing visual pack
- kept one stable analytical story across two presentation surfaces
- translated the same analytical logic for non-technical readers

What this slice does not prove:
- a live Connected Care dashboard estate
- full `Power BI` or `Tableau` workspace ownership
- workshops, training, or adoption support
""",
    )

    write_md(
        OUT_BASE / "shaped_base_note_v1.md",
        f"""
# Shaped Base Note v1

Preparation posture:
- the Frimley slice uses a compact SQL-style shaping step over an inherited mixed-source reporting base
- the shaping layer retains only the fields needed for a user-facing dashboard summary and guided visual-story surface

Retained product grain:
- `amount_band`
- row count retained: `{len(shaped_base)}`

Primary focus band after shaping:
- `{focus_row['band_label']}`
- confirming streams: `{int(focus_row['attention_confirmation_count'])}`

Cross-stream focus readings:
- average case-open rate: `{pct(float(focus_row['cross_stream_case_open_rate_avg']))}`
- average truth quality: `{pct(float(focus_row['cross_stream_truth_quality_avg']))}`
- case-open spread across retained streams: `{pp(float(focus_row['case_open_rate_spread_pp']))}`

Why this shaping layer matters:
- it behaves like the `SQL`-to-product preparation step the Frimley role expects
- it converts a mixed-source analytical pack into a cleaner visual-product base without reopening raw scope
""",
    )

    write_md(
        OUT_BASE / "dashboard_summary_note_v1.md",
        f"""
# Dashboard Summary Note v1

Dashboard headline:
- the combined view keeps one clear starting point for non-technical readers

Dashboard summary:
- shared focus band: `{focus_row['band_label']}`
- retained evidence streams: `{int(source_fact_pack['evidence_stream_count'])}`
- confirming streams on the focus band: `{int(focus_row['attention_confirmation_count'])}`
- focus-band average case-open rate: `{pct(float(focus_row['cross_stream_case_open_rate_avg']))}`
- focus-band average truth quality: `{pct(float(focus_row['cross_stream_truth_quality_avg']))}`

What the dashboard is for:
- orient a non-technical reader quickly
- show which part of the governed view deserves attention first
- keep the supporting context available without overwhelming the first read
""",
    )

    write_md(
        OUT_BASE / "infographic_insight_note_v1.md",
        f"""
# Infographic Insight Note v1

Guided card sequence:
1. `Start Here`
   - lead with `{focus_row['band_label']}` because all retained evidence streams reinforce it
2. `What The Numbers Say`
   - explain the focus band in plain language using average case-open and truth-quality readings
3. `How To Read The Rest`
   - position the remaining bands as context rather than competing priorities

Why this counts as the second surface:
- it uses the same governed shaped base as the dashboard summary
- it changes the reading order and language, not the underlying truth
- it is stronger as a static guided insight surface than as a fake multimedia artefact
""",
    )

    write_md(
        OUT_BASE / "accessible_explanation_note_v1.md",
        f"""
# Accessible Explanation Note v1

If you are not an analyst, the quickest way to read this pack is:
- start with `{focus_row['band_label']}`
- notice that all `{int(focus_row['attention_confirmation_count'])}` retained evidence streams point to that same band
- read the remaining three bands as background context rather than as equal-priority signals

In plain language:
- the combined view is not saying that everything is changing everywhere
- it is saying that one part of the picture stands out consistently, while the rest of the picture helps show baseline context

Why this matters:
- the same governed data has been turned into a quicker, clearer reading for a non-technical audience
- the explanation stays faithful to the analytical base rather than adding unsupported domain narrative
""",
    )

    write_md(
        OUT_BASE / "visual_product_caveats_v1.md",
        """
# Visual Product Caveats v1

Boundary caveats:
- this is a bounded static visual-product analogue
- it is not a live Connected Care dashboard estate
- it is not a multimedia-production claim
- it is not yet a training or user-support slice

Analytical caveats:
- the pack inherits the governed mixed-source `amount_band` grain from the earlier Money and Pensions Service slice
- the visual products are only as broad as that inherited governed base
- the slice proves accessible presentation and explanation, not new underlying domain logic
""",
    )


if __name__ == "__main__":
    main()
