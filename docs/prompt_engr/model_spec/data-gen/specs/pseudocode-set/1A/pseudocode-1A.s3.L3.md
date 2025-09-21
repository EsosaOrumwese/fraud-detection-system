# S3·L3 — Validator

# 1) Purpose & Scope (binding)

## 1.1 Purpose (what this validator must prove)

From **bytes on disk only**, prove that the S3 outputs for a given `{parameter_hash, manifest_fingerprint}` satisfy **all state-3 contracts**:

* **Structure & lineage:** schemas match their anchors; partitions are **parameter-scoped only**; every row’s lineage **embed = path** (**row\.parameter_hash == partition.parameter_hash**); all S3 datasets for this run share the same **manifest_fingerprint** (cross-dataset equality).
* **Order authority:** `candidate_rank` is the **only** inter-country order; ranks are **contiguous** with **home=0** and unique per merchant; file order is **non-authoritative** (writer sorts listed below).
* **Optional lanes (as enabled):**

  * **Priors:** values are **fixed-dp weights** (`base_weight_dp` string with **dp = priors_cfg.dp** per row); **subset of candidates allowed** (no extras/dupes); no renormalisation.
  * **Counts:** per-country integers, **Σ count = N** where **N comes from S2 `nb_final`** (merchant→N authority); `residual_rank` total & contiguous; (if bounds configured) all bounds respected.
  * **Sequence:** for each `(merchant,country)`, `site_order = 1..count_i` (no gaps/dupes), optional zero-padded 6-digit `site_id` unique within country; **never** permutes the inter-country order.
* **Lane legality:** `emit_sequence ⇒ emit_counts` holds in the produced datasets.
* **Publish discipline:** the validator emits a single **atomic success marker** on PASS (with `_passed.flag` digest) or **one canonical failure record** (fail-fast).

**Writer sorts (non-authoritative for inter-country order, but required at write/read):**
`candidate_set: (merchant_id, candidate_rank, country_iso)` · `base_weight_priors: (merchant_id, country_iso)` · `integerised_counts: (merchant_id, country_iso)` · `site_sequence: (merchant_id, country_iso, site_order)`

## 1.2 Scope (what this validator touches)

* **Inputs (values, not paths):** `{parameter_hash, manifest_fingerprint, toggles}`, dictionary + schema anchors, BOM values needed to parse/verify (e.g., `priors_cfg`, `bounds?`), S3 datasets under test, and **S2 `nb_final`** map for **N** (read-only).
* **Outputs (validator’s own area):** a small **validation bundle** under the run’s validation area for `parameter_hash`: `summary.json`, `failures.jsonl` (if any), and `_passed.flag` (**SHA-256** over ASCII-sorted bundle bytes).
  **No** writes to S3 business datasets; **no** path literals anywhere.

## 1.3 Non-goals (explicit)

* No recomputation of business logic (no re-ranking, no re-integerisation).
* No RNG; no timestamps written to validated datasets.
* No “healing,” backfill, or producer mutations.
* No CI corridors or performance tuning inside this doc beyond the stated streaming/knob rules.

## 1.4 Success criteria (the green gate)

All must be true:

1. **Determinism:** same inputs (lineage, toggles, artifacts) ⇒ same PASS/FAIL and identical bundle bytes.
2. **Evidence-only:** every check is derivable from datasets + dictionary + minimal BOM parse rules + **S2 `nb_final`**; no hidden sources.
3. **Completeness:** every enabled lane’s contract is proven (structure, lineage, authority, cross-lane consistency).
4. **Atomicity & idempotence:** PASS writes `_passed.flag` atomically; reruns produce identical bytes; FAIL emits exactly one stable failure record and **no** success flag.
5. **Performance envelope:** O(total rows) via **streaming per merchant**, projected columns only; memory bounded per worker; fail-fast on first breach.

## 1.5 Tightness rules (enforced throughout the doc)

* **Placement is explicit:** L3 runs after L2 publish and never blocks L2; “validate-during-run” reads only **finalised** merchant slices.
* **Streaming algorithms only:** every section specifies the exact **columns needed** and a **one-pass** counter/contiguity method.
* **Single source of truth:** inter-country order = `candidate_rank`; within-country = `site_order`; **S2 `nb_final`** is the authority for **N**.
* **No ambiguity in legality:** `emit_sequence ⇒ emit_counts` is verified from artifacts (presence & joins), not assumed.
* **Stable errors:** each failure has a deterministic code, minimal payload, and precise stop point; validator halts at first failure (per merchant or run, as specified).
* **No path literals ever:** dictionary resolves dataset IDs → partitions/anchors; all code talks in **IDs and columns**, not file paths.

## 1.6 Cross-references (for implementers)

* **Where it runs & triggers:** §2 (pipeline placement & gating), §10 (validator DAG), §18 (wiring map).
* **What it validates:** §5 (structural/lineage), §6 (dataset contracts), §7 (cross-lane).
* **How it stays fast:** §8 (streaming algorithms), §9 (knobs).
* **What it emits:** §4 (bundle & `_passed.flag`), §16 (atomicity & idempotence).
* **Errors & logs:** §15 (error taxonomy), §17 (operational logging).
* **Kernels & skeletons:** §13–§14 (validator surfaces & pseudocode).
* **Fixtures & acceptance:** §20–§21.

---

# 2) Where L3 Lives — Pipeline Placement & Triggers

## 2.1 Placement (binding)

* **Default path:** `L2 publish (S3 datasets) → L3 validate (this doc) → merge/consume`.
* **Slice unit:** one **validation run per `parameter_hash`** (the whole S3 slice for that run).
* **Isolation:** L3 is **read-only**. It **never** blocks L2 and **never** touches producer tables.
* **Start condition:** L3 begins **after** L2 finishes publishing the `parameter_hash` slice (or a final subset if running in “during-run” mode; see §2.5).

## 2.2 Trigger & payload (deterministic)

L3 is invoked with a frozen payload—no hidden defaults:

```
RunArgs = {
  parameter_hash: Hex64,
  manifest_fingerprint: Hex64,
  toggles: { emit_priors: bool, emit_counts: bool, emit_sequence: bool }
}
```

**Entry points:**

* **Post-L2 hook (recommended):** controller calls L3 immediately after L2 reports “slice complete”.
* **CI job (optional):** validate a staging slice pre-merge.
* **On-demand audit (optional):** read-only check for ops.

## 2.3 What L3 reads (values, not paths)

* **S3 datasets** for `parameter_hash`:
  `candidate_set` (required), and—iff toggled—`base_weight_priors`, `integerised_counts`, `site_sequence`.
  *Note:* L3 reads **columns only**; full column lists are specified later in dataset sections.
* **Dictionary & schemas:** dataset IDs → schema anchors, **partition template** (parameter-scoped), writer-sort keys.
* **Lineage & toggles:** `{parameter_hash, manifest_fingerprint}` and the `{emit_*}` snapshot.
* **S2 N map:** `merchant_id → N` for the Σ counts check (authoritative).
* **BOM values (parse-only):** e.g., `priors_cfg` (dp), `bounds?` presence.
  *(Used to **verify**; never to recompute business outputs.)*

## 2.4 Gating rule (downstream consumption)

* **Hard gate:** Consumers must only read a `parameter_hash` slice if **L3 PASS** exists for the **same** `{parameter_hash, manifest_fingerprint}`.
* **Artifacts:** L3 produces either
  (a) a **PASS bundle** with an atomic `_passed.flag` (and summary), or
  (b) a **single FAIL record** (no `_passed.flag`).
  Absence of `_passed.flag` = **not validated**.

## 2.5 Validate-during-run (optional mode)

If you validate while L2 is still publishing:

* L3 reads **only finalised** merchant subsets (atomic tmp→rename guarantees no torn reads).
* L3 may skip non-final datasets/merchants; it accumulates results across retries.
* L3 emits the **final PASS** only after **all required datasets** for the `parameter_hash` slice have been validated; until then, no `_passed.flag`.

## 2.6 Concurrency & single-writer coexistence

* **Parallelism:** across-merchant parallelism is allowed in L3; within-merchant checks are **serial per dataset family** to keep counters simple.
* **Coexistence with L2:** L3 never locks producer locations; it only reads partitions that L2 has completed for the merchant/dataset.
* **Deterministic scheduling:** when parallelised, iterate merchants in a stable order for reproducible logs; early-fail stops remaining checks on that merchant.

## 2.7 Controller wiring (practical)

**Post-L2 (recommended):**

```
if L2_publish(parameter_hash).completed:
  result = L3_validate({
    parameter_hash,
    manifest_fingerprint,
    toggles: L2_reported_toggles(parameter_hash)
  })
  if result.PASS:
    mark_validated(parameter_hash, manifest_fingerprint)
  else:
    halt_downstream()
    surface_failure(result.failure)
```

* **CI mode:** same entrypoint; dictionary points at staging datasets; validator bundle is written to a separate validation area; producer tables untouched.
* **Audit mode:** same entrypoint; PASS/FAIL lives under `validation/{parameter_hash}/…`.

## 2.8 Idempotence & retries (binding)

* **Rerun-safe:** Re-running with identical `{parameter_hash, manifest_fingerprint, toggles}` yields the **same PASS bytes** or the **same single FAIL**.
* **Crash semantics:** If the process dies before atomic publish of the bundle, rerun; partials are ignored.
* **Mismatch guard:** If lineage or toggles change between attempts, L3 hard-fails early (no mixed bundles).

## 2.9 Preconditions (must be true before L3 starts)

* L2 has published all datasets implied by `toggles` for the target `parameter_hash` (or a final subset if §2.5).
* Dictionary/schema anchors resolve for each dataset under test.
* The **S2 N map** is accessible read-only for merchants in the slice.
* BOM parse values required for checks (e.g., priors dp, bounds presence) are available as **values**.

## 2.10 Non-actions (what L3 never does here)

* No producer emits, no backfills, no renormalisation, no re-ranking; no dereferencing file paths.
* L3 never blocks L2 and never writes into S3 business partitions.

## 2.11 Acceptance checks for this section

* [ ] Triggers and entry conditions are unambiguous.
* [ ] Gating is explicit and lineage-exact.
* [ ] Inputs are values-only; no paths.
* [ ] Validate-during-run rules prevent read/write races.
* [ ] Idempotent reruns defined and safe.

---

# 3) Inputs (Deterministic, Values not Paths)

## 3.1 Run arguments (must be provided by the controller)

```
RunArgs = {
  parameter_hash: Hex64,                  // slice under validation
  manifest_fingerprint: Hex64,            // lineage value all rows must embed
  toggles: { emit_priors: bool,
             emit_counts: bool,
             emit_sequence: bool }        // dictates which datasets must exist
}
```

## 3.2 Required handles (read-only)

* **Dictionary handle** — resolves dataset IDs → (schema anchor, partition template, logical writer sort).
* **Schema anchors** — JSON-Schema objects for each S3 dataset.
* **BOM values** *(values only)*:

  * `priors_cfg` (fixed-dp weight rules; **dp = priors_cfg.dp**, base-10 strings)
  * `bounds?` (per-country min/max for counts; optional)
* **S2 N map** — immutable `Map<merchant_id → N>` built from **S2 `nb_final` rows** for **this `parameter_hash`** (authority for Σ counts).

## 3.3 Dataset IDs under test (by `parameter_hash`)

* **Required:** `s3_candidate_set`.
* **Optional (gated by toggles):**
  `s3_base_weight_priors` (if `emit_priors`),
  `s3_integerised_counts` (if `emit_counts`),
  `s3_site_sequence` (if `emit_sequence`).

> L3 never uses file paths. The dictionary returns handles/iterators for these dataset IDs **scoped to `parameter_hash`**.

## 3.4 Column projections (exact columns per check)

Read **only** these columns; anything else is wasteful.

* **Candidates:** `merchant_id, country_iso, candidate_rank, is_home, parameter_hash, manifest_fingerprint`
* **Priors (if present):** `merchant_id, country_iso, base_weight_dp, dp, parameter_hash, manifest_fingerprint`
* **Counts (if present):** `merchant_id, country_iso, count, residual_rank, parameter_hash, manifest_fingerprint`
* **Sequence (if present):** `merchant_id, country_iso, site_order, site_id?, parameter_hash, manifest_fingerprint`

*(Lineage fields are for embed=path checks; `site_id` is optional by design.)*

## 3.5 Derived inputs built at start (deterministic)

* **`N_map`**: immutable `Map<merchant_id, int>` from **S2 `nb_final`** for **this `parameter_hash`**; used only to verify `Σ count = N`.
* **`lane_plan`** (from toggles):

  ```
  need_priors   := emit_priors
  need_counts   := emit_counts
  need_sequence := emit_sequence && need_counts    // hard legality
  ```

  This dictates which dataset handles must be present and which checks must run.

## 3.6 Concurrency knobs (values, not logic)

* `N_WORKERS : int` — parallel across merchants only (suggest 1..16).
* `batch_rows : int` — reader chunk size if supported (e.g., 20_000–100_000).
* `mem_watermark : bytes` — per-worker soft cap (e.g., 256–512 MB).
* `fast_mode : bool` — optional: run structural/lineage/keys only (still enforces lane legality); **full mode** runs all lane checks.
  *(Knobs change throughput only, never results; defaults are deterministic.)*

## 3.7 Preconditions (must hold before starting)

1. Dictionary exposes the required dataset IDs for **this `parameter_hash`** implied by `toggles`.
2. Schema anchors resolve; dictionary provides partition templates and writer sorts.
3. `manifest_fingerprint` for the run is known (rows must embed the same value).
4. `N_map` covers all merchants present in **counts** when `emit_counts = true`.
5. `priors_cfg` and any `bounds?` are available **as values** (not paths).

## 3.8 Rejection rules (fail fast, no work started)

* Missing dictionary entry or schema anchor for any required dataset.
* `emit_sequence = true` but counts dataset absent (illegal lane combo).
* `N_map` incomplete for any merchant present in counts.
* Missing BOM values required to parse/verify (e.g., `priors_cfg` dp).

## 3.9 What L3 never accepts as input

* File paths or glob patterns.
* Locale-dependent comparators (sorting is by explicit key order only).
* Producer “helper outputs” (L3 reads the canonical S3 datasets only).

## 3.10 Input → check mapping (at a glance)

* **Structure/lineage** → dictionary, schema anchors, lineage fields, toggles
* **Candidate authority** → candidate_set (rank, is_home)
* **Priors fixed-dp** → priors + `priors_cfg`
* **Counts sum & residuals** → counts + `N_map` (+ `bounds?`)
* **Sequence contiguity** → sequence (+ counts for per-country `count_i`)
* **Cross-lane legality** → presence & joins across candidates/priors/counts/sequence + toggles

---

# 4) Outputs (What L3 Publishes)

## 4.1 What gets published (bundle members)

L3 writes a **validation bundle** for a single `{parameter_hash, manifest_fingerprint}`:

1. `summary.json` — canonical, deterministic summary of the run.
2. `failures.jsonl` — **zero or one** line (fail-fast) with the single canonical failure record.
3. `_passed.flag` — present **only if PASS**; contains a digest computed over the bundle (see §4.4).

> **PASS:** publish `summary.json` and `_passed.flag` (**no** `failures.jsonl`).
> **FAIL:** publish `summary.json` and `failures.jsonl` (**no** `_passed.flag`).

**Fingerprint-scoped:** a bundle is tied to the provided `manifest_fingerprint`; never mix artifacts across fingerprints.

---

## 4.2 Content contracts (canonical formats)

### 4.2.1 `summary.json` (canonical JSON; sorted keys; UTF-8 w/o BOM; LF newline; no timestamps)

All fields required; values deterministic:

```json
{
  "component": "S3.L3",
  "parameter_hash": "<Hex64>",
  "manifest_fingerprint": "<Hex64>",
  "toggles": { "emit_priors": true/false, "emit_counts": true/false, "emit_sequence": true/false },
  "datasets_present": {
    "candidate_set": true,
    "base_weight_priors": true/false,
    "integerised_counts": true/false,
    "site_sequence": true/false
  },
  "row_counts": {
    "candidate_set": <int>,
    "base_weight_priors": <int>,
    "integerised_counts": <int>,
    "site_sequence": <int>
  },
  "merchants": { "total": <int>, "validated": <int>, "failed": <int> },
  "result": "PASS" | "FAIL",
  "version": { "doc_semver": "<x.y.z>", "validator_impl": "<name-or-sha>" }
}
```

**Rules**

* Keys **sorted lexicographically** (stable order); no platform-dependent whitespace.
* No timestamps; outputs are byte-identical across reruns.
* `datasets_present` reflects **actual presence** and is **toggle-consistent** (no present dataset for a disabled lane).
* Row counts and tallies match the validated rows/merchants.

---

### 4.2.2 `failures.jsonl` (only on FAIL; exactly one line)

A **single** JSON line with the canonical failure record:

```json
{
  "code": "<STABLE_ERROR_CODE>",
  "scope": "RUN" | "MERCHANT" | "DATASET",
  "dataset_id": "s3_candidate_set|s3_base_weight_priors|s3_integerised_counts|s3_site_sequence|null",
  "merchant_id": "<id-or-null>",
  "parameter_hash": "<Hex64>",
  "manifest_fingerprint": "<Hex64>",
  "details": { /* minimal deterministic K/Vs (e.g., expected, observed, key) */ }
}
```

**Rules**

* Exactly **one** record (fail-fast).
* Keys sorted; UTF-8 w/o BOM; **LF** newline at end of file.

---

### 4.2.3 `_passed.flag` (only on PASS)

Text file containing the **bundle digest**:

```
sha256=<64-hex>
```

* `<64-hex>` is **lower-case** SHA-256 over the manifest string (see §4.4).
* File ends with **LF** newline.

---

## 4.3 Publish semantics (atomic & idempotent)

* **Atomic:** write members to a temp location → **fsync** → **rename** as a single commit.
* **Idempotent:** re-running L3 with the same inputs produces **byte-identical** `summary.json` and `_passed.flag` (or the same single `failures.jsonl` on FAIL).
* **Ref-safe:** the publisher must **refuse to overwrite** an existing bundle that has different lineage/toggles.
* **No partials:** never expose `_passed.flag` without `summary.json`, or vice versa.

---

## 4.4 Digest rule (how `_passed.flag` is computed)

Deterministic algorithm:

1. Compute **member digests** for the PASS case:
   `d_summary = SHA256(bytes(summary.json))`
   *(No `failures.jsonl` on PASS.)*
2. Build the canonical **manifest string** by concatenating, in lexicographic order of member names:

   ```
   "summary.json" + NUL + d_summary
   ```

   where **NUL** is a single byte `0x00`, and `d_summary` is the **lower-case** hex string.
3. `_passed.flag` content is:

   ```
   sha256=<SHA256(manifest_string)>
   ```

**Notes**

* On **FAIL**, `_passed.flag` is **not** written.
* Because `summary.json` is canonical (sorted keys, no timestamps), the flag is stable across reruns.

---

## 4.5 Determinism rules (binding)

* **Canonical JSON** everywhere (stable key order, UTF-8 w/o BOM, LF newline).
* **No timestamps** or host-dependent fields.
* **Stable counts** derive solely from validated datasets, toggles, and S2 authority.
* **One failure only**: first breach is canonical; do not aggregate errors.

---

## 4.6 Build & publish pseudocode (host-neutral)

```
PROC build_and_publish_bundle(run_args, tallies, maybe_failure):
  // 1) Build canonical summary.json (sorted keys; UTF-8; LF)
  summary := {
    "component": "S3.L3",
    "parameter_hash": run_args.parameter_hash,
    "manifest_fingerprint": run_args.manifest_fingerprint,
    "toggles": run_args.toggles,
    "datasets_present": tallies.datasets_present,   // booleans, toggle-consistent
    "row_counts": tallies.row_counts,               // ints
    "merchants": { "total": tallies.m_total,
                   "validated": tallies.m_ok,
                   "failed": tallies.m_fail },
    "result": (maybe_failure == NULL ? "PASS" : "FAIL"),
    "version": { "doc_semver": DOC_SEMVER, "validator_impl": VALIDATOR_ID }
  }
  summary_bytes := CANONICAL_JSON(summary)   // sorted keys, UTF-8 w/o BOM, LF

  // 2) Decide PASS/FAIL artifacts
  IF maybe_failure == NULL:
      d_summary := SHA256_HEX(summary_bytes).lower()
      manifest  := CONCAT("summary.json", NUL, d_summary)
      flag_line := CONCAT("sha256=", SHA256_HEX(BYTES(manifest)).lower(), "\n")
      PUBLISH_VALIDATION_BUNDLE(run_args.parameter_hash,
                                run_args.manifest_fingerprint,
                                { "summary.json": summary_bytes,
                                  "_passed.flag": BYTES(flag_line) })
  ELSE:
      failure_bytes := BYTES(CANONICAL_JSON_LINE(maybe_failure) + "\n")
      PUBLISH_VALIDATION_BUNDLE(run_args.parameter_hash,
                                run_args.manifest_fingerprint,
                                { "summary.json": summary_bytes,
                                  "failures.jsonl": failure_bytes })
END PROC
```

**Constraints**

* `CANONICAL_JSON(*)` sorts keys recursively; emits **LF** and **no BOM**.
* `CANONICAL_JSON_LINE` same, on one line.
* `PUBLISH_VALIDATION_BUNDLE` performs temp write → fsync → rename and **refuses** to overwrite a different bundle for the same lineage/toggles.

---

## 4.7 Zero-row and partial-lane behavior

* If a toggled lane is **enabled** but produces **zero rows** (e.g., counts enabled with home-only case), the lane still **exists**; the validator treats the empty dataset as **valid** if all structural/lineage rules hold and cross-lane consistency is satisfied.
* If a lane is **disabled** by toggles, the validator **must not** expect its dataset (and must record `datasets_present=false` accordingly).

---

## 4.8 Acceptance checklist (for this section)

* [ ] PASS produces `summary.json` + `_passed.flag`; FAIL produces `summary.json` + `failures.jsonl` (never both).
* [ ] All outputs are canonical and deterministic (sorted keys, UTF-8 w/o BOM, LF, no timestamps).
* [ ] `_passed.flag` digest computed exactly as specified and **only** on PASS.
* [ ] Atomic publish; idempotent reruns; no partial bundles visible.
* [ ] Zero-row/partial-lane behavior defined and consistent with toggles.

---

# 5) Global Structural & Lineage Checks (Run-Wide)

## 5.1 Objective (what this section must prove)

For the given `{parameter_hash, manifest_fingerprint, toggles}`, prove **run-wide** that:

1. Every **required** S3 dataset exists (and no **forbidden** one does) per the toggles.
2. Each dataset resolves to its **schema anchor** and **parameter-scoped** partition template.
3. Every row embeds lineage that **matches the run**: **embed = path** for `parameter_hash` and embedded `manifest_fingerprint` == run fingerprint.
4. All datasets in this run embed the **same** `manifest_fingerprint` (implied by the per-row check).

Zero-row datasets are valid if toggled on and all structural/lineage rules hold.

---

## 5.2 Presence matrix (dataset existence vs toggles)

Derive a **presence matrix** for the four S3 datasets under `parameter_hash`:

| Dataset ID              | Must exist?                           |
|-------------------------|---------------------------------------|
| `s3_candidate_set`      | **Yes** (always)                      |
| `s3_base_weight_priors` | `emit_priors`                         |
| `s3_integerised_counts` | `emit_counts`                         |
| `s3_site_sequence`      | `emit_sequence` **and** `emit_counts` |

**Fail fast** if: a required dataset is missing, a forbidden dataset is present, or `emit_sequence=true` while counts are absent.

---

## 5.3 Dictionary & schema resolution (gate)

For each dataset that **must** exist:

* Resolve **dataset ID → (schema anchor, partition template, logical writer sort)** from the dictionary.
* Reject if resolution fails or the schema anchor is missing.

*(No paths: the dictionary/reader returns handles/iterators.)*

---

## 5.4 Partitioning discipline (parameter-scoped only)

For each **present** dataset:

* Assert the declared partition **dimension set** is **exactly** `{parameter_hash}` (no extras).
* Assert the selected partition **is** the run’s `parameter_hash`.

*(If the reader exposes partition metadata, verify strictly; L3 never infers from file paths.)*

---

## 5.5 Lineage equality (row-level, streaming)

For every **present** dataset, **stream** the minimal lineage projection:

* **Columns:** `parameter_hash, manifest_fingerprint`.
* **Per row checks:**

  * `row.parameter_hash == RunArgs.parameter_hash` → else **EMBED-PATH-MISMATCH** (dataset-scoped).
  * `row.manifest_fingerprint == RunArgs.manifest_fingerprint` → else **MIXED-MANIFEST** (dataset-scoped).

*Because every row is checked against the run fingerprint, cross-dataset equality is guaranteed once all present datasets pass.*

*(This pass also accumulates row counts for `summary.json`.)*

---

## 5.6 Writer-sort note (non-authoritative)

File order is **non-authoritative** for inter-country order; authority checks happen later. Global checks here do **not** rely on file order; they only verify structure/lineage. (Per-dataset writer-sort sanity appears in later sections.)

---

## 5.7 Streaming algorithm (one pass per dataset)

**Columns:** lineage pair (`parameter_hash`, `manifest_fingerprint`) + optionally `merchant_id` for tallies.

```
PROC v_check_structural(run_args, dict, read, toggles):
  presence := DATASET_PRESENCE_MATRIX(dict.dict_handle, run_args.parameter_hash)

  // 1) Presence vs toggles (fail-fast)
  // Required/forbidden: candidate_set always required; priors iff emit_priors;
  // counts iff emit_counts; sequence iff emit_sequence AND emit_counts.
  IF !presence.candidate_set: FAIL("DATASET-PRESENCE-MISMATCH","RUN","s3_candidate_set",NULL,{"required":true,"present":false})
  IF toggles.emit_priors   AND !presence.base_weight_priors:   FAIL("DATASET-PRESENCE-MISMATCH","RUN","s3_base_weight_priors",NULL,{"required":true,"present":false})
  IF toggles.emit_counts   AND !presence.integerised_counts:   FAIL("DATASET-PRESENCE-MISMATCH","RUN","s3_integerised_counts",NULL,{"required":true,"present":false})
  IF toggles.emit_sequence AND !toggles.emit_counts:           FAIL("DATASET-PRESENCE-MISMATCH","RUN","s3_site_sequence",NULL,{"required":true,"present":false})
  IF toggles.emit_sequence AND !presence.site_sequence:        FAIL("DATASET-PRESENCE-MISMATCH","RUN","s3_site_sequence",NULL,{"required":true,"present":false})

  // 2) Resolve anchors & templates (fail-fast)
  required_ids := ["s3_candidate_set"]
  IF toggles.emit_priors:   required_ids.append("s3_base_weight_priors")
  IF toggles.emit_counts:   required_ids.append("s3_integerised_counts")
  IF toggles.emit_sequence: required_ids.append("s3_site_sequence")
  for ds in required_ids:
      r := DICT_RESOLVE(dict.dict_handle, ds)
      IF r == NULL:
           FAIL("DICT-RESOLVE-FAIL","RUN",ds,NULL)
      IF r.partition_keys != ["parameter_hash"]:
           FAIL("PARTITION-TEMPLATE-MISMATCH","RUN",ds,NULL)

  // 3) Stream lineage rows per present dataset
  row_counts := {
    "candidate_set": 0,
    "base_weight_priors": 0,
    "integerised_counts": 0,
    "site_sequence": 0
  }

  // Map dataset_id → summary key used by row_counts / summary.json
  summary_key := {
    "s3_candidate_set":       "candidate_set",
    "s3_base_weight_priors":  "base_weight_priors",
    "s3_integerised_counts":  "integerised_counts",
    "s3_site_sequence":       "site_sequence"
  }

  // Presence map (dataset_id → boolean), to drive streaming below
  present_flag := {
    "s3_candidate_set":       presence.candidate_set,
    "s3_base_weight_priors":  presence.base_weight_priors,
    "s3_integerised_counts":  presence.integerised_counts,
    "s3_site_sequence":       presence.site_sequence
  }

  for ds in ["s3_candidate_set","s3_base_weight_priors","s3_integerised_counts","s3_site_sequence"]:
      IF !present_flag[ds]: continue
      it := OPEN_ITER(ds, run_args.parameter_hash,
                      ["parameter_hash","manifest_fingerprint"], order=NULL)
      for row in it:
          IF row.parameter_hash != run_args.parameter_hash:
              FAIL("EMBED-PATH-MISMATCH", "DATASET", ds, NULL,
                   details={expected: run_args.parameter_hash, observed: row.parameter_hash})
          IF row.manifest_fingerprint != run_args.manifest_fingerprint:
              FAIL("MIXED-MANIFEST", "DATASET", ds, NULL,
                   details={expected: run_args.manifest_fingerprint, observed: row.manifest_fingerprint})
          row_counts[ summary_key[ds] ] += 1
      it.close()

  // Build datasets_present map for summary.json explicitly
  datasets_present := {
    "candidate_set":       present_flag["s3_candidate_set"],
    "base_weight_priors":  present_flag["s3_base_weight_priors"],
    "integerised_counts":  present_flag["s3_integerised_counts"],
    "site_sequence":       present_flag["s3_site_sequence"]
  }
  RETURN { datasets_present: datasets_present, row_counts }
END PROC
```

**Early exit:** On the first breach (resolution, presence, embed/path, mixed manifest), stop and emit the single canonical failure.

---

## 5.8 Complexity & knobs

* **Time:** O(total rows) across present datasets.
* **Memory:** O(1) per row (pure streaming); no materialized joins.
* **Knobs:** `batch_rows` (if the reader supports chunking) to amortize I/O.
* **Fail-fast:** abort on first error to avoid scanning unnecessary bytes.

---

## 5.9 Failure codes (deterministic, minimal)

* `DICT-RESOLVE-FAIL` — dictionary/schema anchor missing for a required dataset.
* `DATASET-PRESENCE-MISMATCH` — presence vs toggles illegal (missing required lane or forbidden lane present).
* `PARTITION-TEMPLATE-MISMATCH` — dataset declares partitions other than `parameter_hash`.
* `EMBED-PATH-MISMATCH` — `row.parameter_hash` ≠ run `parameter_hash`.
* `MIXED-MANIFEST` — `row.manifest_fingerprint` ≠ run `manifest_fingerprint` (dataset-scoped).

Each error carries: `{code, dataset_id?, parameter_hash, manifest_fingerprint, details{…}}`. **One error → stop**.

---

## 5.10 What this section does **not** check (by design)

* Candidate rank contiguity and `home=0` (see §6).
* Priors fixed-dp / **subset** (see §6).
* Counts Σ=N & residual ranks/bounds (see §6).
* Sequence 1..countᵢ gaps/dupes and cross-country stability (see §6).
* Cross-lane joins/legality beyond the presence matrix (see §7).

---

## 5.11 Acceptance checklist (for this section)

* [ ] Presence matrix vs toggles enforced; sequence never present without counts.
* [ ] Dictionary & schema anchors resolve; partition template is parameter-scoped only.
* [ ] Every row’s lineage matches the run; no mixed manifests within or across datasets.
* [ ] Streaming implementation (columns only); O(rows); fail-fast on first breach.
* [ ] Deterministic single failure on error; zero-row datasets allowed if toggled on.

---

# 6) Dataset Contracts (What is Validated)

## 6.1 Scope & prerequisites

This section runs **after** the global structural/lineage checks (presence, schema anchors, partitioning, embed=path) have passed. Each dataset below is validated **only if present** according to toggles.

**Columns required (re-stated for clarity):**

* **Candidates:** `merchant_id, country_iso, candidate_rank, is_home`
* **Priors:** `merchant_id, country_iso, base_weight_dp, dp`
* **Counts:** `merchant_id, country_iso, count, residual_rank`
* **Sequence:** `merchant_id, country_iso, site_order, site_id?`
  *(Lineage was already checked globally.)*

Writer-sort sanity is verified here even though the orchestrator promises it.

---

## 6.2 Candidate set (required)

### 6.2.1 Contract

* **Uniqueness:** per merchant, unique `(country_iso)` and unique `(candidate_rank)`.
* **Contiguity:** per merchant, `candidate_rank` is **exactly** `0..K−1`.
* **Home rank:** exactly one `is_home=true` row with `candidate_rank=0`.
* **Writer sort:** `(merchant_id, candidate_rank, country_iso)` order.

### 6.2.2 Streaming algorithm (one pass, per merchant)

```
state := {
  cur: null, seen_countries: set(), seen_ranks: set(),
  min_rank: +INF, max_rank: -INF, home0_seen: false,
  last_key: null
}

PROC flush_merchant(m):
  IF m == null: RETURN
  IF !state.home0_seen: FAIL("HOME-MISSING", merchant=m)
  IF state.min_rank != 0: FAIL("CAND-RANK-START-NEQ-0", merchant=m)
  IF |state.seen_ranks| != (state.max_rank - state.min_rank + 1):
       FAIL("CAND-RANK-GAP", merchant=m)

for row in stream(candidate_set, order=("merchant_id","candidate_rank","country_iso")):
  IF row.merchant_id != state.cur:
     flush_merchant(state.cur)
     // reset for new merchant
     state := {cur: row.merchant_id, seen_countries: set(), seen_ranks: set(),
               min_rank: +INF, max_rank: -INF, home0_seen: false, last_key: null}

  // writer-sort sanity (non-decreasing key)
  key := (row.merchant_id, row.candidate_rank, row.country_iso)
  IF state.last_key != null AND key < state.last_key:
     FAIL("DATASET-UNSORTED", dataset="s3_candidate_set", merchant=row.merchant_id)
  state.last_key := key

  // uniqueness
  IF row.country_iso IN state.seen_countries:
     FAIL("CAND-DUPE-ISO", merchant=row.merchant_id, iso=row.country_iso)
  IF row.candidate_rank IN state.seen_ranks:
     FAIL("CAND-DUPE-RANK", merchant=row.merchant_id, rank=row.candidate_rank)
  INSERT row.country_iso INTO state.seen_countries
  INSERT row.candidate_rank INTO state.seen_ranks

  // contiguity trackers
  state.min_rank := min(state.min_rank, row.candidate_rank)
  state.max_rank := max(state.max_rank, row.candidate_rank)

  // home@0
  IF row.is_home:
     IF row.candidate_rank != 0:
        FAIL("HOME-RANK-NEQ-0", merchant=row.merchant_id, rank=row.candidate_rank)
     IF state.home0_seen: FAIL("HOME-DUPE", merchant=row.merchant_id)
     state.home0_seen := true

flush_merchant(state.cur)
```

**Outputs for later lanes:** build (in the same pass) `cand_set_map[merchant_id] = set(country_iso)` for priors/counts joins.

---

## 6.3 Priors (optional)

### 6.3.1 Contract

* **Presence & join:** exists iff `emit_priors=true`; **subset of** candidate countries per merchant (no extras; duplicates forbidden).
* **Fixed-dp weights:** `base_weight_dp` parses as a **base-10 fixed-precision decimal string**; on-row `dp` **equals `priors_cfg.dp` for every row**; no exponents/locale.
* **No renormalisation:** priors are **weights**, not probabilities.
* **Writer sort:** `(merchant_id, country_iso)` order.

### 6.3.2 Streaming algorithm (single pass with join coverage)

```
seen := map merchant -> set()  // countries seen in priors

for row in stream(priors, order=("merchant_id","country_iso")):
  // writer-sort sanity
  assert non-decreasing (merchant_id, country_iso)
    else FAIL("DATASET-UNSORTED","DATASET","s3_base_weight_priors", row.merchant_id)

  key := (row.merchant_id, row.country_iso)
  // ensure per-merchant set exists
  IF row.merchant_id NOT IN seen:
     seen[row.merchant_id] := set()
  IF row.merchant_id NOT IN cand_set_map OR
     row.country_iso NOT IN cand_set_map[row.merchant_id]:
       FAIL("PRIORS-EXTRA-COUNTRY", merchant=row.merchant_id, iso=row.country_iso)

  IF row.country_iso IN seen[row.merchant_id]:
       FAIL("PRIORS-DUPE-COUNTRY", merchant=row.merchant_id, iso=row.country_iso)
  INSERT row.country_iso INTO seen[row.merchant_id]

  IF !is_fixed_dp_score(row.base_weight_dp, dp=priors_cfg.dp):
       FAIL("PRIORS-DP-VIOL", merchant=row.merchant_id, iso=row.country_iso)
  IF row.dp != priors_cfg.dp:
       FAIL("PRIORS-DP-VIOL", merchant=row.merchant_id, iso=row.country_iso)

// completeness not required for priors: subset allowed (no extras, no duplicates)
```

---

## 6.4 Counts (optional)

### 6.4.1 Contract

* **Presence & join:** exists iff `emit_counts=true`; **exactly one** row per candidate country; no extras/missing.
* **Integers & non-negative:** `count` is an integer ≥ 0.
* **Sum rule:** per merchant, `Σ count == N_map[merchant_id]`.
* **Residual ranks:** per merchant, `residual_rank` is total/contiguous over the candidate countries (no gaps/dupes, ranks start at 1).
* **Bounds (if configured):** for any configured `(min/max)` per `(merchant,country)`, `min ≤ count ≤ max`.
* **Writer sort:** `(merchant_id, country_iso)` order.

### 6.4.2 Streaming algorithm (single pass + completeness)

```
seen_iso := map merchant -> set()
seen_res  := map merchant -> set()
sum_by_m  := map merchant -> 0

for row in stream(counts, order=("merchant_id","country_iso")):
  // defaults for unseen merchants
  IF row.merchant_id NOT IN seen_iso: seen_iso[row.merchant_id] := set()
  IF row.merchant_id NOT IN seen_res: seen_res[row.merchant_id] := set()
  IF row.merchant_id NOT IN sum_by_m: sum_by_m[row.merchant_id] := 0
  // writer-sort sanity
  assert non-decreasing (merchant_id, country_iso)
    else FAIL("DATASET-UNSORTED","DATASET","s3_integerised_counts", row.merchant_id)

  // join coverage (no extras; no dupes)
  IF row.merchant_id NOT IN cand_set_map OR
     row.country_iso NOT IN cand_set_map[row.merchant_id]:
       FAIL("COUNTS-EXTRA-COUNTRY", merchant=row.merchant_id, iso=row.country_iso)
  IF row.country_iso IN seen_iso[row.merchant_id]:
       FAIL("COUNTS-DUPE-COUNTRY", merchant=row.merchant_id, iso=row.country_iso)
  INSERT row.country_iso INTO seen_iso[row.merchant_id]

  // count type & sum
  IF !is_int(row.count) OR row.count < 0:
       FAIL("COUNTS-NONNEG-INT", merchant=row.merchant_id, iso=row.country_iso, value=row.count)
  sum_by_m[row.merchant_id] += row.count

  // residual ranks
  IF row.residual_rank IN seen_res[row.merchant_id]:
       FAIL("COUNTS-RESID-DUPE", merchant=row.merchant_id, resid=row.residual_rank)
  INSERT row.residual_rank INTO seen_res[row.merchant_id]

  // bounds (optional)
  IF bounds? exists for (row.merchant_id,row.country_iso):
     (lo,hi) := bounds[row.merchant_id,row.country_iso]
     IF row.count < lo OR row.count > hi:
        FAIL("BOUNDS-VIOL", merchant=row.merchant_id, iso=row.country_iso, count=row.count, lo=lo, hi=hi)

// post-merchant checks
for m in cand_set_map:
  // Sum rule
  IF sum_by_m[m] != N_map[m]:
     FAIL("COUNTS-SUM-NEQ-N", merchant=m, expected=N_map[m], observed=sum_by_m[m])
  // Residual-rank totality & contiguity (1..#countries)
  c := |cand_set_map[m]|
  IF |seen_res[m]| != c OR (c > 0 AND (min(seen_res[m]) != 1 OR max(seen_res[m]) != c)):
     FAIL("COUNTS-RESID-GAP", merchant=m)
  // Join completeness (no missing)
  FOR iso IN cand_set_map[m]:
    IF iso NOT IN seen_iso[m]:
       FAIL("COUNTS-MISSING-COUNTRY", merchant=m, iso=iso)
```

---

## 6.5 Sequence (optional; requires counts)

### 6.5.1 Contract

* **Legality:** sequence lane may exist **only if** counts lane exists (and is valid) for the merchant.
* **Within-country contiguity:** for each `(merchant,country)`, `site_order` is **exactly** `1..count_i`; no gaps or duplicates.
* **Optional `site_id`:** if present, zero-padded 6-digit string; unique within `(merchant,country)`.
* **Never permutes inter-country order:** sequencing is inside country blocks only.
* **Writer sort:** `(merchant_id, country_iso, site_order)` order.

### 6.5.2 Streaming algorithm (single pass; extras + contiguity)

```
count_i   := map (merchant,country) -> count   // built from counts in §6.4
seen_site := map (merchant,country) -> 0
seen_ids  := map (merchant,country) -> set()

for row in stream(sequence, order=("merchant_id","country_iso","site_order")):
  key := (row.merchant_id, row.country_iso)

  // writer-sort sanity
  assert non-decreasing (merchant_id, country_iso, site_order)
    else FAIL("DATASET-UNSORTED","DATASET","s3_site_sequence", row.merchant_id)

  // legality & extras
  IF key NOT IN count_i:
     FAIL("SEQ-COUNTRY-NOT-IN-COUNTS", merchant=row.merchant_id, iso=row.country_iso)

  // contiguity within (merchant,country)
  expected := seen_site[key] + 1
  IF row.site_order != expected:
     FAIL("SEQ-GAP", merchant=row.merchant_id, iso=row.country_iso,
                      expected=expected, observed=row.site_order)
  seen_site[key] := row.site_order

  // optional id format/uniqueness
  IF row.site_id != NULL:
     IF !is_zero_padded_6(row.site_id):
        FAIL("SEQ-ID-FORMAT", merchant=row.merchant_id, iso=row.country_iso, id=row.site_id)
     IF row.site_id IN seen_ids[key]:
        FAIL("SEQ-ID-DUPE", merchant=row.merchant_id, iso=row.country_iso, id=row.site_id)
     INSERT row.site_id INTO seen_ids[key]

// post-keys: exact length per (merchant,country)
for (m, iso) IN KEYS(count_i):
  IF seen_site[(m, iso)] != count_i[(m, iso)]:
     FAIL("SEQ-LENGTH-NEQ-COUNT",
          merchant=m, iso=iso,
          expected=count_i[(m, iso)], observed=seen_site[(m, iso)])
```

---

## 6.6 Failure codes (dataset-scoped; deterministic)

* **Candidate set:** `CAND-DUPE-ISO`, `CAND-DUPE-RANK`, `HOME-MISSING`, `HOME-DUPE`, `HOME-RANK-NEQ-0`, `CAND-RANK-START-NEQ-0`, `CAND-RANK-GAP`, `DATASET-UNSORTED`.
* **Priors:** `PRIORS-EXTRA-COUNTRY`, `PRIORS-DP-VIOL`, `PRIORS-DUPE-COUNTRY`, `DATASET-UNSORTED`.
* **Counts:** `COUNTS-EXTRA-COUNTRY`, `COUNTS-MISSING-COUNTRY`, `COUNTS-DUPE-COUNTRY`, `COUNTS-NONNEG-INT`, `COUNTS-SUM-NEQ-N`, `COUNTS-RESID-DUPE`, `COUNTS-RESID-GAP`, `BOUNDS-VIOL`, `DATASET-UNSORTED`.
* **Sequence:** `SEQ-COUNTRY-NOT-IN-COUNTS`, `SEQ-GAP`, `SEQ-LENGTH-NEQ-COUNT`, `SEQ-ID-FORMAT`, `SEQ-ID-DUPE`, `SEQ-NO-COUNTS`, `DATASET-UNSORTED`.

Each failure carries `{code, dataset_id, merchant_id?, details{…}}` and stops validation (fail-fast).

---

## 6.7 Zero-row behavior (enabled lane)

If a toggled lane is **enabled** but yields **zero rows** (e.g., sequence for countries where `count_i=0`), emptiness is **valid** if:

* presence and lineage already passed, and
* cross-lane constraints are satisfied (e.g., no sequence when counts are absent for that `(merchant,country)`).

---

## 6.8 Acceptance checklist (for this section)

* [ ] Candidate set: uniqueness, contiguity `0..K−1`, and **home\@0** verified; writer-sort sanity enforced.
* [ ] Priors: **subset of candidates** (no extras/dupes); **fixed-dp** parsed on `base_weight_dp`; on-row **dp == priors_cfg.dp**; **no renorm**; writer-sort sanity.
* [ ] Counts: one-to-one with candidates; **Σ=N**; non-negative integers; residual ranks total & contiguous; bounds respected; writer-sort sanity; completeness + no extras.
* [ ] Sequence: per-country `1..count_i`; extras rejected; optional ID format/uniqueness; never cross-country reorder; writer-sort sanity.
* [ ] All algorithms are **single-pass streaming**, column-projected, O(rows), and fail-fast.

---

# 7) Cross-Dataset Legality & Authority

## 7.1 Objective (binding)

Across the four S3 datasets for a given `{parameter_hash, manifest_fingerprint}` and the run toggles:

1. **Lane legality:** datasets present exactly match toggles and the dependency holds **per merchant**:
   **`emit_sequence ⇒ emit_counts`** (both run-wide and per merchant).
2. **Cross-lane joins:** when a lane is present:
   - **Priors:** country set is a **subset** of the candidate-set countries (no extras/dupes).
   - **Counts:** country set **equals** the candidate-set countries (no extras/missing).
   *(§6 enforces the lane-internal parts; here we assert the **across-lane** legality per merchant.)*
3. **Order authorities:**

   * **Inter-country:** the **only** authority is `candidate_rank` in **candidate_set**; other datasets must not imply cross-country order.
   * **Within-country:** `site_order` governs **only** inside a country block.

All checks are **read-only**, **O(rows)**, and **fail-fast**.

---

## 7.2 Inputs used in this section (columns only)

* **Candidates:** `merchant_id, country_iso, candidate_rank`
* **Priors (if present):** `merchant_id, country_iso`
* **Counts (if present):** `merchant_id, country_iso, count, residual_rank`
* **Sequence (if present):** `merchant_id, country_iso, site_order`
* **From §6 results (in-memory, deterministic):**

  * `cand_set_map[m] = set(country_iso)` built while validating candidates (§6.2.2)
  * `count_i[(m, iso)] = count` built while validating counts (§6.4.2)

> If your implementation separates modules, you may rebuild these maps by streaming the minimal columns again; the algorithms below assume reuse to avoid a second pass.

---

## 7.3 Streaming strategy (per merchant, single pass per lane)

Iterate merchants in deterministic order; reuse the sets/maps from §6 to avoid re-scans:

```
for each merchant_id in MERCHANT_ORDER:

  cand_set := cand_set_map[merchant_id]                // from §6.2.2
  K := |cand_set|

  // (A) Priors (if present at run-level and present for this merchant)
  if priors lane present:
    seen_priors := 0
    for row in stream(priors where merchant_id,
                      order=("merchant_id","country_iso")):
      if row.country_iso not in cand_set:
        FAIL("PRIORS-EXTRA-COUNTRY", merchant=merchant_id, iso=row.country_iso)
      seen_priors += 1
    // completeness not required for priors; subset allowed (no extras/dupes)

  // (B) Counts (if present)
  if counts lane present:
    seen_counts := 0
    for row in stream(counts where merchant_id,
                      order=("merchant_id","country_iso")):
      if row.country_iso not in cand_set:
        FAIL("COUNTS-EXTRA-COUNTRY", merchant=merchant_id, iso=row.country_iso)
      seen_counts += 1
    if seen_counts != K:
      FAIL("COUNTS-MISSING-COUNTRY", merchant=merchant_id)

  // (C) Sequence (if present)
  if sequence lane present and counts lane absent:
    FAIL("SEQ-NO-COUNTS", merchant=merchant_id)

  if sequence lane present:
    // count_i built in §6; reuse it to cross-check lengths
    seq_len_by_country := map(country_iso -> 0)
    for row in stream(sequence where merchant_id,
                      order=("merchant_id","country_iso","site_order")):
      if (merchant_id,row.country_iso) not in count_i:
        FAIL("SEQ-COUNTRY-NOT-IN-COUNTS", merchant=merchant_id, iso=row.country_iso)
      seq_len_by_country[row.country_iso] += 1

    for iso in cand_set:
      if (merchant_id, iso) not in count_i:
        // covered above, but explicit for completeness
        FAIL("SEQ-COUNTRY-NOT-IN-COUNTS", merchant=merchant_id, iso=iso)
      if seq_len_by_country.get(iso, 0) != count_i[(merchant_id, iso)]:
        FAIL("SEQ-LENGTH-NEQ-COUNT",
             merchant=merchant_id, iso=iso,
             expected=count_i[(merchant_id, iso)],
             observed=seq_len_by_country.get(iso, 0))

  // (D) Inter-country authority sanity
  // Enforced by schema anchors: only candidate_set has 'candidate_rank'.
  // Assert by contract that non-candidate datasets do not expose 'candidate_rank'.
```

**Notes**

* Presence vs toggles was enforced in §5; §6 already validated lane-internal specifics (dp, Σ=N, per-country contiguity). Here we focus on **cross-lane legality** and **authority boundaries**.
* All writer-sort sanity is already checked in §6; we rely on that guarantee to keep the above streaming passes O(rows).

---

## 7.4 Authority boundaries (what must never happen)

* Any attempt to **impose or imply inter-country order outside the candidate set** (e.g., a `candidate_rank`-like field in priors/counts/sequence) is illegal → **`AUTH-ORDER-VIOLATION`**.
* Sequence must never encode cross-country transitions; it is strictly within-country.

> Implementation hint: assert from schema anchors that only **candidate_set** defines `candidate_rank`. The global schema check (§5) already guarantees this; the check here is a contract assertion (no extra I/O).

---

## 7.5 Failure codes (deterministic, minimal)

**Lane legality**

* `SEQ-NO-COUNTS` — sequence present for a merchant while counts absent.

**Cross-lane joins**

* `PRIORS-EXTRA-COUNTRY`
* `COUNTS-EXTRA-COUNTRY` / `COUNTS-MISSING-COUNTRY`
* `SEQ-COUNTRY-NOT-IN-COUNTS` / `SEQ-LENGTH-NEQ-COUNT`

**Authority**

* `AUTH-ORDER-VIOLATION` — non-candidate dataset attempts to encode inter-country order.

Each error carries `{code, dataset_id?, merchant_id, details{country_iso?, expected?, observed?}}` and stops validation.

---

## 7.6 Complexity & performance

* **Time:** O(total rows) across lanes with simple set/map lookups.
* **Memory:** O(C) per merchant, where C = #candidate countries; O(1) counters for priors; O(C) map for counts/sequence.
* **Knobs:** inherit `N_WORKERS`, `batch_rows`, `mem_watermark`; fail-fast truncates wasted scans.

---

## 7.7 Acceptance checklist (for this section)

* [ ] `emit_sequence ⇒ emit_counts` enforced **per merchant**.
* [ ] Priors country set is a **subset** of candidate countries (no extras/dupes).
* [ ] Counts country set equals candidates; Sequence countries ⊆ counts and lengths equal `countᵢ`.
* [ ] Sequence rows per country equal `countᵢ` (from counts); no countries outside counts.
* [ ] Inter-country order authority remains solely the candidate set; sequence is within-country only.
* [ ] Streaming, column-projected implementation; O(rows); fail-fast on first breach.

---

# 8) Streaming Algorithms (How to Validate Without Bottlenecks)

## 8.1 Principles (binding)

* **Projection-only:** read only the columns each check actually needs.
* **Single pass per dataset / merchant:** O(rows) time; O(C) memory per merchant (C = candidate countries; O(N) only for sequence per country).
* **Fail-fast:** first breach stops further work (merchant-scoped or run-scoped as applicable).
* **Deterministic:** fixed merchant iteration order; locale-independent comparisons; no timestamps/RNG.
* **Read-only:** never mutates producer tables; no path literals—only dataset IDs and column names.

---

## 8.2 Reader interface & grouping

Define a minimal reader API the validator uses everywhere:

```
ITER open_iter(dataset_id, parameter_hash, columns: List[str], order: Optional[List[str]])
  // Returns an iterator of rows with only 'columns'. If 'order' is supplied and supported,
  // rows are yielded in that logical order; otherwise unspecified order.

ITER group_by(iter, key_cols: List[str])
  // Returns (key_tuple, row_iter) groups in non-decreasing key order if the input is ordered by key_cols.
  // If input arrives in chunks, group_by MUST stitch groups across chunk boundaries without materializing
  // the entire dataset (bounded per-key buffering).
```

**Merchant iteration order:** ascending `merchant_id` (numeric/ASCII) for reproducible logs and bundle bytes.

---

## 8.3 Shared building blocks

### 8.3.1 Candidate country set (per merchant)

```
PROC build_candidate_country_set():
  it := open_iter("s3_candidate_set", run_args.parameter_hash,
                  ["merchant_id","country_iso","candidate_rank","is_home"],
                  order=["merchant_id","candidate_rank","country_iso"])
  for (m), rows in group_by(it, ["merchant_id"]):
      // While validating candidates (see §6.2), accumulate both:
      cand_set[m] := { row.country_iso for row in rows }
      // rank_info gathered inline in §6.2 to avoid a second pass
  RETURN cand_set
```

### 8.3.2 S2 N map (already built at start)

`N_map : merchant_id → N` for Σ counts checks.

---

## 8.4 Candidate-set streaming (authority + cache)

Use the §6 algorithm to validate uniqueness/contiguity/home\@0; **while streaming**, build:

* `cand_set[m] : Set[country_iso]` for cross-lane checks.
* Optional `country_count[m] = |cand_set[m]|` for priors/counts equality.

**Sanity:** ensure `min_rank == 0` and `|seen_ranks| == max_rank − min_rank + 1` at merchant flush.

---

## 8.5 Priors streaming (when enabled)

**Columns:** `merchant_id, country_iso, base_weight_dp, dp`

```
PROC v_check_priors(cand_set, priors_cfg):
  it := open_iter("s3_base_weight_priors", run_args.parameter_hash,
                  ["merchant_id","country_iso","base_weight_dp","dp"],
                  order=["merchant_id","country_iso"])
  for (m), rows in group_by(it, ["merchant_id"]):
      need := cand_set[m]       // expected countries from candidates
      seen := empty set
      for row in rows:
          if row.country_iso not in need:
             FAIL("PRIORS-EXTRA-COUNTRY", merchant=m, iso=row.country_iso)
          if !is_fixed_dp_score(row.base_weight_dp, priors_cfg.dp):
             FAIL("PRIORS-DP-VIOL", merchant=m, iso=row.country_iso)
          if row.dp != priors_cfg.dp:
             FAIL("PRIORS-DP-VIOL", merchant=m, iso=row.country_iso)
          insert(row.country_iso, seen)
      // completeness not required for priors; subset allowed (no extras, no dupes)
```

**Fixed-dp parser (deterministic)**

```
bool is_fixed_dp_score(s, dp):
  // Allowed: [0-9]* '.' [0-9]{dp}  OR  [0-9]+ if dp==0
  // No sign, no exponent, ASCII digits only.
  // Leading zeros allowed; exact dp trailing zeros when dp>0.
```

---

## 8.6 Counts streaming (when enabled)

**Columns:** `merchant_id, country_iso, count, residual_rank`

```
PROC v_check_counts(cand_set, N_map, bounds?):
  it := open_iter("s3_integerised_counts", run_args.parameter_hash,
                  ["merchant_id","country_iso","count","residual_rank"],
                  order=["merchant_id","country_iso"])
  for (m), rows in group_by(it, ["merchant_id"]):
      need := cand_set[m]
      seen_iso   := empty set
      seen_resid := empty set
      sum := 0
      for row in rows:
          if row.country_iso not in need:
             FAIL("COUNTS-EXTRA-COUNTRY", merchant=m, iso=row.country_iso)
          if row.country_iso in seen_iso:
             FAIL("COUNTS-DUPE-COUNTRY", merchant=m, iso=row.country_iso)
          insert(row.country_iso, seen_iso)

          if !is_int(row.count) or row.count < 0:
             FAIL("COUNTS-NONNEG-INT", merchant=m, iso=row.country_iso, value=row.count)
          sum += row.count

          if row.residual_rank in seen_resid:
             FAIL("COUNTS-RESID-DUPE", merchant=m, resid=row.residual_rank)
          insert(row.residual_rank, seen_resid)

          if bounds? has (m,row.country_iso):
             lo,hi := bounds?[m,row.country_iso]
             if row.count < lo or row.count > hi:
                FAIL("BOUNDS-VIOL", merchant=m, iso=row.country_iso, count=row.count, lo=lo, hi=hi)

      if size(seen_iso) != size(need):
         FAIL("COUNTS-MISSING-COUNTRY", merchant=m)
      if sum != N_map[m]:
         FAIL("COUNTS-SUM-NEQ-N", merchant=m, expected=N_map[m], observed=sum)

      // residual contiguity 1..|need|
      if size(seen_resid) != size(need) or min(seen_resid) != 1 or max(seen_resid) != size(need):
         FAIL("COUNTS-RESID-GAP", merchant=m)
```

---

## 8.7 Sequence streaming (when enabled; requires counts)

**Columns:** `merchant_id, country_iso, site_order, site_id?`

```
PROC v_check_sequence(counts_index):
  it := open_iter("s3_site_sequence", run_args.parameter_hash,
                  ["merchant_id","country_iso","site_order","site_id"],
                  order=["merchant_id","country_iso","site_order"])
  for (m, iso), rows in group_by(it, ["merchant_id","country_iso"]):
      if (m, iso) not in counts_index:
         FAIL("SEQ-COUNTRY-NOT-IN-COUNTS", merchant=m, iso=iso)

      need_len := counts_index[(m, iso)]
      seen_len := 0
      seen_ids := empty set

      for row in rows:
          expected := seen_len + 1
          if row.site_order != expected:
             FAIL("SEQ-GAP", merchant=m, iso=iso, expected=expected, observed=row.site_order)
          seen_len = row.site_order

          if row.site_id != NULL:
             if !is_zero_padded_6(row.site_id):
                FAIL("SEQ-ID-FORMAT", merchant=m, iso=iso, id=row.site_id)
             if row.site_id in seen_ids:
                FAIL("SEQ-ID-DUPE", merchant=m, iso=iso, id=row.site_id)
             insert(row.site_id, seen_ids)

      if seen_len != need_len:
         FAIL("SEQ-LENGTH-NEQ-COUNT", merchant=m, iso=iso,
              expected=need_len, observed=seen_len)
```

**Authority note:** sequence checks never infer cross-country order; they operate strictly inside `(merchant,country)`.

---

## 8.8 Cross-lane streaming ties (per merchant)

Reuse the §6 artifacts to avoid extra scans:

* **Priors:** test membership in `cand_set[m]`.
* **Counts:** as above (also populates `count_i`).
* **Sequence:** require `(m,iso) ∈ count_i` and compare length to `count_i[(m,iso)]`.

---

## 8.9 Memory budget & batching

* **Working sets per merchant:**
  candidates: `seen_countries`, `seen_ranks` · priors: `seen` · counts: `seen_iso`, `seen_resid`, `sum` · sequence: `seen_len`, optional `seen_ids`.
* **Batching:** if the reader supports chunking, pass `batch_rows` (20k–100k). **Groups may span chunks**—`group_by` must stitch seamlessly without materializing full datasets.

---

## 8.10 Deterministic numeric/string comparisons

* **Priors decimals:** ASCII digits only; decimal point `.`; exactly `dp` fractional digits when `dp>0`; no exponent/signed formats; reject whitespace.
* **IDs/codes:** compare as ASCII byte strings; no locale collation.
* **Ranks/counts:** compare as integers (no float coercions).

---

## 8.11 Zero-row merchants & lanes

* If a lane is toggled **on** but yields **zero rows**, it is valid **only** if cross-lane constraints make it logically empty (e.g., sequence for `count_i=0`).
* Counts: zero total rows with `N_map[m] > 0` ⇒ **FAIL** (`COUNTS-MISSING-COUNTRY` and/or `COUNTS-SUM-NEQ-N`).
* Priors: zero rows are **allowed** (subset policy); ensure no extras or dupes if present.

---

## 8.12 Early exits & error routing

* **Run-scoped** structural errors from §5 abort the validation (e.g., mixed manifest).
* **Merchant-scoped dataset errors** in this section produce the single canonical failure record and stop further checks for the run.
* Always stop at the first deterministic error to save I/O.

---

## 8.13 Acceptance checklist (for this section)

* [ ] All loops are **single-pass streaming** with column projection and constant-time checks.
* [ ] Merchant iteration is deterministic; `group_by` stitches across chunks; no full materialization.
* [ ] Per-lane algorithms match §6 contracts and §7 cross-lane rules.
* [ ] Numeric parsing is locale-independent; comparisons are exact.
* [ ] Memory bounded per merchant; batch-friendly; fail-fast enforced.

---

# 9) Performance Model & Knobs (Practical, Conservative)

## 9.1 Goals

* Keep validation **O(rows)** with **bounded memory** per worker.
* Be robust to **I/O-bound** and **sequence-heavy** slices.
* Provide defaults that run on a modest laptop and scale on a workstation—**without changing bytes**.

---

## 9.2 What typically dominates time

1. **I/O**: scanning large partitions; opening many small fragments.
2. **Sequence lane** (if enabled): per-country iteration of `site_order` (rows scale with `N`).
3. **Per-merchant setup**: iterator open/close and small set operations.
4. **Local ordering** (only if the reader cannot deliver `order=[…]`): minimal in-memory sort **per merchant**.

*Priors decimal parsing and rank/contiguity checks are CPU-light compared to I/O.*

---

## 9.3 Knob inventory (defaults & safe ranges)

All knobs are **deterministic**—changing them never changes PASS/FAIL or bytes.

| Knob               | Default (safe)           | Safe Range    | Effect & Guidance                                                                                     |
| ------------------ | ------------------------ | ------------- | ----------------------------------------------------------------------------------------------------- |
| `N_WORKERS`        | `min(physical_cores, 4)` | `1…16`        | Parallelism **across merchants only**. Increase if CPU underused and memory allows.                   |
| `batch_rows`       | `20_000`                 | `10k…100k`    | Chunk size for readers that stream; amortizes open/seek costs; larger helps I/O-bound runs.           |
| `mem_watermark`    | `256 MB / worker`        | `128…1024 MB` | Soft cap per worker; lower if host swaps; raise for sequence-heavy slices.                            |
| `fast_mode`        | `false`                  | `bool`        | If `true`: run **structural/lineage/keys** only, still enforce lane legality; **full mode** runs all. |
| `open_concurrency` | `N_WORKERS`              | `1…N_WORKERS` | Cap simultaneous iterator opens; lower on slow disks / cloud object stores.                           |
| `prefetch_next`    | `true`                   | `bool`        | Allow a worker to pre-open the next merchant’s iterators when memory permits.                         |

> If a reader does **not** support `order=[…]`, fall back to **per-merchant local sort** on the minimal key set and ensure the sorter stays **under `mem_watermark`** (spill/merge if needed).

---

## 9.4 Memory sizing (conservative heuristics)

Per worker, the working set is dominated by **sets & maps** per merchant:

* Candidates: `seen_countries`, `seen_ranks` → ≈ `C × small`
* Priors: `seen` → ≈ `C`
* Counts: `seen_iso`, `seen_resid`, `count_i` → ≈ `3C`
* Sequence: per `(merchant,country)` `seen_len` + optional `seen_ids` → worst-case ∝ `count_i`

**Rule of thumb**

```
bytes_worker ≈ overhead_fixed
             + (C × small)
             + (Σ per-country count_i × tiny)  // only if site_id checking
```

Start with `mem_watermark = 256 MB/worker`. If the host swaps or sequence is large, either:

* **Reduce `N_WORKERS` by 25–50%**, or
* **Raise `mem_watermark`** (if RAM allows), and/or
* **Increase `batch_rows`** to reduce fragment churn.

---

## 9.5 Throughput model (back-of-envelope)

Let:

* `R` = total rows scanned across present datasets
* `p` = `N_WORKERS` (across merchants)
* `t_io` = time/row to read+decode (dominant)
* `t_cpu` = time/row to check (small)
* `α` = iterator open/close overhead per merchant

**Approx time**

```
T ≈ α·(#merchants)/p  +  (R/p)·(t_io + t_cpu)
```

If `T` does not scale with `p`, the run is **I/O-bound**—tune `batch_rows`, `open_concurrency`, and prefetch.

---

## 9.6 When to prefer fewer workers

* Spinning rust or saturated network filesystem.
* Many small files per merchant (open/seek dominating).
* Cloud object storage with throttling.
  Start at `N_WORKERS=2–4`, observe, then scale carefully.

---

## 9.7 When to prefer more workers

* NVMe/SSD with headroom; CPU <40% and disk not saturated.
* Large `candidate_set` but modest sequence.
  Scale `N_WORKERS` toward 8–12, watching RAM and I/O.

---

## 9.8 Reader fallbacks & guards

* **No projection?** If the reader can’t project columns, keep `N_WORKERS` conservative (I/O rises).
* **No ordering?** Do a **per-merchant local sort** on the minimal key set (e.g., `(merchant_id, candidate_rank, country_iso)`); the sorter must **respect `mem_watermark`** (spill/merge if needed).
* **Fragment storms:** If opening thousands of fragments per merchant, cap `open_concurrency` and raise `batch_rows`.

---

## 9.9 Failure-mode shortcuts (save time)

* **Fail-fast**: on first structural/lineage breach, abort the run.
* **Per-merchant early exit**: on first lane breach for a merchant, stop further lanes for that merchant and surface the failure.
* **Skip-lane I/O**: if a lane is disabled by toggles, never open its dataset.

---

## 9.10 Operational counters (to guide tuning)

Log these (INFO), no payloads:

* `merchants_total`, `merchants_validated`, `merchants_failed`
* `rows_scanned_candidate_set`, `rows_scanned_base_weight_priors`, `rows_scanned_integerised_counts`, `rows_scanned_site_sequence`
* `avg_open_ms`, `avg_iter_ms`, `avg_emit_ms` (bundle)
* `io_wait_ratio` (if available)
* `max_worker_resident_bytes`
* `fragment_opens_total`

**Interpretation**

* High `io_wait_ratio` + low CPU → I/O-bound; adjust `batch_rows`/`open_concurrency`.
* Many fragment opens per merchant → raise `batch_rows`, reduce `N_WORKERS`.
* Memory near watermark → reduce `N_WORKERS` or disable prefetch.

---

## 9.11 Presets (conservative starting points)

**Laptop (4–8 cores, 16–32 GB RAM)**

* `N_WORKERS=4` · `batch_rows=20_000` · `mem_watermark=256 MB` · `open_concurrency=4` · `prefetch_next=true`

**Workstation (8–32 cores, 64–256 GB RAM)**

* `N_WORKERS=min(cores,12)` · `batch_rows=50_000` · `mem_watermark=512 MB` · `open_concurrency=8` · `prefetch_next=true`

**Sequence-heavy slice**

* Reduce `N_WORKERS` by 25–50% or raise `mem_watermark` to 512–1024 MB.
* Keep `batch_rows ≥ 50_000` if the reader supports chunking.

---

## 9.12 Acceptance checklist (for this section)

* [ ] Knobs and defaults are conservative and deterministic (no byte changes).
* [ ] Clear guidance for **I/O-bound** vs **CPU-bound** symptoms.
* [ ] Safe fallbacks when projection/order aren’t available.
* [ ] Memory sizing and sequence-heavy behavior addressed.
* [ ] Early-exit rules to avoid wasted scans.
* [ ] Practical presets for laptop/workstation with room to scale.

---

# 10) Validator DAG (V-series)

## 10.1 One-screen DAG (human)

Legend: **\[■] required** · **\[◇] optional** (gated by toggles) · **—** required edge · **···** optional edge · **⟂** fail-fast stop

```
[■ V0  Open handles (dict/schemas/BOM, N_map)] 
        |
        v
[■ V1  Discover datasets @ parameter_hash] 
        |
        v
[■ V2  Structural & lineage checks (run-wide)]
        |
        v
[■ V3  Candidate-set checks]  --build-->  cand_set[m]
        | 
        |··· if priors enabled
        v
[◇ V4  Priors checks]        --use-->    cand_set[m]
        |
        |··· if counts enabled
        v
[◇ V5  Counts checks]        --build-->  count_i[(m,iso)], Σ=N
        |
        |··· if sequence enabled (and counts enabled)
        v
[◇ V6  Sequence checks]      --use-->    count_i[(m,iso)]
        |
        v
[■ V7  Cross-lane legality & authority]
        |
        v
[■ V8  Build bundle (summary/failure)]
        |
        v
[■ V9  Atomic publish (PASS: +_passed.flag | FAIL: +failures.jsonl)]
```

Fail-fast: any node may emit the single canonical failure → **⟂ stop** (no nodes after V8 run).

---

## 10.2 Node registry (stable IDs, purposes, surfaces)

| ID | Name                            | Type     | Optional | Purpose (one-liner)                                                   | Surface / Kernel     |
|----|---------------------------------|----------|----------|-----------------------------------------------------------------------|----------------------|
| V0 | Open handles                    | run-wide | No       | Open dictionary/schemas/BOM; build `N_map`.                           | (host shims)         |
| V1 | Discover datasets               | run-wide | No       | Presence vs toggles for the 4 datasets.                               | internal             |
| V2 | Structural & lineage            | run-wide | No       | Schema/partition; embed=path; **manifest equality**.                  | `v_check_structural` |
| V3 | Candidate-set checks            | per-m    | No       | Uniqueness, contiguity 0..K−1, home\@0.                               | `v_check_candidates` |
| V4 | Priors checks                   | per-m    | Yes      | **Subset of candidates;** fixed-dp `base_weight_dp` with dp-constant. | `v_check_priors`     |
| V5 | Counts checks                   | per-m    | Yes      | One-to-one; integers; **Σ=N**; residual totality.                     | `v_check_counts`     |
| V6 | Sequence checks                 | per-m    | Yes      | Per-country 1..countᵢ; IDs; uses counts map.                          | `v_check_sequence`   |
| V7 | Cross-lane legality & authority | per-m    | No       | Lane legality; country-set equality; authority.                       | `v_check_crosslane`  |
| V8 | Build bundle                    | run-wide | No       | Compose canonical `summary.json`/failure.                             | `v_build_bundle`     |
| V9 | Atomic publish                  | run-wide | No       | Write PASS/FAIL artifacts atomically.                                 | (host shim)          |

*Types:* “run-wide” scans across datasets; “per-m” streams grouped by merchant in deterministic order.

---

## 10.3 Edge list with guards (authoritative)

**Required spine**
`V0 → V1 → V2 → V3 → V7 → V8 → V9`

**Optional lanes (gated by toggles)**
`V3 → V4` *(if `emit_priors`)*
`V3 → V5` *(if `emit_counts`)*
`V5 → V6` *(if `emit_sequence` **and** `emit_counts`)*

**Cross-lane join to V7**
`{ last of V3 / V4? / V5? / V6? } → V7`

**Guards**

* **Presence/toggle legality** (e.g., `emit_sequence ∧ ¬emit_counts`) is enforced in **V1**.
* **Manifest/lineage equality** is enforced in **V2**.
* **V6** is reachable **only** if **V5** was taken.

**V8** chooses **PASS** (no failure) vs **FAIL** (first failure).

---

## 10.4 Prohibited edges (must not exist)

* Any bypass of V2 (structural/lineage) to V3+.
* V6 without V5; V4/V5/V6 when their lanes are disabled.
* Publishing `_passed.flag` when any failure was recorded.
* Cross-merchant edges that would require global state beyond tallies (per-merchant checks are independent).

---

## 10.5 Data contracts on edges (what flows)

* **V0 → V1:** `{ dict_handle, schema_anchors, BOM(priors_cfg?, bounds?), N_map }`
* **V1 → V2:** `{ presence_matrix, dataset_handles@parameter_hash }`
* **V2 → V3:** `{ validated_handles, lineage_ok=true }`
* **V3 → V4:** `{ cand_set[m] }`
* **V3 → V5:** `{ cand_set[m], N_map }`
* **V5 → V6:** `{ count_i[(m,iso)] }`
* **→ V7 (from last lane):** `{ cand_set[m], count_i? , lane_presence_flags }`
* **V7 → V8:** `{ tallies: { datasets_present, row_counts, merchants: {total,validated,failed} }, maybe_failure }`
* **V8 → V9:** `{ bundle_members (summary, maybe failure), pass_flag? }`

All payloads are **values/iterators**, never paths.

---

## 10.6 Single permitted linearisation (normalized)

Per run (conceptual):

```
V0 → V1 → V2 → V3 → [V4?] → [V5?] → [V6?] → V7 → V8 → V9
```

Per merchant (within V3–V7), checks are serial in that same order; merchants execute in a deterministic iteration order; across-merchant parallelism is allowed.

---

## 10.7 Early-exit and failure routing

* **Run-scoped** failures in V1/V2 (e.g., presence/toggles, schema/partition, manifest breaches) abort the run → V8/V9 with FAIL.
* **Merchant-scoped** failures in V3–V7 stop checks immediately and route to V8/V9 with the single canonical failure record.
* No additional errors are collected; **fail-fast** saves I/O.

---

## 10.8 Determinism guarantees (DAG level)

* Fixed node order; optional nodes controlled only by toggles and presence.
* Merchant iteration order is deterministic; file order is non-authoritative (writer sorts only).
* V8 builds **canonical JSON**; V9 performs **atomic publish**; reruns produce identical PASS bytes or the same single FAIL.

---

## 10.9 Acceptance checklist (for this section)

* [ ] Node registry V0..V9 defined with stable IDs and purposes.
* [ ] Optional lanes mapped cleanly to toggles; sequence requires counts.
* [ ] Edge list + guards + prohibited edges are explicit.
* [ ] Data contracts between nodes are values/iterators only.
* [ ] Single normalized topological order stated; early-exit rules defined.
* [ ] Determinism and idempotent publish guaranteed at DAG level.

---

# 11) Concurrency & Scheduling (Validator)

## 11.1 Goals (binding)

* **Deterministic & reproducible** execution: same inputs ⇒ same PASS/FAIL + bytes.
* **Read-only coexistence** with L2: never block producers; never read torn data.
* **Throughput without drift**: use workers only to increase speed—never to change results.

---

## 11.2 Execution model

* **Across-merchant parallelism:** Yes. Submit merchants to a worker pool; each worker processes one merchant at a time through V3→V7.
* **Within-merchant serialism:** Candidate → Priors? → Counts? → Sequence? → Cross-lane, all **serial** for the same merchant.
* **Run-wide nodes (V0/V1/V2/V8/V9):** Executed by the controller thread (single-shot per run).

---

## 11.3 Deterministic merchant ordering

* **Order:** ascending `merchant_id` (ASCII/bytewise).
* **Rationale:** stable logs and byte-identical `summary.json` on reruns, independent of worker scheduling.
* The controller enqueues merchants in that order; workers pull from a **bounded FIFO**.

---

## 11.4 Single-writer coexistence (read-only validator)

* L3 is read-only; it never opens producer writers.
* **Validate-during-run mode:** L3 only opens iterators for **finalised** publisher outputs (atomic rename completed).
* If a dataset for the merchant is not final, **skip** it now and re-queue later (or run post-L2 to avoid skip loops).

---

## 11.5 Worker pool & backpressure

* **Pool size:** `N_WORKERS` (see §9 defaults & ranges).
* **Queue:** bounded; producer thread blocks when the queue is full (deterministic backpressure).
* **Open concurrency:** cap simultaneous `open_iter` calls to avoid fragment storms; default `open_concurrency = N_WORKERS`.
* **Prefetch:** if `prefetch_next=true`, a worker may open the next merchant’s iterators **only** when under `mem_watermark`.

---

## 11.6 Group-by and chunk stitching (crucial)

* When the reader returns chunked iterators, `group_by` **must stitch** groups across chunk boundaries without materializing entire datasets.
* **Invariant:** per-merchant group streams are contiguous to the consumer; counters/sets never see split groups.

---

## 11.7 Failure routing & early exits

* **Run-scoped** failure in V1/V2: stop pool, jump to V8/V9 (FAIL).
* **Merchant-scoped** failure in V3–V7: stop that merchant immediately; surface failure; controller proceeds to V8/V9 (FAIL).
* **Fail-fast** always: do not continue scanning once a deterministic breach is observed.

---

## 11.8 Memory discipline

* **Per-worker bound:** keep resident sets/maps ≤ `mem_watermark`; sequence-heavy runs may require fewer workers.
* **Local sorts:** if the reader cannot respect `order=[…]`, per-merchant local sorts **must** spill/merge to remain under the watermark.
* **No cross-merchant caching.** All maps are per merchant and discarded at flush.

---

## 11.9 Logging (operational, not evidence)

* Log `MERCHANT_START`, `MERCHANT_DONE{OK|FAIL}`, and counters per dataset (`rows_scanned_*`) at INFO.
* Never log PII/payloads or dataset paths; include lineage tuple and knob values once at run start.

---

## 11.10 Idempotence and retry safety

* Re-running the same `{parameter_hash, manifest_fingerprint, toggles}` is **safe**: V8 generates identical PASS bytes or the same single FAIL.
* If the process crashes mid-run, the controller **replays** the run; no partial bundles are considered valid (atomic publish only).

---

## 11.11 Acceptance checklist (for this section)

* [ ] Across-merchant parallelism; within-merchant serialism preserved.
* [ ] Merchant dispatch order is deterministic; queue is bounded (backpressure).
* [ ] Validate-during-run reads only finalised outputs; no read/write races with L2.
* [ ] Group-by stitches across chunk boundaries; no full materialization.
* [ ] Memory under `mem_watermark`; local sorts spill/merge if needed.
* [ ] Fail-fast routing to V8/V9; idempotent re-runs guaranteed.

---

# 12) Host Interfaces (Read-Only Shims)

## 12.1 Intent (binding)

Provide a small, stable API that L3 uses to:

* resolve dataset contracts (dictionary + schemas),
* stream rows with **projection** and optional **logical order**,
* discover merchants and dataset presence for a `parameter_hash`,
* read auxiliary facts (`priors_cfg`, `bounds?`, `N_map`),
* publish the validator bundle **atomically**, and
* log operational events.

No other host/system calls are permitted.

---

## 12.2 Design principles

* **Read-only:** never creates/modifies producer data.
* **Path-agnostic:** returns handles/iterators and schema objects; no filesystem paths.
* **Deterministic:** same inputs → same outputs; no timestamps.
* **Thread-safe:** concurrent calls are safe; results are immutable or copied per call.
* **Minimal:** only what L3 needs to validate bytes efficiently.

---

## 12.3 Type aliases (for signatures)

```
Hex64        := string    // lowercase hex
ISO2         := string    // ASCII alpha-2
SchemaAnchor := opaque    // JSON-Schema object/handle
Iter         := opaque    // row iterator with .next() and .close()
DictHandle   := opaque
BomValues    := { priors_cfg?: { dp:int, ... }, bounds?: Map<(merchant_id,ISO2)→{min:int?, max:int?}> }
NMap         := Map<merchant_id → int>  // from S2 nb_final
DatasetID    := "s3_candidate_set" | "s3_base_weight_priors" | "s3_integerised_counts" | "s3_site_sequence"
```

---

## 12.4 Shim specifications (signatures & contracts)

### 12.4.1 Dictionary / schemas

```
PROC DICT_OPEN() -> DictHandle

PROC DICT_RESOLVE(dict: DictHandle, dataset_id: DatasetID)
  -> { schema: SchemaAnchor,
       partition_keys: List<string>,        // must be ["parameter_hash"]
       writer_sort: List<string> }          // e.g., ["merchant_id","candidate_rank","country_iso"]

PROC DATASET_PRESENCE_MATRIX(dict: DictHandle, parameter_hash: Hex64)
  -> { candidate_set: bool,
       base_weight_priors: bool,
       integerised_counts: bool,
       site_sequence: bool }
```

**Failures:** `DICT-OPEN-FAIL`, `DICT-RESOLVE-FAIL`, `PRESENCE-MATRIX-FAIL`.

---

### 12.4.2 Dataset readers (projection + optional logical order)

```
PROC OPEN_ITER(dataset_id: DatasetID,
               parameter_hash: Hex64,
               columns: List<string>,
               order?: List<string>) -> Iter
  // Streams only 'columns'. If 'order' is supported and stable, rows are yielded in that order; else unspecified.

PROC ITER_GROUP_BY(it: Iter, key_cols: List[str])
  -> Iterator<(key_tuple, row_iter)>        // groups by key; must tolerate chunk boundaries
```

**Requirements**

* Projection is exact; no extra columns returned.
* If `order` is unsupported, caller falls back to minimal in-memory sort per merchant respecting **mem_watermark**.
* Iterators are **closeable** and may chunk by `batch_rows`; `ITER_GROUP_BY` must stitch groups across chunk boundaries.

**Failures:** `READER-OPEN-FAIL`, `READER-UNSUPPORTED-ORDER`, `READER-UNSUPPORTED-PROJECTION`.

---

### 12.4.3 Merchant & presence discovery

```
PROC DISCOVER_MERCHANTS(dict: DictHandle, parameter_hash: Hex64)
  -> List<merchant_id>                      // deterministic order (ascending ASCII)

PROC DATASET_PRESENCE_MATRIX(dict: DictHandle, parameter_hash: Hex64)
  -> { candidate_set: bool,
       base_weight_priors: bool,
       integerised_counts: bool,
       site_sequence: bool }
```

**Failures:** `DISCOVER-MERCHANTS-FAIL`, `PRESENCE-MATRIX-FAIL`.

---

### 12.4.4 Auxiliary facts (read-only)

```
PROC OPEN_BOM_VALUES() -> BomValues        // priors_cfg? and bounds? to PARSE/VERIFY, not compute
PROC GET_S2_N_MAP(parameter_hash: Hex64) -> NMap    // authoritative Σ counts
```

**Failures:** `BOM-OPEN-FAIL`, `S2-NMAP-FAIL`.

---

### 12.4.5 Finalisation status (validate-during-run)

```
PROC LIST_FINALISED_MERCHANTS(dataset_ids: Set<DatasetID>,
                               parameter_hash: Hex64)
  -> Set<merchant_id>                       // merchants whose required datasets are final
```

**Failure:** `FINAL-STATUS-FAIL`.
**Note:** selector only; L3 never polls producer locks or writes.

---

### 12.4.6 Atomic publish of validator bundle (L3-owned area)

```
PROC PUBLISH_VALIDATION_BUNDLE(parameter_hash: Hex64,
                               manifest_fingerprint: Hex64,
                               files: Map<string → bytes>)
  -> void
  // tmp write → fsync → rename; refuse mixed fingerprints; refuse partial overwrites.
```

**Failures:** `BUNDLE-PUBLISH-FAIL`, `BUNDLE-FINGERPRINT-MISMATCH`, `BUNDLE-PARTIAL-REFUSED`.

---

### 12.4.7 Operational logging (non-evidence)

```
PROC HOST_LOG(level: "INFO"|"WARN"|"ERROR",
              event: string,
              kv?: Map<string → string|int|bool>) -> void
```

Constraints: no PII, no row payloads, no dataset paths; include lineage tuple and counters only.

---

## 12.5 Determinism & thread-safety (binding)

* All shims return **immutable** values for the run or clearly documented snapshots.
* Repeated calls with the same arguments return byte-identical results or stable deterministic iterators.
* Any internal caching must **not** alter the exposed sequence/content to L3.

---

## 12.6 Error model (stable, minimal)

Every failure returns a stable code and structured details:

```
{ code: "<STABLE_CODE>",
  where: "<SHIM_NAME>",
  args: { ... },           // normalized argument echo
  details?: { ... } }
```

**Run behavior**

* **V0/V1/V2 stage**: treat as run-scoped failure; publish FAIL with the first error.
* **Per-merchant stage**: treat as merchant-scoped failure; publish FAIL with that error.

---

## 12.7 Usage map (where each shim is called)

| Shim                         | Node(s)  | Purpose                                    |
| ---------------------------- | -------- | ------------------------------------------ |
| `DICT_OPEN`, `DICT_RESOLVE`  | V0,V1,V2 | Resolve schemas, partitions, writer sorts  |
| `DATASET_PRESENCE_MATRIX`    | V1       | Presence vs toggles                        |
| `DISCOVER_MERCHANTS`         | V0,V3    | Merchant domain (deterministic order)      |
| `OPEN_BOM_VALUES`            | V0       | Parse/verify dp & bounds (not compute)     |
| `GET_S2_N_MAP`               | V0       | Build `N_map` for Σ counts                 |
| `OPEN_ITER`, `ITER_GROUP_BY` | V2–V6    | Streaming row access with projection/order |
| `LIST_FINALISED_MERCHANTS`   | V1/V3    | Validate-during-run merchant selection     |
| `HOST_LOG`                   | V0–V9    | Operational visibility                     |
| `PUBLISH_VALIDATION_BUNDLE`  | V9       | Atomic PASS/FAIL artifacts                 |

---

## 12.8 Forbidden behavior (must never happen)

* Returning filesystem paths or requiring callers to concatenate paths.
* Emitting timestamps or host-specific metadata that could change bundle bytes.
* Mutating producer tables or their metadata.
* Exposing locale-dependent comparisons (collations) to L3 logic.
* Leaking storage layout details (fragment filenames, offsets).

---

## 12.9 Acceptance checklist (for this section)

* [ ] All shims are read-only, deterministic, path-agnostic, and thread-safe.
* [ ] Signatures provide exactly what L3 needs (no less, no more).
* [ ] Atomic publish is defined for the validator bundle only; producer data untouched.
* [ ] Finalisation shim supports validate-during-run without blocking L2.
* [ ] Error model is stable; usage map covers all V-nodes.

---

# 13) Validator Surfaces (Kernels)

## 13.1 Common types & return shape

```
Hex64        := string            // lowercase hex
MerchantID   := string            // ASCII
ISO2         := string            // ASCII alpha-2
DatasetID    := "s3_candidate_set" | "s3_base_weight_priors" | "s3_integerised_counts" | "s3_site_sequence"

RunArgs := {
  parameter_hash: Hex64,
  manifest_fingerprint: Hex64,
  toggles: { emit_priors: bool, emit_counts: bool, emit_sequence: bool }
}

BomValues := { priors_cfg?: { dp:int, ... },
               bounds?: Map<(MerchantID,ISO2)→{min?:int, max?:int}> }

DictCtx := { dict_handle, schema_handles }                  // dictionary + schema anchors
ReadCtx := { open_iter, iter_group_by }                     // reader functions bound to parameter_hash
AuxCtx  := { N_map: Map<MerchantID→int>, bom: BomValues }   // S2 N map + BOM values

OK   := { ok: true }
Fail := { ok: false,
          code: string,
          scope: "RUN"|"MERCHANT"|"DATASET",
          dataset_id?: DatasetID,
          merchant_id?: MerchantID,
          details?: Map }
```

**Fail-fast:** each kernel returns **Fail** on the first breach; callers must stop and surface this failure.

---

## 13.2 V2 — Structural & lineage (run-wide)

```
PROC v_check_structural(run: RunArgs, dict: DictCtx, read: ReadCtx)
  -> OK | Fail
```

**Purpose.** Enforce presence vs toggles; resolve schema anchors & partition template; verify **parameter-scoped only**; stream lineage columns and assert **embed = path** and **dataset-scoped manifest equality**.

**Columns.** `parameter_hash, manifest_fingerprint` (all present datasets).

**Failure codes.**
`DATASET-PRESENCE-MISMATCH`, `DICT-RESOLVE-FAIL`, `PARTITION-TEMPLATE-MISMATCH`,
`EMBED-PATH-MISMATCH`, `MIXED-MANIFEST`.

**Complexity.** O(rows) total; O(1) memory; no per-merchant grouping.

---

## 13.3 V3 — Candidates (per merchant)

```
PROC v_check_candidates(run: RunArgs, dict: DictCtx, read: ReadCtx, m: MerchantID)
  -> { ok: true, cand_set: Set<ISO2>, K: int } | Fail
```

**Purpose.** Per merchant: uniqueness on `(country_iso)` and on `(candidate_rank)`; **contiguity 0..K−1**; **home\@0 exactly once**; streaming writer-sort sanity.

**Columns.** `merchant_id, country_iso, candidate_rank, is_home`.

**Outputs on OK.**
`cand_set` — exact candidate countries for `m` (for V4/V5/V6/V7).
`K` — number of candidate countries.

**Failure codes.**
`CAND-DUPE-ISO`, `CAND-DUPE-RANK`, `CAND-RANK-START-NEQ-0`, `CAND-RANK-GAP`,
`HOME-MISSING`, `HOME-DUPE`, `HOME-RANK-NEQ-0`, `DATASET-UNSORTED`.

**Complexity.** Single pass over `m`’s rows; memory O(K).

---

## 13.4 V4 — Priors (per merchant; optional)

```
PROC v_check_priors(run: RunArgs, dict: DictCtx, read: ReadCtx,
                    m: MerchantID, cand_set: Set<ISO2>, priors_cfg) -> OK | Fail
```

**Purpose.** Enforce **subset of candidates** (no extras/dupes) and **fixed-dp weights** on `base_weight_dp` with on-row **dp == `priors_cfg.dp`**; no renorm.

**Columns.** `merchant_id, country_iso, base_weight_dp, dp`.

**Failure codes.**
`PRIORS-EXTRA-COUNTRY`, `PRIORS-DP-VIOL`, `PRIORS-DUPE-COUNTRY`, `DATASET-UNSORTED`.

**Complexity.** Single pass; memory O(K).

---

## 13.5 V5 — Counts (per merchant; optional)

```
PROC v_check_counts(run: RunArgs, dict: DictCtx, read: ReadCtx,
                    m: MerchantID, cand_set: Set<ISO2>, N_map, bounds?)
  -> { ok: true, count_i: Map<ISO2→int> } | Fail
```

**Purpose.** Enforce **one-to-one** with candidates; **non-negative integers**; **Σ count = N_map\[m]**; `residual_rank` total & contiguous; optional bounds satisfied.

**Columns.** `merchant_id, country_iso, count, residual_rank`.

**Outputs on OK.**
`count_i` — per-country counts to be reused by V6 & V7.

**Failure codes.**
`COUNTS-EXTRA-COUNTRY`, `COUNTS-MISSING-COUNTRY`, `COUNTS-DUPE-COUNTRY`,
`COUNTS-NONNEG-INT`, `COUNTS-SUM-NEQ-N`, `COUNTS-RESID-DUPE`, `COUNTS-RESID-GAP`,
`BOUNDS-VIOL`, `DATASET-UNSORTED`.

**Complexity.** Single pass; memory O(K).

---

## 13.6 V6 — Sequence (per merchant; optional; requires counts)

```
PROC v_check_sequence(run: RunArgs, dict: DictCtx, read: ReadCtx,
                      m: MerchantID, count_i: Map<ISO2→int>) -> OK | Fail
```

**Purpose.** For each `(merchant,country)`, assert `site_order = 1..count_i[country]`; no gaps/dupes; optional 6-digit zero-padded `site_id` unique within country.

**Columns.** `merchant_id, country_iso, site_order, site_id?`.

**Failure codes.**
`SEQ-COUNTRY-NOT-IN-COUNTS`, `SEQ-GAP`, `SEQ-LENGTH-NEQ-COUNT`,
`SEQ-ID-FORMAT`, `SEQ-ID-DUPE`, `DATASET-UNSORTED`.

**Complexity.** Single pass grouped by `(merchant_id,country_iso)`; memory O(1) per country (+ set of seen IDs if present).

---

## 13.7 V7 — Cross-lane legality & authority (per merchant)

```
PROC v_check_crosslane(run: RunArgs,
                       m: MerchantID,
                       cand_set: Set<ISO2>,
                       count_i?: Map<ISO2→int>,
                       priors_present: bool,
                       counts_present: bool,
                       sequence_present: bool) -> OK | Fail
```

**Purpose.** Enforce **lane legality** and **country-set equality** across lanes; protect **order authorities**:

* `emit_sequence ⇒ emit_counts` (per merchant).
* If priors present: priors country set is a **subset** of candidate countries (no extras/dupes).
* If counts present: counts countries == candidates.
* If sequence present: sequence countries ⊆ counts and lengths equal `count_i`.
* No non-candidate dataset may encode inter-country order.

**Inputs.** Lane presence booleans per merchant, `cand_set`, and `count_i` when present.

**Failure codes.**
`SEQ-NO-COUNTS`, `PRIORS-EXTRA-COUNTRY`,
`COUNTS-EXTRA-COUNTRY`, `COUNTS-MISSING-COUNTRY`,
`SEQ-COUNTRY-NOT-IN-COUNTS`, `SEQ-LENGTH-NEQ-COUNT`,
`AUTH-ORDER-VIOLATION`.

**Complexity.** O(K) using the sets/maps already produced.

---

## 13.8 V8 — Build bundle (run-wide)

```
PROC v_build_bundle(run: RunArgs,
                    tallies: {
                      datasets_present: { candidate_set:bool, base_weight_priors:bool,
                                          integerised_counts:bool, site_sequence:bool },
                      row_counts: { candidate_set:int, base_weight_priors:int,
                                    integerised_counts:int, site_sequence:int },
                      merchants_total:int, merchants_validated:int, merchants_failed:int
                    },
                    maybe_failure: Fail | NULL) -> { files: Map<string→bytes>, pass: bool }
```

**Purpose.** Produce canonical `summary.json` and either `_passed.flag` (PASS) or `failures.jsonl` (FAIL) exactly as specified in §4.

**Determinism.** Sorted-key JSON; no timestamps; stable digest construction; identical bytes on rerun.

**Failure.** Kernel itself should not fail unless serialization errors occur; treat such errors as run-scoped bundle failures.

---

## 13.9 Column requests (for each kernel)

So implementers never guess, each kernel calls the reader with **exact** columns:

| Kernel             | Dataset            | Columns (projection)                                | Order hint                                       |
|--------------------|--------------------|-----------------------------------------------------|--------------------------------------------------|
| v_check_structural | all present        | `parameter_hash, manifest_fingerprint`              | none                                             |
| v_check_candidates | candidate_set      | `merchant_id, country_iso, candidate_rank, is_home` | `["merchant_id","candidate_rank","country_iso"]` |
| v_check_priors     | base_weight_priors | `merchant_id, country_iso, base_weight_dp, dp`      | `["merchant_id","country_iso"]`                  |
| v_check_counts     | integerised_counts | `merchant_id, country_iso, count, residual_rank`    | `["merchant_id","country_iso"]`                  |
| v_check_sequence   | site_sequence      | `merchant_id, country_iso, site_order, site_id?`    | `["merchant_id","country_iso","site_order"]`     |

If the reader cannot honor `order`, the kernel performs a **minimal local sort per merchant** on the listed keys within `mem_watermark`.

---

## 13.10 Determinism, purity, and stop-on-first-failure (binding)

* **Purity:** kernels never mutate producer datasets and never write validation artifacts.
* **Stop rule:** return **Fail** immediately on the first deterministic breach; caller routes to bundle FAIL.
* **No global hidden state:** only `cand_set`/`count_i` produced in prior kernels and passed explicitly.
* **Reproducible:** given the same inputs and tallies, kernels return identical outcomes.

---

## 13.11 Acceptance checklist (for this section)

* [ ] All kernels have explicit inputs/outputs, columns, orders, and failure codes.
* [ ] Per-merchant kernels are pure, streaming, and memory-bounded.
* [ ] Cross-lane kernel enforces legality and authority using prior outputs.
* [ ] Bundle builder yields canonical bytes and honors PASS/FAIL semantics.
* [ ] No hidden globals, no path literals, and deterministic stop-on-first-failure behavior.

---

# 14) Pseudocode Skeletons (Language-Agnostic)

## 14.0 Conventions used below

```
FAIL(code, scope, dataset_id?, merchant_id?, details?) -> Fail
OK() -> OK

nondecreasing(prev_key, key) -> bool
is_fixed_dp_score(s, dp:int) -> bool               // ASCII; '.'; exactly dp fractional digits; no exp/sign
is_zero_padded_6(s) -> bool                        // ^\d{6}$ ; leading zeros allowed
```

All iterators return **projected** columns only. `ITER_GROUP_BY` tolerates chunking and preserves input order when provided, otherwise minimally buffers **per key**. `ReadCtx.open_iter` is bound to the run’s `parameter_hash`.

---

## 14.1 V2 — Structural & Lineage (run-wide)

```
PROC v_check_structural(run: RunArgs, dict: DictCtx, read: ReadCtx) -> OK | Fail:
  // Presence vs toggles
  present_raw := DATASET_PRESENCE_MATRIX(dict.dict_handle, run.parameter_hash)
  present := {
    "s3_candidate_set":       present_raw.candidate_set,
    "s3_base_weight_priors":  present_raw.base_weight_priors,
    "s3_integerised_counts":  present_raw.integerised_counts,
    "s3_site_sequence":       present_raw.site_sequence
  }
  required := {
    "s3_candidate_set": true,
    "s3_base_weight_priors": run.toggles.emit_priors,
    "s3_integerised_counts": run.toggles.emit_counts,
    "s3_site_sequence": run.toggles.emit_sequence
  }
  if required["s3_site_sequence"] and not required["s3_integerised_counts"]:
    return FAIL("DATASET-PRESENCE-MISMATCH","RUN","s3_site_sequence",NULL,{"required":true,"present":false})

  // Resolve schema & template; enforce parameter-only partitioning
  for ds, must in required:
    has := present[ds]
    if  must and not has:  return FAIL("DATASET-PRESENCE-MISMATCH","RUN", ds, NULL, {"required":true,"present":false})
    if !must and     has:  return FAIL("DATASET-PRESENCE-MISMATCH","RUN", ds, NULL, {"required":false,"present":true})
    if has:
      r := DICT_RESOLVE(dict.dict_handle, ds)
      if r == NULL: return FAIL("DICT-RESOLVE-FAIL","RUN", ds, NULL, {})
      if r.partition_keys != ["parameter_hash"]:
         return FAIL("PARTITION-TEMPLATE-MISMATCH","RUN", ds, NULL, {"partition_keys":r.partition_keys})

  // Lineage streaming check (embed=path; dataset-scoped manifest equality)
  for ds, has in present:
    if not has: continue
    it := read.open_iter(ds, run.parameter_hash, ["parameter_hash","manifest_fingerprint"], order=NULL)
    while row := it.next():
      if row.parameter_hash != run.parameter_hash:
        return FAIL("EMBED-PATH-MISMATCH","DATASET", ds, NULL, {"got":row.parameter_hash})
      if row.manifest_fingerprint != run.manifest_fingerprint:
        return FAIL("MIXED-MANIFEST","DATASET", ds, NULL, {"got":row.manifest_fingerprint})
    it.close()

  return OK()
```

---

## 14.2 V3 — Candidates (per merchant)

```
PROC v_check_candidates(run: RunArgs, dict: DictCtx, read: ReadCtx, m: MerchantID)
  -> { ok:true, cand_set:Set<ISO2>, K:int } | Fail:

  it   := read.open_iter("s3_candidate_set",
                         run.parameter_hash,
                         ["merchant_id","country_iso","candidate_rank","is_home"],
                         order=["merchant_id","candidate_rank","country_iso"])
  rows := ITER_GROUP_BY(it, ["merchant_id"]).get(m)

  seen_iso := set(), seen_rank := set()
  min_rank := +INF, max_rank := -INF
  home_seen := false
  prev_key := NULL

  for row in rows:
    key := (row.merchant_id, row.candidate_rank, row.country_iso)
    if prev_key != NULL and not nondecreasing(prev_key, key):
      return FAIL("DATASET-UNSORTED","DATASET","s3_candidate_set", m)
    prev_key = key

    if row.country_iso in seen_iso:
      return FAIL("CAND-DUPE-ISO","MERCHANT","s3_candidate_set", m, {"iso":row.country_iso})
    insert(row.country_iso, seen_iso)

    if row.candidate_rank in seen_rank:
      return FAIL("CAND-DUPE-RANK","MERCHANT","s3_candidate_set", m, {"rank":row.candidate_rank})
    insert(row.candidate_rank, seen_rank)

    min_rank = MIN(min_rank, row.candidate_rank)
    max_rank = MAX(max_rank, row.candidate_rank)

    if row.is_home:
       if row.candidate_rank != 0:
         return FAIL("HOME-RANK-NEQ-0","MERCHANT","s3_candidate_set", m, {"rank":row.candidate_rank})
       if home_seen:
         return FAIL("HOME-DUPE","MERCHANT","s3_candidate_set", m)
       home_seen = true

  if SIZE(seen_rank) == 0: return FAIL("CAND-RANK-GAP","MERCHANT","s3_candidate_set", m)
  if min_rank != 0:        return FAIL("CAND-RANK-START-NEQ-0","MERCHANT","s3_candidate_set", m)
  if not home_seen:        return FAIL("HOME-MISSING","MERCHANT","s3_candidate_set", m)
  if SIZE(seen_rank) != (max_rank - 0 + 1):
     return FAIL("CAND-RANK-GAP","MERCHANT","s3_candidate_set", m)

  it.close()
  return { ok:true, cand_set: seen_iso, K: SIZE(seen_iso) }
```

---

## 14.3 V4 — Priors (per merchant; optional)

```
PROC v_check_priors(run: RunArgs, dict: DictCtx, read: ReadCtx,
                    m: MerchantID, cand_set:Set<ISO2>, priors_cfg) -> OK | Fail:

  if not run.toggles.emit_priors: return OK()

  it   := read.open_iter("s3_base_weight_priors",
                         run.parameter_hash,
                         ["merchant_id","country_iso","base_weight_dp","dp"],
                         order=["merchant_id","country_iso"])
  rows := ITER_GROUP_BY(it, ["merchant_id"]).get(m)

  seen := set()
  prev_key := NULL

  for row in rows:
    key := (row.merchant_id, row.country_iso)
    if prev_key != NULL and not nondecreasing(prev_key, key):
      return FAIL("DATASET-UNSORTED","DATASET","s3_base_weight_priors", m)
    prev_key = key

    if row.country_iso not in cand_set:
      return FAIL("PRIORS-EXTRA-COUNTRY","MERCHANT","s3_base_weight_priors", m, {"iso":row.country_iso})
    if not is_fixed_dp_score(row.base_weight_dp, priors_cfg.dp):
      return FAIL("PRIORS-DP-VIOL","MERCHANT","s3_base_weight_priors", m,
                  {"iso":row.country_iso,"value":row.base_weight_dp})
    if row.dp != priors_cfg.dp:
      return FAIL("PRIORS-DP-VIOL","MERCHANT","s3_base_weight_priors", m,
                  {"iso":row.country_iso,"dp":row.dp,"expected":priors_cfg.dp})

    insert(row.country_iso, seen)

  // completeness not required for priors; subset allowed (no extras, no dupes)

  it.close()
  return OK()
```

---

## 14.4 V5 — Counts (per merchant; optional)

```
PROC v_check_counts(run: RunArgs, dict: DictCtx, read: ReadCtx,
                    m: MerchantID, cand_set:Set<ISO2>, N_map, bounds?)
  -> { ok:true, count_i: Map<ISO2→int> } | Fail:

  if not run.toggles.emit_counts: return { ok:true, count_i: {} }

  it   := read.open_iter("s3_integerised_counts",
                         run.parameter_hash,
                         ["merchant_id","country_iso","count","residual_rank"],
                         order=["merchant_id","country_iso"])
  rows := ITER_GROUP_BY(it, ["merchant_id"]).get(m)

  seen_iso := set(), seen_resid := set()
  count_i := {}
  sum := 0
  prev_key := NULL

  for row in rows:
    key := (row.merchant_id, row.country_iso)
    if prev_key != NULL and not nondecreasing(prev_key, key):
      return FAIL("DATASET-UNSORTED","DATASET","s3_integerised_counts", m)
    prev_key = key

    if row.country_iso not in cand_set:
      return FAIL("COUNTS-EXTRA-COUNTRY","MERCHANT","s3_integerised_counts", m, {"iso":row.country_iso})
    if row.country_iso in seen_iso:
      return FAIL("COUNTS-DUPE-COUNTRY","MERCHANT","s3_integerised_counts", m, {"iso":row.country_iso})
    insert(row.country_iso, seen_iso)

    if NOT is_int(row.count) OR row.count < 0:
      return FAIL("COUNTS-NONNEG-INT","MERCHANT","s3_integerised_counts", m,
                  {"iso":row.country_iso,"value":row.count})
    sum += row.count
    count_i[row.country_iso] = row.count

    if row.residual_rank in seen_resid:
      return FAIL("COUNTS-RESID-DUPE","MERCHANT","s3_integerised_counts", m,
                  {"resid":row.residual_rank})
    insert(row.residual_rank, seen_resid)

    if bounds? has (m,row.country_iso):
      lo := bounds?[(m,row.country_iso)].min?
      hi := bounds?[(m,row.country_iso)].max?
      if (lo != NULL and row.count < lo) or (hi != NULL and row.count > hi):
        return FAIL("BOUNDS-VIOL","MERCHANT","s3_integerised_counts", m,
                    {"iso":row.country_iso,"count":row.count,"lo":lo,"hi":hi})

  if SIZE(seen_iso) != SIZE(cand_set):
    return FAIL("COUNTS-MISSING-COUNTRY","MERCHANT","s3_integerised_counts", m)
  expected := N_map[m]
  if sum != expected:
    return FAIL("COUNTS-SUM-NEQ-N","MERCHANT","s3_integerised_counts", m,
                {"expected":expected,"observed":sum})

  if SIZE(seen_resid) != SIZE(cand_set) or MIN(seen_resid) != 1 or MAX(seen_resid) != SIZE(cand_set):
    return FAIL("COUNTS-RESID-GAP","MERCHANT","s3_integerised_counts", m)

  it.close()
  return { ok:true, count_i: count_i }
```

---

## 14.5 V6 — Sequence (per merchant; optional; requires counts)

```
PROC v_check_sequence(run: RunArgs, dict: DictCtx, read: ReadCtx,
                      m: MerchantID, count_i: Map<ISO2→int>) -> OK | Fail:

  if not run.toggles.emit_sequence: return OK()
  if run.toggles.emit_sequence and not run.toggles.emit_counts:
    return FAIL("SEQ-NO-COUNTS","MERCHANT","s3_site_sequence", m)

  it   := read.open_iter("s3_site_sequence",
                         run.parameter_hash,
                         ["merchant_id","country_iso","site_order","site_id"],
                         order=["merchant_id","country_iso","site_order"])
  groups := ITER_GROUP_BY(it, ["merchant_id","country_iso"])

  for ((mid, iso), rows) in groups:
    if mid != m: continue
    if iso not in count_i:
      return FAIL("SEQ-COUNTRY-NOT-IN-COUNTS","MERCHANT","s3_site_sequence", m, {"iso":iso})
    need := count_i[iso]

    prev_key := NULL
    seen_len := 0
    seen_ids := set()

    for row in rows:
      key := (row.merchant_id, row.country_iso, row.site_order)
      if prev_key != NULL and not nondecreasing(prev_key, key):
        return FAIL("DATASET-UNSORTED","DATASET","s3_site_sequence", m)
      prev_key = key

      expected := seen_len + 1
      if row.site_order != expected:
        return FAIL("SEQ-GAP","MERCHANT","s3_site_sequence", m,
                    {"iso":iso,"expected":expected,"observed":row.site_order})
      seen_len = row.site_order

      if row.site_id != NULL:
        if not is_zero_padded_6(row.site_id):
          return FAIL("SEQ-ID-FORMAT","MERCHANT","s3_site_sequence", m, {"iso":iso,"id":row.site_id})
        if row.site_id in seen_ids:
          return FAIL("SEQ-ID-DUPE","MERCHANT","s3_site_sequence", m, {"iso":iso,"id":row.site_id})
        insert(row.site_id, seen_ids)

    if seen_len != need:
      return FAIL("SEQ-LENGTH-NEQ-COUNT","MERCHANT","s3_site_sequence", m,
                  {"iso":iso,"expected":need,"observed":seen_len})

  it.close()
  return OK()
```

---

## 14.6 V7 — Cross-lane legality & authority (per merchant)

```
PROC v_check_crosslane(run: RunArgs, m: MerchantID,
                       cand_set:Set<ISO2>,
                       count_i?: Map<ISO2→int>,
                       priors_present: bool,
                       counts_present: bool,
                       sequence_present: bool) -> OK | Fail:

  if sequence_present and not counts_present:
    return FAIL("SEQ-NO-COUNTS","MERCHANT",NULL, m)

  // Priors completeness is not required (subset policy). Candidate set is always present in S3.

  if counts_present and SIZE(cand_set) == 0:
    return FAIL("COUNTS-MISSING-COUNTRY","MERCHANT","s3_integerised_counts", m)

  // Authority boundary: only candidate_set may encode inter-country order.
  return OK()
```

---

## 14.7 V8 — Build bundle (run-wide)

```
PROC v_build_bundle(run: RunArgs, tallies, maybe_failure) -> { files: Map<string→bytes>, pass: bool }:
  summary_bytes := CANONICAL_JSON({
     "component":"S3.L3",
     "parameter_hash": run.parameter_hash,
     "manifest_fingerprint": run.manifest_fingerprint,
     "toggles": run.toggles,
     "datasets_present": tallies.datasets_present,
     "row_counts": tallies.row_counts,
     "merchants": { "total":tallies.merchants_total,
                    "validated":tallies.merchants_validated,
                    "failed":tallies.merchants_failed },
     "result": (maybe_failure==NULL ? "PASS" : "FAIL"),
     "version": { "doc_semver": DOC_SEMVER, "validator_impl": VALIDATOR_ID }
  })

  if maybe_failure == NULL:
     d_summary := SHA256_HEX(summary_bytes).lower()
     manifest  := CONCAT("summary.json", NUL, d_summary)
     flag_line := CONCAT("sha256=", SHA256_HEX(BYTES(manifest)).lower(), "\n")
     return { files: { "summary.json": summary_bytes,
                       "_passed.flag": BYTES(flag_line) }, pass:true }
  else:
     fail_line := CANONICAL_JSON_LINE(maybe_failure) + "\n"
     return { files: { "summary.json": summary_bytes,
                       "failures.jsonl": BYTES(fail_line) }, pass:false }
```

---

## 14.8 Complexity summary (per kernel)

* `v_check_structural`: O(total rows), O(1) memory.
* `v_check_candidates`: O(K) rows for merchant m, O(K) memory.
* `v_check_priors`: O(K), O(K) memory.
* `v_check_counts`: O(K), O(K) memory.
* `v_check_sequence`: O(Σ count_i), O(1) per country (+ IDs set if present).
* `v_build_bundle`: O(1) serialization; O(1) memory.

---

## 14.9 Acceptance checklist (for this section)

* [ ] Each skeleton names exact projections and order hints.
* [ ] Single-pass streaming with deterministic guards and **fail-fast**.
* [ ] Return shapes align with §13; no hidden state.
* [ ] Helper predicates defined for fixed-dp parsing & ID format.
* [ ] No paths, no RNG, no timestamps, and reproducible outputs.

---

# 15) Failure Taxonomy (Deterministic, Minimal)

## 15.1 Principles (binding)

* **Deterministic:** same inputs ⇒ same failure code and payload bytes.
* **Minimal:** record **one** failure (fail-fast). No aggregation.
* **Scoped:** `RUN`, `DATASET`, or `MERCHANT` scope determines routing.
* **Stable codes:** `UPPER_SNAKE`; no host/environment details.
* **No PII / no paths:** payload holds IDs, lineage, and compact details only.

---

## 15.2 Standard payload shape (canonical JSON line)

Every failure record must conform to:

```json
{
  "code": "<STABLE_ERROR_CODE>",
  "scope": "RUN" | "DATASET" | "MERCHANT",
  "dataset_id": "s3_candidate_set|s3_base_weight_priors|s3_integerised_counts|s3_site_sequence|null",
  "merchant_id": "<id-or-null>",
  "parameter_hash": "<Hex64>",
  "manifest_fingerprint": "<Hex64>",
  "details": { /* small, deterministic K/Vs: expected, observed, key fields */ }
}
```

**Canonicalization**

* Keys sorted lexicographically; UTF-8; newline at EOF.
* Values are primitive types (string/int/bool); **no floats**; no timestamps.

---

## 15.3 Routing & stop rules

* **RUN-scoped** (V0–V2): abort the entire run; publish FAIL bundle.
* **DATASET / MERCHANT-scoped** (V3–V7): stop that merchant immediately and publish FAIL bundle; remaining work drains/cancels.
* **Priority:** earlier V-nodes dominate later ones. Within a node, the **first streamed breach** is canonical.

---

## 15.4 Code catalog by node (authoritative)

### V0–V2 (open/resolve/presence/lineage) — run-wide

| Code                          | Scope   | Where it arises                                      | details{} hints                 |
|-------------------------------|---------|------------------------------------------------------|---------------------------------|
| `DICT-OPEN-FAIL`              | RUN     | open dictionary                                      | {reason}                        |
| `PRESENCE-MATRIX-FAIL`        | RUN     | presence matrix resolution                           | {parameter_hash}                |
| `DATASET-PRESENCE-MISMATCH`   | RUN     | presence vs toggles (incl. `sequence ⇒ counts`)      | {dataset_id, required, present} |
| `DICT-RESOLVE-FAIL`           | RUN     | resolve schema/partition template                    | {dataset_id}                    |
| `PARTITION-TEMPLATE-MISMATCH` | RUN     | partition keys ≠ `["parameter_hash"]`                | {dataset_id, partition_keys}    |
| `EMBED-PATH-MISMATCH`         | DATASET | row\.parameter_hash ≠ run parameter_hash             | {dataset_id, got}               |
| `MIXED-MANIFEST`              | DATASET | row\.manifest_fingerprint ≠ run manifest_fingerprint | {dataset_id, got}               |
| `BOM-OPEN-FAIL`               | RUN     | open BOM (priors_cfg/bounds)                         | {reason}                        |
| `S2-NMAP-FAIL`                | RUN     | build S2 merchant→N map                              | {reason}                        |

### V3 (candidates) — per merchant

| Code                    | Scope    | Description                  | details{}    |
|-------------------------|----------|------------------------------|--------------|
| `DATASET-UNSORTED`      | DATASET  | writer-sort broken           | {dataset_id} |
| `CAND-DUPE-ISO`         | MERCHANT | duplicate `country_iso`      | {iso}        |
| `CAND-DUPE-RANK`        | MERCHANT | duplicate `candidate_rank`   | {rank}       |
| `CAND-RANK-START-NEQ-0` | MERCHANT | min rank ≠ 0                 | {}           |
| `CAND-RANK-GAP`         | MERCHANT | ranks not contiguous 0..K−1  | {}           |
| `HOME-MISSING`          | MERCHANT | no `is_home=true@rank0` row  | {}           |
| `HOME-DUPE`             | MERCHANT | more than one `is_home=true` | {}           |
| `HOME-RANK-NEQ-0`       | MERCHANT | home row exists but rank≠0   | {rank}       |

### V4 (priors) — per merchant (optional)

| Code                     | Scope    | Description                                               | details{}                            |
|--------------------------|----------|-----------------------------------------------------------|--------------------------------------|
| `DATASET-UNSORTED`       | DATASET  | writer-sort broken                                        | {dataset_id:"s3_base_weight_priors"} |
| `PRIORS-EXTRA-COUNTRY`   | MERCHANT | priors row not in candidate countries                     | {iso}                                |
| `PRIORS-DUPE-COUNTRY`    | MERCHANT | duplicate priors row for a country                        | {iso}                                |
| `PRIORS-DP-VIOL`         | MERCHANT | `base_weight_dp` not fixed-dp **or** `dp`≠`priors_cfg.dp` | {iso, value?\|dp?, expected?}        |

### V5 (counts) — per merchant (optional)

| Code                     | Scope    | Description                           | details{}                            |
|--------------------------|----------|---------------------------------------|--------------------------------------|
| `DATASET-UNSORTED`       | DATASET  | writer-sort broken                    | {dataset_id:"s3_integerised_counts"} |
| `COUNTS-EXTRA-COUNTRY`   | MERCHANT | counts row not in candidate countries | {iso}                                |
| `COUNTS-MISSING-COUNTRY` | MERCHANT | candidate country missing in counts   | {}                                   |
| `COUNTS-DUPE-COUNTRY`    | MERCHANT | duplicate counts row for a country    | {iso}                                |
| `COUNTS-NONNEG-INT`      | MERCHANT | count not a non-negative integer      | {iso, value}                         |
| `COUNTS-SUM-NEQ-N`       | MERCHANT | Σ count ≠ N (from S2)                 | {expected, observed}                 |
| `COUNTS-RESID-DUPE`      | MERCHANT | duplicate `residual_rank`             | {resid}                              |
| `COUNTS-RESID-GAP`       | MERCHANT | residual ranks not contiguous 1..K    | {}                                   |
| `BOUNDS-VIOL`            | MERCHANT | count outside configured (lo,hi)      | {iso, count, lo?, hi?}               |

### V6 (sequence) — per merchant (optional; requires counts)

| Code                        | Scope    | Description                                 | details{}                       |
|-----------------------------|----------|---------------------------------------------|---------------------------------|
| `DATASET-UNSORTED`          | DATASET  | writer-sort broken                          | {dataset_id:"s3_site_sequence"} |
| `SEQ-NO-COUNTS`             | MERCHANT | sequence present while counts absent        | {}                              |
| `SEQ-COUNTRY-NOT-IN-COUNTS` | MERCHANT | sequence row for country without counts     | {iso}                           |
| `SEQ-GAP`                   | MERCHANT | site_order not contiguous (expected vs got) | {iso, expected, observed}       |
| `SEQ-LENGTH-NEQ-COUNT`      | MERCHANT | per-country length ≠ countᵢ                 | {iso, expected, observed}       |
| `SEQ-ID-FORMAT`             | MERCHANT | site_id not zero-padded 6-digit             | {iso, id}                       |
| `SEQ-ID-DUPE`               | MERCHANT | duplicate site_id within a country          | {iso, id}                       |

### V7 (cross-lane legality & authority) — per merchant

| Code                   | Scope    | Description                                       | details{}    |
|------------------------|----------|---------------------------------------------------|--------------|
| `SEQ-NO-COUNTS`        | MERCHANT | sequence lane without counts (per merchant)       | {}           |
| `AUTH-ORDER-VIOLATION` | RUN      | non-candidate dataset encodes inter-country order | {dataset_id} |

### V8–V9 (bundle publish) — run-wide

| Code                          | Scope | Description                              | details{}         |
|-------------------------------|-------|------------------------------------------|-------------------|
| `BUNDLE-PUBLISH-FAIL`         | RUN   | failure to atomically publish bundle     | {reason}          |
| `BUNDLE-FINGERPRINT-MISMATCH` | RUN   | attempted publish for mixed fingerprints | {got, expected}   |
| `BUNDLE-PARTIAL-REFUSED`      | RUN   | attempted partial commit                 | {members_present} |

---

## 15.5 Code naming conventions

* **Prefix by domain:** `CAND-*`, `PRIORS-*`, `COUNTS-*`, `SEQ-*`, `DICT-*`, `BUNDLE-*`.
* **Keep it atomic:** one condition ↔ one code ↔ one node.

---

## 15.6 Error construction helper (language-agnostic)

```
PROC mk_fail(code, scope, dataset_id, merchant_id, details) -> Fail:
  return { ok:false, code, scope,
           dataset_id: dataset_id ? dataset_id : "null",
           merchant_id: merchant_id ? merchant_id : "null",
           parameter_hash: RUN.parameter_hash,
           manifest_fingerprint: RUN.manifest_fingerprint,
           details: SORT_KEYS(details) }
```

Use in every kernel to guarantee identical JSON key order.

---

## 15.7 First-failure selection (tie-breaking)

* **Node order precedence:** V2 ≺ V3 ≺ V4 ≺ V5 ≺ V6 ≺ V7.
* **Within node:** the first streamed breach is canonical (no post-hoc scans).
* **Specific beats generic:** prefer the most specific applicable code (e.g., `CAND-DUPE-ISO` over a generic dataset error).

---

## 15.8 Logging (non-evidence) for failures

On failure, log one structured event (e.g., `V_LANE_FAIL`) with `{code, dataset_id, merchant_id?, parameter_hash}` and minimal counters. Never log row payloads or paths.

---

## 15.9 Acceptance checklist (for this section)

* [ ] Single, canonical JSON failure line with stable code and scope.
* [ ] Complete mapping from V-nodes to codes; no overlaps or ambiguity.
* [ ] Deterministic tie-breaking and fail-fast rules.
* [ ] No PII, no paths; compact details only.
* [ ] Bundle publish failures defined and scoped.

---

# 16) Outputs & Atomic Success Marker

## 16.1 Contract (binding)

For a single `{parameter_hash, manifest_fingerprint}` slice, L3 must publish exactly one of:

* **PASS bundle** — contents: `summary.json` and `_passed.flag`. Meaning: all checks succeeded; bytes are canonical and reproducible.
* **FAIL bundle** — contents: `summary.json` and `failures.jsonl` (**exactly one** JSON line). Meaning: first canonical failure encountered; **no** success marker present.

No other combinations are valid (e.g., `_passed.flag` without `summary.json` is forbidden).

---

## 16.2 Canonical files (recap)

* `summary.json` — canonical JSON with **sorted keys**, **UTF-8 (no BOM)**, **LF newline**, **no timestamps**.
* `failures.jsonl` — one JSON line, **sorted keys**, **UTF-8 (no BOM)**, **LF** (only on FAIL).
* `_passed.flag` — one line `sha256=<64-hex>` (**lowercase**), **LF** (only on PASS).

All bytes must be **identical across reruns** given the same inputs.

---

## 16.3 Digest rule (authoritative)

The success marker is derived only from canonical content, so reruns are byte-stable.

**On PASS**

1. `d_summary = SHA256_HEX(bytes(summary.json))` (lowercase).
2. Manifest string = `"summary.json" + NUL + d_summary` (members in lexicographic order; PASS has one).
3. `_passed.flag` = `"sha256=" + SHA256_HEX(bytes(manifest)) + "\n"` (lowercase hex).

**On FAIL**
No digest is produced; `_passed.flag` is **not** written.

---

## 16.4 Atomic publish protocol

Publishing the bundle is **all-or-nothing**:

1. Stage each file to a temp area.
2. **fsync** staged bytes and containing directory (or equivalent durability primitive).
3. Perform a single **atomic rename/commit** so either the whole bundle is visible or nothing is.
4. **Refuse** mixed fingerprints or partial overwrites.

If publish fails at any step, treat it as run-scoped bundle error → `BUNDLE-PUBLISH-FAIL`.

---

## 16.5 Idempotence & retries

* **Rerun-safe:** same lineage/toggles and identical inputs ⇒ PASS re-publishes **bit-for-bit** the same `summary.json` and `_passed.flag`; FAIL re-publishes the **same** single `failures.jsonl`.
* **Crash recovery:** if the process dies before commit, rerun; no partial bundle is considered valid.
* **Conflict rule:** if a bundle for the same lineage already exists:

  * If **PASS** exists: recompute; bytes **must match**. If not, refuse with `BUNDLE-PARTIAL-REFUSED` (**inputs changed**).
  * If **FAIL** exists: re-emit the **same** single failure line. If a different failure would be produced, refuse with `BUNDLE-PARTIAL-REFUSED` (**inputs changed**).

---

## 16.6 Concurrency safety

* **Single-writer per lineage:** only one validator instance may publish for a given `{parameter_hash, manifest_fingerprint}` at a time.
* The publish API must enforce this via an internal per-lineage lock or idempotent compare-and-swap.
* Concurrent **readers** are fine; validation never blocks producers.

---

## 16.7 PASS/FAIL decision point (wiring)

* The controller calls `v_build_bundle(tallies, maybe_failure)`.
* If `maybe_failure == NULL` → PASS branch; else → FAIL branch.
* No additional checks run after a FAIL is decided; fail-fast preserves time and ensures a single error record.

---

## 16.8 Canonicalization rules (to avoid drift)

* **JSON**: keys sorted lexicographically, no extraneous whitespace, **UTF-8 (no BOM)**, **LF**.
* **Numbers**: integers only in summaries; no floats.
* **Booleans/strings**: lowercase `true/false`; lineage and IDs are ASCII strings.
* **Ordering**: lists in summaries (e.g., dataset presence flags) are fixed-key maps, not arrays, to keep byte order stable.

---

## 16.9 Pseudocode (final emission)

```
PROC publish(run_args, tallies, maybe_failure):
  summary_bytes := CANONICAL_JSON({
    "component":"S3.L3",
    "parameter_hash": run_args.parameter_hash,
    "manifest_fingerprint": run_args.manifest_fingerprint,
    "toggles": run_args.toggles,
    "datasets_present": tallies.datasets_present,
    "row_counts": tallies.row_counts,
    "merchants": { "total":tallies.m_total, "validated":tallies.m_ok, "failed":tallies.m_fail },
    "result": (maybe_failure==NULL ? "PASS" : "FAIL"),
    "version": { "doc_semver": DOC_SEMVER, "validator_impl": VALIDATOR_ID }
  })

  if maybe_failure == NULL:
     d_summary := SHA256_HEX(summary_bytes).lower()
     manifest  := BYTES("summary.json") + NUL + BYTES(d_summary)
     flag_line := BYTES("sha256=") + SHA256_HEX(manifest).lower() + BYTES("\n")
     PUBLISH_VALIDATION_BUNDLE(run_args.parameter_hash,
                               run_args.manifest_fingerprint,
                               { "summary.json": summary_bytes,
                                 "_passed.flag": flag_line })
  else:
     failure_line := CANONICAL_JSON_LINE(maybe_failure) + BYTES("\n")
     PUBLISH_VALIDATION_BUNDLE(run_args.parameter_hash,
                               run_args.manifest_fingerprint,
                               { "summary.json": summary_bytes,
                                 "failures.jsonl": failure_line })
  return
```

---

## 16.10 Edge cases

* **Zero-row lanes:** PASS is still possible if presence/lineage and cross-lane legality hold and per-lane contracts admit emptiness (e.g., per-country sequence with `count_i=0`).
* **Toggle mismatch at runtime:** if observed datasets contradict toggles after structural checks, treat as `DATASET-PRESENCE-MISMATCH` earlier—L3 must **not** adapt at publish time.
* **Re-validation after producer changes:** if producers modified S3 rows after L3 PASS, lineage/tallies would change; a re-run must refuse to overwrite the bundle (**idempotence guard**) and operators should produce a fresh lineage (new fingerprint/parameter set).

---

## 16.11 Acceptance checklist (for this section)

* [ ] PASS emits `summary.json` + `_passed.flag` with the exact digest rule; FAIL emits `summary.json` + single-line `failures.jsonl`.
* [ ] Atomic commit; no partial visibility; refusal on mixed lineage or conflicting existing bundle.
* [ ] Idempotent reruns; deterministic bytes; stable canonicalization.
* [ ] Single-writer enforced per lineage; readers unaffected.
* [ ] No timestamps/RNG; integers/booleans/strings only.

---

# 17) Logging (Operational, Not Evidence)

## 17.1 Intent & hard boundaries

* **Intent:** give operators clear visibility into progress, lane activity, and failures.
* **Not evidence:** logs are *never* used for validation outcomes and must not influence PASS/FAIL or bundle bytes.
* **No PII/paths:** log IDs and counts only; never dump row payloads or filesystem paths.

---

## 17.2 Canonical envelope (every log line)

All log events MUST include this envelope (order of keys is not significant here; do not serialize this into the bundle):

```
{
  "comp": "S3.L3",
  "level": "INFO" | "WARN" | "ERROR",
  "event": "<STABLE_EVENT_NAME>",
  "parameter_hash": "<Hex64>",
  "manifest_fingerprint": "<Hex64>",
  "seq": <int>,                 // monotonic per validator process (1,2,3,…)
  "kv": { ... }                 // event-specific fields below
}
```

**Rules**

* `seq` is **process-local**, monotonic, and resets only when a new validator process starts; it is not used in bundle bytes.
* Timestamps are optional and **non-deterministic**; omit by default.

---

## 17.3 Event catalog (stable names & required kv)

### Run lifecycle

* **`V_RUN_START`** — validator invoked.
  `kv`: `{ "toggles": {emit_priors,emit_counts,emit_sequence}, "workers": N_WORKERS }`

* **`V_OPEN_HANDLES_OK`** — dictionary/schemas/BOM opened; N_map built.
  `kv`: `{ "bom_bounds": <bool>, "bom_priors_cfg": <bool> }`

* **`V_PRESENCE_RESOLVED`** — presence matrix established.
  `kv`: `{ "present": {candidate_set, base_weight_priors, integerised_counts, site_sequence} }`

* **`V_RUN_PASS`** — run completed with PASS.
  `kv`: `{ "row_counts": {candidate_set, base_weight_priors, integerised_counts, site_sequence}, "merchants": {total,ok,failed} }`

* **`V_RUN_FAIL`** — run aborted on first failure.
  `kv`: `{ "code": "<ERROR_CODE>", "dataset": "<id|null>", "merchant_id": "<id|null>" }`

### Merchant scheduling

* **`V_CHECK_ENQUEUED`** — merchant queued. `kv`: `{ "merchant_id": "<id>" }`
* **`V_CHECK_BEGIN`** — worker starts merchant. `kv`: `{ "merchant_id": "<id>" }`
* **`V_CHECK_DONE`** — worker finished merchant successfully. `kv`: `{ "merchant_id": "<id>" }`

### Lane-level (per merchant)

* **`V_CAND_BEGIN` / `V_CAND_DONE`** — `kv`: `{ "merchant_id": "<id>" }`
* **`V_PRIORS_BEGIN` / `V_PRIORS_DONE`** (only if enabled) — `kv`: `{ "merchant_id": "<id>" }`
* **`V_COUNTS_BEGIN` / `V_COUNTS_DONE`** (only if enabled) — `kv`: `{ "merchant_id": "<id>" }`
* **`V_SEQ_BEGIN` / `V_SEQ_DONE`** (only if enabled) — `kv`: `{ "merchant_id": "<id>" }`
* **`V_LANE_FAIL`** — lane-specific failure (first and only).
  `kv`: `{ "merchant_id": "<id>", "code": "<ERROR_CODE>", "dataset": "<id|null>" }`

### Publish

* **`V_BUNDLE_PUBLISH_PASS`** — `_passed.flag` + `summary.json` published atomically.
  `kv`: `{ "bytes_summary": <int>, "flag_written": true }`

* **`V_BUNDLE_PUBLISH_FAIL`** — `summary.json` + `failures.jsonl` published atomically.
  `kv`: `{ "bytes_summary": <int>, "bytes_failure": <int> }`

---

## 17.4 Privacy & payload discipline

* Allowed: counts, booleans, merchant IDs, dataset IDs, stable error codes.
* Forbidden: row payloads (e.g., scores, counts per country), file paths, stack traces, timestamps in summaries.
* Do not include JSON snippets from datasets.

---

## 17.5 Volume control & sampling

**Default levels**

* `INFO`: lifecycle + merchant begin/done; lane begin/done; publish.
* `ERROR`: only on first canonical failure or publish errors.
* `WARN`: non-fatal advisories (e.g., skipped merchants in validate-during-run mode).

**Sampling** (when merchants ≫ 100k): sample `V_CHECK_DONE` at a fixed interval (`every_k=100`), but **never** sample `V_LANE_FAIL`, `V_RUN_FAIL`, or publish events.

---

## 17.6 Operational counters (lightweight)

Emit occasional `V_PROGRESS`:

```
kv: {
  "m_processed": <int>, "m_failed": <int>,
  "rows_scanned": {
    "candidate_set": <int>, "base_weight_priors": <int>,
    "integerised_counts": <int>, "site_sequence": <int>
  }
}
```

These are informational and **must not** be used for evidence.

---

## 17.7 Failure logging handshake

When a kernel returns `Fail`, the controller must:

1. Emit a single `V_LANE_FAIL` (or `V_RUN_FAIL`) with the failure metadata.
2. Stop workers promptly (fail-fast) and proceed to build the FAIL bundle.
3. Avoid duplicate failure logs; exactly one error path.

---

## 17.8 Determinism guardrails for logging

* Logs are **out-of-band**: no log content feeds into bundle bytes.
* No timing-derived fields; `seq` provides a monotonic marker without affecting results.
* Log emission order should follow the deterministic merchant submission order where feasible; concurrency may interleave workers (acceptable).

---

## 17.9 Acceptance checklist (for this section)

* [ ] Envelope is stable and minimal; no PII/paths/payloads.
* [ ] Event catalog covers lifecycle, scheduling, lanes, and publish.
* [ ] Volume controls documented; errors not sampled.
* [ ] Logs are operational only—never part of evidence or PASS/FAIL logic.
* [ ] Determinism guardrails prevent log→result coupling.

---

# 18) “Where Do I Put It?” Wiring Map

## 18.1 What this section gives you

A concrete, end-to-end recipe for **where** the validator runs, **how** it’s invoked, **what** it needs on entry, and **how** it publishes PASS/FAIL without throttling L2 or confusing downstream consumers. Everything here is implementable on a single machine first, with a clean path to CI and on-demand audit.

---

## 18.2 Runtime integration patterns (pick one or use multiple)

### A) Post-L2 merge gate (recommended)

```
L2 publish (parameter_hash=H, fingerprint=F)
      └─▶ invoke L3 validate(H,F,toggles)     // read-only
               ├─ PASS → publish PASS bundle (summary.json + _passed.flag)
               │         └─▶ mark slice H/F “validated” → downstream readers may consume
               └─ FAIL → publish FAIL bundle (summary.json + failures.jsonl)
                         └─▶ stop downstream; surface error to operators
```

### B) CI pre-merge job (staging artifacts)

Run L3 against a staging `parameter_hash` **before** merging code or parameters. Same entrypoint, read-only; publish results to a CI artifacts area so reviewers can see PASS/FAIL.

### C) On-demand audit (read-only check)

Operations runs L3 periodically or on request for a historical `parameter_hash`. Publishes to a separate `validation/` area (same rules, no producer writes).

---

## 18.3 Controller contract (what must be passed to L3)

```json
{
  "parameter_hash": "<Hex64>",
  "manifest_fingerprint": "<Hex64>",
  "toggles": { "emit_priors": true|false, "emit_counts": true|false, "emit_sequence": true|false }
}
```

* Payload is **immutable for the run**: the values above must not change mid-run and must match the lineage embedded in the datasets the validator reads.
* The controller **must** ensure L2 has completed publishes for `parameter_hash` (or that the merchants you ask L3 to touch are final, if validating during the run).
* Enforce **one** L3 run per `{parameter_hash, manifest_fingerprint}` at a time (single-writer for the validation bundle).

---

## 18.4 Module layout (code-time wiring)

```
/validator
  /host         # read-only shims (dict/schemas, BOM, N_map, readers, publish, logging)
  /kernels      # v_check_* kernels (pure, streaming; §13)
  /orchestrator # DAG V0..V9 (submission, worker-pool, fail-fast routing; §10–§11)
  /cli          # thin CLI/entrypoint (parse RunArgs; call orchestrator)
  /config       # static defaults for knobs (N_WORKERS, batch_rows, mem_watermark; §9)
```

* **Orchestrator** calls kernels; **kernels** never call host publish.
* **Host** returns only values/handles (no paths).

---

## 18.5 Data access wiring (values, not paths)

* Open **dictionary** → resolve dataset IDs, schema anchors, partition template, logical writer sorts.
* Open **BOM** → values to parse/verify (`priors_cfg`, optional `bounds`).
* Build **S2 N_map** once on startup: `merchant_id → N`.
* For each dataset under `parameter_hash`, obtain a **reader handle** that supports:

  * **Projection** (exact columns per kernel), and
  * **Optional order** hints (fallback to per-merchant minimal sort if unsupported).

---

## 18.6 Deterministic scheduling (process-time wiring)

* **Discover merchants** from `s3_candidate_set` at `parameter_hash`.
* Submit merchants to a **bounded queue** in ascending `merchant_id`.
* Worker pool size = `N_WORKERS` (safe 1…16). Workers perform **V3 → \[V4?] → \[V5?] → \[V6?] → V7** serially per merchant.
* **Group-by MUST stitch across chunk boundaries** (per §8.2) so per-merchant scans stay contiguous.
* First failure wins: set a shared `fail_ref`, stop pulling new work, drain/cancel queue, publish FAIL bundle.

---

## 18.7 Validate-during-run (optional mode)

If you cannot wait for L2 to finish the entire partition:

1. Query **finalized merchants** for the datasets implied by toggles.
2. Schedule only these merchants.
3. Keep a **pending set** of merchants not yet final → retry them later.
4. Emit the PASS bundle **only** when all required merchants are validated for `parameter_hash`.
5. Never read non-final outputs; L2’s atomic publish guarantees you won’t see torn data.

---

## 18.8 Integration with downstream consumers (gate semantics)

* Downstream code must check for a PASS bundle **matching** `{parameter_hash, manifest_fingerprint}` **before** reading S3 datasets.
* Missing PASS bundle = “not validated”; FAIL bundle = “do not read” (and surface the error).
* This rule is **hard**: do not allow “read anyway” flags in production.

---

## 18.9 CLI and job examples (practical)

**CLI (local)**

```bash
validate_s3_l3 \
  --parameter-hash ab12... \
  --manifest-fingerprint cd34... \
  --toggles '{"emit_priors":true,"emit_counts":true,"emit_sequence":true}' \
  --workers 4 --batch-rows 20000 --mem-watermark 268435456
```

**Controller hook**

```python
def on_l2_publish_complete(param_hash, fingerprint, toggles):
    result = run_l3_validator(
        parameter_hash=param_hash,
        manifest_fingerprint=fingerprint,
        toggles=toggles,
        workers=default_workers(), batch_rows=default_batch(), mem_watermark=default_mem()
    )
    if not result.pass_:
        halt_downstream()
        raise ValidationError(result.failure_code, result.details)
```

**CI job (YAML sketch)**

```yaml
jobs:
  s3_l3_validate:
    runs-on: ubuntu-latest
    steps:
      - uses: checkout@v4
      - run: validate_s3_l3 --parameter-hash ${{ inputs.ph }} --manifest-fingerprint ${{ inputs.fp }} --toggles '${{ inputs.toggles }}' --workers 4
```

---

## 18.10 Failure routing & rollback (operational)

* **Run-scoped** failure (presence/lineage/resolve): stop immediately; publish FAIL; notify.
* **Merchant-scoped** failure (candidates/priors/counts/sequence): stop on the first merchant that fails; publish FAIL.
* Do **not** attempt to “heal” or skip merchants; fixes belong upstream.

---

## 18.11 Idempotence & resume (controller behavior)

* If the process crashes before bundle commit, rerun with the **same** lineage and toggles.
* If a PASS bundle already exists for `{parameter_hash, manifest_fingerprint}`, recompute → bytes **must** match; otherwise refuse commit and alert.
* If a FAIL bundle exists, re-emitting must produce the **same** single failure line; mismatches indicate inputs changed—treat as an operational incident.

---

## 18.12 Observability hooks (what to log, where)

* Emit **INFO**: `V_RUN_START`, `V_PRESENCE_RESOLVED`, `V_CHECK_ENQUEUED`, `V_CHECK_BEGIN/DONE`, `V_BUNDLE_PUBLISH_PASS/FAIL`.
* Emit **ERROR** only once on canonical failure or publish errors.
* Never log row payloads, file paths, or timestamps that could confuse determinism.

---

## 18.13 Security & permissions (minimal)

* **Read** permissions for S3 datasets at `parameter_hash`.
* **Read** for dictionary/schemas and BOM values.
* **Write** permission only to the validator’s **own** `validation/{parameter_hash}` area.
* No producer table writes; no schema migrations.

---

## 18.14 Configuration surface (centralized, deterministic)

```toml
[validator]
N_WORKERS      = 4
batch_rows     = 20000
mem_watermark  = 268435456
fast_mode      = false

[reader]
open_concurrency = 4
prefetch_next    = true
```

* Store with the code; include a **semver** for the validator logic.
* Changing these affects throughput only—never bytes.

---

## 18.15 Sequence diagrams (at a glance)

**Post-L2 gate**

```
Controller ──(L2 done: H,F,toggles)──▶ L3.Orchestrator
L3.Orchestrator ──▶ V0/V1/V2  // handles, presence, lineage
L3.Orchestrator ──▶ workers (V3..V7 per merchant)
workers ──(first failure?)──▶ Orchestrator
Orchestrator ──▶ V8/V9 publish (PASS or FAIL)
Controller ◀─(result)── L3.Orchestrator  // gate downstream on PASS
```

**Validate-during-run mode**

```
Controller ──▶ L3: list_finalised_merchants(required_datasets,H)
L3 ──▶ workers (only final merchants)
[repeat until all required merchants final]
L3 ──▶ publish PASS
```

---

## 18.16 Playbooks (what to do when…)

* **Presence mismatch (sequence present without counts):** Stop; report `DATASET-PRESENCE-MISMATCH`; fix publisher wiring (L2).
* **Σ counts ≠ N:** Stop; report `COUNTS-SUM-NEQ-N`; inspect S2 N and L2 integerisation.
* **Rank gap/home missing:** Stop; report `CAND-RANK-GAP`/`HOME-MISSING`; inspect candidate builder.
* **Publish failed:** Report `BUNDLE-PUBLISH-FAIL`; retry; if persistent, check permissions and storage health.

---

## 18.17 Acceptance checklist (for this section)

* [ ] Clear runtime placement (post-L2, CI, audit) and **single entrypoint** documented.
* [ ] Deterministic controller payload and **single-writer** rule for validation bundle.
* [ ] Code-time module map ensures kernels are pure and orchestrator owns scheduling/publish.
* [ ] Validate-during-run recipe avoids read/write races and defines final PASS condition.
* [ ] Downstream gate on PASS enforced; no “read anyway” path.
* [ ] Practical CLI/job examples included; idempotence/resume rules specified.
* [ ] Logging, permissions, and configuration surfaces are minimal and sufficient.

---

# 19) Performance Presets

## 19.1 Principles (how to use these)

* **Conservative first, then nudge.** Start with the preset for your environment; adjust in small steps.
* **Throughput-only knobs.** These change speed and memory use **without** affecting validation outcomes.
* **One bottleneck at a time.** Observe symptoms (I/O wait, memory pressure, CPU idle) and apply the specific fix—don’t change many knobs at once.

**Knobs referenced below**

* `N_WORKERS` — across-merchant parallelism (within-merchant stays serial).
* `batch_rows` — reader chunk size (if supported).
* `mem_watermark` — per-worker soft memory cap.
* `open_concurrency` — cap on concurrent iterator opens.
* `prefetch_next` — allow a worker to pre-open next merchant’s iterators.
* `fast_mode` — structural/lineage-only pass (still enforces lane legality).

---

## 19.2 Environment presets

### A) Developer laptop (4–8 cores, 16–32 GB RAM, SSD/NVMe)

**Use when:** local runs, moderate partitions, occasional sequence lane.

* `N_WORKERS = 4`
* `batch_rows = 20_000`
* `mem_watermark = 256 MB`
* `open_concurrency = 4`
* `prefetch_next = true`
* `fast_mode = false` (set `true` for schema/lineage-only smoke test)
  **Rationale:** balances CPU with I/O; keeps memory predictable.
  **If sequence-heavy:** drop `N_WORKERS` to 3, or raise `mem_watermark` to 384–512 MB.

### B) Workstation (8–32 cores, 64–256 GB RAM, SSD/NVMe)

**Use when:** large partitions, stable storage, sustained runs.

* `N_WORKERS = min(physical_cores, 12)`
* `batch_rows = 50_000`
* `mem_watermark = 512 MB`
* `open_concurrency = 8`
* `prefetch_next = true`
* `fast_mode = false`
  **Rationale:** pushes parallelism while protecting storage by limiting opens; larger batches amortize fragment overhead.
  **If CPU still <40% and I/O cool:** step `N_WORKERS` up by +2 (max 16), watch RAM and fragment opens.

### C) VM / shared disk (moderate CPU, networked filesystem, higher latency)

**Use when:** I/O is the dominant cost; reader opens are expensive.

* `N_WORKERS = 2–4`
* `batch_rows = 50_000`
* `mem_watermark = 256–384 MB`
* `open_concurrency = 2`
* `prefetch_next = false`
* `fast_mode = false` (consider `true` for quick gate checks)
  **Rationale:** fewer workers and opens reduce contention; bigger batches reduce seek churn.

### D) Cloud object storage (e.g., S3/Blob) with request throttling

**Use when:** object-store latency and per-request costs dominate.

* `N_WORKERS = 2–6` (start at 3)
* `batch_rows = 100_000` (or the largest your reader tolerates)
* `mem_watermark = 512 MB`
* `open_concurrency = 2–4`
* `prefetch_next = false`
* `fast_mode = false`
  **Rationale:** large batches to amortize GETs; tightened open concurrency to avoid throttling.
  **If 429s/slowdowns appear:** reduce `open_concurrency` by 1 and `N_WORKERS` by 1; retry after backoff.

### E) Sequence-heavy slices (large `N` per merchant)

**Use when:** `site_sequence` dominates row count.

* `N_WORKERS = ⌊baseline × 0.5⌋` (e.g., 4 → 2)
* `batch_rows = 50_000–100_000`
* `mem_watermark = 512–1024 MB` (depending on RAM)
* `open_concurrency = N_WORKERS`
* `prefetch_next = false` (avoid double-buffering; per-merchant O(count_i))
  **Rationale:** sequence rows scale with `N`; reduce concurrency to cap memory; bigger batches smooth I/O.

### F) Validate-during-run (read only finalised merchants)

**Use when:** you need early feedback while L2 is still publishing.

* `N_WORKERS = 2–4`
* `batch_rows = 20_000–50_000`
* `mem_watermark = 256–384 MB`
* `open_concurrency = N_WORKERS`
* `prefetch_next = false`
* `fast_mode = true` (recommended) for early structural assurance; full mode once all merchants final.
  **Rationale:** frequent finalisation checks mean many small reads—lightweight settings are friendlier to producers.

---

## 19.3 Quick tuning playbook (symptom → action)

| Symptom                         | Likely bottleneck  | Do this (one step at a time)                                                                 |
|---------------------------------|--------------------|----------------------------------------------------------------------------------------------|
| High I/O wait, low CPU          | Storage-bound      | Increase `batch_rows` (→ 50k/100k). Lower `open_concurrency`. Optionally reduce `N_WORKERS`. |
| CPU idle, disk cool             | Under-parallelized | Increase `N_WORKERS` by +2 (cap 16). Watch RAM.                                              |
| Many small fragments            | Open/seek churn    | Raise `batch_rows`, reduce `open_concurrency`. Consider prefetch only if memory allows.      |
| Memory near swap                | Working set large  | Reduce `N_WORKERS` (−1 or −2). Lower `prefetch_next`. Raise `mem_watermark` if RAM allows.   |
| Sequence lane slow              | Per-merchant O(N)  | Use preset **E**. Lower `N_WORKERS`, raise `batch_rows` and `mem_watermark`.                 |
| Intermittent throttling (cloud) | Request limits     | Reduce `open_concurrency` and `N_WORKERS`. Keep `batch_rows` high. Add retry/backoff.        |

---

## 19.4 Safe limits (guardrails)

* `N_WORKERS`: **1…16** (beyond 16 rarely helps on a single machine).
* `batch_rows`: **10 000…100 000** (must be ≤ reader’s max batch size).
* `mem_watermark`: **128 MB…1 GB** per worker (stay below 50–60% of total RAM).
* `open_concurrency`: **1…N_WORKERS**.
* `prefetch_next`: **false/true** (enable only if memory headroom exists).

---

## 19.5 Minimal configuration examples

**Laptop default**

```toml
[validator]
N_WORKERS     = 4
batch_rows    = 20000
mem_watermark = 268435456  # 256 MiB
fast_mode     = false

[reader]
open_concurrency = 4
prefetch_next    = true
```

**Workstation default**

```toml
[validator]
N_WORKERS     = 12
batch_rows    = 50000
mem_watermark = 536870912  # 512 MiB
fast_mode     = false

[reader]
open_concurrency = 8
prefetch_next    = true
```

**Sequence-heavy**

```toml
[validator]
N_WORKERS     = 2
batch_rows    = 100000
mem_watermark = 1073741824  # 1 GiB
fast_mode     = false

[reader]
open_concurrency = 2
prefetch_next    = false
```

**Validate-during-run**

```toml
[validator]
N_WORKERS     = 3
batch_rows    = 20000
mem_watermark = 268435456
fast_mode     = true

[reader]
open_concurrency = 3
prefetch_next    = false
```

---

## 19.6 Operational counters to watch (and what to do)

* **`io_wait_ratio` high, `avg_iter_ms` high** → storage-bound → increase `batch_rows`, reduce `open_concurrency`, maybe reduce `N_WORKERS`.
* **`fragment_opens_total` huge** → fragmentation → raise `batch_rows`, reduce `N_WORKERS`.
* **`max_worker_resident_bytes` near watermark** → memory pressure → lower `N_WORKERS` or disable `prefetch_next`; if RAM allows, raise `mem_watermark`.
* **`rows_scanned_*` dominated by sequence** → apply preset **E**.

---

## 19.7 Acceptance checklist (for this section)

* [ ] Presets exist for laptop, workstation, VM/shared disk, cloud object storage, sequence-heavy, and validate-during-run.
* [ ] Each preset defines all knobs with conservative defaults and rationale.
* [ ] Symptom→action table gives clear, single-step adjustments.
* [ ] Safe limits prevent runaway memory or futile parallelism.
* [ ] Examples show exactly how to encode settings (deterministic TOML).

---

# 20) Test Fixtures & Sampling Plan

## 20.1 Objectives

* Prove the validator is **correct, deterministic, and fast** using small, surgical fixtures.
* Catch **every contract breach** with a single, stable failure line (fail-fast).
* Exercise **all lanes** and **cross-lane rules** under realistic toggles—without giant datasets.
* Provide a **scalable sampling plan** for large, real partitions so confidence grows as data grows.

---

## 20.2 Fixture design principles

* **Tiny, surgical, self-contained.** Each fixture targets one invariant; rows fit on a screen.
* **Values, not paths.** Harness plumbing uses dataset IDs, columns, and lineage.
* **Single breach per fixture.** Build one illegal condition at a time so the single canonical failure is obvious.
* **Canonical lineage.** Every row embeds the same `{parameter_hash, manifest_fingerprint}` for a given fixture unless the test is about lineage violations.
* **Explicit toggles.** Each fixture declares `{emit_priors,emit_counts,emit_sequence}`; presence must match.

---

## 20.3 Golden fixture set (authoritative, checked into repo)

### G0 — PASS baseline (all lanes)

* **Toggles:** `{priors:1, counts:1, sequence:1}`
* **Merchants:** two

  * **M_A (K=3, N=7):** candidate ranks `0..2` with `home@0`; priors fixed-dp; counts sum to 7; residual ranks `1..3`; sequence `1..count_i` per country.
  * **M_B (K=1, N=2):** home-only + counts + sequence of length 2; priors present with dp match.
* **Expect:** PASS bundle; `_passed.flag` stable across reruns.

### G1 — Candidate rank gap

* Candidate ranks `0,2` (missing `1`) for M_A.
* **Expect:** `CAND-RANK-GAP` (MERCHANT, `s3_candidate_set`).

### G2 — Home missing

* No `is_home=true` row for M_A.
* **Expect:** `HOME-MISSING`.

### G3 — Priors dp violation

* `base_weight_dp = "0.1"` when `dp=2` (should be `"0.10"`), or any row with `dp != priors_cfg.dp`.
* **Expect:** `PRIORS-DP-VIOL` (MERCHANT, `s3_base_weight_priors`).

### G4 — Priors extra country

* Priors include a country not in candidates.
* **Expect:** `PRIORS-EXTRA-COUNTRY`.

### G5 — Counts Σ≠N

* Counts sum to 6 when `N_map[M_A]=7`.
* **Expect:** `COUNTS-SUM-NEQ-N`.

### G6 — Counts residual gap

* Residual ranks `1,3` (missing `2`).
* **Expect:** `COUNTS-RESID-GAP`.

### G7 — Bounds violation (optional policy present)

* Count below `min` or above `max` for a configured country.
* **Expect:** `BOUNDS-VIOL`.

### G8 — Sequence length ≠ countᵢ

* Per-country sequence has length 4 when countᵢ==5.
* **Expect:** `SEQ-LENGTH-NEQ-COUNT`.

### G9 — Sequence without counts (lane legality)

* **Toggles:** `sequence=1, counts=0`; or present `site_sequence` when `counts` dataset absent.
* **Expect:** `DATASET-PRESENCE-MISMATCH` (run-wide) **or** `SEQ-NO-COUNTS` (per-merchant), depending on stage.

### G10 — Mixed manifest across datasets

* Priors embed a different `manifest_fingerprint`.
* **Expect:** `MIXED-MANIFEST` (DATASET).

### G11 — Embed/path mismatch

* A row’s `parameter_hash` differs from the run hash.
* **Expect:** `EMBED-PATH-MISMATCH` (DATASET).

### G12 — Writer sort breached

* Candidate rows out of `(merchant_id, candidate_rank, country_iso)` order in **`s3_candidate_set`**.
* **Expect:** `DATASET-UNSORTED`.

### G13 — Validate-during-run slice

* Only M_A final; M_B not final. Run L3 in “during-run” mode: validate M_A; ensure no PASS is emitted; complete with M_B; now PASS.
* **Expect:** PASS only after both merchants validated.

> Each golden fixture is one folder under a fixture root, with:
>
> ```
> run.json           // {parameter_hash, manifest_fingerprint, toggles}
> bom.json           // {priors_cfg?, bounds?}
> n_map.json         // {merchant_id -> N}
> candidate_set.parquet
> base_weight_priors.parquet?          // gated
> integerised_counts.parquet?          // gated
> site_sequence.parquet?               // gated
> expected.json       // {result: PASS|FAIL, code?: <if FAIL>}
> ```

---

## 20.4 Negative sampling (auto-mutations from PASS baseline)

Start from G0 PASS and programmatically mutate **one** thing per sample:

* **Candidate mutations:** drop a rank; duplicate `candidate_rank`; remove `home`; set `home@rank≠0`.
* **Priors mutations:** extra/missing country; non-fixed-dp score; scientific notation; wrong dp.
* **Counts mutations:** add extra country; drop a country; make count negative; non-integer count; residual dup/gap; Σ≠N; violate bounds.
* **Sequence mutations:** gap at `site_order=2`; duplicate `site_order`; wrong length; bad `site_id` format; duplicate `site_id`.

For each mutation:

* Build fixture → run validator → assert **first** failure code equals expected.
* Ensure no other files are changed (determinism guard).

---

## 20.5 Fuzz & property checks (bounded, deterministic)

* **Priors fixed-dp property:** generate random ASCII decimals and assert `is_fixed_dp_score(s,dp)` agrees with a reference parser; reject exponents/locale digits; accept exactly `dp` fractional digits (or integer form if `dp==0`). Use these strings as `base_weight_dp`; also assert an on-row `dp` equals `priors_cfg.dp`.
* **Residual ranks property:** for random K up to 32, create sets with exactly one duplicate or a gap; validator must flag `COUNTS-RESID-DUPE` or `COUNTS-RESID-GAP` respectively.
* **Sequence contiguity property:** for random `count_i` up to 200, emit stream with either perfect `1..count_i` or a single off-by-1; validator must flag `SEQ-GAP`.
* **Σ=N property:** generate random per-country counts summing to `N±δ`; validator must accept δ=0 and reject otherwise.

All fuzz runs are **seeded** (`SEED=...`) so failures reproduce exactly.

---

## 20.6 Reader capability fallbacks (ordering/projection tests)

* **No projection:** simulate a reader that returns extra columns; ensure kernels still project in code and do not use extras.
* **No ordering:** simulate a reader that ignores `order=[…]`; ensure per-merchant minimal sort path triggers and respects `mem_watermark`.

---

## 20.7 Determinism tests

* **Rerun stability:** run the same fixture twice; compare `summary.json` bytes and `_passed.flag` (or `failures.jsonl`) **byte-for-byte**.
* **Worker variation:** run with `N_WORKERS=1` and `N_WORKERS=8`; outputs must be identical.
* **Fast vs full mode:** in `fast_mode=true`, structural/lineage/legality still enforced; full mode adds lane checks—results consistent for fixtures where lanes are valid.

---

## 20.8 Performance smoke (small but real)

* **I/O-bound slice:** many small fragments; assert runtime stays within a conservative bound and no OOM occurs at default knobs.
* **Sequence-heavy slice:** large `N`; validate that reducing `N_WORKERS` and increasing `batch_rows` keeps memory under `mem_watermark`.

---

## 20.9 CI gating & coverage

**CI job matrix**

* Run all **goldens** (G0–G13).
* Run **negative sampling** (N≈20 auto mutations from G0).
* Run **determinism set** with two worker settings.

**Coverage matrix (requirements → fixtures)**

| Requirement (section)                      | Fixture(s)          |
|--------------------------------------------|---------------------|
| Presence vs toggles (5.2)                  | G0, G9              |
| Partition template & embed=path (5.4–5.5)  | G0, G11             |
| Manifest equality (5.5)                    | G0, G10             |
| Candidate uniqueness/contiguity/home (6.2) | G0, G1, G2          |
| Priors fixed-dp & subset (6.3)             | G0, G3, G4          |
| Counts Σ=N, residuals, bounds (6.4)        | G0, G5, G6, G7      |
| Sequence 1..countᵢ and IDs (6.5)           | G0, G8              |
| Lane legality & cross-lane joins (7)       | G0, G9              |
| Sorting discipline (6.\*)                  | G12                 |
| Validate-during-run gating (11.6)          | G13                 |
| Atomic PASS/FAIL bundles (16)              | G0, any FAIL        |
| Determinism (9, 16)                        | G0 (rerun/parallel) |

---

## 20.10 Fixture generation helpers (dev utilities)

* `mk_run(parameter_hash, fingerprint, toggles)`
* `mk_candidates(m, countries:list, home_iso, rank_order:list)`
* `mk_priors(m, countries:list, dp:int)`
* `mk_counts(m, country_counts:map, residual_ranks:1..K, bounds?:map)`
* `mk_sequence(m, country_counts:map, ids?:bool)`
* `mk_n_map({m->N})`, `mk_bom({priors_cfg?,bounds?})`

These return in-memory tables/rows; the harness writes them to the test backend (Parquet/JSONL) through the dictionary, never by path.

---

## 20.11 Bundle verification utility

A small tool to assert bundle shape and bytes:

* Verify PASS has exactly `summary.json` + `_passed.flag`, FAIL has exactly `summary.json` + `failures.jsonl`.
* Recompute `_passed.flag` digest from `summary.json` and compare.
* Check canonical JSON: sorted keys, integers only, booleans lower-case, trailing newline, **UTF-8 (no BOM)**.

---

## 20.12 Acceptance checklist (for this section)

* [ ] Golden fixtures cover every invariance and lane.
* [ ] Negative sampling mutates **one** thing at a time and asserts canonical first failure.
* [ ] Fuzz/property tests cover dp parsing, residuals, contiguity, Σ=N.
* [ ] Reader fallbacks (no order/projection) are exercised and bounded by `mem_watermark`.
* [ ] Determinism verified across reruns and worker counts.
* [ ] CI matrix wires goldens + negatives + determinism; coverage matrix complete.
* [ ] Bundle verifier checks PASS/FAIL outputs and digest rule.

---

# 21) Acceptance Checklist (L3)

> Use this as the **single green gate** before freezing S3 · L3. Every item below must be **true now**—no “tighten later.” Checklists are organized to mirror the document structure and the implementation surface.

---

## 21.1 Green-Gate Summary (must all be true)

* [ ] **Read-only & path-agnostic.** L3 uses only values/handles; never writes producer data; never dereferences filesystem paths.
* [ ] **Evidence-only.** All results derive solely from datasets under `parameter_hash`, dictionary/schemas, BOM values (parse/verify), and the S2 N map.
* [ ] **Deterministic.** Same lineage/toggles/inputs ⇒ identical PASS/FAIL and identical bundle bytes.
* [ ] **Streaming, fail-fast.** Every kernel is single-pass (O(rows)), column-projected, memory-bounded; first breach stops the run.
* [ ] **Atomic PASS/FAIL.** Exactly one PASS bundle (with `_passed.flag`) or one FAIL bundle (with a single JSON line), published atomically, idempotent across reruns.

---

## 21.2 Section-by-Section Gates

### §1 Purpose & Scope

* [ ] Purpose states byte-level proofs (structure, lineage, authority, lane legality) and excludes recomputation/RNG/mutation.
* [ ] Success criteria define determinism, fail-fast, O(rows) streaming, and atomic publish.

### §2 Placement & Triggers

* [ ] Post-L2 merge gate is explicit; L3 never blocks L2.
* [ ] Validate-during-run mode only reads **finalised** merchant slices; PASS emitted only after all required merchants are validated.
* [ ] Downstream must gate consumption on PASS for the exact `{parameter_hash, manifest_fingerprint}`.

### §3 Inputs (values, not paths)

* [ ] Run arguments include `parameter_hash`, `manifest_fingerprint`, and `{emit_*}` toggles.
* [ ] Dictionary & **schema anchors** resolve for each **dataset ID** under test.
* [ ] BOM parse/verify values (`priors_cfg?`, `bounds?`) and **S2 N_map** are present.
* [ ] Column projections for each dataset are enumerated and sufficient.

### §4 Outputs (bundle & success marker)

* [ ] PASS bundle = `summary.json` + `_passed.flag`; FAIL bundle = `summary.json` + single-line `failures.jsonl`.
* [ ] Canonical JSON (sorted keys, **UTF-8 no BOM**, **LF newlines**, no timestamps).
* [ ] Digest rule for `_passed.flag` is defined and used exactly.

### §5 Structural & Lineage (run-wide)

* [ ] Presence matrix matches toggles (sequence never without counts).
* [ ] Partitioning is **parameter-scoped only** (no `seed`, no date shards); schema anchors resolve for the exact dataset IDs.
* [ ] Every row satisfies **embed = path** for `parameter_hash`; all datasets carry the same `manifest_fingerprint`.

### §6 Dataset Contracts

**Candidates**

* [ ] Unique `(merchant_id,country_iso)` and `(merchant_id,candidate_rank)` per merchant.
* [ ] Contiguity `candidate_rank = 0..K−1`; exactly one `is_home=true` at rank 0.
* [ ] Writer-sort sanity enforced.
  **Priors (if present)**
* [ ] **Subset of candidates** (no extras/dupes); **base_weight_dp** parses as fixed-dp and per-row `dp == priors_cfg.dp`; no renorm.
* [ ] Writer-sort sanity enforced.
  **Counts (if present)**
* [ ] One-to-one with candidates; non-negative integers; **Σ count = N_map\[m]**.
* [ ] `residual_rank` is total & contiguous; bounds obeyed if configured.
* [ ] Writer-sort sanity enforced.
  **Sequence (if present; requires counts)**
* [ ] For each `(merchant,country)`, `site_order = 1..count_i` (no gaps/dupes); optional 6-digit `site_id` unique in country.
* [ ] Never encodes inter-country order; writer-sort sanity enforced.

### §7 Cross-Dataset Legality & Authority

* [ ] `emit_sequence ⇒ emit_counts` holds **per merchant**.
* [ ] Priors country set is a **subset** of candidates (no extras/dupes); Counts country set **equals** candidates; Sequence countries ⊆ counts and lengths equal `count_i`.
* [ ] Inter-country authority is **only** `candidate_rank`; within-country authority is **only** `site_order`.

### §8 Streaming Algorithms

* [ ] All kernels specify exact projections and grouping; single-pass; minimal in-memory state.
* [ ] Local sort fallback is bounded by `mem_watermark` when reader can’t order.

### §9 Performance Model & Knobs

* [ ] Knobs are defined (defaults & safe ranges) and **cannot** change bytes—only throughput.
* [ ] Guidance exists for I/O-bound vs CPU-bound vs sequence-heavy cases.

### §10 Validator DAG

* [ ] V0..V9 nodes and edges are authoritative; sequence requires counts; prohibited edges listed.
* [ ] Single normalized linearisation stated.

### §11 Concurrency & Scheduling

* [ ] Across-merchant parallelism; within-merchant serial checks; bounded queue/backpressure; early-exit routing.
* [ ] Validate-during-run merchant selection respects finalisation only.

### §12 Host Interfaces (Shims)

* [ ] Shims return values/handles only; projection/order in readers; list-finalised provided; atomic bundle publish available.
* [ ] Error model for shims uses stable codes and structured details.

### §13 Validator Surfaces (Kernels)

* [ ] Signatures, inputs/outputs, failure codes, and columns are explicit; no hidden state; stop-on-first-failure semantics.

### §14 Pseudocode Skeletons

* [ ] Each kernel has turnkey skeleton with projections, order hints, loops, guards, and canonical error construction.

### §15 Failure Taxonomy

* [ ] Stable, minimal code set mapped to V-nodes; scopes (`RUN|DATASET|MERCHANT`) clear; canonical JSON failure shape enforced; tie-breaking deterministic.

### §16 Outputs & Atomic Success Marker

* [ ] PASS/FAIL emission rules, digest computation, atomic commit, idempotence and single-writer guarantees are complete.

### §17 Logging (Operational)

* [ ] Envelope and event catalog defined; logs do not feed validation; no PII/paths; sampling rules safe.

### §18 Wiring Map

* [ ] Controller payload and single-entrypoint defined; downstream gate on PASS enforced; validate-during-run recipe included.

### §19 Performance Presets

* [ ] Presets exist for laptop, workstation, VM/shared disk, cloud, sequence-heavy, validate-during-run; each includes rationale and concrete values.

### §20 Test Fixtures & Sampling

* [ ] Golden fixtures G0–G13 cover every requirement; negative sampling mutates one condition at a time; determinism tests pass; bundle verifier included.

---

## 21.3 Determinism & Idempotence Gates

* [ ] Reruns with the same inputs produce **byte-identical** PASS bytes (or the same single FAIL line).
* [ ] Results are invariant to `N_WORKERS` within safe range and to merchant scheduling interleavings.
* [ ] Canonical JSON rules applied everywhere (**UTF-8 no BOM**, **LF newlines**); `_passed.flag` uses lowercase hex and exact manifest construction.

---

## 21.4 Performance & Safety Gates

* [ ] All kernels are O(rows); per-merchant memory O(C) or O(1); sequence lane O(Σ count_i).
* [ ] Reader fallbacks (no order/projection) are bounded and documented.
* [ ] Knob changes cannot alter PASS/FAIL; only throughput and resource use.

---

## 21.5 Failure Handling & Routing Gates

* [ ] First failure wins; exactly **one** failure line emitted; no aggregation.
* [ ] Run-scoped failures (V0–V2) abort immediately; merchant-scoped failures (V3–V7) stop that merchant and publish FAIL.
* [ ] Publish errors emit run-scoped bundle failures and never leave partial bundles visible.

---

## 21.6 Freeze Sign-Off (fill before freeze)

```
L3 Doc version (semver): ___________   SHA256(doc): ______________________________

Lineage under test: parameter_hash=________________  manifest_fingerprint=________________
Toggles: priors=__  counts=__  sequence=__

Reader capabilities verified:
  projection=[yes/no]  order_hints=[yes/no]  mem_watermark=________  N_WORKERS=____

Validator DAG V0..V9: stable @ commit ____________
Host shims contract: stable @ commit _____________
Failure taxonomy: stable @ commit ________________

Fixtures:
  Goldens G0–G13 PASS/FAIL as expected: [yes/no]
  Negative sampling (N=__): [yes/no]
  Determinism (workers 1 vs 8): [identical/not]
  Bundle verifier (digest rule): [ok/fail]

Gatekeeper (name): _______________   Date: _______________
```

---

## 21.7 “No-Drift” Enforcement (ongoing)

* [ ] Any change to schemas, dictionary, or BOM parse rules increments doc semver and re-runs fixtures and determinism matrix.
* [ ] Any new failure code updates §15 and the golden fixtures table.
* [ ] Any change to reader behavior (projection/order) re-validates fallbacks and memory bounds.

---

# Appendix — Cross-State L3 Common Library (for S0/S1/S2/S3 and future states)

## A. Purpose & Scope

Defines a **reusable validator library** for all L3 documents. It standardizes:

* **Surfaces (kernels)** you can call across states
* **Helper predicates** (decimal parsing, ordering, ID formats)
* **Reader shims** (projection, grouping, optional ordering)
* **Bundle emission** (PASS/FAIL, digest rule)
* **Failure payload shape & code canon**
* **Column maps/adapters** per state
* **Fixtures & property tests** for CI

Everything is **read-only**, **path-agnostic**, **streaming**, and **deterministic**.

---

## B. Canonical L3 Surfaces (State-Agnostic)

### B.1 Run-wide structural & lineage

```
PROC v_check_structural(run, dict, read) -> OK | Fail
// Presence ↔ toggles, schema anchor resolve, parameter-only partitioning,
// embed=path, dataset-scoped manifest equality across artifacts under parameter_hash.
```

### B.2 Dataset validators (dataset states like S3)

```
PROC v_check_candidates(run, dict, read, m) -> {ok:true, cand_set:Set<ISO2>, K:int} | Fail
PROC v_check_priors(run, dict, read, m, cand_set, priors_cfg) -> OK | Fail
PROC v_check_counts(run, dict, read, m, cand_set, N_map, bounds?) -> {ok:true, count_i:Map<ISO2→int>} | Fail
PROC v_check_sequence(run, dict, read, m, count_i) -> OK | Fail
PROC v_check_crosslane(run, m, cand_set, count_i?, priors_present, counts_present, sequence_present) -> OK | Fail
```

### B.3 Event-stream validators (event states like S1/S2)

```
PROC v_ev_hurdle_structural(run, dict, read) -> OK | Fail
// Event schema/partition discipline, audit-before-events, envelope sanity.

PROC v_ev_hurdle_replay(run, dict, read, m) -> OK | Fail
// Recompute (η,π); if stochastic, replay one open-interval uniform; match is_multi.

PROC v_ev_nb_attempts(run, dict, read, m) -> OK | Fail
// Γ→Π pairing by counter intervals; budgets/trace identities;
// finaliser non-consumption & echo (μ,φ); coverage (N,r).
```

### B.4 Bundle & emission

```
PROC v_build_bundle(run, tallies, maybe_failure) -> {files: Map<string→bytes>, pass: bool}
PROC PUBLISH_VALIDATION_BUNDLE(parameter_hash, manifest_fingerprint, files) -> void
// Canonical JSON (sorted keys, UTF-8 no BOM, LF), digest rule for _passed.flag, atomic tmp→fsync→rename.
```

### B.5 Failure construction (uniform)

```
PROC mk_fail(code, scope, dataset_id?, merchant_id?, details?) -> Fail
// Stable JSON shape (sorted keys); only ints/strings/bools; no floats/timestamps.
```

---

## C. Helper Predicates (Shared Across States)

* **Ordering**

  ```
  nondecreasing(prev_key, key) -> bool
  // Tuple lexicographic; ASCII bytewise for strings; integer compare for ranks & counts.
  ```
* **Decimal score parsing (priors; fixed dp)**

  ```
  is_fixed_dp_score(s, dp:int) -> bool
  // ASCII digits only; '.'; exactly dp fractional digits if dp>0 (or integer if dp==0); no sign/exponent/locale.
  ```
* **Zero-padded ID**

  ```
  is_zero_padded_6(s) -> bool   // ^\d{6}$
  ```
* **Integer guard**

  ```
  is_int(x) -> bool  // Reject NaN, floats, or non-digit strings
  ```

---

## D. Reader & Dictionary API (Host-Neutral Contract)

**Dictionary**

```
DICT_OPEN() -> DictHandle
DICT_RESOLVE(dict, dataset_id) -> {schema, partition_keys, writer_sort}
DATASET_PRESENCE_MATRIX(dict, parameter_hash) -> {candidate_set, base_weight_priors, integerised_counts, site_sequence}
DISCOVER_MERCHANTS(dict, parameter_hash) -> List<merchant_id>  // deterministic order
```

**Readers**

```
OPEN_ITER(dataset_id, parameter_hash, columns, order?) -> Iter
  // Returns only 'columns'; order is a logical hint. Iter has .next() and .close().

ITER_GROUP_BY(iter, key_cols) -> Iterator<(key_tuple, row_iter)>
  // MUST stitch groups across chunk boundaries; minimal per-key buffering; no full materialization.
```

**Aux facts**

```
OPEN_BOM_VALUES() -> {priors_cfg?, bounds?}
GET_S2_N_MAP(parameter_hash) -> Map<merchant_id→N>
```

**Atomic publish**

```
PUBLISH_VALIDATION_BUNDLE(parameter_hash, manifest_fingerprint, files: Map<name→bytes>)
```

---

## E. Failure Payload & Code Canon (One Shape, All States)

**Canonical JSON line**

```json
{ "code":"<STABLE_ERROR_CODE>", "scope":"RUN|DATASET|MERCHANT",
  "dataset_id":"…|null", "merchant_id":"…|null",
  "parameter_hash":"<Hex64>", "manifest_fingerprint":"<Hex64>",
  "details":{…} }
```

**Code families (reserved prefixes)**

* `DICT-*` (dictionary/resolve/list/presence)
* `STRUCT-*` (partition template/lineage/manifest)
* `CAND-*` (candidate set)
* `PRIORS-*` (priors dp/joins)
* `COUNTS-*` (counts joins/sum/residual/bounds)
* `SEQ-*` (sequence legality/contiguity)
* `EV-HURDLE-*` (S1) · `EV-NB-*` (S2)
* `AUTH-*` (authority boundary)
* `BUNDLE-*` (publish/digest/atomicity)

> Keep a **one condition ↔ one code ↔ one node** mapping; avoid synonyms across states.

---

## F. Column Maps & Adapters (Per State)

| State | Kernel family   | Canonical columns (→ adapter maps)                                                                                                                                                                                                                   |
|------:|-----------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|    S0 | Structural only | `parameter_hash`, `manifest_fingerprint` (for each artifact under validation)                                                                                                                                                                        |
|    S1 | Event streams   | `merchant_id`, `module`, `substream_label`, `before`, `after`, `draws`, payload fields `(η,π,u?,is_multi)`                                                                                                                                           |
|    S2 | Event streams   | `merchant_id`, attempt index, `before/after/draws`, Γ/Π payloads `(μ,φ,λ)`, finaliser `(μ,φ,N,r)`                                                                                                                                                    |
|    S3 | Datasets        | **Candidates**: `merchant_id,country_iso,candidate_rank,is_home` · **Priors**: `merchant_id,country_iso,base_weight_dp,dp` · **Counts**: `merchant_id,country_iso,count,residual_rank` · **Sequence**: `merchant_id,country_iso,site_order,site_id?` |
**Adapter pattern**

```
PROC sX_columns_adapter(dataset_or_stream) -> {canonical_col→actual_col}
PROC sX_open_iter_canonical(dataset_id, canonical_cols, order?) -> Iter
// Wraps OPEN_ITER + renames projected columns before kernels see rows.
```

---

## G. Reuse Guide by State

* **S0** — Use `v_check_structural` + bundle; no dataset kernels. Codes: `DICT-*`, `STRUCT-*`, `BUNDLE-*`.
* **S1** — `v_ev_hurdle_structural`, `v_ev_hurdle_replay` (per merchant). Same bundle/failure canon.
* **S2** — `v_ev_nb_attempts` (Γ→Π pairing, counters, finaliser echo) + structural + bundle.
* **S3** — Dataset kernels (`v_check_candidates/priors/counts/sequence/crosslane`) + structural + bundle.
  *Future states pick **event** family (EV-*) or **dataset** family (DS-*) with thin adapters.*

---

## H. Canonical Bundle & Digest (All States)

* **PASS**: `summary.json` + `_passed.flag`
  `_passed.flag` = `sha256=<SHA256("summary.json" + NUL + SHA256(summary_bytes))>` (lowercase hex)
* **FAIL**: `summary.json` + `failures.jsonl` (exactly one JSON line)
* Canonical JSON: **sorted keys**, **UTF-8 (no BOM)**, **LF newline**; integers/bools/strings only; no timestamps.

---

## I. Determinism & Concurrency Rules

* Across-merchant parallelism OK; within-merchant checks serial.
* Merchant iteration order deterministic (e.g., ascending `merchant_id`).
* First failure wins; stop workers; publish FAIL bundle.
* Reruns with same inputs must reproduce **identical bytes**.
* Knobs (`N_WORKERS`, `batch_rows`, `mem_watermark`, `open_concurrency`, `prefetch_next`, `fast_mode`) affect **throughput only**.

---

## J. Test Fixture Toolkit (Reusable)

* **Golden fixtures** for each family (S0: structural; S1: hurdle; S2: NB; S3: candidates/priors/counts/sequence) with explicit toggles and lineage.
* **Negative sampling** utilities that mutate one invariant at a time and assert the canonical first failure.
* **Property tests**: fixed-dp parser; residual ranks totality; sequence contiguity; Σ=N.
* **Determinism suite**: rerun stability; `N_WORKERS=1` vs `>1`; fast vs full mode.

---

## K. Performance Presets (Shared)

* Laptop: `N_WORKERS=4`, `batch_rows=20k`, `mem_watermark=256MB`, `open_concurrency=4`, `prefetch_next=true`.
* Workstation: `N_WORKERS=12`, `batch_rows=50k`, `mem_watermark=512MB`, `open_concurrency=8`.
* Sequence-heavy: halve `N_WORKERS`, raise `batch_rows` and `mem_watermark`.
* Validate-during-run: `N_WORKERS=2–4`, `fast_mode=true`, conservative opens.
  *(Tunable; byte-stable.)*

---

## L. Compatibility Notes & Unification Decisions

1. **Structural/lineage**: one shared kernel (`v_check_structural`) for **all** states.
2. **Bundle/digest**: one shared implementation; identical PASS/FAIL shapes across states.
3. **Failure payload**: one canonical JSON line; same envelope and key ordering.
4. **Ordering & parsing helpers**: single shared predicates (`nondecreasing`, `is_fixed_dp_score`, `is_zero_padded_6`, `is_int`).
5. **Event vs Dataset families**: keep two kernel families (EV-\* and DS-\*). Adapt columns through state adapters rather than forking kernels.
6. **Error codes**: reserve prefixes per domain; avoid synonyms across states. If two states used different names for the same invariant, choose the **shortest, clearest** code and keep a tiny alias map in dev tools (not in the spec).

---

## M. Versioning & Governance

* The common library is versioned (semver). Any change to surfaces or failure codes bumps the minor/major version and re-runs the full fixture matrix.
* State docs (S0…S3) reference the library version they target.
* Migrations include adapter deltas and test changes.

---

## N. Quick Reference (Cheat Sheet)

**Call order (dataset states)**
`v_check_structural → v_check_candidates → [v_check_priors?] → [v_check_counts?] → [v_check_sequence?] → v_check_crosslane → v_build_bundle → PUBLISH_VALIDATION_BUNDLE`

**Call order (event states)**
`v_check_structural → v_ev_* (per merchant) → v_build_bundle → PUBLISH_VALIDATION_BUNDLE`

**Always pass**: `run` (lineage, toggles), `dict` (dictionary/schemas), `read` (projection/order), `aux` (N_map, BOM) as needed.

---