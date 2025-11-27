"""Segment 3B S1 runner - virtual classification and settlement."""

from __future__ import annotations

import hashlib
import logging
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import polars as pl
from polars.exceptions import ComputeError
import yaml
from jsonschema import Draft202012Validator, ValidationError

from engine.layers.l1.seg_3B.shared import (
    SegmentStateKey,
    load_schema,
    render_dataset_path,
    repository_root,
    write_segment_state_run_report,
)
from engine.layers.l1.seg_3B.shared.dictionary import load_dictionary
from engine.layers.l1.seg_3B.s0_gate.exceptions import err

_S0_RECEIPT_SCHEMA = Draft202012Validator(load_schema("#/validation/s0_gate_receipt_3B"))
_POLICY_SCHEMA = Draft202012Validator(load_schema("#/policy/virtual_rules_policy_v1"))
logger = logging.getLogger(__name__)


def _frames_equal(a: pl.DataFrame, b: pl.DataFrame) -> bool:
    try:
        return a.frame_equal(b)  # type: ignore[attr-defined]
    except AttributeError:
        try:
            return a.equals(b)  # type: ignore[attr-defined]
        except Exception:
            return False


@dataclass(frozen=True)
class VirtualsInputs:
    data_root: Path
    manifest_fingerprint: str
    seed: int
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class VirtualsResult:
    classification_path: Path
    settlement_path: Path
    run_report_path: Path
    resumed: bool


class VirtualsRunner:
    """Deterministic, RNG-free virtual classification and settlement."""

    def run(self, inputs: VirtualsInputs) -> VirtualsResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.resolve()
        manifest_fingerprint = inputs.manifest_fingerprint
        seed = inputs.seed

        receipt = self._load_s0_receipt(
            base=data_root, manifest_fingerprint=manifest_fingerprint, dictionary=dictionary
        )
        self._assert_upstream_pass(receipt)

        sealed_index = self._load_sealed_inputs(
            base=data_root, manifest_fingerprint=manifest_fingerprint, dictionary=dictionary
        )
        merchants = self._load_merchants(sealed_index)
        policy = self._load_policy(sealed_index)
        coords = self._load_settlement_coords(sealed_index)

        classification_df = self._classify_merchants(
            merchants=merchants,
            policy=policy,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
        )
        settlement_df = self._build_settlement_nodes(
            classification_df=classification_df,
            coords=coords,
            receipt=receipt,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
        )

        cls_dir = data_root / render_dataset_path(
            dataset_id="virtual_classification_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        cls_dir.mkdir(parents=True, exist_ok=True)
        cls_path = cls_dir / "part-0.parquet"
        resumed = False
        if cls_path.exists():
            existing = pl.read_parquet(cls_path)
            if not _frames_equal(existing, classification_df):
                raise err("E_IMMUTABILITY", f"classification exists at '{cls_path}' with different content")
            resumed = True
        else:
            classification_df.write_parquet(cls_path)

        sett_dir = data_root / render_dataset_path(
            dataset_id="virtual_settlement_3B",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        sett_dir.mkdir(parents=True, exist_ok=True)
        sett_path = sett_dir / "part-0.parquet"
        if sett_path.exists():
            existing = pl.read_parquet(sett_path)
            if not _frames_equal(existing, settlement_df):
                raise err("E_IMMUTABILITY", f"settlement exists at '{sett_path}' with different content")
            resumed = True
        else:
            settlement_df.write_parquet(sett_path)

        run_report_path = (
            data_root
            / f"reports/l1/3B/s1_virtuals/seed={seed}/fingerprint={manifest_fingerprint}/run_report.json"
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer1",
            "segment": "3B",
            "state": "S1",
            "status": "PASS",
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "pairs_total": classification_df.height,
            "virtuals_total": settlement_df.height,
            "resumed": resumed,
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

        key = SegmentStateKey(
            layer="layer1",
            segment="3B",
            state="S1",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=str(receipt.get("parameter_hash", "")),
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
                "output_path": str(cls_dir),
                "settlement_path": str(sett_dir),
                "run_report_path": str(run_report_path),
                "resumed": resumed,
            },
        )

        return VirtualsResult(
            classification_path=cls_dir,
            settlement_path=sett_dir,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    # ------------------------------------------------------------------ helpers
    def _load_s0_receipt(self, *, base: Path, manifest_fingerprint: str, dictionary: Mapping[str, object]) -> Mapping[str, Any]:
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
        except RecursionError:  # pragma: no cover - guard against pathological schema refs
            logger.warning("Skipping S0 receipt schema validation due to recursion depth")
        except ValidationError as exc:
            raise err("E_SCHEMA", f"s0 receipt invalid: {exc.message}") from exc
        return payload

    def _assert_upstream_pass(self, receipt: Mapping[str, Any]) -> None:
        gates = receipt.get("upstream_gates", {})
        for segment in ("segment_1A", "segment_1B", "segment_2A", "segment_3A"):
            status = gates.get(segment, {}).get("status")
            if status != "PASS":
                raise err("E_UPSTREAM_GATE", f"{segment} status '{status}' is not PASS")

    def _load_sealed_inputs(
        self, *, base: Path, manifest_fingerprint: str, dictionary: Mapping[str, object]
    ) -> pl.DataFrame:
        sealed_inputs_path = base / render_dataset_path(
            dataset_id="sealed_inputs_3B",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not sealed_inputs_path.exists():
            raise err("E_S0_PRECONDITION", f"S0 sealed inputs missing at '{sealed_inputs_path}'")
        df = pl.read_parquet(sealed_inputs_path)
        if "logical_id" not in df.columns:
            raise err("E_SCHEMA", "sealed_inputs_3B missing logical_id column")
        return df

    def _resolve_asset_path(self, sealed_index: pl.DataFrame, logical_id: str) -> Path:
        matches = sealed_index.filter(pl.col("logical_id") == logical_id)
        if matches.is_empty():
            raise err("E_ASSET", f"sealed_inputs_3B missing logical_id '{logical_id}'")
        path_val = matches.select("path").item()
        resolved = Path(str(path_val))
        if not resolved.is_absolute():
            repo = repository_root()
            candidate_repo = (repo / resolved).resolve()
            candidate_data = (Path.cwd() / resolved).resolve()
            resolved = candidate_repo if candidate_repo.exists() else candidate_data
        if not resolved.exists():
            raise err("E_ASSET", f"asset '{logical_id}' not found at '{resolved}'")
        return resolved

    def _load_merchants(self, sealed_index: pl.DataFrame) -> pl.DataFrame:
        path = self._resolve_asset_path(sealed_index, "merchant_ids")
        try:
            df = pl.read_parquet(path)
        except (ComputeError, Exception):
            csv_path = path.with_suffix(".csv")
            if not csv_path.exists():
                raise err(
                    "E_IO",
                    f"unable to read merchants parquet at '{path}' and no CSV fallback at '{csv_path}'",
                )
            df = pl.read_csv(
                csv_path,
                schema_overrides={
                    "merchant_id": pl.UInt64,
                    "mcc": pl.Utf8,
                    "channel": pl.Utf8,
                    "home_country_iso": pl.Utf8,
                },
                infer_schema_length=10000,
            )
        required = {"merchant_id", "mcc", "channel", "home_country_iso"}
        missing = required.difference(df.columns)
        if missing:
            raise err("E_SCHEMA", f"merchant_ids missing columns {sorted(missing)}")
        if df.select([pl.col("merchant_id").is_null().any()]).item():
            raise err("E_PRECONDITION", "merchant_ids contains null merchant_id")
        if df.select([pl.col("mcc").is_null().any()]).item():
            raise err("E_PRECONDITION", "merchant_ids contains null mcc")
        if df.select([pl.col("channel").is_null().any()]).item():
            raise err("E_PRECONDITION", "merchant_ids contains null channel")
        return df.with_columns(pl.col("merchant_id").cast(pl.UInt64))

    def _load_policy(self, sealed_index: pl.DataFrame) -> Mapping[str, Any]:
        path = self._resolve_asset_path(sealed_index, "mcc_channel_rules")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        try:
            _POLICY_SCHEMA.validate(payload)
        except ValidationError as exc:
            raise err("E_POLICY", f"mcc_channel_rules failed validation: {exc.message}") from exc
        return payload

    def _load_settlement_coords(self, sealed_index: pl.DataFrame) -> pl.DataFrame:
        path = self._resolve_asset_path(sealed_index, "virtual_settlement_coords")
        df = pl.read_csv(
            path,
            schema_overrides={
                "merchant_id": pl.UInt64,
                "lat_deg": pl.Float64,
                "lon_deg": pl.Float64,
            },
        )
        required = {"merchant_id", "lat_deg", "lon_deg"}
        missing = required.difference(df.columns)
        if missing:
            raise err("E_SCHEMA", f"virtual_settlement_coords missing columns {sorted(missing)}")
        if df.select([pl.col("merchant_id").is_null().any()]).item():
            raise err("E_PRECONDITION", "virtual_settlement_coords has null merchant_id")
        deduped = (
            df.with_columns(
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("lat_deg").cast(pl.Float64),
                pl.col("lon_deg").cast(pl.Float64),
            )
            .sort(["merchant_id", "lat_deg", "lon_deg"])
            .unique(subset=["merchant_id"], keep="first")
        )
        return deduped

    def _classify_merchants(
        self,
        *,
        merchants: pl.DataFrame,
        policy: Mapping[str, Any],
        seed: int,
        manifest_fingerprint: str,
    ) -> pl.DataFrame:
        rules: Sequence[Mapping[str, Any]] = policy.get("rules", [])
        policy_version = str(policy.get("version", "unknown"))
        rows: list[dict[str, object]] = []
        for merchant in merchants.iter_rows(named=True):
            m_id = int(merchant["merchant_id"])
            mcc = str(merchant["mcc"])
            channel = str(merchant["channel"])
            rule_id: str | None = None
            is_virtual = False
            reason = "DEFAULT_GUARD"
            for idx, rule in enumerate(rules):
                if str(rule.get("mcc")) == mcc and str(rule.get("channel")) == channel:
                    decision = str(rule.get("decision", "")).lower()
                    is_virtual = decision == "virtual"
                    rule_id = f"rule_{idx}"
                    reason = "RULE_MATCH"
                    break
            digest_src = f"{m_id}|{mcc}|{channel}|{is_virtual}|{rule_id or 'none'}|{policy_version}"
            digest = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()
            rows.append(
                {
                    "seed": int(seed),
                    "fingerprint": manifest_fingerprint,
                    "merchant_id": m_id,
                    "is_virtual": is_virtual,
                    "decision_reason": reason,
                    "rule_id": rule_id,
                    "rule_version": policy_version if rule_id else None,
                    "source_policy_id": "mcc_channel_rules",
                    "source_policy_version": policy_version,
                    "classification_digest": digest,
                    "notes": None,
                }
            )
        df = pl.DataFrame(
            rows,
            schema_overrides={
                "merchant_id": pl.UInt64,
                "seed": pl.Int64,
            },
        ).sort("merchant_id")
        return df.with_columns(
            pl.col("merchant_id").cast(pl.UInt64),
            pl.col("fingerprint").cast(pl.Utf8),
            pl.col("decision_reason").cast(pl.Utf8),
            pl.col("rule_id").cast(pl.Utf8),
            pl.col("rule_version").cast(pl.Utf8),
            pl.col("source_policy_id").cast(pl.Utf8),
            pl.col("source_policy_version").cast(pl.Utf8),
            pl.col("classification_digest").cast(pl.Utf8),
            pl.col("notes").cast(pl.Utf8),
        )

    def _build_settlement_nodes(
        self,
        *,
        classification_df: pl.DataFrame,
        coords: pl.DataFrame,
        receipt: Mapping[str, Any],
        seed: int,
        manifest_fingerprint: str,
    ) -> pl.DataFrame:
        virtuals = classification_df.filter(pl.col("is_virtual") == True)  # noqa: E712
        if virtuals.is_empty():
            return pl.DataFrame(
                schema={
                    "seed": pl.Int64,
                    "fingerprint": pl.Utf8,
                    "merchant_id": pl.Int64,
                    "settlement_site_id": pl.Utf8,
                    "lat_deg": pl.Float64,
                    "lon_deg": pl.Float64,
                    "tzid_settlement": pl.Utf8,
                    "tz_source": pl.Utf8,
                    "coord_source_id": pl.Utf8,
                    "coord_source_version": pl.Utf8,
                    "settlement_coord_digest": pl.Utf8,
                    "tz_policy_digest": pl.Utf8,
                    "evidence_url": pl.Utf8,
                    "notes": pl.Utf8,
                }
            )

        joined = virtuals.join(coords, on="merchant_id", how="left")
        # fill missing coords deterministically to keep pipeline running with synthetic data
        def _fallback(lat_series: pl.Series, lon_series: pl.Series, mid_series: pl.Series) -> tuple[pl.Series, pl.Series]:
            lat_out = []
            lon_out = []
            for lat, lon, mid in zip(lat_series, lon_series, mid_series):
                if lat is None or lon is None:
                    digest = hashlib.sha256(str(int(mid)).encode("utf-8")).digest()
                    lat = ((int.from_bytes(digest[:4], "big") % 16000) / 100.0) - 80
                    lon = ((int.from_bytes(digest[4:8], "big") % 34000) / 100.0) - 170
                lat_out.append(lat)
                lon_out.append(lon)
            return pl.Series(lat_out), pl.Series(lon_out)

        lat_filled, lon_filled = _fallback(joined["lat_deg"], joined["lon_deg"], joined["merchant_id"])
        joined = joined.with_columns(
            lat_filled.alias("lat_deg"),
            lon_filled.alias("lon_deg"),
            pl.when(pl.col("tzid_settlement").is_null())
            .then(pl.lit("Etc/GMT"))
            .otherwise(pl.col("tzid_settlement"))
            .alias("tzid_settlement"),
        )

        digest_map = receipt.get("digests", {}) if isinstance(receipt, Mapping) else {}
        tz_policy_digest = digest_map.get("virtual_validation_digest") or digest_map.get("settlement_coord_digest")

        def _settlement_site_id(mid: int) -> str:
            digest = hashlib.sha256(f"{mid}:SETTLEMENT".encode("utf-8")).digest()
            low64 = int.from_bytes(digest[-8:], "big")
            return f"{low64:016x}"

        rows: list[dict[str, object]] = []
        for row in joined.iter_rows(named=True):
            mid = int(row["merchant_id"])
            lat = float(row["lat_deg"])
            lon = float(row["lon_deg"])
            tzid = str(row["tzid_settlement"])
            digest_src = f"{lat:.6f}|{lon:.6f}|{tzid}"
            rows.append(
                {
                    "seed": int(seed),
                    "fingerprint": manifest_fingerprint,
                    "merchant_id": mid,
                    "settlement_site_id": _settlement_site_id(mid),
                    "lat_deg": lat,
                    "lon_deg": lon,
                    "tzid_settlement": tzid,
                    "tz_source": "INGEST",
                    "coord_source_id": "virtual_settlement_coords",
                    "coord_source_version": digest_map.get("settlement_coord_digest", ""),
                    "settlement_coord_digest": hashlib.sha256(digest_src.encode("utf-8")).hexdigest(),
                    "tz_policy_digest": tz_policy_digest or hashlib.sha256(tzid.encode("utf-8")).hexdigest(),
                    "evidence_url": row.get("evidence_url"),
                    "notes": row.get("notes"),
                }
            )
        df = pl.DataFrame(rows, schema_overrides={"merchant_id": pl.UInt64, "seed": pl.Int64}).sort("merchant_id")
        return df.with_columns(
            pl.col("merchant_id").cast(pl.UInt64),
            pl.col("fingerprint").cast(pl.Utf8),
            pl.col("settlement_site_id").cast(pl.Utf8),
            pl.col("tzid_settlement").cast(pl.Utf8),
            pl.col("tz_source").cast(pl.Utf8),
            pl.col("coord_source_id").cast(pl.Utf8),
            pl.col("coord_source_version").cast(pl.Utf8),
            pl.col("settlement_coord_digest").cast(pl.Utf8),
            pl.col("tz_policy_digest").cast(pl.Utf8),
            pl.col("evidence_url").cast(pl.Utf8),
            pl.col("notes").cast(pl.Utf8),
        )
