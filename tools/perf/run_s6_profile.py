#!/usr/bin/env python3
"""Profiler harness for Segment 1B S6 site jitter.

Usage:
    python tools/perf/run_s6_profile.py \
        --data-root runs/local_layer1_regen7 \
        --parameter-hash <hash> \
        --manifest-fingerprint <fingerprint> \
        --seed <seed> \
        --profile-out docs/perf/s6_jitter/profile.pstats

The script expects that S0-S5 artefacts already exist under the supplied
`--data-root`. It executes S6 in isolation and emits a cProfile snapshot for
subsequent analysis (e.g., `snakeviz`, `pstats`).
"""

from __future__ import annotations

import argparse
import cProfile
import pathlib
import sys
import pstats

from engine.layers.l1.seg_1B import S6RunnerConfig, S6SiteJitterRunner
from engine.layers.l1.seg_1B.shared.dictionary import load_dictionary


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile Segment 1B S6 jitter")
    parser.add_argument("--data-root", required=True, type=pathlib.Path)
    parser.add_argument("--parameter-hash", required=True)
    parser.add_argument("--manifest-fingerprint", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--dictionary", type=pathlib.Path, help="Optional dictionary override")
    parser.add_argument(
        "--profile-out",
        type=pathlib.Path,
        default=None,
        help="Optional output location for the cProfile stats",
    )
    args = parser.parse_args()

    data_root = args.data_root.expanduser().resolve()
    dictionary = load_dictionary(args.dictionary) if args.dictionary else load_dictionary()

    runner = S6SiteJitterRunner()
    config = S6RunnerConfig(
        data_root=data_root,
        manifest_fingerprint=args.manifest_fingerprint,
        seed=args.seed,
        parameter_hash=args.parameter_hash,
        dictionary=dictionary,
    )

    profiler = cProfile.Profile()
    profiler.enable()
    runner.run(config)
    profiler.disable()

    stats = pstats.Stats(profiler).strip_dirs().sort_stats(pstats.SortKey.CUMULATIVE)
    stats.print_stats(50)

    if args.profile_out:
        args.profile_out.parent.mkdir(parents=True, exist_ok=True)
        stats.dump_stats(str(args.profile_out))
        print(f"Profile written to {args.profile_out}")


if __name__ == "__main__":
    try:
        import polars as pl  # noqa: F401
    except ImportError:
        print("polars is required for the profiling harness", file=sys.stderr)
        sys.exit(1)

    main()
