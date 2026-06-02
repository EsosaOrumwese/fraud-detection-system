## Interviewer

The interviewer nods.

“Good. That answer works.”

He writes:

**learning proved by changed default method**

Then he looks back at the graduate.

“You did not rely on the assignment result alone. You showed that your behaviour changed afterward. That is what I wanted.”

He reads the evidence back:

“Before: stuck meant tutorial-hunting.
After: stuck meant mapping the stages, adding checks, testing smaller versions, and locating the failure point.”

He underlines:

> “errors became local rather than overwhelming”

“That is a useful phrase. It shows the learning became practical.”

Then he taps the page.

“This is the key distinction for Learn and Be Curious:”

> “I did not just finish one assignment. I changed how I approached later technical work.”

“Keep that. Do not spend too long explaining machine learning. The interviewer does not need every technical detail. They need to see self-awareness, learning method, and changed behaviour.”

He closes the page.

“Learn and Be Curious is covered.”

Then he turns to a new page.

**FRUGALITY**

He does not say the word like “cheapness.” He says it like a constraint.

“Frugality is not about refusing to spend money. It is about making progress when you do not have ideal resources.”

He writes:

**limited laptop / dataset sample**

“This is your first-choice story here. You had a classification project, a dataset that was too heavy for your laptop to handle smoothly, no paid cloud compute, and a deadline. Your first method wasted time: full runs just to discover basic mistakes.”

He writes another line:

**full dataset = final proof stage, not debugging ground**

“That is the centre.”

He looks up.

“Your backup could be the Swing Dance taster, because the society had limited people, limited time, and no big crowd at the start. But for Frugality, the laptop story is cleaner.”

He pauses.

“Now answer the coverage question.”

**For Frugality, what is your first-choice story, what is your backup story, and what proof shows you made progress despite limited resources rather than simply accepting a lower standard?**


## Graduate
For **Frugality**, my first-choice story would be the **limited laptop / dataset sample** story.

I would use that because the constraint was clear: I had an MSc classification project, the dataset was heavy enough that full notebook runs were slow on my laptop, I did not have a more powerful setup available, and I still had a coursework deadline. At first, I was wasting the resource I did have — time — because I kept running the full dataset just to discover basic pipeline mistakes.

The proof that I made progress despite the constraint is that I did not lower the standard of the final work. I changed the workflow. I created a smaller representative sample that still kept the target, key numerical and categorical columns, missing values, and both outcomes. The point was not to make the problem easy; it was to build a faster test version that still contained the messy parts.

That sample exposed a real issue: after categorical encoding, the training and test data were not ending up with the same feature columns. I fixed that on the sample, added checks, restarted the notebook environment to prove it ran cleanly, and then returned to the full dataset once the route was stable.

The result was that the full dataset became the final proof stage, not the place where I debugged every small mistake. I submitted on time with an end-to-end pipeline I could explain, and I produced the final metrics needed for the write-up. So the standard stayed the same: the final result still had to run on the full dataset. I just stopped using the most expensive path for every small error.

My backup story would be the **Swing Dance taster**.

That one works if the question is about limited people and limited time rather than technical resources. We had a small society, a short room slot, and not enough natural momentum in the room. Instead of waiting for a big crowd or a perfect setup, I used what we had: two stronger dancers, one person at the door, music, and a simple beginner step. That made the room active enough for beginners to join.

But for a direct Frugality question, I would lead with the laptop story because the constraint, workaround, and result are clearest.


## Interviewer
The interviewer nods.

“Good. This is the right first-choice story for Frugality.”

He writes:

**constraint: laptop + time**
**waste: full runs for basic mistakes**
**solution: smaller representative test route**
**standard: final run still on full dataset**

Then he looks up.

“That last part is important. You did not reduce the standard. You reduced the waste in how you got there.”

He taps the line:

> “The point was not to make the problem easy; it was to build a faster test version that still contained the messy parts.”

“Keep that. That is the defence against the obvious follow-up.”

He glances at the Swing Dance backup.

“The taster can work as a backup, but it is softer. It is more Bias for Action or leadership without authority than pure Frugality. Keep it as a backup only if the question is about limited people, limited time, or limited setup.”

He turns back to the laptop story.

“Now the follow-up.”

He speaks as the interviewer again:

**How did you make sure the smaller sample did not hide the real problem or lower the quality of the final work?**

He raises his hand.

“I want you to answer with proof. Do not say, ‘I made sure it was representative.’ That is too vague.”

“I want to hear:

* same target column;
* same key numerical and categorical columns;
* missing values still present;
* both outcomes preserved;
* checked target distribution with value counts;
* sample still exposed the categorical encoding problem;
* final submitted results were produced on the full dataset, not only the sample.

That is the answer.”

He waits.

“Go.”


## Graduate
I made sure the sample did not hide the real problem by checking that it still carried the same structure and mess as the full dataset.

I kept the same target column, the key numerical columns, and the key categorical columns. I also made sure missing values were still present, because if the sample removed the messy rows, it would only give me false confidence.

I checked the target distribution with value counts before and after sampling. I wanted both outcomes represented, not a sample where one class almost disappeared and made the pipeline easier than the real problem.

The best proof was that the sample still broke in a meaningful way. It exposed the categorical encoding issue: the training and test data were not ending up with the same feature columns. So it was not just a convenient small file. It was still realistic enough to reveal the same type of problem I needed to fix.

And I did not submit results from the sample. The sample was my test route. Once the pipeline worked there, I went back to the full dataset and ran the final process section by section. The metrics I used in the write-up came from the full dataset run, not from the sample. So the sample reduced wasted debugging time, but the final quality standard stayed attached to the full data.


## Interviewer
The interviewer nods.

“That answer works.”

He writes:

**sample = test route, not final evidence**

Then he looks up.

“That is the right defence. You did not say, ‘I used a smaller sample and hoped.’ You proved the sample still carried the real problem.”

He reads the proof back:

* same target;
* key numerical and categorical columns;
* missing values still present;
* both outcomes checked with value counts;
* sample still exposed the categorical encoding issue;
* final write-up used metrics from the full dataset, not the sample.

“That is Frugality. You did not lower the bar. You reduced wasted effort.”

He underlines:

> “The sample reduced wasted debugging time, but the final quality standard stayed attached to the full data.”

“Keep that. It is the whole story.”

Then he closes the page.

“Frugality is covered.”

He turns to a new page and writes:

**STRIVE TO BE EARTH’S BEST EMPLOYER / INCLUSION / TEAM CULTURE**

He looks at the graduate.

“This one is not usually asked with that exact title. They may ask: tell me about a time you supported someone, adapted your communication, helped someone feel included, or worked with different experience levels.”

He writes:

**Swing Dance beginner withdrawing**
**Newer crew member bagging**

“The Swing Dance story is your better inclusion/adapting communication story. The newer crew member is your better work-based coaching story.”

He looks up.

“For this principle, I want the answer to avoid corporate diversity language. The story is not ‘I value inclusion.’ The story is that someone was physically in the room but starting to withdraw because the way help was being given did not match her confidence level.”

He writes:

**same correction — different impact**

Then he asks:

**For inclusion/adapting communication/team culture, what is your first-choice story, what is your backup story, and what proof shows your action helped someone stay engaged rather than just made you sound supportive?**
