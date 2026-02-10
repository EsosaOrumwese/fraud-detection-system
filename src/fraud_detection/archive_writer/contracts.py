"""Archive writer contracts (Phase 6.0)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping


class ArchiveWriterContractError(ValueError):
    """Raised when archive writer contract inputs are invalid."""


_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9_.:-]+")


@dataclass(frozen=True)
class OriginOffset:
    topic: str
    partition: int
    offset: str
    offset_kind: str

    def __post_init__(self) -> None:
        if not str(self.topic or "").strip():
            raise ArchiveWriterContractError("origin_offset.topic is required")
        if int(self.partition) < 0:
            raise ArchiveWriterContractError("origin_offset.partition must be >= 0")
        if not str(self.offset or "").strip():
            raise ArchiveWriterContractError("origin_offset.offset is required")
        if not str(self.offset_kind or "").strip():
            raise ArchiveWriterContractError("origin_offset.offset_kind is required")

    def as_dict(self) -> dict[str, Any]:
        return {
            "topic": str(self.topic),
            "partition": int(self.partition),
            "offset": str(self.offset),
            "offset_kind": str(self.offset_kind),
        }

    def as_archive_tokens(self) -> dict[str, str]:
        return {
            "topic": _sanitize_token(str(self.topic)),
            "partition": str(int(self.partition)),
            "offset_kind": _sanitize_token(str(self.offset_kind)),
            "offset": _sanitize_token(str(self.offset)),
        }


@dataclass(frozen=True)
class ArchiveEventRecord:
    archived_at_utc: str
    platform_run_id: str
    scenario_run_id: str
    manifest_fingerprint: str
    parameter_hash: str
    scenario_id: str
    seed: str | None
    event_id: str
    event_type: str
    ts_utc: str
    payload_hash: str
    origin_offset: OriginOffset
    envelope: dict[str, Any]

    @classmethod
    def from_bus_record(
        cls,
        *,
        envelope: Mapping[str, Any],
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        archived_at_utc: str | None = None,
    ) -> "ArchiveEventRecord":
        if not isinstance(envelope, Mapping):
            raise ArchiveWriterContractError("envelope must be a mapping")
        payload = dict(envelope)
        required = {
            "platform_run_id": _required(payload.get("platform_run_id"), "platform_run_id"),
            "scenario_run_id": _required(payload.get("scenario_run_id"), "scenario_run_id"),
            "manifest_fingerprint": _required(payload.get("manifest_fingerprint"), "manifest_fingerprint"),
            "parameter_hash": _required(payload.get("parameter_hash"), "parameter_hash"),
            "scenario_id": _required(payload.get("scenario_id"), "scenario_id"),
            "event_id": _required(payload.get("event_id"), "event_id"),
            "event_type": _required(payload.get("event_type"), "event_type"),
            "ts_utc": _required(payload.get("ts_utc"), "ts_utc"),
        }
        origin = OriginOffset(
            topic=str(topic),
            partition=int(partition),
            offset=str(offset),
            offset_kind=str(offset_kind),
        )
        return cls(
            archived_at_utc=archived_at_utc or _utc_now(),
            platform_run_id=required["platform_run_id"],
            scenario_run_id=required["scenario_run_id"],
            manifest_fingerprint=required["manifest_fingerprint"],
            parameter_hash=required["parameter_hash"],
            scenario_id=required["scenario_id"],
            seed=_optional(payload.get("seed")),
            event_id=required["event_id"],
            event_type=required["event_type"],
            ts_utc=required["ts_utc"],
            payload_hash=canonical_payload_hash(payload),
            origin_offset=origin,
            envelope=payload,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "archived_at_utc": self.archived_at_utc,
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "manifest_fingerprint": self.manifest_fingerprint,
            "parameter_hash": self.parameter_hash,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "ts_utc": self.ts_utc,
            "payload_hash": self.payload_hash,
            "origin_offset": self.origin_offset.as_dict(),
            "envelope": dict(self.envelope),
        }

    def archive_relative_path(self, *, run_prefix: str) -> str:
        tokens = self.origin_offset.as_archive_tokens()
        return (
            f"{run_prefix}/archive/events/"
            f"topic={tokens['topic']}/partition={tokens['partition']}/"
            f"offset_kind={tokens['offset_kind']}/offset={tokens['offset']}.json"
        )


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping):
        raise ArchiveWriterContractError("payload must be a mapping")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _required(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ArchiveWriterContractError(f"{field_name} is required")
    return text


def _optional(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _sanitize_token(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "_"
    return _SAFE_TOKEN.sub("_", text)


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
