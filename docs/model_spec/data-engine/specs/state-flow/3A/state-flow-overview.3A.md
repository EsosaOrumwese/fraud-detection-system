# 3A — Capturing cross-zone merchants (state-overview, 7 states)

## S0 — Gate & environment seal (RNG-free)

**Goal.** Prove we’re authorised to read 1A, pin identities, and fix governed inputs.
**Must verify before any read.**

* **1A PASS** for the fingerprint: recompute the 1A bundle hash from `index.json` (ASCII-lex order; flag excluded) and match `_passed.flag` → **No PASS → no read**. Then assert path↔embed equality when opening `outlet_catalogue`.
  **Fix for the run.** `{seed, manifest_fingerprint}`; record digests for: `tz_world_2025a`, `zone_mixture_policy.yml`, `country_zone_alphas.yaml`, `zone_floor.yml` (and the day-effect policy you’ll register later).

---

## S1 — Mixture policy & escalation queue (RNG-free)

**Goal.** Decide which countries **need** an internal split into multiple IANA zones.
**Inputs.**

* From 1A: per-merchant **country counts** (vector **v**, normalised to unit mass for policy decisions). 
* **`zone_mixture_policy.yml`** (keys incl. `theta_mix`; digest recorded as `theta_digest`). Countries with mass ≥ θ enter the **escalation queue**; others remain **monolithic** in their country’s **largest-area TZID** from tz-world. 
  **Notes.** Largest-area TZID is taken from the frozen `tz_world_2025a` polygons (deterministic index build). 

---

## S2 — Load country→TZ Dirichlet priors (RNG-free)

**Goal.** Open the prior **α-ledger** and smooth as documented.
**Inputs.**

* **`config/allocation/country_zone_alphas.yaml`** mapping `ISO → {TZID: α}`; digest recorded as **`zone_alpha_digest`**. The file is built from public settlement statistics and smoothed by a global constant **τ = 200** (governed; reviewer-tunable). 

---

## S3 — Sample zone shares for escalated countries (RNG-bounded)

**Goal.** For each **queued** country with Nₙ outlets, draw zone shares and produce **real-valued** expectations.
**Algorithm essentials.**

* Draw **s ~ Dirichlet(α)** on a dedicated Philox sub-stream keyed by `(merchant_id, country_iso)`; compute expectations `E[count_z] = s_z · Nₙ` in binary64. 
  **RNG posture.** Sub-stream policy follows your engine’s Philox/open-interval conventions; draws are replayable. 

---

## S4 — Integerise with floors + bump rule (RNG-free)

**Goal.** Turn expectations into **integers** that (a) sum to Nₙ, (b) don’t erase micro-zones, and (c) are deterministic.
**Algorithm essentials.**

* **Largest-remainder** rounding; fixed tie-break by alphabetical `TZID`.
* **Bump rule:** if a zone’s fractional expectation > 0.8 but rounding would drop it to 0, reassign **one** outlet from the largest rounded zone in the same country.
* **Zone floors:** enforce tiny global floors **φ_z** from `zone_floor.yml`; reallocate from the largest zone within the country if a floor would be violated. Floors are tiny (<0.1%), so realism shift is negligible.

---

## S5 — Write allocation + bind to routing universe (RNG-free)

**Goal.** Publish the per-merchant zone allocation and register digests used by the router to detect drift.
**Outputs.**

* **`zone_alloc.parquet`** per merchant with `(country_iso, tzid, outlet_count)`; update **`zone_alloc_index.csv`** and record digests. Router later recomputes a **universe hash** over exactly
  `zone_alpha_digest ∥ theta_digest ∥ zone_floor_digest ∥ gamma_variance_digest ∥ zone_alloc_parquet_digest`
  and embeds it into each alias file. 
  **Corporate-day hook (no draw here).** Record the governed **day-effect variance** (`gamma_variance_digest`) so that 2B/L2 can realise the latent γ_d but the **universe hash** already covers the chosen policy.

---

## S6 — Structural validation & reports (RNG-free)

**Goal.** Prove allocation integrity before anyone consumes it.
**Checks.**

* **Per-country sums match:** `Σ_z count_z == Nₙ` for every country in **v**.
* **Escalation coherence:** non-queued countries produce exactly one `(country_iso, tzid)` (largest-area TZ). 
* **Floors satisfied** and **bump rule** applied deterministically (prove via reproducible diff if applied).
* **Index hygiene:** `zone_alloc_index.csv` lists **every** merchant once with a valid SHA-256 of its Parquet. 
  *(The later “offset-barcode slope” and “share-fidelity” diagnostics run as part of the cross-segment validation harness after arrivals exist; see Cross-segment note.)*

---

## S7 — Validation bundle & PASS gate (fingerprint-scoped, RNG-free)

**Goal.** Seal 3A so downstream readers can **hard-gate**.
**Bundle.** `data/layer1/3A/validation/fingerprint={manifest_fingerprint}/` with `MANIFEST.json`, `index.json`, allocation checks, digests (`theta_digest`, `zone_alpha_digest`, `zone_floor_digest`, `zone_alloc_index_digest`, `gamma_variance_digest`) and `_passed.flag` computed by the same **ASCII-lex + raw-bytes + SHA-256** law used in 1A/1B. **Consumers: no PASS → no read.**

---

## Cross-state invariants (what keeps this green)

* **Authority & identity.** 1A is read **only after** gate PASS; all 3A artefacts bind to `{seed, manifest_fingerprint}` and enforce path↔embed equality. 
* **RNG boundary.** Only **S3** consumes RNG (Dirichlet); everything else is deterministic. 
* **Governance.** `theta_mix`, α-ledger and zone-floors are YAML-governed with recorded digests; allocation files are digested and indexed for router drift checks via **universe hash**.

## Failure vocabulary (deterministic aborts)

* `GateFailure_1AFlagMismatch` (no PASS → no read). 
* `ZoneAlphaMissing` / `PolicyLedgerDigestMismatch`. 
* `AllocationSumMismatch` (Σ_z ≠ Nₙ for any country). 
* `FloorInfeasible` (φ_z cannot be satisfied without violating Nₙ). 
* `IndexDriftDetected` (zone_alloc_index.csv or per-merchant Parquet digest mismatch). 

---

### Cross-segment note (where the realism tests happen)

Once L2 produces ~30 synthetic days, the harness runs the **offset-barcode slope** test (expect slope in −1…−0.5 offsets/hour) and a **share-fidelity** check (empirical zone shares vs integer allocations, ≤ 2 pp deviation). Failing either **aborts the build**; thresholds live in `cross_zone_validation.yml`. (This CI lives with the validation rails but is **driven by** 3A/2B outputs.)
