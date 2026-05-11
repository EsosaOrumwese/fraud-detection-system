COPY (
    WITH cohorts AS (
        SELECT *
        FROM parquet_scan($population_cohort_metrics_path)
        WHERE split_role = 'test'
    ),
    ranked AS (
        SELECT
            *,
            RANK() OVER (ORDER BY avg_lifecycle_hours DESC, flow_rows DESC) AS burden_rank,
            RANK() OVER (ORDER BY fraud_truth_rate DESC, flow_rows DESC) AS yield_rank
        FROM cohorts
    )
    SELECT
        cohort_label,
        flow_rows,
        case_rows,
        fraud_truth_rate,
        bank_positive_rate,
        avg_lifecycle_hours,
        median_lifecycle_hours,
        avg_hours_event_to_case_open,
        avg_amount,
        burden_rank,
        yield_rank
    FROM ranked
    ORDER BY burden_rank, yield_rank, cohort_label
) TO $population_pathway_problem_summary_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
