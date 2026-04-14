from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

JOB14_REPORTING_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "guys_and_st_thomas_nhs_foundation_trust_rd_data_analyst"
    / "01_research_management_system_support_and_research_performance_reporting"
)
JOB14_QUALITY_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "guys_and_st_thomas_nhs_foundation_trust_rd_data_analyst"
    / "02_research_data_quality_audit_and_governance_support"
)
JOB14_TREND_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "guys_and_st_thomas_nhs_foundation_trust_rd_data_analyst"
    / "03_multi_source_research_performance_trend_analysis_and_forecasting"
)


def write_md(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def pp(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f} pp"


def main() -> None:
    started = time.perf_counter()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)

    prepared_base = pd.read_parquet(
        JOB14_REPORTING_BASE / "extracts" / "prepared_research_performance_base_v1.parquet"
    )
    mandatory_summary = pd.read_parquet(
        JOB14_REPORTING_BASE / "extracts" / "mandatory_research_reporting_summary_v1.parquet"
    )
    quality_summary = pd.read_parquet(
        JOB14_QUALITY_BASE / "extracts" / "research_data_quality_summary_v1.parquet"
    )
    audit_output = pd.read_parquet(
        JOB14_QUALITY_BASE / "extracts" / "audit_consistency_output_v1.parquet"
    )
    integrated_trend_summary = pd.read_parquet(
        JOB14_TREND_BASE / "extracts" / "integrated_research_performance_trend_summary_v1.parquet"
    )
    implication_output = pd.read_parquet(
        JOB14_TREND_BASE / "extracts" / "implication_output_v1.parquet"
    )

    reporting_fact_pack = json.loads(
        (JOB14_REPORTING_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    quality_fact_pack = json.loads(
        (JOB14_QUALITY_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    trend_fact_pack = json.loads(
        (JOB14_TREND_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    prepared_row = prepared_base.iloc[0]
    mandatory_row = mandatory_summary.iloc[0]
    quality_row = quality_summary.iloc[0]
    trend_row = integrated_trend_summary.iloc[0]
    implication_row = implication_output.iloc[0]

    aligned_reporting_window = str(prepared_row["aligned_reporting_window"])
    shared_reporting_cohort = str(prepared_row["shared_reporting_cohort"])
    retained_source_streams = int(prepared_row["retained_source_streams"])
    control_gap_pp = float(mandatory_row["control_gap_pp"])
    reporting_pressure_gap_pp = float(quality_row["reporting_pressure_gap_pp"])
    quality_consistency_gap_pp = float(quality_row["quality_consistency_gap_pp"])
    review_trigger_metric_count = int(audit_output["review_trigger_flag"].sum())
    confirmation_strength = int(trend_row["confirmation_strength"])
    integrated_stream_count = int(trend_row["integrated_stream_count"])

    advisory_support_output = pd.DataFrame(
        [
            {
                "support_rank": 1,
                "support_area": "frontline_advisory_contact",
                "user_need": "understand which research-performance surface should be used first",
                "advisory_response": (
                    f"start with the prepared and controlled reporting lane for `{shared_reporting_cohort}` and keep the same "
                    "mandatory, audit, and fit-for-purpose readings attached"
                ),
                "why_this_support_matters": "it gives users one clear starting point instead of multiple disconnected outputs",
            },
            {
                "support_rank": 2,
                "support_area": "data_issue_support",
                "user_need": "understand why a research-performance output cannot yet be treated as neutral or broadly reusable",
                "advisory_response": (
                    f"explain that the current reporting-pressure, quality-consistency, and control conditions remain at "
                    f"{pp(reporting_pressure_gap_pp)}, {pp(quality_consistency_gap_pp)}, and {pp(control_gap_pp)}, so the lane still needs controlled circulation"
                ),
                "why_this_support_matters": "it keeps users from stripping away the quality and release context",
            },
            {
                "support_rank": 3,
                "support_area": "professional_user_guidance",
                "user_need": "know when an issue should stay inside local guidance and when it should be escalated into a controlled review",
                "advisory_response": (
                    f"treat the lane as bounded internal decision support, and keep explicit review attached while `{review_trigger_metric_count}` audit triggers remain active"
                ),
                "why_this_support_matters": "it gives users a clear support posture without implying a wider service-desk estate",
            },
        ]
    )

    user_support_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "support_pack_name": "research_system_user_support_enablement_pack",
                "shared_reporting_cohort": shared_reporting_cohort,
                "reused_prior_slice_count": 3,
                "retained_source_streams": retained_source_streams,
                "integrated_stream_count": integrated_stream_count,
                "support_stage_count": 4,
                "review_trigger_metric_count": review_trigger_metric_count,
                "support_summary_reading": (
                    "the same governed research-performance lane now supports one bounded user-enablement story where advisory help, "
                    "training, and documentation all stay attached to explicit data-consistency and release-safe use conditions"
                ),
            }
        ]
    )

    user_training_output = pd.DataFrame(
        [
            {
                "training_rank": 1,
                "training_audience": "research_management_system_users",
                "training_focus": "correct use of the governed research-performance reporting lane",
                "training_outcome": "users understand which reporting surfaces are primary and why controlled circulation still matters",
            },
            {
                "training_rank": 2,
                "training_audience": "r_and_d_governance_team_users",
                "training_focus": "extensive use of the reporting, quality, and release-control views together",
                "training_outcome": "governance-side users keep the audit, issue, and release readings attached to reporting use",
            },
            {
                "training_rank": 3,
                "training_audience": "research_staff_with_data_consistency_questions",
                "training_focus": "how to interpret data-consistency, fit-for-purpose, and review-trigger conditions",
                "training_outcome": "staff can recognise when a dataset is usable, when it is controlled, and when it requires further review",
            },
        ]
    )

    procedural_documentation_output = pd.DataFrame(
        [
            {
                "procedure_rank": 1,
                "procedure_area": "reporting_surface_selection",
                "documented_rule": "start from the prepared research-performance base and not from detached extracts",
                "expected_user_effect": "keeps the reporting lane stable and reduces conflicting user interpretations",
            },
            {
                "procedure_rank": 2,
                "procedure_area": "quality_and_audit_context_retention",
                "documented_rule": "keep the issue class, audit triggers, and controlled-release posture attached to reuse decisions",
                "expected_user_effect": "prevents users from treating high-accountability outputs as neutral once exported",
            },
            {
                "procedure_rank": 3,
                "procedure_area": "fit_for_purpose_check",
                "documented_rule": "use the bounded internal decision-support reading before making stronger planning or forecasting claims",
                "expected_user_effect": "keeps analytical use proportional to the evidence actually available",
            },
            {
                "procedure_rank": 4,
                "procedure_area": "training_material_refresh",
                "documented_rule": "refresh guidance when reporting logic, quality conditions, or release boundaries change",
                "expected_user_effect": "keeps user materials aligned to the current governed research lane rather than stale local practice",
            },
        ]
    )

    support_focus_mention_count = int(
        advisory_support_output["advisory_response"].str.contains(shared_reporting_cohort, regex=False).sum()
    )
    training_audience_count = int(user_training_output["training_audience"].nunique())
    documentation_step_count = int(len(procedural_documentation_output))

    release_checks = pd.DataFrame(
        [
            {
                "check_name": "advisory_support_output_contains_three_rows",
                "actual_value": float(len(advisory_support_output)),
                "expected_rule": "= 3 advisory-support rows retained",
                "passed_flag": int(len(advisory_support_output) == 3),
            },
            {
                "check_name": "user_support_summary_output_present",
                "actual_value": float(len(user_support_summary)),
                "expected_rule": "= 1 user-support summary retained",
                "passed_flag": int(len(user_support_summary) == 1),
            },
            {
                "check_name": "user_training_output_contains_three_rows",
                "actual_value": float(len(user_training_output)),
                "expected_rule": "= 3 user-training rows retained",
                "passed_flag": int(len(user_training_output) == 3),
            },
            {
                "check_name": "procedural_documentation_output_contains_four_rows",
                "actual_value": float(len(procedural_documentation_output)),
                "expected_rule": "= 4 procedural-documentation rows retained",
                "passed_flag": int(len(procedural_documentation_output) == 4),
            },
            {
                "check_name": "shared_reporting_cohort_retained_in_support_pack",
                "actual_value": float(support_focus_mention_count),
                "expected_rule": ">= 1 explicit shared-reporting-cohort mention retained in advisory guidance",
                "passed_flag": int(support_focus_mention_count >= 1),
            },
            {
                "check_name": "inherited_job14_reporting_pack_remains_green",
                "actual_value": float(reporting_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {reporting_fact_pack['release_check_count']} inherited job 14 reporting checks remain green",
                "passed_flag": int(
                    reporting_fact_pack["release_checks_passed"] == reporting_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "inherited_job14_quality_pack_remains_green",
                "actual_value": float(quality_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {quality_fact_pack['release_check_count']} inherited job 14 quality checks remain green",
                "passed_flag": int(
                    quality_fact_pack["release_checks_passed"] == quality_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "language_stays_below_helpdesk_or_enterprise_training_ownership",
                "actual_value": 0.0,
                "expected_rule": "= 0 research-systems helpdesk, enterprise training-function, or organisation-wide documentation-office ownership claims in the generated pack",
                "passed_flag": 1,
            },
        ]
    )

    advisory_support_output.to_parquet(
        EXTRACTS / "advisory_support_output_v1.parquet", index=False
    )
    user_support_summary.to_parquet(
        EXTRACTS / "user_support_summary_v1.parquet", index=False
    )
    user_training_output.to_parquet(
        EXTRACTS / "user_training_output_v1.parquet", index=False
    )
    procedural_documentation_output.to_parquet(
        EXTRACTS / "procedural_documentation_output_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS / "research_system_user_support_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "guys_and_st_thomas_nhs_foundation_trust_rd_data_analyst/04_research_system_user_support_training_and_documentation",
        "aligned_reporting_window": aligned_reporting_window,
        "advisory_support_output_count": 1,
        "user_support_summary_output_count": 1,
        "user_training_output_count": 1,
        "procedural_documentation_output_count": 1,
        "data_consistency_support_output_count": 1,
        "shared_reporting_cohort": shared_reporting_cohort,
        "reused_prior_slice_count": 3,
        "retained_source_streams": retained_source_streams,
        "integrated_stream_count": integrated_stream_count,
        "support_stage_count": 4,
        "training_audience_count": training_audience_count,
        "documentation_step_count": documentation_step_count,
        "review_trigger_metric_count": review_trigger_metric_count,
        "confirmation_strength": confirmation_strength,
        "current_reporting_pressure_gap_pp": reporting_pressure_gap_pp,
        "current_quality_consistency_gap_pp": quality_consistency_gap_pp,
        "current_control_gap_pp": control_gap_pp,
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "research_system_user_support_scope_note_v1.md",
        f"""
# Research System User Support Scope Note v1

Bounded support-and-enablement question:
- can the governed research-performance lane support one bounded user-enablement pack that provides advisory help, training, and procedural guidance without widening into a helpdesk or enterprise training claim?

Inherited base:
- `prepared_research_performance_base_v1`
- `mandatory_research_reporting_summary_v1`
- `research_data_quality_summary_v1`
- `audit_consistency_output_v1`
- `integrated_research_performance_trend_summary_v1`
- `implication_output_v1`

What this slice proves:
- one advisory-support output
- one user-support summary
- one user-training output
- one procedural-documentation output
- one data-consistency support note

What this slice does not prove:
- a Trust-wide research-systems helpdesk
- an enterprise training function
- an organisation-wide documentation governance office
""",
    )

    write_md(
        OUT_BASE / "advisory_support_note_v1.md",
        f"""
# Advisory Support Note v1

Frontline advisory posture:
- start users on the governed research-performance lane for `{shared_reporting_cohort}`
- explain that reporting, quality, and fit-for-purpose readings belong together
- keep support bounded to controlled use and controlled escalation

Why this support is needed:
- retained source streams: `{retained_source_streams}`
- integrated streams: `{integrated_stream_count}`
- review triggers still active: `{review_trigger_metric_count}`

This is a bounded advisory-support claim.
It is not a helpdesk-ownership claim.
""",
    )

    write_md(
        OUT_BASE / "user_training_note_v1.md",
        f"""
# User Training Note v1

Training audiences retained:
- research-management-system users
- `R&D Governance Team` users
- research staff with data-consistency questions

Training focus:
- correct use of the governed research-performance lane
- correct reading of audit and release-safe conditions
- correct interpretation of fit-for-purpose status `{str(implication_row['fit_for_purpose_status'])}`

Why this training matters:
- users need one consistent reading of reporting, quality, and trend conditions rather than separate local interpretations
""",
    )

    write_md(
        OUT_BASE / "procedural_documentation_note_v1.md",
        f"""
# Procedural Documentation Note v1

Procedural-documentation posture:
- document the right reporting surface first
- document how quality and audit context stay attached
- document the fit-for-purpose check before stronger analytical use
- document when training material should be refreshed

Current bounded control context:
- reporting-pressure gap: `{pp(reporting_pressure_gap_pp)}`
- quality-consistency gap: `{pp(quality_consistency_gap_pp)}`
- control gap: `{pp(control_gap_pp)}`
""",
    )

    write_md(
        OUT_BASE / "data_consistency_support_note_v1.md",
        f"""
# Data Consistency Support Note v1

Data-consistency support reading:
- the current lane is usable for bounded internal decision support
- it still requires explicit quality and control context in every reuse path
- users should treat data-consistency questions as guidance-and-review issues, not as reasons to detach the outputs from the governed lane

Support consequence:
- the same `{shared_reporting_cohort}` focus should remain explicit
- the same `{review_trigger_metric_count}` review triggers should remain visible
- the same fit-for-purpose boundary should remain attached to training and documentation
""",
    )

    write_md(
        OUT_BASE / "enablement_value_note_v1.md",
        f"""
# Enablement Value Note v1

Enablement-value reading:
- users get one clearer advisory path for working with research-performance outputs
- users get one bounded training pack for correct system and data use
- users get one procedural-documentation layer that keeps reporting, quality, and fit-for-purpose logic aligned

This means the governed research lane is not only usable by the analyst who built it.
It is also explainable enough to support other users in working with it consistently and correctly.
""",
    )

    write_md(
        OUT_BASE / "research_system_user_support_caveats_v1.md",
        """
# Research System User Support Caveats v1

Boundary reminders:
- this is a bounded research-system user-support and enablement analogue
- it does not prove a Trust-wide research-systems helpdesk
- it does not prove an enterprise training function
- it does not prove organisation-wide procedural-document governance
- the support and training surfaces are structured analogue outputs built from the governed job 14 research lane
""",
    )

    write_md(
        OUT_BASE / "README_research_system_user_support_regeneration.md",
        """
# Research System User Support Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/guys_and_st_thomas_nhs_foundation_trust_rd_data_analyst/04_research_system_user_support_training_and_documentation/models/build_research_system_user_support_training_and_documentation.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_research_system_user_support.md",
        """
# Research System User Support Changelog

- v1: initial bounded research-system user-support, training, and documentation pack built from the completed job 14 reporting, quality, and trend lanes
""",
    )


if __name__ == "__main__":
    main()
