# -*- coding: utf-8 -*-
"""PDF -> text, using the pdftotext already installed on this machine.

Note: under the DSH sandbox, child processes may not use piped stdio.
We redirect to DEVNULL instead of capture_output=True.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

FALLBACKS = [
    r"C:\Users\admin\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdftotext.exe",
    r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin\pdftotext.exe",
]


def find_pdftotext() -> str:
    exe = shutil.which("pdftotext")
    if exe:
        return exe
    for candidate in FALLBACKS:
        if Path(candidate).is_file():
            return candidate
    raise RuntimeError("pdftotext not found")


def extract(pdf: Path | str, txt: Path | str) -> str:
    pdf, txt = Path(pdf), Path(txt)
    txt.parent.mkdir(parents=True, exist_ok=True)
    cmd = [find_pdftotext(), "-layout", "-enc", "UTF-8", str(pdf), str(txt)]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if proc.returncode:
        raise RuntimeError(f"pdftotext failed with exit code {proc.returncode}")
    return txt.read_text(encoding="utf-8", errors="replace")
