#!/usr/bin/env python3
"""Watchdog ngân sách token — chạy bằng cron no_agent (KHÔNG tốn token).

VÌ SAO CẦN: thủ phạm đốt token lớn nhất không phải cron mà là SESSION CHAT SỐNG LÂU — mỗi lượt
Hermes gửi lại toàn bộ ngữ cảnh, nên 1 session 718 lượt × ~190k token = 137M token. Đo thực tế
10-11/09/2026: 4 session >5M chiếm 86% tổng chi phí.

Script này làm 3 việc:
  1. Tính token hôm nay (tách tươi / cache / output) + top session đốt nhất.
  2. Ghi báo cáo ~/.hermes/reports/token_budget.md (đọc lại khi cần).
  3. VƯỢT NGƯỠNG → ghi 1 file escalate cho Hoàng (tối đa 1 lần/ngưỡng/ngày, không spam).

Im lặng khi mọi thứ bình thường. Chạy: mỗi 30 phút qua cron `ultron-token-budget`.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import sys
from pathlib import Path

HH = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
DB = HH / "state.db"
REPORT = HH / "reports" / "token_budget.md"
STATE = HH / "token_budget_state.json"
ESCALATIONS = HH / "escalations"

# Ngưỡng (chỉnh ở đây khi cần siết/nới)
SESSION_ALERT_TOKENS = 15_000_000   # 1 session cộng dồn quá mức này → báo
DAY_INPUT_ALERT_TOKENS = 60_000_000  # tổng input cả ngày vượt mức này → báo
HIGH_AVG_PER_CALL = 80_000           # ngữ cảnh/lượt quá cao = dấu hiệu session phình
TOP_N = 5


def today() -> str:
    return dt.date.today().isoformat()


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"alerts": {}}


def save_state(st: dict) -> None:
    try:
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def collect() -> dict:
    if not DB.exists():
        return {"ok": False, "why": "chưa có state.db"}
    con = sqlite3.connect(DB)
    d = today()
    rows = []
    for sid, src, ts, it, ot, cr, mc, ac, title, chat in con.execute(
            "select id, source, started_at, input_tokens, output_tokens, cache_read_tokens,"
            " message_count, api_call_count, title, chat_id from sessions"):
        day = dt.datetime.fromtimestamp(ts or 0).strftime("%Y-%m-%d")
        if day != d:
            continue
        rows.append({"id": sid, "source": src or "", "input": it or 0, "output": ot or 0,
                     "cache": cr or 0, "msgs": mc or 0, "calls": ac or 0,
                     "title": (title or "")[:60], "chat": chat or ""})
    tot_in = sum(r["input"] for r in rows)
    tot_cache = sum(r["cache"] for r in rows)
    tot_out = sum(r["output"] for r in rows)
    for r in rows:
        r["avg"] = int(r["input"] / r["calls"]) if r["calls"] else 0
    rows.sort(key=lambda r: -r["input"])
    return {"ok": True, "day": d, "sessions": len(rows), "input": tot_in, "cache": tot_cache,
            "output": tot_out, "fresh": tot_in - tot_cache, "top": rows[:TOP_N],
            "bloat": [r for r in rows if r["avg"] >= HIGH_AVG_PER_CALL and r["input"] >= 2_000_000]}


def write_report(d: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    L = [f"# Ngân sách token — {d['day']}", "",
         f"- session hôm nay: {d['sessions']}",
         f"- input tổng: {d['input']:,} (tươi {d['fresh']:,} · cache {d['cache']:,})",
         f"- output: {d['output']:,}", "", "## Top session đốt nhất", ""]
    for r in d["top"]:
        L.append(f"- {r['input']:,} tok · {r['msgs']} msgs · {r['calls']} lượt API · "
                 f"~{r['avg']:,} tok/lượt · {r['source']} · {r['title']} · `{r['id']}`")
    if d["bloat"]:
        L += ["", "## ⚠️ Session có ngữ cảnh phình (nên mở session mới)", ""]
        for r in d["bloat"]:
            L.append(f"- ~{r['avg']:,} tok/lượt · {r['input']:,} tok cộng dồn · {r['title']} · `{r['id']}`")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


def escalate(question: str, reason: str) -> None:
    ESCALATIONS.mkdir(parents=True, exist_ok=True)
    p = ESCALATIONS / f"token_budget_{int(dt.datetime.now().timestamp())}.json"
    p.write_text(json.dumps({"from": "Ultron (watchdog token)", "space": "(hệ thống)",
                             "question": question, "reason": reason}, ensure_ascii=False, indent=2),
                 encoding="utf-8")


def main() -> int:
    d = collect()
    if not d.get("ok"):
        print(f"token-budget: {d.get('why')}")
        return 0
    write_report(d)
    st = load_state()
    st.setdefault("alerts", {})
    day = d["day"]
    fired = []
    st["alerts"].setdefault(day, [])

    if d["input"] >= DAY_INPUT_ALERT_TOKENS and "day" not in st["alerts"][day]:
        msg = (f"⚠️ Ngân sách token hôm nay đã vượt ngưỡng: {d['input']:,} token input "
               f"(tươi {d['fresh']:,}) trong {d['sessions']} session. Top: "
               + "; ".join(f"{r['input']:,} tok — {r['title']}" for r in d["top"][:3]))
        escalate(msg, f"ngưỡng ngày {DAY_INPUT_ALERT_TOKENS:,} token")
        st["alerts"][day].append("day")
        fired.append("day")

    for r in d["top"]:
        if r["input"] >= SESSION_ALERT_TOKENS and f"session:{r['id']}" not in st["alerts"][day]:
            msg = (f"⚠️ Một session đang đốt quá nhiều: {r['input']:,} token "
                   f"({r['calls']} lượt API, ~{r['avg']:,} token/lượt) — \"{r['title']}\". "
                   f"Đề xuất: chốt việc rồi mở session mới cho việc tiếp theo.")
            escalate(msg, f"session vượt {SESSION_ALERT_TOKENS:,} token")
            st["alerts"][day].append(f"session:{r['id']}")
            fired.append(f"session:{r['id']}")

    save_state(st)
    line = (f"token-budget {day}: input={d['input']:,} (tươi {d['fresh']:,} · cache {d['cache']:,}) "
            f"output={d['output']:,} · {d['sessions']} session · top={d['top'][0]['input']:,} "
            f"\"{d['top'][0]['title']}\"" if d["top"] else "token-budget: hôm nay chưa có session")
    print(line)
    if fired:
        print(f"  → đã báo Hoàng: {', '.join(fired)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
