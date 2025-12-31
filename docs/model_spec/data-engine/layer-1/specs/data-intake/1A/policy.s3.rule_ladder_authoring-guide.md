# Authoring Guide — `policy.s3.rule_ladder.yaml` (S3 rule ladder + candidate admission authority)

This policy is the **only authority** for **S3.1 (rule ladder)** and drives **S3.2 (candidate universe)** and **S3.3 (ordering key reconstruction)**. It is **deterministic**, has **closed vocabularies**, and must include a **terminal DEFAULT** decision rule. 

---

## 1) File identity (binding)

* **Registry id:** `policy.s3.rule_ladder.yaml`
* **Path:** `config/policy/s3.rule_ladder.yaml` 
* **Governance:** must be opened atomically with other S3 authorities and must be part of the run's sealed inputs; changing bytes must be treated as a policy change (new lineage). 

---

### 1.1 Realism bar (MUST)

As an authored policy, this MUST not remain in a toy state:

* At least one admit-bearing rule SHOULD admit a **non-trivial** foreign candidate set for eligible merchants (so S6/S7 have real work to do), while still allowing domestic-only merchants.
* Any set like `SANCTIONED` / `HIGH_RISK` SHOULD be derived from a pinned external source and frozen to a dated vintage (do not hard-code a tiny hand list unless it is explicitly a placeholder and clearly marked as such).
* This policy SHOULD be kept broadly coherent with S0's `crossborder_hyperparams.yaml` gating: large systematic disagreements should be treated as a realism defect unless explicitly intended.

If no external country-set source is wired yet, `country_sets` may be authored directly for v1, but the file MUST include a clear provenance note (e.g., a top comment block) stating `source=authored` and a `vintage` date for each such set.

---

## 2) What this file must contain (binding minimum)

### 2.1 Closed vocabularies (MUST)

* `reason_codes[]` — closed set (any unknown reason code ⇒ FAIL). 
* `filter_tags[]` — closed set (any unknown tag ⇒ FAIL). 
  *Must include `"HOME"` because S3.2 always tags the home row with `"HOME"`. *

### 2.2 Precedence is a total order (MUST)

Define an explicit total order over:
`DENY, ALLOW, CLASS, LEGAL, THRESHOLD, DEFAULT`
This must be treated as the **precedence order** used for stable `rule_trace` ordering and for `precedence_rank()` in S3.3 ordering keys.

### 2.3 Named country sets (MAY, but required if referenced)

A dictionary of named ISO2 sets (e.g., `SANCTIONED`, `EEA`, `WHITELIST_X`). Any set referenced by a **fired** rule must exist and must expand only to ISO2 codes (else FAIL).

### 2.4 Rules array (MUST)

`rules[]` is ordered (but trace ordering is **by precedence+priority+rule_id**, not evaluation time). 
Each rule must include the required fields below.

---

## 3) Rule record shape (binding)

Each `rules[]` element MUST have these fields: 

* `rule_id` (ASCII `[A-Z0-9_]+`, unique)
* `precedence` ∈ `{DENY, ALLOW, CLASS, LEGAL, THRESHOLD, DEFAULT}`
* `priority` (int; lower wins within same precedence)
* `is_decision_bearing` (bool)
* `predicate` (deterministic boolean expression; no RNG / no host state)
* `outcome.reason_code` (member of closed `reason_codes[]`)
* `outcome.tags` (optional array; members of closed `filter_tags[]`)

### 3.1 Admit/Deny directives (required for S3.2 usefulness)

Rules MAY additionally carry **country-level** admit/deny directives used by S3.2:

* `admit_countries[]` and/or `admit_sets[]`
* `deny_countries[]` and/or `deny_sets[]`
* `row_tags[]` (optional; tags to apply to the **candidate rows** admitted by this rule; must be in `filter_tags[]`)

**Scope rule:** admit/deny operates at **country-level only**. 

---

## 4) Decision law (binding)

### 4.1 Fired set

Evaluate **all** predicates; collect `Fired = { r : predicate(r)==true }`. 

### 4.2 Eligibility decision (`eligible_crossborder`)

* If any `DENY` fires ⇒ `eligible_crossborder = false` (decision source = first decision-bearing `DENY`)
* Else if any `ALLOW` fires ⇒ `eligible_crossborder = true` (decision source = first decision-bearing `ALLOW`)
* Else decision comes from `{CLASS, LEGAL, THRESHOLD, DEFAULT}` using the same “first decision-bearing under precedence+priority+rule_id” rule. 

### 4.3 Mandatory DEFAULT terminal

The artefact MUST include **exactly one** `DEFAULT` rule with `is_decision_bearing=true` that **always fires** (or is guaranteed to catch the remainder). 

### 4.4 Trace ordering

`rule_trace` must list **all fired rules** ordered by:
`(precedence order, priority asc, rule_id asc)` and must mark exactly one `is_decision_source=true`. 

---

## 5) Candidate universe law (S3.2) that the file must support

When `eligible_crossborder == true`, S3.2 forms:

* `ADMITS` = union over fired rules of `admit_countries` + expansions of `admit_sets`
* `DENIES` = union over fired rules of `deny_countries` + expansions of `deny_sets` (this is where `SANCTIONED` etc typically live)
* `FOREIGN = (ADMITS \ DENIES) \ {home}`
* `C = {home} ∪ FOREIGN`

Row tagging requirements:

* Home row always gets `filter_tags += ["HOME"]` and includes the **decision source** reason for traceability. 
* Foreign rows must receive deterministic unions of:

  * `merchant_tags` (union of fired `outcome.tags`)
  * `row_tags` from the admit-bearing fired rules that admitted that country
  * `reason_codes` from the admit-bearing fired rules that justified inclusion
    with **A→Z stable ordering** in each emitted array.

---

## 6) Ordering-key reconstruction law (S3.3) the file must support

S3.3 cannot “guess” why a country was admitted. It needs a **closed mapping** from row `reason_codes[]` to the admitting rule ids. If this mapping is missing, S3 fails ordering as **KEY_UNDEFINED / UNSTABLE**.

**Therefore, this policy file MUST provide one of:**

* A one-to-one mapping `reason_code → rule_id`, **and** ensure every admitted foreign row includes at least one reason code that maps to an **admit-bearing** fired rule; **or**
* An explicit per-row `admit_rule_ids[]` mechanism (if you choose that design).

The ordering key per foreign row is then built from:
`K(r)=⟨precedence_rank(r), priority(r), rule_id⟩` and `Key1(i)=min_lex K(r)` over the admitting rules for that row.

---

## 7) Predicate representation (PINNED for Codex, so no guessing)

Use a small structured DSL (no string eval):

Supported forms:

* `{ op: "TRUE" }`
* `{ op: "IN_SET", field: "home_country_iso", set: "<COUNTRY_SET_NAME>" }`
* `{ op: "CHANNEL_IN", values: ["card_present","card_not_present"] }`
* `{ op: "MCC_IN", codes: ["7995","4829"], ranges: ["5000-5999"] }`
* `{ op: "N_GE", value: 2 }`
* `{ op: "AND", args: [<predicate>, ...] }`
* `{ op: "OR",  args: [<predicate>, ...] }`
* `{ op: "NOT", arg: <predicate> }`

All operations must be evaluated deterministically; numeric comparisons follow the engine numeric regime (binary64/RNE/FMA-off). 

---

## 8) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

> **Note:** this minimal file is sufficient for plumbing/validation, but it is **not** a production-realistic country policy. Treat it as a starter template and expand the country sets + rules for realism before you rely on synthetic outputs.

```yaml
# config/policy/s3.rule_ladder.yaml
# Authority: S3.1 rule ladder + S3.2 candidate admission + S3.3 ordering-key reconstruction (deterministic).
#
# Provenance / vintages
# - SANCTIONED / HIGH_RISK: authored-for-simulation placeholders (NOT an authoritative real-world list), vintage=2025-01-01.
# - GDP_PC_BUCKET_GE{3,4}_2024: derived offline from gdp_bucket_map_2024 (method=jenks, k=5, source_year=2024).
# - ISO2 validity checked against iso3166_canonical_2024.
# - Channel values follow schemas.ingress.layer1.yaml#/merchant_ids: {card_present, card_not_present}.
#
precedence_order:
- DENY
- ALLOW
- CLASS
- LEGAL
- THRESHOLD
- DEFAULT
reason_codes:
- DENY_HOME_SANCTIONED
- ALLOW_CNP_DIGITAL
- ALLOW_TRAVEL_TRANSPORT
- CLASS_HOME_HUB_JURISDICTION
- GEO_HOME_EEA_REGIONAL
- GEO_HOME_USMCA_REGIONAL
- GEO_HOME_ASEAN_REGIONAL
- GEO_HOME_GCC_REGIONAL
- THRESHOLD_LARGE_CHAIN
- DEFAULT_DOMESTIC_ONLY
filter_tags:
- ADMISSIBLE
- BIG_MARKET
- CNP
- DIGITAL
- FIN_HUB
- GEO
- HOME
- HUB_HOME
- LARGE_CHAIN
- REGIONAL_ASEAN
- REGIONAL_EEA
- REGIONAL_GCC
- REGIONAL_NA
- SANCTIONED
- TRAVEL
country_sets:
  SANCTIONED:
  - BY
  - CU
  - IR
  - KP
  - RU
  - SD
  - SY
  HIGH_RISK:
  - AF
  - IQ
  - LY
  - SO
  - SS
  - VE
  - YE
  HUB_JURISDICTIONS:
  - AD
  - AE
  - BM
  - GG
  - GI
  - HK
  - IM
  - JE
  - KY
  - LI
  - MC
  - MO
  - SG
  - TC
  - VG
  - 'NO'
  FINANCIAL_HUBS:
  - AE
  - AU
  - BE
  - CA
  - CH
  - DE
  - DK
  - FR
  - GB
  - HK
  - IE
  - JP
  - LU
  - NL
  - 'NO'
  - SE
  - SG
  - US
  BIG_MARKETS:
  - AU
  - BR
  - CA
  - CN
  - DE
  - ES
  - FR
  - GB
  - ID
  - IN
  - IT
  - JP
  - KR
  - MX
  - NL
  - PL
  - SA
  - SE
  - TH
  - TR
  - US
  EEA_UK_CH:
  - AT
  - BE
  - BG
  - CH
  - CY
  - CZ
  - DE
  - DK
  - EE
  - ES
  - FI
  - FR
  - GB
  - GR
  - HR
  - HU
  - IE
  - IS
  - IT
  - LI
  - LT
  - LU
  - LV
  - MT
  - NL
  - 'NO'
  - PL
  - PT
  - RO
  - SE
  - SI
  - SK
  USMCA:
  - CA
  - MX
  - US
  ASEAN:
  - BN
  - ID
  - KH
  - LA
  - MM
  - MY
  - PH
  - SG
  - TH
  - VN
  GCC:
  - AE
  - BH
  - KW
  - OM
  - QA
  - SA
  GDP_PC_BUCKET_GE3_2024:
  - AD
  - AE
  - AT
  - AU
  - BE
  - BM
  - CA
  - CH
  - DE
  - DK
  - FI
  - FO
  - FR
  - GB
  - HK
  - IE
  - IL
  - IS
  - LU
  - MC
  - 'NO'
  - NZ
  - SE
  - SG
  - TC
  - US
  - CW
  - MO
  - SM
  GDP_PC_BUCKET_GE4_2024:
  - BM
  - CH
  - IE
  - LU
  - MC
  - 'NO'
reason_code_to_rule_id:
  DENY_HOME_SANCTIONED: RL_DENY_HOME_SANCTIONED
  ALLOW_CNP_DIGITAL: RL_ALLOW_CNP_DIGITAL
  ALLOW_TRAVEL_TRANSPORT: RL_ALLOW_TRAVEL_TRANSPORT
  CLASS_HOME_HUB_JURISDICTION: RL_CLASS_HOME_HUB_JURISDICTION
  GEO_HOME_EEA_REGIONAL: RL_GEO_HOME_EEA_REGIONAL
  GEO_HOME_USMCA_REGIONAL: RL_GEO_HOME_USMCA_REGIONAL
  GEO_HOME_ASEAN_REGIONAL: RL_GEO_HOME_ASEAN_REGIONAL
  GEO_HOME_GCC_REGIONAL: RL_GEO_HOME_GCC_REGIONAL
  THRESHOLD_LARGE_CHAIN: RL_THRESHOLD_LARGE_CHAIN
  DEFAULT_DOMESTIC_ONLY: RL_DEFAULT_DOMESTIC_ONLY
rules:
- rule_id: RL_DENY_HOME_SANCTIONED
  precedence: DENY
  priority: 10
  is_decision_bearing: true
  predicate:
    op: IN_SET
    field: home_country_iso
    set: SANCTIONED
  outcome:
    reason_code: DENY_HOME_SANCTIONED
    tags:
    - SANCTIONED

- rule_id: RL_ALLOW_CNP_DIGITAL
  precedence: ALLOW
  priority: 100
  is_decision_bearing: true
  predicate:
    op: AND
    args:
    - op: CHANNEL_IN
      values:
      - card_not_present
    - op: MCC_IN
      codes:
      - '5815'
      - '5816'
      - '5817'
      - '5818'
      ranges:
      - 4810-4899
      - 5960-5969
  outcome:
    reason_code: ALLOW_CNP_DIGITAL
    tags:
    - ADMISSIBLE
    - CNP
    - DIGITAL
  admit_sets:
  - BIG_MARKETS
  - FINANCIAL_HUBS
  - GDP_PC_BUCKET_GE3_2024
  deny_sets:
  - SANCTIONED
  - HIGH_RISK
  row_tags:
  - ADMISSIBLE
  - BIG_MARKET
  - FIN_HUB

- rule_id: RL_ALLOW_TRAVEL_TRANSPORT
  precedence: ALLOW
  priority: 200
  is_decision_bearing: true
  predicate:
    op: MCC_IN
    codes:
    - '4511'
    - '4722'
    - '7011'
    - '7012'
    - '4111'
    - '4121'
    - '4131'
    - '4411'
    - '4582'
    - '4789'
    ranges:
    - 3000-3999
  outcome:
    reason_code: ALLOW_TRAVEL_TRANSPORT
    tags:
    - ADMISSIBLE
    - TRAVEL
  admit_sets:
  - EEA_UK_CH
  - USMCA
  - ASEAN
  - GCC
  - BIG_MARKETS
  - FINANCIAL_HUBS
  deny_sets:
  - SANCTIONED
  - HIGH_RISK
  row_tags:
  - ADMISSIBLE
  - TRAVEL

- rule_id: RL_CLASS_HOME_HUB_JURISDICTION
  precedence: CLASS
  priority: 10
  is_decision_bearing: true
  predicate:
    op: IN_SET
    field: home_country_iso
    set: HUB_JURISDICTIONS
  outcome:
    reason_code: CLASS_HOME_HUB_JURISDICTION
    tags:
    - HUB_HOME
  admit_sets:
  - FINANCIAL_HUBS
  - BIG_MARKETS
  - GDP_PC_BUCKET_GE3_2024
  deny_sets:
  - SANCTIONED
  - HIGH_RISK
  row_tags:
  - ADMISSIBLE
  - FIN_HUB
  - HUB_HOME

- rule_id: RL_GEO_HOME_EEA_REGIONAL
  precedence: LEGAL
  priority: 10
  is_decision_bearing: false
  predicate:
    op: IN_SET
    field: home_country_iso
    set: EEA_UK_CH
  outcome:
    reason_code: GEO_HOME_EEA_REGIONAL
    tags:
    - GEO
    - REGIONAL_EEA
  admit_sets:
  - EEA_UK_CH
  deny_sets:
  - SANCTIONED
  - HIGH_RISK
  row_tags:
  - ADMISSIBLE
  - REGIONAL_EEA

- rule_id: RL_GEO_HOME_USMCA_REGIONAL
  precedence: LEGAL
  priority: 20
  is_decision_bearing: false
  predicate:
    op: IN_SET
    field: home_country_iso
    set: USMCA
  outcome:
    reason_code: GEO_HOME_USMCA_REGIONAL
    tags:
    - GEO
    - REGIONAL_NA
  admit_sets:
  - USMCA
  deny_sets:
  - SANCTIONED
  - HIGH_RISK
  row_tags:
  - ADMISSIBLE
  - REGIONAL_NA

- rule_id: RL_GEO_HOME_ASEAN_REGIONAL
  precedence: LEGAL
  priority: 30
  is_decision_bearing: false
  predicate:
    op: IN_SET
    field: home_country_iso
    set: ASEAN
  outcome:
    reason_code: GEO_HOME_ASEAN_REGIONAL
    tags:
    - GEO
    - REGIONAL_ASEAN
  admit_sets:
  - ASEAN
  deny_sets:
  - SANCTIONED
  - HIGH_RISK
  row_tags:
  - ADMISSIBLE
  - REGIONAL_ASEAN

- rule_id: RL_GEO_HOME_GCC_REGIONAL
  precedence: LEGAL
  priority: 40
  is_decision_bearing: false
  predicate:
    op: IN_SET
    field: home_country_iso
    set: GCC
  outcome:
    reason_code: GEO_HOME_GCC_REGIONAL
    tags:
    - GEO
    - REGIONAL_GCC
  admit_sets:
  - GCC
  deny_sets:
  - SANCTIONED
  - HIGH_RISK
  row_tags:
  - ADMISSIBLE
  - REGIONAL_GCC

- rule_id: RL_THRESHOLD_LARGE_CHAIN
  precedence: THRESHOLD
  priority: 10
  is_decision_bearing: true
  predicate:
    op: N_GE
    value: 20
  outcome:
    reason_code: THRESHOLD_LARGE_CHAIN
    tags:
    - ADMISSIBLE
    - LARGE_CHAIN
  admit_sets:
  - EEA_UK_CH
  - USMCA
  - ASEAN
  - GCC
  - BIG_MARKETS
  - FINANCIAL_HUBS
  - GDP_PC_BUCKET_GE3_2024
  deny_sets:
  - SANCTIONED
  - HIGH_RISK
  row_tags:
  - ADMISSIBLE
  - LARGE_CHAIN

- rule_id: RL_DEFAULT_DOMESTIC_ONLY
  precedence: DEFAULT
  priority: 999999
  is_decision_bearing: true
  predicate:
    op: TRUE
  outcome:
    reason_code: DEFAULT_DOMESTIC_ONLY
    tags: []

```

This satisfies:

* precedence total order and stable trace ordering 
* closed reason/tag sets 
* S3.2 admit/deny mechanics 
* S3.3 ordering-key mapping requirement 

---

## 9) Acceptance checklist (Codex must enforce)

* `precedence_order` contains exactly the 6 precedence classes (no duplicates).
* `reason_codes` and `filter_tags` are closed: every rule’s `outcome.reason_code` and tag appears in the corresponding list.
* `rules[].rule_id` unique; (precedence, priority, rule_id) defines a strict order within each precedence. 
* Exactly one `DEFAULT` rule, decision-bearing, guaranteed to fire. 
* Any referenced `country_set` exists and expands only to ISO2.
* `reason_code_to_rule_id` is total for all `reason_codes` and one-to-one.
* Every admit-bearing rule has at least one admit directive (`admit_countries` or `admit_sets`) so admitted foreign rows can reconstruct admission keys (or else S3.3 fails).

## Placeholder resolution (MUST)

- Replace placeholder `country_sets` with the real ISO2 sets and record their provenance.
- Replace placeholder `rule_id`, `precedence`, `priority`, and `predicate` with the final ladder.
- Ensure `reason_codes`, `filter_tags`, and any rule tags are the closed enums used at runtime.

