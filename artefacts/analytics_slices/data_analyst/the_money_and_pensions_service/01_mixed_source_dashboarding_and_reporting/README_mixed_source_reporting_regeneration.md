
# Mixed-Source Reporting Regeneration

Regeneration order:
1. confirm the inherited HUC, Claire House, and Hertfordshire compact outputs still exist
2. run `models/build_mixed_source_dashboarding_and_reporting.py`
3. verify the integrated base, dashboard summary, supporting detail output, and release checks under `extracts/`
4. confirm release checks remain `6/6`

Current bounded outcome:
- `3` evidence streams combined
- `1` common reporting grain
- `1` dashboard-style summary
- `1` supporting detail output
- regeneration completed in `0.18` seconds
