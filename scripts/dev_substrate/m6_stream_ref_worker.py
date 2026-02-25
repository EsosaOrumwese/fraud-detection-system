#!/usr/bin/env python3
"""Minimal stream-ref worker for EMR-on-EKS M6.F lane execution.

This worker intentionally runs as a bounded, deterministic loop that can be
dispatched under the canonical lane refs. It can optionally emit ingress
admission probes when IG details are supplied.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


def _post_ingest(*, ig_base_url: str, api_key: str, payload: dict) -> tuple[int, str]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(
        f"{ig_base_url.rstrip('/')}/v1/ingest/push",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-IG-Api-Key": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - runtime guard
        return 599, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="M6 stream ref worker")
    parser.add_argument("--lane-ref", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--phase-id", default="P6.B")
    parser.add_argument("--iterations", type=int, default=600)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--ig-base-url", default="")
    parser.add_argument("--ig-api-key", default="")
    args = parser.parse_args()

    started = int(time.time())
    admitted = 0
    failed = 0

    for idx in range(max(1, args.iterations)):
        event_id = f"{args.lane_ref}:{started}:{idx}"
        if args.ig_base_url and args.ig_api_key:
            payload = {
                "platform_run_id": args.platform_run_id,
                "scenario_run_id": args.scenario_run_id,
                "phase_id": args.phase_id,
                "event_class": "m6_lane_probe",
                "event_id": event_id,
                "runtime_lane": args.lane_ref,
                "trace_id": event_id,
            }
            status, _ = _post_ingest(
                ig_base_url=args.ig_base_url,
                api_key=args.ig_api_key,
                payload=payload,
            )
            if status == 202:
                admitted += 1
            else:
                failed += 1

        if idx % 30 == 0:
            print(
                json.dumps(
                    {
                        "event": "m6_stream_ref_heartbeat",
                        "lane_ref": args.lane_ref,
                        "platform_run_id": args.platform_run_id,
                        "iteration": idx,
                        "admitted": admitted,
                        "failed": failed,
                        "timestamp_epoch": int(time.time()),
                    },
                    ensure_ascii=True,
                ),
                flush=True,
            )
        time.sleep(max(0.0, args.sleep_seconds))

    print(
        json.dumps(
            {
                "event": "m6_stream_ref_complete",
                "lane_ref": args.lane_ref,
                "platform_run_id": args.platform_run_id,
                "scenario_run_id": args.scenario_run_id,
                "iterations": max(1, args.iterations),
                "admitted": admitted,
                "failed": failed,
                "timestamp_epoch": int(time.time()),
            },
            ensure_ascii=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
