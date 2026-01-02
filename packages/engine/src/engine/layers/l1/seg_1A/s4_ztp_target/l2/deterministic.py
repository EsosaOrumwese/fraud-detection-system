"""Deterministic context assembly for S4 ZTP target sampling."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence, Tuple

import polars as pl
import yaml

from ...s0_foundations.exceptions import err
from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import HurdleDecision
from engine.layers.l1.seg_1A.s2_nb_outlets.l2.runner import NBFinalRecord
from ..contexts import S4DeterministicContext, S4HyperParameters, S4MerchantTarget


@dataclass(frozen=True)
class S4DeterministicArtefacts:
    """Digest summary of governed artefacts referenced by the S4 run."""

    hyperparams_path: Path
    hyperparams_sha256: str
    features_path: Path | None
    features_sha256: str | None

    def to_mapping(self) -> Mapping[str, str]:
        payload = {
            self.hyperparams_path.name: self.hyperparams_sha256,
        }
        if self.features_path and self.features_sha256:
            payload[self.features_path.name] = self.features_sha256
        return payload


def _sha256_file(path: Path) -> str:
    if not path.exists():
        raise err("ERR_S4_POLICY_INVALID", f"artefact '{path}' missing")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_hyperparams(path: Path) -> tuple[S4HyperParameters, float]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise err(
            "ERR_S4_POLICY_INVALID",
            f"hyperparameter file '{path}' must decode to a mapping",
        )
    if "ztp" in data:
        ztp = data.get("ztp")
        if not isinstance(ztp, Mapping):
            raise err(
                "ERR_S4_POLICY_INVALID",
                "ztp section must be a mapping",
            )
        theta = ztp.get("theta")
        theta_order = ztp.get("theta_order")
        if not isinstance(theta, Mapping) or not isinstance(theta_order, Sequence):
            raise err(
                "ERR_S4_POLICY_INVALID",
                "ztp must define theta (mapping) and theta_order (sequence)",
            )
        required_order = ("theta0_intercept", "theta1_log_n_sites")
        if any(name not in theta_order for name in required_order):
            raise err(
                "ERR_S4_POLICY_INVALID",
                "ztp.theta_order must include theta0_intercept and theta1_log_n_sites",
            )
        if "theta2_openness" in theta and "theta2_openness" not in theta_order:
            raise err(
                "ERR_S4_POLICY_INVALID",
                "ztp.theta_order must include theta2_openness when provided",
            )
        try:
            theta0 = float(theta["theta0_intercept"])
            theta1 = float(theta["theta1_log_n_sites"])
        except (KeyError, TypeError, ValueError) as exc:
            raise err(
                "ERR_S4_POLICY_INVALID",
                "ztp.theta must define numeric theta0_intercept/theta1_log_n_sites",
            ) from exc
        theta2 = theta.get("theta2_openness")
        if theta2 is not None:
            try:
                theta2 = float(theta2)
            except (TypeError, ValueError) as exc:
                raise err(
                    "ERR_S4_POLICY_INVALID",
                    "ztp.theta2_openness must be numeric when provided",
                ) from exc

        max_attempts = ztp.get("MAX_ZTP_ZERO_ATTEMPTS", 64)
        try:
            max_attempts_int = int(max_attempts)
        except (TypeError, ValueError) as exc:
            raise err(
                "ERR_S4_POLICY_INVALID",
                "ztp.MAX_ZTP_ZERO_ATTEMPTS must be an integer",
            ) from exc
        if max_attempts_int <= 0:
            raise err(
                "ERR_S4_POLICY_INVALID",
                "MAX_ZTP_ZERO_ATTEMPTS must be positive",
            )
        policy = ztp.get("ztp_exhaustion_policy", "abort")
        if policy not in {"abort", "downgrade_domestic"}:
            raise err(
                "ERR_S4_POLICY_INVALID",
                "ztp_exhaustion_policy must be 'abort' or 'downgrade_domestic'",
            )

        feature_x = ztp.get("feature_x")
        if not isinstance(feature_x, Mapping):
            raise err(
                "ERR_S4_POLICY_INVALID",
                "ztp.feature_x must be a mapping",
            )
        feature_default = float(feature_x.get("x_default", 0.0))
        if not 0.0 <= feature_default <= 1.0:
            raise err(
                "ERR_S4_POLICY_INVALID",
                f"x_default must lie in [0,1]; received {feature_default!r}",
            )
    else:
        link = data.get("ztp_link")
        controls = data.get("ztp_controls")
        if not isinstance(link, Mapping) or not isinstance(controls, Mapping):
            raise err(
                "ERR_S4_POLICY_INVALID",
                "hyperparameter file missing 'ztp' or legacy 'ztp_link'/'ztp_controls' sections",
            )
        try:
            theta0 = float(link["theta0"])
            theta1 = float(link["theta1"])
        except (KeyError, TypeError, ValueError) as exc:
            raise err(
                "ERR_S4_POLICY_INVALID",
                "ztp_link must define numeric theta0/theta1",
            ) from exc
        theta2 = link.get("theta2")
        if theta2 is not None:
            try:
                theta2 = float(theta2)
            except (TypeError, ValueError) as exc:
                raise err(
                    "ERR_S4_POLICY_INVALID",
                    "ztp_link.theta2 must be numeric when provided",
                ) from exc

        max_attempts = controls.get("MAX_ZTP_ZERO_ATTEMPTS", 64)
        try:
            max_attempts_int = int(max_attempts)
        except (TypeError, ValueError) as exc:
            raise err(
                "ERR_S4_POLICY_INVALID",
                "ztp_controls.MAX_ZTP_ZERO_ATTEMPTS must be an integer",
            ) from exc
        if max_attempts_int <= 0:
            raise err(
                "ERR_S4_POLICY_INVALID",
                "MAX_ZTP_ZERO_ATTEMPTS must be positive",
            )
        policy = controls.get("ztp_exhaustion_policy", "abort")
        if policy not in {"abort", "downgrade_domestic"}:
            raise err(
                "ERR_S4_POLICY_INVALID",
                "ztp_exhaustion_policy must be 'abort' or 'downgrade_domestic'",
            )

        feature_default = float(data.get("X_default", 0.0))
        if not 0.0 <= feature_default <= 1.0:
            raise err(
                "ERR_S4_POLICY_INVALID",
                f"X_default must lie in [0,1]; received {feature_default!r}",
            )

    semver = data.get("semver")
    if semver is not None and not isinstance(semver, str):
        raise err(
            "ERR_S4_POLICY_INVALID",
            "hyperparameter semver must be a string when provided",
        )

    hyperparams = S4HyperParameters(
        theta0=theta0,
        theta1=theta1,
        theta2=float(theta2) if theta2 is not None else None,
        max_zero_attempts=max_attempts_int,
        exhaustion_policy=str(policy),
        default_feature_value=feature_default,
        source_path=path,
        semver=semver,
    )
    return hyperparams, feature_default


def _decision_lookup(decisions: Sequence[HurdleDecision]) -> Mapping[int, HurdleDecision]:
    mapping: dict[int, HurdleDecision] = {}
    for decision in decisions:
        merchant_id = int(decision.merchant_id)
        if merchant_id in mapping:
            raise err(
                "ERR_S4_POLICY_INVALID",
                f"duplicate hurdle decision for merchant {merchant_id}",
            )
        mapping[merchant_id] = decision
    return mapping


def _final_lookup(finals: Sequence[NBFinalRecord]) -> Mapping[int, NBFinalRecord]:
    mapping: dict[int, NBFinalRecord] = {}
    for record in finals:
        merchant_id = int(record.merchant_id)
        if merchant_id in mapping:
            raise err(
                "ERR_S4_POLICY_INVALID",
                f"duplicate nb_final record for merchant {merchant_id}",
            )
        mapping[merchant_id] = record
    return mapping


def _eligibility_lookup(flags: pl.DataFrame) -> Mapping[int, bool]:
    if "merchant_id" not in flags.columns or "is_eligible" not in flags.columns:
        raise err(
            "ERR_S4_POLICY_INVALID",
            "crossborder_flags must expose 'merchant_id' and 'is_eligible'",
        )
    return {
        int(row[0]): bool(row[1])
        for row in flags.select(["merchant_id", "is_eligible"]).to_numpy()
    }


def _feature_lookup(
    path: Path | None,
    *,
    parameter_hash: str,
) -> tuple[Mapping[int, float], Path | None]:
    if path is None:
        return {}, None
    candidate_path = path
    if not candidate_path.exists():
        if candidate_path.is_dir():
            raise err("ERR_S4_POLICY_INVALID", f"feature view '{path}' missing")
        if candidate_path.parent.exists():
            shard_candidates = sorted(candidate_path.parent.glob(candidate_path.name.replace("00000", "*.parquet")))
            if shard_candidates:
                candidate_path = shard_candidates[0]
    if not candidate_path.exists():
        raise err("ERR_S4_POLICY_INVALID", f"feature view '{path}' missing")

    frame = pl.read_parquet(candidate_path, columns=["merchant_id", "openness", "parameter_hash"])
    if "merchant_id" not in frame.columns or "openness" not in frame.columns:
        raise err(
            "ERR_S4_POLICY_INVALID",
            "feature view must include 'merchant_id' and 'openness' columns",
        )
    if "parameter_hash" in frame.columns and frame.height > 0:
        if not bool((frame.get_column("parameter_hash") == parameter_hash).all()):
            raise err(
                "ERR_S4_POLICY_INVALID",
                "crossborder_features parameter_hash mismatch",
            )
    mapping: dict[int, float] = {}
    for merchant_id, value, _param in frame.iter_rows():
        try:
            feature_value = float(value)
        except (TypeError, ValueError) as exc:
            raise err(
                "ERR_S4_POLICY_INVALID",
                f"feature value for merchant {merchant_id} is non-numeric",
            ) from exc
        mapping[int(merchant_id)] = feature_value
    return mapping, candidate_path


def _candidate_universe_counts(path: Path) -> Mapping[int, int]:
    if not path.exists():
        raise err(
            "ERR_S4_POLICY_INVALID",
            f"S3 candidate set not found at '{path}'",
        )
    frame = pl.read_parquet(path, columns=["merchant_id", "is_home"])
    if "is_home" not in frame.columns or "merchant_id" not in frame.columns:
        raise err(
            "ERR_S4_POLICY_INVALID",
            "candidate set must contain 'merchant_id' and 'is_home'",
        )
    counts = (
        frame.filter(pl.col("is_home") == False)  # noqa: E712
        .group_by("merchant_id")
        .agg(pl.len().alias("foreign_count"))
    )
    return {
        int(row[0]): int(row[1])
        for row in counts.iter_rows()
    }


def build_deterministic_context(
    *,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
    seed: int,
    hyperparams_path: Path,
    nb_finals: Sequence[NBFinalRecord],
    hurdle_decisions: Sequence[HurdleDecision],
    crossborder_flags: pl.DataFrame,
    candidate_set_path: Path,
    feature_view_path: Path | None = None,
) -> tuple[S4DeterministicContext, S4DeterministicArtefacts]:
    """Assemble the deterministic context required by the S4 sampler."""

    hyperparams, feature_default = _load_hyperparams(hyperparams_path)
    decision_map = _decision_lookup(hurdle_decisions)
    final_map = _final_lookup(nb_finals)
    eligibility_map = _eligibility_lookup(crossborder_flags)
    feature_map, feature_path = _feature_lookup(
        feature_view_path,
        parameter_hash=parameter_hash,
    )
    candidate_counts = _candidate_universe_counts(candidate_set_path)

    merchants: list[S4MerchantTarget] = []
    for merchant_id, final in sorted(final_map.items(), key=lambda item: item[0]):
        decision = decision_map.get(merchant_id)
        if decision is None:
            raise err(
                "ERR_S4_POLICY_INVALID",
                f"hurdle decision missing for merchant {merchant_id}",
            )
        is_multi = bool(decision.is_multi)
        eligibility = bool(eligibility_map.get(merchant_id, False))
        feature_value = feature_map.get(merchant_id, feature_default)
        if not 0.0 <= feature_value <= 1.0:
            raise err(
                "ERR_S4_POLICY_INVALID",
                f"feature value for merchant {merchant_id} must lie in [0,1]; "
                f"received {feature_value!r}",
            )
        merchants.append(
            S4MerchantTarget(
                merchant_id=merchant_id,
                n_outlets=int(final.n_outlets),
                admissible_foreign_count=int(candidate_counts.get(merchant_id, 0)),
                is_multi=is_multi,
                is_eligible=eligibility,
                feature_value=float(feature_value),
            )
        )

    artefacts = S4DeterministicArtefacts(
        hyperparams_path=hyperparams_path,
        hyperparams_sha256=_sha256_file(hyperparams_path),
        features_path=feature_path,
        features_sha256=_sha256_file(feature_path) if feature_path else None,
    )

    context = S4DeterministicContext(
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        seed=int(seed),
        run_id=str(run_id),
        hyperparams=hyperparams,
        merchants=tuple(merchants),
        feature_name="openness",
        feature_source_path=feature_path,
        artefact_digests=artefacts.to_mapping(),
    )
    return context, artefacts


__all__ = [
    "S4DeterministicArtefacts",
    "build_deterministic_context",
]
