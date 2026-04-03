COPY (
    WITH base AS (
        SELECT
            week_role,
            corrected_flow_conversion_rate,
            discrepant_conversion_rate,
            absolute_gap,
            rate_ratio
        FROM read_parquet($discrepancy_path)
    )
    SELECT
        week_role,
        'original_discrepant_view' AS metric_version,
        discrepant_conversion_rate AS conversion_rate
    FROM base
    UNION ALL
    SELECT
        week_role,
        'corrected_flow_view' AS metric_version,
        corrected_flow_conversion_rate AS conversion_rate
    FROM base
    UNION ALL
    SELECT
        week_role,
        'absolute_gap' AS metric_version,
        absolute_gap AS conversion_rate
    FROM base
    ORDER BY week_role, metric_version
) TO $output_path (FORMAT PARQUET);
