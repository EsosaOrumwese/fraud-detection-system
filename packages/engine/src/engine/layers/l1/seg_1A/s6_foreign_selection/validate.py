"""Validation helpers for S6 foreign-set selection."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import re

import pandas as pd
import yaml
from jsonschema import Draft201909Validator, ValidationError
from referencing import Registry, Resource

from ..s0_foundations.l1.rng import PhiloxEngine, comp_iso, comp_u64
from ..shared.dictionary import get_repo_root, load_dictionary, resolve_dataset_path
from . import constants as c
from .loader import verify_s5_pass
from .runner import S6RunOutputs
from .types import CandidateSelection, MerchantSelectionResult

__all__ = ["S6ValidationError", "validate_outputs"]


class S6ValidationError(RuntimeError):
    """Raised when S6 validation checks fail."""


def validate_outputs(*, base_path: Path, outputs: S6RunOutputs) -> Mapping[str, object]:
    """Validate all S6 artefacts and return the parsed receipt payload."""

    base_path = Path(base_path).expanduser().resolve()
    deterministic = outputs.deterministic
    dictionary = load_dictionary()

    weights_path = resolve_dataset_path(
        "ccy_country_weights_cache",
        base_path=base_path,
        template_args={"parameter_hash": deterministic.parameter_hash},
        dictionary=dictionary,
    )
    verify_s5_pass(weights_path.parent)

    receipt_payload = _load_receipt(outputs.receipt_path)
    _validate_receipt_payload(receipt_payload, outputs)

    events = _read_event_log(outputs.events_path)

    if outputs.events_expected == 0:
        if events:
            raise S6ValidationError("expected zero events but log contains entries")
    else:
        if len(events) != outputs.events_written:
            raise S6ValidationError(
                f"event log count ({len(events)}) does not match recorded events ({outputs.events_written})"
            )
        if outputs.log_all_candidates and len(events) != outputs.events_expected:
            raise S6ValidationError(
                "log_all_candidates enabled but log does not cover considered domain"
            )
        if not outputs.log_all_candidates and len(events) != outputs.membership_rows:
            raise S6ValidationError(
                "reduced logging mode should emit one event per selected country"
            )

    membership_df = _read_membership(outputs.membership_path)
    if outputs.membership_rows == 0:
        if membership_df is not None and not membership_df.empty:
            raise S6ValidationError("expected empty membership surface")
    else:
        if membership_df is None or membership_df.shape[0] != outputs.membership_rows:
            raise S6ValidationError(
                "membership row count does not match recorded metrics"
            )

    if events:
        _validate_events(
            events=events,
            results=outputs.results,
            log_all_candidates=outputs.log_all_candidates,
            membership_df=membership_df,
        )

    trace_events = _count_trace_entries(outputs.trace_path)
    if trace_events != outputs.trace_events:
        raise S6ValidationError(
            f"trace log event count ({trace_events}) differs from recorded value ({outputs.trace_events})"
        )
    if outputs.trace_reconciled != (outputs.trace_events == outputs.events_written):
        raise S6ValidationError("trace reconciliation flag inconsistent with log counts")

    _verify_counter_replay(outputs)

    return receipt_payload


def _load_receipt(receipt_path: Path | None) -> Mapping[str, object]:
    if receipt_path is None:
        raise S6ValidationError("receipt path missing")
    receipt_file = Path(receipt_path).expanduser().resolve()
    if receipt_file.is_dir():
        receipt_file = receipt_file / "S6_VALIDATION.json"
    if not receipt_file.exists():
        raise S6ValidationError(f"receipt not found at {receipt_file}")

    payload_text = receipt_file.read_text(encoding="utf-8")
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise S6ValidationError(f"receipt JSON malformed: {exc}") from exc

    flag_path = receipt_file.with_name("_passed.flag")
    if not flag_path.exists():
        raise S6ValidationError(f"_passed.flag missing alongside {receipt_file}")

    expected_digest = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    flag_text = flag_path.read_text(encoding="ascii").strip()
    prefix = "sha256_hex="
    if not flag_text.startswith(prefix):
        raise S6ValidationError(f"_passed.flag contents malformed at {flag_path}")
    observed_digest = flag_text[len(prefix) :].strip()
    if observed_digest != expected_digest:
        raise S6ValidationError(
            "_passed.flag digest does not match S6_VALIDATION.json contents"
        )
    return payload


def _validate_receipt_payload(payload: Mapping[str, object], outputs: S6RunOutputs) -> None:
    expected_fields = {
        "seed": int(outputs.deterministic.seed),
        "parameter_hash": outputs.deterministic.parameter_hash,
        "policy_digest": outputs.policy_digest,
        "gumbel_key_expected": int(outputs.events_expected),
        "gumbel_key_written": int(outputs.events_written),
        "events_written": int(outputs.events_written),
        "shortfall_count": int(outputs.shortfall_count),
        "membership_rows": int(outputs.membership_rows),
        "trace_events": int(outputs.trace_events),
        "log_all_candidates": bool(outputs.log_all_candidates),
        "rng_isolation_ok": bool(outputs.rng_isolation_ok),
    }
    for field, expected in expected_fields.items():
        if payload.get(field) != expected:
            raise S6ValidationError(
                f"receipt field '{field}' mismatch (expected {expected}, got {payload.get(field)})"
            )
    _receipt_validator().validate(payload)


def _read_event_log(events_path: Path | None) -> list[dict]:
    if events_path is None or not events_path.exists():
        return []
    records: list[dict] = []
    with events_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise S6ValidationError(f"invalid event JSON: {exc}") from exc
            records.append(record)
    return records


def _read_membership(membership_path: Path | None) -> pd.DataFrame | None:
    if membership_path is None or not membership_path.exists():
        return None
    df = pd.read_parquet(membership_path)
    _membership_validator().validate(df.to_dict(orient="records"))
    return df


def _count_trace_entries(trace_path: Path | None) -> int:
    if trace_path is None or not trace_path.exists():
        return 0
    count = 0
    with trace_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                if record.get("module") != c.MODULE_NAME:
                    raise S6ValidationError(
                        f"trace record module mismatch: {record.get('module')}"
                    )
                run_id = str(record.get("run_id", ""))
                if not _HEX32_RE.fullmatch(run_id):
                    raise S6ValidationError(
                        "trace run_id must be 32 lowercase hex characters"
                    )
                if not _HEX64_RE.fullmatch(str(record.get("parameter_hash", ""))):
                    raise S6ValidationError("trace parameter_hash must be 64 lowercase hex characters")
                count += 1
    return count


def _candidate_lookup(results: Sequence[MerchantSelectionResult]) -> Mapping[tuple[int, str], CandidateSelection]:
    lookup: dict[tuple[int, str], CandidateSelection] = {}
    for result in results:
        for candidate in result.candidates:
            lookup[(result.merchant_id, candidate.country_iso)] = candidate
    return lookup


def _validate_events(
    *,
    events: list[dict],
    results: Sequence[MerchantSelectionResult],
    log_all_candidates: bool,
    membership_df: pd.DataFrame | None,
) -> None:
    lookup = _candidate_lookup(results)
    seen: set[tuple[int, str]] = set()
    selected_pairs: set[tuple[int, str]] = set()
    tolerance = 1e-9

    for record in events:
        module = record.get("module")
        if module != c.MODULE_NAME:
            raise S6ValidationError(f"unexpected RNG module '{module}' in gumbel_key log")

        run_id = str(record.get("run_id", ""))
        if not _HEX32_RE.fullmatch(run_id):
            raise S6ValidationError("run_id must be 32 lowercase hex characters")

        parameter_hash = str(record.get("parameter_hash", ""))
        if not _HEX64_RE.fullmatch(parameter_hash):
            raise S6ValidationError("parameter_hash must be 64 lowercase hex characters")

        merchant_id = int(record.get("merchant_id"))
        country_iso = str(record.get("country_iso"))
        key = (merchant_id, country_iso)
        if key not in lookup:
            raise S6ValidationError(
                f"event references unknown candidate (merchant={merchant_id}, country={country_iso})"
            )
        candidate = lookup[key]

        weight_logged = float(record.get("weight", 0.0))
        if not math.isclose(weight_logged, candidate.weight_normalised, rel_tol=0.0, abs_tol=tolerance):
            raise S6ValidationError(
                f"weight mismatch for {key}: {weight_logged} vs {candidate.weight_normalised}"
            )

        if record.get("selected"):
            selected_pairs.add(key)
            order = record.get("selection_order")
            if candidate.selection_order != order:
                raise S6ValidationError(
                    f"selection order mismatch for {key}: {order} vs {candidate.selection_order}"
                )

        uniform = record.get("u")
        key_value = record.get("key")
        if log_all_candidates and candidate.eligible:
            if uniform is None or key_value is None:
                raise S6ValidationError("log_all mode requires uniform and key fields")
            expected_key = _gumbel_key(candidate.weight_normalised, float(uniform))
            candidate_key = candidate.key if candidate.key is not None else expected_key
            if not math.isclose(expected_key, candidate_key, rel_tol=0.0, abs_tol=1e-9):
                raise S6ValidationError(
                    f"key mismatch for {key}: {expected_key} vs {candidate_key}"
                )

        if log_all_candidates:
            if key in seen:
                raise S6ValidationError(f"duplicate event for candidate {key}")
            seen.add(key)

    if log_all_candidates and len(seen) != len(lookup):
        raise S6ValidationError("log_all mode did not cover entire candidate domain")

    if membership_df is not None and not membership_df.empty:
        membership_pairs = {
            (int(row.merchant_id), str(row.country_iso))
            for row in membership_df.itertuples(index=False)
        }
        if membership_pairs != selected_pairs:
            raise S6ValidationError("membership surface does not match selected events")


def _gumbel_key(weight: float, uniform: float) -> float:
    if weight <= 0.0:
        return float("-inf")
    if not (0.0 < uniform < 1.0):
        raise S6ValidationError("uniform deviate must lie in (0,1)")
    return math.log(weight) - math.log(-math.log(uniform))


def _verify_counter_replay(outputs: S6RunOutputs) -> None:
    engine = PhiloxEngine(
        seed=outputs.deterministic.seed,
        manifest_fingerprint=outputs.deterministic.manifest_fingerprint,
    )
    tolerance = 1e-9

    for result in outputs.results:
        candidates = sorted(result.candidates, key=lambda c: c.candidate_rank)
        for candidate in candidates:
            substream = engine.derive_substream(
                c.SUBSTREAM_LABEL_GUMBEL,
                (
                    comp_u64(int(result.merchant_id)),
                    comp_iso(candidate.country_iso),
                ),
            )
            uniform = substream.uniform()
            if candidate.uniform is not None and not math.isclose(
                candidate.uniform,
                uniform,
                rel_tol=0.0,
                abs_tol=tolerance,
            ):
                raise S6ValidationError(
                    f"uniform mismatch for merchant={result.merchant_id}, country={candidate.country_iso}"
                )
            if candidate.eligible:
                expected_key = _gumbel_key(candidate.weight_normalised, uniform)
                if candidate.key is None or not math.isclose(
                    candidate.key,
                    expected_key,
                    rel_tol=0.0,
                    abs_tol=tolerance,
                ):
                    raise S6ValidationError(
                        f"key mismatch for merchant={result.merchant_id}, country={candidate.country_iso}"
                    )


_LAYER1_SCHEMA_DATA: dict | None = None
_LAYER1_RESOURCE: Resource | None = None
_LAYER1_REGISTRY: Registry | None = None
_LAYER1_VALIDATORS: dict[str, Draft201909Validator] = {}
_MEMBERSHIP_VALIDATOR: Draft201909Validator | None = None
_RECEIPT_VALIDATOR: Draft201909Validator | None = None
_HEX32_RE = re.compile(r"[a-f0-9]{32}")
_HEX64_RE = re.compile(r"[0-9a-f]{64}")


def _layer1_validator(pointer: str) -> Draft201909Validator:
    global _LAYER1_SCHEMA_DATA, _LAYER1_RESOURCE, _LAYER1_REGISTRY
    if _LAYER1_SCHEMA_DATA is None:
        schema_path = get_repo_root() / "contracts" / "schemas" / "layer1" / "schemas.layer1.yaml"
        payload = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
        _LAYER1_SCHEMA_DATA = payload
        base_uri = payload.get("$id", "memory://schemas.layer1.yaml")
        resource = Resource.from_contents(payload)
        _LAYER1_RESOURCE = resource
        _LAYER1_REGISTRY = Registry().with_resource(base_uri, resource)
    if pointer not in _LAYER1_VALIDATORS:
        if _LAYER1_RESOURCE is None or _LAYER1_REGISTRY is None:
            raise S6ValidationError("Layer1 schema registry not initialised")
        node = _resolve_pointer(_LAYER1_SCHEMA_DATA, pointer)
        _LAYER1_VALIDATORS[pointer] = Draft201909Validator(node, registry=_LAYER1_REGISTRY)
    return _LAYER1_VALIDATORS[pointer]


def _membership_validator() -> Draft201909Validator:
    global _MEMBERSHIP_VALIDATOR
    if _MEMBERSHIP_VALIDATOR is None:
        schema_path = get_repo_root() / "contracts" / "schemas" / "l1" / "seg_1A" / "s6_membership.schema.json"
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
        node = payload.get("membership", payload)
        _MEMBERSHIP_VALIDATOR = Draft201909Validator(node)
    return _MEMBERSHIP_VALIDATOR


def _receipt_validator() -> Draft201909Validator:
    global _RECEIPT_VALIDATOR
    if _RECEIPT_VALIDATOR is None:
        schema_path = get_repo_root() / "contracts" / "schemas" / "l1" / "seg_1A" / "s6_validation.schema.json"
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
        _RECEIPT_VALIDATOR = Draft201909Validator(payload)
    return _RECEIPT_VALIDATOR


def _resolve_pointer(root: Mapping[str, object], pointer: str):
    node = root
    for part in pointer.split("/"):
        if not part:
            continue
        if isinstance(node, Mapping) and part in node:
            node = node[part]
        else:
            raise S6ValidationError(f"schema pointer '{pointer}' not found (stopped at '{part}')")
    return node
