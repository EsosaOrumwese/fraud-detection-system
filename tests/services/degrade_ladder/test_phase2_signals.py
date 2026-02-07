from __future__ import annotations

import pytest

from fraud_detection.degrade_ladder.signals import (
    DlSignalError,
    DlSignalSample,
    build_signal_snapshot,
    build_signal_snapshot_from_payloads,
)


def _sample(
    *,
    name: str,
    scope_key: str = "scope=GLOBAL",
    observed_at_utc: str = "2026-02-07T03:00:00.000000Z",
    status: str = "OK",
    value: object = 1,
) -> DlSignalSample:
    return DlSignalSample(
        name=name,
        scope_key=scope_key,
        observed_at_utc=observed_at_utc,
        status=status,
        value=value,
    )


def test_build_snapshot_marks_missing_and_stale_required_signals() -> None:
    snapshot = build_signal_snapshot(
        [
            _sample(name="ofp_health", observed_at_utc="2026-02-07T03:04:10.000000Z"),
            _sample(name="ieg_health", observed_at_utc="2026-02-07T03:01:00.000000Z"),
        ],
        scope_key="scope=GLOBAL",
        decision_time_utc="2026-02-07T03:06:00.000000Z",
        required_signal_names=["ofp_health", "ieg_health", "eb_consumer_lag"],
        optional_signal_names=["control_publish_health"],
        required_max_age_seconds=120,
    )

    assert snapshot.has_required_gaps is True
    assert snapshot.state_by_name("ofp_health").state == "OK"
    assert snapshot.state_by_name("ieg_health").state == "STALE"
    assert snapshot.state_by_name("eb_consumer_lag").state == "MISSING"
    assert snapshot.state_by_name("control_publish_health").required is False


def test_build_snapshot_is_deterministic_for_input_order_and_duplicates() -> None:
    samples_a = [
        _sample(name="ofp_health", observed_at_utc="2026-02-07T03:05:20.000000Z", value={"p95": 250}),
        _sample(name="ofp_health", observed_at_utc="2026-02-07T03:04:20.000000Z", value={"p95": 260}),
        _sample(name="ieg_health", observed_at_utc="2026-02-07T03:05:10.000000Z"),
    ]
    samples_b = list(reversed(samples_a))

    snapshot_a = build_signal_snapshot(
        samples_a,
        scope_key="scope=GLOBAL",
        decision_time_utc="2026-02-07T03:06:00.000000Z",
        required_signal_names=["ofp_health", "ieg_health"],
        required_max_age_seconds=120,
    )
    snapshot_b = build_signal_snapshot(
        samples_b,
        scope_key="scope=GLOBAL",
        decision_time_utc="2026-02-07T03:06:00.000000Z",
        required_signal_names=["ofp_health", "ieg_health"],
        required_max_age_seconds=120,
    )

    assert snapshot_a.snapshot_digest == snapshot_b.snapshot_digest
    assert snapshot_a.state_by_name("ofp_health").value == {"p95": 250}


def test_scope_filtering_is_explicit() -> None:
    snapshot = build_signal_snapshot(
        [
            _sample(name="ofp_health", scope_key="scope=RUN_A", observed_at_utc="2026-02-07T03:05:00.000000Z"),
            _sample(name="ofp_health", scope_key="scope=RUN_B", observed_at_utc="2026-02-07T03:05:30.000000Z"),
        ],
        scope_key="scope=RUN_A",
        decision_time_utc="2026-02-07T03:06:00.000000Z",
        required_signal_names=["ofp_health"],
        required_max_age_seconds=120,
    )
    assert snapshot.state_by_name("ofp_health").observed_at_utc == "2026-02-07T03:05:00.000000Z"


def test_build_signal_snapshot_from_payloads_requires_valid_status() -> None:
    with pytest.raises(DlSignalError):
        build_signal_snapshot_from_payloads(
            [
                {
                    "name": "ofp_health",
                    "scope_key": "scope=GLOBAL",
                    "observed_at_utc": "2026-02-07T03:05:00.000000Z",
                    "status": "warn",
                }
            ],
            scope_key="scope=GLOBAL",
            decision_time_utc="2026-02-07T03:06:00.000000Z",
            required_signal_names=["ofp_health"],
            required_max_age_seconds=120,
        )
