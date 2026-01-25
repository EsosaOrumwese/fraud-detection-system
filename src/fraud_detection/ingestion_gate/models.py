"""IG core models (minimal)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AdmissionDecision:
    decision: str
    reason_codes: list[str]
    eb_ref: dict[str, Any] | None = None
    evidence_refs: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class Receipt:
    payload: dict[str, Any]


@dataclass(frozen=True)
class QuarantineRecord:
    payload: dict[str, Any]
