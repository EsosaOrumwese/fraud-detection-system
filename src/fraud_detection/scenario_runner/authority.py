"""Run authority: equivalence registry and lease management (durable)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from .ids import hash_payload, run_id_from_equivalence_key


@dataclass(frozen=True)
class RunHandle:
    run_id: str
    intent_fingerprint: str
    leader: bool
    lease_token: str | None
    status_ref: str | None = None
    facts_view_ref: str | None = None


class AuthorityStore:
    def resolve_equivalence(self, run_equivalence_key: str, intent_fingerprint: str) -> tuple[str, bool]:
        raise NotImplementedError

    def acquire_lease(self, run_id: str, owner_id: str, ttl_seconds: int) -> tuple[bool, str | None]:
        raise NotImplementedError

    def check_lease(self, run_id: str, lease_token: str) -> bool:
        raise NotImplementedError

    def renew_lease(self, run_id: str, lease_token: str, ttl_seconds: int) -> bool:
        raise NotImplementedError

    def release_lease(self, run_id: str, lease_token: str) -> bool:
        raise NotImplementedError


class SQLiteAuthorityStore(AuthorityStore):
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sr_run_equivalence (
                    run_equivalence_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    intent_fingerprint TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sr_run_leases (
                    run_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    lease_token TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def resolve_equivalence(self, run_equivalence_key: str, intent_fingerprint: str) -> tuple[str, bool]:
        run_id = run_id_from_equivalence_key(run_equivalence_key)
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT run_id, intent_fingerprint FROM sr_run_equivalence WHERE run_equivalence_key = ?",
                (run_equivalence_key,),
            ).fetchone()
            if row:
                existing_run_id, existing_fingerprint = row
                if existing_fingerprint != intent_fingerprint:
                    raise RuntimeError("EQUIV_KEY_COLLISION")
                conn.execute(
                    "UPDATE sr_run_equivalence SET last_seen_at = ? WHERE run_equivalence_key = ?",
                    (now, run_equivalence_key),
                )
                return existing_run_id, False
            conn.execute(
                """
                INSERT INTO sr_run_equivalence
                (run_equivalence_key, run_id, intent_fingerprint, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_equivalence_key, run_id, intent_fingerprint, now, now),
            )
            return run_id, True

    def acquire_lease(self, run_id: str, owner_id: str, ttl_seconds: int) -> tuple[bool, str | None]:
        now = datetime.now(tz=timezone.utc)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
        token = hash_payload(f"{run_id}|{owner_id}|{now.isoformat()}")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT lease_token, expires_at FROM sr_run_leases WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row:
                _, current_expires = row
                if datetime.fromisoformat(current_expires) > now:
                    return False, None
                conn.execute(
                    """
                    UPDATE sr_run_leases
                    SET owner_id = ?, lease_token = ?, expires_at = ?, updated_at = ?
                    WHERE run_id = ?
                    """,
                    (owner_id, token, expires_at, now.isoformat(), run_id),
                )
                return True, token
            conn.execute(
                """
                INSERT INTO sr_run_leases
                (run_id, owner_id, lease_token, expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, owner_id, token, expires_at, now.isoformat()),
            )
            return True, token

    def check_lease(self, run_id: str, lease_token: str) -> bool:
        now = datetime.now(tz=timezone.utc)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT lease_token, expires_at FROM sr_run_leases WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if not row:
                return False
            token, expires_at = row
            if token != lease_token:
                return False
            return datetime.fromisoformat(expires_at) > now

    def renew_lease(self, run_id: str, lease_token: str, ttl_seconds: int) -> bool:
        now = datetime.now(tz=timezone.utc)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE sr_run_leases
                SET expires_at = ?, updated_at = ?
                WHERE run_id = ? AND lease_token = ?
                """,
                (expires_at, now.isoformat(), run_id, lease_token),
            )
            return cur.rowcount > 0

    def release_lease(self, run_id: str, lease_token: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM sr_run_leases WHERE run_id = ? AND lease_token = ?",
                (run_id, lease_token),
            )
            return cur.rowcount > 0


class PostgresAuthorityStore(AuthorityStore):
    def __init__(self, dsn: str) -> None:
        import psycopg

        self._psycopg = psycopg
        self.dsn = dsn
        self._init_schema()

    def _connect(self):
        return self._psycopg.connect(self.dsn)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sr_run_equivalence (
                        run_equivalence_key TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        intent_fingerprint TEXT NOT NULL,
                        first_seen_at TEXT NOT NULL,
                        last_seen_at TEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sr_run_leases (
                        run_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        lease_token TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )

    def resolve_equivalence(self, run_equivalence_key: str, intent_fingerprint: str) -> tuple[str, bool]:
        run_id = run_id_from_equivalence_key(run_equivalence_key)
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT run_id, intent_fingerprint FROM sr_run_equivalence WHERE run_equivalence_key = %s",
                    (run_equivalence_key,),
                )
                row = cur.fetchone()
                if row:
                    existing_run_id, existing_fingerprint = row
                    if existing_fingerprint != intent_fingerprint:
                        raise RuntimeError("EQUIV_KEY_COLLISION")
                    cur.execute(
                        "UPDATE sr_run_equivalence SET last_seen_at = %s WHERE run_equivalence_key = %s",
                        (now, run_equivalence_key),
                    )
                    return existing_run_id, False
                cur.execute(
                    """
                    INSERT INTO sr_run_equivalence
                    (run_equivalence_key, run_id, intent_fingerprint, first_seen_at, last_seen_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (run_equivalence_key, run_id, intent_fingerprint, now, now),
                )
                if cur.rowcount == 0:
                    cur.execute(
                        "SELECT run_id, intent_fingerprint FROM sr_run_equivalence WHERE run_equivalence_key = %s",
                        (run_equivalence_key,),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise RuntimeError("EQUIV_KEY_RESOLUTION_FAILED")
                    existing_run_id, existing_fingerprint = row
                    if existing_fingerprint != intent_fingerprint:
                        raise RuntimeError("EQUIV_KEY_COLLISION")
                    return existing_run_id, False
                return run_id, True

    def acquire_lease(self, run_id: str, owner_id: str, ttl_seconds: int) -> tuple[bool, str | None]:
        now = datetime.now(tz=timezone.utc)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
        token = hash_payload(f"{run_id}|{owner_id}|{now.isoformat()}")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT lease_token, expires_at FROM sr_run_leases WHERE run_id = %s",
                    (run_id,),
                )
                row = cur.fetchone()
                if row:
                    _, current_expires = row
                    if datetime.fromisoformat(current_expires) > now:
                        return False, None
                    cur.execute(
                        """
                        UPDATE sr_run_leases
                        SET owner_id = %s, lease_token = %s, expires_at = %s, updated_at = %s
                        WHERE run_id = %s
                        """,
                        (owner_id, token, expires_at, now.isoformat(), run_id),
                    )
                    return True, token
                cur.execute(
                    """
                    INSERT INTO sr_run_leases
                    (run_id, owner_id, lease_token, expires_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (run_id, owner_id, token, expires_at, now.isoformat()),
                )
                return True, token

    def check_lease(self, run_id: str, lease_token: str) -> bool:
        now = datetime.now(tz=timezone.utc)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT lease_token, expires_at FROM sr_run_leases WHERE run_id = %s",
                    (run_id,),
                )
                row = cur.fetchone()
                if not row:
                    return False
                token, expires_at = row
                if token != lease_token:
                    return False
                return datetime.fromisoformat(expires_at) > now

    def renew_lease(self, run_id: str, lease_token: str, ttl_seconds: int) -> bool:
        now = datetime.now(tz=timezone.utc)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE sr_run_leases
                    SET expires_at = %s, updated_at = %s
                    WHERE run_id = %s AND lease_token = %s
                    """,
                    (expires_at, now.isoformat(), run_id, lease_token),
                )
                return cur.rowcount > 0

    def release_lease(self, run_id: str, lease_token: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM sr_run_leases WHERE run_id = %s AND lease_token = %s",
                    (run_id, lease_token),
                )
                return cur.rowcount > 0


def build_authority_store(dsn: str) -> AuthorityStore:
    parsed = urlparse(dsn)
    scheme = parsed.scheme.lower()
    if scheme.startswith("sqlite"):
        if dsn.startswith("sqlite:///"):
            path = dsn.replace("sqlite:///", "", 1)
        elif dsn.startswith("sqlite://"):
            path = dsn.replace("sqlite://", "", 1)
        else:
            path = parsed.path
        return SQLiteAuthorityStore(Path(path))
    if scheme.startswith("postgres"):
        return PostgresAuthorityStore(dsn)
    raise ValueError(f"Unsupported authority_store_dsn scheme: {scheme}")


class EquivalenceRegistry:
    def __init__(self, store: AuthorityStore) -> None:
        self.store = store

    def resolve(self, run_equivalence_key: str, intent_fingerprint: str) -> tuple[str, bool]:
        return self.store.resolve_equivalence(run_equivalence_key, intent_fingerprint)


class LeaseManager:
    def __init__(self, store: AuthorityStore, ttl_seconds: int = 300) -> None:
        self.store = store
        self.ttl_seconds = ttl_seconds

    def acquire(self, run_id: str, owner_id: str) -> tuple[bool, str | None]:
        return self.store.acquire_lease(run_id, owner_id, self.ttl_seconds)

    def renew(self, run_id: str, lease_token: str) -> bool:
        return self.store.renew_lease(run_id, lease_token, self.ttl_seconds)

    def check(self, run_id: str, lease_token: str) -> bool:
        return self.store.check_lease(run_id, lease_token)

    def release(self, run_id: str, lease_token: str) -> bool:
        return self.store.release_lease(run_id, lease_token)
