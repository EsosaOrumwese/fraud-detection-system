WITH event_flows AS (
    SELECT
        flow_id,
        MIN(CAST(ts_utc AS TIMESTAMP)) AS first_event_ts_utc
    FROM parquet_scan($event_files, filename := TRUE)
    GROUP BY 1
),
case_rollup AS (
    SELECT
        flow_id,
        MIN(case_id) AS case_id,
        MAX(CASE WHEN case_event_type = 'CUSTOMER_DISPUTE_FILED' THEN 1 ELSE 0 END) AS has_customer_dispute,
        MAX(CASE WHEN case_event_type = 'CHARGEBACK_INITIATED' THEN 1 ELSE 0 END) AS has_chargeback_initiated,
        MAX(CASE WHEN case_event_type = 'CHARGEBACK_DECISION' THEN 1 ELSE 0 END) AS has_chargeback_decision,
        MAX(CASE WHEN case_event_type = 'DETECTION_EVENT_ATTACHED' THEN 1 ELSE 0 END) AS has_detection_event_attached
    FROM parquet_scan($case_files, filename := TRUE)
    GROUP BY 1
),
base AS (
    SELECT
        e.flow_id,
        c.case_id,
        CASE
            WHEN COALESCE(c.has_chargeback_decision, 0) = 1 THEN 'chargeback_decision'
            WHEN COALESCE(c.has_chargeback_initiated, 0) = 1 THEN 'chargeback_initiated'
            WHEN COALESCE(c.has_customer_dispute, 0) = 1 THEN 'customer_dispute'
            WHEN COALESCE(c.has_detection_event_attached, 0) = 1 THEN 'detection_event_attached'
            WHEN c.case_id IS NOT NULL THEN 'opened_only'
            ELSE 'no_case'
        END AS pathway_stage,
        COALESCE(t.is_fraud_truth, FALSE) AS is_fraud_truth,
        t.fraud_label,
        COALESCE(b.is_fraud_bank_view, FALSE) AS is_fraud_bank_view,
        b.bank_label,
        CASE
            WHEN COALESCE(t.is_fraud_truth, FALSE) AND COALESCE(b.is_fraud_bank_view, FALSE) THEN 'truth_positive_bank_positive'
            WHEN COALESCE(t.is_fraud_truth, FALSE) AND NOT COALESCE(b.is_fraud_bank_view, FALSE) THEN 'truth_positive_bank_negative'
            WHEN NOT COALESCE(t.is_fraud_truth, FALSE) AND COALESCE(b.is_fraud_bank_view, FALSE) THEN 'truth_negative_bank_positive'
            ELSE 'truth_negative_bank_negative'
        END AS mismatch_class,
        NTILE(10) OVER (ORDER BY e.first_event_ts_utc, e.flow_id) AS time_split_decile
    FROM event_flows e
    LEFT JOIN case_rollup c ON e.flow_id = c.flow_id
    LEFT JOIN parquet_scan($truth_files, filename := TRUE) t ON e.flow_id = t.flow_id
    LEFT JOIN parquet_scan($bank_files, filename := TRUE) b ON e.flow_id = b.flow_id
)
SELECT
    CASE
        WHEN time_split_decile <= 6 THEN 'train'
        WHEN time_split_decile <= 8 THEN 'validation'
        ELSE 'test'
    END AS split_role,
    pathway_stage,
    mismatch_class,
    COUNT(*) FILTER (WHERE case_id IS NOT NULL) AS case_selected_flows,
    AVG(CASE WHEN case_id IS NOT NULL AND is_fraud_truth THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) AS truth_yield,
    AVG(CASE WHEN case_id IS NOT NULL AND is_fraud_bank_view THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) AS bank_yield,
    AVG(CASE WHEN case_id IS NOT NULL AND is_fraud_truth <> is_fraud_bank_view THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) AS mismatch_rate
FROM base
WHERE case_id IS NOT NULL
GROUP BY 1, 2, 3
HAVING COUNT(*) FILTER (WHERE case_id IS NOT NULL) > 0
ORDER BY split_role, pathway_stage, case_selected_flows DESC, mismatch_class
;
