COPY (
    WITH chronology AS (
        SELECT *
        FROM parquet_scan($case_chronology_rollup_path)
    ),
    flow_anchor AS (
        SELECT
            flow_id,
            arrival_seq,
            merchant_id,
            party_id,
            account_id,
            instrument_id,
            device_id,
            ip_id,
            CAST(ts_utc AS TIMESTAMP) AS flow_ts_utc,
            amount
        FROM parquet_scan($anchor_files, filename := TRUE)
    ),
    flow_truth AS (
        SELECT
            flow_id,
            is_fraud_truth,
            fraud_label
        FROM parquet_scan($truth_files, filename := TRUE)
    ),
    flow_bank AS (
        SELECT
            flow_id,
            is_fraud_bank_view,
            bank_label
        FROM parquet_scan($bank_files, filename := TRUE)
    ),
    base AS (
        SELECT
            ch.case_id,
            ch.flow_id,
            ch.chronology_rows,
            ch.first_case_ts_utc,
            ch.last_case_ts_utc,
            ch.case_opened_ts_utc,
            ch.case_closed_ts_utc,
            CAST(ch.case_opened_ts_utc AS DATE) AS case_open_date_utc,
            EXTRACT('hour' FROM ch.case_opened_ts_utc) AS case_open_hour_utc,
            EXTRACT('dow' FROM ch.case_opened_ts_utc) AS case_open_dow_utc,
            EXTRACT('month' FROM ch.case_opened_ts_utc) AS case_open_month_utc,
            ch.max_case_event_seq,
            ch.has_case_opened,
            ch.has_case_closed,
            ch.has_customer_dispute,
            ch.has_chargeback_initiated,
            ch.has_chargeback_decision,
            ch.has_detection_event_attached,
            ch.lifecycle_hours,
            CASE
                WHEN ch.lifecycle_hours < 24 THEN 'lt_1d'
                WHEN ch.lifecycle_hours < 72 THEN '1d_to_3d'
                WHEN ch.lifecycle_hours < 168 THEN '3d_to_7d'
                WHEN ch.lifecycle_hours < 720 THEN '7d_to_30d'
                ELSE 'gte_30d'
            END AS lifecycle_bucket,
            fa.arrival_seq,
            fa.amount,
            LN(fa.amount + 1.0) AS log_amount,
            fa.merchant_id,
            fa.party_id,
            fa.account_id,
            fa.instrument_id,
            fa.device_id,
            fa.ip_id,
            fa.flow_ts_utc,
            ft.is_fraud_truth AS target_is_fraud_truth,
            ft.fraud_label,
            fb.is_fraud_bank_view,
            fb.bank_label
        FROM chronology ch
        LEFT JOIN flow_anchor fa
            ON ch.flow_id = fa.flow_id
        LEFT JOIN flow_truth ft
            ON ch.flow_id = ft.flow_id
        LEFT JOIN flow_bank fb
            ON ch.flow_id = fb.flow_id
    ),
    ordered AS (
        SELECT
            *,
            NTILE(10) OVER (ORDER BY case_opened_ts_utc, case_id) AS time_split_decile
        FROM base
    )
    SELECT
        *,
        CASE
            WHEN amount < 100 THEN 'lt_100'
            WHEN amount < 500 THEN '100_to_500'
            WHEN amount < 1000 THEN '500_to_1000'
            ELSE 'gte_1000'
        END AS amount_band,
        CASE
            WHEN has_chargeback_decision = 1 THEN 'chargeback_decision'
            WHEN has_chargeback_initiated = 1 THEN 'chargeback_initiated'
            WHEN has_customer_dispute = 1 THEN 'customer_dispute'
            WHEN has_detection_event_attached = 1 THEN 'detection_event_attached'
            ELSE 'opened_only'
        END AS pathway_stage,
        CASE
            WHEN time_split_decile <= 6 THEN 'train'
            WHEN time_split_decile <= 8 THEN 'validation'
            ELSE 'test'
        END AS split_role
    FROM ordered
) TO $case_analytics_product_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
