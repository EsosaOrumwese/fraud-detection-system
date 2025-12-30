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
* `{ op: "CHANNEL_IN", values: ["CP","CNP"] }`
* `{ op: "MCC_IN", codes: ["7995","4829"], ranges: ["5000-5999"] }`
* `{ op: "N_GE", value: 2 }`
* `{ op: "AND", args: [<predicate>, ...] }`
* `{ op: "OR",  args: [<predicate>, ...] }`
* `{ op: "NOT", arg: <predicate> }`

All operations must be evaluated deterministically; numeric comparisons follow the engine numeric regime (binary64/RNE/FMA-off). 

---

## 8) Minimal v1 file (Codex can author verbatim)

> **Note:** this minimal file is sufficient for plumbing/validation, but it is **not** a production-realistic country policy. Treat it as a starter template and expand the country sets + rules for realism before you rely on synthetic outputs.

```yaml
precedence_order: ["DENY","ALLOW","CLASS","LEGAL","THRESHOLD","DEFAULT"]

reason_codes:
  - "DENY_SANCTIONED"
  - "ALLOW_GLOBAL"
  - "DEFAULT_DENY"

filter_tags:
  - "ADMISSIBLE"
  - "HOME"
  - "SANCTIONED"

country_sets:
  SANCTIONED: ["IR","KP","RU"]
  GLOBAL_CORE: ["AE","CA","CH","DE","FR","GB","NL","SG","US"]

# Closed mapping needed by S3.3: reason_code -> rule_id
reason_code_to_rule_id:
  DENY_SANCTIONED: "RL_DENY_SANCTIONED"
  ALLOW_GLOBAL:    "RL_ALLOW_GLOBAL"
  DEFAULT_DENY:    "RL_DEFAULT_DENY"

rules:
  - rule_id: "RL_DENY_SANCTIONED"
    precedence: "DENY"
    priority: 10
    is_decision_bearing: true
    predicate:
      op: "IN_SET"
      field: "home_country_iso"
      set: "SANCTIONED"
    outcome:
      reason_code: "DENY_SANCTIONED"
      tags: ["SANCTIONED"]

  - rule_id: "RL_ALLOW_GLOBAL"
    precedence: "ALLOW"
    priority: 100
    is_decision_bearing: true
    predicate: { op: "TRUE" }
    outcome:
      reason_code: "ALLOW_GLOBAL"
      tags: ["ADMISSIBLE"]
    admit_sets: ["GLOBAL_CORE"]
    deny_sets: ["SANCTIONED"]
    row_tags: ["ADMISSIBLE"]

  # Mandatory terminal DEFAULT (exactly one, decision-bearing, guaranteed to fire)
  - rule_id: "RL_DEFAULT_DENY"
    precedence: "DEFAULT"
    priority: 999999
    is_decision_bearing: true
    predicate: { op: "TRUE" }
    outcome:
      reason_code: "DEFAULT_DENY"
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

- Replace any placeholder country sets with the real allow/deny lists and cite their source.
- Replace placeholder rule IDs and ordering with the final ladder order.
- Replace any TODO reason codes or tags with the closed enum values in the policy.

