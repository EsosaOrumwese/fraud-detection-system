COPY (
    WITH base AS (
        SELECT
            month_role,
            month_start_date,
            SUM(flow_rows) AS flow_rows,
            SUM(case_opened_flow_rows) AS case_opened_flow_rows,
            SUM(truth_linked_flow_rows) AS truth_linked_flow_rows,
            SUM(case_truth_rows) AS case_truth_rows,
            SUM(CASE WHEN amount_band = '50_plus' THEN flow_rows ELSE 0 END) AS fifty_plus_flow_rows
        FROM read_parquet($agg_path)
        GROUP BY 1, 2
    ),
    shaped AS (
        SELECT
            month_role,
            month_start_date,
            CAST(flow_rows AS DOUBLE) AS flow_rows,
            CAST(case_opened_flow_rows AS DOUBLE) / NULLIF(flow_rows, 0) AS case_open_rate,
            CAST(case_truth_rows AS DOUBLE) / NULLIF(case_opened_flow_rows, 0) AS case_truth_rate,
            CAST(truth_linked_flow_rows AS DOUBLE) / NULLIF(flow_rows, 0) AS truth_link_rate,
            CAST(fifty_plus_flow_rows AS DOUBLE) / NULLIF(flow_rows, 0) AS fifty_plus_share
        FROM base
    ),
    current_row AS (
        SELECT * FROM shaped WHERE month_role = 'current'
    ),
    prior_row AS (
        SELECT * FROM shaped WHERE month_role = 'prior'
    )
    SELECT
        current_row.month_role,
        current_row.month_start_date,
        current_row.flow_rows,
        current_row.case_open_rate,
        current_row.case_truth_rate,
        current_row.truth_link_rate,
        current_row.fifty_plus_share,
        prior_row.month_start_date AS prior_month_start_date,
        prior_row.flow_rows AS prior_flow_rows,
        prior_row.case_open_rate AS prior_case_open_rate,
        prior_row.case_truth_rate AS prior_case_truth_rate,
        prior_row.truth_link_rate AS prior_truth_link_rate,
        prior_row.fifty_plus_share AS prior_fifty_plus_share,
        current_row.flow_rows - prior_row.flow_rows AS flow_rows_delta,
        current_row.case_open_rate - prior_row.case_open_rate AS case_open_rate_delta,
        current_row.case_truth_rate - prior_row.case_truth_rate AS case_truth_rate_delta,
        current_row.truth_link_rate - prior_row.truth_link_rate AS truth_link_rate_delta,
        current_row.fifty_plus_share - prior_row.fifty_plus_share AS fifty_plus_share_delta
    FROM current_row
    CROSS JOIN prior_row
) TO $output_path (FORMAT PARQUET, COMPRESSION ZSTD);
