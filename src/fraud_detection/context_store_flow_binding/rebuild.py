"""CSFB rebuild/backfill entrypoint (Phase 4)."""

from __future__ import annotations

import argparse
import logging

from .intake import ContextStoreFlowBindingInlet
from .replay import CsfbReplayManifest

logger = logging.getLogger("fraud_detection.csfb.rebuild")


def main() -> None:
    parser = argparse.ArgumentParser(description="CSFB rebuild/backfill runner (explicit basis required)")
    parser.add_argument("--policy", required=True, help="Path to CSFB intake policy YAML")
    parser.add_argument(
        "--replay-manifest",
        required=True,
        help="Path to CSFB replay basis manifest (must include explicit offsets)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    inlet = ContextStoreFlowBindingInlet.build(args.policy)
    manifest = CsfbReplayManifest.load(args.replay_manifest)
    processed = inlet.run_replay_once(manifest)
    logger.info("CSFB rebuild complete processed=%s replay_id=%s", processed, manifest.replay_id())


if __name__ == "__main__":
    main()
