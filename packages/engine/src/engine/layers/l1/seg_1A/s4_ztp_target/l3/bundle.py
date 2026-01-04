"""Utilities for publishing S4 validation artefacts."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Mapping

from ...s0_foundations.l2.output import refresh_validation_bundle_flag
from ...shared.dictionary import load_dictionary, resolve_dataset_path

logger = logging.getLogger(__name__)
_S4_BUNDLE_DIRNAME = "s4_ztp_target"


def _resolve_validation_bundle_dir(
    *,
    base_path: Path,
    manifest_fingerprint: str,
) -> Path | None:
    dictionary = load_dictionary()
    candidates: list[Path] = []
    for dataset_id in ("validation_bundle_1A", "validation_bundle"):
        try:
            resolved = resolve_dataset_path(
                dataset_id,
                base_path=base_path.expanduser().resolve(),
                template_args={"manifest_fingerprint": manifest_fingerprint},
                dictionary=dictionary,
            )
        except Exception:
            continue
        candidates.append(resolved)
        if resolved.exists():
            return resolved

    fallback = (
        base_path.expanduser()
        .resolve()
        / "data"
        / "layer1"
        / "1A"
        / "validation"
        / f"fingerprint={manifest_fingerprint}"
    )
    candidates.append(fallback)
    if fallback.exists():
        logger.warning(
            "S4 validation bundle resolved via fallback '%s'",
            fallback,
        )
        return fallback

    logger.warning(
        "S4 validation bundle missing; checked %s",
        ", ".join(str(path) for path in candidates),
    )
    return None


def publish_s4_validation_artifacts(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    metrics: Mapping[str, float] | None,
    validation_output_dir: Path | None,
) -> Path | None:
    """Copy S4 validation artefacts into the sealed validation bundle."""

    bundle_dir = _resolve_validation_bundle_dir(
        base_path=base_path,
        manifest_fingerprint=manifest_fingerprint,
    )
    if bundle_dir is None:
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
