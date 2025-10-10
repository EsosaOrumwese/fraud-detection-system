"""Gating catalogue helpers for S1 hurdle outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

from ...s0_foundations.exceptions import err
from ...shared.dictionary import default_dictionary_path, load_dictionary


@dataclass(frozen=True)
class GatedStream:
    """Represents a dataset that is presence-gated by the hurdle stream."""

    dataset_id: str
    path: str
    predicate: str
    gated_by: str
    also_requires: Tuple[str, ...]
    owner: str | None
    section: str


def load_gated_streams(
    *,
    gated_by: str,
    dictionary_path: Path | None = None,
) -> Tuple[GatedStream, ...]:
    """Discover all dataset dictionary entries gated by ``gated_by``."""

    path = dictionary_path or default_dictionary_path()
    data = load_dictionary(path)
    streams: list[GatedStream] = []
    for section_name, section in data.items():
        if not isinstance(section, dict):
            continue
        for dataset_id, dataset in section.items():
            if not isinstance(dataset, dict):
                continue
            gating = dataset.get("gating")
            if not isinstance(gating, dict):
                continue
            if gating.get("gated_by") != gated_by:
                continue
            predicate = str(gating.get("predicate", "")).strip()
            also_raw = gating.get("also_requires", [])
            if also_raw is None:
                also_raw = []
            if not isinstance(also_raw, Iterable):
                raise err(
                    "E_VALIDATION_MISMATCH",
                    f"gating.also_requires for dataset '{dataset_id}' must be iterable",
                )
            also_requires = tuple(str(item) for item in also_raw)
            streams.append(
                GatedStream(
                    dataset_id=str(dataset_id),
                    path=str(dataset.get("path", "")),
                    predicate=predicate,
                    gated_by=gated_by,
                    also_requires=also_requires,
                    owner=str(dataset.get("owner")) if dataset.get("owner") else None,
                    section=str(section_name),
                )
            )
    return tuple(streams)


def write_hurdle_catalogue(
    *,
    base_path: Path,
    parameter_hash: str,
    module: str,
    substream_label: str,
    multi_merchant_ids: Iterable[int],
    gated_streams: Iterable[GatedStream],
) -> Path:
    """Materialise a JSON catalogue describing hurdle gating outputs."""

    directory = (
        base_path
        / "parameter_scoped"
        / f"parameter_hash={parameter_hash}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    catalogue_path = directory / "s1_hurdle_catalogue.json"
    payload = {
        "version": "1A.S1.catalogue.v1",
        "module": module,
        "substream_label": substream_label,
        "multi_merchant_ids": sorted(int(mid) for mid in set(multi_merchant_ids)),
        "gated_streams": [
            {
                "dataset_id": stream.dataset_id,
                "path": stream.path,
                "predicate": stream.predicate,
                "gated_by": stream.gated_by,
                "also_requires": list(stream.also_requires),
                "owner": stream.owner,
                "section": stream.section,
            }
            for stream in gated_streams
        ],
    }
    catalogue_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return catalogue_path


__all__ = ["GatedStream", "load_gated_streams", "write_hurdle_catalogue"]
