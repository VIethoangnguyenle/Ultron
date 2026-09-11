"""Soi lịch sử: Ultron (bot) từng gửi tin nào chứa SOURCE CODE Java lên group không.

Dùng read token của Hoàng (chỉ đọc). Quét các space Ultron có mặt, lọc tin do bot Ultron gửi,
tìm dấu hiệu mã nguồn Java.
"""
import json
import re
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

H = Path.home() / ".hermes"
BOT = "users/107189931083311611240"  # Ultron bot

SPACES = {
    "spaces/AAAADv4ib6s": "VBB SME | Nội bộ dự án",
    "spaces/AAQASaFjh6M": "Agent Space",
    "spaces/AAQAIj8eRac": "DVNH - Daily",
    "spaces/AAQAiOgBqio": "Những chú chồn ăn dưa",
    "spaces/AAQAZxc2km8": "Ultron - Trợ lý",
    "spaces/AAQAakZ7wC8": "VB SME | Billing + SDK",
    "spaces/AAQAHdMJfLM": "VB SME | OTT",
}

# dấu hiệu mã nguồn Java (không dùng cho SQL / bảng / biểu thức)
JAVA_MARKERS = [
    r"```\s*java", r"\bpublic\s+(class|interface|enum|record)\b", r"\bprivate\s+\w+\s+\w+\s*[;=]",
    r"@Override\b", r"\bimport\s+(java|org|com)\.", r"\bSystem\.out\.print", r"\bvoid\s+\w+\s*\(",
    r"\bprotected\s+\w+", r"\breturn\s+new\s+\w+\(", r"@RestController|@Service|@Entity|@Autowired",
    r"\bnew\s+\w+\(\)\s*;", r"\bString\[\]\s+args",
]
PAT = re.compile("|".join(JAVA_MARKERS), re.IGNORECASE)

d = json.loads((H / "google_chat_read_token.json").read_text())
c = Credentials(token=d.get("token"), refresh_token=d.get("refresh_token"),
                token_uri=d.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=d.get("client_id"), client_secret=d.get("client_secret"),
                scopes=d.get("scopes", ["https://www.googleapis.com/auth/chat.messages.readonly"]))
if not c.valid:
    c.refresh(Request())
svc = build("chat", "v1", credentials=c, cache_discovery=False)

total, flagged, errs = 0, [], []
for space, name in SPACES.items():
    try:
        msgs, token = [], None
        for _ in range(3):  # tối đa 300 tin / space
            page = svc.spaces().messages().list(parent=space, pageSize=100,
                                               orderBy="createTime desc", pageToken=token).execute()
            msgs.extend(page.get("messages") or [])
            token = page.get("nextPageToken")
            if not token:
                break
    except Exception as exc:
        errs.append(f"{name}: {str(exc)[:80]}")
        continue
    for m in msgs:
        if ((m.get("sender") or {}).get("name")) != BOT:
            continue
        total += 1
        txt = m.get("text") or ""
        hit = PAT.search(txt)
        if hit:
            flagged.append((name, (m.get("createTime") or "")[:19], hit.group(0)[:40],
                            txt[:120].replace("\n", " ")))

print(f"Đã quét tin do Ultron gửi trong {len(SPACES)} space — tổng {total} tin")
if errs:
    print("Lỗi đọc:", errs)
if not flagged:
    print("KẾT QUẢ: KHÔNG có tin nào chứa dấu hiệu source code Java.")
else:
    print(f"KẾT QUẢ: {len(flagged)} tin cần xem lại:")
    for name, ts, pat, snippet in flagged:
        print(f"  [{ts}] {name} | khớp '{pat}' | {snippet}")
