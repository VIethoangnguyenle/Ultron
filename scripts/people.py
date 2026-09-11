#!/usr/bin/env python3
"""People registry — what Ultron remembers about the colleagues it works with.

Store: ~/.hermes/people.json  (one file, atomic writes, mode 600)

  {
    "spaces": {"spaces/XXX": "Label"},
    "people": {
      "users/123": {
        "name": "Hoàng, Nguyễn Lê Việt (KCN, DVNH)",
        "call": "Hoàng",                       # how to address them in chat
        "role": "KCN, DVNH",
        "seat": "ROLE_MANAGER|ROLE_MEMBER",     # from the Chat API, when known
        "groups": ["spaces/XXX"],
        "how": "",                              # tone / preferences learned over time
        "tags": [],
        "first_seen": "2026-09-10",
        "notes": [{"at": "2026-09-10", "text": "..."}]
      }
    }
  }

Commands:
  people.py sync [--space spaces/X ...]     pull members from tracked spaces (NEVER clobbers notes)
  people.py list [--group spaces/X] [--json]
  people.py show <id|name-substring>
  people.py note <id|name-substring> "text" [--at YYYY-MM-DD]
  people.py set  <id|name-substring> [--role "..."] [--how "..."] [--call "..."] [--tag x]...
"""
import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
STORE = HOME / "people.json"
SA_PATH = HOME / "google-chat-sa.json"
DEFAULT_SPACES = {
    "spaces/AAQASaFjh6M": "Agent Space",
    "spaces/AAAADv4ib6s": "VietBank SME (dev/test)",
    "spaces/AAQAiOgBqio": "Những chú chồn ăn dưa (test riêng của Hoàng)",
}


def load() -> dict:
    if STORE.exists():
        try:
            data = json.loads(STORE.read_text(encoding="utf-8"))
            data.setdefault("spaces", {})
            data.setdefault("people", {})
            return data
        except Exception as exc:
            print(f"WARN: people.json unreadable ({exc}); starting fresh", file=sys.stderr)
    return {"spaces": dict(DEFAULT_SPACES), "people": {}}


def save(data: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(STORE)


def call_name(display: str) -> str:
    """'Hoàng, Nguyễn Lê Việt (KCN, DVNH)' -> 'Hoàng' (the given name people actually use)."""
    head = (display or "").split(",")[0].strip()
    return head.split()[0] if head else ""


def find(data: dict, needle: str):
    """Resolve an id or a name to (key, person). Exact id → exact call → unique substring."""
    people = data["people"]
    if needle in people:
        return needle, people[needle]
    low = needle.lower().strip()
    exact = [(k, p) for k, p in people.items() if (p.get("call") or "").lower() == low]
    if len(exact) == 1:
        return exact[0]
    hits = exact or [(k, p) for k, p in people.items()
                     if low in (p.get("name") or "").lower() or low in (p.get("call") or "").lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise SystemExit(f"no person matches {needle!r} — use the users/<id> instead")
    raise SystemExit(f"ambiguous for {needle!r} ({len(hits)} hits) — use the users/<id>: "
                     + ", ".join(f"{p.get('name')} [{k}]" for k, p in hits[:6]))


def cmd_add(args) -> int:
    """Create/overwrite a person who never shows up in members.list (apps/bots are omitted)."""
    data = load()
    p = data["people"].get(args.id) or {"first_seen": date.today().isoformat(), "notes": [], "tags": [], "groups": []}
    p["name"] = args.name
    p["call"] = args.call or call_name(args.name)
    if args.type:
        p["type"] = args.type
    if args.role is not None:
        p["role"] = args.role
    if args.how is not None:
        p["how"] = args.how
    if args.tag:
        p["tags"] = sorted(set((p.get("tags") or []) + args.tag))
    if args.group:
        p["groups"] = sorted(set((p.get("groups") or []) + args.group))
    data["people"][args.id] = p
    save(data)
    print(f"saved {args.name} [{args.id}]")
    return 0


def cmd_sync(args) -> int:
    if not SA_PATH.exists():
        print(f"ERROR: service account missing at {SA_PATH}", file=sys.stderr)
        return 2
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    data = load()
    spaces = dict(data["spaces"])
    if args.space:
        spaces = {s: spaces.get(s, s) for s in args.space}
    creds = service_account.Credentials.from_service_account_info(
        json.loads(SA_PATH.read_text(encoding="utf-8")),
        scopes=["https://www.googleapis.com/auth/chat.bot"])
    svc = build("chat", "v1", credentials=creds, cache_discovery=False)

    today = date.today().isoformat()
    added = updated = 0
    for space, label in spaces.items():
        try:
            resp = svc.spaces().members().list(parent=space, pageSize=200).execute()
        except Exception as exc:
            print(f"  ! {space}: {str(exc)[:120]}", file=sys.stderr)
            continue
        for m in resp.get("memberships", []):
            member = m.get("member") or {}
            uid = member.get("name") or ""
            if not uid.startswith("users/"):
                continue
            p = data["people"].get(uid)
            if p is None:
                p = {"first_seen": today, "notes": [], "tags": [], "groups": []}
                data["people"][uid] = p
                added += 1
            else:
                updated += 1
            if member.get("displayName"):
                p["name"] = member["displayName"]
                p["call"] = call_name(member["displayName"])
            p["type"] = member.get("type") or p.get("type", "")
            p["seat"] = m.get("role") or p.get("seat", "")
            if label and label not in p["groups"]:
                p["groups"] = sorted(set(p["groups"] + [f"{space} ({label})"]))
    save(data)
    print(f"synced: {len(spaces)} spaces | new {added}, existing {updated}, total {len(data['people'])}")
    return 0


def cmd_list(args) -> int:
    data = load()
    rows = []
    for uid, p in sorted(data["people"].items(), key=lambda kv: kv[1].get("name") or ""):
        if args.group and not any(args.group in g for g in p.get("groups") or []):
            continue
        if args.tag:
            have = {t.lower() for t in (p.get("tags") or [])}
            if not all(t.lower() in have for t in args.tag):
                continue
        if args.role and args.role.lower() not in (p.get("role") or "").lower():
            continue
        rows.append({"id": uid, **{k: p.get(k, "") for k in ("name", "call", "role", "seat", "type", "how")},
                     "groups": p.get("groups") or [],
                     "notes": len(p.get("notes") or []), "habits": len(p.get("habits") or [])})
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            extra = f" | {r['how'][:60]}" if r["how"] else ""
            print(f"{r['id']} | {r['name']} | {r['seat']}{extra} | notes:{r['notes']} habits:{r['habits']}")
    return 0


def cmd_show(args) -> int:
    data = load()
    uid, p = find(data, args.who)
    print(f"{uid}\n{json.dumps(p, ensure_ascii=False, indent=2)}")
    return 0


def cmd_note(args) -> int:
    data = load()
    uid, p = find(data, args.who)
    p.setdefault("notes", []).append({"at": args.at or date.today().isoformat(), "text": args.text})
    save(data)
    print(f"noted on {p.get('name')} [{uid}]: {args.text}")
    return 0


def cmd_habit(args) -> int:
    """Record an OBSERVED habit (a repeating pattern, not a one-off). Same text bumps the count."""
    data = load()
    uid, p = find(data, args.who)
    habits = p.setdefault("habits", [])
    today = args.at or date.today().isoformat()
    for h in habits:
        if (h.get("text") or "").strip().lower() == args.text.strip().lower():
            h["times"] = int(h.get("times", 1)) + 1
            h["last"] = today
            hit = h
            break
    else:
        hit = {"text": args.text, "times": 1, "first": today, "last": today}
        habits.append(hit)
    save(data)
    print(f"habit on {p.get('name')} [{uid}]: {args.text} (times={hit['times']}, last={hit['last']})")
    return 0


def cmd_todo(args) -> int:
    """Ai còn thiếu thông tin → để Ultron chủ động hỏi thăm bổ sung hồ sơ."""
    data = load()
    spaces = data.get("spaces", {})
    want = set(args.missing or ["role"])
    rows = []
    for uid, p in data["people"].items():
        if (p.get("type") or "HUMAN").upper() == "BOT" or "self" in (p.get("tags") or []):
            continue
        if args.group and args.group not in (p.get("groups") or []):
            continue
        miss = []
        if "role" in want and not (p.get("role") or "").strip():
            miss.append("chức danh")
        if "note" in want and not (p.get("notes") or []):
            miss.append("ghi chú")
        if not miss:
            continue
        rows.append({
            "id": uid,
            "name": p.get("name", ""),
            "groups": ", ".join(spaces.get(g, g) for g in (p.get("groups") or [])) or "-",
            "missing": miss,
        })
    rows.sort(key=lambda r: r["name"])
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    where = f" (nhóm {spaces.get(args.group, args.group)})" if args.group else ""
    print(f"{len(rows)} người còn thiếu thông tin{where}")
    for r in rows[: args.limit]:
        print(f"  {r['name']}  [{r['id']}]  thiếu: {','.join(r['missing'])}  • {r['groups']}")
    if len(rows) > args.limit:
        print(f"  … còn {len(rows) - args.limit} người nữa (dùng --limit để xem thêm)")
    return 0


def cmd_set(args) -> int:
    data = load()
    uid, p = find(data, args.who)
    for field in ("role", "how", "call"):
        val = getattr(args, field)
        if val is not None:
            p[field] = val
    if args.tag:
        p["tags"] = sorted(set((p.get("tags") or []) + args.tag))
    save(data)
    print(f"updated {p.get('name')} [{uid}]")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync"); s.add_argument("--space", action="append"); s.set_defaults(fn=cmd_sync)
    l = sub.add_parser("list"); l.add_argument("--group"); l.add_argument("--json", action="store_true")
    l.add_argument("--tag", action="append", help="chỉ lấy người có ĐỦ các tag này (repeatable)")
    l.add_argument("--role", help="lọc theo chuỗi trong role")
    l.set_defaults(fn=cmd_list)
    sh = sub.add_parser("show"); sh.add_argument("who"); sh.set_defaults(fn=cmd_show)
    n = sub.add_parser("note"); n.add_argument("who"); n.add_argument("text"); n.add_argument("--at"); n.set_defaults(fn=cmd_note)
    st = sub.add_parser("set"); st.add_argument("who")
    for f in ("role", "how", "call"):
        st.add_argument(f"--{f}")
    st.add_argument("--tag", action="append"); st.set_defaults(fn=cmd_set)
    a = sub.add_parser("add"); a.add_argument("id"); a.add_argument("--name", required=True)
    a.add_argument("--call"); a.add_argument("--type"); a.add_argument("--role"); a.add_argument("--how")
    a.add_argument("--group", action="append"); a.add_argument("--tag", action="append"); a.set_defaults(fn=cmd_add)
    hb = sub.add_parser("habit"); hb.add_argument("who"); hb.add_argument("text"); hb.add_argument("--at")
    hb.set_defaults(fn=cmd_habit)
    td = sub.add_parser("todo", help="ai còn thiếu chức danh/ghi chú để hỏi thăm")
    td.add_argument("--group"); td.add_argument("--missing", action="append", choices=["role", "note"])
    td.add_argument("--limit", type=int, default=25); td.add_argument("--json", action="store_true")
    td.set_defaults(fn=cmd_todo)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
