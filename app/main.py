# -*- coding: utf-8 -*-
"""TD Radar M0: offline TD -> quality gate -> DeepSeek -> quick + detail PDFs."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import paths
from analyze import analyze, normalize, parse_json, to_markdown
from extract import extract
from quality import gate
from render import render


def _print_gate(label: str, data: dict) -> None:
    print(f"[{label}] chars={data['chars']} mojibake={data['mojibake']} "
          f"french/1k={data['french_per_1k']} letters={data['letters_ratio']} "
          f"-> {'GOOD' if data['good'] else 'BAD'}")
    for reason in data["reasons"]:
        print(f"  - {reason}")


def demo(args) -> int:
    clean_pdf = Path(args.clean_pdf)
    garbled_pdf = Path(args.garbled_pdf)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("== 1. extract ==")
    clean_text = extract(clean_pdf, paths.INBOX / "algebre_td1.txt")
    garbled_text = extract(garbled_pdf, paths.INBOX / "series_td2.txt")
    clean_gate = gate(clean_text)
    garbled_gate = gate(garbled_text)
    _print_gate("clean", clean_gate)
    _print_gate("garbled", garbled_gate)

    if not clean_gate["good"]:
        print("!! clean PDF failed the quality gate; aborting")
        return 2
    if garbled_gate["good"]:
        print("!! garbled PDF unexpectedly passed; gate needs tuning")

    print("\n== 2. analyze ==")
    if args.raw:
        raw = Path(args.raw).read_text(encoding="utf-8")
        data = normalize(parse_json(raw), args.course, args.td)
        usage = {"model": "replay", "latency_s": 0, "total_tokens": 0}
        print(f"replay from {args.raw}")
    else:
        data, raw, usage = analyze(args.course, args.td, clean_text, model=args.model)
        print(f"model={usage.get('model')} latency={usage.get('latency_s')}s "
              f"tokens={usage.get('total_tokens')} "
              f"(prompt={usage.get('prompt_tokens')}, completion={usage.get('completion_tokens')})")
    print(f"exercises={len(data.get('exercises', []))} "
          f"glossary={len(data.get('glossary', []))}")
    (out_dir / "llm_raw.json").write_text(raw, encoding="utf-8")

    print("\n== 3. markdown ==")
    quick_md = out_dir / "td_card.md"
    detail_md = out_dir / "td_detail.md"
    quick_md.write_text(to_markdown(data, "quick"), encoding="utf-8")
    detail_md.write_text(to_markdown(data, "detail"), encoding="utf-8")
    print(f"wrote {quick_md} and {detail_md}")

    print("\n== 4. render ==")
    quick = render(quick_md, out_dir / "td_card.pdf")
    detail = render(detail_md, out_dir / "td_detail.pdf")
    print(json.dumps({"quick": quick, "detail": detail}, ensure_ascii=False, indent=2))

    meta = {
        "course": args.course,
        "td": args.td,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "quality_gate": {"clean": clean_gate, "garbled": garbled_gate},
        "usage": usage,
        "render": {"quick": quick, "detail": detail},
        "exercises": [e["no"] for e in data.get("exercises", [])],
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nDONE: quick={quick['pages']} pages, detail={detail['pages']} pages, "
          f"missing={quick['missing_chars'] + detail['missing_chars']}")
    return 0 if quick["missing_chars"] == 0 and detail["missing_chars"] == 0 else 3


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TD Radar M0")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo", help="run the offline M0 demo")
    p_demo.add_argument("--clean-pdf", default=r"C:\Users\admin\Documents\deepseek-harness\good-learning skill\Polynômes-多项式\Algèbre_TD1_c.pdf")
    p_demo.add_argument("--garbled-pdf", default=r"C:\Users\admin\Documents\deepseek-harness\good-learning skill\Séries-级数\TD2-cor.pdf")
    p_demo.add_argument("--course", default="Algèbre I")
    p_demo.add_argument("--td", default="TD1")
    p_demo.add_argument("--out", default=str(paths.OUT / "algebre_td1"))
    p_demo.add_argument("--model", default=None)
    p_demo.add_argument("--raw", default=None, help="replay a saved LLM JSON instead of calling the API")
    p_demo.set_defaults(func=demo)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
