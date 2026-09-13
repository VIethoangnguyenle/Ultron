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

Mạng (2026-09-13, Hoàng chốt "cứ online ở local, tailscale mở thì forward về domain ultron"):
cổng LUÔN nghe ở 127.0.0.1:9444 nên sống cả khi máy không có node Tailscale; dò được IP tailnet
thì nghe THÊM ở đó để client cũ gọi http://ultron:9444 y như trước. Listener tailnet hỏng/IP đổi
chỉ ghi log — watchdog nền mở lại, listener local không bao giờ chết theo.

Bảo mật: bắt buộc token, chặn body > 8KB. Không log token hay nội dung lệnh.
"""
from __future__ import annotations

import errno
import hmac
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()

TOKEN_PATH = HOME / ".hermes" / "state" / "siri_token.txt"
OUTBOX_PATH = HOME / ".hermes" / "state" / "siri_outbox.json"   # Ultron ghi câu trả lời ở đây


LOCAL_HOST = "127.0.0.1"          # cổng LUÔN nghe ở đây — không phụ thuộc Tailscale
PORT = int(os.environ.get("SIRI_SPEAK_PORT") or 9444)
GATEWAY_PORT = 9443
ROUTE = "siri"
IP_FILE = HOME / ".hermes" / "state" / "tailnet_ip.txt"
TAILNET_RETRY_SECONDS = 25.0      # watchdog dò lại IP tailnet / mở lại listener phụ
FAILOVER_TIMEOUT = 5.0            # chờ tối đa ở một địa chỉ gateway khi còn địa chỉ khác để thử
FAILOVER_ERRNOS = {errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ENETUNREACH,
                   errno.EADDRNOTAVAIL, errno.ECONNRESET}
MAX_BODY = 8192
WAIT_SECONDS = 25.0  # iOS/Siri tự cắt sau ~30s ⇒ chờ 25s để không trả "request timeout" ở phía điện thoại
POLL_EVERY = 0.7
TIMEOUT_MSG = "Still working on it — ask me again in a moment."

_ip_lock = threading.Lock()
_tailnet_ip = ""                  # IP tailnet đang biết; "" = máy không có tailnet lúc này


def detect_tailnet_ip() -> str:
    """IP tailnet hiện tại: env → state file → hỏi node. Trả "" khi không có node.

    KHÔNG fallback 127.0.0.1 như bản cũ: loopback đã có listener riêng, nên "" ở đây nghĩa là
    "chưa có tailnet", không phải "dùng localhost".
    """
    ip = (os.environ.get("TAILNET_IP") or "").strip()
    if not ip:
        try:
            ip = IP_FILE.read_text().strip()
        except Exception:  # noqa: BLE001
            ip = ""
    if not ip:
        try:
            out = subprocess.run(["docker", "exec", "tailscale", "tailscale", "ip", "-4"],
                                 capture_output=True, text=True, timeout=10)
            ip = (out.stdout or "").strip().splitlines()[0] if out.stdout.strip() else ""
        except Exception:  # noqa: BLE001
            ip = ""
    if ip:
        try:
            IP_FILE.write_text(ip + "\n")
        except Exception:  # noqa: BLE001
            pass
    return ip


def tailnet_ip() -> str:
    with _ip_lock:
        return _tailnet_ip


def remember_tailnet_ip(ip: str) -> None:
    global _tailnet_ip
    with _ip_lock:
        _tailnet_ip = ip


def serve_on(host: str, tag: str) -> tuple[ThreadingHTTPServer, threading.Thread]:
    """Bind + phục vụ trong thread nền. Ném OSError nếu không bind được."""
    srv = ThreadingHTTPServer((host, PORT), Handler)
    th = threading.Thread(target=srv.serve_forever, name=f"http-{tag}", daemon=True)
    th.start()
    return srv, th


def tailnet_watchdog() -> None:
    """Giữ listener PHỤ trên IP tailnet: node lên thì mở, IP đổi thì đóng cái cũ mở cái mới.

    Node tắt (dò ra "") thì GIỮ NGUYÊN listener cũ: socket trỏ IP đã mất là vô hại và dùng lại
    được khi node quay lại đúng IP. Mọi lỗi ở đây chỉ log — listener local không dính gì.
    """
    srv: ThreadingHTTPServer | None = None
    th: threading.Thread | None = None
    bound = ""
    while True:
        try:
            ip = detect_tailnet_ip()
            remember_tailnet_ip(ip or bound)
            if srv and ((ip and ip != bound) or not th.is_alive()):
                sys.stderr.write(f"[siri-speak] đóng listener tailnet {bound}:{PORT} (IP mới: {ip or 'chưa có'})\n")
                srv.shutdown()
                srv.server_close()
                srv, th, bound = None, None, ""
            if ip and not srv:
                srv, th = serve_on(ip, "tailnet")
                bound = ip
                sys.stderr.write(f"[siri-speak] nghe THÊM tại http://{ip}:{PORT}/siri/say\n")
        except OSError as exc:
            srv, th, bound = None, None, ""
            sys.stderr.write(f"[siri-speak] chưa mở được listener tailnet ({exc}) — "
                             f"local vẫn chạy, thử lại sau {TAILNET_RETRY_SECONDS:.0f}s\n")
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"[siri-speak] watchdog tailnet lỗi: {type(exc).__name__}: {exc}\n")
        time.sleep(TAILNET_RETRY_SECONDS)


def upstream_urls() -> list[str]:
    """Địa chỉ gateway theo thứ tự thử: loopback trước, IP tailnet sau.

    Gateway có thể bind loopback hoặc bind IP tailnet — thử lần lượt nên kiểu nào cũng tới.
    """
    out = []
    for host in (LOCAL_HOST, tailnet_ip()):
        url = f"http://{host}:{GATEWAY_PORT}/webhooks/{ROUTE}"
        if host and url not in out:
            out.append(url)
    return out


def should_failover(exc: OSError) -> bool:
    """Đúng khi KHÔNG chạm được tới địa chỉ đó ⇒ đáng thử địa chỉ kế tiếp."""
    if isinstance(exc, urllib.error.HTTPError):
        return False              # đã tới gateway, nó trả lỗi HTTP ⇒ đổi địa chỉ cũng vô ích
    err = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(err, TimeoutError):
        return True
    return isinstance(err, OSError) and err.errno in FAILOVER_ERRNOS


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


def post_upstream(url: str, payload: bytes, token: str, timeout: float) -> int:
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "X-Gitlab-Token": token}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def forward(text: str, token: str) -> int:
    payload = json.dumps({"text": text}).encode("utf-8")
    urls = upstream_urls()
    for idx, url in enumerate(urls):
        last = idx == len(urls) - 1
        try:
            return post_upstream(url, payload, token, 15.0 if last else FAILOVER_TIMEOUT)
        except OSError as exc:
            if last or not should_failover(exc):
                raise
            sys.stderr.write(f"[siri-speak] gateway {url} không nhận ({getattr(exc, 'reason', exc)}) "
                             f"— thử địa chỉ kế tiếp\n")
    raise OSError("không có địa chỉ gateway nào để thử")


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
        log_history(text, answer or TIMEOUT_MSG)
        if answer:
            self._reply_result("ok", answer, waited_s=waited, echo=text)
        else:
            self._reply_result("timeout", TIMEOUT_MSG, waited_s=waited, echo=text)


HIST = os.path.expanduser("~/.hermes/state/siri_history.log")


def log_history(cmd: str, answer: str) -> None:
    """Ghi lại từng lượt Siri (lệnh thô + câu trả lời), giữ 40 dòng.

    Để lượt sau hiểu được mấy câu cụt kiểu "Send" / "Yes please" / "Finish now"
    là đang nói tiếp việc gì — dictation của Hoàng hay mất chữ.
    """
    try:
        with open(HIST, "a", encoding="utf-8") as fh:
            fh.write("[%s] cmd=%r -> %r\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), cmd, answer))
        with open(HIST, encoding="utf-8") as fh:
            lines = fh.read().splitlines()[-40:]
        with open(HIST, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[siri-speak] ghi history lỗi: {type(exc).__name__}\n")


def main() -> int:
    try:
        srv = ThreadingHTTPServer((LOCAL_HOST, PORT), Handler)
    except OSError as exc:
        sys.stderr.write(f"[siri-speak] không bind được {LOCAL_HOST}:{PORT} — {exc}\n")
        return 1
    threading.Thread(target=tailnet_watchdog, name="tailnet-watchdog", daemon=True).start()
    sys.stderr.write(f"[siri-speak] nghe tại http://{LOCAL_HOST}:{PORT}/siri/say "
                     f"(listener tailnet: watchdog thử mỗi {TAILNET_RETRY_SECONDS:.0f}s)\n")
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
