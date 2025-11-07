"""High-level scaffolding for Segment 2A S1."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from engine.layers.l1.seg_2A.shared.dictionary import load_dictionary, resolve_dataset_path
from engine.layers.l1.seg_2A.shared.receipt import GateReceiptSummary, load_gate_receipt

from ..l1.context import ProvisionalLookupAssets, ProvisionalLookupContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProvisionalLookupInputs:
    """User-supplied configuration for running 2A.S1."""

    data_root: Path
    seed: int
    manifest_fingerprint: str
    dictionary: Optional[Mapping[str, object]] = None
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class ProvisionalLookupResult:
    """Outcome of the provisional lookup runner."""

    seed: int
    manifest_fingerprint: str
    output_path: Path
    resumed: bool


class ProvisionalLookupRunner:
    """Resolves inputs for S1 and prepares the execution context."""

    def run(self, config: ProvisionalLookupInputs) -> ProvisionalLookupResult:
        dictionary = config.dictionary or load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().resolve()
        logger.info(
            "Segment2A S1 scaffolding invoked (seed=%s, manifest=%s)",
            config.seed,
            config.manifest_fingerprint,
        )
        receipt = load_gate_receipt(
            base_path=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        context = self._prepare_context(
            data_root=data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
            receipt=receipt,
        )
        # Processing is not yet implemented; this scaffolding simply prepares the inputs.
        raise NotImplementedError(
            "Segment 2A S1 plumbing prepared context but execution is not implemented yet",
        )

    def _prepare_context(
        self,
        *,
        data_root: Path,
        seed: int,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
        receipt: GateReceiptSummary,
    ) -> ProvisionalLookupContext:
        assets = self._resolve_assets(
            data_root=data_root,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            dictionary=dictionary,
        )
        logger.debug(
            "Resolved S1 assets (site_locations=%s, tz_world=%s)",
            assets.site_locations,
            assets.tz_world,
        )
        return ProvisionalLookupContext(
            data_root=data_root,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            receipt_path=receipt.path,
            assets=assets,
        )

    def _resolve_assets(
        self,
        *,
        data_root: Path,
        seed: int,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
    ) -> ProvisionalLookupAssets:
        template_args = {"seed": seed, "manifest_fingerprint": manifest_fingerprint}
        site_locations = resolve_dataset_path(
            "site_locations",
            base_path=data_root,
            template_args=template_args,
            dictionary=dictionary,
        )
        tz_world = resolve_dataset_path(
            "tz_world_2025a",
            base_path=data_root,
            template_args={},
            dictionary=dictionary,
        )
        tz_nudge = resolve_dataset_path(
            "tz_nudge",
            base_path=data_root,
            template_args={},
            dictionary=dictionary,
        )
        tz_overrides: Path | None
        try:
            tz_overrides = resolve_dataset_path(
                "tz_overrides",
                base_path=data_root,
                template_args={},
                dictionary=dictionary,
            )
        except Exception:
            tz_overrides = None
        return ProvisionalLookupAssets(
            site_locations=site_locations,
            tz_world=tz_world,
            tz_nudge=tz_nudge,
            tz_overrides=tz_overrides,
        )


__all__ = [
    "ProvisionalLookupInputs",
    "ProvisionalLookupResult",
    "ProvisionalLookupRunner",
]

