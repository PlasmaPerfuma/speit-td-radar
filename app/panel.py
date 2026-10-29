# -*- coding: utf-8 -*-
"""Local control panel for TD Radar.

A small stdlib HTTP server bound to 127.0.0.1. The browser UI is a single
static page; adding a feature means adding a route here and a tab in
``panel/index.html``. No Flask/FastAPI dependency.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import canvas
import notify
import paths
import scheduler

PANEL_HTML = paths.RESOURCE_DIR / "panel" / "index.html"
RUNNING = False
RUN_LOCK = threading.Lock()


def open_app_window(url: str) -> bool:
    """Open the panel as a standalone Edge/Chrome app window.

    A normal webbrowser.open() gives a tab; --app gives a window without the
    browser chrome, which is much closer to a desktop control panel.
    """
    candidates = [
        shutil.which("msedge"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""),
                     "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""),
                     "Microsoft", "Edge", "Application", "msedge.exe"),
        shutil.which("chrome"),
        os.path.join(os.environ.get("ProgramFiles", ""),
                     "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for exe in candidates:
        if not exe or not os.path.isfile(exe):
            continue
        try:
            subprocess.Popen([exe, f"--app={url}", "--window-size=1100,820"],
                             close_fds=True)
            return True
        except OSError:
            continue
    webbrowser.open(url)
    return False


def _read_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)


def _mask(value: str) -> bool:
    return bool(value and "PASTE" not in value)


def _latest_pdf() -> str | None:
    files = []
    for root in (paths.DATA_DIR / "out", paths.OUT):
        if root.exists():
            files.extend(root.rglob("td_detail.pdf"))
    return str(max(files, key=lambda p: p.stat().st_mtime)) if files else None


def status() -> dict:
    state = canvas.load_state()
    llm = _read_json(paths.LLM_CONFIG, {})
    ncfg = _read_json(paths.DATA_DIR / "notify.json", {})
    try:
        sched = scheduler.status(scheduler.load_schedule())
    except Exception as exc:  # noqa: BLE001
        sched = {"error": str(exc)}
    return {
        "frozen": paths.IS_FROZEN,
        "data_dir": str(paths.DATA_DIR),
        "token_set": _mask(paths.TOKEN.read_text(encoding="utf-8", errors="replace").strip()
                           if paths.TOKEN.exists() else ""),
        "llm": {
            "base_url": llm.get("base_url", ""),
            "model": llm.get("model", ""),
            "max_tokens": llm.get("max_tokens"),
            "api_key_set": _mask(llm.get("api_key", "")),
        },
        "notify": {
            "enabled": bool(ncfg.get("enabled")),
            "provider": ncfg.get("provider", ""),
            "wecom_set": _mask(ncfg.get("wecom_webhook", "")),
        },
        "canvas_files": len(state.get("files", {})),
        "latest_pdf": _latest_pdf(),
        "running": RUNNING,
        "schedule": sched,
    }


def config() -> dict:
    llm = _read_json(paths.LLM_CONFIG, {})
    ncfg = _read_json(paths.DATA_DIR / "notify.json", {})
    return {
        "token_set": _mask(paths.TOKEN.read_text(encoding="utf-8", errors="replace").strip()
                           if paths.TOKEN.exists() else ""),
        "llm": {
            "base_url": llm.get("base_url", "https://api.deepseek.com"),
            "model": llm.get("model", "deepseek-flash"),
            "max_tokens": llm.get("max_tokens", 100000),
            "timeout": llm.get("timeout", 180),
            "api_key_set": _mask(llm.get("api_key", "")),
        },
        "notify": {
            "enabled": bool(ncfg.get("enabled")),
            "provider": ncfg.get("provider", "wecom"),
            "wecom_set": _mask(ncfg.get("wecom_webhook", "")),
        },
        "data_dir": str(paths.DATA_DIR),
    }


def save_config(payload: dict) -> dict:
    token = str(payload.get("canvas_token", "")).strip()
    if token and token != "********":
        paths.TOKEN.write_text(token + "\n", encoding="utf-8")

    llm = _read_json(paths.LLM_CONFIG, {})
    for src, dst in (("llm_base_url", "base_url"), ("llm_model", "model")):
        value = str(payload.get(src, "")).strip()
        if value:
            llm[dst] = value
    if payload.get("llm_max_tokens"):
        llm["max_tokens"] = int(payload["llm_max_tokens"])
    key = str(payload.get("llm_api_key", "")).strip()
    if key and key != "********":
        llm["api_key"] = key
    llm.setdefault("timeout", 180)
    llm.setdefault("reasoning_effort", None)
    paths.LLM_CONFIG.write_text(json.dumps(llm, ensure_ascii=False, indent=2),
                                encoding="utf-8")

    ncfg = _read_json(paths.DATA_DIR / "notify.json", {})
    webhook = str(payload.get("wecom_webhook", "")).strip()
    if webhook and webhook != "********":
        ncfg["wecom_webhook"] = webhook
    if "notify_enabled" in payload:
        ncfg["enabled"] = bool(payload["notify_enabled"])
    if payload.get("notify_provider"):
        ncfg["provider"] = str(payload["notify_provider"])
    ncfg.setdefault("send_file", True)
    (paths.DATA_DIR / "notify.json").write_text(
        json.dumps(ncfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return status()


def save_schedule(payload: dict) -> dict:
    cfg = scheduler.load_schedule()
    t = cfg["trigger"]
    for src, dst in (("time", "time"), ("until", "until"),
                     ("other_days_time", "other_days_time")):
        value = str(payload.get(src, "")).strip()
        if value:
            t[dst] = value
    if payload.get("weekdays"):
        t["weekdays"] = [d.strip().upper() for d in str(payload["weekdays"]).split(",")
                         if d.strip()]
    if payload.get("interval_minutes") is not None:
        t["interval_minutes"] = int(payload["interval_minutes"])
    scheduler.save_schedule(cfg)
    if payload.get("install"):
        scheduler.install(cfg)
    return {"config": cfg, "status": scheduler.status(cfg)}


def _run_job() -> None:
    global RUNNING
    try:
        canvas.run_once(download_new=True, process_new=True)
    finally:
        with RUN_LOCK:
            RUNNING = False


def start_run() -> bool:
    global RUNNING
    with RUN_LOCK:
        if RUNNING:
            return False
        RUNNING = True
    threading.Thread(target=_run_job, daemon=True).start()
    return True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, code: int = 200) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                html = PANEL_HTML.read_text(encoding="utf-8")
                self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/status":
                self._json(status())
            elif path == "/api/config":
                self._json(config())
            elif path == "/api/logs":
                log = paths.LOGS / "canvas_poll.log"
                text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
                self._json({"log": "\n".join(text.splitlines()[-250:])})
            elif path == "/api/canvas":
                result = []
                for cid, (_, label) in canvas.COURSES.items():
                    try:
                        files = canvas.discover(cid)
                    except Exception as exc:  # noqa: BLE001
                        result.append({"course": label, "error": str(exc)})
                        continue
                    result.append({"course": label, "files": [
                        {"name": f["name"], "td": f["td"], "kind": f["kind"],
                         "size": f["size"], "updated_at": f["updated_at"]}
                        for f in files
                    ]})
                self._json({"courses": result})
            elif path == "/api/schedule":
                cfg = scheduler.load_schedule()
                self._json({"config": cfg, "status": scheduler.status(cfg)})
            else:
                self._json({"error": "not found"}, 404)
        except Exception as exc:  # noqa: BLE001
            self._json({"error": str(exc)}, 500)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/config":
                self._json(save_config(self._body()))
            elif path == "/api/schedule":
                self._json(save_schedule(self._body()))
            elif path == "/api/run":
                self._json({"started": start_run(), "status": status()})
            elif path == "/api/notify/test":
                file = _latest_pdf()
                result = notify.send("TD Radar 测试", "控制台通知测试", file=file)
                self._json({"file": file, "result": result})
            else:
                self._json({"error": "not found"}, 404)
        except Exception as exc:  # noqa: BLE001
            self._json({"error": str(exc)}, 500)


def main(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> int:
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"TD Radar control panel: {url}")
    print("Ctrl+C to stop")
    if open_browser:
        threading.Thread(target=lambda: (time.sleep(1.0), open_app_window(url)),
                         daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
