"""Dataset dictionary helpers for Segment 1A."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, MutableMapping

import yaml

from ..s0_foundations.exceptions import err


def _discover_repo_root(current: Path | None = None) -> Path:
    """Locate the repository root by walking up from ``current`` (defaults to file path)."""
    anchor = current or Path(__file__).resolve()
    for parent in anchor.parents:
        if parent.name == "packages":
            return parent.parent
    raise err(
        "E_DATASET_NOT_FOUND",
        "unable to locate repository root for dataset dictionary discovery",
    )


def default_dictionary_path() -> Path:
    """Return the default dataset dictionary path for Segment 1A."""
    repo_root = _discover_repo_root()
    return (
        repo_root
        / "contracts"
        / "dataset_dictionary"
        / "l1"
        / "seg_1A"
        / "layer1.1A.yaml"
    )


def load_dictionary(path: Path | None = None) -> Mapping[str, object]:
    """Load the dataset dictionary from YAML and assert the root node is a mapping."""
    dictionary_path = path or default_dictionary_path()
    if not dictionary_path.exists():
        raise err("E_DATASET_NOT_FOUND", f"dataset dictionary '{dictionary_path}' missing")
    payload = yaml.safe_load(dictionary_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, MutableMapping):
        raise err(
            "E_DATASET_NOT_FOUND",
            f"dataset dictionary '{dictionary_path}' must decode to a mapping",
        )
    # `yaml.safe_load` returns MutableMapping, but we expose it as Mapping for callers.
    return payload


def resolve_dataset_path(
    dataset_id: str,
    *,
    base_path: Path,
    template_args: Mapping[str, object],
    dictionary: Mapping[str, object] | None = None,
) -> Path:
    """Resolve the absolute path for ``dataset_id`` using the dataset dictionary.

    Parameters
    ----------
    dataset_id:
        Identifier of the dataset in the dictionary (e.g., ``s3_candidate_set``).
    base_path:
        Base directory under which all materialised datasets are written (the CLI
        ``--output-dir`` value).
    template_args:
        Mapping of template placeholders to render in the path string (for example
        ``parameter_hash`` or ``manifest_fingerprint``).
    dictionary:
        Optional pre-loaded dictionary; when omitted the default dictionary is used.

    Returns
    -------
    Path
        Absolute filesystem path where the dataset should be materialised.
    """

    dictionary = dictionary or load_dictionary()
    for section in dictionary.values():
        if not isinstance(section, Mapping):
            continue
        entry = section.get(dataset_id)
        if entry is None:
            continue
        if not isinstance(entry, Mapping):
            raise err(
                "E_DATASET_INVALID",
                f"dataset '{dataset_id}' entry must be a mapping",
            )
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise err(
                "E_DATASET_INVALID",
                f"dataset '{dataset_id}' is missing a valid path template",
            )
        formatted = _format_template(raw_path, template_args, dataset_id=dataset_id)
        return (base_path / formatted).resolve()

    raise err("E_DATASET_NOT_FOUND", f"dataset '{dataset_id}' not found in dictionary")


def _format_template(
    template: str,
    template_args: Mapping[str, object],
    *,
    dataset_id: str,
) -> Path:
    """Render ``template`` with ``template_args`` and normalise shard placeholders."""
    safe_args = {key: str(value) for key, value in template_args.items()}
    try:
        rendered = template.format(**safe_args)
    except KeyError as exc:
        missing = exc.args[0]
        raise err(
            "E_DATASET_TEMPLATE",
            f"dataset '{dataset_id}' requires template parameter '{missing}'",
        ) from exc

    rendered = rendered.strip()
    if not rendered:
        raise err(
            "E_DATASET_TEMPLATE",
            f"dataset '{dataset_id}' produced an empty path after formatting",
        )

    # Drop trailing slash when the dictionary encodes directories.
    rendered = rendered.rstrip("/")
    path = Path(rendered)

    # Replace shard globbing (`part-*.parquet`) with a deterministic filename so
    # writers can emit a single shard without guessing the convention.
    if "*" in path.name:
        path = path.with_name(path.name.replace("*", "00000"))

    return path


__all__ = ["default_dictionary_path", "load_dictionary", "resolve_dataset_path"]
