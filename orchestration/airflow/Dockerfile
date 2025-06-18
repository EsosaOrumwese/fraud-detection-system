# ─────────────────────────────────────────────────────────────────────
# Build a custom Airflow image with pinned deps at build time
# (uncommented build: . in compose → picks this Dockerfile)
# ─────────────────────────────────────────────────────────────────────
ARG AIRFLOW_VERSION=3.0.2
ARG PYTHON_VERSION=3.11
FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

# ─────────────────────────────────────────────────────────────────────
# Install OS-level libs for wheels (e.g. psycopg2); clean up apt lists
# ─────────────────────────────────────────────────────────────────────
USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential libpq-dev \
  && rm -rf /var/lib/apt/lists/*

USER airflow

# ─────────────────────────────────────────────────────────────────────
# Copy & install your exact Python requirements
# Changed: moved pip installs to build time for immutable images
# ─────────────────────────────────────────────────────────────────────
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r /tmp/requirements.txt

# ─────────────────────────────────────────────────────────────────────
# Bake in your DAGs and plugins for faster container startup
# ─────────────────────────────────────────────────────────────────────
COPY dags/    /opt/airflow/dags/
COPY plugins/ /opt/airflow/plugins/
