# -*- coding: utf-8 -*-
"""TD Radar console entrypoint (dev + PyInstaller)."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

import canvas  # noqa: E402
import notify  # noqa: E402
import paths  # noqa: E402
import pipeline  # noqa: E402
import scheduler  # noqa: E402
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
    sub.add_parser("setup", help="interactive first-run configuration")

    pc = sub.add_parser("canvas", help="Canvas list/poll/download")
    pc.add_argument("canvas_args", nargs=argparse.REMAINDER)

    pg = sub.add_parser("generate", help="PDF -> quality gate -> LLM -> detail PDF")
    pg.add_argument("--pdf", required=True)
    pg.add_argument("--course", required=True)
    pg.add_argument("--td", required=True)
    pg.add_argument("--out", default=None)
    pg.add_argument("--model", default=None)
    pg.add_argument("--max-tokens", type=int, default=None)

    ps = sub.add_parser("schedule", help="Windows Task Scheduler integration")
    pss = ps.add_subparsers(dest="schedule_cmd", required=True)
    pss.add_parser("show", help="print the effective schedule config")
    pss.add_parser("install", help="create/replace the scheduled task")
    pss.add_parser("uninstall", help="remove the scheduled task")
    pss.add_parser("status", help="show task state and next run")
    pss.add_parser("ensure", help="install only if missing")
    pend = pss.add_parser("set", help="edit schedule values, then save")
    pend.add_argument("--time", default=None, help="HH:MM start on the main weekdays")
    pend.add_argument("--weekdays", default=None, help="comma list: MON,TUE,...")
    pend.add_argument("--interval-minutes", type=int, default=None,
                      help="0 = once per day")
    pend.add_argument("--until", default=None, help="HH:MM stop repeating")
    pend.add_argument("--other-days-time", default=None, help="HH:MM or empty")
    pend.add_argument("--task-name", default=None)
    pend.add_argument("--command", default=None)
    pend.add_argument("--arguments", default=None)

    pn = sub.add_parser("notify", help="test notification channels")
    pns = pn.add_subparsers(dest="notify_cmd", required=True)
    pnt = pns.add_parser("test", help="send a test text (+ optional PDF)")
    pnt.add_argument("--file", default=None, help="PDF to attach; default: latest td_detail.pdf")

    args = p.parse_args(argv)
    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "setup":
        return setup_cmd()
    if args.cmd == "canvas":
        return canvas.main(args.canvas_args)
    if args.cmd == "generate":
        meta = pipeline.process_pdf(args.pdf, args.course, args.td,
                                    out_dir=args.out, model=args.model,
                                    max_tokens=args.max_tokens)
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "schedule":
        return schedule_cmd(args)
    if args.cmd == "notify":
        return notify_cmd(args)
    return 2


def _ask(label: str, current: str = "", secret: bool = False) -> str:
    suffix = "（已有，回车保留）" if current else ""
    try:
        value = (getpass.getpass(f"{label}{suffix}: ") if secret
                 else input(f"{label}{suffix}: "))
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("cancelled")
    value = value.strip()
    return value or current


def setup_cmd() -> int:
    print(f"data dir: {paths.DATA_DIR}")
    print("直接回车 = 保留已有值\n")

    old_token = ""
    if paths.TOKEN.exists():
        old_token = paths.TOKEN.read_text(encoding="utf-8", errors="replace").strip()
    token = _ask("Canvas token", old_token, secret=True)
    if not token:
        print("Canvas token 为空，已取消")
        return 1
    paths.TOKEN.write_text(token + "\n", encoding="utf-8")

    old_llm = {}
    if paths.LLM_CONFIG.exists():
        try:
            old_llm = json.loads(paths.LLM_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            old_llm = {}
    base = _ask("DeepSeek base_url", old_llm.get("base_url", "https://api.deepseek.com"))
    model = _ask("model", old_llm.get("model", "deepseek-flash"))
    key = _ask("API key", old_llm.get("api_key", ""), secret=True)
    max_tokens = _ask("max_tokens", str(old_llm.get("max_tokens", 100000)))
    llm = {
        "base_url": base,
        "api_key": key,
        "model": model,
        "max_tokens": int(max_tokens or 100000),
        "timeout": int(old_llm.get("timeout", 180)),
        "reasoning_effort": old_llm.get("reasoning_effort"),
    }
    paths.LLM_CONFIG.write_text(json.dumps(llm, ensure_ascii=False, indent=2),
                                encoding="utf-8")

    old_notify = notify.load_config()
    webhook = _ask("企业微信消息推送 webhook（可留空）",
                   old_notify.get("wecom_webhook", ""), secret=True)
    if webhook and "PASTE" not in webhook:
        old_notify.update({
            "enabled": True,
            "provider": "wecom",
            "wecom_webhook": webhook,
            "send_file": True,
        })
        (paths.DATA_DIR / "notify.json").write_text(
            json.dumps(old_notify, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n已写入：")
    print(f"  {paths.TOKEN}")
    print(f"  {paths.LLM_CONFIG}")
    if webhook and "PASTE" not in webhook:
        print(f"  {paths.DATA_DIR / 'notify.json'}")
    print("\n下一步：tdradar doctor")
    return 0


def latest_pdf() -> str | None:
    roots = [paths.DATA_DIR / "out", paths.OUT]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(root.rglob("td_detail.pdf"))
    if not files:
        return None
    return str(max(files, key=lambda p: p.stat().st_mtime))


def notify_cmd(args) -> int:
    if args.notify_cmd != "test":
        return 2
    cfg = notify.load_config()
    if not cfg.get("enabled"):
        print("notify disabled (check data/notify.json)")
        return 1
    file = args.file or latest_pdf()
    result = notify.send("TD Radar 测试", "通知通道测试：如果你看到这条，说明已经通了。",
                         file=file, cfg=cfg)
    print(json.dumps({"file": file, "result": result}, ensure_ascii=False, indent=2))
    return 0


def schedule_cmd(args) -> int:
    cfg = scheduler.load_schedule()
    cmd = args.schedule_cmd
    if cmd == "show":
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        print(f"config file: {scheduler.SCHEDULE_PATH}")
        return 0
    if cmd == "set":
        t = cfg["trigger"]
        if args.time:
            t["time"] = args.time
        if args.weekdays is not None:
            t["weekdays"] = [d.strip().upper() for d in args.weekdays.split(",") if d.strip()]
        if args.interval_minutes is not None:
            t["interval_minutes"] = args.interval_minutes
        if args.until:
            t["until"] = args.until
        if args.other_days_time is not None:
            t["other_days_time"] = args.other_days_time
        if args.task_name:
            cfg["task_name"] = args.task_name
        if args.command:
            cfg["command"] = args.command
        if args.arguments:
            cfg["arguments"] = args.arguments
        path = scheduler.save_schedule(cfg)
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        print(f"saved: {path}")
        if scheduler.status(cfg).get("installed"):
            print("task was installed; run `tdradar schedule install` to apply the change")
        return 0
    if cmd == "install":
        name = scheduler.install(cfg)
        print(f"installed: {name}")
        print(json.dumps(scheduler.status(cfg), ensure_ascii=False, indent=2))
        return 0
    if cmd == "uninstall":
        scheduler.uninstall(cfg)
        print("removed")
        return 0
    if cmd == "ensure":
        info = scheduler.status(cfg)
        if info.get("installed"):
            print(f"already installed: {cfg['task_name']} ({info.get('state')})")
            return 0
        name = scheduler.install(cfg)
        print(f"installed: {name}")
        return 0
    if cmd == "status":
        print(json.dumps(scheduler.status(cfg), ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
