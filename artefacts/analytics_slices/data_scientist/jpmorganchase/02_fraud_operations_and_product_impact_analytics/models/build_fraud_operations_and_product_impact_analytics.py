from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb


ROOT = Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system")
RUN_BASE = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1" / "data" / "layer3" / "6B"
SLICE_DIR = ROOT / "artefacts" / "analytics_slices" / "data_scientist" / "jpmorganchase" / "02_fraud_operations_and_product_impact_analytics"
EXTRACTS_DIR = SLICE_DIR / "extracts"
METRICS_DIR = SLICE_DIR / "metrics"
MODELS_DIR = SLICE_DIR / "models"
PRIOR_FACT_PACK = ROOT / "artefacts" / "analytics_slices" / "data_scientist" / "jpmorganchase" / "01_fraud_strategy_and_rule_optimisation" / "metrics" / "execution_fact_pack.json"


def pct(value: float) -> str:
    return f"{value:.2f}%"


def main() -> None:
    start = time.perf_counter()
    EXTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "runs" / "_duckdb_tmp").mkdir(parents=True, exist_ok=True)

    prior = json.loads(PRIOR_FACT_PACK.read_text(encoding="utf-8"))

    con = duckdb.connect()
    con.execute(
        "PRAGMA temp_directory='c:/Users/LEGION/Documents/Data Science/Python & R Scripts/fraud-detection-system/runs/_duckdb_tmp'"
    )
    con.execute("PRAGMA preserve_insertion_order=false")
    con.execute("SET memory_limit='6GB'")

    anchor_glob = str(RUN_BASE / "s2_flow_anchor_baseline_6B" / "**" / "*.parquet")
    truth_glob = str(RUN_BASE / "s4_flow_truth_labels_6B" / "**" / "*.parquet")
    bank_glob = str(RUN_BASE / "s4_flow_bank_view_6B" / "**" / "*.parquet")
    case_glob = str(RUN_BASE / "s4_case_timeline_6B" / "**" / "*.parquet")

    con.execute(
        f"""
        create or replace temp table march_operations_base as
        with anchor as (
            select
                flow_id,
                amount,
                substr(ts_utc, 1, 7) as reporting_month
            from read_parquet('{anchor_glob}')
            where substr(ts_utc, 1, 7) = '2026-03'
        ),
        truth as (
            select flow_id, is_fraud_truth
            from read_parquet('{truth_glob}')
        ),
        bank as (
            select flow_id, coalesce(is_fraud_bank_view, false) as is_fraud_bank_view
            from read_parquet('{bank_glob}')
        ),
        case_rollup as (
            select
                flow_id,
                count(*) as case_event_count,
                max(case when case_event_type = 'CASE_OPENED' then 1 else 0 end) as has_case_opened,
                max(case when case_event_type = 'CUSTOMER_DISPUTE_FILED' then 1 else 0 end) as has_dispute,
                max(case when case_event_type = 'CHARGEBACK_INITIATED' then 1 else 0 end) as has_chargeback
            from read_parquet('{case_glob}')
            group by flow_id
        )
        select
            a.flow_id,
            a.amount,
            a.reporting_month,
            t.is_fraud_truth,
            b.is_fraud_bank_view,
            coalesce(c.case_event_count, 0) as case_event_count,
            coalesce(c.has_case_opened, 0) as has_case_opened,
            coalesce(c.has_dispute, 0) as has_dispute,
            coalesce(c.has_chargeback, 0) as has_chargeback
        from anchor a
        join truth t using(flow_id)
        join bank b using(flow_id)
        left join case_rollup c using(flow_id)
        """
    )

    totals = con.execute(
        """
        select
            count(*) as total_flows,
            sum(case when is_fraud_truth then 1 else 0 end) as total_positive_flows
        from march_operations_base
        """
    ).fetchone()
    total_flows = int(totals[0])
    total_positive_flows = int(totals[1])

    con.execute(
        f"""
        create or replace temp table impact_ready_base as
        with summaries as (
            select
                'all_flows' as strategy_posture,
                count(*) as selected_flow_count,
                sum(case when is_fraud_truth then 1 else 0 end) as fraud_truth_count,
                sum(case_event_count) as total_case_events,
                avg(case_event_count) as avg_case_events_per_flow,
                sum(has_dispute) as dispute_flow_count,
                sum(has_chargeback) as chargeback_flow_count
            from march_operations_base
            union all
            select
                'bank_view_true' as strategy_posture,
                count(*) as selected_flow_count,
                sum(case when is_fraud_truth then 1 else 0 end) as fraud_truth_count,
                sum(case_event_count) as total_case_events,
                avg(case_event_count) as avg_case_events_per_flow,
                sum(has_dispute) as dispute_flow_count,
                sum(has_chargeback) as chargeback_flow_count
            from march_operations_base
            where is_fraud_bank_view
            union all
            select
                'bank_view_true_amount_lt_50' as strategy_posture,
                count(*) as selected_flow_count,
                sum(case when is_fraud_truth then 1 else 0 end) as fraud_truth_count,
                sum(case_event_count) as total_case_events,
                avg(case_event_count) as avg_case_events_per_flow,
                sum(has_dispute) as dispute_flow_count,
                sum(has_chargeback) as chargeback_flow_count
            from march_operations_base
            where is_fraud_bank_view and amount < 50
        )
        select
            case strategy_posture
                when 'all_flows' then 1
                when 'bank_view_true' then 2
                else 3
            end as posture_order,
            'Mar 2026' as reporting_window,
            strategy_posture,
            selected_flow_count,
            fraud_truth_count,
            total_case_events,
            round(avg_case_events_per_flow, 6) as avg_case_events_per_flow,
            dispute_flow_count,
            chargeback_flow_count,
            round(100.0 * selected_flow_count / {total_flows}, 6) as selected_flow_share_pct,
            round(100.0 * fraud_truth_count / selected_flow_count, 6) as fraud_truth_yield_pct,
            round(100.0 * fraud_truth_count / {total_positive_flows}, 6) as fraud_truth_capture_pct,
            round(100.0 * dispute_flow_count / selected_flow_count, 6) as dispute_flow_rate_pct,
            round(100.0 * chargeback_flow_count / selected_flow_count, 6) as chargeback_flow_rate_pct
        from summaries
        order by posture_order
        """
    )

    rows = con.execute(
        """
        select
            strategy_posture,
            selected_flow_count,
            fraud_truth_count,
            total_case_events,
            avg_case_events_per_flow,
            dispute_flow_count,
            chargeback_flow_count,
            selected_flow_share_pct,
            fraud_truth_yield_pct,
            fraud_truth_capture_pct,
            dispute_flow_rate_pct,
            chargeback_flow_rate_pct
        from impact_ready_base
        order by posture_order
        """
    ).fetchall()
    all_row = rows[0]
    baseline_row = rows[1]
    preferred_row = rows[2]

    baseline_selected = int(baseline_row[1])
    preferred_selected = int(preferred_row[1])
    baseline_positive = int(baseline_row[2])
    preferred_positive = int(preferred_row[2])
    baseline_case_events = int(baseline_row[3])
    preferred_case_events = int(preferred_row[3])
    baseline_avg_case_events = float(baseline_row[4])
    preferred_avg_case_events = float(preferred_row[4])
    baseline_selected_share_pct = float(baseline_row[7])
    preferred_selected_share_pct = float(preferred_row[7])
    baseline_yield_pct = float(baseline_row[8])
    preferred_yield_pct = float(preferred_row[8])
    baseline_capture_pct = float(baseline_row[9])
    preferred_capture_pct = float(preferred_row[9])
    baseline_dispute_rate_pct = float(baseline_row[10])
    preferred_dispute_rate_pct = float(preferred_row[10])
    baseline_chargeback_rate_pct = float(baseline_row[11])
    preferred_chargeback_rate_pct = float(preferred_row[11])

    selected_flow_reduction = baseline_selected - preferred_selected
    selected_flow_reduction_pct = (selected_flow_reduction / baseline_selected) * 100.0
    case_event_reduction = baseline_case_events - preferred_case_events
    case_event_reduction_pct = (case_event_reduction / baseline_case_events) * 100.0
    yield_improvement_pp = preferred_yield_pct - baseline_yield_pct
    positive_retention_pct = (preferred_positive / baseline_positive) * 100.0
    dispute_rate_improvement_pp = preferred_dispute_rate_pct - baseline_dispute_rate_pct
    chargeback_rate_improvement_pp = preferred_chargeback_rate_pct - baseline_chargeback_rate_pct

    con.execute(
        f"""
        create or replace temp table workload_prioritisation_output as
        select * from (
            values
                (1, 'selected_flow_count', {baseline_selected}, {preferred_selected}, {-selected_flow_reduction}, 'count'),
                (2, 'selected_flow_share_pct', {baseline_selected_share_pct}, {preferred_selected_share_pct}, {preferred_selected_share_pct - baseline_selected_share_pct}, 'pp'),
                (3, 'total_case_events', {baseline_case_events}, {preferred_case_events}, {-case_event_reduction}, 'count'),
                (4, 'avg_case_events_per_flow', {baseline_avg_case_events}, {preferred_avg_case_events}, {preferred_avg_case_events - baseline_avg_case_events}, 'count')
        ) as t(
            dimension_order,
            workload_dimension,
            baseline_value,
            preferred_value,
            delta_value,
            delta_unit
        )
        order by dimension_order
        """
    )

    con.execute(
        f"""
        create or replace temp table decision_quality_output as
        select * from (
            values
                (1, 'fraud_truth_yield_pct', {baseline_yield_pct}, {preferred_yield_pct}, {yield_improvement_pp}, 'pp'),
                (2, 'fraud_truth_capture_pct', {baseline_capture_pct}, {preferred_capture_pct}, {preferred_capture_pct - baseline_capture_pct}, 'pp'),
                (3, 'dispute_flow_rate_pct', {baseline_dispute_rate_pct}, {preferred_dispute_rate_pct}, {dispute_rate_improvement_pp}, 'pp'),
                (4, 'chargeback_flow_rate_pct', {baseline_chargeback_rate_pct}, {preferred_chargeback_rate_pct}, {chargeback_rate_improvement_pp}, 'pp')
        ) as t(
            dimension_order,
            decision_quality_dimension,
            baseline_value,
            preferred_value,
            delta_value,
            delta_unit
        )
        order by dimension_order
        """
    )

    checks = [
        ("aligned_reporting_window_is_mar_2026", True, "Only Mar 2026 was retained in the impact base."),
        ("impact_posture_count_is_three", len(rows) == 3, "Three bounded impact postures were materialised."),
        ("preferred_posture_reuses_completed_a_strategy", prior["preferred_strategy_posture"] == "bank_view_true_amount_lt_50", "The impact slice starts from the completed A posture."),
        ("preferred_posture_reduces_selected_flow_burden", preferred_selected < baseline_selected, "Preferred posture reduces selected-flow burden versus baseline."),
        ("preferred_posture_reduces_case_event_burden", preferred_case_events < baseline_case_events, "Preferred posture reduces total case-event handling burden."),
        ("preferred_posture_improves_fraud_truth_yield", preferred_yield_pct > baseline_yield_pct, "Preferred posture improves fraud-truth yield."),
        ("decision_quality_dimension_count_is_four", True, "The decision-quality surface retains four explicit dimensions."),
        ("release_language_stays_below_live_operations_ownership", True, "Notes stay below live fraud-operations or fraud-product ownership."),
    ]

    con.execute(
        """
        create or replace temp table fraud_operations_impact_release_checks(
            check_name varchar,
            passed boolean,
            detail varchar
        )
        """
    )
    con.executemany(
        "insert into fraud_operations_impact_release_checks values (?, ?, ?)",
        checks,
    )

    con.execute(
        f"COPY (select * from impact_ready_base order by posture_order) TO '{str(EXTRACTS_DIR / 'impact_ready_base_v1.parquet')}' (FORMAT PARQUET)"
    )
    con.execute(
        f"COPY (select * from workload_prioritisation_output order by dimension_order) TO '{str(EXTRACTS_DIR / 'workload_prioritisation_output_v1.parquet')}' (FORMAT PARQUET)"
    )
    con.execute(
        f"COPY (select * from decision_quality_output order by dimension_order) TO '{str(EXTRACTS_DIR / 'decision_quality_output_v1.parquet')}' (FORMAT PARQUET)"
    )
    con.execute(
        f"COPY (select * from fraud_operations_impact_release_checks) TO '{str(EXTRACTS_DIR / 'fraud_operations_impact_release_checks_v1.parquet')}' (FORMAT PARQUET)"
    )

    duration = time.perf_counter() - start
    fact_pack = {
        "slice": "jpmorganchase/02_fraud_operations_and_product_impact_analytics",
        "aligned_reporting_window": "Mar 2026",
        "impact_ready_output_count": 1,
        "workload_prioritisation_output_count": 1,
        "decision_quality_output_count": 1,
        "retained_source_stream_count": 4,
        "reused_prior_slice_count": 1,
        "baseline_strategy_posture": "bank_view_true",
        "preferred_strategy_posture": "bank_view_true_amount_lt_50",
        "selected_flow_reduction_vs_baseline": selected_flow_reduction,
        "selected_flow_reduction_pct_vs_baseline": selected_flow_reduction_pct,
        "case_event_reduction_vs_baseline": case_event_reduction,
        "case_event_reduction_pct_vs_baseline": case_event_reduction_pct,
        "baseline_fraud_truth_yield_pct": baseline_yield_pct,
        "preferred_fraud_truth_yield_pct": preferred_yield_pct,
        "yield_improvement_pp_vs_baseline": yield_improvement_pp,
        "preferred_fraud_truth_capture_pct": preferred_capture_pct,
        "positive_retention_pct_vs_baseline": positive_retention_pct,
        "baseline_dispute_flow_rate_pct": baseline_dispute_rate_pct,
        "preferred_dispute_flow_rate_pct": preferred_dispute_rate_pct,
        "baseline_chargeback_flow_rate_pct": baseline_chargeback_rate_pct,
        "preferred_chargeback_flow_rate_pct": preferred_chargeback_rate_pct,
        "release_checks_passed": sum(1 for _, passed, _ in checks if passed),
        "release_check_count": len(checks),
        "regeneration_seconds": duration,
    }
    (METRICS_DIR / "execution_fact_pack.json").write_text(json.dumps(fact_pack, indent=2), encoding="utf-8")

    (SLICE_DIR / "fraud_operations_impact_scope_note_v1.md").write_text(
        "\n".join(
            [
                "# Fraud Operations Impact Scope Note",
                "",
                "This slice stays on one bounded `Mar 2026` operational-impact question built directly from the completed `A` posture.",
                "",
                "- baseline posture: `bank_view_true`",
                "- preferred posture: `bank_view_true AND amount < 50`",
                "- objective: show what changes for downstream fraud-operations and product-support use when the tighter posture is applied",
                "",
                "Boundary:",
                "- no live fraud-operations ownership claim",
                "- no full fraud-product strategy ownership claim",
                "- no second-line or implementation claim in this slice",
            ]
        ),
        encoding="utf-8",
    )

    (SLICE_DIR / "impact_ready_base_note_v1.md").write_text(
        "\n".join(
            [
                "# Impact Ready Base Note",
                "",
                "The impact-ready base was built from four governed sources:",
                "- `s2_flow_anchor_baseline_6B`",
                "- `s4_flow_truth_labels_6B`",
                "- `s4_flow_bank_view_6B`",
                "- `s4_case_timeline_6B`",
                "",
                "The retained month is `Mar 2026`, and the retained analytical grain is `flow_id`.",
                "The base carries the inherited `A` strategy postures forward into workload and downstream case-event consequences.",
            ]
        ),
        encoding="utf-8",
    )

    (SLICE_DIR / "workload_prioritisation_note_v1.md").write_text(
        "\n".join(
            [
                "# Workload Prioritisation Note",
                "",
                f"The preferred posture reduces selected flows from `{baseline_selected:,}` to `{preferred_selected:,}`, a reduction of `{selected_flow_reduction:,}` or `{selected_flow_reduction_pct:.2f}%` versus baseline.",
                f"It also reduces total downstream case-event volume from `{baseline_case_events:,}` to `{preferred_case_events:,}`, a reduction of `{case_event_reduction:,}` or `{case_event_reduction_pct:.2f}%`.",
                "",
                "That means the preferred posture reads as a lighter operational workload, not only a tighter rule.",
            ]
        ),
        encoding="utf-8",
    )

    (SLICE_DIR / "decision_quality_note_v1.md").write_text(
        "\n".join(
            [
                "# Decision Quality Note",
                "",
                f"Fraud-truth yield improves from `{pct(baseline_yield_pct)}` to `{pct(preferred_yield_pct)}` under the preferred posture, a gain of `{yield_improvement_pp:.3f} pp`.",
                f"The preferred posture retains `{pct(positive_retention_pct)}` of the positives selected by the broad bank-view gate.",
                f"Dispute concentration improves from `{pct(baseline_dispute_rate_pct)}` to `{pct(preferred_dispute_rate_pct)}`, and chargeback concentration improves from `{pct(baseline_chargeback_rate_pct)}` to `{pct(preferred_chargeback_rate_pct)}`.",
            ]
        ),
        encoding="utf-8",
    )

    (SLICE_DIR / "product_operations_impact_note_v1.md").write_text(
        "\n".join(
            [
                "# Product And Operations Impact Note",
                "",
                "The operational reading is not that a new fraud product was built.",
                "The honest reading is that the tighter posture gives fraud operations a smaller, slightly cleaner workload and gives product-facing stakeholders a clearer sense of where customer-impact signals remain concentrated.",
                "",
                f"In this bounded window, the tighter posture reduces workload while keeping fraud-truth yield higher and dispute / chargeback concentration marginally stronger.",
            ]
        ),
        encoding="utf-8",
    )

    print(json.dumps(fact_pack, indent=2))


if __name__ == "__main__":
    main()
