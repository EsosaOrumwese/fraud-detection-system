"""Normalize or build 2B arrival roster with deterministic is_virtual assignment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import polars as pl


VIRTUAL_PERCENT = 10


def _find_repo_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return start


def _resolve_utc_day(explicit_day: str | None) -> str:
    if explicit_day:
        return explicit_day
    repo_root = _find_repo_root(Path(__file__).resolve())
    policy_path = repo_root / "config" / "layer1" / "2B" / "policy" / "day_effect_policy_v1.json"
    if policy_path.exists():
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
        start_day = str(payload.get("start_day") or "").strip()
        if start_day:
            return start_day
    return "2026-01-01"


def _virtual_bucket(merchant_id: int, seed: int) -> int:
    token = f"{merchant_id}:{seed}".encode("utf-8")
    digest = hashlib.sha256(token).digest()
    return int.from_bytes(digest[:4], "big") % 100


def _is_virtual(merchant_id: int, seed: int) -> bool:
    return _virtual_bucket(merchant_id, seed) < VIRTUAL_PERCENT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--runs-root", default="runs/local_full_run-5")
    parser.add_argument("--utc-day", default=None, help="Override UTC day for roster rows (YYYY-MM-DD).")
    args = parser.parse_args()

    run_id = args.run_id.strip()
    runs_root = Path(args.runs_root)
    receipt_path = runs_root / run_id / "run_receipt.json"
    if not receipt_path.exists():
        raise SystemExit(f"Run receipt not found: {receipt_path}")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    seed = receipt.get("seed")
    parameter_hash = receipt.get("parameter_hash")
    if seed is None or not parameter_hash:
        raise SystemExit(f"Missing seed or parameter_hash in receipt: {receipt_path}")

    utc_day = _resolve_utc_day(args.utc_day)
    utc_timestamp = f"{utc_day}T00:00:00.000000Z"

    roster_path = (
        runs_root
        / run_id
        / "data"
        / "layer1"
        / "2B"
        / "s5_arrival_roster"
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
        / "arrival_roster.jsonl"
    )
    if not roster_path.exists():
        manifest_fingerprint = receipt.get("manifest_fingerprint")
        if not manifest_fingerprint:
            raise SystemExit(f"Missing manifest_fingerprint in receipt: {receipt_path}")
        site_root = (
            runs_root
            / run_id
            / "data"
            / "layer1"
            / "1B"
            / "site_locations"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest_fingerprint}"
        )
        if site_root.is_file():
            site_paths = [site_root]
        else:
            site_paths = sorted(site_root.glob("*.parquet"))
        if not site_paths:
            raise SystemExit(f"site_locations parquet not found under: {site_root}")

        roster_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = roster_path.with_suffix(".jsonl.tmp")

        df = pl.read_parquet(site_paths, columns=["merchant_id"]).unique()
        merchant_ids = df.get_column("merchant_id").to_list()
        with tmp_path.open("w", encoding="utf-8") as handle:
            for merchant_id in merchant_ids:
                is_virtual = _is_virtual(int(merchant_id), int(seed))
                payload = {
                    "merchant_id": int(merchant_id),
                    "utc_timestamp": utc_timestamp,
                    "utc_day": utc_day,
                    "is_virtual": is_virtual,
                }
                handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
                handle.write("\n")
        tmp_path.replace(roster_path)
        print(
            "Generated arrival roster:",
            f"path={roster_path}",
            f"rows={len(merchant_ids)}",
            f"virtual_percent={VIRTUAL_PERCENT}",
            f"seed={seed}",
        )
        return

    tmp_path = roster_path.with_suffix(".jsonl.tmp")
    total = 0
    updated = 0
    updated_day = 0
    kept = 0

    with roster_path.open("r", encoding="utf-8") as handle, tmp_path.open(
        "w", encoding="utf-8"
    ) as tmp_handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            total += 1
            if "is_virtual" not in payload:
                payload["is_virtual"] = _is_virtual(int(payload["merchant_id"]), int(seed))
                updated += 1
            else:
                kept += 1
            if str(payload.get("utc_day")) != utc_day:
                payload["utc_day"] = utc_day
                updated_day += 1
            if str(payload.get("utc_timestamp")) != utc_timestamp:
                payload["utc_timestamp"] = utc_timestamp
            tmp_handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
            tmp_handle.write("\n")

    tmp_path.replace(roster_path)
    print(
        "Normalized arrival roster:",
        f"path={roster_path}",
        f"rows={total}",
        f"added_is_virtual={updated}",
        f"kept_existing={kept}",
        f"updated_day={updated_day}",
        f"utc_day={utc_day}",
        f"virtual_percent={VIRTUAL_PERCENT}",
        f"seed={seed}",
    )


if __name__ == "__main__":
    main()
