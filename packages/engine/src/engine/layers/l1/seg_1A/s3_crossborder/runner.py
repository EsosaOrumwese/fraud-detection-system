"""S3 cross-border candidate set runner for Segment 1A."""

from __future__ import annotations

import datetime as dt
import json
import math
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import polars as pl
import yaml
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import validate_dataframe
from engine.contracts.loader import (
    find_dataset_entry,
    load_artefact_registry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import (
    ContractError,
    EngineFailure,
    InputResolutionError,
    SchemaValidationError,
)
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_ns, utc_now_rfc3339_micro
from engine.layers.l1.seg_1A.s0_foundations.validation_bundle import write_failure_record


MODULE_S3 = "1A.s3_crossborder"
DATASET_HURDLE = "rng_event_hurdle_bernoulli"
DATASET_NB_FINAL = "rng_event_nb_final"
DATASET_CANDIDATE = "s3_candidate_set"
DATASET_PRIORS = "s3_base_weight_priors"
DATASET_COUNTS = "s3_integerised_counts"
DATASET_SITE_SEQUENCE = "s3_site_sequence"

PRECEDENCE_CLASSES = ("DENY", "ALLOW", "CLASS", "LEGAL", "THRESHOLD", "DEFAULT")
CHANNEL_VALUES = {"card_present", "card_not_present"}
DP_RESID = 8


@dataclass(frozen=True)
class S3RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    candidate_set_path: Path
    base_weight_priors_path: Path
    integerised_counts_path: Path
    site_sequence_path: Path


@dataclass(frozen=True)
class Rule:
    rule_id: str
    precedence: str
    priority: int
    is_decision_bearing: bool
    predicate: dict
    outcome_reason_code: str
    outcome_tags: tuple[str, ...]
    admit_countries: frozenset[str]
    deny_countries: frozenset[str]
    row_tags: tuple[str, ...]


@dataclass(frozen=True)
class RuleLadder:
    precedence_order: tuple[str, ...]
    precedence_rank: dict[str, int]
    reason_codes: tuple[str, ...]
    filter_tags: tuple[str, ...]
    country_sets: dict[str, frozenset[str]]
    reason_code_to_rule_id: dict[str, str]
    rules: tuple[Rule, ...]
    rules_by_id: dict[str, Rule]


@dataclass(frozen=True)
class BaseWeightPolicy:
    version: str
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
    semver: str
    version: str
    enabled: bool
    home_min: int
    force_at_least_one_foreign_if_foreign_present: bool
    min_one_per_country_when_feasible: bool
    foreign_cap_mode: str
    on_infeasible: str


class _StepTimer:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._start = time.monotonic()
        self._last = self._start

    def info(self, message: str) -> None:
        now = time.monotonic()
        elapsed = now - self._start
        delta = now - self._last
        self._last = now
        self._logger.info("%s (elapsed=%.2fs, delta=%.2fs)", message, elapsed, delta)


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing YAML file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _pick_latest_run_receipt(runs_root: Path) -> Path:
    candidates = sorted(
        runs_root.glob("*/run_receipt.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        raise InputResolutionError(f"No run_receipt.json found under {runs_root}")
    return candidates[-1]


def _resolve_run_receipt(runs_root: Path, run_id: Optional[str]) -> tuple[Path, dict]:
    if run_id:
        receipt_path = runs_root / run_id / "run_receipt.json"
        return receipt_path, _load_json(receipt_path)
    receipt_path = _pick_latest_run_receipt(runs_root)
    return receipt_path, _load_json(receipt_path)


def _resolve_run_path(
    run_paths: RunPaths, path_template: str, tokens: dict[str, str]
) -> Path:
    path = path_template
    for key, value in tokens.items():
        path = path.replace(f"{{{key}}}", value)
    return run_paths.run_root / path


def _resolve_run_glob(
    run_paths: RunPaths, path_template: str, tokens: dict[str, str]
) -> list[Path]:
    path = path_template
    for key, value in tokens.items():
        path = path.replace(f"{{{key}}}", value)
    if "*" in path:
        return sorted(run_paths.run_root.glob(path))
    return [run_paths.run_root / path]


def _segment_state_runs_path(
    run_paths: RunPaths, dictionary: dict, utc_day: str
) -> Path:
    entry = find_dataset_entry(dictionary, "segment_state_runs").entry
    path_template = entry["path"]
    path = path_template.replace("{utc_day}", utc_day)
    return run_paths.run_root / path


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        handle.write("\n")


def _schema_from_pack(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        node = node[part]
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": schema_pack.get("$defs", {}),
    }
    schema.update(node)
    unevaluated = None
    if isinstance(schema.get("allOf"), list):
        for subschema in schema["allOf"]:
            if not isinstance(subschema, dict):
                continue
            if "unevaluatedProperties" in subschema:
                if unevaluated is None:
                    unevaluated = subschema["unevaluatedProperties"]
                subschema.pop("unevaluatedProperties", None)
    if unevaluated is not None and "unevaluatedProperties" not in schema:
        schema["unevaluatedProperties"] = unevaluated
    return schema


def _iter_jsonl_files(paths: Iterable[Path]) -> Iterable[tuple[Path, int, dict]]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                yield path, line_no, json.loads(line)


def _select_dataset_file(dataset_id: str, dataset_path: Path) -> Path:
    if dataset_path.is_file():
        return dataset_path
    if not dataset_path.exists():
        raise InputResolutionError(f"Dataset path does not exist: {dataset_path}")
    if not dataset_path.is_dir():
        raise InputResolutionError(f"Dataset path is not a file or dir: {dataset_path}")
    explicit = dataset_path / f"{dataset_id}.parquet"
    if explicit.exists():
        return explicit
    parquet_files = sorted(dataset_path.glob("*.parquet"))
    if len(parquet_files) == 1:
        return parquet_files[0]
    raise InputResolutionError(
        f"Unable to resolve dataset file in {dataset_path}; "
        f"expected {explicit.name} or a single parquet file."
    )


def _write_parquet_partition(
    df: pl.DataFrame, target_root: Path, tmp_root: Path, dataset_id: str
) -> None:
    tmp_dir = tmp_root / f"{dataset_id}_{uuid.uuid4().hex}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_dir / "part-00000.parquet"
    df.write_parquet(tmp_file)
    target_root.parent.mkdir(parents=True, exist_ok=True)
    if target_root.exists():
        shutil.rmtree(target_root)
    tmp_dir.replace(target_root)


def _dataset_has_parquet(root: Path) -> bool:
    if not root.exists():
        return False
    if root.is_file() and root.suffix == ".parquet":
        return True
    if root.is_dir():
        return any(root.glob("*.parquet"))
    return False


def _load_sealed_inputs(path: Path) -> list[dict]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise InputResolutionError("sealed_inputs_1A payload must be a list.")
    return payload


def _sealed_path(sealed_inputs: list[dict], asset_id: str) -> Path:
    for entry in sealed_inputs:
        if entry.get("asset_id") == asset_id:
            raw_path = entry.get("path")
            if not raw_path:
                raise InputResolutionError(f"sealed_inputs_1A missing path for {asset_id}")
            return Path(raw_path)
    raise InputResolutionError(f"sealed_inputs_1A missing asset_id {asset_id}")


def _load_iso_set(path: Path) -> set[str]:
    df = pl.read_parquet(path)
    if "country_iso" not in df.columns:
        raise InputResolutionError("iso3166_canonical_2024 missing country_iso column.")
    return set(df["country_iso"].to_list())


def _validate_merchants(
    merchant_path: Path,
    ingress_schema: dict,
    iso_set: set[str],
) -> pl.DataFrame:
    merchant_df = (
        pl.read_parquet(merchant_path)
        if merchant_path.suffix == ".parquet"
        else pl.read_csv(merchant_path)
    )
    validate_dataframe(merchant_df.iter_rows(named=True), ingress_schema, "merchant_ids")
    bad_iso = (
        merchant_df.filter(~pl.col("home_country_iso").is_in(list(iso_set)))
        .select("home_country_iso")
        .unique()
    )
    if bad_iso.height > 0:
        raise EngineFailure(
            "F1",
            "home_iso_fk",
            "S3",
            MODULE_S3,
            {"iso": bad_iso.to_series().to_list()},
        )
    return merchant_df


def _validate_schema_payload(
    payload: dict, schema: dict, label: str
) -> None:
    validator = Draft202012Validator(schema)
    errors = []
    for error in validator.iter_errors(payload):
        field = ".".join(str(part) for part in error.path) if error.path else ""
        errors.append({"row_index": 0, "field": field, "message": error.message})
    if errors:
        lines = [
            f"row {item['row_index']}: {item['field']} {item['message']}".strip()
            for item in errors
        ]
        raise SchemaValidationError(
            f"{label} schema validation failed:\n" + "\n".join(lines),
            errors,
        )


def _compile_predicate(node: dict, country_sets: dict[str, frozenset[str]]) -> dict:
    op = node.get("op")
    if op == "TRUE":
        return {"op": "TRUE"}
    if op == "IN_SET":
        field = node.get("field")
        set_name = node.get("set")
        if field != "home_country_iso":
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"unsupported IN_SET field={field}"},
            )
        if set_name not in country_sets:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"unknown country_set {set_name}"},
            )
        return {"op": "IN_SET", "field": field, "set": country_sets[set_name]}
    if op == "CHANNEL_IN":
        values = node.get("values") or []
        if not isinstance(values, list):
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": "CHANNEL_IN values must be a list"},
            )
        parsed = [str(value) for value in values]
        unknown = sorted(set(parsed) - CHANNEL_VALUES)
        if unknown:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"CHANNEL_IN unknown values {unknown}"},
            )
        return {"op": "CHANNEL_IN", "values": set(parsed)}
    if op == "MCC_IN":
        codes = node.get("codes") or []
        ranges = node.get("ranges") or []
        if not isinstance(codes, list) or not isinstance(ranges, list):
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": "MCC_IN codes/ranges must be lists"},
            )
        code_set = set()
        for value in codes:
            code = int(value)
            if code < 0 or code > 9999:
                raise EngineFailure(
                    "F3",
                    "s3_rule_ladder_invalid",
                    "S3",
                    MODULE_S3,
                    {"detail": f"MCC_IN code out of range: {code}"},
                )
            code_set.add(code)
        range_list = []
        for raw in ranges:
            if not isinstance(raw, str) or "-" not in raw:
                raise EngineFailure(
                    "F3",
                    "s3_rule_ladder_invalid",
                    "S3",
                    MODULE_S3,
                    {"detail": f"MCC_IN range invalid: {raw}"},
                )
            start_s, end_s = raw.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if start < 0 or end > 9999 or start > end:
                raise EngineFailure(
                    "F3",
                    "s3_rule_ladder_invalid",
                    "S3",
                    MODULE_S3,
                    {"detail": f"MCC_IN range invalid: {raw}"},
                )
            range_list.append((start, end))
        return {"op": "MCC_IN", "codes": code_set, "ranges": range_list}
    if op == "N_GE":
        value = int(node.get("value"))
        return {"op": "N_GE", "value": value}
    if op == "AND":
        args = node.get("args") or []
        if not isinstance(args, list) or not args:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": "AND requires non-empty args"},
            )
        return {"op": "AND", "args": [_compile_predicate(arg, country_sets) for arg in args]}
    if op == "OR":
        args = node.get("args") or []
        if not isinstance(args, list) or not args:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": "OR requires non-empty args"},
            )
        return {"op": "OR", "args": [_compile_predicate(arg, country_sets) for arg in args]}
    if op == "NOT":
        arg = node.get("arg")
        if not isinstance(arg, dict):
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": "NOT requires arg"},
            )
        return {"op": "NOT", "arg": _compile_predicate(arg, country_sets)}
    raise EngineFailure(
        "F3",
        "s3_rule_ladder_invalid",
        "S3",
        MODULE_S3,
        {"detail": f"unknown predicate op {op}"},
    )


def _eval_predicate(node: dict, context: dict) -> bool:
    op = node["op"]
    if op == "TRUE":
        return True
    if op == "IN_SET":
        return context[node["field"]] in node["set"]
    if op == "CHANNEL_IN":
        return context["channel"] in node["values"]
    if op == "MCC_IN":
        mcc = context["mcc"]
        if mcc in node["codes"]:
            return True
        for start, end in node["ranges"]:
            if start <= mcc <= end:
                return True
        return False
    if op == "N_GE":
        return context["n_outlets"] >= node["value"]
    if op == "AND":
        return all(_eval_predicate(arg, context) for arg in node["args"])
    if op == "OR":
        return any(_eval_predicate(arg, context) for arg in node["args"])
    if op == "NOT":
        return not _eval_predicate(node["arg"], context)
    raise EngineFailure(
        "F3",
        "s3_rule_ladder_invalid",
        "S3",
        MODULE_S3,
        {"detail": f"unknown predicate op {op}"},
    )

def _load_rule_ladder(
    path: Path,
    schema_layer1: dict,
    iso_set: set[str],
) -> RuleLadder:
    payload = _load_yaml(path)
    schema = _schema_from_pack(schema_layer1, "#/policy/s3_rule_ladder")
    _validate_schema_payload(payload, schema, "policy.s3.rule_ladder")

    precedence_order = tuple(payload.get("precedence_order") or [])
    if set(precedence_order) != set(PRECEDENCE_CLASSES) or len(precedence_order) != len(
        PRECEDENCE_CLASSES
    ):
        raise EngineFailure(
            "F3",
            "s3_rule_ladder_invalid",
            "S3",
            MODULE_S3,
            {"detail": "precedence_order must contain DENY, ALLOW, CLASS, LEGAL, THRESHOLD, DEFAULT"},
        )
    precedence_rank = {value: idx for idx, value in enumerate(precedence_order)}

    reason_codes = tuple(payload.get("reason_codes") or [])
    if len(reason_codes) != len(set(reason_codes)):
        raise EngineFailure(
            "F3",
            "s3_rule_ladder_invalid",
            "S3",
            MODULE_S3,
            {"detail": "reason_codes must be unique"},
        )
    filter_tags = tuple(payload.get("filter_tags") or [])
    if len(filter_tags) != len(set(filter_tags)):
        raise EngineFailure(
            "F3",
            "s3_rule_ladder_invalid",
            "S3",
            MODULE_S3,
            {"detail": "filter_tags must be unique"},
        )
    if "HOME" not in filter_tags:
        raise EngineFailure(
            "F3",
            "s3_rule_ladder_invalid",
            "S3",
            MODULE_S3,
            {"detail": "filter_tags must include HOME"},
        )

    country_sets = {}
    for name, values in (payload.get("country_sets") or {}).items():
        if not isinstance(values, list):
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"country_set {name} must be a list"},
            )
        codes = [str(value) for value in values]
        unknown = sorted(set(codes) - iso_set)
        if unknown:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"country_set {name} contains unknown ISO {unknown}"},
            )
        country_sets[name] = frozenset(codes)

    reason_code_to_rule_id = dict(payload.get("reason_code_to_rule_id") or {})
    if set(reason_code_to_rule_id.keys()) != set(reason_codes):
        raise EngineFailure(
            "F3",
            "s3_rule_ladder_invalid",
            "S3",
            MODULE_S3,
            {"detail": "reason_code_to_rule_id must cover all reason_codes"},
        )
    if len(set(reason_code_to_rule_id.values())) != len(reason_code_to_rule_id):
        raise EngineFailure(
            "F3",
            "s3_rule_ladder_invalid",
            "S3",
            MODULE_S3,
            {"detail": "reason_code_to_rule_id must be one-to-one"},
        )

    rules = []
    rules_by_id: dict[str, Rule] = {}
    default_rules = []
    for raw in payload.get("rules") or []:
        rule_id = str(raw.get("rule_id"))
        if rule_id in rules_by_id:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"duplicate rule_id {rule_id}"},
            )
        precedence = str(raw.get("precedence"))
        if precedence not in precedence_rank:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"unknown precedence {precedence}"},
            )
        priority = int(raw.get("priority"))
        is_decision_bearing = bool(raw.get("is_decision_bearing"))
        predicate = raw.get("predicate") or {}
        outcome = raw.get("outcome") or {}
        reason_code = str(outcome.get("reason_code"))
        if reason_code not in reason_codes:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"unknown reason_code {reason_code}"},
            )
        tags = tuple(str(tag) for tag in outcome.get("tags") or [])
        unknown_tags = sorted(set(tags) - set(filter_tags))
        if unknown_tags:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"rule {rule_id} has unknown tags {unknown_tags}"},
            )

        row_tags = tuple(str(tag) for tag in raw.get("row_tags") or [])
        unknown_row_tags = sorted(set(row_tags) - set(filter_tags))
        if unknown_row_tags:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"rule {rule_id} has unknown row_tags {unknown_row_tags}"},
            )

        admit_countries = set()
        deny_countries = set()
        for value in raw.get("admit_countries") or []:
            admit_countries.add(str(value))
        for value in raw.get("deny_countries") or []:
            deny_countries.add(str(value))
        for set_name in raw.get("admit_sets") or []:
            if set_name not in country_sets:
                raise EngineFailure(
                    "F3",
                    "s3_rule_ladder_invalid",
                    "S3",
                    MODULE_S3,
                    {"detail": f"rule {rule_id} references unknown admit_set {set_name}"},
                )
            admit_countries.update(country_sets[set_name])
        for set_name in raw.get("deny_sets") or []:
            if set_name not in country_sets:
                raise EngineFailure(
                    "F3",
                    "s3_rule_ladder_invalid",
                    "S3",
                    MODULE_S3,
                    {"detail": f"rule {rule_id} references unknown deny_set {set_name}"},
                )
            deny_countries.update(country_sets[set_name])

        unknown_admit = sorted(set(admit_countries) - iso_set)
        if unknown_admit:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"rule {rule_id} admit_countries unknown {unknown_admit}"},
            )
        unknown_deny = sorted(set(deny_countries) - iso_set)
        if unknown_deny:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"rule {rule_id} deny_countries unknown {unknown_deny}"},
            )

        if reason_code_to_rule_id.get(reason_code) != rule_id:
            raise EngineFailure(
                "F3",
                "s3_rule_ladder_invalid",
                "S3",
                MODULE_S3,
                {"detail": f"reason_code_to_rule_id mismatch for {reason_code}"},
            )

        compiled_predicate = _compile_predicate(predicate, country_sets)
        rule = Rule(
            rule_id=rule_id,
            precedence=precedence,
            priority=priority,
            is_decision_bearing=is_decision_bearing,
            predicate=compiled_predicate,
            outcome_reason_code=reason_code,
            outcome_tags=tags,
            admit_countries=frozenset(admit_countries),
            deny_countries=frozenset(deny_countries),
            row_tags=row_tags,
        )
        rules.append(rule)
        rules_by_id[rule_id] = rule
        if precedence == "DEFAULT" and is_decision_bearing:
            default_rules.append(rule)

    if len(default_rules) != 1:
        raise EngineFailure(
            "F3",
            "s3_rule_ladder_invalid",
            "S3",
            MODULE_S3,
            {"detail": "exactly one decision-bearing DEFAULT rule is required"},
        )
    if default_rules[0].predicate.get("op") != "TRUE":
        raise EngineFailure(
            "F3",
            "s3_rule_ladder_invalid",
            "S3",
            MODULE_S3,
            {"detail": "DEFAULT rule must use TRUE predicate"},
        )
    missing_rule_ids = sorted(
        set(reason_code_to_rule_id.values()) - set(rules_by_id.keys())
    )
    if missing_rule_ids:
        raise EngineFailure(
            "F3",
            "s3_rule_ladder_invalid",
            "S3",
            MODULE_S3,
            {"detail": f"reason_code_to_rule_id references unknown rules {missing_rule_ids}"},
        )

    return RuleLadder(
        precedence_order=precedence_order,
        precedence_rank=precedence_rank,
        reason_codes=reason_codes,
        filter_tags=filter_tags,
        country_sets=country_sets,
        reason_code_to_rule_id=reason_code_to_rule_id,
        rules=tuple(rules),
        rules_by_id=rules_by_id,
    )


def _load_base_weight_policy(path: Path, schema_layer1: dict) -> BaseWeightPolicy:
    payload = _load_yaml(path)
    schema = _schema_from_pack(schema_layer1, "#/policy/s3_base_weight")
    _validate_schema_payload(payload, schema, "policy.s3.base_weight")

    dp = int(payload.get("dp"))
    if dp < 0 or dp > 255:
        raise EngineFailure(
            "F3",
            "s3_weight_config",
            "S3",
            MODULE_S3,
            {"detail": f"dp out of range: {dp}"},
        )
    model = payload.get("model") or {}
    if model.get("kind") != "loglinear_rank_home":
        raise EngineFailure(
            "F3",
            "s3_weight_config",
            "S3",
            MODULE_S3,
            {"detail": "unsupported model kind"},
        )
    coeffs = model.get("coeffs") or {}
    bounds = payload.get("bounds") or {}
    return BaseWeightPolicy(
        version=str(payload.get("version")),
        dp=dp,
        beta0=float(coeffs.get("beta0")),
        beta_home=float(coeffs.get("beta_home")),
        beta_rank=float(coeffs.get("beta_rank")),
        log_w_min=float(bounds.get("log_w_min")),
        log_w_max=float(bounds.get("log_w_max")),
        w_min=float(bounds.get("w_min")),
        w_max=float(bounds.get("w_max")),
    )


def _load_thresholds_policy(path: Path, schema_layer1: dict) -> ThresholdsPolicy:
    payload = _load_yaml(path)
    schema = _schema_from_pack(schema_layer1, "#/policy/s3_thresholds")
    _validate_schema_payload(payload, schema, "policy.s3.thresholds")
    return ThresholdsPolicy(
        semver=str(payload.get("semver")),
        version=str(payload.get("version")),
        enabled=bool(payload.get("enabled")),
        home_min=int(payload.get("home_min")),
        force_at_least_one_foreign_if_foreign_present=bool(
            payload.get("force_at_least_one_foreign_if_foreign_present")
        ),
        min_one_per_country_when_feasible=bool(
            payload.get("min_one_per_country_when_feasible")
        ),
        foreign_cap_mode=str(payload.get("foreign_cap_mode")),
        on_infeasible=str(payload.get("on_infeasible")),
    )


def _load_hurdle_events(
    paths: Iterable[Path],
    schema_layer1: dict,
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
) -> dict[int, bool]:
    schema = _schema_from_pack(schema_layer1, "#/rng/events/hurdle_bernoulli")
    validator = Draft202012Validator(schema)
    result: dict[int, bool] = {}
    errors: list[dict] = []
    for path, line_no, payload in _iter_jsonl_files(paths):
        for error in validator.iter_errors(payload):
            field = ".".join(str(part) for part in error.path) if error.path else ""
            errors.append(
                {
                    "row_index": line_no,
                    "field": field,
                    "message": f"{path}:{line_no} {error.message}",
                }
            )
            break
        if errors:
            break
        if payload.get("seed") != seed:
            raise InputResolutionError(
                f"hurdle_bernoulli seed mismatch in {path}:{line_no}"
            )
        if payload.get("parameter_hash") != parameter_hash:
            raise InputResolutionError(
                f"hurdle_bernoulli parameter_hash mismatch in {path}:{line_no}"
            )
        if payload.get("manifest_fingerprint") != manifest_fingerprint:
            raise InputResolutionError(
                f"hurdle_bernoulli manifest_fingerprint mismatch in {path}:{line_no}"
            )
        if payload.get("run_id") != run_id:
            raise InputResolutionError(
                f"hurdle_bernoulli run_id mismatch in {path}:{line_no}"
            )
        merchant_id = int(payload.get("merchant_id"))
        if merchant_id in result:
            raise InputResolutionError(
                f"duplicate hurdle_bernoulli for merchant_id={merchant_id}"
            )
        result[merchant_id] = bool(payload.get("is_multi"))
    if errors:
        raise SchemaValidationError(
            "hurdle_bernoulli schema validation failed",
            errors,
        )
    return result


def _load_nb_final_events(
    paths: Iterable[Path],
    schema_layer1: dict,
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
) -> dict[int, int]:
    schema = _schema_from_pack(schema_layer1, "#/rng/events/nb_final")
    validator = Draft202012Validator(schema)
    result: dict[int, int] = {}
    errors: list[dict] = []
    for path, line_no, payload in _iter_jsonl_files(paths):
        for error in validator.iter_errors(payload):
            field = ".".join(str(part) for part in error.path) if error.path else ""
            errors.append(
                {
                    "row_index": line_no,
                    "field": field,
                    "message": f"{path}:{line_no} {error.message}",
                }
            )
            break
        if errors:
            break
        if payload.get("seed") != seed:
            raise InputResolutionError(
                f"nb_final seed mismatch in {path}:{line_no}"
            )
        if payload.get("parameter_hash") != parameter_hash:
            raise InputResolutionError(
                f"nb_final parameter_hash mismatch in {path}:{line_no}"
            )
        if payload.get("manifest_fingerprint") != manifest_fingerprint:
            raise InputResolutionError(
                f"nb_final manifest_fingerprint mismatch in {path}:{line_no}"
            )
        if payload.get("run_id") != run_id:
            raise InputResolutionError(
                f"nb_final run_id mismatch in {path}:{line_no}"
            )
        merchant_id = int(payload.get("merchant_id"))
        if merchant_id in result:
            raise InputResolutionError(
                f"duplicate nb_final for merchant_id={merchant_id}"
            )
        n_outlets = int(payload.get("n_outlets"))
        if n_outlets < 2:
            raise EngineFailure(
                "F3",
                "s3_precondition",
                "S3",
                MODULE_S3,
                {"detail": f"nb_final n_outlets < 2 for merchant {merchant_id}"},
                merchant_id=str(merchant_id),
            )
        result[merchant_id] = n_outlets
    if errors:
        raise SchemaValidationError("nb_final schema validation failed", errors)
    return result


def _rule_sort_key(rule: Rule, precedence_rank: dict[str, int]) -> tuple[int, int, str]:
    return (precedence_rank[rule.precedence], rule.priority, rule.rule_id)


def _select_decision_source(rule_trace: list[Rule]) -> Rule:
    for rule in rule_trace:
        if rule.is_decision_bearing:
            return rule
    raise EngineFailure(
        "F3",
        "s3_rule_ladder_invalid",
        "S3",
        MODULE_S3,
        {"detail": "no decision-bearing rule fired"},
    )


def _decide_eligibility(
    rule_trace: list[Rule],
) -> tuple[bool, Rule]:
    for rule in rule_trace:
        if rule.is_decision_bearing and rule.precedence == "DENY":
            return False, rule
    for rule in rule_trace:
        if rule.is_decision_bearing and rule.precedence == "ALLOW":
            return True, rule
    decision_source = _select_decision_source(rule_trace)
    return decision_source.precedence == "ALLOW", decision_source


def _round_to_dp(value: float, dp: int) -> float:
    scale = 10.0**dp
    return round(value * scale) / scale


def _fixed_dp_string(value: float, dp: int) -> str:
    return f"{value:.{dp}f}"


def _base_weight_policy_weights(
    rows: list[dict],
    policy: BaseWeightPolicy,
) -> tuple[list[dict], list[float]]:
    weights = []
    prior_rows = []
    for row in rows:
        is_home = bool(row["is_home"])
        candidate_rank = int(row["candidate_rank"])
        log_w = (
            policy.beta0
            + policy.beta_home * (1.0 if is_home else 0.0)
            + policy.beta_rank * candidate_rank
        )
        log_w = min(max(log_w, policy.log_w_min), policy.log_w_max)
        w = math.exp(log_w)
        w = min(max(w, policy.w_min), policy.w_max)
        w_q = _round_to_dp(w, policy.dp)
        weights.append(w_q)
        prior_rows.append(
            {
                "merchant_id": row["merchant_id"],
                "country_iso": row["country_iso"],
                "base_weight_dp": _fixed_dp_string(w_q, policy.dp),
                "dp": policy.dp,
                "parameter_hash": row["parameter_hash"],
                "produced_by_fingerprint": row["produced_by_fingerprint"],
            }
        )
    if sum(weights) <= 0.0:
        raise EngineFailure(
            "F3",
            "s3_weight_zero",
            "S3",
            MODULE_S3,
            {"detail": "sum of quantised weights is zero"},
        )
    return prior_rows, weights


def _compute_bounds(
    rows: list[dict],
    total_n: int,
    thresholds: ThresholdsPolicy,
) -> tuple[list[int], list[int]]:
    if total_n < 1:
        raise EngineFailure(
            "F3",
            "s3_integer_negative",
            "S3",
            MODULE_S3,
            {"detail": "total_n < 1"},
        )
    home_min = min(thresholds.home_min, total_n)
    has_foreign = len(rows) > 1
    if (
        thresholds.force_at_least_one_foreign_if_foreign_present
        and has_foreign
        and total_n >= 2
    ):
        home_max = total_n - 1
    else:
        home_max = total_n

    lower = []
    upper = []
    for row in rows:
        if row["is_home"]:
            lower.append(home_min)
            upper.append(home_max)
            continue
        if thresholds.min_one_per_country_when_feasible and total_n >= len(rows) and total_n >= 2:
            l_foreign = 1
        else:
            l_foreign = 0
        if thresholds.foreign_cap_mode == "n_minus_home_min":
            u_foreign = max(l_foreign, total_n - home_min)
        elif thresholds.foreign_cap_mode == "none":
            u_foreign = total_n
        else:
            raise EngineFailure(
                "F3",
                "s3_integer_feasibility",
                "S3",
                MODULE_S3,
                {"detail": f"unknown foreign_cap_mode {thresholds.foreign_cap_mode}"},
            )
        lower.append(l_foreign)
        upper.append(u_foreign)
    if sum(lower) > total_n or sum(upper) < total_n:
        raise EngineFailure(
            "F3",
            "s3_integer_feasibility",
            "S3",
            MODULE_S3,
            {"detail": "bounds infeasible for total_n"},
        )
    return lower, upper


def _integerise_counts(
    rows: list[dict],
    total_n: int,
    weights: Optional[list[float]],
    thresholds: Optional[ThresholdsPolicy],
) -> list[dict]:
    count_rows = []
    row_count = len(rows)
    if row_count == 0:
        return count_rows

    if thresholds and thresholds.enabled:
        lower, upper = _compute_bounds(rows, total_n, thresholds)
    else:
        lower = [0] * row_count
        upper = [total_n] * row_count

    base = list(lower)
    remaining = total_n - sum(base)
    capacities = [upper[idx] - lower[idx] for idx in range(row_count)]

    eligible_idx = [idx for idx, cap in enumerate(capacities) if cap > 0]
    if remaining < 0:
        raise EngineFailure(
            "F3",
            "s3_integer_feasibility",
            "S3",
            MODULE_S3,
            {"detail": "remaining negative after lower bounds"},
        )

    if remaining == 0:
        residual_order = list(range(row_count))
        residual_order.sort(
            key=lambda idx: (rows[idx]["country_iso"], rows[idx]["candidate_rank"])
        )
        for rank, idx in enumerate(residual_order, start=1):
            count_rows.append(
                {
                    "merchant_id": rows[idx]["merchant_id"],
                    "country_iso": rows[idx]["country_iso"],
                    "count": base[idx],
                    "residual_rank": rank,
                    "parameter_hash": rows[idx]["parameter_hash"],
                    "produced_by_fingerprint": rows[idx]["produced_by_fingerprint"],
                }
            )
        return count_rows

    if eligible_idx:
        if weights is None:
            weights_vec = [1.0 for _ in eligible_idx]
        else:
            weights_vec = [weights[idx] for idx in eligible_idx]
        weight_sum = sum(weights_vec)
        if weight_sum <= 0.0:
            raise EngineFailure(
                "F3",
                "s3_weight_zero",
                "S3",
                MODULE_S3,
                {"detail": "sum of weights is zero"},
            )
        shares = [value / weight_sum for value in weights_vec]
        ideal = [remaining * share for share in shares]
        floors = []
        for idx, value in zip(eligible_idx, ideal):
            floor_val = math.floor(value)
            cap = capacities[idx]
            floors.append(min(floor_val, cap))
        for floor_val, idx in zip(floors, eligible_idx):
            base[idx] += floor_val
        remaining = remaining - sum(floors)

        residuals = [0.0 for _ in range(row_count)]
        for idx, value, floor_val in zip(eligible_idx, ideal, floors):
            residuals[idx] = value - floor_val
    else:
        residuals = [0.0 for _ in range(row_count)]

    remaining_capacity = [capacities[idx] - (base[idx] - lower[idx]) for idx in range(row_count)]
    residual_keys = []
    for idx, resid in enumerate(residuals):
        if remaining_capacity[idx] > 0:
            residual_keys.append(_round_to_dp(resid, DP_RESID))
        else:
            residual_keys.append(-1.0)

    residual_order = list(range(row_count))
    residual_order.sort(
        key=lambda idx: (
            -residual_keys[idx],
            rows[idx]["country_iso"],
            rows[idx]["candidate_rank"],
        )
    )

    eligible_order = [idx for idx in residual_order if remaining_capacity[idx] > 0]
    if remaining > len(eligible_order):
        raise EngineFailure(
            "F3",
            "s3_integer_sum_mismatch",
            "S3",
            MODULE_S3,
            {"detail": "remaining bumps exceed eligible rows"},
        )
    bumped = set(eligible_order[:remaining])
    for idx in bumped:
        base[idx] += 1

    if sum(base) != total_n:
        raise EngineFailure(
            "F3",
            "s3_integer_sum_mismatch",
            "S3",
            MODULE_S3,
            {"detail": "counts do not sum to total_n"},
        )
    for idx, count in enumerate(base):
        if count < 0:
            raise EngineFailure(
                "F3",
                "s3_integer_negative",
                "S3",
                MODULE_S3,
                {"detail": f"negative count for {rows[idx]['country_iso']}"},
            )
        if count < lower[idx] or count > upper[idx]:
            raise EngineFailure(
                "F3",
                "s3_integer_feasibility",
                "S3",
                MODULE_S3,
                {"detail": f"count out of bounds for {rows[idx]['country_iso']}"},
            )

    for rank, idx in enumerate(residual_order, start=1):
        count_rows.append(
            {
                "merchant_id": rows[idx]["merchant_id"],
                "country_iso": rows[idx]["country_iso"],
                "count": base[idx],
                "residual_rank": rank,
                "parameter_hash": rows[idx]["parameter_hash"],
                "produced_by_fingerprint": rows[idx]["produced_by_fingerprint"],
            }
        )
    return count_rows


def _build_site_sequence(count_rows: list[dict]) -> list[dict]:
    site_rows = []
    for row in count_rows:
        count = int(row["count"])
        for order in range(1, count + 1):
            site_rows.append(
                {
                    "merchant_id": row["merchant_id"],
                    "country_iso": row["country_iso"],
                    "site_order": order,
                    "site_id": None,
                    "parameter_hash": row["parameter_hash"],
                    "produced_by_fingerprint": row["produced_by_fingerprint"],
                }
            )
    return site_rows

def run_s3(config: EngineConfig, run_id: Optional[str] = None) -> S3RunResult:
    logger = get_logger("engine.layers.l1.seg_1A.s3_crossborder.l2.runner")
    timer = _StepTimer(logger)

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dictionary_path, dictionary = load_dataset_dictionary(source, "1A")
    registry_path, registry = load_artefact_registry(source, "1A")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
    schema_ingress_path, schema_ingress = load_schema_pack(source, "1A", "ingress.layer1")
    schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
    logger.info(
        "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s",
        config.contracts_layout,
        config.contracts_root,
        dictionary_path,
        registry_path,
        schema_layer1_path,
        schema_ingress_path,
        schema_1a_path,
    )

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = receipt.get("run_id")
    seed = int(receipt.get("seed"))
    parameter_hash = receipt.get("parameter_hash")
    manifest_fingerprint = receipt.get("manifest_fingerprint")
    run_paths = RunPaths(config.runs_root, run_id)
    add_file_handler(run_paths.run_root / f"run_log_{run_id}.log")
    timer.info(f"S3: loaded run receipt {receipt_path}")

    utc_day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    segment_state_runs_path = _segment_state_runs_path(run_paths, dictionary, utc_day)

    def _emit_state_run(status: str, detail: Optional[str] = None) -> None:
        payload = {
            "layer": "layer1",
            "segment": "1A",
            "state": "S3",
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "run_id": run_id,
            "status": status,
            "ts_utc": utc_now_rfc3339_micro(),
        }
        if detail:
            payload["detail"] = detail
        _append_jsonl(segment_state_runs_path, payload)

    def _record_failure(failure: EngineFailure) -> None:
        payload = {
            "failure_class": failure.failure_class,
            "failure_code": failure.failure_code,
            "state": "S3",
            "module": failure.module,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "seed": seed,
            "run_id": run_id,
            "ts_utc": utc_now_ns(),
            "detail": failure.detail,
        }
        if failure.dataset_id:
            payload["dataset_id"] = failure.dataset_id
        if failure.merchant_id is not None:
            payload["merchant_id"] = str(failure.merchant_id)
        if isinstance(failure.detail, dict) and failure.detail.get("path"):
            payload["path"] = failure.detail.get("path")
        failure_root = (
            run_paths.run_root
            / "data/layer1/1A/validation/failures"
            / f"manifest_fingerprint={manifest_fingerprint}"
            / f"seed={seed}"
            / f"run_id={run_id}"
        )
        write_failure_record(failure_root, payload)
        _emit_state_run("failed", detail=failure.failure_code)

    tokens = {
        "seed": str(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "run_id": run_id,
    }

    _emit_state_run("started")

    try:
        gate_entry = find_dataset_entry(dictionary, "s0_gate_receipt_1A").entry
        gate_path = _resolve_run_path(
            run_paths, gate_entry["path"], {"manifest_fingerprint": manifest_fingerprint}
        )
        gate_receipt = _load_json(gate_path)
        if gate_receipt.get("manifest_fingerprint") != manifest_fingerprint:
            raise InputResolutionError("s0_gate_receipt manifest_fingerprint mismatch.")
        if gate_receipt.get("parameter_hash") != parameter_hash:
            raise InputResolutionError("s0_gate_receipt parameter_hash mismatch.")
        if gate_receipt.get("run_id") != run_id:
            raise InputResolutionError("s0_gate_receipt run_id mismatch.")

        sealed_entry = find_dataset_entry(dictionary, "sealed_inputs_1A").entry
        sealed_path = _resolve_run_path(
            run_paths,
            sealed_entry["path"],
            {"manifest_fingerprint": manifest_fingerprint},
        )
        sealed_inputs = _load_sealed_inputs(sealed_path)
        sealed_ids = {entry.get("asset_id") for entry in sealed_inputs}
        required_sealed = {
            "transaction_schema_merchant_ids",
            "iso3166_canonical_2024",
            "policy.s3.rule_ladder.yaml",
            "policy.s3.base_weight.yaml",
            "policy.s3.thresholds.yaml",
        }
        missing = sorted(required_sealed - sealed_ids)
        if missing:
            raise InputResolutionError(
                f"sealed_inputs_1A missing required assets: {missing}"
            )

        iso_path = _sealed_path(sealed_inputs, "iso3166_canonical_2024")
        iso_set = _load_iso_set(iso_path)

        ladder_path = _sealed_path(sealed_inputs, "policy.s3.rule_ladder.yaml")
        ladder = _load_rule_ladder(ladder_path, schema_layer1, iso_set)
        base_weight_path = _sealed_path(sealed_inputs, "policy.s3.base_weight.yaml")
        base_weight_policy = _load_base_weight_policy(base_weight_path, schema_layer1)
        thresholds_path = _sealed_path(sealed_inputs, "policy.s3.thresholds.yaml")
        thresholds_policy = _load_thresholds_policy(thresholds_path, schema_layer1)

        merchant_path = _sealed_path(sealed_inputs, "transaction_schema_merchant_ids")
        merchant_df = _validate_merchants(merchant_path, schema_ingress, iso_set)
        merchant_df = merchant_df.sort("merchant_id")
        merchant_map = {int(row["merchant_id"]): row for row in merchant_df.iter_rows(named=True)}
        timer.info(f"S3: loaded merchants rows={merchant_df.height}")

        hurdle_entry = find_dataset_entry(dictionary, DATASET_HURDLE).entry
        hurdle_paths = _resolve_run_glob(run_paths, hurdle_entry["path"], tokens)
        if not hurdle_paths:
            raise InputResolutionError("Missing hurdle_bernoulli event stream.")
        nb_final_entry = find_dataset_entry(dictionary, DATASET_NB_FINAL).entry
        nb_final_paths = _resolve_run_glob(run_paths, nb_final_entry["path"], tokens)
        if not nb_final_paths:
            raise InputResolutionError("Missing nb_final event stream.")

        hurdle_map = _load_hurdle_events(
            hurdle_paths, schema_layer1, seed, parameter_hash, manifest_fingerprint, run_id
        )
        nb_final_map = _load_nb_final_events(
            nb_final_paths, schema_layer1, seed, parameter_hash, manifest_fingerprint, run_id
        )
        missing_hurdle = [mid for mid in merchant_map if mid not in hurdle_map]
        if missing_hurdle:
            sample = missing_hurdle[:5]
            raise InputResolutionError(
                f"hurdle_bernoulli missing for {len(missing_hurdle)} merchants "
                f"(sample={sample})"
            )
        extra_hurdle = [mid for mid in hurdle_map if mid not in merchant_map]
        if extra_hurdle:
            sample = extra_hurdle[:5]
            raise InputResolutionError(
                f"hurdle_bernoulli contains {len(extra_hurdle)} unknown merchants "
                f"(sample={sample})"
            )

        for merchant_id in nb_final_map:
            if merchant_id not in merchant_map:
                raise EngineFailure(
                    "F3",
                    "s3_precondition",
                    "S3",
                    MODULE_S3,
                    {"detail": "nb_final merchant missing from ingress"},
                    merchant_id=str(merchant_id),
                )
            if not hurdle_map.get(merchant_id):
                raise EngineFailure(
                    "F3",
                    "s3_precondition",
                    "S3",
                    MODULE_S3,
                    {"detail": "nb_final exists for non-multi merchant"},
                    merchant_id=str(merchant_id),
                )

        for merchant_id, is_multi in hurdle_map.items():
            if is_multi and merchant_id not in nb_final_map:
                raise EngineFailure(
                    "F3",
                    "s3_precondition",
                    "S3",
                    MODULE_S3,
                    {"detail": "multi merchant missing nb_final"},
                    merchant_id=str(merchant_id),
                )

        candidate_entry = find_dataset_entry(dictionary, DATASET_CANDIDATE).entry
        priors_entry = find_dataset_entry(dictionary, DATASET_PRIORS).entry
        counts_entry = find_dataset_entry(dictionary, DATASET_COUNTS).entry
        site_entry = find_dataset_entry(dictionary, DATASET_SITE_SEQUENCE).entry

        candidate_root = _resolve_run_path(run_paths, candidate_entry["path"], tokens)
        priors_root = _resolve_run_path(run_paths, priors_entry["path"], tokens)
        counts_root = _resolve_run_path(run_paths, counts_entry["path"], tokens)
        site_root = _resolve_run_path(run_paths, site_entry["path"], tokens)

        outputs_exist = {
            DATASET_CANDIDATE: _dataset_has_parquet(candidate_root),
            DATASET_PRIORS: _dataset_has_parquet(priors_root),
            DATASET_COUNTS: _dataset_has_parquet(counts_root),
            DATASET_SITE_SEQUENCE: _dataset_has_parquet(site_root),
        }
        if any(outputs_exist.values()) and not all(outputs_exist.values()):
            raise InputResolutionError(
                "Partial S3 outputs detected; remove existing outputs before rerun."
            )

        merchant_ids = sorted(
            [mid for mid, is_multi in hurdle_map.items() if is_multi]
        )
        total = len(merchant_ids)
        progress_every = max(1, min(10_000, total // 10 if total else 1))
        start_time = time.monotonic()

        candidate_rows = []
        prior_rows = []
        count_rows = []
        site_rows = []

        logger.info("S3: processing merchants=%d", total)
        for idx, merchant_id in enumerate(merchant_ids, start=1):
            if idx % progress_every == 0 or idx == total:
                elapsed = max(time.monotonic() - start_time, 1e-9)
                rate = idx / elapsed
                eta = (total - idx) / rate if rate > 0 else 0.0
                logger.info(
                    "S3 progress %d/%d (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
                    idx,
                    total,
                    elapsed,
                    rate,
                    eta,
                )

            merchant = merchant_map[merchant_id]
            home_country_iso = str(merchant["home_country_iso"])
            channel = str(merchant["channel"])
            mcc = int(merchant["mcc"])
            n_outlets = nb_final_map[merchant_id]

            context = {
                "home_country_iso": home_country_iso,
                "channel": channel,
                "mcc": mcc,
                "n_outlets": n_outlets,
            }
            fired = []
            for rule in ladder.rules:
                if _eval_predicate(rule.predicate, context):
                    fired.append(rule)
            if not fired:
                raise EngineFailure(
                    "F3",
                    "s3_rule_ladder_invalid",
                    "S3",
                    MODULE_S3,
                    {"detail": "no rules fired"},
                    merchant_id=str(merchant_id),
                )
            rule_trace = sorted(fired, key=lambda r: _rule_sort_key(r, ladder.precedence_rank))
            eligible_crossborder, decision_source = _decide_eligibility(rule_trace)

            merchant_tags = sorted(
                set(tag for rule in fired for tag in rule.outcome_tags)
            )
            fired_reason_codes = sorted(set(rule.outcome_reason_code for rule in fired))

            home_filter_tags = sorted(set(merchant_tags) | {"HOME"})
            home_row = {
                "merchant_id": merchant_id,
                "country_iso": home_country_iso,
                "is_home": True,
                "candidate_rank": 0,
                "reason_codes": fired_reason_codes,
                "filter_tags": home_filter_tags,
                "parameter_hash": parameter_hash,
                "produced_by_fingerprint": manifest_fingerprint,
            }

            foreign_rows = []
            if eligible_crossborder:
                admit_countries = set()
                deny_countries = set()
                for rule in fired:
                    admit_countries.update(rule.admit_countries)
                    deny_countries.update(rule.deny_countries)
                foreigns = (admit_countries - deny_countries) - {home_country_iso}

                for country_iso in foreigns:
                    admit_rules = [rule for rule in fired if country_iso in rule.admit_countries]
                    reason_codes = sorted(
                        set(rule.outcome_reason_code for rule in admit_rules)
                    )
                    if not reason_codes:
                        raise EngineFailure(
                            "F3",
                            "s3_ordering_key_undefined",
                            "S3",
                            MODULE_S3,
                            {"detail": f"no admit rules for {country_iso}"},
                            merchant_id=str(merchant_id),
                        )
                    row_tags = sorted(
                        set(merchant_tags)
                        | set(tag for rule in admit_rules for tag in rule.row_tags)
                    )

                    admit_rule_ids = []
                    for code in reason_codes:
                        rule_id = ladder.reason_code_to_rule_id.get(code)
                        if rule_id is None:
                            raise EngineFailure(
                                "F3",
                                "s3_ordering_key_undefined",
                                "S3",
                                MODULE_S3,
                                {"detail": f"reason_code {code} missing mapping"},
                                merchant_id=str(merchant_id),
                            )
                        admit_rule = ladder.rules_by_id.get(rule_id)
                        if admit_rule is None or not admit_rule.admit_countries:
                            raise EngineFailure(
                                "F3",
                                "s3_ordering_key_undefined",
                                "S3",
                                MODULE_S3,
                                {"detail": f"reason_code {code} mapped to non-admit rule"},
                                merchant_id=str(merchant_id),
                            )
                        admit_rule_ids.append(rule_id)

                    keys = [
                        _rule_sort_key(ladder.rules_by_id[rule_id], ladder.precedence_rank)
                        for rule_id in admit_rule_ids
                    ]
                    order_key = min(keys)

                    foreign_rows.append(
                        {
                            "merchant_id": merchant_id,
                            "country_iso": country_iso,
                            "is_home": False,
                            "candidate_rank": 0,
                            "reason_codes": reason_codes,
                            "filter_tags": row_tags,
                            "parameter_hash": parameter_hash,
                            "produced_by_fingerprint": manifest_fingerprint,
                            "_order_key": order_key,
                        }
                    )

            foreign_rows.sort(key=lambda row: (row["_order_key"], row["country_iso"]))
            for rank, row in enumerate(foreign_rows, start=1):
                row["candidate_rank"] = rank
                row.pop("_order_key", None)

            merchant_candidate_rows = [home_row] + foreign_rows
            candidate_rows.extend(merchant_candidate_rows)

            prior_rows_local, weights = _base_weight_policy_weights(
                merchant_candidate_rows, base_weight_policy
            )
            prior_rows.extend(prior_rows_local)

            counts_local = _integerise_counts(
                merchant_candidate_rows,
                n_outlets,
                weights,
                thresholds_policy,
            )
            count_rows.extend(counts_local)
            site_rows.extend(_build_site_sequence(counts_local))

        candidate_df = pl.DataFrame(
            candidate_rows,
            schema={
                "merchant_id": pl.UInt64,
                "country_iso": pl.Utf8,
                "candidate_rank": pl.Int32,
                "is_home": pl.Boolean,
                "reason_codes": pl.List(pl.Utf8),
                "filter_tags": pl.List(pl.Utf8),
                "parameter_hash": pl.Utf8,
                "produced_by_fingerprint": pl.Utf8,
            },
        ).sort(["merchant_id", "candidate_rank", "country_iso"])

        prior_df = pl.DataFrame(
            prior_rows,
            schema={
                "merchant_id": pl.UInt64,
                "country_iso": pl.Utf8,
                "base_weight_dp": pl.Utf8,
                "dp": pl.Int32,
                "parameter_hash": pl.Utf8,
                "produced_by_fingerprint": pl.Utf8,
            },
        ).sort(["merchant_id", "country_iso"])

        counts_df = pl.DataFrame(
            count_rows,
            schema={
                "merchant_id": pl.UInt64,
                "country_iso": pl.Utf8,
                "count": pl.Int32,
                "residual_rank": pl.Int32,
                "parameter_hash": pl.Utf8,
                "produced_by_fingerprint": pl.Utf8,
            },
        ).sort(["merchant_id", "country_iso"])

        site_df = pl.DataFrame(
            site_rows,
            schema={
                "merchant_id": pl.UInt64,
                "country_iso": pl.Utf8,
                "site_order": pl.Int32,
                "site_id": pl.Utf8,
                "parameter_hash": pl.Utf8,
                "produced_by_fingerprint": pl.Utf8,
            },
        ).sort(["merchant_id", "country_iso", "site_order"])

        tmp_root = run_paths.tmp_root / "s3_crossborder"
        tmp_root.mkdir(parents=True, exist_ok=True)

        if all(outputs_exist.values()):
            existing_candidate = pl.read_parquet(
                _select_dataset_file(DATASET_CANDIDATE, candidate_root)
            ).select(candidate_df.columns).sort(
                ["merchant_id", "candidate_rank", "country_iso"]
            )
            existing_prior = pl.read_parquet(
                _select_dataset_file(DATASET_PRIORS, priors_root)
            ).select(prior_df.columns).sort(["merchant_id", "country_iso"])
            existing_counts = pl.read_parquet(
                _select_dataset_file(DATASET_COUNTS, counts_root)
            ).select(counts_df.columns).sort(["merchant_id", "country_iso"])
            existing_site = pl.read_parquet(
                _select_dataset_file(DATASET_SITE_SEQUENCE, site_root)
            ).select(site_df.columns).sort(["merchant_id", "country_iso", "site_order"])

            if not existing_candidate.equals(candidate_df):
                raise EngineFailure(
                    "F3",
                    "s3_output_mismatch",
                    "S3",
                    MODULE_S3,
                    {"detail": "candidate_set mismatch"},
                )
            if not existing_prior.equals(prior_df):
                raise EngineFailure(
                    "F3",
                    "s3_output_mismatch",
                    "S3",
                    MODULE_S3,
                    {"detail": "base_weight_priors mismatch"},
                )
            if not existing_counts.equals(counts_df):
                raise EngineFailure(
                    "F3",
                    "s3_output_mismatch",
                    "S3",
                    MODULE_S3,
                    {"detail": "integerised_counts mismatch"},
                )
            if not existing_site.equals(site_df):
                raise EngineFailure(
                    "F3",
                    "s3_output_mismatch",
                    "S3",
                    MODULE_S3,
                    {"detail": "site_sequence mismatch"},
                )
            timer.info("S3: existing outputs validated")
            _emit_state_run("completed")
            return S3RunResult(
                run_id=run_id,
                parameter_hash=parameter_hash,
                manifest_fingerprint=manifest_fingerprint,
                candidate_set_path=candidate_root,
                base_weight_priors_path=priors_root,
                integerised_counts_path=counts_root,
                site_sequence_path=site_root,
            )

        _write_parquet_partition(candidate_df, candidate_root, tmp_root, DATASET_CANDIDATE)
        _write_parquet_partition(prior_df, priors_root, tmp_root, DATASET_PRIORS)
        _write_parquet_partition(counts_df, counts_root, tmp_root, DATASET_COUNTS)
        _write_parquet_partition(site_df, site_root, tmp_root, DATASET_SITE_SEQUENCE)
        timer.info("S3: outputs emitted")

        _emit_state_run("completed")
        return S3RunResult(
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            candidate_set_path=candidate_root,
            base_weight_priors_path=priors_root,
            integerised_counts_path=counts_root,
            site_sequence_path=site_root,
        )
    except EngineFailure as failure:
        _record_failure(failure)
        raise
    except (ContractError, InputResolutionError, SchemaValidationError) as exc:
        failure = EngineFailure(
            "F5" if isinstance(exc, InputResolutionError) else "F4",
            "s3_contract_failure",
            "S3",
            MODULE_S3,
            {"detail": str(exc)},
        )
        _record_failure(failure)
        raise
