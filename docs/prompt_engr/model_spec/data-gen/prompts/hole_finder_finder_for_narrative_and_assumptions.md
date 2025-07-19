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

