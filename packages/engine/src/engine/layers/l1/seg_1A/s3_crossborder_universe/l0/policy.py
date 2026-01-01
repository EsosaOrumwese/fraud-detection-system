"""Helpers for loading and evaluating the governed S3 rule ladder artefact."""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Sequence, Tuple, List, Optional

from decimal import Decimal

import yaml

from ...s0_foundations.exceptions import err
from ..constants import SITE_SEQUENCE_LIMIT
from .types import (
    RuleDefinition,
    RuleLadder,
    RuleLadderEvaluation,
    RuleTraceEntry,
)

_ASCII_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True)
class BaseWeightPolicy:
    """Deterministic configuration for base-weight priors."""

    semver: str | None
    version: str | None
    dp: int
    beta0: float
    beta_home: float
    beta_rank: float
    log_w_min: float
    log_w_max: float
    w_min: float
    w_max: float


@dataclass(frozen=True)
class ThresholdsPolicy:
    """Integerisation bounds and residual configuration."""

    semver: str | None
    version: str | None
    enabled: bool
    home_min: int
    force_at_least_one_foreign_if_foreign_present: bool
    min_one_per_country_when_feasible: bool
    foreign_cap_mode: str
    on_infeasible: str


@dataclass(frozen=True)
class BoundsPolicy:
    """Per-country capacity caps applied during S3 integerisation."""

    semver: str | None
    version: str | None
    default_upper: int
    overrides: Mapping[str, int]

    def cap_for(self, iso: str) -> int:
        return self.overrides.get(iso.upper(), self.default_upper)


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

    allowed_keys = {
        "semver",
        "version",
        "precedence_order",
        "reason_codes",
        "filter_tags",
        "country_sets",
        "named_sets",
        "reason_code_to_rule_id",
        "rules",
        "default_admit_sets",
        "default_tags",
    }
    unknown_keys = set(payload) - allowed_keys
    if unknown_keys:
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            f"policy contains unknown keys: {sorted(unknown_keys)}",
        )

    raw_reason_codes = payload.get("reason_codes")
    if not isinstance(raw_reason_codes, Sequence) or not raw_reason_codes:
        raise err("ERR_S3_RULE_LADDER_INVALID", "policy must declare reason_codes[]")
    reason_vocab = _sorted_unique_reasons(raw_reason_codes)

    raw_filter_tags = payload.get("filter_tags")
    if not isinstance(raw_filter_tags, Sequence) or not raw_filter_tags:
        raise err("ERR_S3_RULE_LADDER_INVALID", "policy must declare filter_tags[]")
    tag_vocab = _sorted_unique(raw_filter_tags)
    if "HOME" not in tag_vocab:
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "filter_tags must include 'HOME'",
        )

    precedence_order = payload.get("precedence_order")
    if not isinstance(precedence_order, Sequence) or not precedence_order:
        raise err(
            "ERR_S3_RULE_LADDER_INVALID", "policy must declare precedence_order[]"
        )
    precedence_tuple = tuple(str(item).strip().upper() for item in precedence_order)
    expected_precedence = ("DENY", "ALLOW", "CLASS", "LEGAL", "THRESHOLD", "DEFAULT")
    if precedence_tuple != expected_precedence:
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "precedence_order must be the six-class total order "
            f"{list(expected_precedence)}",
        )
    precedence_rank = {name: idx for idx, name in enumerate(precedence_tuple)}
    if len(precedence_rank) != len(precedence_tuple):
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "precedence_order contains duplicate entries",
        )

    raw_named_sets = payload.get("country_sets")
    if raw_named_sets is None:
        raw_named_sets = payload.get("named_sets", {})
    if not isinstance(raw_named_sets, Mapping):
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "country_sets must be a mapping when present",
        )
    named_sets: Dict[str, Tuple[str, ...]] = {}
    for name, raw_set in raw_named_sets.items():
        values = raw_set
        if isinstance(raw_set, Mapping) and "countries" in raw_set:
            values = raw_set.get("countries")
        if values is None:
            values = []
        if not isinstance(values, Sequence):
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"country set '{name}' must be a sequence of ISO2 codes",
            )
        named_sets[name.strip().upper()] = tuple(
            _normalise_iso(code) for code in values
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

    raw_reason_map = payload.get("reason_code_to_rule_id")
    if not isinstance(raw_reason_map, Mapping) or not raw_reason_map:
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "policy must declare reason_code_to_rule_id mapping",
        )
    reason_code_to_rule_id: Dict[str, str] = {}
    for reason, rule_id_raw in raw_reason_map.items():
        if not isinstance(rule_id_raw, str) or not rule_id_raw.strip():
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                "reason_code_to_rule_id values must be non-empty strings",
            )
        reason_code = _normalise_reason_code(str(reason))
        reason_code_to_rule_id[reason_code] = rule_id_raw.strip()
    if set(reason_code_to_rule_id.keys()) != set(reason_vocab):
        missing = set(reason_vocab) - set(reason_code_to_rule_id.keys())
        extra = set(reason_code_to_rule_id.keys()) - set(reason_vocab)
        if missing:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"reason_code_to_rule_id missing codes {sorted(missing)}",
            )
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            f"reason_code_to_rule_id contains unknown codes {sorted(extra)}",
        )
    if len(set(reason_code_to_rule_id.values())) != len(reason_code_to_rule_id):
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "reason_code_to_rule_id must be one-to-one",
        )

    rules: list[RuleDefinition] = []
    seen_rule_ids: set[str] = set()
    decision_rules = 0
    default_rules: list[str] = []
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
        predicate: object = predicate_raw
        if isinstance(predicate_raw, str):
            if not predicate_raw.strip():
                raise err(
                    "ERR_S3_RULE_LADDER_INVALID",
                    f"rule '{rule_id}' predicate cannot be empty",
                )
            predicate = predicate_raw.strip()
        elif isinstance(predicate_raw, Mapping):
            if "op" not in predicate_raw:
                raise err(
                    "ERR_S3_RULE_LADDER_INVALID",
                    f"rule '{rule_id}' predicate missing op",
                )
        else:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' predicate must be a mapping or string",
            )

        is_decision_bearing = bool(raw_rule.get("is_decision_bearing", False))
        outcome = raw_rule.get("outcome", {})
        if not isinstance(outcome, Mapping):
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' outcome must be a mapping",
            )

        reason_raw = outcome.get("reason_code")
        if reason_raw is None:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' missing outcome.reason_code",
            )
        if not isinstance(reason_raw, str):
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' reason_code must be a string",
            )
        reason_code = _normalise_reason_code(reason_raw)
        if reason_code not in reason_vocab:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' reason_code '{reason_code}' not in vocabulary",
            )

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
        rule_row_tags = raw_rule.get("row_tags", row_tags_raw)
        if rule_row_tags is None:
            rule_row_tags = []
        if not isinstance(rule_row_tags, Sequence):
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"rule '{rule_id}' row_tags must be an array",
            )
        row_tags = tuple(_normalise_tag(tag) for tag in rule_row_tags)
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
            "admit_countries",
            raw_rule.get("admit_countries", outcome.get("admit_countries")),
            _normalise_iso,
        )
        admit_sets_raw = raw_rule.get(
            "admit_sets", raw_rule.get("admit_named_sets", outcome.get("admit_sets", ()))
        )
        admit_sets = tuple(str(name).strip().upper() for name in admit_sets_raw or [])
        deny_countries = _normalise_seq(
            "deny_countries",
            raw_rule.get("deny_countries", outcome.get("deny_countries")),
            _normalise_iso,
        )
        deny_sets_raw = raw_rule.get(
            "deny_sets", raw_rule.get("deny_named_sets", outcome.get("deny_sets", ()))
        )
        deny_sets = tuple(str(name).strip().upper() for name in deny_sets_raw or [])

        for name in (*admit_sets, *deny_sets):
            if name not in named_sets:
                raise err(
                    "ERR_S3_RULE_LADDER_INVALID",
                    f"rule '{rule_id}' references unknown country set '{name}'",
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
                outcome_tags=tuple(sorted(outcome_tags)),
                row_tags=tuple(sorted(row_tags)),
                admit_countries=admit_countries,
                admit_sets=admit_sets,
                deny_countries=deny_countries,
                deny_sets=deny_sets,
            )
        )
        if is_decision_bearing:
            decision_rules += 1
        if precedence == "DEFAULT":
            default_rules.append(rule_id)

    if decision_rules == 0:
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "policy must mark at least one decision-bearing rule",
        )
    if len(default_rules) != 1:
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "policy must define exactly one DEFAULT rule",
        )
    default_rule = next(rule for rule in rules if rule.rule_id == default_rules[0])
    if not default_rule.is_decision_bearing:
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            "DEFAULT rule must be decision-bearing",
        )
    if isinstance(default_rule.predicate, Mapping):
        if str(default_rule.predicate.get("op", "")).strip().upper() != "TRUE":
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                "DEFAULT rule predicate must be TRUE",
            )
    elif isinstance(default_rule.predicate, str):
        if default_rule.predicate.strip().upper() != "TRUE":
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                "DEFAULT rule predicate must be TRUE",
            )

    for rule in rules:
        if rule.reason_code is None:
            continue
        mapped_rule = reason_code_to_rule_id.get(rule.reason_code)
        if mapped_rule != rule.rule_id:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                f"reason_code_to_rule_id maps {rule.reason_code} to '{mapped_rule}' "
                f"but rule '{rule.rule_id}' declares that reason",
            )

    return RuleLadder(
        semver=semver,
        version=version,
        precedence_order=precedence_tuple,
        rules=tuple(rules),
        reason_code_vocab=reason_vocab,
        reason_code_to_rule_id=reason_code_to_rule_id,
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


def _normalise_mcc_value(value: object) -> tuple[str, int | None]:
    raw = str(value).strip()
    if not raw:
        return raw, None
    try:
        numeric = int(raw)
    except ValueError:
        numeric = None
    return raw.zfill(4) if raw.isdigit() else raw, numeric


def _resolve_field(context: _EvaluationContext, field: str) -> object:
    mapping = context.variable_mapping()
    if field not in mapping:
        raise err(
            "ERR_S3_RULE_EVAL_DOMAIN",
            f"predicate references unknown field '{field}'",
        )
    return mapping[field]


def _evaluate_structured_predicate(
    predicate: Mapping[str, object],
    context: _EvaluationContext,
) -> bool:
    op = predicate.get("op")
    if not isinstance(op, str) or not op:
        raise err("ERR_S3_RULE_EVAL_DOMAIN", "predicate op must be a string")
    op = op.strip().upper()

    if op == "TRUE":
        return True
    if op == "IN_SET":
        field = predicate.get("field")
        set_name = predicate.get("set")
        if not isinstance(field, str) or not isinstance(set_name, str):
            raise err("ERR_S3_RULE_EVAL_DOMAIN", "IN_SET requires field/set strings")
        value = _resolve_field(context, field)
        members = context.named_sets.get(set_name.strip().upper())
        if members is None:
            raise err(
                "ERR_S3_RULE_EVAL_DOMAIN",
                f"IN_SET references unknown set '{set_name}'",
            )
        return str(value).upper() in {iso.upper() for iso in members}
    if op == "CHANNEL_IN":
        values = predicate.get("values")
        if not isinstance(values, Sequence) or not values:
            raise err(
                "ERR_S3_RULE_EVAL_DOMAIN",
                "CHANNEL_IN requires non-empty values[]",
            )
        channel = str(context.channel)
        return channel in {str(value) for value in values}
    if op == "MCC_IN":
        codes = predicate.get("codes", [])
        ranges = predicate.get("ranges", [])
        if codes is None:
            codes = []
        if ranges is None:
            ranges = []
        if not isinstance(codes, Sequence) or not isinstance(ranges, Sequence):
            raise err(
                "ERR_S3_RULE_EVAL_DOMAIN",
                "MCC_IN requires codes[] and ranges[] sequences",
            )
        mcc_str, mcc_int = _normalise_mcc_value(context.mcc)
        for code in codes:
            code_str, code_int = _normalise_mcc_value(code)
            if code_str and code_str == mcc_str:
                return True
            if mcc_int is not None and code_int is not None and mcc_int == code_int:
                return True
        for raw_range in ranges:
            if not isinstance(raw_range, str) or "-" not in raw_range:
                raise err(
                    "ERR_S3_RULE_EVAL_DOMAIN",
                    f"MCC_IN range '{raw_range}' must be 'min-max'",
                )
            start_raw, end_raw = raw_range.split("-", 1)
            try:
                start = int(start_raw)
                end = int(end_raw)
            except ValueError as exc:
                raise err(
                    "ERR_S3_RULE_EVAL_DOMAIN",
                    f"MCC_IN range '{raw_range}' must be numeric",
                ) from exc
            if mcc_int is not None and start <= mcc_int <= end:
                return True
        return False
    if op == "N_GE":
        value = predicate.get("value")
        if not isinstance(value, int):
            raise err("ERR_S3_RULE_EVAL_DOMAIN", "N_GE requires integer value")
        return int(context.n_outlets) >= value
    if op == "AND":
        args = predicate.get("args")
        if not isinstance(args, Sequence) or not args:
            raise err("ERR_S3_RULE_EVAL_DOMAIN", "AND requires args[]")
        results: list[bool] = []
        for arg in args:
            if not isinstance(arg, Mapping):
                raise err("ERR_S3_RULE_EVAL_DOMAIN", "AND args must be mappings")
            results.append(_evaluate_structured_predicate(arg, context))
        return all(results)
    if op == "OR":
        args = predicate.get("args")
        if not isinstance(args, Sequence) or not args:
            raise err("ERR_S3_RULE_EVAL_DOMAIN", "OR requires args[]")
        results = []
        for arg in args:
            if not isinstance(arg, Mapping):
                raise err("ERR_S3_RULE_EVAL_DOMAIN", "OR args must be mappings")
            results.append(_evaluate_structured_predicate(arg, context))
        return any(results)
    if op == "NOT":
        arg = predicate.get("arg")
        if not isinstance(arg, Mapping):
            raise err("ERR_S3_RULE_EVAL_DOMAIN", "NOT requires arg mapping")
        return not _evaluate_structured_predicate(arg, context)

    raise err("ERR_S3_RULE_EVAL_DOMAIN", f"unsupported predicate op '{op}'")


def _evaluate_predicate(predicate: object, context: _EvaluationContext) -> bool:
    if isinstance(predicate, Mapping):
        return bool(_evaluate_structured_predicate(predicate, context))
    if isinstance(predicate, str):
        expr = _compile_predicate(predicate)
        return _evaluate_compiled_predicate(expr, context)
    raise err(
        "ERR_S3_RULE_EVAL_DOMAIN",
        "predicate must be a mapping or string expression",
    )


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
    fired_rules: list[RuleDefinition] = []
    merchant_tags: set[str] = set(ladder.default_tags)
    admitting_map: MutableMapping[str, list[str]] = {}
    denying_map: MutableMapping[str, list[str]] = {}
    row_tags_map: MutableMapping[str, set[str]] = {}

    sorted_rules = sorted(
        ladder.rules,
        key=lambda rule: (rule.precedence_rank, rule.priority, rule.rule_id),
    )

    for rule in sorted_rules:
        if not _evaluate_predicate(rule.predicate, context):
            continue

        fired_rules.append(rule)
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
        for name in rule.admit_sets:
            for iso in ladder.named_sets[name]:
                _extend(admitting_map, iso)
        for iso in rule.deny_countries:
            _extend(denying_map, iso)
        for name in rule.deny_sets:
            for iso in ladder.named_sets[name]:
                _extend(denying_map, iso)
        if rule.row_tags:
            for iso in (*rule.admit_countries,):
                row_tags_map.setdefault(iso, set()).update(rule.row_tags)
            for name in rule.admit_sets:
                for iso in ladder.named_sets[name]:
                    row_tags_map.setdefault(iso, set()).update(rule.row_tags)

    def _first_decision(precedences: set[str]) -> RuleDefinition | None:
        for rule in fired_rules:
            if rule.precedence in precedences and rule.is_decision_bearing:
                return rule
        return None

    deny_fired = any(rule.precedence == "DENY" for rule in fired_rules)
    allow_fired = any(rule.precedence == "ALLOW" for rule in fired_rules)

    decision_rule: RuleDefinition | None = None
    eligible_crossborder = False
    if deny_fired:
        decision_rule = _first_decision({"DENY"})
        if decision_rule is None:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                "deny rules fired without a decision-bearing DENY rule",
            )
        eligible_crossborder = False
    elif allow_fired:
        decision_rule = _first_decision({"ALLOW"})
        if decision_rule is None:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                "allow rules fired without a decision-bearing ALLOW rule",
            )
        eligible_crossborder = True
    else:
        decision_rule = _first_decision(set(ladder.precedence_order) - {"DENY", "ALLOW"})
        if decision_rule is None:
            raise err(
                "ERR_S3_RULE_LADDER_INVALID",
                "rule ladder did not yield a decision-bearing rule",
            )
        eligible_crossborder = decision_rule.precedence not in {"DEFAULT", "DENY"}

    fired_trace = [
        RuleTraceEntry(
            rule_id=entry.rule_id,
            precedence=entry.precedence,
            precedence_rank=entry.precedence_rank,
            priority=entry.priority,
            is_decision_bearing=entry.is_decision_bearing,
            reason_code=entry.reason_code,
            is_decision_source=(entry.rule_id == decision_rule.rule_id),
            tags=entry.tags,
        )
        for entry in fired_trace
    ]

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
        eligible_crossborder=bool(eligible_crossborder),
        decision_rule_id=decision_rule.rule_id,
        trace=tuple(fired_trace),
        merchant_tags=merchant_tag_tuple,
        admitting_rules_by_country=_freeze(admitting_map),
        denying_rules_by_country=_freeze(denying_map),
        row_tags_by_country=row_tags_frozen,
    )


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
    if version is None or not isinstance(version, str) or not version.strip():
        raise err("ERR_S3_PRIOR_DOMAIN", "base-weight policy version must be a string")

    allowed_keys = {"semver", "version", "dp", "model", "bounds"}
    unknown = set(payload) - allowed_keys
    if unknown:
        raise err(
            "ERR_S3_PRIOR_DOMAIN",
            f"base-weight policy contains unknown keys: {sorted(unknown)}",
        )

    dp = payload.get("dp")
    if not isinstance(dp, int) or dp < 0 or dp > 255:
        raise err("ERR_S3_PRIOR_DOMAIN", "base-weight policy dp must be 0..255")

    model = payload.get("model")
    if not isinstance(model, Mapping):
        raise err("ERR_S3_PRIOR_DOMAIN", "base-weight policy missing model block")
    kind = model.get("kind")
    if kind != "loglinear_rank_home":
        raise err(
            "ERR_S3_PRIOR_DOMAIN",
            "base-weight model.kind must be 'loglinear_rank_home'",
        )
    coeffs = model.get("coeffs")
    if not isinstance(coeffs, Mapping):
        raise err("ERR_S3_PRIOR_DOMAIN", "model.coeffs must be a mapping")

    def _require_float(name: str) -> float:
        value = coeffs.get(name)
        if not isinstance(value, (int, float)):
            raise err(
                "ERR_S3_PRIOR_DOMAIN",
                f"model.coeffs.{name} must be numeric",
            )
        return float(value)

    beta0 = _require_float("beta0")
    beta_home = _require_float("beta_home")
    beta_rank = _require_float("beta_rank")

    bounds = payload.get("bounds")
    if not isinstance(bounds, Mapping):
        raise err("ERR_S3_PRIOR_DOMAIN", "base-weight policy bounds must be a mapping")
    log_w_min = bounds.get("log_w_min")
    log_w_max = bounds.get("log_w_max")
    w_min = bounds.get("w_min")
    w_max = bounds.get("w_max")
    if not isinstance(log_w_min, (int, float)) or not isinstance(log_w_max, (int, float)):
        raise err("ERR_S3_PRIOR_DOMAIN", "bounds.log_w_min/log_w_max must be numeric")
    if not isinstance(w_min, (int, float)) or not isinstance(w_max, (int, float)):
        raise err("ERR_S3_PRIOR_DOMAIN", "bounds.w_min/w_max must be numeric")
    if float(log_w_min) >= float(log_w_max):
        raise err("ERR_S3_PRIOR_DOMAIN", "log_w_min must be < log_w_max")
    if float(w_min) <= 0.0 or float(w_max) <= float(w_min):
        raise err("ERR_S3_PRIOR_DOMAIN", "w_min must be > 0 and < w_max")

    return BaseWeightPolicy(
        semver=str(semver) if semver is not None else None,
        version=str(version),
        dp=int(dp),
        beta0=beta0,
        beta_home=beta_home,
        beta_rank=beta_rank,
        log_w_min=float(log_w_min),
        log_w_max=float(log_w_max),
        w_min=float(w_min),
        w_max=float(w_max),
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

    allowed = {
        "semver",
        "version",
        "enabled",
        "home_min",
        "force_at_least_one_foreign_if_foreign_present",
        "min_one_per_country_when_feasible",
        "foreign_cap_mode",
        "on_infeasible",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            f"thresholds policy contains unknown keys: {sorted(unknown)}",
        )

    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise err("ERR_S3_INTEGER_FEASIBILITY", "enabled must be a boolean")
    home_min = payload.get("home_min")
    if not isinstance(home_min, int) or home_min < 0:
        raise err("ERR_S3_INTEGER_FEASIBILITY", "home_min must be a non-negative integer")
    force_foreign = payload.get("force_at_least_one_foreign_if_foreign_present")
    if not isinstance(force_foreign, bool):
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "force_at_least_one_foreign_if_foreign_present must be boolean",
        )
    min_one = payload.get("min_one_per_country_when_feasible")
    if not isinstance(min_one, bool):
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "min_one_per_country_when_feasible must be boolean",
        )
    foreign_cap_mode = payload.get("foreign_cap_mode")
    if foreign_cap_mode not in {"none", "n_minus_home_min"}:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "foreign_cap_mode must be 'none' or 'n_minus_home_min'",
        )
    on_infeasible = payload.get("on_infeasible")
    if on_infeasible != "fail":
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "on_infeasible must be 'fail'",
        )

    return ThresholdsPolicy(
        semver=str(semver) if semver is not None else None,
        version=str(version) if version is not None else None,
        enabled=enabled,
        home_min=int(home_min),
        force_at_least_one_foreign_if_foreign_present=force_foreign,
        min_one_per_country_when_feasible=min_one,
        foreign_cap_mode=foreign_cap_mode,
        on_infeasible=on_infeasible,
    )


def load_bounds_policy(
    path: Path,
    *,
    iso_countries: Iterable[str] | None = None,
) -> BoundsPolicy:
    """Load per-country caps that preserve the 6-digit site_id envelope."""

    payload = _load_yaml(path)
    semver = payload.get("semver")
    if semver is not None and not isinstance(semver, str):
        raise err("ERR_S3_INTEGER_FEASIBILITY", "bounds policy semver must be a string")
    version = payload.get("version")
    if version is not None and not isinstance(version, str):
        raise err("ERR_S3_INTEGER_FEASIBILITY", "bounds policy version must be a string")

    default_upper = payload.get("default_upper", SITE_SEQUENCE_LIMIT)
    if not isinstance(default_upper, int) or default_upper <= 0:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "default_upper must be a positive integer",
        )
    if default_upper > SITE_SEQUENCE_LIMIT:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            f"default_upper must be <= {SITE_SEQUENCE_LIMIT}",
        )

    iso_allowed = {code.upper() for code in iso_countries} if iso_countries else None
    raw_overrides = payload.get("overrides", {})
    if raw_overrides is None:
        raw_overrides = {}
    if not isinstance(raw_overrides, Mapping):
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "overrides must be a mapping when present",
        )

    overrides: Dict[str, int] = {}
    for key, raw_value in raw_overrides.items():
        iso = _normalise_iso(str(key))
        if iso_allowed is not None and iso not in iso_allowed:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                f"override references ISO not present in canonical set: '{iso}'",
            )
        if not isinstance(raw_value, int) or raw_value <= 0:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                f"override for '{iso}' must be a positive integer",
            )
        if raw_value > SITE_SEQUENCE_LIMIT:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                (
                    f"override for '{iso}' exceeds site_id capacity "
                    f"(max {SITE_SEQUENCE_LIMIT})"
                ),
            )
        overrides[iso] = raw_value

    return BoundsPolicy(
        semver=str(semver) if semver is not None else None,
        version=str(version) if version is not None else None,
        default_upper=int(default_upper),
        overrides=overrides,
    )


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
    """Evaluate deterministic base-weight priors for a single candidate."""

    if candidate_rank < 0:
        raise err("ERR_S3_PRIOR_DOMAIN", "candidate_rank must be non-negative")

    x_home = 1.0 if is_home else 0.0
    x_rank = float(candidate_rank)
    log_w = policy.beta0 + policy.beta_home * x_home + policy.beta_rank * x_rank
    log_w = max(min(log_w, policy.log_w_max), policy.log_w_min)
    weight = math.exp(log_w)
    if weight < policy.w_min:
        weight = policy.w_min
    if weight > policy.w_max:
        weight = policy.w_max
    if weight <= 0.0:
        raise err("ERR_S3_PRIOR_DOMAIN", "base-weight prior must be positive")
    return Decimal(str(weight))


__all__ = [
    "RuleLadder",
    "load_rule_ladder",
    "evaluate_rule_ladder",
    "BaseWeightPolicy",
    "ThresholdsPolicy",
    "BoundsPolicy",
    "load_base_weight_policy",
    "load_thresholds_policy",
    "load_bounds_policy",
    "evaluate_base_weight",
]
