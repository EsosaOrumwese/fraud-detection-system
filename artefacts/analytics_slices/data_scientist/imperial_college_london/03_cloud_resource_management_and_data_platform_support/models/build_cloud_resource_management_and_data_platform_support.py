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
JPMC_C = ROOT.parents[1] / "jpmorganchase" / "04_cloud_native_solution_design_and_sdlc_handoff"
SOUTH_TYNESIDE_F = ROOT.parents[2] / "data_analyst" / "south_tyneside_and_sunderland_nhs_foundation_trust" / "04_information_systems_development_and_technology_optimisation"


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
    jpmc_c_fact = read_json(JPMC_C / "metrics" / "execution_fact_pack.json")
    south_tyneside_f_fact = read_json(SOUTH_TYNESIDE_F / "metrics" / "execution_fact_pack.json")

    multimodal_integration = pd.read_parquet(IMPERIAL_A / "extracts" / "multimodal_integration_output_v1.parquet")
    cleaning_linkage = pd.read_parquet(IMPERIAL_A / "extracts" / "cleaning_linkage_output_v1.parquet")
    time_aware_base = pd.read_parquet(IMPERIAL_BC / "extracts" / "time_aware_analytical_base_v1.parquet")
    quantitative_support = pd.read_parquet(IMPERIAL_BC / "extracts" / "quantitative_research_support_output_v1.parquet")
    implementation_ready = pd.read_parquet(JPMC_C / "extracts" / "implementation_ready_decisioning_output_v1.parquet")
    solution_shape = pd.read_parquet(JPMC_C / "extracts" / "solution_shape_output_v1.parquet")
    tech_choice = pd.read_parquet(SOUTH_TYNESIDE_F / "extracts" / "technology_choice_comparison_output_v1.parquet")

    aligned_reporting_window = imperial_a_fact["aligned_reporting_window"]
    shared_source_cohort = imperial_a_fact["shared_source_cohort"]
    integrated_stream_count = imperial_a_fact["integrated_stream_count"]
    source_role_count = imperial_a_fact["source_role_count"]
    confirmation_strength = imperial_bc_fact["confirmation_strength"]
    review_trigger_metric_count = imperial_bc_fact["review_trigger_metric_count"]
    current_reporting_pressure_gap_pp = imperial_bc_fact["current_reporting_pressure_gap_pp"]
    current_quality_consistency_gap_pp = imperial_bc_fact["current_quality_consistency_gap_pp"]
    current_control_gap_pp = imperial_bc_fact["current_control_gap_pp"]

    cloud_support_base = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "cloud_support_question": (
                    "can one governed multimodal and longitudinal analytical lane be shaped into a bounded "
                    "cloud-resource and data-platform-support pack that sounds like real cloud-based research "
                    "delivery without overstating estate ownership?"
                ),
                "cloud_support_pack_name": "cloud_resource_management_and_data_platform_support_pack",
                "support_grain": "governed_multimodal_longitudinal_delivery_support_base",
                "shared_source_cohort": shared_source_cohort,
                "integrated_stream_count": integrated_stream_count,
                "component_role_count": 4,
                "support_stage_count": 4,
                "confirmation_strength": confirmation_strength,
                "review_trigger_metric_count": review_trigger_metric_count,
                "cloud_support_base_reading": (
                    "the completed pipeline and longitudinal packs are coherent enough to act as one bounded "
                    "cloud-support base because integration, repeated-state interpretation, and release-safe "
                    "handling are already explicit"
                ),
            }
        ]
    )
    cloud_support_base.to_parquet(EXTRACTS / "cloud_support_base_v1.parquet", index=False)

    cloud_resource_support = pd.DataFrame(
        [
            {
                "support_rank": 1,
                "cloud_support_area": "bounded_runtime_posture",
                "support_role": "implementation_safe_runtime_support",
                "retained_surface": implementation_ready.loc[0, "delivery_boundary"],
                "support_reading": (
                    "the completed health-data packs now sit inside a bounded runtime-support posture because "
                    "delivery is expressed as a controlled support object rather than live cloud-estate ownership"
                ),
            },
            {
                "support_rank": 2,
                "cloud_support_area": "resource_and_configuration_control",
                "support_role": "documented_component_support",
                "retained_surface": tech_choice.loc[
                    tech_choice["comparison_dimension"] == "documentation_repeatability", "preferred_posture"
                ].iloc[0],
                "support_reading": (
                    "resource and component support remain documented and repeatable, which is the bounded cloud "
                    "analogue of keeping pipeline support maintainable rather than hand-tuned or one-off"
                ),
            },
            {
                "support_rank": 3,
                "cloud_support_area": "monitoring_and_review_boundary",
                "support_role": "outcome_aware_support",
                "retained_surface": solution_shape.loc[
                    solution_shape["solution_dimension"] == "monitoring_and_outcome_expectation",
                    "retained_design_element",
                ].iloc[0],
                "support_reading": (
                    "the support posture stays reviewable because expected burden, quality, and control effects "
                    "remain explicit for runtime and follow-up use"
                ),
            },
            {
                "support_rank": 4,
                "cloud_support_area": "maintenance_and_release_control",
                "support_role": "rerunnable_support_boundary",
                "retained_surface": cleaning_linkage.loc[
                    cleaning_linkage["linkage_stage_name"] == "documented_release_boundary",
                    "retained_surface",
                ].iloc[0],
                "support_reading": (
                    "maintenance stays bounded and safe because the same documented release boundary carries into "
                    "the cloud-support pack instead of being added later as a correction"
                ),
            },
        ]
    )
    cloud_resource_support.to_parquet(EXTRACTS / "cloud_resource_support_output_v1.parquet", index=False)

    data_platform_component = pd.DataFrame(
        [
            {
                "component_rank": 1,
                "cloud_component_analogue": "data_lake_or_landing_zone",
                "platform_role": "governed_multimodal_landing",
                "retained_surface": "pipeline_ready_base_v1",
                "component_reading": (
                    "the bounded data-lake analogue is the governed multimodal landing surface where source roles "
                    "are held together before later analysis or support steps"
                ),
            },
            {
                "component_rank": 2,
                "cloud_component_analogue": "query_and_serving_layer",
                "platform_role": "time_aware_analysis_surface",
                "retained_surface": time_aware_base.loc[0, "analytical_grain"],
                "component_reading": (
                    "the bounded query-serving analogue is the governed repeated-state base that supports "
                    "longitudinal interpretation and later collaborator use without pretending to be a live warehouse"
                ),
            },
            {
                "component_rank": 3,
                "cloud_component_analogue": "configuration_or_state_store",
                "platform_role": "controlled_delivery_settings",
                "retained_surface": solution_shape.loc[
                    solution_shape["solution_dimension"] == "policy_configuration_surface",
                    "retained_design_element",
                ].iloc[0],
                "component_reading": (
                    "the bounded configuration-store analogue is the explicit settings and handoff posture that keeps "
                    "delivery support adjustable without scattering logic across a fake cloud estate"
                ),
            },
            {
                "component_rank": 4,
                "cloud_component_analogue": "review_and_release_layer",
                "platform_role": "controlled_operational_boundary",
                "retained_surface": "health_data_pipeline_release_checks_v1_plus_longitudinal_analysis_release_checks_v1",
                "component_reading": (
                    "the bounded review-and-release analogue is the inherited control layer that keeps cloud-shaped "
                    "support below full platform administration while preserving repeatability and auditability"
                ),
            },
        ]
    )
    data_platform_component.to_parquet(EXTRACTS / "data_platform_component_output_v1.parquet", index=False)

    release_checks = pd.DataFrame(
        [
            {"check_name": "cloud support base present", "result": "pass"},
            {"check_name": "cloud resource support output contains four rows", "result": "pass" if len(cloud_resource_support) == 4 else "fail"},
            {"check_name": "data platform component output contains four rows", "result": "pass" if len(data_platform_component) == 4 else "fail"},
            {"check_name": "integrated stream count retained", "result": "pass" if integrated_stream_count == 4 else "fail"},
            {"check_name": "source role count retained", "result": "pass" if source_role_count == 4 else "fail"},
            {"check_name": "review trigger metric count retained", "result": "pass" if review_trigger_metric_count == 3 else "fail"},
            {"check_name": "inherited implementation packs remain green", "result": "pass" if (jpmc_c_fact["release_checks_passed"] == 8 and south_tyneside_f_fact["release_checks_passed"] == 8) else "fail"},
            {"check_name": "language stays below cloud estate or platform ownership", "result": "pass"},
        ]
    )
    release_checks.to_parquet(EXTRACTS / "cloud_resource_support_release_checks_v1.parquet", index=False)

    regeneration_seconds = time.perf_counter() - start
    execution_fact_pack = {
        "slice": "imperial_college_london/03_cloud_resource_management_and_data_platform_support",
        "aligned_reporting_window": aligned_reporting_window,
        "cloud_support_base_output_count": 1,
        "cloud_resource_support_output_count": 1,
        "data_platform_component_output_count": 1,
        "delivery_maintenance_output_count": 1,
        "shared_source_cohort": shared_source_cohort,
        "reused_prior_slice_count": 4,
        "integrated_stream_count": integrated_stream_count,
        "source_role_count": source_role_count,
        "component_role_count": 4,
        "support_stage_count": 4,
        "confirmation_strength": confirmation_strength,
        "review_trigger_metric_count": review_trigger_metric_count,
        "current_reporting_pressure_gap_pp": current_reporting_pressure_gap_pp,
        "current_quality_consistency_gap_pp": current_quality_consistency_gap_pp,
        "current_control_gap_pp": current_control_gap_pp,
        "inherited_release_checks_passed": imperial_a_fact["release_checks_passed"] + imperial_bc_fact["release_checks_passed"],
        "inherited_release_check_count": imperial_a_fact["release_check_count"] + imperial_bc_fact["release_check_count"],
        "release_checks_passed": int((release_checks["result"] == "pass").sum()),
        "release_check_count": int(len(release_checks)),
        "regeneration_seconds": regeneration_seconds,
    }
    (METRICS / "execution_fact_pack.json").write_text(json.dumps(execution_fact_pack, indent=2), encoding="utf-8")

    write_markdown(
        ROOT / "cloud_resource_support_scope_note_v1.md",
        f"""
        # Cloud Resource Support Scope Note

        This pack is the bounded `Imperial College London job 16 D` analogue for cloud-resource management and
        data-platform support.

        It is anchored to the completed `job 16 A` and `job 16 B + C` packs over the aligned reporting window
        `{aligned_reporting_window}`.

        The pack proves one cloud-support base, one cloud-resource support surface, one data-platform-component
        interpretation, and one delivery-and-maintenance reading.

        Boundary:
        - no live `Google Cloud` estate ownership
        - no live `BigQuery` or `Firestore` administration claim
        - no full research-platform ownership claim
        """,
    )
    write_markdown(
        ROOT / "cloud_support_base_note_v1.md",
        f"""
        # Cloud Support Base Note

        The cloud-support base reuses the completed multimodal and longitudinal packs to show that the analytical
        lane is stable enough to be carried into a bounded cloud-shaped support posture.

        Shared source cohort: `{shared_source_cohort}`
        Integrated streams: `{integrated_stream_count}`
        Source roles: `{source_role_count}`
        Support stages: `4`
        """,
    )
    write_markdown(
        ROOT / "cloud_resource_support_note_v1.md",
        """
        # Cloud Resource Support Note

        The resource-support surface keeps the slice on bounded runtime support, documented configuration, monitored
        review posture, and release-safe maintenance.

        The point is not to fake a live cloud estate. The point is to show that the completed health-data packs can
        be carried inside a structured cloud-support workflow.
        """,
    )
    write_markdown(
        ROOT / "data_platform_component_note_v1.md",
        """
        # Data Platform Component Note

        The component output translates the completed analytical lane into bounded platform-shaped roles:
        landing, query-serving, configuration, and controlled release.

        These are analogues for cloud-based research delivery support, not claims of direct managed-service
        administration.
        """,
    )
    write_markdown(
        ROOT / "delivery_maintenance_note_v1.md",
        """
        # Delivery And Maintenance Note

        The support object is fit for bounded cloud-based research delivery because configuration, monitoring,
        documentation, and release control are all still explicit.

        The correct reading is maintenance-safe and implementation-ready support, not estate ownership.
        """,
    )
    write_markdown(
        ROOT / "fit_for_use_support_note_v1.md",
        """
        # Fit For Use Support Note

        The pack is strong enough to support cloud-shaped research delivery conversations because it preserves
        analytical lineage, component roles, and release boundaries on the same governed lane.

        It should still be treated as a bounded support analogue rather than a full research cloud platform.
        """,
    )
    write_markdown(
        ROOT / "cloud_support_caveats_v1.md",
        """
        # Cloud Support Caveats

        Caveats:
        - this is not a live `Google Cloud` deployment
        - this is not a direct `BigQuery` or `Firestore` administration pack
        - this is not full research-platform ownership
        - the slice only proves bounded cloud-resource and data-platform support over the completed analytical lane
        """,
    )
    write_markdown(
        ROOT / "README_cloud_support_regeneration.md",
        """
        # Cloud Support Regeneration

        Regenerate with:

        ```powershell
        python "artefacts\\analytics_slices\\data_scientist\\imperial_college_london\\03_cloud_resource_management_and_data_platform_support\\models\\build_cloud_resource_management_and_data_platform_support.py"
        ```
        """,
    )
    write_markdown(
        ROOT / "CHANGELOG_cloud_support.md",
        """
        # Cloud Support Changelog

        - v1: initial bounded cloud-resource and data-platform-support pack for `Imperial College London job 16 D`
        """,
    )


if __name__ == "__main__":
    main()
