"""OFP snapshot index persistence (SQLite/Postgres)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

import psycopg
from fraud_detection.postgres_runtime import postgres_threadlocal_connection

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn


@dataclass(frozen=True)
class SnapshotIndexRecord:
    snapshot_hash: str
    stream_id: str
    platform_run_id: str
    scenario_run_id: str
    as_of_time_utc: str
    created_at_utc: str
    feature_groups_json: str
    feature_def_policy_id: str
    feature_def_revision: str
    feature_def_content_digest: str
    run_config_digest: str
    eb_offset_basis_json: str
    graph_version_json: str | None
    snapshot_ref: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "snapshot_hash": self.snapshot_hash,
            "stream_id": self.stream_id,
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "as_of_time_utc": self.as_of_time_utc,
            "created_at_utc": self.created_at_utc,
            "feature_groups_json": self.feature_groups_json,
            "feature_def_policy_id": self.feature_def_policy_id,
            "feature_def_revision": self.feature_def_revision,
            "feature_def_content_digest": self.feature_def_content_digest,
            "run_config_digest": self.run_config_digest,
            "eb_offset_basis_json": self.eb_offset_basis_json,
            "graph_version_json": self.graph_version_json,
            "snapshot_ref": self.snapshot_ref,
        }


class SnapshotIndex:
    def upsert(self, record: SnapshotIndexRecord) -> None:
        raise NotImplementedError

    def get(self, snapshot_hash: str) -> SnapshotIndexRecord | None:
        raise NotImplementedError


def build_snapshot_index(dsn: str) -> SnapshotIndex:
    if is_postgres_dsn(dsn):
        return PostgresSnapshotIndex(dsn=dsn)
    return SqliteSnapshotIndex(path=Path(_sqlite_path(dsn)))


@dataclass
class SqliteSnapshotIndex(SnapshotIndex):
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ofp_snapshot_index (
                    snapshot_hash TEXT PRIMARY KEY,
                    stream_id TEXT NOT NULL,
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    as_of_time_utc TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    feature_groups_json TEXT NOT NULL,
                    feature_def_policy_id TEXT NOT NULL,
                    feature_def_revision TEXT NOT NULL,
                    feature_def_content_digest TEXT NOT NULL,
                    run_config_digest TEXT NOT NULL,
                    eb_offset_basis_json TEXT NOT NULL,
                    graph_version_json TEXT,
                    snapshot_ref TEXT NOT NULL
                )
                """
            )

    def upsert(self, record: SnapshotIndexRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ofp_snapshot_index (
                    snapshot_hash, stream_id, platform_run_id, scenario_run_id,
                    as_of_time_utc, created_at_utc, feature_groups_json,
                    feature_def_policy_id, feature_def_revision, feature_def_content_digest,
                    run_config_digest, eb_offset_basis_json, graph_version_json, snapshot_ref
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_hash) DO UPDATE SET
                    stream_id = excluded.stream_id,
                    platform_run_id = excluded.platform_run_id,
                    scenario_run_id = excluded.scenario_run_id,
                    as_of_time_utc = excluded.as_of_time_utc,
                    created_at_utc = excluded.created_at_utc,
                    feature_groups_json = excluded.feature_groups_json,
                    feature_def_policy_id = excluded.feature_def_policy_id,
                    feature_def_revision = excluded.feature_def_revision,
                    feature_def_content_digest = excluded.feature_def_content_digest,
                    run_config_digest = excluded.run_config_digest,
                    eb_offset_basis_json = excluded.eb_offset_basis_json,
                    graph_version_json = excluded.graph_version_json,
                    snapshot_ref = excluded.snapshot_ref
                """,
                (
                    record.snapshot_hash,
                    record.stream_id,
                    record.platform_run_id,
                    record.scenario_run_id,
                    record.as_of_time_utc,
                    record.created_at_utc,
                    record.feature_groups_json,
                    record.feature_def_policy_id,
                    record.feature_def_revision,
                    record.feature_def_content_digest,
                    record.run_config_digest,
                    record.eb_offset_basis_json,
                    record.graph_version_json,
                    record.snapshot_ref,
                ),
            )

    def get(self, snapshot_hash: str) -> SnapshotIndexRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT snapshot_hash, stream_id, platform_run_id, scenario_run_id,
                       as_of_time_utc, created_at_utc, feature_groups_json,
                       feature_def_policy_id, feature_def_revision, feature_def_content_digest,
                       run_config_digest, eb_offset_basis_json, graph_version_json, snapshot_ref
                FROM ofp_snapshot_index
                WHERE snapshot_hash = ?
                """,
                (snapshot_hash,),
            ).fetchone()
        if not row:
            return None
        return SnapshotIndexRecord(
            snapshot_hash=str(row[0]),
            stream_id=str(row[1]),
            platform_run_id=str(row[2]),
            scenario_run_id=str(row[3]),
            as_of_time_utc=str(row[4]),
            created_at_utc=str(row[5]),
            feature_groups_json=str(row[6]),
            feature_def_policy_id=str(row[7]),
            feature_def_revision=str(row[8]),
            feature_def_content_digest=str(row[9]),
            run_config_digest=str(row[10]),
            eb_offset_basis_json=str(row[11]),
            graph_version_json=str(row[12]) if row[12] is not None else None,
            snapshot_ref=str(row[13]),
        )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path))


@dataclass
class PostgresSnapshotIndex(SnapshotIndex):
    dsn: str

    def __post_init__(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ofp_snapshot_index (
                    snapshot_hash TEXT PRIMARY KEY,
                    stream_id TEXT NOT NULL,
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    as_of_time_utc TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    feature_groups_json TEXT NOT NULL,
                    feature_def_policy_id TEXT NOT NULL,
                    feature_def_revision TEXT NOT NULL,
                    feature_def_content_digest TEXT NOT NULL,
                    run_config_digest TEXT NOT NULL,
                    eb_offset_basis_json TEXT NOT NULL,
                    graph_version_json TEXT,
                    snapshot_ref TEXT NOT NULL
                )
                """
            )

    def upsert(self, record: SnapshotIndexRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ofp_snapshot_index (
                    snapshot_hash, stream_id, platform_run_id, scenario_run_id,
                    as_of_time_utc, created_at_utc, feature_groups_json,
                    feature_def_policy_id, feature_def_revision, feature_def_content_digest,
                    run_config_digest, eb_offset_basis_json, graph_version_json, snapshot_ref
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (snapshot_hash) DO UPDATE SET
                    stream_id = EXCLUDED.stream_id,
                    platform_run_id = EXCLUDED.platform_run_id,
                    scenario_run_id = EXCLUDED.scenario_run_id,
                    as_of_time_utc = EXCLUDED.as_of_time_utc,
                    created_at_utc = EXCLUDED.created_at_utc,
                    feature_groups_json = EXCLUDED.feature_groups_json,
                    feature_def_policy_id = EXCLUDED.feature_def_policy_id,
                    feature_def_revision = EXCLUDED.feature_def_revision,
                    feature_def_content_digest = EXCLUDED.feature_def_content_digest,
                    run_config_digest = EXCLUDED.run_config_digest,
                    eb_offset_basis_json = EXCLUDED.eb_offset_basis_json,
                    graph_version_json = EXCLUDED.graph_version_json,
                    snapshot_ref = EXCLUDED.snapshot_ref
                """,
                (
                    record.snapshot_hash,
                    record.stream_id,
                    record.platform_run_id,
                    record.scenario_run_id,
                    record.as_of_time_utc,
                    record.created_at_utc,
                    record.feature_groups_json,
                    record.feature_def_policy_id,
                    record.feature_def_revision,
                    record.feature_def_content_digest,
                    record.run_config_digest,
                    record.eb_offset_basis_json,
                    record.graph_version_json,
                    record.snapshot_ref,
                ),
            )

    def get(self, snapshot_hash: str) -> SnapshotIndexRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT snapshot_hash, stream_id, platform_run_id, scenario_run_id,
                       as_of_time_utc, created_at_utc, feature_groups_json,
                       feature_def_policy_id, feature_def_revision, feature_def_content_digest,
                       run_config_digest, eb_offset_basis_json, graph_version_json, snapshot_ref
                FROM ofp_snapshot_index
                WHERE snapshot_hash = %s
                """,
                (snapshot_hash,),
            ).fetchone()
        if not row:
            return None
        return SnapshotIndexRecord(
            snapshot_hash=str(row[0]),
            stream_id=str(row[1]),
            platform_run_id=str(row[2]),
            scenario_run_id=str(row[3]),
            as_of_time_utc=str(row[4]),
            created_at_utc=str(row[5]),
            feature_groups_json=str(row[6]),
            feature_def_policy_id=str(row[7]),
            feature_def_revision=str(row[8]),
            feature_def_content_digest=str(row[9]),
            run_config_digest=str(row[10]),
            eb_offset_basis_json=str(row[11]),
            graph_version_json=str(row[12]) if row[12] is not None else None,
            snapshot_ref=str(row[13]),
        )

    def _connect(self) -> psycopg.Connection:
        return postgres_threadlocal_connection(self.dsn)


def _sqlite_path(dsn: str) -> str:
    if dsn.startswith("sqlite:///"):
        return dsn.replace("sqlite:///", "", 1)
    if dsn.startswith("sqlite://"):
        return dsn.replace("sqlite://", "", 1)
    return dsn

