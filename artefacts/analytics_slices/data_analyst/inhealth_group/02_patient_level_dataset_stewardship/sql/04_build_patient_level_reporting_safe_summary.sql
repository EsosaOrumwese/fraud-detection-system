COPY (
    WITH flow_month AS (
        SELECT
            CASE
                WHEN amount < 10 THEN 'under_10'
                WHEN amount < 25 THEN '10_to_25'
                WHEN amount < 50 THEN '25_to_50'
                ELSE '50_plus'
            END AS amount_band,
            COUNT(*) AS flow_rows
        FROM parquet_scan($flow_path)
        WHERE DATE_TRUNC('month', ts_utc::TIMESTAMP) = DATE '$current_month'
        GROUP BY 1
    ),
    maintained AS (
        SELECT *
        FROM read_parquet($dataset_path)
    ),
    by_band AS (
        SELECT
            amount_band,
            COUNT(*) AS case_opened_rows,
            SUM(is_fraud_truth) AS case_truth_rows
        FROM maintained
        GROUP BY 1
    ),
    detail AS (
        SELECT
            f.amount_band,
            f.flow_rows,
            COALESCE(b.case_opened_rows, 0) AS case_opened_rows,
            CAST(COALESCE(b.case_opened_rows, 0) AS DOUBLE) / NULLIF(f.flow_rows, 0) AS case_open_rate,
            COALESCE(b.case_truth_rows, 0) AS case_truth_rows,
            CAST(COALESCE(b.case_truth_rows, 0) AS DOUBLE) / NULLIF(COALESCE(b.case_opened_rows, 0), 0) AS case_truth_rate
        FROM flow_month f
        LEFT JOIN by_band b USING (amount_band)
    )
    SELECT
        amount_band,
        flow_rows,
        case_opened_rows,
        case_open_rate,
        case_truth_rows,
        case_truth_rate
    FROM detail

    UNION ALL

    SELECT
        '__overall__' AS amount_band,
        SUM(flow_rows) AS flow_rows,
        SUM(case_opened_rows) AS case_opened_rows,
        CAST(SUM(case_opened_rows) AS DOUBLE) / NULLIF(SUM(flow_rows), 0) AS case_open_rate,
        SUM(case_truth_rows) AS case_truth_rows,
        CAST(SUM(case_truth_rows) AS DOUBLE) / NULLIF(SUM(case_opened_rows), 0) AS case_truth_rate
    FROM detail
) TO $output_path (FORMAT PARQUET, COMPRESSION ZSTD);
