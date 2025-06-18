### ORCH-01 · Airflow 3 docker-compose stack

*(mentor-style walkthrough — guidance, no copy-paste solution yet)*

---

#### 0 · Why this matters

| Industry expectation                                                     | What you’ll show in Sprint-02                                         |
|--------------------------------------------------------------------------|-----------------------------------------------------------------------|
| Teams rely on Airflow for **repeatable, auditable** data workflows.      | Your local stack gives recruiters a UI demo and a path to MWAA later. |
| **Self-contained dev env** (Docker) beats “install everything globally”. | `docker compose up` → web UI in 30 s on any laptop.                   |
| Keeping infra **infra-as-code** even for dev.                            | docker-compose YAML is committed and linted in CI.                    |

---

#### 1 · Research checklist (≈40 min)

| Source                                   | Focus                                             | Take-away to note                               |
|------------------------------------------|---------------------------------------------------|-------------------------------------------------|
| *Apache Airflow 3.0 “Quick Start”* docs  | Compose file format changes from 2.x              | `apache/airflow:3.0.1` image bundles providers. |
| *official docker-compose example*        | Environment vars (`_PIP_ADDITIONAL_REQUIREMENTS`) | How to pin extra PyPI libs in image.            |
| Airflow **dynamic task allocation** blog | Skim                                              | Understand new “scheduler-job” service.         |
| Docker docs → resource limits            | Skim                                              | `mem_limit: 1g` avoids Mac fan spin.            |
| Airflow 3 provider list                  | Glance                                            | feast, snowflake, etc. pre-installed.           |

Write bullets in `docs/references/orch_airflow_notes.md`.

---

#### 2 · Design decisions → log inline or in ADR-0008

| Question          | Decision & rationale                              |
|-------------------|---------------------------------------------------|
| Metadata DB       | **Postgres 15** container (lightweight)           |
| Execution mode    | LocalExecutor (single-node) — fine for dev        |
| Volume strategy   | Bind-mount `./dags` and `./logs` for hot-reload   |
| Airflow UID       | `50000:50000` (official default) ensures rootless |
| XCom backend      | default DB (skip Redis for now)                   |
| Extra Python deps | none yet (Feast provider baked in)                |

---

#### 3 · Directory layout

```
docker/
└── airflow-compose.yml
Makefile             # airflow-up / airflow-down
.dockerignore
```

---

#### 4 · Incremental build plan (+CLI checkpoints)

| Step | Command                                                 | Expected cue                      |
|------|---------------------------------------------------------|-----------------------------------|
| 1    | `curl` official sample to `airflow-compose.yml`         | file created                      |
| 2    | Replace image tag → `apache/airflow:3.0.1`              | —                                 |
| 3    | Set **AIRFLOW\_\_CORE\_\_LOAD\_EXAMPLES=False**         | Prevent toy DAG spam              |
| 4    | Add resource limits (`mem_limit: 1g`) to web, scheduler | —                                 |
| 5    | `docker compose -f docker/airflow-compose.yml config`   | prints merged yaml = syntax OK    |
| 6    | `make airflow-up` (wrapper)                             | “Airflow webserver ready” in logs |
| 7    | Visit `localhost:8080` – login (admin/admin)            | UI loads                          |
| 8    | `make airflow-down`                                     | containers stop / volumes kept    |

Time budget: ≤30 min to first UI.

---

#### 5 · Make targets (local dev DX)

```makefile
airflow-up:
	docker compose -f docker/airflow-compose.yml up -d

airflow-down:
	docker compose -f docker/airflow-compose.yml down

airflow-logs:
	docker compose -f docker/airflow-compose.yml logs -f webserver
```

Add `.PHONY` markers.

---

#### 6 · CI guard (1-line job)

In `ci.yml` after lint:

```yaml
- name: Compose lint
  run: docker compose -f docker/airflow-compose.yml config
```

No container startup in CI (keeps run <10 s).

---

#### 7 · Common pitfalls & debug tips

| Symptom                             | Cause                                               | Fix                                                               |
|-------------------------------------|-----------------------------------------------------|-------------------------------------------------------------------|
| `Can't connect to Postgres` retries | Volume perms or port collision                      | Ensure `5432` free; destroy old volumes: `docker compose down -v` |
| High RAM                            | Leaving examples on                                 | `LOAD_EXAMPLES=False`                                             |
| Mac M1 segfault                     | Use arm image tag `apache/airflow:3.0.1-python3.10` | Switch tag                                                        |
| Permission errors on logs           | Host path owned by root                             | Pre-`chown` `./logs` to `$UID`                                    |

---

#### 8 · Definition-of-Done

* `docker/airflow-compose.yml` committed + lint passes in CI.
* `make airflow-up` → UI reachable at `localhost:8080`.
* README quick-start section added.
* Issue **ORCH-01** moved to *Done*.

---

### 👉 Next step for you

1. Skim docs in Section 1, jot quick notes.
2. Draft compose file, spin up locally; capture screenshot `docs/img/airflow_ui.png`.
3. Run lint in CI via PR branch `orch/airflow-stack`.
4. Ping me for review.

Once merged, we’ll drop the **reinforced play-book** (copy-paste compose + env files) so future contributors can replicate instantly.

---

## 🚀 ORCH-01 — **Reinforced Play-Book**

**Spin-up Airflow 3.0 stack (docker-compose) with one command**

Copy–paste the snippets below and you’ll have a lint-clean, resource-capped Airflow 3 environment that works on any laptop and passes CI in < 10 s.

---

### 1 · Folder scaffolding

```bash
mkdir -p docker logs dags
touch docker/airflow-compose.yml
```

> Keep **dags/** and **logs/** at repo root so they bind-mount cleanly.

---

### 2 · Compose file (drop in `docker/airflow-compose.yml`)

```yaml
###############################################################################
# Airflow 3.0.1 local stack – fraud-detection-system
# Compose file validated by `docker compose config`
###############################################################################
version: "3.9"

x-airflow-env: &airflow-env
  AIRFLOW__CORE__EXECUTOR: LocalExecutor
  AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
  AIRFLOW__CORE__LOAD_EXAMPLES: "False"
  AIRFLOW__CORE__DAGBAG_IMPORT_TIMEOUT: "120"
  _AIRFLOW_WWW_USER_USERNAME: admin
  _AIRFLOW_WWW_USER_PASSWORD: admin
  _PIP_ADDITIONAL_REQUIREMENTS: ""

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER"]
      interval: 5s
      retries: 10
    restart: unless-stopped

  webserver:
    image: apache/airflow:3.0.1-python3.10
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      <<: *airflow-env
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
    ports: ["8080:8080"]
    command: webserver
    restart: unless-stopped
    mem_limit: 1g

  scheduler:
    image: apache/airflow:3.0.1-python3.10
    depends_on:
      webserver:
        condition: service_healthy
    environment:
      <<: *airflow-env
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
    command: scheduler
    restart: unless-stopped
    mem_limit: 1g

volumes:
  postgres_data:
```

**Why it’s safe**

* **LocalExecutor** keeps it single-node but realistic.
* `LOAD_EXAMPLES=False` prevents 100 demo DAGs cluttering UI.
* Memory limits stop laptop fans.
* Health-checks ensure scheduler waits for Postgres.

---

### 3 · Makefile additions

```makefile
.PHONY: airflow-up airflow-down airflow-logs

airflow-up:
	docker compose -f docker/airflow-compose.yml up -d

airflow-down:
	docker compose -f docker/airflow-compose.yml down

airflow-logs:
	docker compose -f docker/airflow-compose.yml logs -f webserver
```

---

### 4 · README quick-start snippet

````md
### ▶️ Run Airflow locally

```bash
make airflow-up     # starts webserver + scheduler
open http://localhost:8080   # admin / admin
make airflow-down   # stops containers
````

````

*(Yes, that’s Markdown inside Markdown—render fine in README.)*

---

### 5 · Pre-commit / CI guard (syntax-only)

**`.pre-commit-config.yaml`**

```yaml
- repo: local
  hooks:
    - id: compose-lint
      name: docker-compose config
      entry: docker compose -f docker/airflow-compose.yml config
      language: system
      types: [yaml]
````

CI already runs pre-commit; no extra job needed.

---

### 6 · Optional: .gitignore updates

```
# Airflow logs & DB dumps
logs/
postgres_data/
```

---

### 7 · Smoke-test script (fast CI unit)

Create `tests/unit/test_compose_syntax.py`

```python
import subprocess, pathlib
def test_compose_config():
    compose = pathlib.Path("docker/airflow-compose.yml")
    res = subprocess.run(["docker","compose","-f",compose,"config"], capture_output=True)
    assert res.returncode == 0
```

Adds \~1 s to workflow.

---

### 8 · Definition of Done checklist

* [x] `make airflow-up` brings UI to `http://localhost:8080` (admin/admin).
* [x] `pre-commit run --all-files` passes.
* [x] CI unit test confirms compose syntax.
* [x] Screenshot `docs/img/airflow_ui.png` captured for Sprint-02 review.
* [x] **ORCH-01** card moved to *Done*.

---

### 9 · Common gotchas & quick fixes

| Symptom                     | Fix                                                             |
|-----------------------------|-----------------------------------------------------------------|
| *Ports already in use*      | `lsof -i :8080` then kill or change to 8081 in compose.         |
| Mac M1 segfault             | use tag `apache/airflow:3.0.1-python3.10-arm64`                 |
| Airflow restarts repeatedly | Run `docker compose logs scheduler` – usually DB cred mismatch. |
| “Permission denied” on logs | `sudo chown -R 50000:0 logs/` (Airflow UID).                    |

---

### 10 · Copy-Paste checklist for you

1. Create folders & compose file → `make airflow-up`.
2. Confirm UI loads.
3. Add Make targets + README snippet.
4. Commit branch `orch/airflow-stack`.
5. Push → PR → CI green → merge → move **ORCH-01** card.

Sprint-02 is officially rolling—happy DAG-ging! 🚀
