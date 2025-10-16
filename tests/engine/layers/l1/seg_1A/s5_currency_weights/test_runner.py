from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error
from engine.layers.l1.seg_1A.s5_currency_weights import (
    LegalTender,
    MerchantCurrencyInput,
    S5CurrencyWeightsRunner,
    S5DeterministicContext,
    ShareSurface,
)


class _DummyShareLoader:
    def __init__(self, settlement, ccy):
        self._settlement = settlement
        self._ccy = ccy

    def load_settlement_shares(self):
        return self._settlement

    def load_ccy_country_shares(self):
        return self._ccy


def _basic_deterministic_context() -> S5DeterministicContext:
    policy_path = Path("config/allocation/ccy_smoothing_params.yaml").resolve()
    return S5DeterministicContext(
        parameter_hash="abc123",
        manifest_fingerprint="fff111",
        run_id="run-1",
        seed=1234,
        policy_path=policy_path,
        merchants=(
            MerchantCurrencyInput(
                merchant_id=1,
                home_country_iso="US",
                share_vector={"USD": 0.6, "CAD": 0.4},
            ),
        ),
        settlement_shares_path=None,
        ccy_country_shares_path=None,
        iso_legal_tender_path=None,
    )


def _basic_share_surfaces():
    settlement = [
        ShareSurface(currency="USD", country_iso="US", share=0.7, obs_count=100),
        ShareSurface(currency="USD", country_iso="CA", share=0.3, obs_count=50),
    ]
    ccy = [
        ShareSurface(currency="USD", country_iso="US", share=0.6, obs_count=120),
        ShareSurface(currency="USD", country_iso="CA", share=0.4, obs_count=80),
    ]
    return settlement, ccy


def test_runner_writes_stage_logs_and_receipt(tmp_path):
    settlement, ccy = _basic_share_surfaces()
    runner = S5CurrencyWeightsRunner()
    deterministic = _basic_deterministic_context()
    outputs = runner.run(
        base_path=tmp_path,
        deterministic=deterministic,
        share_loader=_DummyShareLoader(settlement, ccy),
        iso_legal_tender=[
            LegalTender(country_iso="US", primary_ccy="USD"),
            LegalTender(country_iso="CA", primary_ccy="CAD"),
        ],
    )

    assert outputs.merchant_currency_path is not None
    assert outputs.stage_log_path is not None
    assert outputs.stage_log_path.exists()
    assert outputs.metrics["currencies_total"] == 1
    assert len(outputs.per_currency_metrics) == 1

    with outputs.stage_log_path.open("r", encoding="utf-8") as handle:
        lines = [json.loads(line) for line in handle if line.strip()]
    stages = [entry["stage"] for entry in lines]
    assert stages[0] == "N0"
    assert "N4" in stages
    assert lines[0]["event"] == "POLICY_RESOLVED"
    assert lines[0]["seed"] == deterministic.seed
    assert all("seed" in entry for entry in lines)

    receipt_path = outputs.receipt_path
    data = pd.read_parquet(outputs.weights_path)
    assert not data.empty
    receipt = json.loads(receipt_path.read_text())
    assert receipt["rng_trace_delta_events"] == 0
    assert receipt["rng_trace_delta_draws"] == 0


def test_runner_fails_on_rng_interaction(tmp_path, monkeypatch):
    settlement, ccy = _basic_share_surfaces()
    runner = S5CurrencyWeightsRunner()
    deterministic = _basic_deterministic_context()
    call_state = {"count": 0}

    def fake_snapshot(self, base_path, det):
        call_state["count"] += 1
        if call_state["count"] == 1:
            return {"events_total": 0, "draws_total": 0, "blocks_total": 0}
        return {"events_total": 1, "draws_total": 2, "blocks_total": 0}

    monkeypatch.setattr(
        S5CurrencyWeightsRunner, "_snapshot_rng_totals", fake_snapshot, raising=False
    )

    with pytest.raises(S0Error) as exc:
        runner.run(
            base_path=tmp_path,
            deterministic=deterministic,
            share_loader=_DummyShareLoader(settlement, ccy),
        )
    assert exc.value.context.code == "E_RNG_INTERACTION"
