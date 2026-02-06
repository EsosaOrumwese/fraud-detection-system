"""OFP snapshot materialization + index persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fraud_detection.scenario_runner.storage import build_object_store

from .config import OfpProfile
from .contracts import build_snapshot_hash
from .snapshot_index import SnapshotIndex, SnapshotIndexRecord, build_snapshot_index
from .store import OfpStore, build_store


@dataclass
class OfpSnapshotMaterializer:
    profile: OfpProfile
    store: OfpStore
    index: SnapshotIndex
    object_store: Any
    object_store_root: str

    @classmethod
    def build(cls, profile_path: str) -> "OfpSnapshotMaterializer":
        profile = OfpProfile.load(Path(profile_path))
        store = build_store(
            profile.wiring.projection_db_dsn,
            stream_id=profile.policy.stream_id,
            basis_stream=profile.wiring.event_bus_topic,
            run_config_digest=profile.policy.run_config_digest,
            feature_def_policy_id=profile.policy.feature_def_policy_rev.policy_id,
            feature_def_revision=profile.policy.feature_def_policy_rev.revision,
            feature_def_content_digest=profile.policy.feature_def_policy_rev.content_digest,
        )
        index = build_snapshot_index(profile.wiring.snapshot_index_dsn)
        object_store = build_object_store(
            profile.wiring.snapshot_store_root,
            s3_endpoint_url=profile.wiring.snapshot_store_endpoint,
            s3_region=profile.wiring.snapshot_store_region,
            s3_path_style=profile.wiring.snapshot_store_path_style,
        )
        return cls(
            profile=profile,
            store=store,
            index=index,
            object_store=object_store,
            object_store_root=profile.wiring.snapshot_store_root,
        )

    def materialize(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        as_of_time_utc: str | None = None,
        graph_version: dict[str, Any] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        try:
            basis = self.store.input_basis()
            if not basis:
                raise RuntimeError("OFP_SNAPSHOT_BASIS_MISSING")

            projection_meta = self.store.projection_meta() or {}
            rows = self.store.list_group_states(
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                group_name=self.profile.policy.feature_group_name,
                group_version=self.profile.policy.feature_group_version,
            )
            if not rows:
                raise RuntimeError("OFP_SNAPSHOT_STATE_MISSING")
            created_at_utc = _utc_now()
            resolved_as_of = as_of_time_utc or str(basis.get("window_end_utc") or created_at_utc)

            feature_map: dict[str, Any] = {}
            for row in rows:
                key = f"{row['key_type']}:{row['key_id']}"
                feature_map[key] = {
                    "event_count": int(row["event_count"]),
                    "amount_sum": float(row["amount_sum"]),
                    "last_event_ts_utc": row.get("last_event_ts_utc"),
                }

            source_row = rows[0] if rows else {}
            pins = {
                "manifest_fingerprint": str(source_row.get("manifest_fingerprint") or ""),
                "parameter_hash": str(source_row.get("parameter_hash") or ""),
                "seed": int(source_row.get("seed") or 0),
                "scenario_id": str(source_row.get("scenario_id") or ""),
                "platform_run_id": platform_run_id,
                "scenario_run_id": scenario_run_id,
            }
            run_id = source_row.get("run_id")
            if run_id:
                pins["run_id"] = str(run_id)

            snapshot: dict[str, Any] = {
                "pins": pins,
                "created_at_utc": created_at_utc,
                "as_of_time_utc": resolved_as_of,
                "feature_groups": [
                    {
                        "name": self.profile.policy.feature_group_name,
                        "version": self.profile.policy.feature_group_version,
                    }
                ],
                "feature_def_policy_rev": {
                    "policy_id": str(
                        projection_meta.get("feature_def_policy_id")
                        or self.profile.policy.feature_def_policy_rev.policy_id
                    ),
                    "revision": str(
                        projection_meta.get("feature_def_revision")
                        or self.profile.policy.feature_def_policy_rev.revision
                    ),
                    "content_digest": str(
                        projection_meta.get("feature_def_content_digest")
                        or self.profile.policy.feature_def_policy_rev.content_digest
                    ),
                },
                "eb_offset_basis": basis,
                "run_config_digest": str(
                    projection_meta.get("run_config_digest")
                    or self.profile.policy.run_config_digest
                ),
                "features": feature_map,
                "freshness": {
                    "stale_groups": [],
                    "missing_groups": []
                    if feature_map
                    else [self.profile.policy.feature_group_name],
                },
            }
            if graph_version:
                snapshot["graph_version"] = graph_version
            if notes:
                snapshot["notes"] = notes

            snapshot_hash = build_snapshot_hash(snapshot)
            snapshot["snapshot_hash"] = snapshot_hash
            relative_path = _snapshot_relative_path(
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                snapshot_hash=snapshot_hash,
            )
            try:
                artifact = self.object_store.write_json_if_absent(relative_path, snapshot)
                snapshot_ref = artifact.path
            except FileExistsError:
                snapshot_ref = _artifact_ref(self.object_store_root, relative_path)
            snapshot["snapshot_ref"] = snapshot_ref

            record = SnapshotIndexRecord(
                snapshot_hash=snapshot_hash,
                stream_id=self.profile.policy.stream_id,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                as_of_time_utc=resolved_as_of,
                created_at_utc=created_at_utc,
                feature_groups_json=json.dumps(
                    snapshot["feature_groups"],
                    sort_keys=True,
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
                feature_def_policy_id=snapshot["feature_def_policy_rev"]["policy_id"],
                feature_def_revision=snapshot["feature_def_policy_rev"]["revision"],
                feature_def_content_digest=snapshot["feature_def_policy_rev"]["content_digest"],
                run_config_digest=str(snapshot.get("run_config_digest") or ""),
                eb_offset_basis_json=json.dumps(
                    snapshot["eb_offset_basis"],
                    sort_keys=True,
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
                graph_version_json=(
                    json.dumps(snapshot["graph_version"], sort_keys=True, ensure_ascii=True, separators=(",", ":"))
                    if snapshot.get("graph_version")
                    else None
                ),
                snapshot_ref=snapshot_ref,
            )
            self.index.upsert(record)
            self.store.increment_metric(
                scenario_run_id=scenario_run_id,
                metric_name="snapshots_built",
                delta=1,
            )
            return snapshot
        except Exception:
            try:
                self.store.increment_metric(
                    scenario_run_id=scenario_run_id,
                    metric_name="snapshot_failures",
                    delta=1,
                )
            except Exception:
                pass
            raise

    def get_snapshot_index(self, snapshot_hash: str) -> dict[str, Any] | None:
        record = self.index.get(snapshot_hash)
        if not record:
            return None
        return record.as_dict()

    def load_snapshot(self, snapshot_hash: str) -> dict[str, Any] | None:
        record = self.index.get(snapshot_hash)
        if not record:
            return None
        relative = _relative_from_ref(self.object_store_root, record.snapshot_ref)
        return self.object_store.read_json(relative)


def _snapshot_relative_path(*, platform_run_id: str, scenario_run_id: str, snapshot_hash: str) -> str:
    return f"{platform_run_id}/ofp/snapshots/{scenario_run_id}/{snapshot_hash}.json"


def _relative_from_ref(root: str, artifact_ref: str) -> str:
    if artifact_ref.startswith("s3://") and root.startswith("s3://"):
        ref = urlparse(artifact_ref)
        base = urlparse(root)
        if ref.netloc != base.netloc:
            raise RuntimeError("OFP_SNAPSHOT_REF_BUCKET_MISMATCH")
        ref_path = ref.path.lstrip("/")
        base_prefix = base.path.lstrip("/")
        if base_prefix and ref_path.startswith(base_prefix + "/"):
            return ref_path[len(base_prefix) + 1 :]
        return ref_path
    artifact_path = Path(artifact_ref)
    base_path = Path(root)
    if artifact_path.is_absolute():
        try:
            return str(artifact_path.relative_to(base_path))
        except ValueError:
            return str(artifact_path)
    return str(artifact_path)


def _artifact_ref(root: str, relative_path: str) -> str:
    if root.startswith("s3://"):
        parsed = urlparse(root)
        prefix = parsed.path.lstrip("/")
        key = f"{prefix}/{relative_path}" if prefix else relative_path
        return f"s3://{parsed.netloc}/{key}"
    return str(Path(root) / relative_path)


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
