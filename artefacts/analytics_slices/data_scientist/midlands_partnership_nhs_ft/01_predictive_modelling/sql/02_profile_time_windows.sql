WITH flow_anchor AS (
    SELECT
        flow_id,
        CAST(ts_utc AS TIMESTAMP) AS flow_ts_utc
    FROM parquet_scan($flow_anchor_glob)
),
flow_truth AS (
    SELECT
        flow_id,
        is_fraud_truth
    FROM parquet_scan($flow_truth_glob)
),
weekly AS (
    SELECT
        DATE_TRUNC('week', fa.flow_ts_utc) AS flow_week_utc,
        COUNT(*) AS flow_rows,
        SUM(CASE WHEN ft.is_fraud_truth THEN 1 ELSE 0 END) AS fraud_truth_rows
    FROM flow_anchor fa
    INNER JOIN flow_truth ft
        ON fa.flow_id = ft.flow_id
    GROUP BY 1
)
SELECT
    flow_week_utc,
    flow_rows,
    fraud_truth_rows,
    fraud_truth_rows * 1.0 / NULLIF(flow_rows, 0) AS fraud_truth_rate
FROM weekly
ORDER BY flow_week_utc;
