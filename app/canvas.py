# -*- coding: utf-8 -*-
"""Canvas poller: discover TD files and download signed URLs.

Typical use:
  python app/canvas.py list
  python app/canvas.py poll --once --bootstrap   # first run: mark current, no download
  python app/canvas.py poll --once --download    # later: download newly discovered
  python app/canvas.py poll --interval 300 --download
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

import paths

BASE = "https://oc.sjtu.edu.cn/api/v1"
COURSES = {
    95175: ("algebre", "Algèbre I"),
    95173: ("series", "Séries"),
    95166: ("physique1", "Physique (1)"),
    95168: ("physique2", "Physique (2)"),
}

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with (paths.LOGS / "canvas_poll.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def token() -> str:
    raw = paths.TOKEN.read_text(encoding="utf-8", errors="replace").strip()
    if not raw or "PASTE" in raw:
        raise SystemExit(f"empty/placeholder token: {paths.TOKEN}")
    return raw


def api_get(path: str) -> dict:
    req = urllib.request.Request(
        BASE + path,
        headers={"Authorization": "Bearer " + token(), "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def normalize(name: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(ch)
    )


def match_file(name: str) -> tuple[str, str] | None:
    n = normalize(name)
    m = re.match(r"^PHY2301P_P2025_TD(\d+)_(questions|solutions)\.pdf$", n, re.I)
    if m:
        return f"TD{m.group(1)}", "sujet" if m.group(2).lower() == "questions" else "corrige"
    m = re.match(r"^Sujet_TD(\d+)\.pdf$", n, re.I)
    if m:
        return f"TD{m.group(1)}", "sujet"
    m = re.match(r"^Algebre_TD(\d+)_(e|c)\.pdf$", n, re.I)
    if m:
        return f"TD{m.group(1)}", "sujet" if m.group(2).lower() == "e" else "corrige"
    m = re.match(r"^TD(\d+)-(.+)\.pdf$", n, re.I)
    if m:
        suffix = m.group(2).lower()
        return f"TD{m.group(1)}", "corrige" if "cor" in suffix else "sujet"
    return None


def discover(course_id: int) -> list[dict]:
    files = api_get(f"/courses/{course_id}/files?per_page=100&sort=updated_at&order=desc")
    out = []
    for f in files:
        name = str(f.get("display_name") or f.get("filename") or "")
        parsed = match_file(name)
        if not parsed:
            continue
        td, kind = parsed
        out.append({
            "course_id": course_id,
            "course_key": COURSES.get(course_id, (str(course_id), str(course_id)))[0],
            "id": f.get("id"),
            "name": name,
            "td": td,
            "kind": kind,
            "size": f.get("size"),
            "updated_at": f.get("updated_at"),
            "url": f.get("url"),
        })
    return out


def load_state() -> dict:
    if paths.STATE.exists():
        try:
            data = json.loads(paths.STATE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("files"), dict):
                for entry in data["files"].values():
                    if "baseline" not in entry and not entry.get("downloaded"):
                        entry["baseline"] = True
                return data
        except Exception:
            pass
    return {"version": 1, "files": {}}


def save_state(state: dict) -> None:
    tmp = paths.STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(paths.STATE)


def safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "file.pdf"


def download(f: dict) -> Path:
    target = paths.CANVAS_INBOX / f["course_key"] / f["td"] / safe_name(f["name"])
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size == f.get("size"):
        log(f"skip existing {target}")
        return target
    url = f.get("url")
    if not url:
        detail = api_get(f"/files/{f['id']}")
        url = detail.get("url")
    if not url:
        raise RuntimeError(f"no download URL for {f['name']}")
    # Signed Canvas URL must be fetched WITHOUT Authorization.
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    tmp = target.with_suffix(target.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(target)
    log(f"downloaded {target} ({len(data)} bytes)")
    return target


def run_once(download_new: bool = False, bootstrap: bool = False,
             force: bool = False) -> list[dict]:
    state = load_state()
    changed = False
    new_items = []
    for cid in COURSES:
        try:
            files = discover(cid)
        except Exception as exc:  # noqa: BLE001
            log(f"course {cid} discover failed: {exc}")
            continue
        for f in files:
            key = f"{cid}:{f['id']}"
            old = state["files"].get(key)
            is_new = old is None
            changed = old is not None and old.get("updated_at") != f["updated_at"]
            if is_new or changed:
                new_items.append(f)
            if bootstrap and not force:
                if is_new:
                    log(f"baseline {COURSES[cid][1]} {f['td']} {f['kind']} {f['name']}")
                state["files"][key] = {
                    "course_id": cid, "file_id": f["id"], "name": f["name"],
                    "td": f["td"], "kind": f["kind"], "updated_at": f["updated_at"],
                    "downloaded": bool(old and old.get("downloaded")),
                    "baseline": True,
                }
                changed = True
                continue
            if download_new and (
                is_new or changed or force or
                (old is not None and not old.get("downloaded") and not old.get("baseline"))
            ):
                try:
                    target = download(f)
                    state["files"][key] = {
                        "course_id": cid, "file_id": f["id"], "name": f["name"],
                        "td": f["td"], "kind": f["kind"], "updated_at": f["updated_at"],
                        "downloaded": True, "baseline": False, "path": str(target),
                    }
                    changed = True
                except Exception as exc:  # noqa: BLE001
                    log(f"download failed {f['name']}: {exc}")
            elif is_new or changed:
                log(f"new/updated (not downloaded) {COURSES[cid][1]} {f['td']} {f['kind']} {f['name']}")
                state["files"][key] = {
                    "course_id": cid, "file_id": f["id"], "name": f["name"],
                    "td": f["td"], "kind": f["kind"], "updated_at": f["updated_at"],
                    "downloaded": False, "baseline": False,
                }
                changed = True
    if changed:
        save_state(state)
    log(f"poll done; {len(new_items)} new item(s)")
    return new_items


def cmd_list(_args) -> int:
    for cid, (_, label) in COURSES.items():
        try:
            files = discover(cid)
        except Exception as exc:  # noqa: BLE001
            print(f"{label}: ERROR {exc}")
            continue
        print(f"\n{label} ({cid}) — {len(files)} TD file(s)")
        for f in files:
            print(f"  {f['td']:4} {f['kind']:7} {f['updated_at']} {f['size']:>9} {f['name']}")
    return 0


def cmd_download(args) -> int:
    state = load_state()
    files = []
    for cid in ([args.course] if args.course else COURSES):
        files.extend(discover(cid))
    hits = [f for f in files if args.match.lower() in normalize(f["name"]).lower()]
    if not hits:
        print("no matching file")
        return 1
    for f in hits:
        target = download(f)
        state["files"][f"{f['course_id']}:{f['id']}"] = {
            "course_id": f["course_id"], "file_id": f["id"], "name": f["name"],
            "td": f["td"], "kind": f["kind"], "updated_at": f["updated_at"],
            "downloaded": True, "baseline": False, "path": str(target),
        }
    save_state(state)
    return 0


def cmd_poll(args) -> int:
    while True:
        run_once(download_new=args.download, bootstrap=args.bootstrap, force=args.force)
        if args.once:
            return 0
        time.sleep(max(30, args.interval))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="TD Radar Canvas poller")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="list matching TD files")
    pl.set_defaults(func=cmd_list)

    pp = sub.add_parser("poll", help="poll Canvas and optionally download")
    pp.add_argument("--once", action="store_true")
    pp.add_argument("--interval", type=int, default=300)
    pp.add_argument("--download", action="store_true")
    pp.add_argument("--bootstrap", action="store_true", help="mark current files as seen, no download")
    pp.add_argument("--force", action="store_true", help="download even if already seen")
    pp.set_defaults(func=cmd_poll)

    pd = sub.add_parser("download", help="download files matching a name substring")
    pd.add_argument("--course", type=int, default=None)
    pd.add_argument("--match", required=True)
    pd.set_defaults(func=cmd_download)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
