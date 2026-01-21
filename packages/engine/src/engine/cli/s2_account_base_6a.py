"""CLI for Segment 6A S2 account base."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from engine.core.config import EngineConfig
from engine.core.logging import get_logger
from engine.layers.l3.seg_6A.s2_accounts.runner import run_s2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Segment 6A S2 account base.")
    parser.add_argument("--contracts-layout", default=os.getenv("ENGINE_CONTRACTS_LAYOUT", "model_spec"))
    parser.add_argument("--contracts-root", default=os.getenv("ENGINE_CONTRACTS_ROOT"))
    parser.add_argument("--runs-root", default=os.getenv("ENGINE_RUNS_ROOT"))
    parser.add_argument(
        "--external-root",
        action="append",
        default=os.getenv("ENGINE_EXTERNAL_ROOTS", "").split(";") if os.getenv("ENGINE_EXTERNAL_ROOTS") else [],
        help="External roots for input resolution (repeatable or ';' delimited).",
    )
    parser.add_argument("--run-id", default=None, help="Select a run_id (defaults to latest run_receipt.json).")
    return parser


def main() -> None:
    logger = get_logger("engine.layers.l3.seg_6A.s2_accounts.cli")
    args = build_parser().parse_args()
    cfg = EngineConfig.default()
    runs_root = Path(args.runs_root) if args.runs_root else cfg.runs_root
    if args.contracts_root:
        cfg = EngineConfig(
            repo_root=cfg.repo_root,
            contracts_root=Path(args.contracts_root),
            contracts_layout=args.contracts_layout,
            runs_root=runs_root,
            external_roots=cfg.external_roots,
        )
    else:
        cfg = EngineConfig(
            repo_root=cfg.repo_root,
            contracts_root=cfg.repo_root,
            contracts_layout=args.contracts_layout,
            runs_root=runs_root,
            external_roots=cfg.external_roots,
        )
    external_roots = [Path(root) for root in args.external_root if root]
    if external_roots:
        cfg = cfg.with_external_roots(external_roots)
    result = run_s2(cfg, run_id=args.run_id)
    logger.info(
        "S2 6A complete: run_id=%s parameter_hash=%s manifest_fingerprint=%s account_base=%s",
        result.run_id,
        result.parameter_hash,
        result.manifest_fingerprint,
        result.account_base_path,
    )


if __name__ == "__main__":
    main()
