#!/usr/bin/env python3
"""Cổng "nói" cho Siri: nhận lệnh thoại → chuyển cho Ultron → ĐỢI câu trả lời → trả text cho Siri đọc.

Vì sao đi qua FILE chứ không qua tin nhắn Chat: webhook của Hermes trả 202 ngay (bất đồng bộ),
nên cổng phải tự đi lấy câu trả lời. Trước đây lấy bằng cách đọc tin bot trong DM ⇒ câu trả lời
hiện ra trong chat. Hoàng chốt 2026-09-12: "Không cần phải show các response của em với siri ở đây"
⇒ route `siri` để `deliver: "log"` (chỉ ghi log, KHÔNG gửi lên Chat) và Ultron ghi câu trả lời
cuối cùng vào file outbox dưới đây. Cổng đọc file, trả cho Siri; DM/group không thấy gì.

    POST /siri/say     header X-Gitlab-Token: <token>   body: {"text": "..."} (hoặc text thô)
        → 200 JSON {"status":"ok|timeout|empty|error","text":"...","waited_s":<float>,"echo":"..."}
          (?format=text → text thô)
    GET  /health       → "ok"

Bảo mật: chỉ mở trong tailnet (bind IP Tailscale), bắt buộc token, chặn body > 8KB.
Không log token hay nội dung lệnh.
"""
from __future__ import annotations

import hmac
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()

TOKEN_PATH = HOME / ".hermes" / "state" / "siri_token.txt"
OUTBOX_PATH = HOME / ".hermes" / "state" / "siri_outbox.json"   # Ultron ghi câu trả lời ở đây


def _tailnet_ip() -> str:
    """IP tailnet hiện tại. Node tạo lại là IP đổi ⇒ đọc từ state, KHÔNG gắn cứng."""
    try:
        ip = (Path.home() / ".hermes" / "state" / "tailnet_ip.txt").read_text().strip()
    except Exception:
        ip = ""
    return ip or os.environ.get("TAILNET_IP") or "100.120.110.26"


TS_IP = _tailnet_ip()
BIND_HOST = TS_IP               # IP Tailscale — chỉ trong tailnet
PORT = 9444
UPSTREAM = f"http://{TS_IP}:9443/webhooks/siri"
MAX_BODY = 8192
WAIT_SECONDS = 25.0  # iOS/Siri tự cắt sau ~30s ⇒ chờ 25s để không trả "request timeout" ở phía điện thoại
POLL_EVERY = 0.7
TIMEOUT_MSG = "Still working on it — ask me again in a moment."


def read_token() -> str:
    return TOKEN_PATH.read_text().strip()


def wait_outbox(started: float, deadline: float) -> str:
    """Chờ file outbox Ultron ghi câu trả lời cho phiên Siri này.

    Chỉ nhận file được ghi SAU khi lệnh được gửi (`started`) để không nhặt lại câu trả lời cũ.
    """
    while time.time() < deadline:
        try:
            if OUTBOX_PATH.exists():
                data = json.loads(OUTBOX_PATH.read_text(encoding="utf-8")) or {}
                text = str(data.get("text", "")).strip()
                if text and float(data.get("ts") or 0) >= started - 2:
                    return text
        except Exception as exc:  # noqa: BLE001 — file đang ghi dở/lỗi JSON thì thử lượt sau
            sys.stderr.write(f"[siri-speak] đọc outbox lỗi: {type(exc).__name__}\n")
        time.sleep(POLL_EVERY)
    return ""


def clear_outbox() -> None:
    try:
        OUTBOX_PATH.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[siri-speak] xoá outbox lỗi: {type(exc).__name__}\n")


def forward(text: str, token: str) -> int:
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        UPSTREAM, data=payload,
        headers={"Content-Type": "application/json", "X-Gitlab-Token": token}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status


class Handler(BaseHTTPRequestHandler):
    server_version = "siri-speak/4.0"

    def _reply(self, code: int, body: str, ctype: str = "text/plain; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _reply_result(self, status: str, text: str, **extra) -> None:
        """Mặc định trả JSON (để Shortcuts bắt key 'text'); ?format=text thì trả text thô."""
        self._reply(200, text) if "format=text" in self.path else self._reply(
            200, json.dumps({"status": status, "text": text, **extra}, ensure_ascii=False),
            "application/json; charset=utf-8")

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        sys.stderr.write("[siri-speak] %s\n" % (fmt % args))

    def do_GET(self) -> None:  # noqa: N802
        self._reply(200, "ok") if self.path.split("?")[0] in ("/health", "/") else self._reply(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?")[0] != "/siri/say":
            self._reply(404, "not found")
            return
        try:
            token = read_token()
        except Exception as exc:  # noqa: BLE001
            self._reply(500, f"token error: {exc}")
            return
        if not hmac.compare_digest(self.headers.get("X-Gitlab-Token", "") or "", token):
            self._reply(401, "bad token")
            return
        raw = self.rfile.read(min(int(self.headers.get("Content-Length") or 0), MAX_BODY))
        text = ""
        try:
            if "json" in (self.headers.get("Content-Type") or "").lower():
                text = str((json.loads(raw.decode("utf-8")) or {}).get("text", "")).strip()
            else:
                text = raw.decode("utf-8", "replace").strip()
        except Exception:  # noqa: BLE001
            text = raw.decode("utf-8", "replace").strip()
        if not text:
            self._reply_result("empty", "I didn't get any command.")
            return

        started = time.time()
        clear_outbox()          # dọn câu trả lời của lượt trước, tránh đọc nhầm
        try:
            status = forward(text, token)
        except Exception as exc:  # noqa: BLE001
            self._reply(502, json.dumps(
                {"status": "error", "text": "I couldn't reach Ultron just now."},
                ensure_ascii=False), "application/json; charset=utf-8")
            sys.stderr.write(f"[siri-speak] lỗi forward: {exc}\n")
            return
        answer = wait_outbox(started, started + WAIT_SECONDS)
        waited = round(time.time() - started, 1)
        sys.stderr.write(f"[siri-speak] fwd={status} len(text)={len(text)} "
                         f"wait={waited}s answer={'yes' if answer else 'timeout'}\n")
        if answer:
            self._reply_result("ok", answer, waited_s=waited, echo=text)
        else:
            self._reply_result("timeout", TIMEOUT_MSG, waited_s=waited, echo=text)


def main() -> int:
    try:
        srv = ThreadingHTTPServer((BIND_HOST, PORT), Handler)
    except OSError as exc:
        sys.stderr.write(f"[siri-speak] không bind được {BIND_HOST}:{PORT} — {exc}\n")
        return 1
    sys.stderr.write(f"[siri-speak] nghe tại http://{BIND_HOST}:{PORT}/siri/say\n")
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
