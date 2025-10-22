from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from engine.layers.l1.seg_1B import S1RunResult, S2RunResult
from engine.scenario_runner.l1_seg_1B import (
    Segment1BConfig,
    Segment1BOrchestrator,
)


class StubS0Runner:
    def __init__(self) -> None:
        self.inputs = None

    def run(self, inputs):
        self.inputs = inputs
        return SimpleNamespace(receipt_path=inputs.base_path / "receipt.json")


class StubS1Runner:
    def __init__(self) -> None:
        self.config = None

    def run(self, config):
        self.config = config
        base = config.data_root
        return S1RunResult(
            tile_index_path=base / "tile_index",
            tile_bounds_path=base / "tile_bounds",
            report_path=base / "s1_report.json",
            country_summary_path=base / "s1_summary.jsonl",
            rows_emitted=3,
        )


class StubS2Runner:
    def __init__(self) -> None:
        self.prepared = None
        self.quantised = None
        self.measure_calls = 0

    def prepare(self, config):
        self.prepared = SimpleNamespace(
            data_root=config.data_root,
            governed=SimpleNamespace(basis=config.basis, dp=config.dp),
            dictionary=config.dictionary,
            tile_index=SimpleNamespace(parameter_hash=config.parameter_hash),
            pat=self._stub_pat(),
        )
        return self.prepared

    def _stub_pat(self):
        from engine.layers.l1.seg_1B import PatCounters

        return PatCounters()

    def compute_masses(self, prepared):
        return object()

    def measure_baselines(self, prepared, measure_raster: bool = False):
        self.measure_calls += 1

    def quantise(self, prepared, masses):
        self.quantised = SimpleNamespace(frame=None, summaries=[])
        prepared.pat.rows_emitted = 3
        return self.quantised

    def materialise(self, prepared, quantised):
        prepared.pat.validate_envelope()
        base = prepared.data_root
        return S2RunResult(
            tile_weights_path=base / "tile_weights",
            report_path=base / "s2_report.json",
            country_summary_path=base / "s2_summary.jsonl",
            determinism_receipt={"partition_path": "dummy", "sha256_hex": "deadbeef"},
        )


def test_orchestrator_runs_all_states(tmp_path: Path):
    orchestrator = Segment1BOrchestrator()
    orchestrator._s0_runner = StubS0Runner()
    orchestrator._s1_runner = StubS1Runner()
    orchestrator._s2_runner = StubS2Runner()

    dictionary = {"datasets": {}}

    result = orchestrator.run(
        Segment1BConfig(
            data_root=tmp_path,
            parameter_hash="abc123",
            dictionary=dictionary,
            basis="uniform",
            dp=2,
            manifest_fingerprint="ff" * 32,
            seed="123",
        )
    )

    assert result.s0_receipt_path == tmp_path / "receipt.json"
    assert result.s1.tile_index_path == tmp_path / "tile_index"
    assert result.s2.tile_weights_path == tmp_path / "tile_weights"
    assert orchestrator._s2_runner.measure_calls == 1


def test_orchestrator_skip_s0(tmp_path: Path):
    orchestrator = Segment1BOrchestrator()
    stub_s0 = StubS0Runner()
    orchestrator._s0_runner = stub_s0
    orchestrator._s1_runner = StubS1Runner()
    orchestrator._s2_runner = StubS2Runner()

    result = orchestrator.run(
        Segment1BConfig(
            data_root=tmp_path,
            parameter_hash="hash",
            dictionary={"datasets": {}},
            basis="uniform",
            dp=2,
            skip_s0=True,
        )
    )

    assert result.s0_receipt_path is None
    assert stub_s0.inputs is None

