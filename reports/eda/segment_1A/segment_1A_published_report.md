# Segment 1A — Published Assessment Report (Human‑Readable)
Date: 2026-01-30
Run: `runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92`
Scope: `data/layer1/1A` outputs only (no RNG logs). No charts by request.

## 0) Why this report exists
Segment 1A is the **world‑building foundation** for the data engine. It creates the merchant/outlet universe and the scaffolding that later segments use to simulate transactions. Your goal is not “perfect reality,” but **credible realism**: outputs that feel plausible, structurally consistent, and rich enough to support reasonable fraud modeling and explanations.

This report translates the technical assessment into plain language and connects:
- **Design intent** → what 1A is supposed to represent.
- **Implementation interpretation** → how the design was translated into data.
- **Actual output** → what this run produced.
- **Realism grade** → how believable the results are for platform use.

## 1) Design intent in plain language (what 1A should represent)
1A should produce a **repeatable merchant/outlet universe** that feels like a global retail ecosystem:
- Merchants belong to countries and have **multiple outlets** (small shops, branches, locations).
- Most merchants are domestic; some are cross‑border (operate in multiple countries).
- The distribution should be **skewed**: many small merchants, a few giants with huge networks.
- There should be **policy‑driven controls**: eligibility flags, candidate sets, and gate receipts.
- Everything should be **auditable and deterministic** under a given seed and parameter hash.

## 2) Implementation interpretation (what the code actually committed to)
Key interpretation points that matter for realism:
- **S9 is the canonical validation publisher** (data is considered valid only after S9). This improves audit integrity.
- **Strict hashing and manifest fingerprints** mean outputs are tied to exact inputs; reproducibility is strong.
- **Eligibility scoping fixes** ensure “no foreign candidates” doesn’t accidentally mark a merchant as ineligible.
- **Counts parity logic** tolerates “implicit zeros” if certain count outputs are absent.

Implication for you: the data may be structurally valid even when some “approved” datasets are missing, but missing outputs **still reduce fidelity** to the design contract.

## 3) What this run actually produced (plain English inventory)
These are the 1A datasets present in this run and what they mean:
- **outlet_catalogue** → the master list of merchants and their outlets (core realism surface).
- **merchant_currency** → the primary currency assigned to each merchant.
- **s3_candidate_set** → for each merchant, which countries are considered as possible foreign expansion targets.
- **s3_base_weight_priors** → baseline weights that bias country selection.
- **crossborder_eligibility_flags** → which merchants are allowed to be cross‑border.
- **crossborder_features** → numeric features (e.g., openness) used in hurdle modeling.
- **hurdle_design_matrix** + **hurdle_pi_probs** → the “propensity” model for being multi‑site.
- **s6/membership** → actual assigned foreign‑country memberships.
- **validation and receipts** → pass/fail gate artifacts and sealing receipts.

Missing (approved but not present in data output):
- **s3_integerised_counts**
- **s3_site_sequence**
- **sparse_flag**
- **merchant_abort_log**
- **hurdle_stationarity_tests**

These missing items do not automatically break realism, but they **reduce auditability and fidelity** to the intended design contract.

## 4) What the numbers say (translated for humans)
### 4.1 Outlet distribution (how “retail‑like” the merchant universe feels)
- **Merchants:** 1,238 across **77 countries**
- **Outlets per merchant:** min 2, median 16, max 2,546
- **Country coverage per merchant:** min 1, median 1, max 11
- **Multi‑country merchants:** 37.4%
- **Outlet concentration:** top 10% of merchants hold ~46% of all outlets

**Interpretation:** This is a classic heavy‑tail distribution: most merchants are small, a few are huge. That’s realistic for retail ecosystems and a good realism signal.

### 4.1A Outlet catalogue integrity checks (core dataset deep‑dive)
These are **dataset‑level sanity checks** that tell us if the outlet universe is internally coherent and realistic:

- **Rows (outlet records):** 31,257  
- **Distinct site_id values:** 2,546  
- **Distinct merchant+site pairs:** 24,555  

**Interpretation:** There are more rows than unique merchant+site pairs, which means **duplicate merchant‑site pairs exist**. This is not necessarily wrong if the duplicates represent **different legal countries** or repeated assignments.

**Duplicate pair analysis:**
- About **12.7%** of merchant‑site pairs are duplicated.
- The duplicates differ primarily by **legal_country_iso** and **final_country_outlet_count**, while other columns stay constant.

**Interpretation:** This implies a single `site_id` can be reused across different legal countries for the same merchant. That can be acceptable **only if `site_id` is a per‑merchant index**, not a globally unique location ID. If downstream assumes site IDs are unique per country, this is a realism risk.

**Flag behavior:**
- `single_vs_multi_flag` is **True for every merchant**.
- Minimum outlets per merchant is **2** (no single‑site merchants).

**Interpretation:** This is a realism weakness. Real economies have many single‑site merchants, but this dataset has **zero**. If the flag truly means “multi‑site,” then we are over‑representing multi‑site merchants and under‑representing small businesses.

**Home vs legal country mismatch:**
- **~38.6%** of rows have `home_country_iso != legal_country_iso`.

**Interpretation:** That is a **high mismatch rate**. It could be realistic for large firms with offshore legal domicile, but for typical retail it is likely too high. This is another realism lever to adjust if you want “everyday merchant” realism.

**Internal consistency check:**
- For every `(merchant_id, legal_country_iso)` pair, **actual outlet rows exactly match `final_country_outlet_count`**.
- `site_order` is **contiguous** (no gaps) for all merchants.

**Interpretation:** The dataset is **internally coherent**. The realism concerns are about population shape (single‑site absence, high legal/home mismatch), not data integrity.

### 4.1B Outlet catalogue realism grade (core dataset)
**Grade: B‑ (Moderate realism, but skewed toward multi‑site/global behavior)**  

**Reasons for this grade:**
1) **Strong realism signals:** outlet distribution is heavy‑tailed (many small, few huge), and the dataset is internally consistent (counts match, site_order contiguous).  
2) **Major realism gap:** there are **zero single‑site merchants** (min outlets = 2; `single_vs_multi_flag` is True for all merchants). This is not realistic for everyday commerce.  
3) **High legal vs home mismatch (~38.6%)** suggests a world with unusually high offshore domicile behavior, which can be realistic for large firms but is too high for typical merchant populations.  
4) **Duplicate merchant‑site pairs (~12.7%)** are acceptable only if `site_id` is an internal per‑merchant index. If downstream assumes unique physical locations, this introduces ambiguity.  

**Summary:** The universe feels plausible in shape, but it over‑represents large/global merchants and under‑represents single‑site businesses. With single‑site inclusion and a lower home/legal mismatch, this could move to A‑ realism.

### 4.2 Candidate set breadth (how “globally open” merchants are)
- **Candidate countries per merchant:** min 1, median 38, max 39

**Interpretation:** Nearly every merchant has access to most countries. That feels **overly global**, and less realistic unless the simulated world is meant to be extremely international. This is a realism weakness because most merchants in real life are geographically constrained.

### 4.3 Cross‑border eligibility (policy gating realism)
- **Eligibility rate:** ~70.7%

**Interpretation:** Roughly 7 out of 10 merchants are eligible for cross‑border behavior. This is a plausible mix; it creates a meaningful distinction between eligible and ineligible populations.

### 4.4 Hurdle probabilities (likelihood of multi‑site behavior)
- **pi range:** ~0.00009 to 0.6797 (median ~0.142)

**Interpretation:** The model generates a spectrum of “propensity to be multi‑site.” The values are not extreme; most merchants are not forced into multi‑site behavior, which is realistic.

### 4.5 Cross‑border features (openness)
- **openness range:** ~0.02 to 0.53 (median ~0.19)

**Interpretation:** Openness scores sit in a plausible band, suggesting that merchants are not overwhelmingly global. However, because the candidate sets are huge, these openness scores are not constraining enough to counterbalance the global candidate universe.

### 4.6 Currency realism
- **Currencies:** 139 unique codes (from AED to ZWG)

**Interpretation:** Very strong signal of global coverage and variety. This is good realism for a global platform.

### 4.7 Foreign membership (actual assigned foreign countries)
- **Foreign countries per merchant:** min 1, median 2, max 12

**Interpretation:** This is believable: most cross‑border merchants expand to only a few countries. This partially offsets the “too global” candidate sets.

## 5) Where realism is strong vs weak
### Strong realism signals
- **Heavy‑tailed outlet distribution** (few giants, many small merchants).
- **Moderate multi‑country merchant share** (not everyone is global).
- **Hurdle probabilities are not extreme** (most merchants lean toward single‑site).
- **Currency diversity is high**, supporting global realism.

### Weak realism signals
- **Candidate sets are too broad** (median 38 out of 39 countries). This implies most merchants are “allowed” almost everywhere, which is uncommon in real economies.
- **Missing approved outputs** reduce traceability and make it harder to validate distributional assumptions (e.g., site sequencing and integerised counts).

## 6) Realism grade (1A only)
**Grade: B (Moderate realism)**

**Why:** The outputs are internally coherent and strongly skewed in a way that matches real merchant ecosystems. However, the **global candidate universe** is too permissive, and several approved data artifacts are missing. This puts the segment in a “credible but improvable” state.

## 7) What I would fix first (if realism is the priority)
1) **Constrain candidate sets** so most merchants only see regional or realistically reachable country targets.
2) **Emit s3_site_sequence and s3_integerised_counts** to make site‑level realism auditable.
3) **Ensure sparse_flag and hurdle_stationarity_tests** exist so distributional shape is validated and reproducible.

## 8) Bottom line for platform readiness
You can build v0 on this data, but expect **cross‑border behavior to feel more global than real life** unless you tighten candidate sets. If you want a platform demo that “feels real,” this is the first lever to adjust.
