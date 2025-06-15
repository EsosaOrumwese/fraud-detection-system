# Build a custom Airflow image with all deps baked in
ARG AIRFLOW_VERSION=3.0.2
ARG PYTHON_VERSION=3.9
FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

# Install OS-level build tools for any Python wheels (e.g. psycopg2)
USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential libpq-dev \
  && rm -rf /var/lib/apt/lists/*

USER airflow

# Copy & install Python dependencies
COPY ../../pyproject.toml ../../poetry.lock* /opt/airflow/
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir poetry \
  && poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi --no-dev

# Bake in our DAGs and plugins for fast startup
COPY dags/    /opt/airflow/dags/
COPY plugins/ /opt/airflow/plugins/
