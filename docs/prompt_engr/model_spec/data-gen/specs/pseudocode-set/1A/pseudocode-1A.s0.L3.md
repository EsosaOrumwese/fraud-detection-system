# 0) Purpose — what L3 is (and isn’t)

## Purpose (what L3 **is**)

* A **read-only, idempotent validator** for **State-0** that proves the run is correct **from bytes on disk only**.
* It **recomputes** all deterministic lineage (`parameter_hash`, `manifest_fingerprint`) using L0 primitives, checks the **numeric gate** (S0.8) passed, and verifies **RNG is audit-only** for S0 (root key/counter match).
* It enforces **partition contracts** (embedded lineage equals path lineage), **schema authority**, and the **validation gate** (`_passed.flag` over ASCII-sorted bundle bytes; atomic publish).
* On the **first violation**, it emits **one** S0.9 failure record (class + code + typed detail) and stops. Re-running yields the **same** verdict (idempotent).

## Style (how L3 behaves)

* **No new logic**: L3 calls only **frozen L0 helpers** and reads artefacts emitted by L1/L2.
* **Deterministic comparisons**: byte-for-byte equality where required; otherwise exact integer math (e.g., 128-bit counters).
* **Fail-fast, fail-once**: a single authoritative failure record; no retries, no masking.

## Scope (what L3 covers for S0)

* Lineage re-derivation (𝓟 → `parameter_hash`; 𝓐 + `git32` + `param_b32` → `manifest_fingerprint`).
* Numeric attestation presence & **pass** status; confirms **numeric_policy.json** and **math_profile_manifest.json** are in the fingerprint artefact set.
* RNG **audit-only** invariant for S0 and master-material match to audit row (`philox2x64-10`).
* Partition lineage ≡ row lineage for parameter-scoped outputs (`crossborder_eligibility_flags`, optional `hurdle_pi_probs`).
* Validation bundle integrity (`_passed.flag` hash, atomic publish) and abort semantics (if present).

## Non-goals (what L3 **isn’t**)

* No sampler replays, no pseudorandom draws, no statistical checks.
* No re-implementation or reinterpretation of S0 business logic.
* No heuristics, fuzzy matching, or tolerance bands (other than what the spec already defines).
* No inference of config (e.g., **not** inferring `emit_hurdle_pi_cache` from dataset presence; the cache is treated as optional).
* No success markers may be written **inside** the fingerprint-scoped validation bundle; any success logging (if used) must be **outside** the bundle.

## Section DoD

* The validator description above is **consistent** with the frozen S0 spec and L0/L1/L2: it recomputes only deterministic artifacts, checks S0.8, asserts audit-only RNG for S0, enforces partition/gate rules, and emits at most **one** failure.
* No new artefacts, toggles, or algorithms are introduced here.
---

# 1) Inputs (closed set)

L3 validators read **bytes on disk** (no producer state) and only the artefacts S0 was allowed to touch. The set below is *closed*—no “helpful” extras.

**Lineage & artefact inputs**

* **Governed parameter bundle 𝓟**: the exact files enumerated (ASCII/unique basenames) for S0.2; used to recompute `parameter_hash`. L2’s host shim `list_parameter_files()` is the authority for this set.
* **Opened artefacts 𝓐 snapshot** (from S0.1, as consumed by S0.2): includes `numeric_policy.json`, `math_profile_manifest.json`, ISO set, GDP vintage, Jenks-5 buckets, schema/dictionary/registry anchors. L3 uses the bundle’s **fingerprint artefact list** (rows S0.2 emitted) to know *exactly* which basenames/paths to re-open and hash.
* **Git commit (hex, resolved)**: read `git_commit_hex` from `manifest_fingerprint_resolved.json` and **decode to raw 32 bytes** for fingerprint recomputation (never hash the hex string).
* **Resolved lineage files** written by S0.2:
  `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`, and the tabulations of parameter and artefact digests for cross-check.

**Numeric policy inputs**

* **numeric_policy_attest.json** produced by S0.8 (RNE, FMA-off, FTZ/DAZ-off, pinned libm profile result + self-tests). L3 verifies presence + fields and that these files were in 𝓐 before S0.2 (via the artefact list).

**RNG logs (S0 emits audit only)**

* **RNG audit log** under `{seed, parameter_hash, run_id}` with master key/counter & metadata. L3 asserts it exists and precedes *any* events. (S0 emits **no** RNG events; L3 also confirms absence of event files for S0.)
* **RNG trace log** *(not used in S0)*: if present for later states under the run-id scope, reconcile `blocks_total` with any envelope rows. For S0, trace files are not expected.

**Parameter-scoped outputs from S0**

* **`crossborder_eligibility_flags`** (required): rows embed the exact `parameter_hash` equal to the partition key.
* **`hurdle_pi_probs`** (optional, only if `emit_hurdle_pi_cache=true`): same parameter-scoped partition/embedding rules.

**Validation bundle (fingerprint-scoped)**

* The full bundle under `fingerprint={manifest_fingerprint}` containing: lineage `_resolved` files, artefact/parameter digest tables, `numeric_policy_attest.json`, RNG audit/trace copies (if mirrored there), and **`_passed.flag`** whose hash covers the ASCII-sorted bytes of all other bundle files.

**Host-provided byte shims (read-only)**

* L3 may reuse the L2 read-only shims to fetch bytes/paths *without* adding logic:
  `list_parameter_files`, `read_bytes` (to re-open artefacts). (The git-hex→raw32 step is provided here as a **local adapter**; see Appendix `read_git32_from_resolved`.)

**Explicit non-inputs (to prevent drift)**

* No late-opened governance files (anything not in 𝓐 at S0.2) and no environment/config knobs beyond what S0 already recorded. L3 must *not* introduce new reads that would mutate 𝓐.

---

L3 produces **no new business artefacts**. Its job is to verify, from bytes, that S0’s outputs obey the spec. On success, it produces **no files**; on failure, it emits **exactly one** failure record (mandatory on first violation).

## Failure (authoritative, exactly one)

When any check fails, L3 must emit **one** S0.9 failure record under the run’s lineage scope and stop:

* **Failure record** (JSON) placed under `{fingerprint, seed, run_id}` per S0.9, with:

  * `failure_class` ∈ {F1…F10},
  * a precise `failure_code` (e.g., `lineage_mismatch`, `numeric_attest_fail`, `rng_audit_missing`, `partition_mismatch`, `gate_hash_mismatch`, `non_atomic_publish`),
  * typed `detail` payload (expected vs observed digests, paths, counters).
    Any subsequent S0.10 publish must **not** exist for an aborted run. Violations are atomicity errors.

## Scope & partitions L3 validates (no new writes)

L3 **verifies** the following persisted outputs; it does **not** create them:

* **RNG audit (S0)** — exactly one audit row; **no RNG events** for S0. Path is `logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`; partition keys `{seed, parameter_hash, run_id}`. L3 recomputes master key/counter and matches them (bit-for-bit), and asserts audit-only invariant.
* **Parameter-scoped datasets**

  * `crossborder_eligibility_flags` (**required**) and `hurdle_pi_probs` (**optional** if configured): each row **embeds `parameter_hash` equal to the path key**. L3 will fail on any mismatch.
* **Validation bundle (fingerprint-scoped)** — directory `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/` containing `MANIFEST.json`, the two `*_resolved.json`, `param_digest_log.jsonl`, `fingerprint_artifacts.jsonl`, `numeric_policy_attest.json`, optional lints, and **`_passed.flag`**. L3 verifies the file set and recomputes the gate hash over ASCII-sorted file bytes (excluding the flag) and checks the publish was **atomic**.

## Explicit non-outputs

* L3 must not emit RNG events, modify parameter-scoped datasets, or change the validation bundle.
* Success is signalled by process status (and/or an external validator log outside the bundle).
* On failure, write exactly one failure record using the S0.9 taxonomy in the failure path.
* Never add or modify files inside the validation bundle and never re-write `_passed.flag`.

This matches your L0/L1/L2 contracts: bundle contents and `_passed.flag` rules (S0.10), partition scopes (S0.10.3), audit-only RNG in S0 (S0.3/L2), and the S0.9 failure taxonomy and placement.

---

# 3) Execution order (validator run plan)

**V1 — Lineage recompute first.**
Recompute `parameter_hash` from the governed parameter set using the tuple-hash (ASCII‐sorted basenames; name included in the tuple), and compare to `parameter_hash_resolved.json`. Then recompute `manifest_fingerprint` from the **opened artefacts set** + `git32` + `parameter_hash_bytes`, and compare to `manifest_fingerprint_resolved.json`. Any mismatch ⇒ fail (F2).

**V2 — Numeric attestation must be valid.**
Read `numeric_policy_attest.json` from the bundle and require: RNE rounding, FMA-off, FTZ/DAZ-off, pinned libm profile (incl. `lgamma`), and self-tests = “pass”. If absent or failing ⇒ fail (F7).

**V3 — RNG audit presence, and *only* audit in S0.**
* Check the RNG audit JSONL exists under {seed, parameter_hash, run_id} and that each row embeds
* exactly the recomputed {seed, parameter_hash, manifest_fingerprint, run_id}. Assert zero RNG events
* exist for S0 (no envelopes with {before,after,blocks,draws}); counters therefore never advance.

If any event exists ⇒ fail (**F4a**). 

**V4 — Partition scope & embedding.**
For each parameter-scoped dataset produced in S0 (e.g., `crossborder_eligibility_flags`, optional `hurdle_pi_probs`), verify the path key `parameter_hash=…` equals the **embedded** `parameter_hash` in every row. RNG audit rows must embed `{seed, parameter_hash, run_id}`; the validation bundle must be under `fingerprint={manifest_fingerprint}` and embed that fingerprint. Any mismatch ⇒ fail (F5/F10).

**V5 — Validation gate & atomic publish.**
Recompute `_passed.flag`: list bundle files in **bytewise ASCII** order, concatenate the raw bytes of **all except** `_passed.flag`, SHA-256 the concatenation; flag content must match. Also ensure publish was atomic (no temp files visible in final path). Otherwise ⇒ fail (F10).

**V6 — Final verdict.**
If V1–V5 pass, emit success (**no new files**). On first failure, write one S0.9 failure record (typed class/code) and stop (idempotent).

> Rationale for this order: lineage proves we’re validating the right bytes; numeric policy gates determinism **before** any RNG stage; S0 is **audit-only** for RNG; partition rules are enforced per dictionary; and the bundle is accepted only via the hash gate + atomic publish contract. 

---

# 4) Validator routines (pseudocode)

Here’s **Section 4 — Validator routines**, written as **code-agnostic pseudocode** that only uses frozen L0 helpers and read-only host shims. Each routine is **pure**, idempotent, and maps failures to the S0.9 taxonomy. No new algorithms, no replays, no guessing.

> Host shims L3 can use (bytes/paths only):
> `host.read_bytes(path)->bytes`, `host.read_json(path)->obj`, `host.list_files(dir)->[path]`, `host.glob(pattern)->[path]`.
> (These do **not** implement hashing, RNG, or partition policy; they just fetch bytes and paths.)

---

## V1. `recompute_lineage_and_compare() -> ok | abort(F2, code, detail)`

**Inputs:** governed parameter files 𝓟; bundle files:

* `parameter_hash_resolved.json`, `param_digest_log.jsonl`
* `manifest_fingerprint_resolved.json`, `fingerprint_artifacts.jsonl`
* `git_commit_hex` (from `manifest_fingerprint_resolved.json`), **decoded to raw 32 bytes** for recomputation

**Uses L0:** `all_ascii_unique_basenames`, `sha256_stream`, `UER/LE64`, `compute_parameter_hash`, `compute_manifest_fingerprint`.

```text
function V1_recompute_lineage_and_compare(bundle_dir, parameters_root):
  # 1) Recompute parameter_hash from governed parameter bundle 𝓟
  P_files = host.list_parameter_files(parameters_root)                  # same enumeration rules as S0.2 (host shim)
  if not all_ascii_unique_basenames(P_files): 
      return abort_run(F2, "basenames_invalid_or_duplicate", {where:"parameters"})

  (param_hash_hex, param_hash_bytes, param_log_rows) =
      compute_parameter_hash(P_files)                             # tuple-hash, ASCII basename sort

  # Compare to bundle
  ph_resolved = host.read_json(bundle_dir + "/parameter_hash_resolved.json")
  if ph_resolved.parameter_hash != param_hash_hex:
      return abort_run(F2, "parameter_hash_mismatch",
                       {expected:param_hash_hex, found:ph_resolved.parameter_hash})

  # 2) Recompute manifest_fingerprint from artifacts set 𝓐 + git32 + param_b32
  fa_rows       = read_artifact_list(bundle_dir + "/fingerprint_artifacts.jsonl") # names + hashes that S0.2 used
  arts = materialize_artifacts_bytes(fa_rows)                      # open exactly those basenames/paths
  if not all_ascii_unique_basenames(arts):
      return abort_run(F2, "basenames_invalid_or_duplicate", {where:"artifacts"})

  # Source the git commit **hex** from the resolved file, and decode to raw 32 bytes
  mf_resolved = host.read_json(bundle_dir + "/manifest_fingerprint_resolved.json")
  git32 = hex64_to_raw32(mf_resolved.git_commit_hex)

  (fp_hex, fp_bytes, fp_resolved, fa_rows_recomputed) =
      compute_manifest_fingerprint(arts, git32, param_hash_bytes)
      
  if mf_resolved.manifest_fingerprint != fp_hex:
      return abort_run(F2, "manifest_fingerprint_mismatch",
                       {expected:fp_hex, found:mf_resolved.manifest_fingerprint})

  return ok, { fp_bytes: fp_bytes }
```

**Notes:**

* `discover_parameter_files` and `materialize_artifacts_bytes` are thin wrappers around `host.list_files`/`host.read_bytes`, honoring the exact basenames S0.2 recorded.
* No new files are added to 𝓐; we only re-open what S0.2 enumerated.

---

## V2. `verify_numeric_attestation() -> ok | abort(F7/F2, code, detail)`

**Inputs:** `numeric_policy_attest.json` from the bundle; the **𝓐 artefact list** (must include `numeric_policy.json` and `math_profile_manifest.json`).

```text
function V2_verify_numeric_attestation(bundle_dir, artifact_list_rows):
  attest = host.read_json(bundle_dir + "/numeric_policy_attest.json")  # must exist

  # Require pass verdicts for all pinned checks
  req = ["rounding_RNE", "FMA_off", "FTZ_DAZ_off", "libm_profile_ok",
         "neumaier_sum_ok", "total_order_ok", "libm_regression_ok"]
  for k in req:
      if attest[k] != "pass":
          return abort_run(F7, "numeric_attest_fail", {check:k, value:attest[k]})

  # Confirm both numeric artefacts were part of 𝓐 that formed the fingerprint
  if not artifact_list_contains(artifact_list_rows, "numeric_policy.json"):
      return abort_run(F2, "fingerprint_inputs_incomplete", {missing:"numeric_policy.json"})
  if not artifact_list_contains(artifact_list_rows, "math_profile_manifest.json"):
      return abort_run(F2, "fingerprint_inputs_incomplete", {missing:"math_profile_manifest.json"})

  return ok
```

---

## V3. `check_rng_audit_invariant() -> ok | abort(F4a, code, detail)`

**Inputs:** lineage `{seed, parameter_hash, run_id}`, `manifest_fingerprint_bytes` (from V1), RNG logs directory.

**Uses L0:** `derive_master_material(seed, manifest_fingerprint_bytes)`.

```text
function V3_check_rng_audit_invariant(log_root, seed, parameter_hash, run_id, manifest_fingerprint_bytes):
  lineage_path = log_root + "/logs/rng/audit/seed=" + seed +
                 "/parameter_hash=" + parameter_hash + "/run_id=" + run_id + "/"
  audit_files = host.list_files(lineage_path)
  if count_jsonl(audit_files) != 1:
      return abort_run(F4a, "rng_audit_missing_or_multiple", {path:lineage_path, count:count_jsonl(audit_files)})
  if count_lines(audit_files[0]) != 1:
      return abort_run(F4a, "rng_audit_row_count", {path:audit_files[0], count:count_lines(audit_files[0])})

  # S0 must be audit-only: assert absence of RNG event envelopes for this lineage
  events_glob = log_root + "/logs/rng/events/*/seed=" + seed +
                "/parameter_hash=" + parameter_hash + "/run_id=" + run_id + "/part-*.jsonl"
  if host.glob(events_glob) is not empty:
      return abort_run(F4a, "rng_events_present_in_S0", {path_glob:events_glob})

  # Recompute root key/counter and compare to the audit row fields
  (M, root_key, root_ctr) = derive_master_material(seed, manifest_fingerprint_bytes)
  audit_row = read_single_jsonl(audit_files[0])         # guaranteed 1 file, 1 row
  if audit_row.algorithm != "philox2x64-10":
      return abort_run(F4a, "rng_algorithm_mismatch", {expected:"philox2x64-10", found:audit_row.algorithm})
                        
  # If the schema variant exposes key/counter, enforce exact match with L0 names
  if ("rng_key_lo" in audit_row) or ("rng_key_hi" in audit_row):
      if (audit_row.rng_key_hi != 0) or (audit_row.rng_key_lo != root_key):
          return abort_run(F4a, "audit_root_key_mismatch",
                           {expected_lo:root_key, expected_hi:0,
                            found_lo:audit_row.rng_key_lo, found_hi:audit_row.rng_key_hi})
  if ("rng_counter_hi" in audit_row) or ("rng_counter_lo" in audit_row):
      if (audit_row.rng_counter_hi != root_ctr.hi) or (audit_row.rng_counter_lo != root_ctr.lo):
          return abort_run(F4a, "audit_root_counter_mismatch",
                           {expected_hi:root_ctr.hi, expected_lo:root_ctr.lo,
                            found_hi:audit_row.rng_counter_hi, found_lo:audit_row.rng_counter_lo})

  # Embedded lineage must equal the path lineage
  if audit_row.seed != seed or audit_row.parameter_hash != parameter_hash or audit_row.run_id != run_id:
      return abort_run(F4a, "rng_audit_lineage_embed_mismatch",
                       {path:{seed,parameter_hash,run_id}, embedded:{audit_row.seed,audit_row.parameter_hash,audit_row.run_id}})

  return ok
```

---

## V4. `lint_partitions_and_schema() -> ok | abort(F5/F6, code, detail)`

**Inputs:** dataset dictionary/registry anchors (already part of 𝓐), parameter-scoped datasets (if present).

**Uses L0:** `verify_partition_keys(dataset_id, path_keys, embedded_row)`.

```text
function V4_lint_partitions_and_schema(dictionary, registry, parameter_hash, data_root):
  # 1) Parameter-scoped datasets (presence rules)
  flags_paths = host.glob(data_root + "/crossborder_eligibility_flags/parameter_hash=" + parameter_hash + "/*.parquet")
  if flags_paths is empty:
      return abort_run(F5, "missing_required_dataset", {dataset:"crossborder_eligibility_flags"})

  for file in flags_paths:
      for row in read_rows(file):
          if not verify_partition_keys("crossborder_eligibility_flags",
                                       {parameter_hash:parameter_hash}, row):
              return abort_run(F5, "partition_lineage_mismatch",
                               {dataset:"crossborder_eligibility_flags", file:file, row_id:row.id})

  # Optional diagnostic cache
  cache_paths = host.glob(data_root + "/hurdle_pi_probs/parameter_hash=" + parameter_hash + "/*.parquet")
  for file in cache_paths:
      for row in read_rows(file):
          if not verify_partition_keys("hurdle_pi_probs",
                                       {parameter_hash:parameter_hash}, row):
              return abort_run(F5, "partition_lineage_mismatch",
                               {dataset:"hurdle_pi_probs", file:file, row_id:row.id})

  # 2) Schema authority lint — ensure JSON-Schema anchors (no Avro in 1A)
  anchors = extract_json_schema_anchors_from(registry)    # registry is part of 𝓐; pure lookup
  for ds in ["crossborder_eligibility_flags", "hurdle_pi_probs"]:
      if dataset_exists(ds, data_root):
          ref = dictionary.schema_ref(ds)
          if not ref in anchors:
              return abort_run(F6, "schema_reference_not_json_schema",
                               {dataset:ds, schema_ref:ref})

  return ok
```

*Implementation notes:*

* `read_rows` is a schematic reader (can be a row iterator); L3 just inspects embedded lineage fields.
* `dataset_exists` is a convenience over `host.glob`.
* No content math is performed—only lineage equality and schema anchor checks.

---

## V5. `verify_gate_hash_and_publish() -> ok | abort(F10, code, detail)`

**Inputs:** validation bundle directory at `fingerprint={manifest_fingerprint}`.

**Uses L0:** `_passed.flag` hashing rules (ASCII-sorted file names; concatenated raw bytes; SHA-256).

```text
function V5_verify_gate_hash_and_publish(bundle_dir):
  files = host.list_files(bundle_dir)
  if "_passed.flag" not in files:
      return abort_run(F10, "passed_flag_missing", {dir:bundle_dir})

  # 1) Recompute the gate hash exactly as specified
  others = L0.sort_ascii([f for f in files if f != "_passed.flag"])
  H = new_SHA256()
  for f in others:
      H.update( host.read_bytes(bundle_dir + "/" + f) )           # raw bytes, no transcoding
  expected_hex = hex64( H.finalize() )

  flag_text = host.read_bytes(bundle_dir + "/_passed.flag").decode_ascii_strict()
  if L0.extract_hash(flag_text) != expected_hex:
      return abort_run(F10, "gate_hash_mismatch",
                       {expected:expected_hex, found:L0.extract_hash(flag_text)})

  # 2) Atomic publish via manifest: no extras beyond MANIFEST.json and _passed.flag
  manifest = host.read_json(join(bundle_dir, "MANIFEST.json"))
  expected = set(manifest.files)
  expected.add("_passed.flag")
  if set(files) != expected:
      return abort_run(F10, "bundle_contains_unexpected_files", {expected:expected, found:set(files)})
return ok
```

*Notes:*

* `extract_hash` parses the flag’s canonical format to the hex digest; exact format is fixed by L0/L1.
* Atomicity is verified by absence of temp-like names (`_tmp`, partials). Full provenance of rename cannot be proven post hoc—this is the enforceable invariant.

---

## V6. `check_abort_semantics() -> ok | abort(F9/F10, code, detail)`

**Inputs:** presence of a failure record and sentinels; absence of a published bundle after abort.

```text
function V6_check_abort_semantics(root, fingerprint, seed, parameter_hash, run_id):
  fail_dir = root + "/fingerprint=" + fingerprint + "/seed=" + seed + 
             "/run_id=" + run_id + "/"
  failure_files = host.glob(fail_dir + "/failure.json")
  sentinel_files = host.glob(fail_dir + "/_FAILED.SENTINEL.json")

  if failure_files not empty:
      # A failure implies: sentinel present, and no successful bundle publish afterwards
      if sentinel_files is empty:
          return abort_run(F10, "missing_failed_sentinel", {fail_dir:fail_dir})

      bundle_dir = root + "/fingerprint=" + fingerprint + "/"
      # Success bundle must not coexist with a failure for the same lineage instance
      # instance_matches expects {parameter_hash, fingerprint}
      if bundle_contains_success_marker(bundle_dir) and instance_matches(bundle_dir, {parameter_hash:parameter_hash, fingerprint:fingerprint}):
          return abort_run(F9, "bundle_published_after_abort",
                           {bundle:bundle_dir, fail_dir:fail_dir})

      # Validate failure payload shape (class, code, detail present)
      payload = host.read_json(failure_files[0])
      if not valid_failure_shape(payload):
          return abort_run(F9, "invalid_failure_payload", {file:failure_files[0]})

  return ok
```

*Notes:*

* L3 does **not** create or modify failure records; it only verifies placement and mutual exclusivity with a success bundle.

---

### Definition of Done for §4

* Each routine **only** calls L0 primitives and host **byte shims**; no new algorithms or tolerances.
* Each failure path maps to a **single** S0.9 `abort_run(F*, code, detail)` invocation and then stops.
* Success produces **no** new business artefacts.
* Re-running yields identical outcomes (idempotent).

---

# 5) L3 Orchestrator (wire-up, no surprises)

Below is the **single** entrypoint that runs all validators in the only allowed order. It is **read-only**, idempotent, and terminates on the **first** failure (one S0.9 record). It uses only frozen L0 helpers and the host byte/FS shims you already defined.

```text
# Orchestrator for State-0 validation (L3)
#
# Inputs (closed):
#   validation_root: absolute dir that contains fingerprint-scoped bundles
#   data_root:       absolute dir that contains parameter-scoped datasets (e.g., crossborder_eligibility_flags, hurdle_pi_probs)
#   log_root:        absolute dir that contains RNG logs (audit path)
#   seed:            u64 (decimal string or native u64, must match path key format used in logs)
#   parameter_hash:  hex64 (path key)
#   manifest_fingerprint: hex64 (path key and bundle directory name)
#   run_id:          hex32 (path key)
#
# Side effects:
#   - On failure:   write exactly one S0.9 failure record under {fingerprint, seed, run_id} and stop.
#
# Non-goals:
#   - Never alters business datasets or logs.
#   - Never emits RNG events or draws.
#   - Never adds to artefact set 𝓐; only re-opens what S0 already recorded.
#   - Never writes success markers inside the fingerprint-scoped validation bundle.

function validate_S0(validation_root, data_root, log_root, parameters_root,
                     seed:u64, parameter_hash:hex64,
                     manifest_fingerprint:hex64, run_id:hex32):

  # Derive canonical bundle path (fingerprint-scoped)
  bundle_dir = join(validation_root, "fingerprint=" + manifest_fingerprint)

  # ---------------------------
  # V1 — Lineage recomputation
  # ---------------------------
  # Recompute parameter_hash and manifest_fingerprint from bytes and compare to *_resolved.json
  ok1, v1 = V1_recompute_lineage_and_compare(bundle_dir, parameters_root)
  if ok1 != ok: return fail_once_and_stop()   # V1 already called abort_run(F2, ...)

  # Load artefact list rows once; many checks reuse it
  artifact_list_path = join(bundle_dir, "fingerprint_artifacts.jsonl")
  artifact_rows = read_artifact_list(artifact_list_path)      # rows S0.2 emitted (names+digests)

  # Get fingerprint bytes for RNG master-material recomputation
  mf_resolved = host.read_json(join(bundle_dir, "manifest_fingerprint_resolved.json"))
  mf_hex = mf_resolved.manifest_fingerprint
  mf_bytes = v1.fp_bytes                           # L0 helper; exact 32-byte array

  # --------------------------------
  # V2 — Numeric attestation (gate)
  # --------------------------------
  ok2 = V2_verify_numeric_attestation(bundle_dir, artifact_rows)
  if ok2 != ok: return fail_once_and_stop()                   # abort_run(F7/F2, ...) already done

  # ---------------------------------------------
  # V3 — RNG audit-only invariant for S0 (no evts)
  # ---------------------------------------------
  ok3 = V3_check_rng_audit_invariant(log_root, as_dec(seed), parameter_hash, run_id, mf_bytes)
  if ok3 != ok: return fail_once_and_stop()                   # abort_run(F4a, ...) already done

  # -----------------------------------------
  # V4 — Partition lineage & schema authority
  # -----------------------------------------
  (dictionary, registry) = load_dictionary_and_registry_from_artifacts(artifact_rows)
  ok4 = V4_lint_partitions_and_schema(dictionary, registry, parameter_hash, data_root)
  if ok4 != ok: return fail_once_and_stop()                   # abort_run(F5/F6, ...) already done

  # ----------------------------------------
  # V5 — Gate hash & atomic publish contract
  # ----------------------------------------
  ok5 = V5_verify_gate_hash_and_publish(bundle_dir)
  if ok5 != ok: return fail_once_and_stop()                   # abort_run(F10, ...) already done

  # ---------------------------------------
  # V6 — Abort semantics (mutual exclusivity)
  # ---------------------------------------
  ok6 = V6_check_abort_semantics(validation_root, manifest_fingerprint, as_dec(seed), parameter_hash, run_id)
  if ok6 != ok: return fail_once_and_stop()                   # abort_run(F9/F10, ...) already done

  return { verdict: "pass" }
```

## Notes to implementers (to keep this 100% green)

* **Order is hard**: V1 → V2 → V3 → V4 → V5 → V6. Do not parallelize or reorder.
* **No new artefacts**: All reads come from the bundle, datasets, and logs already written by S0.
* **Idempotent**: If any `V*` calls `abort_run(F*, code, detail)`, the orchestrator returns immediately; a second run yields the same failure record.
* **Paths**:

  * Bundle is **fingerprint-scoped** at `validation_root/fingerprint={manifest_fingerprint}`.
  * RNG audit is under `logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/`.
  * Parameter-scoped datasets under `{dataset}/parameter_hash={parameter_hash}/...`.
* **Types**: treat `seed` as a u64 for RNG recomputation but as a string for path interpolation; treat `manifest_fingerprint`/`parameter_hash` as fixed-length hex strings.
* **Optional cache**: `hurdle_pi_probs` is optional—V4 lints it if present; absence is not an error.

## Minimal host shims used by the orchestrator (read-only)

* `host.read_json(path)`, `host.read_bytes(path)`
* `host.list_files(dir)`, `host.glob(pattern)`
* `host.list_parameter_files(root)`  ← (enumerate governed parameter bundle 𝓟; same contract as L2 H1)

These shims only fetch bytes/paths. All hashing, hex/bytes conversions, and policy checks are performed via **frozen L0** and the **V1–V6** routines you already accepted.

---

# 6) Host shims L3 may use (read-only, bytes only)

L3 is **read-only**. It uses a **small subset** of the host shims already defined for L2 (same contracts—no new logic). These shims fetch bytes/paths only; all hashing, hex/bytes rules, and policy checks are done with **frozen L0** + the L3 routines.

> Rule of thumb: shims **never normalize** or reinterpret content. They return raw bytes/objects and let L0/L3 do the exact work.

## H-L3.0 `list_parameter_files(root: string) -> list[(basename_ascii: string, abs_path: string)]`

**Purpose.** Enumerate the governed parameter bundle 𝓟 for V1 recomputation of `parameter_hash`.

**Contract.**
* Return every governed parameter file **exactly once**.
* Each `basename_ascii` must be **ASCII** and **unique** across the list.
* Paths must be absolute and readable.

**Determinism.** Order is irrelevant (L0 hashes after **ASCII basename** sort). Contents must be stable for the run.

**Failure mapping.** IO/missing → `F2:param_files_io`; non-ASCII/duplicate basenames → `F2:basenames_invalid_or_duplicate`.

**Used by.** V1 `compute_parameter_hash(...)`.

---

## H-L3.1 `read_bytes(path: string) -> bytes`

**Purpose.** Load the exact file bytes for hashing/flag recomputation and JSONL parsing.

**Contract.**

* Returns the raw file content; **no** newline translation, decoding, or BOM stripping.
* Binary-safe; may be used on any artefact (bundle file, dataset shard, audit JSONL).

**Determinism.** Same bytes for repeated reads within the run.

**Failure mapping.**
If the file is required by the bundle/contracts and can’t be opened → `abort_run(F2, "artifact_open_failed", {path})` (V1/V5 callers choose precise code).

**Used by.** V1 (artefacts & parameters), V5 (`_passed.flag` hash), any JSONL reads.

---

## H-L3.2 `read_json(path: string) -> object`

**Purpose.** Load small JSON control files emitted by S0 (e.g., `*_resolved.json`, `numeric_policy_attest.json`, single-row audit JSON).

**Contract.**

* Strict JSON parse; **no** key renaming or type coercion beyond JSON.
* Must reject trailing data and non-UTF-8.

**Determinism.** Parsing the same bytes yields the same object.

**Failure mapping.**
Missing/unparseable required JSON → `abort_run(F10, "bundle_corrupt", {path})` if inside the fingerprint bundle; otherwise `F2` for non-bundle control files (call-site decides).

**Used by.** V1, V2, V3, V5, V6.

---

## H-L3.3 `list_files(dir: string) -> [basename: string]`

**Purpose.** Enumerate immediate children of a directory (e.g., bundle contents).

**Contract.**

* Returns **basenames** only; order is **unspecified** (callers must ASCII-sort when required).
* Excludes `.` and `..`; hidden files are returned if present.

**Determinism.** Same set for repeated calls within the run.

**Failure mapping.**
Directory missing where mandated by spec → `abort_run(F10, "bundle_missing", {dir})` for the fingerprint bundle; `F5` for required datasets (V4).

**Used by.** V5 (bundle file set), V3 (audit lineage directory).

---

## H-L3.4 `glob(pattern: string) -> [path: string]`

**Purpose.** Resolve dataset partitions and lineage-scoped log paths.

**Contract.**

* Supports the partition shapes used by S0 (e.g., `…/dataset/parameter_hash=<hex>/*.parquet`).
* Returns full paths; order unspecified.

**Determinism.** Same set for repeated calls with stable FS.

**Failure mapping.**
Required dataset not found → `abort_run(F5, "missing_required_dataset", {dataset, pattern})`.

**Used by.** V3 (event absence check), V4 (datasets), V6 (failure record/sentinel presence).

---

## H-L3.5 `read_lines(path: string) -> iterator<byte[]>` *(optional convenience)*

**Purpose.** Stream JSONL rows without loading whole files.

**Contract.**

* Yields raw **line bytes** exactly as stored (no decoding/strip).
* Caller is responsible for per-line JSON parse (using L3’s strict JSON decoder).

**Determinism.** Byte-stable.

**Failure mapping.**
As `read_bytes` (caller maps to `F2`/`F10` appropriately).

**Used by.** V3 (audit JSONL), V1 (artefact/parameter logs if JSONL).

---

## H-L3.6 `exists(path: string) -> bool`

**Purpose.** Cheap existence check (bundle markers, temp files).

**Contract.**

* Returns true if the path exists and is accessible.

**Determinism.** Stable within the validator run.

**Failure mapping.**
Not a failing shim by itself; callers decide (e.g., temp files in bundle → `F10 non_atomic_publish_detected`).

**Used by.** V5 (atomicity heuristics), V6 (mutual exclusivity checks).

---

### Non-shims (explicitly **not** part of host)

* Hashing, hex/bytes conversions, tuple-hash rules, `_passed.flag` recomputation, RNG master material, Neumaier/total-order checks, partition verification, and the S0.9 `abort_run(...)` **all come from L0/L3**, not from host utilities.

### DoD for §6

* Only 6 read-only shims are listed; they **match** what L3 actually calls.
* Each shim states **purpose, contract, determinism, failure mapping, and usage**.
* No duplication of L0/L1 logic, no “smart” parsing, no normalization.
* Implementers can provide these trivially on any FS; L3 remains portable and deterministic.

---

# 7) Definition of Done (DoD) for L3

This section is the acceptance contract. If **all** checks pass exactly as written, L3 is green to freeze.

## 7.1 Functional completeness

* Implements **V1…V6** exactly (no extra routines):
  V1 lineage, V2 numeric attestation, V3 RNG audit-only, V4 partitions & schema, V5 gate & atomic publish, V6 abort semantics.
* Orchestrator runs **strictly in order**: V1 → V2 → V3 → V4 → V5 → V6; stops on first failure.

## 7.2 Inputs/outputs (closed set)

* Reads only: bundle (fingerprint-scoped), parameter-scoped datasets, RNG audit path, governed parameters, artefact list, git32, attestation.
* **No new artefacts are written inside the bundle.** Success is signalled by process status and/or an external validator log outside the bundle.

## 7.3 Determinism & purity

* Uses **frozen L0** for: tuple-hash, fingerprint, hex/bytes, `_passed.flag` hashing, RNG master-material, partition-key verification.
* Host shims are **read-only** (those listed in §6, incl. the optional `read_lines`); no normalization, no hidden state.
* Re-running L3 yields identical results and (on failure) the **same** single failure record.

## 7.4 Failure policy (S0.9)

* On first violation, calls `abort_run(F*, failure_code, detail)` and **returns immediately**.
* Exactly **one** failure record is produced, under `{fingerprint, seed, run_id}` (path). The JSON payload still carries `{parameter_hash}`.
* Failure classes map as:

  * **F2** lineage/fingerprint/artefact-set errors, missing governed inputs.
  * **F7** numeric attestation absent/failing.
  * **F4a** RNG audit invariant broken (missing/multiple audit; wrong algo/key/counter; any S0 event present).
  * **F5** partition lineage ≠ embedded lineage; required dataset missing.
  * **F6** schema authority mismatch (non–JSON-Schema anchors where required).
  * **F10** `_passed.flag` mismatch; non-atomic publish; corrupt bundle.
  * **F9/F10** abort semantics violations (bundle published after abort; missing sentinels).

## 7.5 Lineage & artefacts

* V1 recomputes:

  * `parameter_hash` from 𝓟 with ASCII/unique basenames; equals `parameter_hash_resolved.json`.
  * `manifest_fingerprint` from artefact list 𝓐 + `git32` + `param_b32`; equals `manifest_fingerprint_resolved.json`.
* 𝓐 **includes** `numeric_policy.json` and `math_profile_manifest.json`. Missing either → **F2**.

## 7.6 Numeric policy gate

* `numeric_policy_attest.json` exists and is **pass** for: RNE, FMA-off, FTZ/DAZ-off, pinned libm profile, Neumaier, total-order, libm regression.
* Artefacts referenced by the attestation are present in 𝓐 (proved in 7.5).

## 7.7 RNG (S0 is audit-only)

* Exactly **one** audit JSONL exists at the lineage path; **zero** RNG event envelopes exist for S0.
* Recomputed `(root_key, root_ctr)` from `(seed, manifest_fingerprint_bytes)` matches the audit row **bit-for-bit**; algorithm equals `philox2x64-10`.

## 7.8 Partitions & schema authority

* `crossborder_eligibility_flags` **exists** under `parameter_hash=…` and every row embeds the *same* `parameter_hash`.
* `hurdle_pi_probs` is **optional**; if present, same embedding rule.
* For any dataset present, schema refs resolve to the registry’s **JSON-Schema** anchors (no Avro in 1A).

## 7.9 Validation gate & atomic publish

* Recomputed `_passed.flag` = SHA-256 over **ASCII-sorted** bundle file bytes (excluding the flag) **matches** the flag content.
* Final publish is **atomic** (no `_tmp`/partial files in the finalized bundle dir).

## 7.10 Abort semantics (if applicable)

* If a failure record exists, it is placed **exactly** under `{fingerprint, seed, run_id}` with valid shape. The record body includes `{parameter_hash}`.
* A success bundle **must not** co-exist for the same lineage instance; otherwise fail (**F9/F10**).

## 7.11 Negative/edge tests (must fail correctly)

* Wrong `parameter_hash` or `manifest_fingerprint` → **F2**.
* Attestation missing or any check ≠ “pass” → **F7**.
* Any RNG event present for S0; or audit key/counter mismatch → **F4a**.
* Missing `crossborder_eligibility_flags` or lineage mismatch in rows → **F5**.
* `_passed.flag` digest mismatch or temp files visible → **F10**.
* Non-JSON-Schema ref for a dataset → **F6**.

## 7.12 Success criteria

* With a valid S0 run, L3 completes V1…V6 **without emitting a failure record**.
* A second run over the same bytes yields identical success.

This DoD makes “green” objective: every check is mechanical, byte-backed, and mapped to a single failure class.

---

# 8) Pitfalls L3 explicitly forbids

To keep L3 deterministic, spec-true, and guess-free, **do not** do any of the following:

## Inputs & artefacts

* **Late-opening governance**: don’t read any artefact that wasn’t in the S0.2 artefact list 𝓐. L3 must only re-open what S0 fingerprinted.
* **Expanding the parameter set**: don’t discover extra governed files beyond the logged parameter list; don’t ignore basename ASCII/uniqueness rules.
* **Using hex commit text**: always **decode** `git_commit_hex` to the **raw 32 bytes**; never hash the hex string itself.

## RNG & numeric policy

* **Any RNG replay**: don’t simulate samplers or “check randomness.” S0 is audit-only; validate the audit row and invariants only.
* **Treating counters/draws as floats**: all counter math is **unsigned 128-bit**; zero float leakage.
* **Skipping numeric attestation**: do not proceed if `numeric_policy_attest.json` is missing or not “pass”.

## File I/O & parsing

* **Normalizing bytes**: never transcode/trim/normalize line endings, BOMs, or whitespace before hashing; `_passed.flag` uses **raw bytes**.
* **Lenient JSON**: no comments, trailing commas, or non-UTF-8; reject on parse error.
* **Assuming order from the FS**: directory listings are unsorted; when required (e.g., gate), **ASCII-sort** explicitly.

## Partitions & schemas

* **Inferring config from presence**: treat `hurdle_pi_probs` as optional; if present, lint; if absent, OK. Do not infer `emit_hurdle_pi_cache`.
* **Partition drift**: never accept rows whose embedded lineage doesn’t equal the path lineage.
* **Authority drift**: don’t accept non–JSON-Schema refs for 1A datasets.

## Gate & publish

* **Wrong gate procedure**: don’t hash names; hash the **concatenated bytes** of all bundle files **except** `_passed.flag`, with ASCII filename ordering.
* **Post-hoc mutation**: never modify bundle contents after publish; L3 only *verifies* the existing `_passed.flag`.
* **Non-atomic publish tolerance**: don’t ignore `_tmp`/partial files in the final bundle; that’s a failure.

## Control flow & failures

* **Multiple failures**: emit **one** S0.9 failure record and stop. No cascades, no retries.
* **Reinterpreting classes/codes**: don’t invent new failure classes or reuse the wrong one; map exactly (F2, F4a, F5, F6, F7, F9, F10).
* **Temporal guesses**: don’t rely on timestamps to “prove” order; validate only what bytes and invariants can prove.

## Performance/engineering “helpfulness”

* **Stateful caches that alter behavior**: no memoization that could hide FS changes within a run.
* **Parallel reordering**: don’t parallelize V1…V6 or reorder checks; order is part of the contract.

Sticking to these “don’ts” keeps L3 lean, reproducible, and perfectly aligned with the frozen S0 spec and your L0/L1/L2 truths.

---

# Appendix — Local adapters used by L3 (pure, no new logic)

- `read_artifact_list(path)` → parse JSONL rows into `{basename, path, hash}` records.
- `materialize_artifacts_bytes(rows)` → for each row, call `host.read_bytes(row.path)` and return list of `{basename, bytes}`; preserve basenames.
- `read_git32_from_resolved(bundle_dir)` → read `git_commit_hex` from `manifest_fingerprint_resolved.json` and return **raw 32 bytes** via `hex64_to_raw32`.
- `read_single_jsonl(path)` → ensure exactly one line; strict-parse JSON and return the object.
- `count_jsonl(files)` → number of JSONL files in the list; `count_lines(path)` → exact line count in file.
- `bundle_manifest_list(bundle_dir)` → `host.read_json(join(bundle_dir,"MANIFEST.json")).files`.
- `load_dictionary_and_registry_from_artifacts(rows)` → locate dictionary/registry in 𝓐 and `host.read_json(...)`; pure lookups.

Local adapters used above (self‑contained)

```text
# use L0.sort_ascii(xs) — single canonical ASCII ordering
function ascii_sort(xs:list<string>) -> list<string>:
  return L0.sort_ascii(xs)

function as_dec(u64val:u64) -> string:
  # Decimal string without separators
  return to_decimal_string(u64val)

function artifact_list_contains(rows:list<object>, name:string) -> bool:
  # rows are objects with a 'basename' field
  for r in rows:
      if r.basename == name: return true
  return false

function bundle_contains_success_marker(dir:string) -> bool:
  return ("_passed.flag" in host.list_files(dir))

function instance_matches(bundle_dir:string, lineage:object) -> bool:
  # Minimal lineage equivalence: compare resolved files
  r = host.read_json(bundle_dir + "/parameter_hash_resolved.json")
  s = host.read_json(bundle_dir + "/manifest_fingerprint_resolved.json")
  return (r.parameter_hash == lineage.parameter_hash) and (s.manifest_fingerprint == lineage.fingerprint)

function valid_failure_shape(payload:object) -> bool:
  return (("failure_class" in payload) and ("failure_code" in payload) and ("detail" in payload))

# Minimal wrappers to align with L0 encoders/hashes used in V3
function hex64_to_raw32(hex64:string) -> bytes[32]:
  # delegate to L0 (single source of truth)
  return L0.hex64_to_raw32(hex64)

# LE64 encoder: use the single L0 primitive
function enc_u64_le(x:u64) -> bytes[8]:
  return L0.enc_u64(x)

# --- Primitive parsing capsule: strict JSON + byte helpers (normative for L3 JSONL usage) ---

function bytes_to_ascii(bs:bytes) -> string:
  # delegate to L0 strict decoder (reject BOM, invalid UTF-8)
  return L0.bytes_to_ascii(bs)

function split_bytes_on_lf(bs:bytes) -> list[bytes]:
  # delegate to L0 canonical splitter
  return L0.split_bytes_on_lf(bs)

function parse_json_strict(s:string) -> object:
  # delegate to L0 strict JSON (RFC 8259 + integer policy)
  return L0.parse_json_strict(s)

function read_single_jsonl(path:string) -> object:
  # Strictly one line → one JSON object
  bs = host.read_bytes(path)
  lines = L0.split_bytes_on_lf(bs)
  # ignore possible trailing empty line from final newline
  payload = [ln for ln in lines if len(ln) > 0]
  assert len(payload) == 1
  return L0.parse_json_strict(L0.bytes_to_ascii(payload[0]))

function count_jsonl(files:list[string]) -> u32:
  # Count JSONL files in a listing (basenames)
  return len([f for f in files if ends_with(f, ".jsonl")])

function count_lines(path:string) -> u64:
  # Exact line count (no normalization)
  return len(host.read_bytes(path).split(b"\n"))

function read_artifact_list(path:string) -> list[object]:
  # fingerprint_artifacts.jsonl rows → objects with at least {basename, path, sha256_hex}
  bs = host.read_bytes(path)
  out = []
  for ln in L0.split_bytes_on_lf(bs):
      if len(ln) == 0: continue
      out.append(L0.parse_json_strict(L0.bytes_to_ascii(ln)))
  return out

function materialize_artifacts_bytes(rows:list[object]) -> list[object]:
  # Re-open exactly the artefacts S0.2 fingerprinted; preserve basenames
  out = []
  for r in rows:
      out.append({ basename: r.basename, bytes: host.read_bytes(r.path) })
  return out

function read_git32_from_resolved(bundle_dir:string) -> bytes[32]:
  # Read git hex from the resolved file and decode to raw 32 bytes for recomputation
  mf = host.read_json(bundle_dir + "/manifest_fingerprint_resolved.json")
  return hex64_to_raw32(mf.git_commit_hex)

function read_rows(path:string) -> iterator[object]:
  # Schematic row iterator over a Parquet/JSONL shard; must surface embedded lineage fields.
  # Uses ONLY declared host shims:
  #  - JSONL: host.read_lines(path) → parse each line strictly.
  #  - Parquet: host.read_bytes(path) → decode via a local codec adapter (not a host shim).
  if ends_with(path, ".jsonl"):
      for ln in host.read_lines(path):
          if len(ln) == 0: continue
          yield L0.parse_json_strict(L0.bytes_to_ascii(ln))
  else:
      bs = host.read_bytes(path)                   # raw Parquet bytes
      for row in parquet_iter_rows(bs):            # local adapter, pure decode
          yield row

function parquet_iter_rows(bytes_blob:bytes) -> iterator[object]:
  # Local decode adapter; implementation binds to a deterministic Parquet reader.
  # Not a host shim; no normalization beyond the codec’s exact decoding.
  return PARQUET.decode_iter(bytes_blob)

function extract_json_schema_anchors_from(registry:object) -> set[string]:
  # Return the set of schema refs that are JSON-Schema anchors
  anchors = set()
  for entry in registry.entries:
      if entry.type == "json-schema" and has_key(entry, "anchor"):
          anchors.add(entry.anchor)
  return anchors

function fail_once_and_stop() -> object:
  # Orchestrator convenience: after abort_run(F*,...) was called by a validator
  return { verdict: "fail" }
```
```text
# Additional small adapters to avoid undefined names
function join(dir:string, name:string) -> string:
  # simple POSIX-style join; callers pass normalized roots
  if ends_with(dir, "/"): return dir + name
  else: return dir + "/" + name

function extract_hash(flag_text:string) -> hex64:
  # delegate to L0 `_passed.flag` inverse parser
  return L0.extract_hash(flag_text)

## (hex_to_bytes removed — use L0.hex_to_bytes / L0.hex64_to_raw32)

## (u64_to_le_bytes removed — use L0.enc_u64)
```