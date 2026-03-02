# Dev_min Architecture Views

This folder contains the architecture views for `dev_min` in three forms:

- `*.graphviz.dot` -> source of truth for Graphviz rendering.
- `*.mmd` -> Mermaid equivalents.
- `*.svg` and `*.png` -> rendered outputs.
- `*.ascii.txt` -> text fallback diagrams.

## View set

- `dev_min_executive_view`: high-level system boundaries and core flow.
- `dev_min_engineering_view`: implementation-level resource and data-flow ownership.
- `dev_min_audit_view`: truth surfaces and fail-closed certification gate flow.
- `dev_min_network_topology`: provisioned network posture (VPC, subnets, routing, security groups, Internet gateway, runtime services, database).

## Visual variants

- `without_icons/`: labels-first rendering for maximum readability.
- `with_icons/`: AWS/tool icon-assisted rendering for presentation.

## Regenerate

From repo root:

```powershell
pwsh -NoProfile -File scripts/design/apply_professional_icons_to_graphviz.ps1
pwsh -NoProfile -File scripts/design/render_dev_min_architecture.ps1 -Set all -MermaidLayout elk -MermaidTheme neutral
```

## Icon sources

- Curated pack used by Graphviz: `docs/design/platform/assets/iconpack_professional_18/`
- Preparation script: `scripts/design/prepare_professional_iconpack.ps1`
