from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.case_trigger.config import CaseTriggerConfigError, load_trigger_policy


def test_load_trigger_policy_v0_is_stable_and_complete() -> None:
    path = Path("config/platform/case_trigger/trigger_policy_v0.yaml")
    policy_a = load_trigger_policy(path)
    policy_b = load_trigger_policy(path)
    assert policy_a.version == "0.1.0"
    assert policy_a.policy_id == "case_trigger.policy.v0"
    assert policy_a.revision == "r1"
    assert policy_a.content_digest == policy_b.content_digest
    assert policy_a.rule_for_trigger_type("DECISION_ESCALATION") is not None
    assert policy_a.rule_for_trigger_type("UNKNOWN") is None


def test_trigger_policy_rejects_missing_supported_trigger_rule(tmp_path: Path) -> None:
    path = tmp_path / "bad_policy.yaml"
    path.write_text(
        """
version: "0.1.0"
policy_id: case_trigger.policy.v0
revision: r1
case_trigger:
  trigger_rules:
    - trigger_type: DECISION_ESCALATION
      source_classes: [DF_DECISION]
      required_evidence_ref_types: [DECISION, DLA_AUDIT_RECORD]
  required_pins: [platform_run_id, scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed]
  require_seed: true
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(CaseTriggerConfigError):
        load_trigger_policy(path)


def test_trigger_policy_rejects_unknown_required_evidence_ref_type(tmp_path: Path) -> None:
    path = tmp_path / "bad_ref_policy.yaml"
    path.write_text(
        """
version: "0.1.0"
policy_id: case_trigger.policy.v0
revision: r1
case_trigger:
  trigger_rules:
    - trigger_type: DECISION_ESCALATION
      source_classes: [DF_DECISION]
      required_evidence_ref_types: [DECISION, NOT_A_REAL_REF]
    - trigger_type: ACTION_FAILURE
      source_classes: [AL_OUTCOME]
      required_evidence_ref_types: [ACTION_OUTCOME, DLA_AUDIT_RECORD]
    - trigger_type: ANOMALY
      source_classes: [DLA_AUDIT]
      required_evidence_ref_types: [DLA_AUDIT_RECORD]
    - trigger_type: EXTERNAL_SIGNAL
      source_classes: [EXTERNAL_SIGNAL]
      required_evidence_ref_types: [EXTERNAL_REF]
    - trigger_type: MANUAL_ASSERTION
      source_classes: [MANUAL_ASSERTION]
      required_evidence_ref_types: [EXTERNAL_REF]
  required_pins: [platform_run_id, scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed]
  require_seed: true
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(CaseTriggerConfigError):
        load_trigger_policy(path)
