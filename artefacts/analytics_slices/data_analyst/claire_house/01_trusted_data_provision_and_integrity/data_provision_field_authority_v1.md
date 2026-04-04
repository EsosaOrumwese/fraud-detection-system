
# Data Provision Field Authority v1

Release-safe authority fields:
- `flow_id`
- `flow_ts_utc`
- `amount`
- `amount_band`
- `merchant_id`
- `party_id`
- `case_id`
- `is_fraud_truth`
- `fraud_label`

Control-only field:
- `raw_case_event_rows`
  - retained only to prove why raw event-grain rows are unsafe for direct provision

Core provision rules:
- one maintained row per `flow_id`
- raw event-grain case rows are not release-safe
- downstream analytical use is permitted only from the controlled maintained lane

Explicit authority count:
- `9` release-safe field rules
