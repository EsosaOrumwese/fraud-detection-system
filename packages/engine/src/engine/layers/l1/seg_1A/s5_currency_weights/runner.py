"""Orchestrator for state-5 currency→country weights (L2 layer)."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence, Tuple

from ..s0_foundations.exceptions import err
from ..shared.dictionary import load_dictionary, resolve_dataset_path
from .builder import CurrencyResult, build_weights
from .contexts import S5DeterministicContext, S5PolicyMetadata
from .loader import (
    LegalTender,
    ShareLoader,
    ShareSurface,
    load_ccy_country_shares,
    load_iso_legal_tender,
    load_settlement_shares,
)
from .merchant_currency import MerchantCurrencyRecord, derive_merchant_currency
from .persist import (
    PersistConfig,
    write_ccy_country_weights,
    write_merchant_currency,
    write_sparse_flag,
)
from .policy import PolicyValidationError, SmoothingPolicy, load_policy


@dataclass(frozen=True)
class S5RunOutputs:
    """Materialised artefacts emitted by the S5 runner."""

    deterministic: S5DeterministicContext
    policy: S5PolicyMetadata
    smoothing_policy: SmoothingPolicy
    weights_path: Path
    sparse_flag_path: Path | None = None
    receipt_path: Path | None = None
    merchant_currency_path: Path | None = None


class S5CurrencyWeightsRunner:
    """Execute the S5 pipeline (policy→weights cache→receipts)."""

    def run(
        self,
        *,
        base_path: Path,
        deterministic: S5DeterministicContext,
        emit_sparse_flag: bool = True,
        share_loader: ShareLoader | None = None,
        iso_legal_tender: Sequence[LegalTender] | None = None,
    ) -> S5RunOutputs:
        """Run state-5 using deterministic context information."""

        base_path = base_path.expanduser().resolve()
        dictionary = load_dictionary()
        policy, policy_metadata = self._resolve_policy(deterministic.policy_path)
        settlements = self._load_settlement_shares(
            deterministic, share_loader=share_loader
        )  # noqa: F841 -- placeholder for future merchant-currency support
        ccy_shares = self._load_ccy_shares(deterministic, share_loader=share_loader)
        iso_lookup = list(
            iso_legal_tender
            if iso_legal_tender is not None
            else self._load_iso_legal_tender(deterministic)
        )

        legal_tender_map = {
            entry.country_iso.upper(): entry.primary_ccy.upper()
            for entry in iso_lookup
        }
        merchant_records: Tuple[MerchantCurrencyRecord, ...] | None = None
        if deterministic.merchants:
            has_share_vector = any(
                bool(merchant.share_vector) for merchant in deterministic.merchants
            )
            if legal_tender_map or has_share_vector:
                merchant_records = derive_merchant_currency(
                    deterministic.merchants,
                    legal_tender_map,
                )

        self._preflight_surface_checks(
            settlement_shares=settlements,
            ccy_shares=ccy_shares,
            iso_lookup=iso_lookup,
        )

        results = build_weights(
            settlement_shares=settlements,
            ccy_shares=ccy_shares,
            policy=policy,
        )

        staging_root = self._create_staging_dir(base_path)
        config = PersistConfig(
            parameter_hash=deterministic.parameter_hash,
            output_dir=staging_root,
            emit_validation=True,
            emit_sparse_flag=emit_sparse_flag,
        )
        weights_staging_path = write_ccy_country_weights(results, config=config)
        sparse_staging_path: Path | None = None
        if emit_sparse_flag:
            sparse_staging_path = staging_root / "sparse_flag" / f"parameter_hash={deterministic.parameter_hash}"
        weights_final_path = self._publish_partition(
            base_path=base_path,
            dataset_id="ccy_country_weights_cache",
            partition_dir=weights_staging_path.parent,
            dictionary=dictionary,
            template_args={"parameter_hash": deterministic.parameter_hash},
        )
        sparse_final_path: Path | None = None
        if emit_sparse_flag and sparse_staging_path is not None and sparse_staging_path.exists():
            sparse_final_path = self._publish_partition(
                base_path=base_path,
                dataset_id="sparse_flag",
                partition_dir=sparse_staging_path,
                dictionary=dictionary,
                template_args={"parameter_hash": deterministic.parameter_hash},
            )

        merchant_final_path: Path | None = None
        if merchant_records:
            if len(merchant_records) != len(deterministic.merchants):
                raise err(
                    "E_MCURR_CARDINALITY",
                    (
                        "merchant_currency rows do not match merchant universe "
                        f"(expected {len(deterministic.merchants)}, "
                        f"produced {len(merchant_records)})"
                    ),
                )
            merchant_staging_path = write_merchant_currency(
                merchant_records,
                config=config,
            )
            merchant_final_path = self._publish_partition(
                base_path=base_path,
                dataset_id="merchant_currency",
                partition_dir=merchant_staging_path.parent,
                dictionary=dictionary,
                template_args={"parameter_hash": deterministic.parameter_hash},
            )

        receipt_path = weights_final_path.parent / "S5_VALIDATION.json"

        self._cleanup_staging(staging_root)

        return S5RunOutputs(
            deterministic=deterministic,
            policy=policy_metadata,
            smoothing_policy=policy,
            weights_path=weights_final_path,
            sparse_flag_path=sparse_final_path,
            receipt_path=receipt_path,
            merchant_currency_path=merchant_final_path,
        )

    # --------------------------------------------------------------------- #
    # Internal helpers

    def _resolve_policy(
        self, policy_path: Path
    ) -> tuple[SmoothingPolicy, S5PolicyMetadata]:
        try:
            policy = load_policy(policy_path)
        except PolicyValidationError as exc:  # pragma: no cover - raised from helper
            raise err(
                "E_POLICY_DOMAIN",
                f"S5 policy failed validation at '{policy_path}': {exc}",
            ) from exc
        digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
        metadata = S5PolicyMetadata(
            path=policy_path.expanduser().resolve(),
            digest_hex=digest,
            version=policy.version,
            semver=policy.semver,
        )
        return policy, metadata

    def _load_settlement_shares(
        self,
        deterministic: S5DeterministicContext,
        *,
        share_loader: ShareLoader | None = None,
    ) -> Sequence[ShareSurface]:
        if share_loader is not None:
            return share_loader.load_settlement_shares()
        return load_settlement_shares(deterministic.settlement_shares_path)

    def _load_ccy_shares(
        self,
        deterministic: S5DeterministicContext,
        *,
        share_loader: ShareLoader | None = None,
    ) -> Sequence[ShareSurface]:
        if share_loader is not None:
            return share_loader.load_ccy_country_shares()
        return load_ccy_country_shares(deterministic.ccy_country_shares_path)

    def _load_iso_legal_tender(
        self, deterministic: S5DeterministicContext
    ) -> Sequence[LegalTender]:
        if deterministic.iso_legal_tender_path is None:
            return []
        return load_iso_legal_tender(deterministic.iso_legal_tender_path)

    def _preflight_surface_checks(
        self,
        *,
        settlement_shares: Sequence[ShareSurface],
        ccy_shares: Sequence[ShareSurface],
        iso_lookup: Sequence[LegalTender],
        tolerance: float = 1e-6,
    ) -> None:
        iso_codes = {item.country_iso for item in iso_lookup} if iso_lookup else None
        self._validate_surface(
            settlement_shares,
            tolerance=tolerance,
            iso_codes=iso_codes,
        )
        self._validate_surface(
            ccy_shares,
            tolerance=tolerance,
            iso_codes=iso_codes,
        )

    def _validate_surface(
        self,
        shares: Sequence[ShareSurface],
        *,
        tolerance: float,
        iso_codes: Iterable[str] | None,
    ) -> None:
        seen_keys: set[tuple[str, str]] = set()
        iso_set = set(iso_codes) if iso_codes is not None else None
        grouped: dict[str, float] = {}
        for row in shares:
            if (row.currency, row.country_iso) in seen_keys:
                raise err(
                    "E_INPUT_SCHEMA",
                    f"duplicate share row detected for ({row.currency}, {row.country_iso})",
                )
            seen_keys.add((row.currency, row.country_iso))
            if iso_set is not None and row.country_iso not in iso_set:
                raise err(
                    "E_INPUT_SCHEMA",
                    f"share surface references unknown ISO '{row.country_iso}'",
                )
            if row.share < -tolerance or row.share > 1.0 + tolerance:
                raise err(
                    "E_INPUT_SCHEMA",
                    f"share for ({row.currency}, {row.country_iso}) outside [0,1]",
                )
            if row.obs_count < 0:
                raise err(
                    "E_INPUT_SCHEMA",
                    f"obs_count for ({row.currency}, {row.country_iso}) negative",
                )
            grouped.setdefault(row.currency, 0.0)
            grouped[row.currency] += row.share

        for currency, total in grouped.items():
            if abs(total - 1.0) > tolerance:
                raise err(
                    "E_INPUT_SUM",
                    f"share surface for {currency} sums to {total}, outside tolerance ±{tolerance}",
                )

    def _create_staging_dir(self, base_path: Path) -> Path:
        staging_root = base_path / "tmp" / f"s5_{uuid.uuid4().hex}"
        staging_root.mkdir(parents=True, exist_ok=False)
        return staging_root

    def _publish_partition(
        self,
        *,
        base_path: Path,
        dataset_id: str,
        partition_dir: Path,
        dictionary: Mapping[str, object],
        template_args: Mapping[str, object],
    ) -> Path:
        final_file = resolve_dataset_path(
            dataset_id,
            base_path=base_path,
            template_args=template_args,
            dictionary=dictionary,
        )
        final_dir = final_file.parent
        if final_dir.exists():
            raise err(
                "E_PARTITION_EXISTS",
                f"S5 output partition already present for dataset '{dataset_id}' at '{final_dir}'",
            )
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(partition_dir), str(final_dir))
        return final_file

    def _cleanup_staging(self, staging_root: Path) -> None:
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)


__all__ = [
    "S5CurrencyWeightsRunner",
    "S5RunOutputs",
]
