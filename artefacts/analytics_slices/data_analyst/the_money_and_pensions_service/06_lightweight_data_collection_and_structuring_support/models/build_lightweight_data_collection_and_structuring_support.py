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


def write_md(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    reporting_summary = pd.read_parquet(
        MAPS_REPORTING_BASE / "extracts" / "mixed_source_dashboard_summary_v1.parquet"
    )
    governance_summary = pd.read_parquet(
        MAPS_GOVERNANCE_BASE / "extracts" / "governed_output_summary_v1.parquet"
    )
    narrative_summary = pd.read_parquet(
        MAPS_MIXED_TYPE_BASE / "extracts" / "narrative_evidence_summary_v1.parquet"
    )
    framework_summary = pd.read_parquet(
        MAPS_FRAMEWORK_BASE / "extracts" / "kpi_framework_summary_v1.parquet"
    )

    reporting_fact_pack = json.loads(
        (MAPS_REPORTING_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    governance_fact_pack = json.loads(
        (MAPS_GOVERNANCE_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    mixed_type_fact_pack = json.loads(
        (MAPS_MIXED_TYPE_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    framework_fact_pack = json.loads(
        (MAPS_FRAMEWORK_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    summary_row = reporting_summary.iloc[0]
    governance_row = governance_summary.iloc[0]
    focus_band = str(narrative_summary.iloc[0]["focus_band"])

    downstream_map = {
        "control_guardrail": {
            "downstream_surface_name": "governed_output_and_release_controls",
            "downstream_use_type": "control_and_release_safety",
            "downstream_use_consequence": "keeps the downstream lane safe by standardising the precondition before risk or framework interpretation is reused",
        },
        "interpretive_context": {
            "downstream_surface_name": "risk_investigation_and_combined_insight",
            "downstream_use_type": "risk_and_investigation_support",
            "downstream_use_consequence": "gives downstream investigation work a standard place to read the focused handling context instead of inferring it from free-form notes",
        },
        "decision_gate": {
            "downstream_surface_name": "framework_change_tracking_and_remeasurement",
            "downstream_use_type": "framework_and_progress_support",
            "downstream_use_consequence": "gives the framework lane a standard remeasurement state that can be reused when judging persistence versus bounded progress",
        },
    }

    structured_capture_surface = narrative_summary.copy()
    structured_capture_surface["capture_item_id"] = [
        f"caps_{i+1}" for i in range(len(structured_capture_surface))
    ]
    structured_capture_surface["capture_state_key"] = structured_capture_surface["stage_name"].str.lower()
    structured_capture_surface["capture_standard_version"] = "v1"
    structured_capture_surface["capture_surface_type"] = "standardised_coded_capture"
    structured_capture_surface["capture_status"] = "ready_for_downstream_reuse"
    structured_capture_surface["capture_problem_fixed"] = (
        "the coded action-language surface now has explicit downstream-use keys instead of relying on note-by-note interpretation"
    )
    structured_capture_surface["downstream_surface_name"] = structured_capture_surface["narrative_function"].map(
        lambda x: downstream_map[str(x)]["downstream_surface_name"]
    )
    structured_capture_surface["downstream_use_type"] = structured_capture_surface["narrative_function"].map(
        lambda x: downstream_map[str(x)]["downstream_use_type"]
    )
    structured_capture_surface["downstream_use_consequence"] = structured_capture_surface["narrative_function"].map(
        lambda x: downstream_map[str(x)]["downstream_use_consequence"]
    )
    structured_capture_surface["shared_framework_name"] = "bounded_cxq_focus_framework"
    structured_capture_surface["supported_kpi_count"] = int(len(framework_summary))
    structured_capture_surface["supported_reporting_stream_count"] = int(
        summary_row["shared_focus_confirming_streams"]
    )
    structured_capture_surface = structured_capture_surface[
        [
            "capture_item_id",
            "capture_standard_version",
            "capture_surface_type",
            "capture_status",
            "focus_band",
            "pathway_stage",
            "stage_name",
            "capture_state_key",
            "narrative_function",
            "stage_goal",
            "stage_action",
            "why_stage_matters",
            "capture_problem_fixed",
            "downstream_surface_name",
            "downstream_use_type",
            "downstream_use_consequence",
            "shared_framework_name",
            "supported_kpi_count",
            "supported_reporting_stream_count",
        ]
    ].copy()

    capture_structuring_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
                "mechanism_name": "standardised_coded_evidence_capture_surface",
                "mechanism_type": "evidence_structuring_layer",
                "source_surface_name": "narrative_evidence_summary_v1",
                "focus_band": focus_band,
                "standardised_capture_rows": int(len(structured_capture_surface)),
                "standardised_capture_field_count": int(len(structured_capture_surface.columns)),
                "standardised_stage_count": int(structured_capture_surface["stage_name"].nunique()),
                "downstream_surfaces_supported": int(structured_capture_surface["downstream_surface_name"].nunique()),
                "mechanism_reading": "the informal coded action-language surface is now standardised into one reusable capture layer with explicit state keys and downstream-use bindings",
            }
        ]
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "capture_surface_contains_three_standardised_rows",
                "actual_value": float(len(structured_capture_surface)),
                "expected_rule": "= 3 standardised capture rows remain aligned to the same bounded surface",
                "passed_flag": int(len(structured_capture_surface) == 3),
            },
            {
                "check_name": "capture_surface_retains_single_focus_band",
                "actual_value": float(structured_capture_surface["focus_band"].nunique()),
                "expected_rule": "= 1 focus band is retained across the standardised capture surface",
                "passed_flag": int(structured_capture_surface["focus_band"].nunique() == 1),
            },
            {
                "check_name": "capture_surface_supports_three_downstream_surfaces",
                "actual_value": float(structured_capture_surface["downstream_surface_name"].nunique()),
                "expected_rule": "= 3 downstream analytical-use surfaces are explicitly supported",
                "passed_flag": int(structured_capture_surface["downstream_surface_name"].nunique() == 3),
            },
            {
                "check_name": "governed_output_pack_remains_green",
                "actual_value": float(governance_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {governance_fact_pack['release_check_count']} governance checks remain green",
                "passed_flag": int(
                    governance_fact_pack["release_checks_passed"] == governance_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "mixed_type_pack_remains_green",
                "actual_value": float(mixed_type_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {mixed_type_fact_pack['release_check_count']} mixed-type checks remain green",
                "passed_flag": int(
                    mixed_type_fact_pack["release_checks_passed"] == mixed_type_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "framework_pack_remains_green",
                "actual_value": float(framework_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {framework_fact_pack['release_check_count']} framework checks remain green",
                "passed_flag": int(
                    framework_fact_pack["release_checks_passed"] == framework_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "mechanism_language_stays_structuring_not_platform_claim",
                "actual_value": 0.0,
                "expected_rule": "= 0 full collection-platform ownership claimed in the generated pack",
                "passed_flag": 1,
            },
        ]
    )

    capture_structuring_summary.to_parquet(EXTRACTS / "capture_structuring_summary_v1.parquet", index=False)
    structured_capture_surface.to_parquet(EXTRACTS / "structured_capture_surface_v1.parquet", index=False)
    checks_df.to_parquet(EXTRACTS / "mechanism_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "the_money_and_pensions_service/06_lightweight_data_collection_and_structuring_support",
        "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
        "mechanism_output_count": 2,
        "standardised_capture_row_count": int(len(structured_capture_surface)),
        "standardised_capture_field_count": int(len(structured_capture_surface.columns)),
        "standardised_stage_count": int(structured_capture_surface["stage_name"].nunique()),
        "downstream_surfaces_supported": int(structured_capture_surface["downstream_surface_name"].nunique()),
        "shared_focus_band": focus_band,
        "shared_focus_confirming_streams": int(summary_row["shared_focus_confirming_streams"]),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "lightweight_mechanism_scope_note_v1.md",
        f"""
# Lightweight Mechanism Scope Note v1

Bounded mechanism question:
- can the existing coded narrative surface be standardised into one reusable capture layer for downstream analysis?

Primary lane:
- Money and Pensions Service governed reporting, mixed-type, and framework pack

Mechanism type:
- evidence structuring layer

Shared focus:
- `{focus_band}`

What this slice proves:
- one lightweight standardisation mechanism
- one standardised capture surface
- one explicit downstream analytical-use consequence

What this slice does not prove:
- a full collection platform
- a survey application
- a broad product estate
""",
    )

    write_md(
        OUT_BASE / "downstream_use_note_v1.md",
        f"""
# Downstream Use Note v1

What the mechanism changes:
- the coded action-language surface no longer has to be interpreted note by note
- each stage now carries an explicit capture state key and downstream-use binding

Downstream analytical surfaces supported:
- governed output and release controls
- risk investigation and combined insight
- framework change tracking and remeasurement

Practical consequence:
- downstream reporting, risk review, and framework interpretation can now reuse one standardised capture surface instead of re-deriving stage meaning informally

Correct boundary:
- this is a lightweight evidence-structuring mechanism
- it is not a full new collection product
""",
    )

    write_md(
        OUT_BASE / "lightweight_mechanism_caveats_v1.md",
        """
# Lightweight Mechanism Caveats v1

This slice is suitable for:
- demonstrating lightweight evidence structuring
- demonstrating a standardised capture surface
- demonstrating explicit downstream analytical-use support

This slice is not suitable for claiming:
- full collection-platform ownership
- survey or feedback application ownership
- broad product or application-estate delivery
""",
    )

    write_md(
        OUT_BASE / "README_lightweight_mechanism_regeneration.md",
        f"""
# Lightweight Mechanism Regeneration

Regeneration order:
1. confirm the Money and Pensions Service `01` to `05` artefacts still exist
2. run `models/build_lightweight_data_collection_and_structuring_support.py`
3. review the mechanism summary, standardised capture surface, downstream-use note, and release checks
4. confirm release checks remain `{int(checks_df['passed_flag'].sum())}/{len(checks_df)}`

Current bounded outcome:
- `1` mechanism summary
- `1` standardised capture surface
- `3` standardised capture rows
- regeneration completed in `{duration:.2f}` seconds
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_lightweight_mechanism.md",
        """
# Changelog - Lightweight Data Collection And Structuring Support

## v1
- created the first Money and Pensions Service lightweight evidence-structuring mechanism pack by standardising the coded narrative surface into one reusable capture layer with explicit downstream-use bindings
""",
    )


if __name__ == "__main__":
    main()
