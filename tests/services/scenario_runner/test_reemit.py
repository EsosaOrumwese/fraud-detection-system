from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fraud_detection.scenario_runner.config import PolicyProfile, WiringProfile
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.ids import hash_payload, run_id_from_equivalence_key
from fraud_detection.scenario_runner.models import ReemitKind, ReemitRequest, RunPlan, RunStatusState, Strategy
from fraud_detection.scenario_runner.runner import ScenarioRunner


def _build_wiring(tmp_path: Path) -> WiringProfile:
    return WiringProfile(
        object_store_root=str(tmp_path / "artefacts"),
        control_bus_topic="fp.bus.control.v1",
        control_bus_root=str(tmp_path / "control_bus"),
        engine_catalogue_path="docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        gate_map_path="docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml",
        schema_root="docs/model_spec/platform/contracts/scenario_runner",
        engine_contracts_root="docs/model_spec/data-engine/interface_pack/contracts",
        authority_store_dsn=f"sqlite:///{(tmp_path / 'sr_authority.db').as_posix()}",
    )


def _build_policy() -> PolicyProfile:
    return PolicyProfile(
        policy_id="sr_policy",
        revision="v0-test",
        content_digest="b" * 64,
        reuse_policy="DENY",
        evidence_wait_seconds=60,
        attempt_limit=1,
        traffic_output_ids=["sealed_inputs_1A"],
    )


def _read_bus_message(bus_root: Path, topic: str, message_id: str) -> dict[str, object]:
    path = bus_root / topic / f"{message_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload


def test_reemit_ready_publishes_control_fact(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())
    platform_run_id = runner.platform_run_id

    run_id = run_id_from_equivalence_key("reemit-ready")
    anchor_event = runner._event("RUN_ACCEPTED", run_id, {"intent_fingerprint": "x"})
    runner.ledger.anchor_run(run_id, anchor_event)

    facts_view = {
        "run_id": run_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": run_id,
        "pins": {
            "manifest_fingerprint": "a" * 64,
            "parameter_hash": "b" * 64,
            "seed": 1,
            "scenario_id": "s1",
            "run_id": run_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": run_id,
        },
        "locators": [],
        "gate_receipts": [],
        "policy_rev": policy.as_rev(),
        "bundle_hash": "c" * 64,
        "run_config_digest": policy.content_digest,
        "plan_ref": f"{runner.ledger.prefix}/run_plan/{run_id}.json",
        "record_ref": f"{runner.ledger.prefix}/run_record/{run_id}.jsonl",
        "status_ref": f"{runner.ledger.prefix}/run_status/{run_id}.json",
        "oracle_pack_ref": {
            "engine_run_root": "runs/local_full_run-5/abc",
            "oracle_pack_id": "d" * 64,
            "manifest_ref": "runs/local_full_run-5/abc/_oracle_pack_manifest.json",
            "engine_release": "engine-0.1.0",
        },
    }
    runner.ledger.commit_facts_view(run_id, facts_view)
    plan = RunPlan(
        run_id=run_id,
        plan_hash=hash_payload("plan"),
        policy_rev=policy.as_rev(),
        strategy=Strategy.FORCE_REUSE,
        intended_outputs=[],
        required_gates=[],
        evidence_deadline_utc=datetime.now(tz=timezone.utc),
        attempt_limit=1,
        created_at_utc=datetime.now(tz=timezone.utc),
    )
    plan_event = runner._event("PLAN_COMMITTED", run_id, {"plan_hash": plan.plan_hash})
    runner.ledger.commit_plan(plan, plan_event)
    ready_event = runner._event("READY_COMMITTED", run_id, {"bundle_hash": facts_view["bundle_hash"]})
    runner.ledger.commit_ready(run_id, ready_event)

    response = runner.reemit(ReemitRequest(run_id=run_id, reemit_kind=ReemitKind.READY_ONLY))
    assert response.status_state == RunStatusState.READY
    assert response.published

    expected_key = hash_payload(f"ready|{platform_run_id}|{run_id}|{facts_view['bundle_hash']}")
    assert expected_key in response.published

    message = _read_bus_message(Path(wiring.control_bus_root), wiring.control_bus_topic, expected_key)
    assert message["message_id"] == expected_key
    payload = message["payload"]
    assert payload["run_id"] == run_id
    assert payload["platform_run_id"] == platform_run_id
    assert payload["scenario_run_id"] == run_id
    assert payload["bundle_hash"] == facts_view["bundle_hash"]
    assert payload.get("oracle_pack_ref") == facts_view["oracle_pack_ref"]


def test_reemit_terminal_publishes_control_fact(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())

    run_id = run_id_from_equivalence_key("reemit-terminal")
    anchor_event = runner._event("RUN_ACCEPTED", run_id, {"intent_fingerprint": "x"})
    runner.ledger.anchor_run(run_id, anchor_event)

    terminal_event = runner._event("EVIDENCE_FAIL", run_id, {"reason": "TEST_FAIL"})
    runner.ledger.commit_terminal(run_id, RunStatusState.FAILED, "TEST_FAIL", terminal_event)

    response = runner.reemit(ReemitRequest(run_id=run_id, reemit_kind=ReemitKind.TERMINAL_ONLY))
    assert response.status_state == RunStatusState.FAILED
    assert response.published

    status = runner.ledger.read_status(run_id)
    assert status is not None
    status_payload = status.model_dump(mode="json", exclude_none=True)
    status_hash = hash_payload(json.dumps(status_payload, sort_keys=True, ensure_ascii=True))
    expected_key = hash_payload(f"terminal|{run_id}|{RunStatusState.FAILED.value}|{status_hash}")
    assert expected_key in response.published

    message = _read_bus_message(Path(wiring.control_bus_root), wiring.control_bus_topic, expected_key)
    payload = message["payload"]
    assert payload["run_id"] == run_id
    assert payload["status_state"] == RunStatusState.FAILED.value

    events = runner.ledger.read_record_events(run_id)
    gov = [event for event in events if event.get("event_kind") == "GOV_REEMIT_KEY"]
    assert gov
    assert gov[-1]["details"].get("reemit_key") == expected_key


def test_reemit_ready_only_mismatch(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())

    run_id = run_id_from_equivalence_key("reemit-ready-only-mismatch")
    anchor_event = runner._event("RUN_ACCEPTED", run_id, {"intent_fingerprint": "x"})
    runner.ledger.anchor_run(run_id, anchor_event)
    terminal_event = runner._event("EVIDENCE_FAIL", run_id, {"reason": "TEST_FAIL"})
    runner.ledger.commit_terminal(run_id, RunStatusState.FAILED, "TEST_FAIL", terminal_event)

    response = runner.reemit(ReemitRequest(run_id=run_id, reemit_kind=ReemitKind.READY_ONLY))
    assert response.published == []
    assert response.message == "Reemit not applicable."

    events = runner.ledger.read_record_events(run_id)
    failed = [event for event in events if event.get("event_kind") == "REEMIT_FAILED"]
    assert failed
    assert failed[-1]["details"].get("reason") == "REEMIT_READY_ONLY_MISMATCH"


def test_reemit_terminal_only_mismatch(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())
    platform_run_id = runner.platform_run_id

    run_id = run_id_from_equivalence_key("reemit-terminal-only-mismatch")
    anchor_event = runner._event("RUN_ACCEPTED", run_id, {"intent_fingerprint": "x"})
    runner.ledger.anchor_run(run_id, anchor_event)

    facts_view = {
        "run_id": run_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": run_id,
        "pins": {
            "manifest_fingerprint": "a" * 64,
            "parameter_hash": "b" * 64,
            "seed": 1,
            "scenario_id": "s1",
            "run_id": run_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": run_id,
        },
        "locators": [],
        "gate_receipts": [],
        "policy_rev": policy.as_rev(),
        "bundle_hash": "c" * 64,
        "run_config_digest": policy.content_digest,
        "plan_ref": f"{runner.ledger.prefix}/run_plan/{run_id}.json",
        "record_ref": f"{runner.ledger.prefix}/run_record/{run_id}.jsonl",
        "status_ref": f"{runner.ledger.prefix}/run_status/{run_id}.json",
    }
    runner.ledger.commit_facts_view(run_id, facts_view)
    plan = RunPlan(
        run_id=run_id,
        plan_hash=hash_payload("plan"),
        policy_rev=policy.as_rev(),
        strategy=Strategy.FORCE_REUSE,
        intended_outputs=[],
        required_gates=[],
        evidence_deadline_utc=datetime.now(tz=timezone.utc),
        attempt_limit=1,
        created_at_utc=datetime.now(tz=timezone.utc),
    )
    plan_event = runner._event("PLAN_COMMITTED", run_id, {"plan_hash": plan.plan_hash})
    runner.ledger.commit_plan(plan, plan_event)
    ready_event = runner._event("READY_COMMITTED", run_id, {"bundle_hash": facts_view["bundle_hash"]})
    runner.ledger.commit_ready(run_id, ready_event)

    response = runner.reemit(ReemitRequest(run_id=run_id, reemit_kind=ReemitKind.TERMINAL_ONLY))
    assert response.published == []
    assert response.message == "Reemit not applicable."

    events = runner.ledger.read_record_events(run_id)
    failed = [event for event in events if event.get("event_kind") == "REEMIT_FAILED"]
    assert failed
    assert failed[-1]["details"].get("reason") == "REEMIT_TERMINAL_ONLY_MISMATCH"


def test_reemit_ready_missing_facts_view(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())
    platform_run_id = runner.platform_run_id

    run_id = run_id_from_equivalence_key("reemit-ready-missing-facts")
    anchor_event = runner._event("RUN_ACCEPTED", run_id, {"intent_fingerprint": "x"})
    runner.ledger.anchor_run(run_id, anchor_event)

    facts_view = {
        "run_id": run_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": run_id,
        "pins": {
            "manifest_fingerprint": "a" * 64,
            "parameter_hash": "b" * 64,
            "seed": 1,
            "scenario_id": "s1",
            "run_id": run_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": run_id,
        },
        "locators": [],
        "gate_receipts": [],
        "policy_rev": policy.as_rev(),
        "bundle_hash": "c" * 64,
        "run_config_digest": policy.content_digest,
        "plan_ref": f"{runner.ledger.prefix}/run_plan/{run_id}.json",
        "record_ref": f"{runner.ledger.prefix}/run_record/{run_id}.jsonl",
        "status_ref": f"{runner.ledger.prefix}/run_status/{run_id}.json",
    }
    runner.ledger.commit_facts_view(run_id, facts_view)
    plan = RunPlan(
        run_id=run_id,
        plan_hash=hash_payload("plan"),
        policy_rev=policy.as_rev(),
        strategy=Strategy.FORCE_REUSE,
        intended_outputs=[],
        required_gates=[],
        evidence_deadline_utc=datetime.now(tz=timezone.utc),
        attempt_limit=1,
        created_at_utc=datetime.now(tz=timezone.utc),
    )
    plan_event = runner._event("PLAN_COMMITTED", run_id, {"plan_hash": plan.plan_hash})
    runner.ledger.commit_plan(plan, plan_event)
    ready_event = runner._event("READY_COMMITTED", run_id, {"bundle_hash": facts_view["bundle_hash"]})
    runner.ledger.commit_ready(run_id, ready_event)

    facts_view_path = Path(wiring.object_store_root) / f"{runner.ledger.prefix}/run_facts_view/{run_id}.json"
    facts_view_path.unlink()

    response = runner.reemit(ReemitRequest(run_id=run_id, reemit_kind=ReemitKind.READY_ONLY))
    assert response.message == "Reemit failed."

    events = runner.ledger.read_record_events(run_id)
    failed = [event for event in events if event.get("event_kind") == "REEMIT_FAILED"]
    assert failed
    assert failed[-1]["details"].get("reason") == "FACTS_VIEW_MISSING"


def test_reemit_run_not_found(tmp_path: Path) -> None:
    wiring = _build_wiring(tmp_path)
    policy = _build_policy()
    runner = ScenarioRunner(wiring, policy, LocalEngineInvoker())

    response = runner.reemit(ReemitRequest(run_id=run_id_from_equivalence_key("missing-run")))
    assert response.message == "Run not found."
    assert response.published == []
