# S0.1 — Universe, symbols, authority (formal)

## S0.1.a Typed domains and the ingress relation

Define the primitive domains:

* Merchant identifiers: $\mathsf{MerchantID}$ (opaque identifiers; equality and ordering only).
* Merchant category codes: $\mathsf{MCC}=\{1000,\dots,9999\}\subset\mathbb{N}$ (4-digit numeric codes).
* Channels: $\mathsf{Chan}=\{\text{CP},\text{CNP}\}$.
* Countries (ISO-3166-1 alpha-2): $\mathcal{I}\subset\{\text{AA},\text{AB},\dots\}$ (2-character uppercase strings).

The **ingress table** is a finite relation (no duplicates by definition):

$$
\texttt{merchant_ids}\ \subseteq\ \mathsf{MerchantID}\times \mathsf{MCC}\times \mathsf{Chan}\times \mathcal{I}.
$$

We write a row as a 4-tuple $(\texttt{merchant_id},\texttt{mcc},\texttt{channel},\texttt{home_country_iso})$. This table **must** validate against `schemas.ingress.layer1.yaml#/merchant_ids`. S0.1’s first outcome is the **set** of seed merchants

$$
\mathcal{M}\;=\;\{\texttt{merchant_id} : (\texttt{merchant_id},\_,\_,\_)\in \texttt{merchant_ids}\}.
$$

All further computation quantifies over $\mathcal{M}$.

### Ingress invariants (enforced by validation)

For every $(m,\mathrm{mcc},\mathrm{ch},c)\in\texttt{merchant_ids}$:

1. $m\in\mathsf{MerchantID}$, $\mathrm{mcc}\in\mathsf{MCC}$, $\mathrm{ch}\in\mathsf{Chan}$, $c\in\mathcal{I}$.
2. **Uniqueness:** at most one tuple with the same $m$.
3. **Non-nulls:** all four fields present (no missing values).
4. **ISO authority:** $c$ must be an ISO-3166 alpha-2 code admitted by the run’s canonical list (see below).
   (If any fails, S0 aborts before proceeding.)

---

## S0.1.b Canonical reference artefacts (immutable within a run)

S0.1 **loads and freezes** three immutable references:

1. **ISO countries:** the set $\mathcal{I}$ of valid ISO-3166 alpha-2 codes used for domain checks and foreign keys.
2. **GDP per-capita function:** a total map

$$
G:\ \mathcal{I}\ \to\ \mathbb{R}_{>0},\qquad c\mapsto G(c),
$$

**pinned to the 2025-04-15 vintage** (so every run uses the same numeric vector).
3\) **Jenks 5-bucket map:** a total map

$$
B:\ \mathcal{I}\ \to\ \{1,2,3,4,5\},
$$

precomputed from the pinned GDP vintage (not recomputed at run time). For intuition, there exist thresholds $\tau_0<\dots<\tau_5$ such that $B(c)=k$ iff $G(c)\in(\tau_{k-1},\tau_k]$; but only the map $B(\cdot)$ itself is authoritative.

**Immutability contract.** Within a single run, $\mathcal{I}$, $G$, and $B$ are **constants**. Any change of these artefacts (new ISO list, new GDP vintage, or a regenerated Jenks map) must occur between runs and will be captured by lineage in S0.2 (parameter/fingerprint hashing).

---

## S0.1.c Authority and precedence

There are **three** authoritative schema families, in strict precedence:

1. `schemas.ingress.layer1.yaml` — governs external inputs (e.g., `merchant_ids`) and canonical lookups.
2. `schemas.1A.yaml` — governs 1A’s own parameter-scoped and egress datasets.
3. `schemas.layer1.yaml` — governs shared RNG/event envelopes and event payloads.

If an Avro or auxiliary schema disagrees, **these YAML schemas win**. All validations, FK checks, and type domains in S0+ later states are defined **by these authorities**.

---

## S0.1.d Outputs of S0.1 (what later substates may use)

After S0.1, the process exposes, for the rest of S0 (and states S1–S8):

* The seed merchant set $\mathcal{M}$ and the validated ingress relation `merchant_ids`.
* The canonical domains $\mathcal{I}$, $G(\cdot)$, $B(\cdot)$ (all immutable for the run).
* The schema-authority precedence used by every subsequent validation.

No RNG, no hashing, and no feature vectors are produced **yet** (that starts in S0.2+).

---

### Quick checklist (pass/fail for S0.1)

* Ingress rows conform to the authoritative ingress schema.
* $\mathcal{I}$, $G$, $B$ are loaded and pinned for the run.
* $\mathcal{M}$ is well-defined (no duplicate merchant IDs).
* All subsequent states can treat $\mathcal{I}$, $G$, $B$ as constants.

---

# S0.2.1 Hash primitives (definitions, conversions, guards)

## A) Byte strings, length, concatenation

* Let $\mathbb{B}=\{0,1\}$. A **byte string** is an element $x\in(\mathbb{B}^8)^{*}$.
* **Length in bytes:** $|x|\in\mathbb{N}$.
* **Concatenation:** for byte strings $x,y$, define $x\ \|\ y$ as the byte string formed by appending the bytes of $y$ after $x$. Concatenation is **on raw bytes**, never on hex text. This is used directly in the parameter-hash recipe (e.g., concatenating raw 32-byte digests before hashing).

## B) SHA-256

* $\mathrm{SHA256}:(\mathbb{B}^8)^{*}\to\mathbb{B}^{256}$ maps any byte string to a **32-byte** digest. We always hash **exact file bytes** (no newline, encoding, or YAML normalization): $D(a)=\mathrm{SHA256}(\mathrm{bytes}(a))$.
* **Hex encoder (lowercase):**
  $\mathrm{hex64}:\mathbb{B}^{256}\to\{[0\!-\!9a\!-\!f]\}^{64}$ produces a 64-char lowercase hex. Downstream schemas accept only `^[a-f0-9]{64}$`.

## C) 256-bit XOR

* Let $\oplus:\mathbb{B}^{256}\times\mathbb{B}^{256}\to\mathbb{B}^{256}$ be **bytewise XOR**:
  if $x=(x_0,\dots,x_{31})$ and $y=(y_0,\dots,y_{31})$ with bytes $x_j,y_j\in\mathbb{B}^8$, then

  $$
  x\oplus y \;=\; (x_0\oplus y_0,\ \dots,\ x_{31}\oplus y_{31}).
  $$

  The identity element is $0^{256}$ (32 zero bytes).
  **XOR-reduce** of a finite multiset $S\subset(\mathbb{B}^{256})$ is $\bigoplus S:=\;$left-to-right fold with identity $0^{256}$.
  This operator is used both in forming the **manifest fingerprint** and (legacy variant) for the parameter hash; our *current* parameter-hash uses concatenation→SHA-256, while the manifest uses XOR-reduce→SHA-256.

## D) 64-bit little-endian conversions (used in S0.3 seeding)

* $\mathrm{LE64}:\{0,\dots,2^{64}\!-\!1\}\to\mathbb{B}^{64}$ encodes an unsigned 64-bit integer as **8 bytes, little-endian**.
* $\mathrm{LE64}^{-1}:\mathbb{B}^{64}\to\{0,\dots,2^{64}\!-\!1\}$ decodes 8 little-endian bytes to u64.
* $\mathrm{split64}:\mathbb{B}^{128}\to\{0,\dots,2^{64}\!-\!1\}^2$ splits 16 bytes into two u64 via little-endian for the low/high words.
  These are invoked by the master seed and counter derivations (S0.3).

## E) 20→32 byte padding for git commit hashes

Let $\mathrm{git}_{\mathrm{raw}}$ be the VCS commit hash bytes. Define

$$
\mathrm{git}_{32} \;=\;
\begin{cases}
\text{0x00}^{12}\ \|\ \mathrm{git}_{\mathrm{raw}}, & |\mathrm{git}_{\mathrm{raw}}|=20\ \text{(SHA-1)},\\
\mathrm{git}_{\mathrm{raw}}, & |\mathrm{git}_{\mathrm{raw}}|=32\ \text{(SHA-256)},\\
\text{abort}, & \text{otherwise}.
\end{cases}
$$

This produces a **32-byte** value suitable for XOR alongside 32-byte digests. Used in the manifest fingerprint.

## F) Helper combinators used by S0.2

* **Concat-digest** (used for the parameter hash): for filenames $p_1 < p_2 < p_3$ (ASCII lexicographic order),

  $$
  \text{parameter_hash_bytes}\;=\;\mathrm{SHA256}\!\big(D(p_1)\ \|\ D(p_2)\ \|\ D(p_3)\big),\quad
  \text{parameter_hash}=\mathrm{hex64}(\cdot).
  $$

  This is the **only** version key for parameter-scoped datasets.
* **XOR-digest** (used for the manifest fingerprint): if $\mathcal{A}$ is the set of all artefacts opened in 1A, let

  $$
  X=\Big(\bigoplus_{a\in\mathcal{A}} D(a)\Big)\ \oplus\ \mathrm{git}_{32}\ \oplus\ \text{parameter_hash_bytes},\qquad
  \text{manifest_fingerprint_bytes}=\mathrm{SHA256}(X),\ \text{then hex64}.
  $$

  This fingerprint versions **egress & validation** and appears in their partition paths.

## G) Guards & failure semantics

Operations below **abort** S0.2 with a reproducible message:

1. **Length mismatch:** any XOR operand not exactly 32 bytes; any LE64 input not 8 or 16 bytes (for `split64`).
2. **Hex policy breach:** any persisted fingerprint/hash not matching `^[a-f0-9]{64}$`.
3. **Git hash anomaly:** commit bytes not 20 or 32 (unexpected VCS format).

---

### What S0.2.1 “exports” to S0.2.2–S0.2.3

* **Primitives:** $\mathrm{SHA256}$, $\mathrm{hex64}$, $\oplus$, $\|$, $\mathrm{git}_{32}$, $\mathrm{LE64}$, $\mathrm{split64}$.
* **Recipes:** Concat-digest (parameter hash) and XOR-digest (manifest fingerprint).
* **Contracts:** All inputs are raw bytes; outputs are 32-byte digests or 64-hex strings; schema patterns/paths downstream rely on these encodings (e.g., `outlet_catalogue/…/fingerprint={manifest_fingerprint}/`).

---

# S0.2.2 — Parameter hash (canonical, under-the-hood)

## Goal

Produce a **single 256-bit key** `parameter_hash` that deterministically version-controls all **parameter-scoped** datasets. It must change if **any byte** of any required parameter file changes, and be invariant to directory layout or file read chunking.

---

## Inputs (exactly three files, required)

Let the required set of **filenames** be

$$
\mathcal{F}=\{\text{``hurdle_coefficients.yaml''},\ \text{``nb_dispersion_coefficients.yaml''},\ \text{``crossborder_hyperparams.yaml''}\}.
$$

Each filename must resolve to **exactly one** regular file on disk (symlinks allowed but resolved), and will be read as raw bytes.

> Important: Only the **file contents** matter for digesting. Paths, YAML parsing, whitespace normalization, and OS line endings are **not** used. We hash **exact bytes on disk**.

---

## Discovery & validation (before hashing)

1. **Resolve** each $f\in\mathcal{F}$ via the artefact registry → absolute path $P(f)$.
2. **Symlink resolution:** resolve $P(f)$ through symlinks; reject cycles.
3. **File type:** require “regular file”; reject directories, sockets, FIFOs.
4. **Uniqueness:** each $f$ appears **once**; duplicates by name are an error.
5. **Readability:** open for read; permission errors abort.
6. **Stability window (optional hardening):** record `(size, mtime_ns)` before and after hashing; if either changes, re-hash once; if still inconsistent, abort (`changed_during_hash`).

Zero-length files are allowed (their SHA-256 is the standard zero-length digest).

---

## Digest of each file (raw bytes, streaming)

For any resolved file $a$ (one of the three):

* Define $D(a)=\mathrm{SHA256}(\text{bytes}(a))\in\{0,1\}^{256}$.
* **Streaming**: read in fixed chunks (e.g., 1 MiB) and update the SHA-256 state; do **not** transcode encodings; include every byte as stored (including `\r\n` vs `\n`, BOMs, trailing newlines).
* Do **not** canonicalize YAML (no parse-and-dump); we hash the literal bytes.

This yields three 32-byte digests: $D_1, D_2, D_3$.

---

## Canonical ordering of inputs

Sort the **filenames** in **ASCII lexicographic** order (case-sensitive) to obtain $(p_1,p_2,p_3)$. With the three names above, the order is:

$$
p_1=\text{``crossborder_hyperparams.yaml''},\quad
p_2=\text{``hurdle_coefficients.yaml''},\quad
p_3=\text{``nb_dispersion_coefficients.yaml''}.
$$

Let $D(p_i)$ denote the SHA-256 digest (32 bytes) of the file whose name is $p_i$.

---

## Construction (concatenate-then-hash)

Concatenate the **raw digests** in that filename order to form a 96-byte string:

$$
C \;=\; D(p_1)\ \|\ D(p_2)\ \|\ D(p_3)\ \in \{0,1\}^{96\cdot 8}.
$$

Hash the concatenation once more:

$$
\boxed{\ \text{parameter_hash_bytes} \;=\; \mathrm{SHA256}(C)\ \in\ \{0,1\}^{256}\ }.
$$

Encode for persistence:

$$
\boxed{\ \text{parameter_hash}\;=\;\mathrm{hex64}(\text{parameter_hash_bytes})\ \in\ [a\!-\!f0\!-\!9]^{64}\ }.
$$

---

## Properties (why this is robust)

* **Any-byte sensitivity:** if any single bit of any input file flips, at least one $D(p_i)$ changes → `parameter_hash` changes with overwhelming probability ($1-2^{-256}$).
* **Order invariance to paths:** directory layout doesn’t matter; only filename **order** and **content bytes** matter.
* **Streaming-safe:** chunk boundaries do not affect $D(\cdot)$; the result is independent of buffer sizes.
* **Normalization-free:** no dependence on YAML parser, locale, or line ending normalization.

---

## Failure semantics (abort conditions)

Abort S0.2 with a precise error code if any of the following occurs:

* `missing_parameter_file(f)`: a required filename $f$ is not found.
* `duplicate_parameter_file(f)`: more than one candidate resolves for $f$.
* `unreadable_parameter_file(f)`: permission/IO error.
* `not_regular_file(f)`: resolved target is not a regular file.
* `changed_during_hash(f)`: `(size, mtime_ns)` instability across the hashing pass(es).
* `bad_hex_encoding`: when persisting, `parameter_hash` is not `^[a-f0-9]{64}$` (should never happen if encoder is correct).

Each abort should include `(filename, resolved_path, errno, size_before/after, mtime_before/after)` for forensics.

---

## Determinism & reproducibility invariants

* **I-PH1 (content determinism):** For a fixed triple of file **contents**, `parameter_hash` is **bit-identical** across machines/OSes.
* **I-PH2 (name determinism):** Renaming any of the three files changes the **ordering** (and hence `parameter_hash`) even if bytes are unchanged. (We require the canonical names; this prevents accidental swaps.)
* **I-PH3 (scope):** Only these three files influence `parameter_hash`. Extra parameter files present in the repo or on disk are **ignored** by S0.2.2.

---

## What this key controls downstream

All **parameter-scoped** datasets and caches must partition on `parameter_hash={parameter_hash}` (e.g., `hurdle_pi_probs`, `crossborder_eligibility_flags`, `country_set`, `ranking_residual_cache_1A`, and any validation outputs keyed to parameters rather than egress). The **egress** datasets (e.g., `outlet_catalogue`) will instead be versioned by the **manifest fingerprint** from S0.2.3.

---

## Minimal reference algorithm (pseudo, language-agnostic)

```
INPUT: registry paths for the three canonical filenames in F
OUTPUT: parameter_hash (64-char lowercase hex)

1  files := sort_ascii(["crossborder_hyperparams.yaml",
                        "hurdle_coefficients.yaml",
                        "nb_dispersion_coefficients.yaml"])
2  digests := []
3  for f in files:
4      p := resolve_path_via_registry(f)       # symlinks allowed; must end at a regular file
5      (size0, mtime0) := stat(p)
6      D := sha256_streaming_bytes(p)          # exact bytes; no normalization
7      (size1, mtime1) := stat(p)
8      if (size0,mtime0)!=(size1,mtime1):      # optional hardening
9          D := sha256_streaming_bytes(p)
10     digests.append(D)                       # D is 32 bytes
11 C := concat_bytes(digests[0], digests[1], digests[2])   # 96 bytes
12 H := sha256_bytes(C)                        # 32 bytes
13 return hex_lowercase_64(H)
```

---

# S0.2.3 — Manifest fingerprint (run lineage, under the hood)

## Goal

Produce a **run-level lineage key** `manifest_fingerprint ∈ [a–f0–9]^64` used to version **egress** and **validation** partitions and embedded in all RNG envelopes. It must change if **any opened artefact** (models, reference tables, schema knobs, etc.) changes, **or** if the code commit changes, **or** if the parameter bundle (from S0.2.2) changes.

---

## Inputs

* **Artefact set** $\mathcal{A}$: the **set of all files opened** by the 1A run (e.g., ISO table, GDP bucket map, currency splits, schema catalogs, plus the 3 YAMLs). Each $a\in\mathcal{A}$ is a resolved, regular file; define $D(a)=\mathrm{SHA256}(\text{bytes}(a))\in\{0,1\}^{256}$. (The S0 doc explicitly defines $\mathcal{A}$ this way.)
* **Repository commit bytes** $\text{git}_{32}\in\{0,1\}^{256}$: the VCS commit hash as 32 bytes; if using SHA-1, **left-pad with 12 zero bytes** to 32 (per S0.2.1).
* **`parameter_hash_bytes`** $\in\{0,1\}^{256}$: from S0.2.2 (concat-digest of the three YAMLs). Partitioning for parameter-scoped datasets depends only on this; we fold it here too so egress/validation lineage “tracks” the parameter bundle.

---

## Canonical construction

1. **Artefact closure & uniqueness.** Build $\mathcal{A}$ as the set of **distinct** absolute paths after symlink resolution; reject non-regular files. (If a file is opened via multiple aliases, include it **once**.)
2. **Digest each artefact.** For all $a\in\mathcal{A}$, compute $D(a)$ via streaming SHA-256 of **raw bytes** (no normalization).
3. **XOR-reduce to a 32-byte accumulator.**

   $$
   X_0 \;=\; \bigoplus_{a\in\mathcal{A}} D(a)\quad(\text{bytewise XOR; identity }0^{256}).
   $$
4. **Fold in commit and parameters.**

   $$
   X \;=\; X_0 \;\oplus\; \text{git}_{32} \;\oplus\; \text{parameter_hash_bytes}.
   $$
5. **Hash once.**

   $$
   \boxed{\ \text{manifest_fingerprint_bytes}=\mathrm{SHA256}(X)\ },\qquad
   \text{manifest_fingerprint}=\mathrm{hex64}(\text{manifest_fingerprint_bytes}).
   $$

**Why XOR?** It makes the accumulator **order-independent** (set semantics) and sensitive to any byte change in any artefact; the final SHA-256 removes linearity and yields a uniformly distributed 256-bit lineage key. The separate inclusion of `parameter_hash_bytes` ensures egress lineage shifts even if the three YAMLs are already members of $\mathcal{A}$.

---

## Properties & invariants

* **Order-insensitivity.** Because XOR is commutative/associative, permuting $\mathcal{A}$ does not change `manifest_fingerprint`.
* **Any-byte sensitivity.** Flipping any bit in any opened artefact (or changing the commit or parameter bundle) changes the fingerprint with probability $1-2^{-256}$.
* **Non-emptiness.** $\mathcal{A}\neq\varnothing$ (at least the 3 YAMLs + ISO/GDP are opened in S0). Otherwise abort.
* **Encoding.** Persisted value must satisfy the hex pattern `^[a-f0-9]{64}$` (schema primitive `hex64`).

---

## Failure semantics (abort with diagnostics)

* `artefact_missing(path)` / `not_regular_file(path)` / `unreadable(path)` during closure or hashing.
* `git_hash_bad_length` if commit bytes are neither 20 nor 32 before padding.
* `empty_artefact_set` if $\mathcal{A}$ resolves empty.
* `bad_hex_encoding` if the encoder yields a non-hex64 string (should not happen).

Each failure records: path, resolved target, errno, size/mtime (before/after), and, for commit, the raw length observed.

---

## Determinism & replay

For a fixed set of **file contents** in $\mathcal{A}$, a fixed commit, and a fixed parameter bundle, the fingerprint is **bit-reproducible** across machines/OSes. The value is written into:

* **Egress partitions**:
  `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/…` (and stored per row as `manifest_fingerprint`).
* **Validation bundle**:
  `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/…` (plus `_passed.flag`).
* **RNG events**: every JSONL event includes `manifest_fingerprint` in the **shared envelope** (required by `schemas.layer1.yaml`).

Parameter-scoped datasets (e.g., `country_set`, `ranking_residual_cache_1A`, `crossborder_eligibility_flags`) continue to partition by `parameter_hash={parameter_hash}`. This split of responsibilities is asserted in S0 and re-checked in validation.

---

## Minimal reference algorithm (language-agnostic)

```
INPUT: artefact registry + runtime file list (all actually opened files),
       git_commit_bytes (20 or 32), parameter_hash_bytes (32)
OUTPUT: manifest_fingerprint (64-char lowercase hex)

1  A := resolve_all_opened_files()            # absolute paths, symlinks resolved
2  if A is empty: abort("empty_artefact_set")
3  X := 0x00...00 (32 bytes)
4  for a in set(A):                            # de-duplicate aliases
5      assert is_regular_file(a)
6      D := sha256_streaming_bytes(a)         # exact bytes, no normalization
7      X := xor_32bytes(X, D)
8  git32 := (len(git_commit_bytes)==20) ? (0x00*12 || git_commit_bytes)
         : (len==32 ? git_commit_bytes : abort("git_hash_bad_length"))
9  X := xor_32bytes( xor_32bytes(X, git32), parameter_hash_bytes )
10 H := sha256_bytes(X)
11 return hex_lowercase_64(H)
```

---

## What S0.2.3 “exports” to the rest of 1A

* A single **`manifest_fingerprint`** (hex64) used to **partition egress and validation** and recorded in **every** RNG envelope.
* The explicit **partitioning contract**: parameter-scoped by `{parameter_hash}`, egress/validation by `{manifest_fingerprint}` (and often `{seed}`). Validators in S9 assert this split.

---

# S0.3.1 — Algorithm and state (Philox engine, envelope, and u01)

## A) Engine and state objects

We fix the counter-based RNG to **Philox $2\times64$ with 10 rounds**. The engine is a pure function

$$
\Phi_{S}:\ \{0,\dots,2^{64}\!-\!1\}^2 \longrightarrow \{0,\dots,2^{64}\!-\!1\}^2,
$$

parameterised by a **64-bit key** $S$ (“seed”) and evaluated at a **128-bit counter**
$C=(c_{\mathrm{hi}},c_{\mathrm{lo}})\in\{0,\dots,2^{64}\!-\!1\}^2$.
A single **block call** returns two independent 64-bit integers:

$$
(z_0,z_1) \;=\; \Phi_{S}(C).
$$

**Counter stepping.** Let $\mathrm{inc}(C)$ add 1 to the low word with carry:

$$
\mathrm{inc}(c_{\mathrm{hi}},c_{\mathrm{lo}}) \;=\; \big(c_{\mathrm{hi}} + \mathbf{1}\{c_{\mathrm{lo}}=2^{64}\!-\!1\},\ (c_{\mathrm{lo}}+1)\bmod 2^{64}\big).
$$

Consuming $B$ blocks advances the counter by $B$ applications of $\mathrm{inc}$. We never reuse a counter value within a run. (Per-label “jumps” that reposition the counter are specified later in S0.3.3.)

---

## B) Event envelope (what every RNG JSONL record must carry)

Every RNG JSONL event **must** include the shared **rng envelope** fields:

$$
\{\texttt{ts_utc},\texttt{run_id},\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint},\texttt{module},\texttt{substream_label},\texttt{rng_counter_before_{\{lo,hi\}}},\texttt{rng_counter_after_{\{lo,hi\}}}\}.
$$

* `seed` is the master Philox key $S$ (u64).
* `rng_counter_before_{lo,hi}` is the **counter before** the first block for the event.
* `rng_counter_after_{lo,hi}` is the counter **after** the last block consumed by the event.
* `parameter_hash` and `manifest_fingerprint` bind the event to the parameter bundle and run fingerprint.
* `module` and `substream_label` identify the logical producer and the Philox substream (see S0.3.3).
  These fields and types are mandated by `schemas.layer1.yaml` and are validated structurally.

In addition, the **RNG trace log** carries `draws` (the count of uniforms consumed) together with the same before/after counters; validators recompute the expected block advance:

$$
B=\left\lceil \frac{\texttt{draws}}{2}\right\rceil,\qquad
(\text{after_hi},\text{after_lo}) \stackrel{?}{=}\mathrm{advance}\big((\text{before_hi},\text{before_lo}),\ B\big).
$$

Any mismatch is a hard failure.

---

## C) Open-interval uniforms $u\in(0,1)$ (binary64-safe mapping)

All event schemas that log a uniform require **open-interval** $u01$ values. We obtain a binary64 deviate $u\in(0,1)$ from a 64-bit integer $z$ by using the top 53 bits (binary64 mantissa width) with a half-ulp offset:

1. Extract top-53 bits: $t = \left\lfloor z/2^{11} \right\rfloor \in \{0,\dots,2^{53}\!-\!1\}$.
2. Map to $(0,1)$:

$$
\boxed{\ u \;=\; \frac{t + \tfrac{1}{2}}{2^{53}} \ }\ \in\ \Big(\tfrac{1}{2^{54}},\, 1-\tfrac{1}{2^{54}}\Big).
$$

This guarantees strict **exclusion** of 0 and 1 and is invariant to platform endianness (we only shift integers). When an event needs $d$ uniforms, we read the block outputs $(z_0,z_1),(\tilde z_0,\tilde z_1),\dots$, applying the mapping to each in order; number of blocks consumed is $B=\lceil d/2\rceil$. The resulting `u` fields validate against the `u01` primitive in the shared schema.

---

## D) Consumption semantics (uniform accounting)

For a single **event** that needs $d$ uniforms:

* **Before-state:** read `rng_counter_before_{hi,lo}` $=$ $C_{\mathrm{before}}$.
* **Blocks:** $B=\lceil d/2\rceil$.
* **Outputs:** collect $(z_0,z_1)$ from $\Phi_S(C_{\mathrm{before}})$, then increment the counter $B-1$ times to obtain the remaining blocks, mapping each $z$ to $u$ via §C.
* **After-state:** compute $C_{\mathrm{after}} = \mathrm{advance}(C_{\mathrm{before}},B)$ and write it to `rng_counter_after_{hi,lo}`.
* **Trace:** emit a `rng_trace_log` record with `draws=d` and the same before/after counters.

Downstream event schemas (e.g., `hurdle_bernoulli`, `gumbel_key`, `dirichlet_gamma_vector`, `poisson_component`, `gamma_component`, `nb_final`, `ztp_*`) inherit the envelope and add their payload; validators cross-check that the number of logical uniforms implied by the payload equals `draws` in the trace and thus $B$ blocks.

---

## E) Determinism, ordering, and isolation

* **Determinism:** Given fixed `(seed, manifest_fingerprint, parameter_hash)` and the same **substream label** and **merchant ordering**, all events reproduce bit-identically; counters advance only by the declared number of blocks. (Substream jump policy sits in S0.3.3.)
* **Ordering:** Within an event, we consume $z_0$ **before** $z_1$; across blocks, we process in ascending counter order.
* **Isolation:** Different substreams (labels) start from **disjoint counter locations**; jumping is logged (see “stream_jump” dataset in the dictionary) and ensures that events cannot overlap counters even if executed out of order.

---

## F) Invariants and failure semantics

**Invariants (must hold for every event):**

1. Envelope presence and types match `schemas.layer1.yaml#/$defs/rng_envelope`.
2. `u01` values (when present) satisfy $0 < u < 1$ per schema primitive.
3. Counter conservation:

$$
\text{after} \;=\; \mathrm{advance}(\text{before},\ \lceil \tfrac{\texttt{draws}}{2}\rceil).
$$

4. Monotonic counters across events within the **same substream** (strictly increasing by blocks).
5. `seed`, `parameter_hash`, `manifest_fingerprint` in each event equal the run’s authoritative values.

**Abort conditions (hard fail):**

* Missing any required envelope field or schema-type violation.
* Counter conservation failure or non-monotonic advance in a substream trace.
* Any logged uniform equals 0 or 1 (should be impossible under §C, but validated via `u01`).

---

## G) What S0.3.1 exports to S0.3.2/S0.3.3 and later states

* The **engine contract** $(S,C)\mapsto(z_0,z_1)$ and the block/advance arithmetic.
* The **envelope contract** (fields, meanings, and counter accounting) that every RNG JSONL record must satisfy.
* The **u01 mapping** from 64-bit integers to binary64 $u\in(0,1)$ with strict open bounds.
* The requirement to log `rng_trace_log(draws, before, after)` per substream, enabling S9’s replay/accounting checks.

---

# S0.3.2 — Master seed and initial counter (deterministic, under the hood)

## Goal

Derive a single **64-bit Philox key** $S_{\text{master}}$ and a **128-bit starting counter** $C_0=(c_{\mathrm{hi}},c_{\mathrm{lo}})$ **deterministically** from:

* a run-supplied 64-bit integer $s$, and
* the 32-byte `manifest_fingerprint_bytes` (from S0.2.3),

using **domain-separated** SHA-256 constructions so that (i) reordering/aliasing cannot collide seed and counter domains, and (ii) different runs/commits/artefact sets produce different RNG trajectories.

---

## Inputs (types, encoding, guards)

* $s \in \{0,\dots,2^{64}\!-\!1\}$ — **unsigned** 64-bit integer provided by the caller (“run seed”).
* `manifest_fingerprint_bytes` $\in \mathbb{B}^{256}$ — exactly **32 bytes** (raw, not hex).
* **String tags** for domain separation are **ASCII** byte strings:

  * $t_{\text{seed}}=$ `b"seed:1A"`,
  * $t_{\text{ctr}}=$ `b"ctr:1A"`.

**Abort if**: $s$ is not representable as u64; or `manifest_fingerprint_bytes` is not 32 bytes; or tags are altered (the tags are normative constants).

---

## Byte combinators used (from S0.2.1)

* $\mathrm{LE64}(s)$ — 8-byte **little-endian** encoding of the u64 $s$.
* Concatenation $x\|\!y$ — **raw bytes** append (no hex, no delimiters).
* $\mathrm{split64}(b_0{:}16)$ — interpret the first 16 bytes as two u64s in **little-endian** order, returning $(u_0,u_1)$.
* $\mathrm{SHA256}(\cdot)$ — 32-byte digest (raw).

---

## Constructions (exact recipes)

### A) Master Philox key $S_{\text{master}}$ (u64)

$$
\boxed{\quad
S_{\text{master}} \;=\; \mathrm{LE64}\!\Big(\ \mathrm{SHA256}\big(t_{\text{seed}} \ \|\ \mathrm{LE64}(s) \ \|\ \text{manifest_fingerprint_bytes}\big)\ [0{:}8]\ \Big)\ .
\quad}
$$

* Compute the SHA-256 of the **concatenation** in that exact order.
* Take the **first 8 bytes** of the digest (offset 0..7) and **decode** as u64 by **little-endian**.
* No rejection or masking: every 8-byte pattern is valid; Philox accepts any 64-bit key.

### B) Initial counter $C_0=(c_{\mathrm{hi}},c_{\mathrm{lo}})$ (two u64)

$$
\boxed{\quad
(c_{\mathrm{hi}},c_{\mathrm{lo}}) \;=\; \mathrm{split64}\!\Big(\ \mathrm{SHA256}\big(t_{\text{ctr}} \ \|\ \text{manifest_fingerprint_bytes} \ \|\ \mathrm{LE64}(s)\big)\ [0{:}16]\ \Big)\ .
\quad}
$$

* Compute SHA-256 of the **different, domain-separated** concatenation (note the **tag** and the **argument order** differ from the seed construction).
* Take the **first 16 bytes** and split into two u64s by **little-endian**:

  * bytes 0..7 → $c_{\mathrm{hi}}$,
  * bytes 8..15 → $c_{\mathrm{lo}}$.
* This yields a full 128-bit starting counter. (No requirement that either word be non-zero.)

**Why different tags *and* different argument order?**
This ensures **PRF-like separation** of the two derived values. Even if an adversary could pick $s$ and the fingerprint, the chance that seed and counter collide under some unintended algebraic relation is negligible; the two SHA-256 inputs are unrelated except via shared bytes.

---

## Properties and invariants

* **I-SC1 (Determinism).** For fixed $(s,\text{manifest_fingerprint_bytes})$, the pair $(S_{\text{master}},C_0)$ is **bit-stable** across machines/OSes.
* **I-SC2 (Avalanche).** Flipping any bit of $s$ or the fingerprint flips each output bit with probability $\approx \tfrac12$ (SHA-256 avalanche); effective collision probability is $\ll 2^{-64}$ for the seed and $\ll 2^{-128}$ for the counter pair.
* **I-SC3 (Domain separation).** Using distinct tags and argument orders prevents accidental equality $S_{\text{master}} = c_{\mathrm{lo}}$ (or similar) except with negligible probability.
* **I-SC4 (No draws yet).** $C_0$ is **not consumed** here; it is only **recorded**. First consumption happens in the first RNG event of S1 (or whichever state draws first).
* **I-SC5 (Audit before use).** An audit row **must** be written before any draw (see “Audit emission” below).

---

## Failure semantics (abort conditions)

* `bad_run_seed`: input $s$ outside u64 range or non-integer type.
* `bad_manifest_bytes`: fingerprint buffer not exactly 32 bytes.
* `tag_mutation`: the tag bytes differ from the normative ASCII constants (configuration corruption).
  All failures are **hard** and abort S0.3.

---

## Audit emission (required output of S0.3.2)

Before **any** RNG consumption, write one row to `rng_audit_log` with (at minimum):

```
{ ts_utc,
  run_id,
  seed = S_master,                       # u64
  parameter_hash,                        # hex64
  manifest_fingerprint,                  # hex64
  module = "1A.rng.bootstrap",
  substream_label = "rng_audit_log",
  rng_counter_before_hi = c_hi,          # equals c_hi
  rng_counter_before_lo = c_lo,          # equals c_lo
  rng_counter_after_hi  = c_hi,          # no draws yet -> before==after
  rng_counter_after_lo  = c_lo }
```

* **Counters do not advance** here (`before == after`), establishing the **ground truth** starting point used by S9 to verify all later counter advances.

---

## Minimal reference algorithm (language-agnostic)

```
INPUT:
  s : u64
  mf_bytes : 32-byte buffer (manifest_fingerprint_bytes)

CONSTANTS:
  T_SEED = ASCII bytes("seed:1A")
  T_CTR  = ASCII bytes("ctr:1A")

OUTPUT:
  S_master : u64
  (c_hi, c_lo) : (u64, u64)

# seed
buf_seed := sha256( T_SEED || LE64(s) || mf_bytes )      # 32 bytes
S_master := LE64_to_u64( buf_seed[0:8] )

# counter
buf_ctr  := sha256( T_CTR  || mf_bytes || LE64(s) )      # 32 bytes
c_hi     := LE64_to_u64( buf_ctr[0:8] )
c_lo     := LE64_to_u64( buf_ctr[8:16] )

# audit row (before any draws)
emit_rng_audit_log(S_master, c_hi, c_lo, parameter_hash, manifest_fingerprint, ...)

return S_master, (c_hi, c_lo)
```

---

## Notes for implementers

* Treat all concatenations as **raw bytes**; do **not** hex-encode intermediate digests/fields.
* The **little-endian** interpretation is normative; do not switch to big-endian.
* Store `manifest_fingerprint` and `parameter_hash` on the audit row as **hex strings** (64 lowercase hex chars), but feed **raw 32-byte** `manifest_fingerprint_bytes` into the SHA-256 recipes above.
* The first producer that actually **consumes** RNG (e.g., the S1 hurdle) must log `rng_counter_before_*` equal to $(c_{\mathrm{hi}},c_{\mathrm{lo}})$ from the audit row, enabling end-to-end counter accounting.

---

# S0.3.3 — Sub-stream labelling (jump discipline)

## Purpose

Give every logical RNG **event label** $\ell$ (e.g., `"hurdle_bernoulli"`, `"gamma_component"`, `"poisson_component"`, `"gumbel_key"`, `"dirichlet_gamma_vector"`, `"residual_rank"`, `"sequence_finalize"`, `"ztp_*"`) a **deterministic jump** in the Philox counter so that events from different labels occupy (practically) disjoint regions of the $2^{128}$ counter space, while keeping draw accounting exact via the common envelope. Labels and event streams are catalogued in the dataset dictionary and share the layer-wide RNG envelope schema.

---

## Label domain and encoding

* Label set $\mathcal{L}$: finite set of canonical **ASCII** strings used in the RNG event streams and in the `substream_label` envelope field (case-sensitive; no normalization; no trailing NUL). Examples above are **illustrative**, not exhaustive; the registry enumerates the authoritative set.
* When an event is emitted, its `substream_label` **must exactly** equal the $\ell$ used to compute the jump for that event; validators rely on this. Envelope fields are mandated by `schemas.layer1.yaml#/$defs/rng_envelope`.

---

## Stride derivation $J(\ell)$ (exact bytes)

Let $\mathrm{SHA256}(\ell)\in\mathbb{B}^{256}$ be the digest of the ASCII bytes of the label (no terminator). Define the **64-bit** stride

$$
\boxed{\ J(\ell)\;=\;\mathrm{LE64}\!\big(\mathrm{SHA256}(\ell)[0{:}8]\big)\ \in\ \{0,\dots,2^{64}\!-\!1\}\ }.
$$

That is: take the **first 8 bytes** of the 32-byte digest and decode them little-endian to an unsigned 64-bit integer. (No rejection if $J(\ell)=0$; it is allowed but astronomically rare that two labels share the same 8-byte prefix.)

**Determinism:** for a fixed $\ell$, $J(\ell)$ is bit-stable across machines/OSes.

---

## Jump update (mod $2^{128}$) before each labelled event

Let the current Philox counter be $C=(c_{\mathrm{hi}},c_{\mathrm{lo}})\in\{0,\dots,2^{64}\!-\!1\}^2$.
**Before consuming uniforms for an event with label $\ell$**, compute the **jumped** counter

$$
\boxed{\ (c'_{\mathrm{hi}},c'_{\mathrm{lo}})\;=\;\big(c_{\mathrm{hi}}\ +\ \mathbf{1}\{c_{\mathrm{lo}}+J(\ell)\ \ge\ 2^{64}\},\ \ (c_{\mathrm{lo}}+J(\ell))\bmod 2^{64}\big)\ },
$$

i.e., add $J(\ell)$ to the **low** word with 64-bit carry into the high word. Then **start** the event’s draws at $C'=(c'_{\mathrm{hi}},c'_{\mathrm{lo}})$.

* The **jump** itself is **not** counted as “draws.” It is recorded in a separate `stream_jump` event (see below), so the event’s envelope still satisfies the counter-conservation rule “after = advance(before, ⌈draws/2⌉)”.
* **No stride duplication in payloads:** event payloads never carry $J(\ell)$; only the `substream_label` declares the label used to compute the jump.

---

## Logging & accounting artefacts

1. **RNG envelope (every event):**
   `ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_{lo,hi}, rng_counter_after_{lo,hi}`. Validators assert open-interval uniforms and strict counter conservation per event.

2. **`stream_jump` events (one per labelled event):**
   Explicitly logs the jump from $C$ to $C'$ with the label $\ell$. Path & schema are fixed in the dictionary (`logs/rng/events/stream_jump/…`). These records let S9 **separate** address-space re-positioning from block consumption when auditing counters.

3. **`rng_trace_log` (roll-up):**
   Aggregated per-label/per-module draw accounting and jump offsets (by run/seed/parameter_hash). Used by validators to check that the sum of event draws implies the total block advance observed.

---

## Invariants

* **I-L1 (label determinism).** Given $\ell$, the stride $J(\ell)$ is fixed; different labels are overwhelmingly likely to have different strides.
* **I-L2 (event conservation).** For an event needing $d$ uniforms, with block count $B=\lceil d/2\rceil$, the envelope must satisfy

  $$
  \text{after} \;=\; \mathrm{advance}(\text{before},\,B),
  $$

  **independent** of the jump; the jump is evidenced by the paired `stream_jump` record that sets `before`.
* **I-L3 (sub-stream monotonicity).** Within the **same** label, the sequence of event `before` counters is strictly increasing **in the emitted order** because each event begins at the previous event’s `after` plus a non-negative stride $J(\ell)$ (wrap to 0 across $2^{128}$ is practically unreachable under any realistic draw budget).
* **I-L4 (cross-label isolation, practical).** Because label jumps are SHA-256 derived and the counter space is $2^{128}$, the probability that two labels’ event ranges overlap **exactly** at a block boundary within our total block budget is negligible; if ever detected, it is treated as a fatal audit failure.

---

## Failure semantics (hard abort)

* `bad_label_encoding`: non-ASCII label or empty string encountered.
* `envelope_mismatch`: `substream_label` in envelope does not equal the label used to compute the jump.
* `trace_violation`: after $\neq$ advance(before, $B$) for any event (draws mis-counted).
* `missing_stream_jump`: a labelled event lacks a companion `stream_jump` record establishing its `before` counter.

---

## Minimal reference algorithm (numbered, language-agnostic)

**Inputs:** current counter $C=(c_{\mathrm{hi}},c_{\mathrm{lo}})$; event label $\ell$; event needs $d$ uniforms; Philox key $S$.
**Outputs:** updated counter; two JSONL rows (one `stream_jump`, one event with envelope).

1. **Compute stride.**
   $h \leftarrow \mathrm{SHA256}(\text{ASCII}(\ell))$ (32 bytes).
   $J \leftarrow \mathrm{LE64}(h[0{:}8])$.

2. **Jump the counter.**
   $c'_{\mathrm{lo}} \leftarrow (c_{\mathrm{lo}}+J) \bmod 2^{64}$.
   $c'_{\mathrm{hi}} \leftarrow c_{\mathrm{hi}} + \mathbf{1}\{c_{\mathrm{lo}}+J \ge 2^{64}\}$.
   $C' \leftarrow (c'_{\mathrm{hi}}, c'_{\mathrm{lo}})$.

3. **Emit `stream_jump`.**
   JSONL with the RNG envelope where `rng_counter_before_* = C`, `rng_counter_after_* = C'`, `substream_label = \ell`, `module = <producer>`. (No `draws` counted here.)

4. **Prepare event draw accounting.**
   $B \leftarrow \lceil d/2\rceil$.
   Set event `before = C'`.

5. **Generate uniforms from Philox.**
   Evaluate $\Phi_S$ at counters $C',\ \mathrm{inc}(C'),\ \ldots,\ \mathrm{advance}(C',B-1)$; map each 64-bit word to $u\in(0,1)$ via the u01 rule (S0.3.1).

6. **Set event `after`.**
   $C'' \leftarrow \mathrm{advance}(C',B)$.
   Event envelope: `rng_counter_before_* = C'`, `rng_counter_after_* = C''`, `substream_label = \ell` (plus payload).

7. **Publish both records and update cursor.**
   Append the `stream_jump` row (step 3) and the event row (step 6).
   Set the global cursor $C \leftarrow C''$.

Steps (1)–(7) are repeated for **every** labelled event. The event’s **draws** equal $d$; `rng_trace_log` can roll up draw totals and confirm that the net counter advance equals $\sum \lceil d/2\rceil$ blocks across the run.



```css
INPUT:
  S_master : u64                              # Philox key
  C        : (u64 hi, u64 lo)                 # current 128-bit counter
  label    : ASCII string                     # substream label (e.g., "gumbel_key")
  d        : int >= 0                         # number of uniforms the event will consume
  ctx      : {ts_utc, run_id, parameter_hash, manifest_fingerprint, module}

OUTPUT:
  C_next   : (u64 hi, u64 lo)                 # updated counter after the event
  records  : [ stream_jump_row, event_row ]   # two JSONL rows (envelopes filled)
  U        : list<float> length d             # u01 uniforms for caller (optional)

# --- helpers ---
# inc(C) -> advance counter by 1 block (add 1 to low, carry to high)
# advance(C, B) -> apply inc(.) exactly B times
# phi_block(S, C) -> (z0, z1)  two 64-bit ints from Philox2x64-10 at counter C
# u01(z) = ((floor(z / 2^11) + 0.5) / 2^53)   # maps 64-bit int to open-interval (0,1)

1  assert is_ascii(label) and label != ""
2  h  := sha256(ASCII(label))                 # 32 bytes
3  J  := LE64(h[0:8])                         # 64-bit stride from first 8 bytes

# ---- jump BEFORE consuming any draws ----
4  C_before := C
5  lo' := (C.lo + J) mod 2^64
6  hi' := C.hi + ((C.lo + J) >= 2^64 ? 1 : 0)
7  C_jump := (hi', lo')                       # event will start here

# ---- emit stream_jump (no draws counted) ----
8  stream_jump_row := {
       ts_utc: ctx.ts_utc, run_id: ctx.run_id, module: ctx.module,
       seed: S_master, parameter_hash: ctx.parameter_hash,
       manifest_fingerprint: ctx.manifest_fingerprint,
       substream_label: label,
       rng_counter_before_hi: C_before.hi, rng_counter_before_lo: C_before.lo,
       rng_counter_after_hi:  C_jump.hi,   rng_counter_after_lo:  C_jump.lo
   }

# ---- consume d uniforms in blocks of 2 words per block ----
9  B := ceil(d / 2)                           # number of Philox blocks
10 U := []                                    # will hold d uniforms
11 for b in 0 .. B-1:
12     C_blk := advance(C_jump, b)
13     (z0, z1) := phi_block(S_master, C_blk)
14     if 2*b     < d: U.append( u01(z0) )
15     if 2*b + 1 < d: U.append( u01(z1) )

# ---- finalize event envelope ----
16 C_after := advance(C_jump, B)
17 event_row := {
       ts_utc: ctx.ts_utc, run_id: ctx.run_id, module: ctx.module,
       seed: S_master, parameter_hash: ctx.parameter_hash,
       manifest_fingerprint: ctx.manifest_fingerprint,
       substream_label: label,
       rng_counter_before_hi: C_jump.hi,   rng_counter_before_lo: C_jump.lo,
       rng_counter_after_hi:  C_after.hi,  rng_counter_after_lo:  C_after.lo,
       /* + event-specific payload fields built by the caller, which must imply d draws */
   }

# ---- return and advance global cursor ----
18 C_next := C_after
19 records := [stream_jump_row, event_row]
20 return (C_next, records, U)
```

notes:

* if `d == 0`, then `B == 0`, `C_after == C_jump`, and you still emit both rows (the jump is separate from draw accounting).
* event payloads must be consistent with `d` (S9 checks `after = advance(before, ceil(d/2))` exactly).

---

## Where this shows up (paths/schemas)

* `logs/rng/events/<label>/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` for each event stream (e.g., `gumbel_key`, `dirichlet_gamma_vector`, etc.).
* `logs/rng/events/stream_jump/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` for the jump records.
* All event records use the shared envelope defined in `schemas.layer1.yaml` (u01, hex patterns, counters).

---

# S0.4 — Deterministic GDP bucket assignment

## Purpose

For each merchant $m$ with home ISO $c\in\mathcal{I}$, attach:

* the **GDP per-capita level** $g_c\in\mathbb{R}_{>0}$ from the pinned **2025-04-15** WDI vintage, and
* the **Jenks bucket id** $b_m:=B(c)\in\{1,2,3,4,5\}$ from the **frozen** mapping table (not recomputed online).

These are read-only lookups governed by authoritative ingress schemas and artefact dictionary entries.

---

## Inputs (read-only)

* `merchant_ids` (authoritative seed), columns `(merchant_id, mcc, channel, home_country_iso)`. `home_country_iso` must be ISO-2 and FK-valid.
* `world_bank_gdp_per_capita/2025-04-15` (flattened table) → supplies $G(c)$. Schema enforces non-null `gdp_pc_usd_2015` and uniqueness per `(country_iso, observation_year)`.
* `gdp_bucket_map_2024` (processed table) → supplies $B(c)\in\{1..5\}$. Primary key on `country_iso`, bucket in $[1..5]$, method=`"jenks"`, $K=5$.

---

## Outputs (to S0.5 and downstream)

For each merchant $m$ with home ISO $c$:

* $g_c$ — numeric GDP level used in the **NB dispersion** design (as $\log g_c$ in S0.5/S2).
* $b_m$ — categorical bucket used in the **hurdle** design (GDP dummies) and optionally logged for diagnostics.

(These may be persisted in a small feature cache, or carried transiently into S0.5. They are **not** parameter-scoped datasets themselves.)

---

## Deterministic definitions

Let $c=\texttt{home_country_iso}(m)\in\mathcal{I}$. Then:

$$
g_c \leftarrow G(c)\in\mathbb{R}_{>0},\qquad
b_m \leftarrow B(c)\in\{1,2,3,4,5\}.
$$

Here $G$ is the function induced by the **2025-04-15** WDI table and $B$ is the function induced by the **pinned** Jenks $K=5$ bucket map; both are immutable within a run and referenced by schema/dictionary.

---

## Invariants (must hold)

* **I-ISO.** $c$ must exist in the canonical ISO list; enforced via FK on `merchant_ids.home_country_iso`.
* **I-GDP.** There exists exactly one GDP value for $(c,\text{year}=2025\text{-}04\text{-}15\ \text{vintage})$; schema uniqueness covers year disambiguation. $g_c>0$.
* **I-Bucket.** Exactly one row in `gdp_bucket_map_2024` for `country_iso=c`; `bucket_id ∈ {1..5}`. $B$ is a **lookup table**, not recomputed.
* **I-Usage split.** The **bucket** $b_m$ is used **only** in the hurdle logistic; $\log g_c$ appears **only** in NB dispersion. (Design parsimony per assumptions.)

---

## Failure semantics (abort with diagnostics)

* `unknown_home_iso(m,c)`: $c\notin\mathcal{I}$ or FK fails.
* `missing_gdp_value(c)`: no GDP row for $c$ at the pinned vintage.
* `nonpositive_gdp(c, g_c)`: $g_c\le 0$ (schema guards this, but we assert).
* `missing_bucket_mapping(c)`: no `gdp_bucket_map_2024` row for $c$.
* `bucket_out_of_range(c, b)`: $b\notin\{1,\dots,5\}$ (schema guard).

Each abort should include `(merchant_id, c, offending_dataset, expected_pk)` to speed forensics.

---

## Minimal reference algorithm (numbered, language-agnostic)

```css
INPUT:
  merchant_ids               # table: (merchant_id, mcc, channel, home_country_iso)
  world_bank_gdp_2025_04_15  # table: (country_iso, observation_year, gdp_pc_usd_2015)
  gdp_bucket_map_2024        # table: (country_iso -> bucket_id in [1..5])

OUTPUT:
  features: list of records (merchant_id, home_country_iso, g_c, b_m)

1  iso_set := load_iso2_canonical()                            # from ingress schema ref
2  gdp     := index(world_bank_gdp_2025_04_15 by country_iso)  # single row per (iso,year)
3  buckets := index(gdp_bucket_map_2024 by country_iso)        # PK guarantees uniqueness

4  features := []
5  for each row r in merchant_ids:
6      m := r.merchant_id
7      c := r.home_country_iso
8      if c not in iso_set: abort("unknown_home_iso", m, c)

9      if c not in gdp:    abort("missing_gdp_value", c)
10     g_c := gdp[c].gdp_pc_usd_2015
11     if g_c <= 0:        abort("nonpositive_gdp", c, g_c)

12     if c not in buckets: abort("missing_bucket_mapping", c)
13     b   := buckets[c].bucket_id
14     if b < 1 or b > 5:  abort("bucket_out_of_range", c, b)

15     features.append({ merchant_id: m,
16                       home_country_iso: c,
17                       g_c: g_c,
18                       b_m: b })

19 return features
```

---

## Notes for implementers

* Treat both lookups as **pure reads** from artefacts pinned by the dictionary; never recompute Jenks online.
* If you cache outputs, scope any dataset to **`parameter_hash`** only if it depends on model params; here, simple feature caching is optional since the artefacts are ingress-scoped, not parameter-scoped.

---

# S0.5 — Design matrices (hurdle and NB)

## Purpose

Construct **deterministic, column-aligned design vectors** for each merchant $m$, to be used by:

* the **hurdle logistic** (single vs. multi-site) in S1, and
* the **NB branch** in S2 (mean and dispersion links).

Column order and encoders are **frozen** by the model-fitting bundle and validated against the schema/dictionary entries for the optional caches (`hurdle_design_matrix`, `hurdle_pi_probs`).

---

## Inputs (read-only; all from S0.\*)

* From **ingress**: for each $m$, $\texttt{mcc}_m\in\{0,\dots,9999\}$, $\texttt{channel}_m\in\{\text{CP},\text{CNP}\}$, $\texttt{home_country_iso}_m\in\mathcal{I}$. (Validated earlier.)
* From **S0.4**: GDP lookup $g_c=G(c)>0$ for home ISO $c$, and **Jenks bucket** $b_m=B(c)\in\{1,\dots,5\}$.
* From the **model-fitting bundle** (frozen):

  * One-hot **column dictionaries** that define the column **order** for MCC dummies, channel dummies, and GDP-bucket dummies.
  * Coefficients:

    * **Hurdle** coefficients $\beta$ in a **single YAML vector** (includes intercept, MCC, channel, and **all 5 GDP-bucket dummies**).
    * **NB dispersion** coefficients (contains the slope $\eta$ on $\log g_c$; $\eta>0$ at fit time). NB mean excludes GDP bucket by design.

(Design rule recapped in the S0 doc: GDP bucket used **only** in hurdle; $\log g_c$ used **only** in dispersion.)

---

## Encoders (column-frozen one-hots)

Let

$$
\phi_{\mathrm{mcc}}:\mathbb{N}\to\{0,1\}^{C_{\mathrm{mcc}}},\quad
\phi_{\mathrm{ch}}:\{\mathrm{CP},\mathrm{CNP}\}\to\{0,1\}^{2},\quad
\phi_{\mathrm{dev}}:\{1,\dots,5\}\to\{0,1\}^{5},
$$

be **deterministic** maps with exactly one “1” per input and columns ordered by the **fitting bundle dictionary** (not recomputed online). The **intercept** is a separate scalar $1$.

* Channel recoding is canonicalised to the event schema vocabulary when logged (`"card_present"`, `"card_not_present"`), but the encoder domain is $\{\mathrm{CP},\mathrm{CNP}\}$.

---

## Design vectors (definitions & dimensions)

Let $c$ be the home ISO for $m$, $g_c>0$, $b_m\in\{1,\dots,5\}$. Then:

### Hurdle (logit) design

$$
\boxed{\;x_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m),\ \phi_{\mathrm{dev}}(b_m)\big]^\top\;}\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}.
$$

Logit:

$$
\pi_m=\sigma(\beta^\top x_m),\qquad
\sigma(t)=\tfrac{1}{1+e^{-t}}.
$$

**All** hurdle coefficients (including GDP-bucket dummies) are stored **together** in `hurdle_coefficients.yaml` and loaded atomically.

### Negative-Binomial (used later in S2)

$$
\boxed{\;x^{(\mu)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m)\big]^\top\;}\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2},
$$

$$
\boxed{\;x^{(\phi)}_m=\big[1,\ \phi_{\mathrm{mcc}}(\texttt{mcc}_m),\ \phi_{\mathrm{ch}}(\texttt{channel}_m),\ \log g_c\big]^\top\;}\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+1}.
$$

**Design rule:** GDP bucket **excluded** from NB mean; $\log g_c$ **included** in dispersion with positive slope $\eta>0$.

---

## Numerical guard for $\sigma$ (overflow-safe)

Evaluate with branch-stable form:

$$
\sigma(\eta)=
\begin{cases}
\frac{1}{1+e^{-\eta}},& \eta\ge 0,\\[4pt]
\frac{e^\eta}{1+e^\eta},& \eta<0,
\end{cases}
$$

and (optionally) clip **only for display/logging** at $|\eta|>40$ to avoid NaNs; $\pi\in\{0,1\}$ at saturation.

---

## Invariants & validation

* **Column alignment.** The length of $\beta$ equals $\dim(x_m)$; MCC/channel/dev dummy **orders** match the frozen dictionaries. (Hurdle $\beta$ is a **single YAML vector**.)
* **One-hot correctness.** For each encoder, exactly one entry is 1; others 0.
* **GDP constraints.** $g_c>0$; $b_m\in\{1,\dots,5\}$ (from S0.4).
* **Scope split.** GDP bucket appears **only** in $x_m$; $\log g_c$ appears **only** in $x^{(\phi)}_m$. (Checked by design-matrix builder.)
* **Schema ties.** If persisted, `hurdle_design_matrix` and `hurdle_pi_probs` use the dictionary paths and schema refs in Layer-1 1A.

---

## Failure semantics (hard abort)

* `unknown_mcc(mcc)`: MCC not present in the fitting dictionary (should not happen if dictionary covers ingress).
* `unknown_channel(ch)`: channel not in {$\mathrm{CP},\mathrm{CNP}$}.
* `bucket_out_of_range(b)`: $b\notin\{1,\dots,5\}$.
* `nonpositive_gdp(g)`: $g\le 0$.
* `beta_length_mismatch`: $|\beta|\neq 1+C_{\mathrm{mcc}}+2+5$.
* `column_order_mismatch`: dictionary order differs from what the bundle declares.

Each abort surfaces the merchant id, offending field(s), and the dictionary digest used.

---

## Outputs (what S1/S2 will read)

* In-memory (or cached) per-merchant vectors $x_m$, $x^{(\mu)}_m$, $x^{(\phi)}_m$.
* Optional caches (parameter-scoped, per dictionary):

  * `hurdle_design_matrix/parameter_hash={parameter_hash}/…` (schema `schemas.1A.yaml#/model/hurdle_design_matrix`).
  * `hurdle_pi_probs/parameter_hash={parameter_hash}/…` (schema `schemas.1A.yaml#/model/hurdle_pi_probs`).

---

## Minimal reference algorithm (numbered, language-agnostic)

```css
INPUT:
  merchant_ids              # (merchant_id, mcc, channel, home_country_iso)
  gdp_map, bucket_map       # from S0.4: c -> g_c > 0, c -> b in {1..5}
  dicts:                    # frozen by fitting bundle
    mcc_cols[]              # ordered list of MCC keys
    ch_cols[]               # ["CP","CNP"] in fixed order
    dev_cols[]              # [1,2,3,4,5] in fixed order
  hurdle_beta               # single YAML vector for hurdle (includes dev dummies)

OUTPUT:
  per-merchant:
    x_m, x_mu_m, x_phi_m    # design vectors
    (optional) pi_m         # logistic probability for diagnostics cache

1  C_mcc := length(mcc_cols);  assert length(ch_cols)==2;  assert length(dev_cols)==5
2  assert length(hurdle_beta) == 1 + C_mcc + 2 + 5        # intercept + MCC + ch + dev

3  features := []
4  for each row r in merchant_ids:
5      m := r.merchant_id
6      c := r.home_country_iso
7      g := gdp_map[c];        if g <= 0: abort("nonpositive_gdp", c, g)
8      b := bucket_map[c];     if b not in {1..5}: abort("bucket_out_of_range", c, b)

9      # --- one-hot encoders (column order fixed by dicts) ---
10     oh_mcc := zero_vector(C_mcc)
11     idx_m  := index_of(r.mcc in mcc_cols);     if idx_m == NONE: abort("unknown_mcc", r.mcc)
12     oh_mcc[idx_m] := 1

13     oh_ch  := zero_vector(2)
14     idx_c  := index_of(r.channel in ch_cols);  if idx_c == NONE: abort("unknown_channel", r.channel)
15     oh_ch[idx_c] := 1

16     oh_dev := zero_vector(5)
17     idx_d  := index_of(b in dev_cols)          # dev_cols == [1,2,3,4,5]
18     oh_dev[idx_d] := 1

19     # --- assemble designs ---
20     x_m      := concat([1], oh_mcc, oh_ch, oh_dev)
21     x_mu_m   := concat([1], oh_mcc, oh_ch)
22     x_phi_m  := concat([1], oh_mcc, oh_ch, [log(g)])

23     # --- optional: compute hurdle probability for diagnostics ---
24     eta      := dot(hurdle_beta, x_m)
25     if eta >= 0: pi := 1.0 / (1.0 + exp(-eta))
26     else        : t  := exp(eta);  pi := t / (1.0 + t)      # overflow-safe branch

27     emit_optional_row_to("hurdle_design_matrix", m, x_m)        # schema/dictionary-controlled
28     emit_optional_row_to("hurdle_pi_probs", m, eta, pi)         # diagnostics table

29     features.append({merchant_id:m, x:x_m, x_mu:x_mu_m, x_phi:x_phi_m, pi:pi})

30 return features
```

---

### Where this is anchored in your docs

* The exact **design forms** and the **“bucket only in hurdle / log-GDP only in dispersion”** rule come straight from your narrative & assumptions.
* The **single YAML** for hurdle $\beta$ and the optional **π cache**/schemas are called out in the state/narrative and dictionary.
* Event schema vocabulary (for logging later in S1) fixes channel strings and u01 constraints.

---

# S0.6 Cross-border eligibility (deterministic gate)

### Inputs (authoritative)

* Merchant snapshot row $m\in\mathcal{M}$ with $(\texttt{merchant_id},\texttt{mcc},\texttt{channel},\texttt{home_country_iso})$ from `schemas.ingress.layer1.yaml#/merchant_ids`.
* Eligibility policy bundle **`crossborder_eligibility_rules.yaml`** (ruleset identifier/version lives here; tracked in the artefact registry).
* Partition/version lineage: `parameter_hash`, `manifest_fingerprint`.
* Output contract: `schemas.1A.yaml#/prep/crossborder_eligibility_flags` (columns: `manifest_fingerprint`, `merchant_id`, `is_eligible`, `reason`, `rule_set`), and dictionary path/partitioning by `{parameter_hash}`.

### Output (authoritative)

* One row per $m$:
  $(\texttt{merchant_id},\ \texttt{is_eligible}\in\{0,1\},\ \texttt{reason}\in\text{String or Enum},\ \texttt{rule_set},\ \texttt{manifest_fingerprint})$
  written to `data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/…` under the schema above.

---

### Domain and symbols

Let

$$
\mathcal{C}=\{\mathrm{CP},\mathrm{CNP}\},\qquad
\mathcal{I}=\text{ISO-3166 alpha-2 set},\qquad
\mathcal{K}=\text{valid 4-digit MCC codes}.
$$

A merchant $m$ maps to the triple

$$
t(m) := \big(\texttt{mcc}_m,\ \texttt{channel}_m,\ \texttt{home_country_iso}_m\big)\in \mathcal{K}\times\mathcal{C}\times\mathcal{I}.
$$

The policy file defines a **finite family of clauses** $\mathcal{R}=\{r_j\}_{j=1}^J$. Each clause $r_j$ is a tuple

$$
r_j=\big(S^{(j)}_{\!\mathrm{mcc}},\ S^{(j)}_{\!\mathrm{ch}},\ S^{(j)}_{\!\mathrm{iso}},\ d_j,\ \mathrm{id}_j\big),
$$

where $S^{(j)}_{\!\mathrm{mcc}}\subseteq\mathcal{K}$ (sets and/or disjoint ranges),
$S^{(j)}_{\!\mathrm{ch}}\subseteq\mathcal{C}$,
$S^{(j)}_{\!\mathrm{iso}}\subseteq\mathcal{I}$,
and $d_j\in\{\textsf{allow},\textsf{deny}\}$.
`id_j` is a stable string label for provenance in `reason`.
(The registry explicitly tracks this rule bundle as the source of the flags. )

Define the **set semantics** of a clause:

$$
\lbrack\!\lbrack r_j\rbrack\!\rbrack := S^{(j)}_{\!\mathrm{mcc}}\times S^{(j)}_{\!\mathrm{ch}}\times S^{(j)}_{\!\mathrm{iso}}\ \subseteq\ \mathcal{K}\times\mathcal{C}\times\mathcal{I}.
$$

Partition the family by decision:

$$
\mathcal{R}_{\textsf{allow}}=\{r_j:d_j=\textsf{allow}\},\qquad
\mathcal{R}_{\textsf{deny}}=\{r_j:d_j=\textsf{deny}\}.
$$

Aggregate **coverage sets**:

$$
E_{\textsf{allow}}:=\bigcup_{r\in\mathcal{R}_{\textsf{allow}}}\lbrack\!\lbrack r\rbrack\!\rbrack,\qquad
E_{\textsf{deny}} :=\bigcup_{r\in\mathcal{R}_{\textsf{deny}}}\lbrack\!\lbrack r\rbrack\!\rbrack.
$$

### Policy (default-deny with deny-overrides-allow)

Adopt conservative semantics (fits gating intent and compliance defensibility):

$$
\boxed{\ E := E_{\textsf{allow}}\setminus E_{\textsf{deny}}\ },\qquad
\boxed{\ \text{elig}_m = \mathbf{1}\{\,t(m)\in E\,\}\ }.
$$

Equivalently, $ \text{elig}_m=1$ iff $t(m)$ is covered by **at least one** allow clause and **no** deny clause; otherwise $ \text{elig}_m=0$.
(These semantics align with the dataset’s purpose as a *pre-ZTP enforcement* and the registry’s explicit “rules determine which merchants attempt cross-border expansion”.)

### Provenance fields

Let `rule_set` be the versioned identifier of the loaded policy file (e.g., a semver or config hash). Each output row carries this `rule_set` and the run’s `manifest_fingerprint` for lineage, as required by the schema. Reasons are emitted as deterministic strings:

$$
\text{reason}_m=\begin{cases}
\text{"allow:"}\!+\!\min\{\mathrm{id}_j: t(m)\in\lbrack\!\lbrack r_j\rbrack\!\rbrack,\, d_j=\textsf{allow}\}, & \text{if }\text{elig}_m=1;\\[4pt]
\text{"deny:"}\!+\!\min\{\mathrm{id}_j: t(m)\in\lbrack\!\lbrack r_j\rbrack\!\rbrack,\, d_j=\textsf{deny}\}, & \text{if }t(m)\in E_{\textsf{deny}};\\[4pt]
\text{"deny:default_no_rule"}, & \text{otherwise (default-deny)}.
\end{cases}
$$

(The schema’s `reason` is nullable; you may choose to populate it only for the negative branch, but carrying a deterministic code for both branches eases audits.)

### Invariants and properties

1. **Determinism / RNG-free.** No randomness enters; output depends only on $t(m)$ and the policy artefact (therefore partitions by `{parameter_hash}` as specified).
2. **Monotonicity.** Adding a deny clause never increases eligibility; adding an allow clause never decreases it **unless** it also introduces overlapping deny coverage (deny wins).
3. **Idempotence.** Re-applying the rules does not change results: a pure function of $t(m)$.
4. **Completeness of lineage.** Every row **must** include `manifest_fingerprint` and `rule_set` (schema-enforced), and the dataset **must** be partitioned by `{parameter_hash}` (dictionary-enforced).

---

### Reference algorithm (minimal, deterministic)

```text
INPUT: merchants M, ruleset R = {r_j}, parameter_hash, manifest_fingerprint, rule_set_id
OUTPUT: crossborder_eligibility_flags rows

1  # Pre-normalise rules:
2  # Expand each r_j into explicit (MCC-set, channel-set, ISO-set, decision, id_j)
3  # Ensure sets are finite and disjointable; no regex/wildcards at this point.

4  for each merchant m in M:
5      t := (m.mcc, m.channel, m.home_country_iso)
6      allow_hits := { id_j : t ∈ ⟦r_j⟧ and r_j.decision = ALLOW }
7      deny_hits  := { id_j : t ∈ ⟦r_j⟧ and r_j.decision = DENY }
8      is_eligible := (|allow_hits| > 0) and (|deny_hits| = 0)
9      reason :=
10         if is_eligible then
11             ("allow:" + min_lex(allow_hits))
12         else if |deny_hits| > 0 then
13             ("deny:" + min_lex(deny_hits))
14         else
15             "deny:default_no_rule"
16      emit row:
17         (manifest_fingerprint, m.merchant_id, is_eligible, reason, rule_set = rule_set_id)
18
19 # Persist to:
20 # data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/...
# Schema: schemas.1A.yaml#/prep/crossborder_eligibility_flags
```

---

# S0.7 — Optional diagnostic cache (hurdle $\pi$)

## Purpose

Materialize a **read-only** cache of the hurdle logistic outputs for each merchant,

$$
(\texttt{merchant_id},\ \eta_m,\ \pi_m),
\qquad
\eta_m:=\beta^\top x_m,\ \ \pi_m:=\sigma(\eta_m),
$$

to the dataset **`hurdle_pi_probs/parameter_hash={parameter_hash}/…`** with schema `schemas.1A.yaml#/model/hurdle_pi_probs`. This artefact is **never consulted during sampling**; it exists solely for diagnostics/validation and lineage.

## Inputs (deterministic)

* **Design vector** $x_m$ built in S0.5 (intercept + MCC + channel + GDP-bucket one-hots).
* **Hurdle coefficients** $\beta$ (single YAML vector; loaded atomically).
* **Lineage keys:** `parameter_hash` (partitions this cache) and `manifest_fingerprint` (embedded per row). Dictionary fixes path and partitioning.

## Output (schema & typing)

A Parquet table with:

* **Primary key:** `merchant_id`. **Partition key:** `parameter_hash`.
* **Columns:**
  `manifest_fingerprint` (hex64), `merchant_id` (id64), `logit` (float32), `pi` (pct01).

The dictionary declares the dataset as **model** artefact, produced by `1A.fit_hurdle_model`, retained 365 days, and **not final** in layer 1A.

## Deterministic definitions & numerical policy

* **Linear predictor.** $\eta_m=\beta^\top x_m$ with **column order** exactly matching the fitting bundle used for $\beta$ (S0.5).

* **Logistic link (overflow-safe).**

  $$
  \sigma(\eta)=
  \begin{cases}
  \dfrac{1}{1+e^{-\eta}},& \eta\ge 0,\\[6pt]
  \dfrac{e^\eta}{1+e^\eta},& \eta<0,
  \end{cases}
  \quad\Rightarrow\quad
  \pi_m=\sigma(\eta_m)\in(0,1).
  $$

  For persistence, store `pi` as **float32** and accept $[0,1]$ as per `pct01` (hard saturation at $|\eta| \gg 1$ may round to exactly 0 or 1; this satisfies the schema).

* **Precision discipline.** Compute $\eta_m,\pi_m$ in binary64, then round to the schema’s `float32` on write; this avoids avoidable drift across platforms while meeting the column type. (Schema for `pi` uses `pct01` in $[0,1]$.)

## Invariants (must hold)

1. **One row per merchant:**
   $\big|\texttt{hurdle_pi_probs}\big|=\big|\mathcal{M}\big|$, keyed by `merchant_id`.
2. **Lineage presence:**
   Every row has `manifest_fingerprint` equal to the run fingerprint; partition directory equals the run’s `parameter_hash`.
3. **Shape/ordering consistency:**
   $|\beta|=\dim(x_m)$; MCC, channel, GDP-bucket dummy **orders** match the frozen dictionaries from the fitting bundle (S0.5).
4. **Range checks:**
   `pi ∈ [0,1]` (schema `pct01`), `logit` finite (no NaN/Inf).
5. **Read-only contract:**
   Declared as diagnostic; **never read** by the sampler (reinforced by dictionary lineage and the narrative).

## Failure semantics (abort)

* `beta_length_mismatch` or `column_order_mismatch` (design vs. coefficients).
* `nan_or_inf_logit` or `nan_pi` (numerical failure).
* `bad_lineage`: missing/incorrect `manifest_fingerprint` or wrong `parameter_hash` partition.
* `pk_violation`: duplicate `merchant_id` in output (should be impossible if inputs are unique).

## Minimal reference algorithm (supporting, not explanatory)

```
INPUT: merchants M, design x_m (from S0.5), beta, parameter_hash, manifest_fingerprint
OUTPUT: rows (merchant_id, logit, pi, manifest_fingerprint) -> hurdle_pi_probs

1  check length(beta) == dim(x_m) for a sentinel merchant; else abort
2  for each m in M:
3      eta := dot(beta, x_m[m])                 # binary64 compute
4      pi  := (eta >= 0) ? 1/(1+exp(-eta))      # overflow-safe σ
5                       : exp(eta)/(1+exp(eta))
6      write {manifest_fingerprint, merchant_id=m, logit=float32(eta), pi=float32(pi)}
7  persist under data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/...
```
---

# S0.8 — Numeric policy and determinism invariants

## S0.8.1 Numeric environment (authoritative)

We **fix** the arithmetic model to IEEE-754 **binary64** with *round-to-nearest, ties-to-even*; all scalars $x,y,\dots$ live in $\mathbb{F}_{64}$ (double precision). Two explicit controls are part of the artefact/runtime configuration and therefore fall under the **fingerprinted environment**:

1. **FMA policy (disabled where ordering matters).**
   For any expression of the form $a\cdot b + c$ used in computations that later influence **ordering** (e.g., residuals for largest-remainder), evaluate **as two rounded steps**:

   $$
   r_1 := \mathrm{round}_{64}(a\cdot b),\qquad
   s := \mathrm{round}_{64}(r_1 + c).
   $$

   No fused-multiply-add is permitted in these code paths. (This toggle is part of the artefact set and hence included in the run **manifest fingerprint**.)

2. **Deterministic reductions (no parallel non-associative sums).**
   Any sum over a finite sequence $x_1,\dots,x_n\in\mathbb{F}_{64}$ that affects **branching or ordering** is evaluated by a **serial left fold** in a fixed, documented key order:

   $$
   s_0:=0,\quad s_k:=\mathrm{round}_{64}(s_{k-1}+x_k)\ \ (k=1,\dots,n),
   $$

   where the iteration order is the lexicographic order of the dataset’s **primary key** (e.g., $(\texttt{merchant_id},\texttt{legal_country_iso})$ for per-merchant, per-country accumulations). No tree/pairwise/compensated or parallel reductions are used in these **ordering-sensitive** paths. (The policy is stated in S0 and carried into S1–S8; the validator replays with the same order.)

**Reproducibility note.** Because (i) FMA is disabled in sensitive paths, and (ii) reduction order is fixed, any compliant implementation produces **bit-identical** decisions (ranks, argmaxes, ties) across machines given the same `parameter_hash` and `manifest_fingerprint`.

---

## S0.8.2 RNG envelope invariants (must hold for **every** RNG event, states $>$ S0)

Every RNG JSONL event uses the **shared envelope** schema and must **include**:

$$
\{\texttt{ts_utc},\texttt{run_id},\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint},\texttt{module},\texttt{substream_label},\texttt{rng_counter_before_{lo,hi}},\texttt{rng_counter_after_{lo,hi}}\}.
$$

* `seed` is the master Philox u64; `parameter_hash` and `manifest_fingerprint` bind the event to its parameter bundle and run lineage.
* Counters satisfy **block conservation**:

  $$
  C_{\text{after}}=\mathrm{advance}\!\left(C_{\text{before}},\,\Big\lceil\frac{\texttt{draws}}{2}\Big\rceil\right),
  $$

  with `draws` implied by the payload and cross-checked by S9.
* Absence of any required field is a **structural failure** against `schemas.layer1.yaml#/$defs/rng_envelope`.

---

## S0.8.3 Partitioning invariants (dictionary-backed, audited)

Partitioning is **data-contracted**; the dataset dictionary enumerates which key drives each artefact’s path.

* **Parameter-scoped** artefacts must live under:

  $$
  \texttt{…/parameter_hash=\{parameter_hash\}/…}\quad\text{(and often } \texttt{seed}\text{ when per-seed)}.
  $$

  Examples:
  `crossborder_eligibility_flags( parameter_hash )`,
  `hurdle_pi_probs( parameter_hash )`,
  `country_set( seed, parameter_hash )`,
  `ranking_residual_cache( seed, parameter_hash )`.

* **Egress / validation** artefacts must live under:

  $$
  \texttt{…/fingerprint=\{manifest_fingerprint\}/…}\quad\text{(and often } \texttt{seed}\text{)}.
  $$

  Examples:
  `outlet_catalogue( seed, fingerprint )`,
  `validation_bundle_1A( fingerprint )`,
  `_passed.flag( fingerprint )`.

The **paths** above are authoritative; validators assert the path template **and** the embedded columns (e.g., every Parquet row in `outlet_catalogue` carries the same `manifest_fingerprint` as the directory).

---

## S0.8.4 Determinism guarantees (what equality means)

For any two runs $R,R'$:

* If $\texttt{parameter_hash}(R)=\texttt{parameter_hash}(R')$ **and** $\texttt{manifest_fingerprint}(R)=\texttt{manifest_fingerprint}(R')$, then all **parameter-scoped** artefacts and all **egress/validation** artefacts are **bit-replayable** (identical schemas, values, and RNG traces), provided the numeric toggles match (which they must, as they’re part of the artefact set hashed into the fingerprint).

* If either key differs, reproducible divergence is **expected** and treated as a new lineage. (Dictionary and registry encode this expectation; consumers must use the partition keys when discovering data.)

---

## S0.8.5 What S0.8 enforces downstream

* **Numeric policy**: FMA-off and serial reductions for ordering-sensitive ops; binary64 throughout.
* **RNG envelope**: every event post-S0 is structurally validated against the shared schema; missing fields or counter-conservation failure is a **hard abort** in S9.
* **Partitioning**: writers must use the dictionary’s path templates; readers must treat `{parameter_hash}` vs `{fingerprint}` as **semantic** (parameter lineage vs run lineage).
---

# S0.9 — Failure modes (all abort)

Let the run context be fixed (`parameter_hash`, `manifest_fingerprint`, numeric/FMA toggles) and the authoritative schemas be those named by the **Schema Authority Policy**. Any violation below **aborts S0** (or the first state that can detect it) with a deterministic error code and a forensic payload (offending PKs, artefact id/path, sizes/mtimes, etc.).

---

## (F1) Ingress schema violation (merchant_ids)

**Predicate.**
`merchant_ids ⊄ schemas.ingress.layer1.yaml#/merchant_ids` (type, required fields, PK uniqueness, ISO-2 pattern) ⟺ **FAIL**.

Formally, for some row $r=(m,\mathrm{mcc},\mathrm{ch},c)$:

* $m$ not an `id64`; or
* $\mathrm{mcc}$ not a valid 4-digit code; or
* $\mathrm{ch}\notin\{\mathrm{CP},\mathrm{CNP}\}$; or
* $c$ not matching `^[A-Z]{2}$` or not in the canonical ISO table; or
* duplicate $m$.

**Detection.** JSON-Schema validation against the ingress ref in the **dictionary** (the dictionary pins the schema and the path).

**Error.** `ingress_schema_violation(merchant_ids, row_pk=…)`.

---

## (F2) Missing artefact or digest/fingerprint formation failure

Covers S0.2 hashing & lineage.

### (F2a) Parameters (S0.2.2)

Missing/duplicate/unreadable file in $\mathcal{F}=${`crossborder_hyperparams.yaml`, `hurdle_coefficients.yaml`, `nb_dispersion_coefficients.yaml`} ⟺ **FAIL**.
Guard also fires on **instability during hash** (size/mtime changed), **bad hex64**, or any non-regular file.

**Error.** `missing_parameter_file(f) | duplicate_parameter_file(f) | unreadable_parameter_file(f) | changed_during_hash(f) | bad_hex_encoding`.

### (F2b) Manifest fingerprint (S0.2.3)

* **Empty artefact set** $\mathcal{A}=\varnothing$; or
* **git hash** not 20 or 32 bytes before padding to `git32`; or
* any artefact in $\mathcal{A}$ unreadable/not regular; or
* **bad hex64** on persistence. ⟺ **FAIL**.

**Error.** `empty_artefact_set | git_hash_bad_length | artefact_missing(path) | not_regular_file(path) | bad_hex_encoding`.

*(Both (F2a) and (F2b) are part of the lineage contract that later drives partitioning of parameter-scoped vs egress/validation artefacts.)*

---

## (F3) Non-finite / out-of-domain feature or model outputs

### (F3a) GDP & bucket (S0.4)

* $g_c\notin\mathbb{R}_{>0}$ (NaN/Inf/≤0) ⟺ **FAIL**.
* $b_m\notin\{1,2,3,4,5\}$ ⟺ **FAIL**.
  (These are pure lookups from pinned artefacts; violations indicate bad upstream rows or wrong joins.)

**Error.** `nonpositive_gdp(c, g_c) | bucket_out_of_range(c, b)`.

### (F3b) Hurdle logit/probability (S0.5/S0.7)

* $\eta_m=\beta^\top x_m$ not finite; or
* $\pi_m=\sigma(\eta_m)$ is NaN (implementation bug—overflow-safe form prevents this). ⟺ **FAIL**.
  Schema for the optional cache requires `logit` finite and `pi ∈ [0,1]`.

**Error.** `nan_or_inf_logit(m) | nan_pi(m)`.

---

## (F4) RNG audit/envelope violations

### (F4a) Audit not written before first draw

If **any** RNG event exists but no `rng_audit_log` row for the run (`seed, parameter_hash, run_id`) has been written ⟺ **FAIL**. The dictionary mandates the audit log path & schema.

**Error.** `missing_rng_audit_log(run_id, seed, parameter_hash)`.

### (F4b) Envelope structural failure (any event)

Missing any required envelope field:
$\{\texttt{ts_utc},\texttt{run_id},\texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint},\texttt{module},\texttt{substream_label},\texttt{rng_counter_before_{lo,hi}},\texttt{rng_counter_after_{lo,hi}}\}$
or type/pattern mismatch (e.g., non-hex64), ⟺ **FAIL** against the shared schema.

**Error.** `rng_envelope_schema_violation(label, event_id)`.

### (F4c) Counter conservation failure

For an event with `draws = d`,

$$
C_{\text{after}}\ne \mathrm{advance}\!\left(C_{\text{before}},\ \left\lceil \frac{d}{2}\right\rceil\right)\ \ \Rightarrow\ \ \textbf{FAIL}.
$$

Detected by the **rng trace** validator using the same dictionary/schema.

**Error.** `rng_counter_mismatch(label, before, after, draws)`.

---

## (F5) Partitioning/lineage mismatch (schema + dictionary)

Any dataset written under a **wrong partition key** or with **embedded lineage** not equal to the directory key ⟺ **FAIL**. Examples:

* Parameter-scoped outputs (e.g., `crossborder_eligibility_flags`, `hurdle_pi_probs`, `country_set`, `ranking_residual_cache`) **must** live under `…/parameter_hash={parameter_hash}/…` and rows must embed the **same** `parameter_hash`.
* Egress/validation (`outlet_catalogue`, `validation_bundle_1A`) **must** live under `…/fingerprint={manifest_fingerprint}/…` and rows/bundle index must embed the **same** `manifest_fingerprint`.

**Error.** `partition_mismatch(dataset_id, path_key, embedded_key)`.

---

## (F6) Schema authority breach

Referencing non-authoritative schemas (e.g., an `.avsc` for a 1A dataset) or drifting from the declared JSON-Schema refs in the **dictionary** ⟺ **FAIL** (build-time or validation-time).

**Error.** `non_authoritative_schema_ref(dataset_id, observed_ref)`.

---

### Where these guards are anchored

* **Schemas & envelope:** `schemas.ingress.layer1.yaml`, `schemas.1A.yaml`, and `schemas.layer1.yaml` (rng envelope + primitives inc. `hex64`, `u01`, `pct01`).
* **Dictionary paths/partitions:** canonical paths for every dataset (eligibility, design, caches, egress, validation, RNG logs).
* **Lineage recipes:** parameter hash & manifest fingerprint definitions in S0.2.\* (what to compute and how).
---

perfect — here’s **S0.10 — Outputs leaving S0 (deterministic state)**, tightened to the exact artefacts, types, and partitions the next states will rely on.

---

# S0.10 — Outputs leaving S0

For each $m\in\mathcal{M}$, S0 emits the following **deterministic** products and lineage keys.

## A) In-memory (or transient model-input artefact)

* **Design vectors** (column order frozen by the fitting bundle):

  * $x_m\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+5}$ (hurdle: intercept + MCC + channel + GDP-bucket dummies),
  * $x^{(\mu)}_m\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2}$ (NB mean),
  * $x^{(\phi)}_m\in\mathbb{R}^{1+C_{\mathrm{mcc}}+2+1}$ (NB dispersion, includes $\log g_c$).
* **Country features:** $b_m\in\{1,\dots,5\}$ (Jenks bucket), $g_c>0$ (GDP per-capita for home ISO).
  If materialised, these live under **`hurdle_design_matrix/parameter_hash={parameter_hash}/…`** with schema `schemas.1A.yaml#/model/hurdle_design_matrix`.

## B) Deterministic prep/caches (parameter-scoped)

* **Cross-border gate:** one row per merchant in
  **`crossborder_eligibility_flags/parameter_hash={parameter_hash}/…`**, schema `schemas.1A.yaml#/prep/crossborder_eligibility_flags`.
* **Optional diagnostics:** hurdle cache
  **`hurdle_pi_probs/parameter_hash={parameter_hash}/…`**, schema `schemas.1A.yaml#/model/hurdle_pi_probs` (never read by samplers).

> Partitioning is **by `{parameter_hash}`** for both datasets; this is dictionary-backed and audited.

## C) Run-level lineage + RNG bootstrap (persisted logs)

S0 finalises and records the keys that bind all subsequent RNG and egress:

* **`parameter_hash ∈ [a–f0–9]^{64}`** (concat-digest of parameter YAMLs) and
  **`manifest_fingerprint ∈ [a–f0–9]^{64}`** (XOR-reduce of artefacts ⊕ git ⊕ parameter hash), both carried in all downstream artefacts/events.
* **Master Philox seed** $S_{\text{master}}\in\{0,\dots,2^{64}-1\}$ and **initial counter** $(c_{\mathrm{hi}},c_{\mathrm{lo}})\in\{0,\dots,2^{64}-1\}^2$, written to the **RNG audit log** **before any draw**:
  `logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl`, schema `schemas.layer1.yaml#/rng/core/rng_audit_log`. Envelope fields (`seed`, `parameter_hash`, `manifest_fingerprint`, counters) are mandatory in all RNG JSONL.
* **RNG trace log** is opened (same partition keys) to enforce counter conservation in later states.

## D) What downstream states can assume

* The triplet $(\texttt{parameter_hash},\texttt{manifest_fingerprint},\texttt{seed}=S_{\text{master}})$ and initial $(c_{\mathrm{hi}},c_{\mathrm{lo}})$ are **already recorded** and immutable for the run; types follow `hex64`/`uint64` defs in the shared schema.
* Any consumer needing hurdle design or π may **optionally** read the caches above; samplers must not depend on them for correctness.
* Egress in later states (e.g., `outlet_catalogue`) will partition by `{seed,fingerprint}`; parameter-scoped intermediates continue under `{parameter_hash}`.