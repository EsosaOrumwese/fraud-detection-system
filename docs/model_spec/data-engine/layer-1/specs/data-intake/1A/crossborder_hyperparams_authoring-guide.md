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
  rule_set_id: "<non-empty string>"
  theta_order: ["<coef_name_0>", "<coef_name_1>", "..."]  # evaluation order (fixed)
  theta: { ... }                                         # map coef_name -> float
  feature_x:
    feature_id: "<string>"            # e.g., "openness"
    x_default: <float in [0,1]>       # used if X missing; overrides 0.0 if present
    x_transform: { ... }              # monotone transform into [0,1]
  MAX_ZTP_ZERO_ATTEMPTS: <int >= 1>   # default 64 if you keep v1 default
  ztp_exhaustion_policy: "abort" | "downgrade_domestic"
```

### 4.2 Semantics (what S4 computes)

**Realism sanity (MUST):** choose `theta` so that for typical `(N, X)` values in your merchant population, `lambda_extra = exp(eta)` stays in a reasonable numeric range (finite, not extreme), and produces a plausible foreign-count distribution. As a minimum, self-test `eta`/`lambda_extra` on a grid over `N` and `X` before sealing.

S4 evaluates (binary64, fixed operation order):

* `η = θ0 + θ1 * log(N) + θ2 * X + ...`
* `λ_extra = exp(η)` and MUST be finite and > 0
* Then it runs the ZTP loop (Poisson draws rejecting 0) with:

  * attempt cap = `MAX_ZTP_ZERO_ATTEMPTS`
  * policy on cap hit = `ztp_exhaustion_policy`

### 4.3 `theta_order` + `theta` representation (v1 baseline)

For v1, keep the link basis minimal and explicit, and pin evaluation order:

```yaml
theta_order:
  - "theta0_intercept"
  - "theta1_log_n_sites"
  - "theta2_openness"   # align with `feature_x.feature_id`
theta:
  theta0_intercept: <float>       # intercept
  theta1_log_n_sites: <float>     # coefficient on log(N)
  theta2_openness: <float>        # coefficient on X (`feature_x`)
```

If you later add more terms (“…”) you add new explicit keys (semver bump as needed).

### 4.4 `x_transform` (v1 baseline)

Keep it monotone and bounded:

```yaml
x_transform:
  kind: "clamp01"   # v1
```

Meaning: treat X as already in [0,1], clamp if needed (applies to `ztp.feature_x.x_transform`).

---

### 4.5 Placeholder resolution (MUST)

The angle-bracket tokens in the YAML snippets are literal placeholders. Replace them with:

* `<non-empty string>`: a stable, human-readable `rule_set_id` (e.g., `eligibility.v1.2025-04-15`).
* `<float>`: a finite numeric value (no NaN/Inf), chosen to meet the realism sanity check in 4.2.
* `<int >= 1>`: a positive integer cap for ZTP zero-attempts (use 64 unless you have evidence to lower it).

Do not introduce additional keys without a semver bump.

---

## 5) Determinism and hashing obligations (what Codex must respect)

* This file is **parsed**, then the engine computes `parameter_hash` using a canonical serialization discipline.
* For the **S4-controlled portion**, the hash must be sensitive to:

  * `rule_set_id`
  * `theta_order`
  * `theta`
  * `feature_x.feature_id`
  * `feature_x.x_transform`
  * `feature_x.x_default`
  * `MAX_ZTP_ZERO_ATTEMPTS`
  * `ztp_exhaustion_policy`

So: avoid “pretty YAML tricks” (anchors, comments-as-data). Keep the structure simple and stable.

---

## 6) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
# config/policy/crossborder_hyperparams.yaml
# source=authored; vintage=2025-12-31
# Governs: 1A.S0.6 eligibility + 1A.S4 ZTP link/exhaustion (participates in parameter_hash)

semver: "1.0.0"
version: "2025-12-31"

eligibility:
  rule_set_id: "eligibility.v1.2025-12-31"
  default_decision: "deny"   # "allow" | "deny"
  rules:
    # Hard deny: sanctioned home countries (all channels, all MCCs)
    - id: "deny_sanctioned_home"
      priority: 10
      decision: "deny"
      mcc: ["*"]
      channel: ["*"]         # "*" or subset of {"CP","CNP"}
      iso: ["BY","CU","IR","KP","RU","SD","SY","VE"]
      reason: "deny_sanctioned_home"

    # Risk deny: cash-like / gambling / high-risk CNP categories (global)
    - id: "deny_high_risk_cnp_cashlike"
      priority: 20
      decision: "deny"
      mcc:
        - "4829"              # money transfer
        - "6011"              # cash disbursement (ATM)
        - "6051"              # quasi-cash / crypto-like (scheme dependent)
        - "7995"              # gambling
        - "7800-7999"         # gambling / gaming bands
      channel: ["CNP"]
      iso: ["*"]
      reason: "deny_high_risk_cnp_cashlike"

    # Allow: travel/transport/hospitality tends to be genuinely cross-border (CP and CNP)
    - id: "allow_travel_transport"
      priority: 100
      decision: "allow"
      mcc:
        - "3000-3999"         # travel/airline bands
        - "4111"              # local commuter transport
        - "4121"              # taxi/ride
        - "4131"              # bus
        - "4411"              # cruise/steamship
        - "4511"              # airlines
        - "4722"              # travel agencies
        - "4789"              # transport services
        - "7011"              # hotels/lodging
      channel: ["CP","CNP"]
      iso: ["*"]
      reason: "allow_travel_transport"

    # Allow: digital / ecommerce CNP (cross-border is common)
    - id: "allow_digital_cnp"
      priority: 110
      decision: "allow"
      mcc:
        - "4810-4899"         # telecom / digital services bands
        - "5960-5969"         # direct marketing / ecommerce
        - "5815"              # digital goods (scheme dependent)
        - "5816"
        - "5817"
        - "5818"
      channel: ["CNP"]
      iso: ["*"]
      reason: "allow_digital_cnp"

    # Allow: general retail ecommerce band (moderate broadness, still CNP-only)
    - id: "allow_retail_cnp"
      priority: 200
      decision: "allow"
      mcc:
        - "5000-5999"         # broad retail band
        - "5300-5399"         # discount/warehouse
        - "5400-5599"         # grocery / food retail band
      channel: ["CNP"]
      iso: ["*"]
      reason: "allow_retail_cnp"

    # Allow: home in major economies / payment hubs (covers “international brands” outside the bands above)
    - id: "allow_home_hubs_major_markets"
      priority: 300
      decision: "allow"
      mcc: ["*"]
      channel: ["*"]
      iso:
        - "AE"
        - "AU"
        - "BE"
        - "BR"
        - "CA"
        - "CH"
        - "CN"
        - "DE"
        - "DK"
        - "ES"
        - "FR"
        - "GB"
        - "HK"
        - "IE"
        - "IL"
        - "IN"
        - "IT"
        - "JP"
        - "KR"
        - "LU"
        - "MX"
        - "NL"
        - "NO"
        - "SA"
        - "SE"
        - "SG"
        - "US"
      reason: "allow_home_hubs_major_markets"

ztp:
  rule_set_id: "ztp_link.v1.2025-12-31"

  # Fixed-order link parameters θ for:
  #   η = θ0 + θ1*log(N) + θ2*X
  #   λ = exp(η)
  theta_order:
    - "theta0_intercept"
    - "theta1_log_n_sites"
    - "theta2_openness"
  theta:
    theta0_intercept: -1.8
    theta1_log_n_sites: 0.85
    theta2_openness: 1.0

  # Feature X ∈ [0,1]; if missing, S4 MUST use X_default.
  feature_x:
    feature_id: "openness"
    x_default: 0.0
    x_transform:
      kind: "clamp01"   # governance-defined; stays deterministic

  # Exhaustion controls (governed)
  MAX_ZTP_ZERO_ATTEMPTS: 64
  ztp_exhaustion_policy: "downgrade_domestic"   # "abort" | "downgrade_domestic"
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
* `channel` contains `"*"` or is a subset of `{CP,CNP}`
* `iso` contains `"*"` or all entries exist in `iso3166_canonical_2024`
* `mcc` contains `"*"` or valid selectors; ranges expand; reject invalid MCCs

### ZTP

* `theta_order` non-empty; every name in `theta_order` exists in `theta` (and no extra keys in `theta`)
* `feature_x.x_default ∈ [0,1]`
* `MAX_ZTP_ZERO_ATTEMPTS >= 1`
* `ztp_exhaustion_policy ∈ {abort, downgrade_domestic}`

---
