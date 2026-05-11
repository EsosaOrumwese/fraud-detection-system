COPY (
    WITH base AS (
        SELECT
            month_start_date,
            SUM(flow_rows) AS flow_rows,
            SUM(case_opened_rows) AS case_opened_rows,
            SUM(case_truth_rows) AS case_truth_rows,
            SUM(CASE WHEN amount_band = '50_plus' THEN flow_rows ELSE 0 END) AS fifty_plus_flow_rows
        FROM read_parquet($agg_path)
        GROUP BY 1
    ),
    shaped AS (
        SELECT
            month_start_date,
            CAST(flow_rows AS DOUBLE) AS flow_rows,
            CAST(case_opened_rows AS DOUBLE) / NULLIF(flow_rows, 0) AS case_open_rate,
            CAST(case_truth_rows AS DOUBLE) / NULLIF(case_opened_rows, 0) AS case_truth_rate,
            CAST(fifty_plus_flow_rows AS DOUBLE) / NULLIF(flow_rows, 0) AS fifty_plus_share
        FROM base
    )
    SELECT
        month_start_date,
        flow_rows,
        case_open_rate,
        case_truth_rate,
        fifty_plus_share,
        LAG(flow_rows) OVER (ORDER BY month_start_date) AS prior_flow_rows,
        LAG(case_open_rate) OVER (ORDER BY month_start_date) AS prior_case_open_rate,
        LAG(case_truth_rate) OVER (ORDER BY month_start_date) AS prior_case_truth_rate,
        LAG(fifty_plus_share) OVER (ORDER BY month_start_date) AS prior_fifty_plus_share,
        flow_rows - LAG(flow_rows) OVER (ORDER BY month_start_date) AS flow_rows_delta,
        case_open_rate - LAG(case_open_rate) OVER (ORDER BY month_start_date) AS case_open_rate_delta,
        case_truth_rate - LAG(case_truth_rate) OVER (ORDER BY month_start_date) AS case_truth_rate_delta,
        fifty_plus_share - LAG(fifty_plus_share) OVER (ORDER BY month_start_date) AS fifty_plus_share_delta
    FROM shaped
    ORDER BY month_start_date
) TO $output_path (FORMAT PARQUET, COMPRESSION ZSTD);
