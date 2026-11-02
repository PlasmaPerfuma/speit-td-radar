# -*- coding: utf-8 -*-
"""Extract embedded figures from a TD PDF and attach them to exercises.

This handles raster images (PDF image XObjects). Vector-only diagrams are not
extracted by pdfimages and remain a known limitation.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

FALLBACKS = [
    r"C:\Users\admin\AppData\Local\Programs\MiKTeX\miktex\bin\x64",
    r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin",
]


def _find(name: str) -> str:
    exe = shutil.which(name)
    if exe:
        return exe
    for folder in FALLBACKS:
        candidate = Path(folder) / f"{name}.exe"
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(f"{name} not found")


def _pdfinfo(pdf: Path, out: Path) -> int:
    path = out / "_pdfinfo.txt"
    try:
        with path.open("w", encoding="utf-8", errors="replace") as handle:
            subprocess.run([_find("pdfinfo"), str(pdf)], stdout=handle,
                           stderr=subprocess.DEVNULL)
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Pages:"):
                return int(line.split()[1])
    finally:
        path.unlink(missing_ok=True)
    return 0


def _list_images(pdf: Path, out: Path) -> list[dict]:
    listing = out / "_pdfimages.txt"
    with listing.open("w", encoding="utf-8", errors="replace") as handle:
        subprocess.run([_find("pdfimages"), "-list", str(pdf)],
                       stdout=handle, stderr=subprocess.DEVNULL)
    images = []
    for line in listing.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 6 or not parts[0].isdigit():
            continue
        try:
            page, width, height = int(parts[0]), int(parts[3]), int(parts[4])
        except ValueError:
            continue
        if parts[2] != "image" or width < 80 or height < 80:
            continue
        images.append({"page": page, "width": width, "height": height})
    listing.unlink(missing_ok=True)
    return images


def _page_headings(pdf: Path, pages: int, out: Path) -> dict[int, str]:
    headings: dict[int, str] = {}
    for page in range(1, pages + 1):
        txt = out / f"_page_{page}.txt"
        with txt.open("w", encoding="utf-8", errors="replace") as handle:
            subprocess.run(
                [_find("pdftotext"), "-f", str(page), "-l", str(page),
                 "-layout", "-enc", "UTF-8", str(pdf), "-"],
                stdout=handle, stderr=subprocess.DEVNULL)
        match = re.search(r"(?i)(?:exercice|exercise)\s*([0-9]+(?:\.[0-9]+)?)",
                          txt.read_text(encoding="utf-8", errors="replace"))
        if match:
            headings[page] = match.group(1)
        txt.unlink(missing_ok=True)
    return headings


def _exercise_number(no: str) -> str:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(no))
    return match.group(1) if match else ""


def attach(pdf: Path, out: Path, data: dict) -> None:
    """Extract large raster images and attach them to matching exercises."""
    pages = _pdfinfo(pdf, out)
    if pages <= 0:
        return
    images = _list_images(pdf, out)
    if not images:
        return
    headings = _page_headings(pdf, pages, out)
    exercises = data.get("exercises") or []
    if not exercises:
        return
    by_number = {_exercise_number(e.get("no", "")): e for e in exercises}

    figdir = out / "figures"
    if figdir.exists():
        shutil.rmtree(figdir, ignore_errors=True)
    figdir.mkdir(parents=True, exist_ok=True)

    page_owner: dict[int, str] = {}
    current = _exercise_number(exercises[0].get("no", ""))
    for page in range(1, pages + 1):
        if page in headings:
            current = headings[page]
        page_owner[page] = current

    for idx, img in enumerate(images, 1):
        page = img["page"]
        prefix = figdir / f"p{page}_{idx}"
        with open(prefix.with_suffix(".log"), "w", encoding="utf-8") as handle:
            subprocess.run(
                [_find("pdfimages"), "-png", "-f", str(page), "-l", str(page),
                 "-all", str(pdf), str(prefix)],
                stdout=handle, stderr=subprocess.DEVNULL)
        produced = sorted(figdir.glob(f"p{page}_{idx}-*.png"))
        if not produced:
            continue
        target = by_number.get(page_owner.get(page, "")) or exercises[0]
        target.setdefault("figures", []).append({
            "path": str(produced[0]),
            "page": page,
            "width": img["width"],
            "height": img["height"],
            "caption": f"原题图（第 {page} 页）",
        })
