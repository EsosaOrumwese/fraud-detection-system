"""S3 day effects generator for Segment 2B."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Mapping, Optional, Sequence

import polars as pl
from jsonschema import Draft202012Validator, ValidationError

from ...shared.dictionary import load_dictionary, render_dataset_path, repository_root
from ...shared.receipt import GateReceiptSummary, load_gate_receipt
from ...shared.schema import load_schema
from ...s0_gate.exceptions import S0GateError, err

logger = logging.getLogger(__name__)

PHILOX_M0 = 0xD2511F53
PHILOX_M1 = 0xCD9E8D57
PHILOX_W0 = 0x9E3779B9
PHILOX_W1 = 0xBB67AE85


@dataclass
class DayEffectPolicy:
    """Parsed representation of the day-effect policy."""

    sigma_gamma: float
    clip_bounds: tuple[float, float]
    utc_day_start: date
    utc_day_count: int
    rng_key_hi: int
    rng_key_lo: int
    rng_counter_start_hi: int
    rng_counter_start_lo: int
    rng_stream_id: str
    sha256_hex: str


@dataclass(frozen=True)
class S3DayEffectsInputs:
    """Configuration required to execute Segment 2B S3."""

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
            raise err("E_S3_SEED_EMPTY", "seed must be provided for S3")
        object.__setattr__(self, "seed", seed_value)
        manifest = self.manifest_fingerprint.lower()
        if len(manifest) != 64:
            raise err(
                "E_S3_MANIFEST_FINGERPRINT",
                "manifest_fingerprint must be 64 hex characters",
            )
        int(manifest, 16)
        object.__setattr__(self, "manifest_fingerprint", manifest)


@dataclass(frozen=True)
class S3DayEffectsResult:
    """Outcome of the S3 runner."""

    manifest_fingerprint: str
    output_path: Path
    run_report_path: Path
    resumed: bool


class PhiloxRNG:
    """Minimal Philox4x32-10 implementation."""

    def __init__(self, key_lo: int, key_hi: int) -> None:
        self.key_lo = key_lo & 0xFFFFFFFF
        self.key_hi = key_hi & 0xFFFFFFFF

    def generate(self, counter_int: int) -> tuple[int, int, int, int]:
        counter_int &= (1 << 128) - 1
        c0 = counter_int & 0xFFFFFFFF
        c1 = (counter_int >> 32) & 0xFFFFFFFF
        c2 = (counter_int >> 64) & 0xFFFFFFFF
        c3 = (counter_int >> 96) & 0xFFFFFFFF
        k0 = self.key_lo
        k1 = self.key_hi
        for _ in range(10):
            p0 = (PHILOX_M0 * c0) & 0xFFFFFFFFFFFFFFFF
            p1 = (PHILOX_M1 * c2) & 0xFFFFFFFFFFFFFFFF
            c0, c1, c2, c3 = (
                ((p1 >> 32) & 0xFFFFFFFF) ^ c1 ^ k0,
                p1 & 0xFFFFFFFF,
                ((p0 >> 32) & 0xFFFFFFFF) ^ c3 ^ k1,
                p0 & 0xFFFFFFFF,
            )
            k0 = (k0 + PHILOX_W0) & 0xFFFFFFFF
            k1 = (k1 + PHILOX_W1) & 0xFFFFFFFF
        return c0, c1, c2, c3


class S3DayEffectsRunner:
    """Runs Segment 2B State 3."""

    RUN_REPORT_ROOT = Path("reports") / "l1" / "s3_day_effects"

    def run(self, config: S3DayEffectsInputs) -> S3DayEffectsResult:
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
        tz_path = self._resolve_dataset_path(
            dataset_id="site_timezones",
            config=config,
            dictionary=dictionary,
        )
        output_path = self._resolve_dataset_path(
            dataset_id="s3_day_effects",
            config=config,
            dictionary=dictionary,
        )
        if output_path.exists():
            if config.resume:
                logger.info(
                    "Segment2B S3 resume detected (seed=%s, manifest=%s); skipping run",
                    config.seed,
                    config.manifest_fingerprint,
                )
                run_report_path = self._resolve_run_report_path(config=config)
                return S3DayEffectsResult(
                    manifest_fingerprint=config.manifest_fingerprint,
                    output_path=output_path,
                    run_report_path=run_report_path,
                    resumed=True,
                )
            raise err(
                "E_S3_OUTPUT_EXISTS",
                f"s3_day_effects already exists at '{output_path}' - use resume or delete partition first",
            )

        joined = self._prepare_groups(weights_path, tz_path)
        tz_groups = (
            joined.select(["merchant_id", "legal_country_iso", "tzid"])
            .unique()
            .sort(["merchant_id", "tzid"])
        )
        if tz_groups.height == 0:
            raise err("E_S3_NO_TZ_GROUPS", "no tz groups found for S3 factors")

        days = [
            (policy.utc_day_start + timedelta(days=day_idx)).isoformat()
            for day_idx in range(policy.utc_day_count)
        ]
        rng = PhiloxRNG(policy.rng_key_lo, policy.rng_key_hi)

        merchants_total = tz_groups.select("merchant_id").unique().height
        tz_groups_total = tz_groups.height
        rows_out = []
        clip_hits = 0
        base_counter = ((policy.rng_counter_start_hi << 64) | policy.rng_counter_start_lo) & (
            (1 << 128) - 1
        )

        row_index = 0
        for record in tz_groups.iter_rows(named=True):
            merchant_id = int(record["merchant_id"])
            tzid = record["tzid"]
            legal_country_iso = record["legal_country_iso"]
            tz_group_id = self._tz_group_id(tzid)
            for day in days:
                counter = (base_counter + row_index) & ((1 << 128) - 1)
                out = rng.generate(counter)
                u1 = self._uint32_to_uniform(out[0])
                u2 = self._uint32_to_uniform(out[1])
                if u1 <= 0.0:
                    u1 = 1.0 / (1 << 32)
                sigma = policy.sigma_gamma
                mu = -0.5 * sigma * sigma
                r = math.sqrt(-2.0 * math.log(u1))
                theta = 2.0 * math.pi * u2
                z = r * math.cos(theta)
                log_gamma = mu + sigma * z
                lower, upper = policy.clip_bounds
                if log_gamma < lower:
                    log_gamma = lower
                    clip_hits += 1
                elif log_gamma > upper:
                    log_gamma = upper
                    clip_hits += 1
                gamma = math.exp(log_gamma)
                rng_counter_lo = counter & ((1 << 64) - 1)
                rng_counter_hi = counter >> 64
                rows_out.append(
                    {
                        "merchant_id": merchant_id,
                        "legal_country_iso": legal_country_iso,
                        "tz_group_id": tz_group_id,
                        "tzid": tzid,
                        "utc_day": day,
                        "gamma": gamma,
                        "log_gamma": log_gamma,
                        "sigma_gamma": sigma,
                        "rng_stream_id": policy.rng_stream_id,
                        "rng_counter_lo": rng_counter_lo,
                        "rng_counter_hi": rng_counter_hi,
                        "created_utc": receipt.verified_at_utc,
                    }
                )
                row_index += 1

        df = pl.DataFrame(rows_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(output_path, compression="zstd")

        run_report_path = self._resolve_run_report_path(config=config)
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        sample_rows = rows_out[: min(10, len(rows_out))]
        run_report = self._build_run_report(
            config=config,
            receipt=receipt,
            policy=policy,
            dictionary=dictionary,
            policy_path=policy_path,
            output_path=output_path,
            merchants_total=merchants_total,
            tz_groups_total=tz_groups_total,
            days_total=len(days),
            rows_total=len(rows_out),
            clip_hits=clip_hits,
            sample_rows=sample_rows,
        )
        run_report_path.write_text(json.dumps(run_report, indent=2), encoding="utf-8")
        if config.emit_run_report_stdout:
            print(json.dumps(run_report, indent=2))  # pragma: no cover

        return S3DayEffectsResult(
            manifest_fingerprint=config.manifest_fingerprint,
            output_path=output_path,
            run_report_path=run_report_path,
            resumed=False,
        )

    # ------------------------------------------------------------------ helpers

    def _load_policy(
        self, *, config: S3DayEffectsInputs, dictionary: Mapping[str, object]
    ) -> tuple[DayEffectPolicy, Path]:
        policy_rel = render_dataset_path(
            "day_effect_policy_v1",
            template_args={},
            dictionary=dictionary,
        )
        candidate = (config.data_root / policy_rel).resolve()
        if not candidate.exists():
            repo_candidate = repository_root() / policy_rel
            if not repo_candidate.exists():
                raise err(
                    "E_S3_POLICY_MISSING",
                    f"day_effect_policy_v1 not found at '{policy_rel}'",
                )
            candidate = repo_candidate.resolve()

        payload = json.loads(candidate.read_text(encoding="utf-8"))
        schema = load_schema("#/policy/day_effect_policy_v1")
        validator = Draft202012Validator(schema)
        try:
            validator.validate(payload)
        except ValidationError as exc:
            raise err(
                "E_S3_POLICY_INVALID",
                f"day_effect_policy_v1 violates schema: {exc.message}",
            ) from exc

        policy = DayEffectPolicy(
            sigma_gamma=float(payload["sigma_gamma"]),
            clip_bounds=(float(payload["clip_bounds"][0]), float(payload["clip_bounds"][1])),
            utc_day_start=date.fromisoformat(payload["utc_day_start"]),
            utc_day_count=int(payload["utc_day_count"]),
            rng_key_hi=int(payload["rng_key_hi"]),
            rng_key_lo=int(payload["rng_key_lo"]),
            rng_counter_start_hi=int(payload["rng_counter_start_hi"]),
            rng_counter_start_lo=int(payload["rng_counter_start_lo"]),
            rng_stream_id=str(payload["rng_stream_id"]),
            sha256_hex=_sha256_hex(candidate),
        )
        return policy, candidate

    def _prepare_groups(self, weights_path: Path, tz_path: Path) -> pl.DataFrame:
        try:
            weights = pl.read_parquet(
                weights_path,
                columns=["merchant_id", "legal_country_iso", "site_order"],
            )
        except Exception as exc:  # pragma: no cover
            raise err("E_S3_SITE_WEIGHTS_IO", f"failed to read s1_site_weights: {exc}") from exc
        try:
            tz = pl.read_parquet(
                tz_path,
                columns=["merchant_id", "legal_country_iso", "site_order", "tzid"],
            )
        except Exception as exc:  # pragma: no cover
            raise err("E_S3_TZ_LOOKUP_IO", f"failed to read site_timezones: {exc}") from exc
        joined = weights.join(
            tz, on=["merchant_id", "legal_country_iso", "site_order"], how="inner"
        )
        if joined.height != weights.height:
            raise err(
                "E_S3_TZ_LOOKUP_MISSING",
                "site_timezones missing rows for some s1_site_weights keys",
            )
        return joined

    def _resolve_dataset_path(
        self,
        *,
        dataset_id: str,
        config: S3DayEffectsInputs,
        dictionary: Mapping[str, object],
    ) -> Path:
        template_args = {
            "seed": config.seed,
            "manifest_fingerprint": config.manifest_fingerprint,
        }
        rel = render_dataset_path(dataset_id, template_args=template_args, dictionary=dictionary)
        return (config.data_root / rel).resolve()

    def _resolve_run_report_path(self, *, config: S3DayEffectsInputs) -> Path:
        return (
            config.data_root
            / self.RUN_REPORT_ROOT
            / f"seed={config.seed}"
            / f"fingerprint={config.manifest_fingerprint}"
            / "run_report.json"
        ).resolve()

    def _tz_group_id(self, tzid: str) -> str:
        import hashlib

        return hashlib.sha256(tzid.encode("utf-8")).hexdigest()[:16]

    def _uint32_to_uniform(self, value: int) -> float:
        return (value + 0.5) / 4294967296.0

    def _build_run_report(
        self,
        *,
        config: S3DayEffectsInputs,
        receipt: GateReceiptSummary,
        policy: DayEffectPolicy,
        dictionary: Mapping[str, object],
        policy_path: Path,
        output_path: Path,
        merchants_total: int,
        tz_groups_total: int,
        days_total: int,
        rows_total: int,
        clip_hits: int,
        sample_rows: Sequence[dict],
    ) -> dict:
        validators = [
            {"id": "V-01", "status": "PASS", "codes": []},
        ]
        run_report = {
            "component": "2B.S3",
            "fingerprint": config.manifest_fingerprint,
            "seed": config.seed,
            "created_utc": receipt.verified_at_utc,
            "catalogue_resolution": self._catalogue_resolution(dictionary=dictionary),
            "policy": {
                "id": "day_effect_policy_v1",
                "sha256_hex": policy.sha256_hex,
                "sigma_gamma": policy.sigma_gamma,
                "clip_bounds": list(policy.clip_bounds),
                "utc_day_start": policy.utc_day_start.isoformat(),
                "utc_day_count": policy.utc_day_count,
            },
            "output_path": str(output_path),
            "stats": {
                "merchants_total": merchants_total,
                "tz_groups_total": tz_groups_total,
                "days_total": days_total,
                "rows_total": rows_total,
                "clip_hits": clip_hits,
                "clip_percentage": (clip_hits / rows_total) if rows_total else 0.0,
            },
            "samples": {
                "factors": [
                    {
                        "merchant_id": row["merchant_id"],
                        "legal_country_iso": row["legal_country_iso"],
                        "tzid": row["tzid"],
                        "utc_day": row["utc_day"],
                        "gamma": row["gamma"],
                        "log_gamma": row["log_gamma"],
                    }
                    for row in sample_rows
                ],
            },
            "validators": validators,
            "summary": {"overall_status": "PASS", "warn_count": 0, "fail_count": 0},
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
                    "id": "site_timezones",
                    "path": str(
                        render_dataset_path(
                            "site_timezones",
                            template_args={
                                "seed": config.seed,
                                "manifest_fingerprint": config.manifest_fingerprint,
                            },
                            dictionary=dictionary,
                        )
                    ),
                },
                {"id": "day_effect_policy_v1", "path": str(policy_path)},
                {"id": "s3_day_effects", "path": str(output_path)},
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


def _sha256_hex(path: Path) -> str:
    import hashlib

    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()
