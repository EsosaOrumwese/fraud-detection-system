# Conversion Discrepancy Issue Log v1

Issue:
- suspicious-to-case conversion did not align across two linked weekly reporting views

Affected KPI:
- suspicious-to-case conversion

Current-week discrepancy:
- corrected flow-based conversion: 9.6%
- discrepant event-normalized conversion: 4.8%
- absolute gap: 4.8%

Likely root cause:
- numerator was reused correctly, but denominator drifted from `flow_rows` to `entry_event_rows`

Severity:
- high, because the discrepant view makes weekly conversion look materially weaker than it really is

Immediate corrective action:
- keep `flow_rows` as the only allowed denominator for suspicious-to-case conversion

Long-term control:
- add a release check that compares the corrected flow-based rate to any linked reporting view before pack release
