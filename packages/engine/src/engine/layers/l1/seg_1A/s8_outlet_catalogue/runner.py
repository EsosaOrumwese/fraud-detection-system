
"""S8 outlet catalogue runner for Segment 1A."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import polars as pl
import yaml
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema, validate_dataframe
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


MODULE_NAME = "1A.site_id_allocator"
SUBSTREAM_SEQUENCE = "sequence_finalize"
SUBSTREAM_OVERFLOW = "site_sequence_overflow"

DATASET_OUTLET = "outlet_catalogue"
DATASET_CANDIDATE_SET = "s3_candidate_set"
DATASET_COUNTS = "s3_integerised_counts"
DATASET_SITE_SEQUENCE = "s3_site_sequence"
DATASET_NB_FINAL = "rng_event_nb_final"
DATASET_ZTP_FINAL = "rng_event_ztp_final"
DATASET_MEMBERSHIP = "s6_membership"
DATASET_GUMBEL = "rng_event_gumbel_key"
DATASET_SEQUENCE_FINALIZE = "rng_event_sequence_finalize"
DATASET_SEQUENCE_OVERFLOW = "rng_event_site_sequence_overflow"
DATASET_TRACE = "rng_trace_log"
DATASET_AUDIT = "rng_audit_log"
DATASET_S6_RECEIPT = "s6_validation_receipt"
DATASET_ISO = "iso3166_canonical_2024"
DATASET_S3_INTEGERISATION_POLICY = "policy.s3.integerisation.yaml"

COUNTS_HANDOFF_FILENAME = "s7_integerised_counts.jsonl"


@dataclass(frozen=True)
class S8RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    outlet_path: Path | None
    sequence_path: Path | None
    overflow_path: Path | None
    trace_path: Path


@dataclass(frozen=True)
class S3IntegerisationPolicy:
    semver: str
    version: str
    emit_integerised_counts: bool
    emit_site_sequence: bool
    consume_integerised_counts_in_s8: bool
    consume_site_sequence_in_s8: bool


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
    return normalize_nullable_schema(schema)


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


def _audit_has_entry(
    audit_path: Path, seed: int, parameter_hash: str, run_id: str
) -> bool:
    if not audit_path.exists():
        return False
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


def _load_s3_integerisation_policy(
    path: Path, schema_layer1: dict
) -> S3IntegerisationPolicy:
    payload = _load_yaml(path)
    schema = _schema_from_pack(schema_layer1, "policy/s3_integerisation")
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    if errors:
        raise EngineFailure(
            "F4",
            "E_SCHEMA_INVALID",
            "S8",
            MODULE_NAME,
            {"detail": errors[0].message, "path": path.as_posix()},
        )
    return S3IntegerisationPolicy(
        semver=str(payload.get("semver")),
        version=str(payload.get("version")),
        emit_integerised_counts=bool(payload.get("emit_integerised_counts")),
        emit_site_sequence=bool(payload.get("emit_site_sequence")),
        consume_integerised_counts_in_s8=bool(
            payload.get("consume_integerised_counts_in_s8", False)
        ),
        consume_site_sequence_in_s8=bool(
            payload.get("consume_site_sequence_in_s8", False)
        ),
    )


def _git_hex_to_bytes(git_hex: str) -> bytes:
    git_hex = git_hex.strip().lower()
    raw = bytes.fromhex(git_hex)
    if len(raw) == 20:
        return b"\x00" * 12 + raw
    if len(raw) == 32:
        return raw
    raise InputResolutionError("Unexpected git hash length; expected SHA-1 or SHA-256.")


def _resolve_git_bytes(repo_root: Path) -> bytes:
    env_hash = os.environ.get("ENGINE_GIT_COMMIT")
    if env_hash:
        return _git_hex_to_bytes(env_hash)
    git_file = repo_root / "ci" / "manifests" / "git_commit_hash.txt"
    if git_file.exists():
        return _git_hex_to_bytes(git_file.read_text(encoding="utf-8").strip())
    try:
        output = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root)
        return _git_hex_to_bytes(output.decode("utf-8").strip())
    except Exception as exc:  # pragma: no cover - fallback when git unavailable
        raise InputResolutionError("Unable to resolve git commit hash.") from exc


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


def _event_has_rows(paths: Iterable[Path]) -> bool:
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    return True
    return False


def _segment_state_runs_path(
    run_paths: RunPaths, dictionary: dict, utc_day: str
) -> Path:
    entry = find_dataset_entry(dictionary, "segment_state_runs").entry
    path_template = entry["path"]
    path = path_template.replace("{utc_day}", utc_day)
    return run_paths.run_root / path


def _require_pass_receipt(
    receipt_path: Path, passed_flag_path: Path, detail: str
) -> None:
    if not receipt_path.exists() or not passed_flag_path.exists():
        raise EngineFailure(
            "F4",
            "E_PASS_GATE_MISSING",
            "S8",
            MODULE_NAME,
            {"detail": detail},
        )
    expected_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    flag_contents = passed_flag_path.read_text(encoding="ascii").strip()
    if flag_contents != f"sha256_hex = {expected_hash}":
        raise EngineFailure(
            "F4",
            "E_PASS_GATE_MISSING",
            "S8",
            MODULE_NAME,
            {"detail": f"{detail}_hash_mismatch"},
        )

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
                    "E_ORDER_AUTHORITY_DRIFT",
                    "S8",
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
                "E_ORDER_AUTHORITY_DRIFT",
                "S8",
                MODULE_NAME,
                {"detail": "candidate_rank_not_contiguous", "merchant_id": mid},
                dataset_id=DATASET_CANDIDATE_SET,
            )
        expected_rank += 1
        country_iso = str(row["country_iso"])
        if country_iso not in iso_set:
            raise EngineFailure(
                "F4",
                "E_FK_ISO_INVALID",
                "S8",
                MODULE_NAME,
                {"detail": "unknown_country_iso", "country_iso": country_iso},
                dataset_id=DATASET_CANDIDATE_SET,
            )
        if row.get("parameter_hash") != parameter_hash:
            raise EngineFailure(
                "F4",
                "E_PATH_EMBED_MISMATCH",
                "S8",
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
                "S8",
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
                "S8",
                MODULE_NAME,
                {"detail": "invalid_filter_tags", "merchant_id": mid},
                dataset_id=DATASET_CANDIDATE_SET,
            )
        is_home = bool(row["is_home"])
        if is_home and rank != 0:
            raise EngineFailure(
                "F4",
                "E_ORDER_AUTHORITY_DRIFT",
                "S8",
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
                "E_ORDER_AUTHORITY_DRIFT",
                "S8",
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
                "S8",
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
                "S8",
                MODULE_NAME,
                {"line": line_no},
                dataset_id=DATASET_NB_FINAL,
            )
        if payload.get("rng_counter_before_hi") != payload.get("rng_counter_after_hi") or payload.get(
            "rng_counter_before_lo"
        ) != payload.get("rng_counter_after_lo"):
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S8",
                MODULE_NAME,
                {"line": line_no, "detail": "nb_final_counter_mismatch"},
                dataset_id=DATASET_NB_FINAL,
            )
        if payload.get("blocks") != 0 or payload.get("draws") != "0":
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S8",
                MODULE_NAME,
                {"line": line_no, "detail": "nb_final_consuming"},
                dataset_id=DATASET_NB_FINAL,
            )
        merchant_id = int(payload["merchant_id"])
        if merchant_id in events:
            raise EngineFailure(
                "F4",
                "E_DUP_PK",
                "S8",
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
                "S8",
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
                "S8",
                MODULE_NAME,
                {"line": line_no},
                dataset_id=DATASET_ZTP_FINAL,
            )
        merchant_id = int(payload["merchant_id"])
        if merchant_id in events:
            raise EngineFailure(
                "F4",
                "E_DUP_PK",
                "S8",
                MODULE_NAME,
                {"merchant_id": merchant_id, "detail": "duplicate_ztp_final"},
                dataset_id=DATASET_ZTP_FINAL,
            )
        events[merchant_id] = payload
    return events


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
                "E_PATH_EMBED_MISMATCH",
                "S8",
                MODULE_NAME,
                {"detail": "membership_partition_mismatch"},
                dataset_id=DATASET_MEMBERSHIP,
            )
        merchant_id = int(row["merchant_id"])
        country_iso = str(row["country_iso"])
        if merchant_id not in candidate_index:
            raise EngineFailure(
                "F4",
                "E_S3_MEMBERSHIP_MISSING",
                "S8",
                MODULE_NAME,
                {"detail": "membership_unknown_merchant", "merchant_id": merchant_id},
                dataset_id=DATASET_MEMBERSHIP,
            )
        if country_iso not in candidate_index[merchant_id]:
            raise EngineFailure(
                "F4",
                "E_S3_MEMBERSHIP_MISSING",
                "S8",
                MODULE_NAME,
                {"detail": "membership_not_in_candidate_set", "merchant_id": merchant_id},
                dataset_id=DATASET_MEMBERSHIP,
            )
        if candidate_index[merchant_id][country_iso]["is_home"]:
            raise EngineFailure(
                "F4",
                "E_S3_MEMBERSHIP_MISSING",
                "S8",
                MODULE_NAME,
                {"detail": "membership_includes_home", "merchant_id": merchant_id},
                dataset_id=DATASET_MEMBERSHIP,
            )
        members = membership.setdefault(merchant_id, set())
        if country_iso in members:
            raise EngineFailure(
                "F4",
                "E_DUP_PK",
                "S8",
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
                "S8",
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
                "E_PATH_EMBED_MISMATCH",
                "S8",
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
                "E_S3_MEMBERSHIP_MISSING",
                "S8",
                MODULE_NAME,
                {"detail": "gumbel_unknown_merchant", "merchant_id": merchant_id},
                dataset_id=DATASET_GUMBEL,
            )
        if country_iso not in candidate_index[merchant_id]:
            raise EngineFailure(
                "F4",
                "E_S3_MEMBERSHIP_MISSING",
                "S8",
                MODULE_NAME,
                {"detail": "gumbel_not_in_candidate_set", "merchant_id": merchant_id},
                dataset_id=DATASET_GUMBEL,
            )
        if candidate_index[merchant_id][country_iso]["is_home"]:
            raise EngineFailure(
                "F4",
                "E_S3_MEMBERSHIP_MISSING",
                "S8",
                MODULE_NAME,
                {"detail": "gumbel_includes_home", "merchant_id": merchant_id},
                dataset_id=DATASET_GUMBEL,
            )
        if payload.get("selection_order") is None:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S8",
                MODULE_NAME,
                {"detail": "missing_selection_order", "merchant_id": merchant_id},
                dataset_id=DATASET_GUMBEL,
            )
        members = membership.setdefault(merchant_id, set())
        if country_iso in members:
            raise EngineFailure(
                "F4",
                "E_DUP_PK",
                "S8",
                MODULE_NAME,
                {"detail": "duplicate_selected", "merchant_id": merchant_id},
                dataset_id=DATASET_GUMBEL,
            )
        members.add(country_iso)
    return membership

def _load_counts_from_s3(
    df: pl.DataFrame,
    parameter_hash: str,
    candidate_index: dict[int, dict[str, dict]],
) -> dict[int, dict[str, dict]]:
    counts: dict[int, dict[str, dict]] = {}
    for row in df.select(
        ["merchant_id", "country_iso", "count", "residual_rank", "parameter_hash"]
    ).iter_rows(named=True):
        if row["parameter_hash"] != parameter_hash:
            raise EngineFailure(
                "F4",
                "E_PATH_EMBED_MISMATCH",
                "S8",
                MODULE_NAME,
                {"detail": "integerised_counts_parameter_hash"},
                dataset_id=DATASET_COUNTS,
            )
        merchant_id = int(row["merchant_id"])
        country_iso = str(row["country_iso"])
        if merchant_id not in candidate_index:
            raise EngineFailure(
                "F4",
                "E_S3_MEMBERSHIP_MISSING",
                "S8",
                MODULE_NAME,
                {"detail": "counts_unknown_merchant", "merchant_id": merchant_id},
                dataset_id=DATASET_COUNTS,
            )
        if country_iso not in candidate_index[merchant_id]:
            raise EngineFailure(
                "F4",
                "E_S3_MEMBERSHIP_MISSING",
                "S8",
                MODULE_NAME,
                {"detail": "counts_unknown_country", "merchant_id": merchant_id},
                dataset_id=DATASET_COUNTS,
            )
        count = int(row["count"])
        if count < 0:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S8",
                MODULE_NAME,
                {"detail": "count_negative", "merchant_id": merchant_id},
                dataset_id=DATASET_COUNTS,
            )
        residual_rank = int(row["residual_rank"])
        merchant_counts = counts.setdefault(merchant_id, {})
        if country_iso in merchant_counts:
            raise EngineFailure(
                "F4",
                "E_DUP_PK",
                "S8",
                MODULE_NAME,
                {"detail": "duplicate_count", "merchant_id": merchant_id},
                dataset_id=DATASET_COUNTS,
            )
        merchant_counts[country_iso] = {
            "count": count,
            "residual_rank": residual_rank,
            "candidate_rank": candidate_index[merchant_id][country_iso]["candidate_rank"],
        }
    return counts


def _load_counts_handoff(
    path: Path,
    seed: int,
    parameter_hash: str,
    run_id: str,
    manifest_fingerprint: str,
    candidate_index: dict[int, dict[str, dict]],
) -> dict[int, dict[str, dict]]:
    if not path.exists():
        raise InputResolutionError(f"Missing counts handoff file: {path}")
    counts: dict[int, dict[str, dict]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if (
                payload.get("seed") != seed
                or payload.get("parameter_hash") != parameter_hash
                or payload.get("run_id") != run_id
                or payload.get("manifest_fingerprint") != manifest_fingerprint
            ):
                raise EngineFailure(
                    "F4",
                    "E_PATH_EMBED_MISMATCH",
                    "S8",
                    MODULE_NAME,
                    {"path": path.as_posix(), "line": line_no},
                    dataset_id=DATASET_COUNTS,
                )
            merchant_id = int(payload["merchant_id"])
            country_iso = str(payload["country_iso"])
            if merchant_id not in candidate_index:
                raise EngineFailure(
                    "F4",
                    "E_S3_MEMBERSHIP_MISSING",
                    "S8",
                    MODULE_NAME,
                    {"detail": "handoff_unknown_merchant", "merchant_id": merchant_id},
                    dataset_id=DATASET_COUNTS,
                )
            if country_iso not in candidate_index[merchant_id]:
                raise EngineFailure(
                    "F4",
                    "E_S3_MEMBERSHIP_MISSING",
                    "S8",
                    MODULE_NAME,
                    {"detail": "handoff_unknown_country", "merchant_id": merchant_id},
                    dataset_id=DATASET_COUNTS,
                )
            count = int(payload["count"])
            if count < 0:
                raise EngineFailure(
                    "F4",
                    "E_SCHEMA_INVALID",
                    "S8",
                    MODULE_NAME,
                    {"detail": "handoff_count_negative", "merchant_id": merchant_id},
                    dataset_id=DATASET_COUNTS,
                )
            residual_rank = int(payload["residual_rank"])
            candidate_rank = int(payload.get("candidate_rank", -1))
            expected_rank = int(
                candidate_index[merchant_id][country_iso]["candidate_rank"]
            )
            if candidate_rank != expected_rank:
                raise EngineFailure(
                    "F4",
                    "E_ORDER_AUTHORITY_DRIFT",
                    "S8",
                    MODULE_NAME,
                    {"detail": "candidate_rank_mismatch", "merchant_id": merchant_id},
                    dataset_id=DATASET_COUNTS,
                )
            merchant_counts = counts.setdefault(merchant_id, {})
            if country_iso in merchant_counts:
                raise EngineFailure(
                    "F4",
                    "E_DUP_PK",
                    "S8",
                    MODULE_NAME,
                    {"detail": "duplicate_handoff", "merchant_id": merchant_id},
                    dataset_id=DATASET_COUNTS,
                )
            merchant_counts[country_iso] = {
                "count": count,
                "residual_rank": residual_rank,
                "candidate_rank": candidate_rank,
            }
    return counts


def _load_site_sequence(
    df: pl.DataFrame, parameter_hash: str
) -> dict[int, dict[str, set[int]]]:
    sequences: dict[int, dict[str, set[int]]] = {}
    for row in df.select(
        ["merchant_id", "country_iso", "site_order", "parameter_hash"]
    ).iter_rows(named=True):
        if row["parameter_hash"] != parameter_hash:
            raise EngineFailure(
                "F4",
                "E_PATH_EMBED_MISMATCH",
                "S8",
                MODULE_NAME,
                {"detail": "site_sequence_parameter_hash"},
                dataset_id=DATASET_SITE_SEQUENCE,
            )
        merchant_id = int(row["merchant_id"])
        country_iso = str(row["country_iso"])
        site_order = int(row["site_order"])
        merchant_seq = sequences.setdefault(merchant_id, {})
        orders = merchant_seq.setdefault(country_iso, set())
        if site_order in orders:
            raise EngineFailure(
                "F4",
                "E_DUP_PK",
                "S8",
                MODULE_NAME,
                {"detail": "duplicate_site_order", "merchant_id": merchant_id},
                dataset_id=DATASET_SITE_SEQUENCE,
            )
        orders.add(site_order)
    return sequences


def _load_existing_sequence_events(
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
                "S8",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no, "detail": errors[0].message},
                dataset_id=DATASET_SEQUENCE_FINALIZE,
            )
        if (
            payload.get("seed") != seed
            or payload.get("parameter_hash") != parameter_hash
            or payload.get("run_id") != run_id
        ):
            raise EngineFailure(
                "F4",
                "E_PATH_EMBED_MISMATCH",
                "S8",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no},
                dataset_id=DATASET_SEQUENCE_FINALIZE,
            )
        merchant_id = int(payload["merchant_id"])
        country_iso = str(payload["country_iso"])
        merchant_events = events.setdefault(merchant_id, {})
        if country_iso in merchant_events:
            raise EngineFailure(
                "F4",
                "E_DUP_PK",
                "S8",
                MODULE_NAME,
                {"detail": "duplicate_sequence_finalize", "merchant_id": merchant_id},
                dataset_id=DATASET_SEQUENCE_FINALIZE,
            )
        merchant_events[country_iso] = payload
    return events


def _load_existing_overflow_events(
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
                "S8",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no, "detail": errors[0].message},
                dataset_id=DATASET_SEQUENCE_OVERFLOW,
            )
        if (
            payload.get("seed") != seed
            or payload.get("parameter_hash") != parameter_hash
            or payload.get("run_id") != run_id
        ):
            raise EngineFailure(
                "F4",
                "E_PATH_EMBED_MISMATCH",
                "S8",
                MODULE_NAME,
                {"path": path.as_posix(), "line": line_no},
                dataset_id=DATASET_SEQUENCE_OVERFLOW,
            )
        merchant_id = int(payload["merchant_id"])
        country_iso = str(payload["country_iso"])
        merchant_events = events.setdefault(merchant_id, {})
        if country_iso in merchant_events:
            raise EngineFailure(
                "F4",
                "E_DUP_PK",
                "S8",
                MODULE_NAME,
                {"detail": "duplicate_site_sequence_overflow", "merchant_id": merchant_id},
                dataset_id=DATASET_SEQUENCE_OVERFLOW,
            )
        merchant_events[country_iso] = payload
    return events


def _assert_same_frame(
    expected: pl.DataFrame, actual: pl.DataFrame, sort_keys: list[str], dataset_id: str
) -> None:
    expected_sorted = expected.sort(sort_keys)
    actual_sorted = actual.sort(sort_keys)
    if expected_sorted.columns != actual_sorted.columns:
        raise EngineFailure(
            "F4",
            "E_SCHEMA_INVALID",
            "S8",
            MODULE_NAME,
            {"dataset_id": dataset_id, "detail": "columns_mismatch"},
            dataset_id=dataset_id,
        )
    if expected_sorted.height != actual_sorted.height:
        raise EngineFailure(
            "F4",
            "E_SCHEMA_INVALID",
            "S8",
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
                "E_SCHEMA_INVALID",
                "S8",
                MODULE_NAME,
                {"dataset_id": dataset_id, "detail": "value_mismatch"},
                dataset_id=dataset_id,
            )

def run_s8(
    config: EngineConfig,
    run_id: Optional[str] = None,
    validate_only: bool = False,
) -> S8RunResult:
    logger = get_logger("engine.layers.l1.seg_1A.s8_outlet_catalogue.l2.runner")
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
    timer.info(f"S8: loaded run receipt {receipt_path}")
    if validate_only:
        logger.info("S8: validate-only enabled; outputs will not be written")

    utc_day = utc_day_from_receipt(receipt)
    segment_state_runs_path = _segment_state_runs_path(run_paths, dictionary, utc_day)

    def _emit_state_run(status: str, detail: Optional[str] = None) -> None:
        payload = {
            "layer": "layer1",
            "segment": "1A",
            "state": "S8",
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
            "state": "S8",
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
        missing = {DATASET_ISO, DATASET_S3_INTEGERISATION_POLICY} - sealed_ids
        if missing:
            raise InputResolutionError(
                f"sealed_inputs_1A missing required assets: {sorted(missing)}"
            )
        iso_path = _sealed_path(sealed_inputs, DATASET_ISO)
        iso_df = pl.read_parquet(iso_path)
        validate_dataframe(iso_df.iter_rows(named=True), schema_ingress, DATASET_ISO)
        if "country_iso" not in iso_df.columns:
            raise InputResolutionError("iso3166_canonical_2024 missing country_iso column")
        iso_set = set(iso_df.get_column("country_iso").to_list())
        timer.info(f"S8: loaded iso3166 rows={iso_df.height}")

        s3_integerisation_path = _sealed_path(
            sealed_inputs, DATASET_S3_INTEGERISATION_POLICY
        )
        s3_integerisation_policy = _load_s3_integerisation_policy(
            s3_integerisation_path, schema_layer1
        )
        emit_s3_counts = s3_integerisation_policy.emit_integerised_counts
        emit_s3_site_sequence = s3_integerisation_policy.emit_site_sequence
        consume_s3_counts = (
            emit_s3_counts and s3_integerisation_policy.consume_integerised_counts_in_s8
        )
        consume_s3_site_sequence = (
            emit_s3_site_sequence
            and s3_integerisation_policy.consume_site_sequence_in_s8
        )
        if (
            s3_integerisation_policy.consume_integerised_counts_in_s8
            and not emit_s3_counts
        ):
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S8",
                MODULE_NAME,
                {"detail": "consume_counts_in_s8 requires emit_integerised_counts"},
            )
        if (
            s3_integerisation_policy.consume_site_sequence_in_s8
            and not emit_s3_site_sequence
        ):
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S8",
                MODULE_NAME,
                {"detail": "consume_site_sequence_in_s8 requires emit_site_sequence"},
            )
        if consume_s3_site_sequence and not consume_s3_counts:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S8",
                MODULE_NAME,
                {"detail": "consuming site_sequence requires consuming integerised_counts"},
            )
        timer.info(
            f"S8: integerisation_policy emit_counts={emit_s3_counts} "
            f"emit_site_sequence={emit_s3_site_sequence} "
            f"consume_counts={consume_s3_counts} "
            f"consume_site_sequence={consume_s3_site_sequence}"
        )

        candidate_entry = find_dataset_entry(dictionary, DATASET_CANDIDATE_SET).entry
        candidate_root = _resolve_run_path(
            run_paths, candidate_entry["path"], {"parameter_hash": parameter_hash}
        )
        candidate_file = _select_dataset_file(DATASET_CANDIDATE_SET, candidate_root)
        candidate_df = pl.read_parquet(candidate_file)
        validate_dataframe(
            candidate_df.iter_rows(named=True),
            _schema_section(schema_1a, "s3"),
            "candidate_set",
        )
        candidate_map = _build_candidate_map(candidate_df, parameter_hash, iso_set)
        if not candidate_map:
            raise InputResolutionError("S3 candidate set is empty.")
        candidate_index = _candidate_index(candidate_map)
        timer.info(f"S8: loaded candidate_set merchants={len(candidate_map)}")

        seq_entry = find_dataset_entry(dictionary, DATASET_SEQUENCE_FINALIZE).entry
        seq_paths = _resolve_run_glob(run_paths, seq_entry["path"], tokens)
        seq_event_dir = _resolve_event_dir(run_paths, seq_entry["path"], tokens)
        seq_event_path = _resolve_event_path(run_paths, seq_entry["path"], tokens)
        existing_sequence_events = _event_has_rows(seq_paths)

        overflow_entry = find_dataset_entry(dictionary, DATASET_SEQUENCE_OVERFLOW).entry
        overflow_paths = _resolve_run_glob(run_paths, overflow_entry["path"], tokens)
        overflow_event_dir = _resolve_event_dir(run_paths, overflow_entry["path"], tokens)
        overflow_event_path = _resolve_event_path(run_paths, overflow_entry["path"], tokens)
        existing_overflow_events = _event_has_rows(overflow_paths)

        trace_entry = find_dataset_entry(dictionary, DATASET_TRACE).entry
        trace_path = _resolve_run_path(run_paths, trace_entry["path"], tokens)
        existing_sequence_trace = _trace_has_substream(
            trace_path, MODULE_NAME, SUBSTREAM_SEQUENCE
        )
        existing_overflow_trace = _trace_has_substream(
            trace_path, MODULE_NAME, SUBSTREAM_OVERFLOW
        )

        outlet_entry = find_dataset_entry(dictionary, DATASET_OUTLET).entry
        outlet_root = _resolve_run_path(run_paths, outlet_entry["path"], tokens)
        outlet_exists = _dataset_has_parquet(outlet_root)

        had_existing_outputs = (
            existing_sequence_events
            or existing_overflow_events
            or existing_sequence_trace
            or existing_overflow_trace
            or outlet_exists
        )
        if had_existing_outputs:
            logger.info("S8: existing outputs detected; validating only")
            validate_only = True

        audit_entry = find_dataset_entry(dictionary, DATASET_AUDIT).entry
        audit_path = _resolve_run_path(run_paths, audit_entry["path"], tokens)
        audit_schema = _schema_from_pack(schema_layer1, "rng/core/rng_audit_log/record")
        audit_validator = Draft202012Validator(audit_schema)
        if _audit_has_entry(audit_path, seed, parameter_hash, run_id):
            logger.info("S8: rng_audit_log entry present")
        elif validate_only:
            raise InputResolutionError(
                "rng_audit_log missing required audit row for "
                f"seed={seed} parameter_hash={parameter_hash} run_id={run_id}"
            )
        else:
            git_bytes = _resolve_git_bytes(config.repo_root)
            audit_payload = {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": run_id,
                "seed": seed,
                "manifest_fingerprint": manifest_fingerprint,
                "parameter_hash": parameter_hash,
                "algorithm": "philox2x64-10",
                "build_commit": git_bytes.hex(),
                "code_digest": None,
                "hostname": None,
                "platform": None,
                "notes": None,
            }
            errors = list(audit_validator.iter_errors(audit_payload))
            if errors:
                raise EngineFailure(
                    "F4",
                    "E_SCHEMA_INVALID",
                    "S8",
                    MODULE_NAME,
                    {"detail": errors[0].message},
                    dataset_id="rng_audit_log",
                )
            _append_jsonl(audit_path, audit_payload)
            logger.info("S8: appended rng_audit_log entry")
        nb_entry = find_dataset_entry(dictionary, DATASET_NB_FINAL).entry
        nb_paths = _resolve_run_glob(run_paths, nb_entry["path"], tokens)
        nb_map = _load_nb_final_events(nb_paths, schema_layer1, seed, parameter_hash, run_id)
        timer.info(f"S8: loaded nb_final events={len(nb_map)}")

        ztp_entry = find_dataset_entry(dictionary, DATASET_ZTP_FINAL).entry
        ztp_paths = _resolve_run_glob(run_paths, ztp_entry["path"], tokens)
        ztp_map = _load_ztp_final_events(ztp_paths, schema_layer1, seed, parameter_hash, run_id)
        timer.info(f"S8: loaded ztp_final events={len(ztp_map)}")

        scope_merchants = sorted(set(candidate_map) & set(nb_map))
        missing_nb = set(candidate_map) - set(nb_map)
        if missing_nb:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_INVALID",
                "S8",
                MODULE_NAME,
                {
                    "detail": "missing_nb_final_for_candidate_merchants",
                    "count": len(missing_nb),
                },
                dataset_id=DATASET_NB_FINAL,
            )
        missing_ztp = set(scope_merchants) - set(ztp_map)
        if missing_ztp:
            logger.info(
                "S8: merchants without ztp_final will be projected as home-only count=%d",
                len(missing_ztp),
            )

        receipt_entry = find_dataset_entry(dictionary, DATASET_S6_RECEIPT).entry
        receipt_dir = _resolve_run_path(
            run_paths, receipt_entry["path"], {"seed": str(seed), "parameter_hash": parameter_hash}
        )
        receipt_path = receipt_dir / "S6_VALIDATION.json"
        passed_flag_path = receipt_dir / "_passed.flag"

        membership_entry = find_dataset_entry(dictionary, DATASET_MEMBERSHIP).entry
        membership_root = _resolve_run_path(
            run_paths,
            membership_entry["path"],
            {"seed": str(seed), "parameter_hash": parameter_hash},
        )
        membership_map: dict[int, set[str]] = {}
        membership_source = "gumbel_key"
        if _dataset_has_parquet(membership_root):
            _require_pass_receipt(receipt_path, passed_flag_path, "s6_membership")
            membership_df = pl.read_parquet(
                _select_dataset_file(DATASET_MEMBERSHIP, membership_root)
            )
            validate_dataframe(
                membership_df.iter_rows(named=True),
                _schema_section(schema_1a, "alloc"),
                "membership",
            )
            membership_map = _load_membership(
                membership_df, seed, parameter_hash, candidate_index
            )
            membership_source = "s6_membership"
            timer.info(f"S8: loaded membership rows={membership_df.height}")
        else:
            _require_pass_receipt(receipt_path, passed_flag_path, "gumbel_key")
            gumbel_entry = find_dataset_entry(dictionary, DATASET_GUMBEL).entry
            gumbel_paths = _resolve_run_glob(run_paths, gumbel_entry["path"], tokens)
            membership_map = _load_selected_gumbel_events(
                gumbel_paths, schema_layer1, seed, parameter_hash, run_id, candidate_index
            )
            membership_source = "gumbel_key"
            timer.info("S8: reconstructed membership from gumbel_key")

        counts_map: dict[int, dict[str, dict]] = {}
        counts_source = "s7_counts_handoff"
        if consume_s3_counts:
            counts_entry = find_dataset_entry(dictionary, DATASET_COUNTS).entry
            counts_root = _resolve_run_path(
                run_paths, counts_entry["path"], {"parameter_hash": parameter_hash}
            )
            if not _dataset_has_parquet(counts_root):
                raise EngineFailure(
                    "F4",
                    "E_COUNTS_SOURCE_MISSING",
                    "S8",
                    MODULE_NAME,
                    {"detail": "s3_integerised_counts_missing"},
                    dataset_id=DATASET_COUNTS,
                )
            counts_df = pl.read_parquet(
                _select_dataset_file(DATASET_COUNTS, counts_root)
            )
            validate_dataframe(
                counts_df.iter_rows(named=True),
                _schema_section(schema_1a, "s3"),
                "integerised_counts",
            )
            counts_map = _load_counts_from_s3(counts_df, parameter_hash, candidate_index)
            counts_source = "s3_integerised_counts"
            timer.info(f"S8: loaded s3_integerised_counts rows={counts_df.height}")
        else:
            counts_path = run_paths.tmp_root / "s7_integerisation" / COUNTS_HANDOFF_FILENAME
            try:
                counts_map = _load_counts_handoff(
                    counts_path,
                    seed,
                    parameter_hash,
                    run_id,
                    manifest_fingerprint,
                    candidate_index,
                )
            except InputResolutionError as exc:
                raise EngineFailure(
                    "F4",
                    "E_COUNTS_SOURCE_MISSING",
                    "S8",
                    MODULE_NAME,
                    {"detail": "s7_counts_handoff_missing", "path": counts_path.as_posix()},
                ) from exc
            timer.info(
                f"S8: loaded counts handoff rows={sum(len(v) for v in counts_map.values())}"
            )

        if not counts_map:
            raise EngineFailure(
                "F4",
                "E_COUNTS_SOURCE_MISSING",
                "S8",
                MODULE_NAME,
                {"detail": "counts_source_empty", "source": counts_source},
                dataset_id=DATASET_COUNTS,
            )

        if counts_source == "s3_integerised_counts":
            mismatch_detail = None
            for merchant_id, counts_for_merchant in counts_map.items():
                rows = candidate_map.get(merchant_id, [])
                membership_set = membership_map.get(merchant_id, set())
                domain_isos = {
                    row["country_iso"]
                    for row in rows
                    if row["is_home"] or row["country_iso"] in membership_set
                }
                for country_iso, entry in counts_for_merchant.items():
                    if country_iso in domain_isos:
                        continue
                    if int(entry["count"]) > 0:
                        mismatch_detail = {
                            "merchant_id": merchant_id,
                            "country_iso": country_iso,
                        }
                        break
                if mismatch_detail:
                    break
            if mismatch_detail:
                raise EngineFailure(
                    "F4",
                    "E_S3_MEMBERSHIP_MISSING",
                    "S8",
                    MODULE_NAME,
                    {
                        "detail": "counts_outside_domain",
                        "merchant_id": mismatch_detail["merchant_id"],
                        "country_iso": mismatch_detail["country_iso"],
                    },
                    dataset_id=DATASET_COUNTS,
                )

        site_sequence_map: dict[int, dict[str, set[int]]] | None = None
        if consume_s3_site_sequence:
            site_sequence_entry = find_dataset_entry(
                dictionary, DATASET_SITE_SEQUENCE
            ).entry
            site_sequence_root = _resolve_run_path(
                run_paths, site_sequence_entry["path"], {"parameter_hash": parameter_hash}
            )
            if not _dataset_has_parquet(site_sequence_root):
                raise EngineFailure(
                    "F4",
                    "E_SEQUENCE_DIVERGENCE",
                    "S8",
                    MODULE_NAME,
                    {"detail": "site_sequence_missing"},
                    dataset_id=DATASET_SITE_SEQUENCE,
                )
            site_sequence_df = pl.read_parquet(
                _select_dataset_file(DATASET_SITE_SEQUENCE, site_sequence_root)
            )
            validate_dataframe(
                site_sequence_df.iter_rows(named=True),
                _schema_section(schema_1a, "s3"),
                "site_sequence",
            )
            site_sequence_map = _load_site_sequence(site_sequence_df, parameter_hash)
            timer.info(f"S8: loaded site_sequence rows={site_sequence_df.height}")

        sequence_validator = Draft202012Validator(
            _schema_from_pack(schema_layer1, "rng/events/sequence_finalize")
        )
        overflow_validator = Draft202012Validator(
            _schema_from_pack(schema_layer1, "rng/events/site_sequence_overflow")
        )
        trace_validator = Draft202012Validator(
            _schema_from_pack(schema_layer1, "rng/core/rng_trace_log/record")
        )

        existing_sequence_map: dict[int, dict[str, dict]] | None = None
        if existing_sequence_events:
            existing_sequence_map = _load_existing_sequence_events(
                seq_paths, sequence_validator, seed, parameter_hash, run_id
            )
        existing_overflow_map: dict[int, dict[str, dict]] | None = None
        if existing_overflow_events:
            existing_overflow_map = _load_existing_overflow_events(
                overflow_paths, overflow_validator, seed, parameter_hash, run_id
            )

        master_material = derive_master_material(bytes.fromhex(parameter_hash), seed)
        def _expected_sequence_payload(
            merchant_id: int,
            country_iso: str,
            site_count: int,
        ) -> dict:
            _key, ctr_hi, ctr_lo = derive_substream(
                master_material, SUBSTREAM_SEQUENCE, merchant_u64(merchant_id), country_iso
            )
            return {
                "seed": seed,
                "run_id": run_id,
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": MODULE_NAME,
                "substream_label": SUBSTREAM_SEQUENCE,
                "rng_counter_before_lo": ctr_lo,
                "rng_counter_before_hi": ctr_hi,
                "rng_counter_after_lo": ctr_lo,
                "rng_counter_after_hi": ctr_hi,
                "draws": "0",
                "blocks": 0,
                "merchant_id": merchant_id,
                "country_iso": country_iso,
                "site_count": site_count,
                "start_sequence": str(1).zfill(6),
                "end_sequence": str(site_count).zfill(6),
            }

        def _expected_overflow_payload(
            merchant_id: int,
            country_iso: str,
            attempted_count: int,
        ) -> dict:
            _key, ctr_hi, ctr_lo = derive_substream(
                master_material, SUBSTREAM_OVERFLOW, merchant_u64(merchant_id), country_iso
            )
            overflow_by = attempted_count - 999999
            return {
                "seed": seed,
                "run_id": run_id,
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": MODULE_NAME,
                "substream_label": SUBSTREAM_OVERFLOW,
                "rng_counter_before_lo": ctr_lo,
                "rng_counter_before_hi": ctr_hi,
                "rng_counter_after_lo": ctr_lo,
                "rng_counter_after_hi": ctr_hi,
                "draws": "0",
                "blocks": 0,
                "merchant_id": merchant_id,
                "country_iso": country_iso,
                "attempted_count": attempted_count,
                "max_seq": 999999,
                "overflow_by": overflow_by,
                "severity": "ERROR",
            }

        metrics = {
            "s8.merchants_in_scope": 0,
            "s8.merchants_single": 0,
            "s8.merchants_without_ztp": 0,
            "s8.merchants_overflow": 0,
            "s8.events.sequence_finalize.rows": 0,
            "s8.events.site_sequence_overflow.rows": 0,
            "s8.trace.rows": 0,
            "s8.outlet.rows": 0,
        }

        expected_sequence_events = 0
        expected_overflow_events = 0
        expected_sequence_keys: set[tuple[int, str]] = set()
        expected_overflow_keys: set[tuple[int, str]] = set()

        sequence_trace_acc = _TraceAccumulator(MODULE_NAME, SUBSTREAM_SEQUENCE)
        overflow_trace_acc = _TraceAccumulator(MODULE_NAME, SUBSTREAM_OVERFLOW)

        tmp_dir = run_paths.tmp_root / "s8_outlet_catalogue"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_sequence_path = tmp_dir / "rng_event_sequence_finalize.jsonl"
        tmp_overflow_path = tmp_dir / "rng_event_site_sequence_overflow.jsonl"
        tmp_trace_path = tmp_dir / "rng_trace_log_s8.jsonl"

        sequence_written = 0
        overflow_written = 0
        trace_written = 0
        outlet_rows: list[dict] = []

        total_merchants = len(scope_merchants)
        progress_every = max(1, min(10_000, total_merchants // 10)) if total_merchants else 1
        start_time = time.monotonic()
        logger.info(
            "S8: starting outlet materialization merchants_in_scope=%d (membership_source=%s, counts_source=%s)",
            total_merchants,
            membership_source,
            counts_source,
        )

        sequence_handle = None
        overflow_handle = None
        trace_handle = None
        try:
            if not validate_only:
                sequence_handle = tmp_sequence_path.open("w", encoding="utf-8")
                overflow_handle = tmp_overflow_path.open("w", encoding="utf-8")
                trace_handle = tmp_trace_path.open("w", encoding="utf-8")

            for idx, merchant_id in enumerate(scope_merchants, start=1):
                if idx % progress_every == 0 or idx == total_merchants:
                    elapsed = max(time.monotonic() - start_time, 1e-9)
                    rate = idx / elapsed
                    eta = (total_merchants - idx) / rate if rate > 0 else 0.0
                    logger.info(
                        "S8 progress merchants_processed=%d/%d (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
                        idx,
                        total_merchants,
                        elapsed,
                        rate,
                        eta,
                    )

                metrics["s8.merchants_in_scope"] += 1
                nb_payload = nb_map.get(merchant_id)
                if nb_payload is None:
                    raise EngineFailure(
                        "F4",
                        "E_SCHEMA_INVALID",
                        "S8",
                        MODULE_NAME,
                        {"detail": "missing_nb_final", "merchant_id": merchant_id},
                        dataset_id=DATASET_NB_FINAL,
                    )
                n_outlets = int(nb_payload["n_outlets"])

                rows = candidate_map[merchant_id]
                home_iso = None
                for row in rows:
                    if row["is_home"]:
                        home_iso = row["country_iso"]
                        break
                if home_iso is None:
                    raise EngineFailure(
                        "F4",
                        "E_ORDER_AUTHORITY_DRIFT",
                        "S8",
                        MODULE_NAME,
                        {"detail": "missing_home_row", "merchant_id": merchant_id},
                        dataset_id=DATASET_CANDIDATE_SET,
                    )

                if n_outlets < 2:
                    metrics["s8.merchants_single"] += 1
                    outlet_rows.append(
                        {
                            "manifest_fingerprint": manifest_fingerprint,
                            "merchant_id": merchant_id,
                            "site_id": str(1).zfill(6),
                            "home_country_iso": home_iso,
                            "legal_country_iso": home_iso,
                            "single_vs_multi_flag": False,
                            "raw_nb_outlet_draw": n_outlets,
                            "final_country_outlet_count": 1,
                            "site_order": 1,
                            "global_seed": seed,
                        }
                    )
                    metrics["s8.outlet.rows"] += 1
                    continue
                ztp_payload = ztp_map.get(merchant_id)
                if ztp_payload is None:
                    metrics["s8.merchants_without_ztp"] += 1
                    domain_counts = [
                        {
                            "country_iso": home_iso,
                            "count": n_outlets,
                            "candidate_rank": 0,
                        }
                    ]
                else:
                    k_target = int(ztp_payload["K_target"])
                    membership_set = membership_map.get(merchant_id, set())
                    if k_target == 0 and membership_set:
                        raise EngineFailure(
                            "F4",
                            "E_UPSTREAM_GATE",
                            "S8",
                            MODULE_NAME,
                            {"detail": "k_target_zero_but_membership", "merchant_id": merchant_id},
                        )
                    if len(membership_set) > k_target:
                        raise EngineFailure(
                            "F4",
                            "E_UPSTREAM_GATE",
                            "S8",
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
                            "E_ORDER_AUTHORITY_DRIFT",
                            "S8",
                            MODULE_NAME,
                            {"detail": "empty_domain", "merchant_id": merchant_id},
                        )
                    counts_for_merchant = counts_map.get(merchant_id)
                    if counts_for_merchant is None:
                        raise EngineFailure(
                            "F4",
                            "E_COUNTS_SOURCE_MISSING",
                            "S8",
                            MODULE_NAME,
                            {"detail": "counts_missing_merchant", "merchant_id": merchant_id},
                            dataset_id=DATASET_COUNTS,
                        )
                    domain_isos = {row["country_iso"] for row in domain_rows}
                    for country_iso, entry in counts_for_merchant.items():
                        if country_iso in domain_isos:
                            continue
                        count = int(entry["count"])
                        if count > 0:
                            raise EngineFailure(
                                "F4",
                                "E_S3_MEMBERSHIP_MISSING",
                                "S8",
                                MODULE_NAME,
                                {
                                    "detail": "counts_outside_domain",
                                    "merchant_id": merchant_id,
                                    "country_iso": country_iso,
                                },
                                dataset_id=DATASET_COUNTS,
                            )

                    domain_counts = []
                    total_count = 0
                    for row in domain_rows:
                        country_iso = row["country_iso"]
                        entry = counts_for_merchant.get(country_iso)
                        if entry is None:
                            raise EngineFailure(
                                "F4",
                                "E_COUNTS_SOURCE_MISSING",
                                "S8",
                                MODULE_NAME,
                                {"detail": "counts_missing_country", "merchant_id": merchant_id},
                                dataset_id=DATASET_COUNTS,
                            )
                        count = int(entry["count"])
                        domain_counts.append(
                            {
                                "country_iso": country_iso,
                                "count": count,
                                "candidate_rank": row["candidate_rank"],
                            }
                        )
                        total_count += count

                    if total_count != n_outlets:
                        raise EngineFailure(
                            "F4",
                            "E_SUM_MISMATCH",
                            "S8",
                            MODULE_NAME,
                            {
                                "detail": "count_sum_mismatch",
                                "merchant_id": merchant_id,
                                "expected": n_outlets,
                                "actual": total_count,
                            },
                            dataset_id=DATASET_COUNTS,
                        )

                overflow_countries = [
                    item for item in domain_counts if int(item["count"]) > 999999
                ]
                if overflow_countries:
                    metrics["s8.merchants_overflow"] += 1
                    for item in overflow_countries:
                        country_iso = item["country_iso"]
                        count = int(item["count"])
                        expected_overflow_events += 1
                        expected_overflow_keys.add((merchant_id, country_iso))
                        metrics["s8.events.site_sequence_overflow.rows"] += 1
                        metrics["s8.trace.rows"] += 1
                        expected_payload = _expected_overflow_payload(
                            merchant_id, country_iso, count
                        )
                        if existing_overflow_map is not None:
                            logged = existing_overflow_map.get(merchant_id)
                            if not logged or country_iso not in logged:
                                raise EngineFailure(
                                    "F4",
                                    "E_TRACE_COVERAGE_MISSING",
                                    "S8",
                                    MODULE_NAME,
                                    {
                                        "detail": "missing_overflow_event",
                                        "merchant_id": merchant_id,
                                    },
                                    dataset_id=DATASET_SEQUENCE_OVERFLOW,
                                )
                            payload = logged[country_iso]
                            for key, value in expected_payload.items():
                                if payload.get(key) != value:
                                    raise EngineFailure(
                                        "F4",
                                        "E_SCHEMA_INVALID",
                                        "S8",
                                        MODULE_NAME,
                                        {
                                            "detail": "overflow_field_mismatch",
                                            "merchant_id": merchant_id,
                                            "field": key,
                                        },
                                        dataset_id=DATASET_SEQUENCE_OVERFLOW,
                                    )
                        elif overflow_handle is not None:
                            payload = dict(expected_payload)
                            payload["ts_utc"] = utc_now_rfc3339_micro()
                            errors = list(overflow_validator.iter_errors(payload))
                            if errors:
                                raise EngineFailure(
                                    "F4",
                                    "E_SCHEMA_INVALID",
                                    "S8",
                                    MODULE_NAME,
                                    {"detail": errors[0].message, "merchant_id": merchant_id},
                                    dataset_id=DATASET_SEQUENCE_OVERFLOW,
                                )
                            trace = overflow_trace_acc.append(payload)
                            trace_errors = list(trace_validator.iter_errors(trace))
                            if trace_errors:
                                raise EngineFailure(
                                    "F4",
                                    "E_SCHEMA_INVALID",
                                    "S8",
                                    MODULE_NAME,
                                    {"detail": trace_errors[0].message},
                                    dataset_id=DATASET_TRACE,
                                )
                            overflow_handle.write(
                                json.dumps(payload, ensure_ascii=True, sort_keys=True)
                            )
                            overflow_handle.write("\n")
                            if trace_handle is not None:
                                trace_handle.write(
                                    json.dumps(trace, ensure_ascii=True, sort_keys=True)
                                )
                                trace_handle.write("\n")
                                trace_written += 1
                            overflow_written += 1
                    continue

                for item in domain_counts:
                    count = int(item["count"])
                    if count <= 0:
                        continue
                    country_iso = item["country_iso"]
                    expected_sequence_events += 1
                    expected_sequence_keys.add((merchant_id, country_iso))
                    metrics["s8.events.sequence_finalize.rows"] += 1
                    metrics["s8.trace.rows"] += 1
                    expected_payload = _expected_sequence_payload(
                        merchant_id, country_iso, count
                    )
                    if existing_sequence_map is not None:
                        logged = existing_sequence_map.get(merchant_id)
                        if not logged or country_iso not in logged:
                            raise EngineFailure(
                                "F4",
                                "E_TRACE_COVERAGE_MISSING",
                                "S8",
                                MODULE_NAME,
                                {
                                    "detail": "missing_sequence_finalize",
                                    "merchant_id": merchant_id,
                                },
                                dataset_id=DATASET_SEQUENCE_FINALIZE,
                            )
                        payload = logged[country_iso]
                        for key, value in expected_payload.items():
                            if payload.get(key) != value:
                                raise EngineFailure(
                                    "F4",
                                    "E_SCHEMA_INVALID",
                                    "S8",
                                    MODULE_NAME,
                                    {
                                        "detail": "sequence_field_mismatch",
                                        "merchant_id": merchant_id,
                                        "field": key,
                                    },
                                    dataset_id=DATASET_SEQUENCE_FINALIZE,
                                )
                    elif sequence_handle is not None:
                        payload = dict(expected_payload)
                        payload["ts_utc"] = utc_now_rfc3339_micro()
                        errors = list(sequence_validator.iter_errors(payload))
                        if errors:
                            raise EngineFailure(
                                "F4",
                                "E_SCHEMA_INVALID",
                                "S8",
                                MODULE_NAME,
                                {"detail": errors[0].message, "merchant_id": merchant_id},
                                dataset_id=DATASET_SEQUENCE_FINALIZE,
                            )
                        trace = sequence_trace_acc.append(payload)
                        trace_errors = list(trace_validator.iter_errors(trace))
                        if trace_errors:
                            raise EngineFailure(
                                "F4",
                                "E_SCHEMA_INVALID",
                                "S8",
                                MODULE_NAME,
                                {"detail": trace_errors[0].message},
                                dataset_id=DATASET_TRACE,
                            )
                        sequence_handle.write(
                            json.dumps(payload, ensure_ascii=True, sort_keys=True)
                        )
                        sequence_handle.write("\n")
                        if trace_handle is not None:
                            trace_handle.write(
                                json.dumps(trace, ensure_ascii=True, sort_keys=True)
                            )
                            trace_handle.write("\n")
                            trace_written += 1
                        sequence_written += 1

                    if site_sequence_map is not None:
                        merchant_seq = site_sequence_map.get(merchant_id, {})
                        orders = merchant_seq.get(country_iso)
                        if orders is None:
                            raise EngineFailure(
                                "F4",
                                "E_SEQUENCE_DIVERGENCE",
                                "S8",
                                MODULE_NAME,
                                {
                                    "detail": "site_sequence_missing",
                                    "merchant_id": merchant_id,
                                    "country_iso": country_iso,
                                },
                                dataset_id=DATASET_SITE_SEQUENCE,
                            )
                        expected_orders = set(range(1, count + 1))
                        if orders != expected_orders:
                            raise EngineFailure(
                                "F4",
                                "E_SEQUENCE_DIVERGENCE",
                                "S8",
                                MODULE_NAME,
                                {
                                    "detail": "site_sequence_mismatch",
                                    "merchant_id": merchant_id,
                                    "country_iso": country_iso,
                                },
                                dataset_id=DATASET_SITE_SEQUENCE,
                            )

                    for site_order in range(1, count + 1):
                        outlet_rows.append(
                            {
                                "manifest_fingerprint": manifest_fingerprint,
                                "merchant_id": merchant_id,
                                "site_id": str(site_order).zfill(6),
                                "home_country_iso": home_iso,
                                "legal_country_iso": country_iso,
                                "single_vs_multi_flag": True,
                                "raw_nb_outlet_draw": n_outlets,
                                "final_country_outlet_count": count,
                                "site_order": site_order,
                                "global_seed": seed,
                            }
                        )
                        metrics["s8.outlet.rows"] += 1
        finally:
            if sequence_handle is not None:
                sequence_handle.close()
            if overflow_handle is not None:
                overflow_handle.close()
            if trace_handle is not None:
                trace_handle.close()
        if site_sequence_map is not None:
            for merchant_id, countries in site_sequence_map.items():
                for country_iso, orders in countries.items():
                    if (merchant_id, country_iso) not in expected_sequence_keys and orders:
                        raise EngineFailure(
                            "F4",
                            "E_SEQUENCE_DIVERGENCE",
                            "S8",
                            MODULE_NAME,
                            {
                                "detail": "unexpected_site_sequence",
                                "merchant_id": merchant_id,
                                "country_iso": country_iso,
                            },
                            dataset_id=DATASET_SITE_SEQUENCE,
                        )

        if existing_sequence_map is not None:
            for merchant_id, events in existing_sequence_map.items():
                for country_iso in events.keys():
                    if (merchant_id, country_iso) not in expected_sequence_keys:
                        raise EngineFailure(
                            "F4",
                            "E_TRACE_COVERAGE_MISSING",
                            "S8",
                            MODULE_NAME,
                            {
                                "detail": "unexpected_sequence_finalize",
                                "merchant_id": merchant_id,
                            },
                            dataset_id=DATASET_SEQUENCE_FINALIZE,
                        )
            trace_rows = _trace_rows_for_substream(
                trace_path, MODULE_NAME, SUBSTREAM_SEQUENCE
            )
            if len(trace_rows) != expected_sequence_events:
                raise EngineFailure(
                    "F4",
                    "E_TRACE_COVERAGE_MISSING",
                    "S8",
                    MODULE_NAME,
                    {
                        "detail": "sequence_trace_row_count_mismatch",
                        "expected": expected_sequence_events,
                        "actual": len(trace_rows),
                    },
                    dataset_id=DATASET_TRACE,
                )
            for row in trace_rows:
                errors = list(trace_validator.iter_errors(row))
                if errors:
                    raise EngineFailure(
                        "F4",
                        "E_SCHEMA_INVALID",
                        "S8",
                        MODULE_NAME,
                        {"detail": errors[0].message},
                        dataset_id=DATASET_TRACE,
                    )
            if trace_rows:
                last = trace_rows[-1]
                if (
                    int(last.get("events_total", 0)) != expected_sequence_events
                    or int(last.get("blocks_total", 0)) != 0
                    or int(last.get("draws_total", 0)) != 0
                ):
                    raise EngineFailure(
                        "F4",
                        "E_TRACE_COVERAGE_MISSING",
                        "S8",
                        MODULE_NAME,
                        {"detail": "sequence_trace_totals_mismatch"},
                        dataset_id=DATASET_TRACE,
                    )
        elif had_existing_outputs and expected_sequence_events > 0:
            raise EngineFailure(
                "F4",
                "E_TRACE_COVERAGE_MISSING",
                "S8",
                MODULE_NAME,
                {"detail": "sequence_finalize_missing"},
                dataset_id=DATASET_SEQUENCE_FINALIZE,
            )

        if existing_overflow_map is not None:
            for merchant_id, events in existing_overflow_map.items():
                for country_iso in events.keys():
                    if (merchant_id, country_iso) not in expected_overflow_keys:
                        raise EngineFailure(
                            "F4",
                            "E_TRACE_COVERAGE_MISSING",
                            "S8",
                            MODULE_NAME,
                            {
                                "detail": "unexpected_site_sequence_overflow",
                                "merchant_id": merchant_id,
                            },
                            dataset_id=DATASET_SEQUENCE_OVERFLOW,
                        )
            trace_rows = _trace_rows_for_substream(
                trace_path, MODULE_NAME, SUBSTREAM_OVERFLOW
            )
            if len(trace_rows) != expected_overflow_events:
                raise EngineFailure(
                    "F4",
                    "E_TRACE_COVERAGE_MISSING",
                    "S8",
                    MODULE_NAME,
                    {
                        "detail": "overflow_trace_row_count_mismatch",
                        "expected": expected_overflow_events,
                        "actual": len(trace_rows),
                    },
                    dataset_id=DATASET_TRACE,
                )
            for row in trace_rows:
                errors = list(trace_validator.iter_errors(row))
                if errors:
                    raise EngineFailure(
                        "F4",
                        "E_SCHEMA_INVALID",
                        "S8",
                        MODULE_NAME,
                        {"detail": errors[0].message},
                        dataset_id=DATASET_TRACE,
                    )
            if trace_rows:
                last = trace_rows[-1]
                if (
                    int(last.get("events_total", 0)) != expected_overflow_events
                    or int(last.get("blocks_total", 0)) != 0
                    or int(last.get("draws_total", 0)) != 0
                ):
                    raise EngineFailure(
                        "F4",
                        "E_TRACE_COVERAGE_MISSING",
                        "S8",
                        MODULE_NAME,
                        {"detail": "overflow_trace_totals_mismatch"},
                        dataset_id=DATASET_TRACE,
                    )
        elif had_existing_outputs and expected_overflow_events > 0:
            raise EngineFailure(
                "F4",
                "E_TRACE_COVERAGE_MISSING",
                "S8",
                MODULE_NAME,
                {"detail": "site_sequence_overflow_missing"},
                dataset_id=DATASET_SEQUENCE_OVERFLOW,
            )

        if existing_sequence_map is None and sequence_written > 0 and not validate_only:
            seq_event_dir.mkdir(parents=True, exist_ok=True)
            if seq_event_path.exists():
                raise InputResolutionError(
                    f"S8 sequence_finalize output already exists: {seq_event_path}"
                )
            tmp_sequence_path.replace(seq_event_path)
        else:
            tmp_sequence_path.unlink(missing_ok=True)

        if existing_overflow_map is None and overflow_written > 0 and not validate_only:
            overflow_event_dir.mkdir(parents=True, exist_ok=True)
            if overflow_event_path.exists():
                raise InputResolutionError(
                    f"S8 site_sequence_overflow output already exists: {overflow_event_path}"
                )
            tmp_overflow_path.replace(overflow_event_path)
        else:
            tmp_overflow_path.unlink(missing_ok=True)

        if trace_written > 0 and not validate_only:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with trace_path.open("a", encoding="utf-8") as dest_handle, tmp_trace_path.open(
                "r", encoding="utf-8"
            ) as src_handle:
                for line in src_handle:
                    dest_handle.write(line)
            logger.info(
                "S8: appended trace rows count=%d (sequence_finalize=%d, site_sequence_overflow=%d)",
                trace_written,
                sequence_written,
                overflow_written,
            )
        tmp_trace_path.unlink(missing_ok=True)

        outlet_df = pl.DataFrame(
            outlet_rows,
            schema={
                "manifest_fingerprint": pl.Utf8,
                "merchant_id": pl.UInt64,
                "site_id": pl.Utf8,
                "home_country_iso": pl.Utf8,
                "legal_country_iso": pl.Utf8,
                "single_vs_multi_flag": pl.Boolean,
                "raw_nb_outlet_draw": pl.Int32,
                "final_country_outlet_count": pl.Int32,
                "site_order": pl.Int32,
                "global_seed": pl.UInt64,
            },
        ).sort(["merchant_id", "legal_country_iso", "site_order"])
        validate_dataframe(
            outlet_df.iter_rows(named=True),
            _schema_section(schema_1a, "egress"),
            "outlet_catalogue",
        )

        if outlet_exists:
            existing_df = pl.read_parquet(_select_dataset_file(DATASET_OUTLET, outlet_root))
            _assert_same_frame(
                outlet_df,
                existing_df,
                ["merchant_id", "legal_country_iso", "site_order"],
                DATASET_OUTLET,
            )
            logger.info("S8: existing outlet_catalogue validated")
        elif not validate_only:
            _write_parquet_partition(outlet_df, outlet_root, DATASET_OUTLET)
            logger.info("S8: wrote outlet_catalogue rows=%d", outlet_df.height)
        else:
            logger.info("S8: validate-only mode; outlet_catalogue not written")

        logger.info(
            "S8 summary: merchants_in_scope=%d single=%d missing_ztp=%d overflow=%d "
            "sequence_finalize_rows=%d overflow_rows=%d outlet_rows=%d",
            metrics["s8.merchants_in_scope"],
            metrics["s8.merchants_single"],
            metrics["s8.merchants_without_ztp"],
            metrics["s8.merchants_overflow"],
            metrics["s8.events.sequence_finalize.rows"],
            metrics["s8.events.site_sequence_overflow.rows"],
            metrics["s8.outlet.rows"],
        )

        timer.info("S8: completed")
        _emit_state_run("completed")

        sequence_path_out: Path | None = None
        if existing_sequence_map is not None:
            existing_paths = [path for path in seq_paths if path.exists()]
            sequence_path_out = existing_paths[0] if existing_paths else None
        elif not validate_only and sequence_written > 0:
            sequence_path_out = seq_event_path

        overflow_path_out: Path | None = None
        if existing_overflow_map is not None:
            existing_paths = [path for path in overflow_paths if path.exists()]
            overflow_path_out = existing_paths[0] if existing_paths else None
        elif not validate_only and overflow_written > 0:
            overflow_path_out = overflow_event_path

        outlet_path_out: Path | None = None
        if outlet_exists or not validate_only:
            outlet_path_out = outlet_root

        return S8RunResult(
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            outlet_path=outlet_path_out,
            sequence_path=sequence_path_out,
            overflow_path=overflow_path_out,
            trace_path=trace_path,
        )
    except EngineFailure as failure:
        _record_failure(failure)
        raise
    except (ContractError, InputResolutionError, SchemaValidationError) as exc:
        failure = EngineFailure(
            "F5" if isinstance(exc, InputResolutionError) else "F4",
            "s8_contract_failure",
            "S8",
            MODULE_NAME,
            {"detail": str(exc)},
        )
        _record_failure(failure)
        raise


__all__ = ["S8RunResult", "run_s8"]
