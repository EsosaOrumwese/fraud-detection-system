## [1A.1.0] - 2025-07-26
### Added
- Temporal Version Matrix Finder (TVM-F) prompt for sub-segment 1A across narrative, assumptions, artefact registry, parameter and interface specs.  
- Generated TV blocks enumerating every physical-site merchant artefact with missing version_tag, valid_window, update_cadence, digest, and compatibility flags.  
- Temporal Version Matrix Spec-Writer (TVM-S) TOML entries closing all gaps for 1A: draft version_tags, valid windows, cadences, placeholder sha256, and compatibility lists.  
- Token-chunking markers (`<<TV-CONTINUE>>`/`<<TV-END>>`) to handle long outputs.  

### Changed
- Finder rules refined to match artefact names via supplied registry and inline identifiers only, removing file-reference tags.  

### Fixed
- Removed inline contentReference tags from catalogue output anchors.  

### Removed
- Extraneous citation tokens and file-tag markers from prompts and outputs.

### Breaking
- None

## [1B.1.0] - 2025-07-26
### Added
- TVM-F gap analysis for 35 artefacts in sub-segment 1B (spatial sampling & placement).  
- TVM-S TOML TV-FIX blocks for IDs 1–35, populating draft version_tags, valid windows, cadences, placeholder sha256, and compatibility lists.  
- Consistent context chains linking “prev … next” for spatial artefact workflows.  

### Changed
- Standardized “N/A” and “Missing” flag conventions in Finder output.  

### Fixed
- Corrected severity rules to mark High when tag_missing or compat_missing = Y.  

### Removed
- Duplicate TV blocks by OR-ing gap flags across identical artefact names.  

### Breaking
- None

## [2A.1.0] - 2025-07-26
### Added
- TVM-F analysis for 14 artefacts in sub-segment 2A (time-zone derivation).  
- TVM-S TOML entries for IDs 1–14 with realistic version_tags (e.g. tz_world_polygons 2025a), valid windows, daily/monthly/annual cadences, and placeholder sha256.  

### Changed
- Introduced “annual” cadence for IANA tzdata and polygon updates.  

### Fixed
- Harmonized “snapshot_date” as version_tag for daily OSM extracts.  

### Removed
- NA flags consolidated to only apply to non-versioned documentation artefacts.  

### Breaking
- None

## [2B.1.0] - 2025-07-26
### Added
- TVM-F gap analysis for 13 routing-through-sites artefacts.  
- TVM-S blocks for IDs 1–13, establishing draft version_tags, valid windows, annual cadences for configs, and compatibility chains.  

### Changed
- Update cadence for routing_day_effect set to annual.  

### Fixed
- Linkage between routing_manifest and site_catalogue artefacts corrected in compatibility lists.  

### Removed
- Unused “digest_missing” flags for code artefacts with known digest presence.  

### Breaking
- None

## [3A.1.0] - 2025-07-26
### Added
- TVM-F analysis for 15 cross-zone allocation artefacts.  
- TVM-S TOML fixes for IDs 1–15: draft semver for config files, CSV/Parquet schemas, and placeholder digests.  

### Changed
- Marked docs/round_ints.md as draft version_tag to close compat_missing.  

### Fixed
- Ensured artefacts/allocation CSV and Parquet listings include sha256 placeholders.  

### Removed
- Implicit “N/A” on functional spec artefacts replaced with explicit draft entries.  

### Breaking
- None

## [3B.1.0] - 2025-07-26
### Added
- TVM-F for 18 purely-virtual merchant artefacts (config, rasters, logs).  
- TVM-S entries for IDs 1–18: draft versions, daily cadences for logs, never cadences for static artefacts, and placeholder sha256.  

### Changed
- Defined “daily” cadence for all virtual-validation and error logs.  

### Fixed
- Unified version_tag naming convention (`v1.0.0-draft`) across all virtual artefacts.  

### Removed
- Ambiguous “container” types without clear version_tag replaced with draft entries.  

### Breaking
- None

## [4A.1.0] - 2025-07-26
### Added
- TVM-F analysis for 11 reproducibility & configurability artefacts (Dockerfile.lock, registry, hyperparams).  
- TVM-S fixes for IDs 1–11: draft version_tags, valid windows, never cadences, and ALL_OTHER_ARTIFACTS compatibility.  

### Changed
- Renamed config/footall_coefficients.yaml anchor to match narrative spelling.  

### Fixed
- Corrected anchor spelling for “config/footfall_coefficients.yaml”.  

### Removed
- Unnecessary “digest_missing=NA” flags for code artefacts with digest_present=Yes.  

### Breaking
- None

## [4B.1.0] - 2025-07-26
### Added
- TVM-F for 20 validation artefacts (schemas, logs, flags).  
- TVM-S entries for IDs 1–20: draft semver for schemas/configs, daily cadences for validation logs, on-success/on-change cadences for flags, and placeholder sha256.  

### Changed
- Applied “on-success” cadence to CI pass flag and “on-change” to readonly.flag.  

### Fixed
- Updated compatible_with chains to reflect new validation workflow order.  

### Removed
- Redundant NA flags for container artefacts with digest_present=Yes.  

### Breaking
- None