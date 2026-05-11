COPY (
    SELECT
        split_role,
        selected_model_name,
        priority_rank,
        priority_decile,
        flow_id,
        flow_ts_utc,
        predicted_probability,
        risk_band,
        cohort_label,
        pathway_stage,
        target_is_fraud_truth,
        fraud_label,
        has_case_opened,
        is_case_selected,
        lifecycle_hours,
        hours_event_to_case_open,
        amount,
        amount_band,
        merchant_id,
        party_id,
        device_id,
        merchant_train_fraud_rate,
        party_train_fraud_rate,
        device_train_fraud_rate
    FROM parquet_scan($dashboard_base_path)
    WHERE split_role = 'test'
      AND risk_band IN ('High', 'Medium')
) TO $dashboard_drillthrough_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
