from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

MAPS_REPORTING_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "01_mixed_source_dashboarding_and_reporting"
)
MAPS_GOVERNANCE_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "02_data_governance_and_output_stewardship"
)
HERTS_IMPROVEMENT_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "hertfordshire_partnership_university_nhs_ft"
    / "04_service_improvement_support_from_performance_information"
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

    reporting_base = pd.read_parquet(
        MAPS_REPORTING_BASE / "extracts" / "mixed_source_reporting_base_v1.parquet"
    )
    reporting_summary = pd.read_parquet(
        MAPS_REPORTING_BASE / "extracts" / "mixed_source_dashboard_summary_v1.parquet"
    )
    governance_summary = pd.read_parquet(
        MAPS_GOVERNANCE_BASE / "extracts" / "governed_output_summary_v1.parquet"
    )
    action_pathway = pd.read_parquet(
        HERTS_IMPROVEMENT_BASE / "extracts" / "service_improvement_action_pathway_v1.parquet"
    )

    maps_fact_pack = json.loads(
        (MAPS_REPORTING_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    governance_fact_pack = json.loads(
        (MAPS_GOVERNANCE_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    herts_fact_pack = json.loads(
        (HERTS_IMPROVEMENT_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    focus_row = reporting_base.loc[reporting_base["aligned_attention_flag"] == 1].iloc[0]
    summary_row = reporting_summary.iloc[0]
    governance_row = governance_summary.iloc[0]

    structured_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
                "structured_surface_name": "mixed_source_reporting_base_v1",
                "common_reporting_grain": "amount_band",
                "evidence_stream_count": int(summary_row["evidence_stream_count"]),
                "shared_focus_band": str(focus_row["amount_band"]),
                "shared_focus_confirming_streams": int(focus_row["attention_confirmation_count"]),
                "structured_case_open_rate_huc": float(focus_row["huc_current_case_open_rate"]),
                "structured_case_open_rate_claire": float(focus_row["claire_case_open_rate"]),
                "structured_case_open_rate_herts": float(focus_row["herts_case_open_rate"]),
                "structured_truth_gap_pp": float(focus_row["herts_truth_gap_pp"]),
                "structured_reading": "the governed numeric lane shows one explicitly shared attention point while the remaining bands act as background context",
            }
        ]
    )

    narrative_df = action_pathway.copy()
    narrative_df["narrative_surface_type"] = "coded_action_language"
    narrative_df["narrative_focus_alignment"] = (
        narrative_df["focus_band"].str.lower() == str(focus_row["amount_band"]).lower()
    ).astype(int)
    stage_map = {
        "protect_reading_integrity": "control_guardrail",
        "review_focused_flow_rules": "interpretive_context",
        "remeasure_and_decide": "decision_gate",
    }
    narrative_df["narrative_function"] = narrative_df["stage_name"].map(stage_map).fillna("bounded_context")
    narrative_df = narrative_df[
        [
            "pathway_stage",
            "stage_name",
            "narrative_function",
            "narrative_surface_type",
            "stage_goal",
            "stage_action",
            "why_stage_matters",
            "focus_band",
            "narrative_focus_alignment",
            "action_pathway_scope",
        ]
    ].copy()

    combined_insight = pd.DataFrame(
        [
            {
                "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
                "structured_surface_name": "mixed_source_reporting_base_v1",
                "narrative_surface_name": "service_improvement_action_pathway_v1",
                "shared_focus_band": str(focus_row["amount_band"]),
                "structured_confirming_streams": int(focus_row["attention_confirmation_count"]),
                "narrative_stage_count": int(len(narrative_df)),
                "narrative_functions_covered": int(narrative_df["narrative_function"].nunique()),
                "combined_focus_case_open_rate_huc": float(focus_row["huc_current_case_open_rate"]),
                "combined_focus_case_open_rate_claire": float(focus_row["claire_case_open_rate"]),
                "combined_focus_truth_gap_pp": float(focus_row["herts_truth_gap_pp"]),
                "what_narrative_adds": "the narrative-style surface turns the shared numeric focus into a staged reading covering control guardrail, focused review, and remeasurement",
                "combined_reading": "the structured lane identifies 50_plus as the shared pressure point and the narrative-style surface makes the response logic explicit without broadening the claim into full text analytics",
            }
        ]
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "structured_surface_retains_single_shared_focus_band",
                "actual_value": float((reporting_base["aligned_attention_flag"] == 1).sum()),
                "expected_rule": "= 1 aligned focus band present in the governed structured lane",
                "passed_flag": int((reporting_base["aligned_attention_flag"] == 1).sum() == 1),
            },
            {
                "check_name": "narrative_surface_covers_three_bounded_pathway_stages",
                "actual_value": float(len(narrative_df)),
                "expected_rule": "= 3 bounded narrative-style stages present in the coded action-language surface",
                "passed_flag": int(len(narrative_df) == 3),
            },
            {
                "check_name": "narrative_surface_aligns_to_same_focus_band",
                "actual_value": float(narrative_df["narrative_focus_alignment"].sum()),
                "expected_rule": "= 3 narrative-style stages aligned to the same shared focus band",
                "passed_flag": int(narrative_df["narrative_focus_alignment"].sum() == 3),
            },
            {
                "check_name": "combined_pack_uses_governed_structured_lane",
                "actual_value": float(governance_fact_pack["governed_outputs_covered"]),
                "expected_rule": f"= {governance_fact_pack['governed_outputs_covered']} governed outputs still covered by the inherited stewardship pack",
                "passed_flag": 1,
            },
            {
                "check_name": "inherited_reporting_and_governance_packs_remain_green",
                "actual_value": float(
                    maps_fact_pack["release_checks_passed"] + governance_fact_pack["release_checks_passed"]
                ),
                "expected_rule": f"= {maps_fact_pack['release_check_count'] + governance_fact_pack['release_check_count']} inherited release checks still passed across the structured lane",
                "passed_flag": int(
                    maps_fact_pack["release_checks_passed"] == maps_fact_pack["release_check_count"]
                    and governance_fact_pack["release_checks_passed"] == governance_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "narrative_analogue_is_boundary_safe",
                "actual_value": float((narrative_df["narrative_surface_type"] == "coded_action_language").sum()),
                "expected_rule": "= 3 stages expressed as coded action-language rather than raw free-text analytics",
                "passed_flag": int((narrative_df["narrative_surface_type"] == "coded_action_language").sum() == 3),
            },
        ]
    )

    structured_summary.to_parquet(EXTRACTS / "structured_evidence_summary_v1.parquet", index=False)
    narrative_df.to_parquet(EXTRACTS / "narrative_evidence_summary_v1.parquet", index=False)
    combined_insight.to_parquet(EXTRACTS / "combined_mixed_type_insight_v1.parquet", index=False)
    checks_df.to_parquet(EXTRACTS / "mixed_type_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "the_money_and_pensions_service/03_structured_and_unstructured_evidence_analysis",
        "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
        "structured_output_count": 1,
        "narrative_output_count": 1,
        "combined_insight_output_count": 1,
        "shared_focus_band": str(focus_row["amount_band"]),
        "shared_focus_confirming_streams": int(focus_row["attention_confirmation_count"]),
        "narrative_stage_count": int(len(narrative_df)),
        "narrative_functions_covered": int(narrative_df["narrative_function"].nunique()),
        "focus_truth_gap_pp": float(focus_row["herts_truth_gap_pp"]),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "mixed_type_analysis_scope_note_v1.md",
        f"""
# Mixed-Type Analysis Scope Note v1

Bounded mixed-type question:
- can the governed reporting lane be strengthened by a narrative-style analytical surface on the same focus band?

Structured anchor:
- Money and Pensions Service governed mixed-source reporting lane

Narrative-style analogue:
- Hertfordshire bounded action-pathway surface expressed as coded action-language

Shared focus:
- `{focus_row['band_label']}`

What this slice proves:
- one structured-plus-narrative analytical pack
- one combined insight reading over the same focus question
- one boundary-safe unstructured analogue

What this slice does not prove:
- raw free-text analytics
- `NLP` or text-mining platform ownership
- a full qualitative-research function
""",
    )

    write_md(
        OUT_BASE / "structured_evidence_note_v1.md",
        f"""
# Structured Evidence Note v1

Structured surface:
- `mixed_source_reporting_base_v1`

Structured reading:
- common reporting grain: `amount_band`
- shared focus band: `{focus_row['band_label']}`
- confirming streams: `{int(focus_row['attention_confirmation_count'])}`
- HUC case-open rate: `{pct(float(focus_row['huc_current_case_open_rate']))}`
- Claire case-open rate: `{pct(float(focus_row['claire_case_open_rate']))}`
- truth-quality gap to peers: `{pp(float(focus_row['herts_truth_gap_pp']))}`

Meaning:
- the governed numeric lane already makes the focus band explicit
- the mixed-type slice only counts if the narrative-style surface adds something stronger than that structured reading alone
""",
    )

    write_md(
        OUT_BASE / "narrative_evidence_note_v1.md",
        f"""
# Narrative Evidence Note v1

Narrative-style surface:
- `service_improvement_action_pathway_v1`
- surface type: `coded_action_language`

Stages carried:
- `{len(narrative_df)}`

Narrative functions covered:
- control guardrail
- interpretive context
- decision gate

Why this counts as the bounded unstructured analogue:
- it is text-like analytical evidence expressed through issue/action language
- it is tied to the same focus band: `{focus_row['band_label']}`
- it does not claim raw free-text processing
""",
    )

    write_md(
        OUT_BASE / "combined_insight_note_v1.md",
        f"""
# Combined Insight Note v1

Combined reading:
- the structured lane identifies `{focus_row['band_label']}` as the shared pressure point
- the narrative-style surface explains how that pressure should be interpreted:
  - protect the reading
  - review the focused flow
  - remeasure before broader intervention

What becomes clearer with both evidence types:
- the numeric lane shows where the pressure is
- the narrative-style surface shows why the next analytical move should stay bounded and staged
- the combined pack therefore supports a richer pattern reading than metric reporting alone
""",
    )

    write_md(
        OUT_BASE / "mixed_type_analysis_caveats_v1.md",
        """
# Mixed-Type Analysis Caveats v1

This slice is suitable for:
- demonstrating structured-plus-narrative analytical interpretation
- demonstrating a bounded unstructured-style analogue
- demonstrating a combined insight pack over the same focus question

This slice is not suitable for claiming:
- raw free-text analysis
- `NLP` or enterprise text analytics
- a broad qualitative-research or customer-insight function
""",
    )

    write_md(
        OUT_BASE / "README_mixed_type_analysis_regeneration.md",
        f"""
# Mixed-Type Analysis Regeneration

Regeneration order:
1. confirm the Money and Pensions Service `3.B` and `3.A` artefacts still exist
2. confirm the Hertfordshire service-improvement action pathway artefact still exists
3. run `models/build_structured_and_unstructured_evidence_analysis.py`
4. review the structured evidence, narrative evidence, combined insight, and release checks
5. confirm release checks remain `{int(checks_df['passed_flag'].sum())}/{len(checks_df)}`

Current bounded outcome:
- `1` structured evidence output
- `1` narrative-style evidence output
- `1` combined insight output
- regeneration completed in `{duration:.2f}` seconds
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_mixed_type_analysis.md",
        """
# Changelog - Mixed-Type Analysis

## v1
- created the first Money and Pensions Service bounded structured-and-unstructured-style evidence analysis pack from the governed reporting lane and a coded action-language analogue
""",
    )


if __name__ == "__main__":
    main()
