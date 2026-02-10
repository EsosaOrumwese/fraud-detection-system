"""CLI for environment parity conformance checks."""

from __future__ import annotations

import argparse
import json

from .checker import run_environment_conformance


def main() -> None:
    parser = argparse.ArgumentParser(description="Platform environment conformance checker")
    parser.add_argument(
        "--local-parity-profile",
        default="config/platform/profiles/local_parity.yaml",
    )
    parser.add_argument(
        "--dev-profile",
        default="config/platform/profiles/dev.yaml",
    )
    parser.add_argument(
        "--prod-profile",
        default="config/platform/profiles/prod.yaml",
    )
    parser.add_argument("--platform-run-id", default=None)
    parser.add_argument("--output-path", default=None)
    args = parser.parse_args()

    result = run_environment_conformance(
        local_parity_profile=args.local_parity_profile,
        dev_profile=args.dev_profile,
        prod_profile=args.prod_profile,
        platform_run_id=args.platform_run_id,
        output_path=args.output_path,
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "artifact_path": result.artifact_path,
                "payload": result.payload,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
