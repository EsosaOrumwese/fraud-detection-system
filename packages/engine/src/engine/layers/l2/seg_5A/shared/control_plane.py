"""Shared helpers for loading Segment 5A control-plane artefacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Mapping, MutableMapping, Sequence

import polars as pl

from .dictionary import load_dictionary, render_dataset_path


@dataclass(frozen=True)
class ScenarioBinding:
    """Scenario metadata resolved from the gate outputs."""

    scenario_id: str
    scenario_version: str | None = None
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
    """Load `s0_gate_receipt_5A`, `sealed_inputs_5A`, and optional scenario bindings."""

    dictionary = load_dictionary(dictionary_path)
    template_args = {"manifest_fingerprint": manifest_fingerprint}
    sealed_path = data_root / render_dataset_path(
        dataset_id="sealed_inputs_5A", template_args=template_args, dictionary=dictionary
    )
    receipt_path = data_root / render_dataset_path(
        dataset_id="s0_gate_receipt_5A", template_args=template_args, dictionary=dictionary
    )

    if not sealed_path.exists():
        raise FileNotFoundError(f"sealed_inputs_5A missing at {sealed_path}")
    if not receipt_path.exists():
        raise FileNotFoundError(f"s0_gate_receipt_5A missing at {receipt_path}")

    sealed_df = pl.read_parquet(sealed_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    _assert_gate_consistency(receipt, manifest_fingerprint, parameter_hash)
    _assert_inventory_consistency(sealed_df, manifest_fingerprint, parameter_hash)
    _validate_sealed_inputs_digest(sealed_df, receipt)

    scenario_bindings = _load_scenario_bindings(
        data_root=data_root,
        manifest_fingerprint=manifest_fingerprint,
        dictionary=dictionary,
        receipt=receipt,
    )

    return receipt, sealed_df, scenario_bindings


def _assert_gate_consistency(
    receipt: Mapping[str, object], manifest_fingerprint: str, parameter_hash: str
) -> None:
    if receipt.get("manifest_fingerprint") != manifest_fingerprint:
        raise ValueError("s0_gate_receipt_5A manifest_fingerprint mismatch")
    if receipt.get("parameter_hash") != parameter_hash:
        raise ValueError("s0_gate_receipt_5A parameter_hash mismatch")


def _assert_inventory_consistency(
    sealed_df: pl.DataFrame, manifest_fingerprint: str, parameter_hash: str
) -> None:
    mf_values = sealed_df["manifest_fingerprint"].unique().to_list()
    if mf_values and (len(mf_values) != 1 or mf_values[0] != manifest_fingerprint):
        raise ValueError("sealed_inputs_5A manifest_fingerprint mismatch")
    param_values = sealed_df["parameter_hash"].unique().to_list()
    if param_values and (len(param_values) != 1 or param_values[0] != parameter_hash):
        raise ValueError("sealed_inputs_5A parameter_hash mismatch")


def _validate_sealed_inputs_digest(sealed_df: pl.DataFrame, receipt: Mapping[str, object]) -> None:
    rows = sealed_df.sort(["owner_layer", "owner_segment", "artifact_id"]).to_dicts()
    digest = compute_sealed_inputs_digest(rows)
    expected = receipt.get("sealed_inputs_digest")
    if expected and digest != expected:
        raise ValueError("sealed_inputs_5A digest mismatch with s0_gate_receipt_5A")


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
    receipt: Mapping[str, object],
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
                    scenario_version=row.get("scenario_version"),
                    horizon_start_utc=row.get("horizon_start_utc"),
                    horizon_end_utc=row.get("horizon_end_utc"),
                    is_baseline=bool(row.get("is_baseline")),
                    is_stress=bool(row.get("is_stress")),
                    labels=tuple(row.get("labels") or ()),
                )
            )
    else:
        scenario_value = receipt.get("scenario_id")
        if isinstance(scenario_value, str):
            scenario_ids = [scenario_value]
        elif isinstance(scenario_value, Sequence):
            scenario_ids = [str(item) for item in scenario_value if item]
        else:
            scenario_ids = ["baseline"]
        for scenario_id in scenario_ids:
            bindings.append(
                ScenarioBinding(
                    scenario_id=scenario_id,
                    scenario_version=receipt.get("scenario_pack_id"),
                    is_baseline=scenario_id.lower() == "baseline",
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
        source_manifest = self._extract_manifest_override(row.get("notes"))
        if source_manifest:
            merged_args["manifest_fingerprint"] = source_manifest
            merged_args["fingerprint"] = source_manifest
        base_dir = self._select_base_dir(template)
        return expand_dataset_files(
            base_path=base_dir,
            template=template,
            template_args=merged_args,
            dataset_id=artifact_id,
        )

    def _select_base_dir(self, template: str) -> Path:
        normalized = template.strip()
        repo_prefixes = ("config/", "contracts/", "reference/", "docs/", "packages/", "scripts/", "artefacts/")
        if normalized.startswith(repo_prefixes) or normalized.startswith("runs/"):
            return self._repo_root
        return self._base_path

    @staticmethod
    def _extract_manifest_override(notes: object) -> str | None:
        if not isinstance(notes, str):
            return None
        for part in notes.split(";"):
            part = part.strip()
            if part.startswith("source_manifest="):
                _, _, value = part.partition("=")
                value = value.strip()
                if value:
                    return value
        return None


def expand_dataset_files(
    *,
    base_path: Path,
    template: str,
    template_args: Mapping[str, object],
    dataset_id: str,
) -> list[Path]:
    glob_pattern = _template_to_glob(template, template_args)
    candidate_paths = sorted(base_path.glob(glob_pattern))
    if not candidate_paths:
        raise FileNotFoundError(f"no artefacts found for '{dataset_id}' using pattern '{glob_pattern}'")
    files: list[Path] = []
    for candidate in candidate_paths:
        if candidate.is_file():
            files.append(candidate)
        elif candidate.is_dir():
            files.extend([child for child in candidate.rglob("*") if child.is_file()])
    if not files:
        raise FileNotFoundError(f"dataset '{dataset_id}' resolved to empty directory '{glob_pattern}'")
    return files


def _template_to_glob(template: str, template_args: Mapping[str, object]) -> str:
    partially_rendered = _partial_format_template(template, template_args)
    pattern = re.sub(r"\{[^}]+\}", "*", partially_rendered)
    if pattern.endswith("/"):
        pattern = f"{pattern}*"
    return pattern.replace("\\", "/").strip()


def _partial_format_template(template: str, template_args: Mapping[str, object]) -> str:
    formatter = Formatter()
    rendered: list[str] = []
    for literal, field, format_spec, _ in formatter.parse(template):
        rendered.append(literal)
        if field is None:
            continue
        if field in template_args:
            rendered.append(format(template_args[field], format_spec))
        else:
            rendered.append(f"{{{field}}}")
    return "".join(rendered)


__all__ = [
    "ScenarioBinding",
    "SealedInventory",
    "compute_sealed_inputs_digest",
    "expand_dataset_files",
    "load_control_plane",
]
