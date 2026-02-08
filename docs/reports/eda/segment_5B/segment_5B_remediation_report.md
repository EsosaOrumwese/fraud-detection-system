# Segment 5B Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 5B toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness
This section captures the observed statistical weaknesses in Segment 5B, prioritized by their effect on realism and downstream model behavior.

### 1.1 Primary weaknesses (material for realism)
1. **Systematic DST local-time defect (main realism weakness).**  
   Observed local-time mismatch rate is about `2.6%` (sample-based checks), with mismatches dominated by exact `-3600s` offsets and a very small `+3600s` tail.  
   Mismatches cluster around DST transition windows, especially the EU transition period.  
   - Why this is material: this is a structured timing bias, not random noise. It distorts hour-of-day feature realism for a meaningful subset of events and weakens explainability around time-sensitive behavior.
2. **High timezone concentration (global world skew).**  
   Timezone concentration is steep: top `5%` of timezones carry about `58.6%` of arrivals, and top `10%` carry about `81.3%`.  
   - Why this is material: global temporal behavior is dominated by a small timezone set. Downstream models can over-learn geography/timezone-specific rhythms rather than broadly realistic patterns.

### 1.2 Secondary weaknesses (constrain realism quality, but not hard blockers)
1. **Virtual routing share is low for rich online-behavior realism.**  
   Virtual arrivals are about `2.25%` of total arrivals.  
   - Why this matters: this is plausible for a physical-first world, but it limits online/CNP-like diversity if the intended synthetic world expects stronger digital behavior representation.
2. **Lean validation posture under-tests civil-time realism by default.**  
   Segment 5B validation uses sampled checks and relaxed civil-time/RNG gates in lean mode.  
   - Why this matters: defects like DST misalignment can still pass operational validation unless they are explicitly checked in statistical analysis.

### 1.3 Non-weaknesses (to avoid false diagnosis)
1. **S2/S3 duplicate-key anatomy is structural, not a bug.**  
   Multiple component rows per logical key are expected in current mechanics. After logical-key aggregation, count conservation is exact.
2. **Mass conservation and macro heavy-tail alignment are strong.**  
   Total S3 counts match total arrivals exactly, and merchant-level arrivals align almost perfectly with S2 intensity.
   - Why this matters: these are statistical strengths and should not be misclassified as remediation targets.

### 1.4 Section-1 interpretation
1. Segment 5B is statistically strong overall and can already support `B/B+` posture on most realism axes.
2. The main remediation priority is DST correctness in local-time rendering.
3. Secondary priorities are timezone concentration calibration (if broader global realism is required) and virtual-share tuning (if richer online behavior is required).
4. Because conservation and macro alignment already pass strongly, remediation should be focused and surgical rather than broad redesign.

## 2) Expected Statistical Posture (B/B+)

## 3) Root-Cause Trace

## 4) Remediation Options (Ranked + Tradeoffs)

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

## 6) Validation Tests + Thresholds

## 7) Expected Grade Lift (Local + Downstream Impact)
