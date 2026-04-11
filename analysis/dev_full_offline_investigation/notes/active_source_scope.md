# Active Source Scope

As of `2026-04-11`

The offline investigation is pinned to this engine run:

- run root:
  - `runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1`
- `run_id = a3bd8cac9a4284cd36072c6b9624a0c1`
- `seed = 42`
- `manifest_fingerprint = 76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460`
- `parameter_hash = 0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00`

## Why this run is accepted as the active basis

- the run receipt is present and coherent
- the `6B` validation report is present
- upstream segment gates `1A, 1B, 2A, 2B, 3A, 3B, 5A, 5B, 6A` are all `PASS`
- `6B` required checks are `PASS`
- the key offline analytical surfaces are present under the pinned world identity

## Key accepted surfaces in this run

- `data/layer2/5B/arrival_events_5B/...`
- `data/layer3/6B/s1_arrival_entities_6B/...`
- `data/layer3/6B/s1_session_index_6B/...`
- `data/layer3/6B/s2_event_stream_baseline_6B/...`
- `data/layer3/6B/s2_flow_anchor_baseline_6B/...`
- `data/layer3/6B/s3_event_stream_with_fraud_6B/...`
- `data/layer3/6B/s3_flow_anchor_with_fraud_6B/...`
- `data/layer3/6B/s4_event_labels_6B/...`
- `data/layer3/6B/s4_flow_truth_labels_6B/...`
- `data/layer3/6B/s4_flow_bank_view_6B/...`
- `data/layer3/6B/s4_case_timeline_6B/...`

## Important semantic note

The `6B` validation report has:

- `overall_status = WARN`

but this is driven by warn-only realism corridors, not by required machine gates. Required machine checks are green, so this run is acceptable as the analytical source basis.

## Immediate usage rule

Every notebook, SQL file, extract, or metric pack created in this workspace should either:

1. use this run as its basis, or
2. explicitly state that it is using a different run and why
