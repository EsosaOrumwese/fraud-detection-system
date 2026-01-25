"""Minimal IG CLI (pull ingestion)."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .audit import verify_pull_run
from .admission import IngestionGate
from .config import WiringProfile


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion Gate CLI")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--run-facts", help="Path to SR run_facts_view.json for pull ingestion")
    parser.add_argument("--push-file", help="Path to envelope JSON for push ingestion")
    parser.add_argument("--lookup-event-id", help="Lookup receipt by event_id")
    parser.add_argument("--lookup-receipt-id", help="Lookup receipt by receipt_id")
    parser.add_argument("--lookup-dedupe-key", help="Lookup receipt by dedupe_key")
    parser.add_argument("--rebuild-index", action="store_true", help="Rebuild ops index from object store")
    parser.add_argument("--health", action="store_true", help="Print IG health probe state")
    parser.add_argument("--audit-verify", help="Verify pull-run hash chain + checkpoints for run_id")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    wiring = WiringProfile.load(Path(args.profile))
    gate = IngestionGate.build(wiring)

    if args.lookup_event_id:
        result = gate.ops_index.lookup_event(args.lookup_event_id)
        print(json.dumps(result or {}, ensure_ascii=True))
        return
    if args.lookup_receipt_id:
        result = gate.ops_index.lookup_receipt(args.lookup_receipt_id)
        print(json.dumps(result or {}, ensure_ascii=True))
        return
    if args.lookup_dedupe_key:
        result = gate.ops_index.lookup_dedupe(args.lookup_dedupe_key)
        print(json.dumps(result or {}, ensure_ascii=True))
        return
    if args.rebuild_index:
        gate.ops_index.rebuild_from_store(gate.store)
        print("REBUILT=1")
        return
    if args.health:
        result = gate.health.check()
        print(json.dumps({"state": result.state.value, "reasons": result.reasons}, ensure_ascii=True))
        return
    if args.audit_verify:
        report = verify_pull_run(gate, args.audit_verify)
        print(json.dumps(report, ensure_ascii=True))
        return
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
