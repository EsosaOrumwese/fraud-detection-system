from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from engine.cli import segment1b as cli

@pytest.fixture()
def tmp_dictionary(tmp_path: Path) -> Path:
    path = tmp_path / "dictionary.yaml"
    path.write_text("{}", encoding="utf-8")
    return path



@pytest.fixture()
def stub_orchestrator(monkeypatch: pytest.MonkeyPatch):
    def _run(config):
        return SimpleNamespace(
            s0_receipt_path=None,
            s1=SimpleNamespace(
                tile_index_path=Path("/tmp/tile_index"),
                tile_bounds_path=Path("/tmp/tile_bounds"),
                report_path=Path("/tmp/s1_report.json"),
            ),
            s2=SimpleNamespace(
                tile_weights_path=Path("/tmp/tile_weights"),
                report_path=Path("/tmp/s2_report.json"),
                country_summary_path=Path("/tmp/s2_summary.jsonl"),
            ),
        )

    monkeypatch.setattr(cli, "Segment1BOrchestrator", lambda: SimpleNamespace(run=_run))


def test_segment1b_cli_run(monkeypatch: pytest.MonkeyPatch, stub_orchestrator, tmp_dictionary):
    output_file = tmp_dictionary

    args = [
        "run",
        "--data-root",
        ".",
        "--parameter-hash",
        "abc123",
        "--dictionary",
        str(output_file),
        "--skip-s0",
    ]

    exit_code = cli.main(args)
    assert exit_code == 0


def test_segment1b_cli_outputs(monkeypatch: pytest.MonkeyPatch, stub_orchestrator, capsys, tmp_dictionary):
    exit_code = cli.main(
        [
            "run",
            "--data-root",
            ".",
            "--parameter-hash",
            "abc123",
            "--skip-s0",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert Path(payload["s2"]["tile_weights_path"]) == Path("/tmp/tile_weights")