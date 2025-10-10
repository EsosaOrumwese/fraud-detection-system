"""Utilities for publishing S3 validation artefacts into the sealed bundle."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Mapping

from ...s0_foundations.l2.output import refresh_validation_bundle_flag

_S3_BUNDLE_DIRNAME = "s3_crossborder_universe"
logger = logging.getLogger(__name__)


def publish_s3_validation_artifacts(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    metrics: Mapping[str, float] | None,
    passed: bool,
    failed_merchants: Mapping[int, str] | None = None,
    error_message: str | None = None,
) -> Path | None:
    """Persist S3 validation metrics into the validation bundle.

    Parameters
    ----------
    base_path:
        Root directory that contains the ``validation_bundle/`` hierarchy.
    manifest_fingerprint:
        Fingerprint identifying the sealed run (directory name).
    metrics:
        Metrics emitted by ``validate_s3_outputs`` (optional).
    passed:
        Overall validation outcome.
    failed_merchants:
        Optional mapping of merchant ids to error codes/messages.
    error_message:
        Optional run-scoped error description when validation fails.

    Returns
    -------
    Optional[Path]
        The directory inside the bundle where artefacts now live, or ``None`` if
        the bundle location is unavailable.
    """

    bundle_dir = (
        base_path.expanduser().resolve()
        / "validation_bundle"
        / f"manifest_fingerprint={manifest_fingerprint}"
    )
    if not bundle_dir.exists():
        logger.warning(
            "S3 validation bundle missing at '%s'; skipping artefact publish",
            bundle_dir,
        )
        return None

    target_dir = bundle_dir / _S3_BUNDLE_DIRNAME
    target_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "version": "1A.S3.validation.v1",
        "passed": passed,
        "metrics": dict(metrics) if metrics is not None else {},
    }
    if failed_merchants:
        summary["failed_merchants"] = dict(failed_merchants)
    if error_message is not None:
        summary["error_message"] = error_message

    (target_dir / "validation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    refresh_validation_bundle_flag(bundle_dir)
    return target_dir


__all__ = ["publish_s3_validation_artifacts"]
