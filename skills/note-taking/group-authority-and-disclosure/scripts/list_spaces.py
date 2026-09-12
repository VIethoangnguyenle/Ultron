#!/usr/bin/env python3
"""Liệt kê Google Chat space mà Hoàng là thành viên, kèm displayName + spaceType.

Dùng khi cần ĐỔI TÊN NHÓM (người ta nói miệng) → space id, trước khi ghi một luật có phạm vi,
vd "Hoàng cho nhóm X show mã nguồn". Tên nhóm gần giống nhau rất nhiều (DVNH - Daily /
DVNH - MN / DVNH - MN - AppServer - Nhóm 1) ⇒ phải xác định DUY NHẤT, không đoán id từ tên.

Read-only: dùng read token của Hoàng (~/.hermes/google_chat_read_token.json). Host phải có
`google-api-python-client` (chạy bằng python3 của máy này).

Usage:
  list_spaces.py [--grep daily] [--json]
"""
import argparse
import json
import os
import sys
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
TOKEN = HOME / "google_chat_read_token.json"
SCOPES = [
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
]


def service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    d = json.loads(TOKEN.read_text(encoding="utf-8"))
    c = Credentials(
        token=d.get("token"), refresh_token=d.get("refresh_token"),
        token_uri=d.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=d.get("client_id"), client_secret=d.get("client_secret"), scopes=SCOPES,
    )
    # refresh VÔ ĐIỀU KIỆN: token hết hạn mà .valid vẫn có thể báo True → 401 thật đã gặp
    c.refresh(Request())
    return build("chat", "v1", credentials=c, cache_discovery=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grep", default="", help="lọc theo displayName (không phân biệt hoa thường)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    svc = service()
    rows, page_token = [], None
    while True:
        kw = {"pageSize": 100}
        if page_token:
            kw["pageToken"] = page_token
        page = svc.spaces().list(**kw).execute()
        for s in page.get("spaces") or []:
            rows.append({
                "id": s.get("name", ""),
                "name": s.get("displayName") or "(no name)",
                "type": s.get("spaceType", ""),
            })
        page_token = page.get("nextPageToken")
        if not page_token:
            break

    if args.grep:
        needle = args.grep.lower()
        rows = [r for r in rows if needle in r["name"].lower() or needle in r["id"].lower()]

    if args.json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        for r in rows:
            print(f"{r['id']} | {r['name']} | {r['type']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
