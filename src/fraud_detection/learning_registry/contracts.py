"""Typed contracts for Learning + Registry plane (Phase 6.1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .schemas import LearningRegistrySchemaRegistry


_DATASET_MANIFEST_SCHEMA = "dataset_manifest_v0.schema.yaml"
_EVAL_REPORT_SCHEMA = "eval_report_v0.schema.yaml"
_BUNDLE_PUBLICATION_SCHEMA = "bundle_publication_v0.schema.yaml"
_REGISTRY_LIFECYCLE_SCHEMA = "registry_lifecycle_event_v0.schema.yaml"
_DF_BUNDLE_RESOLUTION_SCHEMA = "df_bundle_resolution_v0.schema.yaml"
_OWNERSHIP_PATH = Path("config/platform/learning_registry/ownership_boundaries_v0.yaml")


@dataclass(frozen=True)
class DatasetManifestContract:
    payload: dict[str, Any]

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        registry: LearningRegistrySchemaRegistry | None = None,
    ) -> "DatasetManifestContract":
        body = _payload(payload)
        (registry or LearningRegistrySchemaRegistry()).validate(_DATASET_MANIFEST_SCHEMA, body)
        return cls(payload=body)


@dataclass(frozen=True)
class EvalReportContract:
    payload: dict[str, Any]

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        registry: LearningRegistrySchemaRegistry | None = None,
    ) -> "EvalReportContract":
        body = _payload(payload)
        (registry or LearningRegistrySchemaRegistry()).validate(_EVAL_REPORT_SCHEMA, body)
        return cls(payload=body)


@dataclass(frozen=True)
class BundlePublicationContract:
    payload: dict[str, Any]

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        registry: LearningRegistrySchemaRegistry | None = None,
    ) -> "BundlePublicationContract":
        body = _payload(payload)
        (registry or LearningRegistrySchemaRegistry()).validate(_BUNDLE_PUBLICATION_SCHEMA, body)
        return cls(payload=body)


@dataclass(frozen=True)
class RegistryLifecycleEventContract:
    payload: dict[str, Any]

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        registry: LearningRegistrySchemaRegistry | None = None,
    ) -> "RegistryLifecycleEventContract":
        body = _payload(payload)
        (registry or LearningRegistrySchemaRegistry()).validate(_REGISTRY_LIFECYCLE_SCHEMA, body)
        return cls(payload=body)


@dataclass(frozen=True)
class DfBundleResolutionContract:
    payload: dict[str, Any]

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        registry: LearningRegistrySchemaRegistry | None = None,
    ) -> "DfBundleResolutionContract":
        body = _payload(payload)
        (registry or LearningRegistrySchemaRegistry()).validate(_DF_BUNDLE_RESOLUTION_SCHEMA, body)
        return cls(payload=body)


def load_ownership_boundaries(path: Path | str = _OWNERSHIP_PATH) -> dict[str, Any]:
    resolved = Path(path)
    if not resolved.exists():
        raise ValueError(f"ownership boundaries file not found: {resolved}")
    payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("ownership boundaries payload must be a mapping")
    required = ("owners", "inputs", "outputs")
    for key in required:
        if key not in payload:
            raise ValueError(f"ownership boundaries missing key: {key}")
    return dict(payload)


def _payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    return dict(payload)
