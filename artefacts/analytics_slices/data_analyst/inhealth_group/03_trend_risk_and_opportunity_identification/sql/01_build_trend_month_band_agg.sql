COPY (
    WITH flow_month AS (
        SELECT
            flow_id,
            DATE_TRUNC('month', ts_utc::TIMESTAMP) AS month_start,
            CASE
                WHEN amount < 10 THEN 'under_10'
                WHEN amount < 25 THEN '10_to_25'
                WHEN amount < 50 THEN '25_to_50'
                ELSE '50_plus'
            END AS amount_band
        FROM parquet_scan($flow_path)
        WHERE DATE_TRUNC('month', ts_utc::TIMESTAMP) IN (
            DATE '$month_1',
            DATE '$month_2',
            DATE '$month_3'
        )
    ),
    case_roll AS (
        SELECT
            flow_id,
            MAX(CASE WHEN case_event_type = 'CASE_OPENED' THEN 1 ELSE 0 END) AS has_case_opened
        FROM parquet_scan($case_path)
        GROUP BY 1
    ),
    truth_roll AS (
        SELECT
            flow_id,
            CAST(MAX(CAST(is_fraud_truth AS INTEGER)) AS INTEGER) AS is_fraud_truth
        FROM parquet_scan($truth_path)
        GROUP BY 1
    )
    SELECT
        CAST(f.month_start AS DATE) AS month_start_date,
        f.amount_band,
        COUNT(*) AS flow_rows,
        SUM(COALESCE(c.has_case_opened, 0)) AS case_opened_rows,
        SUM(
            CASE
                WHEN COALESCE(c.has_case_opened, 0) = 1 THEN COALESCE(t.is_fraud_truth, 0)
                ELSE 0
            END
        ) AS case_truth_rows
    FROM flow_month f
    LEFT JOIN case_roll c USING (flow_id)
    LEFT JOIN truth_roll t USING (flow_id)
    GROUP BY 1, 2
    ORDER BY month_start_date, amount_band
) TO $output_path (FORMAT PARQUET, COMPRESSION ZSTD);
