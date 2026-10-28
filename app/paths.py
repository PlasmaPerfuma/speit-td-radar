# -*- coding: utf-8 -*-
"""Paths: repo layout in dev, per-user app-data when frozen."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
IS_FROZEN = bool(getattr(sys, "frozen", False))
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", ROOT))

# Writable data: %APPDATA%\TD Radar when packaged, repo data/ in dev.
DATA_DIR = Path(os.environ.get("TD_RADAR_DATA", "")) if os.environ.get("TD_RADAR_DATA") else (
    Path(os.environ.get("APPDATA", Path.home())) / "TD Radar" if IS_FROZEN else ROOT / "data"
)

INBOX = DATA_DIR / "inbox" if IS_FROZEN else ROOT / "inbox"
CANVAS_INBOX = INBOX / "canvas"
OUT = DATA_DIR / "out" if IS_FROZEN else ROOT / "out"
LOGS = DATA_DIR / "logs" if IS_FROZEN else ROOT / "logs"
PROMPTS = RESOURCE_DIR / "prompts"
TESTS = ROOT / "tests"
STATE = DATA_DIR / "canvas_state.json"
TOKEN = DATA_DIR / "canvas_token.txt"
LLM_CONFIG = DATA_DIR / "llm_config.json"

for _d in (DATA_DIR, INBOX, CANVAS_INBOX, OUT, LOGS):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except OSError:
        # A read-only or ACL-restricted data dir must not break `--help`,
        # `doctor`, or config inspection; commands that write surface the error.
        pass
