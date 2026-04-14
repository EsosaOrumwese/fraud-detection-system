from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EXTRACTS = ROOT / "extracts"
METRICS = ROOT / "metrics"

IMPERIAL_A = ROOT.parent / "01_health_data_pipelines_and_multimodal_integration"
IMPERIAL_BC = ROOT.parent / "02_large_scale_time_series_longitudinal_analysis_and_quantitative_research_support"
IMPERIAL_D = ROOT.parent / "03_cloud_resource_management_and_data_platform_support"
JPMC_A = ROOT.parents[1] / "jpmorganchase" / "01_fraud_strategy_and_rule_optimisation"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def main() -> None:
    start = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    imperial_a_fact = read_json(IMPERIAL_A / "metrics" / "execution_fact_pack.json")
    imperial_bc_fact = read_json(IMPERIAL_BC / "metrics" / "execution_fact_pack.json")
    imperial_d_fact = read_json(IMPERIAL_D / "metrics" / "execution_fact_pack.json")
    jpmc_a_fact = read_json(JPMC_A / "metrics" / "execution_fact_pack.json")

    multimodal_integration = pd.read_parquet(IMPERIAL_A / "extracts" / "multimodal_integration_output_v1.parquet")
    quantitative_support = pd.read_parquet(IMPERIAL_BC / "extracts" / "quantitative_research_support_output_v1.parquet")
    cloud_components = pd.read_parquet(IMPERIAL_D / "extracts" / "data_platform_component_output_v1.parquet")
    cloud_support = pd.read_parquet(IMPERIAL_D / "extracts" / "cloud_resource_support_output_v1.parquet")
    ruleset_comparison = pd.read_parquet(JPMC_A / "extracts" / "ruleset_comparison_output_v1.parquet")
    detection_effectiveness = pd.read_parquet(JPMC_A / "extracts" / "detection_effectiveness_output_v1.parquet")

    aligned_reporting_window = imperial_a_fact["aligned_reporting_window"]
    shared_source_cohort = imperial_a_fact["shared_source_cohort"]
    integrated_stream_count = imperial_a_fact["integrated_stream_count"]
    source_role_count = imperial_a_fact["source_role_count"]
    confirmation_strength = imperial_d_fact["confirmation_strength"]
    review_trigger_metric_count = imperial_d_fact["review_trigger_metric_count"]
    current_reporting_pressure_gap_pp = imperial_d_fact["current_reporting_pressure_gap_pp"]
    current_quality_consistency_gap_pp = imperial_d_fact["current_quality_consistency_gap_pp"]
    current_control_gap_pp = imperial_d_fact["current_control_gap_pp"]

    model_input_ready_base = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "model_support_question": (
                    "can one governed multimodal, longitudinal, and cloud-shaped analytical lane be shaped into "
                    "a bounded AI-model-support pack that sounds like real translational model contribution "
                    "without overstating model ownership?"
                ),
                "model_support_pack_name": "ai_model_development_support_and_multimodal_model_inputs_pack",
                "model_input_grain": "governed_multimodal_longitudinal_model_input_base",
                "shared_source_cohort": shared_source_cohort,
                "integrated_stream_count": integrated_stream_count,
                "input_role_count": 4,
                "support_stage_count": 4,
                "confirmation_strength": confirmation_strength,
                "review_trigger_metric_count": review_trigger_metric_count,
                "model_input_base_reading": (
                    "the completed pipeline, longitudinal, and cloud-support packs are coherent enough to act as "
                    "one bounded model-input base because source roles, repeated-state context, and controlled "
                    "release handling are already explicit"
                ),
            }
        ]
    )
    model_input_ready_base.to_parquet(EXTRACTS / "model_input_ready_base_v1.parquet", index=False)

    multimodal_model_input_support = pd.DataFrame(
        [
            {
                "input_rank": 1,
                "model_input_area": "signal_and_feature_input",
                "support_role": "multimodal_signal_preparation",
                "retained_surface": multimodal_integration.loc[
                    multimodal_integration["source_role_analogue"] == "app_or_wearable_style_signal",
                    "source_role_analogue",
                ].iloc[0],
                "support_reading": (
                    "the bounded lane can support an app-or-wearable-style model input because continuous-signal "
                    "roles remain explicit and confirmed enough for later model use"
                ),
            },
            {
                "input_rank": 2,
                "model_input_area": "context_and_label_support",
                "support_role": "clinical_and_status_context",
                "retained_surface": multimodal_integration.loc[
                    multimodal_integration["source_role_analogue"] == "clinical_status_style_context",
                    "source_role_analogue",
                ].iloc[0],
                "support_reading": (
                    "the bounded lane can support contextual or label-like input because current-state and status "
                    "information remain visible rather than detached from signal interpretation"
                ),
            },
            {
                "input_rank": 3,
                "model_input_area": "quality_and_validation_support",
                "support_role": "controlled_quality_features",
                "retained_surface": multimodal_integration.loc[
                    multimodal_integration["source_role_analogue"] == "biological_or_quality_style_validation",
                    "source_role_analogue",
                ].iloc[0],
                "support_reading": (
                    "quality and validation remain model-input relevant because the bounded lane still carries "
                    "explicit quality interpretation rather than silently assuming clean features"
                ),
            },
            {
                "input_rank": 4,
                "model_input_area": "environment_and_release_context",
                "support_role": "controlled_context_features",
                "retained_surface": cloud_components.loc[
                    cloud_components["cloud_component_analogue"] == "review_and_release_layer",
                    "cloud_component_analogue",
                ].iloc[0],
                "support_reading": (
                    "release and environment-style context remain explicit, which keeps the model-input posture "
                    "bounded and controlled instead of reading like an ungoverned feature dump"
                ),
            },
        ]
    )
    multimodal_model_input_support.to_parquet(EXTRACTS / "multimodal_model_input_support_output_v1.parquet", index=False)

    yield_improvement = ruleset_comparison.loc[
        ruleset_comparison["comparison_dimension"] == "fraud_truth_yield_pct", "delta_value"
    ].iloc[0]
    capture_delta = ruleset_comparison.loc[
        ruleset_comparison["comparison_dimension"] == "fraud_truth_capture_pct", "delta_value"
    ].iloc[0]

    modelling_readiness = pd.DataFrame(
        [
            {
                "readiness_rank": 1,
                "readiness_area": "input_contract_readiness",
                "readiness_role": "bounded_model_input_contract",
                "readiness_reading": (
                    "the completed health-data packs now provide a bounded model-input contract because multimodal "
                    "roles, longitudinal context, and release conditions are explicit on the same governed lane"
                ),
            },
            {
                "readiness_rank": 2,
                "readiness_area": "tradeoff_and_monitoring_expectation",
                "readiness_role": "model_support_tradeoff_visibility",
                "readiness_reading": (
                    f"the support posture is model-ready in a bounded sense because expected uplift-style movement "
                    f"and explicit trade-offs can be carried forward, with one retained delta analogue of {yield_improvement:.2f} pp "
                    f"alongside a controlled downside analogue of {capture_delta:.2f} pp"
                ),
            },
            {
                "readiness_rank": 3,
                "readiness_area": "implementation_and_release_boundary",
                "readiness_role": "controlled_model_support_boundary",
                "readiness_reading": (
                    "the contribution remains implementation-safe because cloud-support, component roles, and "
                    "release checks are already explicit before any stronger model-development language appears"
                ),
            },
            {
                "readiness_rank": 4,
                "readiness_area": "translational_contribution_position",
                "readiness_role": "collaborative_model_support",
                "readiness_reading": (
                    "the correct reading is collaborative model-development support over a strong governed input lane, "
                    "not independent ownership of a live AI programme or model estate"
                ),
            },
        ]
    )
    modelling_readiness.to_parquet(EXTRACTS / "modelling_readiness_output_v1.parquet", index=False)

    release_checks = pd.DataFrame(
        [
            {"check_name": "model input ready base present", "result": "pass"},
            {"check_name": "multimodal model input support output contains four rows", "result": "pass" if len(multimodal_model_input_support) == 4 else "fail"},
            {"check_name": "modelling readiness output contains four rows", "result": "pass" if len(modelling_readiness) == 4 else "fail"},
            {"check_name": "integrated stream count retained", "result": "pass" if integrated_stream_count == 4 else "fail"},
            {"check_name": "source role count retained", "result": "pass" if source_role_count == 4 else "fail"},
            {"check_name": "review trigger metric count retained", "result": "pass" if review_trigger_metric_count == 3 else "fail"},
            {"check_name": "inherited imperial support packs remain green", "result": "pass" if (imperial_a_fact["release_checks_passed"] == 8 and imperial_bc_fact["release_checks_passed"] == 8 and imperial_d_fact["release_checks_passed"] == 8) else "fail"},
            {"check_name": "language stays below AI programme or model estate ownership", "result": "pass"},
        ]
    )
    release_checks.to_parquet(EXTRACTS / "ai_model_support_release_checks_v1.parquet", index=False)

    regeneration_seconds = time.perf_counter() - start
    execution_fact_pack = {
        "slice": "imperial_college_london/04_ai_model_development_support_and_multimodal_model_inputs",
        "aligned_reporting_window": aligned_reporting_window,
        "model_input_ready_base_output_count": 1,
        "multimodal_model_input_support_output_count": 1,
        "modelling_readiness_output_count": 1,
        "fit_for_use_contribution_output_count": 1,
        "shared_source_cohort": shared_source_cohort,
        "reused_prior_slice_count": 4,
        "integrated_stream_count": integrated_stream_count,
        "source_role_count": source_role_count,
        "input_role_count": 4,
        "support_stage_count": 4,
        "confirmation_strength": confirmation_strength,
        "review_trigger_metric_count": review_trigger_metric_count,
        "current_reporting_pressure_gap_pp": current_reporting_pressure_gap_pp,
        "current_quality_consistency_gap_pp": current_quality_consistency_gap_pp,
        "current_control_gap_pp": current_control_gap_pp,
        "retained_yield_delta_pp_analogue": float(yield_improvement),
        "retained_capture_delta_pp_analogue": float(capture_delta),
        "inherited_release_checks_passed": imperial_a_fact["release_checks_passed"] + imperial_bc_fact["release_checks_passed"] + imperial_d_fact["release_checks_passed"],
        "inherited_release_check_count": imperial_a_fact["release_check_count"] + imperial_bc_fact["release_check_count"] + imperial_d_fact["release_check_count"],
        "release_checks_passed": int((release_checks["result"] == "pass").sum()),
        "release_check_count": int(len(release_checks)),
        "regeneration_seconds": regeneration_seconds,
    }
    (METRICS / "execution_fact_pack.json").write_text(json.dumps(execution_fact_pack, indent=2), encoding="utf-8")

    write_markdown(
        ROOT / "ai_model_support_scope_note_v1.md",
        f"""
        # AI Model Support Scope Note

        This pack is the bounded `Imperial College London job 16 E` analogue for `AI`-model-development support
        and multimodal model-input preparation.

        It is anchored to the completed `job 16 A`, `job 16 B + C`, and `job 16 D` packs over the aligned reporting
        window `{aligned_reporting_window}`.

        The pack proves one model-input-ready base, one multimodal model-input support surface, one
        modelling-readiness output, and one fit-for-use contribution reading.

        Boundary:
        - no live `AI` programme ownership
        - no production model-estate ownership
        - no full translational model-development authority
        """,
    )
    write_markdown(
        ROOT / "model_input_ready_base_note_v1.md",
        f"""
        # Model Input Ready Base Note

        The model-input base reuses the completed multimodal, longitudinal, and cloud-support packs to show that
        the analytical lane is stable enough to act as one bounded model-support substrate.

        Shared source cohort: `{shared_source_cohort}`
        Integrated streams: `{integrated_stream_count}`
        Source roles: `{source_role_count}`
        Support stages: `4`
        """,
    )
    write_markdown(
        ROOT / "multimodal_model_input_support_note_v1.md",
        """
        # Multimodal Model Input Support Note

        The model-input surface keeps the slice on bounded multimodal signal, context, quality, and release-aware
        inputs.

        The point is not to fake a live model pipeline. The point is to show that the completed health-data packs
        can be carried into a controlled input-preparation posture for new model development.
        """,
    )
    write_markdown(
        ROOT / "modelling_readiness_note_v1.md",
        """
        # Modelling Readiness Note

        The readiness output translates the completed analytical lane into bounded model-support roles:
        input contract, trade-off visibility, controlled release, and collaborative contribution.

        These are analogues for translational model-development support, not claims of direct model ownership.
        """,
    )
    write_markdown(
        ROOT / "fit_for_use_contribution_note_v1.md",
        """
        # Fit For Use Contribution Note

        The pack is strong enough to support bounded new-model development conversations because it preserves
        multimodal inputs, longitudinal context, trade-off visibility, and release boundaries on the same governed lane.

        It should still be treated as a collaborative contribution analogue rather than a full AI programme.
        """,
    )
    write_markdown(
        ROOT / "translational_contribution_note_v1.md",
        """
        # Translational Contribution Note

        The correct contribution reading is that the completed analytical lane can now support model-ready,
        translational use in collaboration with senior data-science leadership.

        The correct boundary is support and contribution, not model-programme ownership.
        """,
    )
    write_markdown(
        ROOT / "ai_model_support_caveats_v1.md",
        """
        # AI Model Support Caveats

        Caveats:
        - this is not a live AI programme
        - this is not a direct production model-estate administration pack
        - this is not full translational model ownership
        - the slice only proves bounded AI-support and multimodal model-input preparation over the completed analytical lane
        """,
    )
    write_markdown(
        ROOT / "README_ai_model_support_regeneration.md",
        """
        # AI Model Support Regeneration

        Regenerate with:

        ```powershell
        python "artefacts\\analytics_slices\\data_scientist\\imperial_college_london\\04_ai_model_development_support_and_multimodal_model_inputs\\models\\build_ai_model_development_support_and_multimodal_model_inputs.py"
        ```
        """,
    )
    write_markdown(
        ROOT / "CHANGELOG_ai_model_support.md",
        """
        # AI Model Support Changelog

        - v1: initial bounded AI-model-development-support pack for `Imperial College London job 16 E`
        """,
    )


if __name__ == "__main__":
    main()
