#!/usr/bin/env python3
"""List Google Chat space members (user id + display name) so Ultron can @-mention
someone proactively. Uses the bot service account.

Usage:
    gchat_members.py --space spaces/XXXX [--json]

Prints "users/<id> | <displayName> | <type>" per line (or JSON with --json).
Note: displayName is only returned when the space exposes it; otherwise blank.
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
SA_ENV = os.environ.get("GOOGLE_CHAT_SERVICE_ACCOUNT_JSON", "")
SA_PATH = Path(SA_ENV) if SA_ENV and not SA_ENV.startswith("{") else (HERMES_HOME / "google-chat-sa.json")
_SCOPES = ["https://www.googleapis.com/auth/chat.bot"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--space", required=True)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    if not SA_PATH.exists():
        print(f"ERROR: service account not found at {SA_PATH}", file=sys.stderr)
        return 2
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_info(
        json.loads(SA_PATH.read_text(encoding="utf-8")), scopes=_SCOPES)
    svc = build("chat", "v1", credentials=creds, cache_discovery=False)

    out, page = [], None
    while True:
        kw = dict(parent=a.space, pageSize=200)
        if page:
            kw["pageToken"] = page
        resp = svc.spaces().members().list(**kw).execute()
        out.extend(resp.get("memberships", []))
        page = resp.get("nextPageToken")
        if not page:
            break

    rows = []
    for m in out:
        member = m.get("member") or {}
        rows.append({
            "name": member.get("name", ""),
            "displayName": member.get("displayName", ""),
            "type": member.get("type", ""),
            "role": m.get("role", ""),
        })
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r['name']} | {r['displayName'] or '(no name)'} | {r['type']} | {r['role']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
