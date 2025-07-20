Below is the uncompacted, assumption‑surfaced ledger for **“Reproducibility and configurability.”**
Every sentence binds a premise to (a) the explicit file or database object where that premise is stored, (b) the deterministic code line or equation that consumes it, (c) the fingerprint that proves the premise was in force when data were minted, and (d) the CI alarm that rings when the premise drifts. Because nothing happens outside those four reference points, an auditor can re‑enact any row’s birth by replaying the chain exactly as written here.

---

The very first premise is that the build always executes inside the Docker image whose **content‑hash lives in `Dockerfile.lock`**. `pipeline_launcher.sh` reads the lock file’s `IMAGE_SHA256=` line, passes the digest to `docker run --pull=never`, then writes three items—container hash, container hostname, UTC start time—to the first three fields of a run‑local manifest at `/tmp/build.manifest`. CI job `validate_container_hash.yml` starts a sibling container from the same digest and hashes the root file system; any mismatch halts the workflow before a single artefact is touched.

Source code immutability follows. `git rev-parse --verify HEAD` exports the exact tree hash of the checked‑out repository; that forty‑character SHA‑1 becomes `source_sha1` on line 4 of the manifest. The generator’s internal version string is pulled from `fraudsim/__init__.py`; the file is decorated with `__codehash__ = "<TREE_SHA1>"`. At runtime `importlib.metadata.version` emits that same string, and a guard inside `main.py` raises `SourceHashMismatchError` if the embedded SHA‑1 differs from the manifest entry. Thus hot‑patching any Python file between container start and dataset write is impossible without detection.

No artefact may influence sampling unless it appears in **`artefact_registry.yaml`**. This registry’s top level is an ordered list of absolute POSIX paths. `artefact_loader.py` loops in lexical order, opens each path in binary mode, streams it into `sha256sum` and appends `digest  path` to the manifest. Simultaneously a `hashlib.sha256()` accumulator ingests `digest\n` bytes for every artefact. Once enumeration ends the accumulator’s hex digest becomes the **parameter‑set hash**—the 256‑bit signature of all configuration. `dataset_root = f"synthetic_v1_{param_hash}"` ensures that two runs differing by even one artefact byte land in different directories. CI step `compare_registry.py` regenerates the enumeration under a fresh interpreter and asserts that the manifest’s artefact list and the re‑enumeration are byte‑identical.

Randomness revolves around that parameter hash. The **master seed** is produced by taking the high‑resolution monotonic clock `time_ns()`, left‑shifting by 64 bits, then XOR‑ing with the low 128 bits of `param_hash`. The seed is printed onto line N of the manifest (`master_seed_hex=`) and passed to NumPy’s `Philox` constructor. Every module defines a static string `STREAM_NAME`, hashed with SHA‑1 to 128 bits; at module entry, code calls `rng._jump(int.from_bytes(stream_hash, 'big'))`. Because `_jump` is additive modulo 2¹²⁸, streams remain non‑overlapping. The *jump offset* is recorded per invocation in `logs/rng_trace.log` as `module,identifier,offset`. `replay_rng.py` in CI parses the trace, reproduces the counter state, draws the first three random numbers for spot‑check, and fails if any differ.

Configurability is confined to YAMLs validated by JSON Schema. Each YAML begins with a header:

```
schema: "jp.fraudsim.<domain>@<major>"
version: "<semver>"
released: "<YYYY‑MM‑DD>"
```

The loader maps the `<domain>` identifier to a local `schemas/<domain>.json`, checks the `major` matches, and raises `SchemaVersionError` if the YAML’s major exceeds the generator’s expectation. Numeric entries meant to be statistical estimators must include `mean, ci_lower, ci_upper`. After loading, `bootstrap_validator.py` draws one hundred truncated‑normal replicates from each triplet, re‑runs the generator on a 50 000‑row dry slice, and checks that synthetic histograms lie within the 90 % predictive envelope. If any bucket fails, the YAML gains a Git label “needs‑tune” and CI refuses merge.

Collision prevention is anchored in Postgres catalog **`datasets(id, parameter_hash, seed, path)`**. `register_dataset.py` inserts the triple and declares `parameter_hash, seed` unique. If an attempt is made to write a different `path` under the same `(parameter_hash, seed)`, Postgres throws `UNIQUE_VIOLATION`; the CLI surfaces the error as “parameter collision—increment YAML versions.” This rule guarantees that no two semantic parameter sets ever masquerade behind the same seed.

The **structural firewall** is coded in `firewall.py`. It streams generated records in batches of 50 000. Each batch undergoes five vectorised checks: (1) either `latitude` or `ip_latitude` is finite; (2) `tzid` belongs to the zoneinfo build `zoneinfo_version.yml`; (3) `event_time_utc + 60*local_time_offset` converts to the stated `tzid` via `zoneinfo.ZoneInfo`; (4) no illegal time stamps in DST gaps; (5) `fold` flag equals 0/1 only on repeated local hours. On first violation a reproducer file is written with the offending row and RNG offset; CI fails citing the reproducer path.

**Geospatial conformance** relies on conjugate beta bounds. `country_zone_alphas.yaml` yields for each `(country_iso, tzid)` the alpha vector. When generation ends `geo_audit.py` tallies outlets, forms beta posterior intervals at 95 %, and asserts synthetic share sits inside. If not, the script prints `(country, tzid, posterior_interval, observed_share)` and CI fails.

The **outlet‑count bootstrap** re‑inverts the hurdle coefficients. From `hurdle_coefficients.yaml` it reconstructs the logit and NB regressions; draws 10 000 bootstrap coefficient vectors; simulates chain‑size histograms; and overlays synthetic counts. If the synthetic count in any size bucket falls outside the bootstrap’s 95 % envelope, the histogram is saved as PNG, the YAML gains label “retune‑hurdle,” merge is blocked.

The **footfall model check** fits a Poisson GLM with spline basis to hourly counts versus `log_footfall`. Dispersion parameter θ must land in `[1,2]` for card‑present and `[2,4]` for CNP. If θ drifts outside, `footfall_coefficients.yaml` gets flagged.

For **multivariate indistinguishability** the harness samples 200 000 rows (split real vs. synthetic), embeds each into ℝ⁶ (sin/cos hour, sin/cos DOW, latitude, longitude) and trains XGBoost with fixed depth and learning rate. The XGBoost seed is the Philox counter after `bootstraps`, guaranteeing deterministic AUROC. If AUROC≥0.55, CI fails.

**DST edge passer** iterates every DST‑observing `tzid`. For each simulation year it builds a 48‑h schedule around both transitions, checks: no timestamps in gaps, all repeated minutes appear twice, offsets flip by exactly ±60 min. Failure produces a CSV `dst_failures.csv` and blocks merge.

All validation outputs—CSV, PNG, GLM tables—are written under `validation/{parameter_hash}/`. `upload_to_hashgate.py` posts the manifest, validation flag, and artefact URL to HashGate. Pull‑request lint rule `.github/workflows/block_merge.yml` polls HashGate; merge gates on `validation_passed=true`.

Licences must accompany artefacts. `artefact_registry.yaml` maps each artefact path to a licence path. CI job `validate_licences.py` verifies every artefact has a licence and that the licence text’s SHA‑1 is listed in `manifest.licence_digests`. Replacing an artefact without updating its licence digest stalls the pipeline.

Finally, dataset immutability: the dataset directory name embeds `parameter_hash`. NFS exports it read‑only. Any attempt to regenerate with the same hash but different contents throws `OSError: read‑only file system`, forcing version bump.

This chain—container hash, source SHA‑1, artefact registry, parameter‑set hash, master seed, Philox sub‑stream jumps, YAML schema gating, predictive‑envelope bootstraps, deterministic AUROC, DST edge scans, licence cross‑checks, HashGate attestation and read‑only export—constitutes an airtight provenance mesh. Every premise is visible, every mutation propagates into a digest diff, and every diff either triggers regeneration or blocks the merge, delivering the reproducibility and configurability demanded by JP Morgan’s harshest model‑risk reviewers.
