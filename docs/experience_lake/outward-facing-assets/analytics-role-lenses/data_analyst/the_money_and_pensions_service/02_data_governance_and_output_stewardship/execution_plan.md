# Execution Plan - Data Governance And Output Stewardship Slice

As of `2026-04-04`

Purpose:
- turn the chosen Money and Pensions Service `3.A` slice into a concrete execution order tied to the governed mixed-source reporting pack already available in the repo
- keep the work governance-and-output-first, requirement-first, and release-safety-first rather than drifting into generic governance rhetoric, broad policy ownership, or a repeat of the mixed-source reporting slice
- prove one governed output lane, one explicit data-requirements surface, one output-control surface, and one bounded stewardship note from the same mixed-source base
- keep execution memory-safe by reusing the existing Money and Pensions Service `3.B` outputs before considering any wider raw query footprint

Execution substrate:
- governed local artefacts already available in `artefacts/analytics_slices/`
- the Money and Pensions Service `01_mixed_source_dashboarding_and_reporting` pack as the direct starting point
- inherited controlled-output and stewardship patterns from Claire House and InHealth slices only where they sharpen the governed-output posture
- compact new governance-and-output outputs to be written under `artefacts/analytics_slices/data_analyst/the_money_and_pensions_service/02_data_governance_and_output_stewardship/`

Primary rule:
- confirm the mixed-source reporting base first
- define the explicit required fields and dimensions second
- materialise the governed-output summary third
- materialise the output-control surface fourth
- package the stewardship and caveat notes only after the requirements and controls are explicit
- never reopen broad raw detailed surfaces if the governance-and-output question can be answered from the existing governed pack
- if figures are used later, they must be analytical control plots rather than explanatory diagrams

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the repo already contains enough governed mixed-source output structure to support one honest governance-and-output stewardship slice without a fresh analytical rebuild
- the strongest platform analogue for the Money and Pensions Service governance burden is a reporting lane with explicit required fields, dimensions, and control checks rather than abstract policy text
- one bounded governed-output summary and one control surface can be produced from the Money and Pensions Service `3.B` pack
- one stewardship note can be stated from that same lane without widening scope into a full enterprise governance or information-management programme

Candidate first-pass reusable foundations:
- Money and Pensions Service `01_mixed_source_dashboarding_and_reporting`
- Claire House `01_trusted_data_provision_and_integrity`
- Claire House `05_data_quality_audit_and_governance_support`
- InHealth `02_patient_level_dataset_stewardship`

Working assumption about the governance question:
- the slice should focus on the governed output lane only
- the output should show what the mixed-source pack must contain and how it remains controlled
- the slice should prove governance inside the reporting lane, not literal ownership of the wider `CX&Q` governance function

Important warning:
- these assumptions must be tested rather than carried forward casually
- if the inherited outputs cannot support a clean requirements-and-control surface, narrow the claim rather than inventing synthetic governance layers

## 2. Governance-And-Output-First Posture

This slice must not begin as another dashboard slice and it must not collapse into a generic governance memo.

The correct posture is:
- confirm the inherited governed output lane first
- identify the explicit required fields and shared dimensions second
- define the control expectations third
- build the governed-output summary fourth
- build the output-control surface fifth
- write the stewardship and caveat notes sixth
- use Python only after the inherited compact outputs have already bounded the governance-and-output question

This matters because the Money and Pensions Service responsibility is about managing governed outputs, and the execution should read like stewardship of a usable analytical lane rather than either policy writing or a second reporting slice.

## 2A. Memory And Query Discipline

This slice must be executed with explicit memory discipline.

The correct posture is:
- do not pull broad raw surfaces into pandas
- do not reopen wide raw profiling if the governance-and-output question can be answered from the existing mixed-source pack
- do not assume “data governance” justifies a fresh rebuild when the proof can be made from controlled compact surfaces

The correct query discipline is:
- start with the Money and Pensions Service `3.B` outputs before any new materialisation
- use inherited reporting base, summary, detail, and release-check outputs first
- if a probe is needed, filter the window and fields at scan time
- materialise compact requirements and control outputs only after the governed lane is explicit
- let Python read only those compact outputs, not raw detailed source families

The default execution ceiling for this slice is:
- inherited governed output lane first
- one compact data-requirements surface second
- one compact output-control surface third
- one compact note set fourth

If a query starts behaving like a full governance programme rebuild rather than a bounded governed-output proof, stop and narrow it before proceeding.

## 3. First-Pass Objective

The first-pass objective is:

`build one governed mixed-source output pack over the existing reporting lane, with one explicit data-requirements surface, one output-control surface, and one bounded stewardship note`

The proof object is:
- `data_governance_and_output_stewardship_v1`

The first-pass output family is:
- one governed-output summary
- one data-requirements output
- one output-control output
- one governed-output release-check output
- one governance-and-output scope note
- one data-requirements note
- one output-control note
- one output-stewardship note

## 4. Early Scope Gate

Before building either the governed-output summary or the output-control surface, run a bounded scope gate.

The first profiling pass must answer:
- which Money and Pensions Service `3.B` outputs are the true governed base for this slice?
- what fields and dimensions are required to keep that base usable?
- which control expectations are already explicit and which need to be made explicit?
- can the governed-output summary and control surface both be produced from the same compact lane?
- do the row counts, fields, and current notes show that the slice can remain compact?

Required checks:
- continuity of the integrated reporting base
- continuity of shared dimensions and summary/detail dependencies
- ability to define one compact required-field set
- ability to define one compact output-control surface without diverging logic

Those checks should be implemented as:
- aggregate-only or compact-output probes
- inherited compact outputs where available
- no broad row materialisation into memory

Decision rule:
- if the inherited mixed-source lane is explicit enough, proceed with the bounded governance-and-output pack
- if not, add one compact control layer rather than broadening the query footprint

## 5. Candidate Analytical Base

The first-pass analytical base should stay bounded and explicit.

Each component should have one stated purpose:
- mixed-source reporting base
  - define the governed lane underneath the outputs
- summary and detail dependency surface
  - define which outputs depend on that lane
- data-requirements layer
  - define what the lane must contain to remain usable
- output-control layer
  - define whether the governed lane is still release-safe and consistent
- stewardship note
  - define why the lane is both governed and usable
- release or repeatability checks
  - define whether the pack is controlled enough to reuse

If inherited outputs do not support one of those components cleanly, adapt by narrowing the governed-output claim rather than stretching earlier slices past their truth boundary.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. inherited governed-lane confirmation and requirements profiling
2. data-requirements surface materialisation
3. governed-output summary materialisation
4. output-control surface materialisation
5. note and caveat packaging

The transformations should not be hidden inside vague governance language or manual copy-paste.

## 7. Bounded Build Order

### Step 1. Confirm the inherited governed output lane

Build small profile checks only for:
- the mixed-source reporting base
- the dashboard summary output
- the supporting detail output
- the existing release-check output
- any inherited stewardship or control notes needed to state the governed-output posture safely

Goal:
- define the governance-and-output slice honestly
- prove that the Money and Pensions Service `3.B` pack can be repurposed into a governed-output proof without broad raw rebuild

### Step 2. Materialise the data-requirements output

Create one bounded output, for example:
- `governed_output_data_requirements_v1`

This output should:
- show the required dimensions and fields for the governed lane
- make the shared dependencies explicit
- remain compact enough to act as a stewardship surface rather than a policy catalogue

### Step 3. Materialise the governed-output summary

Create one bounded output, for example:
- `governed_output_summary_v1`

This output should:
- show the governed lane at a top level
- make the output pack dependency explicit
- remain tied to the same compact controlled logic

### Step 4. Materialise the output-control surface

Create one bounded output, for example:
- `governed_output_control_checks_v1`

This output should:
- show whether the governed lane still meets its required control expectations
- keep release and structure checks explicit
- avoid becoming a generic audit sheet detached from the reporting lane

### Step 5. Package the notes and caveats

Write:
- the governance-and-output scope note
- the data-requirements note
- the output-control note
- the output-stewardship note
- the caveats and regeneration note

Only after the governed-output summary and control surface are real.

## 8. Requirement-Surface Strategy

The requirement surface has to stay honest.

The first-pass requirement strategy should answer:
- what fields and dimensions are required?
- why are they required for the governed lane to remain usable?
- which outputs depend on them?
- why does that make the reporting lane governed rather than merely convenient?

Allowed requirement posture:
- one compact required-field and dimension surface tied directly to the reporting pack
- one compact control surface tied to the same lane

Disallowed requirement posture:
- inventing broad governance standards or policy obligations not materially evidenced by the slice

Decision rule:
- every retained requirement must earn its place in either:
  - governed output usability
  - release safety
  - stewardship explanation
- if a field or rule does not support one of those purposes, drop it

## 9. Documentation And Control Strategy

The slice is not complete unless another analyst could understand and review the governed-output logic responsibly.

The documentation and control pack should answer:
- what the governed lane is
- what it must contain
- which outputs depend on it
- what controls keep it release-safe
- what the slice does and does not prove

Create:
- `governed_output_scope_note_v1.md`
- `data_requirements_note_v1.md`
- `output_control_note_v1.md`
- `output_stewardship_note_v1.md`
- `governed_output_caveats_v1.md`
- `README_governed_output_regeneration.md`
- `CHANGELOG_governed_output.md`

## 10. Reproducibility Strategy

This slice is not complete unless the governed-output pack and its checks can be rerun consistently.

The first-pass reproducibility pack should include:
- versioned governed-output logic
- versioned data-requirements and control outputs
- compact release or repeatability checks
- regeneration README
- execution fact pack

## 11. Definition Of Done For Execution

Execution is only complete when all of the following are true:
- one bounded governed mixed-source output lane has been identified explicitly
- one explicit data-requirements surface has been stated
- one governed-output summary has been materialised clearly
- one output-control surface has been materialised from the same lane
- one stewardship note ties governance to output usability
- the slice remains clearly distinct from the Money and Pensions Service `3.B` reporting-product work
- the whole pack remains compact and rerunnable from inherited governed outputs

## 12. Immediate Next Step

Immediate next step after approving this execution plan:
- run the governed-output scope gate and decide which required fields, dimensions, and controls best support one honest stewardship pack without reopening any broad raw analytical rebuild
