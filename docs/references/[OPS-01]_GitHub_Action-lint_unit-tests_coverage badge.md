# Summary notes
Summary notes for `[OPS-01] GitHub Action — lint, unit-tests, coverage badge (target ≥ 50 % for now)`.

---
## OPS-01: GitHub Actions for Lint, Tests & Coverage

**Goal**
Stand up a CI pipeline that automatically lints, runs unit tests, and measures coverage—blocking merges if tests fail or coverage falls below our threshold.

**Why**

* Guarantees that every merge meets a minimum quality bar: code compiles, tests pass, untested paths are highlighted.
* Provides a visible coverage badge to drive gradual improvement.
* “Shift-left” on regressions by surfacing failures on every push/PR.

**Acceptance Criteria**

* Workflow triggers on pushes and PRs to `main`/`dev`.
* Steps: install dependencies → run linters → run `pytest` → generate `coverage.xml`.
* CI job fails if any lint/test/coverage-threshold errors occur.
* Coverage badge (e.g. via Codecov) shows on README.
---

> Note that SEC-01 is a tweaked issue for security which isn't showing in repo. Check below:

**Issue**: SEC-01 -- Add tfsec & Checkov security scan to CI for Terraform and Dockerfiles.\
**Goal**: Extend CI to automatically scan your Terraform configs, Dockerfiles, and other IaC for security misconfigurations, failing the build on high-severity issues.

**Why**
* Catches critical infrastructure security holes early (e.g. open S3 buckets, risky Docker settings).
* Embeds security as code—developers get instant feedback, instead of discovering issues in post-mortem.
* Builds confidence that every merge meets our security baseline.

**Acceptance Criteria**
* CI runs `tfsec` on any `.tf` files; build fails on HIGH findings.
* CI runs `Checkov` across Terraform, Dockerfiles, etc.; build fails on HIGH (medium can be reported but not block).
* Sample “passing” output appears in CI logs, demonstrating zero high-severity alerts.

---

## What's the difference between issues REP-02, OPS-01 and SEC-01?
Even though your original single-job `ci.yml` did technically tick off all three boxes—

* **REP-02** (pre-commit hooks),
* **OPS-01** (lint, tests, coverage), and
* **SEC-01** (tfsec & Checkov)—

the “advanced” workflow reorganizes and enriches that simple flow to give you better:

1. **Speed & Resource Efficiency**

   * **Caching** (`actions/cache`) so you don’t re-download pip packages or re-warm the pre-commit cache on every run.
   * **Concurrency control** so that if you push several commits in quick succession, only the latest run for each branch/PR actually finishes.

2. **Parallel Feedback & Isolation**

   * **Separate jobs** for linting, testing, and security mean:

     * Tests don’t wait on security scans if you want faster feedback on code errors, and vice versa.
     * Failures are scoped—if lint breaks, you know it’s not a test or security issue.

3. **Matrix Builds for Compatibility**

   * Running your tests under **multiple Python versions** (3.12 *and* 3.11) ensures you catch subtle compatibility bugs before they ever land.

4. **Selective “Fail-Fast” vs. “Soft-Fail”**

   * You can enforce a minimum coverage threshold (`--cov-fail-under=50`, for now. Make `70` later) so OPS-01 truly blocks merges when coverage dips below your bar.
   * Meanwhile, security scans can be tuned to **only** block on HIGH-severity (soft-fail for MEDIUM), so your pipeline stays both secure **and** developer‐friendly.

5. **Reproducibility & Pinning**

   * Pinning Poetry, actions, and tools guarantees that a run today behaves the same as one a month from now, avoiding mysterious “it works on my laptop” drift.


### Mapping back to your tickets

| Ticket | Goal                                      | Basic CI |                         Advanced CI                          |
|--------|-------------------------------------------|:--------:|:------------------------------------------------------------:|
| REP-02 | Pre-commit hooks pass locally & in CI     |    ✅     |                              ✅                               |
| OPS-01 | Lint + unit tests + coverage badge (≥50%) |    ✅     |          ✅ (with matrix, thresholds, Codecov flags)          |
| SEC-01 | tfsec & Checkov scans; high-sev = fail    |    ✅     | ✅ (always runs even on lint/test failures; soft-fail tuning) |

Your former CI *did* satisfy all three on a “functional” level—but the advanced workflow treats them as distinct phases:

1. **Lint phase** (REP-02)
2. **Test phase** (OPS-01)
3. **Security phase** (SEC-01)

…each with its own environment, caching, and failure semantics.


### Why the extra complexity?

* **Faster feedback loops:** Developers get lint errors in seconds without waiting for slow security scans or full test suites.
* **Better resource utilization:** Parallel jobs finish sooner and cost you fewer CI minutes.
* **Clearer failure attribution:** It’s immediately obvious *which* phase (lint, test, or security) broke, so fixing is more focused.
* **Scalability:** As your test matrix grows (e.g. add 3.10 or 3.9), you simply extend the matrix without duplicating steps.
* **Maintainability:** With well-named jobs and steps, it’s easier to onboard new team members, audit your pipeline, or tweak one phase without touching the others.

In short, the advanced workflow isn’t about adding bells and whistles for their own sake—it’s about giving you a **robust**, **scalable**, and **developer-friendly** CI pipeline that will serve you as your codebase (and team) grows.

---

## Why was the task of building `ci.yml` split into 3 issues?
They were split up for exactly the same reason you’d break any big project into smaller chunks: to ship value early, get feedback fast, and reduce risk. Here’s the usual progression:

1. **Start small with an MVP pipeline**

   * You first tackle **REP-02** (“make sure our pre-commit hooks run everywhere”). That gives you instant, automated formatting, linting, type-checks, and secrets scanning on every commit.
   * This is quick to set up, low-risk, and immediately raises your dev‐workflow quality.

2. **Add core dev-ops fundamentals next**

   * Once your code is always clean, you tackle **OPS-01**: linting plus unit-tests plus a coverage badge.
   * Now you’ve got real feedback on “does my code actually work?” and “how well are my tests covering it?”
   * At this point you already have a working CI that stops bad code from merging—even if it’s still a single job.

3. **Layer on security scans last**

   * Finally, you implement **SEC-01** (tfsec + Checkov). Security tooling tends to be heavier, more opinionated, and can generate a lot of noise, so it’s safest to integrate once the basics are solid.

Only once you’ve proven out each of those in isolation do you invest the extra time to:

* Introduce **job-level caching**,
* Split into **lint / test / security** phases,
* Run a **matrix** of Python versions,
* Pin your tools for **reproducibility**,
* Tune “fail fast” vs “soft fail” behaviors, etc.

That “advanced” pipeline is fantastic for a growing codebase and team, but it has a non-trivial setup and maintenance cost. By rolling it out incrementally, you:

* **Validate assumptions** (e.g. “do my tests even pass under coverage?”),
* **Catch configuration mistakes** early on simple samples,
* **Train the team** on each new tool (pre-commit, pytest, tfsec, Checkov) one at a time,
* **Keep the repo green** all the way, instead of wrestling with a massive YAML from day one.

So in short: you break it into REP-02, OPS-01, SEC-01 to get each building block solid before composing them into a full-blown, multi-job, matrix-driven, cached, reproducible CI pipeline. That’s why you didn’t start with the advanced one up front.

---

## Research Workflow for this section
### 0 · Big-picture purpose

| Why we add a CI job *in addition* to pre-commit                                                       | Interview-ready phrasing                                                                                |
|-------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| Fresh, **clean environment** catches “works-on-my-laptop” issues (missing dep, wrong Python version). | “Local hooks are great for fast feedback; CI proves a newcomer can clone the repo on any box and pass.” |
| Lets you **gate merges to dev/main** with an unforgeable ✅.                                           | “We fail the pipeline → PR can’t merge → quality bar stays high.”                                       |
| Builds the **habit** of red/green testing every push — invaluable in regulated finance.               | “Auditors can point to the Actions log as proof of repeatable builds.”                                  |

### 1 · How you would research (primary sources first)

1. **GitHub Docs → Actions → “Testing Python”** — see the official `actions/setup-python` examples.
2. **Pytest docs → `pytest --cov`** — how to collect coverage.
3. **Ruff README → ‘GitHub Actions’ section.**
4. **GitHub Actions cache doc** — to speed up dependency installs (`pip cache`).
5. Glance at **two popular OSS Python repos** (fastapi, poetry) to see real CI YAMLs.


### 2 · Decide scope & policy

| Decision area            | Choice & justification                                                                                                   |
|--------------------------|--------------------------------------------------------------------------------------------------------------------------|
| **Trigger**              | `pull_request` **and** `push` to `dev` (so branch protections pass).                                                     |
| **Python versions**      | Matrix `3.12`, `3.11` — proves code works on n-1 version with minimal extra minutes.                                     |
| **Dependencies install** | `pip install -e .[dev]` (dev-extras defined in `pyproject.toml`) to guarantee `ruff`, `pytest`, etc. are version-pinned. |
| **Separate jobs?**       | Single **job** with two **steps** (`ruff`, `pytest`) is enough now; we can split later if runtimes diverge.              |
| **Coverage target**      | Collect coverage, fail job if `< 50 %` (adjust later).                                                                   |

> Write these down in **ADR-0002** “Choose CI policy” — practising traceable decisions.


### 3 · Augment `pyproject.toml` (dev extras)

```toml
[project.optional-dependencies]
dev = [
  "ruff==0.4.3",
  "pytest==8.1.1",
  "pytest-cov==5.0.0"
]
```

Push a tiny **failing** test stub to force pytest to run:

```python
# tests/unit/test_sanity.py
def test_always_passes():
    assert 1 + 1 == 2
```

### 4 · Draft the workflow (thought process)

1. **Checkout** → always first.
2. **Cache** → pip wheels keyed by `hashFiles('pyproject.toml')`.
3. **Setup Python matrix**.
4. **Install deps** (+ `--upgrade pip`).
5. **Run ruff** (`ruff src tests`).
6. **Run pytest** with coverage (`pytest --cov=src --cov-report=xml`).
7. *(Optional)* **Upload coverage** to Codecov for a shiny badge — future sprint.

*Where did those steps come from?* — every line maps back to a doc bullet you just read.


### 5 · Implement & test locally (dry-run)

Create `.github/workflows/ci.yml` with the structure above.
Commit → push a **feature branch** `ci/basic-pipeline`.
Open PR to **dev** — you **expect** red X the first time if you typo YAML; fix → push again.

> ⏳ *CI round-trip teaches you to read logs, not guess.*


### 6 · Enforce it

* Repo → **Settings → Branch protection**

  * Require status checks → select the new **ci** workflow.
* README badge (after the first green run):

```md
![CI](https://github.com/<user>/fraud-detection-system/actions/workflows/ci.yml/badge.svg)
```


### 7 · Acceptance checklist (for your Sprint doc)

* [ ] Workflow runs on `pull_request` & `push` to `dev`.
* [ ] Matrix covers **3.12** and **3.11**.
* [ ] `ruff` step fails on unused import (try adding one, watch it go red, then remove).
* [ ] `pytest` step passes with ≥70 % coverage (only sanity test for now).
* [ ] Badge visible in README.
* [ ] Branch protection uses the workflow.
* [ ] **OPS-01** card → **Done**.


### 8 · Reflection prompts (write answers in your dev journal)

1. *What benefit does a coverage threshold give compared to “just run tests”?*
2. *Why might you split lint and test into separate jobs later?*
3. *What’s the trade-off of adding more Python versions to the matrix?*
4. *How would you cache Terraform plugins in a future workflow?*

Being able to narrate these choices = **senior-ish** competency.

---

### 9 · Next sprint dependency

When we tackle **IAC-01**, any badly-formatted `.tf` file will already fail in the same CI run — no extra work. That’s the compounding payoff of OPS-01.


**Action for you:**

1. Read the docs (step 1), pick version pins, update `pyproject.toml`.
2. Build the workflow YAML from scratch — resist copy-paste until you understand each line.
3. Push → iterate until ✅.
4. Move the board card, tick Sprint-01 file, and drop a short stand-up note.

---

## Code Explanation (just for refreshing + deep understanding during review)
This “advanced” `ci.yml` builds on your earlier workflow by:

* **Cancelling in-flight runs** when you force-push (via `concurrency`),
* **Re-using cached dependencies** (via `actions/cache`),
* **Splitting lint, test, and security** into separate jobs (so they can run in parallel or continue on failures as needed),
* **Testing across multiple Python versions** (via a matrix),
* **Injecting a “dev” group** of Poetry deps,
* **Failing fast or soft-failing** selectively (e.g. security scans still run even if lint fails),
* **Enforcing minimum coverage** at test time, and
* **Pinning your tools** for reproducibility.

Below is a breakdown:

---

### Top-level settings

```yaml
name: CI
```

Gives this workflow the simple name **“CI”** in GitHub’s Actions UI.

```yaml
on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]
```

Trigger on any **push** or **PR** against `main` or `dev`—so you catch problems both on direct commits and via pull requests.

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

* **`group`**: groups runs by branch or PR ref (e.g. `ci-refs/heads/dev`).
* **`cancel-in-progress: true`**: if you push a new commit to the same branch/PR, GitHub will cancel the previous run. Keeps your queue clean and speeds feedback on force-pushes.

```yaml
env:
  POETRY_VIRTUALENVS_CREATE: "false"
```

Tells Poetry **not** to create its own virtual environment; instead installs straight into the runner’s Python. Speeds up setup and simplifies caching.

---

### Job 1: **Lint**

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
```

1. **Checkout** your code so you can lint it.

```yaml
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
```

2. **Install Python 3.12** on the runner.

```yaml
      - uses: actions/cache@v4
        with:
          path: |
            ~/.cache/pip
            ~/.cache/pre-commit
          key: ${{ runner.os }}-lint-${{ hashFiles('pyproject.toml', '.pre-commit-config.yaml') }}
          restore-keys: |
            ${{ runner.os }}-lint-
```

3. **Cache** your pip and pre-commit caches across runs.

   * **`key`** ties the cache to your OS plus a hash of your dependency files;
   * **`restore-keys`** lets you fall back to older caches if the exact key misses.

```yaml
      - uses: abatilo/actions-poetry@v4
        with:
          poetry-version: "1.8.3"
```

4. **Install Poetry 1.8.3** (pinned for reproducibility).

```yaml
      - name: Install dev dependencies
        run: poetry install --no-interaction --no-root --with dev
```

5. **Install only your dev-group** dependencies (`pre-commit`, `black`, `ruff`, etc.), skipping your project package itself (`--no-root`).

```yaml
      - name: Run pre-commit hooks
        run: |
          poetry run pre-commit run --all-files --show-diff-on-failure
```

6. **Execute all pre-commit hooks** (formatters, linters, secrets scanners, Terraform fmt/validate).

   * `--show-diff-on-failure` makes it easier to see what Black/Ruff would change.

---

### Job 2: **Test & Coverage**

```yaml
  test:
    needs: lint
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.11"]
```

* **`needs: lint`**: waits for lint to pass.
* **`matrix:`** runs this job *twice*, once under Python 3.12 and once under Python 3.11.

```yaml
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
```

1. **Checkout** & **setup the matrix’d Python version**.

```yaml
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ matrix.python-version }}-${{ hashFiles('pyproject.toml') }}
          restore-keys: |
            ${{ runner.os }}-pip-${{ matrix.python-version }}-
```

2. **Cache pip** for this Python version, keyed by `pyproject.toml`.

```yaml
      - uses: abatilo/actions-poetry@v4
        with:
          poetry-version: "1.8.3"
```

3. Pin Poetry again.

```yaml
      - name: Install dev dependencies
        run: poetry install --no-interaction --no-root --with dev
```

4. Install the same dev deps so you can run tests and coverage.

```yaml
      - name: Run tests with coverage
        run: |
          poetry run pytest -q --cov=src --cov-report=xml --cov-fail-under=70
```

5. **Run `pytest`** with coverage measured on your `src/` directory.

   * `-q`: quiet output
   * `--cov-report=xml`: emit `coverage.xml`
   * `--cov-fail-under=70`: fail the job if total coverage < 70%.

```yaml
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          files: ./coverage.xml
          flags: unittests
          fail_ci_if_error: true
```

6. **Upload to Codecov** under the `unittests` flag.

   * Omitting the token on public repos works too;
   * `fail_ci_if_error: true` ensures any upload issue marks the CI as failed.

---

### Job 3: **Security Scans**

```yaml
  security:
    needs: lint
    if: ${{ always() }}
    runs-on: ubuntu-latest
```

* **`needs: lint`** ensures lint runs first (so you don’t scan broken code).
* **`if: always()`** makes this job run **even if** lint or tests fail—so security scans always give feedback.

```yaml
    steps:
      - uses: actions/checkout@v4
```

1. Checkout again for the security checks.

```yaml
      - name: tfsec (Terraform static scan)
        if: hashFiles('**/*.tf') != ''
        uses: aquasecurity/tfsec-action@v1.0.3
        with:
          soft_fail: false
```

2. **`tfsec`** only runs if any `.tf` file exists. High-severity findings fail the build.

```yaml
      - name: Checkov (IaC / Docker / Python scan)
        uses: bridgecrewio/checkov-action@v12.1347.0
        with:
          quiet: true
          soft_fail_on: MEDIUM
```

3. **`Checkov`** scans Terraform, Dockerfiles, GitHub workflows, etc., but will only hard-fail on HIGHs.

---

#### Why it’s “more advanced”

* **Parallelization**: lint ⟂ test matrix ⟂ security
* **Caching**: pip & pre-commit caches speed up repeated runs
* **Branch-level cancellation**: no wasted CI minutes on replaced runs
* **Matrix testing**: ensures your code works on multiple Python versions
* **Selective failure modes**:

  * Cover-under threshold fails fast,
  * Security always runs (and can soft-fail mediums),
  * Codecov upload errors break CI only if critical.
* **Pinning** (actions, Poetry, etc.) gives reproducible, predictable builds.

All of these combine to give you **faster feedback**, **more resilient pipelines**, and **clearer separation** of concerns than your initial single-job CI.
