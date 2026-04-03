COPY (
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
            COALESCE(t.is_fraud_truth, FALSE) AS authoritative_outcome_rate_flag,
            COALESCE(b.is_fraud_bank_view, FALSE) AS comparison_outcome_rate_flag,
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
        COUNT(*) FILTER (WHERE case_id IS NOT NULL) AS case_selected_flows,
        AVG(CASE WHEN case_id IS NOT NULL AND comparison_outcome_rate_flag THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) AS comparison_outcome_rate,
        AVG(CASE WHEN case_id IS NOT NULL AND authoritative_outcome_rate_flag THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) AS authoritative_outcome_rate,
        AVG(CASE WHEN case_id IS NOT NULL AND comparison_outcome_rate_flag <> authoritative_outcome_rate_flag THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) AS mismatch_rate,
        'authoritative_outcome_rate comes from s4_flow_truth_labels_6B; comparison_outcome_rate is bank-view only and must not replace truth in yield KPIs' AS source_rule_note
    FROM base
    WHERE case_id IS NOT NULL
    GROUP BY 1, 2
    ORDER BY split_role, pathway_stage
) TO $flow_quality_reporting_ready_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
