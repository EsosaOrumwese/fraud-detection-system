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
    ),
    joined AS (
        SELECT
            f.flow_id,
            f.flow_ts_utc,
            f.amount,
            f.amount_band,
            f.merchant_id,
            f.party_id,
            c.case_id,
            c.has_case_opened,
            c.raw_case_event_rows,
            t.is_fraud_truth,
            t.fraud_label
        FROM flow_month f
        LEFT JOIN case_roll c USING (flow_id)
        LEFT JOIN truth_roll t USING (flow_id)
    ),
    by_band AS (
        SELECT
            amount_band,
            COUNT(*) AS flow_rows,
            SUM(CASE WHEN case_id IS NOT NULL THEN 1 ELSE 0 END) AS case_linked_rows,
            SUM(COALESCE(has_case_opened, 0)) AS case_opened_rows,
            SUM(CASE WHEN case_id IS NOT NULL THEN raw_case_event_rows ELSE 0 END) AS raw_case_event_rows_on_linked_flows,
            SUM(COALESCE(is_fraud_truth, 0)) AS truth_rows,
            AVG(CASE WHEN case_id IS NOT NULL THEN CAST(raw_case_event_rows AS DOUBLE) END) AS avg_case_event_rows_when_linked
        FROM joined
        GROUP BY 1
    ),
    overall AS (
        SELECT
            '__overall__' AS amount_band,
            COUNT(*) AS flow_rows,
            SUM(CASE WHEN case_id IS NOT NULL THEN 1 ELSE 0 END) AS case_linked_rows,
            SUM(COALESCE(has_case_opened, 0)) AS case_opened_rows,
            SUM(CASE WHEN case_id IS NOT NULL THEN raw_case_event_rows ELSE 0 END) AS raw_case_event_rows_on_linked_flows,
            SUM(COALESCE(is_fraud_truth, 0)) AS truth_rows,
            AVG(CASE WHEN case_id IS NOT NULL THEN CAST(raw_case_event_rows AS DOUBLE) END) AS avg_case_event_rows_when_linked
        FROM joined
    )
    SELECT
        amount_band,
        flow_rows,
        case_linked_rows,
        case_opened_rows,
        raw_case_event_rows_on_linked_flows,
        truth_rows,
        avg_case_event_rows_when_linked
    FROM by_band
    UNION ALL
    SELECT
        amount_band,
        flow_rows,
        case_linked_rows,
        case_opened_rows,
        raw_case_event_rows_on_linked_flows,
        truth_rows,
        avg_case_event_rows_when_linked
    FROM overall
) TO $output_path (FORMAT PARQUET, COMPRESSION ZSTD);
