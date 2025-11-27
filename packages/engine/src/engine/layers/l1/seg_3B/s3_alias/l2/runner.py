"""Segment 3B S3 runner - alias tables and universe hash (synthetic)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

import polars as pl

from engine.layers.l1.seg_3B.shared import (
    SegmentStateKey,
    render_dataset_path,
    write_segment_state_run_report,
)
from engine.layers.l1.seg_3B.shared.dictionary import load_dictionary
from engine.layers.l1.seg_3B.s0_gate.exceptions import err


def _frames_equal(a: pl.DataFrame, b: pl.DataFrame) -> bool:
    try:
        return a.frame_equal(b)  # type: ignore[attr-defined]
    except AttributeError:
        try:
            return a.equals(b)  # type: ignore[attr-defined]
        except Exception:
            return False


_ALIAS_INDEX_SCHEMA = {
    "scope": pl.Utf8,
    "seed": pl.UInt64,
    "fingerprint": pl.Utf8,
    "merchant_id": pl.UInt64,
    "blob_offset_bytes": pl.Int64,
    "blob_length_bytes": pl.Int64,
    "edge_count_total": pl.Int64,
    "alias_table_length": pl.Int64,
    "merchant_alias_checksum": pl.Utf8,
    "alias_layout_version": pl.Utf8,
    "universe_hash": pl.Utf8,
    "blob_sha256_hex": pl.Utf8,
    "notes": pl.Utf8,
}


@dataclass(frozen=True)
class AliasInputs:
    data_root: Path
    manifest_fingerprint: str
    seed: int
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class AliasResult:
    alias_blob_path: Path
    alias_index_path: Path
    edge_universe_hash_path: Path
    run_report_path: Path
    resumed: bool


class AliasRunner:
    """RNG-free alias packaging over S2 outputs."""

    def run(self, inputs: AliasInputs) -> AliasResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.resolve()
        manifest_fingerprint = inputs.manifest_fingerprint
        seed = inputs.seed

        edge_df = self._load_edge_catalogue(data_root, dictionary, seed, manifest_fingerprint)
        idx_df = self._load_edge_index(data_root, dictionary, seed, manifest_fingerprint)

        alias_blob_bytes, alias_index_df, universe_hash = self._build_alias(edge_df, idx_df)

        blob_path = data_root / render_dataset_path(
            dataset_id="edge_alias_blob_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        resumed = False
        if blob_path.exists():
            existing = blob_path.read_bytes()
            if existing != alias_blob_bytes:
                raise err("E_IMMUTABILITY", f"alias blob exists at '{blob_path}' with different content")
            resumed = True
        else:
            blob_path.write_bytes(alias_blob_bytes)

        alias_index_path = data_root / render_dataset_path(
            dataset_id="edge_alias_index_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        alias_index_path.parent.mkdir(parents=True, exist_ok=True)
        if alias_index_path.exists():
            existing = pl.read_parquet(alias_index_path)
            if not _frames_equal(existing, alias_index_df):
                raise err("E_IMMUTABILITY", f"alias index exists at '{alias_index_path}' with different content")
            resumed = True
        else:
            alias_index_df.write_parquet(alias_index_path)

        universe_hash_path = data_root / render_dataset_path(
            dataset_id="edge_universe_hash_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        universe_hash_path.parent.mkdir(parents=True, exist_ok=True)
        universe_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "edge_universe_hash": universe_hash,
            "blob_sha256_hex": hashlib.sha256(alias_blob_bytes).hexdigest(),
            "notes": "synthetic alias universe hash",
        }
        if universe_hash_path.exists():
            existing = json.loads(universe_hash_path.read_text(encoding="utf-8"))
            if existing != universe_payload:
                raise err("E_IMMUTABILITY", f"universe hash exists at '{universe_hash_path}' with different content")
            resumed = True
        else:
            universe_hash_path.write_text(json.dumps(universe_payload, indent=2), encoding="utf-8")

        run_report_path = (
            data_root
            / f"runs/layer1/3B/s3_alias/seed={seed}/fingerprint={manifest_fingerprint}/run_report.json"
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer1",
            "segment": "3B",
            "state": "S3",
            "status": "PASS",
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "edges_total": edge_df.height,
            "resumed": resumed,
            "edge_universe_hash": universe_hash,
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

        key = SegmentStateKey(
            layer="layer1",
            segment="3B",
            state="S3",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash="",
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
                "output_path": str(blob_path.parent),
                "run_report_path": str(run_report_path),
                "resumed": resumed,
            },
        )

        return AliasResult(
            alias_blob_path=blob_path,
            alias_index_path=alias_index_path,
            edge_universe_hash_path=universe_hash_path,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    # ------------------------------------------------------------------ helpers
    def _load_edge_catalogue(
        self, data_root: Path, dictionary: Mapping[str, object], seed: int, manifest_fingerprint: str
    ) -> pl.DataFrame:
        cat_dir = data_root / render_dataset_path(
            dataset_id="edge_catalogue_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        cat_path = cat_dir / "part-0.parquet"
        if not cat_path.exists():
            raise err("E_S2_PRECONDITION", f"S2 edge catalogue missing at '{cat_path}'")
        return pl.read_parquet(cat_path)

    def _load_edge_index(
        self, data_root: Path, dictionary: Mapping[str, object], seed: int, manifest_fingerprint: str
    ) -> pl.DataFrame:
        idx_path = data_root / render_dataset_path(
            dataset_id="edge_catalogue_index_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not idx_path.exists():
            raise err("E_S2_PRECONDITION", f"S2 edge index missing at '{idx_path}'")
        return pl.read_parquet(idx_path)

    def _build_alias(
        self, edge_df: pl.DataFrame, idx_df: pl.DataFrame
    ) -> tuple[bytes, pl.DataFrame, str]:
        # Simple deterministic alias: one edge per merchant, uniform weight = 1.
        alias_entries: list[dict[str, Any]] = []
        blob_chunks: list[bytes] = []
        offset = 0
        for merchant_key, group in edge_df.group_by("merchant_id"):
            if isinstance(merchant_key, (list, tuple)):
                merchant_id = int(merchant_key[0])
            else:
                merchant_id = int(merchant_key)
            weights = group.select("edge_weight").to_series().to_list()
            blob_section = json.dumps(
                {"merchant_id": merchant_id, "weights": weights, "edge_ids": group["edge_id"].to_list()}
            ).encode("utf-8")
            blob_chunks.append(blob_section)
            checksum = hashlib.sha256(blob_section).hexdigest()
            alias_entries.append(
                {
                    "scope": "MERCHANT",
                    "seed": int(group.select("seed").item()),
                    "fingerprint": group.select("fingerprint").item(),
                    "merchant_id": merchant_id,
                    "blob_offset_bytes": offset,
                    "blob_length_bytes": len(blob_section),
                    "edge_count_total": len(weights),
                    "alias_table_length": len(weights),
                    "merchant_alias_checksum": checksum,
                    "alias_layout_version": "synthetic-v1",
                    "universe_hash": None,
                    "blob_sha256_hex": None,
                    "notes": "synthetic alias entry",
                }
            )
            offset += len(blob_section)
        blob_bytes = b"".join(blob_chunks)
        blob_sha = hashlib.sha256(blob_bytes).hexdigest()
        universe_hash = hashlib.sha256((blob_sha + str(edge_df.height)).encode("utf-8")).hexdigest()
        global_entry = {
            "scope": "GLOBAL",
            "seed": int(edge_df.select("seed").head(1).item() if edge_df.height else 0),
            "fingerprint": edge_df.select("fingerprint").head(1).item() if edge_df.height else "",
            "merchant_id": None,
            "blob_offset_bytes": None,
            "blob_length_bytes": len(blob_bytes),
            "edge_count_total": None,
            "alias_table_length": None,
            "merchant_alias_checksum": None,
            "alias_layout_version": "synthetic-v1",
            "universe_hash": universe_hash,
            "blob_sha256_hex": blob_sha,
            "notes": "synthetic global alias entry",
        }
        alias_entries.append(global_entry)
        alias_index_df = (
            pl.DataFrame(alias_entries, schema=_ALIAS_INDEX_SCHEMA)
            .select(
                [
                    "scope",
                    "seed",
                    "fingerprint",
                    "merchant_id",
                    "blob_offset_bytes",
                    "blob_length_bytes",
                    "edge_count_total",
                    "alias_table_length",
                    "merchant_alias_checksum",
                    "alias_layout_version",
                    "universe_hash",
                    "blob_sha256_hex",
                    "notes",
                ]
            )
            .sort(["scope", "merchant_id"], nulls_last=True)
        )
        # propagate universe hash to merchant rows for convenience
        alias_index_df = alias_index_df.with_columns(
            pl.when(pl.col("scope") == "MERCHANT")
            .then(pl.lit(universe_hash))
            .otherwise(pl.col("universe_hash"))
            .alias("universe_hash")
        )
        return blob_bytes, alias_index_df, universe_hash


__all__ = ["AliasInputs", "AliasResult", "AliasRunner"]
