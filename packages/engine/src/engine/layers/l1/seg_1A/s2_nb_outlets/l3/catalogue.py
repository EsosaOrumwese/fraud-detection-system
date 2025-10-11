"""Catalogue helpers for S2 NB outlet datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from engine.layers.l1.seg_1A.s1_hurdle.l3.catalogue import GatedStream, load_gated_streams

_S2_DATASET_IDS = {
    "rng_event_gamma_component",
    "rng_event_poisson_component",
    "rng_event_nb_final",
}


def _filter_s2_streams(streams: Sequence[GatedStream]) -> list[GatedStream]:
    return [stream for stream in streams if stream.dataset_id in _S2_DATASET_IDS]


def write_nb_catalogue(
    *,
    base_path: Path,
    parameter_hash: str,
    multi_merchant_ids: Sequence[int],
    metrics: Mapping[str, object] | None,
) -> Path:
    """Persist a presence catalogue for S2 RNG datasets."""

    try:
        streams = load_gated_streams(gated_by="rng_event_hurdle_bernoulli")
    except Exception:
        streams = ()
    filtered = _filter_s2_streams(streams)
    directory = (
        base_path
        / "parameter_scoped"
        / f"parameter_hash={parameter_hash}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    catalogue_path = directory / "s2_nb_catalogue.json"
    payload = {
        "version": "1A.S2.catalogue.v1",
        "multi_merchant_ids": sorted(int(mid) for mid in set(multi_merchant_ids)),
        "datasets": [
            {
                "dataset_id": stream.dataset_id,
                "path": stream.path,
                "predicate": stream.predicate,
                "gated_by": stream.gated_by,
                "also_requires": list(stream.also_requires),
                "owner": stream.owner,
                "section": stream.section,
            }
            for stream in filtered
        ],
        "metrics": dict(metrics) if metrics is not None else None,
    }
    catalogue_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return catalogue_path


__all__ = ["write_nb_catalogue"]
