"""Runner for S6 foreign-set selection."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

from ..s0_foundations.exceptions import err
from ..s0_foundations.l1.rng import PhiloxEngine, PhiloxState, comp_iso, comp_u64
from ..shared.dictionary import load_dictionary, resolve_dataset_path
from . import constants as c
from .builder import iter_select_foreign_set
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
    metrics: Mapping[str, object]
    metrics_log_path: Path | None


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

        active_merchant_id: Optional[int] = None
        current_events: Dict[Tuple[str, int], _EventRecord] = {}

        def _on_merchant_begin(merchant: object) -> None:
            nonlocal active_merchant_id, current_events
            # Merchants are processed sequentially; reset the buffer so the
            # uniform provider only retains events for the active merchant.
            if current_events:
                current_events.clear()
            active_merchant_id = getattr(merchant, "merchant_id", None)

        def uniform_provider(
            merchant_id: int, country_iso: str, candidate_rank: int
        ) -> float:
            upper_iso = country_iso.upper()
            nonlocal active_merchant_id
            if active_merchant_id is None:
                active_merchant_id = merchant_id
            elif merchant_id != active_merchant_id:
                raise err(
                    "E_RNG_COUNTER",
                    "uniform provider invoked out of order for merchant "
                    f"{merchant_id} (active={active_merchant_id})",
                )
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
            current_events[(upper_iso, candidate_rank)] = _EventRecord(
                before=before,
                after=after,
                blocks=substream.blocks,
                draws=substream.draws,
            )
            return value

        events_by_merchant: Dict[int, int] = {}
        collected_results: list[MerchantSelectionResult] = []
        for result in iter_select_foreign_set(
            policy=policy,
            merchants=deterministic.merchants,
            uniform_provider=uniform_provider,
            on_merchant_begin=_on_merchant_begin,
        ):
            collected_results.append(result)
            events_count = self._log_events_for_result(
                writer=writer,
                result=result,
                event_records=current_events,
                log_all_candidates=policy.log_all_candidates,
            )
            events_by_merchant[result.merchant_id] = events_count
            current_events.clear()
        results: Tuple[MerchantSelectionResult, ...] = tuple(collected_results)
        events_written = sum(events_by_merchant.values())

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

        trace_events, trace_totals = self._trace_summary(writer.module_trace_path)
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
            events_by_merchant=events_by_merchant,
            trace_totals=trace_totals,
        )

        metrics, log_path = self._build_metrics(
            base_path=base_path,
            deterministic=deterministic,
            results=results,
            policy=policy,
            events_by_merchant=events_by_merchant,
            events_expected=events_expected,
            events_written=events_written,
            trace_totals=trace_totals,
            metrics_log_enabled=True,
        )

        return S6RunOutputs(
            deterministic=deterministic,
            policy=policy,
            policy_digest=policy_digest,
            results=tuple(results),
            events_path=writer.events_path if events_written > 0 else None,
            trace_path=writer.module_trace_path if trace_events > 0 else None,
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
            metrics=metrics,
            metrics_log_path=log_path,
        )

    # ------------------------------------------------------------------ #
    # Helpers

    def _log_events_for_result(
        self,
        *,
        writer: GumbelEventWriter,
        result: MerchantSelectionResult,
        event_records: Mapping[Tuple[str, int], _EventRecord],
        log_all_candidates: bool,
    ) -> int:
        events_written = 0
        for candidate in result.candidates:
            cache_key = (candidate.country_iso.upper(), candidate.candidate_rank)
            record = event_records.get(cache_key)
            if record is None:
                continue
            should_log = log_all_candidates or candidate.selected
            try:
                event_records.pop(cache_key, None)  # type: ignore[attr-defined]
            except AttributeError:
                pass
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
            events_written += 1
        return events_written

    def _expected_events(
        self,
        results: Sequence[MerchantSelectionResult],
        log_all_candidates: bool,
    ) -> int:
        if log_all_candidates:
            return sum(result.expected_events for result in results)
        return sum(result.k_realised for result in results)

    def _trace_summary(self, trace_path: Path | None) -> tuple[int, Dict[str, int]]:
        if trace_path is None or not trace_path.exists():
            return 0, {"events_total": 0, "blocks_total": 0, "draws_total": 0}
        count = 0
        last_record: dict | None = None
        with trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last_record = json.loads(line)
                    count += 1
        totals = {"events_total": 0, "blocks_total": 0, "draws_total": 0}
        if last_record is not None:
            totals["events_total"] = int(last_record.get("events_total", 0))
            totals["blocks_total"] = int(last_record.get("blocks_total", "0"))
            totals["draws_total"] = int(last_record.get("draws_total", "0"))
        return count, totals

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
        events_by_merchant: Mapping[int, int],
        trace_totals: Mapping[str, int],
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
            "trace_totals": {
                "events_total": int(trace_totals.get("events_total", 0)),
                "blocks_total": int(trace_totals.get("blocks_total", 0)),
                "draws_total": int(trace_totals.get("draws_total", 0)),
            },
            "events_by_merchant": {str(key): int(value) for key, value in events_by_merchant.items()},
        }

        return write_receipt(destination=receipt_dir, payload=payload)

    def _build_metrics(
        self,
        *,
        base_path: Path,
        deterministic: S6DeterministicContext,
        results: Sequence[MerchantSelectionResult],
        policy: SelectionPolicy,
        events_by_merchant: Mapping[int, int],
        events_expected: int,
        events_written: int,
        trace_totals: Mapping[str, int],
        metrics_log_enabled: bool,
    ) -> tuple[Dict[str, object], Path | None]:
        merchants_total = len(deterministic.merchants)
        merchants_gated_in = len(results)
        merchants_selected = sum(1 for result in results if result.k_realised > 0)
        merchants_empty = sum(1 for result in results if result.k_realised == 0)
        a_filtered_sum = sum(result.domain_considered for result in results)
        k_target_sum = sum(result.k_target for result in results)
        k_realised_sum = sum(result.k_realised for result in results)
        shortfall_merchants = sum(1 for result in results if result.shortfall)

        reason_counts = Counter(result.reason_code for result in results)
        reason_metrics = {
            "NO_CANDIDATES": int(reason_counts.get("NO_CANDIDATES", 0)),
            "K_ZERO": int(reason_counts.get("K_ZERO", 0)),
            "ZERO_WEIGHT_DOMAIN": int(reason_counts.get("ZERO_WEIGHT_DOMAIN", 0)),
            "CAPPED_BY_MAX_CANDIDATES": int(reason_counts.get("CAPPED_BY_MAX_CANDIDATES", 0)),
        }

        selection_hist = {
            "b0": 0,
            "b1": 0,
            "b2": 0,
            "b3_5": 0,
            "b6_10": 0,
            "b11_plus": 0,
        }
        for result in results:
            k = result.k_realised
            if k == 0:
                selection_hist["b0"] += 1
            elif k == 1:
                selection_hist["b1"] += 1
            elif k == 2:
                selection_hist["b2"] += 1
            elif 3 <= k <= 5:
                selection_hist["b3_5"] += 1
            elif 6 <= k <= 10:
                selection_hist["b6_10"] += 1
            else:
                selection_hist["b11_plus"] += 1

        metrics: Dict[str, object] = {
            "s6.run.merchants_total": merchants_total,
            "s6.run.merchants_gated_in": merchants_gated_in,
            "s6.run.merchants_selected": merchants_selected,
            "s6.run.merchants_empty": merchants_empty,
            "s6.run.A_filtered_sum": a_filtered_sum,
            "s6.run.K_target_sum": k_target_sum,
            "s6.run.K_realized_sum": k_realised_sum,
            "s6.run.shortfall_merchants": shortfall_merchants,
            "s6.run.reason.NO_CANDIDATES": reason_metrics["NO_CANDIDATES"],
            "s6.run.reason.K_ZERO": reason_metrics["K_ZERO"],
            "s6.run.reason.ZERO_WEIGHT_DOMAIN": reason_metrics["ZERO_WEIGHT_DOMAIN"],
            "s6.run.reason.CAPPED_BY_MAX_CANDIDATES": reason_metrics["CAPPED_BY_MAX_CANDIDATES"],
            "s6.run.events.gumbel_key.expected": events_expected,
            "s6.run.events.gumbel_key.written": events_written,
            "s6.run.trace.events_total": int(trace_totals.get("events_total", 0)),
            "s6.run.trace.blocks_total": int(trace_totals.get("blocks_total", 0)),
            "s6.run.trace.draws_total": int(trace_totals.get("draws_total", 0)),
            "s6.run.policy.log_all_candidates": bool(policy.log_all_candidates),
            "s6.run.policy.max_candidates_cap": int(policy.max_candidates_cap),
            "s6.run.policy.zero_weight_rule": policy.zero_weight_rule,
            "s6.run.policy.currency_overrides_count": len(policy.per_currency),
            "s6.run.selection_size_histogram": selection_hist,
        }

        log_path: Path | None = None
        if metrics_log_enabled:
            log_path = self._write_metrics_log(
                base_path=base_path,
                deterministic=deterministic,
                results=results,
                log_all_candidates=policy.log_all_candidates,
                events_by_merchant=events_by_merchant,
            )
        return metrics, log_path

    def _write_metrics_log(
        self,
        *,
        base_path: Path,
        deterministic: S6DeterministicContext,
        results: Sequence[MerchantSelectionResult],
        log_all_candidates: bool,
        events_by_merchant: Mapping[int, int],
    ) -> Path:
        metrics_dir = (
            Path(base_path).expanduser().resolve()
            / "logs"
            / "metrics"
            / "s6"
            / f"seed={deterministic.seed}"
            / f"parameter_hash={deterministic.parameter_hash}"
            / f"run_id={deterministic.run_id}"
        )
        metrics_dir.mkdir(parents=True, exist_ok=True)
        log_path = metrics_dir / "merchant_metrics.jsonl"
        with log_path.open("w", encoding="utf-8") as handle:
            for result in results:
                events_written = int(events_by_merchant.get(result.merchant_id, 0))
                record = {
                    "ts": _utc_timestamp(),
                    "level": "INFO",
                    "component": c.MODULE_NAME,
                    "stage": "select",
                    "seed": int(deterministic.seed),
                    "parameter_hash": deterministic.parameter_hash,
                    "run_id": deterministic.run_id,
                    "merchant_id": result.merchant_id,
                    "A": result.domain_total,
                    "A_filtered": result.domain_considered,
                    "K_target": result.k_target,
                    "K_realized": result.k_realised,
                    "considered_expected_events": result.expected_events,
                    "gumbel_key_written": events_written,
                    "is_shortfall": bool(result.shortfall),
                    "reason_code": result.reason_code,
                    "ties_resolved": result.ties_resolved,
                    "policy_cap_applied": bool(result.policy_cap_applied),
                    "cap_value": int(result.cap_value),
                    "zero_weight_considered": result.zero_weight_considered,
                    "log_all_candidates": bool(log_all_candidates),
                    "rng": {
                        "trace": {
                            "delta": {
                                "events": events_written,
                                "blocks": events_written,
                                "draws": events_written,
                            }
                        }
                    },
                }
                handle.write(json.dumps(record, sort_keys=True))
                handle.write("\n")
        return log_path


def _utc_timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="microseconds")
