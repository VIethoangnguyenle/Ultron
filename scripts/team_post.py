#!/usr/bin/env python3
"""Post a recurring team message to a Google Chat space AS the bot (service account).

Một script cho mọi tin định kỳ trong ngày, chọn loại bằng `--kind`:
  lunch    — nhắc ăn trưa (12h)
  evening  — chào cuối ngày (17:30)

Vì sao gom: các tin này chỉ khác nhau ở nội dung. Thêm loại mới = thêm 1 entry trong KINDS,
không phải thêm script thứ N rồi lại phải nhớ xoá.

Câu chọn theo NGÀY (không random) → mỗi ngày một câu khác, và chạy lại trong cùng ngày vẫn ra
đúng câu đó nên test được. Không @mention ai: tin vui vẻ mà réo tên cả team thì thành chuông báo.

Usage:
  team_post.py --kind lunch [--space spaces/...] [--dry-run] [--variant N]
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
SA_PATH = HOME / "google-chat-sa.json"
DEFAULT_SPACE = "spaces/AAAADv4ib6s"  # VBB SME | Nội bộ dự án

KINDS = {
    "lunch": [
        "12h rồi cả nhà ơi 🍚\nĐến giờ ăn trưa rồi đấy — ai đang dính bug thì để đó, cơm nguội ăn không ngon đâu 😄\nEm cũng xin phép đi ăn đây.",
        "Trưa rồi nha cả nhà 🕛\nGấp gì thì gấp, ăn đã rồi tính — não cần năng lượng mới fix nổi bug 😌",
        "12h — giờ ăn trưa ạ 🍜\nMọi người nhớ ăn đúng bữa nhé, em trông máy giúp cho. Quay lại mình chạy tiếp.",
        "Tới giờ cơm rồi cả nhà ơi 🍛\nĐừng để task nguội trước cơm nhé 😄 Ăn xong nghỉ chút rồi chiều chiến tiếp.",
        "Chuông báo: 12h — ăn trưa 🍽️\nAi đang họp thì cố thêm 5 phút, ai đang code thì cũng cố thêm 5 phút rồi đi ăn nha 😄",
    ],
    "evening": [
        "Hết ngày rồi cả nhà ơi 🌇\nHôm nay mọi người làm việc thế nào? Có gì vướng thì kể em nghe, mai xử tiếp.\nEm xin phép về ăn dưa đây 🍉",
        "Tan làm rồi ạ 🌆\nNay anh chị em chạy có trôi không? Ai còn vướng cứ để lại lời nhắn, sáng mai em xử tiếp nhé.\nEm về xơi dưa trước đây 🍉",
        "17h30 rồi nha cả nhà 🕠\nHôm nay ai xong sớm thì khoe, ai còn dở thì kể — em ghi lại hết.\nCòn em xin phép chuồn về ăn dưa 🍉",
        "Chào cuối ngày cả nhà 👋\nNay mọi người thế nào? Bug nào còn sống sót thì để mai em xử 😌\nEm về ăn dưa đây 🍉",
        "Hết giờ ạ ⏰\nTổng kết nhanh: hôm nay mọi người ổn hết chứ? Cần gì thì nhắn em, không thì... em về ăn dưa 🍉",
    ],
}


def build_text(kind: str, variant: int = None) -> str:
    if kind not in KINDS:
        raise SystemExit(f"kind không hợp lệ: {kind!r} (chọn: {', '.join(sorted(KINDS))})")
    opts = KINDS[kind]
    if variant is None:
        variant = date.today().toordinal() % len(opts)
    return opts[variant % len(opts)]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--kind", required=True, choices=sorted(KINDS))
    p.add_argument("--space", default=DEFAULT_SPACE)
    p.add_argument("--variant", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    text = build_text(a.kind, a.variant).strip()
    if a.dry_run:
        print(f"[dry-run] kind={a.kind} -> {a.space}")
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
