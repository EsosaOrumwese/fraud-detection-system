"""Segment 3A S4 runner – deterministic integer zone allocation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import polars as pl

from engine.layers.l1.seg_3A.s0_gate.exceptions import err
from engine.layers.l1.seg_3A.shared import (
    SegmentStateKey,
    load_schema,
    render_dataset_path,
    write_segment_state_run_report,
)
from engine.layers.l1.seg_3A.shared.dictionary import load_dictionary
from jsonschema import Draft202012Validator, ValidationError

_S0_RECEIPT_SCHEMA = load_schema("#/validation/s0_gate_receipt_3A")
_S0_RECEIPT_FIELDS = {"parameter_hash", "manifest_fingerprint", "seed", "upstream_gates"}


def _frames_equal(a: pl.DataFrame, b: pl.DataFrame) -> bool:
    try:
        return a.frame_equal(b)  # type: ignore[attr-defined]
    except AttributeError:
        try:
            return a.equals(b)  # type: ignore[attr-defined]
        except Exception:
            return False


@dataclass(frozen=True)
class ZoneCountsInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class ZoneCountsResult:
    output_path: Path
    run_report_path: Path
    resumed: bool


class ZoneCountsRunner:
    """RNG-free integeriser from zone shares to counts."""

    def run(self, inputs: ZoneCountsInputs) -> ZoneCountsResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.resolve()
        manifest_fingerprint = inputs.manifest_fingerprint
        parameter_hash = inputs.parameter_hash
        seed = inputs.seed

        s0_receipt = self._load_s0_receipt(
            base=data_root, manifest_fingerprint=manifest_fingerprint, dictionary=dictionary
        )
        self._assert_upstream_pass(s0_receipt)
        if str(s0_receipt.get("parameter_hash")) != str(parameter_hash):
            raise err("E_PARAM_HASH", "parameter_hash mismatch between inputs and S0 receipt")

        s1_path = data_root / render_dataset_path(
            dataset_id="s1_escalation_queue",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        s3_path = data_root / render_dataset_path(
            dataset_id="s3_zone_shares",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not s1_path.exists() or not s3_path.exists():
            raise err("E_UPSTREAM_MISSING", "S1 escalation queue or S3 zone shares missing for S4")

        s1_df = pl.read_parquet(s1_path)
        s3_df = pl.read_parquet(s3_path)
        escalated = s1_df.filter(pl.col("is_escalated"))
        if escalated.is_empty():
            return self._write_outputs(
                data_root=data_root,
                dictionary=dictionary,
                seed=seed,
                manifest_fingerprint=manifest_fingerprint,
                rows=[],
                parameter_hash=parameter_hash,
                resumed=False,
            )

        # Build lookup keyed by (merchant_id, country)
        share_index: dict[tuple[int, str], list[Mapping[str, Any]]] = {}
        for row in s3_df.sort(["merchant_id", "legal_country_iso", "tzid"]).to_dicts():
            key = (int(row["merchant_id"]), str(row["legal_country_iso"]))
            share_index.setdefault(key, []).append(row)

        rows: list[dict[str, Any]] = []
        for pair in escalated.to_dicts():
            merchant_id = int(pair["merchant_id"])
            country = str(pair["legal_country_iso"])
            site_count = int(pair["site_count"])
            share_rows = share_index.get((merchant_id, country))
            if not share_rows:
                raise err("E_S3_MISSING", f"s3_zone_shares missing for escalated pair {merchant_id}/{country}")
            rows.extend(self._integerise_pair(merchant_id, country, site_count, share_rows, seed, manifest_fingerprint))

        return self._write_outputs(
            data_root=data_root,
            dictionary=dictionary,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            rows=rows,
            parameter_hash=parameter_hash,
            resumed=False,
        )

    # ------------------------------------------------------------------ #
    def _integerise_pair(
        self,
        merchant_id: int,
        country: str,
        site_count: int,
        share_rows: Sequence[Mapping[str, Any]],
        seed: int,
        manifest_fingerprint: str,
    ) -> list[dict[str, Any]]:
        if site_count < 0:
            raise err("E_SITE_COUNT", f"site_count must be >=0, got {site_count}")
        # compute targets
        targets = []
        for row in share_rows:
            share = float(row["share_drawn"])
            targets.append((row, site_count * share, share))
        # floor counts
        floored = [(row, int(target // 1), target, share) for row, target, share in targets]
        floor_sum = sum(item[1] for item in floored)
        residual = site_count - floor_sum
        # rank by residual fraction then tzid
        ranked = sorted(
            [(row, target - floor, target, floor, share) for row, floor, target, share in floored],
            key=lambda item: (-item[1], str(item[0]["tzid"])),
        )
        allocations: dict[str, int] = {}
        for idx, (row, resid, target, floor, share) in enumerate(ranked, start=1):
            extra = 1 if residual > 0 else 0
            if residual > 0:
                residual -= 1
            allocations[row["tzid"]] = floor + extra
            ranked[idx - 1] = (row, resid, target, floor + extra, share, idx)
        # build rows
        output_rows = []
        share_sum_country = sum(r["share_drawn"] for r in share_rows)
        for row, resid, target, floor, share, rank_idx in ranked:
            tzid = row["tzid"]
            output_rows.append(
                {
                    "seed": seed,
                    "fingerprint": manifest_fingerprint,
                    "merchant_id": merchant_id,
                    "legal_country_iso": country,
                    "tzid": tzid,
                    "zone_site_count": int(allocations[tzid]),
                    "zone_site_count_sum": int(site_count),
                    "share_sum_country": float(share_sum_country),
                    "fractional_target": float(target),
                    "residual_rank": int(rank_idx) if site_count > 0 else None,
                    "prior_pack_id": row["prior_pack_id"],
                    "prior_pack_version": row["prior_pack_version"],
                    "floor_policy_id": row["floor_policy_id"],
                    "floor_policy_version": row["floor_policy_version"],
                    "alpha_sum_country": row.get("alpha_sum_country"),
                    "notes": None,
                }
            )
        return output_rows

    def _write_outputs(
        self,
        *,
        data_root: Path,
        dictionary: Mapping[str, object],
        seed: int,
        manifest_fingerprint: str,
        rows: Sequence[Mapping[str, Any]],
        parameter_hash: str,
        resumed: bool,
    ) -> ZoneCountsResult:
        output_dir = data_root / render_dataset_path(
            dataset_id="s4_zone_counts",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "part-0.parquet"
        schema = {
            "seed": pl.Int64,
            "fingerprint": pl.Utf8,
            "merchant_id": pl.UInt64,
            "legal_country_iso": pl.Utf8,
            "tzid": pl.Utf8,
            "zone_site_count": pl.Int64,
            "zone_site_count_sum": pl.Int64,
            "share_sum_country": pl.Float64,
            "fractional_target": pl.Float64,
            "residual_rank": pl.Int64,
            "prior_pack_id": pl.Utf8,
            "prior_pack_version": pl.Utf8,
            "floor_policy_id": pl.Utf8,
            "floor_policy_version": pl.Utf8,
            "alpha_sum_country": pl.Float64,
            "notes": pl.Utf8,
        }
        result_df = pl.DataFrame(rows, schema=schema)
        if output_file.exists():
            existing = pl.read_parquet(output_file)
            if not _frames_equal(existing, result_df):
                raise err(
                    "E_IMMUTABILITY",
                    f"s4_zone_counts already exists at '{output_file}' with different content",
                )
            resumed = True
        else:
            result_df.write_parquet(output_file)

        run_report_path = data_root / render_dataset_path(
            dataset_id="s4_run_report_3A",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer1",
            "segment": "3A",
            "state": "S4",
            "status": "PASS",
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "pairs_total": len(
                {(int(row["merchant_id"]), str(row["legal_country_iso"])) for row in result_df.to_dicts()}
            )
            if result_df.height > 0
            else 0,
            "zones_total": result_df.height,
            "resumed": resumed,
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")
        key = SegmentStateKey(
            layer="layer1",
            segment="3A",
            state="S4",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
        )
        report_path = data_root / render_dataset_path(
            dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
        )
        write_segment_state_run_report(
            path=report_path,
            key=key,
            payload={
                **key.as_dict(),
                "status": "PASS",
                "attempt": 1,
                "output_path": str(output_file),
                "run_report_path": str(run_report_path),
                "resumed": resumed,
            },
        )

        return ZoneCountsResult(
            output_path=output_dir,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    def _load_s0_receipt(self, *, base: Path, manifest_fingerprint: str, dictionary: Mapping[str, object]) -> Mapping[str, Any]:
        receipt_path = base / render_dataset_path(
            dataset_id="s0_gate_receipt_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not receipt_path.exists():
            raise err("E_S0_PRECONDITION", f"S0 receipt missing at '{receipt_path}'")
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        for field in _S0_RECEIPT_FIELDS:
            if field not in payload:
                raise err("E_S0_PRECONDITION", f"S0 receipt missing field '{field}'")
        from jsonschema import Draft202012Validator, ValidationError

        try:
            Draft202012Validator(_S0_RECEIPT_SCHEMA).validate(payload)
        except ValidationError as exc:
            raise err("E_SCHEMA", f"s0 receipt invalid: {exc.message}") from exc
        return payload

    def _assert_upstream_pass(self, receipt: Mapping[str, Any]) -> None:
        gates = receipt.get("upstream_gates", {})
        for segment in ("segment_1A", "segment_1B", "segment_2A"):
            status = gates.get(segment, {}).get("status")
            if status != "PASS":
                raise err("E_UPSTREAM_GATE", f"{segment} status '{status}' is not PASS")
