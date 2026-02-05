# Segment 6A — Design vs Implementation Observations (Entity & Product World)
Date: 2026-02-05  
Run: `runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92`  
Scope: Design intent vs implementation notes for Segment 6A (S0–S5) prior to deep statistical assessment.

---

## 0) Why this report exists
Segment 6A builds the **synthetic entity world**: parties, accounts, instruments, devices/IPs, and the static fraud posture. This world is the backbone that 6B uses to simulate flows and fraud. If 6A’s population, holdings, graph structure, or fraud roles are statistically unrealistic, the downstream transaction realism will be compromised no matter how good 6B is.

This report anchors three things before analysis:
1. **Design intent** (what the 6A states are supposed to produce).
2. **Implementation posture** (what we actually built, including lean tradeoffs).
3. **Datasets of interest** (what we will examine for realism).

---

## 1) Design intent (what 6A should do)
1. **S0 — Gate & sealed inputs**  
   Bind the world to a single `manifest_fingerprint`, verify upstream PASS (1A–3B, 5A–5B), validate 6A contracts and priors, then seal the input universe into `sealed_inputs_6A`.

2. **S1 — Party base population**  
   Create the closed-world set of parties/customers, with stable IDs, segmentation, and region assignments. This is the sole authority on “who exists.”

3. **S2 — Accounts & product holdings**  
   Create the closed-world set of accounts/products, assign ownership to parties (and optionally merchants), and produce per-party holdings views.

4. **S3 — Instruments & credentials**  
   Create instruments (cards, transfer handles, wallets, etc.), attach them to accounts and parties, and emit account–instrument links.

5. **S4 — Devices, IPs & network graph**  
   Create devices and IP endpoints, wire them into a static graph over parties/accounts/instruments/merchants, and emit link tables.

6. **S5 — Static fraud posture & 6A HashGate**  
   Assign static fraud roles (party/account/merchant/device/IP) and close the segment with the 6A validation bundle and `_passed.flag`.

---

## 2) Priority datasets (realism‑relevant)
Primary realism surfaces:
1. `s1_party_base_6A` (population, segmentation, geography)
2. `s2_account_base_6A` (account existence and attributes)
3. `s2_party_product_holdings_6A` (distribution of products per party)
4. `s3_instrument_base_6A` (instrument mix and attributes)
5. `s3_account_instrument_links_6A` (instrument attachment topology)
6. `s4_device_base_6A` (device mix and attributes)
7. `s4_ip_base_6A` (IP mix and attributes)
8. `s4_device_links_6A` and `s4_ip_links_6A` (graph structure and sharing)
9. `s5_*_fraud_roles_6A` (static fraud posture by entity type)

Supporting summary views (useful for fast aggregation, not authoritative):
1. `s1_party_summary_6A`
2. `s2_account_summary_6A`
3. Optional `s3_instrument_summary_6A`, `s4_network_summary_6A`

Evidence/control surfaces (minimal realism impact, but explain constraints):
1. `s0_gate_receipt_6A`, `sealed_inputs_6A`
2. `validation_bundle_6A` + `_passed.flag`

---

## 3) Implementation observations (what is actually done)
Based on `docs\model_spec\data-engine\implementation_maps\segment_6A.impl_actual.md` and the 6A state‑expanded specs.

### 3.1 S0 — Gate & sealed inputs
Observed posture: strict schema compliance, metadata‑only sealing for large datasets.

Key implementation decisions:
1. **Schema validation is strict.**  
   All `schema_ref` anchors must resolve; any placeholder anchors cause S0 to FAIL.
2. **HashGate verification uses bundle indices.**  
   Upstream bundle digests are recomputed from index laws and compared to `_passed.flag` without re‑hashing all data.
3. **Structural digests for large data-plane surfaces.**  
   Large row‑level artefacts (e.g., `arrival_events_5B`) are sealed by structural digests (path/template/schema), while priors/policies are content‑hashed.

### 3.2 S1 — Party base population
Observed posture: deterministic, streaming generation with lean observability.

Key implementation decisions:
1. **S0 run‑report dependency relaxed.**  
   Because L3 contracts do not define a run‑report dataset, S1 uses `s0_gate_receipt_6A` + `sealed_inputs_6A` digest as the hard gate; missing run‑report is WARN‑only.
2. **Region mapping is synthetic.**  
   No sealed country→region mapping exists, so `region_id` is assigned via a deterministic hash of `country_iso` into the configured region list.
3. **RNG logs are aggregated.**  
   RNG events are logged per cell/batch, not per party, to avoid IO explosion.
4. **Summary built from counters.**  
   `s1_party_summary_6A` is derived from streaming counters without re‑scanning the base table.

### 3.3 S2 — Accounts & holdings
Observed posture: priors‑driven account counts with deterministic allocation.

Key implementation decisions:
1. **Account counts derived from priors.**  
   Uses `prior_account_per_party_6A` and `prior_product_mix_6A` to compute targets.
2. **Eligibility rules enforced.**  
   Product linkage and eligibility rules gate which parties can hold which products.
3. **Lean RNG/event logging.**  
   Allocation and attribute sampling are logged at aggregated granularity.

### 3.4 S3 — Instruments
Observed posture: instrument mix driven by priors and linked to accounts.

Key implementation decisions:
1. **Instrument mix from priors.**  
   `prior_instrument_per_account_6A` and `prior_instrument_mix_6A` define counts and composition.
2. **Deterministic account‑level allocation.**  
   Instruments are assigned to accounts with deterministic cell ordering and controlled RNG.
3. **Lean logging.**  
   RNG events are aggregated rather than per‑instrument.

### 3.5 S4 — Devices, IPs & graph
Observed posture: graph wiring is priors‑driven with deterministic sampling.

Key implementation decisions:
1. **Device/IP counts from priors.**  
   `prior_device_counts_6A` and `prior_ip_counts_6A` set expected counts by cell.
2. **Graph linkage rules enforced.**  
   `graph_linkage_rules_6A` and `device_linkage_rules_6A` drive sharing patterns.
3. **Optional graph summaries.**  
   `s4_network_summary_6A` is optional and not required for correctness.

### 3.6 S5 — Static fraud posture & HashGate
Observed posture: deterministic role assignment + lean validation bundle.

Key implementation decisions:
1. **Deterministic hash‑based role assignment.**  
   Fraud roles are assigned via hash‑derived scores rather than heavy stochastic simulation.
2. **Validation policy relaxed.**  
   Caps for max devices per IP, instruments per account, and risky IP fraction were raised to match observed synthetic distributions.
3. **Validation bundle is minimal.**  
   Only the validation report and issue table are included in the bundle; role tables remain in egress locations.

---

## 4) Design vs implementation deltas (material)
1. **S0 sealing is structural for large data.**  
   Design treats sealed inputs as authoritative; implementation uses structural digests for large row‑level artefacts instead of full content hashing.
2. **S1 region mapping is synthetic.**  
   The design presumes regions; implementation hashes countries into region buckets due to missing taxonomy.
3. **Run‑report gating is relaxed.**  
   Specs require S0 run‑report PASS; implementation uses S0 gate receipt + digest because L3 run‑reports are not defined.
4. **RNG observability is aggregated.**  
   RNG trace/audit is cell/batch‑level rather than per‑entity, for feasibility.
5. **S5 fraud roles are deterministic and validation caps are relaxed.**  
   The static fraud posture is hash‑based, and validation thresholds were raised to let current generators pass.

---

## 5) Expectations before statistical analysis
Given the design and implementation posture, we should expect:
1. **Party distributions match priors.**  
   Population totals and segment splits should align with `prior_population_6A` and `prior_segmentation_6A`, subject to integerisation.
2. **Account holdings match product mix.**  
   The number of accounts per party and the product mix should reflect priors and eligibility constraints, not arbitrary noise.
3. **Instrument counts align with account structures.**  
   Instruments per account should follow `prior_instrument_per_account_6A` and should not violate linkage rules.
4. **Graph structure reflects device/IP sharing rules.**  
   Devices per party, devices per account, IPs per device, and devices per IP should follow linkage policies (even if caps are high).
5. **Fraud roles align with priors and topology.**  
   Role proportions should match role priors, and role assignments should correlate with graph features where the policy expects it.
6. **ID and FK integrity is strict.**  
   No duplicate IDs, no dangling links, and all link tables should resolve to valid bases.

---

## 6) Implications for realism assessment
1. **Region realism must be interpreted cautiously.**  
   Because regions are hashed from countries, region‑level patterns are synthetic partitions, not true geography.
2. **We must verify distributions directly.**  
   Lean RNG logging and structural seals mean we cannot infer realism from gate artifacts alone; we need direct distributional checks.
3. **High‑degree tails may be policy‑driven.**  
   Relaxed validation caps imply that heavy tails (e.g., devices per IP) might be intentional for this synthetic world.

---

## 7) Next step
Proceed to statistical realism assessment, starting from:
1. `s1_party_base_6A`
2. `s2_account_base_6A` + `s2_party_product_holdings_6A`
3. `s3_instrument_base_6A` + `s3_account_instrument_links_6A`
4. `s4_device_base_6A` + `s4_ip_base_6A` + link tables
5. `s5_*_fraud_roles_6A`

---
