"""Hurdle diagnostics cache (S0.7)."""
from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence

import polars as pl

from ..exceptions import err
from .design import DesignVectors


def _logistic_branch(eta: float) -> float:
    if eta >= 0.0:
        z = math.exp(-eta)
        return 1.0 / (1.0 + z)
    z = math.exp(eta)
    return z / (1.0 + z)


def build_hurdle_diagnostics(
    vectors: Iterable[DesignVectors],
    *,
    beta: Sequence[float],
    parameter_hash: str,
    produced_by_fingerprint: Optional[str] = None,
) -> pl.DataFrame:
    rows = []
    beta_tuple = tuple(float(x) for x in beta)
    for vector in vectors:
        if len(vector.x_hurdle) != len(beta_tuple):
            raise err(
                "E_PI_SHAPE_MISMATCH",
                f"beta length {len(beta_tuple)} does not match design {len(vector.x_hurdle)}",
            )
        eta = 0.0
        for coeff, value in zip(beta_tuple, vector.x_hurdle):
            eta = math.fsum([eta, coeff * value])
        pi = _logistic_branch(eta)
        if not (math.isfinite(eta) and math.isfinite(pi)):
            raise err("E_PI_NAN_OR_INF", f"merchant {vector.merchant_id} produced non-finite output")
        row = {
            "parameter_hash": parameter_hash,
            "merchant_id": vector.merchant_id,
            "logit": float(eta),
            "pi": float(pi),
        }
        if produced_by_fingerprint is not None:
            row["produced_by_fingerprint"] = produced_by_fingerprint
        rows.append(row)

    schema = {
        "parameter_hash": pl.String,
        "merchant_id": pl.Int64,
        "logit": pl.Float32,
        "pi": pl.Float32,
    }
    if produced_by_fingerprint is not None:
        schema["produced_by_fingerprint"] = pl.String

    return pl.DataFrame(rows, schema=schema)


__all__ = ["build_hurdle_diagnostics"]
