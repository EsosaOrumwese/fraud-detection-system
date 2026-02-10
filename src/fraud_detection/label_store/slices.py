"""Manifest-grade bulk as-of slice surfaces for OFS/MF consumers (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from fraud_detection.platform_runtime import RUNS_ROOT

from .contracts import LABEL_TYPES
from .writer_boundary import (
    LS_AS_OF_CONFLICT,
    LS_AS_OF_NOT_FOUND,
    LS_AS_OF_RESOLVED,
    LabelStoreWriterBoundary,
)


LS_SLICE_POLICY_ID = "label_store.slice_policy.v0"
LS_SLICE_POLICY_REVISION = "r1"
LS_SLICE_POLICY_DIGEST_RECIPE_V1 = "ls.slice.policy_digest.v1"
LS_SLICE_BASIS_DIGEST_RECIPE_V1 = "ls.slice.basis_digest.v1"
LS_SLICE_PAYLOAD_DIGEST_RECIPE_V1 = "ls.slice.payload_digest.v1"


class LabelStoreSliceError(ValueError):
    """Raised when bulk as-of slice requests are invalid."""


@dataclass(frozen=True)
class LabelSliceTarget:
    platform_run_id: str
    event_id: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "LabelSliceTarget":
        if not isinstance(payload, Mapping):
            raise LabelStoreSliceError("target must be a mapping")
        platform_run_id = _required_text(payload.get("platform_run_id"), "target.platform_run_id")
        event_id = _required_text(payload.get("event_id"), "target.event_id")
        return cls(platform_run_id=platform_run_id, event_id=event_id)

    def as_dict(self) -> dict[str, str]:
        return {
            "platform_run_id": self.platform_run_id,
            "event_id": self.event_id,
        }


@dataclass(frozen=True)
class LabelAsOfSliceRow:
    platform_run_id: str
    event_id: str
    label_type: str
    status: str
    selected_label_value: str | None
    selected_assertion_id: str | None
    candidate_assertion_ids: tuple[str, ...]
    candidate_label_values: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform_run_id": self.platform_run_id,
            "event_id": self.event_id,
            "label_type": self.label_type,
            "status": self.status,
            "selected_label_value": self.selected_label_value,
            "selected_assertion_id": self.selected_assertion_id,
            "candidate_assertion_ids": list(self.candidate_assertion_ids),
            "candidate_label_values": list(self.candidate_label_values),
        }


@dataclass(frozen=True)
class LabelCoverageSignal:
    label_type: str
    target_total: int
    resolved_total: int
    conflict_total: int
    not_found_total: int
    coverage_ratio: float
    conflict_ratio: float
    maturity_ratio: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "label_type": self.label_type,
            "target_total": self.target_total,
            "resolved_total": self.resolved_total,
            "conflict_total": self.conflict_total,
            "not_found_total": self.not_found_total,
            "coverage_ratio": self.coverage_ratio,
            "conflict_ratio": self.conflict_ratio,
            "maturity_ratio": self.maturity_ratio,
        }


@dataclass(frozen=True)
class LabelDatasetGateSignals:
    ready_for_training: bool
    evaluated_at_utc: str
    min_coverage_by_label_type: dict[str, float]
    max_conflict_ratio: float
    reasons: tuple[str, ...]
    per_label_type: tuple[LabelCoverageSignal, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready_for_training": self.ready_for_training,
            "evaluated_at_utc": self.evaluated_at_utc,
            "min_coverage_by_label_type": dict(self.min_coverage_by_label_type),
            "max_conflict_ratio": self.max_conflict_ratio,
            "reasons": list(self.reasons),
            "per_label_type": [item.as_dict() for item in self.per_label_type],
        }


@dataclass(frozen=True)
class LabelAsOfSlice:
    platform_run_id: str
    scenario_run_id: str | None
    observed_as_of: str
    effective_at: str
    ls_policy_rev: dict[str, str]
    label_types: tuple[str, ...]
    target_set_fingerprint: str
    basis_digest: str
    slice_digest: str
    rows: tuple[LabelAsOfSliceRow, ...]
    coverage_signals: tuple[LabelCoverageSignal, ...]

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "basis": {
                "observed_as_of": self.observed_as_of,
                "effective_at": self.effective_at,
                "ls_policy_rev": dict(self.ls_policy_rev),
                "label_types": list(self.label_types),
                "target_set_fingerprint": self.target_set_fingerprint,
                "basis_digest": self.basis_digest,
            },
            "row_count": self.row_count,
            "slice_digest": self.slice_digest,
            "rows": [row.as_dict() for row in self.rows],
            "coverage_signals": [item.as_dict() for item in self.coverage_signals],
        }


@dataclass(frozen=True)
class LabelSliceArtifactRef:
    slice_ref: str
    local_path: str
    slice_digest: str
    basis_digest: str
    row_count: int
    written_new: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "slice_ref": self.slice_ref,
            "local_path": self.local_path,
            "slice_digest": self.slice_digest,
            "basis_digest": self.basis_digest,
            "row_count": self.row_count,
            "written_new": self.written_new,
        }


@dataclass
class LabelStoreSliceBuilder:
    writer_boundary: LabelStoreWriterBoundary
    max_targets: int = 50_000
    policy_id: str = LS_SLICE_POLICY_ID
    policy_revision: str = LS_SLICE_POLICY_REVISION

    def __post_init__(self) -> None:
        if self.max_targets <= 0:
            raise LabelStoreSliceError("max_targets must be > 0")
        self.policy_id = _required_text(self.policy_id, "policy_id")
        self.policy_revision = _required_text(self.policy_revision, "policy_revision")

    def build_resolved_as_of_slice(
        self,
        *,
        target_subjects: Sequence[Mapping[str, Any] | LabelSliceTarget],
        observed_as_of: str,
        effective_at: str | None = None,
        label_types: Sequence[str] | None = None,
        scenario_run_id: str | None = None,
    ) -> LabelAsOfSlice:
        observed = _normalize_ts(observed_as_of, "observed_as_of")
        effective = _normalize_ts(effective_at or observed, "effective_at")
        if effective > observed:
            raise LabelStoreSliceError("effective_at must be <= observed_as_of")

        targets = _normalize_targets(target_subjects=target_subjects, max_targets=self.max_targets)
        platform_run_ids = {target.platform_run_id for target in targets}
        if len(platform_run_ids) != 1:
            raise LabelStoreSliceError("target_subjects must share one platform_run_id")
        platform_run_id = next(iter(platform_run_ids))
        normalized_label_types = _normalize_label_types(label_types)
        normalized_scenario_run_id = _optional_text(scenario_run_id)

        policy_rev = _policy_revision(
            policy_id=self.policy_id,
            revision=self.policy_revision,
            label_types=normalized_label_types,
        )
        target_set_fingerprint = _hash_with_recipe(
            LS_SLICE_BASIS_DIGEST_RECIPE_V1,
            [target.as_dict() for target in targets],
        )
        basis_digest = _hash_with_recipe(
            LS_SLICE_BASIS_DIGEST_RECIPE_V1,
            {
                "platform_run_id": platform_run_id,
                "scenario_run_id": normalized_scenario_run_id or "",
                "observed_as_of": observed,
                "effective_at": effective,
                "label_types": list(normalized_label_types),
                "target_set_fingerprint": target_set_fingerprint,
                "ls_policy_rev": policy_rev,
            },
        )

        rows: list[LabelAsOfSliceRow] = []
        for target in targets:
            for label_type in normalized_label_types:
                resolved = self.writer_boundary.label_as_of(
                    platform_run_id=target.platform_run_id,
                    event_id=target.event_id,
                    label_type=label_type,
                    as_of_observed_time=observed,
                )
                rows.append(
                    LabelAsOfSliceRow(
                        platform_run_id=target.platform_run_id,
                        event_id=target.event_id,
                        label_type=label_type,
                        status=resolved.status,
                        selected_label_value=resolved.selected_label_value,
                        selected_assertion_id=resolved.selected_assertion_id,
                        candidate_assertion_ids=tuple(resolved.candidate_assertion_ids),
                        candidate_label_values=tuple(resolved.candidate_label_values),
                    )
                )

        rows.sort(key=lambda row: (row.platform_run_id, row.event_id, row.label_type))
        coverage = _coverage_signals(rows=rows, label_types=normalized_label_types, target_total=len(targets))
        slice_digest = _slice_digest(
            basis_digest=basis_digest,
            rows=rows,
        )
        return LabelAsOfSlice(
            platform_run_id=platform_run_id,
            scenario_run_id=normalized_scenario_run_id,
            observed_as_of=observed,
            effective_at=effective,
            ls_policy_rev=policy_rev,
            label_types=normalized_label_types,
            target_set_fingerprint=target_set_fingerprint,
            basis_digest=basis_digest,
            slice_digest=slice_digest,
            rows=tuple(rows),
            coverage_signals=coverage,
        )

    def evaluate_dataset_gate(
        self,
        *,
        slice_payload: LabelAsOfSlice,
        min_coverage_by_label_type: Mapping[str, float] | None = None,
        max_conflict_ratio: float = 0.0,
    ) -> LabelDatasetGateSignals:
        if max_conflict_ratio < 0.0 or max_conflict_ratio > 1.0:
            raise LabelStoreSliceError("max_conflict_ratio must be between 0 and 1")
        thresholds = {
            signal.label_type: 1.0
            for signal in slice_payload.coverage_signals
        }
        if min_coverage_by_label_type:
            for label_type, value in min_coverage_by_label_type.items():
                normalized_type = _required_text(label_type, "min_coverage_by_label_type.label_type")
                if normalized_type not in slice_payload.label_types:
                    raise LabelStoreSliceError(
                        f"unknown label_type threshold: {normalized_type!r}; expected one of {sorted(slice_payload.label_types)!r}"
                    )
                ratio = float(value)
                if ratio < 0.0 or ratio > 1.0:
                    raise LabelStoreSliceError("coverage thresholds must be between 0 and 1")
                thresholds[normalized_type] = ratio

        reasons: list[str] = []
        for signal in slice_payload.coverage_signals:
            minimum = float(thresholds.get(signal.label_type, 1.0))
            if signal.coverage_ratio < minimum:
                reasons.append(
                    f"COVERAGE_BELOW_MIN:{signal.label_type}:{signal.coverage_ratio:.6f}<{minimum:.6f}"
                )
            if signal.conflict_ratio > max_conflict_ratio:
                reasons.append(
                    f"CONFLICT_RATIO_ABOVE_MAX:{signal.label_type}:{signal.conflict_ratio:.6f}>{max_conflict_ratio:.6f}"
                )

        reasons.sort()
        return LabelDatasetGateSignals(
            ready_for_training=len(reasons) == 0,
            evaluated_at_utc=_utc_now(),
            min_coverage_by_label_type={k: float(v) for k, v in sorted(thresholds.items())},
            max_conflict_ratio=float(max_conflict_ratio),
            reasons=tuple(reasons),
            per_label_type=slice_payload.coverage_signals,
        )

    def export_slice_artifact(
        self,
        *,
        slice_payload: LabelAsOfSlice,
        output_root: Path | None = None,
    ) -> LabelSliceArtifactRef:
        run_root = Path(output_root) if output_root is not None else RUNS_ROOT / slice_payload.platform_run_id
        slices_root = run_root / "label_store" / "slices"
        filename = f"resolved_as_of_{slice_payload.basis_digest[:16]}_{slice_payload.slice_digest[:16]}.json"
        output_path = slices_root / filename
        payload = slice_payload.as_dict()
        digest = _slice_digest(
            basis_digest=slice_payload.basis_digest,
            rows=slice_payload.rows,
        )
        if digest != slice_payload.slice_digest:
            raise LabelStoreSliceError("slice_payload digest mismatch; payload is not deterministic")

        written_new = True
        if output_path.exists():
            try:
                existing_payload = json.loads(output_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise LabelStoreSliceError("existing slice artifact is not valid JSON") from exc
            existing_digest = str(existing_payload.get("slice_digest") or "").strip()
            if existing_digest != digest:
                raise LabelStoreSliceError("slice artifact immutability violation: existing artifact digest mismatch")
            written_new = False
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )

        if output_root is None:
            slice_ref = f"runs/fraud-platform/{slice_payload.platform_run_id}/label_store/slices/{filename}"
        else:
            slice_ref = str(output_path)
        return LabelSliceArtifactRef(
            slice_ref=slice_ref,
            local_path=str(output_path),
            slice_digest=digest,
            basis_digest=slice_payload.basis_digest,
            row_count=slice_payload.row_count,
            written_new=written_new,
        )


def _normalize_targets(
    *,
    target_subjects: Sequence[Mapping[str, Any] | LabelSliceTarget],
    max_targets: int,
) -> tuple[LabelSliceTarget, ...]:
    if not target_subjects:
        raise LabelStoreSliceError("target_subjects must be non-empty")
    if len(target_subjects) > max_targets:
        raise LabelStoreSliceError(f"target_subjects exceeds max_targets={max_targets}")
    deduped: dict[tuple[str, str], LabelSliceTarget] = {}
    for item in target_subjects:
        target = item if isinstance(item, LabelSliceTarget) else LabelSliceTarget.from_payload(item)
        deduped[(target.platform_run_id, target.event_id)] = target
    normalized = sorted(deduped.values(), key=lambda target: (target.platform_run_id, target.event_id))
    if not normalized:
        raise LabelStoreSliceError("target_subjects resolved to empty after normalization")
    return tuple(normalized)


def _normalize_label_types(label_types: Sequence[str] | None) -> tuple[str, ...]:
    if label_types is None:
        return tuple(sorted(LABEL_TYPES))
    values: list[str] = []
    for item in label_types:
        text = _required_text(item, "label_types[]")
        if text not in LABEL_TYPES:
            raise LabelStoreSliceError(
                f"label_types contains unsupported value: {text!r}; expected one of {sorted(LABEL_TYPES)!r}"
            )
        values.append(text)
    deduped = sorted(set(values))
    if not deduped:
        raise LabelStoreSliceError("label_types must be non-empty when provided")
    return tuple(deduped)


def _coverage_signals(
    *,
    rows: Sequence[LabelAsOfSliceRow],
    label_types: Sequence[str],
    target_total: int,
) -> tuple[LabelCoverageSignal, ...]:
    counts: dict[str, dict[str, int]] = {}
    for label_type in label_types:
        counts[label_type] = {
            LS_AS_OF_RESOLVED: 0,
            LS_AS_OF_CONFLICT: 0,
            LS_AS_OF_NOT_FOUND: 0,
        }
    for row in rows:
        lane = counts.get(row.label_type)
        if lane is None:
            continue
        status = row.status
        lane[status] = lane.get(status, 0) + 1

    signals: list[LabelCoverageSignal] = []
    for label_type in sorted(label_types):
        lane = counts[label_type]
        resolved_total = int(lane.get(LS_AS_OF_RESOLVED, 0))
        conflict_total = int(lane.get(LS_AS_OF_CONFLICT, 0))
        not_found_total = int(lane.get(LS_AS_OF_NOT_FOUND, 0))
        if target_total <= 0:
            coverage_ratio = 0.0
            conflict_ratio = 0.0
            maturity_ratio = 0.0
        else:
            coverage_ratio = resolved_total / float(target_total)
            conflict_ratio = conflict_total / float(target_total)
            maturity_ratio = (resolved_total + conflict_total) / float(target_total)
        signals.append(
            LabelCoverageSignal(
                label_type=label_type,
                target_total=int(target_total),
                resolved_total=resolved_total,
                conflict_total=conflict_total,
                not_found_total=not_found_total,
                coverage_ratio=round(coverage_ratio, 6),
                conflict_ratio=round(conflict_ratio, 6),
                maturity_ratio=round(maturity_ratio, 6),
            )
        )
    return tuple(signals)


def _policy_revision(*, policy_id: str, revision: str, label_types: Sequence[str]) -> dict[str, str]:
    digest = _hash_with_recipe(
        LS_SLICE_POLICY_DIGEST_RECIPE_V1,
        {
            "policy_id": policy_id,
            "revision": revision,
            "resolution_semantics": "effective_time_desc,observed_time_desc,label_assertion_id_desc",
            "conflict_posture": "EXPLICIT_CONFLICT",
            "label_types": list(label_types),
        },
    )
    return {
        "policy_id": policy_id,
        "revision": revision,
        "content_digest": digest,
    }


def _hash_with_recipe(recipe: str, payload: Any) -> str:
    canonical = _canonical_json(
        {
            "recipe": recipe,
            "payload": payload,
        }
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _slice_digest(*, basis_digest: str, rows: Sequence[LabelAsOfSliceRow]) -> str:
    return _hash_with_recipe(
        LS_SLICE_PAYLOAD_DIGEST_RECIPE_V1,
        {
            "basis_digest": basis_digest,
            "rows": [row.as_dict() for row in rows],
        },
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _normalize_ts(value: Any, field_name: str) -> str:
    text = _required_text(value, field_name)
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(probe)
    except ValueError as exc:
        raise LabelStoreSliceError(f"{field_name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    normalized = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return normalized


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise LabelStoreSliceError(f"{field_name} is required")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
