# Authoring Guide — `day_effect_policy_v1` (2B.S3 zone-level day effects: γ)

This policy is the **governed control surface** for **2B.S3** (day effects). It is sealed in **2B.S0** and drives a **large, production-scale** output table `s3_day_effects` by specifying:

* the **UTC day range** (inclusive),
* the **log-normal variance** (`sigma_gamma`) for `log_gamma`,
* the **Philox wiring** (`rng_engine`, `rng_stream_id`, and deterministic key/counter derivation),
* and the **minimum record fields** S3 must persist.

The goal is “**real deal**”: this policy must not allow Codex to emit a tiny, toy configuration (e.g., 7 days). The policy should yield a realistic volume of day effects and stable replay behaviour.

---

## 1) File identity (binding)

* **Dictionary ID:** `day_effect_policy_v1`
* **Path:** `contracts/policy/2B/day_effect_policy_v1.json`
* **Format:** JSON
* **Tokens:** **none** (fingerprint-sealed by S0; selected by **exact path + sha256**)

---

## 2) What S3 requires from this policy (binding minima)

This policy **MUST** declare (minimum set):

* `rng_engine` (Philox variant token)
* `rng_stream_id` (reserved for S3)
* `draws_per_row = 1`
* `sigma_gamma > 0`
* `day_range = { start_day, end_day }` with **inclusive** semantics and `start_day ≤ end_day`
* `record_fields` containing at least:

  * `gamma`, `log_gamma`, `sigma_gamma`,
  * `rng_stream_id`, `rng_counter_lo`, `rng_counter_hi`,
  * `created_utc`
* `created_utc_policy_echo` (boolean)

Absence of any required entry ⇒ **FAIL CLOSED**.

---

## 3) Policy shape (pinned by this guide)

Top-level JSON object MUST contain these keys:

### 3.1 Required identity + digest

* `policy_id` : string, MUST equal `"day_effect_policy_v1"`
* `version_tag` : string (real governance tag; not placeholder)
* `sha256_hex` : hex64 lowercase (computed by §4)

### 3.2 Required day-effect controls

* `day_range` : object

  * `start_day` : `"YYYY-MM-DD"` (UTC date)
  * `end_day`   : `"YYYY-MM-DD"` (UTC date)
  * semantics: inclusive bounds
* `sigma_gamma` : number, MUST be `> 0`
* `draws_per_row` : integer, MUST equal `1`

### 3.3 Required RNG wiring

* `rng_engine` : string, MUST equal `"philox2x64-10"`  *(wire token used elsewhere in Layer-1)*
* `rng_stream_id` : string, MUST match `^2B\.[A-Za-z0-9_.-]+$`
* `rng_derivation` : object (pins deterministic key + base counter)

  * `domain_master` : string (e.g., `"mlr:2B.master"`)
  * `domain_stream` : string (e.g., `"mlr:2B.s3.day_effects"`)
  * `low64_rule` : string, MUST equal `"LE64_tail_bytes_24_31"`
  * `counter_split_rule` : string, MUST equal `"BE64_bytes_16_23_and_24_31"`
  * `key_basis` : array, MUST equal `["manifest_fingerprint_bytes","seed_u64","rng_stream_id"]`
  * `base_counter_basis` : array, MUST equal `["manifest_fingerprint_bytes","seed_u64","rng_stream_id"]`

### 3.4 Required persistence controls

* `record_fields` : array of strings (see §2)
* `created_utc_policy_echo` : boolean

### 3.5 Optional extension bucket

* `extensions` : object (optional; any future fields MUST live here)

---

## 4) Canonical digest law (`sha256_hex`) (MUST)

Compute `sha256_hex` from the policy **excluding** the `sha256_hex` field:

1. Copy the JSON object and remove `sha256_hex`.
2. Serialize as **canonical JSON**:

   * UTF-8
   * sort object keys lexicographically at every level
   * no insignificant whitespace
   * numbers are standard JSON decimals (no NaN/Inf)
3. `sha256_hex = SHA256(canonical_bytes)` → lowercase hex64
4. Write the final policy including `sha256_hex`
5. Recompute and verify equality; mismatch ⇒ **FAIL CLOSED**

---

## 5) Deterministic RNG derivation law (binding)

S3’s per-row RNG provenance is based on a **run-constant** 128-bit `base_counter` and a **run-constant** 64-bit `key`, then a contiguous counter range:

* Writer row order defines rank `i` in:
  `(merchant_id ↑, utc_day ↑, tz_group_id ↑)`
* Row counter is:
  `counter = base_counter + i` (128-bit unsigned add; wrap forbidden)

This policy pins how to derive `key` and `base_counter` deterministically from `{manifest_fingerprint_bytes, seed, rng_stream_id}`:

### 5.1 Definitions (normative)

* `UER(s)` = length-prefixed UTF-8 bytes for string `s` (no delimiters)
* `LE64(seed)` = 8 bytes little-endian
* `LOW64(H)` = interpret digest bytes `[24..31]` as **LE64**
* `split128(H)` = `(hi, lo)` where `hi = BE64(H[16..23])`, `lo = BE64(H[24..31])`

### 5.2 Master material (run-constant)

```
M = SHA256( UER(domain_master) || manifest_fingerprint_bytes || LE64(seed_u64) )
```

### 5.3 Stream material (run-constant)

```
msg = UER(domain_stream) || UER(rng_stream_id)
H   = SHA256( M || msg )
key = LOW64(H)
(base_counter_hi, base_counter_lo) = split128(H)
```

S3 MUST:

* use this `key` and `base_counter` for the entire run,
* record the per-row counter words in output as `rng_counter_hi`, `rng_counter_lo`,
* and enforce **exactly one** Philox draw per row (`draws_per_row=1`).

---

## 6) Day grid semantics (binding)

* `utc_day` values are the inclusive date grid from `day_range.start_day` to `day_range.end_day`.
* Each `utc_day` is a **UTC calendar day label** (not a timestamp).
* No gaps, no extras.

Codex MUST:

* parse both as ISO dates,
* require `start_day ≤ end_day`,
* generate the complete inclusive sequence deterministically.

---

## 7) Realism floors (MUST; prevents toy policies)

Codex MUST reject a `day_effect_policy_v1` that violates any of:

### 7.1 Day-range size (volume)

Let `D = number_of_days_inclusive(start_day, end_day)`.

* **MUST:** `D ≥ 365`  (minimum one full year; prevents “sample week” configs)
* **SHOULD (production baseline):** `D ≥ 730`  (two years)
* **MUST:** `D ≤ 1826` (≤ 5 years) unless you deliberately introduce a v2 policy with explicit scale justification

### 7.2 Variance realism

* **MUST:** `0 < sigma_gamma ≤ 1.2`
* **MUST:** `sigma_gamma ≥ 0.08` (prevents near-flat γ surfaces that look toy)
* **RECOMMENDED baseline:** `sigma_gamma ∈ [0.20, 0.45]`

### 7.3 RNG wiring realism

* `rng_engine` MUST be `"philox2x64-10"`
* `rng_stream_id` MUST be namespaced (pattern in §3.3)
* `draws_per_row` MUST equal `1`

### 7.4 Non-placeholder governance

* `version_tag` MUST NOT be placeholder-like (`test`, `example`, `todo`, `TBD`, `null`, etc.)

If any realism floor fails ⇒ **FAIL CLOSED** (do not emit; do not seal).

---

## 8) Required `record_fields` (MUST)

`record_fields` MUST include at least the following strings:

* `"gamma"`
* `"log_gamma"`
* `"sigma_gamma"`
* `"rng_stream_id"`
* `"rng_counter_lo"`
* `"rng_counter_hi"`
* `"created_utc"`

Additional fields MAY be present, but S3 must still emit (and validators must still check) the required core set.

---

## 9) Recommended v1 production policy (non-toy baseline)

```json
{
  "policy_id": "day_effect_policy_v1",
  "version_tag": "v1.0.0",
  "rng_engine": "philox2x64-10",
  "rng_stream_id": "2B.day_effects",
  "draws_per_row": 1,
  "sigma_gamma": 0.30,
  "day_range": {
    "start_day": "2024-01-01",
    "end_day": "2026-12-31"
  },
  "rng_derivation": {
    "domain_master": "mlr:2B.master",
    "domain_stream": "mlr:2B.s3.day_effects",
    "low64_rule": "LE64_tail_bytes_24_31",
    "counter_split_rule": "BE64_bytes_16_23_and_24_31",
    "key_basis": ["manifest_fingerprint_bytes", "seed_u64", "rng_stream_id"],
    "base_counter_basis": ["manifest_fingerprint_bytes", "seed_u64", "rng_stream_id"]
  },
  "record_fields": [
    "merchant_id",
    "utc_day",
    "tz_group_id",
    "gamma",
    "log_gamma",
    "sigma_gamma",
    "rng_stream_id",
    "rng_counter_hi",
    "rng_counter_lo",
    "created_utc"
  ],
  "created_utc_policy_echo": true,
  "extensions": {},
  "sha256_hex": "<COMPUTED_BY_SECTION_4>"
}
```

This is “real deal” because:

* it forces **multi-year** day surfaces,
* it pins a **non-degenerate** sigma,
* it fully specifies deterministic Philox key/counter derivation (no ad-hoc RNG),
* and it’s sealable + replayable.

---

## 10) Acceptance checklist (Codex MUST enforce)

1. JSON parses; required keys present.
2. `policy_id == "day_effect_policy_v1"`.
3. `sha256_hex` recomputes exactly by §4.
4. `day_range` parses; `start_day ≤ end_day`; inclusive `D` computed.
5. Realism floors (§7) pass.
6. `rng_engine == "philox2x64-10"` and `rng_stream_id` matches pattern.
7. `draws_per_row == 1`.
8. `sigma_gamma` within bounds and non-degenerate.
9. `rng_derivation` fields exactly match the pinned derivation law (§5).
10. `record_fields` includes the required core set (§8).

If any check fails → **FAIL CLOSED**.

---

## Placeholder resolution (MUST)

- Replace placeholder weekday/seasonality weights with real values (not uniform defaults).
- Replace any example calendars or date ranges with the actual effective ranges.
- Replace placeholder policy IDs/versions with final identifiers.

