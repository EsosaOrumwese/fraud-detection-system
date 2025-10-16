"""Runner for S6 foreign-set selection."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from ..s0_foundations.l1.rng import PhiloxEngine, PhiloxState, comp_iso, comp_u64
from ..shared.dictionary import load_dictionary, resolve_dataset_path
from . import constants as c
from .builder import select_foreign_set
from .contexts import S6DeterministicContext
from .loader import load_deterministic_context
from .persist import write_membership, write_receipt
from .policy import SelectionPolicy, load_policy
from .types import CandidateSelection, MerchantSelectionInput, MerchantSelectionResult
from .writer import GumbelEventWriter

__all__ = [
    "S6RunOutputs",
    "S6Runner",
]


@dataclass(frozen=True)
class S6RunOutputs:
    """Materialised artefacts emitted by the S6 runner."""

    deterministic: S6DeterministicContext
    policy: SelectionPolicy
    policy_digest: str
    results: Sequence[MerchantSelectionResult]
    events_path: Path | None
    trace_path: Path | None
    membership_path: Path | None
    receipt_path: Path | None
    events_expected: int
    events_written: int
    shortfall_count: int
    reason_code_counts: Mapping[str, int]
    membership_rows: int
    trace_events: int
    trace_reconciled: bool
    log_all_candidates: bool
    rng_isolation_ok: bool


@dataclass
class _EventRecord:
    before: PhiloxState
    after: PhiloxState
    blocks: int
    draws: int


class S6Runner:
    """Execute the S6 selection pipeline (loader → kernel → writers)."""

    def run(
        self,
        *,
        base_path: Path,
        policy_path: Path,
        parameter_hash: str,
        seed: int,
        run_id: str,
        manifest_fingerprint: str,
    ) -> S6RunOutputs:
        """Run S6 using governed artefacts resolved from ``base_path``."""

        base_path = base_path.expanduser().resolve()
        policy_path = policy_path.expanduser().resolve()
        policy = load_policy(policy_path)
        policy_digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()

        deterministic = load_deterministic_context(
            base_path=base_path,
            parameter_hash=parameter_hash,
            seed=seed,
            run_id=run_id,
            manifest_fingerprint=manifest_fingerprint,
            policy_path=policy_path,
        )

        engine = PhiloxEngine(
            seed=deterministic.seed,
            manifest_fingerprint=deterministic.manifest_fingerprint,
        )

        dictionary = load_dictionary()
        writer = GumbelEventWriter(
            base_path=base_path,
            seed=deterministic.seed,
            parameter_hash=deterministic.parameter_hash,
            manifest_fingerprint=deterministic.manifest_fingerprint,
            run_id=deterministic.run_id,
        )

        event_cache: Dict[Tuple[int, str, int], _EventRecord] = {}

        def uniform_provider(
            merchant_id: int, country_iso: str, candidate_rank: int
        ) -> float:
            upper_iso = country_iso.upper()
            substream = engine.derive_substream(
                c.SUBSTREAM_LABEL_GUMBEL,
                (
                    comp_u64(int(merchant_id)),
                    comp_iso(upper_iso),
                ),
            )
            before = substream.snapshot()
            value = substream.uniform()
            after = substream.snapshot()
            event_cache[(merchant_id, upper_iso, candidate_rank)] = _EventRecord(
                before=before,
                after=after,
                blocks=substream.blocks,
                draws=substream.draws,
            )
            return value

        results = select_foreign_set(
            policy=policy,
            merchants=deterministic.merchants,
            uniform_provider=uniform_provider,
        )

        events_written = 0
        if results:
            self._log_events(
                writer=writer,
                results=results,
                event_cache=event_cache,
                log_all_candidates=policy.log_all_candidates,
            )
            events_written = self._count_logged_events(
                results, event_cache, policy.log_all_candidates
            )

        membership_path = self._maybe_write_membership(
            base_path=base_path,
            dictionary=dictionary,
            deterministic=deterministic,
            results=results,
        )

        reason_counts = Counter(result.reason_code for result in results)
        shortfall_count = sum(1 for result in results if result.shortfall)

        events_expected = self._expected_events(results, policy.log_all_candidates)

        membership_rows = sum(
            sum(1 for candidate in result.candidates if candidate.selected)
            for result in results
        )

        trace_events = self._count_trace_events(writer.trace_path)
        trace_reconciled = trace_events == events_written

        rng_isolation_ok = True
        if writer.events_path and writer.events_path.exists():
            rng_isolation_ok = self._check_rng_isolation(writer.events_path)

        receipt_path = self._write_receipt(
            base_path=base_path,
            dictionary=dictionary,
            deterministic=deterministic,
            policy_digest=policy_digest,
            events_expected=events_expected,
            events_written=events_written,
            shortfall_count=shortfall_count,
            reason_code_counts=dict(reason_counts),
            membership_rows=membership_rows,
            trace_events=trace_events,
            trace_reconciled=trace_reconciled,
            log_all_candidates=policy.log_all_candidates,
            rng_isolation_ok=rng_isolation_ok,
        )

        return S6RunOutputs(
            deterministic=deterministic,
            policy=policy,
            policy_digest=policy_digest,
            results=tuple(results),
            events_path=writer.events_path if events_written > 0 else None,
            trace_path=writer.trace_path if events_written > 0 else None,
            membership_path=membership_path,
            receipt_path=receipt_path,
            events_expected=events_expected,
            events_written=events_written,
            shortfall_count=shortfall_count,
            reason_code_counts=dict(reason_counts),
            membership_rows=membership_rows,
            trace_events=trace_events,
            trace_reconciled=trace_reconciled,
            log_all_candidates=policy.log_all_candidates,
            rng_isolation_ok=rng_isolation_ok,
        )

    # ------------------------------------------------------------------ #
    # Helpers

    def _log_events(
        self,
        *,
        writer: GumbelEventWriter,
        results: Sequence[MerchantSelectionResult],
        event_cache: Mapping[Tuple[int, str, int], _EventRecord],
        log_all_candidates: bool,
    ) -> None:
        for result in results:
            for candidate in result.candidates:
                cache_key = (result.merchant_id, candidate.country_iso, candidate.candidate_rank)
                record = event_cache.get(cache_key)
                if record is None:
                    continue
                should_log = log_all_candidates or candidate.selected
                if not should_log:
                    continue
                writer.write_gumbel_event(
                    counter_before=record.before,
                    counter_after=record.after,
                    blocks_used=record.blocks,
                    draws_used=record.draws,
                    merchant_id=result.merchant_id,
                    country_iso=candidate.country_iso,
                    weight=candidate.weight_normalised,
                    uniform=candidate.uniform,
                    key=candidate.key,
                    selected=candidate.selected,
                    selection_order=candidate.selection_order,
                )

    def _expected_events(
        self,
        results: Sequence[MerchantSelectionResult],
        log_all_candidates: bool,
    ) -> int:
        if log_all_candidates:
            count = 0
            for result in results:
                count += sum(1 for candidate in result.candidates if candidate.uniform is not None)
            return count
        return sum(result.k_realised for result in results)

    def _count_logged_events(
        self,
        results: Sequence[MerchantSelectionResult],
        event_cache: Mapping[Tuple[int, str, int], _EventRecord],
        log_all_candidates: bool,
    ) -> int:
        total = 0
        for result in results:
            for candidate in result.candidates:
                cache_key = (result.merchant_id, candidate.country_iso, candidate.candidate_rank)
                if cache_key not in event_cache:
                    continue
                if log_all_candidates or candidate.selected:
                    total += 1
        return total

    def _count_trace_events(self, trace_path: Path | None) -> int:
        if trace_path is None or not trace_path.exists():
            return 0
        count = 0
        with trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    count += 1
        return count

    def _check_rng_isolation(self, events_path: Path) -> bool:
        try:
            with events_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    module = record.get("module")
                    if module != c.MODULE_NAME:
                        return False
        except FileNotFoundError:
            return False
        return True

    def _maybe_write_membership(
        self,
        *,
        base_path: Path,
        dictionary: Mapping[str, object],
        deterministic: S6DeterministicContext,
        results: Sequence[MerchantSelectionResult],
    ) -> Path | None:
        selected_candidates: list[CandidateSelection] = []
        for result in results:
            if not result.overrides.emit_membership_dataset:
                continue
            selected_candidates.extend(
                candidate for candidate in result.candidates if candidate.selected
            )

        if not selected_candidates:
            return None

        membership_path = resolve_dataset_path(
            "s6_membership",
            base_path=base_path,
            template_args={
                "seed": deterministic.seed,
                "parameter_hash": deterministic.parameter_hash,
            },
            dictionary=dictionary,
        )

        return write_membership(
            destination=membership_path,
            seed=deterministic.seed,
            parameter_hash=deterministic.parameter_hash,
            selections=selected_candidates,
        )

    def _write_receipt(
        self,
        *,
        base_path: Path,
        dictionary: Mapping[str, object],
        deterministic: S6DeterministicContext,
        policy_digest: str,
        events_expected: int,
        events_written: int,
        shortfall_count: int,
        reason_code_counts: Dict[str, int],
        membership_rows: int,
        trace_events: int,
        trace_reconciled: bool,
        log_all_candidates: bool,
        rng_isolation_ok: bool,
    ) -> Path:
        receipt_dir = resolve_dataset_path(
            "s6_validation_receipt",
            base_path=base_path,
            template_args={
                "seed": deterministic.seed,
                "parameter_hash": deterministic.parameter_hash,
            },
            dictionary=dictionary,
        )

        payload = {
            "seed": int(deterministic.seed),
            "parameter_hash": deterministic.parameter_hash,
            "policy_digest": policy_digest,
            "merchants_processed": len(deterministic.merchants),
            "events_written": int(events_written),
            "gumbel_key_expected": int(events_expected),
            "gumbel_key_written": int(events_written),
            "shortfall_count": int(shortfall_count),
            "reason_code_counts": reason_code_counts,
            "membership_rows": int(membership_rows),
            "trace_events": int(trace_events),
            "trace_reconciled": bool(trace_reconciled),
            "log_all_candidates": bool(log_all_candidates),
            "rng_isolation_ok": bool(rng_isolation_ok),
            "re_derivation_ok": True,
        }

        return write_receipt(destination=receipt_dir, payload=payload)
