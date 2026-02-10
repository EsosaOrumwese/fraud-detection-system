from pathlib import Path

from fraud_detection.ingestion_gate.admission import _profile_id_for_class
from fraud_detection.ingestion_gate.config import ClassMap, SchemaPolicy
from fraud_detection.ingestion_gate.partitioning import PartitioningProfiles


CLASS_MAP_PATH = Path("config/platform/ig/class_map_v0.yaml")
SCHEMA_POLICY_PATH = Path("config/platform/ig/schema_policy_v0.yaml")
PARTITIONING_PATH = Path("config/platform/ig/partitioning_profiles_v0.yaml")


def _case_trigger_envelope() -> dict:
    return {
        "event_id": "ct_evt_1",
        "event_type": "case_trigger",
        "schema_version": "v1",
        "ts_utc": "2026-02-09T16:20:00.000000Z",
        "manifest_fingerprint": "a" * 64,
        "platform_run_id": "platform_20260209T162000Z",
        "scenario_run_id": "b" * 32,
        "parameter_hash": "c" * 64,
        "seed": 7,
        "scenario_id": "scenario-1",
        "payload": {
            "case_id": "d" * 32,
            "case_trigger_id": "e" * 32,
            "trigger_type": "DECISION_ESCALATION",
            "source_ref_id": "decision:dec_001",
            "case_subject_key": {
                "platform_run_id": "platform_20260209T162000Z",
                "event_class": "traffic_fraud",
                "event_id": "evt_traffic_1",
            },
            "pins": {
                "platform_run_id": "platform_20260209T162000Z",
                "scenario_run_id": "b" * 32,
                "manifest_fingerprint": "a" * 64,
                "parameter_hash": "c" * 64,
                "scenario_id": "scenario-1",
                "seed": 7,
            },
            "observed_time": "2026-02-09T16:20:00.000000Z",
            "payload_hash": "f" * 64,
            "evidence_refs": [
                {"ref_type": "DECISION", "ref_id": "dec_001"},
                {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
            ],
        },
    }


def test_case_trigger_present_in_class_map_and_schema_policy() -> None:
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

    assert class_map.class_for("case_trigger") == "case_trigger"
    assert set(class_map.required_pins_for("case_trigger")) == expected_required_pins
    assert "run_id" not in class_map.required_pins_for("case_trigger")

    policy = schema_policy.for_event("case_trigger")
    assert policy is not None
    assert policy.class_name == "case_trigger"
    assert policy.schema_version_required is True
    assert policy.allowed_schema_versions == ["v1"]
    assert policy.payload_schema_ref == "docs/model_spec/platform/contracts/case_and_labels/case_trigger.schema.yaml"


def test_case_trigger_routes_to_dedicated_partition_profile() -> None:
    class_map = ClassMap.load(CLASS_MAP_PATH)
    partitioning = PartitioningProfiles(str(PARTITIONING_PATH))

    default_profile = "ig.partitioning.v0.traffic"
    profile_id = _profile_id_for_class(class_map.class_for("case_trigger"), default_profile)
    assert profile_id == "ig.partitioning.v0.case.trigger"

    profile = partitioning.get(profile_id)
    assert profile.stream == "fp.bus.case.v1"

    key = partitioning.derive_key(profile_id, _case_trigger_envelope())
    assert len(key) == 64

    fallback = _case_trigger_envelope()
    payload = dict(fallback["payload"])
    payload.pop("case_id", None)
    fallback["payload"] = payload
    fallback["platform_run_id"] = "platform_20260210T000000Z"
    fallback_payload_pins = dict(fallback["payload"]["pins"])
    fallback_payload_pins["platform_run_id"] = "platform_20260210T000000Z"
    fallback["payload"]["pins"] = fallback_payload_pins
    key_other_run = partitioning.derive_key(profile_id, fallback)
    assert key_other_run != key
