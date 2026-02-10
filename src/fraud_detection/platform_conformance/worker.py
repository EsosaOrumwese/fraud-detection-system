"""Environment conformance worker CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import time

from fraud_detection.platform_runtime import RUNS_ROOT, resolve_platform_run_id

from .checker import run_environment_conformance


logger = logging.getLogger("fraud_detection.platform_conformance.worker")


@dataclass(frozen=True)
class PlatformConformanceWorkerConfig:
    local_parity_profile: Path
    dev_profile: Path
    prod_profile: Path
    poll_seconds: float
    required_platform_run_id: str | None = None


class PlatformConformanceWorker:
    def __init__(self, config: PlatformConformanceWorkerConfig) -> None:
        self.config = config

    def run_once(self) -> dict[str, object]:
        run_id = _resolve_run_id(required=self.config.required_platform_run_id)
        output_path = RUNS_ROOT / run_id / "obs" / "environment_conformance.json"
        result = run_environment_conformance(
            local_parity_profile=str(self.config.local_parity_profile),
            dev_profile=str(self.config.dev_profile),
            prod_profile=str(self.config.prod_profile),
            platform_run_id=run_id,
            output_path=str(output_path),
        )
        return {
            "platform_run_id": run_id,
            "status": result.status,
            "artifact_path": result.artifact_path,
        }

    def run_forever(self) -> None:
        while True:
            try:
                summary = self.run_once()
                logger.info("platform conformance worker tick: %s", json.dumps(summary, sort_keys=True, ensure_ascii=True))
            except Exception as exc:  # pragma: no cover - defensive loop guard
                logger.exception("platform conformance worker tick failed: %s", str(exc)[:256])
            time.sleep(self.config.poll_seconds)


def load_worker_config(
    *,
    local_parity_profile: Path,
    dev_profile: Path,
    prod_profile: Path,
    poll_seconds: float,
    required_platform_run_id: str | None,
) -> PlatformConformanceWorkerConfig:
    for path in (local_parity_profile, dev_profile, prod_profile):
        if not Path(path).exists():
            raise RuntimeError(f"PLATFORM_CONFORMANCE_PROFILE_NOT_FOUND:{path}")
    poll = max(5.0, float(poll_seconds))
    required = str(required_platform_run_id or "").strip() or None
    return PlatformConformanceWorkerConfig(
        local_parity_profile=Path(local_parity_profile),
        dev_profile=Path(dev_profile),
        prod_profile=Path(prod_profile),
        poll_seconds=poll,
        required_platform_run_id=required,
    )


def _resolve_run_id(*, required: str | None) -> str:
    explicit = (os.getenv("ACTIVE_PLATFORM_RUN_ID") or os.getenv("PLATFORM_RUN_ID") or "").strip()
    active = str(resolve_platform_run_id(create_if_missing=False) or "").strip()
    run_id = explicit or active
    if required and run_id and run_id != required:
        raise RuntimeError(f"PLATFORM_CONFORMANCE_RUN_SCOPE_MISMATCH:{run_id}:{required}")
    if required and not run_id:
        return required
    if not run_id:
        raise RuntimeError("PLATFORM_CONFORMANCE_RUN_ID_REQUIRED")
    return run_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Platform environment conformance worker")
    parser.add_argument(
        "--local-parity-profile",
        default=os.getenv("PLATFORM_CONFORMANCE_LOCAL_PARITY_PROFILE", "config/platform/profiles/local_parity.yaml"),
    )
    parser.add_argument(
        "--dev-profile",
        default=os.getenv("PLATFORM_CONFORMANCE_DEV_PROFILE", "config/platform/profiles/dev.yaml"),
    )
    parser.add_argument(
        "--prod-profile",
        default=os.getenv("PLATFORM_CONFORMANCE_PROD_PROFILE", "config/platform/profiles/prod.yaml"),
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=float(os.getenv("PLATFORM_CONFORMANCE_POLL_SECONDS", "30")),
        help="Loop sleep in seconds",
    )
    parser.add_argument(
        "--required-platform-run-id",
        default=os.getenv("PLATFORM_CONFORMANCE_REQUIRED_PLATFORM_RUN_ID"),
        help="Optional strict run scope",
    )
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    worker = PlatformConformanceWorker(
        load_worker_config(
            local_parity_profile=Path(args.local_parity_profile),
            dev_profile=Path(args.dev_profile),
            prod_profile=Path(args.prod_profile),
            poll_seconds=args.poll_seconds,
            required_platform_run_id=args.required_platform_run_id,
        )
    )
    if args.once:
        summary = worker.run_once()
        logger.info("platform conformance worker tick: %s", json.dumps(summary, sort_keys=True, ensure_ascii=True))
        return
    worker.run_forever()


if __name__ == "__main__":
    main()

