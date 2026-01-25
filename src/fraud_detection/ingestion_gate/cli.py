"""Minimal IG CLI (pull ingestion)."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .admission import IngestionGate
from .config import WiringProfile


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion Gate CLI")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--run-facts", help="Path to SR run_facts_view.json for pull ingestion")
    parser.add_argument("--push-file", help="Path to envelope JSON for push ingestion")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    wiring = WiringProfile.load(Path(args.profile))
    gate = IngestionGate.build(wiring)

    if args.run_facts:
        receipts = gate.admit_pull(Path(args.run_facts))
        print(f"ADMITTED={len(receipts)}")
        return
    if args.push_file:
        payload = json.loads(Path(args.push_file).read_text(encoding="utf-8"))
        gate.admit_push(payload)
        print("ADMITTED=1")
        return
    raise SystemExit("Provide --run-facts or --push-file")


if __name__ == "__main__":
    main()
