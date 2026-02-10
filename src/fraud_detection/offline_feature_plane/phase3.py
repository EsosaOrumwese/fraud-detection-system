"""OFS Phase 3 pin and provenance resolver surfaces."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import yaml

from fraud_detection.scenario_runner.storage import LocalObjectStore, ObjectStore, S3ObjectStore

from .contracts import FeatureDefinitionSet, OfsBuildIntent
from .run_ledger import deterministic_run_key


@dataclass(frozen=True)
class OfsPhase3ResolverError(ValueError):
    """Raised when Phase 3 resolver checks fail."""

    code: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code or "").strip() or "UNKNOWN")
        object.__setattr__(self, "message", str(self.message or "").strip() or self.code)
        ValueError.__init__(self, f"{self.code}:{self.message}")


@dataclass(frozen=True)
class ResolvedWorldLocator:
    output_id: str
    path: str
    manifest_fingerprint: str
    parameter_hash: str | None = None
    scenario_id: str | None = None
    seed: int | None = None
    content_digest: dict[str, str] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "output_id": self.output_id,
            "path": self.path,
            "manifest_fingerprint": self.manifest_fingerprint,
        }
        if self.parameter_hash:
            payload["parameter_hash"] = self.parameter_hash
        if self.scenario_id:
            payload["scenario_id"] = self.scenario_id
        if self.seed is not None:
            payload["seed"] = int(self.seed)
        if self.content_digest:
            payload["content_digest"] = dict(self.content_digest)
        return payload


@dataclass(frozen=True)
class ResolvedFeatureProfile:
    profile_ref: str
    feature_set_id: str
    feature_set_version: str
    policy_id: str
    revision: str
    profile_digest: str
    matched_group_digest: str

    @property
    def resolved_revision(self) -> str:
        return f"{self.policy_id}@{self.revision}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile_ref": self.profile_ref,
            "feature_set_id": self.feature_set_id,
            "feature_set_version": self.feature_set_version,
            "policy_id": self.policy_id,
            "revision": self.revision,
            "resolved_revision": self.resolved_revision,
            "profile_digest": self.profile_digest,
            "matched_group_digest": self.matched_group_digest,
        }


@dataclass(frozen=True)
class ResolvedParityBasisSlice:
    topic: str
    partition: int
    offset_kind: str
    start_offset: str
    end_offset: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "partition": int(self.partition),
            "offset_kind": self.offset_kind,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
        }


@dataclass(frozen=True)
class ResolvedParityAnchor:
    anchor_ref: str
    anchor_kind: str
    anchor_id: str | None
    snapshot_hash: str
    replay_basis: tuple[ResolvedParityBasisSlice, ...]
    feature_definition_set: FeatureDefinitionSet | None
    payload_digest: str

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "anchor_ref": self.anchor_ref,
            "anchor_kind": self.anchor_kind,
            "snapshot_hash": self.snapshot_hash,
            "payload_digest": self.payload_digest,
            "replay_basis": [row.as_dict() for row in self.replay_basis],
        }
        if self.anchor_id:
            payload["anchor_id"] = self.anchor_id
        if self.feature_definition_set is not None:
            payload["feature_definition_set"] = self.feature_definition_set.as_dict()
        return payload


@dataclass(frozen=True)
class ResolvedBuildPlan:
    run_key: str
    request_id: str
    intent_kind: str
    platform_run_id: str
    scenario_run_id: str
    run_facts_ref: str
    run_facts_digest: str
    pins: dict[str, Any]
    world_locators: tuple[ResolvedWorldLocator, ...]
    feature_profile: ResolvedFeatureProfile
    parity_anchor: ResolvedParityAnchor | None

    def artifact_relative_path(self) -> str:
        return f"{self.platform_run_id}/ofs/resolved_build_plan/{self.run_key}.json"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "learning.ofs_resolved_build_plan.v0",
            "run_key": self.run_key,
            "request_id": self.request_id,
            "intent_kind": self.intent_kind,
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "run_facts_ref": self.run_facts_ref,
            "run_facts_digest": self.run_facts_digest,
            "pins": dict(self.pins),
            "world_locators": [item.as_dict() for item in self.world_locators],
            "feature_profile": self.feature_profile.as_dict(),
        }
        if self.parity_anchor is not None:
            payload["parity_anchor"] = self.parity_anchor.as_dict()
        return _normalize_mapping(payload)


@dataclass(frozen=True)
class OfsBuildPlanResolverConfig:
    object_store_root: str = "runs"
    object_store_endpoint: str | None = None
    object_store_region: str | None = None
    object_store_path_style: bool | None = None
    feature_profile_ref: str = "config/platform/ofp/features_v0.yaml"
    required_output_ids: tuple[str, ...] = ()


class OfsBuildPlanResolver:
    """Resolves Phase 3 pins and emits immutable run-scoped build-plan artifacts."""

    def __init__(self, *, config: OfsBuildPlanResolverConfig | None = None) -> None:
        self.config = config or OfsBuildPlanResolverConfig()
        self._store = _build_store(self.config)

    def resolve(self, *, intent: OfsBuildIntent, run_key: str | None = None) -> ResolvedBuildPlan:
        resolved_run_key = str(run_key or deterministic_run_key(intent.request_id))
        try:
            run_facts = _read_json_ref(ref=intent.run_facts_ref, store=self._store, config=self.config)
        except OfsPhase3ResolverError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise OfsPhase3ResolverError("RUN_FACTS_UNAVAILABLE", str(exc)) from exc
        if not isinstance(run_facts, Mapping):
            raise OfsPhase3ResolverError("RUN_FACTS_UNAVAILABLE", "run_facts payload must be a mapping")

        pins = _mapping(run_facts.get("pins"), field_name="run_facts.pins", code="RUN_FACTS_UNAVAILABLE")
        run_platform_id = _text_or_empty(run_facts.get("platform_run_id")) or _text_or_empty(pins.get("platform_run_id"))
        if run_platform_id != intent.platform_run_id:
            raise OfsPhase3ResolverError(
                "RUN_SCOPE_INVALID",
                f"run_facts platform_run_id {run_platform_id!r} does not match intent {intent.platform_run_id!r}",
            )
        scenario_run_id = _text_or_empty(run_facts.get("scenario_run_id")) or _text_or_empty(pins.get("scenario_run_id"))
        if not scenario_run_id:
            raise OfsPhase3ResolverError("RUN_SCOPE_INVALID", "run_facts scenario_run_id is required")
        if intent.scenario_run_ids and scenario_run_id not in set(intent.scenario_run_ids):
            raise OfsPhase3ResolverError(
                "RUN_SCOPE_INVALID",
                f"scenario_run_id {scenario_run_id!r} not in intent scenario_run_ids",
            )

        world_locators = _resolve_world_locators(
            run_facts=run_facts,
            pins=pins,
            required_output_ids=_required_output_ids(intent=intent, config=self.config),
        )
        feature_profile = _resolve_feature_profile(intent=intent, config=self.config)
        parity_anchor = _resolve_parity_anchor(intent=intent, store=self._store, config=self.config)

        return ResolvedBuildPlan(
            run_key=resolved_run_key,
            request_id=intent.request_id,
            intent_kind=intent.intent_kind,
            platform_run_id=intent.platform_run_id,
            scenario_run_id=scenario_run_id,
            run_facts_ref=intent.run_facts_ref,
            run_facts_digest=_sha256_payload(run_facts),
            pins=_normalize_mapping(dict(pins)),
            world_locators=tuple(world_locators),
            feature_profile=feature_profile,
            parity_anchor=parity_anchor,
        )

    def emit_immutable(self, *, plan: ResolvedBuildPlan) -> str:
        relative_path = plan.artifact_relative_path()
        payload = plan.as_dict()
        try:
            ref = self._store.write_json_if_absent(relative_path, payload)
            return str(ref.path)
        except FileExistsError:
            existing = self._store.read_json(relative_path)
            if _normalize_mapping(existing) != payload:
                raise OfsPhase3ResolverError(
                    "BUILD_PLAN_IMMUTABILITY_VIOLATION",
                    f"build plan already exists with drift at {relative_path}",
                )
            return _artifact_ref(self.config, relative_path)


def _resolve_world_locators(
    *,
    run_facts: Mapping[str, Any],
    pins: Mapping[str, Any],
    required_output_ids: tuple[str, ...],
) -> list[ResolvedWorldLocator]:
    raw_locators = run_facts.get("locators")
    if not isinstance(raw_locators, list):
        raw_locators = []
    locators = [item for item in raw_locators if isinstance(item, Mapping)]
    by_output: dict[str, dict[str, Any]] = {}
    for locator in locators:
        output_id = _text_or_empty(locator.get("output_id"))
        if output_id:
            by_output[output_id] = dict(locator)

    selected: list[dict[str, Any]]
    if required_output_ids:
        missing = [output_id for output_id in required_output_ids if output_id not in by_output]
        if missing:
            raise OfsPhase3ResolverError(
                "NO_PASS_NO_READ",
                f"required world outputs missing from run_facts locators: {sorted(missing)}",
            )
        selected = [by_output[output_id] for output_id in required_output_ids]
    else:
        selected = list(by_output.values())

    resolved: list[ResolvedWorldLocator] = []
    for locator in selected:
        _assert_no_pass_no_read(run_facts=run_facts, pins=pins, locator=locator)
        output_id = _required_text(locator.get("output_id"), code="NO_PASS_NO_READ", field_name="locators[].output_id")
        path = _required_text(locator.get("path"), code="NO_PASS_NO_READ", field_name="locators[].path")
        manifest_fingerprint = _text_or_empty(locator.get("manifest_fingerprint")) or _required_text(
            pins.get("manifest_fingerprint"),
            code="NO_PASS_NO_READ",
            field_name="pins.manifest_fingerprint",
        )
        digest = locator.get("content_digest")
        digest_mapping = dict(digest) if isinstance(digest, Mapping) else None
        seed = None
        seed_raw = locator.get("seed")
        if seed_raw not in (None, ""):
            seed = _required_non_negative_int(seed_raw, code="NO_PASS_NO_READ", field_name="locators[].seed")
        resolved.append(
            ResolvedWorldLocator(
                output_id=output_id,
                path=path,
                manifest_fingerprint=manifest_fingerprint,
                parameter_hash=_text_or_none(locator.get("parameter_hash")),
                scenario_id=_text_or_none(locator.get("scenario_id")),
                seed=seed,
                content_digest=digest_mapping,
            )
        )
    return resolved


def _assert_no_pass_no_read(*, run_facts: Mapping[str, Any], pins: Mapping[str, Any], locator: Mapping[str, Any]) -> None:
    output_id = _required_text(locator.get("output_id"), code="NO_PASS_NO_READ", field_name="locators[].output_id")
    locator_path = _text_or_empty(locator.get("path"))
    manifest_fingerprint = _text_or_empty(locator.get("manifest_fingerprint")) or _text_or_empty(pins.get("manifest_fingerprint"))

    instance_receipts = run_facts.get("instance_receipts")
    has_output_receipt = False
    instance_pass = False
    if isinstance(instance_receipts, list):
        for receipt in instance_receipts:
            if not isinstance(receipt, Mapping):
                continue
            if _text_or_empty(receipt.get("output_id")) != output_id:
                continue
            has_output_receipt = True
            if _text_or_empty(receipt.get("status")) != "PASS":
                continue
            target_ref = receipt.get("target_ref")
            if not isinstance(target_ref, Mapping):
                continue
            target_path = _text_or_empty(target_ref.get("path"))
            if locator_path and target_path and target_path != locator_path:
                continue
            instance_pass = True
            break
    if has_output_receipt and instance_pass:
        return
    if has_output_receipt and not instance_pass:
        raise OfsPhase3ResolverError(
            "NO_PASS_NO_READ",
            f"instance receipt PASS missing for output_id={output_id}",
        )

    gate_receipts = run_facts.get("gate_receipts")
    if not isinstance(gate_receipts, list):
        gate_receipts = []
    gate_pass = False
    for receipt in gate_receipts:
        if not isinstance(receipt, Mapping):
            continue
        if _text_or_empty(receipt.get("status")) != "PASS":
            continue
        scope = receipt.get("scope")
        if not isinstance(scope, Mapping):
            continue
        scoped_manifest = _text_or_empty(scope.get("manifest_fingerprint"))
        if manifest_fingerprint and scoped_manifest and scoped_manifest == manifest_fingerprint:
            gate_pass = True
            break
    if not gate_pass:
        raise OfsPhase3ResolverError(
            "NO_PASS_NO_READ",
            f"gate PASS missing for output_id={output_id} manifest_fingerprint={manifest_fingerprint}",
        )


def _resolve_feature_profile(*, intent: OfsBuildIntent, config: OfsBuildPlanResolverConfig) -> ResolvedFeatureProfile:
    ref = str(config.feature_profile_ref or "").strip()
    if not ref:
        raise OfsPhase3ResolverError("FEATURE_PROFILE_UNRESOLVED", "feature_profile_ref is required")
    try:
        text = _read_text_ref(ref=ref, config=config)
        payload = yaml.safe_load(text) or {}
    except OfsPhase3ResolverError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise OfsPhase3ResolverError("FEATURE_PROFILE_UNRESOLVED", str(exc)) from exc
    if not isinstance(payload, Mapping):
        raise OfsPhase3ResolverError("FEATURE_PROFILE_UNRESOLVED", "feature profile payload must be a mapping")
    policy_id = _required_text(payload.get("policy_id"), code="FEATURE_PROFILE_UNRESOLVED", field_name="policy_id")
    revision = _required_text(payload.get("revision"), code="FEATURE_PROFILE_UNRESOLVED", field_name="revision")
    groups = payload.get("feature_groups")
    if not isinstance(groups, list):
        raise OfsPhase3ResolverError("FEATURE_PROFILE_UNRESOLVED", "feature_groups list is required")
    matched_group: dict[str, Any] | None = None
    for row in groups:
        if not isinstance(row, Mapping):
            continue
        if _text_or_empty(row.get("name")) != intent.feature_definition_set.feature_set_id:
            continue
        if _text_or_empty(row.get("version")) != intent.feature_definition_set.feature_set_version:
            continue
        matched_group = dict(row)
        break
    if matched_group is None:
        raise OfsPhase3ResolverError(
            "FEATURE_PROFILE_UNRESOLVED",
            (
                "feature set not found in shared authority: "
                f"{intent.feature_definition_set.feature_set_id}@{intent.feature_definition_set.feature_set_version}"
            ),
        )
    return ResolvedFeatureProfile(
        profile_ref=ref,
        feature_set_id=intent.feature_definition_set.feature_set_id,
        feature_set_version=intent.feature_definition_set.feature_set_version,
        policy_id=policy_id,
        revision=revision,
        profile_digest=_sha256_payload(payload),
        matched_group_digest=_sha256_payload(matched_group),
    )


def _resolve_parity_anchor(
    *,
    intent: OfsBuildIntent,
    store: ObjectStore,
    config: OfsBuildPlanResolverConfig,
) -> ResolvedParityAnchor | None:
    ref = _text_or_none(intent.parity_anchor_ref)
    if ref is None:
        return None
    try:
        payload = _read_json_ref(ref=ref, store=store, config=config)
    except OfsPhase3ResolverError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise OfsPhase3ResolverError("PARITY_ANCHOR_INVALID", str(exc)) from exc
    if not isinstance(payload, Mapping):
        raise OfsPhase3ResolverError("PARITY_ANCHOR_INVALID", "parity anchor payload must be a mapping")
    anchor_pins = payload.get("pins")
    if isinstance(anchor_pins, Mapping):
        platform_run_id = _text_or_empty(anchor_pins.get("platform_run_id"))
        if platform_run_id and platform_run_id != intent.platform_run_id:
            raise OfsPhase3ResolverError(
                "RUN_SCOPE_INVALID",
                (
                    "parity anchor pins.platform_run_id "
                    f"{platform_run_id!r} does not match intent {intent.platform_run_id!r}"
                ),
            )
    snapshot_hash = _required_text(payload.get("snapshot_hash"), code="PARITY_ANCHOR_INVALID", field_name="snapshot_hash")
    replay_basis = _resolve_parity_basis(payload)
    feature_definition_set = _resolve_anchor_feature_set(payload, intent)
    anchor_kind = "generic"
    anchor_id = None
    if _text_or_empty(payload.get("audit_id")):
        anchor_kind = "audit_record"
        anchor_id = _text_or_empty(payload.get("audit_id"))
    elif _text_or_empty(payload.get("decision_id")):
        anchor_kind = "decision_payload"
        anchor_id = _text_or_empty(payload.get("decision_id"))
    elif _text_or_empty(payload.get("snapshot_ref")):
        anchor_kind = "snapshot_ref"
        anchor_id = _text_or_empty(payload.get("snapshot_ref"))
    return ResolvedParityAnchor(
        anchor_ref=ref,
        anchor_kind=anchor_kind,
        anchor_id=anchor_id or None,
        snapshot_hash=snapshot_hash,
        replay_basis=tuple(replay_basis),
        feature_definition_set=feature_definition_set,
        payload_digest=_sha256_payload(payload),
    )


def _resolve_parity_basis(payload: Mapping[str, Any]) -> list[ResolvedParityBasisSlice]:
    eb_basis = payload.get("eb_offset_basis")
    if isinstance(eb_basis, Mapping):
        stream = _required_text(eb_basis.get("stream"), code="PARITY_ANCHOR_INVALID", field_name="eb_offset_basis.stream")
        offset_kind = _required_text(
            eb_basis.get("offset_kind"),
            code="PARITY_ANCHOR_INVALID",
            field_name="eb_offset_basis.offset_kind",
        )
        rows = eb_basis.get("offsets")
        if not isinstance(rows, list) or not rows:
            raise OfsPhase3ResolverError("PARITY_ANCHOR_INVALID", "eb_offset_basis.offsets must be a non-empty list")
        output: list[ResolvedParityBasisSlice] = []
        for row in rows:
            item = _mapping(row, field_name="eb_offset_basis.offsets[]", code="PARITY_ANCHOR_INVALID")
            partition = _required_non_negative_int(item.get("partition"), code="PARITY_ANCHOR_INVALID", field_name="partition")
            offset = _required_text(item.get("offset"), code="PARITY_ANCHOR_INVALID", field_name="offset")
            output.append(
                ResolvedParityBasisSlice(
                    topic=stream,
                    partition=partition,
                    offset_kind=offset_kind,
                    start_offset=offset,
                    end_offset=offset,
                )
            )
        return output

    basis = payload.get("replay_basis")
    if isinstance(basis, list) and basis:
        output: list[ResolvedParityBasisSlice] = []
        for row in basis:
            item = _mapping(row, field_name="replay_basis[]", code="PARITY_ANCHOR_INVALID")
            output.append(
                ResolvedParityBasisSlice(
                    topic=_required_text(item.get("topic"), code="PARITY_ANCHOR_INVALID", field_name="replay_basis[].topic"),
                    partition=_required_non_negative_int(
                        item.get("partition"),
                        code="PARITY_ANCHOR_INVALID",
                        field_name="replay_basis[].partition",
                    ),
                    offset_kind=_required_text(
                        item.get("offset_kind"),
                        code="PARITY_ANCHOR_INVALID",
                        field_name="replay_basis[].offset_kind",
                    ),
                    start_offset=_required_text(
                        item.get("start_offset"),
                        code="PARITY_ANCHOR_INVALID",
                        field_name="replay_basis[].start_offset",
                    ),
                    end_offset=_required_text(
                        item.get("end_offset"),
                        code="PARITY_ANCHOR_INVALID",
                        field_name="replay_basis[].end_offset",
                    ),
                )
            )
        return output

    raise OfsPhase3ResolverError("PARITY_ANCHOR_INVALID", "parity anchor must include eb_offset_basis or replay_basis")


def _resolve_anchor_feature_set(payload: Mapping[str, Any], intent: OfsBuildIntent) -> FeatureDefinitionSet | None:
    explicit = payload.get("feature_definition_set")
    if isinstance(explicit, Mapping):
        return FeatureDefinitionSet.from_payload(explicit)
    groups = payload.get("feature_groups")
    if isinstance(groups, list):
        for row in groups:
            if not isinstance(row, Mapping):
                continue
            name = _text_or_empty(row.get("name"))
            version = _text_or_empty(row.get("version"))
            if name and version:
                return FeatureDefinitionSet(feature_set_id=name, feature_set_version=version)
    if isinstance(payload.get("feature_def_policy_rev"), Mapping):
        return intent.feature_definition_set
    return None


def _required_output_ids(intent: OfsBuildIntent, config: OfsBuildPlanResolverConfig) -> tuple[str, ...]:
    required: list[str] = []
    join_scope_required = intent.join_scope.get("required_output_ids")
    if isinstance(join_scope_required, list):
        required.extend([_text_or_empty(item) for item in join_scope_required])
    required.extend([_text_or_empty(item) for item in config.required_output_ids])
    deduped = sorted({item for item in required if item})
    return tuple(deduped)


def _build_store(config: OfsBuildPlanResolverConfig) -> ObjectStore:
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


def _artifact_ref(config: OfsBuildPlanResolverConfig, relative_path: str) -> str:
    root = str(config.object_store_root or "").rstrip("/")
    if root.startswith("s3://"):
        return f"{root}/{relative_path.lstrip('/')}"
    return str(Path(root) / relative_path)


def _read_json_ref(*, ref: str, store: ObjectStore, config: OfsBuildPlanResolverConfig) -> dict[str, Any]:
    value = str(ref or "").strip()
    if not value:
        raise OfsPhase3ResolverError("RUN_FACTS_UNAVAILABLE", "artifact ref is required")
    if value.startswith("s3://"):
        parsed = urlparse(value)
        s3_store = S3ObjectStore(
            parsed.netloc,
            prefix="",
            endpoint_url=config.object_store_endpoint,
            region_name=config.object_store_region,
            path_style=config.object_store_path_style,
        )
        return s3_store.read_json(parsed.path.lstrip("/"))
    path = Path(value)
    if path.is_absolute():
        return json.loads(path.read_text(encoding="utf-8"))
    return store.read_json(value)


def _read_text_ref(*, ref: str, config: OfsBuildPlanResolverConfig) -> str:
    value = str(ref or "").strip()
    if not value:
        raise OfsPhase3ResolverError("FEATURE_PROFILE_UNRESOLVED", "feature profile ref is required")
    if value.startswith("s3://"):
        parsed = urlparse(value)
        s3_store = S3ObjectStore(
            parsed.netloc,
            prefix="",
            endpoint_url=config.object_store_endpoint,
            region_name=config.object_store_region,
            path_style=config.object_store_path_style,
        )
        return s3_store.read_text(parsed.path.lstrip("/"))
    path = Path(value)
    if path.is_absolute() or path.exists():
        return path.read_text(encoding="utf-8")
    raise OfsPhase3ResolverError("FEATURE_PROFILE_UNRESOLVED", f"feature profile ref not found: {value}")


def _sha256_payload(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_normalize_mapping(payload), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()


def _text_or_none(value: Any) -> str | None:
    text = _text_or_empty(value)
    return text or None


def _required_text(value: Any, *, code: str, field_name: str) -> str:
    text = _text_or_empty(value)
    if not text:
        raise OfsPhase3ResolverError(code, f"{field_name} is required")
    return text


def _required_non_negative_int(value: Any, *, code: str, field_name: str) -> int:
    try:
        parsed = int(value)
    except Exception as exc:  # noqa: BLE001
        raise OfsPhase3ResolverError(code, f"{field_name} must be an integer") from exc
    if parsed < 0:
        raise OfsPhase3ResolverError(code, f"{field_name} must be >= 0")
    return parsed


def _mapping(value: Any, *, field_name: str, code: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OfsPhase3ResolverError(code, f"{field_name} must be a mapping")
    return dict(value)
