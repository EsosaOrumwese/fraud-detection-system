"""Platform-wide governance event writer/query helpers.

Keep this package surface lazy so hot-path components such as IG do not pull
optional evidence-corridor or scenario-runner surfaces during import.
"""

from __future__ import annotations

from importlib import import_module


_WRITER_EXPORTS = {
    "GovernanceEvent",
    "PlatformGovernanceError",
    "PlatformGovernanceWriter",
    "build_platform_governance_writer",
    "emit_platform_governance_event",
}
_EVIDENCE_EXPORTS = {
    "EvidenceRefResolutionCorridor",
    "EvidenceRefResolutionError",
    "EvidenceRefResolutionRequest",
    "EvidenceRefResolutionResult",
    "build_evidence_ref_resolution_corridor",
}

__all__ = [
    "GovernanceEvent",
    "EvidenceRefResolutionCorridor",
    "EvidenceRefResolutionError",
    "EvidenceRefResolutionRequest",
    "EvidenceRefResolutionResult",
    "build_evidence_ref_resolution_corridor",
    "classify_anomaly",
    "PlatformGovernanceError",
    "PlatformGovernanceWriter",
    "build_platform_governance_writer",
    "emit_platform_governance_event",
]


def __getattr__(name: str):
    if name == "classify_anomaly":
        module = import_module(".anomaly_taxonomy", __name__)
        return getattr(module, name)
    if name in _WRITER_EXPORTS:
        module = import_module(".writer", __name__)
        return getattr(module, name)
    if name in _EVIDENCE_EXPORTS:
        module = import_module(".evidence_corridor", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
