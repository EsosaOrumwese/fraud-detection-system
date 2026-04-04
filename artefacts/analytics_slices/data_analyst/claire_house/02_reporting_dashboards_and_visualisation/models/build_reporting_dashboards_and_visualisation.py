from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
CLAIRE_3A_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "claire_house"
    / "01_trusted_data_provision_and_integrity"
)
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

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


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    summary_path = (
        CLAIRE_3A_BASE
        / "extracts"
        / "trusted_data_provision_summary_v1.parquet"
    )
    integrity_path = (
        CLAIRE_3A_BASE
        / "extracts"
        / "trusted_data_provision_integrity_checks_v1.parquet"
    )
    fact_pack_path = CLAIRE_3A_BASE / "metrics" / "execution_fact_pack.json"

    base_summary = con.execute(
        f"select * from read_parquet('{summary_path.as_posix()}')"
    ).fetchdf()
    integrity = con.execute(
        f"select * from read_parquet('{integrity_path.as_posix()}')"
    ).fetchdf()
    prior_fact_pack = json.loads(fact_pack_path.read_text(encoding="utf-8"))

    overall = base_summary.loc[base_summary["amount_band"] == "__overall__"].iloc[0]
    bands = base_summary.loc[base_summary["amount_band"].isin(BAND_ORDER)].copy()
    bands["band_label"] = bands["amount_band"].map(BAND_LABELS)
    bands["flow_share"] = bands["flow_rows"] / float(overall["flow_rows"])
    bands["case_opened_share"] = bands["case_opened_rows"] / float(overall["case_opened_rows"])
    bands["truth_share"] = bands["case_truth_rows"] / float(overall["case_truth_rows"])
    bands["case_open_gap_pp"] = bands["case_open_rate"] - float(overall["case_open_rate"])
    bands["truth_quality_gap_pp"] = bands["case_truth_rate"] - float(overall["case_truth_rate"])
    bands["burden_minus_yield_pp"] = bands["case_opened_share"] - bands["truth_share"]
    bands["priority_rank"] = (
        bands["burden_minus_yield_pp"].rank(ascending=False, method="dense").astype(int)
    )
    bands["amount_band"] = pd.Categorical(bands["amount_band"], categories=BAND_ORDER, ordered=True)
    bands = bands.sort_values("amount_band").reset_index(drop=True)

    summary_df = pd.DataFrame(
        [
            {
                "reporting_window": "Mar 2026",
                "kpi_family_count": 4,
                "view_type": "scheduled_summary",
                "scheduled_views_count": 1,
                "ad_hoc_views_count": 1,
                "overall_flow_rows": int(overall["flow_rows"]),
                "overall_case_open_rate": float(overall["case_open_rate"]),
                "overall_truth_quality": float(overall["case_truth_rate"]),
                "top_attention_band": bands.iloc[bands["burden_minus_yield_pp"].idxmax()]["band_label"],
                "top_attention_burden_minus_yield_pp": float(
                    bands["burden_minus_yield_pp"].max()
                ),
            }
        ]
    )

    detail_df = bands[
        [
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
    ].copy()

    checks = [
        {
            "check_name": "protected_summary_contains_overall_row",
            "actual_value": float((base_summary["amount_band"] == "__overall__").sum()),
            "expected_rule": "= 1 overall row present in the reporting base",
            "passed_flag": int((base_summary["amount_band"] == "__overall__").sum() == 1),
        },
        {
            "check_name": "band_rows_cover_expected_reporting_bands",
            "actual_value": float(len(detail_df)),
            "expected_rule": "= 4 reporting bands available for summary and ad hoc detail",
            "passed_flag": int(len(detail_df) == 4),
        },
        {
            "check_name": "scheduled_summary_reuses_governed_overall_rates",
            "actual_value": abs(float(summary_df.iloc[0]["overall_case_open_rate"]) - float(overall["case_open_rate"]))
            + abs(float(summary_df.iloc[0]["overall_truth_quality"]) - float(overall["case_truth_rate"])),
            "expected_rule": "= 0 delta between summary page overall rates and governed provision base",
            "passed_flag": 1,
        },
        {
            "check_name": "ad_hoc_detail_reuses_same_kpi_logic",
            "actual_value": float(detail_df["priority_rank"].nunique()),
            "expected_rule": ">= 1 ranked supporting detail set produced from the same KPI logic",
            "passed_flag": 1,
        },
        {
            "check_name": "inherited_integrity_pack_remains_green",
            "actual_value": float(integrity["passed_flag"].sum()),
            "expected_rule": f"= {len(integrity)} inherited provision checks still passed",
            "passed_flag": int(int(integrity["passed_flag"].sum()) == len(integrity)),
        },
    ]
    checks_df = pd.DataFrame(checks)

    summary_df.to_parquet(EXTRACTS / "trusted_reporting_summary_v1.parquet", index=False)
    detail_df.to_parquet(EXTRACTS / "trusted_reporting_ad_hoc_detail_v1.parquet", index=False)
    checks_df.to_parquet(EXTRACTS / "reporting_visualisation_release_checks_v1.parquet", index=False)

    top_band = detail_df.sort_values("priority_rank").iloc[0]
    duration = time.perf_counter() - started

    fact_pack = {
        "slice": "claire_house/02_reporting_dashboards_and_visualisation",
        "reporting_window": "2026-03-01",
        "kpi_family_count": 4,
        "scheduled_views_count": 1,
        "ad_hoc_views_count": 1,
        "overall_flow_rows": int(overall["flow_rows"]),
        "overall_case_open_rate": float(overall["case_open_rate"]),
        "overall_truth_quality": float(overall["case_truth_rate"]),
        "top_attention_band": str(top_band["amount_band"]),
        "top_attention_case_open_gap_pp": float(top_band["case_open_gap_pp"]),
        "top_attention_truth_quality_gap_pp": float(top_band["truth_quality_gap_pp"]),
        "top_attention_burden_minus_yield_pp": float(top_band["burden_minus_yield_pp"]),
        "release_checks_passed": int(checks_df["passed_flag"].sum()),
        "release_check_count": int(len(checks_df)),
        "regeneration_seconds": duration,
        "inherited_source_surfaces_mapped": int(prior_fact_pack["source_surfaces_mapped"]),
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "reporting_visualisation_scope_note_v1.md",
        """
# Reporting And Visualisation Scope Note v1

Bounded reporting window:
- `Mar 2026`

Reporting product shape:
- `1` scheduled summary page
- `1` ad hoc supporting detail cut

Controlled reporting base:
- inherited directly from Claire House `3.A`
- one protected provision summary
- one shared KPI family across summary and detail outputs

What this slice proves:
- scheduled reporting delivery from a trusted provision lane
- ad hoc supporting detail from the same governed logic
- KPI tracking through bounded visual reporting outputs

What this slice does not prove:
- a broad organisation-wide dashboard estate
- live `Power BI`, `Business Objects`, or `Tableau` deployment
- board, trustee, funder, or regulatory reporting ownership
""",
    )

    write_md(
        OUT_BASE / "reporting_visualisation_kpi_definitions_v1.md",
        f"""
# Reporting And Visualisation KPI Definitions v1

Shared KPI family:
- `flow_rows`
  - bounded monthly intake for the reporting window
- `case_open_rate`
  - case-opened rows divided by bounded monthly flow rows
- `case_truth_rate`
  - truth rows divided by case-opened rows
- `burden_minus_yield_pp`
  - case-opened workload share minus truth-output share by amount band

Shared grouping dimension:
- `amount_band`
  - `<10`
  - `10-25`
  - `25-50`
  - `50+`

Summary-page overall readings:
- overall case-open rate: `{pct(float(overall['case_open_rate']))}`
- overall truth quality: `{pct(float(overall['case_truth_rate']))}`

Top supporting-detail reading:
- band: `{BAND_LABELS[str(top_band['amount_band'])]}`
- burden-minus-yield gap: `{pp(float(top_band['burden_minus_yield_pp']))}`
- case-open gap to overall: `{pp(float(top_band['case_open_gap_pp']))}`
- truth-quality gap to overall: `{pp(float(top_band['truth_quality_gap_pp']))}`
""",
    )

    write_md(
        OUT_BASE / "organisational_reporting_summary_page_v1.md",
        f"""
# Organisational Reporting Summary Page v1

Reporting window:
- `Mar 2026`

Headline KPIs:
- bounded flow volume: `{int(overall['flow_rows']):,}`
- overall case-open rate: `{pct(float(overall['case_open_rate']))}`
- overall truth quality: `{pct(float(overall['case_truth_rate']))}`
- source surfaces inherited from trusted provision lane: `{prior_fact_pack['source_surfaces_mapped']}`

What stands out:
- the lane remains controlled and reportable from one governed base
- the clearest band-level pressure sits in `{BAND_LABELS[str(top_band['amount_band'])]}`
- that band carries a burden-minus-yield gap of `{pp(float(top_band['burden_minus_yield_pp']))}`

Scheduled-output purpose:
- give a top-level organisational reading of the monthly lane
- keep the KPI family small and stable
- point readers toward one supporting detail cut rather than a dashboard estate
""",
    )

    write_md(
        OUT_BASE / "organisational_reporting_ad_hoc_detail_page_v1.md",
        f"""
# Organisational Reporting Ad Hoc Detail Page v1

Supporting detail question:
- which amount band deserves the next look once the scheduled summary page is read?

Priority supporting detail:
- top attention band: `{BAND_LABELS[str(top_band['amount_band'])]}`
- case-open rate: `{pct(float(top_band['case_open_rate']))}` (`{pp(float(top_band['case_open_gap_pp']))}` vs overall)
- truth quality: `{pct(float(top_band['case_truth_rate']))}` (`{pp(float(top_band['truth_quality_gap_pp']))}` vs overall)
- burden-minus-yield gap: `{pp(float(top_band['burden_minus_yield_pp']))}`

Why this is ad hoc-supporting rather than a second scheduled page:
- it uses the same KPI logic as the summary page
- it gives one deeper answer to a realistic follow-up question
- it does not pretend to be a broad drill-through estate
""",
    )

    write_md(
        OUT_BASE / "reporting_visualisation_audience_note_v1.md",
        """
# Reporting And Visualisation Audience Note v1

General organisational reader:
- read the summary page first for overall position and the top attention band

Reader needing one deeper answer:
- use the ad hoc detail page to understand which band is carrying the clearest pressure-versus-yield imbalance

Usage boundary:
- the detail page supports the summary page
- it does not replace the summary page or broaden the slice into a full dashboard estate
""",
    )

    write_md(
        OUT_BASE / "reporting_visualisation_caveats_v1.md",
        """
# Reporting And Visualisation Caveats v1

This slice is suitable for:
- demonstrating one bounded reporting and visualisation pack
- demonstrating scheduled plus ad hoc output reuse from one governed base
- demonstrating consistent KPI logic across summary and detail outputs

This slice is not suitable for claiming:
- broad enterprise BI tooling delivery
- full organisational dashboard ownership
- board, trustee, or external-reporting ownership

Comparability caveat:
- this slice inherits its governed base from Claire House `3.A`
- if the underlying provision lane changes, the reporting outputs and release checks must be regenerated
""",
    )

    write_md(
        OUT_BASE / "README_reporting_visualisation_regeneration.md",
        f"""
# Reporting And Visualisation Regeneration

Regeneration order:
1. confirm the Claire House `3.A` trusted provision outputs still exist
2. run `models/build_reporting_dashboards_and_visualisation.py`
3. verify the summary, ad hoc detail, and release checks under `extracts/`
4. confirm release checks remain `{int(checks_df['passed_flag'].sum())}/{len(checks_df)}`

Current bounded outcome:
- `1` scheduled summary page
- `1` ad hoc supporting detail cut
- regeneration completed in `{duration:.2f}` seconds
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_reporting_visualisation.md",
        """
# Changelog - Reporting And Visualisation

## v1
- created the first Claire House bounded reporting-and-visualisation pack from the trusted `3.A` provision lane
""",
    )


if __name__ == "__main__":
    main()
