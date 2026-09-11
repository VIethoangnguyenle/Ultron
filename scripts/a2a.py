#!/usr/bin/env python3
"""A2A — envelope cho tin nhắn giữa CÁC APP BOT trong Google Chat (bản mở rộng N bot).

VÌ SAO: Google Chat không giao MESSAGE event giữa hai app bot với nhau, nên các bot "nói" qua một
kênh chung (Agent Space) và phải tự đánh dấu tin của mình để không lẫn với tin NGƯỜI.

VÌ SAO KHÔNG DÙNG DẤU RIÊNG TỪNG CẶP (ULT2KIT / KIT2ULT): N bot thì cần N*(N-1) dấu → không quản
nổi. Thay bằng MỘT envelope chung, có trường from/to; thêm bot mới = thêm 1 dòng registry.

ENVELOPE:
    [[A2A:v1 from=<tên> to=<tên>]] <nội dung>

Một tin CHỈ được coi là tin bot khi thoả CẢ HAI:
  (1) envelope nằm Ở ĐẦU message, đúng cú pháp
  (2) user id người gửi khớp với tên `from` trong registry (~/.hermes/a2a_agents.json)
=> Người thật gõ y nguyên envelope cũng không giả được (vì điều kiện 2). Bot lạ chưa có trong
   registry bị coi là KHÔNG RÕ danh tính: không thi hành, ghi log, báo chủ.

Lệnh:
    agents                                   in registry
    envelope --from X --to Y [--text T]      in chuỗi đã bọc (để dán tay khi cần)
    send --to Y (--text T | --file F) [--space S] [--thread TH]
                                             tự bọc envelope rồi gửi vào space
    parse "<text>"                           đọc envelope → JSON (dùng khi quét lại space)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HH = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
REGISTRY = HH / "a2a_agents.json"
SELF = (os.environ.get("A2A_SELF")
        or ((HH / "a2a_self.txt").read_text(encoding="utf-8").strip()
            if (HH / "a2a_self.txt").exists() else "")
        or "ultron")     # tên bot đang chạy script này (mỗi máy 1 file a2a_self.txt)
GCHAT_REPLY = HH / "scripts" / "gchat_reply.py"

ENV_RE = re.compile(r"^\[\[A2A:v(\d+)\s+from=([a-z0-9_\-]+)\s+to=([a-z0-9_\-*]+)\]\]\s*", re.IGNORECASE)
# Dấu cũ (đã triển khai 2026-09-11, chỉ 2 bot) — vẫn nhận để tin đang xếp hàng không mất.
LEGACY = {"[[ULT2KIT]]": ("ultron", "kitty"), "[[KIT2ULT]]": ("kitty", "ultron")}


def load_registry() -> dict:
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"space": "", "agents": {}}


def agent_id(name: str) -> str:
    return ((load_registry().get("agents") or {}).get(name) or {}).get("id", "")


def build_envelope(sender: str, recipient: str, text: str) -> str:
    return f"[[A2A:v1 from={sender} to={recipient}]] {text}"


def parse(text: str, sender_id: str = "") -> dict:
    """Đọc envelope ở đầu message. Trả {'ok', 'from', 'to', 'version', 'body', 'reason'}."""
    text = (text or "").lstrip()
    m = ENV_RE.match(text)
    if m:
        ver, frm, to = m.group(1), m.group(2).lower(), m.group(3).lower()
        body = text[m.end():].strip()
        out = {"ok": True, "version": int(ver), "from": frm, "to": to, "body": body, "legacy": False}
    else:
        hit = next((k for k in LEGACY if text.startswith(k)), None)
        if not hit:
            return {"ok": False, "reason": "không có envelope A2A ở đầu message"}
        frm, to = LEGACY[hit]
        out = {"ok": True, "version": 0, "from": frm, "to": to,
               "body": text[len(hit):].strip(), "legacy": True}
    # điều kiện 2: user id phải khớp tên `from`
    if sender_id:
        expected = agent_id(out["from"])
        if not expected:
            out.update(ok=False, reason=f"'{out['from']}' chưa có trong registry — bot lạ, không thi hành")
        elif expected != sender_id:
            out.update(ok=False, reason="user id người gửi KHÔNG khớp tên from → coi là tin người/giả mạo")
        else:
            out["sender_verified"] = True
    elif out["from"] not in (load_registry().get("agents") or {}):
        out.update(ok=False, reason=f"'{out['from']}' chưa có trong registry")
    return out


def cmd_agents(_a) -> int:
    r = load_registry()
    print("space mặc định:", r.get("space") or "(chưa đặt)")
    for name, meta in (r.get("agents") or {}).items():
        print(f"  {name:10s} {meta.get('id')}  ({meta.get('owner') or '—'})")
    return 0


def cmd_envelope(a) -> int:
    print(build_envelope(a.sender, a.to, a.text or ""))
    return 0


def cmd_parse(a) -> int:
    print(json.dumps(parse(a.text, a.sender_id or ""), ensure_ascii=False, indent=2))
    return 0


def cmd_send(a) -> int:
    target = agent_id(a.to)
    if not target:
        print(f"ERROR: '{a.to}' không có trong registry {REGISTRY}", file=sys.stderr)
        return 2
    body = a.text or ""
    if a.file:
        body = Path(a.file).read_text(encoding="utf-8")
    if not body.strip():
        print("ERROR: không có nội dung", file=sys.stderr)
        return 2
    space = a.space or load_registry().get("space") or ""
    if not space:
        print("ERROR: thiếu --space và registry không có space mặc định", file=sys.stderr)
        return 2
    wrapped = build_envelope(SELF, a.to.lower(), body.strip())
    tmp = HH / "tmp_a2a_send.txt"
    tmp.write_text(wrapped, encoding="utf-8")
    cmd = [sys.executable, str(GCHAT_REPLY), "--space", space, "--file", str(tmp)]
    if a.thread:
        cmd += ["--thread", a.thread]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "").strip()
    print(out or r.stderr.strip()[:200])
    return 0 if out.startswith("OK") else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="A2A envelope cho tin giữa các app bot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("agents")
    p_env = sub.add_parser("envelope")
    p_env.add_argument("--from", dest="sender", default=SELF)
    p_env.add_argument("--to", required=True)
    p_env.add_argument("--text", default="")
    p_par = sub.add_parser("parse")
    p_par.add_argument("text")
    p_par.add_argument("--sender-id", default="")
    p_snd = sub.add_parser("send")
    p_snd.add_argument("--to", required=True)
    p_snd.add_argument("--text", default="")
    p_snd.add_argument("--file", default="")
    p_snd.add_argument("--space", default="")
    p_snd.add_argument("--thread", default="")
    a = ap.parse_args()
    return {"agents": cmd_agents, "envelope": cmd_envelope, "parse": cmd_parse, "send": cmd_send}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
