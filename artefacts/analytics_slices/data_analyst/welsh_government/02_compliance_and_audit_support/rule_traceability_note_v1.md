
# Rule Traceability Note v1

Traceability chain:
1. rule authority
   - authoritative rule: `flow_based_case_conversion_authority`
   - authoritative denominator: `flow_rows`
2. discrepancy exclusion
   - retained discrepancy class: `denominator_drift_doubles_reporting_base`
   - excluded denominator: `entry_event_rows`
3. reconciliation defence
   - current authoritative to control delta: `-0.04 pp`
   - current discrepant to control delta: `-4.83 pp`
4. release review gate
   - inherited recurring control checks: `8/8`

Why this matters:
- a reviewer can now follow the released recurring view back to the named rule, the excluded discrepancy path, the reconciliation evidence, and the release gate without reopening a wider operational lane
