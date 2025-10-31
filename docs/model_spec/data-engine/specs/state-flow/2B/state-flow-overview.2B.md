# 2B — Routing Through Sites (state-overview, 8 states)

## S0 — Gate & environment seal (RNG-free)

**Goal.** Pin identities and prove we’re allowed to read inputs.
**Must verify before any read.**

* **1B PASS**: check `_passed.flag` for `site_locations` (fingerprint-scoped; “No PASS → no read”). 
* Civil-time surfaces from **2A** (when available): tz tables/timetables manifests (pinned version + digests). (General “no PASS→no read” posture is in your top-level contract.) 
  **Fix for the run.** `{seed, manifest_fingerprint}`; record routing RNG policy digests you will use in later states. 

**Inputs (authority).**

* **`site_locations`** (1B egress; order-free; `[seed, fingerprint]`). 
* (If virtual merchants exist) **edge catalogues / weights** (governed). 

---

## S1 — Freeze per-merchant probability law (RNG-free)

**Goal.** Produce immutable `(site_id, p_i)` from foot-traffic scalars `F_i`; write canonical bytes with a digest.
**Algorithm essentials.** `w_i := F_i`; `p_i := w_i / Σ_j w_j` (binary64); persist exact order (lexicographic `site_id`) so two machines produce byte-identical `p_i`. Emit `<merchant_id>_pweights.bin` and record `weight_digest` in `routing_manifest.json`. 

**Outputs.** `pweights.bin` (+ `weight_digest` in manifest). 

---

## S2 — Build alias tables (RNG-free)

**Goal.** Build **O(1) alias** structures per merchant; freeze bytes + digest.
**Algorithm essentials.** Standard small/large stacks → fill `prob`/`alias`; save uncompressed `<merchant_id>_alias.npz` with `alias_digest`. Compute and embed a **`universe_hash`** that concatenates governed digests (zone-alpha / θ / zone-floors / γ-variance / zone-alloc parquet) so drift is detectable at open.

**Outputs.** `<merchant_id>_alias.npz` (prob+alias), `universe_hash` in file header. 

---

## S3 — Corporate-day modulation (RNG-bounded; one draw/day/merchant)

**Goal.** Inject subtle cross-zone co-movement without changing century-scale shares.
**Algorithm essentials.** Draw γ_d once per merchant per UTC day:
[
\log \gamma_d \sim \mathcal N!\bigl(-\tfrac12\sigma_\gamma^2,;\sigma_\gamma^2\bigr)
]
Seed derivation and Philox sub-stream policy per governed `rng_policy.yml`; first counter used for γ_d, subsequent uniforms for routing. Persist `gamma_variance_digest` and RNG policy digests in routing manifest. 

---

## S4 — Zone-group re-normalisation (RNG-free)

**Goal.** Keep **intra-zone** probabilities coherent under γ_d while preserving alias mechanics.
**Algorithm essentials.** For a proposed local `t_local`, compute day `d`, scale `p_i ← γ_d·p_i` **within the originating site’s time-zone group**, then re-normalise s.t. Σ_group p_i = 1. (Alias lookup then uses the same tables with a scaled threshold—no rebuild.) 

---

## S5 — Router core (RNG-bounded; O(1) per event)

**Goal.** Turn each candidate local-time arrival into `(site_id, tzid)` deterministically.
**Algorithm essentials.** Draw `u` from the Philox sub-stream; `k = ⌊u·N_m⌋`;
`site_id = k if u < prob[k] else alias[k]`. Return `(site_id, tzid)` to the temporal engine, which handles UTC↔local and DST rules (from 2A). 

**Interface to L2.** Input: `(merchant_id, t_local, tzid_origin)`; Output: `(site_id, tzid_origin)` (temporal converts to UTC and writes the row). 

---

## S6 — Virtual-merchant edge routing (branch; RNG-bounded)

**Goal.** For `is_virtual=1`, select a CDN **edge** (country-weighted) and expose IP geo while settlement TZ drives cut-off.
**Algorithm essentials.** Use per-merchant **CDN alias** (built from `edge_weight`); Philox key `SHA256(global_seed ∥ "CDN" ∥ merchant_id)` per governed policy. Record `ip_country`, `ip_lat`, `ip_lon` from chosen edge; settlement zone sets `event_time_utc`. Validation later checks `ip_country` share against YAML weights and daily cut-off alignment.

---

## S7 — Audits, replay checks & CI (RNG-free)

**Goal.** Prove determinism and detect drift during long runs.
**What to do.** Every ~10⁶ routed events compute
`checksum = SHA256(merchant_id || batch_index || cumulative_counts_vector)` and append to `logs/routing/routing_audit.log` (rotation/retention governed). Nightly CI replays and expects matching checksums. 

---

## S8 — Validation bundle & PASS gate (fingerprint-scoped)

**Goal.** Seal routing assets so downstream readers can hard-gate.
**Bundle contents (minimum).**

* MANIFEST: `seed, manifest_fingerprint, weight_digest, alias_digest, universe_hash, gamma_variance_digest, rng_policy_digests`.
* **Determinism evidence:** audit checksums; alias open verifies `universe_hash`. 
* **Distributional checks:** after removing γ_d (divide-out), empirical outlet shares track frozen `p_i` within governed tolerance. (For virtuals: `ip_country` tolerances & settlement cut-off CI.) 
* `index.json` + `_passed.flag` (ASCII-lex SHA-256 over listed files; flag excluded). **No PASS → no read.**

---

## Cross-state invariants (what keeps this green)

* **Authority & identity.** Read `site_locations` only **after** 1B PASS; all routing artefacts bind to `{seed, manifest_fingerprint}`; path tokens and embedded lineage must byte-equal.
* **RNG posture.** Counter-based Philox; open-interval mapping; sub-streams governed by `rng_policy.yml` for γ_d and (if virtual) CDN edges; per-event budgets consistent with your engine-wide rules. 
* **Byte-for-byte freeze.** `pweights.bin` and alias `.npz` are canonical; **universe_hash** pins all priors/allocation knobs that could change routing behaviour. 
* **Interface discipline.** Router returns `(site_id, tzid)`; civil-time legality and UTC conversion live in 2A/L2, not here. 

## Failure vocabulary (examples; deterministic aborts)

* `RouterInputGateError` (missing 1B PASS / manifest mismatch). 
* `AliasDriftError` (universe_hash mismatch when opening alias). 
* `RoutingDeterminismError` (checksum replay mismatch in CI). 
* `VirtualValidationError` (ip-country / settlement cut-off outside governed tolerances). 

---

### Why this is practical to implement

* It mirrors your documented pipeline (weights → alias → day-effect → O(1) selection), names the exact **bytes** to freeze, and ties them to digests.
* It leaves civil-time logic where it belongs (2A/L2), keeping 2B fast and auditable. 
* The PASS bundle + **universe_hash** gives reviewers a one-look drift answer and a clean consumer gate. 
