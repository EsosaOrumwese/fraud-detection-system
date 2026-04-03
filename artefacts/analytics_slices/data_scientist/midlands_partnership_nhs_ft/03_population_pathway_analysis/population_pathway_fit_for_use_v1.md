# Population Pathway Fit-for-Use v1

Purpose:
- record the key checks that justify using the bounded linked slice for population, cohort, and pathway analysis

Bounded source profile:
- event rows: `6,911,226`
- event distinct flows: `3,455,613`
- case distinct flows: `361,504`
- case distinct cases: `361,504`

Link and alignment checks:
- event flows with anchor: `3,455,613`
- event flows with truth: `3,455,613`
- event flows with bank-view: `3,455,613`
- event flows with case: `361,504`
- case flows with truth: `361,504`
- case flows with bank-view: `361,504`
- exact event-to-case-open timestamp matches: `361,504`
- average seconds from first event to `CASE_OPENED`: `0`
- flows with multiple cases: `0`

Analytical base checks:
- base rows: `3,455,613`
- base distinct flow IDs: `3,455,613`
- duplicate flow rows in base: `0`
- null flow IDs in base: `0`
- null case-selection flags in base: `0`
- case-selected flows: `361,504`
- case-selected flows missing case ID: `0`

Downstream-output checks:
- cohort rows: `12`
- cohort distinct labels: `4`
- pathway-reporting rows: `15`
- KPI rows: `3`

Interpretation:
- the bounded linked slice is fit for population-pathway analysis
- the main trust question was whether the event surface and case surface could be tied together without ambiguity
- that risk did not materialise in the bounded slice
