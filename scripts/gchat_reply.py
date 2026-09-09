#!/usr/bin/env python3
"""Post a reply into a Google Chat space/thread AS the bot (service account).

Used by the @Hoang-mention auto-reply cron. Bypasses `hermes send` target
resolution (which can't address arbitrary threads) and talks to the Chat API
directly with the bot's service account. Fails cleanly with a non-zero exit
when the bot isn't a member of the space (HTTP 403) — the caller then falls
back to escalating the question to Hoang.

Usage:
  gchat_reply.py --space spaces/XXX [--thread spaces/XXX/threads/YYY] \
                 --text "reply" | --file /path/to/reply.txt
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


def _load_sa():
    if not SA_PATH.exists():
        print(f"ERROR: service account not found at {SA_PATH}", file=sys.stderr)
        sys.exit(2)
    from google.oauth2 import service_account
    info = json.loads(SA_PATH.read_text(encoding="utf-8"))
    return service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--space", required=True)
    p.add_argument("--thread", default=None)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", default=None)
    g.add_argument("--file", default=None)
    a = p.parse_args()

    text = a.text
    if a.file:
        text = Path(a.file).read_text(encoding="utf-8")
    if text is None or not text.strip():
        print("ERROR: empty reply text", file=sys.stderr)
        return 2

    from googleapiclient.discovery import build
    svc = build("chat", "v1", credentials=_load_sa(), cache_discovery=False)
    body = {"text": text.strip()}
    if a.thread:
        body["thread"] = {"name": a.thread}
    kwargs = dict(parent=a.space, body=body)
    if a.thread:
        kwargs["messageReplyOption"] = "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
    try:
        resp = svc.spaces().messages().create(**kwargs).execute()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("OK", resp.get("name", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
