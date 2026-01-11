"""S1 hurdle sampler runner for Segment 1A."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import polars as pl
import yaml

from engine.contracts.loader import (
    find_dataset_entry,
    load_artefact_registry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import ContractError, InputResolutionError
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_1A.s1_hurdle.rng import (
    UINT64_MAX,
    add_u128,
    derive_master_material,
    derive_substream,
    merchant_u64,
    philox2x64_10,
    u01,
)


MODULE_NAME = "1A.hurdle_sampler"
SUBSTREAM_LABEL = "hurdle_bernoulli"
CHANNEL_MAP = {"card_present": "CP", "card_not_present": "CNP"}


@dataclass(frozen=True)
class S1RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    event_path: Path
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


def _resolve_registry_path(path_template: str, repo_root: Path) -> Path:
    if "{" not in path_template:
        return repo_root / path_template
    pattern = path_template
    for token in (
        "{config_version}",
        "{policy_version}",
        "{iso8601_timestamp}",
        "{version}",
    ):
        if token in pattern:
            pattern = pattern.replace(token, "*")
    matches = sorted(repo_root.glob(pattern))
    matches = [path for path in matches if path.exists()]
    if not matches:
        raise InputResolutionError(
            f"No files match registry path template: {path_template}"
        )
    resolved = matches[-1]
    if resolved.is_dir():
        parquet_files = sorted(resolved.glob("*.parquet"))
        if len(parquet_files) == 1:
            return parquet_files[0]
        files = sorted([path for path in resolved.iterdir() if path.is_file()])
        if len(files) == 1:
            return files[0]
        raise InputResolutionError(
            f"Registry path template resolved to directory with multiple files: {resolved}"
        )
    return resolved


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


def _resolve_run_path(
    run_paths: RunPaths, path_template: str, tokens: dict[str, str]
) -> Path:
    path = path_template
    for key, value in tokens.items():
        path = path.replace(f"{{{key}}}", value)
    return run_paths.run_root / path


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


def _require_rng_audit(audit_path: Path, seed: int, parameter_hash: str, run_id: str) -> None:
    if not audit_path.exists():
        raise InputResolutionError(f"Missing rng_audit_log: {audit_path}")
    with audit_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if (
                payload.get("seed") == seed
                and payload.get("parameter_hash") == parameter_hash
                and payload.get("run_id") == run_id
            ):
                return
    raise InputResolutionError(
        "rng_audit_log missing required audit row for "
        f"seed={seed} parameter_hash={parameter_hash} run_id={run_id}"
    )


def _ensure_trace_clear(trace_path: Path) -> None:
    if not trace_path.exists():
        return
    with trace_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if (
                payload.get("module") == MODULE_NAME
                and payload.get("substream_label") == SUBSTREAM_LABEL
            ):
                raise InputResolutionError(
                    "rng_trace_log already has hurdle entries for this run; "
                    "refusing to append duplicate substream entries."
                )


def _ensure_event_path_clear(event_path: Path) -> None:
    if event_path.exists():
        raise InputResolutionError(f"Hurdle event output already exists: {event_path}")
    parent = event_path.parent
    if parent.exists():
        existing = list(parent.glob("*.jsonl"))
        if existing:
            raise InputResolutionError(
                f"Hurdle event directory already contains files: {parent}"
            )


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


def _logistic(eta: float) -> float:
    if eta >= 0.0:
        z = math.exp(-eta)
        return 1.0 / (1.0 + z)
    z = math.exp(eta)
    return z / (1.0 + z)


class _TraceAccumulator:
    def __init__(self) -> None:
        self.draws_total = 0
        self.blocks_total = 0
        self.events_total = 0

    def append(self, event: dict) -> dict:
        draws = int(event["draws"])
        blocks = int(event["blocks"])
        self.draws_total = _checked_add(self.draws_total, draws)
        self.blocks_total = _checked_add(self.blocks_total, blocks)
        self.events_total = _checked_add(self.events_total, 1)
        return {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": event["run_id"],
            "seed": event["seed"],
            "module": event["module"],
            "substream_label": event["substream_label"],
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
        raise InputResolutionError("rng_trace_log counters exceeded uint64 range.")
    return total


def _load_coefficients(path: Path) -> tuple[dict, list[float]]:
    payload = _load_yaml(path)
    dict_mcc = payload.get("dict_mcc")
    dict_ch = payload.get("dict_ch")
    dict_dev5 = payload.get("dict_dev5")
    beta = payload.get("beta")
    if not isinstance(dict_mcc, list) or not isinstance(dict_ch, list) or not isinstance(dict_dev5, list):
        raise InputResolutionError("Malformed hurdle_coefficients: missing dict_mcc/dict_ch/dict_dev5.")
    if dict_ch != ["CP", "CNP"]:
        raise InputResolutionError(f"Unexpected dict_ch ordering: {dict_ch}")
    if dict_dev5 != [1, 2, 3, 4, 5]:
        raise InputResolutionError(f"Unexpected dict_dev5 ordering: {dict_dev5}")
    if not isinstance(beta, list):
        raise InputResolutionError("Malformed hurdle_coefficients: missing beta list.")
    expected_len = 1 + len(dict_mcc) + len(dict_ch) + len(dict_dev5)
    if len(beta) != expected_len:
        raise InputResolutionError(
            f"Hurdle beta length mismatch: expected {expected_len}, got {len(beta)}"
        )
    return {
        "dict_mcc": [int(value) for value in dict_mcc],
        "dict_ch": [str(value) for value in dict_ch],
        "dict_dev5": [int(value) for value in dict_dev5],
    }, [float(value) for value in beta]


def run_s1(config: EngineConfig, run_id: Optional[str] = None) -> S1RunResult:
    logger = get_logger("engine.s1")
    timer = _StepTimer(logger)
    timer.info("S1: run initialised")
    source = ContractSource(root=config.contracts_root, layout=config.contracts_layout)
    dictionary_path, dictionary = load_dataset_dictionary(source, "1A")
    registry_path, registry = load_artefact_registry(source, "1A")
    load_schema_pack(source, "1A", "1A")
    load_schema_pack(source, "1A", "layer1")

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = receipt.get("run_id")
    if not run_id:
        raise InputResolutionError("run_receipt missing run_id.")
    if receipt_path.parent.name != run_id:
        raise InputResolutionError("run_receipt path does not match embedded run_id.")

    seed = int(receipt.get("seed"))
    parameter_hash = receipt.get("parameter_hash")
    manifest_fingerprint = receipt.get("manifest_fingerprint")
    if not parameter_hash or not manifest_fingerprint:
        raise InputResolutionError("run_receipt missing parameter_hash or manifest_fingerprint.")
    if seed < 0 or seed > UINT64_MAX:
        raise InputResolutionError(f"run_receipt seed out of uint64 range: {seed}")

    run_paths = RunPaths(config.runs_root, run_id)
    add_file_handler(run_paths.run_root / f"run_log_{run_id}.log")
    timer.info(f"S1: loaded run receipt {receipt_path}")

    tokens = {
        "seed": str(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "run_id": run_id,
    }

    gate_entry = find_dataset_entry(dictionary, "s0_gate_receipt_1A").entry
    gate_path = _resolve_run_path(run_paths, gate_entry["path"], tokens)
    gate_receipt = _load_json(gate_path)
    if gate_receipt.get("manifest_fingerprint") != manifest_fingerprint:
        raise InputResolutionError("s0_gate_receipt manifest_fingerprint mismatch.")
    if gate_receipt.get("parameter_hash") != parameter_hash:
        raise InputResolutionError("s0_gate_receipt parameter_hash mismatch.")
    if gate_receipt.get("run_id") != run_id:
        raise InputResolutionError("s0_gate_receipt run_id mismatch.")
    sealed_ids = {item.get("id") for item in gate_receipt.get("sealed_inputs", [])}
    if "hurdle_coefficients.yaml" not in sealed_ids:
        raise InputResolutionError("s0_gate_receipt missing hurdle_coefficients.yaml in sealed_inputs.")

    audit_entry = find_dataset_entry(dictionary, "rng_audit_log").entry
    audit_path = _resolve_run_path(run_paths, audit_entry["path"], tokens)
    _require_rng_audit(audit_path, seed, parameter_hash, run_id)
    timer.info("S1: rng_audit_log verified")

    trace_entry = find_dataset_entry(dictionary, "rng_trace_log").entry
    trace_path = _resolve_run_path(run_paths, trace_entry["path"], tokens)
    _ensure_trace_clear(trace_path)

    event_entry = find_dataset_entry(dictionary, "rng_event_hurdle_bernoulli").entry
    event_path = _resolve_event_path(run_paths, event_entry["path"], tokens)
    _ensure_event_path_clear(event_path)

    design_entry = find_dataset_entry(dictionary, "hurdle_design_matrix").entry
    design_root = _resolve_run_path(run_paths, design_entry["path"], {"parameter_hash": parameter_hash})
    design_path = _select_dataset_file("hurdle_design_matrix", design_root)
    design_df = pl.read_parquet(
        design_path,
        columns=["merchant_id", "mcc", "channel", "gdp_bucket_id", "intercept"],
    )
    if set(design_df.columns) != {
        "merchant_id",
        "mcc",
        "channel",
        "gdp_bucket_id",
        "intercept",
    }:
        raise InputResolutionError("hurdle_design_matrix missing required columns.")
    intercept_bad = design_df.filter(pl.col("intercept") != 1.0)
    if intercept_bad.height > 0:
        raise InputResolutionError("hurdle_design_matrix intercept column is not all 1.0.")
    unique_count = design_df.select(pl.col("merchant_id").n_unique()).to_series()[0]
    if unique_count != design_df.height:
        raise InputResolutionError("hurdle_design_matrix merchant_id is not unique.")
    timer.info(f"S1: loaded hurdle_design_matrix rows={design_df.height}")

    registry_entry = None
    for subsegment in registry.get("subsegments", []):
        for artifact in subsegment.get("artifacts", []):
            if artifact.get("name") == "hurdle_coefficients":
                registry_entry = artifact
                break
    if registry_entry is None:
        raise ContractError("Registry entry not found: hurdle_coefficients")
    coeff_path = _resolve_registry_path(registry_entry["path"], config.repo_root)
    coeff_meta, beta = _load_coefficients(coeff_path)
    dict_mcc = coeff_meta["dict_mcc"]
    dict_ch = coeff_meta["dict_ch"]
    dict_dev5 = coeff_meta["dict_dev5"]

    mcc_index = {value: idx for idx, value in enumerate(dict_mcc)}
    ch_index = {value: idx for idx, value in enumerate(dict_ch)}
    dev_index = {value: idx for idx, value in enumerate(dict_dev5)}

    offset_mcc = 1
    offset_ch = offset_mcc + len(dict_mcc)
    offset_dev = offset_ch + len(dict_ch)

    beta_intercept = beta[0]
    beta_mcc = {value: beta[offset_mcc + idx] for value, idx in mcc_index.items()}
    beta_ch = {value: beta[offset_ch + idx] for value, idx in ch_index.items()}
    beta_dev = {value: beta[offset_dev + idx] for value, idx in dev_index.items()}

    master_material = derive_master_material(bytes.fromhex(manifest_fingerprint), seed)

    tmp_dir = run_paths.tmp_root / "s1_hurdle"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_event_path = tmp_dir / "rng_event_hurdle_bernoulli.jsonl"
    tmp_trace_path = tmp_dir / "rng_trace_log_hurdle.jsonl"

    trace_acc = _TraceAccumulator()
    row_count = design_df.height
    progress_every = max(1, min(10_000, row_count // 10 if row_count else 1))
    timer.info(f"S1: emitting hurdle events (progress_every={progress_every})")

    with tmp_event_path.open("w", encoding="utf-8") as event_handle, tmp_trace_path.open(
        "w", encoding="utf-8"
    ) as trace_handle:
        for idx, row in enumerate(design_df.iter_rows(named=True), start=1):
            merchant_id = int(row["merchant_id"])
            mcc = int(row["mcc"])
            channel = row["channel"]
            gdp_bucket = int(row["gdp_bucket_id"])

            channel_sym = CHANNEL_MAP.get(channel)
            if channel_sym is None:
                raise InputResolutionError(f"Unknown channel value: {channel}")
            if mcc not in beta_mcc:
                raise InputResolutionError(f"Unknown MCC in hurdle coefficients: {mcc}")
            if channel_sym not in beta_ch:
                raise InputResolutionError(f"Unknown channel symbol in coefficients: {channel_sym}")
            if gdp_bucket not in beta_dev:
                raise InputResolutionError(f"Unknown GDP bucket id in coefficients: {gdp_bucket}")

            eta = _neumaier_sum(
                (
                    beta_intercept,
                    beta_mcc[mcc],
                    beta_ch[channel_sym],
                    beta_dev[gdp_bucket],
                )
            )
            if not math.isfinite(eta):
                raise InputResolutionError(f"Non-finite eta for merchant_id={merchant_id}")
            pi = _logistic(eta)
            if not math.isfinite(pi) or pi < 0.0 or pi > 1.0:
                raise InputResolutionError(
                    f"Non-finite or out-of-range pi for merchant_id={merchant_id}"
                )

            deterministic = pi == 0.0 or pi == 1.0
            key, ctr_hi, ctr_lo = derive_substream(
                master_material, SUBSTREAM_LABEL, merchant_u64(merchant_id)
            )
            if deterministic:
                u = None
                draws = "0"
                blocks = 0
                after_hi, after_lo = ctr_hi, ctr_lo
                is_multi = pi == 1.0
            else:
                x0, _x1 = philox2x64_10(ctr_hi, ctr_lo, key)
                u = u01(x0)
                if not (0.0 < u < 1.0):
                    raise InputResolutionError(
                        f"Uniform out of open interval for merchant_id={merchant_id}"
                    )
                draws = "1"
                blocks = 1
                after_hi, after_lo = add_u128(ctr_hi, ctr_lo, 1)
                is_multi = u < pi

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
                "draws": draws,
                "blocks": blocks,
                "merchant_id": merchant_id,
                "pi": pi,
                "is_multi": is_multi,
                "deterministic": deterministic,
                "u": u,
            }
            trace = trace_acc.append(event)

            event_handle.write(json.dumps(event, ensure_ascii=True, sort_keys=True))
            event_handle.write("\n")
            trace_handle.write(json.dumps(trace, ensure_ascii=True, sort_keys=True))
            trace_handle.write("\n")

            if idx % progress_every == 0 or idx == row_count:
                logger.info("S1: emitted hurdle events %d/%d", idx, row_count)

    event_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_event_path.replace(event_path)

    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as dest_handle, tmp_trace_path.open(
        "r", encoding="utf-8"
    ) as src_handle:
        for line in src_handle:
            dest_handle.write(line)
    tmp_trace_path.unlink(missing_ok=True)

    timer.info("S1: hurdle events + trace emitted")
    logger.info(
        "S1 complete: run_id=%s parameter_hash=%s manifest_fingerprint=%s rows=%d",
        run_id,
        parameter_hash,
        manifest_fingerprint,
        row_count,
    )
    return S1RunResult(
        run_id=run_id,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        event_path=event_path,
        trace_path=trace_path,
    )
