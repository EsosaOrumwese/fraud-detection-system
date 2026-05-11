COPY (
    WITH base AS (
        SELECT
            week_role,
            flow_rows,
            case_open_rate,
            long_lifecycle_share,
            case_truth_rate
        FROM read_parquet($kpi_path)
    ),
    current_row AS (
        SELECT * FROM base WHERE week_role = 'current'
    ),
    prior_row AS (
        SELECT * FROM base WHERE week_role = 'prior'
    )
    SELECT
        'Pressure flows' AS metric,
        CAST(prior_row.flow_rows AS DOUBLE) AS prior_value,
        CAST(current_row.flow_rows AS DOUBLE) AS current_value,
        CAST(current_row.flow_rows - prior_row.flow_rows AS DOUBLE) AS delta_value,
        'count' AS unit,
        1 AS plot_order
    FROM current_row, prior_row

    UNION ALL

    SELECT
        'Case-open rate' AS metric,
        prior_row.case_open_rate AS prior_value,
        current_row.case_open_rate AS current_value,
        current_row.case_open_rate - prior_row.case_open_rate AS delta_value,
        'rate' AS unit,
        2 AS plot_order
    FROM current_row, prior_row

    UNION ALL

    SELECT
        'Long-lifecycle burden' AS metric,
        prior_row.long_lifecycle_share AS prior_value,
        current_row.long_lifecycle_share AS current_value,
        current_row.long_lifecycle_share - prior_row.long_lifecycle_share AS delta_value,
        'rate' AS unit,
        3 AS plot_order
    FROM current_row, prior_row

    UNION ALL

    SELECT
        'Authoritative truth quality' AS metric,
        prior_row.case_truth_rate AS prior_value,
        current_row.case_truth_rate AS current_value,
        current_row.case_truth_rate - prior_row.case_truth_rate AS delta_value,
        'rate' AS unit,
        4 AS plot_order
    FROM current_row, prior_row
) TO $output_path (FORMAT PARQUET);
