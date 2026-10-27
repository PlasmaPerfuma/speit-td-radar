# -*- coding: utf-8 -*-
"""Reusable PDF -> quality gate -> LLM -> rendered PDF pipeline."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import paths
from analyze import analyze
from extract import extract
from quality import gate
from td_render import render_json


def _slug(text: str) -> str:
    s = re.sub(r"[^0-9A-Za-zÀ-ÿ]+", "_", text.strip())
    return s.strip("_").lower() or "td"


def process_pdf(pdf_path: str | Path, course: str, td: str,
                out_dir: str | Path | None = None,
                model: str | None = None,
                max_tokens: int | None = None) -> dict:
    pdf = Path(pdf_path)
    out = Path(out_dir) if out_dir else paths.OUT / f"{_slug(course)}_{td.lower()}"
    out.mkdir(parents=True, exist_ok=True)

    txt = paths.INBOX / f"{_slug(course)}_{td.lower()}_{pdf.stem}.txt"
    text = extract(pdf, txt)
    q = gate(text)
    if not q["good"]:
        raise RuntimeError(f"quality gate failed: {q['reasons']}")

    data, raw, usage = analyze(course, td, text, model=model, max_tokens=max_tokens)
    (out / "llm_raw.json").write_text(raw, encoding="utf-8")
    (out / "td_detail.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    result = render_json(out / "td_detail.json", out / "td_detail.pdf")

    meta = {
        "source_pdf": str(pdf),
        "course": course,
        "td": td,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "quality_gate": q,
        "usage": usage,
        "render": result,
        "exercises": [e.get("no") for e in data.get("exercises", [])],
    }
    (out / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta
