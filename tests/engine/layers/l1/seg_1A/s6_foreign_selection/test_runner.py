from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from engine.layers.l1.seg_1A.s6_foreign_selection import S6Runner
from engine.layers.l1.seg_1A.s6_foreign_selection.validate import validate_outputs


def _write_s5_receipt(directory: Path) -> None:
    receipt = {"component": "s5", "status": "PASS"}
    payload = json.dumps(receipt, sort_keys=True, indent=2)
    directory.mkdir(parents=True, exist_ok=True)
    receipt_path = directory / "S5_VALIDATION.json"
    receipt_path.write_text(payload, encoding="utf-8")
    digest = __import__("hashlib").sha256(payload.encode("utf-8")).hexdigest()
    (directory / "_passed.flag").write_text(f"sha256_hex={digest}\n", encoding="ascii")


def test_s6_runner_end_to_end(tmp_path):
    parameter_hash = "abc123"
    seed = 12345
    run_id = "run-test"
    manifest = "0" * 64

    # S3 candidate set (home + 2 foreign)
    candidate_dir = (
        tmp_path
        / "data"
        / "layer1"
        / "1A"
        / "s3_candidate_set"
        / f"parameter_hash={parameter_hash}"
    )
    candidate_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "parameter_hash": parameter_hash,
                "merchant_id": 1,
                "country_iso": "US",
                "candidate_rank": 0,
                "is_home": True,
                "reason_codes": [],
                "filter_tags": [],
            },
            {
                "parameter_hash": parameter_hash,
                "merchant_id": 1,
                "country_iso": "CA",
                "candidate_rank": 1,
                "is_home": False,
                "reason_codes": [],
                "filter_tags": [],
            },
            {
                "parameter_hash": parameter_hash,
                "merchant_id": 1,
                "country_iso": "FR",
                "candidate_rank": 2,
                "is_home": False,
                "reason_codes": [],
                "filter_tags": [],
            },
        ]
    ).to_parquet(candidate_dir / "part-00000.parquet", index=False)

    # S5 weights + receipt
    weights_dir = (
        tmp_path
        / "data"
        / "layer1"
        / "1A"
        / "ccy_country_weights_cache"
        / f"parameter_hash={parameter_hash}"
    )
    weights_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"currency": "USD", "country_iso": "US", "weight": 0.5},
            {"currency": "USD", "country_iso": "CA", "weight": 0.3},
            {"currency": "USD", "country_iso": "FR", "weight": 0.2},
        ]
    ).to_parquet(weights_dir / "part-00000.parquet", index=False)
    _write_s5_receipt(weights_dir)

    # Merchant currency cache
    mc_dir = (
        tmp_path
        / "data"
        / "layer1"
        / "1A"
        / "merchant_currency"
        / f"parameter_hash={parameter_hash}"
    )
    mc_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"merchant_id": 1, "kappa": "USD"},
        ]
    ).to_parquet(mc_dir / "part-00000.parquet", index=False)

    # S4 rng_event_ztp_final log
    ztp_path = (
        tmp_path
        / "logs"
        / "rng"
        / "events"
        / "ztp_final"
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
    )
    ztp_path.mkdir(parents=True, exist_ok=True)
    (ztp_path / "part-00000.jsonl").write_text(
        json.dumps({"merchant_id": 1, "K_target": 1}) + "\n",
        encoding="utf-8",
    )

    policy_path = Path("config/allocation/s6_selection_policy.yaml").resolve()

    runner = S6Runner()
    outputs = runner.run(
        base_path=tmp_path,
        policy_path=policy_path,
        parameter_hash=parameter_hash,
        seed=seed,
        run_id=run_id,
        manifest_fingerprint=manifest,
    )

    assert outputs.events_path is not None
    assert outputs.events_path.exists()
    assert outputs.membership_path is not None
    assert outputs.membership_path.exists()
    assert outputs.receipt_path is not None
    assert outputs.receipt_path.exists()

    membership_df = pd.read_parquet(outputs.membership_path)
    assert membership_df.shape[0] == 1

    payload = validate_outputs(receipt_path=outputs.receipt_path)
    assert payload["gumbel_key_written"] == outputs.events_written
    assert payload["merchants_processed"] == 1

    log_lines = [
        json.loads(line)
        for line in outputs.events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(log_lines) == outputs.events_written
    assert len(log_lines) == 2
    selected_rows = [row for row in log_lines if row.get("selected")]
    assert len(selected_rows) == 1
    assert membership_df.iloc[0]["country_iso"] == selected_rows[0]["country_iso"]
