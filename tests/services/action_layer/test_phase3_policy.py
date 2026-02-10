from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.action_layer.policy import ActionLayerPolicyError, load_policy_bundle


def _policy_path() -> Path:
    return Path("config/platform/al/policy_v0.yaml")


def test_load_policy_bundle_parses_required_sections() -> None:
    bundle = load_policy_bundle(_policy_path())
    assert bundle.version == "v0"
    assert bundle.policy_rev.policy_id == "al.authz.v0"
    assert bundle.execution_posture.mode == "NORMAL"
    assert bundle.execution_posture.allow_execution is True
    assert bundle.retry_policy.max_attempts == 3
    assert "DF" in bundle.authz.allowed_origins
    assert "txn_disposition_publish" in bundle.authz.allowed_action_kinds


def test_policy_content_digest_is_deterministic() -> None:
    first = load_policy_bundle(_policy_path())
    second = load_policy_bundle(_policy_path())
    assert first.policy_rev.content_digest == second.policy_rev.content_digest


def test_policy_loader_rejects_invalid_mode(tmp_path: Path) -> None:
    path = tmp_path / "bad_policy.yaml"
    path.write_text(
        """
version: v0
policy_id: al.authz.v0
revision: r1
execution_posture:
  mode: UNKNOWN
  allow_execution: true
authz:
  allowed_origins: [DF]
  allowed_action_kinds: [txn_disposition_publish]
  actor_principal_prefix_allowlist:
    DF: [SYSTEM::decision_fabric]
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ActionLayerPolicyError):
        load_policy_bundle(path)
