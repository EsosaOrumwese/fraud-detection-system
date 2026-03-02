"""MPR runner CLI for learning registry lifecycle corridor operations."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Mapping

from .contracts import RegistryLifecycleEventContract, load_ownership_boundaries


logger = logging.getLogger("fraud_detection.learning_registry.worker")

_PROMOTE_EVENT = "BUNDLE_PROMOTED_ACTIVE"
_ROLLBACK_EVENT = "BUNDLE_ROLLED_BACK"


@dataclass(frozen=True)
class LearningRegistryWorkerConfig:
    profile_path: Path
    poll_seconds: float


@dataclass(frozen=True)
class LifecycleEventResult:
    status: str
    event_type: str
    registry_event_id: str
    scope_key: Mapping[str, Any]
    actor: Mapping[str, Any]
    written_at_utc: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "event_type": self.event_type,
            "registry_event_id": self.registry_event_id,
            "scope_key": dict(self.scope_key),
            "actor": dict(self.actor),
            "written_at_utc": self.written_at_utc,
        }


class LearningRegistryWorker:
    """Fail-closed MPR runner surface for promotion corridor commands."""

    def __init__(self, config: LearningRegistryWorkerConfig) -> None:
        self.config = config
        self._ownership = load_ownership_boundaries()

    def run_once(self) -> dict[str, Any]:
        # Queue/poll integration is introduced in M12. For M1.B, we expose a deterministic,
        # fail-closed runtime surface and prove the command contract exists.
        return {
            "status": "IDLE_NO_REQUEST_SOURCE",
            "ownership_owner_mpr": str((self._ownership.get("owners") or {}).get("mpr_registry") or ""),
            "written_at_utc": _utc_now(),
        }

    def run_forever(self) -> None:
        while True:
            payload = self.run_once()
            logger.info("MPR runner tick: %s", json.dumps(payload, sort_keys=True, ensure_ascii=True))
            time.sleep(self.config.poll_seconds)

    def validate_promote_event(self, event_path: Path) -> LifecycleEventResult:
        payload = _load_json_mapping(event_path)
        contract = RegistryLifecycleEventContract.from_payload(payload)
        return _validated_lifecycle_result(contract.payload, expected_event_type=_PROMOTE_EVENT)

    def validate_rollback_event(self, event_path: Path) -> LifecycleEventResult:
        payload = _load_json_mapping(event_path)
        contract = RegistryLifecycleEventContract.from_payload(payload)
        return _validated_lifecycle_result(contract.payload, expected_event_type=_ROLLBACK_EVENT)


def _validated_lifecycle_result(payload: Mapping[str, Any], *, expected_event_type: str) -> LifecycleEventResult:
    event_type = str(payload.get("event_type") or "")
    if event_type != expected_event_type:
        raise RuntimeError(
            f"MPR_EVENT_TYPE_INVALID:expected={expected_event_type}:actual={event_type or '<empty>'}"
        )
    return LifecycleEventResult(
        status="VALIDATED",
        event_type=event_type,
        registry_event_id=str(payload.get("registry_event_id") or ""),
        scope_key=dict(payload.get("scope_key") or {}),
        actor=dict(payload.get("actor") or {}),
        written_at_utc=_utc_now(),
    )


def _load_json_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"MPR_EVENT_PATH_NOT_FOUND:{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("MPR_EVENT_PAYLOAD_INVALID:expected_mapping")
    return dict(payload)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_worker_config(*, profile_path: Path, poll_seconds: float) -> LearningRegistryWorkerConfig:
    profile = Path(profile_path)
    if not profile.exists():
        raise RuntimeError(f"LEARNING_REGISTRY_PROFILE_NOT_FOUND:{profile}")
    return LearningRegistryWorkerConfig(profile_path=profile, poll_seconds=max(1.0, float(poll_seconds)))


def main() -> None:
    parser = argparse.ArgumentParser(description="MPR learning-registry runner")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--poll-seconds", type=float, default=15.0, help="Poll interval for run loop")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="Run MPR runner loop")
    run_cmd.add_argument("--once", action="store_true", help="Run one cycle and exit")

    promote_cmd = sub.add_parser("promote", help="Validate a promotion lifecycle event payload")
    promote_cmd.add_argument("--event-path", required=True, help="Path to lifecycle event JSON payload")

    rollback_cmd = sub.add_parser("rollback-drill", help="Validate a rollback lifecycle event payload")
    rollback_cmd.add_argument("--event-path", required=True, help="Path to lifecycle event JSON payload")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    config = load_worker_config(profile_path=Path(args.profile), poll_seconds=float(args.poll_seconds))
    worker = LearningRegistryWorker(config)

    if args.command == "run":
        if args.once:
            print(json.dumps(worker.run_once(), sort_keys=True, ensure_ascii=True))
            return
        worker.run_forever()
        return
    if args.command == "promote":
        result = worker.validate_promote_event(Path(str(args.event_path)))
        print(json.dumps(result.as_dict(), sort_keys=True, ensure_ascii=True))
        return
    if args.command == "rollback-drill":
        result = worker.validate_rollback_event(Path(str(args.event_path)))
        print(json.dumps(result.as_dict(), sort_keys=True, ensure_ascii=True))
        return
    raise RuntimeError(f"LEARNING_REGISTRY_COMMAND_UNSUPPORTED:{args.command}")


if __name__ == "__main__":
    main()
