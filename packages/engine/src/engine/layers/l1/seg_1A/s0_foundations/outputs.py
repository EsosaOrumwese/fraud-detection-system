"""Write S0 outputs (sealed inputs, gate receipt, RNG logs)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from engine.core.hashing import FileDigest
from engine.core.logging import get_logger
from engine.layers.l1.seg_1A.s0_foundations.inputs import InputAsset
from engine.layers.l1.seg_1A.s0_foundations.rng import RngTraceAccumulator


@dataclass(frozen=True)
class S0Outputs:
    sealed_inputs_path: Path
    gate_receipt_path: Path
    rng_anchor_path: Path
    rng_audit_path: Path
    rng_trace_path: Path


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, sort_keys=True)


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        handle.write("\n")


def write_sealed_inputs(
    sealed_path: Path, assets: Iterable[InputAsset], digests: dict[Path, FileDigest]
) -> None:
    records = []
    for asset in assets:
        digest = digests[asset.path]
        records.append(
            {
                "asset_id": asset.asset_id,
                "version_tag": asset.version_tag,
                "sha256_hex": digest.sha256_hex,
                "path": asset.path.as_posix(),
                "partition": dict(asset.partition),
            }
        )
    records.sort(key=lambda item: (item["asset_id"], item["path"]))
    _write_json(sealed_path, records)


def write_gate_receipt(
    receipt_path: Path,
    manifest_fingerprint: str,
    parameter_hash: str,
    run_id: str,
    sealed_assets: Iterable[InputAsset],
) -> None:
    sealed_inputs = []
    for asset in sealed_assets:
        sealed_inputs.append(
            {
                "id": asset.asset_id,
                "partition": sorted(asset.partition.keys()),
                "schema_ref": asset.schema_ref or "unknown",
            }
        )
    payload = {
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
        "sealed_inputs": sealed_inputs,
    }
    _write_json(receipt_path, payload)


def write_rng_logs(
    anchor_path: Path,
    audit_path: Path,
    trace_path: Path,
    anchor_event: dict,
    audit_entry: dict,
) -> None:
    logger = get_logger("engine.s0.outputs")
    trace = RngTraceAccumulator()
    _append_jsonl(anchor_path, anchor_event)
    trace_entry = trace.append_event(anchor_event)
    _append_jsonl(trace_path, trace_entry)
    _append_jsonl(audit_path, audit_entry)
    logger.info("Wrote RNG anchor, trace, and audit logs.")
