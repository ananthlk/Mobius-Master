#!/usr/bin/env python3
"""
Master landing server for Mobius. Serves the landing page and exposes POST /api/stop-all
to run the robust stop script and GET /api/status for service health. Binds 127.0.0.1:3999 only (dev-only).
Uses stdlib only (no FastAPI dependency at repo root).
"""
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

MOBIUS_ROOT = Path(__file__).resolve().parent
LANDING_DIR = MOBIUS_ROOT / "landing"
STOP_SCRIPT = MOBIUS_ROOT / "scripts" / "stop_all_mobius.sh"
PIDFILE = MOBIUS_ROOT / ".mobius_start_all.pids"
LOGDIR = MOBIUS_ROOT / ".mobius_logs"
PORT = 3999

# Service id -> names (in PID file) and ports to kill. Used for stop/restart.
SERVICE_STOP = {
    "os": {"names": ["mobius-os-backend", "mobius-os-extension"], "ports": [5001]},
    "chat": {"names": ["mobius-chat-api", "mobius-chat-worker"], "ports": [8000]},
    "rag": {
        "names": [
            "mobius-rag-backend",
            "mobius-rag-chunking-worker",
            "mobius-rag-embedding-worker",
            "mobius-rag-frontend",
        ],
        "ports": [8001, 5173],
    },
    "dbt": {"names": ["mobius-dbt"], "ports": [6500]},
    "chat-worker": {"names": ["mobius-chat-worker"], "ports": []},
    "scraper": {"names": ["mobius-scraper-api", "mobius-scraper-worker"], "ports": [8002]},
    "rag-chunking": {"names": ["mobius-rag-chunking-worker"], "ports": []},
    "rag-embedding": {"names": ["mobius-rag-embedding-worker"], "ports": []},
}

# Service id -> list of (name, cmd) to start. {root} = MOBIUS_ROOT.
def _start_commands(root: Path) -> dict:
    r = str(root)
    rag_cmds = [
        ("mobius-rag-backend", f"cd {r}/mobius-rag && .venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"),
        ("mobius-rag-chunking-worker", f"cd {r}/mobius-rag && .venv/bin/python3 -m app.worker"),
        ("mobius-rag-frontend", f"cd {r}/mobius-rag/frontend && VITE_API_BASE=http://localhost:8001 VITE_SCRAPER_API_BASE=http://localhost:8002 npm run dev"),
    ]
    if (root / "mobius-rag" / "app" / "embedding_worker.py").exists():
        rag_cmds.insert(2, ("mobius-rag-embedding-worker", f"cd {r}/mobius-rag && .venv/bin/python3 -m app.embedding_worker"))
    return {
        "os": [
            ("mobius-os-backend", f"cd {r}/mobius-os/backend && .venv/bin/python server.py"),
            ("mobius-os-extension", f"cd {r}/mobius-os/extension && npm run dev"),
        ],
        "chat": [
            ("mobius-chat-api", f"cd {r}/mobius-chat && ./mchatc"),
            ("mobius-chat-worker", f"cd {r}/mobius-chat && ./mchatcw"),
        ],
        "rag": rag_cmds,
        "dbt": [
            ("mobius-dbt", f"cd {r}/mobius-dbt && .venv/bin/python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 6500"),
        ],
        "chat-worker": [
            ("mobius-chat-worker", f"cd {r}/mobius-chat && ./mchatcw"),
        ],
        "scraper": [
            ("mobius-scraper-api", f"cd {r}/mobius-skills/web-scraper && .venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8002"),
            ("mobius-scraper-worker", f"cd {r}/mobius-skills/web-scraper && ./mscrapew"),
        ],
        "rag-chunking": [
            ("mobius-rag-chunking-worker", f"cd {r}/mobius-rag && .venv/bin/python3 -m app.worker"),
        ],
        "rag-embedding": (
            [("mobius-rag-embedding-worker", f"cd {r}/mobius-rag && .venv/bin/python3 -m app.embedding_worker")]
            if (root / "mobius-rag" / "app" / "embedding_worker.py").exists()
            else []
        ),
    }

# Process: (id, name, url_for_link, probe_url, path). Use 127.0.0.1 so we don't depend on localhost.
PROCESS_PROBES = [
    ("os", "OS (extension + backend)", "http://127.0.0.1:5001", "http://127.0.0.1:5001", "/health"),
    ("chat", "Chat", "http://127.0.0.1:8000", "http://127.0.0.1:8000", "/health"),
    ("dbt", "DBT", "http://127.0.0.1:6500", "http://127.0.0.1:6500", "/config"),
]
# RAG is special: backend 8001 + frontend 5173; combined status.
RAG_BACKEND_URL = "http://127.0.0.1:8001"
RAG_BACKEND_PATH = "/health"
RAG_FRONTEND_URL = "http://127.0.0.1:5173"
RAG_FRONTEND_PATH = "/"
RAG_LINK_URL = "http://127.0.0.1:5173"

# Workers: (id, name, url or None, path, note). None url = no_endpoint.
WORKER_PROBES = [
    ("chat-worker", "Chat worker", None, None, None),
    ("scraper", "Scraper", "http://127.0.0.1:8002", "/health", "Required for RAG Scrape from URL."),
    ("rag-chunking", "RAG chunking", None, None, None),
    ("rag-embedding", "RAG embedding", None, None, None),
]

PROBE_TIMEOUT = 3  # seconds
SLOW_THRESHOLD_MS = 2000  # above this ms = slow


def _kill_port(port: int) -> None:
    """Kill any process bound to port."""
    try:
        out = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(MOBIUS_ROOT),
        )
        if out.returncode == 0 and out.stdout.strip():
            for pid in out.stdout.strip().split():
                try:
                    subprocess.run(["kill", "-9", pid], capture_output=True, timeout=2)
                except Exception:
                    pass
            time.sleep(2)
    except Exception:
        pass


def _stop_service(sid: str) -> tuple[bool, str]:
    """Stop a service by id. Returns (ok, message)."""
    if sid not in SERVICE_STOP:
        return (False, f"Unknown service: {sid}")
    info = SERVICE_STOP[sid]
    names_set = set(info["names"])
    # Kill PIDs from PID file
    if PIDFILE.exists():
        lines = []
        with open(PIDFILE) as f:
            for line in f:
                parts = line.strip().split(None, 1)
                if len(parts) >= 2:
                    pid_str, name = parts[0], parts[1]
                    if name in names_set:
                        try:
                            subprocess.run(["kill", "-9", pid_str], capture_output=True, timeout=2)
                        except Exception:
                            pass
                        continue
                lines.append(line)
        with open(PIDFILE, "w") as f:
            f.writelines(lines)
    # Kill by port
    for port in info["ports"]:
        _kill_port(port)
    return (True, f"Stopped {sid}")


def _start_service(sid: str) -> tuple[bool, str]:
    """Start a service by id. Returns (ok, message)."""
    if sid not in SERVICE_STOP:
        return (False, f"Unknown service: {sid}")
    commands = _start_commands(MOBIUS_ROOT).get(sid)
    if not commands:
        return (False, f"No start commands for: {sid} (or component not present)")
    # Free ports first
    for port in SERVICE_STOP[sid]["ports"]:
        _kill_port(port)
    LOGDIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["MOBIUS_ROOT"] = str(MOBIUS_ROOT)
    started = []
    for name, cmd in commands:
        try:
            log_path = LOGDIR / f"{name}.log"
            with open(log_path, "a") as logf:
                p = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=logf,
                    stderr=subprocess.STDOUT,
                    cwd=str(MOBIUS_ROOT),
                    env=env,
                )
            with open(PIDFILE, "a") as f:
                f.write(f"{p.pid} {name}\n")
            started.append(name)
        except Exception as e:
            return (False, f"Failed to start {name}: {e}")
    return (True, f"Started {sid}: " + ", ".join(started))


def _probe_one(base_url: str, path: str) -> tuple[str, int]:
    """Probe one URL. Returns (status, ms). status is up, slow, or down."""
    url = base_url.rstrip("/") + path
    start = time.perf_counter()
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=PROBE_TIMEOUT) as resp:
            code = resp.getcode()
    except (URLError, HTTPError, OSError):
        return ("down", int((time.perf_counter() - start) * 1000))
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    if 200 <= code < 300:
        return ("up" if elapsed_ms < SLOW_THRESHOLD_MS else "slow", elapsed_ms)
    return ("down", elapsed_ms)


def _probe_rag() -> dict:
    """Probe RAG backend (8001) and frontend (5173). Return single process entry: up/degraded/down/slow."""
    backend_status, backend_ms = _probe_one(RAG_BACKEND_URL, RAG_BACKEND_PATH)
    frontend_status, frontend_ms = _probe_one(RAG_FRONTEND_URL, RAG_FRONTEND_PATH)
    backend_up = backend_status in ("up", "slow")
    frontend_up = frontend_status in ("up", "slow")
    max_ms = max(backend_ms, frontend_ms)
    if backend_up and frontend_up:
        if backend_status == "slow" or frontend_status == "slow":
            status = "slow"
        else:
            status = "up"
        return {
            "id": "rag",
            "name": "RAG",
            "url": RAG_LINK_URL,
            "status": status,
            "ms": max_ms,
            "backend_ms": backend_ms,
            "frontend_ms": frontend_ms,
        }
    if backend_up and not frontend_up:
        return {
            "id": "rag",
            "name": "RAG",
            "url": RAG_LINK_URL,
            "status": "degraded",
            "ms": backend_ms,
            "backend_ms": backend_ms,
            "frontend_ms": frontend_ms,
            "degraded_reason": "Backend up, frontend down.",
        }
    if not backend_up and frontend_up:
        return {
            "id": "rag",
            "name": "RAG",
            "url": RAG_LINK_URL,
            "status": "degraded",
            "ms": frontend_ms,
            "backend_ms": backend_ms,
            "frontend_ms": frontend_ms,
            "degraded_reason": "Frontend up, backend down.",
        }
    return {
        "id": "rag",
        "name": "RAG",
        "url": RAG_LINK_URL,
        "status": "down",
        "ms": max_ms,
        "backend_ms": backend_ms,
        "frontend_ms": frontend_ms,
    }


def _get_status() -> dict:
    processes = []
    # OS, Chat, DBT
    for pid, name, link_url, probe_url, path in PROCESS_PROBES:
        status, ms = _probe_one(probe_url, path)
        processes.append({
            "id": pid,
            "name": name,
            "url": link_url,
            "status": status,
            "ms": ms,
        })
    # RAG (combined)
    processes.append(_probe_rag())
    # Reorder so RAG is third: os, chat, rag, dbt
    processes.sort(key=lambda p: {"os": 0, "chat": 1, "rag": 2, "dbt": 3}.get(p["id"], 4))

    workers = []
    for wid, name, base_url, path, note in WORKER_PROBES:
        if base_url is None or path is None:
            workers.append({"id": wid, "name": name, "status": "no_endpoint", "note": note})
        else:
            status, ms = _probe_one(base_url, path)
            workers.append({
                "id": wid,
                "name": name,
                "status": status,
                "url": base_url,
                "ms": ms,
                "note": note,
            })

    return {
        "processes": processes,
        "workers": workers,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


class LandingHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(LANDING_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/status":
            self._handle_status()
            return
        if self.path == "/" or self.path == "/index.html":
            self.path = "/index.html"
        return super().do_GET()

    def _handle_status(self):
        try:
            data = _get_status()
            self._send_json(200, data)
        except Exception as e:
            self._send_json(500, {"processes": [], "workers": [], "updated_at": None, "error": str(e)})

    def do_POST(self):
        if self.path == "/api/stop-all":
            self._handle_stop_all()
        elif self.path == "/api/start-all":
            self._handle_start_all()
        elif self.path == "/api/service/stop":
            self._handle_service_stop()
        elif self.path == "/api/service/restart":
            self._handle_service_restart()
        else:
            self.send_error(404)

    def _handle_stop_all(self):
        if not STOP_SCRIPT.exists():
            self._send_json(404, {"ok": False, "message": "scripts/stop_all_mobius.sh not found", "output": ""})
            return
        env = os.environ.copy()
        env["MOBIUS_ROOT"] = str(MOBIUS_ROOT)
        env["KEEP_LANDING"] = "1"
        try:
            result = subprocess.run(
                ["bash", str(STOP_SCRIPT)],
                cwd=str(MOBIUS_ROOT),
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = (result.stdout or "").strip() + "\n" + (result.stderr or "").strip()
            self._send_json(200, {
                "ok": result.returncode == 0,
                "message": "Stopped." if result.returncode == 0 else "Stop script exited with code " + str(result.returncode),
                "output": output.strip(),
            })
        except subprocess.TimeoutExpired:
            self._send_json(200, {"ok": False, "message": "Stop script timed out.", "output": ""})
        except Exception as e:
            self._send_json(200, {"ok": False, "message": str(e), "output": ""})

    def _handle_start_all(self):
        mstart = MOBIUS_ROOT / "mstart"
        if not mstart.exists():
            self._send_json(404, {"ok": False, "message": "mstart not found", "output": ""})
            return
        env = os.environ.copy()
        env["MOBIUS_ROOT"] = str(MOBIUS_ROOT)
        try:
            result = subprocess.run(
                ["bash", str(mstart), "--no-landing"],
                cwd=str(MOBIUS_ROOT),
                env=env,
                capture_output=True,
                text=True,
                timeout=90,
            )
            output = (result.stdout or "").strip() + "\n" + (result.stderr or "").strip()
            self._send_json(200, {
                "ok": result.returncode == 0,
                "message": "Started." if result.returncode == 0 else "mstart exited with code " + str(result.returncode),
                "output": output.strip(),
            })
        except subprocess.TimeoutExpired:
            self._send_json(200, {"ok": False, "message": "Start timed out.", "output": ""})
        except Exception as e:
            self._send_json(200, {"ok": False, "message": str(e), "output": ""})

    def _read_json_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return {}
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}

    def _handle_service_stop(self):
        body = self._read_json_body()
        sid = body.get("id") or body.get("service_id")
        if not sid or not isinstance(sid, str):
            self._send_json(400, {"ok": False, "message": "Missing or invalid 'id' in body"})
            return
        sid = sid.strip().lower()
        ok, message = _stop_service(sid)
        self._send_json(200, {"ok": ok, "message": message})

    def _handle_service_restart(self):
        body = self._read_json_body()
        sid = body.get("id") or body.get("service_id")
        if not sid or not isinstance(sid, str):
            self._send_json(400, {"ok": False, "message": "Missing or invalid 'id' in body"})
            return
        sid = sid.strip().lower()
        _stop_service(sid)
        time.sleep(2)
        ok, message = _start_service(sid)
        self._send_json(200, {"ok": ok, "message": message})

    def _send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # quiet by default; comment out to debug


def main():
    server = HTTPServer(("127.0.0.1", PORT), LandingHandler)
    print(f"[landing] Master landing at http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
