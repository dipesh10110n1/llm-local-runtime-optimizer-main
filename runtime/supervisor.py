"""Own and switch the loopback llama.cpp runtime without exposing it to a network."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil

from core.settings import ROOT, settings
from runtime.clients import backend_health

STATE_PATH = ROOT / "runtime" / "active_runtime.json"


class RuntimeSwitchError(RuntimeError):
    pass


def _read_state() -> dict[str, Any] | None:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _stop_managed_server(state: dict[str, Any]) -> None:
    pid = state.get("pid")
    if not isinstance(pid, int) or not psutil.pid_exists(pid):
        return
    process = psutil.Process(pid)
    if "llama-server" not in process.name().lower():
        raise RuntimeSwitchError("The saved runtime process is not llama-server; it will not be stopped.")
    process.terminate()
    try:
        process.wait(timeout=10)
    except psutil.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _adopt_project_server() -> dict[str, Any] | None:
    """Adopt exactly one llama-server that is loading a model from this project."""
    project_models = str(ROOT / "models").lower()
    matches: list[psutil.Process] = []
    for process in psutil.process_iter(["name", "cmdline"]):
        try:
            command = " ".join(process.info.get("cmdline") or []).lower()
            if "llama-server" in (process.info.get("name") or "").lower() and project_models in command:
                matches.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {"pid": matches[0].pid, "adopted": True} if len(matches) == 1 else None


def ensure_runtime(model: dict[str, Any], configuration: dict[str, Any]) -> dict[str, Any]:
    """Ensure the selected GGUF/config is active. Only a server recorded by Orbit is stopped."""
    desired = {
        "model_id": model["model_id"],
        "model_file": model["path"],
        "threads": int(configuration["threads"]),
        "context_size": int(configuration["context_size"]),
        "gpu_layers": int(configuration.get("gpu_layers", 0)),
    }
    state = _read_state()
    if backend_health("llama.cpp") and state and all(state.get(key) == value for key, value in desired.items()):
        return {**desired, "switched": False}
    if backend_health("llama.cpp") and not state:
        state = _adopt_project_server()
        if not state:
            raise RuntimeSwitchError("A llama.cpp server is already running but is not Orbit's local project server. Stop it, then run Start-Agent.ps1 once.")
    if state and backend_health("llama.cpp"):
        _stop_managed_server(state)
        deadline = time.monotonic() + 10
        while backend_health("llama.cpp") and time.monotonic() < deadline:
            time.sleep(0.2)
    executable = shutil.which("llama-server")
    model_path = ROOT / model["path"]
    if not executable:
        raise RuntimeSwitchError("llama-server was not found on PATH.")
    if not model_path.exists():
        raise RuntimeSwitchError(f"Selected model is missing: {model_path.name}")
    command = [
        executable, "-m", str(model_path), "--host", "127.0.0.1", "--port", "9931",
        "-t", str(desired["threads"]), "-c", str(desired["context_size"]),
        "-ngl", str(desired["gpu_layers"]),
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _write_state({**desired, "pid": process.pid})
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if backend_health("llama.cpp"):
            return {**desired, "switched": True}
        if process.poll() is not None:
            raise RuntimeSwitchError("llama-server stopped while loading the selected model.")
        time.sleep(0.5)
    _stop_managed_server({"pid": process.pid})
    raise RuntimeSwitchError("The selected model did not become ready within 90 seconds.")
