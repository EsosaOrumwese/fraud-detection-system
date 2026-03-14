from datetime import datetime, timezone

from scripts.dev_substrate.pr3_wsp_replay_dispatch import measurement_start_boundary


def test_measurement_start_boundary_without_warmup_aligns_to_next_minute() -> None:
    active = datetime(2026, 3, 7, 15, 21, 17, tzinfo=timezone.utc)
    observed = measurement_start_boundary(active, warmup_seconds=0)
    assert observed == datetime(2026, 3, 7, 15, 22, 0, tzinfo=timezone.utc)


def test_measurement_start_boundary_applies_positive_warmup_before_alignment() -> None:
    active = datetime(2026, 3, 7, 15, 21, 17, tzinfo=timezone.utc)
    observed = measurement_start_boundary(active, warmup_seconds=90)
    assert observed == datetime(2026, 3, 7, 15, 23, 0, tzinfo=timezone.utc)


def test_measurement_start_boundary_clamps_negative_warmup() -> None:
    active = datetime(2026, 3, 7, 15, 21, 17, tzinfo=timezone.utc)
    observed = measurement_start_boundary(active, warmup_seconds=-30)
    assert observed == datetime(2026, 3, 7, 15, 22, 0, tzinfo=timezone.utc)
