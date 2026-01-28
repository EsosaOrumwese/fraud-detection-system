"""Oracle pack sealing + manifest writer (write-once)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fraud_detection.scenario_runner.storage import S3ObjectStore

from .config import OracleProfile
from .engine_reader import read_run_receipt, resolve_engine_root


@dataclass(frozen=True)
class OracleWorldKey:
    manifest_fingerprint: str
    parameter_hash: str
    scenario_id: str
    seed: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest_fingerprint": self.manifest_fingerprint,
            "parameter_hash": self.parameter_hash,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class OraclePackManifest:
    version: str
    oracle_pack_id: str
    world_key: OracleWorldKey
    engine_release: str
    catalogue_digest: str
    gate_map_digest: str
    created_at_utc: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "oracle_pack_id": self.oracle_pack_id,
            "world_key": self.world_key.as_dict(),
            "engine_release": self.engine_release,
            "catalogue_digest": self.catalogue_digest,
            "gate_map_digest": self.gate_map_digest,
            "created_at_utc": self.created_at_utc,
        }


class OraclePackError(RuntimeError):
    pass


class OraclePackPacker:
    def __init__(self, profile: OracleProfile) -> None:
        self.profile = profile

    def seal_from_engine_run(
        self,
        engine_run_root: str,
        *,
        scenario_id: str,
        pack_root: str | None = None,
        engine_release: str = "unknown",
        seal_status: str = "SEALED_OK",
    ) -> dict[str, Any]:
        if not scenario_id:
            raise OraclePackError("SCENARIO_ID_MISSING")
        resolved_engine_root = resolve_engine_root(engine_run_root, self.profile.wiring.oracle_root)
        resolved_pack_root = (
            resolve_engine_root(pack_root, self.profile.wiring.oracle_root)
            if pack_root
            else resolved_engine_root
        )
        if not resolved_pack_root.startswith("s3://"):
            if not Path(resolved_pack_root).exists():
                raise OraclePackError("PACK_ROOT_NOT_FOUND")

        receipt = read_run_receipt(resolved_engine_root, self.profile)
        world_key = self._world_key_from_receipt(receipt, scenario_id)
        manifest = self._build_manifest(world_key, engine_release)
        seal = self._build_seal(manifest.oracle_pack_id, seal_status=seal_status)
        self._write_manifest(resolved_pack_root, manifest)
        self._write_seal(resolved_pack_root, seal)
        return {
            "pack_root": resolved_pack_root,
            "engine_run_root": resolved_engine_root,
            "oracle_pack_id": manifest.oracle_pack_id,
        }

    def _world_key_from_receipt(self, receipt: dict[str, Any], scenario_id: str) -> OracleWorldKey:
        try:
            return OracleWorldKey(
                manifest_fingerprint=receipt["manifest_fingerprint"],
                parameter_hash=receipt["parameter_hash"],
                scenario_id=scenario_id,
                seed=int(receipt["seed"]),
            )
        except Exception as exc:
            raise OraclePackError("WORLD_KEY_MISSING") from exc

    def _build_manifest(self, world_key: OracleWorldKey, engine_release: str) -> OraclePackManifest:
        catalogue_digest = _sha256_file(Path(self.profile.wiring.engine_catalogue_path))
        gate_map_digest = _sha256_file(Path(self.profile.wiring.gate_map_path))
        oracle_pack_id = _oracle_pack_id(world_key, engine_release, catalogue_digest, gate_map_digest)
        created_at_utc = datetime.now(tz=timezone.utc).isoformat()
        return OraclePackManifest(
            version="v0",
            oracle_pack_id=oracle_pack_id,
            world_key=world_key,
            engine_release=engine_release,
            catalogue_digest=catalogue_digest,
            gate_map_digest=gate_map_digest,
            created_at_utc=created_at_utc,
        )

    def _build_seal(self, oracle_pack_id: str, *, seal_status: str) -> dict[str, Any]:
        return {
            "version": "v0",
            "oracle_pack_id": oracle_pack_id,
            "seal_status": seal_status,
            "sealed_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }

    def _write_manifest(self, pack_root: str, manifest: OraclePackManifest) -> None:
        data = manifest.as_dict()
        path = _join_pack_path(pack_root, "_oracle_pack_manifest.json")
        self._write_json_if_absent(path, data)
        existing = self._read_json(path)
        if _canonical(_manifest_fingerprint(existing)) != _canonical(_manifest_fingerprint(data)):
            raise OraclePackError("MANIFEST_MISMATCH")

    def _write_seal(self, pack_root: str, seal: dict[str, Any]) -> None:
        path = _join_pack_path(pack_root, "_SEALED.json")
        self._write_json_if_absent(path, seal)
        existing = self._read_json(path)
        if _canonical(_seal_fingerprint(existing)) != _canonical(_seal_fingerprint(seal)):
            raise OraclePackError("SEAL_MISMATCH")

    def _read_json(self, path: str) -> dict[str, Any]:
        if path.startswith("s3://"):
            parsed = urlparse(path)
            store = S3ObjectStore(
                parsed.netloc,
                prefix="",
                endpoint_url=self.profile.wiring.object_store_endpoint,
                region_name=self.profile.wiring.object_store_region,
                path_style=self.profile.wiring.object_store_path_style,
            )
            return store.read_json(parsed.path.lstrip("/"))
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def _write_json_if_absent(self, path: str, payload: dict[str, Any]) -> None:
        data = _canonical(payload) + "\n"
        if path.startswith("s3://"):
            parsed = urlparse(path)
            store = S3ObjectStore(
                parsed.netloc,
                prefix="",
                endpoint_url=self.profile.wiring.object_store_endpoint,
                region_name=self.profile.wiring.object_store_region,
                path_style=self.profile.wiring.object_store_path_style,
            )
            store.write_json_if_absent(parsed.path.lstrip("/"), payload)
            return
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("x", encoding="utf-8") as handle:
                handle.write(data)
        except FileExistsError:
            return


def _oracle_pack_id(
    world_key: OracleWorldKey,
    engine_release: str,
    catalogue_digest: str,
    gate_map_digest: str,
) -> str:
    payload = (
        f"{world_key.manifest_fingerprint}|{world_key.parameter_hash}|"
        f"{world_key.scenario_id}|{world_key.seed}|{engine_release}|"
        f"{catalogue_digest}|{gate_map_digest}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _manifest_fingerprint(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": payload.get("version"),
        "oracle_pack_id": payload.get("oracle_pack_id"),
        "world_key": payload.get("world_key"),
        "engine_release": payload.get("engine_release"),
        "catalogue_digest": payload.get("catalogue_digest"),
        "gate_map_digest": payload.get("gate_map_digest"),
    }


def _seal_fingerprint(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": payload.get("version"),
        "oracle_pack_id": payload.get("oracle_pack_id"),
        "seal_status": payload.get("seal_status"),
    }


def _join_pack_path(pack_root: str, name: str) -> str:
    if pack_root.startswith("s3://"):
        return f"{pack_root.rstrip('/')}/{name}"
    return str(Path(pack_root) / name)
