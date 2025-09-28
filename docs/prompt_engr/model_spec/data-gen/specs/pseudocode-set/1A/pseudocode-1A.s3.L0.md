# S3·L0 — Helpers & Primitives (state-local, deterministic, RNG-free)

# 0) Purpose, Scope, Non-Goals (S3·L0 — Helpers & Primitives)

## Purpose — what this file **is**

A small, **deterministic**, **RNG-free** toolbox for **State-3**. It exposes only the helpers S3 needs so L1/L2 can build and persist S3’s **parameter-scoped** outputs — required: `s3_candidate_set`; optional: `s3_base_weight_priors`, `s3_integerised_counts`, `s3_site_sequence` — **byte-identically** across re-runs. Wherever possible it **reuses** canonical primitives from prior L0s (dictionary/path resolution, lineage/partition checks, strict JSON/numbering, stable ordering) instead of re-implementing them.

**Concretely, S3·L0 provides:**

* **BOM loaders (read-only):** rule ladder, ISO-3166 country set, and optional policy knobs; process-local deterministic memo only.
* **Closed-vocabulary & ISO helpers:** normalise/validate reason codes and filter tags (A→Z), and ISO2 codes (uppercase).
* **Deterministic ordering key:** a total-order key function used by L1 to assign **`candidate_rank`** (home rank = 0; ranks contiguous).
* **Fixed-dp & LRR wrappers (optional features):** fixed-dp decimal strings for priors (scores, not probabilities), and a deterministic largest-remainder integeriser that records `residual_rank` (only if S3 owns counts).
* **Parameter-scoped emit shims:** thin writers for the S3 tables that enforce **embed = path** lineage equality and **no volatile fields**. Paths are **dictionary-resolved** only.

## Scope — how it connects to the rest

* **RNG-free by design.** S3 uses **no** pseudorandom draws; outcomes are fully deterministic (eligibility → candidate universe → ordering → optional priors/integerisation/sequence). S3·L0 therefore exposes **no** RNG writers or trace updaters; it only reuses lineage/partition/JSON and ordering primitives from S0/S1 L0 where relevant.
* **State interfaces.**

  * **L1** calls these helpers to build context, construct/normalise candidate rows, compute ranks, and (optionally) produce priors / integerised counts / sequences — all **pure** functions.
  * **L2** orchestrates and uses the S3·L0 emit shims to persist **parameter-scoped** tables (no `seed`), enforcing **embed = path** via the same partition verifiers used in prior states.
  * **L3** may reuse the fixed-dp parser and tiny predicates to validate schema conformance, contiguous ranks, and `Σ count = N`; actual validation lives in **L3**, not here.
* **Schema & dictionary authority.** Every emitter targets the **S3 anchors** in the layer schema and resolves via dictionary IDs — **partition key: `parameter_hash`** only for S3 datasets.

## Non-Goals — what this file **isn’t**

* **No RNG and no RNG trace.** No event envelopes (`before/after/blocks/draws`), no saturating trace updates (S1/S2 concern only).
* **No policy evaluation or rule firing.** The ladder evaluation/branching belongs in **S3·L1**; S3·L0 offers only predicates/normalisers.
* **No orchestration or host shims.** Looping, idempotence (`skip_if_final`), and publish belong in **S3·L2**; S3·L0 is host-agnostic and side-effect-free (except for minimal emit wrappers).
* **No validators/CI and no corridor math.** Those are **S3·L3** concerns.
* **No schema/dictionary edits or path literals.** Anchors/IDs come from the authoritative schema/dictionary; writers are dictionary-resolved and verify partitions on write.
* **No alternate numeric policy or timing artefacts.** S3 inherits the pinned binary64/ordering discipline from S0; S3 tables **must not** contain volatile timestamps.

**Summary.** S3·L0 is a lean, deterministic helper set that reuses prior L0 authority, targets the **RNG-free, parameter-scoped** S3 datasets, and leaves policy logic, orchestration, and validation to **L1/L2/L3** — giving implementers a clear, minimal surface with zero ambiguity.

---

# 1) Imports & Reuse Map (from S0/S1/S2)

This lists exactly what **S3·L0** reuses from prior L0s (and what it **does not** import), with the intent behind each import. No bodies here—just the binding surfaces we’ll call.

## 1.1 From S0 · L0 (foundational, state-agnostic)

* **Dictionary/path & partition verifier.** Use the dictionary-backed resolver(s) and the verifier that enforces **`embed == path`** lineage equality. We’ll call it for S3’s **parameter-scoped** tables (no `seed`).
* **Atomic write-then-rename.** Use the atomic temp-write → `fsync(tmp)` → **rename** contract for durable publishes.
* **PRNG core & open-interval mapping** *(read-only context for S3)*: Philox block advance, strict-open `u01( )`, Box–Muller invariants—kept for understanding upstream evidence only; S3 emits **no RNG**.
* **Numeric policy & serial reductions.** Reuse pinned binary64 / RNE / FMA-OFF policy and serial Neumaier reductions; S3 defines no new math policy.

## 1.2 From S1 · L0 (evidence I/O conventions; selected utilities)

* **Microsecond timestamp utility** `ts_utc_now_rfc3339_micro()` — **available** but **not used in S3 rows** (S3 tables must avoid volatile fields). Retained solely for deterministic stamps in logs/tools if needed.
* **Shortest round-trip float printer** `f64_to_json_shortest( )` — importable for validator/tools symmetry; S3 writers primarily produce **fixed-dp strings** for priors (scores, not probabilities).
* **`update_rng_trace_totals( )` (saturating) & event writer surfaces** — **not imported** for S3 emitters (S3 emits **no RNG** events/trace). Knowledge of S1’s saturating totals remains relevant only if S3·L3 reads S1/S2 traces.

## 1.3 From S2 · L0 (writer discipline & “single I/O surface” pattern)

* **Dictionary-resolved writer pattern (no path literals).** Resolve all paths via the dataset dictionary; never format paths in kernels. Apply this to S3 emitters for the `s3_*` datasets.
* **Evidence invariants (read-side only).** Budgets are **actual uniforms**; counters advance by blocks; certain events (e.g., `nb_final`) are **non-consuming**—useful when S3 cross-checks S2 inputs, but **not** emitted by S3.
* **Numeric environment reminders.** Reuse the sealed math profile and Neumaier ops; S3 defines no new numeric surfaces.

## 1.4 What S3 · L0 **does not** import (by design)

* **No RNG emitters or trace writers:** e.g., `begin_event_micro( )`, `end_event_emit( )`, `update_rng_trace_totals( )` remain S1/S2-only. S3 emits **parameter-scoped** tables via its **own** deterministic emit shims (dictionary-resolved, atomic publish).
* **No PRNG substreams/samplers** for generation (Philox, Box–Muller, Gamma, Poisson). S3 is **RNG-free**; these remain upstream context only.

## 1.5 Name-qualification & collision policy

* Where S0 and S1 expose similarly named helpers (e.g., trace updaters), S3·L0 **qualifies imports** and never mixes semantics. S1’s **saturating** totals apply only to S1/S2 evidence; S3 imports **neither** updater and emits no trace.

## 1.6 Efficiency posture (inherited)

* **No universe-wide materialisation.** Keep dictionary-resolved **streaming** writes; perform stable sorts only when needed.
* **Complexity targets.** S3 ranking **O(k log k)**; integerisation/sequence **O(k)**—aligned with prior states’ guidance.

> **Net:** S3·L0 reuses **verification, dictionary, atomic publish, and numeric discipline**; it **excludes** RNG writers/trace and PRNG kernels. All S3 outputs are written via state-local, dictionary-resolved emitters that enforce **`embed == path`** and avoid volatile fields.

---

# 2) Constants, Types & Canonical Representations

This pins the symbols, field shapes, and string forms that S3 helpers use/return. It mirrors the **authoritative schema** and the **S3 expanded spec** so L1/L2/L3 never guess types or names.

---

## 2.1 Dataset & schema IDs (single source of truth)

* **`s3_candidate_set`** → `schemas.1A.yaml#/s3/candidate_set`
  **Partition:** `parameter_hash={…}` (parameter-scoped only) • **Logical order:** `(merchant_id ASC, candidate_rank ASC, country_iso ASC)` • **Authority:** inter-country order lives **only** in `candidate_rank`.

* **`s3_base_weight_priors`** *(optional)* → `schemas.1A.yaml#/s3/base_weight_priors`
  **Partition:** `parameter_hash={…}` • **Logical order:** `(merchant_id ASC, country_iso ASC)` • Carries fixed-dp **decimal strings** for priors (scores, **not** probabilities).

* **`s3_integerised_counts`** *(optional)* → `schemas.1A.yaml#/s3/integerised_counts`
  **Partition:** `parameter_hash={…}` • Contains integer `count` and `residual_rank` (largest-remainder bump order).

* **`s3_site_sequence`** *(optional)* → `schemas.1A.yaml#/s3/site_sequence`
  **Partition:** `parameter_hash={…}` • Per-(merchant,country) contiguous `site_order` (1..nᵢ); optional zero-padded 6-digit `site_id`.

---

## 2.2 Canonical type aliases

* **`ISO2`** = uppercase ISO-3166-1 alpha-2 code. Helpers normalise to uppercase; validators check membership in the canonical ISO set.
* **`Hex64`** = 64-hexchar SHA-256 string (for `parameter_hash`, `manifest_fingerprint`). **Rows embed `parameter_hash`** (must equal path). Rows **may** include `produced_by_fingerprint` (optional provenance).
* **`FixedDpDecStr`** = decimal **string** with fixed places (e.g., `"0.275000"`), used **only** for priors; dp is carried in an integer field `dp`.
* **`CandidateRank`** = non-negative **int32**; **contiguous per merchant** with **home at 0**.

---

## 2.3 Records used across helpers (shape only)

* **`Lineage`**
  `{ parameter_hash: Hex64, produced_by_fingerprint?: Hex64 }` — every S3 row **embeds** `parameter_hash` (== path key). Rows **may** include `produced_by_fingerprint` (informational; equals the run’s manifest if present).

* **`BOM`** *(process-local read-only)*
  `{ ladder: Ladder, iso_universe: set<ISO2>, … }` — deterministic caches; no clocks.

* **`Ladder`** *(opaque here; parsed in L1)*
  Closed sets for `reason_codes` / `filter_tags`, precedence/priority ordering. Helpers expose normalisers/checks only.

* **`DecisionTrace`**
  `{ reason_codes: string[], filter_tags: string[] }` — arrays are **closed-vocab, A→Z sorted**.

* **`CandidateRow`** *(unordered; before ranking)*
  `{ merchant_id:u64, country_iso:ISO2, is_home:bool, DecisionTrace, Lineage }` — **no priors here**; ranking later adds `candidate_rank`.

* **`PriorRow`** *(optional; deterministic scores, not probabilities)*
  `{ merchant_id:u64, country_iso:ISO2, base_weight_dp:FixedDpDecStr, dp:int32, Lineage }`.

* **`CountRow`** *(optional; largest-remainder result)*
  `{ merchant_id:u64, country_iso:ISO2, count:int32≥0, residual_rank:int32, Lineage }` — **Σ count = N** from S2.

* **`SequenceRow`** *(optional)*
  `{ merchant_id:u64, country_iso:ISO2, site_order:int32≥1, site_id?:string("^[0-9]{6}$"), Lineage }`.

* **`RankedCandidateRow`** *(used after ranking in §11)*
  `{ merchant_id:u64, country_iso:ISO2, is_home:bool,
     reason_codes: string[], filter_tags: string[],
     candidate_rank:int32≥0, Lineage }`.

* **`Ctx`** *(merchant context fed to L1 kernels)*
  `{ ingress_row, s1_hurdle_row, s2_nb_final_row{N≥2}, home_country_iso:ISO2, channel:ingress_vocab, BOM, Lineage }`. (Numbers are JSON numbers; lineage equality must already hold.)

---

## 2.4 Canonical representation rules (apply to all S3 rows)

* **Numbers vs strings.** Payload numbers are JSON **numbers**, **except** priors, which are emitted as **fixed-dp decimal strings** with an explicit `dp`. **Do not** store probabilities or renormalise in S3.
* **Order authority.** Inter-country order is represented **only** by `candidate_rank` in `s3_candidate_set`; file order is non-authoritative. **Ranks are contiguous** `0..|C|−1` with **home=0**.
* **Residual precision.** When integerising, **quantise residuals to `dp_resid = 8`** before bumping; record `residual_rank` (strict descending residual → ISO A→Z tie-break).
* **Lineage embedding.** Every row embeds `parameter_hash` (**equals** the path key). Rows **may** include `produced_by_fingerprint`; the run’s **manifest** is recorded in the dataset-level sidecar.

---

## 2.5 Minimal constants (names only; bodies elsewhere)

* **Dataset IDs:** `"s3_candidate_set"`, `"s3_base_weight_priors"`, `"s3_integerised_counts"`, `"s3_site_sequence"`.
* **Schema anchors:** `#/s3/candidate_set`, `#/s3/base_weight_priors`, `#/s3/integerised_counts`, `#/s3/site_sequence`.
* **Tie-break tuple for ranking:** `(precedence, priority, rule_id_ASC, country_iso_ASC, stable_idx)` (L1 computes; L0 exposes the comparator key signature).
* **Fixed-dp example (illustrative only):** `"0.275000"` with `dp=6`; **do not** infer probabilities; priors live only in `s3_base_weight_priors`.

*This contract surface is what S3·L0 exports and enforces so L1/L2/L3 can operate without ambiguity.*

---

# 3) BOM Loaders (deterministic, read-only)

### Conventions

* `REQUIRES`, `ENSURES`, `RAISE` = contracts; `//` = comment.
* All artefacts are **dictionary/registry resolved by ID** (no path literals). S3 opens exactly:
  `policy.s3.rule_ladder.yaml` (required), `iso3166_canonical_2024` (required), and optionally `policy.s3.base_weight.yaml`, `policy.s3.thresholds.yaml`.
* S3 egress is **parameter-scoped**; this BOM is read-only and opened in **S3.0** before any S3 logic.

---

## 3.0 Design rules (apply to all loaders)

```
RULES:
  • Pure read-only; no RNG; no wall-clock dependence.
  • Resolve artefacts via dictionary/registry IDs (no path strings in code).
  • Process-local memo: first successful open is cached; subsequent calls return the same object.
  • All-or-nothing: if any required artefact fails validation, return no BOM and RAISE an error.
  • Include {id, semver, digest} meta for each artefact in the returned structs.
```

---

## 3.1 Outputs (types only; no bodies)

```
TYPE Meta        = { id: string, semver: string, digest: Hex64 }
TYPE Ladder      = { rules: Rule[], reason_codes: string[], filter_tags: string[], meta: Meta }
TYPE PriorsCfg   = { dp: int, selection_rules: RuleSpec[], constants: Map, meta: Meta }
TYPE BoundsCfg   = { floors?: Map<ISO2,int>, ceilings?: Map<ISO2,int>, dp_resid?: int, meta: Meta }
TYPE ISOUniverse = { set: Set<ISO2>, meta: Meta }
TYPE BOM         = { ladder: Ladder, iso_universe: ISOUniverse, priors_cfg?: PriorsCfg, bounds_cfg?: BoundsCfg }
```

---

## 3.2 PROC OPEN_BOM_S3(feature_flags) → BOM

```
INPUTS:
  feature_flags = { priors_enabled: bool, integerisation_enabled: bool }

STATE:
  static MEMO_BOM := null   // process-local memo

REQUIRES:
  DICT.IS_AVAILABLE() == true

IF MEMO_BOM != null:
  RETURN MEMO_BOM

LET ladder := LOAD_RULE_LADDER()
LET iso    := LOAD_ISO_UNIVERSE()

LET priors_cfg  := feature_flags.priors_enabled          ? LOAD_PRIORS_POLICY()            : null
LET bounds_cfg  := feature_flags.integerisation_enabled  ? LOAD_INTEGERISATION_THRESHOLDS(): null

LET bom := { ladder, iso_universe: iso, priors_cfg, bounds_cfg }

SET MEMO_BOM := bom
RETURN bom

COMPLEXITY: O(|rules| log |rules| + |iso|)
```

---

## 3.3 PROC LOAD_RULE_LADDER() → Ladder

```
LET id  := "policy.s3.rule_ladder.yaml"
LET res := DICT.RESOLVE(id)                      // {path, semver, digest}
REQUIRES: res != null

LET doc := READ_YAML(res.path)

// Binding validations (total order + closed vocabularies)
REQUIRES: ALL_UNIQUE( MAP(doc.rules, r -> r.rule_id) )
REQUIRES: FOR ALL r IN doc.rules: IS_INT(r.precedence) AND IS_INT(r.priority)
LET rules_total := STABLE_SORT(doc.rules, BY (r.precedence ASC, r.priority ASC, r.rule_id ASC))

LET reason := SORT_ASC( DEDUP( doc.reason_codes ) )
LET tags   := SORT_ASC( DEDUP( doc.filter_tags ) )

ENSURES: reason != null AND tags != null     // closed sets may be empty

RETURN { rules: rules_total, reason_codes: reason, filter_tags: tags, meta: res }

ON ERROR: RAISE ERR_S3_RULE_LADDER_INVALID
COMPLEXITY: O(|rules| log |rules| + |reason| log |reason| + |tags| log |tags|)
```

*(Ladder is a deterministic **total order** by `(precedence, priority, rule_id)`; reason/tags are **closed sets**.)*

---

## 3.4 PROC LOAD_ISO_UNIVERSE() → ISOUniverse

```
LET id  := "iso3166_canonical_2024"
LET res := DICT.RESOLVE(id)
REQUIRES: res != null

LET rows := READ_TABLE(res.path)                 // column: country_iso

LET S := EMPTY_SET()
FOR EACH row IN rows:
  LET c := UPPER(row.country_iso)
  REQUIRES: LENGTH(c) == 2 AND ALL_IN('A'..'Z', c)
  INSERT(S, c)

ENSURES: SIZE(S) > 0
RETURN { set: S, meta: res }

ON ERROR: RAISE ERR_S3_AUTHORITY_MISSING
COMPLEXITY: O(|rows|)
```

*(The canonical ISO set is a required authority for S3.)*

---

## 3.5 PROC LOAD_PRIORS_POLICY() → PriorsCfg      // optional

```
LET id  := "policy.s3.base_weight.yaml"
LET res := DICT.RESOLVE(id)
REQUIRES: res != null

LET doc := READ_YAML(res.path)

REQUIRES: IS_INT(doc.dp) AND 0 <= doc.dp <= 18
// Validate any referenced keys (e.g., MCC groups, country sets) via DICT as needed

ENSURES: NOT HAS_KEY(doc, "renormalise")   // S3 priors are deterministic scores, not probabilities

RETURN { dp: doc.dp, selection_rules: doc.selection_rules, constants: doc.constants, meta: res }

ON ERROR: RAISE ERR_S3_AUTHORITY_MISSING
COMPLEXITY: O(|doc|)
```

*(S3 emits priors only in `s3_base_weight_priors` as fixed-dp strings.)*

---

## 3.6 PROC LOAD_INTEGERISATION_THRESHOLDS() → BoundsCfg   // optional

```
LET id  := "policy.s3.thresholds.yaml"
LET res := DICT.RESOLVE(id)
REQUIRES: res != null

LET doc := READ_YAML(res.path)

IF HAS_KEY(doc, "floors"):
  FOR EACH (k,v) IN doc.floors:
    REQUIRES: IS_ISO2_CANONICAL(k) AND IS_INT(v) AND v >= 0

IF HAS_KEY(doc, "ceilings"):
  FOR EACH (k,v) IN doc.ceilings:
    REQUIRES: IS_ISO2_CANONICAL(k) AND IS_INT(v) AND v >= 0

IF HAS_KEY(doc, "dp_resid"):
  REQUIRES: IS_INT(doc.dp_resid) AND 0 <= doc.dp_resid <= 18

FOR EACH k IN INTERSECT(KEYS(doc.floors?), KEYS(doc.ceilings?)):
  REQUIRES: doc.floors[k] <= doc.ceilings[k]

RETURN { floors: doc.floors?, ceilings: doc.ceilings?, dp_resid: doc.dp_resid?, meta: res }

ON ERROR: RAISE ERR_S3_AUTHORITY_MISSING
COMPLEXITY: O(|floors| + |ceilings|)
```

*(Threshold semantics line up with S3’s optional integerised counts table.)*

---

## 3.7 Error vocabulary (merchant-scoped; non-emitting)

```
ERR_S3_AUTHORITY_MISSING    // required artefact missing/unopenable/invalid (incl. priors/bounds when enabled)
ERR_S3_RULE_LADDER_INVALID  // ladder fails total-order / vocab checks
```

---

## 3.8 Guarantees to downstream

* **Idempotent inputs ⇒ identical BOM** (same `{id, semver, digest}` per artefact), consistent with S3.0’s “open, validate, assemble Context; no writes”.
* BOM aligns with the **authoritative S3 egress datasets** and their **parameter-scoped** partitions; later emitters rely on this.

---

# 4) Closed-Vocabulary Utilities

**Goal.** Tiny, deterministic predicates and normalisers that enforce S3’s **closed sets** and **A→Z** ordering for emitted arrays. No RNG; no I/O; no path literals. Closed sets come from the **rule ladder** artefact (`reason_codes`, `filter_tags`); **ISO** from the canonical ISO table; **channel** from **ingress**.

### Conventions

* `REQUIRES`, `ENSURES`, `RAISE` = contracts; `//` = comment.
* All functions are **pure**; inputs/outputs are immutable values.
* Membership is **case-sensitive** (unless the artefact says otherwise). Exposed arrays are **A→Z** and **deduplicated**.

---

## 4.1 Precomputed vocab views (constant-time membership)

```
PROC BUILD_VOCAB_VIEWS(ladder: Ladder) → { REASONS:Set<string>, TAGS:Set<string> }
REQUIRES: ladder.reason_codes and ladder.filter_tags are closed sets (A→Z, deduped)
LET REASONS := SET_FROM_ARRAY(ladder.reason_codes)
LET TAGS    := SET_FROM_ARRAY(ladder.filter_tags)
RETURN { REASONS, TAGS }
COMPLEXITY: O(|reasons| + |tags|)
```

---

## 4.2 Reason-code utilities

```
PROC ASSERT_REASON_IN_CLOSED_SET(code: string, REASONS:Set<string>)
REQUIRES: code != ""  AND  REASONS != null
IF NOT CONTAINS(REASONS, code): RAISE ERR_S3_RULE_EVAL_DOMAIN
ENSURES: true
```

```
PROC NORMALISE_REASON_CODES(codes: array<string>, REASONS:Set<string>) → array<string>
REQUIRES: codes != null
LET out := EMPTY_ARRAY()
FOR EACH c IN codes:
  CALL ASSERT_REASON_IN_CLOSED_SET(c, REASONS)
  APPEND(out, c)
LET out := SORT_ASC(DEDUP(out))     // A→Z, case-sensitive
RETURN out
ENSURES: ALL_UNIQUE(out) AND IS_SORTED_ASC(out)
COMPLEXITY: O(n log n)
```

---

## 4.3 Filter-tag utilities

```
PROC ASSERT_TAG_IN_CLOSED_SET(tag: string, TAGS:Set<string>)
REQUIRES: tag != ""  AND  TAGS != null
IF NOT CONTAINS(TAGS, tag): RAISE ERR_S3_RULE_EVAL_DOMAIN
ENSURES: true
```

```
PROC NORMALISE_FILTER_TAGS(tags: array<string>, TAGS:Set<string>) → array<string>
REQUIRES: tags != null
LET out := EMPTY_ARRAY()
FOR EACH t IN tags:
  CALL ASSERT_TAG_IN_CLOSED_SET(t, TAGS)
  APPEND(out, t)
LET out := SORT_ASC(DEDUP(out))     // A→Z, case-sensitive
RETURN out
ENSURES: ALL_UNIQUE(out) AND IS_SORTED_ASC(out)
COMPLEXITY: O(n log n)
```

---

## 4.4 Channel vocabulary (ingress-inherited; read-only checks)

S3 defines **no** channel enum; it inherits the **ingress** schema vocabulary. To avoid drift, the vocabulary is **passed in** (e.g., from an ingress constants module), not hard-coded here.

```
PROC ASSERT_CHANNEL_IN_INGRESS_VOCAB(ch: string, CHANNEL_VOCAB: Set<string>)
REQUIRES: ch != ""  AND  CHANNEL_VOCAB != null
IF NOT CONTAINS(CHANNEL_VOCAB, ch): RAISE ERR_S3_RULE_EVAL_DOMAIN
ENSURES: true
```

---

## 4.5 Merchant-level tag union (A→Z, closed-set safe)

Used after rule evaluation to produce merchant-level tags handed to S3.2.

```
PROC MERCHANT_TAG_UNION(fired: array<RuleOutcome>, TAGS:Set<string>) → array<string>
/* RuleOutcome has field: outcome.tags : array<string> */
LET buf := EMPTY_ARRAY()
FOR EACH r IN fired:
  IF r.outcome.tags != null:
    FOR EACH t IN r.outcome.tags:
      CALL ASSERT_TAG_IN_CLOSED_SET(t, TAGS)
      APPEND(buf, t)
LET out := SORT_ASC(DEDUP(buf))     // A→Z
RETURN out
ENSURES: ALL_UNIQUE(out) AND IS_SORTED_ASC(out)
COMPLEXITY: O(n log n)
```

---

## 4.6 Candidate-row annotation helpers (A→Z, closed-set safe)

Map rule trace / merchant tags onto candidate rows without reinterpreting policy.

```
PROC MAKE_REASON_CODES_FOR_CANDIDATE(rule_trace: array<TraceRow>, REASONS:Set<string>) → array<string>
/* TraceRow has: reason_code:string? */
LET buf := EMPTY_ARRAY()
FOR EACH tr IN rule_trace:
  IF HAS_KEY(tr, "reason_code") AND tr.reason_code != null:
    CALL ASSERT_REASON_IN_CLOSED_SET(tr.reason_code, REASONS)
    APPEND(buf, tr.reason_code)
RETURN SORT_ASC(DEDUP(buf))         // A→Z
ENSURES: true
COMPLEXITY: O(n log n)
```

```
PROC MAKE_FILTER_TAGS_FOR_CANDIDATE(merchant_tags: array<string>, TAGS:Set<string>) → array<string>
RETURN NORMALISE_FILTER_TAGS(merchant_tags, TAGS)
```

---

## 4.7 Error vocabulary

```
ERR_S3_RULE_EVAL_DOMAIN  // predicate/annotation references a value outside closed vocabularies (reason/tag/channel)
```

---

## 4.8 Guarantees

* Membership is checked against **governed** sets (ladder + ingress schema).
* Emitted arrays are **A→Z** and deduped — byte-identical across re-runs.
* Utilities **do not** fire rules or write rows; L1/L2 own those steps.

---

# 5) ISO Helpers

**Goal.** Tiny, **deterministic**, RNG-free helpers for ISO-3166-1 alpha-2 handling. They (a) enforce the **canonical representation** S3 emits (exactly two **ASCII** uppercase letters `A`–`Z`), and (b) validate **membership** against the **canonical ISO universe** opened in the BOM. No I/O; no path literals; all functions are pure.

### Conventions

* Contracts: `REQUIRES`, `ENSURES`, `RAISE`; `//` = comment.
* All functions are **pure**, locale-independent, **ASCII-only**.

---

## 5.1 Low-level format predicates (ASCII, constant time)

```
// True iff s has length 2 and both chars are ASCII letters A–Z or a–z
FUNC IS_ASCII_ALPHA2(s: string) -> bool
REQUIRES: s != null
IF LENGTH(s) != 2: RETURN false
LET c0 := CODEPOINT(s[0]); LET c1 := CODEPOINT(s[1])
RETURN (IS_ASCII_ALPHA(c0) AND IS_ASCII_ALPHA(c1))

FUNC IS_ASCII_ALPHA(cp: int) -> bool
RETURN (cp >= 65 AND cp <= 90) OR (cp >= 97 AND cp <= 122)   // 'A'..'Z' or 'a'..'z'
```

**Determinism & perf.** O(1) per call; no locale or Unicode normalisation.

---

## 5.2 Canonical uppercase normaliser (ASCII-only)

```
FUNC UPPER_ASCII_2(s: string) -> string
REQUIRES: IS_ASCII_ALPHA2(s) == true
// Map 'a'..'z' to 'A'..'Z' by subtracting 32; leave 'A'..'Z' unchanged
LET b0 := BYTE(s[0]); LET b1 := BYTE(s[1])
IF b0 >= 97 AND b0 <= 122: b0 := b0 - 32
IF b1 >= 97 AND b1 <= 122: b1 := b1 - 32
RETURN STRING_FROM_BYTES([b0,b1])
```

**ENSURES.** Result is two bytes, each in `'A'..'Z'`.

---

## 5.3 Format checks & assertions

```
PROC ASSERT_ISO2_FORMAT(s: string)
REQUIRES: s != null
IF NOT IS_ASCII_ALPHA2(s): RAISE ERR_S3_ISO_INVALID_FORMAT
ENSURES: true

FUNC IS_ISO2_CANONICAL(s: string) -> bool
REQUIRES: s != null
RETURN IS_ASCII_ALPHA2(s) AND (s == UPPER_ASCII_2(s))
```

---

## 5.4 Membership against canonical ISO universe (from BOM)

```
// iso_universe is a Set<ISO2> opened by OPEN_BOM_S3()
PROC ASSERT_ISO2_MEMBER(c2: string, iso_universe: Set<string>)
REQUIRES: IS_ASCII_ALPHA2(c2)
LET canon := UPPER_ASCII_2(c2)
IF NOT CONTAINS(iso_universe, canon): RAISE ERR_S3_ISO_NOT_IN_UNIVERSE
ENSURES: true
```

---

## 5.5 One-shot normalise-and-validate (preferred for pipelines)

```
// Returns canonical ISO2, or raises if invalid / non-member
FUNC NORMALISE_AND_VALIDATE_ISO2(s: string, iso_universe: Set<string>) -> ISO2
REQUIRES: s != null
CALL ASSERT_ISO2_FORMAT(s)
LET canon := UPPER_ASCII_2(s)
CALL ASSERT_ISO2_MEMBER(canon, iso_universe)
RETURN canon
```

**Why:** most S3 kernels just need a valid, canonical ISO2. This single call provides it deterministically.

---

## 5.6 Arrays: normalise, validate, dedup, sort A→Z

```
FUNC NORMALISE_VALIDATE_DEDUP_SORT_ISO2(list: array<string>, iso_universe: Set<string>) -> array<ISO2>
REQUIRES: list != null
LET out_set := EMPTY_SET()    // dedup
FOR EACH s IN list:
  LET c := NORMALISE_AND_VALIDATE_ISO2(s, iso_universe)
  INSERT(out_set, c)
LET out := ARRAY_FROM_SET(out_set)
RETURN SORT_ASC(out)          // lexicographic A→Z
ENSURES:
  ALL_UNIQUE(out) AND IS_SORTED_ASC(out) AND FOR_ALL(out, x -> CONTAINS(iso_universe, x))
COMPLEXITY: O(n log n)
```

---

## 5.7 Comparator & ordering helpers (for stable total order)

```
// Lexicographic A→Z comparator for canonical ISO2
FUNC CMP_ISO2_AZ(a: ISO2, b: ISO2) -> int
REQUIRES: IS_ISO2_CANONICAL(a) AND IS_ISO2_CANONICAL(b)
IF a == b: RETURN 0
IF a < b: RETURN -1
RETURN +1
```

Used wherever ISO appears in a tie-break tuple (e.g., ranking key `(precedence, priority, rule_id, country_iso, stable_idx)`).

---

## 5.8 Error vocabulary

```
ERR_S3_ISO_INVALID_FORMAT   // not exactly 2 ASCII letters
ERR_S3_ISO_NOT_IN_UNIVERSE  // canonical ISO2 not present in BOM’s ISO universe
```

---

## 5.9 Guarantees & friction reduction

* **Single canonical form:** two **ASCII uppercase** letters everywhere S3 emits or compares ISO2.
* **Deterministic behaviour:** locale-free uppercasing; A→Z sort; stable comparator.
* **Authority-backed membership:** only ISO codes present in the **BOM** universe are accepted, preventing drift or aliases.

---

# 6) Admission-Order Key Builder (pure comparator support)

**Goal.** Provide a **single, total ordering** for foreign candidates (home is always rank 0). The order is computed **without RNG** from rule-ladder metadata and canonical ISO. We expose a **key function** and a comparator so L1/L2 can sort deterministically and assign `candidate_rank`.

### Conventions

* Contracts: `REQUIRES`, `ENSURES`, `RAISE`; `//` comments.
* All functions are **pure** (no I/O, no global state).
* Integers sort **ascending**; strings sort **A→Z**. See §5 for ISO helpers.

---

## 6.1 Types used by the key builder

```
TYPE AdmissionMeta = {
  precedence : int,     // ladder stratum; lower precedes higher
  priority   : int,     // within-stratum; lower precedes higher
  rule_id    : string,  // stable identifier from ladder
  country_iso: ISO2,    // canonical uppercase ISO2 (see §5)
  stable_idx : int      // last-resort tiebreak (input enumeration index, ≥0)
}
```

> `stable_idx` is supplied by the caller (typically “first-seen” order before any sorting). It guarantees a **total** order when all other fields tie.

---

## 6.2 Domain checks (fail fast)

```
PROC ASSERT_ADMISSION_META_DOMAIN(m: AdmissionMeta)
REQUIRES: m != null
IF NOT (IS_INT(m.precedence) AND m.precedence >= 0):      RAISE ERR_S3_ORDER_KEY_DOMAIN
IF NOT (IS_INT(m.priority)   AND m.priority   >= 0):      RAISE ERR_S3_ORDER_KEY_DOMAIN
IF NOT (IS_STRING(m.rule_id) AND LENGTH(m.rule_id) > 0):  RAISE ERR_S3_ORDER_KEY_DOMAIN
IF NOT IS_ISO2_CANONICAL(m.country_iso):                  RAISE ERR_S3_ORDER_KEY_DOMAIN   // §5
IF NOT (IS_INT(m.stable_idx) AND m.stable_idx >= 0):      RAISE ERR_S3_ORDER_KEY_DOMAIN
ENSURES: true
```

---

## 6.3 Key function (lexicographic tuple, ascending)

```
FUNC ADMISSION_ORDER_KEY(m: AdmissionMeta) -> tuple
REQUIRES: m != null
CALL ASSERT_ADMISSION_META_DOMAIN(m)
RETURN ( m.precedence,       // int ↑
         m.priority,         // int ↑
         m.rule_id,          // A→Z
         m.country_iso,      // A→Z (already canonical)
         m.stable_idx )      // int ↑
```

Use this **key** with a **stable sort** to obtain a **total, deterministic** order.

---

## 6.4 Comparator (for hosts that require one)

```
// Returns -1, 0, or +1
FUNC CMP_ADMISSION_ORDER(a: AdmissionMeta, b: AdmissionMeta) -> int
LET ka := ADMISSION_ORDER_KEY(a)
LET kb := ADMISSION_ORDER_KEY(b)
IF ka == kb: RETURN 0
IF ka <  kb: RETURN -1      // tuple lexicographic: ints asc, strings A→Z
RETURN +1
```

---

## 6.5 Assigning a stable index (deterministic last-resort tiebreak)

```
PROC ASSIGN_STABLE_IDX(foreigns: array<AdmissionMeta>) -> array<AdmissionMeta>
/* Preserves input enumeration; writes stable_idx = position */
REQUIRES: foreigns != null
FOR i FROM 0 TO LENGTH(foreigns)-1:
  LET m := foreigns[i]
  SET m.stable_idx := i
RETURN foreigns
ENSURES: FOR_ALL(i, foreigns[i].stable_idx == i)
COMPLEXITY: O(k)  // k = |foreigns|
```

> **Input order source.** Use the caller’s deterministic enumeration (e.g., the order foreigns were admitted after rule evaluation). If none exists, first canonicalise by ISO A→Z, then assign.

---

## 6.6 Sorting foreigners with the key

```
PROC SORT_FOREIGNS_BY_ADMISSION_KEY(foreigns: array<AdmissionMeta>) -> array<AdmissionMeta>
REQUIRES: foreigns != null
LET with_idx := ASSIGN_STABLE_IDX(foreigns)
LET out := STABLE_SORT(with_idx, key = ADMISSION_ORDER_KEY)
ENSURES: IS_NONDECREASING( MAP(out, m -> ADMISSION_ORDER_KEY(m)) )
RETURN out
COMPLEXITY: O(k log k)
```

---

## 6.7 Home handling (rank-0 invariant)

```
PROC SPLIT_HOME_AND_FOREIGNS(candidates: array<AdmissionMeta>, home_iso: ISO2) -> (AdmissionMeta, array<AdmissionMeta>)
REQUIRES: candidates != null  AND  IS_ISO2_CANONICAL(home_iso)
LET home := EMPTY_ARRAY()
LET foreigns := EMPTY_ARRAY()
FOR EACH m IN candidates:
  CALL ASSERT_ADMISSION_META_DOMAIN(m)
  IF m.country_iso == home_iso:
    APPEND(home, m)
  ELSE:
    APPEND(foreigns, m)
IF LENGTH(home) != 1: RAISE ERR_S3_ORDER_KEY_DOMAIN   // exactly one home required
RETURN (home[0], foreigns)
```

**Ranking usage:**

1. `home` → fixed rank **0**
2. `foreigns_sorted := SORT_FOREIGNS_BY_ADMISSION_KEY(foreigns)`
3. Assign ranks **1..k** in order (assignment happens in ranking; this section provides the order).

---

## 6.8 Error vocabulary

```
ERR_S3_ORDER_KEY_DOMAIN   // AdmissionMeta missing/invalid fields, or home cardinality not exactly 1
```

---

## 6.9 Guarantees & friction reduction

* **Single, documented ordering:** everyone uses the same key `(precedence, priority, rule_id, ISO, stable_idx)`.
* **Totality:** even perfect ties end deterministically via `stable_idx`.
* **Separation of concerns:** this section does **not** fire rules or write rows; it supplies a pure ordering primitive that L1 will use to assign `candidate_rank` with **home = 0** and contiguous foreign ranks.

---

# 7) Fixed-dp Quantisation Helpers (scores, not probabilities)

**Goal.** Emit **deterministic, fixed-decimal strings** for S3 “base-weight priors”. These are **scores (not probabilities)**; there is **no renormalisation** in S3. Rounding is **decimal round-half-even (banker’s)** at **dp** places. Helpers are **pure**, RNG-free, and language-agnostic.

### Conventions

* Contracts: `REQUIRES`, `ENSURES`, `RAISE`; `//` = comment.
* `FixedDpDecStr` = decimal string with exactly `dp` digits after the point (or no point if `dp=0`).
* **Rounding mode:** base-10 **half-even** at the `dp`-th fractional digit.
* **Domain:** non-negative, finite inputs only.
* **Uses:** `BINARY64_TO_RATIONAL(f64)->(num,den)` and exact `POW10(dp)` from numeric primitives (big-int).

---

## 7.0 Constants & error vocabulary

```
CONST MAX_DP := 18             // upper bound for fixed-dp fields

ERR_S3_PRIOR_DOMAIN            // invalid score: NaN / Inf / negative / out-of-range dp
ERR_S3_FIXED_DP_FORMAT         // string not matching required fixed-dp shape
```

---

## 7.1 Domain guards (reusable)

```
PROC ASSERT_DP_RANGE(dp: int)
REQUIRES: IS_INT(dp)
IF dp < 0 OR dp > MAX_DP: RAISE ERR_S3_PRIOR_DOMAIN
ENSURES: true

PROC ASSERT_SCORE_DOMAIN(w: f64)
REQUIRES: w != null
IF NOT IS_FINITE(w) OR w < 0.0: RAISE ERR_S3_PRIOR_DOMAIN
ENSURES: true
```

---

## 7.2 Exact decimal quantisation (half-even) → FixedDpDecStr

To avoid binary64 drift across languages, quantise **using integer/rational arithmetic** in base-10:

```
/*
 * QUANTIZE_WEIGHT_TO_DP
 * Rounds w to 'dp' decimal places (base-10 half-even) and returns a fixed-dp string.
 * Deterministic across languages (no locale; no float formatters).
 */
FUNC QUANTIZE_WEIGHT_TO_DP(w: f64, dp: int) -> FixedDpDecStr
REQUIRES:
  ASSERT_SCORE_DOMAIN(w)
  ASSERT_DP_RANGE(dp)

IF dp == 0:
  LET (num, den) := BINARY64_TO_RATIONAL(w)        // exact: w = num/den, gcd(num,den)=1
  LET q := FLOOR_DIV(num, den)
  LET r := MOD(num, den)
  // half-even at integer boundary:
  IF 2*r < den:      rounded := q
  ELSE IF 2*r > den: rounded := q + 1
  ELSE:              rounded := (EVEN(q) ? q : q + 1)
  RETURN DECIMAL_STRING(rounded)                   // no decimal point

// dp > 0
LET scale := POW10(dp)                             // exact 10^dp (big-int)
LET (num, den) := BINARY64_TO_RATIONAL(w)          // exact rational for binary64
LET t_num := num * scale                           // big-int multiply
LET q := FLOOR_DIV(t_num, den)                     // integer quotient
LET r := MOD(t_num, den)                           // remainder

// apply base-10 half-even at dp:
IF 2*r < den:      rounded := q
ELSE IF 2*r > den: rounded := q + 1
ELSE:              rounded := (EVEN(q) ? q : q + 1)

// split into integer and fractional parts at dp places
LET int_part  := FLOOR_DIV(rounded, scale)
LET frac_part := MOD(rounded, scale)               // 0 .. scale-1
LET frac_str  := ZERO_PAD_LEFT(DECIMAL_STRING(frac_part), dp)
IF dp > 0:
  RETURN CONCAT( DECIMAL_STRING(int_part), ".", frac_str )
ELSE:
  RETURN DECIMAL_STRING(int_part)
```

**Notes**

* `BINARY64_TO_RATIONAL(w)` returns the **exact** rational of the IEEE-754 binary64 input (mantissa/exponent decomposition).
* `POW10(dp)` must be exact; implement with big-int.
* `DECIMAL_STRING(k)` renders a non-negative integer in base-10 (ASCII), no separators.
* Handles arbitrarily large magnitudes (big-int).

**Complexity.** O(1) arithmetic; big-int cost ∝ digits of `w·10^dp`.

---

## 7.3 Fixed-dp parser (for validators/tools symmetry)

```
/*
 * PARSE_FIXED_DP
 * Validates a fixed-dp string and returns (value_as_rational, dp_detected).
 * Structural validation only; no rounding.
 */
FUNC PARSE_FIXED_DP(s: string) -> (num:int, den:int, dp:int)
REQUIRES: s != null AND s != ""
IF NOT MATCHES_REGEX(s, "^[0-9]+(\\.[0-9]+)?$"): RAISE ERR_S3_FIXED_DP_FORMAT

IF CONTAINS(s, "."):
  LET parts := SPLIT(s, ".", limit=2)
  LET a := parts[0]         // integer digits
  LET b := parts[1]         // fractional digits
  REQUIRES: LENGTH(a) >= 1 AND LENGTH(b) >= 1
  LET dp := LENGTH(b)
  LET den := POW10(dp)
  LET num := ATOI(a) * den + ATOI(b)   // exact (big-int)
  RETURN (num, den, dp)
ELSE:
  RETURN (ATOI(s), 1, 0)
```

**ENSURES:** Parsed `(num,den)` represents the **exact** decimal value; reduction not required.

---

## 7.4 Round-trip checker (helper; optional)

```
/*
 * ASSERT_FIXED_DP_ROUNDTRIP
 * Quantises w at dp and confirms it equals the provided fixed-dp string.
 */
PROC ASSERT_FIXED_DP_ROUNDTRIP(w: f64, dp: int, fixed: string)
REQUIRES: ASSERT_SCORE_DOMAIN(w); ASSERT_DP_RANGE(dp)
LET want := QUANTIZE_WEIGHT_TO_DP(w, dp)
IF want != fixed: RAISE ERR_S3_FIXED_DP_FORMAT
ENSURES: true
```

---

## 7.5 Examples (worked, edge-aware)  // comments for implementers

```
// dp=2 (half-even)
w=1.234  -> "1.23"             // < .235
w=1.235  -> "1.24"             // tie; preceding digit (3) is odd → rounds up
w=1.245  -> "1.24"             // tie; preceding digit (4) is even → stays
w=0.005  -> "0.00"             // tie to 0.01 vs 0.00 → 0.00 (even)
w=2.675  -> "2.68"             // canonical banker’s result

// dp=0
w=2.5    -> "2"                // tie to 2 vs 3 → 2 (even)
w=3.5    -> "4"                // tie → 4 (even)
```

---

## 7.6 Guarantees & friction reduction

* **Cross-language identical.** Integer/rational quantisation with **half-even** in base-10 yields the **same** string regardless of host float quirks.
* **No hidden semantics.** These are **scores**, not probabilities; **no renormalisation** anywhere in S3.
* **Schema-aligned.** Callers emit the string to `base_weight_dp` and the integer `dp` alongside; validators can use `PARSE_FIXED_DP` (and optionally `ASSERT_FIXED_DP_ROUNDTRIP`) to verify structure and exactness.

---

# 8) Largest-Remainder Integerisation (deterministic wrapper)

**Goal.** Convert **deterministic shares** into **integer counts** that sum to **N** using **Largest-Remainder (Hamilton)** with optional **floors/ceilings**, quantised residuals (`dp_resid`, default **8**) for stable bump order, and a recorded **`residual_rank`**. Pure, RNG-free, host-agnostic, cross-language identical.

### Conventions

* Contracts: `REQUIRES`, `ENSURES`, `RAISE`; `//` comments.
* Shares are **non-negative rationals**. If given as fixed-dp strings, parse first (§7).
* **Tie-break tuple (descending)**: `(residual_q, country_iso A→Z, stable_idx)` where `residual_q` is the **quantised** fractional remainder.
* Bounds are per-country **floors/ceilings**; infeasible inputs **error** (no “best effort”).

---

## 8.0 Types & errors

```
TYPE Rational = { num:int>=0, den:int>0 }   // exact value = num/den (no reduction required)

ERR_S3_INTEGERISATION_DOMAIN      // invalid inputs: N<0, empty lists, negative share, mismatched lengths
ERR_S3_INTEGERISATION_INFEASIBLE  // constraints make allocation impossible
```

---

## 8.1 Helpers (pure; integer/rational arithmetic only)

```
// exact base-10 half-even quantisation of a proper fraction r = num/den, 0 <= r < 1
FUNC QUANTISE_RESIDUAL(num:int, den:int, dp:int) -> int
REQUIRES: 0 <= num AND num < den AND den > 0 AND dp >= 0
LET scale := POW10(dp)                 // big-int
LET t := num * scale                   // big-int
LET q := FLOOR_DIV(t, den)             // 0..scale (half-even tie can bump q to 'scale')
LET rem := MOD(t, den)
IF 2*rem < den:      RETURN q
ELSE IF 2*rem > den: RETURN q + 1
ELSE:                RETURN (EVEN(q) ? q : q + 1)   // half-even
```

```
// normalise shares[] (Rational) to targets ti = N * (si / sum(s)) as exact rationals
FUNC TARGETS_FROM_SHARES(shares: array<Rational>, N:int) -> array<Rational>
REQUIRES: N >= 0 AND LENGTH(shares) >= 1 AND FOR_ALL(shares, s -> s.num >= 0 AND s.den > 0)
LET S := SUM_RATIONALS(shares)                     // exact
IF S.num == 0:                                     // all-zero shares ⇒ uniform split
  LET m := LENGTH(shares)
  RETURN [ { num:N, den:m } FOR EACH _ IN shares ] // each t_i = N/m
RETURN [ RATIONAL_MULTIPLY({num:N,den:1}, RATIONAL_DIVIDE(s_i,S)) FOR EACH s_i IN shares ]
```

---

## 8.2 Main entrypoint (weights as rationals)

```
PROC LRR_INTEGERISE(
  shares   : array<Rational>,    // length M; non-negative
  iso      : array<ISO2>,        // length M; canonical (uppercase, §5)
  N        : int,                // N >= 0 (from S2; typically >= 2)
  bounds?  : { floors?: Map<ISO2,int>=0, ceilings?: Map<ISO2,int>=0, dp_resid?: int>=0 },
  stable?  : array<int>=0        // optional deterministic last-resort index, length M
) -> (counts: array<int>=0>, residual_rank: array<int>=1)

REQUIRES:
  LENGTH(shares) == LENGTH(iso) == M AND M >= 1
  IF stable? provided: LENGTH(stable?) == M AND FOR_ALL(stable?, x -> x >= 0)
  FOR_ALL(shares, s -> s.num >= 0 AND s.den > 0)
  N >= 0

// ---- 1) Targets ----
LET T := TARGETS_FROM_SHARES(shares, N)           // exact rationals t_i
LET dp_resid := (bounds?.dp_resid != null) ? bounds.dp_resid : 8

// ---- 2) Bounds & feasibility skeleton ----
LET floor_i(i) := (bounds?.floors    has iso[i]) ? bounds.floors[iso[i]]    : 0
LET ceil_i(i)  := (bounds?.ceilings  has iso[i]) ? bounds.ceilings[iso[i]]  : +INF

// preliminary base counts = floor(t_i)
LET base := ARRAY_OF_SIZE(M)
FOR i IN 0..M-1:
  LET ti := T[i]
  base[i] := FLOOR_DIV(ti.num, ti.den)           // ⌊t_i⌋

// enforce floors
FOR i IN 0..M-1:
  IF base[i] < floor_i(i): base[i] := floor_i(i)

// hard feasibility by global bounds
LET sum_floor := SUM([floor_i(i) FOR i IN 0..M-1])
REQUIRES: sum_floor <= N
ELSE RAISE ERR_S3_INTEGERISATION_INFEASIBLE

// clamp to ceilings (no overshoot)
FOR i IN 0..M-1:
  IF base[i] > ceil_i(i): base[i] := ceil_i(i)

// base sum must not already exceed N
LET B := SUM(base)
IF B > N: RAISE ERR_S3_INTEGERISATION_INFEASIBLE

// ---- 3) Residuals, eligibility, capacity ----
LET residual_q := ARRAY_OF_SIZE(M)     // quantised residual bin (0..10^dp)
LET eligible   := ARRAY_OF_SIZE(M)     // can receive a +1 bump
FOR i IN 0..M-1:
  LET ti := T[i]
  // fractional remainder r_i = t_i - base[i]
  LET frac_num := ti.num - base[i]*ti.den
  IF frac_num < 0: frac_num := 0       // clamped above floor(t_i)
  residual_q[i] := QUANTISE_RESIDUAL(frac_num, ti.den, dp_resid)
  eligible[i]   := (base[i] < ceil_i(i))

// leftovers to place
LET R := N - B

// quick infeasibility under per-item +1 Hamilton constraint:
LET eligible_count := COUNT(i IN 0..M-1 WHERE eligible[i])
IF R > 0 AND eligible_count == 0: RAISE ERR_S3_INTEGERISATION_INFEASIBLE
IF R > eligible_count:
  // With Hamilton (largest-remainder), each item can receive at most one bump.
  RAISE ERR_S3_INTEGERISATION_INFEASIBLE

// ---- 4) Distribute leftovers by Largest-Remainder (one bump per eligible) ----
IF R > 0:
  // indices of eligible items
  LET idx := [ i FOR i IN 0..M-1 WHERE eligible[i] ]
  // sort by (residual_q DESC, iso ASC, stable_idx ASC)
  FOR j IN 0..LENGTH(idx)-1:
    LET i := idx[j]
    LET sidx := (stable? != null) ? stable?[i] : i
    ATTACH_SORT_KEY(idx[j], (-residual_q[i], iso[i], sidx))
  STABLE_SORT_BY_ATTACHED_KEY(idx)

  FOR k IN 0..R-1:
    LET i := idx[k]
    base[i] := base[i] + 1

// ---- 5) Residual ranking (full order for audit) ----
LET ord := [0..M-1]
FOR i IN 0..M-1:
  LET sidx := (stable? != null) ? stable?[i] : i
  ATTACH_SORT_KEY(ord[i], (-residual_q[i], iso[i], sidx))
STABLE_SORT_BY_ATTACHED_KEY(ord)

LET residual_rank := ARRAY_OF_SIZE(M)
FOR rank FROM 1 TO M:
  LET i := ord[rank-1]
  residual_rank[i] := rank

// ---- 6) Output ----
ENSURES:
  FOR_ALL(i, base[i] >= 0)
  SUM(base) == N
  FOR_ALL(i, base[i] >= floor_i(i))
  FOR_ALL(i, base[i] <= ceil_i(i))
RETURN (counts = base, residual_rank = residual_rank)
```

**Complexity.** `O(M log M)` due to sorting (eligibles + full residual-rank); otherwise linear.
**Determinism.** Pure integer/rational arithmetic; base-10 half-even residual quantisation; explicit tie-break tuple.

---

## 8.3 Convenience overload (from fixed-dp priors)

When priors are fixed-dp strings (`base_weight_dp` with `dp`), convert once and call the main routine.

```
PROC LRR_INTEGERISE_FROM_PRIORS(
  priors : array<{ base_weight_dp:string, dp:int, country_iso:ISO2 }>,
  N      : int,
  bounds?: { floors?: Map<ISO2,int>, ceilings?: Map<ISO2,int>, dp_resid?: int },
  stable?: array<int>
) -> (counts: array<int>, residual_rank: array<int>)

REQUIRES: LENGTH(priors) >= 1 AND N >= 0
LET m := LENGTH(priors)
LET shares := ARRAY_OF_SIZE(m)
LET iso    := ARRAY_OF_SIZE(m)
FOR i IN 0..m-1:
  LET (num, den, _) := PARSE_FIXED_DP(priors[i].base_weight_dp)   // §7
  shares[i] := { num, den }
  iso[i]    := priors[i].country_iso
RETURN LRR_INTEGERISE(shares, iso, N, bounds?, stable?)
```

---

## 8.4 Why this reduces implementer friction

* **Exactness.** Rational arithmetic + base-10 half-even quantisation ⇒ cross-language identical.
* **Bound-aware.** Floors/ceilings enforced up front; infeasibility detected early (no silent drift).
* **Traceable.** Emits a full **`residual_rank`** consistent with the bump order.
* **Deterministic ties.** Residual bin (quantised) → ISO A→Z → caller-supplied **stable_idx**.

---

# 9) Site Sequencing Helpers

**Goal.** Deterministically create **within-country** sequences for each merchant: contiguous `site_order = 1..nᵢ` and (optionally) a **zero-padded 6-digit** `site_id`. No RNG. No I/O. These helpers feed the optional S3 table **`s3_site_sequence`** (parameter-scoped) whose schema expects `(merchant_id, country_iso, site_order[, site_id])`.

---

## 9.0 Policy & bounds (binding)

* Sequencing is **per (merchant, country)** only. Cross-country order is handled elsewhere (`candidate_rank`), not here.
* `site_order` must be **contiguous** starting at **1**; no gaps, no duplicates.
* If emitting `site_id`, it is a **format of the order**: `"000001"` ↔ `site_order=1`, etc. Maximum supported `nᵢ` is **999 999**; beyond that is an error (table schema allows 6 digits).

---

## 9.1 Constants & errors

```
CONST SITE_ID_WIDTH := 6
CONST SITE_ID_MAX   := 999_999

ERR_S3_SEQ_DOMAIN        // invalid inputs: negative counts; null/empty arrays where not allowed
ERR_S3_SEQ_RANGE         // count_i exceeds SITE_ID_MAX when site_id is requested
ERR_S3_SEQ_NONCONTIGUOUS // constructed sequence is not 1..n_i without gaps
```

---

## 9.2 Low-level formatters (pure)

```
// "1" -> "000001" for width 6
FUNC FORMAT_SITE_ID_ZEROPAD6(k: int) -> string
REQUIRES: 1 <= k <= SITE_ID_MAX
LET s := DECIMAL_STRING(k)                 // ASCII, no separators
LET pad := SITE_ID_WIDTH - LENGTH(s)
RETURN REPEAT("0", pad) + s
```

```
// Guard when site_id emission is enabled
PROC ASSERT_SITE_ID_RANGE_OK(count_i: int)
REQUIRES: count_i >= 0
IF count_i > SITE_ID_MAX: RAISE ERR_S3_SEQ_RANGE
ENSURES: true
```

---

## 9.3 Per-country sequencing

```
/*
 * BUILD_SITE_SEQUENCE_FOR_COUNTRY
 * Deterministically builds site_order 1..count_i (and optional site_id).
 * Returns core rows; lineage is added by the emit surface.
 */
PROC BUILD_SITE_SEQUENCE_FOR_COUNTRY(
  merchant_id : u64,
  country_iso : ISO2,          // canonical uppercase (see §5)
  count_i     : int,           // >= 0
  with_site_id: bool
) -> array<{merchant_id:u64, country_iso:ISO2, site_order:int, site_id?:string}>

REQUIRES: count_i >= 0 AND IS_ISO2_CANONICAL(country_iso)
IF count_i == 0: RETURN EMPTY_ARRAY()

IF with_site_id: CALL ASSERT_SITE_ID_RANGE_OK(count_i)

LET rows := EMPTY_ARRAY()
FOR order FROM 1 TO count_i:
  LET sid := (with_site_id ? FORMAT_SITE_ID_ZEROPAD6(order) : null)
  APPEND(rows, { merchant_id, country_iso, site_order: order, site_id: sid })

// safety (construction already guarantees contiguity)
ENSURES: LENGTH(rows) == count_i
ENSURES: rows[0].site_order == 1 AND rows[-1].site_order == count_i
RETURN rows
```

**Complexity.** O(nᵢ). Pure, allocation-linear.

---

## 9.4 All-countries helper (convenience wrapper)

```
/*
 * BUILD_SITE_SEQUENCE_ALL
 * Vectorised convenience: applies per-country sequencing across aligned arrays.
 * Returns core rows; lineage is added by the emit surface.
 */
PROC BUILD_SITE_SEQUENCE_ALL(
  merchant_id : u64,
  iso_list    : array<ISO2>,    // length M
  counts      : array<int>,     // length M, each >= 0
  with_site_id: bool
) -> array<{merchant_id:u64, country_iso:ISO2, site_order:int, site_id?:string}>

REQUIRES:
  LENGTH(iso_list) == LENGTH(counts)
  FOR_ALL(counts, c -> c >= 0)
  FOR_ALL(iso_list, c2 -> IS_ISO2_CANONICAL(c2))

LET out := EMPTY_ARRAY()
FOR i FROM 0 TO LENGTH(counts)-1:
  IF with_site_id: CALL ASSERT_SITE_ID_RANGE_OK(counts[i])
  LET chunk := BUILD_SITE_SEQUENCE_FOR_COUNTRY(merchant_id, iso_list[i], counts[i], with_site_id)
  APPEND_ALL(out, chunk)

// sort to the table’s logical order: (merchant_id, country_iso, site_order)
RETURN STABLE_SORT(out, key=(merchant_id ASC, country_iso ASC /* ISO A→Z */, site_order ASC))
```

---

## 9.5 Validators (tiny guards you can reuse in L3)

```
PROC ASSERT_CONTIGUOUS_SITE_ORDER(rows: array<{site_order:int}>)
REQUIRES: rows != null
IF LENGTH(rows) == 0: RETURN
FOR i FROM 0 TO LENGTH(rows)-1:
  IF rows[i].site_order != i+1: RAISE ERR_S3_SEQ_NONCONTIGUOUS
ENSURES: true
```

```
PROC ASSERT_SITE_ID_MATCHES_ORDER(rows: array<{site_order:int, site_id:string}>)
REQUIRES: rows != null
FOR EACH r IN rows:
  IF r.site_id != FORMAT_SITE_ID_ZEROPAD6(r.site_order):
    RAISE ERR_S3_SEQ_DOMAIN
ENSURES: true
```

---

## 9.6 Guarantees & friction reduction

* **Deterministic & local.** Per-country sequencing uses only `count_i`, producing byte-stable results; no dependence on global order.
* **Schema-aligned.** Shapes match **`s3_site_sequence`** (lineage embedded later by the emit surface).
* **Safety rails.** Range checks prevent silent overflow of 6-digit `site_id`.
* **O(n) cost.** Linear in total sites; trivially parallel per country.

---

# 10) Merchant Context Assembly

**Goal.** Build a clean, deterministic **Ctx** for a merchant by stitching together the three authoritative inputs and the BOM—**without I/O** and **without RNG**—so S3 kernels can run with zero ambiguity. L0 stays pure; L2 fetches rows and verifies partitions via the dictionary resolver.

### Conventions

* Contracts: `REQUIRES`, `ENSURES`, `RAISE`; `//` comments.
* Inputs are **rows already read** by L2 (no path literals here).
* Lineage equality = same `parameter_hash` and same `manifest_fingerprint` across all inputs.
* **Row lineage vs Ctx.** `Ctx` carries the run `manifest_fingerprint` (for sidecar/idempotence); **rows embed `parameter_hash`** and **may** include `produced_by_fingerprint` (optional provenance).
* Channel vocabulary is inherited from **ingress**; ISO membership comes from **BOM.iso_universe**.

---

## 10.0 Types (recap from §2)

```
TYPE Ctx = {
  merchant_id       : u64,
  home_country_iso  : ISO2,          // canonical uppercase; in BOM.iso_universe
  channel           : string,        // in ingress closed vocabulary
  N                 : int,           // S2 accepted NB draw, N >= 2
  s1_is_multi       : bool,          // from S1 hurdle
  ingress_row       : Record,        // pass-through for kernels
  s1_hurdle_row     : Record,        // "
  s2_nb_final_row   : Record,        // "
  lineage           : Lineage,       // {parameter_hash, manifest_fingerprint}
  bom               : BOM
}
```

---

## 10.1 Error vocabulary

```
ERR_S3_CTX_MISSING_INPUTS      // a required row is null / absent
ERR_S3_CTX_MULTIPLE_INPUTS     // more than one row for the merchant in a required input
ERR_S3_CTX_LINEAGE_MISMATCH    // parameter_hash or manifest_fingerprint differ across inputs
ERR_S3_CTX_ID_MISMATCH         // merchant_id differs across ingress / S1 / S2 rows
ERR_S3_CTX_CHANNEL_DOMAIN      // channel not in ingress vocabulary
ERR_S3_CTX_ISO_DOMAIN          // home_country_iso not a valid ISO2 or not in BOM set
ERR_S3_CTX_ENTRY_GATES         // S1 says !is_multi OR S2 N < 2
```

---

## 10.2 Domain/shape guards (pure)

```
// Exactly-one-row checks (L2 should fetch, but we defend here)
PROC ASSERT_SINGLETON(rows: array<Record>, label: string)
REQUIRES: rows != null
IF LENGTH(rows) == 0: RAISE ERR_S3_CTX_MISSING_INPUTS with label
IF LENGTH(rows) > 1: RAISE ERR_S3_CTX_MULTIPLE_INPUTS with label
ENSURES: true

PROC ASSERT_LINEAGE_EQUAL(a: Record, b: Record)
REQUIRES: a != null AND b != null
IF a.parameter_hash != b.parameter_hash:             RAISE ERR_S3_CTX_LINEAGE_MISMATCH
IF a.manifest_fingerprint != b.manifest_fingerprint: RAISE ERR_S3_CTX_LINEAGE_MISMATCH
ENSURES: true

PROC ASSERT_SAME_MERCHANT_ID(a: Record, b: Record)
REQUIRES: a != null AND b != null
IF a.merchant_id != b.merchant_id: RAISE ERR_S3_CTX_ID_MISMATCH
ENSURES: true
```

---

## 10.3 Entry-gate & field validators (compose from §§4–5)

```
PROC ASSERT_CHANNEL_IN_INGRESS_VOCAB(ch: string, CHANNEL_VOCAB: Set<string>)
... // §4.4 — inherited ingress vocabulary; pass vocab set to avoid hard-coding

PROC NORMALISE_AND_VALIDATE_ISO2(s: string, iso_universe: Set<ISO2>) -> ISO2
... // §5.5 — uppercase ASCII + membership in BOM set

PROC ASSERT_S2_ACCEPTED_N(N: int)
REQUIRES: IS_INT(N) AND N >= 2
ELSE RAISE ERR_S3_CTX_ENTRY_GATES
ENSURES: true
```

---

## 10.4 Main routine (pure): build the merchant context

```
PROC BUILD_CTX(
  ingress_rows      : array<Record>,     // 0..1 row for merchant (fetched by L2)
  s1_hurdle_rows    : array<Record>,     // 0..1
  s2_nb_final_rows  : array<Record>,     // 0..1 (the non-consuming final)
  bom               : BOM,
  channel_vocab     : Set<string>        // ingress vocabulary, passed in to avoid hard-coding
) -> Ctx

REQUIRES: bom != null

// ---- 1) Uniqueness guards ----
CALL ASSERT_SINGLETON(ingress_rows,     "ingress")
CALL ASSERT_SINGLETON(s1_hurdle_rows,   "s1.hurdle")
CALL ASSERT_SINGLETON(s2_nb_final_rows, "s2.nb_final")

LET ingress := ingress_rows[0]
LET s1      := s1_hurdle_rows[0]
LET s2      := s2_nb_final_rows[0]

// ---- 2) Lineage & ID equality across inputs ----
CALL ASSERT_LINEAGE_EQUAL(ingress, s1)
CALL ASSERT_LINEAGE_EQUAL(ingress, s2)
CALL ASSERT_SAME_MERCHANT_ID(ingress, s1)
CALL ASSERT_SAME_MERCHANT_ID(ingress, s2)

// ---- 3) Entry gates (must be multi, and N >= 2) ----
IF s1.is_multi != true: RAISE ERR_S3_CTX_ENTRY_GATES
CALL ASSERT_S2_ACCEPTED_N(s2.n_outlets)

// ---- 4) Canonicalise & validate closed vocabularies ----
CALL ASSERT_CHANNEL_IN_INGRESS_VOCAB(ingress.channel, channel_vocab)
LET home_iso := NORMALISE_AND_VALIDATE_ISO2(ingress.home_country_iso, bom.iso_universe.set)

// ---- 5) Assemble lineage object (path↔embed equality verified by L2) ----
LET lin := {
  parameter_hash:       ingress.parameter_hash,
  manifest_fingerprint: ingress.manifest_fingerprint
}

// ---- 6) Build and return Ctx ----
RETURN {
  merchant_id      : ingress.merchant_id,
  home_country_iso : home_iso,
  channel          : ingress.channel,
  N                : s2.n_outlets,
  s1_is_multi      : s1.is_multi,
  ingress_row      : ingress,
  s1_hurdle_row    : s1,
  s2_nb_final_row  : s2,
  lineage          : lin,
  bom              : bom
}

COMPLEXITY: O(1) per merchant
```

---

## 10.5 Downstream guarantee (why this reduces friction)

* **Self-contained `Ctx`.** Kernels receive canonical `home_country_iso`, validated `channel`, and authoritative `N`—no reopening artefacts or rechecking lineage inside L1/L2.
* **Single-sourced lineage.** `Ctx.lineage = {parameter_hash, manifest_fingerprint}` matches all inputs; re-runs with the same lineage are byte-identical.
* **Clean separation.** L2 fetches and enforces path↔embed equality; **L0 assembles**, keeping S3 **RNG-free** and **idempotent**, mirroring S1/S2.
* **Schema/dictionary alignment.** Field names/types match authoritative anchors; consumers join on `merchant_id` and proceed without guessing.

---

# 11) Deterministic Ranking (assign `candidate_rank`, single source of inter-country order)

**Goal.** Assign a **total, contiguous order** to a merchant’s candidate countries with **home at rank 0**, and foreigns ranked deterministically using the §6 key. The resulting `candidate_rank` vector is the **only authority** for inter-country order in `s3_candidate_set`. No RNG. No I/O.

### Conventions

* Contracts: `REQUIRES`, `ENSURES`, `RAISE`; `//` comments.
* Inputs are **pure values** (already canonicalised: ISO uppercase; tags/reasons closed & A→Z).
* Strings sort **A→Z**; integers sort **ascending**.
* Use §6 `ADMISSION_ORDER_KEY` and §5 ISO helpers.

---

## 11.0 Types (recap)

```
TYPE CandidateRow = {
  merchant_id  : u64,
  country_iso  : ISO2,                 // canonical uppercase
  is_home      : bool,
  reason_codes : array<string>,        // closed set; A→Z; deduped
  filter_tags  : array<string>,        // closed set; A→Z; deduped
  lineage      : Lineage
}

TYPE AdmissionMeta = { precedence:int, priority:int, rule_id:string, country_iso:ISO2, stable_idx:int }  // §6
```

**Error vocabulary**

```
ERR_S3_RANK_DOMAIN          // missing home / multiple homes / duplicate countries
ERR_S3_RANK_KEY_DOMAIN      // bad AdmissionMeta (violates §6.2)
```

---

## 11.1 Guards (domain sanity before ranking)

```
// Exactly one home; each country appears at most once for the merchant
PROC ASSERT_RANK_DOMAIN(rows: array<CandidateRow>)
REQUIRES: rows != null AND LENGTH(rows) >= 1
LET seen := EMPTY_SET()
LET home_count := 0
FOR EACH r IN rows:
  IF r.is_home == true: home_count := home_count + 1
  IF CONTAINS(seen, r.country_iso): RAISE ERR_S3_RANK_DOMAIN   // duplicate country
  INSERT(seen, r.country_iso)
REQUIRES: home_count == 1
ENSURES: true
```

---

## 11.2 Split home vs foreigns (rank 0 invariant)

```
PROC SPLIT_HOME_FOREIGNS(rows: array<CandidateRow>, home_iso: ISO2)
REQUIRES: rows != null
LET home := null
LET foreigns := EMPTY_ARRAY()
FOR EACH r IN rows:
  IF r.country_iso == home_iso:
    home := r
  ELSE:
    APPEND(foreigns, r)
REQUIRES: home != null
RETURN (home, foreigns)
```

*(Home ISO comes from §10 Ctx; S3 guarantees exactly one home candidate.)*

---

## 11.3 Build admission metas for foreigns (pure)

```
/*
 * Creates the AdmissionMeta array needed by the §6 key.
 * Caller supplies ladder-derived precedence/priority/rule_id per foreign.
 */
PROC MAKE_ADMISSION_META(foreigns: array<CandidateRow>, meta_src: Map<ISO2, {precedence:int, priority:int, rule_id:string}>) 
    -> array<AdmissionMeta>
REQUIRES: foreigns != null
LET out := EMPTY_ARRAY()
FOR i FROM 0 TO LENGTH(foreigns)-1:
  LET f := foreigns[i]
  LET m := meta_src[f.country_iso]   // must exist; derived from S3 rule trace
  LET a := {
    precedence : m.precedence,
    priority   : m.priority,
    rule_id    : m.rule_id,
    country_iso: f.country_iso,
    stable_idx : i                    // deterministic last-resort tie-break (§6.5)
  }
  CALL ASSERT_ADMISSION_META_DOMAIN(a)  // §6.2
  APPEND(out, a)
RETURN out
```

---

## 11.4 Sort foreigns with the §6 ordering key

```
PROC ORDER_FOREIGNS(foreigns: array<CandidateRow>, metas: array<AdmissionMeta>) 
    -> array<CandidateRow>
REQUIRES: LENGTH(foreigns) == LENGTH(metas)
LET idx := [0..LENGTH(foreigns)-1]
STABLE_SORT(idx, key = (i -> ADMISSION_ORDER_KEY(metas[i])))   // §6.3
LET out := EMPTY_ARRAY()
FOR EACH j IN idx: APPEND(out, foreigns[j])
RETURN out
```

---

## 11.5 Assign contiguous candidate_rank (home=0)

```
/*
 * RANK_CANDIDATES — single source of inter-country order
 */
PROC RANK_CANDIDATES(
  rows     : array<CandidateRow>,
  meta_src : Map<ISO2, {precedence:int, priority:int, rule_id:string}>,
  home_iso : ISO2
) -> array<RankedCandidateRow>  // explicit return type with candidate_rank field

REQUIRES: ASSERT_RANK_DOMAIN(rows)
// Use canonical home ISO from §10 Ctx, and assert alignment with the single is_home row
LET (home, foreigns) := SPLIT_HOME_FOREIGNS(rows, home_iso)
REQUIRES: home.is_home == true
LET metas := MAKE_ADMISSION_META(foreigns, meta_src)
LET ordered_foreigns := ORDER_FOREIGNS(foreigns, metas)

// Build candidate_rank vector aligned to (home :: ordered_foreigns)
LET ranks := MAP(rows, _ -> -1)
LET rank_map := MAP<ISO2,int>()
SET rank_map[home.country_iso] := 0
FOR k FROM 0 TO LENGTH(ordered_foreigns)-1:
  SET rank_map[ ordered_foreigns[k].country_iso ] := k + 1

FOR i FROM 0 TO LENGTH(rows)-1:
  LET c := rows[i].country_iso
  ranks[i] := rank_map[c]

// Sanity: contiguous 0..|rows|-1
REQUIRES: SET_EQUALS( SET(ranks), SET( [0..LENGTH(rows)-1] ) )

ENSURES:
  COUNT(r IN rows WHERE ranks[INDEX_OF(rows,r)] == 0 AND r.is_home) == 1
  IS_NONDECREASING( SORT(ranks) )  // implicitly 0..K contiguous

// Build ranked rows with field attached (host may map to schema later)
LET ranked := EMPTY_ARRAY<RankedCandidateRow>()
FOR i FROM 0 TO LENGTH(rows)-1:
  LET r := rows[i]
  APPEND(ranked, r + { candidate_rank: ranks[i] })
RETURN ranked
```

**Complexity.** O(K log K) where K = #foreigns; linear otherwise.
**Determinism.** Pure; relies only on §6 key, canonical ISO, and stable_idx from enumeration.

---

## 11.6 Postconditions for `s3_candidate_set` rows (what L2 emits later)

When L2 uses the ranked rows to emit `s3_candidate_set` it must ensure (enforced by L3 too):

* `candidate_rank` is **total & contiguous** per merchant; **home rank = 0**.
* **Single source of truth:** downstream **must use `candidate_rank` only** for inter-country order (never file order or ISO).
* Table is parameter-scoped; row order `(merchant_id, candidate_rank, country_iso)` is **logical** only.

---

## 11.7 Why this reduces friction

* **One documented ordering**: `(precedence, priority, rule_id, ISO, stable_idx)`, same everywhere.
* **No surprises**: home → 0; foreigns contiguous; duplicates and domain errors fail fast.
* **Schema-aligned**: exactly matches `s3_candidate_set`’s “total, contiguous” rank contract and “single authority for order”.

---

# 12) Optional: Priors (S3·L0 — deterministic scores, not probabilities)

**Goal.** When the *priors* feature is enabled, compute a **deterministic score** per `(merchant_id, country_iso)` candidate and emit it as a **fixed-decimal string** `base_weight_dp` with an explicit integer `dp`. These are **scores (not probabilities)**; **no renormalisation** is performed in S3. The single source of truth is **`s3_base_weight_priors`** (`schemas.1A.yaml#/s3/base_weight_priors`, partitioned by `parameter_hash`).

### Conventions

* Contracts: `REQUIRES`, `ENSURES`, `RAISE`; `//` comments.
* Pure, RNG-free; no I/O; no path literals.
* `dp` is **constant within a run** (policy-bound) and **must not** vary across rows for the same `parameter_hash`.

---

## 12.0 Errors and constants

```
ERR_S3_PRIOR_DISABLED         // feature disabled (no priors_cfg) but priors were requested
ERR_S3_PRIOR_DOMAIN           // NaN/Inf/negative score; dp out of range; missing required inputs
ERR_S3_PRIOR_DP_INCONSISTENT  // observed dp differs within the same run (not allowed)

CONST MAX_DP := 18            // fixed upper bound for dp
```

---

## 12.1 Inputs & policy surface

**Inputs (pure values):**

* `ranked_candidates : array<CandidateRow>`  // from §11 (canonicalised)
* `ctx               : Ctx`                  // from §10 (lineage, BOM, channel, N≥2)
* `priors_cfg        : PriorsCfg | null`     // from BOM (§3): `{ dp:int, selection_rules:RuleSpec[], constants:Map }`

**Policy rules.** `selection_rules` deterministically choose which candidates receive a prior and how to compute a **non-negative** base score from fields in `Ctx`/candidate. No randomness; no time dependence.

---

## 12.2 Guards & shared helpers (reused from §7)

```
PROC ASSERT_DP_RANGE(dp:int)
REQUIRES: IS_INT(dp) AND 0 <= dp <= MAX_DP
ELSE RAISE ERR_S3_PRIOR_DOMAIN
ENSURES: true

PROC ASSERT_SCORE_DOMAIN(w:f64)
REQUIRES: IS_FINITE(w) AND w >= 0.0
ELSE RAISE ERR_S3_PRIOR_DOMAIN
ENSURES: true

FUNC QUANTIZE_WEIGHT_TO_DP(w:f64, dp:int) -> FixedDpDecStr
... // §7: decimal half-even via exact integer/rational path (cross-language identical)
```

---

## 12.3 Selecting `dp` (constant per run)

```
FUNC SELECT_PRIOR_DP(priors_cfg:PriorsCfg | null) -> int
REQUIRES: priors_cfg != null
ELSE RAISE ERR_S3_PRIOR_DISABLED
CALL ASSERT_DP_RANGE(priors_cfg.dp)
RETURN priors_cfg.dp
```

**Guarantee.** A single `dp` is used for all rows in `s3_base_weight_priors` for a given `parameter_hash`. Changing `dp` is a **policy change** and implies a new fingerprint/`parameter_hash`.

---

## 12.4 Policy evaluation hook (deterministic score, policy-defined)

```
/*
 * EVAL_PRIOR_SCORE — pure, policy-defined algebra (no RNG, no clocks)
 * Returns a non-negative real score for (merchant, country) or null if not selected.
 */
FUNC EVAL_PRIOR_SCORE(c: CandidateRow, ctx: Ctx, priors_cfg:PriorsCfg) -> f64 | null
REQUIRES: c != null AND ctx != null AND priors_cfg != null
LET selected := MATCHES_SELECTION_RULES(c, ctx, priors_cfg.selection_rules)
IF NOT selected: RETURN null
LET w := DETERMINISTIC_FORMULA(c, ctx, priors_cfg.constants)   // pure arithmetic
CALL ASSERT_SCORE_DOMAIN(w)
RETURN w
```

---

## 12.5 Computing priors for a merchant (pure; RNG-free)

```
/*
 * COMPUTE_PRIORS_FOR_MERCHANT
 * Produces PriorRow[] for the merchant’s candidates where the policy applies.
 * No renormalisation: output strings are scores, not probabilities.
 */
PROC COMPUTE_PRIORS_FOR_MERCHANT(
  ranked_candidates : array<CandidateRow>,
  ctx               : Ctx,
  priors_cfg        : PriorsCfg | null
) -> array<PriorRow>   // {merchant_id, country_iso, base_weight_dp:string, dp:int}

REQUIRES: ranked_candidates != null AND LENGTH(ranked_candidates) >= 1
LET dp := SELECT_PRIOR_DP(priors_cfg)        // raises ERR_S3_PRIOR_DISABLED if null

LET out := EMPTY_ARRAY()
FOR EACH c IN ranked_candidates:
  LET w := EVAL_PRIOR_SCORE(c, ctx, priors_cfg)   // may be null (not selected)
  IF w == null: CONTINUE
  CALL ASSERT_SCORE_DOMAIN(w)
  LET s := QUANTIZE_WEIGHT_TO_DP(w, dp)           // §7 half-even; fixed-dp string
  APPEND(out, {
    merchant_id   : c.merchant_id,
    country_iso   : c.country_iso,
    base_weight_dp: s,
    dp            : dp
  })

RETURN STABLE_SORT(out, key=(merchant_id ASC, country_iso ASC))

ENSURES: FOR_ALL(r IN out, r.dp == dp)   // dp constant within the returned set
```

**Complexity.** O(K log K) (K = #candidates), dominated by final sort; per-row work is O(1) arithmetic + quantisation.
**Determinism.** Pure and RNG-free. Identical inputs (including `priors_cfg`) → identical fixed-dp strings.

---

## 12.6 Run-wide dp consistency (defensive aggregator)

```
PROC ASSERT_DP_CONSTANT_OVER_BLOCK(rows: array<PriorRow>)
REQUIRES: rows != null
IF LENGTH(rows) == 0: RETURN
LET d0 := rows[0].dp
FOR EACH r IN rows:
  IF r.dp != d0: RAISE ERR_S3_PRIOR_DP_INCONSISTENT
ENSURES: true
```

---

## 12.7 Emission contract (hand-off to L2 emitters)

* L2 attaches **lineage** (`parameter_hash`, `manifest_fingerprint`) and persists to **`s3_base_weight_priors`** (parameter-scoped) with ordering `(merchant_id, country_iso)`.
* Consumers **must** read priors **only** from this table; `s3_candidate_set` does **not** carry priors. **No renormalisation** by consumers.

---

## 12.8 Why this reduces friction

* **Single table, single format.** One place to read priors; fixed-dp strings with explicit `dp`.
* **Deterministic & cross-language.** Decimal **half-even** quantisation via the integer/rational path; identical outputs on any host.
* **No hidden semantics.** Scores ≠ probabilities; **no renormalisation** in S3; `dp` changes only with policy/fingerprint.

---

# 13) Optional: Integerisation (S3·L0 — deterministic counts from shares)

**Goal.** If the *integerisation* feature is enabled, convert **deterministic shares** over a merchant’s ranked candidates into **integer counts** that sum to **N** (from S2), using **Largest-Remainder (Hamilton)** with fixed tie-breaks and recorded **`residual_rank`**. No RNG. No I/O. Shares may come from S3 priors (fixed-dp strings) or, if absent/degenerate, **uniform** fallback. Bounds (per-country floors/ceilings) are honoured when provided by policy.

### Conventions

* Contracts: `REQUIRES`, `ENSURES`, `RAISE`; `//` comments.
* This section **wraps** §8 LRR primitives; it decides *which* shares to use and ensures schema-aligned outputs.
* Inputs are **pure values** (rows already read; BOM already opened). All ISO are canonical uppercase (§5). Home has no special treatment here beyond any bounds.

---

## 13.0 Errors & constants

```
ERR_S3_INT_DISABLED           // feature disabled but integerisation requested
ERR_S3_INT_DOMAIN             // invalid inputs: empty candidate set, bad N, missing ctx, bad priors shape
ERR_S3_INT_INFEASIBLE         // infeasible after applying floors/ceilings or not enough capacity
```

---

## 13.1 Inputs (pure)

```
ranked_candidates : array<CandidateRow>   // from §11; includes home & foreigns; canonical ISO
ctx               : Ctx                   // from §10; contains N ≥ 2, lineage, etc.
priors?           : array<PriorRow>       // from §12 (optional): base_weight_dp:string, dp:int, per (merchant,country)
bounds_cfg?       : BoundsCfg             // from §3 (optional): floors/ceilings maps, dp_resid
```

**Binding facts**

* `ctx.N` is the **authoritative** total sites (accepted NB draw, **N ≥ 2** for S3).
* If `priors?` is present, it may cover a **subset** of candidates (policy-driven selection).
* `bounds_cfg?.dp_resid` sets the residual quantisation precision (default **8** if absent).

---

## 13.2 Share source (policy-aware, deterministic)

```
/*
 * MAKE_SHARES_FOR_INTEGERISATION
 * Builds Rational shares[] aligned to ranked_candidates, honouring priors if present.
 * If all shares are zero (e.g., no priors or all-zero weights), falls back to uniform shares.
 */
PROC MAKE_SHARES_FOR_INTEGERISATION(
  ranked_candidates : array<CandidateRow>,
  priors?           : array<PriorRow>        // may be null/empty
) -> array<Rational>  // length = K

REQUIRES: ranked_candidates != null AND LENGTH(ranked_candidates) >= 1

// Optional: guard that priors, if provided, belong to the same merchant
IF priors? != null AND LENGTH(priors?) > 0:
  LET m0 := ranked_candidates[0].merchant_id
  FOR EACH p IN priors?: REQUIRES: p.merchant_id == m0 ELSE RAISE ERR_S3_INT_DOMAIN

// Build lookup from priors (if present)
LET W := MAP<ISO2, Rational>()
IF priors? != null AND LENGTH(priors?) > 0:
  LET dp_ref := priors?[0].dp
  // Merchant-local dp consistency (run-wide checked separately in §12.6)
  FOR EACH p IN priors?:
    REQUIRES: p.dp == dp_ref
    LET (num, den, _) := PARSE_FIXED_DP(p.base_weight_dp)   // §7
    SET W[p.country_iso] := { num, den }

// Assemble shares aligned to candidates
LET shares := ARRAY_OF_SIZE(LENGTH(ranked_candidates))
LET all_zero := true
FOR i IN 0..LENGTH(ranked_candidates)-1:
  LET iso := ranked_candidates[i].country_iso
  IF HAS_KEY(W, iso):
    shares[i] := W[iso]
    IF shares[i].num > 0: all_zero := false
  ELSE:
    shares[i] := { num: 0, den: 1 }   // absent prior ⇒ zero weight (policy may exclude)

// Fallback to uniform if all weights are zero
IF all_zero == true:
  LET K := LENGTH(ranked_candidates)
  FOR i IN 0..K-1: shares[i] := { num: 1, den: K }   // exact uniform

RETURN shares
```

**Why this choice?**

* If priors select only some countries, zero weights for others is **policy-consistent** (floors can still force non-zero counts).
* If no priors at all (or effectively none), **uniform** is deterministic and fair, avoiding infeasibility from a zero vector.

---

## 13.3 Bounds materialisation (optional)

```
/*
 * MAKE_BOUNDS_FOR_INTEGERISATION
 * Produces per-ISO floor/ceiling maps (absent → floor=0, ceiling=+INF).
 */
PROC MAKE_BOUNDS_FOR_INTEGERISATION(
  ranked_candidates : array<CandidateRow>,
  bounds_cfg?       : BoundsCfg
) -> { floors: Map<ISO2,int>, ceilings: Map<ISO2,int>, dp_resid:int }

LET floors := EMPTY_MAP<ISO2,int>()
LET ceils  := EMPTY_MAP<ISO2,int>()
LET dp_resid := (bounds_cfg?.dp_resid != null) ? bounds_cfg.dp_resid : 8

FOR EACH c IN ranked_candidates:
  LET iso := c.country_iso
  IF bounds_cfg?.floors exists AND HAS_KEY(bounds_cfg.floors, iso):
    SET floors[iso] := bounds_cfg.floors[iso]
  ELSE:
    SET floors[iso] := 0
  IF bounds_cfg?.ceilings exists AND HAS_KEY(bounds_cfg.ceilings, iso):
    SET ceils[iso] := bounds_cfg.ceilings[iso]
  ELSE:
    SET ceils[iso] := +INF   // large sentinel in §8

RETURN { floors, ceilings: ceils, dp_resid }
```

---

## 13.4 Integerisation for a merchant (pure; uses §8 LRR)

```
/*
 * INTEGERISE_FOR_MERCHANT
 * Returns CountRow[] with deterministic counts and residual_rank.
 */
PROC INTEGERISE_FOR_MERCHANT(
  ranked_candidates : array<CandidateRow>,
  ctx               : Ctx,            // N ≥ 2
  priors?           : array<PriorRow>,
  bounds_cfg?       : BoundsCfg
) -> array<CountRow>   // {merchant_id, country_iso, count:int>=0, residual_rank:int, lineage:Lineage}

REQUIRES:
  ranked_candidates != null AND LENGTH(ranked_candidates) >= 1
  ctx != null AND IS_INT(ctx.N) AND ctx.N >= 2

LET shares := MAKE_SHARES_FOR_INTEGERISATION(ranked_candidates, priors?)
LET iso    := MAP(ranked_candidates, c -> c.country_iso)
LET bounds := MAKE_BOUNDS_FOR_INTEGERISATION(ranked_candidates, bounds_cfg?)
LET stable := [0..LENGTH(ranked_candidates)-1]       // last-resort tie index (§6.5)

// Call §8 LRR with error mapping to S3 surface
TRY:
  LET (counts, rrank) := LRR_INTEGERISE(
    shares = shares,
    iso    = iso,
    N      = ctx.N,
    bounds = bounds,
    stable = stable
  )
CATCH ERR_S3_INTEGERISATION_INFEASIBLE:
  RAISE ERR_S3_INT_INFEASIBLE

// Build CountRow[] (lineage from ctx)
LET out := EMPTY_ARRAY()
FOR i IN 0..LENGTH(ranked_candidates)-1:
  APPEND(out, {
    merchant_id   : ranked_candidates[i].merchant_id,
    country_iso   : ranked_candidates[i].country_iso,
    count         : counts[i],
    residual_rank : rrank[i],
    lineage       : ctx.lineage
  })

// Logical order for table emission: (merchant_id, country_iso)
RETURN STABLE_SORT(out, key=(merchant_id ASC, country_iso ASC))

ENSURES:
  SUM( MAP(out, r -> r.count) ) == ctx.N
  FOR_ALL(r IN out, r.count >= 0)
```

**Complexity.** `O(K log K)` (two sorts in §8 + final stable sort); linear otherwise.
**Determinism.** Identical `(ranked_candidates, ctx.N, priors_cfg content, bounds_cfg content)` → identical results, byte-for-byte.

---

## 13.5 Emission contract (hand-off to L2 emitters)

* L2 persists to **`s3_integerised_counts`** (parameter-scoped) with ordering `(merchant_id, country_iso)` and verifies **`embed == path`** for `parameter_hash`.
* `residual_rank` is required and must reflect the actual bump order (§8 tie-breaks).
* Consumers must not infer probabilities from counts or from priors; counts are **allocations** that sum to **N**.

---

## 13.6 Why this reduces friction

* **Clear source of shares.** Priors if available; else uniform—no ambiguity, no hidden re-weighting.
* **Policy-aware constraints.** Floors/ceilings and residual precision applied consistently.
* **Exact arithmetic.** §8 rational path + base-10 half-even quantisation ensure cross-language identity.
* **Schema-aligned output.** Exactly the shape `s3_integerised_counts` expects (plus lineage), ready for L2 to emit.

---

# 14) Optional: Sequencing (S3·L0 — within-country site order & optional 6-digit IDs)

**Goal.** When *sequencing* is enabled, build per-(merchant, country) **contiguous** `site_order = 1..nᵢ` and (optionally) a **zero-padded 6-digit** `site_id` derived from the order. No RNG. No I/O. Results are ready for L2 to emit into **`s3_site_sequence`** (parameter-scoped).

### Conventions

* Contracts: `REQUIRES`, `ENSURES`, `RAISE`; `//` comments.
* Pure functions only; ISO is canonical uppercase; counts come from §13 (one `CountRow` per candidate).

---

## 14.0 Errors & constants

```
ERR_S3_SEQ_DISABLED        // feature disabled but sequencing requested
ERR_S3_SEQ_DOMAIN          // invalid inputs (mismatch, negative counts)
ERR_S3_SEQ_RANGE           // count_i > 999_999 when site_id is requested
ERR_S3_SEQ_NONCONTIGUOUS   // sequence is not 1..n_i
// Constants are defined once in §9.1: SITE_ID_WIDTH=6, SITE_ID_MAX=999_999
```

---

## 14.1 Inputs (pure)

```
ranked_candidates : array<CandidateRow>  // §11
count_rows        : array<CountRow>      // §13: one per (merchant, country)
ctx               : Ctx                  // §10 (lineage carried forward)
with_site_id      : bool                 // whether to emit 6-digit site_id strings
```

**Binding facts**

* `count_rows` covers **exactly** the countries in `ranked_candidates` (one per country) and `Σ count = ctx.N` (ensured in §13).
* `site_id` is **formatting of order** only: `"000001"` ↔ `site_order = 1`, etc.

---

## 14.2 Low-level helpers (from §9; referenced here)

```
// "1" -> "000001"
FUNC FORMAT_SITE_ID_ZEROPAD6(k:int) -> string
...
PROC ASSERT_SITE_ID_RANGE_OK(count_i:int)
...
PROC BUILD_SITE_SEQUENCE_FOR_COUNTRY(merchant_id:u64, country_iso:ISO2, count_i:int, with_site_id:bool)
  -> array<SequenceRow>    // {merchant_id, country_iso, site_order, site_id?}
...
PROC ASSERT_CONTIGUOUS_SITE_ORDER(rows: array<SequenceRow>)
...
```

*Reused verbatim; no duplication.*

---

## 14.3 Alignment & guards

```
PROC ASSERT_COUNTS_ALIGN_TO_CANDIDATES(
  ranked_candidates: array<CandidateRow>,
  count_rows: array<CountRow>
)
REQUIRES:
  ranked_candidates != null AND count_rows != null
  LENGTH(ranked_candidates) == LENGTH(count_rows)
  // same country set (order-independent)
  SET( MAP(ranked_candidates, c->c.country_iso) ) ==
  SET( MAP(count_rows,        r->r.country_iso) )
  // counts are non-negative
  FOR_ALL(count_rows, r -> r.count >= 0)
ENSURES: true
```

---

## 14.4 Sequence for a single merchant (pure)

```
/*
 * SEQUENCE_FOR_MERCHANT
 * Builds SequenceRow[] for all countries of a merchant deterministically.
 */
PROC SEQUENCE_FOR_MERCHANT(
  ranked_candidates : array<CandidateRow>,
  count_rows        : array<CountRow>,
  ctx               : Ctx,
  with_site_id      : bool
) -> array<SequenceRow>   // {merchant_id, country_iso, site_order, site_id?}

REQUIRES:
  ranked_candidates != null AND count_rows != null
  CALL ASSERT_COUNTS_ALIGN_TO_CANDIDATES(ranked_candidates, count_rows)
  // Σ count == ctx.N and per-row lineage were ensured upstream (§13, §10)

LET COUNT := MAP<ISO2,int>()         // ISO -> count
FOR EACH r IN count_rows:
  SET COUNT[r.country_iso] := r.count

LET out := EMPTY_ARRAY()

FOR EACH c IN ranked_candidates:
  LET iso := c.country_iso
  LET n   := COUNT[iso]              // exists by alignment
  IF with_site_id: CALL ASSERT_SITE_ID_RANGE_OK(n)
  LET chunk := BUILD_SITE_SEQUENCE_FOR_COUNTRY(ctx.merchant_id, iso, n, with_site_id)
  // defensive (construction already guarantees contiguity)
  CALL ASSERT_CONTIGUOUS_SITE_ORDER(chunk)
  APPEND_ALL(out, chunk)

// Table logical order: (merchant_id, country_iso, site_order)
RETURN STABLE_SORT(out, key=(merchant_id ASC, country_iso ASC, site_order ASC))

ENSURES:
  FOR_ALL(r IN out, r.merchant_id == ctx.merchant_id)
  // If n_i == 0 for some country, it contributes no rows (legal)
  IF with_site_id:
    FOR_ALL(r IN out, r.site_id == FORMAT_SITE_ID_ZEROPAD6(r.site_order))
```

**Complexity.** Let `S = Σ nᵢ` (total emitted rows). Build is **O(S)**; final stable sort is **O(S log S)**.
**Determinism.** Pure; byte-identical given the same `(ranked_candidates, count_rows, with_site_id)`.

---

## 14.5 Emission contract (hand-off to L2)

* L2 adds lineage from `ctx` and persists to **`s3_site_sequence`** (parameter-scoped) with logical ordering `(merchant_id, country_iso, site_order)` and verifies **`embed == path`** for `parameter_hash`.
* `site_id` is optional; when enabled, it **must** equal zero-padded `site_order` (width 6).
* Consumers **must not** infer cross-country order from this table; inter-country order is **only** `candidate_rank` in `s3_candidate_set`.

---

## 14.6 Why this reduces friction

* **Zero ambiguity.** One function, one outcome; no hidden counters or RNG.
* **Schema-aligned.** Outputs match `s3_site_sequence` exactly (lineage embedded at emit time).
* **Safety rails.** Explicit range checks prevent overflow beyond 6 digits; contiguity is enforced and validated.

---

# 15) Deterministic Write Surface (parameter-scoped emitters)

**Goal.** Persist S3’s RNG-free tables in a **byte-stable** way. Emitters here are thin, deterministic shims over the dictionary writer: they enforce **parameter-scoped partitions** (no `seed`), **embed = path** lineage equality, **logical row order**, and **atomic publish**. No path literals; no volatile fields (no wall-clock stamps).

### Conventions

* Contracts: `REQUIRES`, `ENSURES`, `RAISE`; `//` comments.
* Schema anchors & dataset IDs:
  `s3_candidate_set → #/s3/candidate_set`, `s3_base_weight_priors → #/s3/base_weight_priors`,
  `s3_integerised_counts → #/s3/integerised_counts`, `s3_site_sequence → #/s3/site_sequence`.
* Logical orders:
  • candidate_set: `(merchant_id ASC, candidate_rank ASC, country_iso ASC)`
  • base_weight_priors: `(merchant_id ASC, country_iso ASC)`
  • integerised_counts: `(merchant_id ASC, country_iso ASC)`
  • site_sequence: `(merchant_id ASC, country_iso ASC, site_order ASC)`

---

## 15.0 Error vocabulary

```
ERR_S3_EMIT_DOMAIN         // missing lineage, bad partition key, wrong schema anchor, null rows
ERR_S3_EMIT_VOLATILE       // volatile fields detected (timestamps, etc.)
ERR_S3_EMIT_ORDERING       // logical order cannot be achieved/validated
ERR_S3_EMIT_CONFLICT       // path exists and skip-if-final says do not overwrite
ERR_S3_EMIT_IO             // writer/rename failure
```

---

## 15.1 Common helpers (deterministic; no RNG)

```
// Resolve dataset metadata from dictionary (no path literals)
FUNC RESOLVE_S3_DATASET(dataset_id: string)
  -> { base_path: string, schema_ref: string, partitions: array<string>, logical_order: Key }
  REQUIRES: dataset_id ∈ {"s3_candidate_set","s3_base_weight_priors","s3_integerised_counts","s3_site_sequence"}
  RETURN DICT.METADATA(dataset_id)   // host-specific; carries schema_ref and expected logical order

// Process-local monotonic counter for tmp-path disambiguation (no I/O, no wall clock).
// Starts at 0 and increments by 1 on each call within the process.
FUNC MONOTONIC_COUNTER() -> int
  STATE: static CTR := 0
  LET out := CTR
  CTR := CTR + 1
  RETURN out

// Build final and temp paths for parameter-scoped partition (temp suffix is deterministic)
FUNC BUILD_PARTITION_PATHS(base_path: string, parameter_hash: Hex64, manifest_fp: Hex64)
  -> { final: string, tmp: string }
  REQUIRES: parameter_hash matches ^[a-f0-9]{64}$ AND manifest_fp matches ^[a-f0-9]{64}$
  LET final := FINAL_PARTITION_PATH(base_path, parameter_hash)
  LET ctr   := MONOTONIC_COUNTER()   // process-local, starts at 0; deterministic within process
  // tmp lives as a **sibling** of 'final', never inside it
  LET tmp   := CONCAT(base_path, "/_tmp_", parameter_hash[0:8], "_", manifest_fp[0:8], "_", DECIMAL_STRING(ctr), "/")
  RETURN { final, tmp }

// Enforce embed=path lineage equality on all rows for the partition
PROC ASSERT_EMBED_EQUALS_PATH(rows: array<Record>, parameter_hash: Hex64)
  REQUIRES: rows != null
  FOR EACH r IN rows:
    IF r.parameter_hash != parameter_hash: RAISE ERR_S3_EMIT_DOMAIN
  ENSURES: true

// Enforce embed manifest fingerprint equality
PROC ASSERT_OPTIONAL_ROW_PROVENANCE_EQUALS(rows: array<Record>, manifest_fp: Hex64)
  REQUIRES: rows != null
  FOR EACH r IN rows:
    IF HAS_KEY(r,"produced_by_fingerprint") AND r.produced_by_fingerprint != manifest_fp:
      RAISE ERR_S3_EMIT_DOMAIN
  ENSURES: true

// Apply dataset’s logical order deterministically
FUNC SORT_TO_LOGICAL_ORDER(dataset_id: string, rows: array<Record>) -> array<Record>
  LET key :=
    IF dataset_id == "s3_candidate_set":           (r -> (r.merchant_id, r.candidate_rank, r.country_iso))
    ELSE IF dataset_id == "s3_base_weight_priors": (r -> (r.merchant_id, r.country_iso))
    ELSE IF dataset_id == "s3_integerised_counts": (r -> (r.merchant_id, r.country_iso))
    ELSE                                           (r -> (r.merchant_id, r.country_iso, r.site_order)) // site_sequence
  RETURN STABLE_SORT(rows, key)
```

```
FUNC FINAL_PARTITION_PATH(base_path: string, parameter_hash: Hex64) -> string
  REQUIRES: parameter_hash matches ^[a-f0-9]{64}$
  RETURN CONCAT(base_path, "/parameter_hash=", parameter_hash, "/")

// Optional probe used by L2 to implement idempotence; exposed here for completeness
FUNC SHOULD_SKIP_FINAL(dataset_id: string, parameter_hash: Hex64) -> bool
  LET meta  := RESOLVE_S3_DATASET(dataset_id)
  LET final := FINAL_PARTITION_PATH(meta.base_path, parameter_hash)
  RETURN FS.EXISTS(final)
```

```
// Write rows to tmp, validate schema_ref, fsync, then atomic rename to final
PROC WRITE_ATOMIC(dataset_id: string, schema_ref: string, tmp: string, final: string, rows: array<Record>)
  REQUIRES: rows != null AND LENGTH(rows) >= 0
  LET writer := OPEN_WRITER(tmp, schema_ref, options={compression:"zstd", row_group_target:"256K"})
  FOR EACH r IN rows: WRITER.APPEND(r)
  WRITER.CLOSE_AND_FSYNC()
  IF FS.EXISTS(final): FS.REMOVE_DIR(final)  // only reached when overwrite was allowed by caller
  FS.ATOMIC_RENAME(tmp, final)
  ENSURES: FS.EXISTS(final) AND NOT FS.EXISTS(tmp)
```

---

## 15.2 Generic emitter (used by all four S3 datasets)

```
/*
 * EMIT_S3_DATASET
 * Deterministic emission for one parameter-scoped partition.
 */
PROC EMIT_S3_DATASET(
  dataset_id     : string,           // one of the four S3 datasets
  parameter_hash : Hex64,
  rows           : array<Record>,    // already shaped to the dataset schema
  manifest_fp    : Hex64,            // embedded in rows already
  skip_if_final  : bool              // L2-controlled idempotence flag
)
REQUIRES:
  dataset_id != "" AND parameter_hash != null AND manifest_fp != null AND rows != null

LET meta := RESOLVE_S3_DATASET(dataset_id)

// S3 partitions must be parameter-scoped only
REQUIRES: meta.partitions == ["parameter_hash"] ELSE RAISE ERR_S3_EMIT_DOMAIN

LET paths := BUILD_PARTITION_PATHS(meta.base_path, parameter_hash, manifest_fp)

// empty-slice ⇒ no-op (do not write 0-row files)
IF rows == NULL OR LENGTH(rows) == 0:
  RETURN

// idempotence gate ⇒ no-op skip when final exists
IF skip_if_final AND FS.EXISTS(paths.final):
  RETURN  // deterministic skip: final already exists (idempotent no-op)

CALL ASSERT_EMBED_EQUALS_PATH(rows, parameter_hash)
CALL ASSERT_OPTIONAL_ROW_PROVENANCE_EQUALS(rows, manifest_fp)
CALL ASSERT_NO_VOLATILE_FIELDS(rows)

LET sorted := SORT_TO_LOGICAL_ORDER(dataset_id, rows)

// Optional post-check (defensive): verify nondecreasing logical key
IF NOT IS_NONDECREASING( MAP(sorted, r ->
  IF dataset_id == "s3_candidate_set":           (r.merchant_id, r.candidate_rank, r.country_iso)
  ELSE IF dataset_id == "s3_base_weight_priors": (r.merchant_id, r.country_iso)
  ELSE IF dataset_id == "s3_integerised_counts": (r.merchant_id, r.country_iso)
  ELSE                                           (r.merchant_id, r.country_iso, r.site_order)) ):
  RAISE ERR_S3_EMIT_ORDERING

WRITE_ATOMIC(dataset_id, meta.schema_ref, paths.tmp, paths.final, sorted)

ENSURES: FS.EXISTS(paths.final)
```

---

## 15.3 Dataset-specific facades (clarity for L2 call-sites)

```
// Candidate set — single source of inter-country order
PROC EMIT_S3_CANDIDATE_SET(rows: array<Record>, parameter_hash: Hex64, manifest_fp: Hex64, skip_if_final: bool)
  REQUIRES:
    FOR_ALL(rows, r -> HAS_KEYS(r, ["merchant_id","country_iso","candidate_rank","is_home","reason_codes","filter_tags","parameter_hash"]))
    // optional row provenance: produced_by_fingerprint may be present
  CALL EMIT_S3_DATASET("s3_candidate_set", parameter_hash, rows, manifest_fp, skip_if_final)

// Base-weight priors (optional)
PROC EMIT_S3_BASE_WEIGHT_PRIORS(rows: array<Record>, parameter_hash: Hex64, manifest_fp: Hex64, skip_if_final: bool)
  REQUIRES:
    FOR_ALL(rows, r -> HAS_KEYS(r, ["merchant_id","country_iso","base_weight_dp","dp","parameter_hash","manifest_fingerprint"]))
  CALL EMIT_S3_DATASET("s3_base_weight_priors", parameter_hash, rows, manifest_fp, skip_if_final)

// Integerised counts (optional)
PROC EMIT_S3_INTEGERISED_COUNTS(rows: array<Record>, parameter_hash: Hex64, manifest_fp: Hex64, skip_if_final: bool)
  REQUIRES:
    FOR_ALL(rows, r -> HAS_KEYS(r, ["merchant_id","country_iso","count","residual_rank","parameter_hash","manifest_fingerprint"]))
  CALL EMIT_S3_DATASET("s3_integerised_counts", parameter_hash, rows, manifest_fp, skip_if_final)

// Site sequence (optional)
PROC EMIT_S3_SITE_SEQUENCE(rows: array<Record>, parameter_hash: Hex64, manifest_fp: Hex64, skip_if_final: bool)
  REQUIRES:
    FOR_ALL(rows, r -> HAS_KEYS(r, ["merchant_id","country_iso","site_order","parameter_hash","manifest_fingerprint"]))
    // site_id is optional per schema; when present, must match ^[0-9]{6}$
    FOR_ALL(rows, r -> NOT HAS_KEY(r,"site_id") OR MATCHES_REGEX(r.site_id, "^[0-9]{6}$"))
  CALL EMIT_S3_DATASET("s3_site_sequence", parameter_hash, rows, manifest_fp, skip_if_final)
```

---

## 15.4 Determinism & efficiency guarantees

* **Deterministic.** Identical `(dataset_id, parameter_hash, manifest_fp, rows)` → identical bytes (stable sort; no volatile fields; atomic publish).
* **Parameter-scoped.** Only `parameter_hash` appears in paths; `seed` is *never* part of S3 partitions.
* **No drift.** `embed == path` and embedded `manifest_fingerprint` are enforced; schema anchors are checked by the writer; dictionary resolution prevents hard-coded paths.
* **Throughput-aware.** Streaming writer, compressed row groups; one pass over rows; O(n log n) at most for ordering (linear if pre-sorted).

---

## 15.5 How L2 uses this (one-liner per table)

* L2 computes rows (from L1), **sets lineage fields**, and calls the matching `EMIT_S3_*` with `skip_if_final = true` for idempotence.
* If a final exists and `skip_if_final=true`, the emitter returns success without writing (deterministic skip).
* 
---

# 16) Assertions & Guards (unit-sized, reusable)

**Goal.** Tiny, **pure** predicates you can drop anywhere (L1/L2/L3) to fail fast on domain, ordering, lineage, and shape errors. They do **no I/O**, **no RNG**, and never guess policy; they just assert what S3 guarantees.

### Conventions

* `REQUIRES`, `ENSURES`, `RAISE`; `//` comments.
* All functions are **pure**; inputs are immutable values.
* Use alongside the earlier helpers (ISO §5, vocab §4, fixed-dp §7, LRR §8, sequencing §9, emitters §15).

---

## 16.0 Error vocabulary (used here)

```
ERR_S3_ASSERT_DOMAIN         // generic domain/shape violation
ERR_S3_CTX_LINEAGE_MISMATCH  // lineage fields disagree
ERR_S3_RANK_DOMAIN           // candidate ranking domain violation (duplicates, home missing, etc.)
ERR_S3_SEQ_NONCONTIGUOUS     // sequencing 1..n contiguous invariant broken
ERR_S3_PRIOR_DP_INCONSISTENT // dp differs within same run or merchant slice
ERR_S3_FIXED_DP_FORMAT       // fixed-dp string invalid (see §7)
ERR_S3_EMIT_DOMAIN           // embed≠path, missing lineage, wrong columns before emit
```

---

## 16.1 Small array/ordering predicates

```
// True iff a[0..n-1] is strictly increasing integers
FUNC IS_STRICTLY_INCREASING_INT(a: array<int>) -> bool
  IF LENGTH(a) <= 1: RETURN true
  FOR i FROM 1 TO LENGTH(a)-1:
    IF a[i] <= a[i-1]: RETURN false
  RETURN true
```

```
// Contiguous check for ranks: {0,1,2,...,K-1}
PROC ASSERT_RANKS_CONTIGUOUS_ZERO_BASE(ranks: array<int>)
  REQUIRES: ranks != null AND LENGTH(ranks) >= 1
  LET K := LENGTH(ranks)
  LET S := SET(ranks)
  IF SIZE(S) != K: RAISE ERR_S3_RANK_DOMAIN
  IF MIN(S) != 0 OR MAX(S) != K-1: RAISE ERR_S3_RANK_DOMAIN
  ENSURES: true
```

```
// Contiguous check for 1..n (sequencing)
PROC ASSERT_CONTIGUOUS_ONE_TO_N(n: int, seq: array<int>)
  REQUIRES: n >= 0
  IF n == 0:
    REQUIRES: LENGTH(seq) == 0
    RETURN
  REQUIRES: LENGTH(seq) == n
  FOR i FROM 1 TO n:
    IF seq[i-1] != i: RAISE ERR_S3_SEQ_NONCONTIGUOUS
  ENSURES: true
```

---

## 16.2 Lineage & partition equality (embed = path)

```
// r.parameter_hash must equal the partition key; fingerprint consistent across rows
PROC ASSERT_EMBED_EQUALS_PARTITION(rows: array<Record>, parameter_hash: Hex64, manifest_fp: Hex64)
  REQUIRES: rows != null
  FOR EACH r IN rows:
    IF r.parameter_hash != parameter_hash:           RAISE ERR_S3_EMIT_DOMAIN
    IF r.manifest_fingerprint != manifest_fp:        RAISE ERR_S3_CTX_LINEAGE_MISMATCH
  ENSURES: true
```

---

## 16.3 Candidate-set guards (single source of inter-country order)

```
// Exactly one home; home has candidate_rank==0; no duplicate countries; candidate_rank contiguous (0..K-1)
PROC ASSERT_CANDIDATE_SET_SHAPE(rows: array<Record>)
  REQUIRES: rows != null AND LENGTH(rows) >= 1
  LET home_cnt := 0
  LET home_rank0 := 0
  LET seen_iso := EMPTY_SET()
  LET ranks := EMPTY_ARRAY()
  
  FOR EACH r IN rows:
    IF r.is_home == true:
      home_cnt := home_cnt + 1
      IF r.candidate_rank == 0: home_rank0 := home_rank0 + 1
    IF CONTAINS(seen_iso, r.country_iso): RAISE ERR_S3_RANK_DOMAIN
    INSERT(seen_iso, r.country_iso)
    APPEND(ranks, r.candidate_rank)
  
  IF home_cnt != 1:        RAISE ERR_S3_RANK_DOMAIN
  IF home_rank0 != 1:      RAISE ERR_S3_RANK_DOMAIN   // home must be rank 0
  CALL ASSERT_RANKS_CONTIGUOUS_ZERO_BASE(ranks)
  ENSURES: true
```

---

## 16.4 Priors guards (fixed-dp + run-/slice-wide dp consistency)

```
// All rows must share the same dp within the slice; strings must be valid fixed-dp
PROC ASSERT_PRIORS_BLOCK_SHAPE(rows: array<Record>)
  REQUIRES: rows != null
  IF LENGTH(rows) == 0: RETURN
  LET d0 := rows[0].dp
  FOR EACH r IN rows:
    IF r.dp != d0: RAISE ERR_S3_PRIOR_DP_INCONSISTENT
    // structural validation of the decimal string
    LET _ := PARSE_FIXED_DP(r.base_weight_dp)  // §7; raises on format error
  ENSURES: true
```

---

## 16.5 Integerised-counts guards (sum = N, residual_rank is permutation)

```
// Counts ≥0, sum equals N; residual_rank is 1..M permutation
PROC ASSERT_COUNTS_SUM_AND_RESIDUAL_RANK(rows: array<Record>, N: int)
  REQUIRES: rows != null AND N >= 0
  LET sum := 0
  LET ranks := EMPTY_ARRAY()
  FOR EACH r IN rows:
    IF r.count < 0: RAISE ERR_S3_ASSERT_DOMAIN
    sum := sum + r.count
    APPEND(ranks, r.residual_rank)
  
  IF sum != N: RAISE ERR_S3_ASSERT_DOMAIN
  
  LET M := LENGTH(rows)
  LET S := SET(ranks)
  IF SIZE(S) != M OR MIN(S) != 1 OR MAX(S) != M: RAISE ERR_S3_ASSERT_DOMAIN
  ENSURES: true
```

*(Full recomputation of residual ordering from residuals is done in L3; this guard ensures the basic permutation invariant.)*

---

## 16.6 Sequencing guards (table-wide)

```
// Group by country and assert each group is 1..n contiguous; site_id, if present, matches order
PROC ASSERT_SEQUENCE_TABLE_SHAPE(rows: array<Record>)
  REQUIRES: rows != null
  LET G := GROUP_BY(rows, key=(r -> r.country_iso))
  FOR EACH (iso, grp) IN G:
    LET n := LENGTH(grp)
    LET seq := MAP( SORT_ASC(grp, key=(r -> r.site_order)), r -> r.site_order )
    CALL ASSERT_CONTIGUOUS_ONE_TO_N(n, seq)
    // if site_id present, it must be zero-padded order
    FOR EACH r IN grp:
      IF HAS_KEY(r, "site_id") AND r.site_id != FORMAT_SITE_ID_ZEROPAD6(r.site_order):
        RAISE ERR_S3_SEQ_NONCONTIGUOUS
  ENSURES: true
```

---

## 16.7 Volatile-field guard (S3 tables must be stable)

```
// Ensure S3 rows do not carry volatile timestamps or RNG envelopes
PROC ASSERT_NO_VOLATILE_FIELDS(rows: array<Record>)
  REQUIRES: rows != null
  FOR EACH r IN rows:
    IF HAS_ANY(r, ["created_at","updated_at","emitted_at","now_ts",
                   "before_counter","after_counter","blocks","draws"]):
      RAISE ERR_S3_EMIT_DOMAIN
  ENSURES: true
```

---

## 16.8 ISO & vocab recap guards (thin wrappers over §§4–5)

```
// Wrap §5 + §4 so call-sites remain short
PROC ASSERT_ISO_MEMBER_CANONICAL(iso: string, iso_set: Set<ISO2>)
  LET _ := NORMALISE_AND_VALIDATE_ISO2(iso, iso_set)  // raises on failure
  ENSURES: true
  
  PROC ASSERT_CHANNEL_VOCAB(ch: string, channel_vocab: Set<string>)
  CALL ASSERT_CHANNEL_IN_INGRESS_VOCAB(ch, channel_vocab)  // raises on failure
  ENSURES: true
```

---

## 16.9 Why these help (friction removal)

* **Fail-fast, localised.** Tiny asserts you can call just before emit or join—no I/O, no side effects.
* **Schema-aligned.** Check exactly what S3 tables guarantee (home rank 0, contiguous ranks, permutations, embed=path, fixed-dp).
* **Composable.** Use in L1 (building blocks), L2 (pre-emit sanity), and L3 (validators) without duplication.

---

# 17) Determinism & Efficiency Notes (applies to all helpers)

**Goal.** Make every S3·L0 routine yield **byte-identical** outcomes across languages and runs, while staying **O(k log k)** (or better) per merchant and avoiding hidden bottlenecks. These rules bind all sections above (ranking, priors, LRR integerisation, sequencing, emitters).

---

## 17.1 Determinism contract (no surprises)

* **RNG-free.** S3 performs **no** pseudorandom draws; outputs are pure functions of inputs (`Ctx`, ladder/ISO artefacts, feature flags).
* **No wall-clock / environment.** Helpers never read time, tz, locale, env-vars, or host globals.
* **Canonical encodings.** ISO2 is exactly two ASCII **uppercase** letters; closed-vocab arrays are **A→Z** and **deduped**; priors are **fixed-dp decimal strings** (with explicit `dp`).
* **Ordering is explicit.** Every sort uses a **documented, total key** (e.g., `(precedence, priority, rule_id, ISO, stable_idx)`); all sorts are **stable**.
* **Idempotence-ready.** Same inputs ⇒ same rows; emitters enforce **`embed == path`** (`parameter_hash`) and atomic rename; all rows embed `{parameter_hash, manifest_fingerprint}`.

---

## 17.2 Numeric discipline (portable & exact where needed)

* **Binary64 policy.** When floats appear (e.g., policy algebra in priors), assume IEEE-754 binary64, **RNE** (round-to-nearest-even), **no FMA**, fixed reduction order (Neumaier).
* **Exact decimal results.** For fixed-dp strings and residual quantisation, use **integer/rational base-10** arithmetic with **half-even** rounding (see §7).
* **Residual bins.** `dp_resid` (default **8**) quantises remainders **before** tie-breaking to ensure cross-language identity.

---

## 17.3 Ordering discipline (single sources of truth)

* **Inter-country order:** lives **only** in `candidate_rank`; file order is non-authoritative.
* **Tie-break tuples:** always complete and total (append `stable_idx` last) to avoid host-dependent comparisons.
* **Within-country order:** `site_order = 1..nᵢ` contiguous; optional `site_id` is **zero-padded order** (`width=6`).

---

## 17.4 Purity, memo, and concurrency

* **Pure helpers.** All L0 helpers are side-effect free; dictionary I/O and emitters are isolated (§15).
* **BOM memo.** First successful open is cached per process (meta `{id,semver,digest}` retained); subsequent reads are lock-free.
* **Parallelism.** Per-merchant work is **embarrassingly parallel**; no shared mutable state beyond the BOM memo.

---

## 17.5 Complexity targets (per merchant)

* **Ranking:** **O(k log k)** where *k* = number of candidate countries.
* **Integerisation:** **O(k log k)** (two sorts) + linear arithmetic; memory **O(k)**.
* **Sequencing:** **O(∑ nᵢ)** to build rows; final country sort **O(k log k)**.
* **Emit:** one stable sort to logical order + streaming write; never quadratic passes.

---

## 17.6 Memory & I/O posture

* **No universe materialisation.** Operate on the current merchant slice only.
* **Streaming writes.** Chunked/row-grouped emission; avoid building large in-memory tables.
* **No path literals.** All paths resolved via the dictionary; emitters validate schema anchors and partitions.

---

## 17.7 Cross-language portability

* **ASCII-only transforms.** ISO uppercase and string compares are **ASCII** (no locale surprises).
* **Fixed formats.** Regexes and decimal renderers are language-neutral (no thousands separators, no exponents for fixed-dp).
* **Big-int / big-den.** Use arbitrary-precision integers for `10^dp`, rational numerators/denominators, and integer div/mod; do not rely on host 32-bit ranges.

---

## 17.8 Idempotence & immutability

* **Parameter-scoped partitions.** S3 tables partition **only** on `parameter_hash` (never on `seed`).
* **Skip-if-final.** L2 decides whether to skip an existing partition; emitters can detect and raise a conflict to prevent overwrites.
* **Atomic publish.** Temp → fsync → rename; never expose partial partitions; no volatile timestamps in S3 rows.

---

## 17.9 Error handling (fail-fast, no “best-effort”)

* **Domain errors:** unknown ISO/vocab, duplicate countries, missing home, malformed fixed-dp, infeasible floors/ceilings ⇒ **RAISE** and remain non-emitting for that merchant.
* **No auto-repair.** Helpers never coerce inputs beyond documented canonicalisation.

---

## 17.10 Verification hooks (keep friction low)

* Provide tiny asserts for: contiguous ranks (0..K-1), contiguous `site_order` (1..nᵢ), `sum(counts)=N`, fixed-dp validity, **`embed == path`** lineage equality, absence of volatile fields (see §16).
* Golden-file tests recommended: same inputs across two hosts ⇒ identical bytes in emitted Parquet/CSV after normalisation.

---

## 17.11 Stable knobs & limits

* **`dp` (priors) and `dp_resid` (residuals)** are policy-controlled; changing either implies a new parameter set/fingerprint.
* **`SITE_ID_WIDTH = 6` / `SITE_ID_MAX = 999999`** are fixed; exceeding them requires a schema change, not a runtime workaround.
* **Ceilings/floors** are hard constraints; infeasible configurations must be corrected in policy, not “softened” in code.

**Bottom line:** follow these rules and every S3 helper remains **replayable, portable, and fast**—with no host-specific behaviour or performance traps.

---

# 18) Minimal Host-Adapter Interfaces (deferred to L2)

**Goal.** Specify the **smallest host-facing API** L2 must provide to keep S3·L0 pure/deterministic and avoid path literals or runtime drift. These adapters are *not* business logic; they are glue for dictionary resolution, artefact I/O, atomic publish, and parallel orchestration.

### Conventions

* Contracts: `REQUIRES`, `ENSURES`, `RAISE`; `//` comments.
* All IDs (datasets, artefacts) are **dictionary/registry** keys—never hardcoded paths.
* S3 egress is **parameter-scoped** (no `seed`); **embed = path** equality is enforced before write.

---

## 18.0 Error vocabulary (host layer)

```
ERR_HOST_DICT_UNAVAILABLE    // dictionary/registry not reachable
ERR_HOST_DICT_MISSING_ID     // dataset/artefact id cannot be resolved
ERR_HOST_IO                  // read/write/rename failures
ERR_HOST_SCHEMA_MISMATCH     // writer/reader schema mismatch
ERR_HOST_CONFLICT            // final partition exists and overwrite not allowed
```

---

## 18.1 Dictionary / Registry

```
// True iff the dictionary is reachable (network/path/auth already configured)
FUNC DICT.IS_AVAILABLE() -> bool

// Resolve a dataset id -> metadata
// Returns base path, schema_ref, partition keys, and any logical ordering hints
FUNC DICT.METADATA(dataset_id:string)
  -> { base_path:string, schema_ref:string, partitions:array<string>, logical_order:Key }

// Resolve an artefact id -> metadata for BOM loads (path, semver, digest)
FUNC DICT.RESOLVE(artefact_id:string)
  -> { path:string, semver:string, digest:Hex64 }
```

---

## 18.2 Readers (L2 responsibilities)

```
// Singleton fetch by merchant (and lineage) from a dictionary-identified table.
// Used for ingress, S1 hurdle, S2 nb_final. Host enforces partition filters.
FUNC READ_SINGLETON_BY_MERCHANT(
  dataset_id : string,
  merchant_id: u64,
  filters    : Map            // e.g., {parameter_hash, manifest_fingerprint, seed?}
) -> array<Record>            // returns 0..1 rows; L0 asserts singleton
```

```
// Artefact readers used by BOM loaders (§3)
FUNC READ_YAML(path:string) -> Any           // strict YAML parser, UTF-8
FUNC READ_TABLE(path:string) -> array<Record>// tabular reader (e.g., Parquet/CSV), schema-checked if available
```

*Notes.*
Host guarantees schema-compatible rows (`schema_ref` from DICT). L2 chooses exact partition filters (seed present for upstream RNG tables; **not present for S3**).

---

## 18.3 Writers (schema-checked, streaming)

```
// Open a streaming writer bound to a path and schema_ref.
// The host should validate schema_ref against the target table's JSON-Schema.
FUNC OPEN_WRITER(tmp_path:string, schema_ref:string, options:Map) -> Writer

// Append one row; host enforces per-row schema validation (or batched).
PROC Writer.APPEND(row:Record)

// Close and fsync underlying file(s); raise ERR_HOST_IO on failure.
PROC Writer.CLOSE_AND_FSYNC()
```

**Options (suggested)**: `compression:"zstd"`, `row_group_target_bytes:int`, `validate_schema:true|false`.

---

## 18.4 Filesystem primitives (atomic publish & idempotence)

```
// True iff final partition directory exists
FUNC FS.EXISTS(path:string) -> bool

// Remove a directory tree if present (fail fast on error)
PROC FS.REMOVE_DIR(path:string)

// Atomic publish: rename tmp dir to final dir (same filesystem/volume)
PROC FS.ATOMIC_RENAME(tmp:string, final:string)
  REQUIRES: NOT FS.EXISTS(final)
  ENSURES:  FS.EXISTS(final) AND NOT FS.EXISTS(tmp)
```

---

## 18.5 Concurrency & work scheduling (host-managed)

```
// Apply f to each merchant_id with bounded parallelism.
// Fail-fast mode: stop-on-first-error or keep-going based on policy.
PROC PARALLEL_FOR_EACH(
  merchant_ids   : array<u64>,
  max_concurrency: int,
  f              : (u64) -> void,
  stop_on_error  : bool
)

// Persistent work queue variant for very large universes (optional)
PROC ENQUEUE_MERCHANTS(ids: array<u64>)
PROC RUN_WORKERS(max_concurrency:int, f:(u64)->void, stop_on_error:bool)
```

---

## 18.6 Skip-if-final (idempotence probe for S3 partitions)

```
// Return true if the target S3 partition already exists (parameter-scoped).
FUNC SHOULD_SKIP_FINAL(dataset_id:string, parameter_hash:Hex64) -> bool
// Typical impl: DICT.METADATA → base_path, build "…/parameter_hash={parameter_hash}/", FS.EXISTS(...)
```

---

## 18.7 Logging & metrics (minimal hooks)

```
// Structured event logging (no timestamps injected by L0; host may stamp)
PROC LOG_INFO(event:string, fields:Map)
PROC LOG_WARN(event:string, fields:Map)
PROC LOG_ERROR(event:string, fields:Map)

// Lightweight counters (optional)
PROC METRIC_COUNT(name:string, delta:int)
PROC METRIC_GAUGE(name:string, value:float)
```

---

## 18.8 Validation shims (optional but helpful)

```
// Validate a batch of rows against a schema_ref without writing (dry-run)
FUNC VALIDATE_ROWS(schema_ref:string, rows:array<Record>) -> bool

// Quick partition verifier (path key equality with embedded lineage)
PROC VERIFY_PARTITION_KEYS(rows:array<Record>, key:string, value:string)
```

---

## 18.9 Host configuration (non-functional knobs)

```
// Acquire run-scoped configuration used by L2 orchestration
FUNC HOST_CONFIG() ->
  { max_concurrency:int, row_group_target_bytes:int, overwrite_final:bool, stop_on_error:bool }
```

---

## 18.10 End-to-end emitter facade (what L2 actually calls)

```
// One-liner tying DICT.METADATA + tmp/final path build + OPEN_WRITER + ATOMIC_RENAME.
// L0’s §15 logic calls into this; L2 chooses overwrite/skip behavior.
PROC EMIT_PARTITION(
  dataset_id     : string,
  parameter_hash : Hex64,
  schema_ref     : string,     // from DICT.METADATA(dataset_id)
  rows           : array<Record>,
  overwrite_final: bool
)
```

---

## 18.11 Why this is the *minimum* that reduces friction

* **Zero path literals:** everything flows through the dictionary; partitions are built from keys.
* **Schema-checked I/O:** writers/validators pin to `schema_ref`, preventing drift.
* **Deterministic publish:** atomic rename and idempotence probe avoid partial/duplicate partitions.
* **Scalable orchestration:** bounded parallelism or a queue—host’s choice—without changing S3 logic.
* **Small surface area:** a handful of primitives cover all of S3’s needs; L0/L1 stay pure; L2 is straightforward to implement.

---

# 19) Acceptance Checklist (what “done” means)

Use this as a **go/no-go** list. Every box must pass for S3·L0 to be declared *done* and ready for orchestration (L2) and validation (L3).

---

## A. Scope & determinism

* [ ] **RNG-free:** No S3·L0 function calls RNG or emits RNG envelopes (`before/after/blocks/draws`).
* [ ] **No wall-clock/locale/env:** No timestamps or locale-dependent ops; all string ops are **ASCII**.
* [ ] **Pure helpers:** L0 helpers are side-effect-free (I/O only in §15 emitters).
* [ ] **Parameter-scoped only:** All S3 emit paths are keyed by **`parameter_hash`** (no `seed`).

## B. Schema & dictionary alignment

* [ ] **Emit targets exist & match:** Emitters point to anchors
  `#/s3/candidate_set`, `#/s3/base_weight_priors`, `#/s3/integerised_counts`, `#/s3/site_sequence`.
* [ ] **Dictionary-resolved paths:** No path literals; `schema_ref` is validated by the writer.
* [ ] **Lineage fields embedded:** Rows carry `parameter_hash`; `produced_by_fingerprint` is **optional**. The **sidecar** carries `manifest_fingerprint`.

## C. BOM loaders (read-only authorities)

* [ ] `OPEN_BOM_S3` loads **rule ladder** and **ISO** (required), and **priors/thresholds** when enabled; **all-or-nothing** memo.
* [ ] **Ladder is total** (unique `rule_id`; ordered by `(precedence,priority,rule_id)`); exposes **closed** `reason_codes`/`filter_tags` (A→Z, deduped).
* [ ] ISO universe is non-empty and strictly **uppercase ISO-3166 alpha-2**.

## D. Closed vocab & ISO helpers

* [ ] Helpers **reject** unknown `reason_codes`/`filter_tags`; outputs are **A→Z**, deduped.
* [ ] Channel checks **inherit ingress vocabulary** (use the ingress channel set; do not hard-code literals).
* [ ] ISO helpers normalise to **ASCII uppercase** and validate **membership** in the BOM ISO set.

## E. Ordering primitives (single source of order)

* [ ] Admission-order key = **(precedence, priority, rule_id, ISO, stable_idx)** is implemented and documented (stable sort).
* [ ] Ranking assigns **`candidate_rank`** with **home=0** and **contiguous** `0..K−1`; duplicate countries **fail**.

## F. Priors (optional; scores, not probabilities)

* [ ] **`dp`** is selected once per run from policy and held **constant**; strings are **fixed-dp** with base-10 **half-even** rounding.
* [ ] No renormalisation anywhere in S3; priors are **scores only** and live **only** in `s3_base_weight_priors`.

## G. Integerisation (optional)

* [ ] Largest-Remainder wrapper uses **exact rational** math; residuals quantised at `dp_resid` (default **8**) with **half-even** ties.
* [ ] Floors/ceilings (if present) are enforced; infeasible configs **raise** (no best-effort). Capacity guard (`R ≤ eligible_count`) is applied.
* [ ] Output includes **`residual_rank`** consistent with bump order.

## H. Sequencing (optional)

* [ ] Per-country **`site_order = 1..nᵢ`** contiguous; optional `site_id` equals **zero-padded** order (width **6**); counts exceeding **999 999** **fail**.

## I. Emitters (parameter-scoped, atomic)

* [ ] Emitters enforce **embed = path** (`row.parameter_hash == partition key`) and **no volatile fields**.
* [ ] Writer applies **logical order** per table and publishes via **fsync → atomic rename**.
* [ ] Idempotence hook (**`skip_if_final`**) is supported; conflicts return a clear error.

## J. Complexity & resources

* [ ] Per-merchant: **ranking O(k log k)**; integerisation **O(k log k)**; sequencing **O(∑nᵢ)**; memory **O(k)**.
* [ ] No universe-wide materialisation; streaming writers used.

## K. Tiny unit checks (fast gates)

* [ ] **Candidate set:** exactly one home; `candidate_rank` contiguous `0..K−1`; home has **rank 0**.
* [ ] **Priors:** `dp` constant within slice; each `base_weight_dp` passes fixed-dp parser.
* [ ] **Counts:** `Σ count = N` and `residual_rank` is a `1..M` permutation.
* [ ] **Sequence:** per-country `1..nᵢ`; `site_id` ⇄ order equality when enabled.

## L. Cross-doc consistency

* [ ] All dataset IDs, schema anchors, and partitioning rules match the **authoritative S3 schema/dictionary**.
* [ ] Consumer notes consistently point to **`candidate_rank`** as the **only** inter-country order authority.

**If every item above is green, S3·L0 is “done” and ready to wire into L2/L3 without implementer guesswork.**

---

# 20) Schema/Dataset Index (one-screen map)

A compact, single source of truth tying S3 emitters to **schema anchors**, **partitions**, and **logical order**. Use this when wiring L2 and writing validators.

```
DATASET: s3_candidate_set
SCHEMA : schemas.1A.yaml#/s3/candidate_set
PARTN  : parameter_hash={…}                   // parameter-scoped (no seed)
ORDER  : (merchant_id ASC, candidate_rank ASC, country_iso ASC)
EMITTER: EMIT_S3_CANDIDATE_SET(rows, parameter_hash, manifest_fp, skip_if_final)
OPT?   : No (required)
NOTES  : Single authority for inter-country order via candidate_rank (home=0; ranks contiguous).

DATASET: s3_base_weight_priors
SCHEMA : schemas.1A.yaml#/s3/base_weight_priors
PARTN  : parameter_hash={…}
ORDER  : (merchant_id ASC, country_iso ASC)
EMITTER: EMIT_S3_BASE_WEIGHT_PRIORS(rows, parameter_hash, manifest_fp, skip_if_final)
OPT?   : Yes
NOTES  : Deterministic scores (not probabilities). base_weight_dp is fixed-dp string; dp constant per run.

DATASET: s3_integerised_counts
SCHEMA : schemas.1A.yaml#/s3/integerised_counts
PARTN  : parameter_hash={…}
ORDER  : (merchant_id ASC, country_iso ASC)
EMITTER: EMIT_S3_INTEGERISED_COUNTS(rows, parameter_hash, manifest_fp, skip_if_final)
OPT?   : Yes
NOTES  : Largest-Remainder counts that sum to N (from S2); includes residual_rank (descending residual tie-break).

DATASET: s3_site_sequence
SCHEMA : schemas.1A.yaml#/s3/site_sequence
PARTN  : parameter_hash={…}
ORDER  : (merchant_id ASC, country_iso ASC, site_order ASC)
EMITTER: EMIT_S3_SITE_SEQUENCE(rows, parameter_hash, manifest_fp, skip_if_final)
OPT?   : Yes
NOTES  : Within-country `site_order = 1..nᵢ`; optional 6-digit site_id == zero-padded order.
```

**Global guarantees (apply to all four):**

* **Embed = path**: each row’s `parameter_hash` equals its partition key; `manifest_fingerprint` is embedded.
* **No volatile fields** in S3 tables (no timestamps / RNG envelopes).
* **Dictionary-resolved paths** only; schema anchors must match on write.
* **Atomic publish**: temp → fsync → rename; idempotence via `skip_if_final`.

---