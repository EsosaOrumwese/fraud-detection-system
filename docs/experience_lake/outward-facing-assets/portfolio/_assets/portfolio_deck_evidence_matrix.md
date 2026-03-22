# Portfolio Deck Evidence Matrix

As of `2026-03-21`

Purpose:
- map each core deck slide to the evidence already available in the repo
- distinguish what is already covered, what is only partially covered, and what still needs a user-supplied artifact or preference

Boundary:
- this matrix is for the recruiter-facing core deck described in the local `scratch_files/scratch.md` working source
- this matrix is about content and evidence, not slide design

Important note on AWS cost evidence:
- I do **not** have live access to your AWS account or billing console
- I can only use cost data that already exists in the repo:
  - implementation notes
  - experience-lake notes
  - outward-facing storyline docs
  - any saved screenshots / exports / tables committed to the workspace

Evidence status legend:
- `Covered` = repo already contains strong enough evidence inputs
- `Partial` = repo contains most of the story, but the slide would benefit from a tighter fact pack or artifact
- `User-needed` = still needs a user-supplied preference, link, or external artifact

---

## Matrix

| Slide | Main claim / job | Evidence status | What I can provide now | Primary repo sources | Still needed from user |
|---|---|---|---|---|---|
| `1` | Cover / identity | `Partial` | role-first identity wording, opening claim posture, subtitle options | [canonical-storyline.md](../../canonical-storyline/canonical-storyline.md) | final title/subtitle preference, whether to show your name |
| `2` | The claim | `Covered` | exact professional claim block, shorter variant, anti-project framing | [canonical-storyline.md](../../canonical-storyline/canonical-storyline.md) | none, unless you want different emphasis |
| `3` | Storyline overview | `Covered` | the full seven-stage progression and one-line consequences | [canonical-storyline.md](../../canonical-storyline/canonical-storyline.md), [canonical-storyline.vertical.mmd](../../canonical-storyline/canonical-storyline.vertical.mmd) | none |
| `4` | Governed fraud world | `Partial` | the world-first claim, layered realism logic, legitimacy-gated world framing, source-backed content summary | data-engine authority docs plus outward storyline, especially [canonical-storyline.md](../../canonical-storyline/canonical-storyline.md) | optional if you want a specific engine visual or screenshot used |
| `5` | One shared operating world | `Partial` | shared-world claim, runtime/case/label/ML coherence story, headline count pack as currently expressed outwardly | [canonical-storyline.md](../../canonical-storyline/canonical-storyline.md), local `scratch_files/scratch.md` working source | optional if you want a specific count table or screenshot; otherwise better fact-pack extraction is enough |
| `6` | Real ML platform | `Covered` | simplified platform scope, owned boundaries, named AWS/managed surfaces, recruiter-safe architecture input set | [a_production_wiring.notes.md](../../../dev_full/a_production_wiring/a_production_wiring.notes.md), local wiring graph exports under `docs/experience_lake/dev_full/a_production_wiring/assets/`, and the accepted readiness graph family under `docs/design/platform/dev_full/graph/readiness/` | none, unless you want a specific diagram emphasized |
| `7` | Earned production readiness | `Partial` | readiness meaning, integrated proof story, widened stress story, doctrine-backed pressure framing | [b_production_readiness.notes.md](../../../dev_full/bi_production_readiness/b_production_readiness.notes.md), production-readiness plan / implementation docs, [canonical-storyline.md](../../canonical-storyline/canonical-storyline.md) | optional if you want a specific run summary screenshot; otherwise the better next step is a source-traced metric table |
| `8` | Governed MLOps corridor | `Partial` | governed corridor story from runtime truth to runtime authority, managed-surface and rollback framing, learning-boundary logic | [a_production_wiring.notes.md](../../../dev_full/a_production_wiring/a_production_wiring.notes.md), [b_production_readiness.notes.md](../../../dev_full/bi_production_readiness/b_production_readiness.notes.md), Group 6 graph family, [platform-production-standard.md](../../../platform-production-standard.md) | exact eval metrics or chosen screenshots if you want them featured rather than recreated structurally |
| `9` | Operable, auditable, recoverable | `Partial` | operator chain, auditability, run reconstruction, idle/restore, alert/runbook doctrine | [b_production_readiness.notes.md](../../../dev_full/bi_production_readiness/b_production_readiness.notes.md), Group 7 graph family, [platform-production-standard.md](../../../platform-production-standard.md) | optional if you want real screenshots; otherwise a curated proof-bullet pack would be better |
| `10` | Cost realism | `Partial` | cost-to-outcome doctrine, cost-as-boundary framing, service-family explanation where repo notes already discuss it | [b_production_readiness.notes.md](../../../dev_full/bi_production_readiness/b_production_readiness.notes.md), Group 7 cost path material, [platform-production-standard.md](../../../platform-production-standard.md) | best if you provide a billing export, screenshot, or final trusted service-family cost table if not already committed somewhere I can trace cleanly |
| `11` | Current operating mission | `Covered` | current capstone operating posture, what is already earned, what is not yet being overclaimed, live operating mission framing | local `docs/experience_lake/dev_full/bii_production_proven/b_production_proven.notes.md` working note, [dev-full_production-proving.md](../../../../../model_spec/platform/pre-design_decisions/dev-full_production-proving.md) | none, unless you want a current mission artifact featured |
| `12` | Why this matters for the role | `Covered` | recruiter-facing role map, seniority signals, artifact-to-role translation | [recruiter-expectation_MLPlatformEngr.md](../../../recruiter-expectation_MLPlatformEngr.md), [recruiter-expectation_MLOps.md](../../../recruiter-expectation_MLOps.md), [platform-production-standard.md](../../../platform-production-standard.md) | only your final preference on role emphasis if you want bias toward one target title |
| `13` | Close / links | `User-needed` | closing posture text | outward-facing doctrine only | GitHub URL, LinkedIn URL, any portfolio/home link, contact preference |

---

## What I can improve next without needing anything from you

1. build a `headline metrics fact pack` for slides `5`, `7`, `8`, `9`, and `10`
2. trace each numeric claim in the local `scratch_files/scratch.md` working source back to its best available source
3. create a `diagram source pack` for slides `4`, `6`, `8`, and `9`
4. create a `cost evidence pack` from repo-visible cost notes and any committed billing artifacts I can locate

## Things that still genuinely need you

- final opening identity preference for slide `1`
- role emphasis preference for slide `12` if you want one
- close-slide links and contact decisions for slide `13`
- any specific screenshots you insist on using instead of recreated visuals
