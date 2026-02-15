FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Pinned M1.A include surfaces only.
COPY pyproject.toml /app/pyproject.toml
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
COPY docs/model_spec/data-engine/interface_pack/layer-1/specs/contracts/1A/schemas.layer1.yaml /app/docs/model_spec/data-engine/interface_pack/layer-1/specs/contracts/1A/schemas.layer1.yaml
COPY docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml /app/docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml
COPY docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml /app/docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml

RUN python -m pip install --upgrade pip && \
    python - <<'PY'
import subprocess
import sys
import tomllib

with open("/app/pyproject.toml", "rb") as fh:
    deps = tomllib.load(fh)["project"]["dependencies"]

selected = {
    "requests",
    "pyarrow",
    "pyyaml",
    "jsonschema",
    "boto3",
    "duckdb",
    "pydantic",
    "pydantic-settings",
    "psutil",
    "psycopg[binary]",
    "flask",
    "werkzeug",
    "referencing",
    "kafka-python",
    "orjson",
}

reqs = []
seen = set()
for dep in deps:
    name = dep.split(" ", 1)[0].lower()
    if name in selected:
        pip_req = dep.replace(" (", "").replace(")", "")
        if pip_req not in seen:
            reqs.append(pip_req)
            seen.add(pip_req)

missing = sorted(x for x in selected if not any(r.lower().startswith(x.lower()) for r in reqs))
if missing:
    raise SystemExit(f"missing required dependency pins in pyproject.toml: {missing}")

subprocess.check_call([sys.executable, "-m", "pip", "install", *reqs])
PY

RUN adduser --disabled-password --gecos "" --home /home/appuser appuser && \
    chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "fraud_detection.platform_conformance.cli", "--help"]
