# Authoring Guide — `crossborder_hyperparams.yaml` (1A governed cross-border hyperparameters)

This file is a **governed parameter artefact** (participates in `parameter_hash`) and is read in **two places** in 1A:

1. **S0 “apply eligibility rules”** → produces `crossborder_eligibility_flags` (one row per merchant).
2. **S4 ZTP parameterisation** → provides the **ZTP link coefficients θ**, feature handling, and **exhaustion cap/policy** for sampling `K_target`.

It is **not** a “downloaded dataset”. It is authored, versioned, and pinned.

---

## 1) Identity and location

* **Basename:** `crossborder_hyperparams.yaml`
* **Path (per artefact registry):** `config/policy/crossborder_hyperparams.yaml`
* **Type:** config (allocation)
* **Governance:** exact bytes participate in `parameter_hash` (so changing this file changes run partitions for parameter-scoped outputs and logs)

---

## 2) Required top-level shape

`crossborder_hyperparams.yaml` MUST contain:

* `semver` (semver string)
* `version` (date label `YYYY-MM-DD`)
* `eligibility` (object) - used by S0 eligibility flags
* `ztp` (object) - used by S4 ZTP link + exhaustion

Unknown top-level keys SHOULD be rejected (keep this strict; it prevents silent drift).

---

### 2.1 Realism & policy-coherence constraints (MUST)

Because this is an **authored** input (not downloaded), Codex MUST NOT choose the "easiest" values. Before sealing a version, you MUST validate that the implied behaviour is **non-degenerate and plausible**:

* Eligibility MUST be neither ~0% nor ~100% across your merchant universe (unless your scenario explicitly calls for that extreme).
* Eligibility SHOULD vary by `channel` and `mcc` (at minimum), so cross-border is not a flat random switch.
* Coherence SHOULD hold with `policy.s3.rule_ladder.yaml`: if S0 marks a merchant as ineligible, the S3 rule ladder SHOULD not later admit a large foreign candidate set for the same merchant. If your design allows disagreement, document it and quantify it (e.g., "< X% of merchants disagree").

---

## 3) `eligibility` block (S0 apply-eligibility rules)

### 3.1 Required fields

```yaml
eligibility:
  rule_set_id: "<non-empty string>"
  default_decision: "allow" | "deny"
  rules: [ ... ]
```

### 3.2 Each rule entry (required fields + domains)

Each element in `eligibility.rules[]` MUST have:

* `id` : ASCII string, unique within the file
* `priority` : integer in `[0, 2^31-1]` (lower = stronger)
* `decision` : `"allow"` or `"deny"`
* `channel` : `"*"` or a list subset of exactly `["CP","CNP"]`
* `iso` : `"*"` or a list of ISO2 (uppercase) from your `iso3166_canonical_2024`
* `mcc` : `"*"` or a list of MCC selectors:

  * 4-digit strings `"NNNN"`, and/or
  * inclusive ranges `"NNNN-MMMM"` with `NNNN ≤ MMMM`, both within `0000..9999`

### 3.3 Match semantics

A rule “matches” merchant `m` iff:

* `channel_sym(m)` ∈ `channel` (or `channel="*"`)
* `home_country_iso(m)` ∈ `iso` (or `iso="*"`)
* `mcc(m)` is one of:

  * the literal MCC codes, or
  * within any expanded MCC ranges (numeric comparison)

### 3.4 Conflict resolution (total order; deterministic)

If multiple rules match, choose the winner by:

1. **Decision tier:** `deny` outranks `allow`
2. **Priority:** lower `priority` outranks higher
3. **Tie-break:** ASCII lexical order on `id`

If **no** rule matches, use:

* `default_decision`, with reason `default_allow` or `default_deny`.

This logic drives:

* `crossborder_eligibility_flags.is_eligible`
* `crossborder_eligibility_flags.reason`
* `crossborder_eligibility_flags.rule_set` = `rule_set_id`

---

## 4) `ztp` block (S4 ZTP link + exhaustion policy)

### 4.1 Required fields

```yaml
ztp:
  theta: { ... }                     # ZTP link coefficients
  x_transform: { ... }               # monotone transform into [0,1]
  x_default: <float in [0,1]>        # used if X missing; overrides 0.0 if present
  max_ztp_zero_attempts: <int >= 1>  # default 64 if you keep v1 default
  ztp_exhaustion_policy: "abort" | "downgrade_domestic"
```

### 4.2 Semantics (what S4 computes)

**Realism sanity (MUST):** choose `theta` so that for typical `(N, X)` values in your merchant population, `lambda_extra = exp(eta)` stays in a reasonable numeric range (finite, not extreme), and produces a plausible foreign-count distribution. As a minimum, self-test `eta`/`lambda_extra` on a grid over `N` and `X` before sealing.

S4 evaluates (binary64, fixed operation order):

* `η = θ0 + θ1 * log(N) + θ2 * X + ...`
* `λ_extra = exp(η)` and MUST be finite and > 0
* Then it runs the ZTP loop (Poisson draws rejecting 0) with:

  * attempt cap = `max_ztp_zero_attempts`
  * policy on cap hit = `ztp_exhaustion_policy`

### 4.3 `theta` representation (v1 baseline)

For v1, keep the link basis minimal and explicit:

```yaml
theta:
  theta0: <float>      # intercept
  theta_log_n: <float> # coefficient on log(N)
  theta_x: <float>     # coefficient on X
```

If you later add more terms (“…”) you add new explicit keys (semver bump as needed).

### 4.4 `x_transform` (v1 baseline)

Keep it monotone and bounded:

```yaml
x_transform:
  kind: "clamp01"   # v1
```

Meaning: treat X as already in [0,1], clamp if needed.

---

## 5) Determinism and hashing obligations (what Codex must respect)

* This file is **parsed**, then the engine computes `parameter_hash` using a canonical serialization discipline.
* For the **S4-controlled portion**, the hash must be sensitive to:

  * `theta`
  * `x_transform`
  * `x_default`
  * `max_ztp_zero_attempts`
  * `ztp_exhaustion_policy`

So: avoid “pretty YAML tricks” (anchors, comments-as-data). Keep the structure simple and stable.

---

## 6) Minimal v1 example file (Codex can write verbatim)

```yaml
semver: "1.0.0"
version: "2024-12-31"

eligibility:
  rule_set_id: "eligibility.v1.2025-04-15"
  default_decision: "deny"
  rules:
    # Example: deny everything by default, allow only a small safe slice.
    - id: "allow_cp_general"
      priority: 100
      decision: "allow"
      channel: ["CP"]
      iso: "*"
      mcc: ["5000-5999"]   # example inclusive range

    - id: "deny_cnp_high_risk"
      priority: 10
      decision: "deny"
      channel: ["CNP"]
      iso: "*"
      mcc: ["7995", "4829"]  # example codes

ztp:
  theta:
    theta0: -1.5
    theta_log_n: 0.7
    theta_x: 0.5
  x_transform:
    kind: "clamp01"
  x_default: 0.0
  max_ztp_zero_attempts: 64
  ztp_exhaustion_policy: "downgrade_domestic"
```

This is intentionally “small but real”: it validates, it’s deterministic, it supports S0 + S4, and you can expand it later without redesign.

---

## 7) Acceptance checklist (Codex should enforce before sealing)

### Eligibility

* `rule_set_id` non-empty
* `default_decision ∈ {allow, deny}`
* rule `id` unique
* `priority` in range
* `decision` valid
* `channel` is `"*"` or subset of `{CP,CNP}`
* `iso` is `"*"` or all entries exist in `iso3166_canonical_2024`
* `mcc` is `"*"` or valid selectors; ranges expand; reject invalid MCCs

### ZTP

* `theta` has required keys
* `x_default ∈ [0,1]`
* `max_ztp_zero_attempts >= 1`
* `ztp_exhaustion_policy ∈ {abort, downgrade_domestic}`

---
