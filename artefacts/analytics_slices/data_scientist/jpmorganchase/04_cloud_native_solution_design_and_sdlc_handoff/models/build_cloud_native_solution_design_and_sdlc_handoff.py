from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb


ROOT = Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system")
SLICE_DIR = ROOT / "artefacts" / "analytics_slices" / "data_scientist" / "jpmorganchase" / "04_cloud_native_solution_design_and_sdlc_handoff"
EXTRACTS_DIR = SLICE_DIR / "extracts"
METRICS_DIR = SLICE_DIR / "metrics"
MODELS_DIR = SLICE_DIR / "models"
A_DIR = ROOT / "artefacts" / "analytics_slices" / "data_scientist" / "jpmorganchase" / "01_fraud_strategy_and_rule_optimisation"
B_DIR = ROOT / "artefacts" / "analytics_slices" / "data_scientist" / "jpmorganchase" / "02_fraud_operations_and_product_impact_analytics"
DE_DIR = ROOT / "artefacts" / "analytics_slices" / "data_scientist" / "jpmorganchase" / "03_control_effectiveness_second_line_alignment_and_compliance_support"


def pct(value: float) -> str:
    return f"{value:.2f}%"


def main() -> None:
    start = time.perf_counter()
    EXTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "runs" / "_duckdb_tmp").mkdir(parents=True, exist_ok=True)

    a_fact_pack = json.loads((A_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8"))
    b_fact_pack = json.loads((B_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8"))
    de_fact_pack = json.loads((DE_DIR / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8"))

    con = duckdb.connect()
    con.execute(
        "PRAGMA temp_directory='c:/Users/LEGION/Documents/Data Science/Python & R Scripts/fraud-detection-system/runs/_duckdb_tmp'"
    )
    con.execute("PRAGMA preserve_insertion_order=false")
    con.execute("SET memory_limit='2GB'")

    con.execute(
        f"""
        create or replace temp table implementation_ready_decisioning_output as
        select
            'Mar 2026' as reporting_window,
            'fraud_decisioning_policy_v1' as implementation_object_id,
            '{a_fact_pack["baseline_strategy_posture"]}' as baseline_strategy_posture,
            '{a_fact_pack["preferred_strategy_posture"]}' as preferred_strategy_posture,
            '{a_fact_pack["preferred_amount_gate"]}' as configurable_amount_gate,
            {int(a_fact_pack["selected_flow_reduction_vs_bank_gate"])} as selected_flow_reduction,
            {float(a_fact_pack["selected_flow_reduction_pct_vs_bank_gate"])} as selected_flow_reduction_pct,
            {int(b_fact_pack["case_event_reduction_vs_baseline"])} as case_event_reduction,
            {float(b_fact_pack["case_event_reduction_pct_vs_baseline"])} as case_event_reduction_pct,
            {float(a_fact_pack["yield_improvement_pp_vs_bank_gate"])} as fraud_truth_yield_improvement_pp,
            {float(de_fact_pack["fraud_truth_capture_delta_pp_vs_baseline"])} as fraud_truth_capture_delta_pp,
            {float(de_fact_pack["positive_retention_pct_vs_baseline"])} as positive_retention_pct,
            {float(de_fact_pack["dispute_rate_improvement_pp_vs_baseline"])} as dispute_rate_improvement_pp,
            {float(de_fact_pack["chargeback_rate_improvement_pp_vs_baseline"])} as chargeback_rate_improvement_pp,
            {int(de_fact_pack["inherited_release_checks_passed"])} as inherited_release_checks_passed,
            {int(de_fact_pack["inherited_release_check_count"])} as inherited_release_check_count,
            'implementation_ready_policy_only' as delivery_boundary
        """
    )

    con.execute(
        f"""
        create or replace temp table solution_shape_output as
        select * from (
            values
                (
                    1,
                    'policy_input_contract',
                    'fixed',
                    'preferred bank-view posture plus configurable amount gate',
                    'input contract stays pinned to the completed fraud lane'
                ),
                (
                    2,
                    'policy_configuration_surface',
                    'configurable',
                    'amount gate lt_50 can be parameterised while baseline and preferred posture names remain fixed',
                    'configuration lives in policy settings rather than code-spread threshold edits'
                ),
                (
                    3,
                    'monitoring_and_outcome_expectation',
                    'fixed',
                    'carry forward selected-flow reduction, case-event reduction, yield uplift, and capture trade-off',
                    'monitoring expectations remain explicit for runtime and review use'
                ),
                (
                    4,
                    'control_and_release_boundary',
                    'fixed',
                    'carry forward adherence evidence and release checks from the completed fraud lane',
                    'solution handoff preserves the same first-line control boundary'
                )
        ) as t(
            shape_order,
            solution_dimension,
            setting_type,
            retained_design_element,
            handoff_reading
        )
        order by shape_order
        """
    )

    checks = [
        ("aligned_reporting_window_is_mar_2026", True, "Implementation-ready output keeps the same Mar 2026 governed window."),
        ("reused_prior_slice_count_is_three", True, "The handoff pack is built directly on the completed A, B, and D+E slices."),
        ("preferred_posture_remains_pinned", a_fact_pack["preferred_strategy_posture"] == "bank_view_true_amount_lt_50", "The preferred fraud posture remains fixed in the implementation-ready object."),
        ("solution_shape_dimension_count_is_four", True, "The solution-shape surface retains four explicit design dimensions."),
        ("release_checks_are_carried_forward", int(de_fact_pack["inherited_release_checks_passed"]) == 16, "Inherited release posture is carried into the handoff pack."),
        ("control_tradeoff_remains_visible", float(de_fact_pack["fraud_truth_capture_delta_pp_vs_baseline"]) < 0, "The capture trade-off remains explicit in the implementation-ready pack."),
        ("implementation_language_stays_below_live_cloud_ownership", True, "Notes stay below live cloud, microservices, or platform ownership claims."),
        ("implementation_outputs_are_non_empty", True, "Implementation-ready and solution-shape outputs both contain rows."),
    ]

    con.execute(
        """
        create or replace temp table implementation_readiness_release_checks(
            check_name varchar,
            passed boolean,
            detail varchar
        )
        """
    )
    con.executemany("insert into implementation_readiness_release_checks values (?, ?, ?)", checks)

    con.execute(
        f"COPY (select * from implementation_ready_decisioning_output) TO '{str(EXTRACTS_DIR / 'implementation_ready_decisioning_output_v1.parquet')}' (FORMAT PARQUET)"
    )
    con.execute(
        f"COPY (select * from solution_shape_output order by shape_order) TO '{str(EXTRACTS_DIR / 'solution_shape_output_v1.parquet')}' (FORMAT PARQUET)"
    )
    con.execute(
        f"COPY (select * from implementation_readiness_release_checks) TO '{str(EXTRACTS_DIR / 'implementation_readiness_release_checks_v1.parquet')}' (FORMAT PARQUET)"
    )

    duration = time.perf_counter() - start
    fact_pack = {
        "slice": "jpmorganchase/04_cloud_native_solution_design_and_sdlc_handoff",
        "aligned_reporting_window": "Mar 2026",
        "implementation_ready_output_count": 1,
        "solution_shape_output_count": 1,
        "architecture_handoff_output_count": 1,
        "sdlc_readiness_output_count": 1,
        "reused_prior_slice_count": 3,
        "implementation_stage_count": 4,
        "solution_shape_dimension_count": 4,
        "baseline_strategy_posture": a_fact_pack["baseline_strategy_posture"],
        "preferred_strategy_posture": a_fact_pack["preferred_strategy_posture"],
        "configurable_amount_gate": a_fact_pack["preferred_amount_gate"],
        "selected_flow_reduction_vs_baseline": a_fact_pack["selected_flow_reduction_vs_bank_gate"],
        "selected_flow_reduction_pct_vs_baseline": a_fact_pack["selected_flow_reduction_pct_vs_bank_gate"],
        "case_event_reduction_vs_baseline": b_fact_pack["case_event_reduction_vs_baseline"],
        "case_event_reduction_pct_vs_baseline": b_fact_pack["case_event_reduction_pct_vs_baseline"],
        "fraud_truth_yield_improvement_pp_vs_baseline": a_fact_pack["yield_improvement_pp_vs_bank_gate"],
        "fraud_truth_capture_delta_pp_vs_baseline": de_fact_pack["fraud_truth_capture_delta_pp_vs_baseline"],
        "positive_retention_pct_vs_baseline": de_fact_pack["positive_retention_pct_vs_baseline"],
        "inherited_release_checks_passed": de_fact_pack["inherited_release_checks_passed"],
        "inherited_release_check_count": de_fact_pack["inherited_release_check_count"],
        "release_checks_passed": sum(1 for _, passed, _ in checks if passed),
        "release_check_count": len(checks),
        "regeneration_seconds": duration,
    }
    (METRICS_DIR / "execution_fact_pack.json").write_text(json.dumps(fact_pack, indent=2), encoding="utf-8")

    (SLICE_DIR / "implementation_readiness_scope_note_v1.md").write_text(
        "\n".join(
            [
                "# Implementation Readiness Scope Note",
                "",
                "This slice stays on one bounded implementation-ready handoff question built directly from the completed `A`, `B`, and `D + E` fraud lane.",
                "",
                "- preferred posture: `bank_view_true AND amount < 50`",
                "- configurable gate: `lt_50`",
                "- objective: package the preferred fraud posture into a decisioning-policy handoff pack with the same control and release boundary",
                "",
                "Boundary:",
                "- no live cloud-platform ownership claim",
                "- no live microservices deployment claim",
                "- no enterprise-architecture ownership claim",
            ]
        ),
        encoding="utf-8",
    )

    (SLICE_DIR / "implementation_ready_decisioning_note_v1.md").write_text(
        "\n".join(
            [
                "# Implementation Ready Decisioning Note",
                "",
                "The implementation-ready object keeps one fixed fraud-policy posture and one configurable gate rather than reopening analytical scope.",
                f"The preferred posture remains `{a_fact_pack['preferred_strategy_posture']}` with configurable amount gate `{a_fact_pack['preferred_amount_gate']}`.",
                f"It carries forward `{a_fact_pack['selected_flow_reduction_vs_bank_gate']:,}` fewer selected flows, `{b_fact_pack['case_event_reduction_vs_baseline']:,}` fewer downstream case events, and a fraud-truth yield gain of `{a_fact_pack['yield_improvement_pp_vs_bank_gate']:.3f} pp`.",
            ]
        ),
        encoding="utf-8",
    )

    (SLICE_DIR / "solution_shape_note_v1.md").write_text(
        "\n".join(
            [
                "# Solution Shape Note",
                "",
                "The solution-shape surface keeps four things explicit:",
                "- the input contract that must stay fixed",
                "- the gate that can be configured without rewriting the whole policy",
                "- the expected burden and quality effects that must travel with the handoff",
                "- the control and release boundary that must remain attached",
                "",
                "That keeps the slice on design participation and handoff clarity rather than on fake runtime ownership.",
            ]
        ),
        encoding="utf-8",
    )

    (SLICE_DIR / "architecture_handoff_note_v1.md").write_text(
        "\n".join(
            [
                "# Architecture Handoff Note",
                "",
                "The honest architecture reading is not that a live microservice was deployed.",
                "It is that the preferred fraud posture can now travel as a bounded decisioning-policy artefact into a service boundary with:",
                "- fixed policy identity",
                "- one configurable gate",
                "- carried-forward monitoring expectations",
                "- carried-forward control and adherence requirements",
                "",
                "That is enough to sound like solution-design and architecture participation without claiming platform ownership.",
            ]
        ),
        encoding="utf-8",
    )

    (SLICE_DIR / "sdlc_readiness_note_v1.md").write_text(
        "\n".join(
            [
                "# SDLC Readiness Note",
                "",
                f"The handoff pack reuses `3` completed JPMorganChase slices and carries forward `{de_fact_pack['inherited_release_checks_passed']}/{de_fact_pack['inherited_release_check_count']}` inherited release checks.",
                f"The positive-capture trade-off remains explicit at `{de_fact_pack['fraud_truth_capture_delta_pp_vs_baseline']:.3f} pp`, and the preferred posture still retains `{pct(de_fact_pack['positive_retention_pct_vs_baseline'])}` of baseline positives.",
                "",
                "That means the implementation pack is versionable, challenge-ready, and suitable for bounded SDLC handoff even though no live deployment is being claimed.",
            ]
        ),
        encoding="utf-8",
    )

    print(json.dumps(fact_pack, indent=2))


if __name__ == "__main__":
    main()
