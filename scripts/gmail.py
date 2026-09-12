#!/usr/bin/env python3
"""Quan ly Gmail cho Hoang — dung token local ~/.hermes/google_token.json (3 scope gmail).

Lenh:
  profile                      -> dia chi mail + tong so thu/thread
  counts                       -> so thu CHUA DOC (inbox) + top label chua doc
  search "<query>" [--max N]   -> liet ke thu (from/subject/date/snippet)
  read <msg_id>               -> header + noi dung text (cat gon)
  send --to A --subject S --body B [--cc C] [--html] [--label Ten]   ("\n" trong body = xuong dong that)
  reply <msg_id> --body B      -> tra loi trong cung thread
  modify <msg_id> [--add L] [--remove L] [--archive] [--mark-read] [--mark-unread]
  labels                       -> danh sach label

Khong co quyen xoa vinh vien (khong xin scope do).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_PATH = Path.home() / ".hermes" / "google_token.json"


def creds() -> Credentials:
    if not TOKEN_PATH.exists():
        sys.exit("ERROR: Chua co token. Chay setup.py --auth-url --services email truoc.")
    c = Credentials.from_authorized_user_file(str(TOKEN_PATH))
    if c.expired and c.refresh_token:
        c.refresh(Request())
        TOKEN_PATH.write_text(c.to_json())
        TOKEN_PATH.chmod(0o600)
    return c


def svc():
    return build("gmail", "v1", credentials=creds(), cache_discovery=False)


def _hdr(msg: dict, name: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _body_text(msg: dict, limit: int = 4000) -> str:
    def walk(part):
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "replace")
        for sub in part.get("parts", []) or []:
            got = walk(sub)
            if got:
                return got
        return ""

    txt = walk(msg.get("payload", {})) or msg.get("snippet", "")
    return txt[:limit]


def _count(s, q: str, cap: int = 50000) -> int:
    """Dem THAT bang phan trang — KHONG dung resultSizeEstimate cua Gmail (bi cap, sai)."""
    n, tok = 0, None
    while True:
        r = s.users().messages().list(userId="me", q=q, maxResults=500, pageToken=tok).execute()
        n += len(r.get("messages", []))
        tok = r.get("nextPageToken")
        if not tok or n >= cap:
            return n


def cmd_profile(_a):
    p = svc().users().getProfile(userId="me").execute()
    print(f"account:      {p.get('emailAddress')}")
    print(f"messagesTotal: {p.get('messagesTotal')}")
    print(f"threadsTotal:  {p.get('threadsTotal')}")


def cmd_counts(_a):
    s = svc()
    lab = s.users().labels().get(userId="me", id="INBOX").execute()
    print(f"INBOX unread: {lab.get('messagesUnread')} / tong {lab.get('messagesTotal')}")
    checks = [
        ("in:inbox is:unread newer_than:1d", "unread 24h qua"),
        ("in:inbox is:unread newer_than:7d", "unread 7 ngay qua"),
        ("in:inbox is:unread newer_than:7d from:jira", "  ... tu JIRA"),
        ("in:inbox is:unread newer_than:7d -from:jira -from:ttnb@vnpay.vn -from:daotao@vnpay.vn", "  ... mail that (bo bot/ban tin)"),
    ]
    for q, name in checks:
        print(f"  {_count(s, q):>6}  {name}")


def cmd_search(a):
    r = svc().users().messages().list(userId="me", q=a.query, maxResults=a.max).execute()
    ids = [m["id"] for m in r.get("messages", [])]
    print(f"khop (dem that): {_count(svc(), a.query)} | lay {len(ids)}")
    for i in ids:
        m = svc().users().messages().get(userId="me", id=i, format="metadata",
                                        metadataHeaders=["From", "Subject", "Date"]).execute()
        print(f"  {i} | {_hdr(m,'Date')[:31]} | {_hdr(m,'From')[:38]} | {_hdr(m,'Subject')[:60]}")


def cmd_read(a):
    m = svc().users().messages().get(userId="me", id=a.msg_id, format="full").execute()
    print(f"id:      {m['id']}")
    print(f"from:    {_hdr(m,'From')}")
    print(f"to:      {_hdr(m,'To')}")
    print(f"date:    {_hdr(m,'Date')}")
    print(f"subject: {_hdr(m,'Subject')}")
    print(f"labels:  {','.join(m.get('labelIds', []))}")
    print("---")
    print(_body_text(m, a.limit))


def _send(payload: dict) -> dict:
    s = svc()
    raw = base64.urlsafe_b64encode(payload.as_bytes()).decode()
    sent = s.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"sent: id={sent.get('id')} thread={sent.get('threadId')}")
    return sent


def _label_id(s, name: str) -> str:
    """Id cua label theo ten; chua co thi tao (can scope gmail.modify)."""
    for l in s.users().labels().list(userId="me").execute().get("labels", []):
        if l["name"].lower() == name.lower():
            return l["id"]
    created = s.users().labels().create(userId="me", body={
        "name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}).execute()
    print(f"tao label moi: {name} ({created['id']})")
    return created["id"]


def cmd_send(a):
    # Cho truyen xuong dong kieu shell: "\\n" trong --body thanh newline that
    body = a.body.replace("\\n", "\n")
    msg = MIMEText(body, "html" if a.html else "plain", "utf-8")
    msg["To"] = a.to
    msg["Subject"] = a.subject
    if a.cc:
        msg["Cc"] = a.cc
    sent = _send(msg)
    if getattr(a, "label", None):
        s = svc()
        s.users().messages().modify(
            userId="me", id=sent["id"], body={"addLabelIds": [_label_id(s, a.label)]}).execute()
        print(f"gan label: {a.label}")


def cmd_reply(a):
    s = svc()
    orig = s.users().messages().get(userId="me", id=a.msg_id, format="metadata",
                                    metadataHeaders=["From", "Subject", "Message-ID", "References"]).execute()
    msg = MIMEText(a.body, "html" if a.html else "plain", "utf-8")
    msg["To"] = a.to or _hdr(orig, "From")
    subj = _hdr(orig, "Subject")
    msg["Subject"] = subj if subj.lower().startswith("re:") else f"Re: {subj}"
    mid = _hdr(orig, "Message-ID")
    if mid:
        msg["In-Reply-To"] = mid
        msg["References"] = (_hdr(orig, "References") + " " + mid).strip()
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = s.users().messages().send(userId="me", body={"raw": raw, "threadId": orig["threadId"]}).execute()
    print(f"replied: id={sent.get('id')} thread={sent.get('threadId')}")


def cmd_modify(a):
    add, remove = list(a.add or []), list(a.remove or [])
    if a.archive:
        remove.append("INBOX")
    if a.mark_read:
        remove.append("UNREAD")
    if a.mark_unread:
        add.append("UNREAD")
    body = {"addLabelIds": add, "removeLabelIds": remove}
    r = svc().users().messages().modify(userId="me", id=a.msg_id, body=body).execute()
    print(f"ok: {r['id']} labels={','.join(r.get('labelIds', []))}")


def cmd_labels(_a):
    labels = svc().users().labels().list(userId="me").execute().get("labels", [])
    for l in sorted(labels, key=lambda x: x["name"]):
        print(f"  {l['id']:<22} {l['name']}")


def main():
    p = argparse.ArgumentParser(description="Gmail helper (token local, 3 scope)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("profile").set_defaults(fn=cmd_profile)
    sub.add_parser("counts").set_defaults(fn=cmd_counts)
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--max", type=int, default=10); s.set_defaults(fn=cmd_search)
    s = sub.add_parser("read"); s.add_argument("msg_id"); s.add_argument("--limit", type=int, default=4000); s.set_defaults(fn=cmd_read)
    s = sub.add_parser("send"); s.add_argument("--to", required=True); s.add_argument("--subject", required=True); s.add_argument("--body", required=True); s.add_argument("--cc"); s.add_argument("--label"); s.add_argument("--html", action="store_true"); s.set_defaults(fn=cmd_send)
    s = sub.add_parser("reply"); s.add_argument("msg_id"); s.add_argument("--body", required=True); s.add_argument("--to"); s.add_argument("--html", action="store_true"); s.set_defaults(fn=cmd_reply)
    s = sub.add_parser("modify"); s.add_argument("msg_id"); s.add_argument("--add", action="append"); s.add_argument("--remove", action="append"); s.add_argument("--archive", action="store_true"); s.add_argument("--mark-read", action="store_true"); s.add_argument("--mark-unread", action="store_true"); s.set_defaults(fn=cmd_modify)
    sub.add_parser("labels").set_defaults(fn=cmd_labels)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
