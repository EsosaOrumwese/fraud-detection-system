"""S4 ZTP sampler runner for Segment 1A."""

from __future__ import annotations

import datetime as dt
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import polars as pl
import yaml
from jsonschema import Draft202012Validator

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
from engine.layers.l1.seg_1A.s2_nb_outlets.rng import (
    UINT64_MAX,
    Substream,
    derive_master_material,
    derive_substream_state,
    u01_pair,
    u01_single,
)


MODULE_NAME = "1A.ztp_sampler"
SUBSTREAM_LABEL = "poisson_component"
CONTEXT = "ztp"

DATASET_HURDLE = "rng_event_hurdle_bernoulli"
DATASET_NB_FINAL = "rng_event_nb_final"
DATASET_POISSON = "rng_event_poisson_component"
DATASET_ZTP_REJECTION = "rng_event_ztp_rejection"
DATASET_ZTP_RETRY = "rng_event_ztp_retry_exhausted"
DATASET_ZTP_FINAL = "rng_event_ztp_final"
DATASET_TRACE = "rng_trace_log"
DATASET_S4_METRICS = "s4_metrics_log"
DATASET_ELIGIBILITY = "crossborder_eligibility_flags"
DATASET_CANDIDATE_SET = "s3_candidate_set"
DATASET_FEATURES = "crossborder_features"


@dataclass(frozen=True)
class S4RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    poisson_dir: Path
    ztp_rejection_path: Path
    ztp_retry_path: Path
    ztp_final_path: Path


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


def _iter_jsonl_files(paths: Iterable[Path]) -> Iterable[tuple[Path, int, dict]]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                yield path, line_no, json.loads(line)


def _event_has_rows(event_path: Path) -> bool:
    if event_path.exists():
        return event_path.stat().st_size > 0
    parent = event_path.parent
    if not parent.exists():
        return False
    for path in parent.glob("*.jsonl"):
        if path.stat().st_size > 0:
            return True
    return False


def _trace_has_substream(trace_path: Path, module: str, substream_label: str) -> bool:
    if not trace_path.exists():
        return False
    with trace_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.get("module") == module and payload.get("substream_label") == substream_label:
                return True
    return False


def _checked_add(current: int, increment: int) -> int:
    total = current + increment
    if total > UINT64_MAX:
        return UINT64_MAX
    return total


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


def _neumaier_sum(values: tuple[float, ...]) -> float:
    total = 0.0
    c = 0.0
    for value in values:
        t = total + value
        if abs(total) >= abs(value):
            c += (total - t) + value
        else:
            c += (value - t) + total
        total = t
    return total + c


def _u128_diff(before_hi: int, before_lo: int, after_hi: int, after_lo: int) -> int:
    before = (int(before_hi) << 64) | int(before_lo)
    after = (int(after_hi) << 64) | int(after_lo)
    if after < before:
        raise EngineFailure(
            "F4",
            "RNG_ACCOUNTING",
            "S4",
            MODULE_NAME,
            {"before": before, "after": after},
        )
    return after - before


def _poisson_inversion(lam: float, stream: Substream) -> tuple[int, int, int]:
    blocks_total = 0
    draws_total = 0
    l = math.exp(-lam)
    k = 0
    p = 1.0
    while p > l:
        u, blocks, draws = u01_single(stream)
        blocks_total += blocks
        draws_total += draws
        p *= u
        k += 1
    return max(k - 1, 0), blocks_total, draws_total


def _poisson_ptrs(lam: float, stream: Substream) -> tuple[int, int, int]:
    blocks_total = 0
    draws_total = 0
    c = 0.767 - 3.36 / lam
    beta = math.pi / math.sqrt(3.0 * lam)
    alpha = beta * lam
    inv_alpha = 1.0 / alpha
    u_cut = 0.5 + 0.5 * beta
    v_r = 0.5 + 0.5 * beta
    a = 1.0 - beta
    b = lam + math.log(c)
    while True:
        u, v, blocks, draws = u01_pair(stream)
        blocks_total += blocks
        draws_total += draws
        if u <= u_cut and v <= v_r:
            k_val = math.floor(b * v / u + lam + 0.43)
            return int(k_val), blocks_total, draws_total
        u_s = 0.5 - abs(u - 0.5)
        k_val = math.floor((2.0 * a / u_s + b) * v + lam + 0.43)
        if k_val < 0:
            continue
        log_accept = math.log(v * inv_alpha / (a / (u_s * u_s) + b))
        if log_accept <= -lam + k_val * math.log(lam) - math.lgamma(k_val + 1.0):
            return int(k_val), blocks_total, draws_total


def _poisson_sample(lam: float, stream: Substream) -> tuple[int, int, int]:
    if lam < 10.0:
        return _poisson_inversion(lam, stream)
    return _poisson_ptrs(lam, stream)


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


def _load_crossborder_hyperparams(path: Path, schema_layer1: dict) -> dict:
    payload = _load_yaml(path)
    schema = _schema_from_pack(schema_layer1, "policy/crossborder_hyperparams")
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
        raise SchemaValidationError(
            "crossborder_hyperparams schema validation failed", details
        )
    return payload


def _load_hurdle_events(
    hurdle_paths: list[Path],
    schema_layer1: dict,
    seed: int,
    parameter_hash: str,
    run_id: str,
) -> dict[int, bool]:
    event_schema = _schema_from_pack(schema_layer1, "rng/events/hurdle_bernoulli")
    validator = Draft202012Validator(event_schema)
    merchants: dict[int, bool] = {}
    for path, line_no, payload in _iter_jsonl_files(hurdle_paths):
        errors = list(validator.iter_errors(payload))
        if errors:
            raise EngineFailure(
                "F4",
                "schema_violation",
                "S4",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no, "detail": errors[0].message},
                dataset_id=DATASET_HURDLE,
            )
        if (
            payload.get("seed") != seed
            or payload.get("parameter_hash") != parameter_hash
            or payload.get("run_id") != run_id
        ):
            raise EngineFailure(
                "F4",
                "PARTITION_MISMATCH",
                "S4",
                MODULE_NAME,
                {"line": line_no},
                dataset_id=DATASET_HURDLE,
            )
        merchant_id = int(payload["merchant_id"])
        if merchant_id in merchants:
            raise EngineFailure(
                "F4",
                "UPSTREAM_DUPLICATE_S1",
                "S4",
                MODULE_NAME,
                {"merchant_id": merchant_id},
                dataset_id=DATASET_HURDLE,
            )
        merchants[merchant_id] = bool(payload.get("is_multi"))
    return merchants


def _load_nb_final_events(
    nb_paths: list[Path],
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
                "schema_violation",
                "S4",
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
                "PARTITION_MISMATCH",
                "S4",
                MODULE_NAME,
                {"line": line_no},
                dataset_id=DATASET_NB_FINAL,
            )
        if payload.get("rng_counter_before_hi") != payload.get("rng_counter_after_hi") or payload.get(
            "rng_counter_before_lo"
        ) != payload.get("rng_counter_after_lo"):
            raise EngineFailure(
                "F4",
                "RNG_ACCOUNTING",
                "S4",
                MODULE_NAME,
                {"line": line_no, "detail": "nb_final_counter_mismatch"},
                dataset_id=DATASET_NB_FINAL,
            )
        if payload.get("blocks") != 0 or payload.get("draws") != "0":
            raise EngineFailure(
                "F4",
                "RNG_ACCOUNTING",
                "S4",
                MODULE_NAME,
                {"line": line_no, "detail": "nb_final_consuming"},
                dataset_id=DATASET_NB_FINAL,
            )
        merchant_id = int(payload["merchant_id"])
        if merchant_id in events:
            raise EngineFailure(
                "F4",
                "UPSTREAM_DUPLICATE_S2",
                "S4",
                MODULE_NAME,
                {"merchant_id": merchant_id},
                dataset_id=DATASET_NB_FINAL,
            )
        events[merchant_id] = payload
    return events


def _load_eligibility_flags(path: Path, parameter_hash: str) -> dict[int, bool]:
    df = pl.read_parquet(path)
    required = {"merchant_id", "is_eligible", "parameter_hash"}
    if not required.issubset(set(df.columns)):
        raise InputResolutionError("crossborder_eligibility_flags missing required columns.")
    if df.filter(pl.col("parameter_hash") != parameter_hash).height > 0:
        raise InputResolutionError("crossborder_eligibility_flags parameter_hash mismatch.")
    return dict(zip(df["merchant_id"].to_list(), df["is_eligible"].to_list()))


def _load_candidate_set(path: Path, parameter_hash: str) -> tuple[dict[int, int], dict[int, int]]:
    df = pl.read_parquet(path)
    required = {"merchant_id", "is_home", "parameter_hash"}
    if not required.issubset(set(df.columns)):
        raise InputResolutionError("s3_candidate_set missing required columns.")
    if df.filter(pl.col("parameter_hash") != parameter_hash).height > 0:
        raise InputResolutionError("s3_candidate_set parameter_hash mismatch.")
    grouped = df.group_by("merchant_id").agg(
        [
            pl.col("is_home").sum().alias("home_count"),
            (~pl.col("is_home")).sum().alias("foreign_count"),
        ]
    )
    a_map = dict(zip(grouped["merchant_id"].to_list(), grouped["foreign_count"].to_list()))
    home_map = dict(zip(grouped["merchant_id"].to_list(), grouped["home_count"].to_list()))
    return a_map, home_map


def _load_features(path: Path, parameter_hash: str, feature_id: str) -> dict[int, float]:
    df = pl.read_parquet(path)
    required = {"merchant_id", "parameter_hash", feature_id}
    if not required.issubset(set(df.columns)):
        raise InputResolutionError("crossborder_features missing required columns.")
    if df.filter(pl.col("parameter_hash") != parameter_hash).height > 0:
        raise InputResolutionError("crossborder_features parameter_hash mismatch.")
    return dict(zip(df["merchant_id"].to_list(), df[feature_id].to_list()))


def _log_failure_line(
    logger,
    seed: int,
    parameter_hash: str,
    run_id: str,
    manifest_fingerprint: str,
    code: str,
    scope: str,
    reason: str,
    merchant_id: Optional[int] = None,
    attempts: Optional[int] = None,
    lambda_extra: Optional[float] = None,
    regime: Optional[str] = None,
) -> None:
    payload = {
        "s4.fail.code": code,
        "s4.fail.scope": scope,
        "s4.fail.reason": reason,
        "s4.run.seed": seed,
        "s4.run.parameter_hash": parameter_hash,
        "s4.run.run_id": run_id,
        "s4.run.manifest_fingerprint": manifest_fingerprint,
    }
    if merchant_id is not None:
        payload["s4.fail.merchant_id"] = merchant_id
    if attempts is not None:
        payload["s4.fail.attempts"] = attempts
    if lambda_extra is not None:
        payload["s4.fail.lambda_extra"] = lambda_extra
    if regime is not None:
        payload["s4.fail.regime"] = regime
    logger.error("S4 failure %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _metrics_base(
    seed: int, parameter_hash: str, run_id: str, manifest_fingerprint: str
) -> dict:
    return {
        "seed": seed,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
        "manifest_fingerprint": manifest_fingerprint,
    }


def _write_metric_line(handle, base: dict, key: str, value: object) -> None:
    payload = dict(base)
    payload[key] = value
    handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    handle.write("\n")


def _has_ztp_poisson_events(poisson_paths: list[Path]) -> bool:
    for _path, _line_no, payload in _iter_jsonl_files(poisson_paths):
        if payload.get("context") == CONTEXT and payload.get("module") == MODULE_NAME:
            return True
    return False


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


def run_s4(config: EngineConfig, run_id: Optional[str] = None) -> S4RunResult:
    logger = get_logger("engine.layers.l1.seg_1A.s4_ztp.l2.runner")
    timer = _StepTimer(logger)

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dictionary_path, dictionary = load_dataset_dictionary(source, "1A")
    registry_path, registry = load_artefact_registry(source, "1A")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
    schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
    logger.info(
        "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s",
        config.contracts_layout,
        config.contracts_root,
        dictionary_path,
        registry_path,
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
    metrics_base = _metrics_base(seed, parameter_hash, run_id, manifest_fingerprint)
    timer.info(f"S4: loaded run receipt {receipt_path}")

    utc_day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    segment_state_runs_path = _segment_state_runs_path(run_paths, dictionary, utc_day)
    failure_recorded = False

    def _emit_state_run(status: str, detail: Optional[str] = None) -> None:
        payload = {
            "layer": "layer1",
            "segment": "1A",
            "state": "S4",
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "run_id": run_id,
            "status": status,
            "ts_utc": utc_now_rfc3339_micro(),
        }
        if detail:
            payload["detail"] = detail
        _append_jsonl(segment_state_runs_path, payload)

    def _record_run_failure(code: str, reason: str | dict) -> None:
        nonlocal failure_recorded
        if failure_recorded:
            return
        failure_recorded = True
        detail = reason
        if isinstance(reason, dict):
            detail = json.dumps(reason, ensure_ascii=True, sort_keys=True)
        payload = {
            "failure_class": "F4",
            "failure_code": code,
            "state": "S4",
            "module": MODULE_NAME,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "seed": seed,
            "run_id": run_id,
            "ts_utc": utc_now_ns(),
            "detail": detail,
        }
        failure_root = (
            run_paths.run_root
            / "data/layer1/1A/validation/failures"
            / f"manifest_fingerprint={manifest_fingerprint}"
            / f"seed={seed}"
            / f"run_id={run_id}"
        )
        write_failure_record(failure_root, payload)
        _emit_state_run("failed", detail=code)

    tokens = {
        "seed": str(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "run_id": run_id,
    }
    metrics_entry = find_dataset_entry(dictionary, DATASET_S4_METRICS).entry
    metrics_path = _resolve_run_path(run_paths, metrics_entry["path"], tokens)
    metrics_exists = metrics_path.exists()

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
        if "crossborder_hyperparams.yaml" not in sealed_ids:
            raise InputResolutionError(
                "sealed_inputs_1A missing crossborder_hyperparams.yaml"
            )

        hyperparams_path = _sealed_path(sealed_inputs, "crossborder_hyperparams.yaml")
        hyperparams = _load_crossborder_hyperparams(hyperparams_path, schema_layer1)
        ztp_policy = hyperparams.get("ztp") or {}
        exhaustion_policy = ztp_policy.get("ztp_exhaustion_policy")
        if exhaustion_policy not in {"abort", "downgrade_domestic"}:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="POLICY_INVALID",
                scope="run",
                reason="ztp_exhaustion_policy_invalid",
            )
            _record_run_failure("POLICY_INVALID", "ztp_exhaustion_policy_invalid")
            raise EngineFailure(
                "F4", "POLICY_INVALID", "S4", MODULE_NAME, "invalid_policy"
            )

        feature_spec = ztp_policy.get("feature_x") or {}
        feature_id = feature_spec.get("feature_id")
        if not feature_id:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="POLICY_INVALID",
                scope="run",
                reason="missing_feature_id",
            )
            _record_run_failure("POLICY_INVALID", "missing_feature_id")
            raise EngineFailure(
                "F4", "POLICY_INVALID", "S4", MODULE_NAME, "missing_feature_id"
            )
        try:
            x_default = float(feature_spec.get("x_default", 0.0))
        except (TypeError, ValueError):
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="POLICY_INVALID",
                scope="run",
                reason="x_default_invalid",
            )
            _record_run_failure("POLICY_INVALID", "x_default_invalid")
            raise EngineFailure(
                "F4", "POLICY_INVALID", "S4", MODULE_NAME, "x_default_invalid"
            )
        if not math.isfinite(x_default) or x_default < 0.0 or x_default > 1.0:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="POLICY_INVALID",
                scope="run",
                reason="x_default_out_of_range",
                x_default=x_default,
            )
            _record_run_failure("POLICY_INVALID", "x_default_out_of_range")
            raise EngineFailure(
                "F4", "POLICY_INVALID", "S4", MODULE_NAME, "x_default_out_of_range"
            )
        x_transform = feature_spec.get("x_transform") or {}
        x_transform_kind = x_transform.get("kind")
        if x_transform_kind != "clamp01":
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="POLICY_INVALID",
                scope="run",
                reason="unsupported_x_transform",
            )
            _record_run_failure("POLICY_INVALID", "unsupported_x_transform")
            raise EngineFailure(
                "F4", "POLICY_INVALID", "S4", MODULE_NAME, "unsupported_x_transform"
            )

        theta_order = list(ztp_policy.get("theta_order") or [])
        theta = dict(ztp_policy.get("theta") or {})
        max_attempts = int(ztp_policy.get("MAX_ZTP_ZERO_ATTEMPTS", 64))

        hurdle_entry = find_dataset_entry(dictionary, DATASET_HURDLE).entry
        hurdle_paths = _resolve_run_glob(run_paths, hurdle_entry["path"], tokens)
        if not hurdle_paths:
            raise InputResolutionError("Missing hurdle_bernoulli event stream.")

        nb_entry = find_dataset_entry(dictionary, DATASET_NB_FINAL).entry
        nb_paths = _resolve_run_glob(run_paths, nb_entry["path"], tokens)
        if not nb_paths:
            raise InputResolutionError("Missing nb_final event stream.")

        trace_entry = find_dataset_entry(dictionary, DATASET_TRACE).entry
        trace_path = _resolve_run_path(run_paths, trace_entry["path"], tokens)
        if not trace_path.exists():
            raise InputResolutionError("Missing rng_trace_log.")

        poisson_entry = find_dataset_entry(dictionary, DATASET_POISSON).entry
        poisson_paths = _resolve_run_glob(run_paths, poisson_entry["path"], tokens)
        poisson_dir = _resolve_event_dir(run_paths, poisson_entry["path"], tokens)

        rejection_entry = find_dataset_entry(dictionary, DATASET_ZTP_REJECTION).entry
        rejection_path = _resolve_event_path(run_paths, rejection_entry["path"], tokens)

        retry_entry = find_dataset_entry(dictionary, DATASET_ZTP_RETRY).entry
        retry_path = _resolve_event_path(run_paths, retry_entry["path"], tokens)

        final_entry = find_dataset_entry(dictionary, DATASET_ZTP_FINAL).entry
        final_path = _resolve_event_path(run_paths, final_entry["path"], tokens)

        eligibility_entry = find_dataset_entry(dictionary, DATASET_ELIGIBILITY).entry
        eligibility_path = _resolve_run_path(
            run_paths, eligibility_entry["path"], {"parameter_hash": parameter_hash}
        )
        eligibility_file = _select_dataset_file(DATASET_ELIGIBILITY, eligibility_path)

        candidate_entry = find_dataset_entry(dictionary, DATASET_CANDIDATE_SET).entry
        candidate_path = _resolve_run_path(
            run_paths, candidate_entry["path"], {"parameter_hash": parameter_hash}
        )
        candidate_file = _select_dataset_file(DATASET_CANDIDATE_SET, candidate_path)

        features_entry = find_dataset_entry(dictionary, DATASET_FEATURES).entry
        features_path = _resolve_run_path(
            run_paths, features_entry["path"], {"parameter_hash": parameter_hash}
        )
        features_file = None
        if features_path.exists():
            features_file = _select_dataset_file(DATASET_FEATURES, features_path)

        hurdle_map = _load_hurdle_events(
            hurdle_paths, schema_layer1, seed, parameter_hash, run_id
        )
        nb_final_map = _load_nb_final_events(
            nb_paths, schema_layer1, seed, parameter_hash, run_id
        )
        eligibility_map = _load_eligibility_flags(eligibility_file, parameter_hash)
        a_map, home_map = _load_candidate_set(candidate_file, parameter_hash)

        features_missing = features_file is None
        features_map: dict[int, float] = {}
        if features_file is not None:
            features_map = _load_features(features_file, parameter_hash, feature_id)
        else:
            logger.info("S4: crossborder_features missing; using x_default for all")

        for merchant_id in sorted(set(eligibility_map) - set(hurdle_map)):
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="UPSTREAM_MISSING_S1",
                scope="merchant",
                reason="missing_hurdle_event",
                merchant_id=merchant_id,
            )

        scope_merchants: list[int] = []
        for merchant_id, is_multi in hurdle_map.items():
            if not is_multi:
                continue
            eligible = eligibility_map.get(merchant_id)
            if eligible is None:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="UPSTREAM_MISSING_A",
                    scope="merchant",
                    reason="missing_eligibility",
                    merchant_id=merchant_id,
                )
                continue
            if not eligible:
                continue
            if home_map.get(merchant_id, 0) < 1:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="UPSTREAM_MISSING_A",
                    scope="merchant",
                    reason="missing_home_row",
                    merchant_id=merchant_id,
                )
                continue
            scope_merchants.append(merchant_id)

        scope_merchants = sorted(scope_merchants)

        existing_s4 = (
            _has_ztp_poisson_events(poisson_paths)
            or _event_has_rows(rejection_path)
            or _event_has_rows(retry_path)
            or _event_has_rows(final_path)
        )
        existing_trace = _trace_has_substream(trace_path, MODULE_NAME, SUBSTREAM_LABEL)

        if existing_s4 and existing_trace:
            if not metrics_exists:
                logger.info("S4: metrics file missing; validation only will proceed")
            timer.info("S4: existing outputs detected; running validation only")
            _validate_s4_outputs(
                logger=logger,
                run_paths=run_paths,
                dictionary=dictionary,
                schema_layer1=schema_layer1,
                tokens=tokens,
                seed=seed,
                parameter_hash=parameter_hash,
                run_id=run_id,
                manifest_fingerprint=manifest_fingerprint,
                scope_merchants=scope_merchants,
                hurdle_map=hurdle_map,
                nb_final_map=nb_final_map,
                eligibility_map=eligibility_map,
                a_map=a_map,
                home_map=home_map,
                exhaustion_policy=exhaustion_policy,
                max_attempts=max_attempts,
            )
            _emit_state_run("completed")
            return S4RunResult(
                run_id=run_id,
                parameter_hash=parameter_hash,
                manifest_fingerprint=manifest_fingerprint,
                poisson_dir=poisson_dir,
                ztp_rejection_path=rejection_path,
                ztp_retry_path=retry_path,
                ztp_final_path=final_path,
            )
        if existing_s4 or existing_trace or metrics_exists:
            raise InputResolutionError(
                "Partial S4 outputs detected; refuse to append. "
                "Remove existing S4 outputs or resume a clean run_id."
            )

        total = len(scope_merchants)
        progress_every = max(1, min(10_000, total // 10 if total else 1))
        start_time = time.monotonic()
        logger.info(
            "S4: entering ZTP loop for eligible multi-site merchants "
            "(S1 is_multi=true, S3 is_eligible=true, has nb_final + home row); "
            "targets=%s",
            total,
        )

        if total == 0:
            timer.info("S4: no eligible merchants; no outputs emitted")
            _emit_state_run("completed")
            metrics = _init_metrics()
            tmp_dir = run_paths.tmp_root / "s4_ztp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_metrics_path = tmp_dir / "s4_metrics.jsonl"
            with tmp_metrics_path.open("w", encoding="utf-8") as metrics_handle:
                _emit_metrics_counters(metrics_handle, metrics_base, metrics)
            metrics_path.parent.mkdir(parents=True, exist_ok=True)
            if metrics_path.exists():
                raise InputResolutionError(
                    f"S4 metrics output already exists: {metrics_path}"
                )
            tmp_metrics_path.replace(metrics_path)
            _log_metrics_summary(logger, metrics=metrics)
            return S4RunResult(
                run_id=run_id,
                parameter_hash=parameter_hash,
                manifest_fingerprint=manifest_fingerprint,
                poisson_dir=poisson_dir,
                ztp_rejection_path=rejection_path,
                ztp_retry_path=retry_path,
                ztp_final_path=final_path,
            )

        master_material = derive_master_material(bytes.fromhex(manifest_fingerprint), seed)

        tmp_dir = run_paths.tmp_root / "s4_ztp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_poisson_path = tmp_dir / "rng_event_poisson_component.jsonl"
        tmp_rejection_path = tmp_dir / "rng_event_ztp_rejection.jsonl"
        tmp_retry_path = tmp_dir / "rng_event_ztp_retry_exhausted.jsonl"
        tmp_final_path = tmp_dir / "rng_event_ztp_final.jsonl"
        tmp_trace_path = tmp_dir / "rng_trace_log_s4.jsonl"
        tmp_metrics_path = tmp_dir / "s4_metrics.jsonl"

        metrics = _init_metrics()
        trace_acc = _TraceAccumulator(MODULE_NAME, SUBSTREAM_LABEL)

        poisson_written = 0
        rejection_written = 0
        retry_written = 0
        final_written = 0
        trace_written = 0

        with (
            tmp_poisson_path.open("w", encoding="utf-8") as poisson_handle,
            tmp_rejection_path.open("w", encoding="utf-8") as rejection_handle,
            tmp_retry_path.open("w", encoding="utf-8") as retry_handle,
            tmp_final_path.open("w", encoding="utf-8") as final_handle,
            tmp_trace_path.open("w", encoding="utf-8") as trace_handle,
            tmp_metrics_path.open("w", encoding="utf-8") as metrics_handle,
        ):
            for idx, merchant_id in enumerate(scope_merchants, start=1):
                if idx % progress_every == 0 or idx == total:
                    elapsed = max(time.monotonic() - start_time, 1e-9)
                    rate = idx / elapsed
                    eta = (total - idx) / rate if rate > 0 else 0.0
                    logger.info(
                        "S4 progress %d/%d (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
                        idx,
                        total,
                        elapsed,
                        rate,
                        eta,
                    )

                metrics["s4.merchants_in_scope"] += 1

                nb_event = nb_final_map.get(merchant_id)
                if nb_event is None:
                    _log_failure_line(
                        logger,
                        seed,
                        parameter_hash,
                        run_id,
                        manifest_fingerprint,
                        code="UPSTREAM_MISSING_S2",
                        scope="merchant",
                        reason="missing_nb_final",
                        merchant_id=merchant_id,
                    )
                    continue
                n_outlets = int(nb_event.get("n_outlets"))
                if n_outlets < 2:
                    _log_failure_line(
                        logger,
                        seed,
                        parameter_hash,
                        run_id,
                        manifest_fingerprint,
                        code="UPSTREAM_MISSING_S2",
                        scope="merchant",
                        reason="nb_final_invalid",
                        merchant_id=merchant_id,
                    )
                    continue

                a_value = a_map.get(merchant_id)
                if a_value is None:
                    _log_failure_line(
                        logger,
                        seed,
                        parameter_hash,
                        run_id,
                        manifest_fingerprint,
                        code="UPSTREAM_MISSING_A",
                        scope="merchant",
                        reason="missing_candidate_set",
                        merchant_id=merchant_id,
                    )
                    continue

                x_value = features_map.get(merchant_id, x_default)
                if features_missing and merchant_id not in features_map:
                    x_value = x_default
                try:
                    x_value = float(x_value)
                except (TypeError, ValueError):
                    _log_failure_line(
                        logger,
                        seed,
                        parameter_hash,
                        run_id,
                        manifest_fingerprint,
                        code="POLICY_INVALID",
                        scope="run",
                        reason="x_value_invalid",
                        merchant_id=merchant_id,
                    )
                    _record_run_failure("POLICY_INVALID", "x_value_invalid")
                    raise EngineFailure(
                        "F4", "POLICY_INVALID", "S4", MODULE_NAME, "x_value_invalid"
                    )
                if not math.isfinite(x_value) or x_value < 0.0 or x_value > 1.0:
                    _log_failure_line(
                        logger,
                        seed,
                        parameter_hash,
                        run_id,
                        manifest_fingerprint,
                        code="POLICY_INVALID",
                        scope="run",
                        reason="x_value_out_of_range",
                        merchant_id=merchant_id,
                        x_value=x_value,
                    )
                    _record_run_failure("POLICY_INVALID", "x_value_out_of_range")
                    raise EngineFailure(
                        "F4", "POLICY_INVALID", "S4", MODULE_NAME, "x_value_out_of_range"
                    )

                log_n = math.log(float(n_outlets))
                terms: list[float] = []
                for term_name in theta_order:
                    coeff = theta.get(term_name)
                    if coeff is None:
                        _log_failure_line(
                            logger,
                            seed,
                            parameter_hash,
                            run_id,
                            manifest_fingerprint,
                            code="POLICY_INVALID",
                            scope="run",
                            reason="missing_theta",
                        )
                        _record_run_failure("POLICY_INVALID", "missing_theta")
                        raise EngineFailure(
                            "F4", "POLICY_INVALID", "S4", MODULE_NAME, "missing_theta"
                        )
                    if term_name == "theta0_intercept":
                        terms.append(float(coeff))
                    elif term_name == "theta1_log_n_sites":
                        terms.append(float(coeff) * log_n)
                    elif term_name == "theta2_openness":
                        terms.append(float(coeff) * x_value)
                    else:
                        _log_failure_line(
                            logger,
                            seed,
                            parameter_hash,
                            run_id,
                            manifest_fingerprint,
                            code="POLICY_INVALID",
                            scope="run",
                            reason="unknown_theta_term",
                        )
                        _record_run_failure("POLICY_INVALID", "unknown_theta_term")
                        raise EngineFailure(
                            "F4", "POLICY_INVALID", "S4", MODULE_NAME, "unknown_theta_term"
                        )

                eta = _neumaier_sum(tuple(terms))
                lambda_extra = math.exp(eta)
                if not math.isfinite(lambda_extra) or lambda_extra <= 0.0:
                    _log_failure_line(
                        logger,
                        seed,
                        parameter_hash,
                        run_id,
                        manifest_fingerprint,
                        code="NUMERIC_INVALID",
                        scope="merchant",
                        reason="lambda_invalid",
                        merchant_id=merchant_id,
                    )
                    continue

                _write_metric_line(
                    metrics_handle,
                    metrics_base,
                    "s4.lambda.hist",
                    lambda_extra,
                )

                regime = "inversion" if lambda_extra < 10.0 else "ptrs"
                if regime == "inversion":
                    metrics["s4.regime.inversion"] += 1
                else:
                    metrics["s4.regime.ptrs"] += 1

                stream = derive_substream_state(
                    master_material, SUBSTREAM_LABEL, merchant_id
                )
                poisson_ms_total = 0.0

                if int(a_value) == 0:
                    before_hi, before_lo = stream.counter()
                    final_event = {
                        "ts_utc": utc_now_rfc3339_micro(),
                        "seed": seed,
                        "parameter_hash": parameter_hash,
                        "manifest_fingerprint": manifest_fingerprint,
                        "run_id": run_id,
                        "module": MODULE_NAME,
                        "substream_label": SUBSTREAM_LABEL,
                        "context": CONTEXT,
                        "rng_counter_before_lo": before_lo,
                        "rng_counter_before_hi": before_hi,
                        "rng_counter_after_lo": before_lo,
                        "rng_counter_after_hi": before_hi,
                        "blocks": 0,
                        "draws": "0",
                        "merchant_id": merchant_id,
                        "K_target": 0,
                        "lambda_extra": lambda_extra,
                        "attempts": 0,
                        "regime": regime,
                    }
                    final_handle.write(json.dumps(final_event, ensure_ascii=True, sort_keys=True))
                    final_handle.write("\n")
                    final_written += 1
                    trace = trace_acc.append(final_event)
                    trace_handle.write(json.dumps(trace, ensure_ascii=True, sort_keys=True))
                    trace_handle.write("\n")
                    trace_written += 1
                    metrics["s4.short_circuit_no_admissible"] += 1
                    metrics["s4.trace.rows"] += 1
                    _write_metric_line(
                        metrics_handle,
                        metrics_base,
                        "s4.attempts.hist",
                        0,
                    )
                    _write_metric_line(
                        metrics_handle,
                        metrics_base,
                        "s4.merchant.summary",
                        {
                            "merchant_id": merchant_id,
                            "attempts": 0,
                            "accepted_K": 0,
                            "regime": regime,
                            "exhausted": False,
                        },
                    )
                    continue

                attempt = 0
                accepted = False
                while True:
                    attempt += 1
                    before_hi, before_lo = stream.counter()
                    attempt_start = time.monotonic()
                    k, blocks_used, draws_used = _poisson_sample(lambda_extra, stream)
                    poisson_ms_total += (time.monotonic() - attempt_start) * 1000.0
                    after_hi, after_lo = stream.counter()
                    blocks_delta = _u128_diff(before_hi, before_lo, after_hi, after_lo)
                    if int(blocks_delta) != int(blocks_used):
                        _log_failure_line(
                            logger,
                            seed,
                            parameter_hash,
                            run_id,
                            manifest_fingerprint,
                            code="RNG_ACCOUNTING",
                            scope="merchant",
                            reason="block_mismatch",
                            merchant_id=merchant_id,
                            attempts=attempt,
                            lambda_extra=lambda_extra,
                            regime=regime,
                        )
                        _record_run_failure("RNG_ACCOUNTING", "block_mismatch")
                        raise EngineFailure(
                            "F4", "RNG_ACCOUNTING", "S4", MODULE_NAME, "block_mismatch"
                        )
                    poisson_event = {
                        "ts_utc": utc_now_rfc3339_micro(),
                        "seed": seed,
                        "parameter_hash": parameter_hash,
                        "manifest_fingerprint": manifest_fingerprint,
                        "run_id": run_id,
                        "module": MODULE_NAME,
                        "substream_label": SUBSTREAM_LABEL,
                        "context": CONTEXT,
                        "rng_counter_before_lo": before_lo,
                        "rng_counter_before_hi": before_hi,
                        "rng_counter_after_lo": after_lo,
                        "rng_counter_after_hi": after_hi,
                        "blocks": blocks_used,
                        "draws": str(draws_used),
                        "merchant_id": merchant_id,
                        "lambda": lambda_extra,
                        "k": k,
                        "attempt": attempt,
                    }
                    poisson_handle.write(json.dumps(poisson_event, ensure_ascii=True, sort_keys=True))
                    poisson_handle.write("\n")
                    poisson_written += 1
                    trace = trace_acc.append(poisson_event)
                    trace_handle.write(json.dumps(trace, ensure_ascii=True, sort_keys=True))
                    trace_handle.write("\n")
                    trace_written += 1
                    metrics["s4.attempts.total"] += 1
                    metrics["s4.trace.rows"] += 1

                    if k == 0:
                        before_hi, before_lo = stream.counter()
                        rejection_event = {
                            "ts_utc": utc_now_rfc3339_micro(),
                            "seed": seed,
                            "parameter_hash": parameter_hash,
                            "manifest_fingerprint": manifest_fingerprint,
                            "run_id": run_id,
                            "module": MODULE_NAME,
                            "substream_label": SUBSTREAM_LABEL,
                            "context": CONTEXT,
                            "rng_counter_before_lo": before_lo,
                            "rng_counter_before_hi": before_hi,
                            "rng_counter_after_lo": before_lo,
                            "rng_counter_after_hi": before_hi,
                            "blocks": 0,
                            "draws": "0",
                            "merchant_id": merchant_id,
                            "lambda_extra": lambda_extra,
                            "k": 0,
                            "attempt": attempt,
                        }
                        rejection_handle.write(
                            json.dumps(rejection_event, ensure_ascii=True, sort_keys=True)
                        )
                        rejection_handle.write("\n")
                        rejection_written += 1
                        trace = trace_acc.append(rejection_event)
                        trace_handle.write(json.dumps(trace, ensure_ascii=True, sort_keys=True))
                        trace_handle.write("\n")
                        trace_written += 1
                        metrics["s4.rejections"] += 1
                        metrics["s4.trace.rows"] += 1

                        if attempt >= max_attempts:
                            if exhaustion_policy == "abort":
                                before_hi, before_lo = stream.counter()
                                retry_event = {
                                    "ts_utc": utc_now_rfc3339_micro(),
                                    "seed": seed,
                                    "parameter_hash": parameter_hash,
                                    "manifest_fingerprint": manifest_fingerprint,
                                    "run_id": run_id,
                                    "module": MODULE_NAME,
                                    "substream_label": SUBSTREAM_LABEL,
                                    "context": CONTEXT,
                                    "rng_counter_before_lo": before_lo,
                                    "rng_counter_before_hi": before_hi,
                                    "rng_counter_after_lo": before_lo,
                                    "rng_counter_after_hi": before_hi,
                                    "blocks": 0,
                                    "draws": "0",
                                    "merchant_id": merchant_id,
                                    "lambda_extra": lambda_extra,
                                    "attempts": attempt,
                                    "aborted": True,
                                }
                                retry_handle.write(
                                    json.dumps(retry_event, ensure_ascii=True, sort_keys=True)
                                )
                                retry_handle.write("\n")
                                retry_written += 1
                                trace = trace_acc.append(retry_event)
                                trace_handle.write(
                                    json.dumps(trace, ensure_ascii=True, sort_keys=True)
                                )
                                trace_handle.write("\n")
                                trace_written += 1
                                metrics["s4.aborted"] += 1
                                metrics["s4.trace.rows"] += 1
                                _write_metric_line(
                                    metrics_handle,
                                    metrics_base,
                                    "s4.attempts.hist",
                                    attempt,
                                )
                                if poisson_ms_total > 0.0:
                                    metric_key = (
                                        "s4.ms.poisson_inversion"
                                        if regime == "inversion"
                                        else "s4.ms.poisson_ptrs"
                                    )
                                    _write_metric_line(
                                        metrics_handle,
                                        metrics_base,
                                        metric_key,
                                        poisson_ms_total,
                                    )
                                _log_failure_line(
                                    logger,
                                    seed,
                                    parameter_hash,
                                    run_id,
                                    manifest_fingerprint,
                                    code="ZTP_EXHAUSTED_ABORT",
                                    scope="merchant",
                                    reason="max_attempts_abort",
                                    merchant_id=merchant_id,
                                    attempts=attempt,
                                    lambda_extra=lambda_extra,
                                    regime=regime,
                                )
                                break
                            before_hi, before_lo = stream.counter()
                            final_event = {
                                "ts_utc": utc_now_rfc3339_micro(),
                                "seed": seed,
                                "parameter_hash": parameter_hash,
                                "manifest_fingerprint": manifest_fingerprint,
                                "run_id": run_id,
                                "module": MODULE_NAME,
                                "substream_label": SUBSTREAM_LABEL,
                                "context": CONTEXT,
                                "rng_counter_before_lo": before_lo,
                                "rng_counter_before_hi": before_hi,
                                "rng_counter_after_lo": before_lo,
                                "rng_counter_after_hi": before_hi,
                                "blocks": 0,
                                "draws": "0",
                                "merchant_id": merchant_id,
                                "K_target": 0,
                                "lambda_extra": lambda_extra,
                                "attempts": attempt,
                                "regime": regime,
                                "exhausted": True,
                            }
                            final_handle.write(
                                json.dumps(final_event, ensure_ascii=True, sort_keys=True)
                            )
                            final_handle.write("\n")
                            final_written += 1
                            trace = trace_acc.append(final_event)
                            trace_handle.write(
                                json.dumps(trace, ensure_ascii=True, sort_keys=True)
                            )
                            trace_handle.write("\n")
                            trace_written += 1
                            metrics["s4.downgrade_domestic"] += 1
                            metrics["s4.trace.rows"] += 1
                            _write_metric_line(
                                metrics_handle,
                                metrics_base,
                                "s4.attempts.hist",
                                attempt,
                            )
                            if poisson_ms_total > 0.0:
                                metric_key = (
                                    "s4.ms.poisson_inversion"
                                    if regime == "inversion"
                                    else "s4.ms.poisson_ptrs"
                                )
                                _write_metric_line(
                                    metrics_handle,
                                    metrics_base,
                                    metric_key,
                                    poisson_ms_total,
                                )
                            _write_metric_line(
                                metrics_handle,
                                metrics_base,
                                "s4.merchant.summary",
                                {
                                    "merchant_id": merchant_id,
                                    "attempts": attempt,
                                    "accepted_K": 0,
                                    "regime": regime,
                                    "exhausted": True,
                                },
                            )
                            break
                        continue

                    before_hi, before_lo = stream.counter()
                    final_event = {
                        "ts_utc": utc_now_rfc3339_micro(),
                        "seed": seed,
                        "parameter_hash": parameter_hash,
                        "manifest_fingerprint": manifest_fingerprint,
                        "run_id": run_id,
                        "module": MODULE_NAME,
                        "substream_label": SUBSTREAM_LABEL,
                        "context": CONTEXT,
                        "rng_counter_before_lo": before_lo,
                        "rng_counter_before_hi": before_hi,
                        "rng_counter_after_lo": before_lo,
                        "rng_counter_after_hi": before_hi,
                        "blocks": 0,
                        "draws": "0",
                        "merchant_id": merchant_id,
                        "K_target": k,
                        "lambda_extra": lambda_extra,
                        "attempts": attempt,
                        "regime": regime,
                    }
                    final_handle.write(
                        json.dumps(final_event, ensure_ascii=True, sort_keys=True)
                    )
                    final_handle.write("\n")
                    final_written += 1
                    trace = trace_acc.append(final_event)
                    trace_handle.write(json.dumps(trace, ensure_ascii=True, sort_keys=True))
                    trace_handle.write("\n")
                    trace_written += 1
                    metrics["s4.accepted"] += 1
                    metrics["s4.trace.rows"] += 1
                    _write_metric_line(
                        metrics_handle,
                        metrics_base,
                        "s4.attempts.hist",
                        attempt,
                    )
                    if poisson_ms_total > 0.0:
                        metric_key = (
                            "s4.ms.poisson_inversion"
                            if regime == "inversion"
                            else "s4.ms.poisson_ptrs"
                        )
                        _write_metric_line(
                            metrics_handle,
                            metrics_base,
                            metric_key,
                            poisson_ms_total,
                        )
                    _write_metric_line(
                        metrics_handle,
                        metrics_base,
                        "s4.merchant.summary",
                        {
                            "merchant_id": merchant_id,
                            "attempts": attempt,
                            "accepted_K": k,
                            "regime": regime,
                            "exhausted": False,
                        },
                    )
                    accepted = True
                    break

                if not accepted and attempt >= max_attempts and exhaustion_policy != "abort":
                    # Defensive: ensure loop exit for downgrade path.
                    continue

            _emit_metrics_counters(metrics_handle, metrics_base, metrics)

        total_events = poisson_written + rejection_written + retry_written + final_written
        if trace_written != total_events:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="TRACE_MISSING",
                scope="run",
                reason="trace_count_mismatch",
            )
            _record_run_failure("TRACE_MISSING", "trace_count_mismatch")
            raise EngineFailure(
                "F4", "TRACE_MISSING", "S4", MODULE_NAME, "trace_count_mismatch"
            )

        poisson_out_path = None
        if poisson_written > 0:
            poisson_out_path = _next_part_path(poisson_dir)
            poisson_out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_poisson_path.replace(poisson_out_path)
        else:
            tmp_poisson_path.unlink(missing_ok=True)

        if rejection_written > 0:
            rejection_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_rejection_path.replace(rejection_path)
        else:
            tmp_rejection_path.unlink(missing_ok=True)

        if retry_written > 0:
            retry_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_retry_path.replace(retry_path)
        else:
            tmp_retry_path.unlink(missing_ok=True)

        if final_written > 0:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_final_path.replace(final_path)
        else:
            tmp_final_path.unlink(missing_ok=True)

        if trace_written > 0:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with trace_path.open("a", encoding="utf-8") as dest_handle, tmp_trace_path.open(
                "r", encoding="utf-8"
            ) as src_handle:
                for line in src_handle:
                    dest_handle.write(line)
        tmp_trace_path.unlink(missing_ok=True)

        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        if metrics_path.exists():
            raise InputResolutionError(f"S4 metrics output already exists: {metrics_path}")
        tmp_metrics_path.replace(metrics_path)

        timer.info("S4: events + trace emitted")
        logger.info(
            "S4: emitted poisson=%s rejection=%s retry=%s final=%s",
            poisson_out_path if poisson_written else "none",
            rejection_path if rejection_written else "none",
            retry_path if retry_written else "none",
            final_path if final_written else "none",
        )

        _validate_s4_outputs(
            logger=logger,
            run_paths=run_paths,
            dictionary=dictionary,
            schema_layer1=schema_layer1,
            tokens=tokens,
            seed=seed,
            parameter_hash=parameter_hash,
            run_id=run_id,
            manifest_fingerprint=manifest_fingerprint,
            scope_merchants=scope_merchants,
            hurdle_map=hurdle_map,
            nb_final_map=nb_final_map,
            eligibility_map=eligibility_map,
            a_map=a_map,
            home_map=home_map,
            exhaustion_policy=exhaustion_policy,
            max_attempts=max_attempts,
        )
        timer.info("S4: validation complete")

        _log_metrics_summary(logger, metrics=metrics)
        _emit_state_run("completed")
        return S4RunResult(
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            poisson_dir=poisson_dir,
            ztp_rejection_path=rejection_path,
            ztp_retry_path=retry_path,
            ztp_final_path=final_path,
        )
    except EngineFailure as failure:
        _record_run_failure(failure.failure_code, failure.detail)
        raise
    except (ContractError, InputResolutionError, SchemaValidationError) as exc:
        failure = EngineFailure(
            "F5" if isinstance(exc, InputResolutionError) else "F4",
            "s4_contract_failure",
            "S4",
            MODULE_NAME,
            {"detail": str(exc)},
        )
        _record_run_failure(failure.failure_code, failure.detail)
        raise

def _init_metrics() -> dict[str, int]:
    return {
        "s4.merchants_in_scope": 0,
        "s4.accepted": 0,
        "s4.short_circuit_no_admissible": 0,
        "s4.downgrade_domestic": 0,
        "s4.aborted": 0,
        "s4.rejections": 0,
        "s4.attempts.total": 0,
        "s4.trace.rows": 0,
        "s4.regime.inversion": 0,
        "s4.regime.ptrs": 0,
    }


def _emit_metrics_counters(handle, base: dict, metrics: dict[str, int]) -> None:
    ordered_keys = [
        "s4.merchants_in_scope",
        "s4.accepted",
        "s4.short_circuit_no_admissible",
        "s4.downgrade_domestic",
        "s4.aborted",
        "s4.rejections",
        "s4.attempts.total",
        "s4.trace.rows",
        "s4.regime.inversion",
        "s4.regime.ptrs",
    ]
    for key in ordered_keys:
        _write_metric_line(handle, base, key, metrics.get(key, 0))


def _log_metrics_summary(
    logger,
    metrics: dict[str, int],
) -> None:
    attempts_total = metrics.get("s4.attempts.total", 0)
    attempts_denom = (
        metrics.get("s4.accepted", 0)
        + metrics.get("s4.downgrade_domestic", 0)
        + metrics.get("s4.aborted", 0)
    )
    mean_attempts = attempts_total / attempts_denom if attempts_denom else 0.0
    logger.info(
        "S4 summary: merchants=%s accept=%s downgrade=%s abort=%s short_circuit=%s mean_attempts=%.2f",
        metrics.get("s4.merchants_in_scope", 0),
        metrics.get("s4.accepted", 0),
        metrics.get("s4.downgrade_domestic", 0),
        metrics.get("s4.aborted", 0),
        metrics.get("s4.short_circuit_no_admissible", 0),
        mean_attempts,
    )


def _validate_s4_outputs(
    *,
    logger,
    run_paths: RunPaths,
    dictionary: dict,
    schema_layer1: dict,
    tokens: dict[str, str],
    seed: int,
    parameter_hash: str,
    run_id: str,
    manifest_fingerprint: str,
    scope_merchants: list[int],
    hurdle_map: dict[int, bool],
    nb_final_map: dict[int, dict],
    eligibility_map: dict[int, bool],
    a_map: dict[int, int],
    home_map: dict[int, int],
    exhaustion_policy: str,
    max_attempts: int,
) -> None:
    poisson_schema = _schema_from_pack(schema_layer1, "rng/events/poisson_component")
    rejection_schema = _schema_from_pack(schema_layer1, "rng/events/ztp_rejection")
    retry_schema = _schema_from_pack(schema_layer1, "rng/events/ztp_retry_exhausted")
    final_schema = _schema_from_pack(schema_layer1, "rng/events/ztp_final")
    trace_schema = _schema_from_pack(schema_layer1, "rng/core/rng_trace_log/record")
    validators = {
        DATASET_POISSON: Draft202012Validator(poisson_schema),
        DATASET_ZTP_REJECTION: Draft202012Validator(rejection_schema),
        DATASET_ZTP_RETRY: Draft202012Validator(retry_schema),
        DATASET_ZTP_FINAL: Draft202012Validator(final_schema),
        DATASET_TRACE: Draft202012Validator(trace_schema),
    }

    poisson_entry = find_dataset_entry(dictionary, DATASET_POISSON).entry
    poisson_paths = _resolve_run_glob(run_paths, poisson_entry["path"], tokens)

    rejection_entry = find_dataset_entry(dictionary, DATASET_ZTP_REJECTION).entry
    rejection_paths = [
        path
        for path in _resolve_run_glob(run_paths, rejection_entry["path"], tokens)
        if path.exists()
    ]

    retry_entry = find_dataset_entry(dictionary, DATASET_ZTP_RETRY).entry
    retry_paths = [
        path
        for path in _resolve_run_glob(run_paths, retry_entry["path"], tokens)
        if path.exists()
    ]

    final_entry = find_dataset_entry(dictionary, DATASET_ZTP_FINAL).entry
    final_paths = [
        path
        for path in _resolve_run_glob(run_paths, final_entry["path"], tokens)
        if path.exists()
    ]

    trace_entry = find_dataset_entry(dictionary, DATASET_TRACE).entry
    trace_path = _resolve_run_path(run_paths, trace_entry["path"], tokens)

    merchants: dict[int, dict[str, list[dict]]] = {}
    blocks_total = 0
    draws_total = 0
    event_total = 0

    def _get_bucket(merchant_id: int) -> dict[str, list[dict]]:
        return merchants.setdefault(
            merchant_id,
            {"poisson": [], "rejection": [], "retry": [], "final": []},
        )

    def _schema_check(dataset_id: str, payload: dict, path: Path, line_no: int) -> None:
        errors = list(validators[dataset_id].iter_errors(payload))
        if errors:
            raise EngineFailure(
                "F4",
                "schema_violation",
                "S4",
                MODULE_NAME,
                {
                    "path": path.as_posix(),
                    "line": line_no,
                    "detail": errors[0].message,
                },
                dataset_id=dataset_id,
            )

    def _lineage_check(payload: dict, path: Path, line_no: int, dataset_id: str) -> None:
        if (
            payload.get("seed") != seed
            or payload.get("parameter_hash") != parameter_hash
            or payload.get("run_id") != run_id
        ):
            raise EngineFailure(
                "F4",
                "PARTITION_MISMATCH",
                "S4",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no},
                dataset_id=dataset_id,
            )

    def _validate_consuming(payload: dict, dataset_id: str) -> None:
        before = (int(payload["rng_counter_before_hi"]) << 64) | int(
            payload["rng_counter_before_lo"]
        )
        after = (int(payload["rng_counter_after_hi"]) << 64) | int(
            payload["rng_counter_after_lo"]
        )
        blocks = int(payload["blocks"])
        draws = int(payload["draws"])
        if after < before or blocks != after - before or draws <= 0:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="RNG_ACCOUNTING",
                scope="merchant",
                reason="consuming_mismatch",
                merchant_id=int(payload.get("merchant_id", 0)),
                attempts=payload.get("attempt"),
                lambda_extra=payload.get("lambda") or payload.get("lambda_extra"),
            )
            raise EngineFailure(
                "F4",
                "RNG_ACCOUNTING",
                "S4",
                MODULE_NAME,
                {"detail": "consuming_mismatch"},
                dataset_id=dataset_id,
            )

    def _validate_nonconsuming(payload: dict, dataset_id: str) -> None:
        before = (int(payload["rng_counter_before_hi"]) << 64) | int(
            payload["rng_counter_before_lo"]
        )
        after = (int(payload["rng_counter_after_hi"]) << 64) | int(
            payload["rng_counter_after_lo"]
        )
        blocks = int(payload["blocks"])
        draws = str(payload["draws"])
        if before != after or blocks != 0 or draws != "0":
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="RNG_ACCOUNTING",
                scope="merchant",
                reason="nonconsuming_mismatch",
                merchant_id=int(payload.get("merchant_id", 0)),
                attempts=payload.get("attempt") or payload.get("attempts"),
                lambda_extra=payload.get("lambda_extra"),
            )
            raise EngineFailure(
                "F4",
                "RNG_ACCOUNTING",
                "S4",
                MODULE_NAME,
                {"detail": "nonconsuming_mismatch"},
                dataset_id=dataset_id,
            )

    for path, line_no, payload in _iter_jsonl_files(poisson_paths):
        if payload.get("context") != CONTEXT:
            continue
        if payload.get("module") != MODULE_NAME:
            raise EngineFailure(
                "F4",
                "UNKNOWN_CONTEXT",
                "S4",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no},
                dataset_id=DATASET_POISSON,
            )
        if payload.get("substream_label") != SUBSTREAM_LABEL:
            raise EngineFailure(
                "F4",
                "UNKNOWN_CONTEXT",
                "S4",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no},
                dataset_id=DATASET_POISSON,
            )
        _schema_check(DATASET_POISSON, payload, path, line_no)
        _lineage_check(payload, path, line_no, DATASET_POISSON)
        _validate_consuming(payload, DATASET_POISSON)
        merchant_id = int(payload["merchant_id"])
        _get_bucket(merchant_id)["poisson"].append(payload)
        blocks_total = _checked_add(blocks_total, int(payload["blocks"]))
        draws_total = _checked_add(draws_total, int(payload["draws"]))
        event_total = _checked_add(event_total, 1)

    for path, line_no, payload in _iter_jsonl_files(rejection_paths):
        _schema_check(DATASET_ZTP_REJECTION, payload, path, line_no)
        _lineage_check(payload, path, line_no, DATASET_ZTP_REJECTION)
        _validate_nonconsuming(payload, DATASET_ZTP_REJECTION)
        merchant_id = int(payload["merchant_id"])
        _get_bucket(merchant_id)["rejection"].append(payload)
        event_total = _checked_add(event_total, 1)

    for path, line_no, payload in _iter_jsonl_files(retry_paths):
        _schema_check(DATASET_ZTP_RETRY, payload, path, line_no)
        _lineage_check(payload, path, line_no, DATASET_ZTP_RETRY)
        _validate_nonconsuming(payload, DATASET_ZTP_RETRY)
        merchant_id = int(payload["merchant_id"])
        _get_bucket(merchant_id)["retry"].append(payload)
        event_total = _checked_add(event_total, 1)

    for path, line_no, payload in _iter_jsonl_files(final_paths):
        _schema_check(DATASET_ZTP_FINAL, payload, path, line_no)
        _lineage_check(payload, path, line_no, DATASET_ZTP_FINAL)
        _validate_nonconsuming(payload, DATASET_ZTP_FINAL)
        merchant_id = int(payload["merchant_id"])
        _get_bucket(merchant_id)["final"].append(payload)
        event_total = _checked_add(event_total, 1)

    trace_rows = []
    if trace_path.exists():
        for path, line_no, payload in _iter_jsonl_files([trace_path]):
            _schema_check(DATASET_TRACE, payload, path, line_no)
            if payload.get("module") != MODULE_NAME:
                continue
            if payload.get("substream_label") != SUBSTREAM_LABEL:
                continue
            if payload.get("seed") != seed or payload.get("run_id") != run_id:
                continue
            trace_rows.append(payload)

    if event_total > 0 and not trace_rows:
        _log_failure_line(
            logger,
            seed,
            parameter_hash,
            run_id,
            manifest_fingerprint,
            code="TRACE_MISSING",
            scope="run",
            reason="trace_absent",
        )
        raise EngineFailure("F4", "TRACE_MISSING", "S4", MODULE_NAME, "trace_absent")

    if trace_rows and int(trace_rows[-1]["events_total"]) != len(trace_rows):
        _log_failure_line(
            logger,
            seed,
            parameter_hash,
            run_id,
            manifest_fingerprint,
            code="TRACE_MISSING",
            scope="run",
            reason="trace_events_total_mismatch",
        )
        raise EngineFailure(
            "F4", "TRACE_MISSING", "S4", MODULE_NAME, "trace_events_total_mismatch"
        )

    if trace_rows and int(trace_rows[-1]["events_total"]) != event_total:
        _log_failure_line(
            logger,
            seed,
            parameter_hash,
            run_id,
            manifest_fingerprint,
            code="TRACE_MISSING",
            scope="run",
            reason="trace_count_mismatch",
        )
        raise EngineFailure(
            "F4", "TRACE_MISSING", "S4", MODULE_NAME, "trace_count_mismatch"
        )

    if trace_rows:
        expected_blocks = blocks_total
        expected_draws = draws_total
        last = trace_rows[-1]
        if int(last["blocks_total"]) != expected_blocks or int(last["draws_total"]) != expected_draws:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="TRACE_MISSING",
                scope="run",
                reason="trace_totals_mismatch",
            )
            raise EngineFailure(
                "F4", "TRACE_MISSING", "S4", MODULE_NAME, "trace_totals_mismatch"
            )

    scope_set = set(scope_merchants)
    for merchant_id in merchants:
        if merchant_id not in scope_set:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="BRANCH_PURITY",
                scope="merchant",
                reason="event_for_out_of_scope",
                merchant_id=merchant_id,
            )
            raise EngineFailure(
                "F4", "BRANCH_PURITY", "S4", MODULE_NAME, "event_for_out_of_scope"
            )

    for merchant_id in scope_merchants:
        if merchant_id not in hurdle_map:
            continue
        if not hurdle_map.get(merchant_id, False):
            continue
        if not eligibility_map.get(merchant_id, False):
            continue

        nb_event = nb_final_map.get(merchant_id)
        if nb_event is None or int(nb_event.get("n_outlets", 0)) < 2:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="UPSTREAM_MISSING_S2",
                scope="merchant",
                reason="missing_nb_final",
                merchant_id=merchant_id,
            )
            raise EngineFailure(
                "F4", "UPSTREAM_MISSING_S2", "S4", MODULE_NAME, "missing_nb_final"
            )

        bucket = merchants.get(merchant_id, {"poisson": [], "rejection": [], "retry": [], "final": []})
        poisson_events = bucket["poisson"]
        rejection_events = bucket["rejection"]
        retry_events = bucket["retry"]
        final_events = bucket["final"]

        a_value = a_map.get(merchant_id)
        if a_value is None or home_map.get(merchant_id, 0) < 1:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="UPSTREAM_MISSING_A",
                scope="merchant",
                reason="missing_candidate_set",
                merchant_id=merchant_id,
            )
            raise EngineFailure(
                "F4", "UPSTREAM_MISSING_A", "S4", MODULE_NAME, "missing_candidate_set"
            )

        if int(a_value) == 0:
            if poisson_events or rejection_events or retry_events:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="A_ZERO_MISSHANDLED",
                    scope="merchant",
                    reason="attempts_present",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "A_ZERO_MISSHANDLED", "S4", MODULE_NAME, "attempts_present"
                )
            if len(final_events) != 1:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="FINAL_MISSING",
                    scope="merchant",
                    reason="final_missing",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "FINAL_MISSING", "S4", MODULE_NAME, "final_missing"
                )
            final_event = final_events[0]
            if int(final_event.get("K_target", -1)) != 0 or int(final_event.get("attempts", -1)) != 0:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="A_ZERO_MISSHANDLED",
                    scope="merchant",
                    reason="final_values_invalid",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "A_ZERO_MISSHANDLED", "S4", MODULE_NAME, "final_values_invalid"
                )
            continue

        if not poisson_events:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="ATTEMPT_GAPS",
                scope="merchant",
                reason="missing_poisson",
                merchant_id=merchant_id,
            )
            raise EngineFailure(
                "F4", "ATTEMPT_GAPS", "S4", MODULE_NAME, "missing_poisson"
            )

        poisson_events = sorted(poisson_events, key=lambda row: int(row["attempt"]))
        attempts = [int(row["attempt"]) for row in poisson_events]
        if attempts != list(range(1, max(attempts) + 1)):
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="ATTEMPT_GAPS",
                scope="merchant",
                reason="attempt_sequence_invalid",
                merchant_id=merchant_id,
            )
            raise EngineFailure(
                "F4", "ATTEMPT_GAPS", "S4", MODULE_NAME, "attempt_sequence_invalid"
            )

        if len(set(attempts)) != len(attempts):
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="ATTEMPT_GAPS",
                scope="merchant",
                reason="duplicate_attempts",
                merchant_id=merchant_id,
            )
            raise EngineFailure(
                "F4", "ATTEMPT_GAPS", "S4", MODULE_NAME, "duplicate_attempts"
            )

        rejection_attempts = [int(row["attempt"]) for row in rejection_events]
        if len(set(rejection_attempts)) != len(rejection_attempts):
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="ATTEMPT_GAPS",
                scope="merchant",
                reason="duplicate_rejections",
                merchant_id=merchant_id,
            )
            raise EngineFailure(
                "F4", "ATTEMPT_GAPS", "S4", MODULE_NAME, "duplicate_rejections"
            )

        retry_attempts = [int(row["attempts"]) for row in retry_events]
        if len(retry_attempts) > 1:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="ATTEMPT_GAPS",
                scope="merchant",
                reason="multiple_retry",
                merchant_id=merchant_id,
            )
            raise EngineFailure(
                "F4", "ATTEMPT_GAPS", "S4", MODULE_NAME, "multiple_retry"
            )

        final_attempts = [int(row["attempts"]) for row in final_events]
        if len(final_attempts) > 1:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="MULTIPLE_FINAL",
                scope="merchant",
                reason="multiple_final",
                merchant_id=merchant_id,
            )
            raise EngineFailure(
                "F4", "MULTIPLE_FINAL", "S4", MODULE_NAME, "multiple_final"
            )

        lambda_values = {float(row["lambda"]) for row in poisson_events}
        lambda_values |= {float(row["lambda_extra"]) for row in rejection_events}
        lambda_values |= {float(row["lambda_extra"]) for row in retry_events}
        lambda_values |= {float(row["lambda_extra"]) for row in final_events}
        if len(lambda_values) != 1:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="POLICY_INVALID",
                scope="merchant",
                reason="lambda_mismatch",
                merchant_id=merchant_id,
            )
            raise EngineFailure(
                "F4", "POLICY_INVALID", "S4", MODULE_NAME, "lambda_mismatch"
            )
        lambda_extra = next(iter(lambda_values))
        expected_regime = "inversion" if lambda_extra < 10.0 else "ptrs"

        k_by_attempt = {int(row["attempt"]): int(row["k"]) for row in poisson_events}
        max_attempt = max(attempts)
        for attempt in rejection_attempts:
            if attempt not in k_by_attempt:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="ATTEMPT_GAPS",
                    scope="merchant",
                    reason="rejection_without_attempt",
                    merchant_id=merchant_id,
                    attempts=attempt,
                )
                raise EngineFailure(
                    "F4", "ATTEMPT_GAPS", "S4", MODULE_NAME, "rejection_without_attempt"
                )
        if max_attempt > max_attempts:
            _log_failure_line(
                logger,
                seed,
                parameter_hash,
                run_id,
                manifest_fingerprint,
                code="ATTEMPT_GAPS",
                scope="merchant",
                reason="attempts_exceed_cap",
                merchant_id=merchant_id,
            )
            raise EngineFailure(
                "F4", "ATTEMPT_GAPS", "S4", MODULE_NAME, "attempts_exceed_cap"
            )

        if any(k_by_attempt[attempt] == 0 for attempt in attempts):
            for attempt in attempts:
                if k_by_attempt[attempt] == 0 and attempt not in rejection_attempts:
                    _log_failure_line(
                        logger,
                        seed,
                        parameter_hash,
                        run_id,
                        manifest_fingerprint,
                        code="ATTEMPT_GAPS",
                        scope="merchant",
                        reason="missing_rejection",
                        merchant_id=merchant_id,
                        attempts=attempt,
                    )
                    raise EngineFailure(
                        "F4", "ATTEMPT_GAPS", "S4", MODULE_NAME, "missing_rejection"
                    )
                if k_by_attempt[attempt] > 0 and attempt in rejection_attempts:
                    _log_failure_line(
                        logger,
                        seed,
                        parameter_hash,
                        run_id,
                        manifest_fingerprint,
                        code="ATTEMPT_GAPS",
                        scope="merchant",
                        reason="rejection_after_accept",
                        merchant_id=merchant_id,
                        attempts=attempt,
                    )
                    raise EngineFailure(
                        "F4", "ATTEMPT_GAPS", "S4", MODULE_NAME, "rejection_after_accept"
                    )

        accepted_attempt = None
        accepted_k = None
        for attempt in attempts:
            if k_by_attempt[attempt] >= 1:
                accepted_attempt = attempt
                accepted_k = k_by_attempt[attempt]
                break

        if accepted_attempt is not None:
            if accepted_attempt != max_attempt:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="ATTEMPT_GAPS",
                    scope="merchant",
                    reason="attempts_after_accept",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "ATTEMPT_GAPS", "S4", MODULE_NAME, "attempts_after_accept"
                )
            if retry_events:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="CAP_WITH_FINAL_ABORT",
                    scope="merchant",
                    reason="retry_with_final",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "CAP_WITH_FINAL_ABORT", "S4", MODULE_NAME, "retry_with_final"
                )
            if not final_events:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="FINAL_MISSING",
                    scope="merchant",
                    reason="final_missing",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "FINAL_MISSING", "S4", MODULE_NAME, "final_missing"
                )
            final_event = final_events[0]
            if int(final_event.get("K_target", -1)) != int(accepted_k):
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="FINAL_MISSING",
                    scope="merchant",
                    reason="final_k_mismatch",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "FINAL_MISSING", "S4", MODULE_NAME, "final_k_mismatch"
                )
            if int(final_event.get("attempts", -1)) != int(accepted_attempt):
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="FINAL_MISSING",
                    scope="merchant",
                    reason="final_attempt_mismatch",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "FINAL_MISSING", "S4", MODULE_NAME, "final_attempt_mismatch"
                )
            regime = final_event.get("regime")
            if regime != expected_regime:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="REGIME_INVALID",
                    scope="merchant",
                    reason="regime_mismatch",
                    merchant_id=merchant_id,
                    lambda_extra=lambda_extra,
                    regime=regime,
                )
                raise EngineFailure(
                    "F4", "REGIME_INVALID", "S4", MODULE_NAME, "regime_mismatch"
                )
            if "exhausted" in final_event and final_event.get("exhausted"):
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="CAP_WITH_FINAL_ABORT",
                    scope="merchant",
                    reason="exhausted_on_accept",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "CAP_WITH_FINAL_ABORT", "S4", MODULE_NAME, "exhausted_on_accept"
                )
            continue

        if retry_events:
            retry_event = retry_events[0]
            if exhaustion_policy != "abort":
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="CAP_WITH_FINAL_ABORT",
                    scope="merchant",
                    reason="retry_with_downgrade",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "CAP_WITH_FINAL_ABORT", "S4", MODULE_NAME, "retry_with_downgrade"
                )
            if final_events:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="CAP_WITH_FINAL_ABORT",
                    scope="merchant",
                    reason="final_with_retry",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "CAP_WITH_FINAL_ABORT", "S4", MODULE_NAME, "final_with_retry"
                )
            if int(retry_event.get("attempts", -1)) != max_attempt:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="ZTP_EXHAUSTED_ABORT",
                    scope="merchant",
                    reason="retry_attempt_mismatch",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "ZTP_EXHAUSTED_ABORT", "S4", MODULE_NAME, "retry_attempt_mismatch"
                )
            continue

        if exhaustion_policy == "downgrade_domestic":
            if not final_events:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="FINAL_MISSING",
                    scope="merchant",
                    reason="final_missing_downgrade",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "FINAL_MISSING", "S4", MODULE_NAME, "final_missing_downgrade"
                )
            final_event = final_events[0]
            if int(final_event.get("K_target", -1)) != 0:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="FINAL_MISSING",
                    scope="merchant",
                    reason="downgrade_k_mismatch",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "FINAL_MISSING", "S4", MODULE_NAME, "downgrade_k_mismatch"
                )
            if int(final_event.get("attempts", -1)) != max_attempt:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="FINAL_MISSING",
                    scope="merchant",
                    reason="downgrade_attempt_mismatch",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "FINAL_MISSING", "S4", MODULE_NAME, "downgrade_attempt_mismatch"
                )
            if not final_event.get("exhausted", False):
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="CAP_WITH_FINAL_ABORT",
                    scope="merchant",
                    reason="downgrade_missing_exhausted",
                    merchant_id=merchant_id,
                )
                raise EngineFailure(
                    "F4", "CAP_WITH_FINAL_ABORT", "S4", MODULE_NAME, "downgrade_missing_exhausted"
                )
            if final_event.get("regime") != expected_regime:
                _log_failure_line(
                    logger,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    code="REGIME_INVALID",
                    scope="merchant",
                    reason="regime_mismatch_downgrade",
                    merchant_id=merchant_id,
                    lambda_extra=lambda_extra,
                    regime=final_event.get("regime"),
                )
                raise EngineFailure(
                    "F4", "REGIME_INVALID", "S4", MODULE_NAME, "regime_mismatch_downgrade"
                )

    logger.info("S4: validation passed")


__all__ = ["S4RunResult", "run_s4"]
