"""Shared type definitions for the S3 cross-border universe helpers.

The expanded S3 specification introduces a number of deterministic helper
surfaces (rule ladder evaluation, candidate construction, ordering).  Keeping
the lightweight data containers in a dedicated module avoids import cycles
between L0/L1/L2 layers while making it easy for tests to introspect the
intermediate structures.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple


@dataclass(frozen=True)
class RuleTraceEntry:
    """Single fired rule recorded during ladder evaluation (S3.1).

    Attributes
    ----------
    rule_id:
        Identifier of the rule in the governed artefact.
    precedence:
        Precedence class name (e.g., ``DENY`` or ``ALLOW``) – stable, ASCII.
    precedence_rank:
        Numeric slot of the precedence class within the artefact's precedence
        order (lower numbers execute first).
    priority:
        Within-precedence priority (lower sorts first); ties fall back to the
        lexicographic rule_id.
    is_decision_bearing:
        Whether this rule is allowed to decide ``eligible_crossborder``.
    reason_code:
        Reason code emitted by the rule outcome (``None`` if the outcome does
        not declare one).
    is_decision_source:
        True iff this rule ultimately supplied the decision that fixed
        ``eligible_crossborder``.
    tags:
        Deterministic tuple of merchant-level tags produced by this rule. The
        vocabulary is limited to the artefact's ``filter_tags`` set and is
        supplied in ASCII A–Z order.
    """

    rule_id: str
    precedence: str
    precedence_rank: int
    priority: int
    is_decision_bearing: bool
    reason_code: str | None
    is_decision_source: bool
    tags: Tuple[str, ...]


@dataclass(frozen=True)
class RuleLadderEvaluation:
    """Result of evaluating the governed rule ladder for a merchant.

    Attributes
    ----------
    eligible_crossborder:
        Final cross-border admission flag (output of S3.1).
    decision_rule_id:
        Identifier of the decision-bearing rule that fixed the outcome.
    trace:
        Ordered tuple of :class:`RuleTraceEntry` describing every fired rule.
    merchant_tags:
        Deterministic union of merchant-scoped tags emitted by fired rules.
        Tags are ASCII uppercase and sorted A–Z.
    admitting_rules_by_country:
        Mapping from ISO2 country codes to the tuple of rule identifiers that
        admitted the country (post precedence filtering).  Each tuple is sorted
        in admission evaluation order.
    denying_rules_by_country:
        Mapping from ISO2 codes to rule identifiers that explicitly deny the
        country.  Used so later phases can subtract denials before forming the
        candidate set.
    row_tags_by_country:
        Optional per-country tag overrides supplied by rule outcomes (e.g.,
        legal/geo annotations).  Tags are sorted A–Z.
    """

    eligible_crossborder: bool
    decision_rule_id: str
    trace: Tuple[RuleTraceEntry, ...]
    merchant_tags: Tuple[str, ...]
    admitting_rules_by_country: Mapping[str, Tuple[str, ...]]
    denying_rules_by_country: Mapping[str, Tuple[str, ...]]
    row_tags_by_country: Mapping[str, Tuple[str, ...]]


@dataclass(frozen=True)
class RuleDefinition:
    """Parsed representation of a rule from the governed ladder artefact."""

    rule_id: str
    precedence: str
    precedence_rank: int
    priority: int
    predicate: object
    is_decision_bearing: bool
    reason_code: str | None
    outcome_tags: Tuple[str, ...]
    row_tags: Tuple[str, ...]
    admit_countries: Tuple[str, ...]
    admit_sets: Tuple[str, ...]
    deny_countries: Tuple[str, ...]
    deny_sets: Tuple[str, ...]


@dataclass(frozen=True)
class RuleLadder:
    """Parsed rule ladder artefact ready for deterministic evaluation."""

    semver: str | None
    version: str | None
    precedence_order: Tuple[str, ...]
    rules: Tuple[RuleDefinition, ...]
    reason_code_vocab: Tuple[str, ...]
    reason_code_to_rule_id: Mapping[str, str]
    filter_tag_vocab: Tuple[str, ...]
    named_sets: Mapping[str, Tuple[str, ...]]
    default_admit_sets: Tuple[str, ...]
    default_tags: Tuple[str, ...]


@dataclass(frozen=True)
class CandidateSeed:
    """Intermediate candidate row prior to ranking (S3.2 output)."""

    merchant_id: int
    country_iso: str
    is_home: bool
    filter_tags: Tuple[str, ...]
    reason_codes: Tuple[str, ...]
    admitting_rules: Tuple[str, ...]


@dataclass(frozen=True)
class RankedCandidateRow:
    """Candidate row after ranking (S3.3 output)."""

    merchant_id: int
    country_iso: str
    is_home: bool
    candidate_rank: int
    filter_tags: Tuple[str, ...]
    reason_codes: Tuple[str, ...]
    admitting_rules: Tuple[str, ...]


@dataclass(frozen=True)
class PriorRow:
    """Deterministic prior score emitted for a candidate."""

    merchant_id: int
    country_iso: str
    base_weight_dp: str
    dp: int


@dataclass(frozen=True)
class CountRow:
    """Integerised count allocation for a candidate country."""

    merchant_id: int
    country_iso: str
    count: int
    residual_rank: int


@dataclass(frozen=True)
class SequenceRow:
    """Within-country site sequencing row."""

    merchant_id: int
    country_iso: str
    site_order: int
    site_id: str | None
