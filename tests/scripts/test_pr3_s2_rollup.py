from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    path = Path("scripts/dev_substrate/pr3_s2_rollup.py")
    spec = importlib.util.spec_from_file_location("pr3_s2_rollup", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_counter_delta_treats_missing_pre_counter_as_zero() -> None:
    module = _load_module()
    pre = {
        "components": {
            "df": {
                "metrics_payload": {"__missing__": True},
                "summary": {
                    "publish_quarantine_total": None,
                },
            }
        }
    }
    post = {
        "components": {
            "df": {
                "metrics_payload": {
                    "metrics": {
                        "publish_quarantine_total": 0,
                    }
                },
                "summary": {
                    "publish_quarantine_total": 0,
                },
            }
        }
    }

    assert module.counter_delta(pre, post, "df", "publish_quarantine_total") == 0.0


def test_counter_delta_still_fails_closed_when_post_counter_missing() -> None:
    module = _load_module()
    pre = {
        "components": {
            "df": {
                "metrics_payload": {
                    "metrics": {
                        "publish_quarantine_total": 0,
                    }
                },
                "summary": {
                    "publish_quarantine_total": 0,
                },
            }
        }
    }
    post = {
        "components": {
            "df": {
                "metrics_payload": {"__missing__": True},
                "summary": {
                    "publish_quarantine_total": None,
                },
            }
        }
    }

    assert module.counter_delta(pre, post, "df", "publish_quarantine_total") is None


def test_select_attempt_snapshots_filters_historical_reruns() -> None:
    module = _load_module()
    snapshots = [
        {
            "snapshot_label": "pre",
            "platform_run_id": "platform_old",
            "generated_at_utc": "2026-03-07T12:00:00Z",
        },
        {
            "snapshot_label": "pre",
            "platform_run_id": "platform_new",
            "generated_at_utc": "2026-03-07T13:00:00Z",
        },
        {
            "snapshot_label": "during_1",
            "platform_run_id": "platform_new",
            "generated_at_utc": "2026-03-07T13:00:30Z",
        },
        {
            "snapshot_label": "post",
            "platform_run_id": "platform_new",
            "generated_at_utc": "2026-03-07T13:05:00Z",
        },
    ]

    selected, meta = module.select_attempt_snapshots(
        snapshots,
        expected_platform_run_id="platform_new",
    )

    assert [row["snapshot_label"] for row in selected] == ["pre", "during_1", "post"]
    assert meta["excluded_snapshot_count"] == 1
    assert meta["excluded_platform_run_ids"] == ["platform_old"]


def test_select_attempt_snapshots_fails_closed_when_post_missing_for_current_attempt() -> None:
    module = _load_module()
    snapshots = [
        {
            "snapshot_label": "pre",
            "platform_run_id": "platform_new",
            "generated_at_utc": "2026-03-07T13:00:00Z",
        },
        {
            "snapshot_label": "during_1",
            "platform_run_id": "platform_new",
            "generated_at_utc": "2026-03-07T13:00:30Z",
        },
        {
            "snapshot_label": "post",
            "platform_run_id": "platform_old",
            "generated_at_utc": "2026-03-07T12:55:00Z",
        },
    ]

    try:
        module.select_attempt_snapshots(snapshots, expected_platform_run_id="platform_new")
    except RuntimeError as exc:
        assert "PR3.S2.B12_COMPONENT_SNAPSHOT_POST_MISSING" in str(exc)
    else:
        raise AssertionError("expected fail-closed missing-post error")
