"""Segment 6A S3 instrument base runner."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import polars as pl
import yaml

from engine.layers.l3.seg_6A.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l3.seg_6A.shared.dictionary import get_dataset_entry, load_dictionary, render_dataset_path, repository_root

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InstrumentInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class InstrumentOutputs:
    instrument_base_path: Path
    account_links_path: Path
    party_holdings_path: Path
    instrument_summary_path: Path


class InstrumentRunner:
    """Builds the 6A.S3 instrument universe."""

    def run(self, inputs: InstrumentInputs) -> InstrumentOutputs:
        dictionary = load_dictionary(inputs.dictionary_path)
        repo_root = repository_root()
        receipt, sealed_df = load_control_plane(
            data_root=inputs.data_root,
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            dictionary_path=inputs.dictionary_path,
        )
        self._assert_upstream_pass(receipt.payload)
        inventory = SealedInventory(
            dataframe=sealed_df,
            base_path=inputs.data_root,
            repo_root=repo_root,
            template_args={
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
                "seed": str(inputs.seed),
            },
        )

        account_path = inputs.data_root / render_dataset_path(
            dataset_id="s2_account_base_6A",
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        account_df = pl.read_parquet(account_path)

        account_taxonomy = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("taxonomy_account_types_6A", dictionary, sealed_df)
            )[0]
        )
        instrument_taxonomy = self._load_yaml(
            inventory.resolve_files(
                manifest_key=self._manifest_key_for("taxonomy_instrument_types_6A", dictionary, sealed_df)
            )[0]
        )

        requires = {
            str(row.get("id")): bool(row.get("requires_instrument"))
            for row in (account_taxonomy.get("account_types") or [])
            if isinstance(row, Mapping)
        }
        instrument_types = [
            row for row in (instrument_taxonomy.get("instrument_types") or []) if isinstance(row, Mapping)
        ]
        schemes = [
            row for row in (instrument_taxonomy.get("schemes") or []) if isinstance(row, Mapping)
        ]
        default_scheme = str(schemes[0].get("id")) if schemes else "UNKNOWN"

        instrument_rows = []
        link_rows = []
        instrument_id = 1
        for account in account_df.to_dicts():
            account_type = str(account.get("account_type"))
            if not requires.get(account_type, False):
                continue
            instrument_type = str(instrument_types[0].get("id")) if instrument_types else "CARD"
            scheme_id = default_scheme
            instrument_rows.append(
                {
                    "instrument_id": instrument_id,
                    "account_id": account.get("account_id"),
                    "owner_party_id": account.get("owner_party_id"),
                    "instrument_type": instrument_type,
                    "scheme": scheme_id,
                    "seed": inputs.seed,
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "parameter_hash": inputs.parameter_hash,
                }
            )
            link_rows.append(
                {
                    "account_id": account.get("account_id"),
                    "instrument_id": instrument_id,
                    "instrument_type": instrument_type,
                    "scheme": scheme_id,
                }
            )
            instrument_id += 1

        instrument_df = pl.DataFrame(instrument_rows)
        instrument_base_path = inputs.data_root / render_dataset_path(
            dataset_id="s3_instrument_base_6A",
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        instrument_base_path.parent.mkdir(parents=True, exist_ok=True)
        instrument_df.write_parquet(instrument_base_path)

        links_df = pl.DataFrame(link_rows)
        account_links_path = inputs.data_root / render_dataset_path(
            dataset_id="s3_account_instrument_links_6A",
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        account_links_path.parent.mkdir(parents=True, exist_ok=True)
        links_df.write_parquet(account_links_path)

        holdings_df = (
            instrument_df.group_by(["owner_party_id", "instrument_type", "scheme"])
            .len()
            .rename({"len": "instrument_count"})
        )
        party_holdings_path = inputs.data_root / render_dataset_path(
            dataset_id="s3_party_instrument_holdings_6A",
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        party_holdings_path.parent.mkdir(parents=True, exist_ok=True)
        holdings_df.write_parquet(party_holdings_path)

        summary_df = (
            instrument_df.group_by(["instrument_type", "scheme"])
            .len()
            .rename({"len": "instrument_count"})
        )
        instrument_summary_path = inputs.data_root / render_dataset_path(
            dataset_id="s3_instrument_summary_6A",
            template_args={
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
            dictionary=dictionary,
        )
        instrument_summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_df.write_parquet(instrument_summary_path)

        logger.info("6A.S3 instruments=%s", len(instrument_rows))

        return InstrumentOutputs(
            instrument_base_path=instrument_base_path,
            account_links_path=account_links_path,
            party_holdings_path=party_holdings_path,
            instrument_summary_path=instrument_summary_path,
        )

    @staticmethod
    def _load_yaml(path: Path) -> Mapping[str, object]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            raise ValueError(f"expected mapping in {path}")
        return payload

    @staticmethod
    def _assert_upstream_pass(receipt: Mapping[str, object]) -> None:
        upstream = receipt.get("upstream_segments")
        if not isinstance(upstream, Mapping):
            raise ValueError("s0_gate_receipt_6A missing upstream_segments")
        for segment, payload in upstream.items():
            status = payload.get("status") if isinstance(payload, Mapping) else None
            if status != "PASS":
                raise RuntimeError(f"6A.S3 upstream segment {segment} not PASS")

    def _manifest_key_for(
        self,
        dataset_id: str,
        dictionary: Mapping[str, object] | Sequence[object],
        sealed_df: pl.DataFrame,
    ) -> str:
        entry = get_dataset_entry(dataset_id, dictionary=dictionary)
        path_template = str(entry.get("path") or "").strip()
        rows = sealed_df.filter(pl.col("path_template") == path_template).to_dicts()
        if rows:
            return str(rows[0].get("manifest_key"))
        return f"mlr.6A.dataset.{dataset_id}"


__all__ = ["InstrumentRunner", "InstrumentInputs", "InstrumentOutputs"]
