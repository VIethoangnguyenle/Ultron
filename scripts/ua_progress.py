#!/usr/bin/env python3
"""Báo tiến độ 2 run Understand-Anything về DM Hoàng. Thuần stdlib, chống spam."""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SENDER = os.path.join(SCRIPTS, "gchat_send_text.py")
SPACE = "spaces/0dniIqAAAAE"
STATE = os.path.expanduser("~/.hermes/state/ua_progress.json")
BASE = "/home/zane/Desktop/work/vietbank/vietbank-digital"
RUNS = [
    {"name": "ekyc", "repo": os.path.join(BASE, "viet-bank-omni-ekyc"), "log": "/tmp/ua_ekyc.log"},
    {"name": "omni", "repo": os.path.join(BASE, "vietbank-omni"), "log": "/tmp/ua_omni.log"},
]
QUIET_FROM, QUIET_TO = dt.time(7, 0), dt.time(22, 30)


def find_pid(repo):
    """PID của run UA cho repo. Nhận cả 2 cách chạy:
    `claude -p /understand <repo>` và `codex exec ... <repo>` (codex chỉ nhận qua
    đường dẫn repo nằm trong prompt, vì nó không có cờ /understand)."""
    esc = re.escape(repo)
    pats = [
        re.compile(r"claude\s+-p\s+[\"']?/understand\s+" + esc + r"(\s|\"|'|$)"),
        re.compile(r"codex\s+exec[\s\S]*?" + esc),
    ]
    try:
        out = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return None
    hits = []
    for line in out.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) < 2 or int(parts[0]) == os.getpid():
            continue
        if any(p.search(parts[1]) for p in pats):
            hits.append((int(parts[0]), parts[1]))
    for pid, cmd in hits:
        if cmd.startswith("claude") or cmd.startswith("codex"):
            return pid
    return hits[0][0] if hits else None


def count_files(path):
    if not os.path.isdir(path):
        return 0
    return sum(len(files) for _, _, files in os.walk(path))


def kg_stats(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return (-1, -1)
    return (len(data.get("nodes") or []), len(data.get("edges") or []))


def last_log_line(path):
    if not os.path.isfile(path):
        return "(chưa có log)"
    try:
        with open(path, "rb") as fh:
            tail = fh.read()[-8192:]
    except Exception:
        return "(không đọc được log)"
    lines = [l.strip() for l in tail.decode("utf-8", "replace").splitlines() if l.strip()]
    return lines[-1][:140] if lines else "(log rỗng)"


def collect():
    snap = []
    for run in RUNS:
        ua = os.path.join(run["repo"], ".ua")
        snap.append({
            "name": run["name"],
            "pid": find_pid(run["repo"]),
            "tmp": count_files(os.path.join(ua, "tmp")),
            "inter": count_files(os.path.join(ua, "intermediate")),
            "kg": kg_stats(os.path.join(ua, "knowledge-graph.json")),
            "log": last_log_line(run["log"]),
        })
    return snap


def signature(snap):
    return "|".join("%s:%s:%d:%d:%d" % (r["name"], r["pid"] or 0, r["tmp"], r["inter"], 1 if r["kg"] else 0)
                    for r in snap)


def render(snap, done=False):
    now = dt.datetime.now().strftime("%H:%M")
    head = "✅ UA xong — cả 2 run đã dừng (%s)" % now if done else "📊 Tiến độ UA lúc %s" % now
    lines = [head]
    for r in snap:
        state = "▶️ đang chạy" if r["pid"] else "⏹️ đã dừng"
        if r["kg"] is None:
            kg = "KG: chưa có"
        elif r["kg"][0] < 0:
            kg = "KG: lỗi đọc"
        else:
            kg = "KG: %d nodes / %d edges" % r["kg"]
        lines.append("• %s: %s | tmp %d | inter %d | %s" % (r["name"], state, r["tmp"], r["inter"], kg))
    lines.append("📝 %s: %s" % (snap[0]["name"], snap[0]["log"]))
    lines.append("📝 %s: %s" % (snap[1]["name"], snap[1]["log"]))
    return "\n".join(lines)


def load_state():
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"sig": "", "same": 0, "quiet": False}


def save_state(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)


def send(text, dry_run):
    if dry_run:
        print("--- DRY RUN: sẽ gửi tới %s ---\n%s" % (SPACE, text))
        return
    subprocess.run([sys.executable, SENDER, "--space", SPACE, "--text", text], check=False)


def main():
    ap = argparse.ArgumentParser(description="Báo tiến độ Understand-Anything về DM Hoàng")
    ap.add_argument("--dry-run", action="store_true", help="chỉ in ra stdout, không gửi tin thật")
    ap.add_argument("--force", action="store_true", help="gửi dù chữ ký không đổi / ngoài khung giờ")
    args = ap.parse_args()

    now = dt.datetime.now().time()
    if not args.force and not (QUIET_FROM <= now <= QUIET_TO):
        print("Ngoài khung 07:00-22:30 → im lặng.")
        return

    state = load_state()
    if state.get("quiet") and not args.force:
        print("Đã chốt UA xong (quiet=true) → im lặng.")
        return

    snap = collect()
    sig = signature(snap)
    changed = sig != state.get("sig", "")
    state["same"] = 0 if changed else state.get("same", 0) + 1
    state["sig"] = sig
    all_stopped = all(r["pid"] is None for r in snap)
    finish = all_stopped and not changed and state["same"] >= 3

    if changed or args.force or finish:
        send(render(snap, done=finish), args.dry_run)
        if finish:
            state["quiet"] = True
    else:
        print("Chữ ký không đổi (lượt %d) → không gửi." % state["same"])

    if not args.dry_run:
        save_state(state)


if __name__ == "__main__":
    main()
