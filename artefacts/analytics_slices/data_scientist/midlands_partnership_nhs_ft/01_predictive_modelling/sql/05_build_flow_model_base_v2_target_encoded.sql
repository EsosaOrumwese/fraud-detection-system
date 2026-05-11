COPY (
    WITH base AS (
        SELECT *
        FROM parquet_scan($model_base_path)
    ),
    train_base AS (
        SELECT *
        FROM base
        WHERE split_role = 'train'
    ),
    global_rate AS (
        SELECT AVG(CASE WHEN target_is_fraud_truth THEN 1.0 ELSE 0.0 END) AS fraud_rate
        FROM train_base
    ),
    merchant_stats AS (
        SELECT
            merchant_id,
            COUNT(*) AS merchant_train_rows,
            SUM(CASE WHEN target_is_fraud_truth THEN 1 ELSE 0 END) AS merchant_train_fraud_rows
        FROM train_base
        GROUP BY merchant_id
    ),
    party_stats AS (
        SELECT
            party_id,
            COUNT(*) AS party_train_rows,
            SUM(CASE WHEN target_is_fraud_truth THEN 1 ELSE 0 END) AS party_train_fraud_rows
        FROM train_base
        GROUP BY party_id
    ),
    account_stats AS (
        SELECT
            account_id,
            COUNT(*) AS account_train_rows,
            SUM(CASE WHEN target_is_fraud_truth THEN 1 ELSE 0 END) AS account_train_fraud_rows
        FROM train_base
        GROUP BY account_id
    ),
    instrument_stats AS (
        SELECT
            instrument_id,
            COUNT(*) AS instrument_train_rows,
            SUM(CASE WHEN target_is_fraud_truth THEN 1 ELSE 0 END) AS instrument_train_fraud_rows
        FROM train_base
        GROUP BY instrument_id
    ),
    device_stats AS (
        SELECT
            device_id,
            COUNT(*) AS device_train_rows,
            SUM(CASE WHEN target_is_fraud_truth THEN 1 ELSE 0 END) AS device_train_fraud_rows
        FROM train_base
        GROUP BY device_id
    ),
    ip_stats AS (
        SELECT
            ip_id,
            COUNT(*) AS ip_train_rows,
            SUM(CASE WHEN target_is_fraud_truth THEN 1 ELSE 0 END) AS ip_train_fraud_rows
        FROM train_base
        GROUP BY ip_id
    )
    SELECT
        b.*,
        COALESCE((ms.merchant_train_fraud_rows + 50.0 * gr.fraud_rate) / NULLIF(ms.merchant_train_rows + 50.0, 0.0), gr.fraud_rate) AS merchant_train_fraud_rate,
        COALESCE((ps.party_train_fraud_rows + 50.0 * gr.fraud_rate) / NULLIF(ps.party_train_rows + 50.0, 0.0), gr.fraud_rate) AS party_train_fraud_rate,
        COALESCE((acs.account_train_fraud_rows + 50.0 * gr.fraud_rate) / NULLIF(acs.account_train_rows + 50.0, 0.0), gr.fraud_rate) AS account_train_fraud_rate,
        COALESCE((ins.instrument_train_fraud_rows + 50.0 * gr.fraud_rate) / NULLIF(ins.instrument_train_rows + 50.0, 0.0), gr.fraud_rate) AS instrument_train_fraud_rate,
        COALESCE((ds.device_train_fraud_rows + 50.0 * gr.fraud_rate) / NULLIF(ds.device_train_rows + 50.0, 0.0), gr.fraud_rate) AS device_train_fraud_rate,
        COALESCE((ips.ip_train_fraud_rows + 50.0 * gr.fraud_rate) / NULLIF(ips.ip_train_rows + 50.0, 0.0), gr.fraud_rate) AS ip_train_fraud_rate
    FROM base b
    CROSS JOIN global_rate gr
    LEFT JOIN merchant_stats ms
        ON b.merchant_id = ms.merchant_id
    LEFT JOIN party_stats ps
        ON b.party_id = ps.party_id
    LEFT JOIN account_stats acs
        ON b.account_id = acs.account_id
    LEFT JOIN instrument_stats ins
        ON b.instrument_id = ins.instrument_id
    LEFT JOIN device_stats ds
        ON b.device_id = ds.device_id
    LEFT JOIN ip_stats ips
        ON b.ip_id = ips.ip_id
) TO $model_base_v2_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
