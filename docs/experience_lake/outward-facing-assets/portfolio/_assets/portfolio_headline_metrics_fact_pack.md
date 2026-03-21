# Portfolio Headline Metrics Fact Pack

As of `2026-03-21`

Purpose:
- give GPT-5.4 a clean, source-traced set of the headline metrics used in the portfolio deck
- separate exact primary facts from outward-facing rounded display values
- avoid soft claims where the repo does not support them strongly enough

Boundary:
- this pack is keyed to `scratch.md`
- it is for deck content and evidence only
- it is not a slide-design document

Evidence grade legend:
- `Primary run artifact` = exact value present in a run summary, scorecard, or operator surface under `runs/`
- `Primary plan / implementation note` = exact value present in the proving-plane plan or implementation notes
- `Outward-facing reuse` = value already used in outward-facing storyline material, but should still be understood as a rounded display form of a deeper primary fact

Normalization rule:
- where the repo contains an exact value and the deck wants a shorter recruiter-facing number, this pack keeps both:
  - `Deck display`
  - `Exact value`

---

## Slide 5 - One shared operating world

Recommended outward-facing use:
- use the rounded event counts
- keep the label/case/campaign counts exact
- state that runtime replay, case history, labels, and later ML all draw from the same bounded current world rather than from separate toy datasets

| Claim | Deck display | Exact value | Best source | Evidence grade | Notes |
|---|---:|---:|---|---|---|
| accepted current fraud slice events | `331.5M` | `331,506,996` | `platform.production_readiness.plan.md`, `platform.production_readiness.impl_actual.md` | `Primary plan / implementation note` | Rounded outward-facing form is already used in `canonical-storyline.md` |
| raw full horizon behind bounded slice | `473.4M` | `473,383,388` | `platform.production_readiness.plan.md` | `Primary plan / implementation note` | This is the raw horizon behind the accepted bounded slice, not a separate platform run |
| flow-level truth labels | `175,830` | `175,830` | `platform.production_readiness.plan.md`, `platform.production_readiness.impl_actual.md`, `platform.production_readiness.phase5.md` | `Primary plan / implementation note` | Stable exact count |
| case timeline rows | `23,681` | `23,681` | `platform.production_readiness.plan.md`, `platform.production_readiness.impl_actual.md`, `platform.production_readiness.phase5.md` | `Primary plan / implementation note` | Stable exact count |
| distinct cases | `12,350` | `12,350` | `platform.production_readiness.plan.md`, `platform.production_readiness.impl_actual.md`, `platform.production_readiness.phase5.md` | `Primary plan / implementation note` | Stable exact count |
| distinct campaigns | `6` | `6` | `platform.production_readiness.plan.md`, `platform.production_readiness.impl_actual.md` | `Primary plan / implementation note` | In `impl_actual`, this appears as `distinct_campaign_count = 6` |

Recommended phrasing:
- `The accepted current fraud slice alone carried ~331.5M events, backed by a 473.4M-event raw horizon, with 175,830 flow-level truth labels, 23,681 case-timeline rows, 12,350 distinct cases, and 6 fraud campaigns on the same bounded world.`

---

## Slide 7 - Earned production readiness

Recommended outward-facing use:
- keep the integrated and widened-stress numbers
- use the rounded recovery value `3019` only if space is tight
- pair the headline numbers with one short semantic line:
  - integrity deltas stayed `0`
  - downstream timing stayed green
  - runtime decisions, case truth, label truth, and governed active-bundle authority stayed alive on the same story

### Integrated full-platform proof

| Claim | Deck display | Exact value | Best source | Evidence grade | Notes |
|---|---:|---:|---|---|---|
| steady EPS | `3049.811` | `3049.811111111111` | `phase6_learning_coupled_20260313T010847Z phase6_learning_coupled_summary.json`, `platform.production_readiness.plan.md`, `b_production_readiness.notes.md` | `Primary run artifact` | Use `3049.811` in the deck |
| burst EPS | `6188` | `6188.0` | `phase6_learning_coupled_20260313T010847Z phase6_learning_coupled_summary.json`, `platform.production_readiness.plan.md`, `b_production_readiness.notes.md` | `Primary run artifact` | Exact enough already |
| recovery EPS | `3019` or `3019.217` | `3019.2166666666667` | `phase6_learning_coupled_20260313T010847Z phase6_learning_coupled_summary.json`, `platform.production_readiness.plan.md`, `b_production_readiness.notes.md` | `Primary run artifact` | `canonical-storyline.md` uses the rounded `3019` form |

### Widened bounded stress authorization

| Claim | Deck display | Exact value | Best source | Evidence grade | Notes |
|---|---:|---:|---|---|---|
| admitted events | `2.36M` | `2,360,103` | `phase9_full_platform_stress_20260313T203100Z phase9_stress_summary.json`, `b_production_readiness.notes.md`, `platform.production_readiness.plan.md` | `Primary run artifact` | Rounded outward-facing form is already used in `canonical-storyline.md` |
| steady EPS | `3007` or `3007.053` | `3007.0533333333333` | `phase9_full_platform_stress_20260313T203100Z phase9_stress_summary.json`, `platform.production_readiness.plan.md`, `b_production_readiness.notes.md` | `Primary run artifact` | Use `3007.053` if space allows |
| burst EPS | `6359` | `6359.0` | `phase9_full_platform_stress_20260313T203100Z phase9_stress_summary.json`, `platform.production_readiness.plan.md`, `b_production_readiness.notes.md` | `Primary run artifact` | Exact enough already |
| recovery EPS | `3017` or `3017.517` | `3017.516666666667` | `phase9_full_platform_stress_20260313T203100Z phase9_stress_summary.json`, `platform.production_readiness.plan.md`, `b_production_readiness.notes.md` | `Primary run artifact` | Use `3017.517` if space allows |

Recommended phrasing:
- `Integrated closure held at 3049.811 steady / 6188 burst / 3019 recovery EPS.`
- `Widened bounded stress then held over 2.36M admitted events at 3007.053 steady / 6359 burst / 3017.517 recovery EPS.`

---

## Slide 8 - Governed MLOps corridor

Recommended outward-facing use:
- use the evaluation metrics only if the slide is explicitly making a model-quality point
- source them from the governed learning / runtime-coupled evidence, not just from a standalone training green
- if GPT-5.4 wants one clean metric pair, this pair is now supportable

| Claim | Deck display | Exact value | Best source | Evidence grade | Notes |
|---|---:|---:|---|---|---|
| AUC ROC | `0.91` | `0.9104674176699058` | `phase9_full_platform_stress_20260313T203100Z phase9_stress_summary.json`, `phase6_learning_coupled_20260313T010847Z phase6_learning_coupled_summary.json` | `Primary run artifact` | Prefer this governed-coupled value over the earlier standalone `0.952...` managed-learning run if the deck is proving corridor continuity |
| Precision@50 | `1.00` | `1.0` | `phase9_full_platform_stress_20260313T203100Z phase9_stress_summary.json`, `phase6_learning_coupled_20260313T010847Z phase6_learning_coupled_summary.json` | `Primary run artifact` | Stable exact value |

Important note:
- the repo also contains an earlier standalone managed-learning summary with `auc_roc = 0.9521772450876929`
- for the outward-facing deck, the stronger claim is the governed value that survives into the later coupled runtime story:
  - `AUC 0.91`
  - `Precision@50 1.00`

Recommended phrasing:
- `The governed learning corridor produced reproducible candidate truth and later carried forward runtime-usable learning authority with AUC 0.91 and Precision@50 1.00 on the accepted coupled story.`

---

## Slide 9 - Operable, auditable, recoverable

Recommended outward-facing use:
- this slide should stay proof-bullet oriented
- the strongest compact bullets are:
  - `6 critical alarms`
  - `OK -> ALARM -> OK drill`
  - `node count after idle = 0`
  - optional: `10 / 10` required local evidence and `18 / 18` readable refs

| Claim | Deck display | Exact value | Best source | Evidence grade | Notes |
|---|---:|---:|---|---|---|
| critical alarms present | `6 critical alarms` | `6` | `platform.production_readiness.plan.md`, `b_production_readiness.notes.md`, `phase9_stress_summary.json` | `Primary plan / implementation note` | Repeated across the rebuilt Phase 7 and integrated Phase 8 story |
| alert drill exercised | `OK -> ALARM -> OK` | `OK -> ALARM -> OK` | `platform.production_readiness.plan.md`, `b_production_readiness.notes.md`, `phase7_alert_runbook_drill.json` | `Primary run artifact` | Drill is explicitly on `fraud-platform-dev-full-ig-lambda-errors` |
| residual non-essential compute after idle | `zero residual compute after idle` | `0` | `platform.production_readiness.plan.md`, `b_production_readiness.notes.md`, `phase9_stress_summary.json` | `Primary run artifact` | In the evidence, this is carried as `node count after idle = 0` |
| required local evidence present | `10 / 10` | `10 / 10` | `b_production_readiness.notes.md` | `Primary plan / implementation note` | Useful as a secondary proof bullet |
| readable Phase 5 refs | `18 / 18` | `18 / 18` | `b_production_readiness.notes.md`, `phase9_stress_summary.json` | `Primary run artifact` | Useful as a secondary proof bullet |

Recommended phrasing:
- `Operability closed on 6 critical alarms, a live OK -> ALARM -> OK drill, exact run reconstruction, readable evidence refs, and node count after idle = 0.`

---

## Slide 10 - Cost realism

Recommended outward-facing use:
- do not flatten the whole `2026-03-01` to `2026-03-13` window into one clean proving-cost story
- the repo itself says the clearest bounded estimate of accepted production-readiness execution cost is the later proving-plane window:
  - `2026-03-10` to `2026-03-13`
- if GPT-5.4 wants one simple recruiter-safe frame, that later window is the better choice

### Broad AWS cost snapshot

| Claim | Deck display | Exact value | Best source | Evidence grade | Notes |
|---|---:|---:|---|---|---|
| broad AWS cost snapshot window | `1-13 March` | `2026-03-01` to `2026-03-13` | `platform.production_readiness.plan.md` | `Primary plan / implementation note` | Valid, but includes earlier methodology formation and tax artifacts |
| broad window total | `4101.39 USD` | `4101.39 USD` | `platform.production_readiness.plan.md` | `Primary plan / implementation note` | Includes `Tax = 708.38 USD` on `2026-03-01` |

### Recommended outward-facing bounded readiness cost frame

| Claim | Deck display | Exact value | Best source | Evidence grade | Notes |
|---|---:|---:|---|---|---|
| accepted proving-plane window | `10-13 March` | `2026-03-10` to `2026-03-13` | `platform.production_readiness.plan.md` | `Primary plan / implementation note` | The plan explicitly says this remains the clearest bounded estimate of accepted production-readiness execution cost |
| bounded readiness cost total | `1647.82 USD` | `1647.82 USD` | `platform.production_readiness.plan.md` | `Primary plan / implementation note` | Sum of `2026-03-10` through `2026-03-13` daily totals |
| `DynamoDB` | `354.49 USD` | `354.49 USD` | `platform.production_readiness.plan.md` | `Primary plan / implementation note` | Ingress idempotency and receipt writes, especially before the compact-row fix |
| `Lambda` | `290.53 USD` | `290.53 USD` | `platform.production_readiness.plan.md` | `Primary plan / implementation note` | Truthful active ingress hot-path execution |
| `API Gateway` | `237.58 USD` | `237.58 USD` | `platform.production_readiness.plan.md` | `Primary plan / implementation note` | Real ingress admission once the live front door was pinned |
| `S3` | `170.41 USD` | `170.41 USD` | `platform.production_readiness.plan.md` | `Primary plan / implementation note` | Evidence traffic plus bounded learning-basis materialization |
| `RDS / Aurora` | `142.94 USD` | `142.94 USD` | `platform.production_readiness.plan.md` | `Primary plan / implementation note` | Aurora ACU and IO pressure from checkpoints and bounded proofs |
| `MSK` | `130.19 USD` | `130.19 USD` | `platform.production_readiness.plan.md` | `Primary plan / implementation note` | Kafka serverless floor plus traffic-driven bytes |

Recommended phrasing:
- `The full 1-13 March AWS window totaled 4101.39 USD, but the cleaner accepted production-readiness cost window is 10-13 March at 1647.82 USD.`
- `In that accepted window, the dominant service families were DynamoDB, Lambda, API Gateway, S3, RDS/Aurora, and MSK.`

---

## Recommended handoff notes for GPT-5.4

1. For Slide 5, treat the shared-world counts as primary-confirmed, not just storyline rhetoric.
2. For Slide 7, use the exact integrated and widened-stress figures from the accepted run artifacts.
3. For Slide 8, use `AUC 0.91` and `Precision@50 1.00` only if the slide is explicitly making a model-quality or governed-learning claim.
4. For Slide 9, prefer `node count after idle = 0` over the looser phrase `zero residual compute after idle` if space allows.
5. For Slide 10, prefer the bounded `2026-03-10` to `2026-03-13` cost story over the whole-window `2026-03-01` to `2026-03-13` story.
