from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


def find_repo_root(start: Path) -> Path:
    cur = start.resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    raise RuntimeError(f"Could not locate repo root from {start}")


REPO_ROOT = find_repo_root(Path(__file__))
IMPL_MAP_DIR = REPO_ROOT / "docs" / "model_spec" / "data-engine" / "implementation_maps"
OUT_DIR = REPO_ROOT / "docs" / "design" / "data-engine" / "engine_state_network"
ENGINE_SRC_ROOT = REPO_ROOT / "packages" / "engine" / "src"
ENGINE_LAYERS_ROOT = ENGINE_SRC_ROOT / "engine" / "layers"


@dataclass
class StateNode:
    seg_id: str
    layer_id: str
    seg_title: str
    state_id: str
    state_title: str
    state_class: str = "UNKNOWN"
    rng_posture: str = "UNKNOWN"
    reads: List[str] = field(default_factory=list)
    writes: List[str] = field(default_factory=list)
    runner_modules: List[str] = field(default_factory=list)


@dataclass
class SegmentNode:
    seg_id: str
    layer_id: str
    title: str
    states: Dict[str, StateNode] = field(default_factory=dict)

    @property
    def ordered_states(self) -> List[str]:
        return sorted(self.states.keys(), key=lambda x: int(x[1:]))


RNG_DISPLAY = {
    "RNG_NONE": "Deterministic",
    "RNG_CONSUMING": "RNG-driven",
    "RNG_MIXED": "Deterministic + RNG",
}

LAYER_DISPLAY = {
    "layer1": "Layer 1 - World and Merchant Realism",
    "layer2": "Layer 2 - Temporal Arrival Surfaces",
    "layer3": "Layer 3 - Behavior, Fraud, and Labels",
}


def load_gate_module():
    path = REPO_ROOT / "scripts" / "engine_state_network" / "generate_engine_state_network.py"
    spec = importlib.util.spec_from_file_location("gate_net", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load generate_engine_state_network.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def seg_sort_key(segment_id: str) -> Tuple[int, str]:
    m = re.match(r"^(\d+)([A-Z])$", segment_id)
    if not m:
        return (999, segment_id)
    return (int(m.group(1)), m.group(2))


def layer_sort_key(layer_id: str) -> int:
    m = re.match(r"^layer(\d+)$", layer_id)
    return int(m.group(1)) if m else 999


def parse_impl_map(path: Path, gate_mod) -> SegmentNode:
    text = gate_mod.read_text_robust(path)
    lines = text.splitlines()

    seg_id = ""
    layer_id = ""
    title = ""
    section = ""
    current_state: StateNode | None = None
    current_list = ""
    states: Dict[str, StateNode] = {}

    for line in lines:
        root_match = re.match(r"^[A-Za-z_][A-Za-z0-9_]*:\s*$", line)
        if root_match:
            section = line.split(":", 1)[0]
            if section != "states":
                current_state = None
                current_list = ""

        if not seg_id:
            m = re.match(r"^\s*segment_id:\s*(.+)\s*$", line)
            if m:
                seg_id = gate_mod.clean_scalar(m.group(1))
                continue

        if not layer_id:
            m = re.match(r"^\s*layer_id:\s*(.+)\s*$", line)
            if m:
                layer_id = gate_mod.clean_scalar(m.group(1))
                continue

        if not title:
            m = re.match(r"^\s*title:\s*(.+)\s*$", line)
            if m:
                title = gate_mod.clean_scalar(m.group(1))
                continue

        if section == "states":
            m_state = re.match(r"^  (S\d+):\s*$", line)
            if m_state:
                sid = m_state.group(1)
                state_title = gate_mod.find_state_title(seg_id, sid)
                current_state = StateNode(
                    seg_id=seg_id,
                    layer_id=layer_id,
                    seg_title=title,
                    state_id=sid,
                    state_title=state_title,
                )
                states[sid] = current_state
                current_list = ""
                continue

            if current_state is None:
                continue

            m_sc = re.match(r"^    state_class:\s*(.+)\s*$", line)
            if m_sc:
                current_state.state_class = gate_mod.clean_scalar(m_sc.group(1))
                continue

            m_rng = re.match(r"^    rng_posture:\s*(.+)\s*$", line)
            if m_rng:
                current_state.rng_posture = gate_mod.clean_scalar(m_rng.group(1))
                continue

            if re.match(r"^    reads:\s*$", line):
                current_list = "reads"
                continue

            if re.match(r"^    writes:\s*$", line):
                current_list = "writes"
                continue

            m_ds = re.match(r"^\s*-\s*dataset_id:\s*(.+)\s*$", line)
            if m_ds and current_list in {"reads", "writes"}:
                ds = gate_mod.clean_scalar(m_ds.group(1))
                if current_list == "reads":
                    current_state.reads.append(ds)
                else:
                    current_state.writes.append(ds)
                continue

            if re.match(r"^    [A-Za-z_][A-Za-z0-9_]*:\s*", line):
                current_list = ""

    if not seg_id or not layer_id or not title or not states:
        raise ValueError(f"Could not parse segment info from {path}")

    return SegmentNode(seg_id=seg_id, layer_id=layer_id, title=title, states=states)


def discover_runner_modules() -> Dict[Tuple[str, str], List[str]]:
    mapping: Dict[Tuple[str, str], List[str]] = {}
    for runner in ENGINE_LAYERS_ROOT.rglob("runner.py"):
        norm = str(runner).replace("\\", "/")
        m = re.search(r"/seg_([0-9A-Z]+)/s(\d+)[^/]*/runner\.py$", norm)
        if not m:
            continue
        seg_id = m.group(1)
        state_id = f"S{int(m.group(2))}"
        rel = runner.relative_to(ENGINE_SRC_ROOT).with_suffix("")
        module = ".".join(rel.parts)
        mapping.setdefault((seg_id, state_id), []).append(module)

    for key in mapping:
        mapping[key] = sorted(set(mapping[key]))
    return mapping


def segment_node_id(seg_id: str) -> str:
    return f"seg_{seg_id}"


def segment_chain(segments: List[SegmentNode]) -> List[SegmentNode]:
    return sorted(segments, key=lambda s: (layer_sort_key(s.layer_id), seg_sort_key(s.seg_id)))


def build_docs_gate_refs(gate_mod) -> Dict[Tuple[str, str], Set[str]]:
    impl_maps = sorted(IMPL_MAP_DIR.glob("segment_*.impl_map.yaml"))
    g_segments = [gate_mod.parse_segment_impl_map(p) for p in impl_maps]
    g_segments.sort(key=lambda s: (gate_mod.layer_sort_key(s.layer_id), gate_mod.seg_sort_key(s.segment_id)))
    edges = gate_mod.simplify_gate_edges(g_segments, gate_mod.build_edges(g_segments))
    refs: Dict[Tuple[str, str], Set[str]] = {}
    for edge in edges:
        if edge.src_seg == edge.dst_seg:
            continue
        refs.setdefault((edge.src_seg, edge.dst_seg), set()).add(edge.gate_id)
    return refs


def render_docs_lite_dot(segments: List[SegmentNode], gate_refs: Dict[Tuple[str, str], Set[str]]) -> str:
    lines: List[str] = []
    lines.append("digraph EngineStateGateLite {")
    lines.append('  graph [rankdir=LR, fontsize=10, fontname="Helvetica", labelloc=t,')
    lines.append('         label="Data Engine State/Gate View (docs-driven, simplified)"];')
    lines.append('  node  [shape=box, style="rounded,filled", fillcolor=white, color="#4b5563", fontname="Helvetica", fontsize=10];')
    lines.append('  edge  [color="#6b7280", fontname="Helvetica", fontsize=8];')
    lines.append("")

    layer_colors = {"layer1": "#e8f0fe", "layer2": "#e6fffa", "layer3": "#fff7ed"}
    by_layer: Dict[str, List[SegmentNode]] = {}
    for seg in segments:
        by_layer.setdefault(seg.layer_id, []).append(seg)

    for layer in sorted(by_layer.keys(), key=layer_sort_key):
        lines.append(f"  subgraph cluster_{layer} {{")
        lines.append(f'    label="{dot_escape(LAYER_DISPLAY.get(layer, layer))}";')
        lines.append('    style="rounded,filled";')
        lines.append(f'    color="{layer_colors.get(layer, "#f3f4f6")}";')
        for seg in sorted(by_layer[layer], key=lambda s: seg_sort_key(s.seg_id)):
            label = f"{seg.seg_id}\\n{seg.title}\\n{len(seg.states)} states"
            lines.append(f'    {segment_node_id(seg.seg_id)} [label="{dot_escape(label)}"];')
        lines.append("  }")
        lines.append("")

    ordered = segment_chain(segments)
    chain_edges = {(ordered[i].seg_id, ordered[i + 1].seg_id) for i in range(len(ordered) - 1)}
    lines.append("  // canonical segment progression")
    for src, dst in sorted(chain_edges, key=lambda t: (seg_sort_key(t[0]), seg_sort_key(t[1]))):
        lines.append(
            f'  {segment_node_id(src)} -> {segment_node_id(dst)} [color="#334155", penwidth=1.8, label="phase progression"];'
        )

    lines.append("")
    lines.append("  // cross-segment gate dependencies")
    for (src, dst), gate_ids in sorted(gate_refs.items(), key=lambda kv: (seg_sort_key(kv[0][0]), seg_sort_key(kv[0][1]))):
        if (src, dst) in chain_edges:
            continue
        lines.append(
            f'  {segment_node_id(src)} -> {segment_node_id(dst)} '
            f'[style=dashed, color="#D97706", penwidth=1.2, label="gate ref"];'
        )

    lines.append("}")
    return "\n".join(lines) + "\n"


def render_docs_lite_mmd(segments: List[SegmentNode], gate_refs: Dict[Tuple[str, str], Set[str]]) -> str:
    lines: List[str] = []
    lines.append("flowchart LR")
    lines.append("%% Data Engine state/gate view (docs-driven, simplified)")
    lines.append("")

    by_layer: Dict[str, List[SegmentNode]] = {}
    for seg in segments:
        by_layer.setdefault(seg.layer_id, []).append(seg)

    for layer in sorted(by_layer.keys(), key=layer_sort_key):
        lines.append(f'  subgraph {layer.upper()}["{mmd_escape(LAYER_DISPLAY.get(layer, layer))}"]')
        for seg in sorted(by_layer[layer], key=lambda s: seg_sort_key(s.seg_id)):
            lines.append(
                f'    {segment_node_id(seg.seg_id)}["{mmd_escape(seg.seg_id + " - " + seg.title)}<br/>{len(seg.states)} states"]'
            )
        lines.append("  end")
        lines.append("")

    ordered = segment_chain(segments)
    chain_edges = {(ordered[i].seg_id, ordered[i + 1].seg_id) for i in range(len(ordered) - 1)}
    for src, dst in sorted(chain_edges, key=lambda t: (seg_sort_key(t[0]), seg_sort_key(t[1]))):
        lines.append(f'  {segment_node_id(src)} -->|phase progression| {segment_node_id(dst)}')

    for (src, dst), _gate_ids in sorted(gate_refs.items(), key=lambda kv: (seg_sort_key(kv[0][0]), seg_sort_key(kv[0][1]))):
        if (src, dst) in chain_edges:
            continue
        lines.append(f'  {segment_node_id(src)} -.->|gate ref| {segment_node_id(dst)}')

    return "\n".join(lines) + "\n"


def render_docs_lite_ascii(segments: List[SegmentNode], gate_refs: Dict[Tuple[str, str], Set[str]]) -> str:
    lines: List[str] = []
    lines.append("DATA ENGINE STATE/GATE VIEW (docs-driven, simplified)")
    lines.append("Source basis: state-expanded docs + segment impl maps")
    lines.append("=" * 84)
    lines.append("")

    by_layer: Dict[str, List[SegmentNode]] = {}
    for seg in segments:
        by_layer.setdefault(seg.layer_id, []).append(seg)

    for layer in sorted(by_layer.keys(), key=layer_sort_key):
        header = LAYER_DISPLAY.get(layer, layer)
        lines.append(header)
        lines.append("-" * len(header))
        for seg in sorted(by_layer[layer], key=lambda s: seg_sort_key(s.seg_id)):
            lines.append(f"  {seg.seg_id}: {seg.title} ({len(seg.states)} states)")
        lines.append("")

    ordered = segment_chain(segments)
    lines.append("Canonical progression:")
    lines.append("  " + " -> ".join(seg.seg_id for seg in ordered))
    lines.append("")

    lines.append("Cross-segment gate refs:")
    chain_edges = {(ordered[i].seg_id, ordered[i + 1].seg_id) for i in range(len(ordered) - 1)}
    rows = []
    for (src, dst), _gate_ids in sorted(gate_refs.items(), key=lambda kv: (seg_sort_key(kv[0][0]), seg_sort_key(kv[0][1]))):
        if (src, dst) in chain_edges:
            continue
        rows.append(f"  {src} -> {dst} (gate ref)")
    if rows:
        lines.extend(rows)
    else:
        lines.append("  (none)")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_docs_state_gate_outputs(segments: List[SegmentNode], gate_mod) -> None:
    gate_refs = build_docs_gate_refs(gate_mod)
    dot_text = render_docs_lite_dot(segments, gate_refs)
    mmd_text = render_docs_lite_mmd(segments, gate_refs)
    txt_text = render_docs_lite_ascii(segments, gate_refs)

    (OUT_DIR / "engine_state_network.dot").write_text(dot_text, encoding="utf-8")
    (OUT_DIR / "engine_state_network.mmd").write_text(mmd_text, encoding="utf-8")
    (OUT_DIR / "engine_state_network.txt").write_text(txt_text, encoding="utf-8")

    (OUT_DIR / "engine_state_gate_view.dot").write_text(dot_text, encoding="utf-8")
    (OUT_DIR / "engine_state_gate_view.mmd").write_text(mmd_text, encoding="utf-8")
    (OUT_DIR / "engine_state_gate_view.txt").write_text(txt_text, encoding="utf-8")


def build_code_io_view(segments: List[SegmentNode]):
    state_lookup: Dict[Tuple[str, str], StateNode] = {}
    for seg in segments:
        for sid, state in seg.states.items():
            state_lookup[(seg.seg_id, sid)] = state

    producers: Dict[str, Set[Tuple[str, str]]] = {}
    for key, state in state_lookup.items():
        for ds in state.writes:
            producers.setdefault(ds, set()).add(key)

    data_edges: Dict[Tuple[Tuple[str, str], Tuple[str, str]], Set[str]] = {}
    unresolved: Dict[Tuple[str, str], Set[str]] = {}

    for dst_key, state in state_lookup.items():
        for ds in state.reads:
            srcs = producers.get(ds, set())
            if not srcs:
                unresolved.setdefault(dst_key, set()).add(ds)
                continue
            for src_key in srcs:
                if src_key == dst_key:
                    continue
                data_edges.setdefault((src_key, dst_key), set()).add(ds)

    return data_edges, unresolved


def node_id(seg_id: str, state_id: str) -> str:
    return f"n_{seg_id}_{state_id}"


def short_owner(modules: List[str]) -> str:
    if not modules:
        return "runner: MISSING"
    if len(modules) == 1:
        return modules[0]
    return f"{modules[0]} (+{len(modules)-1})"


def format_dataset_label(dataset_ids: Set[str], max_items: int = 3) -> str:
    items = sorted(dataset_ids)
    if len(items) <= max_items:
        return ", ".join(items)
    head = ", ".join(items[:max_items])
    return f"{head} (+{len(items)-max_items})"


def dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def mmd_escape(text: str) -> str:
    return text.replace('"', "'")


def render_code_io_dot(segments: List[SegmentNode], data_edges, unresolved) -> str:
    lines: List[str] = []
    lines.append("digraph EngineCodeIOOwnership {")
    lines.append('  graph [rankdir=LR, fontsize=10, fontname="Helvetica", labelloc=t,')
    lines.append('         label="Data Engine Code-Derived IO Ownership Flow (state owners + dataset flows)"];')
    lines.append('  node  [shape=box, style="rounded,filled", fillcolor=white, color="#4b5563", fontname="Helvetica", fontsize=9];')
    lines.append('  edge  [color="#6b7280", fontname="Helvetica", fontsize=8];')
    lines.append('  external_refs [shape=folder, fillcolor="#FEF3C7", label="External Authorities / Reference Datasets"];')
    lines.append("")

    layer_colors = {"layer1": "#e8f0fe", "layer2": "#e6fffa", "layer3": "#fff7ed"}

    by_layer: Dict[str, List[SegmentNode]] = {}
    for seg in segments:
        by_layer.setdefault(seg.layer_id, []).append(seg)

    for layer in sorted(by_layer.keys(), key=layer_sort_key):
        lines.append(f"  subgraph cluster_{layer} {{")
        lines.append(f'    label="{dot_escape(LAYER_DISPLAY.get(layer, layer))}";')
        lines.append('    style="rounded,filled";')
        lines.append(f'    color="{layer_colors.get(layer, "#f3f4f6")}";')

        for seg in sorted(by_layer[layer], key=lambda x: seg_sort_key(x.seg_id)):
            lines.append(f"    subgraph cluster_{seg.seg_id} {{")
            lines.append(f'      label="{dot_escape(seg.seg_id + " | " + seg.title)}";')
            lines.append('      style="rounded";')
            lines.append('      color="#94a3b8";')

            for sid in seg.ordered_states:
                st = seg.states[sid]
                mode = RNG_DISPLAY.get(st.rng_posture, st.rng_posture)
                owner = short_owner(st.runner_modules)
                label = (
                    f"{seg.seg_id}.{sid} {st.state_title}\\n"
                    f"{mode}\\n"
                    f"owner: {owner}\\n"
                    f"R={len(st.reads)} W={len(st.writes)}"
                )
                lines.append(f'      {node_id(seg.seg_id, sid)} [label="{dot_escape(label)}"];')

            lines.append("    }")
        lines.append("  }")
        lines.append("")

    # Sequential edges
    lines.append("  // sequential state progression")
    for seg in sorted(segments, key=lambda x: (layer_sort_key(x.layer_id), seg_sort_key(x.seg_id))):
        ordered = seg.ordered_states
        for i in range(len(ordered) - 1):
            lines.append(
                f"  {node_id(seg.seg_id, ordered[i])} -> {node_id(seg.seg_id, ordered[i+1])} "
                f'[color="#64748b", penwidth=1.2];'
            )
    lines.append("")

    # Dataflow edges
    lines.append("  // code-derived dataset flow edges (producer -> consumer)")
    for (src, dst), datasets in sorted(
        data_edges.items(),
        key=lambda kv: (seg_sort_key(kv[0][0][0]), int(kv[0][0][1][1:]), seg_sort_key(kv[0][1][0]), int(kv[0][1][1][1:])),
    ):
        cross = src[0] != dst[0]
        style = 'style=bold, color="#dc2626", penwidth=1.6' if cross else 'style=dashed, color="#2563eb", penwidth=1.2'
        label = format_dataset_label(datasets)
        lines.append(
            f"  {node_id(src[0], src[1])} -> {node_id(dst[0], dst[1])} "
            f'[label="{dot_escape(label)}", {style}];'
        )

    lines.append("")
    lines.append("  // unresolved reads (no in-engine producer state in parsed scope)")
    for dst, datasets in sorted(
        unresolved.items(), key=lambda kv: (seg_sort_key(kv[0][0]), int(kv[0][1][1:]))
    ):
        label = format_dataset_label(datasets)
        lines.append(
            f"  external_refs -> {node_id(dst[0], dst[1])} "
            f'[label="{dot_escape(label)}", style=dotted, color="#D97706", penwidth=1.1];'
        )

    lines.append("}")
    return "\n".join(lines) + "\n"


def render_code_io_mmd(segments: List[SegmentNode], data_edges, unresolved) -> str:
    lines: List[str] = []
    lines.append("flowchart LR")
    lines.append("%% Data Engine code-derived IO ownership flow (state owners + dataset flows)")
    lines.append('  EXTERNAL[[External Authorities / Reference Datasets]]')
    lines.append("")

    by_layer: Dict[str, List[SegmentNode]] = {}
    for seg in segments:
        by_layer.setdefault(seg.layer_id, []).append(seg)

    for layer in sorted(by_layer.keys(), key=layer_sort_key):
        lines.append(f'  subgraph {layer.upper()}["{mmd_escape(LAYER_DISPLAY.get(layer, layer))}"]')
        for seg in sorted(by_layer[layer], key=lambda x: seg_sort_key(x.seg_id)):
            lines.append(f'    subgraph SEG_{seg.seg_id}["{mmd_escape(seg.seg_id + ": " + seg.title)}"]')
            for sid in seg.ordered_states:
                st = seg.states[sid]
                mode = RNG_DISPLAY.get(st.rng_posture, st.rng_posture)
                owner = short_owner(st.runner_modules)
                lines.append(
                    f'      {node_id(seg.seg_id, sid)}["{mmd_escape(seg.seg_id)}.{mmd_escape(sid)} {mmd_escape(st.state_title)}<br/>{mmd_escape(mode)}<br/>owner: {mmd_escape(owner)}<br/>R={len(st.reads)} W={len(st.writes)}"]'
                )
            lines.append("    end")
        lines.append("  end")
        lines.append("")

    lines.append("  %% sequential progression")
    for seg in sorted(segments, key=lambda x: (layer_sort_key(x.layer_id), seg_sort_key(x.seg_id))):
        ordered = seg.ordered_states
        for i in range(len(ordered) - 1):
            lines.append(f"  {node_id(seg.seg_id, ordered[i])} --> {node_id(seg.seg_id, ordered[i+1])}")

    lines.append("")
    lines.append("  %% dataset flow edges (producer -> consumer)")
    for (src, dst), datasets in sorted(
        data_edges.items(),
        key=lambda kv: (seg_sort_key(kv[0][0][0]), int(kv[0][0][1][1:]), seg_sort_key(kv[0][1][0]), int(kv[0][1][1][1:])),
    ):
        label = mmd_escape(format_dataset_label(datasets, max_items=2))
        if src[0] != dst[0]:
            lines.append(f'  {node_id(src[0], src[1])} == "{label}" ==> {node_id(dst[0], dst[1])}')
        else:
            lines.append(f'  {node_id(src[0], src[1])} -. "{label}" .-> {node_id(dst[0], dst[1])}')

    lines.append("")
    lines.append("  %% unresolved external reads")
    for dst, datasets in sorted(unresolved.items(), key=lambda kv: (seg_sort_key(kv[0][0]), int(kv[0][1][1:]))):
        label = mmd_escape(format_dataset_label(datasets, max_items=2))
        lines.append(f'  EXTERNAL -. "{label}" .-> {node_id(dst[0], dst[1])}')

    return "\n".join(lines) + "\n"


def render_code_io_ascii(segments: List[SegmentNode], data_edges, unresolved) -> str:
    lines: List[str] = []
    lines.append("DATA ENGINE CODE-DERIVED IO OWNERSHIP FLOW")
    lines.append("Source basis: packages/engine runner modules + segment_*.impl_map.yaml reads/writes")
    lines.append("View intent: understandable labels with true owner modules and dataset flow contracts")
    lines.append("=" * 104)
    lines.append("")

    for layer in sorted({s.layer_id for s in segments}, key=layer_sort_key):
        header = LAYER_DISPLAY.get(layer, layer)
        lines.append(header)
        lines.append("-" * len(header))
        for seg in sorted([s for s in segments if s.layer_id == layer], key=lambda s: seg_sort_key(s.seg_id)):
            lines.append(f"  {seg.seg_id}  {seg.title}")
            for sid in seg.ordered_states:
                st = seg.states[sid]
                mode = RNG_DISPLAY.get(st.rng_posture, st.rng_posture)
                owner = short_owner(st.runner_modules)
                reads = ", ".join(sorted(set(st.reads))[:4])
                writes = ", ".join(sorted(set(st.writes))[:4])
                if len(set(st.reads)) > 4:
                    reads += f", ... (+{len(set(st.reads)) - 4})"
                if len(set(st.writes)) > 4:
                    writes += f", ... (+{len(set(st.writes)) - 4})"
                lines.append(f"    {sid} {st.state_title}")
                lines.append(f"      mode: {mode}")
                lines.append(f"      owner: {owner}")
                lines.append(f"      reads ({len(st.reads)}): {reads if reads else '-'}")
                lines.append(f"      writes ({len(st.writes)}): {writes if writes else '-'}")
            lines.append("")

    lines.append("DATAFLOW EDGES (producer state -> consumer state)")
    lines.append("-" * 52)
    if not data_edges:
        lines.append("  (none)")
    else:
        for (src, dst), datasets in sorted(
            data_edges.items(),
            key=lambda kv: (seg_sort_key(kv[0][0][0]), int(kv[0][0][1][1:]), seg_sort_key(kv[0][1][0]), int(kv[0][1][1][1:])),
        ):
            style = "CROSS" if src[0] != dst[0] else "INTERNAL"
            lines.append(
                f"  [{style}] {src[0]}.{src[1]} -> {dst[0]}.{dst[1]} : {format_dataset_label(datasets, max_items=4)}"
            )

    lines.append("")
    lines.append("UNRESOLVED EXTERNAL READS (no producer state in parsed engine scope)")
    lines.append("-" * 72)
    if not unresolved:
        lines.append("  (none)")
    else:
        for dst, datasets in sorted(unresolved.items(), key=lambda kv: (seg_sort_key(kv[0][0]), int(kv[0][1][1:]))):
            lines.append(f"  {dst[0]}.{dst[1]} <- EXTERNAL : {format_dataset_label(datasets, max_items=5)}")

    lines.append("")
    lines.append("Legend:")
    lines.append("  owner      = runner module(s) discovered under packages/engine/src/engine/layers/**/seg_*/s*_*/runner.py")
    lines.append("  reads/writes = dataset_id contracts parsed from segment_*.impl_map.yaml state cards")
    lines.append("  CROSS flow = dataset written in one segment/state and consumed by a different segment/state")
    return "\n".join(lines) + "\n"


def segment_owner_hint(seg: SegmentNode) -> str:
    modules: Set[str] = set()
    for state in seg.states.values():
        modules.update(state.runner_modules)
    if not modules:
        return "owner module not found"
    prefixes: Set[str] = set()
    for mod in modules:
        m = re.match(r"(engine\.layers\.[^.]+\.seg_[^.]+)\..+", mod)
        if m:
            prefixes.add(m.group(1) + ".*")
    if prefixes:
        pref = sorted(prefixes)
        return pref[0] if len(pref) == 1 else f"{pref[0]} (+{len(pref)-1})"
    mod = sorted(modules)
    return mod[0] if len(mod) == 1 else f"{mod[0]} (+{len(mod)-1})"


def collapse_code_io_segment_edges(
    segments: List[SegmentNode],
    data_edges,
    unresolved,
    max_edges_per_source: int = 2,
):
    seg_index = {seg.seg_id: idx for idx, seg in enumerate(segment_chain(segments))}
    seg_edges: Dict[Tuple[str, str], Set[str]] = {}
    for (src, dst), datasets in data_edges.items():
        src_seg, dst_seg = src[0], dst[0]
        if src_seg == dst_seg:
            continue
        # Keep forward data-flow for readability.
        if seg_index[src_seg] >= seg_index[dst_seg]:
            continue
        seg_edges.setdefault((src_seg, dst_seg), set()).update(datasets)

    selected: Dict[Tuple[str, str], Set[str]] = {}
    by_src: Dict[str, List[Tuple[str, Set[str]]]] = {}
    for (src, dst), datasets in seg_edges.items():
        by_src.setdefault(src, []).append((dst, datasets))

    for src, candidates in by_src.items():
        candidates.sort(key=lambda x: (len(x[1]), -seg_index[x[0]]), reverse=True)
        for dst, datasets in candidates[:max_edges_per_source]:
            selected[(src, dst)] = set(datasets)

    ordered = segment_chain(segments)
    for i in range(len(ordered) - 1):
        src = ordered[i].seg_id
        dst = ordered[i + 1].seg_id
        key = (src, dst)
        if key in seg_edges and key not in selected:
            selected[key] = set(seg_edges[key])

    unresolved_seg: Dict[str, Set[str]] = {}
    for (dst_seg, _dst_state), datasets in unresolved.items():
        unresolved_seg.setdefault(dst_seg, set()).update(datasets)

    return selected, unresolved_seg


def render_code_io_lite_dot(segments: List[SegmentNode], seg_edges, unresolved_seg) -> str:
    lines: List[str] = []
    lines.append("digraph EngineCodeIOLite {")
    lines.append('  graph [rankdir=LR, fontsize=10, fontname="Helvetica", labelloc=t,')
    lines.append('         label="Data Engine Code-Level IO Ownership Flow (simplified)"];')
    lines.append('  node  [shape=box, style="rounded,filled", fillcolor=white, color="#4b5563", fontname="Helvetica", fontsize=9];')
    lines.append('  edge  [color="#6b7280", fontname="Helvetica", fontsize=8];')
    lines.append('  external_refs [shape=folder, fillcolor="#FEF3C7", label="External refs / authorities"];')
    lines.append("")

    layer_colors = {"layer1": "#e8f0fe", "layer2": "#e6fffa", "layer3": "#fff7ed"}
    by_layer: Dict[str, List[SegmentNode]] = {}
    for seg in segments:
        by_layer.setdefault(seg.layer_id, []).append(seg)

    for layer in sorted(by_layer.keys(), key=layer_sort_key):
        lines.append(f"  subgraph cluster_{layer} {{")
        lines.append(f'    label="{dot_escape(LAYER_DISPLAY.get(layer, layer))}";')
        lines.append('    style="rounded,filled";')
        lines.append(f'    color="{layer_colors.get(layer, "#f3f4f6")}";')
        for seg in sorted(by_layer[layer], key=lambda s: seg_sort_key(s.seg_id)):
            reads = len({ds for st in seg.states.values() for ds in st.reads})
            writes = len({ds for st in seg.states.values() for ds in st.writes})
            label = (
                f"{seg.seg_id}\\n{seg.title}\\n"
                f"owner: {segment_owner_hint(seg)}\\n"
                f"IO contract: R={reads} W={writes}"
            )
            lines.append(f'    {segment_node_id(seg.seg_id)} [label="{dot_escape(label)}"];')
        lines.append("  }")
        lines.append("")

    ordered = segment_chain(segments)
    chain_edges = {(ordered[i].seg_id, ordered[i + 1].seg_id) for i in range(len(ordered) - 1)}
    lines.append("  // canonical segment progression")
    for src, dst in sorted(chain_edges, key=lambda t: (seg_sort_key(t[0]), seg_sort_key(t[1]))):
        lines.append(
            f'  {segment_node_id(src)} -> {segment_node_id(dst)} [color="#334155", penwidth=1.8, label="phase progression"];'
        )

    lines.append("")
    lines.append("  // strongest code-derived dataset flows (collapsed to segment level)")
    for (src, dst), datasets in sorted(seg_edges.items(), key=lambda kv: (seg_sort_key(kv[0][0]), seg_sort_key(kv[0][1]))):
        lbl = format_dataset_label(datasets, max_items=2)
        style = 'style=bold, color="#DC2626", penwidth=1.4' if (src, dst) not in chain_edges else 'style=dashed, color="#2563EB", penwidth=1.2'
        lines.append(
            f'  {segment_node_id(src)} -> {segment_node_id(dst)} [label="{dot_escape(lbl)}", {style}];'
        )

    lines.append("")
    lines.append("  // unresolved external reads")
    for dst, datasets in sorted(unresolved_seg.items(), key=lambda kv: seg_sort_key(kv[0])):
        lbl = format_dataset_label(datasets, max_items=2)
        lines.append(
            f'  external_refs -> {segment_node_id(dst)} [label="{dot_escape(lbl)}", style=dotted, color="#D97706", penwidth=1.1];'
        )

    lines.append("}")
    return "\n".join(lines) + "\n"


def render_code_io_lite_mmd(segments: List[SegmentNode], seg_edges, unresolved_seg) -> str:
    lines: List[str] = []
    lines.append("flowchart LR")
    lines.append("%% Data Engine code-level IO ownership flow (simplified)")
    lines.append('  EXTERNAL[[External refs / authorities]]')
    lines.append("")

    by_layer: Dict[str, List[SegmentNode]] = {}
    for seg in segments:
        by_layer.setdefault(seg.layer_id, []).append(seg)

    for layer in sorted(by_layer.keys(), key=layer_sort_key):
        lines.append(f'  subgraph {layer.upper()}["{mmd_escape(LAYER_DISPLAY.get(layer, layer))}"]')
        for seg in sorted(by_layer[layer], key=lambda s: seg_sort_key(s.seg_id)):
            reads = len({ds for st in seg.states.values() for ds in st.reads})
            writes = len({ds for st in seg.states.values() for ds in st.writes})
            lines.append(
                f'    {segment_node_id(seg.seg_id)}["{mmd_escape(seg.seg_id + " - " + seg.title)}<br/>owner: {mmd_escape(segment_owner_hint(seg))}<br/>IO: R={reads} W={writes}"]'
            )
        lines.append("  end")
        lines.append("")

    ordered = segment_chain(segments)
    chain_edges = {(ordered[i].seg_id, ordered[i + 1].seg_id) for i in range(len(ordered) - 1)}
    for src, dst in sorted(chain_edges, key=lambda t: (seg_sort_key(t[0]), seg_sort_key(t[1]))):
        lines.append(f'  {segment_node_id(src)} -->|phase progression| {segment_node_id(dst)}')

    for (src, dst), datasets in sorted(seg_edges.items(), key=lambda kv: (seg_sort_key(kv[0][0]), seg_sort_key(kv[0][1]))):
        lbl = mmd_escape(format_dataset_label(datasets, max_items=2))
        if (src, dst) in chain_edges:
            lines.append(f'  {segment_node_id(src)} -. "{lbl}" .-> {segment_node_id(dst)}')
        else:
            lines.append(f'  {segment_node_id(src)} == "{lbl}" ==> {segment_node_id(dst)}')

    for dst, datasets in sorted(unresolved_seg.items(), key=lambda kv: seg_sort_key(kv[0])):
        lbl = mmd_escape(format_dataset_label(datasets, max_items=2))
        lines.append(f'  EXTERNAL -. "{lbl}" .-> {segment_node_id(dst)}')

    return "\n".join(lines) + "\n"


def render_code_io_lite_ascii(segments: List[SegmentNode], seg_edges, unresolved_seg) -> str:
    lines: List[str] = []
    lines.append("DATA ENGINE CODE-LEVEL IO OWNERSHIP FLOW (simplified)")
    lines.append("Source basis: engine runner modules + impl-map read/write contracts")
    lines.append("=" * 92)
    lines.append("")

    by_layer: Dict[str, List[SegmentNode]] = {}
    for seg in segments:
        by_layer.setdefault(seg.layer_id, []).append(seg)

    for layer in sorted(by_layer.keys(), key=layer_sort_key):
        header = LAYER_DISPLAY.get(layer, layer)
        lines.append(header)
        lines.append("-" * len(header))
        for seg in sorted(by_layer[layer], key=lambda s: seg_sort_key(s.seg_id)):
            reads = len({ds for st in seg.states.values() for ds in st.reads})
            writes = len({ds for st in seg.states.values() for ds in st.writes})
            lines.append(f"  {seg.seg_id}: {seg.title}")
            lines.append(f"    owner: {segment_owner_hint(seg)}")
            lines.append(f"    IO contract counts: R={reads} W={writes}")
        lines.append("")

    lines.append("Primary code-derived data flows (segment -> segment):")
    if not seg_edges:
        lines.append("  (none)")
    else:
        for (src, dst), datasets in sorted(seg_edges.items(), key=lambda kv: (seg_sort_key(kv[0][0]), seg_sort_key(kv[0][1]))):
            lines.append(f"  {src} -> {dst}: {format_dataset_label(datasets, max_items=3)}")
    lines.append("")

    lines.append("External dependencies (unresolved reads in engine scope):")
    if not unresolved_seg:
        lines.append("  (none)")
    else:
        for dst, datasets in sorted(unresolved_seg.items(), key=lambda kv: seg_sort_key(kv[0])):
            lines.append(f"  EXTERNAL -> {dst}: {format_dataset_label(datasets, max_items=3)}")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_code_io_outputs(segments: List[SegmentNode], data_edges, unresolved) -> None:
    seg_edges, unresolved_seg = collapse_code_io_segment_edges(segments, data_edges, unresolved, max_edges_per_source=2)
    dot_text = render_code_io_lite_dot(segments, seg_edges, unresolved_seg)
    mmd_text = render_code_io_lite_mmd(segments, seg_edges, unresolved_seg)
    txt_text = render_code_io_lite_ascii(segments, seg_edges, unresolved_seg)
    (OUT_DIR / "engine_code_io_ownership_flow.dot").write_text(dot_text, encoding="utf-8")
    (OUT_DIR / "engine_code_io_ownership_flow.mmd").write_text(mmd_text, encoding="utf-8")
    (OUT_DIR / "engine_code_io_ownership_flow.txt").write_text(txt_text, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    gate_mod = load_gate_module()

    segments: List[SegmentNode] = []
    for path in sorted(IMPL_MAP_DIR.glob("segment_*.impl_map.yaml")):
        segments.append(parse_impl_map(path, gate_mod))

    segments.sort(key=lambda s: (layer_sort_key(s.layer_id), seg_sort_key(s.seg_id)))

    write_docs_state_gate_outputs(segments, gate_mod)

    runners = discover_runner_modules()
    for seg in segments:
        for sid, state in seg.states.items():
            state.runner_modules = runners.get((seg.seg_id, sid), [])

    data_edges, unresolved = build_code_io_view(segments)
    write_code_io_outputs(segments, data_edges, unresolved)

    print("Wrote state/gate relabeled views:")
    print(f"- {(OUT_DIR / 'engine_state_network.dot').relative_to(REPO_ROOT)}")
    print(f"- {(OUT_DIR / 'engine_state_network.mmd').relative_to(REPO_ROOT)}")
    print(f"- {(OUT_DIR / 'engine_state_network.txt').relative_to(REPO_ROOT)}")
    print(f"- {(OUT_DIR / 'engine_state_gate_view.dot').relative_to(REPO_ROOT)}")
    print(f"- {(OUT_DIR / 'engine_state_gate_view.mmd').relative_to(REPO_ROOT)}")
    print(f"- {(OUT_DIR / 'engine_state_gate_view.txt').relative_to(REPO_ROOT)}")
    print("Wrote code-derived IO ownership views:")
    print(f"- {(OUT_DIR / 'engine_code_io_ownership_flow.dot').relative_to(REPO_ROOT)}")
    print(f"- {(OUT_DIR / 'engine_code_io_ownership_flow.mmd').relative_to(REPO_ROOT)}")
    print(f"- {(OUT_DIR / 'engine_code_io_ownership_flow.txt').relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
