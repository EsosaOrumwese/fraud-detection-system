"""Helpers for loading tz-specific artefacts shared across Segment 2A states."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from jsonschema import Draft202012Validator, ValidationError

from ..s0_gate.exceptions import err
from .dictionary import render_dataset_path
from .schema import load_schema

_TZ_ADJUSTMENTS_VALIDATOR = Draft202012Validator(
    load_schema("#/cache/tz_offset_adjustments")
)


@dataclass(frozen=True)
class TzAdjustmentsSummary:
    """Summary of the tz_offset_adjustments dataset for a manifest fingerprint."""

    path: Path
    manifest_fingerprint: str
    created_utc: str
    count: int
    tzids: tuple[str, ...]


def load_tz_adjustments(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object],
) -> TzAdjustmentsSummary | None:
    """Resolve and validate the tz_offset_adjustments artefact if it exists."""

    rel_path = render_dataset_path(
        "tz_offset_adjustments",
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    root_path = (base_path / rel_path).resolve()
    file_path = root_path / "tz_offset_adjustments.json"
    if not file_path.exists():
        return None

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise err(
            "E_TZ_ADJUSTMENTS_INVALID_JSON",
            f"tz_offset_adjustments at '{file_path}' is not valid JSON: {exc}",
        ) from exc

    try:
        _TZ_ADJUSTMENTS_VALIDATOR.validate(payload)
    except ValidationError as exc:  # pragma: no cover - schema edge cases
        raise err(
            "E_TZ_ADJUSTMENTS_SCHEMA",
            f"tz_offset_adjustments violates schema: {exc.message}",
        ) from exc

    if payload.get("manifest_fingerprint") != manifest_fingerprint:
        raise err(
            "E_TZ_ADJUSTMENTS_MISMATCH",
            "tz_offset_adjustments manifest fingerprint mismatch "
            f"(saw '{payload.get('manifest_fingerprint')}', expected '{manifest_fingerprint}')",
        )

    adjustments = payload.get("adjustments") or []
    tzids = _collect_adjusted_tzids(adjustments)

    return TzAdjustmentsSummary(
        path=file_path,
        manifest_fingerprint=manifest_fingerprint,
        created_utc=str(payload.get("created_utc")),
        count=int(payload.get("count", 0)),
        tzids=tzids,
    )


def _collect_adjusted_tzids(adjustments: Sequence[object]) -> tuple[str, ...]:
    tzids: set[str] = set()
    for item in adjustments:
        if not isinstance(item, Mapping):
            continue
        tzid = item.get("tzid")
        if isinstance(tzid, str) and tzid:
            tzids.add(tzid)
    return tuple(sorted(tzids))


__all__ = ["TzAdjustmentsSummary", "load_tz_adjustments"]

