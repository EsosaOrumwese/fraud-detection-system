"""Scenario-runner helpers for Layer-1 Segment 1A states."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import S1RunResult
from engine.layers.l1.seg_1A.s1_hurdle.l3.catalogue import GatedStream


@dataclass(frozen=True)
class HurdleStateContext:
    """Context bundle handed to downstream states after S1 completes."""

    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    seed: int
    multi_merchant_ids: Tuple[int, ...]
    gated_streams: Tuple[GatedStream, ...]
    catalogue_path: Path

    @property
    def gated_dataset_ids(self) -> Tuple[str, ...]:
        """Return the dataset identifiers gated by the hurdle stream."""

        return tuple(stream.dataset_id for stream in self.gated_streams)

    def stream_by_dataset(self) -> Dict[str, GatedStream]:
        """Return a dictionary keyed by dataset identifier."""

        return {stream.dataset_id: stream for stream in self.gated_streams}


def build_hurdle_context(result: S1RunResult) -> HurdleStateContext:
    """Construct the downstream-facing context from an ``S1RunResult``."""

    return HurdleStateContext(
        parameter_hash=result.parameter_hash,
        manifest_fingerprint=result.manifest_fingerprint,
        run_id=result.run_id,
        seed=result.seed,
        multi_merchant_ids=result.multi_merchant_ids,
        gated_streams=result.gated_streams,
        catalogue_path=result.catalogue_path,
    )


__all__ = ["HurdleStateContext", "build_hurdle_context"]
