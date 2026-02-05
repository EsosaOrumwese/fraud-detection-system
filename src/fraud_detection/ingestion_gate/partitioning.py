"""Deterministic partition key derivation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import yaml

from .errors import IngestionError

@dataclass(frozen=True)
class PartitionProfile:
    profile_id: str
    stream: str
    key_precedence: list[str]
    hash_algo: str


class PartitioningProfiles:
    def __init__(self, path: str) -> None:
        data = yaml.safe_load(open(path, "r", encoding="utf-8"))
        self._profiles: dict[str, PartitionProfile] = {}
        for profile_id, profile in data.get("profiles", {}).items():
            self._profiles[profile_id] = PartitionProfile(
                profile_id=profile_id,
                stream=profile.get("stream", ""),
                key_precedence=list(profile.get("key_precedence", [])),
                hash_algo=profile.get("hash_algo", "sha256"),
            )

    def get(self, profile_id: str) -> PartitionProfile:
        if profile_id not in self._profiles:
            raise KeyError(f"Unknown partitioning profile: {profile_id}")
        return self._profiles[profile_id]

    def streams(self) -> list[str]:
        streams = {profile.stream for profile in self._profiles.values() if profile.stream}
        return sorted(streams)

    def derive_key(self, profile_id: str, envelope: dict[str, Any]) -> str:
        profile = self.get(profile_id)
        raw = self._first_key_value(profile.key_precedence, envelope)
        if raw is None:
            raise IngestionError("PARTITION_KEY_MISSING")
        if profile.hash_algo != "sha256":
            raise IngestionError("UNSUPPORTED_HASH_ALGO")
        return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()

    def _first_key_value(self, paths: list[str], envelope: dict[str, Any]) -> Any | None:
        for path in paths:
            if path.startswith("payload."):
                value = _get_nested(envelope.get("payload", {}), path.split(".")[1:])
            else:
                value = envelope.get(path)
            if value not in (None, ""):
                return value
        return None


def _get_nested(payload: dict[str, Any], parts: list[str]) -> Any | None:
    current: Any = payload
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current
