from __future__ import annotations

from pathlib import Path

from fraud_detection.decision_log_audit.config import load_intake_policy
from fraud_detection.decision_log_audit.worker import load_worker_config


def test_dla_policy_is_pinned_to_rtdl_topic() -> None:
    policy = load_intake_policy(Path("config/platform/dla/intake_policy_v0.yaml"))
    assert policy.admitted_topics == ("fp.bus.rtdl.v1",)


def test_dla_load_worker_config_resolves_nested_run_scope_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ACTIVE_PLATFORM_RUN_ID", "platform_20260308T141818Z")
    monkeypatch.setenv("DLA_INDEX_DSN", str(tmp_path / "dla.sqlite"))
    profile = tmp_path / "dev_full.yaml"
    profile.write_text(
        "\n".join(
            [
                "profile_id: dev_full",
                "dla:",
                "  policy:",
                "    intake_policy_ref: config/platform/dla/intake_policy_v0.yaml",
                "    storage_policy_ref: config/platform/dla/storage_policy_v0.yaml",
                "    storage_profile_id: prod",
                "  wiring:",
                "    required_platform_run_id: ${DLA_REQUIRED_PLATFORM_RUN_ID:-${ACTIVE_PLATFORM_RUN_ID:-}}",
                "    index_locator: ${DLA_INDEX_DSN}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = load_worker_config(profile)

    assert config.required_platform_run_id == "platform_20260308T141818Z"
