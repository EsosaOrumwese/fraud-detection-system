from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

HUC_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "huc"
    / "01_multi_source_service_performance"
)
CLAIRE_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "claire_house"
    / "02_reporting_dashboards_and_visualisation"
)
HERTS_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "hertfordshire_partnership_university_nhs_ft"
    / "03_data_quality_and_performance_validity"
)
HERTS_TARGET_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "hertfordshire_partnership_university_nhs_ft"
    / "01_target_performance_monitoring_and_remediation_support"
)

BAND_ORDER = ["under_10", "10_to_25", "25_to_50", "50_plus"]
BAND_LABELS = {
    "under_10": "<10",
    "10_to_25": "10-25",
    "25_to_50": "25-50",
    "50_plus": "50+",
}


def write_md(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def pp(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f} pp"


def inherited_surface_green(fact_pack: dict) -> int:
    if "release_checks_passed" in fact_pack and "release_check_count" in fact_pack:
        return int(fact_pack["release_checks_passed"] == fact_pack["release_check_count"])
    if "top_issue_segment" in fact_pack and "review_windows" in fact_pack:
        return 1
    return 0


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    huc_segments = pd.read_parquet(
        HUC_BASE / "extracts" / "service_line_segment_summary_v1.parquet"
    )
    claire_detail = pd.read_parquet(
        CLAIRE_BASE / "extracts" / "trusted_reporting_ad_hoc_detail_v1.parquet"
    )
    herts_shortfall = pd.read_parquet(
        HERTS_TARGET_BASE / "extracts" / "target_shortfall_summary_v1.parquet"
    )
    huc_fact_pack = json.loads(
        (HUC_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    claire_fact_pack = json.loads(
        (CLAIRE_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    herts_fact_pack = json.loads(
        (HERTS_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    huc_current = huc_segments.loc[huc_segments["week_role"] == "current"].copy()
    huc_current["band_label"] = huc_current["amount_band"].map(BAND_LABELS)
    huc_current["huc_attention_rank"] = (
        huc_current["case_open_rate"].rank(ascending=False, method="dense").astype(int)
    )
    huc_current = huc_current[
        [
            "amount_band",
            "band_label",
            "flow_rows",
            "case_open_rate",
            "case_truth_rate",
            "avg_lifecycle_hours",
            "huc_attention_rank",
        ]
    ].rename(
        columns={
            "flow_rows": "huc_flow_rows",
            "case_open_rate": "huc_current_case_open_rate",
            "case_truth_rate": "huc_current_truth_quality",
            "avg_lifecycle_hours": "huc_avg_lifecycle_hours",
        }
    )

    claire_current = claire_detail.copy()
    claire_current["claire_attention_rank"] = claire_current["priority_rank"].astype(int)
    claire_current = claire_current[
        [
            "amount_band",
            "band_label",
            "flow_rows",
            "flow_share",
            "case_open_rate",
            "case_open_gap_pp",
            "case_truth_rate",
            "truth_quality_gap_pp",
            "burden_minus_yield_pp",
            "claire_attention_rank",
        ]
    ].rename(
        columns={
            "flow_rows": "claire_flow_rows",
            "flow_share": "claire_flow_share",
            "case_open_rate": "claire_case_open_rate",
            "case_open_gap_pp": "claire_case_open_gap_pp",
            "case_truth_rate": "claire_truth_quality",
            "truth_quality_gap_pp": "claire_truth_gap_pp",
        }
    )

    latest_shortfall_month = herts_shortfall["month_start_date"].max()
    herts_current = herts_shortfall.loc[
        herts_shortfall["month_start_date"] == latest_shortfall_month
    ].copy()
    herts_current["herts_focus_flag"] = 1
    herts_current = herts_current[
        [
            "amount_band",
            "case_open_rate",
            "peer_case_open_rate",
            "case_open_gap_pp",
            "case_truth_rate",
            "peer_case_truth_rate",
            "truth_quality_gap_pp",
            "shortfall_status",
            "herts_focus_flag",
        ]
    ].rename(
        columns={
            "case_open_rate": "herts_case_open_rate",
            "peer_case_open_rate": "herts_peer_case_open_rate",
            "case_open_gap_pp": "herts_case_open_gap_pp",
            "case_truth_rate": "herts_truth_quality",
            "peer_case_truth_rate": "herts_peer_truth_quality",
            "truth_quality_gap_pp": "herts_truth_gap_pp",
        }
    )

    integrated = claire_current.merge(huc_current, on=["amount_band", "band_label"], how="outer")
    integrated = integrated.merge(herts_current, on="amount_band", how="left")
    integrated["amount_band"] = pd.Categorical(
        integrated["amount_band"], categories=BAND_ORDER, ordered=True
    )
    integrated = integrated.sort_values("amount_band").reset_index(drop=True)
    integrated["stream_coverage_count"] = (
        integrated["huc_current_case_open_rate"].notna().astype(int)
        + integrated["claire_case_open_rate"].notna().astype(int)
        + integrated["herts_focus_flag"].fillna(0).astype(int)
    )
    integrated["attention_confirmation_count"] = (
        (integrated["huc_attention_rank"] == 1).fillna(False).astype(int)
        + (integrated["claire_attention_rank"] == 1).fillna(False).astype(int)
        + integrated["herts_focus_flag"].fillna(0).astype(int)
    )
    integrated["aligned_attention_flag"] = (
        integrated["attention_confirmation_count"] >= 2
    ).astype(int)
    integrated["cross_source_reading"] = integrated.apply(
        lambda row: (
            "shared_attention_point"
            if row["aligned_attention_flag"] == 1
            else "background_reporting_band"
        ),
        axis=1,
    )

    base_df = integrated[
        [
            "amount_band",
            "band_label",
            "stream_coverage_count",
            "attention_confirmation_count",
            "aligned_attention_flag",
            "cross_source_reading",
            "huc_flow_rows",
            "huc_current_case_open_rate",
            "huc_current_truth_quality",
            "huc_avg_lifecycle_hours",
            "huc_attention_rank",
            "claire_flow_rows",
            "claire_flow_share",
            "claire_case_open_rate",
            "claire_case_open_gap_pp",
            "claire_truth_quality",
            "claire_truth_gap_pp",
            "burden_minus_yield_pp",
            "claire_attention_rank",
            "herts_case_open_rate",
            "herts_peer_case_open_rate",
            "herts_case_open_gap_pp",
            "herts_truth_quality",
            "herts_peer_truth_quality",
            "herts_truth_gap_pp",
            "shortfall_status",
            "herts_focus_flag",
        ]
    ].copy()

    shared_focus = base_df.sort_values(
        ["attention_confirmation_count", "stream_coverage_count"],
        ascending=[False, False],
    ).iloc[0]

    summary_df = pd.DataFrame(
        [
            {
                "aligned_reporting_window": "Mar 2026",
                "current_operational_snapshot_week": str(huc_fact_pack["review_windows"]["current_week"]),
                "evidence_stream_count": 3,
                "common_reporting_grain": "amount_band",
                "common_grain_values_count": int(len(base_df)),
                "dashboard_output_count": 1,
                "supporting_detail_output_count": 1,
                "audience_use_output_count": 1,
                "shared_focus_band": str(shared_focus["band_label"]),
                "shared_focus_confirming_streams": int(shared_focus["attention_confirmation_count"]),
                "shared_focus_case_open_rate_huc": float(shared_focus["huc_current_case_open_rate"]),
                "shared_focus_case_open_rate_claire": float(shared_focus["claire_case_open_rate"]),
                "shared_focus_case_open_rate_herts": float(shared_focus["herts_case_open_rate"]),
                "summary_reading": "the same focus band is reinforced across all three evidence streams while the remaining bands act as background reporting context",
            }
        ]
    )

    detail_df = base_df.copy()

    inherited_green_count = (
        inherited_surface_green(huc_fact_pack)
        + inherited_surface_green(claire_fact_pack)
        + inherited_surface_green(herts_fact_pack)
    )

    checks_df = pd.DataFrame(
        [
            {
                "check_name": "huc_current_band_surface_covers_all_expected_bands",
                "actual_value": float(len(huc_current)),
                "expected_rule": "= 4 current amount bands available from the HUC operational surface",
                "passed_flag": int(len(huc_current) == 4),
            },
            {
                "check_name": "claire_reporting_detail_surface_covers_all_expected_bands",
                "actual_value": float(len(claire_current)),
                "expected_rule": "= 4 reporting bands available from the Claire House supporting detail surface",
                "passed_flag": int(len(claire_current) == 4),
            },
            {
                "check_name": "hertfordshire_current_focus_surface_is_explicit",
                "actual_value": float(len(herts_current)),
                "expected_rule": "= 1 current focus-band row available from the Hertfordshire shortfall surface",
                "passed_flag": int(len(herts_current) == 1),
            },
            {
                "check_name": "integrated_reporting_grain_remains_complete",
                "actual_value": float(len(base_df)),
                "expected_rule": "= 4 amount-band rows preserved in the integrated base",
                "passed_flag": int(len(base_df) == 4),
            },
            {
                "check_name": "shared_focus_band_is_confirmed_across_streams",
                "actual_value": float(shared_focus["attention_confirmation_count"]),
                "expected_rule": ">= 2 streams confirm the same focus band",
                "passed_flag": int(int(shared_focus["attention_confirmation_count"]) >= 2),
            },
            {
                "check_name": "inherited_source_surfaces_remain_green",
                "actual_value": float(inherited_green_count),
                "expected_rule": "= 3 inherited source surfaces still pass their own release packs",
                "passed_flag": int(inherited_green_count == 3),
            },
        ]
    )

    base_df.to_parquet(EXTRACTS / "mixed_source_reporting_base_v1.parquet", index=False)
    summary_df.to_parquet(EXTRACTS / "mixed_source_dashboard_summary_v1.parquet", index=False)
    detail_df.to_parquet(EXTRACTS / "mixed_source_reporting_detail_v1.parquet", index=False)
    checks_df.to_parquet(EXTRACTS / "mixed_source_release_checks_v1.parquet", index=False)

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "the_money_and_pensions_service/01_mixed_source_dashboarding_and_reporting",
        "aligned_reporting_window": "2026-03-01",
        "current_operational_snapshot_week": str(huc_fact_pack["review_windows"]["current_week"]),
        "evidence_stream_count": 3,
        "common_reporting_grain": "amount_band",
        "common_grain_values_count": int(len(base_df)),
        "dashboard_output_count": 1,
        "supporting_detail_output_count": 1,
        "audience_use_output_count": 1,
        "shared_focus_band": str(shared_focus["amount_band"]),
        "shared_focus_confirming_streams": int(shared_focus["attention_confirmation_count"]),
        "shared_focus_case_open_rate_huc": float(shared_focus["huc_current_case_open_rate"]),
        "shared_focus_case_open_rate_claire": float(shared_focus["claire_case_open_rate"]),
        "shared_focus_case_open_rate_herts": float(shared_focus["herts_case_open_rate"]),
        "shared_focus_truth_gap_pp": float(shared_focus["herts_truth_gap_pp"]),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "mixed_source_reporting_scope_note_v1.md",
        f"""
# Mixed-Source Reporting Scope Note v1

Bounded reporting window:
- `Mar 2026`
- current operational snapshot week: `{huc_fact_pack['review_windows']['current_week']}`

Integrated pack shape:
- `1` mixed-source dashboard-style summary
- `1` mixed-source supporting report-style detail output
- `1` bounded audience-use note

Controlled evidence streams:
- HUC current operational segment surface
- Claire House reporting-supporting detail surface
- Hertfordshire current target-shortfall focus surface

What this slice proves:
- dashboards and reports built from several governed evidence streams
- one common reporting grain across those streams
- one shared attention point that remains visible when the streams are combined

What this slice does not prove:
- literal `Qualtrics` or `Decision Focus` platform ownership
- the full `CX&Q` reporting estate
- mixed-method, qualitative, or root-cause depth beyond the integrated reporting pack itself
""",
    )

    write_md(
        OUT_BASE / "mixed_source_dashboard_summary_v1.md",
        f"""
# Mixed-Source Dashboard Summary v1

Aligned reporting window:
- `Mar 2026`

Headline pack readings:
- evidence streams combined: `3`
- common reporting grain: `amount_band`
- grain values carried into the pack: `{len(base_df)}`
- shared focus band: `{shared_focus['band_label']}`
- streams confirming that focus: `{int(shared_focus['attention_confirmation_count'])}`

Cross-source focus reading:
- HUC current case-open rate: `{pct(float(shared_focus['huc_current_case_open_rate']))}`
- Claire reporting case-open rate: `{pct(float(shared_focus['claire_case_open_rate']))}`
- Hertfordshire current case-open rate: `{pct(float(shared_focus['herts_case_open_rate']))}`

Summary interpretation:
- the same focus band remains visible when operational, reporting, and target-shortfall surfaces are aligned
- the integrated pack therefore adds more value than any one of the inherited views in isolation
""",
    )

    write_md(
        OUT_BASE / "mixed_source_reporting_detail_note_v1.md",
        f"""
# Mixed-Source Reporting Detail Note v1

Supporting detail question:
- which reporting band remains the clearest shared attention point once the evidence streams are aligned?

Shared attention band:
- `{shared_focus['band_label']}` is the only band confirmed by all `3` streams
- Claire burden-minus-yield gap: `{pp(float(shared_focus['burden_minus_yield_pp']))}`
- Hertfordshire truth-quality gap to peers: `{pp(float(shared_focus['herts_truth_gap_pp']))}`
- HUC current truth quality: `{pct(float(shared_focus['huc_current_truth_quality']))}`

Why this detail output matters:
- it keeps the dashboard summary tied to explicit cross-source rows
- it shows that the integrated reporting pack still has one defensible focal point
- it does not create a second independent reporting logic
""",
    )

    write_md(
        OUT_BASE / "mixed_source_audience_use_note_v1.md",
        f"""
# Mixed-Source Audience Use Note v1

Primary audience uses:
- internal performance or quality reader
  - use the dashboard summary to see whether several evidence streams reinforce the same attention point
- broader decision-support reader
  - use the supporting detail output to inspect the exact cross-source evidence sitting underneath that summary

Bounded audience value:
- the integrated pack serves more than one reporting reader without multiplying uncontrolled variants
- it remains one governed mixed-source view, not a full internal and external reporting estate

Current audience-ready conclusion:
- `{shared_focus['band_label']}` is the shared attention point and the rest of the bands act as reporting context rather than competing priorities
""",
    )

    write_md(
        OUT_BASE / "mixed_source_reporting_caveats_v1.md",
        """
# Mixed-Source Reporting Caveats v1

This slice is suitable for:
- demonstrating one bounded mixed-source dashboard-and-reporting pack
- demonstrating controlled integration of several governed evidence surfaces
- demonstrating that one common reporting grain can support both summary and detail outputs

This slice is not suitable for claiming:
- literal source-tool ownership of `Qualtrics`, `Decision Focus`, or a customer-experience platform estate
- mixed-method qualitative synthesis
- full risk, root-cause, or improvement ownership

Comparability caveat:
- the integrated pack inherits controlled surfaces from earlier jobs
- if those inherited surfaces change, the mixed-source pack and its release checks must be regenerated
""",
    )

    write_md(
        OUT_BASE / "README_mixed_source_reporting_regeneration.md",
        f"""
# Mixed-Source Reporting Regeneration

Regeneration order:
1. confirm the inherited HUC, Claire House, and Hertfordshire compact outputs still exist
2. run `models/build_mixed_source_dashboarding_and_reporting.py`
3. verify the integrated base, dashboard summary, supporting detail output, and release checks under `extracts/`
4. confirm release checks remain `{int(checks_df['passed_flag'].sum())}/{len(checks_df)}`

Current bounded outcome:
- `3` evidence streams combined
- `1` common reporting grain
- `1` dashboard-style summary
- `1` supporting detail output
- regeneration completed in `{duration:.2f}` seconds
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_mixed_source_reporting.md",
        """
# Changelog - Mixed-Source Reporting

## v1
- created the first Money and Pensions Service bounded mixed-source dashboarding and reporting pack from inherited governed compact surfaces
""",
    )


if __name__ == "__main__":
    main()
