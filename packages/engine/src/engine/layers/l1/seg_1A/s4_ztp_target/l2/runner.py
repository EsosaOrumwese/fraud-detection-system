"""Orchestrator for the S4 Zero-Truncated Poisson target sampler."""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Tuple

from ...s0_foundations.exceptions import err
from ...s0_foundations.l1.rng import PhiloxEngine
from ...shared.dictionary import load_dictionary, resolve_rng_event_path
from ..contexts import S4DeterministicContext, S4MerchantTarget
from ..l0 import constants as c
from ..l0 import writer as l0_writer
from ..l1 import (
    SamplerOutcome,
    compute_lambda_regime,
    derive_poisson_substream,
    run_sampler,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ZTPFinalRecord:
    """Accepted outcome (or exhaustion marker) for a merchant."""

    merchant_id: int
    lambda_extra: float
    regime: str
    attempts: int
    rejections: int
    k_target: int | None
    exhausted: bool
    policy: str
    reason: str | None


@dataclass(frozen=True)
class S4RunResult:
    """Artifacts produced by the S4 sampler."""

    deterministic: S4DeterministicContext
    finals: Tuple[ZTPFinalRecord, ...]
    poisson_events_path: Path
    rejection_events_path: Path
    retry_exhausted_events_path: Path
    final_events_path: Path
    trace_path: Path


def _event_path(
    base_path: Path,
    stream: str,
    *,
    deterministic: S4DeterministicContext,
    dictionary: Mapping[str, object],
) -> Path:
    return resolve_rng_event_path(
        stream,
        base_path=base_path,
        seed=deterministic.seed,
        parameter_hash=deterministic.parameter_hash,
        run_id=deterministic.run_id,
        dictionary=dictionary,
    )


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _group_records(records: Iterable[dict]) -> MutableMapping[int, list[dict]]:
    grouped: MutableMapping[int, list[dict]] = defaultdict(list)
    for record in records:
        if record.get("module") != c.MODULE_NAME or record.get("context") != c.CONTEXT:
            continue
        grouped[int(record["merchant_id"])].append(record)
    return grouped


def _load_existing_outcomes(
    *,
    base_path: Path,
    deterministic: S4DeterministicContext,
) -> tuple[list[ZTPFinalRecord], set[int], set[int]]:
    dictionary = load_dictionary()
    attempts = _group_records(
        _load_jsonl(
            _event_path(
                base_path,
                c.STREAM_POISSON_COMPONENT,
                deterministic=deterministic,
                dictionary=dictionary,
            )
        )
    )
    rejections = _group_records(
        _load_jsonl(
            _event_path(
                base_path,
                c.STREAM_ZTP_REJECTION,
                deterministic=deterministic,
                dictionary=dictionary,
            )
        )
    )
    retries = _group_records(
        _load_jsonl(
            _event_path(
                base_path,
                c.STREAM_ZTP_RETRY_EXHAUSTED,
                deterministic=deterministic,
                dictionary=dictionary,
            )
        )
    )
    finals = _group_records(
        _load_jsonl(
            _event_path(
                base_path,
                c.STREAM_ZTP_FINAL,
                deterministic=deterministic,
                dictionary=dictionary,
            )
        )
    )

    resolved_merchants = set(finals.keys()) | set(retries.keys())
    partial_merchants = {
        merchant_id
        for merchant_id in (set(attempts.keys()) | set(rejections.keys()))
        if merchant_id not in resolved_merchants
    }

    existing_records: list[ZTPFinalRecord] = []
    if resolved_merchants:
        lookup = {merchant.merchant_id: merchant for merchant in deterministic.merchants}
        for merchant_id in resolved_merchants:
            merchant = lookup.get(merchant_id)
            if merchant is None:
                raise err(
                    "ERR_S4_BRANCH_PURITY",
                    f"existing S4 logs reference unknown merchant {merchant_id}",
                )
            lambda_regime = compute_lambda_regime(
                hyperparams=deterministic.hyperparams,
                n_outlets=merchant.n_outlets,
                feature_value=merchant.feature_value,
            )
            rejection_count = len(rejections.get(merchant_id, []))
            final_records = finals.get(merchant_id)
            if final_records:
                if len(final_records) > 1:
                    raise err(
                        "ERR_S4_NUMERIC_INVALID",
                        f"multiple S4 final records found for merchant {merchant_id}",
                    )
                record = final_records[0]
                existing_records.append(
                    ZTPFinalRecord(
                        merchant_id=merchant_id,
                        lambda_extra=float(
                            record.get("lambda_extra", lambda_regime.lambda_extra)
                        ),
                        regime=str(record.get("regime", lambda_regime.regime)),
                        attempts=int(record.get("attempts", 0)),
                        rejections=rejection_count,
                        k_target=int(record["K_target"])
                        if record.get("K_target") is not None
                        else None,
                        exhausted=bool(record.get("exhausted", False)),
                        policy=deterministic.hyperparams.exhaustion_policy,
                        reason=record.get("reason"),
                    )
                )
            else:
                retry_list = retries[merchant_id]
                if len(retry_list) > 1:
                    raise err(
                        "ERR_S4_NUMERIC_INVALID",
                        f"multiple S4 retry_exhausted records for merchant {merchant_id}",
                    )
                retry_record = retry_list[0]
                existing_records.append(
                    ZTPFinalRecord(
                        merchant_id=merchant_id,
                        lambda_extra=float(
                            retry_record.get("lambda_extra", lambda_regime.lambda_extra)
                        ),
                        regime=lambda_regime.regime,
                        attempts=int(retry_record.get("attempts", 0)),
                        rejections=rejection_count,
                        k_target=None,
                        exhausted=True,
                        policy=deterministic.hyperparams.exhaustion_policy,
                        reason=None,
                    )
                )

    existing_records.sort(key=lambda record: record.merchant_id)
    return existing_records, resolved_merchants, partial_merchants


class S4ZTPTargetRunner:
    """Drive the S4 attempt loop for all eligible merchants."""

    def run(
        self,
        *,
        base_path: Path,
        deterministic: S4DeterministicContext,
    ) -> S4RunResult:
        base_path = base_path.expanduser().resolve()
        engine = PhiloxEngine(
            seed=deterministic.seed,
            manifest_fingerprint=deterministic.manifest_fingerprint,
        )
        writer = l0_writer.ZTPEventWriter(
            base_path=base_path,
            seed=deterministic.seed,
            parameter_hash=deterministic.parameter_hash,
            manifest_fingerprint=deterministic.manifest_fingerprint,
            run_id=deterministic.run_id,
        )

        start_perf = time.perf_counter()
        last_checkpoint = start_perf

        def log_progress(message: str) -> None:
            nonlocal last_checkpoint
            now = time.perf_counter()
            total = now - start_perf
            delta = now - last_checkpoint
            logger.info("S4: %s (elapsed=%.2fs, delta=%.2fs)", message, total, delta)
            last_checkpoint = now

        log_progress(f"run initialised (merchants={len(deterministic.merchants)})")

        existing_records, resolved_merchants, partial_merchants = _load_existing_outcomes(
            base_path=base_path,
            deterministic=deterministic,
        )
        if partial_merchants:
            raise err(
                "ERR_S4_PARTIAL_RESUME",
                f"partial S4 logs detected for merchants {sorted(partial_merchants)}",
            )
        if resolved_merchants:
            log_progress(
                f"resume detected (resolved_merchants={len(resolved_merchants)})"
            )

        finals: list[ZTPFinalRecord] = list(existing_records)
        for merchant in deterministic.merchants:
            if merchant.merchant_id in resolved_merchants:
                continue
            if not _merchant_in_scope(merchant):
                continue

            lambda_regime = compute_lambda_regime(
                hyperparams=deterministic.hyperparams,
                n_outlets=merchant.n_outlets,
                feature_value=merchant.feature_value,
            )
            poisson_substream = derive_poisson_substream(
                engine, merchant_id=merchant.merchant_id
            )

            outcome = run_sampler(
                merchant=merchant,
                lambda_regime=lambda_regime,
                hyperparams=deterministic.hyperparams,
                admissible_foreign_count=merchant.admissible_foreign_count,
                poisson_substream=poisson_substream,
                writer=writer,
            )
            finals.append(
                ZTPFinalRecord(
                    merchant_id=outcome.merchant_id,
                    lambda_extra=outcome.lambda_extra,
                    regime=outcome.regime,
                    attempts=outcome.attempts,
                    rejections=outcome.rejections,
                    k_target=outcome.k_target,
                    exhausted=outcome.exhausted,
                    policy=outcome.policy,
                    reason=outcome.reason,
                )
            )

        processed_total = len(finals)
        processed_new = processed_total - len(existing_records)
        log_progress(
            f"emitted s4 events (new_merchants={processed_new}, total_merchants={processed_total})"
        )
        log_progress("completed run")

        return S4RunResult(
            deterministic=deterministic,
            finals=tuple(finals),
            poisson_events_path=writer.poisson_events_path,
            rejection_events_path=writer.rejection_events_path,
            retry_exhausted_events_path=writer.retry_exhausted_events_path,
            final_events_path=writer.final_events_path,
            trace_path=writer.trace_path,
        )


def _merchant_in_scope(merchant: S4MerchantTarget) -> bool:
    """Ensure the merchant satisfies branch purity gates."""

    if not merchant.is_multi or not merchant.is_eligible:
        return False
    if merchant.n_outlets < 2:
        raise err(
            "ERR_S4_BRANCH_PURITY",
            f"S4 received merchant {merchant.merchant_id} with n_outlets={merchant.n_outlets}",
        )
    return True


__all__ = ["S4RunResult", "S4ZTPTargetRunner", "ZTPFinalRecord"]
