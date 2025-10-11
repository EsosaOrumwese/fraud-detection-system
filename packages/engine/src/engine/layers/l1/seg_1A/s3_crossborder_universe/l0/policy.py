"""Helpers for loading and evaluating the governed S3 rule ladder artefact."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import total_ordering
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Sequence, Tuple, List, Optional

from decimal import Decimal

import yaml

from ...s0_foundations.exceptions import err
from .types import (
    RuleDefinition,
    RuleLadder,
    RuleLadderEvaluation,
    RuleTraceEntry,
)

_ASCII_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True)
class BaseWeightRule:
    """Single deterministic scoring rule for priors."""

    rule_id: str
    predicate: str
    predicate_ast: ast.Expression
    components: Tuple[str, ...]
    score_value: Decimal | None = None


@dataclass(frozen=True)
class PolicyNormalisation:
    """Optional normalisation directive applied to rule outputs."""

    method: str
    target: Decimal | None = None


@dataclass(frozen=True)
class BaseWeightPolicy:
    """Deterministic configuration for base-weight priors."""

    semver: str | None
    version: str | None
    dp: int
    constants: Mapping[str, Decimal]
    sets: Mapping[str, Tuple[str, ...]]
    rules: Tuple[BaseWeightRule, ...]
    normalisation: PolicyNormalisation | None = None


@dataclass(frozen=True)
class ThresholdsPolicy:
    """Integerisation bounds and residual configuration."""

    semver: str | None
    version: str | None
    residual_dp: int
    floors: Mapping[str, int]
    ceilings: Mapping[str, Optional[int]]


@dataclass(frozen=True)
class _EvaluationContext:
    """Evaluation context handed to the predicate interpreter."""

    merchant_id: int
    home_country_iso: str
    channel: str
    mcc: str
    n_outlets: int
    named_sets: Mapping[str, Tuple[str, ...]]

    def variable_mapping(self) -> Mapping[str, object]:
        mapping = {
            "merchant_id": self.merchant_id,
            "home_country_iso": self.home_country_iso,
            "channel": self.channel,
            "mcc": self.mcc,
            "n_outlets": self.n_outlets,
        }
        return mapping


@dataclass(frozen=True)
class _BaseWeightContext:
    """Predicate evaluation context for base-weight policies."""

    merchant_id: int
    home_country_iso: str
    channel: str
    mcc: str
    n_outlets: int
    country_iso: str
    is_home: bool
    candidate_rank: int
    filter_tags: Tuple[str, ...]
    merchant_tags: Tuple[str, ...]
    named_sets: Mapping[str, Tuple[str, ...]]

    def variable_mapping(self) -> Mapping[str, object]:
        mapping = {
            "merchant_id": self.merchant_id,
            "home_country_iso": self.home_country_iso,
            "channel": self.channel,
            "mcc": self.mcc,
            "n_outlets": self.n_outlets,
            "country_iso": self.country_iso,
            "is_home": self.is_home,
            "candidate_rank": self.candidate_rank,
            "filter_tags": self.filter_tags,
            "merchant_tags": self.merchant_tags,
        }
        return mapping


def _normalise_iso(code: str) -> str:
    value = code.strip().upper()
    if len(value) != 2 or any(ch not in _ASCII_UPPER for ch in value):
        raise err("ERR_S3_RULE_LADDER_INVALID", f"invalid ISO country code '{code}'")
    return value


def _normalise_tag(tag: str) -> str:
    value = tag.strip().upper()
    if not value or any(ch not in (_ASCII_UPPER + "_0123456789") for ch in value):
        raise err("ERR_S3_RULE_LADDER_INVALID", f"invalid tag '{tag}'")
    return value


def _normalise_reason_code(code: str) -> str:
    value = code.strip().upper()
    if not value or any(ch not in (_ASCII_UPPER + "_0123456789") for ch in value):
        raise err("ERR_S3_RULE_LADDER_INVALID", f"invalid reason code '{code}'")
    return value


def _load_yaml(path: Path) -> Mapping[str, object]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise err("ERR_S3_AUTHORITY_MISSING", f"policy artefact '{path}' missing") from exc
    if not isinstance(payload, Mapping):
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            f"policy artefact '{path}' must decode to a mapping",
        )
    return payload


def _sorted_unique(values: Iterable[str]) -> Tuple[str, ...]:
    unique = {_normalise_tag(v) for v in values}
    return tuple(sorted(unique))


def _sorted_unique_reasons(values: Iterable[str]) -> Tuple[str, ...]:
    unique = {_normalise_reason_code(v) for v in values}
    return tuple(sorted(unique))


def load_rule_ladder(path: Path) -> RuleLadder:
    """Parse a governed rule ladder YAML artefact into a deterministic model."""

    payload = _load_yaml(path)
    semver = payload.get("semver")
    if semver is not None and not isinstance(semver, str):
        raise err("ERR_S3_RULE_LADDER_INVALID", "policy semver must be a string")
    version = payload.get("version")
    if version is not None and not isinstance(version, str):
        raise err("ERR_S3_RULE_LADDER_INVALID", "policy version must be a string")

    raw_reason_codes = payload.get("reason_codes")
    if not isinstance(raw_reason_codes, Sequence) or not raw_reason_codes:
        raise err("ERR_S3_RULE_LADDER_INVALID", "policy must declare reason_codes[]")
    reason_vocab = _sorted_unique_reasons(raw_reason_codes)

    raw_filter_tags = payload.get("filter_tags")
    if not isinstance(raw_filter_tags, Sequence) or not raw_filter_tags:
        raise err("ERR_S3_RULE_LADDER_INVALID", "policy must declare filter_tags[]")
    tag_vocab = _sorted_unique(raw_filter_tags)

    precedence_order = payload.get("precedence_order")
    if not isinstance(precedence_order, Sequence) or not precedence_order:
        raise err(
            "ERR_S3_RULE_LADDER_INVALID", "policy must declare precedence_order[]"
        )
    precedence_tuple = tuple(str(item).strip().upper() for item in precedence_order)
    precedence_rank = {name: idx for idx, name in enumerate(precedence_tuple)}
    if len(precedence_rank) != len(precedence_tuple):
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "precedence_order contains duplicate entries",
        )

    raw_named_sets = payload.get("named_sets", {})
    if not isinstance(raw_named_sets, Mapping):
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "named_sets must be a mapping when present",
        )
    named_sets: Dict[str, Tuple[str, ...]] = {}
    for name, raw_set in raw_named_sets.items():
        if not isinstance(raw_set, Mapping):
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"named set '{name}' must be a mapping with 'countries'",
            )
        countries = raw_set.get("countries")
        if not isinstance(countries, Sequence) or not countries:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"named set '{name}' must provide countries[]",
            )
        named_sets[name.strip().upper()] = tuple(
            _normalise_iso(code) for code in countries
        )

    default_admit_sets = payload.get("default_admit_sets", [])
    if not isinstance(default_admit_sets, Sequence):
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "default_admit_sets must be an array when present",
        )
    default_admit_tuple = tuple(str(item).strip().upper() for item in default_admit_sets)

    default_tags = payload.get("default_tags", [])
    if not isinstance(default_tags, Sequence):
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "default_tags must be an array when present",
        )
    default_tag_tuple = tuple(_normalise_tag(tag) for tag in default_tags)
    for tag in default_tag_tuple:
        if tag not in tag_vocab:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"default tag '{tag}' not present in filter_tags vocabulary",
            )

    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, Sequence) or not raw_rules:
        raise err("ERR_S3_RULE_LADDER_INVALID", "policy must declare rules[]")

    rules: list[RuleDefinition] = []
    seen_rule_ids: set[str] = set()
    decision_rules = 0
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, Mapping):
            raise err("ERR_S3_RULE_LADDER_INVALID", "rule entry must be a mapping")
        rule_id_raw = raw_rule.get("rule_id")
        if not isinstance(rule_id_raw, str) or not rule_id_raw.strip():
            raise err("ERR_S3_RULE_LADDER_INVALID", "rule_id must be a non-empty string")
        rule_id = rule_id_raw.strip()
        if rule_id in seen_rule_ids:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"duplicate rule_id '{rule_id}' in policy",
            )
        seen_rule_ids.add(rule_id)

        precedence_raw = raw_rule.get("precedence")
        if not isinstance(precedence_raw, str) or not precedence_raw.strip():
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' missing precedence",
            )
        precedence = precedence_raw.strip().upper()
        if precedence not in precedence_rank:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' precedence '{precedence}' not declared in precedence_order",
            )

        priority_raw = raw_rule.get("priority")
        if not isinstance(priority_raw, int):
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' priority must be an integer",
            )
        predicate_raw = raw_rule.get("predicate")
        if not isinstance(predicate_raw, str):
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' predicate must be a string expression",
            )
        predicate = predicate_raw.strip()
        if not predicate:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' predicate cannot be empty",
            )

        is_decision_bearing = bool(raw_rule.get("is_decision_bearing", False))
        outcome = raw_rule.get("outcome", {})
        if not isinstance(outcome, Mapping):
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' outcome must be a mapping",
            )

        reason_raw = outcome.get("reason_code")
        reason_code: str | None = None
        if reason_raw is not None:
            if not isinstance(reason_raw, str):
                raise err(
                    "ERR_S3_RULE_LADDER_INVALID",
                    f"rule '{rule_id}' reason_code must be a string when present",
                )
            reason_code = _normalise_reason_code(reason_raw)
            if reason_code not in reason_vocab:
                raise err(
                    "ERR_S3_RULE_LADDER_INVALID",
                    f"rule '{rule_id}' reason_code '{reason_code}' not in vocabulary",
                )

        crossborder_value = outcome.get("crossborder")
        crossborder: bool | None = None
        if crossborder_value is not None:
            if not isinstance(crossborder_value, bool):
                raise err(
                    "ERR_S3_RULE_LADDER_INVALID",
                    f"rule '{rule_id}' crossborder flag must be boolean when present",
                )
            crossborder = crossborder_value

        outcome_tags_raw = outcome.get("tags", [])
        if not isinstance(outcome_tags_raw, Sequence):
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' outcome tags must be an array",
            )
        outcome_tags = tuple(_normalise_tag(tag) for tag in outcome_tags_raw)
        for tag in outcome_tags:
            if tag not in tag_vocab:
                raise err(
                    "ERR_S3_RULE_LADDER_INVALID",
                    f"rule '{rule_id}' tag '{tag}' not in vocabulary",
                )

        row_tags_raw = outcome.get("row_tags", [])
        if not isinstance(row_tags_raw, Sequence):
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' row_tags must be an array",
            )
        row_tags = tuple(_normalise_tag(tag) for tag in row_tags_raw)
        for tag in row_tags:
            if tag not in tag_vocab:
                raise err(
                    "ERR_S3_RULE_LADDER_INVALID",
                    f"rule '{rule_id}' row tag '{tag}' not in vocabulary",
                )

        def _normalise_seq(
            key: str, values: object, normaliser
        ) -> Tuple[str, ...]:
            if values is None:
                return tuple()
            if not isinstance(values, Sequence):
                raise err(
                    "ERR_S3_RULE_LADDER_INVALID",
                    f"rule '{rule_id}' outcome.{key} must be an array when present",
                )
            return tuple(normaliser(value) for value in values)

        admit_countries = _normalise_seq(
            "admit_countries", outcome.get("admit_countries"), _normalise_iso
        )
        admit_named_sets = tuple(
            name.strip().upper()
            for name in outcome.get("admit_named_sets", [])
        )
        deny_countries = _normalise_seq(
            "deny_countries", outcome.get("deny_countries"), _normalise_iso
        )
        deny_named_sets = tuple(
            name.strip().upper()
            for name in outcome.get("deny_named_sets", [])
        )

        for name in (*admit_named_sets, *deny_named_sets):
            if name not in named_sets:
                raise err(
                    "ERR_S3_RULE_LADDER_INVALID",
                    f"rule '{rule_id}' references unknown named set '{name}'",
                )

        rules.append(
            RuleDefinition(
                rule_id=rule_id,
                precedence=precedence,
                precedence_rank=precedence_rank[precedence],
                priority=priority_raw,
                predicate=predicate,
                is_decision_bearing=is_decision_bearing,
                reason_code=reason_code,
                crossborder=crossborder,
                outcome_tags=tuple(sorted(outcome_tags)),
                row_tags=tuple(sorted(row_tags)),
                admit_countries=admit_countries,
                admit_named_sets=admit_named_sets,
                deny_countries=deny_countries,
                deny_named_sets=deny_named_sets,
            )
        )
        if is_decision_bearing:
            decision_rules += 1

    if decision_rules == 0:
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "policy must mark at least one decision-bearing rule",
        )

    return RuleLadder(
        semver=semver,
        version=version,
        precedence_order=precedence_tuple,
        rules=tuple(rules),
        reason_code_vocab=reason_vocab,
        filter_tag_vocab=tag_vocab,
        named_sets=named_sets,
        default_admit_sets=default_admit_tuple,
        default_tags=default_tag_tuple,
    )


class _PredicateEvaluator(ast.NodeVisitor):
    """Safe interpreter for the rule predicate DSL.

    Only a limited subset of Python's expression grammar is supported:
    logical operators (``and``/``or``), unary ``not``, comparisons (``==``,
    ``!=``, ``in``, ``not in``, numeric comparisons), boolean literals, string
    literals, integers/floats, and references to known context variables or
    named country sets.  Any other construct raises ``ERR_S3_RULE_EVAL_DOMAIN``.
    """

    def __init__(self, context: object) -> None:
        self.context = context
        variables: Dict[str, object] = {}
        if hasattr(context, "variable_mapping"):
            base_mapping = getattr(context, "variable_mapping")()
            for key, value in base_mapping.items():
                if value is None:
                    continue
                variables[key] = value
                variables[key.lower()] = value
        self._variables = variables
        named_sets = getattr(context, "named_sets", {})
        self._named_sets = {
            name.upper(): tuple(values) for name, values in named_sets.items()
        }

    @staticmethod
    def _coerce_comparable(left: object, right: object) -> tuple[object, object]:
        numeric_types = (int, float, Decimal)
        if isinstance(left, str) and isinstance(right, numeric_types):
            try:
                return type(right)(left), right
            except Exception:
                pass
        if isinstance(right, str) and isinstance(left, numeric_types):
            try:
                return left, type(left)(right)
            except Exception:
                pass
        return left, right

    def visit(self, node: ast.AST) -> object:
        method = "visit_" + node.__class__.__name__
        visitor = getattr(self, method, None)
        if visitor is None:
            raise err(
                "ERR_S3_RULE_EVAL_DOMAIN",
                f"unsupported expression element '{node.__class__.__name__}'",
            )
        return visitor(node)

    def visit_Expression(self, node: ast.Expression) -> object:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> object:
        if isinstance(node.value, (str, int, float, bool)):
            return node.value
        raise err(
            "ERR_S3_RULE_EVAL_DOMAIN",
            f"unsupported constant type '{type(node.value).__name__}'",
        )

    def visit_Name(self, node: ast.Name) -> object:
        ident = node.id
        lowered = ident.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered == "none":
            return None
        if lowered in self._variables:
            return self._variables[lowered]
        upper = ident.strip().upper()
        if upper in self._named_sets:
            return self._named_sets[upper]
        raise err(
            "ERR_S3_RULE_EVAL_DOMAIN",
            f"unknown symbol '{ident}' in predicate",
        )

    def visit_UnaryOp(self, node: ast.UnaryOp) -> object:
        if isinstance(node.op, ast.Not):
            return not bool(self.visit(node.operand))
        raise err(
            "ERR_S3_RULE_EVAL_DOMAIN",
            f"unsupported unary operator '{node.op.__class__.__name__}'",
        )

    def visit_BoolOp(self, node: ast.BoolOp) -> object:
        if isinstance(node.op, ast.And):
            result = True
            for value in node.values:
                result = result and bool(self.visit(value))
                if not result:
                    break
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for value in node.values:
                result = result or bool(self.visit(value))
                if result:
                    break
            return result
        raise err(
            "ERR_S3_RULE_EVAL_DOMAIN",
            f"unsupported boolean operator '{node.op.__class__.__name__}'",
        )

    def visit_Compare(self, node: ast.Compare) -> object:
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise err(
                "ERR_S3_RULE_EVAL_DOMAIN",
                "predicate comparisons must be simple binary comparisons",
            )
        left = self.visit(node.left)
        right = self.visit(node.comparators[0])
        left, right = self._coerce_comparable(left, right)
        op = node.ops[0]
        if isinstance(op, ast.In):
            return left in right
        if isinstance(op, ast.NotIn):
            return left not in right
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.Gt):
            return left > right
        if isinstance(op, ast.GtE):
            return left >= right
        if isinstance(op, ast.Lt):
            return left < right
        if isinstance(op, ast.LtE):
            return left <= right
        raise err(
            "ERR_S3_RULE_EVAL_DOMAIN",
            f"unsupported comparison '{op.__class__.__name__}'",
        )


def _compile_predicate(predicate: str) -> ast.Expression:
    normalised = predicate.replace("&&", " and ").replace("||", " or ")
    try:
        return ast.parse(normalised, mode="eval")
    except SyntaxError as exc:  # pragma: no cover - configuration error
        raise err(
            "ERR_S3_RULE_EVAL_DOMAIN",
            f"invalid predicate syntax '{predicate}': {exc}",
        ) from exc


def _evaluate_compiled_predicate(expr: ast.Expression, context: object) -> bool:
    evaluator = _PredicateEvaluator(context)
    result = evaluator.visit(expr)
    return bool(result)


def _evaluate_predicate(predicate: str, context: object) -> bool:
    expr = _compile_predicate(predicate)
    return _evaluate_compiled_predicate(expr, context)


def evaluate_rule_ladder(
    ladder: RuleLadder,
    *,
    merchant_id: int,
    home_country_iso: str,
    channel: str,
    mcc: str,
    n_outlets: int,
) -> RuleLadderEvaluation:
    """Evaluate the deterministic rule ladder for a merchant."""

    context = _EvaluationContext(
        merchant_id=merchant_id,
        home_country_iso=home_country_iso,
        channel=channel,
        mcc=mcc,
        n_outlets=n_outlets,
        named_sets=ladder.named_sets,
    )

    fired_trace: list[RuleTraceEntry] = []
    merchant_tags: set[str] = set(ladder.default_tags)
    admitting_map: MutableMapping[str, list[str]] = {}
    denying_map: MutableMapping[str, list[str]] = {}
    row_tags_map: MutableMapping[str, set[str]] = {}

    decision_rule_id: str | None = None
    decision_crossborder: bool | None = None

    sorted_rules = sorted(
        ladder.rules,
        key=lambda rule: (rule.precedence_rank, rule.priority, rule.rule_id),
    )

    for rule in sorted_rules:
        if not _evaluate_predicate(rule.predicate, context):
            continue

        merchant_tags.update(rule.outcome_tags)
        trace_entry = RuleTraceEntry(
            rule_id=rule.rule_id,
            precedence=rule.precedence,
            precedence_rank=rule.precedence_rank,
            priority=rule.priority,
            is_decision_bearing=rule.is_decision_bearing,
            reason_code=rule.reason_code,
            is_decision_source=False,
            tags=tuple(sorted(rule.outcome_tags)),
        )
        fired_trace.append(trace_entry)

        def _extend(target: MutableMapping[str, list[str]], country: str) -> None:
            bucket = target.setdefault(country, [])
            bucket.append(rule.rule_id)

        for iso in rule.admit_countries:
            _extend(admitting_map, iso)
        for name in rule.admit_named_sets:
            for iso in ladder.named_sets[name]:
                _extend(admitting_map, iso)
        for iso in rule.deny_countries:
            _extend(denying_map, iso)
        for name in rule.deny_named_sets:
            for iso in ladder.named_sets[name]:
                _extend(denying_map, iso)
        if rule.row_tags:
            for iso in (*rule.admit_countries,):
                row_tags_map.setdefault(iso, set()).update(rule.row_tags)
            for name in rule.admit_named_sets:
                for iso in ladder.named_sets[name]:
                    row_tags_map.setdefault(iso, set()).update(rule.row_tags)

        if decision_rule_id is None and rule.is_decision_bearing:
            decision_rule_id = rule.rule_id
            decision_crossborder = rule.crossborder
            fired_trace[-1] = RuleTraceEntry(
                rule_id=trace_entry.rule_id,
                precedence=trace_entry.precedence,
                precedence_rank=trace_entry.precedence_rank,
                priority=trace_entry.priority,
                is_decision_bearing=trace_entry.is_decision_bearing,
                reason_code=trace_entry.reason_code,
                is_decision_source=True,
                tags=trace_entry.tags,
            )

    if decision_rule_id is None or decision_crossborder is None:
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "rule ladder did not yield a decision-bearing rule",
        )

    merchant_tag_tuple = tuple(sorted(merchant_tags))

    def _freeze(mapping: MutableMapping[str, list[str]]) -> Dict[str, Tuple[str, ...]]:
        result: Dict[str, Tuple[str, ...]] = {}
        for iso, items in mapping.items():
            result[iso] = tuple(items)
        return result

    row_tags_frozen = {
        iso: tuple(sorted(tags)) for iso, tags in row_tags_map.items()
    }

    return RuleLadderEvaluation(
        eligible_crossborder=bool(decision_crossborder),
        decision_rule_id=decision_rule_id,
        trace=tuple(fired_trace),
        merchant_tags=merchant_tag_tuple,
        admitting_rules_by_country=_freeze(admitting_map),
        denying_rules_by_country=_freeze(denying_map),
        row_tags_by_country=row_tags_frozen,
    )


def _as_decimal(value: object, *, error: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive
        raise err(error, f"unable to parse decimal value '{value}'") from exc


def load_base_weight_policy(
    path: Path,
    *,
    iso_countries: Iterable[str] | None = None,
) -> BaseWeightPolicy:
    """Load the optional base-weight policy artefact."""

    payload = _load_yaml(path)
    semver = payload.get("semver")
    if semver is not None and not isinstance(semver, str):
        raise err("ERR_S3_PRIOR_DOMAIN", "base-weight policy semver must be a string")
    version = payload.get("version")
    if version is not None and not isinstance(version, str):
        raise err("ERR_S3_PRIOR_DOMAIN", "base-weight policy version must be a string")

    if "renormalise" in payload:
        raise err("ERR_S3_PRIOR_DOMAIN", "base-weight policy may not declare renormalise")

    dp = payload.get("dp")
    if not isinstance(dp, int) or dp < 0 or dp > 18:
        raise err("ERR_S3_PRIOR_DOMAIN", "base-weight policy dp must be 0..18")

    raw_constants = payload.get("constants")
    if not isinstance(raw_constants, Mapping) or not raw_constants:
        raise err("ERR_S3_PRIOR_DOMAIN", "base-weight policy must declare constants mapping")
    constants: Dict[str, Decimal] = {}
    for name, value in raw_constants.items():
        key = str(name).strip()
        if not key:
            raise err("ERR_S3_PRIOR_DOMAIN", "constant names must be non-empty strings")
        constant = _as_decimal(value, error="ERR_S3_PRIOR_DOMAIN")
        if constant < Decimal("0"):
            raise err("ERR_S3_PRIOR_DOMAIN", f"constant '{key}' must be non-negative")
        constants[key] = constant

    iso_allowed = {code.upper() for code in iso_countries} if iso_countries else None
    raw_sets = payload.get("sets", {})
    if raw_sets is None:
        raw_sets = {}
    if not isinstance(raw_sets, Mapping):
        raise err("ERR_S3_PRIOR_DOMAIN", "sets must be a mapping when present")
    sets: Dict[str, Tuple[str, ...]] = {}
    for name, values in raw_sets.items():
        set_name = _normalise_tag(str(name))
        if not isinstance(values, Sequence) or not values:
            raise err("ERR_S3_PRIOR_DOMAIN", f"set '{set_name}' must be a non-empty sequence")
        normalised = tuple(_normalise_iso(str(value)) for value in values)
        if iso_allowed is not None:
            unknown = [iso for iso in normalised if iso not in iso_allowed]
            if unknown:
                raise err(
                    "ERR_S3_PRIOR_DOMAIN",
                    f"set '{set_name}' references ISO not present in canonical set: {sorted(unknown)}",
                )
        sets[set_name] = normalised

    normalisation_spec = payload.get("normalisation")
    normalisation: PolicyNormalisation | None = None
    if normalisation_spec is not None:
        if not isinstance(normalisation_spec, Mapping):
            raise err(
                "ERR_S3_PRIOR_DOMAIN",
                "normalisation must be a mapping when present",
            )
        raw_method = normalisation_spec.get("method", "none")
        if not isinstance(raw_method, str) or not raw_method.strip():
            raise err(
                "ERR_S3_PRIOR_DOMAIN",
                "normalisation.method must be a non-empty string",
            )
        method = raw_method.strip().lower()
        target_value = normalisation_spec.get("target")
        target_decimal: Decimal | None = None
        if method in {"l1", "sum_to_target"}:
            if target_value is None:
                target_value = 1
            target_decimal = _as_decimal(target_value, error="ERR_S3_PRIOR_DOMAIN")
            if target_decimal <= Decimal("0"):
                raise err(
                    "ERR_S3_PRIOR_DOMAIN",
                    "normalisation target must be positive when specified",
                )
            if method == "l1":
                method = "sum_to_target"
        elif method != "none":
            raise err(
                "ERR_S3_PRIOR_DOMAIN",
                f"unsupported normalisation method '{method}'",
            )
        normalisation = PolicyNormalisation(method=method, target=target_decimal)

    raw_rules = payload.get("selection_rules")
    if not isinstance(raw_rules, Sequence) or not raw_rules:
        raise err("ERR_S3_PRIOR_DOMAIN", "selection_rules must be a non-empty sequence")

    seen_rule_ids: set[str] = set()
    rules: List[BaseWeightRule] = []
    for entry in raw_rules:
        if not isinstance(entry, Mapping):
            raise err("ERR_S3_PRIOR_DOMAIN", "selection rules must be mappings")
        rule_id = entry.get("id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise err("ERR_S3_PRIOR_DOMAIN", "rule id must be a non-empty string")
        rule_id_norm = rule_id.strip()
        if rule_id_norm in seen_rule_ids:
            raise err("ERR_S3_PRIOR_DOMAIN", f"duplicate rule id '{rule_id_norm}'")
        seen_rule_ids.add(rule_id_norm)

        predicate = entry.get("predicate")
        if not isinstance(predicate, str) or not predicate.strip():
            raise err("ERR_S3_PRIOR_DOMAIN", f"rule '{rule_id_norm}' missing predicate")
        predicate = predicate.strip()
        predicate_ast = _compile_predicate(predicate)

        components_raw = entry.get("score_components", [])
        if components_raw is None:
            components_raw = []
        if not isinstance(components_raw, Sequence):
            raise err(
                "ERR_S3_PRIOR_DOMAIN",
                f"rule '{rule_id_norm}' score_components must be a sequence when present",
            )
        components: List[str] = []
        for name in components_raw:
            key = str(name).strip()
            if not key:
                raise err(
                    "ERR_S3_PRIOR_DOMAIN",
                    f"rule '{rule_id_norm}' contains empty score component reference",
                )
            if key not in constants:
                raise err(
                    "ERR_S3_PRIOR_DOMAIN",
                    f"rule '{rule_id_norm}' references unknown constant '{key}'",
                )
            components.append(key)

        score_value_raw = entry.get("score_value")
        score_value: Decimal | None = None
        if score_value_raw is not None:
            score_value = _as_decimal(score_value_raw, error="ERR_S3_PRIOR_DOMAIN")
            if score_value < Decimal("0"):
                raise err(
                    "ERR_S3_PRIOR_DOMAIN",
                    f"rule '{rule_id_norm}' score_value must be non-negative",
                )

        rules.append(
            BaseWeightRule(
                rule_id=rule_id_norm,
                predicate=predicate,
                predicate_ast=predicate_ast,
                components=tuple(components),
                score_value=score_value,
            )
        )

    return BaseWeightPolicy(
        semver=str(semver) if semver is not None else None,
        version=str(version) if version is not None else None,
        dp=dp,
        constants=constants,
        sets=sets,
        rules=tuple(rules),
        normalisation=normalisation,
    )


def load_thresholds_policy(
    path: Path,
    *,
    iso_countries: Iterable[str] | None = None,
) -> ThresholdsPolicy:
    """Load the optional integerisation thresholds/override policy."""

    payload = _load_yaml(path)
    semver = payload.get("semver")
    if semver is not None and not isinstance(semver, str):
        raise err("ERR_S3_INTEGER_FEASIBILITY", "threshold policy semver must be a string")
    version = payload.get("version")
    if version is not None and not isinstance(version, str):
        raise err("ERR_S3_INTEGER_FEASIBILITY", "threshold policy version must be a string")

    iso_allowed = {code.upper() for code in iso_countries} if iso_countries else None

    def _validate_iso_mapping(
        data: Mapping[str, object],
        field: str,
        allow_none: bool = False,
    ) -> Dict[str, Optional[int]]:
        result: Dict[str, Optional[int]] = {}
        for key, raw_value in data.items():
            iso = _normalise_iso(str(key))
            value: Optional[int]
            if raw_value is None and allow_none:
                value = None
            else:
                if not isinstance(raw_value, int):
                    raise err(
                        "ERR_S3_INTEGER_FEASIBILITY",
                        f"{field} for '{iso}' must be an integer"
                        if not allow_none
                        else f"{field} for '{iso}' must be an integer or null",
                    )
                if raw_value < 0:
                    raise err(
                        "ERR_S3_INTEGER_FEASIBILITY",
                        f"{field} for '{iso}' must be non-negative",
                    )
                value = int(raw_value)
            if iso_allowed is not None and iso not in iso_allowed:
                raise err(
                    "ERR_S3_INTEGER_FEASIBILITY",
                    f"{field} references ISO not present in canonical set: '{iso}'",
                )
            result[iso] = value
        return result

    def _load_new_format() -> ThresholdsPolicy:
        residual_dp = payload.get("dp_resid", 8)
        if not isinstance(residual_dp, int) or residual_dp < 0 or residual_dp > 18:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                "dp_resid must be an integer in 0..18",
            )
        raw_floors = payload.get("floors", {})
        if raw_floors is None:
            raw_floors = {}
        if not isinstance(raw_floors, Mapping):
            raise err("ERR_S3_INTEGER_FEASIBILITY", "floors must be a mapping when present")
        floors = {
            iso: int(value)
            for iso, value in _validate_iso_mapping(raw_floors, "floors").items()
        }
        raw_ceilings = payload.get("ceilings", {})
        if raw_ceilings is None:
            raw_ceilings = {}
        if not isinstance(raw_ceilings, Mapping):
            raise err("ERR_S3_INTEGER_FEASIBILITY", "ceilings must be a mapping when present")
        ceilings = _validate_iso_mapping(raw_ceilings, "ceilings", allow_none=True)
        for iso, ceiling in ceilings.items():
            if ceiling is not None and iso in floors and ceiling < floors[iso]:
                raise err(
                    "ERR_S3_INTEGER_FEASIBILITY",
                    f"ceiling for '{iso}' is below its floor",
                )
        return ThresholdsPolicy(
            semver=str(semver) if semver is not None else None,
            version=str(version) if version is not None else None,
            residual_dp=residual_dp,
            floors=floors,
            ceilings=ceilings,
        )

    if any(key in payload for key in ("dp_resid", "floors", "ceilings")):
        return _load_new_format()

    # Fallback for legacy format (integerisation/bounds overrides).
    integerisation = payload.get("integerisation", {})
    if integerisation is None:
        integerisation = {}
    if not isinstance(integerisation, Mapping):
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "integerisation section must be a mapping when present",
        )
    residual_dp = integerisation.get("residual_dp", 8)
    if not isinstance(residual_dp, int) or residual_dp < 0 or residual_dp > 18:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "integerisation.residual_dp must be an integer in 0..18",
        )

    bounds = payload.get("bounds", {})
    if not isinstance(bounds, Mapping):
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "bounds section must be a mapping when present",
        )
    default_lower = bounds.get("default_lower", 0)
    default_upper = bounds.get("default_upper", 10**9)
    if not isinstance(default_lower, int) or default_lower < 0:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "bounds.default_lower must be a non-negative integer",
        )
    if not isinstance(default_upper, int) or default_upper < default_lower:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "bounds.default_upper must be an integer >= default_lower",
        )
    overrides_block = bounds.get("overrides", [])
    floors: Dict[str, int] = {}
    ceilings: Dict[str, Optional[int]] = {}
    if overrides_block is not None:
        if not isinstance(overrides_block, Sequence):
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                "bounds.overrides must be a sequence when present",
            )
        for entry in overrides_block:
            if not isinstance(entry, Mapping):
                raise err(
                    "ERR_S3_INTEGER_FEASIBILITY",
                    "bounds overrides must be mappings",
                )
            raw_countries = entry.get("countries", [])
            if not isinstance(raw_countries, Sequence) or not raw_countries:
                raise err(
                    "ERR_S3_INTEGER_FEASIBILITY",
                    "bounds override missing countries list",
                )
            countries = tuple(_normalise_iso(str(code)) for code in raw_countries)
            lower = entry.get("lower", default_lower)
            upper = entry.get("upper", default_upper)
            if lower is not None:
                if not isinstance(lower, int) or lower < 0:
                    raise err(
                        "ERR_S3_INTEGER_FEASIBILITY",
                        "bounds override lower must be non-negative integer",
                    )
            if upper is not None:
                if not isinstance(upper, int) or upper < 0:
                    raise err(
                        "ERR_S3_INTEGER_FEASIBILITY",
                        "bounds override upper must be non-negative integer",
                    )
            if lower is not None and upper is not None and lower > upper:
                raise err(
                    "ERR_S3_INTEGER_FEASIBILITY",
                    "bounds override lower cannot exceed upper",
                )
            for iso in countries:
                if iso_allowed is not None and iso not in iso_allowed:
                    raise err(
                        "ERR_S3_INTEGER_FEASIBILITY",
                        f"override references ISO not present in canonical set: '{iso}'",
                    )
                floors[iso] = lower if lower is not None else 0
                ceilings[iso] = upper

    return ThresholdsPolicy(
        semver=str(semver) if semver is not None else None,
        version=str(version) if version is not None else None,
        residual_dp=residual_dp,
        floors=floors,
        ceilings=ceilings,
    )


def _select_base_weight_score(
    policy: BaseWeightPolicy,
    context: _BaseWeightContext,
) -> Optional[Decimal]:
    for rule in policy.rules:
        if _evaluate_compiled_predicate(rule.predicate_ast, context):
            if not rule.components and rule.score_value is None:
                return None
            total = Decimal("0")
            for component in rule.components:
                total += policy.constants[component]
            if rule.score_value is not None:
                total += rule.score_value
            if total < Decimal("0"):
                raise err(
                    "ERR_S3_PRIOR_DOMAIN",
                    f"rule '{rule.rule_id}' produced negative weight",
                )
            return total
    return None


def evaluate_base_weight(
    policy: BaseWeightPolicy,
    *,
    merchant_id: int,
    home_country_iso: str,
    channel: str,
    mcc: str,
    n_outlets: int,
    country_iso: str,
    is_home: bool,
    candidate_rank: int,
    filter_tags: Tuple[str, ...],
    merchant_tags: Tuple[str, ...],
) -> Optional[Decimal]:
    """Evaluate deterministic base-weight rules for a single candidate."""

    context = _BaseWeightContext(
        merchant_id=merchant_id,
        home_country_iso=home_country_iso,
        channel=channel,
        mcc=mcc,
        n_outlets=n_outlets,
        country_iso=country_iso,
        is_home=is_home,
        candidate_rank=candidate_rank,
        filter_tags=filter_tags,
        merchant_tags=merchant_tags,
        named_sets=policy.sets,
    )
    return _select_base_weight_score(policy, context)


__all__ = [
    "RuleLadder",
    "load_rule_ladder",
    "evaluate_rule_ladder",
    "BaseWeightRule",
    "BaseWeightPolicy",
    "PolicyNormalisation",
    "ThresholdsPolicy",
    "load_base_weight_policy",
    "load_thresholds_policy",
    "evaluate_base_weight",
]
