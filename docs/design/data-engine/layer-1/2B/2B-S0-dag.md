```
        LAYER 1 · SEGMENT 2B — STATE S0 (GATE & ENVIRONMENT SEAL)  [NO RNG]

Authoritative inputs (read-only at S0 entry)
--------------------------------------------
[Schema+Dict] Schema & catalogue authority:
    - schemas.layer1.yaml                (layer-wide RNG/log/core schemas; hashing & bundle index law)
    - schemas.1B.yaml                    (1B egress + validation bundle shapes)
    - schemas.2A.yaml                    (2A shapes for optional pins: site_timezones, tz_timetable_cache)
    - schemas.2B.yaml                    (2B shapes incl. s0_gate_receipt_2B & sealed_inputs_2B)
    - schemas.ingress.layer1.yaml        (global layer ingress / common validation shapes)
    - dataset_dictionary.layer1.1B.yaml  (IDs/paths/partitions for 1B datasets incl. validation bundle + site_locations)
    - dataset_dictionary.layer1.2A.yaml  (IDs/paths/partitions for 2A egress/cache if pinned)
    - dataset_dictionary.layer1.2B.yaml  (IDs/paths/partitions for 2B datasets incl. s0_gate_receipt_2B, sealed_inputs_2B)
    - artefact_registry_2B.yaml          (bindings for 2B S0 outputs + referenced upstream artefacts)

[1B Gate Artefacts] (fingerprint-scoped; S0’s primary subject):
    - validation_bundle_1B/              @ data/layer1/1B/validation/fingerprint={manifest_fingerprint}/
        · contains MANIFEST + rng_accounting + egress_checksums + s9_summary + index.json + other non-flag files
    - validation_passed_flag_1B          @ .../validation/fingerprint={manifest_fingerprint}/_passed.flag
        · single-line text: `sha256_hex = <hex64>`; sole consumer gate for 1B egress (No PASS → No Read)

[2B Ingress & Policy] Inputs S0 will seal for 2B (minimum required set):
    - site_locations                     (1B egress; partitions [seed, fingerprint]; final_in_layer for 1B)
    - route_rng_policy_v1                (RNG sub-stream + budget policy for 2B routing states)
    - alias_layout_policy_v1             (alias-table byte layout, endianness, alignment)
    - day_effect_policy_v1               (daily gamma / effect policy for S3/S4)

[Optional pins from 2A] (all-or-none; read-only; S0 may seal them, but does not require them):
    - site_timezones                     (2A egress; partitions [seed, fingerprint])
    - tz_timetable_cache                 (2A S3 cache; partition [fingerprint])

[Numeric, RNG & identity law] (S0 is RNG-free; laws still apply):
    - numeric_policy.json, math_profile_manifest.json
        · binary64, round-to-nearest-even, no FMA/FTZ/DAZ for decision maths
    - RNG posture:
        · S0 **consumes no RNG**; it only seals policy packs that later govern 2B’s Philox sub-streams.
    - Layer-1 bundle hashing law:
        · SHA-256 over raw bytes of all files listed in validation_bundle.index.json (relative paths, ASCII-lex order),
          `_passed.flag` excluded from both list and hash.
    - Global lineage / partition discipline:
        · path↔embed equality for `{seed, manifest_fingerprint}` in S0 outputs,
        · write-once partitions; stage → fsync → atomic move; file order is non-authoritative.


----------------------------------------------------------------------
DAG — 2B.S0 (Upstream 1B gate → sealed inputs inventory → 2B gate receipt)  [NO RNG]

[Schema+Dict],
[Numeric, RNG & identity law]
                ->  (S0.1) Authority rails, run identity & catalogue snapshot
                    - Capture `{seed, manifest_fingerprint}` from the caller; treat both as fixed for the run.
                    - Resolve Layer-1 / 1B / 2A / 2B schema packs & dataset dictionaries by ID (no literal paths).
                    - Mark JSON-Schema as sole shape authority; Dictionary is IDs→paths/partitions/format.
                    - Snapshot catalogue versions into a `catalogue_resolution{dictionary_version, registry_version}` record.
                    - Configure the resolver for this state:
                        · **Dictionary-only resolution** (no free-form paths),
                        · all selections for 2B.S0 outputs are fingerprint-only (`fingerprint={manifest_fingerprint}`).
                    - Confirm S0’s posture:
                        · RNG-free, no network I/O,
                        · only performs gate + sealing; no routing logic, no alias building, no day-effects.

[Schema+Dict],
[1B Gate Artefacts],
[Numeric, RNG & identity law]
                ->  (S0.2) Verify upstream 1B PASS (No PASS → No Read)
                    - Resolve the 1B validation bundle root and `_passed.flag` via Dictionary IDs for this fingerprint.
                    - Load `index.json` from the bundle; enforce index hygiene:
                        · every non-flag file listed exactly once,
                        · all `index.path` entries are **relative**, ASCII-clean, and ASCII-lex-sortable.
                    - Stream the raw bytes of each indexed file **in ASCII-lex order of `index.path`**, concatenate, and compute SHA-256.
                    - Parse `_passed.flag` and assert it matches the canonical format: `sha256_hex = <hex64>`.
                    - Compare recomputed bundle hash to the flag value:
                        · **match → PASS**: 1B egress is authorised for this `manifest_fingerprint`.
                        · **missing/mismatch → Abort** with `BUNDLE_FLAG_HASH_MISMATCH` / `FLAG_FORMAT_INVALID`.
                    - Record the validated bundle path and hash into S0’s working context (to later embed in the receipt).

(S0.2 PASS),
[Schema+Dict]
                ->  (S0.3) Resolve & seal minimum 2B inputs (site + policies)
                    - Resolve required 2B ingress assets **by ID** only:
                        · `site_locations @ seed={seed} / fingerprint={manifest_fingerprint}`,
                        · `route_rng_policy_v1`, `alias_layout_policy_v1`, `day_effect_policy_v1`
                          (token-less; each resolved by the exact path + sha256_hex sealed in S0, not by {seed,fingerprint}).
                    - For each resolved asset:
                        · capture its **partition** object (e.g. `{seed, fingerprint}` or `{fingerprint}`),
                        · attach the governing `schema_ref` from the Dictionary,
                        · determine a `version_tag` from the catalogue (e.g. producer’s semver or `{seed}.{fingerprint}` as declared).
                    - For each asset, compute / obtain a `sha256_hex` digest for `sealed_inputs_2B`:
                        · prefer a published canonical digest from the producing segment’s manifest, if available,
                        · otherwise, hash the raw bytes of the asset (dataset or bundle) at the resolved path,
                          excluding transient control files like `_passed.flag`.
                    - If any of the minimum required IDs cannot be resolved, **Abort** with `MINIMUM_SET_MISSING`.
                    - Build an in-memory sealed-inputs set: `{id, partition, schema_ref, version_tag, sha256_hex, path}`.

(S0.3 sealed set),
[Schema+Dict]
                ->  (S0.4) Optional pins from 2A (all-or-none)
                    - If this fingerprint is configured to pin 2A surfaces, resolve both by ID:
                        · `site_timezones @ seed={seed} / fingerprint={manifest_fingerprint}`,
                        · `tz_timetable_cache @ fingerprint={manifest_fingerprint}`.
                    - If **both** resolve:
                        · treat them as additional sealed assets,
                        · compute `version_tag` + `sha256_hex` using the same law as in (S0.3),
                        · append rows to the sealed-inputs working set.
                    - If **exactly one** resolves:
                        · record a **non-fatal WARN** (`OPTIONAL_PINS_MIXED`) with `present_ids[]`/`absent_ids[]`,
                        · do **not** treat either as authoritative pins for 2B; omit both from the final sealed set.
                    - If **neither** resolves:
                        · leave the sealed set unchanged; 2B proceeds without tz coherence pins.

(S0.3–S0.4 sealed set),
[Schema+Dict],
[Numeric, RNG & identity law]
                ->  (S0.5) Emit s0_gate_receipt_2B (fingerprint-scoped gate receipt)
                    - Shape the gate receipt according to `schemas.2B.yaml#/validation/s0_gate_receipt_v1`.
                    - Populate required fields:
                        · `manifest_fingerprint` (must equal the fingerprint path token),
                        · `seed` (echo of run identity),
                        · `parameter_hash` (bound lineage token for 2B; not used as a partition here),
                        · `verified_at_utc` (UTC timestamp recorded once for this fingerprint),
                        · `sealed_inputs[]` — minimal view: `{id, partition, schema_ref}` for each sealed asset,
                        · `catalogue_resolution{dictionary_version, registry_version}`,
                        · `determinism_receipt{engine_commit?, python_version?, platform?, policy_ids?, policy_digests?}`.
                    - Ensure that policy packs listed in `determinism_receipt.policy_ids` correspond exactly to
                      sealed policy rows in `sealed_inputs_2B`.
                    - Enforce **path↔embed equality**:
                        · embedded `manifest_fingerprint` MUST equal `fingerprint={manifest_fingerprint}` in the output path.

(S0.5 receipt),
(S0.3–S0.4 sealed set),
[Schema+Dict]
                ->  (S0.6) Materialise sealed_inputs_2B (inventory) & publish atomically
                    - Construct `sealed_inputs_2B` as a JSON table:
                        · one row per sealed asset with `{asset_id=id, version_tag, sha256_hex, path, partition, schema_ref}`.
                    - Sort rows deterministically by `asset_id`, then `path` to make inventory order stable.
                    - Validate both `s0_gate_receipt_2B` and `sealed_inputs_2B` against their schema anchors.
                    - Check immutability:
                        · target partitions for both outputs (`fingerprint={manifest_fingerprint}`) MUST be empty,
                          or contain **byte-identical** prior outputs from an identical sealed set.
                        · otherwise, Abort with `IMMUTABLE_OVERWRITE`.
                    - Publish both artefacts using write-once discipline:
                        · write to staging paths, fsync, then atomically move into their Dictionary-resolved final paths.
                    - Post-publish:
                        · re-open both outputs, re-check path↔embed equality for `manifest_fingerprint`,
                        · ensure receipt/inventory ID sets match exactly (no extra/missing IDs).

Downstream touchpoints
----------------------
- **2B.S1–S4 (plan-building states):**
    - MUST treat `s0_gate_receipt_2B` as the **segment gate**:
        · proves 1B PASS for this fingerprint (via 1B bundle + `_passed.flag`),
        · enumerates the exact ingress + policy assets they may read (site_locations, 2B policy packs, optional 2A pins).
    - MUST resolve all inputs via IDs and partitions listed in `sealed_inputs_2B`; no new surfaces or literals.
- **2B.S5–S6 (runtime routing & virtual-edge logs):**
    - Inherit `{seed, manifest_fingerprint}` and RNG policy from the sealed S0 environment.
    - MUST NOT introduce new upstream dependencies outside the sealed inputs for this fingerprint.
- **2B.S7–S8 (audit & validation bundle):**
    - Use `sealed_inputs_2B` as the **supply-chain manifest** for what 2B relied on when building routing plans.
    - Build the 2B validation bundle and `_passed.flag` using the same ASCII-lex index + SHA-256 hashing law as S0 used
      when verifying the upstream 1B bundle.
```
