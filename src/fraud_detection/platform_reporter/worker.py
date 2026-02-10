"""Platform run reporter worker CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import time

from fraud_detection.platform_runtime import resolve_platform_run_id

from .run_reporter import PlatformRunReporter


logger = logging.getLogger("fraud_detection.platform_reporter.worker")


@dataclass(frozen=True)
class PlatformRunReporterWorkerConfig:
    profile_path: Path
    poll_seconds: float
    required_platform_run_id: str | None = None


class PlatformRunReporterWorker:
    def __init__(self, config: PlatformRunReporterWorkerConfig) -> None:
        self.config = config

    def run_once(self) -> dict[str, object]:
        run_id = _resolve_run_id(required=self.config.required_platform_run_id)
        reporter = PlatformRunReporter.build(
            profile_path=str(self.config.profile_path),
            platform_run_id=run_id,
        )
        payload = reporter.export()
        return {
            "platform_run_id": run_id,
            "ingress_sent": int((payload.get("ingress") or {}).get("sent", 0)),
            "ingress_received": int((payload.get("ingress") or {}).get("received", 0)),
            "rtdl_decision": int((payload.get("rtdl") or {}).get("decision", 0)),
            "case_labels_labels_accepted": int(
                ((payload.get("case_labels") or {}).get("summary") or {}).get("labels_accepted", 0)
            ),
            "report_ref": str(((payload.get("artifact_refs") or {}).get("local_path") or "")),
        }

    def run_forever(self) -> None:
        while True:
            try:
                summary = self.run_once()
                logger.info("platform reporter worker tick: %s", json.dumps(summary, sort_keys=True, ensure_ascii=True))
            except Exception as exc:  # pragma: no cover - defensive loop guard
                logger.exception("platform reporter worker tick failed: %s", str(exc)[:256])
            time.sleep(self.config.poll_seconds)


def load_worker_config(*, profile_path: Path, poll_seconds: float, required_platform_run_id: str | None) -> PlatformRunReporterWorkerConfig:
    profile = Path(profile_path)
    if not profile.exists():
        raise RuntimeError(f"PLATFORM_REPORTER_PROFILE_NOT_FOUND:{profile}")
    poll = max(1.0, float(poll_seconds))
    required = str(required_platform_run_id or "").strip() or None
    return PlatformRunReporterWorkerConfig(
        profile_path=profile,
        poll_seconds=poll,
        required_platform_run_id=required,
    )


def _resolve_run_id(*, required: str | None) -> str:
    explicit = (os.getenv("ACTIVE_PLATFORM_RUN_ID") or os.getenv("PLATFORM_RUN_ID") or "").strip()
    active = str(resolve_platform_run_id(create_if_missing=False) or "").strip()
    run_id = explicit or active
    if required and run_id and run_id != required:
        raise RuntimeError(f"PLATFORM_REPORTER_RUN_SCOPE_MISMATCH:{run_id}:{required}")
    if required and not run_id:
        return required
    if not run_id:
        raise RuntimeError("PLATFORM_REPORTER_RUN_ID_REQUIRED")
    return run_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Platform run reporter worker")
    parser.add_argument("--profile", required=True, help="Platform profile path")
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=float(os.getenv("PLATFORM_RUN_REPORTER_POLL_SECONDS", "10")),
        help="Loop sleep in seconds",
    )
    parser.add_argument(
        "--required-platform-run-id",
        default=os.getenv("PLATFORM_REPORTER_REQUIRED_PLATFORM_RUN_ID"),
        help="Optional strict run scope",
    )
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    worker = PlatformRunReporterWorker(
        load_worker_config(
            profile_path=Path(args.profile),
            poll_seconds=args.poll_seconds,
            required_platform_run_id=args.required_platform_run_id,
        )
    )
    if args.once:
        summary = worker.run_once()
        logger.info("platform reporter worker tick: %s", json.dumps(summary, sort_keys=True, ensure_ascii=True))
        return
    worker.run_forever()


if __name__ == "__main__":
    main()

