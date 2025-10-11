"""Utilities for publishing S4 validation artefacts."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Mapping

from ...s0_foundations.l2.output import refresh_validation_bundle_flag

logger = logging.getLogger(__name__)
_S4_BUNDLE_DIRNAME = "s4_ztp_target"


def publish_s4_validation_artifacts(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    metrics: Mapping[str, float] | None,
    validation_output_dir: Path | None,
) -> Path | None:
    """Copy S4 validation artefacts into the sealed validation bundle."""

    bundle_dir = (
        base_path.expanduser().resolve()
        / "validation_bundle"
        / f"manifest_fingerprint={manifest_fingerprint}"
    )
    if not bundle_dir.exists():
        logger.warning(
            "S4 validation bundle missing at '%s'; skipping artefact publish",
            bundle_dir,
        )
        return None

    target_dir = bundle_dir / _S4_BUNDLE_DIRNAME
    target_dir.mkdir(parents=True, exist_ok=True)

    if metrics is not None:
        payload = {
            "version": "1A.S4.metrics.v1",
            "metrics": dict(metrics),
        }
        (target_dir / "metrics.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    if validation_output_dir is not None:
        source_dir = validation_output_dir.expanduser().resolve()
        for artefact in source_dir.iterdir():
            if artefact.is_file():
                shutil.copy2(artefact, target_dir / artefact.name)

    refresh_validation_bundle_flag(bundle_dir)
    return target_dir


__all__ = ["publish_s4_validation_artifacts"]
