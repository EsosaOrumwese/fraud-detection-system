"""Build deterministic crossborder_features (1A) from merchant ingress."""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MERCHANT_PATH = ROOT / "reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet"
GDP_BUCKET_PATH = ROOT / "reference/economic/gdp_bucket_map/2024/gdp_bucket_map.parquet"
OUT_ROOT = ROOT / "data/layer1/1A/crossborder_features"

PARAMETER_FILES = [
    ROOT / "config/layer1/1A/models/hurdle/exports/version=2025-12-31/20251231T134200Z/hurdle_coefficients.yaml",
    ROOT / "config/layer1/1A/models/hurdle/exports/version=2025-12-31/20251231T134200Z/nb_dispersion_coefficients.yaml",
    ROOT / "config/layer1/1A/policy/crossborder_hyperparams.yaml",
    ROOT / "config/layer1/1A/allocation/ccy_smoothing_params.yaml",
    ROOT / "config/layer1/1A/policy.s6.selection.yaml",
]

BASE_MAP = {1: 0.06, 2: 0.12, 3: 0.20, 4: 0.28, 5: 0.35}
CHANNEL_DELTA = {"card_present": -0.04, "card_not_present": 0.08}
SOURCE_BASE = "heuristic_v1:gdp_bucket+channel+mcc"


def sha256_stream(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.digest()


def enc_str(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack("<I", len(raw)) + raw


def compute_parameter_hash(paths: list[Path]) -> str:
    entries = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Missing parameter file: {path}")
        name = path.name
        try:
            name.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError(f"Non-ASCII basename: {name}") from exc
        entries.append((name, path))

    entries.sort(key=lambda item: item[0])
    tuples = []
    for name, path in entries:
        d = sha256_stream(path)
        t = hashlib.sha256(enc_str(name) + d).digest()
        tuples.append(t)
    combined = b"".join(tuples)
    return hashlib.sha256(combined).hexdigest()


def mcc_tilt(mcc: int) -> float:
    if 4810 <= mcc <= 4899 or 5960 <= mcc <= 5969 or 5815 <= mcc <= 5818:
        return 0.10
    if 3000 <= mcc <= 3999 or mcc in {4111, 4121, 4131, 4411, 4511, 4722, 4789, 7011}:
        return 0.06
    if 5000 <= mcc <= 5999 or 5300 <= mcc <= 5399 or 5400 <= mcc <= 5599:
        return 0.03
    return 0.0


def clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def main() -> None:
    if not MERCHANT_PATH.exists():
        raise FileNotFoundError(f"Missing merchant ingress: {MERCHANT_PATH}")
    if not GDP_BUCKET_PATH.exists():
        raise FileNotFoundError(f"Missing GDP bucket map: {GDP_BUCKET_PATH}")

    parameter_hash = compute_parameter_hash(PARAMETER_FILES)

    merchants = pd.read_parquet(MERCHANT_PATH)
    required_cols = {"merchant_id", "mcc", "channel", "home_country_iso"}
    missing_cols = required_cols - set(merchants.columns)
    if missing_cols:
        raise ValueError(f"Missing required merchant columns: {sorted(missing_cols)}")

    if merchants["merchant_id"].duplicated().any():
        raise ValueError("Duplicate merchant_id in transaction_schema_merchant_ids")

    buckets = pd.read_parquet(GDP_BUCKET_PATH)[["country_iso", "bucket_id"]]
    buckets["country_iso"] = buckets["country_iso"].astype(str).str.upper()
    merchants["home_country_iso"] = merchants["home_country_iso"].astype(str).str.upper()
    merged = merchants.merge(
        buckets,
        how="left",
        left_on="home_country_iso",
        right_on="country_iso",
    )

    def compute_row(row) -> tuple[float, str]:
        bucket_id = row["bucket_id"]
        missing_bucket = pd.isna(bucket_id)
        if missing_bucket:
            bucket_id = 1
        base = BASE_MAP.get(int(bucket_id), BASE_MAP[1])
        channel = row["channel"]
        if channel not in CHANNEL_DELTA:
            raise ValueError(f"Unknown channel value: {channel}")
        delta = CHANNEL_DELTA[channel]
        tilt = mcc_tilt(int(row["mcc"]))
        raw = base + delta + tilt
        openness = clamp01(raw)
        if missing_bucket:
            source = f"{SOURCE_BASE};missing_bucket"
        else:
            source = SOURCE_BASE
        return openness, source

    openness_vals = []
    source_vals = []
    for row in merged.itertuples(index=False):
        openness, source = compute_row(row._asdict())
        openness_vals.append(openness)
        source_vals.append(source)

    output = pd.DataFrame(
        {
            "merchant_id": merged["merchant_id"].astype("int64"),
            "openness": openness_vals,
            "source": source_vals,
            "parameter_hash": parameter_hash,
            "produced_by_fingerprint": pd.Series([None] * len(merged), dtype="object"),
        }
    )
    output.sort_values("merchant_id", inplace=True)

    out_dir = OUT_ROOT / f"parameter_hash={parameter_hash}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "part-00000.parquet"
    output.to_parquet(out_path, index=False)


if __name__ == "__main__":
    main()

