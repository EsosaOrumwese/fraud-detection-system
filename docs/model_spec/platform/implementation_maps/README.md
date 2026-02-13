# Platform Implementation Maps
_As of 2026-02-10_

This folder is now organized by implementation track to keep baseline history separate from active substrate-promotion work.

## Tracks
- `local_parity/`:
  - Historical and baseline implementation maps for the completed local-parity track.
  - Includes all prior component `*.build_plan.md`, `*.impl_actual.md`, and platform validation matrix artifacts.
- `dev_substrate/`:
  - Active implementation maps for dev substrate promotion work.
  - New planning and decision entries for this phase must be written here.

## Active writing rule
- For current platform work, append entries under:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/{COMP}.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/dev_substrate/{COMP}.impl_actual.md`

## Continuity rule
- Do not edit historical rationale in `local_parity/` except append-only routing notes.
- Keep daily action logs in `docs/logbook/` and reference the matching track file paths.
