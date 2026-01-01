"""Dataset dictionary helpers for Segment 6B (Layer-3)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Sequence

import yaml


class DictionaryError(RuntimeError):
    """Raised when the dataset dictionary cannot be resolved or decoded."""


def _discover_repo_root(anchor: Path | None = None) -> Path:
    current = anchor or Path(__file__).resolve()
    for parent in current.parents:
        if parent.name == "packages":
            return parent.parent
    raise DictionaryError("unable to locate repository root for dataset dictionary discovery")


def default_dictionary_path() -> Path:
    """Return the canonical dictionary path for Segment 6B."""

    repo_root = _discover_repo_root()
    return repo_root / "contracts" / "dataset_dictionary" / "l3" / "seg_6B" / "layer3.6B.yaml"


def repository_root() -> Path:
    """Expose the repository root for callers that need to locate reference artefacts."""

    return _discover_repo_root()


def load_dictionary(path: Path | None = None) -> Mapping[str, object] | Sequence[object]:
    """Decode the dataset dictionary into a mapping or list of entries."""

    dictionary_path = path or default_dictionary_path()
    if not dictionary_path.exists():
        raise DictionaryError(f"dataset dictionary '{dictionary_path}' missing")
    payload = yaml.safe_load(dictionary_path.read_text(encoding="utf-8"))
    if isinstance(payload, MutableMapping) or isinstance(payload, list):
        return payload
    raise DictionaryError(f"dataset dictionary '{dictionary_path}' must decode to a mapping or list")


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


def _iter_entries(payload: Mapping[str, object] | Sequence[object]) -> Iterable[Mapping[str, object]]:
    if isinstance(payload, Mapping):
        for section_key in _dictionary_sections():
            section = payload.get(section_key)
            if isinstance(section, Mapping):
                for entry in section.values():
                    if isinstance(entry, Mapping):
                        yield entry
            elif isinstance(section, Sequence) and not isinstance(section, (str, bytes)):
                for entry in section:
                    if isinstance(entry, Mapping):
                        yield entry
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for entry in payload:
            if isinstance(entry, Mapping):
                yield entry


def get_dataset_entry(
    dataset_id: str, *, dictionary: Mapping[str, object] | Sequence[object] | None = None
) -> Mapping[str, object]:
    """Return the raw dictionary entry for ``dataset_id``."""

    dictionary = dictionary or load_dictionary()
    for entry in _iter_entries(dictionary):
        if entry.get("id") == dataset_id:
            return entry
    raise DictionaryError(f"dataset '{dataset_id}' not present in the Segment 6B dictionary")


def render_dataset_path(
    dataset_id: str,
    *,
    template_args: Mapping[str, object],
    dictionary: Mapping[str, object] | Sequence[object] | None = None,
) -> str:
    """Render the path template for ``dataset_id`` without joining to a base path."""

    entry = get_dataset_entry(dataset_id, dictionary=dictionary)
    raw_path = entry.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise DictionaryError(f"dictionary entry '{dataset_id}' is missing a path template")
    raw_path = raw_path.strip()
    try:
        return raw_path.format(**template_args)
    except KeyError as exc:
        raise DictionaryError(f"missing template arg {exc} for dataset '{dataset_id}'") from exc


__all__ = [
    "DictionaryError",
    "default_dictionary_path",
    "get_dataset_entry",
    "load_dictionary",
    "render_dataset_path",
    "repository_root",
]
