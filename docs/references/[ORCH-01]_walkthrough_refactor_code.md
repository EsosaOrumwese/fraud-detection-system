Let’s walk through each of your orchestration files end-to-end, unpacking every line, command and stanza so you see exactly what’s happening and why. We’ll start with the **Dockerfile**, then move on to **docker-compose.yml**, the **bootstrap.sh** script, the **CI workflow**, the **smoke-test**, and finish with the **Makefile**. Wherever practical, I’ll call out production-grade rationale.

---

## 1. `Dockerfile`

```dockerfile
# Build a custom Airflow image with pinned deps at build time
# (uncommented build: . in compose → picks this Dockerfile)

ARG AIRFLOW_VERSION=3.0.2
ARG PYTHON_VERSION=3.11
FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}
```

1. **`ARG AIRFLOW_VERSION=3.0.2`** and
   **`ARG PYTHON_VERSION=3.11`** declare build-time variables. By pinning them, every build uses exactly Airflow 3.0.2 on Python 3.11.
2. **`FROM apache/airflow:…`** pulls the official base image matching those versions. This ensures you start from a community-tested snapshot.

```dockerfile
# Install OS-level libs for wheels (e.g. psycopg2); clean up apt lists

USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential libpq-dev \
  && rm -rf /var/lib/apt/lists/*
```

3. **`USER root`** switches to the root user so we can install OS packages.
4. **`RUN apt-get update && apt-get install …`** brings in build tools (`build-essential`) and PostgreSQL headers (`libpq-dev`), needed for compiling Python packages like `psycopg2`.
5. **`rm -rf /var/lib/apt/lists/*`** deletes the apt cache to keep the final image small.

```dockerfile
USER airflow
```

6. **`USER airflow`** drops back to the unprivileged `airflow` user—preventing accidental root actions at runtime and following the principle of least privilege.

```dockerfile
# Copy & install your exact Python requirements
# Changed: moved pip installs to build time for immutable images
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r /tmp/requirements.txt
```

7. **`COPY requirements.txt /tmp/requirements.txt`** brings in your pinned `apache-airflow[celery,redis,postgres]==3.0.2` plus any extras.
8. **`pip install --upgrade pip`** ensures we’re on the latest installer, avoiding older `pip` quirks.
9. **`pip install -r /tmp/requirements.txt`** installs your exact dependencies at build time—so the image is immutable, reproducible, and fast to start.

```dockerfile
# Bake in your DAGs and plugins for faster container startup
COPY dags/    /opt/airflow/dags/
COPY plugins/ /opt/airflow/plugins/
```

10. **`COPY dags/ …`** and **`COPY plugins/ …`** include your workflow code and any custom operators/plugins in the image. At runtime, no external mounts are needed to see your DAGs.

---

## 2. `docker-compose.yml`

```yaml
# Licensed to the Apache Software Foundation (ASF) under one
# …
```

* **License header** acknowledges the ASF template we built from.

### 2.1 Common Anchors

```yaml
x-airflow-common: &airflow-common
  build: .
  environment:
    &airflow-common-env
    AIRFLOW__CORE__EXECUTOR: CeleryExecutor
    AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
    AIRFLOW__CELERY__BROKER_URL: redis://:@redis:6379/0
    AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://airflow:airflow@postgres/airflow
    AIRFLOW__CORE__FERNET_KEY: ''
    AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: 'true'
    AIRFLOW__CORE__LOAD_EXAMPLES: 'true'
    AIRFLOW__CORE__EXECUTION_API_SERVER_URL: 'http://airflow-apiserver:8080/execution/'
    AIRFLOW__SCHEDULER__ENABLE_HEALTH_CHECK: 'true'
    _PIP_ADDITIONAL_REQUIREMENTS: ${_PIP_ADDITIONAL_REQUIREMENTS:-}
    AIRFLOW_CONFIG: '/opt/airflow/config/airflow.cfg'
  volumes:
    - ${AIRFLOW_PROJ_DIR:-.}/dags:/opt/airflow/dags
    - ${AIRFLOW_PROJ_DIR:-.}/logs:/opt/airflow/logs
    - ${AIRFLOW_PROJ_DIR:-.}/config:/opt/airflow/config
    - ${AIRFLOW_PROJ_DIR:-.}/plugins:/opt/airflow/plugins
  user: "${AIRFLOW_UID:-50000}:0"
  depends_on:
    &airflow-common-depends-on
    redis:
      condition: service_healthy
    postgres:
      condition: service_healthy
```

1. **`build: .`** points at our Dockerfile.
2. **`environment:`** block sets Airflow’s core configuration via environment variables—no need to edit `airflow.cfg` by hand.
3. **`FERNET_KEY`** left blank here—supplied at runtime via `.env`.
4. **`volumes:`** bind your local `dags`, `logs`, `config`, and `plugins` directories into the container.
5. **`user:`** maps container files back to your host’s UID (set in `.env`).
6. **`depends_on:`** with `condition: service_healthy` ensures no service starts until Postgres and Redis pass their healthchecks.

### 2.2 Core Services

#### Postgres

```yaml
postgres:
  image: postgres:15
  environment:
    POSTGRES_USER: airflow
    POSTGRES_PASSWORD: airflow
    POSTGRES_DB: airflow
  volumes:
    - postgres-db-volume:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD", "pg_isready", "-U", "airflow"]
    interval: 10s
    timeout: 10s
    retries: 5
    start_period: 5s
  restart: always
```

* **`image: postgres:15`** pins your metadata store.
* **`healthcheck:`** probes `pg_isready` so dependent services wait until it’s truly ready.
* **`restart: always`** auto-recovers the database in case of crashes.

#### Redis

```yaml
redis:
  image: redis:7.2-bookworm
  expose: ["6379"]
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 30s
    retries: 50
    start_period: 30s
  restart: always
```

* **`redis-cli ping`** returns “PONG” when the broker is healthy.

#### airflow-init

```yaml
airflow-init:
  <<: *airflow-common
  entrypoint: /bin/bash
  command: ["-c", |
    if [[ -z "${AIRFLOW_UID}" ]]; then export AIRFLOW_UID=$(id -u); fi
    mkdir -p /opt/airflow/{logs,dags,plugins,config}
    /entrypoint airflow db upgrade
    /entrypoint airflow users create \
      --username "${_AIRFLOW_WWW_USER_USERNAME:-airflow}" \
      --firstname "Admin" \
      --lastname "User" \
      --role Admin \
      --email admin@example.com
    chown -R "${AIRFLOW_UID}:0" /opt/airflow
  ]
  environment:
    <<: *airflow-common-env
    _AIRFLOW_DB_MIGRATE: 'true'
    _AIRFLOW_WWW_USER_CREATE: 'true'
    _AIRFLOW_WWW_USER_USERNAME: ${_AIRFLOW_WWW_USER_USERNAME:-airflow}
    _AIRFLOW_WWW_USER_PASSWORD: ${_AIRFLOW_WWW_USER_PASSWORD:-airflow}
    _PIP_ADDITIONAL_REQUIREMENTS: ''
  user: "0:0"
  restart: always
```

* Runs as root to **create directories**, **upgrade the DB**, **create the admin user**, and **fix ownership**.
* `depends_on` inherited from the common anchor makes it wait on Postgres and Redis.

#### airflow-apiserver / airflow-scheduler / airflow-dag-processor / airflow-worker / airflow-triggerer / flower

Each of these services:

* **Inherits** the common anchor’s build, env, volumes, user, and `depends_on`.
* **Specifies** a `command:` matching its role (e.g. `api-server`, `scheduler`, `dag-processor`, `celery worker`, `triggerer`, `celery flower`).
* **Defines** a tailored `healthcheck:`—either HTTP (`curl --fail …/api/v2/version`) or CLI (e.g. `airflow jobs check --job-type TriggererJob`).
* **Sets** `restart: always` so a crash auto-heals.

At the bottom:

```yaml
volumes:
  postgres-db-volume:
```

declares the named volume for Postgres data.

---

## 3. `bootstrap.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
```

* Fails fast on errors or unset variables.

```bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"
```

* Computes the script’s own directory, then points `ENV_FILE` to the compose root’s `.env`.

```bash
if [[ -f "$ENV_FILE" ]]; then
  echo ".env already exists, skipping"
  exit 0
fi
```

* Ensures idempotency—won’t overwrite existing secrets.

```bash
python - << 'PYCODE'
import base64, os, secrets, pathlib, platform
env_path = pathlib.Path(__file__).parent.parent / '.env'
lines = [
    f"FERNET_KEY={base64.urlsafe_b64encode(os.urandom(32)).decode()}",
    f"SECRET_KEY={secrets.token_urlsafe(32)}",
    f"AIRFLOW_UID={os.getuid() if hasattr(os, 'getuid') else 50000}",
    ("IMAGE_ARCH_SUFFIX=-arm64" if platform.machine().startswith("arm") else "")
]
env_path.write_text("\n".join([l for l in lines if l]) + "\n")
print(f"✓ Created .env at {env_path}")
PYCODE
```

* **Generates:**

  * A 32-byte URL-safe **FERNET\_KEY**.
  * A random **SECRET\_KEY**.
  * The host’s **AIRFLOW\_UID** (fallback 50000).
  * An optional **IMAGE\_ARCH\_SUFFIX** for ARM/x86 builds.
* Writes them into `.env`, so Compose can pick them up automatically.

---

## 4. CI Workflow (`.github/workflows/ci.yml`)

```yaml
orchestration-test:
  needs: test
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
```

1. **Checkout** the PR’s code so we test exactly those changes.

```yaml
    - name: Build & start Airflow stack
      working-directory: orchestration/airflow
      run: |
        docker compose build --pull
        docker compose up -d --wait
```

2. **`build --pull`** fetches the latest base images and builds your custom image.
3. **`up -d --wait`** spins up all services and waits for every healthcheck to pass.

```yaml
    - name: Smoke-test webserver health
      run: curl --fail http://localhost:8080/api/v2/version
```

4. **Health-endpoint check:** Fails the job if the API isn’t responding, catching migration or config errors.

```yaml
    - name: Tear down stack
      working-directory: orchestration/airflow
      run: docker compose down -v
```

5. **Tear down** everything (containers + volumes) so the runner stays clean.

---

## 5. Smoke-Test Script (`test_airflow_compose.py`)

```python
import subprocess
import pytest

def test_compose_config_has_healthchecks():
    # ...
    output = subprocess.check_output(["docker", "compose", "config"])
    assert "healthcheck" in output.decode()
```

* **Verifies** that your `docker-compose.yml` includes at least one `healthcheck` stanza—ensuring you didn’t strip them out.

---

## 6. `Makefile` Targets

```makefile
AIRFLOW_DIR = orchestration/airflow
COMPOSE = docker compose -f $(AIRFLOW_DIR)/docker-compose.yml

airflow-up:
    $(COMPOSE) up -d --wait

airflow-down:
    $(COMPOSE) down -v
```

* **`airflow-up`** wraps the full `up -d --wait` command so you don’t have to type the path.
* **`airflow-down`** tears down the cluster and volumes.

## 7. `requirements.txt`
Your Airflow line is perfect—locking in exactly Airflow 3.0.2 with the Celery, Redis and Postgres extras. However, **both** `connexion[swagger-ui]` and `flask<2.3.0` are still floating, meaning a fresh build today could pull in newer minor or patch releases (and potentially break your image later on). To guarantee immutability you should pin those too.

A more “static” requirements.txt might look like:

```text
# Core Airflow + CeleryExecutor, Redis broker, Postgres backend
apache-airflow[celery,redis,postgres]==3.0.2

# Connexion & Swagger UI support for the API-server
# pin to the current tested version
connexion[swagger-ui]==2.14.2

# Pin Flask to a known good release
flask==2.2.5
```

> **Why this matters:**
>
> * **Reproducibility:** Every `docker build` will install the same patch of Flask and Connexion you’ve tested against.
> * **Safety:** You avoid surprises if, say, Connexion 3.0 drops a breaking change or Flask 2.2.x removes your JSON encoder.
> * **CI consistency:** Your smoke tests and integration tests run against the exact same libraries on every PR.

If you’re not sure which exact versions you’ve been developing with, run inside your dev venv:

```bash
pip freeze | grep -E 'connexion|Flask'
```

and copy those versions into your requirements.txt. From now on, any library you rely on—no matter how small—should be version-pinned for production-grade immutability.

---

### Bringing it all together

1. **Run** `./scripts/bootstrap.sh` → generates `.env`.
2. **Run** `make airflow-up` → builds and spins up your full CeleryExecutor cluster with healthchecks.
3. **Browse** `http://localhost:8080` → Airflow UI shows your DAGs, logs, and metrics.
4. **Run** `make airflow-down` → clean teardown.

Each line—from the Dockerfile’s `USER airflow` to the Compose’s `condition: service_healthy`—exists to guarantee your cluster is **reproducible**, **resilient**, and **production-aligned**, not just a throwaway demo. Let me know if any step needs deeper clarification!

## Workflow
Here’s how your **local orchestration workflow** unfolds, step-by-step via your Makefile, and then how that orchestration layer slots into the broader end-to-end flow of your fraud-detection project.

---

### A. Local Orchestration Workflow

All of these targets live under the “Orchestration: Airflow” section of your Makefile .

1. **`make airflow-bootstrap`**

   * **What it does:**
     Runs `scripts/bootstrap.sh`, which generates a `.env` next to your `docker-compose.yml`. That file contains:

     * A random Fernet key (`FERNET_KEY`) for encrypting Airflow connections
     * A Flask secret key (`SECRET_KEY`) for the web UI sessions
     * Your host’s UID (`AIRFLOW_UID`) so volume permissions line up
     * (Optionally) an `IMAGE_ARCH_SUFFIX` for ARM vs x86 containers
   * **Why it matters:**
     Without this, `docker compose up` would fail on missing required vars (`${FERNET_KEY:?}`) or create root-owned files that your non-root Airflow user can’t access.

2. **`make airflow-build`**

   * **What it does:**
     Invokes

     ```bash
     docker compose --env-file .env build
     ```

     which picks up your custom `Dockerfile` (with pinned dependencies and baked-in DAGs/plugins), and produces the immutable Airflow image.

3. **`make airflow-up`**

   * **What it does:**

     ```bash
     make airflow-bootstrap
     docker compose --env-file .env up airflow-init
     docker compose --env-file .env up -d --wait
     ```

     * **`airflow-init`** runs first (in a one-off container):

       * Creates any missing folders (`dags`, `logs`, `plugins`, `config`)
       * Runs `airflow db upgrade` to apply migrations
       * Bootstraps the admin user
       * Chowns `/opt/airflow` to your `AIRFLOW_UID`
     * **Long-running services** then start in parallel:
       `airflow-apiserver`, `airflow-scheduler`, `airflow-dag-processor`, `airflow-triggerer`, `airflow-worker`, (and optional `flower`), each waiting on Postgres/Redis health.
   * **Why it matters:**
     The `--wait` flag blocks until every healthcheck passes—no race conditions, no “UI is up but DB isn’t” errors.

4. **Inspecting the Running Cluster**

   * **Web UI:** Open your browser to `http://localhost:8080` to view DAGs, trigger runs, and tail logs inline.
   * **Logs tailing:**

     ```bash
     make airflow-logs
     ```

     streams `docker compose logs -f airflow-apiserver`, giving you continuous insight into scheduler heartbeats, API requests, etc.

5. **`make airflow-down`**

   * **What it does:**

     ```bash
     docker compose --env-file .env down || true
     ```

     Stops and removes all containers (but leaves volumes intact).

6. **Optionally, `make airflow-reset`**

   * **What it does:**
     After `airflow-down`, it also deletes your Postgres volume and logs:

     ```bash
     rm -rf orchestration/airflow/postgres-db-volume orchestration/airflow/logs/*
     ```
   * **Why it matters:**
     Gives you a truly clean slate if you suspect schema drift or want to purge all state.

---

### B. Integrating Orchestration into Your End-to-End Workflow

Your Makefile already orchestrates Terraform, data generation, Great Expectations, modelling, and now Airflow. A typical **full-project** flow might look like this:

1. **Infrastructure provisioning**

   ```bash
   make tf-init        # terraform init
   make tf-plan        # terraform plan -var-file=terraform.tfvars
   make tf-apply       # terraform apply plan.out
   ```

   This stands up your VPC, S3 buckets, IAM roles, budgets and alarms in AWS.

2. **Data generation & validation**

   ```bash
   make gen-data       # generate synthetic Parquet & validate with GE
   ```

3. **Baseline modelling & tracking**

   ```bash
   make ml-train       # run your sklearn + XGBoost baseline with MLflow tracking
   make mlflow-ui-start  # (optional) spin up MLflow UI to inspect experiments
   ```

4. **Repository CI/CD**

   * Every PR runs unit tests, mypy, Black, security scans (Trivy, Checkov), and Infracost (via your CI workflows).
   * Now **orchestration-test** kicks off:

     ```yaml
     docker compose build --pull
     docker compose up -d --wait
     curl --fail http://localhost:8080/api/v2/version
     docker compose down -v
     ```

     ensuring your Airflow stack is always PR-ready.

5. **Local end-to-end validation**
   After provisioning infra and generating data locally, you can:

   ```bash
   make airflow-up
   # wait for UI → trigger your dag(s) manually or wait for schedule
   make airflow-logs  # tail logs, confirm tasks ran
   make airflow-down
   ```

6. **Promotion to Staging & Production**

   * **Staging:** push your custom image to your registry, update your Compose (or Helm chart) to pull `airflow-custom:3.0.2-<sha>`, and redeploy; smoke tests run automatically.
   * **Production:** follow the same process, guarded by Infracost checks and budget alarms.

Throughout this flow, **orchestration** sits at the heart of your daily pipelines—after data is ready and baseline models exist, Airflow codifies the schedule, handles retries, logs every run to MLflow, and materializes features into Feast. By fitting `make airflow-*` cleanly alongside `make gen-data`, `make ml-train`, and `make tf-*`, you have a single command surface for the entire project lifecycle: from infra to ML.

---

**Does this align with what you had in mind?** If you’d like to drill into any specific integration (e.g. how Airflow triggers your existing data-generation scripts or wires into MLflow), let me know!
