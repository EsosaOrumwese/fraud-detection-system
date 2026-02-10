"""Validation CLI for WSP Phase 4 (local smoke + dev completion)."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
import logging
from pathlib import Path
from typing import Any

from fraud_detection.platform_runtime import append_session_event, platform_log_paths
from fraud_detection.scenario_runner.logging_utils import configure_logging

from .checkpoints import FileCheckpointStore
from .config import WspProfile
from .runner import WorldStreamProducer

logger = logging.getLogger(__name__)


def _parse_output_ids(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or None


def _choose_outputs(profile: WspProfile, override: list[str] | None) -> list[str]:
    if override:
        return override
    return list(profile.policy.traffic_output_ids)


def _cursor_path(root: Path, pack_key: str, output_id: str) -> Path:
    safe_output = output_id.replace("/", "_")
    return root / pack_key / f"output_id={safe_output}" / "cursor.json"


def _find_pack_key(root: Path, output_id: str) -> str | None:
    if not root.exists():
        return None
    cursor_paths: list[Path] = []
    for candidate in root.iterdir():
        if not candidate.is_dir():
            continue
        cursor = _cursor_path(root, candidate.name, output_id)
        if cursor.exists():
            cursor_paths.append(cursor)
    if not cursor_paths:
        return None
    chosen = max(cursor_paths, key=lambda path: path.stat().st_mtime)
    return chosen.parent.parent.name


def _load_cursor(root: Path, pack_key: str, output_id: str):
    store = FileCheckpointStore(root)
    return store.load(pack_key, output_id)


def _validate_resume(profile: WspProfile, *, output_id: str, max_events: int) -> dict[str, Any]:
    checkpoint_root = Path(profile.wiring.checkpoint_root)
    pack_key = _find_pack_key(checkpoint_root, output_id)
    if not pack_key:
        return {"status": "WARN", "reason": "CHECKPOINT_NOT_FOUND"}
    before = _load_cursor(checkpoint_root, pack_key, output_id)
    if not before:
        return {"status": "WARN", "reason": "CURSOR_MISSING_BEFORE"}
    producer = WorldStreamProducer(profile)
    rerun = producer.stream_engine_world(
        engine_run_root=profile.wiring.oracle_engine_run_root,
        scenario_id=profile.wiring.oracle_scenario_id,
        output_ids=[output_id],
        max_events=max_events,
    )
    if rerun.status != "STREAMED":
        return {"status": "FAIL", "reason": f"RESUME_FAILED:{rerun.reason}"}
    after = _load_cursor(checkpoint_root, pack_key, output_id)
    if not after:
        return {"status": "WARN", "reason": "CURSOR_MISSING_AFTER"}
    advanced = (after.last_file, after.last_row_index) != (before.last_file, before.last_row_index)
    if not advanced and rerun.emitted > 0:
        return {"status": "FAIL", "reason": "CURSOR_NOT_ADVANCED"}
    if not advanced and rerun.emitted == 0:
        return {"status": "WARN", "reason": "NO_REMAINING_EVENTS"}
    return {"status": "PASS", "emitted": rerun.emitted}


def _validate_allowlist(profile: WspProfile) -> dict[str, Any]:
    invalid = replace(profile.wiring, producer_id="svc:invalid")
    bad_profile = WspProfile(policy=profile.policy, wiring=invalid)
    producer = WorldStreamProducer(bad_profile)
    result = producer.stream_engine_world(
        engine_run_root=bad_profile.wiring.oracle_engine_run_root,
        scenario_id=bad_profile.wiring.oracle_scenario_id,
        max_events=1,
    )
    if result.status == "FAILED" and result.reason == "PRODUCER_NOT_ALLOWED":
        return {"status": "PASS"}
    return {"status": "FAIL", "reason": f"EXPECTED_PRODUCER_NOT_ALLOWED:{result.reason}"}


def _validate_local(
    profile: WspProfile,
    *,
    output_ids: list[str] | None,
    max_events: int,
    resume_events: int,
    skip_resume: bool,
    check_failures: bool,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    producer = WorldStreamProducer(profile)
    result = producer.stream_engine_world(
        engine_run_root=profile.wiring.oracle_engine_run_root,
        scenario_id=profile.wiring.oracle_scenario_id,
        output_ids=output_ids,
        max_events=max_events,
    )
    checks.append({"name": "smoke_stream", "status": "PASS" if result.status == "STREAMED" else "FAIL", "reason": result.reason})
    if result.status != "STREAMED":
        return {"status": "FAIL", "checks": checks}

    chosen = _choose_outputs(profile, output_ids)
    if not skip_resume:
        if profile.wiring.checkpoint_backend != "file":
            checks.append({"name": "resume", "status": "WARN", "reason": "NON_FILE_CHECKPOINT"})
        elif chosen:
            resume_result = _validate_resume(profile, output_id=chosen[0], max_events=resume_events)
            checks.append({"name": "resume", **resume_result})
        else:
            checks.append({"name": "resume", "status": "WARN", "reason": "NO_OUTPUT_IDS"})

    if check_failures:
        checks.append({"name": "allowlist_fail", **_validate_allowlist(profile)})

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "WARN"
    if any(item["status"] == "FAIL" for item in checks):
        status = "FAIL"
    return {"status": status, "checks": checks}


def _validate_dev(profile: WspProfile, *, output_ids: list[str] | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    if profile.wiring.checkpoint_backend != "postgres":
        checks.append({"name": "checkpoint_backend", "status": "WARN", "reason": "NOT_POSTGRES"})
    producer = WorldStreamProducer(profile)
    result = producer.stream_engine_world(
        engine_run_root=profile.wiring.oracle_engine_run_root,
        scenario_id=profile.wiring.oracle_scenario_id,
        output_ids=output_ids,
        max_events=None,
    )
    checks.append({"name": "completion_stream", "status": "PASS" if result.status == "STREAMED" else "FAIL", "reason": result.reason})
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {"status": status, "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser(description="WSP Phase 4 validation")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--engine-run-root", required=False, help="Engine run root (overrides profile wiring)")
    parser.add_argument("--scenario-id", required=False, help="Scenario id (overrides profile wiring)")
    parser.add_argument("--output-ids", help="Comma-separated output_ids override")
    parser.add_argument("--mode", choices=["local", "dev"], default="local")
    parser.add_argument("--max-events", type=int, default=10)
    parser.add_argument("--resume-events", type=int, default=1)
    parser.add_argument("--skip-resume", action="store_true")
    parser.add_argument("--check-failures", action="store_true")
    args = parser.parse_args()

    configure_logging(level=logging.INFO, log_paths=platform_log_paths(create_if_missing=True))
    profile = WspProfile.load(Path(args.profile))
    if args.engine_run_root:
        profile = WspProfile(policy=profile.policy, wiring=replace(profile.wiring, oracle_engine_run_root=args.engine_run_root))
    if args.scenario_id:
        profile = WspProfile(policy=profile.policy, wiring=replace(profile.wiring, oracle_scenario_id=args.scenario_id))

    append_session_event(
        "wsp",
        "validation_start",
        {"mode": args.mode, "engine_run_root": profile.wiring.oracle_engine_run_root},
        create_if_missing=True,
    )

    override = _parse_output_ids(args.output_ids)
    if args.mode == "dev":
        result = _validate_dev(profile, output_ids=override)
    else:
        result = _validate_local(
            profile,
            output_ids=override,
            max_events=args.max_events,
            resume_events=args.resume_events,
            skip_resume=args.skip_resume,
            check_failures=args.check_failures,
        )

    append_session_event(
        "wsp",
        "validation_complete",
        {"mode": args.mode, "status": result.get("status")},
        create_if_missing=False,
    )
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result.get("status") == "PASS" else 1)


if __name__ == "__main__":
    main()
