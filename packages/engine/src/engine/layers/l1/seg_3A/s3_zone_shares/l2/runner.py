"""Segment 3A S3 runner – Dirichlet zone share draws."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

import polars as pl

from engine.layers.l1.seg_1A.s0_foundations.l1.rng import PhiloxEngine, PhiloxState, comp_iso, comp_u64
from engine.layers.l1.seg_3A.s0_gate.exceptions import err
from engine.layers.l1.seg_3A.shared import (
    SegmentStateKey,
    load_schema,
    render_dataset_path,
    write_segment_state_run_report,
)
from engine.layers.l1.seg_3A.shared.dictionary import load_dictionary
from jsonschema import Draft202012Validator, ValidationError

_S0_RECEIPT_SCHEMA = load_schema("#/validation/s0_gate_receipt_3A")
_S0_RECEIPT_FIELDS = {"parameter_hash", "manifest_fingerprint", "seed", "upstream_gates"}


def _frames_equal(a: pl.DataFrame, b: pl.DataFrame) -> bool:
    try:
        return a.frame_equal(b)  # type: ignore[attr-defined]
    except AttributeError:
        try:
            return a.equals(b)  # type: ignore[attr-defined]
        except Exception:
            return False


@dataclass(frozen=True)
class ZoneSharesInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str = "00000000000000000000000000000000"
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class ZoneSharesResult:
    output_path: Path
    run_report_path: Path
    rng_trace_path: Path
    resumed: bool


class _DirichletEventWriter:
    """Emit per-pair Dirichlet RNG events and trace totals."""

    def __init__(
        self,
        *,
        base_path: Path,
        seed: int,
        manifest_fingerprint: str,
        parameter_hash: str,
        run_id: str,
    ) -> None:
        self.base_path = base_path.resolve()
        self.seed = int(seed)
        self.manifest_fingerprint = manifest_fingerprint
        self.parameter_hash = parameter_hash
        self.run_id = run_id
        self._events_root = self.base_path / "logs" / "rng" / "events"
        self._trace_root = self.base_path / "logs" / "rng" / "trace"
        self._trace_totals: MutableMapping[tuple[str, str], dict[str, int]] = {}

    def _partition(self, filename: str) -> Path:
        return (
            Path(f"seed={self.seed}")
            / f"parameter_hash={self.parameter_hash}"
            / f"run_id={self.run_id}"
            / filename
        )

    @property
    def events_path(self) -> Path:
        return self._events_root / "zone_dirichlet_share" / self._partition("part-00000.jsonl")

    @property
    def trace_path(self) -> Path:
        return self._trace_root / self._partition("rng_trace_log.jsonl")

    def _append_jsonl(self, path: Path, payload: Mapping[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")

    def _delta(self, before: PhiloxState, after: PhiloxState) -> int:
        before_val = (before.counter_hi << 64) | before.counter_lo
        after_val = (after.counter_hi << 64) | after.counter_lo
        if after_val < before_val:
            raise err("E_RNG_COUNTER", "Philox counters decreased across event emission")
        return after_val - before_val

    def write_dirichlet_event(
        self,
        *,
        merchant_id: int,
        country_iso: str,
        tzid: str,
        counter_before: PhiloxState,
        counter_after: PhiloxState,
        draws_used: int,
        blocks_used: int,
        share_drawn: float,
        alpha_sum: float,
        module: str,
        substream_label: str,
        prior_pack_id: str,
        prior_pack_version: str,
    ) -> None:
        if draws_used <= 0 or blocks_used < 0:
            raise err("E_RNG_BUDGET", "Dirichlet event must consume draws > 0 and blocks >= 0")
        if self._delta(counter_before, counter_after) != blocks_used:
            raise err("E_RNG_COUNTER", "Philox block delta mismatch for Dirichlet event")

        stream_id = f"{substream_label}|{merchant_id}|{country_iso}"
        record = {
            "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "module": module,
            "substream_label": substream_label,
            "stream_id": stream_id,
            "seed": self.seed,
            "run_id": self.run_id,
            "parameter_hash": self.parameter_hash,
            "manifest_fingerprint": self.manifest_fingerprint,
            "merchant_id": int(merchant_id),
            "country_iso": str(country_iso),
            "tzid": str(tzid),
            "share_drawn": float(share_drawn),
            "prior_pack_id": prior_pack_id,
            "prior_pack_version": prior_pack_version,
            "alpha_sum_country": float(alpha_sum),
            "rng_counter_before_hi": int(counter_before.counter_hi),
            "rng_counter_before_lo": int(counter_before.counter_lo),
            "rng_counter_after_hi": int(counter_after.counter_hi),
            "rng_counter_after_lo": int(counter_after.counter_lo),
            "draws": str(int(draws_used)),
            "blocks": int(blocks_used),
        }
        self._append_jsonl(self.events_path, record)
        key = (module, substream_label)
        stats = self._trace_totals.setdefault(key, {"draws": 0, "blocks": 0, "events": 0})
        stats["draws"] = min(stats["draws"] + draws_used, 2**64 - 1)
        stats["blocks"] = min(stats["blocks"] + blocks_used, 2**64 - 1)
        stats["events"] = min(stats["events"] + 1, 2**64 - 1)
        trace_payload = {
            "ts_utc": record["ts_utc"],
            "module": module,
            "substream_label": substream_label,
            "seed": self.seed,
            "run_id": self.run_id,
            "rng_counter_before_hi": int(counter_before.counter_hi),
            "rng_counter_before_lo": int(counter_before.counter_lo),
            "rng_counter_after_hi": int(counter_after.counter_hi),
            "rng_counter_after_lo": int(counter_after.counter_lo),
            "draws_total": stats["draws"],
            "blocks_total": stats["blocks"],
            "events_total": stats["events"],
        }
        self._append_jsonl(self.trace_path, trace_payload)


class ZoneSharesRunner:
    """Deterministic Dirichlet share sampler for Segment 3A."""

    _SUBSTREAM_LABEL = "zone_dirichlet_share"
    _MODULE_NAME = "3A.zone_shares"

    def run(self, inputs: ZoneSharesInputs) -> ZoneSharesResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.resolve()
        manifest_fingerprint = inputs.manifest_fingerprint
        parameter_hash = inputs.parameter_hash
        seed = inputs.seed
        run_id = inputs.run_id
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise err("E_RUN_ID", "run_id must be 32 lowercase hex characters")

        s0_receipt = self._load_s0_receipt(
            base=data_root, manifest_fingerprint=manifest_fingerprint, dictionary=dictionary
        )
        self._assert_upstream_pass(s0_receipt)
        if str(s0_receipt.get("parameter_hash")) != str(parameter_hash):
            raise err("E_PARAM_HASH", "parameter_hash mismatch between inputs and S0 receipt")

        s1_path = data_root / render_dataset_path(
            dataset_id="s1_escalation_queue",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        s2_path = data_root / render_dataset_path(
            dataset_id="s2_country_zone_priors",
            template_args={"parameter_hash": parameter_hash},
            dictionary=dictionary,
        )
        if not s1_path.exists() or not s2_path.exists():
            raise err("E_UPSTREAM_MISSING", "S1 escalation queue or S2 priors missing for S3")

        s1_df = pl.read_parquet(s1_path)
        s2_df = pl.read_parquet(s2_path)
        escalated = s1_df.filter(pl.col("is_escalated"))
        if escalated.is_empty():
            output_dir = data_root / render_dataset_path(
                dataset_id="s3_zone_shares",
                template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
                dictionary=dictionary,
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            empty_df = pl.DataFrame(
                schema={
                    "seed": pl.Int64,
                    "fingerprint": pl.Utf8,
                    "merchant_id": pl.Int64,
                    "legal_country_iso": pl.Utf8,
                    "tzid": pl.Utf8,
                    "share_drawn": pl.Float64,
                    "share_sum_country": pl.Float64,
                    "alpha_sum_country": pl.Float64,
                    "prior_pack_id": pl.Utf8,
                    "prior_pack_version": pl.Utf8,
                    "floor_policy_id": pl.Utf8,
                    "floor_policy_version": pl.Utf8,
                    "rng_module": pl.Utf8,
                    "rng_substream_label": pl.Utf8,
                    "rng_stream_id": pl.Utf8,
                    "rng_event_id": pl.Utf8,
                    "notes": pl.Utf8,
                }
            )
            output_file = output_dir / "part-0.parquet"
            empty_df.write_parquet(output_file)
            run_report_path = data_root / render_dataset_path(
                dataset_id="s3_run_report_3A",
                template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
                dictionary=dictionary,
            )
            run_report_path.parent.mkdir(parents=True, exist_ok=True)
            run_report_path.write_text(
                json.dumps(
                    {
                        "layer": "layer1",
                        "segment": "3A",
                        "state": "S3",
                        "status": "PASS",
                        "seed": seed,
                        "manifest_fingerprint": manifest_fingerprint,
                        "parameter_hash": parameter_hash,
                        "run_id": run_id,
                        "pairs_total": 0,
                        "zones_total": 0,
                        "resumed": False,
                        "rng_events_path": None,
                        "rng_trace_path": str(rng_trace_path),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            rng_trace_path = data_root / "logs/rng/trace" / f"seed={seed}" / f"parameter_hash={parameter_hash}" / f"run_id={run_id}" / "rng_trace_log.jsonl"
            rng_trace_path.parent.mkdir(parents=True, exist_ok=True)
            rng_trace_path.touch(exist_ok=True)
            return ZoneSharesResult(
                output_path=output_dir, run_report_path=run_report_path, rng_trace_path=rng_trace_path, resumed=False
            )

        priors_by_country = self._build_prior_index(s2_df)
        engine = PhiloxEngine(seed=seed, manifest_fingerprint=manifest_fingerprint)
        event_writer = _DirichletEventWriter(
            base_path=data_root,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            run_id=run_id,
        )

        rows = []
        for pair in escalated.to_dicts():
            merchant_id = int(pair["merchant_id"])
            country = str(pair["legal_country_iso"])
            priors = priors_by_country.get(country)
            if priors is None or not priors:
                raise err("E_PRIOR_MISSING", f"no priors found for country '{country}'")
            substream = engine.derive_substream(
                self._SUBSTREAM_LABEL,
                (comp_u64(merchant_id), comp_iso(country)),
            )
            before_state = substream.snapshot()
            before_blocks, before_draws = substream.blocks, substream.draws
            gamma_values = []
            event_meta = []
            alpha_sum = 0.0
            for prior in priors:
                alpha = float(prior["alpha_effective"])
                alpha_sum += alpha
                before_state = substream.snapshot()
                before_blocks, before_draws = substream.blocks, substream.draws
                gamma_value = substream.gamma(alpha)
                after_state = substream.snapshot()
                blocks_used = substream.blocks - before_blocks
                draws_used = substream.draws - before_draws
                gamma_values.append((prior, gamma_value))
                event_meta.append(
                    {
                        "prior": prior,
                        "gamma_value": gamma_value,
                        "before_state": before_state,
                        "after_state": after_state,
                        "draws_used": draws_used,
                        "blocks_used": blocks_used,
                    }
                )
            gamma_total = sum(value for _, value in gamma_values)
            if gamma_total <= 0.0:
                raise err("E_DIRICHLET_DEGENERATE", f"gamma total zero for {merchant_id}/{country}")
            shares = [(prior, value / gamma_total) for prior, value in gamma_values]
            share_sum_total = sum(val for _, val in shares)
            for entry in event_meta:
                prior = entry["prior"]
                share_value = entry["gamma_value"] / gamma_total
                event_writer.write_dirichlet_event(
                    merchant_id=merchant_id,
                    country_iso=country,
                    tzid=str(prior["tzid"]),
                    counter_before=entry["before_state"],
                    counter_after=entry["after_state"],
                    draws_used=entry["draws_used"],
                    blocks_used=entry["blocks_used"],
                    share_drawn=float(share_value),
                    alpha_sum=alpha_sum,
                    module=self._MODULE_NAME,
                    substream_label=self._SUBSTREAM_LABEL,
                    prior_pack_id=str(prior["prior_pack_id"]),
                    prior_pack_version=str(prior["prior_pack_version"]),
                )

            for prior, share_value in shares:
                rows.append(
                    {
                        "seed": seed,
                        "fingerprint": manifest_fingerprint,
                        "merchant_id": merchant_id,
                        "legal_country_iso": country,
                        "tzid": prior["tzid"],
                        "share_drawn": float(share_value),
                        "share_sum_country": float(share_sum_total),
                        "alpha_sum_country": float(alpha_sum),
                        "prior_pack_id": prior["prior_pack_id"],
                        "prior_pack_version": prior["prior_pack_version"],
                        "floor_policy_id": prior["floor_policy_id"],
                        "floor_policy_version": prior["floor_policy_version"],
                        "rng_module": self._MODULE_NAME,
                        "rng_substream_label": self._SUBSTREAM_LABEL,
                        "rng_stream_id": f"{self._SUBSTREAM_LABEL}|{merchant_id}|{country}",
                        "rng_event_id": None,
                        "notes": None,
                    }
                )

        output_dir = data_root / render_dataset_path(
            dataset_id="s3_zone_shares",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "part-0.parquet"
        resumed = False
        schema = {
            "seed": pl.Int64,
            "fingerprint": pl.Utf8,
            "merchant_id": pl.UInt64,
            "legal_country_iso": pl.Utf8,
            "tzid": pl.Utf8,
            "share_drawn": pl.Float64,
            "share_sum_country": pl.Float64,
            "alpha_sum_country": pl.Float64,
            "prior_pack_id": pl.Utf8,
            "prior_pack_version": pl.Utf8,
            "floor_policy_id": pl.Utf8,
            "floor_policy_version": pl.Utf8,
            "rng_module": pl.Utf8,
            "rng_substream_label": pl.Utf8,
            "rng_stream_id": pl.Utf8,
            "rng_event_id": pl.Utf8,
            "notes": pl.Utf8,
        }
        result_df = pl.DataFrame(rows, schema=schema)
        if output_file.exists():
            existing = pl.read_parquet(output_file)
            if not _frames_equal(existing, result_df):
                raise err(
                    "E_IMMUTABILITY",
                    f"s3_zone_shares already exists at '{output_file}' with different content",
                )
            resumed = True
        else:
            result_df.write_parquet(output_file)

        run_report_path = data_root / render_dataset_path(
            dataset_id="s3_run_report_3A",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer1",
            "segment": "3A",
            "state": "S3",
            "status": "PASS",
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
            "pairs_total": len(
                {(int(row["merchant_id"]), str(row["legal_country_iso"])) for row in result_df.to_dicts()}
            ),
            "zones_total": result_df.height,
            "resumed": resumed,
            "rng_events_path": str(event_writer.events_path),
            "rng_trace_path": str(event_writer.trace_path),
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")
        key = SegmentStateKey(
            layer="layer1",
            segment="3A",
            state="S3",
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
        )
        report_path = data_root / render_dataset_path(
            dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
        )
        write_segment_state_run_report(
            path=report_path,
            key=key,
            payload={
                **key.as_dict(),
                "status": "PASS",
                "attempt": 1,
                "output_path": str(output_file),
                "run_report_path": str(run_report_path),
                "rng_trace_path": str(event_writer.trace_path),
                "resumed": resumed,
            },
        )

        return ZoneSharesResult(
            output_path=output_dir,
            run_report_path=run_report_path,
            rng_trace_path=event_writer.trace_path,
            resumed=resumed,
        )

    # ------------------------------------------------------------------ #
    def _load_s0_receipt(self, *, base: Path, manifest_fingerprint: str, dictionary: Mapping[str, object]) -> Mapping[str, Any]:
        receipt_path = base / render_dataset_path(
            dataset_id="s0_gate_receipt_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not receipt_path.exists():
            raise err("E_S0_PRECONDITION", f"S0 receipt missing at '{receipt_path}'")
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        for field in _S0_RECEIPT_FIELDS:
            if field not in payload:
                raise err("E_S0_PRECONDITION", f"S0 receipt missing field '{field}'")
        self._validate_schema(payload)
        return payload

    def _validate_schema(self, payload: Mapping[str, Any]) -> None:
        from jsonschema import Draft202012Validator, ValidationError

        try:
            Draft202012Validator(_S0_RECEIPT_SCHEMA).validate(payload)
        except ValidationError as exc:
            raise err("E_SCHEMA", f"s0 receipt invalid: {exc.message}") from exc

    def _assert_upstream_pass(self, receipt: Mapping[str, Any]) -> None:
        gates = receipt.get("upstream_gates", {})
        for segment in ("segment_1A", "segment_1B", "segment_2A"):
            status = gates.get(segment, {}).get("status")
            if status != "PASS":
                raise err("E_UPSTREAM_GATE", f"{segment} status '{status}' is not PASS")

    def _build_prior_index(self, priors_df: pl.DataFrame) -> dict[str, list[Mapping[str, Any]]]:
        required_cols = {"country_iso", "tzid", "alpha_effective"}
        if not required_cols.issubset(set(priors_df.columns)):
            raise err("E_PRIOR_SCHEMA", "priors dataframe missing required columns")
        result: dict[str, list[Mapping[str, Any]]] = {}
        for row in priors_df.to_dicts():
            country = str(row["country_iso"])
            result.setdefault(country, []).append(row)
        for country, rows in result.items():
            rows.sort(key=lambda r: str(r["tzid"]))
        return result
