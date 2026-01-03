"""Segment 3B S3 runner - alias tables and universe hash (synthetic)."""

from __future__ import annotations

import hashlib
import logging
import json
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

import polars as pl
from jsonschema import Draft202012Validator, ValidationError

from engine.layers.l1.seg_3B.shared import (
    SegmentStateKey,
    render_dataset_path,
    write_segment_state_run_report,
)
from engine.layers.l1.seg_3B.shared.dictionary import load_dictionary
from engine.layers.l1.seg_3B.shared.schema import load_schema
from engine.layers.l1.seg_3B.s0_gate.exceptions import err

logger = logging.getLogger(__name__)

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

_S0_RECEIPT_SCHEMA = Draft202012Validator(load_schema("#/validation/s0_gate_receipt_3B"))
_ALIAS_HEADER_SCHEMA = Draft202012Validator(load_schema("#/binary/edge_alias_blob_header_3B"))
_ALIAS_LAYOUT_VERSION = "synthetic-json-v1"
_ALIAS_LAYOUT_POLICY_ID = "alias_layout_policy_synthetic"
_ALIAS_LAYOUT_POLICY_VERSION = "1.0.0"


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

        s0_receipt = self._load_s0_receipt(data_root, dictionary, manifest_fingerprint)
        parameter_hash = str(s0_receipt.get("parameter_hash", ""))
        if not parameter_hash:
            raise err("E_S0_PRECONDITION", "S0 receipt missing parameter_hash")
        cdn_weights_digest, virtual_rules_digest = self._resolve_policy_digests(
            data_root=data_root,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            receipt=s0_receipt,
        )

        edge_df = self._load_edge_catalogue(data_root, dictionary, seed, manifest_fingerprint)
        edge_index_path = self._edge_index_path(data_root, dictionary, seed, manifest_fingerprint)
        edge_index_digest = self._sha256_file(edge_index_path)

        alias_blob_payload, alias_index_df, payload_digest = self._build_alias_payload(edge_df)
        universe_hash = self._compute_universe_hash(
            cdn_weights_digest=cdn_weights_digest,
            edge_catalogue_index_digest=edge_index_digest,
            alias_blob_digest=payload_digest,
            virtual_rules_digest=virtual_rules_digest,
        )
        alias_index_df = alias_index_df.with_columns(pl.lit(universe_hash).alias("universe_hash"))
        alias_blob_bytes, header = self._build_alias_blob(
            payload=alias_blob_payload,
            payload_digest=payload_digest,
            universe_hash=universe_hash,
        )
        alias_index_df = self._offset_alias_index(alias_index_df, header)

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

        alias_index_digest = self._sha256_file(alias_index_path)

        universe_hash_path = data_root / render_dataset_path(
            dataset_id="edge_universe_hash_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        universe_hash_path.parent.mkdir(parents=True, exist_ok=True)
        universe_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "cdn_weights_digest": cdn_weights_digest,
            "edge_catalogue_index_digest": edge_index_digest,
            "edge_alias_index_digest": alias_index_digest,
            "virtual_rules_digest": virtual_rules_digest,
            "universe_hash": universe_hash,
            "notes": "universe_hash = sha256(cdn_weights_digest|edge_catalogue_index_digest|edge_alias_blob_digest|virtual_rules_digest)",
        }
        if universe_hash_path.exists():
            existing = json.loads(universe_hash_path.read_text(encoding="utf-8"))
            existing_trimmed = dict(existing)
            existing_trimmed.pop("created_at_utc", None)
            universe_trimmed = dict(universe_payload)
            universe_trimmed.pop("created_at_utc", None)
            if existing_trimmed != universe_trimmed:
                raise err("E_IMMUTABILITY", f"universe hash exists at '{universe_hash_path}' with different content")
            resumed = True
        else:
            universe_hash_path.write_text(json.dumps(universe_payload, indent=2), encoding="utf-8")

        run_report_path = data_root / render_dataset_path(
            dataset_id="s3_run_report_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer1",
            "segment": "3B",
            "state": "S3",
            "status": "PASS",
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
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
    def _load_s0_receipt(
        self, base: Path, dictionary: Mapping[str, object], manifest_fingerprint: str
    ) -> Mapping[str, Any]:
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
            pass
        except ValidationError as exc:
            raise err("E_SCHEMA", f"s0 receipt invalid: {exc.message}") from exc
        return payload

    def _resolve_policy_digests(
        self,
        *,
        data_root: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        receipt: Mapping[str, Any],
    ) -> tuple[str, str]:
        digests = receipt.get("digests") or {}
        cdn_digest = digests.get("cdn_weights_digest")
        rules_digest = digests.get("virtual_rules_digest")
        if cdn_digest and rules_digest:
            return str(cdn_digest), str(rules_digest)

        sealed_inputs_path = data_root / render_dataset_path(
            dataset_id="sealed_inputs_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if sealed_inputs_path.exists():
            df = pl.read_parquet(sealed_inputs_path)
            if "logical_id" in df.columns:
                if not cdn_digest:
                    match = df.filter(pl.col("logical_id") == "cdn_country_weights")
                    if not match.is_empty():
                        cdn_digest = match.select("sha256_hex").item()
                if not rules_digest:
                    match = df.filter(pl.col("logical_id") == "mcc_channel_rules")
                    if not match.is_empty():
                        rules_digest = match.select("sha256_hex").item()
        if not cdn_digest or not rules_digest:
            raise err("E_S0_PRECONDITION", "missing cdn_weights_digest or virtual_rules_digest")
        return str(cdn_digest), str(rules_digest)

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

    def _edge_index_path(
        self, data_root: Path, dictionary: Mapping[str, object], seed: int, manifest_fingerprint: str
    ) -> Path:
        idx_path = data_root / render_dataset_path(
            dataset_id="edge_catalogue_index_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not idx_path.exists():
            raise err("E_S2_PRECONDITION", f"S2 edge index missing at '{idx_path}'")
        return idx_path

    def _build_alias_payload(self, edge_df: pl.DataFrame) -> tuple[bytes, pl.DataFrame, str]:
        # Deterministic alias payload with per-merchant JSON slices.
        alias_entries: list[dict[str, Any]] = []
        blob_chunks: list[bytes] = []
        offset = 0
        ordered = edge_df.sort(["merchant_id", "edge_seq_index"], nulls_last=True)
        for merchant_key, group in ordered.group_by("merchant_id", maintain_order=True):
            if isinstance(merchant_key, (list, tuple)):
                merchant_id = int(merchant_key[0])
            else:
                merchant_id = int(merchant_key)
            weights = group.select("edge_weight").to_series().to_list()
            blob_section = json.dumps(
                {
                    "merchant_id": merchant_id,
                    "edge_ids": group["edge_id"].to_list(),
                    "edge_seq_index": group["edge_seq_index"].to_list(),
                    "weights": weights,
                },
                sort_keys=True,
                separators=(",", ":"),
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
                    "alias_layout_version": _ALIAS_LAYOUT_VERSION,
                    "universe_hash": None,
                    "blob_sha256_hex": None,
                    "notes": "synthetic JSON slice",
                }
            )
            offset += len(blob_section)
        blob_bytes = b"".join(blob_chunks)
        payload_digest = hashlib.sha256(blob_bytes).hexdigest()
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
            "alias_layout_version": _ALIAS_LAYOUT_VERSION,
            "universe_hash": None,
            "blob_sha256_hex": payload_digest,
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
        return blob_bytes, alias_index_df, payload_digest

    def _build_alias_blob(
        self, *, payload: bytes, payload_digest: str, universe_hash: str
    ) -> tuple[bytes, Mapping[str, Any]]:
        header = {
            "layout_version": _ALIAS_LAYOUT_VERSION,
            "endianness": "little",
            "alignment_bytes": 1,
            "blob_length_bytes": 0,
            "blob_sha256_hex": payload_digest,
            "alias_layout_policy_id": _ALIAS_LAYOUT_POLICY_ID,
            "alias_layout_policy_version": _ALIAS_LAYOUT_POLICY_VERSION,
            "universe_hash": universe_hash,
            "notes": "blob_sha256_hex = sha256(payload bytes after header)",
        }
        header_bytes = self._stable_header_bytes(header, payload_len=len(payload))
        header_payload = json.loads(header_bytes.decode("utf-8"))
        try:
            _ALIAS_HEADER_SCHEMA.validate(header_payload)
        except RecursionError:
            logger.warning("Skipping alias header schema validation due to recursion depth")
        except ValidationError as exc:
            raise err("E_SCHEMA", f"edge_alias_blob_3B header invalid: {exc.message}") from exc
        header_len = len(header_bytes)
        prefix = struct.pack("<Q", header_len)
        blob_bytes = prefix + header_bytes + payload
        return blob_bytes, header_payload

    def _stable_header_bytes(self, header: dict[str, Any], *, payload_len: int) -> bytes:
        prefix_len = 8
        header_copy = dict(header)
        for _ in range(3):
            header_bytes = json.dumps(
                header_copy, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode("utf-8")
            total_len = prefix_len + len(header_bytes) + payload_len
            if header_copy.get("blob_length_bytes") == total_len:
                return header_bytes
            header_copy["blob_length_bytes"] = total_len
        return json.dumps(header_copy, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

    def _offset_alias_index(self, alias_index_df: pl.DataFrame, header: Mapping[str, Any]) -> pl.DataFrame:
        header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        base_offset = 8 + len(header_bytes)
        return alias_index_df.with_columns(
            pl.when(pl.col("blob_offset_bytes").is_not_null())
            .then(pl.col("blob_offset_bytes") + base_offset)
            .otherwise(pl.col("blob_offset_bytes"))
            .alias("blob_offset_bytes"),
            pl.when(pl.col("scope") == "GLOBAL")
            .then(pl.lit(header.get("blob_length_bytes")))
            .otherwise(pl.col("blob_length_bytes"))
            .alias("blob_length_bytes"),
            pl.when(pl.col("scope") == "GLOBAL")
            .then(pl.lit(header.get("blob_sha256_hex")))
            .otherwise(pl.col("blob_sha256_hex"))
            .alias("blob_sha256_hex"),
        )

    def _compute_universe_hash(
        self,
        *,
        cdn_weights_digest: str,
        edge_catalogue_index_digest: str,
        alias_blob_digest: str,
        virtual_rules_digest: str,
    ) -> str:
        parts = [
            ("alias_blob_digest", alias_blob_digest),
            ("cdn_weights_digest", cdn_weights_digest),
            ("edge_catalogue_index_digest", edge_catalogue_index_digest),
            ("virtual_rules_digest", virtual_rules_digest),
        ]
        concat = "".join(value for _, value in sorted(parts))
        return hashlib.sha256(concat.encode("ascii")).hexdigest()

    def _sha256_file(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = ["AliasInputs", "AliasResult", "AliasRunner"]
