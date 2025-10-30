import json
from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml

from engine.layers.l1.seg_1A.s9_validation import validate as s9_validate


def _load_dictionary() -> Mapping[str, Any]:
    repo_root = s9_validate.get_repo_root()
    dictionary_path = (
        repo_root / "contracts" / "dataset_dictionary" / "l1" / "seg_1A" / "layer1.1A.yaml"
    )
    assert dictionary_path.exists(), f"dataset dictionary missing at {dictionary_path}"
    payload = yaml.safe_load(dictionary_path.read_text(encoding="utf-8")) or {}
    assert isinstance(payload, Mapping), "dataset dictionary must decode to a mapping"
    return payload


def _load_schema_document(file_name: str) -> tuple[Path, Any]:
    schema_path = s9_validate._schema_file_path(file_name)
    if not schema_path.exists():
        repo_root = s9_validate.get_repo_root()
        matches = list(repo_root.rglob(file_name))
        assert matches, f"schema file '{file_name}' not found (searched {schema_path})"
        schema_path = matches[0]
    text = schema_path.read_text(encoding="utf-8")
    if schema_path.suffix in {".json", ".schema"}:
        return schema_path, json.loads(text)
    return schema_path, yaml.safe_load(text)


@pytest.mark.parametrize("section_name", ["reference", "parameters", "model", "allocation", "crossborder", "selection", "egress"])
def test_dictionary_entries_have_schema_ids(section_name: str) -> None:
    dictionary = _load_dictionary()
    section = dictionary.get(section_name, {})
    if not isinstance(section, Mapping):
        pytest.skip(f"Section '{section_name}' is not a mapping")

    for dataset_id, entry in section.items():
        if not isinstance(entry, Mapping):
            continue
        schema_ref = entry.get("schema_ref")
        if not schema_ref or schema_ref is None:
            continue

        file_name, pointer = s9_validate._split_schema_ref(schema_ref)
        schema_path, document = _load_schema_document(file_name)
        assert isinstance(document, Mapping), f"Schema {file_name} must decode to mapping"
        root_identifier = document.get("$id") or document.get("version")
        assert isinstance(
            root_identifier, str
        ) and root_identifier, f"Schema '{file_name}' missing $id/version (referenced by {dataset_id})"
        if pointer:
            s9_validate._resolve_pointer(document, pointer)
