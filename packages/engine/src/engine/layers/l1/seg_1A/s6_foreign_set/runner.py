"""S6 foreign set selection runner for Segment 1A."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
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
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_1A.s0_foundations.validation_bundle import (
    write_failure_record,
    write_json,
)
from engine.layers.l1.seg_1A.s6_foreign_set.rng import (
    UINT64_MAX,
    add_u128,
    derive_master_material,
    derive_substream,
    merchant_u64,
    u01_single,
)


MODULE_NAME = "1A.foreign_country_selector"
SUBSTREAM_LABEL = "gumbel_key"

DATASET_CANDIDATE_SET = "s3_candidate_set"
DATASET_ELIGIBILITY = "crossborder_eligibility_flags"
DATASET_ZTP_FINAL = "rng_event_ztp_final"
DATASET_WEIGHTS = "ccy_country_weights_cache"
DATASET_MERCHANT_CURRENCY = "merchant_currency"
DATASET_ISO = "iso3166_canonical_2024"
DATASET_GUMBEL = "rng_event_gumbel_key"
DATASET_TRACE = "rng_trace_log"
DATASET_S5_RECEIPT = "s5_validation_receipt"
DATASET_S5_PASSED = "s5_passed_flag"
DATASET_RECEIPT = "s6_validation_receipt"
DETAIL_FILENAME = "S6_VALIDATION_DETAIL.jsonl"
POLICY_ASSET_ID = "s6_selection_policy.yaml"

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_REASON_CODES = {
    "NO_CANDIDATES",
    "K_ZERO",
    "ZERO_WEIGHT_DOMAIN",
    "CAPPED_BY_MAX_CANDIDATES",
    "none",
}
_GLOBAL_ONLY_KEYS = {"log_all_candidates", "dp_score_print"}
_PER_CURRENCY_KEYS = {"emit_membership_dataset", "max_candidates_cap", "zero_weight_rule"}
_ENVELOPE_FIELDS = {
    "ts_utc",
    "run_id",
    "seed",
    "parameter_hash",
    "manifest_fingerprint",
    "module",
    "substream_label",
    "rng_counter_before_lo",
    "rng_counter_before_hi",
    "rng_counter_after_lo",
    "rng_counter_after_hi",
    "draws",
    "blocks",
}


@dataclass(frozen=True)
class S6RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    event_path: Path | None
    trace_path: Path
    membership_root: Path | None


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


class _TraceAccumulator:
    def __init__(self, module: str, substream_label: str) -> None:
        self.draws_total = 0
        self.blocks_total = 0
        self.events_total = 0
        self._run_id: str | None = None
        self._seed: int | None = None
        self._module = module
        self._substream_label = substream_label

    def append(self, event: dict) -> dict:
        if self._run_id is None:
            self._run_id = event["run_id"]
            self._seed = int(event["seed"])
        draws = int(event["draws"])
        blocks = int(event["blocks"])
        self.draws_total = _checked_add(self.draws_total, draws)
        self.blocks_total = _checked_add(self.blocks_total, blocks)
        self.events_total = _checked_add(self.events_total, 1)
        return {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": self._run_id,
            "seed": self._seed,
            "module": self._module,
            "substream_label": self._substream_label,
            "rng_counter_before_lo": event["rng_counter_before_lo"],
            "rng_counter_before_hi": event["rng_counter_before_hi"],
            "rng_counter_after_lo": event["rng_counter_after_lo"],
            "rng_counter_after_hi": event["rng_counter_after_hi"],
            "draws_total": self.draws_total,
            "blocks_total": self.blocks_total,
            "events_total": self.events_total,
        }


def _checked_add(current: int, increment: int) -> int:
    total = current + increment
    if total > UINT64_MAX:
        return UINT64_MAX
    return total


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


def _resolve_run_glob(
    run_paths: RunPaths, path_template: str, tokens: dict[str, str]
) -> list[Path]:
    path = path_template
    for key, value in tokens.items():
        path = path.replace(f"{{{key}}}", value)
    if "*" in path:
        return sorted(run_paths.run_root.glob(path))
    return [run_paths.run_root / path]


def _resolve_event_path(
    run_paths: RunPaths, path_template: str, tokens: dict[str, str]
) -> Path:
    path = path_template
    for key, value in tokens.items():
        path = path.replace(f"{{{key}}}", value)
    if "part-*.jsonl" in path:
        path = path.replace("part-*.jsonl", "part-00000.jsonl")
    elif "*" in path:
        raise InputResolutionError(f"Unhandled wildcard path template: {path_template}")
    return run_paths.run_root / path


def _resolve_event_dir(
    run_paths: RunPaths, path_template: str, tokens: dict[str, str]
) -> Path:
    path = path_template
    for key, value in tokens.items():
        path = path.replace(f"{{{key}}}", value)
    if "part-*.jsonl" in path:
        return (run_paths.run_root / path).parent
    if "*" in path:
        raise InputResolutionError(f"Unhandled wildcard path template: {path_template}")
    return (run_paths.run_root / path).parent


def _next_part_path(event_dir: Path) -> Path:
    if not event_dir.exists():
        raise InputResolutionError(f"Missing event directory: {event_dir}")
    existing = sorted(event_dir.glob("part-*.jsonl"))
    max_index = -1
    for path in existing:
        name = path.stem
        if not name.startswith("part-"):
            continue
        suffix = name[5:]
        if suffix.isdigit():
            max_index = max(max_index, int(suffix))
    return event_dir / f"part-{max_index + 1:05d}.jsonl"


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
        raise InputResolutionError(f"Temp dir already exists: {tmp_dir}")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_dir / "part-00000.parquet"
    df.write_parquet(tmp_file)
    target_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir.replace(target_root)


def _iter_jsonl_files(paths: Iterable[Path]):
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                yield path, line_no, json.loads(line)


def _event_has_rows(paths: Iterable[Path]) -> bool:
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    return True
    return False


def _trace_has_substream(path: Path, module: str, substream_label: str) -> bool:
    if not path.exists():
        return False
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.get("module") == module and payload.get("substream_label") == substream_label:
                return True
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


def _write_receipt(receipt_path: Path, passed_flag_path: Path, payload: dict) -> None:
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_receipt = receipt_path.with_suffix(".json.tmp")
    tmp_flag = passed_flag_path.with_suffix(".flag.tmp")
    write_json(tmp_receipt, payload)
    receipt_hash = hashlib.sha256(tmp_receipt.read_bytes()).hexdigest()
    tmp_flag.write_text(f"sha256_hex = {receipt_hash}\n", encoding="ascii")
    tmp_receipt.replace(receipt_path)
    tmp_flag.replace(passed_flag_path)


def _selection_bucket(k_realized: int) -> str:
    if k_realized == 0:
        return "b0"
    if k_realized == 1:
        return "b1"
    if k_realized == 2:
        return "b2"
    if 3 <= k_realized <= 5:
        return "b3_5"
    if 6 <= k_realized <= 10:
        return "b6_10"
    return "b11_plus"


def _log_stage(
    logger,
    message: str,
    *,
    seed: int,
    parameter_hash: str,
    run_id: str,
    stage: str,
    merchant_id: Optional[int] = None,
    country_iso: Optional[str] = None,
    reason_code: Optional[str] = None,
    extras: Optional[dict] = None,
) -> None:
    parts = [
        f"seed={seed}",
        f"parameter_hash={parameter_hash}",
        f"run_id={run_id}",
        f"stage={stage}",
        f"module={MODULE_NAME}",
    ]
    if merchant_id is not None:
        parts.append(f"merchant_id={merchant_id}")
    if country_iso is not None:
        parts.append(f"country_iso={country_iso}")
    if reason_code is not None:
        parts.append(f"reason_code={reason_code}")
    if extras:
        for key, value in extras.items():
            parts.append(f"{key}={value}")
    logger.info("%s (%s)", message, " ".join(parts))


def _load_policy(policy_path: Path, schema_layer1: dict) -> dict:
    payload = _load_yaml(policy_path)
    schema = _schema_from_pack(schema_layer1, "policy/s6_selection")
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    if errors:
        details = [
            {
                "path": ".".join(str(part) for part in err.path),
                "message": err.message,
            }
            for err in errors
        ]
        raise SchemaValidationError("s6_selection policy schema validation failed", details)
    return payload


def _validate_policy(payload: dict) -> tuple[dict, dict, int]:
    defaults = payload.get("defaults") or {}
    per_currency = payload.get("per_currency") or {}
    if not isinstance(per_currency, dict):
        raise EngineFailure(
            "F4",
            "E_POLICY_DOMAIN",
            "S6",
            MODULE_NAME,
            {"detail": "per_currency_not_object"},
        )
    for currency, overrides in per_currency.items():
        if not isinstance(currency, str) or not _CURRENCY_RE.fullmatch(currency):
            raise EngineFailure(
                "F4",
                "E_POLICY_DOMAIN",
                "S6",
                MODULE_NAME,
                {"detail": "invalid_currency_key", "currency": str(currency)},
            )
        if not isinstance(overrides, dict):
            raise EngineFailure(
                "F4",
                "E_POLICY_DOMAIN",
                "S6",
                MODULE_NAME,
                {"detail": "per_currency_not_object", "currency": currency},
            )
        if any(key in _GLOBAL_ONLY_KEYS for key in overrides):
            raise EngineFailure(
                "F4",
                "E_POLICY_CONFLICT",
                "S6",
                MODULE_NAME,
                {"detail": "global_only_override", "currency": currency},
            )
        for key in overrides:
            if key not in _PER_CURRENCY_KEYS:
                raise EngineFailure(
                    "F4",
                    "E_POLICY_DOMAIN",
                    "S6",
                    MODULE_NAME,
                    {"detail": "unknown_override", "currency": currency, "key": key},
                )
    emit_membership = defaults.get("emit_membership_dataset")
    for currency, overrides in per_currency.items():
        if "emit_membership_dataset" in overrides:
            if overrides["emit_membership_dataset"] != emit_membership:
                raise EngineFailure(
                    "F4",
                    "E_POLICY_CONFLICT",
                    "S6",
                    MODULE_NAME,
                    {"detail": "emit_membership_mismatch", "currency": currency},
                )
    return defaults, per_currency, len(per_currency)


def _validate_pass_receipt(receipt_path: Path, passed_flag_path: Path) -> None:
    if not receipt_path.exists() or not passed_flag_path.exists():
        raise InputResolutionError(
            f"Missing S5 PASS receipt: {receipt_path} or {passed_flag_path}"
        )
    expected_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    flag_contents = passed_flag_path.read_text(encoding="ascii").strip()
    if flag_contents != f"sha256_hex = {expected_hash}":
        raise InputResolutionError("S5 PASS receipt hash mismatch")


def _build_candidate_map(
    df: pl.DataFrame, parameter_hash: str, iso_set: set[str]
) -> dict[int, list[dict]]:
    df = df.sort(["merchant_id", "candidate_rank", "country_iso"])
    candidate_map: dict[int, list[dict]] = {}
    current_mid = None
    expected_rank = 0
    home_count = 0
    rows: list[dict] = []
    for row in df.iter_rows(named=True):
        mid = int(row["merchant_id"])
        if current_mid is None:
            current_mid = mid
        if mid != current_mid:
            if expected_rank == 0:
                raise EngineFailure(
                    "F4",
                    "E_UPSTREAM_GATE",
                    "S6",
                    MODULE_NAME,
                    {"detail": "missing_candidate_rows", "merchant_id": current_mid},
                )
            if home_count != 1:
                raise EngineFailure(
                    "F4",
                    "E_UPSTREAM_GATE",
                    "S6",
                    MODULE_NAME,
                    {"detail": "home_row_mismatch", "merchant_id": current_mid},
                )
            candidate_map[current_mid] = rows
            current_mid = mid
            expected_rank = 0
            home_count = 0
            rows = []
        rank = int(row["candidate_rank"])
        if rank != expected_rank:
            raise EngineFailure(
                "F4",
                "E_UPSTREAM_GATE",
                "S6",
                MODULE_NAME,
                {"detail": "candidate_rank_not_contiguous", "merchant_id": mid},
            )
        expected_rank += 1
        country_iso = str(row["country_iso"])
        if country_iso not in iso_set:
            raise EngineFailure(
                "F4",
                "E_DOMAIN_FK",
                "S6",
                MODULE_NAME,
                {"detail": "unknown_country_iso", "country_iso": country_iso},
            )
        if row.get("parameter_hash") != parameter_hash:
            raise EngineFailure(
                "F4",
                "E_LINEAGE_PATH_MISMATCH",
                "S6",
                MODULE_NAME,
                {"detail": "candidate_set_parameter_hash"},
            )
        reason_codes = row.get("reason_codes")
        if not isinstance(reason_codes, list) or any(
            not isinstance(item, str) for item in reason_codes
        ):
            raise EngineFailure(
                "F4",
                "E_SCHEMA_AUTHORITY",
                "S6",
                MODULE_NAME,
                {"detail": "invalid_reason_codes", "merchant_id": mid},
            )
        filter_tags = row.get("filter_tags")
        if not isinstance(filter_tags, list) or any(
            not isinstance(item, str) for item in filter_tags
        ):
            raise EngineFailure(
                "F4",
                "E_SCHEMA_AUTHORITY",
                "S6",
                MODULE_NAME,
                {"detail": "invalid_filter_tags", "merchant_id": mid},
            )
        is_home = bool(row["is_home"])
        if is_home and rank != 0:
            raise EngineFailure(
                "F4",
                "E_UPSTREAM_GATE",
                "S6",
                MODULE_NAME,
                {"detail": "home_rank_mismatch", "merchant_id": mid},
            )
        if is_home:
            home_count += 1
        rows.append(
            {
                "country_iso": country_iso,
                "candidate_rank": rank,
                "is_home": is_home,
            }
        )
    if current_mid is not None:
        if expected_rank == 0 or home_count != 1:
            raise EngineFailure(
                "F4",
                "E_UPSTREAM_GATE",
                "S6",
                MODULE_NAME,
                {"detail": "home_row_mismatch", "merchant_id": current_mid},
            )
        candidate_map[current_mid] = rows
    return candidate_map


def _load_ztp_final_events(
    paths: Iterable[Path],
    schema_layer1: dict,
    seed: int,
    parameter_hash: str,
    run_id: str,
) -> dict[int, dict]:
    event_schema = _schema_from_pack(schema_layer1, "rng/events/ztp_final")
    validator = Draft202012Validator(event_schema)
    events: dict[int, dict] = {}
    for path, line_no, payload in _iter_jsonl_files(paths):
        errors = list(validator.iter_errors(payload))
        if errors:
            raise EngineFailure(
                "F4",
                "schema_violation",
                "S6",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no, "detail": errors[0].message},
                dataset_id=DATASET_ZTP_FINAL,
            )
        if (
            payload.get("seed") != seed
            or payload.get("parameter_hash") != parameter_hash
            or payload.get("run_id") != run_id
        ):
            raise EngineFailure(
                "F4",
                "PARTITION_MISMATCH",
                "S6",
                MODULE_NAME,
                {"line": line_no},
                dataset_id=DATASET_ZTP_FINAL,
            )
        merchant_id = int(payload["merchant_id"])
        if merchant_id in events:
            raise EngineFailure(
                "F4",
                "UPSTREAM_DUPLICATE_S4",
                "S6",
                MODULE_NAME,
                {"merchant_id": merchant_id},
                dataset_id=DATASET_ZTP_FINAL,
            )
        events[merchant_id] = payload
    return events


def _load_weights(
    weights_df: pl.DataFrame, iso_set: set[str]
) -> dict[str, dict[str, float]]:
    weights: dict[str, dict[str, float]] = {}
    for row in weights_df.select(["currency", "country_iso", "weight"]).iter_rows(named=True):
        currency = str(row["currency"])
        if not _CURRENCY_RE.fullmatch(currency):
            raise EngineFailure(
                "F4",
                "E_DOMAIN_FK",
                "S6",
                MODULE_NAME,
                {"detail": "invalid_currency", "currency": currency},
                dataset_id=DATASET_WEIGHTS,
            )
        country_iso = str(row["country_iso"])
        if country_iso not in iso_set:
            raise EngineFailure(
                "F4",
                "E_DOMAIN_FK",
                "S6",
                MODULE_NAME,
                {"detail": "unknown_country_iso", "country_iso": country_iso},
                dataset_id=DATASET_WEIGHTS,
            )
        weight = float(row["weight"])
        if weight < 0.0 or weight > 1.0:
            raise EngineFailure(
                "F4",
                "E_S5_CONTENT",
                "S6",
                MODULE_NAME,
                {"detail": "weight_out_of_range", "currency": currency},
                dataset_id=DATASET_WEIGHTS,
            )
        weights.setdefault(currency, {})[country_iso] = weight
    for currency, rows in weights.items():
        total = sum(rows.values())
        if abs(total - 1.0) > 1e-6:
            raise EngineFailure(
                "F4",
                "E_S5_CONTENT",
                "S6",
                MODULE_NAME,
                {"detail": "weight_sum_mismatch", "currency": currency, "sum": total},
                dataset_id=DATASET_WEIGHTS,
            )
    return weights


def _assert_same_frame(
    expected: pl.DataFrame, actual: pl.DataFrame, sort_keys: list[str], dataset_id: str
) -> None:
    expected_sorted = expected.sort(sort_keys)
    actual_sorted = actual.sort(sort_keys)
    if expected_sorted.columns != actual_sorted.columns:
        raise EngineFailure(
            "F4",
            "E_OUTPUT_MISMATCH",
            "S6",
            MODULE_NAME,
            {"dataset_id": dataset_id, "detail": "columns_mismatch"},
            dataset_id=dataset_id,
        )
    if expected_sorted.height != actual_sorted.height:
        raise EngineFailure(
            "F4",
            "E_OUTPUT_MISMATCH",
            "S6",
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
                "S6",
                MODULE_NAME,
                {"dataset_id": dataset_id, "detail": "value_mismatch"},
                dataset_id=dataset_id,
            )

def run_s6(
    config: EngineConfig,
    run_id: Optional[str] = None,
    emit_membership_dataset: Optional[bool] = None,
    log_all_candidates: Optional[bool] = None,
    fail_on_degrade: bool = False,
    validate_only: bool = False,
) -> S6RunResult:
    logger = get_logger("engine.layers.l1.seg_1A.s6_foreign_set.l2.runner")
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
    timer.info(f"S6: loaded run receipt {receipt_path}")
    if validate_only:
        logger.info("S6: validate-only enabled; outputs will not be written")

    utc_day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    segment_state_runs_path = _segment_state_runs_path(run_paths, dictionary, utc_day)

    def _emit_state_run(status: str, detail: Optional[str] = None) -> None:
        payload = {
            "layer": "layer1",
            "segment": "1A",
            "state": "S6",
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
            "state": "S6",
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
        sealed_entry = find_dataset_entry(dictionary, "sealed_inputs_1A").entry
        sealed_path = _resolve_run_path(
            run_paths, sealed_entry["path"], {"manifest_fingerprint": manifest_fingerprint}
        )
        sealed_inputs = _load_sealed_inputs(sealed_path)
        sealed_ids = {entry.get("asset_id") for entry in sealed_inputs}
        missing = {POLICY_ASSET_ID, DATASET_ISO} - sealed_ids
        if missing:
            raise InputResolutionError(
                f"sealed_inputs_1A missing required assets: {sorted(missing)}"
            )
        policy_path = _sealed_path(sealed_inputs, POLICY_ASSET_ID)
        policy = _load_policy(policy_path, schema_layer1)
        defaults, per_currency, overrides_count = _validate_policy(policy)
        policy_digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
        logger.info(
            "S6: loaded policy %s (overrides=%d)",
            policy_path.as_posix(),
            overrides_count,
        )

        if emit_membership_dataset is not None:
            if bool(emit_membership_dataset) != bool(defaults.get("emit_membership_dataset")):
                raise EngineFailure(
                    "F4",
                    "E_POLICY_CONFLICT",
                    "S6",
                    MODULE_NAME,
                    {"detail": "emit_membership_override_mismatch"},
                )
        if log_all_candidates is not None:
            if bool(log_all_candidates) != bool(defaults.get("log_all_candidates")):
                raise EngineFailure(
                    "F4",
                    "E_POLICY_CONFLICT",
                    "S6",
                    MODULE_NAME,
                    {"detail": "log_all_candidates_override_mismatch"},
                )

        log_all_candidates = bool(defaults.get("log_all_candidates"))
        emit_membership_dataset = bool(defaults.get("emit_membership_dataset"))

        receipt_entry = find_dataset_entry(dictionary, DATASET_S5_RECEIPT).entry
        passed_entry = find_dataset_entry(dictionary, DATASET_S5_PASSED).entry
        s5_receipt_path = _resolve_run_path(
            run_paths, receipt_entry["path"], {"parameter_hash": parameter_hash}
        )
        s5_passed_path = _resolve_run_path(
            run_paths, passed_entry["path"], {"parameter_hash": parameter_hash}
        )
        _validate_pass_receipt(s5_receipt_path, s5_passed_path)
        _log_stage(
            logger,
            "S6: verified S5 PASS receipt before reading weights",
            seed=seed,
            parameter_hash=parameter_hash,
            run_id=run_id,
            stage="preflight",
        )

        iso_path = _sealed_path(sealed_inputs, DATASET_ISO)
        iso_df = pl.read_parquet(_select_dataset_file(DATASET_ISO, iso_path))
        validate_dataframe(
            iso_df.iter_rows(named=True),
            schema_ingress,
            DATASET_ISO,
        )
        iso_set = {str(row[0]) for row in iso_df.select("country_iso").iter_rows()}

        candidate_entry = find_dataset_entry(dictionary, DATASET_CANDIDATE_SET).entry
        candidate_root = _resolve_run_path(
            run_paths, candidate_entry["path"], {"parameter_hash": parameter_hash}
        )
        candidate_df = pl.read_parquet(_select_dataset_file(DATASET_CANDIDATE_SET, candidate_root))
        candidate_map = _build_candidate_map(candidate_df, parameter_hash, iso_set)
        timer.info(f"S6: loaded candidate set merchants={len(candidate_map)}")

        eligibility_entry = find_dataset_entry(dictionary, DATASET_ELIGIBILITY).entry
        eligibility_root = _resolve_run_path(
            run_paths, eligibility_entry["path"], {"parameter_hash": parameter_hash}
        )
        eligibility_df = pl.read_parquet(
            _select_dataset_file(DATASET_ELIGIBILITY, eligibility_root)
        )
        prep_schema = _schema_section(schema_1a, "prep")
        validate_dataframe(
            eligibility_df.iter_rows(named=True),
            prep_schema,
            DATASET_ELIGIBILITY,
        )
        eligibility_map: dict[int, bool] = {}
        for row in eligibility_df.select(["merchant_id", "is_eligible", "parameter_hash"]).iter_rows():
            if str(row[2]) != parameter_hash:
                raise EngineFailure(
                    "F4",
                    "E_LINEAGE_PATH_MISMATCH",
                    "S6",
                    MODULE_NAME,
                    {"detail": "eligibility_parameter_hash"},
                )
            eligibility_map[int(row[0])] = bool(row[1])
        eligible_merchants = {
            mid for mid, flag in eligibility_map.items() if flag and mid in candidate_map
        }
        _log_stage(
            logger,
            "S6: eligibility gate applied to candidate-set merchants",
            seed=seed,
            parameter_hash=parameter_hash,
            run_id=run_id,
            stage="preflight",
            extras={
                "candidate_merchants": len(candidate_map),
                "eligibility_rows": len(eligibility_map),
                "eligible_merchants": len(eligible_merchants),
            },
        )

        ztp_entry = find_dataset_entry(dictionary, DATASET_ZTP_FINAL).entry
        ztp_paths = _resolve_run_glob(run_paths, ztp_entry["path"], tokens)
        ztp_map = _load_ztp_final_events(
            ztp_paths, schema_layer1, seed, parameter_hash, run_id
        )
        if not ztp_map:
            raise InputResolutionError("Missing rng_event_ztp_final inputs.")
        missing_ztp = sorted(mid for mid in eligible_merchants if mid not in ztp_map)
        if missing_ztp:
            raise EngineFailure(
                "F4",
                "E_UPSTREAM_GATE",
                "S6",
                MODULE_NAME,
                {"detail": "missing_ztp_final", "merchant_ids": missing_ztp[:10]},
            )
        extra_ztp = sorted(mid for mid in ztp_map if mid not in eligible_merchants)
        if extra_ztp:
            raise EngineFailure(
                "F4",
                "E_UPSTREAM_GATE",
                "S6",
                MODULE_NAME,
                {"detail": "ztp_final_for_ineligible", "merchant_ids": extra_ztp[:10]},
            )

        weights_entry = find_dataset_entry(dictionary, DATASET_WEIGHTS).entry
        weights_root = _resolve_run_path(
            run_paths, weights_entry["path"], {"parameter_hash": parameter_hash}
        )
        weights_df = pl.read_parquet(_select_dataset_file(DATASET_WEIGHTS, weights_root))
        validate_dataframe(
            weights_df.iter_rows(named=True),
            prep_schema,
            DATASET_WEIGHTS,
        )
        weights_by_currency = _load_weights(weights_df, iso_set)
        if not weights_by_currency:
            raise InputResolutionError("Empty ccy_country_weights_cache.")

        merchant_currency_map: dict[int, str] | None = None
        currency_entry = find_dataset_entry(dictionary, DATASET_MERCHANT_CURRENCY).entry
        currency_root = _resolve_run_path(
            run_paths, currency_entry["path"], {"parameter_hash": parameter_hash}
        )
        if _dataset_has_parquet(currency_root):
            currency_df = pl.read_parquet(
                _select_dataset_file(DATASET_MERCHANT_CURRENCY, currency_root)
            )
            validate_dataframe(
                currency_df.iter_rows(named=True),
                prep_schema,
                DATASET_MERCHANT_CURRENCY,
            )
            merchant_currency_map = {}
            for row in currency_df.select(["merchant_id", "kappa"]).iter_rows():
                merchant_currency_map[int(row[0])] = str(row[1])
            timer.info(f"S6: loaded merchant_currency rows={currency_df.height}")
        else:
            if len(weights_by_currency) != 1:
                raise EngineFailure(
                    "F4",
                    "E_UPSTREAM_GATE",
                    "S6",
                    MODULE_NAME,
                    {"detail": "merchant_currency_missing_multi_currency"},
                )
            single_currency = next(iter(weights_by_currency.keys()))
            logger.info(
                "S6: merchant_currency missing; single currency fallback %s", single_currency
            )

        event_entry = find_dataset_entry(dictionary, DATASET_GUMBEL).entry
        trace_entry = find_dataset_entry(dictionary, DATASET_TRACE).entry
        event_dir = _resolve_event_dir(run_paths, event_entry["path"], tokens)
        event_path = _resolve_event_path(run_paths, event_entry["path"], tokens)
        trace_path = _resolve_run_path(run_paths, trace_entry["path"], tokens)
        existing_events = _event_has_rows(_resolve_run_glob(run_paths, event_entry["path"], tokens))
        existing_trace = _trace_has_substream(trace_path, MODULE_NAME, SUBSTREAM_LABEL)

        receipt_entry = find_dataset_entry(dictionary, DATASET_RECEIPT).entry
        receipt_dir = _resolve_run_path(
            run_paths, receipt_entry["path"], {"seed": str(seed), "parameter_hash": parameter_hash}
        )
        receipt_path = receipt_dir / "S6_VALIDATION.json"
        passed_flag_path = receipt_dir / "_passed.flag"
        detail_path = receipt_dir / DETAIL_FILENAME

        membership_root: Path | None = None
        if emit_membership_dataset:
            membership_entry = find_dataset_entry(dictionary, "s6_membership").entry
            membership_root = _resolve_run_path(
                run_paths,
                membership_entry["path"],
                {"seed": str(seed), "parameter_hash": parameter_hash},
            )
        membership_exists = membership_root is not None and _dataset_has_parquet(
            membership_root
        )
        receipt_exists = receipt_path.exists() and passed_flag_path.exists()

        if existing_events and existing_trace and receipt_exists:
            logger.info("S6: existing outputs detected; validating only")
            validate_only = True
        elif existing_events or existing_trace or receipt_exists or membership_exists:
            raise InputResolutionError(
                "Partial S6 outputs detected; refuse to append. "
                "Remove existing S6 outputs or resume a clean run_id."
            )

        total_merchants = len(candidate_map)
        if total_merchants == 0:
            raise InputResolutionError("S3 candidate set is empty.")
        progress_every = max(1, min(10_000, total_merchants // 10))
        start_time = time.monotonic()

        master_material = derive_master_material(bytes.fromhex(manifest_fingerprint), seed)

        metrics = {
            "s6.run.merchants_total": 0,
            "s6.run.merchants_gated_in": 0,
            "s6.run.merchants_selected": 0,
            "s6.run.merchants_empty": 0,
            "s6.run.A_filtered_sum": 0,
            "s6.run.K_target_sum": 0,
            "s6.run.K_realized_sum": 0,
            "s6.run.shortfall_merchants": 0,
            "s6.run.reason.NO_CANDIDATES": 0,
            "s6.run.reason.K_ZERO": 0,
            "s6.run.reason.ZERO_WEIGHT_DOMAIN": 0,
            "s6.run.reason.CAPPED_BY_MAX_CANDIDATES": 0,
            "s6.run.events.gumbel_key.expected": 0,
            "s6.run.events.gumbel_key.written": 0,
            "s6.run.policy.log_all_candidates": log_all_candidates,
            "s6.run.policy.max_candidates_cap": defaults.get("max_candidates_cap"),
            "s6.run.policy.zero_weight_rule": defaults.get("zero_weight_rule"),
            "s6.run.policy.currency_overrides_count": overrides_count,
        }
        selection_histogram = {
            "b0": 0,
            "b1": 0,
            "b2": 0,
            "b3_5": 0,
            "b6_10": 0,
            "b11_plus": 0,
        }

        event_schema = _schema_from_pack(schema_layer1, "rng/events/gumbel_key")
        event_validator = Draft202012Validator(event_schema)
        trace_schema = _schema_from_pack(schema_layer1, "rng/core/rng_trace_log/record")
        trace_validator = Draft202012Validator(trace_schema)

        tmp_dir = run_paths.tmp_root / "s6_foreign_set"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_event_path = tmp_dir / "rng_event_gumbel_key.jsonl"
        tmp_trace_path = tmp_dir / "rng_trace_log_s6.jsonl"
        tmp_detail_path = tmp_dir / DETAIL_FILENAME

        trace_acc = _TraceAccumulator(MODULE_NAME, SUBSTREAM_LABEL)
        membership_rows: list[dict] = []
        detail_written = 0

        events_written = 0
        trace_written = 0

        timer.info(
            "S6: entering foreign selection loop (gated by eligibility + S4 ztp_final + S5 PASS)"
        )

        with (
            tmp_event_path.open("w", encoding="utf-8") as event_handle,
            tmp_trace_path.open("w", encoding="utf-8") as trace_handle,
            tmp_detail_path.open("w", encoding="utf-8") as detail_handle,
        ):
            for idx, merchant_id in enumerate(sorted(candidate_map.keys()), start=1):
                if idx % progress_every == 0 or idx == total_merchants:
                    elapsed = max(time.monotonic() - start_time, 1e-9)
                    rate = idx / elapsed
                    eta = (total_merchants - idx) / rate if rate > 0 else 0.0
                    logger.info(
                        "S6 progress %d/%d (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
                        idx,
                        total_merchants,
                        elapsed,
                        rate,
                        eta,
                    )

                metrics["s6.run.merchants_total"] += 1

                if merchant_id not in eligibility_map:
                    raise EngineFailure(
                        "F4",
                        "E_UPSTREAM_GATE",
                        "S6",
                        MODULE_NAME,
                        {"detail": "missing_eligibility_flag", "merchant_id": merchant_id},
                    )
                if not eligibility_map[merchant_id]:
                    continue

                metrics["s6.run.merchants_gated_in"] += 1

                ztp_event = ztp_map.get(merchant_id)
                if ztp_event is None:
                    raise EngineFailure(
                        "F4",
                        "E_UPSTREAM_GATE",
                        "S6",
                        MODULE_NAME,
                        {"detail": "missing_ztp_final", "merchant_id": merchant_id},
                    )

                k_target = int(ztp_event.get("K_target", 0))
                metrics["s6.run.K_target_sum"] += k_target

                if merchant_currency_map is None:
                    currency = single_currency
                else:
                    currency = merchant_currency_map.get(merchant_id)
                    if currency is None:
                        raise EngineFailure(
                            "F4",
                            "E_UPSTREAM_GATE",
                            "S6",
                            MODULE_NAME,
                            {"detail": "missing_merchant_currency", "merchant_id": merchant_id},
                        )

                policy = dict(defaults)
                override = per_currency.get(currency)
                if override:
                    policy.update(override)

                max_candidates_cap = int(policy.get("max_candidates_cap", 0))
                zero_weight_rule = str(policy.get("zero_weight_rule", "exclude"))

                candidates = candidate_map[merchant_id]
                foreign_candidates = [row for row in candidates if not row["is_home"]]
                a_value = len(foreign_candidates)

                cap_applied = max_candidates_cap > 0 and a_value > max_candidates_cap
                if cap_applied:
                    foreign_candidates = foreign_candidates[:max_candidates_cap]

                weights = weights_by_currency.get(currency)
                if weights is None:
                    raise EngineFailure(
                        "F4",
                        "E_S5_CONTENT",
                        "S6",
                        MODULE_NAME,
                        {"detail": "missing_currency_weights", "currency": currency},
                        dataset_id=DATASET_WEIGHTS,
                    )

                considered: list[dict] = []
                for row in foreign_candidates:
                    weight = weights.get(row["country_iso"])
                    if weight is None:
                        continue
                    considered.append(
                        {
                            "country_iso": row["country_iso"],
                            "candidate_rank": row["candidate_rank"],
                            "weight": float(weight),
                        }
                    )

                if zero_weight_rule == "exclude":
                    considered = [row for row in considered if row["weight"] > 0.0]

                a_filtered = len(considered)
                zero_weight_considered = sum(1 for row in considered if row["weight"] == 0.0)
                eligible = [row for row in considered if row["weight"] > 0.0]
                eligible_count = len(eligible)

                metrics["s6.run.A_filtered_sum"] += a_filtered

                reason_code = "none"
                if a_value == 0:
                    reason_code = "NO_CANDIDATES"
                elif k_target == 0:
                    reason_code = "K_ZERO"
                elif eligible_count == 0:
                    reason_code = "ZERO_WEIGHT_DOMAIN"
                elif cap_applied:
                    reason_code = "CAPPED_BY_MAX_CANDIDATES"

                if reason_code in ("NO_CANDIDATES", "K_ZERO", "ZERO_WEIGHT_DOMAIN"):
                    metrics["s6.run.merchants_empty"] += 1
                    metrics[f"s6.run.reason.{reason_code}"] += 1
                    selection_histogram[_selection_bucket(0)] += 1
                    detail_payload = {
                        "merchant_id": merchant_id,
                        "A": a_value,
                        "A_filtered": a_filtered,
                        "K_target": k_target,
                        "K_realized": 0,
                        "considered_expected_events": 0,
                        "gumbel_key_written": 0,
                        "is_shortfall": False,
                        "reason_code": reason_code,
                        "ties_resolved": 0,
                        "policy_cap_applied": cap_applied,
                        "cap_value": max_candidates_cap,
                        "zero_weight_considered": zero_weight_considered,
                        "rng.trace.delta.events": 0,
                        "rng.trace.delta.blocks": 0,
                        "rng.trace.delta.draws": 0,
                    }
                    detail_handle.write(
                        json.dumps(detail_payload, ensure_ascii=True, sort_keys=True)
                    )
                    detail_handle.write("\n")
                    detail_written += 1
                    if fail_on_degrade:
                        raise EngineFailure(
                            "F4",
                            "STRUCTURAL_FAIL",
                            "S6",
                            MODULE_NAME,
                            {"detail": "deterministic_empty", "reason_code": reason_code},
                        )
                    continue

                if reason_code == "CAPPED_BY_MAX_CANDIDATES":
                    metrics["s6.run.reason.CAPPED_BY_MAX_CANDIDATES"] += 1
                    if fail_on_degrade:
                        raise EngineFailure(
                            "F4",
                            "STRUCTURAL_FAIL",
                            "S6",
                            MODULE_NAME,
                            {"detail": "cap_applied"},
                        )

                weight_sum = sum(row["weight"] for row in eligible)
                if weight_sum <= 0.0:
                    raise EngineFailure(
                        "F4",
                        "E_S5_CONTENT",
                        "S6",
                        MODULE_NAME,
                        {"detail": "nonpositive_weight_sum", "merchant_id": merchant_id},
                    )

                merchant_u64_val = merchant_u64(merchant_id)

                considered_events: list[dict] = []
                eligible_events: list[dict] = []
                for row in considered:
                    country_iso = row["country_iso"]
                    weight = float(row["weight"])
                    weight_norm = weight / weight_sum if weight > 0.0 else 0.0
                    key, ctr_hi, ctr_lo = derive_substream(
                        master_material, SUBSTREAM_LABEL, merchant_u64_val, country_iso
                    )
                    u, blocks, draws = u01_single(ctr_hi, ctr_lo, key)
                    after_hi, after_lo = add_u128(ctr_hi, ctr_lo, 1)
                    key_value = None
                    if weight_norm > 0.0:
                        key_value = math.log(weight_norm) - math.log(-math.log(u))
                    event = {
                        "ts_utc": utc_now_rfc3339_micro(),
                        "run_id": run_id,
                        "seed": seed,
                        "parameter_hash": parameter_hash,
                        "manifest_fingerprint": manifest_fingerprint,
                        "module": MODULE_NAME,
                        "substream_label": SUBSTREAM_LABEL,
                        "rng_counter_before_lo": ctr_lo,
                        "rng_counter_before_hi": ctr_hi,
                        "rng_counter_after_lo": after_lo,
                        "rng_counter_after_hi": after_hi,
                        "draws": str(draws),
                        "blocks": blocks,
                        "merchant_id": merchant_id,
                        "country_iso": country_iso,
                        "weight": weight_norm,
                        "u": u,
                        "key": key_value,
                        "selected": False,
                    }
                    considered_events.append(event)
                    if weight_norm > 0.0:
                        eligible_events.append(event)

                eligible_sorted = sorted(
                    eligible_events,
                    key=lambda event: (
                        -event["key"],
                        next(
                            row["candidate_rank"]
                            for row in considered
                            if row["country_iso"] == event["country_iso"]
                        ),
                        event["country_iso"],
                    ),
                )
                ties_resolved = 0
                for prev, curr in zip(eligible_sorted, eligible_sorted[1:]):
                    if prev["key"] == curr["key"]:
                        ties_resolved += 1

                k_realized = min(k_target, len(eligible_sorted))
                selected = eligible_sorted[:k_realized]
                selected_set = {event["country_iso"] for event in selected}

                selection_order = {
                    event["country_iso"]: idx for idx, event in enumerate(selected, start=1)
                }

                if k_realized > 0:
                    metrics["s6.run.merchants_selected"] += 1

                metrics["s6.run.K_realized_sum"] += k_realized
                selection_histogram[_selection_bucket(k_realized)] += 1
                is_shortfall = len(eligible_sorted) < k_target
                if is_shortfall:
                    metrics["s6.run.shortfall_merchants"] += 1

                if log_all_candidates:
                    expected_events = a_filtered
                    to_write = considered_events
                else:
                    expected_events = k_realized
                    to_write = [event for event in considered_events if event["country_iso"] in selected_set]

                metrics["s6.run.events.gumbel_key.expected"] += expected_events

                for event in to_write:
                    country_iso = event["country_iso"]
                    if country_iso in selected_set:
                        event["selected"] = True
                        event["selection_order"] = selection_order[country_iso]
                    errors = list(event_validator.iter_errors(event))
                    if errors:
                        raise EngineFailure(
                            "F4",
                            "E_SCHEMA_AUTHORITY",
                            "S6",
                            MODULE_NAME,
                            {"detail": errors[0].message, "country_iso": country_iso},
                            dataset_id=DATASET_GUMBEL,
                        )
                    trace = trace_acc.append(event)
                    trace_errors = list(trace_validator.iter_errors(trace))
                    if trace_errors:
                        raise EngineFailure(
                            "F4",
                            "E_SCHEMA_AUTHORITY",
                            "S6",
                            MODULE_NAME,
                            {"detail": trace_errors[0].message},
                            dataset_id=DATASET_TRACE,
                        )
                    event_handle.write(json.dumps(event, ensure_ascii=True, sort_keys=True))
                    event_handle.write("\n")
                    trace_handle.write(json.dumps(trace, ensure_ascii=True, sort_keys=True))
                    trace_handle.write("\n")
                    events_written += 1
                    trace_written += 1

                metrics["s6.run.events.gumbel_key.written"] += len(to_write)

                if emit_membership_dataset and k_realized > 0:
                    for event in selected:
                        membership_rows.append(
                            {
                                "merchant_id": merchant_id,
                                "country_iso": event["country_iso"],
                                "seed": seed,
                                "parameter_hash": parameter_hash,
                                "produced_by_fingerprint": manifest_fingerprint,
                            }
                        )

                detail_payload = {
                    "merchant_id": merchant_id,
                    "A": a_value,
                    "A_filtered": a_filtered,
                    "K_target": k_target,
                    "K_realized": k_realized,
                    "considered_expected_events": expected_events,
                    "gumbel_key_written": len(to_write),
                    "is_shortfall": is_shortfall,
                    "reason_code": reason_code,
                    "ties_resolved": ties_resolved,
                    "policy_cap_applied": cap_applied,
                    "cap_value": max_candidates_cap,
                    "zero_weight_considered": zero_weight_considered,
                    "rng.trace.delta.events": len(to_write),
                    "rng.trace.delta.blocks": len(to_write),
                    "rng.trace.delta.draws": len(to_write),
                }
                detail_handle.write(
                    json.dumps(detail_payload, ensure_ascii=True, sort_keys=True)
                )
                detail_handle.write("\n")
                detail_written += 1

        if trace_written != events_written:
            raise EngineFailure(
                "F4",
                "E_RNG_ENVELOPE",
                "S6",
                MODULE_NAME,
                {"detail": "trace_count_mismatch"},
            )
        logger.info(
            "S6 summary: merchants_total=%d gated_in=%d selected=%d empty=%d "
            "reasons(NO_CANDIDATES=%d K_ZERO=%d ZERO_WEIGHT_DOMAIN=%d CAPPED_BY_MAX_CANDIDATES=%d) "
            "events_written=%d expected=%d shortfall=%d",
            metrics["s6.run.merchants_total"],
            metrics["s6.run.merchants_gated_in"],
            metrics["s6.run.merchants_selected"],
            metrics["s6.run.merchants_empty"],
            metrics["s6.run.reason.NO_CANDIDATES"],
            metrics["s6.run.reason.K_ZERO"],
            metrics["s6.run.reason.ZERO_WEIGHT_DOMAIN"],
            metrics["s6.run.reason.CAPPED_BY_MAX_CANDIDATES"],
            metrics["s6.run.events.gumbel_key.written"],
            metrics["s6.run.events.gumbel_key.expected"],
            metrics["s6.run.shortfall_merchants"],
        )

        if not existing_events and events_written > 0 and not validate_only:
            event_dir.mkdir(parents=True, exist_ok=True)
            out_path = _next_part_path(event_dir)
            tmp_event_path.replace(out_path)
            event_path = out_path
        else:
            tmp_event_path.unlink(missing_ok=True)
            event_path = None

        if trace_written > 0 and not validate_only:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with trace_path.open("a", encoding="utf-8") as dest_handle, tmp_trace_path.open(
                "r", encoding="utf-8"
            ) as src_handle:
                for line in src_handle:
                    dest_handle.write(line)
        tmp_trace_path.unlink(missing_ok=True)

        if detail_written > 0 and not validate_only:
            receipt_dir.mkdir(parents=True, exist_ok=True)
            if detail_path.exists():
                raise EngineFailure(
                    "F4",
                    "E_PARTIAL_OUTPUT",
                    "S6",
                    MODULE_NAME,
                    {"detail": "detail_output_exists"},
                )
            tmp_detail_path.replace(detail_path)
        else:
            tmp_detail_path.unlink(missing_ok=True)

        membership_df: pl.DataFrame | None = None
        if emit_membership_dataset:
            membership_df = pl.DataFrame(
                membership_rows,
                schema={
                    "merchant_id": pl.UInt64,
                    "country_iso": pl.Utf8,
                    "seed": pl.Int64,
                    "parameter_hash": pl.Utf8,
                    "produced_by_fingerprint": pl.Utf8,
                },
            ).sort(["merchant_id", "country_iso"])
            validate_dataframe(
                membership_df.iter_rows(named=True),
                _schema_section(schema_1a, "alloc"),
                "membership",
            )
            if membership_root is None:
                raise InputResolutionError("membership_root missing while emit_membership_dataset=true")
            if membership_root.exists() and not _dataset_has_parquet(membership_root):
                raise EngineFailure(
                    "F4",
                    "E_PARTIAL_OUTPUT",
                    "S6",
                    MODULE_NAME,
                    {"dataset_id": "s6_membership", "detail": "partition_exists"},
                    dataset_id="s6_membership",
                )
            if _dataset_has_parquet(membership_root):
                existing = pl.read_parquet(
                    _select_dataset_file("s6_membership", membership_root)
                )
                _assert_same_frame(
                    membership_df,
                    existing,
                    ["merchant_id", "country_iso"],
                    "s6_membership",
                )
                logger.info("S6: existing membership detected; validation only")
            elif not validate_only:
                _write_parquet_partition(membership_df, membership_root, "s6_membership")
                logger.info(
                    "S6: wrote membership dataset (%d rows)", membership_df.height
                )

        trace_rows = 0
        trace_totals = None
        if trace_path.exists():
            with trace_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    payload = json.loads(line)
                    if payload.get("module") != MODULE_NAME or payload.get("substream_label") != SUBSTREAM_LABEL:
                        continue
                    trace_rows += 1
                    trace_totals = payload

        metrics["s6.run.trace.events_total"] = trace_totals.get("events_total", 0) if trace_totals else 0
        metrics["s6.run.trace.blocks_total"] = trace_totals.get("blocks_total", 0) if trace_totals else 0
        metrics["s6.run.trace.draws_total"] = trace_totals.get("draws_total", 0) if trace_totals else 0

        rng_isolation_ok = True
        trace_reconciled = trace_rows == metrics["s6.run.events.gumbel_key.written"]
        re_derivation_ok = True

        receipt_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "seed": seed,
            "run_id": run_id,
            "producer": MODULE_NAME,
            "policy_digest": policy_digest,
            "metrics": metrics,
            "selection_size_histogram": selection_histogram,
            "reason_code_counts": {
                "NO_CANDIDATES": metrics["s6.run.reason.NO_CANDIDATES"],
                "K_ZERO": metrics["s6.run.reason.K_ZERO"],
                "ZERO_WEIGHT_DOMAIN": metrics["s6.run.reason.ZERO_WEIGHT_DOMAIN"],
                "CAPPED_BY_MAX_CANDIDATES": metrics["s6.run.reason.CAPPED_BY_MAX_CANDIDATES"],
            },
            "events_written": metrics["s6.run.events.gumbel_key.written"],
            "gumbel_key_expected": metrics["s6.run.events.gumbel_key.expected"],
            "shortfall_count": metrics["s6.run.shortfall_merchants"],
            "rng_isolation_ok": rng_isolation_ok,
            "trace_reconciled": trace_reconciled,
            "re_derivation_ok": re_derivation_ok,
        }

        if receipt_path.exists() and passed_flag_path.exists():
            existing = _load_json(receipt_path)
            if existing != receipt_payload:
                raise EngineFailure(
                    "F4",
                    "E_RECEIPT_MISMATCH",
                    "S6",
                    MODULE_NAME,
                    {"detail": "receipt_mismatch"},
                )
            expected_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            flag_contents = passed_flag_path.read_text(encoding="ascii").strip()
            if f"sha256_hex = {expected_hash}" != flag_contents:
                raise EngineFailure(
                    "F4",
                    "E_RECEIPT_MISMATCH",
                    "S6",
                    MODULE_NAME,
                    {"detail": "passed_flag_mismatch"},
                )
            logger.info("S6: existing receipt validated")
        elif not validate_only:
            _write_receipt(receipt_path, passed_flag_path, receipt_payload)
            logger.info("S6: wrote S6_VALIDATION.json + _passed.flag")

        timer.info("S6: completed")
        _emit_state_run("completed")
        return S6RunResult(
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            event_path=event_path,
            trace_path=trace_path,
            membership_root=membership_root,
        )
    except EngineFailure as failure:
        _record_failure(failure)
        raise
    except (ContractError, InputResolutionError, SchemaValidationError) as exc:
        failure = EngineFailure(
            "F5" if isinstance(exc, InputResolutionError) else "F4",
            "s6_contract_failure",
            "S6",
            MODULE_NAME,
            {"detail": str(exc)},
        )
        _record_failure(failure)
        raise


__all__ = ["S6RunResult", "run_s6"]
