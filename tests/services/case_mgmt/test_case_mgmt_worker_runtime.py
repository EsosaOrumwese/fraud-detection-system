from __future__ import annotations

from pathlib import Path

from fraud_detection.case_mgmt.worker import load_worker_config


def test_case_mgmt_load_worker_config_resolves_nested_run_scope_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ACTIVE_PLATFORM_RUN_ID", "platform_20260308T141818Z")
    profile = tmp_path / "dev_full.yaml"
    profile.write_text(
        "\n".join(
            [
                "profile_id: dev_full",
                "wiring:",
                "  event_bus_kind: kafka",
                "case_mgmt:",
                "  policy: {}",
                "  wiring:",
                "    locator: " + str(tmp_path / "case_mgmt.sqlite"),
                "    label_store_locator: " + str(tmp_path / "label_store.sqlite"),
                "    required_platform_run_id: ${CASE_MGMT_REQUIRED_PLATFORM_RUN_ID:-${ACTIVE_PLATFORM_RUN_ID:-}}",
                "    scenario_run_id: ${ACTIVE_SCENARIO_RUN_ID:-" + "1" * 32 + "}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = load_worker_config(profile)

    assert config.required_platform_run_id == "platform_20260308T141818Z"
