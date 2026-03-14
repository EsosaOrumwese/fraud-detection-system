from datetime import datetime, timezone

from scripts.dev_substrate.pr3_s3_rollup import select_counter_window_bounds, sustained_green_start


def _ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_sustained_green_start_requires_later_rows_to_stay_green() -> None:
    rows = [
        {"window_end_utc": "2026-03-08T02:01:00Z", "pass": False},
        {"window_end_utc": "2026-03-08T02:02:00Z", "pass": True},
        {"window_end_utc": "2026-03-08T02:03:00Z", "pass": False},
        {"window_end_utc": "2026-03-08T02:04:00Z", "pass": True},
        {"window_end_utc": "2026-03-08T02:05:00Z", "pass": True},
    ]

    assert sustained_green_start(rows, pass_key="pass", stable_time_key="window_end_utc") == "2026-03-08T02:04:00Z"


def test_select_counter_window_bounds_prefers_measurement_boundaries() -> None:
    snapshots = [
        {"snapshot_label": "pre", "generated_at_utc": "2026-03-08T02:00:10Z"},
        {"snapshot_label": "during_1", "generated_at_utc": "2026-03-08T02:01:20Z"},
        {"snapshot_label": "during_2", "generated_at_utc": "2026-03-08T02:02:25Z"},
        {"snapshot_label": "post", "generated_at_utc": "2026-03-08T02:04:10Z"},
    ]

    baseline, window_end, meta = select_counter_window_bounds(
        snapshots,
        measurement_start_utc=_ts("2026-03-08T02:01:30Z"),
        measurement_end_utc=_ts("2026-03-08T02:03:30Z"),
    )

    assert baseline["snapshot_label"] == "during_1"
    assert window_end["snapshot_label"] == "during_2"
    assert meta["baseline_selection_mode"] == "latest_at_or_before_measurement_start"
    assert meta["window_end_selection_mode"] == "latest_at_or_before_measurement_end"
