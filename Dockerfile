FROM python:3.12-slim@sha256:42f1689d6d6b906c7e829f9d9ec38491550344ac9adc01e464ff9a08df1ffb48

ARG SOURCE_DATE_EPOCH=0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_NO_COMPILE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONHASHSEED=0 \
    SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH} \
    PYTHONPATH=/app/src

WORKDIR /app

# Pinned M1.A include surfaces only.
COPY pyproject.toml /app/pyproject.toml
COPY requirements/m1-image.lock.txt /app/requirements/m1-image.lock.txt
COPY requirements/wheelhouse /app/requirements/wheelhouse
COPY src/fraud_detection /app/src/fraud_detection
COPY config/platform /app/config/platform
COPY docs/model_spec/platform/contracts /app/docs/model_spec/platform/contracts
COPY docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml /app/docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml
COPY docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml /app/docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml
COPY docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml /app/docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml
COPY docs/model_spec/data-engine/interface_pack/contracts/engine_invocation.schema.yaml /app/docs/model_spec/data-engine/interface_pack/contracts/engine_invocation.schema.yaml
COPY docs/model_spec/data-engine/interface_pack/contracts/engine_output_locator.schema.yaml /app/docs/model_spec/data-engine/interface_pack/contracts/engine_output_locator.schema.yaml
COPY docs/model_spec/data-engine/interface_pack/contracts/gate_receipt.schema.yaml /app/docs/model_spec/data-engine/interface_pack/contracts/gate_receipt.schema.yaml
COPY docs/model_spec/data-engine/interface_pack/contracts/instance_proof_receipt.schema.yaml /app/docs/model_spec/data-engine/interface_pack/contracts/instance_proof_receipt.schema.yaml
COPY docs/model_spec/data-engine/interface_pack/contracts/run_receipt.schema.yaml /app/docs/model_spec/data-engine/interface_pack/contracts/run_receipt.schema.yaml
COPY docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml /app/docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml
COPY docs/model_spec/data-engine/layer-2/specs/contracts/5B /app/docs/model_spec/data-engine/layer-2/specs/contracts/5B
COPY docs/model_spec/data-engine/layer-3/specs/contracts/6B /app/docs/model_spec/data-engine/layer-3/specs/contracts/6B

RUN python -m pip install --no-cache-dir "pip==25.0.1" && \
    python -m pip install --no-index --find-links=/app/requirements/wheelhouse --require-hashes -r /app/requirements/m1-image.lock.txt

RUN python - <<'PY'
from pathlib import Path

from fraud_detection.ingestion_gate.config import SchemaPolicy
from fraud_detection.ingestion_gate.schema import SchemaEnforcer
from fraud_detection.ingestion_gate.schemas import SchemaRegistry

root = Path("/app")
policy = SchemaPolicy.load(root / "config/platform/ig/schema_policy_v0.yaml")
enforcer = SchemaEnforcer(
    envelope_registry=SchemaRegistry(root / "docs/model_spec/data-engine/interface_pack/contracts"),
    payload_registry_root=root,
    policy=policy,
)

refs = sorted(
    {
        str(entry.payload_schema_ref).strip()
        for entry in policy.policies
        if getattr(entry, "payload_schema_ref", None)
    }
)
for ref in refs:
    enforcer._resolve_payload_schema(ref)

print(f"Resolved {len(refs)} IG payload schema refs successfully.")
PY

RUN adduser --disabled-password --gecos "" --home /home/appuser appuser && \
    chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "fraud_detection.platform_conformance.cli", "--help"]
