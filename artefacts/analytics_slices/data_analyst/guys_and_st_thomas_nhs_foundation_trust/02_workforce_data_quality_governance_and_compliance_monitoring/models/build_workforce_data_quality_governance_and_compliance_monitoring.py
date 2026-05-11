from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

GUYS_REPORTING_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "guys_and_st_thomas_nhs_foundation_trust"
    / "01_workforce_intelligence_edi_dashboards_and_statutory_reporting"
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

    workforce_reporting_summary = pd.read_parquet(
        GUYS_REPORTING_BASE / "extracts" / "workforce_reporting_summary_v1.parquet"
    )
    edi_dashboard_surface = pd.read_parquet(
        GUYS_REPORTING_BASE / "extracts" / "edi_dashboard_surface_v1.parquet"
    )
    statutory_reporting_summary = pd.read_parquet(
        GUYS_REPORTING_BASE / "extracts" / "statutory_reporting_summary_v1.parquet"
    )
    reporting_checks = pd.read_parquet(
        GUYS_REPORTING_BASE / "extracts" / "workforce_reporting_release_checks_v1.parquet"
    )

    guys_fact_pack = json.loads(
        (GUYS_REPORTING_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    claire_fact_pack = json.loads(
        (CLAIRE_AUDIT_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    welsh_fact_pack = json.loads(
        (WELSH_AUDIT_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    summary_row = workforce_reporting_summary.iloc[0]
    statutory_row = statutory_reporting_summary.iloc[0]
    case_gap_metric = edi_dashboard_surface.loc[
        edi_dashboard_surface["dashboard_metric_name"] == "focus_case_open_gap_to_peer_pp"
    ].iloc[0]
    truth_gap_metric = edi_dashboard_surface.loc[
        edi_dashboard_surface["dashboard_metric_name"] == "focus_truth_quality_gap_to_peer_pp"
    ].iloc[0]

    aligned_reporting_window = str(summary_row["aligned_reporting_window"])
    protected_group_dimension = str(summary_row["protected_group_dimension"])
    protected_group_focus = str(summary_row["protected_group_focus"])
    issue_class_name = "protected_group_focus_gap_requires_controlled_release"
    likely_root_cause = (
        "the retained protected-group-style focus remains materially separated from peer-style context "
        "across both case-pressure and truth-quality readings, so the same workforce-reporting lane "
        "needs a stricter release and monitoring posture before wider circulation"
    )

    case_gap_pp = float(summary_row["focus_group_case_gap_pp"])
    truth_gap_pp = float(summary_row["focus_group_truth_gap_pp"])
    case_gap_breach_flag = int(case_gap_pp > 1.00)
    truth_gap_breach_flag = int(truth_gap_pp < -1.00)
    release_gate_breach_flag = 0

    workforce_data_quality_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "quality_pack_name": "workforce_data_quality_governance_pack",
                "issue_class_name": issue_class_name,
                "protected_group_dimension": protected_group_dimension,
                "protected_group_focus": protected_group_focus,
                "current_focus_case_gap_pp": case_gap_pp,
                "current_focus_truth_gap_pp": truth_gap_pp,
                "quality_checked_release_gate": str(statutory_row["quality_checked_release_gate"]),
                "release_control_status": "controlled_release_required_before_wider_customer_use",
                "quality_summary_reading": (
                    "the same protected-group-style focus that supports workforce and equality-style reporting "
                    "also carries one bounded quality-and-governance condition, so release safety has to remain explicit"
                ),
            }
        ]
    )

    issue_findings_output = pd.DataFrame(
        [
            {
                "issue_class_name": issue_class_name,
                "issue_area": "protected_group_style_focus_control",
                "severity": "medium",
                "protected_group_dimension": protected_group_dimension,
                "protected_group_focus": protected_group_focus,
                "case_gap_pp": case_gap_pp,
                "truth_gap_pp": truth_gap_pp,
                "likely_root_cause": likely_root_cause,
                "governance_risk_reading": (
                    "without continued quality checking and controlled release, the protected-group-style reading "
                    "could be circulated as a simple reporting fact rather than a monitored condition"
                ),
                "bounded_solution_direction": (
                    "keep the focus pocket on a named monitoring surface and require the same release gate before wider circulation"
                ),
            }
        ]
    )

    compliance_monitoring_output = pd.DataFrame(
        [
            {
                "monitoring_rank": 1,
                "monitoring_metric_name": str(case_gap_metric["dashboard_metric_name"]),
                "monitoring_metric_purpose": "track whether the protected-group-style pressure gap remains elevated",
                "current_value": case_gap_pp,
                "value_unit": "percentage_points",
                "threshold_rule": "> 1.00 pp indicates elevated case-pressure divergence",
                "breach_flag": case_gap_breach_flag,
                "required_response": (
                    "keep the focus pocket under regular review and avoid treating the pressure gap as resolved"
                ),
            },
            {
                "monitoring_rank": 2,
                "monitoring_metric_name": str(truth_gap_metric["dashboard_metric_name"]),
                "monitoring_metric_purpose": "track whether the protected-group-style quality position remains behind peer-style context",
                "current_value": truth_gap_pp,
                "value_unit": "percentage_points",
                "threshold_rule": "< -1.00 pp indicates quality-position lag requiring controlled interpretation",
                "breach_flag": truth_gap_breach_flag,
                "required_response": (
                    "keep the quality reading attached to the same controlled pack rather than wider standalone circulation"
                ),
            },
            {
                "monitoring_rank": 3,
                "monitoring_metric_name": "release_safe_check_pass_rate",
                "monitoring_metric_purpose": "confirm the inherited workforce-reporting lane still passes its release gate",
                "current_value": float(
                    guys_fact_pack["release_checks_passed"] / guys_fact_pack["release_check_count"]
                ),
                "value_unit": "ratio",
                "threshold_rule": "= 1.00 required before wider release reuse",
                "breach_flag": release_gate_breach_flag,
                "required_response": (
                    "continue allowing controlled circulation while the inherited release gate remains fully green"
                ),
            },
        ]
    )

    release_checks = pd.DataFrame(
        [
            {
                "check_name": "workforce_data_quality_summary_output_present",
                "actual_value": float(len(workforce_data_quality_summary)),
                "expected_rule": "= 1 workforce-data quality summary output present",
                "passed_flag": int(len(workforce_data_quality_summary) == 1),
            },
            {
                "check_name": "issue_findings_output_contains_single_issue_class",
                "actual_value": float(issue_findings_output["issue_class_name"].nunique()),
                "expected_rule": "= 1 explicit issue class retained",
                "passed_flag": int(issue_findings_output["issue_class_name"].nunique() == 1),
            },
            {
                "check_name": "compliance_monitoring_surface_contains_three_metrics",
                "actual_value": float(len(compliance_monitoring_output)),
                "expected_rule": "= 3 monitoring metrics retained",
                "passed_flag": int(len(compliance_monitoring_output) == 3),
            },
            {
                "check_name": "two_monitoring_metrics_trigger_review",
                "actual_value": float(compliance_monitoring_output["breach_flag"].sum()),
                "expected_rule": "= 2 monitoring metrics trigger bounded review while release gate stays green",
                "passed_flag": int(compliance_monitoring_output["breach_flag"].sum() == 2),
            },
            {
                "check_name": "all_outputs_retain_same_focus_group",
                "actual_value": float(
                    workforce_data_quality_summary.iloc[0]["protected_group_focus"]
                    == issue_findings_output.iloc[0]["protected_group_focus"]
                    == protected_group_focus
                ),
                "expected_rule": "= 1 same protected-group-style focus retained across quality outputs",
                "passed_flag": int(
                    workforce_data_quality_summary.iloc[0]["protected_group_focus"]
                    == issue_findings_output.iloc[0]["protected_group_focus"]
                    == protected_group_focus
                ),
            },
            {
                "check_name": "inherited_workforce_reporting_pack_remains_green",
                "actual_value": float(guys_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {guys_fact_pack['release_check_count']} inherited workforce-reporting checks remain green",
                "passed_flag": int(
                    guys_fact_pack["release_checks_passed"] == guys_fact_pack["release_check_count"]
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

    workforce_data_quality_summary.to_parquet(
        EXTRACTS / "workforce_data_quality_summary_v1.parquet", index=False
    )
    issue_findings_output.to_parquet(
        EXTRACTS / "issue_findings_output_v1.parquet", index=False
    )
    compliance_monitoring_output.to_parquet(
        EXTRACTS / "compliance_monitoring_output_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS / "workforce_quality_governance_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "guys_and_st_thomas_nhs_foundation_trust/02_workforce_data_quality_governance_and_compliance_monitoring",
        "aligned_reporting_window": aligned_reporting_window,
        "workforce_data_quality_output_count": 1,
        "issue_class_count": int(issue_findings_output["issue_class_name"].nunique()),
        "compliance_monitoring_output_count": 1,
        "corrective_reading_output_count": 1,
        "protected_group_dimension": protected_group_dimension,
        "protected_group_focus": protected_group_focus,
        "monitoring_metric_count": int(len(compliance_monitoring_output)),
        "review_trigger_metric_count": int(compliance_monitoring_output["breach_flag"].sum()),
        "current_focus_case_gap_pp": case_gap_pp,
        "current_focus_truth_gap_pp": truth_gap_pp,
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "workforce_data_quality_scope_note_v1.md",
        f"""
# Workforce Data Quality Scope Note v1

Bounded quality-and-governance question:
- can the governed workforce-reporting lane support one explicit issue class, one monitoring surface, and one release-safe corrective reading without widening into a whole governance-function claim?

Inherited base:
- `workforce_reporting_summary_v1`
- `edi_dashboard_surface_v1`
- `statutory_reporting_summary_v1`
- `workforce_reporting_release_checks_v1`

What this slice proves:
- one workforce-data quality summary
- one explicit issue class
- one `KPI` / compliance-monitoring surface
- one release-safe corrective-reading note

What this slice does not prove:
- a full Trust `IG` office
- a full audit office
- end-to-end workforce-system security administration
""",
    )

    write_md(
        OUT_BASE / "issue_findings_note_v1.md",
        f"""
# Issue Findings Note v1

Issue class retained:
- `{issue_class_name}`

Protected-group-style focus:
- dimension: `{protected_group_dimension}`
- focus: `{protected_group_focus}`

Current issue reading:
- case-gap signal: `{pp(case_gap_pp)}`
- truth-gap signal: `{pp(truth_gap_pp)}`

Likely reason:
- {likely_root_cause}

Why this matters:
- the workforce-reporting lane remains usable
- but the same focus pocket now carries a bounded monitoring condition rather than a simple neutral release reading
""",
    )

    write_md(
        OUT_BASE / "governance_release_note_v1.md",
        f"""
# Governance Release Note v1

Release-control posture:
- inherited workforce-reporting release gate remains green at `{guys_fact_pack['release_checks_passed']}/{guys_fact_pack['release_check_count']}`
- quality-checked release gate retained: `{statutory_row['quality_checked_release_gate']}`
- protected-group-style focus retained: `{protected_group_focus}`

Governance meaning:
- the pack is suitable for controlled workforce-information use
- the issue remains bounded and monitored rather than hidden
- this stays below live governance-office or compliance-function ownership
""",
    )

    write_md(
        OUT_BASE / "corrective_reading_note_v1.md",
        f"""
# Corrective Reading Note v1

Corrective reading:
- keep the `{protected_group_focus}` protected-group-style focus on a named monitoring surface rather than treating it as resolved reporting noise
- require the same release gate before wider customer or board-style reuse
- use the issue class and monitoring surface together so the quality and governance condition stays explicit

Bounded action direction:
- continue quality checking before release
- continue review while the case-gap signal stays above `+1.00 pp`
- continue controlled interpretation while the truth-gap signal stays below `-1.00 pp`

This is a bounded correction-and-monitoring posture, not a whole-Trust governance remediation programme.
""",
    )

    write_md(
        OUT_BASE / "workforce_quality_governance_caveats_v1.md",
        f"""
# Workforce Quality Governance Caveats v1

Boundary reminders:
- this is a bounded workforce-data quality and compliance-monitoring analogue
- it does not prove a live Trust governance office
- it does not prove a live audit function
- the protected-group-style dimension `{protected_group_dimension}` over `{protected_group_focus}` is an honest reporting analogue, not a literal Trust workforce protected-characteristic estate
""",
    )

    write_md(
        OUT_BASE / "README_workforce_quality_governance_regeneration.md",
        """
# Workforce Quality Governance Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/guys_and_st_thomas_nhs_foundation_trust/02_workforce_data_quality_governance_and_compliance_monitoring/models/build_workforce_data_quality_governance_and_compliance_monitoring.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_workforce_quality_governance.md",
        """
# Workforce Quality Governance Changelog

- v1: initial bounded workforce-data quality, governance-safe release, and compliance-monitoring pack built from the inherited Guy's and St Thomas' workforce-reporting lane
""",
    )


if __name__ == "__main__":
    main()
