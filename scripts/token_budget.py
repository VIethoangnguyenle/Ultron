#!/usr/bin/env python3
"""Watchdog ngân sách token — chạy bằng cron no_agent (KHÔNG tốn token).

VÌ SAO CẦN: thủ phạm đốt token lớn nhất không phải cron mà là SESSION CHAT SỐNG LÂU — mỗi lượt
Hermes gửi lại toàn bộ ngữ cảnh, nên 1 session vài trăm lượt × ~120k token là hàng trăm triệu
token cộng dồn.

NGUỒN SỐ LIỆU: log `~/.hermes/logs/agent.log*` là nguồn chính, vì nó ghi token theo NGÀY PHÁT
SINH THẬT của từng lượt API. Bảng `sessions` trong state.db chỉ cho con số CỘNG DỒN từ lúc mở
session, nên lọc theo `started_at` sẽ bỏ sót đúng những session sống lâu — ca đắt tiền nhất.
Log có xoay vòng nên số theo log là MỨC SÀN (phần cũ đã bị xoá); DB dùng để đối chiếu cộng dồn.

Script này làm 3 việc:
  1. Tính token theo ngày từ log (tổng ngày + top session của ngày) + đối chiếu cộng dồn trong DB.
  2. Ghi báo cáo ~/.hermes/reports/token_budget.md (đọc lại khi cần).
  3. VƯỢT NGƯỠNG → ghi 1 file escalate cho Hoàng (tối đa 1 lần/ngưỡng/ngày, không spam).

Im lặng khi mọi thứ bình thường. Chạy: mỗi 30 phút qua cron `ultron-token-budget`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import io
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

HH = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
DB = HH / "state.db"
LOG_DIR = HH / "logs"
LOG_GLOB = "agent.log*"
REPORT = HH / "reports" / "token_budget.md"
STATE = HH / "token_budget_state.json"
OVERRIDES = HH / "token_budget_overrides.json"
ESCALATIONS = HH / "escalations"

# Ngưỡng (chỉnh ở đây khi cần siết/nới)
SESSION_ALERT_TOKENS = 15_000_000    # 1 session cộng dồn quá mức này → báo
SESSION_ALERT_CALLS = 150            # hoặc quá nhiều lượt API → báo
DAY_INPUT_ALERT_TOKENS = 60_000_000  # tổng input cả ngày (theo log) vượt mức này → báo
HIGH_AVG_PER_CALL = 80_000           # ngữ cảnh/lượt quá cao = dấu hiệu session phình
LONG_LIVED_WINDOW_S = 24 * 3600      # "còn hoạt động" = có hoạt động trong 24h gần đây
TOP_N = 5

# 2026-09-14 17:47:34,385 INFO [20260914_174622_484cc5cb] agent.conversation_loop:
#   API call #13: model=... provider=custom in=56881 out=169 total=57050 latency=5.9s id=...
LOG_RE = re.compile(
    r"^(?P<day>\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2},\d+ \s*\w+ \s*"
    r"\[(?P<sid>[^\]]+)\].*?API call #\d+:.*?\bin=(?P<in>\d+)\b.*?\bout=(?P<out>\d+)\b"
)


def today() -> str:
    return dt.date.today().isoformat()


def load_state() -> dict:
    if not STATE.exists():
        return {"alerts": {}}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"alerts": {}}


def save_state(st: dict) -> None:
    try:
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def day_threshold(day: str) -> tuple[int, bool]:
    """Ngưỡng token hiệu dụng của MỘT ngày: trả (ngưỡng, có override hay không).

    File `token_budget_overrides.json` dạng {"2026-09-15": 120000000} — khoá là ngày ISO,
    giá trị là số token. Thiếu file / JSON hỏng / kiểu sai / giá trị <= 0 đều rơi về hằng
    mặc định. Hàm này chạy trong cron nên TUYỆT ĐỐI không ném exception.
    """
    try:
        raw = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DAY_INPUT_ALERT_TOKENS, False
    if not isinstance(raw, dict):
        return DAY_INPUT_ALERT_TOKENS, False
    val = raw.get(day)
    if isinstance(val, bool) or not isinstance(val, int) or val <= 0:
        return DAY_INPUT_ALERT_TOKENS, False
    return val, True


def prune_overrides(day: str) -> None:
    """Dọn các ngày đã qua khỏi file override; chỉ ghi lại khi thật sự có thay đổi."""
    try:
        raw = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(raw, dict):
        return
    kept = {k: v for k, v in raw.items() if not (isinstance(k, str) and k < day)}
    if len(kept) == len(raw):
        return
    try:
        OVERRIDES.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError):
        pass


def open_log(path: Path) -> io.TextIOBase:
    if path.name.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def scan_logs(day: str) -> dict:
    """Quét toàn bộ agent.log* → token của NGÀY `day`, tách theo session.

    Chỉ đếm dòng khớp LOG_RE; dòng khác (background_review, lỗi, traceback) bỏ qua.
    """
    per_session: dict[str, dict] = {}
    tot_in = tot_out = calls = 0
    files = sorted(LOG_DIR.glob(LOG_GLOB)) if LOG_DIR.exists() else []
    for path in files:
        try:
            with open_log(path) as fh:
                for line in fh:
                    m = LOG_RE.match(line)
                    if not m or m.group("day") != day:
                        continue
                    sid = m.group("sid")
                    n_in, n_out = int(m.group("in")), int(m.group("out"))
                    s = per_session.setdefault(sid, {"id": sid, "input": 0, "output": 0, "calls": 0})
                    s["input"] += n_in
                    s["output"] += n_out
                    s["calls"] += 1
                    tot_in += n_in
                    tot_out += n_out
                    calls += 1
        except OSError:
            continue
    for s in per_session.values():
        s["avg"] = int(s["input"] / s["calls"]) if s["calls"] else 0
    ranked = sorted(per_session.values(), key=lambda s: -s["input"])
    return {"input": tot_in, "output": tot_out, "calls": calls, "sessions": len(per_session),
            "per_session": per_session, "ranked": ranked,
            "files": [p.name for p in files]}


def load_db_sessions() -> dict[str, dict]:
    """Toàn bộ session trong DB (KHÔNG lọc theo ngày mở) — dùng để đối chiếu cộng dồn."""
    if not DB.exists():
        return {}
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    out: dict[str, dict] = {}
    for sid, src, ct, st_at, la, ea, it, ot, cr, mc, ac, title, chat in con.execute(
            "select id, source, chat_type, started_at, last_activity_at, ended_at, input_tokens,"
            " output_tokens, cache_read_tokens, message_count, api_call_count, title, chat_id"
            " from sessions"):
        out[sid] = {"id": sid, "source": src or "", "chat_type": ct or "", "started_at": st_at or 0,
                    "active_at": max(la or 0, ea or 0, st_at or 0), "ended_at": ea,
                    "input": it or 0, "output": ot or 0, "cache": cr or 0, "msgs": mc or 0,
                    "calls": ac or 0, "title": (title or "")[:60], "chat": chat or ""}
    con.close()
    for s in out.values():
        s["avg"] = int(s["input"] / s["calls"]) if s["calls"] else 0
    return out


def long_lived(db: dict[str, dict], now: float) -> list[dict]:
    """Session sống quá lâu: cộng dồn nặng VÀ còn hoạt động trong 24h gần đây.

    Xét TOÀN BỘ session trong DB — không lọc theo ngày mở, vì đúng session mở từ hôm trước
    mới là loại bị bỏ sót ở bản cũ.
    """
    heavy = [s for s in db.values()
             if s["input"] >= SESSION_ALERT_TOKENS or s["calls"] >= SESSION_ALERT_CALLS]
    recent = [s for s in heavy if now - s["active_at"] <= LONG_LIVED_WINDOW_S]
    return sorted(recent, key=lambda s: -s["input"])


def collect() -> dict:
    d = today()
    log = scan_logs(d)
    db = load_db_sessions()
    now = dt.datetime.now().timestamp()
    for s in log["ranked"]:
        s["db"] = db.get(s["id"])
    db_today = [s for s in db.values()
                if dt.datetime.fromtimestamp(s["started_at"]).strftime("%Y-%m-%d") == d]
    return {"ok": bool(log["files"]) or bool(db), "why": "không thấy log lẫn state.db",
            "day": d, "log": log, "db": db, "db_today": db_today,
            "long_lived": long_lived(db, now),
            "bloat": [s for s in log["ranked"]
                      if s["avg"] >= HIGH_AVG_PER_CALL and s["input"] >= 2_000_000]}


def label(s: dict | None) -> str:
    if not s:
        return "(không có trong DB)"
    kind = s["chat_type"] or s["source"] or "?"
    return f"{kind} · {s['title'] or '(chưa đặt tên)'}"


def render(d: dict) -> str:
    log = d["log"]
    limit, overridden = day_threshold(d["day"])
    db_in = sum(s["input"] for s in d["db_today"])
    L = [f"# Ngân sách token — {d['day']}", "",
         "> Số theo log là **mức sàn**: `agent.log*` xoay vòng nên phần cũ đã bị xoá.",
         "> Đo theo NGÀY PHÁT SINH của từng lượt API, không lọc theo ngày mở session.", "",
         f"- input tổng (log): {log['input']:,}",
         f"- output tổng (log): {log['output']:,}",
         f"- lượt API: {log['calls']:,} · {log['sessions']} session có hoạt động",
         f"- đối chiếu DB (chỉ session MỞ hôm nay): {db_in:,} tok · {len(d['db_today'])} session",
         f"- ngưỡng ngày hiệu dụng: {limit:,} token "
         f"({'override riêng của ngày' if overridden else 'mặc định'})",
         "", "## Top session đốt nhất (trong ngày)", ""]
    if not log["ranked"]:
        L.append("- (không có lượt API nào trong log hôm nay)")
    for s in log["ranked"][:TOP_N]:
        db = s["db"]
        L.append(f"- {s['input']:,} tok · {s['calls']} lượt · ~{s['avg']:,} tok/lượt · "
                 f"{label(db)} · `{s['id']}`")
        cum = f"{db['input']:,} tok / {db['calls']} lượt" if db else "không có bản ghi"
        L.append(f"  - tích luỹ trong DB: {cum}")

    L += ["", "## ⚠️ Session sống quá lâu (nên mở session mới)", ""]
    if not d["long_lived"]:
        L.append("- (không có)")
    for s in d["long_lived"]:
        seen = dt.datetime.fromtimestamp(s["active_at"]).strftime("%d/%m %H:%M")
        L.append(f"- {s['input']:,} tok tích luỹ · {s['calls']} lượt · ~{s['avg']:,} tok/lượt · "
                 f"{label(s)} · hoạt động cuối {seen} · `{s['id']}`")
        L.append("  - gợi ý: chốt việc rồi gõ `/new` để mở session mới")

    if d["bloat"]:
        L += ["", "## ⚠️ Session có ngữ cảnh phình (trong ngày)", ""]
        for s in d["bloat"]:
            L.append(f"- ~{s['avg']:,} tok/lượt · {s['input']:,} tok trong ngày · "
                     f"{label(s['db'])} · `{s['id']}`")
    return "\n".join(L) + "\n"


def write_report(text: str) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")


def silent_mode() -> bool:
    """Máy không phải của Hoàng (vd máy Kitty): chỉ ghi báo cáo, KHÔNG ghi escalate
    để khỏi ping nhầm chủ máy. Bật bằng env TOKEN_BUDGET_SILENT=1 hoặc file cờ."""
    if os.environ.get("TOKEN_BUDGET_SILENT") in {"1", "true", "yes"}:
        return True
    return (HH / "token_budget_silent.flag").exists()


def escalate(question: str, reason: str) -> None:
    """Ghi 1 file escalate. Tên file có microsecond vì một lượt chạy có thể bắn nhiều cảnh
    báo trong cùng một giây — dùng giây không thôi là file sau đè file trước."""
    if silent_mode():
        return
    ESCALATIONS.mkdir(parents=True, exist_ok=True)
    p = ESCALATIONS / f"token_budget_{dt.datetime.now():%Y%m%d_%H%M%S_%f}.json"
    p.write_text(json.dumps({"from": "Ultron (watchdog token)", "space": "(hệ thống)",
                             "question": question, "reason": reason}, ensure_ascii=False, indent=2),
                 encoding="utf-8")


def check_alerts(d: dict, dry_run: bool) -> list[str]:
    st = load_state()
    st.setdefault("alerts", {})
    day = d["day"]
    done = st["alerts"].setdefault(day, [])
    log = d["log"]
    fired: list[str] = []

    limit, overridden = day_threshold(day)
    note = " (ngưỡng riêng của ngày)" if overridden else ""
    heaviest = log["ranked"][0] if log["ranked"] else None
    if log["input"] > limit and "day" not in done:
        top = (f" Nặng nhất: {heaviest['input']:,} tok / {heaviest['calls']} lượt — "
               f"{label(heaviest['db'])}." if heaviest else "")
        msg = (f"⚠️ Token hôm nay ({day}) đã vượt ngưỡng {limit:,}{note}: {log['input']:,} "
               f"token vào qua {log['calls']:,} lượt API (số theo log, là mức sàn).{top} "
               f"Đề xuất: chốt việc rồi gõ `/new` để mở session mới.")
        if not dry_run:
            escalate(msg, f"ngưỡng ngày {limit:,} token{note}")
            done.append("day")
        fired.append("day")

    for s in d["long_lived"]:
        key = f"session:{s['id']}"
        if key in done:
            continue
        msg = (f"⚠️ Session sống quá lâu, đang đốt token: {s['input']:,} token tích luỹ, "
               f"{s['calls']} lượt API (~{s['avg']:,} token/lượt) — {label(s)}. "
               f"Đề xuất: chốt việc rồi gõ `/new` để mở session mới.")
        if not dry_run:
            escalate(msg, f"session vượt {SESSION_ALERT_TOKENS:,} token hoặc "
                          f"{SESSION_ALERT_CALLS} lượt")
            done.append(key)
        fired.append(key)

    if not dry_run:
        save_state(st)
    return fired


def main() -> int:
    ap = argparse.ArgumentParser(description="Watchdog ngân sách token Hermes")
    ap.add_argument("--dry-run", action="store_true",
                    help="chỉ in ra màn hình, KHÔNG ghi report/state/escalate")
    ap.add_argument("--deliver", default=None, help="(tương thích cron, không dùng)")
    args, _unknown = ap.parse_known_args()

    d = collect()
    if not args.dry_run:
        prune_overrides(d["day"])
    if not d["ok"]:
        print(f"token-budget: {d['why']}")
        return 0

    text = render(d)
    if args.dry_run:
        print(text)
    else:
        write_report(text)

    fired = check_alerts(d, args.dry_run)
    log = d["log"]
    limit, overridden = day_threshold(d["day"])
    top = log["ranked"][0] if log["ranked"] else None
    line = (f"token-budget {d['day']}: input={log['input']:,} output={log['output']:,} · "
            f"{log['calls']:,} lượt · {log['sessions']} session" +
            (f" · nặng nhất={top['input']:,} `{top['id']}`" if top else "") +
            f" · ngưỡng ngày={limit:,} ({'override' if overridden else 'mặc định'})")
    print(line)
    print(f"  → sống quá lâu: {len(d['long_lived'])} session (mức sàn theo log, DB là cộng dồn)")
    if fired:
        verb = "SẼ báo" if args.dry_run else "đã báo"
        print(f"  → {verb} Hoàng: {', '.join(fired)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
