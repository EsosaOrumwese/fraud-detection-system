"""OFP observability export CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .observability import OfpObservabilityReporter


def main() -> None:
    parser = argparse.ArgumentParser(description="OFP observability reporter")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--output-root", default=None, help="Optional explicit output root path")
    args = parser.parse_args()

    reporter = OfpObservabilityReporter.build(args.profile)
    payload = reporter.export(
        scenario_run_id=args.scenario_run_id,
        output_root=(Path(args.output_root) if args.output_root else None),
    )
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    main()

