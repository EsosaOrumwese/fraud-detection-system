# ─── builder ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder
WORKDIR /build

# 1. Install Poetry (only for export)
RUN pip install --no-cache-dir poetry

# 2. Copy only the minimal files needed to resolve main dependencies
#    (your pyproject.toml now has GE in main, and no Apache-Airflow entry)
COPY ../../pyproject.toml ../../poetry.lock* ./

# 3. Export a pinned requirements.txt (main deps only)
RUN poetry export \
      --only main \
      --without-hashes \
      --format requirements.txt \
      --output requirements.txt

# Build a custom Airflow image with pinned deps at build time
ARG AIRFLOW_VERSION=3.0.2
ARG PYTHON_VERSION=3.12
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
#    so `import fraud_detection…` works out-of-the-box
COPY ../../src /opt/airflow/src
ENV PYTHONPATH=/opt/airflow/src

# 3) Bake in your DAGs & plugins
COPY dags/    /opt/airflow/dags/
COPY plugins/ /opt/airflow/plugins/

# 4) Copy infra & GE so scripts can run in-container
COPY ../../infra/terraform /opt/airflow/infra/terraform
COPY ../../great_expectations    /opt/airflow/great_expectations
