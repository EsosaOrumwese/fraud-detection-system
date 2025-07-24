## Subsegment 2A: Deriving the civil time zone
### A.1 Run‑Length Encoding (RLE) of Transition Tables

**Purpose:** compress repeated offset values in the timetable.
**Code:** `timezone/cache.py:encode_rle`
**Artefact:** in‑memory Python bytes stored in the singleton `tz_cache`.

Given an array of length‑$n$ offsets in minutes

$$
V = [v_1, v_2, \dots, v_n],\quad v_i\in\mathbb{Z}\ \text{(minutes)}
$$

define runs $\{(c_j,\ell_j)\}_{j=1}^m$ where

$$
k_1 = 1,\quad k_{j+1} = k_j + \ell_j,
$$

$$
c_j = v_{k_j},\quad
\ell_j = \max\{\,r\ge1 : v_{k_j+r-1}=v_{k_j}\}
$$

Store two arrays:

$$
C = [c_1,\dots,c_m]\quad(\mathrm{int16}),\quad
L = [\ell_1,\dots,\ell_m]\quad(\mathrm{int32}).
$$

**Example:**

$$
V=[0,0,0,60,60,120,120,120]\;\longrightarrow\;
C=[0,60,120],\;L=[3,2,3].
$$

---

### A.2 Simulation Horizon Conversion & Truncation

**Files:**

* `config/timezone/simulation_horizon.yml`
  (fields `sim_start_iso8601`, `sim_end_iso8601`, `semver`, `sha256_digest`)
* Manifest key: `tz_horizon_digest`

Parse ISO 8601 bounds to integer seconds:

$$
s = \bigl\lfloor\mathrm{parseISO}(\mathtt{sim\_start\_iso8601})\times10^3\bigr\rfloor,
\quad
e = \bigl\lfloor\mathrm{parseISO}(\mathtt{sim\_end\_iso8601})\times10^3\bigr\rfloor
$$

($\mathrm{parseISO}$ returns seconds since epoch).
Given full transition list $\{t_i\}$ (int64 seconds), truncate:

$$
T = \{\,t_i : s \le t_i \le e\}.
$$

These $T$ feed into RLE (A.1).

---

### A.3 Forward‑Gap Duration $\Delta$

**Code:** `timezone/local_time.py:compute_gap`
**Definition:**
For each DST transition index $i$, let

$$
o_i,\;o_{i+1}\in\mathbb{Z}\quad(\text{minutes}),
$$

then

$$
\Delta = (o_{i+1} - o_i)\times60
\quad(\text{seconds}).
$$

**Stored as:** `gap_seconds` (int64).
**Example:** $o_i=120$, $o_{i+1}=180$ min ⇒ $\Delta=(180-120)\times60=3600$ s (1 h).

---

### A.4 Local‑to‑UTC Conversion & Gap Adjustment

**Code:**

* `timezone/local_time.py:to_utc`
* `timezone/local_time.py:adjust_gap`

Given local epoch second $t_{\mathrm{local}}$ and offset $o_i$ (minutes):

1. **Naïve UTC**

   $$
     t_{\mathrm{utc}} = t_{\mathrm{local}} - 60\,o_i
     \quad(\text{seconds})
   $$

2. **Forward‑Gap Case** ($t_i < t_{\mathrm{local}} < t_i+\Delta$):

   $$
     t_{\mathrm{utc}} = t_i + \Delta,\quad
     \mathrm{dst\_adjusted} = 1,\quad
     \mathrm{gap\_seconds} = (t_i + \Delta) - t_{\mathrm{local}}.
   $$

3. **Fall‑Back Fold Case** (disambiguation in A.5).

---

### A.5 Fall‑Back Fold‑Bit Hashing

**Code:** `timezone/local_time.py:determine_fold`
**Artefacts:**

* `manifest.json` → `global_seed` (128‑bit hex)
* `docs/rng_proof.md` → `rng_proof_digest`

Let
$\mathtt{seed}\in\{0,1\}^{128}$,
$\mathtt{site\_id}\in\text{UTF-8 bytes of zero‑padded ID}$,
$t_{\mathrm{local}}\in\mathbb{Z}$ ($\mathrm{ms}$ since epoch).
Concatenate big‑endian bytes:

$$
B = \mathtt{seed}\,\|\,\mathtt{site\_id}\,\|\,\mathrm{BE}_{8}(t_{\mathrm{local}}).
$$

Compute

$$
h = \mathrm{SHA256}(B)\in\{0..255\}^{32},\quad
\mathrm{fold} = h[0]\bmod2\in\{0,1\}.
$$

**Example:** If $h[0]=0x8A=138$, then $\mathrm{fold}=0$.

---

### A.6 Event Time Storage in Parquet

**Schema:**

```yaml
event_time_utc:
  type: INT64
  logicalType: TIMESTAMP_MILLIS
```

**Computation:**

$$
\mathrm{event\_time\_utc}
=\bigl\lfloor (t_{\mathrm{local}} - 60\,o)\times10^3\bigr\rfloor
\quad(\text{milliseconds since epoch}).
$$

Sub-millisecond fractions are truncated.

---

### A.7 Memory Gauge & Cache Limit

**Code:** `timezone/cache.py:gauge_memory`
**Manifest Field:** `tz_cache_bytes` (int64)
**CI Rule:**

$$
\mathrm{tz\_cache\_bytes} = \mathrm{sizeof}(tz\_cache)\quad(\text{bytes}),
\qquad
\text{assert }\mathrm{tz\_cache\_bytes}<8\times2^{20}.
$$

If violated, raise `TimeTableCoverageError`.

---

### A.8 Exception Types & Atomic Rollback

| Exception                | Trigger                                      | Effect                       |
| ------------------------ | -------------------------------------------- | ---------------------------- |
| `TimeZoneLookupError`    | no polygon contains point                    | abort build, no rows written |
| `DSTLookupTieError`      | two polygons after nudge                     | abort build, no rows written |
| `TimeTableCoverageError` | cache limit breach or access outside `[s,e]` | abort build, no rows written |

On any exception, clean up `*.parquet.tmp`, flush audit logs, and exit atomically.
