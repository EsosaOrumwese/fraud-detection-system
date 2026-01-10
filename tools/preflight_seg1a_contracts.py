"""Preflight checks for Segment 1A contracts and dataset IDs."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Iterable

import yaml


_DATASET_ID_PATTERN = re.compile(r"^[a-z0-9_.]+$")
_AST_DATASET_NAME_HINTS = {
    "AUDIT_LOG_ID",
    "DATASET",
    "EVENT_FAMILY",
    "RNG_EVENT_DATASETS",
    "S6_RECEIPT_DATASET_ID",
    "TRACE_LOG_ID",
    "VALIDATION_DATASET_ID",
}

_OPTIONAL_DATASET_IDS = {
    "validation_bundle",
}


def _repo_root() -> Path:
    anchor = Path(__file__).resolve()
    for parent in anchor.parents:
        if (parent / "packages").exists() and (parent / "makefile").exists():
            return parent
    return Path.cwd().resolve()


def _dictionary_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "contracts"
        / "dataset_dictionary"
        / "l1"
        / "seg_1A"
        / "layer1.1A.yaml"
    )


def _load_dictionary(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise SystemExit(f"Dictionary must decode to a mapping: {path}")
    return payload


def _iter_entries(dictionary: dict) -> Iterable[tuple[str, dict]]:
    for section in dictionary.values():
        if isinstance(section, dict):
            for key, entry in section.items():
                if isinstance(entry, dict):
                    yield str(key), entry
        elif isinstance(section, list):
            for entry in section:
                if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                    yield entry["id"], entry


def _resolve_schema_file(repo_root: Path, file_name: str) -> Path | None:
    candidates = (
        repo_root / "contracts" / "schemas" / "layer1" / file_name,
        repo_root / "contracts" / "schemas" / file_name,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _resolve_pointer(document: object, pointer: str) -> object:
    if pointer in ("", "#"):
        return document
    if pointer.startswith("#/"):
        pointer = pointer[2:]
    elif pointer.startswith("#"):
        pointer = pointer[1:]
    current = document
    for token in pointer.split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        else:
            raise KeyError(token)
    return current


def _validate_schema_ref(repo_root: Path, schema_ref: str, dataset_id: str) -> list[str]:
    issues: list[str] = []
    if "#" in schema_ref:
        file_name, pointer = schema_ref.split("#", 1)
        pointer = f"#{pointer}"
    else:
        file_name, pointer = schema_ref, ""

    schema_path = _resolve_schema_file(repo_root, file_name)
    if schema_path is None:
        issues.append(f"{dataset_id}: schema file missing for {schema_ref}")
        return issues

    if not pointer:
        return issues

    try:
        payload = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # pragma: no cover - indicates corrupted schema file
        issues.append(f"{dataset_id}: schema file unreadable {schema_path}: {exc}")
        return issues

    try:
        _resolve_pointer(payload, pointer)
    except KeyError as exc:
        issues.append(f"{dataset_id}: schema_ref pointer missing {schema_ref} ({exc})")
    return issues


def _extract_strings(node: ast.AST) -> Iterable[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        for elt in node.elts:
            yield from _extract_strings(elt)
    elif isinstance(node, ast.Dict):
        for value in node.values:
            yield from _extract_strings(value)


def _name_hints(name: str) -> bool:
    if name in _AST_DATASET_NAME_HINTS:
        return True
    if "DATASET" in name or "EVENT_FAMILY" in name:
        return True
    return False


def _collect_dataset_ids(seg_root: Path) -> set[str]:
    dataset_ids: set[str] = set()
    for path in seg_root.rglob("*.py"):
        if path.name.startswith("__"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                func_name = None
                if isinstance(func, ast.Name):
                    func_name = func.id
                elif isinstance(func, ast.Attribute):
                    func_name = func.attr
                if func_name == "resolve_dataset_path" and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        dataset_ids.add(arg.value)
                for keyword in node.keywords:
                    if keyword.arg == "dataset_id" and isinstance(keyword.value, ast.Constant):
                        if isinstance(keyword.value.value, str):
                            dataset_ids.add(keyword.value.value)
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                    value = node.value
                else:
                    targets = [node.target]
                    value = node.value
                for target in targets:
                    if isinstance(target, ast.Name) and _name_hints(target.id):
                        for string_value in _extract_strings(value):
                            dataset_ids.add(string_value)

    filtered = {
        dataset_id
        for dataset_id in dataset_ids
        if _DATASET_ID_PATTERN.match(dataset_id)
    }
    return filtered


def main() -> int:
    repo_root = _repo_root()
    dictionary_path = _dictionary_path(repo_root)
    if not dictionary_path.exists():
        print(f"Missing dataset dictionary: {dictionary_path}", file=sys.stderr)
        return 1

    dictionary = _load_dictionary(dictionary_path)
    entries = list(_iter_entries(dictionary))
    dictionary_ids = {dataset_id for dataset_id, _ in entries}

    duplicates = {dataset_id for dataset_id in dictionary_ids if sum(1 for did, _ in entries if did == dataset_id) > 1}
    if duplicates:
        print("Duplicate dataset IDs in dictionary:", file=sys.stderr)
        for dataset_id in sorted(duplicates):
            print(f" - {dataset_id}", file=sys.stderr)
        return 1

    schema_issues: list[str] = []
    for dataset_id, entry in entries:
        schema_ref = entry.get("schema_ref")
        if not isinstance(schema_ref, str) or not schema_ref.strip():
            schema_issues.append(f"{dataset_id}: missing schema_ref")
            continue
        schema_issues.extend(_validate_schema_ref(repo_root, schema_ref.strip(), dataset_id))

    if schema_issues:
        print("Schema reference issues:", file=sys.stderr)
        for issue in schema_issues:
            print(f" - {issue}", file=sys.stderr)
        return 1

    seg_root = repo_root / "packages" / "engine" / "src" / "engine" / "layers" / "l1" / "seg_1A"
    dataset_ids = _collect_dataset_ids(seg_root)
    missing = sorted(dataset_ids - dictionary_ids - _OPTIONAL_DATASET_IDS)
    if missing:
        print("Dataset IDs referenced by code but missing from dictionary:", file=sys.stderr)
        for dataset_id in missing:
            print(f" - {dataset_id}", file=sys.stderr)
        return 1

    print("Segment 1A contracts preflight: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
