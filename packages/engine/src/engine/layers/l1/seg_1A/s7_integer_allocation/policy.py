"""Policy loading and validation for S7 integer allocation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

import yaml

from ..s0_foundations.exceptions import err
from ..shared.dictionary import get_repo_root

__all__ = [
    "DirichletAlphaPolicy",
    "IntegerisationPolicy",
    "PolicyLoadingError",
    "ResidualQuantisationPolicy",
    "ThresholdsPolicy",
    "load_policy",
]


class PolicyLoadingError(ValueError):
    """Raised when a governed S7 policy fails validation."""


@dataclass(frozen=True)
class ThresholdsPolicy:
    """Deterministic integer bounds policy for bounded Hamilton allocation."""

    semver: str
    version: str
    enabled: bool
    home_min: int
    force_at_least_one_foreign_if_foreign_present: bool
    min_one_per_country_when_feasible: bool
    foreign_cap_mode: str
    on_infeasible: str


@dataclass(frozen=True)
class ResidualQuantisationPolicy:
    """Numeric policy for residual quantisation and deterministic sorting."""

    dp_resid: int
    rounding: str
    sort_primary: str
    tiebreak_keys: Tuple[str, ...]
    forbid_nan_inf: bool
    residual_domain: Tuple[float, float]
    enforce_residual_domain: bool


@dataclass(frozen=True)
class DirichletAlphaPolicy:
    """Dirichlet alpha policy for the S7 Dirichlet lane."""

    semver: str
    version: str
    enabled: bool
    kind: str
    total_concentration: float
    base_share_source: str
    include_home_boost: bool
    home_boost_multiplier: float
    alpha_min: float
    alpha_max: float
    on_missing_base_shares: str
    on_nonfinite_alpha: str


@dataclass(frozen=True)
class IntegerisationPolicy:
    """Aggregated S7 policy bundle."""

    thresholds: ThresholdsPolicy | None
    residual_policy: ResidualQuantisationPolicy
    dirichlet_policy: DirichletAlphaPolicy | None
    thresholds_path: Path | None
    residual_policy_path: Path
    dirichlet_policy_path: Path | None

    @property
    def bounds_enabled(self) -> bool:
        return bool(self.thresholds and self.thresholds.enabled)

    @property
    def dirichlet_enabled(self) -> bool:
        return bool(self.dirichlet_policy and self.dirichlet_policy.enabled)

    @property
    def digests(self) -> Dict[str, str]:
        digests: Dict[str, str] = {
            str(self.residual_policy_path): _sha256_file(self.residual_policy_path),
        }
        if self.thresholds and self.thresholds.enabled and self.thresholds_path is not None:
            digests[str(self.thresholds_path)] = _sha256_file(self.thresholds_path)
        if self.dirichlet_policy and self.dirichlet_policy.enabled and self.dirichlet_policy_path is not None:
            digests[str(self.dirichlet_policy_path)] = _sha256_file(self.dirichlet_policy_path)
        return digests


def load_policy(
    thresholds_path: Path | str | None,
    *,
    residual_policy_path: Path | str | None = None,
    dirichlet_policy_path: Path | str | None = None,
) -> IntegerisationPolicy:
    """Load the S7 policy bundle (thresholds + residual + optional Dirichlet)."""

    repo_root = get_repo_root()
    thresholds_file = Path(thresholds_path).expanduser().resolve() if thresholds_path else None
    if thresholds_file is None:
        candidate = repo_root / "config" / "layer1" / "1A" / "policy" / "s3.thresholds.yaml"
        thresholds_file = candidate if candidate.exists() else None

    residual_file = (
        Path(residual_policy_path).expanduser().resolve()
        if residual_policy_path
        else (
            repo_root
            / "config"
            / "layer1"
            / "1A"
            / "numeric"
            / "residual_quantisation.yaml"
        )
    )
    if not residual_file.exists():
        raise PolicyLoadingError(f"residual quantisation policy missing at {residual_file}")

    dirichlet_file = (
        Path(dirichlet_policy_path).expanduser().resolve()
        if dirichlet_policy_path
        else (
            repo_root
            / "config"
            / "layer1"
            / "1A"
            / "models"
            / "allocation"
            / "dirichlet_alpha_policy.yaml"
        )
    )
    if not dirichlet_file.exists():
        dirichlet_file = None

    thresholds_policy = (
        _load_thresholds_policy(thresholds_file) if thresholds_file is not None else None
    )
    residual_policy = _load_residual_quantisation_policy(residual_file)
    dirichlet_policy = (
        _load_dirichlet_alpha_policy(dirichlet_file) if dirichlet_file is not None else None
    )

    if dirichlet_policy is not None and not dirichlet_policy.enabled:
        dirichlet_policy = None

    return IntegerisationPolicy(
        thresholds=thresholds_policy,
        residual_policy=residual_policy,
        dirichlet_policy=dirichlet_policy,
        thresholds_path=thresholds_file,
        residual_policy_path=residual_file,
        dirichlet_policy_path=dirichlet_file,
    )


def _load_thresholds_policy(path: Path) -> ThresholdsPolicy:
    mapping = _load_yaml_mapping(path, "thresholds policy")
    allowed = {
        "semver",
        "version",
        "enabled",
        "home_min",
        "force_at_least_one_foreign_if_foreign_present",
        "min_one_per_country_when_feasible",
        "foreign_cap_mode",
        "on_infeasible",
    }
    unknown = set(mapping) - allowed
    if unknown:
        raise PolicyLoadingError(f"thresholds policy contains unknown keys: {sorted(unknown)}")

    semver = _expect_string(mapping.get("semver"), "semver")
    version = _expect_string(mapping.get("version"), "version")
    enabled = _expect_bool(mapping.get("enabled"), "enabled")
    home_min = _expect_int(mapping.get("home_min"), "home_min")
    if home_min < 0:
        raise PolicyLoadingError("home_min must be >= 0")
    force_foreign = _expect_bool(
        mapping.get("force_at_least_one_foreign_if_foreign_present"),
        "force_at_least_one_foreign_if_foreign_present",
    )
    min_one = _expect_bool(
        mapping.get("min_one_per_country_when_feasible"),
        "min_one_per_country_when_feasible",
    )
    foreign_cap_mode = _expect_string(mapping.get("foreign_cap_mode"), "foreign_cap_mode")
    if foreign_cap_mode not in {"none", "n_minus_home_min"}:
        raise PolicyLoadingError("foreign_cap_mode must be 'none' or 'n_minus_home_min'")
    on_infeasible = _expect_string(mapping.get("on_infeasible"), "on_infeasible")
    if on_infeasible != "fail":
        raise PolicyLoadingError("on_infeasible must be 'fail' in v1")

    return ThresholdsPolicy(
        semver=semver,
        version=version,
        enabled=enabled,
        home_min=home_min,
        force_at_least_one_foreign_if_foreign_present=force_foreign,
        min_one_per_country_when_feasible=min_one,
        foreign_cap_mode=foreign_cap_mode,
        on_infeasible=on_infeasible,
    )


def _load_residual_quantisation_policy(path: Path) -> ResidualQuantisationPolicy:
    mapping = _load_yaml_mapping(path, "residual quantisation policy")
    allowed = {"semver", "version", "dp_resid", "rounding", "sort", "tiebreak", "validation"}
    unknown = set(mapping) - allowed
    if unknown:
        raise PolicyLoadingError(
            f"residual quantisation policy contains unknown keys: {sorted(unknown)}"
        )

    dp_resid = _expect_int(mapping.get("dp_resid"), "dp_resid")
    if dp_resid < 0 or dp_resid > 18:
        raise PolicyLoadingError("dp_resid must be within 0..18")

    rounding = _expect_string(mapping.get("rounding"), "rounding").upper()
    if rounding != "RNE":
        raise PolicyLoadingError("rounding must be 'RNE' in v1")

    sort_map = _expect_mapping(mapping.get("sort"), "sort")
    sort_primary = _expect_string(sort_map.get("primary_key"), "sort.primary_key")
    stable = _expect_bool(sort_map.get("stable"), "sort.stable")
    if sort_primary != "residual_desc":
        raise PolicyLoadingError("sort.primary_key must be 'residual_desc'")
    if stable is not True:
        raise PolicyLoadingError("sort.stable must be true")

    tiebreak_map = _expect_mapping(mapping.get("tiebreak"), "tiebreak")
    tiebreak_keys_raw = tiebreak_map.get("keys")
    if not isinstance(tiebreak_keys_raw, Sequence) or not tiebreak_keys_raw:
        raise PolicyLoadingError("tiebreak.keys must be a non-empty list")
    allowed_keys = {
        "country_iso_asc",
        "candidate_rank_asc",
        "merchant_id_asc",
        "tile_id_asc",
    }
    tiebreak_keys = []
    for key in tiebreak_keys_raw:
        value = str(key)
        if value not in allowed_keys:
            raise PolicyLoadingError(f"unsupported tiebreak key '{value}'")
        tiebreak_keys.append(value)

    validation_map = _expect_mapping(mapping.get("validation"), "validation")
    forbid_nan_inf = _expect_bool(validation_map.get("forbid_nan_inf"), "validation.forbid_nan_inf")
    residual_domain = validation_map.get("residual_domain")
    if (
        not isinstance(residual_domain, Sequence)
        or len(residual_domain) != 2
        or not all(isinstance(item, (int, float)) for item in residual_domain)
    ):
        raise PolicyLoadingError("validation.residual_domain must be a 2-number list")
    enforce_domain = _expect_bool(
        validation_map.get("enforce_residual_domain"),
        "validation.enforce_residual_domain",
    )

    return ResidualQuantisationPolicy(
        dp_resid=dp_resid,
        rounding=rounding,
        sort_primary=sort_primary,
        tiebreak_keys=tuple(tiebreak_keys),
        forbid_nan_inf=forbid_nan_inf,
        residual_domain=(float(residual_domain[0]), float(residual_domain[1])),
        enforce_residual_domain=enforce_domain,
    )


def _load_dirichlet_alpha_policy(path: Path) -> DirichletAlphaPolicy:
    mapping = _load_yaml_mapping(path, "dirichlet alpha policy")
    allowed = {"semver", "version", "enabled", "alpha_model", "bounds", "fallback"}
    unknown = set(mapping) - allowed
    if unknown:
        raise PolicyLoadingError(f"dirichlet policy contains unknown keys: {sorted(unknown)}")

    semver = _expect_string(mapping.get("semver"), "semver")
    version = _expect_string(mapping.get("version"), "version")
    enabled = _expect_bool(mapping.get("enabled"), "enabled")

    model_map = _expect_mapping(mapping.get("alpha_model"), "alpha_model")
    kind = _expect_string(model_map.get("kind"), "alpha_model.kind")
    if kind not in {"scaled_base_shares", "uniform"}:
        raise PolicyLoadingError("alpha_model.kind must be 'scaled_base_shares' or 'uniform'")
    total_concentration = _expect_positive_float(
        model_map.get("total_concentration"), "alpha_model.total_concentration"
    )
    base_share_source = _expect_string(
        model_map.get("base_share_source"), "alpha_model.base_share_source"
    )
    if base_share_source not in {"base_weight_priors", "ccy_country_weights_cache", "uniform"}:
        raise PolicyLoadingError(
            "alpha_model.base_share_source must be base_weight_priors, ccy_country_weights_cache, or uniform"
        )
    include_home_boost = _expect_bool(
        model_map.get("include_home_boost"), "alpha_model.include_home_boost"
    )
    home_boost_multiplier = _expect_float(
        model_map.get("home_boost_multiplier"), "alpha_model.home_boost_multiplier"
    )
    if home_boost_multiplier < 1.0:
        raise PolicyLoadingError("home_boost_multiplier must be >= 1.0")

    bounds_map = _expect_mapping(mapping.get("bounds"), "bounds")
    alpha_min = _expect_positive_float(bounds_map.get("alpha_min"), "bounds.alpha_min")
    alpha_max = _expect_positive_float(bounds_map.get("alpha_max"), "bounds.alpha_max")
    if alpha_max <= alpha_min:
        raise PolicyLoadingError("bounds.alpha_max must exceed alpha_min")

    fallback_map = _expect_mapping(mapping.get("fallback"), "fallback")
    on_missing = _expect_string(
        fallback_map.get("on_missing_base_shares"), "fallback.on_missing_base_shares"
    )
    if on_missing not in {"fail", "uniform"}:
        raise PolicyLoadingError("fallback.on_missing_base_shares must be 'fail' or 'uniform'")
    on_nonfinite = _expect_string(
        fallback_map.get("on_nonfinite_alpha"), "fallback.on_nonfinite_alpha"
    )
    if on_nonfinite != "fail":
        raise PolicyLoadingError("fallback.on_nonfinite_alpha must be 'fail'")

    return DirichletAlphaPolicy(
        semver=semver,
        version=version,
        enabled=enabled,
        kind=kind,
        total_concentration=total_concentration,
        base_share_source=base_share_source,
        include_home_boost=include_home_boost,
        home_boost_multiplier=home_boost_multiplier,
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        on_missing_base_shares=on_missing,
        on_nonfinite_alpha=on_nonfinite,
    )


def _load_yaml_mapping(path: Path, label: str) -> Mapping[str, object]:
    if not path.exists():
        raise PolicyLoadingError(f"{label} file not found: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PolicyLoadingError(f"failed to parse {label} YAML: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise PolicyLoadingError(f"{label} must decode to a mapping")
    return payload


def _expect_mapping(obj: object, label: str) -> Mapping[str, object]:
    if not isinstance(obj, Mapping):
        raise PolicyLoadingError(f"{label} must be a mapping")
    return obj


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


def _expect_float(obj: object, label: str) -> float:
    if not isinstance(obj, (int, float)):
        raise PolicyLoadingError(f"{label} must be a number")
    return float(obj)


def _expect_positive_float(obj: object, label: str) -> float:
    value = _expect_float(obj, label)
    if value <= 0.0:
        raise PolicyLoadingError(f"{label} must be > 0")
    return value


def _sha256_file(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()
