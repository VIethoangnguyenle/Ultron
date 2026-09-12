#!/usr/bin/env python3
"""Cổng "nói" cho Siri: nhận lệnh thoại → chuyển cho Ultron → ĐỢI câu trả lời → trả text cho Siri đọc.

Vì sao cần: webhook của Hermes trả `{"status":"accepted"}` ngay (bất đồng bộ) và session webhook
bị giới hạn tool (không có write_file), nên không có cách nào lấy câu trả lời qua đường webhook.
Đường đi ở đây: cổng tự gửi lệnh sang webhook, rồi ĐỌC chính tin nhắn trả lời trong DM của Hoàng
(qua Chat API, token read-only) và trả nguyên văn cho Shortcuts đọc to.

    POST /siri/say     header X-Gitlab-Token: <token>   body: {"text": "..."} (hoặc text thô)
        → 200 text/plain: câu trả lời để Siri đọc
    GET  /health       → "ok"

Bảo mật: chỉ mở trong tailnet (bind IP Tailscale), bắt buộc token, chặn body > 8KB.
Không log token hay nội dung lệnh.
"""
from __future__ import annotations

import hmac
import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()
SCRIPTS = HOME / ".hermes" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import gchat_dump as gc  # noqa: E402 — dùng lại creds()/text_of() (token read-only của Hoàng)

TOKEN_PATH = HOME / ".hermes" / "state" / "siri_token.txt"
BIND_HOST = "100.120.110.26"   # IP Tailscale — chỉ trong tailnet
PORT = 9444
UPSTREAM = "http://100.120.110.26:9443/webhooks/siri"
OUTBOX_SPACE = "spaces/0dniIqAAAAE"      # DM Hoàng — kênh DUY NHẤT nhận câu trả lời Siri (nhãn 🎙); KHÔNG group
DM_SPACE = "spaces/0dniIqAAAAE"          # (giữ tên cũ cho tương thích; nay cùng đích)
MIC = "🎙"                               # nhãn phiên Siri — cổng lọc theo nhãn này để không nhặt nhầm chat thường
SEND_SCRIPT = SCRIPTS / "gchat_send_text.py"
VENV_PY = HOME / ".hermes" / "hermes-agent" / "venv" / "bin" / "python"
BOT_ID = "users/107189931083311611240"   # Ultron
MAX_BODY = 8192
WAIT_SECONDS = 50.0
POLL_EVERY = 1.2
SKEW = timedelta(seconds=3)              # trừ hao lệch đồng hồ giữa máy này và Google
TIMEOUT_MSG = "Em đang xử lý, kết quả sẽ về tin nhắn ạ."
SKIP_MARKERS = ("is thinking", "đang nghĩ")

_SVC = None


def read_token() -> str:
    return TOKEN_PATH.read_text().strip()


def service():
    global _SVC
    if _SVC is None:
        from googleapiclient.discovery import build
        _SVC = build("chat", "v1", credentials=gc.creds(), cache_discovery=False)
    return _SVC


def stamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def newest_bot_text(after: str, deadline: float) -> str:
    """Chờ tin trả lời của Ultron trong DM, mới hơn mốc `after`.

    Ưu tiên tin có nhãn 🎙 (đúng phiên Siri). Chỉ khi không có mới dùng tin bot khác
    làm phương án dự phòng — tránh nhặt nhầm câu trả lời của phiên chat thường.
    """
    fallback = ""
    while time.time() < deadline:
        try:
            page = service().spaces().messages().list(
                parent=OUTBOX_SPACE, pageSize=8, orderBy="createTime desc").execute()
            for m in page.get("messages") or []:
                if ((m.get("sender") or {}).get("name")) != BOT_ID:
                    continue
                if (m.get("createTime") or "") <= after:
                    continue
                txt = gc.text_of(m).strip()
                if not txt or any(k.lower() in txt.lower() for k in SKIP_MARKERS):
                    continue
                if txt.startswith(MIC):
                    return txt[len(MIC):].strip()
                if not fallback:
                    fallback = txt
        except Exception as exc:  # noqa: BLE001 — lỗi mạng/API thì thử lại lượt sau
            sys.stderr.write(f"[siri-speak] poll lỗi: {type(exc).__name__}\n")
        time.sleep(POLL_EVERY)
    return fallback


def forward(text: str, token: str) -> int:
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        UPSTREAM, data=payload,
        headers={"Content-Type": "application/json", "X-Gitlab-Token": token}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status


def mirror_to_dm(answer: str) -> None:
    """Gửi bản sao câu trả lời vào DM Hoàng — chạy nền, không làm chậm câu trả lời cho Siri."""
    path = ""
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
            fh.write("🎙 (Siri) " + answer)
            path = fh.name
        subprocess.run([str(VENV_PY), str(SEND_SCRIPT), "--space", DM_SPACE, "--text-file", path],
                       timeout=25, capture_output=True)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[siri-speak] mirror DM lỗi: {type(exc).__name__}\n")
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "siri-speak/3.0"

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
            self._reply(500, f"token lỗi: {exc}")
            return
        if not hmac.compare_digest(self.headers.get("X-Gitlab-Token", "") or "", token):
            self._reply(401, "sai token")
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
            self._reply_result("empty", "chưa nhận được nội dung lệnh")
            return

        started = time.time()
        marker = stamp(datetime.now(timezone.utc) - SKEW)
        try:
            status = forward(text, token)
        except Exception as exc:  # noqa: BLE001
            self._reply(502, json.dumps(
                {"status": "error", "text": "Không gửi được lệnh cho Ultron ạ."},
                ensure_ascii=False), "application/json; charset=utf-8")
            sys.stderr.write(f"[siri-speak] lỗi forward: {exc}\n")
            return
        answer = newest_bot_text(marker, started + WAIT_SECONDS)
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
