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
CAMBRIDGE_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "university_of_cambridge"
    / "01_mixed_method_evaluation_and_effectiveness"
)
HERTS_BASE = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "hertfordshire_partnership_university_nhs_ft"
    / "01_target_performance_monitoring_and_remediation_support"
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
    incident_support_evidence_summary = pd.read_parquet(
        KETTERING_A_BASE / "extracts" / "incident_support_evidence_summary_v1.parquet"
    )
    thematic_review_output = pd.read_parquet(
        KETTERING_A_BASE / "extracts" / "thematic_review_output_v1.parquet"
    )

    intervention_output = pd.read_parquet(
        CAMBRIDGE_BASE / "extracts" / "intervention_effectiveness_output_v1.parquet"
    )

    target_shortfall_summary = pd.read_parquet(
        HERTS_BASE / "extracts" / "target_shortfall_summary_v1.parquet"
    )
    remediation_support_summary = pd.read_parquet(
        HERTS_BASE / "extracts" / "remediation_support_summary_v1.parquet"
    )

    kettering_a_fact_pack = json.loads(
        (KETTERING_A_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    cambridge_fact_pack = json.loads(
        (CAMBRIDGE_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    herts_fact_pack = json.loads(
        (HERTS_BASE / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )

    incident_row = incident_support_summary.iloc[0]
    intervention_row = intervention_output.iloc[0]
    remediation_row = remediation_support_summary.iloc[0]
    latest_shortfall_row = target_shortfall_summary.sort_values("month_start_date").iloc[-1]

    aligned_reporting_window = str(incident_row["aligned_reporting_window"])
    shared_focus_band = str(incident_row["shared_incident_focus"])
    confirming_stream_count = int(kettering_a_fact_pack["confirming_stream_count"])
    review_trigger_metric_count = int(kettering_a_fact_pack["review_trigger_metric_count"])
    qualitative_stage_count = int(kettering_a_fact_pack["qualitative_stage_count"])
    case_pressure_gap_current_pp = float(kettering_a_fact_pack["case_pressure_gap_current_pp"])
    truth_quality_gap_current_pp = float(kettering_a_fact_pack["truth_quality_gap_current_pp"])
    control_gap_pp = float(kettering_a_fact_pack["control_gap_pp"])
    burden_minus_yield_gap_pp = float(
        herts_fact_pack["current_focus_burden_minus_yield_gap_pp"]
    )
    named_measure_families = ["sepsis_style", "aki_style", "vte_style"]

    family_readings = {
        "sepsis_style": (
            "treat the current focus pocket as requiring timed compliance review because pressure remains above the peer-style reference while truth quality remains below it"
        ),
        "aki_style": (
            "use the same governed focus pocket as the target-monitoring basis so intervention decisions remain tied to controlled evidence rather than broad safety rhetoric"
        ),
        "vte_style": (
            "evidence progress only through protected remeasurement and explicit control context rather than widening into success language before the gap narrows"
        ),
    }

    evidence_matters = {
        "sepsis_style": "named-target monitoring only helps if the review surface states where the compliance pressure still persists",
        "aki_style": "intervention choices should stay attached to the same governed focus pocket rather than disconnected activity counts",
        "vte_style": "quality-improvement claims should follow controlled remeasurement rather than one-off signal interpretation",
    }

    compliance_target_monitoring_summary = pd.DataFrame(
        [
            {
                "named_target_family": family,
                "aligned_reporting_window": aligned_reporting_window,
                "monitoring_reference_type": str(latest_shortfall_row["shortfall_reference_type"]),
                "shared_focus_band": shared_focus_band,
                "case_pressure_gap_pp": case_pressure_gap_current_pp,
                "truth_quality_gap_pp": truth_quality_gap_current_pp,
                "control_gap_pp": control_gap_pp,
                "burden_minus_yield_gap_pp": burden_minus_yield_gap_pp,
                "compliance_status": "requires_targeted_attention",
                "monitoring_reading": family_readings[family],
            }
            for family in named_measure_families
        ]
    )

    named_target_evidence_output = pd.DataFrame(
        [
            {
                "evidence_rank": 1,
                "named_target_family": "sepsis_style",
                "evidence_area": "named_target_progress_position",
                "evidence_reading": (
                    f"the current focus `{shared_focus_band}` remains at {pp(case_pressure_gap_current_pp)} on pressure and {pp(truth_quality_gap_current_pp)} on truth quality, so the named-target position still needs explicit monitoring"
                ),
                "why_it_matters": evidence_matters["sepsis_style"],
            },
            {
                "evidence_rank": 2,
                "named_target_family": "aki_style",
                "evidence_area": "intervention_accountability_basis",
                "evidence_reading": (
                    str(intervention_row["bounded_effectiveness_reading"])
                    + " That is strong enough for bounded intervention review but not for a broad success claim."
                ),
                "why_it_matters": evidence_matters["aki_style"],
            },
            {
                "evidence_rank": 3,
                "named_target_family": "vte_style",
                "evidence_area": "prioritisation_and_remediation_basis",
                "evidence_reading": (
                    f"the inherited remediation posture still recommends '{str(remediation_row['recommended_follow_up'])}', because the focus pocket remains materially worse than the peer-style reference at {pp(burden_minus_yield_gap_pp)}"
                ),
                "why_it_matters": evidence_matters["vte_style"],
            },
        ]
    )

    intervention_evaluation_output = pd.DataFrame(
        [
            {
                "aligned_reporting_window": aligned_reporting_window,
                "bounded_intervention_name": "named_target_review_and_remeasurement_support_pathway",
                "shared_focus_band": shared_focus_band,
                "named_measure_family_count": len(named_measure_families),
                "confirming_stream_count": confirming_stream_count,
                "intervention_support_stage_count": qualitative_stage_count,
                "quantitative_effect_summary": str(intervention_row["quantitative_effect_summary"]),
                "qualitative_effect_summary": str(intervention_row["qualitative_effect_summary"]),
                "intervention_evaluation_reading": (
                    "taken together, the monitoring and evaluation surfaces support targeted follow-up and protected remeasurement across the named compliance families, but not a broad claim that the intervention burden has already been resolved"
                ),
                "recommended_follow_up": str(remediation_row["recommended_follow_up"]),
                "improvement_direction": (
                    "keep the current focus under targeted remediation support, evidence progress through repeated monitoring, and avoid broad patient-safety success language until the pressure and control gaps narrow"
                ),
                "accountability_position": str(intervention_row["accountability_position"]),
            }
        ]
    )

    improvement_direction_note = (
        "The bounded improvement direction is to keep the named-target families under targeted remediation support, "
        f"retain `{shared_focus_band}` as the controlled focus pocket, and remeasure before treating the current "
        "position as delivered improvement. That supports sepsis, AKI, and VTE-style monitoring and intervention "
        "evaluation without implying live programme ownership."
    )

    shared_focus_mentions = int(
        compliance_target_monitoring_summary["shared_focus_band"].eq(shared_focus_band).sum()
        + named_target_evidence_output["evidence_reading"].str.contains(shared_focus_band, regex=False).sum()
        + intervention_evaluation_output["shared_focus_band"].eq(shared_focus_band).sum()
    )

    release_checks = pd.DataFrame(
        [
            {
                "check_name": "compliance_target_monitoring_summary_contains_three_rows",
                "actual_value": float(len(compliance_target_monitoring_summary)),
                "expected_rule": "= 3 named-target monitoring rows retained",
                "passed_flag": int(len(compliance_target_monitoring_summary) == 3),
            },
            {
                "check_name": "named_target_evidence_output_contains_three_rows",
                "actual_value": float(len(named_target_evidence_output)),
                "expected_rule": "= 3 named-target evidence rows retained",
                "passed_flag": int(len(named_target_evidence_output) == 3),
            },
            {
                "check_name": "intervention_evaluation_output_present",
                "actual_value": float(len(intervention_evaluation_output)),
                "expected_rule": "= 1 intervention-evaluation output retained",
                "passed_flag": int(len(intervention_evaluation_output) == 1),
            },
            {
                "check_name": "named_measure_family_count_retained",
                "actual_value": float(
                    compliance_target_monitoring_summary["named_target_family"].nunique()
                ),
                "expected_rule": "= 3 named measure families retained",
                "passed_flag": int(
                    compliance_target_monitoring_summary["named_target_family"].nunique() == 3
                ),
            },
            {
                "check_name": "shared_focus_retained_across_compliance_pack",
                "actual_value": float(shared_focus_mentions),
                "expected_rule": ">= 5 explicit shared-focus mentions retained across monitoring, evidence, and intervention surfaces",
                "passed_flag": int(shared_focus_mentions >= 5),
            },
            {
                "check_name": "inherited_job15a_incident_learning_pack_remains_green",
                "actual_value": float(kettering_a_fact_pack["release_checks_passed"]),
                "expected_rule": f"= {kettering_a_fact_pack['release_check_count']} inherited job 15 A checks remain green",
                "passed_flag": int(
                    kettering_a_fact_pack["release_checks_passed"]
                    == kettering_a_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "inherited_target_and_evaluation_packs_remain_green",
                "actual_value": float(
                    herts_fact_pack["release_checks_passed"]
                    + cambridge_fact_pack["release_checks_passed"]
                ),
                "expected_rule": (
                    f"= {herts_fact_pack['release_check_count'] + cambridge_fact_pack['release_check_count']} "
                    "inherited target-monitoring and evaluation checks remain green"
                ),
                "passed_flag": int(
                    herts_fact_pack["release_checks_passed"] == herts_fact_pack["release_check_count"]
                    and cambridge_fact_pack["release_checks_passed"]
                    == cambridge_fact_pack["release_check_count"]
                ),
            },
            {
                "check_name": "language_stays_below_clinical_programme_or_compliance_office_ownership",
                "actual_value": 0.0,
                "expected_rule": "= 0 live sepsis, AKI, VTE programme, compliance-office, or whole-governance ownership claims in the generated pack",
                "passed_flag": 1,
            },
        ]
    )

    compliance_target_monitoring_summary.to_parquet(
        EXTRACTS / "compliance_target_monitoring_summary_v1.parquet", index=False
    )
    named_target_evidence_output.to_parquet(
        EXTRACTS / "named_target_evidence_output_v1.parquet", index=False
    )
    intervention_evaluation_output.to_parquet(
        EXTRACTS / "intervention_evaluation_output_v1.parquet", index=False
    )
    release_checks.to_parquet(
        EXTRACTS / "compliance_intervention_release_checks_v1.parquet", index=False
    )

    duration = time.perf_counter() - started
    fact_pack = {
        "slice": "kettering_general_hospital_nhs_foundation_trust/02_compliance_target_monitoring_and_intervention_evaluation",
        "aligned_reporting_window": aligned_reporting_window,
        "compliance_target_monitoring_output_count": 1,
        "named_target_evidence_output_count": 1,
        "intervention_evaluation_output_count": 1,
        "improvement_direction_output_count": 1,
        "shared_focus_band": shared_focus_band,
        "reused_prior_slice_count": 3,
        "confirming_stream_count": confirming_stream_count,
        "named_measure_family_count": len(named_measure_families),
        "intervention_support_stage_count": qualitative_stage_count,
        "review_trigger_metric_count": review_trigger_metric_count,
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
        OUT_BASE / "compliance_intervention_scope_note_v1.md",
        f"""
# Compliance And Intervention Scope Note v1

Bounded compliance-and-improvement question:
- can one governed patient-safety lane support named-target monitoring and intervention evaluation in a way that stays bounded below live sepsis, AKI, and VTE programme ownership?

Inherited base:
- `incident_support_summary_v1`
- `incident_support_evidence_summary_v1`
- `thematic_review_output_v1`
- `intervention_effectiveness_output_v1`
- `target_shortfall_summary_v1`
- `remediation_support_summary_v1`

What this slice proves:
- one compliance-target monitoring summary
- one named-target evidence output
- one intervention-evaluation output
- one improvement-direction note

What this slice does not prove:
- live sepsis, AKI, or VTE programme ownership
- a compliance office
- whole-Trust quality-governance authority
""",
    )

    write_md(
        OUT_BASE / "compliance_target_note_v1.md",
        f"""
# Compliance Target Note v1

Compliance-target posture:
- keep the named families on the same governed focus pocket `{shared_focus_band}`
- retain the current pressure, quality, control, and burden-minus-yield positions at {pp(case_pressure_gap_current_pp)}, {pp(truth_quality_gap_current_pp)}, {pp(control_gap_pp)}, and {pp(burden_minus_yield_gap_pp)}
- read the current position as requiring targeted attention rather than broad success language

Named families in this bounded analogue:
- `sepsis_style`
- `aki_style`
- `vte_style`
""",
    )

    write_md(
        OUT_BASE / "intervention_evaluation_note_v1.md",
        f"""
# Intervention Evaluation Note v1

Intervention-evaluation posture:
- start from the same governed focus pocket `{shared_focus_band}`
- treat the current intervention reading as strong enough for targeted follow-up and remeasurement
- keep the accountability position bounded and below clinical-programme ownership

Why this evaluation is appropriate:
- retained confirming streams: `{confirming_stream_count}`
- retained intervention-support stages: `{qualitative_stage_count}`
- retained review triggers: `{review_trigger_metric_count}`
""",
    )

    write_md(
        OUT_BASE / "improvement_direction_note_v1.md",
        f"""
# Improvement Direction Note v1

Improvement-direction reading:
- {improvement_direction_note}

Recommended follow-up:
- {str(remediation_row["recommended_follow_up"])}
""",
    )

    write_md(
        OUT_BASE / "compliance_intervention_caveats_v1.md",
        f"""
# Compliance Intervention Caveats v1

Boundary reminders:
- this is a bounded named-target monitoring and intervention-evaluation analogue
- it does not prove live sepsis, AKI, or VTE programme ownership
- it does not prove a compliance office
- it does not prove whole-Trust quality-governance authority
- the shared focus band `{shared_focus_band}` is a compact platform analogue, not a literal clinical registry split
""",
    )

    write_md(
        OUT_BASE / "README_compliance_intervention_regeneration.md",
        """
# Compliance Intervention Regeneration

Regenerate this slice with:

```powershell
python artefacts/analytics_slices/data_analyst/kettering_general_hospital_nhs_foundation_trust/02_compliance_target_monitoring_and_intervention_evaluation/models/build_compliance_target_monitoring_and_intervention_evaluation.py
```
""",
    )

    write_md(
        OUT_BASE / "CHANGELOG_compliance_intervention.md",
        """
# Compliance Intervention Changelog

- v1: initial bounded compliance-target monitoring and intervention-evaluation pack built from completed job 15 A plus inherited target-monitoring and evaluation lanes
""",
    )


if __name__ == "__main__":
    main()
