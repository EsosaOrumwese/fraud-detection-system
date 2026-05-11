# Execution Report - Validation Reconciliation And Cyclical Operational Control Slice

As of `2026-04-04`

Purpose:
- record what was actually executed for the Welsh Government `Payroll Data Analyst` slice around validation, discrepancy handling, reconciliation reporting, and recurring operational-control support
- preserve the truth boundary between one bounded validation-and-reconciliation control pack and any wider claim about payroll-estate ownership, statutory authority, or end-to-end processing ownership
- package the saved facts, validation summary, discrepancy findings, reconciliation output, and claim-ready evidence into one outward-facing report

Truth boundary:
- this execution was completed by building directly on compact inherited discrepancy, trusted-provision, and governed-output packs
- the slice did not rebuild a payroll-processing estate or reopen a broad raw analytical base
- the slice did not claim ownership of full payroll operations, statutory payroll compliance, or end-to-end processing control
- the slice stayed limited to one bounded recurring control view:
  - `current_plus_prior_week`
- the honest platform analogue here is:
  - `1` explicit validation rule
  - `1` bounded discrepancy class
  - `1` reconciliation-ready output
  - `1` recurring operational-support reading
  - `1` release-safe recurring control pack
- the slice therefore supports a truthful claim about validating recurring operational data, identifying discrepancies, and supporting reconciliation-ready outputs
- it does not support a claim that a full payroll-processing environment has already been delivered

---

## 1. Executive Answer

The slice asked:

`can one recurring operational data lane be validated, reconciled, and packaged in a way that keeps the output reliable enough for cyclical operational use?`

The bounded answer is:
- one recurring control window was fixed:
  - `current_plus_prior_week`
- one validation summary was produced:
  - `1`
- one discrepancy findings output was produced:
  - `1`
- one reconciliation output was produced:
  - `1`
- one explicit validation rule was fixed:
  - `1`
- one explicit discrepancy class was fixed:
  - `1`
- the current cycle still carries a material discrepancy:
  - `4.80 pp`
- the prior cycle still carries a material discrepancy:
  - `4.81 pp`
- the current authoritative conversion rate remains:
  - `9.59%`
- the trusted control-family reference remains:
  - `9.63%`
- the current recurring lane still contains:
  - `1,780,031` case-opened rows
- the control pack passed:
  - `8/8` release checks
- regeneration takes about `0.18` seconds because the slice reuses inherited controlled outputs rather than reopening raw scope

That means this slice did not just restate discrepancy handling. It turned the discrepancy into one repeatable validation-and-reconciliation pack and showed that the authoritative view stays within the trusted control family while the discrepant view remains unsuitable for recurring release.

## 2. Slice Summary

The slice executed was:

`one validation-and-reconciliation control pack over a recurring operational lane, with one bounded discrepancy class, one reconciliation surface, and one repeatable recurring-support reading`

This was chosen because it allowed a direct response to the Welsh Government requirement:
- validate detailed or high-consequence operational data
- identify discrepancies and mismatches
- support reconciliation reporting
- keep recurring operational outputs accurate and defensible

The main delivered outputs were:
- one validation summary
- one discrepancy findings output
- one reconciliation output
- one recurring operational-support note
- one compact fact pack
- one scope note
- one validation-rules note
- one caveats note
- one regeneration README

## 3. How This Maps To The Slice Plan

The execution stayed aligned to the approved Welsh Government `A + D` slice rather than drifting into a dashboard-first story or a fake payroll-function pack.

The delivered scope maps back to the planned lens responsibilities as follows:
- `03 - Data Quality, Governance, and Trusted Stewardship`: one explicit validation rule, one discrepancy class, and one controlled balancing surface
- `02 - BI, Insight, and Reporting Analytics`: one reconciliation-ready output that makes the balancing state clear and reusable
- `01 - Operational Performance Analytics`: one bounded recurring operational-support reading tied to the same control lane
- `09 - Delivery Operating Discipline and Repeatability`: one rerunnable release-check pack proving the recurring surface remains safe to use

The report therefore needs to be read as proof of recurring operational validation and reconciliation support, not as proof that the whole Welsh Government payroll environment is already in place.

## 4. Execution Posture

The execution followed the intended validation-first and balancing-first posture rather than broad payroll simulation.

The working discipline was:
- start from the existing discrepancy and control packs
- fix the validation rule before writing any recurring operational-use language
- keep the first pass at aggregate-control and balancing level
- materialise one discrepancy findings output and one reconciliation-ready output from the same lane
- state the recurring operational-support consequence only after the balancing state was explicit
- use Python only after the inherited output set had already reduced the slice to compact control tables

This matters for the truth of the slice because the requirement is about operational-data accuracy and reconciliation support, and the execution should therefore reflect one controlled recurring pack rather than inflated payroll-estate rhetoric.

## 5. Bounded Build That Was Actually Executed

### 5.1 Validation rule

The first step was to fix the smallest truthful validation rule already supported by the inherited control lane.

Observed validation facts:

| Measure | Value |
| --- | ---: |
| Validation rules fixed | 1 |
| Cycles covered | 2 |
| Current case-opened rows | 1,780,031 |
| Current authoritative rate | 9.59% |
| Prior authoritative rate | 9.62% |
| Trusted control reference rate | 9.63% |

The authoritative rule was:
- numerator: case-opened rows
- authoritative denominator: `flow_rows`
- non-authoritative denominator: `entry_event_rows`

Meaning:
- the recurring control lane stayed small and explicit
- the slice therefore proved validation logic rather than generic reporting review

### 5.2 Discrepancy findings

The slice then materialised one bounded discrepancy class rather than stopping at the rule itself.

Observed discrepancy facts:

| Cycle | Authoritative rate | Discrepant rate | Absolute gap |
| --- | ---: | ---: | ---: |
| Current | 9.59% | 4.80% | 4.80 pp |
| Prior | 9.62% | 4.81% | 4.81 pp |

Discrepancy class:
- `denominator_drift_doubles_reporting_base`

Reading:
- the same numerator is preserved
- the denominator drift doubles the reporting base
- the reported rate is therefore halved and materially distorted

Meaning:
- the discrepancy is large enough to affect a recurring operational reading
- the discrepancy remains stable across both retained cycles rather than being a one-off display problem

### 5.3 Reconciliation surface

The slice then translated the discrepancy into one reconciliation-ready balancing surface.

Observed reconciliation facts:
- current authoritative denominator rows:
  - `18,554,942`
- current non-authoritative denominator rows:
  - `37,109,884`
- current balancing adjustment rows:
  - `18,554,942`
- current authoritative-to-control delta:
  - `-0.04 pp`
- current discrepant-to-control delta:
  - `-4.83 pp`

Meaning:
- the authoritative view stays within the trusted control family
- the discrepant view remains materially outside it
- the reconciliation surface therefore makes the release-safe state explicit before recurring use

### 5.4 Release and rerun posture

The control pack then ran a compact release-check layer to prove that the inherited surrounds and new recurring outputs remained safe.

Observed release results:

| Check | Result |
| --- | ---: |
| validation summary covers two recurring cycles | pass |
| single discrepancy class is explicit | pass |
| current-cycle gap remains material | pass |
| prior-cycle gap remains material | pass |
| authoritative view stays within control family | pass |
| trusted provision pack remains green | pass |
| governed output pack remains green | pass |
| recurring-pack language stays control, not payroll estate | pass |

Release verdict:
- `8/8` checks passed

This is enough for the slice because the requirement is not “prove full payroll-process ownership.” It is “validate data, identify discrepancies, support reconciliation, and keep recurring outputs defensible.”

## 6. What Was Actually Added Beyond the Inherited Packs

This slice was not meant to repeat the HUC discrepancy pack, the Claire House trusted pack, or the Money and Pensions Service governance pack. It was meant to convert them into one recurring operational-control proof.

What was inherited directly:
- the bounded discrepancy pattern
- the trusted controlled-output reference family
- the governed output control checks

What was added for Welsh Government `A + D`:
- one explicit validation summary
- one recurring discrepancy findings output
- one reconciliation-ready balancing surface
- one recurring operational-support reading
- one explicit control against fake payroll-estate language

That is the correct widening:
- not another anomaly-only slice
- not another governance-only slice
- not a fake payroll-processing simulation
- but one bounded recurring control pack suitable for validation and reconciliation claims

## 7. Assets Produced

The slice produced the assets that make the validation-and-reconciliation pack credible.

Control assets:
- validation summary
- discrepancy findings output
- reconciliation output

Support assets:
- scope note
- validation-rules note
- discrepancy findings note
- recurring operational-support note
- caveats note
- regeneration README
- changelog

This is the key difference between this slice and a vague “I validate data” claim:
- the output here is not just a statement
- it is one explicit recurring control surface with a defined rule, a defined discrepancy class, and a defined balancing output

## 8. Figures

No figures have been added yet for this slice.

That is intentional at this stage:
- the strongest proof here is the validation summary, the discrepancy findings output, and the reconciliation surface
- a figure would only be useful if it materially clarified the balancing story beyond those compact outputs
- if later review shows that one analytical plot would improve understanding, it can be added then

So the current slice should be treated as:
- validation-and-reconciliation pack first
- figure optional

## 9. What This Slice Supports Claiming

This slice supports truthful statements such as:
- validated recurring operational data against explicit control rules
- identified and quantified material discrepancies before recurring release
- supported reconciliation-ready outputs from a controlled lane
- improved confidence in the integrity of recurring operational outputs

The slice does not support claiming that:
- the whole payroll-processing environment has already been owned
- full statutory payroll compliance has already been proven
- end-to-end payroll operations have already been delivered

## 10. Candidate Resume Claim Surfaces

This section should be read as a direct response to the Welsh Government `A + D` responsibility, not as a generic “I work with operational data” statement.

The requirement asks for someone who can:
- analyse operational or payroll-style data for accuracy
- identify discrepancies and resolve issues
- prepare or support reconciliation reporting
- support recurring operational cycles with reliable outputs

The claim therefore needs to answer back in evidence form:
- I fixed an explicit validation rule for the recurring lane
- I surfaced and quantified the discrepancy class clearly
- I turned the discrepancy into a reconciliation-ready output
- I kept the claim truthful by stopping short of payroll-estate ownership

### 10.1 Flagship `X by Y by Z` claim

> Analysed detailed operational data for accuracy, identified material discrepancies, and supported reconciliation reporting in a recurring control cycle, as measured by fixing `1` explicit validation rule, carrying `1` discrepancy class across `2` recurring cycles, reconciling a current `1,780,031`-row control lane with a `4.80` percentage-point current-cycle gap and `4.81` percentage-point prior-cycle gap, and passing `8/8` release checks in `0.18` seconds, by turning an inherited discrepancy pattern into a controlled balancing surface that kept the authoritative view inside the trusted control family before recurring release.

### 10.2 Shorter recruiter-facing version

> Analysed operational data for accuracy and supported reconciliation reporting, as measured by `1` explicit control rule, `1` recurring discrepancy class, and `8/8` release checks, by turning a bounded discrepancy pattern into a repeatable balancing surface for recurring operational use.

### 10.3 Closer direct-response version

> Analysed detailed operational data for accuracy, identified mismatches, and supported recurring reconciliation work, as measured by one validation summary, one discrepancy findings output, and one reconciliation-ready balancing surface built from controlled evidence, by making recurring operational release safer without claiming ownership of the full payroll-processing function.
