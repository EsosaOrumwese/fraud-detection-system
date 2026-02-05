"""IEG query surface (read-only)."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import IegProfile
from .store import IdentifierCandidate, NeighborCandidate, ProjectionStore, build_store


class QueryError(Exception):
    def __init__(self, code: str, detail: str | None = None, status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class QueryPins:
    platform_run_id: str
    scenario_run_id: str
    scenario_id: str
    manifest_fingerprint: str
    parameter_hash: str
    seed: str
    run_id: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "QueryPins":
        if not isinstance(payload, dict):
            raise QueryError("MISSING_PINS", "pins must be a mapping")
        required = [
            "platform_run_id",
            "scenario_run_id",
            "scenario_id",
            "manifest_fingerprint",
            "parameter_hash",
            "seed",
        ]
        missing = [key for key in required if payload.get(key) in (None, "")]
        if missing:
            raise QueryError("MISSING_PINS", f"missing pins: {','.join(missing)}")
        return cls(
            platform_run_id=str(payload.get("platform_run_id")),
            scenario_run_id=str(payload.get("scenario_run_id")),
            scenario_id=str(payload.get("scenario_id")),
            manifest_fingerprint=str(payload.get("manifest_fingerprint")),
            parameter_hash=str(payload.get("parameter_hash")),
            seed=str(payload.get("seed")),
            run_id=str(payload.get("run_id")) if payload.get("run_id") not in (None, "") else None,
        )

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "scenario_id": self.scenario_id,
            "manifest_fingerprint": self.manifest_fingerprint,
            "parameter_hash": self.parameter_hash,
            "seed": self.seed,
        }
        if self.run_id:
            payload["run_id"] = self.run_id
        return payload

    def digest(self) -> str:
        canonical = json.dumps(self.as_dict(), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


class IdentityGraphQuery:
    def __init__(self, store: ProjectionStore, stream_id: str) -> None:
        self.store = store
        self.stream_id = stream_id

    @classmethod
    def from_profile(cls, profile_path: str) -> "IdentityGraphQuery":
        profile = IegProfile.load(Path(profile_path))
        store = build_store(profile.wiring.projection_db_dsn, stream_id=profile.policy.graph_stream_id)
        return cls(store=store, stream_id=profile.policy.graph_stream_id)

    def status(self, *, scenario_run_id: str) -> dict[str, Any]:
        graph_version = self.store.current_graph_version()
        failure_count = self.store.apply_failure_count(scenario_run_id=scenario_run_id)
        integrity_status = "DEGRADED" if failure_count > 0 else "CLEAN"
        return {
            "graph_version": graph_version,
            "integrity_status": integrity_status,
            "apply_failure_count": failure_count,
        }

    def resolve_identity(
        self,
        *,
        pins: dict[str, Any],
        identifier_type: str,
        identifier_value: str,
        limit: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        pins_obj = QueryPins.from_payload(pins)
        graph_version = self.store.current_graph_version()
        failure_count = self.store.apply_failure_count(scenario_run_id=pins_obj.scenario_run_id)
        integrity_status = "DEGRADED" if failure_count > 0 else "CLEAN"

        after = _decode_page_token(
            page_token,
            op="resolve",
            pins_digest=pins_obj.digest(),
            graph_version=graph_version,
            identifier_type=identifier_type,
            identifier_value=identifier_value,
        )
        candidates = self.store.resolve_identifier_candidates(
            pins=pins_obj.as_dict(),
            identifier_type=identifier_type,
            identifier_value=identifier_value,
            limit=max(1, limit) + 1,
            after=after,
        )
        next_token = None
        if len(candidates) > limit:
            last = candidates[limit - 1]
            next_token = _encode_page_token(
                {
                    "op": "resolve",
                    "pins_digest": pins_obj.digest(),
                    "graph_version": graph_version,
                    "identifier_type": identifier_type,
                    "identifier_value": identifier_value,
                    "last_entity_type": last.entity_type,
                    "last_entity_id": last.entity_id,
                }
            )
            candidates = candidates[:limit]
        payload = {
            "pins": pins_obj.as_dict(),
            "graph_version": graph_version,
            "integrity_status": integrity_status,
            "identifier": {
                "identifier_type": identifier_type,
                "identifier_value": identifier_value,
                "candidates": _serialize_candidates(candidates),
                "conflict": len(candidates) > 1,
            },
        }
        if next_token:
            payload["next_page_token"] = next_token
        return payload

    def get_entity_profile(
        self,
        *,
        pins: dict[str, Any],
        entity_id: str,
        entity_type: str,
    ) -> dict[str, Any]:
        pins_obj = QueryPins.from_payload(pins)
        graph_version = self.store.current_graph_version()
        failure_count = self.store.apply_failure_count(scenario_run_id=pins_obj.scenario_run_id)
        integrity_status = "DEGRADED" if failure_count > 0 else "CLEAN"
        profile = self.store.fetch_entity_profile(
            pins=pins_obj.as_dict(),
            entity_id=entity_id,
            entity_type=entity_type,
        )
        return {
            "pins": pins_obj.as_dict(),
            "graph_version": graph_version,
            "integrity_status": integrity_status,
            "profile": profile,
        }

    def get_neighbors(
        self,
        *,
        pins: dict[str, Any],
        entity_id: str,
        entity_type: str,
        limit: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        pins_obj = QueryPins.from_payload(pins)
        graph_version = self.store.current_graph_version()
        failure_count = self.store.apply_failure_count(scenario_run_id=pins_obj.scenario_run_id)
        integrity_status = "DEGRADED" if failure_count > 0 else "CLEAN"

        after = _decode_page_token(
            page_token,
            op="neighbors",
            pins_digest=pins_obj.digest(),
            graph_version=graph_version,
            entity_id=entity_id,
            entity_type=entity_type,
        )
        neighbors = self.store.fetch_neighbors(
            pins=pins_obj.as_dict(),
            entity_id=entity_id,
            entity_type=entity_type,
            limit=max(1, limit) + 1,
            after=after,
        )
        next_token = None
        if len(neighbors) > limit:
            last = neighbors[limit - 1]
            next_token = _encode_page_token(
                {
                    "op": "neighbors",
                    "pins_digest": pins_obj.digest(),
                    "graph_version": graph_version,
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                    "last_entity_type": last.entity_type,
                    "last_entity_id": last.entity_id,
                }
            )
            neighbors = neighbors[:limit]
        payload = {
            "pins": pins_obj.as_dict(),
            "graph_version": graph_version,
            "integrity_status": integrity_status,
            "entity": {"entity_id": entity_id, "entity_type": entity_type},
            "neighbors": _serialize_neighbors(neighbors),
        }
        if next_token:
            payload["next_page_token"] = next_token
        return payload


def _serialize_candidates(candidates: list[IdentifierCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "entity_id": candidate.entity_id,
            "entity_type": candidate.entity_type,
            "first_seen_ts_utc": candidate.first_seen_ts_utc,
            "last_seen_ts_utc": candidate.last_seen_ts_utc,
        }
        for candidate in candidates
    ]


def _serialize_neighbors(neighbors: list[NeighborCandidate]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for neighbor in neighbors:
        payload.append(
            {
                "entity_id": neighbor.entity_id,
                "entity_type": neighbor.entity_type,
                "first_seen_ts_utc": neighbor.first_seen_ts_utc,
                "last_seen_ts_utc": neighbor.last_seen_ts_utc,
                "shared_identifiers": [
                    {
                        "identifier_type": shared.identifier_type,
                        "identifier_value": shared.identifier_value,
                    }
                    for shared in neighbor.shared_identifiers
                ],
            }
        )
    return payload


def _encode_page_token(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_page_token(
    token: str | None,
    *,
    op: str,
    pins_digest: str,
    graph_version: str | None,
    identifier_type: str | None = None,
    identifier_value: str | None = None,
    entity_id: str | None = None,
    entity_type: str | None = None,
) -> tuple[str, str] | None:
    if not token:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(token.encode("ascii")))
    except Exception as exc:  # pragma: no cover - defensive
        raise QueryError("PAGE_TOKEN_INVALID", str(exc)) from exc
    if not isinstance(payload, dict):
        raise QueryError("PAGE_TOKEN_INVALID", "token payload malformed")
    if payload.get("op") != op:
        raise QueryError("PAGE_TOKEN_INCOMPATIBLE", "token op mismatch")
    if payload.get("pins_digest") != pins_digest:
        raise QueryError("PAGE_TOKEN_INCOMPATIBLE", "token pins mismatch")
    if payload.get("graph_version") != graph_version:
        raise QueryError("PAGE_TOKEN_STALE", "graph_version changed")
    if identifier_type and payload.get("identifier_type") != identifier_type:
        raise QueryError("PAGE_TOKEN_INCOMPATIBLE", "identifier_type mismatch")
    if identifier_value and payload.get("identifier_value") != identifier_value:
        raise QueryError("PAGE_TOKEN_INCOMPATIBLE", "identifier_value mismatch")
    if entity_id and payload.get("entity_id") != entity_id:
        raise QueryError("PAGE_TOKEN_INCOMPATIBLE", "entity_id mismatch")
    if entity_type and payload.get("entity_type") != entity_type:
        raise QueryError("PAGE_TOKEN_INCOMPATIBLE", "entity_type mismatch")
    last_entity_type = payload.get("last_entity_type")
    last_entity_id = payload.get("last_entity_id")
    if not last_entity_type or not last_entity_id:
        raise QueryError("PAGE_TOKEN_INVALID", "missing resume keys")
    return str(last_entity_type), str(last_entity_id)
