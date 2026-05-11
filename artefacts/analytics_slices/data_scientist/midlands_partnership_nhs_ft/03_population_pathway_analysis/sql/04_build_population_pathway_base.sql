COPY (
    WITH event_flows AS (
        SELECT
            flow_id,
            MIN(CAST(ts_utc AS TIMESTAMP)) AS first_event_ts_utc,
            MAX(CAST(ts_utc AS TIMESTAMP)) AS last_event_ts_utc,
            COUNT(*) AS event_rows,
            SUM(CASE WHEN event_type = 'AUTH_REQUEST' THEN 1 ELSE 0 END) AS auth_request_rows,
            SUM(CASE WHEN event_type = 'AUTH_RESPONSE' THEN 1 ELSE 0 END) AS auth_response_rows,
            DATEDIFF(
                'second',
                MIN(CAST(ts_utc AS TIMESTAMP)),
                MAX(CAST(ts_utc AS TIMESTAMP))
            ) AS auth_cycle_seconds
        FROM parquet_scan($event_files, filename := TRUE)
        GROUP BY 1
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
    case_rollup AS (
        SELECT
            flow_id,
            MIN(case_id) AS case_id,
            COUNT(DISTINCT case_id) AS distinct_cases,
            MIN(CAST(ts_utc AS TIMESTAMP)) FILTER (WHERE case_event_type = 'CASE_OPENED') AS case_opened_ts_utc,
            MAX(CAST(ts_utc AS TIMESTAMP)) FILTER (WHERE case_event_type = 'CASE_CLOSED') AS case_closed_ts_utc,
            MAX(CAST(ts_utc AS TIMESTAMP)) AS last_case_ts_utc,
            COUNT(*) AS case_event_rows,
            MAX(case_event_seq) AS max_case_event_seq,
            MAX(CASE WHEN case_event_type = 'CASE_OPENED' THEN 1 ELSE 0 END) AS has_case_opened,
            MAX(CASE WHEN case_event_type = 'CASE_CLOSED' THEN 1 ELSE 0 END) AS has_case_closed,
            MAX(CASE WHEN case_event_type = 'CUSTOMER_DISPUTE_FILED' THEN 1 ELSE 0 END) AS has_customer_dispute,
            MAX(CASE WHEN case_event_type = 'CHARGEBACK_INITIATED' THEN 1 ELSE 0 END) AS has_chargeback_initiated,
            MAX(CASE WHEN case_event_type = 'CHARGEBACK_DECISION' THEN 1 ELSE 0 END) AS has_chargeback_decision,
            MAX(CASE WHEN case_event_type = 'DETECTION_EVENT_ATTACHED' THEN 1 ELSE 0 END) AS has_detection_event_attached
        FROM parquet_scan($case_files, filename := TRUE)
        GROUP BY 1
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
            e.flow_id,
            e.first_event_ts_utc,
            e.last_event_ts_utc,
            CAST(e.first_event_ts_utc AS DATE) AS first_event_date_utc,
            e.event_rows,
            e.auth_request_rows,
            e.auth_response_rows,
            e.auth_cycle_seconds,
            a.arrival_seq,
            a.amount,
            LN(a.amount + 1.0) AS log_amount,
            a.merchant_id,
            a.party_id,
            a.account_id,
            a.instrument_id,
            a.device_id,
            a.ip_id,
            c.case_id,
            c.distinct_cases,
            c.case_opened_ts_utc,
            c.case_closed_ts_utc,
            c.last_case_ts_utc,
            c.case_event_rows,
            c.max_case_event_seq,
            c.has_case_opened,
            c.has_case_closed,
            c.has_customer_dispute,
            c.has_chargeback_initiated,
            c.has_chargeback_decision,
            c.has_detection_event_attached,
            CASE
                WHEN c.case_opened_ts_utc IS NOT NULL
                THEN DATEDIFF(
                    'hour',
                    c.case_opened_ts_utc,
                    COALESCE(c.case_closed_ts_utc, c.last_case_ts_utc)
                )
                ELSE NULL
            END AS lifecycle_hours,
            CASE
                WHEN c.case_opened_ts_utc IS NOT NULL
                THEN DATEDIFF('hour', e.first_event_ts_utc, c.case_opened_ts_utc)
                ELSE NULL
            END AS hours_event_to_case_open,
            t.is_fraud_truth AS target_is_fraud_truth,
            t.fraud_label,
            b.is_fraud_bank_view,
            b.bank_label
        FROM event_flows e
        LEFT JOIN flow_anchor a ON e.flow_id = a.flow_id
        LEFT JOIN case_rollup c ON e.flow_id = c.flow_id
        LEFT JOIN flow_truth t ON e.flow_id = t.flow_id
        LEFT JOIN flow_bank b ON e.flow_id = b.flow_id
    ),
    ordered AS (
        SELECT
            *,
            NTILE(10) OVER (ORDER BY first_event_ts_utc, flow_id) AS time_split_decile
        FROM base
    )
    SELECT
        *,
        CASE
            WHEN amount < 25 THEN 'lt_25'
            WHEN amount < 75 THEN '25_to_75'
            WHEN amount < 150 THEN '75_to_150'
            ELSE 'gte_150'
        END AS amount_band,
        CASE
            WHEN has_case_opened = 1 THEN 1 ELSE 0
        END AS is_case_selected,
        CASE
            WHEN has_chargeback_decision = 1 THEN 'chargeback_decision'
            WHEN has_chargeback_initiated = 1 THEN 'chargeback_initiated'
            WHEN has_customer_dispute = 1 THEN 'customer_dispute'
            WHEN has_detection_event_attached = 1 THEN 'detection_event_attached'
            WHEN has_case_opened = 1 THEN 'opened_only'
            ELSE 'no_case'
        END AS pathway_stage,
        CASE
            WHEN time_split_decile <= 6 THEN 'train'
            WHEN time_split_decile <= 8 THEN 'validation'
            ELSE 'test'
        END AS split_role
    FROM ordered
) TO $population_pathway_base_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
