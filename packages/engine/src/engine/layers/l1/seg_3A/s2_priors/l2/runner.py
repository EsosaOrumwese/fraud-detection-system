"""Segment 3A S2 country-zone priors runner."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import polars as pl
import yaml
from jsonschema import Draft202012Validator, ValidationError

from engine.layers.l1.seg_3A.s0_gate.exceptions import err
from engine.layers.l1.seg_3A.s0_gate.l0 import aggregate_sha256, expand_files, hash_files
from engine.layers.l1.seg_3A.shared import SegmentStateKey, load_schema, write_segment_state_run_report
from engine.layers.l1.seg_3A.shared.dictionary import load_dictionary, render_dataset_path

_S0_RECEIPT_VALIDATOR = Draft202012Validator(load_schema("#/validation/s0_gate_receipt_3A"))
_SEALED_INPUT_VALIDATOR = Draft202012Validator(load_schema("#/validation/sealed_inputs_3A"))
_PRIOR_SCHEMA = Draft202012Validator(load_schema("#/policy/country_zone_alphas_v1"))
_FLOOR_SCHEMA = Draft202012Validator(load_schema("#/policy/zone_floor_policy_v1"))


def _frames_equal(a: pl.DataFrame, b: pl.DataFrame) -> bool:
    try:
        return a.frame_equal(b)  # type: ignore[attr-defined]
    except AttributeError:
        try:
            return a.equals(b)  # type: ignore[attr-defined]
        except Exception:
            return False


@dataclass(frozen=True)
class PriorsInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class PriorsResult:
    output_path: Path
    run_report_path: Path
    resumed: bool


class PriorsRunner:
    """Prepares parameter-scoped Dirichlet priors for S3."""

    def run(self, inputs: PriorsInputs) -> PriorsResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.resolve()
        manifest_fingerprint = inputs.manifest_fingerprint

        sealed_inputs_path = self._resolve_dataset_path(
            dictionary=dictionary,
            dataset_id="sealed_inputs_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            base=data_root,
        )
        receipt_path = self._resolve_dataset_path(
            dictionary=dictionary,
            dataset_id="s0_gate_receipt_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            base=data_root,
        )
        if not sealed_inputs_path.exists() or not receipt_path.exists():
            raise err("E_S0_PRECONDITION", "S0 artefacts missing; run S0 before S2")

        s0_receipt = self._load_json(receipt_path, _S0_RECEIPT_VALIDATOR)
        sealed_df = pl.read_parquet(sealed_inputs_path)
        self._validate_sealed_inputs(sealed_df)
        self._assert_upstream_pass(s0_receipt)

        sealed_index = {row["logical_id"]: row for row in sealed_df.to_dicts()}
        prior_path = self._resolve_sealed_asset(sealed_index, "country_zone_alphas")
        floor_path = self._resolve_sealed_asset(sealed_index, "zone_floor_policy")
        tz_world_path = self._resolve_sealed_asset(sealed_index, "tz_world_2025a")

        prior_payload = self._load_yaml(prior_path, _PRIOR_SCHEMA)
        floor_payload = self._load_yaml(floor_path, _FLOOR_SCHEMA)

        priors_map = self._normalise_priors(prior_payload)
        floor_map = self._normalise_floors(floor_payload)
        tz_df = pl.read_parquet(tz_world_path)
        country_col = self._detect_country_column(tz_df)
        zone_universe = self._build_zone_universe(tz_df, country_col)
        missing_countries = sorted(set(priors_map.keys()) - set(zone_universe.keys()))
        if missing_countries:
            raise err(
                "E_ZONE_DOMAIN",
                f"countries missing from zone universe: {missing_countries}",
            )

        result_df = self._build_prior_table(
            parameter_hash=inputs.parameter_hash,
            zone_universe=zone_universe,
            priors_map=priors_map,
            floor_map=floor_map,
            prior_meta=prior_payload,
            floor_meta=floor_payload,
        )

        output_dir = data_root / render_dataset_path(
            dataset_id="s2_country_zone_priors",
            template_args={"parameter_hash": inputs.parameter_hash},
            dictionary=dictionary,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "part-0.parquet"
        resumed = False
        if output_file.exists():
            existing = pl.read_parquet(output_file)
            if not _frames_equal(existing, result_df):
                raise err(
                    "E_IMMUTABILITY",
                    f"s2_country_zone_priors already exists at '{output_file}' with different content",
                )
            resumed = True
        else:
            result_df.write_parquet(output_file)

        run_report_path = (
            data_root
            / f"reports/l1/3A/s2_priors/parameter_hash={inputs.parameter_hash}/run_report.json"
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_run_report(
            path=run_report_path,
            result_df=result_df,
            parameter_hash=inputs.parameter_hash,
            prior_meta=prior_payload,
            floor_meta=floor_payload,
            resumed=resumed,
        )
        self._write_segment_state_row(
            base_path=data_root,
            dictionary=dictionary,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            run_report_path=run_report_path,
            output_path=output_file,
            prior_pack_id=prior_payload.get("policy_id") or prior_payload.get("id"),
            floor_policy_id=floor_payload.get("policy_id") or floor_payload.get("id"),
            resumed=resumed,
            seed=inputs.seed,
        )

        return PriorsResult(
            output_path=output_dir,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    # ------------------------------ helpers ------------------------------ #

    def _resolve_dataset_path(
        self,
        *,
        dictionary: Mapping[str, object],
        dataset_id: str,
        template_args: Mapping[str, object],
        base: Path,
    ) -> Path:
        relative = render_dataset_path(dataset_id=dataset_id, template_args=template_args, dictionary=dictionary)
        return (base / relative).resolve()

    def _load_json(self, path: Path, validator: Draft202012Validator) -> Mapping[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        try:
            validator.validate(payload)
        except ValidationError as exc:
            raise err("E_SCHEMA", f"{path} failed validation: {exc.message}") from exc
        return payload

    def _load_yaml(self, path: Path, validator: Draft202012Validator) -> Mapping[str, Any]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            raise err("E_POLICY_INVALID", f"{path} must decode to a mapping")
        try:
            validator.validate(payload)
        except ValidationError as exc:
            raise err("E_POLICY_INVALID", f"{path} failed validation: {exc.message}") from exc
        return payload

    def _validate_sealed_inputs(self, sealed_df: pl.DataFrame) -> None:
        for row in sealed_df.to_dicts():
            try:
                _SEALED_INPUT_VALIDATOR.validate(row)
            except ValidationError as exc:
                raise err(
                    "E_SCHEMA",
                    f"sealed_inputs row for '{row.get('logical_id')}' invalid: {exc.message}",
                ) from exc

    def _assert_upstream_pass(self, receipt: Mapping[str, Any]) -> None:
        gates = receipt.get("upstream_gates", {})
        for segment in ("segment_1A", "segment_1B", "segment_2A"):
            status = gates.get(segment, {}).get("status")
            if status != "PASS":
                raise err("E_UPSTREAM_GATE", f"{segment} status '{status}' is not PASS")

    def _resolve_sealed_asset(self, sealed_index: Mapping[str, Mapping[str, Any]], logical_id: str) -> Path:
        row = sealed_index.get(logical_id)
        if row is None:
            raise err("E_ASSET_MISSING", f"sealed_inputs missing '{logical_id}'")
        path = Path(row["path"]).resolve()
        if not path.exists():
            raise err("E_ASSET_PATH", f"sealed asset '{logical_id}' missing at '{path}'")
        expected_sha = row["sha256_hex"]
        actual_sha = aggregate_sha256(hash_files(expand_files(path), error_prefix=logical_id))
        if actual_sha != expected_sha:
            raise err(
                "E_ASSET_DIGEST",
                f"sealed asset '{logical_id}' digest mismatch (expected {expected_sha}, got {actual_sha})",
            )
        return path

    def _normalise_priors(self, payload: Mapping[str, Any]) -> dict[str, dict[str, float]]:
        countries = payload.get("countries") or payload.get("priors") or {}
        result: dict[str, dict[str, float]] = {}
        if isinstance(countries, Mapping):
            for country, entry in countries.items():
                tz_map = {}
                if isinstance(entry, Mapping):
                    if "tzid_alphas" in entry and isinstance(entry["tzid_alphas"], Sequence):
                        for row in entry["tzid_alphas"]:
                            if isinstance(row, Mapping) and "tzid" in row and "alpha" in row:
                                tz_map[str(row["tzid"])] = float(row["alpha"])
                    else:
                        for tz, alpha in entry.items():
                            if isinstance(alpha, (int, float)):
                                tz_map[str(tz)] = float(alpha)
                if tz_map:
                    result[str(country)] = tz_map
        return result

    def _normalise_floors(self, payload: Mapping[str, Any]) -> dict[str, float]:
        floors = payload.get("floors") or []
        result: dict[str, float] = {}
        if isinstance(floors, Sequence):
            for entry in floors:
                if isinstance(entry, Mapping) and "tzid" in entry and "floor_value" in entry:
                    result[str(entry["tzid"])] = float(entry["floor_value"])
        return result

    def _detect_country_column(self, df: pl.DataFrame) -> str:
        for candidate in ("country_iso", "legal_country_iso", "iso"):
            if candidate in df.columns:
                return candidate
        raise err("E_TZ_UNIVERSE", "unable to find country column in tz reference dataset")

    def _build_zone_universe(self, tz_df: pl.DataFrame, country_col: str) -> dict[str, list[str]]:
        universe: dict[str, list[str]] = {}
        for row in tz_df.select([country_col, "tzid"]).to_dicts():
            country = str(row[country_col])
            tzid = str(row["tzid"])
            universe.setdefault(country, []).append(tzid)
        for country, tzids in universe.items():
            universe[country] = sorted(set(tzids))
        return universe

    def _build_prior_table(
        self,
        *,
        parameter_hash: str,
        zone_universe: Mapping[str, Sequence[str]],
        priors_map: Mapping[str, Mapping[str, float]],
        floor_map: Mapping[str, float],
        prior_meta: Mapping[str, Any],
        floor_meta: Mapping[str, Any],
    ) -> pl.DataFrame:
        rows = []
        prior_id = str(prior_meta.get("policy_id") or prior_meta.get("id") or "country_zone_alphas")
        prior_version = str(prior_meta.get("version") or prior_meta.get("semver") or "1.0.0")
        floor_id = str(floor_meta.get("policy_id") or floor_meta.get("id") or "zone_floor_policy")
        floor_version = str(floor_meta.get("version") or floor_meta.get("semver") or "1.0.0")

        domain_countries = sorted(zone_universe.keys())
        for country in domain_countries:
            tzids = zone_universe[country]
            if not tzids:
                raise err("E_ZONE_DOMAIN", f"country '{country}' has empty zone universe")
            alpha_values = []
            for tzid in tzids:
                alpha_raw = float(priors_map.get(country, {}).get(tzid, 0.0))
                floor_value = float(floor_map.get(tzid, 0.0))
                alpha_effective = max(alpha_raw, floor_value)
                alpha_values.append((tzid, alpha_raw, alpha_effective, floor_value))

            alpha_sum_country = sum(value[2] for value in alpha_values)
            if alpha_sum_country <= 0:
                raise err("E_PRIOR_DEGENERATE", f"country '{country}' has zero effective prior mass")

            for tzid, alpha_raw, alpha_effective, floor_value in alpha_values:
                rows.append(
                    {
                        "parameter_hash": parameter_hash,
                        "country_iso": country,
                        "tzid": tzid,
                        "alpha_raw": alpha_raw,
                        "alpha_effective": alpha_effective,
                        "alpha_sum_country": alpha_sum_country,
                        "prior_pack_id": prior_id,
                        "prior_pack_version": prior_version,
                        "floor_policy_id": floor_id,
                        "floor_policy_version": floor_version,
                        "floor_applied": alpha_effective > alpha_raw,
                        "bump_applied": alpha_effective > alpha_raw and floor_value > 0,
                        "share_effective": alpha_effective / alpha_sum_country,
                        "notes": None,
                    }
                )

        return pl.DataFrame(rows).sort(["country_iso", "tzid"])

    def _write_run_report(
        self,
        *,
        path: Path,
        result_df: pl.DataFrame,
        parameter_hash: str,
        prior_meta: Mapping[str, Any],
        floor_meta: Mapping[str, Any],
        resumed: bool,
    ) -> Mapping[str, object]:
        countries = result_df["country_iso"].n_unique()
        zones = result_df.height
        payload = {
            "layer": "layer1",
            "segment": "3A",
            "state": "S2",
            "status": "PASS",
            "parameter_hash": parameter_hash,
            "prior_pack_id": prior_meta.get("policy_id") or prior_meta.get("id"),
            "prior_pack_version": prior_meta.get("version") or prior_meta.get("semver"),
            "floor_policy_id": floor_meta.get("policy_id") or floor_meta.get("id"),
            "floor_policy_version": floor_meta.get("version") or floor_meta.get("semver"),
            "countries_total": countries,
            "zone_rows": zones,
            "resumed": resumed,
        }
        now = datetime.now(timezone.utc).isoformat()
        payload["completed_at_utc"] = now
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload

    def _write_segment_state_row(
        self,
        *,
        base_path: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        parameter_hash: str,
        run_report_path: Path,
        output_path: Path,
        prior_pack_id: str | None,
        floor_policy_id: str | None,
        resumed: bool,
        seed: int,
    ) -> None:
        key = SegmentStateKey(
            layer="layer1",
            segment="3A",
            state="S2",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
        )
        payload = {
            **key.as_dict(),
            "status": "PASS",
            "attempt": 1,
            "output_path": str(output_path),
            "run_report_path": str(run_report_path),
            "prior_pack_id": prior_pack_id,
            "floor_policy_id": floor_policy_id,
            "resumed": resumed,
        }
        report_path = base_path / render_dataset_path(
            dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
        )
        write_segment_state_run_report(path=report_path, key=key, payload=payload)
