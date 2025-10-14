# Configuration Catalogue
Status: ACTIVE (governed).
Purpose: Non-secret, version-controlled inputs and run manifests that the engine and tooling rely on.
Owns: runtime defaults (`models/`, `policy/`, `scenario_profiles/`) and sealed run configs (`runs/`).
Boundaries: keep secrets elsewhere; JSON/Parquet schemas still live under `contracts/`.

Structure (2025-10-14 consolidation):
- `models/hurdle/hurdle_simulation.priors.yaml` — governed priors for synthetic training.
- `models/hurdle/exports/version=*/<timestamp>/` — published coefficient bundles from training runs.
- `policy/` — channel/allocation/cross-border knobs, incl. `s3.rule_ladder.yaml`.
- `runs/` — replayable JSON configs (e.g., `s0_synthetic_config.json`).
- `scenario_profiles/` — curated Scenario Runner inputs.

Migration note: the former `configs/` directory has been merged here. Update any downstream references to point at `config/...`.
