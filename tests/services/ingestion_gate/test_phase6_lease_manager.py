from fraud_detection.ingestion_gate.leases import NullReadyLeaseManager


def test_null_lease_manager_acquires() -> None:
    manager = NullReadyLeaseManager(owner_id="tester")
    lease = manager.try_acquire("msg-1", "run-1")
    assert lease is not None
    assert lease.backend == "none"
    lease.release()
