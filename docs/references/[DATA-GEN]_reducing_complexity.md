Here’s the surgical, methodical plan:

---

## 1. Static code‐scan & baseline estimate

* **Heavy Python‐level loop in `generate_dataframe`**
  The core routine builds a list of `total_rows` dicts, each filled via multiple calls to `random.*`, `Faker`, and Python branching, then calls `pl.DataFrame(rows)` .
* **Memory blow‐up**
  Holding millions of Python dicts and then materializing into Polars incurs large allocation overhead and GC pressure.
* **I/O and serialization**
  Writing one huge Parquet is fine, but generating every record in pure Python incurs both CPU‐ and memory‐bound stalls.
* **Baseline throughput**
  On a typical dev machine, a similar list‐of‐dicts approach with Faker/random modules yields on the order of **500–2 000 rows/sec**.

  * At **1 000 rows/sec**, 1 M rows → \~1 000 s (\~17 min).
  * At **500 rows/sec**, → \~2 000 s (\~33 min).
    We need **≥20× speed-up** to hit a 5 min target for 1 M rows.

---

## 2. High-level optimization methodology

1. **Vectorize record generation**

   * Pre-generate entire columns with NumPy (e.g. `np.random.uniform`, `rng.choice`) or Polars APIs, rather than per-row Python calls.
   * Build the DataFrame in one shot instead of appending dicts.
2. **Chunked buffering**

   * If memory is a concern, generate in batches (e.g. 100 k rows), write/apply, then proceed.
3. **Parallel sharding**

   * Divide `total_rows` into N shards and use `multiprocessing.Pool` or Polars’ native multithreading to generate shards concurrently.
4. **Minimize Python↔Rust crossings**

   * Avoid bridges like `random.random()` per row; instead use large‐array draws in one call.
5. **Leverage Polars/LazyFrame**

   * Where possible, push logic into Polars expressions (e.g. conditional assignment, casting) so it executes in Rust.
6. **Continuous micro-benchmarking**

   * After each refactor, run a small-timing harness (e.g. `pytest-benchmark`) on 100 k rows to verify performance gains and prevent regression.

---

## 3. File-by-file refactoring plan

> **(We’ll leave `core.py` for last, since it’s the biggest change.)**

1. **`config.py`**

   * **Remove duplicate class definitions** at bottom of file. (They shadow earlier ones.)
   * **Cache** the loaded YAML schema if re-reading occurs.
   * **No performance impact**, but cleans up potential confusion.

2. **`cli.py`**

   * **Add `--workers` flag** to control parallel shards.
   * Wire that flag into `generate_dataframe` so we can spawn N workers.
   * **Introduce batch‐size** argument to control chunk sizes.

3. **`generate.py`**

   * No logic here beyond aliasing—**no changes** required.

4. **`catalog.py`**

   * Tiny wins:

     * Move repeated `default_rng(seed)` call into one RNG instance.
     * For `pan_hash`, replace per-card Faker loop with a **single list comprehension seeded once** (it already does this, so minimal change).
   * **Keep** current NumPy vectorization; no structural overhaul.

5. **`temporal.py`**

   * Already fully vectorized via NumPy.
   * **Minor tweak**: accept a global RNG instance rather than re‐creating per call (for consistency across shards).

6. **`core.py`**

   * **Full rewrite** of `generate_dataframe`:

     * **Step A**: Pre-compute all arrays (UUIDs, timestamps, offsets, amounts, risk flags, categorical draws) using vectorized APIs.
     * **Step B**: Assemble a Polars DataFrame directly from these arrays (or via a `pl.LazyFrame` with expressions).
     * **Step C**: Optionally split into worker shards (if `cfg.workers > 1`) and parallelize.
   * Maintain exact schema (column order and types) and the fraud-label logic, but move all per-row work into batched operations.

---
