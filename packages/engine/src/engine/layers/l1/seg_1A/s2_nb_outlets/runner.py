"""S2 NB outlets sampler runner for Segment 1A."""

from __future__ import annotations

import datetime as dt
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


MODULE_GAMMA = "1A.nb_and_dirichlet_sampler"
MODULE_POISSON = "1A.nb_poisson_component"
MODULE_FINAL = "1A.nb_sampler"
SUBSTREAM_GAMMA = "gamma_nb"
SUBSTREAM_POISSON = "poisson_nb"
SUBSTREAM_FINAL = "nb_final"

DATASET_GAMMA = "rng_event_gamma_component"
DATASET_POISSON = "rng_event_poisson_component"
DATASET_FINAL = "rng_event_nb_final"
DATASET_HURDLE = "rng_event_hurdle_bernoulli"
TRACE_DATASET_ID = "rng_trace_log"

CHANNEL_MAP = {"card_present": "CP", "card_not_present": "CNP"}
TAU = float.fromhex("0x1.921fb54442d18p+2")
_DATE_VERSION_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class S2RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    gamma_path: Path
    poisson_path: Path
    nb_final_path: Path


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


def _ensure_event_path_clear(event_path: Path) -> None:
    if event_path.exists():
        raise InputResolutionError(f"Event output already exists: {event_path}")
    parent = event_path.parent
    if parent.exists():
        existing = list(parent.glob("*.jsonl"))
        if existing:
            raise InputResolutionError(
                f"Event directory already contains files: {parent}"
            )


def _event_has_rows(event_path: Path) -> bool:
    if event_path.exists():
        return True
    parent = event_path.parent
    if not parent.exists():
        return False
    return any(parent.glob("*.jsonl"))


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
        self._max_after_hi: int | None = None
        self._max_after_lo: int | None = None
        self._max_before_hi: int | None = None
        self._max_before_lo: int | None = None

    def append(self, event: dict) -> dict:
        if self._run_id is None:
            self._run_id = event["run_id"]
            self._seed = int(event["seed"])
        draws = int(event["draws"])
        blocks = int(event["blocks"])
        self.draws_total = _checked_add(self.draws_total, draws)
        self.blocks_total = _checked_add(self.blocks_total, blocks)
        self.events_total = _checked_add(self.events_total, 1)
        after_hi = int(event["rng_counter_after_hi"])
        after_lo = int(event["rng_counter_after_lo"])
        if self._max_after_hi is None or (after_hi, after_lo) > (
            self._max_after_hi,
            self._max_after_lo,
        ):
            self._max_after_hi = after_hi
            self._max_after_lo = after_lo
            self._max_before_hi = int(event["rng_counter_before_hi"])
            self._max_before_lo = int(event["rng_counter_before_lo"])
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

    def finalize(self) -> dict | None:
        if self.events_total == 0 or self._max_after_hi is None:
            return None
        return {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": self._run_id,
            "seed": self._seed,
            "module": self._module,
            "substream_label": self._substream_label,
            "rng_counter_before_lo": self._max_before_lo,
            "rng_counter_before_hi": self._max_before_hi,
            "rng_counter_after_lo": self._max_after_lo,
            "rng_counter_after_hi": self._max_after_hi,
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


def _load_hurdle_coefficients(path: Path) -> tuple[dict, list[float]]:
    payload = _load_yaml(path)
    dict_mcc = payload.get("dict_mcc")
    dict_ch = payload.get("dict_ch")
    beta_mu = payload.get("beta_mu")
    if not isinstance(dict_mcc, list) or not isinstance(dict_ch, list):
        raise EngineFailure(
            "F3",
            "column_order_mismatch",
            "S2",
            MODULE_GAMMA,
            {"path": path.as_posix(), "detail": "missing_dict_blocks"},
            dataset_id="hurdle_coefficients",
        )
    if not isinstance(beta_mu, list):
        raise EngineFailure(
            "F3",
            "beta_length_mismatch",
            "S2",
            MODULE_GAMMA,
            {"path": path.as_posix(), "detail": "missing_beta_mu"},
            dataset_id="hurdle_coefficients",
        )
    expected_len = 1 + len(dict_mcc) + len(dict_ch)
    if len(beta_mu) != expected_len:
        raise EngineFailure(
            "F3",
            "beta_length_mismatch",
            "S2",
            MODULE_GAMMA,
            {"expected_len": expected_len, "observed_len": len(beta_mu)},
            dataset_id="hurdle_coefficients",
        )
    return {
        "dict_mcc": [int(value) for value in dict_mcc],
        "dict_ch": [str(value) for value in dict_ch],
    }, [float(value) for value in beta_mu]


def _load_nb_dispersion_coefficients(path: Path) -> tuple[dict, list[float]]:
    payload = _load_yaml(path)
    dict_mcc = payload.get("dict_mcc")
    dict_ch = payload.get("dict_ch")
    beta_phi = payload.get("beta_phi")
    if not isinstance(dict_mcc, list) or not isinstance(dict_ch, list):
        raise EngineFailure(
            "F3",
            "column_order_mismatch",
            "S2",
            MODULE_GAMMA,
            {"path": path.as_posix(), "detail": "missing_dict_blocks"},
            dataset_id="nb_dispersion_coefficients",
        )
    if not isinstance(beta_phi, list):
        raise EngineFailure(
            "F3",
            "beta_length_mismatch",
            "S2",
            MODULE_GAMMA,
            {"path": path.as_posix(), "detail": "missing_beta_phi"},
            dataset_id="nb_dispersion_coefficients",
        )
    expected_len = 1 + len(dict_mcc) + len(dict_ch) + 1
    if len(beta_phi) != expected_len:
        raise EngineFailure(
            "F3",
            "beta_length_mismatch",
            "S2",
            MODULE_GAMMA,
            {"expected_len": expected_len, "observed_len": len(beta_phi)},
            dataset_id="nb_dispersion_coefficients",
        )
    return {
        "dict_mcc": [int(value) for value in dict_mcc],
        "dict_ch": [str(value) for value in dict_ch],
    }, [float(value) for value in beta_phi]


def _load_gdp_map(path: Path) -> dict[str, float]:
    df = pl.read_parquet(path)
    required = {"country_iso", "gdp_pc_usd_2015", "observation_year"}
    if not required.issubset(set(df.columns)):
        raise InputResolutionError(
            "world_bank_gdp_per_capita missing required columns."
        )
    df = df.filter(pl.col("observation_year") == 2024)
    if df.is_empty():
        raise InputResolutionError("GDP per-capita missing observation_year=2024.")
    dupes = df.group_by("country_iso").len().filter(pl.col("len") > 1)
    if dupes.height > 0:
        raise InputResolutionError("GDP per-capita has duplicate country_iso rows.")
    return dict(zip(df["country_iso"].to_list(), df["gdp_pc_usd_2015"].to_list()))


def _load_iso_set(path: Path) -> set[str]:
    df = pl.read_parquet(path)
    if "country_iso" not in df.columns:
        raise InputResolutionError("iso3166_canonical_2024 missing country_iso column.")
    return set(df["country_iso"].to_list())


def _build_merchant_frame(
    merchant_path: Path,
    ingress_schema: dict,
    iso_set: set[str],
    gdp_map: dict[str, float],
) -> pl.DataFrame:
    merchant_df = (
        pl.read_parquet(merchant_path)
        if merchant_path.suffix == ".parquet"
        else pl.read_csv(merchant_path)
    )
    try:
        validate_dataframe(merchant_df.iter_rows(named=True), ingress_schema, "merchant_ids")
    except SchemaValidationError as exc:
        first = exc.errors[0] if exc.errors else {}
        raise EngineFailure(
            "F1",
            "ingress_schema_violation",
            "S2.1",
            "1A.s2_ingress",
            {
                "row_index": first.get("row_index"),
                "field": first.get("field"),
                "message": first.get("message"),
            },
        ) from exc
    bad_iso = (
        merchant_df.filter(~pl.col("home_country_iso").is_in(list(iso_set)))
        .select("home_country_iso")
        .unique()
    )
    if bad_iso.height > 0:
        raise EngineFailure(
            "F1",
            "home_iso_fk",
            "S2.1",
            "1A.s2_ingress",
            {"iso": bad_iso.to_series().to_list()},
        )
    gdp_df = pl.DataFrame(
        {
            "home_country_iso": list(gdp_map.keys()),
            "gdp_per_capita": list(gdp_map.values()),
        }
    )
    merged = merchant_df.join(gdp_df, on="home_country_iso", how="left")
    missing_gdp = (
        merged.filter(pl.col("gdp_per_capita").is_null())
        .select("home_country_iso")
        .unique()
    )
    if missing_gdp.height > 0:
        raise EngineFailure(
            "F3",
            "gdp_missing",
            "S2.1",
            "1A.s2_gdp",
            {"iso": missing_gdp.to_series().to_list()},
        )
    nonpos_gdp = merged.filter(pl.col("gdp_per_capita") <= 0.0)
    if nonpos_gdp.height > 0:
        raise EngineFailure(
            "F3",
            "gdp_nonpositive",
            "S2.1",
            "1A.s2_gdp",
            {"count": nonpos_gdp.height},
        )
    return merged.with_columns(
        [
            pl.col("channel").replace_strict(CHANNEL_MAP).alias("channel_sym"),
        ]
    )


def _box_muller(stream: Substream) -> tuple[float, int, int]:
    u1, u2, blocks, draws = u01_pair(stream)
    r = math.sqrt(-2.0 * math.log(u1))
    theta = TAU * u2
    z = r * math.cos(theta)
    return z, blocks, draws


def _gamma_mt1998(alpha: float, stream: Substream) -> tuple[float, int, int]:
    if not math.isfinite(alpha) or alpha <= 0.0:
        raise EngineFailure(
            "F3",
            "gamma_alpha_invalid",
            "S2.3",
            MODULE_GAMMA,
            {"alpha": alpha},
            dataset_id=DATASET_GAMMA,
        )
    blocks_total = 0
    draws_total = 0
    if alpha < 1.0:
        g, blocks, draws = _gamma_mt1998(alpha + 1.0, stream)
        blocks_total += blocks
        draws_total += draws
        u, blocks, draws = u01_single(stream)
        blocks_total += blocks
        draws_total += draws
        return g * (u ** (1.0 / alpha)), blocks_total, draws_total
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


def _poisson_inversion(lam: float, stream: Substream) -> tuple[int, int, int]:
    if lam < 0.0 or not math.isfinite(lam):
        raise EngineFailure(
            "F3",
            "poisson_lambda_invalid",
            "S2.3",
            MODULE_POISSON,
            {"lambda": lam},
            dataset_id=DATASET_POISSON,
        )
    l_const = math.exp(-lam)
    k = 0
    p = 1.0
    blocks_total = 0
    draws_total = 0
    while True:
        u, blocks, draws = u01_single(stream)
        blocks_total += blocks
        draws_total += draws
        p *= u
        if p <= l_const:
            return k, blocks_total, draws_total
        k += 1


def _poisson_ptrs(lam: float, stream: Substream) -> tuple[int, int, int]:
    if lam < 0.0 or not math.isfinite(lam):
        raise EngineFailure(
            "F3",
            "poisson_lambda_invalid",
            "S2.3",
            MODULE_POISSON,
            {"lambda": lam},
            dataset_id=DATASET_POISSON,
        )
    b = 0.931 + 2.53 * math.sqrt(lam)
    a = -0.059 + 0.02483 * b
    inv_alpha = 1.1239 + 1.1328 / (b - 3.4)
    v_r = 0.9277 - 3.6224 / (b - 2.0)
    u_cut = 0.86
    blocks_total = 0
    draws_total = 0
    while True:
        u, v, blocks, draws = u01_pair(stream)
        blocks_total += blocks
        draws_total += draws
        if u <= u_cut and v <= v_r:
            k = math.floor(b * v / u + lam + 0.43)
            return int(k), blocks_total, draws_total
        u_s = 0.5 - abs(u - 0.5)
        k = math.floor((2.0 * a / u_s + b) * v + lam + 0.43)
        if k < 0:
            continue
        log_accept = math.log(v * inv_alpha / (a / (u_s * u_s) + b))
        if log_accept <= -lam + k * math.log(lam) - math.lgamma(k + 1.0):
            return int(k), blocks_total, draws_total


def _poisson_sample(lam: float, stream: Substream) -> tuple[int, int, int]:
    if lam < 10.0:
        return _poisson_inversion(lam, stream)
    return _poisson_ptrs(lam, stream)


def _u128_diff(before_hi: int, before_lo: int, after_hi: int, after_lo: int) -> int:
    before = (int(before_hi) << 64) | int(before_lo)
    after = (int(after_hi) << 64) | int(after_lo)
    if after < before:
        raise EngineFailure(
            "F4",
            "rng_counter_regression",
            "S2",
            MODULE_GAMMA,
            {"before": before, "after": after},
        )
    return after - before


def _load_validation_policy(path: Path, schema_layer1: dict) -> dict:
    payload = _load_yaml(path)
    schema = _schema_from_pack(schema_layer1, "policy/validation_policy")
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
        raise SchemaValidationError("validation_policy schema validation failed", details)
    return payload


def _load_hurdle_gates(
    hurdle_paths: list[Path],
    schema_layer1: dict,
    seed: int,
    parameter_hash: str,
    run_id: str,
) -> set[int]:
    event_schema = _schema_from_pack(schema_layer1, "rng/events/hurdle_bernoulli")
    validator = Draft202012Validator(event_schema)
    multi_merchants: set[int] = set()
    for path, line_no, payload in _iter_jsonl_files(hurdle_paths):
        errors = list(validator.iter_errors(payload))
        if errors:
            raise EngineFailure(
                "F4",
                "schema_violation",
                "S2.1",
                MODULE_GAMMA,
                {"path": path.as_posix(), "line": line_no, "detail": errors[0].message},
                dataset_id=DATASET_HURDLE,
            )
        if payload.get("seed") != seed or payload.get("parameter_hash") != parameter_hash or payload.get("run_id") != run_id:
            raise EngineFailure(
                "F4",
                "lineage_mismatch",
                "S2.1",
                MODULE_GAMMA,
                {"path": path.as_posix(), "line": line_no},
                dataset_id=DATASET_HURDLE,
            )
        if payload.get("is_multi") is True:
            multi_merchants.add(int(payload["merchant_id"]))
    return multi_merchants


def _load_event_rows(
    paths: list[Path],
    schema: dict,
    dataset_id: str,
    module_name: str,
    context_expected: Optional[str] = None,
) -> list[dict]:
    validator = Draft202012Validator(schema)
    rows = []
    for path, line_no, payload in _iter_jsonl_files(paths):
        errors = list(validator.iter_errors(payload))
        if errors:
            raise EngineFailure(
                "F4",
                "schema_violation",
                "S2",
                module_name,
                {"path": path.as_posix(), "line": line_no, "detail": errors[0].message},
                dataset_id=dataset_id,
            )
        if payload.get("module") != module_name:
            raise EngineFailure(
                "F4",
                "module_mismatch",
                "S2",
                module_name,
                {"path": path.as_posix(), "line": line_no, "module": payload.get("module")},
                dataset_id=dataset_id,
            )
        if context_expected is not None and payload.get("context") != context_expected:
            raise EngineFailure(
                "F4",
                "context_mismatch",
                "S2",
                module_name,
                {"path": path.as_posix(), "line": line_no, "context": payload.get("context")},
                dataset_id=dataset_id,
            )
        rows.append(payload)
    return rows


def _trace_row_key(payload: dict, path: Path) -> tuple[int, int, int, str, int, int, str]:
    return (
        int(payload["events_total"]),
        int(payload["blocks_total"]),
        int(payload["draws_total"]),
        str(payload.get("ts_utc", "")),
        int(payload["rng_counter_after_hi"]),
        int(payload["rng_counter_after_lo"]),
        path.name,
    )


def _validate_trace(
    trace_paths: list[Path],
    schema_layer1: dict,
    expected_totals: dict[tuple[str, str], dict[str, int]],
) -> None:
    trace_schema = _schema_from_pack(schema_layer1, "rng/core/rng_trace_log/record")
    validator = Draft202012Validator(trace_schema)
    final_rows: dict[tuple[str, str], tuple[tuple[int, ...], dict]] = {}
    for path, line_no, payload in _iter_jsonl_files(trace_paths):
        errors = list(validator.iter_errors(payload))
        if errors:
            raise EngineFailure(
                "F4",
                "schema_violation",
                "S2",
                MODULE_GAMMA,
                {"path": path.as_posix(), "line": line_no, "detail": errors[0].message},
                dataset_id=TRACE_DATASET_ID,
            )
        key = (payload.get("module"), payload.get("substream_label"))
        if key not in expected_totals:
            continue
        row_key = _trace_row_key(payload, path)
        current = final_rows.get(key)
        if current is None or row_key > current[0]:
            final_rows[key] = (row_key, payload)
    for key, totals in expected_totals.items():
        if key not in final_rows:
            raise EngineFailure(
                "F4",
                "rng_trace_missing_or_totals_mismatch",
                "S2",
                MODULE_GAMMA,
                {"detail": "missing_final_trace_row", "module": key[0], "substream_label": key[1]},
                dataset_id=TRACE_DATASET_ID,
            )
        payload = final_rows[key][1]
        if (
            int(payload["blocks_total"]) != totals["blocks_total"]
            or int(payload["draws_total"]) != totals["draws_total"]
            or int(payload["events_total"]) != totals["events_total"]
        ):
            raise EngineFailure(
                "F4",
                "rng_trace_missing_or_totals_mismatch",
                "S2",
                MODULE_GAMMA,
                {
                    "module": key[0],
                    "substream_label": key[1],
                    "trace_blocks_total": int(payload["blocks_total"]),
                    "trace_draws_total": int(payload["draws_total"]),
                    "trace_events_total": int(payload["events_total"]),
                    "expected_blocks_total": totals["blocks_total"],
                    "expected_draws_total": totals["draws_total"],
                    "expected_events_total": totals["events_total"],
                },
                dataset_id=TRACE_DATASET_ID,
            )


def _compute_corridors(
    nb_final_rows: list[dict], policy: dict
) -> dict[str, float]:
    cusum_policy = policy.get("cusum")
    if cusum_policy is None:
        raise EngineFailure(
            "F8",
            "ERR_S2_CORRIDOR_POLICY_MISSING",
            "S2.7",
            MODULE_FINAL,
            {"detail": "missing_cusum_policy"},
            dataset_id=DATASET_FINAL,
        )
    reference_k = float(cusum_policy.get("reference_k"))
    threshold_h = float(cusum_policy.get("threshold_h"))
    alpha_cap = cusum_policy.get("alpha_cap", 1.0)
    if not math.isfinite(alpha_cap) or alpha_cap <= 0.0 or alpha_cap > 1.0:
        raise EngineFailure(
            "F8",
            "ERR_S2_CORRIDOR_POLICY_MISSING",
            "S2.7",
            MODULE_FINAL,
            {"detail": "alpha_cap_invalid", "alpha_cap": alpha_cap},
            dataset_id=DATASET_FINAL,
        )

    mset = []
    for row in nb_final_rows:
        mu = float(row["mu"])
        phi = float(row["dispersion_k"])
        r = int(row["nb_rejections"])
        p = phi / (mu + phi)
        log_p0 = phi * math.log(p)
        p0 = math.exp(log_p0)
        q = 1.0 - p
        p1 = p0 * phi * q
        alpha = 1.0 - p0 - p1
        if not math.isfinite(alpha) or alpha <= 0.0 or alpha > 1.0:
            continue
        alpha_used = min(alpha, alpha_cap)
        mset.append((int(row["merchant_id"]), r, alpha_used))

    if not mset:
        raise EngineFailure(
            "F8",
            "ERR_S2_CORRIDOR_EMPTY",
            "S2.7",
            MODULE_FINAL,
            {"detail": "no_valid_merchants"},
            dataset_id=DATASET_FINAL,
        )

    r_values = [r for _m, r, _a in mset]
    r_values_sorted = sorted(r_values)
    m_count = len(r_values_sorted)
    idx = math.ceil(0.99 * m_count) - 1
    p99 = r_values_sorted[idx]
    total_r = sum(r_values)
    total_a = sum(r + 1 for r in r_values)
    rho_hat = total_r / total_a

    ordered = sorted(mset, key=lambda item: item[0])
    s_val = 0.0
    s_max = 0.0
    for _m, r, alpha_used in ordered:
        expected_r = (1.0 - alpha_used) / alpha_used
        var_r = (1.0 - alpha_used) / (alpha_used * alpha_used)
        z = (r - expected_r) / math.sqrt(var_r)
        s_val = max(0.0, s_val + (z - reference_k))
        s_max = max(s_max, s_val)

    breaches = []
    if rho_hat > 0.06:
        breaches.append("rho_rej")
    if p99 > 3:
        breaches.append("p99")
    if s_max >= threshold_h:
        breaches.append("cusum")
    if breaches:
        raise EngineFailure(
            "F8",
            "ERR_S2_CORRIDOR_BREACH",
            "S2.7",
            MODULE_FINAL,
            {
                "rho_hat": rho_hat,
                "p99": p99,
                "s_max": s_max,
                "breaches": breaches,
            },
            dataset_id=DATASET_FINAL,
        )
    return {"rho_hat": rho_hat, "p99": float(p99), "s_max": s_max, "count": float(m_count)}


def _validate_s2_outputs(
    run_paths: RunPaths,
    dictionary: dict,
    schema_layer1: dict,
    tokens: dict[str, str],
    multi_merchants: set[int],
    policy_path: Path,
) -> None:
    gamma_entry = find_dataset_entry(dictionary, DATASET_GAMMA).entry
    poisson_entry = find_dataset_entry(dictionary, DATASET_POISSON).entry
    final_entry = find_dataset_entry(dictionary, DATASET_FINAL).entry
    trace_entry = find_dataset_entry(dictionary, TRACE_DATASET_ID).entry

    gamma_paths = _resolve_run_glob(run_paths, gamma_entry["path"], tokens)
    poisson_paths = _resolve_run_glob(run_paths, poisson_entry["path"], tokens)
    final_paths = _resolve_run_glob(run_paths, final_entry["path"], tokens)
    trace_paths = _resolve_run_glob(run_paths, trace_entry["path"], tokens)

    gamma_schema = _schema_from_pack(schema_layer1, "rng/events/gamma_component")
    poisson_schema = _schema_from_pack(schema_layer1, "rng/events/poisson_component")
    final_schema = _schema_from_pack(schema_layer1, "rng/events/nb_final")

    gamma_rows = _load_event_rows(
        gamma_paths,
        gamma_schema,
        DATASET_GAMMA,
        MODULE_GAMMA,
        context_expected="nb",
    )
    poisson_rows = _load_event_rows(
        poisson_paths,
        poisson_schema,
        DATASET_POISSON,
        MODULE_POISSON,
        context_expected="nb",
    )
    final_rows = _load_event_rows(
        final_paths, final_schema, DATASET_FINAL, MODULE_FINAL, context_expected=None
    )

    gamma_by_m: dict[int, list[dict]] = {}
    poisson_by_m: dict[int, list[dict]] = {}
    final_by_m: dict[int, dict] = {}

    expected_totals: dict[tuple[str, str], dict[str, int]] = {}

    def _accumulate(event: dict, module: str, label: str) -> None:
        key = (module, label)
        totals = expected_totals.setdefault(
            key, {"draws_total": 0, "blocks_total": 0, "events_total": 0}
        )
        totals["draws_total"] += int(event["draws"])
        totals["blocks_total"] += int(event["blocks"])
        totals["events_total"] += 1

    for event in gamma_rows:
        merchant_id = int(event["merchant_id"])
        if merchant_id not in multi_merchants:
            raise EngineFailure(
                "F8",
                "branch_purity_violation",
                "S2",
                MODULE_GAMMA,
                {"merchant_id": str(merchant_id)},
                dataset_id=DATASET_GAMMA,
            )
        if int(event.get("index", 0)) != 0:
            raise EngineFailure(
                "F4",
                "gamma_index_invalid",
                "S2",
                MODULE_GAMMA,
                {"merchant_id": str(merchant_id), "index": event.get("index")},
                dataset_id=DATASET_GAMMA,
            )
        if event.get("substream_label") != SUBSTREAM_GAMMA:
            raise EngineFailure(
                "F4",
                "substream_label_mismatch",
                "S2",
                MODULE_GAMMA,
                {"merchant_id": str(merchant_id), "substream_label": event.get("substream_label")},
                dataset_id=DATASET_GAMMA,
            )
        _accumulate(event, MODULE_GAMMA, SUBSTREAM_GAMMA)
        gamma_by_m.setdefault(merchant_id, []).append(event)

    for event in poisson_rows:
        merchant_id = int(event["merchant_id"])
        if merchant_id not in multi_merchants:
            raise EngineFailure(
                "F8",
                "branch_purity_violation",
                "S2",
                MODULE_POISSON,
                {"merchant_id": str(merchant_id)},
                dataset_id=DATASET_POISSON,
            )
        if event.get("substream_label") != SUBSTREAM_POISSON:
            raise EngineFailure(
                "F4",
                "substream_label_mismatch",
                "S2",
                MODULE_POISSON,
                {"merchant_id": str(merchant_id), "substream_label": event.get("substream_label")},
                dataset_id=DATASET_POISSON,
            )
        _accumulate(event, MODULE_POISSON, SUBSTREAM_POISSON)
        poisson_by_m.setdefault(merchant_id, []).append(event)

    for event in final_rows:
        merchant_id = int(event["merchant_id"])
        if merchant_id not in multi_merchants:
            raise EngineFailure(
                "F8",
                "branch_purity_violation",
                "S2",
                MODULE_FINAL,
                {"merchant_id": str(merchant_id)},
                dataset_id=DATASET_FINAL,
            )
        if event.get("substream_label") != SUBSTREAM_FINAL:
            raise EngineFailure(
                "F4",
                "substream_label_mismatch",
                "S2",
                MODULE_FINAL,
                {"merchant_id": str(merchant_id), "substream_label": event.get("substream_label")},
                dataset_id=DATASET_FINAL,
            )
        if int(event["rng_counter_before_hi"]) != int(event["rng_counter_after_hi"]) or int(
            event["rng_counter_before_lo"]
        ) != int(event["rng_counter_after_lo"]):
            raise EngineFailure(
                "F4",
                "rng_consumption_violation",
                "S2",
                MODULE_FINAL,
                {"merchant_id": str(merchant_id)},
                dataset_id=DATASET_FINAL,
            )
        if merchant_id in final_by_m:
            raise EngineFailure(
                "F4",
                "event_coverage_gap",
                "S2",
                MODULE_FINAL,
                {"merchant_id": str(merchant_id), "detail": "duplicate_nb_final"},
                dataset_id=DATASET_FINAL,
            )
        _accumulate(event, MODULE_FINAL, SUBSTREAM_FINAL)
        final_by_m[merchant_id] = event

    for merchant_id, final_row in final_by_m.items():
        gamma_rows_m = gamma_by_m.get(merchant_id, [])
        poisson_rows_m = poisson_by_m.get(merchant_id, [])
        if not gamma_rows_m or not poisson_rows_m:
            raise EngineFailure(
                "F4",
                "event_coverage_gap",
                "S2",
                MODULE_FINAL,
                {"merchant_id": str(merchant_id), "detail": "missing_components"},
                dataset_id=DATASET_FINAL,
            )
        gamma_rows_m = sorted(
            gamma_rows_m,
            key=lambda row: (int(row["rng_counter_before_hi"]), int(row["rng_counter_before_lo"])),
        )
        poisson_rows_m = sorted(
            poisson_rows_m,
            key=lambda row: (int(row["rng_counter_before_hi"]), int(row["rng_counter_before_lo"])),
        )
        if len(gamma_rows_m) != len(poisson_rows_m):
            raise EngineFailure(
                "F4",
                "event_coverage_gap",
                "S2",
                MODULE_FINAL,
                {"merchant_id": str(merchant_id), "gamma": len(gamma_rows_m), "poisson": len(poisson_rows_m)},
                dataset_id=DATASET_FINAL,
            )
        mu = float(final_row["mu"])
        phi = float(final_row["dispersion_k"])
        accepted_index = None
        for idx, (gamma_row, poisson_row) in enumerate(zip(gamma_rows_m, poisson_rows_m)):
            lambda_expected = (mu / phi) * float(gamma_row["gamma_value"])
            if float(poisson_row["lambda"]) != lambda_expected:
                raise EngineFailure(
                    "F4",
                    "composition_mismatch",
                    "S2",
                    MODULE_FINAL,
                    {"merchant_id": str(merchant_id)},
                    dataset_id=DATASET_FINAL,
                )
            if int(poisson_row["k"]) >= 2 and accepted_index is None:
                accepted_index = idx
            blocks_delta = _u128_diff(
                gamma_row["rng_counter_before_hi"],
                gamma_row["rng_counter_before_lo"],
                gamma_row["rng_counter_after_hi"],
                gamma_row["rng_counter_after_lo"],
            )
            if blocks_delta != int(gamma_row["blocks"]):
                raise EngineFailure(
                    "F4",
                    "rng_counter_mismatch",
                    "S2",
                    MODULE_GAMMA,
                    {"merchant_id": str(merchant_id)},
                    dataset_id=DATASET_GAMMA,
                )
            blocks_delta = _u128_diff(
                poisson_row["rng_counter_before_hi"],
                poisson_row["rng_counter_before_lo"],
                poisson_row["rng_counter_after_hi"],
                poisson_row["rng_counter_after_lo"],
            )
            if blocks_delta != int(poisson_row["blocks"]):
                raise EngineFailure(
                    "F4",
                    "rng_counter_mismatch",
                    "S2",
                    MODULE_POISSON,
                    {"merchant_id": str(merchant_id)},
                    dataset_id=DATASET_POISSON,
                )
        if accepted_index is None:
            raise EngineFailure(
                "F4",
                "event_coverage_gap",
                "S2",
                MODULE_FINAL,
                {"merchant_id": str(merchant_id), "detail": "no_acceptance"},
                dataset_id=DATASET_FINAL,
            )
        if int(final_row["n_outlets"]) != int(poisson_rows_m[accepted_index]["k"]):
            raise EngineFailure(
                "F4",
                "event_coverage_gap",
                "S2",
                MODULE_FINAL,
                {"merchant_id": str(merchant_id), "detail": "n_outlets_mismatch"},
                dataset_id=DATASET_FINAL,
            )
        if int(final_row["nb_rejections"]) != accepted_index:
            raise EngineFailure(
                "F4",
                "event_coverage_gap",
                "S2",
                MODULE_FINAL,
                {"merchant_id": str(merchant_id), "detail": "nb_rejections_mismatch"},
                dataset_id=DATASET_FINAL,
            )

    trace_paths = [path for path in trace_paths if path.exists()]
    _validate_trace(trace_paths, schema_layer1, expected_totals)

    policy = _load_validation_policy(policy_path, schema_layer1)
    _compute_corridors(list(final_by_m.values()), policy)


def run_s2(config: EngineConfig, run_id: Optional[str] = None) -> S2RunResult:
    logger = get_logger("engine.layers.l1.seg_1A.s2_nb_outlets.l2.runner")
    timer = _StepTimer(logger)
    timer.info("S2: run initialised")
    source = ContractSource(root=config.contracts_root, layout=config.contracts_layout)
    _dictionary_path, dictionary = load_dataset_dictionary(source, "1A")
    _registry_path, registry = load_artefact_registry(source, "1A")
    _ingress_path, ingress_schema = load_schema_pack(source, "1A", "ingress.layer1")
    _schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

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
    timer.info(f"S2: loaded run receipt {receipt_path}")

    utc_day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    segment_state_runs_path = _segment_state_runs_path(run_paths, dictionary, utc_day)

    def _emit_state_run(status: str, detail: Optional[str] = None) -> None:
        payload = {
            "layer": "layer1",
            "segment": "1A",
            "state": "S2",
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
            "state": "S2",
            "module": failure.module,
            "substream_label": failure.detail.get("substream_label") if isinstance(failure.detail, dict) else None,
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
            "transaction_schema_merchant_ids",
            "world_bank_gdp_per_capita_20250415",
            "iso3166_canonical_2024",
            "hurdle_coefficients.yaml",
            "nb_dispersion_coefficients.yaml",
            "validation_policy",
        }
        missing = sorted(required_sealed - sealed_ids)
        if missing:
            raise InputResolutionError(
                f"sealed_inputs_1A missing required assets: {missing}"
            )

        audit_entry = find_dataset_entry(dictionary, "rng_audit_log").entry
        audit_path = _resolve_run_path(run_paths, audit_entry["path"], tokens)
        _require_rng_audit(audit_path, seed, parameter_hash, run_id)
        timer.info("S2: rng_audit_log verified")

        trace_entry = find_dataset_entry(dictionary, TRACE_DATASET_ID).entry
        trace_path = _resolve_run_path(run_paths, trace_entry["path"], tokens)

        hurdle_entry = find_dataset_entry(dictionary, DATASET_HURDLE).entry
        hurdle_paths = _resolve_run_glob(run_paths, hurdle_entry["path"], tokens)
        if not hurdle_paths:
            raise InputResolutionError("Missing hurdle_bernoulli event stream.")

        gamma_entry = find_dataset_entry(dictionary, DATASET_GAMMA).entry
        gamma_path = _resolve_event_path(run_paths, gamma_entry["path"], tokens)
        poisson_entry = find_dataset_entry(dictionary, DATASET_POISSON).entry
        poisson_path = _resolve_event_path(run_paths, poisson_entry["path"], tokens)
        final_entry = find_dataset_entry(dictionary, DATASET_FINAL).entry
        final_path = _resolve_event_path(run_paths, final_entry["path"], tokens)

        existing_events = (
            _event_has_rows(gamma_path)
            and _event_has_rows(poisson_path)
            and _event_has_rows(final_path)
        )
        existing_trace = (
            _trace_has_substream(trace_path, MODULE_GAMMA, SUBSTREAM_GAMMA)
            and _trace_has_substream(trace_path, MODULE_POISSON, SUBSTREAM_POISSON)
            and _trace_has_substream(trace_path, MODULE_FINAL, SUBSTREAM_FINAL)
        )
        policy_path = _sealed_path(sealed_inputs, "validation_policy")

        multi_merchants = _load_hurdle_gates(
            hurdle_paths, schema_layer1, seed, parameter_hash, run_id
        )
        if existing_events and existing_trace:
            timer.info("S2: existing outputs detected; running validation only")
            _validate_s2_outputs(
                run_paths=run_paths,
                dictionary=dictionary,
                schema_layer1=schema_layer1,
                tokens=tokens,
                multi_merchants=multi_merchants,
                policy_path=policy_path,
            )
            _emit_state_run("completed")
            return S2RunResult(
                run_id=run_id,
                parameter_hash=parameter_hash,
                manifest_fingerprint=manifest_fingerprint,
                gamma_path=gamma_path,
                poisson_path=poisson_path,
                nb_final_path=final_path,
            )
        if existing_events or existing_trace:
            raise InputResolutionError(
                "Partial S2 outputs detected; refuse to append. "
                "Remove existing S2 outputs or resume a clean run_id."
            )

        _ensure_event_path_clear(gamma_path)
        _ensure_event_path_clear(poisson_path)
        _ensure_event_path_clear(final_path)

        merchant_path = _sealed_path(sealed_inputs, "transaction_schema_merchant_ids")
        gdp_path = _sealed_path(sealed_inputs, "world_bank_gdp_per_capita_20250415")
        iso_path = _sealed_path(sealed_inputs, "iso3166_canonical_2024")
        hurdle_coeff_path = _sealed_path(sealed_inputs, "hurdle_coefficients.yaml")
        nb_dispersion_path = _sealed_path(sealed_inputs, "nb_dispersion_coefficients.yaml")

        gdp_map = _load_gdp_map(gdp_path)
        iso_set = _load_iso_set(iso_path)
        merchant_df = _build_merchant_frame(
            merchant_path, ingress_schema, iso_set, gdp_map
        )

        coeff_meta, beta_mu = _load_hurdle_coefficients(hurdle_coeff_path)
        disp_meta, beta_phi = _load_nb_dispersion_coefficients(nb_dispersion_path)
        if coeff_meta["dict_mcc"] != disp_meta["dict_mcc"] or coeff_meta["dict_ch"] != disp_meta["dict_ch"]:
            raise EngineFailure(
                "F3",
                "column_order_mismatch",
                "S2",
                MODULE_GAMMA,
                {"detail": "dict_mcc_or_dict_ch_mismatch"},
                dataset_id="nb_dispersion_coefficients",
            )
        dict_mcc = coeff_meta["dict_mcc"]
        dict_ch = coeff_meta["dict_ch"]
        beta_mu_intercept = beta_mu[0]
        beta_mu_mcc = {value: beta_mu[1 + idx] for idx, value in enumerate(dict_mcc)}
        beta_mu_ch = {
            value: beta_mu[1 + len(dict_mcc) + idx]
            for idx, value in enumerate(dict_ch)
        }
        beta_phi_intercept = beta_phi[0]
        beta_phi_mcc = {
            value: beta_phi[1 + idx] for idx, value in enumerate(dict_mcc)
        }
        beta_phi_ch = {
            value: beta_phi[1 + len(dict_mcc) + idx]
            for idx, value in enumerate(dict_ch)
        }
        beta_phi_gdp = beta_phi[-1]

        master_material = derive_master_material(bytes.fromhex(manifest_fingerprint), seed)

        merchant_df = merchant_df.sort("merchant_id")
        multi_count = len(multi_merchants)
        total = multi_count
        progress_every = max(1, min(10_000, total // 10 if total else 1))
        start_time = time.monotonic()
        timer.info(
            "S2: entering NB sampling loop for multi-site merchants "
            f"(S1 is_multi=true); targets={multi_count}"
        )

        tmp_dir = run_paths.tmp_root / "s2_nb_outlets"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_gamma_path = tmp_dir / "rng_event_gamma_component.jsonl"
        tmp_poisson_path = tmp_dir / "rng_event_poisson_component.jsonl"
        tmp_final_path = tmp_dir / "rng_event_nb_final.jsonl"
        tmp_trace_path = tmp_dir / "rng_trace_log_s2.jsonl"

        trace_accumulators = {
            (MODULE_GAMMA, SUBSTREAM_GAMMA): _TraceAccumulator(MODULE_GAMMA, SUBSTREAM_GAMMA),
            (MODULE_POISSON, SUBSTREAM_POISSON): _TraceAccumulator(MODULE_POISSON, SUBSTREAM_POISSON),
            (MODULE_FINAL, SUBSTREAM_FINAL): _TraceAccumulator(MODULE_FINAL, SUBSTREAM_FINAL),
        }
        skipped = 0
        processed = 0

        with (
            tmp_gamma_path.open("w", encoding="utf-8") as gamma_handle,
            tmp_poisson_path.open("w", encoding="utf-8") as poisson_handle,
            tmp_final_path.open("w", encoding="utf-8") as final_handle,
            tmp_trace_path.open("w", encoding="utf-8") as trace_handle,
        ):
            for row in merchant_df.iter_rows(named=True):
                merchant_id = int(row["merchant_id"])
                if merchant_id not in multi_merchants:
                    continue
                processed += 1
                if processed % progress_every == 0 or processed == total:
                    elapsed = max(time.monotonic() - start_time, 1e-9)
                    rate = processed / elapsed
                    eta = (total - processed) / rate if rate > 0 else 0.0
                    logger.info(
                        "S2 progress %d/%d (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
                        processed,
                        total,
                        elapsed,
                        rate,
                        eta,
                    )
                mcc = int(row["mcc"])
                channel_sym = str(row["channel_sym"])
                gdp_per_capita = float(row["gdp_per_capita"])
                if mcc not in beta_mu_mcc or mcc not in beta_phi_mcc:
                    logger.warning("S2: skip merchant=%s missing_mcc=%s", merchant_id, mcc)
                    skipped += 1
                    continue
                if channel_sym not in beta_mu_ch or channel_sym not in beta_phi_ch:
                    logger.warning(
                        "S2: skip merchant=%s unknown_channel=%s", merchant_id, channel_sym
                    )
                    skipped += 1
                    continue
                if gdp_per_capita <= 0.0 or not math.isfinite(gdp_per_capita):
                    logger.warning(
                        "S2: skip merchant=%s nonpositive_gdp=%s",
                        merchant_id,
                        gdp_per_capita,
                    )
                    skipped += 1
                    continue
                ln_gdp = math.log(gdp_per_capita)
                eta_mu = _neumaier_sum(
                    (beta_mu_intercept, beta_mu_mcc[mcc], beta_mu_ch[channel_sym])
                )
                eta_phi = _neumaier_sum(
                    (
                        beta_phi_intercept,
                        beta_phi_mcc[mcc],
                        beta_phi_ch[channel_sym],
                        beta_phi_gdp * ln_gdp,
                    )
                )
                if not math.isfinite(eta_mu) or not math.isfinite(eta_phi):
                    logger.warning("S2: skip merchant=%s nonfinite_eta", merchant_id)
                    skipped += 1
                    continue
                mu = math.exp(eta_mu)
                phi = math.exp(eta_phi)
                if not math.isfinite(mu) or not math.isfinite(phi) or mu <= 0.0 or phi <= 0.0:
                    logger.warning("S2: skip merchant=%s invalid_mu_phi", merchant_id)
                    skipped += 1
                    continue

                gamma_stream = derive_substream_state(
                    master_material, SUBSTREAM_GAMMA, merchant_id
                )
                poisson_stream = derive_substream_state(
                    master_material, SUBSTREAM_POISSON, merchant_id
                )
                final_stream = derive_substream_state(
                    master_material, SUBSTREAM_FINAL, merchant_id
                )
                attempt = 0
                while True:
                    attempt += 1
                    before_hi, before_lo = gamma_stream.counter()
                    gamma_value, blocks_used, draws_used = _gamma_mt1998(phi, gamma_stream)
                    after_hi, after_lo = gamma_stream.counter()
                    lambda_val = (mu / phi) * gamma_value
                    if not math.isfinite(lambda_val) or lambda_val <= 0.0:
                        logger.warning("S2: skip merchant=%s invalid_lambda", merchant_id)
                        skipped += 1
                        break
                    gamma_event = {
                        "ts_utc": utc_now_rfc3339_micro(),
                        "seed": seed,
                        "parameter_hash": parameter_hash,
                        "manifest_fingerprint": manifest_fingerprint,
                        "run_id": run_id,
                        "module": MODULE_GAMMA,
                        "substream_label": SUBSTREAM_GAMMA,
                        "rng_counter_before_lo": before_lo,
                        "rng_counter_before_hi": before_hi,
                        "rng_counter_after_lo": after_lo,
                        "rng_counter_after_hi": after_hi,
                        "blocks": blocks_used,
                        "draws": str(draws_used),
                        "merchant_id": merchant_id,
                        "context": "nb",
                        "index": 0,
                        "alpha": phi,
                        "gamma_value": gamma_value,
                    }
                    gamma_handle.write(json.dumps(gamma_event, ensure_ascii=True, sort_keys=True))
                    gamma_handle.write("\n")
                    trace = trace_accumulators[(MODULE_GAMMA, SUBSTREAM_GAMMA)].append(
                        gamma_event
                    )
                    trace_handle.write(json.dumps(trace, ensure_ascii=True, sort_keys=True))
                    trace_handle.write("\n")

                    before_hi, before_lo = poisson_stream.counter()
                    k, blocks_used, draws_used = _poisson_sample(lambda_val, poisson_stream)
                    after_hi, after_lo = poisson_stream.counter()
                    poisson_event = {
                        "ts_utc": utc_now_rfc3339_micro(),
                        "seed": seed,
                        "parameter_hash": parameter_hash,
                        "manifest_fingerprint": manifest_fingerprint,
                        "run_id": run_id,
                        "module": MODULE_POISSON,
                        "substream_label": SUBSTREAM_POISSON,
                        "rng_counter_before_lo": before_lo,
                        "rng_counter_before_hi": before_hi,
                        "rng_counter_after_lo": after_lo,
                        "rng_counter_after_hi": after_hi,
                        "blocks": blocks_used,
                        "draws": str(draws_used),
                        "merchant_id": merchant_id,
                        "context": "nb",
                        "lambda": lambda_val,
                        "k": k,
                        "attempt": attempt,
                    }
                    poisson_handle.write(json.dumps(poisson_event, ensure_ascii=True, sort_keys=True))
                    poisson_handle.write("\n")
                    trace = trace_accumulators[
                        (MODULE_POISSON, SUBSTREAM_POISSON)
                    ].append(poisson_event)
                    trace_handle.write(json.dumps(trace, ensure_ascii=True, sort_keys=True))
                    trace_handle.write("\n")

                    if k >= 2:
                        final_before_hi, final_before_lo = final_stream.counter()
                        final_event = {
                            "ts_utc": utc_now_rfc3339_micro(),
                            "seed": seed,
                            "parameter_hash": parameter_hash,
                            "manifest_fingerprint": manifest_fingerprint,
                            "run_id": run_id,
                            "module": MODULE_FINAL,
                            "substream_label": SUBSTREAM_FINAL,
                            "rng_counter_before_lo": final_before_lo,
                            "rng_counter_before_hi": final_before_hi,
                            "rng_counter_after_lo": final_before_lo,
                            "rng_counter_after_hi": final_before_hi,
                            "blocks": 0,
                            "draws": "0",
                            "merchant_id": merchant_id,
                            "mu": mu,
                            "dispersion_k": phi,
                            "n_outlets": k,
                            "nb_rejections": attempt - 1,
                        }
                        final_handle.write(
                            json.dumps(final_event, ensure_ascii=True, sort_keys=True)
                        )
                        final_handle.write("\n")
                        trace = trace_accumulators[(MODULE_FINAL, SUBSTREAM_FINAL)].append(
                            final_event
                        )
                        trace_handle.write(
                            json.dumps(trace, ensure_ascii=True, sort_keys=True)
                        )
                        trace_handle.write("\n")
                        break

        gamma_path.parent.mkdir(parents=True, exist_ok=True)
        poisson_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_gamma_path.replace(gamma_path)
        tmp_poisson_path.replace(poisson_path)
        tmp_final_path.replace(final_path)

        with trace_path.open("a", encoding="utf-8") as dest_handle, tmp_trace_path.open(
            "r", encoding="utf-8"
        ) as src_handle:
            for line in src_handle:
                dest_handle.write(line)

        tmp_trace_path.unlink(missing_ok=True)
        timer.info("S2: events + trace emitted")
        logger.info(
            "S2: emitted gamma=%s poisson=%s final=%s skipped=%s",
            gamma_path,
            poisson_path,
            final_path,
            skipped,
        )

        _validate_s2_outputs(
            run_paths=run_paths,
            dictionary=dictionary,
            schema_layer1=schema_layer1,
            tokens=tokens,
            multi_merchants=multi_merchants,
            policy_path=policy_path,
        )
        timer.info("S2: validation complete")

        _emit_state_run("completed")
        return S2RunResult(
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            gamma_path=gamma_path,
            poisson_path=poisson_path,
            nb_final_path=final_path,
        )
    except EngineFailure as failure:
        _record_failure(failure)
        raise
    except (ContractError, InputResolutionError, SchemaValidationError) as exc:
        failure = EngineFailure(
            "F5" if isinstance(exc, InputResolutionError) else "F4",
            "s2_contract_failure",
            "S2",
            MODULE_GAMMA,
            {"detail": str(exc)},
        )
        _record_failure(failure)
        raise
