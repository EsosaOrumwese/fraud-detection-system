"""Evidence collection and gate verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .models import EvidenceStatus


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Digest:
    algo: str
    hex: str


@dataclass(frozen=True)
class EngineOutputLocator:
    output_id: str
    path: str
    manifest_fingerprint: str | None = None
    parameter_hash: str | None = None
    seed: int | None = None
    scenario_id: str | None = None
    run_id: str | None = None
    content_digest: Digest | None = None


@dataclass(frozen=True)
class GateArtifacts:
    validation_bundle_root: str | None = None
    index_path: str | None = None
    passed_flag_path: str | None = None


@dataclass(frozen=True)
class GateReceipt:
    gate_id: str
    status: GateStatus
    scope: dict[str, Any]
    digest: Digest | None = None
    receipt_kind: str | None = None
    artifacts: GateArtifacts | None = None


@dataclass(frozen=True)
class EvidenceBundle:
    status: EvidenceStatus
    locators: list[EngineOutputLocator]
    gate_receipts: list[GateReceipt]
    instance_receipts: list[dict[str, Any]] | None = None
    bundle_hash: str | None = None
    missing: list[str] | None = None
    reason: str | None = None
    notes: list[str] | None = None


@dataclass(frozen=True)
class GateVerificationResult:
    receipt: GateReceipt | None
    missing: bool
    conflict: bool


class GateMap:
    def __init__(self, gate_map_path: Path) -> None:
        data = yaml.safe_load(gate_map_path.read_text(encoding="utf-8"))
        self.gates = {entry["gate_id"]: entry for entry in data.get("gates", [])}

    def required_gate_set(self, output_ids: list[str]) -> list[str]:
        required = set()
        for gate_id, entry in self.gates.items():
            if any(output_id in entry.get("authorizes_outputs", []) for output_id in output_ids):
                required.add(gate_id)
        # Add upstream dependencies
        changed = True
        while changed:
            changed = False
            for gate_id in list(required):
                deps = self.gates.get(gate_id, {}).get("upstream_gate_dependencies", [])
                for dep in deps:
                    if dep not in required:
                        required.add(dep)
                        changed = True
        return sorted(required)

    def gate_entry(self, gate_id: str) -> dict[str, Any]:
        return self.gates[gate_id]


class GateVerifier:
    def __init__(self, engine_root: Path, gate_map: GateMap) -> None:
        self.engine_root = engine_root
        self.gate_map = gate_map

    def verify(self, gate_id: str, tokens: dict[str, Any]) -> GateVerificationResult:
        entry = self.gate_map.gate_entry(gate_id)
        method = entry.get("verification_method", {})
        passed_flag = self._render(entry["passed_flag_path_template"], tokens)
        bundle_root = self._render(entry["bundle_root_template"], tokens)
        index_path = self._render(entry.get("index_path_template", ""), tokens)
        digest_field = method.get("digest_field")
        ordering = method.get("ordering", "ascii_lex")
        exclude = set(method.get("exclude_filenames", []) or [])

        if "{" in passed_flag or "}" in passed_flag:
            return GateVerificationResult(receipt=None, missing=True, conflict=False)
        if "{" in bundle_root or "}" in bundle_root:
            return GateVerificationResult(receipt=None, missing=True, conflict=False)
        if index_path and ("{" in index_path or "}" in index_path):
            return GateVerificationResult(receipt=None, missing=True, conflict=False)

        passed_path = self.engine_root / passed_flag
        if not passed_path.exists():
            return GateVerificationResult(receipt=None, missing=True, conflict=False)

        bundle_path = self.engine_root / bundle_root
        if not bundle_path.exists():
            return GateVerificationResult(receipt=None, missing=True, conflict=False)

        expected = self._parse_passed_flag(passed_path, digest_field)
        if expected is None:
            return GateVerificationResult(receipt=None, missing=False, conflict=True)

        if method.get("kind") == "sha256_member_digest_concat":
            index_full = self.engine_root / index_path
            if not index_full.exists():
                return GateVerificationResult(receipt=None, missing=True, conflict=False)
            actual = self._digest_member_concat(index_full, digest_field)
        else:
            actual = self._digest_bundle(bundle_path, exclude, ordering)

        artifacts = GateArtifacts(
            validation_bundle_root=str(bundle_path),
            index_path=str(self.engine_root / index_path) if index_path else None,
            passed_flag_path=str(passed_path),
        )
        if actual != expected:
            receipt = GateReceipt(
                gate_id=gate_id,
                status=GateStatus.FAIL,
                scope=tokens,
                digest=Digest(algo="sha256", hex=actual),
                receipt_kind="passed_flag",
                artifacts=artifacts,
            )
            return GateVerificationResult(receipt=receipt, missing=False, conflict=True)
        receipt = GateReceipt(
            gate_id=gate_id,
            status=GateStatus.PASS,
            scope=tokens,
            digest=Digest(algo="sha256", hex=actual),
            receipt_kind="passed_flag",
            artifacts=artifacts,
        )
        return GateVerificationResult(receipt=receipt, missing=False, conflict=False)

    def _render(self, template: str, tokens: dict[str, Any]) -> str:
        rendered = template
        for key, value in tokens.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered

    def _parse_passed_flag(self, path: Path, digest_field: str | None) -> str | None:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return None
        if content.startswith("{"):
            data = json.loads(content)
            return data.get(digest_field) if digest_field else None
        if "=" in content:
            key, value = content.split("=", 1)
            if digest_field and key.strip() != digest_field:
                return None
            return value.strip()
        return None

    def _digest_bundle(self, root: Path, exclude: set[str], ordering: str) -> str:
        files = [path for path in root.rglob("*") if path.is_file() and path.name not in exclude]
        if ordering == "ascii_lex":
            files = sorted(files, key=lambda p: str(p.relative_to(root)))
        digest = hashlib.sha256()
        for path in files:
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def _digest_member_concat(self, index_path: Path, digest_field: str | None) -> str:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        items = data.get("members") or data.get("items") or []
        parts = []
        for item in items:
            value = item.get(digest_field) if digest_field else None
            if value:
                parts.append(value)
        concat = "".join(parts)
        return hashlib.sha256(concat.encode("utf-8")).hexdigest()


def hash_bundle(
    locators: list[EngineOutputLocator],
    receipts: list[GateReceipt],
    policy_rev: dict[str, Any],
    instance_receipts: list[dict[str, Any]] | None = None,
) -> str:
    def locator_key(locator: EngineOutputLocator) -> str:
        return locator.output_id

    def receipt_key(receipt: GateReceipt) -> str:
        return receipt.gate_id

    payload = {
        "locators": [locator_to_wire(locator) for locator in sorted(locators, key=locator_key)],
        "receipts": [receipt_to_wire(receipt) for receipt in sorted(receipts, key=receipt_key)],
        "instance_receipts": sorted(instance_receipts or [], key=lambda r: r.get("output_id", "")),
        "policy_rev": policy_rev,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def prune_none(payload: dict[str, Any]) -> dict[str, Any]:
    pruned: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, dict):
            pruned[key] = prune_none(value)
        else:
            pruned[key] = value
    return pruned


def locator_to_wire(locator: EngineOutputLocator) -> dict[str, Any]:
    payload = asdict(locator)
    payload = prune_none(payload)
    if "content_digest" in payload and isinstance(payload["content_digest"], dict):
        payload["content_digest"] = prune_none(payload["content_digest"])
    return payload


def receipt_to_wire(receipt: GateReceipt) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "gate_id": receipt.gate_id,
        "status": receipt.status.value,
        "scope": receipt.scope,
    }
    if receipt.receipt_kind:
        payload["receipt_kind"] = receipt.receipt_kind
    if receipt.digest is not None:
        payload["digest"] = prune_none(asdict(receipt.digest))
    if receipt.artifacts is not None:
        payload["artifacts"] = prune_none(asdict(receipt.artifacts))
    return payload


def scope_parts(scope: str) -> set[str]:
    raw = scope or ""
    tokens = [
        "manifest_fingerprint",
        "parameter_hash",
        "scenario_id",
        "run_id",
        "seed",
        "fingerprint",
        "parameter",
        "scenario",
        "run",
        "global",
    ]
    return {token for token in tokens if token in raw}


def is_instance_scope(scope: str) -> bool:
    instance_tokens = {"seed", "scenario_id", "parameter_hash", "run_id"}
    return bool(scope_parts(scope) & instance_tokens)


def make_digest(hex_value: str | None) -> Digest | None:
    if not hex_value:
        return None
    return Digest(algo="sha256", hex=hex_value)
