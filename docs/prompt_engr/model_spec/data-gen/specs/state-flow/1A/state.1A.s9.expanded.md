# S9.1 — Scope, inputs, outputs (implementation-ready)

## 1) Purpose (what S9 proves)

For a fixed run lineage $\big(\texttt{seed},\texttt{manifest_fingerprint},\texttt{parameter_hash},\texttt{run_id}\big)$, S9 must prove that 1A’s immutable egress:

1. **conforms to schema**,
2. is **internally consistent** with all upstream 1A artefacts and RNG logs, and
3. is **statistically sane** under governed corridors;

and, on success, emit a **signed validation bundle** and a **`_passed.flag`** that authorise the 1A→1B hand-off **for exactly this** `manifest_fingerprint`.

---

## 2) Identity & authority (inputs are read-only)

### 2.1 Lineage/identity keys (must be present)

* `seed` (u64 master seed), `parameter_hash` (hex64), `manifest_fingerprint` (hex64), `run_id` (opaque run token). These are **inputs to validation** (never rewritten) and scope all lookups below.

### 2.2 Authoritative datasets & where order lives

* **Egress (fingerprint-scoped):**
  `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/` with schema `schemas.1A.yaml#/egress/outlet_catalogue`. **Within-country** sequence only; **inter-country order is intentionally not encoded** here. PK and file ordering are `(merchant_id, legal_country_iso, site_order)`.
* **Country order (parameter-scoped & sole authority):**
  `country_set/seed={seed}/parameter_hash={parameter_hash}/` with schema `#/alloc/country_set`. Column `rank` (0 = home; 1..K = foreign order) is the **only** source of cross-country order. 1B must join it; S9 enforces this separation.
* **Integerisation trail (parameter-scoped):**
  `ranking_residual_cache_1A(seed,parameter_hash)` to reconstruct largest-remainder decisions (residuals in $[0,1)$ and `residual_rank`), and RNG **event** logs (below) to prove replayability.

### 2.3 RNG evidence (run-scoped)

* `rng_audit_log` (master envelope: algo, seed, counter/jump map).
* Structured **event logs** under `schemas.layer1.yaml#/rng/...` for labels used by 1A (e.g., `gumbel_key`, `dirichlet_gamma_vector`, `residual_rank`, `sequence_finalize`), partitioned by `{seed, parameter_hash, run_id}`. Presence, schema conformance, **counter arithmetic**, and **zero-draw** where mandated are validated in S9.

### 2.4 Optional/diagnostic caches (parameter-scoped)

* `hurdle_pi_probs`, `sparse_flag`, `crossborder_eligibility_flags`. Used for corridor checks and coverage diagnostics; they do **not** change egress semantics.

---

## 3) Inputs — exact path/schema contracts (must use)

| Kind               | Path partitioning                                                                                  | Schema pointer / role                                                                                                                     |
| ------------------ | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **Egress**         | `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`                                 | `schemas.1A.yaml#/egress/outlet_catalogue` (PK/order `(merchant_id,legal_country_iso,site_order)`) — **no inter-country order encoded**.  |
| **Country set**    | `country_set/seed={seed}/parameter_hash={parameter_hash}/`                                         | `schemas.1A.yaml#/alloc/country_set` (rank carries cross-country order, `0=home`).                                                        |
| **Residual cache** | `ranking_residual_cache_1A/seed={seed}/parameter_hash={parameter_hash}/`                           | `#/alloc/ranking_residual_cache` (residual $[0,1)$, rank ≥1).                                                                             |
| **RNG events**     | `logs/rng/events/<label>/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` | `schemas.layer1.yaml#/rng/events/<label>` (per-label schema; envelope with before/after counters).                                        |
| **Audit log**      | registry path for `rng_audit_log` (run-scoped)                                                     | envelope that pins master seed/stream map.                                                                                                |

All paths/roles are documented in the **dataset dictionary** and **artefact registry**; S9 must resolve from there rather than hardcoding.

---

## 4) Outputs — what S9 writes & the 1A→1B gate

### 4.1 `validation_bundle_1A` (ZIP)

* **Location:** `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/bundle.zip`.
* **Index:** `index.json` conforming to `schemas.1A.yaml#/validation/validation_bundle` (table with `artifact_id` PK, columns `kind,path,mime,notes`).
* **Minimum contents:** `schema_checks.json`, `key_constraints.json`, `rng_accounting.json`, `metrics.csv`, plus `diffs/*` when mismatches arise.

### 4.2 `_passed.flag` (cryptographic gate)

* **Same folder**; its **file contents equal** `SHA256(bundle.zip)` (lowercase hex).
* **Registry contract:** `validation_passed_flag.digest = {sha256_of_bundle}`, with dependency `validation_passed_flag ← validation_bundle_1A`.

### 4.3 Hand-off condition to 1B (binding)

1B **may read** `outlet_catalogue(seed,fingerprint)` **iff** `_passed.flag` exists for that fingerprint **and** its content hash equals `SHA256(bundle.zip)`. Consumers **must** verify this before access; cross-country order must be recovered **only** via `country_set.rank`.

---

## 5) Boundary invariants fixed by S9.1 (assumed by S9.2+)

* **Scope coherence:** joins pair `outlet_catalogue(seed,fingerprint)` with caches at `(seed,parameter_hash)` and RNG logs at `(seed,parameter_hash,run_id)`. Mixed scopes are invalid.
* **Immutability:** inputs are read-only; S9 writes only under `…/validation/fingerprint={manifest_fingerprint}/`.
* **Single source of country order:** **only** `country_set.rank`; egress never encodes it.

---

## 6) Pre-flight presence & coherence checks (must pass before any deeper validation)

Let $P=(\texttt{seed},\texttt{manifest_fingerprint},\texttt{parameter_hash},\texttt{run_id})$.

1. Exactly one `outlet_catalogue` partition exists at `(seed,fingerprint)`; at least one file present.
2. A matching `country_set` and `ranking_residual_cache_1A` exist at `(seed,parameter_hash)`.
3. Required RNG labels for 1A (per registry) are present for the run under `{seed,parameter_hash,run_id}` (e.g., `dirichlet_gamma_vector`, `residual_rank`, `sequence_finalize`); absence is a **hard S9.1 fail**.
4. Dictionary/registry lookups for schema refs and paths resolve successfully (no stale IDs).

---

## 7) Error taxonomy for S9.1 (machine codes & abort)

| Code                              | Trigger                                                          | Evidence artefact(s)                   |
|-----------------------------------|------------------------------------------------------------------|----------------------------------------|
| `presence_missing_egress`         | Missing/empty `outlet_catalogue(seed,fingerprint)`               | `schema_checks.json` (egress section)  |
| `presence_missing_country_set`    | Missing `country_set(seed,parameter_hash)`                       | `schema_checks.json` (FK base missing) |
| `presence_missing_residual_cache` | Missing `ranking_residual_cache_1A(seed,parameter_hash)`         | `schema_checks.json`                   |
| `presence_missing_rng_streams`    | Any required RNG label absent for `{seed,parameter_hash,run_id}` | `rng_accounting.json` (coverage table) |
| `registry_resolution_error`       | Schema/path cannot be resolved from dictionary/registry          | `schema_checks.json` (registry block)  |

All are **hard-fail** in S9.1; bundle may still be produced later with diagnostics, but `_passed.flag` will not be written.

---

## 8) Reference collector (handles for later S9.x)

```pseudo
function s9_1_collect_handles(seed, fingerprint, parameter_hash, run_id):
    outlet  := read_partition("outlet_catalogue", seed, fingerprint)                      # schemas.1A.yaml#/egress/outlet_catalogue
    cset    := read_partition("country_set", seed, parameter_hash)                         # #/alloc/country_set
    resid   := read_partition("ranking_residual_cache_1A", seed, parameter_hash)           # #/alloc/ranking_residual_cache
    hurdle  := read_param_scoped("hurdle_pi_probs", parameter_hash, optional=true)
    sparse  := read_param_scoped("sparse_flag", parameter_hash)
    xborder := read_param_scoped("crossborder_eligibility_flags", parameter_hash)
    rng_audit := read_run_scoped("rng_audit_log", run_id)
    events := {
       "gumbel_key":            read_events("gumbel_key", seed, parameter_hash, run_id),
       "dirichlet_gamma_vector":read_events("dirichlet_gamma_vector", seed, parameter_hash, run_id),
       "residual_rank":         read_events("residual_rank", seed, parameter_hash, run_id),
       "sequence_finalize":     read_events("sequence_finalize", seed, parameter_hash, run_id)
    }
    assert exists(outlet) and exists(cset) and exists(resid) and exists(rng_audit)
    for label in required_labels: assert exists(events[label])                             # coverage pre-check
    return {outlet,cset,resid,hurdle,sparse,xborder,rng_audit,events}
```

Path templates and required labels are taken from the registry/dictionary; **do not** hardcode.

---

## 9) Conformance tests (must pass for S9.1)

1. **Presence happy-path:** All partitions present; collector returns handles; proceed to S9.2+. ✔︎
2. **Missing RNG stream:** Drop `sequence_finalize` → expect `presence_missing_rng_streams` with coverage table in `rng_accounting.json`. ✔︎
3. **Mixed scopes:** Provide `country_set` at wrong `parameter_hash` → expect registry/scope failure; S9.1 aborts. ✔︎
4. **Egress absent:** No files at `(seed,fingerprint)` → `presence_missing_egress`; no further checks run. ✔︎

---

## 10) Notes for S9.2 (notation) & beyond

S9.2 will bind the symbol table:
$n_{m,i}$ from **row counts** in egress (so $n_{m,i}\ge 0$; note: persisted **rows** always carry `final_country_outlet_count ≥ 1`), $s_{m,i,k}$ and `site_id` bijection (`zpad6`), $R_{m,i}$/$r_{m,i}$ from the residual cache, and the set $\mathcal{I}_m$ + order from `country_set.rank`. These definitions are then used in S9.3–S9.7 for structural checks, RNG accounting, and the bundle.

---

This locks S9.1 at the “100%” level: exact purpose, authoritative inputs with paths/schemas, presence/coherence gates, error taxonomy, a reference collector, the bundle+flag hand-off, and the policy that **only** `country_set.rank` carries cross-country order.

---

# S9.2 — Notation

## 1) Index sets, scope, and partitions (binding)

* **Merchants.** $m\in\mathcal{M}$ (values come from keys present in the inputs for this run).
* **Countries (canonical).** $i\in\mathcal{I}$ = ISO-3166-1 alpha-2 domain from the canonical ingress table referenced by schema FKs.
* **Legal countries for a merchant (sole authority).**

  $$
  \mathcal{I}_m \;=\; \{\, i : (m,i)\in\texttt{country_set}\ \text{at }(seed,\ parameter_hash)\,\},
  $$

  totally ordered by `rank` with $0$ = home. **Cross-country order exists only here**; egress never encodes it.

**Scope discriminants used everywhere in S9.**
Egress is keyed by `(seed, fingerprint)`, allocation caches by `(seed, parameter_hash)`, RNG event logs by `(seed, parameter_hash, run_id)`. S9 joins only across matching scopes; mixed scopes are invalid.

---

## 2) Observables from egress `outlet_catalogue` (per $(m,i,k)$)

Let `OUT` denote the immutable egress partition at
`data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`, schema `schemas.1A.yaml#/egress/outlet_catalogue`. Its **PK and sort keys** are $(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})$; **inter-country order is not encoded** here.

### 2.1 Count and within-country sequence

* **Materialised count** (defined even for zero-blocks):

  $$
  n_{m,i} \;=\; \#\text{rows in OUT where }(\texttt{merchant_id},\texttt{legal_country_iso})=(m,i).
  $$

  If $n_{m,i}=0$, no row for $(m,i)$ exists in egress. If $n_{m,i}\ge 1$, every persisted row must carry the same `final_country_outlet_count = n_{m,i}` (S8 construction contract; S9 re-checks in S9.3/S9.4).

* **Within-country order.** For the $k$-th row of block $(m,i)$,

  $$
  s_{m,i,k}\in\{1,\dots,n_{m,i}\}\ \text{is the value of }\texttt{site_order}.
  $$

  The multiset $\{s_{m,i,k}\}$ must equal $\{1,\dots,n_{m,i}\}$ (gap-free permutation); S9 validates this exactly.

### 2.2 Site identifier & the encoder bijection

* **Encoder.** $\sigma:\mathbb{Z}_{\ge1}\to\{0,1,\dots,9\}^6$, $\sigma(j)=\mathrm{zpad6}(j)$ (left-pad base-10 to width 6). Regex: `^[0-9]{6}$`.
* **ID string on row $k$.** $\text{id}_{m,i,k}=\texttt{site_id}\in\{000000,\dots,999999\}$. For persisted rows, S8 requires $\text{id}_{m,i,k}=\sigma(s_{m,i,k})$; S9 asserts the same. (Capacity guard $n_{m,i}\le 999{,}999$ enforced upstream; overflow aborts S8.)
* **Partial inverse.** $\sigma^{-1}:\texttt{site_id}\mapsto j$ is defined iff the regex matches and $000001\le\texttt{site_id}\le 999999$; then $j$ is the integer value. S9 uses this for diagnostics only (the schema already provides `site_order`).

### 2.3 Merchant-wide constants repeated on rows

* $H_m\in\{0,1\}$ = `single_vs_multi_flag` (boolean).
* $N^{\mathrm{raw}}_m\in\mathbb{Z}_{\ge1}$ = `raw_nb_outlet_draw` (on **all** rows of merchant $m$); S9 later checks conservation $\sum_{i\in\mathcal{I}_m} n_{m,i} = N^{\mathrm{raw}}_m$.
* `home_country_iso` (constant per merchant; must equal the `country_set` row with `rank=0`). `legal_country_iso` = $i$ on the row.
* Lineage echoes: every row carries `manifest_fingerprint` (hex64) and `global_seed` (u64) equal to the partition tokens `(fingerprint, seed)`.

---

## 3) Observables from parameter-scoped caches (allocation trail)

All are read from `(seed, parameter_hash)`.

* **Residuals & their order (largest-remainder trail).**
  $R_{m,i}\in[0,1)$ = `ranking_residual_cache_1A.residual`;
  $r_{m,i}\in\{1,2,\dots\}$ = `ranking_residual_cache_1A.residual_rank` (1 = largest). These support reproducibility of S7’s tie-breaks and are used in S9.4.

* **Optional hurdle probability.** $\pi_m\in[0,1]$ from `hurdle_pi_probs` (diagnostic only; corridors may reference it; omitted if the cache is disabled).

* **(As needed in later checks)** `sparse_flag`, `crossborder_eligibility_flags` at the same scope; they never change egress semantics but appear in corridor/coverage diagnostics.

---

## 4) RNG lineage objects (run-scoped)

* **Audit envelope** $E=(\text{algo},S_{\text{master}},\text{stream map},\text{initial counters},\dots)$ from `rng_audit_log`. Used to verify label→substream mapping and counter arithmetic.
* **Event traces** $T_\ell$ for labels $\ell\in\{$`gumbel_key`, `dirichlet_gamma_vector`, `residual_rank`, `sequence_finalize`, …$\}$: JSONL tuples $(\texttt{rng_counter_before},\texttt{draws},\texttt{rng_counter_after},\texttt{key})$ with a common envelope. Presence, schema conformance, **monotone counter advance**, and **zero-draw** where mandated are asserted in S9.5/S9.6.

---

## 5) Canonical column ↔ symbol table (dataset-backed)

| Dataset.column                    | Symbol               | Domain / notes                                                           |
|-----------------------------------|----------------------|--------------------------------------------------------------------------|
| OUT.manifest_fingerprint         | $F$                  | hex64, equals `{fingerprint}` partition token.                           |
| OUT.global_seed                  | $S_{\text{master}}$  | u64, equals `{seed}` partition token.                                    |
| OUT.merchant_id                  | $m$                  | id64 (PK component).                                                     |
| OUT.legal_country_iso           | $i$                  | ISO-2 (PK component; FK to canonical ISO).                               |
| OUT.home_country_iso            | $\text{home}(m)$     | ISO-2, must equal `country_set.rank=0` for $m$.                          |
| OUT.site_order                   | $s_{m,i,k}$          | $\{1,\dots,n_{m,i}\}$ (PK component).                                    |
| OUT.site_id                      | $\text{id}_{m,i,k}$  | `^[0-9]{6}$`, equals $\sigma(s_{m,i,k})$.                                |
| OUT.final_country_outlet_count | $n_{m,i}$ (row echo) | Constant per $(m,i)$ when $n_{m,i}\ge1$. For $n_{m,i}=0$, no row exists. |
| OUT.single_vs_multi_flag       | $H_m$                | boolean; constant per $m$.                                               |
| OUT.raw_nb_outlet_draw         | $N^{\mathrm{raw}}_m$ | $\mathbb{Z}_{\ge1}$; constant per $m$.                                   |
| CST.country_iso                  | $i$                  | ISO-2; PK with `merchant_id` in `country_set`.                           |
| CST.rank                          | $\text{rank}_{m}(i)$ | $0$=home; $1..K_m$=foreign order (sole authority).                       |
| RC.residual                       | $R_{m,i}$            | $[0,1)$ (exclusive max).                                                 |
| RC.residual_rank                 | $r_{m,i}$            | $\{1,2,\dots\}$ (1 = largest).                                           |

---

## 6) Helper operators & sets (used later; defined now)

* **Row selection.** $\text{Rows}_{OUT}(m,i)=\{\,\text{rows}\in OUT: (\texttt{merchant_id},\texttt{legal_country_iso})=(m,i)\,\}$. Then $n_{m,i}=|\text{Rows}_{OUT}(m,i)|$.
* **Presence predicate.** $\mathbf{1}^{\text{egress}}_{m,i}=\mathbb{I}[n_{m,i}>0]$. Define $\mathcal{I}^{\text{egress}}_m=\{\,i:\mathbf{1}^{\text{egress}}_{m,i}=1\,\}$.
* **Block key sets.** $\mathcal{K}_{m,i}=\{(m,i,j): j\in\{1,\dots,n_{m,i}\}\}$ and $\mathcal{I\!D}_{m,i}=\{(m,i,\sigma(j)): j\in\{1,\dots,n_{m,i}\}\}$. (Exists only when $n_{m,i}\ge1$.)
* **Z-pad encoder & inverse.** As in §2.2; define $\sigma^{-1}$ where applicable.
* **Rank order projection.** For any list of foreign ISO codes $L\subseteq \mathcal{I}_m\setminus\{\text{home}(m)\}$,
  $\text{order}_{\text{country}}(L)=$ sort $L$ by `CST.rank` (ascending). **Never** derive this from egress.
* **Decimal quantiser (for later corridor checks).**
  $q_8(x)=\text{round_half_to_even}(x,\ 8\text{ dp})$. Mentioned here so later sections can reference a single symbol. (No quantisation is applied in S9.2 itself.)

---

## 7) Deterministic decoding rules (zero ambiguity)

Given the three authoritative inputs selected in S9.1:

1. **Counts.** Compute $n_{m,i}$ purely as egress row counts. When $n_{m,i}\ge1$, assert the groupwise constant echo: every row in $\text{Rows}_{OUT}(m,i)$ must have `final_country_outlet_count = n_{m,i}` (validated in S9.3/4). For $n_{m,i}=0$, **no** row exists and no echo is present.

2. **Within-country order.** The set $\{s_{m,i,k}\}$ must equal $\{1..n_{m,i}\}$ and $\text{id}_{m,i,k}=\sigma(s_{m,i,k})$. (S8 wrote it this way; S9 asserts it.)

3. **Cross-country order.** When an ordered country list is needed, **always** join to `country_set` and sort by `rank` (0 home, then $1..K_m$). Never infer cross-country order from any pattern in egress (e.g., file or row ordering).

4. **Merchant constants.** $H_m$, $N^{\mathrm{raw}}_m$, and $\text{home}(m)$ are constants per $m$ discoverable from egress rows; $\text{home}(m)$ must match the `rank=0` row in `country_set`.

5. **Residual order.** Whenever S9 needs to reconstruct integerisation tie-breaks, sort $R_{m,i}$ **descending** with secondary key ISO asc to obtain the deterministic $r_{m,i}$ ranking used by S7. (The cache already persists `residual_rank`; the sort rule is stated for completeness.)

---

## 8) Reference extraction routine (notation only — no validation yet)

```pseudo
function s9_2_symbols(OUT, CST, RC):
    # OUT is outlet_catalogue(seed,fingerprint)
    # CST is country_set(seed,parameter_hash)
    # RC  is ranking_residual_cache_1A(seed,parameter_hash)

    # 1) Per-merchant legal set with order (sole authority)
    I_m := { m -> list of (i, rank) from CST where merchant_id=m ordered by rank }

    # 2) Per-(m,i) egress counts and sequences
    n[m,i] := count_rows(OUT where merchant_id=m and legal_country_iso=i)
    S[m,i] := multiset of site_order from same rows                        # within-country sequence
    ID[m,i]:= multiset of site_id    from same rows                        # 6-digit strings

    # 3) Merchant constants (echoed per row)
    H[m]   := constant value of single_vs_multi_flag across rows of m      # (validated later)
    Nraw[m]:= constant value of raw_nb_outlet_draw  across rows of m
    home[m]:= constant value of home_country_iso     across rows of m

    # 4) Residuals and ranks (parameter-scoped)
    R[m,i] := RC.residual(m,i)
    r[m,i] := RC.residual_rank(m,i)

    return {I_m, n, S, ID, H, Nraw, home, R, r}
```

S9.3–S9.6 will apply the schema/PK/FK predicates, equality proofs, and RNG replay using these symbols; S9.7 packages the bundle and `_passed.flag`.

---

## 9) Sanity notes (what S9.2 **does not** do)

* **No schema/key checks here.** Those are S9.3; S9.2 only defines names and how to read them.
* **No RNG accounting yet.** Counters/labels are introduced in §4 to fix notation; replay and zero-draw proofs are S9.5/S9.6.
* **No corridors yet.** Quantiser $q_8$ is defined but not applied until S9.6.

---

## 10) Quick conformance checks for notation extraction (should pass if inputs are well-formed)

1. For any $(m,i)$ with $n_{m,i}\ge1$, `max(S[m,i]) = n[m,i]` and (|S\[m,i]| = n\[m,i]\`. (Pure decoding sanity.) ✔︎
2. For any $(m,i)$ with $n_{m,i}\ge1$ and any $s\in S[m,i]$, `sigma(s)` is in `ID[m,i]`. ✔︎
3. For each merchant $m$, `home[m] == country_set.rank0.country_iso(m)`. ✔︎

---

This locks **S9.2**: the exact symbol table; where each symbol comes from (dataset, partition scope, and column); the bijection between `site_order` and `site_id`; the strict separation of **within-country** order (egress) from **cross-country** order (country_set); and the helper operators we’ll use to express the validations, RNG replay, and corridor checks in the rest of S9.

---

# S9.3 — Structural validations

## 1) Scope (what S9.3 proves, strictly structural)

Given the fixed lineage $(\texttt{seed},\texttt{manifest_fingerprint},\texttt{parameter_hash},\texttt{run_id})$ established in S9.1, S9.3 validates — **before** any RNG replay or corridor stats — that:

1. **All referenced datasets match their JSON-Schema contracts** (types, ranges, regex), with authoritative schema pointers from the dictionary/registry.
2. **Primary keys and partition echoes** hold exactly (no duplicates; per-row echo equals directory tokens).
3. **Foreign keys (ISO-3166) and dataset scoping** are consistent.
4. **Block-level invariants** on egress are satisfied: gap-free within-country sequence; `site_id = zpad6(site_order)`; constant and correct `final_country_outlet_count` per $(m,i)$; and zero-block elision (no rows when $n_{m,i}=0$).

**Where order lives:** egress never encodes cross-country order; **only** `country_set.rank` carries it. This is a hard policy/contract, reasserted here.

---

## 2) Datasets, paths, partitions, schema pointers (authoritative)

| Dataset                          | Path (partitioned)                                                                      | Partitions                  | Schema pointer                                                                                                                                    |
|----------------------------------|-----------------------------------------------------------------------------------------|-----------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| **outlet_catalogue**            | `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`       | `["seed","fingerprint"]`    | `schemas.1A.yaml#/egress/outlet_catalogue` (PK/ordering = `["merchant_id","legal_country_iso","site_order"]`; **no inter-country order encoded**) |
| **country_set**                 | `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/`               | `["seed","parameter_hash"]` | `schemas.1A.yaml#/alloc/country_set` (column `rank`: 0=home; sole authority for cross-country order)                                              |
| **ranking_residual_cache_1A** | `data/layer1/1A/ranking_residual_cache_1A/seed={seed}/parameter_hash={parameter_hash}/` | `["seed","parameter_hash"]` | `schemas.1A.yaml#/alloc/ranking_residual_cache` (residual $[0,1)$, ISO FK)                                                                        |

All lookups (paths, schema refs) must be resolved **from the dictionary/registry**, not hard-coded.

---

## 3) Dataset-local schema predicates (must-hold)

### 3.1 `outlet_catalogue` (egress)

* **PK & ordering (schema/dictionary):** primary key and sort keys are **exactly** `(merchant_id, legal_country_iso, site_order)`.
* **Regex & ranges:**
  `manifest_fingerprint ~ ^[a-f0-9]{64}$`; `site_id ~ ^[0-9]{6}$`; `site_order ≥ 1`; `raw_nb_outlet_draw ≥ 1`; `home_country_iso` and `legal_country_iso` are ISO-2 with FK to the canonical ISO table referenced by schema; `final_country_outlet_count` is a **row echo of the block size** (see §4).
* **Partition echo:** **every row** must satisfy:
  `global_seed == {seed}` and `manifest_fingerprint == {fingerprint}` (directory tokens).
* **Policy note (structural check):** dataset **does not** encode cross-country order; consumers must join `country_set.rank`. S9 enforces this by asserting the absence of any cross-country ordering column and by later tests that **require** a join to `country_set`.

### 3.2 `country_set` (allocation)

* **PK:** `(merchant_id, country_iso)`; `rank` is integer with `0` = home and increasing foreign order. ISO FK applies. **This is the only source of cross-country order.**

### 3.3 `ranking_residual_cache_1A`

* **PK:** `(merchant_id, country_iso)`; `residual ∈ [0,1)` with `exclusiveMaximum: true`; ISO FK applies.

---

## 4) Cross-field & block invariants on egress (normative)

Let $\text{Rows}_{OUT}(m,i)$ be the egress rows for merchant $m$, legal country $i$ (possibly empty).

1. **Gap-free within-country sequence.**
   $\{\,\texttt{site_order}\,\} = \{1,2,\dots,n_{m,i}\}$ where $n_{m,i} = |\text{Rows}_{OUT}(m,i)|$. (If $n_{m,i}=0$, no row exists.)

2. **Site-ID encoder (bijection).**
   For each row:

   $$
   \texttt{site_id} = \mathrm{zpad6}(\texttt{site_order}) \ \ \text{and}\ \ \texttt{site_id} \sim \texttt{"^[0-9]{6}$"}.
   $$

   This couples the regex to construction used by S8.2.

3. **Block constant echo.**
   For $n_{m,i}\ge 1$: every row $r\in \text{Rows}_{OUT}(m,i)$ has
   `final_country_outlet_count == n_{m,i}` (constant across the block). (Zero-blocks emit **no rows**, so the echo never appears with 0.)

4. **Merchant constants.**
   On all rows for merchant $m$: `single_vs_multi_flag` and `raw_nb_outlet_draw` are merchant-constants, and `home_country_iso` is constant and must equal the `country_set` row where `rank=0`.

5. **Partition echo (row↔path).**
   Already listed in §3.1; re-asserted here as a cross-field equality with directory tokens.

---

## 5) Foreign keys & scoping

* **ISO FK:** every `home_country_iso`, `legal_country_iso` (egress), and every `country_iso` in the allocation tables must be present in the canonical ISO domain referenced by the schemas (enforced by S9.3).
* **Scope coherence:** joins pair `outlet_catalogue(seed,fingerprint)` with `country_set(seed,parameter_hash)` / `ranking_residual_cache_1A(seed,parameter_hash)`; mixed scopes are invalid and must be flagged upstream in S9.1 (presence/coherence).

---

## 6) Error taxonomy (machine codes; all are hard-fail)

**Schema / FK / echo**

* `s9.3.schema_violation.outlet_catalogue` — JSON-Schema mismatch in egress (type/range/regex).
* `s9.3.schema_violation.country_set` — schema mismatch in `country_set`.
* `s9.3.schema_violation.residual_cache` — schema mismatch in `ranking_residual_cache_1A`.
* `s9.3.fk_iso_breach` — any ISO FK failure in egress or allocation datasets.
* `s9.3.partition_echo_mismatch` — any row where `global_seed` ≠ `{seed}` or `manifest_fingerprint` ≠ `{fingerprint}`.

**Keys / ordering**

* `s9.3.pk_duplicate.outlet_catalogue` — duplicate `(merchant_id,legal_country_iso,site_order)`.
* `s9.3.pk_duplicate.country_set` — duplicate `(merchant_id,country_iso)` in `country_set`.
* `s9.3.pk_duplicate.residual_cache` — duplicate `(merchant_id,country_iso)` in residual cache.
* `s9.3.sort_order_break` — (optional) rows not non-decreasing in `(merchant_id,legal_country_iso,site_order)` across files.

**Block invariants**

* `s9.3.block_count_mismatch` — for some $(m,i)$, `#rows != final_country_outlet_count` (constant echo violated).
* `s9.3.site_order_gap_or_dup` — within $(m,i)$, `site_order` not exactly $\{1..n_{m,i}\}$.
* `s9.3.site_id_mismatch` — any row with `site_id != zpad6(site_order)` or failing the 6-digit regex.
* `s9.3.merchant_constant_drift` — merchant-constant fields (`single_vs_multi_flag`, `raw_nb_outlet_draw`, or `home_country_iso`) vary across rows for the same merchant; or `home_country_iso` ≠ `country_set.rank=0`.

**Policy**

* `s9.3.cross_country_order_in_egress` — any attempt to encode cross-country order in `outlet_catalogue` (e.g., unexpected column). (Policy breach per Schema Authority.)

All failures must be recorded in bundle artefacts (`schema_checks.json`, `key_constraints.json`, `diffs/*`) to make the proof reproducible.

---

## 7) Reference validator (single pass + group reductions)

Below is the **implementation-ready** routine. It consumes the three datasets resolved in S9.1 and writes structured evidence on failure.

```pseudo
function validate_structural(seed, fingerprint, parameter_hash,
                             OUT: iterator over outlet_catalogue rows,
                             CST: iterator over country_set rows,
                             RC:  iterator over ranking_residual_cache rows,
                             ISO: set of valid ISO2 codes):

  # A) Schema validations (use JSON-Schema pointers from dictionary/registry)
  assert jsonschema_validate("schemas.1A.yaml#/egress/outlet_catalogue", OUT)       # s9.3.schema_violation.outlet_catalogue
  assert jsonschema_validate("schemas.1A.yaml#/alloc/country_set", CST)             # s9.3.schema_violation.country_set
  assert jsonschema_validate("schemas.1A.yaml#/alloc/ranking_residual_cache", RC)   # s9.3.schema_violation.residual_cache

  # B) Per-row checks on egress (echo, ISO FK, regex coupled to construction)
  seen_pk := HashSet<(m,i,j)>()
  # Block tallies and merchant-constant maps
  rows_in_block := HashMap<(m,i), int>()
  declared_n    := HashMap<(m,i), int>()
  last_site_ord := HashMap<(m,i), int>()                 # for monotone check
  merch_flag    := HashMap<m, bool>()
  merch_nraw    := HashMap<m, int>()
  merch_home    := HashMap<m, ISO2>()

  for r in OUT:
      # Partition echo
      if r.global_seed != seed or r.manifest_fingerprint != fingerprint:
          raise s9.3.partition_echo_mismatch

      # ISO FKs (egress columns)
      if r.home_country_iso notin ISO or r.legal_country_iso notin ISO:
          raise s9.3.fk_iso_breach

      # Regex/range (redundant to JSON-Schema but enforced defensively)
      assert matches(r.manifest_fingerprint, "^[a-f0-9]{64}$")                      # schema echo
      assert matches(r.site_id, "^[0-9]{6}$")
      assert r.site_order >= 1
      assert r.raw_nb_outlet_draw >= 1

      # Site encoder & PK uniqueness
      if r.site_id != zpad6(r.site_order): raise s9.3.site_id_mismatch
      pk := (r.merchant_id, r.legal_country_iso, r.site_order)
      if not add_unique(seen_pk, pk): raise s9.3.pk_duplicate.outlet_catalogue

      # Block tallies (constant echo & count equality)
      k := (r.merchant_id, r.legal_country_iso)
      rows_in_block[k] = rows_in_block.get(k,0) + 1
      if k not in declared_n:
          declared_n[k] = r.final_country_outlet_count
      else:
          if declared_n[k] != r.final_country_outlet_count: raise s9.3.block_count_mismatch

      # Optional monotonicity check inside block
      if k in last_site_ord and r.site_order != last_site_ord[k] + 1:
          # (If you require strict 1..n streaming pattern; otherwise skip)
          pass
      last_site_ord[k] = r.site_order

      # Merchant constants
      m := r.merchant_id
      if m notin merch_flag: merch_flag[m] = r.single_vs_multi_flag
      elif merch_flag[m] != r.single_vs_multi_flag: raise s9.3.merchant_constant_drift

      if m notin merch_nraw: merch_nraw[m] = r.raw_nb_outlet_draw
      elif merch_nraw[m] != r.raw_nb_outlet_draw: raise s9.3.merchant_constant_drift

      if m notin merch_home: merch_home[m] = r.home_country_iso
      elif merch_home[m] != r.home_country_iso: raise s9.3.merchant_constant_drift

  # C) Close block checks (gap-free sequence & constant echo equality)
  for k in rows_in_block.keys():
      n_obs  = rows_in_block[k]
      n_decl = declared_n[k]
      if n_obs != n_decl: raise s9.3.block_count_mismatch
      # Gap-free test: since PK is unique and monotone increments, n_obs == max(site_order in block)
      # If not tracking monotone, compute max(site_order) per block; assert == n_obs.

  # D) Keys in allocation tables (country_set, residual cache) and ISO FKs
  seen_cst := HashSet<(m,i)>()
  seen_rc  := HashSet<(m,i)>()
  rank0    := HashMap<m, ISO2>()

  for c in CST:
      if (c.merchant_id, c.country_iso) in seen_cst: raise s9.3.pk_duplicate.country_set
      seen_cst.add((c.merchant_id, c.country_iso))
      if c.country_iso notin ISO: raise s9.3.fk_iso_breach
      if c.rank == 0:
         if c.merchant_id in rank0: raise s9.3.schema_violation.country_set   # duplicate homes
         rank0[c.merchant_id] = c.country_iso

  for t in RC:
      if (t.merchant_id, t.country_iso) in seen_rc: raise s9.3.pk_duplicate.residual_cache
      seen_rc.add((t.merchant_id, t.country_iso))
      if t.country_iso notin ISO: raise s9.3.fk_iso_breach

  # E) Merchant home-country coherence (egress vs country_set.rank=0)
  for m in merch_home.keys():
      if m notin rank0 or rank0[m] != merch_home[m]:
          raise s9.3.merchant_constant_drift  # or a dedicated code: s9.3.home_mismatch

  return OK
```

**Notes.**

* The “gap-free” test can be done **without** storing a set: PK-uniqueness + `max(site_order) == #rows` suffices.
* The **“row echo equals directory token”** predicate ties rows to the immutable partition (`seed,fingerprint`).

---

## 8) Evidence artefacts (written into the bundle)

S9.3 emits (append-only; final packaging in S9.7):

* `schema_checks.json` — for each dataset: `{dataset_id, files_scanned, violations:[{path, pointer, message}]}`.
* `key_constraints.json` — PK cardinality proofs and any duplicates with sample offending keys.
* `fk_checks.json` — ISO FK coverage table and breaches.
* `egress_block_invariants.json` — per $(m,i)$: `n_rows`, `declared_n`, `max_site_order`, flags for `gap_free`, `encoder_ok`.
* `policy_assertions.json` — presence of cross-country order **only** in `country_set.rank`.

These land under `data/layer1/1A/validation/fingerprint={fingerprint}/bundle.zip` in S9.7, and `_passed.flag` must hash to the bundle bytes.

---

## 9) Conformance tests (must-pass)

1. **Happy path:** pick $m$ with `country_set` entries `(GB rank=0, US rank=1)`, egress rows for GB×3 and US×2. Expect: PK unique; per-block `site_order=1..n`; `site_id=zpad6(site_order)`; `final_country_outlet_count` equals block size; echo matches partition; ISO FK holds; `home_country_iso`==GB==rank0. ✔︎

2. **Zero-block elision:** include FR in `country_set` but $n_{m,FR}=0$. Expect: **no** FR rows in egress; no `final_country_outlet_count=0` appears; all checks pass. ✔︎

3. **PK duplicate:** duplicate `(merchant_id,legal_country_iso,site_order)` → `s9.3.pk_duplicate.outlet_catalogue`. ✔︎

4. **Site-ID mismatch:** set `site_id="000010"` for `site_order=9` → `s9.3.site_id_mismatch`. ✔︎

5. **Block echo drift:** write two GB rows but set `final_country_outlet_count=3` → `s9.3.block_count_mismatch`. ✔︎

6. **Partition echo mismatch:** set a row’s `manifest_fingerprint` ≠ directory token → `s9.3.partition_echo_mismatch`. ✔︎

7. **ISO FK breach:** `legal_country_iso="ZZ"` not in canonical ISO → `s9.3.fk_iso_breach`. ✔︎

8. **Home mismatch:** `home_country_iso` on egress ≠ `country_set.rank=0` → `s9.3.merchant_constant_drift` (or `home_mismatch`). ✔︎

9. **Cross-country order leakage:** introduce a `country_rank` column into egress → `s9.3.cross_country_order_in_egress` (policy breach). ✔︎

---

## 10) Operational notes (binding where stated)

* **Authoritative schemas are JSON-Schema** as per Schema Authority Policy; do **not** validate against Avro in source. If Avro is needed downstream, generate at build/release; the validator still uses JSON-Schema.
* **Dictionary/registry are the source of truth** for `path`, `partitioning`, `schema_ref`, and lineage notes (producer/consumer). The validator should read these at runtime and assert conformance.
* **No inter-country order in egress**: keep this check active (policy assertion + absence of such columns); consumers must join `country_set.rank`.

---

This locks **S9.3** at the 100% level: dataset contracts from the dictionary/registry; executable schema, PK, FK, echo and block predicates; a complete error taxonomy; a reference validator; bundle evidence artefacts; and conformance tests — all aligned to S8’s construction and your Schema Authority Policy.

---

# S9.4 — Cross-dataset invariants

## 1) Scope (what S9.4 proves)

For a fixed lineage $P=(\texttt{seed},\texttt{manifest_fingerprint},\texttt{parameter_hash},\texttt{run_id})$, S9.4 asserts **bit-exact equalities** across:

1. **Realisation and conservation:** egress site counts $n_{m,i}$ and merchant-level **raw draw** $N_m^{\text{raw}}$.
2. **Coverage and order:** membership of legal countries and **cross-country order** derived **only** from `country_set` (and—where required—its *derivation evidence* from the RNG `gumbel_key` label).
3. **Largest-remainder reproducibility:** persisted residuals/ranks used by integerisation.
4. **Within-country sequencing:** bijection `site_order ↔ site_id` and block-finalisation events (presence only; the zero-draw proof lives in S9.5).

All equalities are **exact** (integers / string equality); no tolerances in this section. This aligns with the locked S9 charter for “exact equalities” in §S9.4.

---

## 2) Inputs & authorities (recap)

* **Egress:** `outlet_catalogue/seed={seed}/fingerprint={fingerprint}` (PK/order = `merchant_id, legal_country_iso, site_order`; **no inter-country order encoded**).
* **Allocation (parameter-scoped):** `country_set(seed,parameter_hash)` (sole authority for cross-country order; `rank: 0=home, 1..K` foreigns), `ranking_residual_cache_1A(seed,parameter_hash)` (`residual ∈ [0,1)`, `residual_rank`).
* **RNG evidence (run-scoped):** `gumbel_key` (foreign selection ordering), plus others used later; presence/shape catalogued in S9.1 and S9.3, and referenced here only where needed for order provenance.

---

## 3) Formal statements (per merchant $m$)

Let:

* $\mathcal{I}_m = \{\, i : (m,i)\in\texttt{country_set}\,\}$ with total order by `rank` (0 = home). **Only** this dataset carries cross-country order.
* $n_{m,i} := \#\text{rows in `outlet_catalogue` for } (m,i)$. For $n_{m,i}\ge 1$ all rows in the block echo `final_country_outlet_count = n_{m,i}` (validated in S9.3).
* $N_m^{\text{raw}}$ = `raw_nb_outlet_draw` (merchant-constant; appears on each row of $m$, commonly read from the home row).
* $R_{m,i}$ and $r_{m,i}$ from the residual cache.

### (A) Site-count realisation (definition equality)

$$
n_{m,i}=\big|\text{Rows in egress with }(\texttt{merchant_id},\texttt{legal_country_iso})=(m,i)\big|.
$$

And within each $(m,i)$: $\{\,\texttt{site_order}\,\}=\{1,\dots,n_{m,i}\}$. (Tied to S9.3’s block invariants; re-stated here to ground conservation.)

### (B) Country-set coverage & order (membership + rank continuity)

1. **Home uniqueness:** exactly one `country_set` row with `rank=0`; its `country_iso` equals the egress `home_country_iso` for merchant $m$.
2. **Foreign rank contiguity:** letting $K_m$ be the number of non-home rows, the set of observed foreign ranks equals $\{1,\dots,K_m\}$ (no gaps/dupes).
3. **Membership:** for all egress rows $(m,i)$, we must have $i\in\mathcal{I}_m$. No country in egress may lie outside `country_set` for the merchant. (Zero-blocks allowed via $n_{m,i}=0$, i.e., *absence* of rows.)

### (C) Allocation conservation (integerisation sums back to raw)

$$
\boxed{\ \sum_{i\in\mathcal{I}_m} n_{m,i} \;=\; N_m^{\text{raw}}\ } \quad\text{(exact integer equality).}
$$

This is the principal cross-dataset equality S9 must enforce.

### (D) Largest-remainder reproducibility (residuals & ranks)

Let $R_{m,i}\in[0,1)$ be the persisted fractional residuals and $r_{m,i}$ their deterministic rank (1 = largest). S9 must prove:

$$
\text{sort}\big(\{(i, R_{m,i})\}_{i\in\mathcal{I}_m}\big)\ \text{by}\ (-R_{m,i},\ i_{\text{ISO}})\ \equiv\ \text{order by residual_rank } r_{m,i}.
$$

(Primary key: residual descending; tie-break: ISO lexicographic asc.) This exactly matches the locked intent to reproduce LR tie-breaks from the cache.

> **Note.** If the build includes deterministic re-derivation of the **pre-integer** allocations $q_{m,i}$ from parameter-scoped inputs (no extra RNG), S9 may *also* check $R_{m,i}=\mathrm{frac}(q_{m,i})$. This is optional here; RNG replay of components is covered in S9.5.

### (E) Within-country sequencing & event coverage

For every egress row $k$ of block $(m,i)$:

$$
\texttt{site_id}=\mathrm{zpad6}(\texttt{site_order})\quad\text{and}\quad \#\texttt{sequence_finalize}(m,i)=\mathbf{1}[n_{m,i}>0].
$$

Presence of *exactly one* `sequence_finalize` per non-empty block (no per-site mapping implied). The *non-consumption* proof for these events belongs to S9.5; here we assert **coverage** and bijection with non-empty blocks.

---

## 4) Gumbel-order provenance (how we prove foreign order when required)

Some releases require proving that the foreign order $(\text{rank}=1\dots K_m)$ matches **Top-K by `gumbel_key`** with ISO tie-break. S9.4 therefore performs:

1. **Collect candidate foreign set:** $\mathcal{F}_m = \{i\in\mathcal{I}_m:\ \text{rank}>0\}$. (No inference from egress.)
2. **Build evidence list** $S_m$ by sorting the **`gumbel_key`** events for $m$ on $\mathcal{F}_m$ **descending by key, then ISO asc**.
3. **Assert:** membership of `country_set` foreign ISO equals $\mathcal{F}_m$ and the monotone mapping `rank=1..K_m` equals the order of $S_m$. Any mismatch ⇒ failure. (This binds order to the RNG evidence rather than egress.)

---

## 5) Algorithm (reference implementation)

```pseudo
function s9_4_cross_dataset(OUT, CST, RC, GUMBEL_EVENTS):
  # Index egress by merchant & country
  n := HashMap<(m,i) -> int>(0)
  merch_home := HashMap<m -> ISO2>()
  merch_raw  := HashMap<m -> int>()
  site_id_mismatch := []
  for r in OUT:
      n[(r.merchant_id, r.legal_country_iso)] += 1
      # Merchant constants (already checked in S9.3; re-read for conservation)
      merch_home[r.merchant_id] = r.home_country_iso
      merch_raw[r.merchant_id]  = r.raw_nb_outlet_draw
      # Encoder bijection
      if r.site_id != zpad6(r.site_order):
          site_id_mismatch.append((r.merchant_id, r.legal_country_iso, r.site_order, r.site_id))

  if site_id_mismatch: fail("s9.4.site_id_mismatch", dump=site_id_mismatch)

  # Country-set per merchant, check home uniqueness & rank continuity
  cset_by_m := group_rows(CST, key=merchant_id)
  home_diff := []; rank_gaps := []; coverage_leaks := []
  for m, rows in cset_by_m:
      home_rows = [r for r in rows if r.rank == 0]
      if len(home_rows) != 1 or merch_home.get(m) != home_rows[0].country_iso:
          home_diff.append(m)

      # foreign ranks 1..K_m contiguous, no dups
      foreign = [r for r in rows if r.rank > 0]
      K = len(foreign)
      ranks = sort([r.rank for r in foreign])
      if ranks != [1..K]: rank_gaps.append(m)

      # egress coverage: any (m,i) in OUT must exist in CST
      for (m2,i2), cnt in n.items() where m2==m and cnt>0:
          if not exists(rows where country_iso == i2):
              coverage_leaks.append((m,i2,"egress_outside_country_set"))

  if home_diff: fail("s9.4.country_set_home_mismatch", dump=home_diff)
  if rank_gaps: fail("s9.4.country_set_rank_contiguity", dump=rank_gaps)
  if coverage_leaks: fail("s9.4.country_set_coverage", dump=coverage_leaks)

  # Conservation per merchant: sum_i n_{m,i} == N_m^raw
  cons_diff := []
  for m in keys(cset_by_m):
      total = sum( n[(m,i)] for i in [r.country_iso for r in cset_by_m[m]] )
      if total != merch_raw.get(m, 0):
          cons_diff.append((m, total, merch_raw.get(m, None)))
  if cons_diff: fail("s9.4.mass_not_conserved", dump=cons_diff)

  # Largest-remainder reproducibility: residual sort == residual_rank
  lr_diff := []
  rc_by_m := group_rows(RC, key=merchant_id)
  for m, rows in rc_by_m:
      # expected: sort by (-residual, ISO asc)
      exp = sort(rows, key = (-row.residual, row.country_iso))
      if any(row.residual_rank != idx+1 for idx,row in enumerate(exp)):
          lr_diff.append(m)
  if lr_diff: fail("s9.4.residual_rank_mismatch", dump=lr_diff)

  # Optional: prove foreign order equals Top-K Gumbel order
  if GUMBEL_EVENTS is not None:
      gumbel_by_m := reduce_events_to_keys(GUMBEL_EVENTS)  # (m,i) -> key
      order_diff := []
      for m, rows in cset_by_m:
          foreign = [r for r in rows if r.rank>0]
          # reconstruct order via RNG evidence
          S = sort(foreign, key = (-gumbel_by_m[(m,r.country_iso)], r.country_iso))
          if any(r.rank != idx+1 for idx,r in enumerate(S)):
              order_diff.append(m)
      if order_diff: fail("s9.4.gumbel_order_mismatch", dump=order_diff)

  return OK
```

* `reduce_events_to_keys` extracts the numeric Gumbel key from the `gumbel_key` label stream for each `(m,i)`; the label schema is catalogued by the registry/dictionary and present per S9.1 prechecks.
* Egress **never** supplies cross-country order; we bind order strictly to `country_set.rank` (and to RNG evidence when required).

---

## 6) Error taxonomy (machine codes; all hard-fail here)

| Code                                    | Meaning / Trigger                                                  | Evidence artefact(s) written to bundle                                                     |
| --------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| `s9.4.site_id_mismatch`                 | Some row violates `site_id = zpad6(site_order)`                    | `diffs/sequence.csv` (merchant,country,site_order,site_id)                               |
| `s9.4.country_set_home_mismatch`        | Home ISO on egress ≠ `country_set.rank=0` or multiple/no home rows | `diffs/coverage.csv` (merchant,egress_home,rank0_home)                                   |
| `s9.4.country_set_rank_contiguity`      | Foreign ranks not exactly `1..K_m`                                 | `diffs/coverage.csv` (merchant, observed_ranks)                                           |
| `s9.4.country_set_coverage`             | Egress contains `(m,i)` with `i∉country_set(m)`                    | `diffs/coverage.csv` (merchant,country)                                                    |
| `s9.4.mass_not_conserved`               | $\sum_i n_{m,i} \ne N_m^{\text{raw}}$                              | `diffs/conservation.csv` (merchant, total_from_egress, raw_nb_draw)                    |
| `s9.4.residual_rank_mismatch`           | Sorting residuals (desc, ISO asc) ≠ persisted `residual_rank`      | `diffs/residual_rank_mismatch.csv` (merchant,country,residual,expected_rank,found_rank)  |
| `s9.4.gumbel_order_mismatch` (optional) | `country_set.rank` order ≠ Top-K by `gumbel_key` evidence          | `diffs/gumbel_order_mismatch.csv` (merchant,rank,iso,key,expected_order)                  |

These codes align with the expanded error catalogue and bundle layout.

---

## 7) Artefacts written (bundle wiring)

S9.4 appends to the validation bundle defined in S9.7:

* `diffs/conservation.csv` — one row per merchant with $(\sum_i n_{m,i}, N_m^{\text{raw}})$ and a boolean `ok`.
* `diffs/coverage.csv` — home coherence, rank gaps, and leaks (egress outside `country_set`).
* `diffs/residual_rank_mismatch.csv` — residual/rank diffs.
* `diffs/gumbel_order_mismatch.csv` (when gumbel proof is enabled).
* Updates to `key_constraints.json` and `schema_checks.json` are driven by S9.3; S9.4 supplies cross-dataset equality results and diffs. Bundle location & signing are as fixed in S9.7 (ZIP + `_passed.flag == SHA256(bundle)`).

---

## 8) Conformance tests (must-pass)

1. **Happy path:** Merchant $m$ with `country_set = [GB(rank=0), US(1), FR(2)]`; egress counts $n_{m,GB}=3, n_{m,US}=2, n_{m,FR}=0$; `raw_nb_outlet_draw=5`. Expect conservation 3+2+0=5, foreign ranks {1,2}, home coherence, no egress outside set, `site_id=zpad6(site_order)`, residual ranks consistent with residual sort. ✔︎
2. **Coverage leak:** Add egress rows for `DE` not present in `country_set` → `s9.4.country_set_coverage`. ✔︎
3. **Home mismatch:** Egress `home_country_iso=GB` but `country_set.rank=0 = US` → `s9.4.country_set_home_mismatch`. ✔︎
4. **Rank gap:** Foreign ranks `{1,3}` (missing 2) → `s9.4.country_set_rank_contiguity`. ✔︎
5. **Conservation fail:** $n_{m,GB}=2, n_{m,US}=2, n_{m,FR}=0$ with `raw_nb_outlet_draw=5` → `s9.4.mass_not_conserved`. ✔︎
6. **Residual rank drift:** `RC.residual_rank` disagrees with sort by `residual` desc, ISO asc → `s9.4.residual_rank_mismatch`. ✔︎
7. **Gumbel order check (enabled):** RNG log shows `key(US)>key(FR)`, but `country_set.rank(FR)=1, US=2` → `s9.4.gumbel_order_mismatch`. ✔︎

---

## 9) Policy reminders binding to S9.4

* **Egress never encodes inter-country order**; all order comparisons must reference `country_set.rank` (and optionally the `gumbel_key` RNG evidence when proving provenance).
* **All equalities are exact** in this section; tolerances apply only in S9.6 corridors.
* **Bundle gate:** even on failure S9 writes a full bundle of evidence; `_passed.flag` is written **only** on success and must equal `SHA256(bundle.zip)`.

---

This locks **S9.4** at 100%: exact equalities; Gumbel-order provenance procedure; integer conservation; residual/rank reproducibility; within-country encoder & event coverage; a precise error taxonomy; reference algorithm; bundle artefacts; and conformance tests — all aligned to the locked spec, expanded notes, schemas, and the registry/dictionary.

---

# S9.5 — RNG determinism & replay checks (implementation-ready)

## Scope (what S9.5 must prove)

For every RNG-touching step in 1A (NB mixture, ZTP diagnostics, Gumbel-top-K, Dirichlet, integerisation, sequence finalisation), the validator must **replay** or **account for** exactly the random draws claimed, using only the audited RNG identity and the per-event **RNG envelope** (seed + 128-bit counters). This makes the run **order-invariant** and reproducible under parallel execution.

---

## Inputs & authorities

* **Audit log** (run-scoped): states the RNG algorithm and seed; partitioned by `{seed, parameter_hash, run_id}`.
* **Trace log** (run-scoped): one record per `(module, substream_label)` emission; carries `draws` (uniforms consumed).
* **Structured RNG event streams** (label-scoped): `gamma_component`, `poisson_component`, `nb_final`, `ztp_*`, `gumbel_key`, `dirichlet_gamma_vector`, `residual_rank`, `sequence_finalize`, `stream_jump`—all with the common **RNG envelope**. Paths & schema refs are fixed by the dataset dictionary/registry.
* **Egress dataset**: `outlet_catalogue` carries `global_seed` & `manifest_fingerprint` per row for 1→many equality checks. (S9.4 ties `sequence_finalize` counts to egress rows.)

---

## S9.5.1 Envelope identity (run → egress)

**Goal.** Prove the egress partition came from the audited RNG. For the active `{seed, parameter_hash, run_id}`:

1. `rng_audit_log.algorithm == "philox2x64-10"`.
2. `rng_audit_log.seed == outlet_catalogue.global_seed` for **all** rows in the `(seed,fingerprint)` partition.
3. `rng_audit_log.{parameter_hash,manifest_fingerprint}` equal the partition keys and per-row `manifest_fingerprint`.

**Failure semantics.** Any inequality is a **structural failure**; record in the bundle and withhold `_passed.flag`.

---

## S9.5.2 128-bit counter arithmetic & per-label draw accounting

For each label \$\ell\$ (e.g., `gumbel_key`, `dirichlet_gamma_vector`, `gamma_component`, `poisson_component`, `residual_rank`, `sequence_finalize`, …), order its event rows by `ts_utc` to form \$T_\ell\$. From each event’s envelope:

$$
C^\text{before}_e=(\texttt{before_hi}\ll64)+\texttt{before_lo},\quad
C^\text{after}_e=(\texttt{after_hi}\ll64)+\texttt{after_lo}.
$$

Define the **observed advance** and **declared advance**:

$$
\Delta C_\ell \;=\; C^\text{after}_{\text{last}}-C^\text{before}_{\text{first}},\qquad
D_\ell \;=\; \sum_{\texttt{rng_trace_log where }\ell}\texttt{draws}.
$$

**Mandatory equality** (unsigned 128-bit arithmetic):

$$
\boxed{\;\Delta C_\ell \stackrel{!}{=} D_\ell\;}
$$

Additionally, for consecutive events \$e_j,e_{j+1}\in T_\ell\$ assert **adjacency monotonicity**:
\$C^\text{after}*{e_j}\le C^\text{before}*{e_{j+1}}\$, with equality iff the intervening event consumed **zero** draws.

**Rare jumps.** If `stream_jump` is enabled, add the sum of `jump_stride_{lo,hi}` for label \$\ell\$ to \$D_\ell\$ before comparing to \$\Delta C_\ell\$ (accounts that advance the counter without consumption).

**Primitive budgets (from S0).**

* Uniform \$(0,1)\$: one 64-bit lane; mapping \$u=(x+1)/(2^{64}+1)\in(0,1)\$.
* Standard normal (Box–Muller): **2 uniforms** per \$Z\$; no caching of the sine pair.
* Envelope identity: `after = before + draws`.

---

## S9.5.3 Event cardinalities (must match process logic)

Compute **expected counts** from deterministic inputs/outputs, then compare to **observed**:

* **`gumbel_key`**: exactly **one** event per foreign candidate examined for the merchant; payload carries `(weight,u,key,selected,selection_order)`. **Exactly one** uniform per candidate.
* **`dirichlet_gamma_vector`**: **one** vector event per merchant iff \$|C|=K{+}1>1\$; none when \$K=0\$. Arrays `(country_isos,alpha,gamma_raw,weights)` aligned; `Σ weights = 1` within tolerance.
* **Integerisation:** `residual_rank` — exactly **\$|C|\$** per merchant (including domestic-only); **non-consuming** (before==after).
* **NB composition:** per attempt emit **one** `gamma_component` and **one** `poisson_component`; `nb_final` **exactly once** at acceptance; attempts ≥1.
* **S8 attestation:** `sequence_finalize` — **exactly one** per \$(m,c)\$ with \$n_{m,c}>0\$; **non-consuming**; global count equals \$\sum_{(m,c)} \mathbf{1}{n_{m,c}>0}\$.

---

## S9.5.4 Trace reconciliation (trace vs. events)

For each label \$\ell\$, prove the **two independent sources** agree:

* \$D_{\text{trace}}(\ell) =\$ sum of `draws` in `rng_trace_log` for `(module, substream_label=ℓ)`.
* \$D_{\text{events}}(\ell) =\$ sum over **event** rows’ envelope deltas (`after − before`).

Require \$D_{\text{trace}}(\ell) = D_{\text{events}}(\ell)\$; mismatch ⇒ **structural failure** recorded in `rng_accounting.json`.

---

## S9.5.5 Budget spot-checks (cross-validating expected draw counts)

Use algorithmic budgets to sanity-check totals:

* **Hurdle:** let \$\mathcal{M}*\star={m:0<\pi_m<1}\$. Each such merchant consumes exactly **1** uniform (degenerate \$\pi\$ consumes 0). Require
  \$|\mathcal{M}*\star| = D_{\text{events}}(\text{“hurdle_bernoulli”})\$.

* **NB Gamma (context=`"nb"`):** Gamma sampler costs **3 uniforms** per attempt (α≥1), plus **+1** for the power step when \$0<\alpha<1\$; total attempts equal `nb_rejections + 1`. Require
  \$D_{\text{events}}(\text{“gamma_component”})/3 = \sum_m (\texttt{nb_final.nb_rejections}_m + 1)\$.

* **Dirichlet Gamma vector:** Across components,
  \$D_{\text{events}}(\text{“dirichlet_gamma_vector”}) = 3\cdot A_{\text{tot}} + #{\alpha_i<1}\$,
  where \$A_{\text{tot}}=\big\lfloor D_{\text{events}}(\text{“dirichlet_gamma_vector”})/3\big\rfloor\$; no draws for normalisation.

* **Gumbel-top-K:** exactly **1 uniform per candidate**, and per-merchant event count equals candidate count.

* **Non-consuming labels:** `residual_rank`, `sequence_finalize`, `site_sequence_overflow` must have **before==after** and hence contribute **0** to both \$D_{\text{trace}}\$ and \$D_{\text{events}}\$.

---

## S9.5.6 Replay spot-checks (payload re-derivation)

Pick a **deterministic sample** of merchants (e.g., hash of `(merchant_id ⊕ seed ⊕ fingerprint)` mod \$M\$). For each sampled case:

1. **Gumbel keys.** From the event’s `rng_counter_before` and seed, regenerate \$u\in(0,1)\$ via S0.3.4, compute
   \$z=\log w-\log(-\log u)\$, and compare to logged `u`/`key` bit-for-bit.

2. **Dirichlet vector.** From `dirichlet_gamma_vector`’s `rng_counter_before`, regenerate the \$\Gamma(\alpha_i,1)\$ deviates (MT1998 + Box–Muller budgets), re-normalise to `weights`, and compare arrays (`gamma_raw`, `weights`) and length constraints. Abort on first mismatch and persist a reproducer `{seed, before_hi, before_lo, label, merchant_id}`.

---

## Error taxonomy (normative)

* `ERR_RNG_ALGO_MISMATCH` — audit.algorithm ≠ expected.
* `ERR_RNG_SEED_MISMATCH` — audit.seed ≠ egress.global_seed for any row.
* `ERR_COUNTER_ADVANCE_MISMATCH[ℓ]` — \$\Delta C_\ell \ne D_\ell(+J_\ell)\$ for some label.
* `ERR_EVENT_CARDINALITY[ℓ]` — observed label counts differ from required counts (per bullets above).
* `ERR_TRACE_EVENTS_DIVERGE[ℓ]` — \$D_{\text{trace}}(\ell)\ne D_{\text{events}}(\ell)\$.
* `ERR_REPLAY_MISMATCH[label]` — regenerated `u`/`key` or `gamma_raw`/`weights` don’t match the event payload.

All errors are **hard fails**; the validator still writes `rng_accounting.json` to the bundle but withholds `_passed.flag`.

---

## Validator outputs (machine-readable bundle artefact)

Write `rng_accounting.json` with, for each `(label, merchant_id)` or global as appropriate:
`{observed_events, expected_events, draws_trace, draws_events, counter_delta, jumps, ok, notes}`. Include replay spot-check results and first reproducer on failure.

---

## Reference validator (language-agnostic pseudocode)

```pseudo
INPUT:
  audit := rng_audit_log(seed, parameter_hash, run_id)
  trace := rng_trace_log(seed, parameter_hash, run_id)
  events := {
    gumbel_key, dirichlet_gamma_vector, residual_rank,
    gamma_component(nb), poisson_component(nb), nb_final,
    ztp_rejection, ztp_retry_exhausted, sequence_finalize, stream_jump
  }
  egress := outlet_catalogue(seed, fingerprint)
  country_set := authoritative ranks per merchant

# 1) Envelope identity
assert audit.algorithm == "philox2x64-10"
assert for all rows in egress: row.global_seed == audit.seed
assert audit.parameter_hash == parameter_hash && audit.manifest_fingerprint == fingerprint

# 2) Per-label draw accounting
for ℓ in labels(events):
  Tℓ := sort_by_ts_utc(events[ℓ])
  Cbefore := to_u128(first(Tℓ).before_hi, first(Tℓ).before_lo)
  Cafter  := to_u128(last(Tℓ).after_hi,  last(Tℓ).after_lo)
  ΔC := Cafter - Cbefore
  D := sum(trace.draws where trace.substream_label==ℓ)
  J := sum_jumps(stream_jump where label==ℓ)   # optional
  assert ΔC == D + J
  assert adjacency_monotone(Tℓ)  # after_j ≤ before_{j+1}; equality ⇒ draws==0

# 3) Event cardinalities
for each merchant m:
  assert count(gumbel_key where m) == num_foreign_candidates(m)
  if |C_m|>1: assert exactly_one(dirichlet_gamma_vector where m)
  assert count(residual_rank where m) == |C_m|
  A := count(gamma_component where m) == count(poisson_component where m)
  assert exactly_one(nb_final where m)
  for each (m,c) with n_{m,c}>0: assert exactly_one(sequence_finalize(m,c))

# 4) Trace reconciliation
for ℓ: assert sum(trace.draws where ℓ) == sum_events_delta(events[ℓ])

# 5) Budget spot-checks
assert |{m: 0<π_m<1}| == D_events("hurdle_bernoulli")
assert D_events("gamma_component")/3 == Σ_m(nb_final.rejections_m + 1)
check_dirichlet_budget()  # 3 per attempt + 1 for α<1 components
assert for each m: count(gumbel_key where m) == num_foreign_candidates(m)

# 6) Replay spot-checks for a deterministic sample
for m in sample_merchants(seed,fingerprint):
  replay_gumbel_keys(m)
  replay_dirichlet_vector(m)

# 7) Emit rng_accounting.json and gate _passed.flag
```

Citations for budgets, counters, event scopes and schemas throughout: S0/S2/S6/S7/S8/S9 specs and dictionary/registry.

---

## Conformance tests (negative/edge)

1. Shuffle processing order across partitions → **no change** in counters or draws reconciliation (order-invariance).
2. Inject one `gumbel_key` payload with `u∉(0,1)` → schema breach (hard fail).
3. Drop one `sequence_finalize` for a non-empty \$(m,c)\$ block → global cardinality check fails.
4. Corrupt one `dirichlet_gamma_vector.weights` entry (sum≠1) → schema constraint fails.
5. Tamper `rng_trace_log.draws` for a label by +1 → `D_trace(ℓ)≠D_events(ℓ)` (hard fail).

---

### Why this is “100%”

* **Mathematical identities** for 128-bit counter arithmetic and equality conditions.
* **Operational contracts** (cardinalities, zero-draw labels, replay sampling, budgets) mapped to schemas/paths fixed by the registry/dictionary.
* **Abort semantics** and **machine-readable outputs** to authorize 1A→1B hand-off.

---

# S9.6 — Statistical corridors

This section defines the **release-time sanity tests** that must hold (as *hard gates*) before `_passed.flag` can be written. All corridor metrics are **derived deterministically** from egress, allocation caches, and RNG evidence already locked earlier; results are recorded to `metrics.csv` inside the validation bundle, and any breach produces a **hard fail** (bundle written; flag withheld).

---

## 1) Inputs, scope, determinism

**Authoritative inputs (read-only):**

* `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}`: immutable egress (per-row: `H_m = single_vs_multi_flag`, `N^{raw}_m = raw_nb_outlet_draw`, block counts `n_{m,i}`). Inter-country order is not encoded here.
* `country_set/seed={seed}/parameter_hash={parameter_hash}`: sole carrier of cross-country order (`rank`: 0=home; 1..K foreign). Used to enumerate legal countries per merchant.
* `ranking_residual_cache_1A(seed,parameter_hash)`: persistent residuals; we will **recompute** pre-integer shares $q_{m,i}$ using S9.4 machinery (Dirichlet weights).
* RNG event streams (run-scoped): notably `poisson_component(context="ztp")`, `ztp_rejection`, `ztp_retry_exhausted`, and `dirichlet_gamma_vector` (for rebuilding $q_{m,i}$).
* Optional cache: `hurdle_pi_probs(parameter_hash)` for model-implied $\pi_m$. If absent, **skip** the hurdle corridor (record “not evaluated”).

**Outputs:**

* `metrics.csv` inside `validation_bundle_1A(fingerprint)`; bundle and `_passed.flag` contract as in S9.7. **Any corridor breach** ⇒ gate fails; bundle still materialises.

**Numeric policy:** IEEE-754 binary64 only; sums use Neumaier compensation; final corridor comparisons use exact integer equality where applicable and otherwise the configured epsilons. Quantisation `Q_8` (8 dp, ties-to-even) is the same operator defined in S7/S9.4 and must be applied when reconstructing residual-based quantities.

---

## 2) Corridor catalogue (definitions, math, thresholds, gating)

### 2.1 Hurdle calibration (multi-site prevalence) — *optional if cache present*

**Goal.** Check empirical multi-site rate against model-implied average.

* **Empirical rate:** $\displaystyle \widehat{\pi}=\frac{1}{|\mathcal{M}|}\sum_{m\in\mathcal{M}}H_m$, where $H_m\in\{0,1\}$ is `single_vs_multi_flag` read from egress (merchant-constant).
* **Model average:** $\displaystyle \bar{\pi}=\frac{1}{|\mathcal{M}|}\sum_{m\in\mathcal{M}}\pi_m$ from `hurdle_pi_probs` (if available).
* **Gate:** $|\widehat{\pi}-\bar{\pi}|\le \varepsilon_{\pi}$, default $\varepsilon_{\pi}=0.02$.
* **Recorded (non-gating diagnostics):** Wilson 95% CI for $\widehat{\pi}$, and the z-score of the gap. These appear in `metrics.csv` but do not change pass/fail.

**Wilson CI formula (record only).** For $n=|\mathcal{M}|$, $\hat p=\widehat{\pi}$, $z=1.96$:

$$
\text{center}=\frac{\hat p+\tfrac{z^2}{2n}}{1+\tfrac{z^2}{n}},\quad
\text{halfwidth}=\frac{z}{1+\tfrac{z^2}{n}}\sqrt{\frac{\hat p(1-\hat p)}{n}+\frac{z^2}{4n^2}}.
$$

### 2.2 Integerisation fidelity (largest-remainder L1 guard)

**Goal.** While **mass conservation is exact** (enforced in S9.4), quantify the maximum L1 deviation between realised shares and pre-integer shares.

* **Rebuild pre-integer shares:** using S9.4’s deterministic recomputation from `dirichlet_gamma_vector` events, obtain weights $w_{m,i}$ and shares $q_{m,i}=w_{m,i}$ (post normalisation). Apply `Q_8` only when the corridor explicitly refers to residuals; for shares, use the exact normalised binary64.
* **Realised shares:** $n_{m,i}/N^{raw}_m$ from egress; `N^{raw}_m` is the home-row `raw_nb_outlet_draw` (merchant-constant).
* **Per-merchant L1 gap:** $\displaystyle \Delta_m=\sum_{i\in\mathcal{I}_m}\left|\,\frac{n_{m,i}}{N^{raw}_m}-q_{m,i}\right|$.
* **Gate:** $\max_m \Delta_m \le \varepsilon_{\text{LRR}}$ with default $\varepsilon_{\text{LRR}}=10^{-12}$ (numerical guard only; conservation is still exact). Also record p50/p99 of $\Delta_m$.

### 2.3 Sparsity behaviour (currency-level)

**Goal.** Check that the observed rate of “sparse” currencies matches the governed expectation.

* **Observed rate:** $\widehat{\rho}=\frac{1}{|\mathcal{K}|}\sum_{\kappa\in\mathcal{K}}\mathbf{1}[\texttt{sparse_flag}(\kappa)=1]$, computed over all currencies seen in the run’s candidate sets (or the governed currency domain).
* **Expected rate:** $\rho_{\text{expected}}$ by parameterised rule (from config).
* **Gate:** $|\widehat{\rho}-\rho_{\text{expected}}|\le \varepsilon_\rho$ (default $\varepsilon_\rho$ configured per release). Record both values and absolute diff.

### 2.4 ZTP acceptance corridor (foreign-count draw $K$)

**Goal.** Monitor operational health of the zero-truncated Poisson acceptance process.

* **Counts from RNG events:**
  $T=$ total `poisson_component(context="ztp")` attempts;
  $A=$ number of **accepted** draws (`nb_final` for $K\ge 1$, or dedicated accept event); define $\widehat{a}=A/T$.
* **Gate:** $\widehat{a}\in [a_L,a_U]$ where $[a_L,a_U]$ is governed (config). Record $(\widehat{a})$ and, *if model inputs available*, $\bar a=\text{mean}_m(1-e^{-\lambda_m})$ for traceability only (non-gating).

> **Gating semantics.** Items **(1)–(4)** above are **hard gates**; any breach yields `corridor_breach_*` and blocks `_passed.flag`. Wilson/z-diagnostics and $\widehat{a}-\bar a$ are **record-only**.

---

## 3) Algorithms (reference, deterministic & streaming)

Below is an implementation-ready, language-agnostic routine that **computes and gates** the four corridors, producing `metrics.csv` for the bundle.

```pseudo
function s9_6_corridors(OUT, CST, DIRICHLET_EVENTS, HURDLE_PI_PROBS?, ZTP_EVENTS, CONFIG):
    # CONFIG provides: eps_pi (default 0.02), eps_LRR (1e-12), eps_rho, [a_L, a_U]
    # 1) Precompute merchant sets and constants
    M := distinct merchants in OUT
    H[m]   := merchant-constant single_vs_multi_flag from OUT
    Nraw[m]:= merchant-constant raw_nb_outlet_draw   from OUT
    # counts per (m,i)
    n[(m,i)] := number of OUT rows with (merchant_id=m, legal_country_iso=i)

    # 2) Corridor 1: Hurdle calibration (optional if cache present)
    if HURDLE_PI_PROBS? is present:
        pi_bar := mean_over_m( HURDLE_PI_PROBS[m] )                 # model-implied
        pi_hat := mean_over_m( H[m] )                               # empirical
        gap_pi := abs(pi_hat - pi_bar)
        # Wilson (record-only)
        wilson_center, wilson_halfwidth := wilson_interval(pi_hat, |M|, z=1.96)
        gate_hurdle := (gap_pi <= CONFIG.eps_pi)
        record_metric("hurdle_pi_hat", pi_hat)
        record_metric("hurdle_pi_bar", pi_bar)
        record_metric("hurdle_gap", gap_pi)
        record_metric("hurdle_wilson_center", wilson_center)
        record_metric("hurdle_wilson_halfwidth", wilson_halfwidth)
    else:
        gate_hurdle := true
        record_metric("hurdle_evaluated", 0)    # 0 = skipped; non-gating

    # 3) Corridor 2: Integerisation fidelity (LRR L1)
    #    Rebuild q_{m,i} from dirichlet_gamma_vector events (S9.4 rules), binary64 + Neumaier sums
    W := reconstruct_dirichlet_weights(DIRICHLET_EVENTS)            # (m,i) -> w_{m,i}, Σ_i w=1
    Δ := []
    for m in M:
        denom := R64(Nraw[m])                                       # binary64 cast
        acc := 0.0 ; comp := 0.0                                    # Neumaier
        for i in legal_countries(CST, m):
            share_real := R64(n[(m,i)]) / denom
            share_model:= W[(m,i)]
            term := abs(share_real - share_model)
            # Neumaier accumulate Δ_m
            t := acc + term
            comp += (abs(acc) >= abs(term)) ? (acc - t + term) : (term - t + acc)
            acc = t
        Δ_m := acc + comp
        Δ.append(Δ_m)
    Δ_max := max(Δ); Δ_p50 := percentile(Δ, 50); Δ_p99 := percentile(Δ, 99)
    gate_lrr := (Δ_max <= CONFIG.eps_LRR)
    record_metric("lrr_L1_max", Δ_max)
    record_metric("lrr_L1_p50", Δ_p50)
    record_metric("lrr_L1_p99", Δ_p99)

    # 4) Corridor 3: Sparsity behaviour
    rho_hat := mean_over_currencies( sparse_flag[kappa] )
    gap_rho := abs(rho_hat - CONFIG.rho_expected)
    gate_rho := (gap_rho <= CONFIG.eps_rho)
    record_metric("sparse_rate_hat", rho_hat)
    record_metric("sparse_rate_expected", CONFIG.rho_expected)
    record_metric("sparse_rate_gap", gap_rho)

    # 5) Corridor 4: ZTP acceptance
    T := count(ZTP_EVENTS where label="poisson_component" and context="ztp")
    A := count_acceptances_from_ztp(ZTP_EVENTS)     # module-defined; includes only successes with K>=1
    a_hat := (T == 0) ? 1.0 : R64(A) / R64(T)       # degenerate guard; T should be >0 in practice
    gate_ztp := (CONFIG.a_L <= a_hat and a_hat <= CONFIG.a_U)
    record_metric("ztp_attempts", T)
    record_metric("ztp_acceptances", A)
    record_metric("ztp_rate_hat", a_hat)
    if CONFIG.has_model_lambda:
         a_bar := mean_over_m( 1 - exp(-lambda_m) )
         record_metric("ztp_rate_bar", a_bar)
         record_metric("ztp_rate_gap", a_hat - a_bar)

    # 6) Decide and emit
    corridors_pass := gate_hurdle and gate_lrr and gate_rho and gate_ztp
    write_metrics_csv()           # deterministic ordering of rows/columns
    return corridors_pass
```

* `reconstruct_dirichlet_weights` must **exactly** follow S9.4 replay rules: regenerate gamma deviates from the event’s `rng_counter_before`, normalise with compensated sums (binary64), and use the array order logged; no extra randomness is consumed here.
* `count_acceptances_from_ztp` uses the run’s ZTP events; acceptance is defined by the presence of a success indicator (or `nb_final` attached to ZTP path), consistent with S9.5’s cardinality rules.

---

## 4) `metrics.csv` schema (bundle content)

Write a flat CSV with deterministic column order:

| column      | type            | meaning                                                                             |
|-------------|-----------------|-------------------------------------------------------------------------------------|
| `metric`    | string          | identifier (e.g., `hurdle_pi_hat`, `lrr_L1_max`, `sparse_rate_hat`, `ztp_rate_hat`) |
| `value`     | number          | measured value (binary64)                                                           |
| `threshold` | number or empty | configured gate (e.g., `eps_pi`, `eps_LRR`, `a_L..a_U` encoded in `notes`)          |
| `notes`     | string          | free text, may include “record-only” or model reference (e.g., `a_L=0.35,a_U=0.65`) |
| `evaluated` | {0,1}           | 1 if evaluated; 0 if metric skipped by policy (e.g., missing `hurdle_pi_probs`)     |

The validator’s bundle index must include `("corridor_metrics","table","metrics.csv","text/csv", ...)` and the bundle must be signed; `_passed.flag` content equals `SHA256(bundle.zip)`.

---

## 5) Error taxonomy (machine codes; hard-fail)

* `corridor_breach_hurdle_gap` — $|\widehat{\pi}-\bar{\pi}|>\varepsilon_\pi$. (Only evaluated if `hurdle_pi_probs` present.)
* `corridor_breach_lrr_L1` — $\max_m\Delta_m>\varepsilon_{\text{LRR}}$.
* `corridor_breach_sparse_rate` — $|\widehat{\rho}-\rho_{\text{expected}}|>\varepsilon_\rho$.
* `corridor_breach_ztp_rate` — $\widehat{a}\notin[a_L,a_U]$.

All corridor breaches set `corridors_pass=false` in the decision routine; bundle is written but `_passed.flag` is **not**.

---

## 6) Conformance tests (must pass)

1. **Happy path:** synthetic fixture with `hurdle_pi_probs` present; $|\widehat{\pi}-\bar{\pi}|=0.005\le0.02$; $\max\Delta_m=7\times10^{-14}$; $|\widehat{\rho}-\rho_{\text{expected}}|=0.001$; $\widehat{a}$ within band → `corridors_pass=true`, bundle signed. ✔︎
2. **Hurdle skipped:** remove `hurdle_pi_probs` → metric marked `evaluated=0`, no gate taken; other corridors pass → success. ✔︎
3. **LRR guard breach (numerical):** perturb a `dirichlet_gamma_vector` weight by $5\times10^{-12}$ so $\max\Delta_m=2\times10^{-12}>\varepsilon_{\text{LRR}}$ while conservation still holds → `corridor_breach_lrr_L1`. ✔︎
4. **Sparse rate drift:** flip half the currencies’ flags to 1 when $\rho_{\text{expected}}=0.2$ → `corridor_breach_sparse_rate`. ✔︎
5. **ZTP out of band:** force acceptance to 0.1 with corridor $[0.3,0.7]$ → `corridor_breach_ztp_rate`. ✔︎

---

## 7) Operational notes

* **Do not inline thresholds** in code; read them from governed config and echo into `metrics.csv` for auditability.
* **No extra randomness** is consumed; replay uses the event envelopes already validated in S9.5.
* **Immutability & gate:** corridors are part of the **same** bundle+flag contract — 1B must still validate the flag equals `SHA256(bundle.zip)` before reading egress.

---

This pins **S9.6** at the “100%” level: exact corridor definitions and math; deterministic algorithms with numeric policy; CSV schema and bundle wiring; error taxonomy; conformance tests; and clear gating semantics tied to the registry/dictionary and S9.7 signing rules.

---

# S9.7 — Bundle & Signing

## 1) Purpose and contract (what S9.7 certifies)

After S9.2–S9.6 pass, S9.7 produces a **single audit artefact** — a **ZIP bundle** — and a **flag file** that jointly authorize 1B to read `outlet_catalogue` for this exact `fingerprint`. The bundle lives under

```
data/layer1/1A/validation/fingerprint={manifest_fingerprint}/
```

and its internal `index.json` MUST conform to `schemas.1A.yaml#/validation/validation_bundle`. The `_passed.flag` is written in the **same folder** and acts as the cryptographic gate for 1B.

**Authoritative requirements (recap from locked S9):**

* Minimal bundle contents: `index.json`, `schema_checks.json`, `key_constraints.json`, `rng_accounting.json`, `metrics.csv`, and any `diffs/*` produced.
* Compute `H = SHA256(bundle.zip bytes)` and write `_passed.flag` so that consumers can verify the flag **matches** the bundle hash for the same `fingerprint`. 1B **must** verify the match before reading `outlet_catalogue`.

The artefact registry + dictionary encode this contract (paths, ownership, notes, and the explicit “verify `_passed.flag` against bundle SHA256 before reading” policy).

---

## 2) Bundle index schema (inside the ZIP)

`index.json` is a **table** conforming to the `validation_bundle.index_schema` from your schemas file (PK + column set). We fix the columns and permitted values to avoid ambiguity:

* **Primary key:** `artifact_id` (string; unique).
* **Columns:**

  * `kind ∈ { "plot","table","diff","text","summary" }`
  * `path` — **relative** path within the ZIP (UTF-8).
  * `mime` — optional media type (e.g., `application/json`, `text/csv`).
  * `notes` — optional free text (may include lineage or thresholds).

**Typical rows** (normative examples):

```
("schema_checks","table","schema_checks.json","application/json","JSON-Schema results")
("key_constraints","table","key_constraints.json","application/json",null)
("rng_accounting","table","rng_accounting.json","application/json",null)
("corridor_metrics","table","metrics.csv","text/csv","Release gates & thresholds")
("residual_diffs","diff","diffs/residual_rank_mismatch.csv","text/csv","Exact mismatches")
```

The data dictionary binds **format=`zip`**, **partitioning by `fingerprint`**, and the `schema_ref` for this index.

---

## 3) Canonical packaging (byte-stable ZIP)

To guarantee that the same inputs produce **byte-identical** bundles (so `H` is stable), S9.7 MUST:

1. **Materialise payload files** produced by earlier S9 steps:
   `schema_checks.json`, `key_constraints.json`, `rng_accounting.json`, `metrics.csv`, and any `diffs/*`.

2. **Build `index.json`** as above and **validate it** against `validation_bundle.index_schema` before packaging.

3. **ZIP canonicalisation (determinism rules):**

   * Use **UTF-8** file names.
   * Sort entries **lexicographically by `path`** in the ZIP.
   * Use a **fixed compression level** (e.g., DEFLATE level N chosen by policy) to minimise platform drift.
   * Prefer setting ZIP timestamps to a fixed epoch if your ZIP lib supports it (recommended for maximal stability; not mandated by the current text).
   * Never include absolute paths; all paths are **relative** and must match the `index.json` `path` values exactly.

4. **Compute the digest and sign:**
   Let `B` be the **exact** ZIP bytes. Compute

   $$
   H = \mathrm{SHA256}(B)\ \ \text{as a 64-char lowercase hex string}.
   $$

   Then write the **ASCII text** `H` to `_passed.flag`. (This makes 1B’s check unambiguous: recompute `SHA256(bundle.zip)` and compare to the **contents** of `_passed.flag`.)

5. **Immutability:** The `validation/fingerprint={F}/` folder is **append-only** for the given fingerprint. If any S9 step fails, the bundle may still be written for diagnostics, but `_passed.flag` **must not** be written.

---

## 4) Reference pack-and-sign algorithm (normative pseudocode)

```pseudo
INPUT:
  seed, parameter_hash, manifest_fingerprint, run_id
  payloads:
    - schema_checks.json
    - key_constraints.json
    - rng_accounting.json
    - metrics.csv
    - diffs/* (zero or more CSV files)

OUTPUT:
  data/layer1/1A/validation/fingerprint={manifest_fingerprint}/bundle.zip
  data/layer1/1A/validation/fingerprint={manifest_fingerprint}/_passed.flag  # only on success

# 1) Assemble index rows
IDX := [
  ("schema_checks","table","schema_checks.json","application/json",null),
  ("key_constraints","table","key_constraints.json","application/json",null),
  ("rng_accounting","table","rng_accounting.json","application/json",null),
  ("corridor_metrics","table","metrics.csv","text/csv",null)
] + [("diff_"+name,"diff","diffs/"+name,"text/csv",null) for name in list_diffs()]

# 2) Validate index against schemas.1A.yaml#/validation/validation_bundle.index_schema
assert jsonschema_validate(IDX, "validation_bundle.index_schema")

# 3) Canonical ZIP assembly (UTF-8 names, sorted by 'path', fixed compression)
files := ["index.json"] + [row.path for row in sort_by_path(IDX)]
B := zip_bytes(files, compression="deflate", level=POLICY_LEVEL, sort_names=true)

# 4) Compute digest and write flag (only if all S9 gates passed)
H := sha256_hex(B)  # 64-char lowercase hex
write_file(".../validation/fingerprint={F}/bundle.zip", B)
write_text(".../validation/fingerprint={F}/_passed.flag", H)
```

This matches the “minimal reference algorithm” captured in the expanded S9.7 notes (index build, schema check, canonical ZIP, SHA-256, write flag).

---

## 5) Failure semantics (when the flag must NOT be written)

**Hard fail ⇒ no flag:**

* Any **schema** or **key/FK** violation (S9.3).
* Any **cross-dataset equality** failure (S9.4), including conservation, coverage, home mismatch, residual/rank mismatches, or Gumbel-order mismatch.
* Any **RNG lineage** breach or replay mismatch (S9.5).
* Any **corridor** breach (S9.6).

In these cases, the ZIP bundle **still materialises** (for diagnostics), but `_passed.flag` is **withheld**. Evidence files referenced by `index.json` support triage (`diffs/*.csv`, `rng_accounting.json`, etc.).

---

## 6) What exactly goes into the bundle (minimum viable set)

* `index.json` — authoritative map of artefacts (table as specified).
* `schema_checks.json` — dataset→JSON-Schema validations; include counts and pointers.
* `key_constraints.json` — PK/UK/FK proofs and any duplicates.
* `rng_accounting.json` — per-label draw accounting, counter deltas, and replay spot-checks (with reproducible `(seed,counter)` tuples on failure).
* `metrics.csv` — corridor metrics (π gap, LRR L1 max, sparsity rate gap, ZTP acceptance), with thresholds echoed.
* `diffs/*.csv` — reproducible diffs for any mismatches (e.g., `residual_rank_mismatch.csv`, `conservation.csv`, `coverage.csv`, `sequence.csv`).

The registry entry for `validation_bundle_1A` confirms location and role (and that this bundle/flag pair is the basis for the hand-off gate).

---

## 7) Hand-off to 1B (defence-in-depth preflight)

1B **must** perform the following checks **before** reading egress for a given `(seed, fingerprint)`:

1. **Partition lineage echo (cheap row check).** Open `outlet_catalogue/seed={seed}/fingerprint={F}` and assert a sampled row has `manifest_fingerprint == F`. If not, abort.
2. **Validation proof.** In `.../validation/fingerprint={F}/`, assert:

   * `bundle.zip` exists; compute `H' = SHA256(bundle.zip)`.
   * `_passed.flag` exists; read its **text** `H_flag`.
   * Require `H' == H_flag`. If not equal or missing, abort.
3. **Read policy reminder.** Even after the gate passes, **egress does not encode cross-country order**; if 1B needs it, it **must** join `country_set.rank` (`seed, parameter_hash`).

Both the **artefact registry** and the **data dictionary** restate this consumption rule (“verify `_passed.flag` matches SHA256(bundle) for the same fingerprint before reading”).

### 1B preflight pseudocode

```pseudo
function preflight_read_L1A(seed, fingerprint, parameter_hash):
    # (1) lineage echo on egress
    r := read_one_row("outlet_catalogue", seed, fingerprint)
    assert r.manifest_fingerprint == fingerprint

    # (2) validation proof
    B := read_bytes("validation/fingerprint={fingerprint}/bundle.zip")
    H_prime := sha256_hex(B)
    H_flag  := read_text ("validation/fingerprint={fingerprint}/_passed.flag").strip()
    assert H_prime == H_flag

    # (3) proceed; remember to join country_set.rank for cross-country order
    OUT := read_table("outlet_catalogue", seed, fingerprint)
    CST := read_table("country_set", seed, parameter_hash)
    return (OUT, CST)
```

---

## 8) Error taxonomy specific to S9.7

* `s9.7.index_schema_violation` — `index.json` fails `validation_bundle.index_schema`. **Hard fail; no flag.**
* `s9.7.bundle_write_error` — I/O error while writing `bundle.zip`; abort and record.
* `s9.7.flag_write_on_fail` — guard to prevent flag creation if **any** upstream check failed (defensive assertion).
* `s9.7.flag_mismatch_at_consumer` — 1B preflight finds `SHA256(bundle) ≠ contents(_passed.flag)`; 1B must abort read. (Dictionary/registry require this gate.)

---

## 9) Conformance tests (must pass)

1. **Happy path:** Construct a run where S9.3–S9.6 all pass. Expect: ZIP with deterministic bytes (`H` stable across re-runs), `_passed.flag` written containing exactly `H`, and 1B preflight succeeds.
2. **Bundle-only on failure:** Force a corridor breach (e.g., ZTP acceptance out of band). Expect: bundle exists (with `metrics.csv` and diffs) but **no** `_passed.flag`. 1B preflight must fail.
3. **Index schema violation:** Remove `mime` on a required row if the schema mandates it (or break `kind`). Expect: `s9.7.index_schema_violation`; no flag.
4. **Consumer defence:** Corrupt `_passed.flag` by changing one nibble; 1B preflight must fail at the equality check and refuse to read egress. Policy satisfied.

---

## 10) Operational notes

* **Provenance recording.** Include the run lineage `(seed, parameter_hash, manifest_fingerprint, run_id)` and validator code commit in `index.json.notes` or a `README.txt` inside the ZIP to aid audits.
* **Registry wiring.** `validation_bundle_1A` and `validation_passed_flag` entries bind paths, ownership, and the gate semantics; `outlet_catalogue`’s notes re-state the must-verify rule for consumers.
* **Immutability.** For a given `fingerprint`, the only valid release states are:
  (a) **bundle + flag** (authorized), or (b) **bundle only** (blocked). No other state is permitted.

---

This locks **S9.7**: exact bundle contents and index schema; deterministic ZIP rules; the SHA-256 signing step; precise write/withhold rules; the consumer preflight algorithm; error taxonomy; and conformance tests — all aligned with the locked S9 text, the expanded notes, and your artefact registry & data dictionary.

---

# S9.8 — Failure semantics

This section specifies **exact decision logic** for the S9 validator, the **severity classes**, **machine error codes**, **evidence mapping**, **bundle/flag write rules**, and **idempotence**. It is the single source of truth for when `_passed.flag` is written or withheld, and how 1B must interpret the outcome. The rules below **bind** to the locked S9 text and your registry/dictionary.

---

## 1) Scope & contract (what S9.8 governs)

* **Inputs:** pass/fail outcomes and artefacts produced by S9.3 (structural), S9.4 (cross-dataset equalities), S9.5 (RNG lineage & replay), and S9.6 (corridors), plus the bundle packer from S9.7.
* **Outputs:**

  * On **success**: `bundle.zip` **and** `_passed.flag` whose **contents equal `SHA256(bundle.zip)`**.
  * On **failure**: `bundle.zip` only (full diagnostics); **no** `_passed.flag`.
    These are written under `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`.

**Authoritative rule:** **Any** schema/keys/FK violation, RNG lineage/replay mismatch, cross-dataset equality failure, or corridor breach is a **hard fail**: bundle materialises, flag is withheld. Numerical diagnostics (Wilson CI, z-scores, model deltas) are **record-only** and never gate release.

---

## 2) Severity classes (closed set)

### A. Hard fail (release blocked; no hand-off)

Triggers (any one is sufficient):

1. **Structural / schema**: JSON-Schema breach in `outlet_catalogue`, `country_set`, or `ranking_residual_cache_1A`; partition echo mismatch; PK/UK duplicates; ISO FK breach. Evidence: `schema_checks.json`, `key_constraints.json`.
2. **RNG lineage / replay**: RNG audit mismatch; missing required label streams; counter-advance ≠ declared draws; replay mismatch for `gumbel_key` or `dirichlet_gamma_vector`. Evidence: `rng_accounting.json`.
3. **Cross-dataset equalities**:
   $\sum_i n_{m,i}\ne N_m^{\text{raw}}$, `country_set` coverage/home mismatch, `site_id ≠ zpad6(site_order)`, missing `sequence_finalize`. Evidence: `diffs/*`.
4. **Corridors**: any corridor outside configured bounds (hurdle gap; LRR L1 guard; sparsity rate gap; ZTP acceptance). Evidence: `metrics.csv`.

**Outcome:** write **bundle only**; do **not** write `_passed.flag`. 1B must not read egress without a matching flag for this fingerprint.

### B. Soft warn (record-only)

Non-structural numerical guards that **do not** contradict exact contracts. Example: LRR L1 guard exceeded while **conservation holds** and residual/rank checks pass. These are recorded in `metrics.csv` and may be escalated by policy, but they **do not** block the flag under the current S9 charter.

---

## 3) Error taxonomy (machine codes & evidence map)

| Class           | Code (prefix `s9.*`)                                                                              | Typical trigger                                            | Evidence in bundle                       |
|-----------------|---------------------------------------------------------------------------------------------------|------------------------------------------------------------|------------------------------------------|
| Structural      | `s9.3.schema_violation.*`                                                                         | JSON-Schema mismatch                                       | `schema_checks.json`                     |
| Keys/FK         | `s9.3.pk_duplicate.*`, `s9.3.fk_iso_breach`                                                       | PK dup; ISO not in canonical set                           | `key_constraints.json`                   |
| Partition echo  | `s9.3.partition_echo_mismatch`                                                                    | Row echo ≠ directory token                                 | `schema_checks.json` (echo section)      |
| RNG envelope    | `s9.5.ERR_RNG_ALGO_MISMATCH`, `s9.5.ERR_RNG_SEED_MISMATCH`                                        | Audit algo/seed mismatch                                   | `rng_accounting.json` (header)           |
| Draw accounting | `s9.5.ERR_COUNTER_ADVANCE_MISMATCH[ℓ]`                                                            | $\Delta C_\ell \ne \sum \text{draws}$                      | `rng_accounting.json` (per-label)        |
| Replay          | `s9.5.ERR_REPLAY_MISMATCH[ℓ]`                                                                     | Gumbel/Dirichlet payload regen mismatch                    | `rng_accounting.json` (reproducer tuple) |
| Equalities      | `s9.4.mass_not_conserved`                                                                         | $\sum_i n_{m,i}\ne N_m^{\text{raw}}$                       | `diffs/conservation.csv`                 |
| Coverage/home   | `s9.4.country_set_coverage`, `s9.4.country_set_home_mismatch`, `s9.4.country_set_rank_contiguity` | Egress outside set; home ISO mismatch; rank gaps           | `diffs/coverage.csv`                     |
| Sequencing      | `s9.4.site_id_mismatch`                                                                           | `site_id ≠ zpad6(site_order)`; missing `sequence_finalize` | `diffs/sequence.csv`                     |
| Corridors       | `s9.6.corridor_breach_*`                                                                          | hurdle/LRR/sparse/ZTP out-of-band                          | `metrics.csv` (with thresholds)          |

The bundle content & index format are fixed by S9.7 and the registry. Do **not** invent additional required files.

---

## 4) Canonical decision routine (reference; all gates)

This is the **only** allowed release decision algorithm. It consumes the outcomes from S9.3–S9.6 and controls the S9.7 writer.

```pseudo
function s9_8_decide_and_emit(results, pack_bundle):
    # results: Booleans and soft warning list from prior stages
    with results as {
        schema_pass, keys_pass, fk_pass,
        rng_envelope_pass, rng_accounting_pass, rng_replay_pass,
        eq_conservation_pass, eq_coverage_pass, eq_site_id_pass,
        corridors_pass, soft_warnings
    }:

        # 1) Hard-fail groups (short-circuit on first failure class for exit code)
        if not (schema_pass and keys_pass and fk_pass):
            pack_bundle(write_flag=false, failure_class="structural")
            return EXIT_STRUCTURAL_FAIL

        if not (rng_envelope_pass and rng_accounting_pass and rng_replay_pass):
            pack_bundle(write_flag=false, failure_class="rng_lineage")
            return EXIT_RNG_FAIL

        if not (eq_conservation_pass and eq_coverage_pass and eq_site_id_pass):
            pack_bundle(write_flag=false, failure_class="equalities")
            return EXIT_EQUALITIES_FAIL

        if not corridors_pass:
            pack_bundle(write_flag=false, failure_class="corridors")
            return EXIT_CORRIDOR_FAIL

        # 2) Success path
        H = pack_bundle(write_flag=true, failure_class=null)   # writes bundle.zip; computes SHA256; writes _passed.flag=H
        emit_summary(stdout, { status:"PASS", sha256:H, soft_warnings })
        return EXIT_OK
```

**Notes (binding):**

* `pack_bundle(write_flag)` is the S9.7 canonical pack-and-sign step; on `write_flag=true` it **must** write `_passed.flag` whose **contents equal `SHA256(bundle)`**; on `false`, it **must not** write the flag.
* Exit codes map to CI but **do not** affect the bundle write on failure (bundle always written).

---

## 5) Idempotence, determinism, and concurrency

* **Idempotence:** Re-running S9 with the same inputs must reproduce **byte-identical** `bundle.zip` (UTF-8 names, lexicographic entry order, fixed compression), hence the same `_passed.flag`.
* **Immutable target:** For a given `fingerprint`, only two valid end states exist: **(a)** bundle + flag, or **(b)** bundle only. No other state is valid. Never overwrite a flag for the same `fingerprint`.
* **Concurrency guard (implementation tip):** If multiple workers may attempt S9 concurrently, write the bundle to a temp name, fsync, then atomically rename; write `_passed.flag` last on success. (Advisory; consistent with the immutable-folder rule.)

---

## 6) What 1B must do on consumption (reaffirmed)

Before reading `outlet_catalogue(seed,fingerprint)`, 1B must: compute `SHA256(bundle.zip)` in `…/validation/fingerprint={fingerprint}/`, read `_passed.flag`, and require equality. If missing or unequal, 1B **must** abort. (Inter-country order is **only** in `country_set.rank`; never infer it from egress.)

---

## 7) Conformance tests (negative & edge)

1. **Schema failure path:** Introduce a row with `site_id="ABC123"`. Expect `s9.3.schema_violation.outlet_catalogue`, bundle written, **no** flag; decision exits `EXIT_STRUCTURAL_FAIL`.
2. **RNG counter drift:** Increment `draws` for `gumbel_key` by 1 in the trace. Expect `s9.5.ERR_COUNTER_ADVANCE_MISMATCH[gumbel_key]`, bundle only, **no** flag; `EXIT_RNG_FAIL`.
3. **Conservation breach:** Set `final_country_outlet_count=3` but realise 2 rows for `(m,GB)`. Expect `s9.4.mass_not_conserved`, bundle only; `EXIT_EQUALITIES_FAIL`.
4. **Corridor breach:** Force ZTP acceptance to 0.1 when corridor is `[0.3,0.7]`. Expect `s9.6.corridor_breach_ztp_rate`, bundle only; `EXIT_CORRIDOR_FAIL`.
5. **Soft warn only:** Keep conservation exact; perturb shares to push LRR L1 max slightly over $\varepsilon_{\text{LRR}}$ while residual cache & ranks still match. Expect: **PASS** with `soft_warnings` recorded; bundle+flag written.

---

## 8) Operator runbook (remediation pointers)

* **Structural:** re-emit bad partitions with correct schema & partition echoes; repair ISO mapping; re-run S9.
* **RNG lineage:** ensure required labels exist; fix counter accounting and replay payloads; re-validate.
* **Equalities:** inspect S7 integerisation & S8 write; verify `country_set` is the **only** cross-country order carrier.
* **Corridors:** review thresholds in governed config (not code); triage drift on hurdle/ZTP monitoring.

---

## 9) CI wiring (exit codes & logs)

* `EXIT_OK=0`, `EXIT_STRUCTURAL_FAIL=10`, `EXIT_RNG_FAIL=20`, `EXIT_EQUALITIES_FAIL=30`, `EXIT_CORRIDOR_FAIL=40`.
* Always emit the bundle with `index.json`, `schema_checks.json`, `key_constraints.json`, `rng_accounting.json`, `metrics.csv`, and any `diffs/*`. S9.7 then computes and writes `_passed.flag` **only** on success.

---

**Summary:** S9.8 formalises a **binary gate** driven by S9.3–S9.6: on any hard-fail trigger, **bundle only**; on full pass, **bundle + `_passed.flag`** (flag = SHA-256 of the bundle). This exactly matches the locked S9 and registry contracts and keeps the 1A→1B hand-off cryptographically safe.

---

# S9.9 — Hand-off to 1B (consumer contract)

This section specifies exactly **when and how 1B may consume** the 1A egress, the **preflight gate** it must run, the **join rules** for country order, the **error taxonomy** 1B should raise, and **reference code**. It binds to the locked S9 text, the combined state-flow, the artefact registry, the data dictionary, and the schemas.

---

## 1) Purpose & immutable contract (what S9.9 governs)

1B is authorized to read `outlet_catalogue(seed, fingerprint)` **iff**:

* A **validation bundle** exists at `data/layer1/1A/validation/fingerprint={fingerprint}/bundle.zip`, **and**
* The co-located **_passed.flag** file’s **contents** equal `SHA256(bundle.zip)`.

This is the **binary gate**: without a matching flag for that `fingerprint`, 1B must not read the egress. The dictionary and state spec encode this consumption rule, and it is reiterated here as mandatory consumer behavior.

> **Important:** Egress **does not encode inter-country order**; 1B **must** join `country_set.rank` to obtain cross-country sequencing. `country_set` is the **only** authority for that order.

---

## 2) Inputs & authorities (consumption scope)

* **Egress (immutable, read-only):**
  `outlet_catalogue/seed={seed}/fingerprint={fingerprint}` with schema `schemas.1A.yaml#/egress/outlet_catalogue`. PK & physical order: `(merchant_id, legal_country_iso, site_order)`. **Inter-country order not present** here.

* **Country order (authoritative, read-only):**
  `country_set/seed={seed}/parameter_hash={parameter_hash}` with schema `#/alloc/country_set`. Column `rank` gives cross-country order (`0 = home; 1..K` foreigns selected by Gumbel). This is the **only** source of inter-country order.

* **Validation proof (read-only):**
  `data/layer1/1A/validation/fingerprint={fingerprint}/bundle.zip` and `_passed.flag` (text equals `SHA256(bundle.zip)`). Index `index.json` inside the bundle conforms to `schemas.1A.yaml#/validation/validation_bundle`.

> **Scope note:** `outlet_catalogue` is partitioned by `{seed, fingerprint}`; `country_set` by `{seed, parameter_hash}`. 1B must therefore know **both** `fingerprint` (which egress to consume) and the **parameter_hash** (which allocation order to join).

---

## 3) Mandatory preflight (1B must run before any read)

1B must perform the following **in order**. Any failure ⇒ **abort**; do **not** read egress.

1. **Egress lineage echo (cheap row check).**
   Open `outlet_catalogue(seed, fingerprint)` and assert a sampled row’s `manifest_fingerprint == {fingerprint}`. If not, abort.

2. **Validation proof.**
   Read `bundle.zip`, compute `H' = SHA256(bytes)`. Read `_passed.flag` text `H_flag`. Require `H' == H_flag`. If missing or unequal, abort.

3. **Country-order source availability.**
   Ensure `country_set(seed, parameter_hash)` exists (for the **parameter_hash** that 1B is configured to consume). If missing, abort. (1B cannot legally infer order from egress.)

4. **Bundle index sanity (defence-in-depth).**
   Optionally (recommended): parse `index.json` inside the bundle and validate it against the `validation_bundle.index_schema`; log discrepancies though the flag equality is the hard gate.

---

## 4) Join semantics (how 1B must obtain cross-country order)

**Join key:** `(merchant_id, legal_country_iso)`; **scopes:** same `seed`, egress uses `fingerprint`, order uses `parameter_hash`.

**Allowed join:** **inner join** egress → `country_set` (since S9.4 guarantees every egress `(m,i)` is in `country_set`). The join adds `rank` to every outlet row; **never** compute a rank from egress heuristics.

**Presentation/processing order (if needed):**

* Primary: `rank` ascending (0, 1, 2, …).
* Secondary: `site_order` ascending within `(m, i)`.
* Tertiary (ties only within diagnostics): `legal_country_iso` ascending (deterministic display).
  This mirrors how S7/S9 define cross-country then within-country sequencing.

**Example SQL (reference):**

```sql
WITH egress AS (
  SELECT * FROM outlet_catalogue
  WHERE seed = :seed AND fingerprint = :fingerprint
),
cset AS (
  SELECT merchant_id, country_iso AS legal_country_iso, rank
  FROM country_set
  WHERE seed = :seed AND parameter_hash = :parameter_hash
)
SELECT
  e.merchant_id,
  e.legal_country_iso,
  c.rank                  AS country_rank,    -- authoritative order
  e.site_order,                               -- within-country sequence
  e.site_id, e.raw_nb_outlet_draw, e.single_vs_multi_flag, e.home_country_iso
FROM egress e
JOIN cset  c
  ON (e.merchant_id = c.merchant_id AND e.legal_country_iso = c.legal_country_iso)
ORDER BY e.merchant_id, c.rank, e.site_order;
```

This ordering is **advisory** for consumers that render lists; correctness only depends on joining `rank`.

---

## 5) Materialization & lineage (recommended downstream table)

If 1B persists a derived table, it **must** carry the lineage keys and joined order:

* **Required columns:**
  `seed`, `fingerprint`, `parameter_hash`, `merchant_id`, `legal_country_iso`,
  `country_rank`, `site_order`, `site_id`, plus the needed outlet attributes.
* **Primary key:** `(merchant_id, legal_country_iso, site_order)` **scoped by** `{seed, fingerprint}`.
* **Check constraints:** `country_rank >= 0`, `site_order >= 1`, `site_id ~ '^[0-9]{6}$'`.
* **Join provenance:** store the exact `parameter_hash` used for the join.
  These echo S9 PK/range/regex checks and make misuse detectable downstream.

---

## 6) Caching & scope hygiene (how not to mix scopes)

* It’s valid to **cache** `country_set(seed, parameter_hash)` and reuse it across different `fingerprint`s that share the same `seed` & `parameter_hash`.
* It is **invalid** to mix `country_set` from one `parameter_hash` with egress from another; the dictionary explicitly separates these scopes. 1B must thread both keys.

---

## 7) Consumer error taxonomy (machine codes & actions)

1B should fail closed with explicit errors:

| Code                                  | Trigger                                                                                   | Action                                                           |
| ------------------------------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `consumer.flag_missing`               | `_passed.flag` absent for the `fingerprint`                                               | Abort read; require ops to run S9.                               |
| `consumer.flag_mismatch`              | `SHA256(bundle.zip) ≠ contents(_passed.flag)`                                             | Abort; flag corruption or wrong bundle.                          |
| `consumer.egress_lineage_mismatch`    | Sampled row’s `manifest_fingerprint ≠ fingerprint`                                        | Abort; wrong partition.                                          |
| `consumer.country_set_missing`        | `country_set(seed, parameter_hash)` not found                                             | Abort; cannot infer order.                                       |
| `consumer.scope_mismatch`             | Read egress with `(seed,fingerprint)` but joined `country_set` with different `seed`      | Abort; scope violation.                                          |
| `consumer.invalid_join_multiplicity`  | Join introduces dup/missing rows                                                          | Abort; indicates upstream breach (should be impossible post-S9). |
| `consumer.order_inferred_from_egress` | Using ISO/name to imply order instead of `rank` (detect via code review or runtime guard) | Block release; policy violation.                                 |

These codes align with the gate semantics in S9 and the “only read after verifying flag” rule in the dictionary.

---

## 8) Reference preflight loader (language-agnostic pseudocode)

```pseudo
function load_L1A_for_1B(seed, fingerprint, parameter_hash):
  # (1) lineage echo
  row := read_one("outlet_catalogue", seed, fingerprint)
  assert row.manifest_fingerprint == fingerprint, "consumer.egress_lineage_mismatch"

  # (2) validation proof
  B := read_bytes(".../validation/fingerprint={fingerprint}/bundle.zip")
  H_prime := sha256_hex(B)
  H_flag  := read_text (".../validation/fingerprint={fingerprint}/_passed.flag").strip()
  assert H_prime == H_flag, "consumer.flag_mismatch"

  # (3) source datasets
  OUT := read_table("outlet_catalogue", seed, fingerprint)
  CST := read_table("country_set", seed, parameter_hash)
  assert CST is not None, "consumer.country_set_missing"

  # (4) join & optional materialization
  T := OUT ⨝ CST on (merchant_id, legal_country_iso)   # add country_rank
  # Optional downstream PK & constraints enforcement here
  return T
```

This mirrors the S9.7 preflight and the consumption notes in the state spec.

---

## 9) Conformance tests (consumer-side; must pass)

1. **Happy path:** With a valid bundle+flag pair and matching `fingerprint`, loader joins `country_set` and returns rows ordered by `(rank, site_order)`. ✔︎
2. **Missing flag:** Delete `_passed.flag` → `consumer.flag_missing`. Loader must not read egress. ✔︎
3. **Flag mismatch:** Flip one hex nibble in `_passed.flag` → `consumer.flag_mismatch`. ✔︎
4. **Wrong parameter_hash:** Point loader at a different `parameter_hash` → `consumer.scope_mismatch` (or `country_set_missing` if absent). ✔︎
5. **Order inference attempt:** Remove the join and sort by ISO to mimic order → detect during review or via runtime guard; reject with `consumer.order_inferred_from_egress`. ✔︎

---

## 10) Operational notes for 1B

* **Defence-in-depth:** Even though S9 validated everything, 1B still verifies the flag against the bundle and echoes `fingerprint` from a row. This prevents stale or tampered reads.
* **Reproducibility:** The bundle’s `index.json` (schema-checked) can be logged by 1B for audit; it does not change the gate decision (which depends only on SHA-256 equality).
* **Ordering reminder:** Any consumer that needs cross-country order must join `country_set.rank`. This policy is restated in both the dictionary entry for `outlet_catalogue` and in S9.9’s contract.

---

### Why this is “100%”

* Exact **gate condition** and **cryptographic equality** to authorize consumption.
* Full **preflight algorithm**, **join semantics**, **lineage carrying**, **scope hygiene**, and **error taxonomy** for 1B.
* **Reference SQL** and loader pseudocode that mirror the locked S9/S7 contracts (no inter-country order in egress; only `country_set.rank`).

This completes **S9.9** and closes the S9 series end-to-end, ready for direct hand-off to implementation.

---

# S9.10 — Numeric-determinism checks (policy enforcement)

This section turns the **governed numeric policy** for 1A (binary64, FMA-off, serial reductions, 8-dp residual quantisation) into **executable validations** over the artefacts already written in S5/S7 and the RNG evidence streams. It produces **hard pass/fail outcomes** plus machine-readable diagnostics that land in the **validation bundle** (see S9.7) and gate the 1A→1B hand-off (S9.9).

---

## 1) Scope & contract

**What S9.10 proves**

1. **S5 cache invariants (currency→country weights):** renormalisations and sparse equal-split respect the governed arithmetic (binary64, serial, compensated sum) and the **sum-to-one** target.
2. **S7 Dirichlet + LRR invariants (per merchant):** event-logged gamma vectors normalise correctly; the **quantised** residuals (`Q8`, ties-to-even, pre-sort) reproduce the **published residual ranks**; this implies the deterministic LRR integerisation path was numerically respected.
3. **Environment coherence:** the run’s manifest/registry declares the same numeric policy (e.g., `residual_quantisation_policy` digest) as the validator expects. A mismatch is a **hard fail**.

**Outputs into the bundle (S9.7):**

* `metrics.csv` rows for sum-to-one deltas, equal-split max error, and residual-rank reproducibility rate.
* `rng_accounting.json` echoes per-label coverage and embeds the “numeric-policy” header (doc digests, compile flags, FTZ/DAZ toggles if captured).

**Hard-fail rule:** Any numeric-determinism check below that fails ⇒ **bundle only**, do **not** write `_passed.flag`. (This is an S9 hard gate.)

---

## 2) Governing definitions (normative)

### 2.1 Arithmetic model (re-stated, binding)

All operations that **feed ordering or integerisation** execute in IEEE-754 **binary64**, **roundTiesToEven**, **FMA disabled**, **serial reductions** in a fixed order. Denormals/subnormals are **not** flushed-to-zero. These toggles are part of the artefact set; changing them flips the **manifest_fingerprint**.

We denote correctly-rounded binary64 evaluation of an expression \$\psi\$ by \$\mathrm{R}_{64}\[\psi]\$. Implement multiplication and addition as two-step roundings (to avoid accidental FMA):

$$
\text{mul}(a,b)=\mathrm{R}_{64}[a\cdot b],\quad
\text{add}(x,y)=\mathrm{R}_{64}[x+y],\quad
\text{fma_off}(a,b,c)=\mathrm{R}_{64}\!\big(\mathrm{R}_{64}[a\cdot b]+c\big).
\] :contentReference[oaicite:7]{index=7}

### 2.2 Deterministic reducers and quantiser

**Serial reducer (fixed order):** for $v_1,\dots,v_m$,  
\[
S_0=0,\quad S_i=\text{add}(S_{i-1},v_i)
$$

with the loop order explicitly specified per check (country rank, then ISO). For S7 gamma normalisation, S0.8 prefers **Neumaier compensated sum** in that exact order (validator may recompute both plain and compensated for diagnostics).

**8-dp residual quantiser (`Q8`) used for ranking:**

$$
Q_8(x)=\mathrm{R}_{64}\!\left(\mathrm{R}_{64}(x\cdot 10^8)/10^8\right),\quad x\in[0,1).
$$

Quantisation error \$\le 5\cdot 10^{-9}+O(2^{-53})\$. Sorting keys must use \$r_i=Q_8(a_i-\lfloor a_i\rfloor)\$ (ties by secondary keys below).

**Sorting key for inter-country residual order (S7):**

$$
\text{key}_i=\big(r_i\ \downarrow,\ \texttt{country_set.rank}\ \uparrow,\ \text{ISO}\ \uparrow\big).
$$

This preserves S6 Gumbel order before ISO within exact ties after quantisation.

---

## 3) What is checked (mathematical statements)

### 3.1 S5 cache groups (per currency \$\kappa\$)

Let \$(w^{(\kappa)}*i)*{i=1}^D\$ be the stored weight vector over the \$D\$ eligible countries for currency \$\kappa\$.

1. **Sum-to-one (internal target):**

$$
\delta_\kappa\ :=\ \Big|\,1-\sum_{i=1}^D w^{(\kappa)}_i\,\Big|
\ \le\ 10^{-12},
$$

where the sum is evaluated via the **serial** Neumaier reducer in **lexicographic country order for \$\kappa\$**. Record \$\delta_\kappa\$ to `metrics.csv`.

2. **Sparse equal-split (if `sparse_flag(κ)=1`):**

$$
\epsilon_\kappa\ :=\ \max_i \Big|\,w^{(\kappa)}_i-\tfrac{1}{D}\,\Big|
\ \le\ 10^{-12}.
$$

Record \$\epsilon_\kappa\$; failing any \$\kappa\$ is a hard fail.

### 3.2 S7 Dirichlet and residual-rank (per merchant \$m\$ with \$|C_m|>1\$)

From the single `dirichlet_gamma_vector` event for \$m\$, retrieve arrays `gamma_raw` \$(G_i)\$ and `weights` \$(w_i)\$ **aligned to `country_set.rank`**.

1. **Normalisation check (event tolerance):**

$$
\bigg|\,1-\sum_{i\in C_m} w_i\,\bigg|\ \le\ 10^{-6}
$$

with the **serial** reducer in `rank` order. (S7’s internal target is tighter: \$10^{-12}\$; the event/schema contract is \$10^{-6}\$ and is the hard gate here; we **also record** the internal re-sum.)

2. **Residual-rank reproducibility (using `Q8`):**
   Compute \$a_i=\mathrm{R}_{64}\[N^{\text{raw}}_m\cdot w_i]\$, \$f_i=\lfloor a_i\rfloor\$, \$r_i=Q_8(a_i-f_i)\$. Sort \$C_m\$ by the **key** above and assert equality to the persisted `ranking_residual_cache_1A.residual_rank` **and** equality of residual values to `residual`. Any mismatch is a **hard fail** with a concrete diff.

3. **Edge case (\$|C_m|=1\$):** require a single `residual_rank` event with residual `0.0` and `rank=1`.

---

## 4) Reference validator (pseudocode; exact order & rounding)

```pseudo
INPUTS:
  # S5 artefacts (currency -> weights) and sparse flags
  S5_WEIGHTS[κ] : array of (country_iso, weight)
  SPARSE_FLAG[κ] : bool
  # S7 evidence
  DIR_EVT[m]  : {country_isos[], gamma_raw[], weights[]}      # one iff |C_m|>1
  RES_CACHE[m,i] : {residual: float, residual_rank: int}      # for all (m,i)
  # Lineage & policy digests
  POLICY_DIGEST.expected : { residual_quantisation_policy_sha256, numeric_env_sha256 }

OUTPUTS:
  metrics.csv rows and diffs/* for any mismatch; hard pass/fail

# --- Helper: serial Neumaier in fixed order
function sum_comp(values, order_keys):
    s = 0.0; c = 0.0
    for x in values sorted by order_keys:
        t = s + x
        if abs(s) >= abs(x): c += (s - t) + x
        else:                c += (x - t) + s
        s = t
    return s + c

# --- 0) Environment coherence
assert manifest_contains_digest("residual_quantisation_policy", POLICY_DIGEST.expected.residual_quantisation_policy_sha256),
       "s9.10.numeric_env_mismatch"
assert manifest_contains_digest("numeric_env", POLICY_DIGEST.expected.numeric_env_sha256),
       "s9.10.numeric_env_mismatch"

# --- 1) S5 checks
for κ in S5_WEIGHTS:
    W = S5_WEIGHTS[κ]                     # [(iso, w), ...]
    δ = abs(1.0 - sum_comp([w for (_,w) in W], order_keys=ISO_ASC))
    record_metric("s5.sum_to_one_delta", κ, δ, threshold=1e-12, passed=(δ<=1e-12))
    assert δ <= 1e-12, "s9.10.s5.sum_to_one_violation:" + κ

    if SPARSE_FLAG[κ]:
        eps = max_i abs(W[i].w - 1.0/len(W))
        record_metric("s5.sparse_equal_split_maxerr", κ, eps, threshold=1e-12, passed=(eps<=1e-12))
        assert eps <= 1e-12, "s9.10.s5.equal_split_violation:" + κ

# --- 2) S7 checks
for m in merchants:
    C = country_set(m)   # [(iso, rank)], authoritative order
    if |C| == 1:
        assert RES_CACHE[m,C[0]].residual == 0.0 and RES_CACHE[m,C[0]].residual_rank == 1,
               "s9.10.s7.single_country_residual_event_missing"
        continue

    E = DIR_EVT[m]; assert E exists and aligns to C in (rank, then ISO)
    sumw = abs(1.0 - sum_comp(E.weights, order_keys=RANK_ASC_THEN_ISO))
    record_metric("s7.dirichlet_sum_to_one_delta", m, sumw, threshold=1e-6, passed=(sumw<=1e-6))
    assert sumw <= 1e-6, "s9.10.s7.dirichlet_sum_to_one_violation"

    Nraw = home_row(outlet_catalogue, m).raw_nb_outlet_draw
    A = [ R64(Nraw * wi) for wi in E.weights ]
    F = [ floor(ai) for ai in A ]
    Rq = [ Q8( R64(ai - fi) ) for (ai,fi) in zip(A,F) ]

    # Build order by (Rq desc, rank asc, ISO asc)
    ORDER = argsort( C, key = ( -Rq[i], C[i].rank, C[i].iso ) )
    for k, i in enumerate(ORDER):
        cache = RES_CACHE[m, C[i].iso]
        assert almost_equal(cache.residual, Rq[i], mode="exact_match_binary64"),
               "s9.10.s7.residual_value_mismatch"
        assert cache.residual_rank == k+1,
               "s9.10.s7.residual_rank_mismatch"
record_metric("s7.residual_rank_repro_rate", "GLOBAL", pass_fraction, threshold=1.0, passed=(pass_fraction==1.0))

# If we reached here, S9.10 passes. Bundle writer (S9.7) will include metrics & any diffs collected.
```

**Notes.**

* The validator **does not** recompute gamma draws; it only uses event payloads and deterministic arithmetic/quantisation to **reproduce** recorded ranks. Evidence comes from `dirichlet_gamma_vector` + `ranking_residual_cache_1A`.
* “Exact match” for residual values means bit-equivalence of the binary64 after `Q8`. (If a store/loader path coerces to decimal then back, that would appear as a schema breach upstream.)

---

## 5) Error taxonomy (machine codes & evidence)

| Code                                             | Meaning                                                                                                 | Evidence written                                                       |                                      |                                 |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------ | ------------------------------- |
| `s9.10.numeric_env_mismatch`                     | Manifest/registry digests for numeric policy don’t match validator’s expected (wrong build or toggles). | `metrics.csv` row + `index.json.notes` summary; bundle only.           |                                      |                                 |
| `s9.10.s5.sum_to_one_violation`                  | Some currency group fails \$\delta_\kappa\le 10^{-12}\$.                                               | `diffs/s5_sum_to_one.csv` (κ, δ).                                      |                                      |                                 |
| `s9.10.s5.equal_split_violation`                 | Sparse equal-split max error \$>10^{-12}\$.                                                             | `diffs/s5_sparse_equal_split.csv` (κ, maxerr, D).                      |                                      |                                 |
| `s9.10.s7.dirichlet_sum_to_one_violation`        | Merchant \$m\$ fails \$\le 10^{-6}\$ check.                                                             | `diffs/s7_dirichlet_sum_to_one.csv` (m, δ).                            |                                      |                                 |
| `s9.10.s7.residual_value_mismatch`               | `Q8` residual differs from cache value.                                                                 | `diffs/s7_residual_value.csv` (m, iso, cache, recomputed).             |                                      |                                 |
| `s9.10.s7.residual_rank_mismatch`                | Sort by `(r, rank, ISO)` does not reproduce `residual_rank`.                                            | `diffs/s7_residual_rank.csv` (m, iso, cache_rank, recomputed_rank).  |                                      |                                 |
| `s9.10.s7.single_country_residual_event_missing` | \$                                                                                                      | C                                                                      | =1\$ but residual event not `0.0/1`. | `diffs/s7_single_country.csv`.  |

All are **hard fails** under S9.8; bundle materialises, `_passed.flag` is withheld.

---

## 6) Recording to the bundle (schema hooks)

* Append to `metrics.csv` the rows:
  `("s5.sum_to_one_delta", κ, δ, 1e-12, passed)`,
  `("s5.sparse_equal_split_maxerr", κ, ε, 1e-12, passed)`,
  `("s7.dirichlet_sum_to_one_delta", m, δ, 1e-6, passed)`,
  `("s7.residual_rank_repro_rate","GLOBAL",p,1.0,passed)`.
  (Column names follow the validation bundle table spec.)
* Emit CSV diffs listed in the table above under `diffs/*.csv`; index them in the bundle’s `index.json` (S9.7).
* Add a short `text` artefact in `index.json` noting the numeric-policy digests used for the run.

---

## 7) Conformance tests (must pass)

1. **Happy path (reference build):** All S5 groups satisfy \$\delta_\kappa\le 10^{-12}\$; all sparse groups satisfy \$\epsilon_\kappa\le 10^{-12}\$; all merchants reproduce residual ranks. Expect bundle+flag.
2. **Perturbed rounding mode:** Force residual rounding to 7 dp in a test build. Validator must produce `s9.10.s7.residual_value_mismatch` and withhold the flag. (Demonstrates `Q8` sensitivity.)
3. **Parallel reduction drift:** Replace Neumaier with parallel sum; tiny \$\delta_\kappa>10^{-12}\$ should trigger `s9.10.s5.sum_to_one_violation`.
4. **FTZ/DAZ toggle:** If runtime logged FTZ=ON, mark `numeric_env_mismatch` unless the manifest declares such policy and the validator expects it. (Environment coherence.)
5. **Single-country merchant:** Remove the required residual event; expect `s9.10.s7.single_country_residual_event_missing`.

---

## 8) Relationship to other S9 gates (non-duplication)

* **S9.3** enforces schema/keys/FKs.
* **S9.4** proves conservation, coverage, `site_id=zpad6(site_order)`, and reproduces LRR structure.
* **S9.5** handles RNG lineage/counter accounting.
* **S9.6** enforces corridors.
  **S9.10** specifically enforces the **numeric policy** used to reach those outcomes (sum-to-one with governed reducers; exact `Q8` residuals & ordering) and therefore catches silent drift that could otherwise pass the structural gates.

---

## 9) Why this is “100%”

You have: formal definitions and tolerances; fixed evaluation order; complete pseudocode; precise error taxonomy with evidence artefacts; bundle wiring; and a conformance suite — all tied to the locked S9 text, S0.8/S7 numeric policy, and the artefact registry’s policy digests.

---