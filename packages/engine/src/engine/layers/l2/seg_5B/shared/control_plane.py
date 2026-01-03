"""Shared helpers for loading Segment 5B control-plane artefacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Mapping, MutableMapping, Sequence

import polars as pl

from .dictionary import load_dictionary, render_dataset_path


@dataclass(frozen=True)
class ScenarioBinding:
    """Scenario metadata resolved from 5A's scenario manifest."""

    scenario_id: str
    horizon_start_utc: str | None = None
    horizon_end_utc: str | None = None
    is_baseline: bool = False
    is_stress: bool = False
    labels: tuple[str, ...] = ()


def load_control_plane(
    *,
    data_root: Path,
    manifest_fingerprint: str,
    parameter_hash: str,
    dictionary_path: Path | None = None,
) -> tuple[Mapping[str, object], pl.DataFrame, list[ScenarioBinding]]:
    """Load `s0_gate_receipt_5B`, `sealed_inputs_5B`, and scenario bindings."""

    dictionary = load_dictionary(dictionary_path)
    template_args = {"manifest_fingerprint": manifest_fingerprint}
    sealed_path = data_root / render_dataset_path(
        dataset_id="sealed_inputs_5B", template_args=template_args, dictionary=dictionary
    )
    receipt_path = data_root / render_dataset_path(
        dataset_id="s0_gate_receipt_5B", template_args=template_args, dictionary=dictionary
    )

    if not sealed_path.exists():
        raise FileNotFoundError(f"sealed_inputs_5B missing at {sealed_path}")
    if not receipt_path.exists():
        raise FileNotFoundError(f"s0_gate_receipt_5B missing at {receipt_path}")

    sealed_df = pl.read_parquet(sealed_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    _assert_gate_consistency(receipt, manifest_fingerprint, parameter_hash)
    _assert_inventory_consistency(sealed_df, manifest_fingerprint, parameter_hash)
    _validate_sealed_inputs_digest(sealed_df, receipt)

    scenario_bindings = _load_scenario_bindings(
        data_root=data_root,
        manifest_fingerprint=manifest_fingerprint,
        dictionary=dictionary,
    )

    return receipt, sealed_df, scenario_bindings


def _assert_gate_consistency(
    receipt: Mapping[str, object], manifest_fingerprint: str, parameter_hash: str
) -> None:
    if receipt.get("manifest_fingerprint") != manifest_fingerprint:
        raise ValueError("s0_gate_receipt_5B manifest_fingerprint mismatch")
    if receipt.get("parameter_hash") != parameter_hash:
        raise ValueError("s0_gate_receipt_5B parameter_hash mismatch")


def _assert_inventory_consistency(
    sealed_df: pl.DataFrame, manifest_fingerprint: str, parameter_hash: str
) -> None:
    mf_values = sealed_df["manifest_fingerprint"].unique().to_list()
    if mf_values and (len(mf_values) != 1 or mf_values[0] != manifest_fingerprint):
        raise ValueError("sealed_inputs_5B manifest_fingerprint mismatch")
    param_values = sealed_df["parameter_hash"].unique().to_list()
    if param_values and (len(param_values) != 1 or param_values[0] != parameter_hash):
        raise ValueError("sealed_inputs_5B parameter_hash mismatch")


def _validate_sealed_inputs_digest(sealed_df: pl.DataFrame, receipt: Mapping[str, object]) -> None:
    rows = sealed_df.sort(["owner_layer", "owner_segment", "artifact_id"]).to_dicts()
    digest = compute_sealed_inputs_digest(rows)
    expected = receipt.get("sealed_inputs_digest")
    if expected and digest != expected:
        raise ValueError("sealed_inputs_5B digest mismatch with s0_gate_receipt_5B")


def compute_sealed_inputs_digest(rows: Sequence[Mapping[str, object]]) -> str:
    buffer = bytearray()
    for row in rows:
        buffer.extend(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
    import hashlib

    return hashlib.sha256(buffer).hexdigest()


def _load_scenario_bindings(
    *,
    data_root: Path,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object],
) -> list[ScenarioBinding]:
    manifest_path = data_root / render_dataset_path(
        dataset_id="scenario_manifest_5A",
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    if not manifest_path.exists():
        fallback = str(manifest_path)
        token = f"fingerprint={manifest_fingerprint}"
        if token in fallback:
            fallback = fallback.replace(token, "fingerprint=baseline", 1)
        fallback_path = Path(fallback)
        if fallback_path.exists():
            manifest_path = fallback_path

    bindings: list[ScenarioBinding] = []
    if manifest_path.exists():
        manifest_df = pl.read_parquet(manifest_path)
        for row in manifest_df.to_dicts():
            bindings.append(
                ScenarioBinding(
                    scenario_id=str(row.get("scenario_id")),
                    horizon_start_utc=row.get("horizon_start_utc"),
                    horizon_end_utc=row.get("horizon_end_utc"),
                    is_baseline=bool(row.get("is_baseline")),
                    is_stress=bool(row.get("is_stress")),
                    labels=tuple(row.get("labels") or ()),
                )
            )
    return bindings


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

    def require(self, artifact_id: str) -> Mapping[str, object]:
        for row in self._rows:
            if row.get("artifact_id") == artifact_id:
                return row
        raise FileNotFoundError(f"sealed input '{artifact_id}' not present for this fingerprint")

    def resolve_files(
        self,
        artifact_id: str,
        *,
        template_overrides: Mapping[str, str] | None = None,
    ) -> list[Path]:
        row = self.require(artifact_id)
        template = str(row.get("path_template") or "").strip()
        if not template:
            raise ValueError(f"sealed input '{artifact_id}' missing path_template")
        merged_args = dict(self._template_args)
        if template_overrides:
            merged_args.update(template_overrides)
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

def parse_partition_keys(path_template: str) -> tuple[str, ...]:
    """Infer partition keys from a path template."""

    formatter = Formatter()
    keys = []
    for _, field, _, _ in formatter.parse(path_template):
        if field and field not in keys:
            keys.append(field)
    return tuple(keys)


__all__ = [
    "ScenarioBinding",
    "SealedInventory",
    "compute_sealed_inputs_digest",
    "load_control_plane",
    "parse_partition_keys",
]
