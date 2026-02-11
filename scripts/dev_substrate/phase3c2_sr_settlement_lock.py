#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from urllib.parse import urlparse
import yaml


_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return loaded


def _check(condition: bool, name: str, detail: str, checks: list[dict[str, str]]) -> bool:
    status = "PASS" if condition else "FAIL"
    checks.append({"name": name, "status": status, "detail": detail})
    return condition


def _write_report(
    *,
    started_at: str,
    checks: list[dict[str, str]],
    decision: str,
    output_root: Path,
    artifact_prefix: str,
    details: dict[str, Any] | None = None,
) -> int:
    finished_at = _now_utc()
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_root / f"{artifact_prefix}_{stamp}.json"
    payload = {
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "decision": decision,
        "checks": checks,
    }
    if details:
        payload["details"] = details
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    for item in checks:
        print(f"[{item['status']}] {item['name']}: {item['detail']}")
    print(f"Decision: {decision}")
    print(f"Evidence: {output_path.as_posix()}")
    return 0 if decision == "PASS" else 2


def _expand_value(value: str, env: dict[str, str]) -> str:
    def replacer(match: re.Match[str]) -> str:
        token = match.group(1)
        if ":-" in token:
            key, default = token.split(":-", 1)
            actual = env.get(key)
            if actual in (None, ""):
                return default
            return str(actual)
        actual = env.get(token)
        if actual is None or str(actual).strip() == "":
            raise ValueError(f"missing env var for token: {token}")
        return str(actual)

    return _VAR_PATTERN.sub(replacer, value)


def _safe_scheme(value: str) -> str:
    parsed = urlparse(value)
    return str(parsed.scheme or "").lower()


def _redact_dsn(value: str) -> str:
    if "@" not in value or "://" not in value:
        return value
    prefix, rest = value.split("://", 1)
    if "@" not in rest:
        return value
    creds, tail = rest.split("@", 1)
    if ":" not in creds:
        return f"{prefix}://***@{tail}"
    user = creds.split(":", 1)[0]
    return f"{prefix}://{user}:***@{tail}"


def cmd_preflight(args: argparse.Namespace) -> int:
    started = _now_utc()
    checks: list[dict[str, str]] = []
    details: dict[str, Any] = {}
    all_ok = True

    try:
        settlement = _load_yaml(Path(args.settlement))
        wiring = _load_yaml(Path(args.wiring))
    except Exception as exc:
        checks.append({"name": "load_inputs", "status": "FAIL", "detail": str(exc)})
        return _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c2_sr_s1_preflight",
        )

    required_settlement_keys = {
        "version",
        "settlement_id",
        "component",
        "phase",
        "runtime_acceptance",
        "state_acceptance",
        "run_identity_sources",
        "reemit_policy",
    }
    for key in sorted(required_settlement_keys):
        all_ok &= _check(key in settlement, f"settlement_key_{key}", "present" if key in settlement else "missing", checks)

    runtime_acceptance = settlement.get("runtime_acceptance", {})
    state_acceptance = settlement.get("state_acceptance", {})
    run_identity_sources = settlement.get("run_identity_sources", {})
    reemit_policy = settlement.get("reemit_policy", {})

    all_ok &= _check(
        str(runtime_acceptance.get("mode", "")).strip().lower() == "managed_only",
        "runtime_mode_managed_only",
        str(runtime_acceptance.get("mode", "")),
        checks,
    )
    all_ok &= _check(
        str(state_acceptance.get("mode", "")).strip().lower() == "managed_only",
        "state_mode_managed_only",
        str(state_acceptance.get("mode", "")),
        checks,
    )
    all_ok &= _check(
        bool(reemit_policy.get("same_platform_run_only", False)),
        "reemit_same_platform_run_only",
        str(reemit_policy.get("same_platform_run_only", False)),
        checks,
    )
    override_policy = reemit_policy.get("cross_run_override", {}) if isinstance(reemit_policy.get("cross_run_override"), dict) else {}
    all_ok &= _check(
        bool(override_policy.get("required", False)),
        "reemit_cross_run_override_required",
        str(override_policy.get("required", False)),
        checks,
    )

    expected_identity_sources = {
        "platform_run_id": "scenario_runner.platform_run_id",
        "scenario_run_id": "run_plan.run_id",
        "run_config_digest": "run_plan.policy_rev.content_digest",
    }
    for key, expected in expected_identity_sources.items():
        observed = str(run_identity_sources.get(key, "")).strip()
        all_ok &= _check(observed == expected, f"run_identity_source_{key}", observed or "missing", checks)

    env = dict(os.environ)
    resolved_object_store_root = ""
    resolved_authority_dsn = ""
    resolved_execution_identity = ""
    try:
        resolved_object_store_root = _expand_value(str(wiring.get("object_store_root", "")), env)
        resolved_authority_dsn = _expand_value(str(wiring.get("authority_store_dsn", "")), env)
        execution_identity_env = str(wiring.get("execution_identity_env", "")).strip()
        if execution_identity_env:
            resolved_execution_identity = str(env.get(execution_identity_env, "")).strip()
        details["resolved_object_store_root"] = resolved_object_store_root
        details["resolved_authority_store_dsn"] = _redact_dsn(resolved_authority_dsn)
        details["resolved_execution_identity"] = resolved_execution_identity or "<missing>"
    except Exception as exc:
        all_ok &= _check(False, "wiring_env_resolution", str(exc), checks)

    all_ok &= _check(
        str(wiring.get("acceptance_mode", "")).strip().lower() == "dev_min_managed",
        "wiring_acceptance_mode",
        str(wiring.get("acceptance_mode", "")),
        checks,
    )
    all_ok &= _check(
        str(wiring.get("execution_mode", "")).strip().lower() == "managed",
        "wiring_execution_mode",
        str(wiring.get("execution_mode", "")),
        checks,
    )
    all_ok &= _check(
        str(wiring.get("state_mode", "")).strip().lower() == "managed",
        "wiring_state_mode",
        str(wiring.get("state_mode", "")),
        checks,
    )
    expected_launch_ref = str(runtime_acceptance.get("launch_ref", "")).strip()
    observed_launch_ref = str(wiring.get("execution_launch_ref", "")).strip()
    all_ok &= _check(
        observed_launch_ref == expected_launch_ref and bool(observed_launch_ref),
        "wiring_launch_ref_alignment",
        observed_launch_ref or "missing",
        checks,
    )
    if observed_launch_ref:
        all_ok &= _check(Path(observed_launch_ref).exists(), "wiring_launch_ref_exists", observed_launch_ref, checks)
    expected_identity_env = str(runtime_acceptance.get("execution_identity_env", "")).strip()
    observed_identity_env = str(wiring.get("execution_identity_env", "")).strip()
    all_ok &= _check(
        observed_identity_env == expected_identity_env and bool(observed_identity_env),
        "wiring_execution_identity_env_alignment",
        observed_identity_env or "missing",
        checks,
    )
    if observed_identity_env:
        all_ok &= _check(
            bool(str(os.getenv(observed_identity_env, "")).strip()),
            "wiring_execution_identity_env_set",
            observed_identity_env,
            checks,
        )

    if resolved_object_store_root:
        all_ok &= _check(
            _safe_scheme(resolved_object_store_root) == "s3",
            "wiring_object_store_s3",
            resolved_object_store_root,
            checks,
        )
    if resolved_authority_dsn:
        scheme = _safe_scheme(resolved_authority_dsn)
        all_ok &= _check(
            scheme in {"postgres", "postgresql"},
            "wiring_authority_store_postgres",
            _redact_dsn(resolved_authority_dsn),
            checks,
        )

    control_bus_kind = str(wiring.get("control_bus_kind", "file")).strip().lower()
    all_ok &= _check(
        control_bus_kind != "file",
        "wiring_control_bus_non_file",
        control_bus_kind,
        checks,
    )
    all_ok &= _check(
        bool(wiring.get("reemit_same_platform_run_only", False)),
        "wiring_reemit_same_platform_run_only",
        str(wiring.get("reemit_same_platform_run_only", False)),
        checks,
    )
    all_ok &= _check(
        bool(wiring.get("reemit_cross_run_override_required", False)),
        "wiring_reemit_cross_run_override_required",
        str(wiring.get("reemit_cross_run_override_required", False)),
        checks,
    )

    required_reasons = {
        str(item).strip().upper()
        for item in (override_policy.get("reason_codes") or [])
        if str(item).strip()
    }
    wiring_reasons = {
        str(item).strip().upper()
        for item in (wiring.get("reemit_cross_run_reason_allowlist") or [])
        if str(item).strip()
    }
    all_ok &= _check(
        required_reasons.issubset(wiring_reasons),
        "wiring_reemit_reason_allowlist_alignment",
        f"required={sorted(required_reasons)} observed={sorted(wiring_reasons)}",
        checks,
    )

    decision = "PASS" if all_ok else "FAIL_CLOSED"
    return _write_report(
        started_at=started,
        checks=checks,
        decision=decision,
        output_root=Path(args.output_root),
        artifact_prefix="phase3c2_sr_s1_preflight",
        details=details,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Dev-substrate Phase 3.C.2 S1 SR settlement lock checker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="Validate SR S1 managed settlement posture")
    preflight.add_argument(
        "--settlement",
        default="config/platform/dev_substrate/phase3/scenario_runner_settlement_v0.yaml",
        help="Path to SR settlement file",
    )
    preflight.add_argument(
        "--wiring",
        default="config/platform/sr/wiring_dev_min.yaml",
        help="Path to SR wiring file",
    )
    preflight.add_argument(
        "--output-root",
        default="runs/fraud-platform/dev_substrate/phase3",
        help="Output root for S1 evidence JSON",
    )
    preflight.set_defaults(handler=cmd_preflight)

    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
