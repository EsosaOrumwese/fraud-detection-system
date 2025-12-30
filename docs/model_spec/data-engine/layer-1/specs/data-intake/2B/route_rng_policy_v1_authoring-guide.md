# Authoring Guide — `route_rng_policy_v1` (2B routing Philox streams + budgets)

This policy is the **governed RNG wiring** for Segment **2B** routing states that emit run-scoped RNG evidence:

* **2B.S5** (router): `alias_pick_group`, `alias_pick_site` (**2 single-uniform draws per arrival**)
* **2B.S6** (virtual edge pick): `cdn_edge_pick` (**1 single-uniform draw per virtual arrival**)

It is sealed in **2B.S0** (token-less, selected by exact path + digest), and validators in S5/S6 **fail closed** if emitted RNG evidence doesn’t match this policy.

---

## 1) File identity (binding)

* **Dictionary ID:** `route_rng_policy_v1`
* **Path:** `contracts/policy/2B/route_rng_policy_v1.json`
* **Format:** JSON
* **Schema anchor:** `schemas.2B.yaml#/policy/route_rng_policy_v1` *(intentionally permissive; this guide pins the real contract)*

Token-less posture:

* The file has **no path tokens**.
* S0 seals its exact bytes (sha256) and all consumers must select it by **S0-sealed path + sha256** (never “latest”, never by token).

---

## 2) What this policy controls (binding)

### 2.1 Routing streams (S5 + S6)

This policy defines two run-scoped Philox “streams” (stream IDs written into diagnostic rows and used as wiring checks):

1. **Routing selection stream** (for S5)

* Used by **both** `alias_pick_group` and `alias_pick_site`
* Must support **exactly two** single-uniform events per arrival

2. **Routing edge stream** (for S6)

* Used by `cdn_edge_pick`
* Must support **exactly one** single-uniform event per virtual arrival

### 2.2 Budgets (hard, audited)

Per-event budgets are **fixed**:

* `alias_pick_group`: `blocks = 1`, `draws = "1"`
* `alias_pick_site`:  `blocks = 1`, `draws = "1"`
* `cdn_edge_pick`:    `blocks = 1`, `draws = "1"`

Per-arrival totals are fixed:

* S5: `draws_per_selection = 2`
* S6: `draws_per_virtual = 1`

---

## 3) Required top-level keys (MUST)

The JSON object MUST contain:

### 3.1 Identity & digest (MUST)

* `policy_id` (string) — MUST equal `"route_rng_policy_v1"`
* `version_tag` (string) — real governance tag (see §8)
* Digest is tracked by the S0 sealing inventory (do NOT embed `sha256_hex` inside the file; token-less posture)
* `rng_engine` (string) — MUST equal `"philox2x64-10"` (wire token)

### 3.2 Stream declarations (MUST)

* `streams` (object) with exactly these keys:

  * `routing_selection`
  * `routing_edge`

Each stream object MUST include:

* `rng_stream_id` (string) — the stream ID written into any diagnostic rows for that stream
* `basis` (object) — substream/key basis for the run (see §6)
* `event_families` (object) — family specs keyed by family name
* `draws_per_unit` (object) — per-arrival totals (`selection` or `virtual`)

Unknown top-level keys are only allowed under `extensions`.

---

## 4) Canonical byte law + inventory digest (MUST)

To avoid ambiguity across implementations, the policy file MUST be written as **canonical JSON** and the digest MUST be recorded externally (S0 sealing inventory):

1. Canonical JSON serialization (UTF-8):

   * sort object keys lexicographically at every level
   * no insignificant whitespace
   * numbers as standard JSON decimals (no NaN/Inf)
2. Compute `policy_sha256_hex = SHA256(canonical_bytes)` as lowercase hex64.
3. Record `policy_sha256_hex` in the S0 sealing inventory for this policy path+bytes.
4. The policy file itself MUST NOT contain a `sha256_hex` field.

---

## 5) Stream specs (binding)

### 5.1 `streams.routing_selection` (S5)

MUST declare:

* `rng_stream_id`: recommend a namespaced, non-toy value: **`"2B.routing"`**
* `event_families` MUST include **exactly**:

```json
{
  "alias_pick_group": { "blocks": 1, "draws": "1", "substream_label": "alias_pick_group" },
  "alias_pick_site":  { "blocks": 1, "draws": "1", "substream_label": "alias_pick_site"  }
}
```

* `draws_per_unit` MUST be:

```json
{ "draws_per_selection": 2 }
```

Binding notes:

* S5 emits **two** event rows per arrival **in order**: group then site.
* Counters must be strictly monotone within the run; per event `after − before == 1` (128-bit).

### 5.2 `streams.routing_edge` (S6)

MUST declare:

* `rng_stream_id`: recommend **`"2B.routing_edge"`**
* `event_families` MUST include **exactly**:

```json
{
  "cdn_edge_pick": { "blocks": 1, "draws": "1", "substream_label": "cdn_edge_pick" }
}
```

* `draws_per_unit` MUST be:

```json
{ "draws_per_virtual": 1 }
```

Binding notes:

* S6 emits **one** event row per virtual arrival; non-virtual arrivals emit **no** S6 RNG evidence.

---

## 6) Basis / substream derivation (MUST; decision-free)

Each stream MUST declare a `basis` object pinning how the stream is keyed for a run.

MUST be:

* `key_basis`: `["seed", "parameter_hash", "run_id"]`
* `counter_start`: `{ "hi": 0, "lo": 0 }`
* `counter_step_per_event`: `1`
* `counter_wrap_policy`: `"abort_on_wrap"`

This matches the routing states' posture:

* run-scoped streams (not merchant-keyed)
* counters are monotone and never reused within a run
* `parameter_hash` is **required** at runtime; if it is missing, the run MUST abort (no fallback keying)

---

## 7) Realism floors (MUST; prevents toy policies)

Codex MUST reject policies that violate any of:

* `rng_engine` is not exactly `"philox2x64-10"`
* `version_tag` is placeholder-like (`"test"`, `"example"`, `"todo"`, `"TBD"`, `"null"`, etc.)
* `streams` missing either `routing_selection` or `routing_edge`
* budgets deviate from single-uniform law (`blocks != 1` or `draws != "1"`)
* per-unit totals deviate (`draws_per_selection != 2`, `draws_per_virtual != 1`)
* `rng_stream_id` values are empty or not namespaced (MUST match `^2B\.[A-Za-z0-9_.-]+$`)
* `basis.key_basis` not exactly `["seed","parameter_hash","run_id"]`

---

## 8) Versioning posture (binding)

* `version_tag` MUST be real semver-ish governance tag, e.g. `v1.0.0`
* Any change that could alter:

  * stream IDs,
  * budgets,
  * basis/counter policy,
  * family set,
    MUST bump `version_tag` and MUST change policy bytes (therefore `policy_sha256_hex` changes in the sealing inventory).

---

## 9) Complete v1 production policy (example; non-toy)

```json
{
  "policy_id": "route_rng_policy_v1",
  "version_tag": "v1.0.0",
  "rng_engine": "philox2x64-10",
  "streams": {
    "routing_selection": {
      "rng_stream_id": "2B.routing",
      "basis": {
        "key_basis": ["seed", "parameter_hash", "run_id"],
        "counter_start": { "hi": 0, "lo": 0 },
        "counter_step_per_event": 1,
        "counter_wrap_policy": "abort_on_wrap"
      },
      "event_families": {
        "alias_pick_group": { "substream_label": "alias_pick_group", "blocks": 1, "draws": "1" },
        "alias_pick_site":  { "substream_label": "alias_pick_site",  "blocks": 1, "draws": "1" }
      },
      "draws_per_unit": { "draws_per_selection": 2 }
    },
    "routing_edge": {
      "rng_stream_id": "2B.routing_edge",
      "basis": {
        "key_basis": ["seed", "parameter_hash", "run_id"],
        "counter_start": { "hi": 0, "lo": 0 },
        "counter_step_per_event": 1,
        "counter_wrap_policy": "abort_on_wrap"
      },
      "event_families": {
        "cdn_edge_pick": { "substream_label": "cdn_edge_pick", "blocks": 1, "draws": "1" }
      },
      "draws_per_unit": { "draws_per_virtual": 1 }
    }
  },
  "extensions": {}
}
```

---

## 10) Acceptance checklist (Codex MUST enforce)

1. JSON parses; required keys present.
2. `policy_id == "route_rng_policy_v1"`.
3. `rng_engine == "philox2x64-10"`.
4. File is canonical JSON per §4 and `policy_sha256_hex = SHA256(file_bytes)` is recorded in the S0 sealing inventory; file MUST NOT contain `sha256_hex`.
5. Both streams present with namespaced `rng_stream_id`.
6. Budgets are single-uniform (`blocks=1`, `draws="1"`) for all families.
7. Totals are correct (`draws_per_selection=2`, `draws_per_virtual=1`).
8. `basis.key_basis` exactly `["seed","parameter_hash","run_id"]`, counter rules as §6.
9. No placeholders in `version_tag`.

If any check fails → **FAIL CLOSED** (do not emit/overwrite; do not seal).

---

## Placeholder resolution (MUST)

* Replace all placeholder values (e.g., "TODO", "TBD", "example") before sealing.
* Remove or rewrite any "stub" sections so the guide is decision-free for implementers.
