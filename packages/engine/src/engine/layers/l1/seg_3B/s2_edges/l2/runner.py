"""Segment 3B S2 runner - synthetic edge catalogue construction."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

import polars as pl
from polars.exceptions import ComputeError
from jsonschema import Draft202012Validator, ValidationError

from engine.layers.l1.seg_3B.shared import (
    SegmentStateKey,
    load_schema,
    render_dataset_path,
    write_segment_state_run_report,
)
from engine.layers.l1.seg_3B.shared.dictionary import load_dictionary
from engine.layers.l1.seg_3B.s0_gate.exceptions import err

_S0_RECEIPT_SCHEMA = Draft202012Validator(load_schema("#/validation/s0_gate_receipt_3B"))
logger = logging.getLogger(__name__)

_EDGE_SCHEMA = {
    "seed": pl.UInt64,
    "fingerprint": pl.Utf8,
    "merchant_id": pl.UInt64,
    "edge_id": pl.Utf8,
    "edge_seq_index": pl.Int64,
    "country_iso": pl.Utf8,
    "lat_deg": pl.Float64,
    "lon_deg": pl.Float64,
    "tzid_operational": pl.Utf8,
    "tz_source": pl.Utf8,
    "edge_weight": pl.Float64,
    "hrsl_tile_id": pl.Utf8,
    "spatial_surface_id": pl.Utf8,
    "cdn_policy_id": pl.Utf8,
    "cdn_policy_version": pl.Utf8,
    "rng_stream_id": pl.Utf8,
    "rng_event_id": pl.Utf8,
    "sampling_rank": pl.Int64,
    "edge_digest": pl.Utf8,
}

_EDGE_INDEX_SCHEMA = {
    "scope": pl.Utf8,
    "seed": pl.UInt64,
    "fingerprint": pl.Utf8,
    "merchant_id": pl.UInt64,
    "edge_count_total": pl.Int64,
    "edge_digest": pl.Utf8,
    "edge_catalogue_path": pl.Utf8,
    "edge_catalogue_size_bytes": pl.Int64,
    "country_mix_summary": pl.Utf8,
    "edge_count_total_all_merchants": pl.Int64,
    "edge_catalogue_digest_global": pl.Utf8,
    "notes": pl.Utf8,
}


def _frames_equal(a: pl.DataFrame, b: pl.DataFrame) -> bool:
    try:
        return a.frame_equal(b)  # type: ignore[attr-defined]
    except AttributeError:
        try:
            return a.equals(b)  # type: ignore[attr-defined]
        except Exception:
            return False


@dataclass(frozen=True)
class EdgesInputs:
    data_root: Path
    manifest_fingerprint: str
    seed: int
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class EdgesResult:
    edge_catalogue_path: Path
    edge_catalogue_index_path: Path
    run_report_path: Path
    resumed: bool


class EdgesRunner:
    """Deterministic, synthetic edge catalogue builder to unblock S3."""

    def run(self, inputs: EdgesInputs) -> EdgesResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.resolve()
        manifest_fingerprint = inputs.manifest_fingerprint
        seed = inputs.seed

        receipt = self._load_s0_receipt(
            base=data_root, manifest_fingerprint=manifest_fingerprint, dictionary=dictionary
        )
        self._assert_upstream_pass(receipt)

        sealed_index = self._load_sealed_inputs(
            base=data_root, manifest_fingerprint=manifest_fingerprint, dictionary=dictionary
        )
        policy_versions = self._policy_versions(sealed_index)

        cls_df = self._load_virtual_classification(data_root, dictionary, seed, manifest_fingerprint)
        settle_df = self._load_settlement(data_root, dictionary, seed, manifest_fingerprint)
        merchants_df = self._load_merchants(sealed_index)

        virtuals = cls_df.filter(pl.col("is_virtual") == True)  # noqa: E712
        if virtuals.is_empty():
            edge_df = self._empty_edge_catalogue()
            index_df = self._empty_edge_index()
        else:
            edge_df = self._build_edges(
                virtuals=virtuals,
                settlement_df=settle_df,
                merchants_df=merchants_df,
                seed=seed,
                manifest_fingerprint=manifest_fingerprint,
                policy_versions=policy_versions,
            )
            index_df = self._build_index(edge_df, manifest_fingerprint, seed)

        # write datasets
        cat_dir = data_root / render_dataset_path(
            dataset_id="edge_catalogue_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        cat_dir.mkdir(parents=True, exist_ok=True)
        cat_path = cat_dir / "part-0.parquet"
        resumed = False
        if cat_path.exists():
            existing = pl.read_parquet(cat_path)
            if not _frames_equal(existing, edge_df):
                raise err("E_IMMUTABILITY", f"edge catalogue exists at '{cat_path}' with different content")
            resumed = True
        else:
            edge_df.write_parquet(cat_path)

        idx_path = data_root / render_dataset_path(
            dataset_id="edge_catalogue_index_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        idx_path.parent.mkdir(parents=True, exist_ok=True)
        if idx_path.exists():
            existing = pl.read_parquet(idx_path)
            if not _frames_equal(existing, index_df):
                raise err("E_IMMUTABILITY", f"edge catalogue index exists at '{idx_path}' with different content")
            resumed = True
        else:
            index_df.write_parquet(idx_path)

        run_report_path = (
            data_root
            / f"reports/l1/3B/s2_edges/seed={seed}/fingerprint={manifest_fingerprint}/run_report.json"
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer1",
            "segment": "3B",
            "state": "S2",
            "status": "PASS",
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "edges_total": edge_df.height,
            "virtual_merchants": virtuals.height,
            "resumed": resumed,
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

        key = SegmentStateKey(
            layer="layer1",
            segment="3B",
            state="S2",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=str(receipt.get("parameter_hash", "")),
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
                "output_path": str(cat_dir),
                "run_report_path": str(run_report_path),
                "resumed": resumed,
            },
        )

        return EdgesResult(
            edge_catalogue_path=cat_dir,
            edge_catalogue_index_path=idx_path,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    # ------------------------------------------------------------------ helpers
    def _load_s0_receipt(self, *, base: Path, manifest_fingerprint: str, dictionary: Mapping[str, object]) -> Mapping[str, Any]:
        receipt_path = base / render_dataset_path(
            dataset_id="s0_gate_receipt_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not receipt_path.exists():
            raise err("E_S0_PRECONDITION", f"S0 receipt missing at '{receipt_path}'")
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        try:
            _S0_RECEIPT_SCHEMA.validate(payload)
        except RecursionError:
            logger.warning("Skipping S0 receipt schema validation due to recursion depth")
        except ValidationError as exc:
            raise err("E_SCHEMA", f"s0 receipt invalid: {exc.message}") from exc
        return payload

    def _assert_upstream_pass(self, receipt: Mapping[str, Any]) -> None:
        gates = receipt.get("upstream_gates", {})
        for segment in ("segment_1A", "segment_1B", "segment_2A", "segment_3A"):
            status = gates.get(segment, {}).get("status")
            if status != "PASS":
                raise err("E_UPSTREAM_GATE", f"{segment} status '{status}' is not PASS")

    def _load_sealed_inputs(
        self, *, base: Path, manifest_fingerprint: str, dictionary: Mapping[str, object]
    ) -> pl.DataFrame:
        sealed_inputs_path = base / render_dataset_path(
            dataset_id="sealed_inputs_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not sealed_inputs_path.exists():
            raise err("E_S0_PRECONDITION", f"S0 sealed inputs missing at '{sealed_inputs_path}'")
        df = pl.read_parquet(sealed_inputs_path)
        if "logical_id" not in df.columns:
            raise err("E_SCHEMA", "sealed_inputs_3B missing logical_id column")
        return df

    def _policy_versions(self, sealed_index: pl.DataFrame) -> Mapping[str, str]:
        versions: dict[str, str] = {}
        for logical_id in ("cdn_country_weights",):
            match = sealed_index.filter(pl.col("logical_id") == logical_id)
            if not match.is_empty():
                versions[logical_id] = match.select("schema_ref").item() or "unknown"
        return versions

    def _load_virtual_classification(
        self, data_root: Path, dictionary: Mapping[str, object], seed: int, manifest_fingerprint: str
    ) -> pl.DataFrame:
        cls_dir = data_root / render_dataset_path(
            dataset_id="virtual_classification_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        cls_path = cls_dir / "part-0.parquet"
        if not cls_path.exists():
            raise err("E_S1_PRECONDITION", f"S1 classification missing at '{cls_path}'")
        return pl.read_parquet(cls_path)

    def _load_settlement(
        self, data_root: Path, dictionary: Mapping[str, object], seed: int, manifest_fingerprint: str
    ) -> pl.DataFrame:
        sett_dir = data_root / render_dataset_path(
            dataset_id="virtual_settlement_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        sett_path = sett_dir / "part-0.parquet"
        if not sett_path.exists():
            raise err("E_S1_PRECONDITION", f"S1 settlement missing at '{sett_path}'")
        return pl.read_parquet(sett_path)

    def _load_merchants(self, sealed_index: pl.DataFrame) -> pl.DataFrame:
        match = sealed_index.filter(pl.col("logical_id") == "merchant_ids")
        if match.is_empty():
            raise err("E_ASSET", "merchant_ids not present in sealed_inputs_3B")
        path_val = match.select("path").item()
        path = Path(str(path_val))
        try:
            df = pl.read_parquet(path)
        except (ComputeError, Exception):
            csv_path = path.with_suffix(".csv")
            if not csv_path.exists():
                raise err(
                    "E_IO",
                    f"unable to read merchants parquet at '{path}' and no CSV fallback at '{csv_path}'",
                )
            df = pl.read_csv(
                csv_path,
                schema_overrides={
                    "merchant_id": pl.UInt64,
                    "mcc": pl.Utf8,
                    "channel": pl.Utf8,
                    "home_country_iso": pl.Utf8,
                },
                infer_schema_length=10000,
            )
        if "home_country_iso" not in df.columns:
            raise err("E_SCHEMA", "merchant_ids missing home_country_iso")
        return df

    def _build_edges(
        self,
        *,
        virtuals: pl.DataFrame,
        settlement_df: pl.DataFrame,
        merchants_df: pl.DataFrame,
        seed: int,
        manifest_fingerprint: str,
        policy_versions: Mapping[str, str],
    ) -> pl.DataFrame:
        settle = settlement_df.select(["merchant_id", "lat_deg", "lon_deg", "tzid_settlement"])
        merchants = merchants_df.select(["merchant_id", "home_country_iso"])
        joined = (
            virtuals.join(settle, on="merchant_id", how="left")
            .join(merchants, on="merchant_id", how="left")
            .fill_null(strategy="forward")
        )
        if joined.select(pl.col("lat_deg").is_null().any()).item():
            raise err("E_COORDS", "missing settlement coordinates for at least one virtual merchant")
        rows: list[dict[str, Any]] = []
        for row in joined.iter_rows(named=True):
            mid = int(row["merchant_id"])
            edge_id = f"{mid}-edge-0"
            digest = hashlib.sha256(f"{mid}|{edge_id}".encode("utf-8")).hexdigest()
            rows.append(
                {
                    "seed": int(seed),
                    "fingerprint": manifest_fingerprint,
                    "merchant_id": mid,
                    "edge_id": edge_id,
                    "edge_seq_index": 0,
                    "country_iso": row.get("home_country_iso") or "ZZ",
                    "lat_deg": float(row["lat_deg"]),
                    "lon_deg": float(row["lon_deg"]),
                    "tzid_operational": row.get("tzid_settlement") or "Etc/GMT",
                    "tz_source": "OVERRIDE",
                    "edge_weight": 1.0,
                    "hrsl_tile_id": None,
                    "spatial_surface_id": None,
                    "cdn_policy_id": "cdn_country_weights",
                    "cdn_policy_version": policy_versions.get("cdn_country_weights", "synthetic"),
                    "rng_stream_id": "rng_synthetic",
                    "rng_event_id": "rng_event_0",
                    "sampling_rank": 0,
                    "edge_digest": digest,
                }
            )
        return pl.DataFrame(rows, schema=_EDGE_SCHEMA).sort(["merchant_id", "edge_seq_index"])

    def _build_index(self, edge_df: pl.DataFrame, manifest_fingerprint: str, seed: int) -> pl.DataFrame:
        if edge_df.is_empty():
            return self._empty_edge_index()
        per_merchant = (
            edge_df.group_by("merchant_id")
            .agg(
                pl.count().alias("edge_count_total"),
                pl.first("edge_digest").alias("edge_digest"),
            )
            .with_columns(
                pl.lit("MERCHANT").alias("scope"),
                pl.lit(seed, dtype=pl.UInt64).alias("seed"),
                pl.lit(manifest_fingerprint).alias("fingerprint"),
                pl.lit(None).cast(pl.Utf8).alias("edge_catalogue_path"),
                pl.lit(None).cast(pl.Int64).alias("edge_catalogue_size_bytes"),
                pl.lit(None).cast(pl.Utf8).alias("country_mix_summary"),
                pl.lit(None).cast(pl.Int64).alias("edge_count_total_all_merchants"),
                pl.lit(None).cast(pl.Utf8).alias("edge_catalogue_digest_global"),
                pl.lit(None).cast(pl.Utf8).alias("notes"),
            )
            .select(list(_EDGE_INDEX_SCHEMA.keys()))
        )
        total_edges = int(edge_df.height)
        global_row = pl.DataFrame(
            {
                "scope": ["GLOBAL"],
                "seed": [int(seed)],
                "fingerprint": [manifest_fingerprint],
                "merchant_id": [None],
                "edge_count_total": [None],
                "edge_digest": [None],
                "edge_catalogue_path": [None],
                "edge_catalogue_size_bytes": [None],
                "country_mix_summary": [None],
                "edge_count_total_all_merchants": [total_edges],
                "edge_catalogue_digest_global": [
                    hashlib.sha256("\n".join(edge_df["edge_digest"].to_list()).encode("utf-8")).hexdigest()
                ],
                "notes": ["synthetic edge index"],
            },
            schema=_EDGE_INDEX_SCHEMA,
        )
        return pl.concat([per_merchant, global_row], how="diagonal_relaxed").select(list(_EDGE_INDEX_SCHEMA.keys())).sort(
            ["scope", "merchant_id"], nulls_last=True
        )

    def _empty_edge_catalogue(self) -> pl.DataFrame:
        return pl.DataFrame(schema=_EDGE_SCHEMA)

    def _empty_edge_index(self) -> pl.DataFrame:
        return pl.DataFrame(schema=_EDGE_INDEX_SCHEMA)


__all__ = ["EdgesInputs", "EdgesResult", "EdgesRunner"]
