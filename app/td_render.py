# -*- coding: utf-8 -*-
r"""TD card renderer: short Chinese lines + centered formulas, per-step solution.

2026-10-26 final corrections:
  - body ~10.5pt; Arial + Microsoft YaHei; Chinese body smaller.
  - 题干 one heading: French then Chinese.
  - 知识点 / 解题思路: short Chinese lines, formulas on their own centered lines.
  - 解答: French line -> Chinese line -> centered formula (not block-level).
  - No 速览, no keyword block, no separate answer section.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

LATEX_CMD = os.environ.get("TD_RADAR_LATEX", "xelatex")
_DEFAULT_MIKTEX = Path(r"C:\Users\admin\AppData\Local\Programs\MiKTeX\miktex\bin\x64")
LATEX_BIN_DIR = Path(os.environ.get(
    "TD_RADAR_LATEX_BIN",
    str(_DEFAULT_MIKTEX) if _DEFAULT_MIKTEX.exists() else "",
))
TOKEN = re.compile(r"(\$[^$]+\$)")

PREAMBLE = r"""\documentclass[UTF8,a4paper,10pt]{ctexart}
\usepackage{amsmath,amssymb}
\setmainfont{Tahoma}
\setsansfont{Tahoma}
\setCJKmainfont{SimHei}
\setCJKsansfont{Microsoft YaHei}[BoldFont={Microsoft YaHei Bold}]
\mathversion{bold}
\setlength{\parindent}{0pt}
\setlength{\parskip}{.35em}
\setlength{\abovedisplayskip}{2pt}
\setlength{\belowdisplayskip}{2pt}
\setlength{\abovedisplayshortskip}{1pt}
\setlength{\belowdisplayshortskip}{1pt}
\linespread{1.3}
\raggedright
\setlength{\paperwidth}{210mm}\setlength{\paperheight}{297mm}
\setlength{\textwidth}{166mm}
\setlength{\oddsidemargin}{-3.4mm}\setlength{\evensidemargin}{-3.4mm}
\setlength{\headheight}{14pt}\setlength{\headsep}{12pt}\setlength{\footskip}{12mm}
\setlength{\topmargin}{-12.6mm}\setlength{\textheight}{243mm}
\pagestyle{plain}
\newcommand{\tdsection}[1]{\par\vspace{2.5mm}{\large\bfseries\sffamily #1}\par\vspace{.6mm}}
\newcommand{\tdsub}[1]{\par\vspace{1.5mm}{\normalsize\bfseries\sffamily #1}\par\vspace{.6mm}}
\newcommand{\tdformula}[1]{\[ \displaystyle #1 \]}
\makeatletter
\newlength{\glneedlen}
\newcommand{\glNeedspace}[1]{\par\begingroup\setlength{\glneedlen}{#1}\vskip\z@\@plus\glneedlen\penalty-100\vskip\z@\@plus-\glneedlen\vskip\glneedlen\penalty9999\vskip-\glneedlen\endgroup}
\makeatother
\begin{document}
"""


def esc(text: str) -> str:
    table = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "#": r"\#",
        "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(table.get(ch, ch) for ch in str(text))


def text_escape(text: str) -> str:
    s = esc(text)
    for symbol, latex in {
        "∈": r"$\in$", "≤": r"$\le$", "≥": r"$\ge$",
        "≠": r"$\ne$", "→": r"$\to$", "∞": r"$\infty$",
        "⊂": r"$\subset$", "⊃": r"$\supset$", "⊕": r"$\oplus$",
        "∩": r"$\cap$", "∪": r"$\cup$", "∅": r"$\varnothing$",
        "⇒": r"$\Rightarrow$", "⇔": r"$\Leftrightarrow$",
    }.items():
        s = s.replace(symbol, latex)
    return s


def rich(text: str) -> str:
    text = str(text or "")
    out: list[str] = []
    end = 0
    for match in TOKEN.finditer(text):
        out.append(text_escape(text[end:match.start()]))
        out.append(match.group(1))
        end = match.end()
    out.append(text_escape(text[end:]))
    return "".join(out)


def zh(text: str) -> str:
    return rich(text)


def formula_tex(value: str) -> str:
    """Strip $/$$ wrappers; the LLM often returns display math already wrapped."""
    s = str(value or "").strip()
    if s.startswith("$$") and s.endswith("$$"):
        s = s[2:-2]
    elif s.startswith("$") and s.endswith("$"):
        s = s[1:-1]
    return s.strip()


def _idea_lines(steps: list) -> list[str]:
    out: list[str] = []
    for idx, step in enumerate(steps, 1):
        if isinstance(step, dict):
            text = step.get("text", "")
            formula = step.get("formula", "")
        else:
            text, formula = step, ""
        out.append(r"\begin{minipage}{\linewidth}")
        out.append(r"\noindent\hspace*{1em}\textbf{" + str(idx) + ".} " + zh(text) + r"\par")
        if formula:
            out.append(r"\tdformula{" + formula_tex(formula) + "}")
        out.append(r"\end{minipage}")
        out.append(r"\vspace{.8mm}")
    return out


def _solution_lines(steps: list) -> list[str]:
    out: list[str] = []
    total = len(steps)
    for idx, step in enumerate(steps, 1):
        last = idx == total
        blocks = step.get("blocks") or []
        if blocks:
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                kind = block.get("type", "text")
                if kind == "math":
                    tex = block.get("tex", "")
                    if tex:
                        out.append(r"\tdformula{" + formula_tex(tex) + "}")
                else:
                    fr = block.get("fr", "")
                    zh_text = block.get("zh", "")
                    if fr:
                        out.append(r"\noindent " + rich(fr) + r"\par")
                    if zh_text:
                        out.append(r"\hspace*{1em}" + zh(zh_text) + r"\par")
            if not last:
                out.append(r"\vspace{.6mm}")
            continue

        out.append(rich(step.get("fr", "")) + r"\par")
        out.append(r"\hspace*{1em}" + zh(step.get("zh", "")) + r"\par")
        if step.get("formula"):
            out.append(r"\tdformula{" + formula_tex(step["formula"]) + "}")
        if not last:
            out.append(r"\vspace{.8mm}")
    return out


def build_latex(data: dict) -> str:
    lines = [PREAMBLE]
    lines.append(r"\begin{center}")
    lines.append(r"{\large\bfseries\sffamily " + rich(data.get("course", "")) + " / " + rich(data.get("td", "")) + r"}\\[.8mm]")
    lines.append(r"{\normalsize\bfseries " + rich(data.get("title", "")) + r"}")
    lines.append(r"\end{center}")
    lines.append(r"\vspace{1mm}\hrule")

    for exercise in data.get("exercises", []):
        lines.append(r"\glNeedspace{8\baselineskip}")
        lines.append(r"\tdsection{" + rich(exercise.get("no", "")) + " / " + rich(exercise.get("theme_zh", "")) + "}")
        lines.append(r"\tdsub{题目翻译}")
        lines.append(rich(exercise.get("statement_fr", "")) + r"\par")
        lines.append(r"\hspace*{1em}" + zh(exercise.get("statement_zh", "")) + r"\par")
        for note in exercise.get("statement_notes") or []:
            lines.append(r"\hspace*{1em}· " + zh(note) + r"\par")

        if exercise.get("knowledge"):
            lines.append(r"\glNeedspace{4\baselineskip}")
            lines.append(r"\tdsub{相关知识点}")
            for idx, item in enumerate(exercise["knowledge"], 1):
                lines.append(r"\begin{minipage}{\linewidth}")
                title = item.get("title") or item.get("zh", "")
                fr = item.get("fr", "")
                head = r"\hspace*{.5em}\textbf{（" + str(idx) + "）" + rich(title) + "}"
                if fr:
                    head += "（" + rich(fr) + "）"
                lines.append(head + r"\par")
                for paragraph in item.get("body") or []:
                    lines.append(r"\hspace*{1em}" + zh(paragraph) + r"\par")
                for formula in item.get("formulas") or []:
                    lines.append(r"\tdformula{" + formula_tex(formula) + "}")
                lines.append(r"\end{minipage}")
                lines.append(r"\vspace{.8mm}")

        subquestions = exercise.get("subquestions") or []
        if subquestions:
            if any(sq.get("idea") for sq in subquestions):
                lines.append(r"\glNeedspace{6\baselineskip}")
                lines.append(r"\tdsub{解题思路}")
                for sq in subquestions:
                    if not sq.get("idea"):
                        continue
                    lines.append(r"\glNeedspace{6\baselineskip}")
                    lines.append(r"\noindent\textbf{" + rich(sq.get("label_zh") or sq.get("label", "")) + r"}\par")
                    lines.extend(_idea_lines(sq["idea"]))
            if any(sq.get("solution") for sq in subquestions):
                lines.append(r"\glNeedspace{3\baselineskip}")
                lines.append(r"\tdsub{法语解答}")
                for sq in subquestions:
                    if not sq.get("solution"):
                        continue
                    lines.append(r"\glNeedspace{3\baselineskip}")
                    lines.append(r"\noindent\textbf{" + rich(sq.get("label_fr") or sq.get("label", "")) + r"}\par")
                    lines.extend(_solution_lines(sq["solution"]))
        else:
            if exercise.get("idea"):
                lines.append(r"\glNeedspace{4\baselineskip}")
                lines.append(r"\tdsub{解题思路}")
                lines.extend(_idea_lines(exercise["idea"]))

            if exercise.get("solution"):
                lines.append(r"\glNeedspace{5\baselineskip}")
                lines.append(r"\tdsub{法语解答}")
                lines.extend(_solution_lines(exercise["solution"]))

    lines.append(r"\end{document}")
    return "\n".join(lines)


def _run(cmd: list[str], out_file: Path, cwd: Path, env: dict) -> int:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8", errors="replace") as handle:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, stdout=handle,
                              stderr=subprocess.STDOUT)
    return proc.returncode


def compile_tex(tex: Path, pdf: Path) -> dict:
    tex, pdf = Path(tex), Path(pdf)
    build = tex.parent / "_build_sample"
    if build.exists():
        shutil.rmtree(build, ignore_errors=True)
    build.mkdir(parents=True, exist_ok=True)
    study = build / "study.tex"
    shutil.copyfile(tex, study)
    env = os.environ.copy()
    env["PATH"] = str(LATEX_BIN_DIR) + os.pathsep + env.get("PATH", "")
    for pass_no in (1, 2):
        code = _run([LATEX_CMD, "-interaction=nonstopmode", "-halt-on-error", "study.tex"],
                    build / f"p{pass_no}.out", build, env)
        if code:
            tail = (build / f"p{pass_no}.out").read_text(encoding="utf-8", errors="replace")[-3000:]
            raise RuntimeError(f"xelatex pass {pass_no} failed ({code}):\n{tail}")
    pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(build / "study.pdf", pdf)
    log = (build / "study.log").read_text(encoding="utf-8", errors="replace")
    missing = log.count("Missing character")
    match = re.search(r"Output written on .*?\((\d+) pages?", log)
    pages = int(match.group(1)) if match else None
    return {"pdf": str(pdf), "pages": pages, "missing_chars": missing}


def render_json(json_path: Path, pdf_path: Path, tex_path: Path | None = None) -> dict:
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    tex_path = Path(tex_path) if tex_path else Path(pdf_path).with_suffix(".tex")
    tex_path.write_text(build_latex(data), encoding="utf-8")
    return compile_tex(tex_path, Path(pdf_path))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("json")
    parser.add_argument("pdf")
    parser.add_argument("--tex")
    args = parser.parse_args()
    print(json.dumps(render_json(Path(args.json), Path(args.pdf),
                                 Path(args.tex) if args.tex else None),
                     ensure_ascii=False, indent=2))
