# ─── build args (must come before ALL FROMs) ─────────────────────────────
ARG AIRFLOW_VERSION=3.0.2
ARG PYTHON_VERSION=3.12

# ─── builder stage ──────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS builder
WORKDIR /build

# 1. Install Poetry (only for export)
RUN pip install --no-cache-dir poetry poetry-plugin-export

# 2. Copy only the minimal files needed to resolve main dependencies
#    (pyproject.toml lives at repo root, alongside poetry.lock)
COPY pyproject.toml poetry.lock* ./

# 3. Copy your source tree so Poetry can build it
COPY src/ src/

# 4. Export a pinned requirements.txt (main deps only)
RUN poetry export \
      --only main \
      --without-hashes \
      --format requirements.txt \
      --output requirements.txt

# 5. Build a wheel of your package (will land in dist/)
RUN poetry build -f wheel

# ─── runtime stage ──────────────────────────────────────────────────────
FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

# Install OS-level libs for wheels (e.g. psycopg2); clean up apt lists
USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential libpq-dev \
  && rm -rf /var/lib/apt/lists/*

USER airflow
WORKDIR /opt/airflow

# 1) Pull in the pinned runtime dependencies
COPY --from=builder /build/requirements.txt /tmp/requirements-runtime.txt

# 2) Pull in your freshly-built wheel
COPY --from=builder /build/dist/*.whl    /tmp/

# 3) Install both your deps and your package
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r /tmp/requirements-runtime.txt \
 && pip install --no-cache-dir /tmp/*.whl

# 4) Bake in your DAGs & plugins
COPY orchestration/airflow/dags/    ./dags/
COPY orchestration/airflow/plugins/ ./plugins/

# 5) Bake in infra & GE so your DAGs can import/execute them
## commented out infra/terraform as I don't think it's neccessary for this image
#COPY infra/terraform/       ./infra/terraform/
COPY great_expectations/    ./great_expectations/
COPY schema/                ./schema
COPY scripts/ge_validate.py ./scripts/

# Ensure airflow user can write to GE’s uncommitted store
USER root
# 50000 is the default AIRFLOW_UID; 0 is the root GID
RUN chown -R 50000:0 /opt/airflow/great_expectations

# Back to the airflow user for normal operation
USER airflow
