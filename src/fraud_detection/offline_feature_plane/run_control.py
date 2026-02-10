"""OFS Phase 2 run-control wrapper over the durable run ledger."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import OfsBuildIntent
from .run_ledger import (
    OFS_EXECUTION_FULL,
    OFS_EXECUTION_PUBLISH_ONLY,
    OFS_RETRY_ALLOWED,
    OFS_RETRY_EXHAUSTED,
    OFS_RETRY_NOT_PENDING,
    OfsPublishRetryDecision,
    OfsRunLedger,
    OfsRunLedgerError,
    OfsRunReceipt,
    OfsRunSubmission,
)


@dataclass(frozen=True)
class OfsRunControlPolicy:
    max_publish_retry_attempts: int = 3

    def __post_init__(self) -> None:
        if int(self.max_publish_retry_attempts) < 1:
            raise ValueError("max_publish_retry_attempts must be >= 1")


class OfsRunControl:
    """Controls OFS run transitions with bounded publish-only retry posture."""

    def __init__(self, *, ledger: OfsRunLedger, policy: OfsRunControlPolicy | None = None) -> None:
        self.ledger = ledger
        self.policy = policy or OfsRunControlPolicy()

    def enqueue(self, *, intent: OfsBuildIntent, queued_at_utc: str) -> OfsRunSubmission:
        return self.ledger.submit_intent(intent=intent, queued_at_utc=queued_at_utc)

    def start_full_run(self, *, run_key: str, started_at_utc: str) -> OfsRunReceipt:
        return self.ledger.start_run(run_key=run_key, started_at_utc=started_at_utc, mode=OFS_EXECUTION_FULL)

    def mark_publish_pending(self, *, run_key: str, pending_at_utc: str, reason_code: str) -> OfsRunReceipt:
        return self.ledger.mark_publish_pending(
            run_key=run_key,
            pending_at_utc=pending_at_utc,
            reason_code=reason_code,
        )

    def start_publish_retry(
        self,
        *,
        run_key: str,
        requested_at_utc: str,
        started_at_utc: str,
    ) -> tuple[OfsRunReceipt, OfsPublishRetryDecision]:
        decision = self.ledger.request_publish_retry(
            run_key=run_key,
            requested_at_utc=requested_at_utc,
            max_attempts=int(self.policy.max_publish_retry_attempts),
        )
        if decision.decision == OFS_RETRY_ALLOWED:
            receipt = self.ledger.start_run(
                run_key=run_key,
                started_at_utc=started_at_utc,
                mode=OFS_EXECUTION_PUBLISH_ONLY,
            )
            return receipt, decision
        if decision.decision == OFS_RETRY_EXHAUSTED:
            raise OfsRunLedgerError(
                "PUBLISH_RETRY_EXHAUSTED",
                f"publish retry budget exhausted for run_key={run_key}",
            )
        if decision.decision == OFS_RETRY_NOT_PENDING:
            raise OfsRunLedgerError(
                "RETRY_NOT_PENDING",
                f"run_key={run_key} is not in PUBLISH_PENDING state",
            )
        raise OfsRunLedgerError("UNKNOWN_RETRY_DECISION", f"unexpected retry decision: {decision.decision}")

    def mark_done(self, *, run_key: str, completed_at_utc: str, result_ref: str | None = None) -> OfsRunReceipt:
        return self.ledger.mark_done(run_key=run_key, completed_at_utc=completed_at_utc, result_ref=result_ref)

    def mark_failed(self, *, run_key: str, failed_at_utc: str, reason_code: str) -> OfsRunReceipt:
        return self.ledger.mark_failed(run_key=run_key, failed_at_utc=failed_at_utc, reason_code=reason_code)
