COPY (
    WITH base AS (
        SELECT
            week_role,
            CAST(flow_rows AS DOUBLE) AS flow_rows,
            CAST(entry_event_rows AS DOUBLE) AS entry_event_rows,
            CAST(case_open_rate AS DOUBLE) AS case_open_rate
        FROM read_parquet($kpi_path)
    ),
    calc AS (
        SELECT
            week_role,
            flow_rows,
            entry_event_rows,
            case_open_rate AS corrected_flow_conversion_rate,
            case_open_rate * flow_rows AS case_opened_rows,
            (case_open_rate * flow_rows) / entry_event_rows AS event_normalized_conversion_rate
        FROM base
    )
    SELECT
        week_role,
        flow_rows,
        entry_event_rows,
        case_opened_rows,
        corrected_flow_conversion_rate,
        event_normalized_conversion_rate AS discrepant_conversion_rate,
        corrected_flow_conversion_rate - event_normalized_conversion_rate AS absolute_gap,
        CASE
            WHEN event_normalized_conversion_rate = 0 THEN NULL
            ELSE corrected_flow_conversion_rate / event_normalized_conversion_rate
        END AS rate_ratio
    FROM calc
    ORDER BY week_role
) TO $output_path (FORMAT PARQUET);
