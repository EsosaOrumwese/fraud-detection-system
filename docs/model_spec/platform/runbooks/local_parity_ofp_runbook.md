# OFP Local-Parity Runbook (v0 Boundary)
_As of 2026-02-06_

## Purpose
Run and validate OFP in `local_parity` up to the current component boundary (without DF/DL integration).

## Preconditions
- Docker Desktop is running.
- Local parity infrastructure is up (EB/object store/postgres adapters used by profile).
- Active run is set in `runs/fraud-platform/ACTIVE_RUN_ID` or `PLATFORM_RUN_ID`.
- Python venv available at `.venv`.

## 1) Pin run scope in shell
```powershell
$run = (Get-Content runs/fraud-platform/ACTIVE_RUN_ID -Raw).Trim()
$run = ($run -replace '[^A-Za-z0-9_:-]','')
$env:PLATFORM_RUN_ID = $run
$env:OFP_REQUIRED_PLATFORM_RUN_ID = $run
$env:OFP_PROJECTION_DSN = 'runs/fraud-platform'
$env:PLATFORM_STORE_ROOT = 'runs/fraud-platform'
```

## 2) Run OFP projector once
```powershell
.venv\Scripts\python.exe -m fraud_detection.online_feature_plane.projector `
  --profile config/platform/profiles/local_parity.yaml `
  --once
```

## 3) Discover scenario_run_id from OFP projection DB
```powershell
@'
import sqlite3
from pathlib import Path
run_id = Path("runs/fraud-platform/ACTIVE_RUN_ID").read_text(encoding="utf-8").strip()
db = Path(f"runs/fraud-platform/{run_id}/online_feature_plane/projection/online_feature_plane.db")
con = sqlite3.connect(db)
rows = con.execute("select distinct scenario_run_id from ofp_feature_state order by scenario_run_id").fetchall()
for row in rows:
    print(row[0])
'@ | .venv\Scripts\python.exe -
```

## 4) Materialize a snapshot
```powershell
.venv\Scripts\python.exe -m fraud_detection.online_feature_plane.snapshotter `
  --profile config/platform/profiles/local_parity.yaml `
  --platform-run-id $env:PLATFORM_RUN_ID `
  --scenario-run-id <SCENARIO_RUN_ID>
```

Expected artifact path shape:
- `runs/fraud-platform/<platform_run_id>/ofp/snapshots/<scenario_run_id>/<snapshot_hash>.json`

## 5) Export OFP observability artifacts
```powershell
.venv\Scripts\python.exe -m fraud_detection.online_feature_plane.observe `
  --profile config/platform/profiles/local_parity.yaml `
  --scenario-run-id <SCENARIO_RUN_ID>
```

Expected outputs:
- `runs/fraud-platform/<platform_run_id>/online_feature_plane/metrics/last_metrics.json`
- `runs/fraud-platform/<platform_run_id>/online_feature_plane/health/last_health.json`

## 6) Verify required Phase 7 counters
Check `online_feature_plane/metrics/last_metrics.json` for:
- `snapshots_built`
- `snapshot_failures`
- `events_applied`
- `duplicates`
- `stale_graph_version`
- `missing_features`

## Boundary note
This runbook validates OFP up to the current component boundary.  
DF/DL integration checks are intentionally deferred until those components are implemented.

