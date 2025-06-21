# ─── build args (must come before ALL FROMs) ─────────────────────────────
ARG AIRFLOW_VERSION=3.0.2
ARG PYTHON_VERSION=3.12

# ─── builder stage ──────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS builder
WORKDIR /build

# 1. Install Poetry (only for export)
RUN pip install --no-cache-dir poetry
RUN pip install --no-cache-dir poetry-plugin-export

# 2. Copy only the minimal files needed to resolve main dependencies
#    (pyproject.toml lives at repo root, alongside poetry.lock)
COPY pyproject.toml poetry.lock* ./

# 3. Export a pinned requirements.txt (main deps only)
RUN poetry export \
      --only main \
      --without-hashes \
      --format requirements.txt \
      --output requirements.txt

# ─── runtime stage ──────────────────────────────────────────────────────
FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

# Install OS-level libs for wheels (e.g. psycopg2); clean up apt lists
USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential libpq-dev \
  && rm -rf /var/lib/apt/lists/*

USER airflow

# 1) Install your runtime deps
COPY --from=builder /build/requirements.txt /tmp/requirements-runtime.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r /tmp/requirements-runtime.txt

# 2) Copy & install your fraud-detection package
#    so it's installed as a real Python package
COPY src /opt/airflow/src
RUN pip install --no-cache-dir /opt/airflow/src

# 3) Bake in your DAGs & plugins (paths now under orchestration/airflow/)
COPY orchestration/airflow/dags/    /opt/airflow/dags/
COPY orchestration/airflow/plugins/ /opt/airflow/plugins/

# 4) Copy infra & Great Expectations
COPY infra/terraform/       /opt/airflow/infra/terraform/
COPY great_expectations/    /opt/airflow/great_expectations/
COPY scripts/ge_validate.py /opt/airflow/scripts/
