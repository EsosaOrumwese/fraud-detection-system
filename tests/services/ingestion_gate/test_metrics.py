import threading
import time

from fraud_detection.ingestion_gate.metrics import MetricsRecorder


def test_flush_if_due_is_safe_under_concurrent_latency_recording() -> None:
    recorder = MetricsRecorder(flush_interval_seconds=0)
    recorder.record_decision("ADMIT")
    recorder.record_latency("phase.publish_seconds", 0.01)

    stop = threading.Event()
    errors: list[BaseException] = []

    def writer() -> None:
        try:
            while not stop.is_set():
                recorder.record_latency("phase.publish_seconds", 0.02)
                recorder.record_decision("ADMIT")
        except BaseException as exc:  # pragma: no cover - defensive capture for concurrent failures
            errors.append(exc)
            stop.set()

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        deadline = time.time() + 0.2
        while time.time() < deadline and not errors:
            recorder.flush_if_due({"platform_run_id": "platform_test"})
    finally:
        stop.set()
        thread.join(timeout=1.0)

    assert not errors
