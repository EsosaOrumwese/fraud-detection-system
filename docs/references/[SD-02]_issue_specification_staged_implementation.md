# Technical Specification for SD-02
**1. Purpose & Scope**
This document specifies enhancements to the fraud‐data generator’s temporal sampling (SD-02 sprint), enabling configurable weekday seasonality and time‐of‐day profiles in a way that is fully backward-compatible and extensible. It addresses:

* **Weekday seasonality** via user-supplied relative weights per weekday, affecting the probability of selecting each calendar date.
* **Time-of-day profiles** through configurable mixture components, replacing the current hard-coded Gaussian peaks.
* **Reproducibility** by supporting RNG seeding.
* **Time zone awareness** and handling of daylight-saving transitions.
* **Observability** by emitting sampling metrics and logging normalized parameters.
* **Extensibility** so future non-Gaussian or empirical distributions can be plugged in without refactoring core logic.

All new fields are optional; omitting them yields the existing uniform-date, fixed-Gaussian behavior.

---

**2. Requirements & User Stories**

| ID   | Role               | Capability                                                                                                       | Benefit                                                              |
|------|--------------------|------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| US-1 | Data engineer      | Supply a mapping of weekdays (Monday=0 … Sunday=6) to non-negative weights                                       | Control relative volume by day (e.g. heavy Mondays, light weekends)  |
| US-2 | Data scientist     | Provide a list of time-of-day components each defined by mean hour, standard deviation in hours, and weight      | Simulate domain-specific peaks (e.g. lunch, evening rush)            |
| US-3 | Developer/CLI user | Override config file parameters at runtime via CLI arguments for weekday weights and time components             | Rapid experimentation without editing YAML                           |
| US-4 | Data engineer      | Seed the temporal RNG from configuration or CLI                                                                  | Guarantee reproducible timestamp sequences                           |
| US-5 | Observability lead | Receive metrics or logs summarizing the final normalized weekday and time-component weights at startup           | Validate that simulation adheres to requested profile                |
| US-6 | Test author        | Detect and report invalid configurations (e.g. negative weights, missing distributions, unknown weekday keys)    | Ensure early failure with clear error messages                       |
| US-7 | Developer          | Extend or swap out the underlying distribution type (e.g. log-normal, empirical histogram) without core rewrites | Accommodate future use cases without modifying existing sampler code |

---

**3. Configuration Schema**
Enhance the existing `TemporalConfig` section with the following optional fields:

* **weekday\_weights**: a mapping from integer weekday to non-negative float weight.

  * Keys must be in the range 0 through 6.
  * Values may be any non-negative real number.
  * Omitted weekdays default to zero weight.
* **time\_components**: a sequence of component objects, each containing:

  * `mean_hour`: real number in \[0, 24), representing the center of the peak in hours.
  * `std_hours`: positive real number, the Gaussian standard deviation in hours.
  * `weight`: non-negative real number.
* **seed**: optional integer or string seed used to seed the RNG for both date and time sampling.
* **distribution\_type**: optional string tag (“gaussian” by default) indicating which distribution implementation to use; reserved for future extension.

All weight sequences are normalized internally so that their sums equal one. If any weight sum is zero, configuration loading fails with an explicit error.

---

**4. Command-Line Interface**
Add new flags to the existing CLI entrypoint, parsed after the config file is loaded but before sampling occurs:

* `--weekday-weights`: JSON string or path to JSON file containing the weekday‐to‐weight map. Partial maps merge with or override the YAML mapping; unspecified weekdays inherit existing values or zero if none.
* `--time-components`: JSON string or path to JSON file listing the time component objects. Providing this flag replaces any YAML “time\_components” section entirely.
* `--seed`: integer or string seed to override or set the RNG seed, ensuring deterministic output.
* `--distribution-type`: unnamed argument to select a different distribution class if implemented.

The precedence order is: defaults < config file < CLI flags.

Invalid flag values (e.g. malformed JSON, missing required fields, out-of-range numbers) cause immediate exit with an error message describing the offending key and expected range.

---

**5. Design Details**

**5.1. Distribution Interface**
Define an abstract `TemporalDistribution` interface with a `sample(size, rng, **params)` method. Implement the built-in Gaussian mixture sampler under this interface. Future implementations (log-normal, empirical histogram) can register under a unique `distribution_type` key.

**5.2. Weekday Sampling**

* Construct the list of all calendar dates between `start_date` and `end_date`, inclusive.
* Map each date to its weekday index, then to the configured weight (zero if unspecified).
* Normalize the per-date weights so their sum equals one.
* Sample exact dates by drawing indices from this weighted distribution.

Edge cases:

* If only one date has non-zero weight, all samples fall on that date.
* If sum of supplied weekday weights is zero, loading fails with a descriptive exception citing “weekday\_weights sum must be > 0.”

**5.3. Time-of-Day Sampling**

* Read the list of components (mean\_hour, std\_hours, weight).
* Convert mean\_hour and std\_hours to seconds internally.
* Normalize component weights to sum to one.
* For each sampled date, select a component index by sampling from the normalized weight vector.
* Draw a time offset from a Gaussian with the selected mean and standard deviation.
* Clip or wrap values outside midnight-to-midnight as a configurable policy (default: clip at nearest boundary).

Edge cases:

* Single component with zero deviation yields nearly identical times.
* Sum of weights zero triggers configuration error.

**5.4. Time Zone and DST Handling**

* All date arithmetic and timestamp construction occur in UTC internally to avoid DST ambiguity.
* If users require local times, they may post-process using external timezone libraries.
* Document that Gaussian peaks refer to UTC hours; clients must adjust if they desire local hour semantics.

**5.5. RNG Seeding and Reproducibility**

* A single seed initializes both the date‐sampling RNG and the time‐sampling RNG in a reproducible sequence.
* The seed may come from config, CLI, or a system default if unset (e.g. timestamp‐based).
* Document that changing the seed, date range, or distribution parameters yields a wholly new sample sequence.

**5.6. Performance and Thread Safety**

* Precompute the per-date probability array once.
* Use vectorized sampling functions to minimize Python‐level loops.
* The sampler does not share RNG state across threads; for multi‐threaded use, users must instantiate separate generator instances.

**5.7. Logging and Observability**

* On startup, log at DEBUG level the normalized weekday weights and time-component weights with full precision.
* Emit a metric or summary histogram (e.g. via a user‐provided callback) showing the empirical versus target weights after a dry-run of N samples.
* Error conditions (invalid JSON, out-of-range values) produce clear messages indicating the path to the bad value and its permissible range.

---

**6. Configuration Reference**

* **weekday\_weights**: mapping of integer keys “0” through “6” to non-negative floats.

  * Example valid: a Monday-heavy profile with lighter weekend:
    `{ "0": 1.5, "1": 1.0, "2": 1.0, "3": 1.0, "4": 1.0, "5": 0.5, "6": 0.3 }`
  * Example invalid: negative weight or key “7” → load failure citing invalid key or negative value.

* **time\_components**: list of objects each containing `mean_hour` in \[0, 24), `std_hours` > 0, and `weight` ≥ 0.

  * Valid example with three peaks at 8 AM, noon, and 6 PM: list of three objects mapping to mean\_hour 8.0, 12.0, 18.0 with respective std\_hours and weights.
  * Invalid example: empty list or all weights zero → load failure citing “sum of weights must be > 0.”

* **seed**: integer or string, used to initialize RNG. Omitting yields non-deterministic runs.

* **distribution\_type**: string, defaults to “gaussian.” Unknown values → load failure with allowed types enumerated.

---

**7. Testing & Validation**

* **Unit Tests:**

  * Verify that omitting new fields reproduces existing behavior exactly for a fixed date range and fixed default Gaussian parameters.
  * Test that a weekday\_weights map with one non-zero entry results in all sampled dates on that weekday.
  * Test that a single time\_component with weight one and zero std\_hours places all times exactly at the mean.
  * Ensure invalid configurations (negative weights, invalid keys, zero sums) raise descriptive exceptions.
  * Validate that providing a fixed seed yields identical timestamp sequences across two separate generator instantiations.
* **Integration Tests:**

  * Generate large samples (e.g. 100 000 events), bucket by weekday, and perform a chi-squared statistical test asserting that observed frequencies fall within a configurable tolerance of target weights.
  * Similarly, bucket time-of-day into hourly bins and compare to expected Gaussian mixture histogram.
* **CLI Parsing Tests:**

  * Confirm that JSON strings and file-based inputs for weekday\_weights and time\_components both load correctly.
  * Confirm that overriding only a subset of weekdays merges correctly with defaults.
  * Validate that malformed JSON or missing required fields produce exit code 1 and an error message indicating the exact problem.
* **CI Integration:**

  * Include all new tests in the existing pytest suite.
  * Add coverage thresholds for `temporal.py` and `config.py` to prevent regressions.
  * Ensure tests run in both Python 3.9 and 3.10 environments.

---

**8. Documentation & Versioning**

* **README Updates:**

  * Document new config fields with examples.
  * Explain seed behavior and UTC-based sampling.
  * Describe how to interpret logged weight summaries.
* **CHANGELOG Entry:**

  * Record SD-02 feature addition under “Added” section, listing each new config field, CLI flag, and major behavior change.
* **Migration Guide:**

  * Advise users that existing YAML files without new fields continue to function unchanged.
  * Describe how to adopt new fields, including examples of common patterns (e.g. weekend reduction, lunch-time surge).

This spec should serve as the definitive guide for implementing SD-02, ensuring clarity in configuration, code structure, testing, and operational concerns.

---

# Staged Implementation Guide
Below is the revised nine-stage plan for SD-02, now with explicit performance and efficiency requirements baked into each relevant phase. Each stage remains detailed—nothing is hand-waved away.

---

### Stage 1: Schema & Validation

**Goal:** Extend `TemporalConfig` to accept new fields, enforce correctness, and define chunked-generation parameters.

**Tasks:**

1. **Add new config fields** in `config.py`:

   * `weekday_weights: Optional[Dict[int, float]]`
   * `time_components: Optional[List[TimeComponentConfig]]`
   * `seed: Optional[Union[int, str]]`
   * `distribution_type: str = "gaussian"`
   * **NEW** `chunk_size: Optional[int]` (must be ≥ 1), controlling the maximum rows per sampling batch.
2. **Define `TimeComponentConfig`** with `mean_hour`, `std_hours`, `weight` and validators:

   * `0 ≤ mean_hour < 24`
   * `std_hours > 0`
   * `weight ≥ 0`
3. **Post-load validators** for `TemporalConfig`:

   * Keys in `weekday_weights` ∈ \[0,6], values ≥ 0.
   * Sum of `weekday_weights` > 0 if present.
   * Sum of `time_components.weight` > 0 if present.
   * **Normalize** all weight collections to sum to 1.
   * `chunk_size` must be a positive integer if provided.

**Acceptance:**

* Valid YAML/JSON yields a config object with normalized weights and an integer `chunk_size`.
* Invalid or zero-sum weights, out-of-range weekday keys, or non-positive `chunk_size` throw a `ValueError` citing the exact field.

---

### Stage 2: Abstract Distribution Interface

**Goal:** Introduce a pluggable distribution API without touching performance-critical loops later.

**Tasks:**

1. Define `TemporalDistribution` interface with

   ```python
   def sample(self, count: int, rng: np.random.Generator, **params) -> np.ndarray
   ```
2. Refactor the existing Gaussian logic into `GaussianMixtureDistribution`, registered under `"gaussian"`.
3. Build a registry/factory mapping `distribution_type` → class.

**Acceptance:**

* Requesting `"gaussian"` yields the exact existing sampling behavior.
* Unknown `distribution_type` triggers a clear “supported types: \[…]” error.

---

### Stage 3: Chunked & Weekday Sampling Logic

**Goal:** Efficiently sample large volumes of dates in memory-bounded, vectorized batches.

**Tasks:**

1. **Precompute date array**: list of all dates from `start_date` to `end_date`.
2. **Build per-date weight vector** via weekday lookup, normalized once.
3. **Implement chunked sampling:**

   * If `chunk_size` is set and `total_rows > chunk_size`, split sampling into ⌈total\_rows/chunk\_size⌉ iterations.
   * Each iteration draws `min(chunk_size, remaining)` samples from the same weight vector.
4. **Fallback** to single-shot vectorized draw if `chunk_size` is unset.

**Performance Note:**

* All operations use NumPy’s vectorized `choice` or `integers` calls—no Python-level loops per row.

**Acceptance:**

* For `chunk_size = X`, generator yields batches of size ≤ X and identical concatenated output to a non-chunked run.
* Uniform-date behavior remains unchanged when `weekday_weights` is absent.

---

### Stage 4: Chunked Time-of-Day Sampling Logic

**Goal:** Append time offsets in the same memory-efficient, batched fashion.

**Tasks:**

1. **Within each date-sampling chunk**, invoke the chosen `TemporalDistribution.sample(...)` with:

   * `count = chunk_actual_size`
   * `params` derived from normalized `time_components` or defaults.
2. **Convert hours → seconds**, sample component indices vectorized, then draw Gaussian offsets.
3. **Clip or wrap** out-of-bounds seconds at 0 or 24 h boundary (configurable policy).
4. **Concatenate** time offsets with dates to produce timestamp batches.

**Acceptance:**

* Single-component, zero-std test places all times exactly at the mean.
* Behavior matches legacy on no-override config.
* Combined date+time sampling respects `chunk_size` and reproduces full-batch output.

---

### Stage 5: CLI Integration

**Goal:** Expose all new fields, including `chunk_size`, via command-line flags with correct override semantics.

**Tasks:**

1. Add flags to `cli.py`:

   * `--weekday-weights` (JSON or file)
   * `--time-components` (JSON or file)
   * `--seed` (int or string)
   * `--distribution-type` (string)
   * **NEW** `--chunk-size` (positive integer)
2. **Parsing logic:**

   * Load CLI flags after config file parse.
   * Merge: defaults < config file < CLI.
   * For partial CLI maps, merge at the key/value level (e.g. only Saturday).
3. **Immediate validation**: malformed JSON, invalid ranges, or missing fields error out with exit code 1 and a message specifying “Flag `--foo`: invalid value X; expected …”.

**Acceptance:**

* CLI overrides behave predictably and merge correctly.
* Invalid flag inputs are caught pre-sampling with clear diagnostics.

---

### Stage 6: RNG Seeding & Reproducibility

**Goal:** Guarantee that a given `seed` and parameter set always produce the same timestamp sequence.

**Tasks:**

1. At generator startup, initialize a single `np.random.Generator(seed)` if `seed` is provided; else default to non-deterministic.
2. **Pass the same RNG** instance into both chunked date and time samplers.
3. **Document**: changing any parameter or seed regenerates an entirely new sequence.

**Acceptance:**

* Two runs with identical `seed` + config yield bit-identical timestamp arrays.
* Changing only `seed` yields a completely different stream.

---

### Stage 7: Logging, Observability & Performance Metrics

**Goal:** Surface both parameter normalization and runtime performance data.

**Tasks:**

1. **On startup**, log at DEBUG level:

   * Final normalized weekday weight vector (7 floats).
   * Final normalized time-component weights (list of floats and means/stds).
2. **Dry-run metrics callback**:

   * After the first chunk or an explicit dry-run of N=1 000 samples, compute empirical histograms for weekday and time.
   * Emit these via a user-supplied metric interface or callback.
3. **Performance logging**:

   * Measure per-chunk wall-clock time and peak memory (e.g. using `tracemalloc` or a lightweight custom tracker).
   * After sampling completes, log: total time, average throughput (rows/sec), and peak RSS.

**Acceptance:**

* Logs contain both weight summaries and performance metrics in a structured format.
* Metrics callback receives clear observed vs. target distributions for validation.

---

### Stage 8: Testing, Benchmarking & CI Integration

**Goal:** Build a test suite that guards functionality, statistical fidelity, and performance budgets.

**Tasks:**

1. **Functional & edge-case unit tests** (pytest):

   * Config load/validation errors.
   * Default vs. override behaviors for date/time/chunk\_size.
   * Seed reproducibility.
2. **Statistical integration tests**:

   * Large N (e.g. 100 000) sample, χ² test for weekday distribution within 1% tolerance.
   * KS (or χ²) test for time-of-day distribution within configurable bounds.
3. **CLI tests**: verify JSON flags, file flags, partial overrides, and error messages.
4. **Performance benchmarks** (pytest-benchmark or custom fixture):

   * Defined targets, for example:

     * **10 million** rows in **< 2 s** on standard 4-core CI runner.
     * **Memory** < 500 MB peak for 100 million rows.
   * Fail CI if throughput or memory budgets are breached.
5. **Coverage gating**: enforce ≥ 95% coverage on `temporal.py`, `config.py`, `cli.py`.

**Acceptance:**

* All tests pass on Python 3.9 & 3.10.
* Statistical tests flag any miscalibration.
* CI detects performance regressions and fails builds that exceed budgets.

---

### Stage 9: Documentation & Release

**Goal:** Provide users with clear instructions on the new features, performance knobs, and upgrade path.

**Tasks:**

1. **README updates**:

   * Full schema for `weekday_weights`, `time_components`, `seed`, `distribution_type`, `chunk_size`.
   * CLI flag reference with examples (including chunked runs).
   * Notes on UTC sampling, clipping policy, and RNG seeding semantics.
2. **Benchmark guide**:

   * How to run the built-in benchmark harness, interpret throughput and memory logs.
   * Example outputs and tips for tuning `chunk_size` to available hardware.
3. **CHANGELOG entry** under “Added” listing all new config fields, flags, and performance features.
4. **Migration guide**:

   * Reassure that existing configs without new fields behave identically.
   * Show snippets converting an SD-01 YAML to adopt weekday/time overrides and chunk\_size.
5. **Release tagging** and package metadata bump.

**Acceptance:**

* Documentation renders correctly on GitHub/GitLab.
* Users can follow the benchmark guide to validate performance on their own hardware.
* Release notes clearly outline the upgrade path and new performance controls.

---

Following these stages in order will deliver SD-02 with robust functionality, production-grade performance, and clear observability—so you can push large-scale fraud simulations fast, reliably, and efficiently.
