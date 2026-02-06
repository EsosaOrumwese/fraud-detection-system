"""OFP serve surface (Phase 5): deterministic get_features semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .contracts import (
    OfpContractError,
    build_get_features_error,
    build_get_features_success,
    validate_get_features_request,
)
from .snapshots import OfpSnapshotMaterializer

GraphVersionResolver = Callable[[dict[str, Any]], dict[str, Any] | None]


@dataclass
class OfpGetFeaturesService:
    """Deterministic OFP query surface for DF/DL callers."""

    materializer: OfpSnapshotMaterializer
    graph_version_resolver: GraphVersionResolver | None = None

    @classmethod
    def build(
        cls,
        profile_path: str,
        *,
        graph_version_resolver: GraphVersionResolver | None = None,
    ) -> "OfpGetFeaturesService":
        materializer = OfpSnapshotMaterializer.build(profile_path)
        return cls(materializer=materializer, graph_version_resolver=graph_version_resolver)

    def get_features(self, payload: dict[str, Any]) -> dict[str, Any]:
        served_at_utc = _utc_now()
        try:
            request = validate_get_features_request(payload)
        except OfpContractError as exc:
            return build_get_features_error(
                exc.code,
                detail=exc.detail or "request validation failed",
                request_id=str(payload.get("request_id")) if isinstance(payload, dict) else None,
                served_at_utc=served_at_utc,
            )

        request_id = str(request.get("request_id") or "") or None
        graph_resolution_mode = str(request.get("graph_resolution_mode") or "resolve_if_needed")
        graph_version = None
        posture_flags: list[str] = []

        if graph_resolution_mode != "none":
            if self.graph_version_resolver is None:
                if graph_resolution_mode == "require_ieg":
                    return build_get_features_error(
                        "UNAVAILABLE",
                        detail="graph_resolution_mode=require_ieg but no graph resolver is configured",
                        request_id=request_id,
                        served_at_utc=served_at_utc,
                    )
                posture_flags.append("GRAPH_VERSION_UNAVAILABLE")
            else:
                try:
                    graph_version = self.graph_version_resolver(request)
                except Exception as exc:
                    return build_get_features_error(
                        "UNAVAILABLE",
                        detail=f"graph resolver failed: {exc}",
                        request_id=request_id,
                        served_at_utc=served_at_utc,
                    )
                if graph_version is None:
                    if graph_resolution_mode == "require_ieg":
                        return build_get_features_error(
                            "UNAVAILABLE",
                            detail="graph_resolution_mode=require_ieg but no graph version is available",
                            request_id=request_id,
                            served_at_utc=served_at_utc,
                        )
                    posture_flags.append("GRAPH_VERSION_UNAVAILABLE")

        pins = request["pins"]
        try:
            snapshot = self.materializer.materialize(
                platform_run_id=str(pins["platform_run_id"]),
                scenario_run_id=str(pins["scenario_run_id"]),
                as_of_time_utc=str(request["as_of_time_utc"]),
                graph_version=graph_version,
            )
        except RuntimeError as exc:
            message = str(exc)
            code = "NOT_FOUND" if message == "OFP_SNAPSHOT_STATE_MISSING" else "UNAVAILABLE"
            return build_get_features_error(
                code,
                detail=message,
                request_id=request_id,
                served_at_utc=served_at_utc,
            )

        requested_feature_keys = [
            f"{item['key_type']}:{item['key_id']}"
            for item in list(request.get("feature_keys") or [])
        ]
        feature_payload = snapshot.get("features")
        if not isinstance(feature_payload, dict):
            feature_payload = {}
        filtered_features: dict[str, Any] = {}
        missing_feature_keys: list[str] = []
        for token in requested_feature_keys:
            if token in feature_payload:
                filtered_features[token] = feature_payload[token]
            else:
                missing_feature_keys.append(token)
        snapshot["features"] = filtered_features

        requested_groups = list(request.get("feature_groups") or [])
        requested_group_names = [str(item.get("name") or "") for item in requested_groups if str(item.get("name") or "")]
        available_groups = {
            (str(item.get("name") or ""), str(item.get("version") or ""))
            for item in list(snapshot.get("feature_groups") or [])
            if isinstance(item, dict)
        }
        missing_groups_from_request = sorted(
            {
                str(item.get("name") or "")
                for item in requested_groups
                if (str(item.get("name") or ""), str(item.get("version") or "")) not in available_groups
                and str(item.get("name") or "")
            }
        )

        if missing_feature_keys:
            posture_flags.append("MISSING_FEATURE_STATE")
        if missing_groups_from_request:
            posture_flags.append("MISSING_FEATURE_GROUP")

        stale_groups = _normalize_list((snapshot.get("freshness") or {}).get("stale_groups"))
        missing_groups = _normalize_list((snapshot.get("freshness") or {}).get("missing_groups"))

        as_of_time_utc = str(request["as_of_time_utc"])
        window_end_utc = _read_basis_window_end(snapshot)
        if _is_after(as_of_time_utc, window_end_utc):
            stale_groups = _unique_sorted(stale_groups + requested_group_names)
            posture_flags.append("STALE_INPUT_BASIS")

        if missing_feature_keys:
            missing_groups = _unique_sorted(missing_groups + requested_group_names)
        if missing_groups_from_request:
            missing_groups = _unique_sorted(missing_groups + missing_groups_from_request)

        posture_flags = _unique_sorted(posture_flags)
        posture_state = _posture_state(
            missing_feature_keys=missing_feature_keys,
            missing_groups=missing_groups,
            posture_flags=posture_flags,
        )
        snapshot["freshness"] = {
            "state": posture_state,
            "flags": posture_flags,
            "stale_groups": stale_groups,
            "missing_groups": missing_groups,
            "missing_feature_keys": _unique_sorted(missing_feature_keys),
        }

        return build_get_features_success(
            snapshot,
            request_id=request_id,
            served_at_utc=served_at_utc,
        )


def _read_basis_window_end(snapshot: dict[str, Any]) -> str | None:
    basis = snapshot.get("eb_offset_basis")
    if not isinstance(basis, dict):
        return None
    value = basis.get("window_end_utc")
    if value in (None, ""):
        return None
    return str(value)


def _parse_ts(value: str | None) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _is_after(left: str | None, right: str | None) -> bool:
    left_dt = _parse_ts(left)
    right_dt = _parse_ts(right)
    if left_dt is None or right_dt is None:
        return False
    return left_dt > right_dt


def _normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted({str(item) for item in values if str(item).strip()})


def _posture_state(
    *,
    missing_feature_keys: list[str],
    missing_groups: list[str],
    posture_flags: list[str],
) -> str:
    if missing_feature_keys or missing_groups:
        return "RED"
    if posture_flags:
        return "AMBER"
    return "GREEN"


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

