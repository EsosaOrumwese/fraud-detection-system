COPY (
    SELECT
        case_id,
        flow_id,
        case_open_date_utc,
        case_opened_ts_utc,
        case_closed_ts_utc,
        chronology_rows,
        lifecycle_hours,
        lifecycle_bucket,
        pathway_stage,
        amount,
        amount_band,
        has_customer_dispute,
        has_chargeback_initiated,
        has_chargeback_decision,
        has_detection_event_attached,
        target_is_fraud_truth,
        fraud_label,
        is_fraud_bank_view,
        bank_label,
        split_role
    FROM parquet_scan($case_analytics_product_path)
) TO $case_reporting_ready_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
