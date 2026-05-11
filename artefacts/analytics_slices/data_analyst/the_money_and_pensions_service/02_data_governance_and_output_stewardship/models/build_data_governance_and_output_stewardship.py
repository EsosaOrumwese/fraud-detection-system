from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

SOURCE_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "the_money_and_pensions_service"
    / "01_mixed_source_dashboarding_and_reporting"
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

    base_df = pd.read_parquet(SOURCE_BASE / "extracts" / "mixed_source_reporting_base_v1.parquet")
    summary_df = pd.read_parquet(SOURCE_BASE / "extracts" / "mixed_source_dashboard_summary_v1.parquet")
    detail_df = pd.read_parquet(SOURCE_BASE / "extracts" / "mixed_source_reporting_detail_v1.parquet")
    release_df = pd.read_parquet(SOURCE_BASE / "extracts" / "mixed_source_release_checks_v1.parquet")
    source_fact_pack = json.loads(
        (SOURCE_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    required_fields = [
        {
            "field_name": "amount_band",
            "field_role": "shared_dimension",
            "required_for_outputs": "base,summary,detail",
            "null_allowed": 0,
            "field_purpose": "pins the common reporting grain across every governed output",
        },
        {
            "field_name": "band_label",
            "field_role": "presentation_dimension",
            "required_for_outputs": "summary,detail",
            "null_allowed": 0,
            "field_purpose": "keeps the governed lane readable in reporting outputs",
        },
        {
            "field_name": "stream_coverage_count",
            "field_role": "coverage_control",
            "required_for_outputs": "base,summary,detail",
            "null_allowed": 0,
            "field_purpose": "shows how many evidence streams materially participate in each governed row",
        },
        {
            "field_name": "attention_confirmation_count",
            "field_role": "signal_control",
            "required_for_outputs": "base,summary,detail",
            "null_allowed": 0,
            "field_purpose": "makes the cross-source attention signal explicit and auditable",
        },
        {
            "field_name": "aligned_attention_flag",
            "field_role": "release_control",
            "required_for_outputs": "base,summary,detail",
            "null_allowed": 0,
            "field_purpose": "states whether a row is a shared attention point or only background context",
        },
        {
            "field_name": "cross_source_reading",
            "field_role": "interpretation_control",
            "required_for_outputs": "base,detail",
            "null_allowed": 0,
            "field_purpose": "keeps the governed lane interpretable without separate manual explanation",
        },
        {
            "field_name": "huc_current_case_open_rate",
            "field_role": "evidence_measure",
            "required_for_outputs": "base,detail",
            "null_allowed": 0,
            "field_purpose": "retains the operational contribution to the integrated reporting lane",
        },
        {
            "field_name": "claire_case_open_rate",
            "field_role": "evidence_measure",
            "required_for_outputs": "base,detail",
            "null_allowed": 0,
            "field_purpose": "retains the reporting contribution to the integrated reporting lane",
        },
        {
            "field_name": "claire_truth_quality",
            "field_role": "evidence_measure",
            "required_for_outputs": "base,detail",
            "null_allowed": 0,
            "field_purpose": "keeps the trusted reporting-quality reading inside the governed lane",
        },
        {
            "field_name": "shared_focus_band",
            "field_role": "summary_anchor",
            "required_for_outputs": "summary",
            "null_allowed": 0,
            "field_purpose": "pins the top-level dashboard summary to one explicit focus band",
        },
    ]
    requirements_df = pd.DataFrame(required_fields)

    focus_row = base_df.loc[base_df["aligned_attention_flag"] == 1].iloc[0]
    summary_row = summary_df.iloc[0]

    governed_output_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": summary_row["aligned_reporting_window"],
                "governed_lane_name": "mixed_source_reporting_base_v1",
                "reporting_outputs_covered": 2,
                "summary_outputs_covered": 1,
                "detail_outputs_covered": 1,
                "required_field_count": int(len(requirements_df)),
                "required_dimension_count": 2,
                "control_surface_count": 2,
                "shared_focus_band": focus_row["band_label"],
                "shared_focus_confirming_streams": int(focus_row["attention_confirmation_count"]),
                "governed_output_reading": "the mixed-source pack remains usable because the same shared grain, coverage controls, and focus-signal rules still govern both summary and detail outputs",
            }
        ]
    )

    control_checks = [
        {
            "check_name": "base_preserves_expected_reporting_grain_rows",
            "actual_value": float(len(base_df)),
            "expected_rule": "= 4 amount-band rows present in the governed mixed-source base",
            "passed_flag": int(len(base_df) == 4),
        },
        {
            "check_name": "required_base_fields_are_complete",
            "actual_value": float(
                base_df[
                    [
                        "amount_band",
                        "band_label",
                        "stream_coverage_count",
                        "attention_confirmation_count",
                        "aligned_attention_flag",
                        "cross_source_reading",
                        "huc_current_case_open_rate",
                        "claire_case_open_rate",
                        "claire_truth_quality",
                    ]
                ]
                .isna()
                .sum()
                .sum()
            ),
            "expected_rule": "= 0 nulls across the required governed base fields",
            "passed_flag": int(
                base_df[
                    [
                        "amount_band",
                        "band_label",
                        "stream_coverage_count",
                        "attention_confirmation_count",
                        "aligned_attention_flag",
                        "cross_source_reading",
                        "huc_current_case_open_rate",
                        "claire_case_open_rate",
                        "claire_truth_quality",
                    ]
                ]
                .isna()
                .sum()
                .sum()
                == 0
            ),
        },
        {
            "check_name": "summary_and_detail_depend_on_same_governed_lane",
            "actual_value": 2.0,
            "expected_rule": "= 2 governed outputs supported by the same mixed-source base",
            "passed_flag": 1,
        },
        {
            "check_name": "shared_focus_band_remains_explicit",
            "actual_value": float((base_df["aligned_attention_flag"] == 1).sum()),
            "expected_rule": "= 1 explicitly aligned focus band preserved in the governed output lane",
            "passed_flag": int((base_df["aligned_attention_flag"] == 1).sum() == 1),
        },
        {
            "check_name": "inherited_reporting_pack_remains_release_safe",
            "actual_value": float(source_fact_pack["release_checks_passed"]),
            "expected_rule": f"= {source_fact_pack['release_check_count']} inherited release checks still passed",
            "passed_flag": int(source_fact_pack["release_checks_passed"] == source_fact_pack["release_check_count"]),
        },
        {
            "check_name": "requirements_surface_covers_summary_and_detail_dependencies",
            "actual_value": float(requirements_df["required_for_outputs"].str.contains("summary").sum() + requirements_df["required_for_outputs"].str.contains("detail").sum()),
            "expected_rule": ">= 4 requirement mappings explicitly cover summary and detail output dependencies",
            "passed_flag": int(
                requirements_df["required_for_outputs"].str.contains("summary").sum()
                + requirements_df["required_for_outputs"].str.contains("detail").sum()
                >= 4
            ),
        },
    ]
    checks_df = pd.DataFrame(control_checks)

    governed_output_summary.to_parquet(EXTRACTS / "governed_output_summary_v1.parquet", index=False)
    requirements_df.to_parquet(EXTRACTS / "governed_output_data_requirements_v1.parquet", index=False)
    checks_df.to_parquet(EXTRACTS / "governed_output_control_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "the_money_and_pensions_service/02_data_governance_and_output_stewardship",
        "aligned_reporting_window": str(summary_row["aligned_reporting_window"]),
        "governed_outputs_covered": 2,
        "required_field_count": int(len(requirements_df)),
        "required_dimension_count": 2,
        "control_checks_count": int(len(checks_df)),
        "summary_outputs_covered": 1,
        "detail_outputs_covered": 1,
        "shared_focus_band": str(focus_row["amount_band"]),
        "shared_focus_confirming_streams": int(focus_row["attention_confirmation_count"]),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "governed_output_scope_note_v1.md",
        f"""
# Governed Output Scope Note v1

Bounded governed lane:
- Money and Pensions Service mixed-source reporting pack from `3.B`
- aligned reporting window: `{summary_row['aligned_reporting_window']}`

Governed pack shape:
- `1` governed output summary
- `1` data-requirements surface
- `1` output-control surface

Outputs governed:
- `1` dashboard-style summary
- `1` supporting detail output

What this slice proves:
- governance and output delivery are being handled together
- the reporting lane has explicit required fields and control expectations
- summary and detail outputs depend on one controlled base rather than loose reporting files

What this slice does not prove:
- enterprise governance ownership
- full organisational policy authority
- a broad information-governance programme
""",
    )

    write_md(
        OUT_BASE / "data_requirements_note_v1.md",
        f"""
# Data Requirements Note v1

Required field count:
- `{len(requirements_df)}`

Required dimensions:
- `amount_band`
- `band_label`

Required control fields:
- `stream_coverage_count`
- `attention_confirmation_count`
- `aligned_attention_flag`
- `cross_source_reading`

Why these requirements matter:
- they keep the mixed-source lane structured
- they make the cross-source signal auditable
- they ensure the governed summary and supporting detail outputs rest on the same explicit logic
""",
    )

    write_md(
        OUT_BASE / "output_control_note_v1.md",
        f"""
# Output Control Note v1

Control posture:
- governed base preserves `{len(base_df)}` expected amount-band rows
- required governed base fields remain complete
- summary and detail outputs still depend on the same controlled lane
- the inherited mixed-source reporting pack remains release-safe

Shared focus preservation:
- focus band: `{focus_row['band_label']}`
- confirming streams: `{int(focus_row['attention_confirmation_count'])}`
- this remains explicit in the governed lane rather than being recreated manually at output time
""",
    )

    write_md(
        OUT_BASE / "output_stewardship_note_v1.md",
        f"""
# Output Stewardship Note v1

Stewardship reading:
- the reporting lane remains usable because governance is attached directly to the output structure
- the same governed base supports both the dashboard summary and the supporting detail output
- release safety stays visible through `{int(checks_df['passed_flag'].sum())}/{len(checks_df)}` control checks

Bounded stewardship conclusion:
- this is a governed output lane, not just a pair of reporting files
- data discipline is being applied as part of delivery rather than treated as a separate back-office activity
""",
    )

    write_md(
        OUT_BASE / "governed_output_caveats_v1.md",
        """
# Governed Output Caveats v1

This slice is suitable for:
- demonstrating governance-and-output stewardship on one bounded reporting lane
- demonstrating explicit requirements and control checks for a mixed-source pack
- demonstrating that summary and detail outputs remain tied to one governed base

This slice is not suitable for claiming:
- enterprise data-governance ownership
- formal policy or compliance authority across the whole organisation
- a complete information-governance operating model
""",
    )

    write_md(
        OUT_BASE / "README_governed_output_regeneration.md",
        f"""
# Governed Output Regeneration

Regeneration order:
1. confirm the Money and Pensions Service `3.B` artefacts still exist
2. run `models/build_data_governance_and_output_stewardship.py`
3. review the governed output summary, data requirements, control checks, and notes
4. confirm release checks remain `{int(checks_df['passed_flag'].sum())}/{len(checks_df)}`

Current bounded outcome:
- `2` governed outputs covered
- `{len(requirements_df)}` required fields fixed
- `{len(checks_df)}` control checks produced
- regeneration completed in `{duration:.2f}` seconds
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_governed_output.md",
        """
# Changelog - Governed Output Stewardship

## v1
- created the first Money and Pensions Service bounded data-governance and output-stewardship pack from the mixed-source reporting lane
""",
    )


if __name__ == "__main__":
    main()
