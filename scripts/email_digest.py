#!/usr/bin/env python3
"""Ban tin email cho Hoang — loc bot/ban tin, chi bao mail NGUOI gui.

Chay boi dispatcher (`schedules.yaml`) nen phai thuan script, 0 token.

  email_digest.py --dry-run                 # in ra man hinh, khong gui
  email_digest.py --send                    # gui vao DM Hoang
  email_digest.py --send --hours 12 --max 8

Nguyen tac: im lang khi khong co mail moi (tranh spam). Noi dung mail KHONG BAO GIO ra group —
chi gui vao DM Hoang (spaces/0dniIqAAAAE).
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import gmail  # noqa: E402  (helper cung thu muc)

DM_HOANG = "spaces/0dniIqAAAAE"
SEND = SCRIPT_DIR / "gchat_send_text.py"

# Nguon "rach" — bot he thong, ban tin, dao tao: khong dua vao ban tin.
# CHU Y: KHONG dung -category:promotions/-category:social/-category:forums o day —
# do that su an mat gan het mail nguoi gui (do that: 48 -> 4), ke ca mail du an/nhan su.
NOISE = ["from:jira", "from:ttnb@vnpay.vn", "from:daotao@vnpay.vn",
         "from:noreply", "from:no-reply", "from:notification",
         "from:marketing@vnpay.vn"]

# Dau hieu can xu ly / gap.
URGENT = ["duyệt", "approve", "xác nhận", "confirm", "khẩn", "urgent", "gấp",
          "deadline", "action required", "cần xử lý", "phản hồi", "trả lời"]


def build_query(hours: int) -> str:
    window = f"newer_than:{max(1, round(hours / 24))}d" if hours >= 24 else f"newer_than:1d"
    return "in:inbox is:unread " + window + " " + " ".join(f"-{n}" for n in NOISE)


def fetch(s, hours: int, limit: int) -> list[dict]:
    q = build_query(hours)
    r = s.users().messages().list(userId="me", q=q, maxResults=limit).execute()
    out = []
    for m in r.get("messages", []):
        full = s.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]).execute()
        out.append({
            "id": m["id"],
            "from": gmail._hdr(full, "From"),
            "subject": gmail._hdr(full, "Subject"),
            "date": gmail._hdr(full, "Date"),
        })
    return out


def pretty_from(raw: str) -> str:
    """'Oanh, Lê Hoàng Kiều (KDMN, QLDA) <oa@vnpay.vn>' -> 'Oanh, Lê Hoàng Kiều'."""
    name = re.sub(r"\s*<.*?>\s*", "", raw).strip().strip('"')
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name)          # bo phan phong ban trong ngoac
    name = re.sub(r"\s+via\s+.*$", "", name, flags=re.I)   # bo ' via Vietbank SME'
    name = re.sub(r"\s+", " ", name).strip(", ")
    if len(name) > 32:
        name = name[:31].rstrip() + "…"
    return name or raw


def pretty_time(raw: str) -> str:
    try:
        d = dt.datetime.strptime(raw[:25].strip(), "%a, %d %b %Y %H:%M:%S")
        return d.strftime("%H:%M %d/%m")
    except Exception:
        return raw[:16]


def is_urgent(item: dict) -> bool:
    blob = f"{item['from']} {item['subject']}".lower()
    return any(k in blob for k in URGENT)


def digest_text(items: list[dict], hours: int, noise_n: int) -> str:
    head = f"📬 *Mail người gửi* — {hours}h qua: {len(items)} thư"
    lines = [head, ""]
    for i, it in enumerate(items, 1):
        mark = "⚠️ " if is_urgent(it) else ""
        subj = it["subject"][:78] or "(không có tiêu đề)"
        lines.append(f"{i}. {mark}*{pretty_from(it['from'])[:30]}* — {subj}")
        lines.append(f"    _{pretty_time(it['date'])}_")
    if noise_n:
        lines.append("")
        lines.append(f"_(đã lọc {noise_n} thư bot/bản tin trong {hours}h)_")
    return "\n".join(lines)


def noise_count(s, hours: int) -> int:
    window = f"newer_than:{max(1, round(hours / 24))}d" if hours >= 24 else "newer_than:1d"
    q = f"in:inbox is:unread {window} " + " OR ".join(n for n in NOISE)
    return gmail._count(s, q)


def send(text: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    r = subprocess.run([sys.executable, str(SEND), "--space", DM_HOANG, "--text-file", path],
                       capture_output=True, text=True)
    print(f"   gui DM Hoang: exit={r.returncode} {r.stdout.strip()[:120]}")
    Path(path).unlink(missing_ok=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Ban tin email sang cho Hoang")
    p.add_argument("--hours", type=int, default=24)
    p.add_argument("--max", type=int, default=12)
    p.add_argument("--send", action="store_true", help="gui that vao DM Hoang")
    p.add_argument("--dry-run", action="store_true", help="chi in ra man hinh")
    a = p.parse_args()

    s = gmail.svc()
    items = fetch(s, a.hours, a.max)
    if not items:
        print(f"   (khong co mail nguoi gui trong {a.hours}h — khong gui gi)")
        return 0
    text = digest_text(items, a.hours, noise_count(s, a.hours))
    if a.dry_run or not a.send:
        print(text)
        print(f"\n   [dry-run] se gui {len(items)} dong toi {DM_HOANG}")
        return 0
    send(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
