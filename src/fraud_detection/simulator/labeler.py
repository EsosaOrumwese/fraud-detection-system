"""
External fraud‐labeler: logistic model + burst clustering.

Keeps core.py lean by isolating all label logic here.
Uses NumPy + Polars with no pandas detours.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import polars as pl
from numpy.random import default_rng
from scipy.special import expit  # type: ignore

def label_fraud(
    df: pl.DataFrame,
    fraud_rate: float,
    *,
    seed: Optional[int] = None,
    # Logistic weights
    w_amount: float = 0.8,
    w_mrisk: float   = 2.0,
    w_crisk: float   = 1.5,
    w_night: float   = 0.5,
    # Burst parameters
    burst_factor: int = 10,
    burst_window_s: int = 1800,
) -> pl.DataFrame:
    """
    Vectorized fraud labeling:
      1) Compute per‐txn logistic p via amount, merch_risk, card_risk, hour.
      2) Bernoulli draw clamped to exact fraud_rate via overshoot/undershoot bursts.
    """
    N = df.height
    # Extract arrays
    arr_amt   = df["amount"].to_numpy()
    arr_mrisk = df["merch_risk"].to_numpy()
    arr_crisk = df["card_risk"].to_numpy()
    # event_time as ns since epoch
    arr_ts_ns = df["event_time"].to_numpy().astype("datetime64[ns]").astype(int)
    hours     = ((arr_ts_ns // 1_000_000_000) % 86400) // 3600

    # Clamp fraud_rate away from 0/1
    eps = 1e-6
    fr = float(np.clip(fraud_rate, eps, 1 - eps))

    rng = default_rng(seed)

    # 1) logistic probabilities
    intercept = np.log(fr / (1 - fr))
    logit = (
        intercept
        + w_amount * np.log(arr_amt + 1)
        + w_mrisk * arr_mrisk
        + w_crisk * arr_crisk
        + w_night * (hours < 6).astype(float)
    )
    p = expit(logit)

    # 2) initial draw
    labels = rng.random(N) < p

    # 3) enforce exact fraud_count
    target  = int(round(fr * N))
    current = int(labels.sum())
    if current > target:
        # drop random overshoot
        true_idx = np.nonzero(labels)[0]
        drop = rng.choice(true_idx, size=current - target, replace=False)
        labels[drop] = False
    elif current < target:
        remaining = target - current

        # 1. Draw wave anchors (times + merchants), weighted by merchant risk
        num_waves = max(1, remaining // burst_factor)
        wave_times = rng.choice(arr_ts_ns, size=num_waves, replace=False)

        merch_ids = df["merchant_id"].to_numpy()
        uniq, idx_first = np.unique(merch_ids, return_index=True)
        merch_risks = df["merch_risk"].to_numpy()[idx_first]
        # if all-zero risk, fall back to uniform
        grp_probs = None if merch_risks.sum() <= 0 else merch_risks / merch_risks.sum()
        wave_merch = rng.choice(uniq, size=num_waves, replace=True, p=grp_probs)

        # 2. For each wave:
        #    • pick up to burst_factor txns within ±burst_window_s
        #    • if fewer than burst_factor available, draw the remainder globally
        for wt, wm in zip(wave_times, wave_merch):
            if remaining <= 0:
                break
            mask = (
                (merch_ids == wm)
                & (~labels)
                & (np.abs(arr_ts_ns - wt) <= burst_window_s * 1_000_000_000)
            )
            idxs = np.nonzero(mask)[0]
            if idxs.size >= burst_factor:
                # full burst
                chosen = rng.choice(idxs, size=burst_factor, replace=False)
                labels[chosen] = True
                remaining -= burst_factor
            elif idxs.size > 0:
                # partial: take what we can, then fill the rest globally
                labels[idxs] = True
                taken = idxs.size
                remaining -= taken
                # global fill for the shortfall
                shortfall = min(burst_factor - taken, remaining)
                if shortfall > 0:
                    unlabeled = np.nonzero(~labels)[0]
                    # weight by combined risk
                    cr = arr_mrisk * arr_crisk
                    total = cr[unlabeled].sum()
                    probs = None if total <= 0 else cr[unlabeled] / total
                    extra = rng.choice(unlabeled, size=shortfall, replace=False, p=probs)
                    labels[extra] = True
                    remaining -= shortfall

        # 3. Final global fallback if still below target
        if remaining > 0:
            unlabeled = np.nonzero(~labels)[0]
            if unlabeled.size > 0:
                combined_risk = arr_mrisk * arr_crisk
                total = combined_risk[unlabeled].sum()
                probs = None if total <= 0 else combined_risk[unlabeled] / total
                final = rng.choice(
                    unlabeled,
                    size=min(remaining, unlabeled.size),
                    replace=False,
                    p=probs
                )
                labels[final] = True


    # attach back to Polars
    return df.with_columns(pl.Series("label_fraud", labels).cast(pl.Boolean))
