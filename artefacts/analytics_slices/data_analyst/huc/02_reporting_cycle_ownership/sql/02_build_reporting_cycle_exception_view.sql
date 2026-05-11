COPY (
    WITH segment_base AS (
        SELECT
            week_role,
            amount_band,
            CAST(flow_rows AS DOUBLE) AS flow_rows,
            CAST(case_open_rate AS DOUBLE) AS case_open_rate,
            CAST(long_lifecycle_share AS DOUBLE) AS long_lifecycle_share,
            CAST(case_truth_rate AS DOUBLE) AS case_truth_rate,
            CAST(bank_case_rate AS DOUBLE) AS bank_case_rate,
            CAST(avg_lifecycle_hours AS DOUBLE) AS avg_lifecycle_hours
        FROM read_parquet($segment_path)
    ),
    current_segments AS (
        SELECT
            *,
            ROW_NUMBER() OVER (ORDER BY case_open_rate DESC, case_truth_rate ASC) AS pressure_rank
        FROM segment_base
        WHERE week_role = 'current'
    ),
    prior_segments AS (
        SELECT
            amount_band,
            case_open_rate AS prior_case_open_rate,
            case_truth_rate AS prior_case_truth_rate
        FROM segment_base
        WHERE week_role = 'prior'
    )
    SELECT
        current_segments.amount_band,
        current_segments.flow_rows,
        current_segments.case_open_rate,
        current_segments.long_lifecycle_share,
        current_segments.case_truth_rate,
        current_segments.bank_case_rate,
        current_segments.avg_lifecycle_hours,
        prior_segments.prior_case_open_rate,
        prior_segments.prior_case_truth_rate,
        current_segments.case_open_rate - prior_segments.prior_case_open_rate AS case_open_rate_delta,
        current_segments.case_truth_rate - prior_segments.prior_case_truth_rate AS case_truth_rate_delta,
        current_segments.pressure_rank,
        CASE
            WHEN current_segments.pressure_rank = 1 THEN 1
            ELSE 0
        END AS priority_attention_flag
    FROM current_segments
    LEFT JOIN prior_segments
        ON current_segments.amount_band = prior_segments.amount_band
    ORDER BY current_segments.pressure_rank ASC
) TO $output_path (FORMAT PARQUET);
