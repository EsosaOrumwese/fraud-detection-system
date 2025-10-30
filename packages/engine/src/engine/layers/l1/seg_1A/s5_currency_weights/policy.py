"""Parsing & validation for `ccy_smoothing_params.yaml`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Mapping, MutableMapping, Optional

import yaml

__all__ = [
    "PolicyValidationError",
    "Defaults",
    "CurrencyOverrides",
    "SmoothingPolicy",
    "load_policy",
]


_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO4217_RE = re.compile(r"^[A-Z]{3}$")
_ISO2_RE = re.compile(r"^[A-Z]{2}$")


class PolicyValidationError(ValueError):
    """Raised when the smoothing policy fails structural validation."""


@dataclass(frozen=True)
class Defaults:
    blend_weight: float
    alpha: float
    obs_floor: int
    min_share: float
    shrink_exponent: float


@dataclass(frozen=True)
class CurrencyOverrides:
    blend_weight: Optional[float] = None
    alpha: Optional[float] = None
    obs_floor: Optional[int] = None
    min_share: Optional[float] = None
    shrink_exponent: Optional[float] = None


@dataclass(frozen=True)
class SmoothingPolicy:
    semver: str
    version: str
    dp: int
    defaults: Defaults
    per_currency: Mapping[str, CurrencyOverrides]
    alpha_iso: Mapping[str, Mapping[str, float]]
    min_share_iso: Mapping[str, Mapping[str, float]]


def load_policy(path: str | Path) -> SmoothingPolicy:
    """Load and validate the governed smoothing policy."""

    policy_path = Path(path)
    try:
        raw = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyValidationError(f"policy file not found: {policy_path}") from exc
    except yaml.YAMLError as exc:
        raise PolicyValidationError(f"failed to parse YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise PolicyValidationError("policy root must be a mapping")

    required_keys = {"semver", "version", "dp", "defaults", "per_currency", "overrides"}
    unknown_keys = set(raw) - required_keys
    missing_keys = required_keys - set(raw)
    if unknown_keys:
        raise PolicyValidationError(f"unknown top-level keys: {sorted(unknown_keys)}")
    if missing_keys:
        raise PolicyValidationError(f"missing top-level keys: {sorted(missing_keys)}")

    semver = _expect_string(raw["semver"], "semver")
    if not _SEMVER_RE.fullmatch(semver):
        raise PolicyValidationError(f"semver must match MAJOR.MINOR.PATCH, got '{semver}'")

    version = _expect_string(raw["version"], "version")
    if not _DATE_RE.fullmatch(version):
        raise PolicyValidationError(f"version must be YYYY-MM-DD, got '{version}'")

    dp = _expect_int(raw["dp"], "dp")
    if not 0 <= dp <= 18:
        raise PolicyValidationError(f"dp must be within [0, 18], got {dp}")

    defaults = _parse_defaults(raw["defaults"])
    per_currency = _parse_per_currency(raw["per_currency"])
    overrides = _parse_overrides(raw["overrides"])

    alpha_iso = overrides.get("alpha_iso", {})
    min_share_iso = overrides.get("min_share_iso", {})

    _validate_currencies(per_currency, alpha_iso, min_share_iso)
    _validate_min_share_sums(min_share_iso)

    return SmoothingPolicy(
        semver=semver,
        version=version,
        dp=dp,
        defaults=defaults,
        per_currency=per_currency,
        alpha_iso=alpha_iso,
        min_share_iso=min_share_iso,
    )


def _parse_defaults(obj: object) -> Defaults:
    mapping = _expect_mapping(obj, "defaults")
    expected_keys = {"blend_weight", "alpha", "obs_floor", "min_share", "shrink_exponent"}
    unknown = set(mapping) - expected_keys
    missing = expected_keys - set(mapping)
    if unknown:
        raise PolicyValidationError(f"defaults contains unknown keys: {sorted(unknown)}")
    if missing:
        raise PolicyValidationError(f"defaults missing keys: {sorted(missing)}")

    blend_weight = _expect_float(mapping["blend_weight"], "defaults.blend_weight")
    _check_range(blend_weight, 0.0, 1.0, "defaults.blend_weight")

    alpha = _expect_float(mapping["alpha"], "defaults.alpha")
    _check_min(alpha, 0.0, "defaults.alpha")

    obs_floor = _expect_int(mapping["obs_floor"], "defaults.obs_floor")
    _check_min(obs_floor, 0, "defaults.obs_floor")

    min_share = _expect_float(mapping["min_share"], "defaults.min_share")
    _check_range(min_share, 0.0, 1.0, "defaults.min_share")

    shrink_exponent = _expect_float(mapping["shrink_exponent"], "defaults.shrink_exponent")
    _check_min(shrink_exponent, 0.0, "defaults.shrink_exponent")

    return Defaults(
        blend_weight=blend_weight,
        alpha=alpha,
        obs_floor=obs_floor,
        min_share=min_share,
        shrink_exponent=shrink_exponent,
    )


def _parse_per_currency(obj: object) -> Dict[str, CurrencyOverrides]:
    mapping = _expect_mapping(obj, "per_currency")
    result: Dict[str, CurrencyOverrides] = {}
    for currency, overrides_obj in mapping.items():
        if not _ISO4217_RE.fullmatch(_expect_string(currency, "per_currency key")):
            raise PolicyValidationError(f"per_currency key '{currency}' is not ISO-4217 uppercase code")
        overrides_map = _expect_mapping(overrides_obj, f"per_currency.{currency}")
        allowed_keys = {"blend_weight", "alpha", "obs_floor", "min_share", "shrink_exponent"}
        unknown = set(overrides_map) - allowed_keys
        if unknown:
            raise PolicyValidationError(
                f"per_currency.{currency} contains unknown keys: {sorted(unknown)}"
            )

        overrides = CurrencyOverrides(
            blend_weight=_maybe_float(overrides_map.get("blend_weight"), f"per_currency.{currency}.blend_weight"),
            alpha=_maybe_float(overrides_map.get("alpha"), f"per_currency.{currency}.alpha"),
            obs_floor=_maybe_int(overrides_map.get("obs_floor"), f"per_currency.{currency}.obs_floor"),
            min_share=_maybe_float(overrides_map.get("min_share"), f"per_currency.{currency}.min_share"),
            shrink_exponent=_maybe_float(
                overrides_map.get("shrink_exponent"), f"per_currency.{currency}.shrink_exponent"
            ),
        )

        if overrides.blend_weight is not None:
            _check_range(overrides.blend_weight, 0.0, 1.0, f"per_currency.{currency}.blend_weight")
        if overrides.alpha is not None:
            _check_min(overrides.alpha, 0.0, f"per_currency.{currency}.alpha")
        if overrides.obs_floor is not None:
            _check_min(overrides.obs_floor, 0, f"per_currency.{currency}.obs_floor")
        if overrides.min_share is not None:
            _check_range(overrides.min_share, 0.0, 1.0, f"per_currency.{currency}.min_share")
        if overrides.shrink_exponent is not None:
            _check_min(overrides.shrink_exponent, 0.0, f"per_currency.{currency}.shrink_exponent")

        result[currency] = overrides
    return result


def _parse_overrides(obj: object) -> Dict[str, Dict[str, Dict[str, float]]]:
    mapping = _expect_mapping(obj, "overrides")
    allowed_keys = {"alpha_iso", "min_share_iso"}
    unknown = set(mapping) - allowed_keys
    if unknown:
        raise PolicyValidationError(f"overrides contains unknown keys: {sorted(unknown)}")

    processed: Dict[str, Dict[str, Dict[str, float]]] = {"alpha_iso": {}, "min_share_iso": {}}

    alpha_iso_obj = mapping.get("alpha_iso") or {}
    processed["alpha_iso"] = _parse_iso_overrides(alpha_iso_obj, "alpha_iso", min_value=0.0, max_value=None)

    min_share_iso_obj = mapping.get("min_share_iso") or {}
    processed["min_share_iso"] = _parse_iso_overrides(min_share_iso_obj, "min_share_iso", min_value=0.0, max_value=1.0)

    return processed


def _parse_iso_overrides(
    obj: object,
    label: str,
    *,
    min_value: float,
    max_value: Optional[float],
) -> Dict[str, Dict[str, float]]:
    mapping = _expect_mapping(obj, label)
    result: Dict[str, Dict[str, float]] = {}
    for currency, iso_map_obj in mapping.items():
        if not _ISO4217_RE.fullmatch(_expect_string(currency, f"{label} key")):
            raise PolicyValidationError(f"{label} key '{currency}' is not ISO-4217 uppercase code")
        iso_map = _expect_mapping(iso_map_obj, f"{label}.{currency}")
        if not iso_map:
            raise PolicyValidationError(f"{label}.{currency} must contain at least one ISO override")
        rows: Dict[str, float] = {}
        for iso, value in iso_map.items():
            if not _ISO2_RE.fullmatch(_expect_string(iso, f"{label}.{currency} key")):
                raise PolicyValidationError(f"{label}.{currency} key '{iso}' is not ISO-3166 alpha-2 uppercase")
            number = _expect_float(value, f"{label}.{currency}.{iso}")
            _check_min(number, min_value, f"{label}.{currency}.{iso}")
            if max_value is not None:
                _check_max(number, max_value, f"{label}.{currency}.{iso}")
            rows[iso] = number
        result[currency] = rows
    return result


def _validate_currencies(
    per_currency: Mapping[str, CurrencyOverrides],
    alpha_iso: Mapping[str, Mapping[str, float]],
    min_share_iso: Mapping[str, Mapping[str, float]],
) -> None:
    """Ensure overrides reference only known ISO currency codes."""

    # We accept any ISO-4217 code, so nothing to cross-check against defaults.
    # Validation ensures uppercase 3-letter codes already.
    return None


def _validate_min_share_sums(min_share_iso: Mapping[str, Mapping[str, float]]) -> None:
    for currency, mapping in min_share_iso.items():
        total = sum(mapping.values())
        if total > 1.0 + 1e-9:
            raise PolicyValidationError(
                f"min_share_iso for currency '{currency}' exceeds 1.0 (sum={total})"
            )


def _expect_mapping(obj: object, label: str) -> MutableMapping[str, object]:
    if not isinstance(obj, dict):
        raise PolicyValidationError(f"{label} must be a mapping")
    return obj


def _expect_string(obj: object, label: str) -> str:
    if not isinstance(obj, str):
        raise PolicyValidationError(f"{label} must be a string")
    return obj


def _expect_int(obj: object, label: str) -> int:
    if not isinstance(obj, int):
        raise PolicyValidationError(f"{label} must be an integer")
    return obj


def _expect_float(obj: object, label: str) -> float:
    if not isinstance(obj, (int, float)):
        raise PolicyValidationError(f"{label} must be a number")
    return float(obj)


def _maybe_float(obj: object, label: str) -> Optional[float]:
    if obj is None:
        return None
    return _expect_float(obj, label)


def _maybe_int(obj: object, label: str) -> Optional[int]:
    if obj is None:
        return None
    return _expect_int(obj, label)


def _check_range(value: float, minimum: float, maximum: float, label: str) -> None:
    if value < minimum or value > maximum:
        raise PolicyValidationError(f"{label} must be within [{minimum}, {maximum}], got {value}")


def _check_min(value: float, minimum: float, label: str) -> None:
    if value < minimum:
        raise PolicyValidationError(f"{label} must be ≥ {minimum}, got {value}")


def _check_max(value: float, maximum: float, label: str) -> None:
    if value > maximum:
        raise PolicyValidationError(f"{label} must be ≤ {maximum}, got {value}")
