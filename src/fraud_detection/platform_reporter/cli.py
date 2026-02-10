"""CLI entrypoint for platform run reporter."""

from __future__ import annotations

import argparse
import json

from .run_reporter import PlatformRunReporter


def main() -> None:
    parser = argparse.ArgumentParser(description="Platform run reporter")
    parser.add_argument("--profile", required=True, help="Platform profile YAML path")
    parser.add_argument("--platform-run-id", default=None, help="Platform run scope (defaults to active run)")
    args = parser.parse_args()

    reporter = PlatformRunReporter.build(
        profile_path=args.profile,
        platform_run_id=args.platform_run_id,
    )
    payload = reporter.export()
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
