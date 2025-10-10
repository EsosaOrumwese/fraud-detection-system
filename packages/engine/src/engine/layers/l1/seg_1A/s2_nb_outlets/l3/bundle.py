"""Utilities for publishing S2 validation artefacts into the bundle."""

from __future__ import annotations

import json
import shutil
import logging
from pathlib import Path
from typing import Mapping

from ...s0_foundations.l2.output import refresh_validation_bundle_flag

_S2_BUNDLE_DIRNAME = "s2_nb_outlets"
logger = logging.getLogger(__name__)


def publish_s2_validation_artifacts(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    metrics: Mapping[str, float] | None,
    validation_output_dir: Path | None,
) -> Path | None:
    """Copy S2 validation artefacts into the sealed validation bundle.

    Parameters
    ----------
    base_path:
        Root directory containing the `validation_bundle/` tree.
    manifest_fingerprint:
        Fingerprint identifying the sealed run (directory name under the bundle).
    metrics:
        Corridor metrics produced by ``validate_nb_run``. May be ``None`` if
        validation was skipped.
    validation_output_dir:
        Directory where the validator persisted artefacts (metrics.csv,
        cusum_trace.csv). May be ``None``.

    Returns
    -------
    Optional[Path]
        Directory inside the validation bundle where the artefacts now live.
        Returns ``None`` if the bundle directory is unavailable.
    """

    bundle_dir = (
        base_path.expanduser().resolve()
        / "validation_bundle"
        / f"manifest_fingerprint={manifest_fingerprint}"
    )
    if not bundle_dir.exists():
        logger.warning(
            "S2 validation bundle missing at '%s'; skipping artefact publish",
            bundle_dir,
        )
        return None

    target_dir = bundle_dir / _S2_BUNDLE_DIRNAME
    target_dir.mkdir(parents=True, exist_ok=True)

    if metrics is not None:
        payload = {
            "version": "1A.S2.metrics.v1",
            "metrics": dict(metrics),
        }
        (target_dir / "metrics.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    if validation_output_dir is not None:
        validation_dir = validation_output_dir.expanduser().resolve()
        for filename in ("metrics.csv", "cusum_trace.csv"):
            source = validation_dir / filename
            if source.exists():
                shutil.copy2(source, target_dir / filename)

    refresh_validation_bundle_flag(bundle_dir)
    return target_dir


__all__ = ["publish_s2_validation_artifacts"]
