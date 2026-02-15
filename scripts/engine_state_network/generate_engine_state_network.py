from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    cur = start.resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    raise RuntimeError(f"Could not locate repo root from {start}")


REPO_ROOT = find_repo_root(Path(__file__))
IMPL_MAP_DIR = REPO_ROOT / "docs" / "model_spec" / "data-engine" / "implementation_maps"
OUT_DIR = REPO_ROOT / "docs" / "design" / "data-engine" / "engine_state_network"
STATE_FLOW_ROOT = REPO_ROOT / "docs" / "model_spec" / "data-engine"

LAYER_DISPLAY = {
    "layer1": "Layer 1 - World and Merchant Realism",
    "layer2": "Layer 2 - Temporal Arrival Surfaces",
    "layer3": "Layer 3 - Behavior, Fraud, and Labels",
}

RNG_DISPLAY = {
    "RNG_NONE": "Deterministic",
    "RNG_CONSUMING": "RNG-driven",
    "RNG_MIXED": "Deterministic + RNG",
}

STATE_TITLE_OVERRIDES = {
    ("1A", "S3"): "Cross-border candidate universe and ordering",
    ("1A", "S4"): "Foreign-country count target (ZTP)",
    ("1B", "S0"): "Gate-in and foundations",
}


@dataclass
class StateInfo:
    state_id: str
    title: str = ""
    state_class: str = "UNKNOWN"
    rng_posture: str = "UNKNOWN"
    gates_in: list[str] = field(default_factory=list)


@dataclass
class SegmentInfo:
    segment_id: str
    layer_id: str
    title: str
    states: dict[str, StateInfo]
    gate_types: dict[str, str]
    impl_map_rel: str
    impl_actual_rel: str | None
    latest_impl_entry: str | None

    @property
    def ordered_states(self) -> list[str]:
        return sorted(self.states.keys(), key=lambda x: int(x[1:]))

    @property
    def first_state(self) -> str:
        return self.ordered_states[0]

    @property
    def last_state(self) -> str:
        return self.ordered_states[-1]


@dataclass(frozen=True)
class Edge:
    src_seg: str
    src_state: str
    dst_seg: str
    dst_state: str
    gate_id: str
    gate_label: str
    edge_type: str  # sequential | gate_internal | gate_cross


def clean_scalar(value: str) -> str:
    value = value.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1]
    return value


def read_text_robust(path: Path) -> str:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    # Final fallback: replace invalid bytes to avoid hard failure in doc parsing.
    return path.read_text(encoding="utf-8", errors="replace")


def build_state_doc_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in STATE_FLOW_ROOT.rglob("state.*.expanded.md"):
        index[path.name.lower()] = path
    return index


STATE_DOC_INDEX = build_state_doc_index()


def normalize_title(raw: str, segment_id: str, state_id: str) -> str:
    title = raw.strip()
    title = title.lstrip("#").strip()
    title = title.replace("**", "").replace("`", "")
    title = title.replace("\u2014", "-").replace("\u2013", "-").replace("\u00b7", "-")
    title = title.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    title = title.replace("â", "-").replace("â", "-").replace("â", "->")

    patterns = [
        r"^\d+(\.\d+)*\)\s*",
        rf"^{re.escape(segment_id)}\s*[-:*]\s*",
        rf"^{re.escape(segment_id)}\.{re.escape(state_id)}\s*[-:.]\s*",
        rf"^state\s+{re.escape(segment_id)}\.{re.escape(state_id)}\s*[-:.]\s*",
        rf"^state\s+{re.escape(segment_id)}\s*[-:.]\s*{re.escape(state_id)}\s*[-:.]\s*",
        rf"^state\s*{re.escape(state_id)}\s*",
        rf"^state[\s-]*{re.escape(state_id[1:])}\s*(\(\s*{re.escape(state_id)}\s*\))?\s*",
        rf"^{re.escape(state_id)}(\.\d+)?\s*(spec)?\s*[-:.]\s*",
        rf"^what\s+{re.escape(state_id)}\s+does\s*\(one breath\)\s*",
    ]
    for pat in patterns:
        title = re.sub(pat, "", title, flags=re.IGNORECASE).strip()

    title = title.strip(" '\"“”")
    title = re.sub(r"^\(\s*([^)]*?)\s*\)\s*$", r"\1", title).strip()
    title = re.sub(r"\s+\(layer[^)]*\)\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+\(normative[^)]*\)\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*-\s*Technical Specification\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"[\s\u00A0]+,", ",", title)
    title = re.sub(r"\s+", " ", title).strip(" -")

    if len(title) > 84:
        title = re.sub(r"\([^)]*\)", "", title).strip()
    if len(title) > 84 and "," in title:
        title = title.split(",", 1)[0].strip()
    if len(title) > 84:
        title = title[:81].rstrip() + "..."
    title = re.sub(r"\s+", " ", title).strip(" -")
    return title


def find_state_title(segment_id: str, state_id: str) -> str:
    if (segment_id, state_id) in STATE_TITLE_OVERRIDES:
        return STATE_TITLE_OVERRIDES[(segment_id, state_id)]

    fname = f"state.{segment_id}.{state_id.lower()}.expanded.md".lower()
    path = STATE_DOC_INDEX.get(fname)
    if path is None:
        return state_id

    lines = read_text_robust(path).splitlines()
    headings: list[tuple[int, str]] = []
    for line in lines:
        m = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
        if m:
            level = len(m.group(1))
            headings.append((level, m.group(2).strip()))

    if not headings:
        return state_id

    picked = None
    for level, text in headings:
        if level == 1:
            picked = text
            break
    if picked is None:
        picked = headings[0][1]

    title = normalize_title(picked, segment_id, state_id)
    return title if title else state_id


def friendly_gate_label(gate_id: str, gate_type: str | None) -> str:
    if gate_type == "final_bundle_gate" or gate_id.endswith(".final.bundle_gate"):
        return "PASS bundle"
    if gate_id.endswith(".S0.gate_in_receipt"):
        return "Gate-in receipt"
    if gate_id.endswith(".validation_receipt"):
        return "Validation receipt"
    if gate_id.endswith(".receipt"):
        return "Receipt gate"
    if gate_type == "receipt":
        return "Receipt gate"
    # fallback: keep last token as readable label
    tail = gate_id.split(".")[-1].replace("_", " ").strip()
    return tail.title() if tail else gate_id


def simplify_gate_edges(segments: list["SegmentInfo"], edges: list["Edge"]) -> list["Edge"]:
    seg_first = {s.segment_id: s.first_state for s in segments}
    kept: list[Edge] = []

    # For readability: S0 gate-in fanout often points to many states.
    # Keep only the first downstream gate-in edge per segment.
    first_gate_in_by_seg: dict[str, tuple[int, Edge]] = {}
    for e in edges:
        if (
            e.edge_type == "gate_internal"
            and e.src_state == seg_first.get(e.src_seg)
            and e.gate_id.endswith(".S0.gate_in_receipt")
        ):
            rank = int(e.dst_state[1:])
            prev = first_gate_in_by_seg.get(e.src_seg)
            if prev is None or rank < prev[0]:
                first_gate_in_by_seg[e.src_seg] = (rank, e)

    for e in edges:
        if (
            e.edge_type == "gate_internal"
            and e.src_state == seg_first.get(e.src_seg)
            and e.gate_id.endswith(".S0.gate_in_receipt")
        ):
            chosen = first_gate_in_by_seg.get(e.src_seg)
            if chosen is not None and chosen[1] is e:
                kept.append(e)
            continue
        kept.append(e)
    return kept


def parse_segment_impl_map(path: Path) -> SegmentInfo:
    text = read_text_robust(path)
    lines = text.splitlines()

    segment_id = None
    layer_id = None
    title = None
    states: dict[str, StateInfo] = {}

    section = None
    current_state: StateInfo | None = None
    in_gates_in = False
    current_gate_id: str | None = None
    gate_types: dict[str, str] = {}

    for line in lines:
        # root section switches
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:\s*$", line):
            root = line.split(":", 1)[0]
            section = root
            if root != "states":
                current_state = None
                in_gates_in = False

        if segment_id is None:
            m = re.match(r"^\s*segment_id:\s*(.+)\s*$", line)
            if m:
                segment_id = clean_scalar(m.group(1))
                continue
        if layer_id is None:
            m = re.match(r"^\s*layer_id:\s*(.+)\s*$", line)
            if m:
                layer_id = clean_scalar(m.group(1))
                continue
        if title is None:
            m = re.match(r"^\s*title:\s*(.+)\s*$", line)
            if m:
                title = clean_scalar(m.group(1))
                continue

        if section == "states":
            m = re.match(r"^  (S\d+):\s*$", line)
            if m:
                sid = m.group(1)
                current_state = StateInfo(state_id=sid)
                states[sid] = current_state
                in_gates_in = False
                continue

            if current_state is None:
                continue

            m = re.match(r"^    state_class:\s*(.+)\s*$", line)
            if m:
                current_state.state_class = clean_scalar(m.group(1))
                continue

            m = re.match(r"^    rng_posture:\s*(.+)\s*$", line)
            if m:
                current_state.rng_posture = clean_scalar(m.group(1))
                continue

            if re.match(r"^    gates_in:\s*$", line):
                in_gates_in = True
                continue

            if in_gates_in:
                m = re.match(r"^    -\s*(.+)\s*$", line)
                if m:
                    current_state.gates_in.append(clean_scalar(m.group(1)))
                    continue
                if re.match(r"^    [A-Za-z_][A-Za-z0-9_]*:\s*", line):
                    in_gates_in = False

        if section == "gates":
            m = re.match(r"^-\s*gate_id:\s*(.+)\s*$", line)
            if m:
                current_gate_id = clean_scalar(m.group(1))
                continue

            if current_gate_id is not None:
                m = re.match(r"^\s*gate_type:\s*(.+)\s*$", line)
                if m:
                    gate_types[current_gate_id] = clean_scalar(m.group(1))
                    continue

    if not segment_id or not layer_id or not title or not states:
        raise ValueError(f"Could not parse required fields from {path}")

    for state in states.values():
        state.title = find_state_title(segment_id, state.state_id)

    impl_actual = path.with_name(path.name.replace(".impl_map.yaml", ".impl_actual.md"))
    latest_entry = None
    impl_actual_rel = None
    if impl_actual.exists():
        impl_actual_rel = str(impl_actual.relative_to(REPO_ROOT)).replace("\\", "/")
        for line in read_text_robust(impl_actual).splitlines():
            if line.startswith("## Entry:"):
                latest_entry = line.replace("## Entry:", "", 1).strip()

    return SegmentInfo(
        segment_id=segment_id,
        layer_id=layer_id,
        title=title,
        states=states,
        gate_types=gate_types,
        impl_map_rel=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        impl_actual_rel=impl_actual_rel,
        latest_impl_entry=latest_entry,
    )


def seg_sort_key(segment_id: str) -> tuple[int, str]:
    m = re.match(r"^(\d+)([A-Z])$", segment_id)
    if not m:
        return (999, segment_id)
    return (int(m.group(1)), m.group(2))


def layer_sort_key(layer_id: str) -> int:
    m = re.match(r"^layer(\d+)$", layer_id)
    return int(m.group(1)) if m else 999


def parse_gate_reference(gate_id: str, segment_map: dict[str, SegmentInfo]) -> tuple[str, str] | None:
    m = re.match(r"^([0-9A-Z]+)\.(S\d+|final)\.", gate_id)
    if not m:
        return None
    seg = m.group(1)
    state_token = m.group(2)
    if seg not in segment_map:
        return None
    if state_token == "final":
        state = segment_map[seg].last_state
    else:
        state = state_token
    return seg, state


def build_edges(segments: list[SegmentInfo]) -> list[Edge]:
    seg_map = {s.segment_id: s for s in segments}
    seen: set[tuple[str, str, str, str, str, str]] = set()
    edges: list[Edge] = []

    for seg in segments:
        ordered = seg.ordered_states
        for i in range(len(ordered) - 1):
            edge = Edge(
                src_seg=seg.segment_id,
                src_state=ordered[i],
                dst_seg=seg.segment_id,
                dst_state=ordered[i + 1],
                gate_id="flow",
                gate_label="Next state",
                edge_type="sequential",
            )
            key = (*edge.__dict__.values(),)
            if key not in seen:
                seen.add(key)
                edges.append(edge)

        for dst_state_id in ordered:
            state = seg.states[dst_state_id]
            for gate in state.gates_in:
                src = parse_gate_reference(gate, seg_map)
                if src is None:
                    continue
                src_seg, src_state = src
                edge_type = "gate_cross" if src_seg != seg.segment_id else "gate_internal"
                gate_type = seg_map[src_seg].gate_types.get(gate) or seg.gate_types.get(gate)
                edge = Edge(
                    src_seg=src_seg,
                    src_state=src_state,
                    dst_seg=seg.segment_id,
                    dst_state=dst_state_id,
                    gate_id=gate,
                    gate_label=friendly_gate_label(gate, gate_type),
                    edge_type=edge_type,
                )
                key = (*edge.__dict__.values(),)
                if key not in seen:
                    seen.add(key)
                    edges.append(edge)
    return edges


def dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def mmd_escape(text: str) -> str:
    return text.replace('"', "'")


def node_id(seg: str, state: str) -> str:
    return f"n_{seg}_{state}"


def render_dot(segments: list[SegmentInfo], edges: list[Edge]) -> str:
    layers = sorted({s.layer_id for s in segments}, key=layer_sort_key)
    by_layer: dict[str, list[SegmentInfo]] = {layer: [] for layer in layers}
    for seg in segments:
        by_layer[seg.layer_id].append(seg)
    for layer in layers:
        by_layer[layer].sort(key=lambda s: seg_sort_key(s.segment_id))

    lines: list[str] = []
    lines.append("digraph EngineStateNetwork {")
    lines.append('  graph [rankdir=LR, fontsize=10, fontname="Helvetica", labelloc=t,')
    lines.append('         label="Data Engine Flow Map: layers > segments > states"];')
    lines.append('  node  [shape=box, style="rounded,filled", fillcolor=white, color="#4b5563", fontname="Helvetica", fontsize=9];')
    lines.append('  edge  [color="#6b7280", fontname="Helvetica", fontsize=8];')
    lines.append("")

    layer_colors = {
        "layer1": "#e8f0fe",
        "layer2": "#e6fffa",
        "layer3": "#fff7ed",
    }

    for layer in layers:
        lines.append(f'  subgraph cluster_{layer} {{')
        layer_label = LAYER_DISPLAY.get(layer, layer)
        lines.append(f'    label="{dot_escape(layer_label)}";')
        lines.append('    style="rounded,filled";')
        lines.append(f'    color="{layer_colors.get(layer, "#f3f4f6")}";')
        for seg in by_layer[layer]:
            cluster_label = f"{seg.segment_id} | {seg.title}"
            lines.append(f'    subgraph cluster_{seg.segment_id} {{')
            lines.append(f'      label="{dot_escape(cluster_label)}";')
            lines.append('      style="rounded";')
            lines.append('      color="#94a3b8";')
            for sid in seg.ordered_states:
                s = seg.states[sid]
                mode = RNG_DISPLAY.get(s.rng_posture, s.rng_posture)
                label = f"{seg.segment_id}.{sid} {s.title}\\n{mode}"
                lines.append(f'      {node_id(seg.segment_id, sid)} [label="{dot_escape(label)}"];')
            lines.append("    }")
        lines.append("  }")
        lines.append("")

    lines.append("  // sequential flows")
    for e in edges:
        if e.edge_type != "sequential":
            continue
        lines.append(
            f"  {node_id(e.src_seg, e.src_state)} -> {node_id(e.dst_seg, e.dst_state)} "
            f'[color="#64748b", penwidth=1.3];'
        )

    lines.append("")
    lines.append("  // gate flows (internal and cross-segment)")
    for e in edges:
        if e.edge_type == "sequential":
            continue
        if e.edge_type == "gate_internal":
            style = 'style=dashed, color="#2563eb", penwidth=1.2'
        else:
            style = 'style=bold, color="#dc2626", penwidth=1.8'
        lines.append(
            f"  {node_id(e.src_seg, e.src_state)} -> {node_id(e.dst_seg, e.dst_state)} "
            f'[label="{dot_escape(e.gate_label)}", {style}];'
        )

    lines.append("}")
    return "\n".join(lines) + "\n"


def render_mermaid(segments: list[SegmentInfo], edges: list[Edge]) -> str:
    layers = sorted({s.layer_id for s in segments}, key=layer_sort_key)
    by_layer: dict[str, list[SegmentInfo]] = {layer: [] for layer in layers}
    for seg in segments:
        by_layer[seg.layer_id].append(seg)
    for layer in layers:
        by_layer[layer].sort(key=lambda s: seg_sort_key(s.segment_id))

    lines: list[str] = []
    lines.append("flowchart LR")
    lines.append("%% Data Engine flow map: layers > segments > states")
    lines.append("")

    for layer in layers:
        layer_title = layer.upper()
        layer_label = LAYER_DISPLAY.get(layer, layer)
        lines.append(f'  subgraph {layer_title}["{mmd_escape(layer_label)}"]')
        for seg in by_layer[layer]:
            lines.append(f'    subgraph SEG_{seg.segment_id}["{seg.segment_id}: {mmd_escape(seg.title)}"]')
            for sid in seg.ordered_states:
                s = seg.states[sid]
                nid = node_id(seg.segment_id, sid)
                mode = RNG_DISPLAY.get(s.rng_posture, s.rng_posture)
                lines.append(
                    f'      {nid}["{mmd_escape(seg.segment_id)}.{mmd_escape(sid)} {mmd_escape(s.title)}<br/>{mmd_escape(mode)}"]'
                )
            lines.append("    end")
        lines.append("  end")
        lines.append("")

    lines.append("  %% sequential flows")
    for e in edges:
        if e.edge_type != "sequential":
            continue
        lines.append(
            f"  {node_id(e.src_seg, e.src_state)} --> {node_id(e.dst_seg, e.dst_state)}"
        )

    lines.append("")
    lines.append("  %% gate flows")
    for e in edges:
        if e.edge_type == "sequential":
            continue
        if e.edge_type == "gate_internal":
            lines.append(
                f'  {node_id(e.src_seg, e.src_state)} -. "{mmd_escape(e.gate_label)}" .-> {node_id(e.dst_seg, e.dst_state)}'
            )
        else:
            lines.append(
                f'  {node_id(e.src_seg, e.src_state)} == "{mmd_escape(e.gate_label)}" ==> {node_id(e.dst_seg, e.dst_state)}'
            )
    return "\n".join(lines) + "\n"


def render_ascii(segments: list[SegmentInfo], edges: list[Edge]) -> str:
    layers = sorted({s.layer_id for s in segments}, key=layer_sort_key)
    by_layer: dict[str, list[SegmentInfo]] = {layer: [] for layer in layers}
    for seg in segments:
        by_layer[seg.layer_id].append(seg)
    for layer in layers:
        by_layer[layer].sort(key=lambda s: seg_sort_key(s.segment_id))

    lines: list[str] = []
    lines.append("DATA ENGINE NETWORK (layers > segments > states)")
    lines.append("Source basis: state expanded docs + segment_*.impl_map.yaml")
    lines.append("Reader mode: human-readable names for LinkedIn-safe storytelling")
    lines.append("=" * 96)
    lines.append("")

    for layer in layers:
        header = LAYER_DISPLAY.get(layer, layer)
        lines.append(header)
        lines.append("-" * len(header))
        for seg in by_layer[layer]:
            chain_parts = []
            for sid in seg.ordered_states:
                s = seg.states[sid]
                mode = RNG_DISPLAY.get(s.rng_posture, s.rng_posture)
                chain_parts.append(f"{sid}({s.title}; {mode})")
            chain = " -> ".join(chain_parts)
            lines.append(f"  {seg.segment_id}  {seg.title}")
            lines.append(f"    flow: {chain}")
            lines.append(f"    impl_map:   {seg.impl_map_rel}")
            if seg.impl_actual_rel:
                lines.append(f"    impl_actual:{seg.impl_actual_rel}")
            lines.append("")

    internal = [e for e in edges if e.edge_type == "gate_internal"]
    cross = [e for e in edges if e.edge_type == "gate_cross"]

    internal.sort(key=lambda e: (seg_sort_key(e.src_seg), int(e.src_state[1:]), int(e.dst_state[1:])))
    cross.sort(key=lambda e: (seg_sort_key(e.src_seg), seg_sort_key(e.dst_seg), int(e.src_state[1:]), int(e.dst_state[1:])))

    lines.append("INTERNAL GATE FLOWS")
    lines.append("-" * 20)
    if not internal:
        lines.append("  (none)")
    else:
        for e in internal:
            lines.append(
                f"  {e.src_seg}.{e.src_state} --({e.gate_label})--> {e.dst_seg}.{e.dst_state}"
            )
    lines.append("")

    lines.append("CROSS-SEGMENT GATE FLOWS")
    lines.append("-" * 24)
    if not cross:
        lines.append("  (none)")
    else:
        for e in cross:
            lines.append(
                f"  {e.src_seg}.{e.src_state} ==({e.gate_label})==> {e.dst_seg}.{e.dst_state}"
            )
    lines.append("")

    lines.append("Legend:")
    lines.append("  ->           = sequential state flow within segment")
    lines.append("  --(gate)-->  = internal gate dependency")
    lines.append("  ==(gate)==>  = cross-segment gate dependency")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    impl_maps = sorted(IMPL_MAP_DIR.glob("segment_*.impl_map.yaml"))
    segments = [parse_segment_impl_map(p) for p in impl_maps]
    segments.sort(key=lambda s: (layer_sort_key(s.layer_id), seg_sort_key(s.segment_id)))

    edges = build_edges(segments)
    edges = simplify_gate_edges(segments, edges)

    dot_text = render_dot(segments, edges)
    mmd_text = render_mermaid(segments, edges)
    ascii_text = render_ascii(segments, edges)

    (OUT_DIR / "engine_state_network.dot").write_text(dot_text, encoding="utf-8")
    (OUT_DIR / "engine_state_network.mmd").write_text(mmd_text, encoding="utf-8")
    (OUT_DIR / "engine_state_network.txt").write_text(ascii_text, encoding="utf-8")

    print("Wrote:")
    print(f"- {(OUT_DIR / 'engine_state_network.dot').relative_to(REPO_ROOT)}")
    print(f"- {(OUT_DIR / 'engine_state_network.mmd').relative_to(REPO_ROOT)}")
    print(f"- {(OUT_DIR / 'engine_state_network.txt').relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
