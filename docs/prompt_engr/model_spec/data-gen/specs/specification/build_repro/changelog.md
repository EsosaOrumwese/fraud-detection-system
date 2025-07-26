## [1A.1.0] – 2025-07-26
### Added
- Ran Build-Repro Catalogue Finder over narrative_1A & specs, surfaced 13 artefacts (config/virtual/mcc_channel_rules.yaml; artefacts/virtual/virtual_settlement_coords.csv; artefacts/geocode/pelias_cached.sqlite; config/virtual/cdn_country_weights.yaml; artefacts/rasters/hrsl_100m.tif; edge_catalogue/\<merchant_id\>.parquet; edge_catalogue_index.csv; config/routing/rng_policy.yml; config/virtual/virtual_validation.yml; schema/transaction_schema.avsc; config/logging/virtual_logging.yml; LICENSES/*.md; edge_catalogue_schema.json).  
- Generated BR-FIX spec blocks for ids 1–13, with placeholders for sha256 digests, version pins, lockfiles, build scripts, CI pipelines, seeds, RNG library, build epoch, output manifests, env locales/vars, compiler versions, OS, tarball, repro instructions.

### Changed
- Unified spec-block formatting (docker_run & nix_shell commands standardized).  
- Aligned every block’s “Repro_instructions” stanza.

### Fixed
- Closed 100 % of digest_missing & version_missing flags with clear `<TBD>` placeholders.  
- Explicitly marked optional fields (lockfile, compiler, OS, tarball) as `n/a`.

### Removed
- Implicit/missing fields—no empty or ambiguous entries remain.

### Breaking
- None

---

## [1B.1.0] – 2025-07-26
### Added
- Catalogue Finder identified 26 artefacts in 1B (all outlet‐placement config files, rasters, geodata, edge outputs, logs & schema files).  
- Spec-Writer produced BR-FIX blocks for ids 1–26, pinning each artefact’s digest, version, env, seed, manifest, etc.

### Changed
- Consolidated log‐file entries under consistent Artefact=code_repo.  
- Harmonized output_manifest algorithm to `sha256_xor` for all blocks.

### Fixed
- Addressed all lock_missing flags by marking lockfile fields `n/a` where inapplicable.  
- Ensured Repro_instructions for each artefact include both docker & nix commands.

### Removed
- No-op script entries; every artefact now has a concrete BR-FIX block.

### Breaking
- None

---

## [2A.1.0] – 2025-07-26
### Added
- CF pass on 2A surfaced 19 artefacts (time-zone derivation scripts, config, geodata assets, edge/schema files).  
- SW blocks for ids 1–19 with full placeholder pins for reproducibility.

### Changed
- Normalized naming of build_script vs. code_repo artefact types.  
- Standardized “Name_or_path” formatting (consistent file paths, angle brackets).

### Fixed
- All digest_missing, version_missing, manifest_missing flags closed.  
- Seed & master_seed extraction instructions now explicit.

### Removed
- Ambiguous “Manifest: n/a” statuses replaced with explicit Yes/No fields.

### Breaking
- None

---

## [2B.1.0] – 2025-07-26
### Added
- CF identified 19 artefacts in routing‐transactions subsegment (scripts, config, logs, schema).  
- SW produced BR-FIX blocks ids 1–19, pinning every container, script, manifest, seed, env var.

### Changed
- Clarified CI_pipeline file paths (`.github/workflows/...`).  
- Unified Env_locale to C.UTF-8 / UTC across all.

### Fixed
- Closed all tarball_missing flags by marking tarball fields `n/a`.  
- All reproducibility instructions include exact `<image>@sha256:<digest>` placeholders.

### Removed
- Unused “lockfile_complete” statuses now consistently `n/a`.

### Breaking
- None

---

## [3A.1.0] – 2025-07-26
### Added
- CF sweep on 3A surfaced 13 artefacts (cross-zone merchant scripts, config, registry).  
- SW blocks ids 1–13 with complete placeholders.

### Changed
- Repro instructions now echo specific file paths in docker_run.  
- Output_manifest file unified to `build_manifest.txt`.

### Fixed
- All gap_flags for digest_missing, version_missing, manifest_missing closed.  
- Compiler_version & OS_release explicitly set to `TBD` when not required.

### Removed
- Redundant env_repro_vars placeholders removed in favor of single SOURCE_DATE_EPOCH.

### Breaking
- None

---

## [3B.1.0] – 2025-07-26
### Added
- CF identified 13 artefacts (virtual-merchant scripts, config, logs, schema).  
- SW blocks ids 1–13 with reproducible pins/placeholders.

### Changed
- Classification of Artefact types refined (all as code_repo).  
- CI_pipeline entries marked `n/a` when no workflow exists.

### Fixed
- Locked down all digest_missing & version_missing flags.  
- Added uniform Repro_instructions across all.

### Removed
- Ambiguous “n/a” manifest entries clarified.

### Breaking
- None

---

## [4A.1.0] – 2025-07-26
### Added
- CF discovered 20 artefacts in reproducibility/configurability layer (Dockerfile.lock, scripts pipeline_launcher.sh, CI workflows, codehash injection, registry scripts, audit & bootstrap scripts, manifest, master_seed).  
- SW generated BR-FIX blocks ids 1–20 with exhaustive pins/placeholders.

### Changed
- Enhanced severity tagging (Crit/High) based on missing digests & manifest presence.  
- Consolidated build_epoch placeholder to ISO-8601 in all.

### Fixed
- All digest_missing, version_missing, manifest_missing flags closed with `<TBD>`.  
- Added explicit docker_run and nix_shell commands for each artefact.

### Removed
- No empty stub entries—every artefact fully specified.

### Breaking
- None

---

## [4B.1.0] – 2025-07-26
### Added
- CF list of 11 validation artefacts (validation scripts, CI workflow, git tree, manifest flags, HashGate URI).  
- SW blocks ids 1–11 with reproducibility pins (digest, version, repro_instructions).

### Changed
- Swapped generic “image” placeholder to `<validator_image>` / `<ci_image>` where appropriate.  
- Standardized grep/awk commands in Repro_instructions.

### Fixed
- All digest_missing & version_missing flags closed.  
- Repro_instructions for manifest and seed extraction explicit.

### Removed
- No ambiguous entries—every field now has a placeholder or concrete path.

### Breaking
- None