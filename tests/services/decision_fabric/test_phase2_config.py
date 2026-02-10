from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.decision_fabric.config import DecisionFabricConfigError, load_trigger_policy


def test_load_trigger_policy_v0_is_stable_and_versioned() -> None:
    path = Path("config/platform/df/trigger_policy_v0.yaml")
    policy_a = load_trigger_policy(path)
    policy_b = load_trigger_policy(path)
    assert policy_a.version == "0.1.0"
    assert policy_a.policy_id == "df.trigger_policy.v0"
    assert policy_a.revision == "r1"
    assert policy_a.content_digest == policy_b.content_digest
    assert policy_a.allowed_schema_versions("s3_event_stream_with_fraud_6B") == ("v1",)
    assert policy_a.allowed_schema_versions("unknown") is None


def test_policy_rejects_duplicate_trigger_event_types(tmp_path: Path) -> None:
    path = tmp_path / "bad_policy.yaml"
    path.write_text(
        """
version: "0.1.0"
policy_id: df.trigger_policy.v0
revision: r1
decision_trigger:
  admitted_traffic_topics: [fp.bus.traffic.fraud.v1]
  trigger_allowlist:
    - event_type: s3_event_stream_with_fraud_6B
      schema_versions: [v1]
    - event_type: s3_event_stream_with_fraud_6B
      schema_versions: [v1]
  blocked_event_types: [decision_response]
  blocked_event_type_prefixes: [df.]
  required_pins: [platform_run_id, scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed]
  require_seed: true
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(DecisionFabricConfigError):
        load_trigger_policy(path)
