# Portfolio Cost Evidence Pack

As of `2026-03-21`

Purpose:
- give GPT-5.4 a clean, source-backed cost pack for the portfolio deck
- avoid needing a live AWS billing screenshot to explain the production-readiness cost story
- separate:
  - retrospective cost accounting
  - live operator cost surfaces
  - outward-facing interpretation

Boundary:
- this pack is for the recruiter-facing deck described in `scratch.md`
- this pack is evidence and framing only
- it is not slide design

Core judgment:
- the repo is now strong enough to support the cost slide without any external billing screenshot
- if a screenshot is later used, it should be treated as optional visual reinforcement, not as the primary source of truth

---

## Source hierarchy

### 1. Retrospective cost authority

Primary source:
- `platform.production_readiness.plan.md`

What it gives:
- the full AWS cost snapshot for `2026-03-01` to `2026-03-13`
- daily totals
- service-family totals
- two daily service-family breakdown tables
- explicit interpretation by era
- the explicit judgment that `2026-03-10` to `2026-03-13` is the clearest bounded estimate of accepted production-readiness execution cost

### 2. Live operator cost surface

Primary source:
- `phase9_stress_operator_surface.json`

What it gives:
- the budget surface visible on the live platform
- the paired budget guardrail markdown
- the billing alarm name on the active operator surface
- the live budget snapshot:
  - `budget name = fraud-platform-dev-full-monthly`
  - `limit_amount = 300.0`
  - `actual_spend = 3493.038`
  - `last_updated = 2026-03-13 14:52:39.570000+00:00`

Important note:
- this operator-surface budget snapshot is not the same thing as the later retrospective Cost Explorer refresh captured in the readiness plan
- both are useful, but they answer different questions:
  - operator surface = was cost visible and challengeable on the live platform?
  - retrospective plan snapshot = what did the bounded proving window actually cost when summarized cleanly?

### 3. Cost-accountability reasoning

Primary source:
- `b_production_readiness.notes.md`

What it gives:
- why cost is its own readiness boundary
- why cost-to-outcome is not just reporting
- why attributed spend, budget envelopes, idle-safe posture, and cost receipts are part of platform closure

### 4. Outward-facing doctrine

Primary source:
- `platform-production-standard.md`

What it gives:
- the outward-facing rule that any cost-control claim must show:
  - unit economics
  - budget envelopes
  - idle-safe controls
  - cost-to-outcome receipts

---

## Recommended outward-facing framing

Use this framing on the deck:

- do **not** present cost as `how much AWS I spent on the project`
- present cost as:
  - `what the accepted bounded proving window cost`
  - `which service families drove that cost`
  - `why those families were materially tied to proof instead of ambient cloud residue`

The cleanest outward-facing sentence is:

- `Cost was treated as a platform boundary, not a finance afterthought: the accepted proving window stayed attributable by service family, paired live budget surfaces with idle-safe controls, and closed with explicit cost-to-outcome discipline.`

---

## Recommended deck window

### Preferred deck window

Use:
- `2026-03-10` to `2026-03-13`

Why:
- the readiness plan explicitly says this remains the clearest bounded estimate of accepted production-readiness execution cost
- this is where the proving-plane method was the active authority surface
- this avoids flattening earlier methodology formation, repin learning, and tax artifacts into the main recruiter-facing cost number

### Broader contextual window

Keep available, but do not use as the hero number unless GPT-5.4 wants appendix context:
- `2026-03-01` to `2026-03-13`

Why not as the hero:
- includes `Tax = 708.38 USD` on `2026-03-01`
- includes earlier certification resets and methodology formation
- is truthful, but less precise as an answer to `what did the accepted proving window cost?`

---

## Primary headline numbers

### Broad AWS snapshot

| Metric | Value | Best source | Use |
|---|---:|---|---|
| broad AWS window | `2026-03-01` to `2026-03-13` | `platform.production_readiness.plan.md` | appendix or context |
| broad window total | `4101.39 USD` | `platform.production_readiness.plan.md` | context only |
| tax inside broad window | `708.38 USD` | `platform.production_readiness.plan.md` | cautionary context |

### Recommended proving-window cost

| Metric | Value | Best source | Use |
|---|---:|---|---|
| accepted proving window | `2026-03-10` to `2026-03-13` | `platform.production_readiness.plan.md` | main deck |
| proving-window total | `1647.82 USD` | `platform.production_readiness.plan.md` | main deck |

### Daily totals for the proving window

| Date | Total USD |
|---|---:|
| `2026-03-10` | `275.10` |
| `2026-03-11` | `533.49` |
| `2026-03-12` | `317.49` |
| `2026-03-13` | `521.75` |

Source:
- `platform.production_readiness.plan.md`

---

## Chart-ready service-family breakdown for the recommended window

These are the strongest families to show on the main slide.

| Service family | Window total USD | Operational meaning in the repo |
|---|---:|---|
| `DynamoDB` | `354.49` | ingress idempotency and receipt writes, especially before the compact-row fix removed needless write amplification |
| `Lambda` | `290.53` | truthful active ingress hot-path execution once the live front door was pinned |
| `API Gateway` | `237.58` | real ingress admission on the accepted active boundary |
| `S3` | `170.41` | evidence traffic plus bounded learning-basis materialization |
| `RDS / Aurora` | `142.94` | Aurora ACU and IO pressure from checkpoints and bounded proofs |
| `MSK` | `130.19` | Kafka serverless floor plus traffic-driven bytes during active proof |

Source:
- `platform.production_readiness.plan.md`

Why this is the best main chart:
- it is compact
- it reflects the actual proving window
- it makes the cost story legible without pretending every AWS family matters equally

---

## Secondary service-family context

These are real, but better as footnotes or appendix context:

| Service family | Window total USD |
|---|---:|
| `CloudWatch` | `79.48` |
| `ECS` | `71.54` |
| `EC2 Compute` | `67.95` |
| `EC2 Other` | `65.72` |
| `VPC` | `22.35` |
| `EKS` | `9.60` |
| `Kinesis` | `3.84` |
| `KMS` | `0.59` |
| `Cost Explorer` | `0.35` |
| `ECR` | `0.22` |
| `SageMaker` | `0.03` |

Derived from the same daily service-family tables in:
- `platform.production_readiness.plan.md`

Use rule:
- only show these if GPT-5.4 wants a fuller cost table or appendix
- do not let them dilute the main cost story

---

## Live operator-surface cost evidence

This is the best proof that cost was part of the operating system of the platform, not only a later spreadsheet.

### Live budget surface

From `phase9_stress_operator_surface.json`:

| Field | Value |
|---|---|
| budget name | `fraud-platform-dev-full-monthly` |
| monthly limit | `300.0` |
| actual spend | `3493.038` |
| last updated | `2026-03-13 14:52:39.570000+00:00` |

### Budget guardrail markdown on the operator surface

The operator surface also carries the budget guardrail itself:

- budget name: `fraud-platform-dev-full-monthly`
- monthly limit: `300 USD`
- alert thresholds: `120`, `210`, `270`
- paired runbook: `dev_full_phase7_ops_gov_runbook.md`

### Cost-related live alarm coverage

Present alarm names include:
- `fraud-platform-dev-full-billing-estimated-charges`

Judgment:
- this proves cost was visible on the live operator surface
- it does **not** replace the later retrospective cost summary
- together, the two surfaces give the stronger outward-facing claim:
  - `cost was visible live`
  - `cost was explainable retrospectively`

---

## Cost interpretation by era

This is the reasoning GPT-5.4 should preserve if it chooses to add a short explanatory paragraph.

### Era 1 - `2026-03-01` to `2026-03-05`

Meaning:
- post-`M15` certification entry
- certification resets
- methodology formation

Deck rule:
- do not use this as the main cost story

### Era 2 - `2026-03-06` to `2026-03-09`

Meaning:
- repin learning during `road_to_prod`
- expensive discovery of the right production boundary

Deck rule:
- mention only if GPT-5.4 wants to show that the method got cheaper and more truthful once the proving-plane posture took over

### Era 3 - `2026-03-10` to `2026-03-13`

Meaning:
- proving-plane execution from truthful ingress pinning through bounded full-platform stress authorization

Deck rule:
- this is the main deck window

---

## Recommended cost slide structure for GPT-5.4

The strongest content shape is:

1. one headline number
- `Accepted proving window: 1647.82 USD over 10-13 March`

2. one compact family chart
- `DynamoDB`, `Lambda`, `API Gateway`, `S3`, `RDS/Aurora`, `MSK`

3. one interpretation line
- `The dominant spend families map directly to truthful ingress, bounded proof traffic, evidence movement, checkpoints, and managed runtime state rather than to ambient idle cloud residue.`

4. one operator-discipline line
- `Cost was live on the operator surface through budget guardrails, billing alerts, idle-safe posture, and explicit cost-to-outcome closure.`

---

## What GPT-5.4 should avoid

1. Do not use `4101.39 USD` as the only headline number.
- It is truthful, but it is a broader and noisier window.

2. Do not present cost as if it were just a screenshot from billing.
- The stronger story is cost as platform discipline.

3. Do not imply that the goal was `cheap cloud`.
- The goal was attributable, bounded, explainable spend tied to proof outcome.

4. Do not claim unit cost unless GPT-5.4 computes it explicitly from accepted counters.
- This repo supports the doctrine for unit cost strongly, but this pack does not precompute `cost per event`.

---

## Final recommendation

If GPT-5.4 wants one recruiter-safe cost message, use:

- `The cleanest bounded production-readiness cost window was 10-13 March at 1647.82 USD, with spend dominated by DynamoDB, Lambda, API Gateway, S3, RDS/Aurora, and MSK — all attributable to the accepted proving-plane boundary rather than to ambient project residue.`

If it wants one stronger supporting sentence, add:

- `The platform also carried live budget guardrails, billing alarms, idle-safe controls, and cost-to-outcome closure, so cost was treated as an operating boundary rather than as a post-run spreadsheet.`
