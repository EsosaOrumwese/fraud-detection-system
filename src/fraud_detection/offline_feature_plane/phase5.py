"""OFS Phase 5 label as-of resolver and coverage gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from fraud_detection.label_store import (
    LABEL_TYPES,
    LS_AS_OF_RESOLVED,
    LabelAsOfSlice,
    LabelStoreSliceBuilder,
    LabelStoreWriterBoundary,
)
from fraud_detection.scenario_runner.storage import LocalObjectStore, ObjectStore, S3ObjectStore

from .contracts import OfsBuildIntent
from .run_ledger import deterministic_run_key


@dataclass(frozen=True)
class OfsPhase5LabelError(ValueError):
    """Raised when OFS Phase 5 label checks fail."""

    code: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code or "").strip() or "UNKNOWN")
        object.__setattr__(self, "message", str(self.message or "").strip() or self.code)
        ValueError.__init__(self, f"{self.code}:{self.message}")


@dataclass(frozen=True)
class OfsLabelTarget:
    platform_run_id: str
    event_id: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "OfsLabelTarget":
        mapped = _mapping(payload, field_name="target_subjects[]", code="LABEL_SCOPE_INVALID")
        return cls(
            platform_run_id=_required_text(
                mapped.get("platform_run_id"),
                code="LABEL_SCOPE_INVALID",
                field_name="target_subjects[].platform_run_id",
            ),
            event_id=_required_text(
                mapped.get("event_id"),
                code="LABEL_SCOPE_INVALID",
                field_name="target_subjects[].event_id",
            ),
        )

    def as_dict(self) -> dict[str, str]:
        return {"platform_run_id": self.platform_run_id, "event_id": self.event_id}


@dataclass(frozen=True)
class OfsLabelCoveragePolicy:
    label_types: tuple[str, ...]
    min_coverage_by_label_type: dict[str, float]
    max_conflict_ratio: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "label_types": list(self.label_types),
            "min_coverage_by_label_type": {k: float(v) for k, v in sorted(self.min_coverage_by_label_type.items())},
            "max_conflict_ratio": float(self.max_conflict_ratio),
        }


@dataclass(frozen=True)
class OfsLabelMaturitySignal:
    label_type: str
    resolved_total: int
    mature_resolved_total: int
    immature_resolved_total: int
    mature_resolved_ratio: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "label_type": self.label_type,
            "resolved_total": int(self.resolved_total),
            "mature_resolved_total": int(self.mature_resolved_total),
            "immature_resolved_total": int(self.immature_resolved_total),
            "mature_resolved_ratio": float(self.mature_resolved_ratio),
        }


@dataclass(frozen=True)
class OfsLabelMaturityDiagnostics:
    maturity_days: int | None
    maturity_cutoff_utc: str | None
    resolved_total: int
    mature_resolved_total: int
    immature_resolved_total: int
    mature_resolved_ratio: float
    per_label_type: tuple[OfsLabelMaturitySignal, ...]

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "resolved_total": int(self.resolved_total),
            "mature_resolved_total": int(self.mature_resolved_total),
            "immature_resolved_total": int(self.immature_resolved_total),
            "mature_resolved_ratio": float(self.mature_resolved_ratio),
            "per_label_type": [item.as_dict() for item in self.per_label_type],
        }
        if self.maturity_days is not None:
            payload["maturity_days"] = int(self.maturity_days)
        if self.maturity_cutoff_utc is not None:
            payload["maturity_cutoff_utc"] = self.maturity_cutoff_utc
        return payload


@dataclass(frozen=True)
class OfsLabelResolutionReceipt:
    run_key: str
    request_id: str
    platform_run_id: str
    status: str
    generated_at_utc: str
    label_asof_utc: str
    label_resolution_rule: str
    non_training_allowed: bool
    target_total: int
    row_total: int
    row_digest: str
    selected_value_counts: dict[str, int]
    coverage_policy: OfsLabelCoveragePolicy
    coverage_signals: tuple[dict[str, Any], ...]
    gate: dict[str, Any]
    maturity_diagnostics: OfsLabelMaturityDiagnostics
    label_slice_digest: str
    label_basis_digest: str
    label_policy_rev: dict[str, str]

    def artifact_relative_path(self) -> str:
        return f"{self.platform_run_id}/ofs/label_resolution/{self.run_key}.json"

    def as_dict(self) -> dict[str, Any]:
        return _normalize_mapping(
            {
                "schema_version": "learning.ofs_label_resolution_receipt.v0",
                "run_key": self.run_key,
                "request_id": self.request_id,
                "platform_run_id": self.platform_run_id,
                "status": self.status,
                "generated_at_utc": self.generated_at_utc,
                "label_basis": {
                    "label_asof_utc": self.label_asof_utc,
                    "resolution_rule": self.label_resolution_rule,
                },
                "non_training_allowed": bool(self.non_training_allowed),
                "target_total": int(self.target_total),
                "row_total": int(self.row_total),
                "row_digest": self.row_digest,
                "selected_value_counts": {k: int(v) for k, v in sorted(self.selected_value_counts.items())},
                "coverage_policy": self.coverage_policy.as_dict(),
                "coverage_signals": [dict(item) for item in self.coverage_signals],
                "gate": dict(self.gate),
                "maturity_diagnostics": self.maturity_diagnostics.as_dict(),
                "label_slice_digest": self.label_slice_digest,
                "label_basis_digest": self.label_basis_digest,
                "label_policy_rev": dict(self.label_policy_rev),
            }
        )


@dataclass(frozen=True)
class OfsLabelResolverConfig:
    label_store_locator: str
    object_store_root: str = "runs"
    object_store_endpoint: str | None = None
    object_store_region: str | None = None
    object_store_path_style: bool | None = None
    default_label_types: tuple[str, ...] = ()
    default_min_coverage_by_label_type: dict[str, float] | None = None
    default_max_conflict_ratio: float = 0.0


class OfsLabelAsOfResolver:
    """Resolves leakage-safe as-of labels and enforces OFS training coverage policy."""

    def __init__(self, *, config: OfsLabelResolverConfig) -> None:
        self.config = config
        self._store = _build_store(config)
        self._label_writer = LabelStoreWriterBoundary(config.label_store_locator)
        self._label_slices = LabelStoreSliceBuilder(writer_boundary=self._label_writer)

    def resolve(
        self,
        *,
        intent: OfsBuildIntent,
        target_subjects: Sequence[Mapping[str, Any] | OfsLabelTarget],
        run_key: str | None = None,
    ) -> OfsLabelResolutionReceipt:
        targets = _normalize_targets(target_subjects=target_subjects, platform_run_id=intent.platform_run_id)
        policy = _resolve_coverage_policy(intent=intent, config=self.config)
        scenario_run_id = intent.scenario_run_ids[0] if len(intent.scenario_run_ids) == 1 else None
        try:
            slice_payload = self._label_slices.build_resolved_as_of_slice(
                target_subjects=[target.as_dict() for target in targets],
                observed_as_of=intent.label_basis.label_asof_utc,
                label_types=policy.label_types,
                scenario_run_id=scenario_run_id,
            )
            gate_signals = self._label_slices.evaluate_dataset_gate(
                slice_payload=slice_payload,
                min_coverage_by_label_type=policy.min_coverage_by_label_type,
                max_conflict_ratio=policy.max_conflict_ratio,
            )
        except OfsPhase5LabelError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise OfsPhase5LabelError("LABEL_SCOPE_INVALID", str(exc)) from exc

        maturity = _build_maturity_diagnostics(
            slice_payload=slice_payload,
            as_of_utc=intent.label_basis.label_asof_utc,
            maturity_days=intent.label_basis.maturity_days,
            label_writer=self._label_writer,
        )
        training_intent = _is_training_intent(intent=intent)
        if training_intent and not bool(gate_signals.ready_for_training):
            reasons = [str(item) for item in gate_signals.reasons]
            joined = ",".join(sorted(reasons)) if reasons else "UNKNOWN_COVERAGE_POLICY_VIOLATION"
            raise OfsPhase5LabelError("COVERAGE_POLICY_VIOLATION", joined)

        resolved_run_key = str(run_key or deterministic_run_key(intent.request_id))
        status = "READY_FOR_TRAINING" if bool(gate_signals.ready_for_training) else "NOT_READY_FOR_TRAINING"
        row_payload = [row.as_dict() for row in slice_payload.rows]
        return OfsLabelResolutionReceipt(
            run_key=resolved_run_key,
            request_id=intent.request_id,
            platform_run_id=intent.platform_run_id,
            status=status,
            generated_at_utc=_utc_now(),
            label_asof_utc=_normalize_utc_ts(intent.label_basis.label_asof_utc, field_name="label_basis.label_asof_utc"),
            label_resolution_rule=intent.label_basis.resolution_rule,
            non_training_allowed=bool(intent.non_training_allowed),
            target_total=len(targets),
            row_total=len(row_payload),
            row_digest=_sha256_payload({"rows": row_payload}),
            selected_value_counts=_selected_value_counts(slice_payload=slice_payload),
            coverage_policy=policy,
            coverage_signals=tuple(item.as_dict() for item in slice_payload.coverage_signals),
            gate=gate_signals.as_dict(),
            maturity_diagnostics=maturity,
            label_slice_digest=slice_payload.slice_digest,
            label_basis_digest=slice_payload.basis_digest,
            label_policy_rev=dict(slice_payload.ls_policy_rev),
        )

    def emit_immutable(self, *, receipt: OfsLabelResolutionReceipt) -> str:
        relative_path = receipt.artifact_relative_path()
        payload = receipt.as_dict()
        try:
            ref = self._store.write_json_if_absent(relative_path, payload)
            return str(ref.path)
        except FileExistsError:
            existing = self._store.read_json(relative_path)
            if _normalize_mapping(existing) != payload:
                raise OfsPhase5LabelError(
                    "LABEL_RESOLUTION_IMMUTABILITY_VIOLATION",
                    f"label resolution drift detected at {relative_path}",
                )
            return _artifact_ref(self.config, relative_path)


def _normalize_targets(
    *,
    target_subjects: Sequence[Mapping[str, Any] | OfsLabelTarget],
    platform_run_id: str,
) -> tuple[OfsLabelTarget, ...]:
    if not target_subjects:
        raise OfsPhase5LabelError("LABEL_SCOPE_EMPTY", "target_subjects must be non-empty")
    deduped: dict[tuple[str, str], OfsLabelTarget] = {}
    for item in target_subjects:
        target = item if isinstance(item, OfsLabelTarget) else OfsLabelTarget.from_payload(item)
        if target.platform_run_id != platform_run_id:
            raise OfsPhase5LabelError(
                "RUN_SCOPE_INVALID",
                (
                    "target_subjects platform_run_id mismatch: "
                    f"{target.platform_run_id!r} != {platform_run_id!r}"
                ),
            )
        deduped[(target.platform_run_id, target.event_id)] = target
    rows = sorted(deduped.values(), key=lambda item: (item.platform_run_id, item.event_id))
    if not rows:
        raise OfsPhase5LabelError("LABEL_SCOPE_EMPTY", "target_subjects resolved empty after normalization")
    return tuple(rows)


def _resolve_coverage_policy(*, intent: OfsBuildIntent, config: OfsLabelResolverConfig) -> OfsLabelCoveragePolicy:
    defaults = dict(config.default_min_coverage_by_label_type or {})
    max_conflict_ratio = float(config.default_max_conflict_ratio)
    intent_policy_raw = intent.filters.get("label_coverage_policy")
    intent_policy = _mapping_or_none(intent_policy_raw, field_name="filters.label_coverage_policy", code="LABEL_POLICY_INVALID")
    if intent_policy:
        min_map_raw = intent_policy.get("min_coverage_by_label_type")
        if min_map_raw is not None:
            min_map = _mapping(
                min_map_raw,
                field_name="filters.label_coverage_policy.min_coverage_by_label_type",
                code="LABEL_POLICY_INVALID",
            )
            defaults = {str(key): _ratio(min_map[key], "LABEL_POLICY_INVALID", f"min_coverage_by_label_type.{key}") for key in min_map}
        if "max_conflict_ratio" in intent_policy:
            max_conflict_ratio = _ratio(
                intent_policy.get("max_conflict_ratio"),
                "LABEL_POLICY_INVALID",
                "filters.label_coverage_policy.max_conflict_ratio",
            )

    label_types = _list_text(intent.filters.get("label_types"))
    if not label_types:
        label_types = _list_text(intent.join_scope.get("label_types"))
    if not label_types:
        label_types = sorted(defaults)
    if not label_types:
        label_types = [str(item) for item in config.default_label_types]
    label_types = sorted({item for item in label_types if str(item).strip()})
    if not label_types:
        raise OfsPhase5LabelError(
            "LABEL_TYPE_SCOPE_UNRESOLVED",
            "label_types must be declared via intent.filters, join_scope, policy thresholds, or resolver defaults",
        )
    for label_type in label_types:
        if label_type not in LABEL_TYPES:
            raise OfsPhase5LabelError(
                "LABEL_POLICY_INVALID",
                f"unsupported label_type in coverage policy: {label_type!r}",
            )

    min_coverage_by_label_type: dict[str, float] = {}
    for label_type in label_types:
        value = defaults.get(label_type, 1.0)
        min_coverage_by_label_type[label_type] = _ratio(value, "LABEL_POLICY_INVALID", f"min_coverage_by_label_type.{label_type}")
    return OfsLabelCoveragePolicy(
        label_types=tuple(label_types),
        min_coverage_by_label_type=min_coverage_by_label_type,
        max_conflict_ratio=_ratio(max_conflict_ratio, "LABEL_POLICY_INVALID", "max_conflict_ratio"),
    )


def _build_maturity_diagnostics(
    *,
    slice_payload: LabelAsOfSlice,
    as_of_utc: str,
    maturity_days: int | None,
    label_writer: LabelStoreWriterBoundary,
) -> OfsLabelMaturityDiagnostics:
    as_of = _parse_utc(as_of_utc, field_name="label_basis.label_asof_utc")
    maturity_cutoff = as_of - timedelta(days=int(maturity_days)) if maturity_days is not None else None
    lookup_cache: dict[tuple[str, str, str], dict[str, datetime]] = {}
    totals_by_label: dict[str, dict[str, int]] = {}
    resolved_total = 0
    mature_total = 0
    for row in slice_payload.rows:
        lane = totals_by_label.setdefault(
            row.label_type,
            {"resolved_total": 0, "mature_resolved_total": 0},
        )
        if row.status != LS_AS_OF_RESOLVED:
            continue
        selected_id = _required_text(
            row.selected_assertion_id,
            code="LABEL_TIMELINE_INCONSISTENT",
            field_name="rows[].selected_assertion_id",
        )
        selected_observed = _selected_observed_time(
            cache=lookup_cache,
            label_writer=label_writer,
            platform_run_id=row.platform_run_id,
            event_id=row.event_id,
            label_type=row.label_type,
            selected_assertion_id=selected_id,
        )
        if selected_observed > as_of:
            raise OfsPhase5LabelError(
                "LEAKAGE_POLICY_VIOLATION",
                (
                    "selected assertion observed_time exceeds label_asof_utc: "
                    f"{selected_observed.isoformat()} > {as_of.isoformat()}"
                ),
            )
        lane["resolved_total"] += 1
        resolved_total += 1
        if maturity_cutoff is None or selected_observed <= maturity_cutoff:
            lane["mature_resolved_total"] += 1
            mature_total += 1

    signals: list[OfsLabelMaturitySignal] = []
    for label_type in sorted(totals_by_label):
        lane = totals_by_label[label_type]
        total = int(lane["resolved_total"])
        mature = int(lane["mature_resolved_total"])
        immature = max(total - mature, 0)
        ratio = 1.0 if total <= 0 else round(mature / float(total), 6)
        signals.append(
            OfsLabelMaturitySignal(
                label_type=label_type,
                resolved_total=total,
                mature_resolved_total=mature,
                immature_resolved_total=immature,
                mature_resolved_ratio=ratio,
            )
        )
    overall_ratio = 1.0 if resolved_total <= 0 else round(mature_total / float(resolved_total), 6)
    return OfsLabelMaturityDiagnostics(
        maturity_days=maturity_days,
        maturity_cutoff_utc=_format_utc(maturity_cutoff) if maturity_cutoff is not None else None,
        resolved_total=int(resolved_total),
        mature_resolved_total=int(mature_total),
        immature_resolved_total=int(max(resolved_total - mature_total, 0)),
        mature_resolved_ratio=float(overall_ratio),
        per_label_type=tuple(signals),
    )


def _selected_observed_time(
    *,
    cache: dict[tuple[str, str, str], dict[str, datetime]],
    label_writer: LabelStoreWriterBoundary,
    platform_run_id: str,
    event_id: str,
    label_type: str,
    selected_assertion_id: str,
) -> datetime:
    cache_key = (platform_run_id, event_id, label_type)
    by_assertion = cache.get(cache_key)
    if by_assertion is None:
        by_assertion = {}
        timeline = label_writer.list_timeline(
            platform_run_id=platform_run_id,
            event_id=event_id,
            label_type=label_type,
        )
        for row in timeline:
            by_assertion[row.label_assertion_id] = _parse_utc(
                row.observed_time,
                field_name="label_timeline.observed_time",
            )
        cache[cache_key] = by_assertion
    observed = by_assertion.get(selected_assertion_id)
    if observed is None:
        raise OfsPhase5LabelError(
            "LABEL_TIMELINE_INCONSISTENT",
            f"selected_assertion_id {selected_assertion_id!r} missing from timeline",
        )
    return observed


def _selected_value_counts(*, slice_payload: LabelAsOfSlice) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in slice_payload.rows:
        if row.status != LS_AS_OF_RESOLVED or row.selected_label_value in (None, ""):
            continue
        value = str(row.selected_label_value)
        counts[value] = int(counts.get(value, 0)) + 1
    return counts


def _is_training_intent(*, intent: OfsBuildIntent) -> bool:
    return intent.intent_kind == "dataset_build" and not bool(intent.non_training_allowed)


def _build_store(config: OfsLabelResolverConfig) -> ObjectStore:
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


def _artifact_ref(config: OfsLabelResolverConfig, relative_path: str) -> str:
    root = str(config.object_store_root or "").rstrip("/")
    if root.startswith("s3://"):
        return f"{root}/{relative_path.lstrip('/')}"
    return str(Path(root) / relative_path)


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


def _mapping(value: Any, *, field_name: str, code: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OfsPhase5LabelError(code, f"{field_name} must be a mapping")
    return dict(value)


def _mapping_or_none(value: Any, *, field_name: str, code: str) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    return _mapping(value, field_name=field_name, code=code)


def _list_text(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            output.append(text)
    return output


def _required_text(value: Any, *, code: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise OfsPhase5LabelError(code, f"{field_name} is required")
    return text


def _ratio(value: Any, code: str, field_name: str) -> float:
    try:
        parsed = float(value)
    except Exception as exc:  # noqa: BLE001
        raise OfsPhase5LabelError(code, f"{field_name} must be numeric") from exc
    if parsed < 0.0 or parsed > 1.0:
        raise OfsPhase5LabelError(code, f"{field_name} must be between 0 and 1")
    return float(parsed)


def _parse_utc(value: str, *, field_name: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise OfsPhase5LabelError("LABEL_SCOPE_INVALID", f"{field_name} is required")
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(probe)
    except ValueError as exc:
        raise OfsPhase5LabelError("LABEL_SCOPE_INVALID", f"{field_name} must be ISO-8601: {text}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_utc_ts(value: str, *, field_name: str) -> str:
    return _format_utc(_parse_utc(value, field_name=field_name))


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
