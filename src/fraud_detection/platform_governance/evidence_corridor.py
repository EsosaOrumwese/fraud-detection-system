"""Evidence-ref resolution corridor (RBAC/allowlist + audit emission)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fraud_detection.platform_runtime import RUNS_ROOT
from fraud_detection.scenario_runner.storage import LocalObjectStore, ObjectStore, S3ObjectStore

from .writer import emit_platform_governance_event


DEFAULT_ALLOWLIST: frozenset[str] = frozenset({"svc:platform_run_reporter"})
ALLOWED_REF_TYPES: frozenset[str] = frozenset(
    {
        "receipt_ref",
        "quarantine_ref",
        "reconciliation_ref",
        "audit_ref",
        "artifact_ref",
    }
)


class EvidenceRefResolutionError(RuntimeError):
    """Raised when strict ref resolution fails closed."""


@dataclass(frozen=True)
class EvidenceRefResolutionRequest:
    actor_id: str
    source_type: str
    source_component: str
    purpose: str
    ref_type: str
    ref_id: str
    platform_run_id: str
    scenario_run_id: str | None = None
    observed_time: str | None = None


@dataclass(frozen=True)
class EvidenceRefResolutionResult:
    resolution_status: str
    reason_code: str | None
    ref_exists: bool
    ref_type: str
    ref_id: str
    platform_run_id: str
    scenario_run_id: str | None
    observed_time: str

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "resolution_status": self.resolution_status,
            "reason_code": self.reason_code,
            "ref_exists": self.ref_exists,
            "ref_type": self.ref_type,
            "ref_id": self.ref_id,
            "platform_run_id": self.platform_run_id,
            "observed_time": self.observed_time,
        }
        if self.scenario_run_id:
            payload["scenario_run_id"] = self.scenario_run_id
        return payload


class EvidenceRefResolutionCorridor:
    """Enforces allowlist-gated evidence ref resolution with audit/anomaly events."""

    def __init__(
        self,
        *,
        store: ObjectStore,
        actor_allowlist: set[str] | None = None,
        allowed_local_roots: tuple[Path, ...] | None = None,
    ) -> None:
        self.store = store
        self.actor_allowlist = actor_allowlist or _allowlist_from_env()
        roots: list[Path] = list(allowed_local_roots or ())
        roots.append(RUNS_ROOT.resolve())
        if isinstance(store, LocalObjectStore):
            roots.append(store.root.resolve())
        deduped: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            key = str(root)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(root)
        self.allowed_local_roots = tuple(deduped)

    def resolve(
        self,
        request: EvidenceRefResolutionRequest,
        *,
        raise_on_denied: bool = False,
    ) -> EvidenceRefResolutionResult:
        normalized = _normalize_request(request)
        observed_time = normalized.observed_time or _utc_now()
        ref_kind, ref_locator = _normalize_ref(normalized.ref_id)

        status = "RESOLVED"
        reason_code: str | None = None
        ref_exists = False

        if normalized.actor_id not in self.actor_allowlist:
            status = "DENIED"
            reason_code = "REF_ACCESS_DENIED"
        elif normalized.ref_type not in ALLOWED_REF_TYPES:
            status = "DENIED"
            reason_code = "REF_TYPE_NOT_ALLOWED"
        elif ref_kind == "invalid":
            status = "DENIED"
            reason_code = "REF_INVALID"
        elif not _ref_matches_run_scope(normalized.ref_id, normalized.platform_run_id):
            status = "DENIED"
            reason_code = "REF_SCOPE_MISMATCH"
        else:
            ref_exists = self._exists_ref(ref_kind, ref_locator)
            if not ref_exists:
                status = "DENIED"
                reason_code = "REF_NOT_FOUND"

        details = {
            "ref_type": normalized.ref_type,
            "ref_id": normalized.ref_id,
            "purpose": normalized.purpose,
            "platform_run_id": normalized.platform_run_id,
            "observed_time": observed_time,
            "resolution_status": status,
        }
        if reason_code:
            details["reason_code"] = reason_code
        emit_platform_governance_event(
            store=self.store,
            event_family="EVIDENCE_REF_RESOLVED",
            actor_id=normalized.actor_id,
            source_type=normalized.source_type,
            source_component=normalized.source_component,
            platform_run_id=normalized.platform_run_id,
            scenario_run_id=normalized.scenario_run_id,
            details=details,
        )
        if status != "RESOLVED":
            emit_platform_governance_event(
                store=self.store,
                event_family="CORRIDOR_ANOMALY",
                actor_id=normalized.actor_id,
                source_type=normalized.source_type,
                source_component=normalized.source_component,
                platform_run_id=normalized.platform_run_id,
                scenario_run_id=normalized.scenario_run_id,
                details={
                    "boundary": "evidence_ref_resolution",
                    "reason_code": reason_code or "REF_RESOLUTION_DENIED",
                    "ref_type": normalized.ref_type,
                    "ref_id": normalized.ref_id,
                    "purpose": normalized.purpose,
                    "observed_time": observed_time,
                },
            )
            if raise_on_denied:
                raise EvidenceRefResolutionError(reason_code or "REF_RESOLUTION_DENIED")

        return EvidenceRefResolutionResult(
            resolution_status=status,
            reason_code=reason_code,
            ref_exists=ref_exists,
            ref_type=normalized.ref_type,
            ref_id=normalized.ref_id,
            platform_run_id=normalized.platform_run_id,
            scenario_run_id=normalized.scenario_run_id,
            observed_time=observed_time,
        )

    def _exists_ref(self, ref_kind: str, ref_locator: str) -> bool:
        if ref_kind == "s3":
            if not isinstance(self.store, S3ObjectStore):
                return False
            relative = _s3_relative_path(self.store, ref_locator)
            return self.store.exists(relative)
        if ref_kind == "store":
            return self.store.exists(ref_locator)
        if ref_kind == "local":
            path = Path(ref_locator)
            candidate = path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()
            if not _is_under_roots(candidate, self.allowed_local_roots):
                return False
            return candidate.exists()
        return False


def build_evidence_ref_resolution_corridor(
    *,
    store: ObjectStore,
    actor_allowlist: list[str] | None = None,
) -> EvidenceRefResolutionCorridor:
    allowlist: set[str] | None
    if actor_allowlist is None:
        allowlist = None
    else:
        parsed = {item.strip() for item in actor_allowlist if str(item).strip()}
        allowlist = parsed or None
    return EvidenceRefResolutionCorridor(
        store=store,
        actor_allowlist=allowlist,
    )


def _normalize_request(request: EvidenceRefResolutionRequest) -> EvidenceRefResolutionRequest:
    actor_id = _required(request.actor_id, "actor_id")
    source_type = _required(request.source_type, "source_type").lower()
    source_component = _required(request.source_component, "source_component")
    purpose = _required(request.purpose, "purpose")
    ref_type = _required(request.ref_type, "ref_type").lower()
    ref_id = _required(request.ref_id, "ref_id")
    platform_run_id = _required(request.platform_run_id, "platform_run_id")
    scenario_run_id = _strip_or_none(request.scenario_run_id)
    observed_time = _strip_or_none(request.observed_time)
    return EvidenceRefResolutionRequest(
        actor_id=actor_id,
        source_type=source_type,
        source_component=source_component,
        purpose=purpose,
        ref_type=ref_type,
        ref_id=ref_id,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        observed_time=observed_time,
    )


def _allowlist_from_env() -> set[str]:
    raw = (os.getenv("EVIDENCE_REF_RESOLVER_ALLOWLIST") or "").strip()
    if not raw:
        return set(DEFAULT_ALLOWLIST)
    values = {item.strip() for item in raw.split(",") if item.strip()}
    return values or set(DEFAULT_ALLOWLIST)


def _normalize_ref(ref_id: str) -> tuple[str, str]:
    text = str(ref_id or "").strip()
    if not text:
        return "invalid", text
    if text.startswith("s3://"):
        return "s3", text
    if text.startswith("http://") or text.startswith("https://"):
        return "invalid", text
    if text.startswith("fraud-platform/"):
        return "store", text
    if text.startswith("platform_"):
        return "store", text
    return "local", text


def _s3_relative_path(store: S3ObjectStore, absolute_path: str) -> str:
    text = str(absolute_path or "").strip()
    if not text.startswith("s3://"):
        return text
    parsed = urlparse(text)
    if parsed.netloc != store.bucket:
        return "__invalid_bucket__"
    key = parsed.path.lstrip("/")
    store_prefix = f"{store.prefix}/" if store.prefix else ""
    if store_prefix and key.startswith(store_prefix):
        return key[len(store_prefix) :]
    return key


def _ref_matches_run_scope(ref_id: str, platform_run_id: str) -> bool:
    text = str(ref_id or "").strip()
    run_id = str(platform_run_id or "").strip()
    if not text or not run_id:
        return False
    normalized = text.replace("\\", "/")
    segments = [item for item in normalized.split("/") if item]
    return run_id in segments


def _is_under_roots(path: Path, roots: tuple[Path, ...]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _required(value: str | None, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise EvidenceRefResolutionError(f"{field_name} is required")
    return text


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
