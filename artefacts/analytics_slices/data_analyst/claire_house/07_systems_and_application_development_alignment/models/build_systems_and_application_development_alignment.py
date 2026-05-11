from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_A_DIR = BASE_DIR.parent / "01_trusted_data_provision_and_integrity"
SOURCE_D_DIR = BASE_DIR.parent / "04_data_infrastructure_models_and_process_improvement"
SOURCE_F_DIR = BASE_DIR.parent / "06_efficiency_and_automation_improvement"
EXTRACTS_DIR = BASE_DIR / "extracts"
METRICS_DIR = BASE_DIR / "metrics"

REQUIRED_INTERFACE_FIELDS = [
    "reporting_window",
    "amount_band",
    "band_label",
    "flow_rows",
    "flow_share",
    "case_opened_rows",
    "case_opened_share",
    "case_open_rate",
    "case_open_gap_pp",
    "case_truth_rows",
    "truth_share",
    "case_truth_rate",
    "truth_quality_gap_pp",
    "burden_minus_yield_pp",
    "priority_rank",
    "overall_flow_rows",
    "overall_case_open_rate",
    "overall_case_truth_rate",
]


def ensure_dirs() -> None:
    EXTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]:
    maintained_layer = pd.read_parquet(
        SOURCE_D_DIR / "extracts" / "maintained_processing_layer_v1.parquet"
    )
    supported_outputs = pd.read_parquet(
        SOURCE_F_DIR / "extracts" / "workflow_supported_outputs_v1.parquet"
    )
    repeatability_checks = pd.read_parquet(
        SOURCE_F_DIR / "extracts" / "workflow_repeatability_checks_v1.parquet"
    )
    integrity_checks = pd.read_parquet(
        SOURCE_A_DIR / "extracts" / "trusted_data_provision_integrity_checks_v1.parquet"
    )
    fact_pack_d = json.loads(
        (SOURCE_D_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    fact_pack_f = json.loads(
        (SOURCE_F_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    return (
        maintained_layer,
        supported_outputs,
        repeatability_checks,
        integrity_checks,
        fact_pack_d,
        fact_pack_f,
    )


def build_interface_handoff_map(
    maintained_layer: pd.DataFrame,
    supported_outputs: pd.DataFrame,
    fact_pack_d: dict,
    fact_pack_f: dict,
) -> pd.DataFrame:
    focus = maintained_layer.sort_values("priority_rank").iloc[0]
    return pd.DataFrame(
        [
            {
                "boundary_name": "maintained_layer_to_regeneration_path",
                "producer_surface": "maintained_processing_layer",
                "consumer_surface": "workflow_regeneration_path",
                "producer_grain": "one row per amount band for Mar 2026 maintained analytical layer",
                "consumer_expectation": "stable band-level KPI interface for scheduled, ad hoc, leadership, and oversight regeneration",
                "required_interface_field_count": len(REQUIRED_INTERFACE_FIELDS),
                "required_interface_fields": ", ".join(REQUIRED_INTERFACE_FIELDS),
                "governed_input_rows": int(len(maintained_layer)),
                "downstream_outputs_supported": int(len(supported_outputs)),
                "audience_pack_outputs_supported": int(
                    (supported_outputs["output_family"] == "audience_pack").sum()
                ),
                "focus_band_preserved": str(focus["band_label"]),
                "alignment_value": "one explicit producer-to-consumer handoff keeps reporting and audience-ready outputs on the same governed KPI surface",
                "risk_if_boundary_drifts": "field, grain, or baseline drift would break regenerated-output equivalence and weaken downstream trust",
                "inherited_source_surfaces_mapped": int(fact_pack_d["inherited_source_surfaces_mapped"]),
                "reusable_regeneration_paths": int(fact_pack_f["reusable_regeneration_paths"]),
            }
        ]
    )


def build_integration_control_checks(
    maintained_layer: pd.DataFrame,
    supported_outputs: pd.DataFrame,
    repeatability_checks: pd.DataFrame,
    integrity_checks: pd.DataFrame,
    fact_pack_f: dict,
) -> pd.DataFrame:
    missing_fields = len([field for field in REQUIRED_INTERFACE_FIELDS if field not in maintained_layer.columns])
    null_rows = int(maintained_layer[REQUIRED_INTERFACE_FIELDS].isna().any(axis=1).sum())
    checks = [
        {
            "check_name": "interface_required_fields_present",
            "actual_value": float(missing_fields),
            "expected_rule": "= 0 required interface fields missing from maintained producer surface",
            "passed_flag": int(missing_fields == 0),
        },
        {
            "check_name": "interface_required_fields_complete_for_all_rows",
            "actual_value": float(null_rows),
            "expected_rule": "= 0 maintained-layer rows with nulls across required interface fields",
            "passed_flag": int(null_rows == 0),
        },
        {
            "check_name": "interface_producer_grain_matches_expected_band_rows",
            "actual_value": float(len(maintained_layer)),
            "expected_rule": "= 4 maintained band rows presented to the regeneration consumer",
            "passed_flag": int(len(maintained_layer) == 4),
        },
        {
            "check_name": "interface_supported_outputs_cover_expected_families",
            "actual_value": float(len(supported_outputs)),
            "expected_rule": "= 4 regenerated downstream outputs depend on the maintained producer surface",
            "passed_flag": int(len(supported_outputs) == 4),
        },
        {
            "check_name": "integration_path_repeatability_remains_exact",
            "actual_value": float(repeatability_checks["passed_flag"].sum()),
            "expected_rule": f"= {len(repeatability_checks)} repeatability checks passed on the regeneration consumer path",
            "passed_flag": int(
                int(repeatability_checks["passed_flag"].sum()) == len(repeatability_checks)
            ),
        },
        {
            "check_name": "upstream_controlled_lane_still_release_safe",
            "actual_value": float(integrity_checks["passed_flag"].sum()),
            "expected_rule": f"= {len(integrity_checks)} trusted provision integrity checks passed upstream of the interface",
            "passed_flag": int(int(integrity_checks["passed_flag"].sum()) == len(integrity_checks)),
        },
        {
            "check_name": "consumer_path_remains_single_reusable_interface",
            "actual_value": float(fact_pack_f["reusable_regeneration_paths"]),
            "expected_rule": "= 1 reusable regeneration path consumes the maintained producer surface",
            "passed_flag": int(int(fact_pack_f["reusable_regeneration_paths"]) == 1),
        },
    ]
    return pd.DataFrame(checks)


def build_supported_output_alignment_summary(
    maintained_layer: pd.DataFrame,
    supported_outputs: pd.DataFrame,
) -> pd.DataFrame:
    focus = maintained_layer.sort_values("priority_rank").iloc[0]
    overall_case_open_rate = float(maintained_layer.iloc[0]["overall_case_open_rate"])
    overall_truth_quality = float(maintained_layer.iloc[0]["overall_case_truth_rate"])
    output_rows: list[dict] = []
    for row in supported_outputs.itertuples(index=False):
        output_rows.append(
            {
                "output_name": row.output_name,
                "output_family": row.output_family,
                "interface_source": row.source_path,
                "rows_generated": int(row.rows_generated),
                "depends_on_governed_band_interface": 1,
                "depends_on_overall_baselines": int(
                    row.output_name in {"scheduled_summary", "leadership_summary", "external_oversight_cut"}
                ),
                "focus_band_transmitted": str(focus["band_label"]),
                "overall_case_open_rate_transmitted": overall_case_open_rate,
                "overall_truth_quality_transmitted": overall_truth_quality,
                "alignment_consequence_if_drifted": (
                    "output equivalence and audience-facing trust would fail if the interface grain or KPI fields drifted"
                ),
            }
        )
    return pd.DataFrame(output_rows)


def build_fact_pack(
    interface_handoff_map: pd.DataFrame,
    control_checks: pd.DataFrame,
    supported_alignment: pd.DataFrame,
    duration: float,
) -> dict:
    row = interface_handoff_map.iloc[0]
    return {
        "slice": "claire_house/07_systems_and_application_development_alignment",
        "reporting_window": "Mar 2026",
        "interface_boundaries_controlled": 1,
        "required_interface_field_count": int(row["required_interface_field_count"]),
        "governed_input_rows": int(row["governed_input_rows"]),
        "downstream_outputs_protected": int(row["downstream_outputs_supported"]),
        "audience_pack_outputs_supported": int(row["audience_pack_outputs_supported"]),
        "focus_band_preserved": str(row["focus_band_preserved"]),
        "integration_control_checks_passed": int(control_checks["passed_flag"].sum()),
        "integration_control_check_count": int(len(control_checks)),
        "supported_output_alignment_rows": int(len(supported_alignment)),
        "regeneration_seconds": duration,
    }


def write_notes(
    fact_pack: dict,
    interface_handoff_map: pd.DataFrame,
    supported_alignment: pd.DataFrame,
) -> None:
    interface_row = interface_handoff_map.iloc[0]
    output_names = ", ".join(supported_alignment["output_name"].astype(str).tolist())
    files = {
        BASE_DIR / "systems_alignment_scope_note_v1.md": """# Systems Alignment Scope Note v1

Bounded scope:
- one systems-facing handoff boundary between the maintained analytical layer and the reusable regeneration path
- the downstream regenerated reporting and audience-ready outputs depending on that boundary
- one explicit integration-control pack over the boundary

This slice does not claim application-development ownership or full systems-integration architecture.
""",
        BASE_DIR / "interface_handoff_map_v1.md": f"""# Interface Handoff Map v1

Producer:
- `{interface_row['producer_surface']}`

Consumer:
- `{interface_row['consumer_surface']}`

Boundary purpose:
- hand the governed band-level KPI surface into the reusable regeneration path without field, grain, or baseline drift

Required interface fields:
- `{int(interface_row['required_interface_field_count'])}` fields

Downstream outputs depending on the boundary:
- `{output_names}`
""",
        BASE_DIR / "alignment_risk_note_v1.md": f"""# Alignment Risk Note v1

Primary alignment risk:
- if the maintained producer surface drifts in field coverage, grain, or overall baselines, regenerated downstream outputs stop matching the governed lane

Why that matters:
- scheduled and ad hoc reporting would diverge from leadership and oversight packs
- audience-facing trust would weaken because the same governed facts would no longer flow through one stable interface

Focus band currently protected through the boundary:
- `{fact_pack['focus_band_preserved']}`
""",
        BASE_DIR / "interface_operating_note_v1.md": f"""# Interface Operating Note v1

Operating rule:
1. keep the maintained analytical layer as the explicit producer surface
2. treat the reusable regeneration path as the controlled consumer
3. check required interface fields and maintained-layer grain before relying on regenerated outputs
4. use repeatability checks to confirm downstream equivalence remains exact

Current bounded support:
- governed input rows at the boundary: `{fact_pack['governed_input_rows']}`
- downstream outputs protected: `{fact_pack['downstream_outputs_protected']}`
- audience-pack outputs protected: `{fact_pack['audience_pack_outputs_supported']}`
""",
        BASE_DIR / "systems_alignment_caveats_v1.md": """# Systems Alignment Caveats v1

Caveats:
- this slice proves one analytical interface and handoff boundary only
- it does not prove full storage design or full application-development ownership
- the systems-facing analogue here is the maintained-layer to regeneration-path boundary, not a broader integration estate
""",
        BASE_DIR / "README_systems_alignment_regeneration.md": """# Systems Alignment Regeneration

Regeneration steps:
1. confirm the Claire House `3.A`, `3.D`, and `3.F` artefacts exist
2. run `models/build_systems_and_application_development_alignment.py`
3. review the interface handoff map, integration control checks, and supported-output alignment summary
4. use the execution report to decide whether a figure is needed
""",
        BASE_DIR / "CHANGELOG_systems_alignment.md": """# Changelog - Systems Alignment

- v1: initial systems-facing interface and handoff alignment pack built from Claire House `3.A`, `3.D`, and `3.F`
""",
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")


def main() -> None:
    start = time.perf_counter()
    ensure_dirs()
    (
        maintained_layer,
        supported_outputs,
        repeatability_checks,
        integrity_checks,
        fact_pack_d,
        fact_pack_f,
    ) = load_inputs()
    interface_handoff_map = build_interface_handoff_map(
        maintained_layer, supported_outputs, fact_pack_d, fact_pack_f
    )
    control_checks = build_integration_control_checks(
        maintained_layer,
        supported_outputs,
        repeatability_checks,
        integrity_checks,
        fact_pack_f,
    )
    supported_alignment = build_supported_output_alignment_summary(
        maintained_layer, supported_outputs
    )
    fact_pack = build_fact_pack(
        interface_handoff_map,
        control_checks,
        supported_alignment,
        time.perf_counter() - start,
    )

    interface_handoff_map.to_parquet(EXTRACTS_DIR / "interface_handoff_map_v1.parquet", index=False)
    control_checks.to_parquet(EXTRACTS_DIR / "integration_control_checks_v1.parquet", index=False)
    supported_alignment.to_parquet(
        EXTRACTS_DIR / "supported_output_alignment_summary_v1.parquet", index=False
    )
    (METRICS_DIR / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2),
        encoding="utf-8",
    )
    write_notes(fact_pack, interface_handoff_map, supported_alignment)


if __name__ == "__main__":
    main()
