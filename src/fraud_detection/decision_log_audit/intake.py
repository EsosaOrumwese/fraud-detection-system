"""Decision Log & Audit intake processor + bus consumer (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from pathlib import Path
from typing import Any

from fraud_detection.event_bus import EventBusReader

from .config import DecisionLogAuditIntakePolicy
from .inlet import (
    DLA_INLET_RUN_SCOPE_MISMATCH,
    DlaBusInput,
    DecisionLogAuditInlet,
)
from .storage import DecisionLogAuditIndexStoreError, DecisionLogAuditIntakeStore


logger = logging.getLogger("fraud_detection.dla")

DLA_INTAKE_WRITE_FAILED = "WRITE_FAILED"
DLA_INTAKE_PAYLOAD_HASH_MISMATCH = "PAYLOAD_HASH_MISMATCH"
DLA_INTAKE_LINEAGE_CONFLICT = "LINEAGE_CONFLICT"
DLA_INTAKE_REPLAY_DIVERGENCE = "REPLAY_DIVERGENCE"
DLA_INTAKE_RUN_SCOPE_SKIPPED = "RUN_SCOPE_SKIPPED"


@dataclass(frozen=True)
class DecisionLogAuditIntakeResult:
    accepted: bool
    reason_code: str
    detail: str | None
    checkpoint_advanced: bool
    write_status: str | None


@dataclass(frozen=True)
class DecisionLogAuditIntakeRuntimeConfig:
    event_bus_kind: str = "file"
    event_bus_root: str = "runs/fraud-platform/eb"
    event_bus_stream: str | None = "auto"
    event_bus_region: str | None = None
    event_bus_endpoint_url: str | None = None
    event_bus_start_position: str = "trim_horizon"
    poll_max_records: int = 200
    poll_sleep_seconds: float = 1.0


class DecisionLogAuditIntakeProcessor:
    def __init__(
        self,
        policy: DecisionLogAuditIntakePolicy,
        store: DecisionLogAuditIntakeStore,
        *,
        engine_contracts_root: Path | str = "docs/model_spec/data-engine/interface_pack/contracts",
    ) -> None:
        self.policy = policy
        self.store = store
        self.inlet = DecisionLogAuditInlet(policy, engine_contracts_root=engine_contracts_root)

    def process_record(self, record: DlaBusInput) -> DecisionLogAuditIntakeResult:
        envelope = _unwrap_record_envelope(record.payload) or {}
        event_type = str((envelope or {}).get("event_type") or "") or None
        event_id = str((envelope or {}).get("event_id") or "") or None
        pins = _unwrap_record_pins(record.payload) or {}
        platform_run_id = str(pins.get("platform_run_id") or "") or None
        scenario_run_id = str(pins.get("scenario_run_id") or "") or None

        result = self.inlet.evaluate(record)
        if not result.accepted:
            if result.reason_code == DLA_INLET_RUN_SCOPE_MISMATCH:
                return self._finalize_result(
                    record=record,
                    platform_run_id=platform_run_id,
                    scenario_run_id=scenario_run_id,
                    event_type=event_type,
                    event_id=event_id,
                    result=self._skip_and_checkpoint(
                        record=record,
                        reason_code=result.reason_code,
                        detail=result.detail,
                        event_type=str(_unwrap_record_event_type(record.payload) or ""),
                        event_id=str(_unwrap_record_event_id(record.payload) or ""),
                    ),
                )
            return self._finalize_result(
                record=record,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_type=event_type,
                event_id=event_id,
                result=self._quarantine_and_checkpoint(
                    record=record,
                    reason_code=result.reason_code,
                    detail=result.detail,
                    event_type=str(_unwrap_record_event_type(record.payload) or ""),
                    event_id=str(_unwrap_record_event_id(record.payload) or ""),
                    schema_version=str(_unwrap_record_schema_version(record.payload) or ""),
                    payload_hash=None,
                    pins=_unwrap_record_pins(record.payload),
                    envelope=_unwrap_record_envelope(record.payload),
                ),
            )

        assert result.candidate is not None
        candidate = result.candidate
        try:
            replay = self.store.record_replay_observation(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                platform_run_id=str(candidate.pins.get("platform_run_id") or ""),
                scenario_run_id=str(candidate.pins.get("scenario_run_id") or ""),
                event_type=candidate.event_type,
                event_id=candidate.event_id,
                payload_hash=candidate.payload_hash,
            )
        except Exception as exc:
            return self._finalize_result(
                record=record,
                platform_run_id=str(candidate.pins.get("platform_run_id") or "") or None,
                scenario_run_id=str(candidate.pins.get("scenario_run_id") or "") or None,
                event_type=candidate.event_type,
                event_id=candidate.event_id,
                result=DecisionLogAuditIntakeResult(
                    accepted=False,
                    reason_code=DLA_INTAKE_WRITE_FAILED,
                    detail=str(exc)[:256],
                    checkpoint_advanced=False,
                    write_status=None,
                ),
            )

        if replay.status == "DIVERGENCE":
            return self._finalize_result(
                record=record,
                platform_run_id=str(candidate.pins.get("platform_run_id") or "") or None,
                scenario_run_id=str(candidate.pins.get("scenario_run_id") or "") or None,
                event_type=candidate.event_type,
                event_id=candidate.event_id,
                result=self._quarantine_without_checkpoint(
                    record=record,
                    reason_code=DLA_INTAKE_REPLAY_DIVERGENCE,
                    detail=replay.detail,
                    event_type=candidate.event_type,
                    event_id=candidate.event_id,
                    schema_version=candidate.schema_version,
                    payload_hash=candidate.payload_hash,
                    pins=candidate.pins,
                    envelope=candidate.envelope,
                ),
            )

        try:
            write = self.store.append_candidate(
                platform_run_id=str(candidate.pins.get("platform_run_id") or ""),
                scenario_run_id=str(candidate.pins.get("scenario_run_id") or ""),
                event_type=candidate.event_type,
                event_id=candidate.event_id,
                schema_version=candidate.schema_version,
                payload_hash=candidate.payload_hash,
                source_topic=record.topic,
                source_partition=record.partition,
                source_offset=record.offset,
                source_offset_kind=record.offset_kind,
                source_ts_utc=candidate.source_ts_utc or None,
                published_at_utc=record.published_at_utc,
                envelope=candidate.envelope,
            )
        except Exception as exc:
            return self._finalize_result(
                record=record,
                platform_run_id=str(candidate.pins.get("platform_run_id") or "") or None,
                scenario_run_id=str(candidate.pins.get("scenario_run_id") or "") or None,
                event_type=candidate.event_type,
                event_id=candidate.event_id,
                result=DecisionLogAuditIntakeResult(
                    accepted=False,
                    reason_code=DLA_INTAKE_WRITE_FAILED,
                    detail=str(exc)[:256],
                    checkpoint_advanced=False,
                    write_status=None,
                ),
            )

        if write.status in {"NEW", "DUPLICATE"}:
            try:
                lineage = self.store.apply_lineage_candidate(
                    platform_run_id=str(candidate.pins.get("platform_run_id") or ""),
                    scenario_run_id=str(candidate.pins.get("scenario_run_id") or ""),
                    event_type=candidate.event_type,
                    event_id=candidate.event_id,
                    schema_version=candidate.schema_version,
                    payload_hash=candidate.payload_hash,
                    payload=(candidate.envelope.get("payload") if isinstance(candidate.envelope.get("payload"), dict) else {}),
                    source_ref=candidate.source_eb_ref.as_dict(),
                )
            except Exception as exc:
                return self._finalize_result(
                    record=record,
                    platform_run_id=str(candidate.pins.get("platform_run_id") or "") or None,
                    scenario_run_id=str(candidate.pins.get("scenario_run_id") or "") or None,
                    event_type=candidate.event_type,
                    event_id=candidate.event_id,
                    result=DecisionLogAuditIntakeResult(
                        accepted=False,
                        reason_code=DLA_INTAKE_WRITE_FAILED,
                        detail=str(exc)[:256],
                        checkpoint_advanced=False,
                        write_status=None,
                    ),
                )
            if lineage.status == "CONFLICT":
                return self._finalize_result(
                    record=record,
                    platform_run_id=str(candidate.pins.get("platform_run_id") or "") or None,
                    scenario_run_id=str(candidate.pins.get("scenario_run_id") or "") or None,
                    event_type=candidate.event_type,
                    event_id=candidate.event_id,
                    result=self._quarantine_and_checkpoint(
                        record=record,
                        reason_code=DLA_INTAKE_LINEAGE_CONFLICT,
                        detail=f"decision_id={lineage.decision_id};unresolved={','.join(lineage.unresolved_reasons)}",
                        event_type=candidate.event_type,
                        event_id=candidate.event_id,
                        schema_version=candidate.schema_version,
                        payload_hash=candidate.payload_hash,
                        pins=candidate.pins,
                        envelope=candidate.envelope,
                    ),
                )
            checkpoint_advanced = self._advance_checkpoint_safely(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_ts_utc=candidate.source_ts_utc or None,
            )
            return self._finalize_result(
                record=record,
                platform_run_id=str(candidate.pins.get("platform_run_id") or "") or None,
                scenario_run_id=str(candidate.pins.get("scenario_run_id") or "") or None,
                event_type=candidate.event_type,
                event_id=candidate.event_id,
                result=DecisionLogAuditIntakeResult(
                    accepted=True,
                    reason_code=result.reason_code,
                    detail=result.detail,
                    checkpoint_advanced=checkpoint_advanced,
                    write_status=write.status,
                ),
            )

        return self._finalize_result(
            record=record,
            platform_run_id=str(candidate.pins.get("platform_run_id") or "") or None,
            scenario_run_id=str(candidate.pins.get("scenario_run_id") or "") or None,
            event_type=candidate.event_type,
            event_id=candidate.event_id,
            result=self._quarantine_and_checkpoint(
                record=record,
                reason_code=DLA_INTAKE_PAYLOAD_HASH_MISMATCH,
                detail=f"event_type={candidate.event_type} event_id={candidate.event_id}",
                event_type=candidate.event_type,
                event_id=candidate.event_id,
                schema_version=candidate.schema_version,
                payload_hash=candidate.payload_hash,
                pins=candidate.pins,
                envelope=candidate.envelope,
            ),
        )

    def _finalize_result(
        self,
        *,
        record: DlaBusInput,
        platform_run_id: str | None,
        scenario_run_id: str | None,
        event_type: str | None,
        event_id: str | None,
        result: DecisionLogAuditIntakeResult,
    ) -> DecisionLogAuditIntakeResult:
        try:
            self.store.record_intake_attempt(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_type=event_type,
                event_id=event_id,
                accepted=result.accepted,
                reason_code=result.reason_code,
                write_status=result.write_status,
                checkpoint_advanced=result.checkpoint_advanced,
                detail=result.detail,
            )
        except Exception as exc:
            logger.error("DLA intake attempt logging failed: %s", exc)
        return result

    def _quarantine_without_checkpoint(
        self,
        *,
        record: DlaBusInput,
        reason_code: str,
        detail: str | None,
        event_type: str,
        event_id: str,
        schema_version: str,
        payload_hash: str | None,
        pins: dict[str, Any] | None,
        envelope: dict[str, Any] | None,
    ) -> DecisionLogAuditIntakeResult:
        try:
            write = self.store.append_quarantine(
                reason_code=reason_code,
                detail=detail,
                source_topic=record.topic,
                source_partition=record.partition,
                source_offset=record.offset,
                source_offset_kind=record.offset_kind,
                platform_run_id=str((pins or {}).get("platform_run_id") or "") or None,
                scenario_run_id=str((pins or {}).get("scenario_run_id") or "") or None,
                event_type=event_type or None,
                event_id=event_id or None,
                schema_version=schema_version or None,
                payload_hash=payload_hash,
                source_ts_utc=str((envelope or {}).get("ts_utc") or "") or None,
                published_at_utc=record.published_at_utc,
                envelope=envelope or {},
            )
        except Exception as exc:
            return DecisionLogAuditIntakeResult(
                accepted=False,
                reason_code=DLA_INTAKE_WRITE_FAILED,
                detail=str(exc)[:256],
                checkpoint_advanced=False,
                write_status=None,
            )
        return DecisionLogAuditIntakeResult(
            accepted=False,
            reason_code=reason_code,
            detail=detail,
            checkpoint_advanced=False,
            write_status=write.status,
        )

    def _skip_and_checkpoint(
        self,
        *,
        record: DlaBusInput,
        reason_code: str,
        detail: str | None,
        event_type: str,
        event_id: str,
    ) -> DecisionLogAuditIntakeResult:
        checkpoint_advanced = self._advance_checkpoint_safely(
            topic=record.topic,
            partition=record.partition,
            offset=record.offset,
            offset_kind=record.offset_kind,
            event_ts_utc=None,
        )
        return DecisionLogAuditIntakeResult(
            accepted=False,
            reason_code=reason_code or DLA_INTAKE_RUN_SCOPE_SKIPPED,
            detail=detail,
            checkpoint_advanced=checkpoint_advanced,
            write_status=DLA_INTAKE_RUN_SCOPE_SKIPPED,
        )

    def _quarantine_and_checkpoint(
        self,
        *,
        record: DlaBusInput,
        reason_code: str,
        detail: str | None,
        event_type: str,
        event_id: str,
        schema_version: str,
        payload_hash: str | None,
        pins: dict[str, Any] | None,
        envelope: dict[str, Any] | None,
    ) -> DecisionLogAuditIntakeResult:
        try:
            write = self.store.append_quarantine(
                reason_code=reason_code,
                detail=detail,
                source_topic=record.topic,
                source_partition=record.partition,
                source_offset=record.offset,
                source_offset_kind=record.offset_kind,
                platform_run_id=str((pins or {}).get("platform_run_id") or "") or None,
                scenario_run_id=str((pins or {}).get("scenario_run_id") or "") or None,
                event_type=event_type or None,
                event_id=event_id or None,
                schema_version=schema_version or None,
                payload_hash=payload_hash,
                source_ts_utc=str((envelope or {}).get("ts_utc") or "") or None,
                published_at_utc=record.published_at_utc,
                envelope=envelope or {},
            )
        except Exception as exc:
            return DecisionLogAuditIntakeResult(
                accepted=False,
                reason_code=DLA_INTAKE_WRITE_FAILED,
                detail=str(exc)[:256],
                checkpoint_advanced=False,
                write_status=None,
            )

        checkpoint_advanced = self._advance_checkpoint_safely(
            topic=record.topic,
            partition=record.partition,
            offset=record.offset,
            offset_kind=record.offset_kind,
            event_ts_utc=str((envelope or {}).get("ts_utc") or "") or None,
        )
        return DecisionLogAuditIntakeResult(
            accepted=False,
            reason_code=reason_code,
            detail=detail,
            checkpoint_advanced=checkpoint_advanced,
            write_status=write.status,
        )

    def _advance_checkpoint_safely(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_ts_utc: str | None,
    ) -> bool:
        try:
            self.store.advance_checkpoint(
                topic=topic,
                partition=partition,
                offset=offset,
                offset_kind=offset_kind,
                event_ts_utc=event_ts_utc,
            )
        except Exception as exc:
            logger.error("DLA checkpoint advance blocked: %s", exc)
            return False
        return True


class DecisionLogAuditBusConsumer:
    def __init__(
        self,
        *,
        policy: DecisionLogAuditIntakePolicy,
        store: DecisionLogAuditIntakeStore,
        runtime: DecisionLogAuditIntakeRuntimeConfig | None = None,
        engine_contracts_root: Path | str = "docs/model_spec/data-engine/interface_pack/contracts",
    ) -> None:
        self.policy = policy
        self.store = store
        self.runtime = runtime or DecisionLogAuditIntakeRuntimeConfig()
        self.processor = DecisionLogAuditIntakeProcessor(
            policy,
            store,
            engine_contracts_root=engine_contracts_root,
        )
        self._file_reader = None
        self._kinesis_reader = None
        if self.runtime.event_bus_kind == "file":
            self._file_reader = EventBusReader(Path(self.runtime.event_bus_root))
        elif self.runtime.event_bus_kind == "kinesis":
            from fraud_detection.event_bus.kinesis import KinesisEventBusReader

            self._kinesis_reader = KinesisEventBusReader(
                stream_name=self.runtime.event_bus_stream,
                region=self.runtime.event_bus_region,
                endpoint_url=self.runtime.event_bus_endpoint_url,
            )
        else:
            raise DecisionLogAuditIndexStoreError("DLA_EVENT_BUS_KIND_UNSUPPORTED")

    def run_once(self) -> int:
        if self.runtime.event_bus_kind == "file":
            return self._run_file_once()
        return self._run_kinesis_once()

    def run_forever(self) -> None:
        while True:
            processed = self.run_once()
            if processed == 0:
                time.sleep(self.runtime.poll_sleep_seconds)

    def _run_file_once(self) -> int:
        assert self._file_reader is not None
        processed = 0
        for topic in self.policy.admitted_topics:
            for partition in self._file_partitions(topic):
                checkpoint = self.store.get_checkpoint(topic=topic, partition=partition)
                from_offset = int(checkpoint.next_offset) if checkpoint and checkpoint.offset_kind == "file_line" else 0
                records = self._file_reader.read(
                    topic,
                    partition=partition,
                    from_offset=from_offset,
                    max_records=self.runtime.poll_max_records,
                )
                for record in records:
                    bus_input = DlaBusInput(
                        topic=topic,
                        partition=partition,
                        offset=str(record.offset),
                        offset_kind="file_line",
                        payload=record.record if isinstance(record.record, dict) else {},
                        published_at_utc=(record.record or {}).get("published_at_utc") if isinstance(record.record, dict) else None,
                    )
                    self.processor.process_record(bus_input)
                    processed += 1
        return processed

    def _run_kinesis_once(self) -> int:
        assert self._kinesis_reader is not None
        processed = 0
        for topic in self.policy.admitted_topics:
            stream = self._stream_name(topic)
            for shard_id in self._kinesis_reader.list_shards(stream):
                partition = _partition_id_from_shard(shard_id)
                checkpoint = self.store.get_checkpoint(topic=topic, partition=partition)
                from_sequence = checkpoint.next_offset if checkpoint else None
                start_position = self.runtime.event_bus_start_position
                if checkpoint is None and self.policy.required_platform_run_id:
                    start_position = "trim_horizon"
                records = self._kinesis_reader.read(
                    stream_name=stream,
                    shard_id=shard_id,
                    from_sequence=from_sequence,
                    limit=self.runtime.poll_max_records,
                    start_position=start_position,
                )
                for record in records:
                    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
                    bus_input = DlaBusInput(
                        topic=topic,
                        partition=partition,
                        offset=str(record.get("sequence_number") or ""),
                        offset_kind="kinesis_sequence",
                        payload=payload,
                        published_at_utc=str(record.get("published_at_utc") or "") or None,
                    )
                    self.processor.process_record(bus_input)
                    processed += 1
        return processed

    def _stream_name(self, topic: str) -> str:
        stream = self.runtime.event_bus_stream
        if stream and str(stream).lower() not in {"", "auto", "topic"}:
            return str(stream)
        return topic

    def _file_partitions(self, topic: str) -> list[int]:
        assert self._file_reader is not None
        root = Path(self._file_reader.root) / topic
        if not root.exists():
            return [0]
        partitions: list[int] = []
        for path in root.glob("partition=*.jsonl"):
            token = path.stem.replace("partition=", "")
            try:
                partitions.append(int(token))
            except ValueError:
                continue
        if not partitions:
            return [0]
        return sorted(set(partitions))


def _partition_id_from_shard(shard_id: str) -> int:
    token = str(shard_id).rsplit("-", 1)[-1]
    try:
        return int(token)
    except ValueError:
        return 0


def _unwrap_record_envelope(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    nested = payload.get("envelope")
    if isinstance(nested, dict):
        return dict(nested)
    return dict(payload)


def _unwrap_record_event_type(payload: dict[str, Any] | None) -> str | None:
    envelope = _unwrap_record_envelope(payload)
    if not isinstance(envelope, dict):
        return None
    return str(envelope.get("event_type") or "") or None


def _unwrap_record_event_id(payload: dict[str, Any] | None) -> str | None:
    envelope = _unwrap_record_envelope(payload)
    if not isinstance(envelope, dict):
        return None
    return str(envelope.get("event_id") or "") or None


def _unwrap_record_schema_version(payload: dict[str, Any] | None) -> str | None:
    envelope = _unwrap_record_envelope(payload)
    if not isinstance(envelope, dict):
        return None
    return str(envelope.get("schema_version") or "") or None


def _unwrap_record_pins(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    envelope = _unwrap_record_envelope(payload)
    if not isinstance(envelope, dict):
        return None
    pins: dict[str, Any] = {
        "platform_run_id": envelope.get("platform_run_id"),
        "scenario_run_id": envelope.get("scenario_run_id"),
    }
    return pins
