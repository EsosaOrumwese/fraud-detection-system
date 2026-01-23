# Configuration Catalogue
Status: ACTIVE (governed).
Purpose: Non-secret, version-controlled inputs and run manifests that the engine and tooling rely on.
Owns: layer-scoped configs (`layer1/`, `layer2/`, `layer3/`), scenario inputs (`scenario_profiles/`), and sealed run configs (`runs/`).
Boundaries: keep secrets elsewhere; JSON/Parquet schemas still live under `contracts/`.

Structure (2026-01-10 alignment to model_spec contracts):
- `layer1/1A/` - allocation policies, ingress configs, model bundles, and numeric settings.
- `layer1/2A/` - timezone nudge and override policies.
- `layer1/2B/` - routing policies and alias layout configs.
- `layer1/3A/` - zone allocation priors and policies.
- `layer1/3B/` - virtual edge policies, logging, and validation configs.
- `layer2/` and `layer3/` - segment-scoped policies for 5A/5B and 6A/6B.
- `runs/` - replayable JSON configs (e.g., `s0_synthetic_config.json`).
- `scenario_profiles/` - curated Scenario Runner inputs.

Migration note: flattened `config/` paths were moved into layer-scoped folders to match `docs/model_spec` contract paths. Update downstream references to point at `config/layer*/...`.
