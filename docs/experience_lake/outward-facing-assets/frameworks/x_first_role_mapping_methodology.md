# X-First Role Mapping Methodology

This note records the corrected resume-positioning method for mapping job ads to the platform evidence tree.

## Why This Exists

The earlier mapping approach was useful for collecting evidence, but it was too method-led.

It often started from:

> what was built, what tools were used, what lifecycle stages were owned, what models were trained, what pipelines were managed

That created Z-heavy positioning. It proved capability, but it did not always make the employer's problem visible quickly enough.

A recruiter or hiring manager scanning a CV is not first asking:

> Did this person use PySpark, XGBoost, CI/CD, and production pipelines?

They are first asking:

> Can this person solve the problem I am hiring for?

The tools, duties, workflows, and methods matter because they explain how the problem was solved. They should not usually be the lead signal.

## Old Method

The old method tended to collapse the role into:

> Z -> Y -> X

or:

> Z -> X -> Y

Examples of Z-first posture:

> Built an end-to-end ML workflow...

> Used PySpark to process large customer datasets...

> Managed BAU model monitoring...

These are not wrong as evidence, but they start with the candidate's activity. On a fast scan, the reader sees tools and workstreams before they see the business/customer problem solved.

## What Was Wrong

The old approach made three things too easy:

1. Treating platform capabilities as achievements.
2. Treating metrics as proof without clearly stating the business problem they prove.
3. Treating any "by identifying..." phrase as Z, even when it was actually the business mechanism that gave X its context.

This produced bullets that could be technically strong but scan weakly, because the reader had to finish the whole sentence to infer the point.

## Corrected Method

The corrected method is:

> X first, but with X made specific before adding Y and Z.

That means we do not stop at vague X phrases such as:

> solved business problems

> improved customer experience

> generated insights

> improved products, processes, and performance

Those phrases are useful as umbrella positioning, but they are usually too broad for individual bullets.

## Four-Part Construction

For role mapping and bullet design, use four parts:

| Layer | Meaning |
|---|---|
| Concrete X | The specific customer or business outcome. |
| Business mechanism / target signal | The behaviour, condition, segment, timing, issue, or decision point that gives X business context. |
| Y | How well the outcome was solved, measured, qualified, or evidenced. |
| Z | The method, responsibility, tool, workflow, or duty used to create the outcome. |

The business mechanism is the important addition.

It sits between X and Z. It explains what exactly is happening in the business world, but it is not necessarily the final method used by the candidate.

## Distinguishing Business Mechanism From Z

Some phrases look like Z because they use "by".

Example:

> Reduce churn risk among renewal-stage customers by identifying usage drop-off, price sensitivity, service issues, and upgrade intent.

This contains:

| Layer | Content |
|---|---|
| Concrete X | Reduce churn risk among renewal-stage customers. |
| Business mechanism / target signal | Usage drop-off, price sensitivity, service issues, upgrade intent. |
| Y | Churn reduction, retention uplift, response uplift, earlier detection, precision/recall of churn-risk identification. |
| Z | Build a churn or propensity model; combine usage, billing, service, contract, and customer data; engineer behavioural features; validate and deploy scoring outputs. |

The target signals should not be discarded. They make the X specific. But they should not replace the actual Z duties.

## Job-Ad X Hierarchy

Before mapping the platform, build the employer's X hierarchy:

| Level | Purpose |
|---|---|
| Level 0 | Umbrella company problem. |
| Level 1 | Main outcome facets. |
| Level 2 | Job-ad example outcomes. |
| Level 3 | Specific role-context scenarios with business mechanisms / target signals. |

Only after this hierarchy exists should the platform be mapped.

The mapping flow is:

> employer umbrella problem -> employer outcome facet -> employer example outcome -> employer concrete scenario plus business mechanism -> platform equivalent concrete X plus platform mechanism -> Y proof -> Z method

## Bullet Construction Rule

A strong bullet should usually read as:

> specific customer/business problem -> business mechanism or target signal -> measured proof -> method used

Not:

> method used -> metric -> implied business problem

For example:

> Reduced churn risk among renewal-stage customers by 12% by modelling usage drop-off, price sensitivity, service issues, and upgrade intent across usage, billing, service, contract, and customer data.

This is not a final claim for the current platform. It is a structure example.

The structure is:

| Part | Example content |
|---|---|
| Concrete X | Reduced churn risk among renewal-stage customers. |
| Business mechanism / target signal | Usage drop-off, price sensitivity, service issues, upgrade intent. |
| Y | By 12%. |
| Z | By modelling signals across usage, billing, service, contract, and customer data. |

## How This Applies To The Platform Evidence Tree

The platform evidence tree remains the evidence bank. It stores:

- data sources;
- metrics;
- models;
- pipelines;
- monitoring;
- experiments;
- explainability;
- production workflow evidence.

But when writing outward-facing positioning, do not lead with the evidence bank.

First identify the employer's concrete X and business mechanism. Then choose the platform evidence that can credibly map to it.

The platform story should therefore be shaped as:

> employer problem first, platform evidence second

not:

> platform capability first, employer problem inferred later

## Practical Test

Before accepting a bullet, ask:

1. If the reader only sees the first 5 to 8 words, do they see an outcome or just an activity?
2. Is the X specific enough, or is it still a vague phrase such as "improved customer experience"?
3. Does the bullet name the business mechanism or target signal that makes the X real?
4. Is Y proving the outcome, not just decorating the sentence with a number?
5. Is Z drawn from the duties and methods the employer actually asked for?

If the answer is no, the bullet is probably still Z-led or too vague.
