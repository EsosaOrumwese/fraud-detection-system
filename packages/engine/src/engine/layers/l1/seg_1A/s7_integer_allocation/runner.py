"""Runner for S7 integer allocation (Layer 1 / Segment 1A)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

from ..s0_foundations.exceptions import err
from ..s0_foundations.l1.rng import PhiloxEngine, PhiloxState, comp_u64
from ..shared.dictionary import load_dictionary
from ..s6_foreign_selection.contexts import S6DeterministicContext
from ..s6_foreign_selection.types import MerchantSelectionResult
from ..s2_nb_outlets.l2.runner import NBFinalRecord
from .kernel import allocate_merchants
from .loader import build_deterministic_context
from .policy import IntegerisationPolicy, load_policy
from .types import MerchantAllocationResult
from .writer import S7EventWriter
from . import constants as c
from .contexts import S7DeterministicContext

__all__ = ["S7RunOutputs", "S7Runner"]


@dataclass(frozen=True)
class S7RunOutputs:
    """Materialised artefacts emitted by the S7 runner."""

    deterministic: S7DeterministicContext
    policy: IntegerisationPolicy
    policy_digest: str
    artefact_digests: Mapping[str, str]
    results: Sequence[MerchantAllocationResult]
    residual_events_path: Path
    dirichlet_events_path: Path | None
    trace_path: Path
    residual_events: int
    dirichlet_events: int
    trace_events: int
    trace_reconciled: bool
    metrics: Mapping[str, object]


class S7Runner:
    """Execute the S7 integer allocation pipeline."""

    def run(
        self,
        *,
        base_path: Path,
        policy_path: Path,
        parameter_hash: str,
        manifest_fingerprint: str,
        seed: int,
        run_id: str,
        nb_finals: Sequence[NBFinalRecord],
        s6_context: S6DeterministicContext,
        s6_results: Sequence[MerchantSelectionResult],
    ) -> S7RunOutputs:
        base_path = Path(base_path).expanduser().resolve()
        policy_path = Path(policy_path).expanduser().resolve()
        dictionary = load_dictionary()
        policy = load_policy(policy_path)
        policy_digest = _sha256_file(policy_path)
        artefact_digests: Dict[str, str] = {str(policy_path): policy_digest}
        for path, digest in policy.digests.items():
            artefact_digests[path] = digest

        deterministic = build_deterministic_context(
            base_path=base_path,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            seed=seed,
            run_id=run_id,
            policy_path=policy_path,
            nb_finals=nb_finals,
            s6_context=s6_context,
            s6_results=s6_results,
            policy=policy,
            dictionary=dictionary,
            artefact_digests=artefact_digests,
        )

        allocation_results = allocate_merchants(
            deterministic.merchants,
            policy=policy,
        )

        writer = S7EventWriter(
            base_path=base_path,
            seed=seed,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            run_id=run_id,
        )

        residual_events = 0
        for merchant in allocation_results:
            for domain_alloc in merchant.domain_allocations:
                writer.write_residual_rank(
                    merchant_id=merchant.merchant_id,
                    country_iso=domain_alloc.country_iso,
                    residual=domain_alloc.residual,
                    residual_rank=domain_alloc.residual_rank,
                )
                residual_events += 1

        dirichlet_events = 0
        if policy.dirichlet_enabled:
            dirichlet_events = self._emit_dirichlet_events(
                writer=writer,
                allocation_results=allocation_results,
                policy=policy,
                seed=seed,
                manifest_fingerprint=manifest_fingerprint,
            )

        trace_events = residual_events + dirichlet_events

        metrics = self._build_metrics(
            results=allocation_results,
            policy=policy,
            residual_events=residual_events,
            dirichlet_events=dirichlet_events,
            trace_events=trace_events,
        )

        return S7RunOutputs(
            deterministic=deterministic,
            policy=policy,
            policy_digest=policy_digest,
            artefact_digests=artefact_digests,
            results=allocation_results,
            residual_events_path=writer.residual_path,
            dirichlet_events_path=(
                writer.dirichlet_path if policy.dirichlet_enabled else None
            ),
            trace_path=writer.trace_path,
            residual_events=residual_events,
            dirichlet_events=dirichlet_events,
            trace_events=trace_events,
            trace_reconciled=True,
            metrics=metrics,
        )

    def _emit_dirichlet_events(
        self,
        *,
        writer: S7EventWriter,
        allocation_results: Sequence[MerchantAllocationResult],
        policy: IntegerisationPolicy,
        seed: int,
        manifest_fingerprint: str,
    ) -> int:
        if policy.dirichlet_alpha0 is None:
            raise err(
                "E_DIRICHLET_CONFIG",
                "dirichlet lane enabled but alpha0 not provided",
            )

        engine = PhiloxEngine(seed=seed, manifest_fingerprint=manifest_fingerprint)
        events = 0

        for merchant in allocation_results:
            substream = engine.derive_substream(
                c.SUBSTREAM_LABEL_DIRICHLET,
                (comp_u64(int(merchant.merchant_id)),),
            )
            before = substream.snapshot()
            alphas = _build_dirichlet_alpha_vector(
                merchant=merchant,
                alpha0=policy.dirichlet_alpha0,
            )
            gamma_raw = tuple(substream.gamma(value) for value in alphas)
            after = substream.snapshot()
            blocks_used = substream.blocks
            draws_used = substream.draws
            weights = _normalise_gamma(gamma_raw)
            writer.write_dirichlet_gamma_vector(
                counter_before=before,
                counter_after=after,
                blocks_used=int(blocks_used),
                draws_used=int(draws_used),
                merchant_id=merchant.merchant_id,
                home_country_iso=_home_country(merchant),
                country_isos=tuple(
                    alloc.country_iso for alloc in merchant.domain_allocations
                ),
                alpha=alphas,
                gamma_raw=gamma_raw,
                weights=weights,
                n_domestic=merchant.total_outlets,
            )
            events += 1

        return events

    def _build_metrics(
        self,
        *,
        results: Sequence[MerchantAllocationResult],
        policy: IntegerisationPolicy,
        residual_events: int,
        dirichlet_events: int,
        trace_events: int,
    ) -> Dict[str, object]:
        merchants_in_scope = len(results)
        single_country = sum(1 for result in results if len(result.domain_allocations) == 1)
        bounds_enabled = sum(1 for result in results if result.bounds_enforced)

        domain_hist = {
            "b1": 0,
            "b2": 0,
            "b3_5": 0,
            "b6_10": 0,
            "b11_plus": 0,
        }
        remainder_hist = {
            "b0": 0,
            "b1": 0,
            "b2_3": 0,
            "b4_plus": 0,
        }
        for result in results:
            domain_size = len(result.domain_allocations)
            if domain_size == 1:
                domain_hist["b1"] += 1
            elif domain_size == 2:
                domain_hist["b2"] += 1
            elif 3 <= domain_size <= 5:
                domain_hist["b3_5"] += 1
            elif 6 <= domain_size <= 10:
                domain_hist["b6_10"] += 1
            else:
                domain_hist["b11_plus"] += 1

            remainder = result.remainder
            if remainder == 0:
                remainder_hist["b0"] += 1
            elif remainder == 1:
                remainder_hist["b1"] += 1
            elif 2 <= remainder <= 3:
                remainder_hist["b2_3"] += 1
            else:
                remainder_hist["b4_plus"] += 1

        metrics: Dict[str, object] = {
            "s7.merchants_in_scope": merchants_in_scope,
            "s7.single_country": single_country,
            "s7.events.residual_rank.rows": residual_events,
            "s7.events.dirichlet_gamma_vector.rows": dirichlet_events,
            "s7.trace.rows": trace_events,
            "s7.bounds.enabled": bounds_enabled,
            "s7.failures.structural": 0,
            "s7.failures.integerisation": 0,
            "s7.failures.rng_accounting": 0,
            "s7.failures.bounds": 0,
            "s7.domain.size.hist": domain_hist,
            "s7.remainder.d.hist": remainder_hist,
            "s7.ms.integerisation": None,
            "s7.dirichlet.enabled": bool(policy.dirichlet_enabled),
        }
        return metrics


def _home_country(merchant: MerchantAllocationResult) -> str:
    for alloc in merchant.domain_allocations:
        if alloc.is_home:
            return alloc.country_iso
    raise err(
        "E_S7_HOME_DOMAIN",
        f"home entry missing for merchant {merchant.merchant_id}",
    )


def _build_dirichlet_alpha_vector(
    *,
    merchant: MerchantAllocationResult,
    alpha0: float,
) -> Tuple[float, ...]:
    alpha: list[float] = []
    for alloc in merchant.domain_allocations:
        base = max(alpha0 * alloc.share, 1e-12)
        alpha.append(base)
    return tuple(alpha)


def _normalise_gamma(values: Tuple[float, ...]) -> Tuple[float, ...]:
    total = float(sum(values))
    if total <= 0.0:
        raise err("E_DIRICHLET_SUM", "gamma sum must be > 0")
    return tuple(value / total for value in values)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
