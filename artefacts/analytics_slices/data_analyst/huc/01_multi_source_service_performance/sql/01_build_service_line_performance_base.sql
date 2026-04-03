COPY (
WITH flow_window AS (
    SELECT
        flow_id,
        ts_utc::TIMESTAMP AS flow_ts,
        DATE_TRUNC('week', ts_utc::TIMESTAMP) AS week_start,
        CASE
            WHEN DATE_TRUNC('week', ts_utc::TIMESTAMP) = TIMESTAMP '$current_week'
                THEN 'current'
            ELSE 'prior'
        END AS week_role,
        amount,
        CASE
            WHEN amount < 10 THEN 'under_10'
            WHEN amount < 25 THEN '10_to_25'
            WHEN amount < 50 THEN '25_to_50'
            ELSE '50_plus'
        END AS amount_band
    FROM parquet_scan($flow_path)
    WHERE DATE_TRUNC('week', ts_utc::TIMESTAMP) IN (
        TIMESTAMP '$prior_week',
        TIMESTAMP '$current_week'
    )
),
event_rollup AS (
    SELECT
        e.flow_id,
        COUNT(*) AS event_rows,
        COUNT(DISTINCT e.event_type) AS event_type_count
    FROM parquet_scan($event_path) e
    WHERE e.flow_id IN (SELECT flow_id FROM flow_window)
    GROUP BY e.flow_id
),
case_rollup AS (
    SELECT
        c.flow_id,
        MIN(CASE WHEN c.case_event_type = 'CASE_OPENED' THEN c.ts_utc::TIMESTAMP END) AS case_opened_ts,
        MAX(CASE WHEN c.case_event_type = 'CASE_CLOSED' THEN c.ts_utc::TIMESTAMP END) AS case_closed_ts,
        MAX(CASE WHEN c.case_event_type = 'CHARGEBACK_DECISION' THEN 1 ELSE 0 END) AS has_chargeback_decision,
        MAX(CASE WHEN c.case_event_type = 'CUSTOMER_DISPUTE_FILED' THEN 1 ELSE 0 END) AS has_customer_dispute,
        MAX(CASE WHEN c.case_event_type = 'DETECTION_EVENT_ATTACHED' THEN 1 ELSE 0 END) AS has_detection_event,
        COUNT(DISTINCT c.case_id) AS case_count
    FROM parquet_scan($case_path) c
    WHERE c.flow_id IN (SELECT flow_id FROM flow_window)
    GROUP BY c.flow_id
),
truth AS (
    SELECT
        flow_id,
        is_fraud_truth
    FROM parquet_scan($truth_path)
    WHERE flow_id IN (SELECT flow_id FROM flow_window)
),
bank AS (
    SELECT
        flow_id,
        is_fraud_bank_view
    FROM parquet_scan($bank_path)
    WHERE flow_id IN (SELECT flow_id FROM flow_window)
)
SELECT
    f.week_role,
    CAST(f.week_start AS DATE) AS week_start_date,
    f.flow_id,
    f.flow_ts,
    f.amount,
    f.amount_band,
    COALESCE(e.event_rows, 0) AS event_rows,
    COALESCE(e.event_type_count, 0) AS event_type_count,
    CASE WHEN e.flow_id IS NOT NULL THEN 1 ELSE 0 END AS event_link_flag,
    CASE WHEN c.flow_id IS NOT NULL THEN 1 ELSE 0 END AS case_row_link_flag,
    CASE WHEN t.flow_id IS NOT NULL THEN 1 ELSE 0 END AS truth_link_flag,
    CASE WHEN b.flow_id IS NOT NULL THEN 1 ELSE 0 END AS bank_link_flag,
    CASE WHEN c.case_opened_ts IS NOT NULL THEN 1 ELSE 0 END AS has_case_opened,
    c.case_count,
    c.case_opened_ts,
    c.case_closed_ts,
    CASE
        WHEN c.case_opened_ts IS NULL THEN 'no_case'
        WHEN c.has_chargeback_decision = 1 THEN 'chargeback_decision'
        WHEN c.has_customer_dispute = 1 THEN 'customer_dispute'
        WHEN c.has_detection_event = 1 THEN 'detection_event_attached'
        ELSE 'opened_only'
    END AS pathway_stage,
    CASE
        WHEN c.case_opened_ts IS NOT NULL
            THEN DATE_DIFF('hour', f.flow_ts, COALESCE(c.case_closed_ts, TIMESTAMP '$analysis_end'))
        ELSE NULL
    END AS lifecycle_hours,
    CASE
        WHEN c.case_opened_ts IS NOT NULL
             AND DATE_DIFF('hour', f.flow_ts, COALESCE(c.case_closed_ts, TIMESTAMP '$analysis_end')) >= 168
            THEN 1
        ELSE 0
    END AS long_lifecycle_flag,
    CASE
        WHEN c.case_opened_ts IS NOT NULL
             AND DATE_DIFF('hour', f.flow_ts, COALESCE(c.case_closed_ts, TIMESTAMP '$analysis_end')) >= 336
            THEN 1
        ELSE 0
    END AS very_long_lifecycle_flag,
    COALESCE(CAST(t.is_fraud_truth AS INTEGER), 0) AS is_fraud_truth,
    COALESCE(CAST(b.is_fraud_bank_view AS INTEGER), 0) AS is_fraud_bank_view,
    CASE
        WHEN c.case_opened_ts IS NOT NULL
             AND t.flow_id IS NOT NULL
             AND b.flow_id IS NOT NULL
             AND t.is_fraud_truth <> b.is_fraud_bank_view
            THEN 1
        ELSE 0
    END AS truth_bank_mismatch_flag
FROM flow_window f
LEFT JOIN event_rollup e USING (flow_id)
LEFT JOIN case_rollup c USING (flow_id)
LEFT JOIN truth t USING (flow_id)
LEFT JOIN bank b USING (flow_id)
) TO $service_line_base_output (FORMAT PARQUET, COMPRESSION ZSTD);
