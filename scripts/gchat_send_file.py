#!/usr/bin/env python3
"""Send a file as a native Google Chat attachment (user-OAuth path).

Google Chat's `media.upload` is hard-rejected for the bot service account, so
attachments must be uploaded with a user token (`chat.messages.create` scope,
authorized once via the gateway's /setup-files flow, stored in
~/.hermes/google_chat_user_token.json). This script does upload + message create
in one shot so the agent can deliver reports to a space/DM directly.

Usage:
    gchat_send_file.py --space spaces/XXXX --file /path/report.pdf [--text "caption"] [--thread threads/YYY]
"""
import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

HERMES_HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
TOKEN_PATH = HERMES_HOME / "google_chat_user_token.json"


def chat_api():
    d = json.loads(TOKEN_PATH.read_text())
    creds = Credentials(
        token=d.get("token"),
        refresh_token=d.get("refresh_token"),
        token_uri=d.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=d.get("client_id"),
        client_secret=d.get("client_secret"),
        scopes=d.get("scopes") or ["https://www.googleapis.com/auth/chat.messages.create"],
    )
    if not creds.valid:
        creds.refresh(Request())
        d["token"] = creds.token
        TOKEN_PATH.write_text(json.dumps(d))
        os.chmod(TOKEN_PATH, 0o600)
    return build("chat", "v1", credentials=creds, cache_discovery=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", required=True, help="spaces/XXXX (or a space id)")
    ap.add_argument("--file", required=True)
    ap.add_argument("--text", default="")
    ap.add_argument("--thread", default="")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 2
    space = args.space if args.space.startswith("spaces/") else f"spaces/{args.space}"
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    api = chat_api()

    upload = api.media().upload(
        parent=space,
        body={"filename": path.name},
        media_body=MediaFileUpload(str(path), mimetype=mime, resumable=False),
    ).execute()
    ref = upload.get("attachmentDataRef")
    if not ref:
        print(f"upload returned no attachmentDataRef: {json.dumps(upload)[:300]}", file=sys.stderr)
        return 1

    body = {"attachment": [{"attachmentDataRef": ref}]}
    if args.text:
        body["text"] = args.text
    kwargs: dict = {"parent": space, "body": body}
    if args.thread:
        # BẮT BUỘC: thiếu messageReplyOption thì Chat tạo THREAD MỚI thay vì trả lời vào thread đang có
        kwargs["messageReplyOption"] = "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
        body["thread"] = {"name": args.thread}
    resp = api.spaces().messages().create(**kwargs).execute()
    print(json.dumps({"ok": True, "message": resp.get("name"), "attachment": resp.get("attachment")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
