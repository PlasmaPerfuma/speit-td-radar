# -*- coding: utf-8 -*-
"""Markdown -> XeLaTeX -> PDF, reusing the existing good-learning pipeline.

Under the DSH sandbox, subprocess pipes are blocked.  Every child process here
writes to a real file, never to a pipe.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

BUILD = Path(r"C:\Users\admin\Documents\deepseek-harness\good-learning skill\Séries-级数\源文件\build_docs.py")
MIKTEX_BIN = Path(r"C:\Users\admin\AppData\Local\Programs\MiKTeX\miktex\bin\x64")


def _run_to_file(cmd: list[str], out_file: Path, cwd: Path | None = None,
                 env: dict | None = None) -> int:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8", errors="replace") as handle:
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env,
                              stdout=handle, stderr=subprocess.STDOUT)
    return proc.returncode


def render(md: Path, pdf: Path) -> dict:
    md, pdf = Path(md), Path(pdf)
    tex = md.with_suffix(".tex")
    build = tex.parent / "_build"
    if build.exists():
        shutil.rmtree(build, ignore_errors=True)
    build.mkdir(parents=True, exist_ok=True)

    code = _run_to_file(
        [sys.executable, str(BUILD), str(md), str(tex), "errors", "compact"],
        build / "build_docs.out",
    )
    if code:
        raise RuntimeError(f"build_docs.py failed ({code}); see {build / 'build_docs.out'}")

    text = tex.read_text(encoding="utf-8")
    if r"\small" not in text:
        text = re.sub(r"(\\chaptertitle\{[^}]*\})", r"\1\n\\small", text, count=1)
        tex.write_text(text, encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = str(MIKTEX_BIN) + os.pathsep + env.get("PATH", "")
    study = build / "study.tex"
    shutil.copyfile(tex, study)
    for pass_no in (1, 2):
        code = _run_to_file(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error", "study.tex"],
            build / f"p{pass_no}.out",
            cwd=build,
            env=env,
        )
        if code:
            tail = (build / f"p{pass_no}.out").read_text(encoding="utf-8", errors="replace")[-2500:]
            raise RuntimeError(f"xelatex pass {pass_no} failed ({code}):\n{tail}")

    pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(build / "study.pdf", pdf)
    log = (build / "study.log").read_text(encoding="utf-8", errors="replace")
    missing = log.count("Missing character")
    match = re.search(r"Output written on .*?\((\d+) pages?", log)
    pages = int(match.group(1)) if match else None

    png = None
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        png = pdf.with_suffix(".png")
        subprocess.run(
            [pdftoppm, "-png", "-r", "80", "-f", "1", "-singlefile",
             str(pdf), str(png.with_suffix(""))],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if not png.is_file():
            png = None
    return {"pdf": str(pdf), "tex": str(tex), "pages": pages,
            "missing_chars": missing,
            "preview_png": str(png) if png else None}
