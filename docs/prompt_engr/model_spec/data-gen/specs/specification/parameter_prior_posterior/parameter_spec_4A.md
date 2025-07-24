############################################################
#  PARAMETER SPEC‑WRITER • Sub‑segment 4A                   #
############################################################


<<<PP‑FIX id=1>
Name: Parameter-set hash (manifest fingerprint)
Symbol: $P$
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic function (SHA-256 digest)
hyperparameters:
artefact_set: enumerated absolute POSIX paths (artefact_registry.yaml)
units: 256-bit hex string
default_policy: abort (if missing or hash mismatch)
justification: Anchors all output reproducibility and dataset root; enforces immutability of parameter configuration.
CALIBRATION_RECIPE:
input_path: artefact_registry.yaml, manifest, all artefacts
objective: Complete enumeration and bytewise SHA-256 digest over every artefact
algorithm: artefact_loader.py, hash accumulator
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see manifest)
INTERFACE_CONSUMER:
artefact_name: manifest, all pipeline modules
function: Propagates parameter hash for all output, directory names, PRNG seed, and provenance fields
description: Every pipeline output, log, and artefact embeds or references this hash as a provenance anchor.
POSTERIOR_VALIDATION:
metric: manifest comparison, collision check
acceptance_range: hash matches for every output; no collision
sample_size: all artefacts per build
PROVENANCE_TAG:
artefact_name: manifest, artefact_registry.yaml
sha256: (see manifest)
SHORT_DESCRIPTION:
256-bit SHA-256 fingerprint of all declared artefacts, configs, code, and licences.
TEST_PATHWAY:
test: artefact_loader.py, manifest comparison, collision audit
input: artefact_registry.yaml, manifest, artefacts
assert: Hash matches and unique across builds
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=2>
Name: Master seed for global PRNG
Symbol: $\mathit{master\_seed}$
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic function (timestamp + hash)
hyperparameters:
master_seed: (timestamp_ns << 64) XOR (parameter_set_hash[0:128])
units: 128-bit integer (hex)
default_policy: abort (if missing, drift, or mismatch)
justification: Guarantees global PRNG seed is audit-traceable, unique per parameter set and build time.
CALIBRATION_RECIPE:
input_path: manifest, build logs
objective: Ensure PRNG reproducibility across all pipeline modules
algorithm: deterministic calculation as described in spec
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see manifest)
INTERFACE_CONSUMER:
artefact_name: manifest, all PRNG modules, pipeline logs
function: Seeds Philox 2^128 + AES-round RNG for every pipeline process and row
description: Master seed locks every random number stream to the parameter set and build provenance.
POSTERIOR_VALIDATION:
metric: manifest and replay check, CI PRNG audit
acceptance_range: master_seed matches manifest and all PRNG replay
sample_size: all rows/events per build
PROVENANCE_TAG:
artefact_name: manifest
sha256: (see manifest)
SHORT_DESCRIPTION:
Audit-traceable, deterministic 128-bit seed for global PRNG.
TEST_PATHWAY:
test: manifest/replay check, PRNG audit
input: manifest, logs, build output
assert: All PRNG traces match manifest seed
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=3>
Name: Artefact registry with licence mapping
Symbol: artefact_registry.yaml, license_map
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic contract (YAML, SHA-256, licence mapping)
hyperparameters:
artefact_registry: YAML list of artefact paths
license_map: mapping of artefact → licence file (SHA-256 digest)
units: registry: YAML list; licence: path, SHA-256 digest
default_policy: abort (if artefact, licence, or mapping missing)
justification: Guarantees all artefacts have mapped and governed licences, enforced at every build.
CALIBRATION_RECIPE:
input_path: artefact_registry.yaml, LICENSES/
objective: Complete enumeration, mapping, and hash calculation
algorithm: artefact_loader.py, hash for each licence
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see manifest)
INTERFACE_CONSUMER:
artefact_name: artefact_registry.yaml, LICENSES/, manifest, pipeline modules
function: Maps every artefact to a licence, enforces audit and legal provenance for build/validation
description: Every output and artefact is mapped to a hash-locked licence and tracked in the registry.
POSTERIOR_VALIDATION:
metric: manifest comparison, missing/drift check, CI test
acceptance_range: all artefacts mapped and hashes present
sample_size: all artefacts per build
PROVENANCE_TAG:
artefact_name: artefact_registry.yaml, LICENSES/
sha256: (see manifest)
SHORT_DESCRIPTION:
Governed, auditable registry of artefacts and licences, mapped and hash-locked.
TEST_PATHWAY:
test: artefact_loader.py, CI, manifest replay
input: artefact_registry.yaml, LICENSES/
assert: All mappings present, hashes match manifest
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=4>
Name: Source, container, and build manifest provenance
Symbol: source_sha1, container_sha, build_manifest_digest
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic (SHA-1/SHA-256 digests and build manifests)
hyperparameters:
source_sha1: git SHA-1 commit
container_sha: Dockerfile.lock SHA-256
build_manifest_digest: manifest SHA-256
units: SHA-1 (source), SHA-256 (container), manifest hash
default_policy: abort (on mismatch or missing)
justification: Guarantees full traceability from code to container to build; enforced at manifest and output level.
CALIBRATION_RECIPE:
input_path: Dockerfile.lock, build manifest, pipeline_launcher.sh
objective: Traceable, reproducible container and code state for all outputs
algorithm: shell/git commands, manifest recording, hash comparison
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see manifest)
INTERFACE_CONSUMER:
artefact_name: build manifest, Dockerfile.lock, pipeline_launcher.sh, CI
function: Provenance contract for every artefact, output row, and manifest
description: All output artefacts, logs, and manifests record the container, source, and build hashes.
POSTERIOR_VALIDATION:
metric: manifest hash, container/source check
acceptance_range: all hashes match manifest
sample_size: all outputs/rows per build
PROVENANCE_TAG:
artefact_name: build manifest, Dockerfile.lock, pipeline_launcher.sh
sha256: (see manifest)
SHORT_DESCRIPTION:
Source, container, and build manifest provenance for every output artefact.
TEST_PATHWAY:
test: build log/manifest replay, container/source hash audit
input: build manifest, Dockerfile.lock, git
assert: All outputs/rows carry correct provenance; CI passes
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=5>
Name: Validation, firewall, and audit artefact registry
Symbol: validation/<parameter_hash>/, audit/hashgate_uri.txt
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic contract (SHA-256 digests, hash contracts)
hyperparameters:
validation_dir: validation/<parameter_hash>/
audit_uri: audit/hashgate_uri.txt
units: SHA-256 digest per artefact/log
default_policy: abort (if artefact/log missing, not hash-mapped, or drifted)
justification: Locks all validation, firewall, and audit outputs to parameter hash and manifest.
CALIBRATION_RECIPE:
input_path: validation/<parameter_hash>/, audit/hashgate_uri.txt, manifest
objective: Complete enumeration, hash calculation, and manifest validation
algorithm: artefact enumeration, hash, manifest posting to HashGate
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see manifest)
INTERFACE_CONSUMER:
artefact_name: CI, merge, pipeline, audit, HashGate
function: Registers and hashes every validation/audit output for pipeline, audit, and forensic workflow.
description: Every validation/audit artefact is hash-locked and posted to HashGate, blocking merge on drift.
POSTERIOR_VALIDATION:
metric: hash match, manifest and audit log comparison
acceptance_range: all artefact hashes match manifest and audit logs
sample_size: all validation/audit artefacts per build
PROVENANCE_TAG:
artefact_name: manifest, validation/<parameter_hash>/, audit/hashgate_uri.txt
sha256: (see manifest)
SHORT_DESCRIPTION:
All validation, firewall, and audit artefacts hash-mapped and contract-locked.
TEST_PATHWAY:
test: audit/manifest comparison, HashGate merge check
input: validation directory, audit URI, manifest
assert: All artefact hashes mapped and pass merge audit
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=6>
Name: Directory immutability and collision enforcement
Symbol: synthetic_v1_<parameter_hash>
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic (filesystem, hash-based contract)
hyperparameters:
parameter_hash: 256-bit hex string
directory_path: synthetic_v1_<parameter_hash>
units: directory path (string)
default_policy: abort (on overwrite, mismatch, or collision)
justification: Guarantees dataset output is immutable, unique per parameter set, and collision-proof.
CALIBRATION_RECIPE:
input_path: NFS/export directory, manifest, build logs
objective: Validate immutability, uniqueness, and collision logic
algorithm: create directory, mount read-only, check for collision on parameter_hash
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see manifest)
INTERFACE_CONSUMER:
artefact_name: NFS export, manifest, CI, pipeline outputs
function: Ensures all outputs are written to unique, read-only directory per parameter hash
description: Any overwrite or hash collision aborts build and blocks CI/merge.
POSTERIOR_VALIDATION:
metric: read-only mount, collision audit, manifest check
acceptance_range: directory unique, no collisions, read-only
sample_size: all builds per hash
PROVENANCE_TAG:
artefact_name: filesystem, manifest
sha256: (see manifest)
SHORT_DESCRIPTION:
Directory immutability and collision enforcement for each parameter-set output.
TEST_PATHWAY:
test: mount read-only, audit manifest, collision check
input: NFS export, manifest, logs
assert: Directory immutable, no collision, manifest matches
Confidence=HIGH
<<<END PP‑FIX>>

##### END PARAMETER_SPEC #####

id=1 | gaps_closed=prior|calib|post|prov | notes=Artefact hash, manifest/CI enforced  
id=2 | gaps_closed=prior|calib|post|prov | notes=Deterministic seed, manifest/PRNG audited  
id=3 | gaps_closed=prior|calib|post|prov | notes=Registry+licence mapping, YAML, CI audit  
id=4 | gaps_closed=prior|calib|post|prov | notes=Provenance, container/source hash, manifest  
id=5 | gaps_closed=prior|calib|post|prov | notes=Validation, audit, HashGate, hash-mapped  
id=6 | gaps_closed=prior|calib|post|prov | notes=Immutability, collision, read-only directory  
<<PS‑END>>
