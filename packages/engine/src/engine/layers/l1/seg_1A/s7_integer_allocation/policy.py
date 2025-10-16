"""Policy loading and validation for S7 integer allocation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping

import yaml

__all__ = [
    "BoundsPolicy",
    "IntegerisationPolicy",
    "PolicyLoadingError",
    "load_bounds_policy",
    "load_policy",
]


class PolicyLoadingError(ValueError):
    """Raised when the governed S7 policy fails validation."""


@dataclass(frozen=True)
class BoundsPolicy:
    """Per-ISO integer bounds used when the bounded Hamilton lane is enabled."""

    path: Path
    floors: Mapping[str, int]
    ceilings: Mapping[str, int]

    def lower_bound(self, iso: str) -> int:
        return int(self.floors.get(iso.upper(), 0))

    def upper_bound(self, iso: str) -> int | None:
        value = self.ceilings.get(iso.upper())
        if value is None:
            return None
        return int(value)


@dataclass(frozen=True)
class IntegerisationPolicy:
    """Aggregated configuration for the S7 allocator."""

    policy_semver: str
    policy_version: str
    dp_resid: int
    dirichlet_enabled: bool
    dirichlet_alpha0: float | None
    bounds_enabled: bool
    bounds: BoundsPolicy | None

    @property
    def digests(self) -> Dict[str, str]:
        """Return SHA-256 digests for the governed policy artefacts."""

        digests = {}
        if self.bounds is not None:
            digests[str(self.bounds.path)] = _sha256_file(self.bounds.path)
        return digests


def load_policy(path: Path | str) -> IntegerisationPolicy:
    """Load the governed S7 policy and any referenced sub-policies."""

    policy_path = Path(path).expanduser().resolve()
    try:
        payload = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyLoadingError(f"policy file not found: {policy_path}") from exc
    except yaml.YAMLError as exc:
        raise PolicyLoadingError(f"failed to parse policy YAML: {exc}") from exc

    mapping = _expect_mapping(payload, "policy")
    allowed_keys = {
        "policy_semver",
        "policy_version",
        "notes",
        "dp_resid",
        "dirichlet_lane",
        "bounds_lane",
    }
    unknown = set(mapping) - allowed_keys
    if unknown:
        raise PolicyLoadingError(f"unknown top-level keys: {sorted(unknown)}")

    policy_semver = _expect_string(mapping.get("policy_semver"), "policy_semver")
    policy_version = _expect_string(mapping.get("policy_version"), "policy_version")
    dp_resid = _expect_int(mapping.get("dp_resid", 8), "dp_resid")
    if dp_resid != 8:
        raise PolicyLoadingError(
            f"dp_resid must be 8 (spec binding), got {dp_resid!r}"
        )

    dirichlet_config = mapping.get("dirichlet_lane", {})
    dirichlet_map = _expect_mapping(dirichlet_config, "dirichlet_lane")
    dirichlet_enabled = _expect_bool(
        dirichlet_map.get("enabled", False), "dirichlet_lane.enabled"
    )
    dirichlet_alpha0: float | None = None
    if dirichlet_enabled:
        if "alpha0" not in dirichlet_map:
            raise PolicyLoadingError("dirichlet_lane.alpha0 is required when enabled")
        dirichlet_alpha0 = _expect_positive_float(
            dirichlet_map["alpha0"], "dirichlet_lane.alpha0"
        )

    bounds_config = mapping.get("bounds_lane", {})
    bounds_map = _expect_mapping(bounds_config, "bounds_lane")
    bounds_enabled = _expect_bool(
        bounds_map.get("enabled", False), "bounds_lane.enabled"
    )
    bounds_policy: BoundsPolicy | None = None
    if bounds_enabled:
        policy_ref = bounds_map.get("policy_path")
        if policy_ref is None:
            raise PolicyLoadingError(
                "bounds_lane.policy_path is required when bounds lane is enabled"
            )
        bounds_policy = load_bounds_policy(policy_ref)

    return IntegerisationPolicy(
        policy_semver=policy_semver,
        policy_version=policy_version,
        dp_resid=dp_resid,
        dirichlet_enabled=dirichlet_enabled,
        dirichlet_alpha0=dirichlet_alpha0,
        bounds_enabled=bounds_enabled,
        bounds=bounds_policy,
    )


def load_bounds_policy(path: Path | str) -> BoundsPolicy:
    """Load and validate the optional bounds policy."""

    bounds_path = Path(path).expanduser().resolve()
    try:
        payload = yaml.safe_load(bounds_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyLoadingError(f"bounds policy not found: {bounds_path}") from exc
    except yaml.YAMLError as exc:
        raise PolicyLoadingError(f"failed to parse bounds policy YAML: {exc}") from exc

    mapping = _expect_mapping(payload, "bounds policy")
    allowed_keys = {"policy_semver", "version", "dp_resid", "floors", "ceilings"}
    unknown = set(mapping) - allowed_keys
    if unknown:
        raise PolicyLoadingError(
            f"bounds policy contains unknown keys: {sorted(unknown)}"
        )

    dp_resid = _expect_int(mapping.get("dp_resid", 8), "bounds.dp_resid")
    if dp_resid != 8:
        raise PolicyLoadingError(
            f"bounds policy dp_resid must be 8 (spec binding), got {dp_resid!r}"
        )

    floors = {
        iso.upper(): _expect_int(value, f"floors[{iso}]")
        for iso, value in _expect_mapping(mapping.get("floors", {}), "floors").items()
    }
    ceilings = {
        iso.upper(): _expect_int(value, f"ceilings[{iso}]")
        for iso, value in _expect_mapping(mapping.get("ceilings", {}), "ceilings").items()
    }

    for iso in list(floors):
        if not _is_iso2(iso):
            raise PolicyLoadingError(f"floors key '{iso}' must be ISO-3166 alpha-2")
        if floors[iso] < 0:
            raise PolicyLoadingError(f"floors[{iso}] must be ≥ 0")
    for iso in list(ceilings):
        if not _is_iso2(iso):
            raise PolicyLoadingError(f"ceilings key '{iso}' must be ISO-3166 alpha-2")
        if ceilings[iso] < 0:
            raise PolicyLoadingError(f"ceilings[{iso}] must be ≥ 0")
    for iso, lower in floors.items():
        upper = ceilings.get(iso)
        if upper is not None and upper < lower:
            raise PolicyLoadingError(
                f"ceiling {upper} for {iso} is less than floor {lower}"
            )

    return BoundsPolicy(path=bounds_path, floors=floors, ceilings=ceilings)


# ---------------------------------------------------------------------------#
# Helper utilities


def _expect_mapping(obj: object, label: str) -> Dict[str, object]:
    if obj is None:
        return {}
    if not isinstance(obj, dict):
        raise PolicyLoadingError(f"{label} must be a mapping")
    return dict(obj)


def _expect_string(obj: object, label: str) -> str:
    if not isinstance(obj, str) or not obj:
        raise PolicyLoadingError(f"{label} must be a non-empty string")
    return obj


def _expect_int(obj: object, label: str) -> int:
    if not isinstance(obj, int):
        raise PolicyLoadingError(f"{label} must be an integer")
    return int(obj)


def _expect_bool(obj: object, label: str) -> bool:
    if not isinstance(obj, bool):
        raise PolicyLoadingError(f"{label} must be a boolean")
    return bool(obj)


def _expect_positive_float(obj: object, label: str) -> float:
    if not isinstance(obj, (int, float)):
        raise PolicyLoadingError(f"{label} must be a positive number")
    value = float(obj)
    if value <= 0.0:
        raise PolicyLoadingError(f"{label} must be > 0, got {value!r}")
    return value


def _is_iso2(value: str) -> bool:
    return len(value) == 2 and value.isascii() and value.upper() == value


def _sha256_file(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()
