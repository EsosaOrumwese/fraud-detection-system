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

## 8) Statistical overview / summary (pre‑assessment snapshot)
Run scope: `runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer3\6A`

### 8.1 Totals (row counts)
1. `s1_party_base_6A`: **3,281,174** parties
2. `s2_account_base_6A`: **8,725,420** accounts
3. `s2_party_product_holdings_6A`: **7,271,622** rows
4. `s3_instrument_base_6A`: **10,701,854** instruments
5. `s3_account_instrument_links_6A`: **10,701,854** links
6. `s4_device_base_6A`: **7,263,186** devices
7. `s4_ip_base_6A`: **366,161** IPs
8. `s4_device_links_6A`: **7,263,186** links
9. `s4_ip_links_6A`: **2,226,704** links
10. `s5_*_fraud_roles_6A`: party **3,281,174**; account **8,725,420**; merchant **1,238**; device **7,263,186**; IP **366,161**

### 8.2 Coverage and linkage (sanity checks)
1. Parties with accounts: **3,258,009** (99.29% of parties)
2. Parties with devices: **3,103,813** (94.59% of parties)
3. Accounts with instruments: **6,176,060** (70.78% of accounts)
4. Instruments linked to accounts: **100%** (links == instruments)
5. Devices linked to parties: **100%** (links == devices)
6. IPs linked to devices: **334,529** (91.36% of IPs)

Note: `s4_device_links_6A.account_id` is **entirely null** in this run (0 non‑null rows), so device links are party‑level only here.

### 8.3 Population mix (party types and segments)
Party type mix:
1. `RETAIL`: **96.77%**
2. `BUSINESS`: **2.75%**
3. `OTHER`: **0.48%**

Top segments by count:
1. `RETAIL_FAMILY`: **687,932**
2. `RETAIL_MATURE`: **550,809**
3. `RETAIL_EARLY_CAREER`: **536,394**
4. `RETAIL_RETIRED`: **359,413**
5. `RETAIL_STUDENT`: **343,439**
6. `RETAIL_VALUE`: **326,763**
7. `RETAIL_MASS_MARKET`: **258,327**
8. `RETAIL_AFFLUENT`: **112,271**
9. `BUSINESS_SOLE_TRADER`: **22,773**
10. `BUSINESS_SME`: **19,204**

Top countries by count:
1. `DE`: **477,018**
2. `FR`: **354,149**
3. `GB`: **336,515**
4. `DK`: **210,079**
5. `CH`: **192,274**

Regions by count:
1. `REGION_AFRICA`: **1,019,075**
2. `REGION_EMEA`: **891,125**
3. `REGION_APAC`: **657,966**
4. `REGION_LATAM`: **443,090**
5. `REGION_AMER`: **269,918**

### 8.4 Accounts and holdings
Accounts per party (from `s2_account_base_6A`):
1. mean **2.678**, p50 **2**, p90 **5**, p99 **8**, max **136**

Account type mix (top shares):
1. `RETAIL_CURRENT_BASIC`: **36.39%**
2. `RETAIL_CREDIT_CARD_STANDARD`: **17.97%**
3. `RETAIL_SAVINGS_INSTANT`: **17.09%**
4. `RETAIL_CURRENT_PREMIUM`: **9.39%**
5. `RETAIL_SAVINGS_FIXED`: **7.74%**

Holdings table (`s2_party_product_holdings_6A`):
1. Parties covered: **3,258,009**
2. Total accounts per party (sum across holdings): mean **2.678**, p50 **2**, p90 **5**, p99 **8**, max **136**

### 8.5 Instruments
Instruments per account (accounts with ≥1 instrument):
1. mean **1.733**, p50 **1**, p90 **3**, p99 **5**, max **13**

Instruments per party:
1. mean **3.465**, p50 **3**, p90 **6**, p99 **11**, max **189**

Instrument type mix (top shares):
1. `RETAIL_DEBIT_CARD_PHYSICAL`: **33.38%**
2. `PARTY_BANK_ACCOUNT_DOMESTIC`: **23.99%**
3. `RETAIL_CREDIT_CARD_PHYSICAL`: **17.23%**
4. `RETAIL_DEBIT_CARD_VIRTUAL`: **12.40%**
5. `WALLET_DEVICE_TOKEN`: **5.55%**
6. `RETAIL_CREDIT_CARD_VIRTUAL`: **5.40%**

### 8.6 Devices and IPs
Devices per party:
1. mean **2.34**, p50 **2**, p90 **4**, p99 **7**, max **14**

Devices per IP:
1. mean **6.65**, p50 **2**, p90 **5**, p99 **172**, max **6,114**

Device type mix (top shares):
1. `MOBILE_PHONE`: **58.55%**
2. `LAPTOP`: **12.67%**
3. `DESKTOP`: **10.70%**
4. `TABLET`: **9.94%**
5. `WEARABLE`: **5.77%**

IP type mix (top shares):
1. `RESIDENTIAL`: **96.27%**
2. `CORPORATE`: **1.95%**
3. `MOBILE`: **1.00%**
4. `PUBLIC_WIFI`: **0.31%**
5. `HOTEL_TRAVEL`: **0.27%**

### 8.7 Static fraud posture (role mixes)
Parties:
1. `CLEAN`: **94.95%**
2. `MULE`: **2.45%**
3. `SYNTHETIC_ID`: **2.03%**
4. `ORGANISER`: **0.30%**
5. `ASSOCIATE`: **0.27%**

Accounts:
1. `CLEAN_ACCOUNT`: **97.92%**
2. `HIGH_RISK_ACCOUNT`: **1.21%**
3. `MULE_ACCOUNT`: **0.55%**
4. `DORMANT_RISKY`: **0.32%**

Merchants:
1. `NORMAL`: **99.27%**
2. `HIGH_RISK_MCC`: **0.40%**
3. `COLLUSIVE`: **0.32%**

Devices:
1. `CLEAN_DEVICE`: **96.93%**
2. `HIGH_RISK_DEVICE`: **2.49%**
3. `REUSED_DEVICE`: **0.58%**

IPs:
1. `SHARED_IP`: **88.01%**
2. `HIGH_RISK_IP`: **9.47%**
3. `CLEAN_IP`: **2.52%**

---

## A) Population & segmentation realism (S1)

### A1. Population structure is internally consistent
1. **Total parties = 3,281,174** and `party_id` is **unique** (no duplication).  
   This is a foundational integrity check: the party base is clean and safe for joins downstream.
2. Coverage spans **77 countries**, **5 regions**, and **17 segments**.  
   That is a healthy diversity footprint; realism now depends on the distribution of those entities across geography and segment types.

### A2. Party type mix is strongly retail‑weighted
1. `RETAIL` = **96.77%**, `BUSINESS` = **2.75%**, `OTHER` = **0.48%**.  
   This is a deliberate posture: the synthetic bank is overwhelmingly retail. That can be realistic *if* the target institution is retail‑dominant; if we expect a larger SME share, this is likely too low and will suppress business‑behavior realism downstream.

### A3. Segment assignment is coherent with party type
1. **No leakage between party types and segment families**:  
   All `RETAIL_*` segments appear only under `party_type=RETAIL`, and all `BUSINESS_*` segments appear only under `party_type=BUSINESS`.  
   This indicates segmentation logic is internally consistent rather than cross‑contaminated.
2. Segment weight is concentrated in retail cohorts:  
   `RETAIL_FAMILY` (20.97%), `RETAIL_MATURE` (16.79%), `RETAIL_EARLY_CAREER` (16.35%), `RETAIL_RETIRED` (10.95%), etc.  
   Business segments are present but tiny (~0.3–0.7% each), which is consistent with the overall low business share.

### A4. Country concentration is high (top‑heavy distribution)
1. Top country shares are large: `DE` **14.54%**, `FR` **10.79%**, `GB` **10.26%**.  
   This is a **strong concentration** in the top three countries; it will shape downstream behavior and geography realism.
2. **HHI = 0.0633**, which implies an “effective” **~15.8 countries** (1/HHI).  
   Even though 77 countries are present, the distribution behaves like a much smaller set of dominant countries. This is not automatically unrealistic, but it is a posture choice.

### A5. Region mix reflects synthetic hashing, not true geography
1. Region shares:  
   `REGION_AFRICA` **31.1%**, `REGION_EMEA` **27.2%**, `REGION_APAC` **20.1%**, `REGION_LATAM` **13.5%**, `REGION_AMER` **8.2%**.  
   Because regions are derived from a hashed country‑to‑region mapping, this is **not a real demographic distribution**; it is a deterministic partitioning.  
   The realism implication is: **regional ratios should be treated as synthetic buckets**, not real‑world geography.

### A6. Country‑level segment mix is almost uniform
1. The L1 distance between each country’s segment mix and the global segment mix is:  
   p50 **0.148**, p90 **0.178**, max **0.178** (countries with ≥10k parties).  
   Interpreting L1 as total variation: most countries differ from global by only ~7–9% in total mass.  
   This means **country‑specific segmentation is weak** and the population is effectively governed by a global segment prior.

### A7. Business share is narrowly ranged across countries
1. For countries with ≥10k parties, business share ranges roughly **2.0% → 4.0%**.  
   This is a very tight band; countries do not meaningfully differ in business intensity.  
   That is consistent with a global business‑share policy and inconsistent with a world where business density varies substantially by country.

### A8. Interpretation for realism
1. **Strength:** segmentation is consistent and logically clean (no cross‑type leakage).  
2. **Posture:** the world is strongly retail‑heavy, top‑heavy by country, and geographically uniform in segment mix.  
3. **Realism impact:** this is *statistically coherent* but **policy‑driven**, not emergent geography. If stronger geo‑specific realism is desired, priors need country‑level modulation.

---

## B) Accounts & holdings realism (S2)

### B1. Account coverage is broad, with a small “no‑account” tail
1. Parties with accounts: **3,258,009** out of **3,281,174** → **99.29%** coverage.  
2. Parties without accounts: **23,165** → **0.71%**.  
   This is a small but non‑zero tail, which is realistic for dormant/placeholder parties. If you intended a fully banked world, this tail should be zero; otherwise it looks plausible.

### B2. Holdings table reconciles exactly with the account base
1. Accounts per party from `s2_account_base_6A`:  
   mean **2.678**, p50 **2**, p90 **5**, p99 **8**, max **136**.  
2. The same distribution reconstructed from `s2_party_product_holdings_6A` matches exactly.  
   This shows the holdings table is a faithful summary rather than a lossy or diverging view.

### B3. Accounts‑per‑party distribution has a heavy tail but a stable core
1. Most parties sit in a tight band: p50 **2**, p90 **5**, p99 **8**.  
2. The extreme tail is long: max **136** accounts for a single party.  
   That single‑party extreme is the main realism question here. If the priors allow “stacked” accounts for special entities, it is explainable; if not, it is a tail artifact.

### B4. Retail vs business posture is strongly retail‑skewed
1. Account share by party type:  
   `RETAIL` **97.61%**, `BUSINESS` **2.14%**, `OTHER` **0.25%**.  
2. This is even more retail‑heavy than the party mix (business parties are 2.75%), which implies **business parties hold fewer accounts on average** than retail parties.

### B5. Accounts per party by party type show unexpected ordering
1. Mean accounts per party:  
   `RETAIL` **2.70**, `BUSINESS` **2.13**, `OTHER` **1.43**.  
2. In most real systems, business entities tend to hold **more** accounts than retail on average.  
   Here, business holds **fewer**. That may be by design, but it is a realism flag if you want SMEs to carry more banking surface than individuals.

### B6. Account type mix is cleanly partitioned by party type
1. There is **no leakage** of retail account types into business and vice versa.  
   That is good structural realism: retail parties only hold retail products, business parties only hold business products, etc.
2. The top retail product mix is dominated by:  
   `RETAIL_CURRENT_BASIC`, `RETAIL_CREDIT_CARD_STANDARD`, `RETAIL_SAVINGS_INSTANT`.  
   This looks reasonable for a retail‑heavy synthetic bank.

### B7. Account‑type diversity per party is moderate
1. Distinct account types per party:  
   mean **2.23**, p50 **2**, p90 **4**, p99 **5**, max **7**.  
2. This suggests most parties hold **2 types** (e.g., current + savings or current + card), with a long but not extreme tail.  
   That is a plausible profile for synthetic realism.

### B8. Segment‑level product mix is highly uniform
1. In the top retail segments, the **account type ordering and mix are almost identical**.  
   `RETAIL_EARLY_CAREER`, `RETAIL_FAMILY`, `RETAIL_MATURE`, `RETAIL_RETIRED`, `RETAIL_STUDENT` all show the same ranking of account types with similar proportions.
2. This indicates the **product mix is not strongly segment‑specific**.  
   If you expected different segment preferences (students less fixed savings, retirees more fixed savings, etc.), the current mix is too uniform.

### B9. Interpretation for realism
1. **Strength:** account surfaces are structurally consistent and cleanly partitioned.  
2. **Posture:** retail dominance is reinforced at the account level and segment‑specific product variation is weak.  
3. **Realism impact:** the dataset is coherent but policy‑driven; realism would improve if business accounts and segment‑specific preferences were strengthened.

---

## C) Instruments realism (S3)

### C1. Coverage and linkage are structurally sound
1. Accounts with instruments: **6,176,060** out of **8,725,420** → **70.78%**.  
   About 29% of accounts are un‑instrumented. That is plausible if savings/loan accounts do not carry cards or tokens, but it is a posture decision.
2. Instruments linked to accounts: **100%** (no unlinked instruments).  
3. Orphan links to missing accounts: **0**.  
   Structural integrity is clean and safe for downstream use.

### C2. Instruments per account and per party
1. Instruments per account: mean **1.733**, p50 **1**, p90 **3**, p99 **5**, max **13**.  
2. Instruments per party: mean **3.465**, p50 **3**, p90 **6**, p99 **11**, max **189**.  
   The median shows most accounts are single‑instrument, but the party‑level tail is heavy. If high‑surface entities are intended (e.g., aggregators), the tail is explainable; otherwise it is a realism risk.

### C3. Instrument type mix is plausible but policy‑driven
Top instrument types by count:
1. `RETAIL_DEBIT_CARD_PHYSICAL`: **3,572,255**
2. `PARTY_BANK_ACCOUNT_DOMESTIC`: **2,567,677**
3. `RETAIL_CREDIT_CARD_PHYSICAL`: **1,843,492**
4. `RETAIL_DEBIT_CARD_VIRTUAL`: **1,327,292**
5. `WALLET_DEVICE_TOKEN`: **594,286**
6. `RETAIL_CREDIT_CARD_VIRTUAL`: **577,921**

This mix reflects a large physical card footprint plus a meaningful tokenized/virtual layer.

### C4. Virtual vs physical ratio
1. `PHYSICAL`: **5,544,115**
2. `VIRTUAL`: **1,905,213**
3. `OTHER` (bank accounts, non‑card handles): **3,252,526**

Virtual instruments are ~**17.8%** of total. That is moderate and may be low if the target world is very digital‑heavy.

### C5. Instrument–account alignment is coherent
1. `RETAIL_CURRENT_*` accounts map to **debit instruments**.  
2. `RETAIL_CREDIT_CARD_*` accounts map to **credit instruments**.  
3. Savings/loan accounts map to **bank account handles**.  
4. Business accounts follow the same logic with business‑branded instruments.  

This is a strong realism signal: instruments are attached in a way that matches product semantics, not randomly.

### C6. Instruments per account type show intended layering
1. Current and credit accounts carry **~1.8–2.1 instruments on average** (physical + virtual + tokens).  
2. Savings and loan accounts are **exactly 1 instrument** (bank account handle).  

This is a clear policy posture and is consistent with realistic product behavior.

### C7. Interpretation for realism
1. **Strength:** linkage is clean and instrument–product semantics are correct.  
2. **Posture:** instrument coverage is partial and virtual share is moderate.  
3. **Realism impact:** plausible overall, but tail heaviness (max 189 instruments per party) and the 29% un‑instrumented accounts should be confirmed as intended.
