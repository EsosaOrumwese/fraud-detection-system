# Platform Dev Substrate Build Plan (Fresh Start)
_As of 2026-02-12_

## Reset intent
This build plan starts from a clean slate for dev migration. Legacy dev_substrate implementation artifacts were removed to prevent drift-by-adaptation.

## Phase 0 - Re-baseline and readiness
### Goal
Re-establish a clean execution baseline before new implementation work begins.

### Definition of Done
- [ ] Legacy dev_substrate implementation surfaces are removed from repo paths.
- [ ] Migration runbook and handles registry are treated as the only implementation authority for dev wiring.
- [ ] Fresh-start reset is recorded in `platform.impl_actual.md` and `docs/logbook`.

## Phase 1 - P(-1)/P0 delivery preparation
### Goal
Prepare image packaging and substrate provisioning implementation strictly from migration authority docs.

### Definition of Done
- [ ] P(-1) implementation steps are expanded from runbook into executable build tasks.
- [ ] P0 handle-to-terraform mapping is enumerated with no wildcard handles.
- [ ] Validation checklist for P(-1)/P0 evidence is defined before implementation.
