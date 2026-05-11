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
CLAIRE_AUDIT_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "claire_house"
    / "05_data_quality_audit_and_governance_support"
)
WELSH_AUDIT_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "welsh_government"
    / "02_compliance_and_audit_support"
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
    dashboard_output = pd.read_parquet(
        JOB14_REPORTING_BASE / "extracts" / "research_performance_dashboard_output_v1.parquet"
    )
    reporting_release_checks = pd.read_parquet(
        JOB14_REPORTING_BASE / "extracts" / "research_reporting_release_checks_v1.parquet"
    )

    claire_monitoring_summary = pd.read_parquet(
        CLAIRE_AUDIT_BASE / "extracts" / "data_quality_monitoring_summary_v1.parquet"
    )
    welsh_audit_summary = pd.read_parquet(
        WELSH_AUDIT_BASE / "extracts" / "audit_readiness_summary_v1.parquet"
    )
    welsh_traceability_output = pd.read_parquet(
        WELSH_AUDIT_BASE / "extracts" / "rule_traceability_output_v1.parquet"
    )

    job14_fact_pack = json.loads(
        (JOB14_REPORTING_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    claire_fact_pack = json.loads(
        (CLAIRE_AUDIT_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    welsh_fact_pack = json.loads(
        (WELSH_AUDIT_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    prepared_row = prepared_base.iloc[0]
    mandatory_row = mandatory_summary.iloc[0]
    reporting_pressure_row = dashboard_output.loc[
        dashboard_output["dashboard_metric_name"] == "reporting_pressure_gap_pp"
    ].iloc[0]
    quality_consistency_row = dashboard_output.loc[
        dashboard_output["dashboard_metric_name"] == "quality_consistency_gap_pp"
    ].iloc[0]
    claire_audit_row = claire_monitoring_summary.loc[
        claire_monitoring_summary["monitoring_area"] == "trusted_provision_lane"
    ].iloc[0]
    welsh_audit_row = welsh_audit_summary.iloc[0]

    aligned_reporting_window = str(prepared_row["aligned_reporting_window"])
    shared_reporting_cohort = str(prepared_row["shared_reporting_cohort"])
    issue_class_name = "control_gap_requires_audit_traceability_before_wider_reuse"

    reporting_pressure_gap_pp = float(prepared_row["case_pressure_gap_pp"])
    quality_consistency_gap_pp = float(prepared_row["truth_quality_gap_pp"])
    control_gap_pp = float(mandatory_row["control_gap_pp"])

    pressure_review_flag = int(reporting_pressure_gap_pp > 1.00)
    quality_review_flag = int(quality_consistency_gap_pp < -1.00)
    control_review_flag = int(control_gap_pp > 4.00)

    research_data_quality_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "quality_pack_name": "research_data_quality_audit_governance_pack",
                "issue_class_name": issue_class_name,
                "reporting_grain": str(prepared_row["reporting_grain"]),
                "shared_reporting_cohort": shared_reporting_cohort,
                "reporting_pressure_gap_pp": reporting_pressure_gap_pp,
                "quality_consistency_gap_pp": quality_consistency_gap_pp,
                "control_gap_pp": control_gap_pp,
                "quality_checked_release_gate": str(mandatory_row["quality_checked_release_gate"]),
                "release_control_status": "controlled_release_required_before_wider_r_and_d_reuse",
                "quality_summary_reading": (
                    "the same reporting cohort that supports recurring R&D metrics also carries one bounded "
                    "quality-and-audit condition, so traceability and controlled release have to remain explicit"
                ),
            }
        ]
    )

    issue_findings_output = pd.DataFrame(
        [
            {
                "issue_class_name": issue_class_name,
                "issue_area": "research_reporting_control_traceability",
                "severity": "medium",
                "shared_reporting_cohort": shared_reporting_cohort,
                "control_gap_pp": control_gap_pp,
                "reporting_pressure_gap_pp": reporting_pressure_gap_pp,
                "quality_consistency_gap_pp": quality_consistency_gap_pp,
                "likely_root_cause": (
                    "the retained reporting cohort remains governed and reusable, but the carried control gap and the "
                    "two directional review metrics show that wider circulation still depends on explicit audit traceability "
                    "rather than simple reporting confidence alone"
                ),
                "audit_risk_reading": (
                    "without a named audit-and-traceability layer, the prepared base could be reused as though it were fully "
                    "settled operational reporting rather than a controlled high-accountability R&D pack"
                ),
                "bounded_solution_direction": (
                    "keep the same reporting cohort on one named audit-and-consistency surface and attach release decisions "
                    "to explicit traceability and control checks before wider reuse"
                ),
            }
        ]
    )

    audit_consistency_output = pd.DataFrame(
        [
            {
                "audit_rank": 1,
                "audit_metric_name": "reporting_pressure_gap_pp",
                "audit_metric_purpose": "track whether the retained cohort still carries materially higher reporting pressure than peer context",
                "current_value": reporting_pressure_gap_pp,
                "value_unit": "percentage_points",
                "threshold_rule": "> 1.00 pp indicates continued quality-review pressure",
                "review_trigger_flag": pressure_review_flag,
                "required_response": "keep the cohort on the bounded audit surface and avoid treating the pressure position as resolved",
            },
            {
                "audit_rank": 2,
                "audit_metric_name": "quality_consistency_gap_pp",
                "audit_metric_purpose": "track whether the retained cohort still sits behind peer-quality context for reporting consistency",
                "current_value": quality_consistency_gap_pp,
                "value_unit": "percentage_points",
                "threshold_rule": "< -1.00 pp indicates continued consistency-review need",
                "review_trigger_flag": quality_review_flag,
                "required_response": "keep the quality reading attached to the same controlled pack rather than wider standalone circulation",
            },
            {
                "audit_rank": 3,
                "audit_metric_name": "control_gap_pp",
                "audit_metric_purpose": "track whether the underlying control-family gap remains large enough to require explicit audit traceability",
                "current_value": control_gap_pp,
                "value_unit": "percentage_points",
                "threshold_rule": "> 4.00 pp indicates explicit audit-traceability support remains necessary",
                "review_trigger_flag": control_review_flag,
                "required_response": "retain explicit traceability and release review before broader R&D reporting reuse",
            },
        ]
    )

    release_checks = pd.DataFrame(
        [
            {
                "check_name": "research_data_quality_summary_output_present",
                "actual_value": float(len(research_data_quality_summary)),
                "expected_rule": "= 1 research-data quality summary output present",
                "passed_flag": int(len(research_data_quality_summary) == 1),
            },
            {
                "check_name": "issue_findings_output_contains_single_issue_class",
                "actual_value": float(issue_findings_output["issue_class_name"].nunique()),
                "expected_rule": "= 1 explicit issue class retained",
                "passed_flag": int(issue_findings_output["issue_class_name"].nunique() == 1),
            },
            {
                "check_name": "audit_consistency_surface_contains_three_metrics",
                "actual_value": float(len(audit_consistency_output)),
                "expected_rule": "= 3 audit-and-consistency metrics retained",
                "passed_flag": int(len(audit_consistency_output) == 3),
            },
            {
                "check_name": "three_audit_metrics_trigger_review",
                "actual_value": float(audit_consistency_output["review_trigger_flag"].sum()),
                "expected_rule": "= 3 audit metrics trigger bounded review before wider reuse",
                "passed_flag": int(audit_consistency_output["review_trigger_flag"].sum() == 3),
            },
            {
                "check_name": "all_outputs_retain_same_reporting_cohort",
                "actual_value": float(
                    research_data_quality_summary.iloc[0]["shared_reporting_cohort"]
                    == issue_findings_output.iloc[0]["shared_reporting_cohort"]
                    == shared_reporting_cohort
                ),
                "expected_rule": "= 1 same reporting cohort retained across quality outputs",
                "passed_flag": int(
                    research_data_quality_summary.iloc[0]["shared_reporting_cohort"]
                    == issue_findings_output.iloc[0]["shared_reporting_cohort"]
                    == shared_reporting_cohort
                ),
            },
            {
                "check_name": "inherited_job14_reporting_pack_remains_green",
                "actual_value": float(job14_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {job14_fact_pack['release_check_count']} inherited job 14 reporting checks remain green",
                "passed_flag": int(
                    job14_fact_pack["release_checks_passed"] == job14_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "methodological_quality_audit_pack_remains_green",
                "actual_value": float(claire_fact_pack["audit_checks_passed"]),
                "expected_rule": f"= {claire_fact_pack['audit_check_count']} methodological quality-audit checks remain green",
                "passed_flag": int(
                    claire_fact_pack["audit_checks_passed"] == claire_fact_pack["audit_check_count"]
                ),
            },
            {
                "check_name": "methodological_audit_traceability_pack_remains_green",
                "actual_value": float(welsh_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {welsh_fact_pack['release_check_count']} methodological audit-support checks remain green",
                "passed_flag": int(
                    welsh_fact_pack["release_checks_passed"] == welsh_fact_pack["release_check_count"]
                ),
            },
        ]
    )

    research_data_quality_summary.to_parquet(
        EXTRACTS / "research_data_quality_summary_v1.parquet", index=False
    )
    issue_findings_output.to_parquet(
        EXTRACTS / "issue_findings_output_v1.parquet", index=False
    )
    audit_consistency_output.to_parquet(
        EXTRACTS / "audit_consistency_output_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS / "research_quality_governance_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "guys_and_st_thomas_nhs_foundation_trust_rd_data_analyst/02_research_data_quality_audit_and_governance_support",
        "aligned_reporting_window": aligned_reporting_window,
        "research_data_quality_output_count": 1,
        "issue_class_count": int(issue_findings_output["issue_class_name"].nunique()),
        "audit_consistency_output_count": 1,
        "corrective_reading_output_count": 1,
        "shared_reporting_cohort": shared_reporting_cohort,
        "retained_source_stream_count": int(prepared_row["retained_source_streams"]),
        "audit_metric_count": int(len(audit_consistency_output)),
        "review_trigger_metric_count": int(audit_consistency_output["review_trigger_flag"].sum()),
        "current_reporting_pressure_gap_pp": reporting_pressure_gap_pp,
        "current_quality_consistency_gap_pp": quality_consistency_gap_pp,
        "current_control_gap_pp": control_gap_pp,
        "traceability_stage_count": int(welsh_fact_pack["traceability_stage_count"]),
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "research_data_quality_scope_note_v1.md",
        f"""
# Research Data Quality Scope Note v1

Bounded quality-and-audit question:
- can the governed research-performance reporting lane support one explicit issue class, one audit-and-consistency surface, and one release-safe corrective reading without widening into a whole governance-function claim?

Inherited base:
- `prepared_research_performance_base_v1`
- `mandatory_research_reporting_summary_v1`
- `research_performance_dashboard_output_v1`
- `research_reporting_release_checks_v1`

What this slice proves:
- one research-data quality summary
- one explicit issue class
- one audit-and-consistency surface
- one release-safe corrective-reading note

What this slice does not prove:
- a full Trust governance office
- a full R&D audit office
- end-to-end `EDGE` administration
- direct `CPMS` interface ownership
""",
    )

    write_md(
        OUT_BASE / "issue_findings_note_v1.md",
        f"""
# Issue Findings Note v1

Issue class retained:
- `{issue_class_name}`

Shared reporting cohort:
- `{shared_reporting_cohort}`

Issue reading:
- reporting-pressure gap: `{pp(reporting_pressure_gap_pp)}`
- quality-consistency gap: `{pp(quality_consistency_gap_pp)}`
- control gap: `{pp(control_gap_pp)}`

Why this matters:
- the reporting pack remains reusable, but wider circulation still depends on named audit traceability rather than simple reporting confidence
- the bounded issue is not that the lane has failed
- the bounded issue is that high-accountability reuse still requires explicit control explanation
""",
    )

    write_md(
        OUT_BASE / "governance_release_note_v1.md",
        f"""
# Governance And Release Note v1

Governance-safe release posture:
- inherited reporting release checks remain green at `{job14_fact_pack['release_checks_passed']}/{job14_fact_pack['release_check_count']}`
- inherited Claire audit posture remains green at `{claire_fact_pack['audit_checks_passed']}/{claire_fact_pack['audit_check_count']}`
- inherited Welsh audit-support posture remains green at `{welsh_fact_pack['release_checks_passed']}/{welsh_fact_pack['release_check_count']}`

Release meaning:
- the pack remains safe for controlled circulation
- wider reuse still needs the same traceability and control explanation to remain attached
- this is governance-safe reporting support, not proof of a live governance-office function
""",
    )

    write_md(
        OUT_BASE / "corrective_reading_note_v1.md",
        f"""
# Corrective Reading Note v1

Corrective posture:
- keep the retained reporting cohort `{shared_reporting_cohort}` on one named audit-and-consistency surface
- keep release decisions attached to explicit traceability and control checks
- do not widen the same reporting pack into broader routine reuse without the attached audit reading

Bounded next action:
- preserve the prepared reporting base
- preserve the mandatory-return and dashboard outputs
- add the audit layer whenever the same pack is reused for higher-accountability R&D reporting

Why this is proportionate:
- the reporting pack is still green
- the issue is about defendable reuse, not collapse of the reporting lane
""",
    )

    write_md(
        OUT_BASE / "research_quality_governance_caveats_v1.md",
        f"""
# Research Quality Governance Caveats v1

Boundary reminders:
- this is a bounded research-data quality, audit, and governance-support analogue
- it does not prove live `EDGE` administration
- it does not prove direct `CPMS` integration ownership
- it does not prove a full Trust R&D audit office
- the shared reporting cohort is a compact platform analogue over `{shared_reporting_cohort}`, not a literal Trust research-portfolio segmentation estate
""",
    )

    write_md(
        OUT_BASE / "README_research_quality_governance_regeneration.md",
        """
# Research Quality Governance Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/guys_and_st_thomas_nhs_foundation_trust_rd_data_analyst/02_research_data_quality_audit_and_governance_support/models/build_research_data_quality_audit_and_governance_support.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_research_quality_governance.md",
        """
# Research Quality Governance Changelog

- v1: initial bounded research-data quality, audit, and governance-support pack built from inherited job 14 reporting, Claire audit, and Welsh audit-support lanes
""",
    )


if __name__ == "__main__":
    main()
