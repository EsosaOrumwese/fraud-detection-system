"""Platform run reporter worker CLI."""

from __future__ import annotations

from contextlib import contextmanager
import argparse
from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import time

from fraud_detection.ingestion_gate.config import WiringProfile
from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn
from fraud_detection.postgres_runtime import postgres_threadlocal_connection
from fraud_detection.platform_runtime import resolve_platform_run_id

from .run_reporter import PlatformRunReporter


logger = logging.getLogger("fraud_detection.platform_reporter.worker")


@dataclass(frozen=True)
class PlatformRunReporterWorkerConfig:
    profile_path: Path
    poll_seconds: float
    required_platform_run_id: str | None = None
    lock_backend: str = "db_advisory_lock"
    lock_key_pattern: str = "reporter:{platform_run_id}"


class PlatformRunReporterWorker:
    def __init__(self, config: PlatformRunReporterWorkerConfig) -> None:
        self.config = config

    def run_once(self) -> dict[str, object]:
        run_id = _resolve_run_id(required=self.config.required_platform_run_id)
        with _single_writer_lock(
            profile_path=self.config.profile_path,
            run_id=run_id,
            lock_backend=self.config.lock_backend,
            lock_key_pattern=self.config.lock_key_pattern,
        ):
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
    lock_backend = str(os.getenv("REPORTER_LOCK_BACKEND") or "db_advisory_lock").strip().lower()
    lock_key_pattern = str(os.getenv("REPORTER_LOCK_KEY_PATTERN") or "reporter:{platform_run_id}").strip()
    return PlatformRunReporterWorkerConfig(
        profile_path=profile,
        poll_seconds=poll,
        required_platform_run_id=required,
        lock_backend=lock_backend,
        lock_key_pattern=lock_key_pattern,
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


def _resolve_lock_dsn(*, profile_path: Path) -> str:
    dsn = str(os.getenv("IG_ADMISSION_DSN") or "").strip()
    if dsn:
        return dsn
    profile = WiringProfile.load(profile_path)
    return str(profile.admission_db_path or "").strip()


def _render_lock_key(*, pattern: str, run_id: str) -> str:
    rendered = pattern.replace("{platform_run_id}", run_id).strip()
    if "{platform_run_id}" not in pattern:
        raise RuntimeError("REPORTER_LOCK_KEY_PATTERN_MISSING_PLATFORM_RUN_ID_TOKEN")
    if not rendered or "{" in rendered or "}" in rendered:
        raise RuntimeError("REPORTER_LOCK_KEY_PATTERN_RENDER_FAILED")
    return rendered


def _lock_id_from_key(key: str) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    # Map deterministic key to signed 64-bit Postgres advisory lock id.
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


@contextmanager
def _single_writer_lock(*, profile_path: Path, run_id: str, lock_backend: str, lock_key_pattern: str):
    backend = str(lock_backend or "").strip().lower()
    if backend in {"", "none", "disabled"}:
        logger.info("platform reporter lock disabled by backend=%s", backend or "empty")
        yield
        return
    if backend not in {"db_advisory_lock", "aurora_advisory_lock"}:
        raise RuntimeError(f"REPORTER_LOCK_BACKEND_UNSUPPORTED:{backend}")
    if backend == "aurora_advisory_lock":
        logger.info("platform reporter lock backend alias applied backend=%s -> db_advisory_lock", backend)

    dsn = _resolve_lock_dsn(profile_path=profile_path)
    if not dsn:
        raise RuntimeError("REPORTER_LOCK_DSN_REQUIRED")
    if not is_postgres_dsn(dsn):
        raise RuntimeError("REPORTER_LOCK_DSN_NOT_POSTGRES")

    lock_key = _render_lock_key(pattern=lock_key_pattern, run_id=run_id)
    lock_id = _lock_id_from_key(lock_key)

    with postgres_threadlocal_connection(dsn) as conn:
        logger.info(
            "platform reporter lock attempt backend=%s lock_key=%s lock_id=%s run_id=%s",
            backend,
            lock_key,
            lock_id,
            run_id,
        )
        acquired = bool(conn.execute("SELECT pg_try_advisory_lock(%s)", (lock_id,)).fetchone()[0])
        if not acquired:
            logger.error(
                "platform reporter lock denied backend=%s lock_key=%s lock_id=%s run_id=%s",
                backend,
                lock_key,
                lock_id,
                run_id,
            )
            raise RuntimeError(f"REPORTER_LOCK_NOT_ACQUIRED:{lock_key}")
        logger.info(
            "platform reporter lock acquired backend=%s lock_key=%s lock_id=%s run_id=%s",
            backend,
            lock_key,
            lock_id,
            run_id,
        )
        try:
            yield
        finally:
            released = bool(conn.execute("SELECT pg_advisory_unlock(%s)", (lock_id,)).fetchone()[0])
            if released:
                logger.info(
                    "platform reporter lock released backend=%s lock_key=%s lock_id=%s run_id=%s",
                    backend,
                    lock_key,
                    lock_id,
                    run_id,
                )
            else:
                logger.warning(
                    "platform reporter lock release returned false backend=%s lock_key=%s lock_id=%s run_id=%s",
                    backend,
                    lock_key,
                    lock_id,
                    run_id,
                )


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
