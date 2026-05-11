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
            COALESCE(t.is_fraud_truth, FALSE) AS is_fraud_truth,
            COALESCE(b.is_fraud_bank_view, FALSE) AS is_fraud_bank_view,
            NTILE(10) OVER (ORDER BY e.first_event_ts_utc, e.flow_id) AS time_split_decile
        FROM event_flows e
        LEFT JOIN case_rollup c ON e.flow_id = c.flow_id
        LEFT JOIN parquet_scan($truth_files, filename := TRUE) t ON e.flow_id = t.flow_id
        LEFT JOIN parquet_scan($bank_files, filename := TRUE) b ON e.flow_id = b.flow_id
    ),
    overall_case_selected AS (
        SELECT
            CASE
                WHEN time_split_decile <= 6 THEN 'train'
                WHEN time_split_decile <= 8 THEN 'validation'
                ELSE 'test'
            END AS split_role,
            'overall_case_selected_yield' AS kpi_name,
            'all_case_selected_flows' AS kpi_scope,
            COUNT(*) FILTER (WHERE case_id IS NOT NULL) AS flow_rows,
            AVG(CASE WHEN case_id IS NOT NULL AND is_fraud_bank_view THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) AS raw_bank_view_rate,
            AVG(CASE WHEN case_id IS NOT NULL AND is_fraud_truth THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) AS corrected_truth_rate
        FROM base
        GROUP BY 1
    ),
    stage_case_selected AS (
        SELECT
            CASE
                WHEN time_split_decile <= 6 THEN 'train'
                WHEN time_split_decile <= 8 THEN 'validation'
                ELSE 'test'
            END AS split_role,
            'pathway_stage_yield' AS kpi_name,
            pathway_stage AS kpi_scope,
            COUNT(*) FILTER (WHERE case_id IS NOT NULL) AS flow_rows,
            AVG(CASE WHEN case_id IS NOT NULL AND is_fraud_bank_view THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) AS raw_bank_view_rate,
            AVG(CASE WHEN case_id IS NOT NULL AND is_fraud_truth THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) AS corrected_truth_rate
        FROM base
        WHERE case_id IS NOT NULL
        GROUP BY 1, 2, 3
    ),
    unioned AS (
        SELECT * FROM overall_case_selected
        UNION ALL
        SELECT * FROM stage_case_selected
    )
    SELECT
        split_role,
        kpi_name,
        kpi_scope,
        flow_rows,
        raw_bank_view_rate,
        corrected_truth_rate,
        raw_bank_view_rate - corrected_truth_rate AS absolute_gap,
        CASE
            WHEN corrected_truth_rate = 0 THEN NULL
            ELSE raw_bank_view_rate / corrected_truth_rate
        END AS inflation_ratio
    FROM unioned
    ORDER BY split_role, kpi_name, kpi_scope
) TO $flow_quality_kpi_before_after_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
