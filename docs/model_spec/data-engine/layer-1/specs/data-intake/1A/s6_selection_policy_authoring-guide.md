# Authoring Guide - `config/policy.s6.selection.yaml` (S6 membership selection policy)

This file governs **1A.S6** policy knobs for *membership selection* behaviour and logging, given:

* the ordered candidate set from **S3** (`s3_candidate_set` with `candidate_rank`)
* the foreign target count from **S4** (`K_target`)
* the currency-country weights from **S5** (`ccy_country_weights_cache`)

**Important:** the selection *mechanism* is fixed by the S6 state spec (Gumbel-top-k over **S5 weights**) and MUST NOT be redefined by this policy. This file only provides deterministic knobs (caps + logging mode + zero-weight handling).

---

## 1) File identity

* **Artefact id:** `s6_selection_policy`
* **Path (per artefact registry):** `config/policy.s6.selection.yaml`
* **Governance:** sealed policy input -> affects `parameter_hash`

---

## 2) Required top-level structure (MUST)

Top-level keys (no extras):

* `defaults` : object (required)
* `per_currency` : object (optional; currency overrides)

Reject unknown keys / duplicates.

---

## 3) Required keys inside `defaults` (MUST)

The `defaults` block MUST define:

* `emit_membership_dataset : bool` (default: `false`)
  *If true, S6 emits the optional `s6_membership` dataset. Authority note still applies: it must be re-derivable from RNG events + upstream inputs.*

* `log_all_candidates : bool` (default: `true`)
  *If true, S6 writes one `rng_event.gumbel_key` for every **considered** candidate (recommended). If false, keys are written only for selected candidates and the validator must replay counters to reconstruct missing keys.*

* `max_candidates_cap : int >= 0` (default: `0`)
  *If >0, S6 considers only the first `max_candidates_cap` candidates by `candidate_rank` (no re-order). If 0, no cap.*

* `zero_weight_rule : enum{"exclude","include"}` (default: `"exclude"`)
  *Defines how candidates with S5 weight==0 are handled (see 5.1).*

* `dp_score_print : int >= 0` (optional; diagnostic-only)
  *If present, printed diagnostics may include fixed-dp score strings. This MUST NOT affect selection, RNG budgets, or validation.*

---

## 4) `per_currency` overrides (optional)

If present, `per_currency` maps **ISO-4217 alphabetic currency codes** (uppercase) to an object containing overrides for a **restricted subset** of `defaults`.

**Global-only keys (MUST NOT be overridden):**
* `log_all_candidates`
* `dp_score_print`

Override precedence per merchant MUST be:

1. `per_currency[merchant_currency]` (if present), else
2. `defaults`

Allowed per-currency override keys (only):
* `emit_membership_dataset`
* `max_candidates_cap`
* `zero_weight_rule`

Unknown currency keys, non-uppercase keys, attempts to override global-only keys, or unknown fields are policy validation failures (fail closed).

---

## 5) Fixed semantics (what the policy is controlling)

### 5.1 Considered vs eligible sets (binding)

Given S3 candidate rows in `candidate_rank` order:

* Apply `max_candidates_cap` (if >0) to define the **considered set**.
* Apply `zero_weight_rule`:

  * `"exclude"`: drop weight==0 candidates from the considered set entirely (no events written; not selectable).
  * `"include"`: keep weight==0 in the considered set (events may be written), but they are not eligible for selection (treated as `key=-inf`).

The **eligible set** is the considered set with `weight > 0`.

---

### 5.2 Selection mechanism is not configurable

For every eligible candidate with weight `w_c>0`, S6 computes a Gumbel key consistent with the state law:

`key_c = ln(w_c) - ln(-ln(u_c))` where `u_c` in (0,1) is produced under the Philox/open-interval regime and logged as `rng_event.gumbel_key`.

S6 then selects the top `K_target` keys (ties broken deterministically by `candidate_rank` asc). If `K_target > |eligible|`, S6 realizes `K_realized = |eligible|`.

---

### 5.3 Logging mode (`log_all_candidates`)

* If `log_all_candidates=true`: write one `rng_event.gumbel_key` per considered candidate.
* If `log_all_candidates=false`: write keys only for selected candidates; the validator replays counters for missing keys.

---

## 6) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
defaults:
  emit_membership_dataset: false
  log_all_candidates: true
  max_candidates_cap: 0
  zero_weight_rule: "exclude"
  # dp_score_print: 8   # optional diagnostic-only

per_currency: {}
```

---

## 7) Acceptance checklist (Codex must enforce)

* YAML parses with **no duplicate keys**
* Top-level keys are exactly: `{defaults}` or `{defaults, per_currency}`
* `defaults` contains all required keys, with domains enforced
* `per_currency` currency keys are uppercase ISO-4217 alpha-3
* `per_currency` override blocks contain only: `{emit_membership_dataset, max_candidates_cap, zero_weight_rule}`
* `zero_weight_rule` is one of `{"exclude","include"}`
* This policy does not introduce any scoring model independent of S5 weights (scoring is fixed by S6 spec)

---

## Non-toy/realism guardrails (MUST)

- This policy MUST NOT introduce scoring; only the allowed knobs are permitted.
- `max_candidates_cap` MUST be >= K_target for any merchant where K_target > 0, else fail closed.
- If `zero_weight_rule` excludes candidates, ensure at least K_target candidates remain; otherwise fail closed.
- If `emit_membership_dataset=true`, schema/path must be present and validated.

