# Documentation

## Run Logs
- docs/logbook/

## Platform runtime logs (local/dev)
- Per-run log: `runs/fraud-platform/<platform_run_id>/platform.log`
- Session ledger: `runs/fraud-platform/<platform_run_id>/session.jsonl`
- Run ID resolution: `PLATFORM_RUN_ID` env var, else `runs/fraud-platform/ACTIVE_RUN_ID`, else auto-generate `platform_YYYYMMDDTHHMMSSZ` on first run.
- Override shared log path with `PLATFORM_LOG_PATH` when you need a custom sink.

## Runbooks
- docs/runbooks/

- docs/runbooks/s2_tile_weights.md
- docs/runbooks/platform_parity_walkthrough_v0.md
