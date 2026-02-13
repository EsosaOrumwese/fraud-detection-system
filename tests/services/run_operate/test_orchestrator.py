from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import yaml

from fraud_detection.run_operate import orchestrator as ro


def _write_pack(path: Path, *, required_run: bool, source_path: Path) -> None:
    payload = {
        "version": 1,
        "pack_id": "test_pack_v0",
        "description": "test pack",
        "active_run": {
            "required": bool(required_run),
            "source_path": str(source_path),
        },
        "defaults": {
            "cwd": ".",
            "env": {"PYTHONUNBUFFERED": "1"},
        },
        "processes": [
            {
                "id": "sleeper",
                "command": [sys.executable, "-c", "import time; time.sleep(30)"],
                "readiness": {"type": "process_alive"},
            }
        ],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_env_file_shell_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env.test"
    env_file.write_text("A=from_file\nB=from_file\n", encoding="utf-8")
    monkeypatch.setenv("B", "from_shell")
    merged = ro._build_environment([str(env_file)])
    assert merged["A"] == "from_file"
    assert merged["B"] == "from_shell"


def test_up_status_down_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ro, "RUNS_ROOT", tmp_path / "runs" / "fraud-platform")
    pack_path = tmp_path / "pack.yaml"
    _write_pack(pack_path, required_run=False, source_path=tmp_path / "ACTIVE_RUN_ID")

    env = dict(os.environ)
    pack = ro.PackSpec.load(pack_path)
    orch = ro.ProcessOrchestrator(pack=pack, env=env)

    up_payload = orch.up()
    assert up_payload["started"] == ["sleeper"]
    state_payload = orch._load_state()
    assert state_payload["active_platform_run_id"] == up_payload["active_platform_run_id"]

    status_payload = orch.status()
    process_row = status_payload["processes"][0]
    assert process_row["process_id"] == "sleeper"
    assert process_row["running"] is True
    assert process_row["readiness"]["ready"] is True

    down_payload = orch.down(timeout_seconds=2.0)
    assert down_payload["stopped"] == ["sleeper"]

    status_after = orch.status()
    process_after = status_after["processes"][0]
    assert process_after["running"] is False
    assert process_after["readiness"]["ready"] is False


def test_required_active_run_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ro, "RUNS_ROOT", tmp_path / "runs" / "fraud-platform")
    pack_path = tmp_path / "pack_required.yaml"
    active_run_path = tmp_path / "ACTIVE_RUN_ID"
    _write_pack(pack_path, required_run=True, source_path=active_run_path)

    env = dict(os.environ)
    env.pop("PLATFORM_RUN_ID", None)
    pack = ro.PackSpec.load(pack_path)
    orch = ro.ProcessOrchestrator(pack=pack, env=env)

    status_payload = orch.status()
    assert status_payload["active_platform_run_id"] is None
    with pytest.raises(RuntimeError, match="ACTIVE_PLATFORM_RUN_ID_MISSING"):
        orch.up()


def test_active_run_resolution_prefers_active_file_over_legacy_platform_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ro, "RUNS_ROOT", tmp_path / "runs" / "fraud-platform")
    pack_path = tmp_path / "pack_precedence.yaml"
    active_run_path = tmp_path / "ACTIVE_RUN_ID"
    active_run_path.write_text("platform_from_active_file\n", encoding="utf-8")
    _write_pack(pack_path, required_run=True, source_path=active_run_path)

    env = dict(os.environ)
    env["PLATFORM_RUN_ID"] = "platform_from_legacy_env"
    pack = ro.PackSpec.load(pack_path)
    orch = ro.ProcessOrchestrator(pack=pack, env=env)

    status_payload = orch.status()
    assert status_payload["active_platform_run_id"] == "platform_from_active_file"


def test_up_requires_restart_when_active_run_changes_with_live_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ro, "RUNS_ROOT", tmp_path / "runs" / "fraud-platform")
    pack_path = tmp_path / "pack_required.yaml"
    active_run_path = tmp_path / "ACTIVE_RUN_ID"
    active_run_path.write_text("platform_run_a\n", encoding="utf-8")
    _write_pack(pack_path, required_run=True, source_path=active_run_path)

    env = dict(os.environ)
    env.pop("PLATFORM_RUN_ID", None)
    pack = ro.PackSpec.load(pack_path)
    orch = ro.ProcessOrchestrator(pack=pack, env=env)

    up_payload = orch.up()
    assert up_payload["started"] == ["sleeper"]
    state_payload = orch._load_state()
    assert state_payload["active_platform_run_id"] == "platform_run_a"

    active_run_path.write_text("platform_run_b\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="ACTIVE_PLATFORM_RUN_ID_MISMATCH_RESTART_REQUIRED"):
        orch.up()

    orch.down(timeout_seconds=2.0)


def test_logs_and_events_are_run_scoped_but_state_status_remain_pack_scoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_root = tmp_path / "runs" / "fraud-platform"
    monkeypatch.setattr(ro, "RUNS_ROOT", runs_root)
    pack_path = tmp_path / "pack_required.yaml"
    active_run_path = tmp_path / "ACTIVE_RUN_ID"
    active_run_path.write_text("platform_run_scoped\n", encoding="utf-8")
    _write_pack(pack_path, required_run=True, source_path=active_run_path)

    env = dict(os.environ)
    env.pop("PLATFORM_RUN_ID", None)
    pack = ro.PackSpec.load(pack_path)
    orch = ro.ProcessOrchestrator(pack=pack, env=env)

    try:
        up_payload = orch.up()
        assert up_payload["active_platform_run_id"] == "platform_run_scoped"

        status_payload = orch.status()
        row = status_payload["processes"][0]
        log_path = Path(row["log_path"])
        assert log_path == (
            runs_root
            / "platform_run_scoped"
            / "operate"
            / "test_pack_v0"
            / "logs"
            / "sleeper.log"
        )
        assert log_path.exists()

        # Operator control surfaces stay pack-scoped.
        assert (runs_root / "operate" / "test_pack_v0" / "state.json").exists()
        assert (runs_root / "operate" / "test_pack_v0" / "status" / "last_status.json").exists()

        # Events move to run scope with active run id.
        run_events = runs_root / "platform_run_scoped" / "operate" / "test_pack_v0" / "events.jsonl"
        assert run_events.exists()
        legacy_events = runs_root / "operate" / "test_pack_v0" / "events.jsonl"
        assert not legacy_events.exists()
    finally:
        orch.down(timeout_seconds=2.0)
