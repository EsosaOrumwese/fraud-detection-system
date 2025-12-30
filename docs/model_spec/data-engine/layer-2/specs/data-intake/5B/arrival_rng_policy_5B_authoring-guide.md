# Authoring Guide — `arrival_rng_policy_5B` (5B Philox streams, substreams, budgets, and counter mapping)

## 0) Purpose

`arrival_rng_policy_5B` is the **sealed, token-less RNG wiring** for **all RNG-consuming states in 5B** (S2/S3/S4). It pins:

* the RNG engine (**Philox 2×64-10**) and the open-interval uniform law,
* the **event families** and their `module` + `substream_label`,
* the **budget law** (draws/blocks) per family, and
* the **key/counter derivation law** so counters never overlap and replay is provable.

This policy MUST be strong enough that Codex can’t “wing it” with ad-hoc RNG calls and still pass validation.

---

## 1) File identity (MUST)

* **Artefact ID:** `arrival_rng_policy_5B`
* **Path:** `config/layer2/5B/arrival_rng_policy_5B.yaml`
* **Schema anchor:** `schemas.5B.yaml#/config/arrival_rng_policy_5B` *(permissive; this guide pins the real contract)*
* **Digest posture:** token-less; **do not embed any digest field in-file**. The digest is tracked by 5B.S0 sealing inventory.

---

## 2) Scope (what this policy must cover)

This single policy MUST cover the following 5B RNG families:

### S2 (latent realisation)

* `module = "5B.S2"`
* `substream_label = "latent_vector"`

### S3 (bucket counts)

* `module = "5B.S3"`
* `substream_label = "bucket_count"`

### S4 (arrival synthesis)

* `module = "5B.S4"`
* `substream_label = "arrival_time_jitter"`
* `module = "5B.S4"`
* `substream_label = "arrival_site_pick"`
* `module = "5B.S4"`
* `substream_label = "arrival_edge_pick"`

If any of these are missing → FAIL CLOSED.

---

## 3) Engine + uniform law (MUST)

The policy MUST pin:

* `rng_engine: philox2x64-10`
* `block_outputs_u64: 2`  *(each Philox block yields exactly 2×u64)*
* `uniform_law: open_interval_u64`

**Pinned open-interval mapping:**

* given `x` as uint64,
* `u = (x + 0.5) / 2^64`
* so `u ∈ (0,1)` (never 0, never 1).

---

## 4) Counter semantics (MUST)

* Counters are **128-bit** `(hi, lo)` unsigned.
* Each event consumes an integer number of **Philox blocks**.
* For an event with `draws_u64 = D`:

  * `blocks = ceil(D / 2)`
  * the event consumes exactly `blocks` sequential counters
  * the event yields the first `D` u64 outputs from those blocks (discard at most 1 unused u64 on the last block)
* The RNG envelope for each event MUST record:

  * `rng_counter_before_{hi,lo}`
  * `rng_counter_after_{hi,lo} = rng_counter_before + blocks`
  * `draws` as decimal string `D`
  * `blocks` as integer `blocks`

**Wrap policy:** `abort_on_wrap` (any counter overflow is a hard failure).

---

## 5) Key / counter derivation law (MUST; decision-free)

To guarantee *no overlap* and *replayability*, v1 uses **per-event derived key + per-event derived base counter**.

### 5.1 Canonical encoding primitives

Define:

* `UER(s)` = 4-byte big-endian length prefix + UTF-8 bytes of string `s`
* `LE64(n)` = 8-byte little-endian encoding of uint64 `n`
* `BE64(bytes8)` = interpret 8 bytes as uint64 big-endian

### 5.2 Derivation inputs (MUST be available; no fallback)

Every derivation MUST include all of:

* `manifest_fingerprint` (hex64 string)
* `parameter_hash` (hex64 string)
* `seed` (uint64)
* `scenario_id` (string)
* `family_id` (string; see §6)

If any is missing at runtime → FAIL CLOSED.

**Important:** `run_id` is **log-only** and MUST NOT be included in key/counter derivation (reruns must reproduce identical outputs).

### 5.3 Derivation function

For each event, build message bytes:

```
msg = UER("5B.rng.v1")
    || UER(family_id)
    || UER(manifest_fingerprint)
    || UER(parameter_hash)
    || LE64(seed)
    || UER(scenario_id)
    || UER(domain_key_string)
```

Where `domain_key_string` depends on family (see §6).

Compute:

* `h = SHA256(msg)` (32 bytes)

Derive:

* `key_u64 = BE64(h[0:8])`
* `counter_hi = BE64(h[8:16])`
* `counter_lo = BE64(h[16:24])`

So each event uses:

* `philox_key = key_u64`
* `rng_counter_before = (counter_hi, counter_lo)`

This makes overlaps astronomically unlikely; still, validators MAY optionally scan for duplicates in debug/CI.

---

## 6) Families, domain keys, and budgets (MUST)

The policy MUST define **exactly** these families (IDs pinned), each with:

* `module`
* `substream_label`
* `family_id` (string used in derivation)
* `domain_key_law`
* `draws_u64_law`

### 6.1 S2 latent vector

* `module: "5B.S2"`
* `substream_label: "latent_vector"`
* `family_id: "S2.latent_vector.v1"`

**Domain key string (MUST):**

```
"group_id=<group_id>"
```

(one event per `(scenario_id, group_id)`)

**Draw budget law (v1 pinned):**
This policy pins a specific normal-draw method so budgets are checkable:

* `standard_normal_method: box_muller_u2`
* `uniforms_per_standard_normal: 2`

Let:

* `H = number_of_horizon_buckets` for this scenario (from `s1_time_grid_5B`)
* `latent_dims = H`  (v1: one latent value per horizon bucket)

Then:

* `draws_u64 = uniforms_per_standard_normal * latent_dims`
* `blocks = ceil(draws_u64 / 2)`

If your LGCP config later changes the latent dimensionality, that is a **policy version bump** (do not silently reinterpret).

### 6.2 S3 bucket count

* `module: "5B.S3"`
* `substream_label: "bucket_count"`
* `family_id: "S3.bucket_count.v1"`

**Domain key string (MUST):**

```
"merchant_id=<merchant_id>|zone=<zone_representation>|bucket_index=<bucket_index>"
```

**Draw budget law (MUST):**
Budgets depend on the count-law selected in `arrival_count_config_5B`:

* If `lambda_realised == 0` (or count config’s “force zero” condition holds):

  * `draws_u64 = 0`, `blocks = 0` (and the state MUST emit `count_N = 0` deterministically)
* Else choose by `count_law`:

  * `poisson`: `draws_u64 = 1`
  * `nb2`: `draws_u64 = 2`

`arrival_count_config_5B.count_law_id` MUST be one of `{poisson, nb2}` in v1. Anything else → FAIL CLOSED.

### 6.3 S4 time placement

* `module: "5B.S4"`
* `substream_label: "arrival_time_jitter"`
* `family_id: "S4.arrival_time_jitter.v1"`

**Domain key string (MUST):**

```
"merchant_id=<merchant_id>|zone=<zone_representation>|bucket_index=<bucket_index>|arrival_seq=<arrival_seq>"
```

**Draw budget law (v1 pinned):**

* `draws_u64 = 1` (one uniform per arrival timestamp)

### 6.4 S4 physical routing

* `module: "5B.S4"`
* `substream_label: "arrival_site_pick"`
* `family_id: "S4.arrival_site_pick.v1"`

**Domain key string (MUST):**
same as §6.3 (per arrival identity)

**Draw budget law (v1 pinned):**

* `draws_u64 = 2`
  Interpretation: one uniform for tz-group selection (if applicable) + one uniform for alias site selection.

*(If you later wire S4 to reuse 2B’s router streams with different semantics, that’s a version bump—don’t silently change draw counts.)*

### 6.5 S4 virtual routing

* `module: "5B.S4"`
* `substream_label: "arrival_edge_pick"`
* `family_id: "S4.arrival_edge_pick.v1"`

**Domain key string (MUST):**
same as §6.3 (per arrival identity)

**Draw budget law (v1 pinned):**

* `draws_u64 = 1` (one uniform for edge alias selection)

---

## 7) Required ordering (MUST; for replay and audit)

Even with per-event derived counters, 5B MUST emit RNG events in deterministic order so validators can replay and reconcile cheaply.

Pinned emission order:

### S2

* Iterate `(scenario_id ↑, group_id ↑)` and emit exactly one latent event per pair.

### S3

* Iterate `(scenario_id ↑, merchant_id ↑, zone_representation ↑, bucket_index ↑)` over the domain processed.

### S4

For each `(scenario_id, merchant_id, zone_representation, bucket_index)`:

* iterate `arrival_seq` ascending, and for each arrival:

  1. emit `arrival_time_jitter` event
  2. emit `arrival_site_pick` event for NON_VIRTUAL and HYBRID (HYBRID uses this draw to decide routing)
  3. after routing decision, if `is_virtual=true`, emit `arrival_edge_pick` event

Any deviation → hard failure in validation.

---

## 8) Realism floors (MUST; prevents “toy RNG policy”)

Codex MUST reject authoring if any fail:

* All 5 families present with the exact `module` + `substream_label` set in §2.
* All `family_id` values are unique and namespaced (`S2.*`, `S3.*`, `S4.*`).
* `parameter_hash`, `manifest_fingerprint`, `seed`, `scenario_id` are declared **required** derivation inputs (no fallbacks).
* `uniform_law` is open-interval and `rng_engine` is Philox 2×64-10.
* Draw budgets are strictly pinned (no “TBD”, no “variable unless…” beyond the explicit `lambda==0` rule in §6.2).
* Wrap policy is `abort_on_wrap`.

---

## 9) Recommended v1 file (copy/paste baseline)

```yaml
policy_id: arrival_rng_policy_5B
version: v1.0.0

rng_engine: philox2x64-10
block_outputs_u64: 2
uniform_law: open_interval_u64
counter_width_bits: 128
wrap_policy: abort_on_wrap

encoding:
  string_encoding: UTF-8
  uer: u32be_len_prefix
  seed_encoding: LE64
  hash: SHA256
  key_bytes: [0, 8]          # BE64(h[0:8])
  counter_hi_bytes: [8, 16]  # BE64(h[8:16])
  counter_lo_bytes: [16, 24] # BE64(h[16:24])

families:
  - family_id: S2.latent_vector.v1
    module: 5B.S2
    substream_label: latent_vector
    domain_key_law: group_id
    draws_u64_law:
      kind: box_muller_u2_vector
      uniforms_per_standard_normal: 2
      latent_dims: horizon_buckets_H

  - family_id: S3.bucket_count.v1
    module: 5B.S3
    substream_label: bucket_count
    domain_key_law: merchant_zone_bucket
    draws_u64_law:
      kind: by_count_law
      when_lambda_zero: 0
      laws:
        poisson: 1
        nb2: 2

  - family_id: S4.arrival_time_jitter.v1
    module: 5B.S4
    substream_label: arrival_time_jitter
    domain_key_law: arrival_identity
    draws_u64_law: { kind: fixed, draws_u64: 1 }

  - family_id: S4.arrival_site_pick.v1
    module: 5B.S4
    substream_label: arrival_site_pick
    domain_key_law: arrival_identity
    draws_u64_law: { kind: fixed, draws_u64: 2 }

  - family_id: S4.arrival_edge_pick.v1
    module: 5B.S4
    substream_label: arrival_edge_pick
    domain_key_law: arrival_identity
    draws_u64_law: { kind: fixed, draws_u64: 1 }

derivation:
  domain_sep: 5B.rng.v1
  required_inputs: [manifest_fingerprint, parameter_hash, seed, scenario_id, family_id, domain_key]
  forbid_inputs: [run_id]
```

*(No digests, no timestamps.)*

---

## 10) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. `policy_id` and `version` present; version non-placeholder.
3. All required families present; modules/labels match §2.
4. Derivation law uses required inputs and explicitly forbids `run_id`.
5. Budget laws are fully pinned; count-law IDs restricted to `{poisson, nb2}` in v1.
6. Blocks computed as `ceil(draws/2)` and counters advance by `blocks`.
7. Emission ordering rules in §7 enforced.

---

## Placeholder resolution (MUST)

- Replace family IDs with the final list (`latent_vector`, `bucket_count`, `arrival_time_jitter`, `arrival_site_pick`, `arrival_edge_pick`).
- Replace each family’s `draws_u64_law` with the fixed budgets required by the consuming states.
- Replace any example `domain_key_law` strings with the exact key basis used in v1.

