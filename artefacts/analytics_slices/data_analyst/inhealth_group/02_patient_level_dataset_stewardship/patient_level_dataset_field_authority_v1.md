# Patient-Level Dataset Field Authority v1

Maintained reporting dataset fields:
- `flow_id`: authoritative from flow anchor
- `flow_ts_utc`: authoritative from flow anchor
- `amount`: authoritative from flow anchor
- `amount_band`: derived from authoritative `amount`
- `merchant_id`: authoritative from flow anchor
- `party_id`: authoritative from flow anchor
- `case_id`: authoritative from rolled case timeline
- `raw_case_event_rows`: control field from rolled case timeline used to prove why event-grain joins are unsafe
- `case_opened_flag`: maintained dataset inclusion rule, fixed to `1`
- `is_fraud_truth`: authoritative from truth labels
- `fraud_label`: authoritative from truth labels

Core stewardship rule:
- event-grain case rows are not reporting-safe
- the maintained dataset only admits one rolled case state per `flow_id`
