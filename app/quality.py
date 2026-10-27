# -*- coding: utf-8 -*-
"""Text-layer quality gate: decide whether pdftotext output is usable.

The check is deliberately simple and explainable.  It catches the known
failure mode of French maths PDFs: the text layer is replaced by a broken
font encoding (∞ -> V, -> -> ÝÑ, - -> ¡), while the visual PDF is fine.
"""
from __future__ import annotations

import re

# Latin-1 characters that are extremely unlikely in normal French maths text
# but appear in the broken font encodings we have seen.
BAD_CHARS = set("¡¢£¤¥¦¨©ª¬®¯µ¶¸¹º¼½¾¿ÝÞÑ")

FRENCH_STOPWORDS = set(
    """le la les de des du un une est sont soit montrer donc pour avec dans sur par
    que qui on à et ou en ce cette ces il elle nous vous ils elles au aux se sa son
    leur leurs plus moins très tout tous toute toutes comme si alors ainsi or car
    mais ni y ne pas""".split()
)


def metrics(text: str) -> dict:
    n = max(len(text), 1)
    letters = sum(1 for ch in text if ch.isalpha())
    mojibake = sum(1 for ch in text if ch in BAD_CHARS)
    replacement = text.count("\ufffd")
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", text.lower())
    french = sum(1 for word in words if word in FRENCH_STOPWORDS)
    return {
        "chars": n,
        "letters": letters,
        "letters_ratio": round(letters / n, 4),
        "mojibake": mojibake,
        "replacement": replacement,
        "french_stopwords": french,
        "french_per_1k": round(french / n * 1000, 2),
        "words": len(words),
    }


def gate(text: str) -> dict:
    m = metrics(text)
    reasons: list[str] = []
    if m["mojibake"] >= 5:
        reasons.append(f"mojibake markers: {m['mojibake']}")
    if m["replacement"] > 0:
        reasons.append(f"replacement chars: {m['replacement']}")
    if m["french_per_1k"] < 15:
        reasons.append(f"too few French stopwords: {m['french_per_1k']}/1k")
    if m["letters_ratio"] < 0.20:
        reasons.append(f"too few letters: {m['letters_ratio']}")
    m["good"] = not reasons
    m["reasons"] = reasons
    return m
