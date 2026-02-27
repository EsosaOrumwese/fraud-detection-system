# Dev_min Architecture Views

This folder contains two complete sets of dev_min architecture views:

- `without_icons`
- `with_icons` (portable badge-style icons like `[S3]`, `[ECS]`, `[KAFKA]`)

Each set includes three views:

1. Executive view
2. Engineering view
3. Audit/Governance view

Each view is provided in:

- Graphviz DOT: `*.graphviz.dot`
- Graphviz SVG/PNG render: `*.graphviz.svg`, `*.graphviz.png`
- Mermaid source: `*.mmd`
- Mermaid SVG/PNG render: `*.svg`, `*.png`
- ASCII narrative diagram: `*.ascii.txt`

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

