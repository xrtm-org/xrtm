#!/usr/bin/env python3
"""Manage the local current-checkout XRTM WebUI process."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_RUNS_DIR = Path("runs")
DEFAULT_WORKFLOWS_DIR = Path(".xrtm/workflows")
DEFAULT_STARTUP_TIMEOUT_SECONDS = 30.0
DEFAULT_STOP_TIMEOUT_SECONDS = 10.0
DEFAULT_LOG_LINES = 50


class LiveWebUIError(RuntimeError):
    """Operational error for the live WebUI manager."""


@dataclass(frozen=True)
class ManagerPaths:
    workspace_root: Path
    repo_root: Path
    state_dir: Path
    state_file: Path
    pid_file: Path
    log_file: Path
    webui_dir: Path
    node_modules_dir: Path
    package_lock_file: Path
    package_json_file: Path


@dataclass(frozen=True)
class LiveWebUIConfig:
    host: str
    port: int
    runs_dir: Path
    workflows_dir: Path
    startup_timeout: float = DEFAULT_STARTUP_TIMEOUT_SECONDS

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


def derive_paths(*, workspace_root: Path | None = None, repo_root: Path | None = None) -> ManagerPaths:
    script_path = Path(__file__).resolve()
    repo = Path(os.environ.get("XRTM_LIVE_WEBUI_REPO_ROOT", repo_root or script_path.parents[1])).resolve()
    workspace = Path(os.environ.get("XRTM_LIVE_WEBUI_WORKSPACE_ROOT", workspace_root or repo.parent)).resolve()
    state_dir = workspace / ".xrtm" / "live-webui"
    webui_dir = repo / "webui"
    return ManagerPaths(
        workspace_root=workspace,
        repo_root=repo,
        state_dir=state_dir,
        state_file=state_dir / "state.json",
        pid_file=state_dir / "server.pid",
        log_file=state_dir / "server.log",
        webui_dir=webui_dir,
        node_modules_dir=webui_dir / "node_modules",
        package_lock_file=webui_dir / "package-lock.json",
        package_json_file=webui_dir / "package.json",
    )


class LiveWebUIManager:
    def __init__(self, paths: ManagerPaths) -> None:
        self.paths = paths

    def load_state(self) -> dict[str, Any]:
        if not self.paths.state_file.exists():
            return {}
        return json.loads(self.paths.state_file.read_text(encoding="utf-8"))

    def save_state(self, state: dict[str, Any]) -> None:
        self.paths.state_dir.mkdir(parents=True, exist_ok=True)
        self.paths.state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def resolve_config(self, args: argparse.Namespace) -> LiveWebUIConfig:
        state = self.load_state()
        host = args.host or state.get("host") or DEFAULT_HOST
        port = args.port or state.get("port") or DEFAULT_PORT
        runs_dir = self._resolve_workspace_path(Path(args.runs_dir) if args.runs_dir else state.get("runs_dir") or DEFAULT_RUNS_DIR)
        workflows_dir = self._resolve_workspace_path(
            Path(args.workflows_dir) if args.workflows_dir else state.get("workflows_dir") or DEFAULT_WORKFLOWS_DIR
        )
        return LiveWebUIConfig(
            host=host,
            port=int(port),
            runs_dir=runs_dir,
            workflows_dir=workflows_dir,
            startup_timeout=float(args.timeout or DEFAULT_STARTUP_TIMEOUT_SECONDS),
        )

    def ensure_frontend_assets(self, state: dict[str, Any]) -> dict[str, Any]:
        self._require_command("npm")
        lock_hash = self._dependency_hash()
        previous_hash = state.get("frontend_dependencies_hash")
        needs_install = not self.paths.node_modules_dir.exists() or previous_hash != lock_hash

        if needs_install:
            install_command = (
                ["npm", "ci", "--no-audit", "--no-fund"]
                if self.paths.package_lock_file.exists()
                else ["npm", "install", "--no-audit", "--no-fund"]
            )
            subprocess.run(install_command, cwd=self.paths.webui_dir, check=True)
            state["frontend_dependencies_hash"] = lock_hash

        subprocess.run(["npm", "run", "build"], cwd=self.paths.webui_dir, check=True)
        state["frontend_built_at"] = _utc_now()
        return state

    def build_launch_command(self, config: LiveWebUIConfig) -> list[str]:
        self._require_command("uv")
        return [
            "uv",
            "run",
            "--project",
            str(self.paths.repo_root),
            "xrtm",
            "web",
            "--host",
            config.host,
            "--port",
            str(config.port),
            "--runs-dir",
            str(config.runs_dir),
            "--workflows-dir",
            str(config.workflows_dir),
        ]

    def start(self, config: LiveWebUIConfig) -> dict[str, Any]:
        state = self.load_state()
        active = self._active_process(state)
        if active is not None:
            raise LiveWebUIError(
                f"Managed live WebUI is already running at {config.url} (pid {active}). Use restart to replace it."
            )
        if self.port_open(config.host, config.port):
            raise LiveWebUIError(
                f"{config.url} is already serving traffic, but not with the manager-owned PID. "
                "Stop that process manually before starting live-webui."
            )

        self.paths.state_dir.mkdir(parents=True, exist_ok=True)
        state = self.ensure_frontend_assets(state)
        command = self.build_launch_command(config)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.paths.repo_root / "src")
        with self.paths.log_file.open("a", encoding="utf-8") as handle:
            handle.write(f"\n=== live-webui start { _utc_now() } ===\n")
            handle.write(f"command: {' '.join(command)}\n")
            handle.flush()
            process = subprocess.Popen(
                command,
                cwd=self.paths.workspace_root,
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                text=True,
            )

        pid_start_time = self.pid_start_time(process.pid)
        if pid_start_time is None:
            raise LiveWebUIError(f"live-webui exited too quickly.\n\n{self.tail_logs()}")

        state.update(self._runtime_state(config))
        state.update(
            {
                "command": command,
                "log_file": str(self.paths.log_file),
                "pid": process.pid,
                "pid_start_time": pid_start_time,
                "started_at": _utc_now(),
                "status": "starting",
            }
        )
        self.save_state(state)
        self.paths.pid_file.write_text(f"{process.pid}\n", encoding="utf-8")

        try:
            self.wait_for_ready(config.url, process=process, timeout=config.startup_timeout)
        except Exception:
            self._terminate_managed_pid(state, quiet=True)
            failed_state = self.load_state()
            failed_state.update(self._runtime_state(config))
            failed_state.update({"status": "failed", "failed_at": _utc_now()})
            self.save_state(failed_state)
            raise

        state["status"] = "running"
        self.save_state(state)
        return state

    def stop(self, *, quiet: bool = False) -> dict[str, Any]:
        state = self.load_state()
        active = self._active_process(state)
        if active is not None:
            self._terminate_managed_pid(state, quiet=quiet)
            state = self.load_state()
            state["status"] = "stopped"
            state["stopped_at"] = _utc_now()
            self.save_state(state)
            return state

        cleaned = self._clear_runtime_state(state)
        cleaned["status"] = "stopped"
        cleaned["stopped_at"] = _utc_now()
        self.save_state(cleaned)
        return cleaned

    def restart(self, config: LiveWebUIConfig) -> dict[str, Any]:
        self.stop(quiet=True)
        return self.start(config)

    def status_snapshot(self) -> dict[str, Any]:
        state = self.load_state()
        config = LiveWebUIConfig(
            host=str(state.get("host") or DEFAULT_HOST),
            port=int(state.get("port") or DEFAULT_PORT),
            runs_dir=self._resolve_workspace_path(state.get("runs_dir") or DEFAULT_RUNS_DIR),
            workflows_dir=self._resolve_workspace_path(state.get("workflows_dir") or DEFAULT_WORKFLOWS_DIR),
        )
        active = self._active_process(state)
        port_open = self.port_open(config.host, config.port)
        status = "running" if active is not None else "stopped"
        if active is None and port_open:
            status = "unmanaged-port-active"
        return {
            "status": status,
            "url": config.url,
            "host": config.host,
            "port": config.port,
            "pid": active,
            "pid_file": str(self.paths.pid_file),
            "log_file": str(self.paths.log_file),
            "state_file": str(self.paths.state_file),
            "runs_dir": str(config.runs_dir),
            "workflows_dir": str(config.workflows_dir),
        }

    def status_text(self) -> str:
        snapshot = self.status_snapshot()
        lines = [
            f"Status: {snapshot['status']}",
            f"URL:    {snapshot['url']}",
            f"PID:    {snapshot['pid'] if snapshot['pid'] is not None else '<not running>'}",
            f"Log:    {snapshot['log_file']}",
            f"State:  {snapshot['state_file']}",
            f"Runs:   {snapshot['runs_dir']}",
            f"Flows:  {snapshot['workflows_dir']}",
        ]
        if snapshot["status"] == "unmanaged-port-active":
            lines.append("Note: the URL is active, but not with the manager-owned PID.")
        return "\n".join(lines)

    def logs_text(self, *, lines: int = DEFAULT_LOG_LINES) -> str:
        return self.tail_logs(lines=lines)

    def port_open(self, host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            return sock.connect_ex((host, port)) == 0

    def pid_start_time(self, pid: int) -> int | None:
        stat_path = Path("/proc") / str(pid) / "stat"
        if not stat_path.exists():
            return None
        raw = stat_path.read_text(encoding="utf-8")
        suffix = raw.rsplit(") ", maxsplit=1)[-1].split()
        if len(suffix) <= 19:
            return None
        return int(suffix[19])

    def wait_for_ready(self, url: str, *, process: subprocess.Popen[str], timeout: float) -> None:
        deadline = time.monotonic() + timeout
        health_url = f"{url}/api/health"
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise LiveWebUIError(
                    f"live-webui exited during startup with code {process.returncode}.\n\n{self.tail_logs()}"
                )
            try:
                with urlopen(health_url, timeout=1.0) as response:
                    if response.status == 200:
                        return
            except URLError:
                time.sleep(0.5)
                continue
            time.sleep(0.5)
        raise LiveWebUIError(f"Timed out waiting for {health_url}.\n\n{self.tail_logs()}")

    def tail_logs(self, *, lines: int = DEFAULT_LOG_LINES) -> str:
        if not self.paths.log_file.exists():
            return "<no live-webui log yet>"
        with self.paths.log_file.open("r", encoding="utf-8") as handle:
            return "".join(deque(handle, maxlen=lines)).rstrip() or "<empty live-webui log>"

    def _active_process(self, state: dict[str, Any]) -> int | None:
        pid = state.get("pid")
        expected_start_time = state.get("pid_start_time")
        if not isinstance(pid, int) or not isinstance(expected_start_time, int):
            return None
        current_start_time = self.pid_start_time(pid)
        if current_start_time is None or current_start_time != expected_start_time:
            return None
        try:
            os.kill(pid, 0)
        except OSError:
            return None
        return pid

    def _terminate_managed_pid(self, state: dict[str, Any], *, quiet: bool) -> None:
        pid = self._active_process(state)
        if pid is None:
            self._clear_runtime_state(state)
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            self._clear_runtime_state(state)
            return

        deadline = time.monotonic() + DEFAULT_STOP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self._active_process(state) is None:
                self._clear_runtime_state(state)
                return
            time.sleep(0.25)

        if not quiet:
            print(f"live-webui pid {pid} did not stop after SIGTERM; sending SIGKILL.", file=sys.stderr)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if self._active_process(state) is None:
                break
            time.sleep(0.1)
        self._clear_runtime_state(state)

    def _clear_runtime_state(self, state: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(state)
        cleaned.pop("pid", None)
        cleaned.pop("pid_start_time", None)
        cleaned.pop("command", None)
        cleaned.setdefault("log_file", str(self.paths.log_file))
        self.paths.pid_file.unlink(missing_ok=True)
        self.save_state(cleaned)
        return cleaned

    def _runtime_state(self, config: LiveWebUIConfig) -> dict[str, Any]:
        return {
            "host": config.host,
            "port": config.port,
            "url": config.url,
            "runs_dir": str(config.runs_dir),
            "workflows_dir": str(config.workflows_dir),
            "workspace_root": str(self.paths.workspace_root),
            "repo_root": str(self.paths.repo_root),
        }

    def _dependency_hash(self) -> str:
        source = self.paths.package_lock_file if self.paths.package_lock_file.exists() else self.paths.package_json_file
        return hashlib.sha256(source.read_bytes()).hexdigest()

    def _require_command(self, command: str) -> None:
        if shutil.which(command) is None:
            raise LiveWebUIError(f"Missing required command: {command}")

    def _resolve_workspace_path(self, value: str | Path) -> Path:
        candidate = value if isinstance(value, Path) else Path(value)
        return candidate if candidate.is_absolute() else (self.paths.workspace_root / candidate).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("start", "restart"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--host", default=None)
        subparser.add_argument("--port", type=int, default=None)
        subparser.add_argument("--runs-dir", default=None)
        subparser.add_argument("--workflows-dir", default=None)
        subparser.add_argument("--timeout", type=float, default=DEFAULT_STARTUP_TIMEOUT_SECONDS)

    subparsers.add_parser("stop")
    subparsers.add_parser("status")

    logs = subparsers.add_parser("logs")
    logs.add_argument("--lines", type=int, default=DEFAULT_LOG_LINES)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manager = LiveWebUIManager(derive_paths())

    if args.command == "start":
        state = manager.start(manager.resolve_config(args))
        print(f"live-webui running at {state['url']} (pid {state['pid']})")
        return 0
    if args.command == "restart":
        state = manager.restart(manager.resolve_config(args))
        print(f"live-webui restarted at {state['url']} (pid {state['pid']})")
        return 0
    if args.command == "stop":
        snapshot = manager.stop()
        print(f"live-webui stopped; managed URL is {snapshot.get('url', f'http://{DEFAULT_HOST}:{DEFAULT_PORT}')}")
        return 0
    if args.command == "status":
        print(manager.status_text())
        return 0
    if args.command == "logs":
        print(manager.logs_text(lines=args.lines))
        return 0
    raise LiveWebUIError(f"Unknown command: {args.command}")


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LiveWebUIError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
