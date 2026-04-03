COPY (
    SELECT
        case_id,
        flow_id,
        case_opened_ts_utc,
        case_open_date_utc,
        case_open_hour_utc,
        case_open_dow_utc,
        case_open_month_utc,
        chronology_rows,
        max_case_event_seq,
        lifecycle_hours,
        has_customer_dispute,
        has_chargeback_initiated,
        has_chargeback_decision,
        has_detection_event_attached,
        arrival_seq,
        amount,
        log_amount,
        merchant_id,
        party_id,
        account_id,
        instrument_id,
        device_id,
        ip_id,
        target_is_fraud_truth,
        fraud_label,
        is_fraud_bank_view,
        bank_label,
        split_role
    FROM parquet_scan($case_analytics_product_path)
) TO $case_model_ready_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
