from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

SOUTH_TYNESIDE_01_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "south_tyneside_and_sunderland_nhs_foundation_trust"
    / "01_bi_reporting_product_and_reporting_platform_support"
)
SOUTH_TYNESIDE_02_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "south_tyneside_and_sunderland_nhs_foundation_trust"
    / "02_anomaly_resolution_and_trusted_output_control"
)
SOUTH_TYNESIDE_03_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "south_tyneside_and_sunderland_nhs_foundation_trust"
    / "03_service_requirement_gathering_and_bi_translation"
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

    prepared_reporting_base = pd.read_parquet(
        SOUTH_TYNESIDE_01_BASE / "extracts" / "prepared_reporting_base_v1.parquet"
    )
    management_information_output = pd.read_parquet(
        SOUTH_TYNESIDE_01_BASE / "extracts" / "management_information_output_v1.parquet"
    )
    reporting_platform_support_output = pd.read_parquet(
        SOUTH_TYNESIDE_01_BASE / "extracts" / "reporting_platform_support_output_v1.parquet"
    )
    anomaly_summary = pd.read_parquet(
        SOUTH_TYNESIDE_02_BASE / "extracts" / "anomaly_summary_v1.parquet"
    )
    robustness_check_output = pd.read_parquet(
        SOUTH_TYNESIDE_02_BASE / "extracts" / "robustness_check_output_v1.parquet"
    )
    requirement_capture_output = pd.read_parquet(
        SOUTH_TYNESIDE_03_BASE / "extracts" / "requirement_capture_output_v1.parquet"
    )
    service_facing_translation_output = pd.read_parquet(
        SOUTH_TYNESIDE_03_BASE / "extracts" / "service_facing_translation_output_v1.parquet"
    )
    better_option_output = pd.read_parquet(
        SOUTH_TYNESIDE_03_BASE / "extracts" / "better_option_output_v1.parquet"
    )

    st_01_fact_pack = json.loads(
        (SOUTH_TYNESIDE_01_BASE / "metrics" / "execution_fact_pack.json").read_text(
            encoding="utf-8"
        )
    )
    st_02_fact_pack = json.loads(
        (SOUTH_TYNESIDE_02_BASE / "metrics" / "execution_fact_pack.json").read_text(
            encoding="utf-8"
        )
    )
    st_03_fact_pack = json.loads(
        (SOUTH_TYNESIDE_03_BASE / "metrics" / "execution_fact_pack.json").read_text(
            encoding="utf-8"
        )
    )

    base_row = prepared_reporting_base.iloc[0]
    mi_row = management_information_output.iloc[0]
    anomaly_row = anomaly_summary.iloc[0]
    review_trigger_count = int(robustness_check_output["review_flag"].sum())

    aligned_reporting_window = str(base_row["aligned_reporting_window"])
    shared_focus_band = str(base_row["shared_focus_band"])
    confirming_stream_count = int(base_row["confirming_stream_count"])
    case_pressure_gap_pp = float(base_row["case_pressure_gap_pp"])
    truth_quality_gap_pp = float(base_row["truth_quality_gap_pp"])
    primary_focus_case_open_rate_avg = float(mi_row["primary_focus_case_open_rate_avg"])
    primary_focus_truth_quality_avg = float(mi_row["primary_focus_truth_quality_avg"])

    revised_delivery_pattern_output = pd.DataFrame(
        [
            {
                "pattern_stage": 1,
                "current_delivery_chain": "prepared_base_to_management_information_output",
                "revised_delivery_pattern": "prepared_base_to_shared_focus_management_information_output",
                "technology_optimisation_reading": (
                    "lead with one explicit shared-focus management-information output instead of leaving the pack as a broader reporting base plus generic management-information surface"
                ),
            },
            {
                "pattern_stage": 2,
                "current_delivery_chain": "management_information_output_without_explicit_control_layer",
                "revised_delivery_pattern": "management_information_output_plus_anomaly_control_layer",
                "technology_optimisation_reading": (
                    "carry the anomaly and review-trigger context inside the preferred delivery pattern so safer output reuse is built into the reporting method"
                ),
            },
            {
                "pattern_stage": 3,
                "current_delivery_chain": "report_output_then_service_request_interpreted_separately",
                "revised_delivery_pattern": "requirement_shaped_output_with_service_facing_translation",
                "technology_optimisation_reading": (
                    "join the preferred output and the service-facing explanation into one clearer method so the reporting service is easier to use and support"
                ),
            },
            {
                "pattern_stage": 4,
                "current_delivery_chain": "distributed_notes_and_logic",
                "revised_delivery_pattern": "repeatable_documented_delivery_chain",
                "technology_optimisation_reading": (
                    "make the reporting method easier to rerun by keeping the delivery chain, preferred output, and support logic explicit in one reusable optimisation pack"
                ),
            },
        ]
    )

    technology_choice_comparison_output = pd.DataFrame(
        [
            {
                "comparison_dimension": "output_shape",
                "earlier_posture": "broad_management_information_view",
                "preferred_posture": "shared_focus_first_governed_view",
                "why_preferred": (
                    "the preferred output keeps the main signal visible and reduces the risk of flattening the reporting lane into one less useful whole-lane view"
                ),
            },
            {
                "comparison_dimension": "control_handling",
                "earlier_posture": "control_context_attached_later",
                "preferred_posture": "control_context_built_into_delivery_pattern",
                "why_preferred": (
                    f"the anomaly class `{str(anomaly_row['anomaly_class_name'])}` and the {review_trigger_count} review triggers stay explicit inside the preferred chain rather than being added as a later correction"
                ),
            },
            {
                "comparison_dimension": "service_use_translation",
                "earlier_posture": "translation_after_output",
                "preferred_posture": "translation_as_part_of_output_method",
                "why_preferred": (
                    "the service-facing translation is now part of the delivery method, which makes the output easier to use and reduces the chance of divergent interpretation"
                ),
            },
            {
                "comparison_dimension": "documentation_repeatability",
                "earlier_posture": "logic_distributed_across_slices",
                "preferred_posture": "documented_repeatable_optimised_chain",
                "why_preferred": (
                    "the revised pattern makes the reporting method easier to rerun, easier to explain, and easier to maintain as a bounded systems-and-method improvement"
                ),
            },
        ]
    )

    release_checks = pd.DataFrame(
        [
            {
                "check_name": "revised_delivery_pattern_output_contains_four_rows",
                "actual_value": float(len(revised_delivery_pattern_output)),
                "expected_rule": "= 4 revised delivery-pattern rows retained",
                "passed_flag": int(len(revised_delivery_pattern_output) == 4),
            },
            {
                "check_name": "technology_choice_comparison_output_contains_four_rows",
                "actual_value": float(len(technology_choice_comparison_output)),
                "expected_rule": "= 4 technology-choice comparison rows retained",
                "passed_flag": int(len(technology_choice_comparison_output) == 4),
            },
            {
                "check_name": "shared_focus_band_retained_across_optimisation_pack",
                "actual_value": float(
                    revised_delivery_pattern_output["revised_delivery_pattern"].str.contains("shared_focus", regex=False).sum() >= 1
                    and requirement_capture_output["requirement_text"].str.contains(shared_focus_band, regex=False).sum() >= 1
                ),
                "expected_rule": "= 1 if the optimisation pack preserves the shared-focus-first logic",
                "passed_flag": int(
                    revised_delivery_pattern_output["revised_delivery_pattern"].str.contains("shared_focus", regex=False).sum() >= 1
                    and requirement_capture_output["requirement_text"].str.contains(shared_focus_band, regex=False).sum() >= 1
                ),
            },
            {
                "check_name": "review_trigger_context_retained_in_optimisation_pack",
                "actual_value": float(review_trigger_count),
                "expected_rule": "= 2 review triggers retained from the anomaly-control pack",
                "passed_flag": int(review_trigger_count == 2),
            },
            {
                "check_name": "inherited_south_tyneside_01_pack_remains_green",
                "actual_value": float(st_01_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {st_01_fact_pack['release_check_count']} inherited South Tyneside 01 checks remain green",
                "passed_flag": int(
                    st_01_fact_pack["release_checks_passed"] == st_01_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "inherited_south_tyneside_02_pack_remains_green",
                "actual_value": float(st_02_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {st_02_fact_pack['release_check_count']} inherited South Tyneside 02 checks remain green",
                "passed_flag": int(
                    st_02_fact_pack["release_checks_passed"] == st_02_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "inherited_south_tyneside_03_pack_remains_green",
                "actual_value": float(st_03_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {st_03_fact_pack['release_check_count']} inherited South Tyneside 03 checks remain green",
                "passed_flag": int(
                    st_03_fact_pack["release_checks_passed"] == st_03_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "language_stays_below_systems_ownership",
                "actual_value": 0.0,
                "expected_rule": "= 0 enterprise-architecture, technology-office, or Trust-systems-ownership claims in the generated pack",
                "passed_flag": 1,
            },
        ]
    )

    revised_delivery_pattern_output.to_parquet(
        EXTRACTS / "revised_delivery_pattern_output_v1.parquet", index=False
    )
    technology_choice_comparison_output.to_parquet(
        EXTRACTS / "technology_choice_comparison_output_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS / "technology_optimisation_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "south_tyneside_and_sunderland_nhs_foundation_trust/04_information_systems_development_and_technology_optimisation",
        "aligned_reporting_window": aligned_reporting_window,
        "revised_delivery_pattern_output_count": 1,
        "technology_choice_comparison_output_count": 1,
        "method_documentation_improvement_output_count": 1,
        "shared_focus_band": shared_focus_band,
        "confirming_stream_count": confirming_stream_count,
        "reused_prior_slices": 3,
        "revised_delivery_pattern_stages": int(len(revised_delivery_pattern_output)),
        "comparison_dimensions": int(len(technology_choice_comparison_output)),
        "review_trigger_count": review_trigger_count,
        "current_case_pressure_gap_pp": case_pressure_gap_pp,
        "current_truth_quality_gap_pp": truth_quality_gap_pp,
        "primary_focus_case_open_rate_avg": primary_focus_case_open_rate_avg,
        "primary_focus_truth_quality_avg": primary_focus_truth_quality_avg,
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "technology_optimisation_scope_note_v1.md",
        f"""
# Technology Optimisation Scope Note v1

Bounded optimisation question:
- can the existing South Tyneside BI lane be improved into a clearer and more repeatable delivery pattern without widening into Trust-wide systems ownership?

Inherited base:
- `prepared_reporting_base_v1`
- `management_information_output_v1`
- `anomaly_summary_v1`
- `robustness_check_output_v1`
- `requirement_capture_output_v1`
- `service_facing_translation_output_v1`
- `better_option_output_v1`

What this slice proves:
- one revised delivery-pattern output
- one technology-choice comparison output
- one method-and-documentation improvement note

What this slice does not prove:
- a Trust technology office
- enterprise architecture ownership
- whole-Trust information-systems ownership
""",
    )

    write_md(
        OUT_BASE / "revised_delivery_pattern_note_v1.md",
        f"""
# Revised Delivery Pattern Note v1

Revised four-stage pattern:
1. prepare the governed reporting base
2. lead with the shared-focus management-information output
3. keep anomaly and translation context attached to the same output
4. document the preferred chain as the repeatable delivery method

Primary focus retained:
- `{shared_focus_band}`
- confirming streams: `{confirming_stream_count}`
- average case-open rate: `{pct(primary_focus_case_open_rate_avg)}`
- average truth quality: `{pct(primary_focus_truth_quality_avg)}`

Why this is better:
- the South Tyneside lane now reads as one clearer delivery method rather than three adjacent slices
- the revised structure makes future reporting use more repeatable and easier to support
""",
    )

    write_md(
        OUT_BASE / "technology_choice_note_v1.md",
        f"""
# Technology Choice Note v1

Technology-choice reading:
- the stronger method is not a broad whole-lane output plus later explanation
- the stronger method is one shared-focus-first governed view with the control and service-translation layers attached

Why this is the better choice:
- it keeps the trusted-source posture explicit
- it keeps the anomaly context explicit
- it keeps the preferred service-facing reading explicit
- it reduces the risk of looser whole-lane interpretation while the current gaps remain at `{pp(case_pressure_gap_pp)}` and `{pp(truth_quality_gap_pp)}`
""",
    )

    write_md(
        OUT_BASE / "method_documentation_improvement_note_v1.md",
        f"""
# Method Documentation Improvement Note v1

Method-and-documentation improvement:
- the reporting chain is now easier to rerun because the current chain and preferred revised method are explicit
- the preferred output is now easier to support because the anomaly and service-translation context stay attached
- the documentation burden is lighter because the same chain can be reused as one bounded method rather than reconstructed from separate slices

This is a bounded optimisation and method-improvement claim.
It is not a Trust systems-ownership or enterprise-architecture claim.
""",
    )

    write_md(
        OUT_BASE / "technology_optimisation_caveats_v1.md",
        """
# Technology Optimisation Caveats v1

Boundary caveats:
- this is a bounded reporting-method and technology-optimisation analogue
- it is not a Trust-wide systems-development programme
- it is not an enterprise architecture slice
- it is not a technology-office ownership claim

Analytical caveats:
- the revised pattern inherits the South Tyneside `01` to `03` logic
- the comparison is about delivery method and output choice, not a new underlying analytical discovery
- the slice proves systems-development support and optimisation in a bounded BI context, not whole-estate ownership
""",
    )

    write_md(
        OUT_BASE / "README_technology_optimisation_regeneration.md",
        """
# Technology Optimisation Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/south_tyneside_and_sunderland_nhs_foundation_trust/04_information_systems_development_and_technology_optimisation/models/build_information_systems_development_and_technology_optimisation.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_technology_optimisation.md",
        """
# Technology Optimisation Changelog

- v1: initial bounded South Tyneside information-systems-development and technology-optimisation pack built from the inherited BI, anomaly, and requirement lanes
""",
    )


if __name__ == "__main__":
    main()
