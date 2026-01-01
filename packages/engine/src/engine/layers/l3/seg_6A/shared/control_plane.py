"""Shared helpers for loading Segment 6A control-plane artefacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Mapping, Sequence

import polars as pl

from .dictionary import load_dictionary, render_dataset_path


@dataclass(frozen=True)
class GateReceipt:
    manifest_fingerprint: str
    parameter_hash: str
    sealed_inputs_digest: str
    payload: Mapping[str, object]


def load_control_plane(
    *,
    data_root: Path,
    manifest_fingerprint: str,
    parameter_hash: str,
    dictionary_path: Path | None = None,
) -> tuple[GateReceipt, pl.DataFrame]:
    """Load `s0_gate_receipt_6A` and `sealed_inputs_6A` and validate digest."""

    dictionary = load_dictionary(dictionary_path)
    template_args = {"manifest_fingerprint": manifest_fingerprint}
    sealed_path = data_root / render_dataset_path(
        dataset_id="sealed_inputs_6A", template_args=template_args, dictionary=dictionary
    )
    receipt_path = data_root / render_dataset_path(
        dataset_id="s0_gate_receipt_6A", template_args=template_args, dictionary=dictionary
    )

    if not sealed_path.exists():
        raise FileNotFoundError(f"sealed_inputs_6A missing at {sealed_path}")
    if not receipt_path.exists():
        raise FileNotFoundError(f"s0_gate_receipt_6A missing at {receipt_path}")

    sealed_df = pl.read_parquet(sealed_path)
    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    _assert_receipt_consistency(receipt_payload, manifest_fingerprint, parameter_hash)
    _assert_inventory_consistency(sealed_df, manifest_fingerprint)
    _validate_sealed_inputs_digest(sealed_df, receipt_payload)

    receipt = GateReceipt(
        manifest_fingerprint=manifest_fingerprint,
        parameter_hash=parameter_hash,
        sealed_inputs_digest=str(receipt_payload.get("sealed_inputs_digest_6A", "")),
        payload=receipt_payload,
    )

    return receipt, sealed_df


def _assert_receipt_consistency(
    receipt: Mapping[str, object], manifest_fingerprint: str, parameter_hash: str
) -> None:
    if receipt.get("manifest_fingerprint") != manifest_fingerprint:
        raise ValueError("s0_gate_receipt_6A manifest_fingerprint mismatch")
    if receipt.get("parameter_hash") != parameter_hash:
        raise ValueError("s0_gate_receipt_6A parameter_hash mismatch")


def _assert_inventory_consistency(
    sealed_df: pl.DataFrame, manifest_fingerprint: str
) -> None:
    if "manifest_fingerprint" not in sealed_df.columns:
        raise ValueError("sealed_inputs_6A missing manifest_fingerprint column")
    mf_values = sealed_df["manifest_fingerprint"].unique().to_list()
    if mf_values and (len(mf_values) != 1 or mf_values[0] != manifest_fingerprint):
        raise ValueError("sealed_inputs_6A manifest_fingerprint mismatch")


def _validate_sealed_inputs_digest(
    sealed_df: pl.DataFrame, receipt: Mapping[str, object]
) -> None:
    rows = sealed_df.sort(["owner_layer", "owner_segment", "manifest_key"]).to_dicts()
    digest = compute_sealed_inputs_digest(rows)
    expected = receipt.get("sealed_inputs_digest_6A")
    if expected and digest != expected:
        raise ValueError("sealed_inputs_6A digest mismatch with s0_gate_receipt_6A")


def compute_sealed_inputs_digest(rows: Sequence[Mapping[str, object]]) -> str:
    buffer = bytearray()
    for row in rows:
        buffer.extend(
            json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        )
    import hashlib

    return hashlib.sha256(buffer).hexdigest()


class SealedInventory:
    """Helper for resolving file paths from sealed input rows."""

    def __init__(
        self,
        *,
        dataframe: pl.DataFrame,
        base_path: Path,
        repo_root: Path,
        template_args: Mapping[str, str],
    ):
        self._rows = dataframe.to_dicts()
        self._base_path = base_path
        self._repo_root = repo_root
        self._template_args = dict(template_args)

    def require(
        self,
        artifact_id: str | None = None,
        *,
        manifest_key: str | None = None,
    ) -> Mapping[str, object]:
        if artifact_id is None and manifest_key is None:
            raise ValueError("sealed input lookup requires artifact_id or manifest_key")
        for row in self._rows:
            if artifact_id is not None and row.get("artifact_id") == artifact_id:
                return row
            if manifest_key is not None and row.get("manifest_key") == manifest_key:
                return row
        label = artifact_id or manifest_key or "unknown"
        raise FileNotFoundError(f"sealed input '{label}' not present for this fingerprint")

    def resolve_files(
        self,
        artifact_id: str | None = None,
        *,
        manifest_key: str | None = None,
        template_overrides: Mapping[str, str] | None = None,
    ) -> list[Path]:
        row = self.require(artifact_id, manifest_key=manifest_key)
        template = str(row.get("path_template") or "").strip()
        if not template:
            raise ValueError(f"sealed input '{artifact_id}' missing path_template")
        merged_args = dict(self._template_args)
        if template_overrides:
            merged_args.update(template_overrides)
        source_manifest = self._extract_manifest_override(row.get("notes"))
        if source_manifest:
            merged_args["manifest_fingerprint"] = source_manifest
            merged_args["fingerprint"] = source_manifest
        base_dir = self._select_base_dir(template)
        glob_path = self._render_template(template, merged_args)
        if not glob_path:
            raise ValueError(f"sealed input '{artifact_id}' template resolved to empty path")
        return sorted(base_dir.glob(glob_path))

    def _select_base_dir(self, template: str) -> Path:
        if template.startswith("config/") or template.startswith("contracts/"):
            return self._repo_root
        return self._base_path

    def _render_template(self, template: str, args: Mapping[str, str]) -> str:
        formatter = Formatter()
        field_names = [field for _, field, _, _ in formatter.parse(template) if field]
        for field in field_names:
            if field not in args:
                raise ValueError(f"missing template arg '{field}' for sealed input")
        return template.format(**args)

    @staticmethod
    def _extract_manifest_override(notes: object) -> str | None:
        if not isinstance(notes, str) or not notes:
            return None
        match = re.search(r"source_manifest=([0-9a-f]{64})", notes)
        if match:
            return match.group(1)
        return None


def parse_partition_keys(path_template: str) -> tuple[str, ...]:
    """Infer partition keys from a path template."""

    formatter = Formatter()
    keys: list[str] = []
    for _, field, _, _ in formatter.parse(path_template):
        if field and field not in keys:
            keys.append(field)
    return tuple(keys)


__all__ = [
    "GateReceipt",
    "SealedInventory",
    "compute_sealed_inputs_digest",
    "load_control_plane",
    "parse_partition_keys",
]
