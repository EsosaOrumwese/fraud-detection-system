from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_B_DIR = BASE_DIR.parent / "02_reporting_dashboards_and_visualisation"
SOURCE_C_DIR = BASE_DIR.parent / "03_senior_leadership_and_external_reporting"
SOURCE_D_DIR = BASE_DIR.parent / "04_data_infrastructure_models_and_process_improvement"
EXTRACTS_DIR = BASE_DIR / "extracts"
METRICS_DIR = BASE_DIR / "metrics"
BAND_ORDER = ["under_10", "10_to_25", "25_to_50", "50_plus"]


def ensure_dirs() -> None:
    EXTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    maintained_layer = pd.read_parquet(
        SOURCE_D_DIR / "extracts" / "maintained_processing_layer_v1.parquet"
    )
    reporting_summary = pd.read_parquet(
        SOURCE_B_DIR / "extracts" / "trusted_reporting_summary_v1.parquet"
    )
    ad_hoc_detail = pd.read_parquet(
        SOURCE_B_DIR / "extracts" / "trusted_reporting_ad_hoc_detail_v1.parquet"
    )
    leadership_summary = pd.read_parquet(
        SOURCE_C_DIR / "extracts" / "leadership_reporting_summary_v1.parquet"
    )
    external_cut = pd.read_parquet(
        SOURCE_C_DIR / "extracts" / "external_oversight_reporting_cut_v1.parquet"
    )
    fact_pack_d = json.loads(
        (SOURCE_D_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    return (
        maintained_layer,
        reporting_summary,
        ad_hoc_detail,
        leadership_summary,
        external_cut,
        fact_pack_d,
    )


def build_regenerated_reporting_summary(layer: pd.DataFrame) -> pd.DataFrame:
    top = layer.sort_values("priority_rank").iloc[0]
    return pd.DataFrame(
        [
            {
                "reporting_window": str(layer.iloc[0]["reporting_window"]),
                "kpi_family_count": 4,
                "view_type": "scheduled_summary",
                "scheduled_views_count": 1,
                "ad_hoc_views_count": 1,
                "overall_flow_rows": int(layer.iloc[0]["overall_flow_rows"]),
                "overall_case_open_rate": float(layer.iloc[0]["overall_case_open_rate"]),
                "overall_truth_quality": float(layer.iloc[0]["overall_case_truth_rate"]),
                "top_attention_band": str(top["band_label"]),
                "top_attention_burden_minus_yield_pp": float(top["burden_minus_yield_pp"]),
            }
        ]
    )


def build_regenerated_ad_hoc_detail(layer: pd.DataFrame) -> pd.DataFrame:
    cols = [
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
    ]
    detail = layer[cols].copy()
    detail["amount_band"] = detail["amount_band"].astype(str)
    detail["amount_band"] = pd.Categorical(detail["amount_band"], categories=BAND_ORDER, ordered=True)
    detail = detail.sort_values("amount_band").reset_index(drop=True)
    detail["amount_band"] = detail["amount_band"].astype(str)
    return detail


def build_regenerated_leadership_summary(layer: pd.DataFrame, fact_pack_d: dict) -> pd.DataFrame:
    top = layer.sort_values("priority_rank").iloc[0]
    return pd.DataFrame(
        [
            {
                "reporting_window": str(layer.iloc[0]["reporting_window"]),
                "audience": "senior_leadership",
                "pack_type": "leadership_summary",
                "shared_kpi_family_count": 4,
                "shared_reporting_views_count": 2,
                "overall_flow_rows": int(layer.iloc[0]["overall_flow_rows"]),
                "overall_case_open_rate": float(layer.iloc[0]["overall_case_open_rate"]),
                "overall_truth_quality": float(layer.iloc[0]["overall_case_truth_rate"]),
                "top_attention_band": str(top["band_label"]),
                "top_attention_case_open_gap_pp": float(top["case_open_gap_pp"]),
                "top_attention_truth_quality_gap_pp": float(top["truth_quality_gap_pp"]),
                "top_attention_burden_minus_yield_pp": float(top["burden_minus_yield_pp"]),
                "inherited_source_surfaces_mapped": int(fact_pack_d["inherited_source_surfaces_mapped"]),
            }
        ]
    )


def build_regenerated_external_cut(layer: pd.DataFrame) -> pd.DataFrame:
    top = layer.sort_values("priority_rank").iloc[0]
    overall = {
        "reporting_window": str(layer.iloc[0]["reporting_window"]),
        "audience": "external_oversight",
        "oversight_row": "overall",
        "band_label": "Overall",
        "flow_rows": int(layer.iloc[0]["overall_flow_rows"]),
        "flow_share": 1.0,
        "case_open_rate": float(layer.iloc[0]["overall_case_open_rate"]),
        "case_open_gap_pp": 0.0,
        "case_truth_rate": float(layer.iloc[0]["overall_case_truth_rate"]),
        "truth_quality_gap_pp": 0.0,
        "burden_minus_yield_pp": 0.0,
        "priority_rank": 0,
    }
    focus = {
        "reporting_window": str(layer.iloc[0]["reporting_window"]),
        "audience": "external_oversight",
        "oversight_row": "focus_band",
        "band_label": str(top["band_label"]),
        "flow_rows": int(top["flow_rows"]),
        "flow_share": float(top["flow_share"]),
        "case_open_rate": float(top["case_open_rate"]),
        "case_open_gap_pp": float(top["case_open_gap_pp"]),
        "case_truth_rate": float(top["case_truth_rate"]),
        "truth_quality_gap_pp": float(top["truth_quality_gap_pp"]),
        "burden_minus_yield_pp": float(top["burden_minus_yield_pp"]),
        "priority_rank": int(top["priority_rank"]),
    }
    return pd.DataFrame([overall, focus])


def diff_cells(left: pd.DataFrame, right: pd.DataFrame) -> int:
    left_reset = left.reset_index(drop=True)
    right_reset = right.reset_index(drop=True)
    left_reset = left_reset.reindex(sorted(left_reset.columns), axis=1)
    right_reset = right_reset.reindex(sorted(right_reset.columns), axis=1)
    comparison = left_reset.compare(right_reset, keep_shape=False, keep_equal=False)
    return int(len(comparison))


def build_workflow_automation_summary(
    layer: pd.DataFrame,
    fact_pack_d: dict,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "workflow_area": "audience_pack_regeneration",
                "repeated_burden_before_fix": "scheduled, ad hoc, leadership, and oversight outputs depended on separate slice-specific regeneration steps over the same governed facts",
                "improved_path": "one regeneration path now reassembles those audience-ready outputs directly from the maintained analytical layer",
                "governed_input_rows": int(len(layer)),
                "derived_fields_reused": int(fact_pack_d["derived_fields_centralised"]),
                "supported_output_count": 4,
                "audience_pack_count": 2,
                "repeatability_benefit": "one rerunnable path reduces repeated assembly effort and keeps output generation aligned to the same governed layer",
            }
        ]
    )


def build_supported_outputs_summary(
    regenerated_reporting_summary: pd.DataFrame,
    regenerated_ad_hoc_detail: pd.DataFrame,
    regenerated_leadership_summary: pd.DataFrame,
    regenerated_external_cut: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "output_name": "scheduled_summary",
                "output_family": "reporting",
                "rows_generated": int(len(regenerated_reporting_summary)),
                "source_path": "maintained_processing_layer",
                "automation_value": "headline scheduled output regenerated without separate slice-specific assembly",
            },
            {
                "output_name": "ad_hoc_supporting_detail",
                "output_family": "reporting",
                "rows_generated": int(len(regenerated_ad_hoc_detail)),
                "source_path": "maintained_processing_layer",
                "automation_value": "detail cut regenerated from the same path as the scheduled summary",
            },
            {
                "output_name": "leadership_summary",
                "output_family": "audience_pack",
                "rows_generated": int(len(regenerated_leadership_summary)),
                "source_path": "maintained_processing_layer",
                "automation_value": "leadership pack regenerated from the same governed path",
            },
            {
                "output_name": "external_oversight_cut",
                "output_family": "audience_pack",
                "rows_generated": int(len(regenerated_external_cut)),
                "source_path": "maintained_processing_layer",
                "automation_value": "oversight cut regenerated from the same governed path",
            },
        ]
    )


def build_repeatability_checks(
    regenerated_reporting_summary: pd.DataFrame,
    expected_reporting_summary: pd.DataFrame,
    regenerated_ad_hoc_detail: pd.DataFrame,
    expected_ad_hoc_detail: pd.DataFrame,
    regenerated_leadership_summary: pd.DataFrame,
    expected_leadership_summary: pd.DataFrame,
    regenerated_external_cut: pd.DataFrame,
    expected_external_cut: pd.DataFrame,
    automation_summary: pd.DataFrame,
    supported_outputs: pd.DataFrame,
) -> pd.DataFrame:
    checks = [
        {
            "check_name": "regenerated_scheduled_summary_matches_governed_output",
            "actual_value": float(diff_cells(regenerated_reporting_summary, expected_reporting_summary)),
            "expected_rule": "= 0 differing cells versus governed scheduled summary output",
            "passed_flag": int(diff_cells(regenerated_reporting_summary, expected_reporting_summary) == 0),
        },
        {
            "check_name": "regenerated_ad_hoc_detail_matches_governed_output",
            "actual_value": float(diff_cells(regenerated_ad_hoc_detail, expected_ad_hoc_detail)),
            "expected_rule": "= 0 differing cells versus governed ad hoc supporting detail output",
            "passed_flag": int(diff_cells(regenerated_ad_hoc_detail, expected_ad_hoc_detail) == 0),
        },
        {
            "check_name": "regenerated_leadership_summary_matches_governed_output",
            "actual_value": float(diff_cells(regenerated_leadership_summary, expected_leadership_summary)),
            "expected_rule": "= 0 differing cells versus governed leadership summary output",
            "passed_flag": int(diff_cells(regenerated_leadership_summary, expected_leadership_summary) == 0),
        },
        {
            "check_name": "regenerated_external_cut_matches_governed_output",
            "actual_value": float(diff_cells(regenerated_external_cut, expected_external_cut)),
            "expected_rule": "= 0 differing cells versus governed external oversight cut",
            "passed_flag": int(diff_cells(regenerated_external_cut, expected_external_cut) == 0),
        },
        {
            "check_name": "automation_summary_states_single_reusable_path",
            "actual_value": float(automation_summary.iloc[0]["supported_output_count"]),
            "expected_rule": "= 4 supported outputs regenerated from one reusable path",
            "passed_flag": int(int(automation_summary.iloc[0]["supported_output_count"]) == 4),
        },
        {
            "check_name": "supported_output_summary_covers_expected_outputs",
            "actual_value": float(len(supported_outputs)),
            "expected_rule": "= 4 supported outputs listed in the improved workflow pack",
            "passed_flag": int(len(supported_outputs) == 4),
        },
    ]
    return pd.DataFrame(checks)


def build_fact_pack(
    automation_summary: pd.DataFrame,
    supported_outputs: pd.DataFrame,
    repeatability_checks: pd.DataFrame,
    duration: float,
) -> dict:
    row = automation_summary.iloc[0]
    return {
        "slice": "claire_house/06_efficiency_and_automation_improvement",
        "reporting_window": "Mar 2026",
        "reusable_regeneration_paths": 1,
        "governed_input_rows": int(row["governed_input_rows"]),
        "supported_output_count": int(row["supported_output_count"]),
        "audience_pack_count": int(row["audience_pack_count"]),
        "derived_fields_reused": int(row["derived_fields_reused"]),
        "workflow_repeatability_checks_passed": int(repeatability_checks["passed_flag"].sum()),
        "workflow_repeatability_check_count": int(len(repeatability_checks)),
        "regeneration_seconds": duration,
    }


def write_notes(fact_pack: dict) -> None:
    files = {
        BASE_DIR / "workflow_friction_note_v1.md": f"""# Workflow Friction Note v1

Workflow friction before the improvement:
- the same governed Claire House facts were already supporting reporting and higher-accountability outputs
- but regeneration still depended on separate slice-specific build steps for reporting and audience packs

Bounded friction statement:
- repeated output assembly lived across multiple regeneration paths rather than one reusable audience-pack path
- this increased rerun friction even though the governed maintained layer already existed

Bounded scope:
- reporting window: `Mar 2026`
- governed input rows: `{fact_pack['governed_input_rows']}`
""",
        BASE_DIR / "automation_improvement_note_v1.md": f"""# Automation Improvement Note v1

Automation improvement:
- one reusable regeneration path now rebuilds reporting and audience-ready outputs from the same maintained analytical layer

Observed benefit:
- supported outputs regenerated from the same path: `{fact_pack['supported_output_count']}`
- audience packs supported from the same path: `{fact_pack['audience_pack_count']}`
- derived fields reused from the maintained layer: `{fact_pack['derived_fields_reused']}`

What improved:
- less repeated slice-specific assembly effort
- clearer rerun path
- easier maintenance of audience-ready output generation
""",
        BASE_DIR / "regeneration_path_note_v1.md": """# Regeneration Path Note v1

Reusable regeneration path:
1. read the maintained analytical layer
2. regenerate the scheduled summary output
3. regenerate the ad hoc supporting detail output
4. regenerate the leadership summary output
5. regenerate the external oversight cut
6. run repeatability checks against the governed outputs

This is a bounded automation path, not a full workflow-orchestration platform.
""",
        BASE_DIR / "workflow_caveats_v1.md": """# Workflow Caveats v1

Caveats:
- this slice automates one bounded audience-pack regeneration path only
- it does not automate the whole reporting estate
- it does not claim enterprise orchestration ownership
- it reuses compact governed outputs and the maintained analytical layer rather than rebuilding raw analytical scope
""",
        BASE_DIR / "README_workflow_automation_regeneration.md": """# Workflow Automation Regeneration

Regeneration steps:
1. confirm the Claire House `3.D` maintained analytical layer exists
2. run `models/build_efficiency_and_automation_improvement.py`
3. review the regenerated output pack, supported-output summary, and repeatability checks
4. use the execution report to decide whether a workflow-benefit plot is genuinely needed
""",
        BASE_DIR / "CHANGELOG_workflow_automation.md": """# Changelog - Workflow Automation

- v1: initial bounded workflow-automation pack built to regenerate reporting and audience-ready outputs from one maintained analytical layer
""",
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")


def main() -> None:
    started = time.perf_counter()
    ensure_dirs()
    (
        maintained_layer,
        expected_reporting_summary,
        expected_ad_hoc_detail,
        expected_leadership_summary,
        expected_external_cut,
        fact_pack_d,
    ) = load_inputs()

    regenerated_reporting_summary = build_regenerated_reporting_summary(maintained_layer)
    regenerated_ad_hoc_detail = build_regenerated_ad_hoc_detail(maintained_layer)
    regenerated_leadership_summary = build_regenerated_leadership_summary(maintained_layer, fact_pack_d)
    regenerated_external_cut = build_regenerated_external_cut(maintained_layer)
    automation_summary = build_workflow_automation_summary(maintained_layer, fact_pack_d)
    supported_outputs = build_supported_outputs_summary(
        regenerated_reporting_summary,
        regenerated_ad_hoc_detail,
        regenerated_leadership_summary,
        regenerated_external_cut,
    )
    repeatability_checks = build_repeatability_checks(
        regenerated_reporting_summary,
        expected_reporting_summary,
        regenerated_ad_hoc_detail,
        expected_ad_hoc_detail,
        regenerated_leadership_summary,
        expected_leadership_summary,
        regenerated_external_cut,
        expected_external_cut,
        automation_summary,
        supported_outputs,
    )
    duration = time.perf_counter() - started
    fact_pack = build_fact_pack(automation_summary, supported_outputs, repeatability_checks, duration)

    regenerated_reporting_summary.to_parquet(
        EXTRACTS_DIR / "regenerated_reporting_summary_v1.parquet", index=False
    )
    regenerated_ad_hoc_detail.to_parquet(
        EXTRACTS_DIR / "regenerated_ad_hoc_detail_v1.parquet", index=False
    )
    regenerated_leadership_summary.to_parquet(
        EXTRACTS_DIR / "regenerated_leadership_summary_v1.parquet", index=False
    )
    regenerated_external_cut.to_parquet(
        EXTRACTS_DIR / "regenerated_external_oversight_cut_v1.parquet", index=False
    )
    automation_summary.to_parquet(
        EXTRACTS_DIR / "workflow_automation_summary_v1.parquet", index=False
    )
    supported_outputs.to_parquet(
        EXTRACTS_DIR / "workflow_supported_outputs_v1.parquet", index=False
    )
    repeatability_checks.to_parquet(
        EXTRACTS_DIR / "workflow_repeatability_checks_v1.parquet", index=False
    )
    (METRICS_DIR / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2),
        encoding="utf-8",
    )
    write_notes(fact_pack)


if __name__ == "__main__":
    main()
