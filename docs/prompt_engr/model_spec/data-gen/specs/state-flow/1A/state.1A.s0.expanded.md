# S0.1 — Universe, Symbols, Authority (normative, fixed)

## Purpose & scope

S0.1 establishes the **canonical universe** (merchant rows and reference datasets) and the **schema authority** for subsegment 1A. Its job is to make the rest of S0–S9 reproducible by fixing the domain symbols and where their truth comes from. **No RNG is consumed here.**

**S0.1 freezes for the run**

* The merchant universe $\mathcal{M}$ from the **normalised ingress** table `merchant_ids`.
* The immutable **reference artefacts**: ISO-3166 country set $\mathcal{I}$; GDP-per-capita vintage $G$ pinned to **2025-04-15**; a precomputed Jenks $K{=}5$ GDP bucket map $B$.
* The **schema authority**: only JSON-Schema contracts in `schemas.ingress.layer1.yaml`, `schemas.1A.yaml`, and shared RNG/event schemas in `schemas.layer1.yaml` are authoritative; Avro (if any) is **non-authoritative**.

> Downstream consequence (normative): **inter-country order is never encoded** in egress `outlet_catalogue`; consumers **MUST** join `country_set.rank` (0 = home; foreigns follow Gumbel selection order). S0.1 records that rule as part of the authority.

---

## Domain symbols (definitions and types)

### Merchants (ingress universe)

Let $\mathcal{M}$ be the finite set of merchants from the normalised ingress table:

$$
\texttt{merchant_ids}\subset\{(\texttt{merchant_id},\ \texttt{mcc},\ \texttt{channel},\ \texttt{home_country_iso})\},
$$

validated by `schemas.ingress.layer1.yaml#/merchant_ids`.

**Field domains (authoritative and reused throughout 1A):**

* `merchant_id`: **opaque identifier** (id64 integer, per ingress schema). For all places in 1A that require a 64-bit integer key (e.g., RNG substream keys), the **only** mapping is:

  ```
  merchant_u64 = LOW64(SHA256(LE64(merchant_id)))
  ```
  where `LOW64` takes **bytes 24..31** of the 32-byte SHA-256 digest, interpreted as little-endian u64. **No string formatting** is ever used in this mapping. 

* `mcc`: 4-digit MCC code: **int32 in [0,9999]** per `merchant_ids.mcc` in the ingress schema. (If an enumerated ISO-18245 catalogue is adopted later, this spec will reference that artefact explicitly.)

* `channel ∈ 𝕮`: card-present vs not-present. **Canonical internal symbols:** `CP`, `CNP`. **Ingress mapping (normative):**

  | Ingress value (string) | Internal symbol |
  |------------------------|-----------------|
  | `"card_present"`       | `CP`            |
  | `"card_not_present"`   | `CNP`           |

  Any other value is a schema violation at S0.1.

* `home_country_iso ∈ 𝕀`: ISO-3166 alpha-2 code, **uppercase ASCII**. Foreign-key to 𝕀 is enforced **here** (not “later”).

### Canonical references (immutable within the run)

* **Countries:** $\mathcal{I}$ = ISO-3166 alpha-2 country list (finite, determined by the pinned reference).
* **GDP (per-capita) map:** $G:\mathcal{I}\rightarrow\mathbb{R}_{>0}$, **pinned to 2025-04-15** (fixes both values and coverage).
* **GDP bucket map:** $B:\mathcal{I}\rightarrow{1,\dots,5}$ — a precomputed Jenks $K=5$ classification over $G$. (S0.4 documents the CI-only rebuild; for S0.1 this artefact is immutable input.)

### Derived per-merchant tuple

For $m\in\mathcal{M}$, define the typed quadruple used downstream:

$$
t(m):=\big(\texttt{mcc}_m,\ \texttt{channel}_m\in\{\mathrm{CP},\mathrm{CNP}\},\ \texttt{home_country_iso}_m,\ \texttt{merchant_u64}_m\big)\in\mathcal{K}\times\mathcal{C}\times\mathcal{I}\times\mathbb{U}_{64}.
$$

---

## Authority & contracts (single source of truth)

### Authoritative schemas for 1A

Only **JSON-Schema** is the source of truth for 1A. All dataset contracts and RNG event contracts must refer to these paths (JSON Pointer fragments):

* Ingress: `schemas.ingress.layer1.yaml#/merchant_ids`.
* 1A model/prep/alloc/egress: `schemas.1A.yaml` (e.g., `#/model/hurdle_pi_probs`, `#/prep/sparse_flag`, `#/alloc/country_set`, `#/egress/outlet_catalogue`).
* Shared RNG events: `schemas.layer1.yaml#/rng/events/*`.

Avro (`.avsc`) is **non-authoritative** for 1A and must not be referenced by registry/dictionary entries.

### Semantic clarifications (normative)

* `country_set` is the **only** authority for **cross-country order** (rank: 0 = home, then foreigns). Egress `outlet_catalogue` does **not** carry cross-country order; consumers **must** join `country_set.rank`.
* **Partitioning semantics** (recorded here as authority, implemented in S0.10): parameter-scoped datasets partition by `parameter_hash`; egress/validation partition by `manifest_fingerprint`.

---

## Run-time invariants (frozen context)

S0.1 constructs a **run context** $\mathcal{U}$ and freezes it:

$$
\mathcal{U} := \big(\mathcal{M}, \ \mathcal{I}, \ G,\ B,\ \text{SchemaAuthority}\big).
$$

**Invariants (must hold for the entire run):**

1. **Immutability:** $\mathcal{M}$, $\mathcal{I}$, $G$, $B$, and the authority mapping do not change after S0.1 completes. Any observed mutation later is a hard failure.
2. **Coverage & domain conformance:**

   * $\forall m\in\mathcal{M}$: `home_country_iso_m ∈ 𝕀` (FK enforced here).
   * `mcc_m`: **int32 in [0,9999]** (per ingress schema type).
   * `channel_m ∈ {"card_present","card_not_present"}` at ingress and is mapped to `{CP,CNP}` internally.
3. **Determinism:** No RNG consumption; all S0.1 outputs are pure functions of loaded bytes and schemas (S0.2 will digest/record them).
4. **Authority compliance:** Every dataset/stream referenced downstream must use the **JSON-Schema** anchors listed above; any non-authoritative reference is a policy breach.

---

## Failure semantics (abort codes)

S0.1 **MUST abort** the run if any of the following occur:

* `E_INGRESS_SCHEMA` — `merchant_ids` fails validation against `schemas.ingress.layer1.yaml#/merchant_ids`.
* `E_REF_MISSING` — any canonical reference (ISO list, GDP vintage, or bucket map) is missing or unreadable. (S0.2 separately catches digest mismatches when hashing.)
* `E_AUTHORITY_BREACH` — a dataset or event in registry/dictionary points to a non-JSON-Schema (e.g., an `.avsc`) for 1A.
* `E_FK_HOME_ISO` — some merchant has `home_country_iso` not in 𝕀.
* `E_MCC_OUT_OF_DOMAIN` — some merchant has `mcc` outside **[0,9999]** or violates the ingress type constraints.
* `E_CHANNEL_VALUE` — some merchant has an ingress `channel` not in `{"card_present","card_not_present"}` (cannot map to `{CP,CNP}`).

> When S0.1 aborts, no RNG audit or parameter/fingerprint artefacts are emitted; S0.2 has not yet run.

---

## Validation hooks (what CI/runtime checks here)

* **Schema check:** validate `merchant_ids` against the ingress schema before deriving $t(m)$.
* **Reference presence & immutability:** assert that the referenced ISO set, GDP vintage (2025-04-15), and $B$ load successfully and are cached read-only for the lifetime of the run.
* **Authority audit:** scan the registry/dictionary for any 1A dataset using **non-JSON-Schema** refs and fail the build if found (policy enforcement).
* **Country FK pre-check:** `home_country_iso ∈ 𝕀` for all merchants.
* **MCC & channel domain checks:** `mcc ∈ [0,9999]`; `channel ∈ {"card_present","card_not_present"}` with a deterministic map → `{CP,CNP}`.

---

## Reference routine (language-agnostic)

```text
function S0_1_resolve_universe_and_authority():
  # 1) Load & validate merchants (strict schema)
  M = read_table("merchant_ids")
  assert schema_ok(M, "schemas.ingress.layer1.yaml#/merchant_ids"), E_INGRESS_SCHEMA

  # 2) Load canonical references (read-only for run)
  I = load_iso3166_alpha2()                               # set of country codes (uppercase ASCII)
  G = load_gdp_per_capita(vintage="2025-04-15")           # map ISO -> R_{>0}
  B = load_gdp_jenks_buckets(K=5, vintage="2025-04-15")   # map ISO -> {1..5}; precomputed artefact

  # 3) Pre-flight authority: JSON-Schema only
  assert all_registry_refs_are_jsonschema(), E_AUTHORITY_BREACH
  assert dictionary_notes_include_country_set_order_rule()

  # 4) Domain enforcement & mapping (no RNG)
  for row in M:
      iso = row.home_country_iso
      mcc = row.mcc
      ch  = row.channel
      assert iso in I, E_FK_HOME_ISO
      assert mcc_in_domain(mcc), E_MCC_OUT_OF_DOMAIN
      if   ch == "card_present":     row.channel_sym = "CP"
      elif ch == "card_not_present": row.channel_sym = "CNP"
      else:                          abort(E_CHANNEL_VALUE)
      row.merchant_u64 = LOW64(SHA256(LE64(merchant_id)))  # canonical u64 key

  # 5) Freeze run context (pure functions only)
  U = { M: M, I: I, G: G, B: B, authority: JSONSCHEMA_ONLY }
  return U
```

---

## Notes for downstream states

* S0.2 will **hash** the loaded bytes (parameters and artefacts) to derive `parameter_hash` and `manifest_fingerprint`, and log provenance. S0.1’s immutability guarantees make those digests stable.
* All RNG substream keying that requires a merchant u64 **must** use `merchant_u64` defined here; there is no alternate mapping.
* S3’s eligibility and S6’s `country_set` persistence rely on S0.1’s **country FK** and the **channel symbol** (`CP`/`CNP`) set here.

---

**Summary:** S0.1 now pins the **who** (merchants + canonical `merchant_u64`), the **where** (countries), the **context** (GDP & buckets), and the **law** (JSON-Schema authority + cross-country order rule). It consumes **no randomness**, enforces domain validity **here**, and fails fast on any schema/authority/coverage breach—so everything that follows sits on a rock-solid, reproducible base.

---

# S0.2 — Hashes & Identifiers (Parameter Set, Manifest Fingerprint, Run ID)

## Purpose (what S0.2 guarantees)

Create the three lineage keys that make 1A reproducible and auditable:

1. **`parameter_hash`** — versions *parameter-scoped* datasets; changes when any governed parameter file’s **bytes** change.
2. **`manifest_fingerprint`** — versions *egress & validation* outputs; changes when **any opened artefact**, the **code commit**, or the **parameter bundle** changes.
3. **`run_id`** — partitions logs; **not** part of modelling state; never influences RNG or outputs.

**No RNG is consumed in S0.2.** These identifiers are pure functions of bytes + time (for `run_id` only as a log partitioner).

---

## S0.2.1 Hash primitives & encoding (normative)

* **Digest:** `SHA256(x)` returns a **raw 32-byte** digest.
* **Concatenation:** `||` = byte concatenation of already-encoded fields.
* **Hex encodings:**

  * `hex64(b32)`: lower-case hex of 32 bytes → 64 chars, **zero-left-padded**, no `0x`.
  * `hex32(b16)`: lower-case hex of 16 bytes → 32 chars, **zero-left-padded**, no `0x`.
* **Universal encoding rule (UER):**

  * **Strings:** UTF-8, prefixed by **u32 little-endian** length. *(No normalization; no path cleanup; case-sensitive.)*
  * **Integers:** **LE64**.
  * **Arrays/sets:** sort by the specified key; then encode each element in that order and concatenate; **no delimiters** besides the length-prefixes.
* **Byte domain:** Hash the **exact file bytes** as opened in binary mode; no newline translation or parsing.

> This UER applies everywhere in 1A where S0.2 says “concat” or “encode”.

---

## S0.2.2 `parameter_hash` (canonical, normative)

**Governed set 𝓟 (canonical basenames):**
`hurdle_coefficients.yaml`, `nb_dispersion_coefficients.yaml`, `crossborder_hyperparams.yaml`.

**Algorithm (tuple-hash; includes names):**

1. Validate: basenames are **ASCII** and **unique**; error if not.
2. Sort 𝓟 by **basename** using bytewise ASCII lexicographic order → `(p₁,…,pₙ)`, where here `n=3`.
3. For each `pᵢ`:

   * `dᵢ = SHA256(bytes(pᵢ))`  (32 bytes)
   * `tᵢ = SHA256( UER(nameᵢ) || dᵢ )`  (32 bytes)
4. Let `C = t₁ || t₂ || … || tₙ`  (32·n bytes).
5. `parameter_hash_bytes = SHA256(C)`  (32 bytes).
6. `parameter_hash = hex64(parameter_hash_bytes)`.

**Properties:** deterministic; resistant to name/byte collisions; future-proof if 𝓟 grows.

**Storage effect (normative):** *Parameter-scoped* datasets **must** partition by `parameter_hash={parameter_hash}` (e.g., `crossborder_eligibility_flags`, optional `hurdle_pi_probs`).

> **Note:** Randomness-bearing allocations such as `country_set` and `ranking_residual_cache_1A` are **not** parameter-scoped and must partition by `seed` (and, when applicable, by `manifest_fingerprint`).




> **Physical row order (normative):** For **Parquet** parameter-scoped datasets, row and row-group order are **unspecified** and **MUST NOT** be relied upon. Consumers **must** treat equality as **row-set** equality; any dependence on physical order is non-conformant.

**Errors (abort S0):**
`E_PARAM_EMPTY` (missing), `E_PARAM_IO(name,errno)`, `E_PARAM_NONASCII_NAME`, `E_PARAM_DUP_BASENAME`.

**Audit rows:**
`param_digest_log`: `{filename, size_bytes, sha256_hex, mtime_ns}` for each `pᵢ`.
`parameter_hash_resolved`: `{parameter_hash, filenames_sorted}`.

---

## S0.2.3 `manifest_fingerprint` (egress/validation lineage)

**Purpose.** Single lineage key that flips if **anything material** to the run changes.

**Inputs (exact):**

* 𝓐 = set of **all artefacts actually opened** during the run up to S0.2 (parameters, ISO, GDP, bucket map, schema files you read, numeric policy, etc.).
  For each artefact `a` with basename `nameₐ`:

  * `D(a) = SHA256(bytes(a))`  (32 bytes)
  * `T(a) = SHA256( UER(nameₐ) || D(a) )`  (32 bytes)
* `git_32`: **32 raw bytes** representing the repo commit id:

  * If VCS uses SHA-256: take the 32 raw bytes as-is.
  * If VCS uses SHA-1 (20 bytes): **left-pad with 12 zero bytes** to 32.
  * *(Never ASCII-hex; must be raw digest/padded raw.)*
* `parameter_hash_bytes` from S0.2.2 (raw 32 bytes).

**Algorithm (sorted tuple-hash; no XOR):**

1. Validate: basenames in 𝓐 are **ASCII** and **unique** within the set; error on duplicates.
2. Sort 𝓐 by basename (ASCII).
3. Build `U = T(a₁) || T(a₂) || … || T(a_k) || git_32 || parameter_hash_bytes`.
4. `manifest_fingerprint_bytes = SHA256(U)`;
   `manifest_fingerprint = hex64(manifest_fingerprint_bytes)`.

**Properties:** Any change to an opened artefact’s **bytes or basename**, the **commit**, or the **parameter bundle** flips the fingerprint. No XOR cancellation risk.

**Storage effect (normative):** Egress & validation datasets **must** partition by `fingerprint={manifest_fingerprint}` (often alongside `seed`).

**Errors (abort S0):**
`E_ARTIFACT_EMPTY`, `E_ARTIFACT_IO(name,errno)`, `E_ARTIFACT_NONASCII_NAME`, `E_ARTIFACT_DUP_BASENAME`, `E_GIT_BYTES`, `E_PARAM_HASH_ABSENT`.

**Audit rows:**
`manifest_fingerprint_resolved`: `{ manifest_fingerprint, artifact_count, git_commit_hex, parameter_hash }`.
*(Where `git_commit_hex` is the lower-case hex of `git_32`.)*

---

## S0.2.4 `run_id` (logs only; not modelling state)

**Goal.** Give each execution its own log partition key; **must not** affect RNG or outputs.

**Inputs:**
`manifest_fingerprint_bytes` (32), `seed` (u64; the modelling seed), start time `T_ns` = **UTC nanoseconds** (u64).

**Algorithm (UER payload):**

```
payload = UER("run:1A") || manifest_fingerprint_bytes || LE64(seed) || LE64(T_ns)
r = SHA256(payload)[0:16]      # first 16 bytes
run_id = hex32(r)
```

**Uniqueness (normative):** If a newly computed `run_id` already exists in the target log directory for `{ seed, parameter_hash }`, deterministically adjust `T_ns` by adding `+1` nanosecond and recompute. Repeat until the `run_id` is unused. This loop MUST be bounded by 2^16 steps; exceeding it is a hard failure. `run_id` never influences modelling outputs.
 
**Scope & invariants (normative):**

* Partitions **only** `rng_audit_log`, `rng_trace_log`, and `rng_event_*` as `{ seed, parameter_hash, run_id }`.
* `run_id` **never** enters RNG seeding or model state; all determinism/outputs depend **only** on `(seed, parameter_hash, manifest_fingerprint)`.
 
---

## Partitioning contract (authoritative)

| Dataset class       | Partition keys (in order)          |
|---------------------|------------------------------------|
| Parameter-scoped    | `parameter_hash`                   |
| Egress & validation | `manifest_fingerprint`             |
| RNG logs & events   | `seed`, `parameter_hash`, `run_id` |

*(Row-embedded key columns must equal their path keys byte-for-byte.)*

---

## Operational requirements

* **Streaming digests:** compute all file digests via streaming; hash exact bytes.
* **Race guard:** `stat` (size, mtime) **before/after** hashing; if changed, re-read or fail (`E_PARAM_RACE` / `E_ARTIFACT_RACE`).
* **Basename semantics:** sort by **basename** (no directories); basenames must be ASCII, unique; **abort** on duplicates.
* **Immutability:** After S0.2, treat `parameter_hash` & `manifest_fingerprint` as **final** for the run; embed them in all envelopes/partitions.

---

## Failure semantics

On any `E_PARAM_*`, `E_ARTIFACT_*`, `E_GIT_*`, race error or `E_RUNID_COLLISION_EXHAUSTED` (loop exceeded 2^16) abort the run per S0.9. On abort in S0.2, **do not** emit RNG audit/trace; S0.3 hasn’t begun.

---

## Validation & CI hooks

* **Recompute:** CI recomputes `parameter_hash` from 𝓟 and `manifest_fingerprint` from (enumerated 𝓐, `git_32`, `parameter_hash_bytes`). Must match logged `*_resolved` rows.
* **Partition lint:** dictionary enforces the partition table above; RNG logs must use `{ seed, parameter_hash, run_id }`.
* **Uniqueness:** within `{ seed, parameter_hash }`, `run_id` must be unique (practically guaranteed; guards clock bugs).

---

## Reference pseudocode (language-agnostic)

```text
# --- u32/u64 encoders per UER ---
def enc_str(s): b=s.encode("utf-8"); return le32(len(b)) + b
def enc_u64(x): return le64(x)

# --- parameter_hash ---
def compute_parameter_hash(P_files):  # list of (basename, path)
    assert len(P_files) >= 1, E_PARAM_EMPTY
    assert all_ascii_unique_basenames(P_files), E_PARAM_NONASCII_NAME or E_PARAM_DUP_BASENAME
    files = sort_by_basename_ascii(P_files)
    tuples = []
    for (name, path) in files:
        d = sha256_stream(path)                   # 32 bytes
        t = sha256_bytes(enc_str(name) + d)       # 32 bytes
        tuples.append(t)
    C = b"".join(tuples)
    H = sha256_bytes(C)                           # 32 bytes
    return hex_lower_64(H), H                     # hex64 + raw

# --- manifest_fingerprint ---
def compute_manifest_fingerprint(artifacts, git32, param_bytes):
    assert artifacts, E_ARTIFACT_EMPTY
    assert len(git32) == 32, E_GIT_BYTES
    assert len(param_bytes) == 32, E_PARAM_HASH_ABSENT
    assert all_ascii_unique_basenames(artifacts), E_ARTIFACT_NONASCII_NAME or E_ARTIFACT_DUP_BASENAME
    arts = sort_by_basename_ascii(artifacts)      # list of (basename, path)
    parts = []
    for (name, path) in arts:
        d = sha256_stream(path)                   # 32 bytes
        t = sha256_bytes(enc_str(name) + d)       # 32 bytes
        parts.append(t)
    U = b"".join(parts) + git32 + param_bytes
    F = sha256_bytes(U)
    return hex_lower_64(F), F

# --- run_id ---
def derive_run_id(fingerprint_bytes, seed_u64, start_time_ns):
    payload = enc_str("run:1A") + fingerprint_bytes + enc_u64(seed_u64) + enc_u64(start_time_ns)
    r = sha256_bytes(payload)[:16]                # 16 bytes
    return hex_lower_32(r)
```

---

## Where this shows up next

S0.3 derives the master RNG seed/counters using `manifest_fingerprint_bytes` and `seed`. Therefore S0.2 **must** complete before any RNG event emission.

---

**Bottom line:** S0.2 now uses a **tuple-hash, name-aware, length-prefixed** combiner (no XOR), with universal encoding rules and raw commit bytes. The partitioning contract is crystal-clear, and `run_id` is log-only. This is ready to hand straight to an implementer.

---

# S0.3 — RNG Engine, Substreams, Samplers & Draw Accounting (normative, fixed)

> **Notation (normative):** `ln(x)` denotes the natural logarithm. The unqualified `log` MUST NOT appear in kernels or acceptance tests.

## Purpose

S0.3 pins the *entire* randomness contract for 1A: which PRNG we use, how we carve it into **keyed, order-invariant** substreams, how we map bits to **(0,1)**, how we generate $Z\sim\mathcal N(0,1)$, $\Gamma(\alpha,1)$, and $\text{Poisson}(\lambda)$, and how every draw is **counted, logged, and reproducible**. **S0.3 does not consume RNG events; it defines the contracts and writes the single audit row only (no draws in S0).**

---

## S0.3.1 Engine & Event Envelope
> **Practical bound (normative):** `blocks` is `uint64`. Producers MUST ensure a single event’s block consumption fits this width. If an event would exceed this bound, emit `F4d:rng_budget_violation` and abort the run.

### PRNG (fixed)

* **Algorithm:** Philox 2×64 with 10 rounds (counter-based; splittable).
* **Wire token (normative):** `philox2x64-10` (lowercase). Validators MUST expect this exact token wherever the RNG algorithm is named on the wire (e.g., `rng_audit_log.algorithm`).
> **Counter (normative):** The Philox **counter is 128-bit**, represented as the ordered pair $(c_{\mathrm{hi}}, c_{\mathrm{lo}})$ of unsigned 64-bit integers. All counters in envelopes are these same two words. Any prior 4-word notation is non-normative and MUST NOT be used. The block function advances the counter by **1** (unsigned 128-bit add with carry from `lo` into `hi`).
* **State per substream:** 64-bit **key** $k$ and 128-bit **counter** $c=(c_{\mathrm{hi}},c_{\mathrm{lo}})$.
* **Block function:** $(x_0,x_1)\leftarrow \mathrm{PHILOX}_{2\times64,10}(k,c)$ returns **two** 64-bit words per counter; then increment $c\leftarrow c+1$ mod $2^{128}$.
* **Lane policy (normative):**
  * **No caching (normative):** Families that require two uniforms **must not** reuse, pool, or cache normals/uniforms across events. Each event **must** fetch a fresh block per the lane policy.
  * **Clarification:** “Use low lane” means **read `x0` and advance the counter by 1 block**; the high lane `x1` is discarded and **may not** be reused later.
  * **Single-uniform events:** use **low lane** $x_0$, **discard** $x_1$; advance counter by 1 block; `draws="1"`.
  * **Two-uniform events (e.g., Box–Muller):** use **both lanes** from the same block; advance counter by 1 block; `draws="2"`.
  * No other reuse or caching of lanes is permitted.

### Event envelope (mandatory fields on **every** RNG event row)
> **Note:** Audit/trace logs are governed by `schemas.layer1.yaml#/rng/core/*` and **do not** embed the event envelope.


```
{
  ts_utc:                  string  # RFC 3339 / ISO-8601 UTC (exactly 6 fractional digits), e.g. "2025-08-15T10:03:12.345678Z"
  module:                  string  # e.g. "1A.gumbel_sampler" (registered producer name)
  substream_label:         string  # e.g. "gumbel_key", "dirichlet_gamma_vector"
  seed:                    uint64  # modelling seed (from S0.2)
  parameter_hash:          string  # hex64 (S0.2)
  manifest_fingerprint:    string  # hex64 (S0.2)
  run_id:                  string  # hex32 (S0.2)
  rng_counter_before_lo:   uint64
  rng_counter_before_hi:   uint64
  rng_counter_after_lo:    uint64
  rng_counter_after_hi:    uint64
  blocks:                  uint64   # PHILOX blocks advanced by this event
  draws:                   string   # decimal-encoded uint128; required; **UNIFORMS** used by this event (family budgets check against this); e.g., "0", "2").
  payload: { ... }                 # event-specific fields (flattened into top-level fields by the event schema; schema ensures global name uniqueness; name collisions are compile-time schema errors.)
}
```

> **Order note:** Fields are serialized in **lo, hi** order (`*_before_lo`, `*_before_hi`, `*_after_lo`, `*_after_hi`). For arithmetic, form 128-bit integers as the pair **(hi, lo)**, i.e. `U = (hi << 64) | lo`.

* **Module governance (normative):** `module` MUST equal one of the **registered producer names** in the dataset dictionary for 1A (e.g., `1A.hurdle_sampler`, `1A.nb_sampler`, `1A.gumbel_sampler`).
* **Label governance (normative):** `substream_label` MUST be one of the labels published in the artefact `rng_event_schema_catalog` (manifest_key `mlr.rng.events.schema_catalog`) and validators MUST enforce membership.


> **Blocks vs draws (normative):** `blocks = (after_hi,after_lo) − (before_hi,before_lo)` in unsigned 128-bit arithmetic. `draws` = **uniforms used**. Single-uniform families: `(blocks=1, draws="1")`. Two-uniform families (e.g., Box–Muller): `(blocks=1, draws="2")`. Non-consuming: `(blocks=0, draws="0")`. The `blocks` equality is checked by counters; `draws` is checked by family budgets.

> **Invariants (normative):**
> - `blocks` = $(\texttt{after_hi},\texttt{after_lo}) - (\texttt{before_hi},\texttt{before_lo})$ in unsigned 128-bit arithmetic. (authoritative equality check).
> - `draws` = number of **uniform(0,1)** variates consumed by the event. (independent of the counter delta).
> - With the lane policy, **single-uniform** events have `(blocks=1, draws="1")`, and **two-uniform** events (Box–Muller) have `(blocks=1, draws="2")`. **Non-consuming** events have `(blocks=0, draws="0")`.

* **Non-consuming** events keep `before == after` and set `blocks = 0`.
* `module` and `substream_label` must be chosen from the 1A vocabulary registry enumerated in `schemas.layer1.yaml#/rng/events/*`; free-text labels are not allowed.

* When a family-level **uniforms-used** count is relevant **for diagnostics**, may include an optional `uniforms: string` (decimal-encoded `uint128`, same domain as `draws`) in `payload` **only for** `gamma_component` and `dirichlet_gamma_vector`; when present, validators MUST check it equals `draws`.

**Encoding notes (normative):**
* **Authority (normative):** An event’s envelope `draws` MUST equal the kernel’s computed uniform count for that event. Counters remain the authority for `blocks`.
* `blocks` ≠ (`after` − `before`) ⇒ `F4c: rng_counter_mismatch`
* `draws` ≠ budgeted/actual uniforms ⇒ `F4d: rng_budget_violation`.
> **Budget table (normative authority for S0):**
> - `uniform1` (single-uniform families): `(blocks=1, draws="1")`  
> - `normal` (Box–Muller): `(blocks=1, draws="2")`  
> - `gamma_component`: **variable**, per §S0.3.6 (exact actual-use)  
> - `dirichlet_gamma_vector`: **sum of component** `gamma_component` budgets  
> - `poisson_component (λ<10)`: **variable**, inversion (§S0.3.7)  
> - `poisson_component (λ≥10)`: **2 uniforms/attempt**, PTRS (§S0.3.7)  
> - `stream_jump`: `(blocks=0, draws="0")` — **non-consuming** (before==after)  
> - `sequence_finalize`: `(blocks=0, draws="0")` — **non-consuming** (before==after)  
> - `site_sequence_overflow`: `(blocks=0, draws="0")` — **non-consuming** (before==after)  


* `draws` is a **JSON string** carrying a **base-10** representation of a `uint128`. Producers/consumers **must** parse/emit as decimal and **must not** split into lo/hi words in the envelope (use the decimal string everywhere, mirroring S0.9 failure payloads).
* `ts_utc` in RNG **events** is an **RFC-3339/ISO-8601 UTC string** with **exactly 6 fractional digits** (microseconds), e.g., `"2025-08-15T10:03:12.345678Z"`. `ts_utc` in **failures** is **epoch-nanoseconds** (they are **nanoseconds since epoch** as an unsigned integer). See **§S0.9 “Failure records”** for failure-record timestamps (epoch-ns u64).

* **Serialization note:** Envelope counter fields (`rng_counter_*_{hi,lo}`) and `blocks` are **numbers**; `draws` is a **decimal string** (`uint128` in base-10, per schema). Endianness (LE/BE) applies only to **derivations** (hash splits, Philox counters); JSON serialisation is endianness-agnostic.


---

## S0.3.2 Master seed & initial counter (per run)
> **LOW64(digest32) (normative):** interpret **bytes 24..31** of the 32-byte SHA‑256 digest as **little‑endian u64** (same convention as §S0.1). **Counters** are always split as `BE64(H[16:24]), BE64(H[24:32])`.
> **Use of LOW64:** Whenever `LOW64(H)` appears (e.g., key derivation), it refers to this exact LE64 tail-bytes rule.

Let:

* `seed` = user/model seed (u64, from S0.2),
* `manifest_fingerprint_bytes` (32 bytes, from S0.2).

Define **master material** (UER = universal encoding rule from S0.2):

```
M = SHA256( UER("mlr:1A.master") || manifest_fingerprint_bytes || LE64(seed) )  # 32 bytes
```

> **UER domain strings (normative):** `b"mlr:1A.master"` for master-material; `b"mlr:1A"` for substream messages; event-family labels `ℓ` are ASCII (e.g., `b"hurdle_bernoulli"`, `b"gumbel_key"`). These exact byte sequences are part of the hash inputs.

Derive **root** (audit-only; never used directly for draws):

* Root key:     $k_\star = \text{LOW64}(M)$.
* Root counter: $(c_{\star,\mathrm{hi}}, c_{\star,\mathrm{lo}}) = (\text{BE64}(M[16:24]),\ \text{BE64}(M[24:32]))$.

> **`split64` (normative):** for a 16-byte string `b`, return `hi = u64_be(b[0..8])`, `lo = u64_be(b[8..16])`.

> Envelopes carry these same numeric values as `rng_counter_*_{hi,lo}`. All counter math is **unsigned 128-bit** with addition performed as `lo += n; carry → hi`.

> Emit a single `rng_audit_log` row **before** any draws with `seed`, `manifest_fingerprint`, `parameter_hash`, `run_id`, and $(k_\star,c_\star)$. **No event** may draw from $(k_\star,c_\star)$. (schema: `schemas.layer1.yaml#/rng/core/rng_audit_log`).
> **Schema separation (normative):** `rng_audit_log` rows are **not** RNG events and MUST NOT be encoded with the event envelope. They carry the audit schema only and **must** precede the first RNG event.

---

## S0.3.3 Keyed, order-invariant substreams

Every logical substream is keyed by a deterministic tuple; **never** by execution order.

### Substream derivation (UER, no delimiters) *(SER = integer encodings under UER: LE32 indices; LE64 keys)*
* **Indices (`i`,`j`, …):** 0-based, unsigned, encoded as **LE32**; must satisfy `0 ≤ value ≤ 2^32−1`; negative values are forbidden.
* **ISO encoding (normative):** `iso` MUST be **uppercase ASCII** before UER. If a lower-case code is encountered, **uppercase it** deterministically prior to encoding.

> **UER/SER recap (normative):**
> - **UER (strings):** UTF-8 bytes prefixed by a 32-bit **little-endian** length; concatenation is unambiguous and order-sensitive.  
> - **SER(ids):** integers are **LE32** (indices) or **LE64** (u64 keys); all indices are **0-based** and unsigned.  
> - **ISO codes:** uppercase ASCII under UER.
> These are the only encodings allowed for hashing and substream derivation in §S0.3.

For an event family label `ℓ` (e.g., `"hurdle_bernoulli"`, `"gumbel_key"`) and an ordered ID tuple **ids** (event-family-specific; e.g., `(merchant_u64, iso)`), build:

```
msg = UER("mlr:1A") || UER(ℓ) || SER(ids)
H   = SHA256( M || msg )              # 32 bytes
k(ℓ,ids) = LOW64(H)
c(ℓ,ids) = ( BE64(H[16:24]), BE64(H[24:32]) )   # 128-bit counter (hi,lo)
```

* **SER(ids)** uses UER per component, with **types fixed by schema**:

  * `merchant_u64` (from S0.1 mapping): LE64
  * `iso` (uppercase ISO-3166 alpha-2): UER string (length-prefixed UTF-8)
  * indices `i`, `j`: LE32
  * any other id types must be enumerated in the event schema
* All draws for that event must come from `PHILOX(k(ℓ,ids),·)` by advancing `c` monotonically.

---

## S0.3.4 Uniforms on the **open** interval $(0,1)$

**Normative mapping:**

```text
# x is u64; map to strictly (0,1) — never 0.0, never 1.0
u = ((x + 1) * 0x1.0000000000000p-64)
if u == 1.0: u := 0x1.fffffffffffffp-1   # max < 1 in binary64 (1 - 2^-53)
```

This is the required implementation of the open-interval rule. Computing `1/(2^64+1)` at runtime or using decimal literals is **forbidden**.

## S0.3.5 Standard normal $Z\sim\mathcal N(0,1)$ (Box–Muller, no cache)

**Constants (normative):** `TAU = 0x1.921fb54442d18p+2` (binary64-exact). Computing `2*pi` at runtime is **forbidden** to avoid libm drift. (See constant `TAU` defined once in §S0.3.5.)

To sample **one** $Z$:


1. Draw a **single** Philox block → $(x_0,x_1)$.
2. Map $u_1 = u01(x_0),\ u_2 = u01(x_1)$.
3. Compute $r=\sqrt{-2\ln u_1},\ \theta=\mathrm{TAU}\cdot u_2,\ Z=r\cos\theta$.

Budget & rules:

* **Budget:** exactly **2 uniforms** per $Z$ (1 block).
* **No caching:** **discard** the companion normal $r\sin\theta$.
* **Envelope requirement (normative):** Each Box–Muller event MUST set `blocks=1` and `draws="2"`.
* **Numeric policy:** binary64, round-to-nearest-ties-even, FMA **off**, no FTZ/DAZ; evaluation order is as written (per S0.8).

* **Constants (normative):** All decision-critical constants (e.g., `TAU`) **MUST** be provided as **binary64 hex literals**. Recomputing from other constants (e.g., `2*pi`) is forbidden.

---

## S0.3.6 Gamma $\Gamma(\alpha,1)$ (Marsaglia–Tsang; exact actual-use budgeting)
> **Case B (α<1) clarification (normative):** boosting draws `G' ~ Γ(α+1)` and then **+1 uniform** for `U`; **no** dummy or padding draws are permitted; envelope `draws` reflects exact actual use.

We use Marsaglia–Tsang (2000). Budgets reflect the **exact number of uniforms consumed** (no padding or dummy draws). Normals come from §S0.3.5 (two uniforms per normal). All uniforms use §S0.3.4.

**Case A: $\alpha\ge 1$**  (set $d=\alpha-\tfrac13$, $c=1/\sqrt{9d}$)

Repeat:
1. Draw **one** standard normal $N$ via Box–Muller → **2 uniforms**; `(blocks+=1, draws+=2)`.
2. Compute $v=(1+cN)^3$. If $v\le 0$, **reject** and go to step 1 (no extra uniforms consumed in this branch).
3. Draw $U\sim\mathrm{Uniform}(0,1)$ → **+1 uniform**; `(draws+=1)`.
4. Accept iff $\ln U < \tfrac12 N^2 + d - d v + d\ln v$. If rejected, go to step 1.

On acceptance, return $G=dv$.  
**Budget per accepted sample:** $2A + B$ uniforms, where $A$ is the number of attempts and $B$ is the number of **U draws** (i.e., the attempts with $v>0$, including the final accepted attempt). There is **no fixed multiple**; the envelope `draws` records the exact count.

**Case B: $0 < \alpha < 1$**  (boosting)

1. Sample $G'\sim\Gamma(\alpha+1,1)$ via **Case A** (with its budgeting).
2. Draw $U\sim\mathrm{Uniform}(0,1)$ → **+1 uniform**.
3. Set $G = G'\cdot U^{1/\alpha}$ (pure arithmetic).

**Budget per accepted sample:** `draws(G') + 1` uniforms. There are **no dummy or padding draws**; counters reflect only actual consumption.

**Dirichlet vectors:** For shapes $(\alpha_1,\dots,\alpha_K)$, draw independent components with the kernel above and normalise. The total budget is the **sum** of component budgets; there is **no** “multiple of $3K$” rule. Envelope `draws` MUST equal that sum.

---

## S0.3.7 Poisson $\text{Poisson}(\lambda)$ & ZTP scaffolding

Two regimes; **Threshold (normative):** $\lambda^\star = 10$ (spec constant; not configurable). Changing it requires a spec revision and flips `manifest_fingerprint` per §S0.2.3.

**Small $\lambda<\lambda^\star$** — **Inversion**
Draw uniforms $u_1,u_2,\ldots$ and iterate the standard product until it falls below $e^{-\lambda}$.

* **Budget:** variable (**exactly** $K+1$ uniforms, including the stopping draw); log exactly in `draws`.

**Moderate/Large $\lambda\ge\lambda^\star$** — **PTRS (Hörmann-class) rejection (fully specified)**
Per-attempt draws: **two uniforms** $u,v\sim U(0,1)$ from **one Philox block** (lane policy).
**Constants (normative):**
${} \quad b = 0.931 + 2.53\sqrt{\lambda},\quad a = -0.059 + 0.02483\,b,\quad \mathrm{inv}\,\alpha = 1.1239 + \dfrac{1.1328}{b-3.4},\quad v_r = 0.9277 - \dfrac{3.6224}{b-2},\quad u_{\text{cut}}=0.86.$
**Attempt loop:**
1) Draw $(u,v)$.
2) If $u\le u_{\text{cut}}$ and $v\le v_r$: accept $k=\left\lfloor \dfrac{b\,v}{u} + \lambda + 0.43 \right\rfloor$.
3) Else set $u_s = 0.5 - |u-0.5|$, and form the candidate $k=\left\lfloor \bigl(\tfrac{2a}{u_s} + b\bigr) v + \lambda + 0.43 \right\rfloor$; if $k<0$, continue.
4) Accept iff
$\displaystyle \ln\!\Bigl(\frac{v\cdot \mathrm{inv}\,\alpha}{\,a/u_s^2 + b\,}\Bigr) \le -\lambda + k\ln\lambda - \log\Gamma(k+1).$
On acceptance return $K=k$; otherwise repeat from step 1.
**Budget:** **exactly 2 uniforms per attempt**; attempts repeat until acceptance. `draws` records the total used. All `\ln`, `\sqrt{\ }`, and `\log\Gamma` calls obey §S0.8 (pinned math profile).
 
**Zero-Truncated Poisson (ZTP)**
Handled by accept/reject on $\text{Poisson}(\lambda)$ conditioned on $N>0$. The `draws` field includes all uniforms across rejections.

**ZTP event budgets (normative):**
* Each `poisson_component(context="ztp")` event records the **actual** sampler consumption via the envelope counters.
* `ztp_rejection` and `ztp_retry_exhausted` are **non-consuming**: `before==after`, `blocks=0`, `draws="0"`.
* Hard cap: **64** zero outcomes; on exhaustion, emit `ztp_retry_exhausted` and branch per S4; budgets remain as above.
 
---

## S0.3.8 Gumbel key from a single uniform

For candidate ranking:

* Draw $u\in(0,1)$; compute $g=-\ln(-\ln u)$.
* **Budget:** **1 uniform** per candidate (single-lane low; event-level `draws="1"`).
* **Tie-break:** sort primarily by $g$, then by `ISO` (ASCII ascending), then by `merchant_id` if still tied.
* **Log:** one `gumbel_key` event **per candidate**.

---

## S0.3.9 Draw accounting & logs (auditable replay)
> **Run policy (normative):** Although on-disk totals are saturating counters, producers MUST detect imminent overflow and raise `F4d:rng_budget_violation` **before** any saturation would occur.


Two cross-cut logs in addition to per-event logs:

1. **`rng_audit_log`** — **one row at run start** (before any RNG event): `(seed, manifest_fingerprint, parameter_hash, run_id, root key/counter, code version, ts_utc)`.
   **`rng_audit_log` schema (normative minimum):** `{ ts_utc, seed, parameter_hash, manifest_fingerprint, run_id, algorithm, rng_key_hi, rng_key_lo, rng_counter_hi, rng_counter_lo, code_version }`. Field types and names are governed by `schemas.layer1.yaml#/rng/core/rng_audit_log` (authoritative). Audit rows are **core logs**, not RNG events.
2. **`rng_trace_log`** (**one row per** $(\texttt{module},\texttt{substream_label})$; cumulative **blocks** (unsigned 64-bit), with the *current* `(counter_before, counter_after)`.  
   *(schema: `schemas.layer1.yaml#/rng/core/rng_trace_log`).*  

   **Reconciliation (normative):** For each `(module, substream_label)`, `rng_trace_log.blocks_total` MUST be monotone non-decreasing across emissions, and the **final** `blocks_total` MUST equal the **sum of per-event `blocks`** over `rng_event_*` in the same `{seed, parameter_hash, run_id}`. Budget checks use **event `draws`**, not the trace.
   **Lineage binding (normative):** Producers and consumers **MUST** bind `{ seed, parameter_hash, run_id }` from the enclosing **partition path**. In `rng_trace_log`, **`seed` and `run_id` are also embedded columns** and **must equal** the path keys byte-for-byte; **`parameter_hash` is path-only**. (Drift is a hard F5 failure.)

> **Practical bound (normative):** `rng_trace_log.blocks_total` is `uint64`; emitters MUST ensure totals fit this width or abort with `F4d:rng_budget_violation`.

**Per-event budget rules are enforced **exactly as specified in §S0.3.1 (Budget table)**.

**Envelope invariants:**

* Philox blocks advance consistently with lane policy: single-uniform events advance **one** block (high lane discarded); two-uniform events consume **both lanes** of one block.
* `rng_counter_after` ≥ `rng_counter_before` lexicographically; non-consuming events keep them equal.

---

## S0.3.10 Determinism & failure semantics

**Must hold:**

1. **Order-invariant:** keyed substreams make outputs independent of execution order/sharding.
2. **Open-interval uniforms:** $u\in(0,1)$ strictly (S0.3.4).
3. **Budget correctness:** per-event budgets satisfied (Normals §S0.3.5; Gamma §S0.3.6; Poisson/ZTP §S0.3.7).
4. **Numeric profile:** binary64, no FMA, serial reductions (S0.8).

**Abort the run if:**

* An event’s `blocks` disagrees with the 128-bit counter delta implied by the envelope (`after − before`).
* Any sampler yields NaN/Inf.
* A non-consuming event changes counters.
* A Gamma/Dirichlet event’s `draws` mismatches the recomputed exact budget per §S0.3.6.
---

## Reference pseudocode (language-agnostic)

```text
# Philox
struct Stream { key: u64, ctr: u128 }      # conceptual; envelope exposes (lo,hi) pairs
fn philox_block(s: Stream) -> (u64,u64,Stream) {
  (x0,x1) = PHILOX_2x64_10(s.key, s.ctr)
  s.ctr += 1
  return (x0,x1,s)
}

# u01 mapping (open interval)
fn u01(x: u64) -> f64 {
  # Binary64; strict (0,1) open interval — never 0.0, never 1.0
  const TWO_NEG_64:    f64 = 0x1.0000000000000p-64;   # 2^-64
  const ONE_MINUS_EPS: f64 = 0x1.fffffffffffffp-1;    # 1 - 2^-53 (max < 1 in binary64)
  let u = ((x as f64) + 1.0) * TWO_NEG_64;
  return (u == 1.0) ? ONE_MINUS_EPS : u
}
* **Note (normative):** The `u==1.0` remap is a **measure-zero** adjustment required by binary64 rounding and **does not** affect PRNG budgets or counter deltas. The schema type **`u01`** enforces the open interval **(0,1)**.

# Single uniform (lane policy)
fn uniform1(stream: &mut Stream) -> (f64, draws:int) {
  let (x0, _x1, s2) = philox_block(*stream)   # fetch 1 block; discard high lane
  *stream = s2
  return (u01(x0), 1)
}

# Normal Z via Box–Muller (no cache)
fn normal(stream: &mut Stream) -> (f64, draws:int) {
  let (x0, x1, s2) = philox_block(*stream)    # fetch 1 block; use both lanes
  *stream = s2
  let u1 = u01(x0); let u2 = u01(x1)
  let r  = sqrt(-2.0 * ln(u1))
  # τ = 2π (binary64 hex literal to avoid libm/macro drift)
  const TAU: f64 = 0x1.921fb54442d18p+2;
  let th = TAU * u2
  return (r * cos(th), 2)
}

# Gamma(alpha,1) with budget discipline
fn gamma_mt(alpha: f64, stream: &mut Stream) -> (f64, draws:int) {
  if alpha >= 1.0 {
    let d = alpha - (1.0/3.0);
    let c = 1.0 / sqrt(9.0 * d);
    var total = 0;
    loop {
      let (z, dZ) = normal(stream);       # Box–Muller → 2 uniforms (1 block)
      total += dZ;
      let v = (1.0 + c*z); v = v*v*v;
      if v <= 0.0 { continue; }
      let (u, dU) = uniform1(stream);     # +1 uniform
      total += dU;
      if ln(u) <= 0.5*z*z + d - d*v + d*ln(v) {
        return (d*v, total);              # exact actual-use budgeting
      }
    }
  } else {
    let (y, dY) = gamma_mt(alpha + 1.0, stream);  # recurse to Case A
    let (u, dU) = uniform1(stream);               # +1 uniform
    return (y * pow(u, 1.0/alpha), dY + dU);
  }
}

# Poisson scaffolding (sketch)
fn poisson(lambda: f64, stream: &mut Stream) -> (int, draws:int) {
  if lambda < 10.0 {
    L = exp(-lambda); k = 0; p = 1.0; draws = 0
    loop:
      (u, dU) = uniform1(stream); draws += dU
      p *= u
      if p <= L { return (k, draws) } else { k += 1 }
  } else {
    # PTRS attempt: (u,v) -> 2 uniforms/attempt; repeat until accept.
  }
}
```

---

## Guarantees to downstream states

* Any module declares `(substream_label, ids)` and receives a **stable, independent** substream—order/shard-invariant.
* Samplers have **pinned** budgets (constant where possible; fully logged where variable).
* Given `(seed, parameter_hash, manifest_fingerprint, run_id)` and the envelopes, every draw is **replayable exactly**.

---

**Summary:** S0.3 pins Philox 2×64-10, the **low-lane policy** for single uniforms, **UER-based** substream derivation, one **open-interval** `u01`, Box–Muller (**no cache**), Gamma (Marsaglia–Tsang) with **exact actual-use budgeting**, Poisson with a **fully specified** inversion/PTRS split, and strict **draw accounting** tied to counters. This is deterministic, auditable, and ready to implement. Gumbel keys break ties by ISO, then merchant_id.

---

# S0.4 — Deterministic GDP Bucket Assignment (normative, fixed)

## Purpose

Attach to every merchant $m$ two **deterministic**, **non-stochastic** features from pinned references:

* $g_c$ — GDP-per-capita level for the merchant’s **home** country $c$ from the **2025-04-15** WDI extract, **at a fixed observation year** (see below), and
* $b_m\in\{1,\dots,5\}$ — the **Jenks** $K{=}5$ GDP bucket id for that home country from the **precomputed** mapping table.

**No RNG** is consumed here. S0.4 is a pure function of bytes fixed by S0.1–S0.2.

---

## Inputs & domains (read-only, pinned)

* **Ingress universe:** `merchant_ids` carrying `merchant_id`, `mcc`, `channel`, `home_country_iso`.
  `home_country_iso` is **uppercase ASCII ISO-2** and FK-validated against the run’s ISO set (S0.1).

* **GDP vintage (total function $G$):** artefact `world_bank_gdp_per_capita_20250415`.
  Schema guarantees **exactly one** row per `(country_iso, observation_year)` with a strictly positive value.

  **Normative pinning (this run):**

  * `observation_year = 2024` (fixed),
  * **units/deflator**: *constant 2015 USD* (as recorded in the artefact metadata),
  * so $G:\mathcal I \to \mathbb R_{>0}$ is the map $c \mapsto \text{GDPpc}_{c,2024}^{\text{const2015USD}}$.

* **Bucket map (total function $B$):** artefact `gdp_bucket_map_2024` with PK `country_iso` and `bucket ∈ {1..5}`.
  **It is a precomputed Jenks $K{=}5$ classification built from the exact $G(\cdot)$ above** (same ISO set, same `observation_year`, same units). **Never recomputed at runtime.**

> Both artefacts are enumerated in the registry/dictionary as runtime, read-only inputs and therefore are included in the **manifest fingerprint** (S0.2). Any byte change flips the fingerprint.

---

## Canonical definition (what S0.4 does)

For $m\in\mathcal M$ with $c=\texttt{home_country_iso}(m)\in\mathcal I$,

$$
g_c \leftarrow G(c)\in\mathbb R_{>0},\qquad
b_m \leftarrow B(c)\in\{1,2,3,4,5\}.
$$

These are **lookups** only; **no** thresholds are calculated at runtime.

---

## Semantics & downstream usage

* $b_m$ (Jenks bucket) appears **only** in the hurdle design as five one-hot dummies (column order frozen by the fitting bundle).
* $\log g_c$ appears **only** in NB **dispersion** (never in the mean).
* If materialised, these features live under `…/parameter_hash={parameter_hash}/` (parameter-scoped model artefacts), governed by `schemas.1A.yaml` (e.g., `#/model/hurdle_design_matrix`, `#/model/hurdle_pi_probs`). They are otherwise transient into S0.5.

---

## Determinism & numeric policy

* **No randomness;** outputs identical across shards and reruns with the same `manifest_fingerprint`.

* Any derived transforms (e.g., $\log g_c$ in S0.5) use **binary64**, no FMA, serial evaluation order (S0.8).

* **Class semantics (for CI intuition only):** if $B$ were rebuilt, thresholds $\tau_0<\dots<\tau_5$ satisfy
  $B(c)=k \iff G(c)\in(\tau_{k-1},\tau_k]$ (classes are **right-closed**). The *authoritative* truth remains the shipped table $B$.

---

## Failure semantics (abort; zero tolerance)

Abort with a clear message (including offending dataset and PK) if any holds:

* `E_HOME_ISO_FK(m,c)`: `home_country_iso` not in the run’s ISO set (S0.1).
* `E_GDP_MISSING(c)`: no GDP row for `c` at `observation_year=2024`.
* `E_GDP_NONPOS(c, g_c)`: GDP value $\le 0$ (double-guard; schema forbids).
* `E_BUCKET_MISSING(c)`: no bucket row for `c` in `gdp_bucket_map_2024`.
* `E_BUCKET_RANGE(c, b)`: bucket not in $\{1..5\}$ (double-guard; schema forbids).

---

## Validation hooks (runtime & CI)

1. **Coverage:** every `home_country_iso` in `merchant_ids` has both $G(c)$ and $B(c)$.
2. **FK integrity:** all `country_iso` in GDP & bucket tables are members of the run’s ISO set.
3. **Lineage evidence:** both artefacts are present in the **manifest fingerprint** enumeration (counts & digests logged by S0.2).
4. **Optional CI rebuild (non-runtime):** recompute Jenks $K{=}5$ from the pinned $G(\cdot)$ and assert equality with `gdp_bucket_map_2024`; fail with a per-ISO diff if not identical.

---

## Optional rebuild spec for $B$ (CI only; deterministic)

Goal: optimal 1-D 5-class partition (Jenks / optimal $k$-means DP) over $\{G(c)\}$.

Deterministic procedure (binary64):

1. Build sorted vector $y_1\le\dots\le y_n$ of GDP values; **stable sort by `(value, iso)`** to make ties deterministic.
2. Prefix sums $S_k=\sum_{i\le k}y_i,\ Q_k=\sum_{i\le k}y_i^2$.
3. DP: $ \text{SSE}(a..b)=Q_b-Q_{a-1}-\frac{(S_b-S_{a-1})^2}{b-a+1}$.
   $D[b,1]=\text{SSE}(1..b);\quad D[b,j]=\min_{a\in[j..b]} D[a-1,j-1]+\text{SSE}(a..b)$.
   Keep backpointers $P[b,j]$.
4. Backtrack at $(b{=}n,j{=}5)$ → split indices $t_1 < \dots < t_4$.
5. Thresholds: $\tau_1=y_{t_1},\dots,\tau_4=y_{t_4}$; classes are **right-closed**.
6. **Tie handling:** if multiple optima exist in flat regions, choose the **lexicographically smallest** $(t_1,\dots,t_4)$ (prefer earlier splits).
7. Map $B(c)=k$ iff $G(c)\in(\tau_{k-1},\tau_k]$. Emit a deterministic diff if any ISO’s bucket differs from `gdp_bucket_map_2024`.

---

## Reference routine (runtime path; language-agnostic)

```text
function S0_4_attach_gdp_features(M, I, G, B):
  # Inputs:
  #   M: merchant_ids (merchant_id, mcc, channel, home_country_iso)
  #   I: ISO-2 set (uppercase ASCII)
  #   G: map ISO -> R>0 for observation_year=2024 (const 2015 USD)
  #   B: map ISO -> {1..5} from gdp_bucket_map_2024
  # Output: iterator of (merchant_id, g_c, b_m)

  for row in M:
      m = row.merchant_id
      c = row.home_country_iso

      assert c in I, E_HOME_ISO_FK(m,c)

      g = G.get(c)                       # must exist; > 0
      if g is None: raise E_GDP_MISSING(c)
      if not (g > 0.0): raise E_GDP_NONPOS(c, g)

      b = B.get(c)                       # must exist; in 1..5
      if b is None: raise E_BUCKET_MISSING(c)
      if not (1 <= b <= 5): raise E_BUCKET_RANGE(c, b)

      yield (m, g, b)                    # carried transiently into S0.5 or materialised under parameter_hash
```

---

## Complexity, concurrency, partitions

* **Time:** $O(|\mathcal M|)$ hash lookups; **Space:** $O(1)$ per streamed row.
* **Parallelism:** embarrassingly parallel; determinism holds (pure lookups).
* **Lineage & partitions:** both GDP and bucket artefacts are in the **manifest fingerprint**; changing either flips egress partitions. If features are materialised into design artefacts, they are **parameter-scoped** (partitioned by `parameter_hash` only; **do not** embed `manifest_fingerprint` in parameter-scoped tables).

---

**Bottom line:** S0.4 is a strict, zero-RNG lookup that attaches $(g_c,b_m)$ from a *single*, pinned GDP vintage (obs-year 2024, const-2015-USD) and its precomputed Jenks-5 map. Rebuild rules are deterministic (CI-only), class semantics are right-closed, failure codes are explicit, and storage/lineage boundaries are clear—so S0.5+ can consume these as immutable inputs.

---

# S0.5 — Design Matrices (Hurdle & NB), Column Discipline, and Validation (normative, fixed)

## Purpose & scope

Deterministically construct **column-aligned design vectors** for each merchant $m$ for:

* the **hurdle logistic** (single vs. multi) used in **S1**, and
* the **Negative-Binomial (NB)** branch used in **S2** (mean and dispersion links).

**Column dictionaries and ordering are frozen by the model-fitting bundle** and are **never recomputed at runtime**. **No RNG** is consumed here.

---

## Inputs (read-only; pinned by S0.1–S0.4)

* From **ingress/S0.1** (validated & mapped already):
  `merchant_id`, `mcc`, `channel_sym ∈ {CP,CNP}`, `home_country_iso`.
* From **S0.4**:
  $g_c=G(c)>0$ (GDP per-capita for home ISO $c$), and $b_m=B(c)\in\{1,\dots,5\}$ (Jenks-5 bucket). Pure lookups.
* From the **fitting bundle** (parameter-scoped artefacts whose bytes affect `parameter_hash`):

  * **Column dictionaries** (with **frozen order**):

    * MCC dummies (size $C_{\text{mcc}}$).
    * Channel dummies (size 2) with **canonical order** `["CP","CNP"]`.
    * GDP-bucket dummies (size 5) with order `[1,2,3,4,5]`.
    * *(Dictionaries are shipped together with coefficients; their byte order is authoritative.)*
  * **Coefficient vectors**:

    * **Hurdle** $\beta$ — a **single** YAML vector containing: intercept, MCC block, channel block, **all 5** bucket dummies.
    * **NB dispersion** coefficients — intercept, MCC block, channel block, and **slope on $\ln g_c$**.
      *(NB mean excludes GDP bucket by design.)*

> **Global design rule (normative):** **GDP bucket enters only the hurdle**; **$\ln g_c$** enters **only** NB **dispersion**. The builder **must** assert this at construction time.

---

## Encoders (deterministic one-hots; column-frozen)

Let the frozen dictionaries give column indices. Define one-hot encoders:

$$
\phi_{\text{mcc}}:\mathcal K\to\{0,1\}^{C_{\text{mcc}}},\quad
\phi_{\text{ch}}:\{\text{CP},\text{CNP}\}\to\{0,1\}^{2},\quad
\phi_{\text{dev}}:\{1,\dots,5\}\to\{0,1\}^{5},
$$

each returning a vector with **exactly one** 1 at the index dictated by its dictionary.
The **intercept** is always the leading scalar 1.

* **Channel vocabulary (normative):** the only internal symbols are `CP` and `CNP` (S0.1 mapping from ingress strings). The channel dictionary **must** be exactly `["CP","CNP"]`.

---

## Design vectors (definitions, dimensions, strict order)

For merchant $m$ with $c=\texttt{home_country_iso}(m)$, $g_c>0$, $b_m\in\{1,\dots,5\}$:

### Hurdle (logit) design

$$
\boxed{\,x_m=\big[1,\ \phi_{\text{mcc}}(\texttt{mcc}_m),\ \phi_{\text{ch}}(\texttt{channel_sym}_m),\ \phi_{\text{dev}}(b_m)\big]^\top\,}\in\mathbb R^{1+C_{\text{mcc}}+2+5}.
$$

$$
\eta_m=\beta^\top x_m,\qquad \pi_m=\sigma(\eta_m)=\frac{1}{1+e^{-\eta_m}}.
$$

All hurdle coefficients, including the 5 bucket dummies, are in **one** ordered vector $\beta$.

### Negative-Binomial (used in S2)

$$
\boxed{\,x^{(\mu)}_m=\big[1,\ \phi_{\text{mcc}}(\texttt{mcc}_m),\ \phi_{\text{ch}}(\texttt{channel_sym}_m)\big]^\top\,}\in\mathbb R^{1+C_{\text{mcc}}+2},
$$

$$
\boxed{\,x^{(\phi)}_m=\big[1,\ \phi_{\text{mcc}}(\texttt{mcc}_m),\ \phi_{\text{ch}}(\texttt{channel_sym}_m),\ \ln g_c\big]^\top\,}\in\mathbb R^{1+C_{\text{mcc}}+2+1}.
$$

**Leakage guard (enforced):** bucket dummies **not** present in $x^{(\mu)}$; $\ln g_c$ present **only** in $x^{(\phi)}$.

---

## Safe logistic evaluation (notation consistent with §S0.3: ln = natural log) (overflow-stable, no clamp in compute path)

Use the branch-stable form:

$$
\sigma(\eta)=
\begin{cases}
\frac{1}{1+e^{-\eta}},& \eta\ge0,\\[4pt]
\frac{e^{\eta}}{1+e^{\eta}},& \eta<0.
\end{cases}
$$

* **Computation:** **no clamping**; this preserves the possibility that extreme $\eta$ underflow/overflow yields $\pi\in\{0,1\}$, which S1 will treat as a **zero-draw** Bernoulli case per S0.3.
* **Display/logging:** it is allowed to **format** $\pi$ as 0 or 1 when $|\eta|>40$, but this **must not** affect computation.

---

## Determinism & numeric policy

* **No randomness**; outputs depend only on frozen dictionaries and S0.4 features.
* IEEE-754 **binary64**; on ordering-critical paths (any later reductions/normalisations that involve these vectors), **no FMA** and **serial reductions** per S0.8. Changing these toggles changes the numeric-policy artefact and thus the fingerprint.

---

## Persistence (optional) & partitions

By default, $x_m, x^{(\mu)}_m, x^{(\phi)}_m$ are **in-memory**. If materialised:

* `hurdle_design_matrix` under `…/parameter_hash={parameter_hash}/…` with schema `schemas.1A.yaml#/model/hurdle_design_matrix`.
* Optional diagnostics: `hurdle_pi_probs` under `…/parameter_hash={parameter_hash}/…` with schema `#/model/hurdle_pi_probs` (**never** used by samplers).

**Partitioning (normative):** these caches are **parameter-scoped**.

* **Rows must embed** the same `parameter_hash` as the directory key.
* **Do not embed** `manifest_fingerprint` as a required column in parameter-scoped outputs.

---

## Validation hooks (must pass)

1. **Column alignment / shapes**

   * `len(beta_hurdle) == 1 + C_mcc + 2 + 5`.
   * The NB dispersion coefficient vector matches `1 + C_mcc + 2 + 1`.
   * The **dictionary order** used to build vectors matches the order implied by the coefficient vectors. Any drift is a hard error.
2. **One-hot correctness** — each encoder emits exactly one “1”.
3. **Feature domains** — `g_c > 0`; `b_m ∈ {1..5}` (from S0.4).
4. **Leakage guard (machine-checked)** — bucket dummies appear in `x_m` only; `ln(g_c)` appears in `x^{(φ)}_m` only.
5. **Partition lint (if persisted)** — embedded `parameter_hash` equals the path key exactly; otherwise `E_PARTITION_MISMATCH`.

---

## Failure semantics (precise aborts)

* `E_DSGN_UNKNOWN_MCC(mcc)` — MCC absent from the fitting dictionary.
* `E_DSGN_UNKNOWN_CHANNEL(ch)` — channel symbol not in `{CP,CNP}`.
* `E_DSGN_SHAPE_MISMATCH(exp_dim, got_dim)` — coefficient/design dimension mismatch.
* `E_DSGN_DOMAIN_GDP(g)` — `g_c ≤ 0`.
* `E_DSGN_DOMAIN_BUCKET(b)` — `b ∉ {1..5}`.
* `E_PARTITION_MISMATCH(id, path_key, embedded_key)` — parameter-scoped persistence key mismatch.

---

## Reference algorithm (language-agnostic)

```text
function S0_5_build_designs(M, dict_mcc, dict_ch, dict_dev5,
                            beta_hurdle, nb_dispersion_coef, G, B):
  # dict_ch must equal ["CP","CNP"]; dict_dev5 must equal [1,2,3,4,5]
  assert dict_ch == ["CP","CNP"], E_DSGN_UNKNOWN_CHANNEL
  assert dict_dev5 == [1,2,3,4,5], E_DSGN_SHAPE_MISMATCH

  # Expected shapes (frozen by bundle)
  assert len(beta_hurdle) == 1 + len(dict_mcc) + 2 + 5, E_DSGN_SHAPE_MISMATCH
  assert len(nb_dispersion_coef) == 1 + len(dict_mcc) + 2 + 1, E_DSGN_SHAPE_MISMATCH

  for r in M:
      m  = r.merchant_id
      c  = r.home_country_iso
      ch = r.channel_sym          # already CP/CNP from S0.1 mapping
      g  = G[c];  if not (g > 0):       raise E_DSGN_DOMAIN_GDP(g)
      b  = B[c];  if b not in {1,2,3,4,5}: raise E_DSGN_DOMAIN_BUCKET(b)

      # one-hot positions are obtained from frozen dictionaries
      i_mcc = dict_mcc.index_of(r.mcc)         # throws -> E_DSGN_UNKNOWN_MCC
      i_ch  = dict_ch.index_of(ch)
      i_dev = dict_dev5.index_of(b)

      h_mcc = one_hot(i_mcc, len(dict_mcc))
      h_ch  = one_hot(i_ch, 2)
      h_dev = one_hot(i_dev, 5)

      x_hurdle = [1] + h_mcc + h_ch + h_dev
      x_nb_mu  = [1] + h_mcc + h_ch
      x_nb_phi = [1] + h_mcc + h_ch + [ln(g)]

      # Enforce leakage rule structurally (redundant but explicit)
      assert len(x_nb_mu)  == 1 + len(dict_mcc) + 2
      assert len(x_nb_phi) == 1 + len(dict_mcc) + 2 + 1

      yield (m, x_hurdle, x_nb_mu, x_nb_phi)
```

---

## Complexity & concurrency

* **Time:** $O(|\mathcal M|)$ with constant work per row.
* **Space:** streaming; one merchant at a time.
* **Parallelism:** embarrassingly parallel; determinism holds (frozen dictionaries + S0.4 lookups).

---

## Downstream connections

* **S1** consumes $(x_m,\beta)$ to compute $\eta_m$ and then the Bernoulli hurdle; S1 **aborts** on any design/coeff mismatch.
* **S2** consumes $(x^{(\mu)}_m,x^{(\phi)}_m)$ for NB mean/dispersion; all RNG usage there follows S0.3’s envelope/budget rules.

---

**Summary:** S0.5 now gives an implementer the exact, frozen layout for hurdle and NB designs, enforces the CP/CNP vocabulary and the “bucket-in-hurdle / log-GDP-in-dispersion” rule, and cleanly separates parameter-scoped persistence from egress lineage. It’s deterministic, leakage-proof, and ready to wire into S1/S2.

---

# S0.6 — Cross-border Eligibility (deterministic gate, normative, fixed)

## Purpose

Decide, **without randomness**, whether each merchant $m$ is permitted to attempt cross-border expansion later (i.e., enter S4–S6). 
Persist **exactly one row per merchant** to the parameter-scoped dataset **`crossborder_eligibility_flags`** with fields `(parameter_hash, merchant_id, is_eligible, reason, rule_set)` (optionally `produced_by_fingerprint` for provenance).

* **Parameter-scoped** ⇒ partition by `parameter_hash`; **rows embed `parameter_hash`** (required by schema). `produced_by_fingerprint` (hex64) is optional and informational.

No RNG is consumed in S0.6.

---

## Inputs (read-only; pinned earlier)

* **Merchant tuple** $t(m)=(\texttt{mcc}_m,\texttt{channel_sym}_m,\texttt{home_country_iso}_m)$ from `merchant_ids` (S0.1), where `channel_sym ∈ {CP,CNP}` (S0.1 mapping is authoritative).
* **Parameter bundle:** `crossborder_hyperparams.yaml` (governed by `parameter_hash`; contains the eligibility rule set).
* **Lineage keys:** `parameter_hash` (partition path and embedded column).
* **Schema & dictionary:** dataset `crossborder_eligibility_flags` → partitioned by `{parameter_hash}`, schema `schemas.1A.yaml#/prep/crossborder_eligibility_flags`.

---

## Output (authoritative)

Write one row per merchant $m$ to:

```
.../crossborder_eligibility_flags/parameter_hash={parameter_hash}/part-*.parquet
```

**Columns (normative; per schema):**

* `parameter_hash` (hex64; **must equal** the path key),
* `produced_by_fingerprint` (hex64; optional, **informational only** — it is **never** part of partition keys or equality checks),
* `merchant_id` (PK; one and only one row per merchant),
* `is_eligible` (boolean),
* `reason` (nullable string: winning rule `id`, or `"default_allow"` / `"default_deny"`),
* `rule_set` (non-empty string copied from `eligibility.rule_set_id`).

---

## Domains & symbols

* Channels $\mathcal C=\{\text{CP},\text{CNP}\}$ (internal symbols only; ingress strings are mapped in S0.1).
* Countries $\mathcal I$: ISO-3166 alpha-2 set (uppercase ASCII; pinned in S0.1).
* MCC set $\mathcal K$: 4-digit codes (domain pinned in S0.1).

---

## Rule family (configuration semantics)

All eligibility rules live in **`crossborder_hyperparams.yaml`** under:

```yaml
eligibility:
  rule_set_id: "eligibility.v1.2025-04-15"
  default_decision: "deny"   # "allow" | "deny"
  rules:
    - id: "sanctions_deny"
      priority: 10           # integer [0, 2^31-1]
      decision: "deny"       # "allow" | "deny"
      mcc:     ["*"]         # "*" or list of 4-digit codes or ranges "5000-5999"
      channel: ["CP","CNP"]  # subset of {"CP","CNP"} or "*"
      iso:     ["RU","IR","KP"]  # subset of ISO-2 or "*"
      reason:  "sanctions"
    # ...
```

**Bundle validation (at load):**

* `rule_set_id`: non-empty ASCII; becomes the `rule_set` column value.
* `default_decision ∈ {"allow","deny"}`.
* For each rule:

  * `id`: ASCII, **unique** within the bundle.
  * `priority`: integer in $[0,2^{31}{-}1]$.
  * `decision ∈ {"allow","deny"}`.
  * `channel`: `"*"` or subset of **exactly** `{"CP","CNP"}`.
  * `iso`: `"*"` or subset of $\mathcal I$ (uppercase ASCII).
  * `mcc`: `"*"` or list of **4-digit strings** and/or **inclusive ranges** `"NNNN-MMMM"` with `NNNN, MMMM ∈ 0000..9999` and `NNNN ≤ MMMM`.
* Reject any MCC not in $\mathcal K$ after range expansion; reject any ISO not in $\mathcal I$.

---

## Set interpretation & matching (normative)

After expanding `"*"` and MCC ranges:

* Each rule $r$ defines sets $S_{\rm mcc}\subseteq\mathcal K$, $S_{\rm ch}\subseteq\mathcal C$, $S_{\rm iso}\subseteq\mathcal I$ and a decision $d\in\{\textsf{allow},\textsf{deny}\}$.
* **Match:** $r$ matches $m$ iff $ \texttt{mcc}_m\in S_{\rm mcc} \land \texttt{channel_sym}_m\in S_{\rm ch} \land \texttt{home_country_iso}_m\in S_{\rm iso}$.

**Range semantics (MCC):** `"5000-5999"` means all integer codes $5000 \le \text{MCC} \le 5999$; codes are compared numerically after parsing 4-digit strings.

---

## Conflict resolution & determinism (total order)

When multiple rules match a merchant, choose using this **total order**:

1. **Decision tier:** `deny` outranks `allow`.
2. **Priority:** lower `priority` outranks higher (e.g., `10` beats `50`).
3. **Tie-break:** ASCII lexical order on `id`.

Let $\mathrm{best}_{\textsf{deny}}(m)$ and $\mathrm{best}_{\textsf{allow}}(m)$ be the top-ranked matching rules in their tiers (or `None`).

Decision:

* If $\mathrm{best}_{\textsf{deny}}(m)$ exists → `is_eligible = false`, `reason = that.id`.
* Else if $\mathrm{best}_{\textsf{allow}}(m)$ exists → `is_eligible = true`, `reason = that.id`.
* Else → `is_eligible = (default_decision == "allow")`, `reason = "default_allow"` or `"default_deny"`.

This is **order-invariant** and parallel-safe.

---

## Algorithm (exact; streaming-safe)

For each merchant $m$:

1. Fetch $t(m) = (\texttt{mcc}, \texttt{channel_sym}, \texttt{home_iso})$.
2. Build candidate sets $D$ (deny) and $A$ (allow) by matching rules.
3. Choose per **Conflict resolution**; produce `reason`.
4. Write row (partition by `parameter_hash`):

```json
{
  "parameter_hash":           "<hex64>",
  "produced_by_fingerprint":  "<hex64>",  // optional
  "merchant_id":              "<id>",
  "is_eligible":              true|false,
  "reason":                   "<winning rule id | default_allow | default_deny>",
  "rule_set":                 "<eligibility.rule_set_id>"
}
```

**Performance notes:** Index rules by `(channel_sym, home_iso)` and keep MCC ranges in an interval set for $O(\log R)$ matching; naive $O(R)$ is acceptable at current scale.

---

## Formal spec (decision function)

With $\prec$ defined by `(decision, priority, id)` where `deny < allow`, numeric `priority` ascending, ASCII `id`:

$$
\mathrm{best}_{\textsf{deny}}(m)=\min\nolimits_\prec\{r\in\mathcal{R}_{\textsf{deny}}: r\text{ matches }m\},
$$

$$
\mathrm{best}_{\textsf{allow}}(m)=\min\nolimits_\prec\{r\in\mathcal{R}_{\textsf{allow}}: r\text{ matches }m\}.
$$

$$
e_m =
\begin{cases}
0,& \mathrm{best}_{\textsf{deny}}(m)\text{ exists},\\
1,& \mathrm{best}_{\textsf{deny}}(m)=\varnothing \land \mathrm{best}_{\textsf{allow}}(m)\text{ exists},\\
\mathbf 1\{\texttt{default_decision}=\text{"allow"}\},& \text{otherwise.}
\end{cases}
$$

`reason` = winning rule `id`, else `"default_allow"`/`"default_deny"`.

---

## Determinism & contracts

* **No RNG.** Output depends only on $t(m)$ and the parameter bundle.
* **Schema & partitioning (normative):** rows conform to `#/prep/crossborder_eligibility_flags`; dataset is partitioned by `{parameter_hash}`; each row **embeds the same `parameter_hash`**.
  `produced_by_fingerprint` (if present) is **informational only** and **never** compared to any path key or used in partition/equality semantics.
---

## Failure semantics (precise aborts)

**At parameter load:**

* `E_ELIG_RULESET_ID_EMPTY` — missing/empty `rule_set_id`.
* `E_ELIG_DEFAULT_INVALID` — `default_decision` not in `{"allow","deny"}`.
* `E_ELIG_RULE_DUP_ID(id)` — duplicate rule `id`.
* `E_ELIG_RULE_BAD_CHANNEL(id,ch)` — channel not in `{"CP","CNP"}` or `"*"`.
* `E_ELIG_RULE_BAD_ISO(id,iso)` — ISO not in $\mathcal I$ or not uppercase ASCII.
* `E_ELIG_RULE_BAD_MCC(id,mcc)` — MCC not in $\mathcal K$ or range malformed (`"NNNN-MMMM"` with `NNNN ≤ MMMM` required).

**At evaluation/persist:**

* `E_ELIG_MISSING_MERCHANT(m)` — missing required fields in `merchant_ids`.
* `E_ELIG_WRITE_FAIL(path, errno)` — failed to persist a row.
* `E_PARTITION_MISMATCH(path_key, embedded_key)` — embedded `parameter_hash` mismatches directory key.

On any error, **abort S0**; no partial output is acceptable.

---

## Validation & CI hooks

1. **Schema conformance:** every row matches `#/prep/crossborder_eligibility_flags`.
2. **Coverage/uniqueness:** exactly one row per `merchant_id` (PK).
3. **Determinism:** rerunning S0.6 with the same inputs yields **byte-identical** rows (ignoring file order).
4. **Policy lint:** report counts by decision source (`deny`, `allow`, `default_*`) to monitor rule-set shifts when parameters change.
5. **Partition lint:** dataset path and embedded `parameter_hash` match; `produced_by_fingerprint` (if present) is ignored by validators.

---

## Reference pseudocode (language-agnostic)

```text
function S0_6_apply_eligibility_rules(merchants, params, parameter_hash, produced_by_fp=None):
  cfg   = params["eligibility"]
  rsid  = cfg["rule_set_id"]; assert rsid, E_ELIG_RULESET_ID_EMPTY
  def_allow = (cfg["default_decision"] == "allow")
  rules = parse_validate_expand(cfg["rules"])  # validates domains, ranges, duplicates, vocab

  deny_idx  = index_rules(rules, decision="deny")   # indexed by (channel_sym, home_iso), MCC intervals
  allow_idx = index_rules(rules, decision="allow")

  writer = open_partitioned_writer("crossborder_eligibility_flags",
            partition={"parameter_hash": parameter_hash})

  for m in merchants:
      key = (m.mcc, m.channel_sym, m.home_country_iso)  # channel_sym is CP/CNP from S0.1

      D = match(deny_idx,  key)   # returns list of (priority, id)
      A = match(allow_idx, key)

      if not empty(D):
          best = min_by(D, (priority, id))  # numeric asc, ASCII asc
          is_eligible = false
          reason      = best.id
      elif not empty(A):
          best = min_by(A, (priority, id))
          is_eligible = true
          reason      = best.id
      else:
          is_eligible = def_allow
          reason      = "default_allow" if def_allow else "default_deny"

      row = {
        "parameter_hash": parameter_hash,
        "merchant_id": m.merchant_id,
        "is_eligible": is_eligible,
        "reason": reason,
        "rule_set": rsid
      }
      if produced_by_fp is not None:
          row["produced_by_fingerprint"] = produced_by_fp

      writer.write(row)

  writer.close()
```

---

## Complexity, concurrency, and I/O

* **Time:** $O(|\mathcal M|\log |\mathcal R|)$ with simple indices; $O(|\mathcal M||\mathcal R|)$ naive.
* **Space:** streaming; constant memory aside from rule indices.
* **Parallelism:** embarrassingly parallel; determinism holds (pure function of $t(m)$ and versioned rule set).

---

**Bottom line:** S0.6 now writes a **parameter-scoped** authoritative gate with a stable conflict-resolution order, explicit `reason`, versioned `rule_set`, and **no fingerprint coupling**. S3 consumes it verbatim to control the cross-border branch—no RNG, no ambiguity.

---

# S0.7 — Hurdle π Diagnostic Cache (deterministic, optional, normative, fixed)

## Purpose

Materialise a **read-only diagnostics table** with per-merchant logistic-hurdle outputs

$$
(\texttt{merchant_id},\ \eta_m,\ \pi_m),\quad \eta_m=\beta^\top x_m,\ \pi_m=\sigma(\eta_m)\in[0,1],
$$

so monitoring/validation can inspect the hurdle surface **without** recomputing on the hot path. This artefact is **never consulted by samplers**; it is **optional** and lives under the **parameter-scoped** partition.

* **Dataset id / path / schema:** `hurdle_pi_probs` →
  `.../layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/`
  schema `schemas.1A.yaml#/model/hurdle_pi_probs`.
* **Registry role:** “Logistic-hurdle π (single vs multi) per merchant”. Depends on `hurdle_design_matrix` and `hurdle_coefficients`.

> S0.10 lists this as **optional** output of S0 (parameter-scoped). Presence/absence does not affect any downstream state.

---

## Inputs (frozen by S0.1–S0.5)

* **Design vector** $x_m=[1,\ \phi_{\text{mcc}},\ \phi_{\text{ch}},\ \phi_{\text{dev}}]$ from **S0.5** (column order frozen by the fitting bundle).
* **Hurdle coefficients** $\beta$ (single YAML vector matching $x_m$’s layout).
* **Lineage keys:** `parameter_hash`  (partition path and embedded column). `produced_by_fingerprint` (hex64) optional/informational.

**No RNG** is consumed.

---

## Output (schema, typing, keys)

A Parquet table with **one row per merchant**:

* **Primary key:** `merchant_id`.
* **Partition key:** `parameter_hash` (directory level).

**Columns (normative; per schema):**

* `parameter_hash` (hex64; **must equal** path key),
* `produced_by_fingerprint` (hex64; optional, **informational only** — it is **never** part of partition keys or equality checks),
* `merchant_id` (id64 per ingress schema),
* `logit` (float32) — narrowed $\eta_m$,
* `pi` (float32) — narrowed $\pi_m\in[0,1]$.
---

## Canonical definitions & numerical policy

### Linear predictor and logistic

Let $\eta_m = \beta^\top x_m$ with the **exact** column order frozen by the fitting bundle (validated in S0.5).

Evaluate the logistic with the **overflow-stable** branch form:

$$
\sigma(\eta)=
\begin{cases}
\dfrac{1}{1+e^{-\eta}}, & \eta\ge 0,\\[6pt]
\dfrac{e^{\eta}}{1+e^{\eta}}, & \eta<0.
\end{cases}
$$

* **Computation:** IEEE-754 **binary64**; no FMA; fixed evaluation order (S0.8).
* **Extremes:** $\pi_m$ may equal **exactly** 0 or 1 for large $|\eta_m|$; this is **allowed** and must be persisted faithfully.

### Storage narrowing (deterministic)

Persist `logit` and `pi` as **float32** using **round-to-nearest, ties-to-even** after computing both in binary64. Narrowing is part of the contract and is **for storage only**.

---

## Determinism & scope rules

* **No randomness.** Results depend only on $x_m$ and $\beta$.
* **Diagnostics-only.** No production sampler/allocation routine may read this table.
* **Parameter-scoped.** Changing any governed parameter byte changes `parameter_hash` and thus the partition; no implicit overwrite across partitions.
* `produced_by_fingerprint` (if present) is **informational only** and **does not** participate in partition keys or row equality.

---

## Failure semantics (abort S0; precise codes)

* `E_PI_SHAPE_MISMATCH(exp_dim, got_dim)` — $|\beta|\neq \dim(x_m)$ (double-guard beyond S0.5).
* `E_PI_NAN_OR_INF(m)` — $\eta_m$ or $\pi_m$ non-finite.
* `E_PI_PARTITION(path_key, embedded_key)` — embedded `parameter_hash` mismatches directory key.
* `E_PI_WRITE(path, errno)` — write failure.

> On any failure, **abort S0**; the cache is either wholly correct or absent.

---

## Validation & CI hooks

1. **Schema conformance** — matches `#/model/hurdle_pi_probs`.
2. **Coverage** — exactly $|\mathcal M|$ rows (1 per `merchant_id`).
3. **Recompute check** — rebuild $x_m$ (S0.5) and recompute $\eta_m,\pi_m$ from $\beta$; assert equality to stored **float32** values (bit-for-bit).
4. **Partition lint** — path includes `parameter_hash={parameter_hash}`; row `parameter_hash` equals the path key; no other required lineage fields.
5. **Downstream isolation** — static analysis / policy test: states S1–S9 must not read `hurdle_pi_probs`.

---

## Algorithm (exact; streaming-safe)

For each merchant $m\in\mathcal M$:

1. Load or deterministically construct $x_m$ (S0.5). Assert dictionary/shape alignment.
2. Compute $\eta_m=\beta^\top x_m$ in **binary64**; compute $\pi_m=\sigma(\eta_m)$ via the branch-stable definition.
3. Assert finiteness; else `E_PI_NAN_OR_INF(m)`.
4. Narrow deterministically to float32 (round-to-nearest-even):

   * `logit := f32(η_m)`, `pi := f32(π_m)`.
5. Emit:

   ```json
   {
     "parameter_hash": "<hex64>",
     "produced_by_fingerprint":  "<hex64>",  // optional
     "merchant_id":          "<id64>",
     "logit":                "<float32>",
     "pi":                   "<float32>[0,1]"
   }
   ```
6. Persist under `.../hurdle_pi_probs/parameter_hash={parameter_hash}/…` (Parquet). File ordering is unspecified.

**Complexity.** $O(|\mathcal M|)$ dot-products; $O(1)$ space; trivially parallel.

---

## Reference pseudocode (language-agnostic)

```text
function S0_7_build_hurdle_pi_cache(merchants, beta, dicts, parameter_hash, produced_by_fp=None):
  writer = open_partitioned_writer("hurdle_pi_probs",
             partition={"parameter_hash": parameter_hash})

  for m in merchants:
      x = build_x_hurdle(m, dicts)                 # deterministic, validated in S0.5
      eta64 = dot_f64(beta, x)                      # binary64 accumulation, fixed order
      pi64  = logistic_branch_stable(eta64)         # ∈ [0,1]; extremes allowed

      if not (is_finite(eta64) and is_finite(pi64)):
          raise E_PI_NAN_OR_INF(m.merchant_id)

      row = {
        "parameter_hash": parameter_hash,
        "merchant_id":    m.merchant_id,
        "logit":          f32(eta64),               # IEEE RN–even
        "pi":             f32(pi64)
      }
      if produced_by_fp is not None:
          row["produced_by_fingerprint"] = produced_by_fp

      writer.write(row)

  writer.close()
```

---

## Downstream connections

* **S1** recomputes $\eta_m,\pi_m$ to draw the Bernoulli hurdle; it **does not** read this cache.
* **S0.10** treats this artefact as optional; presence does not affect `manifest_fingerprint` beyond the bytes of the governing parameters that already define `parameter_hash`.

---

**Summary:** S0.7 is now a **parameter-scoped**, deterministic diagnostics cache with **no** coupling to the run fingerprint, consistent logistic semantics ($\pi\in[0,1]$), explicit float32-for-storage narrowing, and strict validation. It’s safe to generate or skip, and it can never influence stochastic behaviour downstream.

---

# S0.8 — Numeric Policy & Determinism Controls (normative, fixed)

**Cross-reference (normative):** All samplers and transforms in §S0.3 use IEEE-754 **binary64**, round-to-nearest-ties-even, **FMA off**, **no FTZ/DAZ**, and the pinned deterministic libm profile (`numeric_policy.json`, `math_profile_manifest.json`). Any computation that affects a branch/order (acceptance tests, sort keys, integerisation) must execute in a **serial, fixed-order** kernel. Self-tests and attest are in §S0.8 and are part of the validation bundle.

## Purpose

Guarantee that numerically sensitive computations in 1A are **bit-stable** across machines, compilers, and parallelism. S0.8 defines:

* the **floating-point environment** (format, rounding, subnormals),
* a **deterministic math profile** for `exp/log/sin/cos/atan2/pow/...`,
* **compiler/runtime flags** forbidding contraction/fast-math,
* **reduction/sorting** rules (fixed order, exact tie-breaks),
* **tolerances** for validation (internal vs. external),
* runtime **self-tests** that abort the run if violated.

No RNG is consumed here.

> **Artefactisation (normative):** Two files are required and **included in the S0.2 manifest enumeration**. Changing either flips `manifest_fingerprint`.
>
> 1. `numeric_policy.json` — declares environment/flags and kernel policies.
> 2. `math_profile_manifest.json` — pins the vendored libm/profile (name, version, digest set).

---

## S0.8.1 Floating-point environment (must hold)

* **Format:** IEEE-754 **binary64** for **all** computations that can affect decisions/order. Diagnostics may downcast only when a state explicitly allows it (e.g., S0.7).
* **Rounding mode:** **Round-to-nearest, ties-to-even (RNE)**; set and verify at startup.
* **FMA (fused multiply-add):** **Disabled** on any ordering-critical path (anything that feeds decisions, rankings, acceptance tests, or integerisation). Permitted **only** in non-critical code paths that never influence a branch/order.
* **Subnormals:** **Honour** subnormals; FTZ/DAZ **off**.
* **Exceptions:** mask signals; **any** NaN/Inf in model computations is a **hard error** (S0.8.8).
* **Endianness:** little-endian; where relevant (hashing/PRNG), byte order is pinned per state.
* **Constants (normative):** All decision-critical constants (e.g., `TAU`) **MUST** be encoded as **binary64 hex literals**; recomputation from other constants (e.g., `2*pi`) is **forbidden** to avoid drift across platforms/compilers.

**`numeric_policy.json` (normative minimum):**

```json
{
  "binary_format": "ieee754-binary64",
  "rounding_mode": "rne",
  "fma_allowed": false,
  "flush_to_zero": false,
  "denormals_are_zero": false,
  "sum_policy": "serial_neumaier",
  "parallel_decision_kernels": "disallowed",
  "version": "1.0"
}
```

---

## S0.8.2 Deterministic libm profile (math functions)

**Scope:** `exp`, `log`, `log1p`, `expm1`, `sqrt`, `sin`, `cos`, `atan2`, `pow`, `tanh`, `erf` (if used), `lgamma`.

**Normative requirements**

* Selected implementations are **bit-identical** across platforms.
* `sqrt` is correctly rounded (IEEE).
* All others above are **deterministic to the last bit** under the selected profile.

**Operationalisation**

* Ship a vendored, deterministic math layer behind a sealed API (e.g., `mlr_math::exp`), or pin an exact libm build with a content digest set.
* **Disallow** toolchains from substituting system libm for these calls in decision-critical code.
* Record a **`math_profile_id`** and fold `math_profile_manifest.json` into the S0.2 artefact set.

**`math_profile_manifest.json` (example):**

```json
{
  "math_profile_id": "mlr-math-1.2.0",
  "vendor": "acme-deterministic-libm",
  "build": "glibc-2.38-toolchain-2025-04-10",
  "functions": ["exp","log","log1p","expm1","sqrt","sin","cos","atan2","pow","tanh","lgamma"],
  "artifacts": [
    {"name":"libmlr_math.so","sha256":"<64-hex>"},
    {"name":"headers.tgz","sha256":"<64-hex>"}
  ]
}
```

---

## S0.8.3 Reductions, accumulations & linear algebra

* **Sums/dots:** Use **serial, fixed-order** accumulation with **Neumaier** compensation for any total/dot feeding a decision or ordering. Never parallel-reduce such values.
* **Products/ratios:** Multiply in binary64 unless a state mandates log-sum; check denominators against zero with strict guards where required.
* **BLAS/LAPACK:** **Do not** call external BLAS/LAPACK on decision-critical paths. If ever required, pin a deterministic backend and include it in `math_profile_id`.

**Reference kernels (normative):** see §S0.8.10.

---

## S0.8.4 Compiler / interpreter flags (build contract)

**C/C++ (examples):**

* `-fno-fast-math -fno-unsafe-math-optimizations`
* `-ffp-contract=off` (no FMA contraction)
* `-fexcess-precision=standard -frounding-math`
* `-fno-associative-math -fno-reciprocal-math -fno-finite-math-only`
* (Legacy/x87 only) `-ffloat-store` if needed to avoid excess precision.

**LLVM/Clang IR:**
Disable `fast-math` flags; use constrained FP intrinsics with RNE and masked exceptions.

**Python/NumPy/JVM, etc.:**

* Avoid `np.sum` for decision-critical reductions; call our scalar kernels.
* Pin `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
* Disable auto-vectorisation where it can change summation order.

**GPU:** Do **not** offload decision-critical kernels unless a deterministic math profile is pinned with fused ops disabled.

> All effective flags + environment variables must be serialised into `numeric_policy_attest.json` (see §S0.8.9) and the attest file’s digest is included in the manifest enumeration.

---

## S0.8.5 Sorting, comparisons & total order for floats

* **Total order:** For sorting/keys, use IEEE-754 **`totalOrder`** semantics; **NaNs are forbidden** (encountering a NaN is a hard error). `-0.0 < +0.0`.
* **Tie-breakers:** If float keys compare equal, break ties **lexicographically** by a deterministic secondary key (e.g., `ISO` then `merchant_id`).
* **Equality:** Use exact equality only where guaranteed (counters, integers).
* **Nearly-equal:** Prefer **ULP-based** checks (`ulpDiff ≤ 1`) when used in self-tests; do **not** “epsilon-fudge” model decisions.

**Portable key mapping (non-NaN domain):**

```text
# bits = uint64 bit pattern of the float (IEEE-754)
# Ties then break by deterministic secondary key: ISO (ASCII) then merchant_id.
# Map to an integer key that is monotone w.r.t. totalOrder for non-NaNs:
key = (bits & 0x8000000000000000) ? (~bits) : (bits | 0x8000000000000000)
# This guarantees -0.0 sorts before +0.0 and preserves numeric order elsewhere.
```

---

## S0.8.6 Tolerances & quantisation

* **Internal (self-tests):**

  * Sums/dots: `ulpDiff ≤ 1`.
  * Transcendentals: **bit-exact** under the pinned profile.
* **External (reporting/comparing persisted float32):**
  `max(abs_diff, rel_diff) ≤ 1e-6` when comparing **float32** diagnostics to recomputed float64 values **downcast to float32**.
* **Quantisation:** Where a state requires downcasting (e.g., S0.7), use IEEE **round-to-nearest-even**. No other quantisation is allowed unless a state explicitly says so.

---

## S0.8.7 Determinism under concurrency

* **Order-invariance by construction:** RNG streams are keyed (S0.3).
* **Numeric kernels:** Any computation that feeds a sort/branch must run in a **single-threaded** scalar loop with fixed iteration order and Neumaier compensation.
* **Map-style parallelism:** Allowed when results are per-row and never aggregated into decision/order without the serial kernel.
* **I/O:** File emission order is unspecified; equality is defined by row sets. Partitions are unambiguous due to hashes/fingerprints.

---

## S0.8.8 Failure semantics (abort codes)

* `E_NUM_FMA_ON` — FMA contraction detected on a guarded kernel.
* `E_NUM_FTZ_ON` — FTZ/DAZ detected.
* `E_NUM_RNDMODE` — non-RNE rounding mode.
* `E_NUM_LIBM_PROFILE` — math profile mismatch or non-deterministic libm detected.
* `E_NUM_NAN_OR_INF(ctx)` — NaN/Inf produced in a model computation.
* `E_NUM_PAR_REDUCE` — decision-critical reduction executed in parallel or with a non-pinned topology.
* `E_NUM_TOTORDER_NAN` — NaN encountered in a total-order sort key.
* `E_NUM_ULP_MISMATCH(func)` — recomputation differs beyond ULP budget.
* `E_NUM_PROFILE_ARTIFACT_MISSING(name)` — required numeric artefact (policy/profile/attest) missing.

On any of the above, **abort the run**.

---

## S0.8.9 Self-tests (must run before S1)

Run after S0.2 (hashing) and before any RNG draw:

1. **Rounding & FTZ**

* Assert RNE.
* Create a subnormal (e.g., `2^-1075`) and multiply by 1; assert not flushed to 0.

2. **FMA detection**

* Evaluate a triple `(a,b,c)` with known fused vs non-fused outcomes; assert the **non-fused** result (contraction disabled).

3. **libm profile**

* Evaluate a fixed regression suite for `exp/log/sin/cos/atan2/pow/...` and compare against vendored expected **bit patterns**. Fail on any mismatch.

4. **Neumaier audited sum**

* Sum an adversarial sequence (e.g., `[1, 1e-16] × N` then `[-1] × N`) and assert `(sum, compensation)` matches expected values.

5. **TotalOrder sanity**

* Sort a crafted float array including `-0.0`, `+0.0`, extremes; verify ordering and tie-breakers.

**Attestation (normative output):** Write `numeric_policy_attest.json` with:

```json
{
  "numeric_policy_version": "1.0",
  "math_profile_id": "mlr-math-1.2.0",
  "platform": {"os":"linux","libc":"glibc-2.38","compiler":"clang-18.0"},
  "flags": {"ffast-math": false, "fp_contract":"off", "rounding":"rne", "ftz": false, "daz": false},
  "self_tests": {"rounding": "pass", "ftz": "pass", "fma": "pass", "libm": "pass", "neumaier": "pass", "total_order": "pass"},
  "digests": [
    {"name": "numeric_policy.json", "sha256": "<64-hex>"},
    {"name": "math_profile_manifest.json", "sha256": "<64-hex>"}
  ]
}
```

Include this file’s digest in the manifest enumeration (S0.2).

---

## S0.8.10 Reference kernels (pseudocode)

**Neumaier compensated sum (fixed order)**

```text
def sum_neumaier(xs: iterable<float64>) -> float64:
    s = 0.0; c = 0.0
    for x in xs:                 # fixed iteration order
        y = x - c
        t = s + y
        c = (t - s) - y
        s = t
    return s
```

**Dot product with Neumaier**

```text
def dot_neumaier(a: float64[], b: float64[]) -> float64:
    assert len(a) == len(b)
    s = 0.0; c = 0.0
    for i in 0..len(a)-1:
        y = a[i]*b[i] - c
        t = s + y
        c = (t - s) - y
        s = t
    return s
```

**Total-order key for non-NaN floats**

```text
def total_order_key(x: float64, secondary) -> tuple:
    assert not isNaN(x)           # NaN forbidden
    bits = u64_from_f64(x)
    key  = (~bits) if (bits & 0x8000000000000000) else (bits | 0x8000000000000000)
    return (key, secondary)       # (-0.0) sorts before (+0.0); ties broken by 'secondary'
```

---

## S0.8.11 Validation & CI hooks

* **Bitwise CI:** run self-tests on ≥2 platforms (e.g., glibc vs. musl) → identical results.
* **Rebuild sensitivity:** any change that alters decision-critical outputs must also change `numeric_policy.json` or `math_profile_manifest.json`, thus flipping the fingerprint.
* **Partition lint:** ensure `numeric_policy_attest.json` is present in the validation bundle and its digest is in the manifest enumeration.

---

## S0.8.12 Interaction with other states

* **S0.3 (RNG):** Box–Muller, gamma acceptance tests, PTRS, and Gumbel keys use the pinned math profile and branch-stable formulas.
* **S0.5–S2 (design & GLM):** Dots/logistics use Neumaier + overflow-stable logistic; results are bit-stable.
* **S6 (ranking):** All sorts over float keys use the **total order** + deterministic tie-breakers.

---

**Bottom line:** S0.8 is now a **first-class, fingerprinted numeric contract**: binary64 + RNE, **no FMA**, **no FTZ/DAZ**, deterministic libm, fixed-order Neumaier reductions, total-order sorting, and mandatory self-tests. With `numeric_policy.json`, `math_profile_manifest.json`, and `numeric_policy_attest.json` wired into lineage, downstream states can rely on bit-stable arithmetic everywhere.

---

# S0.9 — Failure Modes & Abort Semantics (normative, fixed)

## Purpose

Define a **single, deterministic** failure contract for 1A so that any violation of schema, lineage, numeric policy, RNG envelope, or partitioning halts the run the **same way every time**, with an actionable forensic payload.

**Scope.** S0.9 governs **all of 1A** (S0–S7). Failures detected anywhere are classified by **S0.9 failure classes (F1–F10)** and surfaced through a **uniform failure record**.

---

## 0) Definitions & severity

* **Run-abort (hard):** Stop the **entire** 1A run immediately; no further states execute.
* **Merchant-abort (soft):** Allowed **only** where a state explicitly specifies it (e.g., S4 corridor policy). Soft aborts are logged to a **merchant-abort log** (see §2.4) and **never** used to bypass S0.9 run-abort conditions.

---

## 1) Failure catalog (F1–F10)

### F1 — Ingress schema violation (`merchant_ids`)

**Predicate:** fails `schemas.ingress.layer1.yaml#/merchant_ids` (types, required fields, PK, ISO). **Run-abort.**
**`failure_code` examples:** `ingress_schema_violation`, `ingress_pk_duplicate`, `ingress_iso_bad`.

---

### F2 — Parameter / fingerprint formation failure (S0.2)

Covers `parameter_hash` & `manifest_fingerprint`. **Run-abort.**

* **F2a Parameters:** missing/duplicate/unreadable governed file; hash race.
  `failure_code`: `param_file_missing|duplicate|unreadable|changed_during_hash`.
* **F2b Fingerprint:** empty artefact set; artefact unreadable; bad commit bytes.
  `failure_code`: `fingerprint_empty_artifacts|artifact_unreadable|git_bytes_invalid|bad_hex_encoding`.

---

### F3 — Non-finite or out-of-domain features / model outputs

**Run-abort.**

* **F3a S0.4:** `nonpositive_gdp`, `bucket_out_of_range`.
* **F3b S0.5/S0.7:** `hurdle_nonfinite` (non-finite `η`/`π`).

---

### F4 — RNG bootstrap / envelope / draw-accounting failures

**Run-abort.**

* **F4a:** `rng_audit_missing_before_first_draw`.
* **F4b:** `rng_envelope_violation` (missing required fields).
* **F4c:** `rng_counter_mismatch` (`after−before != blocks`).
* **F4d:** `rng_budget_violation` (per S0.3 budgets).

---

### F5 — Partitioning / lineage mismatch (dictionary-backed)

Wrong partition **or** row lineage doesn’t match path. **Run-abort.**
`failure_code`: `partition_mismatch`, `log_partition_violation`.

---

### F6 — Schema-authority breach

1A authority is **JSON-Schema** only. Any non-authoritative ref (e.g., Avro) → **Run-abort.**
`failure_code`: `non_authoritative_schema_ref`.

---

### F7 — Numeric policy violation (S0.8)

Binary64+RNE, no FMA, no FTZ/DAZ, deterministic libm, serial reductions. **Run-abort.**
`failure_code`: `numeric_rounding_mode|fma_detected|ftz_or_daz_enabled|libm_profile_mismatch|parallel_reduce_on_ordering_path`.

---

### F8 — Event coverage / corridor guarantees (state-specific)

Required event families missing/inconsistent; corridor breached. **Run-abort** for structural gaps; state may additionally log **merchant-abort** when allowed.
`failure_code`: `event_family_missing`, `corridor_breach`.

---

### F9 — Dictionary / path drift

Dataset path or lineage semantics deviates from dictionary. **Run-abort.**
`failure_code`: `dictionary_path_violation`.

---

### F10 — I/O integrity & atomics

Short writes, partial instances, non-atomic commit. **Run-abort.**
`failure_code`: `io_write_failure`, `incomplete_dataset_instance`.

---

## 1.1 Crosswalk: state-level `E_*` → S0.9 classes

To keep prior `E_*` codes, attach both:

| Example `E_*` (state)                 | S0.9 class | Canonical `failure_code`                  |
| ------------------------------------- | ---------- | ----------------------------------------- |
| `E_INGRESS_SCHEMA` (S0.1)             | F1         | `ingress_schema_violation`                |
| `E_PARAM_EMPTY`, `E_GIT_BYTES` (S0.2) | F2         | `param_file_missing`, `git_bytes_invalid` |
| `E_PI_NAN_OR_INF` (S0.7)              | F3         | `hurdle_nonfinite`                        |
| `E_AUTHORITY_BREACH` (S0.1)           | F6         | `non_authoritative_schema_ref`            |
| `E_NUM_FMA_ON` (S0.8)                 | F7         | `fma_detected`                            |
| `E_PARTITION_MISMATCH` (several)      | F5         | `partition_mismatch`                      |
| `E_RUNID_COLLISION_EXHAUSTED` (S0.2.4) | F2 | `runid_collision_exhausted` |

**Rule:** a failure record **must** carry both `failure_class` (F1…F10) and the concrete `failure_code` (snake_case).

---

## 2) Abort artefacts, paths, and atomics

### 2.1 Where the failure record lives (validation bundle)

Validation outputs are **fingerprint-scoped**. On the first failure:

```
data/layer1/1A/validation/failures/
  fingerprint={manifest_fingerprint}/
    seed={seed}/
      run_id={run_id}/
        failure.json                  # mandatory, single file
        _FAILED.SENTINEL.json         # duplicate of the forensic header (for quick scans)
```

* The directory is created and committed **atomically** (temp dir → rename).
* Re-runs that hit the **same** failure with the **same** lineage overwrite the temp but **not** the committed `failure.json`.

### 2.2 Failure record (normative JSON schema)

```json
{
  "type": "object",
  "required": ["failure_class","failure_code","state","module",
               "parameter_hash","manifest_fingerprint","seed","run_id",
               "ts_utc","detail"],
  "properties": {
    "failure_class": {"type":"string","enum":["F1","F2","F3","F4","F5","F6","F7","F8","F9","F10"]},
    "failure_code":  {"type":"string"},              // snake_case
    "state":         {"type":"string"},              // e.g., "S0.3"
    "module":        {"type":"string"},              // e.g., "1A.gumbel_sampler"
    "dataset_id":    {"type":"string"},              // optional
    "merchant_id":   {"type":["string","null"]},
    "parameter_hash":{"type":"string","pattern":"^[0-9a-f]{64}$"},
    "manifest_fingerprint":{"type":"string","pattern":"^[0-9a-f]{64}$"},
    "seed":          {"type":"integer","minimum":0},
    "run_id":        {"type":"string","pattern":"^[0-9a-f]{32}$"},
    "ts_utc":        {"type":"integer","minimum":0},
    "detail":        {"type":"object"}               // typed per failure_code (see below)
  }
}
```

**Timestamp encoding note (normative):**
* In **failure records**, `ts_utc` is an **unsigned integer**: **nanoseconds since the Unix epoch (UTC)**.
* In **RNG event envelopes** (S0.3.1), `ts_utc` is an **RFC-3339/ISO-8601 UTC string**.

**Typed `detail` payloads** (normative minima):

* `rng_counter_mismatch`: `{ "before":{"hi":u64,"lo":u64}, "after":{"hi":u64,"lo":u64}, "blocks": uint64, "draws": "uint128-dec" }`
* `partition_mismatch`: `{ "dataset_id":str, "path_key":str, "embedded_key":str }`
* `ingress_schema_violation`: `{ "row_pk":str, "field":str, "message":str }`
* `artifact_unreadable`: `{ "path":str, "errno":int }`
* `dictionary_path_violation`: `{ "expected":str, "observed":str }`
* `hurdle_nonfinite`: `{ "merchant_id":str, "field": "logit|pi", "value":"str" }`

### 2.3 Abort procedure (deterministic)

1. **Stop** emitting new events/datasets immediately.
2. **Flush & seal** validation bundle (path above) with `failure.json` (+ `_FAILED.SENTINEL.json`).
3. **Mark incomplete outputs**: delete temp dirs; if any partial partition escaped temp, write a sibling `_FAILED.json` sentinel **inside that partition** with `{dataset_id, partition_keys, reason}`.
4. **Freeze RNG**: no further RNG events; last counters remain as in the failing envelope.
5. **Exit non-zero**; orchestrator halts downstream.

### 2.4 Merchant-abort log (when a state allows soft aborts)

When a state defines **merchant-abort**, write (parameter-scoped):

```
.../prep/merchant_abort_log/parameter_hash={parameter_hash}/part-*.parquet
  { merchant_id, state, module, reason, ts_utc }
```

This log **never** replaces a run-abort; it records permitted soft fallbacks only.

---

## 3) Validator responsibilities (hardened)

* **Ingress schema** (F1).
* **Lineage recomputation** of `parameter_hash` & `manifest_fingerprint` (F2).
* **RNG envelope & counter conservation** for **every** event; budgets per family (F4).
* **Partition equivalence** (F5): parameter-scoped `{parameter_hash}`, logs `{seed,parameter_hash,run_id}`, egress/validation `{fingerprint}` (and often `seed`).
* **Numeric attestation** (F7): run S0.8 self-tests; verify `numeric_policy_attest.json` and reject mismatches.
* **Coverage/corridors** per state (F8).
* **Dictionary paths** (F9).
* **Instance completeness & atomics** (F10).

---

## 4) Where each failure is first detected

| Failure                         | First detector (preferred)        | Secondary                 |
| ------------------------------- | --------------------------------- | ------------------------- |
| F1 ingress schema               | S0.1 loader                       | Validator pass 1          |
| F2 params/fingerprint           | S0.2 hashing                      | Validator recompute       |
| F3 features / hurdle non-finite | S0.4 / S0.5 / S0.7 evaluators     | Validator recompute       |
| F4 envelope / counters          | Event emitters (runtime guards)   | Validator envelope pass   |
| F5 partitioning/lineage         | Dataset writer (path+embed check) | Validator partition lint  |
| F6 schema authority             | Registry/dictionary linter        | Validator schema refs     |
| F7 numeric policy               | S0.8 self-tests                   | Validator re-attest       |
| F8 coverage/corridor            | State invariants (S1/S2/S4/…)     | Validator family coverage |
| F9 dictionary/path drift        | Writer + dictionary linter        | Validator path lint       |
| F10 I/O atomics                 | Writer commit phase               | Validator completeness    |

---

## 5) Examples (concrete)

* **Missing audit row (F4a):** first RNG event is `hurdle_bernoulli` but `rng_audit_log` has no `run_id=…` → `rng_audit_missing_before_first_draw` → **Run-abort**.
* **Partition mismatch (F5):** write `outlet_catalogue` under `…/fingerprint=X` but embed row fingerprint `Y` → `partition_mismatch` → **Run-abort**.
* **Non-finite hurdle (F3b):** `η_m` becomes NaN due to malformed coefficients → `hurdle_nonfinite` → **Run-abort**.

---

## 6) Reference abort routine (language-agnostic)

```text
function abort_run(failure_class, failure_code, ctx):
  stop_emitters()                                  # no new RNG/events
  payload = build_failure_payload(failure_class, failure_code, ctx)  # includes lineage keys
  path = val_path(fingerprint=ctx.fp, seed=ctx.seed, run_id=ctx.run_id)
  write_atomic(path+"/failure.json", json(payload))
  write_atomic(path+"/_FAILED.SENTINEL.json", json(payload_header(payload)))
  mark_incomplete_partitions(ctx.inflight_outputs)
  exit_nonzero()
```

---

## 7) Determinism & idempotency guarantees

* Given identical inputs & environment, a failing run produces the **same** `failure_class`, `failure_code`, and **bit-identical** `failure.json`.
* Re-running without changing `manifest_fingerprint`/`parameter_hash` yields the **same** abort artefacts.
* Only the **first** detected failure is recorded; subsequent symptoms are suppressed to keep forensics clean.

---

**Bottom line:** S0.9 is now a precise, fingerprinted **fail-fast** contract: one vocabulary (F1–F10 + `failure_code`), one failure record schema, atomic/validated placement under `{fingerprint, seed, run_id}`, a clear E↔F crosswalk for state errors, and a deterministic abort routine. With this in place, **any** deviation from schema, lineage, RNG, numeric policy, or partitioning terminates the run loudly—with everything you need to reproduce and fix it.

---

# S0.10 — Outputs, Partitions & Validation Bundle (normative, fixed)

## S0.10.1 Lineage keys (recap; scope of use)
> **Consumer note (normative):** Egress `outlet_catalogue` does **not** encode cross‑country order; consumers MUST join `country_set.rank` (materialized in S6; the authority rule is recorded in S0.1) to obtain rank (0=home; foreigns by Gumbel order).

> **Tie-break (LRR, normative):** sort by quantised residual (desc), then **ISO code (ASCII) asc**. Do **not** use Gumbel rank as a secondary key.


* **`parameter_hash` (hex64):** partitions **parameter-scoped** artefacts. (S0.2.2)
* **`manifest_fingerprint` (hex64):** partitions **egress & validation** artefacts. (S0.2.3)
* **`seed` (u64):** modelling seed; used in RNG log partitions and S0.3 derivations.
* **`run_id` (hex32):** **logs only**; partitions RNG audit/trace/events. (S0.2.4)

**Embedding rule (row-level):**
* If a schema includes a **`parameter_hash`** column, its value **must equal** the directory key (`parameter_hash`).
* If a schema includes a **`manifest_fingerprint`** column, its value **must equal** the run’s `manifest_fingerprint`.
  For **egress/validation** datasets (fingerprint-scoped), it **must also equal** the directory key `fingerprint={manifest_fingerprint}`.
* For datasets with **both** columns present, both constraints must hold simultaneously.

Any mismatch triggers **S0.9/F5 run-abort**.

---

## S0.10.2 Artefact classes produced by S0

1. **Parameter-scoped model inputs/caches** (deterministic; reusable across runs with the same `parameter_hash`)

* `crossborder_eligibility_flags` (S0.6).
* `hurdle_pi_probs` (S0.7, **optional** diagnostics).
* *(Optionally transient; not authoritative)*: `hurdle_design_matrix`.

2. **Lineage & attestation files** (**fingerprint-scoped**)

* `validation_bundle_1A` directory (see §S0.10.5), containing:

  * `MANIFEST.json`
  * `parameter_hash_resolved.json`
  * `manifest_fingerprint_resolved.json`
  * `param_digest_log.jsonl`
  * `fingerprint_artifacts.jsonl`
  * `numeric_policy_attest.json` (S0.8)
  * optional: `DICTIONARY_LINT.txt`, `SCHEMA_LINT.txt`
  * `_passed.flag` (gate)

3. **RNG logs (for partition contract completeness; produced at S0.3+)**

* `rng_audit_log`, `rng_trace_log`, `rng_event_*` (see §S0.10.3 “Log-scoped”).

---

## S0.10.3 Partitioning & paths (authoritative)

**Naming rule (normative):** Any path segment named `fingerprint={…}` **always** carries the value of `manifest_fingerprint`. The column name is `manifest_fingerprint`; the path label remains `fingerprint=…`.

**RNG logs (normative paths & keys):**
`rng_audit_log` → `logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl`
`rng_trace_log` → `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`
`rng_event_*` → `logs/rng/events/{family}/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
Partitioning for all three: `["seed","parameter_hash","run_id"]`. The dataset dictionary remains authoritative for any additional fields.

### Parameter-scoped (partition by `parameter_hash`)

**Dataset:** `crossborder_eligibility_flags`
**Path:** `data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/part-*.parquet`
**Schema:** `schemas.1A.yaml#/prep/crossborder_eligibility_flags`
**Row keys:** `merchant_id` (PK)
**Embedded lineage (normative):** `parameter_hash` (required; equals path key). Optional: `produced_by_fingerprint` (hex64), **informational only** and **never** part of partition keys/equality.

**Dataset (optional):** `hurdle_pi_probs`
**Path:** `data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/part-*.parquet`
**Schema:** `schemas.1A.yaml#/model/hurdle_pi_probs`
**Row keys:** `merchant_id` (PK)
**Embedded lineage (normative):** `parameter_hash` (required; equals path key). Optional: `produced_by_fingerprint` (hex64), **informational only** and **never** part of partition keys/equality.

> **Write semantics (both):** **overwrite-atomic** per partition (stage in `…/_tmp.{uuid}` → single `rename(2)`). Partial contents must never become visible (S0.9/F10).

### Fingerprint-scoped (partition by `fingerprint`)

**Directory:** `validation_bundle_1A`
**Path:** `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`
**Contents:** §S0.10.5.

### Log-scoped (RNG)

**Logs:** `rng_audit_log`, `rng_trace_log`, each `rng_event_*`
**Path template:** `logs/rng/<stream>/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
> **Authority (normative):** Actual **paths and partition columns** are authoritative in the **dataset dictionary**. Strings shown here are examples to illustrate shape.

> **Physical line order (normative):** For RNG **JSONL** logs, line order is append order **within a file**; there are **no ordering guarantees across files/parts**. Equality is by **row set**; any consumer that depends on physical order is non-conformant.

**Envelope (per S0.3):** `{seed, parameter_hash, manifest_fingerprint, run_id, module, substream_label, counter_before/after, blocks, draws, ts_utc, payload…}`.
`rng_trace_log` aggregates **blocks**.
---

## S0.10.4 Immutability, idempotence & retention

* **Immutability:** A concrete partition directory is **immutable**. Re-runs with the same keys either no-op or atomically replace with **byte-identical** content.
* **Idempotence:** With identical inputs and numeric policy, outputs are **bit-identical** (file order within a Parquet partition is out-of-contract).
* **Retention:**

  * Parameter-scoped: keep last **N=5** `parameter_hash` generations (policy).
  * Validation bundles: keep **all** `manifest_fingerprint` generations.
  * RNG logs: retain per compliance (e.g., 90 days).

---

## S0.10.5 Validation bundle (structure, hashing, gate)

```
validation/
  fingerprint={manifest_fingerprint}/
    MANIFEST.json
    parameter_hash_resolved.json
    manifest_fingerprint_resolved.json
    param_digest_log.jsonl
    fingerprint_artifacts.jsonl
    numeric_policy_attest.json
    DICTIONARY_LINT.txt          # optional
    SCHEMA_LINT.txt              # optional
    _passed.flag
```

**`MANIFEST.json` (normative fields)**

```json
{
  "version": "1A.validation.v1",
  "manifest_fingerprint": "<hex64>",
  "parameter_hash": "<hex64>",
  "git_commit_hex": "<hex40-or-64>",
  "artifact_count": 123,
  "math_profile_id": "mlr-math-1.2.0",
  "compiler_flags": {"fma": false, "ftz": false, "rounding": "RNE", "fast_math": false, "blas": "none"},
  "created_utc_ns": 1723700000123456789
}
```

**`parameter_hash_resolved.json`**

```json
{"parameter_hash":"<hex64>","filenames_sorted":["crossborder_hyperparams.yaml","hurdle_coefficients.yaml","nb_dispersion_coefficients.yaml"]}
```

**`manifest_fingerprint_resolved.json`**

```json
{"manifest_fingerprint":"<hex64>","git_commit_hex":"<hex40-or-64>","parameter_hash":"<hex64>","artifact_count":123}
```

**`param_digest_log.jsonl`** — one JSON line per governed parameter file: `{filename,size_bytes,sha256_hex,mtime_ns}`.
**`fingerprint_artifacts.jsonl`** — one JSON line per opened artefact: `{path,sha256_hex,size_bytes}`.
**`numeric_policy_attest.json`** — S0.8 self-tests/flags & IDs.

**Gate `_passed.flag` (mandatory):**
Contains one line: `sha256_hex = <hex64>`, where `<hex64>` is **SHA-256 over the raw byte concatenation** of **all other bundle files** in **ASCII lexicographic filename order**. `_passed.flag` itself is **excluded** from the hash.
Downstream **must** verify this; mismatch ⇒ treat run as invalid (S0.9/F10).

---

## S0.10.6 Writer behavior (atomicity & lints)

* **Atomic publish:** write bundle into `…/validation/_tmp.{uuid}`; compute `_passed.flag`; single atomic `rename(2)` to `fingerprint=…/`. On failure, delete tmp.
* **Optional lints:**

  * `DICTIONARY_LINT.txt`: diff of dictionary vs observed writer paths/schema refs.
  * `SCHEMA_LINT.txt`: results of schema validation of produced datasets.
    By default these **are included** in the gate hash; you may exclude them only if documented (then also omit them from the hash computation consistently).

---

## S0.10.7 Idempotent re-runs & equivalence

Two bundles are **equivalent** if:

* `MANIFEST.json` matches byte-for-byte.
* all other files match byte-for-byte and `_passed.flag` hashes match.

---

## S0.10.8 Pseudocode (reference)

```text
function S0_10_emit_outputs_and_bundle(ctx):
  # Assert parameter-scoped partitions exist (S0.6/S0.7 may have written them)
  assert partition_exists("crossborder_eligibility_flags", ctx.parameter_hash)
  if ctx.emit_hurdle_pi_probs:
      assert partition_exists("hurdle_pi_probs", ctx.parameter_hash)

  # Build bundle in temp dir
  tmp = mktempdir()
  write_json(tmp+"/MANIFEST.json", {
    "version":"1A.validation.v1",
    "manifest_fingerprint":ctx.fingerprint,
    "parameter_hash":ctx.parameter_hash,
    "git_commit_hex":ctx.git_commit_hex,
    "artifact_count":len(ctx.artifacts),
    "math_profile_id":ctx.math_profile_id,
    "compiler_flags":ctx.compiler_flags,
    "created_utc_ns":now_ns()
  })
  write_json(tmp+"/parameter_hash_resolved.json", {
    "parameter_hash":ctx.parameter_hash,
    "filenames_sorted":ctx.param_filenames_sorted
  })
  write_json(tmp+"/manifest_fingerprint_resolved.json", {
    "manifest_fingerprint":ctx.fingerprint,
    "git_commit_hex":ctx.git_commit_hex,
    "parameter_hash":ctx.parameter_hash,
    "artifact_count":len(ctx.artifacts)
  })
  write_jsonl(tmp+"/param_digest_log.jsonl", ctx.param_digests)
  write_jsonl(tmp+"/fingerprint_artifacts.jsonl", ctx.artifact_digests)
  write_json(tmp+"/numeric_policy_attest.json", ctx.numeric_attest)

  # Gate: hash all files except the flag
  files = list_ascii_sorted(tmp)           # lexicographic ASCII
  H = sha256_concat_bytes([read_bytes(f) for f in files if basename(f) != "_passed.flag"])
  write_text(tmp+"/_passed.flag", "sha256_hex = " + hex64(H) + "\n")

  # Atomic publish under fingerprint partition
  publish_atomic(tmp, "data/layer1/1A/validation/fingerprint="+ctx.fingerprint)
```

---

## S0.10.9 Validation (CI/runtime must assert)

* **Partition lint:** parameter-scoped datasets live under `parameter_hash=…`; rows embed the same `parameter_hash`; RNG logs use `{seed,parameter_hash,run_id}`; validation bundle under `fingerprint=…`.
* **Bundle integrity:** presence of all required files and `_passed.flag` hash match.
* **Schema conformance:** produced datasets validate against their JSON-Schema anchors.
* **Lineage recomputation:** `parameter_hash` and `manifest_fingerprint` recomputed equal the `*_resolved.json` values.
* **Numeric attestation:** `numeric_policy_attest.json` indicates **all** S0.8 self-tests passed.

---

## S0.10.10 Downstream consumption rules

* **Parameter-scoped readers** (S1/S2/S3): key by **`parameter_hash`** only; ignore `run_id`.
* **Egress/validation consumers:**

  1. locate `fingerprint={manifest_fingerprint}`,
  2. verify `_passed.flag`,
  3. (optional) re-hash `fingerprint_artifacts.jsonl` & `param_digest_log.jsonl`.
     Any failure ⇒ treat run as invalid and halt per S0.9.

---

**Bottom line:** S0.10 locks S0’s outputs into clear, non-overlapping partitions: parameter-scoped datasets embed **only `parameter_hash`** (with optional `produced_by_fingerprint`), RNG logs are `{seed,parameter_hash,run_id}`, and the **validation bundle** is fingerprint-scoped and **gate-protected**. Everything is atomic, idempotent, and CI-provable.

---