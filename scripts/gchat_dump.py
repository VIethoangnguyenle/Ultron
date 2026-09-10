#!/usr/bin/env python3
"""Dump Google Chat messages from a space using Hoàng's READ-ONLY OAuth token.

Read-only inspection tool (scope chat.messages.readonly) — used to examine what was actually
said in a space, e.g. to diagnose another agent's behaviour instead of guessing.

Usage:
  gchat_dump.py --space spaces/AAQASaFjh6M [--limit 200] [--sender users/...] [--grep TEXT]
                [--json]
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
TOKEN_PATH = HERMES_HOME / "google_chat_read_token.json"
NAMES_PATH = HERMES_HOME / "google_chat_sender_names.json"


def load_names() -> dict:
    try:
        return json.loads(NAMES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    c = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes", ["https://www.googleapis.com/auth/chat.messages.readonly"]),
    )
    if not c.valid:
        c.refresh(Request())
        data["token"] = c.token
        TOKEN_PATH.write_text(json.dumps(data), encoding="utf-8")
        os.chmod(TOKEN_PATH, 0o600)
    return c


def sender_of(msg: dict) -> str:
    return ((msg.get("sender") or {}).get("name")) or "?"


def text_of(msg: dict) -> str:
    body = (msg.get("text") or "").strip()
    if body:
        return body
    parts = []
    for a in (msg.get("attachment") or []):
        parts.append(f"[đính kèm: {a.get('contentName') or a.get('name')}]")
    for c in (msg.get("cardsV2") or []):
        parts.append("[card]")
    return " ".join(parts) or "(không có text)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", required=True)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--sender", help="chỉ lấy tin của users/... này")
    ap.add_argument("--grep", help="chỉ lấy tin chứa chuỗi này (không phân biệt hoa/thường)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    from googleapiclient.discovery import build
    svc = build("chat", "v1", credentials=creds(), cache_discovery=False)
    names = load_names()

    out, token = [], None
    while len(out) < a.limit:
        page = svc.spaces().messages().list(
            parent=a.space, pageSize=min(100, a.limit - len(out)),
            orderBy="createTime desc", pageToken=token).execute()
        batch = page.get("messages") or []
        out.extend(batch)
        token = page.get("nextPageToken")
        if not token or not batch:
            break
    out.reverse()  # oldest -> newest

    rows = []
    for m in out:
        s = sender_of(m)
        if a.sender and s != a.sender:
            continue
        txt = text_of(m)
        if a.grep and a.grep.lower() not in txt.lower():
            continue
        who = names.get(s, s)
        rows.append({"time": (m.get("createTime") or "")[:19], "sender": s, "name": who, "text": txt})

    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    for r in rows:
        print(f"[{r['time']}] {r['name']}: {r['text'][:400]}")
        print("-" * 70)
    print(f"({len(rows)} tin)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
