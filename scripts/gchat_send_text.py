#!/usr/bin/env python3
"""Gửi 1 tin TEXT vào một space Google Chat, gửi AS BOT (service account).

Vì sao có: `team_post.py` chỉ gửi được mấy câu chào có sẵn theo `--kind`; còn khi cần gửi
một tin nội dung tuỳ ý vào space khác (nhờ test, báo tiến độ, thông báo) thì dùng script này.

    gchat_send_text.py --space spaces/XXXX --text "nội dung"
    gchat_send_text.py --space spaces/XXXX --text-file /tmp/tin.txt
    gchat_send_text.py --space spaces/XXXX --text "..." --thread spaces/XXXX/threads/YYYY
    gchat_send_text.py --space spaces/XXXX --text-file /tmp/tin.txt --dry-run

Lưu ý:
- KHÔNG truyền `--thread` ⇒ tin là **tin mới ở đầu space** (không nằm trong thread nào).
  Đúng cái cần khi muốn mở một việc mới cho cả group thấy.
- Bot chỉ gửi được vào space mà nó đã là thành viên.
- Có sẵn `[[DUYET]]`-free: script chỉ gửi đúng nội dung truyền vào, không tự thêm gì.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HOME = Path.home()
SA_PATH = HOME / ".hermes" / "google-chat-sa.json"

_MENTION_RE = re.compile(r"<users/(\d+)>")


def _u16_len(s: str) -> int:
    """Độ dài theo UTF-16 code unit — Google Chat tính offset kiểu này."""
    return len(s.encode("utf-16-le")) // 2


def _mention_annotations(text: str) -> list:
    """Tự bọc annotation USER_MENTION cho mọi `<users/<id>>` trong text.

    Không có annotation thì Google Chat hiện nguyên chuỗi `<users/123>` —
    không ai được notify. Có annotation thì chip `@Tên` hiện ra và người đó được ping.
    """
    out = []
    for m in _MENTION_RE.finditer(text):
        if m.start() > 0 and text[m.start() - 1] == "\\":
            continue
        out.append({
            "type": "USER_MENTION",
            "startIndex": _u16_len(text[: m.start()]),
            "length": _u16_len(m.group(0)),
            "userMention": {
                "user": {"name": f"users/{m.group(1)}", "type": "HUMAN"},
            },
        })
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--space", required=True, help="vd: spaces/AAAADv4ib6s")
    p.add_argument("--text", default=None)
    p.add_argument("--text-file", default=None, help="đọc nội dung từ file (tránh quote lằng nhằng)")
    p.add_argument("--thread", default=None, help="threadKey hoặc spaces/../threads/.. để trả lời trong thread")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    if a.text_file:
        text = Path(a.text_file).read_text(encoding="utf-8")
    elif a.text:
        text = a.text
    else:
        print("ERROR: cần --text hoặc --text-file", file=sys.stderr)
        return 2
    text = text.strip()
    if not text:
        print("ERROR: nội dung rỗng", file=sys.stderr)
        return 2
    if len(text) > 4000:
        print(f"WARN: {len(text)} ký tự — Google Chat cắt ở 4000, cân nhắc chia tin", file=sys.stderr)

    if a.dry_run:
        print(f"[dry-run] -> {a.space}" + (f" thread={a.thread}" if a.thread else " (tin mới, không thread)"))
        print("-" * 60)
        print(text)
        return 0

    if not SA_PATH.exists():
        print(f"ERROR: thiếu service account {SA_PATH}", file=sys.stderr)
        return 2
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_info(
        json.loads(SA_PATH.read_text(encoding="utf-8")),
        scopes=["https://www.googleapis.com/auth/chat.bot"])
    svc = build("chat", "v1", credentials=creds, cache_discovery=False)

    body: dict = {"text": text}
    annotations = _mention_annotations(text)
    if annotations:
        body["annotations"] = annotations
    kwargs: dict = {"parent": a.space, "body": body}
    if a.thread:
        kwargs["messageReplyOption"] = "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
        body["thread"] = {"name": a.thread} if a.thread.startswith("spaces/") else {"threadKey": a.thread}
    try:
        resp = svc.spaces().messages().create(**kwargs).execute()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK {resp.get('name', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
