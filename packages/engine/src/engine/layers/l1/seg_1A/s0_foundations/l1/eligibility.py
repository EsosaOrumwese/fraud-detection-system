"""Cross-border eligibility evaluation (S0.6)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional, Sequence, Set

import polars as pl

from ..exceptions import err
from .context import RunContext

_ALLOWED_CHANNELS = {"CP", "CNP"}


@dataclass(frozen=True)
class EligibilityRule:
    rule_id: str
    decision: str
    priority: int
    mcc: Set[int]
    channel: Set[str]
    iso: Set[str]

    def matches(self, *, mcc: int, channel: str, iso: str) -> bool:
        return mcc in self.mcc and channel in self.channel and iso in self.iso


@dataclass(frozen=True)
class CrossborderEligibility:
    rule_set_id: str
    default_decision: str
    rules_deny: Sequence[EligibilityRule]
    rules_allow: Sequence[EligibilityRule]


def _expand_mcc(entry: str) -> Sequence[int]:
    if entry == "*":
        return range(0, 10000)
    if "-" in entry:
        start_str, end_str = entry.split("-", 1)
        start = int(start_str)
        end = int(end_str)
        if not (0 <= start <= end <= 9999):
            raise err("E_ELIG_RULE_BAD_MCC", f"range '{entry}' invalid")
        return range(start, end + 1)
    code = int(entry)
    if not (0 <= code <= 9999):
        raise err("E_ELIG_RULE_BAD_MCC", f"code '{entry}' invalid")
    return (code,)


def _expand_channels(values: Sequence[str]) -> Set[str]:
    if len(values) == 1 and values[0] == "*":
        return set(_ALLOWED_CHANNELS)
    expanded = {str(v) for v in values}
    if not expanded <= _ALLOWED_CHANNELS:
        unexpected = sorted(expanded - _ALLOWED_CHANNELS)
        raise err("E_ELIG_RULE_BAD_CHANNEL", f"channels {unexpected} invalid")
    return expanded


def _expand_iso(values: Sequence[str], iso_set: Set[str]) -> Set[str]:
    if len(values) == 1 and values[0] == "*":
        return set(iso_set)
    expanded: Set[str] = set()
    for value in values:
        if len(value) != 2 or not value.isascii():
            raise err("E_ELIG_RULE_BAD_ISO", f"ISO '{value}' invalid")
        upper = value.upper()
        if upper not in iso_set:
            raise err("E_ELIG_RULE_BAD_ISO", f"ISO '{upper}' not in run set")
        expanded.add(upper)
    return expanded


def _build_rule(raw: Mapping[str, object], iso_set: Set[str]) -> EligibilityRule:
    rule_id = str(raw.get("id"))
    if not rule_id:
        raise err("E_ELIG_RULE_ID_EMPTY", "rule id missing")
    decision = str(raw.get("decision"))
    if decision not in {"allow", "deny"}:
        raise err("E_ELIG_RULE_DECISION", f"rule {rule_id} has invalid decision '{decision}'")
    priority = int(raw.get("priority", 0))
    if not (0 <= priority < 2 ** 31):
        raise err("E_ELIG_RULE_PRIORITY", f"rule {rule_id} priority {priority} invalid")
    mcc_raw = raw.get("mcc", ["*"])
    if not isinstance(mcc_raw, Sequence):
        raise err("E_ELIG_RULE_BAD_MCC", f"rule {rule_id} mcc must be list or '*'")
    channels_raw = raw.get("channel", ["*"])
    if not isinstance(channels_raw, Sequence):
        raise err("E_ELIG_RULE_BAD_CHANNEL", f"rule {rule_id} channel must be list or '*'")
    iso_raw = raw.get("iso", ["*"])
    if not isinstance(iso_raw, Sequence):
        raise err("E_ELIG_RULE_BAD_ISO", f"rule {rule_id} iso must be list or '*'")

    mcc_set: Set[int] = set()
    for entry in mcc_raw:
        for code in _expand_mcc(str(entry)):
            mcc_set.add(int(code))
    channel_set = _expand_channels([str(c) for c in channels_raw])
    iso_set_expanded = _expand_iso([str(i) for i in iso_raw], iso_set)

    return EligibilityRule(
        rule_id=rule_id,
        decision=decision,
        priority=priority,
        mcc=mcc_set,
        channel=channel_set,
        iso=iso_set_expanded,
    )


def load_crossborder_eligibility(data: Mapping[str, object], *, iso_set: Set[str]) -> CrossborderEligibility:
    eligibility = data.get("eligibility")
    if not isinstance(eligibility, Mapping):
        raise err("E_ELIG_SCHEMA", "eligibility section missing")
    rule_set_id = str(eligibility.get("rule_set_id"))
    if not rule_set_id:
        raise err("E_ELIG_RULESET_ID_EMPTY", "rule_set_id missing")
    default_decision = str(eligibility.get("default_decision"))
    if default_decision not in {"allow", "deny"}:
        raise err("E_ELIG_DEFAULT_INVALID", "default_decision must be 'allow' or 'deny'")
    rules_raw = eligibility.get("rules", [])
    if not isinstance(rules_raw, Sequence):
        raise err("E_ELIG_SCHEMA", "rules must be a sequence")
    seen_ids: Set[str] = set()
    allow_rules: List[EligibilityRule] = []
    deny_rules: List[EligibilityRule] = []
    for raw_rule in rules_raw:
        if not isinstance(raw_rule, Mapping):
            raise err("E_ELIG_SCHEMA", "rule entry must be mapping")
        rule = _build_rule(raw_rule, iso_set)
        if rule.rule_id in seen_ids:
            raise err("E_ELIG_RULE_DUP_ID", f"duplicate rule id '{rule.rule_id}'")
        seen_ids.add(rule.rule_id)
        if rule.decision == "deny":
            deny_rules.append(rule)
        else:
            allow_rules.append(rule)

    def _sort_key(rule: EligibilityRule) -> tuple:
        return (rule.priority, rule.rule_id)

    deny_rules.sort(key=_sort_key)
    allow_rules.sort(key=_sort_key)

    return CrossborderEligibility(
        rule_set_id=rule_set_id,
        default_decision=default_decision,
        rules_deny=tuple(deny_rules),
        rules_allow=tuple(allow_rules),
    )


def evaluate_eligibility(
    context: RunContext,
    *,
    bundle: CrossborderEligibility,
    parameter_hash: str,
    produced_by_fingerprint: Optional[str] = None,
) -> pl.DataFrame:
    rows: List[dict] = []
    for row in context.merchants.merchants.iter_rows(named=True):
        merchant_id = int(row["merchant_id"])
        mcc = int(row["mcc"])
        channel = str(row["channel_sym"])
        iso = str(row["home_country_iso"])
        if channel not in _ALLOWED_CHANNELS:
            raise err("E_ELIG_MISSING_MERCHANT", f"merchant {merchant_id} has invalid channel '{channel}'")

        winner_id: Optional[str] = None
        decision = bundle.default_decision

        for rule in bundle.rules_deny:
            if rule.matches(mcc=mcc, channel=channel, iso=iso):
                winner_id = rule.rule_id
                decision = "deny"
                break

        if winner_id is None:
            for rule in bundle.rules_allow:
                if rule.matches(mcc=mcc, channel=channel, iso=iso):
                    winner_id = rule.rule_id
                    decision = "allow"
                    break

        if winner_id is None:
            winner_id = "default_allow" if decision == "allow" else "default_deny"

        row_data = {
            "parameter_hash": parameter_hash,
            "merchant_id": merchant_id,
            "is_eligible": decision == "allow",
            "reason": winner_id,
            "rule_set": bundle.rule_set_id,
        }
        if produced_by_fingerprint is not None:
            row_data["produced_by_fingerprint"] = produced_by_fingerprint
        rows.append(row_data)

    schema = {
        "parameter_hash": pl.String,
        "merchant_id": pl.Int64,
        "is_eligible": pl.Boolean,
        "reason": pl.String,
        "rule_set": pl.String,
    }
    if produced_by_fingerprint is not None:
        schema["produced_by_fingerprint"] = pl.String

    return pl.DataFrame(rows, schema=schema)


__all__ = [
    "CrossborderEligibility",
    "load_crossborder_eligibility",
    "evaluate_eligibility",
]
