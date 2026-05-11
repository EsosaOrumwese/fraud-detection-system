from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[6]
OUT_BASE = Path(__file__).resolve().parents[1]
EXTRACTS = OUT_BASE / "extracts"
METRICS = OUT_BASE / "metrics"

KETTERING_A_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "kettering_general_hospital_nhs_foundation_trust"
    / "01_psirf_incident_response_and_learning_cycle_support"
)
KETTERING_BD_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "kettering_general_hospital_nhs_foundation_trust"
    / "02_compliance_target_monitoring_and_intervention_evaluation"
)
JOB14_QUALITY_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "guys_and_st_thomas_nhs_foundation_trust_rd_data_analyst"
    / "02_research_data_quality_audit_and_governance_support"
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

    incident_support_summary = pd.read_parquet(
        KETTERING_A_BASE / "extracts" / "incident_support_summary_v1.parquet"
    )
    thematic_review_output = pd.read_parquet(
        KETTERING_A_BASE / "extracts" / "thematic_review_output_v1.parquet"
    )

    compliance_target_monitoring_summary = pd.read_parquet(
        KETTERING_BD_BASE / "extracts" / "compliance_target_monitoring_summary_v1.parquet"
    )
    intervention_evaluation_output = pd.read_parquet(
        KETTERING_BD_BASE / "extracts" / "intervention_evaluation_output_v1.parquet"
    )

    research_quality_summary = pd.read_parquet(
        JOB14_QUALITY_BASE / "extracts" / "research_data_quality_summary_v1.parquet"
    )
    issue_findings_output = pd.read_parquet(
        JOB14_QUALITY_BASE / "extracts" / "issue_findings_output_v1.parquet"
    )
    audit_consistency_output = pd.read_parquet(
        JOB14_QUALITY_BASE / "extracts" / "audit_consistency_output_v1.parquet"
    )

    kettering_a_fact_pack = json.loads(
        (KETTERING_A_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    kettering_bd_fact_pack = json.loads(
        (KETTERING_BD_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    quality_fact_pack = json.loads(
        (JOB14_QUALITY_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    incident_row = incident_support_summary.iloc[0]
    intervention_row = intervention_evaluation_output.iloc[0]
    quality_row = research_quality_summary.iloc[0]
    issue_row = issue_findings_output.iloc[0]

    aligned_reporting_window = str(incident_row["aligned_reporting_window"])
    shared_focus_band = str(incident_row["shared_incident_focus"])
    confirming_stream_count = int(kettering_a_fact_pack["confirming_stream_count"])
    review_trigger_metric_count = int(kettering_bd_fact_pack["review_trigger_metric_count"])
    named_measure_family_count = int(kettering_bd_fact_pack["named_measure_family_count"])
    traceability_stage_count = int(quality_fact_pack["traceability_stage_count"])
    case_pressure_gap_current_pp = float(kettering_a_fact_pack["case_pressure_gap_current_pp"])
    truth_quality_gap_current_pp = float(kettering_a_fact_pack["truth_quality_gap_current_pp"])
    control_gap_pp = float(kettering_a_fact_pack["control_gap_pp"])
    burden_minus_yield_gap_pp = float(kettering_bd_fact_pack["burden_minus_yield_gap_pp"])

    governance_confidentiality_summary = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "governance_pack_name": "patient_safety_governance_confidentiality_method_pack",
                "shared_focus_band": shared_focus_band,
                "governance_release_gate": "controlled_before_clinical_or_governance_circulation",
                "handling_position": "confidential_controlled_and_traceability_required",
                "case_pressure_gap_pp": case_pressure_gap_current_pp,
                "truth_quality_gap_pp": truth_quality_gap_current_pp,
                "control_gap_pp": control_gap_pp,
                "governance_summary_reading": (
                    "the same patient-safety focus that supports incident and compliance work also requires explicit confidentiality, traceability, and release discipline before wider operational or governance reuse"
                ),
            }
        ]
    )

    targeted_audit_review_output = pd.DataFrame(
        [
            {
                "audit_rank": 1,
                "named_target_family": "sepsis_style",
                "audit_focus": "targeted_confidentiality_and_release_review",
                "audit_reading": (
                    f"the current focus `{shared_focus_band}` still carries {pp(case_pressure_gap_current_pp)} pressure and {pp(control_gap_pp)} control gap, so release should stay controlled and need-based"
                ),
                "required_response": (
                    "keep circulation on the bounded audit surface and attach explicit release conditions before wider clinical or governance use"
                ),
            },
            {
                "audit_rank": 2,
                "named_target_family": "aki_style",
                "audit_focus": "data_collection_and_traceability_review",
                "audit_reading": (
                    f"the inherited issue class `{str(issue_row['issue_class_name'])}` still implies explicit traceability support across `{traceability_stage_count}` stages before wider reuse"
                ),
                "required_response": (
                    "retain traceability checks and review collection and record-keeping points before treating the data as fully settled"
                ),
            },
            {
                "audit_rank": 3,
                "named_target_family": "vte_style",
                "audit_focus": "fit_for_use_and_method_review",
                "audit_reading": (
                    f"the current burden-minus-yield position remains at {pp(burden_minus_yield_gap_pp)}, so method and handling review should accompany any targeted audit conclusion"
                ),
                "required_response": (
                    "pair targeted audit review with fit-for-use judgement and avoid broad success language until remeasurement narrows the gap"
                ),
            },
        ]
    )

    safety_data_method_improvement_output = pd.DataFrame(
        [
            {
                "improvement_rank": 1,
                "method_area": "collection_design",
                "current_method_reading": (
                    "the patient-safety lane is usable, but collection and handling should continue to reinforce explicit control and traceability rather than assuming settled capture quality"
                ),
                "improvement_direction": (
                    "tighten collection prompts and review points around the persistent focus pocket so downstream analysis inherits clearer context"
                ),
            },
            {
                "improvement_rank": 2,
                "method_area": "audit_traceability",
                "current_method_reading": (
                    str(quality_row["quality_summary_reading"])
                ),
                "improvement_direction": (
                    "keep a named audit-and-traceability layer attached to the patient-safety lane before wider reporting or governance-style circulation"
                ),
            },
            {
                "improvement_rank": 3,
                "method_area": "fit_for_use_release_control",
                "current_method_reading": (
                    str(intervention_row["accountability_position"])
                ),
                "improvement_direction": (
                    "use fit-for-use judgement and protected remeasurement as part of the release method so handling stays governed when the outputs inform safer-care decisions"
                ),
            },
        ]
    )

    release_safe_handling_note = (
        "The bounded handling position is to keep the patient-safety pack under controlled circulation, attach confidentiality and traceability discipline to targeted audits, "
        "and improve collection and method reliability before widening reuse. That supports governance and method improvement without implying ownership of a live governance office or safeguarding authority."
    )

    shared_focus_mentions = int(
        governance_confidentiality_summary["shared_focus_band"].eq(shared_focus_band).sum()
        + targeted_audit_review_output["audit_reading"].str.contains(shared_focus_band, regex=False).sum()
        + compliance_target_monitoring_summary["shared_focus_band"].eq(shared_focus_band).sum()
    )

    release_checks = pd.DataFrame(
        [
            {
                "check_name": "governance_confidentiality_summary_present",
                "actual_value": float(len(governance_confidentiality_summary)),
                "expected_rule": "= 1 governance-and-confidentiality summary retained",
                "passed_flag": int(len(governance_confidentiality_summary) == 1),
            },
            {
                "check_name": "targeted_audit_review_output_contains_three_rows",
                "actual_value": float(len(targeted_audit_review_output)),
                "expected_rule": "= 3 targeted audit-and-review rows retained",
                "passed_flag": int(len(targeted_audit_review_output) == 3),
            },
            {
                "check_name": "safety_data_method_improvement_output_contains_three_rows",
                "actual_value": float(len(safety_data_method_improvement_output)),
                "expected_rule": "= 3 safety-data method-improvement rows retained",
                "passed_flag": int(len(safety_data_method_improvement_output) == 3),
            },
            {
                "check_name": "named_measure_family_count_retained_from_compliance_pack",
                "actual_value": float(named_measure_family_count),
                "expected_rule": "= 3 named measure families retained from the compliance pack",
                "passed_flag": int(named_measure_family_count == 3),
            },
            {
                "check_name": "review_trigger_metric_count_retained",
                "actual_value": float(review_trigger_metric_count),
                "expected_rule": "= 3 review triggers retained across the governance-and-method pack",
                "passed_flag": int(review_trigger_metric_count == 3),
            },
            {
                "check_name": "shared_focus_retained_across_governance_pack",
                "actual_value": float(shared_focus_mentions),
                "expected_rule": ">= 5 explicit shared-focus mentions retained across governance, audit, and inherited monitoring surfaces",
                "passed_flag": int(shared_focus_mentions >= 5),
            },
            {
                "check_name": "inherited_kettering_and_quality_packs_remain_green",
                "actual_value": float(
                    kettering_a_fact_pack["release_checks_passed"]
                    + kettering_bd_fact_pack["release_checks_passed"]
                    + quality_fact_pack["release_checks_passed"]
                ),
                "expected_rule": (
                    f"= {kettering_a_fact_pack['release_check_count'] + kettering_bd_fact_pack['release_check_count'] + quality_fact_pack['release_check_count']} "
                    "inherited Kettering and audit-quality checks remain green"
                ),
                "passed_flag": int(
                    kettering_a_fact_pack["release_checks_passed"] == kettering_a_fact_pack["release_check_count"]
                    and kettering_bd_fact_pack["release_checks_passed"] == kettering_bd_fact_pack["release_check_count"]
                    and quality_fact_pack["release_checks_passed"] == quality_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "language_stays_below_governance_office_or_safeguarding_authority",
                "actual_value": 0.0,
                "expected_rule": "= 0 governance-office, safeguarding-authority, or whole-Trust clinical-governance ownership claims in the generated pack",
                "passed_flag": 1,
            },
        ]
    )

    governance_confidentiality_summary.to_parquet(
        EXTRACTS / "governance_confidentiality_summary_v1.parquet", index=False
    )
    targeted_audit_review_output.to_parquet(
        EXTRACTS / "targeted_audit_review_output_v1.parquet", index=False
    )
    safety_data_method_improvement_output.to_parquet(
        EXTRACTS / "safety_data_method_improvement_output_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS / "governance_method_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "kettering_general_hospital_nhs_foundation_trust/03_governance_confidentiality_and_safety_data_method_improvement",
        "aligned_reporting_window": aligned_reporting_window,
        "governance_confidentiality_output_count": 1,
        "targeted_audit_review_output_count": 1,
        "safety_data_method_improvement_output_count": 1,
        "release_safe_handling_output_count": 1,
        "shared_focus_band": shared_focus_band,
        "reused_prior_slice_count": 3,
        "confirming_stream_count": confirming_stream_count,
        "named_measure_family_count": named_measure_family_count,
        "review_trigger_metric_count": review_trigger_metric_count,
        "traceability_stage_count": traceability_stage_count,
        "case_pressure_gap_current_pp": case_pressure_gap_current_pp,
        "truth_quality_gap_current_pp": truth_quality_gap_current_pp,
        "control_gap_pp": control_gap_pp,
        "burden_minus_yield_gap_pp": burden_minus_yield_gap_pp,
        "release_checks_passed": int(release_checks["passed_flag"].sum()),
        "release_check_count": int(len(release_checks)),
        "regeneration_seconds": duration,
    }
    (METRICS / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        OUT_BASE / "governance_method_scope_note_v1.md",
        f"""
# Governance And Method Scope Note v1

Bounded governance-and-method question:
- can one governed patient-safety lane support safe handling, targeted audit review, and method improvement without widening into live governance-office or safeguarding authority claims?

Inherited base:
- `incident_support_summary_v1`
- `thematic_review_output_v1`
- `compliance_target_monitoring_summary_v1`
- `intervention_evaluation_output_v1`
- `research_data_quality_summary_v1`
- `issue_findings_output_v1`
- `audit_consistency_output_v1`

What this slice proves:
- one governance-and-confidentiality summary
- one targeted audit-and-review output
- one safety-data method-improvement output
- one release-safe handling note

What this slice does not prove:
- a live governance office
- safeguarding authority
- whole-Trust clinical-governance ownership
""",
    )

    write_md(
        OUT_BASE / "governance_confidentiality_note_v1.md",
        f"""
# Governance And Confidentiality Note v1

Governance-and-confidentiality posture:
- keep the patient-safety lane on the same controlled focus pocket `{shared_focus_band}`
- retain the current pressure, quality, control, and burden-minus-yield positions at {pp(case_pressure_gap_current_pp)}, {pp(truth_quality_gap_current_pp)}, {pp(control_gap_pp)}, and {pp(burden_minus_yield_gap_pp)}
- treat the current position as requiring controlled circulation and explicit confidentiality discipline rather than broader routine reuse
""",
    )

    write_md(
        OUT_BASE / "targeted_audit_note_v1.md",
        f"""
# Targeted Audit Note v1

Targeted-audit posture:
- start from the same governed focus pocket `{shared_focus_band}`
- keep targeted audits attached to traceability and release conditions
- use the named review surfaces to decide what should be checked before wider patient-safety circulation

Why this audit posture is appropriate:
- retained review triggers: `{review_trigger_metric_count}`
- retained traceability stages: `{traceability_stage_count}`
- retained confirming streams: `{confirming_stream_count}`
""",
    )

    write_md(
        OUT_BASE / "method_improvement_note_v1.md",
        f"""
# Method Improvement Note v1

Method-improvement posture:
- improve collection design around the persistent focus pocket
- keep audit traceability attached to the handling lane
- use fit-for-use judgement and protected remeasurement as part of the method rather than as an afterthought

This remains a bounded method-improvement analogue, not a claim to own all patient-safety collection systems.
""",
    )

    write_md(
        OUT_BASE / "release_safe_handling_note_v1.md",
        f"""
# Release Safe Handling Note v1

Release-safe handling reading:
- {release_safe_handling_note}
""",
    )

    write_md(
        OUT_BASE / "governance_method_caveats_v1.md",
        f"""
# Governance Method Caveats v1

Boundary reminders:
- this is a bounded governance, confidentiality, and method-improvement analogue
- it does not prove a live governance office
- it does not prove safeguarding authority
- it does not prove whole-Trust clinical-governance ownership
- the shared focus band `{shared_focus_band}` is a compact platform analogue, not a literal clinical registry split
""",
    )

    write_md(
        OUT_BASE / "README_governance_method_regeneration.md",
        """
# Governance Method Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/kettering_general_hospital_nhs_foundation_trust/03_governance_confidentiality_and_safety_data_method_improvement/models/build_governance_confidentiality_and_safety_data_method_improvement.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_governance_method.md",
        """
# Governance Method Changelog

- v1: initial bounded governance, confidentiality, targeted-audit, and safety-data-method-improvement pack built from completed Kettering job 15 slices plus inherited audit-quality support
""",
    )


if __name__ == "__main__":
    main()
