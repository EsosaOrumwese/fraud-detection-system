## Question Variants

For **Are Right, A Lot**, the interviewer is testing judgement under ambiguity.

They are **not** testing whether the graduate’s idea always wins. They are testing whether he can seek input, test assumptions, separate signal from noise, and choose the best answer for the customer/business even if it is not his original preference.

Most likely question variants:

| Likely question                                                                             | What they are testing                           |
| ------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **Tell me about a time you made a good decision with incomplete information.**              | Can you judge under ambiguity?                  |
| **Tell me about a time your first assumption was wrong.**                                   | Can you disconfirm your own belief?             |
| **Tell me about a time you changed your mind after hearing another perspective.**           | Do you seek different views?                    |
| **Tell me about a time you used evidence to make a decision.**                              | Do you separate signal from noise?              |
| **Tell me about a time someone disagreed with you and you still reached the right answer.** | Can you use disagreement productively?          |
| **Tell me about a time you had to choose between two reasonable options.**                  | Can you balance trade-offs?                     |
| **Tell me about a time you did not pick the option with the best metric.**                  | Do you understand context behind data?          |
| **Tell me about a time you asked for another person’s view before acting.**                 | Do you avoid over-trusting your own judgement?  |
| **Tell me about a time you made a decision that balanced performance, risk, and delivery.** | Can you judge the whole system, not one metric? |
| **Tell me about a time you checked your judgement before escalating.**                      | Do you verify before acting?                    |

Most likely for the graduate:

1. **Tell me about a time you had to make a judgement call between two reasonable options.**
2. **Tell me about a time you tested another person’s idea before deciding.**
3. **Tell me about a time you used evidence to decide, not just opinion.**
4. **Tell me about a time the highest metric was not the best decision.**
5. **Tell me about a time you sought another perspective before escalating.**

Best story fit from the saved discussion:

**Main story:** random forest disagreement.
This works because the graduate did not simply reject the more complex model. He gave it a fair test, looked at the metric improvement, weighed that against explainability and delivery risk, and chose the option the team could own by the deadline. 

**Backup story:** oilfield loadout mismatch.
This works when the question is about operational judgement: he noticed a mismatch, checked the tag and job sheet, then asked an experienced colleague to verify before escalating. 

The answer must show:

> **initial view → different perspective/evidence → test/check → trade-off decision → business/team result.**

---

## Interviewer

The interviewer writes:

**committed through alignment work**

Then he looks up.

“That is the part I wanted.”

He points at the notebook.

“You proved you committed because you did the boring work after the decision: aligning the notebook, report, results table, confusion matrix, evaluation wording, and conclusion. That matters more than saying, ‘I accepted the decision.’”

He underlines:

> “I stopped treating it as an argument to win and treated it as a delivery decision to execute.”

“Keep that. That is the centre of the follow-up.”

He pauses.

“Also good: you did not erase your teammate’s contribution. You kept the random forest as a comparison or future-work point. That shows you were not trying to defeat him. You were trying to protect the submission.”

He writes:

**challenge → timebox → decision → align deliverable**

“That is the full Backbone arc.”

Then he closes the page.

“Have Backbone; Disagree and Commit is covered.”

He turns to a new page.

**ARE RIGHT, A LOT**

He looks at the graduate.

“This one is close to Backbone, but it is not the same.”

He writes:

**Backbone:** challenge when something matters.
**Are Right, A Lot:** make good judgements by seeking evidence, perspectives, and disconfirming your own first view.

He taps the second line.

“They are not asking whether you are always right. They are asking whether your judgement improves because you listen, inspect, compare, and adjust.”

He writes three possible stories:

1. **Random forest disagreement**
2. **Oilfield loadout mismatch**
3. **Swing Dance beginner withdrawing**

He looks up.

“The random forest story can work here, but the angle changes. For Backbone, the point was that you challenged. For Are Right, A Lot, the point is that you did not dismiss the stronger model. You allowed it to be tested. You let the evidence decide whether it earned a place.”

He points to the second story.

“The oilfield mismatch can also work because you did not rely only on your own reading. You checked the tag, checked the sheet, then asked an experienced colleague to verify before escalating.”

Then the third.

“The Swing Dance story can work if the question is about changing your approach after observing how someone was receiving feedback. You saw that technically correct correction was not the same as useful correction.”

He looks at the graduate.

“So answer this.”

**For Are Right, A Lot, what is your first-choice story, what is your backup story, and what evidence shows you improved your judgement by checking assumptions or seeking another perspective?**


## Graduate
For **Are Right, A Lot**, my first-choice story would be the **random forest disagreement**.

I would use that because the point was not that I assumed my first view was correct. My first concern was that adding a random forest two days before submission could destabilise the project. But my teammate’s point was valid: it might improve performance and make the work stronger.

So I did not dismiss it. I asked what would have to change if we made it the main model, then suggested a timebox so the idea could prove itself without putting the working submission at risk. We kept the simpler model as the baseline and tested the random forest separately.

The evidence that I improved my judgement by checking assumptions is that we let the result guide the decision. The random forest improved one metric slightly — around two percentage points on F1 — but it also required changes to the results table, evaluation explanation, figures, and team speaking points. With two days left, the improvement was not strong enough to justify making it the centre of the submission.

So the judgement was not “my idea won.” It was: the stronger model had a fair test, the evidence was considered, and the group chose the option that best balanced performance, explainability, and delivery risk.

My backup story would be the **oilfield loadout mismatch**.

That also fits because I did not rely only on my own reading of the tag. I noticed the connection description did not match the job sheet, but before escalating, I wiped the tag, checked the line again, and asked an experienced colleague to verify it with me. When he agreed, we took it to the supervisor, and the correct component was found elsewhere in the yard and swapped before dispatch.

So if the question is about judgement in a team decision, I would use the random forest story. If it is about checking assumptions in an operational setting, I would use the loadout mismatch.


## Interviewer
The interviewer writes:

**fair test, not stubbornness**

Then he looks up.

“Good. This is the right angle for **Are Right, A Lot**.”

He taps the page.

“You are no longer using this story as ‘I disagreed with someone.’ You are using it as ‘I did not trust my first reaction enough to shut the idea down. I gave the other view a fair test.’ That is the principle.”

He writes:

**initial view:** late change is risky
**other view:** stronger model may improve result
**test:** timebox random forest separately
**decision:** slight F1 gain not enough to justify system cost

“That is strong.”

Then he points to the metric.

> “around two percentage points on F1”

“Careful. If you say that, you must be ready.”

He writes three questions:

**Same train/test split?**
**Same evaluation method?**
**Two points against what baseline?**

“If the simpler model had an F1 of 0.72 and the random forest had 0.74, say that. If you do not remember the exact baseline, say ‘a small improvement in F1’ instead of inventing precision. The danger is not the number. The danger is a number you cannot defend.”

He leans forward.

“And if the interviewer is not technical, explain F1 simply.”

He gives the line:

> “It improved one balanced classification metric slightly, but not enough to justify rewriting the project around it two days before submission.”

“That is safer.”

Then he asks the real follow-up.

**If the random forest improved the metric, why didn’t you choose the better-performing model?**

He raises a finger.

“Answer carefully. Do not sound anti-ambition. Your reasoning should be:

* the improvement was small;
* it was measured against the same split/evaluation;
* the model change affected the whole submission, not just performance;
* the group had two days left;
* everyone needed to explain the final model;
* the simpler model was stable, coherent, and defensible;
* the random forest was still included as comparison/future work, so the idea was not ignored.

Now answer it.”

**Why didn’t you choose the random forest if it improved the metric?**


## Graduate
Because the better metric was only one part of the decision.

We tested it on the same train-test split and the same evaluation method, and the random forest gave a small improvement on F1. But it was not a large enough improvement to justify making it the main model two days before submission.

If we changed the main model, we would have had to update more than the code. We would need to change the results table, figures, evaluation wording, limitations, and make sure all four of us could explain why that model was chosen and what the result meant. At that point, the simpler model was already stable, matched the report, and was defensible.

So the question was not only, “Which model has the higher metric?” It was, “Which choice gives the best submission we can actually own by the deadline?”

We did not ignore the random forest. We kept it as a comparison and mentioned it as future work, because it was useful evidence that a more complex model might improve performance with more time. But we did not let a small metric gain destabilise the whole deliverable.

So my judgement was that the better-performing model in isolation was not the better final decision for the group at that stage.


## Interviewer
The interviewer nods.

“That is the correct judgement.”

He writes:

**metric alone ≠ best decision**

Then he looks back up.

“You did not sound anti-ambition. That was important. You accepted that the random forest had value. You accepted that it improved one metric. But you judged the whole deliverable, not just the model score.”

He taps the notebook.

“That is **Are Right, A Lot**. Good judgement is not worshipping the highest number. It is understanding what the number means inside the real situation.”

He reads the graduate’s words back:

> “Which choice gives the best submission we can actually own by the deadline?”

“That is the line. Keep it.”

He pauses.

“Also, good that you said the random forest was kept as comparison or future work. That shows you did not bury evidence that disagreed with your preference. You gave the idea a fair place.”

He writes:

**fair test → evidence → delivery-aware decision**

Then he leans forward.

“One more follow-up.”

**What would you do differently next time so the group does not face that decision two days before submission?**

He raises his hand before the graduate answers.

“Do not say, ‘start earlier.’ That is useless.”

“I want a mechanism. You could say:

* agree model-selection criteria earlier;
* set a deadline for experimental models;
* define what counts as ‘worth switching’ before people get attached to a model;
* keep a stable baseline from the start;
* separate exploration from final-deliverable lock;
* make sure everyone understands the chosen model before report writing begins.

That would show you learned from the decision, not just defended it.”

He waits.

“Answer it.”

**If you ran that group project again, how would you prevent that late-stage model disagreement from happening?**

## Graduate
If I ran that group project again, I would separate **model exploration** from **final deliverable lock** much earlier.

At the start, I would make sure we had a stable baseline model first, so there was always a working version the report could be built around. Then I would agree a cut-off point for experimental models, for example: any new model has to be tested and proposed before the report-writing stage, not two days before submission.

I would also agree the switching criteria before people became attached to a model. For example, a new model would only replace the baseline if it improved the key metric by a meaningful amount, ran cleanly on the same split, and everyone could explain it well enough for the report and presentation. Otherwise, it could still be included as a comparison or future-work point, but not become the main submission.

The other thing I would do is lock the final model before writing the evaluation section properly. In our case, part of the tension came because changing the model meant changing the report, figures, explanation, and team speaking points. If the model is locked earlier, the writing and presentation can be built on stable ground.

So the mechanism would be: baseline first, exploration deadline, agreed switching criteria, then final-model lock before the report is written. That would let us stay ambitious without putting the whole deliverable at risk late in the process.


## Interviewer
The interviewer writes:

**baseline first → exploration deadline → switching criteria → model lock**

Then he looks up.

“Good. That is the improvement.”

He taps the sequence with his pen.

“This is the part that shows maturity. You are not saying, ‘Next time I would argue harder.’ You are designing the process so the argument happens at the right time, with the right criteria.”

He underlines:

> “stay ambitious without putting the whole deliverable at risk late in the process.”

“That is the centre. Keep it.”

He pauses.

“Are Right, A Lot is covered.”

Then he turns to a new page.

**LEARN AND BE CURIOUS**

He looks at the graduate.

“This one is not ‘I like learning.’ It is not ‘I watched tutorials.’ Amazon will test whether you recognised a gap, built a way to close it, and changed how you worked afterward.”

He writes two stories:

1. **MSc ML assignment**
2. **Five Guys prep timing**

“The MSc ML assignment is your first-choice story. It has the right shape. You were in the library, the notebook was failing, you understood pieces but not the whole pipeline, and you stopped watching random tutorials. You built a checklist, made a smaller version, asked for specific help, and learned to locate errors.”

He writes:

**not stronger overnight — moved from panic to diagnosis**

“That is the key.”

He looks at the graduate.

“For Learn and Be Curious, what is your first-choice story, what is your backup story, and what proof shows your learning changed your behaviour afterward?”

## STAR Responses
### Main story: random forest disagreement

> During my MSc, I had a group project where we had to decide whether to change our main model close to the submission deadline.
>
> We were a four-person group, about two days from submission, and we already had a simpler model that ran end-to-end and matched the report. One teammate wanted to introduce a random forest because it gave a small improvement in F1 and could make the work stronger.
>
> My first concern was that changing the model that late could destabilise the project. But I did not dismiss his idea, because his point was valid. A better-performing model could improve the submission if we could explain and support it properly.
>
> So I asked, “What would need to change if we use this as the main model?” That moved the discussion from personal preference to the full impact on the submission: results table, figures, evaluation wording, limitations, and whether all four of us could explain the final output.
>
> We agreed to test it separately while keeping the working model safe as the baseline. The random forest improved one balanced classification metric slightly, but not enough to justify rewriting the centre of the project two days before submission.
>
> The judgement was not “my idea won.” It was that the stronger model had a fair test, the evidence was considered, and the group chose the option that best balanced performance, explainability, and delivery risk.
>
> The result was that we submitted on time with a model the whole group could defend. The random forest was not ignored; we kept it as a comparison and future-work point.
>
> What I learned was that being right is not about holding onto your first view or picking the highest number in isolation. It is about testing assumptions, listening to the other side, and choosing the decision that works best in the full situation.

### Backup story: oilfield loadout mismatch

> In my field engineering role, I had a loadout where I had to check my own judgement before escalating a possible issue.
>
> We were preparing completions equipment in the yard, and one component had been grouped with the job equipment. From where it was placed, it looked like it belonged there. But when I checked the tag against the job sheet, the connection description did not match.
>
> I did not want to assume I was right immediately, because I was still younger in that environment and the team was trying to keep the loadout moving. So I wiped the tag, checked the job sheet line again, compared it back to the physical item, and then asked a more experienced colleague to verify it with me.
>
> When he checked it himself, he agreed that the connection did not match. We escalated it to the supervisor, who paused that section of the loadout and asked the team to find the correct component. The correct item was found elsewhere in the yard and swapped before dispatch.
>
> The result was that the equipment left with the correct component. The pause cost around 20–30 minutes in the yard, but it avoided a likely rig-site delay, rework, extra transport, and client escalation.
>
> What I learned was that good judgement is not just trusting your first read. It is checking the detail, asking the right person to verify when the risk is high, and then acting once the evidence is strong enough.
