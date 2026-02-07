"""DL policy profile loader (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from .contracts import CapabilitiesMask, DegradeContractError, MODE_SEQUENCE, PolicyRev, ensure_mode_sequence


class DlConfigError(ValueError):
    """Raised when DL policy profile configuration is invalid."""


@dataclass(frozen=True)
class DlModePolicy:
    mode: str
    capabilities_mask: CapabilitiesMask

    def as_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "capabilities_mask": self.capabilities_mask.as_dict()}


@dataclass(frozen=True)
class DlPolicyProfile:
    profile_id: str
    mode_sequence: tuple[str, ...]
    modes: dict[str, DlModePolicy]
    thresholds: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "mode_sequence": list(self.mode_sequence),
            "modes": {key: mode.as_dict() for key, mode in self.modes.items()},
            "thresholds": self.thresholds,
        }


@dataclass(frozen=True)
class DlPolicyBundle:
    schema_version: str
    policy_rev: PolicyRev
    profiles: dict[str, DlPolicyProfile]

    def profile(self, profile_id: str) -> DlPolicyProfile:
        key = str(profile_id).strip()
        if key not in self.profiles:
            known = ",".join(sorted(self.profiles))
            raise DlConfigError(f"unknown DL policy profile_id '{key}' (known: {known})")
        return self.profiles[key]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_rev": self.policy_rev.as_dict(),
            "profiles": {key: profile.as_dict() for key, profile in self.profiles.items()},
        }

    def canonical_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def load_policy_bundle(path: Path) -> DlPolicyBundle:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise DlConfigError("DL policy profile file must be a mapping")

    schema_version = str(data.get("schema_version") or "").strip()
    if not schema_version:
        raise DlConfigError("schema_version is required")

    policy_id = str(data.get("policy_id") or "").strip()
    revision = str(data.get("revision") or "").strip()
    if not policy_id or not revision:
        raise DlConfigError("policy_id and revision are required")

    profiles_payload = data.get("profiles")
    if not isinstance(profiles_payload, dict) or not profiles_payload:
        raise DlConfigError("profiles must be a non-empty mapping")

    profiles: dict[str, DlPolicyProfile] = {}
    for profile_id, payload in profiles_payload.items():
        if not isinstance(payload, dict):
            raise DlConfigError(f"profile '{profile_id}' must be a mapping")
        profile_key = str(profile_id).strip()
        if not profile_key:
            raise DlConfigError("profile id cannot be empty")

        mode_sequence_raw = payload.get("mode_sequence")
        if not isinstance(mode_sequence_raw, list) or not mode_sequence_raw:
            raise DlConfigError(f"profile '{profile_key}' requires non-empty mode_sequence")
        try:
            mode_sequence = ensure_mode_sequence([str(item) for item in mode_sequence_raw])
        except DegradeContractError as exc:
            raise DlConfigError(f"profile '{profile_key}' has invalid mode_sequence: {exc}") from exc

        modes_payload = payload.get("modes")
        if not isinstance(modes_payload, dict):
            raise DlConfigError(f"profile '{profile_key}' requires modes mapping")

        modes: dict[str, DlModePolicy] = {}
        for mode in mode_sequence:
            mode_payload = modes_payload.get(mode)
            if not isinstance(mode_payload, dict):
                raise DlConfigError(f"profile '{profile_key}' missing mode policy for '{mode}'")
            mask_payload = mode_payload.get("capabilities_mask")
            if not isinstance(mask_payload, dict):
                raise DlConfigError(
                    f"profile '{profile_key}' mode '{mode}' requires capabilities_mask mapping"
                )
            try:
                mode_policy = DlModePolicy(mode=mode, capabilities_mask=CapabilitiesMask.from_payload(mask_payload))
            except DegradeContractError as exc:
                raise DlConfigError(
                    f"profile '{profile_key}' mode '{mode}' invalid capabilities_mask: {exc}"
                ) from exc
            modes[mode] = mode_policy

        thresholds = payload.get("thresholds")
        if thresholds is None:
            thresholds_payload: dict[str, Any] = {}
        elif not isinstance(thresholds, dict):
            raise DlConfigError(f"profile '{profile_key}' thresholds must be a mapping")
        else:
            thresholds_payload = thresholds

        profiles[profile_key] = DlPolicyProfile(
            profile_id=profile_key,
            mode_sequence=mode_sequence,
            modes=modes,
            thresholds=thresholds_payload,
        )

    content_digest = str(data.get("content_digest") or "").strip()
    if not content_digest:
        canonical = {
            "schema_version": schema_version,
            "policy_id": policy_id,
            "revision": revision,
            "profiles": {key: profile.as_dict() for key, profile in profiles.items()},
        }
        content_digest = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    return DlPolicyBundle(
        schema_version=schema_version,
        policy_rev=PolicyRev(policy_id=policy_id, revision=revision, content_digest=content_digest),
        profiles=profiles,
    )
