from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import yaml


ROOT = Path("docs/model_spec/data-engine")
TMP_DIR = Path("docs/tmp")


def normalize_path(path: str | None) -> str | None:
    if not path or not isinstance(path, str):
        return None
    if "\n" in path:
        path = "".join(path.splitlines())
    return path.strip()


def collect_paths(files: list[Path], id_key_preference: list[str]):
    path_to_ids = defaultdict(set)
    id_to_paths = defaultdict(set)

    for file_path in files:
        try:
            data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        def walk(obj):
            if isinstance(obj, dict):
                if "path" in obj and isinstance(obj.get("path"), str):
                    path = normalize_path(obj["path"])
                    if not path:
                        return
                    id_value = None
                    for key in id_key_preference:
                        if key in obj and isinstance(obj[key], str):
                            id_value = obj[key]
                            break
                    if not id_value:
                        return
                    path_to_ids[path].add(id_value)
                    id_to_paths[id_value].add(path)
                for value in obj.values():
                    walk(value)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)

    return path_to_ids, id_to_paths


def is_scoped_path(path: str) -> bool:
    return ("/layer1/" in path) or ("/layer2/" in path) or ("/layer3/" in path) or ("segment=" in path)


def build_tree(path_to_ids: dict[str, set[str]]):
    tree = {"_ids": set(), "_leaf_dir": False, "_children": {}}

    for raw_path, ids in path_to_ids.items():
        path = raw_path
        leaf_dir = path.endswith("/")
        if leaf_dir:
            path = path.rstrip("/")
        parts = [part for part in path.split("/") if part]
        node = tree
        for part in parts:
            node = node["_children"].setdefault(part, {"_ids": set(), "_leaf_dir": False, "_children": {}})
        node["_ids"].update(ids)
        if leaf_dir:
            node["_leaf_dir"] = True

    return tree


def render_tree(node, prefix: str = ""):
    lines: list[str] = []
    for name in sorted(node["_children"].keys()):
        child = node["_children"][name]
        has_children = bool(child["_children"])
        is_dir = has_children or child["_leaf_dir"]
        label = name + ("/" if is_dir else "")
        ids = ""
        if child["_ids"]:
            ids = "  [id: " + ", ".join(sorted(child["_ids"])) + "]"
        lines.append(prefix + label + ids)
        if has_children:
            lines.extend(render_tree(child, prefix + "  "))
    return lines


def write_tree(path_to_ids: dict[str, set[str]], header: str, output_path: Path):
    tree = build_tree(path_to_ids)
    lines = [header, "=" * len(header), ""]
    lines.extend(render_tree(tree))
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    dict_files = list(ROOT.rglob("specs/contracts/**/dataset_dictionary*.yaml"))
    registry_files = list(ROOT.rglob("specs/contracts/**/artefact_registry*.yaml"))

    dict_paths, dict_id_paths = collect_paths(dict_files, ["id"])
    reg_paths, reg_id_paths = collect_paths(registry_files, ["name", "id"])

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    write_tree(dict_paths, "DICTIONARY PATH TREE (ALL SEGMENTS COMBINED)", TMP_DIR / "paths_tree_dictionary_all.txt")
    write_tree(reg_paths, "REGISTRY PATH TREE (ALL SEGMENTS COMBINED)", TMP_DIR / "paths_tree_registry_all.txt")

    registry_collisions: dict[str, set[str]] = {}
    registry_expected_by_path: dict[str, set[str]] = {}
    for path, ids in reg_paths.items():
        if len(ids) > 1:
            if is_scoped_path(path):
                registry_expected_by_path[path] = ids
            else:
                registry_collisions[path] = ids

    dict_collisions: dict[str, set[str]] = {}
    dict_expected_by_path: dict[str, set[str]] = {}
    for path, ids in dict_paths.items():
        if len(ids) > 1:
            if is_scoped_path(path):
                dict_expected_by_path[path] = ids
            else:
                dict_collisions[path] = ids

    expected_duplicate_ids = {"rng_audit_log", "rng_trace_log", "sealed_inputs_v1", "segment_state_runs"}

    def collect_expected(id_to_paths: dict[str, set[str]]):
        expected = {}
        for id_value in sorted(expected_duplicate_ids):
            paths = sorted(id_to_paths.get(id_value, set()))
            if paths:
                expected[id_value] = paths
        return expected

    expected = {}
    expected.update(collect_expected(dict_id_paths))
    expected.update(collect_expected(reg_id_paths))

    lines = [
        "PATH COLLISIONS REPORT (ALL SEGMENTS COMBINED)",
        "=============================================",
        "",
        "REGISTRY COLLISIONS",
        "-------------------",
    ]
    if registry_collisions:
        for path, ids in sorted(registry_collisions.items()):
            lines.append(f"- {path}  [ids: {', '.join(sorted(ids))}]")
    else:
        lines.append("None")

    lines.extend(["", "DICTIONARY COLLISIONS", "---------------------"])
    if dict_collisions:
        for path, ids in sorted(dict_collisions.items()):
            lines.append(f"- {path}  [ids: {', '.join(sorted(ids))}]")
    else:
        lines.append("None")

    lines.extend(["", "EXPECTED DUPLICATES", "-------------------"])
    if registry_expected_by_path or dict_expected_by_path or expected:
        for path, ids in sorted(registry_expected_by_path.items()):
            lines.append(f"- {path}  [ids: {', '.join(sorted(ids))}]")
        for path, ids in sorted(dict_expected_by_path.items()):
            lines.append(f"- {path}  [ids: {', '.join(sorted(ids))}]")
        for id_value in sorted(expected.keys()):
            lines.append(f"- {id_value}")
            for path in expected[id_value]:
                lines.append(f"  - {path}")
    else:
        lines.append("None")

    (TMP_DIR / "paths_tree_collisions.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
