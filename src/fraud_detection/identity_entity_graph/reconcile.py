"""Write reconciliation artifact for IEG."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from fraud_detection.platform_runtime import platform_run_root, resolve_platform_run_id

from .query import IdentityGraphQuery


def main() -> None:
    parser = argparse.ArgumentParser(description="IEG reconciliation artifact writer")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--output", help="Optional output path for reconciliation JSON")
    args = parser.parse_args()

    query = IdentityGraphQuery.from_profile(args.profile)
    basis = query.reconciliation()
    if not basis:
        raise SystemExit("NO_GRAPH_BASIS")

    platform_run_id = resolve_platform_run_id(create_if_missing=False)
    payload = {
        "platform_run_id": platform_run_id,
        "graph_version": basis.get("graph_version"),
        "basis": basis.get("basis"),
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
    }

    if args.output:
        path = Path(args.output)
    else:
        run_root = platform_run_root(create_if_missing=False)
        if not run_root:
            raise SystemExit("PLATFORM_RUN_ID_REQUIRED")
        path = run_root / "identity_entity_graph" / "reconciliation" / "reconciliation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(str(path))


if __name__ == "__main__":
    main()
