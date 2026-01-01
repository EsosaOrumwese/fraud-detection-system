"""Data loading utilities for S6 foreign-set selection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Sequence
import logging

import pandas as pd

from ..shared.dictionary import load_dictionary, resolve_dataset_path
from ..shared.passed_flag import parse_passed_flag
from .contexts import S6DeterministicContext
from .types import CandidateInput, MerchantSelectionInput

__all__ = [
    "S6LoaderError",
    "load_deterministic_context",
    "verify_s5_pass",
]


logger = logging.getLogger(__name__)


class S6LoaderError(RuntimeError):
    """Raised when upstream artefacts required by S6 cannot be loaded."""


@dataclass(frozen=True)
class _Surfaces:
    candidates: pd.DataFrame
    weights: pd.DataFrame
    merchant_currency: pd.DataFrame
    k_targets: Mapping[int, int]
    eligibility: Mapping[int, bool]


def load_deterministic_context(
    *,
    base_path: Path,
    parameter_hash: str,
    seed: int,
    run_id: str,
    manifest_fingerprint: str,
    policy_path: Path,
) -> S6DeterministicContext:
    """Load governed artefacts required to execute S6."""

    base_path = Path(base_path).expanduser().resolve()
    policy_path = Path(policy_path).expanduser().resolve()
    dictionary = load_dictionary()
    surfaces = _load_surfaces(
        base_path=base_path,
        parameter_hash=parameter_hash,
        seed=seed,
        run_id=run_id,
        dictionary=dictionary,
    )
    merchants = _build_selection_inputs(
        surfaces=surfaces,
        parameter_hash=parameter_hash,
    )

    return S6DeterministicContext(
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        seed=seed,
        run_id=run_id,
        merchants=tuple(merchants),
        policy_path=policy_path,
    )


def _load_surfaces(
    *,
    base_path: Path,
    parameter_hash: str,
    seed: int,
    run_id: str,
    dictionary: Mapping[str, object],
) -> _Surfaces:
    candidate_path = resolve_dataset_path(
        "s3_candidate_set",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    weight_path = resolve_dataset_path(
        "ccy_country_weights_cache",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    merchant_currency_path = resolve_dataset_path(
        "merchant_currency",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    k_target_path = resolve_dataset_path(
        "rng_event_ztp_final",
        base_path=base_path,
        template_args={
            "seed": seed,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )
    eligibility_path = resolve_dataset_path(
        "crossborder_eligibility_flags",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )

    verify_s5_pass(weight_path.parent)

    try:
        candidate_frame = pd.read_parquet(
            candidate_path,
            columns=[
                "merchant_id",
                "country_iso",
                "candidate_rank",
                "is_home",
            ],
        )
    except FileNotFoundError as exc:
        raise S6LoaderError(f"s3_candidate_set missing at {candidate_path}") from exc

    try:
        weight_frame = pd.read_parquet(
            weight_path,
            columns=[
                "currency",
                "country_iso",
                "weight",
            ],
        )
    except FileNotFoundError as exc:
        raise S6LoaderError(f"S5 weights cache missing at {weight_path}") from exc

    try:
        merchant_currency_frame = pd.read_parquet(
            merchant_currency_path,
            columns=[
                "merchant_id",
                "kappa",
            ],
        )
    except FileNotFoundError as exc:
        raise S6LoaderError(
            "merchant_currency cache is required for S6 but was not found "
            f"at {merchant_currency_path}"
        ) from exc

    try:
        eligibility_frame = pd.read_parquet(
            eligibility_path,
            columns=[
                "merchant_id",
                "is_eligible",
            ],
        )
    except FileNotFoundError as exc:
        raise S6LoaderError(
            "crossborder_eligibility_flags required by S6 not found "
            f"at {eligibility_path}"
        ) from exc

    k_targets = _load_k_targets(k_target_path)
    return _Surfaces(
        candidates=candidate_frame,
        weights=weight_frame,
        merchant_currency=merchant_currency_frame,
        k_targets=k_targets,
        eligibility=_load_eligibility_map(eligibility_frame),
    )


def verify_s5_pass(partition_dir: Path) -> None:
    """Ensure S5 PASS receipt is present and valid before S6 reads weights."""

    receipt_path = partition_dir / "S5_VALIDATION.json"
    flag_path = partition_dir / "_passed.flag"

    if not receipt_path.exists() or not flag_path.exists():
        raise S6LoaderError(
            "S5 PASS receipt missing; expected S5_VALIDATION.json and _passed.flag "
            f"under {partition_dir}"
        )

    receipt_text = receipt_path.read_text(encoding="utf-8")
    expected_digest = hashlib.sha256(receipt_text.encode("utf-8")).hexdigest()
    try:
        actual_digest = parse_passed_flag(flag_path.read_text(encoding="ascii"))
    except ValueError as exc:
        raise S6LoaderError(f"s5 _passed.flag malformed at {flag_path}") from exc
    if actual_digest != expected_digest:
        raise S6LoaderError(
            "S5 PASS receipt hash mismatch; refusing to read weights "
            f"(expected {expected_digest}, found {actual_digest})"
        )


def _load_k_targets(path: Path) -> Mapping[int, int]:
    if not path.exists():
        raise S6LoaderError(f"rng_event_ztp_final log missing at {path}")
    mapping: Dict[int, int] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            merchant_id = int(record["merchant_id"])
            if merchant_id in mapping:
                raise S6LoaderError(
                    f"duplicate rng_event_ztp_final entries for merchant {merchant_id}"
                )
            mapping[merchant_id] = int(record.get("K_target", 0))
    return mapping


def _build_selection_inputs(
    *,
    surfaces: _Surfaces,
    parameter_hash: str,
) -> Sequence[MerchantSelectionInput]:
    weights_by_currency = _group_weights(surfaces.weights)
    currency_by_merchant = _currency_lookup(surfaces.merchant_currency)
    k_targets = surfaces.k_targets
    eligibility_map = surfaces.eligibility

    merchants: list[MerchantSelectionInput] = []
    missing_k_targets: list[int] = []
    grouped = surfaces.candidates.groupby("merchant_id", sort=False)
    for merchant_id, frame in grouped:
        merchant_id_int = int(merchant_id)
        eligible = eligibility_map.get(merchant_id_int, True)
        if eligible is False:
            k_target_value = 0
            frame_effective = frame[frame["is_home"] == True]
        else:
            k_target_value = k_targets.get(merchant_id_int)
            if k_target_value is None:
                missing_k_targets.append(merchant_id_int)
                k_target_value = 0
                frame_effective = frame[frame["is_home"] == True]
            else:
                frame_effective = frame
        if frame_effective.empty:
            missing_k_targets.append(merchant_id_int)
            continue
        currency = currency_by_merchant.get(merchant_id_int)
        if currency is None:
            raise S6LoaderError(
                f"settlement currency missing for merchant {merchant_id_int}"
            )
        weight_map = weights_by_currency.get(currency)
        if weight_map is None:
            raise S6LoaderError(
                f"currency '{currency}' absent from S5 weights cache "
                f"(merchant {merchant_id_int})"
            )

        candidates: list[CandidateInput] = []
        for row in frame_effective.itertuples(index=False):
            country_iso = str(row.country_iso).upper()
            candidate_rank = int(row.candidate_rank)
            is_home = bool(row.is_home)
            try:
                weight_value = float(weight_map[country_iso])
            except KeyError as exc:
                raise S6LoaderError(
                    "candidate country missing from S5 weights cache "
                    f"(merchant={merchant_id_int}, currency={currency}, "
                    f"country={country_iso})"
                ) from exc
            candidates.append(
                CandidateInput(
                    merchant_id=merchant_id_int,
                    country_iso=country_iso,
                    candidate_rank=candidate_rank,
                    weight=weight_value,
                    is_home=is_home,
                )
            )

        merchants.append(
            MerchantSelectionInput(
                merchant_id=merchant_id_int,
                settlement_currency=currency,
                k_target=int(k_target_value),
                candidates=tuple(
                    sorted(candidates, key=lambda item: item.candidate_rank)
                ),
            )
        )

    if missing_k_targets:
        sample = ", ".join(str(mid) for mid in missing_k_targets[:5])
        logger.warning(
            "S6 loader skipping %d merchants missing rng_event_ztp_final entries "
            "(parameter_hash=%s): %s%s",
            len(missing_k_targets),
            parameter_hash,
            sample,
            "..." if len(missing_k_targets) > 5 else "",
        )

    if not merchants:
        raise S6LoaderError(
            f"no merchants discovered for parameter_hash={parameter_hash}"
        )
    return merchants


def _group_weights(frame: pd.DataFrame) -> Mapping[str, Mapping[str, float]]:
    grouped: MutableMapping[str, Dict[str, float]] = {}
    for row in frame.itertuples(index=False):
        currency = str(row.currency).upper()
        country_iso = str(row.country_iso).upper()
        weight = float(row.weight)
        grouped.setdefault(currency, {})[country_iso] = weight
    return grouped


def _currency_lookup(frame: pd.DataFrame) -> Mapping[int, str]:
    mapping: Dict[int, str] = {}
    for row in frame.itertuples(index=False):
        merchant_id = int(row.merchant_id)
        kappa = str(row.kappa).upper()
        mapping[merchant_id] = kappa
    return mapping


def _load_eligibility_map(frame: pd.DataFrame) -> Mapping[int, bool]:
    mapping: Dict[int, bool] = {}
    for row in frame.itertuples(index=False):
        merchant_id = int(row.merchant_id)
        mapping[merchant_id] = bool(row.is_eligible)
    return mapping
