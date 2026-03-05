# Build Folder (dev_full)
_As of 2026-03-03_

## Purpose
This folder is the dedicated home for build-authority documents for the `dev_full` track.

## Current posture
1. Existing authoritative build plan files still live at:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M*.build_plan.md`
2. We are intentionally not moving them yet to avoid breaking current status-owner references and deep-plan routing.

## Migration strategy
1. Start stress-testing program first (`../stress_test/`).
2. Migrate build files into this folder only with explicit routing update and path continuity checks.
3. Preserve `platform.build_plan.md` status-owner law throughout migration.

## Convention (target state)
1. Build authorities will use this folder.
2. Stress authorities will use `../stress_test/`.
