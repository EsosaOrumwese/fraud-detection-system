## 9. Expert-Level Q\&A Prep

Below is a curated set of advanced “gotcha” areas and talking points—complete with **why** each matters and **how** you’d answer if quizzed by a seasoned DevOps or Data Engineering lead.

---

### 9.1 Containerization Gotchas

1. **Layer-cache invalidation**

   * **Why it matters**: Poorly ordered `COPY`/`RUN` steps force Docker to reinstall deps on every code change, slowing CI and local builds.
   * **How to respond**:

     > “I copy `pyproject.toml` + lockfile first, run `poetry export` and build the wheel, then copy code. This way, dependency resolution is cached unless I explicitly change versions—keeping rebuilds fast.”

2. **UID/GID Mapping & Permissions**

   * **Why it matters**: The non-root `airflow` user inside the container (UID 50000) may not match your host, causing mounted volumes to be unreadable.
   * **How to respond**:

     > “My `bootstrap.sh` captures my host UID and injects it into `.env` as `AIRFLOW_UID`, so the container’s files stay owned by my user on the host—avoiding permission errors without `chmod -R 777` hacks.”

3. **Image Size vs. Build Tools**

   * **Why it matters**: Installing compilers (`build-essential`) and dev-libs (`libpq-dev`) in the final image inflates size and increases surface area.
   * **How to respond**:

     > “For simplicity in dev/CI, I installed build tools in the runtime—but in a hardened production image I’d limit compilers to the builder stage only, copying artifacts into a slim final image.”

---

### 9.2 Orchestration & Docker-Compose Nuances

1. **Service Startup Order & Healthchecks**

   * **Why it matters**: Airflow components fail if Postgres or Redis aren’t fully ready.
   * **How to respond**:

     > “I use `depends_on` with `condition: service_healthy` and custom healthchecks (`pg_isready`, `redis-cli ping`) so Airflow services only start after their dependencies signal healthy.”

2. **Broker Failover & Redis HA**

   * **Why it matters**: A single Redis instance is a single point of failure under CeleryExecutor.
   * **How to respond**:

     > “In our test stack we accept Redis risk for simplicity, but in production we’d deploy a Redis cluster (via AWS ElastiCache or Redis Sentinel) and point `AIRFLOW__CELERY__BROKER_URL` at its VIP.”

3. **Scaling Workers vs. Metadata DB Load**

   * **Why it matters**: More Celery workers can overwhelm the Airflow metadata DB with heartbeats and state writes.
   * **How to respond**:

     > “We limit `max_active_runs` and tune the scheduler’s DAG parsing interval. For larger scale we’d move to the KubernetesExecutor where each task writes its own pod status instead of hammering Postgres.”

---

### 9.3 Airflow-Specific Questions

1. **Executor Choice**

   * **Why it matters**: Different executors suit different scale and infrastructure (Local vs. Celery vs. Kubernetes).
   * **How to respond**:

     > “CeleryExecutor was chosen here for horizontal worker scaling in future sprints. For a single-node PoC, LocalExecutor could suffice—but can’t distribute across machines.”

2. **Backfill vs. Catchup**

   * **Why it matters**: Misconfigured catchup can accidentally trigger massive backfills after downtime.
   * **How to respond**:

     > “We set `catchup=False` to run only the current day, avoiding unintended historical backfills. If backfills are desired, we’d enable catchup or invoke `airflow dags backfill` explicitly.”

3. **Resource Limits on Tasks**

   * **Why it matters**: Long-running PythonOperators can OOM/killed if not bounded.
   * **How to respond**:

     > “In Compose you can specify `deploy.resources.limits` (Docker Swarm) or Docker run flags (`--memory`, `--cpus`). In KubernetesExecutor, we’d define pod resource requests/limits in the Helm chart.”

---

### 9.4 Operational & Security Considerations

1. **Secret Rotation**

   * **Why it matters**: Hard-coded Fernet/API keys or long-lived AWS creds risk compromise.
   * **How to respond**:

     > “Our `bootstrap.sh` can be re-run to generate new Fernet and Flask keys. In prod, we’d integrate with Vault or AWS Secrets Manager and mount secrets at container startup—avoiding persistently stored `.env` files.”

2. **Log Aggregation & Monitoring**

   * **Why it matters**: Local Docker logs aren’t sufficient for production incident response.
   * **How to respond**:

     > “We mount logs out of containers, so a sidecar or log-forwarder (e.g. Fluentd) can pick them up. In AWS we’d push logs to CloudWatch or ELK for centralized dashboards and alerting.”

3. **CI/CD Parity with Production**

   * **Why it matters**: Divergence between local Compose and production (Helm/Kubernetes) can cause “works on my machine” failures.
   * **How to respond**:

     > “Our GitHub Actions mirrors local commands (`airflow-bootstrap`, `build`, `up`), and we smoke-test with `airflow tasks test`. As we transition to prod, we’ll align our Helm values with these same env vars and healthchecks.”

---

By internalizing these points—**why** each configuration or pattern exists, and **how** you’d defend the trade-offs—you’ll be ready to engage any DevOps/Data Engineering expert on your Docker-and-Airflow setup with confidence.
