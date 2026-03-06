from pathlib import Path

from fraud_detection.ingestion_gate.config import SchemaPolicy
from fraud_detection.ingestion_gate.schema import SchemaEnforcer
from fraud_detection.ingestion_gate.schemas import SchemaRegistry


def test_live_ig_schema_policy_refs_resolve_transitively() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    policy = SchemaPolicy.load(repo_root / "config/platform/ig/schema_policy_v0.yaml")
    enforcer = SchemaEnforcer(
        envelope_registry=SchemaRegistry(
            repo_root / "docs/model_spec/data-engine/interface_pack/contracts"
        ),
        payload_registry_root=repo_root,
        policy=policy,
    )

    refs = sorted(
        {
            str(entry.payload_schema_ref).strip()
            for entry in policy.policies.values()
            if getattr(entry, "payload_schema_ref", None)
        }
    )
    assert refs

    for ref in refs:
        schema, _registry = enforcer._resolve_payload_schema(ref)
        assert schema is not None
