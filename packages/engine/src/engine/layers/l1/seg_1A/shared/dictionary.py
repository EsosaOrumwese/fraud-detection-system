"""Dataset dictionary helpers for Segment 1A."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, MutableMapping

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


def get_repo_root() -> Path:
    """Return the repository root inferred from the current module location."""

    return _discover_repo_root()


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
    for entry in _iter_entries(dictionary, dataset_id):
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


def _iter_entries(
    dictionary: Mapping[str, object],
    dataset_id: str,
) -> Iterable[Mapping[str, object]]:
    for section in dictionary.values():
        if isinstance(section, Mapping):
            entry = section.get(dataset_id)
            if entry is None:
                continue
            if not isinstance(entry, Mapping):
                raise err(
                    "E_DATASET_INVALID",
                    f"dataset '{dataset_id}' entry must be a mapping",
                )
            yield entry
            continue
        if isinstance(section, list):
            for item in section:
                if not isinstance(item, Mapping):
                    continue
                if item.get("id") == dataset_id:
                    yield item


_RNG_EVENT_DATASET_IDS: Mapping[str, str] = {
    "core": "rng_event_anchor",
    "hurdle_bernoulli": "rng_event_hurdle_bernoulli",
    "gamma_component": "rng_event_gamma_component",
    "poisson_component": "rng_event_poisson_component",
    "nb_final": "rng_event_nb_final",
    "ztp_rejection": "rng_event_ztp_rejection",
    "ztp_retry_exhausted": "rng_event_ztp_retry_exhausted",
    "ztp_final": "rng_event_ztp_final",
    "gumbel_key": "rng_event_gumbel_key",
    "residual_rank": "rng_event_residual_rank",
    "dirichlet_gamma_vector": "rng_event_dirichlet_gamma_vector",
    "sequence_finalize": "rng_event_sequence_finalize",
    "site_sequence_overflow": "rng_event_site_sequence_overflow",
}


def resolve_rng_event_path(
    stream: str,
    *,
    base_path: Path,
    seed: int,
    parameter_hash: str,
    run_id: str,
    dictionary: Mapping[str, object] | None = None,
) -> Path:
    """Resolve the RNG event path for a given stream label."""

    dataset_id = _RNG_EVENT_DATASET_IDS.get(stream, f"rng_event_{stream}")
    return resolve_dataset_path(
        dataset_id,
        base_path=base_path,
        template_args={
            "seed": seed,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )


def resolve_rng_trace_path(
    *,
    base_path: Path,
    seed: int,
    parameter_hash: str,
    run_id: str,
    dictionary: Mapping[str, object] | None = None,
) -> Path:
    """Resolve the RNG trace log path."""

    return resolve_dataset_path(
        "rng_trace_log",
        base_path=base_path,
        template_args={
            "seed": seed,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )


def resolve_rng_audit_path(
    *,
    base_path: Path,
    seed: int,
    parameter_hash: str,
    run_id: str,
    dictionary: Mapping[str, object] | None = None,
) -> Path:
    """Resolve the RNG audit log path."""

    return resolve_dataset_path(
        "rng_audit_log",
        base_path=base_path,
        template_args={
            "seed": seed,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )


__all__ = [
    "default_dictionary_path",
    "get_repo_root",
    "load_dictionary",
    "resolve_dataset_path",
    "resolve_rng_audit_path",
    "resolve_rng_event_path",
    "resolve_rng_trace_path",
]
