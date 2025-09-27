# 0) One-page quick map (for implementers)

## 0.1 What S3 does (one breath)

Given a gated **multi-site** merchant with accepted outlet count **N** from S2, **S3 deterministically builds the cross-border candidate country universe and its total order** (an ordered list with reasons/tags and, if enabled, deterministic base-weight priors). **S3 uses no RNG.** If your design keeps integerisation in S3, it converts priors to **integer per-country counts** that sum to **N** using the fixed largest-remainder discipline.

---

## 0.2 Inputs → Outputs (at a glance)

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

## 0.3 Bill of Materials (IDs only; no paths)

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

## 0.4 Control gates & invariants (must hold to run)

* **Presence gate:** exactly one S1 hurdle row and **`is_multi == true`** for the merchant.
* **S2 gate:** exactly one **`nb_final`** with **`N ≥ 2`** for the same `{seed, parameter_hash, run_id, merchant}`.
* **Artefact gates:** rule ladder + static refs **loaded atomically** with pinned versions/digests.
* **No RNG:** S3 defines **no RNG families** (no labels, no budgets, no envelopes).
* **Ordering law:** **`candidate_rank(home) = 0`**, ranks are **total** and **contiguous**; **no duplicates**.

---

## 0.5 Outputs (authoritative, dictionary-partitioned)

**Required**

* `s3_candidate_set` — rows:
  `merchant_id`, `country_iso`, **`candidate_rank`**, `reason_codes[]`, `filter_tags[]`, lineage fields.
  **Partition:** `{parameter_hash}`. Embedded lineage: `parameter_hash`; `produced_by_fingerprint?` (optional provenance).
  **Row order guarantee:** `(merchant_id, candidate_rank, country_iso)`.

**Optional (enable only if S3 owns them)**

* `s3_base_weight_priors` — deterministic, quantised priors (dp is fixed in §12; **not probabilities**).
* `s3_integerised_counts` — integer counts per country with `residual_rank` if S3 performs integerisation (else defer downstream).

---

## 0.6 Definition of Done (tick before leaving S3)

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

# 1) Interfaces (hard contracts)

## 1.1 Upstream interface (read-only)

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

## 1.2 Downstream interface (egress S3 produces)

**Purpose:** define exactly what S3 emits and how consumers must read it. Consumers **must not** infer or reinterpret beyond this.

### 1.2.1 Required: ordered candidate set

| Dataset id         | JSON-Schema anchor                  | Partitions (path)    | Embedded lineage (columns)                                | Row order                                                                                      | Columns (name : type : semantics)                                                                                                                                                                                                                                                                                                 |
|--------------------|-------------------------------------|----------------------|-----------------------------------------------------------|------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `s3_candidate_set` | `schemas.1A.yaml#/s3/candidate_set` | `parameter_hash={…}` | `parameter_hash:hex64`, `produced_by_fingerprint?:hex64`  | **Row ordering guarantee (logical):** `(merchant_id ASC, candidate_rank ASC, country_iso ASC)` | `merchant_id:u64` — key; `country_iso:string(ISO-3166-1)` — candidate; **`candidate_rank:u32`** — **total, contiguous order** with `candidate_rank==0` for home; `reason_codes:array<string>` — **closed set** from policy; `filter_tags:array<string>` — deterministic tags (**closed set** defined by policy); lineage as above |

**Contract:**

* **Total order:** `candidate_rank` is total and contiguous per merchant; **no duplicates**; **`candidate_rank(home)=0`**.
* **No priors here:** deterministic priors (if enabled) are emitted only in **`s3_base_weight_priors`** (§12.3).
* **Single authority for inter-country order:** downstream **must use `candidate_rank` only** (never file order or ISO).

### 1.2.2 Optional: deterministic base-weight priors (if enabled)

| Dataset id              | JSON-Schema anchor                       | Partitions           | Embedded lineage                             | Row order                    | Columns                                                                                                           |
|-------------------------|------------------------------------------|----------------------|----------------------------------------------|------------------------------|-------------------------------------------------------------------------------------------------------------------|
| `s3_base_weight_priors` | `schemas.1A.yaml#/s3/base_weight_priors` | `parameter_hash={…}` | `parameter_hash`, `produced_by_fingerprint?` | `(merchant_id, country_iso)` | `merchant_id:u64`, `country_iso:string`, `base_weight_dp:decimal(string)`, `dp:u8` (quantisation places), lineage |

**Contract:** evaluation order and quantisation **dp** fixed in §12; consumers treat as **deterministic scores** only.

### 1.2.3 Optional: integerised counts (if S3 performs integerisation)

| Dataset id              | JSON-Schema anchor                       | Partitions           | Embedded lineage                             | Row order                    | Columns                                                                                                              |
|-------------------------|------------------------------------------|----------------------|----------------------------------------------|------------------------------|----------------------------------------------------------------------------------------------------------------------|
| `s3_integerised_counts` | `schemas.1A.yaml#/s3/integerised_counts` | `parameter_hash={…}` | `parameter_hash`, `produced_by_fingerprint?` | `(merchant_id, country_iso)` | `merchant_id:u64`, `country_iso:string`, `count:i64 (≥0)`, `residual_rank:u32` (largest-remainder tie rank), lineage |

**Contract:**

* Per merchant, `Σ count = N` from S2.
* `residual_rank` captures the exact bump order (quantised residuals + ISO tiebreak) and is **persisted**.

---

## 1.3 Immutability & non-reinterpretation (binding)

**What S3 must not reinterpret**

* **Upstream decisions:** S1 hurdle (`is_multi`) and S2 `nb_final.n_outlets` are **authoritative**; S3 **must not** recompute or override them.
* **Upstream numerics:** inherit S0 numeric policy (binary64, RNE, FMA-off, no FTZ/DAZ).

**What downstream must not reinterpret**

* **Inter-country order:** lives **only** in `s3_candidate_set.candidate_rank`.
* **Priors (if any):** `base_weight_dp` are deterministic **priors**, not probabilities; consumers must not normalise or treat them as stochastic unless a later state explicitly says so.
* **Integerised counts (if emitted):** are **final for S3**; later stages treat them as read-only unless a new fingerprint changes.

**Partition ↔ embed equality (write side)**

* Each S3 row **embeds** `parameter_hash` (must **byte-equal** the path). If present, `produced_by_fingerprint` is informational and has no equality/partition role.

**No paths in code**

* All IO resolves via the **dataset dictionary**. This spec names **dataset IDs and schema anchors only**.

---

# 2) Bill of Materials (BOM)

> **Goal:** freeze *exactly* what S3 may open and the versioning/lineage rules that make runs reproducible. If it isn’t listed here, S3 must not read it.

## 2.1 Governed artefacts (authorities S3 must open atomically)

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

## 2.2 Datasets consumed from prior states (read-only)

| Dataset id                        | JSON-Schema anchor                                 | Partition keys (path)            | Embedded lineage (must equal)    | Used fields                                         |
|-----------------------------------|----------------------------------------------------|----------------------------------|----------------------------------|-----------------------------------------------------|
| `rng_event_hurdle_bernoulli` (S1) | `schemas.layer1.yaml#/rng/events/hurdle_bernoulli` | `{seed, parameter_hash, run_id}` | `{seed, parameter_hash, run_id}` | `merchant_id`, payload `is_multi`                   |
| `rng_event_nb_final` (S2)         | `schemas.layer1.yaml#/rng/events/nb_final`         | `{seed, parameter_hash, run_id}` | `{seed, parameter_hash, run_id}` | `merchant_id`, payload `n_outlets` (≥2)             |
| `merchant_ids` (S0)               | `schemas.ingress.layer1.yaml#/merchant_ids`        | registry-defined                 | —                                | `merchant_id`, `home_country_iso`, `mcc`, `channel` |

**Read-side law:** for S1/S2 events, **embedded** `{seed, parameter_hash, run_id}` must **byte-equal** the path partitions.

---

## 2.3 Optional parameter bundles (only if S3 computes deterministic priors)

| Artefact (registry id)       | Purpose                                               | SemVer | Digest (SHA-256) | Notes                                            |
|------------------------------|-------------------------------------------------------|-------:|------------------|--------------------------------------------------|
| `policy.s3.base_weight.yaml` | Deterministic prior formula, constants/coeffs, **dp** |  x.y.z | …                | **No RNG**; evaluation order & **dp** in §12     |
| `policy.s3.thresholds.yaml`  | Deterministic cutoffs (GDP floors, market limits)     |  x.y.z | …                | If used by the rule ladder; closed numbers+units |

If you **do not** compute deterministic priors in S3, omit this subsection (do **not** keep unused knobs).

---

## 2.4 Outputs S3 produces (tables — shape authorities)

| Output dataset                | JSON-Schema anchor                       | Partition keys (path) | Embedded lineage                             | Consuming notes                                                                                      |
|-------------------------------|------------------------------------------|-----------------------|----------------------------------------------|------------------------------------------------------------------------------------------------------|
| `s3_candidate_set`            | `schemas.1A.yaml#/s3/candidate_set`      | `parameter_hash`      | `parameter_hash`, `produced_by_fingerprint?` | **Inter-country order lives only in `candidate_rank`**; `candidate_rank(home)=0`; total & contiguous |
| (opt) `s3_base_weight_priors` | `schemas.1A.yaml#/s3/base_weight_priors` | `parameter_hash`      | `parameter_hash`, `produced_by_fingerprint?` | Deterministic, quantised **priors** (not probabilities); join on `(merchant_id, country_iso)`        |
| (opt) `s3_integerised_counts` | `schemas.1A.yaml#/s3/integerised_counts` | `parameter_hash`      | `parameter_hash`, `produced_by_fingerprint?` | Counts per country; **Σ count = N (from S2)**; persist `residual_rank`                               |

> **Single source of truth for priors:** We keep priors in **`s3_base_weight_priors`** only (no `base_weight_dp` column in `s3_candidate_set`) to avoid duplication and drift.

**Write-side law:** path partitions and embedded lineage must **match byte-for-byte**. **No `seed`** in S3 partitions.

---

## 2.5 Lineage & fingerprint rules (binding)

* **Dataset-level sidecar (required):** each S3 write MUST emit `_manifest.json` with `{manifest_fingerprint, parameter_hash, row_count, files_sorted, dataset_digest}`.
* **Rows (parameter-scoped):** MUST embed `parameter_hash`; MAY include `produced_by_fingerprint` (informational only; equals the run’s `manifest_fingerprint` if present).
* **Skip-if-final:** producers compare the intended `manifest_fingerprint` to the sidecar; if equal and `dataset_digest` matches, the write MAY be skipped.
* **Consumers:** assert the sidecar’s `manifest_fingerprint` equals the selected run; do not filter on a row column.
* **Inclusion rule (explicit):** the following **must** contribute to `manifest_fingerprint`:
  `policy.s3.rule_ladder.yaml`, `iso3166_canonical_2024`, `static.currency_to_country.map.json` (if used),
  `schemas.layer1.yaml` (and `schema.index.layer1.json` if used), `dataset_dictionary.layer1.1A.yaml`, `artefact_registry_1A.yaml`, and any artefact in §2.3.
  Missing inclusion ⇒ **abort**.
* **No path literals:** all IO resolves via the dataset dictionary; paths never appear in code or outputs.

---

## 2.6 Validity windows & version pinning

| Artefact                              | Valid from | Valid to   | Action on out-of-window      |
|---------------------------------------|------------|------------|------------------------------|
| `policy.s3.rule_ladder.yaml`          | YYYY-MM-DD | YYYY-MM-DD | **Abort** (binding policy)   |
| `iso3166_canonical_2024`              | YYYY-MM-DD | YYYY-MM-DD | **Warn + abort** if mismatch |
| `static.currency_to_country.map.json` | YYYY-MM-DD | YYYY-MM-DD | **Abort** if version drifts  |

If no validity windows are governed for an artefact, state: **“No validity window — pinned by digest only (binding).”**

---

## 2.7 Licensing & provenance (must be auditable)

| Artefact                              | Licence                                | Provenance URL / descriptor | Notes                                       |
|---------------------------------------|----------------------------------------|-----------------------------|---------------------------------------------|
| `iso3166_canonical_2024`              | e.g., “ISO data under licence …”       | …                           | Attach licence text in repo if required     |
| `policy.s3.rule_ladder.yaml`          | Project licence (e.g., MIT/Apache-2.0) | internal                    | Generated artefact; provenance = commit SHA |
| `static.currency_to_country.map.json` | e.g., ODbL / CC-BY / internal          | …                           | Ensure redistribution rights are clear      |

If external licences restrict redistribution, record the policy you follow (e.g., embed digests, not full copies).

---

## 2.8 Open/verify checklist (run-time gates)

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

# 3) Determinism & numeric policy (carry-forward)

## 3.1 Scope (what this section fixes)

These rules are **definition-level**. If any item below is violated, S3’s outputs are **out of spec** (even if the program “works”).

* Applies to **all** numeric work in S3 (feature transforms, thresholds, base-weight priors, ordering keys, integerisation residuals).
* **S3 uses no RNG.** If a future variant introduces RNG, it **must** adopt L0’s RNG/trace surfaces verbatim (see §3.7).

---

## 3.2 Floating-point environment (binding)

* **Format:** IEEE-754 **binary64** (`f64`) for all real computations and emitted JSON numbers.
* **Rounding mode:** **Round-to-Nearest, ties-to-Even (RNE)**.
* **FMA:** **disabled** (no fused multiply-add).
* **Denormals:** **no FTZ/DAZ** (do not flush subnormals to zero).
* **Shortest-round-trip emission:** emit `f64` as JSON **numbers** (not strings) using shortest round-trip formatting.

> Implementation: pin a math/runtime profile that guarantees the above; do not rely on host defaults.

---

## 3.3 Evaluation order & reductions

* **Evaluation order is normative.** Evaluate formulas in the **spelled order**; no algebraic reordering or “fast-math”.
* **Reductions:** when summing/aggregating, use **serial Neumaier** in the **documented iteration order** (explicitly: the order defined by the section that invokes the reduction).
* **Clamp / winsorise / quantise:** apply **exactly** in the written sequence (e.g., compute → clamp → **quantise**)—never fused.

---

## 3.4 Total-order sorting (stable & reproducible)

Whenever S3 requires ordering (e.g., candidate ordering, residual ranking), apply a **total order**:

1. Primary key(s) as specified for that step. **For candidate ordering, see §9 (admission-order key; priors are not used).** Other sorts (e.g., residual ranking) follow the keys stated in their sections.
2. If equal **after any required quantisation**, fall back to **ISO code** (`iso_alpha2`, ASCII A–Z).
3. If still tied: break by `merchant_id` ↑ then **original index** (stable: input sequence index in that step’s source list).

All sorts must be **stable** when keys compare equal.

---

## 3.5 Quantisation & dp policy

* If S3 computes deterministic **priors/scores**, it must **quantise** them to a fixed **decimal dp** **before** they are used for numeric steps (e.g., residual ordering in §10)—**not** for candidate ordering (see §9).
* The **dp value** for each context is declared once in that context’s section (e.g., §12 if priors exist).
* Quantise via `round_to_dp(value, dp)` under RNE, then use the **quantised** number for downstream sort/ties.

**Decimal rounding algorithm (binding):**
Let `s = 10^dp`. Compute `q = round_RNE(value * s) / s` in binary64, where `round_RNE` is ties-to-even on the **binary64** value of `value * s`. The emitted field is the binary64 `q` (or its shortest JSON representation if serialized).

*If a value is emitted as a **prior**, its on-disk representation is the **fixed-dp decimal string** defined in §12.3; the binary64 `q` above is for in-memory computation only.*

---

## 3.6 Integerisation residuals (only if S3 allocates counts)

* **Residuals:** compute residuals **after dp-quantisation** of any priors used for fractional shares.
* **Residual ranking:** sort **descending** by residual; tiebreak by **ISO code** (alpha-2, ASCII A–Z). Persist `residual_rank` if integerisation is emitted.
* **Bump discipline:** add +1 to the top `R` residuals until integer totals sum to **N** (from S2). (State where `R` comes from in the integerisation section.)

---

## 3.7 Optional RNG clause (future-proof, off by default)

* **Default:** **No RNG families** in S3. No event envelopes, no `draws/blocks`, no trace rows.
* **If (and only if) S3 ever adds RNG:**

  * Use L0’s writer/trace surface; events under `{seed, parameter_hash, run_id}`; embed `manifest_fingerprint`.
  * Fix `substream_label` names; document **budget law** (draws vs blocks) and **consuming status** for each family.
  * **Guard-before-emit**: compute all predicates that can invalidate an attempt **before** emitting any event.

*(This subsection is a guardrail; today it’s a no-op.)*

---

## 3.8 Path↔embed equality & lineage keys

* Every S3 output row **embeds** `parameter_hash` (must equal the path); if present, `produced_by_fingerprint` equals the run’s `manifest_fingerprint`. The manifest itself is always recorded in the dataset-level sidecar.* S3 outputs are **parameter-scoped** (no `seed` in partitions).
* **No path literals**: all IO resolves via the **dataset dictionary**.

---

## 3.9 Compliance self-check (tick at build/run)

* [ ] Process uses **binary64, RNE, FMA-off, no FTZ/DAZ**.
* [ ] Formulas follow **spelled evaluation order**; Neumaier used where specified.
* [ ] All ordering uses the **total-order stack** in §3.4; sorts are **stable**.
* [ ] Any priors/scores used in **numeric steps** (e.g., integerisation shares) were **quantised to dp** first (dp declared). *(Candidate ordering does **not** use priors; see §9.)*
* [ ] If integerising: residuals computed **after** dp; **ISO alpha-2** tiebreak; `residual_rank` persisted (if emitted).
* [ ] Outputs embed lineage matching path partitions; **no path literals** anywhere.
* [ ] RNG: **absent** in S3 (or, if later enabled, L0 surfaces + guard-before-emit are in place).

---

# 4) Symbols & vocab (legend)

## 4.1 Scalar symbols (used throughout S3)

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

## 4.2 Sets, indices, and keys

| Symbol         | Type                          | Meaning                                                        | Notes                      |
|----------------|-------------------------------|----------------------------------------------------------------|----------------------------|
| `C`            | set of ISO country codes      | The admissible **country universe** for a merchant after rules | `home ∈ C` always          |
| `home`         | `string` (ISO-3166-1 alpha-2) | Merchant’s home country from ingress                           | Uppercase `A–Z`            |
| `i, j`         | index                         | Index over countries in `C`                                    | Used consistently in loops |
| `merchant_id`  | `u64`                         | Canonical merchant identifier (from ingress)                   | Key in all S3 outputs      |
| `merchant_u64` | `u64`                         | Derived key per S0 (read-only)                                 | Not recomputed here        |

---

## 4.3 Deterministic priors / weights (if enabled)

* **Symbols:** `w_i` (pre-quantisation), `w_i^⋄` (post-quantisation).
* **Evaluation order:** exactly as written in §12 (no re-ordering).
* **Quantisation:** `w_i^⋄ = round_to_dp(w_i, dp)` under binary64 RNE (see §3.5).
* **Emission:** if persisted, emit `w_i^⋄` in **`s3_base_weight_priors`** as a **decimal string** with exactly `dp` places; do **not** emit raw `w_i`.

> **No stochastic meaning:** `w` are **deterministic priors/scores**, **not probabilities**.

---

## 4.4 Ordering & tie-breaker keys (total order contract)

When S3 requires a total order over countries:

1. **Primary key(s)** as specified in the relevant section. **For candidate ordering, §9 applies (admission-order key; priors not used).** For residual ranking see §10.5.
2. **Secondary (stable) key:** `country_iso` **lexicographic A–Z**.
3. **Tertiary (stable) key:** `merchant_id` then original input index (stable: input sequence index).

This yields a **total, contiguous ranking** `candidate_rank_i ∈ {0,1,…,|C|−1}`, with **`candidate_rank(home) = 0`**. (See **§9.4** proof obligation.)

---

## 4.5 Closed vocabularies & identifiers

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

## 4.6 Encodings & JSON types

| Field                                    | JSON type         | Encoding details                                         |
|------------------------------------------|-------------------|----------------------------------------------------------|
| `f64` payload numbers                    | **number**        | Shortest round-trip decimal (never strings)              |
| `base_weight_dp` (in priors table)       | **string**        | Decimal string with exactly `dp` places (deterministic)  |
| `manifest_fingerprint`, `parameter_hash` | **string**        | Lowercase hex (`Hex64`); fixed length                    |
| `country_iso`                            | **string**        | Uppercase ISO-3166-1 alpha-2                             |
| `reason_codes`, `filter_tags`            | **array<string>** | Each element in **closed set**; order preserved (stable) |
| `candidate_rank`, `residual_rank`        | **integer**       | Non-negative; `candidate_rank` contiguous from 0         |

---

## 4.7 Units, bounds, and invariants (quick checks)

* `N` from S2: integer, **`N ≥ 2`**.
* `K`: integer, `K ≥ 0`; if cross-border not eligible ⇒ `K = 0`.
* Candidate set: **non-empty**; contains `home`.
* `candidate_rank`: contiguous per merchant; **no duplicates**, **no ties**.
* If integerising in S3: `∑_i count_i = N`; `count_i ≥ 0`; `residual_rank` persisted (unique per merchant–country).
* If priors exist: `dp` stated; **quantise before** any ordering or residual logic.

---

## 4.8 Shorthand functions (names used later)

| Name                    | Signature                         | Meaning                                                     |
|-------------------------|-----------------------------------|-------------------------------------------------------------|
| `round_to_dp`           | `(x:f64, dp:u8) -> f64`           | Quantise to `dp` decimals under RNE (binary64)              |
| `iso_lex_less`          | `(a:string, b:string) -> bool`    | `true` iff `a` < `b` in A–Z lexicographic order             |
| `assign_candidate_rank` | `(C:list) -> list<u32>`           | Produce contiguous ranks using §4.4 total-order             |
| `residual_rank_sort`    | `(ρ:list, iso:list) -> list<u32>` | Sort residuals desc; ISO-lex tie-break; return stable ranks |

*(Symbolic names; concrete implementations live in L0/L1 as appropriate.)*

---

# 5) Control flow (S3 only)

## 5.1 Mini-DAG (one merchant, deterministic)

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

## 5.2 Step-by-step (inputs → outputs → side-effects)

### S3.0 Load context (deterministic)

* **Inputs:** merchant row (ingress), S1 hurdle (`is_multi == true`), S2 `nb_final` (`N ≥ 2`), governed artefacts opened atomically (BOM §2).
* **Outputs:**
  `Ctx = { merchant_id, home_country_iso, mcc, channel, N, artefact_versions, parameter_hash, manifest_fingerprint }`.
* **Side-effects:** none (read-only).
* **Fail:** missing/invalid artefact or gates ⇒ `ERR_S3_AUTHORITY_MISSING` (stop merchant).

### S3.1 Rule ladder (deterministic policy)

* **Inputs:** `Ctx`, rule-ladder artefact.
* **Algorithm:** evaluate **ordered** rules (deny ≻ allow ≻ class ≻ legal/geo ≻ thresholds) per precedence; record `rule_id` & `reason_code`.
* **Outputs:** `RuleTrace` (ordered list) and `eligible_crossborder: bool`.
* **Side-effects:** none.
* **Fail:** unknown `rule_id`/`reason_code` ⇒ `ERR_S3_RULE_LADDER_INVALID`.

### S3.2 Candidate universe construction (deterministic)

* **Inputs:** `Ctx`, `RuleTrace`, static refs (ISO; currency-to-country map if used).
* **Algorithm:** start set `{home}`; if `eligible_crossborder`, add admissible foreign ISO codes; de-dup; tag with deterministic `filter_tags` & `reason_codes`.
* **Outputs:** `C` = list of candidate rows (unordered yet) with tags per row.
* **Side-effects:** none.
* **Fail:** empty `C` or missing `home` ⇒ `ERR_S3_CANDIDATE_CONSTRUCTION`.

### S3.3 Order & rank (total order; deterministic)

* **Inputs:** `C`.
* **Algorithm:** apply the **admission-order comparator** of §9 (priors are **not** used for ranking), then **ISO lexicographic** tie-break, then stability. Produce contiguous **`candidate_rank`** with **`candidate_rank(home) = 0`**.
* **Outputs:** `C_ranked = C + candidate_rank`.
* **Side-effects:** none.
* **Fail:** duplicate ranks ⇒ **`ERR_S3_ORDERING_NONCONTIGUOUS`**;
  missing `candidate_rank(home)=0` ⇒ **`ERR_S3_ORDERING_HOME_MISSING`**.

> If S3 **does not** compute priors, **skip S3.4**.

### S3.4 Base-weight priors (deterministic; optional)

* **Inputs:** `C_ranked`, `policy.s3.base_weight.yaml`.
* **Algorithm:** compute `w_i` per §12 in **spelled evaluation order**; **quantise** to `dp` ⇒ `w_i^⋄`; attach to each candidate (for the priors table).
* **Outputs:** `C_weighted = C_ranked + w_i^⋄` (for emission only; priors live in their own table).
* **Side-effects:** none.
* **Fail:** unknown coeff/param or missing `dp` ⇒ `ERR_S3_WEIGHT_CONFIG`.

> If S3 **does not** integerise, **skip S3.5**.

### S3.5 Integerise to counts (optional; sum to N)

* **Inputs:** `C_weighted` (or `C_ranked` if no priors), `N`.
* **Algorithm:** largest-remainder: floor, compute residuals **after** dp (if any), sort residuals **desc** with ISO tie-break, bump +1 until Σ count = `N`; persist `residual_rank`.
* **Outputs:** `C_counts` = per-country `count` (≥0) summing to `N`, plus `residual_rank`.
* **Side-effects:** none.
* **Fail:** Σ `count` ≠ `N` ⇒ `ERR_S3_INTEGER_SUM_MISMATCH`;
  any `count < 0` ⇒ `ERR_S3_INTEGER_NEGATIVE`.

### S3.6 Emit tables (authoritative)

* **Inputs:** whichever of `C_ranked` / `C_weighted` / `C_counts` applies; `Ctx` lineage keys.
* **Algorithm:** write **tables** via dictionary-resolved paths, partitioned by **`parameter_hash`**; embed `parameter_hash` (must byte-equal the path); MAY embed `produced_by_fingerprint` (informational).
* **Outputs (tables):**

  * **Required:** `s3_candidate_set` (ranked, tagged candidates with `candidate_rank`).
  * **Optional:** `s3_base_weight_priors` (if S3.4 ran; emit `w_i^⋄` as **decimal string** with exactly `dp` places) and/or `s3_integerised_counts` (if S3.5 ran; includes `residual_rank`).
* **Side-effects:** none beyond writes (no RNG events).
* **Fail:** path↔embed mismatch or schema violation ⇒ `ERR_S3_EGRESS_SHAPE`.

---

## 5.3 Looping & stopping conditions

* **Per merchant:** S3 runs **once**; there are **no stochastic attempts**.
* **Stop-early:** if rule ladder denies cross-border, candidate set is `{home}` with `candidate_rank=0`; optional steps (priors, integerisation) still obey invariants.

---

## 5.4 Concurrency & idempotence

* **Read joins:** keyed by `{seed, parameter_hash, run_id, merchant_id}` for S1/S2 inputs (equality on path↔embed).
* **Outputs:** **parameter-scoped** only (partitioned by `parameter_hash`); S3 has **no finaliser**.
* **Parallelism invariance:** deterministic, no RNG ⇒ re-partitioning/concurrency **cannot** change bytes.

---

## 5.5 Evidence cadence (what is written where)

* **Events:** none in S3.
* **Tables (only in S3.6):** fully-qualified JSON-Schema anchors; numbers as JSON numbers; **priors** (if emitted) as **decimal strings** with fixed `dp` in **`s3_base_weight_priors`**.

---



# 6) S3.0 — Load scopes (deterministic)

## 6.1 Purpose (binding)

Establish the **closed** set of inputs S3 may read, verify **gates and vocabularies**, and assemble a single, immutable **Context** record for subsequent S3 steps. S3.0 performs **no writes** and uses **no RNG**.

---

## 6.2 Inputs (authoritative anchors; read-only)

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

## 6.3 Preconditions & gates (must hold before S3 continues)

1. **Presence & uniqueness** (within `{seed, parameter_hash, run_id}`):
   exactly one S1 hurdle row **and** exactly one S2 `nb_final` row per merchant; exactly one ingress merchant row.
2. **Gate conditions:** `is_multi == true` and `n_outlets (N) ≥ 2`.
3. **Path↔embed equality (read side):** for S1 and S2 rows, embedded `{seed, parameter_hash, run_id}` **byte-equal** the path partitions.
4. **Closed vocabularies:** `channel ∈ (ingress schema’s closed vocabulary)` (case-sensitive); `home_country_iso ∈` ISO set from the static artefact.
5. **Artefact integrity:** rule ladder precedence is a **total order**; `reason_codes[]` is a **closed set**; any configured validity windows are satisfied.
6. **Lineage availability:** run’s `parameter_hash` and `manifest_fingerprint` exist; every artefact opened in §6.2 will be included in the fingerprint inputs for embedding later.

**If any precondition fails, S3 stops for this merchant** (see §6.7). S3.0 produces **no S3 outputs**.

---

## 6.4 Normative behavior (spec, not algorithm)

S3.0 **shall**:

* Open all governed artefacts in §6.2 **atomically**; record each `(id, semver, digest)` for fingerprint inclusion.
* Resolve S1/S2 datasets via the dictionary and read the **single** row per merchant from each (no scanning outside the partition scope).
* Enforce §6.3 exactly as written (no “best effort”).
* Construct an immutable **Context** with the fields in §6.5.
* Perform **no writes** and **no RNG** activity.

---

## 6.5 Context (immutable; passed to S3.1+)

**Fields and semantics (all required unless marked optional):**

| Field                              | Type                                      | Source                  | Semantics                                                            |
|------------------------------------|-------------------------------------------|-------------------------|----------------------------------------------------------------------|
| `merchant_id`                      | `u64`                                     | ingress                 | Canonical key                                                        |
| `home_country_iso`                 | `string (ISO-3166-1)`                     | ingress                 | Must exist in ISO artefact; uppercase A–Z                            |
| `mcc`                              | `string`                                  | ingress                 | Merchant category code (read-only)                                   |
| `channel`                          | `(closed vocabulary from ingress schema)` | ingress                 | Closed vocabulary (read-only)                                        |
| `N`                                | `i64 (≥2)`                                | S2 `nb_final.n_outlets` | Total outlets accepted by S2                                         |
| `seed`                             | `u64`                                     | S1/S2 embed             | For lineage joins only; S3 outputs are **not** seed-partitioned      |
| `parameter_hash`                   | `Hex64`                                   | S1/S2 embed / run       | Partition key for all S3 outputs                                     |
| `manifest_fingerprint`             | `Hex64`                                   | run                     | Recorded in the sidecar; rows MAY include `produced_by_fingerprint`. |
| `artefacts.rule_ladder`            | `{id, semver, digest}`                    | registry                | Governance attest                                                    |
| `artefacts.iso_countries`          | `{id, semver, digest}`                    | registry                | Governance attest                                                    |
| `artefacts.ccy_to_country` *(opt)* | `{id, semver, digest}`                    | registry                | Present only if used                                                 |

> **Deliberate omission:** S3 does **not** carry S2’s `mu`/`dispersion_k` in context; S3 never re-derives or uses them.

**Immutability:** later S3 steps must not modify `Context` nor re-open authorities beyond §6.2.

---

## 6.6 Postconditions (must be true after S3.0)

* Governed artefacts are open, version-pinned, and slated for inclusion in the run `manifest_fingerprint`.
* Merchant has passed gates: `is_multi==true`, `N≥2`.
* Path partitions equal embedded lineage on S1/S2 rows.
* Closed vocabularies validated; ISO presence confirmed.
* A complete **Context** exists with lineage fields ready to embed in S3 egress.

---

## 6.7 Failure vocabulary (merchant-scoped; non-emitting)

| Code                         | Trigger                                                                                    | Effect                           |
|------------------------------|--------------------------------------------------------------------------------------------|----------------------------------|
| `ERR_S3_AUTHORITY_MISSING`   | Any governed artefact in §6.2 missing/unopenable or lacking semver/digest                  | Stop S3 for merchant; no outputs |
| `ERR_S3_PRECONDITION`        | `is_multi=false` or `N<2`                                                                  | Stop S3 for merchant; no outputs |
| `ERR_S3_PARTITION_MISMATCH`  | Path partitions ≠ embedded lineage on S1/S2 rows                                           | Stop S3 for merchant; no outputs |
| `ERR_S3_VOCAB_INVALID`       | `channel` not in (ingress schema’s closed vocabulary) or `home_country_iso` not in ISO set | Stop S3 for merchant; no outputs |
| `ERR_S3_RULE_LADDER_INVALID` | Ladder not total, unknown `reason_codes`, or out-of-window                                 | Stop S3 for merchant; no outputs |

**Non-emission guarantee:** S3.0 never writes tables or events; failures here do not produce partial S3 artefacts.

---

## 6.8 Spec-rehearsal (non-authoritative; for clarity only)

1. Open atomically: rule ladder, ISO set, (optional) currency-to-country map, dataset dictionary, artefact registry.
2. Read exactly one row each (dictionary-resolved IDs): ingress merchant, S1 hurdle, S2 `nb_final`.
3. Check: uniqueness; path partitions equal embedded lineage (S1/S2); `is_multi==true`; `N≥2`; `channel∈(ingress schema’s closed vocabulary)`; `home` ISO in set; ladder is a total order with **closed** reason codes (within window if configured).
4. Assemble `Context` per §6.5.
5. Stop (no RNG, no writes). Pass `Context` to S3.1.

*(End non-authoritative rehearsal.)*

---

# 7) S3.1 — Rule ladder (deterministic policy)

## 7.1 Purpose (binding)

Evaluate an **ordered, deterministic** set of policy rules to decide the merchant’s **cross-border eligibility** and to produce a **trace** of which rules fired (with reason codes/tags) for S3.2. **No RNG** and **no I/O** occur in S3.1.

---

## 7.2 Inputs (authoritative; read-only)

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

## 7.3 Rule artefact — shape & fields (binding)

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

## 7.4 Precedence law & conflict resolution (binding)

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

## 7.5 Evaluation semantics (deterministic; no side-effects)

* Evaluate **all** predicates; collect `Fired`.
* Set `eligible_crossborder` **once** per §7.4.
* Compute `merchant_tags` as the **set-union** of `outcome.tags` from `Fired`, keeping a stable **A→Z** order for emission.
* **No I/O, no RNG**; results are in-memory outputs for S3.2.

---

## 7.6 Outputs to S3.2 (binding)

S3.1 yields the following immutable values:

| Name                   | Type            | Semantics                                                                                                                                |
|------------------------|-----------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `eligible_crossborder` | `bool`          | Merchant-level decision per §7.4                                                                                                         |
| `rule_trace`           | list of structs | Each: `{rule_id, precedence, priority, is_decision_bearing, reason_code, is_decision_source:bool, tags:array<string>}` ordered as §7.4.4 |
| `merchant_tags`        | array<string>   | Deterministic union of all fired rule tags; **closed** vocabulary; **A→Z** order                                                         |

**Consumption:**
S3.2 uses `eligible_crossborder` to decide whether to add foreign countries. `rule_trace`/`merchant_tags` drive candidate-row `reason_codes[]`/`filter_tags[]` (mapping to per-country tags is defined in §8/§10).

---

## 7.7 Invariants (must hold)

* Artefact precedence is a **total order**; `reason_codes[]` and `filter_tags[]` are **closed**.
* Exactly **one** terminal, decision-bearing `DEFAULT` rule exists.
* `eligible_crossborder` is **always defined**.
* `rule_trace` ordering is **stable** and independent of evaluation order/data layout.
* No rule references fields/sets outside §6.2/§2.1.
* No randomness or host state influences the outcome.

---

## 7.8 Failure vocabulary (merchant-scoped; non-emitting)

| Code                         | Trigger                                                                                                                       | Action                              |
|------------------------------|-------------------------------------------------------------------------------------------------------------------------------|-------------------------------------|
| `ERR_S3_RULE_LADDER_INVALID` | Missing/duplicate `DEFAULT`; non-total precedence; duplicate `rule_id`; `reason_code`/`filter_tag` not in the **closed** sets | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_RULE_EVAL_DOMAIN`    | Predicate references unknown feature/value (e.g., unknown `channel`, ISO not in artefact, undeclared named set/map)           | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_RULE_CONFLICT`       | Multiple **decision-bearing** rules tie after priority and lexicographic tiebreak (malformed artefact)                        | Stop S3 for merchant; no S3 outputs |

---

## 7.9 Notes (clarifications; binding where stated)

* **Numeric thresholds:** comparisons are evaluated in **binary64** per §3. If thresholds are decimal, the artefact must state inclusivity (`>=` vs `>`).
* **No re-derivation:** if a rule needs an input (e.g., GDP bucket), it must appear in §2/§6; otherwise the rule is invalid.
* **Trace vs emission:** S3.1 **does not write** traces; `rule_trace`/`merchant_tags` are handed to S3.2 to annotate candidate rows.

---

# 8) S3.2 — Candidate universe construction (deterministic)

## 8.1 Purpose (binding)

Construct, for a single merchant, the **unordered** candidate country set `C` that §9 will **rank** (and, if enabled, §12 will weight / §13 will integerise). The set is **deterministic**, **non-empty**, and **always contains `home`**. **No RNG** and **no egress** occur in S3.2.

---

## 8.2 Inputs (authoritative; read-only)

* **`Context`** from §6.5 (immutable): `merchant_id`, `home_country_iso`, `mcc`, `channel`, `N`, lineage fields, artefact digests.
* **`eligible_crossborder : bool`** and **`rule_trace`** from §7.6 (immutable): ordered fired rules `{rule_id, precedence, priority, is_decision_bearing, reason_code, is_decision_source, tags[]}`.
* **Policy artefact** `policy.s3.rule_ladder.yaml` (opened in §6):
  • **Named country sets** (e.g., `SANCTIONED`, `EEA`, `WHITELIST_X`);
  • Per-rule **admit/deny lists** (`admit_countries[]`, `deny_countries[]`) and/or references to named sets;
  • **Closed vocabularies**: `reason_codes[]`, `filter_tags[]`; mapping notes for row-level tagging.
* **ISO reference** `iso3166_canonical_2024` (opened in §6): authoritative ISO set and lexicographic order (alpha-2, uppercase).

> **Resolution rule:** S3.2 consults **only** the policy artefact’s named sets/lists and the ISO set; **no other source** is permitted.

---

## 8.3 Preconditions (must hold before S3.2 runs)

* `home_country_iso ∈ ISO` (already verified in §6).
* `eligible_crossborder` and `rule_trace` are present (from §7).
* Every named set/list referenced by **fired** rules exists in the policy artefact and expands **only** to ISO codes.

---

## 8.4 Deterministic construction (spec, not algorithm)

### 8.4.1 Start set (invariant)

* Initialise `C := { home }` with `home = Context.home_country_iso`.
* Tag the `home` row with `filter_tags += ["HOME"]` (from the policy’s **closed** `filter_tags`) and include the **decision source** `reason_code` (from §7) in `reason_codes` for traceability.

### 8.4.2 Foreign admission when `eligible_crossborder == false`

* **No foreign country is admitted.**
* `C = { home }`; define `K_foreign := 0`.

### 8.4.3 Foreign admission when `eligible_crossborder == true`

Let `Fired` be the set of fired rules (from `rule_trace`). Build deterministic admits/denies using only **fired** rules and the artefact:

* `ADMITS`  = ⋃ over fired rules of: explicit `admit_countries[]` ∪ expansions of referenced **admit** named sets.

* `DENIES`  = ⋃ over fired rules of: explicit `deny_countries[]`  ∪ expansions of referenced **deny** named sets **including legal/geo constraints** (e.g., `SANCTIONED`).

* **Precedence reflection:** since §7 already applies **DENY ≻ ALLOW**, S3.2 forms the foreign set as
  `FOREIGN := (ADMITS \ DENIES) \ {home}`. *(No re-evaluation of precedence; this is a set-level reflection.)*

* **ISO filter:** `FOREIGN := FOREIGN ∩ ISO`. Any element not in ISO is a **policy artefact error** (see §8.8).

* Add every `c ∈ FOREIGN` to `C`. For each added row, attach deterministic `filter_tags` and `reason_codes` per the artefact’s mapping rules (e.g., per-rule `row_tags`, plus a **stable union** of fired rules’ `reason_code` values that justify inclusion; both vocabularies are **closed** and must appear in **A→Z** order).

* Define `K_foreign := |FOREIGN|`.

### 8.4.4 De-duplication & casing

* `C` contains **unique** ISO alpha-2 codes (uppercase `A–Z`).
* If multiple fired rules admit the same country, merge tags/reasons via **stable union** (A→Z for strings), no duplicates.

---

## 8.5 Outputs to §9 (binding; still unordered)

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

## 8.6 Invariants (must hold after S3.2)

* `C` is **non-empty** and **contains `home`**.
* If `eligible_crossborder == false` ⇒ `C == {home}` and `K_foreign == 0`.
* If `eligible_crossborder == true` ⇒ `C == {home} ∪ FOREIGN`; `K_foreign == |C| − 1`; `FOREIGN` is deterministic per fired rules.
* Every `country_iso ∈ ISO`; **no duplicates** in `C`.
* `filter_tags` and `reason_codes` per row are drawn **only** from the artefact’s **closed** vocabularies and are in **A→Z** order.

---

## 8.7 Notes (clarifications; binding where stated)

* **No re-derivation:** S3.2 does not derive features beyond §6/§2. If a rule needs, e.g., *GDP bucket*, it must be provided via governed artefacts; otherwise the rule is invalid for S3.
* **No RNG:** Country selection in S3.2 is policy-driven, not stochastic. Any stochastic selection (e.g., Gumbel-top-K) belongs in a later state; S3 here is deterministic.
* **Admit/deny scope:** Admit/deny operate at **country-level** only. Merchant-level tags from rules apply to **all** candidate rows; per-row tags follow the artefact’s mapping.

---

## 8.8 Failure vocabulary (merchant-scoped; non-emitting)

| Code                              | Trigger                                                     | Action                              |
|-----------------------------------|-------------------------------------------------------------|-------------------------------------|
| `ERR_S3_CANDIDATE_CONSTRUCTION`   | Candidate set becomes empty **or** `home` missing from `C`  | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_COUNTRY_CODE_INVALID`     | A named set/list expands to a value not in the ISO artefact | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_POLICY_REFERENCE_INVALID` | Fired rule references an undefined named set/list           | Stop S3 for merchant; no S3 outputs |

---

**Hand-off to §9:** §8 yields the **unordered** candidate rows `C`. §9 will impose a **total, deterministic order** (**`candidate_rank`**)—**priors are not used for sorting**. If configured, priors may be computed later and are used in **integerisation** (§10).

---

# 9) S3.3 — Ordering & tie-break (total order)

## 9.1 Purpose (binding)

Impose a **total, deterministic order** over the **unordered** candidate rows from §8 so that every merchant’s candidates receive a **contiguous** **`candidate_rank ∈ {0,…,|C|−1}`** with **`candidate_rank(home) = 0`**. **No RNG** and **no I/O** occur in S3.3.

> Canonical S3 flow (per §5): **rank first, then priors (§12)**. Therefore, ranking **does not** use weights.

---

## 9.2 Inputs (authoritative; read-only)

* **Candidate rows `C` from §8.5** (unordered), each with:
  `merchant_id`, `country_iso`, `is_home`, `filter_tags[]`, `reason_codes[]`, *(optional)* `base_weight_inputs` (only if §12 will run later; not used here).
* **Context** from §6.5 (read-only): includes `home_country_iso`.
* **Policy artefact `policy.s3.rule_ladder.yaml`** (read-only): precedence class order, per-rule `priority`, `rule_id`, and the **closed mapping** from row `reason_codes[]` to the admitting rule id(s) (see 9.3.2).

> Resolution rule: S3.3 consults **only** §8 outputs and the artefact fields listed above. No external sources.

---

## 9.3 Comparator (single path to a total order)

Define one deterministic comparator. Sorting must be **stable**.

### 9.3.1 Home override (rank 0)

* The row with `country_iso == home_country_iso` **must** receive **`candidate_rank = 0`**.
* All other countries are ranked **strictly after** home (beginning at `candidate_rank = 1`).

### 9.3.2 Primary key — **admission order key** (weights are not used)

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

### 9.3.3 Secondary & tertiary keys (shared)

* **Key 2 (ISO tiebreak):** `country_iso` **lexicographic A→Z** (ISO alpha-2).
* **Key 3 (stability):** the row’s **original index** in §8’s output (or, equivalently, `(merchant_id, original_index)`) to guarantee **stable** order under equal keys.

---

## 9.4 Rank assignment (binding)

After sorting with §9.3 for a given merchant:

* Assign **`candidate_rank = 0`** to `home`.
* Assign **`candidate_rank = 1,2,…`** in sorted order to the remaining rows **with no gaps**.

**Contiguity:** per merchant, `candidate_rank` spans `0..|C|−1`.
**Uniqueness:** per merchant, **no two rows share the same `(candidate_rank, country_iso)`**; **no duplicate `country_iso`** exist by §8.

---

## 9.5 Deterministic numeric discipline (binding)

* Priors/weights, if later computed in §12, are **not** used here.
* All string and integer comparisons follow §3’s environment (binary64 rules are irrelevant in §9 unless later sections add numeric keys).
* Sorting is **stable**; do not rely on host/library unspecified stability—**stability is part of the contract**.

---

## 9.6 Outputs to §12/§13/§15 (binding)

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

## 9.7 Invariants (must hold after S3.3)

* **`candidate_rank(home) = 0`**.
* Ranks are **contiguous** with no gaps; total order holds even when keys tie (via ISO then stability key).
* Comparator uses **admission order key** (no priors); sorting is **stable** and host-invariant under §3.
* If the artefact cannot provide a closed mapping from `reason_codes[]` to admit rules for any foreign row, the run is invalid for S3.

---

## 9.8 Failure vocabulary (merchant-scoped; non-emitting)

| Code                            | Trigger                                                                                            | Action                              |
|---------------------------------|----------------------------------------------------------------------------------------------------|-------------------------------------|
| `ERR_S3_ORDERING_HOME_MISSING`  | No row with `country_iso == home` in §8 output                                                     | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_ORDERING_NONCONTIGUOUS` | Assigned **candidate_rank** values are not contiguous `0..\|C\|−1`                                 | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_ORDERING_KEY_UNDEFINED` | Cannot reconstruct the **admission key** (no priors and no closed mapping from reasons → rule ids) | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_ORDERING_UNSTABLE`      | Artefact inconsistency prevents a single total order (e.g., ambiguous mapping that yields ties)    | Stop S3 for merchant; no S3 outputs |

---

## 9.9 Notes (clarifications; binding where stated)

* **Home-first is an override, not a key:** assign `candidate_rank=0` to home **before** comparing the remainder.
* **Admission key derivation** depends on a **closed mapping** from row-level `reason_codes[]` (or explicit `admit_rule_ids[]`) to admitting rules. If your policy expresses reasons at a coarser grain, add explicit `admit_rule_ids[]`.
* **No probabilistic meaning** attaches to `candidate_rank`. It is a deterministic ordering surface only.

---

# 10) S3.4 — Integerisation (include only if S3 allocates counts)

## 10.1 Purpose (binding)

Convert a merchant’s **ranked** candidate universe and a total outlet count **`N`** (from S2) into **non-negative integer per-country counts** that sum to **`N`**, using a **deterministic largest-remainder** method with fixed quantisation and tie-break rules. **No RNG** and **no I/O** occur in S3.4.

---

## 10.2 Inputs (authoritative; read-only)

* **Context** (from §6.5): `merchant_id`, `home_country_iso`, `N (≥2)`, lineage fields.
* **Ranked candidates** (from §9): rows `⟨country_iso, candidate_rank, …⟩`, with `candidate_rank(home)=0`, contiguous ranks, no duplicates.
* **Deterministic priors (optional):** **quantised** weights `w_i^⋄` (post-quantisation per §3.5 / §12) **if** priors are enabled in S3.
* **(Optional) bounds / policy knobs:** per-country integer bounds `L_i, U_i` with `0 ≤ L_i ≤ U_i ≤ N` **if** the policy artefact defines them for integerisation.

> **Resolution rule:** If priors are **not** enabled in S3, integerisation uses the **equal-weight** path (§10.3.B). If bounds exist, apply §10.6 (bounded Hamilton).

---

## 10.3 Ideal (fractional) allocation — two primary paths

Let `M = |C|` be the number of candidate countries.

### 10.3.A Priors present (preferred when enabled)

* Use **quantised** priors `w_i^⋄ > 0` (dp fixed where produced).
* Normalise: `s_i = w_i^⋄ / (Σ_j w_j^⋄)`.
* Ideal fractional counts: `a_i = N · s_i`.

**Guard:** If `Σ_j w_j^⋄ == 0` (policy error), fall back to §10.3.B (equal-weight) and raise `ERR_S3_WEIGHT_ZERO` (see §10.9).

### 10.3.B No priors (equal-weight discipline)

* Set `s_i = 1 / M` for all `i`.
* Ideal counts: `a_i = N / M` (identical for all countries).

*(Either path yields `a = (a_1,…,a_M)` used below.)*

---

## 10.4 Floor step, residuals, and remainder

* **Floor counts:** `b_i = ⌊ a_i ⌋` (integer).
* **Remainder to distribute:** `d = N − Σ_i b_i` (integer, `0 ≤ d < M`).
* **Residuals:** `r_i = a_i − b_i` (fractional part in `[0,1)`).
* **Residual quantisation (binding):** quantise residuals to fixed **`dp_resid = 8`** decimal places under binary64 RNE (§3.5):
  `r_i^⋄ = round_to_dp(r_i, 8)`.

> Residuals are **always** computed **after** using the **quantised** priors (if any). The value of `dp_resid` is **binding**.

---

## 10.5 Deterministic bump rule (largest-remainder with fixed tie-break)

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

## 10.6 Optional bounds (lower/upper) — bounded Hamilton method

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

## 10.7 Outputs to egress (§15) (binding)

For each candidate row:

| Field           | Type       | Semantics                                                        |
|-----------------|------------|------------------------------------------------------------------|
| `count`         | `i64 (≥0)` | Final integer allocation for `country_iso`                       |
| `residual_rank` | `u32`      | Position in the residual order `S` of §10.5 (1 = highest resid.) |

If S3 emits a dedicated table **`s3_integerised_counts`**, include `merchant_id`, `country_iso`, `count`, `residual_rank`, and lineage fields, partitioned per §2.

---

## 10.8 Invariants (must hold)

* `Σ_i count_i = N`; `count_i ≥ 0`.
* **`candidate_rank(home) = 0`** still holds from §9; integerisation **does not** alter ranks.
* Residuals quantised at **`dp_resid = 8`** before ordering; tie-break exactly as §10.5.
* If bounds are used: `L_i ≤ count_i ≤ U_i` for all `i`, and feasibility guard passed.
* `{ i | residual_rank_i ≤ d }` matches exactly the set of bumped countries.

---

## 10.9 Failure vocabulary (merchant-scoped; non-emitting)

| Code                          | Trigger                                            | Action                              |
|-------------------------------|----------------------------------------------------|-------------------------------------|
| `ERR_S3_WEIGHT_ZERO`          | Priors enabled but `Σ_i w_i^⋄ == 0` (policy error) | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_INTEGER_FEASIBILITY`  | Bounds specified but `Σ L_i > N` or `N > Σ U_i`    | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_INTEGER_SUM_MISMATCH` | After allocation, `Σ_i count_i ≠ N`                | Stop S3 for merchant; no S3 outputs |
| `ERR_S3_INTEGER_NEGATIVE`     | Any `count_i < 0`                                  | Stop S3 for merchant; no S3 outputs |

---

## 10.10 Notes (clarifications; binding where stated)

* **dp selection:** `dp_resid = 8` is binding for residuals to ensure cross-host determinism; change only via policy artefact **and** update this section.
* **Home minimum:** If policy requires a **home floor** (e.g., `L_home ≥ 1`), encode via §10.6; do **not** hand-wave it in code.
* **No probabilistic meaning:** counts are deterministic integers; priors (if any) are deterministic scores, *not* probabilities.

---

# 11) S3.5 — Sequencing & IDs (deterministic)

## 11.1 Purpose (binding)

Given per-country **integer counts** `count_i` (from §10) for a multi-site merchant, define a **deterministic, contiguous within-country sequence** `site_order ∈ {1..count_i}`, and—if enabled—a **deterministic identifier** `site_id` per `(merchant_id, country_iso, site_order)`. **No RNG**; **no gaps**; ordering is reproducible across hosts.

---

## 11.2 Preconditions (must hold)

* Inputs from §6.5 (**Context**) and **ranked candidate rows** from §9.
* Integer counts from §10 present and valid: for each `country_iso` in the merchant’s set, `count_i ≥ 0` and `Σ_i count_i = N`.
* **`candidate_rank(home) = 0`** still holds (sequencing must not change inter-country order).

---

## 11.3 Sequencing (deterministic; no side-effects)

* **Per-country domain:** For each `(merchant_id, country_iso)` with `count_i > 0`, define a **contiguous** within-country sequence `site_order ∈ {1,2,…,count_i}`.
* **Logical row grouping:** Within a merchant block, rows are *logically* grouped by `(country_iso, site_order)`; inter-country order remains §9’s **`candidate_rank`** and is **not** encoded here.
* **Zero counts:** If `count_i = 0`, **no rows** exist for that `(merchant_id, country_iso)` in any sequencing output.

> **Binding:** Sequencing **never** reorders countries: inter-country order remains the **`candidate_rank`** from §9; sequencing only establishes the order **within** each country.

---

## 11.4 Identifier policy (if `site_id` is enabled)

* **Format:** `site_id` is a **fixed-width, zero-padded 6-digit string**: `"{site_order:06d}"`.
  Examples: `1 → "000001"`, `42 → "000042"`, `999999 → "999999"`.
* **Scope of uniqueness:** Unique **within** each `(merchant_id, country_iso)`. The same `site_id` string may appear in another country or merchant.
* **Overflow rule (binding):** If `count_i > 999999`, raise `ERR_S3_SITE_SEQUENCE_OVERFLOW` and **stop S3 for that merchant**; no partial sequencing/outputs.
* **Immutability:** Given identical inputs/lineage, the mapping `(merchant_id, country_iso, site_order) → site_id` is a pure function (no host/time dependence).

---

## 11.5 Emitted dataset (Variant A — S3 owns sequencing)

If S3 emits sequencing, it **must** produce the following table; otherwise skip to §11.6.

| Dataset id         | JSON-Schema anchor                  | Partitions (path)    | Embedded lineage (columns)                           | Row order (physical)                                 | Columns (name : type : semantics)                                                                                                                                                             |
|--------------------|-------------------------------------|----------------------|------------------------------------------------------|------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `s3_site_sequence` | `schemas.1A.yaml#/s3/site_sequence` | `parameter_hash={…}` | `manifest_fingerprint:Hex64`, `parameter_hash:Hex64` | `(merchant_id ASC, country_iso ASC, site_order ASC)` | `merchant_id:u64` — key; `country_iso:string(ISO-3166-1 alpha-2)`; `site_order:u32` — **contiguous 1..count\_i**; *(optional)* `site_id:string(len=6)` — zero-padded; lineage fields as above |

**Contracts**

* **Contiguity:** For each `(merchant_id, country_iso)`, the set of `site_order` values is **exactly** `{1..count_i}`.
* **Uniqueness:** No duplicate `site_order` within a `(merchant_id, country_iso)` block; if `site_id` present, no duplicate `site_id` within that block.
* **Read scope:** Consumers **must not** infer inter-country order from this table; inter-country order is **only** `candidate_rank` from §9 (available via `s3_candidate_set`).

---

## 11.6 Deferred emission (Variant B — sequencing implemented later)

If S3 does **not** emit `s3_site_sequence`, it must still fix the **binding rules** in §§11.3–11.4. A later state (e.g., S7 “Sequence & IDs”) must:

* Use **exactly** the same within-country sequencing (contiguous `1..count_i`),
* Enforce the **same** `site_id` format and **overflow** rule, and
* Preserve lineage/path rules from §2 (parameter-scoped partitions; embed `manifest_fingerprint` and `parameter_hash`).

---

## 11.7 Lineage & ordering (write-side discipline, Variant A)

* **Partitions:** `parameter_hash` only (parameter-scoped).
* **Embedded lineage:** each row embeds `{parameter_hash, manifest_fingerprint}` equal to the run.
* **No path literals:** dictionary resolves the dataset id to a physical path.
* **JSON types:** numbers as JSON **numbers**; `site_id` as JSON **string** of length 6.

---

## 11.8 Failure vocabulary (merchant-scoped; non-emitting)

| Code                            | Trigger                                                                                       | Action                                               |
|---------------------------------|-----------------------------------------------------------------------------------------------|------------------------------------------------------|
| `ERR_S3_SITE_SEQUENCE_OVERFLOW` | `count_i > 999999` for any `(merchant_id, country_iso)`                                       | Stop S3 for merchant; emit **no** sequencing outputs |
| `ERR_S3_SEQUENCE_GAP`           | A `(merchant_id, country_iso)` block is missing any integer in `{1..count_i}`                 | Stop S3 for merchant; no outputs                     |
| `ERR_S3_SEQUENCE_DUPLICATE`     | Duplicate `site_order` (or `site_id`, if enabled) within a `(merchant_id, country_iso)` block | Stop S3 for merchant; no outputs                     |
| `ERR_S3_SEQUENCE_ORDER_DRIFT`   | Sequencing attempts to alter inter-country order (i.e., contradict §9 **candidate\_rank**)    | Stop S3 for merchant; no outputs                     |

---

## 11.9 Invariants (must hold after sequencing)

* For every country with `count_i > 0`, `site_order` is **exactly** `1..count_i` (contiguous, no gaps).
* **Inter-country order remains §9’s `candidate_rank`**; sequencing does not permute countries.
* If `site_id` is emitted, it is a deterministic function of `(merchant_id, country_iso, site_order)` with the 6-digit zero-padded format; overflow is impossible by construction or triggers §11.8.
* Outputs (Variant A) follow §2 lineage/partition rules; **no path literals**.

---

*Implementation note (non-authoritative):* If you anticipate future requirements for a check digit or namespace change, nest `site_id` under a versioned object in the schema (e.g., `{ "v": 1, "id": "000123" }`). Until then, the flat 6-digit string above is the **binding** representation.

---

# 12) Emissions (authoritative)

## 12.1 General write discipline (binding)

* **Dictionary-resolved paths only.** All physical locations resolve via the dataset dictionary by dataset **ID**; no hard-coded paths.
* **Partition scope:** all S3 datasets are **parameter-scoped** — partitioned by `parameter_hash` only (**no `seed`**).
* **Embedded lineage:** every S3 row **embeds** `parameter_hash`; MAY include `produced_by_fingerprint?`. A dataset-level sidecar `_manifest.json` is **required** (manifest, files, digest).
* **Numbers:** payload numbers are JSON **numbers** (not strings), except where a **decimal string** is required for deterministic fixed-dp representation (explicitly called out below).
* **Atomic publish:** stage → fsync → atomic rename into the dictionary location. No partials or mismatched partitions.
* **Idempotence:** identical inputs + lineage ⇒ **byte-identical** outputs.

---

## 12.2 Required table — `s3_candidate_set`

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

## 12.3 Optional table — `s3_base_weight_priors` (deterministic scores)

Emit **only** if S3 computes deterministic priors (see §12 / §3.5 for `dp` selection). Priors are deterministic scores, not probabilities.

**Dataset id:** `s3_base_weight_priors`
**JSON-Schema anchor:** `schemas.1A.yaml#/s3/base_weight_priors`
**Partitions (path):** `parameter_hash={…}`
**Embedded lineage (columns):** `parameter_hash`, `produced_by_fingerprint?`
**Row ordering guarantee:** `(merchant_id ASC, country_iso ASC)`

**Columns (binding):**

| Name                       | Type                      | Semantics                                                               |
|----------------------------|---------------------------|-------------------------------------------------------------------------|
| `merchant_id`              | `u64`                     | Canonical merchant key                                                  |
| `country_iso`              | `string(ISO-3166-1, A–Z)` | Candidate country code                                                  |
| `base_weight_dp`           | **string (fixed-dp)**     | Deterministic prior **after quantisation**; exactly `dp` decimal places |
| `dp`                       | `u8`                      | Decimal places used for quantisation (constant within a run)            |
| `parameter_hash`           | `Hex64`                   | Embedded lineage                                                        |
| `produced_by_fingerprint?` | `Hex64`                   | Embedded lineage                                                        |

**Contracts**

* `dp` is constant within a run (may change **only** with policy change + new fingerprint/param hash).
* This table is the **only** authority for priors in S3; `s3_candidate_set` must not carry a `base_weight_dp` field.

---

## 12.4 Optional table — `s3_integerised_counts` (if S3 allocates counts)

Emit **only** if S3 performs integerisation (see §10). Otherwise, counts belong to the later state that owns allocation.

**Dataset id:** `s3_integerised_counts`
**JSON-Schema anchor:** `schemas.1A.yaml#/s3/integerised_counts`
**Partitions (path):** `parameter_hash={…}`
**Embedded lineage (columns):** `parameter_hash`, `produced_by_fingerprint?`
**Row ordering guarantee:** `(merchant_id ASC, country_iso ASC)`

**Columns (binding):**

| Name                       | Type                      | Semantics                                                 |
|----------------------------|---------------------------|-----------------------------------------------------------|
| `merchant_id`              | `u64`                     | Canonical merchant key                                    |
| `country_iso`              | `string(ISO-3166-1, A–Z)` | Candidate country code                                    |
| `count`                    | `i64 (≥0)`                | Final integer allocation for this country                 |
| `residual_rank`            | `u32`                     | Rank in residual order (`1`=highest), as defined in §10.5 |
| `parameter_hash`           | `Hex64`                   | Embedded lineage                                          |
| `produced_by_fingerprint?` | `Hex64`                   | Embedded lineage                                          |

**Contracts**

* Per merchant: `Σ_i count_i = N` from S2; `count_i ≥ 0`.
* `residual_rank` is present for **every** row and deterministically reconstructs the bump set `{ i | residual_rank_i ≤ d }`.

---

## 12.5 Optional table — `s3_site_sequence` (if S3 owns sequencing; see §11)

If sequencing is deferred to a later state, **do not** emit this table here. If S3 owns sequencing (Variant A in §11):

**Dataset id:** `s3_site_sequence`
**JSON-Schema anchor:** `schemas.1A.yaml#/s3/site_sequence`
**Partitions (path):** `parameter_hash={…}`
**Embedded lineage (columns):** `parameter_hash`, `produced_by_fingerprint?`
**Row ordering guarantee:** `(merchant_id ASC, country_iso ASC, site_order ASC)`

**Columns (binding):**

| Name                       | Type                      | Semantics                                           |
|----------------------------|---------------------------|-----------------------------------------------------|
| `merchant_id`              | `u64`                     | Canonical merchant key                              |
| `country_iso`              | `string(ISO-3166-1, A–Z)` | Country                                             |
| `site_order`               | `u32`                     | Contiguous `1..count_i` within country (from §11.3) |
| `site_id` *(optional)*     | `string(6)`               | Zero-padded 6-digit ID; overflow triggers §11.8     |
| `parameter_hash`           | `Hex64`                   | Embedded lineage                                    |
| `produced_by_fingerprint?` | `Hex64`                   | Embedded lineage                                    |

**Contracts:** see §11.5–§11.9.

---

## 12.6 Path↔embed equality (write-side checks)

For every written row in all S3 datasets:

* `row.parameter_hash` (embedded) **equals** the `parameter_hash` path partition (string-equal).
* If present, `row.produced_by_fingerprint` **equals** the run’s manifest fingerprint (informational only; not part of equality/partition).
* No other lineage fields appear in the path (e.g., **no `seed`**); any additional lineage fields must be **embedded** only.

Violation ⇒ **`ERR_S3_EGRESS_SHAPE`**.

---

## 12.7 Non-duplication & uniqueness (binding)

Per merchant:

* `s3_candidate_set`: unique `(country_iso)` and unique `(candidate_rank)`; exactly one `is_home==true` with `candidate_rank==0`.
* `s3_base_weight_priors` (if emitted): unique `(country_iso)`.
* `s3_integerised_counts` (if emitted): unique `(country_iso)`.
* `s3_site_sequence` (if emitted): unique `(country_iso, site_order)` (and `(country_iso, site_id)` if `site_id` present).

---

## 12.8 Example row *shapes* (illustrative; dictionary resolves paths)

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
  "produced_by_fingerprint": "cd34...90"
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
  "produced_by_fingerprint": "cd34...90"
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
  "produced_by_fingerprint": "cd34...90"
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
  "produced_by_fingerprint": "cd34...90"
}
```

---

## 12.9 Failure vocabulary (write-time)

| Code                              | Trigger                                                                            | Action                                            |
|-----------------------------------|------------------------------------------------------------------------------------|---------------------------------------------------|
| `ERR_S3_EGRESS_SHAPE`             | Schema violation; path↔embed mismatch; forbidden lineage in path; wrong JSON types | Stop S3 for merchant; **no** S3 outputs published |
| `ERR_S3_DUPLICATE_ROW`            | Duplicate key per dataset (e.g., duplicate `(country_iso)` or `(candidate_rank)`)  | Stop S3 for merchant; no outputs                  |
| `ERR_S3_ORDER_MISMATCH`           | `candidate_rank(home)≠0` or ranks not contiguous in emitted candidate set          | Stop S3 for merchant; no outputs                  |
| `ERR_S3_INTEGER_SUM_MISMATCH`     | Emitted counts don’t sum to `N` (when integerising)                                | Stop S3 for merchant; no outputs                  |
| `ERR_S3_SEQUENCE_GAP`/`…OVERFLOW` | See §11 sequencing errors                                                          | Stop S3 for merchant; no outputs                  |

---

## 12.10 Consumability notes (binding where stated)

* **Authority of order:** Consumers must use **`candidate_rank`** for inter-country order; file order is non-normative.
* **Priors meaning:** `base_weight_dp` are deterministic **priors**; consumers must not treat them as probabilities or re-normalise unless a later state explicitly says so.
* **Counts immutability:** If `s3_integerised_counts` is present, those counts are final for this stage and read-only downstream unless a new fingerprint changes.

---

This section gives implementers the **exact** shapes, partitions, lineage rules, and publish discipline for S3 outputs. Paired with §§8–11, it completes the blueprint so L0–L3 can be lifted directly without ambiguity.

---

# 13) Idempotence, concurrency, and skip-if-final

## 13.1 Scope (binding)

These rules apply to **all** S3 outputs defined in §12 (required and optional tables). They ensure **re-runs** and **parallelism** produce **byte-identical** results, with no double-writes, no order-dependence, and no cross-merchant interference. S3 uses **no RNG**.

---

## 13.2 Idempotence surface (what defines a unique result)

For a given merchant, S3’s outputs are a **pure function** of:

* The **Context** (§6.5) including `N`, `home_country_iso`, `mcc`, `channel`.
* The opened **artefacts** and **static references** listed in the BOM (§2), by *content bytes* (semver + digest).
* The **policy** (rule ladder) content bytes.
* The run’s **lineage keys** used at write time: `parameter_hash` (partition), `manifest_fingerprint` (embedded).

**Idempotence rule:** Given identical inputs above, S3 **must** produce **byte-identical** rows for the same merchant (same JSON number spellings, same order guarantees, same embedded lineage).

---

## 13.3 Concurrency invariance (parallel-safe by construction)

* **Merchant independence:** Every merchant’s S3 decisions depend only on that merchant’s Context and the governed artefacts. No global mutable state is read or written.
* **No cross-merchant ordering effects:** Sorting/selection rules operate **within merchant** (e.g., `candidate_rank` contiguity), never across merchants.
* **Stable determinism:** Because S3 is deterministic and does not use RNG, **re-partitioning** or changing thread counts **cannot** change bytes.
* **No speculative writes:** A merchant’s rows are written **only after** all its S3 steps succeed (no partial or incremental writes within S3).

---

## 13.4 Skip-if-final (at-most-one per merchant & run)

**Goal:** prevent duplicate rows when resuming or re-running the same logical work.

* Skip source: the dataset-level sidecar in the target partition (`parameter_hash`).
* Rule: If the sidecar’s `manifest_fingerprint` and `dataset_digest` match the would-be output, **skip** writing (idempotent no-op). (If rows carry `produced_by_fingerprint`, you MAY sanity-check equality as a convenience.)
* Conflict rule: If rows exist for `(merchant_id, manifest_fingerprint)` but their bytes **do not** match the would-be output, this is a violation (`ERR_S3_IDEMPOTENCE_VIOLATION`) and S3 must **stop for that merchant** without publishing changes.

> Rationale: S3 tables are **parameter-scoped** in path (`parameter_hash`) and **embed** `manifest_fingerprint`. Multiple manifests may legitimately coexist under the same `parameter_hash`; **skip-if-final** prevents duplicates **within a single manifest**.

---

## 13.5 Dataset-specific uniqueness (per merchant)

For the manifest named in the sidecar, the following must be unique per `merchant_id`:

* `s3_candidate_set`: keys `(country_iso)` **and** `(candidate_rank)` within a merchant block.
* `s3_base_weight_priors` (if emitted): key `(country_iso)`.
* `s3_integerised_counts` (if emitted): key `(country_iso)`; counts sum to `N`.
* `s3_site_sequence` (if emitted): key `(country_iso, site_order)` (and `(country_iso, site_id)` if present).

Any duplicate key in the same manifest is a shape error (`ERR_S3_DUPLICATE_ROW`) and must abort the merchant’s publish.

---

## 13.6 Publish protocol (atomic; resume-friendly)

* **Stage → fsync → atomic rename.** All S3 tables follow the same publish discipline; partial files are forbidden.
* **Row grouping:** A merchant’s rows **may** be appended to the same output file as other merchants (writer-side batching), but **logical uniqueness** is per keys in §13.5 and skip rule in §13.4.
* **Resume semantics:** On resume, S3 inspects the destination partition for `(merchant_id, manifest_fingerprint)`; if present and byte-identical, it **skips** emitting that merchant (no-op). If missing, it writes the rows atomically.
* **No deletions:** S3 does not delete or rewrite prior manifests; coexistence is allowed (partitioned by `parameter_hash`, distinguished by embedded `manifest_fingerprint`).

---

## 13.7 Read-side selection (downstream hygiene)

Downstream readers + Consumers assert the sidecar’s `manifest_fingerprint == <current_run>`. If rows include `produced_by_fingerprint`, they MAY also filter on it; otherwise read the whole `parameter_hash` partition.

---

## 13.8 Failure vocabulary (merchant-scoped; non-emitting)

| Code                           | Trigger                                                                                           | Action                                   |
|--------------------------------|---------------------------------------------------------------------------------------------------|------------------------------------------|
| `ERR_S3_IDEMPOTENCE_VIOLATION` | Existing rows for `(merchant_id, manifest_fingerprint)` differ byte-wise from the would-be output | Stop S3 for merchant; do **not** publish |
| `ERR_S3_DUPLICATE_ROW`         | Any dataset in §12 detects a key duplicate within `(merchant_id, manifest_fingerprint)`           | Stop S3 for merchant; do **not** publish |
| `ERR_S3_PUBLISH_ATOMICITY`     | Writer cannot guarantee atomic rename / fsync discipline                                          | Stop S3 for merchant; do **not** publish |

---

## 13.9 Invariants (must hold)

* Re-running S3 with the **same** artefacts, parameters, and Context produces **byte-identical** rows for each merchant.
* Parallelism and partitioning **do not** affect outputs.
* For any merchant and manifest, S3 emits **at most one** logical set of rows per dataset (skip-if-final enforced); dataset-specific keys in §13.5 are **unique**.
* All rows embed lineage equal to the run; path partition equals embedded `parameter_hash`.

---

This locks S3’s operational guarantees: **deterministic**, **parallel-safe**, and **resume-safe** with clear failure shapes—so implementers can scale and re-run without drift or surprises.

---

# 14) Failure signals (definition-level)

## 14.1 Scope & principles (binding)

* These failures are **definition-level**, not CI corridors. They represent **violations of the S3 spec** (inputs, ordering, shapes, lineage, determinism).
* **Non-emission rule:** On any failure below, **S3 must not publish any S3 outputs** for that merchant (no partial tables).
* **Granularity:** Failures are **merchant-scoped** unless explicitly marked **run-scoped**.
* **Evidence:** S3 may record a **merchant-scoped failure record** for operator visibility (outside S3 egress); this never relaxes the non-emission rule.

---

## 14.2 Merchant-scoped failures (authoritative list)

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

## 14.3 Run-scoped failures (rare; binding)

Run-scoped failures abort the **entire S3 run** (all merchants).

| Code                              | Trigger                                                                                                   | Effect                         |
|-----------------------------------|-----------------------------------------------------------------------------------------------------------|--------------------------------|
| `ERR_S3_SCHEMA_AUTHORITY_MISSING` | `schemas.layer1.yaml` (authoritative) is unavailable or inconsistent **(or the optional index, if used)** | **Abort run**; publish nothing |
| `ERR_S3_DICTIONARY_INCONSISTENT`  | Dataset dictionary cannot resolve required IDs or partitions for S3                                       | Abort run                      |
| `ERR_S3_BOM_INCONSISTENT`         | BOM claims artefacts that cannot be opened atomically across the run                                      | Abort run                      |

> Prefer merchant-scoped failure whenever the issue is isolated to a merchant; use run-scoped only for global authority problems.

---

## 14.4 Non-emission & logging contract (binding)

* **Non-emission:** On any failure above, S3 writes **no S3 datasets** for that merchant.
* **Logging:** A merchant-scoped failure **may** be recorded to an operator log with `{merchant_id, manifest_fingerprint, code, message, ts_utc}`; this log is **not** part of S3 egress.
* **No retries inside S3:** S3 does not auto-retry/auto-correct; recovery is orchestration policy.

---

## 14.5 Determinism & idempotence under failure

* Failures are **deterministic** given the same inputs; re-running with the same `parameter_hash` and artefacts must yield the **same** failure code.
* Skip-if-final (§13.4) applies only to **successful** publishes; on failure, there are **no** S3 rows to skip.

---

## 14.6 Consumer expectations (downstream hygiene)

* Downstream states **must not** infer intent from absence of S3 rows; orchestration should provide an explicit succeeded/failed roster.
* Consumers **must** filter by the intended `manifest_fingerprint` (§13.7); **do not** join across fingerprints.

---

## 14.7 Mapping index (where each failure originates)

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

# 15) Handoff to S4+

## 15.1 Scope (binding)

This section defines **how downstream states (S4+)** must consume S3 outputs. It is the only authority for:

* which S3 datasets to read,
* the **join keys** and **filters**,
* what fields are **binding** vs **illustrative**, and
* what downstream must **never** reinterpret.

Downstream may not infer semantics outside what is stated here.

---

## 15.2 What downstream must read

### 15.2.1 Required dataset (always)

| Dataset id         | Purpose                                                 | Filter (must)                                                                                                                                     | Ordering (must)                                                                       | Keys for joins               |
|--------------------|---------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|------------------------------|
| `s3_candidate_set` | Inter-country **order of record** + policy tags/reasons | Partition by `parameter_hash`; MAY filter `produced_by_fingerprint == <this run>` if present; always assert the sidecar’s `manifest_fingerprint`. | **Order by `(merchant_id ASC, candidate_rank ASC, country_iso ASC)`**; home at rank 0 | `(merchant_id, country_iso)` |

**Binding:** **`candidate_rank`** is the **sole** authority for inter-country order.

### 15.2.2 Optional datasets (present only if S3 owns them)

| Dataset id              | Purpose                                                        | Filter (must)        | Keys                                       |
|-------------------------|----------------------------------------------------------------|----------------------|--------------------------------------------|
| `s3_base_weight_priors` | Deterministic **priors** (fixed-dp strings), not probabilities | same filter as above | `(merchant_id, country_iso)`               |
| `s3_integerised_counts` | **Final integer counts** per country (sum to `N`)              | same filter as above | `(merchant_id, country_iso)`               |
| `s3_site_sequence`      | Within-country **site\_order** (and optional `site_id`)        | same filter as above | `(merchant_id, country_iso[, site_order])` |

> If an optional dataset is **not** produced by S3, downstream must not invent or guess it. The later state that owns it must produce it under its own spec.

---

## 15.3 Consumer recipe (minimal, closed)

### 15.3.1 Recover the ordered country list (always)

1. Select `s3_candidate_set` where `parameter_hash = <run.parameter_hash>`.
2. Filter `manifest_fingerprint == <run.manifest_fingerprint>`.
3. For each merchant, read rows ordered by `(candidate_rank ASC, country_iso ASC)`.
4. **Home row:** exactly one row with `candidate_rank == 0` and `is_home == true`.

Outcome: `⟨country_iso[0..M-1]⟩` with `country_iso[0] == home`.

### 15.3.2 If deterministic priors are present

* Read `s3_base_weight_priors.base_weight_dp` as a **score only** (fixed-dp string).
* Do **not** normalise to probabilities unless a later state explicitly requires it.

### 15.3.3 If integerised counts are present

* Join `s3_integerised_counts` on `(merchant_id, country_iso)` to get `count`.
* Trust `Σ_i count_i = N`; **do not recompute**. Treat counts as **final** for this stage.

### 15.3.4 If site sequencing is present

* Join `s3_site_sequence` on `(merchant_id, country_iso)`; rows sorted by `(country_iso, site_order)`.
* Within a country, `site_order` is **contiguous** `1..count_i`.
* If `site_id` exists, it is a **6-digit zero-padded string**; do not change format.

---

## 15.4 What downstream must **not** reinterpret (binding)

* **Inter-country order:** must come **only** from `candidate_rank`. Do not use file order or lexicographic `country_iso`.
* **Priors:** `base_weight_dp` are deterministic **priors**, not probabilities; do not normalise or rescale unless a later state says so.
* **Counts:** if `s3_integerised_counts` exists, counts are **final** for this stage; do not re-integerise or change bump policy.
* **Sequencing:** if `s3_site_sequence` exists, within-country order/IDs are binding; do not renumber or reformat IDs.
* **Policy evidence:** `reason_codes`/`filter_tags` are from **closed vocabularies**; do not remap outside a documented consumer map.

---

## 15.5 Lineage & selection (consumer hygiene)

Consumers **must** filter by both:

* the partition `parameter_hash = <run.parameter_hash>`, **and**
* `manifest_fingerprint == <run.manifest_fingerprint>`.

Do not join across **different fingerprints** unless explicitly implementing a multi-manifest analysis tool (out of scope here).

---

## 15.6 Allowed consumer transforms (safe)

* **Projection:** select a subset of columns.
* **Join:** equi-joins on keys in §15.2/§15.3.
* **Filtering:** by `merchant_id`, `candidate_rank` ranges, or `country_iso` subsets.
* **Stable sorting:** re-sorts that **do not** contradict `candidate_rank` (e.g., group by region but preserve `candidate_rank` within groups).

Any transform that would change `candidate_rank`, `count`, `site_order`, `site_id` format, or the fixed-dp representation of `base_weight_dp` is **not allowed** unless a later state’s spec explicitly authorises it.

---

## 15.7 Variant matrix (S3 configuration → consumer expectations)

| S3 config                                       | candidate\_set | base\_weight\_priors | counts | sequencing | Consumer expectation                                                  |
|-------------------------------------------------|----------------|----------------------|--------|------------|-----------------------------------------------------------------------|
| **A**: order-only                               | ✅              | ❌                    | ❌      | ❌          | Consumer uses **`candidate_rank`** only.                              |
| **B**: order + priors                           | ✅              | ✅                    | ❌      | ❌          | Use `base_weight_dp` as deterministic **prior**; do not normalise.    |
| **C**: order + counts                           | ✅              | ❌                    | ✅      | ❌          | Use `count` as final; no integerisation downstream.                   |
| **D**: order + counts + sequencing              | ✅              | ❌                    | ✅      | ✅          | Read `site_order`/`site_id` as binding within country.                |
| **E**: order + priors + counts (+/− sequencing) | ✅              | ✅                    | ✅      | ±          | Join by keys; priors are scores; counts final; sequencing if present. |

---

## 15.8 Failure surface for consumers (must stop)

A downstream consumer **must** treat these as **fatal** (merchant- or run-scoped per its own policy):

* Missing `s3_candidate_set` rows for the intended fingerprint.
* No `candidate_rank == 0` home row or duplicate `candidate_rank` within a merchant block.
* Present but malformed optional datasets (schema/type mismatches).
* Inconsistent priors (if duplicated elsewhere) or `Σ count ≠ N` (should not happen if S3 is green).
* Path/lineage inconsistencies (enforce §12/§13 read-side hygiene).

---

## 15.9 Forward-compat & evolution (practical guardrails)

* **Adding columns** to S3 tables requires a **schema semver bump** and backward-compatible defaults (or fields marked optional).
* **Changing dp** for priors requires a policy/artefact bump and thus a new `parameter_hash` (and new fingerprint).
* **Changing ID format** (e.g., `site_id`) requires a new schema version and migration note; until then, the 6-digit string is binding.

---

## 15.10 Consumer “green” checklist (quick)

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

# 16) Governance & publish

## 16.1 Scope (binding)

Fixes **how S3 is governed and published**: what must be opened and pinned, how lineage is formed, how outputs are staged and atomically committed, and what constitutes a valid publish. Applies to **all S3 datasets** defined in §12.

---

## 16.2 Artefact closure (BOM must be complete)

* S3 **may only** open artefacts explicitly listed in the BOM (§2).
* **Atomic open:** all governed artefacts (§2.1) are opened **before** any S3 processing starts. A missing/changed artefact after S3 begins is `ERR_S3_AUTHORITY_MISSING` (merchant-scoped stop).
* **No late opens:** later S3 steps **must not** open artefacts beyond §2.

---

## 16.3 Lineage keys (definitions & scope)

* **`parameter_hash` (path partition)** — hash of **parameter artefacts only** that affect S3 semantics (e.g., `policy.s3.rule_ladder.yaml`, `policy.s3.base_weight.yaml`, integerisation bounds). Changing any such parameter **changes the partition**.
* **`manifest_fingerprint` (embedded)** — composite derived from **all opened artefacts** (BOM closure), **parameter bytes**, and code/commit identity (project-defined). Any byte change flips the fingerprint.
* **No `seed` in S3 paths:** S3 outputs are **parameter-scoped**; `seed` appears only as an embedded lineage field if carried for joins.

**Binding equality:** every emitted row **embeds** `{parameter_hash, manifest_fingerprint}` that **byte-equal** the path partition (for `parameter_hash`) and the run’s fingerprint (§12.6).

---

## 16.4 Versioning & change policy

* **SemVer on artefacts:** governed artefacts carry semantic versions. Backward-compatible additions (that don’t change outcomes) may bump patch/minor. Any change that *can* alter S3 outputs **must** bump minor/major and will flip both `parameter_hash` and `manifest_fingerprint`.
* **Closed vocab drift:** adding/changing a `reason_code` / `filter_tag` / `rule_id` is *governed*; bump policy version and expect lineage flips.
* **Schema evolution:** any column addition/removal/type change is a **schema semver bump**; see consumer guidance in §15.9.

---

## 16.5 Publish protocol (atomic; resume-safe)

* **Resolution:** writers resolve dataset **IDs** to paths using the **dataset dictionary** (no literals).
* **Stage → fsync → atomic rename:** write to a staging area on the same filesystem, fsync, then atomically rename into `parameter_hash=…`.
* **All-or-nothing per dataset:** for a merchant, either the complete row-set for that dataset is present **byte-identical** to computed rows, or nothing is written. Partials are forbidden.
* **Skip-if-final:** before writing, check for existing rows for `(merchant_id, manifest_fingerprint)` in the target partition. If present and **byte-identical**, **skip** (idempotent no-op). If present but bytes differ ⇒ `ERR_S3_IDEMPOTENCE_VIOLATION` (no publish).
* **No deletes:** S3 never deletes prior manifests. Multiple manifests may coexist under the same `parameter_hash`; selection is via `manifest_fingerprint` (§15.5).

---

## 16.6 Partitioning & embedded lineage (write-side checks)

For every emitted dataset:

* **Partition:** `parameter_hash` only (no `seed`, no `run_id` in the path).
* **Embed:** each row embeds `{parameter_hash, manifest_fingerprint}` that **byte-equal** the path partition (for `parameter_hash`) and the run fingerprint.
* **Types:** lineage fields are **lowercase Hex64** strings; payload numbers are JSON **numbers**; fixed-dp priors are JSON **strings**.

Mismatch ⇒ **`ERR_S3_EGRESS_SHAPE`** and blocks publish for that merchant.

---

## 16.7 Governance attest (minimal, binding)

At publish time S3 must retain (operator audit; **outside S3 egress**):

* the **BOM snapshot** used (artefact ids, semver, digests),
* the **dictionary version** used to resolve paths, and
* the **schema authority/version** (`schemas.layer1.yaml`) and, if used, the **schema index** version.

---

## 16.8 Licence & provenance (must be auditable)

* Every external static reference (e.g., ISO list) must have recorded **licence** and **provenance** (§2.7).
* If licence constraints limit redistribution, embed **digests** and refer to artefacts by **id/version** (not copies).

---

## 16.9 Operator-visible publish receipt (optional; non-egress)

Optionally record a **publish receipt** per merchant (outside S3 datasets) with:

* `merchant_id`, `manifest_fingerprint`, `parameter_hash`, dataset ids written, row counts, and `ts_utc`.
  This improves observability only; presence/absence does **not** alter S3 semantics.

---

## 16.10 Run gating & dependencies (what S3 requires before start)

* **Schema authority present:** `schemas.layer1.yaml` containing all `#/s3/*` anchors is available and consistent; the **schema index** (if used) is also consistent.
* **Dictionary present:** required dataset IDs/partitions resolve.
* **BOM complete:** governed artefacts can be opened atomically.

Violation of any of the above is **run-scoped** failure (§14.3): `ERR_S3_SCHEMA_AUTHORITY_MISSING`, `ERR_S3_DICTIONARY_INCONSISTENT`, or `ERR_S3_BOM_INCONSISTENT`.

---

## 16.11 Governance “green” checklist (tick before publish)

* [ ] All governed artefacts from §2.1 opened **before** processing; no late opens.
* [ ] `parameter_hash` reflects all **parameter** artefacts; `manifest_fingerprint` reflects **all opened artefacts + parameters + code id**.
* [ ] All datasets resolved via the **dictionary**; **no path literals**.
* [ ] Partition and embedded lineage **match** (byte-equal).
* [ ] Skip-if-final performed; no duplicate logical writes.
* [ ] Atomic stage→fsync→rename completed without error.
* [ ] Optional receipts/attestations captured for operator audit.

---

## 16.12 Invariants (must hold)

* Given identical Context and artefact bytes, two S3 publishes produce **byte-identical** outputs.
* Re-partitioning or concurrency does **not** change outputs (no RNG; deterministic rules).
* For any dataset and merchant, there exists **at most one** logical row-set per `(manifest_fingerprint)`; duplicates are prevented by skip-if-final.
* All S3 outputs are parameter-scoped in path and carry embedded lineage equal to the run.

---

This governance & publish contract keeps S3 **reproducible**, **auditable**, and **operator-safe**—so implementers’ bytes are accepted or rejected in a predictable, deterministic way.

---

# 17) Worked micro-examples (illustrative)

These are **non-normative** sanity checks that show how the spec behaves on small inputs. Shapes and numbers are **illustrative** only; the **normative** behavior is in §§6–16. All paths resolve via the **dataset dictionary**; examples show **logical rows** only.

---

## 17.1 Minimal “allow” example — order + priors + integerisation

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

## 17.2 Tie-heavy example — no priors, ISO tiebreak

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

## 17.3 No-foreign example — deny cross-border

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

## 17.4 Edge case with bounds — bounded Hamilton (optional)

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

## 17.5 “Green” checklist for examples (what to verify quickly)

* [ ] **`candidate_rank(home)=0`**; ranks contiguous; no duplicate `country_iso`.
* [ ] If priors shown: fixed-dp **strings**; **ranking never uses priors** (priors affect integerisation only).
* [ ] Integerisation: residuals computed **after** dp; **`dp_resid=8`**; ties by ISO; counts sum to `N`.
* [ ] `residual_rank` present for **every** row when counts are emitted.
* [ ] Embedded lineage present and matches the active partition (`parameter_hash`) and run (`manifest_fingerprint`).
* [ ] No event streams (S3 uses none); only tables per §12.

---

*End of illustrative examples.*

---

# 18) Validator proof obligations (what L3 will re-derive)

## 18.1 Scope (binding)

* L3 is **read-only**. It **does not** mutate S3 outputs or produce S3 datasets.
* L3 **re-derives** the deterministic facts S3 promised in §§6–16 and either:
  • emits a **PASS** (run-scoped receipt outside S3 egress), or
  • raises the **precise** failure code(s) in §14 (merchant-scoped unless marked run-scoped).
* **No RNG**, no time dependence, no host state.

---

## 18.2 Inputs L3 must read (authoritative)

* **Schema authority & dictionary** (run-scoped gate): `schemas.layer1.yaml` containing all `#/s3/*` anchors; **optional** schema index if used; dataset dictionary resolving all S3 IDs.
* **Governed artefacts** listed in the S3 BOM (§2): `policy.s3.rule_ladder.yaml`, `iso3166_canonical_2024`, and any optional policy bundles (priors, bounds).
* **S3 datasets (egress)** for the target `parameter_hash`, MAY filter by `produced_by_fingerprint == <this run>` if present; otherwise read the whole `parameter_hash` partition (selection is parameter-scoped):
  `s3_candidate_set` (required); and optionally `s3_base_weight_priors`, `s3_integerised_counts`, `s3_site_sequence`.
* **Upstream evidence (read-only)** for cross-checks: S1 `hurdle_bernoulli` (gate) and S2 `nb_final` (for **N only**) for the same `{seed, parameter_hash, run_id}`.

*(All locations resolve via the dictionary; no literal paths.)*

---

## 18.3 What L3 must *never* do

* Must **not** “fix” data, interpolate, or re-emit S3 rows.
* Must **not** derive features not declared in §§2/6.
* Must **not** treat file order as semantic; only spec’d keys/order count.

---

## 18.4 Proof obligations (per merchant unless stated)

> Ordered **shape → lineage → order/math → cross-dataset coherence**. Each item cites the failure code on breach.

### V1 — Schema & JSON typing (shape)

* Every S3 row conforms to its **JSON-Schema** (§12).
* Numeric payload fields are JSON **numbers**; fixed-dp priors (if present) are JSON **strings** with exactly `dp` places.
  → `ERR_S3_EGRESS_SHAPE`.

### V2 — Partition ↔ embed equality (lineage)

* Embedded `parameter_hash` equals the **path partition**; embedded `manifest_fingerprint` equals the run fingerprint.
* S3 paths contain **no `seed`**.
  → `ERR_S3_EGRESS_SHAPE`.

### V3 — Gating & presence

* Join to S1: merchants with `is_multi==false` have **no S3 rows**.
* Join to S2: merchants used by S3 have exactly one `nb_final` with **`N ≥ 2`**.
  → `ERR_S3_PRECONDITION`.

### V4 — Candidate coverage & uniqueness

* `s3_candidate_set` exists; includes **exactly one** home row; **no duplicate** `(country_iso)`; all `country_iso ∈ ISO`.
  → `ERR_S3_CANDIDATE_CONSTRUCTION` or `ERR_S3_COUNTRY_CODE_INVALID`.

### V5 — Rank law (total order)

* Per merchant, **`candidate_rank`** is **contiguous** `0..|C|−1`; exactly one row has `candidate_rank==0` and `is_home==true`.
  → `ERR_S3_ORDERING_NONCONTIGUOUS` or `ERR_S3_ORDERING_HOME_MISSING`.

### V6 — Ordering proof (primary key = admission order key)

* Reconstruct each foreign row’s **admission key** from the artefact’s **closed mapping** (row `reason_codes[]` → admitting rule id(s)), then compute:

  ```
  K(r) = ⟨ precedence_rank(r), priority(r), rule_id_ASC ⟩
  Key1(i) = min_lex { K(r) : r ∈ AdmitRules(i) }
  ```
* Sort foreign rows by `Key1` → ISO A→Z; pin `home → candidate_rank=0`. The resulting order must match **`candidate_rank`**.
  → `ERR_S3_ORDERING_KEY_UNDEFINED` (cannot reconstruct key) or `ERR_S3_ORDERING_UNSTABLE` (mismatch).

### V7 — Priors surface (if present)

* If `s3_base_weight_priors` exists:
  • `base_weight_dp` parses as a fixed-dp decimal; **dp is constant within the run**.
  • Values are deterministic strings; no duplicate `(merchant_id,country_iso)`.
  *(No equality check vs candidate\_set — priors live **only** here.)*
  → `ERR_S3_EGRESS_SHAPE`.

### V8 — Integerisation reconstruction (if counts present)

* From S2 **N** and §10 policy:
  • If priors exist: use **quantised** `w_i^⋄` (from `base_weight_dp`) for shares; else equal shares.
  • Compute `a_i`, floors `b_i`, remainder `d`, residuals `r_i`; **quantise residuals to `dp_resid=8`**; apply bump rule (residual DESC → ISO A→Z → `candidate_rank` → stability).
  • Reconstruct `count_i`; verify **`Σ count_i = N`**, `count_i ≥ 0`; and `residual_rank` matches the bump order for **all** rows.
  → `ERR_S3_INTEGER_SUM_MISMATCH`, `ERR_S3_INTEGER_NEGATIVE`.

### V9 — Bounds (optional policy)

* If `(L_i,U_i)` are declared: verify `Σ L_i ≤ N ≤ Σ U_i` and `L_i ≤ count_i ≤ U_i`.
  → `ERR_S3_INTEGER_FEASIBILITY`.

### V10 — Sequencing (if S3 emits it)

* For each `(merchant_id,country_iso)` in `s3_site_sequence`:
  • `site_order` is **exactly** `1..count_i` (use counts if present; else check contiguity alone).
  • If `site_id` present: **6-digit zero-padded string**; uniqueness within the block.
  • Every `(merchant_id,country_iso)` also appears in `s3_candidate_set`.
  → `ERR_S3_SEQUENCE_GAP`, `ERR_S3_SEQUENCE_DUPLICATE`, or `ERR_S3_SITE_SEQUENCE_OVERFLOW`.

### V11 — Cross-dataset coherence

* Keys align across datasets (where present): `candidate_set` ↔ `base_weight_priors` ↔ `integerised_counts` ↔ `site_sequence`.
* No extra countries appear in optional tables that are absent from `candidate_set`.
  → `ERR_S3_EGRESS_SHAPE`.

### V12 — Dataset-specific uniqueness (write-side)

* Enforce §12.7 uniqueness:
  `candidate_set`: unique `(country_iso)` **and** `(candidate_rank)`;
  `base_weight_priors`: unique `(country_iso)`;
  `integerised_counts`: unique `(country_iso)`;
  `site_sequence`: unique `(country_iso, site_order)` (and `(country_iso, site_id)` if present).
  → `ERR_S3_DUPLICATE_ROW`.

### V13 — Idempotence surface (semantic)

* Re-compute a **content hash** of each merchant’s would-be rows from artefacts+Context to demonstrate outputs are a pure function (no dependency on file order/concurrency/host).
* If the same `(merchant_id, manifest_fingerprint)` already exists and bytes **differ**, classify as idempotence breach.
  → `ERR_S3_IDEMPOTENCE_VIOLATION`.

### V14 — Publish discipline (run-scoped sanity)

* Stage→fsync→atomic rename in use; no partials; no forbidden lineage in paths.
  → `ERR_S3_PUBLISH_ATOMICITY` (run-scoped) or `ERR_S3_EGRESS_SHAPE` (lineage/path issues).

---

## 18.5 Non-emission confirmation

On any merchant-scoped failure above, **no S3 tables** for that merchant are valid for this fingerprint. L3 treats the merchant as **failed** and excludes them from PASS.

---

## 18.6 PASS criteria (per merchant and run)

A merchant **PASS** iff **all** applicable obligations V1–V12 succeed.
The run **PASS** iff:

* all merchants PASS, and
* V14 (publish discipline) holds.

*(L3 may publish a small PASS/FAIL receipt outside S3 egress; content & location are governance-side and non-normative.)*

---

## 18.7 Validator “green” checklist (quick)

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