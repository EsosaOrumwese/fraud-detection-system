COPY (
    WITH flow_month AS (
        SELECT
            flow_id,
            ts_utc::TIMESTAMP AS flow_ts_utc,
            amount,
            merchant_id,
            party_id
        FROM parquet_scan($flow_path)
        WHERE DATE_TRUNC('month', ts_utc::TIMESTAMP) = DATE '$current_month'
    ),
    truth_roll AS (
        SELECT
            flow_id,
            CAST(is_fraud_truth AS INTEGER) AS is_fraud_truth,
            fraud_label
        FROM parquet_scan($truth_path)
    ),
    truth_uniqueness AS (
        SELECT COUNT(*) - COUNT(DISTINCT flow_id) AS duplicate_flow_rows
        FROM parquet_scan($truth_path)
    ),
    maintained AS (
        SELECT *
        FROM read_parquet($dataset_path)
    )
    SELECT
        'march_flow_ids_unique' AS check_name,
        CAST(COUNT(*) - COUNT(DISTINCT flow_id) AS DOUBLE) AS actual_value,
        '= 0 duplicate monthly flow rows' AS expected_rule,
        CASE WHEN COUNT(*) - COUNT(DISTINCT flow_id) = 0 THEN 1 ELSE 0 END AS passed_flag
    FROM flow_month

    UNION ALL

    SELECT
        'truth_surface_unique_flow_ids' AS check_name,
        CAST(duplicate_flow_rows AS DOUBLE) AS actual_value,
        '= 0 duplicate truth flow rows' AS expected_rule,
        CASE WHEN duplicate_flow_rows = 0 THEN 1 ELSE 0 END AS passed_flag
    FROM truth_uniqueness

    UNION ALL

    SELECT
        'maintained_dataset_unique_flow_ids' AS check_name,
        CAST(COUNT(*) - COUNT(DISTINCT flow_id) AS DOUBLE) AS actual_value,
        '= 0 duplicate maintained flow rows' AS expected_rule,
        CASE WHEN COUNT(*) - COUNT(DISTINCT flow_id) = 0 THEN 1 ELSE 0 END AS passed_flag
    FROM maintained

    UNION ALL

    SELECT
        'maintained_dataset_required_fields_complete' AS check_name,
        CAST(
            SUM(
                CASE
                    WHEN flow_id IS NULL OR case_id IS NULL OR amount IS NULL OR amount_band IS NULL
                         OR merchant_id IS NULL OR party_id IS NULL OR is_fraud_truth IS NULL OR fraud_label IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS DOUBLE
        ) AS actual_value,
        '= 0 rows with null required fields' AS expected_rule,
        CASE
            WHEN SUM(
                CASE
                    WHEN flow_id IS NULL OR case_id IS NULL OR amount IS NULL OR amount_band IS NULL
                         OR merchant_id IS NULL OR party_id IS NULL OR is_fraud_truth IS NULL OR fraud_label IS NULL
                    THEN 1
                    ELSE 0
                END
            ) = 0 THEN 1
            ELSE 0
        END AS passed_flag
    FROM maintained

    UNION ALL

    SELECT
        'maintained_dataset_case_opened_only' AS check_name,
        CAST(SUM(CASE WHEN case_opened_flag <> 1 THEN 1 ELSE 0 END) AS DOUBLE) AS actual_value,
        '= 0 rows outside the case-opened maintained grain' AS expected_rule,
        CASE WHEN SUM(CASE WHEN case_opened_flag <> 1 THEN 1 ELSE 0 END) = 0 THEN 1 ELSE 0 END AS passed_flag
    FROM maintained
) TO $output_path (FORMAT PARQUET, COMPRESSION ZSTD);
