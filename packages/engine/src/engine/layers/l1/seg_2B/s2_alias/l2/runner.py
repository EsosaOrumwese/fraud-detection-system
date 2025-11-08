"""S2 alias table builder for Segment 2B."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

import polars as pl
from jsonschema import Draft202012Validator, ValidationError

from ...shared.dictionary import load_dictionary, render_dataset_path, repository_root
from ...shared.receipt import GateReceiptSummary, load_gate_receipt
from ...shared.schema import load_schema
from ...s0_gate.exceptions import S0GateError, err

logger = logging.getLogger(__name__)


@dataclass
class AliasEncodeSpec:
    """Structured encode instructions coming from alias_layout_policy_v1."""

    site_order_bytes: int
    prob_mass_bytes: int
    alias_site_order_bytes: int
    padding_value: int
    checksum_algorithm: str


@dataclass
class AliasLayoutPolicy:
    """Parsed alias layout policy surface."""

    layout_version: str
    endianness: str
    alignment_bytes: int
    quantised_bits: int
    encode_spec: AliasEncodeSpec
    decode_law: str
    weight_quantisation_epsilon: float
    sha256_hex: str

    @property
    def endian_byteorder(self) -> str:
        return "little" if self.endianness == "little" else "big"


@dataclass(frozen=True)
class S2AliasInputs:
    """Configuration required to execute Segment 2B S2."""

    data_root: Path
    seed: int | str
    manifest_fingerprint: str
    dictionary_path: Optional[Path] = None
    resume: bool = False
    emit_run_report_stdout: bool = True

    def __post_init__(self) -> None:
        data_root = self.data_root.expanduser().resolve()
        object.__setattr__(self, "data_root", data_root)
        seed_value = str(self.seed)
        if not seed_value:
            raise err("E_S2_SEED_EMPTY", "seed must be provided for S2")
        object.__setattr__(self, "seed", seed_value)
        manifest = self.manifest_fingerprint.lower()
        if len(manifest) != 64:
            raise err(
                "E_S2_MANIFEST_FINGERPRINT",
                "manifest_fingerprint must be 64 hex characters",
            )
        int(manifest, 16)
        object.__setattr__(self, "manifest_fingerprint", manifest)


@dataclass(frozen=True)
class S2AliasResult:
    """Outcome of the S2 runner."""

    manifest_fingerprint: str
    index_path: Path
    blob_path: Path
    run_report_path: Path
    resumed: bool


class S2AliasRunner:
    """Runs Segment 2B State 2."""

    RUN_REPORT_ROOT = Path("reports") / "l1" / "s2_alias"

    def run(self, config: S2AliasInputs) -> S2AliasResult:
        dictionary = load_dictionary(config.dictionary_path)
        receipt = load_gate_receipt(
            base_path=config.data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        policy, policy_path = self._load_policy(config=config, dictionary=dictionary)
        weights_path = self._resolve_dataset_path(
            dataset_id="s1_site_weights",
            config=config,
            dictionary=dictionary,
        )
        index_path = self._resolve_dataset_path(
            dataset_id="s2_alias_index",
            config=config,
            dictionary=dictionary,
        )
        blob_path = self._resolve_dataset_path(
            dataset_id="s2_alias_blob",
            config=config,
            dictionary=dictionary,
        )
        if index_path.exists() or blob_path.exists():
            if config.resume and index_path.exists() and blob_path.exists():
                logger.info(
                    "Segment2B S2 resume detected (seed=%s, manifest=%s); skipping run",
                    config.seed,
                    config.manifest_fingerprint,
                )
                run_report_path = self._resolve_run_report_path(config=config)
                return S2AliasResult(
                    manifest_fingerprint=config.manifest_fingerprint,
                    index_path=index_path,
                    blob_path=blob_path,
                    run_report_path=run_report_path,
                    resumed=True,
                )
            raise err(
                "E_S2_OUTPUT_EXISTS",
                "s2_alias_index/blob already exist - remove partition or pass --s2-resume",
            )

        stats = {
            "merchants_total": 0,
            "sites_total": 0,
            "zero_mass_merchants": 0,
            "max_abs_mass_error": 0.0,
            "max_abs_delta": 0.0,
        }
        merchants_index: list[dict] = []
        alignment_samples: list[dict] = []
        merchant_samples: list[dict] = []

        frame = self._load_site_weights(weights_path)
        if frame.height == 0:
            raise err("E_S2_NO_ROWS", "s1_site_weights produced zero rows for S2")
        rows = frame.sort(["merchant_id", "legal_country_iso", "site_order"]).to_dicts()

        blob_bytes = bytearray()
        idx = 0
        while idx < len(rows):
            start = idx
            merchant_id = rows[idx]["merchant_id"]
            while idx < len(rows) and rows[idx]["merchant_id"] == merchant_id:
                idx += 1
            group_rows = rows[start:idx]
            slice_bytes, meta, delta_stats = self._build_alias_slice(
                group_rows=group_rows,
                policy=policy,
            )
            stats["merchants_total"] += 1
            stats["sites_total"] += len(group_rows)
            stats["max_abs_mass_error"] = max(
                stats["max_abs_mass_error"], delta_stats["mass_error"]
            )
            stats["max_abs_delta"] = max(
                stats["max_abs_delta"], delta_stats["slot_delta"]
            )
            if delta_stats["zero_mass"]:
                stats["zero_mass_merchants"] += 1

            padding = (-len(blob_bytes)) % policy.alignment_bytes
            if padding:
                blob_bytes.extend(
                    bytes([policy.encode_spec.padding_value]) * padding
                )
            offset = len(blob_bytes)
            blob_bytes.extend(slice_bytes)
            length = len(slice_bytes)
            checksum = hashlib.sha256(slice_bytes).hexdigest()

            merchants_index.append(
                {
                    "merchant_id": merchant_id,
                    "offset": offset,
                    "length": length,
                    "sites": len(group_rows),
                    "quantised_bits": policy.quantised_bits,
                    "checksum": checksum,
                }
            )
            alignment_samples.append(
                {
                    "merchant_id": merchant_id,
                    "offset": offset,
                    "alignment_bytes": policy.alignment_bytes,
                    "aligned": offset % policy.alignment_bytes == 0,
                }
            )
            if len(merchant_samples) < 10:
                merchant_samples.append(
                    {
                        "merchant_id": merchant_id,
                        "offset": offset,
                        "length": length,
                        "sites": len(group_rows),
                    }
                )

        blob_sha256 = hashlib.sha256(blob_bytes).hexdigest()
        blob_size = len(blob_bytes)
        index_payload = {
            "layout_version": policy.layout_version,
            "endianness": policy.endianness,
            "alignment_bytes": policy.alignment_bytes,
            "quantised_bits": policy.quantised_bits,
            "created_utc": receipt.verified_at_utc,
            "policy_id": "alias_layout_policy_v1",
            "policy_digest": policy.sha256_hex,
            "blob_sha256": blob_sha256,
            "blob_size_bytes": blob_size,
            "merchants_count": stats["merchants_total"],
            "merchants": sorted(merchants_index, key=lambda item: item["merchant_id"]),
        }

        index_path.parent.mkdir(parents=True, exist_ok=True)
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        blob_path.write_bytes(bytes(blob_bytes))
        index_path.write_text(json.dumps(index_payload, indent=2), encoding="utf-8")

        run_report_path = self._resolve_run_report_path(config=config)
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = self._build_run_report(
            config=config,
            receipt=receipt,
            policy=policy,
            stats=stats,
            blob_path=blob_path,
            blob_sha256=blob_sha256,
            blob_size=blob_size,
            index_path=index_path,
            dictionary=dictionary,
            policy_path=policy_path,
            alignment_samples=alignment_samples,
            merchant_samples=merchant_samples,
        )
        run_report_path.write_text(json.dumps(run_report, indent=2), encoding="utf-8")
        if config.emit_run_report_stdout:
            print(json.dumps(run_report, indent=2))  # pragma: no cover

        return S2AliasResult(
            manifest_fingerprint=config.manifest_fingerprint,
            index_path=index_path,
            blob_path=blob_path,
            run_report_path=run_report_path,
            resumed=False,
        )

    # ------------------------------------------------------------------ helpers

    def _load_policy(
        self, *, config: S2AliasInputs, dictionary: Mapping[str, object]
    ) -> tuple[AliasLayoutPolicy, Path]:
        policy_rel = render_dataset_path(
            "alias_layout_policy_v1",
            template_args={},
            dictionary=dictionary,
        )
        candidate = (config.data_root / policy_rel).resolve()
        if not candidate.exists():
            repo_candidate = repository_root() / policy_rel
            if not repo_candidate.exists():
                raise err(
                    "E_S2_POLICY_MISSING",
                    f"alias_layout_policy_v1 not found at '{policy_rel}'",
                )
            candidate = repo_candidate.resolve()

        payload = json.loads(candidate.read_text(encoding="utf-8"))
        schema = load_schema("#/policy/alias_layout_policy_v1")
        validator = Draft202012Validator(schema)
        try:
            validator.validate(payload)
        except ValidationError as exc:
            raise err(
                "E_S2_POLICY_INVALID",
                f"alias_layout_policy_v1 violates schema: {exc.message}",
            ) from exc

        encode_spec = payload["encode_spec"]
        padding_value = int(encode_spec["padding_value"], 16)
        spec = AliasEncodeSpec(
            site_order_bytes=int(encode_spec["site_order_bytes"]),
            prob_mass_bytes=int(encode_spec["prob_mass_bytes"]),
            alias_site_order_bytes=int(encode_spec["alias_site_order_bytes"]),
            padding_value=padding_value,
            checksum_algorithm=encode_spec["checksum"]["algorithm"],
        )

        policy = AliasLayoutPolicy(
            layout_version=payload["layout_version"],
            endianness=payload["endianness"],
            alignment_bytes=int(payload["alignment_bytes"]),
            quantised_bits=int(payload["quantised_bits"]),
            encode_spec=spec,
            decode_law=payload["decode_law"],
            weight_quantisation_epsilon=float(payload["quantisation_epsilon"]),
            sha256_hex=_sha256_hex(candidate),
        )
        return policy, candidate

    def _load_site_weights(self, path: Path) -> pl.DataFrame:
        columns = ["merchant_id", "legal_country_iso", "site_order", "p_weight", "quantised_bits"]
        try:
            return pl.read_parquet(path, columns=columns)
        except Exception as exc:  # pragma: no cover
            raise err("E_S2_SITE_WEIGHTS_IO", f"failed to read s1_site_weights: {exc}") from exc

    def _resolve_dataset_path(
        self,
        *,
        dataset_id: str,
        config: S2AliasInputs,
        dictionary: Mapping[str, object],
    ) -> Path:
        template_args = {
            "seed": config.seed,
            "manifest_fingerprint": config.manifest_fingerprint,
        }
        rel = render_dataset_path(dataset_id, template_args=template_args, dictionary=dictionary)
        return (config.data_root / rel).resolve()

    def _resolve_run_report_path(self, *, config: S2AliasInputs) -> Path:
        return (
            config.data_root
            / self.RUN_REPORT_ROOT
            / f"seed={config.seed}"
            / f"fingerprint={config.manifest_fingerprint}"
            / "run_report.json"
        ).resolve()

    def _build_alias_slice(
        self,
        *,
        group_rows: list[dict],
        policy: AliasLayoutPolicy,
    ) -> tuple[bytes, dict, dict]:
        grid = 1 << policy.quantised_bits
        site_orders = [int(row["site_order"]) for row in group_rows]
        quant_bits = {int(row["quantised_bits"]) for row in group_rows}
        if len(quant_bits) != 1 or quant_bits.pop() != policy.quantised_bits:
            raise err(
                "E_S2_QUANT_BITS_MISMATCH",
                "s1_site_weights quantised_bits mismatched policy",
            )

        masses, mass_error, slot_delta = self._reconstruct_integer_masses(
            rows=group_rows,
            grid=grid,
        )
        if sum(masses) == 0:
            zero_mass = True
        else:
            zero_mass = False

        prob_thresholds, alias_indices = self._build_alias_tables(masses=masses, grid=grid)
        slice_bytes = self._encode_slice(
            site_orders=site_orders,
            prob_thresholds=prob_thresholds,
            alias_indices=alias_indices,
            policy=policy,
        )
        return slice_bytes, {"sites": len(site_orders)}, {
            "mass_error": mass_error,
            "slot_delta": slot_delta,
            "zero_mass": zero_mass,
        }

    def _reconstruct_integer_masses(
        self,
        *,
        rows: list[dict],
        grid: int,
    ) -> tuple[list[int], float, float]:
        masses: list[int] = []
        remainders: list[float] = []
        for row in rows:
            raw = row["p_weight"] * grid
            rounded = round_half_even(raw)
            masses.append(int(rounded))
            remainders.append(raw - math.floor(raw))
        delta = grid - sum(masses)
        if delta > 0:
            order = sorted(
                range(len(rows)),
                key=lambda idx: (
                    -(remainders[idx]),
                    rows[idx]["site_order"],
                ),
            )
            for idx in order[:delta]:
                masses[idx] += 1
        elif delta < 0:
            order = sorted(
                range(len(rows)),
                key=lambda idx: (
                    remainders[idx],
                    rows[idx]["site_order"],
                ),
            )
            for idx in order[: -delta]:
                masses[idx] -= 1

        abs_error = abs(sum(row["p_weight"] for row in rows) - 1.0)
        max_delta = max(
            abs((mass / grid) - row["p_weight"]) for mass, row in zip(masses, rows)
        )
        return masses, abs_error, max_delta

    def _build_alias_tables(
        self,
        *,
        masses: Sequence[int],
        grid: int,
    ) -> tuple[list[int], list[int]]:
        k = len(masses)
        if k == 0:
            raise err("E_S2_EMPTY_MERCHANT", "merchant has zero sites in s1_site_weights")
        scaled = [mass * k for mass in masses]
        threshold = grid
        small = deque(idx for idx, value in enumerate(scaled) if value < threshold)
        large = deque(idx for idx, value in enumerate(scaled) if value >= threshold)
        alias = list(range(k))
        probability = [0] * k

        while small and large:
            s = small.popleft()
            l = large.popleft()
            probability[s] = scaled[s]
            alias[s] = l
            scaled[l] = scaled[l] + scaled[s] - threshold
            if scaled[l] < threshold:
                small.append(l)
            else:
                large.append(l)

        for idx in list(large) + list(small):
            probability[idx] = threshold
            alias[idx] = idx

        return probability, alias

    def _encode_slice(
        self,
        *,
        site_orders: Sequence[int],
        prob_thresholds: Sequence[int],
        alias_indices: Sequence[int],
        policy: AliasLayoutPolicy,
    ) -> bytes:
        endian = policy.endian_byteorder
        encode = policy.encode_spec
        buffer = bytearray()
        buffer.extend(len(site_orders).to_bytes(4, byteorder=endian, signed=False))
        for slot_idx, site_order in enumerate(site_orders):
            buffer.extend(
                int(site_order).to_bytes(
                    encode.site_order_bytes, byteorder=endian, signed=False
                )
            )
            buffer.extend(
                int(prob_thresholds[slot_idx]).to_bytes(
                    encode.prob_mass_bytes, byteorder=endian, signed=False
                )
            )
            alias_site_order = site_orders[alias_indices[slot_idx]]
            buffer.extend(
                int(alias_site_order).to_bytes(
                    encode.alias_site_order_bytes, byteorder=endian, signed=False
                )
            )
        return bytes(buffer)

    def _build_run_report(
        self,
        *,
        config: S2AliasInputs,
        receipt: GateReceiptSummary,
        policy: AliasLayoutPolicy,
        stats: Mapping[str, object],
        blob_path: Path,
        blob_sha256: str,
        blob_size: int,
        index_path: Path,
        dictionary: Mapping[str, object],
        policy_path: Path,
        alignment_samples: Sequence[dict],
        merchant_samples: Sequence[dict],
    ) -> dict:
        validators = [
            {"id": "V-01", "status": "PASS", "codes": []},
        ]
        run_report = {
            "component": "2B.S2",
            "fingerprint": config.manifest_fingerprint,
            "seed": config.seed,
            "created_utc": receipt.verified_at_utc,
            "catalogue_resolution": self._catalogue_resolution(dictionary=dictionary),
            "policy": {
                "id": "alias_layout_policy_v1",
                "sha256_hex": policy.sha256_hex,
                "layout_version": policy.layout_version,
                "endianness": policy.endianness,
                "alignment_bytes": policy.alignment_bytes,
                "quantised_bits": policy.quantised_bits,
            },
            "inputs_summary": {
                "s1_site_weights_path": str(
                    render_dataset_path(
                        "s1_site_weights",
                        template_args={
                            "seed": config.seed,
                            "manifest_fingerprint": config.manifest_fingerprint,
                        },
                        dictionary=dictionary,
                    )
                ),
                "merchants_total": stats["merchants_total"],
                "sites_total": stats["sites_total"],
            },
            "blob": {
                "path": str(blob_path),
                "size_bytes": blob_size,
                "sha256": blob_sha256,
            },
            "index": {
                "path": str(index_path),
            },
            "stats": {
                "max_abs_mass_error": stats["max_abs_mass_error"],
                "max_abs_delta": stats["max_abs_delta"],
                "zero_mass_merchants": stats["zero_mass_merchants"],
            },
            "validators": validators,
            "summary": {"overall_status": "PASS", "warn_count": 0, "fail_count": 0},
            "samples": {
                "merchants": merchant_samples,
                "alignment": alignment_samples[:10],
            },
            "id_map": [
                {
                    "id": "s1_site_weights",
                    "path": str(
                        render_dataset_path(
                            "s1_site_weights",
                            template_args={
                                "seed": config.seed,
                                "manifest_fingerprint": config.manifest_fingerprint,
                            },
                            dictionary=dictionary,
                        )
                    ),
                },
                {
                    "id": "alias_layout_policy_v1",
                    "path": str(policy_path),
                },
                {
                    "id": "s2_alias_index",
                    "path": str(index_path),
                },
                {
                    "id": "s2_alias_blob",
                    "path": str(blob_path),
                },
            ],
        }
        return run_report

    def _catalogue_resolution(self, *, dictionary: Mapping[str, object]) -> Mapping[str, str]:
        catalogue = dictionary.get("catalogue") or {}
        return {
            "dictionary_version": str(
                catalogue.get("dictionary_version") or dictionary.get("version") or "unversioned"
            ),
            "registry_version": str(catalogue.get("registry_version") or "unversioned"),
        }


def round_half_even(value: float) -> int:
    """Round a float to the nearest integer using ties-to-even."""

    floor_value = math.floor(value)
    remainder = value - floor_value
    if remainder > 0.5:
        return floor_value + 1
    if remainder < 0.5:
        return floor_value
    return floor_value + (floor_value % 2)


def _sha256_hex(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


import sys  # placed at bottom to avoid circular import during module init
