"""CLI for Segment 1A S0 foundations."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from engine.core.config import EngineConfig
from engine.core.logging import get_logger
from engine.layers.l1.seg_1A.s0_foundations.runner import run_s0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Segment 1A S0 foundations.")
    parser.add_argument("--contracts-layout", default=os.getenv("ENGINE_CONTRACTS_LAYOUT", "model_spec"))
    parser.add_argument("--contracts-root", default=os.getenv("ENGINE_CONTRACTS_ROOT"))
    parser.add_argument(
        "--external-root",
        action="append",
        default=os.getenv("ENGINE_EXTERNAL_ROOTS", "").split(";") if os.getenv("ENGINE_EXTERNAL_ROOTS") else [],
        help="External roots for input resolution (repeatable or ';' delimited).",
    )
    parser.add_argument("--seed", type=int, default=None, help="Override the run seed.")
    parser.add_argument("--merchant-ids-version", default=None, help="Override merchant_ids version directory.")
    return parser


def main() -> None:
    logger = get_logger("engine.cli.s0")
    args = build_parser().parse_args()
    cfg = EngineConfig.default()
    if args.contracts_root:
        cfg = EngineConfig(
            repo_root=cfg.repo_root,
            contracts_root=Path(args.contracts_root),
            contracts_layout=args.contracts_layout,
            external_roots=cfg.external_roots,
        )
    else:
        cfg = EngineConfig(
            repo_root=cfg.repo_root,
            contracts_root=cfg.repo_root,
            contracts_layout=args.contracts_layout,
            external_roots=cfg.external_roots,
        )
    external_roots = [Path(root) for root in args.external_root if root]
    if external_roots:
        cfg = cfg.with_external_roots(external_roots)
    result = run_s0(cfg, seed_override=args.seed, merchant_ids_version=args.merchant_ids_version)
    logger.info(
        "S0 complete: run_id=%s parameter_hash=%s manifest_fingerprint=%s",
        result.run_id,
        result.parameter_hash,
        result.manifest_fingerprint,
    )


if __name__ == "__main__":
    main()
