# -*- coding: utf-8 -*-
"""Push notifications for generated TD PDFs.

Providers:
  wecom  — 企业微信群机器人 webhook (text + optional file)
  bark   — iOS push (text only)
  email  — SMTP attachment
  ntfy   — ntfy topic (text + optional attachment)

Config lives in ``data/notify.json`` and is never printed in full.
"""
from __future__ import annotations

import json
import mimetypes
import smtplib
import urllib.parse
import urllib.request
import uuid
from email.message import EmailMessage
from pathlib import Path

import paths

CONFIG_PATH = paths.DATA_DIR / "notify.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"enabled": False}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"enabled": False}
    except Exception:
        return {"enabled": False}


def _post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _check(resp: dict, what: str) -> dict:
    code = resp.get("errcode", 0)
    if code:
        raise RuntimeError(f"{what} failed: errcode={code} errmsg={resp.get('errmsg')}")
    return resp


def _upload_url(webhook: str) -> str:
    parsed = urllib.parse.urlparse(webhook)
    key = urllib.parse.parse_qs(parsed.query).get("key", [""])[0]
    if not key:
        raise RuntimeError("wecom webhook has no key")
    path = parsed.path.replace("/send", "/upload_media")
    return f"{parsed.scheme}://{parsed.netloc}{path}?key={urllib.parse.quote(key)}&type=file"


def send_wecom(cfg: dict, title: str, body: str, file: str | Path | None = None) -> dict:
    webhook = cfg.get("wecom_webhook", "")
    if not webhook or "PASTE" in webhook:
        raise RuntimeError("wecom_webhook is not configured")
    text = f"{title}\n{body}".strip()
    result = _check(
        _post_json(webhook, {"msgtype": "text", "text": {"content": text}}),
        "wecom text",
    )
    sent = {"text": True, "file": False, "media_id": None}
    if file and cfg.get("send_file", True):
        path = Path(file)
        if not path.exists():
            raise RuntimeError(f"notification file missing: {path}")
        if path.stat().st_size > 20 * 1024 * 1024:
            raise RuntimeError("wecom file exceeds 20 MB")
        boundary = "----TDradar" + uuid.uuid4().hex
        data = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        parts = [
            f"--{boundary}\r\n".encode(),
            (f'Content-Disposition: form-data; name="media"; filename="{path.name}"\r\n'
             f"Content-Type: {mime}\r\n\r\n").encode(),
            data,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
        req = urllib.request.Request(
            _upload_url(webhook), data=b"".join(parts),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            uploaded = json.loads(resp.read().decode("utf-8", errors="replace"))
        media_id = _check(uploaded, "wecom upload").get("media_id")
        if not media_id:
            raise RuntimeError("wecom upload returned no media_id")
        _check(_post_json(webhook, {"msgtype": "file", "file": {"media_id": media_id}}),
               "wecom file")
        sent.update({"file": True, "media_id": media_id})
    return sent


def send_bark(cfg: dict, title: str, body: str, file=None) -> dict:
    key = cfg.get("bark_key", "")
    if not key:
        raise RuntimeError("bark_key is not configured")
    base = cfg.get("bark_url", "https://api.day.app").rstrip("/")
    url = f"{base}/{urllib.parse.quote(key)}/{urllib.parse.quote(title)}/{urllib.parse.quote(body)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def send_email(cfg: dict, title: str, body: str, file: str | Path | None = None) -> dict:
    e = cfg.get("email") or {}
    required = ("smtp", "user", "password", "to")
    if any(not e.get(k) for k in required):
        raise RuntimeError("email config incomplete")
    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = e["user"]
    msg["To"] = e["to"]
    msg.set_content(body)
    if file:
        path = Path(file)
        msg.add_attachment(path.read_bytes(), maintype="application", subtype="pdf",
                           filename=path.name)
    with smtplib.SMTP_SSL(e["smtp"], int(e.get("port", 465)), timeout=60) as smtp:
        smtp.login(e["user"], e["password"])
        smtp.send_message(msg)
    return {"email": True, "file": bool(file)}


def send(title: str, body: str, file: str | Path | None = None,
         cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    if not cfg.get("enabled", False):
        return {"skipped": "disabled"}
    provider = (cfg.get("provider") or "wecom").lower()
    if provider == "wecom":
        return {"provider": "wecom", **send_wecom(cfg, title, body, file)}
    if provider == "bark":
        return {"provider": "bark", **send_bark(cfg, title, body, file)}
    if provider == "email":
        return {"provider": "email", **send_email(cfg, title, body, file)}
    raise RuntimeError(f"unsupported notify provider: {provider}")
