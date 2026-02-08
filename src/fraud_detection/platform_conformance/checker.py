"""Static environment-parity conformance checks for local_parity/dev/prod profiles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml

from fraud_detection.platform_governance.writer import EVENT_FAMILIES
from fraud_detection.platform_runtime import RUNS_ROOT, resolve_platform_run_id


@dataclass(frozen=True)
class EnvironmentConformanceResult:
    status: str
    artifact_path: str
    payload: dict[str, Any]


def run_environment_conformance(
    *,
    local_parity_profile: str,
    dev_profile: str,
    prod_profile: str,
    platform_run_id: str | None = None,
    output_path: str | None = None,
) -> EnvironmentConformanceResult:
    run_id = str(platform_run_id or resolve_platform_run_id(create_if_missing=False) or "").strip()
    profiles = {
        "local_parity": _read_profile(Path(local_parity_profile), expected_profile_id="local_parity"),
        "dev": _read_profile(Path(dev_profile), expected_profile_id="dev"),
        "prod": _read_profile(Path(prod_profile), expected_profile_id="prod"),
    }
    checks: list[dict[str, Any]] = []
    checks.append(_check_semantic_alignment(profiles))
    checks.append(_check_policy_revision_stamps(profiles))
    checks.append(_check_security_posture(profiles))
    checks.append(_check_governance_schema_contract())

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    payload: dict[str, Any] = {
        "generated_at_utc": _utc_now(),
        "platform_run_id": run_id or None,
        "status": status,
        "checks": checks,
        "profiles": {name: item["profile_id"] for name, item in profiles.items()},
    }
    if output_path:
        artifact = Path(output_path)
    else:
        if not run_id:
            raise RuntimeError("platform_run_id is required when output_path is not provided")
        artifact = RUNS_ROOT / run_id / "obs" / "environment_conformance.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return EnvironmentConformanceResult(status=status, artifact_path=str(artifact), payload=payload)


def _check_semantic_alignment(profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fields = (
        ("policy.partitioning_profiles_ref", _policy_value),
        ("policy.partitioning_profile_id", _policy_value),
        ("policy.schema_policy_ref", _policy_value),
        ("policy.class_map_ref", _policy_value),
        ("wiring.event_bus.topic_control", _event_bus_topic),
        ("wiring.event_bus.topic_traffic", _event_bus_topic),
        ("wiring.event_bus.topic_audit", _event_bus_topic),
        ("wiring.control_bus.topic", _control_bus_topic),
    )
    mismatches: list[str] = []
    for field_name, resolver in fields:
        values = {name: resolver(profile, field_name) for name, profile in profiles.items()}
        unique = {value for value in values.values()}
        if len(unique) > 1:
            mismatches.append(f"{field_name}:{values}")
    status = "PASS" if not mismatches else "FAIL"
    return {
        "check_id": "semantic_contract_alignment",
        "status": status,
        "details": {"mismatches": mismatches},
    }


def _check_policy_revision_stamps(profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing: list[str] = []
    values: dict[str, str] = {}
    for name, profile in profiles.items():
        policy_rev = str(((profile.get("policy") or {}).get("policy_rev") or "")).strip()
        if not policy_rev:
            missing.append(name)
        values[name] = policy_rev
    status = "PASS" if not missing else "FAIL"
    return {
        "check_id": "policy_revision_presence",
        "status": status,
        "details": {"missing_profiles": missing, "values": values},
    }


def _check_security_posture(profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    local_security = _security(profiles["local_parity"])
    if _value(local_security, "auth_mode").lower() != "api_key":
        issues.append("local_parity.auth_mode must be api_key")
    if not (_value(local_security, "auth_allowlist_ref") or _value(local_security, "auth_allowlist")):
        issues.append("local_parity must define auth allowlist")

    dev_mode = _value(_security(profiles["dev"]), "auth_mode").lower()
    prod_mode = _value(_security(profiles["prod"]), "auth_mode").lower()
    if dev_mode != "service_token":
        issues.append("dev.auth_mode must be service_token")
    if prod_mode != "service_token":
        issues.append("prod.auth_mode must be service_token")

    dev_header = _value(_security(profiles["dev"]), "api_key_header")
    prod_header = _value(_security(profiles["prod"]), "api_key_header")
    if dev_header != prod_header:
        issues.append("dev/prod token header must match")

    dev_secret_env = _value(_security(profiles["dev"]), "service_token_secrets_env")
    prod_secret_env = _value(_security(profiles["prod"]), "service_token_secrets_env")
    if not dev_secret_env or not prod_secret_env:
        issues.append("dev/prod service_token_secrets_env must be set")
    elif dev_secret_env != prod_secret_env:
        issues.append("dev/prod service_token_secrets_env must match")

    for name in ("dev", "prod"):
        allowlist = _security(profiles[name]).get("auth_allowlist")
        if not isinstance(allowlist, list) or not [item for item in allowlist if str(item).strip()]:
            issues.append(f"{name}.auth_allowlist must be non-empty for service_token mode")

    status = "PASS" if not issues else "FAIL"
    return {
        "check_id": "security_corridor_posture",
        "status": status,
        "details": {"issues": issues},
    }


def _check_governance_schema_contract() -> dict[str, Any]:
    required = {
        "RUN_READY_SEEN",
        "RUN_STARTED",
        "RUN_ENDED",
        "RUN_CANCELLED",
        "POLICY_REV_CHANGED",
        "CORRIDOR_ANOMALY",
        "EVIDENCE_REF_RESOLVED",
        "RUN_REPORT_GENERATED",
    }
    missing = sorted(required.difference(EVENT_FAMILIES))
    status = "PASS" if not missing else "FAIL"
    return {
        "check_id": "governance_event_schema_contract",
        "status": status,
        "details": {"missing_families": missing, "declared_families": sorted(EVENT_FAMILIES)},
    }


def _read_profile(path: Path, *, expected_profile_id: str) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"profile not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"profile invalid: {path}")
    profile_id = str(payload.get("profile_id") or "").strip()
    if profile_id != expected_profile_id:
        raise RuntimeError(f"profile_id mismatch for {path}: expected {expected_profile_id}, got {profile_id}")
    return payload


def _policy_value(profile: dict[str, Any], field_name: str) -> str:
    key = field_name.split(".", 1)[-1]
    policy = profile.get("policy") if isinstance(profile.get("policy"), dict) else {}
    defaults = {
        "partitioning_profiles_ref": "config/platform/ig/partitioning_profiles_v0.yaml",
        "partitioning_profile_id": "ig.partitioning.v0.traffic",
        "schema_policy_ref": "config/platform/ig/schema_policy_v0.yaml",
        "class_map_ref": "config/platform/ig/class_map_v0.yaml",
    }
    return _value(policy, key) or defaults.get(key, "")


def _event_bus_topic(profile: dict[str, Any], field_name: str) -> str:
    key = field_name.split(".")[-1]
    wiring = profile.get("wiring") if isinstance(profile.get("wiring"), dict) else {}
    event_bus = wiring.get("event_bus") if isinstance(wiring.get("event_bus"), dict) else {}
    return _value(event_bus, key)


def _control_bus_topic(profile: dict[str, Any], _field_name: str) -> str:
    wiring = profile.get("wiring") if isinstance(profile.get("wiring"), dict) else {}
    control_bus = wiring.get("control_bus") if isinstance(wiring.get("control_bus"), dict) else {}
    return _value(control_bus, "topic")


def _security(profile: dict[str, Any]) -> dict[str, Any]:
    wiring = profile.get("wiring") if isinstance(profile.get("wiring"), dict) else {}
    security = wiring.get("security")
    return security if isinstance(security, dict) else {}


def _value(payload: dict[str, Any], key: str) -> str:
    return str(payload.get(key) or "").strip()


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
