WITH flow_truth AS (
    SELECT
        flow_id,
        is_fraud_truth,
        fraud_label
    FROM parquet_scan($flow_truth_glob)
),
flow_anchor AS (
    SELECT
        flow_id,
        ts_utc,
        amount,
        merchant_id,
        party_id,
        account_id,
        instrument_id,
        device_id,
        ip_id,
        arrival_seq
    FROM parquet_scan($flow_anchor_glob)
),
case_timeline AS (
    SELECT
        flow_id,
        case_id,
        case_event_type,
        ts_utc
    FROM parquet_scan($case_timeline_glob)
),
case_flows AS (
    SELECT DISTINCT
        flow_id
    FROM case_timeline
),
anchor_profile AS (
    SELECT
        COUNT(*) AS flow_rows,
        MIN(ts_utc) AS min_flow_ts_utc,
        MAX(ts_utc) AS max_flow_ts_utc,
        AVG(amount) AS avg_amount,
        MIN(amount) AS min_amount,
        MAX(amount) AS max_amount,
        COUNT(DISTINCT merchant_id) AS distinct_merchants,
        COUNT(DISTINCT party_id) AS distinct_parties,
        COUNT(DISTINCT account_id) AS distinct_accounts
    FROM flow_anchor
),
target_profile AS (
    SELECT
        COUNT(*) AS target_rows,
        SUM(CASE WHEN is_fraud_truth THEN 1 ELSE 0 END) AS fraud_truth_rows,
        AVG(CASE WHEN is_fraud_truth THEN 1.0 ELSE 0.0 END) AS fraud_truth_rate
    FROM flow_truth
),
case_profile AS (
    SELECT
        COUNT(*) AS case_timeline_rows,
        COUNT(DISTINCT case_id) AS distinct_cases,
        COUNT(DISTINCT flow_id) AS flows_with_cases
    FROM case_timeline
),
coverage_profile AS (
    SELECT
        COUNT(*) AS total_target_flows,
        SUM(CASE WHEN cf.flow_id IS NOT NULL THEN 1 ELSE 0 END) AS target_flows_with_cases,
        SUM(CASE WHEN ft.is_fraud_truth AND cf.flow_id IS NOT NULL THEN 1 ELSE 0 END) AS fraud_truth_flows_with_cases
    FROM flow_truth ft
    LEFT JOIN case_flows cf
        ON ft.flow_id = cf.flow_id
)
SELECT
    ap.flow_rows,
    ap.min_flow_ts_utc,
    ap.max_flow_ts_utc,
    ap.avg_amount,
    ap.min_amount,
    ap.max_amount,
    ap.distinct_merchants,
    ap.distinct_parties,
    ap.distinct_accounts,
    tp.target_rows,
    tp.fraud_truth_rows,
    tp.fraud_truth_rate,
    cp.case_timeline_rows,
    cp.distinct_cases,
    cp.flows_with_cases,
    cv.total_target_flows,
    cv.target_flows_with_cases,
    cv.fraud_truth_flows_with_cases
FROM anchor_profile ap
CROSS JOIN target_profile tp
CROSS JOIN case_profile cp
CROSS JOIN coverage_profile cv;
