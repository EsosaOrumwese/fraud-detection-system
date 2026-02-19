from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import polars as pl
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema, validate_dataframe
from engine.contracts.loader import (
    find_dataset_entry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import (
    ContractError,
    EngineFailure,
    HashingError,
    InputResolutionError,
    SchemaValidationError,
)
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_3A.s0_gate.runner import (
    _append_jsonl,
    _inline_external_refs,
    _load_json,
    _load_yaml,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _segment_state_runs_path,
    _table_pack,
)
from engine.layers.l1.seg_3A.s3_zone_shares.rng import (
    UINT64_MAX,
    Substream,
    derive_master_material,
    derive_substream_state,
    u01_pair,
    u01_single,
)


MODULE_NAME = "3A.s3_zone_shares"
SEGMENT = "3A"
STATE = "S3"

MODULE_RNG = "3A.S3"
SUBSTREAM_LABEL = "zone_dirichlet"

TOLERANCE = 1e-12


@dataclass(frozen=True)
class S3Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    output_path: Path
    run_report_path: Path


@dataclass(frozen=True)
class _S3DispersionPolicy:
    enabled: bool
    concentration_scale: float
    alpha_temperature: float
    merchant_jitter: float
    merchant_jitter_clip: float
    alpha_floor: float


DEFAULT_S3_DISPERSION_POLICY = _S3DispersionPolicy(
    enabled=False,
    concentration_scale=1.0,
    alpha_temperature=1.0,
    merchant_jitter=0.0,
    merchant_jitter_clip=0.0,
    alpha_floor=1.0e-6,
)


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


class _ProgressTracker:
    def __init__(self, total: int, logger, label: str) -> None:
        self._total = max(int(total), 0)
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < 0.5 and self._processed < self._total:
            return
        self._last_log = now
        elapsed = now - self._start
        rate = self._processed / elapsed if elapsed > 0 else 0.0
        remaining = max(self._total - self._processed, 0)
        eta = remaining / rate if rate > 0 else 0.0
        self._logger.info(
            "%s %s/%s (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
            self._label,
            self._processed,
            self._total,
            elapsed,
            rate,
            eta,
        )


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


def _emit_event(logger, event: str, manifest_fingerprint: Optional[str], severity: str, **fields: object) -> None:
    payload = {
        "event": event,
        "segment": SEGMENT,
        "state": STATE,
        "manifest_fingerprint": manifest_fingerprint or "unknown",
        "severity": severity,
        "timestamp_utc": utc_now_rfc3339_micro(),
    }
    payload.update(fields)
    message = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    if severity == "ERROR":
        logger.error("%s %s", event, message)
    elif severity == "WARN":
        logger.warning("%s %s", event, message)
    elif severity == "DEBUG":
        logger.debug("%s %s", event, message)
    else:
        logger.info("%s %s", event, message)


def _emit_validation(
    logger,
    manifest_fingerprint: Optional[str],
    validator_id: str,
    result: str,
    error_code: Optional[str] = None,
    detail: Optional[object] = None,
) -> None:
    if result == "fail":
        severity = "ERROR"
    elif result == "warn":
        severity = "WARN"
    else:
        severity = "DEBUG"
    payload = {"validator_id": validator_id, "result": result}
    if error_code:
        payload["error_code"] = error_code
    if detail is not None:
        payload["detail"] = detail
    _emit_event(logger, "VALIDATION", manifest_fingerprint, severity, **payload)


def _abort(code: str, validator_id: str, message: str, context: dict, manifest_fingerprint: Optional[str]) -> None:
    logger = get_logger("engine.layers.l1.seg_3A.s3_zone_shares.l2.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _schema_for_payload(schema_pack: dict, schema_layer1: dict, anchor: str) -> dict:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    return normalize_nullable_schema(schema)


def _load_sealed_inputs(path: Path) -> list[dict]:
    try:
        payload = _load_json(path)
    except (InputResolutionError, json.JSONDecodeError):
        if path.suffix.lower() == ".parquet":
            return pl.read_parquet(path).to_dicts()
        raise
    if not isinstance(payload, list):
        raise InputResolutionError("sealed_inputs_3A payload is not a list")
    return payload


def _list_parquet_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.glob("*.parquet"))
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def _resolve_event_paths(
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


def _event_has_rows(paths: list[Path]) -> bool:
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


def _u128_diff(before_hi: int, before_lo: int, after_hi: int, after_lo: int) -> int:
    before = (int(before_hi) << 64) | int(before_lo)
    after = (int(after_hi) << 64) | int(after_lo)
    if after < before:
        raise ValueError("rng_counter_regression")
    return after - before


def _box_muller(stream: Substream) -> tuple[float, int, int]:
    u1, u2, blocks, draws = u01_pair(stream)
    r = math.sqrt(-2.0 * math.log(u1))
    theta = 2.0 * math.pi * u2
    z = r * math.cos(theta)
    return z, blocks, draws


def _gamma_mt1998(alpha: float, stream: Substream) -> tuple[float, int, int]:
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


def _git_hex_to_bytes(git_hex: str) -> bytes:
    git_hex = git_hex.strip().lower()
    raw = bytes.fromhex(git_hex)
    if len(raw) == 20:
        return b"\x00" * 12 + raw
    if len(raw) == 32:
        return raw
    raise InputResolutionError("Unexpected git hash length; expected SHA-1 or SHA-256.")


def _resolve_git_hash(repo_root: Path) -> str:
    env_hash = os.environ.get("ENGINE_GIT_COMMIT")
    if env_hash:
        return _git_hex_to_bytes(env_hash).hex()
    git_file = repo_root / "ci" / "manifests" / "git_commit_hash.txt"
    if git_file.exists():
        return _git_hex_to_bytes(git_file.read_text(encoding="utf-8").strip()).hex()
    try:
        import subprocess

        output = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root)
        return _git_hex_to_bytes(output.decode("utf-8").strip()).hex()
    except Exception as exc:  # pragma: no cover - fallback when git unavailable
        raise InputResolutionError("Unable to resolve git commit hash.") from exc


def _audit_has_entry(audit_path: Path, run_id: str, seed: int, parameter_hash: str, manifest_fingerprint: str) -> bool:
    if not audit_path.exists():
        return False
    with audit_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if (
                payload.get("run_id") == run_id
                and payload.get("seed") == seed
                and payload.get("parameter_hash") == parameter_hash
                and payload.get("manifest_fingerprint") == manifest_fingerprint
            ):
                return True
    return False


def _ensure_rng_audit(audit_path: Path, audit_entry: dict, logger, state_label: str) -> None:
    if audit_path.exists():
        with audit_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if (
                    payload.get("run_id") == audit_entry.get("run_id")
                    and payload.get("seed") == audit_entry.get("seed")
                    and payload.get("parameter_hash") == audit_entry.get("parameter_hash")
                    and payload.get("manifest_fingerprint") == audit_entry.get("manifest_fingerprint")
                ):
                    logger.info(
                        "%s: rng_audit_log already contains audit row for run_id=%s",
                        state_label,
                        audit_entry["run_id"],
                    )
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_entry, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        logger.info("%s: appended rng_audit_log entry for run_id=%s", state_label, audit_entry["run_id"])
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info("%s: wrote rng_audit_log entry for run_id=%s", state_label, audit_entry["run_id"])


def _publish_partition(
    tmp_root: Path,
    final_root: Path,
    df: pl.DataFrame,
    logger,
) -> None:
    if final_root.exists():
        existing_df = pl.read_parquet(str(final_root / "*.parquet"))
        existing_df = existing_df.sort(["merchant_id", "legal_country_iso", "tzid"])
        if df.equals(existing_df):
            for path in tmp_root.rglob("*"):
                if path.is_file():
                    path.unlink()
            try:
                tmp_root.rmdir()
            except OSError:
                pass
            logger.info("S3: s3_zone_shares already exists and is identical; skipping publish.")
            return
        difference_kind = "row_set"
        difference_count = abs(df.height - existing_df.height)
        if df.height == existing_df.height and df.columns == existing_df.columns:
            difference_kind = "field_value"
            diff_left = df.join(existing_df, on=df.columns, how="anti")
            diff_right = existing_df.join(df, on=df.columns, how="anti")
            difference_count = diff_left.height + diff_right.height
        raise EngineFailure(
            "F4",
            "E3A_S3_011_IMMUTABILITY_VIOLATION",
            STATE,
            MODULE_NAME,
            {
                "detail": "non-identical output exists",
                "difference_kind": difference_kind,
                "difference_count": int(difference_count),
                "partition": str(final_root),
            },
        )
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _atomic_publish_file(tmp_path: Path, final_path: Path, logger, label: str) -> None:
    if final_path.exists():
        raise EngineFailure(
            "F4",
            "E3A_S3_011_IMMUTABILITY_VIOLATION",
            STATE,
            MODULE_NAME,
            {"detail": "output already exists", "path": str(final_path), "label": label},
        )
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "E3A_S3_012_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "path": str(final_path), "error": str(exc)},
        ) from exc


def _rng_stream_id(merchant_id: int, country_iso: str) -> str:
    payload = f"{MODULE_RNG}|{SUBSTREAM_LABEL}|{merchant_id}|{country_iso}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hash_u01(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big", signed=False)
    return (value + 0.5) / float(1 << 64)


def _load_s3_dispersion_policy(policy_payload: dict) -> _S3DispersionPolicy:
    block = policy_payload.get("s3_dispersion")
    if block is None:
        return DEFAULT_S3_DISPERSION_POLICY
    if not isinstance(block, dict):
        raise ContractError("zone_mixture_policy.s3_dispersion must be an object when present.")

    try:
        enabled = bool(block.get("enabled", False))
        concentration_scale = float(block.get("concentration_scale", 1.0))
        alpha_temperature = float(block.get("alpha_temperature", 1.0))
        merchant_jitter = float(block.get("merchant_jitter", 0.0))
        merchant_jitter_clip = float(block.get("merchant_jitter_clip", 0.0))
        alpha_floor = float(block.get("alpha_floor", 1.0e-6))
    except (TypeError, ValueError) as exc:
        raise ContractError("zone_mixture_policy.s3_dispersion has non-numeric values.") from exc

    if not (0.25 <= concentration_scale <= 1.50):
        raise ContractError("zone_mixture_policy.s3_dispersion.concentration_scale out of range [0.25,1.50].")
    if not (0.50 <= alpha_temperature <= 1.50):
        raise ContractError("zone_mixture_policy.s3_dispersion.alpha_temperature out of range [0.50,1.50].")
    if not (0.0 <= merchant_jitter <= 0.50):
        raise ContractError("zone_mixture_policy.s3_dispersion.merchant_jitter out of range [0.0,0.50].")
    if not (0.0 <= merchant_jitter_clip <= 0.50):
        raise ContractError("zone_mixture_policy.s3_dispersion.merchant_jitter_clip out of range [0.0,0.50].")
    if merchant_jitter_clip + TOLERANCE < merchant_jitter:
        raise ContractError(
            "zone_mixture_policy.s3_dispersion.merchant_jitter_clip must be >= merchant_jitter."
        )
    if not (0.0 < alpha_floor <= 0.01):
        raise ContractError("zone_mixture_policy.s3_dispersion.alpha_floor out of range (0,0.01].")

    return _S3DispersionPolicy(
        enabled=enabled,
        concentration_scale=concentration_scale,
        alpha_temperature=alpha_temperature,
        merchant_jitter=merchant_jitter,
        merchant_jitter_clip=merchant_jitter_clip,
        alpha_floor=alpha_floor,
    )


def _apply_dispersion_transform(
    alphas: list[float],
    merchant_id: int,
    country_iso: str,
    parameter_hash: str,
    policy: _S3DispersionPolicy,
) -> tuple[list[float], float]:
    if not alphas:
        raise ValueError("empty alpha vector")
    clean_alphas = [float(value) for value in alphas]
    if any((not math.isfinite(value)) or value <= 0.0 for value in clean_alphas):
        raise ValueError("alpha_values_mismatch")

    alpha_sum_base = float(sum(clean_alphas))
    if not math.isfinite(alpha_sum_base) or alpha_sum_base <= 0.0:
        raise ValueError("alpha_sum_mismatch")
    if not policy.enabled:
        return clean_alphas, alpha_sum_base

    base_shares = [value / alpha_sum_base for value in clean_alphas]
    if abs(policy.alpha_temperature - 1.0) > TOLERANCE:
        warped = [max(share, 1.0e-15) ** policy.alpha_temperature for share in base_shares]
        warped_sum = float(sum(warped))
        if not math.isfinite(warped_sum) or warped_sum <= 0.0:
            raise ValueError("dispersion_temperature_invalid")
        base_shares = [value / warped_sum for value in warped]

    jitter_u = _hash_u01("3A.S3.dispersion", merchant_id, country_iso, parameter_hash)
    jitter = ((2.0 * jitter_u) - 1.0) * policy.merchant_jitter
    if jitter > policy.merchant_jitter_clip:
        jitter = policy.merchant_jitter_clip
    if jitter < -policy.merchant_jitter_clip:
        jitter = -policy.merchant_jitter_clip

    min_scale = (policy.alpha_floor * len(clean_alphas)) / alpha_sum_base
    concentration_scale = max(policy.concentration_scale * (1.0 + jitter), min_scale)
    target_sum = float(alpha_sum_base * concentration_scale)
    if not math.isfinite(target_sum) or target_sum <= 0.0:
        raise ValueError("dispersion_target_sum_invalid")

    raw = [share * target_sum for share in base_shares]
    floored = [max(value, policy.alpha_floor) for value in raw]
    floored_sum = float(sum(floored))
    if not math.isfinite(floored_sum) or floored_sum <= 0.0:
        raise ValueError("dispersion_floor_invalid")
    adjusted = [value * (target_sum / floored_sum) for value in floored]

    adjusted = [max(value, policy.alpha_floor) for value in adjusted]
    adjusted_sum = float(sum(adjusted))
    if not math.isfinite(adjusted_sum) or adjusted_sum <= 0.0:
        raise ValueError("dispersion_adjust_invalid")
    adjusted = [value * (target_sum / adjusted_sum) for value in adjusted]

    final_sum = float(sum(adjusted))
    if not math.isfinite(final_sum) or final_sum <= 0.0:
        raise ValueError("dispersion_final_sum_invalid")
    if abs(final_sum - target_sum) > 1.0e-9:
        adjusted = [value * (target_sum / final_sum) for value in adjusted]
        final_sum = float(sum(adjusted))
    if abs(final_sum - target_sum) > 1.0e-7:
        raise ValueError("dispersion_final_sum_mismatch")

    return adjusted, final_sum


def run_s3(config: EngineConfig, run_id: Optional[str] = None) -> S3Result:
    logger = get_logger("engine.layers.l1.seg_3A.s3_zone_shares.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()

    status = "FAIL"
    error_code: Optional[str] = None
    error_class: Optional[str] = None
    error_context: Optional[dict] = None
    first_failure_phase: Optional[str] = None

    seed: Optional[int] = None
    manifest_fingerprint: Optional[str] = None
    parameter_hash: Optional[str] = None
    run_id_value: Optional[str] = None
    output_root: Optional[Path] = None
    run_report_path: Optional[Path] = None

    current_phase = "init"

    counts: dict[str, int] = {
        "pairs_total": 0,
        "pairs_escalated": 0,
        "rows_total": 0,
        "countries_escalated": 0,
        "rng_events": 0,
        "rng_trace_rows": 0,
    }
    zone_count_buckets: Counter[int] = Counter()
    rng_blocks_total = 0
    rng_draws_total = 0

    prior_pack_id = ""
    prior_pack_version = ""
    floor_policy_id = ""
    floor_policy_version = ""
    dispersion_policy = DEFAULT_S3_DISPERSION_POLICY

    try:
        _receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id_value = str(receipt.get("run_id") or "")
        seed = int(receipt.get("seed") or 0)
        parameter_hash = str(receipt.get("parameter_hash") or "")
        manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
        if not run_id_value or not parameter_hash or not manifest_fingerprint:
            raise InputResolutionError("run_receipt missing run_id, parameter_hash, or manifest_fingerprint.")

        run_paths = RunPaths(config.runs_root, run_id_value)
        run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
        add_file_handler(run_log_path)
        timer.info(f"S3: run log initialized at {run_log_path}")

        logger.info(
            "S3: objective=sample zone shares for escalated merchant-country pairs "
            "(S1 escalation + S2 priors) -> outputs (s3_zone_shares, rng_event_zone_dirichlet, rng_trace_log)"
        )

        tokens = {
            "seed": str(seed),
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "run_id": run_id_value,
        }

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_path, dictionary = load_dataset_dictionary(source, SEGMENT)
        schema_3a_path, schema_3a = load_schema_pack(source, "3A", "3A")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        timer.info("S3: contracts loaded")

        current_phase = "s0_gate"
        s0_entry = find_dataset_entry(dictionary, "s0_gate_receipt_3A").entry
        s0_path = _resolve_dataset_path(s0_entry, run_paths, config.external_roots, tokens)
        s0_gate = _load_json(s0_path)
        s0_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/s0_gate_receipt_3A")
        s0_errors = list(Draft202012Validator(s0_schema).iter_errors(s0_gate))
        if s0_errors:
            _abort(
                "E3A_S3_001_PRECONDITION_FAILED",
                "V-01",
                "s0_gate_schema_invalid",
                {"component": "S0_GATE", "reason": "schema_invalid", "error": str(s0_errors[0])},
                manifest_fingerprint,
            )
        upstream_gates = s0_gate.get("upstream_gates") or {}
        for segment in ("1A", "1B", "2A"):
            status_value = (upstream_gates.get(f"segment_{segment}") or {}).get("status")
            if status_value != "PASS":
                _abort(
                    "E3A_S3_001_PRECONDITION_FAILED",
                    "V-01",
                    "upstream_gate_not_pass",
                    {
                        "component": "S0_GATE",
                        "reason": "upstream_gate_not_pass",
                        "segment": segment,
                        "reported_status": status_value,
                    },
                    manifest_fingerprint,
                )

        sealed_entry = find_dataset_entry(dictionary, "sealed_inputs_3A").entry
        sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
        sealed_inputs = _load_sealed_inputs(sealed_path)
        sealed_schema = _schema_from_pack(schema_3a, "validation/sealed_inputs_3A")
        _inline_external_refs(sealed_schema, schema_layer1, "schemas.layer1.yaml#")
        sealed_validator = Draft202012Validator(normalize_nullable_schema(sealed_schema))
        for row in sealed_inputs:
            errors = list(sealed_validator.iter_errors(row))
            if errors:
                _abort(
                    "E3A_S3_001_PRECONDITION_FAILED",
                    "V-01",
                    "sealed_inputs_schema_invalid",
                    {"component": "S0_SEALED_INPUTS", "reason": "schema_invalid", "error": str(errors[0])},
                    manifest_fingerprint,
                )

        sealed_policy_set = s0_gate.get("sealed_policy_set") or []
        sealed_policy_ids = {str(item.get("logical_id") or "") for item in sealed_policy_set}
        missing_policies = sorted(
            policy_id
            for policy_id in ("zone_mixture_policy", "country_zone_alphas", "zone_floor_policy")
            if policy_id not in sealed_policy_ids
        )
        if missing_policies:
            _abort(
                "E3A_S3_001_PRECONDITION_FAILED",
                "V-01",
                "sealed_policy_missing",
                {"component": "S0_GATE", "reason": "missing", "missing_policies": missing_policies},
                manifest_fingerprint,
            )

        timer.info("S3: S0 gate + sealed inputs verified")

        current_phase = "s1_escalation_queue"
        s1_entry = find_dataset_entry(dictionary, "s1_escalation_queue").entry
        s1_path = _resolve_dataset_path(s1_entry, run_paths, config.external_roots, tokens)
        s1_paths = _list_parquet_paths(s1_path)
        s1_df = pl.read_parquet(s1_paths)
        s1_pack, s1_table = _table_pack(schema_3a, "plan/s1_escalation_queue")
        _inline_external_refs(s1_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(s1_df.iter_rows(named=True), s1_pack, s1_table)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S3_001_PRECONDITION_FAILED",
                "V-02",
                "s1_escalation_schema_invalid",
                {"component": "S1_ESCALATION_QUEUE", "reason": "schema_invalid", "error": str(exc)},
                manifest_fingerprint,
            )
        counts["pairs_total"] = s1_df.height

        s1_pairs = s1_df.select(["merchant_id", "legal_country_iso"])
        if s1_pairs.unique().height != s1_pairs.height:
            _abort(
                "E3A_S3_004_DOMAIN_MISMATCH_S1",
                "V-02",
                "s1_duplicate_pairs",
                {"detail": "duplicate merchant-country pairs in s1_escalation_queue"},
                manifest_fingerprint,
            )

        esc_df = s1_df.filter(pl.col("is_escalated") == True)  # noqa: E712
        esc_df = esc_df.select(["merchant_id", "legal_country_iso"]).sort(
            ["merchant_id", "legal_country_iso"]
        )
        escalated_pairs = list(esc_df.iter_rows())
        counts["pairs_escalated"] = len(escalated_pairs)

        logger.info(
            "S3: escalation queue loaded (pairs_total=%d escalated_pairs=%d)",
            counts["pairs_total"],
            counts["pairs_escalated"],
        )

        current_phase = "s2_priors"
        s2_entry = find_dataset_entry(dictionary, "s2_country_zone_priors").entry
        s2_path = _resolve_dataset_path(s2_entry, run_paths, config.external_roots, tokens)
        s2_paths = _list_parquet_paths(s2_path)
        s2_df = pl.read_parquet(s2_paths)
        s2_pack, s2_table = _table_pack(schema_3a, "plan/s2_country_zone_priors")
        _inline_external_refs(s2_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(s2_df.iter_rows(named=True), s2_pack, s2_table)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S3_001_PRECONDITION_FAILED",
                "V-03",
                "s2_priors_schema_invalid",
                {"component": "S2_PRIORS", "reason": "schema_invalid", "error": str(exc)},
                manifest_fingerprint,
            )

        s2_pairs = s2_df.select(["country_iso", "tzid"])
        if s2_pairs.unique().height != s2_pairs.height:
            _abort(
                "E3A_S3_005_DOMAIN_MISMATCH_S2",
                "V-03",
                "s2_duplicate_country_tzid",
                {"detail": "duplicate country_iso/tzid rows in s2_country_zone_priors"},
                manifest_fingerprint,
            )

        unique_prior_ids = s2_df.select("prior_pack_id").unique()
        unique_prior_versions = s2_df.select("prior_pack_version").unique()
        unique_floor_ids = s2_df.select("floor_policy_id").unique()
        unique_floor_versions = s2_df.select("floor_policy_version").unique()
        if (
            unique_prior_ids.height != 1
            or unique_prior_versions.height != 1
            or unique_floor_ids.height != 1
            or unique_floor_versions.height != 1
        ):
            _abort(
                "E3A_S3_010_OUTPUT_INCONSISTENT",
                "V-03",
                "lineage_inconsistent",
                {
                    "prior_pack_id": unique_prior_ids.to_series().to_list(),
                    "prior_pack_version": unique_prior_versions.to_series().to_list(),
                    "floor_policy_id": unique_floor_ids.to_series().to_list(),
                    "floor_policy_version": unique_floor_versions.to_series().to_list(),
                },
                manifest_fingerprint,
            )
        prior_pack_id = str(unique_prior_ids.to_series()[0])
        prior_pack_version = str(unique_prior_versions.to_series()[0])
        floor_policy_id = str(unique_floor_ids.to_series()[0])
        floor_policy_version = str(unique_floor_versions.to_series()[0])

        alpha_sum_counts = (
            s2_df.group_by("country_iso")
            .agg(pl.n_unique("alpha_sum_country").alias("alpha_sum_unique"))
            .filter(pl.col("alpha_sum_unique") > 1)
        )
        if alpha_sum_counts.height > 0:
            sample_country = alpha_sum_counts["country_iso"][0]
            _abort(
                "E3A_S3_006_DIRICHLET_ALPHA_MISMATCH",
                "V-03",
                "alpha_sum_inconsistent",
                {"country_iso": sample_country, "reason": "alpha_sum_mismatch"},
                manifest_fingerprint,
            )

        priors_by_country: dict[str, dict] = {}
        for country_key, group in s2_df.partition_by("country_iso", as_dict=True).items():
            country_iso = country_key[0] if isinstance(country_key, tuple) else country_key
            country_iso = str(country_iso)
            group_sorted = group.sort("tzid")
            tzids = group_sorted["tzid"].to_list()
            alphas = group_sorted["alpha_effective"].to_list()
            if any((not math.isfinite(alpha)) or alpha <= 0.0 for alpha in alphas):
                _abort(
                    "E3A_S3_006_DIRICHLET_ALPHA_MISMATCH",
                    "V-03",
                    "alpha_invalid",
                    {"country_iso": country_iso, "reason": "alpha_values_mismatch"},
                    manifest_fingerprint,
                )
            alpha_sum_country = float(group_sorted["alpha_sum_country"][0])
            alpha_sum_raw = float(sum(alphas))
            if (
                not math.isfinite(alpha_sum_country)
                or alpha_sum_country <= 0.0
                or abs(alpha_sum_country - alpha_sum_raw) > TOLERANCE
            ):
                _abort(
                    "E3A_S3_006_DIRICHLET_ALPHA_MISMATCH",
                    "V-03",
                    "alpha_sum_mismatch",
                    {
                        "country_iso": country_iso,
                        "reason": "alpha_sum_mismatch",
                        "expected_alpha_sum": alpha_sum_raw,
                        "observed_alpha_sum": alpha_sum_country,
                    },
                    manifest_fingerprint,
                )
            priors_by_country[country_iso] = {
                "tzids": tzids,
                "alphas": alphas,
                "alpha_sum_country": alpha_sum_country,
            }

        escalated_countries = sorted({country for _merchant, country in escalated_pairs})
        counts["countries_escalated"] = len(escalated_countries)
        missing_countries = [c for c in escalated_countries if c not in priors_by_country]
        if missing_countries:
            _abort(
                "E3A_S3_003_PRIOR_SURFACE_INCOMPLETE",
                "V-04",
                "prior_surface_incomplete",
                {
                    "missing_countries_count": len(missing_countries),
                    "sample_country_iso": missing_countries[0],
                },
                manifest_fingerprint,
            )
        timer.info("S3: priors loaded and validated")

        current_phase = "s3_dispersion_policy"
        mixture_entry = find_dataset_entry(dictionary, "zone_mixture_policy").entry
        mixture_path = _resolve_dataset_path(mixture_entry, run_paths, config.external_roots, tokens)
        mixture_payload = _load_yaml(mixture_path)
        if not isinstance(mixture_payload, dict):
            _abort(
                "E3A_S3_001_PRECONDITION_FAILED",
                "V-03A",
                "zone_mixture_policy_invalid",
                {"component": "ZONE_MIXTURE_POLICY", "reason": "schema_invalid"},
                manifest_fingerprint,
            )
        mixture_schema = _schema_for_payload(schema_3a, schema_layer1, "policy/zone_mixture_policy_v1")
        mixture_errors = list(Draft202012Validator(mixture_schema).iter_errors(mixture_payload))
        if mixture_errors:
            _abort(
                "E3A_S3_001_PRECONDITION_FAILED",
                "V-03A",
                "zone_mixture_policy_invalid",
                {"component": "ZONE_MIXTURE_POLICY", "reason": "schema_invalid", "error": str(mixture_errors[0])},
                manifest_fingerprint,
            )
        try:
            dispersion_policy = _load_s3_dispersion_policy(mixture_payload)
        except ContractError as exc:
            _abort(
                "E3A_S3_001_PRECONDITION_FAILED",
                "V-03A",
                "s3_dispersion_policy_invalid",
                {"component": "ZONE_MIXTURE_POLICY", "reason": "invalid_s3_dispersion", "error": str(exc)},
                manifest_fingerprint,
            )
        logger.info(
            "S3: dispersion policy loaded (enabled=%s concentration_scale=%.4f alpha_temperature=%.4f "
            "merchant_jitter=%.4f merchant_jitter_clip=%.4f alpha_floor=%.8f)",
            dispersion_policy.enabled,
            dispersion_policy.concentration_scale,
            dispersion_policy.alpha_temperature,
            dispersion_policy.merchant_jitter,
            dispersion_policy.merchant_jitter_clip,
            dispersion_policy.alpha_floor,
        )

        current_phase = "rng_logs"
        event_entry = find_dataset_entry(dictionary, "rng_event_zone_dirichlet").entry
        trace_entry = find_dataset_entry(dictionary, "rng_trace_log").entry
        audit_entry = find_dataset_entry(dictionary, "rng_audit_log").entry

        event_catalog_path = _render_catalog_path(event_entry, tokens)
        trace_catalog_path = _render_catalog_path(trace_entry, tokens)
        audit_catalog_path = _render_catalog_path(audit_entry, tokens)

        for label, path in (
            ("rng_event_zone_dirichlet", event_catalog_path),
            ("rng_trace_log", trace_catalog_path),
            ("rng_audit_log", audit_catalog_path),
        ):
            if (
                f"seed={seed}" not in path
                or f"parameter_hash={parameter_hash}" not in path
                or f"run_id={run_id_value}" not in path
            ):
                _abort(
                    "E3A_S3_002_CATALOGUE_MALFORMED",
                    "V-05",
                    "output_partition_mismatch",
                    {"id": label, "path": path},
                    manifest_fingerprint,
                )

        event_paths = _resolve_event_paths(run_paths, event_entry["path"], tokens)
        event_path = _resolve_event_path(run_paths, event_entry["path"], tokens)
        trace_path = _resolve_dataset_path(trace_entry, run_paths, config.external_roots, tokens)
        audit_path = _resolve_dataset_path(audit_entry, run_paths, config.external_roots, tokens)

        existing_events = _event_has_rows(event_paths)
        existing_trace = _trace_has_substream(trace_path, MODULE_RNG, SUBSTREAM_LABEL)
        skip_rng_logs = False
        if existing_events and existing_trace:
            skip_rng_logs = True
            logger.info("S3: existing rng logs detected; will skip emitting new events/trace.")
        elif existing_events or existing_trace:
            _abort(
                "E3A_S3_007_RNG_ACCOUNTING_BROKEN",
                "V-05",
                "rng_log_partial",
                {"reason": "trace_mismatch"},
                manifest_fingerprint,
            )

        audit_payload = {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id_value,
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "algorithm": "philox2x64-10",
            "build_commit": _resolve_git_hash(config.repo_root),
            "code_digest": None,
            "hostname": platform.node() or None,
            "platform": platform.platform(),
            "notes": None,
        }
        audit_schema = _schema_from_pack(schema_layer1, "rng/core/rng_audit_log/record")
        audit_schema = normalize_nullable_schema(audit_schema)
        audit_errors = list(Draft202012Validator(audit_schema).iter_errors(audit_payload))
        if audit_errors:
            _abort(
                "E3A_S3_007_RNG_ACCOUNTING_BROKEN",
                "V-05",
                "rng_audit_invalid",
                {"reason": "invalid_envelope", "error": str(audit_errors[0])},
                manifest_fingerprint,
            )

        if skip_rng_logs:
            if not _audit_has_entry(audit_path, run_id_value, seed, parameter_hash, manifest_fingerprint):
                _abort(
                    "E3A_S3_007_RNG_ACCOUNTING_BROKEN",
                    "V-05",
                    "rng_audit_missing",
                    {"reason": "trace_mismatch"},
                    manifest_fingerprint,
                )
        else:
            _ensure_rng_audit(audit_path, audit_payload, logger, "S3")

        current_phase = "sampling"
        event_schema = _schema_from_pack(schema_layer1, "rng/events/zone_dirichlet")
        event_schema = normalize_nullable_schema(event_schema)
        event_validator = Draft202012Validator(event_schema)

        manifest_bytes = bytes.fromhex(manifest_fingerprint)
        master_material = derive_master_material(manifest_bytes, seed)

        output_rows: list[dict] = []
        tmp_event_path: Optional[Path] = None
        tmp_trace_path: Optional[Path] = None
        event_handle = None
        trace_handle = None
        trace_acc = _TraceAccumulator(MODULE_RNG, SUBSTREAM_LABEL)

        if not skip_rng_logs:
            tmp_event_path = run_paths.tmp_root / f"rng_event_zone_dirichlet_{uuid.uuid4().hex}.jsonl"
            tmp_trace_path = run_paths.tmp_root / f"rng_trace_log_{uuid.uuid4().hex}.jsonl"
            tmp_event_path.parent.mkdir(parents=True, exist_ok=True)
            event_handle = tmp_event_path.open("w", encoding="utf-8")
            trace_handle = tmp_trace_path.open("w", encoding="utf-8")

        logger.info(
            "S3: entering Dirichlet sampling loop for escalated pairs; targets=%d",
            len(escalated_pairs),
        )
        tracker = _ProgressTracker(len(escalated_pairs), logger, "S3 progress")

        expected_rows = 0
        for merchant_id, country_iso in escalated_pairs:
            prior = priors_by_country[country_iso]
            tzids = prior["tzids"]
            alphas = prior["alphas"]
            effective_alphas, effective_alpha_sum = _apply_dispersion_transform(
                alphas,
                int(merchant_id),
                str(country_iso),
                str(parameter_hash),
                dispersion_policy,
            )
            zone_count = len(tzids)
            if zone_count < 1:
                _abort(
                    "E3A_S3_005_DOMAIN_MISMATCH_S2",
                    "V-06",
                    "zone_count_missing",
                    {"country_iso": country_iso},
                    manifest_fingerprint,
                )
            expected_rows += zone_count
            zone_count_buckets[zone_count] += 1

            rng_stream_id = _rng_stream_id(int(merchant_id), str(country_iso))
            stream = derive_substream_state(master_material, SUBSTREAM_LABEL, rng_stream_id)

            before_hi, before_lo = stream.counter()
            gamma_raw: list[float] = []
            blocks_total = 0
            draws_total = 0
            for alpha in effective_alphas:
                if not math.isfinite(alpha) or alpha <= 0.0:
                    _abort(
                        "E3A_S3_006_DIRICHLET_ALPHA_MISMATCH",
                        "V-06",
                        "alpha_invalid",
                        {"country_iso": country_iso, "reason": "alpha_values_mismatch"},
                        manifest_fingerprint,
                    )
                gamma_value, blocks, draws = _gamma_mt1998(float(alpha), stream)
                gamma_raw.append(gamma_value)
                blocks_total += blocks
                draws_total += draws

            after_hi, after_lo = stream.counter()
            blocks_delta = _u128_diff(before_hi, before_lo, after_hi, after_lo)
            if blocks_delta != blocks_total:
                _abort(
                    "E3A_S3_007_RNG_ACCOUNTING_BROKEN",
                    "V-06",
                    "rng_counter_mismatch",
                    {"reason": "invalid_envelope", "expected": blocks_total, "actual": blocks_delta},
                    manifest_fingerprint,
                )
            sum_gamma = float(sum(gamma_raw))
            if not math.isfinite(sum_gamma) or sum_gamma <= 0.0:
                _abort(
                    "E3A_S3_010_OUTPUT_INCONSISTENT",
                    "V-06",
                    "gamma_sum_nonpositive",
                    {"reason": "share_sum_mismatch", "country_iso": country_iso},
                    manifest_fingerprint,
                )
            shares = [value / sum_gamma for value in gamma_raw]
            share_sum = float(sum(shares))
            if not math.isfinite(share_sum) or share_sum <= 0.0:
                _abort(
                    "E3A_S3_010_OUTPUT_INCONSISTENT",
                    "V-06",
                    "share_sum_nonpositive",
                    {"reason": "share_sum_mismatch", "country_iso": country_iso},
                    manifest_fingerprint,
                )
            if abs(share_sum - 1.0) > TOLERANCE:
                _abort(
                    "E3A_S3_010_OUTPUT_INCONSISTENT",
                    "V-06",
                    "share_sum_mismatch",
                    {
                        "reason": "share_sum_mismatch",
                        "country_iso": country_iso,
                        "expected": 1.0,
                        "observed": share_sum,
                    },
                    manifest_fingerprint,
                )

            counts["rng_events"] += 1
            rng_blocks_total = _checked_add(rng_blocks_total, int(blocks_delta))
            rng_draws_total = _checked_add(rng_draws_total, int(draws_total))

            event_payload = {
                "ts_utc": utc_now_rfc3339_micro(),
                "seed": seed,
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "run_id": run_id_value,
                "module": MODULE_RNG,
                "substream_label": SUBSTREAM_LABEL,
                "rng_stream_id": rng_stream_id,
                "rng_counter_before_lo": before_lo,
                "rng_counter_before_hi": before_hi,
                "rng_counter_after_lo": after_lo,
                "rng_counter_after_hi": after_hi,
                "blocks": int(blocks_delta),
                "draws": str(draws_total),
                "merchant_id": int(merchant_id),
                "country_iso": str(country_iso),
                "zone_count": int(zone_count),
                "alpha_sum_country": float(effective_alpha_sum),
                "alpha_min": float(min(effective_alphas)),
                "alpha_max": float(max(effective_alphas)),
                "notes": None,
            }

            if not skip_rng_logs:
                event_errors = list(event_validator.iter_errors(event_payload))
                if event_errors:
                    _abort(
                        "E3A_S3_007_RNG_ACCOUNTING_BROKEN",
                        "V-06",
                        "rng_event_schema_invalid",
                        {"reason": "invalid_envelope", "error": str(event_errors[0])},
                        manifest_fingerprint,
                    )
                if event_handle is None or trace_handle is None:
                    _abort(
                        "E3A_S3_007_RNG_ACCOUNTING_BROKEN",
                        "V-06",
                        "rng_handle_missing",
                        {"reason": "invalid_envelope"},
                        manifest_fingerprint,
                    )
                event_handle.write(json.dumps(event_payload, ensure_ascii=True, sort_keys=True))
                event_handle.write("\n")
                trace_payload = trace_acc.append(event_payload)
                trace_handle.write(json.dumps(trace_payload, ensure_ascii=True, sort_keys=True))
                trace_handle.write("\n")
                counts["rng_trace_rows"] += 1

            for tzid, share in zip(tzids, shares):
                if not math.isfinite(share) or share < 0.0 or share > 1.0:
                    _abort(
                        "E3A_S3_010_OUTPUT_INCONSISTENT",
                        "V-06",
                        "share_out_of_range",
                        {"reason": "share_sum_mismatch", "country_iso": country_iso, "tzid": tzid},
                        manifest_fingerprint,
                    )
                output_rows.append(
                    {
                        "seed": seed,
                        "manifest_fingerprint": manifest_fingerprint,
                        "merchant_id": int(merchant_id),
                        "legal_country_iso": str(country_iso),
                        "tzid": str(tzid),
                        "share_drawn": float(share),
                        "share_sum_country": float(share_sum),
                        "alpha_sum_country": float(effective_alpha_sum),
                        "prior_pack_id": prior_pack_id,
                        "prior_pack_version": prior_pack_version,
                        "floor_policy_id": floor_policy_id,
                        "floor_policy_version": floor_policy_version,
                        "rng_module": MODULE_RNG,
                        "rng_substream_label": SUBSTREAM_LABEL,
                        "rng_stream_id": rng_stream_id,
                        "rng_event_id": None,
                        "notes": None,
                    }
                )

            tracker.update(1)

        if event_handle is not None:
            event_handle.close()
        if trace_handle is not None:
            trace_handle.close()

        if skip_rng_logs:
            counts["rng_trace_rows"] = counts["rng_events"]

        counts["rows_total"] = len(output_rows)
        if counts["rows_total"] != expected_rows:
            _abort(
                "E3A_S3_005_DOMAIN_MISMATCH_S2",
                "V-07",
                "row_count_mismatch",
                {"expected": expected_rows, "observed": counts["rows_total"]},
                manifest_fingerprint,
            )

        if not skip_rng_logs and counts["rng_events"] == 0:
            if tmp_event_path and tmp_event_path.exists():
                tmp_event_path.unlink()
            if tmp_trace_path and tmp_trace_path.exists():
                tmp_trace_path.unlink()

        output_entry = find_dataset_entry(dictionary, "s3_zone_shares").entry
        output_root = _resolve_dataset_path(output_entry, run_paths, config.external_roots, tokens)
        output_catalog_path = _render_catalog_path(output_entry, tokens)
        tmp_root = run_paths.tmp_root / f"s3_zone_shares_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)

        output_pack, output_table = _table_pack(schema_3a, "plan/s3_zone_shares")
        _inline_external_refs(output_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(iter(output_rows), output_pack, output_table)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S3_009_OUTPUT_SCHEMA_INVALID",
                "V-08",
                "output_schema_invalid",
                {"violation_count": len(exc.errors), "detail": str(exc)},
                manifest_fingerprint,
            )

        df = pl.DataFrame(
            output_rows,
            schema={
                "seed": pl.UInt64,
                "manifest_fingerprint": pl.Utf8,
                "merchant_id": pl.UInt64,
                "legal_country_iso": pl.Utf8,
                "tzid": pl.Utf8,
                "share_drawn": pl.Float64,
                "share_sum_country": pl.Float64,
                "alpha_sum_country": pl.Float64,
                "prior_pack_id": pl.Utf8,
                "prior_pack_version": pl.Utf8,
                "floor_policy_id": pl.Utf8,
                "floor_policy_version": pl.Utf8,
                "rng_module": pl.Utf8,
                "rng_substream_label": pl.Utf8,
                "rng_stream_id": pl.Utf8,
                "rng_event_id": pl.Utf8,
                "notes": pl.Utf8,
            },
        ).sort(["merchant_id", "legal_country_iso", "tzid"])

        if df.height != df.unique(subset=["merchant_id", "legal_country_iso", "tzid"]).height:
            _abort(
                "E3A_S3_004_DOMAIN_MISMATCH_S1",
                "V-08",
                "duplicate_output_rows",
                {"detail": "duplicate merchant-country-tzid rows detected"},
                manifest_fingerprint,
            )

        output_path = tmp_root / "part-00000.parquet"
        df.write_parquet(output_path, compression="zstd")
        logger.info("S3: wrote %d rows to %s", df.height, output_path)

        _publish_partition(tmp_root, output_root, df, logger)
        timer.info("S3: published s3_zone_shares")

        if not skip_rng_logs and counts["rng_events"] > 0:
            if tmp_event_path is None or tmp_trace_path is None:
                _abort(
                    "E3A_S3_007_RNG_ACCOUNTING_BROKEN",
                    "V-09",
                    "rng_tmp_paths_missing",
                    {"reason": "invalid_envelope"},
                    manifest_fingerprint,
                )
            _atomic_publish_file(tmp_event_path, event_path, logger, "rng_event_zone_dirichlet")
            _atomic_publish_file(tmp_trace_path, trace_path, logger, "rng_trace_log")
            logger.info(
                "S3: emitted rng events=%d trace_rows=%d",
                counts["rng_events"],
                counts["rng_trace_rows"],
            )

        status = "PASS"
    except EngineFailure as exc:
        if not error_code:
            error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except ContractError as exc:
        if not error_code:
            error_code = "E3A_S3_002_CATALOGUE_MALFORMED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "E3A_S3_012_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "E3A_S3_012_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id_value and parameter_hash and manifest_fingerprint:
            utc_day = finished_utc[:10]
            try:
                segment_state_runs_path = _segment_state_runs_path(run_paths, dictionary, utc_day)
                _append_jsonl(
                    segment_state_runs_path,
                    {
                        "layer": "layer1",
                        "segment": SEGMENT,
                        "state": STATE,
                        "parameter_hash": str(parameter_hash),
                        "manifest_fingerprint": str(manifest_fingerprint),
                        "run_id": run_id_value,
                        "status": status,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("S3: failed to write segment_state_runs: %s", exc)

            try:
                run_report_entry = find_dataset_entry(dictionary, "s3_run_report_3A").entry
                run_report_path = _resolve_dataset_path(run_report_entry, run_paths, config.external_roots, tokens)
                run_report = {
                    "layer": "layer1",
                    "segment": SEGMENT,
                    "state": STATE,
                    "parameter_hash": str(parameter_hash),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "run_id": run_id_value,
                    "status": status,
                    "seed": int(seed) if seed is not None else 0,
                    "started_at_utc": started_utc,
                    "finished_at_utc": finished_utc,
                    "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                    "policy": {
                        "prior_pack_id": prior_pack_id,
                        "prior_pack_version": prior_pack_version,
                        "floor_policy_id": floor_policy_id,
                        "floor_policy_version": floor_policy_version,
                        "s3_dispersion": {
                            "enabled": dispersion_policy.enabled,
                            "concentration_scale": dispersion_policy.concentration_scale,
                            "alpha_temperature": dispersion_policy.alpha_temperature,
                            "merchant_jitter": dispersion_policy.merchant_jitter,
                            "merchant_jitter_clip": dispersion_policy.merchant_jitter_clip,
                            "alpha_floor": dispersion_policy.alpha_floor,
                        },
                    },
                    "counts": counts,
                    "zone_count_buckets": {str(k): v for k, v in zone_count_buckets.items()},
                    "rng_totals": {
                        "events": counts["rng_events"],
                        "draws": int(rng_draws_total),
                        "blocks": int(rng_blocks_total),
                    },
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {"path": output_catalog_path if output_root else None, "format": "parquet"},
                }
                _write_json(run_report_path, run_report)
                logger.info("S3: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S3: failed to write run-report: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "E3A_S3_012_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if output_root is None or run_report_path is None:
        raise EngineFailure(
            "F4",
            "E3A_S3_012_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S3Result(
        run_id=str(run_id_value),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        output_path=output_root,
        run_report_path=run_report_path,
    )
