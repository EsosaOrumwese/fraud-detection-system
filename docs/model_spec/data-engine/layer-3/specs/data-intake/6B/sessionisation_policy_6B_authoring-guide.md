# Authoring Guide — `sessionisation_policy_6B` (S1 session key + inactivity gaps, v1)

## 0) Purpose

`sessionisation_policy_6B` is the **required** S1 policy that defines:

* the **session key template** (`session_key_base`) used to group arrivals into candidate sessions,
* **inactivity gap thresholds** and other **session boundary** rules, including whether any boundary decisions are stochastic (and therefore must use `rng_event_session_boundary`),
* the deterministic **session_id construction rule** (stable, opaque, unique per `(seed, manifest_fingerprint, scenario_id)`),
* the minimal **session summary fields** S1 must compute for `s1_session_index_6B`.

S1 sessionisation is explicitly: group by `session_key_base`, sort by `ts_utc`, walk gaps to decide boundaries.

---

## 1) Contract identity (MUST)

From the 6B contracts:

* **dataset_id:** `sessionisation_policy_6B`
* **manifest_key:** `mlr.6B.policy.sessionisation_policy`
* **path:** `config/layer3/6B/sessionisation_policy_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/sessionisation_policy_6B`
* **consumed_by:** `6B.S0`, `6B.S1`

Token-less posture:

* no timestamps, UUIDs, or digests in-file (S0 sealing records `sha256_hex`).

---

## 2) Dependencies (MUST)

This policy is evaluated by S1 **after** entity attachment is complete.
It depends on:

* `attachment_policy_6B` (because session keys reference attached entity fields)
* `rng_policy_6B` (only if stochastic boundary behaviour is enabled)
* `rng_profile_layer3` (Layer-3 RNG law for open-interval + keying)
* `behaviour_config_6B` (optional, restrictive scoping/flags)

Hard rule: if stochastic boundary behaviour is enabled here, S1 MUST use `rng_event_session_boundary`.

---

## 3) Pinned S1 algorithm surface (what this policy must fully specify)

S1’s sessionisation procedure is:

1. define `session_key_base` from this policy,
2. group arrivals by `session_key_base`,
3. sort each group by `ts_utc`,
4. apply boundary rules based on gap thresholds (and optional RNG),
5. assign a stable `session_id` and emit `s1_session_index_6B`.

---

## 4) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `policy_id` (string; MUST be `sessionisation_policy_6B`)
3. `policy_version` (string; MUST be `v1`)
4. `session_key` (object)
5. `boundary_rules` (object)
6. `stochastic_boundary` (object)
7. `session_id` (object)
8. `session_summary` (object)
9. `guardrails` (object)
10. `notes` *(optional string)*

Unknown keys ⇒ **INVALID** (fail closed at S0/S1).

---

## 5) Session key definition (MUST)

### 5.1 `session_key.fields`

This is the authoritative list of fields used to form `session_key_base`.
The S1 spec gives a typical template: `{party_id, device_id, merchant_id, channel_group, scenario_id}`.

**v1 REQUIRED default fields (recommended):**

* `party_id`
* `device_id`
* `merchant_id`
* `channel_group`
* `scenario_id`

Rules:

* Field order is authoritative (used for deterministic encoding).
* If a field is nullable under `attachment_policy_6B` for some channels, null MUST be treated as a valid value (don’t drop the component).

### 5.2 `session_key.normalisation`

Pin any normalisation required for deterministic grouping:

* `channel_group` MUST be uppercase ASCII (if present as string).
* IDs are used as-is (opaque).

### 5.3 `session_key.encoding`

Pin a deterministic encoding for `session_key_base` (to avoid impl drift).
Recommended: UER-style length-prefixed UTF-8 concatenation (same pattern used elsewhere in your engine’s keyed constructs).

---

## 6) Boundary rules (MUST)

Session boundaries are decided **within each `session_key_base` group** on sorted arrivals by `ts_utc`.

### 6.1 Gap thresholds (binding, v1)

Define two thresholds in seconds:

* `hard_timeout_seconds`
  If `gap_seconds ≤ hard_timeout_seconds` ⇒ **continue session**

* `hard_break_seconds`
  If `gap_seconds ≥ hard_break_seconds` ⇒ **start new session**

These correspond to the S1 spec’s typical pattern.

Constraints:

* `0 ≤ hard_timeout_seconds < hard_break_seconds`

### 6.2 Optional deterministic breakers

You may add deterministic “always break” predicates (still RNG-free), e.g.:

* `break_on_day_boundary` (bool): if true and `floor_date(ts_utc)` changes, break
* `break_on_channel_change` (bool): only relevant if channel_group not in key fields (not recommended)

If you include any such predicate, you must define it explicitly in the YAML and ensure it is computable from S1 arrival+attachment fields.

---

## 7) Stochastic boundary behaviour (optional, but fully pinned if enabled)

S1 spec allows stochastic break behaviour in the “ambiguous gap band” and requires using `rng_event_session_boundary` when randomisation is used.

### 7.1 v1 ambiguity band

Ambiguity region is strictly:

* `hard_timeout_seconds < gap_seconds < hard_break_seconds`

### 7.2 Decision law (v1 pinned, 1 draw per ambiguous boundary)

If enabled:

* compute deterministic probability ramp:

[
p_{\text{break}}(gap) =
\mathrm{clamp}\left(\frac{gap - hard_timeout}{hard_break - hard_timeout},\ 0,\ 1\right)
]

* draw one uniform `u` from `rng_event_session_boundary`
* break if `u < p_break(gap)` else continue

This preserves:

* fixed draw budget (exactly one draw per ambiguous boundary decision),
* deterministic behaviour outside the ambiguity band.

### 7.3 Keying requirements (MUST)

The policy must specify which identifiers form the boundary decision key. Recommended minimum:

* `(manifest_fingerprint, seed, scenario_id, session_key_base, arrival_seq_left, arrival_seq_right)`
  so each boundary decision is stable and order-independent.

Hard rule:

* `run_id` must not participate in keying (log-only).

---

## 8) Session ID construction (MUST)

S1 must assign a unique `session_id` within `(seed, manifest_fingerprint, scenario_id)` and every `session_id` referenced in arrival entities must exist in the session index.

### 8.1 v1 recommended strategy: anchored hash id

To avoid relying on processing order, define the session anchor as:

* the **first arrival** in the session after sorting (`arrival_seq_first`, `ts_utc_first`, `merchant_id` already in the arrival key)

Define:

* `session_id = id64( SHA256( "mlr:6B.session_id.v1" || mf || LE64(seed) || UER(scenario_id) || SER(session_key_base) || SER(arrival_seq_first) ) )[0:8]`

Where:

* take the first 8 bytes of SHA256 as LE64, format as fixed-width hex (or your `$defs/id64` format).

This ensures:

* deterministic ids across implementations,
* no dependence on batch ordering / streaming strategy.

---

## 9) Session summary (MUST)

S1 must compute at least:

* `session_start_utc = min(ts_utc)`
* `session_end_utc = max(ts_utc)`
* `arrival_count`

And it may surface “primary” entity context and diagnostic aggregates as described in the S1 spec.

The policy must state:

* which “primary” fields are emitted (recommended: `primary_party_id`, `primary_device_id`, `primary_ip_id`, `primary_merchant_id`)
* how ties are broken (recommended: “dominant by arrival_count; tie-break by id asc”)

---

## 10) Guardrails (MUST)

Sessionisation can blow up in degenerate scenarios; this policy must pin caps:

* `max_arrivals_per_session` (int ≥ 1): if exceeded, force a break (deterministic)
* `max_session_duration_seconds` (int ≥ 1): if exceeded, force a break (deterministic)
* `max_sessions_per_session_key` (int ≥ 1): if exceeded, S1 must FAIL (protects against policy bugs)

---

## 11) Minimal v1 policy (copy/paste baseline)

```yaml
schema_version: 1
policy_id: sessionisation_policy_6B
policy_version: v1

session_key:
  fields: [party_id, device_id, merchant_id, channel_group, scenario_id]
  normalisation:
    channel_group: UPPERCASE_ASCII
  encoding:
    mode: uer_concat_v1
    null_token: "<NULL>"

boundary_rules:
  hard_timeout_seconds: 900        # 15 minutes
  hard_break_seconds: 7200         # 2 hours
  break_on_day_boundary: false

stochastic_boundary:
  enabled: true
  ambiguity_band: (hard_timeout_seconds, hard_break_seconds)
  decision_law:
    mode: linear_ramp_pbreak_v1
    pbreak_formula: "clamp((gap - hard_timeout)/(hard_break - hard_timeout), 0, 1)"
    rng_family: rng_event_session_boundary
    draws_per_ambiguous_boundary: 1
  keying:
    forbid_run_id: true
    ids: [manifest_fingerprint, seed, scenario_id, session_key_base, arrival_seq_left, arrival_seq_right]

session_id:
  mode: anchored_hash64_v1
  domain_tag: "mlr:6B.session_id.v1"
  anchor: first_arrival_in_session
  hash: sha256
  output_format: id64_hex_le

session_summary:
  required_fields: [session_start_utc, session_end_utc, arrival_count]
  primary_fields:
    - { name: primary_party_id,    mode: dominant_by_arrival_count, tie_break: id_asc }
    - { name: primary_device_id,   mode: dominant_by_arrival_count, tie_break: id_asc }
    - { name: primary_ip_id,       mode: dominant_by_arrival_count, tie_break: id_asc }
    - { name: primary_merchant_id, mode: dominant_by_arrival_count, tie_break: id_asc }

guardrails:
  max_arrivals_per_session: 500
  max_session_duration_seconds: 43200  # 12 hours
  max_sessions_per_session_key: 20000
```

---

### 11.1 Placeholder resolution (MUST)

Replace `<NULL>` with the literal string you want to use as the null sentinel in `session_key.encoding.null_token`.
Use a value that cannot collide with real IDs (e.g., `"__NULL__"`). Do not leave the angle-bracket token in a sealed policy.

---

## 12) Acceptance checklist (MUST)

1. **Contract pins:** correct path + schema_ref, and registered as required for S0/S1.
2. **Algorithm matches S1 spec:** group by `session_key_base`, sort by `ts_utc`, apply gap thresholds, optional RNG only in ambiguity band.
3. **RNG compliance:** if stochastic enabled, uses `rng_event_session_boundary` exactly as specified (1 draw per ambiguous boundary); otherwise consumes 0 draws.
4. **Session ID invariants:** unique within `(seed, mf, scenario_id)`; every arrival gets exactly one session_id; every session_id appears exactly once in `s1_session_index_6B`.
5. Token-less YAML, no anchors/aliases, unknown keys invalid.

---

## Non-toy/realism guardrails (MUST)

- `hard_timeout_seconds` must be >= `soft_timeout_seconds` and both must be > 0.
- Timeouts must be plausible for the domain (avoid near-zero or multi-day gaps unless justified).
- If stochastic boundaries are enabled, `rng_event_session_boundary` must be wired and budgeted.
- `session_key.fields` must be stable and non-empty; nulls must be handled deterministically.

