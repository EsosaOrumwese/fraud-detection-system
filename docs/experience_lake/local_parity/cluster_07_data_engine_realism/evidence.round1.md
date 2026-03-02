# Cluster 7 - Round 1 Evidence

## Certification anchor

- `runs/fix-data-engine/segment_1A/reports/segment1a_p5_certification.json`
  - `generated_utc=2026-02-13T10:34:00Z`
  - grade decision: `B` (`eligible_B=true`, `eligible_B_plus=false`)
  - hard gates: `4/4`
  - band coverage: `B=13/14`, `B+=10/14`
  - authority runs:
    - `p2_authority_run=9901b537de3a5a146f79365931bd514c`
    - `p3_authority_run=da3e57e73e733b990a5aa3a46705f987`
    - `p4_authority_run=416afa430db3f5bf87180f8514329fe8`

## Freeze-guard enforcement

- scorer: `tools/score_segment1a_freeze_guard.py`
- candidate guard artifact (example):
  - `runs/fix-data-engine/segment_1A/reports/segment1a_freeze_guard_416afa430db3f5bf87180f8514329fe8.json`

## Determinism under forced manifest drift

- run pair:
  - `29bdb537f5aac75aa48479272fc18161`
  - `a1753dc8ed8fb1703b336bd4a869f361`
- same control identity:
  - `seed=42`
  - `parameter_hash=59ca6719a623f6f024806b79344926c5941841789f2f92264bccad187f710f72`
- intentional manifest drift:
  - run A `manifest_fingerprint=f5f04c50d1682d9b00a572172fd3a090ff2420a641cb4f9e2dfa0177a612822e`
  - run B `manifest_fingerprint=c1230ffabe39afdce8d2300fd1b77aad3e5f2d9a49383fc09fa0b3dfacf3fa09`
- evidence files:
  - `runs/fix-data-engine/segment_1A/reports/segment1a_p2_1_baseline_29bdb537f5aac75aa48479272fc18161.json`
  - `runs/fix-data-engine/segment_1A/reports/segment1a_p2_1_baseline_a1753dc8ed8fb1703b336bd4a869f361.json`
  - `runs/fix-data-engine/segment_1A/reports/segment1a_p5_certification.json` (`evidence.determinism.p2_global_equal=true`, `evidence.determinism.p3_global_equal=true`)

## Seed roster

- certification roster used: `{42,43,44}`
- support artifacts:
  - `runs/fix-data-engine/segment_1A/reports/p1_4_lock_scorecard.json` (two-pass replay over seeds `42/43/44`)
  - `runs/fix-data-engine/segment_1A/reports/segment1a_p5_certification.json` (`alternate_seed_run=651fa96a4dc46cbcf6e3cfee8434180f`)

