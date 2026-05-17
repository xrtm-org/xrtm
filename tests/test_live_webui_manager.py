from __future__ import annotations

import importlib.util
import json
import socket
import sys
import textwrap
from pathlib import Path
from urllib.request import urlopen

import pytest


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "live_webui_manager.py"
    spec = importlib.util.spec_from_file_location("live_webui_manager", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manager_paths(tmp_path: Path, module, *, instance_name: str = "shared"):
    workspace_root = tmp_path / "workspace"
    repo_root = workspace_root / "xrtm"
    (repo_root / "webui").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "xrtm" / "product" / "webui_static").mkdir(parents=True, exist_ok=True)
    (repo_root / "webui" / "package.json").write_text('{"name":"xrtm-webui"}', encoding="utf-8")
    (repo_root / "webui" / "package-lock.json").write_text('{"name":"xrtm-webui","lockfileVersion":3}', encoding="utf-8")
    state_dir = (
        workspace_root / ".xrtm" / "live-webui"
        if instance_name == "shared"
        else workspace_root / ".xrtm" / "live-webui-instances" / instance_name
    )
    return module.ManagerPaths(
        instance_name=instance_name,
        workspace_root=workspace_root,
        repo_root=repo_root,
        state_dir=state_dir,
        state_file=state_dir / "state.json",
        pid_file=state_dir / "server.pid",
        log_file=state_dir / "server.log",
        webui_dir=repo_root / "webui",
        node_modules_dir=repo_root / "webui" / "node_modules",
        package_lock_file=repo_root / "webui" / "package-lock.json",
        package_json_file=repo_root / "webui" / "package.json",
    )


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_ensure_frontend_assets_installs_once_per_lock_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    paths = _manager_paths(tmp_path, module)
    manager = module.LiveWebUIManager(paths)
    calls: list[tuple[list[str], Path]] = []

    def fake_run(command, *, cwd, check):
        calls.append((list(command), Path(cwd)))
        if command[:2] == ["npm", "ci"]:
            paths.node_modules_dir.mkdir(parents=True, exist_ok=True)
        return None

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    state = manager.ensure_frontend_assets({})
    assert calls == [
        (["npm", "ci", "--no-audit", "--no-fund"], paths.webui_dir),
        (["npm", "run", "build"], paths.webui_dir),
    ]
    assert state["frontend_dependencies_hash"]

    calls.clear()
    manager.ensure_frontend_assets(state)
    assert calls == [(["npm", "run", "build"], paths.webui_dir)]


def test_manager_start_restart_stop_updates_pid_state_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    paths = _manager_paths(tmp_path, module)
    manager = module.LiveWebUIManager(paths)
    port = _find_free_port()
    server_script = tmp_path / "fake_web_server.py"
    server_script.write_text(
        textwrap.dedent(
            """\
            import json
            import sys
            from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

            host = sys.argv[1]
            port = int(sys.argv[2])

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == "/api/health":
                        payload = json.dumps({"ok": True}).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(payload)))
                        self.end_headers()
                        self.wfile.write(payload)
                        return
                    payload = b"ok"
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

                def log_message(self, *_args):
                    return

            server = ThreadingHTTPServer((host, port), Handler)
            print(f"serving {host}:{port}", flush=True)
            server.serve_forever()
            """
        ),
        encoding="utf-8",
    )

    def fake_ensure_frontend_assets(state: dict[str, object]) -> dict[str, object]:
        state = dict(state)
        state["frontend_dependencies_hash"] = "test-hash"
        state["frontend_built_at"] = "now"
        return state

    monkeypatch.setattr(manager, "ensure_frontend_assets", fake_ensure_frontend_assets)
    monkeypatch.setattr(
        manager,
        "build_launch_command",
        lambda config: [sys.executable, str(server_script), config.host, str(config.port)],
    )

    config = module.LiveWebUIConfig(
        host="127.0.0.1",
        port=port,
        runs_dir=paths.workspace_root / "runs",
        workflows_dir=paths.workspace_root / ".xrtm" / "workflows",
        startup_timeout=10.0,
    )

    started = manager.start(config)
    assert started["status"] == "running"
    assert paths.pid_file.exists()
    with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    assert payload["ok"] is True

    old_pid = int(started["pid"])
    restarted = manager.restart(config)
    assert restarted["status"] == "running"
    assert int(restarted["pid"]) != old_pid

    snapshot = manager.status_snapshot()
    assert snapshot["status"] == "running"
    assert snapshot["pid"] == restarted["pid"]
    assert snapshot["url"] == f"http://127.0.0.1:{port}"

    stopped = manager.stop()
    assert stopped["status"] == "stopped"
    assert not paths.pid_file.exists()
    assert manager.status_snapshot()["status"] == "stopped"


def test_stop_skips_pid_reuse_when_start_time_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    paths = _manager_paths(tmp_path, module)
    manager = module.LiveWebUIManager(paths)
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    manager.save_state(
        {
            "host": "127.0.0.1",
            "port": 8765,
            "url": "http://127.0.0.1:8765",
            "pid": 4242,
            "pid_start_time": 111,
            "log_file": str(paths.log_file),
        }
    )
    paths.pid_file.write_text("4242\n", encoding="utf-8")
    kill_calls: list[tuple[int, int]] = []

    monkeypatch.setattr(manager, "pid_start_time", lambda _pid: 222)
    monkeypatch.setattr(module.os, "kill", lambda pid, sig: kill_calls.append((pid, sig)))

    stopped = manager.stop()
    assert stopped["status"] == "stopped"
    assert kill_calls == []
    assert not paths.pid_file.exists()
    saved = manager.load_state()
    assert "pid" not in saved


def test_shared_and_isolated_instances_use_separate_defaults(tmp_path: Path) -> None:
    module = _load_module()
    shared_paths = _manager_paths(tmp_path, module)
    isolated_paths = _manager_paths(tmp_path, module, instance_name="gate2-smoke")
    shared_manager = module.LiveWebUIManager(shared_paths)
    isolated_manager = module.LiveWebUIManager(isolated_paths)

    shared_config = shared_manager.resolve_config(
        argparse_namespace(host=None, port=None, runs_dir=None, workflows_dir=None, timeout=10.0)
    )
    isolated_config = isolated_manager.resolve_config(
        argparse_namespace(host=None, port=None, runs_dir=None, workflows_dir=None, timeout=10.0)
    )

    assert shared_paths.state_dir.name == "live-webui"
    assert isolated_paths.state_dir == tmp_path / "workspace" / ".xrtm" / "live-webui-instances" / "gate2-smoke"
    assert shared_config.host == "0.0.0.0"
    assert shared_config.port == 8765
    assert isolated_config.host == "127.0.0.1"
    assert isolated_config.port == 8876


def test_shared_instance_requires_explicit_ack_for_mutations(tmp_path: Path) -> None:
    module = _load_module()
    manager = module.LiveWebUIManager(_manager_paths(tmp_path, module))

    with pytest.raises(module.LiveWebUIError, match="--shared-live"):
        manager.require_shared_mutation_ack(shared_live=False, command="restart")

    manager.require_shared_mutation_ack(shared_live=True, command="restart")


def test_isolated_instances_cannot_claim_shared_port(tmp_path: Path) -> None:
    module = _load_module()
    manager = module.LiveWebUIManager(_manager_paths(tmp_path, module, instance_name="validation"))
    config = module.LiveWebUIConfig(
        host="127.0.0.1",
        port=8765,
        runs_dir=manager.paths.workspace_root / "runs",
        workflows_dir=manager.paths.workspace_root / ".xrtm" / "workflows",
    )

    with pytest.raises(module.LiveWebUIError, match="reserved for the shared live-webui instance"):
        manager._ensure_instance_port_allowed(config)


def argparse_namespace(**kwargs):
    class Namespace:
        pass

    namespace = Namespace()
    for key, value in kwargs.items():
        setattr(namespace, key, value)
    return namespace
