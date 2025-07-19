# Prompt Development for Getting Hole Finder Template

### USER: 

>Before we continue, here's a set of documents to build your context. You'll have to read through it and understand as I  have a series of tough and brutal questions to ask and confirm your understanding and knowledge on the document , how they relate together and how it is written. The only acceptable score is 10/10 or perfect understanding and nothing less.
>
>Documents:\
>full_approach_for_realism_synthetic_data_generator.txt - Contains the global description of what I want to achieve with my synthetic data generator\
>full_narrative_merchant_location-realism.txt - The focus of my work now is on merchant local realism and this breaks the journey segments even more into subsegments in a prose and technical way\
>full_assumptions_merchant_location-realism.txt - lays out the assumptions for each subsegment detailed in the doc above

### ASSISTANT: 
...
 
### USER: 
>Describe each document passed to you and how they relate to each other

### ASSISTANT: 
...

### USER: 
> Read and demonstrate your understanding of document 1

_Repeat for doc 2, doc3_

### USER:
> Okay now behave as a thought clarifier as we begin to form the details of a prompt. It should pull out ambiguity and clarify thoughts so that using the prompt, I can communicate my intent more effectively to the model]

### ASSISTANT:
...

### USER:
```text
### Objective
It should think as a Data Scientist working at JP Morgan with this product to be shipped into production.

As you can see, this narratives and assumptions have been reviewed and form "truth". However, there lies some ambiguity and I would like to be able to, for each subsegment, scan through the it, knowing the context of the whole project in mind and how it relates to the other subsegments, to look for any "missing holes". Now in my description of "missing holes", I'm also being ambiguous so it might not know exactly what it should look for, neither do I, so I need help clarifying that.

 Anyway, my expected output or result, is a fully unambiguous and well detailed, down to the t, technical description, written in the same format as it currently is, such that it fully conveys the idea behind it. Any one (here is another ambiguouity for me now, I don't know what "one" refers to) that isn't meant to be in the narrative but feels more like "an assumptions" artefact should be slated for the assumptions artifact also.

### Inputs:
Just like I did with you, I will pass it the entire narrative and assumptions before hand to build its context on the problem. Then for this specific query, I will pass the associated  narrative and technical assumption for the subsegment

### Depth & Style:
It should respond in the similar manner as the documents it is assessing (The narrative doc is a highly detailed narrative prose and the assumptions, I really don't know). However deep technical detail is of essence. Bullet points are forbidden as the cause the model to summarize which leads to loss of detail.  

### Scope & Constraints.
There are no length limits and to avoid reprinting the whole document again, it should point out the section that is unexplained, ambiguous, glossed over and then suggest a replacement for it. This can be done in what ever way you deem neccessary but the piont is that I want it to be thorough cus if it uses bullet points, it'll tend to reduce it's output size. Instead of cutting short its output, if it feels like its output might be too long, it can split it across multiple outputs if need be. THat will be most preferable than summarizing and introducing further ambiguity causing circularity again. 

It is constrained to the context of the entire narrative and how it plans on achieving it as the narrative has been highly reviewed and passed. It shouldn't come out with "new ideas" to solve something which ends up causing a drift from the specifications. However, it should think like a Data Scientist working as 

Audience:
Technical auditors at JP Morgan will brutally review it for drift, ambiguity and correctness i.e. if it's just impractical rubbish that was said. Another model will also read the output in order to create a clear specifications but that is later on. 

Validation:
I would need it to first call out the ambiguities by citing the section or paragraph and stating why it thinks that is an ambiguity. As to how I will know the model has "nailed it", I don't know. The plan for now is to pass its "resolved" documents to another model to act as the technical auditors as JP Morgan and brutally review it.

### Missing holes definition
I'd say, in my head at the moment, when I say "holes", it refers to a part in the document that I read and when I get there, I'm like "hmm...how did we get here? where exactly did this come from?" It's just something stated but never explain. Remember, I defined the local context (of merchant location realism) as a journey from starting point (having the empty transaction schema) to the end point ( a synthetic data generator with a fully realized and implemented, according to the specifications, merchant-location realism. Ready for the next features i.e. Arrival engine with controlled over-dispersion, Fraud dynamics as coupled Hawkes cascades and Multivariate validation harness.) The narrative process is meant to be a map with journey segments and subsegments, so any no to clear defined path is a "missing hole".

Example, looking at the very first subsegment in "From merchants to physical sites", both the narrative and the assumptions doc refer to "spatial priors" but never detail out how we got here.

Narrative: "...Immediately after start‑up the pipeline reads three artefact bundles that live under git LFS and are tagged by semantic version: hurdle_coefficients.yaml, crossborder_hyperparams.yaml, and the spatial‐prior bundle directory...."
Assumptions: "....The spatial‑prior directory is not consulted in this sub‑segment but its digests are concatenated into the same manifest hash so that any change—to road traffic weights, population rasters or polygon boundaries—would alter the fingerprint that ends up embedded in every catalogue row...."

So the natural question is "where did this spatial prior come from and how do I get?" hence making it a hole. The "missing" in "missing holes" is tautology, sorry. It's just called holes

### “One” in “any one (… )”
Here I was refering to artefacts that feel like they belong in the assumptions doc and not the narrative doc. Using our spatial priors as an example, yes the journey to acquiring it could be expressed more clearly but information about the exact document to get or where the data can be gotten from or the specific datasets that make up the spatial priors are best left in the assumptions doc. This can also apply for mathematical formulas. Yeah, the function or formula could be refered to but what the exact variables are and how we arrived at them are best suited for the assumptions doc.

### Annotation versus replacement
Firstly, I would want it to find ambiguities, then fix it in the following prompt. When it finds ambiguities, it should quote the section and then explain why it thinks that is an ambiguity so that we both know (the model and myself), if its fix actually clarifies things.

### Citation of location
It should just get the exact sentence or in quotes. The same way or something similar that I did with my example on spatial priors

### Granularity of output
We would be handling it subsegment by subsegment. So it's task will be to focus only on the narrative and assumption docs attached as .txt files for that subsegment. Once that's ironed out and after brutal review, we'll move to the next

### Strictness on new ideas
Yes, the model should strictly refrain from suggesting any design changes, even minor tweaks to the design especially to the narrative aspect of the design as that detail out exactly how the system works. For example if the design says "The loader computes a SHA‑256 digest for every file it touches and concatenates those digests—plus the commit hash of the source tree—into a single 256‑bit manifest fingerprint." or "The generator multiplies the design matrix row by the logistic‑regression coefficient vector stored in hurdle_coefficients.yaml, applies the logistic function, and obtains a probability π that this merchant is multi‑site.", it shouldn't go ahead an change the SHA-256 to something else that it thinks is better or to change the operation of the generator into something else.

However, it's freedom is in fully developing how it believes this would best work in a production environment like JP Morgan. This means stating how the loader will achieve that computation to get the manifest fingerprint (also saying what it is) or in the assumptions showing us the function and the variables involved in the proocess between the design matric, the logistic function and probability π  and what these all are)

### Output formating style
Firstly, I said that I would the "holes" and the models reason for ambiguity in the initial prompt and then get the proposed clarifications for all the holes discovered in the next prompt. Please note this. As for how it will be discovered, could you suggest other methods because what I want is since the narrative and the companion doc, assumptions, are connected in some way with the assumptions holding information that's to heavy for the narrative. There might be sometimes where the ambiguity appears in both docs as I stated in the example of spatial priors. So keep that in mind.

### Document reference
Quoting the sentence or phrase itself is sufficient but tagging it with <narrative> or <assumption> so as to know which doc it came from. I don't need the name of the file or subsegment seeing as I'm dealing with one subsegment at a time and only passing two files, the narrative and the assumption

### Assumptions vs. Narrative placement
No need for a "see assumptions" note. Whatever belongs in the assumptions doc, should be placed in the assumptions doc. Like I said above, some holes exist in both documents or in one. As a result, when these holes are found either because of ambiguity, wrongness, or inexistent, these should be reference and in the next prompt their replacement shown. As for how to display this outputs, I still don't know what's best for showcasing updates to a txtfile inorder to avoid excessive reprinting.

### Level of production detail
I want no pseudo-code at all. Code is banned. All I just want I want is richly detailed paragraph which can be inserted into the assumptions (or we could call it a better name like companion) document so as to not overcomplicate the narrative.

I'm happy to answer more questions, so feel free to ask
```

### ASSISTANT:
I have distilled what you want the *assessor model* to do and spotted a few places where your current instructions still leave wiggle‑room. Below I outline each point of residual ambiguity in prose (no bullet symbols) and pose one or two decisive questions so we can lock them down before I craft the final, ready‑to‑copy prompt text.

First, the mechanism for very long outputs. You allow the assessor to “split across multiple outputs if need be”. Would you prefer a hard limit stated in characters or tokens after which it must break and send a continuation marker such as “⟨CONTINUE⟩”, or should it decide autonomously and simply chain replies until it reaches the end of its material?

Second, the quoting style for holes. You ask that every ambiguous passage be reproduced verbatim, wrapped in quotation marks and prefixed with either <narrative> or <assumption>. Do you want the assessor to include surrounding context lines for orientation, or should it reproduce only the minimal sentence or clause that triggers the doubt? A strict single‑sentence quote keeps things tight but may force you to look back at the originals too often.

Third, replacement text format in the follow‑up round. Once you approve the list of holes, the assessor will write replacement prose for each one. Do you want those replacements bundled into a single continuous block that is ready to paste into the assumptions document, or would you rather receive a labelled pair for every hole, for example: original quote, then immediately the suggested rewrite, before moving on to the next?

Fourth, signalling the end of processing for a sub‑segment. Should the assessor conclude with an explicit footer such as “⟨END OF SUBSEGMENT X ANALYSIS⟩” so the next stage in your pipeline can detect completion automatically?

Fifth, handling duplicated holes that appear in both documents. If the same conceptual gap is reflected in narrative and assumptions sentences, do you want it reported once with two citations, or reported twice under each source?

Sixth, prohibition of new design ideas is clear, but consider whether the assessor may offer *implementation context* that the narrative already implies yet never spells out. For example, it might emit a short explanatory aside like “the loader performs the digest computation during the same Spark job that writes the Parquet catalogue”. Strictly speaking that is not a design change, but it is additional colour—do you want to allow that, provided it does not clash with the approved architecture?

Seventh, you ban code and bullet points. Are numbered headings acceptable if they are rendered as plain paragraphs that begin with “First,” “Second,” etc.? In long technical rewrites, internal section numbering can keep auditors oriented while still avoiding bullet formatting.

Eighth, in the validation criterion you currently rely on a later auditing model to judge whether the assessor has “nailed it”. Would you like the assessor to append its own internal confidence estimate per hole, for instance a short note like “(high confidence this is ambiguous because …)”? That might give the auditors a starting sense of prioritisation.

Once these eight items are nailed down I can compose the definitive prompt in continuous prose, mirroring the tone of your documents, ready for you to paste into the session that will drive the assessor model. Let me know your decisions on each and I will produce the final wording immediately afterward.

### USER:
```text
## 1. Mechanism for very long outputs:
I thinking your idea on a hard limit is good. You can suggest one  that allows for a reasonable length or output.

##  2. Quoting style for holes
Yes, you can include some surrounding context lines for orientation. Now for holes that are inexistent i.e. information not included in the document and as a result cause ambiguity, their surrounding context lines can be shown with a note or marker showing where the replacement text should be placed

## 3. replacement text format in the follow‑up round
I would prefer a set of labelled pairs but the replacement text being a prose for the narrative doc or a prose or mathematical formula and definition  or description for the assumption doc

## 4. signalling the end of processing for a sub‑segment
Yes, that is preferable as it would help me realize when the analysis is complete.

## 5. handling duplicated holes that appear in both documents
I would want it reported once with two citations and a replacement for both

## 6. prohibition of new design ideas
Yes, your suggestion is allowed, it is not a design change but an additional colour. Such clarification of implementation context is highly encouraged.

## 7. Seventh, you ban code and bullet points
Yes, your suggestion is approved.

## 8. validation criterion you currently rely on a later auditing model
Yes, this suggestion is approved


Feel free to ask more questions
```

### ASSISTANT
```text
Below is the fully specified prompt you can present to the *assessor model*.
It encodes every rule we agreed on, in continuous prose without bullets or code.
Copy it verbatim (or tweak wording if you like) when you launch the assessment of any narrative + assumptions pair.

---

**Prompt for the assessor model**

You are a senior Data Scientist at JP Morgan reviewing a pair of artefacts―a narrative prose file and its companion assumptions file―that together describe one sub‑segment of our merchant‑location‑realism pipeline. These documents have already been accepted as architectural “truth”. Your sole job in this round is to scour them for gaps, ambiguities, or leaps of logic (“holes”) without suggesting any design changes. Think of a hole as any place where a diligent engineer stops and wonders “how did we get here?” or “what concrete artefact or calculation produces this statement?”

Read both files in full, keeping the global project context in mind but limiting yourself strictly to the current sub‑segment. For every hole you detect:

• Quote the exact sentence or clause that contains or illustrates the ambiguity. Pre‑pend **`<narrative>`** or **`<assumption>`** to show which document you are quoting.
• Provide two or three surrounding sentences of context from the same document so the reader can see where the gap sits.
• If the hole concerns information that is entirely absent (for example a missing derivation of the spatial‑prior bundle) reproduce the nearest surrounding lines and insert the marker **`[MISSING HERE]`** where the absent material should slot in.
• After the quote and its context, explain in continuous prose why this passage is ambiguous, incomplete, glossed‑over, or misplaced.
• If the same conceptual hole appears in both documents, report it once, but cite both sources in your explanation.
• Append a short parenthetical confidence note such as “(high confidence this is ambiguous because …)” so later auditors can triage.

Write your analysis as flowing paragraphs. You may begin sentences with “First,” “Second,” and so on for navigation, but use no bullet symbols, no enumerated lists, no code blocks, and no pseudocode. You may add implementation colour that clarifies an already‑accepted design, yet you must not propose new algorithms, new data sources, or alternative digests.

When the length of your response for this sub‑segment approaches about fifteen‑thousand characters, terminate the current message with the exact token **`⟨CONTINUE⟩`** (all caps, angle brackets). Resume in a fresh message that starts with **`⟨CONTINUATION⟩`** and carry on until every hole has been catalogued. This split is only to satisfy delivery constraints; do not shorten or summarise your content.

When you have exhausted the documents and found no further holes, close with the explicit footer **`⟨END OF SUBSEGMENT ANALYSIS⟩`** on its own line.

Do not draft replacement text yet. That will come in the next prompt once the hole list is approved.

---

That text is now ready for production use. Let me know if you spot anything else that needs tightening before we move on.
```

### USER
>Lol, for your response you are not constraint to write in a prose format as that may not allow you to provide the best prompt template for me. You are free to use whatever style you wish

### ASSISTANT
_first try at a prompt gen_

### USER
>Brutally review this prompt template as though you aren't the one who wrote it. Is there any ambiguity that will result in the model not responding as expected? Is there any detail left or something not properly specified

### ASSISTANT
_review released_

### USER
>Alright, provide a solid template that will get a 10/10 brutal review score

### ASSISTANT
Details in `docs/prompt_engr/prompts/hole_finder_for_narrative_and_assumptions.md`

### USER
>What about the prompt template for the fixes or does this include it as well?

### ASSISTANT
_first try at a prompt gen_

### USER
>Brutally review this prompt template as though you aren't the one who wrote it. Is there any ambiguity that will result in the model not responding as expected? Is there any detail left or something not properly specified

### ASSISTANT
_review released_

### USER
>Alright, provide a solid template that will get a 10/10 brutal review score

### ASSISTANT
Details in `docs/prompt_engr/prompts/hole_f_for_narrative_and_assumptions.md`

-----
## Creation of v3 -> emphasis on what a hole is and reduction of headers and footers to focus on content

### USER
>Remember to assume the role of a thought clarifier again:
>
>I just ran this hole fixer prompt and I believe does absolute rubbish. The hole finder is spending but I think introducing another detailed prompt for fixing (given that we have already provided lots of details and contraints in the hole finder, just messes it up and cause the explanation to be subpar. 
>
>Firstly, due to the format, so much space is wasted on structure that it just replaces the sentence with another weak sentence. And in all honesty, I think this who fixing and replacing of individual sentences just doesn't work out.
>
>Secondly, it's interesting that the hole which I saw during my review of the first subsegment i.e. the spatial priors hole, never got picked up as a hole. It appears that maybe my definition of hole didn't cover that kind because although the hole finder did a good job in finding actual problems in that narrative and assumption, because the definition of "holes" didn't include unclear concepts or ideas for example "where did the spatial priors come from and what is it, it never got picked up. So I think great effort should be spent in defining the holes as that is what we're interested in finding.
>
>Every other thing about the hole finder is good but let it also include Low-High holes so I can choose what is worth chasing.
>
>As for the fixing of these holes, instead of fixing sentence by sentence, I would suggest an entire rewrite of the narrative first to fix the holes and then the assumptions to fix the holes. Priority should be placed on detail and not trying to shorten the length. We can still use our markers again. When rewrite, the narrative and technical assumption, it's important to keep the style of both documents (you can analyze my narrative and assumptions doc to find out what style is that). And also when rewriting, it can leave sections that are good as is and only expand on ideas that it needs to expand on, include what needs including or carry out the fixes

### ASSISTANT
```markdown
Got it—you want to tighten *what* the Hole‑Finder flags and overhaul *how* fixes are delivered. Here’s what I’m hearing, plus the questions that will let us pin the new spec down precisely.

---

### 1  •  Broaden the definition of a “hole”

Right now the spec focuses on obvious breaks in logic or missing artefacts. You need it to *also* catch fuzzy or undefined concepts (e.g. “spatial priors” appear but their origin is never explained).
**Proposed tweak** A hole is any passage that forces a reader to ask “what/why/how?” about *either* (a) provenance of an artefact **or** (b) the meaning of a concept.
**Question 1** Do you want the Hole‑Finder to flag *every* vague term (“log‑normal residual”, “Hough transform”, etc.), or only those that lack even a one‑sentence working definition inside the two docs?

### 2  •  Severity tagging

You’d like a Low ⇄ High slider so you can decide which gaps to chase.
**Proposed scheme** 
• Critical = breaks reproducibility or contradicts design.
• High  = undefined artefact or concept that downstream code must reference (e.g. spatial priors).
• Medium = could be inferred but still under‑specified.
• Low  = stylistic or clarity nits.
**Question 2** Is a four‑tier scale enough, or do you want numeric 1‑5?

### 3  •  Whole‑document rewrites instead of line fixes

Sentence‑level patches are yielding tepid prose and waste space. You prefer a guided rewrite that **leaves good sections untouched** and **expands** ambiguous ones in‑place.
**Proposed fix workflow**

1. Hole‑Finder emits the tagged list (incl. severity).
2. Hole‑Fixer returns two **complete** replacement files—one for narrative, one for assumptions—each in its native style.
    • Sections that required no change are copied verbatim.
    • Revised or expanded sections are inserted inline.
    • Use clear markers like
     `<<<FIXED‑NARRATIVE‑START (id=12)>>> … <<<FIXED‑NARRATIVE‑END>>>`
     so diff/merge is deterministic.
   **Question 3a** Do you want both replacements in a **single** message or two messages (one per doc)?
   **Question 3b** Do you prefer explicit change markers as above, or a clean rewrite with a separate diff report?

### 4  •  Structural overhead

You feel the earlier templates burned too many tokens on scaffolding.
**Proposed trim** We can collapse the Hole‑Report header/footer to a simple delimiter (`--- HOLE 12 --- …`) and drop redundant field labels.
**Question 4** Is token economy still a pressing issue now that we will be rewriting whole sections anyway?

### 5  •  Style preservation

You asked the model to “analyze my narrative and assumptions doc to find out what style that is.”
**Proposed guard‑rail** Add an explicit instruction: *“Mimic the sentence length, tense, and lexical density of the original document; do not simplify technical jargon.”*
**Question 5** Should we require the Fixer to run a quick self‑check: e.g. average sentence length must stay within ±10 % of the original?

### 6  •  Handoff format for rewritten docs

If we swap entire files, auditors need an easy import path.
**Option A** Inline code‑fence with the full text.
**Option B** Ask the Fixer to attach two `.txt` files (requires tooling support).
**Question 6** Which option fits your pipeline?

---

Answer these six questions (short bullet replies are fine), and I’ll draft the streamlined Hole‑Finder + rewritten‑file Fixer templates that should finally pass a brutal JP Morgan audit.
```

### USER
>1 Broaden the definition of a “hole”
>Yes, I agree with your proposed tweak but I hope that won't be the only definition of a hole. With regards to your question, I do not want the hole finder to flag "every" vague term in the narrative.txt like the ones you mentioned unless it's use within the narrative isn't detailed. However, I would expect for those vague terms to be fully defined within the assumptions and their variables also detailed. It's interesting that you mentioned these vague terms as this is most times where the ambiguity lies. So just pay attention to the narrative around it, if it's rushed, then we need to slow things down and define it more.
>
>2 Severity tagging
>A four-tier scale is enough with low, medium, high, critical. We can focus on Medium to Critical. However, I would want an honest and brutal review and classification of these holes as I don't have that much tokens for a back and forth.
>
>3 Whole‑document rewrites instead of line fixes
>Question3a: If I say I want it in separate messages i.e. one per doc, that implies I'm limiting it to 1 message for doc. However, what I want is for it to expand in detail every ambiguity per doc and if it exceeds one output, it can flow to the next.
>Question3b: I believe a marker is better as it'll help me know what to look out for.
>
>4 Structural overhead
>When I refer to token economy, it's not like I want to reduce the amount of tokens I use, no. Instead I want to maximize the tokens available. Having a structure with bullet points and so many headers and footers like in the hole fixer, just increase the length of the doc and forces the model to summarize the text so as to not appear to long. When in reality its all empty spaces that filled it up. I also refered to token economy in "2 Severity tagging" and that was because having a weak hole finder and/or fixer will result in me running it over and over again to find and fix the hole. Resulting in waste of tokens
>
>5 Style preservation
>No, I asked YOU to analyze my narrative and assumptions doc to find out what style was used there so that the fixes can follow also. I can't fully describe the style of the doc apart from the narrative which I know is a technical prose in narrative format where details are encouraged and summaries/bullet points/code forbidden unless necessary.
>
>6 Handoff format for rewritten docs
>I don't get this. I'm using this prompt withing chatGPT in their o3 model. The text files will be the ones reviewed by the hole finder

### ASSISTANT
_refer to now updated `docs/prompt_engr/model_spec/data-gen/prompts/hole_finder_finder_for_narrative_and_assumptions.md`_