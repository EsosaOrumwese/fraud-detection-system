# Segment 2B — Design vs Implementation Observations (Routing: Sites + Virtual Edges)
Date: 2026-01-31
Scope: Design intent vs implementation notes for Segment 2B (S0–S8), plus what to look for in 2B datasets before assessment.

---

## 0) Why this report exists
Segment 2B is the **routing realism layer**. It turns merchant/site geography (1B + 2A) into **probabilistic routing surfaces** for physical sites, plus a **virtual-edge routing branch** for virtual merchants. It also produces the audit/validation evidence that the rest of the platform consumes. This report captures **what the design specifies**, **what the implementation actually does**, and **what signals we should look for** in the 2B datasets when assessing realism and correctness.

---

## 1) Design intent (what 2B should do)
High-level intent across states:

1) **S0 — Gate + sealed inputs**
   - Verify upstream 1B PASS bundle (No PASS → No read).
   - Seal required inputs: `site_locations` (1B), `site_timezones` (2A), plus 2B policy packs.
   - Emit `s0_gate_receipt_2B` and `sealed_inputs_2B` under manifest_fingerprint.

2) **S1 — Site weights**
   - Build a **per‑site weight law** for each merchant (RNG‑free).
   - Output `s1_site_weights` with normalized weights and provenance.

3) **S2 — Alias encoding**
   - Encode `s1_site_weights` into alias tables for O(1) sampling.
   - Output `s2_alias_index` + `s2_alias_blob` with strict header ↔ policy echo and blob checksum.

4) **S3 — Day effects**
   - Generate per‑merchant × UTC‑day × tz‑group **gamma multipliers** (RNG‑bounded).
   - Output `s3_day_effects` with strict day grid from policy.

5) **S4 — Group weights**
   - Combine base site weights with day effects to produce per‑merchant/day **tz‑group mix**.
   - Output `s4_group_weights` where Σ p_group = 1.

6) **S5 — Router core (group → site)**
   - For each arrival: pick tz‑group (Stage A) then site within group (Stage B).
   - Two single‑uniform RNG draws per arrival; strict RNG envelope logs.
   - S5 produces **no mandatory egress**; only logs (optional `s5_selection_log`).

7) **S6 — Virtual merchant edge routing**
   - If `is_virtual=1`, pick a **virtual edge** from `virtual_edge_policy_v1`.
   - Exactly one draw per virtual arrival; attach edge metadata.
   - Optional `s6_edge_log`; run‑scoped RNG evidence.

8) **S7 — Audit & CI gate**
   - RNG‑free audit of S2/S3/S4 + policy echo; optional S5/S6 log reconciliation.
   - Emit `s7_audit_report` at `[seed, manifest_fingerprint]`.

9) **S8 — Validation bundle + _passed.flag**
   - Package S7 PASS evidence per seed; compute index + `_passed.flag`.
   - Emit manifest_fingerprint‑scoped validation bundle as consumer gate.

---

## 2) Expected datasets & evidence surfaces (contract view)
Core datasets to assess later:

**Gate + sealing**
- `s0_gate_receipt_2B`, `sealed_inputs_2B`

**Routing surfaces**
- `s1_site_weights`
- `s2_alias_index`, `s2_alias_blob`
- `s3_day_effects`
- `s4_group_weights`

**Routing diagnostics (optional / run‑scoped)**
- `s5_selection_log`
- `s6_edge_log`
- `rng_audit_log`, `rng_trace_log`
- `rng_event_alias_pick_group`, `rng_event_alias_pick_site`, `rng_event_cdn_edge_pick`

**Audit + gate**
- `s7_audit_report`
- `validation_bundle_2B` + `index.json` + `_passed.flag`

These are the surfaces we will use to evaluate realism and coherence.

---

## 3) Implementation observations (what is actually done)

### 3.1 S0 — Gate + sealed inputs
**Observed posture:** Strict, deterministic, and consistent with other segments.

Key implementation traits:
- **Upstream 1B gate is enforced before any 1B read**, with index‑based hash recomputation (ASCII‑lex order) to match bundle law.
- **Sealed inputs are explicit**: `site_locations`, `site_timezones`, 2B policy packs, and 1B gate artefacts; optional `tz_timetable_cache` is warn‑only.
- **Schema validation tightened** by inlining external `$defs` for layer1, preventing resolver failures.
- **Policy versions aligned to semver** and schema enforcement added (policy_version pattern).
- **Flag parsing hardened** to tolerate whitespace / minor formatting while still validating hash equality.
- **Immutability enforced**: any re‑emit must be byte‑identical or abort.

Net: S0 is production‑grade and gate‑strict; most adjustments were robustness fixes rather than scope changes.

---

### 3.2 S1 — Site weights
**Observed posture:** Implemented as RNG‑free weighting, used as the canonical source for alias construction.

Implementation notes from the map indicate:
- Weights are normalized per merchant; provenance columns track `weight_source`, quantised bits, and floor behavior.
- Writer order and partitioning strictly match schema (`merchant_id`, `legal_country_iso`, `site_order` under `[seed, manifest_fingerprint]`).

Expectations: if weights are realistic, they should reflect plausible merchant‑site footprints rather than uniform or single‑site spikes.

---

### 3.3 S2 — Alias index + blob
**Observed posture:** Implemented with strict parity checks and enforced layout echo.

Key points:
- Index header must match `alias_layout_policy_v1` (endianness, alignment, quantised_bits, layout_version).
- Blob SHA‑256 is verified; alias slice offsets are enforced.
- Any parity mismatch is a hard fail in audits.

---

### 3.4 S3 — Day effects
**Observed posture:** RNG‑bounded and policy‑driven (day grid from `day_effect_policy_v1`).

Important implementation history:
- The day_range **must match downstream horizons** (5B). Policy was updated to align the day range with 2026; S0 must be re‑run when policy digests change.
- S3 outputs carry counters (`rng_counter_hi/lo`) to support audit traces.

Risk note: if the policy day range diverges from arrivals, S4 will have missing group weights and S5 will fail with missing days.

---

### 3.5 S4 — Group weights
**Observed posture:** Deterministic mix per merchant/day/tz_group; Σ p_group = 1 enforced in audits.

Implementation implications:
- S4 depends on `site_timezones` (tz groups) + S3 gamma + base shares.
- Any mismatch between day grids and arrival roster triggers S5 failures.

---

### 3.6 S5 — Router core (group → site)
**Observed posture:** Implemented as two‑stage O(1) routing with strict RNG accounting.

Key mechanics:
- **Two draws per arrival** (alias_pick_group, alias_pick_site).
- **Group pick uses S4**, then **site pick uses S1 filtered by site_timezones** (Option‑A path).
- S2 alias artefacts are integrity‑checked but not directly used for group‑slice decoding in v1.
- Optional `s5_selection_log` is run‑scoped and arrival‑ordered when enabled.

---

### 3.7 S6 — Virtual edge routing
**Observed posture:** Implemented as a branch for `is_virtual=1` only, with one draw per virtual arrival.

Key mechanics:
- Uses `virtual_edge_policy_v1` (token‑less, S0‑sealed).
- Optional `s6_edge_log` run‑scoped; no manifest_fingerprint‑scoped egress.

---

### 3.8 S7 — Audit & CI gate
**Observed posture:** Implemented as RNG‑free audit with strict validator mapping.

Notable implementation decision:
- **S7 does NOT require S2/S3/S4 outputs to be in `sealed_inputs_2B`** (those are within‑segment outputs). It resolves them directly at `[seed, manifest_fingerprint]` per Dictionary. This prevents false failures from sealed‑inputs under‑coverage.

Expectations:
- S7 checks alias parity, Σ p_group = 1, gamma echo, day grid equality, and (if logs exist) RNG budget reconciliation.

---

### 3.9 S8 — Validation bundle
**Observed posture:** Implemented, but with a **documented deviation**.

Deviation:
- **Index‑only bundle** (no copying of evidence). `index.json` entries are **run‑root‑relative** paths; `_passed.flag` hashes those source bytes.
- This **deviates from spec**, which expects index paths relative to the bundle root with evidence files inside the bundle. The deviation is explicit and accepted to match index‑only behavior used elsewhere.

Implication for platform:
- Any gate verifier must use the **index‑driven hash law with run_root base** (not bundle root). This has already been wired into the interface pack elsewhere.

---

## 4) Design vs implementation deltas (summary)
1) **S8 index‑only bundle**: Spec expects bundle‑local evidence; implementation uses run‑root paths and minimal bundle contents. This is a deliberate deviation and must be honored by gate verification.
2) **S7 sealed‑inputs posture**: S7 does not require S2/S3/S4 in `sealed_inputs_2B`, aligning with the S0‑evidence rule (within‑segment outputs aren’t S0‑sealed). This is a sensible correction and avoids false audit failures.
3) **Day‑range alignment**: The policy day_range was updated to match downstream horizons; runs must reseal S0 when policy digests change to avoid mismatches.
4) **Roster day alignment**: Arrival roster normalization now derives `utc_day` from policy start_day by default to avoid group‑weight gaps.

These deltas matter because they directly affect whether datasets align with the design intent and whether gates are verified correctly in the platform.

---

## 5) What to look for in 2B datasets (realism + correctness)
This section is the **forward‑looking checklist** for when we assess the actual 2B outputs. It is focused on realism, not just structural validity.

**Realism focus priority (where the analytical energy goes):**
1) **`s1_site_weights`** — baseline spatial realism (if this collapses, everything downstream collapses).
2) **`s4_group_weights`** — actual routing mix realism across tz‑groups and days.
3) **`s3_day_effects`** — temporal realism driver (day‑level modulation).
All other datasets are **structural / compliance** surfaces (alias blobs, audit logs, bundle gates) and should be validated, but they are not the primary realism signals.

### 5.1 `s1_site_weights` (realism baseline)
**What to inspect:**
- **Weight concentration per merchant**: Are weights overly concentrated on a single site, or do they show realistic distribution across multiple sites?
- **Country/site diversity**: Do merchants with multi‑country footprints have meaningful weights across those countries?
- **Weight sources**: Confirm `weight_source` aligns with design choices (not placeholder or static defaults).

**Red flags:**
- Most merchants have exactly one site with p_weight ~1.0.
- Global distribution mirrors the 1B single‑tile artifact (weights assigned to one coordinate cluster per country).

---

### 5.2 `s2_alias_index` + `s2_alias_blob` (alias integrity)
**What to inspect:**
- **Header parity** with `alias_layout_policy_v1` (endianness, alignment, quantised_bits).
- **Blob digest** matches `blob_sha256` in the index.
- **Merchant slice sizes** correlate with the number of sites per merchant (no zero‑length slices).

**Red flags:**
- Any parity mismatch or missing merchants in the index.
- Large discrepancies between site counts and alias slice sizes.

---

### 5.3 `s3_day_effects` (temporal realism)
**What to inspect:**
- **Day grid matches policy** (`day_effect_policy_v1` start/end).
- **Gamma distribution**: Does log‑gamma look plausible (log‑normal spread)?
- **Coverage**: All merchants present for all days, across tz groups.

**Red flags:**
- Missing days or tz groups.
- Gammas tightly clustered around 1.0 with negligible variance (no temporal realism), or extreme outliers without explanation.

---

### 5.4 `s4_group_weights` (routing mix realism)
**What to inspect:**
- **Σ p_group = 1** per merchant/day.
- **Group diversity**: Do merchants in multi‑tz regions have meaningful multi‑group mixes?
- **Gamma echo**: `gamma` in S4 must equal S3 gamma for the same merchant/day/group.

**Red flags:**
- Single group dominates for all merchants (suggests no time‑zone realism).
- Mismatched gamma or missing groups.

---

### 5.5 `s5_selection_log` + RNG logs (routing behavior)
**What to inspect:**
- **Exactly two events per arrival** (group → site), counters monotone.
- **Arrival order preserved** in the selection log.
- **Group ↔ site coherence**: site chosen should belong to selected tz group.

**Red flags:**
- Missing event families, incorrect draw counts, or non‑monotone counters.
- Site not in selected group (mapping bug).

---

### 5.6 `virtual_edge_policy_v1` + `s6_edge_log` (virtual realism)
**What to inspect:**
- **Edge distribution realism**: do edge locations and weights align with intended global footprint?
- **Country mapping**: does `ip_country` correspond plausibly to edge lat/lon?
- **One draw per virtual arrival** in RNG logs.

**Red flags:**
- Edge picks always map to a single edge or single country.
- Edge lat/lon inconsistent with ip_country.

---

### 5.7 `s7_audit_report` + validation bundle
**What to inspect:**
- Audit summary PASS, WARN counts explained.
- Checks for alias parity, Σ p_group, and day‑grid equality.
- Validation bundle index uses run‑root paths (index‑only) and `_passed.flag` digest matches recomputed bytes.

**Red flags:**
- PASS but missing metrics; or bundle digest fails when recomputed with run_root base.

---

## 6) Interpretation guide (when we assess realism)
If 2B outputs look unrealistic, the most likely upstream drivers are:
1) **1B site_locations collapse** (single‑tile or single‑band coordinates) → leads to single tz groups and poor routing diversity.
2) **Policy day_range mismatch** → missing group weights and time grid gaps.
3) **Over‑constrained weight generation** → single‑site dominance and no meaningful routing variety.

So in assessment, we will separate:
- **Structural correctness** (schemas, gates, Σ laws, parity).
- **Realism quality** (diversity of sites, tz groups, temporal patterns, and edges).

---

(Next: detailed assessment of the actual 2B outputs under your run folder.)
