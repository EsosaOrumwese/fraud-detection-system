"""Dataset dictionary helpers for Segment 1B."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, MutableMapping

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
    """Return the canonical dictionary path for Segment 1B."""

    repo_root = _discover_repo_root()
    return (
        repo_root
        / "contracts"
        / "dataset_dictionary"
        / "l1"
        / "seg_1B"
        / "layer1.1B.yaml"
    )


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


def get_dataset_entry(
    dataset_id: str, *, dictionary: Mapping[str, object] | None = None
) -> Mapping[str, object]:
    dictionary = dictionary or load_dictionary()
    sections = (
        "datasets",
        "reference_data",
        "reference",
        "model",
        "validation",
        "logs",
    )
    for section_key in sections:
        section = dictionary.get(section_key)
        if not isinstance(section, Mapping):
            continue
        entry = section.get(dataset_id)
        if entry is not None:
            if not isinstance(entry, Mapping):
                raise err(
                    "E_DICTIONARY_RESOLUTION_FAILED",
                    f"dictionary entry '{dataset_id}' must be a mapping",
                )
            return entry
    raise err(
        "E_DICTIONARY_RESOLUTION_FAILED",
        f"dataset '{dataset_id}' not present in the Segment 1B dictionary",
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
    return _format_template(raw_path, template_args, dataset_id=dataset_id)


def resolve_dataset_path(
    dataset_id: str,
    *,
    base_path: Path,
    template_args: Mapping[str, object],
    dictionary: Mapping[str, object] | None = None,
) -> Path:
    """Resolve ``dataset_id`` to an absolute filesystem path."""

    rendered = render_dataset_path(
        dataset_id, template_args=template_args, dictionary=dictionary
    )
    return (base_path / rendered).resolve()


def _format_template(
    template: str, template_args: Mapping[str, object], *, dataset_id: str
) -> str:
    safe_args = {key: str(value) for key, value in template_args.items()}
    try:
        rendered = template.format(**safe_args)
    except KeyError as exc:
        missing = exc.args[0]
        raise err(
            "E_DICTIONARY_RESOLUTION_FAILED",
            f"dataset '{dataset_id}' requires template parameter '{missing}'",
        ) from exc

    rendered = rendered.strip().rstrip("/")
    if not rendered:
        raise err(
            "E_DICTIONARY_RESOLUTION_FAILED",
            f"dataset '{dataset_id}' resolved to an empty path",
        )

    return rendered


__all__ = [
    "default_dictionary_path",
    "load_dictionary",
    "resolve_dataset_path",
    "render_dataset_path",
    "get_dataset_entry",
]
