"""S1 hurdle sampler runner for Segment 1A."""

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
from engine.layers.l1.seg_1A.s1_hurdle.rng import (
    UINT64_MAX,
    add_u128,
    derive_master_material,
    derive_substream,
    merchant_u64,
    philox2x64_10,
    u01,
)
from engine.layers.l1.seg_1A.s0_foundations.validation_bundle import write_failure_record


MODULE_NAME = "1A.hurdle_sampler"
SUBSTREAM_LABEL = "hurdle_bernoulli"
DATASET_ID = "rng_event_hurdle_bernoulli"
TRACE_DATASET_ID = "rng_trace_log"
CHANNEL_MAP = {"card_present": "CP", "card_not_present": "CNP"}
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
_DATE_VERSION_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


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


def _resolve_registry_path(
    path_template: str, repo_root: Path, artifact_name: Optional[str] = None
) -> Path:
    has_version_token = "{version}" in path_template
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
    if has_version_token:
        dated = []
        for path in matches:
            version_label = path.name if path.is_dir() else path.parent.name
            if _DATE_VERSION_RE.fullmatch(version_label):
                dated.append((version_label, path))
        if dated:
            resolved = sorted(dated, key=lambda item: item[0])[-1][1]
        else:
            resolved = matches[-1]
    else:
        resolved = matches[-1]
    if resolved.is_dir():
        if artifact_name:
            for suffix in (".parquet", ".csv", ".json", ".yaml", ".yml", ".jsonl"):
                candidate = resolved / f"{artifact_name}{suffix}"
                if candidate.exists():
                    return candidate
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


def _trace_has_substream(trace_path: Path) -> bool:
    if not trace_path.exists():
        return False
    with trace_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if (
                payload.get("module") == MODULE_NAME
                and payload.get("substream_label") == SUBSTREAM_LABEL
            ):
                return True
    return False


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


def _event_has_rows(event_path: Path) -> bool:
    if event_path.exists():
        return True
    parent = event_path.parent
    if not parent.exists():
        return False
    return any(parent.glob("*.jsonl"))


def _schema_from_pack(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        node = node[part]
    defs = dict(schema_pack.get("$defs", {}))
    id64_def = defs.get("id64")
    if isinstance(id64_def, dict):
        id64_def = dict(id64_def)
        if id64_def.get("maximum") == 9223372036854775807:
            id64_def["maximum"] = UINT64_MAX
        defs["id64"] = id64_def
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": defs,
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


def _parse_u128_draws(draws: str) -> int:
    if not isinstance(draws, str):
        raise EngineFailure(
            "F4",
            "rng_envelope_schema_violation",
            "S1",
            MODULE_NAME,
            {"detail": "draws_not_string"},
            dataset_id=DATASET_ID,
        )
    if draws not in ("0", "1"):
        raise EngineFailure(
            "F4",
            "rng_counter_mismatch",
            "S1",
            MODULE_NAME,
            {"draws": draws},
            dataset_id=DATASET_ID,
        )
    return int(draws)


def _u128_from(hi: int, lo: int) -> int:
    return (int(hi) << 64) | int(lo)


def _saturating_add(current: int, increment: int) -> int:
    total = current + increment
    if total > UINT64_MAX:
        return UINT64_MAX
    return total


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


def _raise_schema_failure(
    errors: list, dataset_id: str, path: Path, module: str
) -> None:
    missing = []
    for error in errors:
        if error.validator == "required":
            if isinstance(error.validator_value, list):
                missing.extend(error.validator_value)
    missing_fields = set(missing)
    if missing_fields & _ENVELOPE_FIELDS:
        failure_code = "rng_envelope_schema_violation"
    else:
        failure_code = "hurdle_payload_violation"
    raise EngineFailure(
        "F4",
        failure_code,
        "S1",
        module,
        {
            "dataset_id": dataset_id,
            "path": path.as_posix(),
            "missing_or_bad": sorted(missing_fields) if missing_fields else None,
        },
        dataset_id=dataset_id,
    )


def _discover_gated_entries(dictionary: dict) -> list[dict]:
    entries = []
    for section, items in dictionary.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("owner_subsegment") != "1A":
                continue
            gating = item.get("gating") or {}
            if gating.get("gated_by") == DATASET_ID:
                entries.append(item)
    return entries


def _iter_merchants_from_path(path: Path) -> Iterable[int]:
    if path.is_dir():
        for file in sorted(path.glob("*.jsonl")):
            yield from _iter_merchants_from_path(file)
        for file in sorted(path.glob("*.parquet")):
            yield from _iter_merchants_from_path(file)
        return
    if path.suffix == ".jsonl":
        for _path, _line, payload in _iter_jsonl_files([path]):
            if "merchant_id" in payload:
                yield int(payload["merchant_id"])
        return
    if path.suffix == ".parquet":
        df = pl.read_parquet(path, columns=["merchant_id"])
        for merchant_id in df["merchant_id"].to_list():
            yield int(merchant_id)


def _trace_row_key(payload: dict, path: Path) -> tuple[int, int, str, int, int, int, str]:
    return (
        int(payload["rng_counter_after_hi"]),
        int(payload["rng_counter_after_lo"]),
        str(payload.get("ts_utc", "")),
        int(payload["events_total"]),
        int(payload["blocks_total"]),
        int(payload["draws_total"]),
        path.name,
    )


def _validate_s1_outputs(
    run_paths: RunPaths,
    dictionary: dict,
    schema_layer1: dict,
    event_paths: list[Path],
    trace_paths: list[Path],
    design_map: dict[int, tuple[int, str, int]],
    coeff_meta: dict,
    beta: list[float],
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
) -> None:
    event_schema = _schema_from_pack(schema_layer1, "rng/events/hurdle_bernoulli")
    trace_schema = _schema_from_pack(schema_layer1, "rng/core/rng_trace_log/record")
    event_validator = Draft202012Validator(event_schema)
    trace_validator = Draft202012Validator(trace_schema)

    dict_mcc = coeff_meta["dict_mcc"]
    dict_ch = coeff_meta["dict_ch"]
    dict_dev5 = coeff_meta["dict_dev5"]
    offset_mcc = 1
    offset_ch = offset_mcc + len(dict_mcc)
    offset_dev = offset_ch + len(dict_ch)
    beta_intercept = beta[0]
    beta_mcc = {value: beta[offset_mcc + idx] for idx, value in enumerate(dict_mcc)}
    beta_ch = {value: beta[offset_ch + idx] for idx, value in enumerate(dict_ch)}
    beta_dev = {value: beta[offset_dev + idx] for idx, value in enumerate(dict_dev5)}
    master_material = derive_master_material(bytes.fromhex(manifest_fingerprint), seed)

    merchant_seen: set[int] = set()
    merchant_multi: set[int] = set()
    draws_total = 0
    blocks_total = 0
    events_total = 0
    if not event_paths:
        raise EngineFailure(
            "F4",
            "rng_envelope_schema_violation",
            "S1",
            MODULE_NAME,
            {"detail": "missing_hurdle_events"},
            dataset_id=DATASET_ID,
        )
    for path, line_no, event in _iter_jsonl_files(event_paths):
        errors = list(event_validator.iter_errors(event))
        if errors:
            _raise_schema_failure(errors, DATASET_ID, path, MODULE_NAME)
        if event.get("module") != MODULE_NAME:
            raise EngineFailure(
                "F4",
                "substream_label_mismatch",
                "S1",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no, "module": event.get("module")},
                dataset_id=DATASET_ID,
            )
        if event.get("substream_label") != SUBSTREAM_LABEL:
            raise EngineFailure(
                "F4",
                "substream_label_mismatch",
                "S1",
                MODULE_NAME,
                {
                    "path": path.as_posix(),
                    "line": line_no,
                    "substream_label": event.get("substream_label"),
                },
                dataset_id=DATASET_ID,
            )
        if (
            event.get("seed") != seed
            or event.get("parameter_hash") != parameter_hash
            or event.get("run_id") != run_id
            or event.get("manifest_fingerprint") != manifest_fingerprint
        ):
            raise EngineFailure(
                "F5",
                "partition_mismatch",
                "S1",
                MODULE_NAME,
                {
                    "path": path.as_posix(),
                    "path_key": {
                        "seed": seed,
                        "parameter_hash": parameter_hash,
                        "run_id": run_id,
                        "manifest_fingerprint": manifest_fingerprint,
                    },
                    "embedded_key": {
                        "seed": event.get("seed"),
                        "parameter_hash": event.get("parameter_hash"),
                        "run_id": event.get("run_id"),
                        "manifest_fingerprint": event.get("manifest_fingerprint"),
                    },
                },
                dataset_id=DATASET_ID,
            )
        merchant_id = int(event["merchant_id"])
        if merchant_id in merchant_seen:
            raise EngineFailure(
                "F8",
                "duplicate_hurdle_record",
                "S1",
                MODULE_NAME,
                {"merchant_id": str(merchant_id)},
                dataset_id=DATASET_ID,
                merchant_id=str(merchant_id),
            )
        merchant_seen.add(merchant_id)
        if merchant_id not in design_map:
            raise EngineFailure(
                "F3",
                "unknown_category",
                "S1",
                MODULE_NAME,
                {"field": "merchant_id", "value": str(merchant_id)},
                dataset_id=DATASET_ID,
                merchant_id=str(merchant_id),
            )
        mcc, channel_sym, bucket_id = design_map[merchant_id]
        if mcc not in beta_mcc:
            raise EngineFailure(
                "F3",
                "unknown_category",
                "S1",
                MODULE_NAME,
                {"field": "mcc", "value": int(mcc)},
                dataset_id=DATASET_ID,
                merchant_id=str(merchant_id),
            )
        if channel_sym not in beta_ch:
            raise EngineFailure(
                "F3",
                "unknown_category",
                "S1",
                MODULE_NAME,
                {"field": "channel", "value": str(channel_sym)},
                dataset_id=DATASET_ID,
                merchant_id=str(merchant_id),
            )
        if bucket_id not in beta_dev:
            raise EngineFailure(
                "F3",
                "unknown_category",
                "S1",
                MODULE_NAME,
                {"field": "bucket", "value": int(bucket_id)},
                dataset_id=DATASET_ID,
                merchant_id=str(merchant_id),
            )
        eta = _neumaier_sum(
            (beta_intercept, beta_mcc[mcc], beta_ch[channel_sym], beta_dev[bucket_id])
        )
        if not math.isfinite(eta):
            raise EngineFailure(
                "F3",
                "hurdle_nonfinite_eta",
                "S1",
                MODULE_NAME,
                {"merchant_id": str(merchant_id), "eta": str(eta)},
                dataset_id=DATASET_ID,
                merchant_id=str(merchant_id),
            )
        pi_expected = _logistic(eta)
        if not math.isfinite(pi_expected) or pi_expected < 0.0 or pi_expected > 1.0:
            raise EngineFailure(
                "F3",
                "hurdle_nonfinite_or_oob_pi",
                "S1",
                MODULE_NAME,
                {"merchant_id": str(merchant_id), "eta": str(eta), "pi": str(pi_expected)},
                dataset_id=DATASET_ID,
                merchant_id=str(merchant_id),
            )
        if float(event["pi"]) != pi_expected:
            raise EngineFailure(
                "F3",
                "column_order_mismatch",
                "S1",
                MODULE_NAME,
                {"merchant_id": str(merchant_id), "expected_pi": pi_expected, "observed_pi": event["pi"]},
                dataset_id=DATASET_ID,
                merchant_id=str(merchant_id),
            )

        draws_expected = 0 if pi_expected in (0.0, 1.0) else 1
        draws = _parse_u128_draws(event["draws"])
        blocks = int(event["blocks"])
        if draws != draws_expected or blocks != draws_expected:
            raise EngineFailure(
                "F4",
                "rng_counter_mismatch",
                "S1",
                MODULE_NAME,
                {"draws": event["draws"], "blocks": blocks, "expected": draws_expected},
                dataset_id=DATASET_ID,
                merchant_id=str(merchant_id),
            )

        key, ctr_hi, ctr_lo = derive_substream(
            master_material, SUBSTREAM_LABEL, merchant_u64(merchant_id)
        )
        before_hi = int(event["rng_counter_before_hi"])
        before_lo = int(event["rng_counter_before_lo"])
        if before_hi != ctr_hi or before_lo != ctr_lo:
            raise EngineFailure(
                "F4",
                "rng_counter_mismatch",
                "S1",
                MODULE_NAME,
                {
                    "merchant_id": str(merchant_id),
                    "before": {"hi": before_hi, "lo": before_lo},
                    "expected_before": {"hi": ctr_hi, "lo": ctr_lo},
                },
                dataset_id=DATASET_ID,
                merchant_id=str(merchant_id),
            )
        after_hi = int(event["rng_counter_after_hi"])
        after_lo = int(event["rng_counter_after_lo"])
        delta = _u128_from(after_hi, after_lo) - _u128_from(before_hi, before_lo)
        if delta != draws_expected or blocks != draws_expected:
            raise EngineFailure(
                "F4",
                "rng_counter_mismatch",
                "S1",
                MODULE_NAME,
                {
                    "before": {"hi": before_hi, "lo": before_lo},
                    "after": {"hi": after_hi, "lo": after_lo},
                    "blocks": blocks,
                    "draws": event["draws"],
                },
                dataset_id=DATASET_ID,
                merchant_id=str(merchant_id),
            )

        deterministic = bool(event["deterministic"])
        u_value = event.get("u")
        if draws_expected == 0:
            if not deterministic or u_value is not None:
                raise EngineFailure(
                    "F4",
                    "deterministic_branch_inconsistent",
                    "S1",
                    MODULE_NAME,
                    {"merchant_id": str(merchant_id), "pi": pi_expected, "u": u_value},
                    dataset_id=DATASET_ID,
                    merchant_id=str(merchant_id),
                )
            is_multi_expected = pi_expected == 1.0
            if bool(event["is_multi"]) != is_multi_expected:
                raise EngineFailure(
                    "F4",
                    "deterministic_branch_inconsistent",
                    "S1",
                    MODULE_NAME,
                    {"merchant_id": str(merchant_id), "pi": pi_expected, "is_multi": event["is_multi"]},
                    dataset_id=DATASET_ID,
                    merchant_id=str(merchant_id),
                )
        else:
            if deterministic or u_value is None:
                raise EngineFailure(
                    "F4",
                    "deterministic_branch_inconsistent",
                    "S1",
                    MODULE_NAME,
                    {"merchant_id": str(merchant_id), "pi": pi_expected, "u": u_value},
                    dataset_id=DATASET_ID,
                    merchant_id=str(merchant_id),
                )
            u_value = float(u_value)
            if not (0.0 < u_value < 1.0):
                raise EngineFailure(
                    "F4",
                    "u_out_of_range",
                    "S1",
                    MODULE_NAME,
                    {"merchant_id": str(merchant_id), "u": u_value, "pi": pi_expected},
                    dataset_id=DATASET_ID,
                    merchant_id=str(merchant_id),
                )
            x0, _x1 = philox2x64_10(ctr_hi, ctr_lo, key)
            u_expected = u01(x0)
            if u_expected != u_value:
                raise EngineFailure(
                    "F4",
                    "deterministic_branch_inconsistent",
                    "S1",
                    MODULE_NAME,
                    {"merchant_id": str(merchant_id), "u": u_value, "u_expected": u_expected},
                    dataset_id=DATASET_ID,
                    merchant_id=str(merchant_id),
                )
            if (u_value < pi_expected) != bool(event["is_multi"]):
                raise EngineFailure(
                    "F4",
                    "deterministic_branch_inconsistent",
                    "S1",
                    MODULE_NAME,
                    {"merchant_id": str(merchant_id), "u": u_value, "pi": pi_expected},
                    dataset_id=DATASET_ID,
                    merchant_id=str(merchant_id),
                )
        if bool(event["is_multi"]):
            merchant_multi.add(merchant_id)
        draws_total = _saturating_add(draws_total, draws_expected)
        blocks_total = _saturating_add(blocks_total, blocks)
        events_total = _saturating_add(events_total, 1)

    expected_count = len(design_map)
    if events_total != expected_count:
        raise EngineFailure(
            "F8",
            "cardinality_mismatch",
            "S1",
            MODULE_NAME,
            {"expected": expected_count, "observed": events_total},
            dataset_id=DATASET_ID,
        )

    trace_row = None
    trace_row_key = None
    trace_totals_row = None
    trace_totals_key = None
    if not trace_paths:
        raise EngineFailure(
            "F4",
            "rng_trace_missing_or_totals_mismatch",
            "S1",
            MODULE_NAME,
            {"detail": "missing_rng_trace_log"},
            dataset_id=TRACE_DATASET_ID,
        )
    for path, _line, payload in _iter_jsonl_files(trace_paths):
        errors = list(trace_validator.iter_errors(payload))
        if errors:
            _raise_schema_failure(errors, TRACE_DATASET_ID, path, MODULE_NAME)
        if payload.get("seed") != seed or payload.get("run_id") != run_id:
            raise EngineFailure(
                "F5",
                "partition_mismatch",
                "S1",
                MODULE_NAME,
                {
                    "path": path.as_posix(),
                    "path_key": {"seed": seed, "run_id": run_id},
                    "embedded_key": {"seed": payload.get("seed"), "run_id": payload.get("run_id")},
                },
                dataset_id=TRACE_DATASET_ID,
            )
        if payload.get("module") == MODULE_NAME and payload.get("substream_label") == SUBSTREAM_LABEL:
            candidate_key = _trace_row_key(payload, path)
            if trace_row_key is None or candidate_key > trace_row_key:
                trace_row = payload
                trace_row_key = candidate_key
            totals_key = (
                int(payload["events_total"]),
                int(payload["blocks_total"]),
                int(payload["draws_total"]),
                str(payload.get("ts_utc", "")),
                path.name,
            )
            if trace_totals_key is None or totals_key > trace_totals_key:
                trace_totals_row = payload
                trace_totals_key = totals_key
    if trace_row is None:
        raise EngineFailure(
            "F4",
            "rng_trace_missing_or_totals_mismatch",
            "S1",
            MODULE_NAME,
            {"detail": "missing_final_trace_row"},
            dataset_id=TRACE_DATASET_ID,
        )

    if (
        int(trace_row["blocks_total"]) != blocks_total
        or int(trace_row["draws_total"]) != draws_total
        or int(trace_row["events_total"]) != events_total
    ):
        if trace_totals_row and (
            int(trace_totals_row["blocks_total"]) == blocks_total
            and int(trace_totals_row["draws_total"]) == draws_total
            and int(trace_totals_row["events_total"]) == events_total
        ):
            logger = get_logger("engine.layers.l1.seg_1A.s1_hurdle.l2.runner")
            logger.info("S1: trace selection fallback used (max totals row)")
            trace_row = trace_totals_row
        else:
            raise EngineFailure(
                "F4",
                "rng_trace_missing_or_totals_mismatch",
                "S1",
                MODULE_NAME,
                {
                    "trace_blocks_total": int(trace_row["blocks_total"]),
                    "trace_draws_total": int(trace_row["draws_total"]),
                    "trace_events_total": int(trace_row["events_total"]),
                    "expected_blocks_total": blocks_total,
                    "expected_draws_total": draws_total,
                    "expected_events_total": events_total,
                },
                dataset_id=TRACE_DATASET_ID,
            )

    gated_entries = _discover_gated_entries(dictionary)
    for entry in gated_entries:
        path_template = entry.get("path")
        if not path_template:
            continue
        gated_paths = _resolve_run_glob(
            run_paths,
            path_template,
            {"seed": str(seed), "parameter_hash": parameter_hash, "run_id": run_id},
        )
        gated_paths = [path for path in gated_paths if path.exists()]
        if not gated_paths:
            continue
        for path in gated_paths:
            for merchant_id in _iter_merchants_from_path(path):
                if merchant_id not in merchant_multi:
                    raise EngineFailure(
                        "F8",
                        "gating_violation_no_prior_hurdle_true",
                        "S1",
                        MODULE_NAME,
                        {
                            "dataset_id": entry.get("id"),
                            "path": path.as_posix(),
                            "merchant_id": str(merchant_id),
                        },
                        dataset_id=entry.get("id"),
                        merchant_id=str(merchant_id),
                    )


class _TraceAccumulator:
    def __init__(self) -> None:
        self.draws_total = 0
        self.blocks_total = 0
        self.events_total = 0
        self._run_id: str | None = None
        self._seed: int | None = None
        self._module: str | None = None
        self._substream_label: str | None = None
        self._max_after_hi: int | None = None
        self._max_after_lo: int | None = None
        self._max_before_hi: int | None = None
        self._max_before_lo: int | None = None

    def append(self, event: dict) -> dict:
        if self._run_id is None:
            self._run_id = event["run_id"]
            self._seed = int(event["seed"])
            self._module = event["module"]
            self._substream_label = event["substream_label"]
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


def _checked_add(current: int, increment: int) -> int:
    total = current + increment
    if total > UINT64_MAX:
        return UINT64_MAX
    return total


def _load_coefficients(path: Path) -> tuple[dict, list[float]]:
    payload = _load_yaml(path)
    dict_mcc = payload.get("dict_mcc")
    dict_ch = payload.get("dict_ch")
    dict_dev5 = payload.get("dict_dev5")
    beta = payload.get("beta")
    if not isinstance(dict_mcc, list) or not isinstance(dict_ch, list) or not isinstance(dict_dev5, list):
        raise EngineFailure(
            "F3",
            "column_order_mismatch",
            "S1",
            MODULE_NAME,
            {"path": path.as_posix(), "detail": "missing_dict_blocks"},
            dataset_id="hurdle_coefficients",
        )
    if dict_ch != ["CP", "CNP"]:
        raise EngineFailure(
            "F3",
            "column_order_mismatch",
            "S1",
            MODULE_NAME,
            {"path": path.as_posix(), "dict_ch": dict_ch},
            dataset_id="hurdle_coefficients",
        )
    if dict_dev5 != [1, 2, 3, 4, 5]:
        raise EngineFailure(
            "F3",
            "column_order_mismatch",
            "S1",
            MODULE_NAME,
            {"path": path.as_posix(), "dict_dev5": dict_dev5},
            dataset_id="hurdle_coefficients",
        )
    if not isinstance(beta, list):
        raise EngineFailure(
            "F3",
            "beta_length_mismatch",
            "S1",
            MODULE_NAME,
            {"path": path.as_posix(), "detail": "missing_beta_list"},
            dataset_id="hurdle_coefficients",
        )
    expected_len = 1 + len(dict_mcc) + len(dict_ch) + len(dict_dev5)
    if len(beta) != expected_len:
        raise EngineFailure(
            "F3",
            "beta_length_mismatch",
            "S1",
            MODULE_NAME,
            {"expected_len": expected_len, "observed_len": len(beta)},
            dataset_id="hurdle_coefficients",
        )
    return {
        "dict_mcc": [int(value) for value in dict_mcc],
        "dict_ch": [str(value) for value in dict_ch],
        "dict_dev5": [int(value) for value in dict_dev5],
    }, [float(value) for value in beta]


def run_s1(config: EngineConfig, run_id: Optional[str] = None) -> S1RunResult:
    logger = get_logger("engine.layers.l1.seg_1A.s1_hurdle.l2.runner")
    timer = _StepTimer(logger)
    timer.info("S1: run initialised")
    source = ContractSource(root=config.contracts_root, layout=config.contracts_layout)
    _dictionary_path, dictionary = load_dataset_dictionary(source, "1A")
    _registry_path, registry = load_artefact_registry(source, "1A")
    _schema_1a_path, _schema_1a = load_schema_pack(source, "1A", "1A")
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
    timer.info(f"S1: loaded run receipt {receipt_path}")

    utc_day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    segment_state_runs_path = _segment_state_runs_path(run_paths, dictionary, utc_day)

    def _emit_state_run(status: str, detail: Optional[str] = None) -> None:
        payload = {
            "layer": "layer1",
            "segment": "1A",
            "state": "S1",
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
            "state": "S1",
            "module": MODULE_NAME,
            "substream_label": SUBSTREAM_LABEL,
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

    def _wrap_exception(exc: Exception) -> EngineFailure:
        message = str(exc)
        dataset_id = None
        if "rng_audit_log" in message:
            dataset_id = "rng_audit_log"
        elif "rng_trace_log" in message:
            dataset_id = TRACE_DATASET_ID
        failure_class = "F5" if isinstance(exc, InputResolutionError) else "F4"
        failure_code = (
            "wrong_dataset_path"
            if isinstance(exc, InputResolutionError)
            else "hurdle_payload_violation"
        )
        return EngineFailure(
            failure_class,
            failure_code,
            "S1",
            MODULE_NAME,
            {"detail": message},
            dataset_id=dataset_id,
        )

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
        sealed_ids = {item.get("id") for item in gate_receipt.get("sealed_inputs", [])}
        if "hurdle_coefficients.yaml" not in sealed_ids:
            raise InputResolutionError(
                "s0_gate_receipt missing hurdle_coefficients.yaml in sealed_inputs."
            )

        audit_entry = find_dataset_entry(dictionary, "rng_audit_log").entry
        audit_path = _resolve_run_path(run_paths, audit_entry["path"], tokens)
        _require_rng_audit(audit_path, seed, parameter_hash, run_id)
        timer.info("S1: rng_audit_log verified")

        trace_entry = find_dataset_entry(dictionary, "rng_trace_log").entry
        trace_path = _resolve_run_path(run_paths, trace_entry["path"], tokens)

        event_entry = find_dataset_entry(dictionary, DATASET_ID).entry
        event_path = _resolve_event_path(run_paths, event_entry["path"], tokens)

        design_entry = find_dataset_entry(dictionary, "hurdle_design_matrix").entry
        design_root = _resolve_run_path(
            run_paths, design_entry["path"], {"parameter_hash": parameter_hash}
        )
        design_path = _select_dataset_file("hurdle_design_matrix", design_root)
        design_df = pl.read_parquet(
            design_path,
            columns=["merchant_id", "mcc", "channel", "gdp_bucket_id", "intercept"],
        )
        required_cols = {
            "merchant_id",
            "mcc",
            "channel",
            "gdp_bucket_id",
            "intercept",
        }
        if set(design_df.columns) != required_cols:
            raise EngineFailure(
                "F3",
                "column_order_mismatch",
                "S1",
                MODULE_NAME,
                {"detail": "missing_required_columns", "columns": design_df.columns},
                dataset_id="hurdle_design_matrix",
            )
        intercept_bad = design_df.filter(pl.col("intercept") != 1.0)
        if intercept_bad.height > 0:
            raise EngineFailure(
                "F3",
                "column_order_mismatch",
                "S1",
                MODULE_NAME,
                {"detail": "intercept_not_unity", "count": intercept_bad.height},
                dataset_id="hurdle_design_matrix",
            )
        unique_count = design_df.select(pl.col("merchant_id").n_unique()).to_series()[0]
        if unique_count != design_df.height:
            raise EngineFailure(
                "F8",
                "duplicate_hurdle_record",
                "S1",
                MODULE_NAME,
                {"detail": "design_matrix_duplicate_merchant_id"},
                dataset_id="hurdle_design_matrix",
            )
        design_map: dict[int, tuple[int, str, int]] = {}
        for merchant_id, mcc, channel, bucket_id in design_df.select(
            ["merchant_id", "mcc", "channel", "gdp_bucket_id"]
        ).iter_rows():
            channel_sym = CHANNEL_MAP.get(str(channel))
            if channel_sym is None:
                raise EngineFailure(
                    "F3",
                    "unknown_category",
                    "S1",
                    MODULE_NAME,
                    {"field": "channel", "value": str(channel)},
                    dataset_id="hurdle_design_matrix",
                )
            design_map[int(merchant_id)] = (int(mcc), channel_sym, int(bucket_id))
        timer.info(f"S1: loaded hurdle_design_matrix rows={design_df.height}")

        registry_entry = None
        for subsegment in registry.get("subsegments", []):
            for artifact in subsegment.get("artifacts", []):
                if artifact.get("name") == "hurdle_coefficients":
                    registry_entry = artifact
                    break
            if registry_entry:
                break
        if registry_entry is None:
            raise ContractError("Registry entry not found: hurdle_coefficients")
        coeff_path = _resolve_registry_path(
            registry_entry["path"],
            config.repo_root,
            artifact_name=registry_entry.get("name"),
        )
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

        existing_trace = _trace_has_substream(trace_path)
        existing_events = _event_has_rows(event_path)
        if existing_trace and existing_events:
            logger.info("S1: existing hurdle outputs detected; validating only")
            event_paths = _resolve_run_glob(run_paths, event_entry["path"], tokens)
            trace_paths = _resolve_run_glob(run_paths, trace_entry["path"], tokens)
            _validate_s1_outputs(
                run_paths,
                dictionary,
                schema_layer1,
                event_paths,
                trace_paths,
                design_map,
                coeff_meta,
                beta,
                seed,
                parameter_hash,
                manifest_fingerprint,
                run_id,
            )
            _emit_state_run("completed")
            return S1RunResult(
                run_id=run_id,
                parameter_hash=parameter_hash,
                manifest_fingerprint=manifest_fingerprint,
                event_path=event_path,
                trace_path=trace_path,
            )
        if existing_trace or existing_events:
            raise InputResolutionError(
                "Partial hurdle outputs detected; manual cleanup required before re-emission."
            )

        _ensure_trace_clear(trace_path)
        _ensure_event_path_clear(event_path)

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
                channel_raw = row["channel"]
                gdp_bucket = int(row["gdp_bucket_id"])

                channel_sym = CHANNEL_MAP.get(str(channel_raw))
                if channel_sym is None:
                    raise EngineFailure(
                        "F3",
                        "unknown_category",
                        "S1",
                        MODULE_NAME,
                        {"field": "channel", "value": str(channel_raw)},
                        dataset_id=DATASET_ID,
                        merchant_id=str(merchant_id),
                    )
                if mcc not in beta_mcc:
                    raise EngineFailure(
                        "F3",
                        "unknown_category",
                        "S1",
                        MODULE_NAME,
                        {"field": "mcc", "value": int(mcc)},
                        dataset_id=DATASET_ID,
                        merchant_id=str(merchant_id),
                    )
                if channel_sym not in beta_ch:
                    raise EngineFailure(
                        "F3",
                        "unknown_category",
                        "S1",
                        MODULE_NAME,
                        {"field": "channel", "value": str(channel_sym)},
                        dataset_id=DATASET_ID,
                        merchant_id=str(merchant_id),
                    )
                if gdp_bucket not in beta_dev:
                    raise EngineFailure(
                        "F3",
                        "unknown_category",
                        "S1",
                        MODULE_NAME,
                        {"field": "bucket", "value": int(gdp_bucket)},
                        dataset_id=DATASET_ID,
                        merchant_id=str(merchant_id),
                    )

                eta = _neumaier_sum(
                    (
                        beta_intercept,
                        beta_mcc[mcc],
                        beta_ch[channel_sym],
                        beta_dev[gdp_bucket],
                    )
                )
                if not math.isfinite(eta):
                    raise EngineFailure(
                        "F3",
                        "hurdle_nonfinite_eta",
                        "S1",
                        MODULE_NAME,
                        {"merchant_id": str(merchant_id), "eta": str(eta)},
                        dataset_id=DATASET_ID,
                        merchant_id=str(merchant_id),
                    )
                pi = _logistic(eta)
                if not math.isfinite(pi) or pi < 0.0 or pi > 1.0:
                    raise EngineFailure(
                        "F3",
                        "hurdle_nonfinite_or_oob_pi",
                        "S1",
                        MODULE_NAME,
                        {"merchant_id": str(merchant_id), "pi": str(pi)},
                        dataset_id=DATASET_ID,
                        merchant_id=str(merchant_id),
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
                        raise EngineFailure(
                            "F4",
                            "u_out_of_range",
                            "S1",
                            MODULE_NAME,
                            {"merchant_id": str(merchant_id), "u": u, "pi": pi},
                            dataset_id=DATASET_ID,
                            merchant_id=str(merchant_id),
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

            final_trace = trace_acc.finalize()
            if final_trace:
                trace_handle.write(json.dumps(final_trace, ensure_ascii=True, sort_keys=True))
                trace_handle.write("\n")

        event_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_event_path.replace(event_path)

        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with trace_path.open("a", encoding="utf-8") as dest_handle, tmp_trace_path.open(
            "r", encoding="utf-8"
        ) as src_handle:
            for line in src_handle:
                dest_handle.write(line)
        tmp_trace_path.unlink(missing_ok=True)

        event_paths = _resolve_run_glob(run_paths, event_entry["path"], tokens)
        trace_paths = _resolve_run_glob(run_paths, trace_entry["path"], tokens)
        _validate_s1_outputs(
            run_paths,
            dictionary,
            schema_layer1,
            event_paths,
            trace_paths,
            design_map,
            coeff_meta,
            beta,
            seed,
            parameter_hash,
            manifest_fingerprint,
            run_id,
        )

        timer.info("S1: hurdle events + trace emitted")
        logger.info(
            "S1 complete: run_id=%s parameter_hash=%s manifest_fingerprint=%s rows=%d",
            run_id,
            parameter_hash,
            manifest_fingerprint,
            row_count,
        )
        _emit_state_run("completed")
        return S1RunResult(
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            event_path=event_path,
            trace_path=trace_path,
        )
    except EngineFailure as failure:
        _record_failure(failure)
        raise
    except (ContractError, InputResolutionError, SchemaValidationError) as exc:
        failure = _wrap_exception(exc)
        _record_failure(failure)
        raise
