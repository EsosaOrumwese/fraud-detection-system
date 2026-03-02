# Dev_full Visuals (Mermaid-first)

This directory contains `dev_full` architecture and runtime-flow views as Mermaid source and rendered image outputs.

## Layout

- `infrastructure/`
  - `dev_full_infra_executive.mmd`
  - `dev_full_infra_engineering.mmd`
  - `dev_full_infra_audit_governance.mmd`
  - `dev_full_infra_network_topology.mmd`
- `platform_flow/`
  - `dev_full_flow_end_to_end_runtime.mmd`
  - `dev_full_flow_decision_path.mmd`
  - `dev_full_flow_learning_promotion.mmd`
  - `dev_full_flow_failure_recovery_gates.mmd`

Rendered outputs are generated alongside each `.mmd` file as:
- `.svg`
- `.png`

## Render

From repo root:

```powershell
pwsh -NoProfile -File scripts/design/render_dev_full_mermaid.ps1 -MermaidLayout elk -MermaidTheme neutral
```

If ELK produces poor composition for a specific chart, rerender with:

```powershell
pwsh -NoProfile -File scripts/design/render_dev_full_mermaid.ps1 -MermaidLayout dagre -MermaidTheme neutral
```

