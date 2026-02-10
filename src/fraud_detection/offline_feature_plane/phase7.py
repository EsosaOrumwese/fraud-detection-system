"""OFS Phase 7 artifact publication and DatasetManifest authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from fraud_detection.scenario_runner.storage import LocalObjectStore, ObjectStore, S3ObjectStore

from .contracts import OfsBuildIntent
from .phase6 import OfsDatasetDraft
from .run_ledger import deterministic_run_key


class OfsPhase7PublishError(ValueError):
    """Raised when OFS Phase 7 publish checks fail."""

    def __init__(self, code: str, message: str) -> None:
        self.code = str(code or "").strip() or "UNKNOWN"
        self.message = str(message or "").strip() or self.code
        super().__init__(f"{self.code}:{self.message}")


@dataclass(frozen=True)
class OfsManifestPublicationReceipt:
    run_key: str
    request_id: str
    platform_run_id: str
    published_at_utc: str
    publication_mode: str
    dataset_manifest_id: str
    dataset_fingerprint: str
    manifest_ref: str
    dataset_materialization_ref: str
    draft_rows_digest: str
    row_count: int
    replay_status: str
    label_status: str | None
    training_intent: bool
    supersedes_manifest_refs: tuple[str, ...]
    backfill_reason: str | None
    supersession_ref: str | None
    evidence_refs: dict[str, str]

    def artifact_relative_path(self) -> str:
        return f"{self.platform_run_id}/ofs/publication_receipts/{self.run_key}.json"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "learning.ofs_manifest_publication_receipt.v0",
            "run_key": self.run_key,
            "request_id": self.request_id,
            "platform_run_id": self.platform_run_id,
            "published_at_utc": self.published_at_utc,
            "publication_mode": self.publication_mode,
            "dataset_manifest_id": self.dataset_manifest_id,
            "dataset_fingerprint": self.dataset_fingerprint,
            "manifest_ref": self.manifest_ref,
            "dataset_materialization_ref": self.dataset_materialization_ref,
            "draft_rows_digest": self.draft_rows_digest,
            "row_count": int(self.row_count),
            "replay_status": self.replay_status,
            "training_intent": bool(self.training_intent),
            "supersedes_manifest_refs": list(self.supersedes_manifest_refs),
            "evidence_refs": dict(self.evidence_refs),
        }
        if self.label_status:
            payload["label_status"] = self.label_status
        if self.backfill_reason:
            payload["backfill_reason"] = self.backfill_reason
        if self.supersession_ref:
            payload["supersession_ref"] = self.supersession_ref
        return _normalize_mapping(payload)


@dataclass(frozen=True)
class OfsManifestPublisherConfig:
    object_store_root: str = "runs"
    object_store_endpoint: str | None = None
    object_store_region: str | None = None
    object_store_path_style: bool | None = None


class OfsManifestPublisher:
    """Publishes immutable OFS dataset artifacts and authoritative manifests."""

    def __init__(self, *, config: OfsManifestPublisherConfig | None = None) -> None:
        self.config = config or OfsManifestPublisherConfig()
        self._store = _build_store(self.config)

    def publish(
        self,
        *,
        intent: OfsBuildIntent,
        draft: OfsDatasetDraft,
        replay_receipt: Mapping[str, Any],
        label_receipt: Mapping[str, Any] | None = None,
        draft_ref: str | None = None,
        replay_receipt_ref: str | None = None,
        label_receipt_ref: str | None = None,
        run_key: str | None = None,
        supersedes_manifest_refs: Sequence[str] = (),
        backfill_reason: str | None = None,
        dataset_manifest_id: str | None = None,
    ) -> OfsManifestPublicationReceipt:
        if draft.platform_run_id != intent.platform_run_id:
            raise OfsPhase7PublishError(
                "RUN_SCOPE_INVALID",
                f"draft platform_run_id {draft.platform_run_id!r} does not match intent {intent.platform_run_id!r}",
            )
        replay_status = _required_text(
            replay_receipt.get("status"),
            code="REPLAY_RECEIPT_INVALID",
            field_name="replay_receipt.status",
        ).upper()
        if replay_status != "COMPLETE":
            raise OfsPhase7PublishError(
                "REPLAY_INCOMPLETE",
                f"replay receipt status must be COMPLETE before publish (got {replay_status!r})",
            )

        training_intent = _is_training_intent(intent=intent)
        label_status = None
        if label_receipt is not None:
            label_status = _optional_text(label_receipt.get("status"))
        if training_intent:
            if label_receipt is None:
                raise OfsPhase7PublishError("LABEL_GATE_UNSATISFIED", "training-intent publish requires label receipt")
            if not _label_ready_for_training(label_receipt):
                raise OfsPhase7PublishError(
                    "LABEL_GATE_UNSATISFIED",
                    "training-intent publish blocked: label receipt not ready_for_training",
                )

        manifest = intent.to_dataset_manifest(dataset_manifest_id=dataset_manifest_id)
        manifest_payload = dict(manifest.payload)
        manifest_id = _required_text(
            manifest_payload.get("dataset_manifest_id"),
            code="MANIFEST_INVALID",
            field_name="manifest.dataset_manifest_id",
        )
        manifest_fingerprint = _required_text(
            manifest_payload.get("dataset_fingerprint"),
            code="MANIFEST_INVALID",
            field_name="manifest.dataset_fingerprint",
        )
        resolved_run_key = str(run_key or deterministic_run_key(intent.request_id))
        published_at_utc = _utc_now()

        staging_manifest_path = f"{intent.platform_run_id}/ofs/staging/{resolved_run_key}/dataset_manifest.json"
        self._store.write_json(staging_manifest_path, manifest_payload)

        final_manifest_path = f"{intent.platform_run_id}/ofs/manifests/{manifest_id}.json"
        publication_mode = "NEW"
        try:
            manifest_artifact = self._store.write_json_if_absent(final_manifest_path, manifest_payload)
            manifest_ref = str(manifest_artifact.path)
        except FileExistsError:
            existing_manifest = self._store.read_json(final_manifest_path)
            if _normalize_mapping(existing_manifest) != _normalize_mapping(manifest_payload):
                raise OfsPhase7PublishError(
                    "MANIFEST_IMMUTABILITY_VIOLATION",
                    f"existing manifest drift at {final_manifest_path}",
                )
            publication_mode = "ALREADY_PUBLISHED"
            manifest_ref = _artifact_ref(self.config, final_manifest_path)

        materialization_payload = {
            "schema_version": "learning.ofs_dataset_materialization.v0",
            "dataset_manifest_id": manifest_id,
            "dataset_fingerprint": manifest_fingerprint,
            "platform_run_id": intent.platform_run_id,
            "request_id": intent.request_id,
            "run_key": resolved_run_key,
            "draft": draft.as_dict(),
        }
        materialization_path = f"{intent.platform_run_id}/ofs/datasets/{manifest_id}/dataset_draft.json"
        dataset_materialization_ref = _write_json_immutable(
            store=self._store,
            config=self.config,
            relative_path=materialization_path,
            payload=materialization_payload,
            drift_code="DATASET_ARTIFACT_IMMUTABILITY_VIOLATION",
        )

        supersedes = tuple(sorted({str(item).strip() for item in supersedes_manifest_refs if str(item).strip()}))
        backfill = _optional_text(backfill_reason)
        if backfill is not None and not supersedes:
            raise OfsPhase7PublishError(
                "SUPERSESSION_LINK_INVALID",
                "backfill_reason requires non-empty supersedes_manifest_refs",
            )
        supersession_ref = None
        if supersedes:
            supersession_payload: dict[str, Any] = {
                "schema_version": "learning.ofs_dataset_supersession.v0",
                "run_key": resolved_run_key,
                "platform_run_id": intent.platform_run_id,
                "dataset_manifest_id": manifest_id,
                "supersedes_manifest_refs": list(supersedes),
                "created_at_utc": published_at_utc,
            }
            if backfill:
                supersession_payload["backfill_reason"] = backfill
            supersession_path = f"{intent.platform_run_id}/ofs/supersession/{resolved_run_key}.json"
            supersession_ref = _write_json_immutable(
                store=self._store,
                config=self.config,
                relative_path=supersession_path,
                payload=supersession_payload,
                drift_code="SUPERSESSION_LINK_IMMUTABILITY_VIOLATION",
            )

        evidence_refs: dict[str, str] = {
            "manifest_ref": manifest_ref,
            "dataset_materialization_ref": dataset_materialization_ref,
        }
        if draft_ref:
            evidence_refs["draft_ref"] = str(draft_ref).strip()
        if replay_receipt_ref:
            evidence_refs["replay_receipt_ref"] = str(replay_receipt_ref).strip()
        if label_receipt_ref:
            evidence_refs["label_receipt_ref"] = str(label_receipt_ref).strip()
        if supersession_ref:
            evidence_refs["supersession_ref"] = supersession_ref

        receipt = OfsManifestPublicationReceipt(
            run_key=resolved_run_key,
            request_id=intent.request_id,
            platform_run_id=intent.platform_run_id,
            published_at_utc=published_at_utc,
            publication_mode=publication_mode,
            dataset_manifest_id=manifest_id,
            dataset_fingerprint=manifest_fingerprint,
            manifest_ref=manifest_ref,
            dataset_materialization_ref=dataset_materialization_ref,
            draft_rows_digest=draft.rows_digest,
            row_count=len(draft.rows),
            replay_status=replay_status,
            label_status=label_status,
            training_intent=training_intent,
            supersedes_manifest_refs=supersedes,
            backfill_reason=backfill,
            supersession_ref=supersession_ref,
            evidence_refs=evidence_refs,
        )
        receipt_path = receipt.artifact_relative_path()
        try:
            self._store.write_json_if_absent(receipt_path, receipt.as_dict())
        except FileExistsError:
            existing_payload = self._store.read_json(receipt_path)
            _assert_receipt_compatibility(
                expected=receipt,
                existing=existing_payload,
            )
            return _receipt_from_payload(
                existing_payload,
                publication_mode_override="ALREADY_PUBLISHED",
            )
        return receipt


def _label_ready_for_training(label_receipt: Mapping[str, Any]) -> bool:
    gate_raw = label_receipt.get("gate")
    if isinstance(gate_raw, Mapping):
        ready = gate_raw.get("ready_for_training")
        if isinstance(ready, bool):
            return ready
    status = _optional_text(label_receipt.get("status"))
    return str(status or "").upper() == "READY_FOR_TRAINING"


def _write_json_immutable(
    *,
    store: ObjectStore,
    config: OfsManifestPublisherConfig,
    relative_path: str,
    payload: Mapping[str, Any],
    drift_code: str,
) -> str:
    normalized_payload = _normalize_mapping(payload)
    try:
        ref = store.write_json_if_absent(relative_path, normalized_payload)
        return str(ref.path)
    except FileExistsError:
        existing = store.read_json(relative_path)
        if _normalize_mapping(existing) != normalized_payload:
            raise OfsPhase7PublishError(drift_code, f"immutable artifact drift at {relative_path}")
        return _artifact_ref(config, relative_path)


def _assert_receipt_compatibility(*, expected: OfsManifestPublicationReceipt, existing: Mapping[str, Any]) -> None:
    required_checks = {
        "request_id": expected.request_id,
        "platform_run_id": expected.platform_run_id,
        "dataset_manifest_id": expected.dataset_manifest_id,
        "dataset_fingerprint": expected.dataset_fingerprint,
        "manifest_ref": expected.manifest_ref,
        "dataset_materialization_ref": expected.dataset_materialization_ref,
        "draft_rows_digest": expected.draft_rows_digest,
    }
    for field, expected_value in required_checks.items():
        existing_value = str(existing.get(field) or "")
        if existing_value != str(expected_value):
            raise OfsPhase7PublishError(
                "PUBLICATION_RECEIPT_IMMUTABILITY_VIOLATION",
                f"existing publication receipt drift at field {field}",
            )


def _receipt_from_payload(
    payload: Mapping[str, Any],
    *,
    publication_mode_override: str | None = None,
) -> OfsManifestPublicationReceipt:
    mapped = _normalize_mapping(payload)
    supersedes_raw = mapped.get("supersedes_manifest_refs")
    supersedes = tuple(str(item) for item in supersedes_raw) if isinstance(supersedes_raw, list) else tuple()
    evidence_refs_raw = mapped.get("evidence_refs")
    evidence_refs = (
        {str(key): str(value) for key, value in evidence_refs_raw.items()}
        if isinstance(evidence_refs_raw, Mapping)
        else {}
    )
    mode = publication_mode_override or _required_text(
        mapped.get("publication_mode"),
        code="PUBLICATION_RECEIPT_INVALID",
        field_name="publication_mode",
    )
    return OfsManifestPublicationReceipt(
        run_key=_required_text(mapped.get("run_key"), code="PUBLICATION_RECEIPT_INVALID", field_name="run_key"),
        request_id=_required_text(
            mapped.get("request_id"),
            code="PUBLICATION_RECEIPT_INVALID",
            field_name="request_id",
        ),
        platform_run_id=_required_text(
            mapped.get("platform_run_id"),
            code="PUBLICATION_RECEIPT_INVALID",
            field_name="platform_run_id",
        ),
        published_at_utc=_required_text(
            mapped.get("published_at_utc"),
            code="PUBLICATION_RECEIPT_INVALID",
            field_name="published_at_utc",
        ),
        publication_mode=mode,
        dataset_manifest_id=_required_text(
            mapped.get("dataset_manifest_id"),
            code="PUBLICATION_RECEIPT_INVALID",
            field_name="dataset_manifest_id",
        ),
        dataset_fingerprint=_required_text(
            mapped.get("dataset_fingerprint"),
            code="PUBLICATION_RECEIPT_INVALID",
            field_name="dataset_fingerprint",
        ),
        manifest_ref=_required_text(
            mapped.get("manifest_ref"),
            code="PUBLICATION_RECEIPT_INVALID",
            field_name="manifest_ref",
        ),
        dataset_materialization_ref=_required_text(
            mapped.get("dataset_materialization_ref"),
            code="PUBLICATION_RECEIPT_INVALID",
            field_name="dataset_materialization_ref",
        ),
        draft_rows_digest=_required_text(
            mapped.get("draft_rows_digest"),
            code="PUBLICATION_RECEIPT_INVALID",
            field_name="draft_rows_digest",
        ),
        row_count=int(mapped.get("row_count") or 0),
        replay_status=_required_text(
            mapped.get("replay_status"),
            code="PUBLICATION_RECEIPT_INVALID",
            field_name="replay_status",
        ),
        label_status=_optional_text(mapped.get("label_status")),
        training_intent=bool(mapped.get("training_intent")),
        supersedes_manifest_refs=supersedes,
        backfill_reason=_optional_text(mapped.get("backfill_reason")),
        supersession_ref=_optional_text(mapped.get("supersession_ref")),
        evidence_refs=evidence_refs,
    )


def _is_training_intent(*, intent: OfsBuildIntent) -> bool:
    return intent.intent_kind == "dataset_build" and not bool(intent.non_training_allowed)


def _build_store(config: OfsManifestPublisherConfig) -> ObjectStore:
    root = str(config.object_store_root or "").strip()
    if not root:
        raise ValueError("object_store_root is required")
    if root.startswith("s3://"):
        parsed = urlparse(root)
        return S3ObjectStore(
            parsed.netloc,
            prefix=parsed.path.lstrip("/"),
            endpoint_url=config.object_store_endpoint,
            region_name=config.object_store_region,
            path_style=config.object_store_path_style,
        )
    return LocalObjectStore(Path(root))


def _artifact_ref(config: OfsManifestPublisherConfig, relative_path: str) -> str:
    root = str(config.object_store_root or "").rstrip("/")
    if root.startswith("s3://"):
        return f"{root}/{relative_path.lstrip('/')}"
    return str(Path(root) / relative_path)


def _normalize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return _normalize_generic(dict(value))


def _normalize_generic(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_generic(val) for key, val in sorted(value.items(), key=lambda row: str(row[0]))}
    if isinstance(value, list):
        return [_normalize_generic(item) for item in value]
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _required_text(value: Any, *, code: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise OfsPhase7PublishError(code, f"{field_name} is required")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
