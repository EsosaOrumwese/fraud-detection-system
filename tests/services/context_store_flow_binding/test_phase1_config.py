from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.context_store_flow_binding.config import (
    ContextStoreFlowBindingConfigError,
    load_policy,
)


POLICY_PATH = Path("config/platform/context_store_flow_binding/policy_v0.yaml")


def test_load_policy_smoke_and_digest_is_stable(tmp_path: Path) -> None:
    policy = load_policy(POLICY_PATH)
    assert policy.policy_id == "context_store_flow_binding.policy.v0"
    assert policy.query_schema_version == "v1"
    assert "platform_run_id" in policy.required_pins
    assert policy.content_digest

    clone = tmp_path / "policy_clone.yaml"
    clone.write_text(POLICY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    clone_policy = load_policy(clone)
    assert clone_policy.content_digest == policy.content_digest


def test_load_policy_rejects_missing_required_pins(tmp_path: Path) -> None:
    bad = tmp_path / "policy_bad.yaml"
    bad.write_text(
        """
version: "0.1.0"
policy_id: context_store_flow_binding.policy.v0
revision: r1
query_schema_version: v1
required_pins:
  - platform_run_id
  - scenario_run_id
  - manifest_fingerprint
  - parameter_hash
  - scenario_id
require_seed: true
authoritative_flow_binding_event_types:
  - s2_flow_anchor_baseline_6B
""",
        encoding="utf-8",
    )
    with pytest.raises(ContextStoreFlowBindingConfigError):
        load_policy(bad)


@pytest.mark.parametrize("event_type", ["s2_flow_anchor_baseline_6B", "s3_flow_anchor_with_fraud_6B"])
def test_load_policy_accepts_authoritative_event_types(event_type: str, tmp_path: Path) -> None:
    good = tmp_path / "policy_good.yaml"
    good.write_text(
        f"""
version: "0.1.0"
policy_id: context_store_flow_binding.policy.v0
revision: r1
query_schema_version: v1
required_pins:
  - platform_run_id
  - scenario_run_id
  - manifest_fingerprint
  - parameter_hash
  - scenario_id
  - seed
require_seed: true
authoritative_flow_binding_event_types:
  - {event_type}
""",
        encoding="utf-8",
    )
    policy = load_policy(good)
    assert policy.authoritative_flow_binding_event_types == (event_type,)


def test_load_policy_rejects_unknown_event_type(tmp_path: Path) -> None:
    bad = tmp_path / "policy_bad_event.yaml"
    bad.write_text(
        """
version: "0.1.0"
policy_id: context_store_flow_binding.policy.v0
revision: r1
query_schema_version: v1
required_pins:
  - platform_run_id
  - scenario_run_id
  - manifest_fingerprint
  - parameter_hash
  - scenario_id
  - seed
require_seed: true
authoritative_flow_binding_event_types:
  - arrival_events_5B
""",
        encoding="utf-8",
    )
    with pytest.raises(ContextStoreFlowBindingConfigError):
        load_policy(bad)
