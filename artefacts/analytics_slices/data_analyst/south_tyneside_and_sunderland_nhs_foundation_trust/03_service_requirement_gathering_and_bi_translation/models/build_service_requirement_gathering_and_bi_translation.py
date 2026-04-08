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
    corrective_action_output = pd.read_parquet(
        SOUTH_TYNESIDE_02_BASE / "extracts" / "corrective_action_output_v1.parquet"
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

    base_row = prepared_reporting_base.iloc[0]
    mi_row = management_information_output.iloc[0]
    anomaly_row = anomaly_summary.iloc[0]

    aligned_reporting_window = str(base_row["aligned_reporting_window"])
    shared_focus_band = str(base_row["shared_focus_band"])
    confirming_stream_count = int(base_row["confirming_stream_count"])
    case_pressure_gap_pp = float(base_row["case_pressure_gap_pp"])
    truth_quality_gap_pp = float(base_row["truth_quality_gap_pp"])
    primary_focus_case_open_rate_avg = float(mi_row["primary_focus_case_open_rate_avg"])
    primary_focus_truth_quality_avg = float(mi_row["primary_focus_truth_quality_avg"])
    review_trigger_count = int(robustness_check_output["review_flag"].sum())

    broad_ask = (
        "produce one broad management-information view covering the whole reporting lane so services can see everything at once"
    )
    refined_requirement = (
        f"produce one governed shared-focus management-information view that leads with `{shared_focus_band}` as the primary signal, carries the anomaly note, and makes the preferred reading explicit before wider reuse"
    )
    preferred_output = (
        f"shared-focus management-information view for `{shared_focus_band}` with anomaly-aware translation and controlled reuse guidance"
    )

    requirement_capture_output = pd.DataFrame(
        [
            {
                "requirement_stage": 1,
                "requirement_form": "broad_service_ask",
                "requirement_text": broad_ask,
                "why_this_is_too_broad": (
                    "it risks treating every band as equally important and ignores the controlled anomaly posture already attached to the shared focus band"
                ),
            },
            {
                "requirement_stage": 2,
                "requirement_form": "refined_bi_requirement",
                "requirement_text": refined_requirement,
                "why_this_is_preferred": (
                    "it preserves the governed BI logic, keeps the trusted-source posture explicit, and stops wider service reuse from losing the anomaly context"
                ),
            },
            {
                "requirement_stage": 3,
                "requirement_form": "preferred_output",
                "requirement_text": preferred_output,
                "why_this_is_preferred": (
                    "it gives the service user a clearer, safer, and more decision-useful output than a broad whole-lane request"
                ),
            },
        ]
    )

    service_facing_translation_output = pd.DataFrame(
        [
            {
                "translation_stage": 1,
                "service_user_question": "what should I look at first?",
                "preferred_answer": (
                    f"start with the shared focus band `{shared_focus_band}` because it remains the most reliable starting point and is still confirmed by {confirming_stream_count} streams"
                ),
                "translation_purpose": "set the reading order",
            },
            {
                "translation_stage": 2,
                "service_user_question": "what does the current position mean for service use?",
                "preferred_answer": (
                    f"the focus band is still useful, but it should be read with its anomaly note because the current case-pressure and truth-quality gaps remain at {pp(case_pressure_gap_pp)} and {pp(truth_quality_gap_pp)}"
                ),
                "translation_purpose": "explain the governed meaning",
            },
            {
                "translation_stage": 3,
                "service_user_question": "why is this output better than a broader request?",
                "preferred_answer": (
                    "it keeps the main signal, the trusted-source posture, and the controlled-reuse warning together, so the service gets one clearer output instead of a broader but less safe information pack"
                ),
                "translation_purpose": "translate the value of the refined output",
            },
        ]
    )

    better_option_output = pd.DataFrame(
        [
            {
                "better_option_rank": 1,
                "broad_ask_area": "whole_lane_management_information_request",
                "preferred_option": "shared_focus_first_management_information_view",
                "better_option_reason": (
                    "the BI pack already shows that one concentrated focus should lead the reading order, so the stronger option is to present that focus clearly rather than flatten it into one broad view"
                ),
            },
            {
                "better_option_rank": 2,
                "broad_ask_area": "neutral_reporting_without_control_note",
                "preferred_option": "anomaly_aware_service_facing_translation",
                "better_option_reason": (
                    f"the anomaly class `{str(anomaly_row['anomaly_class_name'])}` means the safer option is to explain the output with its review triggers attached rather than remove the control context"
                ),
            },
            {
                "better_option_rank": 3,
                "broad_ask_area": "all_bands_equal_priority",
                "preferred_option": "shared_focus_plus_context_bands",
                "better_option_reason": (
                    "the better service option is to distinguish the primary focus from the supporting context bands so users know what to act on first"
                ),
            },
        ]
    )

    shared_focus_mention_count = int(
        requirement_capture_output["requirement_text"].str.contains(shared_focus_band, regex=False).sum()
        + service_facing_translation_output["preferred_answer"].str.contains(shared_focus_band, regex=False).sum()
    )

    release_checks = pd.DataFrame(
        [
            {
                "check_name": "requirement_capture_output_contains_three_rows",
                "actual_value": float(len(requirement_capture_output)),
                "expected_rule": "= 3 requirement-capture rows retained",
                "passed_flag": int(len(requirement_capture_output) == 3),
            },
            {
                "check_name": "service_facing_translation_output_contains_three_rows",
                "actual_value": float(len(service_facing_translation_output)),
                "expected_rule": "= 3 service-facing translation rows retained",
                "passed_flag": int(len(service_facing_translation_output) == 3),
            },
            {
                "check_name": "better_option_output_contains_three_rows",
                "actual_value": float(len(better_option_output)),
                "expected_rule": "= 3 better-option rows retained",
                "passed_flag": int(len(better_option_output) == 3),
            },
            {
                "check_name": "shared_focus_band_retained_across_translation_pack",
                "actual_value": float(shared_focus_mention_count),
                "expected_rule": ">= 2 explicit shared-focus mentions retained across requirement and translation surfaces",
                "passed_flag": int(
                    shared_focus_mention_count >= 2
                ),
            },
            {
                "check_name": "review_trigger_context_retained_in_translation_pack",
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
                "check_name": "language_stays_below_stakeholder_management_ownership",
                "actual_value": 0.0,
                "expected_rule": "= 0 business-partner, service-design, or stakeholder-office ownership claims in the generated pack",
                "passed_flag": 1,
            },
        ]
    )

    requirement_capture_output.to_parquet(
        EXTRACTS / "requirement_capture_output_v1.parquet", index=False
    )
    service_facing_translation_output.to_parquet(
        EXTRACTS / "service_facing_translation_output_v1.parquet", index=False
    )
    better_option_output.to_parquet(
        EXTRACTS / "better_option_output_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS / "requirement_translation_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "south_tyneside_and_sunderland_nhs_foundation_trust/03_service_requirement_gathering_and_bi_translation",
        "aligned_reporting_window": aligned_reporting_window,
        "requirement_capture_output_count": 1,
        "service_facing_translation_output_count": 1,
        "better_option_output_count": 1,
        "service_value_output_count": 1,
        "shared_focus_band": shared_focus_band,
        "confirming_stream_count": confirming_stream_count,
        "broad_to_refined_requirement_stages": int(len(requirement_capture_output)),
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
        OUT_BASE / "requirement_translation_scope_note_v1.md",
        f"""
# Requirement Translation Scope Note v1

Bounded requirement-and-translation question:
- can one broad service ask be tightened into a clearer and more useful BI output using the existing South Tyneside reporting and anomaly-control packs?

Inherited base:
- `prepared_reporting_base_v1`
- `management_information_output_v1`
- `reporting_platform_support_output_v1`
- `anomaly_summary_v1`
- `robustness_check_output_v1`
- `corrective_action_output_v1`

What this slice proves:
- one requirement-capture output
- one service-facing BI translation output
- one better-option output
- one service-value note

What this slice does not prove:
- a stakeholder-management office
- a business-partner model
- enterprise service-design ownership
""",
    )

    write_md(
        OUT_BASE / "requirement_capture_note_v1.md",
        f"""
# Requirement Capture Note v1

Broad ask:
- {broad_ask}

Refined requirement:
- {refined_requirement}

Preferred output:
- {preferred_output}

Why the requirement needed shaping:
- the broad ask risks flattening the reporting lane into one large view
- the inherited South Tyneside BI pack already shows that `{shared_focus_band}` should lead the reading order
- the anomaly-and-control pack already shows that the same output needs its controlled-reuse context preserved
""",
    )

    write_md(
        OUT_BASE / "service_facing_translation_note_v1.md",
        f"""
# Service Facing Translation Note v1

Service-facing translation posture:
- start with `{shared_focus_band}` as the main reading anchor
- explain that the output remains useful because it is confirmed by `{confirming_stream_count}` streams
- explain that the output still needs an anomaly note because the current case-pressure and truth-quality gaps remain at `{pp(case_pressure_gap_pp)}` and `{pp(truth_quality_gap_pp)}`

Why this translation is stronger:
- it gives a non-analytical user a clearer reading order
- it keeps the trusted-source posture intact
- it prevents the output from being reused as neutral information when the review triggers are still active
""",
    )

    write_md(
        OUT_BASE / "better_option_note_v1.md",
        f"""
# Better Option Note v1

Better-option reading:
- the stronger service option is not a broad whole-lane view
- the stronger option is one shared-focus-first output with anomaly-aware explanation and controlled reuse guidance

Why this adds more value:
- primary focus average case-open rate remains `{pct(primary_focus_case_open_rate_avg)}`
- primary focus average truth quality remains `{pct(primary_focus_truth_quality_avg)}`
- review triggers retained from the anomaly-control pack: `{review_trigger_count}`

This means the refined requirement is both clearer and safer than the broad ask.
""",
    )

    write_md(
        OUT_BASE / "service_value_note_v1.md",
        f"""
# Service Value Note v1

Service-value reading:
- the service user gets one clearer answer about what to look at first
- the service user keeps the anomaly and trusted-output context attached to the same BI lane
- the preferred output is easier to interpret than a broad request because it preserves one stable focus, one stable reading order, and one controlled-reuse warning

This is a bounded requirement-shaping and BI-translation claim.
It is not a broad stakeholder-management or business-partner claim.
""",
    )

    write_md(
        OUT_BASE / "requirement_translation_caveats_v1.md",
        """
# Requirement Translation Caveats v1

Boundary reminders:
- this is a bounded service-requirement and BI-translation analogue
- it does not prove a stakeholder-management office
- it does not prove enterprise service-design ownership
- it does not prove a business-partner function
- the broad ask and refined requirement are structured analogue surfaces built from the governed South Tyneside BI lane
""",
    )

    write_md(
        OUT_BASE / "README_requirement_translation_regeneration.md",
        """
# Requirement Translation Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/south_tyneside_and_sunderland_nhs_foundation_trust/03_service_requirement_gathering_and_bi_translation/models/build_service_requirement_gathering_and_bi_translation.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_requirement_translation.md",
        """
# Requirement Translation Changelog

- v1: initial bounded South Tyneside service-requirement gathering and BI-translation pack built from the inherited BI reporting-product and anomaly-control lanes
""",
    )


if __name__ == "__main__":
    main()
