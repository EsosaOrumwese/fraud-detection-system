COPY (
    WITH base AS (
        SELECT *
        FROM parquet_scan($population_pathway_base_path)
        WHERE is_case_selected = 1
    ),
    thresholds AS (
        SELECT
            MEDIAN(lifecycle_hours) FILTER (WHERE target_is_fraud_truth = TRUE) AS positive_lifecycle_median_hours,
            MEDIAN(lifecycle_hours) FILTER (WHERE COALESCE(target_is_fraud_truth, FALSE) = FALSE) AS negative_lifecycle_median_hours
        FROM base
        WHERE lifecycle_hours IS NOT NULL
    ),
    labelled AS (
        SELECT
            b.*,
            CASE
                WHEN target_is_fraud_truth = TRUE
                     AND lifecycle_hours <= t.positive_lifecycle_median_hours
                THEN 'fast_converting_high_yield'
                WHEN target_is_fraud_truth = TRUE
                THEN 'slow_converting_high_yield'
                WHEN COALESCE(target_is_fraud_truth, FALSE) = FALSE
                     AND lifecycle_hours > t.negative_lifecycle_median_hours
                THEN 'high_burden_low_yield'
                ELSE 'low_burden_low_yield'
            END AS cohort_label
        FROM base b
        CROSS JOIN thresholds t
    )
    SELECT
        split_role,
        cohort_label,
        COUNT(*) AS flow_rows,
        COUNT(DISTINCT case_id) AS case_rows,
        AVG(CASE WHEN target_is_fraud_truth THEN 1.0 ELSE 0.0 END) AS fraud_truth_rate,
        AVG(CASE WHEN is_fraud_bank_view THEN 1.0 ELSE 0.0 END) AS bank_positive_rate,
        AVG(lifecycle_hours) AS avg_lifecycle_hours,
        MEDIAN(lifecycle_hours) AS median_lifecycle_hours,
        AVG(hours_event_to_case_open) AS avg_hours_event_to_case_open,
        AVG(amount) AS avg_amount
    FROM labelled
    GROUP BY 1, 2
    ORDER BY
        split_role,
        CASE cohort_label
            WHEN 'fast_converting_high_yield' THEN 1
            WHEN 'slow_converting_high_yield' THEN 2
            WHEN 'high_burden_low_yield' THEN 3
            ELSE 4
        END
) TO $population_cohort_metrics_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
