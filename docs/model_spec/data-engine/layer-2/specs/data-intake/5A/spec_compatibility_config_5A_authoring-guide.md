# Authoring Guide — `spec_compatibility_config_5A` (5A.S5 upstream spec-version compatibility matrix)

## 0) Purpose

`spec_compatibility_config_5A` is an **optional validation-level config** that tells **5A.S5** which combinations of upstream spec versions it considers **compatible** when validating a sealed world.

S5 explicitly allows this: it “SHOULD be aware of compatible ranges” of `s1_spec_version..s4_spec_version`, and compatibility enforcement “may be configured” via `spec_compatibility_config_5A`.
It’s also called out in S5’s validation-level config list as the config defining which S1–S4 spec-version combinations are supported.

---

## 1) Inputs (what it governs)

This config is evaluated against the spec-version fields embedded in S1–S4 outputs:

* **S1:** `s1_spec_version` (required in `merchant_zone_profile_5A`) 
* **S2:** `s2_spec_version` (required in `class_zone_shape_5A`) 
* **S3:** `s3_spec_version` (required in `merchant_zone_baseline_local_5A`) 
* **S4:** `s4_spec_version` (required in `merchant_zone_scenario_local_5A`) 

All are semantic-style `MAJOR.MINOR.PATCH` and downstream consumers are expected to support an explicit set of **MAJOR** versions and fail fast otherwise.

---

## 2) Authority boundary (MUST)

* This config **ONLY** governs **compatibility acceptance** (supported majors / supported tuples) and the **posture** when unsupported versions are observed.
* It MUST NOT redefine contracts, schemas, or meanings of S1–S4 outputs; S5 validates those using the upstream specs + policies.

---

## 3) Pinned v1 semantics (decision-free)

### 3.1 Compatibility is MAJOR-first (default v1)

v1 compatibility is determined primarily by the 4-tuple:

`(s1_major, s2_major, s3_major, s4_major)`

Reason: MAJOR bumps are the explicit “breaking change” boundary across S1–S4 and consumers are required to gate on supported MAJORs.

### 3.2 What S5 does on mismatch (MUST be explicit)

S5 may treat unsupported MAJORs as an invariant violation or a configuration-level validation failure; this config pins the posture.

---

## 4) Payload shape (fields-strict)

**Recommended path:** `config/layer2/5A/validation/spec_compatibility_config_5A.v1.yaml`
(Token-less; no timestamps/digests.)
**Schema anchor:** `schemas.5A.yaml#/validation/spec_compatibility_config_5A`

Top-level keys MUST be exactly:

1. `config_id` (MUST be `spec_compatibility_config_5A`)
2. `version` (e.g. `v1.0.0`)
3. `mode` (MUST be `major_matrix_v1`)
4. `supported_majors` (object; §5)
5. `allowed_major_tuples` (list; §6)
6. `enforcement` (object; §7)
7. `notes` (string; optional)

No extra keys.

---

## 5) `supported_majors` (MUST)

Object with keys: `s1`, `s2`, `s3`, `s4`, each an **array of ints**.

Example:

```yaml
supported_majors:
  s1: [1]
  s2: [1]
  s3: [1]
  s4: [1]
```

Interpretation:

* If any observed MAJOR is not in the corresponding list → apply `enforcement.on_unsupported_major`.

---

## 6) `allowed_major_tuples` (MUST)

A list of allowed MAJOR quadruples. Each entry MUST be fields-strict:

* `name` (string)
* `s1_major` (int)
* `s2_major` (int)
* `s3_major` (int)
* `s4_major` (int)

Interpretation:

* After per-state MAJOR checks pass, S5 checks whether the observed quadruple matches any entry.
* If not → apply `enforcement.on_unsupported_tuple`.

This implements the “combinations are supported” requirement.

---

## 7) `enforcement` (MUST)

Fields (enums are pinned):

* `on_missing_version_field` : `FAIL_CLOSED` (v1 MUST)
* `on_unparseable_version` : `FAIL_CLOSED` (v1 MUST)
* `on_unsupported_major` : `FAIL_VALIDATION` | `WARN_AND_CONTINUE`
* `on_unsupported_tuple` : `FAIL_VALIDATION` | `WARN_AND_CONTINUE`
* `failure_check_id` : string (recommended: `SPEC_COMPATIBILITY`)

Notes:

* `FAIL_VALIDATION` means S5 completes deterministically but the world verdict is FAIL and `_passed.flag` must not signal PASS (i.e., treat as configuration-level validation failure).
* `WARN_AND_CONTINUE` is allowed but discouraged for MAJOR mismatches in v1 (you’d be explicitly allowing S5 to “pretend” it understands unknown contracts).

---

## 8) Deterministic authoring algorithm (Codex-no-input)

1. Set `mode = major_matrix_v1`.
2. Default v1 supported majors:

   * `s1:[1], s2:[1], s3:[1], s4:[1]`.
3. Set `allowed_major_tuples` to include at least:

   * `(1,1,1,1)` as `name: stack_v1`.
4. Set enforcement to fail-closed for missing/unparseable versions:

   * `on_missing_version_field = FAIL_CLOSED`
   * `on_unparseable_version = FAIL_CLOSED`
5. Set conservative v1 postures:

   * `on_unsupported_major = FAIL_VALIDATION`
   * `on_unsupported_tuple = FAIL_VALIDATION`

This matches S5’s stated “may treat as invariant violation / config-level failure” posture while staying safe by default.

---

## 9) Recommended v1 example (copy/paste)

```yaml
config_id: spec_compatibility_config_5A
version: v1.0.0
mode: major_matrix_v1

supported_majors:
  s1: [1]
  s2: [1]
  s3: [1]
  s4: [1]

allowed_major_tuples:
  - name: stack_v1
    s1_major: 1
    s2_major: 1
    s3_major: 1
    s4_major: 1

enforcement:
  on_missing_version_field: FAIL_CLOSED
  on_unparseable_version: FAIL_CLOSED
  on_unsupported_major: FAIL_VALIDATION
  on_unsupported_tuple: FAIL_VALIDATION
  failure_check_id: SPEC_COMPATIBILITY

notes: "S5 upstream spec compatibility matrix for S1–S4; MAJOR-gated v1."
```

---

## 10) Acceptance checklist (MUST)

1. YAML parses; no duplicate keys; top-level keys exactly as §4.
2. `config_id` matches exactly; `mode == major_matrix_v1`.
3. `supported_majors` contains exactly `s1/s2/s3/s4` arrays (non-empty).
4. Every tuple in `allowed_major_tuples` uses majors that are included in `supported_majors`.
5. Enforcement fields are present and enums match pinned values.
6. Token-less posture: no timestamps/digests/environment metadata.

