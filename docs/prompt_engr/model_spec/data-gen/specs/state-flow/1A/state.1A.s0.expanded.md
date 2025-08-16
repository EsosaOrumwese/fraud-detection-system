# S0.1 — Universe, Symbols, Authority (normative)

## Purpose & scope

S0.1 establishes the **canonical universe** (merchant rows and reference datasets) and the **schema authority** for subsegment 1A. Its job is to make the rest of S0–S9 reproducible by fixing the domain symbols and where their truth comes from. No RNG is consumed here.

**What S0.1 freezes for the run**

* The merchant universe $\mathcal{M}$ from the **normalised ingress** table `merchant_ids`.
* The immutable **reference artefacts**: ISO-3166 country set $\mathcal{I}$; GDP-per-capita vintage $G$ pinned to **2025-04-15**; a precomputed Jenks $K{=}5$ GDP bucket map $B$.
* The **schema authority**: only JSON-Schema contracts in `schemas.ingress.layer1.yaml`, `schemas.1A.yaml`, and shared RNG/event schemas in `schemas.layer1.yaml` are authoritative; Avro (if any) is non-authoritative.

> Downstream consequence: **inter-country order is never encoded** in egress `outlet_catalogue`; consumers MUST join `country_set.rank` (0=home; foreigns follow Gumbel selection order). S0.1 records that rule as part of the authority.

---

## Domain symbols (definitions and types)

### Merchants (ingress universe)

* Let $\mathcal{M}$ be the finite set of merchants from the normalised ingress table:

  $$
  \texttt{merchant_ids}\subset\{(\texttt{merchant_id},\ \texttt{mcc},\ \texttt{channel},\ \texttt{home_country_iso})\}\,,
  $$

  validated by `schemas.ingress.layer1.yaml#/merchant_ids`.

* Field domains (as enforced by the ingress schema and reused throughout 1A):

  * $\texttt{merchant_id}$: opaque 64-bit identifier (string/id type per schema).
  * $\texttt{mcc}\in\mathcal{K}$: valid 4-digit MCC code set $\mathcal{K}$.
  * $\texttt{channel}\in\mathcal{C}$: card-present vs card-not-present, i.e. $\mathcal{C}=\{\mathrm{CP},\mathrm{CNP}\}$.
  * $\texttt{home_country_iso}\in\mathcal{I}$: ISO-3166 alpha-2 code. (FK to $\mathcal{I}$ enforced later.)
    (These symbols are referenced repeatedly in S1–S7; S0.1 defines them once.)

### Canonical references (immutable within the run)

* **Countries:** $\mathcal{I}$ = ISO-3166 alpha-2 country list (finite, determined by the pinned reference).
* **GDP (per-capita) map:** $G:\mathcal{I}\rightarrow\mathbb{R}_{>0}$, **pinned to 2025-04-15** (fixes both values and coverage).
* **GDP bucket map:** $B:\mathcal{I}\rightarrow\{1,\dots,5\}$ — a precomputed Jenks $K=5$ classification over $G$. (S0.4 will define how to (re)build it; here we treat the artefact as immutable input.)

### Derived per-merchant tuple

For $m\in\mathcal{M}$, define the typed triple:

$$
t(m):=\big(\texttt{mcc}_m,\ \texttt{channel}_m,\ \texttt{home_country_iso}_m\big)\in\mathcal{K}\times\mathcal{C}\times\mathcal{I}\,,
$$

used by deterministic policies in later states (e.g., cross-border eligibility).

---

## Authority & contracts (single source of truth)

### Authoritative schemas for 1A

Only **JSON-Schema** is the source of truth for 1A. All dataset contracts and RNG event contracts must refer to these paths (JSON Pointer fragments):

* Ingress: `schemas.ingress.layer1.yaml#/merchant_ids`.
* 1A model/alloc/egress: `schemas.1A.yaml` (e.g., `#/model/hurdle_pi_probs`, `#/prep/sparse_flag`, `#/alloc/country_set`, `#/egress/outlet_catalogue`).
* Shared RNG events: `schemas.layer1.yaml#/rng/events/*`.
  Avro (`.avsc`) is **non-authoritative** for 1A and must not be referenced by registry/dictionary entries.

### Semantic clarifications (normative)

* `country_set` is the **only** authority for **cross-country order** (rank: 0 = home, then foreigns). Egress `outlet_catalogue` does **not** carry cross-country order; consumers **must** join `country_set.rank`. This rule is part of the schema authority and dictionary notes.
* Partitioning semantics (used later, documented here for authority): parameter-scoped datasets partition by `parameter_hash`, while egress/validation partition by `manifest_fingerprint`. (Full details in S0.10; recorded as an invariant here.)

---

## Run-time invariants (frozen context)

S0.1 constructs a **run context** $\mathcal{U}$ and freezes it:

$$
\mathcal{U} := \big(\mathcal{M}, \ \mathcal{I}, \ G,\ B,\ \text{SchemaAuthority}\big).
$$

**Invariants (must hold for the entire run):**

1. **Immutability:** $\mathcal{M}$, $\mathcal{I}$, $G$, $B$ and the authority mapping must not change after S0.1 completes. Any observed mutation later is a hard failure.
2. **Coverage:** $\forall m\in\mathcal{M}:\ \texttt{home_country_iso}_m\in\mathcal{I}$. Missing FK is a schema/lineage violation upstream of S3/S6.
3. **Determinism:** No RNG consumption; all outputs of S0.1 are pure functions of the loaded bytes and schemas (S0.2 will digest/record them).
4. **Authority compliance:** Every dataset/stream referenced downstream must use the **JSON-Schema** anchors listed above; any non-authoritative reference is a policy breach.

---

## Failure semantics (abort codes)

S0.1 MUST abort the run if any of the following occur:

* `E_INGRESS_SCHEMA`: `merchant_ids` fails validation against `schemas.ingress.layer1.yaml#/merchant_ids`.
* `E_REF_MISSING`: any canonical reference (ISO list, GDP vintage, or bucket map) is missing or unreadable. (S0.2 will separately catch digest mismatches when hashing.)
* `E_AUTHORITY_BREACH`: a dataset or event in registry/dictionary points to a non-authoritative schema (e.g., an `.avsc`) for 1A.
* `E_FK_HOME_ISO`: some $m$ has `home_country_iso` not in $\mathcal{I}$. (This will also be caught later when persisting `country_set`.)

> When S0.1 aborts, no RNG audit or parameter/fingerprint artefacts should be emitted; S0.2 has not yet run.

---

## Validation hooks (what CI/runtime checks here)

* **Schema check:** validate `merchant_ids` against the ingress schema before deriving $t(m)$.
* **Reference presence & immutability:** assert that the referenced ISO set, GDP vintage (2025-04-15), and $B$ load successfully and are cached read-only for the lifetime of the run.
* **Authority audit:** scan the registry/dictionary for any 1A dataset using **non-JSON-Schema** refs and fail the build if found (policy enforcement).
* **Country FK pre-check:** `home_country_iso ∈ 𝕀` for all merchants. (This avoids later surprises at S3/S6.)

---

## Reference routine (language-agnostic)

```text
function S0_1_resolve_universe_and_authority():
  # 1) Load & validate merchants
  M = read_table("merchant_ids")                          # ingress
  assert schema_ok(M, "schemas.ingress.layer1.yaml#/merchant_ids")

  # 2) Load canonical references (read-only for run)
  I = load_iso3166_alpha2()                                # set of country codes
  G = load_gdp_per_capita(vintage="2025-04-15")            # map ISO->R_{>0}
  B = load_gdp_jenks_buckets(K=5, vintage="2025-04-15")    # map ISO-> {1..5}; precomputed artefact

  # 3) Pre-flight authority: JSON-Schema only
  assert all_registry_refs_are_jsonschema()
  assert dictionary_notes_include_country_set_order_rule()

  # 4) Cross-check foreign keys
  for m in M:
      assert m.home_country_iso in I, E_FK_HOME_ISO

  # 5) Freeze run context (no RNG here)
  U = { M: M, I: I, G: G, B: B, authority: JSONSCHEMA_ONLY }
  return U
```

(Where `dictionary_notes_include_country_set_order_rule()` verifies that egress readers are instructed to **join `country_set.rank`** for cross-country order; this is required by the dictionary/schema policy.)

---

## Notes for downstream states

* S0.2 will now **hash** the loaded bytes (parameters and artefacts) to derive `parameter_hash` and `manifest_fingerprint`, and log provenance. S0.1’s immutability guarantees make those digests stable.
* S3’s eligibility and S6’s `country_set` persistence rely on S0.1’s **country FK** and authority decisions; violating them becomes a structural failure later.

---

**Summary:** S0.1 pins the **who** (merchants), the **where** (countries), the **context** (GDP & buckets), and the **law** (schema authority). It consumes **no randomness**, and it fails fast on any schema/authority/coverage breach—so everything that follows is on rock-solid, reproducible ground.

---

# S0.2 — Hashes & Identifiers (Parameter Set, Manifest Fingerprint, Run ID)

## Purpose (what S0.2 guarantees)

Create the three lineage keys that make 1A reproducible and auditable:

1. **`parameter_hash`** — versions *parameter-scoped* datasets; changes when any governed parameter file’s **bytes** change.
2. **`manifest_fingerprint`** — versions *egress & validation* outputs; changes when *any opened artefact*, the code commit, or the parameter bundle changes.
3. **`run_id`** — partitions logs; **not** part of modelling state; never influences RNG or outputs.

**No RNG is consumed in S0.2.** These identifiers are pure functions of bytes + time (for `run_id` only as a log partitioner).

---

## S0.2.1 Hash primitives (pin the byte-level rules)

* Digest: $\mathrm{SHA256}(x)\in\{0,1\}^{256}$ (raw 32-byte digest).
* Operators: `||` = byte concatenation; `⊕` = **bytewise XOR** on 32-byte arrays.
* Encodings:

  * `hex64(b32)`: lower-case hex of 32 bytes ⇒ 64 chars.
  * `hex32(b16)`: lower-case hex of 16 bytes ⇒ 32 chars.

**Byte domain rule:** Hash **exact file bytes**; no parsing, normalisation, or newline conversions. Files are opened in binary mode. (This is implicit in the locked spec’s “SHA256(bytes(a))”.)

---

## S0.2.2 `parameter_hash` (canonical, normative)

**Governed set $\mathcal{P}$.** Exactly these three parameter files (canonical names):
`hurdle_coefficients.yaml`, `nb_dispersion_coefficients.yaml`, `crossborder_hyperparams.yaml`.

**Algorithm (exact):**

1. Sort $\mathcal{P}$ by **filename** using bytewise ASCII lexicographic order to get $(p_1,p_2,p_3)$.
2. Compute inner digests $d_i = \mathrm{SHA256}(\text{bytes}(p_i))$ (each 32 bytes).
3. Concatenate: $c = d_1 \,\|\, d_2 \,\|\, d_3$ (96 bytes).
4. Outer digest: $\text{parameter_hash_bytes} = \mathrm{SHA256}(c)$.
5. Encode: $\text{parameter_hash} = \text{hex64}(\text{parameter_hash_bytes})$.

**Properties:**

* Deterministic; order-invariant to input presentation (because of the filename sort).
* Any byte change in any governed file yields a different `parameter_hash`.
* Only the three canonical files influence this hash (governance choice).

**Effect on storage:** *Parameter-scoped* datasets **must** partition by `parameter_hash={parameter_hash}` (e.g., `crossborder_eligibility_flags`, `country_set`, `ranking_residual_cache_1A`, optional `hurdle_pi_probs`).

**Errors (abort S0):**

* `E_PARAM_EMPTY` (any of the three missing/unreadable).
* `E_PARAM_NONASCII_NAME` (if a basename isn’t ASCII).
* `E_PARAM_IO(name, errno)` (I/O error).
* `E_PARAM_DUP_BASENAME` (should never happen if canonical).
  (Names are informative; the lock implies the structural checks by construction.)

**Audit (emit these rows):**

* `param_digest_log`: `{filename, size_bytes, sha256_hex, mtime_ns}` for each $p_i$.
* `parameter_hash_resolved`: `{parameter_hash, filenames_sorted}`.
  (These names mirror S0’s practice of logging lineage; the lock explicitly makes `parameter_hash` a first-class lineage value.)

---

## S0.2.3 `manifest_fingerprint` (run lineage for egress/validation)

**Purpose.** A single lineage key that flips if **anything** material to the run changes: any opened artefact, the repository commit ID, or the parameter bundle. Egress/validation partitions use this key (e.g., `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/…`).

**Inputs (exact):**

* $\mathcal{A}$ = set of **all artefacts the run opens** (includes the parameter files above *plus* ISO tables, GDP map, etc.). Let $D(a)=\mathrm{SHA256}(\text{bytes}(a))$.
* `git_32`: the repository commit as **32 bytes**; if your VCS commit is 20 bytes (SHA-1), left-pad with 12 zero bytes to 32.
* `parameter_hash_bytes` from S0.2.2.

**Algorithm (exact):**

$$
X \;=\; \bigoplus_{a\in \mathcal{A}} D(a)\ \ \oplus\ \ \text{git}_{32}\ \ \oplus\ \ \text{parameter_hash_bytes},\qquad
\text{manifest_fingerprint_bytes}=\mathrm{SHA256}(X),
$$

$$
\text{manifest_fingerprint}=\text{hex64}(\text{manifest_fingerprint_bytes}).
$$

**Properties:**

* Changing **any** opened artefact’s bytes flips the fingerprint.
* Changing the **code commit** flips the fingerprint.
* Changing the **parameter bundle** flips the fingerprint (folded in via `parameter_hash_bytes`).

**Effect on storage:** Egress & validation datasets **must** partition by `fingerprint={manifest_fingerprint}` (often alongside `seed`).
Example:
`outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/…`

**Errors (abort S0):**

* `E_ARTIFACT_EMPTY` (no artefacts enumerated).
* `E_ARTIFACT_IO(name, errno)` (failed to read an opened artefact).
* `E_GIT_BYTES` (unable to obtain/format the commit into 32 bytes).
* `E_PARAM_HASH_ABSENT` (S0.2.2 didn’t complete; parameter bytes not available).

**Audit (emit):**

* `manifest_fingerprint_resolved`: `{ manifest_fingerprint, artifact_count, git_commit_hex, parameter_hash }`.

---

## S0.2.4 `run_id` (logs only; not modelling state)

**Goal.** Give each execution its own log partition key; **must not** affect RNG or outputs.

**Inputs:**

* `manifest_fingerprint_bytes` (32 bytes),
* `seed` (u64; the modelling seed), and
* start time $T$ = UTC **nanoseconds** (u64).

**Algorithm (exact):**

$$
\texttt{run_id}=\text{hex32}\!\Big(\mathrm{SHA256}\big(\text{``run:1A''}\ \|\ \texttt{manifest_fingerprint_bytes}\ \|\ \mathrm{LE64}(\texttt{seed})\ \|\ \mathrm{LE64}(T)\big)[0{:}16]\Big).
$$

**Scope & invariants:**

* Partitions **only** `rng_audit_log`, `rng_trace_log`, and `rng_event_*` as `{seed, parameter_hash, run_id}`.
* `run_id` never enters RNG seeding or model state; outputs depend **only** on `(seed, parameter_hash, manifest_fingerprint)`.

---

## Partitioning contract (recap; dictionary-backed)

* **Parameter-scoped:** `…/parameter_hash={parameter_hash}/…`
* **Egress/validation:** `…/fingerprint={manifest_fingerprint}/…` (often with `seed`).
* **RNG logs/events:** partitions by `{ seed, parameter_hash, run_id }`.

---

## Operational requirements (race-proofing, concurrency, reproducibility)

* **Streaming reads:** hash via streaming to tolerate large files without loading to RAM; the digest must be over **exact bytes**.
* **Anti-race guard:** optionally `stat` (size, mtime) **before/after** hashing; if they differ, re-read and re-hash (or fail `E_PARAM_RACE` / `E_ARTIFACT_RACE`).
* **Filename semantics:** sort by **basename** (no directory components) when building chained/ordered digests.
* **Commit bytes:** if the VCS uses SHA-256, take 32 bytes as-is; if SHA-1, **left-pad** to 32 bytes.
* **Immutability:** once S0.2 is done, treat `parameter_hash` & `manifest_fingerprint` as **final** for the run; embed them in envelopes and partitions.

---

## Failure semantics (explicit aborts)

* `E_PARAM_*` / `E_ARTIFACT_*` / `E_GIT_*` / `E_PARAM_RACE` / `E_ARTIFACT_RACE`: **abort the run** (S0.9 lists abort classes; S0.2 raises these when hashing/enumerating fails).
* On abort in S0.2, **do not** emit RNG audit/trace; S0.3 hasn’t begun.

---

## Validation & CI hooks (prove it’s right)

* **Recompute checks:** CI re-computes `parameter_hash` from the three governed files and asserts equality with the logged `parameter_hash_resolved`. Same for `manifest_fingerprint` from enumerated artefacts + commit bytes.
* **Partition lint:** verify the dictionary enforces `parameter_hash` on parameter-scoped datasets and `fingerprint` on egress/validation, and that RNG logs use `{ seed, parameter_hash, run_id }`.
* **Uniqueness:** ensure `run_id` doesn’t collide within `{ seed, parameter_hash }` scope (practically impossible; catches clock/monotonic-time bugs).

---

## Reference pseudocode (language-agnostic)

```text
# --- parameter_hash ---
def compute_parameter_hash(P_files):            # list of (basename, path)
    if len(P_files) != 3: raise E_PARAM_EMPTY
    assert all_ascii_unique_basenames(P_files)
    files = sort_by_basename_ascii(P_files)     # (p1,p2,p3)
    inner = [sha256_stream(path) for (_, path) in files]  # 3 * 32 bytes
    chain = inner[0] + inner[1] + inner[2]      # 96 bytes
    H = sha256_bytes(chain)                     # 32 bytes
    return hex_lower_64(H), H                   # hex64 + raw bytes

# --- manifest_fingerprint ---
def compute_manifest_fingerprint(artifacts, git32, param_bytes):
    if not artifacts: raise E_ARTIFACT_EMPTY
    X = zero_bytes(32)
    for a in artifacts:
        X = xor32(X, sha256_stream(a))          # bytewise XOR of 32-byte digests
    X = xor32(X, git32)
    X = xor32(X, param_bytes)
    F = sha256_bytes(X)                         # 32 bytes
    return hex_lower_64(F), F

# --- run_id ---
def derive_run_id(fingerprint_bytes, seed_u64, start_time_ns):
    payload = b"run:1A" + fingerprint_bytes \
              + le64(seed_u64) + le64(start_time_ns)
    r = sha256_bytes(payload)[:16]              # first 16 bytes
    return hex_lower_32(r)
```

---

## Worked mini-example (structure only)

* Inner digests: `d1 = SHA256(p1)`, `d2 = …`, `d3 = …`; chain and hash to get `parameter_hash`.
* Artefacts $A$: 17 files opened → XOR their digests, XOR with `git_32` and `parameter_hash_bytes`, hash → `manifest_fingerprint`.
* Start run at $T$ ns with modelling `seed` ⇒ derive `run_id`; log partitions use `{ seed, parameter_hash, run_id }`.

---

## Where this shows up next

S0.3 will use `manifest_fingerprint_bytes` + `seed` to derive the **master RNG seed** and initial counter; S0.2 must therefore run **before** any RNG audit/trace emission.

---

**Bottom line:** S0.2 turns bytes and commit into **two immutable lineage keys** (`parameter_hash`, `manifest_fingerprint`) and a **log-only** `run_id`. Partitioning and envelopes throughout 1A rely on these values exactly as formalised above; change any governed byte and the right partitions flip.

---

# S0.3 — RNG Engine, Substreams, Samplers & Draw Accounting (normative)

## Purpose

S0.3 pins the *entire* randomness contract for 1A: which PRNG we use, how we carve it into **keyed, order-invariant** substreams, how we map bits to $(0,1)$, how we generate $Z\sim\mathcal{N}(0,1)$, $\Gamma(\alpha,1)$, and $\mathrm{Poisson}(\lambda)$, and how every draw is **counted, logged, and reproducible**. This sub-state consumes RNG (unlike S0.1–S0.2).

---

## S0.3.1 Engine & Event Envelope

### PRNG

* **Algorithm:** Philox 2×64 with 10 rounds (counter-based; splittable).
* **State per substream:** a 64-bit **key** $k$ and a 128-bit **counter** $c=(c_3,c_2,c_1,c_0)$.
* **Block function:** $(x_0,x_1)\leftarrow \mathrm{PHILOX}_{2\times64,10}(k, c)$ returns **two** independent 64-bit words per counter.
* **Counter advance:** after consuming a block, increment $c\leftarrow c+1$ mod $2^{128}$.

> We never *cache* the second normal, but we **do** use both 64-bit lanes of each block as independent $x$-words when we need two uniforms at once (e.g., Box–Muller).

### Event envelope (mandatory fields for **every** RNG event/log row)

```
{
  ts_utc:            int64  # epoch ns
  module:            string # e.g. "1A.S6.gumbel"
  substream_label:   string # e.g. "gumbel_key", "dirichlet_gamma_vector"
  seed:              uint64 # modelling seed (S0.3.2)
  parameter_hash:    string # hex64 (S0.2.2)
  manifest_fingerprint: string # hex64 (S0.2.3)
  run_id:            string # hex32 (S0.2.4)
  rng_counter_before_lo: uint64
  rng_counter_before_hi: uint64
  rng_counter_after_lo:  uint64
  rng_counter_after_hi:  uint64
  draws:             uint128 # exact count of 64-bit words consumed by this event
  payload: { ... }          # event-specific fields (e.g., iso, weight, key, α, λ, etc.)
}
```

* **Non-consuming** events set `draws = 0` and keep `before == after`.
* The pair `(substream_label, payload.ids...)` identifies the **substream** used (defined next).

---

## S0.3.2 Master seed & initial counter (per run)

Let:

* `seed` = user/model seed (u64).
* `manifest_fingerprint_bytes` (32 bytes) from S0.2.3.

Define a master material $\mathsf{M} := \mathrm{SHA256}(\text{"mlr:1A.master"}\ \|\ \texttt{manifest_fingerprint_bytes}\ \|\ \mathrm{LE64}(\texttt{seed}))$ (32 bytes).

Derive:

* **Root key:** $k_\star = \mathrm{LOW64}(\mathsf{M})$.
* **Root counter:** $c_\star = (\mathrm{BE64}(\mathsf{M}[8{:}16]),\ \mathrm{BE64}(\mathsf{M}[16{:}24]),\ \mathrm{BE64}(\mathsf{M}[24{:}32]),\ 0)$.

> No events use $(k_\star,c_\star)$ directly; all substreams are **keyed** from it (next section). The initial audit row is emitted **before** any consumption with `run_id` present.

---

## S0.3.3 Keyed, order-invariant substreams

We must be **order-invariant** under parallelism and sharding. To achieve that, every logical substream is keyed by a deterministic tuple, never by execution order.

### Substream key & counter derivation

For any event family label $\ell$ (e.g., `"hurdle_bernoulli"`, `"gumbel_key"`, `"dirichlet_gamma_vector"`) and entity identifiers $\mathbf{id}$ (e.g., `merchant_id`, `candidate_index i`, or `iso`), define a byte message

$$
\mathsf{msg} := \text{"mlr:1A:"}\ \|\ \ell\ \|\ \text{"|"}\ \|\ \mathrm{SER}(\mathbf{id}),
$$

where `SER` is a stable, endian-pinned encoding of IDs (e.g., `merchant_id` as LE64, `i` as LE32, ISO as 2 ASCII bytes).

Compute:

$$
\mathsf{H} := \mathrm{SHA256}\big(\mathsf{M}\ \|\ \mathsf{msg}\big)\quad(\text{32 bytes}).
$$

Then set the **substream**:

* $k(\ell,\mathbf{id}) = \mathrm{LOW64}(\mathsf{H})$,
* $c(\ell,\mathbf{id}) = \big(\mathrm{BE64}(\mathsf{H}[8{:}16]),\ \mathrm{BE64}(\mathsf{H}[16{:}24]),\ \mathrm{BE64}(\mathsf{H}[24{:}32]),\ 0\big).$

> All draws for that event **must** come from $\mathrm{PHILOX}(k(\ell,\mathbf{id}), \cdot)$ by advancing the counter monotonically. This makes results independent of processing order and partitioning.

---

## S0.3.4 Uniforms on the **open** interval $(0,1)$

Given a 64-bit word $x\in\{0,\dots,2^{64}-1\}$, define:

$$
u = \frac{x+1}{2^{64}+1}\in(0,1).
$$

* This mapping guarantees **open bounds** (never 0 or 1), avoiding $\ln(0)$ in Box–Muller and $\log\log(1)$ in Gumbel.
* When two uniforms are needed simultaneously, use the two 64-bit lanes $(x_0,x_1)$ from the **same** Philox block, mapped independently via the same formula.

---

## S0.3.5 Standard normal $Z\sim\mathcal{N}(0,1)$ (Box–Muller, no cache)

To sample one $Z$:

1. Draw $(u_1,u_2)\in (0,1)^2$ using **one** Philox block.
2. Compute

$$
r = \sqrt{-2\ln u_1},\quad \theta = 2\pi u_2,\quad
Z = r\cos\theta.
$$

* **Budget:** exactly **2 uniforms** per $Z$.
* **No caching:** discard $r\sin\theta$; never reuse it later.
* **Determinism:** trigonometric/log operations in binary64; no FMA; serial evaluation (see S0.8 numeric policy).

---

## S0.3.6 Gamma $\Gamma(\alpha,1)$ (Marsaglia–Tsang, fixed-block accounting)

We require gamma variates for Dirichlet weights (S7). Use Marsaglia–Tsang’s method with **fixed draw blocks** so draw counts are predictable.

### Case A: $\alpha \ge 1$

Let $d = \alpha - \tfrac{1}{3}$, $c = 1/\sqrt{9d}$. Repeat:

1. **Normals:** draw one $Z\sim\mathcal{N}(0,1)$ via S0.3.5 (consumes **2 uniforms**).
2. **Transform:** $v = (1 + cZ)^3$. If $v \le 0$, **reject**.
3. **Accept test:** draw $u\in(0,1)$ (**+1 uniform**) and accept if

$$
\ln u \le \tfrac{1}{2}Z^2 + d - dv + d\ln v.
$$

On acceptance, return $X = dv$.

**Budget discipline:** one attempt consumes **3 uniforms** (2 for $Z$, 1 for $u$). On rejection, consume another **block of 3**; total draws per sample are multiples of 3.

### Case B: $\alpha \in (0,1)$

Use the **boosting** trick with draw-count normalisation:

1. Sample $Y\sim\Gamma(\alpha+1,1)$ using Case A (consumes a multiple of 3 uniforms).
2. Draw $u\in(0,1)$ (**+1 uniform**) and set $X = Y \cdot u^{1/\alpha}$.

**Block normalisation:** to keep “draws % 3 == 0” for **every** gamma sample, immediately draw and discard **2 dummy uniforms** after step (2). Thus, each completed $\Gamma(\alpha,1)$ consumes a total that is a multiple of **3** uniforms (attempt-multiple for step 1 plus 3 from step 2 + dummies).

> **Invariants:**
> • Each gamma sample uses $3t$ uniforms for some integer $t\ge 1$.
> • A `dirichlet_gamma_vector` of dimension $K$ consumes a multiple of **3K** uniforms.

---

## S0.3.7 Poisson $\mathrm{Poisson}(\lambda)$ and ZTP scaffolding

We need Poisson counts in NB/ZTP contexts later. Pin the samplers (budgets are variable; envelope must record exact draws):

### Small $\lambda$ (default threshold 10)

**Inversion** method: draw uniforms $u_1,u_2,\dots$ and iterate a cumulative product until it falls below $e^{-\lambda}$.

* **Budget:** variable per outcome $N$ (roughly $N+1$ uniforms).
* **Determinism:** serial loop, binary64.

### Moderate/large $\lambda$ (≥10)

Use a PTRS-class rejection sampler (Hörmann) requiring **one normal** and **one uniform** per attempt; acceptance can require multiple attempts.

* **Budget:** multiples of $3$ uniforms per attempt (2 for normal, 1 for accept $u$).
* **Constants:** fix the exact numeric constants and branch thresholds in code (documented in the sampler’s module notes); deterministic math (S0.8).

### Zero-Truncated Poisson (ZTP) scaffolding

ZTP is handled in S4 with a corridor (e.g., max 64 rejections); **here** we only define that **ZTP draws are regular Poisson draws conditioned on $N>0$** via accept/reject. The event envelope must reflect *all* uniforms used across attempts; the per-event `draws` counter therefore grows with rejections.

---

## S0.3.8 Gumbel key from a single uniform

For candidate ranking we use Gumbel keys:

* Draw $u\in(0,1)$ and compute

$$
g = -\ln(-\ln u).
$$

* **Budget:** **1 uniform** per candidate.
* **Tie-break:** when sorting by $g$, break ties **lexicographically** by ISO code (or the deterministic secondary key specified by the state using it).
* **Logging:** emit one `gumbel_key` event **per candidate** with the standard envelope; `weight` and `iso` live in payload.

---

## S0.3.9 Draw accounting & logs (auditable replay)

Two log streams book-keep RNG usage in addition to the event logs:

1. **`rng_audit_log`** (one row at run start, **before any draw**): snapshot of the root seed/counter identity for audit (`seed`, `manifest_fingerprint`, `parameter_hash`, `run_id`, wall-clock, code version).
2. **`rng_trace_log`** (**one row per** $(\texttt{module},\texttt{substream_label})$): cumulative `draws` consumed on that substream at emission time, with the *current* `(counter_before, counter_after)`.

**Per-event budgets (must hold):**

* **Bernoulli hurdle:**

  * If $0<\pi<1$: **1** uniform.
  * If $\pi\in\{0,1\}$: **0** uniforms (`draws=0`).
* **Gumbel key:** **1** uniform per candidate.
* **Normal $Z$:** **2** uniforms (Box–Muller, no cache).
* **Gamma:** **multiples of 3** uniforms per sample (by design in §S0.3.6).
* **Dirichlet $K$-vector:** **multiple of $3K$** uniforms total.
* **Poisson (inversion):** variable, logged exactly.
* **Poisson (PTRS):** multiples of **3** per attempt; logged exactly.
* **ZTP:** sum of underlying Poisson attempts per rejection; logged exactly.

**Envelope invariants:**

* `draws` equals the number of **64-bit words** consumed in that event.
* Counters advance by exactly `ceil(draws/2)` Philox **blocks** (since a block yields two 64-bit words).
* `rng_counter_after` ≥ `rng_counter_before` lexicographically; non-consuming events keep them equal.

---

## S0.3.10 Determinism & failure semantics

**Must hold for every run:**

1. **Order-invariance:** Results do not change under re-sharding or re-ordering, because every event uses a keyed substream defined by $(\ell,\mathbf{id})$.
2. **Open-interval safety:** All uniforms lie strictly in $(0,1)$.
3. **Budget correctness:** Per-event budgets above are satisfied; gamma/dirichlet **mod-3** rules hold.
4. **No FMA, serial reductions** on ordering-critical arithmetic (S0.8); trigs/logs in binary64.

**Fail the run if:**

* An event’s `draws` disagrees with recomputed draws from envelope counters.
* Any sampler produces NaN/Inf.
* A “non-consuming” event changes counters.
* A gamma/dirichlet event violates the **mod-3** draw discipline.

---

## Reference pseudocode (language-agnostic)

```text
# -- Philox interface --
struct Stream { key: u64, ctr: u128 }  # ctr is (hi64, lo64) logically
fn philox_block(s: Stream) -> (u64,u64, Stream) {
  (x0,x1) = PHILOX_2x64_10(s.key, s.ctr)
  s.ctr += 1
  return (x0,x1,s)
}

# -- u01 open interval --
fn u01(x: u64) -> f64 { (x as f128 + 1.0) / (2^64 + 1.0) }  # conceptually; implement in f64 carefully

# -- Box–Muller (one Z, no cache) --
fn normal(stream: &mut Stream) -> (f64, draws:int) {
  (x0,x1,*stream) = philox_block(*stream)
  u1 = u01(x0); u2 = u01(x1)         # 2 uniforms
  r = sqrt(-2.0 * ln(u1))
  theta = TAU * u2
  return (r * cos(theta), 2)
}

# -- Gamma(alpha,1) with fixed-block accounting --
fn gamma_mt(alpha: f64, stream: &mut Stream) -> (f64, draws:int) {
  if alpha >= 1.0 {
    d = alpha - 1.0/3.0; c = 1.0/sqrt(9.0*d)
    loop:
      (z, dZ) = normal(stream)       # dZ = 2 uniforms
      v = (1.0 + c*z)
      v = v*v*v
      if v <= 0.0 { continue }
      (x0,_,*stream) = philox_block(*stream); u = u01(x0)  # +1 uniform
      if ln(u) <= 0.5*z*z + d - d*v + d*ln(v) {
        return (d*v, dZ + 1)          # total is 3 per attempt
      }
  } else {
    (y, dY) = gamma_mt(alpha + 1.0, stream)   # multiple of 3
    (x0,_,*stream) = philox_block(*stream); u = u01(x0)    # +1
    # burn two dummies to keep mod-3 discipline
    (_,_,*stream) = philox_block(*stream)                  # +2
    return (y * pow(u, 1.0/alpha), dY + 3)                 # still multiple of 3
  }
}

# -- Poisson scaffolding (sketch) --
fn poisson(lambda: f64, stream: &mut Stream) -> (int, draws:int) {
  if lambda < 10.0 {
    L = exp(-lambda); k = 0; p = 1.0; draws = 0
    loop:
      (x0,_,*stream) = philox_block(*stream); u = u01(x0); draws += 1
      p *= u; if p <= L { return (k, draws) } else { k += 1 }
  } else {
    # PTRS-like: each attempt ~ (Z,u) => 3 uniforms (2 for Z, 1 for u)
    # repeat until accepted; count draws accordingly.
  }
}
```

---

## What S0.3 guarantees to downstream states

* Any module can declare a substream label $\ell$ and entity IDs $\mathbf{id}$; it then gets a **stable, independent** random stream unaffected by execution order.
* All samplers have **pinned** budgets (constant where possible; fully logged where variable).
* Auditability is total: given the envelopes and `(seed, parameter_hash, manifest_fingerprint, run_id)`, every draw can be replayed exactly.

---

**Summary:** S0.3 nails the stochastic bedrock for 1A. We fix the engine (Philox 2×64-10), make substreams **keyed & order-invariant**, map bits to **(0,1)** safely, specify **Box–Muller**, **Gamma with mod-3 draw discipline**, **Poisson** regimes, and codify **draw accounting** so audits and replay are deterministic down to each 64-bit word.

---

# S0.4 — Deterministic GDP Bucket Assignment (normative)

## Purpose

Attach to every merchant $m$ two **deterministic**, **non-stochastic** features from pinned references:

* $g_c$ — GDP-per-capita level for the merchant’s **home** country $c$ from the **2025-04-15** vintage World Bank WDI extract, and
* $b_m\in\{1,\dots,5\}$ — the **Jenks** $K{=}5$ GDP bucket id for that home country from the **precomputed** mapping table.

No RNG is consumed here. S0.4 is a pure function of the loaded bytes fixed by S0.1–S0.2.

---

## Inputs & domains (read-only)

* `merchant_ids` (authoritative seed), carrying `merchant_id`, `mcc`, `channel`, `home_country_iso`. `home_country_iso` must be ISO-2; FK validated against the canonical ISO table.
* **GDP vintage**: `world_bank_gdp_per_capita_20250415` (version `2025-04-15`) providing a total function
  $G:\mathcal{I}\rightarrow\mathbb{R}_{>0}$. Schema enforces non-null, one value per `(country_iso, observation_year)`.
* **Bucket map**: `gdp_bucket_map_2024` providing a total function
  $B:\mathcal{I}\rightarrow\{1,2,3,4,5\}$, precomputed by Jenks $K{=}5$ over the pinned GDP vintage. Primary key `country_iso`; `bucket ∈ {1..5}`. **Not recomputed online.**

> Both reference artefacts are listed in the dictionary/registry as run-time, read-only inputs (and therefore folded into the manifest fingerprint by S0.2).

---

## Canonical definition (what S0.4 does)

Let $m\in\mathcal{M}$ with home ISO $c=\texttt{home_country_iso}(m)\in\mathcal{I}$. Then

$$
g_c \leftarrow G(c)\in\mathbb{R}_{>0},\qquad
b_m \leftarrow B(c)\in\{1,2,3,4,5\}.
$$

These are **lookups** only; the bucket boundaries are **not** computed at run-time.

---

## Semantics & usage (downstream expectations)

* $b_m$ (Jenks bucket) appears **only** in the hurdle design as five one-hot dummies (column order frozen by the fitting bundle). $\log g_c$ appears **only** in NB dispersion. (As documented in the S0 design sections that consume S0.4 outputs.)
* If you materialise these features, they live inside the model design artefact(s) under `…/parameter_hash={parameter_hash}/` and are schema-governed in `schemas.1A.yaml` (e.g., `#/model/hurdle_design_matrix`, `#/model/hurdle_pi_probs`), but they are commonly carried transiently into S0.5.

---

## Determinism & numeric policy (ordering-sensitive details)

* **No randomness**; S0.4 must yield identical results across shards and runs with the same `manifest_fingerprint`.
* **Binary64 arithmetic** for any derived transforms (e.g., $\log g_c$ in S0.5); no FMA on ordering-critical code paths (per S0.8).
* **Open/closed rule (for intuition only):** if you rebuild $B$ (CI only), the notional thresholds $\tau_0<\dots<\tau_5$ satisfy
  $B(c)=k \iff G(c)\in(\tau_{k-1},\tau_k]$. **Right-closed** prevents ambiguity when $G(c)$ equals a break value. (Authoritative truth is still the table $B$, not $\tau$).

---

## Failure semantics (abort codes; zero tolerance)

Abort S0 with a clear message and a diff hint if any of the following occur:

* `E_HOME_ISO_FK(m,c)`: `home_country_iso` not in the canonical ISO set $\mathcal{I}$. (Upstream contract from S0.1.)
* `E_GDP_MISSING(c)`: no GDP value at the **2025-04-15** vintage for `c`.
* `E_GDP_NONPOS(c, g_c)`: GDP value $\le 0$ (schema forbids; double-guard here).
* `E_BUCKET_MISSING(c)`: no bucket row for `c` in `gdp_bucket_map_2024`.
* `E_BUCKET_RANGE(c, b)`: bucket outside $\{1,\dots,5\}$. (Schema forbids; double-guard.)

All errors must identify the **offending dataset** and the **expected primary key** to speed forensics.

---

## Validation hooks (what CI/runtime must verify)

1. **Coverage**: every `home_country_iso` in `merchant_ids` has both $G(c)$ and $B(c)$.
2. **FK integrity**: `country_iso` in the bucket and GDP tables are members of the run’s ISO set.
3. **Immutability evidence**: both artefacts appear in the S0.2 `manifest_fingerprint` enumeration (count and digests logged).
4. **Optional rebuild check (CI only, non-runtime)**: recompute Jenks $K{=}5$ breaks from the pinned GDP vector and assert the rebuilt mapping equals `gdp_bucket_map_2024`. If not, fail with a per-ISO diff. (Spec below.)

---

## Optional rebuild spec for $B$ (CI only; not used at runtime)

**Objective:** Find monotone thresholds $\tau_0=-\infty<\tau_1<\dots<\tau_5=+\infty$ minimising the total within-class sum of squares (Jenks natural breaks, **optimal** DP solution), over the multiset $\{G(c)\mid c\in\mathcal{I}\}$.

**Rebuild algorithm (exact, deterministic):**

1. Construct the sorted vector $y_1\le \dots \le y_n$ of GDP values (include duplicates; stable sort by `(value, iso)` lexicographic to make tie-breaks deterministic).
2. Precompute prefix sums $S_k=\sum_{i=1}^k y_i$ and $Q_k=\sum_{i=1}^k y_i^2$.
3. For classes $j=1..5$, run the standard **optimal 1-D $k$-means DP** (a.k.a. Jenks DP):
   $\text{SSE}(a..b)=Q_b-Q_{a-1}-\frac{(S_b-S_{a-1})^2}{b-a+1}$.
   Let $D[b,j]=\min_{a\in[j..b]} D[a-1,j-1]+\text{SSE}(a..b)$ with $D[*,1]=\text{SSE}(1..*)$. Keep backpointers $P[b,j]$ giving the optimal split index.
4. Backtrack at $(b{=}n,j{=}5)$ to obtain split indices $t_1 < \dots < t_4$.
5. Set thresholds by values, using **right-closed** classes:
   $\tau_1=y_{t_1}, \tau_2=y_{t_2}, \tau_3=y_{t_3}, \tau_4=y_{t_4}$.
6. Define $B(c)=k$ iff $G(c)\in(\tau_{k-1},\tau_k]$. In case multiple optimal solutions exist due to flat regions (ties), choose the **lexicographically smallest** $(t_1,\dots,t_4)$ by preferring earlier split indices at each DP tie.
7. Emit a deterministic diff if any `country_iso` maps to a different $k$ than the shipped `gdp_bucket_map_2024`.

This spec fixes all ambiguities (ties, stable sorting, right-closed intervals, lexicographic tie-break), so the CI rebuild is bit-stable under IEEE-754 binary64. (Runtime still uses the **shipped** $B$.)

---

## Reference routine (language-agnostic; runtime path)

```text
function S0_4_attach_gdp_features(M, I, G, B):
  # Inputs:
  #   M: table merchant_ids (merchant_id, mcc, channel, home_country_iso)
  #   I: ISO-2 set (canonical)
  #   G: map ISO -> R>0 from 2025-04-15 vintage
  #   B: map ISO -> {1..5} from gdp_bucket_map_2024
  # Output: iterator of (merchant_id, g_c, b_m)

  for row in M:
      m = row.merchant_id
      c = row.home_country_iso

      assert c in I, E_HOME_ISO_FK(m,c)

      g = G.get(c)        # must exist; > 0
      if g is None: raise E_GDP_MISSING(c)
      if not (g > 0.0): raise E_GDP_NONPOS(c, g)

      b = B.get(c)        # must exist; in 1..5
      if b is None: raise E_BUCKET_MISSING(c)
      if not (1 <= b <= 5): raise E_BUCKET_RANGE(c, b)

      yield (m, g, b)     # carried into S0.5 designs (and/or cached)
```

---

## Complexity & concurrency

* **Time:** $O(|\mathcal{M}|)$ hash-map lookups; **Space:** $O(1)$ per row streaming.
* **Parallelism:** embarrassingly parallel across merchants; determinism holds because the mapping is pure and run-pinned.
* **I/O:** inputs are memory-mapped/streamed; the GDP and bucket tables are small (|𝕀| scale) and cached read-only for the run.

---

## Lineage & partitions (where these matter)

* Both `world_bank_gdp_per_capita_20250415` and `gdp_bucket_map_2024` are enumerated artefacts contributing to `manifest_fingerprint`; **changing either flips the fingerprint** and thus the egress partition for the run.
* If features are materialised into model inputs, they are **parameter-scoped** and therefore partitioned by `parameter_hash={parameter_hash}` per dictionary policy for model artefacts.

---

**Bottom line:** S0.4 is a strict, zero-RNG lookup step that attaches $(g_c,b_m)$ from the pinned GDP vintage and the precomputed Jenks $K{=}5$ map. We specify exact domains, FK/coverage checks, CI rebuild rules (deterministic DP Jenks) and failure semantics. With this, downstream S0.5+ can treat the GDP level and bucket as immutable, reproducible inputs.

---

# S0.5 — Design Matrices (Hurdle & NB), Column Discipline, and Validation (normative)

## Purpose & scope

Construct **deterministic, column-aligned design vectors** for each merchant $m$ for:

* the **hurdle logistic** (single vs multi) used in **S1**, and
* the **Negative-Binomial (NB)** branch used in **S2** (mean and dispersion links).

Column dictionaries and ordering are **frozen by the model-fitting bundle** and **not recomputed online**.

---

## Inputs (read-only; all pinned by S0.1–S0.4)

* From **ingress**: $(\texttt{merchant_id}, \texttt{mcc}, \texttt{channel}, \texttt{home_country_iso})$ per merchant, schema-validated earlier. Channels are in $\{\mathrm{CP},\mathrm{CNP}\}$.
* From **S0.4**: $g_c=G(c)>0$ (GDP per-capita for home ISO $c$) and **Jenks $K{=}5$ bucket** $b_m=B(c)\in\{1,\dots,5\}$. These are **lookups** only.
* From the **model-fitting bundle** (frozen artefacts):

  * One-hot **column dictionaries** fixing the **column order** for:

    * MCC dummies (size $C_{\mathrm{mcc}}$),
    * Channel dummies (size 2, for CP/CNP),
    * GDP-bucket dummies (size 5, for buckets 1..5).
  * **Coefficient vectors**:

    * **Hurdle** coefficients $\beta$ in **one YAML vector** containing intercept, MCC, channel, and **all 5 GDP-bucket dummies** (atomic load).
    * **NB dispersion** coefficients (includes the slope on $\log g_c$; NB mean **excludes** GDP bucket by design).

> Design rule (must hold globally): **GDP bucket** appears **only** in the hurdle design; $\log g_c$ appears **only** in the NB dispersion design.

---

## Encoders (deterministic one-hots; column-frozen)

Define one-hot encoders (exact domains & sizes):

$$
\phi_{\mathrm{mcc}}:\mathbb{N}\rightarrow\{0,1\}^{C_{\mathrm{mcc}}},\quad
\phi_{\mathrm{ch}}:\{\mathrm{CP},\mathrm{CNP}\}\rightarrow\{0,1\}^{2},\quad
\phi_{\mathrm{dev}}:\{1,\dots,5\}\rightarrow\{0,1\}^{5}.
$$

* Each encoder returns a vector with **exactly one** entry equal to 1.
* **Column order is frozen** by the fitting dictionaries (shipped with the coefficients) and is **not** recomputed at runtime.
* The **intercept** is always the leading scalar 1.

*(Channel vocab for logging events is later canonicalised to strings like `"card_present"` / `"card_not_present"`; here the encoder domain remains $\{\mathrm{CP},\mathrm{CNP}\}$.)*

---

## Design vectors (definitions, dimensions, and strict ordering)

Let $c=\texttt{home_country_iso}(m)$, $g_c>0$, $b_m\in\{1,\dots,5\}$.

### Hurdle (logit) design

$$
\boxed{\,x_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m),\ \phi_{\mathrm{dev}}(b_m)\big]^\top\,}\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}.
$$

Link and probability:

$$
\eta_m=\beta^\top x_m,\qquad \pi_m=\sigma(\eta_m)=\tfrac{1}{1+e^{-\eta_m}}.
$$

All hurdle coefficients (including the 5 GDP-bucket dummies) live together in **one** YAML vector $\beta$.

### Negative-Binomial (used in S2)

$$
\boxed{\,x^{(\mu)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m)\big]^\top\,}\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2},
$$

$$
\boxed{\,x^{(\phi)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m),\ \log g_c\big]^\top\,}\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+1}.
$$

**Design rule:** bucket dummies are **excluded** from NB mean; $\log g_c$ is **included** in dispersion (with positive fitted slope).

---

## Safe logistic evaluation (overflow-stable)

Implement $\sigma(\eta)$ using the branch-stable identity:

$$
\sigma(\eta)=
\begin{cases}
\frac{1}{1+e^{-\eta}},& \eta\ge 0,\\[4pt]
\frac{e^{\eta}}{1+e^{\eta}},& \eta<0.
\end{cases}
$$

Optional: clip $|\eta|>40$ **only for display/logging** (not for computation) so that $\pi$ saturates to $\{0,1\}$ without NaNs.

---

## Determinism & numeric policy (ordering-critical)

* **No randomness** in S0.5; output depends only on pinned dictionaries and S0.4 features.
* Use IEEE-754 **binary64**; on ordering-critical paths (e.g., any later normalisations depending on these features) **disable FMA** and use **serial reductions** with fixed order—per S0.8 policy. These toggles are part of the artefact set and flip the fingerprint if changed.

---

## Persistence (optional caches) & partitions

S0.5 usually holds $x_m, x^{(\mu)}_m, x^{(\phi)}_m$ **in memory**. If you materialise:

* `hurdle_design_matrix` under `…/parameter_hash={parameter_hash}/…` with schema in `schemas.1A.yaml#/model/hurdle_design_matrix`.
* Optional diagnostics: `hurdle_pi_probs` under `…/parameter_hash={parameter_hash}/…` with schema `#/model/hurdle_pi_probs` (never used by samplers).

*(These are **parameter-scoped** caches; partitioning and schema references are dictionary-backed.)*

---

## Validation hooks (must pass)

1. **Column alignment:** $\text{len}(\beta)=\dim(x_m)$ and column orders of MCC, channel, bucket dummies **match** the frozen dictionaries. **Any** drift is a hard error. (S1 explicitly aborts on design/coeff mismatch at use.)
2. **One-hot correctness:** each encoder emits exactly one “1”.
3. **Feature domains:** $g_c>0$, $b_m\in\{1,\dots,5\}$ (from S0.4).
4. **Scope split:** **Bucket dummies only in hurdle**; $\log g_c$ **only in dispersion**—checked by the builder to prevent accidental leakage.
5. **Partition lint (if persisted):** any materialised dataset uses the **parameter-scoped** partition and embeds the same `parameter_hash` in rows (dictionary contract).

---

## Failure semantics (abort S0; precise codes)

* `E_DSGN_UNKNOWN_MCC(mcc)`: MCC absent from the fitting dictionary (should not happen if ingress dictionary is aligned).
* `E_DSGN_UNKNOWN_CHANNEL(ch)`: channel not in $\{\mathrm{CP},\mathrm{CNP}\}$.
* `E_DSGN_SHAPE_MISMATCH(exp_dim, got_dim)`: $\dim(\beta)\neq \dim(x_m)$ or dictionary sizes drift. (S1 would also abort on this when forming $\eta_m$.)
* `E_DSGN_DOMAIN_GDP(g)`: $g_c\le 0$ (double guard; S0.4 should have already enforced).
* `E_PARTITION_MISMATCH(id, path_key, embedded_key)`: if persisted, the `parameter_hash` embedded in rows must equal the directory key—otherwise fail.

---

## Reference algorithm (language-agnostic)

```text
function S0_5_build_designs(M, dict_mcc, dict_ch, dict_dev5, beta_hurdle, nb_dispersion_coef, G, B):
  # Inputs:
  #   M: merchant_ids rows (merchant_id, mcc, channel, home_country_iso)
  #   dict_mcc: ordered list of MCC category keys (size C_mcc) -> column positions
  #   dict_ch:  ordered list ["CP","CNP"] -> column positions (size 2)
  #   dict_dev5: ordered list [1,2,3,4,5] -> column positions (size 5)
  #   beta_hurdle: YAML vector (len = 1 + C_mcc + 2 + 5)
  #   nb_dispersion_coef: YAML vector (len = 1 + C_mcc + 2 + 1)
  #   G: ISO -> g_c > 0            (from S0.4)
  #   B: ISO -> b_m in {1..5}      (from S0.4)

  assert len(beta_hurdle) == 1 + len(dict_mcc) + 2 + 5, E_DSGN_SHAPE_MISMATCH
  assert dict_ch == ["CP","CNP"], E_DSGN_UNKNOWN_CHANNEL

  for r in M:
      m := r.merchant_id
      c := r.home_country_iso
      g := G[c];   if not (g > 0):   raise E_DSGN_DOMAIN_GDP(g)
      b := B[c];   if b not in {1,2,3,4,5}: raise E_DSGN_DOMAIN_BUCKET(b)

      # One-hots (positions from frozen dictionaries)
      h_mcc = one_hot(dict_mcc.index_of(r.mcc), len(dict_mcc))     # throws if unknown -> E_DSGN_UNKNOWN_MCC
      h_ch  = one_hot(dict_ch.index_of(r.channel), 2)              # CP/CNP only
      h_dev = one_hot(dict_dev5.index_of(b), 5)

      # Designs (strict order)
      x_hurdle = [1] + h_mcc + h_ch + h_dev
      x_nb_mu  = [1] + h_mcc + h_ch
      x_nb_phi = [1] + h_mcc + h_ch + [log(g)]

      # Emit / cache as needed (parameter-scoped if persisted)
      yield (m, x_hurdle, x_nb_mu, x_nb_phi)
```

---

## Complexity & concurrency

* **Time:** $O(|\mathcal{M}|)$ with constant work per row.
* **Space:** streaming construction; one merchant at a time.
* **Parallelism:** embarrassingly parallel across merchants; determinism holds because dictionaries and S0.4 lookups are fixed.

---

## How S0.5 connects downstream

* **S1 consumes** $(x_m,\beta)$ to compute $\eta_m$ and draw/record the Bernoulli hurdle event (audited). S1 will **abort** if the design/coefficients shape or order is inconsistent.
* **S2 consumes** $(x_m^{(\mu)},x_m^{(\phi)})$ for NB mean/dispersion; all RNG usage there is tracked with the S0.3 envelope/trace rules.

---

**Summary:** S0.5 deterministically builds the **exact** hurdle and NB design vectors with **frozen** column order and strict domain checks, no RNG. It enforces the global design rule (bucket dummies only in hurdle; $\log g_c$ only in dispersion), guarantees shape/ordering alignment with the shipped coefficients, and—if you persist—binds everything to the **parameter-scoped** partitioning contract. This makes S1/S2 reproducible and auditable end-to-end.

---

# S0.6 — Cross-border Eligibility (deterministic gate, normative)

## Purpose

Decide, **without randomness**, whether each merchant $m$ is permitted to attempt cross-border expansion later in the journey (i.e., enter S4–S6). Persist exactly one row per merchant to the parameter-scoped dataset **`crossborder_eligibility_flags`** with fields `(merchant_id, is_eligible, reason, rule_set, manifest_fingerprint)`. This dataset is read by S3 to branch the journey; S3 does not modify it.  

---

## Inputs (read-only; pinned earlier)

* **Merchant tuple** $t(m)=(\texttt{mcc}_m,\texttt{channel}_m,\texttt{home_country_iso}_m)$ from `merchant_ids` (S0.1).
* **Parameter bundle:** `crossborder_hyperparams.yaml` (governed by `parameter_hash`; contains the eligibility rule set as specified below).
* **Lineage keys:** `parameter_hash`, `manifest_fingerprint` (S0.2).
* **Schema & dictionary contracts:**

  * Dataset: `crossborder_eligibility_flags` → partitioned by `{parameter_hash}`, schema `schemas.1A.yaml#/prep/crossborder_eligibility_flags`. 

No RNG is consumed in S0.6.

---

## Output (authoritative)

Write one row per merchant $m$ to:

```
data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/part-*.parquet
```

with columns and constraints exactly per schema:

* `merchant_id` (PK),
* `is_eligible` (boolean),
* `reason` (nullable string: the decisive rule label or fallback),
* `rule_set` (non-null string identifying the rule bundle/version),
* `manifest_fingerprint` (hex64).

---

## Domains & symbols

* Channels $\mathcal{C}=\{\mathrm{CP},\mathrm{CNP}\}$.
* Countries $\mathcal{I}$: ISO-3166 alpha-2 set (S0.1).
* MCC set $\mathcal{K}$: 4-digit merchant category codes.
* Merchant map $t(m)\in\mathcal{K}\times\mathcal{C}\times\mathcal{I}$ defined in S0.1.

---

## Rule family (configuration semantics)

All eligibility rules live in **`crossborder_hyperparams.yaml`** under a top-level object:

```yaml
eligibility:
  rule_set_id: "eligibility.v1.2025-04-15"
  default_decision: "deny"         # "allow" or "deny"
  rules:
    - id: "sanctions_deny"
      priority: 10                 # smaller = higher precedence inside same decision tier
      decision: "deny"             # "allow"|"deny"
      mcc:     ["*"]               # list of MCCs or "*" (wildcard); ranges allowed as "5000-5999"
      channel: ["CP","CNP"]        # subset of {"CP","CNP"} or "*"
      iso:     ["RU","IR","KP"]    # subset of ISO-2 or "*" (wildcard)
      reason:  "sanctions"
    - id: "card_present_low_risk_allow"
      priority: 50
      decision: "allow"
      mcc:     ["5411","5812","5814","5912"]
      channel: ["CP"]
      iso:     ["*"]
      reason:  "low_risk_cp"
    # ... more rules ...
```

**Validation of the bundle** (done once at load):

* `rule_set_id`: non-empty ASCII; becomes **`rule_set`** column value.
* `default_decision ∈ {"allow","deny"}`.
* Each rule: `id` unique; `priority` integer in $[0, 2^{31}{-}1]$; `decision ∈ {"allow","deny"}`; list fields are either `"*"` or non-empty lists with valid members/ranges. Unknown MCC/ISO or channel outside $\mathcal{C}$ is a hard error.

---

## Set interpretation & matching

Each rule $r$ defines (after expansion of `"*"` and ranges) three sets
$(S_{\!{\rm mcc}}, S_{\!{\rm ch}}, S_{\!{\rm iso}})\subseteq \mathcal{K}\times\mathcal{C}\times\mathcal{I}$ and a decision $d\in\{\textsf{allow},\textsf{deny}\}$.

* **Clause semantics:** $[ [ r ] ] = S_{\!{\rm mcc}}\times S_{\!{\rm ch}}\times S_{\!{\rm iso}}$.
* **A rule “matches”** merchant $m$ iff $t(m)\in [ [ r ] ]$.

Let $\mathcal{R}_{\textsf{allow}}$ and $\mathcal{R}_{\textsf{deny}}$ be the sets of rules by decision.

---

## Conflict resolution & determinism (normative)

When multiple rules match a merchant, the decision and the **reason** are selected by this **total order**:

1. **Decision tier:** `deny` outranks `allow`.
2. **Priority:** lower `priority` outranks higher (e.g., `10` beats `50`).
3. **Tie-break:** lexical order on `id` (ASCII).

Let $\mathrm{best}_{\textsf{deny}}(m)$ be the top-ranked matching deny rule (or `None`), and $\mathrm{best}_{\textsf{allow}}(m)$ the top-ranked matching allow rule (or `None`).

* If $\mathrm{best}_{\textsf{deny}}(m)$ exists → **`is_eligible = false`**, `reason = that.id`.
* Else if $\mathrm{best}_{\textsf{allow}}(m)$ exists → **`is_eligible = true`**, `reason = that.id`.
* Else (no matches) → **`is_eligible = (default_decision == "allow")`**,
  `reason = "default_allow"` or `"default_deny"` accordingly.

This rule makes outcomes **order-invariant** and replayable under any parallelisation.

---

## Algorithm (exact; streaming-safe)

For each merchant row $m$:

1. Obtain $t(m)=(\texttt{mcc},\texttt{channel},\texttt{home_iso})$.
2. Build candidate sets $D=\{\text{deny rules matching }m\}$, $A=\{\text{allow rules matching }m\}$.

   * Matching expands `"*"` to full domain and MCC ranges “a–b” to the integer set $\{a,\dots,b\}$.
3. Choose decision per **Conflict resolution** above; collect `reason`.
4. Emit row:

   ```
   {
     manifest_fingerprint, merchant_id,
     is_eligible: true|false,
     reason: <winning rule id or "default_*">,
     rule_set: eligibility.rule_set_id
   }
   ```
5. Partition write by `parameter_hash` (dataset is parameter-scoped).

**Complexities.** If rules are indexed by channel and home ISO, and MCC ranges are interval-tree indexed, per-merchant matching is $O(\log |\mathcal{R}| + M)$ with small constants; naive is $O(|\mathcal{R}|)$, acceptable at current scale.

---

## Formal specification (decision function)

Let $\prec$ be the strict order on rules defined by the triple key
$(\text{decision}, \text{priority}, \text{id})$ under the mapping `deny` $<$ `allow` for the first component, numeric order for `priority`, ASCII for `id`. For a set $S$ of rules, let $\min_\prec S$ be its best element.

Define:

$$
\mathrm{best}_{\textsf{deny}}(m)=\min\nolimits_\prec\{r\in\mathcal{R}_{\textsf{deny}} \mid t(m)\in[ [ r ] ]\},
$$

$$
\mathrm{best}_{\textsf{allow}}(m)=\min\nolimits_\prec\{r\in\mathcal{R}_{\textsf{allow}} \mid t(m)\in[ [ r ] ]\}.
$$

The eligibility indicator is

$$
\boxed{\
e_m = 
\begin{cases}
0,& \mathrm{best}_{\textsf{deny}}(m)\ \text{exists},\\[2pt]
1,& \mathrm{best}_{\textsf{deny}}(m)=\varnothing\ \land\ \mathrm{best}_{\textsf{allow}}(m)\ \text{exists},\\[2pt]
\mathbf{1}\{\texttt{default_decision}=\text{"allow"}\},& \text{otherwise.}
\end{cases}}
$$

The **reason** is the winning rule’s `id` when matched; otherwise `"default_allow"`/`"default_deny"`.

---

## Determinism & contracts

* **No RNG.** Output depends only on $t(m)$ and the parameter bundle.
* **Schema and partitioning:** rows must conform to `#/prep/crossborder_eligibility_flags` and be stored under `parameter_hash={parameter_hash}`. 
* **Downstream gate:** S3 **reads** `is_eligible` and branches: if 0 → **domestic-only** (skip S4–S6); if 1 → proceed to ZTP of foreign-count (S4).

---

## Failure semantics (abort S0 with precise codes)

At parameter load:

* `E_ELIG_RULESET_ID_EMPTY` — missing/empty `rule_set_id`.
* `E_ELIG_DEFAULT_INVALID` — `default_decision` not in {"allow","deny"}.
* `E_ELIG_RULE_DUP_ID(id)` — duplicate rule id.
* `E_ELIG_RULE_BAD_CHANNEL(id, ch)` — channel not in $\{\mathrm{CP},\mathrm{CNP}\}$.
* `E_ELIG_RULE_BAD_ISO(id, iso)` — ISO not in canonical $\mathcal{I}$.
* `E_ELIG_RULE_BAD_MCC(id, mcc)` — MCC not in $\mathcal{K}$ or bad range.

At evaluation time:

* `E_ELIG_MISSING_MERCHANT(m)` — merchant row missing required fields.
* `E_ELIG_WRITE_FAIL(path, errno)` — failed to persist to the partitioned dataset.
* `E_PARTITION_MISMATCH(path_key, embedded_fp)` — embedded `manifest_fingerprint` mismatches directory fingerprint (should not happen; S0.2 pins it).

All errors **abort S0**; no partial output is acceptable.

---

## Validation & CI hooks

1. **Schema conformance:** every output row matches `#/prep/crossborder_eligibility_flags`.
2. **Coverage:** one and only one row per merchant id (PK uniqueness).
3. **Determinism test:** re-run S0.6 with the same inputs → bit-identical Parquet rows (ignoring file ordering).
4. **Policy lint:** simulate N random merchants drawn from the current ingress distribution and report counts by decision tier (`deny`, `allow`, `default_*`) to detect unintended policy swings during parameter updates.
5. **Dictionary lint:** dataset path and partitioning exactly match dictionary entry.

---

## Reference pseudocode (language-agnostic)

```text
function S0_6_apply_eligibility_rules(merchants, params, manifest_fingerprint, parameter_hash):
  cfg = params["eligibility"]
  rsid = cfg["rule_set_id"]
  default_is_allow = (cfg["default_decision"] == "allow")

  rules = parse_and_expand(cfg["rules"])  # validate: domains, ranges, duplicates
  deny_rules  = index_rules(rules, decision="deny")   # index by (channel, home_iso), MCC ranges
  allow_rules = index_rules(rules, decision="allow")

  writer = open_partitioned_writer(
              dataset="crossborder_eligibility_flags",
              partition={"parameter_hash": parameter_hash})

  for m in merchants:          # stream over merchants; order-independent
      key = (m.mcc, m.channel, m.home_country_iso)

      D = match_rules(deny_rules,  key)   # returns list of (priority, id, reason)
      A = match_rules(allow_rules, key)

      if not empty(D):
          best = min_lex(D)               # (priority asc, id ASCII)
          is_eligible = false
          reason      = best.id
      elif not empty(A):
          best = min_lex(A)
          is_eligible = true
          reason      = best.id
      else:
          is_eligible = default_is_allow
          reason      = "default_allow" if default_is_allow else "default_deny"

      writer.write({
        "manifest_fingerprint": manifest_fingerprint,
        "merchant_id": m.merchant_id,
        "is_eligible": is_eligible,
        "reason": reason,
        "rule_set": rsid
      })

  writer.close()
```

---

## Complexity, concurrency, and I/O

* **Time:** $O(|\mathcal{M}| \cdot \log |\mathcal{R}|)$ with simple indices; $O(|\mathcal{M}| \cdot |\mathcal{R}|)$ naive.
* **Space:** streaming; constant memory apart from indices.
* **Parallelism:** embarrassingly parallel across shards; determinism holds because decisions depend only on $t(m)$ and a static, versioned rule set.

---

## How S0.6 connects downstream

* S3 treats `crossborder_eligibility_flags.is_eligible` as the **sole** branch condition before ZTP. If `false`, $K_m=0$ and the country set later persists as `{home}` only; if `true`, proceed to S4 for foreign-count and then S6 for Gumbel selection and final `country_set` persistence. 

---

**Bottom line:** S0.6 deterministically turns policy into a per-merchant **yes/no** gate, with a stable conflict-resolution order, explicit **reason** strings, and a versioned **rule_set** id. It writes an authoritative, parameter-scoped table that downstream states consume verbatim to control the cross-border branch—no RNG, no ambiguity.

---

# S0.7 — Hurdle π Diagnostic Cache (deterministic, optional, normative)

## Purpose

Materialise a **read-only diagnostics table** with per-merchant logistic-hurdle outputs

$$
(\texttt{merchant_id},\ \eta_m,\ \pi_m),\quad \eta_m=\beta^\top x_m,\ \pi_m=\sigma(\eta_m)\in(0,1),
$$

so that monitoring/validation can inspect the hurdle surface without re-evaluating designs on the hot path. This artefact is **never consulted by samplers**; it is optional and lives under the **parameter-scoped** partition.

* **Dataset id / path / schema:** `hurdle_pi_probs` →
  `data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/` with schema `schemas.1A.yaml#/model/hurdle_pi_probs`.
* **Registry role:** “Logistic-hurdle π (single vs multi) per merchant”. Depends on `hurdle_design_matrix` and `hurdle_coefficients`.

> S0.10 explicitly lists this as **optional** output of S0 (parameter-scoped).

---

## Inputs (frozen by S0.1–S0.5)

* **Design vector** $x_m=[1,\ \phi_{\mathrm{mcc}},\ \phi_{\mathrm{ch}},\ \phi_{\mathrm{dev}}]$ constructed in **S0.5** with column order frozen by the fitting bundle.
* **Hurdle coefficients** $\beta$ loaded atomically from `hurdle_coefficients.yaml` (the single YAML contains all columns of $x_m$).
* **Lineage keys:** `parameter_hash` (partition key) and `manifest_fingerprint` (embedded per row).

No other artefacts are read here; **no RNG** is consumed.

---

## Output (schema, typing, keys)

A Parquet table with **one row per merchant**:

* **Primary key:** `merchant_id`.
* **Partition key:** `parameter_hash` (directory level).
* **Columns (min set):**

  * `manifest_fingerprint` (hex64),
  * `merchant_id` (id64 per ingress schema),
  * `logit` (alias of $\eta_m$; **float32**),
  * `pi` (alias of $\pi_m$; **float32** in $(0,1)$).

Dictionary and registry describe this dataset exactly with the path above and schema ref `#/model/hurdle_pi_probs`; lineage marks it **produced by** 1A’s hurdle fit and **final_in_layer: false**.

---

## Canonical definitions & numerical policy (deterministic)

### Linear predictor and logistic

Let $\eta_m = \beta^\top x_m$ with the **exact** column order from the fitting bundle (validated in S0.5). Logistic map is evaluated with the **overflow-stable branch**:

$$
\sigma(\eta)=
\begin{cases}
\dfrac{1}{1+e^{-\eta}}, & \eta\ge 0,\\[6pt]
\dfrac{e^{\eta}}{1+e^{\eta}}, & \eta<0.
\end{cases}
\quad\Rightarrow\quad \pi_m=\sigma(\eta_m)\in(0,1).
$$

Arithmetic is IEEE-754 **binary64** for computation; persisted `logit`/`pi` are **narrowed** to float32 using round-to-nearest, ties-to-even. (This narrowing is deterministic and part of the contract.)

### Determinism & scope rules

* **No randomness.** Results depend only on $x_m$ and $\beta$.
* **No side effects.** This artefact **must not** be read by any sampler or allocation routine (it is diagnostics only).
* **Parameter-scoped.** Changing `parameter_hash` (i.e., any governed parameter byte) invalidates the entire table (distinct partition).

---

## Failure semantics (abort S0 with precise codes)

* `E_PI_SHAPE_MISMATCH(exp_dim, got_dim)` — $|\beta|\neq \dim(x_m)$ for the bundle in use (should have been caught in S0.5; double-guard here).
* `E_PI_NAN_OR_INF(m)` — $\eta_m$ or $\pi_m$ is non-finite after evaluation. (Forbidden in S0 failure list.)
* `E_PI_PARTITION(path_key, embedded_hash)` — embedded `parameter_hash` (if embedded) mismatches directory key (dictionary partition contract).
* `E_PI_WRITE(path, errno)` — write failure to the parameter-scoped location.

> On any of the above, **abort S0**; this cache is either wholly correct or not present for the run.

---

## Validation & CI hooks (prove it)

1. **Schema conformance:** table matches `schemas.1A.yaml#/model/hurdle_pi_probs`.
2. **Coverage:** exactly $|\mathcal{M}|$ rows (1 row per merchant id).
3. **Recompute check:** independently recompute $x_m$ (using S0.5’s dictionaries) and $\eta_m,\pi_m$ from the shipped $\beta$; assert bit-equality after float32 narrowing.
4. **Partition lint:** dataset path includes `parameter_hash={parameter_hash}` and no other partition keys; dictionary entry matches.
5. **Downstream isolation:** static analysis / policy test confirms no production code reads `hurdle_pi_probs` in states S1–S9 (it’s diagnostics only).

---

## Algorithm (exact; streaming-safe)

For each merchant row $m\in\mathcal{M}$:

1. Load $x_m$ from S0.5 (or recompute deterministically). Ensure column order matches the fitting dictionary.
2. Compute $\eta_m=\beta^\top x_m$ in **binary64**; compute $\pi_m=\sigma(\eta_m)$ via the branch-stable definition above.
3. Check finiteness; on failure raise `E_PI_NAN_OR_INF(m)`.
4. Narrow to float32 with IEEE round-to-nearest-even: `logit := float32(η_m)`, `pi := float32(π_m)`.
5. Emit row `{ manifest_fingerprint, merchant_id, logit, pi }`.
6. Persist under `data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/…` (dictionary path), Parquet, one file or multiple parts; ordering is unspecified.

**Complexity.** $O(|\mathcal{M}|)$ dot-products; space $O(1)$ streaming; trivially parallel across shards (determinism unaffected).

---

## Reference pseudocode (language-agnostic)

```text
function S0_7_build_hurdle_pi_cache(merchants, beta, dicts, manifest_fingerprint, parameter_hash):
  # dicts carry the frozen column order for MCC, channel, bucket (from S0.5)
  writer = open_partitioned_writer(
             dataset="hurdle_pi_probs",
             partition={"parameter_hash": parameter_hash})

  for m in merchants:
      x = build_x_hurdle(m, dicts)                # deterministic, validated in S0.5
      eta64 = dot_f64(beta, x)                    # binary64 accumulation (fixed order)
      pi64  = logistic_branch_stable(eta64)       # in (0,1)
      if not is_finite(eta64) or not is_finite(pi64):
          raise E_PI_NAN_OR_INF(m.merchant_id)

      row = {
        "manifest_fingerprint": manifest_fingerprint,
        "merchant_id": m.merchant_id,
        "logit": f32(eta64),                      # IEEE round-to-nearest-even
        "pi":    f32(pi64)
      }
      writer.write(row)

  writer.close()
```

---

## How S0.7 connects downstream

* **S1** recomputes $\eta_m,\pi_m$ on the fly to draw the Bernoulli hurdle; it **does not** read this cache. S0.7 exists solely for auditability and exploration.
* **S0.10** lists `hurdle_pi_probs` as an optional S0 product; presence/absence does not affect any later state (fingerprint captures parameters either way).

---

**Bottom line:** S0.7 provides an **optional, parameter-scoped**, **deterministic** snapshot of the hurdle surface $(\eta_m,\pi_m)$ per merchant. It’s fully governed by schema/dictionary, has strict failure and validation hooks, and—crucially—**does not** influence any stochastic step or allocation result.

---

# S0.8 — Numeric Policy & Determinism Controls (normative)

## Purpose

Guarantee that all numerically sensitive computations in 1A are **bit-stable** across machines, builds, and degrees of parallelism. S0.8 defines:

* the **floating-point environment** (format, rounding, subnormals),
* a **deterministic math profile** for `exp/log/sin/cos/atan2/pow`,
* **compiler/runtime flags** forbidding contraction and fast-math,
* **reduction/sorting** rules (fixed order, exact tie-breaks),
* **tolerances** for validation (internal vs external),
* runtime **self-tests** that abort the run if violated.

No randomness is consumed in S0.8; this is configuration + mandatory self-checks.

---

## S0.8.1 Floating-point environment (must hold)

**Format.** IEEE-754 **binary64** (`float64`) for all model computations and comparisons that can affect decisions/order. Persisted diagnostics may downcast (explicitly specified elsewhere).

**Rounding mode.** **Round to nearest, ties to even** (RNE). The run must confirm the mode at startup and fix it process-wide.

**FMA (fused multiply-add).** **Disabled** on any ordering-critical computation (anything that drives a decision, ranking, acceptance test, or integerisation). The build must set flags to prevent contraction (see §S0.8.4). We allow FMA **only** in code paths explicitly marked “non-critical” and never feeding a branch/ordering.

**Subnormals / FTZ / DAZ.** **Disabled** (i.e., subnormals must be honored). FTZ (“flush-to-zero”) and DAZ (“denormals-are-zero”) must be **off**.

**Exceptions.** Floating exceptions are masked (no SIGFPE), but every numeric op must return a finite value. Any NaN/Inf encountered in a model computation is a **hard error** (§S0.8.8).

**Endianness & integer width.** Assumed little-endian. Where endianness matters (e.g., hashing, PRNG message layouts), the spec pins byte order explicitly.

---

## S0.8.2 Deterministic libm profile (math functions)

Most OS libm functions are not bit-stable across platforms. 1A therefore pins a **math profile** for the following functions used anywhere in the layer:
`exp`, `log`, `log1p`, `expm1`, `sqrt`, `sin`, `cos`, `atan2`, `pow`, `tanh`, `erf` (if ever used).

**Normative requirements**

* Implementations **must be bit-identical** across platforms for all inputs in their defined domains.
* `sqrt` must be **correctly rounded** (IEEE requires this already).
* `exp`, `log`, `sin`, `cos`, `atan2`, `pow`, `tanh`, `erf` must be **deterministic** to the last bit (we pin the implementation/version; see build notes).
* Trig arguments are in radians; domain errors (e.g., `log(x≤0)`) must **never occur** on valid model inputs. If they would, upstream logic must guard them (e.g., open-interval uniforms in Box–Muller ensure `ln(u)` is well-defined).

**Operationalisation**

* Vendor a deterministic math library or table-driven approximations as part of the runtime and expose them through a sealed namespace (e.g., `mlr_math::exp`).
* Disallow the system toolchain from inlining different libm variants.
* Record **`math_profile_id`** (string/semver) in the run manifest and fold it into the **manifest fingerprint** inputs for complete lineage (if you change the math profile, partitions flip).

---

## S0.8.3 Reduction, accumulation & linear algebra

**Sums and dot-products.**

* Use **serial, fixed-order** accumulation (iteration order is the natural data order or an explicitly documented stable order).
* Use **Neumaier** (or Kahan) compensated summation for all dot-products and totals that feed decisions/ordering. Keep the same algorithm consistently across builds.
* Do **not** parallel-reduce with dynamic chunking for decision-critical numbers. If parallel throughput is required for non-critical metrics, use a **fixed topology** pairwise tree with pinned chunk size and ordering and assert numerically that the result does not affect any downstream branch.

**Products and ratios.**

* Compute products by summing logs only if explicitly specified; otherwise multiply in binary64 with overflow/underflow checks.
* Ratios must check the denominator against zero with a **strict** epsilon (see tolerances).

**Matrix ops / BLAS.**

* For decision-critical paths, **do not call external BLAS/LAPACK** because of platform variance; use our deterministic scalar kernels (the dimensionalities in 1A are small—design vectors are short). If a future path needs BLAS, you must pin an exact deterministic backend and version and include that in `math_profile_id`.

---

## S0.8.4 Compiler / interpreter flags (build contract)

**C/C++ (examples):**

* `-ffloat-store` (if needed for specific compilers to avoid excess precision on x87—rare on modern x86_64).
* `-fno-fast-math -fno-unsafe-math-optimizations`
* `-ffp-contract=off` (no FMA contraction)
* `-fexcess-precision=standard`
* `-frounding-math` (where supported)
* `-fno-associative-math -fno-reciprocal-math -fno-finite-math-only`

**LLVM/Clang IR:**

* Set `fast-math` flags **off** on all FP ops that affect decisions.
* Mark reduction loops `llvm.experimental.constrained.*` with rounding mode RNE and exceptions masked.

**JIT/VMs (NumPy/Python, JVM, etc.):**

* Disable vectorisation where it could change summation order (e.g., `NUMPY_EXPERIMENTAL_ARRAY_FUNCTION=0` if necessary; avoid `np.sum` on large arrays when order matters—use our scalar kernel).
* Pin `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1` for any accidental BLAS use; for critical code, avoid BLAS entirely.

**GPU (if any):**

* **Do not** offload decision-critical kernels to GPU unless you pin a deterministic math profile and disable fused ops; otherwise, keep them on CPU.

All build settings are recorded in the **run manifest** and folded into the fingerprint enumeration inputs.

---

## S0.8.5 Sorting, comparisons & total order for floats

**Comparisons.**

* For sorting, use a **total order** on floats defined by IEEE-754 `totalOrder`:

  * `-0.0` < `+0.0`;
  * finite numbers by value, then by sign of zero;
  * NaNs are **forbidden**; encountering a NaN is a hard error.

**Tie-breakers.**

* When two keys compare equal under totalOrder, break ties **lexicographically** by a secondary deterministic key (e.g., `ISO` then `merchant_id`). This rule appears in Gumbel ranking and any place we sort candidates.

**Equality & nearly-equal.**

* Use exact equality only where the math guarantees it (e.g., integer counters).
* For “nearly equal” checks, use a **ULP-based** predicate: `ulpDiff(a,b) ≤ 1` where appropriate, never a raw absolute epsilon, unless specifically specified (see tolerances).

---

## S0.8.6 Tolerances & quantisation (when comparisons are externalised)

**Internal computation tolerances** (used in self-tests, not to fudge decisions):

* **Sums/dots:** compare with `ulpDiff ≤ 1` (exactly 1 ULP) when re-deriving in CI with the same math profile.
* **Transcendentals:** exact bit equality required; mismatch is a build/profile violation.

**External comparison tolerances** (for reporting/tests where CSV/decimal I/O may round):

* Accept absolute diff ≤ **1e-6** or relative diff ≤ **1e-6** (whichever larger) when comparing persisted float32 diagnostics to recomputed float64 values downcast to float32.

**Quantisation.**

* Where the spec requires **downcasting** (e.g., S0.7 narrows to float32), the quantisation is IEEE round-to-nearest-even. No other quantisation is allowed unless a state explicitly says so.

---

## S0.8.7 Determinism under concurrency

**Order-invariance by construction.** RNG substreams are keyed (S0.3), so draw sequences are independent of scheduling. S0.8 complements this with **order-stable numeric kernels**:

* Any operation that feeds a sort or a branch must be computed in a **single-threaded** scalar loop with fixed iteration order and Neumaier compensation.
* Map-like operations over merchants may be parallel, **provided** their results are independent per row and do not aggregate into an ordering/threshold without the serial kernel.

**I/O & partitioning.** File emission order is unspecified; content equivalence is defined by row sets. Hashes and fingerprints make partitions unambiguous regardless of file ordering.

---

## S0.8.8 Failure semantics (abort codes)

* `E_NUM_FMA_ON`: FMA contraction detected on a guarded kernel.
* `E_NUM_FTZ_ON`: FTZ/DAZ detected as enabled.
* `E_NUM_RNDMODE`: rounding mode is not nearest-even.
* `E_NUM_LIBM_PROFILE`: math profile version mismatch or non-deterministic libm detected by self-tests.
* `E_NUM_NAN_OR_INF(ctx)`: any model computation produced NaN/Inf (includes trigs/logs).
* `E_NUM_PAR_REDUCE`: a decision-critical reduction executed in parallel or with a non-pinned topology.
* `E_NUM_TOTORDER_NAN`: NaN encountered where total order on floats is required (e.g., sort key).
* `E_NUM_ULP_MISMATCH(func)`: recomputation differs beyond allowed ULP budget.

On any of the above, **abort the run**. S0.8 errors indicate an environment that cannot guarantee reproducibility.

---

## S0.8.9 Self-tests (must run before S1)

At process start (after S0.2; before any RNG draw):

1. **Rounding & FTZ test.**

   * Set and read rounding mode; ensure RNE.
   * Create a subnormal (e.g., `2^-1075`) and multiply by 1; confirm not flushed to 0.
2. **FMA detection.**

   * Evaluate `a*b + c` with values that have different results with/without FMA (known triples). Confirm it **does not** equal the fused result.
3. **libm profile.**

   * Evaluate a fixed regression suite of inputs for `exp/log/sin/cos/atan2/pow` and compare against the vendored deterministic results (bitwise). Fail if any mismatch.
4. **Neumaier audited sum.**

   * Sum a known adversarial sequence (e.g., `[1, 1e-16] * N + [-1] * N`) and verify the result and compensation term match expected deterministic values.
5. **TotalOrder sanity.**

   * Sort a crafted float array including `-0.0`, `+0.0`, large/small magnitudes. Verify order and tie-breakers.

Persist a `numeric_policy_attest.json` into the validation bundle with the pass/fail status and environment hashes.

---

## S0.8.10 Reference kernels (pseudocode)

**Neumaier compensated sum (fixed order)**

```text
def sum_neumaier(xs: iterable<float64>) -> float64:
    s = 0.0
    c = 0.0
    for x in xs:                  # fixed iteration order
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
    s = 0.0
    c = 0.0
    for i in 0..len(a)-1:
        y = a[i]*b[i] - c
        t = s + y
        c = (t - s) - y
        s = t
    return s
```

**Total order comparator for floats (NaNs forbidden)**

```text
def total_order_key(x: float64, secondary) -> tuple:
    # map to sortable tuple: (isNaN, signbit, magnitude_bits, secondary_key)
    assert not isNaN(x)          # NaN -> E_NUM_TOTORDER_NAN
    bits = u64_from_f64(x)
    sign = bits >> 63
    mag  = bits ^ (sign << 63)   # flip sign to make monotone
    # Treat -0.0 < +0.0 explicitly:
    if x == 0.0 and sign == 1: mag = 0 - 1  # ensure (-0.0) sorts before (+0.0)
    return (sign, mag, secondary)
```

---

## S0.8.11 Validation & CI hooks

* **Bitwise CI:** run the self-tests under at least two platforms (e.g., Linux/glibc and Linux/musl) and assert identical outputs.
* **Rebuild sensitivity:** mild refactors must not change any decision-critical outputs; if they do, they must also change the math profile or numeric policy version and hence flip the fingerprint.
* **Partition lint:** confirm `numeric_policy_attest.json` is included in the validation bundle and its hash is listed in the manifest enumeration.

---

## S0.8.12 Interaction with other states

* **S0.3 (RNG).** Validates that Box–Muller, gamma acceptance tests, and Gumbel keys evaluate on the pinned math profile; `log` and trigs are guaranteed stable.
* **S0.5–S2 (design & GLM evals).** Dot products and logistics use Neumaier + branch-stable logistic; results are stable across builds.
* **S6 (ranking).** Any sort over float keys uses the **total order** + deterministic tie-breakers to make rankings bit-stable.

---

**Bottom line:** S0.8 freezes the numeric universe: binary64 + RNE, **no FMA**, **no FTZ**, deterministic libm, fixed-order compensated reductions, and a total-order sort with explicit tie-breaks. It ships with self-tests that abort the run if anything drifts. With S0.8 in place, every downstream state can rely on bit-stable arithmetic and reproducible decisions.

---

# S0.9 — Failure Modes & Abort Semantics (normative)

## Purpose

Define a **single, deterministic** failure contract for 1A so that any violation of schema, lineage, numeric policy, RNG envelope, or partitioning halts the run in a reproducible way, with an actionable forensic payload. The combined state doc already lists the headline items; S0.9 expands them into a full **failure catalog (F1–F10)** and a **run-abort procedure**.

**Scope.** S0.9 governs **all of 1A**, not only S0.\* steps. Where a failure is detected in a later state (S1–S7), it’s still classified by S0.9’s codes (e.g., envelope/partitioning). The combined doc explicitly calls out S0.9 (“Failure modes (all abort)”).

---

## 0) Definitions & severity

* **Run-abort (hard):** Terminates the **entire** 1A run; no further states execute. This applies to structural lineage/schema/numeric violations and to RNG-envelope/trace corruption. (The combined doc marks S0.9 items as “all abort”.)
* **Merchant-abort (soft):** Permitted **only** where a state explicitly defines a per-merchant policy (e.g., ZTP retry exhaustion can “abort merchant” or “downgrade to domestic” per governed policy). This is **not** an S0.9 escape hatch; it exists where the state spec says so (e.g., S4).

---

## 1) Failure catalog (F1–F10)

### (F1) Ingress schema violation (`merchant_ids`)

**Predicate:** row set fails `schemas.ingress.layer1.yaml#/merchant_ids` (types, required fields, PK uniqueness, ISO-2). This is one of the headline S0.9 bullets. **Run-abort.**
**Error:** `ingress_schema_violation(dataset="merchant_ids", row_pk, detail)`.

---

### (F2) Parameter / fingerprint formation failure (S0.2)

Covers the **parameter hash** and **manifest fingerprint** formation that gate all partition keys. These are explicit S0.9 bullets (“Missing artefact or digest mismatch during parameter/fingerprint formation”). **Run-abort.**

* **(F2a) Parameters:** missing/duplicate/unreadable in governed set {`hurdle_coefficients.yaml`,`nb_dispersion_coefficients.yaml`,`crossborder_hyperparams.yaml`} or hash-race during streaming. **Run-abort.**
  **Error:** `param_file_missing|duplicate|unreadable|changed_during_hash(name)`.

* **(F2b) Manifest fingerprint:** empty artefact set, unreadable artefact, invalid git bytes, bad hex persistence. **Run-abort.**
  **Error:** `fingerprint_empty_artifacts|git_bytes_invalid|artifact_unreadable(path)|bad_hex_encoding`.

---

### (F3) Non-finite / out-of-domain features or model outputs

The S0.9 bullets include “Non-finite values in $\eta_m$, $g_c$, or $b_m\notin\{1..5\}$”. These are pure, deterministic lookups/evals; any violation is unrecoverable. **Run-abort.**

* **(F3a) GDP & bucket (S0.4):** $g_c\le 0$ or NaN/Inf; $b_m\notin\{1..5\}$. **Run-abort.**
  **Error:** `nonpositive_gdp(c, g) | bucket_out_of_range(c, b)`.

* **(F3b) Hurdle eval (S0.5/S0.7):** non-finite $\eta_m$ or $\pi_m$. **Run-abort.**
  **Error:** `hurdle_nonfinite(merchant_id, field)`.

---

### (F4) RNG bootstrap / envelope / draw-accounting failures

The headlines include “RNG audit record not written before first draw; or envelope fields missing in any subsequent event.” S0 & S2 detail the **envelope** and **draws=counters delta** invariants. **Run-abort.**

* **(F4a) Missing audit row:** first RNG event appears without prior `rng_audit_log` (seed, fingerprint, run_id, initial counters). **Run-abort.**
  **Error:** `rng_audit_missing_before_first_draw`.

* **(F4b) Envelope violation:** any RNG event missing required envelope fields (`seed`, `parameter_hash`, `manifest_fingerprint`, pre/post counters, module, substream_label). **Run-abort.**
  **Error:** `rng_envelope_violation(event_path, missing_fields[])`.

* **(F4c) Counter conservation:** `after - before != draws` (128-bit unsigned). **Run-abort.**
  **Error:** `rng_counter_mismatch(label, before, after, draws)`.

* **(F4d) Budget discipline:** per-event expectations breached (e.g., hurdle emits draws=1 when $\pi\in\{0,1\}$). (Budget rules are spelled in S0.3 and per-state invariants like S2.\*.) **Run-abort.**
  **Error:** `rng_budget_violation(event, expected, observed)`.

---

### (F5) Partitioning / lineage mismatch (dictionary-backed)

Writers must use the correct partition **and** embed the same lineage key in rows; validators assert both. This is explicitly documented (examples for parameter-scoped vs egress/validation). **Run-abort.**
**Error:** `partition_mismatch(dataset_id, path_key, embedded_key)`.

---

### (F6) Schema-authority breach

1A’s authority is **JSON-Schema** (specific files); referencing non-authoritative schema (e.g., Avro) or drifting from dictionary refs is a structural error. **Run-abort.**
**Error:** `non_authoritative_schema_ref(dataset_id, observed_ref)`.

---

### (F7) Numeric policy violation (S0.8)

S0.8 pins binary64 + RNE, **FMA-off**, no FTZ/DAZ, serial reductions on ordering paths. Violations invalidate determinism. **Run-abort.**
**Errors:** `numeric_rounding_mode`, `fma_detected`, `ftz_or_daz_enabled`, `parallel_reduce_on_ordering_path`, `libm_profile_mismatch`.

---

### (F8) Event coverage / corridor guarantees (state-specific but classified here)

Later states impose coverage/corridor rules (e.g., NB component coverage, ZTP attempt indexing and exhaustion handling). Violations are **structural**: envelope present but required **event family** missing or inconsistent. **Run-abort** for the run; some states additionally allow **merchant-abort** per policy (e.g., ZTP exhaustion).
**Errors:** `event_family_missing(kind, merchant_id)`, `corridor_breach(kind, metric, value)`.

---

### (F9) Dictionary/path drift (writer/reader)

Paths and lineage semantics are *authoritative* (parameter vs fingerprint partitions, log partitions include `run_id`). Any deviation is structural. **Run-abort.**
**Errors:** `dictionary_path_violation(dataset_id, expected_template, observed_path)`, `log_partition_violation(expected_keys, observed)`.

---

### (F10) I/O integrity & atomics

Non-regular files, short writes, or partial file sets for a dataset instance; lack of atomic commit (e.g., moving a completed tmp dir) → dataset may be partially visible. The writer must **fail the run** and remove/mark the incomplete instance. **Run-abort.** (Implied by partitioning invariants and validator checks.)
**Errors:** `io_write_failure(path, errno)`, `incomplete_dataset_instance(dataset_id, partition)`.

---

## 2) Abort procedure (what happens the instant a failure is detected)

1. **Stop emission** of new events/datasets immediately.
2. **Flush & seal** the validation bundle with:

   * `failure_code`, `state`, `module`, `merchant_id` (optional), and the **forensic payload** (dataset id, offending path/PKs, sizes/mtimes, expected vs observed digests/counters).
3. **Mark incomplete outputs** in the working directory and either:

   * delete temp dirs; or
   * write a `_FAILED.json` sentinel alongside the partition root that contains the forensic payload.
4. **Do not** emit any further RNG events (the audit/trace must **not** advance counters after the failure point).
5. Exit with a non-zero status code; the orchestrator records the failure and halts downstream tasks.

---

## 3) Validator responsibilities (what the harness proves)

* **Ingress schema conformance** (`merchant_ids`).
* **Lineage recomputation**: independently recompute `parameter_hash` and `manifest_fingerprint` and assert equality to logged values; error out on missing/empty artefact sets.
* **Envelope completeness & counter conservation** for **every** RNG event; reconcile `draws` with `after-before`.
* **Budget & coverage checks** for state-specific families (e.g., NB has two component events per attempt then one final; ZTP has its rejection/exhaustion shape).
* **Partition equivalence**: path template vs embedded lineage keys; logs use `{seed,parameter_hash,run_id}`, parameter-scoped use `{parameter_hash}`, egress/validation use `{fingerprint}` (and often `seed`).
* **Numeric policy attestation**: run S0.8 self-tests and abort on mismatch (RNE, no FMA/FTZ, deterministic libm).

---

## 4) Error code schema (structured, machine-actionable)

Every failure MUST emit a JSON object like:

```json
{
  "failure_code": "rng_counter_mismatch",
  "state": "S2",
  "module": "nb_sampler",
  "dataset_id": "logs/rng/events/poisson_component",
  "merchant_id": "m_0065F3A2",
  "detail": {
    "before": {"hi": "...", "lo": "..."},
    "after":  {"hi": "...", "lo": "..."},
    "draws":  "..."
  },
  "parameter_hash": "<hex64>",
  "manifest_fingerprint": "<hex64>",
  "seed": 1234567890,
  "run_id": "<hex32>",
  "ts_utc": 1723700000123456789
}
```

This mirrors the envelope/lineage keys present elsewhere so triage is reproducible. (The combined doc requires envelope presence and log partitioning by `{seed,parameter_hash,run_id}`; the same keys are attached to failures.)

---

## 5) Where to detect each failure (first line of defense)

| Failure                         | First detector (preferred)         | Secondary                       |
|---------------------------------|------------------------------------|---------------------------------|
| F1 ingress schema               | S0.1 loader (schema validation)    | Validator pass 1                |
| F2 params/fingerprint           | S0.2 hashing routine               | Validator recompute             |
| F3 features / hurdle non-finite | S0.4/S0.5/S0.7 evaluators          | Validator recompute             |
| F4 envelope / counters          | Event emitters (runtime guards)    | Validator envelope pass         |
| F5 partitioning/lineage         | Dataset writer (path+embed check)  | Validator partition lint        |
| F6 schema authority             | Registry/dictionary linter (build) | Validator schema refs           |
| F7 numeric policy               | S0.8 self-tests                    | Validator re-attest             |
| F8 coverage/corridor            | State invariants (S1/S2/S4/…)      | Validator family coverage       |
| F9 dictionary/path drift        | Writer + dictionary linter         | Validator path lint             |
| F10 I/O atomics                 | Writer’s commit phase              | Validator instance completeness |

(Headlines F1–F4 match the combined S0.9 bullets; S0.9 formalises the rest to avoid ambiguity in production.)

---

## 6) Examples (concrete, minimal)

* **Missing audit row (F4a):** first seen event is `hurdle_bernoulli` but `rng_audit_log` partition has no `run_id=…` file → `rng_audit_missing_before_first_draw` → **Run-abort**. (Envelope/logging rules are pinned in S0.3/S0.2.)

* **Partition mismatch (F5):** writing `outlet_catalogue` under `…/fingerprint=…` but embedding a different `manifest_fingerprint` in rows → `partition_mismatch(outlet_catalogue, path_fp, row_fp)` → **Run-abort**. (Dictionary enforces fingerprint partition for egress.)

* **Non-finite $\eta_m$ (F3b):** safe logistic still returns NaN due to upstream non-finite β or x → `hurdle_nonfinite` → **Run-abort**. (S0.9 headline lists non-finite $\eta_m$ as abort.)

---

## 7) Interaction with other states

* **S1/S2/S4**: Their own failure sections (coverage, corridors, context fields) are **sub-cases** of S0.9 classes F4/F8 and are validated with the same envelope/partition contracts.
* **S0.10**: Outputs must exist **only** when no F1–F10 occurred; S0.10’s lineage/partition summary depends on clean S0.2/S0.3 completions.

---

**Bottom line:** S0.9 codifies a strict, reproducible “**fail fast, fail loud**” policy. The headline S0.9 bullets from the combined doc are made concrete: exactly when we abort, what error codes look like, where they’re detected, how writers/validators enforce partitioning and envelope invariants, and how numeric policy violations are surfaced. With S0.9 in place, any deviation from schema, lineage, RNG discipline, or numeric rules terminates deterministically with a forensic trail you can replay.

---

awesome — here’s **S0.10 at 100% detail**, written so an engineer can implement it verbatim. This final S0 sub-state is the “contracts & packing slip” for everything S0 produces and the lineage you’ll rely on downstream.

---

# S0.10 — Outputs, Partitions & Validation Bundle (normative)

## Purpose

Freeze **what S0 emits**, **how it’s partitioned**, **what lineage keys must be embedded**, and **how we package the attestation bundle** that lets later states (and CI) prove a run is valid. S0.10 is purely contractual: no RNG is consumed and no model numerics are performed here.

---

## S0.10.1 Lineage keys (recap; scope of use)

* **`parameter_hash` (hex64):** partitions **parameter-scoped** artefacts. Changes when any governed parameter file’s bytes change (S0.2.2).
* **`manifest_fingerprint` (hex64):** partitions **egress & validation** artefacts. Changes when any opened artefact, the repo commit, or the parameter bundle changes (S0.2.3).
* **`seed` (u64):** the modelling seed; used in log partitions and to derive RNG streams (S0.3).
* **`run_id` (hex32):** **logs only**; partitions RNG/audit/trace events. Not modelling state (S0.2.4).

**Embedding rule (row-level):**
Where a dataset schema includes `manifest_fingerprint` or `parameter_hash`, the **embedded value must equal** the directory partition key. Mismatch ⇒ S0.9/F5 **run-abort**.

---

## S0.10.2 Artefact classes produced by S0

S0 produces three classes of outputs:

1. **Parameter-scoped model inputs/caches** (deterministic; safe to reuse across runs that share `parameter_hash`):

   * `crossborder_eligibility_flags` (S0.6).
   * `hurdle_pi_probs` (S0.7, **optional** diagnostics).
   * *(Optionally transient and not authoritative: `hurdle_design_matrix`)*.

2. **Lineage & attestation files** (fingerprint-scoped):

   * `validation_bundle_1A` (directory containing the attestation payload; §S0.10.5).
   * `numeric_policy_attest.json` (from S0.8 self-tests), inside the bundle.
   * `parameter_hash_resolved.json` and `manifest_fingerprint_resolved.json`, inside the bundle.
   * `param_digest_log.jsonl` (one row per governed parameter file), inside the bundle.
   * `fingerprint_artifacts.jsonl` (all opened artefacts: path + SHA256), inside the bundle.

3. **RNG audit stub** (created at **start of S0.3**, not S0.10, listed here for partitioning completeness):

   * `rng_audit_log` and `rng_trace_log` are **log-scoped** by `{seed, parameter_hash, run_id}` and **not** part of the parameter- or fingerprint-scoped datasets. S0.10 records this partitioning contract.

---

## S0.10.3 Partitioning & paths (authoritative)

### Parameter-scoped (partition by `parameter_hash`)

* **Dataset:** `crossborder_eligibility_flags`
  **Path:** `data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/part-*.parquet`
  **Schema:** `schemas.1A.yaml#/prep/crossborder_eligibility_flags`
  **Row keys:** `merchant_id` (PK).
  **Embedded lineage:** `manifest_fingerprint` (column), must equal the run’s fingerprint.

* **Dataset (optional):** `hurdle_pi_probs`
  **Path:** `data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/part-*.parquet`
  **Schema:** `schemas.1A.yaml#/model/hurdle_pi_probs`
  **Row keys:** `merchant_id` (PK).
  **Embedded lineage:** `manifest_fingerprint`.

> **Write semantics:** **overwrite-atomic** per partition. Writers must stage to a temp dir and `rename(2)` into the partition root. Partial outputs must never become visible (S0.9/F10).

### Fingerprint-scoped (partition by `fingerprint`)

* **Dataset:** `validation_bundle_1A` (a directory, not Parquet)
  **Path:** `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`
  **Contents:** see §S0.10.5.
  **Embedded lineage:** filenames and JSON fields include `parameter_hash`, `manifest_fingerprint`, `seed`, `run_id` (where applicable).

### Log-scoped (RNG) — for reference

* **Logs:** `rng_audit_log`, `rng_trace_log`, and every `rng_event_*`
  **Path template:** `logs/rng/<stream>/<seed={seed}>/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
  **Envelope:** must carry `{seed, parameter_hash, manifest_fingerprint, run_id, module, substream_label, counter_before/after, draws}` (S0.3.1).
  *(S0.10 doesn’t produce these; it codifies the partition contract.)*

---

## S0.10.4 Immutability, idempotence & retention

* **Immutability:** A materialised dataset instance (a specific partition directory) is **immutable**. Re-runs with the **same keys** must either (a) detect the existing instance and **no-op**, or (b) write a byte-identical instance to a new temp dir and atomically replace; both strategies are acceptable so long as bytes do not change.
* **Idempotence:** With the same inputs and environment profile, S0 reproduces **bit-identical** bytes (apart from file ordering for Parquet row groups, which is **not** part of the contract).
* **Retention:**

  * Parameter-scoped caches: keep last **N** `parameter_hash` generations (team policy; default N=5).
  * Validation bundles: keep **all** `manifest_fingerprint` generations for audit.
  * Log-scoped events: retain per compliance policy (e.g., 90 days), as they’re not modelling state.

---

## S0.10.5 Validation bundle (structure, hashing & “_passed.flag”)

The **validation bundle** is an on-disk directory (or tarball, optional), **fingerprint-scoped**, containing exactly:

```
validation/
  fingerprint={manifest_fingerprint}/
    MANIFEST.json
    parameter_hash_resolved.json
    manifest_fingerprint_resolved.json
    param_digest_log.jsonl
    fingerprint_artifacts.jsonl
    numeric_policy_attest.json
    DICTIONARY_LINT.txt                 # optional, human-readable
    SCHEMA_LINT.txt                     # optional, human-readable
    _passed.flag
```

### MANIFEST.json (normative keys)

```json
{
  "version": "1A.validation.v1",
  "manifest_fingerprint": "<hex64>",
  "parameter_hash": "<hex64>",
  "git_commit_hex": "<hex40-or-64>",   // canonically padded to 64 in hashing step
  "artifact_count": 123,               // # of opened artefacts in fingerprint set
  "math_profile_id": "libm.det.v2.1",
  "compiler_flags": {
    "fma": false, "ftz": false, "rounding": "RNE",
    "fast_math": false, "blas": "none"
  },
  "created_utc_ns": 1723700000123456789
}
```

### parameter_hash_resolved.json

```json
{
  "parameter_hash": "<hex64>",
  "filenames_sorted": [
    "crossborder_hyperparams.yaml",
    "hurdle_coefficients.yaml",
    "nb_dispersion_coefficients.yaml"
  ]
}
```

### manifest_fingerprint_resolved.json

```json
{
  "manifest_fingerprint": "<hex64>",
  "git_commit_hex": "<hex40-or-64>",
  "parameter_hash": "<hex64>",
  "artifact_count": 123
}
```

### param_digest_log.jsonl

JSON Lines; one row per governed parameter file:

```json
{"filename":"hurdle_coefficients.yaml","size_bytes":12345,"sha256_hex":"<hex64>","mtime_ns":17237...}
{"filename":"nb_dispersion_coefficients.yaml","size_bytes":6789,"sha256_hex":"<hex64>","mtime_ns":17237...}
{"filename":"crossborder_hyperparams.yaml","size_bytes":2345,"sha256_hex":"<hex64>","mtime_ns":17237...}
```

### fingerprint_artifacts.jsonl

All artefacts **actually opened** during the run (including the three params), each with its digest:

```json
{"path":".../iso3166_canonical_2024.csv","sha256_hex":"<hex64>","size_bytes":...}
{"path":".../world_bank_gdp_per_capita_20250415.parquet","sha256_hex":"<hex64>","size_bytes":...}
...
```

### numeric_policy_attest.json

Exact pass/fail & fingerprints from S0.8 self-tests:

```json
{
  "rounding_mode":"RNE","ftz":false,"fma":false,
  "libm_profile_id":"libm.det.v2.1",
  "selftests":{"rounding":true,"ftz":true,"fma":true,"libm":true,"neumaier":true,"total_order":true}
}
```

### `_passed.flag` (gating token)

* **Definition:** `_passed.flag` contains the single line
  `sha256_hex = <hex64>`,
  where `<hex64>` is the **SHA-256** over the **canonical byte concatenation** of the **other bundle files in lexicographic filename order**.
* **Purpose:** Downstream readers (e.g., when consuming final egress) **MUST** verify that `sha256(bundle_without_flag) == value in _passed.flag`. This is the **read-gate** in downstream specs: if it doesn’t match, the egress consumer **must not** read and the run is considered invalid.
* **Canonicalisation rules for the hash:**

  * Filenames sorted ASCII (`DICTIONARY_LINT.txt`, `MANIFEST.json`, …, `param_digest_log.jsonl`, …).
  * Each file’s raw bytes concatenated **exactly**; no newline canonicalisation.
  * `_passed.flag` itself is **excluded** from the hash.

> **Why a gate?** The flag proves **bundle completeness** and protects downstream from half-written or tampered validation payloads.

---

## S0.10.6 Writer behaviour (atomicity & lints)

**Atomic write:**

* Writers for parameter-scoped datasets and the validation bundle must write to a temp dir `.../_tmp.{uuid}` and atomically `rename(2)` into the final partition path. On failure, delete the temp dir. Never expose partial contents.

**Dictionary & schema lints (optional files in bundle):**

* `DICTIONARY_LINT.txt`: diff of dataset dictionary vs observed writer paths and schema refs for the run.
* `SCHEMA_LINT.txt`: results of validating every produced dataset against its JSON-Schema anchor.
  These are **informational** and **excluded** from `_passed.flag` only if you explicitly choose so; by default they are **included**.

---

## S0.10.7 Idempotent re-runs & equivalence

Two validation bundles are **equivalent** if:

* Their `MANIFEST.json` objects are identical byte-for-byte **except** for `created_utc_ns`.
* All other files are identical and `_passed.flag` hashes match.
  This defines the equality notion for CI that de-duplicates bundles across re-runs.

---

## S0.10.8 Pseudocode (reference implementation)

```text
function S0_10_emit_outputs_and_bundle(ctx):
  # ctx carries parameter_hash, manifest_fingerprint, seed, run_id, git_commit_hex,
  # math_profile_id, compiler flags, and enumerations produced in S0.2/S0.8

  # 1) Ensure parameter-scoped datasets persisted (S0.6/S0.7 did the writes)
  assert partition_exists("crossborder_eligibility_flags", parameter_hash)
  # hurdle_pi_probs is optional; if configured, assert its partition too.

  # 2) Build validation bundle contents in memory
  MANIFEST = {
    "version": "1A.validation.v1",
    "manifest_fingerprint": ctx.fingerprint,
    "parameter_hash": ctx.parameter_hash,
    "git_commit_hex": ctx.git_commit_hex,
    "artifact_count": len(ctx.artifacts),
    "math_profile_id": ctx.math_profile_id,
    "compiler_flags": ctx.compiler_flags,
    "created_utc_ns": now_ns()
  }

  # Marshal files:
  write_json("MANIFEST.json", MANIFEST)
  write_json("parameter_hash_resolved.json", {
    "parameter_hash": ctx.parameter_hash,
    "filenames_sorted": ctx.param_filenames_sorted
  })
  write_json("manifest_fingerprint_resolved.json", {
    "manifest_fingerprint": ctx.fingerprint,
    "git_commit_hex": ctx.git_commit_hex,
    "parameter_hash": ctx.parameter_hash,
    "artifact_count": len(ctx.artifacts)
  })
  write_jsonl("param_digest_log.jsonl", ctx.param_digests)      # one row/file
  write_jsonl("fingerprint_artifacts.jsonl", ctx.artifact_digests)
  write_json("numeric_policy_attest.json", ctx.numeric_attest)

  # 3) Compute _passed.flag over all files except the flag itself
  files = list_bundle_files()             # lexicographic ASCII order
  concat = b""
  for f in files:
      if f == "_passed.flag": continue
      concat += read_bytes(f)
  h = sha256_bytes(concat)
  write_text("_passed.flag", "sha256_hex = " + hex_lower_64(h) + "\n")

  # 4) Atomic publish under fingerprint partition
  publish_atomic(dir="data/layer1/1A/validation/fingerprint=" + ctx.fingerprint)
```

---

## S0.10.9 Validation (what CI/runtime must assert)

* **Partition lint:** every produced dataset lives under the correct partition (parameter vs fingerprint vs logs); embedded lineage equals directory key.
* **Bundle integrity:** `_passed.flag` matches the hash of the bundle contents; all required files present.
* **Schema conformance:** each dataset matches its JSON-Schema anchor.
* **Lineage recomputation:** recompute `parameter_hash` and `manifest_fingerprint`; assert equality with the `*_resolved.json` files.
* **Numeric attestation:** `numeric_policy_attest.json` shows all S0.8 self-tests passed for the run.

---

## S0.10.10 Downstream consumption rules (what later states must do)

* **Parameter-scoped readers** (e.g., S1/S2/S3) should **only** key by `parameter_hash` and ignore `run_id`.
* **Egress/validation consumers** (e.g., at final hand-off) **must**:

  1. locate the `fingerprint={manifest_fingerprint}` partition;
  2. verify `_passed.flag`;
  3. optionally re-hash `fingerprint_artifacts.jsonl` and `param_digest_log.jsonl` to spot tampering.
     If any check fails, **do not read** and mark the run invalid.

---

**Bottom line:** S0.10 makes S0’s outputs **unambiguous and self-proving**. Parameter-scoped datasets are immutable and keyed by `parameter_hash`; the **validation bundle** is fingerprint-scoped, atomically published, and protected by a `_passed.flag` gate. With these contracts, later states can consume 1A confidently, and CI can prove a run is reproducible and complete.

---