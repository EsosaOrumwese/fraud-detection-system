"""Deterministic context assembly for S3 (cross-border universe).

S3.0 consumes the S1 hurdle outcomes, S2 NB finals, merchant metadata, and the
governed policy artefacts to build an immutable context record.  The context
captures everything downstream states need (merchant profile, S2 outlet count,
iso vocabulary, policy digests) while enforcing the spec gates defined for S3.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence, Tuple

import yaml

from ...s0_foundations.exceptions import err
from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import HurdleDecision
from engine.layers.l1.seg_1A.s2_nb_outlets.l2.runner import NBFinalRecord

_ALLOWED_CHANNELS = {"CP", "CNP"}


@dataclass(frozen=True)
class ArtefactSpec:
    """Specification describing a governed artefact to include in the context."""

    artefact_id: str
    path: Path
    semver: str | None = None


@dataclass(frozen=True)
class ArtefactMetadata:
    """Digest information captured for governed artefacts."""

    artefact_id: str
    semver: str | None
    version: str | None
    sha256: str


@dataclass(frozen=True)
class ArtefactBundle:
    """Collection of governed artefacts tied to the S3 run."""

    rule_ladder: ArtefactMetadata
    iso_countries: ArtefactMetadata
    currency_to_country: ArtefactMetadata | None = None
    base_weight: ArtefactMetadata | None = None
    thresholds: ArtefactMetadata | None = None
    bounds: ArtefactMetadata | None = None


@dataclass(frozen=True)
class MerchantProfile:
    """Ingress merchant details required by S3."""

    merchant_id: int
    home_country_iso: str
    mcc: str
    channel: str


@dataclass(frozen=True)
class MerchantContext:
    """Deterministic S3 context for a single merchant."""

    merchant_id: int
    home_country_iso: str
    mcc: str
    channel: str
    n_outlets: int


@dataclass(frozen=True)
class S3DeterministicContext:
    """Immutable bundle handed to subsequent S3 stages."""

    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    seed: int
    iso_countries: frozenset[str]
    merchants: Tuple[MerchantContext, ...]
    artefacts: ArtefactBundle

    def by_merchant(self) -> Mapping[int, MerchantContext]:
        """Return the merchant contexts keyed by merchant id."""

        return {merchant.merchant_id: merchant for merchant in self.merchants}


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _load_yaml_metadata(path: Path) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, Mapping):
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            f"policy artefact '{path}' must decode to a mapping",
        )
    return data


def _load_artefact_metadata(spec: ArtefactSpec, *, error_code: str) -> ArtefactMetadata:
    if not spec.path.exists() or not spec.path.is_file():
        raise err(error_code, f"artefact '{spec.path}' missing")
    semver = spec.semver
    version: str | None = None
    if spec.path.suffix.lower() in {".yaml", ".yml"}:
        mapping = _load_yaml_metadata(spec.path)
        if semver is None:
            raw_semver = mapping.get("semver")
            if raw_semver is not None and not isinstance(raw_semver, str):
                raise err(
                    "ERR_S3_RULE_LADDER_INVALID",
                    f"artefact '{spec.path}' semver must be string",
                )
            semver = raw_semver
        raw_version = mapping.get("version")
        if raw_version is not None and not isinstance(raw_version, str):
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"artefact '{spec.path}' version must be string",
            )
        version = raw_version
    digest = _hash_file(spec.path)
    return ArtefactMetadata(
        artefact_id=spec.artefact_id,
        semver=semver,
        version=version,
        sha256=digest,
    )


def _decision_map(decisions: Sequence[HurdleDecision]) -> Dict[int, HurdleDecision]:
    mapping: Dict[int, HurdleDecision] = {}
    for decision in decisions:
        merchant_id = int(decision.merchant_id)
        if merchant_id in mapping:
            raise err(
                "ERR_S3_PRECONDITION",
                f"duplicate hurdle decision for merchant {merchant_id}",
            )
        mapping[merchant_id] = decision
    return mapping


def _nb_final_map(finals: Sequence[NBFinalRecord]) -> Dict[int, NBFinalRecord]:
    mapping: Dict[int, NBFinalRecord] = {}
    for record in finals:
        merchant_id = int(record.merchant_id)
        if merchant_id in mapping:
            raise err(
                "ERR_S3_PRECONDITION",
                f"duplicate nb_final record for merchant {merchant_id}",
            )
        mapping[merchant_id] = record
    return mapping


def _merchant_map(profiles: Sequence[MerchantProfile]) -> Dict[int, MerchantProfile]:
    mapping: Dict[int, MerchantProfile] = {}
    for profile in profiles:
        merchant_id = int(profile.merchant_id)
        if merchant_id in mapping:
            raise err(
                "ERR_S3_PRECONDITION",
                f"duplicate merchant profile for merchant {merchant_id}",
            )
        mapping[merchant_id] = profile
    return mapping


def build_deterministic_context(
    *,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
    seed: int,
    merchant_profiles: Sequence[MerchantProfile],
    decisions: Sequence[HurdleDecision],
    nb_finals: Sequence[NBFinalRecord],
    iso_countries: Iterable[str],
    rule_ladder_spec: ArtefactSpec,
    iso_countries_spec: ArtefactSpec,
    currency_to_country_spec: ArtefactSpec | None = None,
    base_weight_spec: ArtefactSpec | None = None,
    thresholds_spec: ArtefactSpec | None = None,
    bounds_spec: ArtefactSpec | None = None,
) -> S3DeterministicContext:
    """Assemble the deterministic S3 context following the S3.0 specification."""

    if not parameter_hash or not manifest_fingerprint:
        raise err("ERR_S3_PRECONDITION", "parameter hash and manifest fingerprint required")

    iso_set = frozenset(code.upper() for code in iso_countries)
    merchant_lookup = _merchant_map(merchant_profiles)
    decision_lookup = _decision_map(decisions)
    final_lookup = _nb_final_map(nb_finals)

    merchants: list[MerchantContext] = []
    for merchant_id, profile in sorted(merchant_lookup.items()):
        decision = decision_lookup.get(merchant_id)
        if decision is None:
            raise err(
                "ERR_S3_PRECONDITION",
                f"hurdle decision missing for merchant {merchant_id}",
            )
        if not decision.is_multi:
            raise err(
                "ERR_S3_PRECONDITION",
                f"merchant {merchant_id} is not multi-site per hurdle outcome",
            )

        final = final_lookup.get(merchant_id)
        if final is None:
            raise err(
                "ERR_S3_PRECONDITION",
                f"nb_final missing for merchant {merchant_id}",
            )
        if final.n_outlets < 2:
            raise err(
                "ERR_S3_PRECONDITION",
                f"merchant {merchant_id} nb_final.n_outlets must be >= 2",
            )

        home_iso = profile.home_country_iso.upper()
        if home_iso not in iso_set:
            raise err(
                "ERR_S3_VOCAB_INVALID",
                f"home_country_iso '{home_iso}' not present in ISO set",
            )
        channel = profile.channel.upper()
        if channel not in _ALLOWED_CHANNELS:
            raise err(
                "ERR_S3_VOCAB_INVALID",
                f"channel '{profile.channel}' not in closed vocabulary {_ALLOWED_CHANNELS}",
            )

        merchants.append(
            MerchantContext(
                merchant_id=merchant_id,
                home_country_iso=home_iso,
                mcc=str(profile.mcc),
                channel=channel,
                n_outlets=int(final.n_outlets),
            )
        )

    if not merchants:
        raise err("ERR_S3_PRECONDITION", "no admissible merchants for S3")

    artefacts_rule_ladder = _load_artefact_metadata(
        rule_ladder_spec, error_code="ERR_S3_AUTHORITY_MISSING"
    )
    artefacts_iso = _load_artefact_metadata(
        iso_countries_spec, error_code="ERR_S3_AUTHORITY_MISSING"
    )

    artefacts_currency = (
        _load_artefact_metadata(
            currency_to_country_spec, error_code="ERR_S3_AUTHORITY_MISSING"
        )
        if currency_to_country_spec is not None
        else None
    )
    artefacts_base_weight = (
        _load_artefact_metadata(
            base_weight_spec, error_code="ERR_S3_AUTHORITY_MISSING"
        )
        if base_weight_spec is not None
        else None
    )
    artefacts_thresholds = (
        _load_artefact_metadata(
            thresholds_spec, error_code="ERR_S3_AUTHORITY_MISSING"
        )
        if thresholds_spec is not None
        else None
    )
    artefacts_bounds = (
        _load_artefact_metadata(
            bounds_spec, error_code="ERR_S3_AUTHORITY_MISSING"
        )
        if bounds_spec is not None
        else None
    )

    artefacts = ArtefactBundle(
        rule_ladder=artefacts_rule_ladder,
        iso_countries=artefacts_iso,
        currency_to_country=artefacts_currency,
        base_weight=artefacts_base_weight,
        thresholds=artefacts_thresholds,
        bounds=artefacts_bounds,
    )

    return S3DeterministicContext(
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        run_id=str(run_id),
        seed=int(seed),
        iso_countries=iso_set,
        merchants=tuple(merchants),
        artefacts=artefacts,
    )


__all__ = [
    "ArtefactBundle",
    "ArtefactMetadata",
    "ArtefactSpec",
    "MerchantContext",
    "MerchantProfile",
    "S3DeterministicContext",
    "build_deterministic_context",
]
