"""Crossborder eligibility rule parsing and evaluation (S0.6)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Iterable, Optional

import polars as pl
import yaml

from engine.core.errors import EngineFailure


@dataclass(frozen=True)
class EligibilityRule:
    rule_id: str
    decision: str
    priority: int
    mcc_set: Optional[set[int]]
    channel_set: Optional[set[str]]
    iso_set: Optional[set[str]]

    def matches(self, mcc: int, channel_sym: str, home_iso: str) -> bool:
        if self.mcc_set is not None and mcc not in self.mcc_set:
            return False
        if self.channel_set is not None and channel_sym not in self.channel_set:
            return False
        if self.iso_set is not None and home_iso not in self.iso_set:
            return False
        return True


def _expand_mcc_values(values: Iterable[str], rule_id: str) -> Optional[set[int]]:
    if "*" in values:
        return None
    expanded: set[int] = set()
    for raw in values:
        token = str(raw)
        if token == "*":
            return None
        if "-" in token:
            parts = token.split("-", 1)
            if len(parts) != 2:
                raise EngineFailure(
                    "F3",
                    "elig_rule_bad_mcc",
                    "S0.6",
                    "1A.crossborder_eligibility",
                    {"rule_id": rule_id, "mcc": token},
                )
            start, end = parts
            if not (start.isdigit() and end.isdigit()):
                raise EngineFailure(
                    "F3",
                    "elig_rule_bad_mcc",
                    "S0.6",
                    "1A.crossborder_eligibility",
                    {"rule_id": rule_id, "mcc": token},
                )
            start_i = int(start)
            end_i = int(end)
            if start_i > end_i or start_i < 0 or end_i > 9999:
                raise EngineFailure(
                    "F3",
                    "elig_rule_bad_mcc",
                    "S0.6",
                    "1A.crossborder_eligibility",
                    {"rule_id": rule_id, "mcc": token},
                )
            expanded.update(range(start_i, end_i + 1))
        else:
            if not token.isdigit() or len(token) != 4:
                raise EngineFailure(
                    "F3",
                    "elig_rule_bad_mcc",
                    "S0.6",
                    "1A.crossborder_eligibility",
                    {"rule_id": rule_id, "mcc": token},
                )
            value = int(token)
            if value < 0 or value > 9999:
                raise EngineFailure(
                    "F3",
                    "elig_rule_bad_mcc",
                    "S0.6",
                    "1A.crossborder_eligibility",
                    {"rule_id": rule_id, "mcc": token},
                )
            expanded.add(value)
    return expanded


def _expand_channel(values: Iterable[str], rule_id: str) -> Optional[set[str]]:
    if "*" in values:
        return None
    allowed = {"CP", "CNP"}
    channels = {str(value) for value in values}
    bad = channels - allowed
    if bad:
        raise EngineFailure(
            "F3",
            "elig_rule_bad_channel",
            "S0.6",
            "1A.crossborder_eligibility",
            {"rule_id": rule_id, "channel": sorted(bad)},
        )
    return channels


def _expand_iso(
    values: Iterable[str], rule_id: str, iso_set: set[str]
) -> Optional[set[str]]:
    if "*" in values:
        return None
    expanded: set[str] = set()
    for raw in values:
        token = str(raw)
        if token == "*":
            return None
        if token not in iso_set:
            raise EngineFailure(
                "F3",
                "elig_rule_bad_iso",
                "S0.6",
                "1A.crossborder_eligibility",
                {"rule_id": rule_id, "iso": token},
            )
        expanded.add(token)
    return expanded


def load_eligibility_rules(
    path: str, iso_set: set[str]
) -> tuple[str, bool, list[EligibilityRule]]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    eligibility = payload.get("eligibility") if isinstance(payload, dict) else None
    if not isinstance(eligibility, dict):
        raise EngineFailure(
            "F3",
            "elig_rules_missing",
            "S0.6",
            "1A.crossborder_eligibility",
            {"detail": "eligibility_section_missing"},
        )
    rule_set_id = str(eligibility.get("rule_set_id") or "").strip()
    if not rule_set_id:
        raise EngineFailure(
            "F3",
            "elig_rule_set_empty",
            "S0.6",
            "1A.crossborder_eligibility",
            {"detail": "rule_set_id_missing"},
        )
    default_decision = eligibility.get("default_decision")
    if default_decision not in ("allow", "deny"):
        raise EngineFailure(
            "F3",
            "elig_default_invalid",
            "S0.6",
            "1A.crossborder_eligibility",
            {"default_decision": default_decision},
        )
    rules_raw = eligibility.get("rules")
    if not isinstance(rules_raw, list):
        raise EngineFailure(
            "F3",
            "elig_rules_missing",
            "S0.6",
            "1A.crossborder_eligibility",
            {"detail": "eligibility_rules_missing"},
        )
    seen_ids: set[str] = set()
    rules: list[EligibilityRule] = []
    for rule in rules_raw:
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("id") or "").strip()
        if not rule_id:
            raise EngineFailure(
                "F3",
                "elig_rule_id_missing",
                "S0.6",
                "1A.crossborder_eligibility",
                {"detail": "rule_id_missing"},
            )
        if rule_id in seen_ids:
            raise EngineFailure(
                "F3",
                "elig_rule_dup_id",
                "S0.6",
                "1A.crossborder_eligibility",
                {"rule_id": rule_id},
            )
        seen_ids.add(rule_id)
        priority = int(rule.get("priority", -1))
        if priority < 0 or priority > 2**31 - 1:
            raise EngineFailure(
                "F3",
                "elig_rule_bad_priority",
                "S0.6",
                "1A.crossborder_eligibility",
                {"rule_id": rule_id, "priority": priority},
            )
        decision = rule.get("decision")
        if decision not in ("allow", "deny"):
            raise EngineFailure(
                "F3",
                "elig_rule_bad_decision",
                "S0.6",
                "1A.crossborder_eligibility",
                {"rule_id": rule_id, "decision": decision},
            )
        channel_values = rule.get("channel") or []
        iso_values = rule.get("iso") or []
        mcc_values = rule.get("mcc") or []
        if not isinstance(channel_values, list):
            raise EngineFailure(
                "F3",
                "elig_rule_bad_channel",
                "S0.6",
                "1A.crossborder_eligibility",
                {"rule_id": rule_id, "channel": channel_values},
            )
        if not isinstance(iso_values, list):
            raise EngineFailure(
                "F3",
                "elig_rule_bad_iso",
                "S0.6",
                "1A.crossborder_eligibility",
                {"rule_id": rule_id, "iso": iso_values},
            )
        if not isinstance(mcc_values, list):
            raise EngineFailure(
                "F3",
                "elig_rule_bad_mcc",
                "S0.6",
                "1A.crossborder_eligibility",
                {"rule_id": rule_id, "mcc": mcc_values},
            )
        mcc_set = _expand_mcc_values(mcc_values, rule_id)
        channel_set = _expand_channel(channel_values, rule_id)
        iso_rule_set = _expand_iso(iso_values, rule_id, iso_set)
        rules.append(
            EligibilityRule(
                rule_id=rule_id,
                decision=decision,
                priority=priority,
                mcc_set=mcc_set,
                channel_set=channel_set,
                iso_set=iso_rule_set,
            )
        )
    return rule_set_id, default_decision == "allow", rules


def build_eligibility_frame(
    merchants: pl.DataFrame,
    rules: list[EligibilityRule],
    rule_set_id: str,
    default_allow: bool,
    parameter_hash: str,
    produced_by_fingerprint: Optional[str],
    logger,
) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    total = merchants.height
    progress_every = max(1, min(10_000, total // 10 if total else 1))
    start_time = time.monotonic()
    for idx, row in enumerate(
        merchants.select(
            ["merchant_id", "mcc", "channel_sym", "home_country_iso"]
        ).iter_rows(),
        start=1,
    ):
        merchant_id, mcc, channel_sym, home_iso = row
        best_deny: Optional[tuple[int, str]] = None
        best_allow: Optional[tuple[int, str]] = None
        for rule in rules:
            if not rule.matches(int(mcc), str(channel_sym), str(home_iso)):
                continue
            entry = (rule.priority, rule.rule_id)
            if rule.decision == "deny":
                if best_deny is None or entry < best_deny:
                    best_deny = entry
            else:
                if best_allow is None or entry < best_allow:
                    best_allow = entry
        if best_deny is not None:
            is_eligible = False
            reason = best_deny[1]
        elif best_allow is not None:
            is_eligible = True
            reason = best_allow[1]
        else:
            is_eligible = default_allow
            reason = "default_allow" if default_allow else "default_deny"
        record = {
            "parameter_hash": parameter_hash,
            "merchant_id": int(merchant_id),
            "is_eligible": bool(is_eligible),
            "reason": reason,
            "rule_set": rule_set_id,
        }
        if produced_by_fingerprint is not None:
            record["produced_by_fingerprint"] = produced_by_fingerprint
        rows.append(record)
        if idx % progress_every == 0 or idx == total:
            elapsed = time.monotonic() - start_time
            rate = (idx / elapsed) if elapsed > 0.0 else 0.0
            eta = ((total - idx) / rate) if rate > 0.0 else 0.0
            logger.info(
                "S0.6: evaluated eligibility %d/%d (elapsed=%.2fs, rate=%.1f/s, eta=%.2fs)",
                idx,
                total,
                elapsed,
                rate,
                eta,
            )
    schema = {
        "parameter_hash": pl.Utf8,
        "merchant_id": pl.UInt64,
        "is_eligible": pl.Boolean,
        "reason": pl.Utf8,
        "rule_set": pl.Utf8,
    }
    if produced_by_fingerprint is not None:
        schema["produced_by_fingerprint"] = pl.Utf8
    return pl.DataFrame(rows, schema=schema)
