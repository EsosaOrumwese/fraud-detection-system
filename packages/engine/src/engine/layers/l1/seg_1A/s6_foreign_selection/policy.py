"""Policy parsing and validation for S6 foreign-set selection.

The implementation mirrors the binding requirements captured in
docs/model_spec/data-engine/specs/state-flow/1A/state.1A.s6.expanded.md §4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, MutableMapping

import yaml

__all__ = [
    "PolicyValidationError",
    "SelectionOverrides",
    "SelectionPolicy",
    "load_policy",
]

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO4217_RE = re.compile(r"^[A-Z]{3}$")
_ZERO_WEIGHT_RULES = {"exclude", "include"}


class PolicyValidationError(ValueError):
    """Raised when the governed S6 selection policy fails validation."""


@dataclass(frozen=True)
class SelectionOverrides:
    """Effective policy after applying defaults + overrides for a currency."""

    emit_membership_dataset: bool
    max_candidates_cap: int
    zero_weight_rule: str


@dataclass(frozen=True)
class SelectionPolicy:
    """Container for the resolved S6 policy (global + overrides)."""

    policy_semver: str
    policy_version: str
    emit_membership_dataset: bool
    log_all_candidates: bool
    max_candidates_cap: int
    zero_weight_rule: str
    dp_score_print: int | None
    per_currency: Mapping[str, SelectionOverrides]

    def resolve_for_currency(self, currency: str) -> SelectionOverrides:
        """Return the effective overrides for ``currency`` (ISO-4217)."""

        override = self.per_currency.get(currency.upper())
        if override is not None:
            return override
        return SelectionOverrides(
            emit_membership_dataset=self.emit_membership_dataset,
            max_candidates_cap=self.max_candidates_cap,
            zero_weight_rule=self.zero_weight_rule,
        )


def load_policy(path: str | Path) -> SelectionPolicy:
    """Load and validate the governed S6 selection policy YAML."""

    policy_path = Path(path).expanduser().resolve()
    try:
        payload = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyValidationError(f"policy file not found: {policy_path}") from exc
    except yaml.YAMLError as exc:
        raise PolicyValidationError(f"failed to parse policy YAML: {exc}") from exc

    mapping = _expect_mapping(payload, "policy")
    allowed_keys = {"policy_semver", "policy_version", "defaults", "per_currency", "notes"}
    unknown = set(mapping) - allowed_keys
    missing = {"policy_semver", "policy_version", "defaults", "per_currency"} - set(mapping)
    if unknown:
        raise PolicyValidationError(f"unknown top-level keys: {sorted(unknown)}")
    if missing:
        raise PolicyValidationError(f"missing required keys: {sorted(missing)}")

    policy_semver = _expect_string(mapping["policy_semver"], "policy_semver")
    if not _SEMVER_RE.fullmatch(policy_semver):
        raise PolicyValidationError(
            f"policy_semver must match MAJOR.MINOR.PATCH, got '{policy_semver}'"
        )
    policy_version = _expect_string(mapping["policy_version"], "policy_version")
    if not _DATE_RE.fullmatch(policy_version):
        raise PolicyValidationError(
            f"policy_version must match YYYY-MM-DD, got '{policy_version}'"
        )

    defaults = _parse_defaults(mapping["defaults"])
    per_currency = _parse_per_currency(mapping["per_currency"], defaults)

    return SelectionPolicy(
        policy_semver=policy_semver,
        policy_version=policy_version,
        emit_membership_dataset=defaults.emit_membership_dataset,
        log_all_candidates=defaults.log_all_candidates,
        max_candidates_cap=defaults.max_candidates_cap,
        zero_weight_rule=defaults.zero_weight_rule,
        dp_score_print=defaults.dp_score_print,
        per_currency=per_currency,
    )


@dataclass(frozen=True)
class _DefaultPolicy:
    emit_membership_dataset: bool
    log_all_candidates: bool
    max_candidates_cap: int
    zero_weight_rule: str
    dp_score_print: int | None


def _parse_defaults(obj: object) -> _DefaultPolicy:
    mapping = _expect_mapping(obj, "defaults")
    required = {
        "emit_membership_dataset",
        "log_all_candidates",
        "max_candidates_cap",
        "zero_weight_rule",
    }
    unknown = set(mapping) - (required | {"dp_score_print"})
    missing = required - set(mapping)
    if unknown:
        raise PolicyValidationError(f"defaults contains unknown keys: {sorted(unknown)}")
    if missing:
        raise PolicyValidationError(f"defaults missing required keys: {sorted(missing)}")

    emit_membership_dataset = _expect_bool(
        mapping["emit_membership_dataset"], "defaults.emit_membership_dataset"
    )
    log_all_candidates = _expect_bool(
        mapping["log_all_candidates"], "defaults.log_all_candidates"
    )
    max_candidates_cap = _expect_int(
        mapping["max_candidates_cap"], "defaults.max_candidates_cap"
    )
    if max_candidates_cap < 0:
        raise PolicyValidationError(
            f"defaults.max_candidates_cap must be ≥ 0, got {max_candidates_cap}"
        )
    zero_weight_rule = _expect_zero_weight_rule(
        mapping["zero_weight_rule"], "defaults.zero_weight_rule"
    )
    dp_score_print = None
    if "dp_score_print" in mapping:
        dp_score_print = _expect_int(mapping["dp_score_print"], "defaults.dp_score_print")
        if dp_score_print < 0:
            raise PolicyValidationError(
                f"defaults.dp_score_print must be ≥ 0, got {dp_score_print}"
            )

    return _DefaultPolicy(
        emit_membership_dataset=emit_membership_dataset,
        log_all_candidates=log_all_candidates,
        max_candidates_cap=max_candidates_cap,
        zero_weight_rule=zero_weight_rule,
        dp_score_print=dp_score_print,
    )


def _parse_per_currency(
    obj: object,
    defaults: _DefaultPolicy,
) -> Mapping[str, SelectionOverrides]:
    mapping = _expect_mapping(obj, "per_currency")
    overrides: Dict[str, SelectionOverrides] = {}
    for currency, value in mapping.items():
        label = f"per_currency.{currency}"
        currency_code = _expect_string(currency, f"{label} key")
        if not _ISO4217_RE.fullmatch(currency_code):
            raise PolicyValidationError(
                f"{label} must use uppercase ISO-4217 codes, got '{currency_code}'"
            )
        override_mapping = _expect_mapping(value, label)
        allowed_keys = {"emit_membership_dataset", "max_candidates_cap", "zero_weight_rule"}
        unknown = set(override_mapping) - allowed_keys
        if unknown:
            raise PolicyValidationError(
                f"{label} unknown keys: {sorted(unknown)} (log_all_candidates is global)"
            )

        emit_membership_dataset = defaults.emit_membership_dataset
        if "emit_membership_dataset" in override_mapping:
            emit_membership_dataset = _expect_bool(
                override_mapping["emit_membership_dataset"],
                f"{label}.emit_membership_dataset",
            )

        max_candidates_cap = defaults.max_candidates_cap
        if "max_candidates_cap" in override_mapping:
            max_candidates_cap = _expect_int(
                override_mapping["max_candidates_cap"],
                f"{label}.max_candidates_cap",
            )
            if max_candidates_cap < 0:
                raise PolicyValidationError(
                    f"{label}.max_candidates_cap must be ≥ 0, got {max_candidates_cap}"
                )

        zero_weight_rule = defaults.zero_weight_rule
        if "zero_weight_rule" in override_mapping:
            zero_weight_rule = _expect_zero_weight_rule(
                override_mapping["zero_weight_rule"], f"{label}.zero_weight_rule"
            )

        overrides[currency_code] = SelectionOverrides(
            emit_membership_dataset=emit_membership_dataset,
            max_candidates_cap=max_candidates_cap,
            zero_weight_rule=zero_weight_rule,
        )

    # Provide deterministic ordering to aid reproducibility and hashing.
    ordered: Dict[str, SelectionOverrides] = dict(sorted(overrides.items()))
    return ordered


def _expect_mapping(obj: object, label: str) -> MutableMapping[str, object]:
    if not isinstance(obj, MutableMapping):
        raise PolicyValidationError(f"{label} must be a mapping")
    return obj


def _expect_string(obj: object, label: str) -> str:
    if not isinstance(obj, str):
        raise PolicyValidationError(f"{label} must be a string")
    return obj


def _expect_bool(obj: object, label: str) -> bool:
    if not isinstance(obj, bool):
        raise PolicyValidationError(f"{label} must be a boolean")
    return obj


def _expect_int(obj: object, label: str) -> int:
    if not isinstance(obj, int):
        raise PolicyValidationError(f"{label} must be an integer")
    return int(obj)


def _expect_zero_weight_rule(obj: object, label: str) -> str:
    value = _expect_string(obj, label)
    if value not in _ZERO_WEIGHT_RULES:
        raise PolicyValidationError(
            f"{label} must be one of {sorted(_ZERO_WEIGHT_RULES)}, got '{value}'"
        )
    return value
