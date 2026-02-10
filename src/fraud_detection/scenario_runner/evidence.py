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
from .storage import ObjectStore


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

    def has_gate(self, gate_id: str) -> bool:
        return gate_id in self.gates


class GateVerifier:
    def __init__(self, engine_root: str | Path, gate_map: GateMap, store: ObjectStore | None = None) -> None:
        if isinstance(engine_root, Path):
            engine_root_str = str(engine_root)
        else:
            engine_root_str = engine_root
        self.engine_root = engine_root_str
        self.engine_root_path = Path(engine_root_str)
        self.gate_map = gate_map
        self.store = store
        self._is_s3 = engine_root_str.startswith("s3://")
        if self._is_s3 and self.store is None:
            raise RuntimeError("GATE_VERIFIER_STORE_REQUIRED")

    def verify(self, gate_id: str, tokens: dict[str, Any]) -> GateVerificationResult:
        entry = self.gate_map.gate_entry(gate_id)
        method = entry.get("verification_method", {})
        passed_flag = self._render(entry["passed_flag_path_template"], tokens)
        bundle_root = self._render(entry["bundle_root_template"], tokens)
        index_path = self._render(entry.get("index_path_template", ""), tokens)
        digest_field = method.get("digest_field")
        ordering = method.get("ordering", "ascii_lex")
        exclude = set(method.get("exclude_filenames", []) or [])
        path_base = method.get("path_base", "bundle_root")

        if "{" in passed_flag or "}" in passed_flag:
            return GateVerificationResult(receipt=None, missing=True, conflict=False)
        if "{" in bundle_root or "}" in bundle_root:
            return GateVerificationResult(receipt=None, missing=True, conflict=False)
        if index_path and ("{" in index_path or "}" in index_path):
            return GateVerificationResult(receipt=None, missing=True, conflict=False)

        if not self._exists(passed_flag):
            return GateVerificationResult(receipt=None, missing=True, conflict=False)

        if not self._dir_exists(bundle_root):
            return GateVerificationResult(receipt=None, missing=True, conflict=False)

        expected = self._parse_passed_flag(passed_flag, digest_field)
        if expected is None:
            return GateVerificationResult(receipt=None, missing=False, conflict=True)

        if method.get("kind") == "sha256_member_digest_concat":
            if not index_path or not self._exists(index_path):
                return GateVerificationResult(receipt=None, missing=True, conflict=False)
            actual = self._digest_member_concat(index_path, digest_field)
        elif method.get("kind") == "sha256_index_json_ascii_lex_raw_bytes":
            if not index_path or not self._exists(index_path):
                return GateVerificationResult(receipt=None, missing=True, conflict=False)
            base_root = bundle_root if path_base == "bundle_root" else ""
            actual = self._digest_index_raw_bytes(index_path, base_root, ordering, exclude)
            if actual is None:
                return GateVerificationResult(receipt=None, missing=True, conflict=False)
        else:
            actual = self._digest_bundle(bundle_root, exclude, ordering)

        artifacts = GateArtifacts(
            validation_bundle_root=self._artifact_path(bundle_root),
            index_path=self._artifact_path(index_path) if index_path else None,
            passed_flag_path=self._artifact_path(passed_flag),
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

    def _parse_passed_flag(self, relative_path: str, digest_field: str | None) -> str | None:
        content = self._read_text(relative_path).strip()
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

    def _digest_bundle(self, root: str, exclude: set[str], ordering: str) -> str:
        if not self._is_s3:
            base = self.engine_root_path / root
            files = [path for path in base.rglob("*") if path.is_file() and path.name not in exclude]
            if ordering == "ascii_lex":
                files = sorted(files, key=lambda p: str(p.relative_to(base)))
            digest = hashlib.sha256()
            for path in files:
                digest.update(path.read_bytes())
            return digest.hexdigest()

        files = self._list_files_relative(root)
        if ordering == "ascii_lex":
            files = sorted(files)
        digest = hashlib.sha256()
        for rel in files:
            if rel in exclude or Path(rel).name in exclude:
                continue
            blob_path = f"{root.rstrip('/')}/{rel}" if rel else root
            digest.update(self._read_bytes(blob_path))
        return digest.hexdigest()

    def _digest_member_concat(self, index_path: str, digest_field: str | None) -> str:
        data = json.loads(self._read_text(index_path))
        items = data.get("members") or data.get("items") or []
        parts = []
        for item in items:
            value = item.get(digest_field) if digest_field else None
            if value:
                parts.append(value)
        concat = "".join(parts)
        return hashlib.sha256(concat.encode("utf-8")).hexdigest()

    def _digest_index_raw_bytes(
        self,
        index_path: str,
        base_root: str,
        ordering: str,
        exclude: set[str],
    ) -> str | None:
        data = json.loads(self._read_text(index_path))
        items: list[dict[str, Any]]
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = (
                data.get("items")
                or data.get("members")
                or data.get("entries")
                or data.get("files")
                or []
            )
        else:
            items = []
        paths: list[str] = []
        for item in items:
            path = item.get("path")
            if not path:
                continue
            if path in exclude or Path(path).name in exclude:
                continue
            paths.append(path)
        if ordering == "ascii_lex":
            paths = sorted(paths)
        digest = hashlib.sha256()
        for rel in paths:
            if self._is_s3:
                resolved = self._resolve_relative_path(rel, base_root)
                if resolved is None or not self._exists(resolved):
                    return None
                digest.update(self._read_bytes(resolved))
            else:
                candidate = Path(rel)
                full_path = candidate if candidate.is_absolute() else (self.engine_root_path / base_root / candidate)
                if not full_path.exists():
                    return None
                digest.update(full_path.read_bytes())
        return digest.hexdigest()

    def _artifact_path(self, relative_path: str) -> str:
        if not relative_path:
            return ""
        if self._is_s3:
            return f"{self.engine_root.rstrip('/')}/{relative_path.lstrip('/')}"
        return str(self.engine_root_path / relative_path)

    def _exists(self, relative_path: str) -> bool:
        if self._is_s3:
            return bool(self.store and self.store.exists(relative_path))
        return (self.engine_root_path / relative_path).exists()

    def _dir_exists(self, relative_dir: str) -> bool:
        if self._is_s3:
            return bool(self.store and self.store.list_files(relative_dir))
        return (self.engine_root_path / relative_dir).exists()

    def _read_text(self, relative_path: str) -> str:
        if self._is_s3:
            if not self.store:
                raise RuntimeError("GATE_VERIFIER_STORE_REQUIRED")
            return self.store.read_text(relative_path)
        return (self.engine_root_path / relative_path).read_text(encoding="utf-8")

    def _read_bytes(self, relative_path: str) -> bytes:
        if self._is_s3:
            if not self.store:
                raise RuntimeError("GATE_VERIFIER_STORE_REQUIRED")
            return self.store.read_bytes(relative_path)
        return (self.engine_root_path / relative_path).read_bytes()

    def _list_files_relative(self, relative_dir: str) -> list[str]:
        if not self._is_s3:
            base = self.engine_root_path / relative_dir
            if not base.exists():
                return []
            return [str(path.relative_to(base)) for path in base.rglob("*") if path.is_file()]
        if not self.store:
            return []
        files = self.store.list_files(relative_dir)
        base = f"{self.engine_root.rstrip('/')}/{relative_dir.strip('/')}"
        if base and not base.endswith("/"):
            base += "/"
        rels = []
        for uri in files:
            if not uri.startswith(base):
                continue
            rel = uri[len(base):]
            if rel:
                rels.append(rel)
        return rels

    def _resolve_relative_path(self, path: str, base_root: str) -> str | None:
        if self._is_s3:
            if path.startswith("s3://"):
                base = self.engine_root.rstrip("/") + "/"
                if not path.startswith(base):
                    return None
                return path[len(base):]
            trimmed = path.lstrip("/")
            if base_root:
                return f"{base_root.rstrip('/')}/{trimmed}"
            return trimmed
        return path


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
