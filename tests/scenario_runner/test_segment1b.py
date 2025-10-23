from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import polars as pl
import pytest

from engine.layers.l1.seg_1B import (
    S1RunResult,
    S2RunResult,
    S3AggregationResult,
    S3RunResult,
    S4RunResult,
    S5RunResult,
    S6RunResult,
)
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


class StubS3Runner:
    def __init__(self) -> None:
        self.config = None
        self.prepared = None
        self.aggregation = None
        self.materialise_calls = 0

    def prepare(self, config):
        self.config = config
        empty_frame = pl.DataFrame(
            {
                "merchant_id": pl.Series([], dtype=pl.Int64),
                "legal_country_iso": pl.Series([], dtype=pl.Utf8),
                "site_order": pl.Series([], dtype=pl.Int64),
                "manifest_fingerprint": pl.Series([], dtype=pl.Utf8),
            }
        )
        self.prepared = SimpleNamespace(
            config=config,
            dictionary=config.dictionary,
            receipt=SimpleNamespace(payload={}, flag_sha256_hex="hash"),
            outlet_catalogue=SimpleNamespace(frame=empty_frame),
            tile_weights=SimpleNamespace(frame=pl.DataFrame({"country_iso": [], "tile_id": []})),
            iso_table=SimpleNamespace(codes=frozenset()),
        )
        return self.prepared

    def aggregate(self, prepared):
        frame = pl.DataFrame({"merchant_id": [], "legal_country_iso": [], "n_sites": []})
        self.aggregation = S3AggregationResult(frame=frame, source_rows_total=0)
        return self.aggregation

    def materialise(self, prepared, aggregation):
        self.materialise_calls += 1
        base = prepared.config.data_root
        return S3RunResult(
            requirements_path=base / "s3_requirements",
            report_path=base / "s3_report.json",
            determinism_receipt={"partition_path": "dummy", "sha256_hex": "deadbeef"},
            rows_emitted=aggregation.rows_emitted,
            merchants_total=aggregation.merchants_total,
            countries_total=aggregation.countries_total,
            source_rows_total=aggregation.source_rows_total,
        )


class StubS4Runner:
    def __init__(self) -> None:
        self.config = None

    def run(self, config):
        self.config = config
        base = config.data_root
        return S4RunResult(
            alloc_plan_path=base / "s4_alloc_plan",
            report_path=base / "s4_report.json",
            determinism_receipt={"partition_path": "dummy", "sha256_hex": "cafebabe"},
            rows_emitted=0,
            pairs_total=0,
            merchants_total=0,
            shortfall_total=0,
            ties_broken_total=0,
            alloc_sum_equals_requirements=True,
        )


class StubS5Runner:
    def __init__(self) -> None:
        self.config = None

    def run(self, config):
        self.config = config
        base = config.data_root
        return S5RunResult(
            dataset_path=base / "s5_site_tile_assignment",
            rng_log_path=base / "logs" / "site_tile_assign",
            run_report_path=base / "s5_run_report.json",
            determinism_receipt={"partition_path": "dummy", "sha256_hex": "feedface"},
            rows_emitted=4,
            pairs_total=2,
            rng_events_emitted=4,
            run_id="abcd1234ef567890abcd1234ef567890",
        )


class StubS6Runner:
    def __init__(self) -> None:
        self.config = None

    def run(self, config):
        self.config = config
        base = config.data_root
        return S6RunResult(
            dataset_path=base / "s6_site_jitter",
            rng_log_path=base / "logs" / "in_cell_jitter",
            run_report_path=base / "s6_run_report.json",
            determinism_receipt={"partition_path": "dummy", "sha256_hex": "beadfeed"},
            rows_emitted=4,
            rng_events_total=6,
            counter_span=6,
            run_id="bcd1234ef567890abcd1234ef5678901",
        )


def test_orchestrator_runs_all_states(tmp_path: Path):
    orchestrator = Segment1BOrchestrator()
    orchestrator._s0_runner = StubS0Runner()
    orchestrator._s1_runner = StubS1Runner()
    orchestrator._s2_runner = StubS2Runner()
    orchestrator._s3_runner = StubS3Runner()
    orchestrator._s4_runner = StubS4Runner()
    orchestrator._s5_runner = StubS5Runner()
    orchestrator._s6_runner = StubS6Runner()

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
    assert result.s3.requirements_path == tmp_path / "s3_requirements"
    assert result.s4.alloc_plan_path == tmp_path / "s4_alloc_plan"
    assert result.s6.dataset_path == tmp_path / "s6_site_jitter"
    assert result.s5.dataset_path == tmp_path / "s5_site_tile_assignment"
    assert orchestrator._s2_runner.measure_calls == 1
    assert orchestrator._s3_runner.materialise_calls == 1


def test_orchestrator_skip_s0(tmp_path: Path):
    orchestrator = Segment1BOrchestrator()
    stub_s0 = StubS0Runner()
    orchestrator._s0_runner = stub_s0
    orchestrator._s1_runner = StubS1Runner()
    orchestrator._s2_runner = StubS2Runner()
    orchestrator._s3_runner = StubS3Runner()
    orchestrator._s4_runner = StubS4Runner()
    orchestrator._s5_runner = StubS5Runner()
    orchestrator._s6_runner = StubS6Runner()

    result = orchestrator.run(
        Segment1BConfig(
            data_root=tmp_path,
            parameter_hash="hash",
            dictionary={"datasets": {}},
            basis="uniform",
            dp=2,
            skip_s0=True,
            manifest_fingerprint="aa" * 32,
            seed="456",
        )
    )

    assert result.s0_receipt_path is None
    assert stub_s0.inputs is None

