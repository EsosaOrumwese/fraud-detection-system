"""Plane-agnostic Run/Operate process orchestrator."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
import yaml

from fraud_detection.platform_runtime import RUNS_ROOT

_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")
_DEFAULT_ACTIVE_RUN_ID_PATH = "runs/fraud-platform/ACTIVE_RUN_ID"


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        raise RuntimeError(f"ENV_FILE_MISSING:{path}")
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def _build_environment(env_files: list[str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for env_file in env_files:
        merged.update(_load_env_file(Path(env_file)))
    # Runtime shell environment wins over env-file defaults.
    merged.update({key: value for key, value in os.environ.items() if value is not None})
    return merged


def _expand_vars(value: str, env: dict[str, str]) -> str:
    def replacer(match: re.Match[str]) -> str:
        token = match.group(1)
        if ":-" in token:
            key, default = token.split(":-", 1)
            actual = env.get(key)
            if actual in (None, ""):
                return default
            return str(actual)
        actual = env.get(token)
        if actual is None:
            raise RuntimeError(f"ENV_VAR_MISSING:{token}")
        return str(actual)

    return _VAR_PATTERN.sub(replacer, value)


def _expand_mapping(values: dict[str, Any], env: dict[str, str]) -> dict[str, str]:
    expanded: dict[str, str] = {}
    for key, value in values.items():
        if isinstance(value, str):
            expanded[key] = _expand_vars(value, env)
        else:
            expanded[key] = str(value)
    return expanded


def _normalize_command(raw: Any) -> list[str]:
    if isinstance(raw, list) and all(isinstance(part, str) for part in raw):
        if not raw:
            raise RuntimeError("PROCESS_COMMAND_EMPTY")
        return [str(part) for part in raw]
    if isinstance(raw, str):
        tokens = shlex.split(raw, posix=(os.name != "nt"))
        if not tokens:
            raise RuntimeError("PROCESS_COMMAND_EMPTY")
        return tokens
    raise RuntimeError("PROCESS_COMMAND_INVALID")


@dataclass(frozen=True)
class ProbeSpec:
    kind: str
    timeout_seconds: float
    host: str | None = None
    port: str | int | None = None
    path: str | None = None
    command: list[str] | None = None
    cwd: str | None = None

    @classmethod
    def from_mapping(cls, payload: dict[str, Any] | None) -> "ProbeSpec":
        if not payload:
            return cls(kind="process_alive", timeout_seconds=2.0)
        kind = str(payload.get("type") or "process_alive").strip().lower()
        timeout_seconds = float(payload.get("timeout_seconds") or 2.0)
        command_raw = payload.get("command")
        command = _normalize_command(command_raw) if command_raw is not None else None
        return cls(
            kind=kind,
            timeout_seconds=timeout_seconds,
            host=payload.get("host"),
            port=payload.get("port"),
            path=payload.get("path"),
            command=command,
            cwd=payload.get("cwd"),
        )


@dataclass(frozen=True)
class ProcessSpec:
    process_id: str
    command: list[str]
    cwd: str | None
    env: dict[str, Any]
    readiness: ProbeSpec

    @classmethod
    def from_mapping(cls, payload: dict[str, Any], default_probe: ProbeSpec) -> "ProcessSpec":
        process_id = str(payload.get("id") or "").strip()
        if not process_id:
            raise RuntimeError("PROCESS_ID_MISSING")
        command = _normalize_command(payload.get("command"))
        cwd = payload.get("cwd")
        env = payload.get("env") if isinstance(payload.get("env"), dict) else {}
        readiness = ProbeSpec.from_mapping(payload.get("readiness")) if payload.get("readiness") else default_probe
        return cls(
            process_id=process_id,
            command=command,
            cwd=str(cwd) if cwd else None,
            env=env,
            readiness=readiness,
        )


@dataclass(frozen=True)
class ActiveRunSpec:
    required: bool
    source_path: str

    @classmethod
    def from_mapping(cls, payload: dict[str, Any] | None) -> "ActiveRunSpec":
        if not payload:
            return cls(required=False, source_path=_DEFAULT_ACTIVE_RUN_ID_PATH)
        return cls(
            required=bool(payload.get("required", False)),
            source_path=str(payload.get("source_path") or _DEFAULT_ACTIVE_RUN_ID_PATH),
        )


@dataclass(frozen=True)
class PackSpec:
    pack_id: str
    description: str
    default_cwd: str | None
    default_env: dict[str, Any]
    default_probe: ProbeSpec
    active_run: ActiveRunSpec
    processes: list[ProcessSpec]
    source_path: Path

    @classmethod
    def load(cls, path: Path) -> "PackSpec":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("PACK_INVALID")
        if int(payload.get("version") or 1) != 1:
            raise RuntimeError("PACK_VERSION_UNSUPPORTED")
        pack_id = str(payload.get("pack_id") or "").strip()
        if not pack_id:
            raise RuntimeError("PACK_ID_MISSING")
        defaults = payload.get("defaults") if isinstance(payload.get("defaults"), dict) else {}
        default_probe = ProbeSpec.from_mapping(defaults.get("readiness") if isinstance(defaults.get("readiness"), dict) else None)
        default_env = defaults.get("env") if isinstance(defaults.get("env"), dict) else {}
        process_rows = payload.get("processes")
        if not isinstance(process_rows, list) or not process_rows:
            raise RuntimeError("PACK_PROCESSES_MISSING")
        processes: list[ProcessSpec] = []
        seen: set[str] = set()
        for row in process_rows:
            if not isinstance(row, dict):
                raise RuntimeError("PACK_PROCESS_ROW_INVALID")
            spec = ProcessSpec.from_mapping(row, default_probe=default_probe)
            if spec.process_id in seen:
                raise RuntimeError(f"PACK_PROCESS_DUPLICATE:{spec.process_id}")
            seen.add(spec.process_id)
            processes.append(spec)
        return cls(
            pack_id=pack_id,
            description=str(payload.get("description") or ""),
            default_cwd=str(defaults.get("cwd")) if defaults.get("cwd") else None,
            default_env=default_env,
            default_probe=default_probe,
            active_run=ActiveRunSpec.from_mapping(payload.get("active_run") if isinstance(payload.get("active_run"), dict) else None),
            processes=processes,
            source_path=path,
        )


@dataclass(frozen=True)
class ResolvedProcess:
    spec: ProcessSpec
    env: dict[str, str]
    cwd: Path
    log_path: Path
    readiness: ProbeSpec


class ProcessOrchestrator:
    def __init__(self, pack: PackSpec, env: dict[str, str]) -> None:
        self.pack = pack
        self.env = env
        self.operate_root = RUNS_ROOT / "operate" / pack.pack_id
        self.logs_root = self.operate_root / "logs"
        self.status_root = self.operate_root / "status"
        self.events_path = self.operate_root / "events.jsonl"
        self.state_path = self.operate_root / "state.json"

    def up(self, process_filter: set[str] | None = None) -> dict[str, Any]:
        active_run_id = self._resolve_active_run_id()
        state = self._load_state()
        resolved = self._resolve_processes(active_run_id=active_run_id, process_filter=process_filter)
        started: list[str] = []
        already_running: list[str] = []
        for proc in resolved:
            record = state["processes"].get(proc.spec.process_id, {})
            if _is_alive(record):
                already_running.append(proc.spec.process_id)
                continue
            proc.log_path.parent.mkdir(parents=True, exist_ok=True)
            with proc.log_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "ts_utc": _utc_now(),
                            "event": "process_spawn",
                            "process_id": proc.spec.process_id,
                            "pack_id": self.pack.pack_id,
                        },
                        sort_keys=True,
                        ensure_ascii=True,
                    )
                    + "\n"
                )
            handle = proc.log_path.open("a", encoding="utf-8")
            popen_kwargs: dict[str, Any] = {
                "stdout": handle,
                "stderr": subprocess.STDOUT,
                "cwd": str(proc.cwd),
                "env": proc.env,
                "shell": False,
            }
            if os.name == "nt":
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs["start_new_session"] = True
            process = subprocess.Popen(proc.spec.command, **popen_kwargs)  # noqa: S603
            # The child keeps inherited handles; close parent handle immediately.
            handle.close()
            time.sleep(0.15)
            if process.poll() is not None:
                raise RuntimeError(
                    f"PROCESS_EXITED_IMMEDIATELY:{proc.spec.process_id}:exit_code={process.returncode}"
                )
            ps_proc = psutil.Process(process.pid)
            state["processes"][proc.spec.process_id] = {
                "pid": process.pid,
                "pid_create_time": ps_proc.create_time(),
                "command": proc.spec.command,
                "cwd": str(proc.cwd),
                "log_path": str(proc.log_path),
                "started_at_utc": _utc_now(),
                "env_keys": sorted(proc.env.keys()),
            }
            started.append(proc.spec.process_id)
            self._append_event(
                {
                    "event": "process_started",
                    "process_id": proc.spec.process_id,
                    "pid": process.pid,
                    "active_platform_run_id": active_run_id,
                }
            )
        self._write_state(state)
        return {
            "pack_id": self.pack.pack_id,
            "active_platform_run_id": active_run_id,
            "started": started,
            "already_running": already_running,
        }

    def down(self, process_filter: set[str] | None = None, timeout_seconds: float = 15.0) -> dict[str, Any]:
        state = self._load_state()
        records = state.get("processes", {})
        selected = set(records.keys()) if not process_filter else set(process_filter)
        stopped: list[str] = []
        already_stopped: list[str] = []
        for process_id in sorted(selected):
            record = records.get(process_id)
            if not record or not _is_alive(record):
                already_stopped.append(process_id)
                continue
            pid = int(record["pid"])
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=timeout_seconds)
            except psutil.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=max(1.0, timeout_seconds))
            record["stopped_at_utc"] = _utc_now()
            stopped.append(process_id)
            self._append_event(
                {
                    "event": "process_stopped",
                    "process_id": process_id,
                    "pid": pid,
                }
            )
        self._write_state(state)
        return {
            "pack_id": self.pack.pack_id,
            "stopped": stopped,
            "already_stopped": already_stopped,
        }

    def restart(self, process_filter: set[str] | None = None, timeout_seconds: float = 15.0) -> dict[str, Any]:
        down_result = self.down(process_filter=process_filter, timeout_seconds=timeout_seconds)
        up_result = self.up(process_filter=process_filter)
        return {"pack_id": self.pack.pack_id, "down": down_result, "up": up_result}

    def status(self, process_filter: set[str] | None = None) -> dict[str, Any]:
        active_run_id = self._resolve_active_run_id(allow_missing=True)
        state = self._load_state()
        resolved = self._resolve_processes(active_run_id=active_run_id, process_filter=process_filter, allow_missing_run=True)
        rows: list[dict[str, Any]] = []
        for proc in resolved:
            record = state.get("processes", {}).get(proc.spec.process_id, {})
            running = _is_alive(record)
            readiness = self._evaluate_readiness(proc=proc, running=running)
            rows.append(
                {
                    "process_id": proc.spec.process_id,
                    "running": running,
                    "pid": record.get("pid"),
                    "pid_create_time": record.get("pid_create_time"),
                    "log_path": str(proc.log_path),
                    "readiness": readiness,
                }
            )
        payload = {
            "pack_id": self.pack.pack_id,
            "pack_path": str(self.pack.source_path),
            "ts_utc": _utc_now(),
            "active_platform_run_id": active_run_id,
            "processes": rows,
        }
        self.status_root.mkdir(parents=True, exist_ok=True)
        (self.status_root / "last_status.json").write_text(
            json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        self._append_event({"event": "status_written", "process_count": len(rows)})
        return payload

    def _evaluate_readiness(self, *, proc: ResolvedProcess, running: bool) -> dict[str, Any]:
        if not running:
            return {"ready": False, "reason": "not_running", "probe": proc.readiness.kind}
        probe = proc.readiness
        if probe.kind == "process_alive":
            return {"ready": True, "reason": "alive", "probe": probe.kind}
        if probe.kind == "tcp":
            if not probe.host or not probe.port:
                return {"ready": False, "reason": "probe_invalid", "probe": probe.kind}
            try:
                with socket.create_connection((probe.host, int(probe.port)), timeout=probe.timeout_seconds):
                    return {"ready": True, "reason": "tcp_open", "probe": probe.kind}
            except OSError as exc:
                return {"ready": False, "reason": f"tcp_closed:{exc}", "probe": probe.kind}
        if probe.kind == "file_exists":
            if not probe.path:
                return {"ready": False, "reason": "probe_invalid", "probe": probe.kind}
            path = Path(_expand_vars(str(probe.path), proc.env))
            return {
                "ready": path.exists(),
                "reason": "file_exists" if path.exists() else "file_missing",
                "probe": probe.kind,
                "path": str(path),
            }
        if probe.kind == "command":
            if not probe.command:
                return {"ready": False, "reason": "probe_invalid", "probe": probe.kind}
            cwd = Path(_expand_vars(probe.cwd, proc.env)) if probe.cwd else proc.cwd
            try:
                completed = subprocess.run(  # noqa: S603
                    probe.command,
                    cwd=str(cwd),
                    env=proc.env,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=probe.timeout_seconds,
                    check=False,
                )
            except Exception as exc:  # pragma: no cover - defensive
                return {"ready": False, "reason": f"command_error:{exc}", "probe": probe.kind}
            if completed.returncode == 0:
                return {"ready": True, "reason": "command_ok", "probe": probe.kind}
            return {
                "ready": False,
                "reason": f"command_exit:{completed.returncode}",
                "probe": probe.kind,
                "stderr": (completed.stderr or "").strip()[:300],
            }
        return {"ready": False, "reason": "probe_unknown", "probe": probe.kind}

    def _resolve_active_run_id(self, *, allow_missing: bool = False) -> str | None:
        env_run = (self.env.get("PLATFORM_RUN_ID") or "").strip()
        if env_run:
            return env_run
        source_token = _expand_vars(self.pack.active_run.source_path, self.env)
        source_path = Path(source_token)
        if source_path.exists():
            value = source_path.read_text(encoding="utf-8").strip()
            if value:
                return value
        if self.pack.active_run.required and not allow_missing:
            raise RuntimeError("ACTIVE_PLATFORM_RUN_ID_MISSING")
        return None

    def _resolve_processes(
        self,
        *,
        active_run_id: str | None,
        process_filter: set[str] | None = None,
        allow_missing_run: bool = False,
    ) -> list[ResolvedProcess]:
        selected = process_filter or {proc.process_id for proc in self.pack.processes}
        known = {proc.process_id for proc in self.pack.processes}
        unknown = sorted(selected - known)
        if unknown:
            raise RuntimeError(f"PACK_PROCESS_UNKNOWN:{','.join(unknown)}")
        env_seed = dict(self.env)
        if active_run_id:
            env_seed["ACTIVE_PLATFORM_RUN_ID"] = active_run_id
        elif self.pack.active_run.required and not allow_missing_run:
            raise RuntimeError("ACTIVE_PLATFORM_RUN_ID_MISSING")
        defaults = _expand_mapping(self.pack.default_env, env_seed)
        resolved: list[ResolvedProcess] = []
        for spec in self.pack.processes:
            if spec.process_id not in selected:
                continue
            env = dict(env_seed)
            env.update(defaults)
            env.update(_expand_mapping(spec.env, env))
            cwd_token = spec.cwd or self.pack.default_cwd or "."
            cwd = Path(_expand_vars(cwd_token, env))
            log_path = self.logs_root / f"{spec.process_id}.log"
            readiness = _resolve_probe(spec.readiness, env)
            resolved.append(
                ResolvedProcess(
                    spec=spec,
                    env=env,
                    cwd=cwd,
                    log_path=log_path,
                    readiness=readiness,
                )
            )
        return resolved

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {
                "pack_id": self.pack.pack_id,
                "pack_path": str(self.pack.source_path),
                "updated_at_utc": _utc_now(),
                "processes": {},
            }
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("ORCHESTRATOR_STATE_INVALID")
        payload.setdefault("processes", {})
        if not isinstance(payload["processes"], dict):
            raise RuntimeError("ORCHESTRATOR_STATE_INVALID_PROCESSES")
        return payload

    def _write_state(self, payload: dict[str, Any]) -> None:
        self.operate_root.mkdir(parents=True, exist_ok=True)
        payload["updated_at_utc"] = _utc_now()
        self.state_path.write_text(
            json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def _append_event(self, payload: dict[str, Any]) -> None:
        self.operate_root.mkdir(parents=True, exist_ok=True)
        record = {
            "ts_utc": _utc_now(),
            "pack_id": self.pack.pack_id,
            **payload,
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")


def _is_alive(record: dict[str, Any]) -> bool:
    pid = record.get("pid")
    created = record.get("pid_create_time")
    if not isinstance(pid, int):
        return False
    try:
        proc = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return False
    if not proc.is_running():
        return False
    if isinstance(created, (int, float)):
        try:
            current = proc.create_time()
            if abs(float(current) - float(created)) > 1e-3:
                return False
        except (psutil.Error, OSError):
            return False
    return True


def _resolve_probe(probe: ProbeSpec, env: dict[str, str]) -> ProbeSpec:
    host = _expand_vars(probe.host, env) if probe.host else None
    path = _expand_vars(probe.path, env) if probe.path else None
    cwd = _expand_vars(probe.cwd, env) if probe.cwd else None
    command = None
    if probe.command:
        command = [_expand_vars(token, env) for token in probe.command]
    port: int | None = None
    if probe.port is not None:
        port_value = _expand_vars(str(probe.port), env)
        port = int(port_value)
    return ProbeSpec(
        kind=probe.kind,
        timeout_seconds=probe.timeout_seconds,
        host=host,
        port=port,
        path=path,
        command=command,
        cwd=cwd,
    )


def _print_status(payload: dict[str, Any]) -> None:
    print(f"pack={payload['pack_id']} active_platform_run_id={payload.get('active_platform_run_id') or '-'}")
    for row in payload.get("processes", []):
        readiness = row.get("readiness", {})
        ready = "ready" if readiness.get("ready") else "not_ready"
        running = "running" if row.get("running") else "stopped"
        reason = readiness.get("reason") or "-"
        process_id = row.get("process_id")
        pid = row.get("pid")
        print(f"{process_id}: {running} {ready} pid={pid} reason={reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run/Operate orchestrator (plane-agnostic)")
    parser.add_argument("--pack", required=True, help="Path to orchestration pack YAML")
    parser.add_argument(
        "--env-file",
        action="append",
        default=[],
        help="Optional .env file(s); shell env vars override file defaults",
    )
    parser.add_argument("--process", action="append", default=[], help="Limit action to one or more process ids")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("up", help="Start selected processes")
    down = sub.add_parser("down", help="Stop selected processes")
    down.add_argument("--timeout-seconds", type=float, default=15.0)
    restart = sub.add_parser("restart", help="Restart selected processes")
    restart.add_argument("--timeout-seconds", type=float, default=15.0)
    status = sub.add_parser("status", help="Show process status")
    status.add_argument("--json", action="store_true", help="Emit JSON status payload")

    args = parser.parse_args()
    env = _build_environment(args.env_file)
    pack = PackSpec.load(Path(args.pack))
    orchestrator = ProcessOrchestrator(pack=pack, env=env)
    process_filter = set(args.process) if args.process else None

    if args.command == "up":
        payload = orchestrator.up(process_filter=process_filter)
        print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
        return
    if args.command == "down":
        payload = orchestrator.down(process_filter=process_filter, timeout_seconds=float(args.timeout_seconds))
        print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
        return
    if args.command == "restart":
        payload = orchestrator.restart(process_filter=process_filter, timeout_seconds=float(args.timeout_seconds))
        print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
        return
    if args.command == "status":
        payload = orchestrator.status(process_filter=process_filter)
        if args.json:
            print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
        else:
            _print_status(payload)
        return
    raise RuntimeError(f"ORCHESTRATOR_COMMAND_UNSUPPORTED:{args.command}")


if __name__ == "__main__":
    main()
