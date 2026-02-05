# World Stream Producer Build Plan (v0)
_As of 2026-01-28_

## Purpose
Implement WSP as the **primary runtime producer** that replays sealed engine **behavioural traffic** into IG **directly from the Oracle Store** (engine‑rooted), preserving bank‑like temporal flow. WSP also streams **behavioural_context join surfaces** as separate EB topics so downstream components can hydrate local state without scanning the oracle.

**Traffic policy (v0):** WSP emits **one behavioural stream per run**:
- **Baseline:** `s2_event_stream_baseline_6B`
- **Fraud (default):** `s3_event_stream_with_fraud_6B`

**Context policy (v0):** WSP emits **join surfaces** as separate channels:
- `arrival_events_5B`
- `s1_arrival_entities_6B`
- **Flow anchor** aligned with traffic mode:
  - Baseline: `s2_flow_anchor_baseline_6B`
  - Fraud: `s3_flow_anchor_with_fraud_6B`

Traffic + context outputs are **not interleaved** (separate EB streams).  
**Concurrency note:** WSP streams outputs **in parallel by default** when multiple outputs are present (override via `WSP_OUTPUT_CONCURRENCY` if you need sequential debug runs).

## Planning rules (binding)
- **Progressive elaboration:** expand only the active phase into sections + DoD.
- **WSP never writes to EB:** IG remains the only writer.
- **No discovery‑by‑scanning:** WSP must be pointed at a specific engine world (explicit run root).
- **Speedup is a policy knob in all envs** (same semantics at any speed).

## Phase plan (v0)

### Phase 1 — Core stream head (current)
**Intent:** engine‑rooted stream production with canonical envelopes and oracle by‑ref reads.

#### Phase 1.1 — Engine world selection
**DoD checklist:**
- Explicit engine run root + scenario_id required (no “latest” scanning).
- `run_receipt.json` and (if present) `_oracle_pack_manifest.json` validated.

#### Phase 1.2 — StreamPlan derivation
**DoD checklist:**
- Derive **traffic outputs** from policy allowlist (`traffic_output_ids`).
- Derive **context outputs** from policy allowlist (`context_output_ids_ref`), auto‑switching to baseline context when the traffic mode is baseline.
- Output IDs must exist in catalogue; unknown outputs are rejected.

#### Phase 1.3 — Oracle Store by‑ref reads
**DoD checklist:**
- Use catalogue path templates + world tokens to build locators (no scanning).
- Enforce “no PASS → no read” using gate pass flags from engine gate map (traffic + context outputs).

#### Phase 1.4 — Canonical envelope framing
**DoD checklist:**
- Emit canonical envelope with stable `event_id`, `event_type`, `ts_utc`, pins.
- Include both `platform_run_id` and `scenario_run_id` for run-scoped events.
- Preserve legacy pull compatibility where required (naming + payload structure).

#### Phase 1.5 — Temporal pacing + speedup factor
**DoD checklist:**
- Event‑time pacing is defined (no future leakage).
- `stream_speedup` is configurable in **all envs** (policy knob).

#### Phase 1.6 — IG push interface
**DoD checklist:**
- WSP pushes to IG ingress; no direct EB writes.
- Failure handling is explicit (retry vs halt vs quarantine trigger).

#### Phase 1.7 — Retry/backoff posture
**DoD checklist:**
- Retry 429/5xx/timeouts with bounded exponential backoff and the same `event_id`.
- Treat schema/policy 4xx as non-retryable and stop the output stream with explicit reason.
- Retry knobs are configuration-driven (max attempts, base delay, cap).

**Status:** complete.

### Phase 2 — Checkpointing + resume
**Intent:** operational continuity under restarts and at‑least‑once delivery.

#### Phase 2.1 — Checkpoint identity + cursor model
**DoD checklist:**
- Checkpoint key pinned (`oracle_pack_id` + `output_id`, fallback to `engine_run_root` if manifest missing).
- Cursor includes `last_file` + `last_row_index` + `last_ts_utc`.
- Cursor advances **after** successful emit to IG.

#### Phase 2.2 — Local checkpoint backend
**DoD checklist:**
- File‑based checkpoint under `runs/fraud-platform/<platform_run_id>/wsp/checkpoints/`.
- Write‑once append log + current cursor snapshot (atomic rename).
- Resume logic skips previously emitted rows.

#### Phase 2.3 — Dev/Prod checkpoint backend
**DoD checklist:**
- Postgres table for checkpoints (single‑writer semantics).
- Concurrency guard documented (single WSP per pack in v0).
- Clear handling for missing/invalid checkpoints (fail‑closed vs restart).

#### Phase 2.4 — Resume + duplicate posture
**DoD checklist:**
- WSP resumes from cursor and **minimizes duplicates**.
- IG idempotency remains the final guard (at‑least‑once).
- No new validation logic added here (Phase 4 owns validation).

**Status:** complete.

### Phase 3 — Security + governance hardening
**Intent:** producer identity allowlists, provenance stamping, audit hooks.

#### Phase 3.1 — Producer identity allowlist
**DoD checklist:**
- WSP stamps a stable `producer_id` on all envelopes.
- IG allowlist (or WSP config) can restrict which producer_ids are accepted.

#### Phase 3.2 — Provenance stamp (oracle world)
**DoD checklist:**
- Stamp `oracle_pack_id` (or pack_key fallback) into `trace_id` (schema‑safe provenance).
- Stamp `engine_release` into `span_id` when available.

#### Phase 3.3 — Audit hooks
**DoD checklist:**
- WSP emits audit events (or audit log lines) for stream start/stop + cursor updates.
- Audit output is append‑only; does not mutate traffic.

**Status:** complete.

### Phase 4 — Validation (smoke + dev completion)
**Intent:** WSP→IG path validates under local smoke and dev completion policies.

#### Phase 4.1 — Local smoke validation (bounded)
**DoD checklist:**
- Explicit engine run root + scenario_id resolves (no implicit discovery).
- WSP streams a bounded slice (`max_events`) to IG.
- Producer allowlist enforced (bad producer fails closed).
- Provenance stamping visible (`producer`, `trace_id`, optional `span_id`).
- Checkpoint resume works (second run emits remaining events only).
- Audit hooks are recorded (stream_start/complete + checkpoint_saved).

#### Phase 4.2 — Dev completion validation (uncapped)
**DoD checklist:**
- Strict seal enforced (pack must be sealed).
- Postgres checkpoint backend used (dsn required).
- All policy traffic outputs stream to IG without missing gates.
- WSP completes with `STREAMED` status and IG acknowledges ingestion.

#### Phase 4.3 — Failure‑path spot checks
**DoD checklist:**
- Missing gate → `GATE_PASS_MISSING` (fail‑closed).
- Producer not allowed → `PRODUCER_NOT_ALLOWED` (fail‑closed).

**Status:** complete (local parity smoke executed).

### Phase 5 — Stream view mode (per‑output `ts_utc` ordering)
**Intent:** consume **per‑output** Oracle Store stream views instead of raw engine parts.

#### Phase 5.1 — Mode switch + wiring
**DoD checklist:**
- WSP is **stream‑view only** in v0 (no `stream_mode` toggle).
- `wiring.oracle_stream_view_root` supplies the base path for stream views.
- All profiles use stream view; local smoke relies on the same view semantics.

#### Phase 5.2 — Stream view validation
**DoD checklist:**
- Read `_stream_view_manifest.json` + `_stream_sort_receipt.json` and fail‑closed if missing/mismatched.
- Ensure manifest `output_id` matches the target output.
- Stream view id derived deterministically from world + output_id + sort keys.

#### Phase 5.3 — Global cursor + pacing
**DoD checklist:**
- Per‑output checkpoint cursors preserved (no union).
- Pacing uses `ts_utc` from each output stream view; respects `stream_speedup`.
- Progress logging works with stream view mode.

**Status:** complete (v0).

### v0 green summary (WSP)
- READY consumption via Kinesis control bus in parity mode.
- Stream‑view only read path with per‑output receipts/manifest validation (traffic + context).
- Push‑only delivery to IG; WSP does not publish to EB.
- Traffic mode is single‑stream per run (baseline **or** fraud) with context outputs always included.
- Capped smoke runs validated end‑to‑end with receipts + EB offsets present.
