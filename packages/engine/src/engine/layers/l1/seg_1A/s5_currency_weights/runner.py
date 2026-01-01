"""Orchestrator for state-5 currency→country weights (L2 layer)."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from ..s0_foundations.exceptions import err
from ..shared.dictionary import load_dictionary, resolve_dataset_path
from .builder import CurrencyResult, build_weights
from .contexts import MerchantCurrencyInput, S5DeterministicContext, S5PolicyMetadata
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
    build_receipt_payload,
    write_ccy_country_weights,
    write_merchant_currency,
    write_sparse_flag,
    write_validation_receipt,
)
from .policy import PolicyValidationError, SmoothingPolicy, load_policy


logger = logging.getLogger(__name__)

SCHEMA_REFS = {
    "settlement_shares": "schemas.ingress.layer1.yaml#/settlement_shares",
    "ccy_country_shares": "schemas.ingress.layer1.yaml#/ccy_country_shares",
    "ccy_country_weights_cache": "schemas.1A.yaml#/prep/ccy_country_weights_cache",
}


@dataclass(frozen=True)
class S5RunOutputs:
    """Materialised artefacts emitted by the S5 runner."""

    deterministic: S5DeterministicContext
    policy: S5PolicyMetadata
    smoothing_policy: SmoothingPolicy
    weights_path: Path
    metrics: Mapping[str, object]
    per_currency_metrics: Tuple[Mapping[str, object], ...]
    sparse_flag_path: Path | None = None
    receipt_path: Path | None = None
    merchant_currency_path: Path | None = None
    stage_log_path: Path | None = None


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
        rng_before = self._snapshot_rng_totals(base_path, deterministic)
        policy, policy_metadata = self._resolve_policy(deterministic.policy_path)
        stage_log_file = self._stage_log_file_path(base_path, deterministic)
        self._log_stage(
            "N0",
            "POLICY_RESOLVED",
            "policy resolved",
            parameter_hash=deterministic.parameter_hash,
            seed=deterministic.seed,
            policy_path=str(policy_metadata.path),
            policy_digest=policy_metadata.digest_hex,
            run_id=deterministic.run_id,
            log_file=stage_log_file,
        )
        settlements = self._load_settlement_shares(
            deterministic, share_loader=share_loader
        )
        ccy_shares = self._load_ccy_shares(deterministic, share_loader=share_loader)
        iso_lookup = list(
            iso_legal_tender
            if iso_legal_tender is not None
            else self._load_iso_legal_tender(deterministic)
        )

        self._preflight_surface_checks(
            settlement_shares=settlements,
            ccy_shares=ccy_shares,
            iso_lookup=iso_lookup,
            merchants=deterministic.merchants,
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
        currencies_total_inputs = len(
            {row.currency for row in settlements} | {row.currency for row in ccy_shares}
        )
        self._log_stage(
            "N1",
            "INPUTS_VALIDATED",
            "inputs validated",
            parameter_hash=deterministic.parameter_hash,
            seed=deterministic.seed,
            currencies_total=currencies_total_inputs,
            settlement_currencies=len({row.currency for row in settlements}),
            ccy_currencies=len({row.currency for row in ccy_shares}),
            run_id=deterministic.run_id,
            log_file=stage_log_file,
        )

        results = build_weights(
            settlement_shares=settlements,
            ccy_shares=ccy_shares,
            policy=policy,
        )
        results = list(results)
        currencies_processed = len(results)
        rows_written = sum(len(result.weights) for result in results)
        degrade_summary = self._summarise_degrade(results)
        self._log_stage(
            "N2",
            "WEIGHTS_BUILT",
            "weights built",
            parameter_hash=deterministic.parameter_hash,
            seed=deterministic.seed,
            currencies_processed=currencies_processed,
            rows_written=rows_written,
            degrade_summary=degrade_summary,
            run_id=deterministic.run_id,
            log_file=stage_log_file,
        )

        staging_root = self._create_staging_dir(base_path)
        config = PersistConfig(
            parameter_hash=deterministic.parameter_hash,
            output_dir=staging_root,
            emit_validation=False,
            emit_sparse_flag=emit_sparse_flag,
        )
        weights_staging_path = write_ccy_country_weights(results, config=config)
        sparse_staging_path: Path | None = None
        if emit_sparse_flag:
            sparse_staging_path = staging_root / "sparse_flag" / f"parameter_hash={deterministic.parameter_hash}"
        merchant_staging_path: Path | None = None
        if merchant_records:
            merchant_staging_path = write_merchant_currency(
                merchant_records,
                config=config,
            )

        rng_after = self._snapshot_rng_totals(base_path, deterministic)
        receipt_payload = build_receipt_payload(
            results=results,
            parameter_hash=deterministic.parameter_hash,
            policy_metadata=policy_metadata,
            schema_refs=SCHEMA_REFS,
            rng_before=rng_before,
            rng_after=rng_after,
            currencies_total_inputs=currencies_total_inputs,
        )
        run_metrics = {
            key: value
            for key, value in receipt_payload.items()
            if key not in {"by_currency", "currencies"}
        }
        per_currency_metrics = tuple(
            dict(entry) for entry in receipt_payload.get("by_currency", [])
        )
        if (
            receipt_payload.get("rng_trace_delta_events") != 0
            or receipt_payload.get("rng_trace_delta_draws") != 0
        ):
            raise err(
                "E_RNG_INTERACTION",
                "S5 detected RNG interaction (delta events/draws not zero)",
            )
        write_validation_receipt(
            payload=receipt_payload,
            config=config,
            target_dir=weights_staging_path.parent,
        )
        self._log_stage(
            "N3",
            "RECEIPT_STAGED",
            "validation receipt staged",
            parameter_hash=deterministic.parameter_hash,
            seed=deterministic.seed,
            currencies_processed=currencies_processed,
            run_id=deterministic.run_id,
            log_file=stage_log_file,
        )

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
        if merchant_records and merchant_staging_path is not None:
            merchant_final_path = self._publish_partition(
                base_path=base_path,
                dataset_id="merchant_currency",
                partition_dir=merchant_staging_path.parent,
                dictionary=dictionary,
                template_args={"parameter_hash": deterministic.parameter_hash},
            )
            self._log_stage(
                "N2b",
                "MERCHANT_CURRENCY_DERIVED",
                "merchant currency derived",
                parameter_hash=deterministic.parameter_hash,
                seed=deterministic.seed,
                merchant_rows=len(merchant_records),
                run_id=deterministic.run_id,
                log_file=stage_log_file,
            )

        receipt_path = weights_final_path.parent / "S5_VALIDATION.json"
        self._log_stage(
            "N4",
            "PUBLISH_COMPLETE",
            "publish complete",
            parameter_hash=deterministic.parameter_hash,
            seed=deterministic.seed,
            weights_path=str(weights_final_path),
            receipt_path=str(receipt_path),
            run_id=deterministic.run_id,
            log_file=stage_log_file,
        )

        self._cleanup_staging(staging_root)

        return S5RunOutputs(
            deterministic=deterministic,
            policy=policy_metadata,
            smoothing_policy=policy,
            weights_path=weights_final_path,
            metrics=run_metrics,
            per_currency_metrics=per_currency_metrics,
            sparse_flag_path=sparse_final_path,
            receipt_path=receipt_path,
            merchant_currency_path=merchant_final_path,
            stage_log_path=stage_log_file,
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
        merchants: Sequence[MerchantCurrencyInput],
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
        if not merchants:
            return

        iso_currency_map: dict[str, str] = {
            item.country_iso.upper(): item.primary_ccy.upper()
            for item in iso_lookup
            if item.country_iso and item.primary_ccy
        }
        self._assert_currency_coverage(
            merchants=merchants,
            settlement_shares=settlement_shares,
            ccy_shares=ccy_shares,
            iso_currency_map=iso_currency_map,
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

    def _assert_currency_coverage(
        self,
        *,
        merchants: Sequence[MerchantCurrencyInput],
        settlement_shares: Sequence[ShareSurface],
        ccy_shares: Sequence[ShareSurface],
        iso_currency_map: Mapping[str, str],
    ) -> None:
        required_currencies: set[str] = set()
        missing_iso_metadata: set[str] = set()
        for merchant in merchants:
            iso = str(merchant.home_country_iso).upper()
            share_vector = merchant.share_vector or {}
            if share_vector:
                for currency in share_vector.keys():
                    if currency is None:
                        continue
                    required_currencies.add(str(currency).upper())
                continue
            currency = iso_currency_map.get(iso)
            if currency:
                required_currencies.add(currency.upper())
            else:
                missing_iso_metadata.add(iso)
        if missing_iso_metadata:
            raise err(
                "E_INPUT_CURRENCY_COVERAGE",
                f"legal tender mapping missing entries for ISO codes {sorted(missing_iso_metadata)}",
            )
        if not required_currencies:
            return
        available_currencies = {
            row.currency.upper() for row in settlement_shares
        } | {
            row.currency.upper() for row in ccy_shares
        }
        missing_currencies = sorted(required_currencies - available_currencies)
        if missing_currencies:
            raise err(
                "E_INPUT_CURRENCY_COVERAGE",
                (
                    "currency weights required for merchants but not present "
                    f"in share surfaces: {missing_currencies}"
                ),
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

    def _stage_log_file_path(
        self,
        base_path: Path,
        deterministic: S5DeterministicContext,
    ) -> Path:
        return (
            base_path
            / "logs"
            / "stages"
            / "s5_currency_weights"
            / f"parameter_hash={deterministic.parameter_hash}"
            / f"run_id={deterministic.run_id}"
            / "S5_STAGES.jsonl"
        )

    def _snapshot_rng_totals(
        self,
        base_path: Path,
        deterministic: S5DeterministicContext,
    ) -> Dict[str, int]:
        rng_root = (base_path / "logs" / "rng").resolve()
        totals: Dict[str, int] = {"events_total": 0, "draws_total": 0, "blocks_total": 0}
        trace_dir = (
            rng_root
            / "trace"
            / f"seed={deterministic.seed}"
            / f"parameter_hash={deterministic.parameter_hash}"
            / f"run_id={deterministic.run_id}"
        )
        trace_file = trace_dir / "rng_trace_log.jsonl"
        summary_file = trace_dir / "rng_totals.json"
        try:
            if summary_file.exists():
                summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
                if isinstance(summary_data, Mapping):
                    return {
                        "events_total": int(summary_data.get("events_total", 0) or 0),
                        "draws_total": int(summary_data.get("draws_total", 0) or 0),
                        "blocks_total": int(summary_data.get("blocks_total", 0) or 0),
                    }
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            pass

        block_totals: Dict[Tuple[str | None, str | None], int] = {}
        if trace_file.exists():
            with trace_file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    key = (record.get("module"), record.get("substream_label"))
                    block_totals[key] = int(record.get("blocks_total", 0))
        totals["blocks_total"] = sum(block_totals.values())

        events_root = rng_root / "events"
        if events_root.exists():
            pattern = events_root.glob(
                f"**/seed={deterministic.seed}/parameter_hash={deterministic.parameter_hash}/run_id={deterministic.run_id}/part-*.jsonl"
            )
            events_total = 0
            draws_total = 0
            for file_path in pattern:
                try:
                    with file_path.open("r", encoding="utf-8") as handle:
                        for line in handle:
                            try:
                                record = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            events_total += 1
                            try:
                                draws_total += int(record.get("draws", 0))
                            except (TypeError, ValueError):
                                continue
                except FileNotFoundError:
                    continue
            totals["events_total"] = events_total
            totals["draws_total"] = draws_total
        summary_payload = {
            "seed": deterministic.seed,
            "parameter_hash": deterministic.parameter_hash,
            "run_id": deterministic.run_id,
            "events_total": totals["events_total"],
            "draws_total": totals["draws_total"],
            "blocks_total": totals["blocks_total"],
        }
        try:
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text(json.dumps(summary_payload, sort_keys=True), encoding="utf-8")
        except OSError:
            pass
        return totals

    def _log_stage(
        self,
        stage: str,
        event: str,
        message: str,
        *,
        log_file: Path,
        level: str = "INFO",
        **fields: object,
    ) -> None:
        level_upper = level.upper()
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "level": level_upper,
            "component": "1A.expand_currency_to_country",
            "stage": stage,
            "event": event,
            "message": message,
        }
        record.update(fields)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")
        if level_upper == "ERROR":
            log_fn = logger.error
        elif level_upper in {"WARN", "WARNING"}:
            log_fn = logger.warning
        else:
            log_fn = logger.info
        log_fn(json.dumps(record, sort_keys=True))

    @staticmethod
    def _summarise_degrade(results: Sequence[CurrencyResult]) -> Dict[str, int]:
        summary: Dict[str, int] = {"none": 0, "settlement_only": 0, "ccy_only": 0}
        for result in results:
            mode = result.degrade_mode
            summary.setdefault(mode, 0)
            summary[mode] += 1
        return summary


__all__ = [
    "S5CurrencyWeightsRunner",
    "S5RunOutputs",
]
