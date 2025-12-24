# Authoring Guide — `config/allocation/s6_selection_policy.yaml` (S6 membership selection policy)

This file governs **1A.S6**: selecting which foreign candidate countries become members for a merchant, given:

* the ordered candidate set from **S3** (`s3_candidate_set` with `candidate_rank`)
* the target foreign count from **S4** (`K_target`, possibly 0)
* optional eligibility flags / sparse mode signals

Selection is RNG-driven (Gumbel keys), but the **policy** is deterministic and participates in `parameter_hash`.

---

## 1) File identity

* **Artefact id:** `s6_selection_policy`
* **Path:** `config/allocation/s6_selection_policy.yaml`
* **Governance:** sealed policy input → affects `parameter_hash`

---

## 2) What S6 needs this policy to define

S6 must deterministically construct, for each merchant:

1. **Selection domain**: which candidate rows are eligible for selection
2. **Sampling mechanism**: how to turn candidates into an ordered pick list, driven by RNG (`rng_event_gumbel_key`)
3. **Tie-breaks**: how to resolve equal keys deterministically (should be impossible in continuous, but must be defined)
4. **Failure behaviour**: what to do if `K_target > |eligible_foreign|` or if domain is empty

---

## 3) Required top-level structure (MUST)

Top-level keys (no extras):

* `semver` : string
* `version` : string (`YYYY-MM-DD`)
* `domain` : object
* `scoring` : object
* `sampling` : object
* `bounds` : object
* `failure` : object

Reject unknown keys / duplicates.

---

## 4) `domain` (who can be selected)

Required fields:

* `include_home` : boolean (must be `false` for S6; home is not selected)
* `min_candidate_rank` : int ≥ 1 (rank 0 is home)
* `max_candidate_rank` : int ≥ min_candidate_rank (or `null` for “no cap”)
* `require_eligible_crossborder` : boolean
  If true: merchants with `eligible_crossborder=false` force `K_target=0` selection.
* `allow_sparse_mode` : boolean
  If false: any merchant marked sparse must select `K_target=0` (conservative).

Semantics:

* Eligible foreign candidates = all rows in `s3_candidate_set` satisfying:

  * `candidate_rank >= min_candidate_rank`
  * `candidate_rank <= max_candidate_rank` if cap exists
  * plus merchant-level gating per the two booleans above

---

## 5) `scoring` (deterministic base score before RNG)

This policy must specify how each candidate gets a **deterministic base score** that is then perturbed by Gumbel keys.

v1 pinned minimal scoring:

* score is a monotone function of `candidate_rank` only (keeps S6 independent of other surfaces).

Required fields:

* `kind`: `"rank_decay"`
* `decay`: float > 0
* `score_floor`: float > 0

Semantics:

* For candidate rank r (>=1):

  * `base_score(r) = max(score_floor, exp(-decay * r))`

---

## 6) `sampling` (how selection is performed)

Required fields:

* `method`: `"gumbel_topk"`
* `k_source`: `"K_target"`
* `gumbel_scale`: float > 0 (typically 1.0)
* `key_form`: `"log_score_plus_gumbel"`
* `tie_break`: `"candidate_rank_asc"` (deterministic)

Semantics:

* For each eligible candidate i:

  * draw `g ~ Gumbel(0, gumbel_scale)` (logged via `rng_event_gumbel_key`)
  * compute `key_i = log(base_score_i) + g`
* select the **top K_target** candidates by `key_i` descending
* if ties (rare): smaller `candidate_rank` wins

---

## 7) `bounds` (safety constraints)

Required fields:

* `max_k_per_merchant`: int ≥ 0
* `min_k_per_merchant`: int ≥ 0
* `k_cap_policy`: `"cap_to_available"` | `"fail"`

Semantics:

* enforce:

  * `K_target = min(K_target, max_k_per_merchant)`
  * `K_target = max(K_target, min_k_per_merchant)` only if domain has enough candidates; otherwise follow failure policy
* if `K_target > |eligible|`:

  * `cap_to_available`: set `K_target = |eligible|`
  * `fail`: abort merchant

---

## 8) `failure` behaviour (must be explicit)

Required fields:

* `on_empty_domain`: `"select_none"` | `"fail"`
* `on_nan_score`: `"fail"`
* `on_nonfinite_key`: `"fail"`

Rules:

* Any NaN/Inf in score or key is a hard error (consistent with numeric policy).
* Empty domain:

  * v1 recommend `select_none` (safe).

---

## 9) Minimal v1 file (Codex can author verbatim)

```yaml
semver: "1.0.0"
version: "2024-12-31"

domain:
  include_home: false
  min_candidate_rank: 1
  max_candidate_rank: null
  require_eligible_crossborder: true
  allow_sparse_mode: true

scoring:
  kind: "rank_decay"
  decay: 0.35
  score_floor: 1.0e-12

sampling:
  method: "gumbel_topk"
  k_source: "K_target"
  gumbel_scale: 1.0
  key_form: "log_score_plus_gumbel"
  tie_break: "candidate_rank_asc"

bounds:
  max_k_per_merchant: 50
  min_k_per_merchant: 0
  k_cap_policy: "cap_to_available"

failure:
  on_empty_domain: "select_none"
  on_nan_score: "fail"
  on_nonfinite_key: "fail"
```

---

## 10) Acceptance checklist (Codex must enforce)

* schema keys exactly as specified; no duplicates
* `decay > 0`, `score_floor > 0`, `gumbel_scale > 0`
* `max_k_per_merchant >= min_k_per_merchant`
* `k_cap_policy` valid
* `require_eligible_crossborder=true` implies merchant-level eligibility gate is applied before sampling
* selection is deterministic given RNG stream + candidate_rank ordering + tie-break

---
