from fraud_detection.ingestion_gate.retry import with_retry


def test_with_retry_succeeds_after_failures() -> None:
    attempts: list[str] = []

    def _fn() -> str:
        attempts.append("x")
        if len(attempts) < 3:
            raise ValueError("not yet")
        return "ok"

    result = with_retry(_fn, attempts=3, base_delay_seconds=0.0, max_delay_seconds=0.0)
    assert result == "ok"
    assert len(attempts) == 3
