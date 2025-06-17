# Lesson Plan 
Below is our conversational lesson plan for ORCH-01—a deep dive into standing up a production-grade Airflow 3 CeleryExecutor stack on Docker. I’ve turned each module into a flowing narrative, weaving in the probing questions I’ll ask you, the research threads we’ll explore, and the concrete production-grade tips that distinguish this from an academic toy project. At the end, you’ll find a set of comprehension questions to test your understanding.

---

## 1. Discovering Why Orchestration Matters

We begin by painting the picture of life without an orchestrator. Imagine you’ve written a suite of Python scripts—one to generate synthetic transactions, one to materialize features into Feast, another to launch a model training job—and you simply call them in sequence inside a Jupyter notebook or a `cron` job. When everything runs perfectly, you pat yourself on the back; but what happens when your data generator fails halfway through? Or the network hiccups just as your feature-store upload begins? In this setup, you fall back to manual intervention: you log into a server, sift through scattered log files, re-run only the failed steps, and pray you remembered all the flags and parameters. That painful, ad-hoc process is exactly what orchestration solves.

* **Questions I’ll ask you:**
  “If one task in your pipeline fails, how would you currently detect and retry it? Where do you capture the outputs or metrics of each run?”
  As we dig deeper: “What is a Directed Acyclic Graph (DAG)? Why does modeling dependencies explicitly help you avoid mysterious race conditions or silent failures?”

* **Production tip:**
  In a real world team you rarely check emails. Instead, you hook task failures into alerting systems—Slack channels, PagerDuty, or email with rich context (task name, run ID, logs link). Even in your laptop-only dev environment, practice sending a dummy Slack notification on failure; you’ll thank yourself when your first real alert arrives at 3 AM in production.

* **Contrast with academia:**
  A classroom example often runs once on a toy dataset; robustness isn’t emphasized. In production, you must guarantee that tomorrow’s run with new data behaves the same way, with clear recovery strategies and audit trails.

---

## 2. Unpacking Airflow’s Micro-Service Architecture

Next, we step through the official Apache template and unpack each container’s responsibility. You’ll see how a modern Airflow deployment splits brain from brawn:

1. **`airflow-init`** is our one-time initializer. It runs database schema migrations (`airflow db upgrade`), creates the first admin user, and fixes file permissions. By isolating these steps, we avoid bloated startup logic in every service and guarantee the metadata database is ready before anyone tries to talk to it.

2. **`airflow-apiserver`** (formerly webserver) hosts the UI and the REST API. It’s your playground to visualize DAGs, trigger manual runs, and inspect logs.

3. **`airflow-scheduler`** continuously polls the DAG definitions stored in your code repository, looks at the DAG’s schedule, and enqueues task instances into the Celery queue when they are due.

4. **`airflow-dag-processor`** parses Python DAG files in isolation, validating syntax and DAG structure before injecting them into the scheduler’s database. Splitting this job out means you can tune its resource limits separately.

5. **`airflow-triggerer`** powers deferrable operators (e.g. sensors that wait on external services without occupying a worker slot). Offloading that work ensures your heavy compute tasks aren’t blocked.

6. **`airflow-worker`** runs the actual Python task code (your data generator, Feast materializer, model training). You can scale the number of workers independently of the schedulers.

7. **`flower`** (optional) is a small web UI to monitor Celery’s internal state—queues, active tasks, worker heartbeats.

Behind the scenes, **Postgres** holds Airflow’s metadata (task states, DAG definitions, logs), and **Redis** acts as the broker for Celery (dispatching work from scheduler to workers).

* **Questions I’ll ask you:**
  “Why would you not want to run the scheduler and worker in the same process? What happens if a sensor blocks a worker thread?”
  Then: “Deferrable operators use the triggerer—how does that conserve resources compared to a polling sensor?”

* **Production tip:**
  In staging or prod you’ll likely run multiple scheduler replicas behind a load-balancer, autoscale workers based on queue depth, and mount Postgres and Redis on dedicated high-availability clusters. Even if you start with one of each locally, design your Compose file with anchors and minimal coupling so scaling up is straightforward.

* **Production vs. academic:**
  A tutorial DAG can live inside one process; a real pipeline serving thousands of transactions per day demands separation for stability, observability, and scale.

---

## 3. Why We Containerize: The Docker Imperative

Before we write a single line of Compose, we need to understand why Docker is non-negotiable in modern MLOps:

* **Reproducibility:** A container bundles your exact Linux base, Python version, and library versions. When you—and every team member—run `docker-compose up`, you know you’re on identical terrain. No more “I have Pandas 1.5.2, you have 1.5.3, and your code breaks.”

* **Isolation:** Your Airflow stack’s dependencies (e.g. `apache-airflow[celery,redis,postgres]`) won’t collide with your host’s Python or other projects on your machine.

* **Parity with Production:** Most enterprises deploy Airflow on Kubernetes or ECS. Comfort with Docker Compose translates directly to Helm charts and task definitions.

Once we accept containers, we write a **custom Dockerfile** instead of relying on runtime dependency injection. The official quick-start uses `_PIP_ADDITIONAL_REQUIREMENTS` to install packages on container startup—a pattern that delays container readiness and creates non-deterministic builds. In contrast, our Dockerfile:

1. **Starts** from the official `apache/airflow:3.0.2-python3.11` image, ensuring we’re aligned with the ASF’s tested base.
2. **Switches to `root`** to install OS libraries (`libpq-dev`, `build-essential`) required for compiling wheels like `psycopg2`.
3. **Reverts to `airflow` user** (least privilege) and copies in your `requirements.txt`.
4. **Runs `pip install`** at build time, locking versions and creating a fast, immutable image.
5. **Bakes in your DAGs and plugins** so the container is fully operational the moment it starts.

   * **Questions I’ll ask you:**
     “What would happen if your host’s pip version changed? How do you ensure your CI runner sees the same dependencies you used locally?”
     “Why do we need OS-level packages for wheels, and what happens if you omit them?”

   * **Production tip:**
     Tag and push your built image to a private registry (e.g. ECR, GCR) with a semantic version. In your CD pipeline, deploy by digest, ensuring no implicit upgrades ever slip through.

---

## 4. Wiring It Up: The Docker Compose Blueprint

With a custom image in hand, we move on to the heart of ORCH-01: a Compose file that mirrors the official ASF template exactly. We start by defining a common anchor, `x-airflow-common`, containing our build context, environment variables (executor type, DB URI, broker URL, Fernet key placeholder), volumes, and user mapping. We then define another anchor, `x-airflow-common-depends-on`, listing Postgres and Redis with `condition: service_healthy`. This DRYs our YAML and ensures every Airflow service waits for its dependencies.

Each service block—`airflow-apiserver`, `airflow-scheduler`, `airflow-dag-processor`, `airflow-worker`, `airflow-triggerer`, and `airflow-init`—unwraps this anchor, specifies its unique `command`, healthcheck stanza (`test`, `interval`, `timeout`, `start_period`, `retries`), and `restart: always` policy. We define:

* **HTTP-based healthchecks** for the webserver and API endpoints.
* **CLI or Celery ping checks** for scheduler, worker, and triggerer.
* **`depends_on: condition: service_completed_successfully`** on the init container so nothing runs until migrations and user bootstrap finish.

  * **Questions I’ll ask you:**
    “How does `start_period` differ from `timeout` in a healthcheck? Why do we need both?”
    “Why do we explicitly set `restart: always`? What happens if a container crashes?”

  * **Production tip:**
    In Kubernetes you’d translate each healthcheck to liveness and readiness probes; the `restart` policy becomes a `restartPolicy: Always`. Keep your Compose file structured so you can copy-paste probes into your Helm values.

---

## 5. Managing Secrets & Permissions with Bootstrap

Rather than commit sensitive values, we provide a simple Bash script, `bootstrap.sh`, that generates:

* A cryptographically secure `FERNET_KEY` for Airflow’s connection encryption.
* A random `SECRET_KEY` for the web UI’s Flask session.
* The host’s user ID (`AIRFLOW_UID`) so mounted volumes—DAGs, logs, plugins, config—inherit the correct ownership and avoid “permission denied” errors.

The script computes its own directory, writes a `.env` in that folder, and exits idempotently if the file already exists. When you run `docker compose up`, Docker automatically loads `.env` and injects those variables.

* **Questions I’ll ask you:**
  “Why is a Fernet key necessary? What data does it protect?”
  “What file-permission errors have you encountered when mounting from Windows or Linux? How does mapping `AIRFLOW_UID` help?”

* **Production tip:**
  In real deployments you’d swap this script for a secrets manager integration—retrieving keys from AWS SSM, HashiCorp Vault, or Kubernetes Secrets—but the pattern of externalizing secrets remains the same.

---

## 6. CI/CD & Smoke-Testing for Confidence

We integrate an orchestration-test job into your GitHub Actions pipeline so that every pull request is validated end-to-end:

1. **Checkout** your repo.
2. **Bootstrap** the environment (`.env`) and **build** the Docker image.
3. **Spin up** the full Compose stack with `docker compose up -d --wait`, pausing until every healthcheck passes.
4. **Hit** the Airflow API version endpoint (`curl --fail http://localhost:8080/api/v2/version`), verifying the entire stack is alive.
5. **Tear down** the cluster (`docker compose down -v`) so the runner stays clean.

This catches syntax errors, missing files, conflicting ports, or permission issues before any code merges.

* **Questions I’ll ask you:**
  “What’s the risk of never spinning up the stack in CI and only linting YAML?”
  “How would you extend the smoke test to actually schedule a dummy DAG and assert it runs?”

* **Production tip:**
  As your confidence grows, add an integration test that deploys a minimal “hello-world” DAG, waits for its successful completion, and then tears down. That’s as close as you can get to production testing in CI.

---

## 7. Scaling, Observability & Hardening

Finally, we discuss how to evolve this local stack toward production readiness:

* **Resource Constraints:** We show both Compose-level `mem_limit`/`cpus` and Swarm `deploy:` blocks so you never overwhelm your host or a shared dev server.
* **Monitoring & Metrics:** We talk about exposing `/metrics` endpoints, integrating Prometheus exporters into Airflow, and shipping logs to ELK or CloudWatch.
* **Security Scanning:** We bake `trivy scan` and `checkov` into the CI pipeline so no image or Terraform code ever goes live without a clean bill of health.

  * **Questions I’ll ask you:**
    “How would you scrape Airflow’s internal metrics for queue lengths or task durations?”
    “What policies would you enforce if you needed PCI-DSS compliance on your fraud-detection pipeline?”

  * **Production tip:**
    Always run incremental security scans. A nightly full image scan plus a pre-deployment light scan balances coverage and speed.

---

## 8. Bringing It All Together

By the end of our conversation, you’ll have a mental flowchart of:

1. **Running** `bootstrap.sh` to generate secrets.
2. **Building** your custom image.
3. **Launching** the full Airflow micro-service cluster.
4. **Verifying** readiness via healthchecks.
5. **Scheduling** your first DAG and watching logs in the UI.
6. **Automating** the same in CI for every code change.

You’ll also be armed with production-grade talking points—about DRY YAML anchors, healthcheck semantics, image immutability, secrets management, and CI smoke-tests—that will let you confidently explain your work to recruiters or senior engineers.

---

### Check Your Understanding

1. **Initialization Container:** Explain why we isolate database migrations and user creation into a dedicated `airflow-init` service instead of running them inside the `webserver` or `scheduler`.
2. **Healthcheck Semantics:** Describe the difference between `timeout` and `start_period` in a Docker healthcheck and why both matter.
3. **Build-time vs. Runtime Dependencies:** In your own words, why baking packages into the Docker image at build time is superior in a production context to using `_PIP_ADDITIONAL_REQUIREMENTS` at container startup.
4. **CI Smoke Test Extension:** If you wanted to add an integration test that actually runs a “hello-world” DAG in CI, what steps would you add to the job after the API healthcheck?
5. **Environment Parity:** How does running this stack in Docker Compose locally prepare you for deploying on Kubernetes or ECS in production?

Feel free to answer these questions one by one, and I’ll give you feedback on where you’re strong and where we might need another deep dive!

------

## Module 1: Why Orchestration Matters 
I’ll walk you through the core ideas, ask guiding questions as we go, and sprinkle in production tips and contrasts with non‐production projects. When you see a question, pause and think it through or jot down your answer—it’ll help cement the concepts.

### 1.1 The Limits of Manual Pipelines

Imagine your fraud-detection code lives in several Python scripts:

1. **`generate_data.py`**
2. **`compute_features.py`**
3. **`train_model.py`**
4. **`evaluate_and_alert.py`**

A naive “pipeline” might be a single shell script or notebook that calls these in order:

```bash
python generate_data.py && \
python compute_features.py && \
python train_model.py && \
python evaluate_and_alert.py
```

This can work for a one-off experiment. But already you’re facing questions:

* **What if** `compute_features.py` crashes halfway through?
* **How do you** retry only the failed step, without re-running the entire sequence?
* **Where** are the logs for each task stored? How do you search them?
* **How** do you schedule this to run every morning at 2 AM, and ensure you’re notified on failure?

In an academic or beginner setup, you’d open your notebook, re-run the failed cell, and keep working. In production, you need:

* **Automated scheduling** on a reliable cadence.
* **Structured logging** so every task’s output is centrally accessible.
* **Built-in retry logic** (with back-off) for transient failures.
* **Dependency tracking** so task B never runs unless A succeeded.
* **Alerts & metrics** so you know in real time if something goes wrong.

> **Production tip:** Even for a PoC, adopt the habit of writing your logs in a structured format (JSON with timestamp, task name, run ID). It makes downstream monitoring and dashboarding far easier.

---

### 1.2 Enter the Directed Acyclic Graph (DAG)

At the heart of orchestration is the **DAG**—a graph of tasks (nodes) connected by dependencies (edges), with no cycles (you can’t have A → B → A). Why is that important?

* **Explicit dependencies:** You declare that `compute_features` depends on `generate_data`. The orchestrator enforces this.
* **Parallelism:** If `train_model` and `evaluate_and_alert` are independent, they can run in parallel, saving time.
* **Visibility:** You get a visual graph in a UI showing exactly what’s going to run and in what order.

In Airflow, you write something like:

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

def generate_data(): ...
def compute_features(): ...
def train_model(): ...
def evaluate_and_alert(): ...

with DAG('fraud_pipeline', start_date=datetime(2025,1,1), schedule_interval='@daily') as dag:
    t1 = PythonOperator(task_id='generate_data', python_callable=generate_data)
    t2 = PythonOperator(task_id='compute_features', python_callable=compute_features)
    t3 = PythonOperator(task_id='train_model', python_callable=train_model)
    t4 = PythonOperator(task_id='evaluate_and_alert', python_callable=evaluate_and_alert)

    t1 >> t2 >> [t3, t4]
```

Now Airflow’s scheduler reads this DAG, knows when it needs to run, and enqueues each task. If `t2` fails, it retries according to the policy you set (e.g. `retries=3, retry_delay=10m`), logs every attempt, and sends an alert if it still fails.

> **Production tip:** Always set sensible retry policies. For transient infra issues (like a timed-out S3 upload), retries with exponential back-off can dramatically reduce false alarms.

---

### 1.3 Scheduling and Backfills

Suppose your DAG’s schedule is daily at 2 AM. Airflow’s scheduler will:

1. **Trigger** a run at 2025-06-18 02:00 (for data of the previous day).
2. **Enqueue** each task in the correct order.
3. **Record** the run in its metadata DB, with status `running`, then `success` or `failed`.

If your team missed yesterday’s 2 AM run (perhaps the scheduler was down), you can **backfill** or “catch up” historical DAG runs. Airflow will let you trigger runs for past dates, ensuring no data gap.

> **Guiding question:** How would you handle the situation where your feature computation depends on yesterday’s model output? How does airflow’s DAG help enforce that?

---

### 1.4 Centralized Logging and Monitoring

Your notebook-based approach might write logs to `stdout`, or files in various directories. Searching across tasks and hosts becomes a nightmare. With Airflow:

* **Logs for every task instance** are stored in a central folder (e.g. `./logs/<dag_id>/<task_id>/<run_id>/*.log`).
* The web UI shows you logs inline, with clickable links.
* You can configure log shipping to S3 or Elasticsearch for long-term storage and powerful search.

> **Production tip:** Ship logs to an ELK stack or CloudWatch. Then hook up anomaly detection on error rates and task latencies to catch slowdowns or new failures.

---

### 1.5 Retry Logic and Alerting

In a notebook, you’d manually re-run a failed cell. In cron, you might wrap your shell script with a simple `|| mail -s “Job failed” me@example.com`. But:

* **Emails** get lost.
* **Logs** are unwieldy attachments.
* **Retries** are brutal: you either retry the whole script or nothing.

Airflow gives you:

* **Per-task retry policies**, with customizable delays.
* **Dead-letter alerting**: if retries exhaust, it can send Slack, PagerDuty, or email alerts—complete with context (DAG run URL, log link).
* **On-failure callbacks**: run a separate task when a failure happens, to gather metrics or escalate.

> **Guiding question:** If your `train_model` task fails three times due to an intermittent GPU shortage, how do you decide on retry parameters? What’s your SLA for model training success?

---

### 1.6 Production vs. Academic

Let’s tie these ideas back to our key theme: **production-grade** orchestration means:

* **Repeatability:** Automated scheduling, backfills, and no manual interventions.
* **Resilience:** Retries, alerts, and no silent failures.
* **Visibility:** Central UI for DAGs, logs, metrics.
* **Scalability:** Parallelism and decoupling of scheduler vs. workers.

By contrast, an academic proof-of-concept might:

* Run once on a toy dataset.
* Use a single Python process or simple cron job.
* Capture logs in a text file you ssh into.
* Manually re-run failed steps.

Orchestration is what elevates your work from “it runs on my laptop” to “it reliably runs every day for years, under varying loads and conditions.”

---

## 1.7 Quick Recap of Key Questions

1. **Failure Handling:** If `compute_features.py` fails halfway, how does Airflow’s DAG structure and retry policy solve the problem?
2. **Dependency Enforcement:** Why can’t we just sequentially call scripts in a shell script? What do we gain from a DAG?
3. **Logging Centralization:** How does Airflow make logs more searchable and less error-prone than plain-old text files?
4. **Alerts & SLAs:** In production, what’s a better alternative to simple email notifications, and why?

Take a moment to reflect and jot down your answers. When you’re ready, we’ll move on to **Module 2: Airflow 3 Architecture** and see how each micro-service plays its own role in this orchestration symphony.

-----

Great—let’s dive into **Module 2: Airflow 3 Architecture & Service Roles**. We’ll explore each component of the Docker-Compose stack, understand its responsibility, why it’s split out, and how that pattern differs from a simple, all-in-one proof-of-concept. Along the way I’ll pose questions for you to reflect on, suggest research directions, and highlight production best practices.

---

### 2.1 The Rationale for Micro-Services in Airflow

When you first encounter Airflow, it may seem like “just another Python library with decorators,” but under the hood it’s evolved into a small ecosystem of tightly-focused services. Rather than running everything in a single process—scheduler, webserver, workers—all living together, Airflow 3’s recommended Docker-Compose splits them into distinct containers:

* **Initialization**
* **API/Web UI**
* **Scheduler**
* **DAG Processor**
* **Triggerer**
* **Workers**
* **Optional Flower**

Plus external dependencies: **Postgres** for metadata and **Redis** for the Celery broker.

#### Why split it this way?

In a monolithic setup, a bug in one component (say, the web UI) could consume all resources and bring down your scheduler or block workers. By isolating each role:

* **Failure Isolation:** If the DAG processor hits a syntax error in one DAG, it won’t crash the scheduler or block worker slots.
* **Independent Scaling:** Under heavy load you might scale out more workers without touching your scheduler or API.
* **Targeted Healthchecks & Restarts:** You can monitor each service’s health separately and auto-restart just the broken piece.

> **Guiding question:** If your Python code for a DAG accidentally raises an import error, which container should detect that, and why would you not want that error to kill your scheduler process?

Reflect on how isolation improves overall system resilience.

---

### 2.2 The `airflow-init` Container

**Purpose:**
This special init container runs exactly once when you bring the stack up. Its job is to:

1. **Migrate the database** by running `airflow db upgrade`, creating or updating all the metadata tables that Airflow needs.
2. **Create the initial admin user**, so the Web UI has credentials from day one.
3. **Fix file permissions** on shared volumes (`/opt/airflow/dags`, `/opt/airflow/logs`, etc.) so that subsequent containers, running as the `airflow` user, don’t hit “permission denied.”

By handling these steps up front—before the scheduler or API even starts—we ensure they always find a ready, healthy database and the correct directory structure.

> **Research prompt:** Look up the difference between `airflow db init`, `airflow db migrate`, and `airflow db upgrade`. Which commands are idempotent, and why is `upgrade` the right choice in this container?

> **Production tip:** In a Kubernetes deployment, this pattern translates to an “initContainer” spec that runs to completion before your main pods start. That way, your main services never launch against a half-baked database.

---

### 2.3 The `airflow-apiserver` (Web UI & REST API)

**Purpose:**
This container hosts the Flask-based webserver and the new OpenAPI-driven API endpoints. When you navigate to `http://localhost:8080`, you’re talking to this process.

* **UI Functionality:** Visual DAG graph, task instance logs, code editor, variable management.
* **API Endpoints:** Query DAG status, trigger DAG runs, fetch logs programmatically.

By exposing a separate API server, Airflow decouples UI traffic from scheduler load. In high-traffic environments, you can place the API behind a load balancer or enable authentication plugins without touching your task execution pipeline.

> **Guiding question:** Suppose an end-user repeatedly refreshes a large, complex DAG graph and triggers dozens of API calls. Why is it beneficial that these requests don’t share CPU time with your scheduler?

> **Production vs. Academic:**

* In a local demo you might not notice UI lag when refreshing.
* In production, a slow UI under heavy user load can delay scheduler heartbeats, causing missed DAG schedules.

---

### 2.4 The `airflow-scheduler`

**Purpose:**
The scheduler’s sole job is to:

1. **Read** the DAG definitions (from the metadata DB, updated by the DAG processor).
2. **Compare** each DAG’s schedule (cron, interval, or external trigger) to the last run time.
3. **Enqueue** new task instances into the Celery queue when they are due.
4. **Monitor** running tasks for SLA misses, retry limits, or manual terminations.

By isolating this logic, you ensure that heavy Python import or parsing work in the DAG processor won’t block scheduling—and that worker-level CPU or memory spikes won’t delay enqueuing new tasks.

> **Research prompt:** Investigate how the scheduler uses the healthcheck port (usually 8974) to signal liveness. What configuration variable enables this HTTP probe, and how would you verify it’s active?

> **Production tip:** In cloud environments you often run multiple scheduler replicas, using a lock or leader election mechanism to avoid double-scheduling. The Compose template’s readiness probe hints at how you’d detect and auto-heal a crashed scheduler.

---

### 2.5 The `airflow-dag-processor`

**Purpose:**
This relatively new addition processes your Python DAG files in a sandboxed environment:

* **Syntax checking:** Ensures no import errors or syntax mistakes slip into the scheduler’s heart.
* **Structure validation:** Verifies your DAG definitions conform to Airflow’s API.
* **Metadata writing:** Inserts DAG structural metadata (task list, default\_args) into the database.

Separating this role allows you to tune its resource limits more aggressively—DAG parsing can be CPU-heavy if you have hundreds of DAG files with complex Python logic.

> **Guiding question:** If you had 200 DAG files in your directory, how would you optimize startup time? What metrics would you gather, and why might you want to increase CPU allocation solely for the dag-processor?

---

### 2.6 The `airflow-triggerer`

**Purpose:**
Deferrable operators (like sensors that wait for an external HTTP response or a file appearing in S3) can block worker slots for long periods. The triggerer offloads this waiting:

1. **Receives** deferrable tasks.
2. **Registers** them in its own lightweight job queue.
3. **Awaits** external events or timers without holding up a resource-intensive worker.
4. **Resumes** the task on a real worker only when it’s ready to execute the next step.

This dramatically reduces worker starvation and cost in a production environment where sensors might wait for hours.

> **Production tip:** For high-volume pipelines with many sensors, tune the triggerer’s replica count separately from workers. Monitor its lag and queue depth via the HTTP healthcheck port or Celery metrics.

---

### 2.7 The `airflow-worker`

**Purpose:**
Workers are the “muscles” of your orchestration cluster. They:

* **Consume** tasks from the Celery queue.
* **Execute** the Python code you wrote in your DAGs (data generation, feature store writes, model training).
* **Log** stdout/stderr to the central logs folder.
* **Report** status back to the scheduler via the metadata DB.

Workers run as the `airflow` user, so they have only the permissions necessary to read DAGs, write logs, and communicate with external systems per their IAM or network policies.

> **Guiding question:** How would you debug a task that fails with a library import error on a worker but works locally in your notebook? What does that tell you about your Docker image?

> **Production vs. Academic:**

* A simple proof-of-concept might use LocalExecutor (in-process threads).
* In prod, LocalExecutor can’t scale beyond one machine; CeleryExecutor with separate workers is the industry norm for horizontal scaling.

---

### 2.8 The Optional `flower` Service

**Purpose:**
Flower is a lightweight web UI for Celery. It shows:

* **Worker status** (online/offline, active connections).
* **Queue depths** for each Celery queue.
* **Per-task metrics** (runtime, failures, retries).

While optional, Flower gives real-time visibility into your task execution layer, which is invaluable when tuning performance or diagnosing stuck tasks.

> **Production tip:** In a hardened environment, restrict Flower behind authentication or only expose it on an internal network. Celery’s default port can otherwise leak information about your infrastructure.

---

### 2.9 External Dependencies: Postgres & Redis

Airflow’s micro-services rely on two external pillars:

1. **Postgres** holds all metadata—DAG definitions, task states, logs (optionally), and system configurations. It’s your single source of truth for every DAG run ever executed.
2. **Redis** acts as the broker for CeleryExecutor—an in-memory, fast queue for passing task messages between scheduler, triggerer, and workers.

> **Guiding question:** Why might you choose a different broker (e.g., RabbitMQ or SQS) in a large-scale deployment? What characteristics are you optimizing for—durability, throughput, or ease of management?

> **Production tip:** In production, put Postgres in a high-availability cluster (multi-AZ, replicas) and move Redis to a managed service if possible (Elasticache, Memorystore) to avoid single points of failure.

---

### 2.10 Bringing It All Together

By the end of this module, you should be able to:

* **Name** each container in the Compose file and describe its precise role.
* **Articulate** why Airflow splits these roles, and how that split enables scaling, fault isolation, and resilience.
* **Recognize** how the official Docker-Compose template maps directly to a production Kubernetes or ECS blueprint, with readiness probes, restart policies, and resource isolation baked in.

---

#### Module 2 Reflection Questions

1. **Error Containment:** If a badly-written DAG causes a syntax error, which container catches it, and why does that prevent a system-wide outage?
2. **Deferrable Operators:** How does the triggerer improve resource usage compared to a long-running sensor on a worker?
3. **Scaling Strategy:** Suppose you have 50 high-CPU tasks per day. Which containers would you scale out, and which could remain single-instance?
4. **Broker Choice:** What trade-offs would push you to use RabbitMQ instead of Redis for your Celery broker?

Take a moment to think through these—jot answers, then share them when you’re ready. We’ll discuss and then move on to **Module 3: Why We Containerize with Docker**.

----

## Module 3: The Docker Imperative
We’ll explore why containers have become the de facto standard for deploying orchestrated workloads, how we craft a production-grade Airflow image, and what pitfalls to avoid. As always, I’ll weave in probing questions, research prompts, production tips, and contrasts with an academic or ad-hoc approach.

---

### 3.1 Why Containers Are Non-Negotiable

You may be comfortable running Python scripts directly on your laptop or even via a shared VM, but at scale and in a team setting, that approach falls apart:

1. **“It works on my machine” syndrome**

   * On your machine, you might have Pandas 1.5.4, Python 3.9, and an OpenSSL version that plays nicely with your private APIs. Your colleague, however, could be running Pandas 1.4 or Python 3.11, leading to subtle incompatibilities.
   * **Containers solve this** by bundling the exact OS, language runtime, and library versions into a self-contained image that runs identically everywhere.

2. **Environmental drift**

   * Over time, your VM might pick up security patches or tool upgrades, altering behavior. A container image is immutable once built, so every deployment uses the same artifact.

3. **Isolation between projects**

   * Without containers, installing a new library for one project can break another. With containers, each project has its own sandbox, and you never “pollute” your host environment.

4. **Parity with production**

   * Enterprises rarely deploy Airflow on raw VMs; they use Kubernetes pods, Amazon ECS tasks, Docker-Compose on a hardened host, or similar. Mastering containers locally gives you skills that transfer directly to any cloud platform.

> **Guiding question:**
> How would you reproduce a colleague’s bug that occurs only in Python 3.8 if your laptop is on Python 3.11? What steps would you take without Docker, and how does Docker simplify that?

> **Production tip:**
> Always tag your images with a semantic version (e.g. `airflow-custom:3.0.2-20250618`) and push to a private registry. Never pull images by a floating `latest` tag in production pipelines—it invites unintentional upgrades.

---

### 3.2 Anatomy of a Production-Grade Airflow Dockerfile

Rather than treat the official Airflow image as a black box, we extend it responsibly. Let’s walk through the layers of our `Dockerfile`:

1. **Base image selection**

   ```dockerfile
   ARG AIRFLOW_VERSION=3.0.2  
   ARG PYTHON_VERSION=3.11  
   FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}
   ```

   * We explicitly pin both the Airflow version and the Python minor version. This avoids surprises when upstream images release new Python builds.

2. **Installing OS-level build tools**

   ```dockerfile
   USER root  
   RUN apt-get update \
     && apt-get install -y --no-install-recommends build-essential libpq-dev \
     && rm -rf /var/lib/apt/lists/*
   ```

   * `build-essential` and `libpq-dev` are required to compile certain Python wheels (e.g. `psycopg2`).
   * We chain cleanup of `apt` caches to keep the final image small.

3. **Switching to a non-root user**

   ```dockerfile
   USER airflow
   ```

   * Running as `airflow` follows the principle of least privilege: even if a container is compromised, the attacker has fewer permissions.

4. **Copying and installing Python dependencies at build time**

   ```dockerfile
   COPY requirements.txt /tmp/requirements.txt  
   RUN pip install --no-cache-dir --upgrade pip \
     && pip install --no-cache-dir -r /tmp/requirements.txt
   ```

   * **Build-time installation** ensures the `requirements.txt` is baked into the image layers.
   * The two-step `upgrade pip` then install pattern uses caching effectively and prevents outdated installer issues.

5. **Baking in your code**

   ```dockerfile
   COPY dags/    /opt/airflow/dags/  
   COPY plugins/ /opt/airflow/plugins/
   ```

   * By copying in your DAG definitions and any custom plugins, you guarantee that the container is fully functional the moment it starts—no external mount or network requirement for core logic.

> **Guiding question:**
> What would happen if you omitted `libpq-dev` and tried to install `psycopg2`? How would a build failure manifest in your CI logs?

> **Research prompt:**
> Investigate the difference between `--no-cache-dir` and not using it in your pip install commands. How does it affect image size and build performance?

> **Production tip:**
> Add `LABEL org.opencontainers.image.source="https://github.com/EsosaOrumwese/fraud-detection-system"` to the Dockerfile. It embeds provenance metadata, making it easier to trace images back to the source code repository.

---

### 3.3 Build vs. Runtime Dependency Installation

The official quick-start uses an environment variable `_PIP_ADDITIONAL_REQUIREMENTS` to install things at container startup. While convenient for demos, it introduces several downsides:

* **Slower startup:** Installing dozens of packages can take minutes, delaying container readiness and complicating healthchecks.
* **Non-determinism:** A package version released between CI and production deployment could change behavior unexpectedly.
* **No layer caching:** Every `docker-compose up` re-installs packages, burning CPU and network bandwidth.

By contrast, **build-time installation**:

* Creates **immutable** image layers that never change.
* Leverages Docker’s **layer caching**, so incremental changes to `requirements.txt` only re-install affected packages.
* **Speeds up** container start dramatically, since all dependencies are already present.

> **Contrast with academic environments:**
> In a Jupyter notebook you might run `!pip install some-package` on the fly. That’s fine for experimentation but unthinkable for long-running services where every restart could mean another ten-minute install.

---

### 3.4 Versioning and Immutability

Once your image builds successfully, tag it with both version and date or Git commit SHA:

```bash
docker build \
  --build-arg AIRFLOW_VERSION=3.0.2 \
  --build-arg PYTHON_VERSION=3.11 \
  -t registry.example.com/airflow-custom:3.0.2-$(git rev-parse --short HEAD) \
  .
docker push registry.example.com/airflow-custom:3.0.2-$(git rev-parse --short HEAD)
```

In production pipelines:

1. **CI** builds and pushes the image when a merge to main occurs.
2. **CD** pulls the image by full SHA digest, ensuring absolute immutability.

> **Guiding question:**
> Why might you choose a digest (`@sha256:...`) rather than a tag when pulling images in production? What risk does that mitigate?

---

### 3.5 Local Development vs. Production Registry

* **Local dev:** You use `build: .` in Docker-Compose, referencing the local Dockerfile.
* **Production:** You replace `build: .` with:

  ```yaml
  image: registry.example.com/airflow-custom:3.0.2-abc1234
  ```

  That way, the cluster pulls a vetted image from your registry, not a developer’s local context.

> **Production tip:**
> Bake a CI step that runs `docker compose config --resolve-image-digests` and verifies no `build:` directives remain in your staging or prod manifests.

---

#### 3.6 Module 3 Reflection Questions

1. **Why does installing dependencies at container build time improve both performance and reproducibility?**
2. **What are the trade-offs of running your container as root versus a non-root user?**
3. **How would you embed source provenance and commit information into your Docker images?**
4. **Explain why you should prefer image digests over floating tags in a production deployment.**
5. **In what ways does containerizing your Airflow stack locally prepare you for deploying it on Kubernetes or another orchestration platform?**

Take some time to think through these questions, answer them, and let me know when you’re ready—and we’ll move on to **Module 4: Defining the Docker Compose Stack**!

----

## Module 4: Defining the Docker Compose Stack
This is where we translate our understanding of Airflow’s micro-services and Docker containers into a single, cohesive YAML manifest that stands up the entire orchestration cluster. We’ll cover:

1. How we DRY up the file with YAML anchors
2. The purpose of each service block and its settings
3. How dependencies and healthchecks enforce startup order
4. The nuances of `restart: always` and production considerations
5. Why we avoid certain fields (`version:` or `deploy:`) in a pure Compose setup

Throughout, I’ll weave in questions for you to ponder or research, and contrast this with simpler, ad-hoc projects.

---

### 4.1 Anchoring Common Configuration

Rather than repeat the same `build:` or `environment:` settings in every service, we define a top-level anchor:

```yaml
x-airflow-common: &airflow-common
  build: .
  environment:
    &airflow-common-env
    AIRFLOW__CORE__EXECUTOR: CeleryExecutor
    AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
    AIRFLOW__CELERY__BROKER_URL: redis://redis:6379/0
    AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://airflow:airflow@postgres/airflow
    AIRFLOW__CORE__FERNET_KEY: ${FERNET_KEY:?}
    AIRFLOW__API__SECRET_KEY: ${SECRET_KEY:?}
    AIRFLOW__SCHEDULER__ENABLE_HEALTH_CHECK: 'true'
    _PIP_ADDITIONAL_REQUIREMENTS: ${_PIP_ADDITIONAL_REQUIREMENTS:-}
  volumes:
    - ./dags:/opt/airflow/dags
    - ./logs:/opt/airflow/logs
    - ./config:/opt/airflow/config
    - ./plugins:/opt/airflow/plugins
  user: "${AIRFLOW_UID:-50000}:0"
  depends_on:
    &airflow-common-depends-on
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
```

Here’s what this achieves:

* **DRY Configuration**: All services that extend `*airflow-common` inherit the same build context, Dockerfile, environment variables, volume mounts, user mapping, and basic dependencies.
* **Centralized Secrets**: The `${FERNET_KEY:?}` syntax forces Compose to fail early if you haven’t generated your `.env`, preventing silent misconfigurations.
* **Anchored Dependencies**: Defining `&airflow-common-depends-on` once means we can attach it to every service that needs Postgres and Redis to be healthy before starting.

> **Guiding question:** What happens if you don’t use anchors and copy-paste the same blocks into each service? How does that affect maintainability and the risk of typos?

> **Production tip:** Keep your YAML DRY—large teams will thank you when they need to adjust a shared environment variable or volume path in one place, not dozens.

---

### 4.2 Understanding `depends_on` and Healthchecks

In vanilla Docker Compose, `depends_on` without conditions only waits for container start, not readiness. The key production upgrade is:

```yaml
depends_on:
  postgres:
    condition: service_healthy
  redis:
    condition: service_healthy
```

Paired with a `healthcheck:` block in each dependency:

```yaml
postgres:
  healthcheck:
    test: ["CMD","pg_isready","-U","airflow"]
    interval: 10s
    timeout: 10s
    retries: 5
    start_period: 5s
```

this ensures:

* **Readiness over Liveness**: Postgres might accept TCP connections instantly but not be ready for migrations. A `start_period` gives it breathing room before health assessments begin.
* **Ordered Startup**: The `airflow-init` container won’t run its migrations until Postgres and Redis report healthy, preventing cryptic “table does not exist” errors in the scheduler.

> **Research prompt:** Experiment locally by liveness-probing a slow-starting service. What do you observe if you omit `start_period` and the service takes longer to come online?

---

### 4.3 Service-by-Service Breakdown

With the anchors and healthchecks in place, each service block becomes focused on its unique role:

* **`airflow-init`**

  * Extends `*airflow-common` but runs an `entrypoint` script instead of a long-running process.
  * Depends on Postgres+Redis being healthy, then migrates and bootstraps your admin user.
  * Uses `condition: service_completed_successfully` so downstream services wait for it to exit with code 0.

* **`airflow-apiserver`**

  * Runs `command: api-server` and binds port 8080.
  * Has an HTTP healthcheck hitting `/api/v2/version` every 30s.
  * `restart: always` ensures if the UI crashes, it comes back automatically in dev or staging.

* **`airflow-scheduler`**

  * Runs `command: scheduler`, probes its own HTTP health endpoint (port 8974).
  * In production you might run two replicas; Compose supports this via `scale: 2`.

* **`airflow-dag-processor`**

  * Runs `dag-processor` command, checking for Python syntax errors.
  * Lets you allocate extra CPU time here without affecting workers.

* **`airflow-worker`**

  * Runs `celery worker`.
  * Inspects Celery heartbeat via either a Celery ping command or HTTP (if you expose the metrics endpoint).

* **`airflow-triggerer`**

  * Runs `triggerer`, checking for deferrable job health via a CLI check.

* **`flower`** (optional)

  * Runs `celery flower` on port 5555, with its own healthcheck.
  * Useful for interactive debugging of running tasks.

> **Guiding question:** Why do we set `restart: always` on every service, even though `docker-compose down` can stop them manually? How does this help in a shared dev environment?

---

### 4.4 Why We Avoid `version:` and `deploy:`

A common pitfall is to specify:

```yaml
version: "3.9"
```

or use a `deploy:` block with resource limits. In pure Docker Compose:

* **`version:`** is optional in Compose V2+; omitting it lets Compose auto-detect the version.
* **`deploy:`** settings are ignored by non-Swarm mode, so CPU/memory limits under `deploy:` have no effect when you run `docker compose up`. Instead, use the Compose-native fields `cpus:` and `mem_limit:` directly under each service.

By following the ASF template exactly, we ensure:

1. **Maximum compatibility** with any version of Compose.
2. **No surprise missing resource caps** if someone mistakenly thinks `deploy:` works in dev.

> **Production tip:** When moving to a Docker-Swarm or Kubernetes helm deployment, you can migrate your `deploy:` block into Kubernetes resource requests and limits or Swarm service constraints. Keeping your dev YAML clean makes that migration smoother.

---

### 4.5 Putting It All Together

Once you’ve defined your anchors, dependencies, healthchecks, and service blocks, the Compose file becomes a single source of truth for your entire local cluster. Running:

```bash
docker compose up -d --wait
```

will:

1. Build (or pull) your custom Airflow image.
2. Launch Postgres and Redis, waiting for them to report healthy.
3. Execute `airflow-init`, migrating the database and creating the admin user.
4. Spin up the API, scheduler, DAG processor, triggerer, and worker—all in the right order.
5. Expose ports 8080 (UI), 8974 (scheduler health), and 5555 (Flower) for your inspection.

Because each container has its own healthcheck and `restart: always`, you can stop or crash one, and Compose will respawn it—mirroring how a Kubernetes deployment heals itself.

---

#### Module 4 Reflection Questions

1. **YAML Anchors:** How do anchors (`&airflow-common`, `*airflow-common`) improve maintainability compared to copy-pasting blocks?
2. **Healthcheck Granularity:** Explain why a CLI-based healthcheck might sometimes be preferable to an HTTP probe for the scheduler or triggerer.
3. **Restart Policies:** In what scenarios would `restart: always` in Compose help you detect unintended container failures?
4. **Version and Deploy:** Why are `version:` and `deploy:` often misleading in a pure Docker Compose context? What’s the right way to enforce resource limits?

Once you’re comfortable with these ideas, we can proceed to **Module 5: Bootstrapping Configuration & Secrets**—where we’ll see how your `bootstrap.sh` makes `.env` and wires secrets into this orchestrated cluster. Let me know when you’re ready!

-----

## Module 5: Bootstrapping Configuration & Secrets
In this module, we’ll see how we generate and manage the sensitive bits—encryption keys, user IDs, and environment variables—without ever checking secrets into Git. We’ll explore why this matters, how the `bootstrap.sh` script works in detail, and how that pattern maps to real-world secret management at scale.

---

### 5.1 Why Externalize Configuration and Secrets

In a simple tutorial, you might hard-code your Fernet key or database URL directly into `docker-compose.yml`. That’s a fast path to a major security vulnerability:

* **Credentials in source control:** Anyone with repo access can see your production passwords or keys.
* **Unintentional leaks:** A careless screenshot, a public fork—suddenly your secrets are all over the internet.
* **No rotation path:** If a key is compromised, rotating it in code and configuration becomes a manual, error-prone chore.

By externalizing all sensitive values into an **`.env`** file that’s listed in `.gitignore`, we ensure:

1. **Separation of code and secrets.**
2. **Local overrides**—each developer or environment can supply its own values.
3. **Ease of rotation**—just generate a new `.env` and restart the cluster.

> **Guiding question:**
> In what ways does keeping secrets in an `.env` file fall short of enterprise secret management? What risks remain, and how might you mitigate them?

---

### 5.2 Anatomy of `bootstrap.sh`

Your `bootstrap.sh` script lives under `orchestration/airflow/scripts/bootstrap.sh`. Let’s step through it line by line:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

* **Shebang** (`#!/usr/bin/env bash`) ensures the script runs with Bash, even if `/bin/sh` links to a different shell.
* **`set -euo pipefail`** makes the script robust:

  * `-e` aborts on any command failure.
  * `-u` treats unset variables as errors.
  * `-o pipefail` catches errors in piped commands.

```bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"
```

* **`SCRIPT_DIR`** computes the directory containing the script—this makes the script **location-agnostic**, so you can run it from anywhere and it still finds the right path.
* **`ENV_FILE`** points to the `.env` file alongside your `docker-compose.yml`, not inside `scripts/`.

```bash
if [[ -f "$ENV_FILE" ]]; then
  echo ".env already exists, skipping generation"
  exit 0
fi
```

* **Idempotency check**: Don’t overwrite an existing `.env`. If you need to rotate, you delete it manually—an explicit, conscious act.

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

* **Embedded Python** section leverages Python’s standard libraries to:

  1. **Generate a 32-byte Fernet key**, URL-safe, guaranteeing strong symmetric encryption for connections and passwords.
  2. **Generate a `SECRET_KEY`** for Flask session HMAC signing—random and unguessable.
  3. **Detect the host UID** via `os.getuid()`—crucial for correct permissions on mounted volumes (otherwise you get “permission denied” on Linux; Windows may not expose `getuid()`, hence the fallback).
  4. **Optionally set `IMAGE_ARCH_SUFFIX`** to handle ARM vs. x86 builds—this can drive multi-arch support in CI.
  5. **Write** all non-empty lines to the `.env`, trailing newline included.

> **Research prompt:**
> Look up Fernet encryption in the [cryptography](https://cryptography.io/) Python library. Why is Fernet a good default for Airflow’s needs? What would happen if you mistakenly used an insecure key length?

> **Production tip:**
> In a true production setting you might replace this Python block with a call to AWS SSM or Vault. For example:
>
> ```bash
> FERNET_KEY=$(aws ssm get-parameter --name /airflow/fernet-key --with-decryption --query Parameter.Value --output text)
> ```

---

### 5.3 Integrating `.env` with Docker Compose

Docker Compose automatically reads a file named `.env` in the same directory as `docker-compose.yml`. Each line `KEY=VALUE` becomes an environment variable available for substitution in the YAML:

```yaml
environment:
  AIRFLOW__CORE__FERNET_KEY: ${FERNET_KEY:?}
  AIRFLOW__API__SECRET_KEY: ${SECRET_KEY:?}
  user: "${AIRFLOW_UID}:0"
```

* **`${FERNET_KEY:?}`** syntax tells Compose to error out with a clear message if `FERNET_KEY` is unset—no accidental blanks.
* The **`user`** line ensures files created by containers map back to the correct host UID, avoiding root-owned files in your project folder.

> **Guiding question:**
> If you ran `docker compose up` without a `.env`, what error would you see, and why is that preferable to silently using an empty key?

---

### 5.4 Lessons on Permissions and Cross-Platform Issues

Because you develop on Windows with Git Bash, but containers run Linux, you can encounter subtle permission quirks:

* **Windows file ownership** may map to a different UID inside the container, causing tasks to fail.
* The script’s fallback `AIRFLOW_UID=50000` is chosen to be a non-conflicting user ID on most systems.

> **Production vs. Academic:**
> In AWS ECS or Kubernetes, you typically run containers as a fixed, defined user via the pod spec or task definition, and you don’t mount host volumes for code—your images contain everything. But for local dev, this UID mapping trick ensures a smooth experience.

---

### 5.5 Secret Rotation and Idempotency

Because the script skips generation if `.env` exists, rotating keys requires:

1. Deleting the old `.env`.
2. Rerunning `./scripts/bootstrap.sh`.
3. Recreating the cluster (`docker compose down && docker compose up -d --wait`).

In production, you’d swap this for a secret-management workflow:

* **Automatic key rotation** via Vault’s dynamic secrets or AWS KMS.
* **Rolling restarts** of Airflow components to pick up new environment variables without downtime.

> **Research prompt:**
> Investigate how Kubernetes Secrets map to environment variables or mounted volumes in pods. How would you adapt this `.env` approach to a Kubernetes helm chart?

---

#### 5.6 Module 5 Reflection Questions

1. **Idempotency Check:** Why is it important that `bootstrap.sh` exits early if `.env` already exists? What risk does regenerating keys on every run introduce?
2. **UID Mapping:** Explain how `AIRFLOW_UID` affects file permissions on Linux hosts. Why might Windows users see different behavior?
3. **Error-Fail Fast:** What advantage does `${FERNET_KEY:?}` syntax in Compose provide over a default blank value?
4. **Production Secret Management:** Outline a basic workflow for retrieving secrets from AWS SSM instead of an `.env` file. What changes would you make to `bootstrap.sh`?

---

When you’re ready, share your thoughts on these questions or let me know if anything needs more clarification. Once we’re solid on Module 5, we’ll proceed to **Module 6: CI/CD & Smoke Tests** in our orchestration journey.

---

## Module 6: CI/CD & Smoke Tests
where we ensure that every change to our orchestration code is validated automatically, catching errors early and giving us confidence before merging to main or deploying.

---

When you’re hacking locally, you might simply run `docker compose up` and eyeball the logs for a few seconds before declaring, “Looks good!” But in a team—especially one with SLAs around data freshness and system uptime—that manual check isn’t sufficient. You need your continuous integration (CI) pipeline to behave like a trusty co-pilot, spinning up the entire Airflow cluster in an isolated environment, exercising its healthchecks, and even verifying that the web API responds, all without human intervention.

### 6.1 Why Smoke Tests Belong in CI

In academic or ad-hoc scripts, a CI job might only lint your Python code or run unit tests against small functions. But orchestration code is fundamentally about runtime behavior: YAML syntax, Dockerfile correctness, environment variable injection, and service readiness. A typical lint or unit-test suite would entirely miss:

* A malformed `docker-compose.yml` that fails to parse.
* A typo in the `airflow db upgrade` command that silently exits before migrations.
* A missing mount that causes the scheduler to see zero DAGs.
* A port collision that prevents the webserver from starting.

By embedding **smoke tests**—minimal end-to-end checks—into your CI workflow, you catch these errors the moment they appear in a pull request, not when you later demo locally or in staging.

---

### 6.2 Anatomy of the `orchestration-test` CI Job

Here’s a narrative of what the CI job does, why each step is there, and how failures surface:

1. **Checkout the Repo**
   The job begins with `actions/checkout@v4`, pulling down the latest PR branch. This ensures we test exactly what the user has changed—no stale code from the default branch.

2. **Set Up Docker**
   On GitHub’s `ubuntu-latest` runner, Docker Compose is already available via the preinstalled Docker engine. We `cd` into the `orchestration/airflow` folder so that `docker-compose.yml` and `.env` (generated or committed) are in context.

3. **Build the Custom Image**

   ```bash
   docker compose build --pull
   ```

   We force a fresh pull of the base Airflow image and then build our custom one. If there’s a syntax error in the Dockerfile—say, a misspelled `RUN` instruction or a missing `requirements.txt`—this step fails fast, preventing wasted cycles downstream.

4. **Spin Up the Cluster with Healthchecks**

   ```bash
   docker compose up -d --wait
   ```

   The `--wait` flag (available in Docker Compose v2+) instructs Compose to watch the health status of every container. Because our YAML includes comprehensive `healthcheck:` definitions for Postgres, Redis, init, API, scheduler, triggerer, and workers, this command blocks until every service reports “healthy” or times out. On timeout, the job ends in failure, pointing you immediately at the problematic service.

5. **API Smoke Test**

   ```bash
   curl --fail http://localhost:8080/api/v2/version
   ```

   Hitting the `/api/v2/version` endpoint verifies two critical things:

   * The webserver is accepting HTTP traffic on port 8080.
   * The Airflow API is responding as expected, indicating database migrations ran successfully and the application booted without fatal errors.

6. **Tear Down the Cluster**

   ```bash
   docker compose down -v
   ```

   We stop and remove all containers—and the `-v` flag also deletes volumes, ensuring a clean slate for the next CI job and preventing runner disk exhaustion.

7. **Failure Visibility**
   If any of these steps fail—build, `up --wait`, or `curl`—the CI job immediately reports a red X on the pull request. The log output shows exactly which step and which container healthcheck or API call failed, so you can jump straight to the fix.

> **Production tip:** In a larger enterprise pipeline, you might add a final step to run a minimal DAG example: trigger a “hello\_world” DAG, wait for its completion via the API, and then assert the run succeeded. That single integration test gives you end-to-end confidence before deploying to staging.

---

### 6.3 Beyond Smoke Tests: Full Integration and Deployment

Smoke tests catch basic runtime errors, but as your project grows you’ll want a richer CI/CD flow:

* **Static Analysis of Compose & Dockerfile:** Tools like `docker-compose config --quiet` and `hadolint Dockerfile` can lint your YAML and Dockerfile syntax.
* **Security Scanning:** Integrate `Trivy` or `Grype` to scan your custom image for known vulnerabilities, blocking merges if critical CVEs are found.
* **Cost Estimation:** You already run Infracost against your Terraform; you could run an analogous cost check for resource quantities implied by your Compose file or Kubernetes manifests.
* **Automated Deployment:** On merge to `main`, trigger a CD workflow that promotes the tested image to a staging registry or deploys the Compose file to a dedicated staging host, running the same smoke tests there.

> **Guiding question:** How would you extend this CI job to run on both Linux and Windows runners, ensuring your `bootstrap.sh` and Compose file behave cross-platform?

---

### 6.4 Contrasting with Academic Pipelines

In a classroom, CI often means “does this Python script import without errors?” or “does this unit test pass?” There’s rarely any runtime orchestration validated. In contrast, our production-grade CI pipeline treats orchestration code with the same rigor as application code:

* We validate not just syntax but actual service readiness.
* We tear down resources to avoid stale state or disk bloat.
* We can fail fast on configuration mistakes, not just logic bugs.

By giving you this end-to-end safety net, you can merge changes without the fear of “Oops—I forgot to adjust the Dockerfile” or “My `healthcheck:` bracket was mis-aligned.” The pipeline forces you to deliver working orchestration every time.

---

#### Module 6 Reflection Questions

1. **Failure Modes:** If `docker compose up -d --wait` times out, how would you investigate which container failed its healthcheck?
2. **Extending the Smoke Test:** Describe the steps you’d add to trigger a simple DAG run and verify its completion via the Airflow API.
3. **Cross-Platform Considerations:** What pitfalls might you encounter running this CI job on a Windows runner, and how could you adapt your `bootstrap.sh` or Compose file to handle them?
4. **Security & Compliance:** Where in this CI flow would you insert an image vulnerability scan, and what policy rules would you enforce before merging?

Take a moment to reflect on these questions. When you’re ready, we’ll proceed to **Module 7: Scaling, Observability & Hardening**, completing our orchestration masterclass.

----

## Module 7: Scaling, Observability & Hardening
Here we bridge the gap between a robust local dev stack and a battle‐hardened production deployment by discussing how to:

1. Enforce **resource constraints** so your services behave predictably
2. Add **observability**—metrics, logs, and dashboards—for real‐time insight
3. Implement **security scanning** and **policy checks** to keep your images and configs safe
4. Integrate **cost monitoring** so your orchestration never breaks the bank

Throughout, I’ll ask questions for you to reflect on, suggest research directions, and point out where a production cluster departs from “just spinning up containers on your laptop.”

---

### 7.1 Resource Constraints: Taming Your Cluster

Even locally, runaway processes can swamp your machine—imagine dozens of scheduler threads parsing hundreds of DAGs or a runaway worker task spawning unbounded threads. In production, unchecked resource usage can cause cascading outages. We impose limits at two levels:

1. **Docker Compose Native Limits**
   Under each service in your Compose, you can specify:

   ```yaml
   mem_limit: 1g
   cpus: 0.5
   ```

   This ensures that, for instance, a worker can never consume more than 1 GB of RAM or half a CPU core on your dev box. If it tries, Docker throttles or kills it, preventing host exhaustion.

2. **Kubernetes / Swarm Deploy Blocks**
   When you migrate this Compose to a Swarm or convert it to a Helm chart, you’ll translate those same constraints into:

   ```yaml
   deploy:
     resources:
       limits:
         memory: 1Gi
         cpu: "500m"
       requests:
         memory: 512Mi
         cpu: "250m"
   ```

   —so the scheduler, triggerer, and workers all reserve and cap resources appropriately.

> **Guiding question:**
> If your DAG-processor regularly hits its memory cap and gets OOM-killed, how would you detect that and adjust its limits? What metrics or logs would you examine?

> **Production tip:**
> Always set both **requests** and **limits** in Kubernetes. Requests ensure the scheduler can pack pods onto nodes; limits guard against noisy neighbors.

---

### 7.2 Observability: Logs, Metrics & Tracing

A live cluster without observability is like flying blind. You need:

1. **Centralized Logging**

   * Your Compose mounts `./logs`, but in production you’d forward those logs to a managed service (CloudWatch, ELK, Datadog).
   * Each task’s stdout/stderr can be shipped via a sidecar or a logging agent (Fluentd, Filebeat).

2. **Metrics Collection**

   * Airflow exposes a **Prometheus** metrics endpoint (e.g. `/metrics`). You can scrape it to track:

     * DAG parse times
     * Task queue depth
     * Task execution durations
     * Scheduler heartbeats and lag
   * Workers and triggerers export Celery metrics (active tasks, failed tasks, queue lengths).

3. **Distributed Tracing** (optional, advanced)

   * With OpenTelemetry instrumentation, you can trace a single DAG run end-to-end across services.
   * This reveals bottlenecks (e.g. a slow S3 write or a hot DB query) in your real-time pipelines.

> **Research prompt:**
> Explore how to enable the `statsd` or `prometheus` metrics exporter in Airflow 3. What config values must you set in `airflow.cfg`, and which healthchecks or probes change as a result?

> **Production tip:**
> Create pre-built dashboards for key SLOs—e.g., “Percentage of DAGs that succeed within 5 mins of schedule” or “95th percentile task runtime.” That way, on-call engineers can spot regressions at a glance.

---

### 7.3 Security Scanning & Policy Enforcement

Containers and IaC are another attack surface. We bake in security at every stage:

1. **Image Vulnerability Scans**

   * Use **Trivy** or **Grype** in your CI:

     ```bash
     trivy image --exit-code 1 --severity CRITICAL, HIGH registry.example.com/airflow-custom:3.0.2-*
     ```
   * Block merges if any critical or high CVEs are detected in your base image or installed libraries.

2. **Infrastructure as Code Checks**

   * For your Terraform stacks, you run **Checkov** and **tfsec**.
   * Apply the same principle to Dockerfiles with **Hadolint** to catch bad practices (e.g. `ADD` instead of `COPY`, missing `USER` instructions).

3. **Runtime Security Policies**

   * Enforce non-root containers via Kubernetes PodSecurityPolicies or OPA Gatekeeper rules.
   * Use AppArmor or SELinux profiles to restrict syscalls.

> **Guiding question:**
> If a new vulnerability is discovered in `openssl` and you’re pulling `apache/airflow:3.0.2-python3.11`, how does a CI scan help you catch and remediate it before it hits staging?

> **Production tip:**
> Automate monthly vulnerability scans against all images in your private registry and send a summary report to your security team. Integrate auto-remediation scripts for low-risk updates.

---

### 7.4 Cost Monitoring & Guardrails

In cloud environments, orchestration can incur unexpected costs—especially if you autoscale workers or run expensive sensors. To keep your AWS spend in check:

1. **Budget Alarms**

   * Use AWS Budgets with email/SNS alerts when monthly spend approaches your cap.
   * Tie Terraform’s Infracost plugin into PRs to show “This change adds \$5/month” or “This decreases cost by \$10/month.”

2. **Resource Quotas**

   * In Kubernetes, set **ResourceQuota** objects to cap total CPU/RAM per namespace.
   * In ECS, use Service Quotas and cost alarms.

3. **Idle Resource Cleanup**

   * Schedule a daily job to tear down any test clusters left running.
   * Use “nuke scripts” (like your sandbox destroy script) to ensure ephemeral infra doesn’t linger.

> **Guiding question:**
> How would you adjust your CI smoke-test to ensure it doesn’t spin up a cluster and forget to tear it down, resulting in runaway costs on a shared runner?

> **Production tip:**
> Configure your CI to reuse existing Docker networks and volumes where safe, rather than creating new ones for every run—this prevents runaway resource creation on long-lived runners.

---

### 7.5 Bringing Hardening Back to Local Dev

All these production practices should inform your local setup:

* **Run a local Trivy scan** against your custom image before every release.
* **Expose the Prometheus endpoint** in your Compose and run a local Grafana sandbox.
* **Test failure scenarios** by manually sending SIGKILL to the scheduler container and observing that `restart: always` recovers it.
* **Simulate high load** by launching dozens of “dummy” DAG runs and watching workers scale (or throttle) under your resource caps.

By practicing security, observability, and cost-control locally, you build muscle memory that pays dividends when you graduate to a cloud deployment.

---

### Module 7 Reflection Questions

1. **OOM Troubleshooting:** If your `airflow-worker` is repeatedly OOM-killed under load, what metrics would you inspect and how would you adjust its memory limits?
2. **Metrics Pipeline:** Describe the end-to-end flow of a Prometheus scrape from your Airflow API container into a Grafana dashboard.
3. **Vulnerability Response:** A critical CVE appears in one of your base images overnight—how does your CI and registry policy help you respond swiftly?
4. **Cost Safeguards:** Outline how you’d use Infracost in PRs and AWS Budgets to ensure your orchestration layer never exceeds a \$50/month cap.

---

With **Module 7** complete, you’ve now been equipped end-to-end—from the “why” of orchestration to the “how” of production-grade scaling, monitoring, and security. Next, we could do a live **walkthrough of the code**, tracing each file and command, or tackle any deep-dive questions you have. Let me know where you’d like to go from here!
