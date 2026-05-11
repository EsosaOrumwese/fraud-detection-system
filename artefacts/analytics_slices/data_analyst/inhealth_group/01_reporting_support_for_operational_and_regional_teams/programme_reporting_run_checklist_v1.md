# Programme Reporting Run Checklist v1

1. Confirm the monthly window is still bounded to `Feb 2026` and `Mar 2026` for the current slice run.
2. Run the month-band aggregate build in SQL before any Python reporting step.
3. Confirm the monthly summary output contains `1` current row with populated core metrics.
4. Confirm the ad hoc follow-up output contains `4` amount-band rows and one clear priority band.
5. Confirm the release checks pass before figures or notes are regenerated.
6. Confirm the follow-up output uses the same KPI definitions as the monthly pack.
