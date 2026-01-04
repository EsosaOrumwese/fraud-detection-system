"""High-level orchestration for Segment 3A S0 gate."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional, Sequence

import polars as pl
from ...shared.dictionary import (
    default_dictionary_path,
    get_dataset_entry,
    load_dictionary,
    render_dataset_path,
    repository_root,
)
from engine.shared.run_bundle import RunBundleError, materialize_repo_asset
from ...shared.run_report import SegmentStateKey, write_segment_state_run_report
from ..exceptions import S0GateError, err
from ..l0 import (
    ArtifactDigest,
    BundleIndex,
    compute_index_digest,
    hash_files,
    load_index,
    read_pass_flag,
)
from ..l1.sealed_inputs import SealedArtefact, ensure_unique_assets


logger = logging.getLogger(__name__)


def _format_utc(dt: datetime) -> str:
    """Render a UTC timestamp with fixed microsecond precision and trailing Z."""

    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass(frozen=True)
class GateInputs:
    """Configuration required to execute the 3A S0 gate."""

    base_path: Path
    output_base_path: Path
    seed: int | str
    upstream_manifest_fingerprint: str
    parameter_hash: str
    git_commit_hex: str
    dictionary_path: Optional[Path] = None
    validation_bundle_1a: Optional[Path] = None
    validation_bundle_1b: Optional[Path] = None
    validation_bundle_2a: Optional[Path] = None
    notes: Optional[str] = None
    parameter_asset_ids: tuple[str, ...] = field(
        default_factory=lambda: (
            "zone_mixture_policy",
            "country_zone_alphas",
            "zone_floor_policy",
            "day_effect_policy_v1",
        )
    )
    emit_run_report_stdout: bool = True

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
            raise err(
                "E_UPSTREAM_FINGERPRINT",
                "upstream manifest fingerprint must be 64 hex characters",
            )
        if len(self.parameter_hash) != 64:
            raise err(
                "E_PARAMETER_HASH",
                "parameter hash must be 64 hex characters",
            )
        int(self.parameter_hash, 16)
        git_hex = self.git_commit_hex.lower()
        if len(git_hex) not in (40, 64):
            raise err(
                "E_GIT_COMMIT_LEN",
                "git commit hex must be 40 (SHA1) or 64 (SHA256) characters",
            )
        int(git_hex, 16)  # raises ValueError if not hex
        object.__setattr__(self, "git_commit_hex", git_hex)


@dataclass(frozen=True)
class GateOutputs:
    """Result bundle emitted by :class:`S0GateRunner`."""

    manifest_fingerprint: str
    parameter_hash: str
    flag_sha256_hex: str
    receipt_path: Path
    sealed_inputs_path: Path
    sealed_assets: tuple[SealedArtefact, ...]
    validation_bundles: Mapping[str, Path]
    verified_at_utc: datetime


class S0GateRunner:
    """High-level helper that wires together the 3A S0 workflow."""

    _ASSET_SPECS: Mapping[str, Mapping[str, object]] = {
        "zone_mixture_policy": {"owner": "3A", "kind": "policy", "base": "repo"},
        "country_zone_alphas": {"owner": "3A", "kind": "policy", "base": "repo"},
        "zone_floor_policy": {"owner": "3A", "kind": "policy", "base": "repo"},
        "day_effect_policy_v1": {"owner": "2B", "kind": "policy", "base": "repo"},
        "outlet_catalogue": {
            "owner": "1A",
            "kind": "egress",
            "base": "base",
            "tokens": lambda inputs: {
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
            },
        },
        "site_timezones": {
            "owner": "2A",
            "kind": "egress",
            "base": "base",
            "tokens": lambda inputs: {
                "seed": inputs.seed,
                "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
            },
        },
        "tz_timetable_cache": {
            "owner": "2A",
            "kind": "cache",
            "base": "base",
            "tokens": lambda inputs: {
                "manifest_fingerprint": inputs.upstream_manifest_fingerprint,
            },
        },
        "iso3166_canonical_2024": {"owner": "ingress", "kind": "reference", "base": "repo"},
        "tz_world_2025a": {"owner": "ingress", "kind": "reference", "base": "repo"},
    }
    _POLICY_IDS = {
        "zone_mixture_policy",
        "country_zone_alphas",
        "zone_floor_policy",
        "day_effect_policy_v1",
    }

    def run(self, inputs: GateInputs) -> GateOutputs:
        dictionary_path = inputs.dictionary_path or default_dictionary_path()
        dictionary = load_dictionary(dictionary_path)
        self._dictionary = dictionary
        run_started_at = datetime.now(timezone.utc)
        gate_timer = time.perf_counter()

        # verify upstream bundles
        upstream_bundles = self._verify_upstream_bundles(inputs=inputs, dictionary=dictionary)
        gate_verify_ms = int(round((time.perf_counter() - gate_timer) * 1000))

        sealed_assets = self._collect_sealed_assets(
            inputs=inputs, dictionary=dictionary, upstream_bundles=upstream_bundles
        )

        parameter_resolved = self._load_parameter_hash_resolved(
            bundle_path=upstream_bundles["1A"]["path"]
        )
        self._verify_parameter_hash(
            inputs=inputs,
            parameter_resolved=parameter_resolved,
            sealed_assets=sealed_assets,
        )
        manifest_fingerprint = inputs.upstream_manifest_fingerprint
        parameter_hash = inputs.parameter_hash

        receipt_path, verified_at = self._write_receipt(
            inputs=inputs,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            upstream_bundles=upstream_bundles,
            sealed_assets=sealed_assets,
            gate_verify_ms=gate_verify_ms,
            run_started_at=run_started_at,
        )
        sealed_inputs_path = self._write_sealed_inputs(
            inputs=inputs,
            manifest_fingerprint=manifest_fingerprint,
            sealed_assets=sealed_assets,
        )
        run_report_path = inputs.output_base_path / render_dataset_path(
            dataset_id="segment_state_runs",
            template_args={},
            dictionary=dictionary,
        )
        self._write_segment_run_report(
            inputs=inputs,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            start_at=run_started_at,
            verified_at=verified_at,
            gate_verify_ms=gate_verify_ms,
            sealed_inputs_path=sealed_inputs_path,
            receipt_path=receipt_path,
            run_report_path=run_report_path,
        )

        return GateOutputs(
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            flag_sha256_hex=",".join(
                sorted(str(info["sha256_hex"]) for info in upstream_bundles.values())
            ),
            receipt_path=receipt_path,
            sealed_inputs_path=sealed_inputs_path,
            sealed_assets=tuple(sealed_assets),
            validation_bundles={k: v["path"] for k, v in upstream_bundles.items()},
            verified_at_utc=verified_at,
        )

    # -------------------- internal helpers --------------------
    def _verify_upstream_bundles(
        self,
        *,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
    ) -> dict[str, Mapping[str, object]]:
        base = inputs.base_path
        fingerprint = inputs.upstream_manifest_fingerprint
        segments = {
            "1A": ("validation_bundle_1A", "validation_passed_flag_1A", "validation_bundle_1a"),
            "1B": ("validation_bundle_1B", "validation_passed_flag_1B", "validation_bundle_1b"),
            "2A": ("validation_bundle_2A", "validation_passed_flag_2A", "validation_bundle_2a"),
        }

        results: dict[str, Mapping[str, object]] = {}
        for segment, (bundle_id, flag_id, attr_name) in segments.items():
            expected_root = base / render_dataset_path(
                dataset_id=bundle_id,
                template_args={"manifest_fingerprint": fingerprint},
                dictionary=dictionary,
            )
            expected_bundle_path = self._resolve_bundle_path(expected_root)
            expected_flag_path = base / render_dataset_path(
                dataset_id=flag_id,
                template_args={"manifest_fingerprint": fingerprint},
                dictionary=dictionary,
            )
            provided_path = getattr(inputs, attr_name)
            candidate_path = self._resolve_bundle_path(provided_path or expected_root)
            if candidate_path.resolve() != expected_bundle_path.resolve():
                raise err(
                    "E_BUNDLE_PATH",
                    f"{segment} validation bundle path mismatch (expected {expected_bundle_path}, got {candidate_path})",
                )
            if expected_flag_path.resolve() != (candidate_path / "_passed.flag").resolve():
                raise err(
                    "E_FLAG_PATH",
                    f"{segment} pass flag path mismatch (expected {expected_flag_path})",
                )
            logger.info("S0 bundle check: segment=%s, bundle_path=%s", segment, candidate_path)
            if not candidate_path.exists() or not candidate_path.is_dir():
                raise err("E_BUNDLE_MISSING", f"{segment} validation bundle missing at {candidate_path}")
            bundle_index = load_index(candidate_path)
            computed_flag = compute_index_digest(candidate_path, bundle_index)
            declared_flag = read_pass_flag(candidate_path)
            if computed_flag != declared_flag:
                raise err(
                    "E_FLAG_HASH_MISMATCH",
                    f"{segment} computed digest does not match _passed.flag",
                )
            object.__setattr__(inputs, attr_name, candidate_path)
            entry = get_dataset_entry(bundle_id, dictionary=dictionary)
            schema_ref = entry.get("schema_ref")
            if not isinstance(schema_ref, str) or not schema_ref:
                raise err("E_SCHEMA_REF", f"schema_ref missing for {bundle_id}")
            results[segment] = {
                "path": candidate_path,
                "sha256_hex": declared_flag,
                "schema_ref": schema_ref,
                "role": entry.get("description", bundle_id),
                "license_class": entry.get("licence", "Proprietary-Internal"),
            }
        return results

    def _collect_sealed_assets(
        self,
        inputs: GateInputs,
        dictionary: Mapping[str, object],
        upstream_bundles: Mapping[str, Mapping[str, object]],
    ) -> list[SealedArtefact]:
        assets: list[SealedArtefact] = []
        repo_root = repository_root()

        # policy assets from dictionary
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
                if base_choice == "repo":
                    try:
                        resolved_path = materialize_repo_asset(
                            source_path=resolved_path, repo_root=repo_root, run_root=inputs.base_path
                        )
                    except RunBundleError as exc:
                        raise err("E_POLICY_PATH", str(exc)) from exc
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
            bundle_digests = tuple(
                hash_files(paths_to_hash, error_prefix=f"validation_bundle_{segment}")
            )
            assets.append(
                SealedArtefact(
                    owner_segment=segment,
                    artefact_kind="validation",
                    logical_id=f"validation_bundle_{segment}",
                    path=bundle_path,
                    schema_ref=str(bundle_info["schema_ref"]),
                    role=str(bundle_info["role"]),
                    license_class=str(bundle_info["license_class"]),
                    digests=bundle_digests,
                )
            )

        return ensure_unique_assets(assets)

    def _resolve_bundle_path(self, bundle_path: Path) -> Path:
        """Resolve the bundle directory even if callers point to parent/child paths."""

        candidates: list[Path] = [bundle_path]
        if bundle_path.name == "bundle":
            candidates.append(bundle_path.parent)
        else:
            candidates.append(bundle_path / "bundle")

        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                if (candidate / "index.json").exists():
                    return candidate
        return bundle_path

    def _load_parameter_hash_resolved(self, *, bundle_path: Path) -> Mapping[str, object]:
        resolved_path = bundle_path / "parameter_hash_resolved.json"
        if not resolved_path.exists():
            raise err(
                "E_PARAM_RESOLVED_MISSING",
                f"parameter_hash_resolved.json missing at {resolved_path}",
            )
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise err(
                "E_PARAM_RESOLVED_INVALID",
                "parameter_hash_resolved.json must contain a JSON object",
            )
        return payload

    def _verify_parameter_hash(
        self,
        *,
        inputs: GateInputs,
        parameter_resolved: Mapping[str, object],
        sealed_assets: Sequence[SealedArtefact],
    ) -> None:
        param_hash = parameter_resolved.get("parameter_hash")
        if not isinstance(param_hash, str) or param_hash != inputs.parameter_hash:
            raise err(
                "E_PARAMETER_HASH_MISMATCH",
                "parameter hash does not match resolved parameter hash",
            )
        filenames = parameter_resolved.get("filenames_sorted")
        if isinstance(filenames, list):
            filename_set = {str(name) for name in filenames}
            required = {
                Path(asset.path).name
                for asset in sealed_assets
                if asset.logical_id in inputs.parameter_asset_ids
            }
            missing = sorted(name for name in required if name not in filename_set)
            if missing:
                raise err(
                    "E_PARAMETER_ASSET_MISSING",
                    f"parameter_hash_resolved.json missing parameter files: {missing}",
                )
        else:
            logger.warning(
                "parameter_hash_resolved.json missing filenames_sorted; skipping parameter file membership check"
            )

    def _collect_manifest_digests(self, sealed_assets: Iterable[SealedArtefact]) -> list[ArtifactDigest]:
        digests: list[ArtifactDigest] = []
        for asset in sealed_assets:
            digests.extend(asset.digests)
        return digests

    def _write_receipt(
        self,
        inputs: GateInputs,
        manifest_fingerprint: str,
        parameter_hash: str,
        upstream_bundles: Mapping[str, BundleIndex],
        sealed_assets: Sequence[SealedArtefact],
        gate_verify_ms: int,
        run_started_at: datetime,
    ) -> tuple[Path, datetime]:
        output_dir = (
            inputs.output_base_path
            / render_dataset_path(
                dataset_id="s0_gate_receipt_3A",
                template_args={"manifest_fingerprint": manifest_fingerprint},
                dictionary=self._dictionary,
            )
        ).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        verified_at = datetime.now(timezone.utc)
        receipt_payload: MutableMapping[str, object] = {
            "version": "1.0.0",
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "seed": int(inputs.seed),
            "verified_at_utc": _format_utc(verified_at),
            "upstream_gates": {},
            "catalogue_versions": {},
            "sealed_policy_set": [],
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

        receipt_payload["sealed_policy_set"].sort(
            key=lambda row: (row["owner_segment"], row["logical_id"])
        )
        receipt_path = output_dir / "s0_gate_receipt_3A.json"
        receipt_path.write_text(json.dumps(receipt_payload, indent=2))
        return receipt_path, verified_at

    def _write_sealed_inputs(
        self,
        inputs: GateInputs,
        manifest_fingerprint: str,
        sealed_assets: Sequence[SealedArtefact],
    ) -> Path:
        output_path = inputs.output_base_path / render_dataset_path(
            dataset_id="sealed_inputs_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=self._dictionary,
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
            segment="3A",
            state="S0",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=inputs.seed,
        )
        payload = {
            **key.as_dict(),
            "status": "PASS",
            "attempt": 1,
            "run_started_at_utc": _format_utc(start_at),
            "verified_at_utc": _format_utc(verified_at),
            "elapsed_ms": gate_verify_ms,
            "sealed_inputs_path": str(sealed_inputs_path),
            "receipt_path": str(receipt_path),
            "notes": inputs.notes,
        }
        return write_segment_state_run_report(path=run_report_path, key=key, payload=payload)
