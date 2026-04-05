from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

MAPS_MIXED_TYPE_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "03_structured_and_unstructured_evidence_analysis"
)
MAPS_FRAMEWORK_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "05_kpi_and_framework_measurement_support"
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
    return f"{sign}{value:.2f} pp"


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    structured_summary = pd.read_parquet(
        MAPS_MIXED_TYPE_BASE / "extracts" / "structured_evidence_summary_v1.parquet"
    )
    narrative_summary = pd.read_parquet(
        MAPS_MIXED_TYPE_BASE / "extracts" / "narrative_evidence_summary_v1.parquet"
    )
    combined_mixed_type = pd.read_parquet(
        MAPS_MIXED_TYPE_BASE / "extracts" / "combined_mixed_type_insight_v1.parquet"
    )
    framework_change = pd.read_parquet(
        MAPS_FRAMEWORK_BASE / "extracts" / "change_tracking_summary_v1.parquet"
    )
    improvement_priority = pd.read_parquet(
        HERTS_IMPROVEMENT_BASE / "extracts" / "service_improvement_priority_v1.parquet"
    )
    action_pathway = pd.read_parquet(
        HERTS_IMPROVEMENT_BASE / "extracts" / "service_improvement_action_pathway_v1.parquet"
    )

    mixed_type_fact_pack = json.loads(
        (MAPS_MIXED_TYPE_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    framework_fact_pack = json.loads(
        (MAPS_FRAMEWORK_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    herts_fact_pack = json.loads(
        (HERTS_IMPROVEMENT_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    structured_row = structured_summary.iloc[0]
    combined_row = combined_mixed_type.iloc[0]
    priority_row = improvement_priority.iloc[0]
    focus_band = str(structured_row["shared_focus_band"])
    aligned_narrative = narrative_summary.loc[
        narrative_summary["focus_band"].str.lower() == focus_band.lower()
    ].copy()
    aligned_change = framework_change.loc[
        framework_change["shared_focus_band"].str.lower() == focus_band.lower()
    ].copy()

    quantitative_evaluation = pd.DataFrame(
        [
            {
                "aligned_reporting_window": str(structured_row["aligned_reporting_window"]),
                "evaluation_question": "does the focused review and remeasurement support approach show bounded signs of effectiveness on the persistent 50_plus pocket?",
                "bounded_intervention_name": "focused_review_and_remeasurement_support_pathway",
                "quantitative_surface_name": "change_tracking_summary_v1",
                "shared_focus_band": focus_band,
                "confirming_stream_count": int(structured_row["shared_focus_confirming_streams"]),
                "case_pressure_gap_current_pp": float(
                    aligned_change.loc[
                        aligned_change["kpi_name"] == "focus_case_open_gap_to_peer_pp", "current_value"
                    ].iloc[0]
                ),
                "case_pressure_gap_change_pp": float(
                    aligned_change.loc[
                        aligned_change["kpi_name"] == "focus_case_open_gap_to_peer_pp", "net_change_pp"
                    ].iloc[0]
                ),
                "truth_quality_gap_current_pp": float(
                    aligned_change.loc[
                        aligned_change["kpi_name"] == "focus_truth_quality_gap_to_peer_pp", "current_value"
                    ].iloc[0]
                ),
                "truth_quality_gap_change_pp": float(
                    aligned_change.loc[
                        aligned_change["kpi_name"] == "focus_truth_quality_gap_to_peer_pp", "net_change_pp"
                    ].iloc[0]
                ),
                "quantitative_effect_reading": "the quantitative side shows persistent pressure with only marginal narrowing on case pressure and some intended-direction movement on quality, so the support approach reads as bounded and incomplete rather than fully effective",
            }
        ]
    )

    qualitative_support = aligned_narrative.copy()
    qualitative_support["qualitative_surface_name"] = "service_improvement_action_pathway_v1"
    qualitative_support["qualitative_analogue_type"] = "coded_support_and_action_language"
    qualitative_support["bounded_intervention_name"] = "focused_review_and_remeasurement_support_pathway"
    qualitative_support["qualitative_contribution"] = qualitative_support["narrative_function"].map(
        {
            "control_guardrail": "shows that the support approach protected reading integrity before claiming change",
            "interpretive_context": "shows that the support approach narrowed review to the persistent pocket rather than widening the question",
            "decision_gate": "shows that the support approach required remeasurement before any stronger effectiveness claim",
        }
    )
    qualitative_support = qualitative_support[
        [
            "bounded_intervention_name",
            "qualitative_surface_name",
            "qualitative_analogue_type",
            "pathway_stage",
            "stage_name",
            "narrative_function",
            "stage_goal",
            "stage_action",
            "why_stage_matters",
            "qualitative_contribution",
            "focus_band",
            "action_pathway_scope",
        ]
    ].copy()

    intervention_effectiveness = pd.DataFrame(
        [
            {
                "aligned_reporting_window": str(structured_row["aligned_reporting_window"]),
                "bounded_intervention_name": "focused_review_and_remeasurement_support_pathway",
                "shared_focus_band": focus_band,
                "quantitative_effect_surface": "change_tracking_summary_v1",
                "qualitative_support_surface": "service_improvement_action_pathway_v1",
                "quantitative_effect_summary": str(quantitative_evaluation.iloc[0]["quantitative_effect_reading"]),
                "qualitative_effect_summary": "the qualitative-style side shows a disciplined support pathway built around control, focused review, and remeasurement rather than premature success language",
                "bounded_effectiveness_reading": "taken together, the evidence supports a bounded reading that the support approach is methodologically appropriate and directionally encouraging on quality, but not yet strong enough to claim delivered intervention effectiveness on the pressure gap",
                "accountability_position": "the current evaluation is strong enough to justify continued review, protected interpretation, and remeasurement, but not strong enough to support a broad success or institutional-benefit claim",
            }
        ]
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "quantitative_surface_retains_single_bounded_focus_question",
                "actual_value": float(len(quantitative_evaluation)),
                "expected_rule": "= 1 bounded quantitative evaluation output present",
                "passed_flag": int(len(quantitative_evaluation) == 1),
            },
            {
                "check_name": "qualitative_surface_covers_three_support_stages",
                "actual_value": float(len(qualitative_support)),
                "expected_rule": "= 3 qualitative-style support stages retained on the same bounded intervention",
                "passed_flag": int(len(qualitative_support) == 3),
            },
            {
                "check_name": "quantitative_side_uses_two_directional_kpis",
                "actual_value": float(len(aligned_change)),
                "expected_rule": "= 2 directional KPIs retained for the quantitative evaluation side",
                "passed_flag": int(len(aligned_change) == 2),
            },
            {
                "check_name": "qualitative_side_stays_boundary_safe",
                "actual_value": float(
                    (qualitative_support["qualitative_analogue_type"] == "coded_support_and_action_language").sum()
                ),
                "expected_rule": "= 3 rows expressed as coded support/action language rather than live fieldwork evidence",
                "passed_flag": int(
                    (qualitative_support["qualitative_analogue_type"] == "coded_support_and_action_language").sum()
                    == 3
                ),
            },
            {
                "check_name": "mixed_type_pack_remains_green",
                "actual_value": float(mixed_type_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {mixed_type_fact_pack['release_check_count']} inherited mixed-type checks remain green",
                "passed_flag": int(
                    mixed_type_fact_pack["release_checks_passed"] == mixed_type_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "framework_pack_remains_green",
                "actual_value": float(framework_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {framework_fact_pack['release_check_count']} inherited framework checks remain green",
                "passed_flag": int(
                    framework_fact_pack["release_checks_passed"] == framework_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "improvement_pack_remains_green",
                "actual_value": float(herts_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {herts_fact_pack['release_check_count']} inherited improvement checks remain green",
                "passed_flag": int(herts_fact_pack["release_checks_passed"] == herts_fact_pack["release_check_count"]),
            },
        ]
    )

    quantitative_evaluation.to_parquet(EXTRACTS / "quantitative_evaluation_output_v1.parquet", index=False)
    qualitative_support.to_parquet(EXTRACTS / "qualitative_support_output_v1.parquet", index=False)
    intervention_effectiveness.to_parquet(EXTRACTS / "intervention_effectiveness_output_v1.parquet", index=False)
    checks_df.to_parquet(EXTRACTS / "mixed_method_evaluation_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "university_of_cambridge/01_mixed_method_evaluation_and_effectiveness",
        "aligned_reporting_window": str(structured_row["aligned_reporting_window"]),
        "quantitative_evaluation_output_count": 1,
        "qualitative_support_output_count": 1,
        "intervention_effectiveness_output_count": 1,
        "shared_focus_band": focus_band,
        "shared_focus_confirming_streams": int(structured_row["shared_focus_confirming_streams"]),
        "qualitative_support_stage_count": int(len(qualitative_support)),
        "directional_kpis_used": int(len(aligned_change)),
        "current_case_pressure_gap_pp": float(
            quantitative_evaluation.iloc[0]["case_pressure_gap_current_pp"]
        ),
        "current_truth_quality_gap_pp": float(
            quantitative_evaluation.iloc[0]["truth_quality_gap_current_pp"]
        ),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "mixed_method_evaluation_scope_note_v1.md",
        f"""
# Mixed-Method Evaluation Scope Note v1

Bounded evaluation question:
- does the focused review and remeasurement support approach show bounded signs of effectiveness on the persistent `{focus_band}` pocket?

Quantitative side:
- `change_tracking_summary_v1`

Qualitative-style side:
- `service_improvement_action_pathway_v1`
- expressed as coded support and action language, not live fieldwork evidence

Why this counts as a mixed-method analogue:
- the quantitative side carries the effect and change reading
- the qualitative-style side carries the support, review, and remeasurement logic
- both surfaces stay on the same bounded intervention question

What this slice proves:
- one bounded mixed-method evaluation pack
- one intervention-effectiveness reading that stays proportional to the evidence
- one accountability-facing note for future decisions

What this slice does not prove:
- live surveys, interviews, or focus groups
- a full Cambridge institutional evaluation framework
- strong causal proof or quantified institutional-benefit ownership
""",
    )

    write_md(
        OUT_BASE / "quantitative_evaluation_note_v1.md",
        f"""
# Quantitative Evaluation Note v1

Quantitative surface:
- `change_tracking_summary_v1`

Shared focus:
- `{focus_band}`
- confirming streams: `{int(structured_row['shared_focus_confirming_streams'])}`

Quantitative reading:
- current case-pressure gap: `{pp(float(quantitative_evaluation.iloc[0]['case_pressure_gap_current_pp']))}`
- case-pressure change: `{pp(float(quantitative_evaluation.iloc[0]['case_pressure_gap_change_pp']))}`
- current truth-quality gap: `{pp(float(quantitative_evaluation.iloc[0]['truth_quality_gap_current_pp']))}`
- truth-quality change: `{pp(float(quantitative_evaluation.iloc[0]['truth_quality_gap_change_pp']))}`

Evaluation meaning:
- the quantitative side shows persistent pressure with only small narrowing on case pressure
- the quality side is moving in the intended direction, but the gap remains material
- this supports a bounded effectiveness reading, not a delivered-impact claim
""",
    )

    write_md(
        OUT_BASE / "qualitative_support_note_v1.md",
        f"""
# Qualitative Support Note v1

Qualitative-style surface:
- `service_improvement_action_pathway_v1`
- analogue type: `coded_support_and_action_language`

Stages carried:
- `{len(qualitative_support)}`

Why this counts as the qualitative-style side:
- it records the support logic in text-like staged language
- it shows how the bounded approach protects interpretation, narrows review, and requires remeasurement
- it remains tied to the same focus band: `{focus_band}`

Boundary:
- this is not live fieldwork and not a real interview or focus-group surface
- it is a bounded qualitative-style support analogue
""",
    )

    write_md(
        OUT_BASE / "intervention_effectiveness_note_v1.md",
        f"""
# Intervention Effectiveness Note v1

Bounded intervention or support approach:
- focused review and remeasurement support pathway on the persistent `{focus_band}` pocket

Combined reading:
- the quantitative side shows bounded directional movement rather than a decisive effect
- the qualitative-style side shows a disciplined support method built around control, focused review, and remeasurement
- taken together, the evidence supports a cautious reading of partial or developing effectiveness rather than a broad success claim

Most defensible conclusion:
- the support approach appears methodologically appropriate and still worth continuing
- the current pack does not justify strong delivered-effectiveness language on the pressure gap
""",
    )

    write_md(
        OUT_BASE / "accountability_benefits_note_v1.md",
        f"""
# Accountability And Benefits Note v1

Accountability-facing reading:
- the current evaluation pack is strong enough to support continued review, remeasurement, and bounded accountability around the `{focus_band}` pocket
- it is strong enough to show why the support approach should remain in place while the evidence matures

Benefits-style boundary:
- the pack can support discussion of decision-support value and accountability support
- the pack cannot support quantified institutional-benefit ownership
- the pack cannot support a broad claim that the intervention has already fully worked
""",
    )

    write_md(
        OUT_BASE / "mixed_method_evaluation_caveats_v1.md",
        f"""
# Mixed-Method Evaluation Caveats v1

This slice is bounded.

Key caveats:
- the qualitative side is an honest analogue built from coded support and action language
- the slice does not claim live survey, interview, or focus-group delivery
- the effectiveness reading stays below strong causal proof
- the benefits reading stays below quantified institutional-benefit ownership
- the pack should be reused as a bounded evaluation-and-accountability proof, not as a full institutional evaluation claim
""",
    )

    write_md(
        OUT_BASE / "README_mixed_method_evaluation_regeneration.md",
        """
# Mixed-Method Evaluation Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/university_of_cambridge/01_mixed_method_evaluation_and_effectiveness/models/build_mixed_method_evaluation_and_effectiveness.py
```

The builder reads only compact inherited outputs and writes the bounded mixed-method evaluation pack for the Cambridge `C + E` slice.
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_mixed_method_evaluation.md",
        """
# Changelog - Mixed-Method Evaluation And Effectiveness

- v1: built the first bounded Cambridge mixed-method evaluation pack from inherited compact quantitative, qualitative-style, and improvement-support outputs
""",
    )


if __name__ == "__main__":
    main()
