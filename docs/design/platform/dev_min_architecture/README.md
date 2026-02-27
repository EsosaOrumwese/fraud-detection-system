# Dev_min Architecture Views

This folder contains two complete sets of dev_min architecture views:

- `without_icons`
- `with_icons` (portable badge-style icons like `[S3]`, `[ECS]`, `[KAFKA]`)

Each set includes three views:

1. Executive view
2. Engineering view
3. Audit/Governance view
4. Network topology view (VPC, subnets, routes, security groups, ECS placement, DB subnet/RDS path)

Each view is provided in:

- Graphviz DOT: `*.graphviz.dot`
- Graphviz SVG/PNG render: `*.graphviz.svg`, `*.graphviz.png`
- Mermaid source: `*.mmd`
- Mermaid SVG/PNG render: `*.svg`, `*.png`
- ASCII narrative diagram: `*.ascii.txt`

## One-command renderer (all views)

From repo root:

```powershell
pwsh ./scripts/design/render_dev_min_architecture.ps1
```

This renders both sets (`with_icons`, `without_icons`) to SVG and PNG for:
- Graphviz sources (`*.graphviz.dot`)
- Mermaid sources (`*.mmd`)

### Use ELK (adaptive) Mermaid layout

```powershell
pwsh ./scripts/design/render_dev_min_architecture.ps1 -MermaidLayout elk
```

### Common options

- `-Set all|with_icons|without_icons`
- `-MermaidLayout dagre|elk`
- `-GraphvizEngine dot|neato|fdp|sfdp|twopi|circo`
- `-MermaidTheme default|neutral|forest|dark`
- `-SkipGraphviz`
- `-SkipMermaid`

## Render commands used

Graphviz (DOT -> SVG/PNG):

```powershell
docker run --rm --entrypoint dot -v "${PWD}:/workspace" -w /workspace patrickchugh/terravision:latest -Tsvg /workspace/<file>.dot -o /workspace/<file>.svg
docker run --rm --entrypoint dot -v "${PWD}:/workspace" -w /workspace patrickchugh/terravision:latest -Tpng /workspace/<file>.dot -o /workspace/<file>.png
```

Mermaid (MMD -> SVG/PNG):

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace minlag/mermaid-cli -i /workspace/<file>.mmd -o /workspace/<file>.svg -t neutral -w 2400 -H 1600 -b transparent
docker run --rm -v "${PWD}:/workspace" -w /workspace minlag/mermaid-cli -i /workspace/<file>.mmd -o /workspace/<file>.png -t neutral -w 2400 -H 1600 -b white
```


## Icon-pack renders (with_icons set)
The with_icons Mermaid views use icon packs via Iconify (@iconify-json/simple-icons and @iconify-json/mdi) and are rendered by mermaid-cli with --iconPacks flags.

