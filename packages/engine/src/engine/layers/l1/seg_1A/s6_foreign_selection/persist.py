"""Persistence utilities for S6 foreign-set selection outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from .types import CandidateSelection
from ..shared.passed_flag import format_passed_flag

__all__ = [
    "write_membership",
    "write_receipt",
]


def write_membership(
    *,
    destination: Path,
    seed: int,
    parameter_hash: str,
    selections: Iterable[CandidateSelection],
) -> Path:
    """Persist the optional membership surface."""

    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    records = [
        {
            "seed": int(seed),
            "parameter_hash": parameter_hash,
            "merchant_id": selection.merchant_id,
            "country_iso": selection.country_iso,
        }
        for selection in selections
        if selection.selected
    ]

    frame = pd.DataFrame.from_records(
        records,
        columns=["seed", "parameter_hash", "merchant_id", "country_iso"],
    )
    if not frame.empty:
        frame = frame.sort_values(["merchant_id", "country_iso"]).reset_index(drop=True)
    frame.to_parquet(destination, index=False)
    return destination


def write_receipt(
    *,
    destination: Path,
    payload: dict,
) -> Path:
    """Write S6_VALIDATION.json + _passed.flag."""

    destination = destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)

    receipt_path = destination / "S6_VALIDATION.json"
    receipt_text = json.dumps(payload, indent=2, sort_keys=True)
    receipt_path.write_text(receipt_text, encoding="utf-8")

    digest = hashlib.sha256(receipt_text.encode("utf-8")).hexdigest()
    flag_path = destination / "_passed.flag"
    flag_path.write_text(format_passed_flag(digest), encoding="ascii")
    return receipt_path
