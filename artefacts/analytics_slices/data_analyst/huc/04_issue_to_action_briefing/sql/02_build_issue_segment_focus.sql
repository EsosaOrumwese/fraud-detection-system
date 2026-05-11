COPY (
    SELECT
        amount_band,
        CAST(flow_rows AS DOUBLE) AS flow_rows,
        case_open_rate,
        case_truth_rate,
        prior_case_open_rate,
        prior_case_truth_rate,
        case_open_rate_delta,
        case_truth_rate_delta,
        pressure_rank AS priority_rank,
        priority_attention_flag
    FROM read_parquet($exception_path)
    ORDER BY pressure_rank
) TO $output_path (FORMAT PARQUET);
