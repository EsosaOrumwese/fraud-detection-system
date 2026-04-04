COPY (
    WITH shaped AS (
        SELECT
            month_start_date,
            amount_band,
            CAST(flow_rows AS DOUBLE) AS flow_rows,
            CAST(case_opened_rows AS DOUBLE) AS case_opened_rows,
            CAST(case_truth_rows AS DOUBLE) AS case_truth_rows,
            CAST(case_opened_rows AS DOUBLE) / NULLIF(flow_rows, 0) AS case_open_rate,
            CAST(case_truth_rows AS DOUBLE) / NULLIF(case_opened_rows, 0) AS case_truth_rate
        FROM read_parquet($agg_path)
    ),
    month_totals AS (
        SELECT
            month_start_date,
            SUM(flow_rows) AS total_flow_rows,
            SUM(case_opened_rows) AS total_case_opened_rows,
            SUM(case_truth_rows) AS total_case_truth_rows
        FROM shaped
        GROUP BY 1
    ),
    band_totals AS (
        SELECT
            month_start_date,
            amount_band,
            flow_rows,
            case_opened_rows,
            case_truth_rows,
            case_open_rate,
            case_truth_rate
        FROM shaped
    ),
    focused AS (
        SELECT
            b.month_start_date,
            b.amount_band,
            b.flow_rows,
            b.flow_rows / NULLIF(t.total_flow_rows, 0) AS flow_share,
            b.case_open_rate,
            b.case_truth_rate,
            CAST(t.total_case_opened_rows - b.case_opened_rows AS DOUBLE)
                / NULLIF(t.total_flow_rows - b.flow_rows, 0) AS peer_case_open_rate,
            CAST(t.total_case_truth_rows - b.case_truth_rows AS DOUBLE)
                / NULLIF(t.total_case_opened_rows - b.case_opened_rows, 0) AS peer_case_truth_rate
        FROM band_totals b
        INNER JOIN month_totals t
            ON b.month_start_date = t.month_start_date
    )
    SELECT
        month_start_date,
        amount_band,
        flow_rows,
        flow_share,
        case_open_rate,
        case_truth_rate,
        peer_case_open_rate,
        peer_case_truth_rate,
        case_open_rate - peer_case_open_rate AS case_open_gap_to_peer,
        case_truth_rate - peer_case_truth_rate AS case_truth_gap_to_peer,
        ROW_NUMBER() OVER (
            PARTITION BY month_start_date
            ORDER BY
                case_open_rate - peer_case_open_rate DESC,
                case_truth_rate - peer_case_truth_rate ASC,
                flow_rows DESC
        ) AS priority_rank,
        CASE
            WHEN ROW_NUMBER() OVER (
                PARTITION BY month_start_date
                ORDER BY
                    case_open_rate - peer_case_open_rate DESC,
                    case_truth_rate - peer_case_truth_rate ASC,
                    flow_rows DESC
            ) = 1 THEN 1
            ELSE 0
        END AS priority_attention_flag
    FROM focused
    ORDER BY month_start_date, priority_rank
) TO $output_path (FORMAT PARQUET, COMPRESSION ZSTD);
