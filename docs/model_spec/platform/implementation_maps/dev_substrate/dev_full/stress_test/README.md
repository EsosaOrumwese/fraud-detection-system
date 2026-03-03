# Stress Test Folder (dev_full)
_As of 2026-03-03_

## Purpose
This folder contains phase-driven stress testing authorities and execution records for production-readiness hardening.

## Program rule
1. Stress testing is not a box-check before certification.
2. Stress testing is the primary mechanism to expose and remediate bottlenecks before certification is attempted.

## File convention
1. Program-level control file:
   - `platform.stress_test.md`
2. Phase files (created only when active):
   - `platform.M0.stress_test.md`
   - `platform.M1.stress_test.md`
   - ...
   - `platform.M15.stress_test.md`

## Status
1. Program-level file is active: `platform.stress_test.md`.
2. First dedicated phase file is now active: `platform.M2.stress_test.md`.
3. Additional per-phase files are still created progressively as each phase becomes active.
