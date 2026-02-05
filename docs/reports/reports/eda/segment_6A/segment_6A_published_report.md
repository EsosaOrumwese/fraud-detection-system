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
   This matters because downstream models and features can trust that “retail” and “business” segments mean what they say without hidden cross‑mixing.
2. **Posture:** the world is strongly retail‑heavy, top‑heavy by country, and geographically uniform in segment mix.  
   That posture will drive most geography‑based signals to reflect a few dominant countries and a global‑prior segment profile rather than local demographic nuance.
3. **Realism impact:** this is *statistically coherent* but **policy‑driven**, not emergent geography.  
   If stronger geo‑specific realism is desired, priors need country‑level modulation so that segments differ meaningfully across markets rather than by global averages.

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
   This means product holdings can be explained directly from party type and segment without worrying about schema noise or unexpected mixing.
2. **Posture:** retail dominance is reinforced at the account level and segment‑specific product variation is weak.  
   As a result, business patterns are under‑represented and segment‑driven behavioral differences will be muted in 6B.
3. **Realism impact:** the dataset is coherent but policy‑driven.  
   Realism would improve if business accounts were more prevalent and segment‑specific product preferences were stronger (e.g., students vs retirees).

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
   This preserves explainability: instruments look like they belong to the right products rather than arbitrary attachments.
2. **Posture:** instrument coverage is partial and virtual share is moderate.  
   That will dampen digital‑channel intensity unless 6B explicitly compensates for it.
3. **Realism impact:** plausible overall, but tail heaviness (max 189 instruments per party) and the 29% un‑instrumented accounts should be confirmed as intended.  
   If those are not policy‑driven, they could introduce unrealistic long‑tail behavior into downstream fraud features.

---

## D) Devices & IP graph realism (S4)

### D1. Device ownership is clean and fully linked
1. Devices per party (distinct): mean **2.34**, p50 **2**, p90 **4**, p99 **7**, max **14**.  
   This is a plausible consumer‑device profile (most parties have 1–3 devices, a minority have 6–7, and a very small tail up to 14).
2. All devices are linked to parties (**100%** coverage).  
   This is structurally clean and avoids “orphan device” artifacts.

### D2. Account‑level device linkage is absent in this run
1. `s4_device_links_6A.account_id` is **entirely null** (0 non‑null rows).  
   This means device graph structure is **party‑level only**, not account‑level.
2. If your design expects device→account binding (e.g., “this device is used for this account”), that realism dimension is currently missing; it will flatten device usage features downstream.

### D3. IP sharing shows a heavy‑tail but with a sharp core
1. Devices per IP: mean **6.65**, p50 **2**, p90 **5**, p99 **172**, max **6,114**.  
   This is a classic heavy‑tail: most IPs are lightly shared (1–5 devices), but a small fraction are **massively shared**.
2. The top IPs are extremely dense (6k+ devices each).  
   This is not impossible (e.g., NAT gateways, carrier‑grade NAT, shared public Wi‑Fi, data‑centre proxies), but it is **very strong** and will dominate “shared IP” signals unless bounded by policy.

### D4. IPs per device are tightly capped
1. IPs per device: mean **2.07**, p50 **2**, p90 **3**, p99 **3**, max **3**.  
   This is an unusually tight cap — it implies a fixed rule (1–3 typical IPs per device).
2. That cap is not necessarily unrealistic, but it does indicate a **hard policy limit**, not an emergent pattern. If you expect mobile devices or roaming behavior, you might want a broader tail.

### D5. Device type mix is plausible
1. `MOBILE_PHONE` **58.55%**, `LAPTOP` **12.67%**, `DESKTOP` **10.70%**, `TABLET` **9.94%**, `WEARABLE` **5.77%**, `IOT_DEVICE` **2.15%**, `SERVER` **0.23%**.  
   This looks like a modern consumer‑leaning footprint, with a reasonable spread across form factors.

### D6. IP type mix is extremely residential‑heavy
1. `RESIDENTIAL` **96.27%** dominates; `CORPORATE` **1.95%**, `MOBILE` **1.00%**, other categories <1%.  
   This is a strong residential posture. If your synthetic world should include substantial corporate or mobile traffic, this is likely too skewed.

### D7. Link roles are single‑mode (no sharing semantics)
1. Device links are **only** `PRIMARY_OWNER` (100% of links).  
2. IP links are **only** `TYPICAL_DEVICE_IP`.  
   This indicates **no secondary ownership or shared‑device semantics**, which can reduce realism if you expect household sharing, fleet devices, or merchant/shared terminals.

### D8. Interpretation for realism
1. **Strength:** device/IP graph is structurally clean and ownership counts are plausible.  
   The party‑level device distribution fits a believable consumer footprint and avoids graph‑integrity noise.
2. **Posture:** linkage is party‑only, IP sharing has an extreme tail, and IP‑per‑device is tightly capped.  
   This creates a graph that is easy to explain but less realistic in settings where devices roam and link to multiple accounts.
3. **Realism impact:** the graph is coherent but policy‑rigid.  
   Realism would improve with account‑level device links, richer link roles, and a less extreme IP‑sharing tail so that shared‑device and shared‑IP signals are not artificially amplified.

---

## E) Cross‑layer consistency (S1–S4)

### E1. Coverage chain across layers
1. Parties with accounts: **99.29%** (3,258,009 / 3,281,174).  
2. Accounts with instruments: **70.78%** (6,176,060 / 8,725,420).  
3. Parties with devices: **94.59%** (3,103,813 / 3,281,174).  
4. Devices with IP links: **14.82%** (1,076,116 / 7,263,186).  

Interpretation:
1. The **party→account** coverage is near‑total (expected).  
2. **Account→instrument** coverage is partial by design (savings/loan likely un‑instrumented).  
3. **Device→IP linkage is sparse**, implying that most devices do not have IP associations.  
   If IPs were meant to represent typical device endpoints, this is too low; if they represent only salient/high‑risk endpoints, it is plausible. The choice determines how much IP‑based features can contribute to realism.

### E2. Foreign‑key integrity is clean
1. Accounts referencing missing parties: **0**  
2. Instruments referencing missing accounts: **0**  
3. Instrument links referencing missing accounts/instruments: **0**  
4. Device links referencing missing parties: **0**  
5. IP links referencing missing devices/IPs: **0**  

This is excellent structural coherence and a strong realism prerequisite.

### E3. Derived ratios (scale posture)
1. Accounts per party (avg): **2.659**  
2. Instruments per account (avg): **1.227**  
3. Devices per party (avg): **2.214**  
4. IPs per device (avg): **0.0504**  

Interpretation:
1. The averages are consistent with earlier distributions.  
2. The IPs‑per‑device average is extremely low, which is consistent with the low device→IP coverage in E1.  
   This effectively makes IPs a sparse overlay, not a universal attribute; downstream models will treat IPs as “special” rather than standard metadata.

### E4. Interpretation for realism
1. **Strength:** cross‑layer joins are clean and deterministic; no orphan references.  
   This reduces noise in model training and makes errors easier to diagnose.
2. **Posture:** IP linkage is intentionally sparse.  
   That means IP‑based features will be present for a minority of devices and may carry outsized weight.
3. **Realism impact:** the chain is coherent, but the device→IP sparsity should be confirmed as intended rather than accidental.  
   If it is accidental, IP realism will be the dominant weak spot in 6A/6B.

---

## F) Fraud posture realism (S5)

### F1. Role proportions are plausible but strongly policy‑driven
1. Party roles: `CLEAN` **94.95%**, `MULE` **2.45%**, `SYNTHETIC_ID` **2.03%**, `ORGANISER` **0.30%**, `ASSOCIATE` **0.27%**.  
2. Account roles: `CLEAN_ACCOUNT` **97.92%**, `HIGH_RISK_ACCOUNT` **1.21%**, `MULE_ACCOUNT` **0.55%**, `DORMANT_RISKY` **0.32%**.  
3. Device roles: `CLEAN_DEVICE` **96.93%**, `HIGH_RISK_DEVICE` **2.49%**, `REUSED_DEVICE` **0.58%**.  
4. IP roles: `SHARED_IP` **88.01%**, `HIGH_RISK_IP` **9.47%**, `CLEAN_IP` **2.52%**.  
5. Merchant roles (n=1,238): `NORMAL` **99.27%**, `HIGH_RISK_MCC` **0.40%**, `COLLUSIVE` **0.32%**.  

Interpretation: this is a **low‑fraud‑prevalence posture** with a large clean base.  
That is plausible for a retail‑heavy bank, but the IP role mix is unusually skewed toward `SHARED_IP` with very little `CLEAN_IP`. If “shared IP” is treated as risky, this will inflate network risk signals; if it is meant to be benign, the label vocabulary may need adjustment.

### F2. Risk tiers discriminate by party role (good realism signal)
Risk tier distribution by role shows strong separation:
1. `ORGANISER`: **63.6% HIGH**, 26.2% ELEVATED, 10.1% STANDARD  
2. `SYNTHETIC_ID`: **53.1% HIGH**, 33.3% ELEVATED, 13.0% STANDARD  
3. `MULE`: **50.6% HIGH**, 35.4% ELEVATED, 13.4% STANDARD  
4. `ASSOCIATE`: **47.2% HIGH**, 37.1% ELEVATED  
5. `CLEAN`: **51.9% STANDARD**, 24.4% ELEVATED, 13.5% LOW, 10.2% HIGH  

This is internally coherent: risky roles skew high/elevated, while clean parties are mostly standard/low.

### F3. Party role is almost uniform across retail segments
For the top retail segments, role shares are nearly identical:
1. `CLEAN` ≈ **94.85–94.95%**  
2. `MULE` ≈ **2.44–2.50%**  
3. `SYNTHETIC_ID` ≈ **2.04–2.07%**  

Interpretation: there is **no segment‑specific fraud skew**.  
If we expect certain segments (e.g., students or value cohorts) to be more fraud‑exposed, this uniformity will suppress realistic segment‑level signals and reduce explainability in downstream models.

### F4. Account roles are nearly independent of party roles
Non‑clean account share by owner role:
1. `ORGANISER`: **2.17%**  
2. `SYNTHETIC_ID`: **2.11%**  
3. `CLEAN`: **2.08%**  
4. `ASSOCIATE`: **2.07%**  
5. `MULE`: **2.05%**  

Interpretation: account risk labels are **essentially flat** across owner fraud roles.  
That means the model will not see a strong “risky party → risky account” pathway, which is often a core realism feature. If mule/synthetic parties should propagate risk, this coupling needs to be strengthened.

### F5. Device roles are also almost independent of party roles
Non‑clean device share by owner role:
1. `ASSOCIATE`: **3.08%**  
2. `CLEAN`: **3.07%**  
3. `MULE`: **3.04%**  
4. `SYNTHETIC_ID`: **3.03%**  
5. `ORGANISER`: **2.92%**  

Interpretation: devices are **not more risky** for risky parties.  
This weakens “risk propagation” realism and will make device‑risk features less informative in downstream fraud detection.

### F6. Account roles vary by account type, but only modestly
High‑risk account share by type (top retail types):
1. `RETAIL_CREDIT_CARD_*`: **~1.76%**  
2. `RETAIL_CURRENT_*`: **~1.10%**  
3. `RETAIL_SAVINGS_*`: **~0.87%**  

Interpretation: credit accounts are slightly riskier than current/savings, which is plausible, but the gradient is small.  
If product‑level risk differentiation is important for 6B realism, this gradient likely needs to be larger.

### F7. IP roles only weakly track high sharing
1. High‑risk IPs have higher mean degree (≈ **9.85** devices/IP) and the absolute max (6,114 devices).  
2. But the **top‑1% degree IPs** are **89.0% SHARED**, **8.5% HIGH_RISK**, **2.4% CLEAN** — almost identical to overall shares.  

Interpretation: risk labels are not strongly concentrated in the high‑sharing tail, except at the absolute extreme.  
This means “shared IP” does not systematically translate into “high‑risk IP,” which may reduce the realism of IP‑based risk signals.

### F8. Interpretation for realism
1. **Strength:** risk tiering is coherent and aligns with role severity.  
   This makes the fraud posture interpretable and consistent across entity types.
2. **Posture:** risk propagation across entities is weak and segment‑level fraud skew is minimal.  
   As a result, many fraud‑related signals are almost flat across segments and ownership hierarchies.
3. **Realism impact:** the posture is stable and explainable, but realism would improve if risky parties were more likely to own risky accounts/devices and if high‑sharing IPs skewed more strongly toward high‑risk labels.  
   That would create more realistic correlation structure for downstream fraud models to learn.

---

## G) Heavy‑tail & concentration diagnostics

### G1. Accounts per party are not highly concentrated
1. Top‑1% parties (by account count) hold **5.76%** of all accounts.  
2. The 99th percentile is **8 accounts**, so the “top‑1%” threshold is not extreme.  
3. HHI for accounts per party is **4.26e‑07**, which is extremely low.  

Interpretation: accounts are **broadly distributed**.  
The tail exists (max 136) but does not dominate the overall mass, which means extreme parties are rare enough that they should not overwhelm model training.

### G2. Instruments per party show similar mild concentration
1. Top‑1% parties hold **5.83%** of all instruments.  
2. The 99th percentile is **11 instruments**.  

Interpretation: the instrument tail is **noticeable but not dominant**.  
The max of 189 instruments is an outlier rather than a systemic concentration driver, but it should still be explained as a policy feature if it is intended.

### G3. Devices per party are also only mildly concentrated
1. Top‑1% parties hold **6.26%** of devices.  
2. The 99th percentile is **7 devices**.  

Interpretation: device ownership is broadly spread and does not look unnaturally concentrated.  
This suggests that device counts are not being driven by a small elite of parties.

### G4. Devices‑per‑IP is the concentration outlier
1. Top‑1% IPs hold **33.80%** of all device‑IP links.  
2. 99th percentile is **172 devices/IP**; 99.9th percentile **206**.  
3. Top‑N shares of device‑IP links:  
   Top 10 IPs **2.71%**, Top 50 **5.81%**, Top 100 **6.31%**, Top 500 **10.04%**.  
4. HHI for devices‑per‑IP is **0.000164**, far higher than the accounts HHI.  

Interpretation: the IP layer is **highly heavy‑tailed** and much more concentrated than any other surface.  
This will dominate “shared IP” signals unless it is intentionally capped or counter‑balanced by other features.

### G5. Interpretation for realism
1. **Strength:** accounts, instruments, and devices are diffuse; no unnatural elite concentration.  
   This keeps the entity world from being dominated by a tiny fraction of hyper‑active actors.
2. **Posture:** IP sharing is the only extreme concentration hotspot.  
   The network layer behaves very differently from the rest of the entity surfaces.
3. **Realism impact:** the main realism risk in 6A is IP tail heaviness; if that is intentional (e.g., carrier‑grade NAT), it should be documented as such.  
   Otherwise, it will create an exaggerated shared‑IP signal compared to other synthetic dimensions.

---

## H) Policy targets vs observed outcomes

This section compares **design priors** in `config/layer3/6A/priors/*.yaml` to observed distributions. Where the policy is explicit, we check alignment. Where the implementation uses simplified vocabularies, we flag that direct comparison is not possible.

### H1. Segmentation priors are matched almost exactly
1. **Region→party type mix** is effectively exact: observed shares differ from priors by ~1e‑5 per region/party‑type.  
2. **Segment mix within region+party_type** shows tiny L1 distances (max ~0.0014).  
3. **Overall party_type share** matches the prior‑weighted expectation (differences on the order of 1e‑6).  

Interpretation: S1 is essentially **sampling directly from priors** with almost no drift.  
This explains the uniformity seen in A: geographic and segment variation is policy‑fixed rather than emergent. It also means that any realism issues here are policy issues, not sampling noise.

### H2. Product‑mix priors match observed account type shares
Using `product_mix_priors_6A` base lambdas (normalized):
1. Observed account‑type shares by party_type are **very close** to target.  
2. Largest deviations are ~0.02 absolute share (mostly in OTHER accounts).  

Interpretation: account mix is **faithfully policy‑driven**.  
The uniformity noted in B is therefore expected: segment‑level tilt is minor compared to the base mix, so most parties look similar within a party type.

### H3. Account‑per‑party caps are **violated**
`account_per_party_priors_6A` defines **K_max** per account type, but the data exceeds these caps for many types. Examples:
1. `RETAIL_CREDIT_CARD_STANDARD`: K_max **4**, observed max **79**, **25,163** parties exceed.  
2. `RETAIL_SAVINGS_INSTANT`: K_max **4**, observed max **70**, **23,495** parties exceed.  
3. `RETAIL_PERSONAL_LOAN_UNSECURED`: K_max **2**, observed max **23**, **9,434** parties exceed.  
4. `BUSINESS_CREDIT_CARD`: K_max **5**, observed max **135**, **382** parties exceed.  

Interpretation: either the cap is not enforced in the generator, or per‑party aggregation is not aligned with the cap semantics.  
This is a **material policy mismatch** because it changes the tail behavior of account holdings and can inflate downstream risk signals.

### H4. Instrument mix composition matches priors, but totals do not
1. **Instrument‑type shares within each account type** align extremely closely with `instrument_mix_priors_6A` (L1 distances ~1e‑5).  
2. **Instrument counts per account type** are **higher than lambda_total targets** for several types. Examples:  
   - `RETAIL_SAVINGS_INSTANT`: expected **0.45**, observed **1.00**  
   - `RETAIL_SAVINGS_FIXED`: expected **0.25**, observed **1.00**  
   - `RETAIL_PERSONAL_LOAN_UNSECURED`: expected **0.20**, observed **1.00**  
   - `BUSINESS_TERM_LOAN`: expected **0.20**, observed **1.00**  

Interpretation: the **composition** is correct, but the **absolute instrument count** is inflated (likely because each account is forced to have at least one bank‑rail instrument).  
This is a policy mismatch that should be documented or corrected, because it makes instrument totals look “too complete” relative to the intended lambda targets.

### H5. Device priors are mostly respected
1. Mean devices per party type vs base targets:  
   - `RETAIL`: **2.32** vs target **2.2**  
   - `BUSINESS`: **2.99** vs target **2.8**  
   - `OTHER`: **2.08** vs target **1.6**  
2. Device type mix by party_type matches base priors extremely closely (L1 ~1e‑5).  

Interpretation: device counts are slightly higher than base targets but **very close**, and type mix is faithful to policy.  
This suggests the device priors are applied correctly and any deviation is likely due to segment tilts rather than implementation errors.

### H6. IP priors diverge sharply from observations
1. **IPs per device by group**: expected non‑zero IPs for most device groups, but observed means are **0** for `CONSUMER_MOBILE`, `CONSUMER_COMPUTER`, and `SERVER_BACKEND`. Only `COMPUTER_PORTABLE` (laptops) and `IOT_OTHER` match expected lambdas.  
2. **IP type mix**: expected residential share ≈ **0.38**, observed **0.96**. All other IP types are far below targets (by 0.02–0.29 absolute share).  

Interpretation: IP generation is **not following the priors**.  
This is the largest policy mismatch in 6A and is likely responsible for the extreme residential dominance and sparse device→IP linkage. It also explains the heavy‑tail concentration in the IP layer.

### H7. Party role priors: clean share is within target, but caps are breached
1. Clean share by party_type is **within the realism target ranges**.  
2. **Cap violations** against `party_role_priors_6A.max_role_share_caps`:  
   - `ORGANISER` observed **0.296%** vs cap **0.10%**  
   - `SYNTHETIC_ID` observed **2.03%** vs cap **2.00%**  

Interpretation: global role proportions are close but **not fully policy‑compliant**.  
If caps are meant to be hard, this is a spec violation; if they are soft, the caps should be documented as guidelines rather than constraints.

### H8. Device/IP role vocabularies do not match priors
Observed roles use simplified vocabularies (`CLEAN_DEVICE`, `REUSED_DEVICE`, `HIGH_RISK_DEVICE` and `SHARED_IP`, `CLEAN_IP`, `HIGH_RISK_IP`).  
Policy vocabularies in priors are richer (e.g., `BOT_LIKE_DEVICE`, `PUBLIC_SHARED_IP`, `CORPORATE_NAT_IP`, `NORMAL_IP`).  

Interpretation: **direct policy‑vs‑outcome comparison is not possible** for device/IP roles without a mapping layer.  
This is an implementation simplification that should be documented as a design deviation, because it hides which risk semantics were intended by the richer vocabulary.

### H9. Interpretation for realism
1. **Strong alignment:** segmentation, product mix, and instrument‑type composition match priors almost exactly.  
   This means most of the population and product surfaces are behaving exactly as designed.
2. **Material mismatches:** account‑type K_max caps, instrument totals, and IP priors (counts + type mix).  
   These mismatches are large enough to change tail behavior and network realism.
3. **Design deviation:** device/IP role vocabularies are simplified, so policy targets cannot be directly enforced.  
   This reduces traceability from policy intent to observed risk labels.

Overall, 6A is **highly policy‑driven** where the priors are used, but there are **clear gaps** where priors are not applied or are overridden by implementation mechanics.

---

## Final realism grade — Segment 6A

**Grade: B‑**

### Why this grade (strengths)
1. **Structural integrity is excellent.**  
   Party, account, instrument, device, and IP tables join cleanly with no orphan links. This gives a reliable backbone for 6B and prevents “data quality” artifacts from contaminating realism judgments.
2. **Policy alignment is strong for core identity and product mix.**  
   Region→party‑type mix, segment mix, and account mix match priors almost exactly. Instrument **composition** per account type also matches the priors closely, which makes the product surface explainable.
3. **Distributions are stable and interpretable.**  
   Accounts, instruments, and devices are diffuse (no extreme concentration outside the IP layer), which is a plausible synthetic posture and avoids an unrealistic elite‑dominance effect.

### Why it is not higher (gaps)
1. **IP layer deviates sharply from priors.**  
   IP type mix is far from target (residential ~96% observed vs ~38% expected), device→IP linkage is sparse (14.8% coverage), and device‑per‑IP is extremely heavy‑tailed. This creates a dominant, likely unrealistic, network signal that can overwhelm other realism cues.
2. **Account cap violations are widespread.**  
   Many account types exceed their K_max caps by large margins. This suggests enforcement issues or a mismatch between policy semantics and implementation, and it inflates heavy‑tail behavior in holdings.
3. **Risk propagation is weak.**  
   Fraud roles do not materially increase risky accounts/devices. Segment‑specific fraud skew is minimal. This reduces explainability of fraud posture downstream because risk does not “flow” along ownership edges.
4. **Role vocabularies are simplified vs priors.**  
   Device/IP roles used in data do not align with the richer policy vocabulary, blocking direct policy‑to‑data validation and reducing the nuance of network‑risk labels.

### What would move this to B / B+ / A‑
1. **Fix IP realism against priors.**  
   Bring IP type mix and device→IP linkage rates closer to `ip_count_priors_6A`, and reduce extreme device‑per‑IP tails unless explicitly intended. This will make IP features representative rather than dominant anomalies.
2. **Enforce or redefine account K_max.**  
   Either cap per‑party account counts as specified or update the priors to reflect the intended tail. This will improve account realism and prevent policy drift in account holdings.
3. **Strengthen risk propagation.**  
   Make risky parties meaningfully more likely to own risky accounts/devices and ensure high‑sharing IPs skew toward high‑risk labels. This improves realism and model explainability by restoring causal‑looking chains.
4. **Align role vocabularies (or document mapping).**  
   Either use the richer role vocabularies from priors or define a formal mapping so policy targets can be validated. Without that, risk labels cannot be audited against intent.
