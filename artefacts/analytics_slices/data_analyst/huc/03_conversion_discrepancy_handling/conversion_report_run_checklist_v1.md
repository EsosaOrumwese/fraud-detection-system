# Conversion Report Run Checklist v1

Before release:
- confirm suspicious-to-case conversion uses `flow_rows` as denominator
- compare any linked conversion view against the authoritative flow-based rate
- review the discrepancy summary for a material gap

Trigger for review:
- absolute conversion gap at or above 1 percentage point

Required release checks:
- two period rows present
- material gap check executed
- before-and-after KPI view refreshed
