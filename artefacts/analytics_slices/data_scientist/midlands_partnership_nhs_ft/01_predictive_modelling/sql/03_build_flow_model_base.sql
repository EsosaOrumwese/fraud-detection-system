COPY (
    WITH flow_anchor AS (
        SELECT
            flow_id,
            CAST(ts_utc AS TIMESTAMP) AS flow_ts_utc,
            amount,
            merchant_id,
            party_id,
            account_id,
            instrument_id,
            device_id,
            ip_id,
            arrival_seq
        FROM parquet_scan([$flow_anchor_files], filename := TRUE)
    ),
    flow_truth AS (
        SELECT
            flow_id,
            is_fraud_truth,
            fraud_label
        FROM parquet_scan([$flow_truth_files], filename := TRUE)
    ),
    flow_bank AS (
        SELECT
            flow_id,
            is_fraud_bank_view,
            bank_label
        FROM parquet_scan([$flow_bank_files], filename := TRUE)
    ),
    base AS (
        SELECT
            fa.flow_id,
            fa.flow_ts_utc,
            CAST(fa.flow_ts_utc AS DATE) AS flow_date_utc,
            EXTRACT('hour' FROM fa.flow_ts_utc) AS flow_hour_utc,
            EXTRACT('dow' FROM fa.flow_ts_utc) AS flow_dow_utc,
            EXTRACT('month' FROM fa.flow_ts_utc) AS flow_month_utc,
            fa.amount,
            LN(fa.amount + 1.0) AS log_amount,
            fa.arrival_seq,
            fa.merchant_id,
            fa.party_id,
            fa.account_id,
            fa.instrument_id,
            fa.device_id,
            fa.ip_id,
            ft.is_fraud_truth AS target_is_fraud_truth,
            ft.fraud_label,
            fb.is_fraud_bank_view,
            fb.bank_label,
            COUNT(*) OVER (PARTITION BY fa.merchant_id) AS merchant_flow_count,
            COUNT(*) OVER (PARTITION BY fa.party_id) AS party_flow_count,
            COUNT(*) OVER (PARTITION BY fa.account_id) AS account_flow_count,
            COUNT(*) OVER (PARTITION BY fa.instrument_id) AS instrument_flow_count,
            COUNT(*) OVER (PARTITION BY fa.device_id) AS device_flow_count,
            COUNT(*) OVER (PARTITION BY fa.ip_id) AS ip_flow_count
        FROM flow_anchor fa
        INNER JOIN flow_truth ft
            ON fa.flow_id = ft.flow_id
        LEFT JOIN flow_bank fb
            ON fa.flow_id = fb.flow_id
    ),
    ordered AS (
        SELECT
            *,
            NTILE(10) OVER (ORDER BY flow_ts_utc, flow_id) AS time_split_decile
        FROM base
    )
    SELECT
        *,
        CASE
            WHEN time_split_decile <= 6 THEN 'train'
            WHEN time_split_decile <= 8 THEN 'validation'
            ELSE 'test'
        END AS split_role
    FROM ordered
) TO $model_base_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
