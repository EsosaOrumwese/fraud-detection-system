# Dev Substrate Implementation Maps
_As of 2026-02-22_

This directory is now split by target environment to avoid scope drift.

## Tracks
- `dev_min/`: certified migration track (`local_parity -> dev_min`) for Spine Green v0.
- `dev_full/`: planning/execution track for full-platform expansion after dev_min certification.

## Rule
- Do not mix `dev_min` and `dev_full` execution notes in the same file set.
- Keep each track self-contained (build plans, implementation notes, wrap-up notes).
