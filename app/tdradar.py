# -*- coding: utf-8 -*-
"""TD Radar console entrypoint (dev + PyInstaller)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

import canvas  # noqa: E402
import paths  # noqa: E402
import pipeline  # noqa: E402
import td_render  # noqa: E402


def doctor() -> int:
    ok = True
    print(f"frozen      : {paths.IS_FROZEN}")
    print(f"data dir    : {paths.DATA_DIR}")
    print(f"token       : {paths.TOKEN} ", end="")
    try:
        tok = paths.TOKEN.read_text(encoding="utf-8", errors="replace").strip()
        if tok and "PASTE" not in tok:
            print(f"(set, {len(tok)} chars)")
        else:
            print("(missing/placeholder)")
            ok = False
    except Exception:
        print("(missing)")
        ok = False

    print(f"llm config  : {paths.LLM_CONFIG}")
    try:
        cfg = json.loads(paths.LLM_CONFIG.read_text(encoding="utf-8"))
        print(f"  base={cfg.get('base_url')} model={cfg.get('model')} "
              f"max_tokens={cfg.get('max_tokens')}")
        if not cfg.get("api_key") or "PASTE" in str(cfg.get("api_key")):
            print("  api_key: missing/placeholder")
            ok = False
    except Exception as exc:
        print(f"  unreadable: {exc}")
        ok = False

    path = str(td_render.LATEX_BIN_DIR) + os.pathsep + os.environ.get("PATH", "")
    xelatex = shutil.which(td_render.LATEX_CMD, path=path)
    print(f"latex       : {td_render.LATEX_CMD} -> {xelatex or 'NOT FOUND'}")
    if not xelatex:
        ok = False

    state = canvas.load_state()
    print(f"canvas state: {len(state.get('files', {}))} file(s)")
    print("status      :", "OK" if ok else "NEEDS ATTENTION")
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tdradar", description="TD Radar")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="check token/api/latex/state")

    pc = sub.add_parser("canvas", help="Canvas list/poll/download")
    pc.add_argument("canvas_args", nargs=argparse.REMAINDER)

    pg = sub.add_parser("generate", help="PDF -> quality gate -> LLM -> detail PDF")
    pg.add_argument("--pdf", required=True)
    pg.add_argument("--course", required=True)
    pg.add_argument("--td", required=True)
    pg.add_argument("--out", default=None)
    pg.add_argument("--model", default=None)
    pg.add_argument("--max-tokens", type=int, default=None)

    args = p.parse_args(argv)
    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "canvas":
        return canvas.main(args.canvas_args)
    if args.cmd == "generate":
        meta = pipeline.process_pdf(args.pdf, args.course, args.td,
                                    out_dir=args.out, model=args.model,
                                    max_tokens=args.max_tokens)
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
