"""Segment 3B S0 gate runner."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional, Sequence

import polars as pl

from engine.layers.l1.seg_3A.s0_gate.l0 import (
    ArtifactDigest,
    compute_index_digest,
    hash_files,
    load_index,
    read_pass_flag,
)
from engine.layers.l1.seg_3A.s0_gate.l1.sealed_inputs import SealedArtefact, ensure_unique_assets
from engine.layers.l1.seg_1A.s0_foundations.l1.hashing import (
    ParameterHashResult,
    compute_manifest_fingerprint,
    compute_parameter_hash,
    normalise_git_commit,
)
from engine.layers.l1.seg_3B.shared import SegmentStateKey, write_segment_state_run_report
from engine.layers.l1.seg_3B.shared.dictionary import (
    default_dictionary_path,
    load_dictionary,
    render_dataset_path,
    repository_root,
)
from engine.layers.l1.seg_3B.shared.schema import load_schema
from engine.layers.l1.seg_3B.s0_gate.exceptions import err

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GateInputs:
    base_path: Path
    output_base_path: Path
    seed: int | str
    upstream_manifest_fingerprint: str
    git_commit_hex: str
    dictionary_path: Optional[Path] = None
    validation_bundle_1a: Optional[Path] = None
    validation_bundle_1b: Optional[Path] = None
    validation_bundle_2a: Optional[Path] = None
    validation_bundle_3a: Optional[Path] = None
    notes: Optional[str] = None
    emit_run_report_stdout: bool = True
    parameter_asset_ids: tuple[str, ...] = field(
        default_factory=lambda: (
            "mcc_channel_rules",
            "virtual_settlement_coords",
            "cdn_country_weights",
            "virtual_validation_policy",
        )
    )

    def __post_init__(self) -> None:
        base = self.base_path.resolve()
        out = self.output_base_path.resolve()
        object.__setattr__(self, "base_path", base)
        object.__setattr__(self, "output_base_path", out)
        seed_str = str(self.seed)
        if not seed_str:
            raise err("E_SEED_EMPTY", "seed must be provided for S0")
        object.__setattr__(self, "seed", seed_str)
        if len(self.upstream_manifest_fingerprint) != 64:
            raise err("E_UPSTREAM_FINGERPRINT", "upstream manifest fingerprint must be 64 hex characters")
        git_hex = self.git_commit_hex.lower()
        if len(git_hex) not in (40, 64):
            raise err("E_GIT_COMMIT_LEN", "git commit hex must be 40 (SHA1) or 64 (SHA256) characters")
        int(git_hex, 16)
        object.__setattr__(self, "git_commit_hex", git_hex)


@dataclass(frozen=True)
class GateOutputs:
    manifest_fingerprint: str
    parameter_hash: str
    flag_sha256_hex: str
    receipt_path: Path
    sealed_inputs_path: Path
    run_report_path: Path
    sealed_assets: tuple[SealedArtefact, ...]
    validation_bundles: Mapping[str, Path]
    verified_at_utc: datetime


class S0GateRunner:
    """High-level helper that wires together the 3B S0 workflow."""

    _ASSET_SPECS: Mapping[str, Mapping[str, object]] = {
        "mcc_channel_rules": {"owner": "3B", "kind": "policy", "base": "repo"},
        "virtual_settlement_coords": {"owner": "3B", "kind": "reference", "base": "repo"},
        "cdn_country_weights": {"owner": "3B", "kind": "policy", "base": "repo"},
        "virtual_validation_policy": {"owner": "3B", "kind": "policy", "base": "repo"},
        "merchant_ids": {"owner": "ingress", "kind": "dataset", "base": "repo"},
        "site_locations": {
            "owner": "1B",
            "kind": "egress",
            "base": "base",
            "tokens": lambda inputs: {
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
            },
        },
        "zone_alloc": {
            "owner": "3A",
            "kind": "egress",
            "base": "base",
            "tokens": lambda inputs: {
                "seed": inputs.seed,
                "fingerprint": inputs.upstream_manifest_fingerprint,
            },
        },
    }
    _POLICY_IDS = {
        "mcc_channel_rules",
        "virtual_settlement_coords",
        "cdn_country_weights",
        "virtual_validation_policy",
    }

    def run(self, inputs: GateInputs) -> GateOutputs:
        dictionary_path = inputs.dictionary_path or default_dictionary_path()
        dictionary = load_dictionary(dictionary_path)
        run_started_at = datetime.now(timezone.utc)
        gate_timer = time.perf_counter()

        upstream_bundles = self._verify_upstream_bundles(inputs)
        gate_verify_ms = int(round((time.perf_counter() - gate_timer) * 1000))

        sealed_assets = self._collect_sealed_assets(inputs=inputs, dictionary=dictionary, upstream_bundles=upstream_bundles)

        parameter_assets = [asset for asset in sealed_assets if asset.logical_id in inputs.parameter_asset_ids]
        if not parameter_assets:
            raise err("E_PARAM_EMPTY", "no parameter assets found when computing parameter hash")

        parameter_digests: list[ArtifactDigest] = []
        for asset in parameter_assets:
            parameter_digests.extend(asset.digests)
        parameter_result = compute_parameter_hash(parameter_digests)

        manifest_digests = []
        for asset in sealed_assets:
            manifest_digests.extend(asset.digests)
        git_bytes = normalise_git_commit(bytes.fromhex(inputs.git_commit_hex))
        manifest_result = compute_manifest_fingerprint(
            manifest_digests,
            git_commit_raw=git_bytes,
            parameter_hash_bytes=bytes.fromhex(parameter_result.parameter_hash),
        )

        receipt_path, verified_at = self._write_receipt(
            inputs=inputs,
            manifest_fingerprint=manifest_result.manifest_fingerprint,
            parameter_result=parameter_result,
            upstream_bundles=upstream_bundles,
            sealed_assets=sealed_assets,
            gate_verify_ms=gate_verify_ms,
            run_started_at=run_started_at,
        )
        sealed_inputs_path = self._write_sealed_inputs(
            inputs=inputs,
            manifest_fingerprint=manifest_result.manifest_fingerprint,
            sealed_assets=sealed_assets,
        )
        run_report_path = inputs.output_base_path / render_dataset_path(
            dataset_id="segment_state_runs",
            template_args={},
            dictionary=dictionary,
        )
        self._write_segment_run_report(
            inputs=inputs,
            manifest_fingerprint=manifest_result.manifest_fingerprint,
            parameter_hash=parameter_result.parameter_hash,
            start_at=run_started_at,
            verified_at=verified_at,
            gate_verify_ms=gate_verify_ms,
            sealed_inputs_path=sealed_inputs_path,
            receipt_path=receipt_path,
            run_report_path=run_report_path,
        )

        return GateOutputs(
            manifest_fingerprint=manifest_result.manifest_fingerprint,
            parameter_hash=parameter_result.parameter_hash,
            flag_sha256_hex=",".join(sorted(str(info["sha256_hex"]) for info in upstream_bundles.values())),
            receipt_path=receipt_path,
            sealed_inputs_path=sealed_inputs_path,
            run_report_path=run_report_path,
            sealed_assets=tuple(sealed_assets),
            validation_bundles={k: v["path"] for k, v in upstream_bundles.items()},
            verified_at_utc=verified_at,
        )

    # -------------------- internal helpers --------------------
    def _verify_upstream_bundles(self, inputs: GateInputs) -> dict[str, Mapping[str, object]]:
        base = inputs.base_path
        fingerprint = inputs.upstream_manifest_fingerprint
        defaults = {
            "1A": base / f"data/layer1/1A/validation/fingerprint={fingerprint}",
            "1B": base / f"data/layer1/1B/validation/fingerprint={fingerprint}",
            "2A": base / f"data/layer1/2A/validation/fingerprint={fingerprint}/bundle",
            "3A": base / f"data/layer1/3A/validation/fingerprint={fingerprint}",
        }
        bundle_paths: dict[str, Path] = {
            "1A": inputs.validation_bundle_1a or defaults["1A"],
            "1B": inputs.validation_bundle_1b or defaults["1B"],
            "2A": inputs.validation_bundle_2a or defaults["2A"],
            "3A": inputs.validation_bundle_3a or defaults["3A"],
        }

        results: dict[str, Mapping[str, object]] = {}
        for segment, bundle_path in bundle_paths.items():
            if not bundle_path.exists() or not bundle_path.is_dir():
                raise err("E_BUNDLE_MISSING", f"{segment} validation bundle missing at {bundle_path}")
            bundle_index = load_index(bundle_path)
            computed_flag = compute_index_digest(bundle_path, bundle_index)
            declared_flag = read_pass_flag(bundle_path)
            if computed_flag != declared_flag:
                raise err("E_FLAG_HASH_MISMATCH", f"{segment} computed digest does not match _passed.flag")
            # persist resolved path on inputs for downstream use
            if segment == "1A":
                object.__setattr__(inputs, "validation_bundle_1a", bundle_path)
            elif segment == "1B":
                object.__setattr__(inputs, "validation_bundle_1b", bundle_path)
            elif segment == "2A":
                object.__setattr__(inputs, "validation_bundle_2a", bundle_path)
            else:
                object.__setattr__(inputs, "validation_bundle_3a", bundle_path)
            results[segment] = {"path": bundle_path, "sha256_hex": declared_flag}
        return results

    def _collect_sealed_assets(
        self,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        upstream_bundles: Mapping[str, Mapping[str, object]],
    ) -> list[SealedArtefact]:
        assets: list[SealedArtefact] = []
        repo_root = repository_root()

        reference_data: Sequence[Mapping[str, object]] = dictionary.get("reference_data", [])  # type: ignore[arg-type]
        policy_index = {entry["id"]: entry for entry in reference_data if "id" in entry}
        for asset_id, spec in self._ASSET_SPECS.items():
            entry = policy_index.get(asset_id)
            if entry is None:
                raise err("E_POLICY_MISSING", f"missing policy or reference '{asset_id}' in dictionary")
            token_builder = spec.get("tokens")
            template_args: Mapping[str, object]
            if callable(token_builder):
                template_args = token_builder(inputs)  # type: ignore[arg-type]
            else:
                template_args = {}
            relative_path = render_dataset_path(
                dataset_id=asset_id,
                template_args=template_args,
                dictionary=dictionary,
            )
            resolved_path = Path(relative_path)
            if not resolved_path.is_absolute():
                base_choice = spec.get("base", "repo")
                base_path = inputs.base_path if base_choice == "base" else repo_root
                resolved_path = (base_path / resolved_path).resolve()
            if not resolved_path.exists():
                raise err("E_POLICY_PATH", f"asset '{asset_id}' not found at {resolved_path}")
            if resolved_path.is_dir():
                paths_to_hash = [p for p in resolved_path.rglob("*") if p.is_file()]
                if not paths_to_hash:
                    raise err("E_POLICY_PATH", f"asset '{asset_id}' directory '{resolved_path}' is empty")
            else:
                paths_to_hash = [resolved_path]
            digests = tuple(hash_files(paths_to_hash, error_prefix=asset_id))
            assets.append(
                SealedArtefact(
                    owner_segment=str(spec["owner"]),
                    artefact_kind=str(spec["kind"]),
                    logical_id=asset_id,
                    path=resolved_path,
                    schema_ref=entry["schema_ref"],
                    role=entry.get("description", asset_id),
                    license_class=entry.get("licence", "Proprietary-Internal"),
                    digests=digests,
                    notes=entry.get("notes"),
                )
            )

        # upstream validation bundles
        for segment, bundle_info in upstream_bundles.items():
            bundle_path = bundle_info["path"]
            if bundle_path.is_dir():
                paths_to_hash = [p for p in bundle_path.rglob("*") if p.is_file()]
            else:
                paths_to_hash = [bundle_path]
            bundle_digests = tuple(hash_files(paths_to_hash, error_prefix=f"validation_bundle_{segment}"))
            assets.append(
                SealedArtefact(
                    owner_segment=segment,
                    artefact_kind="validation",
                    logical_id=f"validation_bundle_{segment}",
                    path=bundle_path,
                    schema_ref=f"schemas.{segment}.yaml#/validation/validation_bundle",
                    role=f"{segment} validation gate",
                    license_class="Proprietary-Internal",
                    digests=bundle_digests,
                )
            )

        return ensure_unique_assets(assets)

    def _write_receipt(
        self,
        inputs: GateInputs,
        manifest_fingerprint: str,
        parameter_result: ParameterHashResult,
        upstream_bundles: Mapping[str, Mapping[str, object]],
        sealed_assets: Sequence[SealedArtefact],
        gate_verify_ms: int,
        run_started_at: datetime,
    ) -> tuple[Path, datetime]:
        output_dir = (
            inputs.output_base_path
            / render_dataset_path(
                dataset_id="s0_gate_receipt_3B",
                template_args={"manifest_fingerprint": manifest_fingerprint},
                dictionary=load_dictionary(inputs.dictionary_path),
            )
        ).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        verified_at = datetime.now(timezone.utc)
        receipt_payload: MutableMapping[str, object] = {
            "version": "1.0.0",
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_result.parameter_hash,
            "seed": int(inputs.seed),
            "verified_at_utc": verified_at.isoformat(),
            "upstream_gates": {},
            "sealed_policy_set": [],
            "notes": inputs.notes,
            "digests": {},
        }

        for segment, bundle_info in upstream_bundles.items():
            bundle_path = bundle_info["path"]
            sha = bundle_info["sha256_hex"]
            receipt_payload["upstream_gates"][f"segment_{segment}"] = {
                "bundle_id": f"validation_bundle_{segment}",
                "bundle_path": str(bundle_path),
                "flag_path": str(bundle_path / "_passed.flag"),
                "sha256_hex": sha,
                "status": "PASS",
            }

        for asset in sealed_assets:
            if asset.logical_id in self._POLICY_IDS:
                receipt_payload["sealed_policy_set"].append(
                    {
                        "logical_id": asset.logical_id,
                        "owner_segment": asset.owner_segment,
                        "role": asset.role,
                        "sha256_hex": asset.sha256_hex,
                        "schema_ref": asset.schema_ref,
                        "path": str(asset.path),
                    }
                )

        receipt_payload["sealed_policy_set"].sort(key=lambda row: (row["owner_segment"], row["logical_id"]))
        digest_map: MutableMapping[str, str] = {}
        for asset in sealed_assets:
            if asset.logical_id == "mcc_channel_rules":
                digest_map["virtual_rules_digest"] = asset.sha256_hex
            elif asset.logical_id == "virtual_settlement_coords":
                digest_map["settlement_coord_digest"] = asset.sha256_hex
            elif asset.logical_id == "cdn_country_weights":
                digest_map["cdn_weights_digest"] = asset.sha256_hex
            elif asset.logical_id == "virtual_validation_policy":
                digest_map["virtual_validation_digest"] = asset.sha256_hex
        receipt_payload["digests"].update(digest_map)
        receipt_path = output_dir / "s0_gate_receipt_3B.json"
        receipt_path.write_text(json.dumps(receipt_payload, indent=2))
        return receipt_path, verified_at

    def _write_sealed_inputs(
        self,
        inputs: GateInputs,
        manifest_fingerprint: str,
        sealed_assets: Sequence[SealedArtefact],
    ) -> Path:
        output_path = inputs.output_base_path / render_dataset_path(
            dataset_id="sealed_inputs_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=load_dictionary(inputs.dictionary_path),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        rows = [asset.as_row(manifest_fingerprint) for asset in sealed_assets]
        rows.sort(
            key=lambda row: (
                row.get("owner_segment", ""),
                row.get("artefact_kind", ""),
                row.get("logical_id", ""),
                row.get("path", ""),
            )
        )
        df = pl.DataFrame(rows)
        df.write_parquet(output_path)
        return output_path

    def _write_segment_run_report(
        self,
        *,
        inputs: GateInputs,
        manifest_fingerprint: str,
        parameter_hash: str,
        start_at: datetime,
        verified_at: datetime,
        gate_verify_ms: int,
        sealed_inputs_path: Path,
        receipt_path: Path,
        run_report_path: Path,
    ) -> Path:
        key = SegmentStateKey(
            layer="layer1",
            segment="3B",
            state="S0",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=inputs.seed,
        )
        payload = {
            **key.as_dict(),
            "status": "PASS",
            "attempt": 1,
            "run_started_at_utc": start_at.isoformat(),
            "verified_at_utc": verified_at.isoformat(),
            "elapsed_ms": gate_verify_ms,
            "sealed_inputs_path": str(sealed_inputs_path),
            "receipt_path": str(receipt_path),
            "notes": inputs.notes,
        }
        return write_segment_state_run_report(path=run_report_path, key=key, payload=payload)
