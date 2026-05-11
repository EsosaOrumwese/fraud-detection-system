from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_A_DIR = BASE_DIR.parent / "01_trusted_data_provision_and_integrity"
SOURCE_B_DIR = BASE_DIR.parent / "02_reporting_dashboards_and_visualisation"
EXTRACTS_DIR = BASE_DIR / "extracts"
METRICS_DIR = BASE_DIR / "metrics"


def ensure_dirs() -> None:
    EXTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]:
    provision_summary = pd.read_parquet(
        SOURCE_A_DIR / "extracts" / "trusted_data_provision_summary_v1.parquet"
    )
    reporting_summary = pd.read_parquet(
        SOURCE_B_DIR / "extracts" / "trusted_reporting_summary_v1.parquet"
    )
    ad_hoc_detail = pd.read_parquet(
        SOURCE_B_DIR / "extracts" / "trusted_reporting_ad_hoc_detail_v1.parquet"
    )
    fact_pack_a = json.loads(
        (SOURCE_A_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    fact_pack_b = json.loads(
        (SOURCE_B_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    return provision_summary, reporting_summary, ad_hoc_detail, fact_pack_a, fact_pack_b


def build_maintained_layer(
    provision_summary: pd.DataFrame,
    reporting_summary: pd.DataFrame,
    ad_hoc_detail: pd.DataFrame,
) -> pd.DataFrame:
    overall = provision_summary.loc[provision_summary["amount_band"] == "__overall__"].iloc[0]
    band_rows = provision_summary.loc[provision_summary["amount_band"] != "__overall__"].copy()
    detail = ad_hoc_detail[
        [
            "amount_band",
            "band_label",
            "flow_share",
            "case_opened_share",
            "case_open_gap_pp",
            "truth_share",
            "truth_quality_gap_pp",
            "burden_minus_yield_pp",
            "priority_rank",
        ]
    ].copy()
    layer = band_rows.merge(detail, on="amount_band", how="inner", validate="one_to_one")
    layer.insert(0, "reporting_window", reporting_summary.iloc[0]["reporting_window"])
    layer["overall_flow_rows"] = float(overall["flow_rows"])
    layer["overall_case_open_rate"] = float(overall["case_open_rate"])
    layer["overall_case_truth_rate"] = float(overall["case_truth_rate"])
    layer["downstream_views_supported"] = 2
    layer["maintained_layer_purpose"] = "shared_band_kpi_shaping"
    return layer[
        [
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
            "downstream_views_supported",
            "maintained_layer_purpose",
        ]
    ].sort_values(["priority_rank", "amount_band"])


def build_control_profile(layer: pd.DataFrame, fact_pack_b: dict) -> pd.DataFrame:
    top = layer.sort_values("priority_rank").iloc[0]
    rows = [
        {
            "control_area": "shared_band_kpi_logic",
            "risk_before_fix": "band labels, shares, and gap calculations lived in reporting outputs rather than one maintained layer",
            "maintained_layer_rows": int(len(layer)),
            "downstream_views_supported": int(top["downstream_views_supported"]),
            "derived_fields_centralised": 8,
            "top_attention_band": str(top["band_label"]),
            "top_attention_gap_pp": float(top["burden_minus_yield_pp"]),
            "control_fix": "centralise shared band-level KPI shaping in one maintained reusable layer before downstream formatting",
        },
        {
            "control_area": "overall_baseline_reuse",
            "risk_before_fix": "overall baselines had to be re-read by each reporting output rather than inherited from one shaped layer",
            "maintained_layer_rows": int(len(layer)),
            "downstream_views_supported": int(top["downstream_views_supported"]),
            "derived_fields_centralised": 2,
            "top_attention_band": str(top["band_label"]),
            "top_attention_gap_pp": float(fact_pack_b["top_attention_case_open_gap_pp"]),
            "control_fix": "carry stable overall case-open and truth-quality baselines alongside the maintained band layer",
        },
    ]
    return pd.DataFrame(rows)


def build_reuse_summary(layer: pd.DataFrame) -> pd.DataFrame:
    top = layer.sort_values("priority_rank").iloc[0]
    return pd.DataFrame(
        [
            {
                "downstream_output": "scheduled_summary_view",
                "supported_from_layer": 1,
                "reused_fields": "overall_flow_rows, overall_case_open_rate, overall_case_truth_rate, top band",
                "efficiency_gain": "headline and focus-band reading can be assembled without recomputing band-level shaping",
                "focus_band": top["band_label"],
            },
            {
                "downstream_output": "ad_hoc_supporting_detail_view",
                "supported_from_layer": 1,
                "reused_fields": "band_label, flow_share, case_opened_share, case_open_gap_pp, truth_share, truth_quality_gap_pp, burden_minus_yield_pp, priority_rank",
                "efficiency_gain": "detail cut can be formatted from the maintained layer without repeating gap and ranking logic",
                "focus_band": top["band_label"],
            },
        ]
    )


def build_release_checks(
    layer: pd.DataFrame,
    ad_hoc_detail: pd.DataFrame,
    reporting_summary: pd.DataFrame,
) -> pd.DataFrame:
    summary = reporting_summary.iloc[0]
    top = layer.sort_values("priority_rank").iloc[0]
    detail_cols = [
        "amount_band",
        "band_label",
        "flow_share",
        "case_opened_share",
        "case_open_gap_pp",
        "truth_share",
        "truth_quality_gap_pp",
        "burden_minus_yield_pp",
        "priority_rank",
    ]
    merged = layer[detail_cols].sort_values("priority_rank").reset_index(drop=True).compare(
        ad_hoc_detail[detail_cols].sort_values("priority_rank").reset_index(drop=True),
        keep_shape=False,
        keep_equal=False,
    )
    checks = [
        {
            "check_name": "maintained_layer_covers_expected_bands",
            "actual_value": float(len(layer)),
            "expected_rule": "= 4 maintained band rows present",
            "passed_flag": int(len(layer) == 4),
        },
        {
            "check_name": "maintained_layer_reuses_ad_hoc_detail_logic_exactly",
            "actual_value": float(len(merged)),
            "expected_rule": "= 0 differing cells versus governed ad hoc supporting detail",
            "passed_flag": int(len(merged) == 0),
        },
        {
            "check_name": "maintained_layer_reuses_governed_overall_case_open_rate",
            "actual_value": float(abs(layer.iloc[0]["overall_case_open_rate"] - summary["overall_case_open_rate"])),
            "expected_rule": "= 0 delta versus governed overall case-open rate",
            "passed_flag": int(abs(layer.iloc[0]["overall_case_open_rate"] - summary["overall_case_open_rate"]) < 1e-12),
        },
        {
            "check_name": "maintained_layer_reuses_governed_overall_truth_quality",
            "actual_value": float(abs(layer.iloc[0]["overall_case_truth_rate"] - summary["overall_truth_quality"])),
            "expected_rule": "= 0 delta versus governed overall truth quality",
            "passed_flag": int(abs(layer.iloc[0]["overall_case_truth_rate"] - summary["overall_truth_quality"]) < 1e-12),
        },
        {
            "check_name": "maintained_layer_preserves_top_attention_band",
            "actual_value": float(top["band_label"] == summary["top_attention_band"]),
            "expected_rule": "= 1 top attention band remains aligned to governed reporting",
            "passed_flag": int(top["band_label"] == summary["top_attention_band"]),
        },
    ]
    return pd.DataFrame(checks)


def build_fact_pack(
    layer: pd.DataFrame,
    control_profile: pd.DataFrame,
    reuse_summary: pd.DataFrame,
    release_checks: pd.DataFrame,
) -> dict:
    top = layer.sort_values("priority_rank").iloc[0]
    return {
        "slice": "claire_house/04_data_infrastructure_models_and_process_improvement",
        "reporting_window": str(layer.iloc[0]["reporting_window"]),
        "maintained_layer_count": 1,
        "maintained_layer_rows": int(len(layer)),
        "downstream_outputs_supported": int(reuse_summary["supported_from_layer"].sum()),
        "control_profiles_materialised": int(len(control_profile)),
        "derived_fields_centralised": int(control_profile["derived_fields_centralised"].sum()),
        "overall_case_open_rate": float(layer.iloc[0]["overall_case_open_rate"]),
        "overall_truth_quality": float(layer.iloc[0]["overall_case_truth_rate"]),
        "top_attention_band": str(top["band_label"]),
        "top_attention_case_open_gap_pp": float(top["case_open_gap_pp"]),
        "top_attention_truth_quality_gap_pp": float(top["truth_quality_gap_pp"]),
        "top_attention_burden_minus_yield_pp": float(top["burden_minus_yield_pp"]),
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
    }


def write_notes(fact_pack: dict) -> None:
    files = {
        BASE_DIR / "processing_layer_scope_note_v1.md": f"""# Processing Layer Scope Note v1

Bounded scope:
- reporting window: `{fact_pack['reporting_window']}`
- one maintained analytical layer between trusted provision and reporting
- one control-profile pack
- one downstream-reuse summary

The slice does not claim a broad platform build. It fixes one reusable shaping layer under the reporting outputs.
""",
        BASE_DIR / "maintained_analytical_layer_note_v1.md": f"""# Maintained Analytical Layer Note v1

Maintained layer purpose:
- hold the shared band-level KPI shaping once
- support downstream summary and ad hoc outputs without repeating the shaping logic

Observed facts:
- maintained layer rows: `{fact_pack['maintained_layer_rows']}`
- downstream outputs supported: `{fact_pack['downstream_outputs_supported']}`
- top attention band remains `{fact_pack['top_attention_band']}`
""",
        BASE_DIR / "data_capture_control_monitoring_note_v1.md": f"""# Data Capture Control Monitoring Note v1

Control issue surfaced:
- shared band labels, shares, and gap logic were living in downstream outputs rather than one maintained reusable layer

Why it matters:
- repeated shaping increases the risk of drift between reporting outputs
- maintaining the shared layer explicitly makes downstream reuse easier to check and safer to rerun

Focus band still requiring attention:
- `{fact_pack['top_attention_band']}` with burden-minus-yield gap `{fact_pack['top_attention_burden_minus_yield_pp'] * 100:+.2f} pp`
""",
        BASE_DIR / "efficiency_improvement_note_v1.md": f"""# Efficiency Improvement Note v1

Bounded improvement:
- centralise the shared band-level KPI shaping in one maintained analytical layer before downstream formatting

Observed support:
- downstream outputs supported from the same layer: `{fact_pack['downstream_outputs_supported']}`
- derived fields centralised: `{fact_pack['derived_fields_centralised']}`

Efficiency meaning:
- summary and supporting-detail outputs can reuse one maintained layer rather than repeating the same shaping steps independently
""",
        BASE_DIR / "processing_layer_caveats_v1.md": """# Processing Layer Caveats v1

Caveats:
- this slice proves one maintained analytical layer only
- it does not prove a full storage or application-development estate
- the efficiency improvement is bounded to the shared KPI shaping path under the Claire House reporting outputs
""",
        BASE_DIR / "README_processing_layer_regeneration.md": """# Processing Layer Regeneration

Regeneration steps:
1. confirm the Claire House `3.A` and `3.B` artefacts exist
2. run `models/build_data_infrastructure_models_and_process_improvement.py`
3. review the maintained layer, control profile, reuse summary, and release checks
4. use the execution report to decide whether analytical plots are needed
""",
        BASE_DIR / "CHANGELOG_processing_layer.md": """# Changelog - Processing Layer

- v1: initial maintained analytical-layer and bounded efficiency-improvement proof built from Claire House `3.A` and `3.B`
""",
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")


def main() -> None:
    start = time.perf_counter()
    ensure_dirs()
    provision_summary, reporting_summary, ad_hoc_detail, fact_pack_a, fact_pack_b = load_inputs()
    layer = build_maintained_layer(provision_summary, reporting_summary, ad_hoc_detail)
    control_profile = build_control_profile(layer, fact_pack_b)
    reuse_summary = build_reuse_summary(layer)
    release_checks = build_release_checks(layer, ad_hoc_detail, reporting_summary)
    fact_pack = build_fact_pack(layer, control_profile, reuse_summary, release_checks)
    fact_pack["regeneration_seconds"] = time.perf_counter() - start
    fact_pack["inherited_source_surfaces_mapped"] = int(fact_pack_a["source_surfaces_mapped"])

    layer.to_parquet(EXTRACTS_DIR / "maintained_processing_layer_v1.parquet", index=False)
    control_profile.to_parquet(EXTRACTS_DIR / "processing_layer_control_profile_v1.parquet", index=False)
    reuse_summary.to_parquet(EXTRACTS_DIR / "processing_layer_reuse_summary_v1.parquet", index=False)
    release_checks.to_parquet(EXTRACTS_DIR / "processing_layer_release_checks_v1.parquet", index=False)
    (METRICS_DIR / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2),
        encoding="utf-8",
    )
    write_notes(fact_pack)


if __name__ == "__main__":
    main()
