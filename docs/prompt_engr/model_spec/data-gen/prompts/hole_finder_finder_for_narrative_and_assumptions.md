Below is a pair of *lean* yet fully‑specified templates that reflect every preference you just confirmed.
They keep scaffolding to an absolute minimum, broaden the hole definition, tag severity, and move from sentence‑patches to whole‑document rewrites with clear inline markers.

---

## ➊  HOLE‑FINDER TEMPLATE  (v 3.1)

```
##################################
#  HOLE‑FINDER v3.1 • Sub‑segment {{NAME}}
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
Anchor: "exact sentence or clause"          ← mandatory; copy *one* of the quotes verbatim
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

## ➋  HOLE‑FIXER (REWRITER) TEMPLATE  (v 3.1)

````
##################################
#  HOLE‑FIXER v3.1 • Sub‑segment {{NAME}}
##################################

INPUT  
You receive exactly one JSON array in the message **above** this template like this example below:

```json
{"hole_ids":[3,5,9]}
```

PROCESS
Rewrite **both** Narrative.txt and Assumptions.txt so every hole in `hole_ids` is resolved.
• Preserve paragraphs that need no change.
• Expand or insert detail where required.
• Mimic each file’s original tone: same tense, similar sentence length, no bullets, no code.

INLINE‑MARKER CONVENTION
For every hole you fix, wrap the changed or new section like this **(notice the four metadata lines at the top, then the body, then `<<<END FIX>>>`)**:

```text
<<<FIX id={{ID}}>>>
TARGET: {{narrative | assumptions | both}}
INTENT: {{add | replace | delete | rewrite}}
ANCHOR: "exact sentence or clause"          ← copy from the Anchor line in HOLE {{ID}}
>>>
… FIX BODY …
<<<END FIX>>>
```

COLLECT‑AND‑ORDER RULE
  • Buffer all FIX blocks while generating.
  • After every hole_id is processed:
        – Sort buffered blocks in ascending id order within each TARGET.
        – Emit exactly one header and footer per TARGET.
  • If a header + its blocks exceed ~6 000 tokens, insert
    `<<FR‑CONTINUE>>` immediately after a header or between blocks.

OUTPUT
Send the rewritten Narrative first, then the rewritten Assumptions, each inside the single header/footer pair described above.

```txt
#####  REWRITTEN NARRATIVE.txt  #####
<<<FIX id=1>>>
TARGET: narrative
INTENT: add
ANCHOR: "exact sentence or clause"
>>>
… expanded prose …
<<<END FIX>>>
<<<FIX id=2>>>
TARGET: narrative
INTENT: add
ANCHOR: "exact sentence or clause"
>>>
… expanded prose …
<<<END FIX>>>
…

<unchanged paragraphs reproduced verbatim>

#####  END NARRATIVE  #####

#####  REWRITTEN ASSUMPTIONS.txt  #####
<<<FIX id=1>>>
TARGET: narrative
INTENT: add
ANCHOR: "exact sentence or clause"
>>>
… added formula definitions …
<<<END FIX>>>
…
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

## ➌ INTEGRATOR v3
Below is **INTEGRATOR v3**—the fully patched template that incorporates every fix flagged in the brutal audit (items 2‑A → 2‑H) and aligns seamlessly with your Hole‑Finder v3 and Hole‑Fixer v3 workflow.

---

````
####################################################
#  INTEGRATOR v3 • Sub‑segment {{NAME}}            #
####################################################

INPUT FILES (all four must be present in this chat turn)
  narrative_original.txt        ← unaltered baseline
  assumptions_original.txt      ← unaltered baseline
  holes.txt                     ← approved HOLE blocks
  fixes.txt                     ← approved FIX blocks
  

EACH FIX BLOCK MUST CONTAIN
  <<<FIX id=K>>>
  TARGET: narrative | assumptions | both      (MANDATORY)
  INTENT: add | replace | delete | rewrite    (MANDATORY)
  ANCHOR: "quoted sentence…" | [MISSING HERE] (MANDATORY)
  … FIX BODY …
  <<<END FIX>>>
  
  If FIX ids are not in ascending order, 
    read all blocks into memory, 
    sort by id within each TARGET, 
    then proceed with the merge.

Fail‑safe: if any FIX is missing TARGET or INTENT, assume TARGET=both,
INTENT=add, **but record “MISSING METADATA” in the integration report**.
If any FIX lacks an ANCHOR *while* the matching HOLE provides one,
abort with:
  META‑INCONSISTENCY ERROR – id=K.

MISSION
Produce polished Narrative and Assumptions with every FIX applied once,
no markers, no placeholders, no duplicate sentences, preserved voice.

STYLE RULES
  Narrative   – long cohesive technical sentences, first‑person plural,
                inline math `$…$`, italics, em‑dashes.
                **No bullets, no numbered lists, no fenced code.**
  Assumptions – declarative paragraphs, may use inline `$…$`
                or display math `$$…$$`, may retain pre‑existing bullets,
                may keep one‑line ```text``` snippets already present.
                **Do not introduce new bullets or multi‑line code fences.**

ANCHOR‑LOCATOR (four‑stage)
  1. Exact canonical match (whitespace + markdown stripped).
  2. Fuzzy sentence match:
        score = 0.55·Jaccard + 0.30·LCS + 0.15·BigramDice
        accept ≥ {{FUZZY_THRESH:0.68}}
  3. Fuzzy paragraph match (same score on paragraph text).
  4. Thematic fallback:
        pick paragraph with highest density of domain tokens
        (capitalised terms, snake_case, ALL_CAPS, artefact filenames).

If paragraph ends with ':' or regex ^(Step|Phase|Segment)\s+\d+,
insert any *add* text **after** that paragraph, not inside.

INTENT EXECUTION
  replace / rewrite  – swap anchor sentence (or whole paragraph if FIX spans >1 sentence).
  add                – insert FIX BODY after anchor paragraph; if anchor was [MISSING HERE]
                       use thematic fallback placement.
  delete             – remove anchor sentence; if paragraph empties, drop paragraph.

Over‑eager delete guard:
  if deleting the *sole* definition of a concept, downgrade to replace with empty stub.

AFTER EACH INSERT
  • Local de‑dup: within ±3 sentences, drop duplicates (similarity ≥ 0.90).
  • Paragraph re‑tokenised so later FIXes see updated text.

GLOBAL PASS (after all FIXes)
  1. Terminology map first definition → canonical form.
  2. Harmonise later variants to canonical (unless FIX introduces longer, more specific form).
  3. Schema lists: merge to superset, order alphabetically for diff‑stability.
  4. Duplicate check repeated after canonicalisation.

CLEAN‑UP & VERIFICATION
  • Remove all <<<FIX …>>> / <<<END FIX>>> markers.
  • Strip editorial artefacts: strike‑through ~~…~~, diff chevrons >>> <<< .
  • Ensure Narrative contains zero list markers and zero fenced code blocks.
  • Ensure every FIX id appears exactly once per TARGET.
  • Ensure no literal ‘<<<FIX’ or ‘<<<END FIX>>>’ strings remain.

UNPLACED FIXES
  Any FIX still unresolved after fallback is appended *outside* the merged files,
  under “UNPLACED FIXES” header, with REASON diagnostics.

TOKEN MANAGEMENT
  If reply nears ≈6 000 tokens, finish paragraph, output `<<IG‑CONTINUE>>`
  on its own line, then continue in a new message prefixed `<<IG‑CONTINUATION>>`.
  Never split a paragraph.

OUTPUT
```txt
#####  MERGED NARRATIVE.txt  #####
… integrated narrative …
#####  END NARRATIVE  #####

#####  MERGED ASSUMPTIONS.txt  #####
… integrated assumptions …
#####  END ASSUMPTIONS  #####
```

Split either file into PART 1, 2, … blocks if needed.

INTEGRATION REPORT  (separate message **after** <\<IG‑END>>)
id | placement | action | notes
Omit if >120 fixes or if user sets REPORT=false.

FINAL TOKEN
When both merged files pass verification, output `<<IG‑END>>`
on its own line.  If there are unplaced fixes, output `<<IG‑END‑WITH‑UNPLACED>>`.

\####################################################

# END INTEGRATOR v3

\####################################################

````

**Key patches versus v2**

* **Mandatory TARGET / INTENT / ANCHOR** with abort‑on‑mismatch safeguard.  
* **Fuzzy threshold exposed** (`{{FUZZY_THRESH}}`) so you can tune per run.  
* **Paragraph colon/step guard** prevents mid‑list insertions.  
* **Terminology map precedes duplicate sweep** (audit item 2‑E).  
* **Delete‑downgrade rule** averts accidental loss of sole definitions.  
* **UNPLACED appendix now *outside* merged docs** to keep first‑draft feel.  
* **Integration report moved to post‑END message** so it never forces file splits.  
* **Control tokens** remain minimal: `<<IG‑CONTINUE>>`, `<<IG‑CONTINUATION>>`, `<<IG‑END>>`.

Drop your four files above this template, replace `{{NAME}}`, adjust `{{FUZZY_THRESH}}` if needed, and the model will deliver cohesive, audit‑ready documents with zero manual babysitting.

