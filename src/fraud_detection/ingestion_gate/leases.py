"""READY lease management for distributed consumption."""

from __future__ import annotations

import hashlib
import logging
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from .errors import IngestionError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LeaseHandle:
    message_id: str
    run_id: str
    owner_id: str
    acquired_at_utc: str
    backend: str
    _release: Callable[[], None]

    def release(self) -> None:
        try:
            self._release()
        except Exception:  # pragma: no cover - defensive
            logger.exception("IG lease release failed message_id=%s", self.message_id)


class ReadyLeaseManager(Protocol):
    def try_acquire(self, message_id: str, run_id: str) -> LeaseHandle | None:
        ...


class NullReadyLeaseManager:
    """Non-distributed lease manager for local single-instance use."""

    def __init__(self, owner_id: str | None = None) -> None:
        self.owner_id = owner_id or _default_owner()

    def try_acquire(self, message_id: str, run_id: str) -> LeaseHandle | None:
        acquired_at = datetime.now(tz=timezone.utc).isoformat()
        return LeaseHandle(
            message_id=message_id,
            run_id=run_id,
            owner_id=self.owner_id,
            acquired_at_utc=acquired_at,
            backend="none",
            _release=lambda: None,
        )


class PostgresReadyLeaseManager:
    def __init__(self, dsn: str, namespace: str = "ig_ready", owner_id: str | None = None) -> None:
        self.dsn = dsn
        self.namespace = namespace
        self.owner_id = owner_id or _default_owner()

    def try_acquire(self, message_id: str, run_id: str) -> LeaseHandle | None:
        try:
            import psycopg
        except Exception as exc:  # pragma: no cover - optional dependency
            raise IngestionError("LEASE_BACKEND_UNAVAILABLE", "psycopg missing") from exc
        try:
            conn = psycopg.connect(self.dsn, autocommit=True)
            key1, key2 = _lock_keys(self.namespace, message_id)
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s, %s)", (key1, key2))
                acquired = cur.fetchone()[0]
            if not acquired:
                conn.close()
                return None
            acquired_at = datetime.now(tz=timezone.utc).isoformat()

            def _release() -> None:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT pg_advisory_unlock(%s, %s)", (key1, key2))
                finally:
                    conn.close()

            return LeaseHandle(
                message_id=message_id,
                run_id=run_id,
                owner_id=self.owner_id,
                acquired_at_utc=acquired_at,
                backend="postgres",
                _release=_release,
            )
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError("LEASE_BACKEND_UNAVAILABLE", str(exc)[:160]) from exc


def build_ready_lease_manager(
    *,
    backend: str,
    dsn: str | None,
    namespace: str,
    owner_id: str | None,
) -> ReadyLeaseManager:
    backend_norm = (backend or "none").lower()
    if backend_norm in {"none", "disabled", "local"}:
        return NullReadyLeaseManager(owner_id=owner_id)
    if backend_norm == "postgres":
        if not dsn:
            raise IngestionError("LEASE_BACKEND_UNAVAILABLE", "missing_dsn")
        return PostgresReadyLeaseManager(dsn, namespace=namespace, owner_id=owner_id)
    raise IngestionError("LEASE_BACKEND_UNAVAILABLE", f"unsupported:{backend_norm}")


def _lock_keys(namespace: str, message_id: str) -> tuple[int, int]:
    raw = f"{namespace}:{message_id}".encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    hi = int.from_bytes(digest[:4], "big", signed=False)
    lo = int.from_bytes(digest[4:8], "big", signed=False)
    return _to_int32(hi), _to_int32(lo)


def _to_int32(value: int) -> int:
    if value >= 2**31:
        return value - 2**32
    return value


def _default_owner() -> str:
    return os.getenv("IG_INSTANCE_ID") or socket.gethostname()
