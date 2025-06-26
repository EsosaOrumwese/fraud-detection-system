# Breakdown of Issue DAT-02
## DAT-02 — Spike: generate **1 million** synthetic payments (Polars) → profile → push Parquet to S3

### *Mentor-style walk-through (thinking path, no final script yet)*

---

### 0 · Why this matters

| Sandbox pain                                                     | What you’ll prove                                                            | Interview line                                                               |
|------------------------------------------------------------------|------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| Tiny CSV demos don’t surface scaling issues.                     | You can craft **memory-safe** generators that hit ≥ 50 k rows/s on a laptop. | “I produced 1 M rows in 20 s using Polars and streamed straight to Parquet.” |
| Dirty/biased data sinks model quality.                           | You bake in realistic distributions & null-rates from spec.                  | “Fraud label set at 0.3 % prevalence with class-imbalance stratification.”   |
| Future teams complain “we don’t know what your data looks like.” | Profiling report + HTML artifacts for instant EDA.                           | “Here’s the YData-Profiling report stored alongside the Parquet in S3.”      |

---

### 1 · What to read first (≈ 1 h)

| Source                                                 | Why skim / deep-read                                      |
|--------------------------------------------------------|-----------------------------------------------------------|
| **Polars cookbook** → “From rows/structs to DataFrame” | Learn `pl.from_dicts` + lazy API.                         |
| **Faker** & **Mimesis** providers                      | Copy/paste code snippets for credit cards, MCCs, devices. |
| **PyArrow Parquet write\_options**                     | Columnar compression (`"snappy"`) + row-group size.       |
| **ydata-profiling** quickstart                         | Generate HTML in < 30 s for 1 M rows.                     |
| **Boto3** S3 multipart upload                          | Avoid memory blow-ups for 50 MB+ files.                   |

Take quick notes in `/docs/references/DAT-02_notes.md`.

---

### 2 · Design calls → log in **ADR-0006**

| Topic              | Decision                          | Rationale                                            |
|--------------------|-----------------------------------|------------------------------------------------------|
| Generator language | **Polars (Rust core)**            | 10-20× faster than Pandas; sustains 1 M rows easily. |
| Row-group size     | 128 MB default                    | Good perf / memory trade-off.                        |
| Compression        | `"snappy"`                        | Widely supported, fast to read in Spark / DuckDB.    |
| Fraud prevalence   | 0.3 % (\~3 k rows)                | Mirrors real card fraud baselines.                   |
| Upload strategy    | Boto3 `upload_file` (single shot) | 50 MB Parquet fits simple API call.                  |
| File naming        | `payments_1M_2025-05-YY.parquet`  | Timestamped; no overwrite.                           |

---

### 3 · Repo prep (10 min)

```bash
poetry add polars faker mimesis pyarrow ydata-profiling boto3
mkdir -p src/fraud_detection/simulator outputs
touch src/fraud_detection/simulator/generate.py
```

Add Make targets:

```makefile
.PHONY: data profile
data:
	poetry run python src/fraud_detection/simulator/generate.py --rows 1_000_000 --out outputs/
profile: data
	poetry run python scripts/profile_parquet.py outputs/payments_1M_*.parquet
```

---

### 4 · Incremental build steps (with expected console hints)

| Step                            | Command                                                   | Expected output                              |
|---------------------------------|-----------------------------------------------------------|----------------------------------------------|
| **4.1** Quick 10k prototype     | `--rows 10_000`                                           | “Generated 10 000 rows in 0.18 s (55 k r/s)” |
| **4.2** Validate schema columns | unit test compares `df.columns` to YAML field names       | ✔                                            |
| **4.3** Scale to 1 M            | `--rows 1_000_000`                                        | “Peak RSS ≤ 500 MB, 20 s elapsed”            |
| **4.4** Parquet write           | file ≤ 55 MB in `outputs/`                                | `payments_1M_2025-05-29.parquet`             |
| **4.5** Profiling               | `profile_parquet.py` → HTML                               | `profile_1M_2025-05-29.html` (\~3 MB)        |
| **4.6** Upload to S3            | CLI prints “Upload complete to s3://fraud-raw-…/2025/05/” |                                              |
| **4.7** Teardown test           | `aws s3 ls` shows file                                    |                                              |

*Profiling script can be \~12 lines: read Parquet (lazy), sample 100 k rows → `ProfileReport(df)`.*

---

### 5 · Unit tests to add

```python
def test_row_count(tmp_path):
    path = generate_dataset(rows=50_000, out_dir=tmp_path)
    df = pl.read_parquet(path)
    assert df.height == 50_000
```

Add to CI matrix (small row count).

---

### 6 · Common pitfalls & how to debug

| Symptom                      | Likely cause                             | Fix                                                                                             |
|------------------------------|------------------------------------------|-------------------------------------------------------------------------------------------------|
| RAM spikes >2 GB             | Converting list→DataFrame after all rows | Build list of dicts in chunks of 100 k; concatenate Polars.                                     |
| Faker slows after 500 k rows | Global locale RNG overhead               | Pre-compile providers (`faker = Faker(); rand_cc = faker.credit_card_number`) and use in loops. |
| Upload times out             | Default timeout < file size              | Set `Config(signature_version='s3v4', retries={'max_attempts': 5})`.                            |
| Profiling HTML 100 MB        | Using full DF                            | Sample 100 k rows before profiling.                                                             |

---

### 7 · Level-up extras (optional)

| Extra                                                          | Effort | Wow factor                                    |
|----------------------------------------------------------------|--------|-----------------------------------------------|
| **ThreadPool / Rayon** in Polars to parallel-generate rows     | 15 min | Hit 200 k r/s on M-series Apple or modern x86 |
| **Great Expectations** expectations suite auto-built from YAML | 15 min | Data-quality CI gates                         |
| **Dockerfile** for simulator                                   | 10 min | Containerized reproducibility                 |
| **Prefect flow** wrapper                                       | 20 min | Introduces orchestration ahead of next sprint |

---

### 8 · Definition-of-Done

* [ ] `generate.py` CLI produces **1 M** rows in ≤ 30 s on laptop (< 1 GB RAM).
* [ ] Output Parquet ≤ 60 MB, **snappy** compressed.
* [ ] `profile_…html` saved locally **and** uploaded with Parquet to **fraud-raw** S3 bucket.
* [ ] Unit tests for row-count & schema pass in CI (small dataset).
* [ ] ADR-0006 committed (generator design).
* [ ] PR merged; **DAT-02** card → **Done**.

---

### 9 · Your next moves

1. Prototype 10 k rows; iterate until Polars DSL feels comfy.
2. Scale to 1 M, profile memory/time (`/usr/bin/time -v`).
3. Write upload code (use the IAM role created in IAC-01).
4. Generate and push profiling HTML.
5. Open PR → CI green → merge.
6. Drop a Sprint stand-up note with timings & Parquet size.

---

## 🚀 DAT-02 — **Reinforced Mentoring Play-Book**

**Spike script → 1 million synthetic payments (Polars) → YData-Profiling HTML → Parquet to S3**

*Everything a beginner needs to turn out work that makes veteran DS / MLOps folks grin.*

---

### 0 · Outcomes that Make Seniors Say “Nice!”

| Target “wow” signal                | Observable proof                                                                                           |
|------------------------------------|------------------------------------------------------------------------------------------------------------|
| **Fast & memory-safe** generator   | 1 M rows in ≤ 30 s, peak RAM < 1 GB on laptop (measure with `/usr/bin/time -v`).                           |
| **Realistic** distributions & dirt | Fraud prevalence accurately set (0.3 %), 5–10 % nulls on noisy fields, valid ISO / MCC / currency codes.   |
| **Re-usable** artefacts            | Parquet (Snappy) + lightweight HTML profile + versioned script under `src/fraud_detection/simulator/`.     |
| **Infra integration**              | File lands in `s3://fraud-raw-<suffix>/2025/05/` using the IAM role from IAC-01, no manual console clicks. |
| **Governance**                     | ADR-0006 explains design/assumptions; CI runs unit tests + lint on every push.                             |

---

### 1 · Study Pack  (**\~90 min** — capture bullets in `docs/references/DAT-02_notes.md`)

| Link (search & open)                                           | How deep?        | One key note to write                                            |
|----------------------------------------------------------------|------------------|------------------------------------------------------------------|
| **Polars cookbook** – “from\_dicts”, “lazy API”, “groupby agg” | Deep-read 15 min | `pl.DataFrame(df_rows).with_columns(...)` beats Pandas at scale. |
| **Polars performance tips** (official blog)                    | Skim 5 min       | Chunk-append in 100–200 k rows to cap memory.                    |
| **Faker docs**                                                 | Skim             | Provider `credit_card_full`, `ipv4_public`, `uuid4`.             |
| **Mimesis docs**                                               | Skim             | `business.mcc()` – gives valid MCC.                              |
| **PyArrow Parquet write\_options**                             | Skim             | Snappy default, row group ≈ 128 MB.                              |
| **YData-Profiling** “large datasets” note                      | Skim             | Pass `df.sample(100_000)` to avoid 500 MB HTML.                  |
| **Boto3 multipart upload** quickstart                          | Deep-read 10 min | `upload_file` internally switches to multipart at > 8 MB.        |
| *Optional:* AWS “Well-Architected – Data Pillar”               | Skim             | Compression & partitioning trade-offs.                           |

---

### 2 · Design Decisions → **ADR-0006**

| Question           | Decision & rationale (cite doc)                                                                    |
|--------------------|----------------------------------------------------------------------------------------------------|
| Data-frame library | **Polars** (Rust core, zero-copy) -→ meets 1 M rows perf target.                                   |
| Fraud prevalence   | **0.3 %** (≈ 3 000 rows) -→ typical card-present fraud rate.                                       |
| Null strategy      | 8 % nulls on `device_id`, 5 % on `mcc_code`, 1 % on `latitude/longitude` to mimic production gaps. |
| Geolocation        | Country centroid + jitter ±0.5°; lat/long 6-decimal precision (\~11 cm).                           |
| Time distribution  | `event_time` uniform in last 30 days; skew peak 4–8 p.m. local (normal(μ = 18h, σ = 3h)).          |
| Parquet write      | **Snappy** compression, 128 MB row-group (PyArrow default) for downstream analytics.               |
| S3 key layout      | `payments/year=YYYY/month=MM/payments_1M_YYYYMMDD.parquet` (Athena-friendly).                      |
| Upload method      | Boto3 `upload_file` with IAM role from IAC-01.                                                     |

Commit ADR-0006 *before* script: looks professional.

---

### 3 · Environment & Repo Prep (**15 min**)

```bash
poetry add polars faker mimesis ydata-profiling boto3 pyarrow
mkdir -p src/fraud_detection/simulator scripts outputs
touch src/fraud_detection/simulator/generate.py \
      scripts/profile_parquet.py
```

#### Add Make targets

```makefile
.PHONY: data profile
data:
	poetry run python src/fraud_detection/simulator/generate.py \
		--rows 1_000_000 --out outputs/
profile: data
	poetry run python scripts/profile_parquet.py \
		--file outputs/payments_1M_*.parquet
```

#### Pre-commit tweaks

```yaml
- repo: https://github.com/charliermarsh/ruff-pre-commit
  rev: v0.4.3
  hooks:
    - id: ruff

- repo: local            # yamllint already exists
  hooks:
    - id: pytest
      name: pytest-small
      entry: pytest -q tests/unit/test_simulator.py
      language: system
      pass_filenames: false
```

---

### 4 · Build in 6 Micro-Steps (with CLI checkpoints)

| # | What you code                                                                                              | Quick test command             | Success sign                    |
|---|------------------------------------------------------------------------------------------------------------|--------------------------------|---------------------------------|
| 1 | **`generate.py` skeleton** – argparse, loop 10 k rows, Polars DF, write Parquet to `tmp.parquet`.          | `--rows 10_000`                | “10 000 rows in 0.1 s” printed. |
| 2 | **Schema bind** – import YAML spec, ensure all 24 column names match.                                      | `pytest` small test            | green.                          |
| 3 | **Scale chunks** – generate 100 k rows at a time, append with `pl.concat()`.                               | `/usr/bin/time -v`             | Max RSS ≤ 500 MB.               |
| 4 | **Inject fraud labels & nulls** – vectorised operations: `pl.when(pl.Series(...).is_in(fr_idx)... )`.      | unit test: class ratio ±0.01 % | ✔                               |
| 5 | **Write Parquet & profile** – `pl.scan_parquet` sample 100 k → YData-Profiling HTML.                       | `make data profile`            | `profile_*.html` size < 5 MB.   |
| 6 | **Upload** – read bucket & prefix from env / `config/dev.env`; call `boto3.client('s3').upload_file(...)`. | CLI prints S3 URL              | File visible in console.        |

---

### 5 · Unit Tests (CI-friendly, 50 k rows max)

```python
import polars as pl, pathlib, yaml
from fraud_detection.simulator.generate import generate_dataset

SCHEMA = yaml.safe_load(pathlib.Path("schema/transaction_schema.yaml").read_text())

def test_schema_match(tmp_path):
    path = generate_dataset(50_000, tmp_path)
    df = pl.read_parquet(path)
    assert set(df.columns) == {f["name"] for f in SCHEMA["fields"]}

def test_class_balance(tmp_path):
    path = generate_dataset(50_000, tmp_path)
    df = pl.read_parquet(path)
    fraud_rate = df.select(pl.col("label_fraud").mean()).item()
    assert 0.002 < fraud_rate < 0.004      # 0.3 % ± 0.1
```

---

### 6 · Integrate with CI (5 min)

Add step after lint in `ci.yml`:

```yaml
- name: Simulator unit tests
  run: poetry run pytest -q tests/unit/test_simulator.py
```

Caches build so ≤ 30 s run.

---

### 7 · Performance Tuning Tips

| Bottleneck symptom                     | Quick fix                                                                                         |
|----------------------------------------|---------------------------------------------------------------------------------------------------|
| *CPU pegged; RAM flat*                 | Increase Polars `insert_capacity` or generate in parallel via `rayon` (set `POLARS_MAX_THREADS`). |
| *Faker slows drastically > 500 k rows* | Instantiate providers once; avoid `Faker(locale=…)` inside loop.                                  |
| *Upload chokes on 50+ MB*              | Use `upload_file` (multipart auto) **or** `s3transfer` with `max_concurrency=4`.                  |
| *Profiling HTML huge*                  | Sample first (`df.sample(100_000, with_replacement=False)`).                                      |

---

### 8 · Common Pitfalls & Debugging

| Error                                       | Cause                                          | Remedy                                                           |
|---------------------------------------------|------------------------------------------------|------------------------------------------------------------------|
| `ArrowInvalid: ParquetInt32` mismatch       | Col type inferred wrong (e.g., mix int & None) | Cast columns: `with_columns(pl.col("mcc_code").cast(pl.Int32))`. |
| Memory blow-up                              | Building list of dicts then DF                 | Generate Polars `Struct`s directly or chunk concat.              |
| `botocore.exceptions.NoCredentialsError`    | Forgot to export `AWS_PROFILE=fraud-sandbox`   | Source env file or use IAM role on EC2.                          |
| Unit test flakiness (`fraud_rate` variance) | Random seed not fixed                          | `random.seed(42)` + `faker.seed_instance(42)`.                   |

---

### 9 · Level-Up Extras (if buffer hours exist)

| Extra                                                          | Effort | Senior shine                                           |
|----------------------------------------------------------------|--------|--------------------------------------------------------|
| **Prefect flow** wraps generator + uploader                    | 20 min | Introduces orchestration & retries ahead of Sprint-02. |
| **DuckDB validation** – run simple SQL on Parquet after upload | 10 min | Shows cross-engine compatibility.                      |
| **Dockerfile** `simulator.dockerfile` + GH-Action release      | 15 min | Shareable CLI image: `ghcr.io/you/simgen:0.1.0`.       |
| **In-Parquet statistics** – add min/max metadata row-groups    | 10 min | Better query pruning.                                  |

---

### 10 · Definition-of-Done (paste into Sprint doc)

* [ ] `generate.py` CLI produces 1 M rows in ≤ 30 s, RAM < 1 GB.
* [ ] Parquet file ≤ 60 MB, Snappy compressed, schema matches YAML.
* [ ] YData-Profiling HTML generated (≤ 5 MB) & uploaded alongside Parquet.
* [ ] Unit tests for schema & fraud prevalence pass in CI.
* [ ] ADR-0006 committed.
* [ ] PR merged → **DAT-02** card → **Done**.

---

### 11 · Reflection Prompts (write short answers)

1. *Why Polars over Pandas for write-once, read-many synthetic data?*
2. *What trade-offs exist between row-group size and interactive query latency?*
3. *How would you introduce seasonality spikes (e.g., Black Friday) when generating month-long data?*
4. *How could this generator plug into a streaming system (Kinesis) later?*

---

### 12 · Next Actions for **you**

1. **Prototype 10 k rows**; profile runtime & memory.
2. Scale to 1 M, tweak chunk size until specs pass.
3. Wire upload & profiling, commit artefacts (Parquet + HTML) to S3.
4. Push branch `feat/simulator-1M`, open PR → CI should pass first go.
5. Move **DAT-02** card once merged, drop timings in stand-up.

Tag me here when your PR is up—then I’ll ship a concise reference script and we’ll close Sprint-01 strong. ✨

