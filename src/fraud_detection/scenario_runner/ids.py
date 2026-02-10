"""Deterministic identifier helpers for Scenario Runner."""

from __future__ import annotations

import hashlib


def _hex32_from_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def run_id_from_equivalence_key(run_equivalence_key: str) -> str:
    return _hex32_from_text(f"sr_run|{run_equivalence_key}")


def attempt_id_for(run_id: str, attempt_no: int) -> str:
    return _hex32_from_text(f"sr_attempt|{run_id}|{attempt_no}")


def scenario_set_to_id(scenario_set: list[str]) -> str:
    joined = "|".join(sorted(set(scenario_set)))
    return f"scnset_{hashlib.sha256(joined.encode('utf-8')).hexdigest()[:16]}"


def hash_payload(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
