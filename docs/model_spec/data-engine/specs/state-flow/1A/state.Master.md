# S · States (Expanded) — Master

> Single-file compendium of deterministic, frozen expanded specs for subsegment **1A**, states **S0–S9**.

# Contents
- [S0 — Expanded](#S0.EXP)  
- [S1 — Expanded](#S1.EXP)  
- [S2 — Expanded](#S2.EXP)  
- [S3 — Expanded](#S3.EXP)  
- [S4 — Expanded](#S4.EXP) 

---

# S0 — Expanded
<a id="#S0.EXP"></a>
<!-- SOURCE: /s3/states/state.1A.s0.expanded.txt  *  VERSION: v0.0.0 -->

[S0-BEGIN VERBATIM]

## S0.1 — Universe, Symbols, Authority (normative, fixed)

### Purpose & scope

S0.1 establishes the **canonical universe** (merchant rows and reference datasets) and the **schema authority** for subsegment 1A. Its job is to make the rest of S0–S9 reproducible by fixing the domain symbols and where their truth comes from. **No RNG is consumed here.**

**S0.1 freezes for the run**

* The merchant universe $\mathcal{M}$ from the **normalised ingress** table `merchant_ids`.
* The immutable **reference artefacts**: ISO-3166 country set $\mathcal{I}$; GDP-per-capita vintage $G$ pinned to **2025-04-15**; a precomputed Jenks $K{=}5$ GDP bucket map $B$.
* The **schema authority**: only JSON-Schema contracts in `schemas.ingress.layer1.yaml`, `schemas.1A.yaml`, and shared RNG/event schemas in `schemas.layer1.yaml` are authoritative; Avro (if any) is **non-authoritative**.

> Downstream consequence (normative): **inter-country order is never encoded** in egress `outlet_catalogue`; consumers **MUST** join `country_set.rank` (0 = home; foreigns follow Gumbel selection order). S0.1 records that rule as part of the authority.

---

### Domain symbols (definitions and types)

#### Merchants (ingress universe)

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

#### Canonical references (immutable within the run)

* **Countries:** $\mathcal{I}$ = ISO-3166 alpha-2 country list (finite, determined by the pinned reference).
* **GDP (per-capita) map:** $G:\mathcal{I}\rightarrow\mathbb{R}_{>0}$, **pinned to 2025-04-15** (fixes both values and coverage).
* **GDP bucket map:** $B:\mathcal{I}\rightarrow{1,\dots,5}$ — a precomputed Jenks $K=5$ classification over $G$. (S0.4 documents the CI-only rebuild; for S0.1 this artefact is immutable input.)

#### Derived per-merchant tuple

For $m\in\mathcal{M}$, define the typed quadruple used downstream:

$$
t(m):=\big(\texttt{mcc}_m,\ \texttt{channel}_m\in\{\mathrm{CP},\mathrm{CNP}\},\ \texttt{home_country_iso}_m,\ \texttt{merchant_u64}_m\big)\in\mathcal{K}\times\mathcal{C}\times\mathcal{I}\times\mathbb{U}_{64}.
$$

---

### Authority & contracts (single source of truth)

#### Authoritative schemas for 1A

Only **JSON-Schema** is the source of truth for 1A. All dataset contracts and RNG event contracts must refer to these paths (JSON Pointer fragments):

* Ingress: `schemas.ingress.layer1.yaml#/merchant_ids`.
* 1A model/prep/alloc/egress: `schemas.1A.yaml` (e.g., `#/model/hurdle_pi_probs`, `#/prep/sparse_flag`, `#/alloc/country_set`, `#/egress/outlet_catalogue`).
* Shared RNG events: `schemas.layer1.yaml#/rng/events/*`.

Avro (`.avsc`) is **non-authoritative** for 1A and must not be referenced by registry/dictionary entries.

#### Semantic clarifications (normative)

* `country_set` is the **only** authority for **cross-country order** (rank: 0 = home, then foreigns). Egress `outlet_catalogue` does **not** carry cross-country order; consumers **must** join `country_set.rank`.
* **Partitioning semantics** (recorded here as authority, implemented in S0.10): parameter-scoped datasets partition by `parameter_hash`; egress/validation partition by `manifest_fingerprint`.

---

### Run-time invariants (frozen context)

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

### Failure semantics (abort codes)

S0.1 **MUST abort** the run if any of the following occur:

* `E_INGRESS_SCHEMA` — `merchant_ids` fails validation against `schemas.ingress.layer1.yaml#/merchant_ids`.
* `E_REF_MISSING` — any canonical reference (ISO list, GDP vintage, or bucket map) is missing or unreadable. (S0.2 separately catches digest mismatches when hashing.)
* `E_AUTHORITY_BREACH` — a dataset or event in registry/dictionary points to a non-JSON-Schema (e.g., an `.avsc`) for 1A.
* `E_FK_HOME_ISO` — some merchant has `home_country_iso` not in 𝕀.
* `E_MCC_OUT_OF_DOMAIN` — some merchant has `mcc` outside **[0,9999]** or violates the ingress type constraints.
* `E_CHANNEL_VALUE` — some merchant has an ingress `channel` not in `{"card_present","card_not_present"}` (cannot map to `{CP,CNP}`).

> When S0.1 aborts, no RNG audit or parameter/fingerprint artefacts are emitted; S0.2 has not yet run.

---

### Validation hooks (what CI/runtime checks here)

* **Schema check:** validate `merchant_ids` against the ingress schema before deriving $t(m)$.
* **Reference presence & immutability:** assert that the referenced ISO set, GDP vintage (2025-04-15), and $B$ load successfully and are cached read-only for the lifetime of the run.
* **Authority audit:** scan the registry/dictionary for any 1A dataset using **non-JSON-Schema** refs and fail the build if found (policy enforcement).
* **Country FK pre-check:** `home_country_iso ∈ 𝕀` for all merchants.
* **MCC & channel domain checks:** `mcc ∈ [0,9999]`; `channel ∈ {"card_present","card_not_present"}` with a deterministic map → `{CP,CNP}`.

---

### Reference routine (language-agnostic)

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

### Notes for downstream states

* S0.2 will **hash** the loaded bytes (parameters and artefacts) to derive `parameter_hash` and `manifest_fingerprint`, and log provenance. S0.1’s immutability guarantees make those digests stable.
* All RNG substream keying that requires a merchant u64 **must** use `merchant_u64` defined here; there is no alternate mapping.
* S3’s eligibility and S6’s `country_set` persistence rely on S0.1’s **country FK** and the **channel symbol** (`CP`/`CNP`) set here.

---

**Summary:** S0.1 now pins the **who** (merchants + canonical `merchant_u64`), the **where** (countries), the **context** (GDP & buckets), and the **law** (JSON-Schema authority + cross-country order rule). It consumes **no randomness**, enforces domain validity **here**, and fails fast on any schema/authority/coverage breach—so everything that follows sits on a rock-solid, reproducible base.

---

## S0.2 — Hashes & Identifiers (Parameter Set, Manifest Fingerprint, Run ID)

### Purpose (what S0.2 guarantees)

Create the three lineage keys that make 1A reproducible and auditable:

1. **`parameter_hash`** — versions *parameter-scoped* datasets; changes when any governed parameter file’s **bytes** change.
2. **`manifest_fingerprint`** — versions *egress & validation* outputs; changes when **any opened artefact**, the **code commit**, or the **parameter bundle** changes.
3. **`run_id`** — partitions logs; **not** part of modelling state; never influences RNG or outputs.

**No RNG is consumed in S0.2.** These identifiers are pure functions of bytes + time (for `run_id` only as a log partitioner).

---

### S0.2.1 Hash primitives & encoding (normative)

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

### S0.2.2 `parameter_hash` (canonical, normative)

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

### S0.2.3 `manifest_fingerprint` (egress/validation lineage)

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

### S0.2.4 `run_id` (logs only; not modelling state)

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

### Partitioning contract (authoritative)

| Dataset class       | Partition keys (in order)          |
|---------------------|------------------------------------|
| Parameter-scoped    | `parameter_hash`                   |
| Egress & validation | `manifest_fingerprint`             |
| RNG logs & events   | `seed`, `parameter_hash`, `run_id` |

*(Row-embedded key columns must equal their path keys byte-for-byte.)*

---

### Operational requirements

* **Streaming digests:** compute all file digests via streaming; hash exact bytes.
* **Race guard:** `stat` (size, mtime) **before/after** hashing; if changed, re-read or fail (`E_PARAM_RACE` / `E_ARTIFACT_RACE`).
* **Basename semantics:** sort by **basename** (no directories); basenames must be ASCII, unique; **abort** on duplicates.
* **Immutability:** After S0.2, treat `parameter_hash` & `manifest_fingerprint` as **final** for the run; embed them in all envelopes/partitions.

---

### Failure semantics

On any `E_PARAM_*`, `E_ARTIFACT_*`, `E_GIT_*`, race error or `E_RUNID_COLLISION_EXHAUSTED` (loop exceeded 2^16) abort the run per S0.9. On abort in S0.2, **do not** emit RNG audit/trace; S0.3 hasn’t begun.

---

#### Validation & CI hooks

* **Recompute:** CI recomputes `parameter_hash` from 𝓟 and `manifest_fingerprint` from (enumerated 𝓐, `git_32`, `parameter_hash_bytes`). Must match logged `*_resolved` rows.
* **Partition lint:** dictionary enforces the partition table above; RNG logs must use `{ seed, parameter_hash, run_id }`.
* **Uniqueness:** within `{ seed, parameter_hash }`, `run_id` must be unique (practically guaranteed; guards clock bugs).

---

### Reference pseudocode (language-agnostic)

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

### Where this shows up next

S0.3 derives the master RNG seed/counters using `manifest_fingerprint_bytes` and `seed`. Therefore S0.2 **must** complete before any RNG event emission.

---

**Bottom line:** S0.2 now uses a **tuple-hash, name-aware, length-prefixed** combiner (no XOR), with universal encoding rules and raw commit bytes. The partitioning contract is crystal-clear, and `run_id` is log-only. This is ready to hand straight to an implementer.

---

## S0.3 — RNG Engine, Substreams, Samplers & Draw Accounting (normative, fixed)

> **Notation (normative):** `ln(x)` denotes the natural logarithm. The unqualified `log` MUST NOT appear in kernels or acceptance tests.

### Purpose

S0.3 pins the *entire* randomness contract for 1A: which PRNG we use, how we carve it into **keyed, order-invariant** substreams, how we map bits to **(0,1)**, how we generate $Z\sim\mathcal N(0,1)$, $\Gamma(\alpha,1)$, and $\text{Poisson}(\lambda)$, and how every draw is **counted, logged, and reproducible**. **S0.3 does not consume RNG events; it defines the contracts and writes the single audit row only (no draws in S0).**

---

### S0.3.1 Engine & Event Envelope
> **Practical bound (normative):** `blocks` is `uint64`. Producers MUST ensure a single event’s block consumption fits this width. If an event would exceed this bound, emit `F4d:rng_budget_violation` and abort the run.

#### PRNG (fixed)

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

#### Event envelope (mandatory fields on **every** RNG event row)
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

### S0.3.2 Master seed & initial counter (per run)
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

### S0.3.3 Keyed, order-invariant substreams

Every logical substream is keyed by a deterministic tuple; **never** by execution order.

#### Substream derivation (UER, no delimiters) *(SER = integer encodings under UER: LE32 indices; LE64 keys)*
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

### S0.3.4 Uniforms on the **open** interval $(0,1)$

**Normative mapping:**

```text
# x is u64; map to strictly (0,1) — never 0.0, never 1.0
u = ((x + 1) * 0x1.0000000000000p-64)
if u == 1.0: u := 0x1.fffffffffffffp-1   # max < 1 in binary64 (1 - 2^-53)
```

This is the required implementation of the open-interval rule. Computing `1/(2^64+1)` at runtime or using decimal literals is **forbidden**.

### S0.3.5 Standard normal $Z\sim\mathcal N(0,1)$ (Box–Muller, no cache)

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

### S0.3.6 Gamma $\Gamma(\alpha,1)$ (Marsaglia–Tsang; exact actual-use budgeting)
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

### S0.3.7 Poisson $\text{Poisson}(\lambda)$ & ZTP scaffolding

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

### S0.3.8 Gumbel key from a single uniform

For candidate ranking:

* Draw $u\in(0,1)$; compute $g=-\ln(-\ln u)$.
* **Budget:** **1 uniform** per candidate (single-lane low; event-level `draws="1"`).
* **Tie-break:** sort primarily by $g$, then by `ISO` (ASCII ascending), then by `merchant_id` if still tied.
* **Log:** one `gumbel_key` event **per candidate**.

---

### S0.3.9 Draw accounting & logs (auditable replay)
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

### S0.3.10 Determinism & failure semantics

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

### Reference pseudocode (language-agnostic)

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

### Guarantees to downstream states

* Any module declares `(substream_label, ids)` and receives a **stable, independent** substream—order/shard-invariant.
* Samplers have **pinned** budgets (constant where possible; fully logged where variable).
* Given `(seed, parameter_hash, manifest_fingerprint, run_id)` and the envelopes, every draw is **replayable exactly**.

---

**Summary:** S0.3 pins Philox 2×64-10, the **low-lane policy** for single uniforms, **UER-based** substream derivation, one **open-interval** `u01`, Box–Muller (**no cache**), Gamma (Marsaglia–Tsang) with **exact actual-use budgeting**, Poisson with a **fully specified** inversion/PTRS split, and strict **draw accounting** tied to counters. This is deterministic, auditable, and ready to implement. Gumbel keys break ties by ISO, then merchant_id.

---

## S0.4 — Deterministic GDP Bucket Assignment (normative, fixed)

### Purpose

Attach to every merchant $m$ two **deterministic**, **non-stochastic** features from pinned references:

* $g_c$ — GDP-per-capita level for the merchant’s **home** country $c$ from the **2025-04-15** WDI extract, **at a fixed observation year** (see below), and
* $b_m\in\{1,\dots,5\}$ — the **Jenks** $K{=}5$ GDP bucket id for that home country from the **precomputed** mapping table.

**No RNG** is consumed here. S0.4 is a pure function of bytes fixed by S0.1–S0.2.

---

### Inputs & domains (read-only, pinned)

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

### Canonical definition (what S0.4 does)

For $m\in\mathcal M$ with $c=\texttt{home_country_iso}(m)\in\mathcal I$,

$$
g_c \leftarrow G(c)\in\mathbb R_{>0},\qquad
b_m \leftarrow B(c)\in\{1,2,3,4,5\}.
$$

These are **lookups** only; **no** thresholds are calculated at runtime.

---

### Semantics & downstream usage

* $b_m$ (Jenks bucket) appears **only** in the hurdle design as five one-hot dummies (column order frozen by the fitting bundle).
* $\log g_c$ appears **only** in NB **dispersion** (never in the mean).
* If materialised, these features live under `…/parameter_hash={parameter_hash}/` (parameter-scoped model artefacts), governed by `schemas.1A.yaml` (e.g., `#/model/hurdle_design_matrix`, `#/model/hurdle_pi_probs`). They are otherwise transient into S0.5.

---

### Determinism & numeric policy

* **No randomness;** outputs identical across shards and reruns with the same `manifest_fingerprint`.

* Any derived transforms (e.g., $\log g_c$ in S0.5) use **binary64**, no FMA, serial evaluation order (S0.8).

* **Class semantics (for CI intuition only):** if $B$ were rebuilt, thresholds $\tau_0<\dots<\tau_5$ satisfy
  $B(c)=k \iff G(c)\in(\tau_{k-1},\tau_k]$ (classes are **right-closed**). The *authoritative* truth remains the shipped table $B$.

---

### Failure semantics (abort; zero tolerance)

Abort with a clear message (including offending dataset and PK) if any holds:

* `E_HOME_ISO_FK(m,c)`: `home_country_iso` not in the run’s ISO set (S0.1).
* `E_GDP_MISSING(c)`: no GDP row for `c` at `observation_year=2024`.
* `E_GDP_NONPOS(c, g_c)`: GDP value $\le 0$ (double-guard; schema forbids).
* `E_BUCKET_MISSING(c)`: no bucket row for `c` in `gdp_bucket_map_2024`.
* `E_BUCKET_RANGE(c, b)`: bucket not in $\{1..5\}$ (double-guard; schema forbids).

---

### Validation hooks (runtime & CI)

1. **Coverage:** every `home_country_iso` in `merchant_ids` has both $G(c)$ and $B(c)$.
2. **FK integrity:** all `country_iso` in GDP & bucket tables are members of the run’s ISO set.
3. **Lineage evidence:** both artefacts are present in the **manifest fingerprint** enumeration (counts & digests logged by S0.2).
4. **Optional CI rebuild (non-runtime):** recompute Jenks $K{=}5$ from the pinned $G(\cdot)$ and assert equality with `gdp_bucket_map_2024`; fail with a per-ISO diff if not identical.

---

### Optional rebuild spec for $B$ (CI only; deterministic)

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

### Reference routine (runtime path; language-agnostic)

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

### Complexity, concurrency, partitions

* **Time:** $O(|\mathcal M|)$ hash lookups; **Space:** $O(1)$ per streamed row.
* **Parallelism:** embarrassingly parallel; determinism holds (pure lookups).
* **Lineage & partitions:** both GDP and bucket artefacts are in the **manifest fingerprint**; changing either flips egress partitions. If features are materialised into design artefacts, they are **parameter-scoped** (partitioned by `parameter_hash` only; **do not** embed `manifest_fingerprint` in parameter-scoped tables).

---

**Bottom line:** S0.4 is a strict, zero-RNG lookup that attaches $(g_c,b_m)$ from a *single*, pinned GDP vintage (obs-year 2024, const-2015-USD) and its precomputed Jenks-5 map. Rebuild rules are deterministic (CI-only), class semantics are right-closed, failure codes are explicit, and storage/lineage boundaries are clear—so S0.5+ can consume these as immutable inputs.

---

## S0.5 — Design Matrices (Hurdle & NB), Column Discipline, and Validation (normative, fixed)

### Purpose & scope

Deterministically construct **column-aligned design vectors** for each merchant $m$ for:

* the **hurdle logistic** (single vs. multi) used in **S1**, and
* the **Negative-Binomial (NB)** branch used in **S2** (mean and dispersion links).

**Column dictionaries and ordering are frozen by the model-fitting bundle** and are **never recomputed at runtime**. **No RNG** is consumed here.

---

### Inputs (read-only; pinned by S0.1–S0.4)

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

### Encoders (deterministic one-hots; column-frozen)

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

### Design vectors (definitions, dimensions, strict order)

For merchant $m$ with $c=\texttt{home_country_iso}(m)$, $g_c>0$, $b_m\in\{1,\dots,5\}$:

#### Hurdle (logit) design

$$
\boxed{\,x_m=\big[1,\ \phi_{\text{mcc}}(\texttt{mcc}_m),\ \phi_{\text{ch}}(\texttt{channel_sym}_m),\ \phi_{\text{dev}}(b_m)\big]^\top\,}\in\mathbb R^{1+C_{\text{mcc}}+2+5}.
$$

$$
\eta_m=\beta^\top x_m,\qquad \pi_m=\sigma(\eta_m)=\frac{1}{1+e^{-\eta_m}}.
$$

All hurdle coefficients, including the 5 bucket dummies, are in **one** ordered vector $\beta$.

#### Negative-Binomial (used in S2)

$$
\boxed{\,x^{(\mu)}_m=\big[1,\ \phi_{\text{mcc}}(\texttt{mcc}_m),\ \phi_{\text{ch}}(\texttt{channel_sym}_m)\big]^\top\,}\in\mathbb R^{1+C_{\text{mcc}}+2},
$$

$$
\boxed{\,x^{(\phi)}_m=\big[1,\ \phi_{\text{mcc}}(\texttt{mcc}_m),\ \phi_{\text{ch}}(\texttt{channel_sym}_m),\ \ln g_c\big]^\top\,}\in\mathbb R^{1+C_{\text{mcc}}+2+1}.
$$

**Leakage guard (enforced):** bucket dummies **not** present in $x^{(\mu)}$; $\ln g_c$ present **only** in $x^{(\phi)}$.

---

### Safe logistic evaluation (notation consistent with §S0.3: ln = natural log) (overflow-stable, no clamp in compute path)

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

### Determinism & numeric policy

* **No randomness**; outputs depend only on frozen dictionaries and S0.4 features.
* IEEE-754 **binary64**; on ordering-critical paths (any later reductions/normalisations that involve these vectors), **no FMA** and **serial reductions** per S0.8. Changing these toggles changes the numeric-policy artefact and thus the fingerprint.

---

### Persistence (optional) & partitions

By default, $x_m, x^{(\mu)}_m, x^{(\phi)}_m$ are **in-memory**. If materialised:

* `hurdle_design_matrix` under `…/parameter_hash={parameter_hash}/…` with schema `schemas.1A.yaml#/model/hurdle_design_matrix`.
* Optional diagnostics: `hurdle_pi_probs` under `…/parameter_hash={parameter_hash}/…` with schema `#/model/hurdle_pi_probs` (**never** used by samplers).

**Partitioning (normative):** these caches are **parameter-scoped**.

* **Rows must embed** the same `parameter_hash` as the directory key.
* **Do not embed** `manifest_fingerprint` as a required column in parameter-scoped outputs.

---

### Validation hooks (must pass)

1. **Column alignment / shapes**

   * `len(beta_hurdle) == 1 + C_mcc + 2 + 5`.
   * The NB dispersion coefficient vector matches `1 + C_mcc + 2 + 1`.
   * The **dictionary order** used to build vectors matches the order implied by the coefficient vectors. Any drift is a hard error.
2. **One-hot correctness** — each encoder emits exactly one “1”.
3. **Feature domains** — `g_c > 0`; `b_m ∈ {1..5}` (from S0.4).
4. **Leakage guard (machine-checked)** — bucket dummies appear in `x_m` only; `ln(g_c)` appears in `x^{(φ)}_m` only.
5. **Partition lint (if persisted)** — embedded `parameter_hash` equals the path key exactly; otherwise `E_PARTITION_MISMATCH`.

---

### Failure semantics (precise aborts)

* `E_DSGN_UNKNOWN_MCC(mcc)` — MCC absent from the fitting dictionary.
* `E_DSGN_UNKNOWN_CHANNEL(ch)` — channel symbol not in `{CP,CNP}`.
* `E_DSGN_SHAPE_MISMATCH(exp_dim, got_dim)` — coefficient/design dimension mismatch.
* `E_DSGN_DOMAIN_GDP(g)` — `g_c ≤ 0`.
* `E_DSGN_DOMAIN_BUCKET(b)` — `b ∉ {1..5}`.
* `E_PARTITION_MISMATCH(id, path_key, embedded_key)` — parameter-scoped persistence key mismatch.

---

### Reference algorithm (language-agnostic)

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

### Complexity & concurrency

* **Time:** $O(|\mathcal M|)$ with constant work per row.
* **Space:** streaming; one merchant at a time.
* **Parallelism:** embarrassingly parallel; determinism holds (frozen dictionaries + S0.4 lookups).

---

### Downstream connections

* **S1** consumes $(x_m,\beta)$ to compute $\eta_m$ and then the Bernoulli hurdle; S1 **aborts** on any design/coeff mismatch.
* **S2** consumes $(x^{(\mu)}_m,x^{(\phi)}_m)$ for NB mean/dispersion; all RNG usage there follows S0.3’s envelope/budget rules.

---

**Summary:** S0.5 now gives an implementer the exact, frozen layout for hurdle and NB designs, enforces the CP/CNP vocabulary and the “bucket-in-hurdle / log-GDP-in-dispersion” rule, and cleanly separates parameter-scoped persistence from egress lineage. It’s deterministic, leakage-proof, and ready to wire into S1/S2.

---

## S0.6 — Cross-border Eligibility (deterministic gate, normative, fixed)

### Purpose

Decide, **without randomness**, whether each merchant $m$ is permitted to attempt cross-border expansion later (i.e., enter S4–S6). 
Persist **exactly one row per merchant** to the parameter-scoped dataset **`crossborder_eligibility_flags`** with fields `(parameter_hash, merchant_id, is_eligible, reason, rule_set)` (optionally `produced_by_fingerprint` for provenance).

* **Parameter-scoped** ⇒ partition by `parameter_hash`; **rows embed `parameter_hash`** (required by schema). `produced_by_fingerprint` (hex64) is optional and informational.

No RNG is consumed in S0.6.

---

### Inputs (read-only; pinned earlier)

* **Merchant tuple** $t(m)=(\texttt{mcc}_m,\texttt{channel_sym}_m,\texttt{home_country_iso}_m)$ from `merchant_ids` (S0.1), where `channel_sym ∈ {CP,CNP}` (S0.1 mapping is authoritative).
* **Parameter bundle:** `crossborder_hyperparams.yaml` (governed by `parameter_hash`; contains the eligibility rule set).
* **Lineage keys:** `parameter_hash` (partition path and embedded column).
* **Schema & dictionary:** dataset `crossborder_eligibility_flags` → partitioned by `{parameter_hash}`, schema `schemas.1A.yaml#/prep/crossborder_eligibility_flags`.

---

### Output (authoritative)

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

### Domains & symbols

* Channels $\mathcal C=\{\text{CP},\text{CNP}\}$ (internal symbols only; ingress strings are mapped in S0.1).
* Countries $\mathcal I$: ISO-3166 alpha-2 set (uppercase ASCII; pinned in S0.1).
* MCC set $\mathcal K$: 4-digit codes (domain pinned in S0.1).

---

### Rule family (configuration semantics)

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

### Set interpretation & matching (normative)

After expanding `"*"` and MCC ranges:

* Each rule $r$ defines sets $S_{\rm mcc}\subseteq\mathcal K$, $S_{\rm ch}\subseteq\mathcal C$, $S_{\rm iso}\subseteq\mathcal I$ and a decision $d\in\{\textsf{allow},\textsf{deny}\}$.
* **Match:** $r$ matches $m$ iff $ \texttt{mcc}_m\in S_{\rm mcc} \land \texttt{channel_sym}_m\in S_{\rm ch} \land \texttt{home_country_iso}_m\in S_{\rm iso}$.

**Range semantics (MCC):** `"5000-5999"` means all integer codes $5000 \le \text{MCC} \le 5999$; codes are compared numerically after parsing 4-digit strings.

---

### Conflict resolution & determinism (total order)

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

### Algorithm (exact; streaming-safe)

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

### Formal spec (decision function)

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

### Determinism & contracts

* **No RNG.** Output depends only on $t(m)$ and the parameter bundle.
* **Schema & partitioning (normative):** rows conform to `#/prep/crossborder_eligibility_flags`; dataset is partitioned by `{parameter_hash}`; each row **embeds the same `parameter_hash`**.
  `produced_by_fingerprint` (if present) is **informational only** and **never** compared to any path key or used in partition/equality semantics.
---

### Failure semantics (precise aborts)

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

### Validation & CI hooks

1. **Schema conformance:** every row matches `#/prep/crossborder_eligibility_flags`.
2. **Coverage/uniqueness:** exactly one row per `merchant_id` (PK).
3. **Determinism:** rerunning S0.6 with the same inputs yields **byte-identical** rows (ignoring file order).
4. **Policy lint:** report counts by decision source (`deny`, `allow`, `default_*`) to monitor rule-set shifts when parameters change.
5. **Partition lint:** dataset path and embedded `parameter_hash` match; `produced_by_fingerprint` (if present) is ignored by validators.

---

### Reference pseudocode (language-agnostic)

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

### Complexity, concurrency, and I/O

* **Time:** $O(|\mathcal M|\log |\mathcal R|)$ with simple indices; $O(|\mathcal M||\mathcal R|)$ naive.
* **Space:** streaming; constant memory aside from rule indices.
* **Parallelism:** embarrassingly parallel; determinism holds (pure function of $t(m)$ and versioned rule set).

---

**Bottom line:** S0.6 now writes a **parameter-scoped** authoritative gate with a stable conflict-resolution order, explicit `reason`, versioned `rule_set`, and **no fingerprint coupling**. S3 consumes it verbatim to control the cross-border branch—no RNG, no ambiguity.

---

## S0.7 — Hurdle π Diagnostic Cache (deterministic, optional, normative, fixed)

### Purpose

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

### Inputs (frozen by S0.1–S0.5)

* **Design vector** $x_m=[1,\ \phi_{\text{mcc}},\ \phi_{\text{ch}},\ \phi_{\text{dev}}]$ from **S0.5** (column order frozen by the fitting bundle).
* **Hurdle coefficients** $\beta$ (single YAML vector matching $x_m$’s layout).
* **Lineage keys:** `parameter_hash`  (partition path and embedded column). `produced_by_fingerprint` (hex64) optional/informational.

**No RNG** is consumed.

---

### Output (schema, typing, keys)

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

### Canonical definitions & numerical policy

#### Linear predictor and logistic

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

#### Storage narrowing (deterministic)

Persist `logit` and `pi` as **float32** using **round-to-nearest, ties-to-even** after computing both in binary64. Narrowing is part of the contract and is **for storage only**.

---

### Determinism & scope rules

* **No randomness.** Results depend only on $x_m$ and $\beta$.
* **Diagnostics-only.** No production sampler/allocation routine may read this table.
* **Parameter-scoped.** Changing any governed parameter byte changes `parameter_hash` and thus the partition; no implicit overwrite across partitions.
* `produced_by_fingerprint` (if present) is **informational only** and **does not** participate in partition keys or row equality.

---

### Failure semantics (abort S0; precise codes)

* `E_PI_SHAPE_MISMATCH(exp_dim, got_dim)` — $|\beta|\neq \dim(x_m)$ (double-guard beyond S0.5).
* `E_PI_NAN_OR_INF(m)` — $\eta_m$ or $\pi_m$ non-finite.
* `E_PI_PARTITION(path_key, embedded_key)` — embedded `parameter_hash` mismatches directory key.
* `E_PI_WRITE(path, errno)` — write failure.

> On any failure, **abort S0**; the cache is either wholly correct or absent.

---

### Validation & CI hooks

1. **Schema conformance** — matches `#/model/hurdle_pi_probs`.
2. **Coverage** — exactly $|\mathcal M|$ rows (1 per `merchant_id`).
3. **Recompute check** — rebuild $x_m$ (S0.5) and recompute $\eta_m,\pi_m$ from $\beta$; assert equality to stored **float32** values (bit-for-bit).
4. **Partition lint** — path includes `parameter_hash={parameter_hash}`; row `parameter_hash` equals the path key; no other required lineage fields.
5. **Downstream isolation** — static analysis / policy test: states S1–S9 must not read `hurdle_pi_probs`.

---

### Algorithm (exact; streaming-safe)

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

### Reference pseudocode (language-agnostic)

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

### Downstream connections

* **S1** recomputes $\eta_m,\pi_m$ to draw the Bernoulli hurdle; it **does not** read this cache.
* **S0.10** treats this artefact as optional; presence does not affect `manifest_fingerprint` beyond the bytes of the governing parameters that already define `parameter_hash`.

---

**Summary:** S0.7 is now a **parameter-scoped**, deterministic diagnostics cache with **no** coupling to the run fingerprint, consistent logistic semantics ($\pi\in[0,1]$), explicit float32-for-storage narrowing, and strict validation. It’s safe to generate or skip, and it can never influence stochastic behaviour downstream.

---

## S0.8 — Numeric Policy & Determinism Controls (normative, fixed)

**Cross-reference (normative):** All samplers and transforms in §S0.3 use IEEE-754 **binary64**, round-to-nearest-ties-even, **FMA off**, **no FTZ/DAZ**, and the pinned deterministic libm profile (`numeric_policy.json`, `math_profile_manifest.json`). Any computation that affects a branch/order (acceptance tests, sort keys, integerisation) must execute in a **serial, fixed-order** kernel. Self-tests and attest are in §S0.8 and are part of the validation bundle.

### Purpose

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

### S0.8.1 Floating-point environment (must hold)

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

### S0.8.2 Deterministic libm profile (math functions)

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

### S0.8.3 Reductions, accumulations & linear algebra

* **Sums/dots:** Use **serial, fixed-order** accumulation with **Neumaier** compensation for any total/dot feeding a decision or ordering. Never parallel-reduce such values.
* **Products/ratios:** Multiply in binary64 unless a state mandates log-sum; check denominators against zero with strict guards where required.
* **BLAS/LAPACK:** **Do not** call external BLAS/LAPACK on decision-critical paths. If ever required, pin a deterministic backend and include it in `math_profile_id`.

**Reference kernels (normative):** see §S0.8.10.

---

### S0.8.4 Compiler / interpreter flags (build contract)

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

### S0.8.5 Sorting, comparisons & total order for floats

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

### S0.8.6 Tolerances & quantisation

* **Internal (self-tests):**

  * Sums/dots: `ulpDiff ≤ 1`.
  * Transcendentals: **bit-exact** under the pinned profile.
* **External (reporting/comparing persisted float32):**
  `max(abs_diff, rel_diff) ≤ 1e-6` when comparing **float32** diagnostics to recomputed float64 values **downcast to float32**.
* **Quantisation:** Where a state requires downcasting (e.g., S0.7), use IEEE **round-to-nearest-even**. No other quantisation is allowed unless a state explicitly says so.

---

### S0.8.7 Determinism under concurrency

* **Order-invariance by construction:** RNG streams are keyed (S0.3).
* **Numeric kernels:** Any computation that feeds a sort/branch must run in a **single-threaded** scalar loop with fixed iteration order and Neumaier compensation.
* **Map-style parallelism:** Allowed when results are per-row and never aggregated into decision/order without the serial kernel.
* **I/O:** File emission order is unspecified; equality is defined by row sets. Partitions are unambiguous due to hashes/fingerprints.

---

### S0.8.8 Failure semantics (abort codes)

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

### S0.8.9 Self-tests (must run before S1)

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

### S0.8.10 Reference kernels (pseudocode)

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

### S0.8.11 Validation & CI hooks

* **Bitwise CI:** run self-tests on ≥2 platforms (e.g., glibc vs. musl) → identical results.
* **Rebuild sensitivity:** any change that alters decision-critical outputs must also change `numeric_policy.json` or `math_profile_manifest.json`, thus flipping the fingerprint.
* **Partition lint:** ensure `numeric_policy_attest.json` is present in the validation bundle and its digest is in the manifest enumeration.

---

### S0.8.12 Interaction with other states

* **S0.3 (RNG):** Box–Muller, gamma acceptance tests, PTRS, and Gumbel keys use the pinned math profile and branch-stable formulas.
* **S0.5–S2 (design & GLM):** Dots/logistics use Neumaier + overflow-stable logistic; results are bit-stable.
* **S6 (ranking):** All sorts over float keys use the **total order** + deterministic tie-breakers.

---

**Bottom line:** S0.8 is now a **first-class, fingerprinted numeric contract**: binary64 + RNE, **no FMA**, **no FTZ/DAZ**, deterministic libm, fixed-order Neumaier reductions, total-order sorting, and mandatory self-tests. With `numeric_policy.json`, `math_profile_manifest.json`, and `numeric_policy_attest.json` wired into lineage, downstream states can rely on bit-stable arithmetic everywhere.

---

## S0.9 — Failure Modes & Abort Semantics (normative, fixed)

### Purpose

Define a **single, deterministic** failure contract for 1A so that any violation of schema, lineage, numeric policy, RNG envelope, or partitioning halts the run the **same way every time**, with an actionable forensic payload.

**Scope.** S0.9 governs **all of 1A** (S0–S7). Failures detected anywhere are classified by **S0.9 failure classes (F1–F10)** and surfaced through a **uniform failure record**.

---

### 0) Definitions & severity

* **Run-abort (hard):** Stop the **entire** 1A run immediately; no further states execute.
* **Merchant-abort (soft):** Allowed **only** where a state explicitly specifies it (e.g., S4 corridor policy). Soft aborts are logged to a **merchant-abort log** (see §2.4) and **never** used to bypass S0.9 run-abort conditions.

---

### 1) Failure catalog (F1–F10)

#### F1 — Ingress schema violation (`merchant_ids`)

**Predicate:** fails `schemas.ingress.layer1.yaml#/merchant_ids` (types, required fields, PK, ISO). **Run-abort.**
**`failure_code` examples:** `ingress_schema_violation`, `ingress_pk_duplicate`, `ingress_iso_bad`.

---

#### F2 — Parameter / fingerprint formation failure (S0.2)

Covers `parameter_hash` & `manifest_fingerprint`. **Run-abort.**

* **F2a Parameters:** missing/duplicate/unreadable governed file; hash race.
  `failure_code`: `param_file_missing|duplicate|unreadable|changed_during_hash`.
* **F2b Fingerprint:** empty artefact set; artefact unreadable; bad commit bytes.
  `failure_code`: `fingerprint_empty_artifacts|artifact_unreadable|git_bytes_invalid|bad_hex_encoding`.

---

#### F3 — Non-finite or out-of-domain features / model outputs

**Run-abort.**

* **F3a S0.4:** `nonpositive_gdp`, `bucket_out_of_range`.
* **F3b S0.5/S0.7:** `hurdle_nonfinite` (non-finite `η`/`π`).

---

#### F4 — RNG bootstrap / envelope / draw-accounting failures

**Run-abort.**

* **F4a:** `rng_audit_missing_before_first_draw`.
* **F4b:** `rng_envelope_violation` (missing required fields).
* **F4c:** `rng_counter_mismatch` (`after−before != blocks`).
* **F4d:** `rng_budget_violation` (per S0.3 budgets).

---

#### F5 — Partitioning / lineage mismatch (dictionary-backed)

Wrong partition **or** row lineage doesn’t match path. **Run-abort.**
`failure_code`: `partition_mismatch`, `log_partition_violation`.

---

#### F6 — Schema-authority breach

1A authority is **JSON-Schema** only. Any non-authoritative ref (e.g., Avro) → **Run-abort.**
`failure_code`: `non_authoritative_schema_ref`.

---

#### F7 — Numeric policy violation (S0.8)

Binary64+RNE, no FMA, no FTZ/DAZ, deterministic libm, serial reductions. **Run-abort.**
`failure_code`: `numeric_rounding_mode|fma_detected|ftz_or_daz_enabled|libm_profile_mismatch|parallel_reduce_on_ordering_path`.

---

#### F8 — Event coverage / corridor guarantees (state-specific)

Required event families missing/inconsistent; corridor breached. **Run-abort** for structural gaps; state may additionally log **merchant-abort** when allowed.
`failure_code`: `event_family_missing`, `corridor_breach`.

---

#### F9 — Dictionary / path drift

Dataset path or lineage semantics deviates from dictionary. **Run-abort.**
`failure_code`: `dictionary_path_violation`.

---

#### F10 — I/O integrity & atomics

Short writes, partial instances, non-atomic commit. **Run-abort.**
`failure_code`: `io_write_failure`, `incomplete_dataset_instance`.

---

### 1.1 Crosswalk: state-level `E_*` → S0.9 classes

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

### 2) Abort artefacts, paths, and atomics

#### 2.1 Where the failure record lives (validation bundle)

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

#### 2.2 Failure record (normative JSON schema)

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

#### 2.3 Abort procedure (deterministic)

1. **Stop** emitting new events/datasets immediately.
2. **Flush & seal** validation bundle (path above) with `failure.json` (+ `_FAILED.SENTINEL.json`).
3. **Mark incomplete outputs**: delete temp dirs; if any partial partition escaped temp, write a sibling `_FAILED.json` sentinel **inside that partition** with `{dataset_id, partition_keys, reason}`.
4. **Freeze RNG**: no further RNG events; last counters remain as in the failing envelope.
5. **Exit non-zero**; orchestrator halts downstream.

#### 2.4 Merchant-abort log (when a state allows soft aborts)

When a state defines **merchant-abort**, write (parameter-scoped):

```
.../prep/merchant_abort_log/parameter_hash={parameter_hash}/part-*.parquet
  { merchant_id, state, module, reason, ts_utc }
```

This log **never** replaces a run-abort; it records permitted soft fallbacks only.

---

### 3) Validator responsibilities (hardened)

* **Ingress schema** (F1).
* **Lineage recomputation** of `parameter_hash` & `manifest_fingerprint` (F2).
* **RNG envelope & counter conservation** for **every** event; budgets per family (F4).
* **Partition equivalence** (F5): parameter-scoped `{parameter_hash}`, logs `{seed,parameter_hash,run_id}`, egress/validation `{fingerprint}` (and often `seed`).
* **Numeric attestation** (F7): run S0.8 self-tests; verify `numeric_policy_attest.json` and reject mismatches.
* **Coverage/corridors** per state (F8).
* **Dictionary paths** (F9).
* **Instance completeness & atomics** (F10).

---

### 4) Where each failure is first detected

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

### 5) Examples (concrete)

* **Missing audit row (F4a):** first RNG event is `hurdle_bernoulli` but `rng_audit_log` has no `run_id=…` → `rng_audit_missing_before_first_draw` → **Run-abort**.
* **Partition mismatch (F5):** write `outlet_catalogue` under `…/fingerprint=X` but embed row fingerprint `Y` → `partition_mismatch` → **Run-abort**.
* **Non-finite hurdle (F3b):** `η_m` becomes NaN due to malformed coefficients → `hurdle_nonfinite` → **Run-abort**.

---

### 6) Reference abort routine (language-agnostic)

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

### 7) Determinism & idempotency guarantees

* Given identical inputs & environment, a failing run produces the **same** `failure_class`, `failure_code`, and **bit-identical** `failure.json`.
* Re-running without changing `manifest_fingerprint`/`parameter_hash` yields the **same** abort artefacts.
* Only the **first** detected failure is recorded; subsequent symptoms are suppressed to keep forensics clean.

---

**Bottom line:** S0.9 is now a precise, fingerprinted **fail-fast** contract: one vocabulary (F1–F10 + `failure_code`), one failure record schema, atomic/validated placement under `{fingerprint, seed, run_id}`, a clear E↔F crosswalk for state errors, and a deterministic abort routine. With this in place, **any** deviation from schema, lineage, RNG, numeric policy, or partitioning terminates the run loudly—with everything you need to reproduce and fix it.

---

## S0.10 — Outputs, Partitions & Validation Bundle (normative, fixed)

### S0.10.1 Lineage keys (recap; scope of use)
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

### S0.10.2 Artefact classes produced by S0

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

### S0.10.3 Partitioning & paths (authoritative)

**Naming rule (normative):** Any path segment named `fingerprint={…}` **always** carries the value of `manifest_fingerprint`. The column name is `manifest_fingerprint`; the path label remains `fingerprint=…`.

**RNG logs (normative paths & keys):**
`rng_audit_log` → `logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl`
`rng_trace_log` → `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`
`rng_event_*` → `logs/rng/events/{family}/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
Partitioning for all three: `["seed","parameter_hash","run_id"]`. The dataset dictionary remains authoritative for any additional fields.

#### Parameter-scoped (partition by `parameter_hash`)

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

#### Fingerprint-scoped (partition by `fingerprint`)

**Directory:** `validation_bundle_1A`
**Path:** `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`
**Contents:** §S0.10.5.

#### Log-scoped (RNG)

**Logs:** `rng_audit_log`, `rng_trace_log`, each `rng_event_*`
**Path template:** `logs/rng/<stream>/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
> **Authority (normative):** Actual **paths and partition columns** are authoritative in the **dataset dictionary**. Strings shown here are examples to illustrate shape.

> **Physical line order (normative):** For RNG **JSONL** logs, line order is append order **within a file**; there are **no ordering guarantees across files/parts**. Equality is by **row set**; any consumer that depends on physical order is non-conformant.

**Envelope (per S0.3):** `{seed, parameter_hash, manifest_fingerprint, run_id, module, substream_label, counter_before/after, blocks, draws, ts_utc, payload…}`.
`rng_trace_log` aggregates **blocks**.
---

### S0.10.4 Immutability, idempotence & retention

* **Immutability:** A concrete partition directory is **immutable**. Re-runs with the same keys either no-op or atomically replace with **byte-identical** content.
* **Idempotence:** With identical inputs and numeric policy, outputs are **bit-identical** (file order within a Parquet partition is out-of-contract).
* **Retention:**

  * Parameter-scoped: keep last **N=5** `parameter_hash` generations (policy).
  * Validation bundles: keep **all** `manifest_fingerprint` generations.
  * RNG logs: retain per compliance (e.g., 90 days).

---

### S0.10.5 Validation bundle (structure, hashing, gate)

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

### S0.10.6 Writer behavior (atomicity & lints)

* **Atomic publish:** write bundle into `…/validation/_tmp.{uuid}`; compute `_passed.flag`; single atomic `rename(2)` to `fingerprint=…/`. On failure, delete tmp.
* **Optional lints:**

  * `DICTIONARY_LINT.txt`: diff of dictionary vs observed writer paths/schema refs.
  * `SCHEMA_LINT.txt`: results of schema validation of produced datasets.
    By default these **are included** in the gate hash; you may exclude them only if documented (then also omit them from the hash computation consistently).

---

### S0.10.7 Idempotent re-runs & equivalence

Two bundles are **equivalent** if:

* `MANIFEST.json` matches byte-for-byte.
* all other files match byte-for-byte and `_passed.flag` hashes match.

---

### S0.10.8 Pseudocode (reference)

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

### S0.10.9 Validation (CI/runtime must assert)

* **Partition lint:** parameter-scoped datasets live under `parameter_hash=…`; rows embed the same `parameter_hash`; RNG logs use `{seed,parameter_hash,run_id}`; validation bundle under `fingerprint=…`.
* **Bundle integrity:** presence of all required files and `_passed.flag` hash match.
* **Schema conformance:** produced datasets validate against their JSON-Schema anchors.
* **Lineage recomputation:** `parameter_hash` and `manifest_fingerprint` recomputed equal the `*_resolved.json` values.
* **Numeric attestation:** `numeric_policy_attest.json` indicates **all** S0.8 self-tests passed.

---

### S0.10.10 Downstream consumption rules

* **Parameter-scoped readers** (S1/S2/S3): key by **`parameter_hash`** only; ignore `run_id`.
* **Egress/validation consumers:**

  1. locate `fingerprint={manifest_fingerprint}`,
  2. verify `_passed.flag`,
  3. (optional) re-hash `fingerprint_artifacts.jsonl` & `param_digest_log.jsonl`.
     Any failure ⇒ treat run as invalid and halt per S0.9.

---

**Bottom line:** S0.10 locks S0’s outputs into clear, non-overlapping partitions: parameter-scoped datasets embed **only `parameter_hash`** (with optional `produced_by_fingerprint`), RNG logs are `{seed,parameter_hash,run_id}`, and the **validation bundle** is fingerprint-scoped and **gate-protected**. Everything is atomic, idempotent, and CI-provable.

---


[S0-END VERBATIM]

---

# S1 — Expanded
<a id="S1.EXP"></a>
<!-- SOURCE: /s3/states/state.1A.s1.expanded.txt  *  VERSION: v0.0.0 -->

[S1-BEGIN VERBATIM]

## S1.1 — Inputs, Preconditions, and Write Targets (normative)

### Purpose (what S1 does and does **not** do)

S1 evaluates a **logistic hurdle** per merchant and emits a **Bernoulli outcome** (“single vs multi”). Here we pin **inputs**, **context/lineage**, and **write targets** required to do that deterministically. The logistic, RNG use, and payload specifics are defined in **S1.2–S1.4**.
S1 does **not** specify downstream sampling (NB, ZTP, Dirichlet, etc.) nor CI/monitoring; those live in their respective state specs and the validation harness.

---

### Inputs (available at S1 entry)

#### 1) Design vector $x_m$ (column-frozen from S0.5)

**Feature vector (logistic):**

* **Block order (fixed):** $[\,\text{intercept}\,] \;\Vert\; \text{onehot(MCC)} \;\Vert\; \text{onehot(channel)} \;\Vert\; \text{onehot(GDP_bucket)}$.
* **Channel encoder (dim=2):** labels/order exactly $[\,\mathrm{CP},\,\mathrm{CNP}\,]$ (from S0).
* **GDP bucket encoder (dim=5):** labels/order exactly $[\,1,2,3,4,5\,]$ (S0 Jenks-5).
* **MCC encoder (dim $=C_{\text{mcc}}$):** **column order is frozen by S0.5** (the fitting bundle). S1 never derives order from map iteration.
* **Shape invariant:** $|x_m| = 1 + C_{\text{mcc}} + 2 + 5$.

S1 **receives** $x_m$ (already constructed by S0.5) as

$$
x_m = \big[\,1,\ \phi_{\text{mcc}}(\texttt{mcc}_m),\ \phi_{\text{ch}}(\texttt{channel}_m),\ \phi_{\text{dev}}(b_m)\,\big]^\top,
$$

with $b_m\in\{1,\dots,5\}$. These are the **only** hurdle features. (NB dispersion’s $\log g_c$ is **not** used here.)

> S0 guarantees domain validity and “one-hot sums to 1” for all encoder blocks. S1 relies on that; it does **not** re-validate domains.

#### 2) Coefficient vector $\beta$ (single YAML, atomic load)

Load $\beta$ **atomically** from the hurdle coefficients bundle. The vector contains **all coefficients** aligned to $x_m$: intercept, MCC block, channel block, and the **five** GDP-bucket dummies. Enforce

$$
|\beta| \;=\; 1 + C_{\text{mcc}} + 2 + 5 \quad\text{else abort (design/coeff mismatch).}
$$

*(Design rule context from S0.5: hurdle uses bucket dummies; NB mean excludes them; NB dispersion uses $\log g_c$.)*

#### 3) Lineage & RNG context (fixed before any draw)

S0 has already established the **run identifiers** and RNG environment S1 uses:

* `parameter_hash` (hex64) — partitions parameter-scoped artefacts.
* `manifest_fingerprint` (hex64) — lineage key; **not** a path partition here.
* `seed` (uint64) — master Philox seed.
* `run_id` (hex32) — logs-only partition key.
* An `rng_audit_log` exists for this `{seed, parameter_hash, run_id}`. S1 must **not** emit the first hurdle event if that audit row is absent.

**PRNG use model (order-invariant).** All RNG use in 1A is via **label-keyed substreams**. The **base counter** for a given label/merchant pair is derived by S0’s keyed-substream mapping from the tuple

$$
(\texttt{seed},\ \texttt{manifest_fingerprint},\ \texttt{substream_label},\ \texttt{merchant_id}),
$$

independent of execution order or other labels. There is **no** cross-label counter chaining in S1.

---

### Envelope contract (shared fields carried by every hurdle event)

Each hurdle record **must** include the layer envelope fields (names and types per the layer schema):

* `ts_utc` — RFC-3339 UTC with `Z` and **exactly 6 fractional digits** (microseconds).
* `run_id`, `seed`, `parameter_hash`, `manifest_fingerprint`.
* `module` — **literal** `"1A.hurdle_sampler"`.
* `substream_label` — **literal** `"hurdle_bernoulli"`.
* Counter words (uint64):
  `rng_counter_before_lo`, `rng_counter_before_hi`, `rng_counter_after_lo`, `rng_counter_after_hi`.
(Object key order is **non-semantic**; names are authoritative. **Producers MAY emit in any order; consumers bind by name.** Compose u128 as `(hi<<64) | lo`.)
* **`draws`** — **required** decimal u128 **string**: the number of uniforms consumed by **this** event.

**Budget identity (unsigned 128-bit):**

$$
\Delta \;\equiv\; \mathrm{u128}(\text{after_hi},\text{after_lo}) - \mathrm{u128}(\text{before_hi},\text{before_lo})
\;=\; \texttt{parse_u128(draws)}.
$$

This identity is **scoped to the hurdle family only**. For hurdle, `draws ∈ {"0","1"}`; `blocks ∈ {0,1}` and **must equal** `parse_u128(draws)`. Other RNG families may have `draws ≠ blocks` while still satisfying S0’s counter rules.


For hurdle, $\texttt{draws} \in \{"0","1"\}$.
* Additionally, emit `blocks:uint64` as **required** by S0; for hurdle, `blocks ∈ {0,1}` and **must equal** `parse_u128(draws)`.*

---

### Preconditions (hard invariants at S1 entry)

1. **Shape & alignment:** $|\beta|=\dim(x_m)$ and encoder block orders match S0.5’s fitting bundle; else abort (design/coeff mismatch).
2. **Numeric environment:** S0’s math policy is in force: IEEE-754 **binary64**, RNE, **no FMA**, **no FTZ/DAZ**; fixed-order reductions. S1 uses the overflow-safe **two-branch logistic** (no ad-hoc clamp threshold) in S1.2.
3. **RNG audit present:** audit row for `{seed, parameter_hash, run_id}` exists **before** the first hurdle emission; else abort.

---

### Event stream target (authoritative id, partitions, schema)

S1 emits **exactly one** hurdle record per merchant to:

```
logs/rng/events/hurdle_bernoulli/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

* **Partitions:** `["seed","parameter_hash","run_id"]` (no `module`/`substream_label`/`manifest_fingerprint` in the path).
* **Schema:** `schemas.layer1.yaml#/rng/events/hurdle_bernoulli` (envelope + payload).

**Uniqueness & completeness (per run).** Within `{seed, parameter_hash, run_id}`, there is **exactly one** hurdle event per `merchant_id`, and the hurdle row count equals the merchant universe count for the run (from S0 ingress for the same `manifest_fingerprint`).

**Trace (totals; no merchant dimension).** The RNG **trace** is per `(module, substream_label)` and records cumulative totals keyed by `{seed, parameter_hash, run_id}`. `blocks_total` is the **normative** counter of cumulative consumption; `draws_total` is **required** and **diagnostic** (it must equal the saturating sum of per-event `draws`).

---

### Forward contracts S1 must satisfy (declared here so inputs are complete)

* **Probability (S1.2).** Compute $\eta_m=\beta^\top x_m$ (fixed-order dot in binary64) and $\pi_m$ via the **two-branch** logistic. $\pi_m \in [0,1]$; the row is **deterministic** iff $\pi_m$ equals exactly `0.0` or `1.0` in binary64 (extreme underflow/overflow of `exp`), otherwise $0<\pi_m<1$.
* **RNG substream & $u\in(0,1)$ (S1.3).** Use the keyed substream mapping from **S0**. If $0<\pi_m<1$, consume exactly one open-interval uniform via S0’s `u01` mapping (binary64): $u=((x+1)\times 2^{-64})$, then **if** $u==1.0$ set $u=\mathrm{nextafter}(1.0,\text{below})$; if $\pi_m\in\{0,1\}$, draw **zero**. Envelope counters must satisfy the budget identity.
* **Payload discipline (S1.4).** Payload is `{merchant_id, pi, is_multi, deterministic, u}` where `u` is **required** and **nullable**:

  * if $0<\pi<1$: `u ∈ (0,1)`, `deterministic=false`, `is_multi = 1{u<pi}`;
  * if $\pi\in\{0,1\}$: `u=null`, `deterministic=true`, `is_multi = (pi == 1.0)`.

---

### Failure semantics (at the S1.1 boundary)

Abort the run if any precondition fails: shape/alignment mismatch; missing audit; envelope/schema or path/partition mismatch. Detailed failure codes and validator behaviour are specified in S1.6 and S1.V.

---

### Why this matters (determinism & replay)

By fixing $x_m$, $\beta$, the run identifiers, the **order-invariant substream mapping**, and the envelope/budget law **before** any draw, S1’s Bernoulli outcomes and counters are **bit-replayable** under any sharding or scheduling. This gives the validator a single, unambiguous contract to reproduce S1 decisions.

---

**Bottom line:** S1 starts only when $x_m$, $\beta$, and the lineage/RNG context are immutable and schema-backed; it writes to the single authoritative hurdle stream with fixed envelope and partitions. With these inputs and preconditions, S1.2–S1.4 compute $\eta,\pi$, consume at most one uniform (as required), and emit an event that validators can reproduce exactly.

---

## S1.2 — Probability map (η → π), deterministic & overflow-safe (normative)

### Purpose

Given the frozen design vector $x_m$ and the single-YAML coefficient vector $\beta$ (from S1.1), compute

$$
\eta_m=\beta^\top x_m,\qquad
\pi_m=\sigma(\eta_m)\in[0,1],
$$

then pass $(\eta_m,\pi_m)$ forward to S1.3 (RNG) and S1.4 (event). All numeric environment rules come from **S0.8** (binary64, RN-even, no FMA/FTZ/DAZ, deterministic libm; fixed-order reductions).

---

### Inputs (recap; validated in S1.1)

* **Design vector** $x_m\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}$, column order frozen by the fitting bundle (S0.5).
* **Coefficients** $\beta\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}$ loaded atomically; shape/order equals $x_m$.

(Shape/order failures are handled at S1.1 / S0.9.)

---

### Canonical definitions (math)

#### Linear predictor (fixed-order Neumaier reduction)

$$
\eta_m=\beta^\top x_m
$$

Compute in IEEE-754 **binary64** using the **frozen column order** and the **Neumaier compensated summation** mandated by S0.8. No BLAS reordering or parallel reduction is permitted on any ordering-critical path.

#### Logistic map and **overflow-safe evaluation** (normative)

Baseline logistic:

$$
\sigma:\mathbb{R}\to(0,1),\qquad
\sigma(\eta)=\frac{1}{1+e^{-\eta}}.
$$

**Evaluation contract (binary64, deterministic):** Use the **two-branch, overflow-safe form**; do **not** introduce any ad-hoc clamp/threshold:

$$
\pi\;=\;
\begin{cases}
\dfrac{1}{1+e^{-\eta}}, & \eta \ge 0,\\[8pt]
\dfrac{e^{\eta}}{1+e^{\eta}}, & \eta < 0.
\end{cases}
$$

Under the S0.8 math profile, this keeps $\pi\in[0,1]$ in binary64 and avoids spurious overflow/underflow in intermediate terms. For **extreme** $|\eta|$, binary64 underflow/overflow of the exponentials may yield $\pi$ exactly `0.0` or `1.0`—this is the **only** source of exact saturation.

**Determinism flag (derived):**
`deterministic := (pi == 0.0 || pi == 1.0)` using **binary64 equality**. If `deterministic=true` then S1.3 will consume **zero** uniforms; else S1.3 consumes **exactly one** (see S1.3).

---

### Serialization & bounds (normative I/O rules)

* **Binary64 round-trip:** Producers **MUST** serialize `pi` as the **shortest round-trippable decimal** (≤17 significant digits; scientific notation allowed) so that parsing yields the **exact** original binary64. Consumers **MUST** parse as binary64.
* **Legal range:** Enforce `0.0 ≤ pi ≤ 1.0` (binary64). If $\pi$ is exactly `0.0` or `1.0`, it came from the two-branch evaluation under binary64; otherwise `0.0 < pi < 1.0`.
* **Diagnostics:** `eta` is **not** part of the normative hurdle event payload; if recorded, it belongs to a **diagnostic** dataset only (non-authoritative).

---

### Deterministic vs stochastic and consequences for S1.3

* **Stochastic case** $(0<\pi<1)$: S1.3 will draw **one** $u\in(0,1)$ from the keyed substream, then decide `is_multi = (u < pi)`; budget `draws=1`. (Open-interval mapping and substreaming per S0.3.)
* **Deterministic case** $(\pi\in\{0.0,1.0\})$: S1.3 performs **no draw**; budget `draws=0`; downstream decision is implied by $\pi$ (`is_multi=true` iff `pi==1.0`).

---

### Numeric policy (must hold; inherited)

S0.8 applies in full: **binary64**, RN-even, **no FMA**, **no FTZ/DAZ**, deterministic libm; fixed-order Neumaier reductions; any NaN/Inf in $\eta$ or $\pi$ is a **hard error** under S0.9.

---

**Bottom line:** S1.2 fixes a single, portable way to compute $(\eta,\pi)$: a **fixed-order Neumaier** dot product followed by a **two-branch logistic** with **no ad-hoc clamp**. Exact `0.0/1.0` arises only from binary64 behavior, and $\pi$ then cleanly determines whether S1.3 consumes **one** uniform or **zero**. **MUST-NOT:** Implementations may **not** clamp $\eta$ or $\pi$ at any threshold (e.g., $|\eta|>40$) during S1 computation or emission; event payload `pi` is the exact logistic result.

---

### Output of S1.2 (to S1.3/S1.4)

For each merchant $m$, S1.2 produces the numeric pair

$$
(\eta_m,\ \pi_m),\qquad \eta_m\in\mathbb{R}\ \text{(finite)},\ \ \pi_m\in[0,1]\ \text{(binary64)}.
$$

These values are **not persisted by S1.2**. They flow directly into:

* **S1.3 (RNG & decision):** determines whether **one** uniform is consumed $(0<\pi<1)$ or **zero** $(\pi\in\{0,1\})$, and—if stochastic—evaluates `is_multi = (u < pi)`.
* **S1.4 (event payload):** `pi` is a required payload field. `eta` is **not** a normative payload field; if recorded, it belongs to a diagnostic dataset (non-authoritative). S1.4 derives `deterministic` from `pi` and applies the `u` presence rule: `u=null` iff `pi∈{0.0,1.0}`, else `u∈(0,1)`.

---

### Failure semantics (abort S1 / run)

S1.2 must **abort the run** if any of the following hold:

1. **Numeric invalid:** either $\eta$ or $\pi$ is non-finite (NaN/±Inf) after evaluation.
2. **Out-of-range:** $\pi \notin [0,1]$ (should not occur with the two-branch logistic).
3. **Shape/order mismatch:** already handled at S1.1; if encountered here, treat as a hard precondition failure.

(Full failure taxonomy, codes, and CI handling live outside S1; this section defines only the operational abort triggers.)

---

### Validator hooks (what the S1 checklist asserts for S1.2)

The single S1 Validator Checklist (referenced once from S1) must be able to **reproduce** S1.2 exactly:

* **Recompute:** Rebuild $x_m$ (from S0’s frozen encoders) and re-evaluate $\eta,\pi$ using the fixed-order binary64 dot product and the **two-branch logistic**. Assert:

  * $\eta$ is finite;
  * $\pi \in [0.0,1.0]$;
  * the recomputed $\pi$ matches the emitted `pi` **bit-for-bit** (binary64).
* **Determinism equivalences:**
  $\pi\in\{0.0,1.0\} \iff \text{deterministic}=\text{true} \iff \text{draws}=0 \iff u=\text{null}$.
  Otherwise $0<\pi<1 \iff \text{deterministic}=\text{false} \iff \text{draws}=1 \iff u\in(0,1)$.
* **Budget prediction link (with S1.3):** From $\pi$, predict `draws` as above and reconcile with the event envelope and the cumulative trace totals for the hurdle substream.

---

### Reference algorithm (language-agnostic, ordering-stable)

1. **Dot product:** Compute $\eta=\beta^\top x$ in binary64 using the **frozen column order** and **Neumaier** compensation (no reordering/BLAS on ordering-critical paths).
2. **Logistic (two-branch):**

   * if $\eta \ge 0$ ⇒ $\pi = 1/(1+\exp(-\eta))$;
   * else ⇒ $\pi = \exp(\eta)/(1+\exp(\eta))$.
3. **Guards:** $\eta$ and $\pi$ must be finite; $\pi$ must satisfy $0.0 \le \pi \le 1.0$.
4. **Hand-off:** Emit $(\eta,\pi)$ to S1.3/S1.4. The RNG budget and `u` presence follow directly from $\pi$ as stated above.

*(This is a procedural specification, not implementation code; S0 remains the authority for the FP environment and PRNG primitives.)*

---

### How S1.2 interacts with adjacent sections

* **Feeds S1.3:** $\pi$ sets the **uniform budget**: exactly **one** uniform if $0<\pi<1$, else **zero**. If stochastic, S1.3 evaluates `is_multi = (u < pi)` using the open-interval mapping from S0.
* **Feeds S1.4:** `pi` is serialized with **binary64 round-trip** fidelity. `deterministic` is derived from `pi`; `u` is **required** and **nullable** (`null` iff $\pi\in\{0,1\}$, otherwise a number in $(0,1)$). `is_multi` is **boolean** only.

---

**Bottom line:** S1.2 defines a single, portable procedure for $(\eta,\pi)$: **fixed-order** binary64 dot product and a **two-branch logistic** with **no ad-hoc clamp**. That yields $\pi\in[0,1]$ deterministically, and $\pi$ cleanly drives the exact RNG budget and payload semantics required by S1.3–S1.4.

---

## S1.3 — RNG substream & Bernoulli trial (normative)

### Purpose

Given $\pi_m$ from S1.2, consume **at most one** uniform $u_m\in(0,1)$ from the merchant-keyed substream labeled `"hurdle_bernoulli"`, decide

$$
\text{is_multi}(m)\;=\;[\,u_m < \pi_m\,],
$$

and emit exactly one hurdle event (payload in S1.4). The keyed-substream mapping, lane policy, and open-interval $U(0,1)$ are owned by **S0.3** and are referenced here without redefinition.

---

### Inputs (available at S1.3 entry)

* $\pi_m\in [0,1]$ from S1.2.
* Run lineage identifiers: `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`, and `module` (registry literal for this producer).
* `merchant_id` (type `$defs/id64`, carried as a JSON **integer** in events; treated as u64 by the S0 keying primitive).
* Dataset/registry anchors for hurdle events and RNG trace are established elsewhere (S1.1 / dictionary); S1.3 does **not** restate paths.

---

### Canonical substream (order-invariant; per merchant)

#### Label

$$
\ell := \text{"hurdle_bernoulli"} \quad\text{(registry literal; appears verbatim in the event envelope).}
$$

#### Base counter & independence (via S0 primitive)

The **base counter** for each $(\ell, m)$ and the **keyed substream** are obtained **only** through S0’s mapping (pure in $(\texttt{seed}, \texttt{manifest_fingerprint}, \ell, m)$) and therefore **order-invariant** across partitions/shards. S1.3 **does not** chain counters across labels or merchants.

---

### Envelope budgeting (counter law)

For hurdle events, the envelope must satisfy the S0 budgeting identity:

$$
\mathrm{u128}(\texttt{after_hi},\texttt{after_lo}) - \mathrm{u128}(\texttt{before_hi},\texttt{before_lo})
\;=\; \texttt{parse_u128(draws)},
$$

with unsigned 128-bit arithmetic on counters. In the hurdle stream, `draws ∈ {"0","1"}` (the number of uniforms consumed).
**`blocks` is required**; for hurdle (uint64) it **must** be `0` or `1` and **must equal** `parse_u128(draws)`.

> **Trace model (reconciliation):** The RNG trace is **cumulative** per `(module, substream_label)` within the run (no merchant dimension) and includes `rng_counter_before_{lo,hi}` and `rng_counter_after_{lo,hi}`. 
> For the **final** row per key in a run (selection rule per `schemas.layer1.yaml#/rng/core/rng_trace_log`):
>
> * `draws_total == Σ parse_u128(draws)` (**required**; diagnostic; saturating uint64),
> * `blocks_total == Σ blocks` (normative; saturating uint64),
> * `events_total ==` hurdle event count.
>
> (Note: `u128(after) − u128(before)` on the final row is the **delta for that last emission only**; do **not** equate it to cumulative totals.)
> Trace **rows are emitted per event**; consumers select the **final** row per key (selection per `schemas.layer1.yaml#/rng/core/rng_trace_log`).

**Field-order convention (names are authoritative):** JSON carries
`rng_counter_before_lo`, `rng_counter_before_hi`, `rng_counter_after_lo`, `rng_counter_after_hi`. Parsers compose u128 as `(hi<<64) | lo`.

---

### Uniform $u\in(0,1)$ & lane policy

* **Engine:** Philox 2×64-10 (fixed in S0). Each block yields two 64-bit words; **single-uniform** events use the **low lane** (`x0`) and **discard** the high lane (`x1`). One counter increment ⇒ one uniform.
* **Mapping to $U(0,1)$:** Use S0’s **open-interval** `u01` mapping from a 64-bit unsigned word to binary64 — **identical to S0’s `u01`**. Exact 0 and exact 1 are **never** produced. (S1.3 **references** this mapping; it **does not** redefine it.)

---

### Draw budget & decision

Let $\pi=\pi_m$.

* **Deterministic branch** ($\pi\in\{0.0,1.0\}$).
  `draws="0"`; **no** Philox call; set `blocks=0`; envelope has `after == before`.
  Outcome is implied by $\pi$: `is_multi = true` iff `pi == 1.0`; else `false`.
  Payload rules (S1.4): `deterministic=true`, `u=null`.

* **Stochastic branch** ($0<\pi<1$).
  Draw **one** uniform $u\in(0,1)$ using the keyed substream and lane policy; `draws="1"`; set `blocks=1`; envelope has `after = before + 1`.
  Decide `is_multi = (u < pi)`; payload: `deterministic=false` and `u` present and numeric.

All of the above are enforced by the S0/S1 budgeting invariants and the S1 validator checklist (determinism equivalences and gating).

---

**Bottom line:** S1.3 consumes **zero or one** uniform from the merchant-keyed `"hurdle_bernoulli"` substream, applies the **open-interval** mapping, decides with `u < pi`, and records a budget-correct envelope. No cross-label chaining; **trace rows are emitted per event** and consumers select the **final** row per key—everything is S0-aligned and replayable.

---

### Envelope & streams touched here (recap; S1.4 formalises payload)

Each hurdle event **must** carry the **complete** layer RNG envelope:

`{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, draws, blocks }`

* `module` and `substream_label` are **registry-closed literals** (schema-typed as strings; closure enforced by validators/registry).
* `draws` is a non-negative **u128 encoded as decimal string**; budget identity: `u128(after) − u128(before) = parse_u128(draws)`.
* `blocks` is a non-negative uint64; for hurdle, `blocks ∈ {0,1}` and **must equal** `parse_u128(draws)` **(hurdle-only; other RNG families may have `draws ≠ blocks` while still satisfying S0’s counter rules)**.

**Single flat JSON object.** Each hurdle record is **one** top-level JSON object; “envelope” and “payload” are **conceptual groupings only** (no nested objects). This wording eliminates any ambiguity about structure.

S1.3 writes **one** hurdle event per merchant.  The RNG trace is **cumulative** per `(module, substream_label)` within the run (no merchant dimension). Its totals reconcile to the **sum of event budgets**. **Trace rows are emitted per event; validators select the final row per** `schemas.layer1.yaml#/rng/core/rng_trace_log`.

---

### Failure semantics (abort class bindings)

Abort the run on any of the following:

* **Envelope/label violation.** Missing required envelope fields; wrong `module`/`substream_label` literal; malformed counter fields (`*_hi/*_lo`).
* **Budget identity failure.** `u128(after) − u128(before) ≠ parse_u128(draws)`; or `blocks∉{0,1}` for hurdle.
* **Uniform out of range.** In a stochastic branch, `u ≤ 0` or `u ≥ 1` (violates open-interval `u01`).
* **Determinism inconsistency.** `π∈{0,1}` but `u` present or `deterministic=false`; or $0<\pi<1$ but `u` absent or `deterministic=true`.

(Shape/order and non-finite numeric faults are owned by S1.1–S1.2 preconditions.)

---

### Validator hooks (must pass)

For each hurdle record in the run, the validator performs:

1. **Rebuild base counter (order-invariant).** Using the S0 keyed-substream primitive with `(seed, manifest_fingerprint, substream_label="hurdle_bernoulli", merchant_id)`, recompute the **base counter** and assert envelope `before` equals it. (No cross-label chaining is permitted.)

2. **Branch-specific checks from $\pi$ (from S1.2):**

   * If `draws="0"`: assert $\pi\in{0.0,1.0}$, `u==null`, `deterministic=true`, and `after==before`.
   * If `draws="1"`: generate **one** 64-bit word from the keyed substream at `before` using S0’s lane policy (low lane), map via S0’s **open-interval** `u01`, assert `0<u<1`, assert `(u<pi) == is_multi`, and assert `after = before + 1`.

3. **Trace reconciliation (cumulative).** Let `H` be all hurdle events in the run. For the **final** trace row for `(module, substream_label)`:
   * Assert `trace.draws_total == Σ parse_u128(e.draws)` (**required**; diagnostic; saturating uint64),
   * Assert `trace.blocks_total == Σ e.blocks` (normative; saturating uint64),
   * Assert `trace.events_total ==` hurdle event count (saturating uint64).
   * (No assertion that `u128(trace.after) − u128(trace.before)` on the final row equals any cumulative total; that delta is **per-row**.)

4. **Partition/embedding equality.** Path partitions `{seed, parameter_hash, run_id}` match the embedded envelope fields; `module` / `substream_label` match the registry literals exactly.

---

### Procedure (ordering-invariant, language-agnostic)

1. **Obtain base counter** for `(label="hurdle_bernoulli", merchant_id)` via the S0 keyed-substream primitive; set `before` accordingly.
2. **Branch on $\pi$:**

   * If $\pi\in\{0.0,1.0\}$: set `draws="0"`, `blocks=0`, `after=before`, `u=null`, `is_multi=(pi==1.0)`. 
   * If $0<\pi<1$: fetch **one** uniform $u\in(0,1)$ using the S0 lane policy and `u01`; set `draws="1"`, `blocks=1`, `after=before+1`, `is_multi=(u<pi)`. 
3. **Emit hurdle event** (S1.4): envelope includes all required fields above; payload includes `merchant_id`, `pi`, `u` (nullable), `is_multi` (boolean), `deterministic` (derived from `pi`).
4. **Emit one trace row for this event** with updated cumulative totals for `(module, substream_label)`: add `parse_u128(draws)` to `draws_total` (diagnostic; saturating uint64), add `blocks` to `blocks_total` (normative; saturating uint64), and `+1` to `events_total`. Validators **select the final row** using the rule in `#/rng/core/rng_trace_log`.

*(This is a procedural spec; S0 remains the authority for PRNG keying, counter arithmetic, lane policy, and `u01` mapping.)*

---

### Invariants (S1/H) guaranteed here

* **Bit-replay:** Fixing $(x_m,\beta,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, both the envelope counters and the pair $(u,\text{is_multi})$ are **bit-identical** under replay.
* **Consumption:** `draws="1"` **iff** $0<\pi<1$; else `"0"`.
* **Schema conformance:** `u` and `deterministic` comply with the hurdle event schema: `u=null` iff $\pi\in\{0.0,1.0\}$; `is_multi` is **boolean** only.
* **Order-invariance:** `before` equals the keyed **base counter** for `(label, merchant)`—never a prior label’s `after`.
* **Gating (forward contract):** Downstream 1A RNG streams appear **iff** `is_multi=true`. **Discover the stream set programmatically** from the dataset dictionary (`dataset_dictionary.layer1.1A.yaml`) via entries with `owner_subsegment == "1A"` **and** `gating.gated_by == "rng_event_hurdle_bernoulli"`. If a legacy dictionary lacks `gating`, **fall back** to the artefact-registry enumeration. S1 does **not** enumerate names inline.

---

**Bottom line:** S1.3 produces a single-uniform Bernoulli decision on a **merchant-keyed**, **label-stable** substream, with a budget-correct envelope and a **cumulative** (per-substream) trace model. Everything is S0-compatible, order-invariant, and validator-checkable without guesswork.

---

## S1.4 — Event emission (hurdle Bernoulli), with **exact** envelope/payload, partitioning, invariants, and validation

#### 1) Where the records go (authoritative dataset id, partitions, schema)

Emit **one JSONL record per merchant** to the hurdle RNG dataset:

* **Dataset id:** registry entry for `rng_event_hurdle_bernoulli`.
* **Partitions (path):**

  ```
  logs/rng/events/hurdle_bernoulli/
    seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
  ```

  *(No `manifest_fingerprint`, `module`, or `substream_label` in the path; those are embedded in the envelope.)*
* **Schema:** layer schema anchor `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`.

> **Partition keys are exactly** `{seed, parameter_hash, run_id}` as bound in the dictionary/registry.
> **Path ↔ embed equality:** for every row, the embedded `{seed, parameter_hash, run_id}` **must equal** the folder values byte-for-byte.

---

#### 2) Envelope (shared; required for **all** RNG events)

Every hurdle record **must** carry the complete layer RNG envelope (single source of truth in the layer schema).

**Required fields**

* `ts_utc`, `run_id`, `seed`, `parameter_hash`, `manifest_fingerprint`, `module`, `substream_label`,
* `rng_counter_before_lo`, `rng_counter_before_hi`, `rng_counter_after_lo`, `rng_counter_after_hi`,
* `draws` (**required**, u128 as a decimal string),
* `blocks` (**required**, uint64).

**Semantics**

* `ts_utc` — RFC-3339 UTC with **exactly 6 fractional digits** and `Z` (microseconds).
* `module`, `substream_label` — **registry-closed literals** (schema-typed as strings; closure enforced by validators/registry); for this stream `substream_label == "hurdle_bernoulli"`.
* `rng_counter_*` — 128-bit counters represented as two u64 words; names define the pairing `(lo, hi)`. Object key **order is non-semantic**; producers **must** use the exact field names shown (…`_lo` and …`_hi`). Compose u128 as `(hi<<64) | lo`.
* `draws` — non-negative **u128 encoded as a base-10 string** (no sign; no leading zeros except `"0"`). It is the **authoritative** per-event uniform count.
* **Budget identity (must hold):**

  ```
  u128(after_hi,after_lo) − u128(before_hi,before_lo) = parse_u128(draws)
  ```

  For the hurdle stream specifically: `draws ∈ {"0","1"}`; `blocks ∈ {0,1}` and **must equal** `parse_u128(draws)`.
* **Identifier serialization:** 64-bit identifiers in the envelope (e.g., `seed`) are **JSON integers** per the layer schema (not strings).

> **Merchant scope (envelope vs event).** The shared RNG **envelope schema** admits an optional/nullable `merchant_id` for merchant-scoped streams (see layer schema). For the **hurdle** stream specifically, the **event schema requires** top-level `merchant_id`. Validators check presence under the event schema (and, if present, under the envelope anchor). This remains a **single flat JSON object**; “envelope” and “payload” are conceptual groupings only.

---

#### 3) Payload (event-specific; minimal and authoritative)

Fields and types (per the hurdle schema):

* `merchant_id` — **id64 JSON integer** (canonical u64).
* `pi` — JSON number, **binary64 round-trip** to the exact value computed in S1.2; must satisfy `0.0 ≤ pi ≤ 1.0`.
* `is_multi` — **boolean** outcome.
* `deterministic` — **boolean**, **derived**: `true` iff `pi ∈ {0.0, 1.0}` (binary64 equality).
* `u` — **required** with type **number | null**:

  * `u = null` iff `pi ∈ {0.0, 1.0}` (deterministic).
  * `u ∈ (0,1)` iff `0 < pi < 1` (stochastic); `u` must also round-trip to the same binary64.

**Outcome semantics (canonical, predicate form)**

* If `0 < pi < 1`: `is_multi := (u < pi)`.
* If `pi ∈ {0.0, 1.0}`: `is_multi := (pi == 1.0)`.

**Branch invariants**

Deterministic ⇒ `u == null` and a **non-consuming event** (`draws="0"`, `blocks=0`, `after == before`).
* Stochastic ⇒ `0 < u < 1`, `is_multi == (u < pi)`, and **exactly one uniform consumed** (`draws="1"`, `blocks=1`).

> The payload is **minimal** and authoritative for the decision; `eta` and any diagnostics are **not** part of this stream (they belong in non-authoritative diagnostic datasets, if present at all).

---

#### 4) Canonical examples (normative JSON; object key order non-semantic)

**Numeric policy for examples.** All numeric values below MUST be the **shortest round-trippable** IEEE-754 binary64 decimals. (Integer-typed ids remain JSON **integers** per schema.)

**Stochastic example (`0 < pi < 1`)**

```json
{
  "ts_utc": "2025-08-15T10:03:12.345678Z",
  "run_id": "0123456789abcdef0123456789abcdef",
  "seed": 1234567890123456789,
  "parameter_hash": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
  "manifest_fingerprint": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
  "module": "1A.hurdle_sampler",
  "substream_label": "hurdle_bernoulli",

  "rng_counter_before_lo": 9876543210,
  "rng_counter_before_hi": 42,
  "rng_counter_after_lo": 9876543211,
  "rng_counter_after_hi": 42,

  "draws": "1",
  "blocks": 1,

  "merchant_id": 184467440737095,
  "pi": 0.3725,
  "is_multi": true,
  "deterministic": false,
  "u": 0.1049
}
```

**Deterministic example (`pi ∈ {0.0,1.0}`)**

```json
{
  "ts_utc": "2025-08-15T10:03:12.345678Z",
  "run_id": "0123456789abcdef0123456789abcdef",
  "seed": 1234567890123456789,
  "parameter_hash": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
  "manifest_fingerprint": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
  "module": "1A.hurdle_sampler",
  "substream_label": "hurdle_bernoulli",

  "rng_counter_before_lo": 9876543210,
  "rng_counter_before_hi": 42,
  "rng_counter_after_lo": 9876543210,
  "rng_counter_after_hi": 42,

  "draws": "0",
  "blocks": 0,

  "merchant_id": 184467440737095,
  "pi": 1.0,
  "is_multi": true,
  "deterministic": true,
  "u": null
}
```

---

**Bottom line:** This section pins the **single authoritative** hurdle event stream: **where it’s written**, the **complete envelope** (with budget identity), the **minimal payload** with **boolean** `is_multi` and **required** `u:number|null`, and the **branch invariants** that tie `pi`, `u`, `deterministic`, and the **uniform budget** together—no ambiguity, no order-dependence, and no drift from S0.

---

#### 5) Write discipline, idempotency, and ordering

* **Exactly one hurdle row per merchant (per run).** Within `{seed, parameter_hash, run_id}` there is **exactly one** hurdle event for each `merchant_id`, and the hurdle row count equals the merchant universe cardinality **for the run’s `manifest_fingerprint`** (from ingress). Writes are **append-only** to `part-*` shards.
* **Stable partitioning.** The hurdle event dataset is partitioned **only** by `{seed, parameter_hash, run_id}`; **do not** include `manifest_fingerprint`, `module`, or `substream_label` in the path (they are embedded in the envelope).
* **Module/label stability.** `module` and `substream_label` are **registry-closed literals** (schema-typed as strings; closure enforced by validators/registry). For this stream, `substream_label == "hurdle_bernoulli"`; `module` **MUST** equal `"1A.hurdle_sampler"`.
* **Trace linkage (cumulative, substream-scoped).** Maintain a **cumulative** `rng_trace_log` per `(module, substream_label)` (no merchant dimension) within the run, including `rng_counter_before_{lo,hi}` and `rng_counter_after_{lo,hi}`. Totals are **saturating uint64** and equal the **sums** over all hurdle events in the run:

  * `draws_total == Σ parse_u128(draws)` (diagnostic; **required**; saturating uint64),
  * `blocks_total == Σ blocks` (normative; saturating uint64),
  * `events_total ==` hurdle event count (saturating uint64).
  *(No assertion that `u128(after)−u128(before)` equals `blocks_total` on the final row; that delta is **per-row**.)*

---

#### 6) Validation hooks (what replay must assert)

* **Schema conformance.** Every row validates against `#/rng/events/hurdle_bernoulli` (payload) and `$defs.rng_envelope` (envelope).
* **Budget identity & replay.** Let `d_m := 1` iff `0 < pi_m < 1`, else `0`. Assert:

  * `u128(after) − u128(before) = parse_u128(draws)`,
  * for hurdle: `parse_u128(draws) ∈ {0,1}` and `blocks = parse_u128(draws) = d_m`.
* **Decision predicate.**

  * If `d_m=0` (deterministic): `pi∈{0.0,1.0}`, `u==null`, `deterministic=true`, `after==before`, and `is_multi == (pi==1.0)`.
  * If `d_m=1` (stochastic): regenerate **one** uniform from the keyed substream at `before` (low-lane policy), map via open-interval `u01`, assert `0<u<1` and `(u<pi) == is_multi`; assert `after = before + 1`.
* **Trace reconciliation (cumulative, substream-scoped).** For the run, aggregate hurdle events and assert on the **final** trace row (selected per `#/rng/core/rng_trace_log`):
  * `trace.draws_total == Σ parse_u128(draws)` (**required**; diagnostic; saturating uint64),
  * `trace.blocks_total == Σ blocks` (normative; saturating uint64),
  * `trace.events_total ==` hurdle event count,
  * (no assertion on `u128(trace.after) − u128(trace.before)`; that difference is per-row, not cumulative).
* **Gating invariant.** Downstream **1A RNG streams** must appear for a merchant **iff** that merchant’s hurdle event has `is_multi=true`. **Build the set programmatically** from the dataset dictionary by selecting entries with `owner_subsegment == "1A"` and `gating.gated_by == "rng_event_hurdle_bernoulli"`. If the dictionary is legacy and lacks `gating`, **fall back** to the artefact-registry enumeration. S1 does **not** enumerate names inline.
* **Cardinality & uniqueness.** Hurdle row count equals the ingress merchant count for the **run** (same `manifest_fingerprint`); uniqueness key is `merchant_id` scoped by `{seed, parameter_hash, run_id}`.

---

#### 7) Failure semantics (surface at S1.4)

* **E_SCHEMA_HURDLE.** Record fails schema: missing required envelope fields; wrong types (e.g., `is_multi` not boolean, `u` not `number|null`); `u` violates open interval when stochastic; counters field names malformed.
* **E_COUNTER_MISMATCH.** Budget identity fails: `u128(after) − u128(before) ≠ parse_u128(draws)`; or hurdle emits values outside `{draws∈{"0","1"}}`; or `blocks ≠ parse_u128(draws)`.
* **E_GATING_VIOLATION.** Any downstream 1A RNG event exists for a merchant **without** a conformant hurdle event with `is_multi=true`. (Order is irrelevant; this is a **presence** invariant on the finalized datasets.)
* **E_PARTITION_MISMATCH.** Path partitions `{seed, parameter_hash, run_id}` differ from the same fields embedded in the envelope; or `module`/`substream_label` don’t match registry literals **exactly**.

(Shape/order and non-finite numeric faults are owned by S1.1–S1.2 preconditions.)

---

#### 8) Reference emission procedure (ordering-invariant; language-agnostic)

1. **Base counter.** Obtain the **base counter** for `(label="hurdle_bernoulli", merchant_id)` using the S0 keyed-substream primitive; set `before`.
2. **Branch from `pi`.**

   * If `pi ∈ {0.0,1.0}`: set `draws="0"`, `blocks=0`, `after=before`, `u=null`, `deterministic=true`, `is_multi=(pi==1.0)`.
   * If `0 < pi < 1`: draw **one** uniform `u∈(0,1)` (low-lane, open-interval `u01`); set `draws="1"`, `blocks=1`, `after=before+1`, `deterministic=false`, `is_multi=(u<pi)`.
3. **Emit hurdle event.** Envelope includes all required fields (`*_lo` and `*_hi` naming; object key order is non-semantic); payload includes `merchant_id` (JSON integer), `pi` (binary64 round-trip), `u:number|null`, `is_multi:boolean`, `deterministic:boolean`.
4. **Update cumulative trace (substream-scoped).** Increase `draws_total` and `blocks_total` as above and increment `events_total` by 1. *Producers update per event; validators select the final row using the rule in `#/rng/core/rng_trace_log`.*

*(Procedure is normative; S0 remains the authority for PRNG keying, counter arithmetic, lane policy, and `u01`.)*

---

**Bottom line:** S1.4 nails the **write discipline** (one row per merchant; stable `{seed, parameter_hash, run_id}` partitions), the **complete envelope** with an authoritative `draws` field and budget identity, the **minimal authoritative payload** (`is_multi` boolean; `u:number|null`), the **substream-scoped cumulative** trace model, and a validator-oriented hook set (budget, decision, gating, cardinality)—all order-invariant and S0-consistent.

---

## S1.5 — Determinism & Correctness Invariants (normative)

### Purpose

Freeze the invariants that must hold for every merchant’s hurdle decision so downstream states can **trust** and **replay** S1 exactly. The I-H invariants below are stated as precise predicates with the validator obligations that prove them.

---

### I-H0 — Environment & schema authority (precondition)

* **Numeric policy (S0):** IEEE-754 **binary64**, round-to-nearest-even, **no FMA**, **no FTZ/DAZ**; fixed-order reductions; deterministic `exp`.
* **Schema authority:** Every RNG record conforms to the **layer envelope** (single anchor) and its **event-specific schema**. The hurdle stream uses the registered dataset id and the schema anchor for `rng/events/hurdle_bernoulli`.

---

### I-H1 — Bit-replay (per merchant, per run)

**Statement.** For fixed inputs
$(x_m,\ \beta,\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{manifest_fingerprint})$, the pair $(u_m,\ \text{is_multi}(m))$ and the envelope counters $(C^{\text{pre}}_m,\ C^{\text{post}}_m)$ are **bit-identical** across replays and **independent of emission order** or sharding.

**Why it holds.** The keyed-substream primitive derives a **base counter** for $(\ell=\text{"hurdle_bernoulli"}, m)$ that depends only on the run keys and $(\ell,m)$. The draw budget is a pure function of $\pi_m$. The uniform $u_m$ is obtained by the S0 **open-interval** mapping from the substream (low-lane) and therefore deterministic.

**Validator.** Rebuild the base counter from `(seed, manifest_fingerprint, substream_label="hurdle_bernoulli", merchant_id)`; assert envelope `before` matches.
If `draws="1"`, regenerate $u$ and assert `(u < pi) == is_multi`. Assert counters match exactly.

---

### I-H2 — Consumption & budget (single-uniform law)

**Statement.** Let $d_m = \mathbf{1}\{0 < \pi_m < 1\}$. The hurdle consumes exactly `draws = d_m` uniforms and:

* If $0<\pi_m<1$: `after = before + 1`.
* If $\pi_m \in \{0.0,1.0\}$: `after = before`.

**Law.** Envelope budgeting must satisfy
`u128(after) − u128(before) = parse_u128(draws)` (unsigned 128-bit arithmetic). For the hurdle, `draws ∈ {"0","1"}`; blocks is required and must equal `parse_u128(draws)`.

**Trace model (cumulative).** RNG trace is **cumulative per `(module, substream_label)`** within the run (no merchant dimension). Its totals equal the **sums across all hurdle events** for that substream.

**Validator.** Check the envelope identity above; aggregate event budgets over all hurdle rows for `(module, substream_label)` and assert equality with the trace totals.

---

### I-H3 — Schema-level payload discipline

**Statement.** The hurdle payload is **minimal and authoritative** with fields:
`merchant_id` (**id64 integer**), `pi` (binary64 round-trip), `is_multi` (**boolean**), `deterministic` (**boolean**), `u` (**number|null**, **required**).

**Equivalences (binary64 semantics).**

* `deterministic ⇔ (pi ∈ {0.0, 1.0}) ⇔ draws="0" ⇔ u == null`.
* `¬deterministic ⇔ (0 < pi < 1) ⇔ draws="1" ⇔ u ∈ (0,1)` and `is_multi == (u < pi)`.

`is_multi` is **boolean only** (never `{0,1}`); any other encoding is non-conformant.

---

### I-H4 — Branch purity (downstream gating)

**Statement.** Downstream **1A RNG streams** for a merchant appear **iff** that merchant’s hurdle event has `is_multi=true`.

**Authority.** Validators **MUST** derive the gated set **programmatically** from the dataset dictionary (`owner_subsegment == "1A"` **and** `gating.gated_by == "rng_event_hurdle_bernoulli"`). If the dictionary is legacy and lacks `gating`, they **MUST** fall back to the artefact-registry enumeration. S1 does **not** enumerate stream names inline.

**Validator.** For each merchant, check presence/absence of all gated streams per the registry list against the merchant’s hurdle `is_multi` value.

---

**Bottom line:** S1.5 fixes the invariant surface: a deterministic, order-invariant substream; a single-uniform budget with a strict envelope law and **cumulative** trace; a minimal, typed payload with `u:number|null` and boolean `is_multi`; and a registry-driven gating rule. These invariants give downstream states and validators a single, unambiguous contract for replay and auditing.

---

### I-H5 — Cardinality & uniqueness (per run)

* Exactly **one** hurdle record per merchant within `{seed, parameter_hash, run_id}`. **No duplicates.**
* **Presence gate, not order:** downstream 1A RNG streams are validated **by presence** relative to the hurdle decision (see I-H4). Emission order is **unspecified** and not validated.

**Validator.** Count hurdle rows and assert equality with the ingress `merchant_ids` for the run; assert uniqueness of `merchant_id` within the hurdle partition.

---

### I-H6 — Envelope completeness & equality with path keys

* Every record contains the **full** RNG envelope required by `$defs.rng_envelope`. `draws` is **required**; `blocks` must equal `parse_u128(draws)` and for hurdle be `0` or `1`.
* Embedded `{seed, parameter_hash, run_id}` **equal** the same keys in the dataset path. `module` and `substream_label` are registry literals checked **in the envelope** (they do **not** appear in the path).
* **Flat record.** Hurdle records are a **single flat JSON object**. `merchant_id` is declared on the shared RNG envelope (nullable in the envelope) and is **required by the hurdle event schema**; listing it under “payload” is purely a conceptual grouping.

---

### I-H7 — Order-invariance & concurrency safety

* Emission **order is unspecified**; correctness depends only on per-row content. Replays with different shard orders yield byte-identical counters and decisions (I-H1).
* Writers may produce multiple `part-*` files; **set equivalence** of rows defines dataset equivalence.

---

### I-H8 — Independence across merchants & substreams

* Base counters are derived **per (label, merchant_id)** via the keyed mapping, so distinct pairs receive **disjoint** substreams under a fixed `{seed, manifest_fingerprint}`.
* `substream_label` in the envelope is **exactly** `"hurdle_bernoulli"`, preventing accidental reuse of counters intended for other labels.

---

### I-H9 — Optional diagnostics remain out of band

* If any diagnostic cache (e.g., `hurdle_pi_probs`) exists, it is **non-authoritative**. S1 decisions must match an **independent recomputation** of $(\eta,\pi)$ from $(x_m,\beta)$. Validators may compare for sanity; disagreements never override the event.

---

### I-H10 — Replay equations (what the validator recomputes)

For each hurdle row $r$ with merchant $m$:

1. **Recompute $\eta,\pi$.** Using S1.2 rules (fixed-order dot + two-branch logistic (no clamp)), assert `finite(η)` and `0.0 ≤ pi ≤ 1.0`.
2. **Rebuild base counter.** Using `(seed, manifest_fingerprint, substream_label="hurdle_bernoulli", merchant_id)`, assert `rng_counter_before == base_counter`.
3. **Budget identity.** From $\pi$, set `draws = "1"` iff $0<\pi<1$, else `"0"`. Assert
   `u128(after) − u128(before) = parse_u128(draws)` and, blocks is required and must equal `parse_u128(draws)`.
   **Trace reconciliation:** join to the **cumulative** trace record for `(module, substream_label)` and assert its totals equal the **sum of hurdle event budgets**.
4. **Outcome consistency.**

   * If `draws="1"`: regenerate a single uniform via the S0 lane policy & open-interval mapping; assert `0<u<1` and `(u < pi) == is_multi`.
   * If `draws="0"`: assert `pi ∈ {0.0,1.0}`, `u == null`, `deterministic == true`, and `is_multi == (pi == 1.0)`.

> **Determinism equivalence (normative recap):** `π∈{0.0,1.0}` (binary64-exact) ⇔ `deterministic==true` ⇔ `draws=="0"` ⇔ `u==null` ⇔ `is_multi==(π==1.0)`.

---

### Failure bindings (S0.9 classes surfaced by these invariants)

* **Envelope/label/counter failures** → RNG envelope & accounting failure (**F4**) → **abort run**.
* **Partition mismatch (path vs embedded)** → lineage/partition failure (**F5**) → **abort run**.
* **Schema breach** (e.g., missing required envelope fields; `is_multi` not boolean; `u` not `number|null`; `u` out of (0,1) when stochastic) → schema failure (treated as **F4**).
* **Gating violation** (downstream event exists when hurdle `is_multi=false` or no hurdle event) → coverage/gating failure (validator; event-family coverage class, e.g., **F8**).

---

### What this guarantees downstream

* **Deterministic hand-off (by content, not cursor).** Each merchant has a single authoritative hurdle decision (`is_multi`) and a **self-contained** envelope. **Downstream states derive their own base counters** from the keyed mapping for their **own labels**; there is **no** requirement that `before(next) == after(hurdle)`.
* **Auditable lineage.** Hurdle events are partitioned by `{seed, parameter_hash, run_id}`; validation/egress bundles are fingerprint-scoped. Consumers can verify they are reading the intended parameterization using the embedded `manifest_fingerprint`.

---

**Bottom line:** S1.5 (complete) nails the invariants that make S1 reproducible and safe to build on: uniqueness/cardinality, full envelope with budget identity, order-invariance, cross-label independence, gated downstream presence, diagnostics out-of-band, and validator-ready replay equations—mapped to S0.9 failure classes for actionable aborts.

---

## S1.6 — Failure modes (normative, abort semantics)

**Scope.** Failures here are specific to S1 (hurdle): design/β misuse, numeric invalids, schema/envelope breaches, RNG counter/accounting errors, partition drift, and downstream gating. This section formalizes **all predicates, detection points, and run-abort semantics** that S1 may surface.

**Authoritative references:**
Layer schema (envelope anchor + hurdle event schema), dataset dictionary/registry (dataset id, partitions, enums), and S1 invariants (I-H1..I-H10).

---

### Family A — Design / coefficients misuse (compute-time hard abort)

**A1. `beta_length_mismatch`**
**Predicate.** `len(β) ≠ 1 + C_mcc + 2 + 5` when forming $\eta = \beta^\top x$.
**Detect at.** S1.1/S1.2 entry. **Abort run.**
**Forensics.** `{expected_len, observed_len, mcc_cols, channel_cols, bucket_cols}`.

**A2. `unknown_category`**
**Predicate.** `mcc_m` not in MCC dictionary, or `channel_m ∉ {CP,CNP}`, or `b_m ∉ {1..5}`.
**Detect at.** Precondition breach (inputs from S0). **Abort run.**
**Forensics.** `{merchant_id, field, value}`.

**A3. `column_order_mismatch`**
**Predicate.** Frozen encoder column order does **not** match β’s bundle order.
**Detect at.** S1.1 design load. **Abort run.**
**Forensics.** `{block:"mcc|channel|bucket", dict_digest, beta_digest}`.

---

### Family B — Numeric invalids (compute-time hard abort)

**B1. `hurdle_nonfinite_eta`**
**Predicate.** $\eta$ non-finite after fixed-order binary64 dot product.
**Detect at.** S1.2. **Abort run.**
**Forensics.** `{merchant_id, eta}`.

**B2. `hurdle_nonfinite_or_oob_pi`**
**Predicate.** $\pi$ non-finite **or** $\pi \notin [0,1]$ after the two-branch logistic (no clamp).
**Detect at.** S1.2. **Abort run.**
**Forensics.** `{merchant_id, eta, pi}`.

---

### Family C — Envelope & accounting (RNG/logging hard abort)

**C1. `rng_envelope_schema_violation`**
**Predicate.** Missing/mistyped **envelope** field required by the anchor:
`{ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, draws, blocks}`.

**Detect at.** Writer + validator schema checks. **Abort run.**
**Forensics.** `{dataset_id, path, missing_or_bad:[...]}`.

**C2. `substream_label_mismatch`**
**Predicate.** Envelope `substream_label` ≠ registry literal `"hurdle_bernoulli"`.
**Detect at.** Writer assertion; validator. **Abort run.**

**C3. `rng_counter_mismatch`**
**Predicate.** `u128(after) − u128(before) ≠ parse_u128(draws)`; or `blocks ≠ parse_u128(draws)`. For hurdle, it must also satisfy `blocks ∈ {0,1}` and `draws ∈ {"0","1"}`.
**Detect at.** Writer (optional) and validator reconciliation. **Abort run.**
**Forensics.** `{before_hi, before_lo, after_hi, after_lo, blocks, draws}`.

**C4. `rng_trace_missing_or_totals_mismatch`**
**Predicate.** Missing **final cumulative** `rng_trace_log` record for `(module, substream_label)` within the run, **or** its totals ≠ **sum of event budgets** for that key.
**Detect at.** Validator aggregate. **Abort run.**
**Final-row selection rule.** Selection per schema anchor `schemas.layer1.yaml#/rng/core/rng_trace_log`.

**C5. `u_out_of_range`**
**Predicate.** In a stochastic branch, payload `u` not in `(0,1)` (open-interval violation).
**Detect at.** Writer check; validator schema + re-derivation. **Abort run.**
**Forensics.** `{merchant_id, u, pi}`.

---

### Family D — Payload/schema discipline (hurdle event)

**D1. `hurdle_payload_violation`**
**Predicate.** Record fails the hurdle event schema: missing any of `{merchant_id, pi, is_multi, deterministic, u}`; `is_multi` not **boolean**; `u` not `number|null`; `pi` not binary64-round-trippable (or out of `[0,1]`).
**Detect at.** Writer schema validation; CI/validator. **Abort run.**

**D2. `deterministic_branch_inconsistent`**
**Predicate.** Payload contradicts branch rules:

* `0<pi<1` but `u` absent/`null` or `deterministic=true`, **or**
* `pi∈{0.0,1.0}` but `u` numeric or `deterministic=false`.
  **Detect at.** Writer; validator. **Abort run.**

---

### Family E — Partitioning & lineage coherence (paths vs embedded)

**E1. `partition_mismatch`**
**Predicate.** Path partitions `{seed, parameter_hash, run_id}` do **not** equal the same embedded envelope fields; or path includes unexpected partitions (e.g., `module`, `substream_label`, `manifest_fingerprint`).
**Detect at.** Writer; validator lint. **Abort run.**

**E2. `wrong_dataset_path`**
**Predicate.** Hurdle events written under a path that does not match the dictionary/registry binding (dataset id ↔ path template).
**Detect at.** Writer; validator path lint. **Abort run.**

---

### Family F — Coverage & gating (cross-stream structural)

**F1. `gating_violation_no_prior_hurdle_true`**
**Predicate.** Any downstream **1A RNG stream** appears for merchant $m$ **without** a conformant hurdle event with `is_multi=true` in the run. (Presence rule; emission order irrelevant.)
**Detect at.** Validator cross-stream join using the set **derived programmatically** from the dataset dictionary (`owner_subsegment == "1A"` **and** `gating.gated_by == "rng_event_hurdle_bernoulli"`); **fallback** to the artefact-registry enumeration if the dictionary lacks `gating`. **Run invalid (hard).**

**F2. `duplicate_hurdle_record`**
**Predicate.** More than one hurdle event for the same merchant within `{seed, parameter_hash, run_id}`.
**Detect at.** Validator uniqueness check. **Abort run.**

**F3. `cardinality_mismatch`**
**Predicate.** `count(hurdle_events) ≠ count(merchant_ids)` for the run.
**Detect at.** Validator count check. **Abort run.**

---

**Scope recap:** S1.6 enumerates **all abortable predicates** for the hurdle: design/β misuse, numeric invalids, complete envelope with strict **budget identity**, cumulative trace reconciliation, payload typing/branch rules, exact partition/embedding equality, and registry-driven gating. Each failure includes a precise detection point and forensics so the run can halt with actionable evidence.

---

### Error object (forensics payload; exact fields)

Every S1 failure MUST emit a JSON object (alongside the validation bundle / `_FAILED.json` sentinel) carrying lineage + precise forensics:

```json
{
  "failure_class": "F4",
  "failure_code": "rng_counter_mismatch",
  "state": "S1",
  "module": "1A.hurdle_sampler",
  "substream_label": "hurdle_bernoulli",
  "dataset_id": "rng_event_hurdle_bernoulli",
  "path": "logs/rng/events/hurdle_bernoulli/seed=1234567890123456789/parameter_hash=abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789/run_id=0123456789abcdef0123456789abcdef/part-0001.jsonl",
  "merchant_id": "184467440737095",
  "detail": {
    "before": {"hi": 42, "lo": 9876543210},
    "after":  {"hi": 42, "lo": 9876543211},
    "draws": "1",
    "expected_delta": "1",
    "blocks": 1,
    "trace_blocks_total": 0
  },
  "seed": 1234567890123456789,
  "parameter_hash": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
  "manifest_fingerprint": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
  "run_id": "0123456789abcdef0123456789abcdef",
  "ts_utc": 1752555123123456000
}
```

* `dataset_id` is the **registry id** (not a path).
* **Types per S0 failure schema:** `seed` is a JSON **integer**; `merchant_id` is a JSON **string** (or `null` when not applicable); `ts_utc` is a JSON **integer** = nanoseconds since Unix epoch (UTC). The `detail` payload for counter mismatches must include `before`, `after`, `blocks:uint64`, and `draws:"uint128-dec"`. 

---

### Where to detect (first line) & who double-checks

| Family / Code                  | First detector (runtime)         | Secondary (validator / CI)                                                                                                                                                                                                        |
|--------------------------------|----------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| A1–A3 design/β                 | S1.1/S1.2 guards                 | (optional) build lints                                                                                                                                                                                                            |
| B1–B2 numeric invalid          | S1.2 evaluation guards           | Re-eval η, π                                                                                                                                                                                                                      |
| C1 envelope schema             | Writer JSON-Schema check         | Validator schema pass                                                                                                                                                                                                             |
| C2 label mismatch              | Writer assertion                 | Validator                                                                                                                                                                                                                         |
| C3 counter mismatch            | Writer assertion                 | Validator counter math (`u128(after)−u128(before)` vs **blocks**, and **`blocks == parse_u128(draws)`**); trace `blocks_total` reconciliation                                                                                     |
| C4 trace missing/totals mis    | —                                | Trace aggregate vs Σ(event budgets)                                                                                                                                                                                               |
| C5 u out of range              | Writer check                     | `u01` + recompute                                                                                                                                                                                                                 |
| D1 payload schema              | Writer JSON-Schema check         | Validator schema pass                                                                                                                                                                                                             |
| D2 deterministic inconsistency | Writer assertion                 | Recompute branch from π                                                                                                                                                                                                           |
| E1 partition mismatch          | Writer path/embed equality check | Path lint (only `{seed, parameter_hash, run_id}`)                                                                                                                                                                                 |
| E2 wrong dataset path          | —                                | Dictionary/registry binding lint                                                                                                                                                                                                  |
| F1 gating violation            | —                                | Cross-stream presence check using **dataset dictionary `gating:` blocks** (`owner_subsegment == "1A"` and `gating.gated_by == "rng_event_hurdle_bernoulli"`); **fallback** to artefact-registry enumeration if `gating` is absent |
| F2 duplicate record            | —                                | Uniqueness check                                                                                                                                                                                                                  |
| F3 cardinality mismatch        | —                                | Row count vs ingress merchant set                                                                                                                                                                                                 |

> **Gating note:** Enforcement is **presence-based**: downstream gated streams must exist **iff** hurdle `is_multi=true`. No temporal “prior” requirement. **Literal:** `gating.gated_by == "rng_event_hurdle_bernoulli"`.

---

### Validator assertions (executable checklist)

Using the dictionary/registry bindings and schema anchors:

1. **Schema:** validate hurdle events **and** cumulative trace against the layer anchors (envelope + event + trace).
2. **Counters & budget:** enforce the **budget identity** (see **S1.4 — Envelope**) and, for **hurdle**, the branch constraints `draws ∈ {"0","1"}` and `blocks ∈ {0,1}`.
   **Trace reconciliation:** per `(module, substream_label)`, `blocks_total` equals **Σ(event blocks)** (saturating to uint64; normative) and `draws_total` equals **Σ(event draws)** (saturating to uint64; **required**, diagnostic); and `events_total` equals the **event count** (saturating to uint64; normative).
   **Note:** Do **not** assert any relationship between `u128(key.after) − u128(key.before)` on the **final trace row** and these cumulative totals; that per-row delta is not equal to a cumulative sum.
3. **Decision:** recompute $\eta,\pi$ (S1.2 rules); if stochastic (`draws="1"`), regenerate one uniform from the keyed **base counter** (low-lane, open-interval `u01`) and assert `0<u<1` and `(u<pi) == is_multi`.
   *Doc note:* Whether one writes `(u < \pi)` or `(u \le \pi)` is **immaterial** here—`u` is drawn from an **open interval** (schema `$defs/u01`) so the equality case has probability 0, and the **deterministic branch** (`\pi ∈ {0,1}`) carries `u = null` by schema. See S0 open-interval and S1 envelope/payload rules.
4. **Deterministic regime:** if `draws="0"`, assert `pi ∈ {0.0,1.0}` **(binary64 *bit-exact*)**, `deterministic=true`, and `u == null`.
5. **Partition lint:** path partitions `{seed, parameter_hash, run_id}` equal the embedded envelope; path **must not** include `module`, `substream_label`, or `manifest_fingerprint`.
6. **Gating:** build the set of **gated 1A RNG streams** from the **dataset dictionary/registry** using `owner_subsegment="1A"` and the enumerated **gated** dataset ids; for each merchant, presence/absence of those streams is **iff** hurdle `is_multi=true`. S1 does **not** enumerate names inline.
7. **Uniqueness & cardinality:** within the run partition, **exactly one** hurdle row per `merchant_id`; hurdle row count equals the ingress merchant cardinality.

---

### Minimal examples (concrete)

* **Numeric invalid (B2).** `pi` is NaN after logistic ⇒ `hurdle_nonfinite_or_oob_pi` ⇒ **abort**.
* **Envelope gap (C1).** Missing `rng_counter_after_hi` ⇒ `rng_envelope_schema_violation` ⇒ **abort**.
* **Gating failure (F1).** A gated stream (from the **dataset dictionary/registry**) exists for merchant `m` while hurdle `is_multi=false` or no hurdle event exists ⇒ `gating_violation_no_prior_hurdle_true` ⇒ **run invalid**.

---

**Bottom line:** S1.6 (complete) specifies the **failure predicates**, **where they’re detected**, the **forensics object** (with registry ids, lineage, counters, and budgets), and the **validator checklist**—all consistent with S0 and the locked S1 contracts (nullable `u`, boolean `is_multi`, full envelope with required `draws`, stable `{seed, parameter_hash, run_id}` partitions, cumulative trace per substream, and registry-driven gating).

---

## S1.7 — Outputs of S1 (state boundary, normative)

### A) Authoritative event stream that S1 **must** persist

For every merchant $m\in\mathcal{M}$, S1 writes **exactly one** JSONL record to the hurdle RNG dataset:

```
logs/rng/events/hurdle_bernoulli/
  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

* **Dataset id (registry):** `rng_event_hurdle_bernoulli`.
* **Partitions (path):** `{seed, parameter_hash, run_id}` only.
  *(Do **not** include `manifest_fingerprint`, `module`, or `substream_label` in the path; those live in the envelope.)*
* **Schema:** `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`.

**Envelope (shared; required for all RNG events):**
{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, draws, blocks }

`module`, `substream_label` are **registry-closed literals** (schema-typed as strings; closure enforced by validators/registry).
* **Budget identity (must hold):**
  `u128(after) − u128(before) = parse_u128(draws)` (unsigned 128-bit arithmetic).
  For the hurdle stream (a **single-uniform family**), `draws ∈ {"0","1"}` (unit = one 64-bit uniform) and `blocks ∈ {0,1}` and **must equal** `parse_u128(draws)`—**hurdle-specific**. Other families may record `blocks=1` with `draws>1`.

**Identifier serialization:** fields typed as `uint64/id64` in the schema (e.g., `seed`, counter words, `merchant_id`) are emitted as **JSON integers** (not strings).

**Payload (authoritative, minimal):**
`{ merchant_id, pi, is_multi, deterministic, u }`
(Note: `merchant_id` is **required** by the hurdle event schema and appears as a **top-level** field in the event; it is optional in the shared envelope but **mandatory** here by the event schema.)

* `merchant_id` — **id64 integer**.
* `pi` — JSON number, **binary64 round-trip**, `0.0 ≤ pi ≤ 1.0`.
* `is_multi` — **boolean**.
* `deterministic` — **boolean**, derived: `true` iff `pi ∈ {0.0, 1.0}` (binary64).
* `u` — **required** `number|null`: `u=null` iff `pi ∈ {0.0,1.0}`, else `u∈(0,1)` (open interval).

> **Diagnostics policy.** Diagnostic/context fields (e.g., `eta`, `mcc`, `channel`, `gdp_bucket_id`) are **allowed by the schema as optional/nullable**, but they are **non-authoritative**: producers **SHOULD NOT** emit them, and validators **MUST ignore** them if present.

**Companion trace (cumulative; per-substream, no merchant dimension):**
Maintain a **cumulative** `rng_trace_log` row per `(module, substream_label)` within the run; its totals equal the **sum of event budgets** for that substream. (Trace **rows are emitted per event**; consumers pick the **final** row per key. No merchant dimension in trace.)

* **Totals semantics (normative):**
  - `events_total` = **count of event rows** for that `(module, substream_label)` in the run (saturating `uint64`);
  - `blocks_total` = **Σ(event.blocks)** for that key in the run (saturating `uint64`);
  - `draws_total`  = **Σ(event.draws)** for that key in the run (saturating `uint64`).
  (Matches `schemas.layer1.yaml#/rng/core/rng_trace_log` and dictionary text for the trace dataset.) 

* **Final-row selection rule.** Selection per schema anchor `schemas.layer1.yaml#/rng/core/rng_trace_log`.
 
> The hurdle event is the **only authoritative source** of the decision and its **own** counter evolution.

**Trace path ↔ embed (subset):** For `rng_trace_log`, the embedded envelope fields present (**`seed`, `run_id`**) **equal** the same path keys; **`parameter_hash` is path-only**.

---

### B) In-memory **handoff tuple** to downstream (typed, deterministic)

S1 does not persist a “state table”; it yields a **typed tuple** per merchant to the orchestrator:

$$
\boxed{\ \Xi_m \;=\; \big(\ \text{is_multi}:\mathbf{bool},\ N:\mathbb{N},\ K:\mathbb{N},\ \mathcal{C}:\text{set[ISO_3166-1 alpha-2]},\ C^{\star}:\text{u128}\ \big)\ }.
$$

**Field semantics (normative):**

* `is_multi` — hurdle outcome (**boolean**) from the event payload.
* `N` — **target outlet count** for S2 when `is_multi=true`; set `N:=1` on the single-site path.
* `K` — **non-home country budget**; initialize `K:=0` on the single-site path; multi-site assigns later.
* `𝓒 : \text{set[ISO_3166-1 alpha-2]}` — **country set accumulator**;  
  _Ordering invariant:_ maintain `𝓒` as a **deterministic ordered set** with **rank 0 reserved for `home_iso(m)`**. Any later country allocations **append** in a deterministic order; downstream materializations **must preserve** this order (pinned later in `alloc/country_set`).
* $C^{\star}$ — the hurdle event’s **post** counter as u128, carried **only for audit**. Represent as either:
  (i) a **decimal** `u128` string (`rng_counter_after_dec_u128`), or
  (ii) a labelled struct `{after_hi:uint64, after_lo:uint64}` (no positional tuples).

**Persistence note:** $C^{\star}$ is **not persisted** as a column in any dataset; it travels only in the in-memory handoff tuple for audit/replay and **must not** be used for downstream counter chaining.

**Crucial counter rule:**
Downstream states **do not** chain from $C^{\star}$. Each downstream RNG stream derives its **own base counter** from S0’s keyed-substream mapping using its **own** `(module, substream_label, merchant_id)`; there is **no cross-label counter chaining**.

**Branch semantics:**

* If `is_multi == false`: set `N:=1`, `K:=0`, `𝓒 := { home_iso(m) }`, and route to **S7** (single-home placement). No NB/ZTP/Dirichlet/Gumbel streams may appear.
* If `is_multi == true`: route to **S2** (NB branch). `N`, `K` are assigned downstream; `𝓒` starts as `{ home_iso(m) }`.

---

### C) Downstream visibility (for validation & joins)

Validators discover **gated** 1A RNG streams **programmatically** in the dataset dictionary via `gating:` blocks (`owner_subsegment == "1A"` **and** `gating.gated_by == "rng_event_hurdle_bernoulli"`). If the dictionary is legacy and lacks `gating`, they **fall back** to the artefact-registry enumeration. Those streams must be **present iff** `is_multi=true` for a merchant. S1 does **not** enumerate names inline.

---

### D) Optional diagnostic dataset (parameter-scoped; not consulted by samplers)

If enabled, a diagnostic table may be persisted (often produced in S0.7):

```
data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/…
```

**Schema:** `#/model/hurdle_pi_probs` (authoritative; see S0.7). **Contents (per merchant):**
`{ parameter_hash (embedded; must equal path key), merchant_id, logit:float32, pi:float32, produced_by_fingerprint? }`.
`manifest_fingerprint` is **not** part of this parameter-scoped dataset. This table is **read-only** and **non-authoritative**; samplers never consult it.

---

### E) Boundary invariants (must hold when S1 ends)

1. **Single emit:** exactly one hurdle record per merchant per `{seed, parameter_hash, run_id}` and exactly one $\Xi_m$.
2. **Cross-label independence:** downstream RNG events **derive** their base counters via S0’s keyed mapping for their **own** labels; there is **no** requirement that `before(next) == C^{\star}`.
3. **Branch purity (gating):** gated downstream 1A RNG streams are **present iff** `is_multi=true`.
4. **Lineage coherence:** dataset paths use `{seed, parameter_hash, run_id}`; embedded envelope keys equal the path keys (**see V2: Path ↔ embed equality**); egress/validation later uses `fingerprint={manifest_fingerprint}`.
5. **Numeric consistency:** hurdle `pi` equals the S1.2 recomputed value (fixed-order dot + two-branch logistic (no clamp)).

---

### F) Minimal handoff construction (reference)

```text
INPUT:
  hurdle_event for merchant m (envelope + payload), home_iso(m)

OUTPUT:
  Xi_m = (is_multi, N, K, C_set, C_star)

1  is_multi := hurdle_event.payload.is_multi                 # boolean
2  C_star   := envelope.rng_counter_after_dec_u128  # or {after_hi, after_lo}; audit only

3  if is_multi == false:
4      N := 1
5      K := 0
6      C_set := { home_iso(m) }
7      next_state := S7
8  else:
9      N := <unassigned>   # set in S2
10     K := <unassigned>   # set in cross-border/ranking
11     C_set := { home_iso(m) }
12     next_state := S2

13  return Xi_m, next_state
```

*(This is a handoff contract, not persisted state. Downstream states derive their **own** base counters; `C_star` is for audit.)*

---

**Scope recap:** S1 outputs **one** authoritative hurdle event per merchant (complete envelope + minimal payload) and a **typed, deterministic handoff tuple**. The boundary guarantees **gated presence**, **cross-label RNG independence** (no counter chaining), stable 3-key partitions, and numeric consistency—giving downstream states and validators a clean, replayable interface.

---

## S1.V — Validator & CI (normative)

### V0. Purpose & scope

Prove that every hurdle record is (a) **schema-valid**, (b) **numerically correct** under the pinned math policy, (c) **RNG-accounted** (counters ↔ uniform budget), (d) **partition-coherent**, and (e) **structurally consistent** with downstream streams via **presence-based gating**.
Validator logic is **order-invariant** (shard/emit order is irrelevant) and uses the **dataset dictionary/registry** plus S1 invariants.
*Doc note:* Path/partition rules are **normative** in **V2**; any repeats elsewhere are **reminders** that defer to V2.

---

### V1. Inputs the validator must read
**Notation.** For any counter pair `{lo:uint64, hi:uint64}` (matching the envelope names `*_lo`, `*_hi`), define `u128(x) := (x.hi << 64) | x.lo` and `Δctr := u128(after) − u128(before)`. We use `Δctr` below for per-event counter deltas and reconciliation rules.

1. **Locked specs:** the S1 state text (this document) and the combined journey spec (for cross-state joins).
2. **Event datasets (logs):**

   * **Hurdle events** — dataset id `rng_event_hurdle_bernoulli`, schema `#/rng/events/hurdle_bernoulli`, partitions

     ```
     logs/rng/events/hurdle_bernoulli/
       seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
     ```
   * **RNG trace (cumulative)** — dataset id `rng_trace_log`; per (module='1A.hurdle_sampler', substream_label='hurdle_bernoulli') totals (saturating `uint64`) **and** `rng_counter_before/after` for the run (no merchant dimension; append-safe; take the **final** row per key — **selection rule per** `schemas.layer1.yaml#/rng/core/rng_trace_log`).  
     *(S1 uses a single fixed substream label: `hurdle_bernoulli`.)*
   * **Downstream gated streams** — discoverable **programmatically** in the dataset dictionary (`dataset_dictionary.layer1.1A.yaml`) via the `gating:` blocks. Concretely: select entries with `owner_subsegment == "1A"` **and** `gating.gated_by == "rng_event_hurdle_bernoulli"` (e.g., `rng_event_gamma_component`, `rng_event_poisson_component`). 
     If a legacy dictionary lacks `gating`, fall back to the artefact-registry enumeration for the same set. S1 does **not** enumerate names inline.
3. **Design/β artefacts:** frozen encoders/dictionaries and the single-YAML hurdle coefficients bundle (β).
4. **Lineage keys:** `{seed, parameter_hash, manifest_fingerprint, run_id}` from path + envelope; the **shared RNG envelope** is mandatory for each event.

---

### V2. Discovery & partition lint (dictionary-backed)

* **Locate** the hurdle partition for the run using the dictionary/registry binding.
* **Path ↔ embed equality:** for **every row**, the embedded envelope keys
  `{seed, parameter_hash, run_id}` **equal** the same path keys.
  `module` and `substream_label` are checked **in the envelope only** as registry literals (they do **not** appear in the path).
  `manifest_fingerprint` is **embedded only** (never a path partition).
* **Canonical path representation (normative):** partition values must be **string-identical** to their canonical formats:
  - `seed` → base-10 **unsigned** with **no leading zeros** (except the single digit `"0"` when zero);
  - `parameter_hash` → **lowercase** 64-hex (`hex64`);
  - `run_id` → **lowercase** 32-hex (`hex32`).
  The equality check in the previous bullet is performed **byte-for-byte** on these canonical strings (path segment vs embedded field).
* **Trace path ↔ embed (subset):** For `rng_trace_log`, the embedded envelope fields present (`seed`, `run_id`) **equal** the same path keys; `parameter_hash` is path-only.
* **Schema anchors** are fixed by the layer schema set. Payload keys are exactly
  `{merchant_id, pi, is_multi, deterministic, u}`; the envelope is the layer-wide anchor.
  For S1 hurdle events, the envelope literal **`module` MUST equal `"1A.hurdle_sampler"`** and
  **`substream_label` MUST equal `"hurdle_bernoulli"`** (registry literals; validated against the layer schema).
* **Merchant scope & dual validation.** For merchant-scoped streams the envelope anchor admits `merchant_id` (nullable), while the hurdle **event schema requires** `merchant_id`. Validators treat the record as **one flat object** and enforce presence per the event schema (plus envelope conformance where applicable).

> The **allowed literal set** for `module` and `substream_label` is resolved from the **dataset dictionary/registry**; S1 does **not** maintain a local enumerated list.

> **Diagnostics policy (schema-aligned).** Optional diagnostic fields permitted by the layer schema (e.g., `eta`, or categorical predictors such as `mcc`, `channel`, `gdp_bucket_id`) are **non-authoritative** for S1.
> Producers **SHOULD NOT** emit them in `rng_event_hurdle_bernoulli`; validators **MUST ignore** such fields if present—they have no effect on outcome, gating, or validation predicates.

> **Numeric policy (examples reminder):** 64-bit counters/ids remain **JSON integers**; the u128 **`draws`** field is a **decimal string**; probabilities are IEEE-754 binary64; `u` uses S0’s **open-interval** `u01` mapping.

**Discovery checks:**

* **P-1:** partition exists; **P-2:** at least one `part-*` file;
* **P-3:** hurdle row count equals the ingress merchant count for the run;
* **P-4:** uniqueness of `merchant_id` within `{seed, parameter_hash, run_id}`.

---

### V3. Schema conformance (row-level)

Validate **every** hurdle record against:

* **Envelope (complete):**
  `ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, draws, blocks`.
  (`module`/`substream_label` are **registry-closed literals**; `draws` is **u128 as a decimal string**).
* **Payload (minimal, authoritative):**
  `merchant_id` (**id64 JSON integer**), `pi` (**binary64 round-trip**, `0.0 ≤ pi ≤ 1.0`),
  `is_multi` (**boolean**), `deterministic` (**boolean**, derived from `pi`),
  `u` (**required** with type **number|null**: `null` iff `pi ∈ {0.0,1.0}`, else `u∈(0,1)`).

**Flat record reminder.** There is **one** top-level JSON object per row; the “envelope” vs “payload” lists above are **not** separate nested objects.

**Authority.** The envelope/payload key sets above are the **single normative inventory** for S1 hurdle. Any other lists (e.g., in S1.4 or examples) are **non-authoritative recaps** and must not diverge from V3.

**Counter fields.** `rng_counter_*_{lo,hi}` are **named** words; JSON object key order is **non-semantic**.

> **Diagnostics policy.** Diagnostic/context fields (e.g., `eta`, `mcc`, `channel`, `gdp_bucket_id`) are **allowed by the schema as optional/nullable**, but they are **non-authoritative**: producers **SHOULD NOT** emit them, and validators **MUST ignore** them if present.

---

### V4. Recompute η and π (numeric truth)

For each merchant $m$:

1. Rebuild $x_m$ using the **frozen encoders** (one-hot sums = 1; column order equals the fitting bundle).
2. Load β atomically; assert $|β| = 1 + C_{\text{mcc}} + 2 + 5$ (**counts come from the frozen encoders/dictionaries pinned for this run**) and **exact column alignment** with $x_m$
3. Compute $\eta_m = β^\top x_m$ in binary64 (fixed-order Neumaier).
4. Compute $\pi_m$ with the **two-branch logistic (no clamp)**: assert finiteness and `0.0 ≤ pi ≤ 1.0`.

**Fail fast:** any non-finite $\eta$/$\pi$ or shape/order mismatch is a **hard abort**.

---

### V5. RNG replay & counter accounting (per row)

Let the label be the registry literal `substream_label="hurdle_bernoulli"`.

1. **Base counter reconstruction:** using `(seed, manifest_fingerprint, substream_label, merchant_id)` and the S0 keyed-substream primitive, recompute the **base counter** and assert it equals the envelope `rng_counter_before`.
2. **Budget from π:** set `draws_expected = 1` iff `0 < pi < 1`, else `0`.
3. **Budget identity:** compute `delta = u128(after) − u128(before)` and assert
   `delta == parse_u128(draws) == draws_expected`.
   Also assert `blocks == parse_u128(draws)` (specific to `rng_event_hurdle_bernoulli`) and `blocks ∈ {0,1}`.
4. **Lane policy:** assert `delta ∈ {0,1}`.
5. **Stochastic vs deterministic:**

   * If `draws_expected == 0`: assert `pi ∈ {0.0,1.0}` (binary64 *bit-exact*), `u == null`, `deterministic == true`, and `is_multi == (pi == 1.0)`.
   * If `draws_expected == 1`: regenerate **one** uniform from the keyed substream at `before` (low lane), map via **open-interval** `u01`, assert `0<u<1` and `(u < pi) == is_multi`.

**Trace reconciliation (cumulative):** For the **final** trace row per `(module, substream_label)`:
`draws_total == Σ parse_u128(draws)` (**required**; diagnostic; saturating `uint64`) and `blocks_total == Σ blocks` (normative; saturating `uint64`). *(No assertion on `u128(after) − u128(before)` for the final row.)*

> Naming: use `draws_expected` (from π), `blocks`/`draws` (from envelope), and `delta` for counter difference.

---

### V6. Cross-stream gating (branch purity)

Let $\mathcal{H}_1=\{m\mid \text{hurdle.is_multi}(m)=\text{true}\}$.
Build the **set of gated 1A RNG streams** **programmatically** from the dataset dictionary (`owner_subsegment == "1A"` **and** `gating.gated_by == "rng_event_hurdle_bernoulli"`); if the dictionary is legacy and lacks `gating`, **fall back** to the artefact-registry enumeration. For **every** row in any gated stream, assert `merchant_id ∈ 𝓗₁`. For merchants **not** in $𝓗_1$, assert **no** gated rows exist. *(Presence-based; no temporal ordering requirement.)*

---

### V7. Cardinality & uniqueness

* **Uniqueness:** exactly **one** hurdle record per `merchant_id` within `{seed, parameter_hash, run_id}`.
* **Coverage:** hurdle row count equals the ingress merchant count for the run.

---

**Bottom line:** This validator spec proves each hurdle event is schema-conformant, numerically correct, budget-conserving, partition-coherent, and correctly gates downstream streams—using **base-counter reconstruction**, **open-interval** replay, **cumulative per-substream trace totals** (grouped by (`module`, `substream_label`)), and registry-driven discovery.

---

### V8. Partition equality & path authority

For **every** hurdle row:

* **Path ↔ embed equality:** Embedded envelope keys
  `{seed, parameter_hash, run_id}` **must equal** the same keys in the dataset path.
  *(The hurdle dataset partitions by `{seed, parameter_hash, run_id}` only.)*
* **Literal checks (envelope):** `substream_label == "hurdle_bernoulli"` (registry literal) and `module` **MUST** equal `"1A.hurdle_sampler"`.
* **No fingerprint in path:** `manifest_fingerprint` is **embedded only** (lineage), never a path partition.

Mismatch is a lineage/partition failure.

---

### V9. Optional diagnostics (non-authoritative)

If the diagnostic table `…/hurdle_pi_probs/parameter_hash={parameter_hash}` exists, **do not** use it to verify decisions. At most, compare its `(eta, pi)` to recomputed values for sanity. Decisions are proven **only** by replaying S1.2 + S1.3.

---

### V10. Failure objects (forensics payload; exact keys)

Emit **one JSON object per failure** with envelope lineage and a precise code:

```json
{
  "state": "S1",
  "dataset_id": "rng_event_hurdle_bernoulli",
  "module": "1A.hurdle_sampler",
  "substream_label": "hurdle_bernoulli",
  "failure_code": "rng_counter_mismatch",
  "failure_class": "F4",

  "merchant_id": "184467440737095",
  "detail": {
    "before": { "hi": 42, "lo": 9876543210 },
    "after":  { "hi": 42, "lo": 9876543211 },
    "blocks": 1,
    "draws": "1",
    "expected_delta": "1",
    "trace_blocks_total": 0,
    "trace_draws_total": 0
  },

  "seed": 1234567890123456789,
  "parameter_hash": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
  "manifest_fingerprint": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
  "run_id": "0123456789abcdef0123456789abcdef",
  "ts_utc": 1752555123123456000
}
```

* `dataset_id` is the **registry id** (not a path).
* **Types per S0 failure schema:** `seed` is a JSON **integer**; `merchant_id` is a JSON **string** (or `null` when not applicable); `ts_utc` is a JSON **integer** = nanoseconds since Unix epoch (UTC). The `detail` payload for counter mismatches must include `before`, `after`, `blocks:uint64`, and `draws:"uint128-dec"`.
* `failure_code` maps **1:1** to S1.6 predicates.

---

### V11. End-of-run verdict & artifact

* If **any** check fails ⇒ **RUN INVALID**. Emit a `_FAILED.json` sentinel with aggregated stats and the list of failure objects; CI blocks the merge.
* If all checks pass ⇒ **RUN VALID**. Optionally record summary metrics (row counts, draw histograms, min/max/mean `pi`, `u` bounds). *(Downstream layers may re-check gating; S1.V is the first hard gate.)*

---

### CI integration (blocking gate)

#### CI-1. Job matrix

* All **changed parameter bundles** (distinct `parameter_hash`) and a **seed matrix** (e.g., 3 fixed seeds per PR).
* At least one **prior manifest fingerprint** (regression guard vs last known good).

#### CI-2. Steps

1. **Schema:** validate hurdle + trace rows against schema anchors; fail fast.
2. **Partition:** path ↔ embedded equality on `{seed, parameter_hash, run_id}`; then check envelope literals (`module`, `substream_label`); ensure **no fingerprint in path**.
3. **Replay:** Recompute `η=βᵀx` and `π=σ(η)` (two-branch logistic, no clamps). For rows with `0<π<1`, regenerate **one** uniform from the keyed substream at `rng_counter_before` (low-lane, open-interval `u01`) and assert the Bernoulli outcome matches the event record. Then reconcile cumulative per-substream **trace totals** and the **final trace row** as specified in **S1.V (Trace reconciliation)**.
4. **Gating:** enforce **presence-based** rule: gated streams exist **iff** `is_multi=true`.
5. **Cardinality/uniqueness:** exactly one hurdle row per merchant; counts match ingress.

#### CI-3. What blocks the merge

Any: schema violation, partition mismatch, counter/trace mismatch, non-finite numeric, deterministic-branch inconsistency, **gating presence failure**, or cardinality/uniqueness failure. (Codes per S1.6.)

#### CI-4. Provenance in the validation bundle

Record a compact summary in the fingerprint-scoped validation payload: counts, pass/fail, and optional lint artifacts (`SCHEMA_LINT.txt`, `DICTIONARY_LINT.txt`) for human inspection. *(Bundles are fingerprint-scoped; logs remain log-scoped.)*

---

### Reference validator outline (language-agnostic)

```text
INPUT:
  paths from registry; encoders; beta; run keys (seed, parameter_hash, run_id)

LOAD:
  H := read_jsonl(hurdle partition)
  T := read_jsonl(trace partition)
  S := discover_gated_streams_via_registry()

# 1) schema
assert_all_schema(H, "#/rng/events/hurdle_bernoulli")
assert_all_schema(T, "#/rng/core/rng_trace_log")

# 2) partition equality
for e in H: assert path_keys(e) == embedded_keys(e)   # {seed, parameter_hash, run_id}
assert all(e.module == "1A.hurdle_sampler" and e.substream_label == "hurdle_bernoulli" for e in H)

# 3) recompute (η, π) and budget
beta := load_beta_once()
for e in H:
  x_m := rebuild_design(m)                 # frozen encoders; one-hot sums; column order
  eta, pi := fixed_order_dot_and_safe_logistic(x_m, beta)
  draws := 1 if 0 < pi < 1 else 0

  # 4) base counter + counters & trace
  before := reconstruct_base_counter(seed, manifest_fingerprint, "hurdle_bernoulli", m)
  assert e.rng_counter_before == before
  delta := u128(e.after) - u128(e.before)
  assert delta == parse_u128(e.draws) == draws
  assert e.blocks == parse_u128(e.draws)

  # 5) branch checks
  if draws == 0:
     assert (pi == 0.0 and !e.is_multi) || (pi == 1.0 and e.is_multi)
     assert e.deterministic and e.u == null
  else:
     u := regenerate_u01(seed, before)     # (0,1), low-lane policy
     assert 0.0 < u and u < 1.0
     assert (u < pi) == e.is_multi

# 6) trace reconciliation (final per (module, substream_label))
for each key in final_rows(T):
  assert key.draws_total == sum(parse_u128(e.draws) for e in H if e.module==key.module and e.substream_label==key.substream_label)   # required; diagnostic; saturating uint64
  assert key.blocks_total == sum(e.blocks for e in H if e.module==key.module and e.substream_label==key.substream_label)             # normative; saturating uint64
  # no assertion relating (after−before) on the final row to cumulative totals

# 7) gating (presence-based)
H1 := { m | H[m].is_multi == true }
for each row in each gated stream s ∈ S:
  assert row.merchant_id in H1
for each m ∉ H1:
  assert no rows exist in any s ∈ S

# 8) uniqueness & cardinality
assert |H| == |ingress_merchant_ids|
assert unique(H.merchant_id)
```

---

**Bottom line:** This chunk locks the **partition/lineage checks**, the **forensics error object**, and the **CI gate** to the exact S1 contracts: complete envelope, base-counter reconstruction, budget identity + cumulative trace, presence-based gating via the registry, and strict uniqueness/cardinality—so any drift trips a named, actionable failure.

---


[S1-END VERBATIM]


---

# S2 — Expanded
<a id="S2.EXP"></a>
<!-- SOURCE: /s3/states/state.1A.s2.expanded.txt  *  VERSION: v0.0.0 -->

[S2-BEGIN VERBATIM]

## S2.1 — Scope, Preconditions, and Inputs (implementation-ready)

### 1) Scope & intent

S2 generates the **total pre-split multi-site outlet count** $N_m$ for merchants that passed the hurdle as **multi-site** in S1. It is a *stochastic* state (NB via Poisson–Gamma), but **S2.1 itself** is deterministic: it gates who enters S2 and assembles the numeric inputs needed for S2.2–S2.5. Only merchants with `is_multi=1` (per S1’s authoritative event) may enter S2; single-site merchants bypass S2 entirely.

---

### 2) Entry preconditions (MUST)

For a merchant $m$ to enter S2:

1. **Hurdle provenance.** There exists exactly one S1 event record under
   `logs/rng/events/hurdle_bernoulli/…` with the merchant key and payload containing `is_multi=true`. This is the canonical gate from S1. **Absence** or `is_multi=false` ⇒ S2 MUST NOT run for $m$. (Branch purity.)
2. **Branch purity guarantee.** For `is_multi=0`, **no S2 events** may exist for $m$ in any stream; any presence constitutes a structural failure detected by validation.
3. **Lineage anchors available.** The run exposes `run_id`, `seed`, `parameter_hash`, and `manifest_fingerprint` (used in RNG envelopes and joins). S2.1 **does not** recompute any lineage keys.

**Abort codes (preflight):**

* `ERR_S2_ENTRY_NOT_MULTI` — hurdle present but `is_multi=false`.
* `ERR_S2_ENTRY_MISSING_HURDLE` — no S1 hurdle record for $m$.
* On either, S2 is **skipped** for $m$ (no S2 emission); the global validator will also enforce branch purity.

---

### 3) Mathematical inputs (MUST)

For each $m$ that satisfies the preconditions:

#### 3.1 Design vectors (from S0/S1 encoders; column order frozen)

Form the **fixed** design vectors using the frozen one-hot encoders and column dictionaries established in S0/S1 (no re-definition here):

$$
\boxed{x^{(\mu)}_m=\big[1,\ \Phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \Phi_{\mathrm{ch}}(\texttt{channel\_sym}_m)\big]^\top},\quad
\boxed{x^{(\phi)}_m=\big[1,\ \Phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \Phi_{\mathrm{ch}}(\texttt{channel\_sym}_m),\ \ln g_c\big]^\top}.
$$

* $g_c$ is the GDP-per-capita scalar for the **home country** $c=\texttt{home_country_iso}_m$; the GDP term is **excluded** from the mean and **included** in the dispersion. Its sign and magnitude are exactly those encoded in the governed $\beta_\phi$ (§3.2).

**Domain & shapes:** $\Phi_{\mathrm{mcc}},\ \Phi_{\mathrm{ch}}$ are fixed-length **one-hot blocks** (sum to 1; column order frozen by the fitting bundle). $g_c>0$ so that $\ln g_c$ is defined. *(Here and below, $\ln$ denotes the natural log.)*

**FKs (deterministic):**
`mcc_m` and `channel_sym_m` come from ingress/S0 feature prep; $g_c$ is keyed by `home_country_iso`. (S0 established these and the parameter lineage via `parameter_hash`.)

#### 3.2 Coefficient vectors (governed artefacts)

Load the **approved** coefficient vectors $\beta_\mu$ and $\beta_\phi$ from governed artefacts referenced by the run’s `parameter_hash`. Concretely: NB-mean coefficients from `hurdle_coefficients.yaml` (**key:** `beta_mu`), and NB-dispersion coefficients from `nb_dispersion_coefficients.yaml` (**key:** `beta_phi`). These are the only sources used to compute $\mu_m,\phi_m$ in S2.2.

#### 3.3 RNG discipline & authoritative schemas (for later S2 steps)

Pin the RNG/stream contracts that S2.3–S2.5 will rely on:

* **RNG:** Philox $2\times 64$-10 with the **shared RNG envelope** (`run_id`, `seed`, `parameter_hash`, `manifest_fingerprint`, `substream_label`, counters). Open-interval uniforms $U(0,1)$ and normals follow S0 primitives.
  The **full envelope** (including `module`, `substream_label`, `rng_counter_before_*`, `rng_counter_after_*`, `draws` as decimal u128, and `blocks` as u64) is governed by the layer schema and is the one S2.3–S2.5 will use when writing events.
  For S2 streams in 1A, the `module` literal is **registry-closed per stream** (data dictionary): `gamma_component` → "1A.nb_and_dirichlet_sampler", `poisson_component` → "1A.nb_poisson_component", `nb_final` → "1A.nb_sampler".

* **Event streams (authoritative, JSONL):**
  `gamma_component` (context=`"nb"`), `poisson_component` (context=`"nb"`), and `nb_final` — each with schema refs in `schemas.layer1.yaml#/rng/events/...` and paths partitioned by `{seed, parameter_hash, run_id}`. These will be **written later** (S2.3–S2.5), not in S2.1.

---

### 4) Numeric evaluation requirements (MUST)

* **Policy:** Numeric policy is **exactly S0’s** (binary64, RNE, FMA-OFF, fixed-order Neumaier dot; deterministic libm surface).
* **Sanity guards:** After exponentiation in S2.2, $\mu_m>0,\ \phi_m>0$. If either is non-finite or $\le 0$, abort for $m$ with `ERR_S2_NUMERIC_INVALID`. (S2.2 will restate this as part of the link spec; S2.1 ensures the inputs exist to compute them.)

---

### 5) Pseudocode (normative preflight & assembly)

```pseudo
# Preflight gate + input assembly; emits no RNG events (draws=0)

function s2_1_prepare_inputs(m):
    # 1) Entry gate from S1
    hb := read_hurdle_event(m)                     # select within {seed, parameter_hash, run_id}, then merchant_id=m
                                                   # and verify the in-row envelope `manifest_fingerprint`
                                                   # equals the current run's `manifest_fingerprint` (explicit lineage check).
    if hb is None:           raise ERR_S2_ENTRY_MISSING_HURDLE
    if hb.is_multi != true:  raise ERR_S2_ENTRY_NOT_MULTI   # branch purity

    # 2) Load deterministic features
    c  := ingress.home_country_iso[m]
    g  := gdp_per_capita[c]                        # > 0 (checked when loaded in S0)
    xm := [1, enc_mcc(ingress.mcc[m]), enc_ch(ingress.channel_sym[m])]   # channel_sym ∈ {CP,CNP}
    xk := [1, enc_mcc(ingress.mcc[m]), enc_ch(ingress.channel_sym[m]), ln(g)]  # ln = natural log

    # 3) Load governed coefficients (parameter-scoped by parameter_hash)
    beta_mu  := artefacts.hurdle_coefficients.beta_mu           # from hurdle_coefficients.yaml
    beta_phi := artefacts.nb_dispersion_coefficients.beta_phi   # from nb_dispersion_coefficients.yaml

    # 4) Produce the S2 context (consumed by S2.2+)
    return NBContext{
        merchant_id: m,
        x_mu: xm, x_phi: xk,
        beta_mu: beta_mu, beta_phi: beta_phi,
        lineage: {seed, parameter_hash, manifest_fingerprint, run_id}
    }
```

**Emissions:** S2.1 emits **no** event records and consumes **no** RNG draws (draws=0).

---

### 6) Invariants & MUST-NOTs (checked locally, and again by the validator)

* **I-S2.1-A (Entry determinism).** S2 only runs for merchants with an S1 hurdle record where `is_multi=true`. Any S2 event for `is_multi=false` is a **structural failure**.
* **I-S2.1-B (Inputs completeness).** $x_m^{(\mu)},\ x_m^{(\phi)},\ \beta_\mu,\ \beta_\phi$ MUST all be available (encoders used to form $x$ are the frozen S0/S1 one-hots). Missing → abort for $m$ with `ERR_S2_INPUTS_INCOMPLETE`. (The expanded doc’s validator also enforces this via schema/path checks downstream.)
* **I-S2.1-C (No persistence yet).** S2.1 MUST NOT write any of the S2 event streams nor any sidecar tables; persistence happens only in S2.3–S2.5 (events) and the state boundary in S2.9.

---

### 7) Errors & abort semantics (merchant-scoped)

* `ERR_S2_ENTRY_MISSING_HURDLE` — no S1 hurdle record for $m$.
* `ERR_S2_ENTRY_NOT_MULTI` — S1 shows `is_multi=false`.
* `ERR_S2_INPUTS_INCOMPLETE:{key}` — missing design feature or coefficient.
* `ERR_S2_NUMERIC_INVALID` — later, if $\mu$ or $\phi$ evaluate non-finite/≤0 (S2.2).
  **Effect:** For any of the above, **skip S2** for $m$ (no S2 events written). The run-level validator will additionally fail branch-purity or coverage if contradictions appear.

---

### 8) Hand-off contract to S2.2+

If S2.1 succeeds for $m$, the engine must expose an **NB context** containing:

$$
(x^{(\mu)}_m,\ x^{(\phi)}_m,\ \beta_\mu,\ \beta_\phi,\ \text{seed},\ \text{parameter_hash},\ \text{manifest_fingerprint},\ \text{run_id})
$$

for use in S2.2 (NB link evaluation), S2.3 (Gamma/Poisson samplers), and S2.4 (rejection loop). **No additional mutable state** may be consulted when sampling.

---

### 9) Conformance spot-checks (writer & validator)

* **Gate correctness:** pick a known single-site merchant (`is_multi=0`); confirm **no** S2 streams contain its key. (Structural fail otherwise.)
* **Inputs reproducibility:** recompute $x^{(\mu)},x^{(\phi)}$ for a sample of merchants and verify byte-exact equality with the values used to compute `nb_final.mu` / `nb_final.dispersion_k` later.
* **Lineage presence:** ensure the S2 context carries `(seed, parameter_hash, manifest_fingerprint, run_id)` so later events can include a consistent envelope.

> **S2 in 6 steps (informative overview)**  
> 1) Compute links: $\mu=\exp(\beta_\mu^\top x^{(\mu)}),\ \phi=\exp(\beta_\phi^\top x^{(\phi)})$. *(§S2.2)*
> 2) Start attempt loop: draw $G\sim\Gamma(\phi,1)$, set $\lambda=(\mu/\phi)\,G$. *(§S2.3)*
> 3) Draw $K\sim\mathrm{Poisson}(\lambda)$; accept iff $K\ge 2$. *(§S2.3)*
> 4) On reject, repeat step 2; count rejections $r$. *(§S2.4)*
> 5) On acceptance, **emit** non-consuming `nb_final` with `n_outlets = K` and `nb_rejections = r`. *(§S2.5)*
> 6) **Hand off** $(N=K,r)$ in-memory to the next state (no egress here). *(§S2.9)*
> *(See §S2.2, §S2.3–S2.5, and §S2.9 for the normative details.)*

## S2.2 — NB2 parameterisation (links, domains, guards)

### 1) Scope & intent

Compute the **Negative-Binomial (NB2)** parameters for merchant $m$ that passed S2.1 preflight:

$$
\boxed{\ \mu_m=\exp(\beta_\mu^\top x^{(\mu)}_m)\;>\;0\ },\qquad
\boxed{\ \phi_m=\exp(\beta_\phi^\top x^{(\phi)}_m)\;>\;0\ }.
$$

This step is **deterministic** (no RNG), yields the **mean** $\mu_m$ and **dispersion** $\phi_m$ used by S2.3–S2.5, and must be **binary64-stable** and auditable. The NB2 moments are $\mathbb{E}[N_m]=\mu_m$ and $\operatorname{Var}[N_m]=\mu_m+\mu_m^2/\phi_m$. (The $r,p$ parametrisation $r=\phi_m,\ p=\phi_m/(\phi_m+\mu_m)$ is derivational only, not persisted.)

---

### 2) Inputs (MUST)

Provided by **S2.1** and artefacts keyed by `parameter_hash`:

* **Design vectors** (from S0/S2.1):

  $$
  x^{(\mu)}_m=\big[1,\ \Phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \Phi_{\mathrm{ch}}(\texttt{channel\_sym}_m)\big]^\top,\quad
  x^{(\phi)}_m=\big[1,\ \Phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \Phi_{\mathrm{ch}}(\texttt{channel\_sym}_m),\ \ln g_c\big]^\top,
  $$

  where $g_c > 0$ is the GDP-per-capita scalar for the home ISO $c$. (NB mean **excludes** GDP; dispersion **includes** $\ln g_c$.)
  *Notation:* $\Phi_{\mathrm{mcc}}(\cdot)$ and $\Phi_{\mathrm{ch}}(\cdot)$ denote **frozen one-hot encoder functions** from S0/S1; they are **not** the NB dispersion $\phi_m$ used below.
* **Coefficient vectors:** $\beta_\mu,\ \beta_\phi$ from governed artefacts **keyed by `parameter_hash`**:
  * `hurdle_coefficients.yaml` → key **`beta_mu`** (maps to $\beta_\mu$),
  * `nb_dispersion_coefficients.yaml` → key **`beta_phi`** (maps to $\beta_\phi$).
* **Lineage:** `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id` (for later event joins and partition equality).

**Preconditions (MUST):**

1. All elements of $x^{(\mu)}_m$, $x^{(\phi)}_m$, $\beta_\mu$, $\beta_\phi$ are **finite** binary64 numbers.
2. $g_c > 0$ so that $\ln g_c$ is defined.  (Here and below, $\ln$ denotes the natural log.)
3. Vector lengths match (inner products defined).

---

### 3) Algorithm (normative, deterministic)

Let $\eta^{(\mu)}_m=\beta_\mu^\top x^{(\mu)}_m$ and $\eta^{(\phi)}_m=\beta_\phi^\top x^{(\phi)}_m$.

1. **Evaluate linear predictors** in **binary64** with **FMA disabled** and **fixed-order, serial Neumaier accumulation** for dot products. Do **not** reorder summands or use non-deterministic BLAS paths; this mirrors S0’s numeric contract (binary64, RNE, FMA-OFF; deterministic libm).
2. **Exponentiate** safely in binary64:

   $$
   \mu_m=\exp\!\big(\eta^{(\mu)}_m\big),\qquad \phi_m=\exp\!\big(\eta^{(\phi)}_m\big).
   $$
3. **Numeric guards (MUST):** if either exponentiation yields **non-finite** (NaN/±Inf) or $\le 0$, raise `ERR_S2_NUMERIC_INVALID` (merchant-scoped abort). No clamping; failure is explicit.

**Notes.**
• This step **does not** create or consume RNG draws and emits **no** S2 events. $\mu_m,\phi_m$ are *handed forward* in-memory; they will be echoed byte-exactly later in `nb_final` (see §6).

---

### 4) Output contract (to S2.3–S2.5)

On success, expose the immutable NB2 context:

$$
\big(m,\ x^{(\mu)}_m,\ x^{(\phi)}_m,\ \beta_\mu,\ \beta_\phi,\ \mu_m,\ \phi_m,\ \text{seed},\ \text{parameter_hash},\ \text{manifest_fingerprint},\ \text{run_id}\big).
$$

S2.3 (Gamma/Poisson attempt), S2.4 (rejection rule), and S2.5 (finalisation) **must** use **exactly** these $\mu_m,\phi_m$ values (binary64 bit-pattern) without re-computation from different inputs.

---

### 5) Invariants (MUST)

* **I-NB2-POS:** $\mu_m > 0$ and $\phi_m > 0$.
* **I-NB2-B64:** $\mu_m,\phi_m$ are representable as IEEE-754 binary64 and remain unchanged when round-tripped through the eventual JSONL `nb_final` record. (Validator re-parses numbers and compares the binary64 bit pattern.)
* **I-NB2-SER (binding):** Producers **MUST** serialize `mu` and `dispersion_k` using the **shortest round-trip decimal for binary64** (same rule as S1; L0 helper `f64_to_json_shortest`), so that parsing yields the **exact** original bit pattern.
* **I-NB2-ECHO:** The `nb_final` payload **must echo** these exact values in fields `mu` and `dispersion_k`. Any mismatch is a structural failure at validation.

* **Numeric examples (formatting only):** Example numbers use the **shortest binary64 round-trippable decimals**; consumers parse as binary64.
---

### 6) Downstream echo (binding reference)

When S2.5 emits the single `nb_final` event for $m$, it **MUST** include:

```
{ mu: <binary64>, dispersion_k: <binary64>, n_outlets: N_m, nb_rejections: R_m, ... }
```

with `mu == μ_m` and `dispersion_k == φ_m` as produced here. Here **$R_m$** denotes the integer **rejection tally** (number of rejected attempts), distinct from the dispersion/shape $\phi_m$. (Event schema: `schemas.layer1.yaml#/rng/events/nb_final`; partitioning `{seed, parameter_hash, run_id}` per dictionary.)

---

### 7) Errors & abort semantics (merchant-scoped)

* `ERR_S2_NUMERIC_INVALID` — any of: non-finite $\eta$; non-finite or $\le 0$ $\mu_m$ or $\phi_m$; missing/mismatched vector sizes.
  **Effect:** skip S2 for $m$ (no S2 events written); validator also checks coverage so no `nb_final` may appear for this merchant.

---

### 8) Reference pseudocode (deterministic; no RNG; no emissions)

```pseudo
function s2_2_eval_links(ctx: NBContext) -> NBContext:
    # Inputs from S2.1
    xm   := ctx.x_mu          # vector
    xk   := ctx.x_phi         # vector includes ln(gdp_pc)
    bmu  := ctx.beta_mu       # vector
    bphi := ctx.beta_phi      # vector

    # 1) Linear predictors in binary64 (fixed-order Neumaier; FMA disabled)
    eta_mu  := dot64_no_fma(bmu,  xm)      # deterministic Neumaier reduction
    eta_phi := dot64_no_fma(bphi, xk)      # deterministic Neumaier reduction

    # 2) Exponentiate safely (no clamping on overflow)
    mu  := exp64(eta_mu)
    phi := exp64(eta_phi)

    # 3) Guards
    if not isfinite(mu) or mu <= 0:   raise ERR_S2_NUMERIC_INVALID
    if not isfinite(phi) or phi <= 0: raise ERR_S2_NUMERIC_INVALID

    # 4) Hand-off; no RNG draws, no event persistence here
    ctx.mu  = mu
    ctx.phi = phi
    return ctx
```

---

### 9) Conformance tests (KATs)

**Positive (round-trip & echo).**

1. Select $m$, compute $\mu_m,\phi_m$ with high-precision reference; confirm the engine’s binary64 exactly matches and later `nb_final.mu`/`dispersion_k` numerically round-trip to the same binary64.

**Negative (guard trips).**

1. Force $\eta^{(\mu)}$ above \~709.78 (binary64 overflow threshold for `exp`) → `ERR_S2_NUMERIC_INVALID`.
2. Force $\eta^{(\phi)}\to -\infty$ via extreme negative coefficients → $\phi\to 0^+$ underflow; if non-finite or $\le 0$, error.
3. Remove GDP $g_c$ (so $\ln g_c$ undefined) or set $g_c\le 0$ in features → `ERR_S2_NUMERIC_INVALID`.

**Structural.**

1. Deliberately change coefficients between S2.2 and S2.5 echo → validator should fail `I-NB2-ECHO`.

---

### 10) Complexity

* Time: $O(d_\mu + d_\phi)$ per merchant (vector dot products).
* Memory: $O(1)$.
* This step is embarrassingly parallel across merchants.

---

## S2.3 — Poisson–Gamma construction (one attempt), samplers, substreams

### 1) Scope & intent

Given deterministic $(\mu_m,\phi_m)$ from **S2.2**, perform **one attempt** of the NB mixture:

$$
G\sim\mathrm{Gamma}(\alpha{=}\phi_m,1),\quad \lambda=(\mu_m/\phi_m)\,G,\quad K\sim\mathrm{Poisson}(\lambda).
$$

Emit exactly **one** `gamma_component` and **one** `poisson_component` event (context=`"nb"`) for this attempt, with **authoritative RNG envelope** and draw accounting.
**Envelope must include:** `seed`, `parameter_hash`, `run_id`, `manifest_fingerprint`, `module`, `substream_label`, `ts_utc`, `rng_counter_before_hi/lo`, `rng_counter_after_hi/lo`, and per-event `blocks` (u64) and `draws` (decimal u128). Acceptance of the attempt is decided in **S2.4** (accept if $K\ge2$).

**Index semantics:** For `gamma_component`, set `index=0` for the NB mixture; for Dirichlet (elsewhere in 1A) `index=i≥1` denotes the i-th category component.

---

### 2) Mathematical foundation (normative)

**Theorem (composition).** If $G\sim\Gamma(\alpha{=}\phi_m,\text{scale}=1)$ and $K\mid G\sim\mathrm{Poisson}(\lambda{=}\tfrac{\mu_m}{\phi_m}G)$, then marginally $K\sim\mathrm{NB2}(\mu_m,\phi_m)$ with $\mathbb{E}[K]=\mu_m$, $\mathrm{Var}(K)=\mu_m+\mu_m^2/\phi_m$. (Parametrisation used in S2.2.)

---

### 3) Samplers (normative, pinned)

#### 3.1 Gamma $\Gamma(\alpha,1)$ — Marsaglia–Tsang MT1998

Use the **MT1998** algorithm with **open-interval uniforms** (S0.3.4) and **Box–Muller** normals (S0.3.5). **No normal caching**. Draw budgets are **variable per attempt** (actual-use; see counters).

* **Case $\alpha\ge 1$**
  Let $d=\alpha-\frac{1}{3}$, $c=(9d)^{-1/2}$. Repeat:

  1. $Z\sim\mathcal{N}(0,1)$ (Box–Muller → **2 uniforms**).
  2. $V=(1+cZ)^3$; if $V\le0$ reject.
  3. $U\sim U(0,1)$ (**1 uniform**).
  4. Accept if $\ln U < \tfrac{1}{2}Z^2 + d - dV + d\ln V$; return $G=dV$.
     Uniform consumption (one Gamma variate): **2×J + A**, where **J≥1** is the number of MT98 iterations and **A** is the count of iterations with $V>0$ (only those iterations draw the accept-$U$).
     If $0<\alpha<1$, add **+1** uniform for the power step $U^{1/\alpha}$.

* **Case $0 < \alpha < 1$**

  1. Draw $G'\sim\Gamma(\alpha+1,1)$ via the $\alpha\ge1$ branch (variable MT98 iterations; 2 uniforms per iteration; accept-$U$ only when $V>0$).
  2. Draw $U\sim U(0,1)$ (**1 uniform**).
  3. Return $G = G'\, U^{1/\alpha}$.
     **Additional uniform:** **+1 per variate** for the power step U^{1/α}

* **Eventing (Gamma):** emit **one** `gamma_component` with `context="nb"`; payload includes `alpha=φ_m` and `gamma_value=G`.
* **Draw accounting (per event):** for attempt $t$, $\mathrm{draws}_\gamma(t)=2J_t + A_t + \mathbf{1}[\phi_m<1]$, where $J_t\ge1$ is the number of MT1998 iterations and $A_t$ is the count of iterations with $V>0$ (only those iterations draw the accept-$U$).

#### 3.2 Poisson $\mathrm{Poisson}(\lambda)$ — S0.3.7 (deterministic regimes)

Use **S0.3.7** regime split: **inversion** for $\lambda<10$; **PTRS** (Hörmann transformed-rejection) for $\lambda\ge 10$. Constants in PTRS are **normative**; they are *not* tunables. Uniform consumption is **variable** and is measured by the envelope counters. Emit `poisson_component` with `context="nb"`.

* **Inversion ($\lambda<10$)**: multiplicative $p$ until $p\le e^{-\lambda}$.
* **PTRS ($\lambda\ge10$)**: use $b=0.931+2.53\sqrt\lambda$, $a=-0.059+0.02483\,b$, $\text{inv}\alpha=1.1239+1.1328/(b-3.4)$, $v_r=0.9277-3.6224/(b-2)$; draw $u,v\sim U(0,1)$; apply the squeeze/acceptance tests from S0.3.7.
* **Uniforms:** **variable** — each PTRS **iteration** uses 2 uniforms; the number of iterations is geometric; total per event is measured by envelope counters.
* **Logging:** `poisson_component` with `context="nb"`.

---

### 4) RNG substreams & labels (MUST)

* **Module (registry-closed per stream):**
  * `gamma_component`  → `module="1A.nb_and_dirichlet_sampler"`
  * `poisson_component` → `module="1A.nb_poisson_component"`
  * `nb_final` → `module="1A.nb_sampler"`
* **NB substreams (disjoint from ZTP):**
  * Gamma: `substream_label="gamma_nb"`
  * Poisson: `substream_label="poisson_nb"`
* **Order per attempt:** emit exactly two component events: `gamma_component` → `poisson_component`.
Counters advance deterministically within each `(merchant, substream_label)` stream; there is **no cross-label counter chaining**. All uniforms use S0.3.4 `u01`; all normals use Box–Muller.

---

### 5) Construction (one attempt) & event emission (normative)

Given merchant $m$ with $(\mu_m,\phi_m)$ from S2.2:

* **Numeric examples (formatting only):** Example numbers use the **shortest binary64 round-trippable decimals**; consumers parse as binary64.

1. **Gamma step (context=`"nb"`)**
   Draw $G\sim\Gamma(\alpha{=}\phi_m,1)$ via **3.1** on `substream_label="gamma_nb"`.
   Emit:

   ```json
   {
          "seed": "...",
          "parameter_hash": "...",
          "run_id": "...",
          "manifest_fingerprint": "...",
          "ts_utc": "2025-01-01T00:00:00.000000Z",
          "module": "1A.nb_and_dirichlet_sampler",
          "substream_label": "gamma_nb",
          "rng_counter_before_hi": "...",
          "rng_counter_before_lo": "...",
          "rng_counter_after_hi":  "...",
          "rng_counter_after_lo":  "...",
          "blocks": 1,
          "draws": "2",

          "merchant_id": "<m>",
          "index": 0,
          "context": "nb",
          "alpha": <phi_m as binary64>,
          "gamma_value": <G as binary64>
   }
   ```

   Schema (authoritative): `schemas.layer1.yaml#/rng/events/gamma_component`. **Partition:** `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/...`. **Draws:** per §3.1 above.

2. **Poisson step (context=`"nb"`)**
   Compute $\lambda=\frac{\mu_m}{\phi_m}\,G$ in binary64. Draw $K\sim\mathrm{Poisson}(\lambda)$ via **3.2** on `substream_label="poisson_nb"`.
   Emit:

   ```json
   {
          "seed": "...",
          "parameter_hash": "...",
          "run_id": "...",
          "manifest_fingerprint": "...",
          "ts_utc": "2025-01-01T00:00:00.000000Z",
          "module": "1A.nb_poisson_component",
          "substream_label": "poisson_nb",
          "rng_counter_before_hi": "...",
          "rng_counter_before_lo": "...",
          "rng_counter_after_hi":  "...",
          "rng_counter_after_lo":  "...",
          "blocks": 1,
          "draws": "1",

          "merchant_id": "<m>",
          "context": "nb",
          "lambda": <lambda as binary64>,
          "k": <K as int64>
   }
   ```

   Schema (authoritative): `schemas.layer1.yaml#/rng/events/poisson_component`. **Partition:** `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/...`. **Draws:** variable; reconciled by envelope counters.

> **Note (types).** All floating-point payloads are **IEEE-754 binary64** and must round-trip exactly. Integers are signed 64-bit (`k≥0`).

---

### 6) Draw accounting & reconciliation (MUST)

**Trace rule (cumulative).** Persist one **trace** row per `(module, substream_label)` carrying
`blocks_total = Σ blocks_event` and `draws_total = Σ draws_event`. The stream’s 128-bit
counter span **must** satisfy `u128(last_after) − u128(first_before) = blocks_total`.
There is **no** identity deriving `draws` (or `draws_total`) from counter deltas.
Validators compare `draws_total` to the sampler budgets (Gamma/Poisson as specified),
and verify the counter-span equality for `blocks_total`. `nb_final` is non-consuming.
---

### 7) Determinism & ordering (MUST)

* **Emission cardinality:** Emit exactly one `gamma_component` (with `substream_label="gamma_nb"`, `context="nb"`) then one `poisson_component` (with `substream_label="poisson_nb"`, `context="nb"`) per attempt for the merchant (no parallelization per merchant). Both events must carry the same lineage and the authoritative RNG envelope (before/after counters; `draws` computed).
* **Label order:** Gamma **precedes** Poisson; ordering is determined solely by each event’s **envelope counter interval** (`rng_counter_before_*` → `rng_counter_after_*`). There is **no `attempt` field in the payload** for these streams.
* **Bit-replay:** For fixed $(x_m^{(\mu)},x_m^{(\phi)},\beta_\mu,\beta_\phi,\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the entire $(G_t,K_t)$ attempt stream is **bit-identical** across replays. (Counter-based Philox + fixed labels + variable, actual-use budgets)
* (Reminder) NB substream **labels are closed**: `gamma_nb` / `poisson_nb` with `context="nb"`.
* Producers are registry-closed per stream (see §4):
  - `gamma_component → "1A.nb_and_dirichlet_sampler"`,
  - `poisson_component → "1A.nb_poisson_component"`,
  - `nb_final → "1A.nb_sampler"`.
---

### 8) Preconditions & guards (MUST)

* Inputs $\mu_m>0,\ \phi_m>0$ (from S2.2).
* Compute $\lambda$ in binary64; if $\lambda$ is **non-finite** or $\le0$ due to numeric error, raise `ERR_S2_NUMERIC_INVALID` (merchant-scoped abort of S2). (This is rare given $\mu,\phi>0$, but it is pinned.)

---

### 9) Reference pseudocode (one attempt; emissions included)

```pseudo
function s2_3_attempt_once(ctx: NBContext, t: int) -> AttemptRecord:
    # Inputs
    mu  := ctx.mu      # >0, binary64
    phi := ctx.phi     # >0, binary64

    # --- Gamma step on substream "gamma_nb"
    G := gamma_mt1998(alpha=phi)              # uses S0.3.4/5; variable attempts internally
    # --- Compute λ and guard numeric validity BEFORE any emission
    lambda := (mu/phi) * G
    if (!isfinite(lambda) or lambda <= 0.0):
        raise ERR_S2_NUMERIC_INVALID          # no S2 events should exist for this merchant
        return

    # --- Now emit gamma (envelope from the substream at this point)
    emit_gamma_component(
        merchant_id=ctx.merchant_id,
        context="nb", index=0, alpha=phi, gamma_value=G,
        envelope=substream_envelope(module="1A.nb_and_dirichlet_sampler", label="gamma_nb")
    )

    # --- Poisson step on substream "poisson_nb"
    lambda := (mu / phi) * G                  # binary64
    if not isfinite(lambda) or lambda <= 0: raise ERR_S2_NUMERIC_INVALID
    K := poisson_s0_3_7(lambda)               # regimes per S0.3.7
    emit_poisson_component(
        merchant_id=ctx.merchant_id,
        context="nb", lambda=lambda, k=K,
        envelope=substream_envelope(module="1A.nb_poisson_component", label="poisson_nb")
    )

    return AttemptRecord{G: G, lambda: lambda, K: K}
```

* `gamma_mt1998` implements §3.1 including α<1 power-step and **draw budgets**.
* `poisson_s0_3_7` implements §3.2 (inversion / PTRS; **normative constants**).
* `emit_*` attach the **rng envelope** with `blocks = u128(after)−u128(before)` and`draws` equal to the **actual uniforms consumed** by that event (decimal uint128 string).

---

### 10) Errors & abort semantics (merchant-scoped)

* `ERR_S2_NUMERIC_INVALID` — non-finite or $\le0$ $\lambda$.
  **Effect:** abort S2 for $m$; **no further** S2 events are emitted for that merchant (validator will also enforce coverage).

---

### 11) Conformance tests (KATs)

* **Gamma budgets.** Let `attempts` be the number of Gamma variates emitted for the merchant. For $\phi\ge1$, assert the **sum of `draws` across all `gamma_component` events for the merchant** equals $\sum_{t=1}^{\text{attempts}} \big(2 J_t + A_t\big)$; for $0<\phi<1$, assert the **sum of `draws` across all `gamma_component` events** equals $\sum_{t=1}^{\text{attempts}} \big(2 J_t + A_t + 1\big)$.
  Here $J_t$ is the number of Box–Muller iterations for attempt $t$, and $A_t$ is the number of those iterations with $V>0$ (i.e., the iterations that consume the accept-$U$). The validator recomputes $J_t$ and $A_t$ by bit-replay and compares them to the **sum of per-event `draws`** reported by `gamma_component`.
* **Poisson regimes.** Choose $\lambda=5$ (inversion) and $\lambda=50$ (PTRS); confirm `poisson_component` bit-replays and that the counters advance with variable consumption.
* **Ordering.** Verify each attempt produces **two** events in the `gamma`→`poisson` order for the same merchant and that `nb_final` (later) appears once at acceptance.

---

### 12) Complexity

* Gamma MT1998: expected constant iterations (depends on $\alpha$); per-attempt uniforms are **variable**: Box–Muller uses 2 uniforms per iteration; accept-$U$ is drawn only when $V>0$; add **+1** if $0<\alpha<1$.
* Poisson S0.3.7: inversion costs $\approx \lambda$ uniforms; PTRS has constant expected attempts but **variable** uniform consumption; budgets are measured by envelope counters.
* One attempt is $O(1)$ expected time and $O(1)$ memory.

---

### 13) Interactions (binding where stated)

* Draw budgets and counters must follow **S0.3.6**; `nb_final` (S2.5) will be **non-consuming** (`draws=0`).
* The **rejection rule** ($K\in\{0,1\}\Rightarrow$ resample) and corridor monitoring are specified in **S2.4** (do not duplicate here).

---

## S2.4 — Rejection rule (enforce multi-site $N\ge 2$)

### 1) Scope & intent

Turn the stream of NB mixture **attempts** from S2.3 into a single **accepted** domestic outlet count

$$
\boxed{\,N_m\in\{2,3,\dots\}\,}
$$

by **rejecting** any attempt whose Poisson draw is $K\in\{0,1\}$. Count deterministic retries

$$
\boxed{\,r_m\in\mathbb{N}_0\ \text{ = #rejections before acceptance}\,}.
$$

S2.4 **emits no events**; it controls acceptance and the loop. Finalisation (`nb_final`) is S2.5. Corridor checks on rejection behaviour are enforced by the validator (not here).

---

### 2) Inputs (MUST)

From prior substates:

* **Deterministic parameters:** $(\mu_m,\phi_m)$ from S2.2, already validated $(>0)$.
* **Attempt generator:** S2.3 provides an i.i.d. attempt stream; each attempt yields $(G_t,\lambda_t,K_t)$ and **logs exactly one** `gamma_component` (context=`"nb"`) **then** **one** `poisson_component` (context=`"nb"`), with the authoritative RNG envelope. S2.4 itself consumes **no RNG**.
* **Lineage envelope:** `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`, `substream_label`, counters (for coverage checks later).

**Preconditions (MUST):** $\mu_m>0$, $\phi_m>0$; S2.3 must adhere to per-attempt cardinality (1 Gamma + 1 Poisson).

---

### 3) Acceptance process (formal, normative)

Let attempts be indexed $t=0,1,2,\dots$. For each $t$:

$$
G_t\sim\Gamma(\phi_m,1),\quad
\lambda_t=\tfrac{\mu_m}{\phi_m}G_t,\quad
K_t\sim\mathrm{Poisson}(\lambda_t)
$$

(as produced/logged by S2.3). Accept the **first** $t$ with $K_t\ge 2$, and set

$$
\boxed{\,N_m:=K_t,\quad r_m:=t\,}.
$$

If $K_t\in\{0,1\}$, **reject** and continue with the same merchant’s substreams; envelope counters advance deterministically per attempt. **No hard cap** is imposed here; drift/instability is policed by the corridor gates in validation.

---

### 4) Per-attempt acceptance probability & distribution of rejections (binding math)

Each attempt is an NB2 draw with mean $\mu_m$ and dispersion $\phi_m$. With $r=\phi_m,\,p=\frac{\phi_m}{\mu_m+\phi_m}$ (derivational), the pmf is

$$
\Pr[K=k]=\binom{k+r-1}{k}(1-p)^k\,p^r.
$$

Hence

$$
\Pr[K=0]=p^{\phi_m}=\Bigl(\tfrac{\phi_m}{\mu_m+\phi_m}\Bigr)^{\phi_m},\quad
\Pr[K=1]=\phi_m\cdot(1-p)\,p^{\phi_m}=\phi_m\frac{\mu_m}{\mu_m+\phi_m}\Bigl(\tfrac{\phi_m}{\mu_m+\phi_m}\Bigr)^{\phi_m}.
$$

Define the **success** (acceptance) probability per attempt

$$
\boxed{\,\alpha_m=1-\Pr[K=0]-\Pr[K=1]\,}.
$$

Then $r_m$ (the number of rejections before acceptance) is **geometric** with success probability $\alpha_m$:

$$
\Pr[r_m=r]=(1-\alpha_m)^r\alpha_m,\qquad
\mathbb{E}[r_m]=\frac{1-\alpha_m}{\alpha_m},\qquad
r_{m,q}=\Bigl\lceil\frac{\ln(1-q)}{\ln(1-\alpha_m)}\Bigr\rceil-1.
$$

(These expressions underpin the validator’s corridor metrics; they are not computed in S2.4.)

---

### 5) Event coverage & ordering (binding evidence requirements)

Although S2.4 emits nothing, acceptance **requires** the following to exist for merchant $m$ (evidence checked later):

* $\ge 1$ `gamma_component` (context=`"nb"`) **and** $\ge 1$ `poisson_component` (context=`"nb"`) with matching envelope keys **preceding** the single `nb_final` (S2.5).
* Per attempt, exactly **two** component events in order: Gamma → Poisson.
* `nb_final` is **non-consuming** (its envelope counters do **not** advance).

---

### 6) Determinism & invariants (MUST)

* **I-NB-A (bit replay).** For fixed inputs and lineage, the attempt sequence $(G_t,K_t)_{t\ge0}$, acceptance $(N_m,r_m)$, and the component event set are **bit-reproducible** across replays (Philox counters + fixed per-attempt cardinality + label-scoped substreams).
* **I-NB-B (consumption discipline).** Within each substream, envelope counter intervals are **non-overlapping** and **monotone**; `nb_final` later shows **before == after**. Exactly two component events per attempt; exactly one finalisation at acceptance.
* **I-NB-C (context correctness).** All S2 component events carry `context="nb"` (S4 uses `"ztp"`).

---

### 7) Outputs (to S2.5 and to the validator)

* **Hand-off to S2.5 (in-memory):** $(N_m,\ r_m)$ with $N_m\ge 2$. S2.5 will emit the **single** `nb_final` row echoing $\mu_m,\phi_m$ and recording `n_outlets=N_m`, `nb_rejections=r_m`.
* **Evidence for validation:** Component events as above; validator computes $\widehat{\rho}_{\text{rej}}$ (overall rejection rate), $\widehat{Q}_{0.99}$ (p99 of $r_m$), and a one-sided CUSUM trace. Breaches **abort the run** (no `_passed.flag`).

---

### 8) Failure semantics (merchant-scoped vs run-scoped)

* **Merchant-scoped numeric invalid** (should not arise here if S2.2/2.3 passed): non-finite or $\le0$ $\lambda_t$ ⇒ `ERR_S2_NUMERIC_INVALID` (skip merchant).
* **Structural/coverage failure** (run-scoped): Any `nb_final` without at least one prior `gamma_component` **and** one prior `poisson_component` with matching envelope keys; more than one `nb_final` for the same key; counter overlap/regression. Validators **abort** the run.
* **Corridor breach** (run-scoped): If overall rejection rate $>0.06$, or $p99(r_m)>3$, or the configured one-sided CUSUM gate trips, validators **abort** the run and persist metrics.

---

### 9) Reference pseudocode (language-agnostic; no RNG; no emissions)

```pseudo
# S2.4 rejection loop; S2.3 performs the draws and emits events.
# Returns (N >= 2, r = #rejections)

function s2_4_accept(mu, phi, merchant_id, lineage) -> (N, r):
    t := 0
    loop:
        # One attempt (S2.3): emits gamma_component then poisson_component
        (G, lambda, K) := s2_3_attempt_once(mu, phi, merchant_id, lineage)

        if K >= 2:
            N := K
            r := t
            return (N, r)                # S2.5 will emit nb_final(N, r, mu, phi)
        else:
            t := t + 1                   # rejection; continue loop
```

**Notes.** Attempt indices are not persisted; reconstructions **must** be by **counter intervals** per sub-stream
only (no reliance on time/file order). S2.4 itself **consumes 0 RNG**, writes **no** rows.

---

### 10) Conformance tests (KATs)

1. **Coverage & ordering.** For a sample merchant, use **envelope counter intervals only** to show a pair of `gamma_component`→`poisson_component` followed by **one** `nb_final`; reconstruct `r_m=a-1`; verify `nb_final.nb_rejections == r_m`.
2. **Numeric consistency.** For each attempt $t$, confirm `poisson_component.lambda == (μ/φ)*gamma_value` as binary64; for the accepted attempt, confirm `nb_final.n_outlets == k` from the corresponding Poisson event.
3. **Corridor metrics.** On a synthetic run, compute overall rejection rate and empirical p99; intentionally increase low-μ merchants to trigger a breach and verify the validator aborts.

---

### 11) Complexity

Expected constant attempts (geometric). S2.4 adds **no** compute beyond control-flow; all cost is in S2.3’s samplers. Memory $O(1)$.

---

## S2.5 — Finalisation event `nb_final` (non-consuming, authoritative)

### 1) Scope & intent

Emit **one and only one** authoritative JSONL event per accepted multi-site merchant $m$ that records:

$$
\boxed{\,\mu_m>0,\ \phi_m>0,\ N_m\in\{2,3,\dots\},\ r_m\in\mathbb{N}_0\,}
$$

where $(\mu_m,\phi_m)$ come **verbatim** from S2.2 and $(N_m,r_m)$ from S2.4’s acceptance. This event is **non-consuming** (RNG counters unchanged) and is the sole persisted echo of S2’s accepted NB draw.

---

### 2) Inputs (MUST)

* From **S2.2**: $\mu_m$, $\phi_m$ as IEEE-754 binary64, both $>0$.
* From **S2.4**: $N_m \ge 2$, $r_m \ge 0$ (integers). S2.4 has already ensured acceptance $K\ge2$.
* **RNG envelope** (from S0 infra): `ts_utc, seed, parameter_hash, manifest_fingerprint, run_id, module, substream_label, rng_counter_before_{lo,hi}, rng_counter_after_{lo,hi}, blocks, draws`.
Types: `blocks` is **uint64**; `draws` is **"uint128-dec"** (decimal string).
For `nb_final`, **before == after** (non-consuming) ⇒ `blocks = 0`, `draws = "0"`.

---

### 3) Event stream & partitioning (normative)

Persist **exactly one row** per $(\texttt{seed},\texttt{parameter_hash},\texttt{run_id},\texttt{merchant_id})$ to:

```
logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
```

* **Schema (authoritative):** `schemas.layer1.yaml#/rng/events/nb_final`.
* **Partitions:** `["seed","parameter_hash","run_id"]` (no other partition keys).
* **Stream status:** approved, retention 180 days, consumed by `validation`.

---

### 4) Payload (required fields & domains)

The event **MUST** carry the following payload (beyond the common envelope):

$$
\boxed{\ \{\ \texttt{merchant_id},\ \mu=\mu_m,\ \texttt{dispersion_k}=\phi_m,\ \texttt{n_outlets}=N_m,\ \texttt{nb_rejections}=r_m\ \}\ }.
$$

* `mu`, `dispersion_k`: **positive** binary64 scalars; must bit-match S2.2 outputs.
* `n_outlets`: signed 64-bit integer, **$\ge 2$**.
* `nb_rejections`: signed 64-bit integer, **$\ge 0$**.
* `context` is **not** present here (it exists on component streams); `module`/`substream_label` remain in the envelope for consistency, with **no** RNG consumption.

**Envelope constraint (non-consuming):** `rng_counter_before == rng_counter_after` (both 128-bit fields treated as a pair). The validator asserts this equality for **every** `nb_final` row.

---

### 5) Wire-format example (normative shape)

```json
{
    "ts_utc": "2025-08-15T13:22:19.000000Z",
    "seed": 42,
    "parameter_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "manifest_fingerprint": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
    "run_id": "6e1f3a5b9d0c2e7f3d4a1b2c3e4f5a6b",
    "module": "1A.nb_sampler",
    "substream_label": "nb_final",
    "rng_counter_before_lo": 2,
    "rng_counter_before_hi": 0,
    "rng_counter_after_lo":  2,
    "rng_counter_after_hi":  0,
    "blocks": 0,
    "draws": "0",

    "merchant_id": "M12345",
    "mu": 7.0,
    "dispersion_k": 2.25,
    "n_outlets": 5,
    "nb_rejections": 1
}
```

* Schema anchor: `#/rng/events/nb_final`.
* Counters unchanged → **non-consuming** evidence.

---

### 6) Determinism & invariants (MUST)

* **I-FINAL-ECHO.** `mu` and `dispersion_k` **exactly equal** the S2.2 values (binary64). Any mismatch is a structural consistency failure.
* **I-FINAL-ACCEPT.** `n_outlets == N_m` and `nb_rejections == r_m` from S2.4; there is **exactly one** `nb_final` per merchant key; no other NB events after finalisation.
* **I-FINAL-NONCONSUME.** `rng_counter_before == rng_counter_after` (non-consuming event).
* **I-FINAL-COVERAGE.** Presence of `nb_final` **implies** ≥1 prior `gamma_component` **and** ≥1 prior `poisson_component` with matching envelope keys and `context="nb"`; validator enforces coverage & cardinality.

---

### 7) Failure semantics

* **Schema violation** (missing/typed wrong fields, absent envelope) ⇒ `schema_violation` (row-level), run fails validation.
* **Coverage gap** (final with no prior NB components) ⇒ **structural failure**, run aborts.
* **Duplicate finals** for same key ⇒ **structural failure**; validator reports duplicates and aborts.
* **Non-consumption breach** (counters differ) ⇒ **structural failure**; nb_final must not advance Philox.

---

### 8) Writer algorithm (normative; no RNG; single emission)

```pseudo
# Inputs from S2.2 and S2.4:
#   mu>0 (binary64), phi>0 (binary64), N>=2 (int64), r>=0 (int64)
#   envelope with counters and lineage; counters must already be equal.

function s2_5_emit_nb_final(m, mu, phi, N, r, envelope):
    # 0) Domain checks
    if not (isfinite(mu) and mu > 0):        raise ERR_S2_NUMERIC_INVALID
    if not (isfinite(phi) and phi > 0):      raise ERR_S2_NUMERIC_INVALID
    if not (is_integer(N) and N >= 2):       raise ERR_S2_FINAL_INVALID_N
    if not (is_integer(r) and r >= 0):       raise ERR_S2_FINAL_INVALID_R

    # 1) Non-consuming proof
    if not counters_equal(envelope.before, envelope.after):
        raise ERR_S2_FINAL_CONSUMPTION_DRIFT

    # 2) Construct payload (echo μ, φ exactly; attach in-memory N, r)
    payload := {
        merchant_id: m,
        mu: mu, dispersion_k: phi,
        n_outlets: N, nb_rejections: r
    }

    # 3) Persist one JSONL row to the nb_final stream (dictionary path/partitions)
    emit_event(
        stream="nb_final", schema="#/rng/events/nb_final",
        partition_keys={seed, parameter_hash, run_id},
        envelope=envelope, payload=payload
    )

    # 4) Return (no further S2 emissions)
    return
```

* Emission count: **exactly one** per merchant; **no RNG draws** consumed.

---

### 9) Validator joins & downstream usage (binding)

* **Joins:** Validator left-joins `nb_final` to NB **component** streams by $(\texttt{seed},\texttt{parameter_hash},\texttt{run_id},\texttt{merchant_id})$ to (i) prove coverage/cardinality, (ii) verify $\lambda_t = (\mu/\phi)\cdot\texttt{gamma_value}$ per attempt, and (iii) compute corridors (overall rejection rate, $p_{99}(r_m)$, CUSUM). On any hard failure, the validation bundle is written **without** `_passed.flag`.
* **Hand-off:** $N_m,r_m$ continue **in-memory** to S3+; S2 writes **no** Parquet/Delta tables.

---

### 10) Conformance tests (KATs)

1. **Echo test.** For sampled merchants, recompute $\mu,\phi$ from S2.2 and assert `nb_final.mu` and `nb_final.dispersion_k` **bit-match**; fail run on mismatch.
2. **Non-consuming test.** Assert `rng_counter_before == rng_counter_after` in every `nb_final` row.
3. **Coverage & cardinality.** For every `nb_final`, assert ≥1 prior `gamma_component` and ≥1 prior `poisson_component` (`context="nb"`), and assert **exactly one** `nb_final` per key.
4. **Dictionary path test.** Ensure all `nb_final` rows appear **only** under the dictionary path/partitions & schema anchor.
5. **No side-effects.** Confirm S2 does **not** emit any Parquet data products; only the three JSONL streams exist (Gamma, Poisson, Final).

---

### 11) Complexity

O(1) time and memory per merchant (field checks + single JSONL write). No RNG, no retries.

---

## S2.6 — RNG substreams & consumption discipline (keyed mapping; budgeted/reconciled draws)

### 1) Scope & intent

Guarantee **bit-replay** and **auditability** of the NB sampler by fixing (i) which **Philox** sub-streams are used for each NB attempt component, (ii) how **counters** advance and are exposed, and (iii) what **evidence** is emitted so the validator can prove replay and detect any consumption drift. S2.6 itself draws **no** randomness; it **governs** how S2.3/S2.4/S2.5 consume and log it.

---

### 2) Inputs & label set (must)

* **Labels (NB):** `ℓ_γ = "gamma_nb"`, `ℓ_π = "poisson_nb"`. Exactly these two substreams are used by S2 attempts; `nb_final` is **non-consuming**.

    > **Legend (informative; mirrors registry & schemas)**
    >
    > | substream_label | producer `module` (registry)  | schema ref                       | partitions                     |
    > |-----------------|-------------------------------|----------------------------------|--------------------------------|
    > | `gamma_nb`      | `1A.nb_and_dirichlet_sampler` | `#/rng/events/gamma_component`   | `seed, parameter_hash, run_id` |
    > | `poisson_nb`    | `1A.nb_poisson_component`     | `#/rng/events/poisson_component` | `seed, parameter_hash, run_id` |
    > | `nb_final`      | `1A.nb_sampler`               | `#/rng/events/nb_final`          | `seed, parameter_hash, run_id` |
    >
    > *Note:* This table is a convenience only; authoritative semantics remain in S2 text + S0/S1 + schema/dictionary.
* **Schemas (authoritative):** `schemas.layer1.yaml#/rng/events/gamma_component`, `#/rng/events/poisson_component`, `#/rng/events/nb_final`. Each includes the **rng envelope** with pre/post 128-bit counters.
* **Dictionary paths/partitions:**

  * `logs/rng/events/poisson_component/...` (approved; `["seed","parameter_hash","run_id"]`),
  * `logs/rng/events/nb_final/...` (approved; same partitions).
    (Gamma stream path is pinned similarly; consumers/partitions mirror Poisson.)

---

### 3) Deterministic keyed mapping (normative)

All sub-streams are derived by the **S0.3.3 keyed mapping** from run lineage + label + merchant, order-invariant across partitions:

1. **Base counter for a (label, merchant)**

    $$
    (c^{\mathrm{base}}_{\mathrm{hi}},c^{\mathrm{base}}_{\mathrm{lo}})
    =\mathrm{split64}\!\Big(\mathrm{SHA256}\big(\text{"ctr:1A"}\,\|\,\texttt{manifest_fingerprint_bytes}\,\|\,\mathrm{LE64}(\texttt{seed})\,\|\,\ell\,\|\,\mathrm{LE64}(m)\big)[0{:}16]\Big).
    $$

2. **b-th block** for that pair uses

    $$
    (c_{\mathrm{hi}},c_{\mathrm{lo}})=(c^{\mathrm{base}}_{\mathrm{hi}},\,c^{\mathrm{base}}_{\mathrm{lo}}+b),
    $$

    with 64-bit carry into $c_{\mathrm{hi}}$; this block yields two lanes $(x_0,x_1)$.
    **Single-uniform events** consume $x_0$ and **discard** $x_1$ ($\texttt{blocks}=1$, $\texttt{draws}="1"$);
    **two-uniform events** (e.g., Box–Muller) consume **both** $x_0,x_1$ from the **same** block
    ($\texttt{blocks}=1$, $\texttt{draws}="2"$). Mapping is **pure** in $(\texttt{seed},\texttt{fingerprint},\ell,m,b)$.

**Envelope arithmetic (per event):**

$$
\boxed{\texttt{blocks}\;:=\;u128(\texttt{after})-u128(\texttt{before})}
$$

in **unsigned 128-bit** arithmetic. The envelope **must** carry both:
`blocks` (**uint64**) and `draws` (decimal **uint128** string).
Here `draws` records the **actual count of U(0,1)** uniforms consumed by
the event’s sampler(s) and is **independent** of the counter delta.

Examples: Box–Muller → `blocks=1`, `draws="2"`; single-uniform → `blocks=1`,
`draws="1"`; non-consuming finaliser → `blocks=0`, `draws="0"`.
---

### 4) Uniform & normal primitives (normative)

* **Open-interval uniform** (exclusive bounds):

$$
\boxed{\,u = ((x+1)\times 0x1.0000000000000p-64)\ \in (0,1)\,},\quad x\in\{0,\dots,2^{64}\!-\!1\}.
$$

The multiplier **must** be written as the **binary64 hex literal** `0x1.0000000000000p-64`
(no decimal substitutes).
**Clamp to strict open interval.** After computing `u`, perform:
`if u == 1.0: u := 0x1.fffffffffffffp-1` (i.e., \(1-2^{-53}\)).
This does not affect `blocks`/`draws`; it guarantees \(u\in(0,1)\) in binary64.

**Lane policy.** A Philox **block** yields two 64-bit lanes `(x0,x1)` then advances by **1**.
* **Single-uniform events:** use `x0`, **discard** `x1` → `blocks=1`, `draws="1"`.
* **Two-uniform events (e.g., Box–Muller):** use **both** `x0,x1` from the **same** block
→ `blocks=1`, `draws="2"`; **no caching** across events.

* **Standard normal** $Z$ via Box–Muller: exactly **2 uniforms per $Z$**; **no caching** of the sine deviate.

> **Scope rule:** All uniforms in S2 (Gamma & Poisson) **must** use this `u01`. Validators don’t log uniforms but prove discipline via counters.

---

### 5) Event cardinality & ordering (attempt-level)

For attempt index $t=0,1,2,\dots$ of merchant $m$:

* Emit **exactly one** `gamma_component` on $\ell_\gamma$ **then** **exactly one** `poisson_component` on $\ell_\pi$.
* On acceptance (first $K_t\ge2$), emit **exactly one** `nb_final` (non-consuming).
  No other NB events are allowed for that merchant.

---

### 6) Draw budgets & reconciliation (normative)

For each `(module, substream_label)`, validators reconcile **two independent totals**:
`blocks_total = Σ blocks_event` (which equals the stream’s 128-bit counter span) and
`draws_total = Σ draws_event` (which equals the uniforms implied by the sampler budgets).
No identity ties `draws` to the counter delta.
* **`gamma_component` (context="nb")**

  $$
  \text{draws} = \sum_t \left( 3 \times J_t + \mathbf{1}[\phi_m < 1] \right)
  $$
  where the sum is over NB attempts $t$ (one Gamma variate per attempt) and $J_t≥1$ is the number of MT98 internal iterations for that variate.

  Rationale: each MT98 iteration uses **2 uniforms** for the Box–Muller normal and **1 uniform** for the accept-$U$; when $\phi_m < 1$, add **+1 uniform per variate** for the power step $U^{1/\alpha}$.
* **`poisson_component` (context="nb")**
  **Variable** (inversion for $\lambda<10$; PTRS otherwise). Envelope counters measure actual consumption; there is **no fixed budget**.
* **`nb_final`**
  **Non-consuming**: `before == after`; `draws = 0`. (Validator enforces.)

Additionally, a run may emit **`rng_trace_log`** rows (per `(module, substream_label)`) carrying `draws` for fast aggregation; these are used by validation for reconciliation.

---

### 7) Counter discipline (interval semantics)

Within each $(m,\ell)$ stream, event intervals must be **non-overlapping and monotone**:

$$
[c^{(e)}_{\text{before}},c^{(e)}_{\text{after}}) \cap [c^{(e+1)}_{\text{before}},c^{(e+1)}_{\text{after}})=\varnothing,\quad
c^{(e+1)}_{\text{before}}\ge c^{(e)}_{\text{after}}.
$$

For `nb_final`, enforce **non-consumption** (`before == after`).

---

### 8) Validator contract (replay & discipline proof)

**Replay proof (per merchant):**

1. Collect all `gamma_component` and `poisson_component` rows for the key $(\texttt{seed},\texttt{parameter_hash},\texttt{run_id},\texttt{merchant_id})$. Enforce **monotone, non-overlapping** intervals per sub-stream.
2. Reconstruct attempt pairs (Gamma→Poisson) **solely by counter intervals**:
   per merchant, sort each substream strictly by `rng_counter_before` (lexicographic on
   `(before_hi,before_lo)`), then pair the *t*-th Gamma with the *t*-th Poisson subject to
   `u128(before)_Γ[t] < u128(after)_Γ[t] ≤ u128(before)_Π[t] < u128(after)_Π[t]`.
   **No reliance on time/file order.** Derive the first $t$ with $K_t\ge2$.
3. Join to the single `nb_final`; assert `n_outlets` and `nb_rejections` match the reconstruction; assert `mu, dispersion_k` **echo** S2.2. **Pass iff identical.**

**Discipline checks (hard):**

* **Cardinality:** exactly 1 Gamma and 1 Poisson per attempt; exactly 1 `nb_final` per merchant key.
* **Budgets:** Gamma draw totals equal $3\times$attempts $+\mathbf{1}[\phi_m<1]$; Poisson totals reconcile by counters; `nb_final` has `draws=0`.
* **Coverage:** if `nb_final` exists, there is ≥1 `gamma_component` **and** ≥1 `poisson_component` with `context="nb"` and matching envelopes.

---

### 9) Failure semantics (run-scoped unless noted)

* **Structural/counter failure** (overlap, non-monotone, or `nb_final` consumption) ⇒ validator **aborts** the run; bundle is written without `_passed.flag`.
* **Schema/coverage/cardinality failure** (missing envelope fields; missing component event; duplicate `nb_final`) ⇒ **abort**.
* **Corridor breach** (overall NB rejection rate or p99 gate tripped—defined in S2.4/S2.7) ⇒ **abort** with metrics; out of scope of S2.6 but enforced in the same validation pass.

---

### 10) Reference implementation pattern (non-allocating; per merchant)

```pseudo
# Substream state (derived, not stored):
# base_gamma, base_pois: (hi, lo) from S0.3.3; i_gamma, i_pois: u64 counters (block index)
struct Substream {
  base_hi: u64; base_lo: u64; i: u128
}

function substream_begin(s: Substream) -> (before_hi, before_lo):
    return add128((s.base_hi, s.base_lo), s.i)   # 128-bit

function substream_end(s: Substream, blocks: u128) -> (after_hi, after_lo):
    return add128((s.base_hi, s.base_lo), s.i + blocks)

# Each Philox block yields two 64-bit lanes (x0,x1); s.i advances by **1 block** per call.
# Single-uniform events use the **low lane** and **discard** the high lane; two-uniform families use **both lanes from one block**.

# Map lane to u in (0,1) using the hex-float multiplier (Crit #5).
function u01_map(x: u64) -> f64:
    u = ((x + 1) * 0x1.0000000000000p-64)
    if u == 1.0:
        u = 0x1.fffffffffffffp-1
    return u

# Advance by **one block**, return both lanes.
function philox_block(s: inout Substream) -> (x0:u64, x1:u64):
    ctr = add128((s.base_hi, s.base_lo), s.i)
    (x0, x1) = philox64x2(ctr)
    s.i += 1
    return (x0, x1)

# Two uniforms from **one** block (e.g., Box–Muller).
function u01_pair(s: inout Substream) -> (u0:f64, u1:f64, blocks_used:u128, draws_used:u128):
    (x0, x1) = philox_block(s)                   # consumes 1 block
    return (u01_map(x0), u01_map(x1), 1, 2)     # blocks=1, draws=2

# Single uniform: use **low lane** from a fresh block; **discard** the high lane.
function u01_single(s: inout Substream) -> (u:f64, blocks_used:u128, draws_used:u128):
    (x0, _x1) = philox_block(s)                  # consumes 1 block; high lane discarded
    return (u01_map(x0), 1, 1)                   # blocks=1, draws=1

# Event emission for Gamma component (per attempt):
# The sampler returns actual budgets; the emitter stamps counters independently.
function emit_gamma_component(ctx, s_gamma: inout Substream, alpha_phi: f64):
    (before_hi, before_lo) = substream_begin(s_gamma)
    (G, blocks_used, draws_used) = gamma_mt98_with_budget(alpha_phi, s_gamma)  # uses u01_single/u01_pair internally
    (after_hi,  after_lo)  = substream_end(s_gamma, blocks_used)
    assert u128((after_hi,after_lo)) - u128((before_hi,before_lo)) == blocks_used
    write_jsonl("gamma_component",
        envelope={
          ...,
          "rng_counter_before_lo": before_lo, "rng_counter_before_hi": before_hi,
          "rng_counter_after_lo":  after_lo,  "rng_counter_after_hi":  after_hi,
          "blocks": blocks_used, "draws": stringify_u128(draws_used),
          "substream_label": "gamma_nb"
        },
        payload={ merchant_id, context:"nb", index:0, alpha:alpha_phi, gamma_value:G }
    )

# Poisson component is analogous, using its sampler’s (blocks_used, draws_used) and payload {lambda, k}.
# nb_final is non-consuming: before == after, blocks=0, draws="0".
```

**Notes.**
- The samplers do **not** see counters; they only call `u01(s)`; the event writer collects `draws_used` and stamps the envelope.
- For Gamma with $\phi_m < 1$, add **one** `u01(s_gamma)` for the $U^{1/\alpha}$ power step **per variate (i.e., per attempt)**, not once per merchant. Hence the total budget aggregates as **$\sum_t \left( 3 \times J_t + \mathbf{1}[\phi_m < 1] \right)$**.

---

### 11) Invariants (MUST)

* **I-NB1 (bit replay).** Fixed inputs + S0 mapping ⇒ the sequence $(G_t,K_t)_{t\ge0}$ and the accepted pair $(N_m,r_m)$ are **bit-identical** across replays.
* **I-NB3 (open-interval).** All uniforms satisfy $u\in(0,1)$.
* **I-NB4 (consumption).** Exactly two component events per attempt; one `nb_final`; downstream counters match the trace; `nb_final` non-consuming.

---

### 12) Conformance tests (KATs)

1. **Budget check (Gamma).** For a case with $\phi\ge1$ and $a$ attempts, assert `Σ draws(gamma_component) == 3a`; with $\phi<1$, assert `== 3a+1`.
2. **Variable Poisson.** Choose $\lambda=5$ (inversion) and $\lambda=50$ (PTRS); verify envelope deltas are positive, monotone, and **not** fixed.
3. **Non-consumption final.** Every `nb_final` has `before == after`.
4. **Interval discipline.** Per $(m,\ell)$, counters are **non-overlapping** and **monotone**; reconstruct attempts (Gamma→Poisson) then join to `nb_final`; fail on any deviation.
5. **Coverage.** If a `nb_final` exists, assert presence of ≥1 prior Gamma and ≥1 prior Poisson with `context="nb"`.

---

### 13) Complexity

* **Runtime:** negligible overhead beyond sampler draws (constant-time arithmetic + one JSONL write per event).
* **Memory:** $O(1)$ per merchant (two sub-streams with 128-bit indices).

---

## S2.7 — Monitoring corridors & thresholds (run gate)

### 1) Scope & intent

Compute run-level statistics of the S2 rejection process and **abort the run** if any corridor is breached. Corridors cover:

* the **overall rejection rate** across all attempts,
* the **99th percentile** of per-merchant rejections $r_m$,
* a **one-sided CUSUM** detector for upward drift in rejections relative to model-expected behaviour.

**This step consumes no RNG, writes no NB events, and is evaluated by validation** immediately after S2 completes (it may persist its own validation bundle/metrics as per your validation harness; persistence details live in the validation spec).

---

### 2) Inclusion criteria (MUST)

Only merchants with a **valid S2 finalisation** are included. Formally, define the set

$$
\mathcal{M}=\{\,m:\ \text{exactly one } \texttt{nb_final}\ \text{exists for }m\ \text{and coverage tests pass}\,\}.
$$

For each $m\in\mathcal{M}$, read from `nb_final`:

* $r_m = \texttt{nb_rejections}\in\mathbb{N}_0$,
* $N_m=\texttt{n_outlets}\in\{2,3,\dots\}$.

Merchants without `nb_final` (e.g., numeric aborts in S2.2/2.3) are **excluded** from corridor statistics but counted under separate health metrics (not part of the corridors). Coverage must already have verified ≥1 `gamma_component` and ≥1 `poisson_component` (context=`"nb"`) for each `nb_final`.

---

### 3) Per-merchant acceptance parameter $\alpha_m$ (used by CUSUM)

For each $m\in\mathcal{M}$, compute the **model-predicted** attempt acceptance probability $\alpha_m$ from the S2.2 parameters $(\mu_m,\phi_m)$ (binary64):

Let

$$
p_m=\frac{\phi_m}{\mu_m+\phi_m},\quad
q_m=1-p_m=\frac{\mu_m}{\mu_m+\phi_m}.
$$

Then the NB2 probabilities for $K=0$ and $K=1$ are

$$
P_0 = p_m^{\phi_m},\qquad
P_1 = \phi_m\,q_m\,p_m^{\phi_m}.
$$

Define

$$
\boxed{\ \alpha_m=1-P_0-P_1\ } \quad\text{(success = accept on an attempt)}.
$$

#### 3.1 Numerically stable evaluation (MUST)

Evaluate in **binary64** with log-domain guards:

* $\log p_m=\log\phi_m-\log(\mu_m+\phi_m)$.
* $\log P_0=\phi_m\log p_m$; $P_0=\exp(\log P_0)$.
* $P_1 = P_0 \cdot \phi_m \cdot q_m$ (re-use $P_0$ to avoid an extra exponentiation).
* $\alpha_m = 1 - P_0 - P_1$.

**Guards:**

* If any intermediate is non-finite, or if $\alpha_m\notin(0,1]$, the merchant is flagged `ERR_S2_CORRIDOR_ALPHA_INVALID` and **excluded** from corridor statistics (still recorded under health metrics). This should not occur if S2.2 guards held; making it explicit keeps the corridor math well-posed.

---

### 4) Corridor metrics (normative)

Let $a_m = r_m+1$ be the total attempts for merchant $m$. Define $M=|\mathcal{M}|$ and totals

$$
R=\sum_{m\in\mathcal{M}} r_m,\qquad
A=\sum_{m\in\mathcal{M}} a_m = \sum_{m\in\mathcal{M}} (r_m+1).
$$

#### 4.1 Overall rejection rate $\widehat{\rho}_{\text{rej}}$

$$
\boxed{\ \widehat{\rho}_{\text{rej}} = \frac{R}{A}\ } \in [0,1).
$$

Equivalently, $\widehat{\rho}_{\text{rej}} = 1 - M/A$. **MUST** be computed exactly as above (attempt-weighted).

**Threshold (hard):** $\widehat{\rho}_{\text{rej}} \le 0.06$. Exceedance ⇒ run fails.

#### 4.2 99th percentile of rejections $Q_{0.99}$

Let $r_{(1)}\le \dots \le r_{(M)}$ be the ascending order. Use **nearest-rank** quantile (normative):

$$
\boxed{\ Q_{0.99} = r_{(\lceil 0.99\,M\rceil)}\ }.
$$

**Threshold (hard):** $Q_{0.99} \le 3$. Exceedance ⇒ run fails.

**Notes:**

* If $M=0$ (no merchants reached S2 final), corridors are **not evaluable**: return `ERR_S2_CORRIDOR_EMPTY` and fail the run (no evidence to assert health).
* For $M<100$, nearest-rank is still well-defined; this is intentional for determinism.

#### 4.3 One-sided CUSUM for upward drift (standardised residuals)

We monitor the sequence $\{r_m\}_{m\in\mathcal{M}}$ ordered by **merchant key** (deterministic total order; e.g., ascending `merchant_id`). For each $m$, form a standardised residual against the geometric expectation implied by $\alpha_m$:

$$
\mathbb{E}[r_m] = \frac{1-\alpha_m}{\alpha_m},\qquad
\mathrm{Var}(r_m) = \frac{1-\alpha_m}{\alpha_m^2}.
$$

Define

$$
z_m = \frac{r_m - \mathbb{E}[r_m]}{\sqrt{\mathrm{Var}(r_m)}}.
$$

Let the **one-sided positive CUSUM** be

$$
S_0=0,\qquad S_t=\max\{0,\ S_{t-1} + (z_{m_t} - k)\},\quad t=1,\dots,M,
$$

with **reference value** $k>0$ and **threshold** $h>0$.

**Gate (hard):** If $\max_{1\le t\le M} S_t \ge h$ ⇒ run fails.

**Governance of $k,h$:** These are **policy parameters** (not algorithmic constants). They MUST be supplied by the validation policy artefact for the run (e.g., `validation_policy.yaml`):
`cusum.reference_k` (default 0.5), `cusum.threshold_h` (default 8.0). If absent, validation must **fail closed** (`ERR_S2_CORRIDOR_POLICY_MISSING`).

**Notes:**

* Using standardised $z_m$ accounts for heterogeneity in $\alpha_m$ across merchants.
* CUSUM is computed **once** per run over the ordered merchant sequence; there is no windowing in this spec.

---

### 5) Pass/fail logic (normative)

Compute the three statistics. The run **passes the S2 corridors** iff **all** hold:

1. $\widehat{\rho}_{\text{rej}} \le 0.06$,
2. $Q_{0.99} \le 3$,
3. $\max S_t < h$.

Else, the run **fails**: the validator **must not** write `_passed.flag` for this fingerprint; it must persist a metrics object (see §8) documenting the breach(es).

---

### 6) Numerical & data handling requirements (MUST)

* All computations are **binary64**; no integer overflow risks since $r_m$ are small.
* Sorting uses **bytewise ascending** on the merchant key (deterministic).
* Duplicate `nb_final` rows for the same key ⇒ structural failure upstream; corridors are not computed until structure is clean.
* Exclusions: merchants with invalid $\alpha_m$ (see §3.1) are **not** in $\mathcal{M}$ for corridor stats; they are reported separately.

---

### 7) Errors & abort semantics

* `ERR_S2_CORRIDOR_EMPTY` — $M=0$; corridors not evaluable. ⇒ **Fail run**.
* `ERR_S2_CORRIDOR_POLICY_MISSING` — missing $k,h$ in policy. ⇒ **Fail run**.
* `ERR_S2_CORRIDOR_ALPHA_INVALID:{m}` — bad $\alpha_m$ for merchant `m`; merchant is excluded; proceed if $M>0$.
* **Breach** of any corridor ⇒ **Fail run** with `reason ∈ {"rho_rej","p99","cusum"}` (multi-reason allowed).

---

### 8) Validator algorithm (reference; no RNG; O(M log M))

```pseudo
function s2_7_corridors(nb_finals, policy) -> Result:
    # nb_finals: iterable of records with {merchant_id, mu, phi, n_outlets, nb_rejections}
    # policy: { cusum: { reference_k: f64, threshold_h: f64 } }

    if policy.cusum is None: return FAIL(ERR_S2_CORRIDOR_POLICY_MISSING)

    # 1) Construct inclusion set with α_m
    Mset := []
    for row in nb_finals:
        m  := row.merchant_id
        r  := int64(row.nb_rejections)
        mu := f64(row.mu);  phi := f64(row.dispersion_k)
        # α_m from μ, φ (binary64), numerically stable
        p  := phi / (mu + phi)
        logP0 := phi * log(p)         # phi>0, p∈(0,1)
        P0 := exp(logP0)
        q  := 1.0 - p
        P1 := P0 * phi * q
        alpha := 1.0 - P0 - P1
        if not isfinite(alpha) or alpha <= 0.0 or alpha > 1.0:
            record_warn(ERR_S2_CORRIDOR_ALPHA_INVALID, m)
            continue
        Mset.append({m, r, alpha})

    M := len(Mset)
    if M == 0: return FAIL(ERR_S2_CORRIDOR_EMPTY)

    # 2) Overall rejection rate
    R := sum(r for each in Mset)
    A := sum(r + 1 for each in Mset)
    rho_hat := R / A

    # 3) p99 of r_m (nearest-rank)
    r_sorted := sort([r for each in Mset])           # ascending
    idx := ceil(0.99 * M)
    p99 := r_sorted[idx - 1]                         # 1-based to 0-based

    # 4) One-sided CUSUM over standardised residuals
    k := policy.cusum.reference_k     # e.g., 0.5
    h := policy.cusum.threshold_h     # e.g., 8.0
    Ms := sort(Mset by merchant_id bytes ascending)
    S := 0.0; Smax := 0.0
    for each in Ms:
        alpha := each.alpha; r := each.r
        Er := (1.0 - alpha) / alpha
        Vr := (1.0 - alpha) / (alpha * alpha)
        z  := (r - Er) / sqrt(Vr)
        S  := max(0.0, S + (z - k))
        Smax := max(Smax, S)

    # 5) Decide
    breaches := []
    if rho_hat > 0.06: breaches.append("rho_rej")
    if p99 > 3:        breaches.append("p99")
    if Smax >= h:      breaches.append("cusum")

    if breaches is empty:
        return PASS({rho_hat, p99, Smax, M, R, A})
    else:
        return FAIL({rho_hat, p99, Smax, M, R, A, breaches})
```

**Complexity:** $O(M\log M)$ due to sorting; memory $O(M)$.

---

### 9) Invariants & evidence (MUST)

* **I-S2.7-ATTEMPT:** $A=\sum_m (r_m+1)$ equals the **total count of Poisson component events** across all S2 merchants; validator **must** reconcile these tallies (attempt-weighted rate correctness).
* **I-S2.7-ECHO:** For every $m$, the `nb_final`’s `mu`/`dispersion_k` match S2.2; `n_outlets` matches acceptance in S2.4; these are preconditions for inclusion.
* **I-S2.7-ORDER:** CUSUM ordering uses a deterministic total order on merchant keys (bytewise asc.); the order MUST be recorded in the bundle to ensure reproducibility of $S_{\max}$.

---

### 10) Conformance tests (KATs)

**Determinism.**

1. Shuffle the input `nb_final` rows: $\widehat{\rho}_{\text{rej}}$ and $Q_{0.99}$ unchanged; $S_{\max}$ unchanged **iff** the order reconstruction is the same — hence the order is explicitly defined as merchant key bytes ascending.

**Threshold triggers.**
2\) Synthetic dataset with $r_m=0$ for all $m$: expect $\widehat{\rho}_{\text{rej}}=0$, $Q_{0.99}=0$, $S_{\max}=0$ ⇒ **pass**.
3\) Inject 7% of attempts as rejections uniformly (increase many $r_m$ by 1): expect $\widehat{\rho}_{\text{rej}}>0.06$ ⇒ **fail** with breach `rho_rej`.
4\) Make $1\%$ of merchants have $r_m=4$ and the rest ≤3: expect $Q_{0.99}=4$ ⇒ **fail** with breach `p99`.
5\) Create a drift scenario: progressively inflate $r_m$ above $\mathbb{E}[r_m]$ late in the ordered sequence so that $S_{\max}\ge h$ ⇒ **fail** with breach `cusum`.

**Numerical guard.**
6\) Force extreme $\mu$/$\phi$ to yield $\alpha$ near 0 or 1; verify computation remains finite; if not, those merchants are excluded and flagged `ERR_S2_CORRIDOR_ALPHA_INVALID`, but run proceeds if $M>0$.

---

### 11) Outputs

* **Pass:** Return metrics `{rho_hat, p99, Smax, M, R, A}`; the overall validation may then stamp `_passed.flag` (outside this section).
* **Fail:** Return metrics + `breaches`; the overall validation **must not** stamp `_passed.flag` and must surface the reasons.

---

## S2.8 — Failure modes (abort semantics, evidence, actions)

### 1) Scope & intent

Define **all** conditions under which the S2 NB sampler (multi-site outlet count) must **abort** (merchant-scoped) or **fail validation** (run-scoped), and the **exact evidence** required to prove and diagnose each failure. This section binds to:

* S2.1 (entry gate, inputs), S2.2 (NB2 links), S2.3 (Gamma/Poisson samplers), S2.4 (rejection loop), S2.5 (finalisation), S2.6 (RNG discipline), S2.7 (corridors).

**Authoritative streams & schema anchors** (must be used by validator):
`logs/rng/events/gamma_component/…  #/rng/events/gamma_component`
`logs/rng/events/poisson_component/…  #/rng/events/poisson_component`
`logs/rng/events/nb_final/…  #/rng/events/nb_final`  (all partitioned by `["seed","parameter_hash","run_id"]`).

---

### 2) Error classes, codes, and actions (normative)

We categorize failures as **merchant-scoped aborts** (S2 stops for that merchant; no further S2 output) and **run-scoped validation fails** (the validator **aborts the run** and does not write `_passed.flag`).

#### A) Merchant-scoped aborts (during S2 execution)

**F-S2.1 — Non-finite / non-positive NB2 parameters** (S2.2)
**Condition.** $\mu_m\le 0$ or $\phi_m\le 0$, or either linear predictor/exponential is NaN/Inf in binary64.
**Code.** `ERR_S2_NUMERIC_INVALID`.
**Action.** **Abort S2 for m**; **no** S2.3 events should be emitted for that merchant.
**Evidence.** Validator recomputes $(\mu_m,\phi_m)$ from S2.1 inputs + governed artefacts (by `parameter_hash`) and flags `invalid_nb_parameters(m)`.

**F-S2.2 — Sampler numeric invalid** (S2.3)
**Condition.** `gamma_component.alpha ≤ 0` or `gamma_value ≤ 0`, or `poisson_component.lambda ≤ 0` / non-finite. (Should not occur if S2.2 passed.)
**Code.** `ERR_S2_SAMPLER_NUMERIC_INVALID`.
**Action.** **Row-level schema failure** → merchant effectively fails; validator will abort the run (see C-class).
**Evidence.** Offending JSONL row fails `schemas.layer1.yaml` numeric/domain checks.

**F-S2.0 — Entry gate violations** (S2.1)
**Condition.** Missing S1 hurdle record or `is_multi=false` attempting to enter S2.
**Code.** `ERR_S2_ENTRY_MISSING_HURDLE` / `ERR_S2_ENTRY_NOT_MULTI`.
**Action.** **Skip S2** for the merchant; any S2 events later will be caught as structural (D-class).
**Evidence.** Hurdle stream is authoritative gate for S2.

#### B) Run-scoped schema/structure/discipline failures (validator)

**C-S2.3 — Schema violation (any S2 event)**
**Condition.** Missing envelope fields; missing required payload keys; wrong `context` (`"nb"` required for Gamma/Poisson; `nb_final` has **no** `context` field); bad domains (e.g., `k<0`).
**Action.** **Hard schema failure** → **abort run**.
**Evidence.** Per-row schema checks on the three streams.

**C-S2.4 — Coverage & cardinality gap**
**Condition.** Any `nb_final` **without** at least one prior `gamma_component` **and** one prior `poisson_component` (both with `context="nb"`), or **duplicate** `nb_final` for the same `(seed, parameter_hash, run_id, merchant_id)`.
**Action.** **Structural failure** → **abort run**.
**Evidence.** Coverage join across the three streams indicates absence/duplication.

**C-S2.5 — Consumption discipline breach** (S2.6 invariants)
**Condition.** Any of: `after < before`; overlapping intervals within a sub-stream; `nb_final` advances counters (`before≠after`); per-attempt cardinality differs from **exactly one** Gamma + **exactly one** Poisson.
**Action.** **Structural failure** → **abort run**.
**Evidence.** Envelope counter scans on Gamma/Poisson/Final prove the violation.

**C-S2.6 — Composition mismatch (Gamma→Poisson)**
**Condition.** For attempt $t$:

$$
\lambda_t \stackrel{!}{=} (\mu/\phi)\cdot \texttt{gamma_value}_t
$$

with `mu, dispersion_k` taken from `nb_final`; mismatch under strict binary64 equality (or 1-ULP, per policy).
**Action.** **Consistency failure** → **abort run**.
**Evidence.** Validator pairs attempts by counters/time and checks equality.

**C-S2.8 — Partition/path misuse**
**Condition.** Any S2 event written outside its dictionary path or missing required partitions `["seed","parameter_hash","run_id"]`.
**Action.** **Structural failure** → **abort run**.
**Evidence.** Dictionary path/partition check.

**C-S2.9 — Single-site hygiene breach (branch purity)**
**Condition.** A merchant with S1 `is_multi=0` has **any** S2 NB event.
**Action.** **Structural failure** → **abort run**.
**Evidence.** Cross-check hurdle stream vs S2 streams; hurdle is authoritative first RNG stream.

#### C) Run-scoped corridor failures (validator, S2.7)

**D-S2.7 — Corridor breach**
**Condition.** Any of: overall rejection rate $\widehat{\rho}_{\text{rej}}>0.06$; p99 of $r_m$ exceeds 3; one-sided CUSUM exceeds threshold $h$ (policy).
**Action.** **Validation abort** → **no** `_passed.flag`; metrics & plots in bundle.
**Evidence.** `metrics.csv` + CUSUM trace in the validation bundle.

---

### 3) Consolidated error code table (normative)

| Code                                | Scope     | Trigger                                                     | Detection locus               | Action          |
|-------------------------------------|-----------|-------------------------------------------------------------|-------------------------------|-----------------|
| `ERR_S2_ENTRY_MISSING_HURDLE`       | merchant  | no hurdle record for $m$                                    | S2.1                          | skip S2 for $m$ |
| `ERR_S2_ENTRY_NOT_MULTI`            | merchant  | hurdle `is_multi=false`                                     | S2.1                          | skip S2 for $m$ |
| `ERR_S2_NUMERIC_INVALID`            | merchant  | $\mu\le0$ or $\phi\le0$ or NaN/Inf                          | S2.2 (+defensive in S2.3/2.5) | abort $m$       |
| `ERR_S2_SAMPLER_NUMERIC_INVALID`    | run (row) | gamma/poisson numeric domains violated                      | Validator (schema)            | abort run       |
| `schema_violation`                  | run (row) | envelope/payload/context missing/invalid                    | Validator                     | abort run       |
| `event_coverage_gap`                | run       | `nb_final` lacks prior Gamma & Poisson; or duplicate finals | Validator                     | abort run       |
| `rng_consumption_violation`         | run       | counter overlap/regression; `nb_final` consumes             | Validator                     | abort run       |
| `composition_mismatch`              | run       | $\lambda\neq (\mu/\phi)\cdot \texttt{gamma_value}$          | Validator                     | abort run       |
| `partition_misuse`                  | run       | wrong path/partitions                                       | Validator                     | abort run       |
| `branch_purity_violation`           | run       | single-site merchant has S2 events                          | Validator                     | abort run       |
| `corridor_breach:{rho\|p99\|cusum}` | run       | corridor thresholds trip                                    | Validator                     | abort run       |

---

### 4) Detection loci and evidence (binding)

1. **During S2** (writer-side, merchant-scoped): S2.2/S2.3/S2.5 must **raise** their errors and **avoid emitting** downstream S2 events for the merchant. (No partial S2 trails.)
2. **After S2** (validator): perform, at minimum, the following checks in order—schema, coverage/cardinality, counter discipline, composition, corridors, path partitions, branch purity. A failure in **any** step ⇒ run fails; bundle still written without `_passed.flag`.

---

### 5) Validator reference algorithm (S2 failure screening; O(N log N))

A minimal but normative checklist appears below (expands your draft into an enforceable pass/fail).

```pseudo
function validate_S2(nb_gamma, nb_pois, nb_final, hurdle, dictionary, policy):
    # 0) Schema & path/partition checks for all three S2 streams
    for row in nb_gamma: schema_check(row, "#/rng/events/gamma_component")
    for row in nb_pois:  schema_check(row, "#/rng/events/poisson_component")
    for row in nb_final: schema_check(row, "#/rng/events/nb_final")
    assert_dictionary_paths_partitions({nb_gamma, nb_pois, nb_final})
    # 1) Branch purity: any S2 event for is_multi=0 => branch_purity_violation
    assert_branch_purity(hurdle, {nb_gamma, nb_pois, nb_final})
    # 2) By (seed, parameter_hash, run_id, merchant_id):
    for key in keys:
        A := nb_gamma[key]; B := nb_pois[key]; F := nb_final[key]
        # coverage/cardinality
        assert ((len(A)>=1 && len(B)>=1 && len(F)==1) or merchant_is_not_multi(key))
        # counters: monotone intervals; nb_final non-consuming
        assert_counters_monotone(A); assert_counters_monotone(B); assert_final_nonconsuming(F)
        # parameter echo & composition
        (mu,phi) := (F[0].mu, F[0].dispersion_k)
        for a in A: assert_ulps_equal(a.alpha, phi, 1)
        pairwise_by_counter_intervals(A, B, (a, b) => assert_ulps_equal(b.lambda, (mu/phi)*a.gamma_value, 1))
        # acceptance reconstruction
        t := first i with B[i].k >= 2
        assert t exists && F[0].n_outlets == B[t].k && F[0].nb_rejections == t
    # 3) Corridors (S2.7)
    (rho_hat, p99, Smax) := corridors(nb_final, policy)
    assert rho_hat <= 0.06 && p99 <= 3 && Smax < policy.cusum.threshold_h
```

**Fail fast:** Any violated assertion returns a typed failure with the corresponding code in §3.

---

### 6) Invariants (re-stated as validator obligations)

* **I-NB2 echo.** `nb_final.mu`/`dispersion_k` must **equal** S2.2 outputs (binary64).
* **Coverage invariant.** If `nb_final` exists, there must be ≥1 prior Gamma and ≥1 prior Poisson (`context="nb"`) with matching envelope keys.
* **Consumption discipline.** Exactly two component events/attempt; `nb_final` non-consuming; counters monotone, non-overlapping.

---

### 7) Conformance tests (KATs)

1. **Parameter invalid KAT.** Force $\eta$ to overflow/underflow so $\mu$ or $\phi$ becomes non-finite or $\le0$ ⇒ writer raises `ERR_S2_NUMERIC_INVALID`; validator shows **no** S2 events for that merchant and flags `invalid_nb_parameters`.
2. **Schema KAT.** Drop `context` in a Gamma row ⇒ schema failure; run aborts with `schema_violation`.
3. **Coverage KAT.** Emit `nb_final` without a Poisson component ⇒ `event_coverage_gap` and abort.
4. **Counters KAT.** Make `nb_final` advance counters ⇒ `rng_consumption_violation` and abort.
5. **Composition KAT.** Perturb `lambda` by 1 ULP ⇒ `composition_mismatch` and abort.
6. **Partitions KAT.** Write Poisson to a wrong path or missing `parameter_hash` partition ⇒ `partition_misuse` and abort.
7. **Branch purity KAT.** Create S2 events for a known `is_multi=0` merchant ⇒ `branch_purity_violation`.
8. **Corridors KAT.** Inflate low-$\mu$ merchants to push $\widehat{\rho}_{\text{rej}}>0.06$ ⇒ `corridor_breach:rho`.

---

### 8) Run outcome & artifacts

* **Any single hard failure** causes the S2 block to **fail validation**, so **1A fails** for that `manifest_fingerprint`. The validator still writes a **bundle** to
  `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`
  containing: `index.json`, `schema_checks.json`, `rng_accounting.json`, `metrics.csv`, diffs; `_passed.flag` is **omitted**. 1A→1B hand-off is **disallowed** until fixed.

---

### 9) Practical guidance (non-normative but recommended)

* Treat schema failures and counter violations as **CI blockers**—catch them on small test shards.
* Keep a **golden KAT suite** exercising each failure class (§7) with tiny fixtures.
* When corridor breaches occur, surface **α-diagnostics** (expected attempts from $\alpha_m$) to highlight modelling drift vs. data shift.

---

## S2.9 — Outputs (state boundary) & hand-off to S3

### 1) Scope & intent (normative)

S2 closes by (i) **persisting only the authoritative RNG event streams** for the NB sampler and (ii) exporting the accepted domestic outlet count $N_m$ (and rejection tally $r_m$) **in-memory** to S3. **No Parquet data product** is written by S2. All persistence is via three JSONL **event** streams defined in the dictionary and validated against canonical schema anchors.

---

### 2) Persisted outputs (authoritative RNG event streams)

Write **exactly** these streams, **partitioned** by `["seed","parameter_hash","run_id"]`, with the indicated **schema refs**. Cardinalities are **hard** contracts:

1. **Gamma components (NB mixture)**
   Path: `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/gamma_component`
   Cardinality per multi-site merchant: **≥ 1** (one row **per attempt**).

2. **Poisson components (NB mixture)**
   Path: `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/poisson_component`
   Cardinality: **≥ 1** (one row **per attempt**). (This stream id is **reused by S4** with a different `context`, hence the dictionary description `NB composition / ZTP`.)

3. **NB final (accepted outcome)**
   Path: `logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
   Schema: `schemas.layer1.yaml#/rng/events/nb_final`
   Cardinality: **exactly 1** row **per merchant** (echoes `mu`, `dispersion_k`, `n_outlets`, `nb_rejections`).

**Envelope (must on every row).** `ts_utc, seed, parameter_hash, manifest_fingerprint, run_id, module, substream_label, rng_counter_before_lo, rng_counter_before_hi, rng_counter_after_lo, rng_counter_after_hi, blocks (uint64), draws ("uint128-dec")`. (`nb_final` is **non-consuming**: `before == after`, so `blocks=0`, `draws="0"`.)

**Payload (must).**

* `gamma_component`: `{ merchant_id, context="nb", index=0, alpha=φ_m, gamma_value }`.
* `poisson_component`: `{ merchant_id, context="nb", lambda, k }`.
* `nb_final`: `{ merchant_id, mu=μ_m, dispersion_k=φ_m, n_outlets=N_m, nb_rejections=r_m }`.
  Types & domains per schema (positivity for `mu`,`dispersion_k`; `n_outlets≥2`; `nb_rejections≥0`).

**Index semantics (binding).** For `gamma_component` with `context="nb"`, the Gamma is **scalar** per attempt; therefore
`index` is the fixed value **`0`** (scalar placeholder), not a component selector.

**Retention & lineage.** These streams are **not final in layer**, carry 180-day retention, and are produced by registry-closed producers (dictionary lineage): `gamma_component` → "1A.nb_and_dirichlet_sampler", `poisson_component` → "1A.nb_poisson_component", `nb_final` → "1A.nb_sampler".

---

### 3) In-memory export to S3 (contract)

For each merchant $m$ that **finalised** in S2:

$$
\boxed{\,N_m\in\{2,3,\dots\}\,}\quad\text{and}\quad \boxed{\,r_m\in\mathbb{Z}_{\ge 0}\,}.
$$

* $N_m$ = **authoritative** domestic outlet count for downstream branches; it **must not be re-sampled** downstream.
* $r_m$ = diagnostic only (corridor metrics); no modelling effect beyond validation.

**Downstream use.**

* **S3 (eligibility gate)** consumes $N_m$ to determine if the merchant may attempt cross-border (policy flags live in `crossborder_eligibility_flags`). S3 runs **only** for multi-site merchants that left S2.
* **S4 (ZTP)**, if eligible, will typically inject $\log N_m$ into its intensity for foreign count; S4 writes its **own** events but reuses the **Poisson component stream id** with `context="ztp"`.

---

### 4) Boundary invariants (must-hold at S2 exit)

1. **Coverage invariant.** If a merchant has an `nb_final`, there exist **≥1** `gamma_component` **and** **≥1** `poisson_component` rows (both with `context="nb"`) under the same envelope keys. Absence is a **structural failure**.

2. **Consumption discipline.** Per merchant and label, event counter intervals are **monotone & non-overlapping**; `nb_final` is **non-consuming** (`before==after`). (Checked in S2.6 and by the validator.)

3. **Composition identity.** For each attempt $t$: $\lambda_t = (\mu_m/\phi_m)\cdot \texttt{gamma_value}_t$ (ULP-tight). The `nb_final`’s `mu, dispersion_k` **equal** the S2.2 values.

4. **Cardinality.** Exactly **one** `nb_final` per `(seed, parameter_hash, run_id, merchant_id)`. **≥1** component rows per attempt; exactly **one** Gamma + **one** Poisson per attempt.

5. **Partitions & paths.** All three streams are written **only** under their dictionary paths and partitions; any deviation is a hard failure (`partition_misuse`).

---

### 5) Hand-off to S3 (operational)

**Eligibility of a merchant to enter S3:**

* Must have `is_multi=1` from S1 and a valid S2 `nb_final`. (Branch purity is enforced globally; single-site merchants must have **no** S2/S4–S6 events.)
* S3 receives $(N_m,r_m)$ **in-memory** and reads `crossborder_eligibility_flags(parameter_hash)` to determine the branch. **S3 persists nothing**; it fixes the policy branch that later must be reflected when `country_set` is materialised.

> **Note.** The **1A→1B hand-off** (egress consumption) is governed later by S9: `_passed.flag` must match `SHA256(validation_bundle_1A)` for the same fingerprint before 1B can read `outlet_catalogue`. S2 does not write egress and therefore cannot authorise 1B directly.

---

### 6) Writer reference pattern (idempotent; per merchant)

```pseudo
# Preconditions: merchant m is multi-site from S1; (mu, phi) evaluated in S2.2; RNG substreams established per S2.6.

# Attempt loop (S2.3/2.4) emits gamma_component then poisson_component per attempt (not repeated here).

# On acceptance:
N := accepted K_t   # K_t >= 2
r := t              # number of rejections

# Emit final (non-consuming) event:
envelope := current_envelope_with_counters()   # before == after (no extra draws here)
row := {
  merchant_id: m,
  mu: mu, dispersion_k: phi,
  n_outlets: N, nb_rejections: r
}
write_jsonl(
  path="logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl",
  envelope=envelope, payload=row
)

# Idempotency: the (seed, parameter_hash, run_id, merchant_id) key must not appear twice.
# Writers must dedupe on that composite key; validators hard-fail duplicate finals.
```

**Why non-consuming?** S2.5 records the acceptance and echoes parameters; all randomness was consumed in the attempts. Envelope equality proves it.

---

### 7) Validator obligations (S2-specific at boundary)

Before S3 consumes $(N_m,r_m)$ in-memory, the S2 validator must have already:

* **Schema-validated** all three streams.
* Checked **coverage & cardinality** and **consumption discipline**; verified **composition** identity per attempt.
* Computed **corridor metrics** $\widehat{\rho}_{\text{rej}}$, $p_{99}(r_m)$, and **CUSUM**; **hard-fail** on any breach.

---

### 8) Conformance tests (KATs for S2.9)

1. **Streams present & partitioned.** For a shard, assert that for every merchant with `nb_final`, there exist matching `gamma_component` and `poisson_component` rows under the same `(seed, parameter_hash, run_id)` partitions; no rows exist under any other path.

2. **Final echo & non-consumption.** For a sample of merchants, check `nb_final.mu == S2.2.mu` and `nb_final.dispersion_k == S2.2.phi`, and envelope counters are equal (`before==after`).

3. **Reconstruction of $(N_m,r_m)$.** Rebuild attempts by **counter-interval pairing** as above; confirm `nb_final.n_outlets == k` and the attempt index equals `nb_final.nb_rejections`.

4. **S3 readiness.** Ensure all `is_multi=1` merchants with `nb_final` also have a row in `crossborder_eligibility_flags(parameter_hash)`; single-site merchants have **no** S2 events.

---

### 9) Complexity & operational notes

* **I/O:** three append-only JSONL streams; per-merchant output is O(#attempts).
* **Memory:** O(1) for the writer at finalisation; S3 consumes only $(N_m,r_m)$.
* **Reuse:** The Poisson component stream id is deliberately shared with S4 (ZTP) via `context`, simplifying audit tooling.


[S2-END VERBATIM]


---

# S3 — Expanded
<a id="S3.EXP"></a>
<!-- SOURCE: /s3/states/state.1A.s3.expanded.txt  *  VERSION: v0.0.0 -->

[S3-BEGIN VERBATIM]

## S3.0) One-page quick map (for implementers)

### 0.1 What S3 does (one breath)

Given a gated **multi-site** merchant with accepted outlet count **N** from S2, **S3 deterministically builds the cross-border candidate country universe and its total order** (an ordered list with reasons/tags and, if enabled, deterministic base-weight priors). **S3 uses no RNG.** If your design keeps integerisation in S3, it converts priors to **integer per-country counts** that sum to **N** using the fixed largest-remainder discipline.

---

### 0.2 Inputs → Outputs (at a glance)

```
Ingress (read-only)                       S3 core (deterministic)                          Egress (authoritative)

S1 hurdle  ─┐
            ├─► Gate: is_multi == true ───┐
S2 nb_final │                             │
(N)         │   Policy artefacts &        │
            │   static refs (IDs only)    │
Merchant    ┘                             ▼
context  ────────────────────────►  S3.1 Rule ladder (deny ≻ allow ≻ class ≻ legal/geo ≻ thresholds)
                                     │
                                     ▼
                      S3.2 Candidate universe (home + admissible foreigns; tags/reasons)
                                     │
                                     ▼
                      S3.3 Ordering & tie-break (total order; candidate_rank(home)=0)
                                     │
                      ├──────────────┴──────────────┐
                      ▼                             ▼
        (optional) S3.4 Base-weight priors   (optional) S3.5 Integerisation to counts (sum = N)

                                             ▼
                                  ┌──────────────────────────────────────┐
                                  │ Outputs (dictionary-partitioned):    │
                                  │ • s3_candidate_set (ordered)         │
                                  │ • (opt) s3_base_weight_priors        │
                                  │ • (opt) s3_integerised_counts        │
                                  └──────────────────────────────────────┘
```

*Downstream reads the **ordered** candidate set; inter-country order lives **only** in `candidate_rank`.*

---

### 0.3 Bill of Materials (IDs only; no paths)

| Kind               | ID / Anchor                                 | Purpose                                         | Notes (semver / digest) |
|--------------------|---------------------------------------------|-------------------------------------------------|-------------------------|
| Dataset (upstream) | `schemas.layer1.yaml#/rng/events/nb_final`  | Source of **N** (accepted outlet count)         | From S2 run             |
| Dataset (upstream) | `schemas.ingress.layer1.yaml#/merchant_ids` | Merchant scope & keys                           | From S0                 |
| Policy artefact    | `policy.s3.rule_ladder.yaml`                | Ordered rules, precedence, reason codes         | Semver + SHA-256        |
| Static ref         | `iso3166_canonical_2024`                 | ISO3166 canonical list/order                    | Versioned snapshot      |
| Static ref         | `static.currency_to_country.map.json`       | Deterministic currency-to-country mapping       | Versioned snapshot      |
| (Optional) Params  | `policy.s3.base_weight.yaml`                | Deterministic prior formula/coeffs + dp         | Semver + SHA-256        |
| Output table       | `schemas.1A.yaml#/s3/candidate_set`         | Ordered candidates with `candidate_rank` & tags | New schema              |
| (Optional) Output  | `schemas.1A.yaml#/s3/base_weight_priors`    | Deterministic priors per candidate              | New schema              |
| (Optional) Output  | `schemas.1A.yaml#/s3/integerised_counts`    | Integer counts per country (sum=N)              | New schema              |

> All IO resolves via the **dataset dictionary**. **No hard-coded paths** in S3.

---

### 0.4 Control gates & invariants (must hold to run)

* **Presence gate:** exactly one S1 hurdle row and **`is_multi == true`** for the merchant.
* **S2 gate:** exactly one **`nb_final`** with **`N ≥ 2`** for the same `{seed, parameter_hash, run_id, merchant}`.
* **Artefact gates:** rule ladder + static refs **loaded atomically** with pinned versions/digests.
* **No RNG:** S3 defines **no RNG families** (no labels, no budgets, no envelopes).
* **Ordering law:** **`candidate_rank(home) = 0`**, ranks are **total** and **contiguous**; **no duplicates**.

---

### 0.5 Outputs (authoritative, dictionary-partitioned)

**Required**

* `s3_candidate_set` — rows:
  `merchant_id`, `country_iso`, **`candidate_rank`**, `reason_codes[]`, `filter_tags[]`, lineage fields.
  **Partition:** `{parameter_hash}`. **Embedded lineage:** includes `{manifest_fingerprint}`.
  **Row order guarantee:** `(merchant_id, candidate_rank, country_iso)`.

**Optional (enable only if S3 owns them)**

* `s3_base_weight_priors` — deterministic, quantised priors (dp is fixed in §12; **not probabilities**).
* `s3_integerised_counts` — integer counts per country with `residual_rank` if S3 performs integerisation (else defer downstream).

---

### 0.6 Definition of Done (tick before leaving S3)

* [ ] Every input/output cites a **JSON-Schema anchor** (no prose names).
* [ ] Rule ladder is **ordered** with explicit precedence and closed **reason codes**.
* [ ] Candidate construction is **deterministic**; **tie-break** and **quantisation dp** (if any) are stated.
* [ ] **Total order** proven: `candidate_rank(home)=0`, contiguous ranks, no duplicates.
* [ ] If priors exist: formula, units, bounds, **evaluation order**, and **dp** fixed.
* [ ] If integerising: **largest-remainder**, **lexicographic ISO** tie-break, and `residual_rank` persisted; **Σ counts = N**.
* [ ] Partitions & embedded lineage fixed for each dataset; **no path literals**.
* [ ] Non-emission failure shapes listed (`ERR_S3_*`, merchant-scoped).
* [ ] Two tiny **worked examples** included (illustrative row shapes).

---

## S3.1) Interfaces (hard contracts)

### 1.1 Upstream interface (read-only)

**Purpose:** define the **closed** set of inputs S3 may read. No alternative sources; no re-deriving.

| Source                                 | JSON-Schema anchor (authoritative)                      | Required columns (name : type)                                                                                          | Invariants & notes                                                        | Cardinality (per merchant, within `{seed, parameter_hash, run_id}`) |
|----------------------------------------|---------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------|---------------------------------------------------------------------|
| Merchant scope                         | `schemas.ingress.layer1.yaml#/merchant_ids`             | `merchant_id:u64`, `home_country_iso:string(ISO-3166-1)`, `mcc:string`, `channel:(ingress schema’s closed vocabulary)`  | `home_country_iso` must be ISO; `channel` in the closed vocabulary        | **Exactly 1**                                                       |
| Hurdle decision (S1)                   | `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`      | `merchant_id:u64`, `is_multi:bool` plus standard envelope/lineage fields                                                | Presence **required**; **gate:** `is_multi==true`                         | **Exactly 1**                                                       |
| Accepted outlet count (S2)             | `schemas.layer1.yaml#/rng/events/nb_final`              | `merchant_id:u64`, `n_outlets:i64 (≥2)` plus standard envelope/lineage fields                                           | Finaliser is **non-consuming**; `n_outlets ≥ 2` to enter S3               | **Exactly 1**                                                       |
| Policy: S3 rule ladder                 | `artefact_registry_1A.yaml:policy.s3.rule_ladder.yaml`  | `rules[]` (ordered), `precedence`, `reason_codes[]` (**closed set**), validity window                                   | Load **atomically**; precedence is **total**; reason codes are **closed** | **Exactly 1** artefact                                              |
| Static refs (ISO, etc.)                | `iso3166_canonical_2024`                                | `iso_alpha2:string`, `iso_alpha3:string`, canonical ISO ordering                                                        | Versioned snapshot; no mutation                                           | **Exactly 1** artefact                                              |
| Currency→country map (if used)         | `static.currency_to_country.map.json`                   | `currency_code:string` → `countries:[iso_alpha2]`                                                                       | Deterministic map; **no RNG** smoothing                                   | **Exactly 1** artefact                                              |
| (Optional) deterministic weight params | `policy.s3.base_weight.yaml`                            | explicitly named coefficients/thresholds; **units & bounds**                                                            | Only authority if S3 computes deterministic priors                        | **0 or 1** artefact                                                 |

**Path resolution:** via the **dataset dictionary** only; **no hard-coded paths**.

**Partition equality (read side):** embedded `{seed, parameter_hash, run_id}` in S1/S2 events must **byte-equal** their path partitions.

**RNG note:** S3 defines **no RNG families** (no labels, no budgets, no envelopes).

---

### 1.2 Downstream interface (egress S3 produces)

**Purpose:** define exactly what S3 emits and how consumers must read it. Consumers **must not** infer or reinterpret beyond this.

#### 1.2.1 Required: ordered candidate set

| Dataset id         | JSON-Schema anchor                  | Partitions (path)    | Embedded lineage (columns)                           | Row order                                                                                      | Columns (name : type : semantics)                                                                                                                                                                                                                                                                                                 |
|--------------------|-------------------------------------|----------------------|------------------------------------------------------|------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `s3_candidate_set` | `schemas.1A.yaml#/s3/candidate_set` | `parameter_hash={…}` | `manifest_fingerprint:hex64`, `parameter_hash:hex64` | **Row ordering guarantee (logical):** `(merchant_id ASC, candidate_rank ASC, country_iso ASC)` | `merchant_id:u64` — key; `country_iso:string(ISO-3166-1)` — candidate; **`candidate_rank:u32`** — **total, contiguous order** with `candidate_rank==0` for home; `reason_codes:array<string>` — **closed set** from policy; `filter_tags:array<string>` — deterministic tags (**closed set** defined by policy); lineage as above |

**Contract:**

* **Total order:** `candidate_rank` is total and contiguous per merchant; **no duplicates**; **`candidate_rank(home)=0`**.
* **No priors here:** deterministic priors (if enabled) are emitted only in **`s3_base_weight_priors`** (§12.3).
* **Single authority for inter-country order:** downstream **must use `candidate_rank` only** (never file order or ISO).

#### 1.2.2 Optional: deterministic base-weight priors (if enabled)

| Dataset id              | JSON-Schema anchor                       | Partitions           | Embedded lineage                         | Row order                    | Columns                                                                                                           |
|-------------------------|------------------------------------------|----------------------|------------------------------------------|------------------------------|-------------------------------------------------------------------------------------------------------------------|
| `s3_base_weight_priors` | `schemas.1A.yaml#/s3/base_weight_priors` | `parameter_hash={…}` | `manifest_fingerprint`, `parameter_hash` | `(merchant_id, country_iso)` | `merchant_id:u64`, `country_iso:string`, `base_weight_dp:decimal(string)`, `dp:u8` (quantisation places), lineage |

**Contract:** evaluation order and quantisation **dp** fixed in §12; consumers treat as **deterministic scores** only.

#### 1.2.3 Optional: integerised counts (if S3 performs integerisation)

| Dataset id              | JSON-Schema anchor                       | Partitions           | Embedded lineage                         | Row order                    | Columns                                                                                                              |
|-------------------------|------------------------------------------|----------------------|------------------------------------------|------------------------------|----------------------------------------------------------------------------------------------------------------------|
| `s3_integerised_counts` | `schemas.1A.yaml#/s3/integerised_counts` | `parameter_hash={…}` | `manifest_fingerprint`, `parameter_hash` | `(merchant_id, country_iso)` | `merchant_id:u64`, `country_iso:string`, `count:i64 (≥0)`, `residual_rank:u32` (largest-remainder tie rank), lineage |

**Contract:**

* Per merchant, `Σ count = N` from S2.
* `residual_rank` captures the exact bump order (quantised residuals + ISO tiebreak) and is **persisted**.

---

### 1.3 Immutability & non-reinterpretation (binding)

**What S3 must not reinterpret**

* **Upstream decisions:** S1 hurdle (`is_multi`) and S2 `nb_final.n_outlets` are **authoritative**; S3 **must not** recompute or override them.
* **Upstream numerics:** inherit S0 numeric policy (binary64, RNE, FMA-off, no FTZ/DAZ).

**What downstream must not reinterpret**

* **Inter-country order:** lives **only** in `s3_candidate_set.candidate_rank`.
* **Priors (if any):** `base_weight_dp` are deterministic **priors**, not probabilities; consumers must not normalise or treat them as stochastic unless a later state explicitly says so.
* **Integerised counts (if emitted):** are **final for S3**; later stages treat them as read-only unless a new fingerprint changes.

**Partition ↔ embed equality (write side)**

* All S3 tables are partitioned by **`parameter_hash`** (no `seed`); each row **embeds** `parameter_hash` and `manifest_fingerprint`. Embedded values must **byte-equal** the path partition and the run’s fingerprint.

**No paths in code**

* All IO resolves via the **dataset dictionary**. This spec names **dataset IDs and schema anchors only**.

---

## S3.2) Bill of Materials (BOM)

> **Goal:** freeze *exactly* what S3 may open and the versioning/lineage rules that make runs reproducible. If it isn’t listed here, S3 must not read it.

### 2.1 Governed artefacts (authorities S3 must open atomically)

| Artefact (registry id)                | Purpose in S3                                                                                                          | SemVer | Digest (SHA-256, hex64) | Evidence / Notes                                           |
|---------------------------------------|------------------------------------------------------------------------------------------------------------------------|-------:|-------------------------|------------------------------------------------------------|
| `policy.s3.rule_ladder.yaml`          | Ordered deterministic rules (deny ≻ allow ≻ class ≻ legal/geo ≻ thresholds), precedence law, **closed** `reason_codes` |  x.y.z | …                       | Must be **total order**; reason codes are a **closed set** |
| `iso3166_canonical_2024`              | ISO-3166-1 alpha-2/alpha-3 canonical list + canonical ISO order                                                        |  x.y.z | …                       | Versioned snapshot; no mutation                            |
| `static.currency_to_country.map.json` | Deterministic **currency-to-country** mapping (if used by rules)                                                       |  x.y.z | …                       | Deterministic only; **no RNG** smoothing                   |
| `schemas.layer1.yaml`                 | **JSON-Schema source of truth** (includes all `#/s3/*` anchors)                                                        |  x.y.z | …                       | Schema authority; Avro (if any) is build-artefact only     |
| `schema.index.layer1.json` *(opt)*    | **Derived** schema index for faster lookups (non-authoritative)                                                        |  x.y.z | …                       | Convenience only                                           |
| `dataset_dictionary.layer1.1A.yaml`   | Dataset IDs → partition spec → physical path template                                                                  |  x.y.z | …                       | Resolves *all* IO; **no hard-coded paths**                 |
| `artefact_registry_1A.yaml`           | Full registry (this BOM appears in it)                                                                                 |  x.y.z | …                       | Names, semver, digests must match this table               |

**Atomic open:** S3 **must** open all artefacts above *before* any processing and record their `(id, semver, digest)` into the run’s `manifest_fingerprint`.

---

### 2.2 Datasets consumed from prior states (read-only)

| Dataset id                        | JSON-Schema anchor                                 | Partition keys (path)            | Embedded lineage (must equal)    | Used fields                                         |
|-----------------------------------|----------------------------------------------------|----------------------------------|----------------------------------|-----------------------------------------------------|
| `rng_event_hurdle_bernoulli` (S1) | `schemas.layer1.yaml#/rng/events/hurdle_bernoulli` | `{seed, parameter_hash, run_id}` | `{seed, parameter_hash, run_id}` | `merchant_id`, payload `is_multi`                   |
| `rng_event_nb_final` (S2)         | `schemas.layer1.yaml#/rng/events/nb_final`         | `{seed, parameter_hash, run_id}` | `{seed, parameter_hash, run_id}` | `merchant_id`, payload `n_outlets` (≥2)             |
| `merchant_ids` (S0)               | `schemas.ingress.layer1.yaml#/merchant_ids`        | registry-defined                 | —                                | `merchant_id`, `home_country_iso`, `mcc`, `channel` |

**Read-side law:** for S1/S2 events, **embedded** `{seed, parameter_hash, run_id}` must **byte-equal** the path partitions.

---

### 2.3 Optional parameter bundles (only if S3 computes deterministic priors)

| Artefact (registry id)       | Purpose                                               | SemVer | Digest (SHA-256) | Notes                                            |
|------------------------------|-------------------------------------------------------|-------:|------------------|--------------------------------------------------|
| `policy.s3.base_weight.yaml` | Deterministic prior formula, constants/coeffs, **dp** |  x.y.z | …                | **No RNG**; evaluation order & **dp** in §12     |
| `policy.s3.thresholds.yaml`  | Deterministic cutoffs (GDP floors, market limits)     |  x.y.z | …                | If used by the rule ladder; closed numbers+units |

If you **do not** compute deterministic priors in S3, omit this subsection (do **not** keep unused knobs).

---

### 2.4 Outputs S3 produces (tables — shape authorities)

| Output dataset                | JSON-Schema anchor                       | Partition keys (path) | Embedded lineage                         | Consuming notes                                                                                      |
|-------------------------------|------------------------------------------|-----------------------|------------------------------------------|------------------------------------------------------------------------------------------------------|
| `s3_candidate_set`            | `schemas.1A.yaml#/s3/candidate_set`      | `parameter_hash`      | `manifest_fingerprint`, `parameter_hash` | **Inter-country order lives only in `candidate_rank`**; `candidate_rank(home)=0`; total & contiguous |
| (opt) `s3_base_weight_priors` | `schemas.1A.yaml#/s3/base_weight_priors` | `parameter_hash`      | `manifest_fingerprint`, `parameter_hash` | Deterministic, quantised **priors** (not probabilities); join on `(merchant_id, country_iso)`        |
| (opt) `s3_integerised_counts` | `schemas.1A.yaml#/s3/integerised_counts` | `parameter_hash`      | `manifest_fingerprint`, `parameter_hash` | Counts per country; **Σ count = N (from S2)**; persist `residual_rank`                               |

> **Single source of truth for priors:** We keep priors in **`s3_base_weight_priors`** only (no `base_weight_dp` column in `s3_candidate_set`) to avoid duplication and drift.

**Write-side law:** path partitions and embedded lineage must **match byte-for-byte**. **No `seed`** in S3 partitions.

---

### 2.5 Lineage & fingerprint rules (binding)

* **`parameter_hash`** = hash of *parameter* artefacts (e.g., rule ladder, thresholds, prior coeffs). Changing it **re-partitions** parameter-scoped outputs.
* **`manifest_fingerprint`** = composite of **all opened artefacts** (this BOM), plus parameter bytes and git commit (as your project defines). It is **embedded** in every S3 row.
* **Inclusion rule (explicit):** the following **must** contribute to `manifest_fingerprint`:
  `policy.s3.rule_ladder.yaml`, `iso3166_canonical_2024`, `static.currency_to_country.map.json` (if used),
  `schemas.layer1.yaml` (and `schema.index.layer1.json` if used), `dataset_dictionary.layer1.1A.yaml`, `artefact_registry_1A.yaml`, and any artefact in §2.3.
  Missing inclusion ⇒ **abort**.
* **No path literals:** all IO resolves via the dataset dictionary; paths never appear in code or outputs.

---

### 2.6 Validity windows & version pinning

| Artefact                              | Valid from | Valid to   | Action on out-of-window      |
|---------------------------------------|------------|------------|------------------------------|
| `policy.s3.rule_ladder.yaml`          | YYYY-MM-DD | YYYY-MM-DD | **Abort** (binding policy)   |
| `iso3166_canonical_2024`              | YYYY-MM-DD | YYYY-MM-DD | **Warn + abort** if mismatch |
| `static.currency_to_country.map.json` | YYYY-MM-DD | YYYY-MM-DD | **Abort** if version drifts  |

If no validity windows are governed for an artefact, state: **“No validity window — pinned by digest only (binding).”**

---

### 2.7 Licensing & provenance (must be auditable)

| Artefact                              | Licence                                | Provenance URL / descriptor | Notes                                       |
|---------------------------------------|----------------------------------------|-----------------------------|---------------------------------------------|
| `iso3166_canonical_2024`              | e.g., “ISO data under licence …”       | …                           | Attach licence text in repo if required     |
| `policy.s3.rule_ladder.yaml`          | Project licence (e.g., MIT/Apache-2.0) | internal                    | Generated artefact; provenance = commit SHA |
| `static.currency_to_country.map.json` | e.g., ODbL / CC-BY / internal          | …                           | Ensure redistribution rights are clear      |

If external licences restrict redistribution, record the policy you follow (e.g., embed digests, not full copies).

---

### 2.8 Open/verify checklist (run-time gates)

* [ ] **Open all governed artefacts** in §2.1 and record `(id, semver, digest)`.
* [ ] **Resolve datasets via dictionary**; **no literal paths**.
* [ ] **Equality check** path partitions ↔ embedded lineage for S1/S2 inputs.
* [ ] **Fingerprint inclusion test:** all artefact digests listed in §2.5 are included in `manifest_fingerprint`.
* [ ] **Closed vocab check:** `reason_codes` (policy), `filter_tags` (policy), channels (ingress schema closed vocabulary), ISO set.
* [ ] **Version pin check:** artefacts within validity windows (if defined) or explicitly “digest-pinned only”.
* [ ] **No RNG in S3:** confirm **no RNG families/labels** are referenced anywhere in S3 (events, budgets, envelopes).
* [ ] **Abort vocabulary loaded:** `ERR_S3_*` symbols available to callers.

---

> **Practical note:** This BOM is intentionally minimal but binding. If later sections call for an artefact or parameter not listed here, either (a) add it here with semver/digest, or (b) remove the dependency. No “ghost inputs.”

---

## S3.3) Determinism & numeric policy (carry-forward)

### 3.1 Scope (what this section fixes)

These rules are **definition-level**. If any item below is violated, S3’s outputs are **out of spec** (even if the program “works”).

* Applies to **all** numeric work in S3 (feature transforms, thresholds, base-weight priors, ordering keys, integerisation residuals).
* **S3 uses no RNG.** If a future variant introduces RNG, it **must** adopt L0’s RNG/trace surfaces verbatim (see §3.7).

---

### 3.2 Floating-point environment (binding)

* **Format:** IEEE-754 **binary64** (`f64`) for all real computations and emitted JSON numbers.
* **Rounding mode:** **Round-to-Nearest, ties-to-Even (RNE)**.
* **FMA:** **disabled** (no fused multiply-add).
* **Denormals:** **no FTZ/DAZ** (do not flush subnormals to zero).
* **Shortest-round-trip emission:** emit `f64` as JSON **numbers** (not strings) using shortest round-trip formatting.

> Implementation: pin a math/runtime profile that guarantees the above; do not rely on host defaults.

---

### 3.3 Evaluation order & reductions

* **Evaluation order is normative.** Evaluate formulas in the **spelled order**; no algebraic reordering or “fast-math”.
* **Reductions:** when summing/aggregating, use **serial Neumaier** in the **documented iteration order** (explicitly: the order defined by the section that invokes the reduction).
* **Clamp / winsorise / quantise:** apply **exactly** in the written sequence (e.g., compute → clamp → **quantise**)—never fused.

---

### 3.4 Total-order sorting (stable & reproducible)

Whenever S3 requires ordering (e.g., candidate ordering, residual ranking), apply a **total order**:

1. Primary key(s) as specified for that step. **For candidate ordering, see §9 (admission-order key; priors are not used).** Other sorts (e.g., residual ranking) follow the keys stated in their sections.
2. If equal **after any required quantisation**, fall back to **ISO code** (`iso_alpha2`, ASCII A–Z).
3. If still tied: break by `merchant_id` ↑ then **original index** (stable: input sequence index in that step’s source list).

All sorts must be **stable** when keys compare equal.

---

### 3.5 Quantisation & dp policy

* If S3 computes deterministic **priors/scores**, it must **quantise** them to a fixed **decimal dp** **before** they are used for numeric steps (e.g., residual ordering in §10)—**not** for candidate ordering (see §9).
* The **dp value** for each context is declared once in that context’s section (e.g., §12 if priors exist).
* Quantise via `round_to_dp(value, dp)` under RNE, then use the **quantised** number for downstream sort/ties.

**Decimal rounding algorithm (binding):**
Let `s = 10^dp`. Compute `q = round_RNE(value * s) / s` in binary64, where `round_RNE` is ties-to-even on the **binary64** value of `value * s`. The emitted field is the binary64 `q` (or its shortest JSON representation if serialized).

*If a value is emitted as a **prior**, its on-disk representation is the **fixed-dp decimal string** defined in §12.3; the binary64 `q` above is for in-memory computation only.*

---

### 3.6 Integerisation residuals (only if S3 allocates counts)

* **Residuals:** compute residuals **after dp-quantisation** of any priors used for fractional shares.
* **Residual ranking:** sort **descending** by residual; tiebreak by **ISO code** (alpha-2, ASCII A–Z). Persist `residual_rank` if integerisation is emitted.
* **Bump discipline:** add +1 to the top `R` residuals until integer totals sum to **N** (from S2). (State where `R` comes from in the integerisation section.)

---

### 3.7 Optional RNG clause (future-proof, off by default)

* **Default:** **No RNG families** in S3. No event envelopes, no `draws/blocks`, no trace rows.
* **If (and only if) S3 ever adds RNG:**

  * Use L0’s writer/trace surface; events under `{seed, parameter_hash, run_id}`; embed `manifest_fingerprint`.
  * Fix `substream_label` names; document **budget law** (draws vs blocks) and **consuming status** for each family.
  * **Guard-before-emit**: compute all predicates that can invalidate an attempt **before** emitting any event.

*(This subsection is a guardrail; today it’s a no-op.)*

---

### 3.8 Path↔embed equality & lineage keys

* Every S3 output row **embeds** `{parameter_hash, manifest_fingerprint}` that must **byte-equal** the path partition (`parameter_hash`) and the run’s fingerprint.
* S3 outputs are **parameter-scoped** (no `seed` in partitions).
* **No path literals**: all IO resolves via the **dataset dictionary**.

---

### 3.9 Compliance self-check (tick at build/run)

* [ ] Process uses **binary64, RNE, FMA-off, no FTZ/DAZ**.
* [ ] Formulas follow **spelled evaluation order**; Neumaier used where specified.
* [ ] All ordering uses the **total-order stack** in §3.4; sorts are **stable**.
* [ ] Any priors/scores used in **numeric steps** (e.g., integerisation shares) were **quantised to dp** first (dp declared). *(Candidate ordering does **not** use priors; see §9.)*
* [ ] If integerising: residuals computed **after** dp; **ISO alpha-2** tiebreak; `residual_rank` persisted (if emitted).
* [ ] Outputs embed lineage matching path partitions; **no path literals** anywhere.
* [ ] RNG: **absent** in S3 (or, if later enabled, L0 surfaces + guard-before-emit are in place).

---

## S3.4) Symbols & vocab (legend)

### 4.1 Scalar symbols (used throughout S3)

| Symbol             | Type                                   | Meaning                                                                                        | Bounds / Notes                                                                                                                                                |
|--------------------|----------------------------------------|------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `N`                | `i64`                                  | Total outlets accepted for the merchant from S2 `nb_final.n_outlets`                           | `N ≥ 2`                                                                                                                                                       |
| `K`                | `u32`                                  | Number of **foreign** countries admitted into the candidate set (after rules)                  | `K ≥ 0` (if cross-border not eligible ⇒ `K = 0`)                                                                                                              |
| `w_i`              | `f64`                                  | Deterministic base score/weight for country `i` (if §12 enabled) **before quantisation**       | Units & evaluation order fixed in §12                                                                                                                         |
| `w_i^⋄`            | `f64` (quantised) or `decimal(string)` | `w_i` **after** quantisation to `dp` decimal places (see §3.5, §12)                            | Used for **integerisation/residual ordering** (§10); **not** used for candidate ordering (§9). If emitted (priors table), use decimal string with fixed `dp`. |
| `ρ_i`              | `f64`                                  | Residual for country `i` in integerisation (if §13 used) computed **after** quantising weights | Used only for residual ranking                                                                                                                                |
| `candidate_rank_i` | `u32`                                  | Total order position for country `i` in the candidate set                                      | `candidate_rank(home) = 0`; contiguous; no ties                                                                                                               |
| `dp`               | `u8`                                   | Decimal places used to quantise `w` (if priors exist)                                          | Declared once in §12                                                                                                                                          |
| `ε`                | `f64`                                  | Small closed-form constants if needed (e.g., clamp)                                            | Declared where used; hex literal                                                                                                                              |

**Type conventions:** `u64` unsigned 64-bit, `i64` signed 64-bit, `u32/u8` unsigned, `f64` IEEE-754 binary64 (RNE, FMA-off; §3).

---

### 4.2 Sets, indices, and keys

| Symbol         | Type                          | Meaning                                                        | Notes                      |
|----------------|-------------------------------|----------------------------------------------------------------|----------------------------|
| `C`            | set of ISO country codes      | The admissible **country universe** for a merchant after rules | `home ∈ C` always          |
| `home`         | `string` (ISO-3166-1 alpha-2) | Merchant’s home country from ingress                           | Uppercase `A–Z`            |
| `i, j`         | index                         | Index over countries in `C`                                    | Used consistently in loops |
| `merchant_id`  | `u64`                         | Canonical merchant identifier (from ingress)                   | Key in all S3 outputs      |
| `merchant_u64` | `u64`                         | Derived key per S0 (read-only)                                 | Not recomputed here        |

---

### 4.3 Deterministic priors / weights (if enabled)

* **Symbols:** `w_i` (pre-quantisation), `w_i^⋄` (post-quantisation).
* **Evaluation order:** exactly as written in §12 (no re-ordering).
* **Quantisation:** `w_i^⋄ = round_to_dp(w_i, dp)` under binary64 RNE (see §3.5).
* **Emission:** if persisted, emit `w_i^⋄` in **`s3_base_weight_priors`** as a **decimal string** with exactly `dp` places; do **not** emit raw `w_i`.

> **No stochastic meaning:** `w` are **deterministic priors/scores**, **not probabilities**.

---

### 4.4 Ordering & tie-breaker keys (total order contract)

When S3 requires a total order over countries:

1. **Primary key(s)** as specified in the relevant section. **For candidate ordering, §9 applies (admission-order key; priors not used).** For residual ranking see §10.5.
2. **Secondary (stable) key:** `country_iso` **lexicographic A–Z**.
3. **Tertiary (stable) key:** `merchant_id` then original input index (stable: input sequence index).

This yields a **total, contiguous ranking** `candidate_rank_i ∈ {0,1,…,|C|−1}`, with **`candidate_rank(home) = 0`**. (See **§9.4** proof obligation.)

---

### 4.5 Closed vocabularies & identifiers

| Vocabulary       | Values (closed set)                                                                                 | Where used                  | Notes                                                  |
|------------------|-----------------------------------------------------------------------------------------------------|-----------------------------|--------------------------------------------------------|
| `channel`        | `(closed vocabulary from ingress schema)`                                                           | Read from ingress in §2     | Case-sensitive; order fixed                            |
| `reason_codes`   | e.g., `["DENY_SANCTIONED","ALLOW_WHITELIST","CLASS_RULE_XYZ","LEGAL_EXCLUSION","THRESHOLD_LT_GDP"]` | Emitted with candidate rows | **Closed set** defined by `policy.s3.rule_ladder.yaml` |
| `rule_id`        | e.g., `"RL_DENY_SANCTIONED"`, `"RL_CLASS_MCC_XXXX"`                                                 | Rule ladder trace & tags    | Stable identifiers; no spaces                          |
| `filter_tags`    | e.g., `"SANCTIONED"`, `"GEO_OK"`, `"ADMISSIBLE"`                                                    | Candidate tagging           | Deterministic, documented list                         |
| `country_iso`    | ISO-3166-1 alpha-2                                                                                  | All S3 tables               | Uppercase `A–Z`; canonical ISO list from artefact      |
| `candidate_rank` | non-negative integer                                                                                | `s3_candidate_set`          | `candidate_rank(home)=0`; no gaps                      |

> The exact **enumerations** for `reason_codes`, `rule_id`, and `filter_tags` are defined in the policy artefact (§2.1). S3 treats them as **closed**; encountering an unknown code is a **failure**.

---

### 4.6 Encodings & JSON types

| Field                                    | JSON type         | Encoding details                                         |
|------------------------------------------|-------------------|----------------------------------------------------------|
| `f64` payload numbers                    | **number**        | Shortest round-trip decimal (never strings)              |
| `base_weight_dp` (in priors table)       | **string**        | Decimal string with exactly `dp` places (deterministic)  |
| `manifest_fingerprint`, `parameter_hash` | **string**        | Lowercase hex (`Hex64`); fixed length                    |
| `country_iso`                            | **string**        | Uppercase ISO-3166-1 alpha-2                             |
| `reason_codes`, `filter_tags`            | **array<string>** | Each element in **closed set**; order preserved (stable) |
| `candidate_rank`, `residual_rank`        | **integer**       | Non-negative; `candidate_rank` contiguous from 0         |

---

### 4.7 Units, bounds, and invariants (quick checks)

* `N` from S2: integer, **`N ≥ 2`**.
* `K`: integer, `K ≥ 0`; if cross-border not eligible ⇒ `K = 0`.
* Candidate set: **non-empty**; contains `home`.
* `candidate_rank`: contiguous per merchant; **no duplicates**, **no ties**.
* If integerising in S3: `∑_i count_i = N`; `count_i ≥ 0`; `residual_rank` persisted (unique per merchant–country).
* If priors exist: `dp` stated; **quantise before** any ordering or residual logic.

---

### 4.8 Shorthand functions (names used later)

| Name                    | Signature                         | Meaning                                                     |
|-------------------------|-----------------------------------|-------------------------------------------------------------|
| `round_to_dp`           | `(x:f64, dp:u8) -> f64`           | Quantise to `dp` decimals under RNE (binary64)              |
| `iso_lex_less`          | `(a:string, b:string) -> bool`    | `true` iff `a` < `b` in A–Z lexicographic order             |
| `assign_candidate_rank` | `(C:list) -> list<u32>`           | Produce contiguous ranks using §4.4 total-order             |
| `residual_rank_sort`    | `(ρ:list, iso:list) -> list<u32>` | Sort residuals desc; ISO-lex tie-break; return stable ranks |

*(Symbolic names; concrete implementations live in L0/L1 as appropriate.)*

---

## S3.5) Control flow (S3 only)

### 5.1 Mini-DAG (one merchant, deterministic)

```
Ingress (read-only)                 S3 pipeline (deterministic)                          Egress (authoritative)

S1 hurdle ─┐
           ├─ is_multi == true ? ──► [ENTER S3]
S2 nb_final│
(N ≥ 2)    │
Merchant   ┘
context         ┌────────────────┐    ┌──────────────────────────┐   ┌───────────────────────────┐
                │ S3.0 Load ctx  │ →  │ S3.1 Rule ladder (deny…) │ → │ S3.2 Candidate universe   │
                └────────────────┘    └──────────────────────────┘   └──────────────┬────────────┘
                                                                                    │
                                                                                    ▼
                                                        ┌───────────────────────────┐
                                                        │ S3.3 Order & rank (total) │
                                                        └──────────────┬────────────┘
                                                                       │
                        (optional, if enabled)                         ▼
                   ┌───────────────────────────┐        ┌────────────────────────────┐
                   │ S3.4 Base-weight priors   │  →     │ S3.5 Integerise to counts  │
                   └──────────────┬────────────┘        └───────────────┬────────────┘
                                  │                                     │
                                  └──────────────┬──────────────────────┘
                                                 ▼
                                      ┌──────────────────────────────┐
                                      │ S3.6 Emit tables             │
                                      │ (candidate_set, opt. priors/ │
                                      │  opt. integerised_counts)    │
                                      └──────────────────────────────┘
```

**Writes:** only in **S3.6** (tables). **No RNG**; no event streams.

---

### 5.2 Step-by-step (inputs → outputs → side-effects)

#### S3.0 Load context (deterministic)

* **Inputs:** merchant row (ingress), S1 hurdle (`is_multi == true`), S2 `nb_final` (`N ≥ 2`), governed artefacts opened atomically (BOM §2).
* **Outputs:**
  `Ctx = { merchant_id, home_country_iso, mcc, channel, N, artefact_versions, parameter_hash, manifest_fingerprint }`.
* **Side-effects:** none (read-only).
* **Fail:** missing/invalid artefact or gates ⇒ `ERR_S3_AUTHORITY_MISSING` (stop merchant).

#### S3.1 Rule ladder (deterministic policy)

* **Inputs:** `Ctx`, rule-ladder artefact.
* **Algorithm:** evaluate **ordered** rules (deny ≻ allow ≻ class ≻ legal/geo ≻ thresholds) per precedence; record `rule_id` & `reason_code`.
* **Outputs:** `RuleTrace` (ordered list) and `eligible_crossborder: bool`.
* **Side-effects:** none.
* **Fail:** unknown `rule_id`/`reason_code` ⇒ `ERR_S3_RULE_LADDER_INVALID`.

#### S3.2 Candidate universe construction (deterministic)

* **Inputs:** `Ctx`, `RuleTrace`, static refs (ISO; currency-to-country map if used).
* **Algorithm:** start set `{home}`; if `eligible_crossborder`, add admissible foreign ISO codes; de-dup; tag with deterministic `filter_tags` & `reason_codes`.
* **Outputs:** `C` = list of candidate rows (unordered yet) with tags per row.
* **Side-effects:** none.
* **Fail:** empty `C` or missing `home` ⇒ `ERR_S3_CANDIDATE_CONSTRUCTION`.

#### S3.3 Order & rank (total order; deterministic)

* **Inputs:** `C`.
* **Algorithm:** apply the **admission-order comparator** of §9 (priors are **not** used for ranking), then **ISO lexicographic** tie-break, then stability. Produce contiguous **`candidate_rank`** with **`candidate_rank(home) = 0`**.
* **Outputs:** `C_ranked = C + candidate_rank`.
* **Side-effects:** none.
* **Fail:** duplicate ranks ⇒ **`ERR_S3_ORDERING_NONCONTIGUOUS`**;
  missing `candidate_rank(home)=0` ⇒ **`ERR_S3_ORDERING_HOME_MISSING`**.

> If S3 **does not** compute priors, **skip S3.4**.

#### S3.4 Base-weight priors (deterministic; optional)

* **Inputs:** `C_ranked`, `policy.s3.base_weight.yaml`.
* **Algorithm:** compute `w_i` per §12 in **spelled evaluation order**; **quantise** to `dp` ⇒ `w_i^⋄`; attach to each candidate (for the priors table).
* **Outputs:** `C_weighted = C_ranked + w_i^⋄` (for emission only; priors live in their own table).
* **Side-effects:** none.
* **Fail:** unknown coeff/param or missing `dp` ⇒ `ERR_S3_WEIGHT_CONFIG`.

> If S3 **does not** integerise, **skip S3.5**.

#### S3.5 Integerise to counts (optional; sum to N)

* **Inputs:** `C_weighted` (or `C_ranked` if no priors), `N`.
* **Algorithm:** largest-remainder: floor, compute residuals **after** dp (if any), sort residuals **desc** with ISO tie-break, bump +1 until Σ count = `N`; persist `residual_rank`.
* **Outputs:** `C_counts` = per-country `count` (≥0) summing to `N`, plus `residual_rank`.
* **Side-effects:** none.
* **Fail:** Σ `count` ≠ `N` ⇒ `ERR_S3_INTEGER_SUM_MISMATCH`;
  any `count < 0` ⇒ `ERR_S3_INTEGER_NEGATIVE`.

#### S3.6 Emit tables (authoritative)

* **Inputs:** whichever of `C_ranked` / `C_weighted` / `C_counts` applies; `Ctx` lineage keys.
* **Algorithm:** write **tables** via dictionary-resolved paths, partitioned by **`parameter_hash`**; embed `{parameter_hash, manifest_fingerprint}` (must byte-equal path partition and run fingerprint).
* **Outputs (tables):**

  * **Required:** `s3_candidate_set` (ranked, tagged candidates with `candidate_rank`).
  * **Optional:** `s3_base_weight_priors` (if S3.4 ran; emit `w_i^⋄` as **decimal string** with exactly `dp` places) and/or `s3_integerised_counts` (if S3.5 ran; includes `residual_rank`).
* **Side-effects:** none beyond writes (no RNG events).
* **Fail:** path↔embed mismatch or schema violation ⇒ `ERR_S3_EGRESS_SHAPE`.

---

### 5.3 Looping & stopping conditions

* **Per merchant:** S3 runs **once**; there are **no stochastic attempts**.
* **Stop-early:** if rule ladder denies cross-border, candidate set is `{home}` with `candidate_rank=0`; optional steps (priors, integerisation) still obey invariants.

---

### 5.4 Concurrency & idempotence

* **Read joins:** keyed by `{seed, parameter_hash, run_id, merchant_id}` for S1/S2 inputs (equality on path↔embed).
* **Outputs:** **parameter-scoped** only (partitioned by `parameter_hash`); S3 has **no finaliser**.
* **Parallelism invariance:** deterministic, no RNG ⇒ re-partitioning/concurrency **cannot** change bytes.

---

### 5.5 Evidence cadence (what is written where)

* **Events:** none in S3.
* **Tables (only in S3.6):** fully-qualified JSON-Schema anchors; numbers as JSON numbers; **priors** (if emitted) as **decimal strings** with fixed `dp` in **`s3_base_weight_priors`**.

---

## S3.6) S3.0 — Load scopes (deterministic)

### 6.1 Purpose (binding)

Establish the **closed** set of inputs S3 may read, verify **gates and vocabularies**, and assemble a single, immutable **Context** record for subsequent S3 steps. S3.0 performs **no writes** and uses **no RNG**.

---

### 6.2 Inputs (authoritative anchors; read-only)

* **Merchant scope:** `schemas.ingress.layer1.yaml#/merchant_ids`
  Required: `merchant_id:u64`, `home_country_iso:string(ISO-3166-1 alpha-2)`, `mcc:string`, `channel ∈ (ingress schema’s closed vocabulary)`.
* **S1 hurdle:** `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`
  Required: payload `is_multi:bool`, embedded `{seed, parameter_hash, run_id}`.
* **S2 finaliser:** `schemas.layer1.yaml#/rng/events/nb_final`
  Required: payload `n_outlets:i64 (≥2)`, embedded `{seed, parameter_hash, run_id}`.
* **Policy artefact:** registry id `policy.s3.rule_ladder.yaml`
  Required: ordered `rules[]`, precedence law (total), **closed** `reason_codes[]`, optional validity window.
* **Static references:**
  `iso3166_canonical_2024` (canonical ISO set & lexicographic order).
  *(Optional)* `static.currency_to_country.map.json` (deterministic map) if referenced by policy.
* **Dictionary & registry:**
  `dataset_dictionary.layer1.1A.yaml` (dataset-id → partition spec → path template).
  `artefact_registry_1A.yaml` (audit of artefacts and semver/digests).

**Resolution rule:** all physical locations resolve via the **dataset dictionary**. **No literal paths** in S3.

---

### 6.3 Preconditions & gates (must hold before S3 continues)

1. **Presence & uniqueness** (within `{seed, parameter_hash, run_id}`):
   exactly one S1 hurdle row **and** exactly one S2 `nb_final` row per merchant; exactly one ingress merchant row.
2. **Gate conditions:** `is_multi == true` and `n_outlets (N) ≥ 2`.
3. **Path↔embed equality (read side):** for S1 and S2 rows, embedded `{seed, parameter_hash, run_id}` **byte-equal** the path partitions.
4. **Closed vocabularies:** `channel ∈ (ingress schema’s closed vocabulary)` (case-sensitive); `home_country_iso ∈` ISO set from the static artefact.
5. **Artefact integrity:** rule ladder precedence is a **total order**; `reason_codes[]` is a **closed set**; any configured validity windows are satisfied.
6. **Lineage availability:** run’s `parameter_hash` and `manifest_fingerprint` exist; every artefact opened in §6.2 will be included in the fingerprint inputs for embedding later.

**If any precondition fails, S3 stops for this merchant** (see §6.7). S3.0 produces **no S3 outputs**.

---

### 6.4 Normative behavior (spec, not algorithm)

S3.0 **shall**:

* Open all governed artefacts in §6.2 **atomically**; record each `(id, semver, digest)` for fingerprint inclusion.
* Resolve S1/S2 datasets via the dictionary and read the **single** row per merchant from each (no scanning outside the partition scope).
* Enforce §6.3 exactly as written (no “best effort”).
* Construct an immutable **Context** with the fields in §6.5.
* Perform **no writes** and **no RNG** activity.

---

### 6.5 Context (immutable; passed to S3.1+)

**Fields and semantics (all required unless marked optional):**

| Field                              | Type                                      | Source                  | Semantics                                                       |
|------------------------------------|-------------------------------------------|-------------------------|-----------------------------------------------------------------|
| `merchant_id`                      | `u64`                                     | ingress                 | Canonical key                                                   |
| `home_country_iso`                 | `string (ISO-3166-1)`                     | ingress                 | Must exist in ISO artefact; uppercase A–Z                       |
| `mcc`                              | `string`                                  | ingress                 | Merchant category code (read-only)                              |
| `channel`                          | `(closed vocabulary from ingress schema)` | ingress                 | Closed vocabulary (read-only)                                   |
| `N`                                | `i64 (≥2)`                                | S2 `nb_final.n_outlets` | Total outlets accepted by S2                                    |
| `seed`                             | `u64`                                     | S1/S2 embed             | For lineage joins only; S3 outputs are **not** seed-partitioned |
| `parameter_hash`                   | `Hex64`                                   | S1/S2 embed / run       | Partition key for all S3 outputs                                |
| `manifest_fingerprint`             | `Hex64`                                   | run                     | Embedded in every S3 output row                                 |
| `artefacts.rule_ladder`            | `{id, semver, digest}`                    | registry                | Governance attest                                               |
| `artefacts.iso_countries`          | `{id, semver, digest}`                    | registry                | Governance attest                                               |
| `artefacts.ccy_to_country` *(opt)* | `{id, semver, digest}`                    | registry                | Present only if used                                            |

> **Deliberate omission:** S3 does **not** carry S2’s `mu`/`dispersion_k` in context; S3 never re-derives or uses them.

**Immutability:** later S3 steps must not modify `Context` nor re-open authorities beyond §6.2.

---

### 6.6 Postconditions (must be true after S3.0)

* Governed artefacts are open, version-pinned, and slated for inclusion in the run `manifest_fingerprint`.
* Merchant has passed gates: `is_multi==true`, `N≥2`.
* Path partitions equal embedded lineage on S1/S2 rows.
* Closed vocabularies validated; ISO presence confirmed.
* A complete **Context** exists with lineage fields ready to embed in S3 egress.

---

### 6.7 Failure vocabulary (merchant-scoped; non-emitting)

| Code                         | Trigger                                                                                    | Effect                           |
|------------------------------|--------------------------------------------------------------------------------------------|----------------------------------|
| `ERR_S3_AUTHORITY_MISSING`   | Any governed artefact in §6.2 missing/unopenable or lacking semver/digest                  | Stop S3 for merchant; no outputs |
| `ERR_S3_PRECONDITION`        | `is_multi=false` or `N<2`                                                                  | Stop S3 for merchant; no outputs |
| `ERR_S3_PARTITION_MISMATCH`  | Path partitions ≠ embedded lineage on S1/S2 rows                                           | Stop S3 for merchant; no outputs |
| `ERR_S3_VOCAB_INVALID`       | `channel` not in (ingress schema’s closed vocabulary) or `home_country_iso` not in ISO set | Stop S3 for merchant; no outputs |
| `ERR_S3_RULE_LADDER_INVALID` | Ladder not total, unknown `reason_codes`, or out-of-window                                 | Stop S3 for merchant; no outputs |

**Non-emission guarantee:** S3.0 never writes tables or events; failures here do not produce partial S3 artefacts.

---

### 6.8 Spec-rehearsal (non-authoritative; for clarity only)

1. Open atomically: rule ladder, ISO set, (optional) currency-to-country map, dataset dictionary, artefact registry.
2. Read exactly one row each (dictionary-resolved IDs): ingress merchant, S1 hurdle, S2 `nb_final`.
3. Check: uniqueness; path partitions equal embedded lineage (S1/S2); `is_multi==true`; `N≥2`; `channel∈(ingress schema’s closed vocabulary)`; `home` ISO in set; ladder is a total order with **closed** reason codes (within window if configured).
4. Assemble `Context` per §6.5.
5. Stop (no RNG, no writes). Pass `Context` to S3.1.

*(End non-authoritative rehearsal.)*

---

## S3.7) S3.1 — Rule ladder (deterministic policy)

### 7.1 Purpose (binding)

Evaluate an **ordered, deterministic** set of policy rules to decide the merchant’s **cross-border eligibility** and to produce a **trace** of which rules fired (with reason codes/tags) for S3.2. **No RNG** and **no I/O** occur in S3.1.

---

### 7.2 Inputs (authoritative; read-only)

* **Context** from §6.5 (immutable):
  `merchant_id, home_country_iso, mcc, channel, N, seed, parameter_hash, manifest_fingerprint`, plus artefact digests. *(Deliberate omission: S3 does not use S2’s `μ, dispersion_k`.)*
* **Policy artefact** `policy.s3.rule_ladder.yaml` (opened in §6):
  – an **ordered** array `rules[]` with a **total order**;
  – a **closed set** `reason_codes[]`;
  – a **closed set** `filter_tags[]` (merchant/candidate tags the rules may emit);
  – optional **validity window**;
  – if used, named constant sets/maps (e.g., sanctioned lists) and deterministic thresholds declared inside the artefact or via static artefacts from §2.

**Resolution rule:** this artefact is the **only** policy authority for S3.1.

---

### 7.3 Rule artefact — shape & fields (binding)

Each element of `rules[]` **must** have:

| Field                 | Type                             | Semantics                                                                                              |
|-----------------------|----------------------------------|--------------------------------------------------------------------------------------------------------|
| `rule_id`             | `string` (ASCII `[A-Z0-9_]+`)    | Unique and version-stable within the artefact                                                          |
| `precedence`          | enum (closed)                    | One of `{ "DENY","ALLOW","CLASS","LEGAL","THRESHOLD","DEFAULT" }`                                      |
| `priority`            | integer                          | Strict order **within** the same `precedence`; lower number = higher priority                          |
| `is_decision_bearing` | `bool`                           | If `true`, this rule may set `eligible_crossborder` under §7.4; else it only contributes to tags/trace |
| `predicate`           | deterministic boolean expression | Over **Context** fields and named sets/maps in the artefact (e.g., `home_country_iso ∈ SANCTIONED`)    |
| `outcome.reason_code` | `string`                         | Element of the artefact’s **closed** `reason_codes[]`                                                  |
| `outcome.tags?`       | array<string>                    | Zero or more **closed** `filter_tags[]` to emit if the rule fires                                      |
| `notes?`              | string                           | Non-normative commentary (ignored by S3)                                                               |

**Determinism constraints**

* Predicates may use **only** equality/inequality, set membership, ISO lexicographic comparisons, and numeric comparisons on §6.5 fields or artefact-declared constants.
* **No RNG**, no external calls, no clock/host state.
* Numeric comparisons follow §3 (binary64, RNE, FMA-off).

---

### 7.4 Precedence law & conflict resolution (binding)

Let `Fired = { r ∈ rules : r.predicate == true }`. Define `eligible_crossborder` and the **decision source** as:

1. **DENY ≻ ALLOW ≻ {CLASS,LEGAL,THRESHOLD,DEFAULT}**

   * If any `DENY` fires ⇒ `eligible_crossborder = false` (decision source = the first decision-bearing `DENY`).
   * Else if any `ALLOW` fires ⇒ `eligible_crossborder = true` (decision source = the first decision-bearing `ALLOW`).
   * Else ⇒ choose from `{CLASS,LEGAL,THRESHOLD,DEFAULT}` by the ordering below.

2. **Within each precedence**, order rules by **priority asc**, then **rule\_id lexicographic A→Z**.

   * The **first** rule under this order whose `is_decision_bearing==true` becomes the decision source.
   * Rules with `is_decision_bearing==false` never set the decision but **do** contribute tags/reasons.

3. **DEFAULT terminal (mandatory, exactly one)**

   * Artefact **must** include exactly one `DEFAULT` with `is_decision_bearing==true` that **always fires** (or is otherwise guaranteed to catch the remainder). It provides the fallback decision (e.g., `eligible_crossborder=false`).

4. **Trace ordering (stable)**

   * `rule_trace` lists **all fired rules** sorted by `(precedence order, priority asc, rule_id asc)` — not evaluation time.
   * Mark the **single** decision source explicitly (`is_decision_source=true`).

---

### 7.5 Evaluation semantics (deterministic; no side-effects)

* Evaluate **all** predicates; collect `Fired`.
* Set `eligible_crossborder` **once** per §7.4.
* Compute `merchant_tags` as the **set-union** of `outcome.tags` from `Fired`, keeping a stable **A→Z** order for emission.
* **No I/O, no RNG**; results are in-memory outputs for S3.2.

---

### 7.6 Outputs to S3.2 (binding)

S3.1 yields the following immutable values:

| Name                   | Type            | Semantics                                                                                                                                |
|------------------------|-----------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `eligible_crossborder` | `bool`          | Merchant-level decision per §7.4                                                                                                         |
| `rule_trace`           | list of structs | Each: `{rule_id, precedence, priority, is_decision_bearing, reason_code, is_decision_source:bool, tags:array<string>}` ordered as §7.4.4 |
| `merchant_tags`        | array<string>   | Deterministic union of all fired rule tags; **closed** vocabulary; **A→Z** order                                                         |

**Consumption:**
S3.2 uses `eligible_crossborder` to decide whether to add foreign countries. `rule_trace`/`merchant_tags` drive candidate-row `reason_codes[]`/`filter_tags[]` (mapping to per-country tags is defined in §8/§10).

---

### 7.7 Invariants (must hold)

* Artefact precedence is a **total order**; `reason_codes[]` and `filter_tags[]` are **closed**.
* Exactly **one** terminal, decision-bearing `DEFAULT` rule exists.
* `eligible_crossborder` is **always defined**.
* `rule_trace` ordering is **stable** and independent of evaluation order/data layout.
* No rule references fields/sets outside §6.2/§2.1.
* No randomness or host state influences the outcome.

---

### 7.8 Failure vocabulary (merchant-scoped; non-emitting)

| Code                         | Trigger                                                                                                                       | Action                              |
|------------------------------|-------------------------------------------------------------------------------------------------------------------------------|-------------------------------------|
| `ERR_S3_RULE_LADDER_INVALID` | Missing/duplicate `DEFAULT`; non-total precedence; duplicate `rule_id`; `reason_code`/`filter_tag` not in the **closed** sets | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_RULE_EVAL_DOMAIN`    | Predicate references unknown feature/value (e.g., unknown `channel`, ISO not in artefact, undeclared named set/map)           | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_RULE_CONFLICT`       | Multiple **decision-bearing** rules tie after priority and lexicographic tiebreak (malformed artefact)                        | Stop S3 for merchant; no S3 outputs |

---

### 7.9 Notes (clarifications; binding where stated)

* **Numeric thresholds:** comparisons are evaluated in **binary64** per §3. If thresholds are decimal, the artefact must state inclusivity (`>=` vs `>`).
* **No re-derivation:** if a rule needs an input (e.g., GDP bucket), it must appear in §2/§6; otherwise the rule is invalid.
* **Trace vs emission:** S3.1 **does not write** traces; `rule_trace`/`merchant_tags` are handed to S3.2 to annotate candidate rows.

---

## S3.8) S3.2 — Candidate universe construction (deterministic)

### 8.1 Purpose (binding)

Construct, for a single merchant, the **unordered** candidate country set `C` that §9 will **rank** (and, if enabled, §12 will weight / §13 will integerise). The set is **deterministic**, **non-empty**, and **always contains `home`**. **No RNG** and **no egress** occur in S3.2.

---

### 8.2 Inputs (authoritative; read-only)

* **`Context`** from §6.5 (immutable): `merchant_id`, `home_country_iso`, `mcc`, `channel`, `N`, lineage fields, artefact digests.
* **`eligible_crossborder : bool`** and **`rule_trace`** from §7.6 (immutable): ordered fired rules `{rule_id, precedence, priority, is_decision_bearing, reason_code, is_decision_source, tags[]}`.
* **Policy artefact** `policy.s3.rule_ladder.yaml` (opened in §6):
  • **Named country sets** (e.g., `SANCTIONED`, `EEA`, `WHITELIST_X`);
  • Per-rule **admit/deny lists** (`admit_countries[]`, `deny_countries[]`) and/or references to named sets;
  • **Closed vocabularies**: `reason_codes[]`, `filter_tags[]`; mapping notes for row-level tagging.
* **ISO reference** `iso3166_canonical_2024` (opened in §6): authoritative ISO set and lexicographic order (alpha-2, uppercase).

> **Resolution rule:** S3.2 consults **only** the policy artefact’s named sets/lists and the ISO set; **no other source** is permitted.

---

### 8.3 Preconditions (must hold before S3.2 runs)

* `home_country_iso ∈ ISO` (already verified in §6).
* `eligible_crossborder` and `rule_trace` are present (from §7).
* Every named set/list referenced by **fired** rules exists in the policy artefact and expands **only** to ISO codes.

---

### 8.4 Deterministic construction (spec, not algorithm)

#### 8.4.1 Start set (invariant)

* Initialise `C := { home }` with `home = Context.home_country_iso`.
* Tag the `home` row with `filter_tags += ["HOME"]` (from the policy’s **closed** `filter_tags`) and include the **decision source** `reason_code` (from §7) in `reason_codes` for traceability.

#### 8.4.2 Foreign admission when `eligible_crossborder == false`

* **No foreign country is admitted.**
* `C = { home }`; define `K_foreign := 0`.

#### 8.4.3 Foreign admission when `eligible_crossborder == true`

Let `Fired` be the set of fired rules (from `rule_trace`). Build deterministic admits/denies using only **fired** rules and the artefact:

* `ADMITS`  = ⋃ over fired rules of: explicit `admit_countries[]` ∪ expansions of referenced **admit** named sets.

* `DENIES`  = ⋃ over fired rules of: explicit `deny_countries[]`  ∪ expansions of referenced **deny** named sets **including legal/geo constraints** (e.g., `SANCTIONED`).

* **Precedence reflection:** since §7 already applies **DENY ≻ ALLOW**, S3.2 forms the foreign set as
  `FOREIGN := (ADMITS \ DENIES) \ {home}`. *(No re-evaluation of precedence; this is a set-level reflection.)*

* **ISO filter:** `FOREIGN := FOREIGN ∩ ISO`. Any element not in ISO is a **policy artefact error** (see §8.8).

* Add every `c ∈ FOREIGN` to `C`. For each added row, attach deterministic `filter_tags` and `reason_codes` per the artefact’s mapping rules (e.g., per-rule `row_tags`, plus a **stable union** of fired rules’ `reason_code` values that justify inclusion; both vocabularies are **closed** and must appear in **A→Z** order).

* Define `K_foreign := |FOREIGN|`.

#### 8.4.4 De-duplication & casing

* `C` contains **unique** ISO alpha-2 codes (uppercase `A–Z`).
* If multiple fired rules admit the same country, merge tags/reasons via **stable union** (A→Z for strings), no duplicates.

---

### 8.5 Outputs to §9 (binding; still unordered)

S3.2 yields an **unordered** list of candidate rows for the merchant:

| Field                             | Type                 | Semantics                                                                                                     |
|-----------------------------------|----------------------|---------------------------------------------------------------------------------------------------------------|
| `merchant_id`                     | `u64`                | From `Context`                                                                                                |
| `country_iso`                     | `string(ISO-3166-1)` | `home` or admitted foreign                                                                                    |
| `is_home`                         | `bool`               | `true` iff `country_iso == home`                                                                              |
| `filter_tags`                     | `array<string>`      | Deterministic tags (**closed** set from policy); **A→Z** order; includes `"HOME"` for the home row            |
| `reason_codes`                    | `array<string>`      | Deterministic union (**closed** set); **A→Z** order                                                           |
| *(optional)* `base_weight_inputs` | struct               | Only if §12 computes deterministic priors later; contains **declared** numeric inputs (no RNG, no host state) |

> **No `candidate_rank` is assigned in §8**; ranking happens in §9. If S3 does not implement priors (§12) or integerisation (§13), omit their optional fields.

---

### 8.6 Invariants (must hold after S3.2)

* `C` is **non-empty** and **contains `home`**.
* If `eligible_crossborder == false` ⇒ `C == {home}` and `K_foreign == 0`.
* If `eligible_crossborder == true` ⇒ `C == {home} ∪ FOREIGN`; `K_foreign == |C| − 1`; `FOREIGN` is deterministic per fired rules.
* Every `country_iso ∈ ISO`; **no duplicates** in `C`.
* `filter_tags` and `reason_codes` per row are drawn **only** from the artefact’s **closed** vocabularies and are in **A→Z** order.

---

### 8.7 Notes (clarifications; binding where stated)

* **No re-derivation:** S3.2 does not derive features beyond §6/§2. If a rule needs, e.g., *GDP bucket*, it must be provided via governed artefacts; otherwise the rule is invalid for S3.
* **No RNG:** Country selection in S3.2 is policy-driven, not stochastic. Any stochastic selection (e.g., Gumbel-top-K) belongs in a later state; S3 here is deterministic.
* **Admit/deny scope:** Admit/deny operate at **country-level** only. Merchant-level tags from rules apply to **all** candidate rows; per-row tags follow the artefact’s mapping.

---

### 8.8 Failure vocabulary (merchant-scoped; non-emitting)

| Code                              | Trigger                                                     | Action                              |
|-----------------------------------|-------------------------------------------------------------|-------------------------------------|
| `ERR_S3_CANDIDATE_CONSTRUCTION`   | Candidate set becomes empty **or** `home` missing from `C`  | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_COUNTRY_CODE_INVALID`     | A named set/list expands to a value not in the ISO artefact | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_POLICY_REFERENCE_INVALID` | Fired rule references an undefined named set/list           | Stop S3 for merchant; no S3 outputs |

---

**Hand-off to §9:** §8 yields the **unordered** candidate rows `C`. §9 will impose a **total, deterministic order** (**`candidate_rank`**)—**priors are not used for sorting**. If configured, priors may be computed later and are used in **integerisation** (§10).

---

## S3.9) S3.3 — Ordering & tie-break (total order)

### 9.1 Purpose (binding)

Impose a **total, deterministic order** over the **unordered** candidate rows from §8 so that every merchant’s candidates receive a **contiguous** **`candidate_rank ∈ {0,…,|C|−1}`** with **`candidate_rank(home) = 0`**. **No RNG** and **no I/O** occur in S3.3.

> Canonical S3 flow (per §5): **rank first, then priors (§12)**. Therefore, ranking **does not** use weights.

---

### 9.2 Inputs (authoritative; read-only)

* **Candidate rows `C` from §8.5** (unordered), each with:
  `merchant_id`, `country_iso`, `is_home`, `filter_tags[]`, `reason_codes[]`, *(optional)* `base_weight_inputs` (only if §12 will run later; not used here).
* **Context** from §6.5 (read-only): includes `home_country_iso`.
* **Policy artefact `policy.s3.rule_ladder.yaml`** (read-only): precedence class order, per-rule `priority`, `rule_id`, and the **closed mapping** from row `reason_codes[]` to the admitting rule id(s) (see 9.3.2).

> Resolution rule: S3.3 consults **only** §8 outputs and the artefact fields listed above. No external sources.

---

### 9.3 Comparator (single path to a total order)

Define one deterministic comparator. Sorting must be **stable**.

#### 9.3.1 Home override (rank 0)

* The row with `country_iso == home_country_iso` **must** receive **`candidate_rank = 0`**.
* All other countries are ranked **strictly after** home (beginning at `candidate_rank = 1`).

#### 9.3.2 Primary key — **admission order key** (weights are not used)

For each foreign row `i`, derive a deterministic **admission key** from the artefact:

* Let `AdmitRules(i)` be the set of **admit-bearing** fired rules (from §7/§8 mapping) that justify inclusion of `i`.
  If the artefact’s `reason_codes[]` alone are not sufficient to reconstruct `AdmitRules(i)`, the artefact **must** provide an explicit, closed mapping (e.g., per-row `admit_rule_ids[]`). If this mapping is missing, the artefact is **invalid** for S3 (§9.8).

* For each `r ∈ AdmitRules(i)`, compute the triplet
  `K(r) = ⟨ precedence_rank(r), priority(r), rule_id_ASC ⟩`,
  where `precedence_rank` is the numeric index of the artefact’s precedence class (lower = earlier).

* Define the row’s primary key as the **minimum** (lexicographic) triplet over `AdmitRules(i)`:

  ```
  Key1(i) = min_lex { K(r) : r ∈ AdmitRules(i) }
  ```

  (Intuition: if multiple rules justify inclusion, the earliest under artefact order wins deterministically.)

#### 9.3.3 Secondary & tertiary keys (shared)

* **Key 2 (ISO tiebreak):** `country_iso` **lexicographic A→Z** (ISO alpha-2).
* **Key 3 (stability):** the row’s **original index** in §8’s output (or, equivalently, `(merchant_id, original_index)`) to guarantee **stable** order under equal keys.

---

### 9.4 Rank assignment (binding)

After sorting with §9.3 for a given merchant:

* Assign **`candidate_rank = 0`** to `home`.
* Assign **`candidate_rank = 1,2,…`** in sorted order to the remaining rows **with no gaps**.

**Contiguity:** per merchant, `candidate_rank` spans `0..|C|−1`.
**Uniqueness:** per merchant, **no two rows share the same `(candidate_rank, country_iso)`**; **no duplicate `country_iso`** exist by §8.

---

### 9.5 Deterministic numeric discipline (binding)

* Priors/weights, if later computed in §12, are **not** used here.
* All string and integer comparisons follow §3’s environment (binary64 rules are irrelevant in §9 unless later sections add numeric keys).
* Sorting is **stable**; do not rely on host/library unspecified stability—**stability is part of the contract**.

---

### 9.6 Outputs to §12/§13/§15 (binding)

Augment each candidate row with:

| Field                    | Type   | Semantics                                                                                             |
|--------------------------|--------|-------------------------------------------------------------------------------------------------------|
| `candidate_rank`         | `u32`  | Contiguous per merchant; `home` is `0`                                                                |
| *(optional)* `order_key` | struct | Non-emitted diagnostic tuple capturing `Key1` (for debugging only; include only if schema defines it) |

**Consumption:**

* §12 (if enabled) may compute **priors** over the already ranked list (does **not** affect `candidate_rank`).
* §13 (if enabled) consumes the ranked list (and, if present, priors) to integerise to counts.
* §15 egress always emits **`candidate_rank`** as the **sole authority** for inter-country order.

---

### 9.7 Invariants (must hold after S3.3)

* **`candidate_rank(home) = 0`**.
* Ranks are **contiguous** with no gaps; total order holds even when keys tie (via ISO then stability key).
* Comparator uses **admission order key** (no priors); sorting is **stable** and host-invariant under §3.
* If the artefact cannot provide a closed mapping from `reason_codes[]` to admit rules for any foreign row, the run is invalid for S3.

---

### 9.8 Failure vocabulary (merchant-scoped; non-emitting)

| Code                            | Trigger                                                                                            | Action                              |
|---------------------------------|----------------------------------------------------------------------------------------------------|-------------------------------------|
| `ERR_S3_ORDERING_HOME_MISSING`  | No row with `country_iso == home` in §8 output                                                     | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_ORDERING_NONCONTIGUOUS` | Assigned **candidate_rank** values are not contiguous `0..\|C\|−1`                                 | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_ORDERING_KEY_UNDEFINED` | Cannot reconstruct the **admission key** (no priors and no closed mapping from reasons → rule ids) | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_ORDERING_UNSTABLE`      | Artefact inconsistency prevents a single total order (e.g., ambiguous mapping that yields ties)    | Stop S3 for merchant; no S3 outputs |

---

### 9.9 Notes (clarifications; binding where stated)

* **Home-first is an override, not a key:** assign `candidate_rank=0` to home **before** comparing the remainder.
* **Admission key derivation** depends on a **closed mapping** from row-level `reason_codes[]` (or explicit `admit_rule_ids[]`) to admitting rules. If your policy expresses reasons at a coarser grain, add explicit `admit_rule_ids[]`.
* **No probabilistic meaning** attaches to `candidate_rank`. It is a deterministic ordering surface only.

---

## S3.10) S3.4 — Integerisation (include only if S3 allocates counts)

### 10.1 Purpose (binding)

Convert a merchant’s **ranked** candidate universe and a total outlet count **`N`** (from S2) into **non-negative integer per-country counts** that sum to **`N`**, using a **deterministic largest-remainder** method with fixed quantisation and tie-break rules. **No RNG** and **no I/O** occur in S3.4.

---

### 10.2 Inputs (authoritative; read-only)

* **Context** (from §6.5): `merchant_id`, `home_country_iso`, `N (≥2)`, lineage fields.
* **Ranked candidates** (from §9): rows `⟨country_iso, candidate_rank, …⟩`, with `candidate_rank(home)=0`, contiguous ranks, no duplicates.
* **Deterministic priors (optional):** **quantised** weights `w_i^⋄` (post-quantisation per §3.5 / §12) **if** priors are enabled in S3.
* **(Optional) bounds / policy knobs:** per-country integer bounds `L_i, U_i` with `0 ≤ L_i ≤ U_i ≤ N` **if** the policy artefact defines them for integerisation.

> **Resolution rule:** If priors are **not** enabled in S3, integerisation uses the **equal-weight** path (§10.3.B). If bounds exist, apply §10.6 (bounded Hamilton).

---

### 10.3 Ideal (fractional) allocation — two primary paths

Let `M = |C|` be the number of candidate countries.

#### 10.3.A Priors present (preferred when enabled)

* Use **quantised** priors `w_i^⋄ > 0` (dp fixed where produced).
* Normalise: `s_i = w_i^⋄ / (Σ_j w_j^⋄)`.
* Ideal fractional counts: `a_i = N · s_i`.

**Guard:** If `Σ_j w_j^⋄ == 0` (policy error), fall back to §10.3.B (equal-weight) and raise `ERR_S3_WEIGHT_ZERO` (see §10.9).

#### 10.3.B No priors (equal-weight discipline)

* Set `s_i = 1 / M` for all `i`.
* Ideal counts: `a_i = N / M` (identical for all countries).

*(Either path yields `a = (a_1,…,a_M)` used below.)*

---

### 10.4 Floor step, residuals, and remainder

* **Floor counts:** `b_i = ⌊ a_i ⌋` (integer).
* **Remainder to distribute:** `d = N − Σ_i b_i` (integer, `0 ≤ d < M`).
* **Residuals:** `r_i = a_i − b_i` (fractional part in `[0,1)`).
* **Residual quantisation (binding):** quantise residuals to fixed **`dp_resid = 8`** decimal places under binary64 RNE (§3.5):
  `r_i^⋄ = round_to_dp(r_i, 8)`.

> Residuals are **always** computed **after** using the **quantised** priors (if any). The value of `dp_resid` is **binding**.

---

### 10.5 Deterministic bump rule (largest-remainder with fixed tie-break)

Distribute the `d` remaining units by adding **+1** to exactly `d` countries according to this deterministic order:

1. Sort by **`r_i^⋄` descending**.
2. Break ties by **`country_iso`** lexicographic **A→Z** (ISO alpha-2).
3. If still tied (should not occur with fixed dp + ISO key), break by **`candidate_rank` ascending** (home first), then by the stable original input index from §8.

Let `S` be the resulting order. Bump the top `d` entries (`S[1..d]`) by +1. Final integer **count**:

```
count_i = b_i + 1[i ∈ top d].
```

**Persisted residual order:** define `residual_rank_i` as the **1-based position** of country `i` in `S` (the bump set is `{ i | residual_rank_i ≤ d }`). Persist `residual_rank` for **all** countries to make replay and tie reviews byte-deterministic downstream.

---

### 10.6 Optional bounds (lower/upper) — bounded Hamilton method

If the policy artefact supplies per-country integer bounds `(L_i, U_i)`:

1. **Feasibility guard:** require `Σ_i L_i ≤ N ≤ Σ_i U_i`. If violated ⇒ `ERR_S3_INTEGER_FEASIBILITY`.
2. **Initial allocation:** set `b_i = L_i`. Let `N′ = N − Σ_i L_i`. Define **capacities** `cap_i = U_i − L_i`.
3. **Reweighting set:** consider only countries with `cap_i > 0`. Recompute **shares** over that set:

   * With priors: `s_i = w_i^⋄ / Σ_{cap_j>0} w_j^⋄`; else `s_i = 1 / |{j : cap_j>0}|`.
   * Ideal increments: `a_i′ = N′ · s_i`.
   * Floors: `f_i = ⌊ a_i′ ⌋`, limited by capacity: `f_i = min(f_i, cap_i)`; set `b_i ← b_i + f_i`.
   * Remainder `d′ = N′ − Σ_i f_i`.
4. **Residuals and bump:** compute `r_i′ = a_i′ − f_i`, quantise to **`dp_resid = 8`**, and apply §10.5 **restricted to countries with remaining capacity** (`cap_i − f_i > 0`) to distribute the remaining `d′`.
5. **Final counts:** `count_i = b_i` after bumps; each satisfies `L_i ≤ count_i ≤ U_i` and `Σ_i count_i = N`.

---

### 10.7 Outputs to egress (§15) (binding)

For each candidate row:

| Field           | Type       | Semantics                                                        |
|-----------------|------------|------------------------------------------------------------------|
| `count`         | `i64 (≥0)` | Final integer allocation for `country_iso`                       |
| `residual_rank` | `u32`      | Position in the residual order `S` of §10.5 (1 = highest resid.) |

If S3 emits a dedicated table **`s3_integerised_counts`**, include `merchant_id`, `country_iso`, `count`, `residual_rank`, and lineage fields, partitioned per §2.

---

### 10.8 Invariants (must hold)

* `Σ_i count_i = N`; `count_i ≥ 0`.
* **`candidate_rank(home) = 0`** still holds from §9; integerisation **does not** alter ranks.
* Residuals quantised at **`dp_resid = 8`** before ordering; tie-break exactly as §10.5.
* If bounds are used: `L_i ≤ count_i ≤ U_i` for all `i`, and feasibility guard passed.
* `{ i | residual_rank_i ≤ d }` matches exactly the set of bumped countries.

---

### 10.9 Failure vocabulary (merchant-scoped; non-emitting)

| Code                          | Trigger                                            | Action                              |
|-------------------------------|----------------------------------------------------|-------------------------------------|
| `ERR_S3_WEIGHT_ZERO`          | Priors enabled but `Σ_i w_i^⋄ == 0` (policy error) | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_INTEGER_FEASIBILITY`  | Bounds specified but `Σ L_i > N` or `N > Σ U_i`    | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_INTEGER_SUM_MISMATCH` | After allocation, `Σ_i count_i ≠ N`                | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_INTEGER_NEGATIVE`     | Any `count_i < 0`                                  | Stop S3 for merchant; no S3 outputs |

---

### 10.10 Notes (clarifications; binding where stated)

* **dp selection:** `dp_resid = 8` is binding for residuals to ensure cross-host determinism; change only via policy artefact **and** update this section.
* **Home minimum:** If policy requires a **home floor** (e.g., `L_home ≥ 1`), encode via §10.6; do **not** hand-wave it in code.
* **No probabilistic meaning:** counts are deterministic integers; priors (if any) are deterministic scores, *not* probabilities.

---

## S3.11) S3.5 — Sequencing & IDs (deterministic)

### 11.1 Purpose (binding)

Given per-country **integer counts** `count_i` (from §10) for a multi-site merchant, define a **deterministic, contiguous within-country sequence** `site_order ∈ {1..count_i}`, and—if enabled—a **deterministic identifier** `site_id` per `(merchant_id, country_iso, site_order)`. **No RNG**; **no gaps**; ordering is reproducible across hosts.

---

### 11.2 Preconditions (must hold)

* Inputs from §6.5 (**Context**) and **ranked candidate rows** from §9.
* Integer counts from §10 present and valid: for each `country_iso` in the merchant’s set, `count_i ≥ 0` and `Σ_i count_i = N`.
* **`candidate_rank(home) = 0`** still holds (sequencing must not change inter-country order).

---

### 11.3 Sequencing (deterministic; no side-effects)

* **Per-country domain:** For each `(merchant_id, country_iso)` with `count_i > 0`, define a **contiguous** within-country sequence `site_order ∈ {1,2,…,count_i}`.
* **Logical row grouping:** Within a merchant block, rows are *logically* grouped by `(country_iso, site_order)`; inter-country order remains §9’s **`candidate_rank`** and is **not** encoded here.
* **Zero counts:** If `count_i = 0`, **no rows** exist for that `(merchant_id, country_iso)` in any sequencing output.

> **Binding:** Sequencing **never** reorders countries: inter-country order remains the **`candidate_rank`** from §9; sequencing only establishes the order **within** each country.

---

### 11.4 Identifier policy (if `site_id` is enabled)

* **Format:** `site_id` is a **fixed-width, zero-padded 6-digit string**: `"{site_order:06d}"`.
  Examples: `1 → "000001"`, `42 → "000042"`, `999999 → "999999"`.
* **Scope of uniqueness:** Unique **within** each `(merchant_id, country_iso)`. The same `site_id` string may appear in another country or merchant.
* **Overflow rule (binding):** If `count_i > 999999`, raise `ERR_S3_SITE_SEQUENCE_OVERFLOW` and **stop S3 for that merchant**; no partial sequencing/outputs.
* **Immutability:** Given identical inputs/lineage, the mapping `(merchant_id, country_iso, site_order) → site_id` is a pure function (no host/time dependence).

---

### 11.5 Emitted dataset (Variant A — S3 owns sequencing)

If S3 emits sequencing, it **must** produce the following table; otherwise skip to §11.6.

| Dataset id         | JSON-Schema anchor                  | Partitions (path)    | Embedded lineage (columns)                           | Row order (physical)                                 | Columns (name : type : semantics)                                                                                                                                                             |
|--------------------|-------------------------------------|----------------------|------------------------------------------------------|------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `s3_site_sequence` | `schemas.1A.yaml#/s3/site_sequence` | `parameter_hash={…}` | `manifest_fingerprint:Hex64`, `parameter_hash:Hex64` | `(merchant_id ASC, country_iso ASC, site_order ASC)` | `merchant_id:u64` — key; `country_iso:string(ISO-3166-1 alpha-2)`; `site_order:u32` — **contiguous 1..count\_i**; *(optional)* `site_id:string(len=6)` — zero-padded; lineage fields as above |

**Contracts**

* **Contiguity:** For each `(merchant_id, country_iso)`, the set of `site_order` values is **exactly** `{1..count_i}`.
* **Uniqueness:** No duplicate `site_order` within a `(merchant_id, country_iso)` block; if `site_id` present, no duplicate `site_id` within that block.
* **Read scope:** Consumers **must not** infer inter-country order from this table; inter-country order is **only** `candidate_rank` from §9 (available via `s3_candidate_set`).

---

### 11.6 Deferred emission (Variant B — sequencing implemented later)

If S3 does **not** emit `s3_site_sequence`, it must still fix the **binding rules** in §§11.3–11.4. A later state (e.g., S7 “Sequence & IDs”) must:

* Use **exactly** the same within-country sequencing (contiguous `1..count_i`),
* Enforce the **same** `site_id` format and **overflow** rule, and
* Preserve lineage/path rules from §2 (parameter-scoped partitions; embed `manifest_fingerprint` and `parameter_hash`).

---

### 11.7 Lineage & ordering (write-side discipline, Variant A)

* **Partitions:** `parameter_hash` only (parameter-scoped).
* **Embedded lineage:** each row embeds `{parameter_hash, manifest_fingerprint}` equal to the run.
* **No path literals:** dictionary resolves the dataset id to a physical path.
* **JSON types:** numbers as JSON **numbers**; `site_id` as JSON **string** of length 6.

---

### 11.8 Failure vocabulary (merchant-scoped; non-emitting)

| Code                            | Trigger                                                                                       | Action                                               |
|---------------------------------|-----------------------------------------------------------------------------------------------|------------------------------------------------------|
| `ERR_S3_SITE_SEQUENCE_OVERFLOW` | `count_i > 999999` for any `(merchant_id, country_iso)`                                       | Stop S3 for merchant; emit **no** sequencing outputs |
| `ERR_S3_SEQUENCE_GAP`           | A `(merchant_id, country_iso)` block is missing any integer in `{1..count_i}`                 | Stop S3 for merchant; no outputs                     |
| `ERR_S3_SEQUENCE_DUPLICATE`     | Duplicate `site_order` (or `site_id`, if enabled) within a `(merchant_id, country_iso)` block | Stop S3 for merchant; no outputs                     |
| `ERR_S3_SEQUENCE_ORDER_DRIFT`   | Sequencing attempts to alter inter-country order (i.e., contradict §9 **candidate\_rank**)    | Stop S3 for merchant; no outputs                     |

---

### 11.9 Invariants (must hold after sequencing)

* For every country with `count_i > 0`, `site_order` is **exactly** `1..count_i` (contiguous, no gaps).
* **Inter-country order remains §9’s `candidate_rank`**; sequencing does not permute countries.
* If `site_id` is emitted, it is a deterministic function of `(merchant_id, country_iso, site_order)` with the 6-digit zero-padded format; overflow is impossible by construction or triggers §11.8.
* Outputs (Variant A) follow §2 lineage/partition rules; **no path literals**.

---

*Implementation note (non-authoritative):* If you anticipate future requirements for a check digit or namespace change, nest `site_id` under a versioned object in the schema (e.g., `{ "v": 1, "id": "000123" }`). Until then, the flat 6-digit string above is the **binding** representation.

---

## S3.12) Emissions (authoritative)

### 12.1 General write discipline (binding)

* **Dictionary-resolved paths only.** All physical locations resolve via the dataset dictionary by dataset **ID**; no hard-coded paths.
* **Partition scope:** all S3 datasets are **parameter-scoped** — partitioned by `parameter_hash` only (**no `seed`**).
* **Embedded lineage:** every S3 row **embeds** `{parameter_hash: Hex64, manifest_fingerprint: Hex64}` that must **byte-equal** the run’s values and, for `parameter_hash`, the path partition.
* **Numbers:** payload numbers are JSON **numbers** (not strings), except where a **decimal string** is required for deterministic fixed-dp representation (explicitly called out below).
* **Atomic publish:** stage → fsync → atomic rename into the dictionary location. No partials or mismatched partitions.
* **Idempotence:** identical inputs + lineage ⇒ **byte-identical** outputs.

---

### 12.2 Required table — `s3_candidate_set`

**Dataset id:** `s3_candidate_set`
**JSON-Schema anchor:** `schemas.1A.yaml#/s3/candidate_set`
**Partitions (path):** `parameter_hash={…}`
**Embedded lineage (columns):** `parameter_hash: Hex64`, `manifest_fingerprint: Hex64`
**Row ordering guarantee (logical):** `(merchant_id ASC, candidate_rank ASC, country_iso ASC)`

**Columns (binding):**

| Name                   | Type                      | Semantics                                                                   |
|------------------------|---------------------------|-----------------------------------------------------------------------------|
| `merchant_id`          | `u64`                     | Canonical merchant key                                                      |
| `country_iso`          | `string(ISO-3166-1, A–Z)` | Candidate country code                                                      |
| `candidate_rank`       | `u32`                     | **Total, contiguous order** per merchant; **`candidate_rank(home)=0`** (§9) |
| `is_home`              | `bool`                    | `true` iff `country_iso == home_country_iso`                                |
| `reason_codes`         | `array<string>`           | Deterministic union (A→Z) from policy’s **closed** set                      |
| `filter_tags`          | `array<string>`           | Deterministic tags (A→Z) from policy’s **closed** set                       |
| `parameter_hash`       | `Hex64`                   | Embedded lineage (must equal path)                                          |
| `manifest_fingerprint` | `Hex64`                   | Embedded lineage                                                            |

**Contracts**

* Per merchant: ≥1 row (candidate set **non-empty**) and exactly one row with `is_home==true` and `candidate_rank==0`.
* No duplicate `(merchant_id, country_iso)` and no duplicate `candidate_rank` within a merchant block.
* Inter-country order is **authoritatively** given by `candidate_rank` only. Consumers must **not** infer order from file order.

> **No priors in this table.** Deterministic priors (if any) live in `s3_base_weight_priors` (12.3) as the **single source of truth**.

---

### 12.3 Optional table — `s3_base_weight_priors` (deterministic scores)

Emit **only** if S3 computes deterministic priors (see §12 / §3.5 for `dp` selection). Priors are deterministic scores, not probabilities.

**Dataset id:** `s3_base_weight_priors`
**JSON-Schema anchor:** `schemas.1A.yaml#/s3/base_weight_priors`
**Partitions (path):** `parameter_hash={…}`
**Embedded lineage (columns):** `parameter_hash`, `manifest_fingerprint`
**Row ordering guarantee:** `(merchant_id ASC, country_iso ASC)`

**Columns (binding):**

| Name                   | Type                      | Semantics                                                               |
|------------------------|---------------------------|-------------------------------------------------------------------------|
| `merchant_id`          | `u64`                     | Canonical merchant key                                                  |
| `country_iso`          | `string(ISO-3166-1, A–Z)` | Candidate country code                                                  |
| `base_weight_dp`       | **string (fixed-dp)**     | Deterministic prior **after quantisation**; exactly `dp` decimal places |
| `dp`                   | `u8`                      | Decimal places used for quantisation (constant within a run)            |
| `parameter_hash`       | `Hex64`                   | Embedded lineage                                                        |
| `manifest_fingerprint` | `Hex64`                   | Embedded lineage                                                        |

**Contracts**

* `dp` is constant within a run (may change **only** with policy change + new fingerprint/param hash).
* This table is the **only** authority for priors in S3; `s3_candidate_set` must not carry a `base_weight_dp` field.

---

### 12.4 Optional table — `s3_integerised_counts` (if S3 allocates counts)

Emit **only** if S3 performs integerisation (see §10). Otherwise, counts belong to the later state that owns allocation.

**Dataset id:** `s3_integerised_counts`
**JSON-Schema anchor:** `schemas.1A.yaml#/s3/integerised_counts`
**Partitions (path):** `parameter_hash={…}`
**Embedded lineage (columns):** `parameter_hash`, `manifest_fingerprint`
**Row ordering guarantee:** `(merchant_id ASC, country_iso ASC)`

**Columns (binding):**

| Name                   | Type                      | Semantics                                                 |
|------------------------|---------------------------|-----------------------------------------------------------|
| `merchant_id`          | `u64`                     | Canonical merchant key                                    |
| `country_iso`          | `string(ISO-3166-1, A–Z)` | Candidate country code                                    |
| `count`                | `i64 (≥0)`                | Final integer allocation for this country                 |
| `residual_rank`        | `u32`                     | Rank in residual order (`1`=highest), as defined in §10.5 |
| `parameter_hash`       | `Hex64`                   | Embedded lineage                                          |
| `manifest_fingerprint` | `Hex64`                   | Embedded lineage                                          |

**Contracts**

* Per merchant: `Σ_i count_i = N` from S2; `count_i ≥ 0`.
* `residual_rank` is present for **every** row and deterministically reconstructs the bump set `{ i | residual_rank_i ≤ d }`.

---

### 12.5 Optional table — `s3_site_sequence` (if S3 owns sequencing; see §11)

If sequencing is deferred to a later state, **do not** emit this table here. If S3 owns sequencing (Variant A in §11):

**Dataset id:** `s3_site_sequence`
**JSON-Schema anchor:** `schemas.1A.yaml#/s3/site_sequence`
**Partitions (path):** `parameter_hash={…}`
**Embedded lineage (columns):** `parameter_hash`, `manifest_fingerprint`
**Row ordering guarantee:** `(merchant_id ASC, country_iso ASC, site_order ASC)`

**Columns (binding):**

| Name                   | Type                      | Semantics                                           |
|------------------------|---------------------------|-----------------------------------------------------|
| `merchant_id`          | `u64`                     | Canonical merchant key                              |
| `country_iso`          | `string(ISO-3166-1, A–Z)` | Country                                             |
| `site_order`           | `u32`                     | Contiguous `1..count_i` within country (from §11.3) |
| `site_id` *(optional)* | `string(6)`               | Zero-padded 6-digit ID; overflow triggers §11.8     |
| `parameter_hash`       | `Hex64`                   | Embedded lineage                                    |
| `manifest_fingerprint` | `Hex64`                   | Embedded lineage                                    |

**Contracts:** see §11.5–§11.9.

---

### 12.6 Path↔embed equality (write-side checks)

For every written row in all S3 datasets:

* `row.parameter_hash` (embedded) **equals** the `parameter_hash` path partition (string-equal).
* `row.manifest_fingerprint` **equals** the run’s fingerprint used to derive all S3 inputs.
* No other lineage fields appear in the path (e.g., **no `seed`**); any additional lineage fields must be **embedded** only.

Violation ⇒ **`ERR_S3_EGRESS_SHAPE`**.

---

### 12.7 Non-duplication & uniqueness (binding)

Per merchant:

* `s3_candidate_set`: unique `(country_iso)` and unique `(candidate_rank)`; exactly one `is_home==true` with `candidate_rank==0`.
* `s3_base_weight_priors` (if emitted): unique `(country_iso)`.
* `s3_integerised_counts` (if emitted): unique `(country_iso)`.
* `s3_site_sequence` (if emitted): unique `(country_iso, site_order)` (and `(country_iso, site_id)` if `site_id` present).

---

### 12.8 Example row *shapes* (illustrative; dictionary resolves paths)

> Illustrative JSON snippets (not full rows). Exact schemas are normative via the anchors.

**`s3_candidate_set`:**

```json
{
  "merchant_id": 123456789,
  "country_iso": "GB",
  "candidate_rank": 0,
  "is_home": true,
  "reason_codes": ["ALLOW_WHITELIST"],
  "filter_tags": ["GEO_OK","HOME"],
  "parameter_hash": "ab12...ef",
  "manifest_fingerprint": "cd34...90"
}
```

**`s3_base_weight_priors`:**

```json
{
  "merchant_id": 123456789,
  "country_iso": "FR",
  "base_weight_dp": "0.180000",
  "dp": 6,
  "parameter_hash": "ab12...ef",
  "manifest_fingerprint": "cd34...90"
}
```

**`s3_integerised_counts`:**

```json
{
  "merchant_id": 123456789,
  "country_iso": "FR",
  "count": 3,
  "residual_rank": 2,
  "parameter_hash": "ab12...ef",
  "manifest_fingerprint": "cd34...90"
}
```

**`s3_site_sequence`:**

```json
{
  "merchant_id": 123456789,
  "country_iso": "FR",
  "site_order": 1,
  "site_id": "000001",
  "parameter_hash": "ab12...ef",
  "manifest_fingerprint": "cd34...90"
}
```

---

### 12.9 Failure vocabulary (write-time)

| Code                              | Trigger                                                                            | Action                                            |
|-----------------------------------|------------------------------------------------------------------------------------|---------------------------------------------------|
| `ERR_S3_EGRESS_SHAPE`             | Schema violation; path↔embed mismatch; forbidden lineage in path; wrong JSON types | Stop S3 for merchant; **no** S3 outputs published |
| `ERR_S3_DUPLICATE_ROW`            | Duplicate key per dataset (e.g., duplicate `(country_iso)` or `(candidate_rank)`)  | Stop S3 for merchant; no outputs                  |
| `ERR_S3_ORDER_MISMATCH`           | `candidate_rank(home)≠0` or ranks not contiguous in emitted candidate set          | Stop S3 for merchant; no outputs                  |
| `ERR_S3_INTEGER_SUM_MISMATCH`     | Emitted counts don’t sum to `N` (when integerising)                                | Stop S3 for merchant; no outputs                  |
| `ERR_S3_SEQUENCE_GAP`/`…OVERFLOW` | See §11 sequencing errors                                                          | Stop S3 for merchant; no outputs                  |

---

### 12.10 Consumability notes (binding where stated)

* **Authority of order:** Consumers must use **`candidate_rank`** for inter-country order; file order is non-normative.
* **Priors meaning:** `base_weight_dp` are deterministic **priors**; consumers must not treat them as probabilities or re-normalise unless a later state explicitly says so.
* **Counts immutability:** If `s3_integerised_counts` is present, those counts are final for this stage and read-only downstream unless a new fingerprint changes.

---

This section gives implementers the **exact** shapes, partitions, lineage rules, and publish discipline for S3 outputs. Paired with §§8–11, it completes the blueprint so L0–L3 can be lifted directly without ambiguity.

---

## S3.13) Idempotence, concurrency, and skip-if-final

### 13.1 Scope (binding)

These rules apply to **all** S3 outputs defined in §12 (required and optional tables). They ensure **re-runs** and **parallelism** produce **byte-identical** results, with no double-writes, no order-dependence, and no cross-merchant interference. S3 uses **no RNG**.

---

### 13.2 Idempotence surface (what defines a unique result)

For a given merchant, S3’s outputs are a **pure function** of:

* The **Context** (§6.5) including `N`, `home_country_iso`, `mcc`, `channel`.
* The opened **artefacts** and **static references** listed in the BOM (§2), by *content bytes* (semver + digest).
* The **policy** (rule ladder) content bytes.
* The run’s **lineage keys** used at write time: `parameter_hash` (partition), `manifest_fingerprint` (embedded).

**Idempotence rule:** Given identical inputs above, S3 **must** produce **byte-identical** rows for the same merchant (same JSON number spellings, same order guarantees, same embedded lineage).

---

### 13.3 Concurrency invariance (parallel-safe by construction)

* **Merchant independence:** Every merchant’s S3 decisions depend only on that merchant’s Context and the governed artefacts. No global mutable state is read or written.
* **No cross-merchant ordering effects:** Sorting/selection rules operate **within merchant** (e.g., `candidate_rank` contiguity), never across merchants.
* **Stable determinism:** Because S3 is deterministic and does not use RNG, **re-partitioning** or changing thread counts **cannot** change bytes.
* **No speculative writes:** A merchant’s rows are written **only after** all its S3 steps succeed (no partial or incremental writes within S3).

---

### 13.4 Skip-if-final (at-most-one per merchant & run)

**Goal:** prevent duplicate rows when resuming or re-running the same logical work.

* **Key for skip:** `(merchant_id, manifest_fingerprint)` within the target dataset and partition `parameter_hash`.
* **Rule:** If rows already exist for a merchant **with the same `manifest_fingerprint`** in the target dataset, S3 **must not** write additional rows for that merchant to the same dataset. Treat as **success** (idempotent no-op).
* **Conflict rule:** If rows exist for `(merchant_id, manifest_fingerprint)` but their bytes **do not** match the would-be output, this is a violation (`ERR_S3_IDEMPOTENCE_VIOLATION`) and S3 must **stop for that merchant** without publishing changes.

> Rationale: S3 tables are **parameter-scoped** in path (`parameter_hash`) and **embed** `manifest_fingerprint`. Multiple manifests may legitimately coexist under the same `parameter_hash`; **skip-if-final** prevents duplicates **within a single manifest**.

---

### 13.5 Dataset-specific uniqueness (per merchant)

Per §12 schemas, the following **must** be unique for each `(merchant_id, manifest_fingerprint)` pair:

* `s3_candidate_set`: keys `(country_iso)` **and** `(candidate_rank)` within a merchant block.
* `s3_base_weight_priors` (if emitted): key `(country_iso)`.
* `s3_integerised_counts` (if emitted): key `(country_iso)`; counts sum to `N`.
* `s3_site_sequence` (if emitted): key `(country_iso, site_order)` (and `(country_iso, site_id)` if present).

Any duplicate key in the same manifest is a shape error (`ERR_S3_DUPLICATE_ROW`) and must abort the merchant’s publish.

---

### 13.6 Publish protocol (atomic; resume-friendly)

* **Stage → fsync → atomic rename.** All S3 tables follow the same publish discipline; partial files are forbidden.
* **Row grouping:** A merchant’s rows **may** be appended to the same output file as other merchants (writer-side batching), but **logical uniqueness** is per keys in §13.5 and skip rule in §13.4.
* **Resume semantics:** On resume, S3 inspects the destination partition for `(merchant_id, manifest_fingerprint)`; if present and byte-identical, it **skips** emitting that merchant (no-op). If missing, it writes the rows atomically.
* **No deletions:** S3 does not delete or rewrite prior manifests; coexistence is allowed (partitioned by `parameter_hash`, distinguished by embedded `manifest_fingerprint`).

---

### 13.7 Read-side selection (downstream hygiene)

Downstream readers **must** select rows for the **intended manifest** by filtering `manifest_fingerprint == <current_run>` in addition to the `parameter_hash` partition. File order is **non-normative**; **`candidate_rank`** is the sole inter-country order (§12.2).

---

### 13.8 Failure vocabulary (merchant-scoped; non-emitting)

| Code                           | Trigger                                                                                           | Action                                   |
|--------------------------------|---------------------------------------------------------------------------------------------------|------------------------------------------|
| `ERR_S3_IDEMPOTENCE_VIOLATION` | Existing rows for `(merchant_id, manifest_fingerprint)` differ byte-wise from the would-be output | Stop S3 for merchant; do **not** publish |
| `ERR_S3_DUPLICATE_ROW`         | Any dataset in §12 detects a key duplicate within `(merchant_id, manifest_fingerprint)`           | Stop S3 for merchant; do **not** publish |
| `ERR_S3_PUBLISH_ATOMICITY`     | Writer cannot guarantee atomic rename / fsync discipline                                          | Stop S3 for merchant; do **not** publish |

---

### 13.9 Invariants (must hold)

* Re-running S3 with the **same** artefacts, parameters, and Context produces **byte-identical** rows for each merchant.
* Parallelism and partitioning **do not** affect outputs.
* For any merchant and manifest, S3 emits **at most one** logical set of rows per dataset (skip-if-final enforced); dataset-specific keys in §13.5 are **unique**.
* All rows embed lineage equal to the run; path partition equals embedded `parameter_hash`.

---

This locks S3’s operational guarantees: **deterministic**, **parallel-safe**, and **resume-safe** with clear failure shapes—so implementers can scale and re-run without drift or surprises.

---

## S3.14) Failure signals (definition-level)

### 14.1 Scope & principles (binding)

* These failures are **definition-level**, not CI corridors. They represent **violations of the S3 spec** (inputs, ordering, shapes, lineage, determinism).
* **Non-emission rule:** On any failure below, **S3 must not publish any S3 outputs** for that merchant (no partial tables).
* **Granularity:** Failures are **merchant-scoped** unless explicitly marked **run-scoped**.
* **Evidence:** S3 may record a **merchant-scoped failure record** for operator visibility (outside S3 egress); this never relaxes the non-emission rule.

---

### 14.2 Merchant-scoped failures (authoritative list)

| Code                              | Trigger (precise)                                                                                                                | Section source | Effect                               |
|-----------------------------------|----------------------------------------------------------------------------------------------------------------------------------|----------------|--------------------------------------|
| `ERR_S3_AUTHORITY_MISSING`        | Any governed artefact in §2/§6 cannot be opened, lacks semver/digest, or the BOM is incomplete                                   | §6.2–§6.3      | **Stop merchant**; no S3 outputs     |
| `ERR_S3_PRECONDITION`             | `is_multi==false` or `N<2` at read time                                                                                          | §6.3.2         | Stop merchant; no outputs            |
| `ERR_S3_PARTITION_MISMATCH`       | For S1/S2 inputs, embedded `{seed,parameter_hash,run_id}` ≠ path partitions                                                      | §6.3.3         | Stop merchant; no outputs            |
| `ERR_S3_VOCAB_INVALID`            | `channel∉(ingress schema’s closed vocabulary)` or `home_country_iso` not in ISO set                                              | §6.3.4         | Stop merchant; no outputs            |
| `ERR_S3_RULE_LADDER_INVALID`      | Rule artefact missing `DEFAULT`, precedence not total, duplicate `rule_id`, unknown `reason_code`/`filter_tag`, or out-of-window | §7.3–§7.4      | Stop merchant; no outputs            |
| `ERR_S3_RULE_EVAL_DOMAIN`         | Rule predicate references an undeclared feature or named set/map                                                                 | §7.9           | Stop merchant; no outputs            |
| `ERR_S3_CANDIDATE_CONSTRUCTION`   | Candidate set empty **or** missing `home`                                                                                        | §8.6           | Stop merchant; no outputs            |
| `ERR_S3_COUNTRY_CODE_INVALID`     | Named set/list expands to a non-ISO code                                                                                         | §8.8           | Stop merchant; no outputs            |
| `ERR_S3_POLICY_REFERENCE_INVALID` | Fired rule references an undefined named set/list                                                                                | §8.8           | Stop merchant; no outputs            |
| `ERR_S3_ORDERING_HOME_MISSING`    | No row with `country_iso==home` when ranking                                                                                     | §9.8           | Stop merchant; no outputs            |
| `ERR_S3_ORDERING_NONCONTIGUOUS`   | Assigned **`candidate_rank`** values are not contiguous `0..\|C\|−1\`                                                            | §9.4–§9.8      | Stop merchant; no outputs            |
| `ERR_S3_ORDERING_KEY_UNDEFINED`   | Cannot reconstruct the **admission key** for a foreign row (no closed mapping from reasons → admitting rule ids)                 | §9.3–§9.8      | Stop merchant; no outputs            |
| `ERR_S3_ORDERING_UNSTABLE`        | Artefact/mapping ambiguity prevents a single total order (e.g., reasons cannot map to rule ids deterministically)                | §9.3, §9.9     | Stop merchant; no outputs            |
| `ERR_S3_WEIGHT_ZERO`              | Priors enabled but `Σ w_i^⋄ == 0`                                                                                                | §10.3.A        | Stop merchant; no outputs            |
| `ERR_S3_WEIGHT_CONFIG`            | Priors enabled but policy config invalid (unknown coeff/param, or required `dp` not declared)                                    | §5.2, §12      | Stop S3 for merchant; no S3 outputs  |
| `ERR_S3_INTEGER_FEASIBILITY`      | Bounds provided but `Σ L_i > N` or `N > Σ U_i`                                                                                   | §10.6          | Stop merchant; no outputs            |
| `ERR_S3_INTEGER_SUM_MISMATCH`     | After allocation, `Σ_i count_i ≠ N`                                                                                              | §10.8–§12.4    | Stop merchant; no outputs            |
| `ERR_S3_INTEGER_NEGATIVE`         | Any `count_i < 0`                                                                                                                | §10.8          | Stop merchant; no outputs            |
| `ERR_S3_SITE_SEQUENCE_OVERFLOW`   | `count_i > 999999` when `site_id` is 6-digit                                                                                     | §11.4, §11.8   | Stop merchant; no outputs            |
| `ERR_S3_SEQUENCE_GAP`             | Missing any integer in `{1..count_i}` within a `(merchant,country)` block                                                        | §11.5–§11.8    | Stop merchant; no outputs            |
| `ERR_S3_SEQUENCE_DUPLICATE`       | Duplicate `site_order` (or `site_id`, if enabled) within a `(merchant,country)` block                                            | §11.5–§11.8    | Stop merchant; no outputs            |
| `ERR_S3_SEQUENCE_ORDER_DRIFT`     | Sequencing permutes inter-country order (contradicts §9 **candidate\_rank**)                                                     | §11.3, §11.9   | Stop merchant; no outputs            |
| `ERR_S3_EGRESS_SHAPE`             | Schema violation; wrong JSON types; path↔embed mismatch; forbidden lineage in path; wrong fixed-dp representation                | §12.1–§12.6    | Stop merchant; no outputs            |
| `ERR_S3_DUPLICATE_ROW`            | Duplicate dataset key per §12.7 (e.g., duplicate `(candidate_rank)` or `(country_iso)`)                                          | §12.7          | Stop merchant; no outputs            |
| `ERR_S3_ORDER_MISMATCH`           | Emitted `s3_candidate_set` violates `candidate_rank(home)=0` or contiguity                                                       | §12.9          | Stop merchant; no outputs            |
| `ERR_S3_IDEMPOTENCE_VIOLATION`    | Existing rows for `(merchant_id, manifest_fingerprint)` differ byte-wise from would-be output (skip-if-final breach)             | §13.4          | Stop merchant; no outputs            |
| `ERR_S3_PUBLISH_ATOMICITY`        | Atomic publish discipline (stage→fsync→rename) cannot be guaranteed                                                              | §13.6          | Stop merchant; no outputs            |

**Effect (all rows):** **no S3 tables** are published for that merchant in this run/fingerprint. Downstream must not see partial S3 state.

---

### 14.3 Run-scoped failures (rare; binding)

Run-scoped failures abort the **entire S3 run** (all merchants).

| Code                              | Trigger                                                                                                   | Effect                         |
|-----------------------------------|-----------------------------------------------------------------------------------------------------------|--------------------------------|
| `ERR_S3_SCHEMA_AUTHORITY_MISSING` | `schemas.layer1.yaml` (authoritative) is unavailable or inconsistent **(or the optional index, if used)** | **Abort run**; publish nothing |
| `ERR_S3_DICTIONARY_INCONSISTENT`  | Dataset dictionary cannot resolve required IDs or partitions for S3                                       | Abort run                      |
| `ERR_S3_BOM_INCONSISTENT`         | BOM claims artefacts that cannot be opened atomically across the run                                      | Abort run                      |

> Prefer merchant-scoped failure whenever the issue is isolated to a merchant; use run-scoped only for global authority problems.

---

### 14.4 Non-emission & logging contract (binding)

* **Non-emission:** On any failure above, S3 writes **no S3 datasets** for that merchant.
* **Logging:** A merchant-scoped failure **may** be recorded to an operator log with `{merchant_id, manifest_fingerprint, code, message, ts_utc}`; this log is **not** part of S3 egress.
* **No retries inside S3:** S3 does not auto-retry/auto-correct; recovery is orchestration policy.

---

### 14.5 Determinism & idempotence under failure

* Failures are **deterministic** given the same inputs; re-running with the same `parameter_hash` and artefacts must yield the **same** failure code.
* Skip-if-final (§13.4) applies only to **successful** publishes; on failure, there are **no** S3 rows to skip.

---

### 14.6 Consumer expectations (downstream hygiene)

* Downstream states **must not** infer intent from absence of S3 rows; orchestration should provide an explicit succeeded/failed roster.
* Consumers **must** filter by the intended `manifest_fingerprint` (§13.7); **do not** join across fingerprints.

---

### 14.7 Mapping index (where each failure originates)

* **§5.2 / §12 (Priors config):** `WEIGHT_CONFIG`
* **§6 (Load scopes):** `AUTHORITY_MISSING`, `PRECONDITION`, `PARTITION_MISMATCH`, `VOCAB_INVALID`
* **§7 (Rule ladder):** `RULE_LADDER_INVALID`, `RULE_EVAL_DOMAIN`
* **§8 (Candidates):** `CANDIDATE_CONSTRUCTION`, `COUNTRY_CODE_INVALID`, `POLICY_REFERENCE_INVALID`
* **§9 (Ordering):** `ORDERING_HOME_MISSING`, `ORDERING_NONCONTIGUOUS`, `ORDERING_KEY_UNDEFINED`, `ORDERING_UNSTABLE`
* **§10 (Integerisation):** `WEIGHT_ZERO`, `INTEGER_FEASIBILITY`, `INTEGER_SUM_MISMATCH`, `INTEGER_NEGATIVE`
* **§11 (Sequencing/IDs):** `SITE_SEQUENCE_OVERFLOW`, `SEQUENCE_GAP`, `SEQUENCE_DUPLICATE`, `SEQUENCE_ORDER_DRIFT`
* **§12 (Emissions):** `EGRESS_SHAPE`, `DUPLICATE_ROW`, `ORDER_MISMATCH`
* **§13 (Ops):** `IDEMPOTENCE_VIOLATION`, `PUBLISH_ATOMICITY`
* **Run-scoped (§14.3):** `SCHEMA_AUTHORITY_MISSING`, `DICTIONARY_INCONSISTENT`, `BOM_INCONSISTENT`

---

This is a **closed catalogue** of S3 failure shapes with crisp triggers and effects, so implementations cannot drift on error handling and L3 can validate outcomes unambiguously.

---

## S3.15) Handoff to S4+

### 15.1 Scope (binding)

This section defines **how downstream states (S4+)** must consume S3 outputs. It is the only authority for:

* which S3 datasets to read,
* the **join keys** and **filters**,
* what fields are **binding** vs **illustrative**, and
* what downstream must **never** reinterpret.

Downstream may not infer semantics outside what is stated here.

---

### 15.2 What downstream must read

#### 15.2.1 Required dataset (always)

| Dataset id         | Purpose                                                 | Filter (must)                                                                  | Ordering (must)                                                                       | Keys for joins               |
|--------------------|---------------------------------------------------------|--------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|------------------------------|
| `s3_candidate_set` | Inter-country **order of record** + policy tags/reasons | Partition by `parameter_hash`; **filter `manifest_fingerprint == <this run>`** | **Order by `(merchant_id ASC, candidate_rank ASC, country_iso ASC)`**; home at rank 0 | `(merchant_id, country_iso)` |

**Binding:** **`candidate_rank`** is the **sole** authority for inter-country order.

#### 15.2.2 Optional datasets (present only if S3 owns them)

| Dataset id              | Purpose                                                        | Filter (must)        | Keys                                       |
|-------------------------|----------------------------------------------------------------|----------------------|--------------------------------------------|
| `s3_base_weight_priors` | Deterministic **priors** (fixed-dp strings), not probabilities | same filter as above | `(merchant_id, country_iso)`               |
| `s3_integerised_counts` | **Final integer counts** per country (sum to `N`)              | same filter as above | `(merchant_id, country_iso)`               |
| `s3_site_sequence`      | Within-country **site\_order** (and optional `site_id`)        | same filter as above | `(merchant_id, country_iso[, site_order])` |

> If an optional dataset is **not** produced by S3, downstream must not invent or guess it. The later state that owns it must produce it under its own spec.

---

### 15.3 Consumer recipe (minimal, closed)

#### 15.3.1 Recover the ordered country list (always)

1. Select `s3_candidate_set` where `parameter_hash = <run.parameter_hash>`.
2. Filter `manifest_fingerprint == <run.manifest_fingerprint>`.
3. For each merchant, read rows ordered by `(candidate_rank ASC, country_iso ASC)`.
4. **Home row:** exactly one row with `candidate_rank == 0` and `is_home == true`.

Outcome: `⟨country_iso[0..M-1]⟩` with `country_iso[0] == home`.

#### 15.3.2 If deterministic priors are present

* Read `s3_base_weight_priors.base_weight_dp` as a **score only** (fixed-dp string).
* Do **not** normalise to probabilities unless a later state explicitly requires it.

#### 15.3.3 If integerised counts are present

* Join `s3_integerised_counts` on `(merchant_id, country_iso)` to get `count`.
* Trust `Σ_i count_i = N`; **do not recompute**. Treat counts as **final** for this stage.

#### 15.3.4 If site sequencing is present

* Join `s3_site_sequence` on `(merchant_id, country_iso)`; rows sorted by `(country_iso, site_order)`.
* Within a country, `site_order` is **contiguous** `1..count_i`.
* If `site_id` exists, it is a **6-digit zero-padded string**; do not change format.

---

### 15.4 What downstream must **not** reinterpret (binding)

* **Inter-country order:** must come **only** from `candidate_rank`. Do not use file order or lexicographic `country_iso`.
* **Priors:** `base_weight_dp` are deterministic **priors**, not probabilities; do not normalise or rescale unless a later state says so.
* **Counts:** if `s3_integerised_counts` exists, counts are **final** for this stage; do not re-integerise or change bump policy.
* **Sequencing:** if `s3_site_sequence` exists, within-country order/IDs are binding; do not renumber or reformat IDs.
* **Policy evidence:** `reason_codes`/`filter_tags` are from **closed vocabularies**; do not remap outside a documented consumer map.

---

### 15.5 Lineage & selection (consumer hygiene)

Consumers **must** filter by both:

* the partition `parameter_hash = <run.parameter_hash>`, **and**
* `manifest_fingerprint == <run.manifest_fingerprint>`.

Do not join across **different fingerprints** unless explicitly implementing a multi-manifest analysis tool (out of scope here).

---

### 15.6 Allowed consumer transforms (safe)

* **Projection:** select a subset of columns.
* **Join:** equi-joins on keys in §15.2/§15.3.
* **Filtering:** by `merchant_id`, `candidate_rank` ranges, or `country_iso` subsets.
* **Stable sorting:** re-sorts that **do not** contradict `candidate_rank` (e.g., group by region but preserve `candidate_rank` within groups).

Any transform that would change `candidate_rank`, `count`, `site_order`, `site_id` format, or the fixed-dp representation of `base_weight_dp` is **not allowed** unless a later state’s spec explicitly authorises it.

---

### 15.7 Variant matrix (S3 configuration → consumer expectations)

| S3 config                                       | candidate\_set | base\_weight\_priors | counts | sequencing | Consumer expectation                                                  |
|-------------------------------------------------|----------------|----------------------|--------|------------|-----------------------------------------------------------------------|
| **A**: order-only                               | ✅              | ❌                    | ❌      | ❌          | Consumer uses **`candidate_rank`** only.                              |
| **B**: order + priors                           | ✅              | ✅                    | ❌      | ❌          | Use `base_weight_dp` as deterministic **prior**; do not normalise.    |
| **C**: order + counts                           | ✅              | ❌                    | ✅      | ❌          | Use `count` as final; no integerisation downstream.                   |
| **D**: order + counts + sequencing              | ✅              | ❌                    | ✅      | ✅          | Read `site_order`/`site_id` as binding within country.                |
| **E**: order + priors + counts (+/− sequencing) | ✅              | ✅                    | ✅      | ±          | Join by keys; priors are scores; counts final; sequencing if present. |

---

### 15.8 Failure surface for consumers (must stop)

A downstream consumer **must** treat these as **fatal** (merchant- or run-scoped per its own policy):

* Missing `s3_candidate_set` rows for the intended fingerprint.
* No `candidate_rank == 0` home row or duplicate `candidate_rank` within a merchant block.
* Present but malformed optional datasets (schema/type mismatches).
* Inconsistent priors (if duplicated elsewhere) or `Σ count ≠ N` (should not happen if S3 is green).
* Path/lineage inconsistencies (enforce §12/§13 read-side hygiene).

---

### 15.9 Forward-compat & evolution (practical guardrails)

* **Adding columns** to S3 tables requires a **schema semver bump** and backward-compatible defaults (or fields marked optional).
* **Changing dp** for priors requires a policy/artefact bump and thus a new `parameter_hash` (and new fingerprint).
* **Changing ID format** (e.g., `site_id`) requires a new schema version and migration note; until then, the 6-digit string is binding.

---

### 15.10 Consumer “green” checklist (quick)

* [ ] Filter by `parameter_hash` and **`manifest_fingerprint`**.
* [ ] Use **`candidate_rank`** as the only inter-country order.
* [ ] If priors exist: treat as deterministic scores (fixed-dp strings).
* [ ] If counts exist: treat as final; sum equals S2 `N`.
* [ ] If sequencing exists: `site_order` contiguous; `site_id` 6-digit string.
* [ ] Do not reinterpret tags/reasons; closed vocabularies only.
* [ ] No cross-fingerprint joins unless expressly required.

---

This handoff locks the **consumer contract** so S4+ can plug in with zero guesswork, zero reinterpretation, and guaranteed reproducibility.

---

## S3.16) Governance & publish

### 16.1 Scope (binding)

Fixes **how S3 is governed and published**: what must be opened and pinned, how lineage is formed, how outputs are staged and atomically committed, and what constitutes a valid publish. Applies to **all S3 datasets** defined in §12.

---

### 16.2 Artefact closure (BOM must be complete)

* S3 **may only** open artefacts explicitly listed in the BOM (§2).
* **Atomic open:** all governed artefacts (§2.1) are opened **before** any S3 processing starts. A missing/changed artefact after S3 begins is `ERR_S3_AUTHORITY_MISSING` (merchant-scoped stop).
* **No late opens:** later S3 steps **must not** open artefacts beyond §2.

---

### 16.3 Lineage keys (definitions & scope)

* **`parameter_hash` (path partition)** — hash of **parameter artefacts only** that affect S3 semantics (e.g., `policy.s3.rule_ladder.yaml`, `policy.s3.base_weight.yaml`, integerisation bounds). Changing any such parameter **changes the partition**.
* **`manifest_fingerprint` (embedded)** — composite derived from **all opened artefacts** (BOM closure), **parameter bytes**, and code/commit identity (project-defined). Any byte change flips the fingerprint.
* **No `seed` in S3 paths:** S3 outputs are **parameter-scoped**; `seed` appears only as an embedded lineage field if carried for joins.

**Binding equality:** every emitted row **embeds** `{parameter_hash, manifest_fingerprint}` that **byte-equal** the path partition (for `parameter_hash`) and the run’s fingerprint (§12.6).

---

### 16.4 Versioning & change policy

* **SemVer on artefacts:** governed artefacts carry semantic versions. Backward-compatible additions (that don’t change outcomes) may bump patch/minor. Any change that *can* alter S3 outputs **must** bump minor/major and will flip both `parameter_hash` and `manifest_fingerprint`.
* **Closed vocab drift:** adding/changing a `reason_code` / `filter_tag` / `rule_id` is *governed*; bump policy version and expect lineage flips.
* **Schema evolution:** any column addition/removal/type change is a **schema semver bump**; see consumer guidance in §15.9.

---

### 16.5 Publish protocol (atomic; resume-safe)

* **Resolution:** writers resolve dataset **IDs** to paths using the **dataset dictionary** (no literals).
* **Stage → fsync → atomic rename:** write to a staging area on the same filesystem, fsync, then atomically rename into `parameter_hash=…`.
* **All-or-nothing per dataset:** for a merchant, either the complete row-set for that dataset is present **byte-identical** to computed rows, or nothing is written. Partials are forbidden.
* **Skip-if-final:** before writing, check for existing rows for `(merchant_id, manifest_fingerprint)` in the target partition. If present and **byte-identical**, **skip** (idempotent no-op). If present but bytes differ ⇒ `ERR_S3_IDEMPOTENCE_VIOLATION` (no publish).
* **No deletes:** S3 never deletes prior manifests. Multiple manifests may coexist under the same `parameter_hash`; selection is via `manifest_fingerprint` (§15.5).

---

### 16.6 Partitioning & embedded lineage (write-side checks)

For every emitted dataset:

* **Partition:** `parameter_hash` only (no `seed`, no `run_id` in the path).
* **Embed:** each row embeds `{parameter_hash, manifest_fingerprint}` that **byte-equal** the path partition (for `parameter_hash`) and the run fingerprint.
* **Types:** lineage fields are **lowercase Hex64** strings; payload numbers are JSON **numbers**; fixed-dp priors are JSON **strings**.

Mismatch ⇒ **`ERR_S3_EGRESS_SHAPE`** and blocks publish for that merchant.

---

### 16.7 Governance attest (minimal, binding)

At publish time S3 must retain (operator audit; **outside S3 egress**):

* the **BOM snapshot** used (artefact ids, semver, digests),
* the **dictionary version** used to resolve paths, and
* the **schema authority/version** (`schemas.layer1.yaml`) and, if used, the **schema index** version.

---

### 16.8 Licence & provenance (must be auditable)

* Every external static reference (e.g., ISO list) must have recorded **licence** and **provenance** (§2.7).
* If licence constraints limit redistribution, embed **digests** and refer to artefacts by **id/version** (not copies).

---

### 16.9 Operator-visible publish receipt (optional; non-egress)

Optionally record a **publish receipt** per merchant (outside S3 datasets) with:

* `merchant_id`, `manifest_fingerprint`, `parameter_hash`, dataset ids written, row counts, and `ts_utc`.
  This improves observability only; presence/absence does **not** alter S3 semantics.

---

### 16.10 Run gating & dependencies (what S3 requires before start)

* **Schema authority present:** `schemas.layer1.yaml` containing all `#/s3/*` anchors is available and consistent; the **schema index** (if used) is also consistent.
* **Dictionary present:** required dataset IDs/partitions resolve.
* **BOM complete:** governed artefacts can be opened atomically.

Violation of any of the above is **run-scoped** failure (§14.3): `ERR_S3_SCHEMA_AUTHORITY_MISSING`, `ERR_S3_DICTIONARY_INCONSISTENT`, or `ERR_S3_BOM_INCONSISTENT`.

---

### 16.11 Governance “green” checklist (tick before publish)

* [ ] All governed artefacts from §2.1 opened **before** processing; no late opens.
* [ ] `parameter_hash` reflects all **parameter** artefacts; `manifest_fingerprint` reflects **all opened artefacts + parameters + code id**.
* [ ] All datasets resolved via the **dictionary**; **no path literals**.
* [ ] Partition and embedded lineage **match** (byte-equal).
* [ ] Skip-if-final performed; no duplicate logical writes.
* [ ] Atomic stage→fsync→rename completed without error.
* [ ] Optional receipts/attestations captured for operator audit.

---

### 16.12 Invariants (must hold)

* Given identical Context and artefact bytes, two S3 publishes produce **byte-identical** outputs.
* Re-partitioning or concurrency does **not** change outputs (no RNG; deterministic rules).
* For any dataset and merchant, there exists **at most one** logical row-set per `(manifest_fingerprint)`; duplicates are prevented by skip-if-final.
* All S3 outputs are parameter-scoped in path and carry embedded lineage equal to the run.

---

This governance & publish contract keeps S3 **reproducible**, **auditable**, and **operator-safe**—so implementers’ bytes are accepted or rejected in a predictable, deterministic way.

---

## S3.17) Worked micro-examples (illustrative)

These are **non-normative** sanity checks that show how the spec behaves on small inputs. Shapes and numbers are **illustrative** only; the **normative** behavior is in §§6–16. All paths resolve via the **dataset dictionary**; examples show **logical rows** only.

---

### 17.1 Minimal “allow” example — order + priors + integerisation

**Context.**
Merchant `m=123456789`, `home=GB`, `N=7` (from S2). Rule ladder fires `ALLOW_WHITELIST` (decision source) and `LEGAL_OK`; cross-border **eligible**.

**Candidate universe (§8).**
`C = { GB, DE, FR }`, each row tagged (closed vocab):

* `reason_codes`: `["ALLOW_WHITELIST","LEGAL_OK"]` (A→Z),
* `filter_tags`: `["GEO_OK"]` plus `"HOME"` for GB.

**Priors enabled (§12, dp=6).**
Deterministic priors are computed and **quantised** (RNE, binary64):

| country | conceptual `w_i` | **emitted** `w_i^⋄` (fixed-dp string) |
|:-------:|-----------------:|--------------------------------------:|
|   GB    |           0.275… |                          `"0.275000"` |
|   DE    |           0.180… |                          `"0.180000"` |
|   FR    |           0.120… |                          `"0.120000"` |

Sum of quantised priors = `0.575000`.

**Ordering (§9 — ranking is independent of priors).**
`candidate_rank(GB)=0`. For foreigns, the **admission key** (precedence→priority→rule\_id) ties; break by **ISO A→Z**: `DE` before `FR`.
Final order: `GB(0) → DE(1) → FR(2)`.

**Integerisation (§10, dp\_resid=8).**
Use quantised priors for shares: `a_i = N * w_i^⋄ / Σ w^⋄`.

* GB: `7*(0.275/0.575)=3.348…` → `b=3`, `r=0.348…`
* DE: `7*(0.180/0.575)=2.191…` → `b=2`, `r=0.191…`
* FR: `7*(0.120/0.575)=1.460…` → `b=1`, `r=0.460…`
  Remainder `d = 7 − (3+2+1) = 1`. Quantise residuals to **8 dp**; bump highest (`FR`) by +1.

**Final counts & residual ranks.**

* `GB: 3` (residual\_rank=2)
* `DE: 2` (residual\_rank=3)
* `FR: 2` (residual\_rank=1)
  Sum = 7 = `N`. **`candidate_rank` unchanged.**

**Illustrative rows (egress; §12).**

*`s3_candidate_set` (subset):*

```json
{ "merchant_id": 123456789, "country_iso": "GB", "candidate_rank": 0, "is_home": true,
  "reason_codes": ["ALLOW_WHITELIST","LEGAL_OK"], "filter_tags": ["GEO_OK","HOME"],
  "parameter_hash": "ab12...ef", "manifest_fingerprint": "cd34...90" }
{ "merchant_id": 123456789, "country_iso": "DE", "candidate_rank": 1, "is_home": false,
  "reason_codes": ["ALLOW_WHITELIST","LEGAL_OK"], "filter_tags": ["GEO_OK"],
  "parameter_hash": "ab12...ef", "manifest_fingerprint": "cd34...90" }
{ "merchant_id": 123456789, "country_iso": "FR", "candidate_rank": 2, "is_home": false,
  "reason_codes": ["ALLOW_WHITELIST","LEGAL_OK"], "filter_tags": ["GEO_OK"],
  "parameter_hash": "ab12...ef", "manifest_fingerprint": "cd34...90" }
```

*`s3_base_weight_priors`:*

```json
{ "merchant_id": 123456789, "country_iso": "GB", "base_weight_dp": "0.275000", "dp": 6,
  "parameter_hash": "ab12...ef", "manifest_fingerprint": "cd34...90" }
{ "merchant_id": 123456789, "country_iso": "DE", "base_weight_dp": "0.180000", "dp": 6,
  "parameter_hash": "ab12...ef", "manifest_fingerprint": "cd34...90" }
{ "merchant_id": 123456789, "country_iso": "FR", "base_weight_dp": "0.120000", "dp": 6,
  "parameter_hash": "ab12...ef", "manifest_fingerprint": "cd34...90" }
```

*`s3_integerised_counts`:*

```json
{ "merchant_id": 123456789, "country_iso": "GB", "count": 3, "residual_rank": 2,
  "parameter_hash": "ab12...ef", "manifest_fingerprint": "cd34...90" }
{ "merchant_id": 123456789, "country_iso": "DE", "count": 2, "residual_rank": 3,
  "parameter_hash": "ab12...ef", "manifest_fingerprint": "cd34...90" }
{ "merchant_id": 123456789, "country_iso": "FR", "count": 2, "residual_rank": 1,
  "parameter_hash": "ab12...ef", "manifest_fingerprint": "cd34...90" }
```

*(If S3 also owns sequencing; §11):*

```json
{ "merchant_id": 123456789, "country_iso": "FR", "site_order": 1, "site_id": "000001",
  "parameter_hash": "ab12...ef", "manifest_fingerprint": "cd34...90" }
{ "merchant_id": 123456789, "country_iso": "FR", "site_order": 2, "site_id": "000002",
  "parameter_hash": "ab12...ef", "manifest_fingerprint": "cd34...90" }
```

**Quick checks.**
`candidate_rank(home)=0`; ranks contiguous; priors are fixed-dp strings but **not used for ranking**; residuals use **dp\_resid=8**; counts sum to `N`; lineage embeds match partition.

---

### 17.2 Tie-heavy example — no priors, ISO tiebreak

**Context.**
Merchant `m=555`, `home=US`, `N=5`. Ladder admits `{CA, CH}` under the same admit rule, so admission keys tie.

**Candidate universe (§8).**
`C = { US, CA, CH }`; unioned `reason_codes` equal across CA/CH.

**Ordering (§9).**
Home gets `candidate_rank=0`. Foreigns tie on admission key; break by **ISO A→Z** → `CA` then `CH`.
Final order: `US(0) → CA(1) → CH(2)`.

**Integerisation (equal-weights; §10).**
`M=3`; `a_i = 5/3 = 1.666…`. Floors `[1,1,1]`, remainder `d=2`.
Residuals equal; ISO tiebreak bumps `CA` then `CH`.
Counts: `US=1`, `CA=2`, `CH=2`; residual ranks: `CA:1`, `CH:2`, `US:3`.

*`s3_integerised_counts`:*

```json
{ "merchant_id": 555, "country_iso": "US", "count": 1, "residual_rank": 3,
  "parameter_hash": "aa00...11", "manifest_fingerprint": "bb22...33" }
{ "merchant_id": 555, "country_iso": "CA", "count": 2, "residual_rank": 1,
  "parameter_hash": "aa00...11", "manifest_fingerprint": "bb22...33" }
{ "merchant_id": 555, "country_iso": "CH", "count": 2, "residual_rank": 2,
  "parameter_hash": "aa00...11", "manifest_fingerprint": "bb22...33" }
```

**Quick checks.**
Ties resolved by ISO; **`candidate_rank`** is the authority; counts sum to `N`; `residual_rank` reconstructs bump set `{CA,CH}`.

---

### 17.3 No-foreign example — deny cross-border

**Context.**
Merchant `m=777`, `home=AE`, `N=4`. Ladder’s `DENY_SANCTIONED` (decision source) yields `eligible_crossborder=false`.

**Candidate universe (§8).**
`C = { AE }` only; `K_foreign=0`.

**Ordering (§9).**
Trivial: `candidate_rank(AE)=0`.

**Integerisation (§10).**
If S3 owns counts: `count(AE) = 4`. No residuals (single row).

*Illustrative rows:*

```json
{ "merchant_id": 777, "country_iso": "AE", "candidate_rank": 0, "is_home": true,
  "reason_codes": ["DENY_SANCTIONED"], "filter_tags": ["HOME"],
  "parameter_hash": "fe98...76", "manifest_fingerprint": "dc54...32" }
```

```json
{ "merchant_id": 777, "country_iso": "AE", "count": 4, "residual_rank": 1,
  "parameter_hash": "fe98...76", "manifest_fingerprint": "dc54...32" }
```

**Quick checks.**
Candidate set non-empty with `home`; **`candidate_rank(home)=0`**; counts (if present) sum to `N`.

---

### 17.4 Edge case with bounds — bounded Hamilton (optional)

**Context.**
Merchant `m=888`, `home=GB`, `N=6`, candidates `{GB, IE, NL}` with fixed-dp priors (`dp=6`):
`"0.500000"`, `"0.300000"`, `"0.200000"`. Bounds: `L = {1,0,0}`, `U = {6,3,3}`.

**Step 1 (floor to L).** `b = {1,0,0}`, remaining `N′=5`, capacities `{5,3,3}`.
**Step 2 (shares over cap>0).** Same priors; `a′ = 5 * {0.5,0.3,0.2} = {2.5,1.5,1.0}` → `f = {2,1,1}` (cap-limited), `d′ = 5 − 4 = 1`.
**Step 3 (residuals, dp\_resid=8).** Residuals `{0.5,0.5,0.0}` → ISO tiebreak: `GB` before `IE`. Bump `GB` by +1.
**Final counts.** `GB=1+2+1=4`, `IE=0+1=1`, `NL=0+1=1` (within bounds; sum=6).

*`s3_integerised_counts`:*

```json
{ "merchant_id": 888, "country_iso": "GB", "count": 4, "residual_rank": 1,
  "parameter_hash": "1357...9b", "manifest_fingerprint": "2468...ac" }
{ "merchant_id": 888, "country_iso": "IE", "count": 1, "residual_rank": 2,
  "parameter_hash": "1357...9b", "manifest_fingerprint": "2468...ac" }
{ "merchant_id": 888, "country_iso": "NL", "count": 1, "residual_rank": 3,
  "parameter_hash": "1357...9b", "manifest_fingerprint": "2468...ac" }
```

**Quick checks.**
Feasibility ok; `L_i ≤ count_i ≤ U_i`; ISO tiebreak visible; sum equals `N`.

---

### 17.5 “Green” checklist for examples (what to verify quickly)

* [ ] **`candidate_rank(home)=0`**; ranks contiguous; no duplicate `country_iso`.
* [ ] If priors shown: fixed-dp **strings**; **ranking never uses priors** (priors affect integerisation only).
* [ ] Integerisation: residuals computed **after** dp; **`dp_resid=8`**; ties by ISO; counts sum to `N`.
* [ ] `residual_rank` present for **every** row when counts are emitted.
* [ ] Embedded lineage present and matches the active partition (`parameter_hash`) and run (`manifest_fingerprint`).
* [ ] No event streams (S3 uses none); only tables per §12.

---

*End of illustrative examples.*

---

## S3.18) Validator proof obligations (what L3 will re-derive)

### 18.1 Scope (binding)

* L3 is **read-only**. It **does not** mutate S3 outputs or produce S3 datasets.
* L3 **re-derives** the deterministic facts S3 promised in §§6–16 and either:
  • emits a **PASS** (run-scoped receipt outside S3 egress), or
  • raises the **precise** failure code(s) in §14 (merchant-scoped unless marked run-scoped).
* **No RNG**, no time dependence, no host state.

---

### 18.2 Inputs L3 must read (authoritative)

* **Schema authority & dictionary** (run-scoped gate): `schemas.layer1.yaml` containing all `#/s3/*` anchors; **optional** schema index if used; dataset dictionary resolving all S3 IDs.
* **Governed artefacts** listed in the S3 BOM (§2): `policy.s3.rule_ladder.yaml`, `iso3166_canonical_2024`, and any optional policy bundles (priors, bounds).
* **S3 datasets (egress)** for the target `parameter_hash`, **filtered by `manifest_fingerprint == <this run>`**:
  `s3_candidate_set` (required); and optionally `s3_base_weight_priors`, `s3_integerised_counts`, `s3_site_sequence`.
* **Upstream evidence (read-only)** for cross-checks: S1 `hurdle_bernoulli` (gate) and S2 `nb_final` (for **N only**) for the same `{seed, parameter_hash, run_id}`.

*(All locations resolve via the dictionary; no literal paths.)*

---

### 18.3 What L3 must *never* do

* Must **not** “fix” data, interpolate, or re-emit S3 rows.
* Must **not** derive features not declared in §§2/6.
* Must **not** treat file order as semantic; only spec’d keys/order count.

---

### 18.4 Proof obligations (per merchant unless stated)

> Ordered **shape → lineage → order/math → cross-dataset coherence**. Each item cites the failure code on breach.

#### V1 — Schema & JSON typing (shape)

* Every S3 row conforms to its **JSON-Schema** (§12).
* Numeric payload fields are JSON **numbers**; fixed-dp priors (if present) are JSON **strings** with exactly `dp` places.
  → `ERR_S3_EGRESS_SHAPE`.

#### V2 — Partition ↔ embed equality (lineage)

* Embedded `parameter_hash` equals the **path partition**; embedded `manifest_fingerprint` equals the run fingerprint.
* S3 paths contain **no `seed`**.
  → `ERR_S3_EGRESS_SHAPE`.

#### V3 — Gating & presence

* Join to S1: merchants with `is_multi==false` have **no S3 rows**.
* Join to S2: merchants used by S3 have exactly one `nb_final` with **`N ≥ 2`**.
  → `ERR_S3_PRECONDITION`.

#### V4 — Candidate coverage & uniqueness

* `s3_candidate_set` exists; includes **exactly one** home row; **no duplicate** `(country_iso)`; all `country_iso ∈ ISO`.
  → `ERR_S3_CANDIDATE_CONSTRUCTION` or `ERR_S3_COUNTRY_CODE_INVALID`.

#### V5 — Rank law (total order)

* Per merchant, **`candidate_rank`** is **contiguous** `0..|C|−1`; exactly one row has `candidate_rank==0` and `is_home==true`.
  → `ERR_S3_ORDERING_NONCONTIGUOUS` or `ERR_S3_ORDERING_HOME_MISSING`.

#### V6 — Ordering proof (primary key = admission order key)

* Reconstruct each foreign row’s **admission key** from the artefact’s **closed mapping** (row `reason_codes[]` → admitting rule id(s)), then compute:

  ```
  K(r) = ⟨ precedence_rank(r), priority(r), rule_id_ASC ⟩
  Key1(i) = min_lex { K(r) : r ∈ AdmitRules(i) }
  ```
* Sort foreign rows by `Key1` → ISO A→Z; pin `home → candidate_rank=0`. The resulting order must match **`candidate_rank`**.
  → `ERR_S3_ORDERING_KEY_UNDEFINED` (cannot reconstruct key) or `ERR_S3_ORDERING_UNSTABLE` (mismatch).

#### V7 — Priors surface (if present)

* If `s3_base_weight_priors` exists:
  • `base_weight_dp` parses as a fixed-dp decimal; **dp is constant within the run**.
  • Values are deterministic strings; no duplicate `(merchant_id,country_iso)`.
  *(No equality check vs candidate\_set — priors live **only** here.)*
  → `ERR_S3_EGRESS_SHAPE`.

#### V8 — Integerisation reconstruction (if counts present)

* From S2 **N** and §10 policy:
  • If priors exist: use **quantised** `w_i^⋄` (from `base_weight_dp`) for shares; else equal shares.
  • Compute `a_i`, floors `b_i`, remainder `d`, residuals `r_i`; **quantise residuals to `dp_resid=8`**; apply bump rule (residual DESC → ISO A→Z → `candidate_rank` → stability).
  • Reconstruct `count_i`; verify **`Σ count_i = N`**, `count_i ≥ 0`; and `residual_rank` matches the bump order for **all** rows.
  → `ERR_S3_INTEGER_SUM_MISMATCH`, `ERR_S3_INTEGER_NEGATIVE`.

#### V9 — Bounds (optional policy)

* If `(L_i,U_i)` are declared: verify `Σ L_i ≤ N ≤ Σ U_i` and `L_i ≤ count_i ≤ U_i`.
  → `ERR_S3_INTEGER_FEASIBILITY`.

#### V10 — Sequencing (if S3 emits it)

* For each `(merchant_id,country_iso)` in `s3_site_sequence`:
  • `site_order` is **exactly** `1..count_i` (use counts if present; else check contiguity alone).
  • If `site_id` present: **6-digit zero-padded string**; uniqueness within the block.
  • Every `(merchant_id,country_iso)` also appears in `s3_candidate_set`.
  → `ERR_S3_SEQUENCE_GAP`, `ERR_S3_SEQUENCE_DUPLICATE`, or `ERR_S3_SITE_SEQUENCE_OVERFLOW`.

#### V11 — Cross-dataset coherence

* Keys align across datasets (where present): `candidate_set` ↔ `base_weight_priors` ↔ `integerised_counts` ↔ `site_sequence`.
* No extra countries appear in optional tables that are absent from `candidate_set`.
  → `ERR_S3_EGRESS_SHAPE`.

#### V12 — Dataset-specific uniqueness (write-side)

* Enforce §12.7 uniqueness:
  `candidate_set`: unique `(country_iso)` **and** `(candidate_rank)`;
  `base_weight_priors`: unique `(country_iso)`;
  `integerised_counts`: unique `(country_iso)`;
  `site_sequence`: unique `(country_iso, site_order)` (and `(country_iso, site_id)` if present).
  → `ERR_S3_DUPLICATE_ROW`.

#### V13 — Idempotence surface (semantic)

* Re-compute a **content hash** of each merchant’s would-be rows from artefacts+Context to demonstrate outputs are a pure function (no dependency on file order/concurrency/host).
* If the same `(merchant_id, manifest_fingerprint)` already exists and bytes **differ**, classify as idempotence breach.
  → `ERR_S3_IDEMPOTENCE_VIOLATION`.

#### V14 — Publish discipline (run-scoped sanity)

* Stage→fsync→atomic rename in use; no partials; no forbidden lineage in paths.
  → `ERR_S3_PUBLISH_ATOMICITY` (run-scoped) or `ERR_S3_EGRESS_SHAPE` (lineage/path issues).

---

### 18.5 Non-emission confirmation

On any merchant-scoped failure above, **no S3 tables** for that merchant are valid for this fingerprint. L3 treats the merchant as **failed** and excludes them from PASS.

---

### 18.6 PASS criteria (per merchant and run)

A merchant **PASS** iff **all** applicable obligations V1–V12 succeed.
The run **PASS** iff:

* all merchants PASS, and
* V14 (publish discipline) holds.

*(L3 may publish a small PASS/FAIL receipt outside S3 egress; content & location are governance-side and non-normative.)*

---

### 18.7 Validator “green” checklist (quick)

* [ ] All S3 rows conform to schemas; JSON numbers/strings as specified.
* [ ] Path partitions = embedded lineage; no `seed` in paths.
* [ ] Candidate coverage: non-empty; unique countries; home present.
* [ ] **`candidate_rank`** contiguous; `candidate_rank(home)=0`.
* [ ] Ordering proof matches (admission-key path).
* [ ] If priors present: fixed-dp strings; **dp constant** within run.
* [ ] If counts present: sum to **N**; `residual_rank` reconstructs bumps (`dp_resid=8`); bounds respected (if any).
* [ ] If sequencing present: contiguous `site_order`; 6-digit `site_id`; keys coherent.
* [ ] Dataset-specific uniqueness holds.
* [ ] No idempotence/publish breaches detected.

---

With these obligations, L3 can **mechanically** prove S3 kept its promises—no RNG, no ambiguity, byte-replayable ordering & integerisation, correct lineage, and run-safe publishing—so downstream can rely on S3 without surprises.

---


[S3-END VERBATIM]

---

# S4 — Expanded
<a id="#S4.EXP"></a>
<!-- SOURCE: /s3/states/state.1A.s4.expanded.txt  *  VERSION: v0.0.0 -->

[S4-BEGIN VERBATIM]

## S4.0) Document contract & status

**Status.** Draft (to be Frozen).

**Master spec.** This document is **normative** for S4. Any pseudocode shown here is **illustrative** only; the definitive, language-agnostic build guidance must **derive** from this spec.

**Schema authority.** For 1A, **JSON-Schema is the single schema authority**; registry/dictionary entries point only to `schemas.*.yaml` anchors (JSON Pointer fragments). Avro, if generated, is **non-authoritative** and must **not** be referenced by 1A artefacts.

**Inherited numeric/RNG law (from S0).**

* IEEE-754 **binary64**, **RNE**, **FMA-off**, **no FTZ/DAZ** for any computation that can affect decisions/order. Non-finite values are hard errors.
* PRNG is **counter-based Philox** with **open-interval** mapping `u∈(0,1)`; **draws** = actual uniforms consumed; **blocks** = counter delta. Envelopes and trace obey the budgeting/trace rules already established upstream.

**Lineage & partitions (read-side discipline).** Where S4 reads upstream RNG events (S1/S2), **path partitions must equal embedded envelope fields** `{seed, parameter_hash, run_id}` **byte-for-byte**. S4 itself **emits logs only** (no Parquet egress).

**Scope boundary (what S4 does / doesn’t).**

* **Does:** compute `λ_extra`, sample ZTP for a foreign-count **target `K_target`**, and emit **RNG events only** (including a **non-consuming finaliser** that fixes `K_target`).
* **Does not:** choose countries (S6), allocate counts (S7), sequence/IDs or write `outlet_catalogue` (S8), or produce validation bundles (S9). Authority for inter-country order remains in S3’s `candidate_set`/`candidate_rank`.

**Branch purity (gates owned upstream).** S4 runs **only** for merchants with **S1 `is_multi=true`** and **S3 `is_eligible=true`**; singles and ineligible merchants produce **no S4 events**.

---

## S4.0A) One-page quick map (for implementers)

> A single-screen view of **what runs**, **what’s read/written**, and **where S4 hands off**. All MUST/SHOULD rules are defined in §§0–2A and later sections; this is the wiring diagram you keep beside the code.

### Flow (gates → ZTP loop → outcomes)

```
S1 hurdle      S3 eligibility        S3 admissible set size A
is_multi? ──►  is_eligible? ──►  compute A := size(S3.candidate_set \ {home})
   │ no             │ no                     │
   └──────────► BYPASS S4 (domestic only) ◄──┘

            yes             yes
                 ▼
           [Parameterise]
  η = θ0 + θ1·log N + θ2·X (binary64, fixed order)
  λ = exp(η) ; if non-finite/≤0 → NUMERIC_INVALID (abort S4 for m)

                 ▼
       A == 0 ? ────────────── yes ──►  emit ztp_final{K_target=0[, reason:"no_admissible"]?} (non-consuming)
           │ no
           ▼
     ZTP attempt loop (attempt = 1..)
       draw K ~ Poisson(λ)  →  emit poisson_component{attempt, k} (consuming)
             │
             ├─ K == 0 → emit ztp_rejection{attempt} (non-consuming) → next attempt
             │
             ├─ K ≥ 1 → ACCEPT:
             │          emit ztp_final{K_target=K, attempts=attempt, exhausted=false} (non-consuming)
             │          STOP
             │
             └─ attempts == MAX_ZTP_ZERO_ATTEMPTS ?
                    │ yes → policy:
                    │        • "abort"  → emit ztp_retry_exhausted{attempts, aborted:true} (non-consuming); ZTP_EXHAUSTED_ABORT (no final)
                    │        • "downgrade_domestic" → emit ztp_final{K_target=0, exhausted:true} (non-consuming)
                    └ no  → next attempt
```

**After each event append:** append exactly **one** cumulative `rng_trace_log` row (saturating totals).

---

### Quick I/O (what S4 reads and writes)

**Reads (values / streams):**

* **S1 hurdle** (gate): `is_multi=true` ⇒ in scope.
* **S2 `nb_final`** (fact): authoritative **`N ≥ 2`** (non-consuming).
* **S3 eligibility** (gate) and **A** definition: **`A := size(S3.candidate_set \ {home})`**.
* **Hyper-parameters** `θ`, **cap** `MAX_ZTP_ZERO_ATTEMPTS` (governed), **policy** `ztp_exhaustion_policy`.
* **Features** `X ∈ [0,1]` (default **0.0** if missing).

**Writes (logs only; partitions from dictionary = `{seed, parameter_hash, run_id}`):**

* `rng_event_poisson_component` (context=`"ztp"`) — **consuming** attempts (`attempt` is **1-based**).
* `rng_event_ztp_rejection` — **non-consuming** zero markers.
* `rng_event_ztp_retry_exhausted` — **non-consuming** cap marker.
* `rng_event_ztp_final` — **non-consuming** finaliser fixing `{K_target, lambda_extra, attempts, regime, exhausted?}`.
* `rng_trace_log` — **one row per event append** (cumulative, saturating).

---

### Hard literals & regimes (so no one guesses)

* **module:** `1A.s4.ztp`
* **substream_label:** `poisson_component`
* **context:** `"ztp"`
* **Poisson regimes:** **Inversion** if `λ < 10`, **PTRS** if `λ ≥ 10` (spec-fixed threshold/constants).
* **Budget law:** `draws` = uniforms consumed; `blocks` = `after − before`.
* **File order is non-authoritative** — pairing/replay by **counters** only.

---

### Handoff (what downstream consumes)

* S4 exports **`K_target`** (or `K_target=0` via `A=0` short-circuit or policy **downgrade**).
* **S6 MUST realise** `K_realized = min(K_target, A)` (select up to `K_realized` foreigns); S6 owns selection/weights.
* S4 **never** encodes inter-country order (still only in S3 `candidate_rank`).

---

## S4.1) Purpose, scope & non-goals

### Purpose (what S4 is).
For each merchant `m` on the eligible multi-site branch, compute a deterministic **log-link**

$$
\eta_m=\theta_0+\theta_1\log N_m+\theta_2 X_m+\cdots\quad\text{(binary64, fixed order)}
$$
**Informative.** Governance MAY prefer a sub-linear size effect; this is **not** a protocol constraint.

and set $\lambda_{\text{extra},m}=\exp(\eta_m)>0$; then **sample ZTP** by drawing from Poisson$(\lambda)$ and **rejecting zeros** until acceptance or a governed **zero-draw cap** is hit. Record the attempt stream(s), zero-rejection markers, and a **non-consuming finaliser** that fixes **`K_target`** and run facts. S4 writes **no Parquet egress**—only RNG event logs under dictionary partitions `{seed, parameter_hash, run_id}`.
**By definition ZTP yields `K ≥ 1`; `K_target = 0` occurs only via (a) the `A=0` short-circuit or (b) the exhaustion policy = `"downgrade_domestic"` (never from ZTP itself).**

### Scope (what S4 owns).

* **Parameterisation:** evaluate $\eta$ and $\lambda$ in **binary64** with fixed operation order; **abort** the merchant if $\lambda$ is non-finite or ≤ 0. (If the features view lacks `X_m`, use **`X_m := 0.0`**.)
* **RNG protocol:** use keyed Philox substreams; **open-interval** $u\in(0,1)$; per-event envelopes obey **draws vs blocks** identities. **After each S4 event append, the producer MUST append exactly one cumulative `rng_trace_log` row** (saturating totals) for the S4 module/substream.
* **Events produced (logs-only):**

  1. one or more `poisson_component` attempts with `context:"ztp"` (**consuming**; attempts are **1-based**: `attempt = 1,2,…`),
  2. `ztp_rejection` markers for zeros (**non-consuming**),
  3. optional `ztp_retry_exhausted` on cap (**non-consuming**),
  4. **exactly one** `ztp_final` (**non-consuming**) that **fixes** `{K_target, lambda_extra, attempts, regime, exhausted?}`.

### Non-goals (what S4 must not do).

* **No re-sampling or alteration of `N`.** Authoritative **`N`** is fixed by S2’s non-consuming `nb_final`; S4 only **reads** it.
* **No country choice or order.** S4 **does not** select which countries—S6 does; order authority remains S3’s `candidate_rank (home=0; contiguous)`.
* **No integerisation or sequencing.** Counts allocation (S7) and within-country sequence/IDs (S8) are out of scope here.
* **No egress or consumer gates.** `outlet_catalogue` and the 1A→1B gate live in S9.
* **No path literals.** All locations are dictionary-resolved; events must be written under `{seed, parameter_hash, run_id}` with **path↔embed equality** for those keys.

### Branch & universe awareness (clarifying notes).

* **Definition of the admissible foreign universe.** Let **`A := size(S3.candidate_set \ {home})`**.
* **Eligibility short-circuit (`A=0`).** If **A=0** for a merchant, S4 **MUST NOT** sample and must resolve the merchant with a **finaliser carrying `K_target=0`** and, if the schema includes this optional field, `reason:"no_admissible"` (domestic-only downstream).
* **Cap governance.** The zero-draw cap **`MAX_ZTP_ZERO_ATTEMPTS`** is a **governed value** (default **64**) that **participates in `parameter_hash`**; the **exhaustion policy** `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}` is also governed and participates in `parameter_hash`.

### Hand-off contract (forward-looking pointer).
S4 **exports** an accepted **`K_target`** (or a deterministic `K_target=0` under short-circuit/policy). **S6 must realise**

$$
K_{\text{realized}}=\min\big(K_{\text{target}},\,A\big),
$$

and may log a shortfall marker in its own state; S4 does **not** encode inter-country order at any point (that remains in S3).

---

## S4.2) Authorities & schema anchors

### Single schema authority.
For 1A, **JSON-Schema is the only schema authority**. Every dataset/stream S4 references **must** be a `schema_ref` JSON Pointer into `schemas.*.yaml`. Avro (`.avsc`) may be generated but is **non-authoritative** and **must not** be referenced by the registry/dictionary.

### What S4 writes (logs only): authoritative event anchors.

* `schemas.layer1.yaml#/rng/events/poisson_component` — **consuming** attempt rows with `context="ztp"`; payload includes `k`, `attempt`. Budgets are measured via the envelope (`draws` vs `blocks`).
* `schemas.layer1.yaml#/rng/events/ztp_rejection` — **non-consuming** zero-draw marker (`k=0`, `attempt`).
* `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted` — **non-consuming** cap-hit marker (`attempts=…`).
* `schemas.layer1.yaml#/rng/events/ztp_final` — **non-consuming** finaliser fixing `{K_target, lambda_extra, attempts, regime, exhausted?}` for the merchant (mirrors S2’s non-consuming finaliser pattern).
* `schemas.layer1.yaml#/rng/core/rng_trace_log` — **trace stream** with cumulative totals per `(module, substream_label)`; append **exactly one** row after each S4 event (saturating).

### What S4 reads / gates it respects.

* **S1 hurdle events** (presence gate for multi-site RNG): partitioned by `{seed, parameter_hash, run_id}`. S4 emits **no** events for `is_multi = false`.
* **S2 `nb_final`** (exactly one, **non-consuming**): fixes **`N`**; S4 **must not** re-sample or alter **N**.
* **S3 eligibility & admissible set size.** S4 requires `is_eligible = true`. Let **`A := size(S3.candidate_set \ {home})`**; S4 uses **A** only for the **A=0** short-circuit (no sampling). S4 does **not** use S3 inter-country order here.

### Authority boundaries (reaffirmed).

* Inter-country **order authority** remains **only** in **S3 `candidate_set.candidate_rank`** (home=0; contiguous). S4 **never** encodes cross-country order; it only logs the ZTP outcome.

### Dictionary vs Schema roles.

* **JSON-Schema** defines **row shape/keys** and payload/envelope fields.
* The **Data Dictionary** defines **dataset IDs**, **partitions** (RNG logs: `{seed, parameter_hash, run_id}`), and **writer sort keys**; path resolution and lifecycle live there.

### File order is non-authoritative.
Pairing and replay are determined **only by counters** in the RNG envelopes (hi/lo counters and deltas), not by physical file order or timestamps.

---

## S4.2A) Label / stream registry (frozen identifiers)

> These literals fix **module / substream / context** so replay and budgeting are stable across releases. Changing any is a **breaking change**.

| Stream                          | **module**  | **substream_label** | **context** |
|---------------------------------|-------------|---------------------|-------------|
| `rng_event_poisson_component`   | `1A.s4.ztp` | `poisson_component` | `"ztp"`     |
| `rng_event_ztp_rejection`       | `1A.s4.ztp` | `poisson_component` | `"ztp"`     |
| `rng_event_ztp_retry_exhausted` | `1A.s4.ztp` | `poisson_component` | `"ztp"`     |
| `rng_event_ztp_final`           | `1A.s4.ztp` | `poisson_component` | `"ztp"`     |

**Note.** All S4 events share `substream_label="poisson_component"` to aggregate budgets/trace under one domain; event type is distinguished by the table/anchor and `context:"ztp"`.

**Budgeting, envelopes & trace (MUST).**

* `poisson_component(context="ztp")` is **consuming**; envelopes must satisfy **`blocks == after − before`** and **`draws > 0`**.
* `ztp_rejection`, `ztp_retry_exhausted`, and `ztp_final` are **non-consuming**: **`before == after`**, **`blocks = 0`**, **`draws = "0"`**.
* **After each S4 event append, the producer MUST append exactly one cumulative `rng_trace_log` row** (saturating totals) for this `(module, substream_label)`.

**Dictionary partitions (read/write discipline).** All S4 streams are **logs** partitioned by **`{seed, parameter_hash, run_id}`**. When reading S1/S2 or writing S4, **path keys must equal embedded envelope fields** for those partitions **byte-for-byte**.

**Reminder (non-authority of file order).** Do not rely on writer order; validators and replayers must use **envelope counters** to sequence and pair events.

---

## S4.2B) Bill of Materials (BOM)

> Single place that enumerates every **governed artefact**, **value view**, and **authority** S4 depends on; what each item is for, whether it **participates in `parameter_hash`**, and how it is scoped. **Values, not paths.** Physical resolution always comes from the **Data Dictionary**.

### 2B.1 Governed artefacts (participate in `parameter_hash`) — **N**

| Name                      | Role in S4                                    | Kind                               | Scope | Fields / Contents (relevant to S4)                                                                       | Owner    | Versioning / Digest  | Participates in `parameter_hash` | Default / Notes                     |
|---------------------------|-----------------------------------------------|------------------------------------|-------|----------------------------------------------------------------------------------------------------------|----------|----------------------|----------------------------------|-------------------------------------|
| `crossborder_hyperparams` | Parameterises ZTP link & exhaustion behaviour | Artefact (governed values)         | value | `θ = {θ₀, θ₁, θ₂, …}`; `MAX_ZTP_ZERO_ATTEMPTS`; `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}` | Governed | semver + byte digest | **Yes**                          | Cap default **64** unless specified |
| `crossborder_features`    | Optional merchant feature(s) for η            | Artefact / View (parameter-scoped) | value | `X_m ∈ [0,1]` (and any documented transforms)                                                            | Governed | semver + byte digest | **Yes**                          | If `X_m` missing, **use 0.0**       |

### 2B.2 Authorities (schema & dictionary) — **N**

| Name                                                                                                                                                                                                                         | Role                                                                             | Kind                    | Scope     | Source of truth       | Participates in `parameter_hash` | Notes                                                            |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|-------------------------|-----------|-----------------------|----------------------------------|------------------------------------------------------------------|
| RNG event schemas (`schemas.layer1.yaml#/rng/events/poisson_component`, `schemas.layer1.yaml#/rng/events/ztp_rejection`, `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted`, `schemas.layer1.yaml#/rng/events/ztp_final`) | Define row/envelope shapes for all S4 logs                                       | **JSON-Schema anchors** | authority | `schemas.layer1.yaml` | No                               | Serialization authority only (row shape/keys)                    |
| Data Dictionary entries (S4 logs)                                                                                                                                                                                            | Define dataset IDs, **partitions** `{seed, parameter_hash, run_id}`, writer sort | Dictionary              | authority | Data Dictionary       | No                               | Paths, partitions, writer sort; **file order non-authoritative** |

### 2B.3 Upstream runtime surfaces S4 must read (gates & facts) — **N**

| Name                               | Role in S4                             | Kind                     | Partitions / Scope               | Source of truth | Notes                                                                                         |
|------------------------------------|----------------------------------------|--------------------------|----------------------------------|-----------------|-----------------------------------------------------------------------------------------------|
| S1 hurdle events                   | **Gate**: `is_multi = true` ⇒ in scope | RNG log                  | `{seed, parameter_hash, run_id}` | S1 producer     | Enforce path↔embed equality on read                                                           |
| S2 `nb_final`                      | **Fixes** `N ≥ 2` (non-consuming)      | RNG log                  | `{seed, parameter_hash, run_id}` | S2 producer     | Exactly one non-consuming finaliser per merchant                                              |
| S3 `crossborder_eligibility_flags` | **Gate**: `is_eligible = true`         | Parameter-scoped dataset | `parameter_hash`                 | S3 producer     | Deterministic; no RNG                                                                         |
| S3 `candidate_set`                 | Defines admissible universe size **A** | Parameter-scoped dataset | `parameter_hash`                 | S3 producer     | **A := size(S3.candidate_set \ {home})** (foreigns only). S4 uses **A** only for the `A=0` check |

### 2B.4 Hard literals & spec constants (breaking if changed) — **N**

| Literal / Constant                                   | Role                      | Kind          | Participates in `parameter_hash` | Notes                                                           |
|------------------------------------------------------|---------------------------|---------------|----------------------------------|-----------------------------------------------------------------|
| `module = "1A.s4.ztp"`                               | Envelope identity         | Spec literal  | No                               | Frozen identifier for replay/tooling                            |
| `substream_label = "poisson_component"`              | Envelope identity         | Spec literal  | No                               | Family reuse; disambiguated by `context="ztp"`                  |
| `context = "ztp"`                                    | Envelope identity         | Spec literal  | No                               | Tags S4 attempts/markers/final                                  |
| Poisson regime threshold **λ★ = 10**                 | Selects Inversion vs PTRS | Spec constant | No                               | Regime constants/threshold are spec-fixed (breaking if changed) |
| Numeric profile (binary64, RNE, FMA-off, no FTZ/DAZ) | Deterministic math        | Spec constant | No                               | Inherited from S0; breaking if changed                          |
| Open-interval mapping `u ∈ (0,1)`                    | RNG mapping               | Spec constant | No                               | Inherited from S0                                               |

### 2B.5 Trace & observability (values, not paths) — **N**

| Name                  | Role                                                                  | Kind             | Scope                            | Participates in `parameter_hash` | Notes                                                                                                                          |
|-----------------------|-----------------------------------------------------------------------|------------------|----------------------------------|----------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| `rng_trace_log`       | **Cumulative** budget/coverage totals per `(module, substream_label)` | RNG trace stream | `{seed, parameter_hash, run_id}` | No                               | **MUST append exactly one row after every S4 event append** (saturating)                                                       |
| Run counters (`s4.*`) | Ops/telemetry                                                         | Values           | per-run                          | No                               | e.g., `s4.merchants_in_scope`, `s4.accepted`, `s4.rejections`, `s4.retry_exhausted`, `s4.policy.*`, `s4.ms.*`, `s4.trace.rows` |

**Definition.** "Saturating totals" = cumulative counters that never decrease per `(module, substream_label)`; validators reconcile these against event budgets.

**BOM discipline (MUST).**

1. Items listed as **governed artefacts** **must** be passed to S4 as **values** and **participate in `parameter_hash`** (reproducibility).
2. **Authorities** (schemas/dictionary) define shapes and partitions/sort; **do not** put physical paths in S4.
3. **Upstream surfaces** are read-only; S4 enforces path↔embed equality on read.
4. **Spec literals/constants** are frozen; changing them is **breaking** and requires a spec revision.

---

## S4.3) Host inputs (values, not paths)

**What these are.** Run-constant **values** S4 receives from the orchestrator to bind lineage, parameterisation, and policy. They are **not** filesystem paths; all physical locations are resolved via the **Data Dictionary**.

### 3.1 Lineage surfaces (read-only values)

* `seed : u64`
* `parameter_hash : hex64`
* `run_id : str`
* `manifest_fingerprint : hex64`

**MUST.** S4 **must not** mutate these; when S4 writes logs, any lineage fields required by the stream schema **must** byte-match the path tokens.

### 3.2 Hyper-parameters & features (governed values)

* **ZTP link parameters** `θ = (θ₀, θ₁, θ₂, …)` — real-valued; **governed**.
  **MUST.** The bytes of `θ` **participate in `parameter_hash`**.
  **Informative.** Governance MAY prefer a sub-linear size effect; this is **not** a protocol constraint.
* **Merchant feature** `X_m ∈ [0,1]` (e.g., "openness") — governed mapping & provenance (document monotone transform, cohort, scaling).
  **Default.** If `X_m` is missing, **MUST use `X_m := 0.0`**. A different default MAY be supplied by governance and **MUST** participate in `parameter_hash`.
  **Precedence.** If governance provides `X_default`, it **overrides** 0.0; otherwise **use 0.0**.
* **Exhaustion cap** `MAX_ZTP_ZERO_ATTEMPTS ∈ ℕ⁺` — **governed** (default **64**); **participates** in `parameter_hash`.
* **Exhaustion policy** `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}` — **governed**; **participates** in `parameter_hash`.

### 3.3 Prohibitions (MUST NOT)

* No literal storage paths in S4 text or implementations.
* No dynamic/environment-dependent sources for `θ`, the `X` transform/default, the cap, or the policy; they **must** be governed values bound into the run’s `parameter_hash`.

---

## S4.4) Required upstream datasets & gates

### 4.1 Gates S4 must respect (branch purity)

* **S1 hurdle (presence gate).** S4 runs for a merchant **iff** `is_multi = true`. Singles produce **no** S4 events.
* **S3 eligibility.** Merchant must be **cross-border eligible**; if ineligible, S4 **must** emit nothing.

### 4.2 Authoritative fact S4 must read (never alter)

* **S2 `nb_final`.** The accepted **`N_m ≥ 2`** (exactly one **non-consuming** finaliser per merchant). S4 **must not** re-sample or alter `N_m`.

### 4.3 Admissible-set size (context only)

* Define **`A_m := size(S3.candidate_set \ {home})`** (foreign countries only).
  **Use in S4.** Only for the **A=0** short-circuit; S4 does **not** use S3’s order here.

### 4.4 Partitions when reading

* S1/S2 logs are read under **`{seed, parameter_hash, run_id}`**; **path↔embed equality** must hold for these keys (byte-for-byte).
* S3 tables are read under **`parameter_hash={…}`** (parameter-scoped).
* **File order is non-authoritative;** pairing/replay **must** use **envelope counters** only.

### 4.5 Zero-row discipline

* Dataset **presence** implies ≥1 row for the run’s partition. **Zero-row artefacts are forbidden**; treat as producer error upstream.

---

## S4.5) Symbols & domains

### 5.1 Upstream facts & context

* `N_m ∈ {2,3,…}` — accepted multi-site total from S2 (**authoritative**).
* `A_m ∈ {0,1,2,…}` — size of S3’s admissible foreign set (foreigns only).

### 5.2 Link and intensity

$$
\eta_m = \theta_0 + \theta_1 \log N_m + \theta_2 X_m + \cdots
$$

Compute in **binary64** with **fixed operation order**.

$$
\lambda_{\text{extra},m} = \exp(\eta_m) > 0
$$

**MUST.** Abort the merchant in S4 (`NUMERIC_INVALID`) if $\lambda$ is non-finite or ≤ 0.
**Default for features.** If `X_m` absent, **use `X_m := 0.0`** (deterministic).

### 5.3 Draw outcomes (targets vs realisation)

* `K_target,m ∈ {0,1,2,…}` — result recorded by S4:
  **ZTP yields `K≥1`;** `K_target=0` appears only from **A=0 short-circuit** or policy **"downgrade_domestic"** (never from ZTP itself).
* `K_realized,m = min(K_target, A_m)` — applied later by **S6** (top-K selection).

### 5.4 Attempting & regimes

* `attempt ∈ {1,2,…}` — **1-based** index of Poisson attempts for the merchant.
* `regime ∈ {"inversion","ptrs"}` — closed enum indicating the Poisson sampler branch chosen by the fixed λ-threshold.

### 5.5 PRNG & envelopes

* Uniforms `u ∈ (0,1)` (strict-open) per S0 law.
* **Envelope identities:**

  * **Consuming attempts:** `draws` = actual uniforms consumed; `blocks` = `after − before`.
  * **Markers/final:** `before == after`, `blocks = 0`, `draws = "0"`.
* **Trace duty.** The **trace-after-every-event** obligation from §2A applies: after each S4 event append, append exactly one cumulative `rng_trace_log` row (saturating totals) for the S4 module/substream.

### 5.6 Caps & policies

* `MAX_ZTP_ZERO_ATTEMPTS ∈ ℕ⁺` — governed; default **64**.
* `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}` — governed.

### 5.7 Determinism requirement (MUST)

* For fixed inputs and lineage, the Poisson attempt sequence and resolved `K_target` are **bit-replayable** under the keyed substream and frozen literals; **counters provide the total order** (timestamps are observational only).

---

## S4.6) Outputs (streams) & partitions

### What S4 writes.
S4 is a **logs-only** producer. It emits **RNG event rows** (serialization per JSON-Schema). **No 1A egress tables.** 
Every S4 stream is partitioned by **`{ seed, parameter_hash, run_id }`**. Every S4 **event** row carries a full **RNG envelope**; trace rows carry only `ts_utc, module, substream_label` and cumulative counters per **§14.1**.

### Streams (authoritative event anchors).

1. **`poisson_component`** (with `context:"ztp"`) — **consuming** attempt rows.
   **Payload (minimum):** `{ merchant_id, attempt:int≥1, k:int≥0, lambda_extra:float64, regime:"inversion"|"ptrs" }`
   **Domain:** `merchant_id` is **int64** per ingress `merchant_ids` (see `schemas.ingress.layer1.yaml#/merchant_ids`).
   **Envelope (minimum):** `{ ts_utc, module, substream_label, context, before, after, blocks, draws }`.
2. **`ztp_rejection`** — **non-consuming** marker for a **zero** draw.
   **Payload:** `{ merchant_id, attempt, k:0, lambda_extra }` + non-consuming envelope.
3. **`ztp_retry_exhausted`** — **non-consuming** marker when the zero-draw **cap** is hit **and policy="abort"**.
   **Payload:** `{ merchant_id, attempts:int, lambda_extra, aborted:true }` + non-consuming envelope.
4. **`ztp_final`** — **non-consuming** **finaliser** that **fixes** the outcome for the merchant.
   **Payload:** `{ merchant_id, K_target:int, lambda_extra, attempts:int, regime, exhausted?:bool [ , reason:"no_admissible"]? }` + non-consuming envelope.

### Partitioning & path↔embed equality (MUST).

* All four streams are written under `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`.
* The envelope’s `{ seed, parameter_hash, run_id }` **must equal** the path tokens **byte-for-byte**. A mismatch is a structural failure.

### Row ordering (writer-sort) (MUST).

* `poisson_component`, `ztp_rejection`: sort by **`(merchant_id, attempt)`** (stable).
* `ztp_retry_exhausted`: **`(merchant_id, attempts)`** (single row per merchant if present).
* `ztp_final`: **`(merchant_id)`** (exactly one per **resolved** merchant; absent only under hard abort).

### Cardinality & presence rules (MUST).

* **Exactly one** `ztp_final` per **resolved** merchant.
* Acceptance ⇒ **≥1** `poisson_component(context:"ztp")` exists; the **last** such row has `k≥1`.
* Cap path ⇒ `ztp_retry_exhausted` exists; if policy is `"downgrade_domestic"`, a `ztp_final{K_target=0, exhausted:true}` **must** exist; if policy is `"abort"`, **no** `ztp_final` is written.

### Zero-row discipline & idempotence (MUST).

* **Zero-row files are forbidden.** If no rows are produced for a slice, write nothing.
* Re-runs with identical inputs produce byte-identical content; if the partition already exists and is complete, the writer **must** no-op ("skip-if-final").

### Non-authority of file order (MUST).
**File order is non-authoritative;** pairing/replay **MUST** use **envelope counters** (hi/lo and deltas) only.

### Trace duty (pointer).
After each S4 event append, append exactly **one** cumulative `rng_trace_log` row—see **§7 Trace duty**.

---

## S4.7) Determinism & RNG protocol

**Substream keying & identifiers (MUST).**

* Use the **frozen literals** from §2A for `module`, `substream_label`, `context:"ztp"`.
* Each merchant’s attempt loop uses a **merchant-keyed** substream; **attempt** is **1-based** and strictly increasing.

**Open-interval uniforms & budgets (MUST).**

* Map counters to uniforms on the **open interval** `u∈(0,1)`.
* **Budget identities:**

  * `poisson_component(context:"ztp")` rows are **consuming**: `blocks == after − before`, and `draws > 0`.
  * `ztp_rejection`, `ztp_retry_exhausted`, `ztp_final` are **non-consuming**: `before == after`, `blocks == 0`, `draws == "0"`.

**Poisson regimes (fixed & measurable) (MUST).**

* **Inversion** for `λ < 10` — consumes exactly `K + 1` uniforms for `K`.
* **PTRS** for `λ ≥ 10` — consumes a **variable** count per attempt (≥2). Threshold/constants are spec-fixed.
* **Budgets are measured, not inferred**: validators rely on the envelope.

**Replay & ordering (MUST).**

* **Monotone, non-overlapping** counters per merchant/substream provide a total order; **timestamps are observational only**.
* Replaying attempts must reconstruct the same sequence and acceptance (bit-replay under the fixed literals).

**Concurrency discipline (MUST).**

* Parallelize **across** merchants only; a single merchant’s attempt loop is **serial** with fixed iteration order.
* Any merge/sink stages must be **deterministic and stable** with respect to the writer-sort keys in §6.

**Trace duty (MUST).**

* **After each S4 event append, append exactly one cumulative `rng_trace_log` record** (saturating totals) for **`(module, substream_label)`**.
* **Responsibility:** the writer that commits the event row **MUST** immediately append the single cumulative `rng_trace_log` row; higher-level sinks **MUST NOT** emit additional trace rows.

---

## S4.8) Parameterisation & target distribution

### Link & intensity (MUST).

* Compute

  $$
  \eta_m = \theta_0 + \theta_1 \log N_m + \theta_2 X_m + \cdots
  $$

  in **binary64** with a **fixed operation order**.
* Set $\lambda_{\text{extra},m} = \exp(\eta_m)$. If $\lambda$ is **NaN/Inf/≤0**, fail the merchant in S4 with `NUMERIC_INVALID`.

**Informative.** Governance MAY prefer a sub-linear size effect; this is **not** a protocol constraint.

### Target distribution (ZTP) (MUST).

* Let $Y \sim \text{Poisson}(\lambda_{\text{extra}})$. Define the **ZTP target**

  $$
  K_{\text{target}} = Y \,\big|\, (Y \ge 1).
  $$

  Acceptance probability is $1 - e^{-\lambda_{\text{extra}}}$ (for ops observability; not a decision gate).

### Realisation method (MUST).

* Realise ZTP by **sampling Poisson** and **rejecting zeros** until acceptance or the governed **zero-draw cap** is hit.
* On acceptance at attempt `a`: write the consuming `poisson_component` for that attempt and then write a **non-consuming `ztp_final`** echoing `{K_target, lambda_extra, attempts=a, regime, exhausted:false}`.
* On cap: follow the governed **exhaustion policy**:
  * `"abort"` ⇒ write `ztp_retry_exhausted{attempts, aborted:true}` and **no** `ztp_final` (merchant leaves S4 with `ZTP_EXHAUSTED_ABORT`).
  * `"downgrade_domestic"` ⇒ **do not** write `ztp_retry_exhausted`; write `ztp_final{K_target=0, exhausted:true}` (domestic-only downstream).

### Universe-aware short-circuit (MUST).

* If the **admissible foreign set is empty** (`A=0` from S3), **do not sample**; immediately write `ztp_final{K_target=0[, reason:"no_admissible"]?}` (non-consuming).

### Separation of concerns (MUST).

* S4 **fixes** the **target** count **`K_target`** only.
* In S6, the realised selection size is

  $$
  K_{\text{realized}}=\min\big(K_{\text{target}},\,A\big),
  $$

  and S6 may log a shortfall marker in its own state. S4 never encodes inter-country order.

---

## S4.9) Sampling algorithm (attempt loop & cap)

### 9.0 Overview (what this section fixes)

For each merchant **m** on the multi-site, cross-border path, S4 deterministically computes the intensity $\lambda_{\text{extra},m}$ and then realises a **Zero-Truncated Poisson** by repeatedly sampling $Y\sim \text{Poisson}(\lambda)$ and **rejecting zeros** until it accepts $K_{\text{target}}\ge 1$ or hits a governed **zero-draw cap**. S4 **emits logs only**: consuming **attempt** rows, **non-consuming** rejection/cap markers, and a **non-consuming finaliser** that fixes **`K_target`** (or records a governed `K_target=0` outcome). S4 never chooses which countries—that is later.

---

### 9.1 Preconditions (merchant enters S4) — **MUST**

* **Branch purity:** S1 `is_multi = true`. If `false` ⇒ **emit nothing** in S4 for m.
* **Eligibility:** S3 `is_eligible = true`. If `false` ⇒ **emit nothing** in S4 for m.
* **Total outlets:** S2 `nb_final` exists and fixes **`N_m ≥ 2`** (read-only).
* **Admissible set size:** obtain **`A_m := size(S3.candidate_set \ {home})`** (foreigns only).

---

### 9.2 Universe-aware short-circuit — **MUST**

If **`A_m = 0`**, S4 **MUST NOT** sample. It **MUST** immediately write a **non-consuming**
`ztp_final{ K_target=0, lambda_extra: computed λ (see 9.3), attempts:0, regime: "inversion"|"ptrs" (from λ), exhausted:false [ , reason:"no_admissible"]? }`
and **skip** S6 (domestic-only downstream).

*Note:* Computing λ is still required for observability/trace uniformity; the optional `reason` field is written **only if present** in the schema.
The `regime` is derived once from λ for observability/validator uniformity; it **does not imply** that a Poisson attempt occurred.

---

### 9.3 Deterministic parameterisation — **MUST**

* **Link:** $\eta_m = \theta_0 + \theta_1 \log N_m + \theta_2 X_m + \cdots$ evaluated in **binary64**, fixed operation order (no FMA/FTZ/DAZ).
  **Informative.** Governance MAY prefer a sub-linear size effect; this is **not** a protocol constraint.
* **Intensity:** $\lambda_{\text{extra},m}=\exp(\eta_m)$.
* **Guard:** If $\lambda$ is **NaN/Inf/≤0**, fail merchant in S4 with `NUMERIC_INVALID` (no attempts written).
* **Regime selection (fixed threshold):** if $\lambda < 10$ ⇒ **regime = "inversion"**; else **"ptrs"**. The chosen **regime is constant per merchant** (no mid-loop switching).

---

### 9.4 Substream & envelope set-up — **MUST**

* Use the **frozen identifiers** (module / substream / context) from §2A for all S4 events.
* Start a merchant-keyed **attempt counter** `a := 1` (attempts are **1-based**).
* Each event’s envelope **must** carry `{ts_utc, module, substream_label, context, before, after, blocks, draws}`.
* **Budget law:** consuming attempts satisfy `blocks == after − before` and `draws > 0`; markers/final are **non-consuming** with `before == after`, `blocks == 0`, `draws = "0"`.

---

### 9.5 Attempt loop (realising ZTP) — **MUST**

Repeat until **acceptance** or **cap**:

1. **Draw attempt `a`.** Sample $K_a \sim \text{Poisson}(\lambda)$ using the merchant’s **fixed regime**.
   **Emit** a **consuming** `poisson_component{ merchant_id, attempt:a, k:K_a, lambda_extra, regime }`.

2. **Zero?**

   * If **`K_a == 0`**: **emit** a **non-consuming** `ztp_rejection{ merchant_id, attempt:a, k:0, lambda_extra }`.
     **Cap check (now):**
     - If **`a == MAX_ZTP_ZERO_ATTEMPTS`** ⇒ **emit** a **non-consuming** `ztp_retry_exhausted{ merchant_id, attempts:a, lambda_extra }` and apply policy (see below).
     - Else **set `a := a+1`** and continue.
   * If **`K_a ≥ 1`** (**ACCEPT**): set `K_target := K_a`; **emit** a **non-consuming**
     `ztp_final{ merchant_id, K_target, lambda_extra, attempts:a, regime, exhausted:false }` and **STOP**.

3. **Policy on cap (from the prior branch):**

   * **`"abort"` ⇒ STOP** with **no `ztp_final`**; outcome is `ZTP_EXHAUSTED_ABORT`.
   * **`"downgrade_domestic"` ⇒ emit** a **non-consuming**
     `ztp_final{ merchant_id, K_target=0, lambda_extra, attempts:a, regime, exhausted:true }` and **STOP** (domestic-only downstream).

*Trace note:* After **each** event append in steps (1)–(3), **append exactly one** cumulative `rng_trace_log` row (saturating totals) for `(module, substream_label)` (see §7).

**Norms inside the loop**

* **No regime switching** mid-merchant.
* **No silent retries:** each Poisson draw writes exactly one **consuming** attempt; each zero writes exactly one **non-consuming** rejection marker.
* **Attempt indexing** is **1-based, strictly increasing**, and **monotone** within m.

---

### 9.6 Ordering & replay — **MUST**

* Within a merchant’s substream, envelope counters are **monotone, non-overlapping**; validators reconstruct attempt order **from counters** (not timestamps or file order).
* The accepting attempt (or capped path) is the **last** event sequence for that merchant’s substream; the presence/absence of `ztp_final` reflects the policy outcome unambiguously.
* After **each** S4 append, write one **cumulative** `rng_trace_log` row (saturating totals) for `(module, substream_label)`.

---

### 9.7 Postconditions (what S4 fixes) — **MUST**

For a resolved merchant:

* Either **`K_target ≥ 1`** via acceptance, with exactly one `ztp_final{…, exhausted:false}`, or
* **`K_target = 0`** via **A=0** short-circuit or **"downgrade_domestic"** policy, with exactly one `ztp_final{…, exhausted:true [ , reason:"no_admissible"]? }`, or
* **Abort** under `"abort"` policy at cap: **no `ztp_final`**; exactly one `ztp_retry_exhausted`.
* In all acceptance/short-circuit/downgrade cases, **exactly one** `ztp_final` exists for the merchant.
* No S4 Parquet products exist; only the four event streams.

---

### 9.8 Prohibitions & edge discipline — **MUST NOT**

* **MUST NOT** write any S4 events for singles or ineligible merchants.
* **MUST NOT** compute or encode inter-country order in S4.
* **MUST NOT** switch the Poisson regime mid-loop or reuse counters across merchants.
* **MUST NOT** emit zero-row files for any S4 stream partitions.

---

### 9.9 Determinism under concurrency — **MUST**

* A merchant’s attempt loop executes **serially** (fixed iteration order).
* Concurrency is **across** merchants only; any writer/merge step must be **stable** w\.r.t. the sort keys in §6 to ensure **byte-identical** outputs for identical inputs.

---

### 9.10 Observability hooks (values-only) — **SHOULD**

For each `(seed, parameter_hash, run_id)`:

* per-merchant: `{attempts, zero_rejections, accepted_K (or 0), regime, exhausted?}`
* per-run: acceptance-rate estimate $1-e^{-\bar{\lambda}}$ vs observed, cap rate, regime split, elapsed-ms quantiles.

---

## S4.9A) Universe awareness & short-circuits

### What "A" is (precise).
Let **`A := size(S3.candidate_set \ {home})`** be the count of *foreign* ISO2s in the merchant’s admissible universe (home excluded). S4 **does not** use `candidate_rank` here—only the set size.

### How S4 obtains A (read-side discipline).

* Read **`s3_candidate_set`** under **`parameter_hash={…}`** (parameter-scoped).
* **MUST** enforce path↔embed equality for required lineage fields on read.
* **MUST NOT** infer A from file order or any non-governed source.
* Missing/ill-formed admissible-set data is an **upstream S3 error**, not an S4 defect.

### Short-circuit when `A = 0` (no admissible foreigns).

* **MUST NOT** run the Poisson loop.
* **MUST** still compute `lambda_extra` (binary64, fixed order) for observability and regime derivation.
* **MUST** immediately write a **non-consuming**
  `ztp_final{ K_target=0, lambda_extra, attempts:0, regime: "inversion"|"ptrs", exhausted:false [ , reason:"no_admissible"]? }`.
  *(The `reason` field is written only if present in the finaliser schema.)*
* **MUST** skip S6 (no top-K) and proceed along the domestic-only path downstream (S7 will allocate `{home: N}`).

### When `A > 0` (normal case).

* Run the Poisson loop per **§9.5**.
* Acceptance yields **`K_target ≥ 1`**.
* **MUST NOT** cap `K_target` to `A` in S4. S4 fixes **`K_target`**; **S6 MUST** realise `K_realized = min(K_target, A)` (see **§9B**).

### Invariant & logging.

* Exactly one `ztp_final` per resolved merchant (absent only on hard abort).
* **Informative:** ops counters **SHOULD** record short-circuits (count of `K_target=0` due to `A=0`).

### Prohibitions.

* **MUST NOT** emit any S4 events for `is_multi=false` or `is_eligible=false`.
* **MUST NOT** encode inter-country order in S4.

---

## S4.9B) S4 → **S6** handshake

### Purpose.
Fix what S6 must consume from S4 and how to realise selection size for all outcomes.

### What S6 reads from S4 (authoritative):
fields from **`ztp_final`** for the merchant:

* `K_target : int` — the **target** foreign count S4 fixed (≥1 on acceptance; 0 on short-circuit/downgrade).
* `lambda_extra : float64` — intensity used (audit/diagnostics; not a decision gate in S6).
* `attempts : int≥0` — number of Poisson attempts written by S4 (0 iff short-circuit).
* `regime : "inversion"|"ptrs"` — Poisson regime S4 used (closed enum).
* `exhausted? : bool` — present and `true` only when cap hit and policy was **"downgrade_domestic"**.

### What S6 must combine with its own inputs:

* **`A`** (admissible foreign set size) and the **ordered/weighted foreign candidate list** S6 owns.

### Realisation rule (binding).

* **MUST** compute **`K_realized = min(K_target, A)`**.
* If `K_target = 0` (short-circuit or downgrade): **MUST** skip top-K entirely and continue with the domestic-only path.
* If `K_target > A`: **MUST** select **all `A`** foreigns (top-K shortfall). S6 **MAY** emit its own **non-consuming** marker (e.g., `topk_shortfall{K_target, A}`) in **its** state; S4 does not emit this marker.

### Outcomes matrix (exhaustive).

| S4 outcome                                                   | `A`                | S6 must…                                                                                                           |
|--------------------------------------------------------------|--------------------|--------------------------------------------------------------------------------------------------------------------|
| `ztp_final{K_target ≥ 1, exhausted:false}`                   | `A ≥ K_target`     | Select exactly `K_target` foreigns via its governed top-K mechanism; proceed.                                      |
| `ztp_final{K_target ≥ 1, exhausted:false}`                   | `0 < A < K_target` | Select **all `A`** (shortfall); **MUST** treat `K_realized = A`.                                                   |
| `ztp_final{K_target=0 [ , reason:"no_admissible"]? }`        | `A = 0`            | Skip top-K; domestic-only path.                                                                                    |
| `ztp_final{K_target=0, exhausted:true}` (policy = downgrade) | any `A`            | Skip top-K; domestic-only path.                                                                                    |
| Cap + policy = `"abort"` (no `ztp_final`)                    | any `A`            | **MUST NOT** run S6 for this merchant; pipeline treats merchant as **aborted** for S4+ (downstream states ignore). |

### Lineage continuity (MUST).

* S6 **must** carry forward the same `{seed, parameter_hash, run_id}` lineage triplet for any logs it writes.
* S6 **must not** reinterpret `lambda_extra` or `regime`.

### Authority boundaries (reaffirmed).

* S4 **fixes counts only at the target level** (`K_target`).
* S6 **owns**: which foreign ISO2s are chosen and in what order/weight for later stages.
* S3 `candidate_rank` remains the sole cross-country **order** authority; S4 never encodes order.

### Prohibitions.

* **MUST NOT** ignore `ztp_final` (if present).
* **MUST NOT** realise `K` greater than `A`.
* **MUST NOT** treat Poisson attempts or rejections as authoritative selection signals (they are evidence only; `ztp_final` is the single acceptance record).

---

## S4.10) Draw accounting & envelopes

### 10.1 Streams S4 writes (reminder).
Logs only, all partitioned by `{seed, parameter_hash, run_id}` with a full RNG **envelope** on every row:

* `poisson_component` (with `context:"ztp"`): **consuming** attempt rows.
* `ztp_rejection`: **non-consuming** zero marker.
* `ztp_retry_exhausted`: **non-consuming** cap-hit marker.
* `ztp_final`: **non-consuming** finaliser that **fixes** `{K_target, …}`.

### 10.2 Envelope fields (MUST).
Every S4 event row **must** carry:

* `ts_utc` (microsecond; observational only—never used for ordering).
* `module`, `substream_label`, `context` — **must match** the frozen identifiers in §2A.
* `before` (u128), `after` (u128), `blocks` (u64), `draws` (decimal-u128 as **string**).
* **MUST.** `draws` uses the S0 **canonical decimal-u128** format (no sign, no exponent, no leading zeros except `"0"`).
* Path↔embed equality: embedded `{seed, parameter_hash, run_id}` **must equal** path tokens **byte-for-byte**.

### 10.3 Budget identities (MUST).

* **Consuming attempts** (`poisson_component(context:"ztp")`):
  `blocks == after − before` (**strictly positive**), and `draws` parses as decimal-u128 and is **> 0** (actual uniforms consumed).
* **Non-consuming markers/final** (`ztp_rejection`, `ztp_retry_exhausted`, `ztp_final`):
  `before == after`, `blocks == 0`, `draws == "0"`.

### 10.4 Per-attempt write discipline (MUST).

* Exactly **one** consuming `poisson_component` row **per attempt index** for the merchant (attempts are **1-based** and contiguous).
* If that attempt’s `k == 0`, write exactly **one** `ztp_rejection{attempt}` **after** the attempt row.
* If that attempt’s `k ≥ 1` (acceptance), **no rejection marker** for that attempt; instead write exactly **one** `ztp_final{attempts := a}` after the attempt row.
* If the **cap** is reached with all zeros:
  - if policy=`"abort"` → write exactly **one** `ztp_retry_exhausted{attempts := MAX, aborted:true}` and **no** `ztp_final`;
  - if policy=`"downgrade_domestic"` → **do not** write an exhausted marker; write `ztp_final{K_target=0, exhausted:true}` (non-consuming).

### 10.5 Monotone, non-overlapping counters (MUST).

* Within a merchant’s substream, counter spans **must** be **strictly increasing and non-overlapping** for consuming events.
* Ordering and pairing for replay/validation is by **counters only** (timestamps and file order are non-authoritative).

### 10.6 Payload typing & constancy (MUST).

* **Attempt rows** (`poisson_component`, `ztp_rejection`): `attempt:int≥1`.
* **Finaliser / cap rows** (`ztp_final`, `ztp_retry_exhausted`): `attempts:int≥0` (==0 only on A=0 short-circuit).
* Common fields (where present): `k:int≥0`, `K_target:int≥0`, `lambda_extra:float64 (finite, >0)`, `regime ∈ {"inversion","ptrs"}`.
* For a given merchant, `lambda_extra` and `regime` **must** be identical across all S4 rows for that merchant (computed once in §9.3).

### 10.7 Writer sort & uniqueness (MUST).

* Sort keys (as in §6):
  - attempts/rejections by `(merchant_id, attempt)` (stable),
  - cap marker by `(merchant_id, attempts)`,
  - finaliser by `(merchant_id)`.
* Uniqueness constraints:
  - ≤1 `poisson_component` per `(merchant_id, attempt)`,
  - ≤1 `ztp_rejection` per `(merchant_id, attempt)`,
  - ≤1 `ztp_retry_exhausted` per merchant,
  - ≤1 `ztp_final` per **resolved** merchant.

### 10.8 Trace duty (MUST).

* After **each** S4 row append, write one cumulative `rng_trace_log` record (saturating totals) keyed by `(module, substream_label)`.
  - Consuming attempt: trace counters **increase** by the event’s `blocks`/`draws`.
  - Non-consuming marker/final: trace counters **do not increase**; only the event count increments.

### 10.9 Zero-row files & idempotence (MUST).

* Zero-row files are **forbidden**; empty slices write nothing.
* Re-running with identical inputs **must** produce byte-identical content; if a complete partition already exists, **must** no-op (skip-if-final).

---

## S4.11) Invariants (state-level)

### 11.1 Branch purity & scope.

* **No S4 events** for merchants with `is_multi=false` or `is_eligible=false`.
* S4 is **logs-only**; S4 writes **no Parquet egress** and **never encodes inter-country order**.

### 11.2 Parameterisation & regime.

* For each merchant, `η` and `λ_extra` are computed **once** (binary64, fixed order); `λ_extra` must be **finite and >0**.
* The Poisson **regime** (`"inversion"` if `λ<10`, otherwise `"ptrs"`) is **fixed** for the merchant; **no regime switching** mid-loop.

### 11.3 Attempts, markers, finalisers.

* **Acceptance path:**
  - ≥1 consuming `poisson_component(context:"ztp")`, with the **last** having `k ≥ 1`.
  - Exactly **one** non-consuming `ztp_final{K_target≥1, exhausted:false}`.
  - No `ztp_retry_exhausted`.
* **Cap path:**
  - A sequence of `poisson_component` with `k=0` and matching `ztp_rejection`s.
  - Policy=`"abort"` ⇒ exactly **one** `ztp_retry_exhausted{aborted:true}` and **no** `ztp_final`.
  - Policy=`"downgrade_domestic"` ⇒ **no** exhausted marker; exactly **one** `ztp_final{K_target=0, exhausted:true}`.
* **A=0 short-circuit:**
  - Exactly **one** `ztp_final{K_target=0, attempts:0 [ , reason:"no_admissible"]? }`; **no** attempts, **no** rejections, **no** cap marker.

### 11.4 Counter & budget identities.

* For every consuming attempt row: `after > before`, `blocks == after − before`, and `draws > 0` (decimal-u128).
* For every non-consuming marker/final: `before == after`, `blocks == 0`, `draws == "0"`.
* Within a merchant’s substream, counter spans are **monotone** and **non-overlapping**.

### 11.5 Cardinality & contiguity.

* Attempt indices are **contiguous**: `1..a` for attempts; `ztp_final.attempts == a` on acceptance/cap, and `== 0` on A=0 short-circuit.
* Exactly **one** `ztp_final` per **resolved** merchant (absent only on hard abort).
* At most **one** `ztp_retry_exhausted` per merchant, and only when the cap is reached.

### 11.6 Partitions, lineage & identifiers.

* All S4 streams live under `{seed, parameter_hash, run_id}`; embedded lineage **equals** path tokens **byte-for-byte**.
* `module`, `substream_label`, `context` **must** match the frozen registry in §2A.

### 11.7 Determinism & concurrency.

* For fixed inputs and lineage, the attempt sequence, acceptance, and finaliser content are **bit-replayable** (counter-based).
* Concurrency is **across** merchants only; each merchant’s loop is **serial**. Writer merges are **stable** w\.r.t. §6 sort keys.
* Re-runs on identical inputs yield **byte-identical** outputs (idempotence).

### 11.8 Separation of concerns (downstream compatibility).

* S4 **fixes** only `K_target` (or governed `0`); **S6** realises `K_realized = min(K_target, A)` and owns which foreign ISO2s are chosen.
* S3 `candidate_rank` remains the sole cross-country **order** authority; S4 never writes order.

### 11.9 Prohibitions.

* **MUST NOT** emit any S4 rows for singles/ineligible merchants.
* **MUST NOT** compute/encode inter-country order.
* **MUST NOT** write zero-row files.
* **MUST NOT** change `λ_extra` or `regime` across attempts for a merchant.
* **MUST NOT** use timestamps or file order to reconstruct sequencing (counters only).

---

## S4.12) Failure vocabulary (stable codes)

> **Principles.**
> - Fail **deterministically**; never emit partial merchant output.
> - **Scope** every failure (Merchant vs Run).
> - Emit **values-only** context (no paths), with stable keys.
> - Prefer **merchant-scoped** failure; reserve **run-scoped** for structural/authority violations.

### 12.1 Required failure payload (all codes) — **MUST**

Each failure record **MUST** include:

```
{
  code,
  scope ∈ {"merchant","run"},
  reason : str,
  merchant_id? : int64,
  seed : u64, parameter_hash : hex64, run_id : str, manifest_fingerprint : hex64,
  attempts? : int,          // present if any attempts occurred; 0 for A=0 short-circuit; omitted otherwise
  lambda_extra? : float64,  // present if computed (§9.3) or any attempts were made
  regime? : "inversion" | "ptrs"
}
```

*`merchant_id` is present for merchant-scoped failures.*

### 12.2 Stable codes — **MUST**

| Code                    | Scope    | Condition (trigger)                                                                                      | Required producer behavior                                                  |
|-------------------------|----------|----------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `UPSTREAM_MISSING_S1`   | Merchant | No authoritative hurdle decision found for merchant (S1)                                                 | **Abort** merchant; write no S4 events; upstream coverage error.            |
| `NUMERIC_INVALID`       | Merchant | $\lambda_{\text{extra}}$ is NaN/Inf/≤0 after §9.3                                                        | **Abort** merchant; **no** attempts; **no** `ztp_final`; log failure.       |
| `BRANCH_PURITY`         | Merchant | Any S4 event for `is_multi=false` or `is_eligible=false`                                                 | **Abort** merchant; suppress further S4 events; log failure.                |
| `A_ZERO_MISSHANDLED`    | Merchant | `A=0` **and** (any attempts **or** `K_target≠0` **or** *(if schema has field)* `reason≠"no_admissible"`) | **Abort** merchant; log failure (implementation bug).                       |
| `ATTEMPT_GAPS`          | Merchant | Attempt indices not contiguous from 1..a                                                                 | **Abort** merchant; log failure.                                            |
| `FINAL_MISSING`         | Merchant | Acceptance observed (last `poisson_component.k≥1`) but **no** `ztp_final`                                | **Abort** merchant; log failure.                                            |
| `MULTIPLE_FINAL`        | Merchant | >1 `ztp_final` for merchant                                                                              | **Abort** merchant; log failure.                                            |
| `CAP_WITH_FINAL_ABORT`  | Merchant | `ztp_retry_exhausted` present and policy=`abort` **but** a `ztp_final` exists                            | **Abort** merchant; log failure.                                            |
| `ZTP_EXHAUSTED_ABORT`   | Merchant | Cap hit and policy=`abort`                                                                               | **Stop** merchant; **no** `ztp_final`; log this code (outcome; not a bug).  |
| `TRACE_MISSING`         | Merchant | Event append without a corresponding **cumulative** `rng_trace_log` update                               | **Abort** merchant; log failure; trace duty breached.                       |
| `POLICY_INVALID`        | Run      | `ztp_exhaustion_policy` **missing or** ∉ {"abort","downgrade_domestic"}                                  | **Abort run**; configuration/artefact error.                                |
| `REGIME_INVALID`        | Merchant | `regime` ∉ {"inversion","ptrs"} **or** regime switched mid-merchant                                      | **Abort** merchant; log failure.                                            |
| `RNG_ACCOUNTING`        | Merchant | Consuming row with `draws≤0` **or** `blocks≠after−before`; **or** non-consuming marker advanced counters | **Abort** merchant; log failure; counters must be monotone/non-overlapping. |
| `STREAM_ID_MISMATCH`    | Run      | `module/substream_label/context` deviate from §2A registry                                               | **Abort run**; label registry violated.                                     |
| `PARTITION_MISMATCH`    | Run      | Path tokens `{seed,parameter_hash,run_id}` ≠ embedded envelope fields                                    | **Abort run**; structural violation.                                        |
| `DICT_BYPASS_FORBIDDEN` | Run      | Producer used literal paths (bypassed dictionary)                                                        | **Abort run**; structural violation.                                        |
| `UPSTREAM_MISSING_S2`   | Merchant | S2 `nb_final` absent for merchant entering S4                                                            | **Abort** merchant; upstream coverage error.                                |
| `UPSTREAM_MISSING_A`    | Merchant | **`s3_candidate_set`** unavailable/ill-formed for the merchant (A cannot be derived)                     | **Abort** merchant; upstream S3 error.                                      |
| `ZERO_ROW_FILE`         | Run      | Any S4 stream wrote a zero-row file                                                                      | **Abort run**; zero-row files forbidden.                                    |
| `UNKNOWN_CONTEXT`       | Run      | S4 events have `context≠"ztp"`                                                                           | **Abort run**; schema/producer bug.                                         |

### 12.3 No partial writes — **MUST**

* On **merchant-scoped** failure, **MUST NOT** emit additional S4 rows for that merchant after logging the failure.
* On **run-scoped** failure, **MUST** stop writing immediately.

### 12.4 Logging keys (stable) — **MUST**

Use these values-only keys for failure lines:

```
s4.fail.code, s4.fail.scope, s4.fail.reason,
s4.fail.attempts, s4.fail.lambda_extra, s4.fail.regime,
s4.run.seed, s4.run.parameter_hash, s4.run.run_id, s4.run.manifest_fingerprint,
s4.fail.merchant_id?
```

### 12.5 Mapping to validation — **Informative**

Validator checks for `ATTEMPT_GAPS`, `FINAL_MISSING`, `RNG_ACCOUNTING`, `TRACE_MISSING` mirror these producer codes; failures should correlate 1:1.

**Informative.** S4 codes are the canonical names for this state and appear **as-is** in the global ledger; the run’s failure record also carries the S0 global `failure_class` per the validation schema.

---

## S4.13) Observability (values-only; bytes-safe)

> **Aim.** Minimal, stable metrics for S4 health/cost/behavior **without** paths/PII or duplicating validator logic. Metrics are values-only and keyed to run lineage.

### 13.1 Run lineage dimensions — **MUST**

Every metric line **MUST** include:

```
{ seed, parameter_hash, run_id, manifest_fingerprint }
```

### 13.2 Minimal counters & gauges — **MUST**

| Key                              | Type    | Definition                                                                                                                                  |
|----------------------------------|---------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `s4.merchants_in_scope`          | counter | # merchants that entered S4 (S1 multi **and** S3 eligible).                                                                                 |
| `s4.accepted`                    | counter | # merchants with `ztp_final{K_target≥1, exhausted:false}`.                                                                                  |
| `s4.short_circuit_no_admissible` | counter | # merchants resolved via **A=0** short-circuit (detect as `attempts==0 ∧ K_target==0` and, **if field exists**, `reason=="no_admissible"`). |
| `s4.downgrade_domestic`          | counter | # merchants with `ztp_final{K_target=0, exhausted:true}`.                                                                                   |
| `s4.aborted`                     | counter | # merchants with `ZTP_EXHAUSTED_ABORT`.                                                                                                     |
| `s4.rejections`                  | counter | Total zero-draw rejections written (count of `ztp_rejection`).                                                                              |
| `s4.attempts.total`              | counter | Total attempts across all merchants (count of `poisson_component`).                                                                         |
| `s4.trace.rows`                  | counter | Total S4 events appended (sum over all four streams; should equal cumulative trace row count).                                              |
| `s4.regime.inversion`            | counter | # merchants whose regime was `"inversion"`.                                                                                                 |
| `s4.regime.ptrs`                 | counter | # merchants whose regime was `"ptrs"`.                                                                                                      |

### 13.3 Distributions / histograms — **SHOULD**

| Key                       | Kind      | Definition                                                                       |
|---------------------------|-----------|----------------------------------------------------------------------------------|
| `s4.attempts.hist`        | histogram | Per-merchant attempts (accepted path → `attempts`; A=0 → 0; abort → cap value).  |
| `s4.lambda.hist`          | histogram | Bucketed $\lambda_{\text{extra}}$ (e.g., log-buckets); values are finite and >0. |
| `s4.ms.poisson_inversion` | histogram | Milliseconds spent in inversion branch (per merchant).                           |
| `s4.ms.poisson_ptrs`      | histogram | Milliseconds spent in PTRS branch (per merchant).                                |

### 13.4 Derived rates (computed by metrics layer) — **SHOULD**

* `s4.accept_rate = s4.accepted / s4.merchants_in_scope`
* `s4.cap_rate = s4.aborted / s4.merchants_in_scope`
* `s4.mean_attempts = s4.attempts.total / s4.merchants_in_scope`

### 13.5 Per-merchant summaries — **SHOULD**

Emit one values-only summary per **resolved** merchant:

```
s4.merchant.summary = {
  merchant_id,
  attempts,
  accepted_K : (K_target | 0),
  regime,
  exhausted : bool,
  reason?          // present only if the ztp_final schema has this optional field
}
```

*`accepted_K` is 0 for A=0 short-circuit or downgrade. Omit the summary for hard abort (policy=`abort`).*

### 13.6 Emission points — **MUST**

* Increment outcome counters **exactly once per merchant**: on writing `ztp_final` (accepted/downgrade/short-circuit) **or** on logging `ZTP_EXHAUSTED_ABORT`.
* Update attempt/rejection counters **immediately after** writing each corresponding row.
* Write histogram samples **once per merchant** at resolution (on final/abort).
* **Emission responsibility:** Metrics **MUST** be emitted by the same process that writes the event rows, **after** the event fsync completes.

### 13.7 Cardinality & privacy — **MUST**

* **Values-only; no paths/URIs.**
* **Bounded cardinality:** keys are run-scoped plus `merchant_id`; no high-cardinality labels beyond those.
* **No PII.** `merchant_id` is an ID; do not log names or free-text beyond stable enum `reason` values.

### 13.8 Alerting hints — **Informative**

* **Cap rate spike** (e.g., `s4.cap_rate > 0.01`) → investigate θ or `X` transform drift.
* **Mean attempts ↑** or **rejections ↑** → indicative of low $\lambda$; check cohorts with small `N` or `X`.
* **Unexpected regime split** → verify regime threshold/constants.
* Any **`NUMERIC_INVALID` > 0** → input/overflow issue; block release.

### 13.9 Output format — **MUST**

All metrics are emitted as structured values (e.g., JSON lines) with the lineage dimension and keys from this section; consumers/aggregation are outside S4’s scope.

---

## S4.14) Interfaces & dictionary (lookup table)

> **Goal.** Freeze exactly what S4 **writes** and **reads**, how each stream is **partitioned**, which **envelope** fields are required, the **writer sort keys**, and who **consumes** the output. Physical paths come from the **Data Dictionary**; S4 **must not** hard-code paths.

### 14.1 Streams S4 **writes** (logs-only)

| Stream ID                                            | Schema anchor (authoritative)                         | Partitions (path keys)         | Required envelope fields (all rows)                                      | Required payload (minimum)                                                                                                                          | Writer sort keys (stable)                                               | Consumers                                             |
|------------------------------------------------------|-------------------------------------------------------|--------------------------------|--------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------|-------------------------------------------------------|
| `rng_event_poisson_component` (with `context:"ztp"`) | `schemas.layer1.yaml#/rng/events/poisson_component`   | `seed, parameter_hash, run_id` | `ts_utc, module, substream_label, context, before, after, blocks, draws` | `{ merchant_id, attempt:int≥1, k:int≥0, lambda_extra:float64, regime:"inversion" \| "ptrs" }`                                                       | `(merchant_id, attempt)`                                                | S4 validator, observability                           |
| `rng_event_ztp_rejection`                            | `schemas.layer1.yaml#/rng/events/ztp_rejection`       | `seed, parameter_hash, run_id` | *(same envelope fields as above)*                                        | `{ merchant_id, attempt:int≥1, k:0, lambda_extra }`                                                                                                 | `(merchant_id, attempt)`                                                | S4 validator, observability                           |
| `rng_trace_log`                                      | `schemas.layer1.yaml#/rng/core/rng_trace_log`         | `seed, parameter_hash, run_id` | `ts_utc, module, substream_label`                                        | `{ module, substream_label, rng_counter_after_hi:u64,  rng_counter_after_lo:u64  }`                                                                 | `(module, substream_label, rng_counter_after_hi, rng_counter_after_lo)` | S4 validator, observability                           |
| `rng_event_ztp_retry_exhausted`                      | `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted` | `seed, parameter_hash, run_id` | *(same envelope fields as above)*                                        | `{ merchant_id, attempts:int≥1, lambda_extra, aborted:true }`                                                                                       | `(merchant_id, attempts)`                                               | S4 validator, observability (abort-only)              |
| `rng_event_ztp_final`                                | `schemas.layer1.yaml#/rng/events/ztp_final`           | `seed, parameter_hash, run_id` | *(same envelope fields as above)*                                        | `{ merchant_id, K_target:int≥0, lambda_extra:float64, attempts:int≥0, regime:"inversion" \| "ptrs", exhausted?:bool [ , reason:"no_admissible"]? }` | `(merchant_id)`                                                         | **S6** (reads `K_target,…`), validator, observability |

**MUST.**

* **Path↔embed equality:** For **event streams**, embedded `{seed, parameter_hash, run_id}` **must equal** path tokens **byte-for-byte**.  
  `rng_trace_log` **omits** these fields by design; lineage equality for trace rows is enforced via the partition path keys.
* **Label registry:** For **event streams**, `module`, `substream_label`, `context` **must** match §2A’s frozen literals.  
  `rng_trace_log` carries only `module` and `substream_label` (no `context`).
* **File order is non-authoritative:** Pairing/replay **MUST** use **envelope counters** only.
* **Trace duty:** After each event append, **append exactly one** cumulative `rng_trace_log` row (see §§7/10).
* **Failure records sink:** On abort, write values-only `failure.json` under the S0 bundle path `data/layer1/1A/validation/failures/fingerprint={manifest_fingerprint}/seed={seed}/run_id={run_id}/` using the payload keys in §12.1/§12.4. *(Not a stream.)*

**Schema versioning note.** The optional `reason:"no_admissible"` field on `ztp_final` is **present only** in schema versions that include it (per §21.1 it is absent in this version). Its mention in the table is **forward-compatible**; producers must omit it unless the bound schema version defines it.

---

### 14.2 Surfaces S4 **reads** (gates / facts)

| Surface                            | Schema anchor                                       | Partitions                     | What S4 uses (only)                                                                             | Notes                            |
|------------------------------------|-----------------------------------------------------|--------------------------------|-------------------------------------------------------------------------------------------------|----------------------------------|
| S1 hurdle events                   | `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`  | `seed, parameter_hash, run_id` | **Gate:** `is_multi==true` to enter S4                                                          | S4 writes nothing for singles    |
| S2 `nb_final`                      | `schemas.layer1.yaml#/rng/events/nb_final`          | `seed, parameter_hash, run_id` | **Fact:** authoritative `N_m≥2` (non-consuming; one per merchant)                               | Read-only; S4 must not alter `N` |
| S3 `crossborder_eligibility_flags` | `schemas.1A.yaml#/s3/crossborder_eligibility_flags` | `parameter_hash`               | **Gate:** `is_eligible==true`                                                                   | Deterministic; no RNG            |
| S3 `candidate_set`                 | `schemas.1A.yaml#/s3/candidate_set`                 | `parameter_hash`               | **Context:**  `A := size(S3.candidate_set \ {home})` (foreign count only); S4 doesn’t use order | File order non-authoritative     |

**MUST.** When reading S1/S2 logs, enforce **path↔embed** equality on `{seed, parameter_hash, run_id}`; treat violations as structural failures (run-scoped).

---

### 14.3 Ordering & idempotence requirements (writer)

* **Sort before write** per table above; merges must be **stable** w.r.t. sort keys.
* **Skip-if-final:** if a complete partition already exists with byte-identical content, **no-op**.
* **Uniqueness per merchant:** ≤1 `poisson_component` per `(merchant_id, attempt)`; ≤1 `ztp_rejection` per `(merchant_id, attempt)`; ≤1 `ztp_retry_exhausted`; ≤1 `ztp_final` if the merchant is **resolved** (absent only under hard abort).

---

## S4.15) Numeric policy & equality (S4-local application)

> **Goal.** Pin the exact math, equality, and comparison discipline S4 applies so results are reproducible and validator-provable—without tolerances or hidden heuristics.

### 15.1 Floating-point profile (binding)

* **IEEE-754 binary64**, **round-to-nearest-even**, **FMA-off**, **no FTZ/DAZ** for any computation that can affect outcomes or payloads.
* All merchant-local computations run with a **fixed operation order**; no parallel/underdetermined reductions.

**MUST.** Treat **NaN/Inf** anywhere in `η`/`λ_extra` evaluation as a hard error (`NUMERIC_INVALID`); write no attempts.

---

### 15.2 Link evaluation & regime threshold

* **Link:** $\eta = \theta_0 + \theta_1 \log N + \theta_2 X + \cdots$ evaluated in **binary64**, fixed order.
  **Informative.** Governance MAY prefer a sub-linear size effect; this is **not** a protocol constraint.
* **Intensity:** $\lambda_{\text{extra}}=\exp(\eta)$ (**finite, >0** required).
* **Regime (spec-fixed threshold):**
  * If $\lambda_{\text{extra}} < 10$ → `regime="inversion"`
  * Else (including `==10`) → `regime="ptrs"`
    Regime is **fixed per merchant** (no switching mid-loop).
  *(Primary rule.)* See **§15.6 Payload constancy within a merchant** for the one-time evaluation and constancy of `regime` and `lambda_extra`.
* **Informative.** PTRS constants are normative and pinned upstream in **S0.3.7**; **S2 §3.2** implements that profile for NB Poisson.

---

### 15.3 Uniform mapping & budget identities

* **Open-interval uniforms:** map PRNG counters to `u∈(0,1)` (strict-open; never include 0 or 1).
* **Consuming attempts** (`poisson_component`) must satisfy **both**:
  `blocks == after − before` (**>0**) and `draws` (decimal-u128 string) parses and **>0**.
* **Non-consuming markers/final** (`ztp_rejection`, `ztp_retry_exhausted`, `ztp_final`) must satisfy:
  `before == after`, `blocks == 0`, `draws == "0"`.

---

### 15.4 Equality & ordering rules

* **Exact equality** for integers, counters, regime enums, and lineage tokens (no tolerances).
* **Float comparisons:** the only float comparison that affects control flow is the **regime split** at `λ<10` vs `≥10`; apply it directly in binary64 (**no epsilons**).
* **Ordering for replay/validation:** use **counters** exclusively; timestamps are observational; **file order is non-authoritative**.

---

### 15.5 Determinism & concurrency

* **Serial per merchant:** the attempt loop is single-threaded with fixed iteration order.
* **Across merchants:** concurrency allowed; any writer/merge must be **stable** w\.r.t. §14 sort keys so identical inputs yield **byte-identical** outputs.

---

### 15.6 Payload constancy within a merchant

* `lambda_extra` and `regime` are computed **once** and **must** be identical across all S4 rows for that merchant (attempts, markers, final).
* Attempt indices are **contiguous** starting at 1; `ztp_final.attempts` equals the last attempt index (or 0 for A=0 short-circuit).

---

### 15.7 Prohibitions

* **No epsilons** or fuzzy checks in producer logic (validators may compute diagnostics, but producer decisions are exact).
* **No regime drift**, **no counter reuse**, **no zero-row files**, **no path literals**.

---

## S4.16) Complexity & parallelism

**16.1 Per-merchant asymptotics**

* **Attempt loop (Poisson):** amortised **O(1)** work per attempt; **O(1)** memory.
* **Expected attempts:** $\mathbb{E}[\text{attempts}]=1/p$, with $p=1-e^{-\lambda_{\text{extra}}}$. The governed cap `MAX_ZTP_ZERO_ATTEMPTS` bounds worst-case attempts.
* **Uniform budgets (qualitative):**

  * **Inversion** (`λ<10`): exactly **`K+1` uniforms** for a draw returning `K`.
  * **PTRS** (`λ≥10`): a small, **variable** count per attempt (≥2). Budgets are **measured from envelopes**; producers do not infer them.
* **Rows per merchant (expected):**

  * **Acceptance path:** `attempts`×`poisson_component` + (`attempts−1`)×`ztp_rejection` + 1×`ztp_final`.
  * **Cap + downgrade:** `MAX`×`poisson_component` + `MAX`×`ztp_rejection` + 1×`ztp_retry_exhausted` + 1×`ztp_final`.
  * **Cap + abort:** `MAX`×`poisson_component` + `MAX`×`ztp_rejection` + 1×`ztp_retry_exhausted`.
  * **A=0 short-circuit:** 1×`ztp_final` only.

**16.2 Throughput & sizing**

* **Concurrency model:** run merchants **in parallel** up to a worker cap `C`; each merchant’s loop remains **serial**.
* **Writer strategy (deterministic):**
  (a) **Serial writer**: one writer enforces §6 sort keys—simplest route to byte-identical outputs.
  (b) **Partitioned merge**: workers spill **sorted** chunks; a final **stable** merge per partition assembles `(merchant_id, attempt)` order (and cap/final keys).
* **Back-pressure:** bound in-flight merchants; size queues so the writer never merges out-of-order.
* **File layout:** avoid tiny files; batch into sensible row-groups. The spec mandates **content & order** (§6) and **idempotence**, not physical sizes.

**16.3 Determinism & resume**

* **Idempotence:** identical inputs ⇒ **byte-identical** outputs. If a complete partition exists, **skip-if-final**.
* **Resume:** stage→fsync→rename ensures an all-or-nothing publish; reruns are safe.

**16.4 Instrumentation overhead**

* Metrics (values-only, §13) update at acceptance/short-circuit/abort and **after each event append**; they do not affect control flow.

---

## S4.17) Deterministic read-side lineage gates

> These gates ensure S4 runs only for the correct merchants and reads only authoritative inputs, with lineage equality enforced **byte-for-byte**.

### 17.1 Lineage equality for S1/S2 reads — MUST
When reading S1/S2 logs, embedded envelope fields **`{seed, parameter_hash, run_id}` must equal** the path tokens **byte-for-byte**. Any mismatch is a **run-scoped structural failure** (`PARTITION_MISMATCH`); S4 must abort the run.

### 17.2 Upstream coverage & uniqueness — MUST

* **Hurdle presence (S1):** exactly one authoritative hurdle decision **must** exist for the run.

  * If **absent** ⇒ **`UPSTREAM_MISSING_S1`** (merchant-scoped abort); S4 **must not** write any S4 rows for that merchant.
  * If present with `is_multi=false` ⇒ merchant is out of scope; any S4 events would be `BRANCH_PURITY`.
* **NB final (S2):** exactly one **non-consuming** `nb_final` per merchant in scope; it fixes **`N_m≥2`**. Absence ⇒ `UPSTREAM_MISSING_S2` (merchant-scoped abort).
* **Eligibility & admissible context (S3):** S4 requires an eligibility verdict and an admissible set to derive **`A`**. Missing/ill-formed context ⇒ `UPSTREAM_MISSING_A` (merchant-scoped abort). S4 **does not** use S3 order at this state.

  * **File order is non-authoritative** for S3 reads: derive **`A := size(S3.candidate_set \ {home})`** from set contents only (never from writer order).

### 17.3 Dictionary resolution — MUST
All physical locations (read and write) are resolved via the **Data Dictionary**. Hard-coding or constructing literal paths is forbidden (`DICT_BYPASS_FORBIDDEN`, run-scoped).

### 17.4 Partition scopes — MUST

* **Reads:** S1/S2 under **`{seed, parameter_hash, run_id}`**; S3 under **`parameter_hash={…}`** (parameter-scoped).
* **Writes:** all S4 streams under **`{seed, parameter_hash, run_id}`**. Path↔embed equality must hold for every S4 row written.

### 17.5 Time & ordering neutrality — MUST
S4 must not depend on wall-clock time or file enumeration order. Ordering/replay is by **counters only** (per §10); timestamps are observational.

### 17.6 Merchant scope isolation — MUST
A merchant’s attempt loop uses a **merchant-keyed** substream and may not interleave counter spans with another merchant’s substream. Counter reuse across merchants is forbidden.

### 17.7 Deterministic inputs surface — MUST
`η`/`λ_extra`, `regime`, and `A` must be determined solely from governed values (`θ`, `X` transform/default, `MAX_ZTP_ZERO_ATTEMPTS`, `ztp_exhaustion_policy`) and authoritative upstream facts (S1, S2, S3). No environment-dependent inputs are permitted.

### 17.8 Failure handling — MUST
On any gate violation above, producers emit exactly one **values-only** failure line (per §12) and stop in the appropriate scope (merchant/run). **No partial merchant output** may be written after a merchant-scoped failure.

---

## S4.18) Artefact governance & parameter-hash participation

### 18.1 Purpose.
Pin exactly which governed inputs S4 depends on, how they are versioned and normalised, and how their bytes participate in the run’s **`parameter_hash`**. S4 is **logs-only** and is partitioned by `{seed, parameter_hash, run_id}`; these rules ensure **reproducible** K-draws and traceability.

### 18.2 Governance ledger (S4-relevant artefacts) — MUST

| Artefact (governed value) | Purpose in S4                          | Owner       | Semver | Digest algo | Participates in `parameter_hash` | Notes                                             |
|---------------------------|----------------------------------------|-------------|--------|-------------|----------------------------------|---------------------------------------------------|
| `θ = (θ₀, θ₁, θ₂, …)`     | Link parameters for `η`                | Policy      | x.y.z  | SHA-256     | **YES**                          | Numeric values serialised canonically (see §18.3) |
| `X` transform spec        | Map raw signals → `X_m ∈ [0,1]`        | Policy/Data | x.y.z  | SHA-256     | **YES**                          | Includes scaling, cohort, monotone mapping        |
| `X_default`               | Fallback when `X_m` missing            | Policy      | x.y.z  | SHA-256     | **YES**                          | Must be in \[0,1]                                 |
| `MAX_ZTP_ZERO_ATTEMPTS`   | Zero-draw cap (int)                    | Policy      | x.y.z  | SHA-256     | **YES**                          | Default 64 unless governed otherwise              |
| `ztp_exhaustion_policy`   | `"abort"` or `"downgrade_domestic"`    | Policy      | x.y.z  | SHA-256     | **YES**                          | Closed enum                                       |
| Label/stream registry     | `module`, `substream_label`, `context` | Engine      | x.y.z  | SHA-256     | **NO** (code contract)           | Changes are **breaking**; see §19                 |
| S0 numeric/RNG profile    | FP & PRNG law                          | Engine      | x.y.z  | SHA-256     | **NO** (code contract)           | Changes are **breaking**; see §19                 |

**Informative.** Governance MAY prefer a sub-linear size effect; this is **not** a protocol constraint.

### 18.3 Normalisation & hashing — MUST

* **Number serialisation:** All floating-point values **MUST** be serialised using **shortest round-trip binary64** text (no locale/epsilon variants).
* **Key order:** Within each artefact, keys **MUST** be sorted **lexicographically** before serialisation.
* **Concatenation order:** Compute

  ```
  parameter_hash = H(
    bytes(θ) ||
    bytes(X-transform) ||
    bytes(X_default) ||
    bytes(MAX_ZTP_ZERO_ATTEMPTS) ||
    bytes(ztp_exhaustion_policy)
  )
  ```

  using the **exact artefact order** shown above (top→bottom).
* Any change to these bytes **must** produce a new `parameter_hash` and hence a new S4 run partition.

### 18.4 Change classes & scope — MUST

* **Policy changes** (θ, X transform/default, cap, policy) **participate** in `parameter_hash`; **not** breaking by themselves.
* **Code-contract changes** (labels/contexts, envelope field set, regime threshold/constants, partition keys, S0 numeric/PRNG law) **do not** flow through `parameter_hash`; they are **breaking** (see §19).
* **Upstream inputs (S1/S2/S3)** are authoritative **inputs** and **do not** participate in `parameter_hash` (they may change outcomes, but not the hash).

### 18.5 Provenance & auditability — MUST
For each governed artefact, the run manifest (outside S4 logs) **must** report: `{name, version, digest, owner, last_updated}`. Producers **must** ensure the values injected into S4 match those versions **byte-for-byte**.

### 18.6 Prohibitions — MUST NOT

* **MUST NOT** fetch governed values from environment variables, clocks, or non-versioned stores.
* **MUST NOT** compute `θ` or `X` from non-governed sources.

---

## S4.19) Compatibility & evolution

**Goal.** Define which changes are **additive-safe**, which are **breaking**, how to **version/tag** them, and how to **migrate** without ambiguity or data loss. S4 is logs-only; forward compatibility hinges on **stable labels, envelopes, partitions, and semantics**.

### 19.1 Change taxonomy — **MUST**

Classify each contemplated change into exactly one bucket:

1. **Policy change** (participates in `parameter_hash`): `θ`, `X` transform/default, `MAX_ZTP_ZERO_ATTEMPTS`, `ztp_exhaustion_policy`.
2. **Additive-safe schema extension**: optional payload fields with defaults; **no** change in meaning of existing fields.
3. **Breaking code-contract change**: labels/contexts, envelope structure, regime threshold/constants, partition keys, or meanings of existing fields.

### 19.2 Additive-safe changes — **MUST**

Allowed without breaking consumers, provided JSON-Schema marks fields **optional** with **default behaviour** and consumers are tolerant readers:

* Add an **optional** payload field to `poisson_component`, `ztp_rejection`, `ztp_retry_exhausted`, or `ztp_final` (e.g., `reason`, `merchant_features_hash`, `cap_policy_version`).
* Add an **optional** boolean like `short_circuit?: true` to `ztp_final` (A=0 case), default `false`.
* Add **observability-only** counters/histograms (values-only, §13) not used in control flow.
* Tighten **validator corridors** (outside S4 producer; no producer behaviour change).

**MUST.** Preserve **existing meanings**; defaults **must** exactly reproduce prior behaviour. Keep **writer sort keys, partitions, labels, contexts** unchanged.

### 19.3 Breaking changes — **MUST NOT** (without a major)

Require a **major** bump + migration (see §19.5):

* Changing any **label/stream identifier** in §2A: `module`, `substream_label`, or `context:"ztp"`.
* Changing **partition keys** (currently `{seed, parameter_hash, run_id}`) or the **path↔embed equality** rule.
* Modifying the **envelope field set**, types, or semantics (`before/after/blocks/draws`).
* Changing the **regime threshold** (`λ<10` inversion → `ptrs`) or **PTRS constants**, or the **open-interval** rule for `u01`.
* Removing or altering the **`ztp_final`** contract (e.g., making it consuming, changing its role as the single acceptance record).
* Using **timestamps** or **file order** for ordering instead of counters.
* Altering **writer sort keys** per stream.

### 19.4 Deprecation policy — **MUST**

* Any additive field later removed is **breaking**.
* Announce deprecations as **"present but ignored"** for at least **one minor** release before removal; keep validators tolerant during the window.
* Record deprecations in the **Data Dictionary** and **artefact registry** changelog.

### 19.5 Migration playbook (for breaking changes) — **MUST**

1. **Version & tag.**

   * Bump the **module literal** (e.g., `1A.s4.ztp.v2`).
   * Introduce **versioned schema anchors** by **suffixing anchor IDs with `@vN`** (e.g., `schemas.layer1.yaml#/rng/events/poisson_component@v2`). 
   * S4 normatively uses this suffix scheme; path-segment anchor versioning is **not used** by S4. 
   * The **Data Dictionary must pin** the exact anchor version per stream.

2. **Dual-write window (optional, recommended).**

   * Producers **MAY** dual-write v1 and v2 for a bounded window; the Dictionary **must** list both.
   * Validators pin to the intended version per run configuration.

3. **Cutover & freeze.**

   * After consumers confirm v2 ingestion, freeze v1 (no more writes) and mark it **deprecated** in dictionary/registry.

4. **Backfill policy.**

   * Backfills **must** run with the same **`parameter_hash`** inputs to guarantee byte-identical outcomes.
   * When the **code contract** changes, backfill under **new version tags** only (do **not** rewrite old partitions).

### 19.6 Coexistence rules — **MUST**

* Consumers **must** pin on one of: `(module, schema version)` or `(context, schema version)`; never "best-effort".
* Producers **must not** interleave v1 and v2 rows within the same `(seed, parameter_hash, run_id)` partition.

### 19.7 Consumer & validator impact — **MUST**

* **S6**: Reads only `ztp_final{K_target, lambda_extra, attempts, regime, exhausted?}`; tolerant to **optional** new fields; **must** ignore unknown keys.
* **Validators**: Tolerate additive fields; enforce invariants on the **core** set (attempt accounting, cardinalities, counters, existence/absence of `ztp_final`, cap semantics).
* **Downstream order**: S3 `candidate_rank` remains the sole authority—unchanged by S4 evolution.

### 19.8 Version signalling — **MUST**

* Expose `{module_version, schema_version}` in the S4 run manifest (outside logs) and **optionally** in `ztp_final` as **optional** payload fields for audit.
* Track `θ`/`X`/cap/policy versions in the **governance ledger** (§18) and tie them to `parameter_hash`.

### 19.9 Rollback stance — **MUST**

* Rollbacks **must not** overwrite or delete already-published partitions.
* After rollback, producers **must** resume writing with the previous stable `(module, schema)` pair; the Dictionary must point consumers accordingly.

### 19.10 Examples of safe vs breaking changes — **Informative**

* **Safe (additive):** Add optional `reason:"no_admissible"` to `ztp_final` (default absent).
* **Breaking:** Rename `context:"ztp"` → `"ztp_k"`; change `λ` threshold to 8; make `ztp_final` consuming.

---

## S4.20) Handoff to later states

### 20.1 Purpose.
Freeze exactly what S4 exports, who consumes it, and how downstream must interpret it. S4 is **logs-only**; it fixes a **target** foreign count and nothing else.

### 20.2 What S4 exports (authoritative for downstream).
From `ztp_final` for merchant *m*:

* `K_target : int≥0` — target foreign count (**authoritative outcome of S4**).
  - `≥1` on acceptance;
  - `=0` only via **A=0 short-circuit** or **exhaustion policy = "downgrade_domestic"**.
* `lambda_extra : float64` — intensity used (audit/diagnostics only; not a gate downstream).
* `attempts : int≥0` — number of Poisson attempts written by S4 (`0` iff short-circuit).
* `regime : "inversion"|"ptrs"` — Poisson sampler branch (closed enum).
* `exhausted? : bool` — present/`true` only for **cap + downgrade** outcome; omitted otherwise.
* Optional `reason : "no_admissible"` — present only for A=0 short-circuit (if the schema includes this optional field).

### 20.3 Who consumes S4 and how.

* **S6 (top-K selection)** — *MUST* read `ztp_final{K_target, lambda_extra, attempts, regime, exhausted?, reason?}` and combine with its own admissible foreign set of size `A`.
  - *Realisation rule (binding):* **`K_realized = min(K_target, A)`**.
  - If `K_target = 0` (short-circuit/downgrade): *MUST* skip top-K and continue domestic-only.
  - If `K_target > A` (shortfall): *MUST* select **all A**; **MAY** log a non-consuming `topk_shortfall{K_target, A}` marker **in S6**.
* **S7 (allocation / integerisation)** — *MUST NOT* infer any probability from S4 logs. It receives the set chosen by S6 and later allocates **N** across {home + chosen foreigns} (outside S4’s scope).
* **S8 (sequencing / IDs)** — unaffected by S4 semantics; it operates on per-country counts.
* **S9 (egress / handoff to 1B)** — S4 contributes no egress rows. S9’s `outlet_catalogue` contains **no** inter-country order; consumers recover order from S3 `candidate_rank`.

### 20.4 Authority boundaries (reaffirmed).

* S4 **never** encodes inter-country order; **S3 `candidate_rank`** remains the sole authority for cross-country order (home=0; contiguous).
* S4 **fixes only** the **target** count (`K_target`); S6/S7/S8 own *which* countries, *how many per country*, and *per-country sequences* respectively.
* S4’s `lambda_extra`, `attempts`, `regime` are **audit surfaces**, not consumer gates.

### 20.5 Consumer pitfalls (MUST NOT).

* *MUST NOT* derive **`K_target`** by counting Poisson attempts or rejections; the **only** authoritative target is `ztp_final.K_target`. *(S6 later realises `K_realized = min(K_target, A)`.)*
* *MUST NOT* treat `lambda_extra` as a probabilistic weight for later selection.
* *MUST NOT* exceed `A` when realising K (enforced in **S6 (Top-K selection)** via `min(K_target, A)`).
* *MUST NOT* process a merchant **without a `ztp_final`** (e.g., `NUMERIC_INVALID` or cap + policy=`"abort"`).

### 20.6 Lineage continuity (MUST).
All downstream states (S6+) *must* carry forward `{seed, parameter_hash, run_id}` as read from S4; they *must not* reinterpret or recompute `lambda_extra` or `regime`.

---

## S4.21) Glossary & closed vocabularies — **Normative (terms)** / **Informative (glossary)**

### 21.1 Closed vocabularies (enumerations) — MUST

* `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}` — governed policy when the zero-draw cap is hit.
* `regime ∈ {"inversion","ptrs"}` — Poisson sampler branch; set once per merchant from the λ threshold.
* `context == "ztp"` — fixed context string on all S4 events.
* `module == "1A.s4.ztp"`, `substream_label == "poisson_component"` — fixed label literals (see §2A).
* `reason ∈ {"no_admissible"}` — optional `ztp_final` payload enum for A=0 short-circuit. 
  *(Schema presence.)* The `reason` field is optional and **absent in this schema version**; adding it in a later schema revision is **additive-safe**; this document fixes the vocabulary in advance.

### 21.2 Terms (precise meanings) — MUST/SHOULD

* **ZTP (Zero-Truncated Poisson)** — Distribution of `Y | (Y≥1)` where `Y~Poisson(λ)`. Realised by rejecting 0s from Poisson draws.
* **PTRS** — Poisson sampling regime for large λ (two uniforms + geometric attempts; constants/threshold fixed).
* **Inversion** — Poisson sampling regime for small λ; consumes exactly `K+1` uniforms for result `K`.
* **`attempt` (int≥1)** — 1-based index of a Poisson draw for a merchant; strictly increasing and contiguous on accepted/capped paths.
* **`attempts` (int≥0)** — on `ztp_final`/cap rows: equals last attempt index; **0 only for A=0 short-circuit**.
* **`draws` (decimal-u128 string)** — actual uniforms consumed by the event (consuming rows only).
* **`blocks` (u64)** — counter delta = **`after − before`** (consuming rows only).
* **`before` / `after` (u128)** — PRNG counters that prove order; **timestamps are observational only**.
* **`K_target` (int≥0)** — S4’s authoritative **target** foreign count: result of ZTP acceptance (`≥1`) or governed `0` (A=0 / downgrade).
* **`K_realized` (int≥0)** — realised selection size used by **S6**: `min(K_target, A)`.
* **`A` (int≥0)** — size of admissible foreign set from S3 (foreigns only; home excluded).
* **`exhausted` (bool)** — `true` only when the cap is hit and policy=`"downgrade_domestic"`; omitted otherwise.
* **`λ_extra` (float64 > 0)** — intensity for extra-country count; computed from log-link `η` in binary64 with fixed order.
* **`parameter_hash` (hex64)** — run’s parameter set hash; partitions S4 inputs/outputs with `seed`/`run_id`.
* **`manifest_fingerprint` (hex64)** — run fingerprint used by egress/validation (S4 writes logs only).

### 21.3 Notational conventions — SHOULD

* `log` denotes natural logarithm.
* Where float comparisons affect control flow (λ threshold), comparisons are exact in binary64 (`λ < 10` ⇒ inversion; else PTRS).
* All sets/maps over ISO2 codes are **order-free** unless explicitly sorted/ranked by a defined key.

### 21.4 Prohibitions (terminology drift) — MUST NOT

* *MUST NOT* call `K_target` "realised K" in S4; **only S6** realises K vis-à-vis `A`.
* *MUST NOT* use "probability" for `base_weight_dp` (priors live outside S4); S4 has no priors and no Dirichlet.
* *MUST NOT* use "order" to describe any S4 output; cross-country order belongs exclusively to S3 `candidate_rank`.

---


[S4-END VERBATIM]

---
