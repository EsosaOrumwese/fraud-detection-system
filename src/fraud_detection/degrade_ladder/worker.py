"""Degrade Ladder runtime worker CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any

import yaml

from fraud_detection.platform_runtime import RUNS_ROOT, resolve_platform_run_id, resolve_run_scoped_path

from .config import DlPolicyBundle, DlPolicyProfile, load_policy_bundle
from .emission import DlControlPublisher, DlDrainResult, build_outbox_store
from .evaluator import evaluate_posture_safe, resolve_scope
from .ops import DlOpsStore, build_ops_store
from .signals import DlSignalSample, build_signal_snapshot
from .store import DlCurrentPosture, DlPostureStore, build_store


logger = logging.getLogger("fraud_detection.dl.worker")
_ENV_PATTERN = re.compile(r"^\$\{([^}:]+)(?::-([^}]*))?\}$")


@dataclass(frozen=True)
class DlWorkerConfig:
    profile_path: Path
    policy_ref: Path
    policy_profile_id: str
    stream_id: str
    scope_key: str
    store_dsn: str
    outbox_dsn: str
    ops_dsn: str
    poll_seconds: float
    max_age_seconds: int
    outbox_max_events: int
    outbox_max_attempts: int
    outbox_backoff_seconds: int
    platform_run_id: str | None
    registry_snapshot_ref: Path | None


@dataclass(frozen=True)
class SignalState:
    status: str
    value: Any
    detail: str | None
    source: str


class DlJsonlPublisher(DlControlPublisher):
    def __init__(self, path: Path) -> None:
        self.path = path

    def publish(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "published_at_utc": _utc_now(),
            "event": event,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")


class DegradeLadderWorker:
    def __init__(self, config: DlWorkerConfig) -> None:
        self.config = config
        self.bundle: DlPolicyBundle = load_policy_bundle(config.policy_ref)
        self.profile: DlPolicyProfile = self.bundle.profile(config.policy_profile_id)
        self.store: DlPostureStore = build_store(config.store_dsn, stream_id=config.stream_id)
        self.outbox = build_outbox_store(config.outbox_dsn, stream_id=config.stream_id)
        self.ops: DlOpsStore = build_ops_store(config.ops_dsn, stream_id=config.stream_id)
        self.publisher = DlJsonlPublisher(path=self._control_events_path())
        self._last_drain_result: DlDrainResult | None = None
        self._policy_activation_recorded = False

    def run_once(self) -> dict[str, Any]:
        now_utc = _utc_now()
        if not self._policy_activation_recorded:
            self.ops.record_policy_activation(
                scope_key=self.config.scope_key,
                policy_rev=self.bundle.policy_rev,
                actor="SYSTEM::degrade_ladder_worker",
                reason="WORKER_START",
                ts_utc=now_utc,
                metadata={
                    "profile_id": self.profile.profile_id,
                    "stream_id": self.config.stream_id,
                },
            )
            self._policy_activation_recorded = True

        prior = self._read_prior()
        samples = self._collect_signal_samples(scope_key=self.config.scope_key, observed_at_utc=now_utc)
        snapshot = build_signal_snapshot(
            samples,
            scope_key=self.config.scope_key,
            decision_time_utc=now_utc,
            required_signal_names=self.profile.signal_policy.required_signals,
            optional_signal_names=self.profile.signal_policy.optional_signals,
            required_max_age_seconds=self.profile.signal_policy.required_max_age_seconds,
        )
        self.ops.record_signal_snapshot(scope_key=self.config.scope_key, snapshot=snapshot, ts_utc=now_utc)

        posture_seq = 1 if prior is None else int(prior.decision.posture_seq) + 1
        decision = evaluate_posture_safe(
            profile=self.profile,
            policy_rev=self.bundle.policy_rev,
            snapshot=snapshot,
            decision_time_utc=now_utc,
            scope_key=self.config.scope_key,
            posture_seq=posture_seq,
            prior_decision=None if prior is None else prior.decision,
        )
        commit = self.store.commit_current(scope_key=self.config.scope_key, decision=decision)

        previous_mode = None if prior is None else prior.decision.mode
        transition_source = "WORKER_LOOP"
        if snapshot.has_required_gaps:
            transition_source = "WORKER_LOOP_REQUIRED_SIGNAL_GAP"
        self.ops.record_posture_transition(
            scope_key=self.config.scope_key,
            decision=decision,
            previous_mode=previous_mode,
            source=transition_source,
            forced_fail_closed=(decision.mode == "FAIL_CLOSED" and snapshot.has_required_gaps),
            reason_codes=tuple(sorted({state.state for state in snapshot.states if state.required})),
            ts_utc=now_utc,
        )

        enqueued = False
        change_kind = "HEARTBEAT"
        if prior is None:
            change_kind = "INITIAL"
        elif prior.decision.mode != decision.mode:
            change_kind = "MODE_CHANGE"
        if change_kind in {"INITIAL", "MODE_CHANGE"}:
            enqueued = self.outbox.enqueue_posture_change(
                scope_key=self.config.scope_key,
                decision=decision,
                change_kind=change_kind,
                triggers_summary=_trigger_summary(snapshot=snapshot),
            )
        self._last_drain_result = self.outbox.drain_once(
            publisher=self.publisher,
            max_events=self.config.outbox_max_events,
            max_attempts=self.config.outbox_max_attempts,
            base_backoff_seconds=self.config.outbox_backoff_seconds,
            now_utc=now_utc,
        )
        outbox_metrics = self.outbox.metrics(now_utc=now_utc).as_dict()

        return {
            "ts_utc": now_utc,
            "scope_key": self.config.scope_key,
            "mode": decision.mode,
            "posture_seq": decision.posture_seq,
            "commit_status": commit.status,
            "change_kind": change_kind,
            "outbox_enqueued": enqueued,
            "outbox_drain": {
                "considered": self._last_drain_result.considered,
                "published": self._last_drain_result.published,
                "failed": self._last_drain_result.failed,
                "dead_lettered": self._last_drain_result.dead_lettered,
                "pending_backlog": self._last_drain_result.pending_backlog,
            },
            "outbox_metrics": outbox_metrics,
            "required_signal_states": {
                state.name: state.state for state in snapshot.states if state.required
            },
        }

    def run_forever(self) -> None:
        while True:
            payload = self.run_once()
            logger.info("DL worker tick: %s", json.dumps(payload, sort_keys=True, ensure_ascii=True))
            time.sleep(self.config.poll_seconds)

    def _collect_signal_samples(self, *, scope_key: str, observed_at_utc: str) -> list[DlSignalSample]:
        rows: list[DlSignalSample] = []
        tracked = list(self.profile.signal_policy.required_signals) + list(self.profile.signal_policy.optional_signals)
        seen: set[str] = set()
        for name in tracked:
            if name in seen:
                continue
            seen.add(name)
            state = self._resolve_signal(name=name, observed_at_utc=observed_at_utc)
            rows.append(
                DlSignalSample(
                    name=name,
                    scope_key=scope_key,
                    observed_at_utc=observed_at_utc,
                    status=state.status,
                    value=state.value,
                    source=state.source,
                    detail=state.detail,
                )
            )
        return rows

    def _resolve_signal(self, *, name: str, observed_at_utc: str) -> SignalState:
        if name == "posture_store_health":
            return self._signal_posture_store_health()
        if name == "ofp_health":
            return self._signal_component_health(
                component="online_feature_plane",
                key="health_state",
            )
        if name == "ieg_health":
            return self._signal_component_health(
                component="identity_entity_graph",
                key="health_state",
            )
        if name == "registry_health":
            return self._signal_registry_health()
        if name == "eb_consumer_lag":
            return self._signal_orchestrator_ready()
        if name == "control_publish_health":
            return self._signal_control_publish_health()
        return SignalState(
            status="ERROR",
            value={"signal": name},
            detail="UNSUPPORTED_SIGNAL",
            source="dl.worker",
        )

    def _signal_posture_store_health(self) -> SignalState:
        try:
            _ = self.store.read_current(scope_key=self.config.scope_key)
        except Exception as exc:
            return SignalState(
                status="ERROR",
                value={"error": str(exc)[:256]},
                detail="POSTURE_STORE_UNAVAILABLE",
                source="dl.worker",
            )
        return SignalState(
            status="OK",
            value={"state": "READY"},
            detail=None,
            source="dl.worker",
        )

    def _signal_component_health(self, *, component: str, key: str) -> SignalState:
        path = self._run_root() / component / "health" / "last_health.json"
        if not path.exists():
            return SignalState(
                status="ERROR",
                value={"path": str(path)},
                detail="HEALTH_ARTIFACT_MISSING",
                source=f"dl.worker:{component}",
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return SignalState(
                status="ERROR",
                value={"path": str(path), "error": str(exc)[:256]},
                detail="HEALTH_ARTIFACT_INVALID",
                source=f"dl.worker:{component}",
            )
        raw_state = str(payload.get(key) or payload.get("state") or "").strip().upper()
        if raw_state in {"GREEN", "CLEAN", "HEALTHY"}:
            return SignalState(status="OK", value={"state": raw_state}, detail=None, source=f"dl.worker:{component}")
        if raw_state:
            return SignalState(
                status="ERROR",
                value={"state": raw_state},
                detail="COMPONENT_HEALTH_NOT_GREEN",
                source=f"dl.worker:{component}",
            )
        return SignalState(
            status="ERROR",
            value={"path": str(path)},
            detail="HEALTH_STATE_MISSING",
            source=f"dl.worker:{component}",
        )

    def _signal_registry_health(self) -> SignalState:
        path = self.config.registry_snapshot_ref
        if path is None:
            return SignalState(
                status="ERROR",
                value={"path": None},
                detail="REGISTRY_SNAPSHOT_NOT_CONFIGURED",
                source="dl.worker:registry",
            )
        if not path.exists():
            return SignalState(
                status="ERROR",
                value={"path": str(path)},
                detail="REGISTRY_SNAPSHOT_MISSING",
                source="dl.worker:registry",
            )
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return SignalState(
                status="ERROR",
                value={"path": str(path), "error": str(exc)[:256]},
                detail="REGISTRY_SNAPSHOT_INVALID",
                source="dl.worker:registry",
            )
        if not isinstance(payload, dict):
            return SignalState(
                status="ERROR",
                value={"path": str(path)},
                detail="REGISTRY_SNAPSHOT_INVALID",
                source="dl.worker:registry",
            )
        if not str(payload.get("snapshot_id") or "").strip():
            return SignalState(
                status="ERROR",
                value={"path": str(path)},
                detail="REGISTRY_SNAPSHOT_ID_MISSING",
                source="dl.worker:registry",
            )
        return SignalState(
            status="OK",
            value={"snapshot_id": str(payload.get("snapshot_id"))},
            detail=None,
            source="dl.worker:registry",
        )

    def _signal_orchestrator_ready(self) -> SignalState:
        operate_root = RUNS_ROOT / "operate"
        candidate_paths = [
            operate_root / "local_parity_rtdl_core_v0" / "status" / "last_status.json",
            operate_root / "local_parity_rtdl_decision_lane_v0" / "status" / "last_status.json",
        ]
        readiness: list[dict[str, Any]] = []
        for path in candidate_paths:
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for row in list(payload.get("processes") or []):
                if not isinstance(row, dict):
                    continue
                ready_blob = row.get("readiness")
                ready = bool(isinstance(ready_blob, dict) and ready_blob.get("ready"))
                readiness.append(
                    {
                        "process_id": str(row.get("process_id") or ""),
                        "ready": ready,
                    }
                )
        if not readiness:
            return SignalState(
                status="ERROR",
                value={"status_paths": [str(path) for path in candidate_paths]},
                detail="ORCHESTRATOR_STATUS_MISSING",
                source="dl.worker:run_operate",
            )
        not_ready = [row["process_id"] for row in readiness if not row["ready"]]
        if not_ready:
            return SignalState(
                status="ERROR",
                value={"not_ready": not_ready},
                detail="DOWNSTREAM_NOT_READY",
                source="dl.worker:run_operate",
            )
        return SignalState(
            status="OK",
            value={"ready_processes": len(readiness)},
            detail=None,
            source="dl.worker:run_operate",
        )

    def _signal_control_publish_health(self) -> SignalState:
        if self._last_drain_result is None:
            return SignalState(
                status="OK",
                value={"state": "NO_PREVIOUS_DRAIN"},
                detail=None,
                source="dl.worker:outbox",
            )
        if self._last_drain_result.failed > 0 or self._last_drain_result.dead_lettered > 0:
            return SignalState(
                status="ERROR",
                value={
                    "failed": self._last_drain_result.failed,
                    "dead_lettered": self._last_drain_result.dead_lettered,
                },
                detail="OUTBOX_DRAIN_ERRORS",
                source="dl.worker:outbox",
            )
        return SignalState(
            status="OK",
            value={
                "published": self._last_drain_result.published,
                "pending_backlog": self._last_drain_result.pending_backlog,
            },
            detail=None,
            source="dl.worker:outbox",
        )

    def _control_events_path(self) -> Path:
        return self._run_root() / "degrade_ladder" / "control_events.jsonl"

    def _run_root(self) -> Path:
        run_id = self.config.platform_run_id
        if not run_id:
            return RUNS_ROOT / "_unknown"
        return RUNS_ROOT / run_id

    def _read_prior(self) -> DlCurrentPosture | None:
        try:
            return self.store.read_current(scope_key=self.config.scope_key)
        except Exception:
            return None


def load_worker_config(profile_path: Path) -> DlWorkerConfig:
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("DL_PROFILE_INVALID")

    profile_id = str(payload.get("profile_id") or "local")
    dl_payload = payload.get("dl") if isinstance(payload.get("dl"), dict) else {}
    policy = dl_payload.get("policy") if isinstance(dl_payload.get("policy"), dict) else {}
    wiring = dl_payload.get("wiring") if isinstance(dl_payload.get("wiring"), dict) else {}
    df_payload = payload.get("df") if isinstance(payload.get("df"), dict) else {}
    df_policy = df_payload.get("policy") if isinstance(df_payload.get("policy"), dict) else {}

    policy_ref = Path(
        _resolve_env_token(
            policy.get("profiles_ref")
            or os.getenv("DL_POLICY_PROFILES_REF")
            or "config/platform/dl/policy_profiles_v0.yaml"
        )
    )
    policy_profile_id = str(
        _resolve_env_token(
            policy.get("profile_id")
            or os.getenv("DL_POLICY_PROFILE_ID")
            or profile_id
        )
    ).strip() or profile_id

    store_dsn = _resolve_locator(
        wiring.get("store_dsn") or os.getenv("DL_POSTURE_DSN") or os.getenv("PARITY_IG_ADMISSION_DSN"),
        suffix="degrade_ladder/posture.sqlite",
    )
    outbox_dsn = _resolve_locator(
        wiring.get("outbox_dsn") or os.getenv("DL_OUTBOX_DSN") or store_dsn,
        suffix="degrade_ladder/outbox.sqlite",
    )
    ops_dsn = _resolve_locator(
        wiring.get("ops_dsn") or os.getenv("DL_OPS_DSN") or store_dsn,
        suffix="degrade_ladder/ops.sqlite",
    )

    platform_run_id = _resolve_platform_run_id()
    base_stream_id = str(
        _resolve_env_token(wiring.get("stream_id") or os.getenv("DL_STREAM_ID") or "dl.v0")
    ).strip()
    stream_id = base_stream_id
    if platform_run_id and "::" not in stream_id:
        stream_id = f"{stream_id}::{platform_run_id}"

    scope_kind = str(_resolve_env_token(wiring.get("scope_kind") or os.getenv("DL_SCOPE_KIND") or "GLOBAL")).strip().upper()
    scope = resolve_scope(
        scope_kind=scope_kind,
        manifest_fingerprint=_none_if_blank(_resolve_env_token(wiring.get("manifest_fingerprint") or os.getenv("DL_SCOPE_MANIFEST_FINGERPRINT"))),
        run_id=_none_if_blank(_resolve_env_token(wiring.get("run_id") or os.getenv("DL_SCOPE_RUN_ID"))),
        scenario_id=_none_if_blank(_resolve_env_token(wiring.get("scenario_id") or os.getenv("DL_SCOPE_SCENARIO_ID"))),
        parameter_hash=_none_if_blank(_resolve_env_token(wiring.get("parameter_hash") or os.getenv("DL_SCOPE_PARAMETER_HASH"))),
        seed=_none_if_blank(_resolve_env_token(wiring.get("seed") or os.getenv("DL_SCOPE_SEED"))),
    )

    registry_snapshot_ref = _none_if_blank(
        _resolve_env_token(
            df_policy.get("registry_snapshot_ref")
            or os.getenv("DF_REGISTRY_SNAPSHOT_REF")
        )
    )
    registry_snapshot_path = Path(registry_snapshot_ref) if registry_snapshot_ref else None

    return DlWorkerConfig(
        profile_path=profile_path,
        policy_ref=policy_ref,
        policy_profile_id=policy_profile_id,
        stream_id=stream_id,
        scope_key=scope.scope_key,
        store_dsn=store_dsn,
        outbox_dsn=outbox_dsn,
        ops_dsn=ops_dsn,
        poll_seconds=max(0.05, float(_resolve_env_token(wiring.get("poll_seconds") or os.getenv("DL_POLL_SECONDS") or 1.0))),
        max_age_seconds=max(1, int(_resolve_env_token(wiring.get("max_age_seconds") or os.getenv("DL_MAX_AGE_SECONDS") or 120))),
        outbox_max_events=max(1, int(_resolve_env_token(wiring.get("outbox_max_events") or os.getenv("DL_OUTBOX_MAX_EVENTS") or 25))),
        outbox_max_attempts=max(1, int(_resolve_env_token(wiring.get("outbox_max_attempts") or os.getenv("DL_OUTBOX_MAX_ATTEMPTS") or 5))),
        outbox_backoff_seconds=max(1, int(_resolve_env_token(wiring.get("outbox_backoff_seconds") or os.getenv("DL_OUTBOX_BACKOFF_SECONDS") or 1))),
        platform_run_id=platform_run_id,
        registry_snapshot_ref=registry_snapshot_path,
    )


def _resolve_locator(value: Any, *, suffix: str) -> str:
    resolved = _resolve_env_token(value)
    token = str(resolved or "").strip()
    scoped = resolve_run_scoped_path(token or None, suffix=suffix, create_if_missing=True)
    if not scoped:
        raise RuntimeError(f"DL_LOCATOR_MISSING:{suffix}")
    return scoped


def _trigger_summary(*, snapshot: Any) -> tuple[str, ...]:
    reasons: list[str] = []
    for state in snapshot.states:
        if state.required and state.state in {"MISSING", "STALE", "ERROR"}:
            reasons.append(f"required:{state.name}:{state.state}")
    if not reasons:
        reasons.append("required:all_ok")
    return tuple(sorted(set(reasons)))


def _resolve_platform_run_id() -> str | None:
    explicit = (os.getenv("ACTIVE_PLATFORM_RUN_ID") or os.getenv("PLATFORM_RUN_ID") or "").strip()
    if explicit:
        return explicit
    return resolve_platform_run_id(create_if_missing=False)


def _resolve_env_token(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    token = value.strip()
    match = _ENV_PATTERN.fullmatch(token)
    if not match:
        return value
    key = match.group(1)
    default = match.group(2) or ""
    return os.getenv(key, default)


def _none_if_blank(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="DL runtime worker")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    config = load_worker_config(Path(args.profile))
    worker = DegradeLadderWorker(config=config)

    if args.once:
        payload = worker.run_once()
        logger.info("DL worker tick: %s", json.dumps(payload, sort_keys=True, ensure_ascii=True))
        return
    worker.run_forever()


if __name__ == "__main__":
    main()
