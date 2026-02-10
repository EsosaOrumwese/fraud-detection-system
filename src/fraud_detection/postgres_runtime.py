"""Shared Postgres runtime connection helpers."""

from __future__ import annotations

from contextlib import AbstractContextManager
import json
import threading
import time
from typing import Any, Mapping

import psycopg


_THREAD_LOCAL = threading.local()


class _ThreadLocalPostgresContext(AbstractContextManager[psycopg.Connection[Any]]):
    def __init__(self, *, dsn: str, connect_kwargs: Mapping[str, Any]) -> None:
        self._dsn = str(dsn or "").strip()
        self._connect_kwargs = dict(connect_kwargs)
        self._key = _connection_key(self._dsn, self._connect_kwargs)
        self._connection: psycopg.Connection[Any] | None = None

    def __enter__(self) -> psycopg.Connection[Any]:
        self._connection = _acquire_connection(self._key, self._dsn, self._connect_kwargs)
        return self._connection

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        connection = self._connection
        self._connection = None
        if connection is None:
            return False
        if exc_type is not None:
            # Persistent connections must be rolled back after failed operations.
            try:
                connection.rollback()
            except Exception:
                _drop_connection(self._key)
                return False
        elif not bool(getattr(connection, "autocommit", False)):
            # Mirror psycopg context-manager behavior: successful scope exits commit.
            try:
                connection.commit()
            except Exception:
                _drop_connection(self._key)
                raise
        if _is_connection_closed(connection):
            _drop_connection(self._key)
        return False


def postgres_threadlocal_connection(
    dsn: str,
    **connect_kwargs: Any,
) -> AbstractContextManager[psycopg.Connection[Any]]:
    """Return a context manager that reuses a thread-local Postgres connection."""
    return _ThreadLocalPostgresContext(dsn=dsn, connect_kwargs=connect_kwargs)


def clear_threadlocal_postgres_connections() -> None:
    """Close and clear all cached Postgres connections for the current thread."""
    connections = _thread_connections()
    for key in list(connections.keys()):
        _drop_connection(key)


def _thread_connections() -> dict[str, psycopg.Connection[Any]]:
    value = getattr(_THREAD_LOCAL, "connections", None)
    if isinstance(value, dict):
        return value
    connections: dict[str, psycopg.Connection[Any]] = {}
    _THREAD_LOCAL.connections = connections
    return connections


def _connection_key(dsn: str, connect_kwargs: Mapping[str, Any]) -> str:
    payload = {"dsn": dsn, "kwargs": connect_kwargs}
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str)


def _acquire_connection(
    key: str,
    dsn: str,
    connect_kwargs: Mapping[str, Any],
) -> psycopg.Connection[Any]:
    connections = _thread_connections()
    cached = connections.get(key)
    if cached is not None and not _is_connection_closed(cached):
        return cached
    if cached is not None:
        _drop_connection(key)

    retries = 3
    backoff_seconds = 0.05
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            connection = psycopg.connect(dsn, **dict(connect_kwargs))
            connections[key] = connection
            return connection
        except psycopg.OperationalError as exc:
            last_error = exc
            if attempt >= (retries - 1):
                break
            time.sleep(backoff_seconds * (2**attempt))
    if last_error is not None:
        raise last_error
    raise psycopg.OperationalError("postgres connection attempt failed")


def _drop_connection(key: str) -> None:
    connections = _thread_connections()
    connection = connections.pop(key, None)
    if connection is None:
        return
    try:
        connection.close()
    except Exception:
        pass


def _is_connection_closed(connection: psycopg.Connection[Any]) -> bool:
    if bool(getattr(connection, "closed", False)):
        return True
    if bool(getattr(connection, "broken", False)):
        return True
    return False
