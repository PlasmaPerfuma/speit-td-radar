# -*- coding: utf-8 -*-
"""OpenAI-compatible LLM client with a local, editable config.

Fill `td-radar/data/llm_config.json` (never commit/paste the key):

{
  "base_url": "https://your-endpoint/v1",
  "api_key": "sk-...",
  "model": "your-model",
  "max_tokens": 8000,
  "timeout": 180,
  "reasoning_effort": null
}

If the config is absent/placeholder, fall back to the DSH modian provider.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import paths

CONFIG_PATH = paths.LLM_CONFIG
PLACEHOLDERS = {"", "PASTE_BASE_URL_HERE", "PASTE_API_KEY_HERE", "PASTE_MODEL_NAME_HERE"}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


CFG = load_config()
HAS_CONFIG = bool(CFG)

BASE_URL = str(CFG.get("base_url") or "").strip()
if BASE_URL in PLACEHOLDERS:
    BASE_URL = os.environ.get("TD_RADAR_BASE", "https://discovery-api.intern-ai.org.cn/v1")

DEFAULT_MODEL = str(CFG.get("model") or "").strip()
if DEFAULT_MODEL in PLACEHOLDERS:
    DEFAULT_MODEL = os.environ.get("TD_RADAR_MODEL", "deepseek-v4-flash-0731")

DEFAULT_MAX_TOKENS = int(CFG.get("max_tokens") or 8000)
DEFAULT_TIMEOUT = int(CFG.get("timeout") or 180)
DEFAULT_REASONING = CFG.get("reasoning_effort") if HAS_CONFIG else "none"
if DEFAULT_REASONING in PLACEHOLDERS:
    DEFAULT_REASONING = None


def api_key() -> str:
    key = str(CFG.get("api_key") or "").strip()
    if key and key not in PLACEHOLDERS:
        return key
    key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("MODIAN_API_KEY")
    if key:
        return key
    cred = Path.home() / ".dsh" / ".credentials.yaml"
    if cred.exists():
        text = cred.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"^\s+modian:\s+(\S+)\s*$", text, re.M)
        if match:
            return match.group(1)
    raise RuntimeError(
        "no API key: fill td-radar/data/llm_config.json (api_key/base_url/model)"
    )


def chat(messages: list[dict], model: str | None = None,
         max_tokens: int | None = None, temperature: float = 0.2,
         timeout: int | None = None, response_format: dict | None = None,
         reasoning_effort: str | None = None) -> tuple[str, dict]:
    model = model or DEFAULT_MODEL
    max_tokens = DEFAULT_MAX_TOKENS if max_tokens is None else max_tokens
    timeout = DEFAULT_TIMEOUT if timeout is None else timeout
    effort = DEFAULT_REASONING if reasoning_effort is None else reasoning_effort

    url = BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format
    if effort:
        payload["reasoning_effort"] = effort
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key(),
    }

    last_error = None
    for attempt in range(2):
        req = urllib.request.Request(url, data=body, headers=headers)
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
                choice = (data.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                content = message.get("content") or ""
                usage = data.get("usage") or {}
                usage["latency_s"] = round(time.time() - started, 1)
                usage["model"] = data.get("model", model)
                return content, usage
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:600]
            last_error = f"HTTP {exc.code}: {detail}"
            if exc.code in (429, 500, 502, 503, 504) and attempt < 1:
                time.sleep(5)
                continue
            raise RuntimeError(last_error) from exc
        except Exception as exc:  # noqa: BLE001
            last_error = repr(exc)
            if attempt < 1:
                time.sleep(3)
                continue
            raise RuntimeError(last_error) from exc
    raise RuntimeError(last_error or "unknown LLM error")
