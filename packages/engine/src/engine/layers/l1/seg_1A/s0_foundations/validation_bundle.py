"""Validation bundle and failure record helpers for Segment 1A S0."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Iterable

from engine.core.hashing import FileDigest


def _json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True))
            handle.write("\n")


def write_failure_record(path: Path, payload: dict) -> None:
    if path.exists():
        return
    tmp_dir = path.parent / f"_tmp.{uuid.uuid4().hex}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    write_json(tmp_dir / "failure.json", payload)
    write_json(tmp_dir / "_FAILED.SENTINEL.json", payload)
    tmp_dir.replace(path)


def write_validation_bundle(
    bundle_root: Path,
    manifest_payload: dict,
    parameter_hash_resolved: dict,
    manifest_fingerprint_resolved: dict,
    param_digest_log: list[dict],
    fingerprint_artifacts: list[dict],
    numeric_policy_attest: dict,
    run_environ: dict,
    index_entries: list[dict],
) -> None:
    tmp_root = bundle_root.parent / f"_tmp.{uuid.uuid4().hex}"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)

    write_json(tmp_root / "MANIFEST.json", manifest_payload)
    write_json(tmp_root / "parameter_hash_resolved.json", parameter_hash_resolved)
    write_json(
        tmp_root / "manifest_fingerprint_resolved.json", manifest_fingerprint_resolved
    )
    write_jsonl(tmp_root / "param_digest_log.jsonl", param_digest_log)
    write_jsonl(tmp_root / "fingerprint_artifacts.jsonl", fingerprint_artifacts)
    write_json(tmp_root / "numeric_policy_attest.json", numeric_policy_attest)
    write_json(tmp_root / "run_environ.json", run_environ)

    write_json(tmp_root / "index.json", index_entries)
    passed_hash = _bundle_hash(tmp_root, index_entries)
    passed_flag = f"sha256_hex = {passed_hash}"
    (tmp_root / "_passed.flag").write_text(passed_flag + "\n", encoding="ascii")

    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    tmp_root.replace(bundle_root)


def _bundle_hash(bundle_root: Path, index_entries: list[dict]) -> str:
    paths = sorted(entry["path"] for entry in index_entries if entry.get("path"))
    hasher = hashlib.sha256()
    for path in paths:
        blob = (bundle_root / path).read_bytes()
        hasher.update(blob)
    return hasher.hexdigest()


def build_param_digest_log(
    param_digests: Iterable[tuple[str, FileDigest]],
) -> list[dict]:
    records = []
    for name, digest in param_digests:
        records.append(
            {
                "filename": name,
                "size_bytes": digest.size_bytes,
                "sha256_hex": digest.sha256_hex,
                "mtime_ns": digest.mtime_ns,
            }
        )
    return sorted(records, key=lambda item: item["filename"])
