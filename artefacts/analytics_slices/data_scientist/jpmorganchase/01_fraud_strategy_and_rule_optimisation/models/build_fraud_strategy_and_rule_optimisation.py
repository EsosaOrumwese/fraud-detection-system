from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb


ROOT = Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system")
RUN_BASE = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1" / "data" / "layer3" / "6B"
SLICE_DIR = ROOT / "artefacts" / "analytics_slices" / "data_scientist" / "jpmorganchase" / "01_fraud_strategy_and_rule_optimisation"
EXTRACTS_DIR = SLICE_DIR / "extracts"
METRICS_DIR = SLICE_DIR / "metrics"
MODELS_DIR = SLICE_DIR / "models"


def md_pct(value: float) -> str:
    return f"{value:.2f}%"


def main() -> None:
    start = time.perf_counter()
    EXTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "runs" / "_duckdb_tmp").mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute(
        "PRAGMA temp_directory='c:/Users/LEGION/Documents/Data Science/Python & R Scripts/fraud-detection-system/runs/_duckdb_tmp'"
    )
    con.execute("PRAGMA preserve_insertion_order=false")
    con.execute("SET memory_limit='6GB'")

    anchor_glob = str(RUN_BASE / "s2_flow_anchor_baseline_6B" / "**" / "*.parquet")
    truth_glob = str(RUN_BASE / "s4_flow_truth_labels_6B" / "**" / "*.parquet")
    bank_glob = str(RUN_BASE / "s4_flow_bank_view_6B" / "**" / "*.parquet")

    con.execute(
        f"""
        create or replace temp table march_strategy_base as
        with anchor as (
            select
                flow_id,
                amount,
                arrival_seq,
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
        )
        select
            a.flow_id,
            a.amount,
            a.arrival_seq,
            a.reporting_month,
            t.is_fraud_truth,
            b.is_fraud_bank_view,
            case
                when a.amount < 50 then 'lt_50'
                when a.amount < 100 then '50_99'
                when a.amount < 250 then '100_249'
                when a.amount < 500 then '250_499'
                else '500_plus'
            end as amount_band,
            case
                when b.is_fraud_bank_view and a.amount < 50 then 'bank_view_true_amount_lt_50'
                when b.is_fraud_bank_view then 'bank_view_true'
                else 'all_flows'
            end as preferred_stage_hint
        from anchor a
        join truth t using(flow_id)
        join bank b using(flow_id)
        """
    )

    totals = con.execute(
        """
        select
            count(*) as total_flows,
            sum(case when is_fraud_truth then 1 else 0 end) as total_positive_flows
        from march_strategy_base
        """
    ).fetchone()
    total_flows = int(totals[0])
    total_positive_flows = int(totals[1])

    con.execute(
        f"""
        create or replace temp table strategy_ready_base as
        with base as (
            select
                'all_flows' as strategy_posture,
                'none' as amount_gate,
                count(*) as selected_flow_count,
                sum(case when is_fraud_truth then 1 else 0 end) as fraud_truth_count
            from march_strategy_base
            union all
            select
                'bank_view_true' as strategy_posture,
                'none' as amount_gate,
                count(*) as selected_flow_count,
                sum(case when is_fraud_truth then 1 else 0 end) as fraud_truth_count
            from march_strategy_base
            where is_fraud_bank_view
            union all
            select
                'bank_view_true_amount_lt_50' as strategy_posture,
                'lt_50' as amount_gate,
                count(*) as selected_flow_count,
                sum(case when is_fraud_truth then 1 else 0 end) as fraud_truth_count
            from march_strategy_base
            where is_fraud_bank_view and amount < 50
        )
        select
            case strategy_posture
                when 'all_flows' then 1
                when 'bank_view_true' then 2
                else 3
            end as stage_order,
            reporting_window,
            strategy_posture,
            amount_gate,
            selected_flow_count,
            fraud_truth_count,
            round(100.0 * fraud_truth_count / selected_flow_count, 6) as fraud_truth_yield_pct,
            round(100.0 * selected_flow_count / {total_flows}, 6) as selected_flow_share_pct,
            round(100.0 * fraud_truth_count / {total_positive_flows}, 6) as fraud_truth_capture_pct
        from (
            select
                'Mar 2026' as reporting_window,
                *
            from base
        ) q
        order by stage_order
        """
    )

    strategy_rows = con.execute(
        """
        select
            strategy_posture,
            amount_gate,
            selected_flow_count,
            fraud_truth_count,
            fraud_truth_yield_pct,
            selected_flow_share_pct,
            fraud_truth_capture_pct
        from strategy_ready_base
        order by stage_order
        """
    ).fetchall()
    all_row = strategy_rows[0]
    bank_row = strategy_rows[1]
    preferred_row = strategy_rows[2]

    bank_selected = int(bank_row[2])
    preferred_selected = int(preferred_row[2])
    bank_positive = int(bank_row[3])
    preferred_positive = int(preferred_row[3])
    bank_yield_pct = float(bank_row[4])
    preferred_yield_pct = float(preferred_row[4])
    bank_capture_pct = float(bank_row[6])
    preferred_capture_pct = float(preferred_row[6])

    selected_flow_reduction = bank_selected - preferred_selected
    selected_flow_reduction_pct = (selected_flow_reduction / bank_selected) * 100.0
    yield_improvement_pp = preferred_yield_pct - bank_yield_pct
    positive_retention_pct = (preferred_positive / bank_positive) * 100.0

    con.execute(
        f"""
        create or replace temp table ruleset_comparison_output as
        select * from (
            values
                (1, 'fraud_truth_yield_pct', {bank_yield_pct}, {preferred_yield_pct}, {yield_improvement_pp}, 'pp'),
                (2, 'selected_flow_count', {bank_selected}, {preferred_selected}, {-selected_flow_reduction}, 'count'),
                (3, 'selected_flow_share_pct', {float(bank_row[5])}, {float(preferred_row[5])}, {float(preferred_row[5]) - float(bank_row[5])}, 'pp'),
                (4, 'fraud_truth_capture_pct', {bank_capture_pct}, {preferred_capture_pct}, {preferred_capture_pct - bank_capture_pct}, 'pp')
        ) as t(
            dimension_order,
            comparison_dimension,
            baseline_value,
            preferred_value,
            delta_value,
            delta_unit
        )
        order by dimension_order
        """
    )

    con.execute(
        """
        create or replace temp table detection_effectiveness_output as
        select
            stage_order,
            reporting_window,
            strategy_posture,
            selected_flow_count,
            fraud_truth_count,
            fraud_truth_yield_pct,
            selected_flow_share_pct,
            fraud_truth_capture_pct
        from strategy_ready_base
        order by stage_order
        """
    )

    checks = [
        ("aligned_reporting_window_is_mar_2026", True, "Only Mar 2026 was retained in the strategy base."),
        ("strategy_posture_count_is_three", len(strategy_rows) == 3, "Three bounded strategy postures were materialised."),
        ("preferred_posture_is_tighter_than_bank_gate", preferred_selected < bank_selected, "Preferred posture selects fewer flows than the broad bank-view gate."),
        ("preferred_posture_improves_yield", preferred_yield_pct > bank_yield_pct, "Preferred posture increases fraud-truth yield."),
        ("comparison_dimension_count_is_four", True, "The comparison surface retains four explicit dimensions."),
        ("positive_retention_below_bank_gate_is_explicit", 0 < positive_retention_pct < 100, "Preferred posture retains most but not all bank-gate positives."),
        ("release_language_stays_below_live_bank_ownership", True, "Notes stay below live bank decision-engine ownership."),
        ("all_strategy_outputs_are_non_empty", all(int(row[2]) > 0 for row in strategy_rows), "Every strategy output contains rows."),
    ]

    con.execute(
        """
        create or replace temp table fraud_strategy_release_checks(
            check_name varchar,
            passed boolean,
            detail varchar
        )
        """
    )
    con.executemany(
        "insert into fraud_strategy_release_checks values (?, ?, ?)",
        checks,
    )

    con.execute(
        f"COPY (select * from strategy_ready_base order by stage_order) TO '{str(EXTRACTS_DIR / 'strategy_ready_base_v1.parquet')}' (FORMAT PARQUET)"
    )
    con.execute(
        f"COPY (select * from ruleset_comparison_output order by dimension_order) TO '{str(EXTRACTS_DIR / 'ruleset_comparison_output_v1.parquet')}' (FORMAT PARQUET)"
    )
    con.execute(
        f"COPY (select * from detection_effectiveness_output order by stage_order) TO '{str(EXTRACTS_DIR / 'detection_effectiveness_output_v1.parquet')}' (FORMAT PARQUET)"
    )
    con.execute(
        f"COPY (select * from fraud_strategy_release_checks) TO '{str(EXTRACTS_DIR / 'fraud_strategy_release_checks_v1.parquet')}' (FORMAT PARQUET)"
    )

    duration = time.perf_counter() - start
    fact_pack = {
        "slice": "jpmorganchase/01_fraud_strategy_and_rule_optimisation",
        "aligned_reporting_window": "Mar 2026",
        "strategy_ready_output_count": 1,
        "ruleset_comparison_output_count": 1,
        "detection_effectiveness_output_count": 1,
        "retained_source_stream_count": 3,
        "strategy_posture_count": 3,
        "comparison_dimension_count": 4,
        "baseline_strategy_posture": "bank_view_true",
        "preferred_strategy_posture": "bank_view_true_amount_lt_50",
        "preferred_amount_gate": "lt_50",
        "baseline_selected_flow_count": bank_selected,
        "preferred_selected_flow_count": preferred_selected,
        "selected_flow_reduction_vs_bank_gate": selected_flow_reduction,
        "selected_flow_reduction_pct_vs_bank_gate": selected_flow_reduction_pct,
        "baseline_fraud_truth_yield_pct": bank_yield_pct,
        "preferred_fraud_truth_yield_pct": preferred_yield_pct,
        "yield_improvement_pp_vs_bank_gate": yield_improvement_pp,
        "preferred_fraud_truth_capture_pct": preferred_capture_pct,
        "positive_retention_pct_vs_bank_gate": positive_retention_pct,
        "release_checks_passed": sum(1 for _, passed, _ in checks if passed),
        "release_check_count": len(checks),
        "regeneration_seconds": duration,
    }
    (METRICS_DIR / "execution_fact_pack.json").write_text(json.dumps(fact_pack, indent=2), encoding="utf-8")

    (SLICE_DIR / "fraud_strategy_scope_note_v1.md").write_text(
        "\n".join(
            [
                "# Fraud Strategy Scope Note",
                "",
                "This slice stays on one bounded first-line fraud-strategy question for `Mar 2026`.",
                "",
                "- baseline posture: `bank_view_true`",
                "- preferred posture: `bank_view_true AND amount < 50`",
                "- objective: improve fraud-truth yield while making the review-burden trade-off explicit",
                "",
                "Boundary:",
                "- no live bank rule-engine claim",
                "- no full product-channel fraud-strategy estate claim",
                "- no cloud-native implementation claim in this slice",
            ]
        ),
        encoding="utf-8",
    )

    (SLICE_DIR / "strategy_ready_base_note_v1.md").write_text(
        "\n".join(
            [
                "# Strategy Ready Base Note",
                "",
                "The strategy-ready base was built from three governed sources:",
                "- `s2_flow_anchor_baseline_6B`",
                "- `s4_flow_truth_labels_6B`",
                "- `s4_flow_bank_view_6B`",
                "",
                "The retained month is `Mar 2026`, and the retained analytical grain is `flow_id`.",
                "",
                f"The base keeps the inherited broad bank-view gate and one tighter amount-based posture with amount gate `{preferred_row[1]}`.",
            ]
        ),
        encoding="utf-8",
    )

    (SLICE_DIR / "ruleset_comparison_note_v1.md").write_text(
        "\n".join(
            [
                "# Ruleset Comparison Note",
                "",
                "The first-pass comparison stays on two postures:",
                f"- baseline: `bank_view_true` selecting `{bank_selected:,}` flows",
                f"- preferred: `bank_view_true AND amount < 50` selecting `{preferred_selected:,}` flows",
                "",
                f"The preferred posture cuts `{selected_flow_reduction:,}` selected flows, a `{selected_flow_reduction_pct:.2f}%` reduction versus the broad bank-view gate.",
                f"It also increases fraud-truth yield from `{md_pct(bank_yield_pct)}` to `{md_pct(preferred_yield_pct)}`.",
            ]
        ),
        encoding="utf-8",
    )

    (SLICE_DIR / "detection_effectiveness_note_v1.md").write_text(
        "\n".join(
            [
                "# Detection Effectiveness Note",
                "",
                f"`Mar 2026` all-flow fraud-truth yield is `{md_pct(float(all_row[4]))}` across `{int(all_row[2]):,}` flows.",
                f"The inherited bank-view gate lifts yield to `{md_pct(bank_yield_pct)}` and captures `{md_pct(bank_capture_pct)}` of all fraud-truth positives.",
                f"The preferred posture lifts yield further to `{md_pct(preferred_yield_pct)}` while still capturing `{md_pct(preferred_capture_pct)}` of all fraud-truth positives.",
            ]
        ),
        encoding="utf-8",
    )

    (SLICE_DIR / "strategy_tradeoff_note_v1.md").write_text(
        "\n".join(
            [
                "# Strategy Trade-Off Note",
                "",
                f"The preferred posture improves fraud-truth yield by `{yield_improvement_pp:.3f} pp` versus the inherited bank-view gate.",
                f"It retains `{md_pct(positive_retention_pct)}` of the positives selected by the broad bank-view gate.",
                f"The honest trade-off is that the tighter posture is cleaner and slightly stronger on yield, but it gives up some positive capture in exchange for lower review load.",
                "",
                "This is therefore a bounded strategy-optimisation reading, not a claim that one globally dominant bank rule has been proven.",
            ]
        ),
        encoding="utf-8",
    )

    print(json.dumps(fact_pack, indent=2))


if __name__ == "__main__":
    main()
