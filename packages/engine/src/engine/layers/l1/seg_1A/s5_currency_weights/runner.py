"""S5 currency-to-country weights runner for Segment 1A."""

from __future__ import annotations

import datetime as dt
import hashlib
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
    find_artifact_entry,
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
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_1A.s0_foundations.validation_bundle import (
    write_failure_record,
    write_json,
)


MODULE_NAME = "1A.expand_currency_to_country"
PRODUCER = "1A.expand_currency_to_country"

DATASET_SETTLEMENT = "settlement_shares_2024Q4"
DATASET_CCY = "ccy_country_shares_2024Q4"
DATASET_ISO = "iso3166_canonical_2024"
DATASET_LEGAL_TENDER = "iso_legal_tender_2024"
DATASET_MERCHANTS = "transaction_schema_merchant_ids"
DATASET_WEIGHTS = "ccy_country_weights_cache"
DATASET_MERCHANT_CURRENCY = "merchant_currency"
DATASET_SPARSE = "sparse_flag"
DATASET_TRACE = "rng_trace_log"
DATASET_RECEIPT = "s5_validation_receipt"
DATASET_PASSED = "s5_passed_flag"
DATASET_LICENSE_MAP = "license_map"
POLICY_ASSET_ID = "ccy_smoothing_params.yaml"
POLICY_REGISTRY_NAME = "ccy_smoothing_params"


@dataclass(frozen=True)
class S5RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    weights_root: Path


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


def _resolve_run_receipt(
    runs_root: Path, run_id: Optional[str]
) -> tuple[Path, dict]:
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


def _schema_section(schema_pack: dict, section: str) -> dict:
    node = schema_pack.get(section)
    if not isinstance(node, dict):
        raise ContractError(f"Schema section not found: {section}")
    subset = {"$id": schema_pack.get("$id", ""), "$defs": schema_pack.get("$defs", {})}
    subset.update(node)
    return subset


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


def _dataset_has_parquet(root: Path) -> bool:
    if not root.exists():
        return False
    if root.is_file() and root.suffix == ".parquet":
        return True
    if root.is_dir():
        return any(root.glob("*.parquet"))
    return False


def _write_parquet_partition(
    df: pl.DataFrame, target_root: Path, dataset_id: str
) -> None:
    tmp_dir = target_root.parent / f"_tmp.{dataset_id}.{uuid.uuid4().hex}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_dir / "part-00000.parquet"
    df.write_parquet(tmp_file)
    target_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir.replace(target_root)


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


def _round_half_even(value: float) -> int:
    return int(round(value))


def _quantile_int(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = int(math.ceil(q * len(ordered)) - 1)
    index = min(max(index, 0), len(ordered) - 1)
    return int(ordered[index])


def _trace_snapshot(path: Path) -> dict[tuple[str, str], dict]:
    snapshot: dict[tuple[str, str], dict] = {}
    if not path.exists():
        return snapshot
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            key = (str(payload.get("module")), str(payload.get("substream_label")))
            snapshot[key] = payload
    return snapshot


def _trace_totals(snapshot: dict[tuple[str, str], dict]) -> tuple[int, int, int]:
    events_total = sum(int(row.get("events_total", 0)) for row in snapshot.values())
    draws_total = sum(int(row.get("draws_total", 0)) for row in snapshot.values())
    blocks_total = sum(int(row.get("blocks_total", 0)) for row in snapshot.values())
    return events_total, draws_total, blocks_total

def _validate_policy(
    policy_path: Path, schema_layer1: dict, iso_set: set[str]
) -> dict:
    payload = _load_yaml(policy_path)
    schema = _schema_from_pack(schema_layer1, "policy/ccy_smoothing_params")
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    if errors:
        details = [
            {"path": ".".join(str(part) for part in err.path), "message": err.message}
            for err in errors
        ]
        raise SchemaValidationError(
            "ccy_smoothing_params schema validation failed", details
        )
    overrides = payload.get("overrides") or {}
    for override_key in ("alpha_iso", "min_share_iso"):
        override_map = overrides.get(override_key) or {}
        for currency, iso_map in override_map.items():
            for iso in iso_map.keys():
                if iso not in iso_set:
                    raise EngineFailure(
                        "F4",
                        "E_POLICY_UNKNOWN_CODE",
                        "S5",
                        MODULE_NAME,
                        {"currency": currency, "iso": iso},
                    )
    min_share_iso = (overrides.get("min_share_iso") or {}).items()
    for currency, iso_map in min_share_iso:
        total = float(sum(float(value) for value in iso_map.values()))
        if total > 1.0 + 1e-12:
            raise EngineFailure(
                "F4",
                "E_POLICY_MINSHARE_FEASIBILITY",
                "S5",
                MODULE_NAME,
                {"currency": currency, "sum": total},
            )
    return payload


def _load_shares(
    path: Path, schema_ingress: dict, table_name: str, dataset_id: str
) -> pl.DataFrame:
    df = pl.read_parquet(path)
    validate_dataframe(df.iter_rows(named=True), schema_ingress, table_name)
    required = {"currency", "country_iso", "share", "obs_count"}
    if not required.issubset(set(df.columns)):
        raise InputResolutionError(f"{dataset_id} missing required columns.")
    dupes = (
        df.group_by(["currency", "country_iso"])
        .len()
        .filter(pl.col("len") > 1)
    )
    if dupes.height > 0:
        raise EngineFailure(
            "F4",
            "E_INPUT_PK",
            "S5",
            MODULE_NAME,
            {"dataset_id": dataset_id},
            dataset_id=dataset_id,
        )
    bad_shares = df.filter(
        pl.col("share").is_nan()
        | pl.col("share").is_infinite()
        | (pl.col("share") < 0.0)
        | (pl.col("share") > 1.0)
    )
    if bad_shares.height > 0:
        raise EngineFailure(
            "F4",
            "E_INPUT_DOMAIN",
            "S5",
            MODULE_NAME,
            {"dataset_id": dataset_id, "detail": "share_out_of_range"},
            dataset_id=dataset_id,
        )
    if df.filter(pl.col("obs_count") < 0).height > 0:
        raise EngineFailure(
            "F4",
            "E_INPUT_DOMAIN",
            "S5",
            MODULE_NAME,
            {"dataset_id": dataset_id, "detail": "obs_count_negative"},
            dataset_id=dataset_id,
        )
    sums = df.group_by("currency").agg(pl.col("share").sum().alias("sum_share"))
    bad = sums.filter((pl.col("sum_share") - 1.0).abs() > 1e-6)
    if bad.height > 0:
        raise EngineFailure(
            "F4",
            "E_INPUT_SUM",
            "S5",
            MODULE_NAME,
            {"dataset_id": dataset_id, "rows": bad.to_dicts()},
            dataset_id=dataset_id,
        )
    return df


def _surface_map(df: pl.DataFrame) -> dict[str, dict[str, tuple[float, int]]]:
    surface: dict[str, dict[str, tuple[float, int]]] = {}
    for row in df.iter_rows(named=True):
        currency = str(row["currency"])
        iso = str(row["country_iso"])
        share = float(row["share"])
        obs_count = int(row["obs_count"])
        surface.setdefault(currency, {})[iso] = (share, obs_count)
    return surface


def _validate_artefact_entry(
    registry: dict, name: str, expected_path: str, expected_schema: Optional[str]
) -> None:
    entry = find_artifact_entry(registry, name).entry
    if entry.get("path") != expected_path:
        raise ContractError(f"Registry path mismatch for {name}: {entry.get('path')}")
    if expected_schema and entry.get("schema") and entry.get("schema") != expected_schema:
        raise ContractError(
            f"Registry schema mismatch for {name}: {entry.get('schema')}"
        )


def _load_license_map(path: Path, schema_layer1: dict) -> dict:
    payload = _load_yaml(path)
    schema = _schema_from_pack(schema_layer1, "governance/license_map")
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    if errors:
        details = [
            {"path": ".".join(str(part) for part in err.path), "message": err.message}
            for err in errors
        ]
        raise SchemaValidationError("license_map schema validation failed", details)
    return payload


def _license_summary(
    dictionary: dict, license_map: dict, dataset_ids: Iterable[str]
) -> list[dict]:
    licenses = license_map.get("licenses") or {}
    summary = []
    for dataset_id in sorted(set(dataset_ids)):
        entry = find_dataset_entry(dictionary, dataset_id).entry
        licence = entry.get("licence")
        if not licence:
            raise EngineFailure(
                "F4",
                "E_LICENSE_MISSING",
                "S5",
                MODULE_NAME,
                {"dataset_id": dataset_id, "detail": "missing_licence"},
                dataset_id=dataset_id,
            )
        if licence not in licenses:
            raise EngineFailure(
                "F4",
                "E_LICENSE_MISSING",
                "S5",
                MODULE_NAME,
                {"dataset_id": dataset_id, "licence": licence},
                dataset_id=dataset_id,
            )
        summary.append(
            {
                "dataset_id": dataset_id,
                "licence": licence,
                "retention_days": entry.get("retention_days"),
            }
        )
    return summary


def _write_receipt(
    receipt_path: Path, passed_flag_path: Path, payload: dict
) -> None:
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_receipt = receipt_path.with_suffix(".json.tmp")
    tmp_flag = passed_flag_path.with_suffix(".flag.tmp")
    write_json(tmp_receipt, payload)
    receipt_hash = hashlib.sha256(tmp_receipt.read_bytes()).hexdigest()
    tmp_flag.write_text(f"sha256_hex = {receipt_hash}\n", encoding="ascii")
    tmp_receipt.replace(receipt_path)
    tmp_flag.replace(passed_flag_path)


def _assert_same_frame(
    expected: pl.DataFrame, actual: pl.DataFrame, sort_keys: list[str], dataset_id: str
) -> None:
    expected_sorted = expected.sort(sort_keys)
    actual_sorted = actual.sort(sort_keys)
    if expected_sorted.columns != actual_sorted.columns:
        raise EngineFailure(
            "F4",
            "E_OUTPUT_MISMATCH",
            "S5",
            MODULE_NAME,
            {"dataset_id": dataset_id, "detail": "columns_mismatch"},
            dataset_id=dataset_id,
        )
    if expected_sorted.height != actual_sorted.height:
        raise EngineFailure(
            "F4",
            "E_OUTPUT_MISMATCH",
            "S5",
            MODULE_NAME,
            {"dataset_id": dataset_id, "detail": "row_count_mismatch"},
            dataset_id=dataset_id,
        )
    for row_expected, row_actual in zip(
        expected_sorted.iter_rows(), actual_sorted.iter_rows()
    ):
        if row_expected != row_actual:
            raise EngineFailure(
                "F4",
                "E_OUTPUT_MISMATCH",
                "S5",
                MODULE_NAME,
                {"dataset_id": dataset_id, "detail": "value_mismatch"},
                dataset_id=dataset_id,
            )

def run_s5(
    config: EngineConfig,
    run_id: Optional[str] = None,
    emit_sparse_flag: bool = False,
    fail_on_degrade: bool = False,
    validate_only: bool = False,
) -> S5RunResult:
    logger = get_logger("engine.layers.l1.seg_1A.s5_currency_weights.l2.runner")
    timer = _StepTimer(logger)

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dictionary_path, dictionary = load_dataset_dictionary(source, "1A")
    registry_path, registry = load_artefact_registry(source, "1A")
    schema_ingress_path, schema_ingress = load_schema_pack(source, "1A", "ingress.layer1")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
    schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
    logger.info(
        "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s",
        config.contracts_layout,
        config.contracts_root,
        dictionary_path,
        registry_path,
        schema_ingress_path,
        schema_layer1_path,
        schema_1a_path,
    )

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = receipt.get("run_id")
    seed = int(receipt.get("seed"))
    parameter_hash = receipt.get("parameter_hash")
    manifest_fingerprint = receipt.get("manifest_fingerprint")
    run_paths = RunPaths(config.runs_root, run_id)
    add_file_handler(run_paths.run_root / f"run_log_{run_id}.log")
    timer.info(f"S5: loaded run receipt {receipt_path}")
    if validate_only:
        logger.info("S5: validate-only enabled; outputs will not be written")

    utc_day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    segment_state_runs_path = _segment_state_runs_path(run_paths, dictionary, utc_day)

    def _emit_state_run(status: str, detail: Optional[str] = None) -> None:
        payload = {
            "layer": "layer1",
            "segment": "1A",
            "state": "S5",
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
            "state": "S5",
            "module": failure.module,
            "ts_utc": utc_now_rfc3339_micro(),
            "detail": failure.detail,
        }
        if failure.dataset_id:
            payload["dataset_id"] = failure.dataset_id
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
        gate_path = _resolve_run_path(run_paths, gate_entry["path"], tokens)
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
            DATASET_SETTLEMENT,
            DATASET_CCY,
            DATASET_ISO,
            POLICY_ASSET_ID,
            DATASET_LICENSE_MAP,
        }
        missing = sorted(required_sealed - sealed_ids)
        if missing:
            raise InputResolutionError(
                f"sealed_inputs_1A missing required assets: {missing}"
            )

        weights_entry = find_dataset_entry(dictionary, DATASET_WEIGHTS).entry
        _validate_artefact_entry(
            registry,
            DATASET_WEIGHTS,
            weights_entry["path"],
            weights_entry.get("schema_ref"),
        )
        _validate_artefact_entry(
            registry,
            POLICY_REGISTRY_NAME,
            "config/layer1/1A/allocation/ccy_smoothing_params.yaml",
            "schemas.layer1.yaml#/policy/ccy_smoothing_params",
        )

        if DATASET_MERCHANT_CURRENCY in [item.get("id") for item in dictionary.get("datasets", [])]:
            merchant_entry = find_dataset_entry(dictionary, DATASET_MERCHANT_CURRENCY).entry
            _validate_artefact_entry(
                registry,
                DATASET_MERCHANT_CURRENCY,
                merchant_entry["path"],
                merchant_entry.get("schema_ref"),
            )
        if DATASET_SPARSE in [item.get("id") for item in dictionary.get("datasets", [])]:
            sparse_entry = find_dataset_entry(dictionary, DATASET_SPARSE).entry
            _validate_artefact_entry(
                registry,
                DATASET_SPARSE,
                sparse_entry["path"],
                sparse_entry.get("schema_ref"),
            )

        license_map_path = _sealed_path(sealed_inputs, DATASET_LICENSE_MAP)
        license_map = _load_license_map(license_map_path, schema_layer1)

        iso_path = _sealed_path(sealed_inputs, DATASET_ISO)
        iso_df = pl.read_parquet(iso_path)
        validate_dataframe(iso_df.iter_rows(named=True), schema_ingress, DATASET_ISO)
        iso_set = set(iso_df["country_iso"].to_list())

        policy_path = _sealed_path(sealed_inputs, POLICY_ASSET_ID)
        policy = _validate_policy(policy_path, schema_layer1, iso_set)
        policy_digest = sha256_file(policy_path).sha256_hex

        settlement_path = _sealed_path(sealed_inputs, DATASET_SETTLEMENT)
        ccy_path = _sealed_path(sealed_inputs, DATASET_CCY)

        settlement_df = _load_shares(
            settlement_path, schema_ingress, DATASET_SETTLEMENT, DATASET_SETTLEMENT
        )
        ccy_df = _load_shares(ccy_path, schema_ingress, DATASET_CCY, DATASET_CCY)
        timer.info("S5: ingress shares validated")

        settlement_map = _surface_map(settlement_df)
        ccy_map = _surface_map(ccy_df)
        currencies_union = sorted(settlement_map.keys() | ccy_map.keys())
        logger.info(
            "S5: preflight shares (settlement currencies=%d, ccy currencies=%d, union currencies=%d)",
            len(settlement_map),
            len(ccy_map),
            len(currencies_union),
        )

        policy_currencies = set(policy.get("per_currency", {}).keys())
        overrides = policy.get("overrides") or {}
        policy_currencies |= set((overrides.get("alpha_iso") or {}).keys())
        policy_currencies |= set((overrides.get("min_share_iso") or {}).keys())
        unknown_policy = sorted(policy_currencies - set(currencies_union))
        if unknown_policy:
            raise EngineFailure(
                "F4",
                "E_POLICY_UNKNOWN_CODE",
                "S5",
                MODULE_NAME,
                {"currencies": unknown_policy},
            )

        trace_entry = find_dataset_entry(dictionary, DATASET_TRACE).entry
        trace_path = _resolve_run_path(run_paths, trace_entry["path"], tokens)
        trace_before = _trace_snapshot(trace_path)

        defaults = policy["defaults"]
        per_currency = policy.get("per_currency") or {}
        overrides_alpha = (overrides.get("alpha_iso") or {})
        overrides_min_share = (overrides.get("min_share_iso") or {})
        dp = int(policy["dp"])
        scale = 10**dp
        logger.info(
            "S5: policy validated (dp=%d, per_currency=%d, alpha_overrides=%d, min_share_overrides=%d)",
            dp,
            len(per_currency),
            len(overrides_alpha),
            len(overrides_min_share),
        )

        weights_rows: list[dict] = []
        by_currency: list[dict] = []
        sparse_rows: list[dict] = []

        largest_remainder_ulps_list: list[int] = []
        overrides_applied_count = 0
        floors_triggered_count = 0
        sum_numeric_pass = 0
        sum_decimal_pass = 0
        degrade_counts = {"none": 0, "settlement_only": 0, "ccy_only": 0}
        degraded_currencies: list[dict] = []

        total_currencies = len(currencies_union)
        progress_every = max(1, min(10_000, total_currencies // 10 if total_currencies else 1))
        loop_start = time.monotonic()
        logger.info(
            "S5: building weights cache (currencies=%d, dp=%d, emit_sparse_flag=%s)",
            total_currencies,
            dp,
            emit_sparse_flag,
        )

        for idx, currency in enumerate(currencies_union, start=1):
            settlement_rows = settlement_map.get(currency, {})
            ccy_rows = ccy_map.get(currency, {})
            if not settlement_rows and not ccy_rows:
                continue

            degrade_mode = "none"
            degrade_reason = None
            if not settlement_rows:
                degrade_mode = "ccy_only"
                degrade_reason = "SRC_MISSING_SETTLEMENT"
                blend_weight = 1.0
            elif not ccy_rows:
                degrade_mode = "settlement_only"
                degrade_reason = "SRC_MISSING_CCY"
                blend_weight = 0.0
            else:
                blend_weight = float(
                    per_currency.get(currency, {}).get(
                        "blend_weight", defaults["blend_weight"]
                    )
                )
            if degrade_mode != "none":
                degrade_counts[degrade_mode] += 1
                degraded_currencies.append(
                    {"currency": currency, "mode": degrade_mode, "reason_code": degrade_reason}
                )
            else:
                degrade_counts["none"] += 1

            obs_floor = int(
                per_currency.get(currency, {}).get("obs_floor", defaults["obs_floor"])
            )
            shrink_exponent = float(
                per_currency.get(currency, {}).get(
                    "shrink_exponent", defaults["shrink_exponent"]
                )
            )
            shrink_exponent = max(shrink_exponent, 1.0)
            alpha_default = float(
                per_currency.get(currency, {}).get("alpha", defaults["alpha"])
            )
            min_share_default = float(
                per_currency.get(currency, {}).get("min_share", defaults["min_share"])
            )
            alpha_map = overrides_alpha.get(currency, {})
            min_share_map = overrides_min_share.get(currency, {})

            overrides_applied = {
                "alpha_iso": any(iso in alpha_map for iso in settlement_rows.keys() | ccy_rows.keys()),
                "min_share_iso": any(
                    iso in min_share_map for iso in settlement_rows.keys() | ccy_rows.keys()
                ),
                "per_currency": currency in per_currency,
            }
            if any(overrides_applied.values()):
                overrides_applied_count += 1

            iso_union = sorted(settlement_rows.keys() | ccy_rows.keys())
            sum_n_ccy = float(sum(value[1] for value in ccy_rows.values()))
            sum_n_settle = float(sum(value[1] for value in settlement_rows.values()))
            n0 = blend_weight * sum_n_ccy + (1.0 - blend_weight) * sum_n_settle
            n_eff = max(float(obs_floor), math.pow(n0, 1.0 / shrink_exponent) if n0 > 0.0 else 0.0)

            q_values: list[float] = []
            alpha_values: list[float] = []
            min_share_values: list[float] = []
            for iso in iso_union:
                s_ccy = ccy_rows.get(iso, (0.0, 0))[0]
                s_settle = settlement_rows.get(iso, (0.0, 0))[0]
                q_values.append(blend_weight * float(s_ccy) + (1.0 - blend_weight) * float(s_settle))
                alpha_values.append(float(alpha_map.get(iso, alpha_default)))
                min_share_values.append(float(min_share_map.get(iso, min_share_default)))

            alpha_total = float(sum(alpha_values))
            denom = n_eff + alpha_total
            if denom <= 0.0:
                raise EngineFailure(
                    "F4",
                    "E_ZERO_MASS",
                    "S5",
                    MODULE_NAME,
                    {"currency": currency},
                )

            posterior = [
                (q * n_eff + alpha) / denom for q, alpha in zip(q_values, alpha_values)
            ]

            floors_triggered = 0
            p_prime = []
            for value, floor in zip(posterior, min_share_values):
                if value < floor:
                    floors_triggered += 1
                    p_prime.append(floor)
                else:
                    p_prime.append(value)
            floors_triggered_count += floors_triggered
            total_prime = float(sum(p_prime))
            if total_prime <= 0.0:
                raise EngineFailure(
                    "F4",
                    "E_ZERO_MASS",
                    "S5",
                    MODULE_NAME,
                    {"currency": currency, "detail": "zero_after_floor"},
                )
            p_values = [value / total_prime for value in p_prime]

            scaled = [value * scale for value in p_values]
            ticks = [int(round(value)) for value in scaled]
            remainder = [s - t for s, t in zip(scaled, ticks)]
            delta = int(scale - sum(ticks))
            if delta != 0:
                if delta > 0:
                    order = sorted(
                        range(len(iso_union)),
                        key=lambda idx2: (-remainder[idx2], iso_union[idx2]),
                    )
                    for idx2 in order[:delta]:
                        ticks[idx2] += 1
                else:
                    order = list(range(len(iso_union)))
                    order.sort(key=lambda idx2: iso_union[idx2], reverse=True)
                    order.sort(key=lambda idx2: remainder[idx2])
                    for idx2 in order[: abs(delta)]:
                        ticks[idx2] -= 1
                if any(tick < 0 for tick in ticks):
                    raise EngineFailure(
                        "F4",
                        "E_QUANT_NEGATIVE",
                        "S5",
                        MODULE_NAME,
                        {"currency": currency},
                    )

            ticks_sum = sum(ticks)
            sum_decimal_ok = ticks_sum == scale
            sum_numeric_ok = abs(sum(tick / scale for tick in ticks) - 1.0) <= 1e-6
            if sum_numeric_ok:
                sum_numeric_pass += 1
            if sum_decimal_ok:
                sum_decimal_pass += 1

            obs_count_value = _round_half_even(n0)
            for iso, tick in zip(iso_union, ticks):
                weights_rows.append(
                    {
                        "currency": currency,
                        "country_iso": iso,
                        "weight": tick / scale,
                        "obs_count": obs_count_value,
                        "smoothing": None,
                    }
                )

            largest_remainder_ulps = abs(delta)
            largest_remainder_ulps_list.append(largest_remainder_ulps)

            by_currency.append(
                {
                    "currency": currency,
                    "parameter_hash": parameter_hash,
                    "policy_digest": policy_digest,
                    "producer": PRODUCER,
                    "schema_refs": {
                        "settlement_shares": "schemas.ingress.layer1.yaml#/settlement_shares",
                        "ccy_country_shares": "schemas.ingress.layer1.yaml#/ccy_country_shares",
                        "ccy_country_weights_cache": "schemas.1A.yaml#/prep/ccy_country_weights_cache",
                    },
                    "countries_union_count": len(iso_union),
                    "countries_output_count": len(iso_union),
                    "policy_narrowed": False,
                    "sum_numeric_ok": sum_numeric_ok,
                    "sum_decimal_dp_ok": sum_decimal_ok,
                    "largest_remainder_ulps": largest_remainder_ulps,
                    "overrides_applied": overrides_applied,
                    "floors_triggered": floors_triggered,
                    "degrade_mode": degrade_mode,
                    "degrade_reason_code": degrade_reason,
                    "N0": n0,
                    "N_eff": n_eff,
                    "dp": dp,
                }
            )

            if emit_sparse_flag:
                sparse_rows.append(
                    {
                        "currency": currency,
                        "is_sparse": n0 < obs_floor,
                        "obs_count": obs_count_value,
                        "threshold": obs_floor,
                    }
                )

            if idx % progress_every == 0 or idx == total_currencies:
                elapsed = time.monotonic() - loop_start
                rate = idx / elapsed if elapsed else 0.0
                eta = (total_currencies - idx) / rate if rate else 0.0
                logger.info(
                    "S5 progress %d/%d (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
                    idx,
                    total_currencies,
                    elapsed,
                    rate,
                    eta,
                )

        if fail_on_degrade and len(degraded_currencies) > 0:
            raise EngineFailure(
                "F4",
                "E_DEGRADE_USED",
                "S5",
                MODULE_NAME,
                {"currencies": degraded_currencies},
            )
        if sum_numeric_pass != len(by_currency):
            raise EngineFailure(
                "F4",
                "E_SUM_NUMERIC",
                "S5",
                MODULE_NAME,
                {"detail": "group_sum_numeric_failed"},
                dataset_id=DATASET_WEIGHTS,
            )
        if sum_decimal_pass != len(by_currency):
            raise EngineFailure(
                "F4",
                "E_SUM_DECIMAL",
                "S5",
                MODULE_NAME,
                {"detail": "decimal_sum_failed"},
                dataset_id=DATASET_WEIGHTS,
            )

        if not weights_rows:
            raise EngineFailure(
                "F4",
                "E_NO_OUTPUTS",
                "S5",
                MODULE_NAME,
                {"detail": "no_weights_rows"},
                dataset_id=DATASET_WEIGHTS,
            )

        weights_df = pl.DataFrame(
            weights_rows,
            schema={
                "currency": pl.Utf8,
                "country_iso": pl.Utf8,
                "weight": pl.Float64,
                "obs_count": pl.Int64,
                "smoothing": pl.Utf8,
            },
        )
        weights_df = weights_df.sort(["currency", "country_iso"])

        prep_schema = _schema_section(schema_1a, "prep")
        validate_dataframe(
            weights_df.iter_rows(named=True),
            prep_schema,
            DATASET_WEIGHTS,
        )

        sparse_df: pl.DataFrame | None = None
        if emit_sparse_flag:
            sparse_df = pl.DataFrame(
                sparse_rows,
                schema={
                    "currency": pl.Utf8,
                    "is_sparse": pl.Boolean,
                    "obs_count": pl.Int64,
                    "threshold": pl.Int64,
                },
            ).sort("currency")
            validate_dataframe(
                sparse_df.iter_rows(named=True),
                prep_schema,
                DATASET_SPARSE,
            )

        produce_merchant_currency = (
            DATASET_LEGAL_TENDER in sealed_ids and DATASET_MERCHANTS in sealed_ids
        )
        merchant_df: pl.DataFrame | None = None
        if produce_merchant_currency:
            legal_path = _sealed_path(sealed_inputs, DATASET_LEGAL_TENDER)
            legal_df = pl.read_parquet(legal_path)
            validate_dataframe(
                legal_df.iter_rows(named=True), schema_ingress, DATASET_LEGAL_TENDER
            )
            legal_dupes = (
                legal_df.group_by("country_iso")
                .len()
                .filter(pl.col("len") > 1)
            )
            if legal_dupes.height > 0:
                raise EngineFailure(
                    "F4",
                    "E_MCURR_RESOLUTION",
                    "S5",
                    MODULE_NAME,
                    {"detail": "iso_legal_tender_duplicates"},
                    dataset_id=DATASET_LEGAL_TENDER,
                )
            legal_map = dict(
                zip(legal_df["country_iso"].to_list(), legal_df["currency"].to_list())
            )

            merchants_path = _sealed_path(sealed_inputs, DATASET_MERCHANTS)
            merchants_df = pl.read_parquet(merchants_path)
            validate_dataframe(
                merchants_df.iter_rows(named=True), schema_ingress, "merchant_ids"
            )
            merchants_df = merchants_df.with_columns(
                pl.col("merchant_id").cast(pl.UInt64)
            )
            missing_isos = sorted(
                {
                    iso
                    for iso in merchants_df["home_country_iso"].to_list()
                    if iso not in legal_map
                }
            )
            if missing_isos:
                logger.info(
                    "S5.0: legal_tender missing coverage (iso_count=%d, iso=%s)",
                    len(missing_isos),
                    ",".join(missing_isos),
                )
                raise EngineFailure(
                    "F4",
                    "E_MCURR_RESOLUTION",
                    "S5",
                    MODULE_NAME,
                    {"missing_iso": missing_isos},
                    dataset_id=DATASET_LEGAL_TENDER,
                )
            dupes = (
                merchants_df.group_by("merchant_id")
                .len()
                .filter(pl.col("len") > 1)
            )
            if dupes.height > 0:
                raise EngineFailure(
                    "F4",
                    "E_MCURR_CARDINALITY",
                    "S5",
                    MODULE_NAME,
                    {"detail": "duplicate_merchant_id"},
                    dataset_id=DATASET_MERCHANTS,
                )
            merchant_ids = merchants_df["merchant_id"].to_list()
            home_isos = merchants_df["home_country_iso"].to_list()
            rows = []
            total_merchants = len(merchant_ids)
            progress_every_m = max(1, min(100_000, total_merchants // 10 if total_merchants else 1))
            loop_start_m = time.monotonic()
            logger.info(
                "S5.0: deriving merchant_currency from home_primary_legal_tender (merchants=%d)",
                total_merchants,
            )
            for idx_m, (merchant_id, iso) in enumerate(zip(merchant_ids, home_isos), start=1):
                currency = legal_map.get(iso)
                if currency is None:
                    raise EngineFailure(
                        "F4",
                        "E_MCURR_RESOLUTION",
                        "S5",
                        MODULE_NAME,
                        {"merchant_id": int(merchant_id), "iso": iso},
                        dataset_id=DATASET_LEGAL_TENDER,
                    )
                rows.append(
                    {
                        "merchant_id": int(merchant_id),
                        "kappa": currency,
                        "source": "home_primary_legal_tender",
                        "tie_break_used": False,
                    }
                )
                if idx_m % progress_every_m == 0 or idx_m == total_merchants:
                    elapsed = time.monotonic() - loop_start_m
                    rate = idx_m / elapsed if elapsed else 0.0
                    eta = (total_merchants - idx_m) / rate if rate else 0.0
                    logger.info(
                        "S5.0 progress %d/%d (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
                        idx_m,
                        total_merchants,
                        elapsed,
                        rate,
                        eta,
                    )
            merchant_df = pl.DataFrame(
                rows,
                schema={
                    "merchant_id": pl.UInt64,
                    "kappa": pl.Utf8,
                    "source": pl.Utf8,
                    "tie_break_used": pl.Boolean,
                },
            ).sort("merchant_id")
            validate_dataframe(
                merchant_df.iter_rows(named=True),
                prep_schema,
                DATASET_MERCHANT_CURRENCY,
            )
        else:
            logger.info("S5.0: merchant_currency skipped (missing source datasets)")

        output_dataset_ids = [DATASET_WEIGHTS]
        if produce_merchant_currency:
            output_dataset_ids.append(DATASET_MERCHANT_CURRENCY)
        if emit_sparse_flag:
            output_dataset_ids.append(DATASET_SPARSE)
        input_dataset_ids = [DATASET_SETTLEMENT, DATASET_CCY, DATASET_ISO]
        if produce_merchant_currency:
            input_dataset_ids.extend([DATASET_LEGAL_TENDER, DATASET_MERCHANTS])

        licence_summary = _license_summary(
            dictionary, license_map, input_dataset_ids + output_dataset_ids
        )

        weights_entry = find_dataset_entry(dictionary, DATASET_WEIGHTS).entry
        weights_root = _resolve_run_path(
            run_paths,
            weights_entry["path"],
            {"parameter_hash": parameter_hash},
        )
        weights_exists = _dataset_has_parquet(weights_root)
        if weights_root.exists() and not weights_exists:
            raise EngineFailure(
                "F4",
                "E_PARTIAL_OUTPUT",
                "S5",
                MODULE_NAME,
                {"dataset_id": DATASET_WEIGHTS, "detail": "partition_exists"},
                dataset_id=DATASET_WEIGHTS,
            )

        if weights_exists:
            existing_weights = pl.read_parquet(
                _select_dataset_file(DATASET_WEIGHTS, weights_root)
            )
            _assert_same_frame(
                weights_df, existing_weights, ["currency", "country_iso"], DATASET_WEIGHTS
            )
            logger.info("S5: existing weights cache detected; validation only")
        elif not validate_only:
            _write_parquet_partition(weights_df, weights_root, DATASET_WEIGHTS)
            logger.info("S5: wrote weights cache (%d rows)", weights_df.height)

        if produce_merchant_currency and merchant_df is not None:
            merchant_entry = find_dataset_entry(dictionary, DATASET_MERCHANT_CURRENCY).entry
            merchant_root = _resolve_run_path(
                run_paths,
                merchant_entry["path"],
                {"parameter_hash": parameter_hash},
            )
            merchant_exists = _dataset_has_parquet(merchant_root)
            if merchant_root.exists() and not merchant_exists:
                raise EngineFailure(
                    "F4",
                    "E_PARTIAL_OUTPUT",
                    "S5",
                    MODULE_NAME,
                    {"dataset_id": DATASET_MERCHANT_CURRENCY, "detail": "partition_exists"},
                    dataset_id=DATASET_MERCHANT_CURRENCY,
                )
            if merchant_exists:
                existing = pl.read_parquet(
                    _select_dataset_file(DATASET_MERCHANT_CURRENCY, merchant_root)
                )
                _assert_same_frame(
                    merchant_df,
                    existing,
                    ["merchant_id"],
                    DATASET_MERCHANT_CURRENCY,
                )
                logger.info("S5.0: existing merchant_currency detected; validation only")
            elif not validate_only:
                _write_parquet_partition(
                    merchant_df, merchant_root, DATASET_MERCHANT_CURRENCY
                )
                logger.info(
                    "S5.0: wrote merchant_currency (%d rows)", merchant_df.height
                )

        if emit_sparse_flag and sparse_df is not None:
            sparse_entry = find_dataset_entry(dictionary, DATASET_SPARSE).entry
            sparse_root = _resolve_run_path(
                run_paths,
                sparse_entry["path"],
                {"parameter_hash": parameter_hash},
            )
            sparse_exists = _dataset_has_parquet(sparse_root)
            if sparse_root.exists() and not sparse_exists:
                raise EngineFailure(
                    "F4",
                    "E_PARTIAL_OUTPUT",
                    "S5",
                    MODULE_NAME,
                    {"dataset_id": DATASET_SPARSE, "detail": "partition_exists"},
                    dataset_id=DATASET_SPARSE,
                )
            if sparse_exists:
                existing = pl.read_parquet(
                    _select_dataset_file(DATASET_SPARSE, sparse_root)
                )
                _assert_same_frame(
                    sparse_df, existing, ["currency"], DATASET_SPARSE
                )
                logger.info("S5: existing sparse_flag detected; validation only")
            elif not validate_only:
                _write_parquet_partition(sparse_df, sparse_root, DATASET_SPARSE)
                logger.info("S5: wrote sparse_flag (%d rows)", sparse_df.height)

        trace_after = _trace_snapshot(trace_path)
        before_events, before_draws, _ = _trace_totals(trace_before)
        after_events, after_draws, _ = _trace_totals(trace_after)
        if trace_before != trace_after:
            raise EngineFailure(
                "F4",
                "E_RNG_INTERACTION",
                "S5",
                MODULE_NAME,
                {"detail": "rng_trace_changed"},
            )

        coverage_union_pass = all(
            row["countries_union_count"] == row["countries_output_count"]
            for row in by_currency
        )
        if not coverage_union_pass:
            raise EngineFailure(
                "F4",
                "E_COVERAGE",
                "S5",
                MODULE_NAME,
                {"detail": "union_coverage_mismatch"},
            )

        receipt_entry = find_dataset_entry(dictionary, DATASET_RECEIPT).entry
        passed_entry = find_dataset_entry(dictionary, DATASET_PASSED).entry
        receipt_path = _resolve_run_path(
            run_paths,
            receipt_entry["path"],
            {"parameter_hash": parameter_hash},
        )
        passed_flag_path = _resolve_run_path(
            run_paths,
            passed_entry["path"],
            {"parameter_hash": parameter_hash},
        )

        receipt_payload = {
            "parameter_hash": parameter_hash,
            "policy_digest": policy_digest,
            "producer": PRODUCER,
            "schema_refs": {
                "settlement_shares": "schemas.ingress.layer1.yaml#/settlement_shares",
                "ccy_country_shares": "schemas.ingress.layer1.yaml#/ccy_country_shares",
                "ccy_country_weights_cache": "schemas.1A.yaml#/prep/ccy_country_weights_cache",
            },
            "currencies_total": total_currencies,
            "currencies_processed": len(by_currency),
            "rows_written": len(weights_rows),
            "sum_numeric_pass": sum_numeric_pass,
            "sum_decimal_dp_pass": sum_decimal_pass,
            "largest_remainder_total_ulps": sum(largest_remainder_ulps_list),
            "largest_remainder_ulps_quantiles": {
                "p50": _quantile_int(largest_remainder_ulps_list, 0.50),
                "p95": _quantile_int(largest_remainder_ulps_list, 0.95),
                "p99": _quantile_int(largest_remainder_ulps_list, 0.99),
            },
            "overrides_applied_count": overrides_applied_count,
            "floors_triggered_count": floors_triggered_count,
            "degrade_mode_counts": degrade_counts,
            "coverage_union_pass": coverage_union_pass,
            "coverage_policy_narrowed": False,
            "rng_trace_delta_events": int(after_events - before_events),
            "rng_trace_delta_draws": int(after_draws - before_draws),
            "policy_narrowed_currencies": [],
            "degraded_currencies": degraded_currencies,
            "licence_summary": licence_summary,
            "by_currency": by_currency,
        }
        if produce_merchant_currency:
            receipt_payload["schema_refs"]["merchant_currency"] = (
                "schemas.1A.yaml#/prep/merchant_currency"
            )
        if emit_sparse_flag:
            receipt_payload["schema_refs"]["sparse_flag"] = (
                "schemas.1A.yaml#/prep/sparse_flag"
            )

        if receipt_path.exists() and passed_flag_path.exists():
            existing = _load_json(receipt_path)
            if existing != receipt_payload:
                raise EngineFailure(
                    "F4",
                    "E_RECEIPT_MISMATCH",
                    "S5",
                    MODULE_NAME,
                    {"detail": "receipt_mismatch"},
                )
            expected_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            flag_contents = passed_flag_path.read_text(encoding="ascii").strip()
            if f"sha256_hex = {expected_hash}" != flag_contents:
                raise EngineFailure(
                    "F4",
                    "E_RECEIPT_MISMATCH",
                    "S5",
                    MODULE_NAME,
                    {"detail": "passed_flag_mismatch"},
                )
            logger.info("S5: existing receipt validated")
        else:
            _write_receipt(receipt_path, passed_flag_path, receipt_payload)
            logger.info("S5: wrote S5_VALIDATION.json + _passed.flag")

        timer.info("S5: completed")
        _emit_state_run("completed")
        return S5RunResult(
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            weights_root=weights_root,
        )
    except EngineFailure as failure:
        _record_failure(failure)
        raise
    except (ContractError, InputResolutionError, SchemaValidationError) as exc:
        failure = EngineFailure(
            "F5" if isinstance(exc, InputResolutionError) else "F4",
            "s5_contract_failure",
            "S5",
            MODULE_NAME,
            {"detail": str(exc)},
        )
        _record_failure(failure)
        raise


__all__ = ["S5RunResult", "run_s5"]
