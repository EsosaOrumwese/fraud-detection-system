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
            s3=SimpleNamespace(
                requirements_path=Path("/tmp/s3_requirements"),
                report_path=Path("/tmp/s3_report.json"),
                determinism_receipt={"partition_path": "/tmp/s3_requirements", "sha256_hex": "deadbeef"},
                rows_emitted=3,
                merchants_total=2,
                countries_total=2,
                source_rows_total=5,
            ),
        )

    monkeypatch.setattr(cli, "Segment1BOrchestrator", lambda: SimpleNamespace(run=_run))


@pytest.fixture()
def stub_s3_validator(monkeypatch: pytest.MonkeyPatch):
    class _StubValidator:
        def __init__(self) -> None:
            self.calls = []

        def validate(self, config):
            self.calls.append(config)

    validator = _StubValidator()
    monkeypatch.setattr(cli, "S3RequirementsValidator", lambda: validator)
    return validator


def test_segment1b_cli_run(monkeypatch: pytest.MonkeyPatch, stub_orchestrator, tmp_dictionary):
    args = [
        "run",
        "--data-root",
        ".",
        "--parameter-hash",
        "abc123",
        "--dictionary",
        str(tmp_dictionary),
        "--manifest-fingerprint",
        "f" * 64,
        "--seed",
        "123",
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
            "--manifest-fingerprint",
            "f" * 64,
            "--seed",
            "123",
            "--skip-s0",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert Path(payload["s2"]["tile_weights_path"]) == Path("/tmp/tile_weights")
    assert Path(payload["s3"]["requirements_path"]) == Path("/tmp/s3_requirements")


def test_segment1b_cli_validate_s3(monkeypatch: pytest.MonkeyPatch, stub_s3_validator, tmp_dictionary):
    exit_code = cli.main(
        [
            "validate-s3",
            "--data-root",
            ".",
            "--parameter-hash",
            "abc123",
            "--seed",
            "123",
            "--manifest-fingerprint",
            "f" * 64,
            "--dictionary",
            str(tmp_dictionary),
        ]
    )
    assert exit_code == 0
    assert len(stub_s3_validator.calls) == 1

