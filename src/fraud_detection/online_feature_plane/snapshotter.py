"""OFP snapshot materializer CLI."""

from __future__ import annotations

import argparse
import json

from .snapshots import OfpSnapshotMaterializer


def main() -> None:
    parser = argparse.ArgumentParser(description="OFP snapshot materializer")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--as-of-time-utc", default=None)
    parser.add_argument("--snapshot-hash", default=None, help="Lookup snapshot index by hash instead of building")
    args = parser.parse_args()

    materializer = OfpSnapshotMaterializer.build(args.profile)
    if args.snapshot_hash:
        payload = materializer.get_snapshot_index(args.snapshot_hash)
        print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
        return
    snapshot = materializer.materialize(
        platform_run_id=args.platform_run_id,
        scenario_run_id=args.scenario_run_id,
        as_of_time_utc=args.as_of_time_utc,
    )
    print(json.dumps(snapshot, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    main()
