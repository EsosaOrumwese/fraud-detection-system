# Segment 2A — Design vs Implementation Observations (Civil Time)
Date: 2026-01-30
Scope: Design intent vs implementation notes for Segment 2A (S0–S5) before dataset assessment.

---

## 0) Why this report exists
Segment 2A is the **civil‑time assignment layer**. It takes site coordinates from 1B and produces per‑site time zones plus a validation gate. This report records what the design expects **and what the implementation actually does**, including deviations, strictness decisions, and any risks those choices introduce. This is meant to guide the upcoming realism assessment of 2A outputs.

---

## 1) Design intent (what 2A should do)
At a high level, 2A is a deterministic pipeline:

1) **S0 — Gate & sealed inputs**
   - Verify 1B PASS gate (“No PASS → No Read”).
   - Seal all required 2A inputs (site_locations, tz_world, tzdb_release, overrides, nudge policy, etc.).
   - Emit a fingerprint‑scoped receipt + sealed‑inputs inventory.

2) **S1 — Provisional TZ lookup**
   - Map each site’s lat/lon to a provisional tzid using tz_world polygons.
   - Apply a deterministic ε‑nudge at boundaries; record nudge fields.
   - Only consult tz_overrides for post‑nudge ambiguity (site > mcc > country).

3) **S2 — Overrides & finalisation**
   - Apply overrides when S1 says “override_applied=true”.
   - Enforce strict provenance + tzid membership and emit final `site_timezones`.

4) **S3 — Timetable cache**
   - Compile tzdb into a manifest_fingerprint‑scoped cache for downstream legality checks.

5) **S4 — Legality report**
   - Use the cache to compute DST gap/fold windows per tzid and emit a report.

6) **S5 — Validation bundle + PASS flag**
   - Bundle S3 + S4 evidence and write `_passed.flag` as the consumer gate for 2A egress.

---

## 2) Expected outputs & evidence surfaces (contract view)
Key datasets produced by 2A (from the contracts):
- `s0_gate_receipt_2A`, `sealed_inputs_2A` (S0)
- `s1_tz_lookup` (S1, plan)
- `site_timezones` (S2, egress)
- `tz_timetable_cache` (S3, cache)
- `s4_legality_report` (S4, validation evidence)
- `validation_bundle_2A` + `index.json` + `_passed.flag` (S5 gate)

These are the surfaces we will evaluate when we assess realism and correctness in later steps.

---

## 3) Implementation observations (what is actually done)

### 3.1 S0 — Gate & sealed inputs
**Observed posture:** S0 is fully implemented and extremely strict about gates, sealing, and determinism.

Key observations:
- **PASS verification is enforced before any read** of 1B egress. The `_passed.flag` hash is recomputed from the bundle index in ASCII‑lex order and must match exactly.
- **Run identity is hard‑fixed** from `run_receipt.json`. If `parameter_hash` or `manifest_fingerprint` is missing, S0 hard‑fails. No CLI fallback.
- **Sealed inputs are minimal by design.** `iso3166_canonical_2024` and `world_countries` are omitted unless explicitly required downstream.
- **tzdb_release resolution is deterministic.** If `{release_tag}` is unresolved, S0 scans `artefacts/priors/tzdata/` for exactly one valid release folder. Multiple candidates or no candidate aborts.
- **Schema validation issues were fixed by local $ref rewriting.** External refs in schema packs are rewritten into local `$defs` to avoid runtime resolver failures.
- **tz_world validity enforced** (CRS=WGS84, non‑empty geometry set).
- **Overrides now require tzid membership enforcement.** tzids are derived from tz_world; any override tzid not in tz_world is a hard failure.
- **Stricter failure when overrides exist but tzid index can’t be derived.** If overrides are non‑empty and tzid index cannot be built, S0 aborts (fail‑closed).
- **Deterministic timestamps:** S0 uses `run_receipt.created_utc` for `verified_at_utc` and sealed input rows to allow byte‑identical reruns.
- **Determinism receipt + run-report** are emitted; these are not identity‑bearing but record audit state.

Net result: S0 is **strict, deterministic, and gate‑heavy**, matching the spec’s contract posture and “No PASS → No Read” law.

---

### 3.2 S1 — Provisional TZ lookup
**Observed posture:** Implemented, but with **a deliberate spec deviation** to avoid run aborts.

Key observations:
- **Base logic matches spec:** point‑in‑polygon tzid assignment with ε‑nudge; override fallback only for post‑nudge ambiguity.
- **Inputs expanded in spec + implementation:** `tz_overrides` + optional `merchant_mcc_map` are explicitly consumed for ambiguity fallback.
- **Spec deviation introduced:** When post‑nudge ambiguity still remains and no override applies, S1 **no longer aborts**. Instead:
  - It picks the **nearest tz_world polygon in the same country ISO**.
  - If the nearest polygon is beyond the epsilon‑derived threshold, it still selects it to preserve 1:1 coverage but logs a WARN and records the event in the run‑report.
- **Output schema unchanged** (still `columns_strict`), and provenance remains `tzid_provisional_source="polygon"` with `override_applied=false` to avoid breaking S2.
- **Diagnostics improved**: candidate tzids for unresolved ambiguities are included in error payloads and run‑report samples.

Impact:
- This is a **controlled deviation** from fail‑closed behavior. It prevents pipeline aborts but may hide genuine geographic boundary issues unless carefully reviewed in the report diagnostics.

---

### 3.3 S2 — Overrides & finalisation
**Observed posture:** Implemented and strict, aligned with the spec.

Key observations:
- **Override precedence and expiry enforcement** follow the spec (site > mcc > country; active by S0 receipt date).
- **Strict MCC gating**: if MCC overrides are active and no `merchant_mcc_map` is sealed, S2 aborts.
- **tzid membership is enforced** against tz_world; any unknown tzid aborts.
- **`override_no_effect` is fatal** if an override applies but does not change the tzid (spec‑aligned).
- **created_utc is deterministic** and forced to S0 receipt time.

Known friction:
- A country‑level override that matches the provisional tzid will **always abort** (`2A‑S2‑055`). The implementation calls this out and requires a policy fix or a design change; no silent relaxation is applied.

---

### 3.4 S3 — Timetable cache
**Observed posture:** Implemented with deterministic compilation rules.

Key observations:
- **Cache is manifest_fingerprint‑scoped** and derived strictly from sealed tzdb_release.
- **Canonicalisation + digest** are enforced to keep `tz_index_digest` stable.
- **Deterministic created_utc** is tied to S0 receipt (no wall‑clock).
- **Spec update applied** (sentinel exception for offset bounds) to align compilation edge cases with validators.

---

### 3.5 S4 — Legality report
**Observed posture:** Implemented as a strict validation evidence report.

Key observations:
- Reads `site_timezones` + `tz_timetable_cache` and emits aggregate counts only.
- Does **not** mutate or override tzids; the report is strictly evidence.
- Uses S0 receipt time for deterministic timestamps.

---

### 3.6 S5 — Validation bundle + PASS flag
**Observed posture:** Implemented; enforces seed discovery and evidence completeness.

Key observations:
- Discovers **all seeds** with `site_timezones` under the manifest_fingerprint.
- Requires a **PASS legality report per seed**; otherwise aborts.
- Builds the bundle index and `_passed.flag` using the ASCII‑lex raw‑bytes law.
- Emits a manifest_fingerprint‑scoped validation gate for downstream consumers.

---

## 4) Deviations & risk notes
1) **S1 ambiguity fallback (spec deviation):** runs no longer fail on unresolved boundary ambiguity; nearest‑polygon fallback is used instead. This is deterministic but can be geographically inaccurate when the nearest polygon is outside the nudge threshold. The run‑report diagnostics are now critical evidence and should be reviewed.

2) **Strict override_no_effect in S2:** country‑level overrides can cause aborts if they match provisional tzids. This makes policy authoring brittle; policy needs to be precise or the spec posture should be revisited.

3) **tzid membership enforcement moved into S0 (strict):** overrides now fail closed if tzid index can’t be derived. This tightens correctness but will block runs if tz_world tzid extraction fails.

---

## 5) Implications for upcoming data assessment
When we assess Segment 2A outputs, we will pay special attention to:
- Evidence of S1 fallback usage (run‑report diagnostics).
- Distribution of `tzid_source` vs `override_scope` in `site_timezones`.
- Whether overrides are narrow enough to avoid `override_no_effect` failures.
- Coverage of tzids vs tz_world and cache consistency.

---

(Next: detailed assessment of the actual 2A outputs under your run folder.)
