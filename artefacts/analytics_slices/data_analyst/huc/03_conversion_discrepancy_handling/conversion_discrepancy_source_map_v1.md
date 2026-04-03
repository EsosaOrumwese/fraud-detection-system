# Conversion Discrepancy Source Map v1

Compared reporting views:
- view A: service-line KPI view using `flow_rows` as the conversion denominator
- view B: linked reporting interpretation that normalises the same case-open count by `entry_event_rows`

Source path:
- event source contributes workflow-entry pressure
- flow source defines the analytical `flow_id` denominator
- case-open conversion should therefore be a flow-to-case KPI, not an event-to-case KPI

Why the views should align:
- both are intended to describe suspicious-to-case conversion inside the same weekly reporting lane
- the only legitimate conversion denominator for this KPI is `flow_rows`
