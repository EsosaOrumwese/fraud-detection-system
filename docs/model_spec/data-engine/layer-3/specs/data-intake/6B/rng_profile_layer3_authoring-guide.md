# Authoring Guide — `rng_profile_layer3` (Layer-3 Philox invariants, v1)

## 0) Purpose

`rng_profile_layer3` is the **single sealed authority** for the **Layer-3 RNG law** used by 6B’s RNG policies (`rng_policy_6B`, `flow_rng_policy_6B`, `fraud_rng_policy_6B`, `label_rng_policy_6B`). It pins:

* **PRNG engine token** + counter/key widths
* **open-interval** mapping `u ∈ (0,1)` from `uint64` lanes
* **lane policy** (low lane vs both lanes; no caching)
* **budget accounting law** (`draws` vs `blocks`)
* **keyed, order-invariant substream derivation** (hash framing + encodings)

It is a **required** control-plane pack, consumed by `6B.S0–6B.S4`.

---

## 1) File identity (MUST)

From the 6B contracts:

* **manifest_key:** `mlr.6B.policy.rng_profile_layer3` 
* **dataset_id:** `rng_profile_layer3` 
* **path:** `config/layer3/6B/rng_profile_layer3.yaml` 
* **schema_ref:** `schemas.6B.yaml#/policy/rng_profile_layer3`
* **status:** required; **consumed_by:** `6B.S0`, `6B.S1`, `6B.S2`, `6B.S3`, `6B.S4` 

Token-less posture:

* **No** timestamps, UUIDs, or digests inside the YAML.
* Integrity is tracked via `sealed_inputs_6B.sha256_hex` produced by `6B.S0`.

---

## 2) Scope (what this file does and does not do)

### In scope

* Defines the **shared RNG law** that all 6B RNG policies reference.
* Defines **substream keying**, **open-interval uniform mapping**, and **budget semantics**.
* Defines **standard normal primitive** (Box–Muller, no cache) *for any policy that needs it*.

### Out of scope

* Naming/declaring 6B **RNG families** and their per-decision budgets (that belongs in the per-state RNG policies).
* Any behavioural “business logic” (attachment, flows, campaigns, labels).

---

## 3) Engine + counter semantics (MUST)

### 3.1 PRNG token (MUST)

* `rng_engine: philox2x64-10`
* Each Philox block yields exactly **2×u64 lanes** `(x0, x1)`.

(Use the same wire token already used across the engine.)

### 3.2 Counter representation (MUST)

* Counter is **128-bit**, stored as `(hi:u64, lo:u64)` with **unsigned 128-bit add with carry**.
* A **block** consumes exactly **1** counter step.

### 3.3 Wrap policy (MUST)

* `wrap_policy: abort_on_wrap`
  If any event would require counter overflow, the run must abort (hard failure).

---

## 4) Open-interval uniform law (MUST)

v1 pins the **strict-open** mapping used elsewhere in the project’s RNG contracts (hex-literal, clamp-to-open):

```text
# x is uint64 lane
u = ((x + 1) * 0x1.0000000000000p-64)
if u == 1.0: u := 0x1.fffffffffffffp-1   # 1 - 2^-53
```

Rules:

* The multiplier MUST be written exactly as the **binary64 hex literal** `0x1.0000000000000p-64`. 
* Produces `u ∈ (0,1)` in binary64 (never 0.0, never 1.0).

---

## 5) Lane policy + multi-uniform budgeting (MUST)

### 5.1 Lane usage

* **Single-uniform** decisions consume **`x0` only** and discard `x1`.
* **Two-uniform** decisions consume **both** `x0,x1` from the same block (e.g., Box–Muller).
* **No caching** across events (never reuse an unused lane in a later event).

### 5.2 `draws` vs `blocks`

* `draws` = number of `U(0,1)` uniforms consumed (**decimal u128 string** conceptually)
* `blocks` = number of Philox blocks advanced (**u64**)

Pinned v1 relationship for *any* consuming event with `draws = D`:

* `blocks = ceil(D / 2)`
* Within an event, uniforms are taken in lane order: `x0` then `x1` across consecutive blocks, stopping after `D` uniforms, discarding the final unused lane if `D` is odd.

Non-consuming event:

* `draws = "0"`, `blocks = 0`

This is the basic budget law that all 6B RNG policies will rely on.

---

## 6) Standard normal primitive (Pinned if used)

If any 6B policy needs `Z ~ N(0,1)`, v1 uses **Box–Muller (no cache)** with a pinned TAU constant:

* `TAU = 0x1.921fb54442d18p+2` (hex literal)
* One normal consumes:

  * `draws = "2"` uniforms (u1,u2),
  * `blocks = 1`
* **Discard** the sine mate (no caching).

---

## 7) Keyed, order-invariant substreams (MUST)

v1 adopts the same general “keyed substream” pattern used in upstream RNG contracts (UER/SER framing + SHA-256), but with 6B domain tags.

### 7.1 Encodings (MUST)

* **UER(string):** UTF-8 bytes prefixed by **LE32 length**, concatenated without delimiters.
* **SER(u64):** LE64
* **SER(index):** LE32 (0-based, unsigned)
* **ISO codes:** uppercase ASCII before encoding (when used as ids).

### 7.2 Master material (per `(manifest_fingerprint, seed)`)

Let `fp_bytes` be the 32-byte fingerprint and `seed` be u64.

* `M = SHA256( UER("mlr:6B.master") || fp_bytes || LE64(seed) )`

### 7.3 Substream derivation (per event family label + id tuple)

For label `ℓ` (string literal) and ordered `ids`:

* `msg = UER("mlr:6B") || UER(ℓ) || SER(ids)`
* `H = SHA256( M || msg )`
* `key = LOW64(H)` where `LOW64` is bytes `24..31` interpreted as **LE64** (pinned).
* `counter_base = ( BE64(H[16:24]), BE64(H[24:32]) )` (hi,lo)

This ensures substreams are **order-invariant** (no dependence on execution order).

---

## 8) Required YAML structure (fields-strict by this guide)

Top-level YAML object with **exactly**:

1. `policy_id` (MUST be `rng_profile_layer3`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `rng_engine` (MUST be `philox2x64-10`)
4. `philox` (object)
5. `counter` (object)
6. `uniform_u01` (object)
7. `lane_policy` (object)
8. `budget_law` (object)
9. `normal_z` (object)
10. `substreams` (object)
11. `guardrails` (object)
12. `notes` (optional)

Unknown keys ⇒ **FAIL CLOSED**.

---

## 9) Recommended v1 policy file (copy/paste baseline)

```yaml
policy_id: rng_profile_layer3
version: v1.0.0

rng_engine: philox2x64-10

philox:
  rounds: 10
  lanes_per_block_u64: 2
  key_bits: 64
  counter_bits: 128

counter:
  representation: { hi: uint64, lo: uint64 }
  arithmetic: unsigned_128_add_with_carry
  increment_per_block: 1
  wrap_policy: abort_on_wrap

uniform_u01:
  law_id: strict_open_interval_u64_v1
  u_from_u64:
    expr: "u = ((x + 1) * 0x1.0000000000000p-64); if u == 1.0: u = 0x1.fffffffffffffp-1"
  forbid_decimal_substitutes: true

lane_policy:
  single_uniform: { uses: x0, discards: x1 }
  two_uniform: { uses: [x0, x1], same_block: true }
  cache_across_events: false

budget_law:
  draws_type: dec_u128_string
  blocks_type: uint64
  blocks_from_draws: "blocks = ceil(draws / 2)"
  lane_order: [x0, x1]
  non_consuming: { draws: "0", blocks: 0 }

normal_z:
  enabled: true
  law_id: box_muller_no_cache_v1
  tau_hex: 0x1.921fb54442d18p+2
  draws_per_z: "2"
  blocks_per_z: 1
  discard_sine_mate: true

substreams:
  master_domain: "mlr:6B.master"
  msg_domain: "mlr:6B"
  encodings:
    uer_string: "LE32_len || utf8"
    ser_u64: "LE64"
    ser_index_u32: "LE32 (0-based)"
    iso_uppercase: true
  derivation:
    master_material: "M = SHA256(UER(master_domain) || fingerprint_bytes || LE64(seed))"
    substream_hash: "H = SHA256(M || UER(msg_domain) || UER(label) || SER(ids))"
    key: "LOW64_LE(H[24:32])"
    counter_base: "hi=BE64(H[16:24]); lo=BE64(H[24:32])"

guardrails:
  forbid_rng_without_policy: true
  forbid_event_lane_reuse: true
  require_open_interval_u01: true
```

---

## 10) Acceptance checklist (Codex MUST enforce)

1. YAML parses; keys exactly as §8.
2. `policy_id == rng_profile_layer3` and `rng_engine == philox2x64-10`.
3. `uniform_u01` uses the pinned strict-open law (hex literal + clamp).
4. `budget_law.blocks_from_draws` is `ceil(draws/2)` and non-consuming is `(draws="0", blocks=0)`.
5. `substreams` derivation is order-invariant and uses the pinned encoding rules. 
6. Token-less posture: no timestamps/digests embedded; sealing handles digests.

---

## Non-toy/realism guardrails (MUST)

- Do not change `rng_engine`, open-interval law, or lane policy without a formal spec update.
- `blocks = ceil(draws/2)` is mandatory for all consuming events; no alternative accounting.
- Box-Muller (no cache) is the only allowed normal primitive; TAU must match the pinned hex literal.
- Any deviation from these laws must fail closed at S0.

## Placeholder resolution (MUST)

* Replace all placeholder values (e.g., "TODO", "TBD", "example") before sealing.
* Remove or rewrite any "stub" sections so the guide is decision-free for implementers.
