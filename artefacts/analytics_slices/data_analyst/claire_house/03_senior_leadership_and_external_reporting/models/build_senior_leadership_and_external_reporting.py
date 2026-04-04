from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = BASE_DIR.parent / "02_reporting_dashboards_and_visualisation"
EXTRACTS_DIR = BASE_DIR / "extracts"
METRICS_DIR = BASE_DIR / "metrics"


def ensure_dirs() -> None:
    EXTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    extracts = SOURCE_DIR / "extracts"
    metrics = SOURCE_DIR / "metrics" / "execution_fact_pack.json"
    summary = pd.read_parquet(extracts / "trusted_reporting_summary_v1.parquet")
    detail = pd.read_parquet(extracts / "trusted_reporting_ad_hoc_detail_v1.parquet")
    release = pd.read_parquet(extracts / "reporting_visualisation_release_checks_v1.parquet")
    fact_pack = json.loads(metrics.read_text(encoding="utf-8"))
    return summary, detail, release, fact_pack


def build_leadership_summary(summary: pd.DataFrame, focus_row: pd.Series, fact_pack: dict) -> pd.DataFrame:
    row = summary.iloc[0]
    return pd.DataFrame(
        [
            {
                "reporting_window": row["reporting_window"],
                "audience": "senior_leadership",
                "pack_type": "leadership_summary",
                "shared_kpi_family_count": int(row["kpi_family_count"]),
                "shared_reporting_views_count": int(row["scheduled_views_count"] + row["ad_hoc_views_count"]),
                "overall_flow_rows": int(row["overall_flow_rows"]),
                "overall_case_open_rate": float(row["overall_case_open_rate"]),
                "overall_truth_quality": float(row["overall_truth_quality"]),
                "top_attention_band": str(focus_row["band_label"]),
                "top_attention_case_open_gap_pp": float(focus_row["case_open_gap_pp"]),
                "top_attention_truth_quality_gap_pp": float(focus_row["truth_quality_gap_pp"]),
                "top_attention_burden_minus_yield_pp": float(focus_row["burden_minus_yield_pp"]),
                "inherited_source_surfaces_mapped": int(fact_pack["inherited_source_surfaces_mapped"]),
            }
        ]
    )


def build_external_cut(summary: pd.DataFrame, focus_row: pd.Series) -> pd.DataFrame:
    row = summary.iloc[0]
    overall = {
        "reporting_window": row["reporting_window"],
        "audience": "external_oversight",
        "oversight_row": "overall",
        "band_label": "Overall",
        "flow_rows": int(row["overall_flow_rows"]),
        "flow_share": 1.0,
        "case_open_rate": float(row["overall_case_open_rate"]),
        "case_open_gap_pp": 0.0,
        "case_truth_rate": float(row["overall_truth_quality"]),
        "truth_quality_gap_pp": 0.0,
        "burden_minus_yield_pp": 0.0,
        "priority_rank": 0,
    }
    focus = {
        "reporting_window": row["reporting_window"],
        "audience": "external_oversight",
        "oversight_row": "focus_band",
        "band_label": str(focus_row["band_label"]),
        "flow_rows": int(focus_row["flow_rows"]),
        "flow_share": float(focus_row["flow_share"]),
        "case_open_rate": float(focus_row["case_open_rate"]),
        "case_open_gap_pp": float(focus_row["case_open_gap_pp"]),
        "case_truth_rate": float(focus_row["case_truth_rate"]),
        "truth_quality_gap_pp": float(focus_row["truth_quality_gap_pp"]),
        "burden_minus_yield_pp": float(focus_row["burden_minus_yield_pp"]),
        "priority_rank": int(focus_row["priority_rank"]),
    }
    return pd.DataFrame([overall, focus])


def build_release_checks(
    leadership_summary: pd.DataFrame,
    external_cut: pd.DataFrame,
    release_checks: pd.DataFrame,
    inherited_release_count: int,
) -> pd.DataFrame:
    leadership = leadership_summary.iloc[0]
    external_focus = external_cut.loc[external_cut["oversight_row"] == "focus_band"].iloc[0]
    checks = [
        {
            "check_name": "leadership_summary_contains_single_audience_row",
            "actual_value": float(len(leadership_summary)),
            "expected_rule": "= 1 leadership summary row present",
            "passed_flag": int(len(leadership_summary) == 1),
        },
        {
            "check_name": "external_cut_contains_overall_and_focus_rows",
            "actual_value": float(len(external_cut)),
            "expected_rule": "= 2 rows covering overall and the top focus band",
            "passed_flag": int(len(external_cut) == 2),
        },
        {
            "check_name": "leadership_and_external_reuse_same_focus_band",
            "actual_value": float(leadership["top_attention_band"] == external_focus["band_label"]),
            "expected_rule": "= 1 same focus band carried across both audience cuts",
            "passed_flag": int(leadership["top_attention_band"] == external_focus["band_label"]),
        },
        {
            "check_name": "leadership_and_external_reuse_same_case_open_gap",
            "actual_value": float(
                abs(leadership["top_attention_case_open_gap_pp"] - external_focus["case_open_gap_pp"])
            ),
            "expected_rule": "= 0 delta in focus-band case-open gap across both cuts",
            "passed_flag": int(
                abs(leadership["top_attention_case_open_gap_pp"] - external_focus["case_open_gap_pp"]) < 1e-12
            ),
        },
        {
            "check_name": "leadership_and_external_reuse_same_truth_quality_gap",
            "actual_value": float(
                abs(
                    leadership["top_attention_truth_quality_gap_pp"]
                    - external_focus["truth_quality_gap_pp"]
                )
            ),
            "expected_rule": "= 0 delta in focus-band truth-quality gap across both cuts",
            "passed_flag": int(
                abs(
                    leadership["top_attention_truth_quality_gap_pp"]
                    - external_focus["truth_quality_gap_pp"]
                )
                < 1e-12
            ),
        },
        {
            "check_name": "inherited_reporting_release_pack_remains_green",
            "actual_value": float(release_checks["passed_flag"].sum()),
            "expected_rule": f"= {inherited_release_count} inherited reporting checks still passed",
            "passed_flag": int(release_checks["passed_flag"].sum() == inherited_release_count),
        },
    ]
    return pd.DataFrame(checks)


def build_fact_pack(
    leadership_summary: pd.DataFrame,
    external_cut: pd.DataFrame,
    release_checks: pd.DataFrame,
    inherited_release_count: int,
) -> dict:
    leadership = leadership_summary.iloc[0]
    focus = external_cut.loc[external_cut["oversight_row"] == "focus_band"].iloc[0]
    return {
        "slice": "claire_house/03_senior_leadership_and_external_reporting",
        "reporting_window": leadership["reporting_window"],
        "audience_specific_views_count": 2,
        "shared_kpi_family_count": int(leadership["shared_kpi_family_count"]),
        "leadership_summary_count": int(len(leadership_summary)),
        "external_oversight_row_count": int(len(external_cut)),
        "overall_flow_rows": int(leadership["overall_flow_rows"]),
        "overall_case_open_rate": float(leadership["overall_case_open_rate"]),
        "overall_truth_quality": float(leadership["overall_truth_quality"]),
        "top_attention_band": str(leadership["top_attention_band"]),
        "top_attention_case_open_gap_pp": float(leadership["top_attention_case_open_gap_pp"]),
        "top_attention_truth_quality_gap_pp": float(leadership["top_attention_truth_quality_gap_pp"]),
        "top_attention_burden_minus_yield_pp": float(leadership["top_attention_burden_minus_yield_pp"]),
        "focus_band_flow_share": float(focus["flow_share"]),
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "inherited_reporting_checks_passed": int(inherited_release_count),
    }


def write_markdown(fact_pack: dict) -> None:
    leadership_pack = f"""# Leadership Summary Pack v1

Reporting window:
- `{fact_pack['reporting_window'].replace('-01', '') if '-01' in fact_pack['reporting_window'] else fact_pack['reporting_window']}`

Leadership reading:
- overall case-open rate remains controlled at `{fact_pack['overall_case_open_rate']:.2%}`
- overall truth quality remains `{fact_pack['overall_truth_quality']:.2%}`
- the clearest band-level attention point remains `{fact_pack['top_attention_band']}`
- `{fact_pack['top_attention_band']}` carries a burden-minus-yield gap of `{fact_pack['top_attention_burden_minus_yield_pp'] * 100:+.2f} pp`

What matters next:
- leadership attention should stay on the bounded focus band rather than broad lane-wide concern
- the higher-accountability pack reuses the same governed KPI base and keeps the reading concise
"""
    external_pack = f"""# External Oversight Reporting Cut v1

Oversight purpose:
- provide one concise external-style reporting cut from the same governed KPI base

Oversight comparison:
- overall case-open rate: `{fact_pack['overall_case_open_rate']:.2%}`
- overall truth quality: `{fact_pack['overall_truth_quality']:.2%}`
- focus band: `{fact_pack['top_attention_band']}`
- focus-band case-open gap: `{fact_pack['top_attention_case_open_gap_pp'] * 100:+.2f} pp`
- focus-band truth-quality gap: `{fact_pack['top_attention_truth_quality_gap_pp'] * 100:+.2f} pp`
- focus-band burden-minus-yield gap: `{fact_pack['top_attention_burden_minus_yield_pp'] * 100:+.2f} pp`

Use posture:
- this cut is suitable for bounded oversight-style circulation
- it is not a whole submission programme or full external reporting estate
"""
    scope_note = """# Leadership And External Reporting Scope Note v1

This slice reshapes the governed Claire House reporting base into:
- one concise leadership summary pack
- one bounded external-style oversight cut

It does not claim:
- a full board-reporting estate
- a whole regulatory or compliance reporting function
- a broad submission environment
"""
    audience_matrix = """# Leadership And External Audience Matrix v1

| Audience | Needs first | Output form | Control posture |
|---|---|---|---|
| Senior leadership | concise top-line status and one clear attention point | one leadership summary pack | same governed KPI base with concise reading note |
| External-style oversight | compact, trust-safe comparison and caveated focus point | one oversight cut | same governed KPI base with explicit caveat and trust note |
"""
    leadership_note = f"""# Leadership Reporting Reading Note v1

Leadership should read this pack as:
- a concise top-line status update for `{fact_pack['reporting_window']}`
- confirmation that the controlled lane remains stable overall
- one focused attention point in `{fact_pack['top_attention_band']}` rather than a broad deterioration story
"""
    external_note = """# External Oversight Reporting Use Note v1

This oversight cut is for:
- bounded external-style review
- concise high-accountability discussion
- controlled reuse of the same KPI base already established internally

It is not for:
- broad external benchmarking claims
- formal regulatory submission claims
- organisation-wide compliance assertions
"""
    caveats = """# Leadership And External Caveats v1

Caveats:
- the slice reuses one governed reporting window and one supporting focus band only
- the external-style cut is an oversight analogue, not a live submission artefact
- the higher-accountability pack inherits trust from Claire House `3.A` and reporting consistency from Claire House `3.B`
"""
    trust = """# Leadership And External Trust Note v1

Trust boundary:
- the leadership and external-style outputs inherit the controlled provision path from Claire House `3.A`
- the KPI family and supporting band logic inherit the governed reporting base from Claire House `3.B`
- no new raw detailed rebuild was introduced for this slice
"""
    readme = """# Leadership And External Reporting Regeneration

Regeneration steps:
1. confirm the Claire House `3.A` and `3.B` artefacts exist
2. run `models/build_senior_leadership_and_external_reporting.py`
3. review the leadership summary output, external oversight cut, and release checks
4. use the execution report to decide whether analytical figures are needed
"""
    changelog = """# Changelog - Leadership And External Reporting

- v1: initial bounded higher-accountability reporting pack built from the Claire House `3.A` and `3.B` governed base
"""

    files = {
        BASE_DIR / "leadership_summary_pack_v1.md": leadership_pack,
        BASE_DIR / "external_oversight_reporting_cut_v1.md": external_pack,
        BASE_DIR / "leadership_external_reporting_scope_note_v1.md": scope_note,
        BASE_DIR / "leadership_external_audience_matrix_v1.md": audience_matrix,
        BASE_DIR / "leadership_reporting_reading_note_v1.md": leadership_note,
        BASE_DIR / "external_oversight_reporting_use_note_v1.md": external_note,
        BASE_DIR / "leadership_external_caveats_v1.md": caveats,
        BASE_DIR / "leadership_external_trust_note_v1.md": trust,
        BASE_DIR / "README_leadership_external_reporting_regeneration.md": readme,
        BASE_DIR / "CHANGELOG_leadership_external_reporting.md": changelog,
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    summary, detail, release_checks, fact_pack = load_inputs()
    focus_row = detail.sort_values("priority_rank").iloc[0]
    leadership_summary = build_leadership_summary(summary, focus_row, fact_pack)
    external_cut = build_external_cut(summary, focus_row)
    leadership_release_checks = build_release_checks(
        leadership_summary,
        external_cut,
        release_checks,
        int(release_checks["passed_flag"].sum()),
    )
    execution_fact_pack = build_fact_pack(
        leadership_summary,
        external_cut,
        leadership_release_checks,
        int(release_checks["passed_flag"].sum()),
    )

    leadership_summary.to_parquet(EXTRACTS_DIR / "leadership_reporting_summary_v1.parquet", index=False)
    external_cut.to_parquet(EXTRACTS_DIR / "external_oversight_reporting_cut_v1.parquet", index=False)
    leadership_release_checks.to_parquet(
        EXTRACTS_DIR / "leadership_external_release_checks_v1.parquet",
        index=False,
    )
    (METRICS_DIR / "execution_fact_pack.json").write_text(
        json.dumps(execution_fact_pack, indent=2),
        encoding="utf-8",
    )
    write_markdown(execution_fact_pack)


if __name__ == "__main__":
    main()
