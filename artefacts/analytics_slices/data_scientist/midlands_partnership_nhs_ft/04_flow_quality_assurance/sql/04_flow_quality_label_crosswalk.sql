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
        MIN(case_id) AS case_id
    FROM parquet_scan($case_files, filename := TRUE)
    GROUP BY 1
),
base AS (
    SELECT
        e.flow_id,
        c.case_id,
        t.fraud_label,
        COALESCE(t.is_fraud_truth, FALSE) AS is_fraud_truth,
        b.bank_label,
        COALESCE(b.is_fraud_bank_view, FALSE) AS is_fraud_bank_view,
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
    fraud_label,
    bank_label,
    COUNT(*) FILTER (WHERE case_id IS NOT NULL) AS case_selected_flows,
    AVG(CASE WHEN case_id IS NOT NULL AND is_fraud_truth THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) AS truth_rate,
    AVG(CASE WHEN case_id IS NOT NULL AND is_fraud_bank_view THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) AS bank_rate
FROM base
WHERE case_id IS NOT NULL
GROUP BY 1, 2, 3
HAVING COUNT(*) FILTER (WHERE case_id IS NOT NULL) > 0
ORDER BY split_role, case_selected_flows DESC, fraud_label, bank_label
;
