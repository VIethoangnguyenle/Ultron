#!/usr/bin/env python3
"""Gác khẩn: xoá mọi tin do BOT đăng có lộ bản đồ mã nguồn (danh sách file / tên class).

Phase 1: quét 400 tin gần nhất, xoá các tin khớp dấu hiệu lộ.
Phase 2: gác tiếp trong THỜI GIAN giây, quét lại mỗi 15s (để dập tin đang được sinh ra).
Chỉ ĐỌC + XOÁ TIN CỦA CHÍNH BOT — không đụng tin của người khác.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials

HH = Path("/home/zane/.hermes")
SPACE = "spaces/AAAADv4ib6s"
BOT = "107189931083311611240"
SUFFIX = (r"(?:Controller|Handler|Factory|Repository|Entity|Model|Service|Services|Executor|"
          r"Constants|Enum|Error|Definition|Request|Response|FactoryImpl|Filter|Item|Metadata)")
CAMEL = re.compile(r"\b[A-Z][A-Za-z0-9]*" + SUFFIX + r"\b")
LITERAL = ("src/main/java", "75 file", "550 file", "CustomerFactory.java",
           "danh sách file thay đổi", "file .java\nauth", "user_settings —")
WATCH_SEC = int(sys.argv[1]) if len(sys.argv) > 1 else 180


def tok_read():
    tok = json.loads((HH / "google_chat_read_token.json").read_text())
    c = Credentials(token=tok["token"], refresh_token=tok["refresh_token"],
                    token_uri=tok["token_uri"], client_id=tok["client_id"],
                    client_secret=tok["client_secret"], scopes=tok["scopes"])
    c.refresh(Request())  # refresh VÔ ĐIỀU KIỆN — token cũ có thể hết hạn mà .valid vẫn báo True
    tok["token"] = c.token
    (HH / "google_chat_read_token.json").write_text(json.dumps(tok))
    return c


def tok_sa():
    sa = json.loads((HH / "google-chat-sa.json").read_text())
    c = service_account.Credentials.from_service_account_info(
        sa, scopes=["https://www.googleapis.com/auth/chat.bot"])
    c.refresh(Request())
    return c


def call(url, cred, method="GET"):
    req = urllib.request.Request(url, method=method, headers={
        "Authorization": f"Bearer {cred.token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def is_leak(t: str) -> str:
    for k in LITERAL:
        if k in t:
            return f"literal:{k}"
    names = set(CAMEL.findall(t))
    if len(names) >= 3:
        return "3+ tên class: " + ", ".join(sorted(names)[:4])
    return ""


def scan(rc):
    out, page = [], None
    for _ in range(4):
        u = f"https://chat.googleapis.com/v1/{SPACE}/messages?pageSize=100&orderBy=createTime%20desc"
        if page:
            u += "&pageToken=" + page
        d = call(u, rc)
        for m in d.get("messages") or []:
            if BOT not in ((m.get("sender") or {}).get("name") or ""):
                continue
            out.append(m)
        page = d.get("nextPageToken")
        if not page:
            break
    return out


def main() -> int:
    rc, sc = tok_read(), tok_sa()
    hits = json.loads(Path("/tmp/leak_hits.json").read_text()) if Path("/tmp/leak_hits.json").exists() else []
    deleted = set()

    def sweep(tag: str) -> None:
        for m in scan(rc):
            t = m.get("text") or ""
            why = is_leak(t)
            if not why or m["name"] in deleted:
                continue
            try:
                call(f"https://chat.googleapis.com/v1/{m['name']}", sc, method="DELETE")
                print(f"[{tag}] XOÁ {m['createTime']} {m['name']} ({why})", flush=True)
                hits.append({"createTime": m["createTime"], "name": m["name"], "text": t})
                Path("/tmp/leak_hits.json").write_text(
                    json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")
            except Exception as e:  # noqa: BLE001
                print(f"[{tag}] LỖI {m['name']}: {e}", flush=True)
            deleted.add(m["name"])

    sweep("phase1")
    print(f"--- phase1 xong, gác tiếp {WATCH_SEC}s ---", flush=True)
    end = time.time() + WATCH_SEC
    while time.time() < end:
        time.sleep(15)
        sweep("gác")
    print("--- hết thời gian gác ---", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
