"""MF Phase 2 run-control wrapper over durable run ledger."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import MfTrainBuildRequest
from .run_ledger import (
    MF_EXECUTION_FULL,
    MF_EXECUTION_PUBLISH_ONLY,
    MF_RETRY_ALLOWED,
    MF_RETRY_EXHAUSTED,
    MF_RETRY_NOT_PENDING,
    MfPublishRetryDecision,
    MfRunLedger,
    MfRunLedgerError,
    MfRunReceipt,
    MfRunSubmission,
)


@dataclass(frozen=True)
class MfRunControlPolicy:
    max_publish_retry_attempts: int = 3

    def __post_init__(self) -> None:
        if int(self.max_publish_retry_attempts) < 1:
            raise ValueError("max_publish_retry_attempts must be >= 1")


class MfRunControl:
    """Controls MF run transitions with bounded publish-only retry posture."""

    def __init__(self, *, ledger: MfRunLedger, policy: MfRunControlPolicy | None = None) -> None:
        self.ledger = ledger
        self.policy = policy or MfRunControlPolicy()

    def enqueue(self, *, request: MfTrainBuildRequest, queued_at_utc: str) -> MfRunSubmission:
        return self.ledger.submit_request(request=request, queued_at_utc=queued_at_utc)

    def start_full_run(self, *, run_key: str, started_at_utc: str) -> MfRunReceipt:
        return self.ledger.start_run(run_key=run_key, started_at_utc=started_at_utc, mode=MF_EXECUTION_FULL)

    def mark_eval_ready(self, *, run_key: str, eval_ready_at_utc: str, eval_report_ref: str | None = None) -> MfRunReceipt:
        return self.ledger.mark_eval_ready(
            run_key=run_key,
            eval_ready_at_utc=eval_ready_at_utc,
            eval_report_ref=eval_report_ref,
        )

    def mark_pass(self, *, run_key: str, passed_at_utc: str, gate_receipt_ref: str) -> MfRunReceipt:
        return self.ledger.mark_pass(
            run_key=run_key,
            passed_at_utc=passed_at_utc,
            gate_receipt_ref=gate_receipt_ref,
        )

    def mark_publish_pending(self, *, run_key: str, pending_at_utc: str, reason_code: str) -> MfRunReceipt:
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
    ) -> tuple[MfRunReceipt, MfPublishRetryDecision]:
        decision = self.ledger.request_publish_retry(
            run_key=run_key,
            requested_at_utc=requested_at_utc,
            max_attempts=int(self.policy.max_publish_retry_attempts),
        )
        if decision.decision == MF_RETRY_ALLOWED:
            receipt = self.ledger.start_run(
                run_key=run_key,
                started_at_utc=started_at_utc,
                mode=MF_EXECUTION_PUBLISH_ONLY,
            )
            return receipt, decision
        if decision.decision == MF_RETRY_EXHAUSTED:
            raise MfRunLedgerError(
                "PUBLISH_RETRY_EXHAUSTED",
                f"publish retry budget exhausted for run_key={run_key}",
            )
        if decision.decision == MF_RETRY_NOT_PENDING:
            raise MfRunLedgerError(
                "RETRY_NOT_PENDING",
                f"run_key={run_key} is not in PUBLISH_PENDING state",
            )
        raise MfRunLedgerError("UNKNOWN_RETRY_DECISION", f"unexpected retry decision: {decision.decision}")

    def mark_published(self, *, run_key: str, published_at_utc: str, bundle_publication_ref: str) -> MfRunReceipt:
        return self.ledger.mark_published(
            run_key=run_key,
            published_at_utc=published_at_utc,
            bundle_publication_ref=bundle_publication_ref,
        )

    def mark_failed(self, *, run_key: str, failed_at_utc: str, reason_code: str) -> MfRunReceipt:
        return self.ledger.mark_failed(run_key=run_key, failed_at_utc=failed_at_utc, reason_code=reason_code)

