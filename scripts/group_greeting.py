#!/usr/bin/env python3
"""Post a short greeting to a Google Chat space AS the bot (service account).

Used by the one-shot cron `ultron-morning-greeting`. Deterministic: no LLM, no reasoning —
just build the message and post it, so the 9am fire costs nothing and cannot go off-script.

Usage:
  group_greeting.py --space spaces/XXX [--dry-run] [--text "..."]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HOME = Path.home() / ".hermes"
SA_PATH = HOME / "google-chat-sa.json"
DEFAULT_SPACE = "spaces/AAAADv4ib6s"  # VBB SME | Nội bộ dự án — nhóm làm việc chính
PEOPLE = HOME / "people.json"
# Team Tester đầu mối: tag "tester" + "vbsme" → chị Hà (leader) + Như + Tú (Hoàng chốt 2026-09-10)
TESTER_TAGS = {"tester", "vbsme"}
# Từ xưng hô hợp lệ — chỉ ghép trước tên khi `call` là xưng hô, không phải tên gọi tắt
HONORIFICS = ("anh", "chị", "em", "cô", "chú", "bác", "sếp", "thầy")


def _tester_mentions() -> str:
    """`<users/id>` chips for the Tester focal points, read from the people registry.

    Selects by TAG (never department), orders the leader first, and prefixes each name with the
    honorific stored in `call` (vd "Chị") so the greeting addresses people the way they're called.
    Returns "" when the registry is missing — the greeting still reads fine without it.
    """
    try:
        data = json.loads(PEOPLE.read_text(encoding="utf-8"))
        rows = []
        for uid, p in (data.get("people") or {}).items():
            if not TESTER_TAGS <= {t.lower() for t in (p.get("tags") or [])}:
                continue
            is_leader = "MANAGER" in (p.get("seat") or "")
            rows.append((not is_leader, p.get("name") or "", uid, (p.get("call") or "").strip()))
        rows.sort()
        parts = []
        for _, _, uid, call in rows:
            honorific = call if call and call.split()[0].lower() in HONORIFICS else ""
            parts.append(f"{honorific} <{uid}>" if honorific else f"<{uid}>")
        return ", ".join(parts)
    except Exception:
        return ""


def build_text() -> str:
    team = _tester_mentions()
    lead = f"{team} ơi — " if team else "Cả nhà ơi — "
    return (
        "Chào buổi sáng cả nhà ☀️\n\n"
        "Hôm nay sếp Hoàng nghỉ ạ.\n"
        f"{lead}có vấn đề gì cứ nhắn cho em (Ultron) nhé — em trực cả ngày 🫡\n"
        "Việc gì cần sếp quyết thì em ghi lại, sếp về là em báo lại ngay."
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--space", default=DEFAULT_SPACE)
    p.add_argument("--text", default=None)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    text = (a.text or build_text()).strip()
    if a.dry_run:
        print(f"[dry-run] would post to {a.space} at {datetime.now().isoformat(timespec='seconds')}:")
        print("-" * 60)
        print(text)
        return 0

    if not SA_PATH.exists():
        print(f"ERROR: service account missing at {SA_PATH}", file=sys.stderr)
        return 2
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_info(
        json.loads(SA_PATH.read_text(encoding="utf-8")),
        scopes=["https://www.googleapis.com/auth/chat.bot"])
    svc = build("chat", "v1", credentials=creds, cache_discovery=False)
    try:
        resp = svc.spaces().messages().create(parent=a.space, body={"text": text}).execute()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK {resp.get('name','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
