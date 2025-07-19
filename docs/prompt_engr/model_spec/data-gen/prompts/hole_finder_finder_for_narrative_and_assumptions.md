Below is a pair of *lean* yet fully‑specified templates that reflect every preference you just confirmed.
They keep scaffolding to an absolute minimum, broaden the hole definition, tag severity, and move from sentence‑patches to whole‑document rewrites with clear inline markers.

---

## ➊  HOLE‑FINDER TEMPLATE  (v 3)

```
##################################
#  HOLE‑FINDER • Sub‑segment {{NAME}}
##################################

ROLE  
You are a senior JP Morgan Data Scientist reviewing two artefacts—Narrative.txt and Assumptions.txt—for this sub‑segment.

WHAT COUNTS AS A HOLE  
Flag anything that forces a reader to ask “what/why/how?” about:  
• provenance or whereabouts of an artefact,  
• meaning or derivation of a concept or variable,  
• logic that skips steps or contradicts earlier context.  
A vague term in the Narrative **is a hole** only if its meaning is not made explicit anywhere in the Assumptions.

SEVERITY  
Critical breaks reproducibility or contradicts design  
High  undefined artefact / concept needed downstream  
Medium under‑specified; inference possible but risky  
Low  stylistic or minor clarity issue

OUTPUT WHEN NO HOLES  
Write exactly: `No holes detected.` then `<<HF‑END>>`.

HOLE REPORT FORMAT  
For each hole, output the block below (no extra labels, no bullets):

--- HOLE {{ID}} | Severity={{Critical|High|Medium|Low}} ---
<narrative> "quoted sentence or clause"                 ← include only if present
<assumption> "quoted sentence or clause"                ← include only if present
Context: “… previous sentence … {{TARGET}} … next sentence …”
Why: one paragraph explaining the ambiguity (no bullets).  
Confidence={{HIGH|MEDIUM|LOW}}
--- END HOLE {{ID}} ---

• Quote exactly one full sentence before and after the target.  
• If information is entirely absent, quote nearest line and insert `[MISSING HERE]`.  
• Combine duplicate holes across docs into a single block, stacking both quotes.  
• Stop when done, and write `<<HF‑END>>`.

TOKENS  
When a single response nears ≈6 500 tokens end with `<<HF‑CONTINUE>>`.  
Resume in a new message starting `<<HF‑CONTINUATION>>` and keep going.  
Never split a HOLE block across messages.
```

---

## ➋  HOLE‑FIXER (REWRITER) TEMPLATE  (v 3)

````
##################################
#  HOLE‑FIXER • Sub‑segment {{NAME}}
##################################

INPUT  
You receive exactly one JSON array in the message **above** this template:

```json
{"hole_ids":[3,5,9]}
```

PROCESS
Rewrite **both** Narrative.txt and Assumptions.txt so every hole in `hole_ids` is resolved.
• Preserve paragraphs that need no change.
• Expand or insert detail where required.
• Mimic each file’s original tone: same tense, similar sentence length, no bullets, no code.

INLINE‑MARKER CONVENTION
Wrap every changed or new section with `<<<FIX id={{ID}}>>>` … `<<<END FIX>>>`.
Use the matching Hole ID so auditors can diff selectively.

OUTPUT
Send the rewritten Narrative first, then the rewritten Assumptions, each in a fenced block.

```txt
#####  REWRITTEN NARRATIVE.txt  #####
<<<FIX id=3>>>
… expanded prose …
<<<END FIX>>>

<unchanged paragraphs reproduced verbatim>

#####  END NARRATIVE  #####

#####  REWRITTEN ASSUMPTIONS.txt  #####
<<<FIX id=5>>>
… added formula definitions …
<<<END FIX>>>

<unchanged paragraphs reproduced verbatim>

#####  END ASSUMPTIONS  #####
```

RATIONALE BLOCK
After both files, list *one* short paragraph per Hole ID (no bullets, ≤ 3 sentences) explaining how your rewrite closes the gap and stating `Confidence={{HIGH|MEDIUM|LOW}}`.

LENGTH MANAGEMENT
If either rewritten file or the rationales push the message past ≈6 500 tokens:
• finish the current logical section, write `<<FR‑CONTINUE>>`,
• start the next message with `<<FR‑CONTINUATION>>` and continue.
Never split a single paragraph across messages.

END TOKEN
When both rewritten files and all rationales are complete, output `<<FR‑END>>` on its own line.

````

---

### Why these versions should “ace” a brutal review

* **Minimal scaffolding** – headers are single‑line, no excess labels or bullets.  
* **Expanded hole definition** – now captures undefined *concepts* like spatial priors.  
* **Severity tagging** – four clear levels; Critical–High–Medium the likely focus.  
* **Whole‑file rewrites** – fixes appear in context; unchanged material preserved.  
* **Deterministic diff markers** – each fix bracketed with Hole ID for easy grep or automated merge.  
* **Style fidelity rule** – mandates sentence‑length + tone matching without burdening you to describe it.  
* **Token‑safe splitting** – one control token set for finder (`HF‑…`) and another for rewriter (`FR‑…`), never colliding with text.  
* **No forbidden code or bullets** – complies with your narrative and assumptions style.

If any final nuance still feels loose, tell me and we’ll tighten it before you rerun the loop.

## ➌ INTEGRATOR

Below is a new **INTEGRATOR PROMPT** that aligns with the exact stylistic DNA of your full Narrative and Assumptions, fixes every flaw caught in the last audit, and guarantees a seamless, “always‑been‑there” merge.

---

````
####################################################
#  INTEGRATOR • Sub‑segment {{NAME}}               #
####################################################

INPUT FILES
 • narrative_*.txt         ← pristine source narrative
 • assumptions_*.txt       ← pristine source assumptions
 • holes_*.txt             ← identified <<<FIX id=…>>> blocks
 • fixes_*.txt             ← approved fixes for <<<FIX id=…>>> blocks
   (style: dense prose, no summaries; each block already
    states the anchor sentence or [MISSING HERE] placeholder)

ROLE
You are JP Morgan’s editorial integrator.  
Merge every fix **in place** so the finished Narrative and
Assumptions read as continuous first drafts—no FIX markers,
no placeholders, no duplicate sentences, no stylistic drift.

STYLE MATRIX  (MUST be honoured)

| File        | Voice & Flow                               | Allowed Syntax                               | Forbidden                                                       |
|-------------|--------------------------------------------|----------------------------------------------|-----------------------------------------------------------------|
| Narrative   | Technical‑narrative prose, long sentences, | Inline math `$…$`; inline code in back‑ticks | • bullets                                                       |
|             | first‑person plural, em‑dash cadence       | (rare), emphasised words `*like this*`,      | • numbered lists                                                |
|             |                                            | em‑dashes `—`                                | • code blocks ```…```                                           |
| Assumptions | Declarative companion prose,               | Inline & display math (`$$…$$`);             | • bullets *may stay* if already present but do not add new ones |
|             | one paragraph per rule/constant,           | inline code in back‑ticks; **short**         | • new code blocks of > 5 lines                                  |
|             | may embed brief one‑line code snippets     | code snippets in ```text``` fences           | • pseudocode                                                    |

GENERAL RULES
G-0 Ensure all anchors exist within file. If **any** anchor cannot be matched (even after fuzzy
     10‑word subsequence search) or placement is ambiguous, take note of it. 
     After search of all anchors if there are anchors which are missing then;
     STOP and emit exactly for all missing anchors:

       CLARIFICATION NEEDED – id={{n}} – “first five words
       of the missing anchor” - why you think it is missing to help the USER guide you

     then await instructions.
    
G‑1 Locate the anchor sentence from each <<<FIX id=…>>> block 
     *case‑insensitive*.  
     • If found, expand or replace at that exact spot.  
     • If anchor is `[MISSING HERE]`, insert the fix at the
       nearest preceding paragraph that introduces the same
       concept; if two candidates tie, pick the first.

G‑2 Do **not** truncate or paraphrase unchanged content; copy
     it verbatim so reviewers can run a plain diff.

G‑3 When integrating, replicate original typography  
     (em‑dashes, italics, line‑breaks, section headings).

G‑4 After merging, strip **all** `<<<FIX …>>>` and
     `<<<END FIX>>>` markers.

G‑5 Verification pass:  
     • Every `id=` present in fixes.txt must appear **exactly
       once** in the merged output.  
     • No literal `<<<FIX` or `<<<END FIX>>>` strings remain.  
     • No duplicate of the anchor sentence survives within a
       ±3‑line window of the insertion.  
     • Narrative contains **zero** bullet symbols `•‑*`,
       numbered lists `1)`, or fenced code blocks. And most have
       a logical flow with no abrupt interjections.
     • Assumptions may retain *existing* bullets or one‑line
       ```text``` snippets, but no multi‑line code fences or
       pseudocode were added.

TOKEN MANAGEMENT
 • When a single reply nears ≈6000 tokens, finish the current
   logical paragraph, output `<<IG‑CONTINUE>>`, and send a
   follow‑up message beginning `<<IG‑CONTINUATION>>`.  
   Never split a paragraph.

OUTPUT
```txt
#####  MERGED NARRATIVE.txt  #####
… fully integrated narrative …
#####  END NARRATIVE  #####

#####  MERGED ASSUMPTIONS.txt  #####
… fully integrated assumptions …
#####  END ASSUMPTIONS  #####
```

If either file exceeds ≈6000 tokens, split it into PART 1,
PART 2, … each inside its own `#####` block; keep order.

END
When both files pass verification, output `<<IG‑END>>`
on a line by itself.
\####################################################

# END OF TEMPLATE

\####################################################

````

**What changed & why**

* **Code ban reinstated** – multi‑line code fences disallowed in both docs; assumptions may keep their existing one‑liners.  
* **Bullet ban clarified** – zero bullets permitted in Narrative; Assumptions may *retain* but not *add* bullets.  
* **Style matrix** – explicit sentence‑length, voice, syntax cues to stop generic prose drift.  
* **Anchor‑search fallback & clarification hook** – avoids silent mis‑placements.  
* **Duplicate‑sentence purge** – guarantees seamless flow.  
* **No change‑log lure** – prevents summarisation creep; focus stays on detail.  
* **Control‑token safety** – only `<<IG‑CONTINUE>>`, `<<IG‑CONTINUATION>>`, `<<IG‑END>>` allowed, each on its own line.  

Drop your three files above this template, fill `{{NAME}}`, and the model will produce polished, audit‑ready documents that look like they were never broken.

