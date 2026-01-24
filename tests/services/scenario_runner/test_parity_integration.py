from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.models import RunRequest, RunWindow, ScenarioBinding, Strategy
from fraud_detection.scenario_runner.runner import ScenarioRunner


pytestmark = [pytest.mark.parity, pytest.mark.engine_fixture]

RUN_ROOT = Path("runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92")
MANIFEST = "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8"
PARAM_HASH = "56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7"


def _require_env() -> dict[str, str]:
    bucket = os.getenv("SR_TEST_S3_BUCKET")
    dsn = os.getenv("SR_TEST_PG_DSN")
    if not bucket or not dsn:
        pytest.skip("SR_TEST_S3_BUCKET or SR_TEST_PG_DSN not set")
    prefix = os.getenv("SR_TEST_S3_PREFIX", "sr-test")
    endpoint = os.getenv("SR_TEST_S3_ENDPOINT_URL")
    region = os.getenv("SR_TEST_S3_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    path_style = os.getenv("SR_TEST_S3_PATH_STYLE", "true")
    return {
        "bucket": bucket,
        "dsn": dsn,
        "prefix": prefix,
        "endpoint": endpoint or "",
        "region": region,
        "path_style": path_style,
    }


def _build_wiring(tmp_path: Path, env: dict[str, str]) -> WiringProfile:
    unique = uuid.uuid4().hex
    root = f"s3://{env['bucket']}/{env['prefix']}/{unique}/fraud-platform/sr"
    return WiringProfile(
        object_store_root=root,
        control_bus_topic="fp.bus.control.v1",
        control_bus_root=str(tmp_path / "control_bus"),
        engine_catalogue_path="docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        gate_map_path="docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml",
        schema_root="docs/model_spec/platform/contracts/scenario_runner",
        engine_contracts_root="docs/model_spec/data-engine/interface_pack/contracts",
        authority_store_dsn=env["dsn"],
        s3_endpoint_url=env["endpoint"] or None,
        s3_region=env["region"],
        s3_path_style=env["path_style"].lower() == "true",
    )


def _build_policy() -> PolicyProfile:
    return PolicyProfile(
        policy_id="sr_policy",
        revision="v0-test",
        content_digest="b" * 64,
        reuse_policy="ALLOW",
        evidence_wait_seconds=60,
        attempt_limit=1,
        traffic_output_ids=["s5_validation_report_6A"],
    )


@pytest.mark.skipif(not RUN_ROOT.exists(), reason="local_full_run-5 not available")
def test_parity_reuse_ready_commit(tmp_path: Path) -> None:
    env = _require_env()
    wiring = _build_wiring(tmp_path, env)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker(str(RUN_ROOT)))

    run_key = f"sr-parity-reuse-6a-{uuid.uuid4().hex}"
    request = RunRequest(
        run_equivalence_key=run_key,
        manifest_fingerprint=MANIFEST,
        parameter_hash=PARAM_HASH,
        seed=42,
        scenario=ScenarioBinding(scenario_id="baseline_v1"),
        window=RunWindow(
            window_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        output_ids=["s5_validation_report_6A"],
        engine_run_root=str(RUN_ROOT),
        requested_strategy=Strategy.FORCE_REUSE,
        invoker="test",
    )

    response = runner.submit_run(request)
    assert response.message == "READY committed"
    status = runner.ledger.read_status(response.run_id)
    assert status is not None
    assert status.state.value == "READY"
