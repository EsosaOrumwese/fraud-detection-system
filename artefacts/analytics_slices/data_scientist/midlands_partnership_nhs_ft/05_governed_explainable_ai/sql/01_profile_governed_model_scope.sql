WITH flow_anchor AS (
    SELECT
        flow_id,
        CAST(ts_utc AS TIMESTAMP) AS flow_ts_utc,
        amount,
        arrival_seq,
        merchant_id,
        party_id,
        account_id,
        instrument_id,
        device_id,
        ip_id
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
case_opened AS (
    SELECT DISTINCT
        flow_id
    FROM parquet_scan([$case_files], filename := TRUE)
    WHERE case_event_type = 'CASE_OPENED'
),
joined AS (
    SELECT
        fa.flow_id,
        fa.flow_ts_utc,
        fa.amount,
        fa.arrival_seq,
        fa.merchant_id,
        fa.party_id,
        fa.account_id,
        fa.instrument_id,
        fa.device_id,
        fa.ip_id,
        ft.is_fraud_truth,
        ft.fraud_label,
        fb.is_fraud_bank_view,
        fb.bank_label,
        CASE WHEN co.flow_id IS NOT NULL THEN 1 ELSE 0 END AS has_case_opened
    FROM flow_anchor fa
    INNER JOIN flow_truth ft
        ON fa.flow_id = ft.flow_id
    LEFT JOIN flow_bank fb
        ON fa.flow_id = fb.flow_id
    LEFT JOIN case_opened co
        ON fa.flow_id = co.flow_id
)
SELECT
    COUNT(*) AS flow_rows,
    COUNT(DISTINCT flow_id) AS distinct_flow_id,
    MIN(flow_ts_utc) AS min_flow_ts_utc,
    MAX(flow_ts_utc) AS max_flow_ts_utc,
    AVG(CASE WHEN is_fraud_truth THEN 1.0 ELSE 0.0 END) AS fraud_truth_rate,
    AVG(CASE WHEN is_fraud_bank_view THEN 1.0 ELSE 0.0 END) AS bank_view_rate,
    AVG(CASE WHEN has_case_opened = 1 THEN 1.0 ELSE 0.0 END) AS case_open_rate,
    AVG(CASE WHEN is_fraud_bank_view IS DISTINCT FROM is_fraud_truth THEN 1.0 ELSE 0.0 END) AS truth_bank_mismatch_rate,
    AVG(CASE WHEN amount IS NULL THEN 1.0 ELSE 0.0 END) AS amount_null_rate,
    AVG(CASE WHEN arrival_seq IS NULL THEN 1.0 ELSE 0.0 END) AS arrival_seq_null_rate,
    AVG(CASE WHEN merchant_id IS NULL THEN 1.0 ELSE 0.0 END) AS merchant_id_null_rate,
    AVG(CASE WHEN party_id IS NULL THEN 1.0 ELSE 0.0 END) AS party_id_null_rate,
    AVG(CASE WHEN account_id IS NULL THEN 1.0 ELSE 0.0 END) AS account_id_null_rate,
    AVG(CASE WHEN instrument_id IS NULL THEN 1.0 ELSE 0.0 END) AS instrument_id_null_rate,
    AVG(CASE WHEN device_id IS NULL THEN 1.0 ELSE 0.0 END) AS device_id_null_rate,
    AVG(CASE WHEN ip_id IS NULL THEN 1.0 ELSE 0.0 END) AS ip_id_null_rate
FROM joined;
