"""S3 day effects generator for Segment 2B."""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import NormalDist
from typing import Dict, Mapping, Optional, Sequence

import polars as pl
from jsonschema import Draft202012Validator, ValidationError

from ...shared.dictionary import load_dictionary, render_dataset_path, repository_root
from ...shared.receipt import GateReceiptSummary, load_gate_receipt
from ...shared.schema import load_schema
from ...s0_gate.exceptions import err

logger = logging.getLogger(__name__)

PHILOX_M0 = 0xD2511F53
PHILOX_M1 = 0xCD9E8D57
PHILOX_W0 = 0x9E3779B9
PHILOX_W1 = 0xBB67AE85
MAX_COUNTER = (1 << 128) - 1
NORMAL_DIST = NormalDist()


@dataclass
class DayEffectPolicy:
    """Parsed representation of the day-effect policy."""

    version_tag: str
    rng_engine: str
    rng_stream_id: str
    sigma_gamma: float
    day_start: date
    day_end: date
    draws_per_row: int
    record_fields: tuple[str, ...]
    created_utc_policy_echo: bool
    rng_key_hi: int
    rng_key_lo: int
    base_counter_hi: int
    base_counter_lo: int
    sha256_hex: str

    @property
    def utc_day_count(self) -> int:
        return (self.day_end - self.day_start).days + 1

    @property
    def day_range_iso(self) -> Mapping[str, str]:
        return {
            "start_day": self.day_start.isoformat(),
            "end_day": self.day_end.isoformat(),
        }

    @property
    def base_counter(self) -> int:
        return ((self.base_counter_hi << 64) | self.base_counter_lo) & MAX_COUNTER


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
        counter_int &= MAX_COUNTER
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
    REQUIRED_RECORD_FIELDS = {
        "gamma",
        "log_gamma",
        "sigma_gamma",
        "rng_stream_id",
        "rng_counter_lo",
        "rng_counter_hi",
    }

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
        output_dir = self._resolve_dataset_path(
            dataset_id="s3_day_effects",
            config=config,
            dictionary=dictionary,
        )
        if output_dir.exists():
            if config.resume:
                logger.info(
                    "Segment2B S3 resume detected (seed=%s, manifest=%s); skipping run",
                    config.seed,
                    config.manifest_fingerprint,
                )
                run_report_path = self._resolve_run_report_path(config=config)
                return S3DayEffectsResult(
                    manifest_fingerprint=config.manifest_fingerprint,
                    output_path=output_dir,
                    run_report_path=run_report_path,
                    resumed=True,
                )
            raise err(
                "E_S3_OUTPUT_EXISTS",
                f"s3_day_effects already exists at '{output_dir}' - use resume or delete partition first",
            )

        groups_by_merchant, merchants_total, tz_groups_total = self._prepare_groups(
            weights_path=weights_path, tz_path=tz_path
        )
        days = self._materialise_days(policy=policy)
        rows_expected = self._expected_rows(groups_by_merchant, len(days))
        base_counter = policy.base_counter
        if base_counter + rows_expected - 1 > MAX_COUNTER:
            raise err(
                "E_S3_COUNTER_OVERFLOW",
                "rng counter range exceeds 128-bit capacity for requested coverage",
            )

        rng = PhiloxRNG(policy.rng_key_lo, policy.rng_key_hi)
        mu = -0.5 * policy.sigma_gamma * policy.sigma_gamma
        sigma = policy.sigma_gamma
        rows_out = []
        row_samples = []
        rng_monotonic_samples = []
        max_abs_log_gamma = 0.0
        rows_written = 0
        prev_counter: int | None = None
        first_counter_hi = None
        first_counter_lo = None
        last_counter_hi = None
        last_counter_lo = None

        merchants_sorted = sorted(groups_by_merchant.keys())
        for merchant_id in merchants_sorted:
            tzids = groups_by_merchant[merchant_id]
            for utc_day in days:
                for tzid in tzids:
                    counter = base_counter + rows_written
                    if prev_counter is not None and counter <= prev_counter:
                        raise err(
                            "E_S3_COUNTER_MONOTONIC",
                            "rng counters must be strictly increasing in writer order",
                        )
                    words = rng.generate(counter)
                    u = self._uint64_to_uniform(words[0], words[1])
                    z = NORMAL_DIST.inv_cdf(u)
                    log_gamma = mu + sigma * z
                    if not math.isfinite(log_gamma):
                        raise err(
                            "E_S3_NONFINITE_LOG_GAMMA",
                            f"log_gamma not finite for merchant {merchant_id}, tz '{tzid}', day {utc_day}",
                        )
                    gamma = math.exp(log_gamma)
                    if gamma <= 0.0:
                        raise err(
                            "E_S3_NON_POSITIVE_GAMMA",
                            f"gamma <= 0 detected for merchant {merchant_id}, tz '{tzid}', day {utc_day}",
                        )
                    rng_counter_lo = counter & ((1 << 64) - 1)
                    rng_counter_hi = (counter >> 64) & ((1 << 64) - 1)
                    rows_out.append(
                        {
                            "merchant_id": merchant_id,
                            "utc_day": utc_day,
                            "tz_group_id": tzid,
                            "gamma": gamma,
                            "log_gamma": log_gamma,
                            "sigma_gamma": sigma,
                            "rng_stream_id": policy.rng_stream_id,
                            "rng_counter_hi": rng_counter_hi,
                            "rng_counter_lo": rng_counter_lo,
                            "created_utc": receipt.verified_at_utc,
                        }
                    )
                    if len(row_samples) < 10:
                        row_samples.append(
                            {
                                "merchant_id": merchant_id,
                                "utc_day": utc_day,
                                "tz_group_id": tzid,
                                "gamma": gamma,
                                "log_gamma": log_gamma,
                            }
                        )
                    if (
                        prev_counter is not None
                        and len(rng_monotonic_samples) < 10
                    ):
                        rng_monotonic_samples.append(
                            {
                                "row_index": rows_written,
                                "prev": {
                                    "hi": (prev_counter >> 64) & ((1 << 64) - 1),
                                    "lo": prev_counter & ((1 << 64) - 1),
                                },
                                "curr": {
                                    "hi": rng_counter_hi,
                                    "lo": rng_counter_lo,
                                },
                            }
                        )
                    prev_counter = counter
                    if first_counter_hi is None:
                        first_counter_hi = rng_counter_hi
                        first_counter_lo = rng_counter_lo
                    last_counter_hi = rng_counter_hi
                    last_counter_lo = rng_counter_lo
                    max_abs_log_gamma = max(max_abs_log_gamma, abs(log_gamma))
                    rows_written += 1

        if rows_written != rows_expected:
            raise err(
                "E_S3_ROW_MISMATCH",
                f"rows produced ({rows_written}) != expected coverage ({rows_expected})",
            )

        bytes_written = self._publish_rows(
            rows_out=rows_out,
            output_dir=output_dir,
        )

        run_report_path = self._resolve_run_report_path(config=config)
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        dictionary_resolution = self._catalogue_resolution(dictionary=dictionary)
        output_rel = render_dataset_path(
            "s3_day_effects",
            template_args={
                "seed": config.seed,
                "manifest_fingerprint": config.manifest_fingerprint,
            },
            dictionary=dictionary,
        )
        run_report = self._build_run_report(
            config=config,
            receipt=receipt,
            policy=policy,
            dictionary=dictionary,
            policy_path=policy_path,
            output_path=output_rel,
            merchants_total=merchants_total,
            tz_groups_total=tz_groups_total,
            days_total=len(days),
            rows_total=rows_written,
            rows_expected=rows_expected,
            max_abs_log_gamma=max_abs_log_gamma,
            row_samples=row_samples,
            rng_monotonic_samples=rng_monotonic_samples,
            dictionary_resolution=dictionary_resolution,
            bytes_written=bytes_written,
            first_counter=(first_counter_hi or 0, first_counter_lo or 0),
            last_counter=(last_counter_hi or 0, last_counter_lo or 0),
        )
        run_report_path.write_text(json.dumps(run_report, indent=2), encoding="utf-8")
        if config.emit_run_report_stdout:
            print(json.dumps(run_report, indent=2))  # pragma: no cover

        return S3DayEffectsResult(
            manifest_fingerprint=config.manifest_fingerprint,
            output_path=output_dir,
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

        start_day = date.fromisoformat(payload["day_range"]["start_day"])
        end_day = date.fromisoformat(payload["day_range"]["end_day"])
        if start_day > end_day:
            raise err(
                "E_S3_POLICY_DAY_RANGE",
                "day_range.start_day must be <= day_range.end_day",
            )
        draws_per_row = int(payload["draws_per_row"])
        if draws_per_row != 1:
            raise err(
                "E_S3_POLICY_DRAWS",
                f"draws_per_row must be 1 (observed {draws_per_row})",
            )
        record_fields = tuple(str(field) for field in payload["record_fields"])
        missing = self.REQUIRED_RECORD_FIELDS.difference(record_fields)
        if missing:
            raise err(
                "E_S3_POLICY_RECORD_FIELDS",
                f"policy missing required record_fields: {', '.join(sorted(missing))}",
            )
        rng_engine = str(payload["rng_engine"])
        if rng_engine != "philox_4x32_10":
            raise err(
                "E_S3_POLICY_RNG_ENGINE",
                f"unsupported rng_engine '{rng_engine}' (expected philox_4x32_10)",
            )

        policy = DayEffectPolicy(
            version_tag=str(payload["version_tag"]),
            rng_engine=rng_engine,
            rng_stream_id=str(payload["rng_stream_id"]),
            sigma_gamma=float(payload["sigma_gamma"]),
            day_start=start_day,
            day_end=end_day,
            draws_per_row=draws_per_row,
            record_fields=record_fields,
            created_utc_policy_echo=bool(payload["created_utc_policy_echo"]),
            rng_key_hi=int(payload["rng_key_hi"]),
            rng_key_lo=int(payload["rng_key_lo"]),
            base_counter_hi=int(payload["base_counter_hi"]),
            base_counter_lo=int(payload["base_counter_lo"]),
            sha256_hex=_sha256_hex(candidate),
        )
        return policy, candidate

    def _materialise_days(self, *, policy: DayEffectPolicy) -> list[str]:
        days = [
            date.fromordinal(policy.day_start.toordinal() + offset).isoformat()
            for offset in range(policy.utc_day_count)
        ]
        if not days:
            raise err("E_S3_DAY_RANGE_EMPTY", "policy day_range produced zero days")
        return days

    def _expected_rows(
        self, groups_by_merchant: Mapping[int, Sequence[str]], days_total: int
    ) -> int:
        tz_groups_total = sum(len(tzids) for tzids in groups_by_merchant.values())
        expected = tz_groups_total * days_total
        if expected <= 0:
            raise err(
                "E_S3_NO_ROWS",
                "cartesian coverage produced zero rows (check day range and tz groups)",
            )
        return expected

    def _prepare_groups(
        self,
        *,
        weights_path: Path,
        tz_path: Path,
    ) -> tuple[Dict[int, list[str]], int, int]:
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

        duplicates = (
            tz.group_by(["merchant_id", "legal_country_iso", "site_order"])
            .len()
            .rename({"len": "count"})
            .filter(pl.col("count") > 1)
        )
        if duplicates.height:
            sample = duplicates.select(
                ["merchant_id", "legal_country_iso", "site_order"]
            ).head(5)
            raise err(
                "E_S3_TZ_LOOKUP_DUPLICATE",
                f"site_timezones has duplicate tzid entries for keys: {sample.to_dicts()}",
            )

        joined = weights.join(
            tz, on=["merchant_id", "legal_country_iso", "site_order"], how="inner"
        )
        if joined.height != weights.height:
            raise err(
                "E_S3_TZ_LOOKUP_MISSING",
                "site_timezones missing rows for some s1_site_weights keys",
            )

        groups: Dict[int, set[str]] = {}
        for row in joined.select(["merchant_id", "tzid"]).iter_rows(named=True):
            merchant_id = int(row["merchant_id"])
            tzid = str(row["tzid"])
            if not tzid:
                raise err(
                    "E_S3_TZ_LOOKUP_INVALID",
                    f"empty tzid encountered for merchant {merchant_id}",
                )
            groups.setdefault(merchant_id, set()).add(tzid)

        if not groups:
            raise err("E_S3_NO_TZ_GROUPS", "no tz groups found for S3 factors")

        sorted_groups: Dict[int, list[str]] = {
            merchant: sorted(tzids)
            for merchant, tzids in sorted(groups.items())
        }
        merchants_total = len(sorted_groups)
        tz_groups_total = sum(len(tzids) for tzids in sorted_groups.values())
        if tz_groups_total == 0:
            raise err("E_S3_NO_TZ_GROUPS", "no tz groups found for S3 factors")
        return sorted_groups, merchants_total, tz_groups_total

    def _publish_rows(self, *, rows_out: Sequence[Mapping[str, object]], output_dir: Path) -> int:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging_dir = output_dir.parent / f".s3_day_effects_{uuid.uuid4().hex}"
        staging_dir.mkdir(parents=True, exist_ok=False)
        part_path = staging_dir / "part-00000.parquet"
        try:
            df = pl.DataFrame(
                rows_out,
                schema={
                    "merchant_id": pl.UInt64,
                    "utc_day": pl.Utf8,
                    "tz_group_id": pl.Utf8,
                    "gamma": pl.Float64,
                    "log_gamma": pl.Float64,
                    "sigma_gamma": pl.Float64,
                    "rng_stream_id": pl.Utf8,
                    "rng_counter_hi": pl.UInt64,
                    "rng_counter_lo": pl.UInt64,
                    "created_utc": pl.Utf8,
                },
            )
            df.write_parquet(part_path, compression="zstd")
            self._fsync_file(part_path)
            os.replace(staging_dir, output_dir)
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        bytes_written = sum(f.stat().st_size for f in output_dir.glob("*.parquet"))
        return bytes_written

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

    def _uint64_to_uniform(self, word0: int, word1: int) -> float:
        value = ((word0 & 0xFFFFFFFF) << 32) | (word1 & 0xFFFFFFFF)
        return (value + 0.5) / 18446744073709551616.0

    def _build_run_report(
        self,
        *,
        config: S3DayEffectsInputs,
        receipt: GateReceiptSummary,
        policy: DayEffectPolicy,
        dictionary: Mapping[str, object],
        policy_path: Path,
        output_path: str,
        merchants_total: int,
        tz_groups_total: int,
        days_total: int,
        rows_total: int,
        rows_expected: int,
        max_abs_log_gamma: float,
        row_samples: Sequence[Mapping[str, object]],
        rng_monotonic_samples: Sequence[Mapping[str, object]],
        dictionary_resolution: Mapping[str, str],
        bytes_written: int,
        first_counter: tuple[int, int],
        last_counter: tuple[int, int],
    ) -> dict:
        validators = [
            {"id": "V-01", "status": "PASS", "codes": []},
            {"id": "V-02", "status": "PASS", "codes": []},
            {"id": "V-06", "status": "PASS", "codes": []},
            {"id": "V-12", "status": "PASS", "codes": []},
        ]
        run_report = {
            "component": "2B.S3",
            "fingerprint": config.manifest_fingerprint,
            "seed": config.seed,
            "created_utc": receipt.verified_at_utc,
            "catalogue_resolution": dictionary_resolution,
            "policy": {
                "id": "day_effect_policy_v1",
                "version_tag": policy.version_tag,
                "sha256_hex": policy.sha256_hex,
                "rng_engine": policy.rng_engine,
                "rng_stream_id": policy.rng_stream_id,
                "sigma_gamma": policy.sigma_gamma,
                "day_range": policy.day_range_iso,
                "created_utc_policy_echo": policy.created_utc_policy_echo,
            },
            "inputs_summary": {
                "weights_path": str(
                    render_dataset_path(
                        "s1_site_weights",
                        template_args={
                            "seed": config.seed,
                            "manifest_fingerprint": config.manifest_fingerprint,
                        },
                        dictionary=dictionary,
                    )
                ),
                "timezones_path": str(
                    render_dataset_path(
                        "site_timezones",
                        template_args={
                            "seed": config.seed,
                            "manifest_fingerprint": config.manifest_fingerprint,
                        },
                        dictionary=dictionary,
                    )
                ),
                "merchants_total": merchants_total,
                "tz_groups_total": tz_groups_total,
                "days_total": days_total,
            },
            "rng_accounting": {
                "rows_expected": rows_expected,
                "rows_written": rows_total,
                "draws_total": rows_total,
                "first_counter": {"hi": first_counter[0], "lo": first_counter[1]},
                "last_counter": {"hi": last_counter[0], "lo": last_counter[1]},
            },
            "stats": {
                "rows_written": rows_total,
                "rows_expected": rows_expected,
                "max_abs_log_gamma": max_abs_log_gamma,
                "bytes_written": bytes_written,
            },
            "samples": {
                "rows": list(row_samples),
                "rng_monotonic": list(rng_monotonic_samples),
            },
            "validators": validators,
            "summary": {"overall_status": "PASS", "warn_count": 0, "fail_count": 0},
            "output_path": output_path,
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
                {"id": "s3_day_effects", "path": output_path},
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

    def _fsync_file(self, path: Path) -> None:
        try:
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
        except (OSError, AttributeError):  # pragma: no cover - best effort on some platforms
            logger.debug("fsync skipped for %s", path)


def _sha256_hex(path: Path) -> str:
    import hashlib

    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()
