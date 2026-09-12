#!/usr/bin/env python3
"""Theo doi mail QUAN TRONG lien quan tới Hoàng → ping DM. Thuần script, 0 token.

Không phải bản tin: chỉ thư "đáng để anh biết ngay" mới ping; còn lại im lặng.
Chạy bởi cron `ultron-email-watch`; tự gửi vào DM Hoàng.

  email_watch.py                 # chạy thật (cron gọi cái này)
  email_watch.py --dry-run       # in ra, không gửi, không ghi state
  email_watch.py --explain       # soi điểm mọi mail: vì sao ping / vì sao bỏ
  email_watch.py --lookback 7    # cửa sổ xét (mặc định 2 ngày)
  email_watch.py --reset-seen    # xoá baseline (lần sau coi như chạy lần đầu)

Ba tầng quyết định, mọi bước đều in được bằng --explain:
  1. LOẠI THẲNG  — mail bulk/invite/HR tự động/bản tin: không bao giờ ping
  2. CHẤM ĐIỂM   — sự cố > gửi thẳng cho anh > người quan trọng > dự án
  3. NGƯỠNG      — >= 5 điểm thì ping (1 thư ping 1 lần, có state chống lặp)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import gmail  # noqa: E402

DM_HOANG = "spaces/0dniIqAAAAE"
SEND = SCRIPT_DIR / "gchat_send_text.py"
STATE = Path.home() / ".hermes" / "state" / "email_watch_seen.json"
ME = "hoangnlv@vnpay.vn"
THRESHOLD = 4

# --- Tầng 1: nguồn rác ---------------------------------------------------------
NOISE = ["from:jira", "from:ttnb@vnpay.vn", "from:daotao@vnpay.vn",
         "from:noreply", "from:no-reply", "from:notification",
         "from:marketing@vnpay.vn", "from:hrmpro", "from:tuyendung",
         "from:recruit", "from:sumeru"]

# Tiêu đề của mail hệ thống/invite/digest — bỏ, dù người gửi là người thật.
SKIP_SUBJECT = [
    r"\[.*bug report\s*\d{2}/\d{2}", r"bảng tổng hợp", r"đăng ký giải trình",
    r"thông báo nhân sự", r"sự kiện đã hủy", r"đã hủy:", r"^invitation",
    r"updated invitation", r"^accepted:", r"^declined:", r"^canceled event",
    r"bản tin", r"\[vpmn\]", r"nhắc nhở", r"thông báo nghỉ",
]

# --- Tầng 2: chấm điểm ---------------------------------------------------------
INCIDENT = ["lỗi live", "live bị", "production", "prod bị", "sự cố", "incident",
            "khẩn", "hỏa tốc", "urgent", "gấp", "không hoạt động", "không tải được",
            "ảnh hưởng khách hàng", "rollback", "hotfix", "downtime", "timeout"]
NEED_ACTION = ["xác nhận", "duyệt", "approve", "deadline", "cần xử lý", "yêu cầu",
               "phản hồi", "trả lời", "confirm", "action required", "xin ý kiến",
               "issue", "lỗi", "sai sót", "không đúng", "chậm", "tồn đọng"]
PROJECT = ["vb sme", "vbsme", "vietbank sme", "go-live", "golive", "release",
           "deploy", "bàn giao", "uat", "sit", "napas", "gói 3.1", "omni",
           "ekyc", "thanh toán", "giao dịch"]
VIP_ADDRS = ["duynl@vnpay.vn", "isms@vnpay.vn", "tchc@vnpay.vn", "hrvnpay@vnpay.vn"]
VIP_DOMAINS = ["vietbank.vn", "vietbank.com.vn", "napas.com.vn"]
VIP_TITLES = ["tổng giám đốc", "phó tổng giám đốc", "chủ tịch", "ban giám đốc"]


def addr(raw: str) -> str:
    m = re.search(r"<([^>]+)>", raw or "")
    return (m.group(1) if m else (raw or "")).strip().lower()


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {"seen": {}}


def save_state(st: dict) -> None:
    cut = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    st["seen"] = {k: v for k, v in st["seen"].items() if str(v)[:10] >= cut}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1))


TRUSTED_DOMAINS = ["vnpay.vn", "vietbank.vn", "vietbank.com.vn", "napas.com.vn"]


def skip_reason(hdr: dict) -> str | None:
    """Tầng 1 — lý do loại thẳng, hoặc None nếu đáng để chấm điểm."""
    subj = (hdr.get("Subject") or "").strip()
    low = subj.lower()
    for pat in SKIP_SUBJECT:
        if re.search(pat, low):
            return f"tiêu đề dạng hệ thống ({pat})"
    # LƯU Ý: mail nhóm nội bộ VNPay CŨNG có List-Unsubscribe → chỉ coi là bulk khi
    # người gửi nằm NGOÀI domain công ty/đối tác (nếu không sẽ mất sạch mail thật).
    a = addr(hdr.get("From"))
    internal = any(a.endswith("@" + d) or a.endswith("." + d) or d in a for d in TRUSTED_DOMAINS)
    if not internal and (hdr.get("List-Unsubscribe") or hdr.get("List-Id")
                         or "bulk" in (hdr.get("Precedence") or "").lower()):
        return "mail danh sách/bulk từ ngoài"
    return None


def score(hdr: dict) -> tuple[int, list[str]]:
    """Tầng 2 — hàm thuần: cùng input luôn ra cùng điểm."""
    frm, to, cc = hdr.get("From") or "", hdr.get("To") or "", hdr.get("Cc") or ""
    subj = hdr.get("Subject") or ""
    addr_from = addr(frm)
    blob = f"{frm} {subj}".lower()
    pts, why = 0, []

    if ME in to.lower():
        pts += 3; why.append("gửi thẳng cho anh")
    elif ME in cc.lower():
        pts += 1; why.append("anh trong Cc")
    if addr_from in VIP_ADDRS:
        pts += 2; why.append("đầu mối quan trọng")
    elif any(addr_from.endswith("@" + d) or addr_from.endswith("." + d) for d in VIP_DOMAINS):
        pts += 2; why.append("khách hàng/đối tác")
    if any(t in frm.lower() for t in VIP_TITLES):
        pts += 2; why.append("lãnh đạo")
    hits = [k for k in INCIDENT if k in blob]
    if hits:
        pts += 3; why.append("SỰ CỐ: " + ", ".join(hits[:3]))
    hits = [k for k in NEED_ACTION if k in blob]
    if hits:
        pts += 1; why.append("cần phản hồi: " + ", ".join(hits[:3]))
    hits = [k for k in PROJECT if k in blob]
    if hits:
        pts += 1; why.append("dự án: " + ", ".join(hits[:3]))
    if re.match(r"^\s*(re|fwd|fw)\s*:", subj, re.I) and ME in to.lower():
        pts += 1; why.append("trả lời trực tiếp cho anh")
    return pts, why


def candidates(s, lookback: int) -> list[dict]:
    q = f"in:inbox is:unread newer_than:{max(1, lookback)}d " + " ".join(f"-{n}" for n in NOISE)
    ids, tok = [], None
    while True:
        r = s.users().messages().list(userId="me", q=q, maxResults=100, pageToken=tok).execute()
        ids += [m["id"] for m in r.get("messages", [])]
        tok = r.get("nextPageToken")
        if not tok:
            break
    out = []
    for mid in ids:
        full = s.users().messages().get(
            userId="me", id=mid, format="metadata",
            metadataHeaders=["From", "To", "Cc", "Subject", "Date",
                             "List-Unsubscribe", "List-Id", "Precedence"]).execute()
        hdr = {h["name"]: h["value"] for h in full.get("payload", {}).get("headers", [])}
        out.append({"id": mid, "hdr": hdr, "snippet": full.get("snippet", "")})
    return out


def tally(items: list[dict]) -> tuple[list[dict], list[dict]]:
    keep, dropped = [], []
    for it in items:
        it["skip"] = skip_reason(it["hdr"])
        if it["skip"]:
            dropped.append(it)
            continue
        it["pts"], it["why"] = score(it["hdr"])
        keep.append(it)
    return sorted(keep, key=lambda x: -x["pts"]), dropped


def pretty_from(raw: str) -> str:
    name = re.sub(r"\s*<.*?>\s*", "", raw or "").strip().strip('"')
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name)
    name = re.sub(r"\s+via\s+.*$", "", name, flags=re.I)
    return re.sub(r"\s+", " ", name).strip(", ")[:40] or raw


def alert_text(it: dict) -> str:
    h, snip = it["hdr"], re.sub(r"\s+", " ", it["snippet"])[:200]
    return (f"🔔 *Mail quan trọng*\n"
            f"*{pretty_from(h.get('From'))}* — {(h.get('Subject') or '')[:95]}\n"
            f"_{h.get('Date', '')[:22]}_\n"
            f"vì: {', '.join(it['why'])}\n"
            f"↳ {snip}")


def send(text: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        path = fh.name
    r = subprocess.run([sys.executable, str(SEND), "--space", DM_HOANG, "--text-file", path],
                       capture_output=True, text=True)
    print(f"   ping: exit={r.returncode} {r.stdout.strip()[:100]}")
    Path(path).unlink(missing_ok=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Ping mail quan trong cho Hoang")
    p.add_argument("--lookback", type=int, default=2)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--explain", action="store_true")
    p.add_argument("--reset-seen", action="store_true")
    p.add_argument("--init-alerts-hours", type=int, default=12)
    a = p.parse_args()

    st = load_state()
    if a.reset_seen:
        save_state({"seen": {}})
        print("   da xoa baseline")
        return 0

    items = candidates(gmail.svc(), a.lookback)
    ranked, dropped = tally(items)

    if a.explain:
        print(f"   {'diem':>4} {'ping':5} {'tu':26} tieu de / ly do")
        for it in ranked:
            h = it["hdr"]
            print(f"   {it['pts']:>4} {'PING' if it['pts'] >= THRESHOLD else '-':5} "
                  f"{pretty_from(h.get('From'))[:26]:26} {(h.get('Subject') or '')[:52]}")
            if it["pts"] >= THRESHOLD:
                print(f"        vì: {', '.join(it['why'])}")
        print(f"   -- bo thang {len(dropped)} thu (bulk/invite/he thong):")
        for it in dropped[:8]:
            print(f"        [{(it['hdr'].get('Subject') or '')[:46]}] <- {it['skip']}")
        n = sum(1 for i in ranked if i["pts"] >= THRESHOLD)
        print(f"   (nguong {THRESHOLD}: {n}/{len(ranked)} thu se ping)")
        return 0

    first_run = not st["seen"]
    cut = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=a.init_alerts_hours)
    fresh = 0
    for it in ranked:
        if it["id"] in st["seen"]:
            continue
        if first_run and _older_than(it["hdr"].get("Date", ""), cut):
            st["seen"][it["id"]] = dt.date.today().isoformat()
            continue
        if it["pts"] >= THRESHOLD:
            if a.dry_run:
                print(alert_text(it))
            else:
                send(alert_text(it))
            fresh += 1
        st["seen"][it["id"]] = dt.date.today().isoformat()
    print(f"   xet {len(ranked)} | ping {fresh} | bo thang {len(dropped)}")
    if not a.dry_run:
        save_state(st)
    return 0


def _older_than(date_hdr: str, cut: dt.datetime) -> bool:
    try:
        d = dt.datetime.strptime(date_hdr[:25].strip(), "%a, %d %b %Y %H:%M:%S")
        return d.replace(tzinfo=dt.timezone.utc) < cut
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
