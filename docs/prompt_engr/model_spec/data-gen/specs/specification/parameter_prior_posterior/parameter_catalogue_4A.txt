############################################################
#  PARAMETER CATALOGUE‑FINDER • Sub‑segment 4A             #
############################################################

--- PP 1 ---
Name: Parameter-set hash (manifest fingerprint)
Symbol: $P$
Scope: merchant_location
Prior_type: Deterministic function (SHA-256 digest over artefact set)
Prior_specified: Yes
Calibration_recipe: Yes (enumeration via artefact_loader.py, manifest/artefact_registry.yaml, CI test)
Posterior_validation: Yes (re-enumeration and hash match, manifest comparison, collision check)
Provenance_tag: Yes (manifest, artefact_registry.yaml)
Units: 256-bit hex string
Default_policy: abort (if missing or hash mismatch)
Interface_consumer: All pipeline modules, manifest, row-level provenance, validation logs
Description: Cryptographically signed parameter-set hash across all artefacts, configs, code, and licences—anchors reproducibility.
Anchor: "After the final artefact is processed the accumulator yields a 256‑bit value: the **parameter‑set hash**. That hash is then hex‑encoded and used in three places: (1) as a suffix of the dataset’s root directory name (`synthetic_v1_<hash>`), (2) as the comment string in every Parquet schema (`creator_param_hash=<hash>`), and (3) as a positional argument to the random‑seed generator."
Context: "With source code frozen, `artefact_loader.py` enumerates every artefact path declared in `artefact_registry.yaml`... After the final artefact is processed the accumulator yields a 256‑bit value: the **parameter‑set hash**..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 1 ---

--- PP 2 ---
Name: Master seed for global PRNG
Symbol: $\mathit{master\_seed}$
Scope: merchant_location
Prior_type: Deterministic function (timestamp + hash)
Prior_specified: Yes
Calibration_recipe: Yes (constructed at build, written in manifest, CI hash check)
Posterior_validation: Yes (manifest and replay check, CI seed/PRNG audit)
Provenance_tag: Yes (build manifest, parameter-set hash, run logs)
Units: 128-bit integer (hex)
Default_policy: abort (if missing, drift, or mismatch)
Interface_consumer: All PRNG modules, RNG trace log, random state for every pipeline stream
Description: Deterministic, audit-traceable 128-bit PRNG seed; combines timestamp and parameter-set hash.
Anchor: "The *master seed* is a 128‑bit integer formed by left‑shifting the high‑resolution timestamp in nanoseconds by 64 bits and then XOR‑ing that result with the low 128 bits of the parameter‑set hash. That seed is written into line 5 of the manifest before any stochastic step occurs."
Context: "The generator’s random numbers come from NumPy’s **Philox 2¹²⁸ + AES‑round** counter PRNG. The *master seed* is a 128‑bit integer formed by left‑shifting the high‑resolution timestamp in nanoseconds by 64 bits and then XOR‑ing that result with the low 128 bits of the parameter‑set hash..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 2 ---

--- PP 3 ---
Name: Artefact registry with licence mapping
Symbol: artefact_registry.yaml, license_map
Scope: merchant_location
Prior_type: Deterministic contract (YAML, SHA-256, licence file mapping)
Prior_specified: Yes
Calibration_recipe: Yes (artefact_loader.py, YAML schema, CI validation)
Posterior_validation: Yes (manifest, re-enumeration, missing/drift check, audit/merge block)
Provenance_tag: Yes (artefact_registry.yaml, LICENSES/, manifest)
Units: registry: YAML list; licence: path, SHA-256 digest
Default_policy: abort (if artefact, licence, or mapping missing or mismatched)
Interface_consumer: All pipeline modules, manifest, validation, legal/CI scripts
Description: Governed, auditable registry of all artefacts and licences; every artefact must have a mapped, hash-locked licence.
Anchor: "artefact_registry.yaml... top‑level list of absolute POSIX paths and a `license_map` section pointing each artefact to the full‑text licence file... Simultaneously a `hashlib.sha256()` accumulator ingests `digest\n` bytes for every artefact. Once enumeration ends the accumulator’s hex digest becomes the **parameter‑set hash**..."
Context: "With source code frozen, `artefact_loader.py` enumerates every artefact path declared in `artefact_registry.yaml`... Simultaneously a `hashlib.sha256()` accumulator ingests `digest\n` bytes for every artefact..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 3 ---

--- PP 4 ---
Name: Source, container, and build manifest provenance
Symbol: source_sha1, container_sha, build_manifest_digest
Scope: merchant_location
Prior_type: Deterministic (SHA-1/SHA-256 digests and build manifests)
Prior_specified: Yes
Calibration_recipe: Yes (git commit hash, Dockerfile.lock, manifest; CI log)
Posterior_validation: Yes (manifest cross-check, sibling-container root-fs hash, SourceHashMismatchError)
Provenance_tag: Yes (build manifest, Dockerfile.lock, pipeline_launcher.sh, manifest)
Units: SHA-1 (source), SHA-256 (container), manifest hash
Default_policy: abort (on mismatch or missing provenance)
Interface_consumer: All output artefacts, row-level fields, validation logs, CI
Description: Every output artefact, row, and manifest must record source, container, and build provenance.
Anchor: "pipeline_launcher.sh script reads that digest, the container’s hostname, and the UTC start timestamp, and writes the trio as the first three lines of a *live manifest* file in `/tmp/build.manifest`... The very next action is to fingerprint the generator’s source code: `git rev-parse --verify HEAD` yields a forty‑character SHA‑1 tree hash."
Context: "The build process launches inside a container whose base image has a **sha256 digest pinned in `Dockerfile.lock`**; the `pipeline_launcher.sh` script reads that digest... The very next action is to fingerprint the generator’s source code: `git rev-parse --verify HEAD` yields a forty‑character SHA‑1 tree hash..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 4 ---

--- PP 5 ---
Name: Validation, firewall, and audit artefact registry
Symbol: validation/<parameter_hash>/, audit/hashgate_uri.txt
Scope: merchant_location
Prior_type: Deterministic contract (SHA-256 digests, hash contracts)
Prior_specified: Yes
Calibration_recipe: Yes (artefact enumeration, hash generation, CI validation)
Posterior_validation: Yes (hash match, output/audit log, manifest, CI merge block)
Provenance_tag: Yes (manifest, validation directory, HashGate URI)
Units: SHA-256 digest per artefact/log
Default_policy: abort (if artefact/log missing, not hash-mapped, or drifted)
Interface_consumer: CI, merge, model risk, pipeline, audit, forensic
Description: Every validation, firewall, and audit output must be registered, hash-locked, referenced in manifest, and immutable.
Anchor: "All validation artefacts—raw CSVs, PNGs, GLM coefficient tables—are written under `validation/<parameter_hash>/`. Finally, `upload_to_hashgate.py` posts the manifest JSON, the `validation_passed=true` flag, and the artefacts URL to the internal Flask service **HashGate**. Pull‑requests that ship a new synthetic dataset must include the HashGate URI..."
Context: "All validation artefacts—raw CSVs, PNGs, GLM coefficient tables—are written under `validation/<parameter_hash>/`. Finally, `upload_to_hashgate.py` posts the manifest JSON, the `validation_passed=true` flag, and the artefacts URL to the internal Flask service **HashGate**..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 5 ---

--- PP 6 ---
Name: Directory immutability and collision enforcement
Symbol: synthetic_v1_<parameter_hash>
Scope: merchant_location
Prior_type: Deterministic (filesystem/OS/NFS, parameter hash-based contract)
Prior_specified: Yes
Calibration_recipe: Yes (directory creation, NFS export, collision and uniqueness checks)
Posterior_validation: Yes (read-only directory, hash match, OSError/ParameterHashCollisionError)
Provenance_tag: Yes (filesystem, build log, registry, manifest)
Units: directory path (string)
Default_policy: abort (on overwrite, mismatch, or collision)
Interface_consumer: All pipeline outputs, merge/release, NFS admin, CI
Description: Output directory must be set read-only by parameter-set hash; any overwrite triggers a fatal error, CI block, or collision.
Anchor: "Once the merge occurs, the dataset’s directory—whose name already embeds `parameter_hash`—is mounted read‑only on the shared NFS. Attempting to regenerate the same seed with a different parameter hash yields a directory‑name collision, forcing the developer to bump semantic versions..."
Context: "Once the merge occurs, the dataset’s directory—whose name already embeds `parameter_hash`—is mounted read‑only on the shared NFS. Attempting to regenerate the same seed with a different parameter hash yields a directory‑name collision..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 6 ---

<<PP‑END>>
