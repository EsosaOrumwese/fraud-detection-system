# CHANGELOG - Conversion Reporting

Version `v1`:
- identified a suspicious-to-case conversion discrepancy across linked reporting views
- traced the mismatch to denominator drift from `flow_rows` to `entry_event_rows`
- fixed the KPI authority rule and added a recurring discrepancy control
