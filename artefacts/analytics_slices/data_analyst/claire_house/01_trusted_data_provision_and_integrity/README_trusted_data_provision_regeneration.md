
# Trusted Data Provision Regeneration

Regeneration order:
1. confirm the inherited InHealth `3.C` maintained lane and control outputs still exist
2. run `models/build_trusted_data_provision_and_integrity.py`
3. verify the output pack under `extracts/` and `metrics/`
4. confirm provision integrity remains `5/5` inherited validation passes and `4/4` protected-output reconciliations

Current bounded outcome:
- one controlled provision lane
- one protected downstream analytical output
- regeneration completed in `0.51` seconds
