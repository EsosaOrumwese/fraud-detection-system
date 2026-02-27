# Platform Design Asset Map

This folder is organized by environment and artifact type.

## Layout

- `assets/`
  - shared design assets used across platform diagrams/docs
- `dev_min/`
  - `architecture/`:
    - multi-view architecture packs (`with_icons`, `without_icons`)
    - executive, engineering, audit/governance, and network topology views
  - `graph/`:
    - earlier dev_min graph set (legacy snapshots)
  - `terraform/`:
    - Terraform resource architecture outputs for dev_min roots
- `dev_full/`
  - `graph/`:
    - planned/proposed dev_full architecture and infra graph set
- `local-parity/`
  - local-parity architecture artifacts and addenda

## Render Scripts

- `scripts/design/render_dev_min_architecture.ps1`
  - renders all dev_min architecture views (DOT + Mermaid -> SVG/PNG)
  - supports Mermaid layout selection: `dagre` or `elk`
- `scripts/design/run_terravision_dev_min.ps1`
  - Terravision-based Terraform graph generation for dev_min roots

