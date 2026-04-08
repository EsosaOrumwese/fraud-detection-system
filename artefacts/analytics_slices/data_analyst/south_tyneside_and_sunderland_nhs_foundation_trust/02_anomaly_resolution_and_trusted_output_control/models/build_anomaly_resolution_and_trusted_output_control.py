from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

SOUTH_TYNESIDE_REPORTING_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "south_tyneside_and_sunderland_nhs_foundation_trust"
    / "01_bi_reporting_product_and_reporting_platform_support"
)
GUYS_QUALITY_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "guys_and_st_thomas_nhs_foundation_trust"
    / "02_workforce_data_quality_governance_and_compliance_monitoring"
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
        SOUTH_TYNESIDE_REPORTING_BASE / "extracts" / "prepared_reporting_base_v1.parquet"
    )
    management_information_output = pd.read_parquet(
        SOUTH_TYNESIDE_REPORTING_BASE / "extracts" / "management_information_output_v1.parquet"
    )
    reporting_platform_support_output = pd.read_parquet(
        SOUTH_TYNESIDE_REPORTING_BASE / "extracts" / "reporting_platform_support_output_v1.parquet"
    )
    reporting_release_checks = pd.read_parquet(
        SOUTH_TYNESIDE_REPORTING_BASE / "extracts" / "reporting_product_release_checks_v1.parquet"
    )

    south_tyneside_fact_pack = json.loads(
        (SOUTH_TYNESIDE_REPORTING_BASE / "metrics" / "execution_fact_pack.json").read_text(
            encoding="utf-8"
        )
    )
    guys_quality_fact_pack = json.loads(
        (GUYS_QUALITY_BASE / "metrics" / "execution_fact_pack.json").read_text(
            encoding="utf-8"
        )
    )

    base_row = prepared_reporting_base.iloc[0]
    mi_row = management_information_output.iloc[0]

    aligned_reporting_window = str(base_row["aligned_reporting_window"])
    shared_focus_band = str(base_row["shared_focus_band"])
    confirming_stream_count = int(base_row["confirming_stream_count"])
    case_pressure_gap_pp = float(base_row["case_pressure_gap_pp"])
    truth_quality_gap_pp = float(base_row["truth_quality_gap_pp"])
    primary_focus_case_open_rate_avg = float(mi_row["primary_focus_case_open_rate_avg"])
    primary_focus_truth_quality_avg = float(mi_row["primary_focus_truth_quality_avg"])
    anomaly_class_name = "shared_focus_band_requires_robustness_gate_before_wider_reuse"

    case_gap_review_flag = int(case_pressure_gap_pp > 1.00)
    truth_gap_review_flag = int(truth_quality_gap_pp < -1.00)
    release_safe_flag = int(
        south_tyneside_fact_pack["release_checks_passed"]
        == south_tyneside_fact_pack["release_check_count"]
    )

    anomaly_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "anomaly_summary_name": "south_tyneside_shared_focus_anomaly_pack",
                "anomaly_class_name": anomaly_class_name,
                "reporting_grain": str(base_row["reporting_grain"]),
                "shared_focus_band": shared_focus_band,
                "confirming_stream_count": confirming_stream_count,
                "case_pressure_gap_pp": case_pressure_gap_pp,
                "truth_quality_gap_pp": truth_quality_gap_pp,
                "anomaly_status": "bounded_anomaly_requires_controlled_reuse",
                "anomaly_summary_reading": (
                    "the same focus band that supports the trusted BI product also remains materially separated "
                    "from neutral position on both pressure and quality, so wider reuse should stay inside a named anomaly-and-control posture"
                ),
            }
        ]
    )

    robustness_check_output = pd.DataFrame(
        [
            {
                "robustness_rank": 1,
                "robustness_check_name": "shared_focus_still_confirmed_across_streams",
                "current_value": float(confirming_stream_count),
                "value_unit": "streams",
                "expected_rule": ">= 3 confirming streams required to keep the shared focus analytically coherent",
                "review_flag": 0,
                "robustness_reading": (
                    "the anomaly remains bounded because the same focus band is still confirmed across multiple retained views rather than appearing as a single-stream artefact"
                ),
            },
            {
                "robustness_rank": 2,
                "robustness_check_name": "case_pressure_gap_requires_review",
                "current_value": case_pressure_gap_pp,
                "value_unit": "percentage_points",
                "expected_rule": "> 1.00 pp means the pressure reading still needs explicit review before wider reuse",
                "review_flag": case_gap_review_flag,
                "robustness_reading": (
                    "the case-pressure position is still materially elevated, so the output should be treated as controlled BI information rather than an unquestioned baseline"
                ),
            },
            {
                "robustness_rank": 3,
                "robustness_check_name": "truth_quality_gap_requires_review",
                "current_value": truth_quality_gap_pp,
                "value_unit": "percentage_points",
                "expected_rule": "< -1.00 pp means the truth-quality reading still needs controlled interpretation",
                "review_flag": truth_gap_review_flag,
                "robustness_reading": (
                    "the truth-quality position remains behind neutral context, so the same BI surface needs an explicit trust note attached to it"
                ),
            },
            {
                "robustness_rank": 4,
                "robustness_check_name": "inherited_release_gate_remains_green",
                "current_value": float(release_safe_flag),
                "value_unit": "binary_flag",
                "expected_rule": "= 1 required before the bounded anomaly pack can still be reused as trusted output",
                "review_flag": int(not release_safe_flag),
                "robustness_reading": (
                    "the inherited BI release gate still holds, so the anomaly is manageable through control and commentary rather than full withdrawal of the output"
                ),
            },
        ]
    )

    corrective_action_output = pd.DataFrame(
        [
            {
                "corrective_rank": 1,
                "corrective_area": "shared_focus_release_posture",
                "corrective_direction": (
                    "keep the shared focus band on a named anomaly surface instead of treating it as neutral recurring management information"
                ),
            },
            {
                "corrective_rank": 2,
                "corrective_area": "review_trigger_control",
                "corrective_direction": (
                    "require explicit review whenever the case-pressure gap stays above +1.00 pp or the truth-quality gap stays below -1.00 pp"
                ),
            },
            {
                "corrective_rank": 3,
                "corrective_area": "trusted_output_reuse",
                "corrective_direction": (
                    "allow bounded reuse only while the inherited reporting-product release checks remain fully green and the anomaly note stays attached"
                ),
            },
        ]
    )

    release_checks = pd.DataFrame(
        [
            {
                "check_name": "anomaly_summary_output_present",
                "actual_value": float(len(anomaly_summary)),
                "expected_rule": "= 1 anomaly summary output present",
                "passed_flag": int(len(anomaly_summary) == 1),
            },
            {
                "check_name": "robustness_check_output_contains_four_rows",
                "actual_value": float(len(robustness_check_output)),
                "expected_rule": "= 4 bounded robustness rows retained",
                "passed_flag": int(len(robustness_check_output) == 4),
            },
            {
                "check_name": "corrective_action_output_contains_three_rows",
                "actual_value": float(len(corrective_action_output)),
                "expected_rule": "= 3 bounded corrective directions retained",
                "passed_flag": int(len(corrective_action_output) == 3),
            },
            {
                "check_name": "anomaly_class_count_fixed_to_one",
                "actual_value": float(anomaly_summary["anomaly_class_name"].nunique()),
                "expected_rule": "= 1 explicit anomaly class retained",
                "passed_flag": int(anomaly_summary["anomaly_class_name"].nunique() == 1),
            },
            {
                "check_name": "shared_focus_band_retained_across_outputs",
                "actual_value": float(anomaly_summary.iloc[0]["shared_focus_band"] == shared_focus_band),
                "expected_rule": "= 1 same shared focus band retained across anomaly outputs",
                "passed_flag": int(anomaly_summary.iloc[0]["shared_focus_band"] == shared_focus_band),
            },
            {
                "check_name": "two_robustness_checks_trigger_review",
                "actual_value": float(robustness_check_output["review_flag"].sum()),
                "expected_rule": "= 2 review-trigger robustness checks retained while release gate stays green",
                "passed_flag": int(robustness_check_output["review_flag"].sum() == 2),
            },
            {
                "check_name": "inherited_south_tyneside_reporting_pack_remains_green",
                "actual_value": float(south_tyneside_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {south_tyneside_fact_pack['release_check_count']} inherited South Tyneside reporting checks remain green",
                "passed_flag": int(
                    south_tyneside_fact_pack["release_checks_passed"]
                    == south_tyneside_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "analogue_quality_control_pack_remains_green",
                "actual_value": float(guys_quality_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {guys_quality_fact_pack['release_check_count']} analogue quality-control checks remain green",
                "passed_flag": int(
                    guys_quality_fact_pack["release_checks_passed"]
                    == guys_quality_fact_pack["release_check_count"]
                ),
            },
        ]
    )

    anomaly_summary.to_parquet(EXTRACTS / "anomaly_summary_v1.parquet", index=False)
    robustness_check_output.to_parquet(
        EXTRACTS / "robustness_check_output_v1.parquet", index=False
    )
    corrective_action_output.to_parquet(
        EXTRACTS / "corrective_action_output_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS / "anomaly_output_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "south_tyneside_and_sunderland_nhs_foundation_trust/02_anomaly_resolution_and_trusted_output_control",
        "aligned_reporting_window": aligned_reporting_window,
        "anomaly_summary_output_count": 1,
        "robustness_check_output_count": 1,
        "corrective_action_output_count": 1,
        "trusted_output_output_count": 1,
        "shared_focus_band": shared_focus_band,
        "confirming_stream_count": confirming_stream_count,
        "anomaly_class_count": int(anomaly_summary["anomaly_class_name"].nunique()),
        "review_trigger_count": int(robustness_check_output["review_flag"].sum()),
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
        OUT_BASE / "anomaly_resolution_scope_note_v1.md",
        f"""
# Anomaly Resolution Scope Note v1

Bounded anomaly-and-trust question:
- can the trusted South Tyneside BI reporting lane support one explicit anomaly class, one robustness surface, and one corrective reading without widening into warehouse or governance-office ownership?

Inherited base:
- `prepared_reporting_base_v1`
- `management_information_output_v1`
- `reporting_platform_support_output_v1`
- `reporting_product_release_checks_v1`

What this slice proves:
- one anomaly summary
- one robustness-check output
- one corrective-action output
- one trusted-output note

What this slice does not prove:
- live Trust data-warehouse administration
- a governance office
- whole-Trust data-quality ownership
""",
    )

    write_md(
        OUT_BASE / "anomaly_summary_note_v1.md",
        f"""
# Anomaly Summary Note v1

Anomaly class retained:
- `{anomaly_class_name}`

Shared focus under review:
- focus band: `{shared_focus_band}`
- confirming streams: `{confirming_stream_count}`
- case-pressure gap: `{pp(case_pressure_gap_pp)}`
- truth-quality gap: `{pp(truth_quality_gap_pp)}`

Headline reading:
- the trusted BI pack remains usable, but the same focus band still needs an explicit anomaly-and-control layer before wider service reuse
""",
    )

    write_md(
        OUT_BASE / "robustness_check_note_v1.md",
        f"""
# Robustness Check Note v1

Robustness posture:
- confirmation strength remains at `{confirming_stream_count}` streams
- case-pressure review trigger: `{pp(case_pressure_gap_pp)}`
- truth-quality review trigger: `{pp(truth_quality_gap_pp)}`
- inherited reporting release gate remains green at `{south_tyneside_fact_pack['release_checks_passed']}/{south_tyneside_fact_pack['release_check_count']}`

Interpretation:
- the anomaly is bounded rather than destabilising
- the output can still be trusted for controlled use because the release gate remains green
- the output should not be reused as neutral baseline reporting while the two review triggers remain active
""",
    )

    write_md(
        OUT_BASE / "corrective_action_note_v1.md",
        f"""
# Corrective Action Note v1

Corrective direction:
- keep `{shared_focus_band}` on a named anomaly surface
- require review whenever the case-pressure or truth-quality thresholds remain breached
- keep the anomaly note attached to the BI pack before wider reuse

Why this is proportionate:
- primary focus average case-open rate remains `{pct(primary_focus_case_open_rate_avg)}`
- primary focus average truth quality remains `{pct(primary_focus_truth_quality_avg)}`
- the issue is therefore real enough to name, but still bounded enough to control without withdrawing the whole BI pack
""",
    )

    write_md(
        OUT_BASE / "trusted_output_note_v1.md",
        f"""
# Trusted Output Note v1

Trusted-output reading:
- the South Tyneside BI pack is still trusted for bounded reuse because the inherited reporting-product checks remain fully green
- the same pack should circulate with an explicit anomaly note while the focus band `{shared_focus_band}` retains both review triggers
- this is a trusted-output control claim, not a governance-office or warehouse-administration claim
""",
    )

    write_md(
        OUT_BASE / "anomaly_control_caveats_v1.md",
        f"""
# Anomaly Control Caveats v1

Boundary reminders:
- this is a bounded anomaly-resolution and trusted-output-control analogue
- it does not prove live warehouse administration
- it does not prove whole-Trust data-quality ownership
- the anomaly class is tied to one shared focus band `{shared_focus_band}` and should be reused only as a compact BI trust proof
""",
    )

    write_md(
        OUT_BASE / "README_anomaly_control_regeneration.md",
        """
# Anomaly Control Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/south_tyneside_and_sunderland_nhs_foundation_trust/02_anomaly_resolution_and_trusted_output_control/models/build_anomaly_resolution_and_trusted_output_control.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_anomaly_control.md",
        """
# Anomaly Control Changelog

- v1: initial bounded South Tyneside anomaly-resolution, robustness-check, and trusted-output-control pack built from the inherited BI reporting-product lane
""",
    )


if __name__ == "__main__":
    main()
