COPY (
    WITH shaped AS (
        SELECT
            month_role,
            month_start_date,
            amount_band,
            CAST(flow_rows AS DOUBLE) AS flow_rows,
            CAST(case_opened_flow_rows AS DOUBLE) / NULLIF(flow_rows, 0) AS case_open_rate,
            CAST(case_truth_rows AS DOUBLE) / NULLIF(case_opened_flow_rows, 0) AS case_truth_rate
        FROM read_parquet($agg_path)
    ),
    current_month AS (
        SELECT
            *,
            ROW_NUMBER() OVER (ORDER BY case_open_rate DESC, case_truth_rate ASC, flow_rows DESC) AS priority_rank
        FROM shaped
        WHERE month_role = 'current'
    ),
    prior_month AS (
        SELECT
            amount_band,
            case_open_rate AS prior_case_open_rate,
            case_truth_rate AS prior_case_truth_rate
        FROM shaped
        WHERE month_role = 'prior'
    ),
    current_total AS (
        SELECT SUM(flow_rows) AS total_flow_rows
        FROM current_month
    )
    SELECT
        c.amount_band,
        c.flow_rows,
        c.flow_rows / NULLIF(t.total_flow_rows, 0) AS flow_share,
        c.case_open_rate,
        c.case_truth_rate,
        p.prior_case_open_rate,
        p.prior_case_truth_rate,
        c.case_open_rate - p.prior_case_open_rate AS case_open_rate_delta,
        c.case_truth_rate - p.prior_case_truth_rate AS case_truth_rate_delta,
        c.priority_rank,
        CASE WHEN c.priority_rank = 1 THEN 1 ELSE 0 END AS priority_attention_flag
    FROM current_month c
    CROSS JOIN current_total t
    LEFT JOIN prior_month p
        ON c.amount_band = p.amount_band
    ORDER BY c.priority_rank
) TO $output_path (FORMAT PARQUET, COMPRESSION ZSTD);
