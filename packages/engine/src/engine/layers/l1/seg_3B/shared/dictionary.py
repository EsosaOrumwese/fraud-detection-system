"""Dataset dictionary helpers for Segment 3B."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, MutableMapping

import yaml

from ..s0_gate.exceptions import err


def _discover_repo_root(anchor: Path | None = None) -> Path:
    current = anchor or Path(__file__).resolve()
    for parent in current.parents:
        if parent.name == "packages":
            return parent.parent
    raise err(
        "E_DICTIONARY_RESOLUTION_FAILED",
        "unable to locate repository root for dataset dictionary discovery",
    )


def default_dictionary_path() -> Path:
    """Return the canonical dictionary path for Segment 3B."""

    repo_root = _discover_repo_root()
    return (
        repo_root
        / "contracts"
        / "dataset_dictionary"
        / "l1"
        / "seg_3B"
        / "layer1.3B.yaml"
    )


def repository_root() -> Path:
    """Expose the repository root for callers that need to locate reference artefacts."""

    return _discover_repo_root()


def load_dictionary(path: Path | None = None) -> Mapping[str, object]:
    """Decode the dataset dictionary into a mapping."""

    dictionary_path = path or default_dictionary_path()
    if not dictionary_path.exists():
        raise err(
            "E_DICTIONARY_RESOLUTION_FAILED",
            f"dataset dictionary '{dictionary_path}' missing",
        )
    payload = yaml.safe_load(dictionary_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, MutableMapping):
        raise err(
            "E_DICTIONARY_RESOLUTION_FAILED",
            f"dataset dictionary '{dictionary_path}' must decode to a mapping",
        )
    return payload


def _dictionary_sections() -> tuple[str, ...]:
    return (
        "datasets",
        "reference_data",
        "policies",
        "artefacts",
        "validation",
        "reference",
        "model",
        "logs",
        "reports",
    )


def get_dataset_entry(
    dataset_id: str, *, dictionary: Mapping[str, object] | None = None
) -> Mapping[str, object]:
    """Return the raw dictionary entry for ``dataset_id``."""

    dictionary = dictionary or load_dictionary()
    for section_key in _dictionary_sections():
        section = dictionary.get(section_key)
        if isinstance(section, Mapping):
            entry = section.get(dataset_id)
            if entry is not None:
                if not isinstance(entry, Mapping):
                    raise err(
                        "E_DICTIONARY_RESOLUTION_FAILED",
                        f"dictionary entry '{dataset_id}' must be a mapping",
                    )
                return entry
        elif isinstance(section, Iterable):
            for item in section:
                if not isinstance(item, Mapping):
                    continue
                if item.get("id") == dataset_id:
                    return item
    raise err(
        "E_DICTIONARY_RESOLUTION_FAILED",
        f"dataset '{dataset_id}' not present in the Segment 3B dictionary",
    )


def render_dataset_path(
    dataset_id: str,
    *,
    template_args: Mapping[str, object],
    dictionary: Mapping[str, object] | None = None,
) -> str:
    """Render the path template for ``dataset_id`` without joining to a base path."""

    entry = get_dataset_entry(dataset_id, dictionary=dictionary)
    raw_path = entry.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise err(
            "E_DICTIONARY_RESOLUTION_FAILED",
            f"dictionary entry '{dataset_id}' is missing a path template",
        )
    try:
        return raw_path.format(**template_args)
    except KeyError as exc:
        raise err(
            "E_DICTIONARY_RESOLUTION_FAILED",
            f"missing template arg {exc} for dataset '{dataset_id}'",
        ) from exc


__all__ = [
    "default_dictionary_path",
    "get_dataset_entry",
    "load_dictionary",
    "render_dataset_path",
    "repository_root",
]
