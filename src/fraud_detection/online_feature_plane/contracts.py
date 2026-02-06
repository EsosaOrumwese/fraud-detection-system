"""OFP request/response contract helpers (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


_ERROR_CODES = {
    "MISSING_PINS",
    "INVALID_REQUEST",
    "NOT_FOUND",
    "UNAVAILABLE",
    "MISSING_PROVENANCE",
}

_RETRYABLE_BY_CODE = {
    "MISSING_PINS": False,
    "INVALID_REQUEST": False,
    "NOT_FOUND": False,
    "UNAVAILABLE": True,
    "MISSING_PROVENANCE": True,
}

_STATUS_BY_CODE = {
    "MISSING_PINS": 400,
    "INVALID_REQUEST": 400,
    "NOT_FOUND": 404,
    "UNAVAILABLE": 503,
    "MISSING_PROVENANCE": 503,
}


class OfpContractError(Exception):
    def __init__(self, code: str, detail: str | None = None, status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class OfpPins:
    platform_run_id: str
    scenario_run_id: str
    scenario_id: str
    manifest_fingerprint: str
    parameter_hash: str
    seed: str
    run_id: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "OfpPins":
        if not isinstance(payload, dict):
            raise OfpContractError("MISSING_PINS", "pins must be a mapping")
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
            raise OfpContractError("MISSING_PINS", f"missing pins: {','.join(missing)}")
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


def validate_get_features_request(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise OfpContractError("INVALID_REQUEST", "request must be a mapping")
    pins = OfpPins.from_payload(payload.get("pins") or {})
    as_of_time_utc = payload.get("as_of_time_utc")
    if as_of_time_utc in (None, ""):
        raise OfpContractError("INVALID_REQUEST", "as_of_time_utc is required")
    feature_keys = payload.get("feature_keys")
    if not isinstance(feature_keys, list) or not feature_keys:
        raise OfpContractError("INVALID_REQUEST", "feature_keys must be a non-empty list")
    feature_groups = payload.get("feature_groups")
    if not isinstance(feature_groups, list) or not feature_groups:
        raise OfpContractError("INVALID_REQUEST", "feature_groups must be a non-empty list")

    normalized_groups: list[dict[str, str]] = []
    for group in feature_groups:
        if not isinstance(group, dict):
            raise OfpContractError("INVALID_REQUEST", "feature_groups entries must be mappings")
        name = group.get("name")
        version = group.get("version")
        if name in (None, "") or version in (None, ""):
            raise OfpContractError("INVALID_REQUEST", "feature_groups entries require name and version")
        normalized_groups.append({"name": str(name), "version": str(version)})

    normalized_keys: list[dict[str, str]] = []
    for key in feature_keys:
        if not isinstance(key, dict):
            raise OfpContractError("INVALID_REQUEST", "feature_keys entries must be mappings")
        key_type = key.get("key_type")
        key_id = key.get("key_id")
        if key_type in (None, "") or key_id in (None, ""):
            raise OfpContractError("INVALID_REQUEST", "feature_keys entries require key_type and key_id")
        normalized_keys.append({"key_type": str(key_type), "key_id": str(key_id)})

    return {
        "pins": pins.as_dict(),
        "as_of_time_utc": str(as_of_time_utc),
        "feature_keys": normalized_keys,
        "feature_groups": sorted(normalized_groups, key=lambda item: (item["name"], item["version"])),
        "graph_resolution_mode": str(payload.get("graph_resolution_mode") or "resolve_if_needed"),
        "request_id": payload.get("request_id"),
    }


def build_snapshot_hash(snapshot: dict[str, Any]) -> str:
    required = [
        "pins",
        "as_of_time_utc",
        "feature_groups",
        "feature_def_policy_rev",
        "eb_offset_basis",
        "features",
    ]
    missing = [key for key in required if snapshot.get(key) is None]
    if missing:
        raise OfpContractError("MISSING_PROVENANCE", f"snapshot missing fields: {','.join(missing)}", status=503)
    canonical_groups = sorted(
        [
            {"name": str(item.get("name")), "version": str(item.get("version"))}
            for item in list(snapshot.get("feature_groups") or [])
        ],
        key=lambda item: (item["name"], item["version"]),
    )
    canonical_payload = {
        "pins": snapshot.get("pins"),
        "as_of_time_utc": snapshot.get("as_of_time_utc"),
        "feature_groups": canonical_groups,
        "feature_def_policy_rev": snapshot.get("feature_def_policy_rev"),
        "eb_offset_basis": snapshot.get("eb_offset_basis"),
        "graph_version": snapshot.get("graph_version"),
        "run_config_digest": snapshot.get("run_config_digest"),
        "features": snapshot.get("features"),
        "freshness": snapshot.get("freshness"),
    }
    canonical = json.dumps(canonical_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_get_features_success(
    snapshot: dict[str, Any],
    *,
    request_id: str | None = None,
    served_at_utc: str | None = None,
) -> dict[str, Any]:
    payload = dict(snapshot)
    payload["snapshot_hash"] = str(payload.get("snapshot_hash") or build_snapshot_hash(payload))
    response: dict[str, Any] = {"status": "OK", "snapshot": payload}
    if request_id:
        response["request_id"] = request_id
    if served_at_utc:
        response["served_at_utc"] = served_at_utc
    return response


def build_get_features_error(
    code: str,
    *,
    detail: str | None = None,
    retryable: bool | None = None,
    request_id: str | None = None,
    served_at_utc: str | None = None,
) -> dict[str, Any]:
    if code not in _ERROR_CODES:
        raise ValueError(f"unsupported OFP error code: {code}")
    payload: dict[str, Any] = {
        "status": "ERROR",
        "code": code,
        "retryable": bool(_RETRYABLE_BY_CODE[code] if retryable is None else retryable),
    }
    if detail:
        payload["detail"] = detail
    if request_id:
        payload["request_id"] = request_id
    if served_at_utc:
        payload["served_at_utc"] = served_at_utc
    return payload


def error_status(code: str) -> int:
    if code not in _ERROR_CODES:
        raise ValueError(f"unsupported OFP error code: {code}")
    return _STATUS_BY_CODE[code]

