"""Segment 3A S5 runner – zone allocation egress and universe hash."""

from __future__ import annotations

import json
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import polars as pl
from jsonschema import Draft202012Validator, ValidationError

from engine.layers.l1.seg_3A.s0_gate.exceptions import err
from engine.layers.l1.seg_3A.s0_gate.l0 import aggregate_sha256, expand_files, hash_files
from engine.layers.l1.seg_3A.shared import SegmentStateKey, load_schema, render_dataset_path, write_segment_state_run_report
from engine.layers.l1.seg_3A.shared.dictionary import load_dictionary

_S0_RECEIPT_SCHEMA = Draft202012Validator(load_schema("#/validation/s0_gate_receipt_3A"))
_SEALED_INPUT_VALIDATOR = Draft202012Validator(load_schema("#/validation/sealed_inputs_3A"))
_UNIVERSE_SCHEMA = Draft202012Validator(load_schema("#/validation/zone_alloc_universe_hash"))


@dataclass(frozen=True)
class ZoneAllocInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class ZoneAllocResult:
    output_path: Path
    universe_hash_path: Path
    run_report_path: Path
    resumed: bool


class ZoneAllocRunner:
    """Build zone_alloc egress and universe hash."""

    def run(self, inputs: ZoneAllocInputs) -> ZoneAllocResult:
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
        s4_path = data_root / render_dataset_path(
            dataset_id="s4_zone_counts",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not s1_path.exists() or not s3_path.exists() or not s4_path.exists():
            raise err("E_UPSTREAM_MISSING", "S1, S3, or S4 outputs missing for S5")

        s1_df = pl.read_parquet(s1_path)
        s3_df = pl.read_parquet(s3_path)
        s4_df = pl.read_parquet(s4_path)

        sealed_inputs = self._load_sealed_inputs(
            base=data_root, manifest_fingerprint=manifest_fingerprint, dictionary=dictionary
        )
        sealed_index = {row["logical_id"]: row for row in sealed_inputs.to_dicts()}
        day_effect_meta = self._load_policy_meta(sealed_index, "day_effect_policy_v1")

        # join s4 with s1 to bring mixture/site_count, and s3 to add routing hash basis
        s1_keyed = s1_df.select(
            [
                "merchant_id",
                "legal_country_iso",
                "site_count",
                "mixture_policy_id",
                "mixture_policy_version",
                "theta_digest",
            ]
        )
        s4_enriched = s4_df.join(s1_keyed, on=["merchant_id", "legal_country_iso"], how="left")
        if s4_enriched.filter(pl.col("site_count").is_null()).height > 0:
            raise err("E_JOIN_MISSING", "site_count join failed for one or more rows")

        routing_universe_hash = self._compute_routing_hash(s3_df)

        rows = []
        for row in s4_enriched.to_dicts():
            site_count = int(row["site_count"])
            zone_sum = int(row["zone_site_count_sum"])
            if site_count != zone_sum:
                raise err(
                    "E_COUNT_MISMATCH",
                    f"zone_site_count_sum {zone_sum} does not equal site_count {site_count}",
                )
            rows.append(
                {
                    "seed": seed,
                    "fingerprint": manifest_fingerprint,
                    "merchant_id": row["merchant_id"],
                    "legal_country_iso": row["legal_country_iso"],
                    "tzid": row["tzid"],
                    "zone_site_count": int(row["zone_site_count"]),
                    "zone_site_count_sum": int(row["zone_site_count_sum"]),
                    "site_count": site_count,
                    "prior_pack_id": row["prior_pack_id"],
                    "prior_pack_version": row["prior_pack_version"],
                    "floor_policy_id": row["floor_policy_id"],
                    "floor_policy_version": row["floor_policy_version"],
                    "mixture_policy_id": row["mixture_policy_id"],
                    "mixture_policy_version": row["mixture_policy_version"],
                    "day_effect_policy_id": day_effect_meta["policy_id"],
                    "day_effect_policy_version": day_effect_meta["version"],
                    "routing_universe_hash": routing_universe_hash,
                    "alpha_sum_country": row.get("alpha_sum_country"),
                    "notes": None,
                }
            )

        output_dir = data_root / render_dataset_path(
            dataset_id="zone_alloc",
            template_args={"seed": seed, "fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "part-0.parquet"
        result_df = pl.DataFrame(rows)
        resumed = False
        if output_file.exists():
            existing = pl.read_parquet(output_file)
            if not existing.frame_equal(result_df):
                raise err("E_IMMUTABILITY", f"zone_alloc exists at '{output_file}' with different content")
            resumed = True
        else:
            result_df.write_parquet(output_file)

        universe_path = data_root / render_dataset_path(
            dataset_id="zone_alloc_universe_hash",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        universe_path.parent.mkdir(parents=True, exist_ok=True)
        universe_payload = self._build_universe_hash(
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            sealed_index=sealed_index,
            theta_digest=s1_df.select("theta_digest").to_series()[0] if s1_df.height > 0 else "0" * 64,
            zone_alloc_path=output_file,
            routing_hash=routing_universe_hash,
        )
        universe_path.write_text(json.dumps(universe_payload, indent=2, sort_keys=True), encoding="utf-8")

        run_report_path = (
            data_root
            / f"runs/layer1/3A/s5_zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}/run_report.json"
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer1",
            "segment": "3A",
            "state": "S5",
            "status": "PASS",
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "rows": result_df.height,
            "resumed": resumed,
            "zone_alloc_path": str(output_file),
            "universe_hash_path": str(universe_path),
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

        # segment-state run entry
        key = SegmentStateKey(
            layer="layer1",
            segment="3A",
            state="S5",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
        )
        report_dataset_path = data_root / render_dataset_path(
            dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
        )
        write_segment_state_run_report(
            path=report_dataset_path,
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

        return ZoneAllocResult(
            output_path=output_dir,
            universe_hash_path=universe_path,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    # ------------------------------------------------------------------ helpers
    def _load_s0_receipt(self, *, base: Path, manifest_fingerprint: str, dictionary: Mapping[str, object]) -> Mapping[str, Any]:
        receipt_path = base / render_dataset_path(
            dataset_id="s0_gate_receipt_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not receipt_path.exists():
            raise err("E_S0_PRECONDITION", f"S0 receipt missing at '{receipt_path}'")
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        try:
            _S0_RECEIPT_SCHEMA.validate(payload)
        except ValidationError as exc:
            raise err("E_SCHEMA", f"s0 receipt invalid: {exc.message}") from exc
        return payload

    def _load_sealed_inputs(self, *, base: Path, manifest_fingerprint: str, dictionary: Mapping[str, object]) -> pl.DataFrame:
        sealed_path = base / render_dataset_path(
            dataset_id="sealed_inputs_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not sealed_path.exists():
            raise err("E_S0_PRECONDITION", "sealed_inputs_3A missing; run S0 first")
        df = pl.read_parquet(sealed_path)
        for row in df.to_dicts():
            try:
                _SEALED_INPUT_VALIDATOR.validate(row)
            except ValidationError as exc:
                raise err("E_SCHEMA", f"sealed_inputs row invalid: {exc.message}") from exc
        return df

    def _load_policy_meta(self, sealed_index: Mapping[str, Mapping[str, Any]], logical_id: str) -> Mapping[str, str]:
        row = sealed_index.get(logical_id)
        if row is None:
            return {"policy_id": logical_id, "version": "unknown"}
        path = Path(row["path"])
        if not path.exists():
            return {"policy_id": logical_id, "version": "unknown"}
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            policy_id = str(payload.get("policy_id") or payload.get("id") or logical_id)
            version = str(payload.get("version") or payload.get("semver") or "unknown")
            return {"policy_id": policy_id, "version": version}
        except Exception:
            return {"policy_id": logical_id, "version": "unknown"}

    def _compute_routing_hash(self, s3_df: pl.DataFrame) -> str:
        if s3_df.is_empty():
            return "0" * 64
        # hash deterministic csv bytes
        csv_bytes = s3_df.sort(["merchant_id", "legal_country_iso", "tzid"]).to_pandas().to_csv(index=False).encode()
        return self._hash_bytes(csv_bytes)

    def _hash_bytes(self, data: bytes) -> str:
        from hashlib import sha256

        return sha256(data).hexdigest()

    def _build_universe_hash(
        self,
        *,
        manifest_fingerprint: str,
        parameter_hash: str,
        sealed_index: Mapping[str, Mapping[str, Any]],
        theta_digest: str,
        zone_alloc_path: Path,
        routing_hash: str,
    ) -> Mapping[str, Any]:
        def _digest_for(logical_id: str) -> str:
            row = sealed_index.get(logical_id)
            if row is None:
                return "0" * 64
            return str(row.get("sha256_hex") or "0" * 64)

        zone_alloc_digest = aggregate_sha256(hash_files(expand_files(zone_alloc_path), error_prefix="zone_alloc"))
        payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "zone_alpha_digest": _digest_for("country_zone_alphas"),
            "theta_digest": theta_digest or "0" * 64,
            "zone_floor_digest": _digest_for("zone_floor_policy"),
            "day_effect_digest": _digest_for("day_effect_policy_v1"),
            "zone_alloc_parquet_digest": zone_alloc_digest,
            "routing_universe_hash": routing_hash or "0" * 64,
            "version": "1.0.0",
        }
        try:
            _UNIVERSE_SCHEMA.validate(payload)
        except ValidationError as exc:
            raise err("E_SCHEMA", f"zone_alloc_universe_hash invalid: {exc.message}") from exc
        return payload

    def _assert_upstream_pass(self, receipt: Mapping[str, Any]) -> None:
        gates = receipt.get("upstream_gates", {})
        for segment in ("segment_1A", "segment_1B", "segment_2A"):
            status = gates.get(segment, {}).get("status")
            if status != "PASS":
                raise err("E_UPSTREAM_GATE", f"{segment} status '{status}' is not PASS")
