from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

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


def _prepare_base_inputs(
    tmp_path: Path,
    *,
    parameter_hash: str,
    seed: int,
    run_id: str,
    weights: list[dict],
    candidate_rows: list[dict] | None = None,
    merchant_currency_rows: list[dict] | None = None,
    ztp_records: list[dict] | None = None,
    eligibility_rows: list[dict] | None = None,
) -> None:
    candidate_dir = (
        tmp_path
        / "data"
        / "layer1"
        / "1A"
        / "s3_candidate_set"
        / f"parameter_hash={parameter_hash}"
    )
    candidate_dir.mkdir(parents=True, exist_ok=True)
    default_candidates = [
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
    selected_candidates = candidate_rows or default_candidates
    pd.DataFrame(selected_candidates).to_parquet(
        candidate_dir / "part-00000.parquet",
        index=False,
    )
    if eligibility_rows is None:
        merchant_ids = sorted(
            {int(row["merchant_id"]) for row in selected_candidates}
        )
        eligibility_rows = [
            {"merchant_id": merchant_id, "is_eligible": True}
            for merchant_id in merchant_ids
        ]

    weights_dir = (
        tmp_path
        / "data"
        / "layer1"
        / "1A"
        / "ccy_country_weights_cache"
        / f"parameter_hash={parameter_hash}"
    )
    weights_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(weights).to_parquet(weights_dir / "part-00000.parquet", index=False)
    _write_s5_receipt(weights_dir)

    mc_dir = (
        tmp_path
        / "data"
        / "layer1"
        / "1A"
        / "merchant_currency"
        / f"parameter_hash={parameter_hash}"
    )
    mc_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(merchant_currency_rows or [{"merchant_id": 1, "kappa": "USD"}]).to_parquet(
        mc_dir / "part-00000.parquet",
        index=False,
    )
    eligibility_dir = (
        tmp_path
        / "data"
        / "layer1"
        / "1A"
        / "crossborder_eligibility_flags"
        / f"parameter_hash={parameter_hash}"
    )
    eligibility_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(eligibility_rows).to_parquet(
        eligibility_dir / "part-00000.parquet",
        index=False,
    )

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
    records = ztp_records or [{"merchant_id": 1, "K_target": 1}]
    payload = "\n".join(json.dumps(record) for record in records)
    (ztp_path / "part-00000.jsonl").write_text(
        payload + ("\n" if payload else ""),
        encoding="utf-8",
    )


def _write_policy(
    tmp_path: Path,
    *,
    emit_membership: bool = True,
    log_all_candidates: bool = True,
    zero_weight_rule: str = "exclude",
) -> Path:
    policy = {
        "policy_semver": "0.1.0",
        "policy_version": "2025-10-16",
        "defaults": {
            "emit_membership_dataset": emit_membership,
            "log_all_candidates": log_all_candidates,
            "max_candidates_cap": 0,
            "zero_weight_rule": zero_weight_rule,
        },
        "per_currency": {
            "USD": {
                "emit_membership_dataset": emit_membership,
                "max_candidates_cap": 0,
                "zero_weight_rule": zero_weight_rule,
            }
        },
    }
    path = tmp_path / "s6_policy.yaml"
    path.write_text(yaml.safe_dump(policy), encoding="utf-8")
    return path


def test_s6_runner_end_to_end(tmp_path):
    parameter_hash = "a" * 64
    seed = 12345
    run_id = "d" * 32
    manifest = "0" * 64

    _prepare_base_inputs(
        tmp_path,
        parameter_hash=parameter_hash,
        seed=seed,
        run_id=run_id,
        weights=[
            {"currency": "USD", "country_iso": "US", "weight": 0.5},
            {"currency": "USD", "country_iso": "CA", "weight": 0.3},
            {"currency": "USD", "country_iso": "FR", "weight": 0.2},
        ],
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

    payload = validate_outputs(base_path=tmp_path, outputs=outputs)
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


def test_s6_runner_zero_weight_domain(tmp_path):
    parameter_hash = "b" * 64
    seed = 777
    run_id = "e" * 32
    manifest = "f" * 64

    _prepare_base_inputs(
        tmp_path,
        parameter_hash=parameter_hash,
        seed=seed,
        run_id=run_id,
        weights=[
            {"currency": "USD", "country_iso": "US", "weight": 1.0},
            {"currency": "USD", "country_iso": "CA", "weight": 0.0},
            {"currency": "USD", "country_iso": "FR", "weight": 0.0},
        ],
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

    assert outputs.events_written == 0
    assert outputs.events_path is None
    assert outputs.membership_path is None
    assert outputs.membership_rows == 0
    assert outputs.reason_code_counts == {"ZERO_WEIGHT_DOMAIN": 1}

    payload = validate_outputs(base_path=tmp_path, outputs=outputs)
    assert payload["membership_rows"] == 0


def test_s6_runner_reduced_logging(tmp_path):
    parameter_hash = "c" * 64
    seed = 4242
    run_id = "f" * 32
    manifest = "1" * 64

    _prepare_base_inputs(
        tmp_path,
        parameter_hash=parameter_hash,
        seed=seed,
        run_id=run_id,
        weights=[
            {"currency": "USD", "country_iso": "US", "weight": 0.5},
            {"currency": "USD", "country_iso": "CA", "weight": 0.3},
            {"currency": "USD", "country_iso": "FR", "weight": 0.2},
        ],
    )

    policy_path = _write_policy(
        tmp_path,
        emit_membership=True,
        log_all_candidates=False,
    )

    runner = S6Runner()
    outputs = runner.run(
        base_path=tmp_path,
        policy_path=policy_path,
        parameter_hash=parameter_hash,
        seed=seed,
        run_id=run_id,
        manifest_fingerprint=manifest,
    )

    assert outputs.log_all_candidates is False
    assert outputs.events_written == outputs.membership_rows == 1
    assert outputs.events_path is not None and outputs.events_path.exists()
    assert outputs.membership_path is not None and outputs.membership_path.exists()

    payload = validate_outputs(base_path=tmp_path, outputs=outputs)
    assert payload["log_all_candidates"] is False


def test_s6_runner_defaults_missing_k_target_to_zero(tmp_path):
    parameter_hash = "d" * 64
    seed = 30303
    run_id = "a" * 32
    manifest = "2" * 64

    candidate_rows = [
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
            "merchant_id": 2,
            "country_iso": "US",
            "candidate_rank": 0,
            "is_home": True,
            "reason_codes": [],
            "filter_tags": [],
        },
        {
            "parameter_hash": parameter_hash,
            "merchant_id": 2,
            "country_iso": "GB",
            "candidate_rank": 1,
            "is_home": False,
            "reason_codes": [],
            "filter_tags": [],
        },
    ]

    _prepare_base_inputs(
        tmp_path,
        parameter_hash=parameter_hash,
        seed=seed,
        run_id=run_id,
        weights=[
            {"currency": "USD", "country_iso": "US", "weight": 0.6},
            {"currency": "USD", "country_iso": "CA", "weight": 0.4},
            {"currency": "USD", "country_iso": "GB", "weight": 0.2},
        ],
        candidate_rows=candidate_rows,
        merchant_currency_rows=[
            {"merchant_id": 1, "kappa": "USD"},
            {"merchant_id": 2, "kappa": "USD"},
        ],
        ztp_records=[
            {"merchant_id": 1, "K_target": 1},
        ],
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

    assert len(outputs.results) == 2
    zero_k_merchants = [result for result in outputs.results if result.k_target == 0]
    assert len(zero_k_merchants) == 1
    assert outputs.membership_rows == 1

    payload = validate_outputs(base_path=tmp_path, outputs=outputs)
    assert payload["membership_rows"] == 1
    assert set(payload["events_by_merchant"].keys()) == {"1", "2"}


def test_s6_runner_skips_ineligible_merchants(tmp_path):
    parameter_hash = 'e' * 64
    seed = 5151
    run_id = 'deadbeefcafebabedeadbeefcafebabe'
    manifest = '3' * 64

    candidate_rows = [
        {
            'parameter_hash': parameter_hash,
            'merchant_id': 1,
            'country_iso': 'US',
            'candidate_rank': 0,
            'is_home': True,
            'reason_codes': [],
            'filter_tags': [],
        },
        {
            'parameter_hash': parameter_hash,
            'merchant_id': 1,
            'country_iso': 'CA',
            'candidate_rank': 1,
            'is_home': False,
            'reason_codes': [],
            'filter_tags': [],
        },
        {
            'parameter_hash': parameter_hash,
            'merchant_id': 2,
            'country_iso': 'US',
            'candidate_rank': 0,
            'is_home': True,
            'reason_codes': [],
            'filter_tags': [],
        },
        {
            'parameter_hash': parameter_hash,
            'merchant_id': 2,
            'country_iso': 'GB',
            'candidate_rank': 1,
            'is_home': False,
            'reason_codes': [],
            'filter_tags': [],
        },
    ]

    _prepare_base_inputs(
        tmp_path,
        parameter_hash=parameter_hash,
        seed=seed,
        run_id=run_id,
        weights=[
            {'currency': 'USD', 'country_iso': 'US', 'weight': 0.7},
            {'currency': 'USD', 'country_iso': 'CA', 'weight': 0.3},
            {'currency': 'USD', 'country_iso': 'GB', 'weight': 0.2},
        ],
        candidate_rows=candidate_rows,
        merchant_currency_rows=[
            {'merchant_id': 1, 'kappa': 'USD'},
            {'merchant_id': 2, 'kappa': 'USD'},
        ],
        ztp_records=[{'merchant_id': 1, 'K_target': 1}],
        eligibility_rows=[
            {'merchant_id': 1, 'is_eligible': True},
            {'merchant_id': 2, 'is_eligible': False},
        ],
    )

    policy_path = Path('config/allocation/s6_selection_policy.yaml').resolve()
    runner = S6Runner()
    outputs = runner.run(
        base_path=tmp_path,
        policy_path=policy_path,
        parameter_hash=parameter_hash,
        seed=seed,
        run_id=run_id,
        manifest_fingerprint=manifest,
    )

    merchant_ids = [result.merchant_id for result in outputs.results]
    assert merchant_ids == [1]
    assert outputs.membership_rows == 1

    payload = validate_outputs(base_path=tmp_path, outputs=outputs)
    assert payload['membership_rows'] == 1
    assert set(payload['events_by_merchant'].keys()) == {'1'}

