# Execution Plan - Service Requirement Gathering And BI Translation Slice

As of `2026-04-08`

Purpose:
- turn the chosen South Tyneside and Sunderland NHS Foundation Trust `E` slice into a concrete execution order tied to the BI reporting-product pack already available from South Tyneside `01` and the anomaly-and-control pack already available from South Tyneside `02`
- keep the work broad-ask-first, refined-requirement-second, service-facing-translation-third, and better-option-fourth rather than drifting into generic stakeholder rhetoric, broad business-partner ownership, or synthetic service-design language
- prove one bounded requirement-capture output, one service-facing BI translation output, one better-option output, and one service-value note from the same governed BI lane
- keep execution memory-safe by reusing compact South Tyneside `01` and `02` outputs before considering any wider raw query footprint

Execution substrate:
- governed local artefacts already available in `artefacts/analytics_slices/`
- the South Tyneside `01_bi_reporting_product_and_reporting_platform_support` pack as the primary BI product base
- the South Tyneside `02_anomaly_resolution_and_trusted_output_control` pack as the primary trust-and-correction base
- compact new South Tyneside outputs to be written under `artefacts/analytics_slices/data_analyst/south_tyneside_and_sunderland_nhs_foundation_trust/03_service_requirement_gathering_and_bi_translation/`

Primary rule:
- confirm the inherited South Tyneside `01` and `02` packs first
- identify the smallest truthful service requirement-and-translation question second
- define one broad ask and one refined requirement third
- materialise one requirement-capture output fourth
- materialise one service-facing BI translation output fifth
- materialise one better-option output sixth
- write one service-value note seventh
- package the release checks and caveats only after the requirement, translation, and better-option surfaces are explicit
- never reopen broad raw detailed surfaces if the requirement-and-translation question can be answered from compact governed outputs
- keep the stakeholder language below live business-partner, stakeholder-office, or enterprise service-design ownership
- if a figure is used later, it must materially clarify the requirement-shaping or preferred-output story rather than duplicate the translation surface

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the South Tyneside `01` and `02` packs are already strong enough to support one requirement-shaping and BI-translation analogue
- the first pass can stay on broad ask, refined requirement, translation, and better-option direction without needing any stronger stakeholder-estate simulation
- one explicit broad ask can be tightened clearly enough to support a useful BI requirement
- one bounded better-option direction can be stated once the requirement and translation surfaces are explicit
- the strongest truthful end state is likely to be clearer service-facing BI use rather than a stronger stakeholder-management claim

Candidate first-pass reusable foundation:
- South Tyneside `01_bi_reporting_product_and_reporting_platform_support`
- South Tyneside `02_anomaly_resolution_and_trusted_output_control`

Working assumption about the requirement-and-translation question:
- the slice should stay on the same governed BI reporting-product lane
- the lane should support one explicit service ask and one tighter requirement
- the translation surface should be visible enough to act as a bounded service-facing explanation layer
- the resulting outputs should help a service user understand what was really needed, what output is preferable, and why that output is safer and more useful

Important warning:
- these assumptions must be tested rather than carried forward casually
- if the inherited lane does not support a clean requirement-and-translation pack, narrow the claim to service-facing explanation rather than inventing a stronger stakeholder-management story

## 2. Broad-Ask-To-Better-Output Posture

This slice must not begin as another BI-product pack and it must not become a generic stakeholder note.

The correct posture is:
- confirm the inherited South Tyneside `01` and `02` packs first
- define one broad service ask second
- define one refined BI requirement third
- materialise one requirement-capture output fourth
- materialise one service-facing BI translation output fifth
- materialise one better-option output sixth
- write one service-value note seventh
- package the release checks and caveats eighth
- use Python only after the inherited compact outputs have already bounded the requirement-and-translation question

This matters because the South Tyneside responsibility is about gathering requirements, explaining complex BI meaning, and helping users get more value from reporting outputs, and the execution should therefore read like one bounded requirement-and-translation pack rather than broad stakeholder rhetoric.

## 2A. Memory And Query Discipline

This slice must be executed with explicit memory discipline.

The correct posture is:
- do not pull broad raw surfaces into pandas
- do not reopen wide raw profiling if the requirement-and-translation question can be answered from the existing South Tyneside `01` and `02` packs
- do not assume service-facing language justifies a broader stakeholder or warehouse reconstruction

The correct query discipline is:
- start with the South Tyneside `01` fact pack, prepared reporting base, management-information output, reporting-platform-support output, and release checks
- use the South Tyneside `02` anomaly summary, robustness-check output, corrective-action output, and trusted-output note where they sharpen the safer requirement choice
- use inherited compact outputs first
- if a probe is needed, filter the period and fields at scan time
- materialise compact requirement, translation, better-option, and release outputs only after the requirement-and-translation question is fixed
- let Python read only those compact outputs, not broad raw source families

The default execution ceiling for this slice is:
- inherited South Tyneside `01` and `02` packs first
- one compact requirement-capture output second
- one compact service-facing BI translation output third
- one compact better-option output fourth
- one service-value note fifth
- one release-check surface sixth

If a query starts behaving like whole-Trust stakeholder-management simulation rather than a bounded BI translation proof, stop and narrow it before proceeding.

## 3. First-Pass Objective

The first-pass objective is:

`build one service-requirement and BI-translation pack with one broad ask, one refined requirement, one service-facing translation surface, one better-option direction, and one bounded service-value reading`

The proof object is:
- `service_requirement_gathering_and_bi_translation_v1`

The first-pass output family is:
- one requirement-capture output
- one service-facing BI translation output
- one better-option output
- one release-check output
- one service-value note
- one scope note
- one caveats note

## 4. Requirement-And-Translation Gate

Before building any South Tyneside `E` output, run a bounded requirement-and-translation gate.

The first profiling pass must answer:
- does the inherited South Tyneside BI pack already contain a clear broad ask versus preferred-output story?
- can the same controlled base support both translation reading and better-option direction?
- can one compact requirement surface distinguish a useful BI requirement from a broader or looser request?
- does the resulting pack remain a requirement-and-translation proof rather than a broader stakeholder-function story?
- does the resulting pack stay compact enough to act as a bounded proof object?

Required checks:
- continuity of the inherited BI reporting-product grain
- continuity of the shared focus and trusted-output posture
- continuity of the inherited anomaly and controlled-reuse posture where relevant
- ability to state one bounded service-value consequence from the same pack

Those checks should be implemented as:
- aggregate-only or compact-output probes
- inherited compact outputs first
- no broad row materialisation into memory

Decision rule:
- if the BI reporting pack remains explicit and compact, proceed into requirement, translation, and better-option materialisation
- if the question is too broad or ambiguous, narrow the slice before proceeding

## 5. Candidate Analytical Base

The first-pass analytical base should stay bounded and explicit.

Each component should have one stated purpose:
- inherited prepared reporting base
  - define the recurring BI structure available for service use
- inherited management-information output
  - define the main service-facing BI surface under discussion
- inherited reporting-platform-support output
  - define the trusted-source posture available to reuse
- inherited anomaly and trusted-output surfaces
  - define why some broader asks should be narrowed before wider reuse
- requirement layer
  - define what the service user originally wants and what should be captured instead
- translation layer
  - define how the current BI meaning should be explained clearly
- better-option layer
  - define what output should be preferred and why

If inherited outputs do not support one of those components cleanly, adapt by narrowing the claim rather than stretching earlier slices past their truth boundary.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. inherited BI-pack and anomaly-pack confirmation
2. broad-ask and refined-requirement materialisation
3. service-facing BI translation materialisation
4. better-option output materialisation
5. service-value note
6. release-check and caveat packaging

The transformations should not be hidden inside vague stakeholder language.

## 7. Bounded Build Order

### Step 1. Confirm the inherited South Tyneside `01` and `02` packs

Build small profile checks only for:
- the prepared reporting base
- the management-information output
- the reporting-platform-support output
- the anomaly summary
- the trusted-output note or equivalent compact output
- the release checks

Goal:
- define the smallest truthful requirement-and-translation question
- prove that the same BI reporting pack can support a bounded service-facing slice without reopening broad scope

### Step 2. Define the requirement-capture output

Create one bounded output, for example:
- `requirement_capture_output_v1`

This output should:
- state one broad ask as originally framed
- state one refined BI requirement
- remain compact enough to act as the centre of the requirement-shaping proof

### Step 3. Define the service-facing BI translation output

Create one bounded output, for example:
- `service_facing_translation_output_v1`

This output should:
- state how the current BI output should be explained
- show what the service user should focus on
- remain clearly tied to the inherited BI reporting lane

### Step 4. Define the better-option output

Create one bounded output, for example:
- `better_option_output_v1`

This output should:
- show what reporting or analysis option should be preferred
- expose why that option adds more value than the broad ask
- stay proportional to the evidence

### Step 5. Write the service-value note

Write one bounded note, for example:
- `service_value_note_v1.md`

This note should:
- explain what the user gains from the refined requirement
- explain what becomes clearer or safer through the preferred output
- stay below full stakeholder-management or business-partner rhetoric

### Step 6. Package the release checks and caveats

Create one bounded output, for example:
- `requirement_translation_release_checks_v1`

Write:
- the requirement-translation scope note
- the requirement-capture note
- the service-facing translation note
- the better-option note
- the service-value note
- the caveats note
- the regeneration README

Only after the requirement, translation, and better-option surfaces are real.

## 8. Service-Value Strategy

The service-facing story has to stay honest.

The first-pass service-value strategy should answer:
- what exactly was the broad ask?
- how does the refined requirement improve usefulness?
- how does the translation surface reveal the right reading for a non-analytical user?
- why does the slice stop at requirement shaping and BI translation rather than stronger stakeholder ownership?

Allowed posture:
- one bounded broad ask
- one compact refined requirement
- one service-facing translation surface
- one better-option direction
- one repeatable release-check pack

Disallowed posture:
- claiming whole-Trust stakeholder-management leadership
- asserting enterprise service-design ownership
- importing generic customer-relationship language as fake proof

Decision rule:
- every retained element must earn its place in either:
  - requirement capture
  - BI translation
  - better-option direction
  - service-value explanation
- if an element does not support one of those purposes, drop it

## 9. Better-Option Strategy

This is what makes the slice useful rather than merely descriptive.

The first-pass better-option layer should answer:
- what did the user really need?
- why is the first broad ask too loose or less useful?
- what should be preferred before wider service reuse?
- what can a service user now rely on more confidently?

Required posture:
- use the inherited BI reporting pack to support one explicit better-option reading
- use the anomaly and trusted-output surfaces where they sharpen that reading
- keep the consequence proportional to the evidence

Disallowed posture:
- claiming whole-stakeholder ownership
- claiming organisation-wide requirement-management authority
- claiming service redesign consequences not evidenced by the pack

## 10. Planned Deliverables

Requirement-and-translation assets:
- one requirement-capture output
- one service-facing BI translation output
- one better-option output
- one service-value note

Support assets:
- one scope note
- one caveats note

Controls:
- one release-check output
- one regeneration README
- one changelog

## 11. Suggested Artefact Names

Recommended names:
- `requirement_capture_output_v1.parquet`
- `service_facing_translation_output_v1.parquet`
- `better_option_output_v1.parquet`
- `requirement_translation_release_checks_v1.parquet`
- `requirement_translation_scope_note_v1.md`
- `requirement_capture_note_v1.md`
- `service_facing_translation_note_v1.md`
- `better_option_note_v1.md`
- `service_value_note_v1.md`
- `requirement_translation_caveats_v1.md`
- `README_requirement_translation_regeneration.md`
- `CHANGELOG_requirement_translation.md`
- `execution_fact_pack.json`

## 12. Definition Of Green Before Reporting

Do not move to the execution report until the following are true:
- one explicit broad ask and one refined requirement are fixed
- one service-facing BI translation surface is fixed
- one better-option output exists
- one service-value note exists
- one release-check surface exists
- the pack stays clearly distinct from BI product delivery and anomaly-control work
- the pack stays clearly bounded below whole-Trust stakeholder-management ownership
- the whole pack stays compact and rerunnable from governed outputs

## 13. Failure Conditions

Stop and narrow the slice if:
- the broad ask cannot be stated without broad ambiguity
- the translation surface remains mostly routine BI description with no real service-facing meaning
- the evidence would force fake stakeholder-management language
- the better-option note drifts into consequences the pack cannot support
- the execution starts reopening broad raw scope without materially strengthening the requirement-and-translation proof

## 14. Immediate Next-Step Order

1. Run the inherited requirement-and-translation gate over South Tyneside `01` and `02`.
2. Define one compact requirement-capture output from that pack.
3. Materialise the service-facing BI translation output and the better-option output.
4. Write the service-value note.
5. Package the caveats, changelog, and regeneration note.
