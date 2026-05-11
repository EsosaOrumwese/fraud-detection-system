COPY (
    WITH case_timeline AS (
        SELECT
            case_id,
            flow_id,
            case_event_seq,
            case_event_type,
            CAST(ts_utc AS TIMESTAMP) AS case_ts_utc
        FROM parquet_scan($case_timeline_files, filename := TRUE)
    )
    SELECT
        case_id,
        MIN(flow_id) AS flow_id,
        COUNT(*) AS chronology_rows,
        MIN(case_ts_utc) AS first_case_ts_utc,
        MAX(case_ts_utc) AS last_case_ts_utc,
        MIN(CASE WHEN case_event_type = 'CASE_OPENED' THEN case_ts_utc END) AS case_opened_ts_utc,
        MAX(CASE WHEN case_event_type = 'CASE_CLOSED' THEN case_ts_utc END) AS case_closed_ts_utc,
        MAX(case_event_seq) AS max_case_event_seq,
        MAX(CASE WHEN case_event_type = 'CASE_OPENED' THEN 1 ELSE 0 END) AS has_case_opened,
        MAX(CASE WHEN case_event_type = 'CASE_CLOSED' THEN 1 ELSE 0 END) AS has_case_closed,
        MAX(CASE WHEN case_event_type = 'CUSTOMER_DISPUTE_FILED' THEN 1 ELSE 0 END) AS has_customer_dispute,
        MAX(CASE WHEN case_event_type = 'CHARGEBACK_INITIATED' THEN 1 ELSE 0 END) AS has_chargeback_initiated,
        MAX(CASE WHEN case_event_type = 'CHARGEBACK_DECISION' THEN 1 ELSE 0 END) AS has_chargeback_decision,
        MAX(CASE WHEN case_event_type = 'DETECTION_EVENT_ATTACHED' THEN 1 ELSE 0 END) AS has_detection_event_attached,
        (EPOCH(MAX(case_ts_utc)) - EPOCH(MIN(case_ts_utc))) / 3600.0 AS lifecycle_hours
    FROM case_timeline
    GROUP BY case_id
) TO $case_chronology_rollup_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
