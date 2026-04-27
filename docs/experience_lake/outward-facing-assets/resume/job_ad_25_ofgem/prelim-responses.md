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
- A strong example came from a March 2026 fraud-strategy review where I was asked to assess whether an inherited broad transaction-selection posture was still the right operational choice for the platform, or whether a tighter amount-based posture would give a better balance between control strength and review burden.
- The data volume was not small. I was working across a governed cloud-based analytical environment over millions of transaction-flow records and their linked downstream case activity. In the comparison window, the broader posture selected `4,018,508` flows for review, while the tighter posture selected `3,507,008`. I also had to account for linked downstream case events, where the operational effect of a rule change becomes much more visible than it does at simple selection level.
- The uncertainty was real. The decision makers did not simply want “the rule with the better percentage”. They needed to know whether reducing review volume would still retain enough fraud capture to remain commercially and operationally sensible, or whether the broader posture’s wider net was still worth the extra handling burden.

Task:
- My task was to work through that uncertainty and give a recommendation that was analytically sound, operationally credible, and usable for decision making.
- That meant I had to do more than compare two headline rates. I needed to:
- quantify the effect of each posture on review volume;
- quantify the effect on downstream case-handling burden;
- assess confirmed fraud concentration under each posture;
- make the trade-offs explicit rather than hiding them inside one “better” number;
- present the result in a way that a decision maker could act on.

Action:
- I started by pulling the relevant governed fraud-window data from the shared analytical environment and structuring the comparison so both postures were measured on like-for-like footing. That involved using SQL to shape the comparison base, align the selection populations, and connect them to the downstream case-handling and confirmed-outcome surfaces. I was careful to work in a controlled way because the size of the data meant careless joins would distort the result and create false confidence.
- The analytical skills I used were a combination of large-scale data handling, comparative analysis, validation, and operational interpretation. I was not just counting records. I was asking: what does each posture do to the workload entering review, what does it do to the case activity created afterwards, and how much confirmed fraud is actually concentrated inside the reviewed population?
- I then evaluated the competing options. The broad posture had the advantage of wider capture. The tighter posture had the advantage of being more selective. Rather than present one as automatically right, I framed them as two pragmatic options:
- keep the broader posture if the priority was maximum capture and the business was willing to accept higher review and case-handling burden;
- move to the tighter posture if the priority was a cleaner review population, lower operational burden, and better confirmed-fraud concentration, while accepting some loss of broader capture.
- To make that judgement usable, I translated the technical comparison into operational terms. I did not leave the output as a rule table. I set out what the numbers meant for the people making the decision: how many fewer transactions would enter review, how much downstream case activity would be avoided, what would happen to confirmed fraud yield, and what capture would be given up in exchange.

Result:
- The tighter posture reduced selected review volume by `511,500` flows, from `4,018,508` to `3,507,008`, which was a `12.73%` reduction in review burden.
- It also reduced downstream case-handling activity by `1,185,849` events, a `12.38%` reduction, which mattered because this is where operational cost and analyst effort become much more tangible.
- At the same time, confirmed fraud yield improved from `12.06%` to `12.37%`, and the tighter posture still retained `89.53%` of the positives found by the broader posture.
- That gave decision makers a grounded and pragmatic choice rather than a vague recommendation. The analysis showed that the tighter posture was not “universally better”; it was better if the business wanted a smaller, cleaner, more efficient review population with lower downstream handling burden. The broad posture remained defensible only if the business explicitly preferred wider capture over operational efficiency.
- This is the example I would use to demonstrate the lead criterion because it shows the full chain they are asking for: I worked with a genuinely large dataset, handled uncertainty rather than pretending it away, solved a real operational problem, formulated pragmatic options with explicit trade-offs, and presented actionable information that decision makers could use immediately.

## Q2 - Analytical Input into Public-Interest / Regulatory-Style Work

Question:
- Tell me of a time where you provided analytical input or assurance into work that was regulatory, policy-facing, government-style, consultancy-style, or otherwise aimed at delivering benefits for consumers, communities, or society.

STAR

Situation:
- 

Task:
- 

Action:
- 

Result:
- 

## Q3 - Tools and Insightful Analysis

Question:
- Tell me of a time where you used data-management and manipulation tools such as Excel, Power BI, Python, or similar tools to produce insightful analysis.

STAR

Situation:
- 

Task:
- 

Action:
- 

Result:
- 

## Q4 - Stakeholder Relationships and Open Engagement

Question:
- Tell me of a time where you built effective relationships with internal or external stakeholders and created space for constructive, open, and transparent engagement.

STAR

Situation:
- 

Task:
- 

Action:
- 

Result:
- 

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
