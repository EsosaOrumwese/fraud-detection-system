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
COPY docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml /app/docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml
COPY docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml /app/docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml

RUN python -m pip install --no-cache-dir "pip==25.0.1" && \
    python -m pip install --require-hashes -r /app/requirements/m1-image.lock.txt

RUN adduser --disabled-password --gecos "" --home /home/appuser appuser && \
    chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "fraud_detection.platform_conformance.cli", "--help"]
