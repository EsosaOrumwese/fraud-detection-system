COPY (
    WITH selected_scores AS (
        SELECT
            'validation' AS split_role,
            flow_id,
            CAST(flow_ts_utc AS TIMESTAMP) AS flow_ts_utc,
            target_is_fraud_truth,
            fraud_label,
            is_fraud_bank_view,
            bank_label,
            has_case_opened,
            predicted_probability,
            risk_band
        FROM parquet_scan($validation_scores_path)

        UNION ALL

        SELECT
            'test' AS split_role,
            flow_id,
            CAST(flow_ts_utc AS TIMESTAMP) AS flow_ts_utc,
            target_is_fraud_truth,
            fraud_label,
            is_fraud_bank_view,
            bank_label,
            has_case_opened,
            predicted_probability,
            risk_band
        FROM parquet_scan($test_scores_path)
    ),
    pathway_thresholds AS (
        SELECT
            MEDIAN(lifecycle_hours) FILTER (WHERE target_is_fraud_truth = TRUE) AS positive_lifecycle_median_hours,
            MEDIAN(lifecycle_hours) FILTER (WHERE COALESCE(target_is_fraud_truth, FALSE) = FALSE) AS negative_lifecycle_median_hours
        FROM parquet_scan($population_pathway_base_path)
        WHERE is_case_selected = 1
          AND lifecycle_hours IS NOT NULL
    ),
    pathway_context AS (
        SELECT
            p.flow_id,
            p.split_role,
            p.case_id,
            p.is_case_selected,
            p.pathway_stage,
            p.lifecycle_hours,
            p.hours_event_to_case_open,
            p.amount_band,
            CASE
                WHEN p.is_case_selected = 0 THEN 'not_case_selected'
                WHEN p.target_is_fraud_truth = TRUE
                     AND p.lifecycle_hours <= t.positive_lifecycle_median_hours
                THEN 'fast_converting_high_yield'
                WHEN p.target_is_fraud_truth = TRUE
                THEN 'slow_converting_high_yield'
                WHEN COALESCE(p.target_is_fraud_truth, FALSE) = FALSE
                     AND p.lifecycle_hours > t.negative_lifecycle_median_hours
                THEN 'high_burden_low_yield'
                ELSE 'low_burden_low_yield'
            END AS cohort_label
        FROM parquet_scan($population_pathway_base_path) p
        CROSS JOIN pathway_thresholds t
        WHERE p.split_role IN ('validation', 'test')
    ),
    model_context AS (
        SELECT
            flow_id,
            split_role,
            flow_date_utc,
            flow_hour_utc,
            flow_dow_utc,
            flow_month_utc,
            amount,
            merchant_id,
            party_id,
            account_id,
            instrument_id,
            device_id,
            ip_id,
            merchant_train_fraud_rate,
            party_train_fraud_rate,
            account_train_fraud_rate,
            instrument_train_fraud_rate,
            device_train_fraud_rate,
            ip_train_fraud_rate
        FROM parquet_scan($model_base_path)
        WHERE split_role IN ('validation', 'test')
    )
    SELECT
        ss.split_role,
        'challenger_logistic_encoded_history' AS selected_model_name,
        ss.flow_id,
        ss.flow_ts_utc,
        CAST(ss.flow_ts_utc AS DATE) AS flow_date_utc,
        DATE_TRUNC('week', ss.flow_ts_utc) AS flow_week_utc,
        ss.predicted_probability,
        ss.risk_band,
        CASE ss.risk_band
            WHEN 'High' THEN 1
            WHEN 'Medium' THEN 2
            ELSE 3
        END AS risk_band_order,
        ROW_NUMBER() OVER (
            PARTITION BY ss.split_role
            ORDER BY ss.predicted_probability DESC, ss.flow_id
        ) AS priority_rank,
        NTILE(10) OVER (
            PARTITION BY ss.split_role
            ORDER BY ss.predicted_probability DESC, ss.flow_id
        ) AS priority_decile,
        mc.amount,
        COALESCE(pc.amount_band,
            CASE
                WHEN mc.amount < 25 THEN 'lt_25'
                WHEN mc.amount < 75 THEN '25_to_75'
                WHEN mc.amount < 150 THEN '75_to_150'
                ELSE 'gte_150'
            END
        ) AS amount_band,
        ss.target_is_fraud_truth,
        ss.fraud_label,
        ss.is_fraud_bank_view,
        ss.bank_label,
        ss.has_case_opened,
        COALESCE(pc.case_id, NULL) AS case_id,
        COALESCE(pc.is_case_selected, CASE WHEN ss.has_case_opened = 1 THEN 1 ELSE 0 END) AS is_case_selected,
        COALESCE(pc.pathway_stage, CASE WHEN ss.has_case_opened = 1 THEN 'opened_only' ELSE 'no_case' END) AS pathway_stage,
        COALESCE(pc.cohort_label, 'not_case_selected') AS cohort_label,
        pc.lifecycle_hours,
        pc.hours_event_to_case_open,
        mc.flow_hour_utc,
        mc.flow_dow_utc,
        mc.flow_month_utc,
        mc.merchant_id,
        mc.party_id,
        mc.account_id,
        mc.instrument_id,
        mc.device_id,
        mc.ip_id,
        mc.merchant_train_fraud_rate,
        mc.party_train_fraud_rate,
        mc.account_train_fraud_rate,
        mc.instrument_train_fraud_rate,
        mc.device_train_fraud_rate,
        mc.ip_train_fraud_rate
    FROM selected_scores ss
    LEFT JOIN model_context mc
      ON ss.flow_id = mc.flow_id
     AND ss.split_role = mc.split_role
    LEFT JOIN pathway_context pc
      ON ss.flow_id = pc.flow_id
     AND ss.split_role = pc.split_role
) TO $dashboard_base_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
