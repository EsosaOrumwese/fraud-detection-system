from pathlib import Path

from fraud_detection.ingestion_gate.admission import _profile_id_for_class
from fraud_detection.ingestion_gate.config import ClassMap, SchemaPolicy
from fraud_detection.ingestion_gate.partitioning import PartitioningProfiles


CLASS_MAP_PATH = Path("config/platform/ig/class_map_v0.yaml")
SCHEMA_POLICY_PATH = Path("config/platform/ig/schema_policy_v0.yaml")
PARTITIONING_PATH = Path("config/platform/ig/partitioning_profiles_v0.yaml")


def _decision_response_envelope() -> dict:
    return {
        "event_id": "dec_evt_1",
        "event_type": "decision_response",
        "schema_version": "v1",
        "ts_utc": "2026-02-07T00:00:00.000000Z",
        "manifest_fingerprint": "a" * 64,
        "platform_run_id": "platform_20260207T000000Z",
        "scenario_run_id": "b" * 32,
        "parameter_hash": "c" * 64,
        "seed": 7,
        "scenario_id": "scenario-1",
        "payload": {
            "decision_id": "d" * 32,
            "source_event": {"event_id": "traffic_evt_1"},
            "pins": {"scenario_run_id": "b" * 32},
        },
    }


def _action_intent_envelope() -> dict:
    return {
        "event_id": "intent_evt_1",
        "event_type": "action_intent",
        "schema_version": "v1",
        "ts_utc": "2026-02-07T00:00:00.000000Z",
        "manifest_fingerprint": "a" * 64,
        "platform_run_id": "platform_20260207T000000Z",
        "scenario_run_id": "b" * 32,
        "parameter_hash": "c" * 64,
        "seed": 7,
        "scenario_id": "scenario-1",
        "payload": {
            "decision_id": "d" * 32,
            "idempotency_key": "idem-1",
            "pins": {"scenario_run_id": "b" * 32},
        },
    }


def test_df_outputs_present_in_class_map_and_schema_policy() -> None:
    class_map = ClassMap.load(CLASS_MAP_PATH)
    schema_policy = SchemaPolicy.load(SCHEMA_POLICY_PATH)

    expected_required_pins = {
        "platform_run_id",
        "scenario_run_id",
        "manifest_fingerprint",
        "parameter_hash",
        "seed",
        "scenario_id",
    }

    assert class_map.class_for("decision_response") == "rtdl_decision"
    assert class_map.class_for("action_intent") == "rtdl_action_intent"
    assert set(class_map.required_pins_for("decision_response")) == expected_required_pins
    assert set(class_map.required_pins_for("action_intent")) == expected_required_pins
    assert "run_id" not in class_map.required_pins_for("decision_response")
    assert "run_id" not in class_map.required_pins_for("action_intent")

    decision_policy = schema_policy.for_event("decision_response")
    assert decision_policy is not None
    assert decision_policy.class_name == "rtdl_decision"
    assert decision_policy.schema_version_required is True
    assert decision_policy.allowed_schema_versions == ["v1"]
    assert decision_policy.payload_schema_ref == "docs/model_spec/platform/contracts/real_time_decision_loop/decision_payload.schema.yaml"

    intent_policy = schema_policy.for_event("action_intent")
    assert intent_policy is not None
    assert intent_policy.class_name == "rtdl_action_intent"
    assert intent_policy.schema_version_required is True
    assert intent_policy.allowed_schema_versions == ["v1"]
    assert intent_policy.payload_schema_ref == "docs/model_spec/platform/contracts/real_time_decision_loop/action_intent.schema.yaml"


def test_df_outputs_route_to_expected_partitioning_profiles() -> None:
    class_map = ClassMap.load(CLASS_MAP_PATH)
    partitioning = PartitioningProfiles(str(PARTITIONING_PATH))

    default_profile = "ig.partitioning.v0.traffic"
    decision_profile_id = _profile_id_for_class(class_map.class_for("decision_response"), default_profile)
    intent_profile_id = _profile_id_for_class(class_map.class_for("action_intent"), default_profile)

    assert decision_profile_id == "ig.partitioning.v0.rtdl.decision"
    assert intent_profile_id == "ig.partitioning.v0.rtdl.action_intent"

    decision_profile = partitioning.get(decision_profile_id)
    intent_profile = partitioning.get(intent_profile_id)
    assert decision_profile.stream == "fp.bus.traffic.fraud.v1"
    assert intent_profile.stream == "fp.bus.traffic.fraud.v1"

    decision_key = partitioning.derive_key(decision_profile_id, _decision_response_envelope())
    intent_key = partitioning.derive_key(intent_profile_id, _action_intent_envelope())

    assert len(decision_key) == 64
    assert len(intent_key) == 64
