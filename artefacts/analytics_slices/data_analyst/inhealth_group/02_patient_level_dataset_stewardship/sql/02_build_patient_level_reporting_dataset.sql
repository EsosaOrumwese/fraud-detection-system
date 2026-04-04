COPY (
    WITH flow_month AS (
        SELECT
            flow_id,
            ts_utc::TIMESTAMP AS flow_ts_utc,
            amount,
            merchant_id,
            party_id,
            CASE
                WHEN amount < 10 THEN 'under_10'
                WHEN amount < 25 THEN '10_to_25'
                WHEN amount < 50 THEN '25_to_50'
                ELSE '50_plus'
            END AS amount_band
        FROM parquet_scan($flow_path)
        WHERE DATE_TRUNC('month', ts_utc::TIMESTAMP) = DATE '$current_month'
    ),
    case_roll AS (
        SELECT
            flow_id,
            MIN(case_id) AS case_id,
            MAX(CASE WHEN case_event_type = 'CASE_OPENED' THEN 1 ELSE 0 END) AS has_case_opened,
            COUNT(*) AS raw_case_event_rows
        FROM parquet_scan($case_path)
        GROUP BY 1
    ),
    truth_roll AS (
        SELECT
            flow_id,
            CAST(is_fraud_truth AS INTEGER) AS is_fraud_truth,
            fraud_label
        FROM parquet_scan($truth_path)
    )
    SELECT
        f.flow_id,
        f.flow_ts_utc,
        f.amount,
        f.amount_band,
        f.merchant_id,
        f.party_id,
        c.case_id,
        c.raw_case_event_rows,
        1 AS case_opened_flag,
        t.is_fraud_truth,
        t.fraud_label
    FROM flow_month f
    INNER JOIN case_roll c
        ON f.flow_id = c.flow_id
       AND c.has_case_opened = 1
    INNER JOIN truth_roll t
        ON f.flow_id = t.flow_id
) TO $output_path (FORMAT PARQUET, COMPRESSION ZSTD);
