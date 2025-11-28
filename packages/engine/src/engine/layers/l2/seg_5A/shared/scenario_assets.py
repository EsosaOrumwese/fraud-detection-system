"""Helpers for staging scenario artefacts prior to sealing."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


def ensure_scenario_calendar(
    *,
    repo_root: Path,
    run_base_path: Path,
    manifest_fingerprint: str,
    scenario_id: str,
) -> Path:
    """Ensure the scenario calendar for (manifest, scenario) exists under the run tree."""

    target = (
        run_base_path
        / "data"
        / "layer2"
        / "5A"
        / "scenario"
        / "calendar"
        / f"fingerprint={manifest_fingerprint}"
        / f"scenario={scenario_id}"
        / "scenario_calendar_5A.parquet"
    )
    if target.exists():
        return target

    candidates = _calendar_template_candidates(
        repo_root=repo_root,
        manifest_fingerprint=manifest_fingerprint,
        scenario_id=scenario_id,
    )
    source = _select_existing(candidates)
    if source is None:
        raise FileNotFoundError(
            f"No scenario calendar template available for scenario '{scenario_id}' "
            f"(looked in {len(candidates)} locations)"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    logger.info(
        "Segment5A: staged scenario calendar from %s -> %s",
        source.relative_to(repo_root),
        target,
    )
    return target


def _calendar_template_candidates(
    *,
    repo_root: Path,
    manifest_fingerprint: str,
    scenario_id: str,
) -> list[Path]:
    base = repo_root / "config" / "layer2" / "5A" / "scenario" / "calendar"
    return [
        base / f"fingerprint={manifest_fingerprint}" / f"scenario={scenario_id}" / "scenario_calendar_5A.parquet",
        base / f"fingerprint=baseline" / f"scenario={scenario_id}" / "scenario_calendar_5A.parquet",
        base / "fingerprint=baseline" / "scenario=baseline" / "scenario_calendar_5A.parquet",
    ]


def _select_existing(candidates: Iterable[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


__all__ = ["ensure_scenario_calendar"]
