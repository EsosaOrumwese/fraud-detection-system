# Prelim Responses - Analyst - OFGEM

Purpose:
- build evidence for the supporting statement before drafting the final 1250-word response
- keep the lead criterion strongest
- work criterion by criterion using grounded examples

Role criteria structure:

1. Essential - Lead criterion
- Good analytical skills, including proficiency in working with large volumes of data, and the ability to use data analytical skills to work with uncertainty and solve problems, formulate pragmatic options, and present actionable information to decision makers.

2. Essential
- Experience of providing data analytical input or assurance into consultancy, government, policy, regulatory or energy sector projects that deliver benefits for consumers, communities, or society.

3. Essential
- Effective in the use of data management and manipulation tools to produce insightful analysis, including proficiency in some or all of Excel, Power BI and Python/R.

4. Essential
- Ability to build effective relationships with internal and external stakeholders that creates space for constructive, open, and transparent engagement.

5. Essential
- Good written and verbal communication skills that effectively communicate analysis insights to non-expert audiences.

6. Desirable
- Good sector knowledge, including commercial understanding of the energy sector and/or consumer related issues.

Notes:
- Behaviours should be evidenced through the criterion examples, not treated as separate standalone answers unless required later.
- Main behaviours to embed: Seeing the Big Picture, Making Effective Decisions, Working Together, Delivering at Pace.
- Primary evidence posture: regulated-style analytics, consumer-impact framing, decision support under uncertainty, and clear non-expert communication.

## Q1 - Lead Criterion

Question:
- Tell me of a time where you demonstrated good analytical skills while working with large volumes of data, used analysis to work through uncertainty, solved a problem, formulated pragmatic options, and presented actionable information to decision makers.

STAR

Situation:
- In March 2026, a fraud-strategy review had to answer a more difficult question than “which rule has the better rate”. A broad inherited posture was pushing a very large review population through the workflow, but it was no longer obvious that the extra burden was justified by the value being captured.
- The comparison sat over millions of governed records. Within the review window, the broad posture selected `4,018,508` flows while a tighter amount-based alternative selected `3,507,008`. The true effect could not be judged at selection level alone because the consequence of the rule only became clear once those flows were followed into downstream case activity and confirmed outcomes.
- The uncertainty sat in the trade-off. A broader posture might still be worth it if the extra capture justified the workload. A tighter posture might be better if it removed enough burden without giving up too much confirmed value.

Task:
- The work needed to move beyond a headline comparison and produce a decision basis that was operationally usable.
- That meant quantifying review burden, downstream case burden, confirmed fraud concentration, and retained capture together, then reducing that into options that were pragmatic rather than absolute.

Action:
- SQL was used to build a controlled comparison base so both postures were measured on like-for-like footing across the governed data world. Careful shaping mattered because at this scale careless joins would distort burden, inflate outputs, and make the comparison unreliable.
- The analysis followed each posture through the full operating chain: flows entering review, case activity created downstream, and confirmed fraud concentration inside the reviewed population. That was the only way to answer the real question, which was not “which percentage is bigger?” but “which posture is more sensible once operational cost and retained value are considered together?”
- Two pragmatic options then emerged. One kept the broader posture on the logic of wider capture. The other moved to the tighter posture on the logic of lower burden and cleaner concentration. The comparison was written in operating terms rather than rule shorthand: fewer reviewed flows, fewer downstream case events, improved confirmed-fraud yield, and a clear statement of what retained capture would be given up in exchange.

Result:
- The tighter posture reduced selected review volume by `511,500` flows, from `4,018,508` to `3,507,008`, which was a `12.73%` reduction in review burden.
- It also reduced downstream case-handling activity by `1,185,849` events, a `12.38%` reduction, which mattered because this is where operational cost and analyst effort become much more tangible.
- At the same time, confirmed fraud yield improved from `12.06%` to `12.37%`, and the tighter posture still retained `89.53%` of the positives found by the broader posture.
- The result was a grounded choice rather than a vague recommendation. The tighter posture made sense where the priority was lower review burden, lower case-handling activity, and cleaner confirmed-fraud concentration. The broader posture only remained defensible where the priority was explicitly maximum capture despite the heavier operational cost.
- The uncertainty was reduced to a usable decision basis instead of being hidden behind one flattering number.

## Q2 - Analytical Input into Public-Interest / Regulatory-Style Work

Question:
- Tell me of a time where you provided analytical input or assurance into work that was regulatory, policy-facing, government-style, consultancy-style, or otherwise aimed at delivering benefits for consumers, communities, or society.

STAR

Situation:
- The closest honest analogue to regulatory or public-interest analytical input came from work where the output had to balance protection, proportionality, and operational burden rather than simply improve an internal metric.
- In the March 2026 strategy review, the issue was whether a broad fraud-selection posture was creating unnecessary intervention and downstream workload relative to the confirmed value it was returning. That mattered beyond internal efficiency because too much avoidable review harms customer experience, weakens prioritisation, and consumes effort that should be used where the control is most effective.

Task:
- The analytical task was to support a proportionate control decision rather than a narrow technical comparison.
- That required a view of balance: what burden was being created, what value was being retained, and whether the resulting posture remained sensible.

Action:
- The work was structured as an assurance-style comparison between a broader inherited posture and a tighter alternative. Review volume, downstream case burden, and confirmed fraud concentration were all compared together so the decision would not be driven by one flattering metric.
- The comparison was then interpreted in terms of consequence. The important questions were whether too many legitimate or low-value cases were being pulled into review, whether analyst effort was being consumed on weak-return activity, and whether the posture remained proportionate rather than simply broad.
- The final comparison was framed as a balance question: wider capture versus lower burden and cleaner concentration, not “more” versus “less” in the abstract.

Result:
- The tighter posture reduced selected review volume by `511,500` flows and reduced downstream case-handling activity by `1,185,849` events, while improving confirmed fraud yield from `12.06%` to `12.37%` and still retaining `89.53%` of the positives found by the broader posture.
- The value of the analysis was that it showed a more proportionate route: lower avoidable review burden, better use of analyst effort, and a more focused control population while still retaining most of the broader posture’s positives.
- It is not a direct government or energy-sector example, but it is a defensible example of analytical input built around proportionate decision making and benefits that matter to customers and the wider operating environment, not just the analyst.

## Q3 - Tools and Insightful Analysis

Question:
- Tell me of a time where you used data-management and manipulation tools such as Excel, Power BI, Python, or similar tools to produce insightful analysis.

STAR

Situation:
- A useful example came from work that needed to do three things at once: analyse a large governed dataset properly, check that the conclusions were sound, and present the result in forms that could be revisited and used rather than manually rebuilt each time.
- The underlying demand was to show where workload was building, how quality and output concentration were shifting, and whether the current review posture was creating unnecessary downstream burden. No single tool was a good fit for all of that.

Task:
- The task was to move from governed raw data to a checked analytical comparison and then into a reusable monitoring form.
- That meant using Python, Excel, and Power BI where each tool carried a different part of the work.

Action:
- Python handled the deeper analytical work: structuring the comparison logic, checking performance distributions, testing burden differences between alternative postures, and validating that the summaries were internally coherent.
- Excel handled controlled review and structured comparison. Once the outputs were stable, it gave a quick way to inspect movement, posture differences, and operational trade-offs without losing clarity.
- Power BI handled repeatable monitoring. Dashboard and KPI views were built so workload, throughput, quality, and exception movement became directly visible inside the governed reporting layer rather than something that had to be rebuilt as a one-off extract.
- The tool chain mattered because each tool did a different job instead of being named after the fact.

Result:
- The result was not just a finished analysis, but a usable analytical chain: deeper comparison in Python, controlled review in Excel, and repeatable monitoring in Power BI.
- In one strategy comparison, that tool chain helped surface a tighter posture that reduced selected review volume by `511,500` flows and downstream case-handling activity by `1,185,849` events while improving confirmed fraud yield from `12.06%` to `12.37%`.
- More importantly, it showed the tools being used for what they were actually good at.

## Q4 - Stakeholder Relationships and Open Engagement

Question:
- Tell me of a time where you built effective relationships with internal or external stakeholders and created space for constructive, open, and transparent engagement.

STAR

Situation:
- The strongest honest analogue for this criterion comes from analytical work that had to satisfy a live operating demand around performance understanding, workload movement, and the effect of control changes.
- A reporting and review cycle exposed a familiar problem: if the output arrived as a finished number with no visible reasoning, it would not create useful engagement. The operating need was not just an answer. It was an answer that could be examined, challenged, and still used.

Task:
- The task was to shape the analysis so that challenge would improve it rather than break it.
- That meant the output had to show what it was saying, what it was not saying, and where the real trade-offs sat.

Action:
- Assumptions were stated rather than hidden. Where a figure depended on a particular rule definition, reporting cut, or analytical boundary, that dependence was made visible.
- Challenge was built into the shape of the output. Instead of forcing everything into one headline number, the analysis separated review volume, downstream case burden, confirmed fraud concentration, and retained positives so the underlying concerns could be examined one by one.
- The effect of that structure was that the output did not need to be accepted on trust alone. It showed enough of its reasoning that disagreement could stay constructive.

Result:
- The output became something that could be engaged with openly rather than something that simply asserted a conclusion. The trade-offs were visible, the limits were clearer, and the decision basis was more transparent.
- That is the most defensible way to carry this criterion from the platform: not through exaggerated claims about stakeholder management, but through work shaped so open challenge and transparent engagement were possible.

## Q5 - Written and Verbal Communication to Non-Experts

Question:
- Tell me of a time where you communicated analytical insight clearly in writing and verbally to non-expert audiences.

STAR

Situation:
- 

Task:
- 

Action:
- 

Result:
- 

## Q6 - Desirable Sector Knowledge

Question:
- What is your closest relevant sector or consumer-impact understanding for this role, and how would you frame it honestly as relevant to OFGEM?

STAR

Situation:
- 

Task:
- 

Action:
- 

Result:
- 
