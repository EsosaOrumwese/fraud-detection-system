"""S7 integer allocation runner for Segment 1A."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import time
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
from engine.core.time import utc_day_from_receipt, utc_now_rfc3339_micro
from engine.core.run_receipt import pick_latest_run_receipt
from engine.layers.l1.seg_1A.s0_foundations.validation_bundle import write_failure_record
from engine.layers.l1.seg_1A.s6_foreign_set.rng import (
    UINT64_MAX,
    derive_master_material,
    derive_substream,
    merchant_u64,
)
from engine.layers.l1.seg_1A.s2_nb_outlets.rng import (
    Substream,
    derive_substream_state,
    u01_pair,
    u01_single,
)


MODULE_NAME = "1A.integerisation"
SUBSTREAM_LABEL = "residual_rank"
MODULE_DIRICHLET = "1A.dirichlet_allocator"
SUBSTREAM_DIRICHLET = "dirichlet_gamma_vector"

DATASET_NB_FINAL = "rng_event_nb_final"
DATASET_ZTP_FINAL = "rng_event_ztp_final"
DATASET_CANDIDATE_SET = "s3_candidate_set"
DATASET_WEIGHTS = "ccy_country_weights_cache"
DATASET_MEMBERSHIP = "s6_membership"
DATASET_GUMBEL = "rng_event_gumbel_key"
DATASET_MERCHANT_CURRENCY = "merchant_currency"
DATASET_ISO = "iso3166_canonical_2024"
DATASET_TRACE = "rng_trace_log"
DATASET_RESIDUAL_RANK = "rng_event_residual_rank"
DATASET_DIRICHLET = "rng_event_dirichlet_gamma_vector"
DATASET_S5_RECEIPT = "s5_validation_receipt"
DATASET_S5_PASSED = "s5_passed_flag"
DATASET_S6_RECEIPT = "s6_validation_receipt"
POLICY_ASSET_ID = "s7_integerisation_policy.yaml"
COUNTS_HANDOFF_FILENAME = "s7_integerised_counts.jsonl"

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class S7RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    event_path: Path | None
    trace_path: Path


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


def _box_muller(stream: Substream) -> tuple[float, int, int]:
    u1, u2, blocks, draws = u01_pair(stream)
    r = math.sqrt(-2.0 * math.log(u1))
    theta = 2.0 * math.pi * u2
    z = r * math.cos(theta)
    return z, blocks, draws


def _gamma_mt1998(alpha: float, stream: Substream) -> tuple[float, int, int]:
    if not math.isfinite(alpha) or alpha <= 0.0:
        raise EngineFailure(
            "F4",
            "E_DIRICHLET_NONPOS",
            "S7",
            MODULE_DIRICHLET,
            {"detail": "alpha_nonpositive", "alpha": alpha},
            dataset_id=DATASET_DIRICHLET,
        )
    blocks_total = 0
    draws_total = 0
    if alpha < 1.0:
        while True:
            g, blocks, draws = _gamma_mt1998(alpha + 1.0, stream)
            blocks_total += blocks
            draws_total += draws
            u, blocks, draws = u01_single(stream)
            blocks_total += blocks
            draws_total += draws
            candidate = g * (u ** (1.0 / alpha))
            if math.isfinite(candidate) and candidate > 0.0:
                return candidate, blocks_total, draws_total
    d = alpha - (1.0 / 3.0)
    c = 1.0 / math.sqrt(9.0 * d)
    while True:
        z, blocks, draws = _box_muller(stream)
        blocks_total += blocks
        draws_total += draws
        v = (1.0 + c * z) ** 3
        if v <= 0.0:
            continue
        u, blocks, draws = u01_single(stream)
        blocks_total += blocks
        draws_total += draws
        if math.log(u) < (0.5 * z * z + d - d * v + d * math.log(v)):
            return d * v, blocks_total, draws_total


def _u128_diff(before_hi: int, before_lo: int, after_hi: int, after_lo: int) -> int:
    before = (int(before_hi) << 64) | int(before_lo)
    after = (int(after_hi) << 64) | int(after_lo)
    if after < before:
        raise EngineFailure(
            "F4",
            "E_RNG_ENVELOPE",
            "S7",
            MODULE_DIRICHLET,
            {"detail": "rng_counter_regression", "before": before, "after": after},
            dataset_id=DATASET_DIRICHLET,
        )
    return after - before


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
    return pick_latest_run_receipt(runs_root)


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


def _trace_rows_for_substream(path: Path, module: str, substream_label: str) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.get("module") == module and payload.get("substream_label") == substream_label:
                rows.append(payload)
    return rows


def _load_sealed_inputs(path: Path) -> list[dict]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise InputResolutionError("sealed_inputs_1A payload must be a list.")
    return payload


def _sealed_path(sealed_inputs: list[dict], asset_id: str) -> Path:
    for entry in sealed_inputs:
        if entry.get("asset_id") == asset_id:
            raw = entry.get("path")
            if not raw:
                raise InputResolutionError(f"sealed_inputs_1A missing path for {asset_id}")
            return Path(raw)
    raise InputResolutionError(f"sealed_inputs_1A missing asset_id {asset_id}")


def _require_pass_receipt(
    receipt_path: Path, passed_flag_path: Path, detail: str
) -> None:
    if not receipt_path.exists() or not passed_flag_path.exists():
        raise EngineFailure(
            "F4",
            "E_PASS_GATE_MISSING",
            "S7",
            MODULE_NAME,
            {"detail": detail},
        )
    expected_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    flag_contents = passed_flag_path.read_text(encoding="ascii").strip()
    if flag_contents != f"sha256_hex = {expected_hash}":
        raise EngineFailure(
            "F4",
            "E_PASS_GATE_MISSING",
            "S7",
            MODULE_NAME,
            {"detail": f"{detail}_hash_mismatch"},
        )


def _load_policy(policy_path: Path, schema_layer1: dict) -> dict:
    payload = _load_yaml(policy_path)
    schema = _schema_from_pack(schema_layer1, "policy/s7_integerisation")
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    if errors:
        raise EngineFailure(
            "F4",
            "E_SCHEMA_INVALID",
            "S7",
            MODULE_NAME,
            {"detail": errors[0].message},
            dataset_id="s7_integerisation_policy",
        )
    return payload

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
            if expected_rank == 0 or home_count != 1:
                raise EngineFailure(
                    "F4",
                    "E_UPSTREAM_MISSING",
                    "S7",
                    MODULE_NAME,
                    {"detail": "candidate_rows_incomplete", "merchant_id": current_mid},
                    dataset_id=DATASET_CANDIDATE_SET,
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
                "E_UPSTREAM_MISSING",
                "S7",
                MODULE_NAME,
                {"detail": "candidate_rank_not_contiguous", "merchant_id": mid},
                dataset_id=DATASET_CANDIDATE_SET,
            )
        expected_rank += 1
        country_iso = str(row["country_iso"])
        if country_iso not in iso_set:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S7",
                MODULE_NAME,
                {"detail": "unknown_country_iso", "country_iso": country_iso},
                dataset_id=DATASET_CANDIDATE_SET,
            )
        if row.get("parameter_hash") != parameter_hash:
            raise EngineFailure(
                "F4",
                "E_PATH_EMBED_MISMATCH",
                "S7",
                MODULE_NAME,
                {"detail": "candidate_set_parameter_hash"},
                dataset_id=DATASET_CANDIDATE_SET,
            )
        reason_codes = row.get("reason_codes")
        if not isinstance(reason_codes, list) or any(
            not isinstance(item, str) for item in reason_codes
        ):
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S7",
                MODULE_NAME,
                {"detail": "invalid_reason_codes", "merchant_id": mid},
                dataset_id=DATASET_CANDIDATE_SET,
            )
        filter_tags = row.get("filter_tags")
        if not isinstance(filter_tags, list) or any(
            not isinstance(item, str) for item in filter_tags
        ):
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S7",
                MODULE_NAME,
                {"detail": "invalid_filter_tags", "merchant_id": mid},
                dataset_id=DATASET_CANDIDATE_SET,
            )
        is_home = bool(row["is_home"])
        if is_home and rank != 0:
            raise EngineFailure(
                "F4",
                "E_UPSTREAM_MISSING",
                "S7",
                MODULE_NAME,
                {"detail": "home_rank_mismatch", "merchant_id": mid},
                dataset_id=DATASET_CANDIDATE_SET,
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
                "E_UPSTREAM_MISSING",
                "S7",
                MODULE_NAME,
                {"detail": "home_row_mismatch", "merchant_id": current_mid},
                dataset_id=DATASET_CANDIDATE_SET,
            )
        candidate_map[current_mid] = rows
    return candidate_map


def _candidate_index(candidate_map: dict[int, list[dict]]) -> dict[int, dict[str, dict]]:
    index: dict[int, dict[str, dict]] = {}
    for merchant_id, rows in candidate_map.items():
        index[merchant_id] = {row["country_iso"]: row for row in rows}
    return index


def _load_nb_final_events(
    nb_paths: Iterable[Path],
    schema_layer1: dict,
    seed: int,
    parameter_hash: str,
    run_id: str,
) -> dict[int, dict]:
    event_schema = _schema_from_pack(schema_layer1, "rng/events/nb_final")
    validator = Draft202012Validator(event_schema)
    events: dict[int, dict] = {}
    for path, line_no, payload in _iter_jsonl_files(nb_paths):
        errors = list(validator.iter_errors(payload))
        if errors:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S7",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no, "detail": errors[0].message},
                dataset_id=DATASET_NB_FINAL,
            )
        if (
            payload.get("seed") != seed
            or payload.get("parameter_hash") != parameter_hash
            or payload.get("run_id") != run_id
        ):
            raise EngineFailure(
                "F4",
                "E_PATH_EMBED_MISMATCH",
                "S7",
                MODULE_NAME,
                {"line": line_no},
                dataset_id=DATASET_NB_FINAL,
            )
        if payload.get("rng_counter_before_hi") != payload.get("rng_counter_after_hi") or payload.get(
            "rng_counter_before_lo"
        ) != payload.get("rng_counter_after_lo"):
            raise EngineFailure(
                "F4",
                "E_RNG_ENVELOPE",
                "S7",
                MODULE_NAME,
                {"line": line_no, "detail": "nb_final_counter_mismatch"},
                dataset_id=DATASET_NB_FINAL,
            )
        if payload.get("blocks") != 0 or payload.get("draws") != "0":
            raise EngineFailure(
                "F4",
                "E_RNG_ENVELOPE",
                "S7",
                MODULE_NAME,
                {"line": line_no, "detail": "nb_final_consuming"},
                dataset_id=DATASET_NB_FINAL,
            )
        merchant_id = int(payload["merchant_id"])
        if merchant_id in events:
            raise EngineFailure(
                "F4",
                "E_UPSTREAM_MISSING",
                "S7",
                MODULE_NAME,
                {"merchant_id": merchant_id, "detail": "duplicate_nb_final"},
                dataset_id=DATASET_NB_FINAL,
            )
        events[merchant_id] = payload
    return events


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
                "E_SCHEMA_INVALID",
                "S7",
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
                "E_PATH_EMBED_MISMATCH",
                "S7",
                MODULE_NAME,
                {"line": line_no},
                dataset_id=DATASET_ZTP_FINAL,
            )
        merchant_id = int(payload["merchant_id"])
        if merchant_id in events:
            raise EngineFailure(
                "F4",
                "E_UPSTREAM_MISSING",
                "S7",
                MODULE_NAME,
                {"merchant_id": merchant_id, "detail": "duplicate_ztp_final"},
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
                "E_SCHEMA_INVALID",
                "S7",
                MODULE_NAME,
                {"detail": "invalid_currency", "currency": currency},
                dataset_id=DATASET_WEIGHTS,
            )
        country_iso = str(row["country_iso"])
        if country_iso not in iso_set:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S7",
                MODULE_NAME,
                {"detail": "unknown_country_iso", "country_iso": country_iso},
                dataset_id=DATASET_WEIGHTS,
            )
        weight = float(row["weight"])
        if weight < 0.0 or weight > 1.0:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S7",
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
                "E_SCHEMA_INVALID",
                "S7",
                MODULE_NAME,
                {"detail": "weight_sum_mismatch", "currency": currency, "sum": total},
                dataset_id=DATASET_WEIGHTS,
            )
    return weights


def _load_membership(
    df: pl.DataFrame,
    seed: int,
    parameter_hash: str,
    candidate_index: dict[int, dict[str, dict]],
) -> dict[int, set[str]]:
    membership: dict[int, set[str]] = {}
    for row in df.select(["merchant_id", "country_iso", "seed", "parameter_hash"]).iter_rows(
        named=True
    ):
        if int(row["seed"]) != seed or str(row["parameter_hash"]) != parameter_hash:
            raise EngineFailure(
                "F4",
                "E_LINEAGE_PATH_MISMATCH",
                "S7",
                MODULE_NAME,
                {"detail": "membership_partition_mismatch"},
                dataset_id=DATASET_MEMBERSHIP,
            )
        merchant_id = int(row["merchant_id"])
        country_iso = str(row["country_iso"])
        if merchant_id not in candidate_index:
            raise EngineFailure(
                "F4",
                "E_S6_NOT_SUBSET_S3",
                "S7",
                MODULE_NAME,
                {"detail": "membership_unknown_merchant", "merchant_id": merchant_id},
                dataset_id=DATASET_MEMBERSHIP,
            )
        if country_iso not in candidate_index[merchant_id]:
            raise EngineFailure(
                "F4",
                "E_S6_NOT_SUBSET_S3",
                "S7",
                MODULE_NAME,
                {"detail": "membership_not_in_candidate_set", "merchant_id": merchant_id},
                dataset_id=DATASET_MEMBERSHIP,
            )
        if candidate_index[merchant_id][country_iso]["is_home"]:
            raise EngineFailure(
                "F4",
                "E_S6_NOT_SUBSET_S3",
                "S7",
                MODULE_NAME,
                {"detail": "membership_includes_home", "merchant_id": merchant_id},
                dataset_id=DATASET_MEMBERSHIP,
            )
        members = membership.setdefault(merchant_id, set())
        if country_iso in members:
            raise EngineFailure(
                "F4",
                "E_EVENT_COVERAGE",
                "S7",
                MODULE_NAME,
                {"detail": "duplicate_membership", "merchant_id": merchant_id},
                dataset_id=DATASET_MEMBERSHIP,
            )
        members.add(country_iso)
    return membership


def _load_selected_gumbel_events(
    paths: Iterable[Path],
    schema_layer1: dict,
    seed: int,
    parameter_hash: str,
    run_id: str,
    candidate_index: dict[int, dict[str, dict]],
) -> dict[int, set[str]]:
    event_schema = _schema_from_pack(schema_layer1, "rng/events/gumbel_key")
    validator = Draft202012Validator(event_schema)
    membership: dict[int, set[str]] = {}
    for path, line_no, payload in _iter_jsonl_files(paths):
        errors = list(validator.iter_errors(payload))
        if errors:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S7",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no, "detail": errors[0].message},
                dataset_id=DATASET_GUMBEL,
            )
        if (
            payload.get("seed") != seed
            or payload.get("parameter_hash") != parameter_hash
            or payload.get("run_id") != run_id
        ):
            raise EngineFailure(
                "F4",
                "E_LINEAGE_PATH_MISMATCH",
                "S7",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no},
                dataset_id=DATASET_GUMBEL,
            )
        if not payload.get("selected"):
            continue
        merchant_id = int(payload["merchant_id"])
        country_iso = str(payload["country_iso"])
        if merchant_id not in candidate_index:
            raise EngineFailure(
                "F4",
                "E_S6_NOT_SUBSET_S3",
                "S7",
                MODULE_NAME,
                {"detail": "gumbel_unknown_merchant", "merchant_id": merchant_id},
                dataset_id=DATASET_GUMBEL,
            )
        if country_iso not in candidate_index[merchant_id]:
            raise EngineFailure(
                "F4",
                "E_S6_NOT_SUBSET_S3",
                "S7",
                MODULE_NAME,
                {"detail": "gumbel_not_in_candidate_set", "merchant_id": merchant_id},
                dataset_id=DATASET_GUMBEL,
            )
        if candidate_index[merchant_id][country_iso]["is_home"]:
            raise EngineFailure(
                "F4",
                "E_S6_NOT_SUBSET_S3",
                "S7",
                MODULE_NAME,
                {"detail": "gumbel_includes_home", "merchant_id": merchant_id},
                dataset_id=DATASET_GUMBEL,
            )
        if payload.get("selection_order") is None:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S7",
                MODULE_NAME,
                {"detail": "missing_selection_order", "merchant_id": merchant_id},
                dataset_id=DATASET_GUMBEL,
            )
        members = membership.setdefault(merchant_id, set())
        if country_iso in members:
            raise EngineFailure(
                "F4",
                "E_EVENT_COVERAGE",
                "S7",
                MODULE_NAME,
                {"detail": "duplicate_selected", "merchant_id": merchant_id},
                dataset_id=DATASET_GUMBEL,
            )
        members.add(country_iso)
    return membership


def _load_existing_residual_events(
    paths: Iterable[Path],
    validator: Draft202012Validator,
    seed: int,
    parameter_hash: str,
    run_id: str,
) -> dict[int, dict[str, dict]]:
    events: dict[int, dict[str, dict]] = {}
    for path, line_no, payload in _iter_jsonl_files(paths):
        errors = list(validator.iter_errors(payload))
        if errors:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S7",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no, "detail": errors[0].message},
                dataset_id=DATASET_RESIDUAL_RANK,
            )
        if (
            payload.get("seed") != seed
            or payload.get("parameter_hash") != parameter_hash
            or payload.get("run_id") != run_id
        ):
            raise EngineFailure(
                "F4",
                "E_LINEAGE_PATH_MISMATCH",
                "S7",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no},
                dataset_id=DATASET_RESIDUAL_RANK,
            )
        merchant_id = int(payload["merchant_id"])
        country_iso = str(payload["country_iso"])
        merchant_events = events.setdefault(merchant_id, {})
        if country_iso in merchant_events:
            raise EngineFailure(
                "F4",
                "E_EVENT_COVERAGE",
                "S7",
                MODULE_NAME,
                {"detail": "duplicate_residual_rank", "merchant_id": merchant_id},
                dataset_id=DATASET_RESIDUAL_RANK,
            )
        merchant_events[country_iso] = payload
    return events


def _load_existing_dirichlet_events(
    paths: Iterable[Path],
    validator: Draft202012Validator,
    seed: int,
    parameter_hash: str,
    run_id: str,
) -> dict[int, dict]:
    events: dict[int, dict] = {}
    for path, line_no, payload in _iter_jsonl_files(paths):
        errors = list(validator.iter_errors(payload))
        if errors:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S7",
                MODULE_DIRICHLET,
                {"path": path.as_posix(), "line": line_no, "detail": errors[0].message},
                dataset_id=DATASET_DIRICHLET,
            )
        if (
            payload.get("seed") != seed
            or payload.get("parameter_hash") != parameter_hash
            or payload.get("run_id") != run_id
        ):
            raise EngineFailure(
                "F4",
                "E_PATH_EMBED_MISMATCH",
                "S7",
                MODULE_DIRICHLET,
                {"path": path.as_posix(), "line": line_no},
                dataset_id=DATASET_DIRICHLET,
            )
        if payload.get("module") != MODULE_DIRICHLET or payload.get("substream_label") != SUBSTREAM_DIRICHLET:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S7",
                MODULE_DIRICHLET,
                {"path": path.as_posix(), "line": line_no, "detail": "module_substream_mismatch"},
                dataset_id=DATASET_DIRICHLET,
            )
        merchant_id = int(payload["merchant_id"])
        if merchant_id in events:
            raise EngineFailure(
                "F4",
                "E_EVENT_COVERAGE",
                "S7",
                MODULE_DIRICHLET,
                {"detail": "duplicate_dirichlet_event", "merchant_id": merchant_id},
                dataset_id=DATASET_DIRICHLET,
            )
        events[merchant_id] = payload
    return events


def _quantize_residual(value: float, dp: int) -> float:
    scale = 10 ** dp
    return round(value * scale) / scale


def run_s7(
    config: EngineConfig,
    run_id: Optional[str] = None,
    validate_only: bool = False,
) -> S7RunResult:
    logger = get_logger("engine.layers.l1.seg_1A.s7_integerisation.l2.runner")
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
    timer.info(f"S7: loaded run receipt {receipt_path}")
    if validate_only:
        logger.info("S7: validate-only enabled; outputs will not be written")

    utc_day = utc_day_from_receipt(receipt)
    segment_state_runs_path = _segment_state_runs_path(run_paths, dictionary, utc_day)

    def _emit_state_run(status: str, detail: Optional[str] = None) -> None:
        payload = {
            "layer": "layer1",
            "segment": "1A",
            "state": "S7",
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
            "state": "S7",
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
        dp_resid = int(policy.get("dp_resid", 0))
        dirichlet_enabled = bool(
            (policy.get("dirichlet_lane") or {}).get("enabled", False)
        )
        bounds_enabled = bool((policy.get("bounds_lane") or {}).get("enabled", False))
        alpha0: float | None = None
        lower_multiplier: float | None = None
        upper_multiplier: float | None = None
        if dp_resid != 8:
            raise EngineFailure(
                "F4",
                "E_RESIDUAL_QUANTISATION",
                "S7",
                MODULE_NAME,
                {"detail": "dp_resid_mismatch", "dp_resid": dp_resid},
            )
        if dirichlet_enabled:
            alpha0 = float((policy.get("dirichlet_lane") or {}).get("alpha0", float("nan")))
            if not math.isfinite(alpha0) or alpha0 <= 0.0:
                raise EngineFailure(
                    "F4",
                    "E_DIRICHLET_NONPOS",
                    "S7",
                    MODULE_DIRICHLET,
                    {"detail": "alpha0_invalid", "alpha0": alpha0},
                    dataset_id=DATASET_DIRICHLET,
                )
        if bounds_enabled:
            lower_multiplier = float(
                (policy.get("bounds_lane") or {}).get("lower_multiplier", float("nan"))
            )
            upper_multiplier = float(
                (policy.get("bounds_lane") or {}).get("upper_multiplier", float("nan"))
            )
            if (
                not math.isfinite(lower_multiplier)
                or not math.isfinite(upper_multiplier)
                or lower_multiplier < 0.0
                or upper_multiplier <= 0.0
                or upper_multiplier < lower_multiplier
            ):
                raise EngineFailure(
                    "F4",
                    "E_BOUNDS_INFEASIBLE",
                    "S7",
                    MODULE_NAME,
                    {
                        "detail": "bounds_multiplier_invalid",
                        "lower_multiplier": lower_multiplier,
                        "upper_multiplier": upper_multiplier,
                    },
                )
        logger.info(
            "S7: loaded policy %s (dp_resid=%d, dirichlet_lane=%s, bounds_lane=%s)",
            policy_path.as_posix(),
            dp_resid,
            dirichlet_enabled,
            bounds_enabled,
        )
        if dirichlet_enabled:
            logger.info("S7: dirichlet_lane enabled (alpha0=%.6f)", alpha0)
        if bounds_enabled:
            logger.info(
                "S7: bounds_lane enabled (lower_multiplier=%.6f, upper_multiplier=%.6f)",
                lower_multiplier,
                upper_multiplier,
            )

        s5_receipt_entry = find_dataset_entry(dictionary, DATASET_S5_RECEIPT).entry
        s5_passed_entry = find_dataset_entry(dictionary, DATASET_S5_PASSED).entry
        s5_receipt_path = _resolve_run_path(
            run_paths, s5_receipt_entry["path"], {"parameter_hash": parameter_hash}
        )
        s5_passed_path = _resolve_run_path(
            run_paths, s5_passed_entry["path"], {"parameter_hash": parameter_hash}
        )
        _require_pass_receipt(s5_receipt_path, s5_passed_path, "s5_pass")
        logger.info("S7: verified S5 PASS before reading weights")

        s6_receipt_entry = find_dataset_entry(dictionary, DATASET_S6_RECEIPT).entry
        s6_receipt_root = _resolve_run_path(
            run_paths,
            s6_receipt_entry["path"],
            {"seed": str(seed), "parameter_hash": parameter_hash},
        )
        s6_receipt_path = s6_receipt_root / "S6_VALIDATION.json"
        s6_passed_path = s6_receipt_root / "_passed.flag"
        _require_pass_receipt(s6_receipt_path, s6_passed_path, "s6_pass")
        logger.info("S7: verified S6 PASS before reading membership or gumbel_key")

        iso_path = _sealed_path(sealed_inputs, DATASET_ISO)
        iso_df = pl.read_parquet(_select_dataset_file(DATASET_ISO, iso_path))
        validate_dataframe(iso_df.iter_rows(named=True), schema_ingress, DATASET_ISO)
        iso_set = {str(row[0]) for row in iso_df.select("country_iso").iter_rows()}

        candidate_entry = find_dataset_entry(dictionary, DATASET_CANDIDATE_SET).entry
        candidate_root = _resolve_run_path(
            run_paths, candidate_entry["path"], {"parameter_hash": parameter_hash}
        )
        candidate_df = pl.read_parquet(
            _select_dataset_file(DATASET_CANDIDATE_SET, candidate_root)
        )
        candidate_map = _build_candidate_map(candidate_df, parameter_hash, iso_set)
        candidate_index = _candidate_index(candidate_map)
        timer.info(f"S7: loaded candidate set merchants={len(candidate_map)}")
        if not candidate_map:
            raise InputResolutionError("S3 candidate set is empty.")

        nb_entry = find_dataset_entry(dictionary, DATASET_NB_FINAL).entry
        nb_paths = _resolve_run_glob(run_paths, nb_entry["path"], tokens)
        nb_map = _load_nb_final_events(nb_paths, schema_layer1, seed, parameter_hash, run_id)
        if not nb_map:
            raise InputResolutionError("Missing rng_event_nb_final inputs.")
        extra_nb = sorted(mid for mid in nb_map if mid not in candidate_map)
        if extra_nb:
            raise EngineFailure(
                "F4",
                "E_UPSTREAM_MISSING",
                "S7",
                MODULE_NAME,
                {"detail": "extra_nb_final", "merchant_ids": extra_nb[:10]},
                dataset_id=DATASET_NB_FINAL,
            )
        timer.info(f"S7: loaded nb_final events rows={len(nb_map)}")

        ztp_entry = find_dataset_entry(dictionary, DATASET_ZTP_FINAL).entry
        ztp_paths = _resolve_run_glob(run_paths, ztp_entry["path"], tokens)
        ztp_map = _load_ztp_final_events(
            ztp_paths, schema_layer1, seed, parameter_hash, run_id
        )
        if not ztp_map:
            raise InputResolutionError("Missing rng_event_ztp_final inputs.")
        extra_ztp = sorted(mid for mid in ztp_map if mid not in candidate_map)
        if extra_ztp:
            raise EngineFailure(
                "F4",
                "E_UPSTREAM_MISSING",
                "S7",
                MODULE_NAME,
                {"detail": "extra_ztp_final", "merchant_ids": extra_ztp[:10]},
                dataset_id=DATASET_ZTP_FINAL,
            )
        scope_merchants = sorted(mid for mid in candidate_map if mid in ztp_map)
        missing_ztp = sorted(mid for mid in candidate_map if mid not in ztp_map)
        if missing_ztp:
            logger.info(
                "S7: ztp_final absent for %d candidate-set merchants (S4 gate: single-site or ineligible); "
                "treating as out-of-scope",
                len(missing_ztp),
            )
        missing_nb = sorted(mid for mid in scope_merchants if mid not in nb_map)
        if missing_nb:
            raise EngineFailure(
                "F4",
                "E_UPSTREAM_MISSING",
                "S7",
                MODULE_NAME,
                {"detail": "missing_nb_final", "merchant_ids": missing_nb[:10]},
                dataset_id=DATASET_NB_FINAL,
            )
        timer.info(
            f"S7: loaded ztp_final events rows={len(ztp_map)} scope_merchants={len(scope_merchants)}"
        )

        weights_entry = find_dataset_entry(dictionary, DATASET_WEIGHTS).entry
        weights_root = _resolve_run_path(
            run_paths, weights_entry["path"], {"parameter_hash": parameter_hash}
        )
        weights_df = pl.read_parquet(
            _select_dataset_file(DATASET_WEIGHTS, weights_root)
        )
        prep_schema = _schema_section(schema_1a, "prep")
        validate_dataframe(weights_df.iter_rows(named=True), prep_schema, DATASET_WEIGHTS)
        weights = _load_weights(weights_df, iso_set)
        if not weights:
            raise InputResolutionError("No currency weights resolved.")
        logger.info("S7: loaded weights currencies=%d", len(weights))

        merchant_currency_entry = find_dataset_entry(dictionary, DATASET_MERCHANT_CURRENCY).entry
        merchant_currency_root = _resolve_run_path(
            run_paths, merchant_currency_entry["path"], {"parameter_hash": parameter_hash}
        )
        currency_map: dict[int, str] | None = None
        fallback_currency: str | None = None
        if _dataset_has_parquet(merchant_currency_root):
            currency_df = pl.read_parquet(
                _select_dataset_file(DATASET_MERCHANT_CURRENCY, merchant_currency_root)
            )
            validate_dataframe(
                currency_df.iter_rows(named=True), prep_schema, DATASET_MERCHANT_CURRENCY
            )
            currency_map = {}
            for row in currency_df.select(
                ["merchant_id", "kappa"]
            ).iter_rows(named=True):
                merchant_id = int(row["merchant_id"])
                currency = str(row["kappa"])
                if not _CURRENCY_RE.fullmatch(currency):
                    raise EngineFailure(
                        "F4",
                        "E_SCHEMA_INVALID",
                        "S7",
                        MODULE_NAME,
                        {"detail": "invalid_currency", "currency": currency},
                        dataset_id=DATASET_MERCHANT_CURRENCY,
                    )
                currency_map[merchant_id] = currency
            missing_currency = [mid for mid in candidate_map if mid not in currency_map]
            if missing_currency:
                raise EngineFailure(
                    "F4",
                    "E_UPSTREAM_MISSING",
                    "S7",
                    MODULE_NAME,
                    {"detail": "missing_merchant_currency", "merchant_ids": missing_currency[:10]},
                    dataset_id=DATASET_MERCHANT_CURRENCY,
                )
            logger.info("S7: loaded merchant_currency rows=%d", len(currency_map))
        else:
            currency_map = None
            if len(weights) == 1:
                fallback_currency = next(iter(weights))
                logger.info(
                    "S7: merchant_currency missing; using single currency fallback %s",
                    fallback_currency,
                )
            else:
                raise EngineFailure(
                    "F4",
                    "E_UPSTREAM_MISSING",
                    "S7",
                    MODULE_NAME,
                    {"detail": "merchant_currency_missing_multi_currency"},
                    dataset_id=DATASET_MERCHANT_CURRENCY,
                )

        membership_entry = find_dataset_entry(dictionary, DATASET_MEMBERSHIP).entry
        membership_root = _resolve_run_path(
            run_paths,
            membership_entry["path"],
            {"seed": str(seed), "parameter_hash": parameter_hash},
        )
        membership_map: dict[int, set[str]]
        membership_source: str
        if _dataset_has_parquet(membership_root):
            membership_df = pl.read_parquet(
                _select_dataset_file(DATASET_MEMBERSHIP, membership_root)
            )
            alloc_schema = _schema_section(schema_1a, "alloc")
            validate_dataframe(
                membership_df.iter_rows(named=True), alloc_schema, "membership"
            )
            membership_map = _load_membership(
                membership_df, seed, parameter_hash, candidate_index
            )
            membership_source = "s6_membership"
            member_rows = sum(len(rows) for rows in membership_map.values())
            logger.info("S7: loaded s6_membership rows=%d", member_rows)
        else:
            gumbel_entry = find_dataset_entry(dictionary, DATASET_GUMBEL).entry
            gumbel_paths = _resolve_run_glob(run_paths, gumbel_entry["path"], tokens)
            membership_map = _load_selected_gumbel_events(
                gumbel_paths,
                schema_layer1,
                seed,
                parameter_hash,
                run_id,
                candidate_index,
            )
            membership_source = "rng_event_gumbel_key"
            member_rows = sum(len(rows) for rows in membership_map.values())
            logger.info(
                "S7: s6_membership missing; reconstructed membership from gumbel_key rows=%d",
                member_rows,
            )

        event_entry = find_dataset_entry(dictionary, DATASET_RESIDUAL_RANK).entry
        event_paths = _resolve_run_glob(run_paths, event_entry["path"], tokens)
        event_path = _resolve_event_path(run_paths, event_entry["path"], tokens)
        event_dir = _resolve_event_dir(run_paths, event_entry["path"], tokens)
        dirichlet_entry = find_dataset_entry(dictionary, DATASET_DIRICHLET).entry
        dirichlet_paths = _resolve_run_glob(run_paths, dirichlet_entry["path"], tokens)
        dirichlet_path = _resolve_event_path(run_paths, dirichlet_entry["path"], tokens)
        dirichlet_dir = _resolve_event_dir(run_paths, dirichlet_entry["path"], tokens)
        trace_entry = find_dataset_entry(dictionary, DATASET_TRACE).entry
        trace_path = _resolve_run_path(run_paths, trace_entry["path"], tokens)
        existing_events = _event_has_rows(event_paths)
        existing_trace = _trace_has_substream(trace_path, MODULE_NAME, SUBSTREAM_LABEL)
        existing_dirichlet_events = _event_has_rows(dirichlet_paths)
        existing_dirichlet_trace = _trace_has_substream(
            trace_path, MODULE_DIRICHLET, SUBSTREAM_DIRICHLET
        )

        if dirichlet_enabled:
            if (
                existing_events
                and existing_trace
                and existing_dirichlet_events
                and existing_dirichlet_trace
            ):
                logger.info("S7: existing outputs detected; validating only")
                validate_only = True
            elif (
                existing_events
                or existing_trace
                or existing_dirichlet_events
                or existing_dirichlet_trace
            ):
                raise InputResolutionError(
                    "Partial S7 outputs detected; refuse to append. "
                    "Remove existing S7 outputs or resume a clean run_id."
                )
        else:
            if existing_dirichlet_events or existing_dirichlet_trace:
                raise InputResolutionError(
                    "Dirichlet outputs exist but dirichlet_lane is disabled; "
                    "remove outputs or resume a clean run_id."
                )
            if existing_events and existing_trace:
                logger.info("S7: existing residual_rank outputs detected; validating only")
                validate_only = True
            elif existing_events or existing_trace:
                raise InputResolutionError(
                    "Partial S7 outputs detected; refuse to append. "
                    "Remove existing S7 outputs or resume a clean run_id."
                )

        event_schema = _schema_from_pack(schema_layer1, "rng/events/residual_rank")
        event_validator = Draft202012Validator(event_schema)
        dirichlet_schema = _schema_from_pack(schema_layer1, "rng/events/dirichlet_gamma_vector")
        dirichlet_validator = Draft202012Validator(dirichlet_schema)
        trace_schema = _schema_from_pack(schema_layer1, "rng/core/rng_trace_log/record")
        trace_validator = Draft202012Validator(trace_schema)

        existing_event_map: dict[int, dict[str, dict]] | None = None
        if existing_events:
            existing_event_map = _load_existing_residual_events(
                event_paths, event_validator, seed, parameter_hash, run_id
            )

        existing_dirichlet_map: dict[int, dict] | None = None
        if existing_dirichlet_events:
            existing_dirichlet_map = _load_existing_dirichlet_events(
                dirichlet_paths, dirichlet_validator, seed, parameter_hash, run_id
            )

        total_merchants = len(scope_merchants)
        progress_every = max(1, min(10_000, total_merchants // 10))
        start_time = time.monotonic()
        logger.info(
            "S7: starting deterministic integerisation over candidate-set merchants=%d "
            "(membership_source=%s)",
            total_merchants,
            membership_source,
        )

        metrics = {
            "s7.merchants_in_scope": 0,
            "s7.single_country": 0,
            "s7.events.residual_rank.rows": 0,
            "s7.trace.rows": 0,
            "s7.events.dirichlet_gamma_vector.rows": 0,
            "s7.bounds.enabled": 0,
            "s7.failures.structural": 0,
            "s7.failures.integerisation": 0,
            "s7.failures.rng_accounting": 0,
            "s7.failures.bounds": 0,
        }

        trace_acc = _TraceAccumulator(MODULE_NAME, SUBSTREAM_LABEL)
        dirichlet_trace_acc = _TraceAccumulator(MODULE_DIRICHLET, SUBSTREAM_DIRICHLET)
        tmp_dir = run_paths.tmp_root / "s7_integerisation"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_event_path = tmp_dir / "rng_event_residual_rank.jsonl"
        tmp_dirichlet_path = tmp_dir / "rng_event_dirichlet_gamma_vector.jsonl"
        tmp_trace_path = tmp_dir / "rng_trace_log_s7.jsonl"
        tmp_counts_path = tmp_dir / f"{COUNTS_HANDOFF_FILENAME}.tmp"
        counts_path = tmp_dir / COUNTS_HANDOFF_FILENAME

        events_written = 0
        trace_written = 0
        dirichlet_events_written = 0
        counts_written = 0
        expected_residual_events = 0
        expected_dirichlet_events = 0
        expected_dirichlet_blocks = 0
        expected_dirichlet_draws = 0

        master_material = derive_master_material(
            bytes.fromhex(manifest_fingerprint), seed
        )

        def _expected_event_payload(
            merchant_id: int,
            country_iso: str,
            residual: float,
            residual_rank: int,
        ) -> dict:
            _key_value, ctr_hi, ctr_lo = derive_substream(
                master_material, SUBSTREAM_LABEL, merchant_u64(merchant_id), country_iso
            )
            return {
                "seed": seed,
                "run_id": run_id,
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": MODULE_NAME,
                "substream_label": SUBSTREAM_LABEL,
                "rng_counter_before_lo": ctr_lo,
                "rng_counter_before_hi": ctr_hi,
                "rng_counter_after_lo": ctr_lo,
                "rng_counter_after_hi": ctr_hi,
                "draws": "0",
                "blocks": 0,
                "merchant_id": merchant_id,
                "country_iso": country_iso,
                "residual": residual,
                "residual_rank": residual_rank,
            }

        def _expected_dirichlet_payload(
            merchant_id: int,
            country_isos: list[str],
            home_country_iso: str,
            shares: list[float],
            n_domestic: int,
        ) -> dict:
            if alpha0 is None:
                raise EngineFailure(
                    "F4",
                    "E_DIRICHLET_SHAPE",
                    "S7",
                    MODULE_DIRICHLET,
                    {"detail": "alpha0_missing"},
                    dataset_id=DATASET_DIRICHLET,
                )
            stream = derive_substream_state(
                master_material, SUBSTREAM_DIRICHLET, merchant_id
            )
            before_hi, before_lo = stream.counter()
            alpha_vec: list[float] = []
            gamma_raw: list[float] = []
            blocks_total = 0
            draws_total = 0
            for share in shares:
                alpha_i = alpha0 * share
                if not math.isfinite(alpha_i) or alpha_i <= 0.0:
                    raise EngineFailure(
                        "F4",
                        "E_DIRICHLET_NONPOS",
                        "S7",
                        MODULE_DIRICHLET,
                        {"detail": "alpha_nonpositive", "alpha": alpha_i},
                        dataset_id=DATASET_DIRICHLET,
                    )
                alpha_vec.append(alpha_i)
                gamma_value, blocks, draws = _gamma_mt1998(alpha_i, stream)
                gamma_raw.append(gamma_value)
                blocks_total += blocks
                draws_total += draws
            after_hi, after_lo = stream.counter()
            blocks_delta = _u128_diff(before_hi, before_lo, after_hi, after_lo)
            if blocks_delta != blocks_total:
                raise EngineFailure(
                    "F4",
                    "E_RNG_ENVELOPE",
                    "S7",
                    MODULE_DIRICHLET,
                    {"detail": "dirichlet_counter_mismatch", "expected": blocks_total, "actual": blocks_delta},
                    dataset_id=DATASET_DIRICHLET,
                )
            sum_gamma = sum(gamma_raw)
            if not math.isfinite(sum_gamma) or sum_gamma <= 0.0:
                raise EngineFailure(
                    "F4",
                    "E_DIRICHLET_SUM",
                    "S7",
                    MODULE_DIRICHLET,
                    {"detail": "gamma_sum_nonpositive", "sum": sum_gamma},
                    dataset_id=DATASET_DIRICHLET,
                )
            weights_vec = [value / sum_gamma for value in gamma_raw]
            sum_weights = sum(weights_vec)
            if not math.isfinite(sum_weights) or abs(sum_weights - 1.0) > 1e-6:
                raise EngineFailure(
                    "F4",
                    "E_DIRICHLET_SUM",
                    "S7",
                    MODULE_DIRICHLET,
                    {"detail": "weights_sum_mismatch", "sum": sum_weights},
                    dataset_id=DATASET_DIRICHLET,
                )
            return {
                "seed": seed,
                "run_id": run_id,
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": MODULE_DIRICHLET,
                "substream_label": SUBSTREAM_DIRICHLET,
                "rng_counter_before_lo": before_lo,
                "rng_counter_before_hi": before_hi,
                "rng_counter_after_lo": after_lo,
                "rng_counter_after_hi": after_hi,
                "draws": str(draws_total),
                "blocks": blocks_total,
                "merchant_id": merchant_id,
                "home_country_iso": home_country_iso,
                "country_isos": country_isos,
                "alpha": alpha_vec,
                "gamma_raw": gamma_raw,
                "weights": weights_vec,
                "n_domestic": n_domestic,
            }

        if existing_event_map is None:
            event_handle = tmp_event_path.open("w", encoding="utf-8")
            trace_handle = tmp_trace_path.open("w", encoding="utf-8")
            dirichlet_handle = (
                tmp_dirichlet_path.open("w", encoding="utf-8") if dirichlet_enabled else None
            )
            counts_handle = (
                tmp_counts_path.open("w", encoding="utf-8") if not validate_only else None
            )
        else:
            event_handle = None
            trace_handle = None
            dirichlet_handle = None
            counts_handle = None
        try:
            for idx, merchant_id in enumerate(scope_merchants, start=1):
                if idx % progress_every == 0 or idx == total_merchants:
                    elapsed = max(time.monotonic() - start_time, 1e-9)
                    rate = idx / elapsed
                    eta = (total_merchants - idx) / rate if rate > 0 else 0.0
                    logger.info(
                        "S7 progress merchants_processed=%d/%d (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
                        idx,
                        total_merchants,
                        elapsed,
                        rate,
                        eta,
                    )

                metrics["s7.merchants_in_scope"] += 1
                rows = candidate_map[merchant_id]
                membership_set = membership_map.get(merchant_id, set())
                k_target = int(ztp_map[merchant_id]["K_target"])
                if k_target == 0 and membership_set:
                    raise EngineFailure(
                        "F4",
                        "E_UPSTREAM_GATE",
                        "S7",
                        MODULE_NAME,
                        {"detail": "k_target_zero_but_membership", "merchant_id": merchant_id},
                    )
                if len(membership_set) > k_target:
                    raise EngineFailure(
                        "F4",
                        "E_UPSTREAM_GATE",
                        "S7",
                        MODULE_NAME,
                        {"detail": "membership_exceeds_k_target", "merchant_id": merchant_id},
                    )
                domain_rows = []
                for row in rows:
                    if row["is_home"] or row["country_iso"] in membership_set:
                        domain_rows.append(row)
                if not domain_rows:
                    raise EngineFailure(
                        "F4",
                        "E_UPSTREAM_MISSING",
                        "S7",
                        MODULE_NAME,
                        {"detail": "empty_domain", "merchant_id": merchant_id},
                    )
                if len(domain_rows) == 1:
                    metrics["s7.single_country"] += 1
                if bounds_enabled:
                    metrics["s7.bounds.enabled"] += 1

                home_row = next((row for row in domain_rows if row["is_home"]), None)
                if home_row is None:
                    raise EngineFailure(
                        "F4",
                        "E_UPSTREAM_MISSING",
                        "S7",
                        MODULE_NAME,
                        {"detail": "missing_home_row", "merchant_id": merchant_id},
                        dataset_id=DATASET_CANDIDATE_SET,
                    )
                home_iso = home_row["country_iso"]
                domain_isos = [row["country_iso"] for row in domain_rows]

                currency = (
                    currency_map[merchant_id]
                    if currency_map is not None
                    else fallback_currency
                )
                if currency is None or currency not in weights:
                    raise EngineFailure(
                        "F4",
                        "E_UPSTREAM_MISSING",
                        "S7",
                        MODULE_NAME,
                        {"detail": "missing_currency_weights", "merchant_id": merchant_id},
                        dataset_id=DATASET_WEIGHTS,
                    )
                weight_map = weights[currency]

                total_weight = 0.0
                domain_weights: list[float] = []
                for row in domain_rows:
                    weight = float(weight_map.get(row["country_iso"], 0.0))
                    domain_weights.append(weight)
                    total_weight += weight
                if total_weight <= 0.0:
                    raise EngineFailure(
                        "F4",
                        "E_ZERO_SUPPORT",
                        "S7",
                        MODULE_NAME,
                        {"detail": "zero_support", "merchant_id": merchant_id},
                    )

                n_outlets = int(nb_map[merchant_id]["n_outlets"])
                items: list[dict] = []
                total_floor = 0
                sum_lower = 0
                sum_upper = 0
                for stable_index, (row, weight) in enumerate(
                    zip(domain_rows, domain_weights), start=0
                ):
                    s_i = weight / total_weight
                    a_i = n_outlets * s_i
                    floor_a = int(math.floor(a_i))
                    residual = _quantize_residual(a_i - floor_a, dp_resid)
                    if residual < 0.0 or residual >= 1.0:
                        raise EngineFailure(
                            "F4",
                            "E_RESIDUAL_QUANTISATION",
                            "S7",
                            MODULE_NAME,
                            {"detail": "residual_out_of_range", "merchant_id": merchant_id},
                        )
                    if bounds_enabled:
                        if lower_multiplier is None or upper_multiplier is None:
                            raise EngineFailure(
                                "F4",
                                "E_BOUNDS_INFEASIBLE",
                                "S7",
                                MODULE_NAME,
                                {"detail": "bounds_multiplier_missing"},
                            )
                        lower = int(math.floor(n_outlets * s_i * lower_multiplier))
                        upper = int(math.ceil(n_outlets * s_i * upper_multiplier))
                        if lower < 0:
                            lower = 0
                        if upper < 0:
                            upper = 0
                        if lower > n_outlets:
                            lower = n_outlets
                        if upper > n_outlets:
                            upper = n_outlets
                        if upper < lower:
                            raise EngineFailure(
                                "F4",
                                "E_BOUNDS_INFEASIBLE",
                                "S7",
                                MODULE_NAME,
                                {
                                    "detail": "bounds_inverted",
                                    "merchant_id": merchant_id,
                                    "country_iso": row["country_iso"],
                                },
                            )
                    else:
                        lower = 0
                        upper = n_outlets
                    sum_lower += lower
                    sum_upper += upper
                    b_i = max(floor_a, lower)
                    total_floor += b_i
                    items.append(
                        {
                            "country_iso": row["country_iso"],
                            "candidate_rank": row["candidate_rank"],
                            "stable_index": stable_index,
                            "share": s_i,
                            "a": a_i,
                            "floor": floor_a,
                            "b": b_i,
                            "lower": lower,
                            "upper": upper,
                            "residual": residual,
                        }
                    )

                shares = [item["share"] for item in items]

                if bounds_enabled and (sum_lower > n_outlets or sum_upper < n_outlets):
                    raise EngineFailure(
                        "F4",
                        "E_BOUNDS_INFEASIBLE",
                        "S7",
                        MODULE_NAME,
                        {"detail": "bounds_infeasible", "merchant_id": merchant_id},
                    )

                d = n_outlets - total_floor
                if d < 0:
                    raise EngineFailure(
                        "F4",
                        "E_BOUNDS_INFEASIBLE" if bounds_enabled else "INTEGER_SUM_MISMATCH",
                        "S7",
                        MODULE_NAME,
                        {"detail": "remainder_negative", "merchant_id": merchant_id},
                    )
                if not bounds_enabled and d > len(items):
                    raise EngineFailure(
                        "F4",
                        "INTEGER_SUM_MISMATCH",
                        "S7",
                        MODULE_NAME,
                        {"detail": "remainder_out_of_range", "merchant_id": merchant_id},
                    )

                ordered = sorted(
                    items,
                    key=lambda item: (
                        -item["residual"],
                        item["country_iso"],
                        item["candidate_rank"],
                        item["stable_index"],
                    ),
                )
                for rank, item in enumerate(ordered, start=1):
                    item["residual_rank"] = rank

                if bounds_enabled:
                    eligible_order = [item for item in ordered if item["b"] < item["upper"]]
                    if d > len(eligible_order):
                        raise EngineFailure(
                            "F4",
                            "E_BOUNDS_CAP_EXHAUSTED",
                            "S7",
                            MODULE_NAME,
                            {"detail": "bounds_capacity_exhausted", "merchant_id": merchant_id},
                        )
                    top_iso = {item["country_iso"] for item in eligible_order[:d]}
                else:
                    top_iso = {item["country_iso"] for item in ordered[:d]}
                total_count = 0
                for item in items:
                    bump = 1 if item["country_iso"] in top_iso else 0
                    count = item["b"] + bump
                    item["count"] = count
                    total_count += count
                    if count < 0:
                        raise EngineFailure(
                            "F4",
                            "INTEGER_SUM_MISMATCH",
                            "S7",
                            MODULE_NAME,
                            {"detail": "negative_count", "merchant_id": merchant_id},
                        )
                    if bounds_enabled:
                        if count < item["lower"] or count > item["upper"]:
                            raise EngineFailure(
                                "F4",
                                "E_BOUNDS_CAP_EXHAUSTED",
                                "S7",
                                MODULE_NAME,
                                {
                                    "detail": "count_out_of_bounds",
                                    "merchant_id": merchant_id,
                                    "country_iso": item["country_iso"],
                                },
                            )
                    if abs(count - item["a"]) > 1.0 + 1e-9:
                        raise EngineFailure(
                            "F4",
                            "INTEGERISATION_FAIL",
                            "S7",
                            MODULE_NAME,
                            {"detail": "proximity_violation", "merchant_id": merchant_id},
                        )
                if total_count != n_outlets:
                    raise EngineFailure(
                        "F4",
                        "INTEGER_SUM_MISMATCH",
                        "S7",
                        MODULE_NAME,
                        {"detail": "sum_mismatch", "merchant_id": merchant_id},
                    )

                if counts_handle is not None:
                    for item in items:
                        payload = {
                            "seed": seed,
                            "parameter_hash": parameter_hash,
                            "run_id": run_id,
                            "manifest_fingerprint": manifest_fingerprint,
                            "merchant_id": merchant_id,
                            "country_iso": item["country_iso"],
                            "count": item["count"],
                            "residual_rank": item["residual_rank"],
                            "candidate_rank": item["candidate_rank"],
                        }
                        counts_handle.write(
                            json.dumps(payload, ensure_ascii=True, sort_keys=True)
                        )
                        counts_handle.write("\n")
                        counts_written += 1

                dirichlet_payload: dict | None = None
                if dirichlet_enabled:
                    dirichlet_payload = _expected_dirichlet_payload(
                        merchant_id,
                        domain_isos,
                        home_iso,
                        shares,
                        n_outlets,
                    )
                    expected_dirichlet_events += 1
                    expected_dirichlet_blocks += int(dirichlet_payload["blocks"])
                    expected_dirichlet_draws += int(dirichlet_payload["draws"])
                    metrics["s7.events.dirichlet_gamma_vector.rows"] += 1
                    metrics["s7.trace.rows"] += 1

                expected_residual_events += len(items)
                metrics["s7.events.residual_rank.rows"] += len(items)
                metrics["s7.trace.rows"] += len(items)

                if existing_event_map is not None:
                    logged_events = existing_event_map.get(merchant_id)
                    if not logged_events:
                        raise EngineFailure(
                            "F4",
                            "E_EVENT_COVERAGE",
                            "S7",
                            MODULE_NAME,
                            {"detail": "missing_residual_rank", "merchant_id": merchant_id},
                            dataset_id=DATASET_RESIDUAL_RANK,
                        )
                    if len(logged_events) != len(items):
                        raise EngineFailure(
                            "F4",
                            "E_EVENT_COVERAGE",
                            "S7",
                            MODULE_NAME,
                            {"detail": "residual_rank_count_mismatch", "merchant_id": merchant_id},
                            dataset_id=DATASET_RESIDUAL_RANK,
                        )
                    for item in items:
                        country_iso = item["country_iso"]
                        payload = logged_events.get(country_iso)
                        if payload is None:
                            raise EngineFailure(
                                "F4",
                                "E_EVENT_COVERAGE",
                                "S7",
                                MODULE_NAME,
                                {"detail": "missing_country_event", "merchant_id": merchant_id},
                                dataset_id=DATASET_RESIDUAL_RANK,
                            )
                        expected = _expected_event_payload(
                            merchant_id,
                            country_iso,
                            item["residual"],
                            item["residual_rank"],
                        )
                        for key, value in expected.items():
                            if payload.get(key) != value:
                                raise EngineFailure(
                                    "F4",
                                    "E_OUTPUT_MISMATCH",
                                    "S7",
                                    MODULE_NAME,
                                    {
                                        "detail": "event_field_mismatch",
                                        "merchant_id": merchant_id,
                                        "field": key,
                                    },
                                    dataset_id=DATASET_RESIDUAL_RANK,
                                )
                    if dirichlet_enabled:
                        if existing_dirichlet_map is None:
                            raise EngineFailure(
                                "F4",
                                "E_EVENT_COVERAGE",
                                "S7",
                                MODULE_DIRICHLET,
                                {"detail": "missing_dirichlet_events"},
                                dataset_id=DATASET_DIRICHLET,
                            )
                        payload = existing_dirichlet_map.get(merchant_id)
                        if payload is None:
                            raise EngineFailure(
                                "F4",
                                "E_EVENT_COVERAGE",
                                "S7",
                                MODULE_DIRICHLET,
                                {"detail": "missing_dirichlet_event", "merchant_id": merchant_id},
                                dataset_id=DATASET_DIRICHLET,
                            )
                        if dirichlet_payload is None:
                            raise EngineFailure(
                                "F4",
                                "E_OUTPUT_MISMATCH",
                                "S7",
                                MODULE_DIRICHLET,
                                {"detail": "dirichlet_payload_missing", "merchant_id": merchant_id},
                                dataset_id=DATASET_DIRICHLET,
                            )
                        for key, value in dirichlet_payload.items():
                            if payload.get(key) != value:
                                raise EngineFailure(
                                    "F4",
                                    "E_OUTPUT_MISMATCH",
                                    "S7",
                                    MODULE_DIRICHLET,
                                    {
                                        "detail": "dirichlet_field_mismatch",
                                        "merchant_id": merchant_id,
                                        "field": key,
                                    },
                                    dataset_id=DATASET_DIRICHLET,
                                )
                    continue

                if event_handle is None or trace_handle is None:
                    raise EngineFailure(
                        "F4",
                        "E_OUTPUT_MISMATCH",
                        "S7",
                        MODULE_NAME,
                        {"detail": "event_handle_missing"},
                    )

                for item in ordered:
                    payload = _expected_event_payload(
                        merchant_id,
                        item["country_iso"],
                        item["residual"],
                        item["residual_rank"],
                    )
                    payload["ts_utc"] = utc_now_rfc3339_micro()
                    errors = list(event_validator.iter_errors(payload))
                    if errors:
                        raise EngineFailure(
                            "F4",
                            "E_SCHEMA_AUTHORITY",
                            "S7",
                            MODULE_NAME,
                            {"detail": errors[0].message, "merchant_id": merchant_id},
                            dataset_id=DATASET_RESIDUAL_RANK,
                        )
                    trace = trace_acc.append(payload)
                    trace_errors = list(trace_validator.iter_errors(trace))
                    if trace_errors:
                        raise EngineFailure(
                            "F4",
                            "E_SCHEMA_AUTHORITY",
                            "S7",
                            MODULE_NAME,
                            {"detail": trace_errors[0].message},
                            dataset_id=DATASET_TRACE,
                        )
                    event_handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
                    event_handle.write("\n")
                    trace_handle.write(json.dumps(trace, ensure_ascii=True, sort_keys=True))
                    trace_handle.write("\n")
                    events_written += 1
                    trace_written += 1

                if dirichlet_enabled:
                    if dirichlet_handle is None or trace_handle is None:
                        raise EngineFailure(
                            "F4",
                            "E_OUTPUT_MISMATCH",
                            "S7",
                            MODULE_DIRICHLET,
                            {"detail": "dirichlet_handle_missing", "merchant_id": merchant_id},
                        )
                    if dirichlet_payload is None:
                        raise EngineFailure(
                            "F4",
                            "E_OUTPUT_MISMATCH",
                            "S7",
                            MODULE_DIRICHLET,
                            {"detail": "dirichlet_payload_missing", "merchant_id": merchant_id},
                            dataset_id=DATASET_DIRICHLET,
                        )
                    payload = dict(dirichlet_payload)
                    payload["ts_utc"] = utc_now_rfc3339_micro()
                    errors = list(dirichlet_validator.iter_errors(payload))
                    if errors:
                        raise EngineFailure(
                            "F4",
                            "E_SCHEMA_AUTHORITY",
                            "S7",
                            MODULE_DIRICHLET,
                            {"detail": errors[0].message, "merchant_id": merchant_id},
                            dataset_id=DATASET_DIRICHLET,
                        )
                    trace = dirichlet_trace_acc.append(payload)
                    trace_errors = list(trace_validator.iter_errors(trace))
                    if trace_errors:
                        raise EngineFailure(
                            "F4",
                            "E_SCHEMA_AUTHORITY",
                            "S7",
                            MODULE_DIRICHLET,
                            {"detail": trace_errors[0].message},
                            dataset_id=DATASET_TRACE,
                        )
                    dirichlet_handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
                    dirichlet_handle.write("\n")
                    trace_handle.write(json.dumps(trace, ensure_ascii=True, sort_keys=True))
                    trace_handle.write("\n")
                    dirichlet_events_written += 1
                    trace_written += 1
        finally:
            if event_handle is not None:
                event_handle.close()
            if trace_handle is not None:
                trace_handle.close()
            if dirichlet_handle is not None:
                dirichlet_handle.close()
            if counts_handle is not None:
                counts_handle.close()

        if existing_event_map is not None:
            extra_merchants = set(existing_event_map) - set(scope_merchants)
            if extra_merchants:
                raise EngineFailure(
                    "F4",
                    "E_EVENT_COVERAGE",
                    "S7",
                    MODULE_NAME,
                    {"detail": "unexpected_merchants", "merchant_ids": sorted(extra_merchants)[:10]},
                    dataset_id=DATASET_RESIDUAL_RANK,
                )

            trace_rows = _trace_rows_for_substream(
                trace_path, MODULE_NAME, SUBSTREAM_LABEL
            )
            if len(trace_rows) != expected_residual_events:
                raise EngineFailure(
                    "F4",
                    "RNG_ACCOUNTING_FAIL",
                    "S7",
                    MODULE_NAME,
                    {
                        "detail": "trace_row_count_mismatch",
                        "expected": expected_residual_events,
                        "actual": len(trace_rows),
                    },
                    dataset_id=DATASET_TRACE,
                )
            for row in trace_rows:
                errors = list(trace_validator.iter_errors(row))
                if errors:
                    raise EngineFailure(
                        "F4",
                        "E_SCHEMA_AUTHORITY",
                        "S7",
                        MODULE_NAME,
                        {"detail": errors[0].message},
                        dataset_id=DATASET_TRACE,
                    )
            if trace_rows:
                last = trace_rows[-1]
                if (
                    int(last.get("events_total", 0)) != expected_residual_events
                    or int(last.get("blocks_total", 0)) != 0
                    or int(last.get("draws_total", 0)) != 0
                ):
                    raise EngineFailure(
                        "F4",
                        "RNG_ACCOUNTING_FAIL",
                        "S7",
                        MODULE_NAME,
                        {"detail": "trace_totals_mismatch"},
                        dataset_id=DATASET_TRACE,
                    )

            if dirichlet_enabled:
                if existing_dirichlet_map is None:
                    raise EngineFailure(
                        "F4",
                        "E_EVENT_COVERAGE",
                        "S7",
                        MODULE_DIRICHLET,
                        {"detail": "missing_dirichlet_events"},
                        dataset_id=DATASET_DIRICHLET,
                    )
                extra_merchants = set(existing_dirichlet_map) - set(scope_merchants)
                if extra_merchants:
                    raise EngineFailure(
                        "F4",
                        "E_EVENT_COVERAGE",
                        "S7",
                        MODULE_DIRICHLET,
                        {"detail": "unexpected_dirichlet_merchants", "merchant_ids": sorted(extra_merchants)[:10]},
                        dataset_id=DATASET_DIRICHLET,
                    )
                trace_rows = _trace_rows_for_substream(
                    trace_path, MODULE_DIRICHLET, SUBSTREAM_DIRICHLET
                )
                if len(trace_rows) != expected_dirichlet_events:
                    raise EngineFailure(
                        "F4",
                        "RNG_ACCOUNTING_FAIL",
                        "S7",
                        MODULE_DIRICHLET,
                        {
                            "detail": "dirichlet_trace_row_count_mismatch",
                            "expected": expected_dirichlet_events,
                            "actual": len(trace_rows),
                        },
                        dataset_id=DATASET_TRACE,
                    )
                for row in trace_rows:
                    errors = list(trace_validator.iter_errors(row))
                    if errors:
                        raise EngineFailure(
                            "F4",
                            "E_SCHEMA_AUTHORITY",
                            "S7",
                            MODULE_DIRICHLET,
                            {"detail": errors[0].message},
                            dataset_id=DATASET_TRACE,
                        )
                if trace_rows:
                    last = trace_rows[-1]
                    blocks_total = int(last.get("blocks_total", 0))
                    draws_total = int(last.get("draws_total", 0))
                    if int(last.get("events_total", 0)) != expected_dirichlet_events:
                        raise EngineFailure(
                            "F4",
                            "RNG_ACCOUNTING_FAIL",
                            "S7",
                            MODULE_DIRICHLET,
                            {"detail": "dirichlet_trace_totals_mismatch"},
                            dataset_id=DATASET_TRACE,
                        )
                    if blocks_total != expected_dirichlet_blocks or draws_total != expected_dirichlet_draws:
                        raise EngineFailure(
                            "F4",
                            "RNG_ACCOUNTING_FAIL",
                            "S7",
                            MODULE_DIRICHLET,
                            {
                                "detail": "dirichlet_trace_totals_mismatch",
                                "expected_blocks": expected_dirichlet_blocks,
                                "expected_draws": expected_dirichlet_draws,
                                "actual_blocks": blocks_total,
                                "actual_draws": draws_total,
                            },
                            dataset_id=DATASET_TRACE,
                        )

        if existing_event_map is None and events_written > 0 and not validate_only:
            event_dir.mkdir(parents=True, exist_ok=True)
            if event_path.exists():
                raise InputResolutionError(
                    f"S7 residual_rank output already exists: {event_path}"
                )
            tmp_event_path.replace(event_path)
            if dirichlet_enabled and dirichlet_events_written > 0:
                dirichlet_dir.mkdir(parents=True, exist_ok=True)
                if dirichlet_path.exists():
                    raise InputResolutionError(
                        f"S7 dirichlet_gamma_vector output already exists: {dirichlet_path}"
                    )
                tmp_dirichlet_path.replace(dirichlet_path)
            if trace_written > 0:
                trace_path.parent.mkdir(parents=True, exist_ok=True)
                with trace_path.open("a", encoding="utf-8") as trace_handle:
                    with tmp_trace_path.open("r", encoding="utf-8") as tmp_handle:
                        for line in tmp_handle:
                            trace_handle.write(line)
                logger.info(
                    "S7: appended trace rows count=%d (residual_rank=%d, dirichlet_gamma_vector=%d)",
                    trace_written,
                    events_written,
                    dirichlet_events_written,
                )
            if counts_written > 0:
                if counts_path.exists():
                    raise InputResolutionError(
                        f"S7 counts handoff already exists: {counts_path}"
                    )
                tmp_counts_path.replace(counts_path)
                logger.info(
                    "S7: wrote counts handoff rows=%d path=%s",
                    counts_written,
                    counts_path,
                )

        if existing_event_map is None and events_written > 0 and validate_only:
            logger.info("S7: validate-only mode; outputs not written")

        logger.info(
            "S7 summary: merchants_in_scope=%d single_country=%d residual_rank_rows=%d "
            "dirichlet_rows=%d trace_rows=%d",
            metrics["s7.merchants_in_scope"],
            metrics["s7.single_country"],
            metrics["s7.events.residual_rank.rows"],
            metrics["s7.events.dirichlet_gamma_vector.rows"],
            metrics["s7.trace.rows"],
        )

        timer.info("S7: completed")
        _emit_state_run("completed")

        event_path_out: Path | None = None
        if existing_event_map is not None:
            existing_paths = [path for path in event_paths if path.exists()]
            event_path_out = existing_paths[0] if existing_paths else None
        elif not validate_only and events_written > 0:
            event_path_out = event_path
        return S7RunResult(
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            event_path=event_path_out,
            trace_path=trace_path,
        )
    except EngineFailure as failure:
        _record_failure(failure)
        raise
    except (ContractError, InputResolutionError, SchemaValidationError) as exc:
        failure = EngineFailure(
            "F5" if isinstance(exc, InputResolutionError) else "F4",
            "s7_contract_failure",
            "S7",
            MODULE_NAME,
            {"detail": str(exc)},
        )
        _record_failure(failure)
        raise
