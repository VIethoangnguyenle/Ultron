#!/usr/bin/env python3
"""Cổng "nói" cho Siri: nhận lệnh thoại → chuyển cho Ultron → ĐỢI câu trả lời → trả text cho Siri đọc.

Vì sao đi qua FILE chứ không qua tin nhắn Chat: webhook của Hermes trả 202 ngay (bất đồng bộ),
nên cổng phải tự đi lấy câu trả lời. Trước đây lấy bằng cách đọc tin bot trong DM ⇒ câu trả lời
hiện ra trong chat. Hoàng chốt 2026-09-12: "Không cần phải show các response của em với siri ở đây"
⇒ route `siri` để `deliver: "log"` (chỉ ghi log, KHÔNG gửi lên Chat) và Ultron ghi câu trả lời
cuối cùng vào file outbox dưới đây. Cổng đọc file, trả cho Siri; DM/group không thấy gì.

    POST /siri/say     header X-Gitlab-Token: <token>   body: {"text": "...", "wait": <giây>}
        → 200 JSON {"status":"ok|timeout|empty|error","text":"...","waited_s":<float>,"echo":"..."}
          (?format=text → text thô)
    GET  /health       → "ok"

Bắt tay với Ultron (req_id):
cổng sinh `req_id` ngẫu nhiên cho TỪNG lượt và gửi kèm payload; chỉ nhận outbox có ĐÚNG `req_id`
đó, và nhận xong thì CLAIM (xoá file) nên không bao giờ trả lại câu cũ. Outbox thiếu/sai `req_id`
bị coi như chưa có câu trả lời — không có đường nào để câu trả lời của lượt khác lọt sang đây.

Mạng: cổng LUÔN nghe ở 127.0.0.1:9444 nên sống cả khi máy không có node Tailscale; dò được IP
tailnet thì nghe THÊM ở đó để client cũ gọi http://ultron:9444 y như trước. Watchdog dò lại IP
mỗi 25s: node dựng lại đổi IP thì listener phụ tự đổi theo, không cần restart tay. Forward lên
gateway thử 127.0.0.1:9443 trước rồi mới tới IP tailnet (gateway có thể bind kiểu nào cũng tới).

Bảo mật: token client (state/siri_token.txt) KHÁC secret route webhook (đọc từ
webhook_subscriptions.json) — token lọt từ điện thoại không gọi thẳng được vào gateway.
Chặn Content-Length rác (400), body > 8KB (413), body không phải JSON (400). Không log token
hay nội dung lệnh.
"""
from __future__ import annotations

import errno
import hmac
import json
import math
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()
STATE = HOME / ".hermes" / "state"

TOKEN_PATH = STATE / "siri_token.txt"            # token client (Shortcut của Hoàng) — KHÔNG đổi
SUBS_PATH = HOME / ".hermes" / "webhook_subscriptions.json"   # secret route (khác token client)
OUTBOX_PATH = STATE / "siri_outbox.json"         # Ultron ghi câu trả lời ở đây
HIST_PATH = STATE / "siri_history.log"

LOCAL_HOST = "127.0.0.1"          # cổng LUÔN nghe ở đây — không phụ thuộc Tailscale
PORT = int(os.environ.get("SIRI_SPEAK_PORT") or 9444)
GATEWAY_PORT = int(os.environ.get("SIRI_GATEWAY_PORT") or 9443)
ROUTE = "siri"
IP_FILE = STATE / "tailnet_ip.txt"
TAILNET_RETRY_SECONDS = 25.0      # watchdog dò lại IP tailnet / mở lại listener phụ
FAILOVER_TIMEOUT = 5.0            # chờ tối đa ở một địa chỉ gateway khi còn địa chỉ khác để thử
FAILOVER_ERRNOS = {errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ENETUNREACH,
                   errno.EADDRNOTAVAIL, errno.ECONNRESET}
MAX_BODY = 8192
MAX_CONCURRENT = 4                # Siri chỉ 1 client; chặn để không cạn thread khi bị spam
WAIT_SECONDS = 25.0  # iOS/Siri tự cắt sau ~30s ⇒ chờ 25s để không trả "request timeout" ở phía điện thoại
MAX_WAIT = 120.0
POLL_EVERY = 0.7
TIMEOUT_MSG = "Still working on it — ask me again in a moment."

_ip_lock = threading.Lock()
_tailnet_ip = ""                  # IP tailnet đang biết; "" = máy không có tailnet lúc này
_hist_lock = threading.Lock()
_slots = threading.BoundedSemaphore(MAX_CONCURRENT)


def log(msg: str) -> None:
    sys.stderr.write(f"[siri-speak {time.strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()


# --- tailnet: dò ĐỘNG, listener phụ tự đổi theo IP mới -------------------------------------

def probe_tailnet_ip() -> str:
    """IP tailnet THẬT lúc này: env (override để test) → node → file cache. "" = không có tailnet.

    Thứ tự cố ý đặt node TRƯỚC file: node dựng lại là IP đổi, mà file chỉ là cache của lần dò
    trước — đọc file trước thì IP cũ dính mãi và listener phụ trỏ vào địa chỉ đã chết.
    """
    env_ip = (os.environ.get("TAILNET_IP") or "").strip()
    if env_ip:
        return env_ip
    ip = ""
    try:
        out = subprocess.run(["docker", "exec", "tailscale", "tailscale", "ip", "-4"],
                             capture_output=True, text=True, timeout=10)
        lines = (out.stdout or "").strip().splitlines()
        ip = lines[0].strip() if lines else ""
    except Exception:  # noqa: BLE001 — không có docker/node thì coi như không có tailnet
        ip = ""
    if ip:
        try:
            IP_FILE.write_text(ip + "\n")
        except Exception:  # noqa: BLE001
            pass
        return ip
    try:
        cached = IP_FILE.read_text().strip()
    except Exception:  # noqa: BLE001
        return ""
    return cached if cached and ip_is_local(cached) else ""


def ip_is_local(ip: str) -> bool:
    """IP còn nằm trên một interface của máy này? (bind thử cổng 0 — không chiếm cổng nào)"""
    if not ip:
        return False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((ip, 0))
        return True
    except OSError:
        return False


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
    """Giữ listener PHỤ trên IP tailnet: node lên thì mở, IP đổi (hoặc IP cũ mất) thì đóng mở lại.

    Mọi lỗi ở đây chỉ ghi log — listener local (127.0.0.1) không dính gì, cổng vẫn phục vụ
    bình thường khi máy không có tailnet.
    """
    srv: ThreadingHTTPServer | None = None
    th: threading.Thread | None = None
    bound = ""
    while True:
        try:
            ip = probe_tailnet_ip()
            remember_tailnet_ip(ip)
            stale = bool(srv) and (
                (ip and ip != bound) or not ip_is_local(bound) or not (th and th.is_alive()))
            if stale:
                log(f"đóng listener tailnet {bound}:{PORT} (IP hiện tại: {ip or 'chưa có'})")
                try:
                    srv.shutdown()
                    srv.server_close()
                except Exception as exc:  # noqa: BLE001
                    log(f"đóng listener tailnet lỗi: {type(exc).__name__}: {exc}")
                srv, th, bound = None, None, ""
            if ip and not srv:
                srv, th = serve_on(ip, "tailnet")
                bound = ip
                log(f"nghe THÊM tại http://{ip}:{PORT}/siri/say")
        except OSError as exc:
            srv, th, bound = None, None, ""
            log(f"chưa mở được listener tailnet ({exc}) — local vẫn chạy, "
                f"thử lại sau {TAILNET_RETRY_SECONDS:.0f}s")
        except Exception as exc:  # noqa: BLE001
            log(f"watchdog tailnet lỗi: {type(exc).__name__}: {exc}")
        time.sleep(TAILNET_RETRY_SECONDS)


# --- forward lên gateway -------------------------------------------------------------------

def upstream_urls() -> list[str]:
    """Địa chỉ gateway theo thứ tự thử: loopback trước, IP tailnet sau.

    Gateway có thể bind loopback hoặc bind IP tailnet — thử lần lượt nên kiểu nào cũng tới,
    và KHÔNG phải sửa gì phía gateway.
    """
    out: list[str] = []
    for host in (LOCAL_HOST, tailnet_ip()):
        if not host:
            continue
        url = f"http://{host}:{GATEWAY_PORT}/webhooks/{ROUTE}"
        if url not in out:
            out.append(url)
    return out


def should_failover(exc: BaseException) -> bool:
    """Đúng khi KHÔNG chạm được tới địa chỉ đó ⇒ đáng thử địa chỉ kế tiếp."""
    if isinstance(exc, urllib.error.HTTPError):
        return False              # đã tới gateway, nó trả lỗi HTTP ⇒ đổi địa chỉ cũng vô ích
    err = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(err, TimeoutError):
        return True
    return isinstance(err, OSError) and err.errno in FAILOVER_ERRNOS


class UpstreamUnreachable(RuntimeError):
    """Không địa chỉ gateway nào nhận — lý do gom lại để trả ra client và ghi log ERROR."""


def read_token() -> str:
    """Token client (Shortcut trên iPhone). Đường dẫn KHÔNG đổi — Hoàng đang dùng."""
    return TOKEN_PATH.read_text().strip()


_secret_cache: tuple[float, str] = (0.0, "")


def route_secret() -> str:
    """Secret của route webhook — KHÁC token client, đọc live từ webhook_subscriptions.json.

    Cache theo mtime: file được gateway đọc lại live, đổi secret không cần restart cổng.
    """
    global _secret_cache
    mtime = SUBS_PATH.stat().st_mtime
    if _secret_cache[0] == mtime and _secret_cache[1]:
        return _secret_cache[1]
    data = json.loads(SUBS_PATH.read_text(encoding="utf-8"))
    secret = str(((data or {}).get(ROUTE) or {}).get("secret") or "").strip()
    if not secret:
        raise RuntimeError(f"route {ROUTE} chưa có secret")
    _secret_cache = (mtime, secret)
    return secret


def post_upstream(url: str, payload: bytes, secret: str, timeout: float) -> int:
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "X-Gitlab-Token": secret}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def forward(text: str, req_id: str) -> int:
    payload = json.dumps({"text": text, "req_id": req_id}).encode("utf-8")
    secret = route_secret()
    urls = upstream_urls()
    if not urls:
        raise UpstreamUnreachable("không có địa chỉ gateway nào để thử")
    problems: list[str] = []
    for idx, url in enumerate(urls):
        last = idx == len(urls) - 1
        try:
            return post_upstream(url, payload, secret, 15.0 if last else FAILOVER_TIMEOUT)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{url}: {getattr(exc, 'reason', exc)}")
            if not should_failover(exc):
                raise
            if not last:
                log(f"gateway {url} không nhận ({getattr(exc, 'reason', exc)}) — thử địa chỉ kế tiếp")
    raise UpstreamUnreachable("; ".join(problems))


# --- outbox: chỉ nhận đúng req_id, nhận xong thì CLAIM -------------------------------------

def claim_outbox(req_id: str, started: float) -> str:
    """Câu trả lời của ĐÚNG lượt này, và claim luôn (xoá file) để không trả lại lần sau.

    Đọc trước / claim sau: file có thể đang được Ultron ghi dở, parse lỗi thì để nguyên cho
    lượt poll kế tiếp, không cướp mất file đang ghi.
    """
    try:
        raw = OUTBOX_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except Exception as exc:  # noqa: BLE001
        log(f"đọc outbox lỗi: {type(exc).__name__}")
        return ""
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001 — đang ghi dở, thử lượt sau
        return ""
    if not isinstance(data, dict):
        log("outbox không phải JSON object — bỏ qua")
        return ""
    text = str(data.get("text") or "").strip()
    got = str(data.get("req_id") or "").strip()
    if not text or not hmac.compare_digest(got.encode("utf-8"), req_id.encode("utf-8")):
        return ""
    try:
        ts = float(data.get("ts") or 0)
    except (TypeError, ValueError):
        log("outbox có ts sai định dạng — bỏ qua bản ghi")
        return ""
    if ts < started - 2:
        return ""
    claimed = OUTBOX_PATH.with_name(f"siri_outbox.claim-{req_id}.json")
    try:
        os.replace(OUTBOX_PATH, claimed)
    except FileNotFoundError:
        return ""                # thread khác claim trước
    except Exception as exc:  # noqa: BLE001
        log(f"claim outbox lỗi: {type(exc).__name__}")
        return text
    try:
        claimed.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass
    return text


def wait_outbox(req_id: str, started: float, deadline: float) -> str:
    while time.time() < deadline:
        text = claim_outbox(req_id, started)
        if text:
            return text
        time.sleep(POLL_EVERY)
    return ""


def log_history(cmd: str, answer: str) -> None:
    """Ghi lại từng lượt Siri (lệnh thô + câu trả lời), giữ 40 dòng, ghi ATOMIC.

    Để lượt sau hiểu được mấy câu cụt kiểu "Send" / "Yes please" / "Finish now"
    là đang nói tiếp việc gì — dictation của Hoàng hay mất chữ.
    """
    line = "[%s] cmd=%r -> %r" % (time.strftime("%Y-%m-%d %H:%M:%S"), cmd, answer)
    with _hist_lock:
        try:
            try:
                lines = HIST_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            except FileNotFoundError:
                lines = []
            lines = (lines + [line])[-40:]
            tmp = HIST_PATH.with_name(f"{HIST_PATH.name}.tmp-{os.getpid()}")
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            os.replace(tmp, HIST_PATH)
        except Exception as exc:  # noqa: BLE001
            log(f"ghi history lỗi: {type(exc).__name__}")


# --- HTTP ---------------------------------------------------------------------------------

class BadRequest(Exception):
    """Đầu vào sai — mang sẵn mã HTTP để trả về, không để exception rơi ra làm đứt kết nối."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class Handler(BaseHTTPRequestHandler):
    server_version = "siri-speak/5.0"

    def _reply(self, code: int, body: str | bytes, ctype: str = "text/plain; charset=utf-8",
               close: bool = False) -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        if close:
            self.close_connection = True
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            if close:
                self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:  # noqa: BLE001 — client cắt kết nối giữa đường là chuyện thường
            log(f"không trả được response ({type(exc).__name__})")

    def _reply_json(self, code: int, obj: dict, close: bool = False) -> None:
        self._reply(code, json.dumps(obj, ensure_ascii=False),
                    "application/json; charset=utf-8", close=close)

    def _reply_result(self, status: str, text: str, **extra) -> None:
        """Mặc định trả JSON (để Shortcuts bắt key 'text'); ?format=text thì trả text thô."""
        if "format=text" in self.path:
            self._reply(200, text)
            return
        self._reply_json(200, {"status": status, "text": text, **extra})

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        log(fmt % args)

    def _authed(self) -> bool:
        try:
            expected = read_token().encode("utf-8")
        except Exception:  # noqa: BLE001 — KHÔNG lộ đường dẫn file token ra client
            log("không đọc được token client")
            self._reply(500, "token store unavailable", close=True)
            return False
        provided = (self.headers.get("X-Gitlab-Token") or "").encode("utf-8", "replace")
        if not hmac.compare_digest(provided, expected):
            self._reply(401, "bad token", close=True)
            return False
        return True

    def _read_body(self) -> bytes:
        """Body theo ĐÚNG Content-Length. Header rác ⇒ 400, quá to ⇒ 413 (không cắt cụt)."""
        raw_len = self.headers.get("Content-Length")
        if raw_len is None:
            return b""
        text = raw_len.strip()
        if not text.isdigit():
            raise BadRequest(400, "Content-Length không hợp lệ")
        length = int(text)
        if length > MAX_BODY:
            raise BadRequest(413, f"body quá lớn (tối đa {MAX_BODY} byte)")
        body = self.rfile.read(length)
        if len(body) != length:
            raise BadRequest(400, "body ngắn hơn Content-Length")
        return body

    def _parse(self, raw: bytes) -> tuple[str, float]:
        """JSON body → (text, wait). Không bao giờ lấy body thô làm lệnh gửi cho Ultron."""
        if not raw:
            return "", WAIT_SECONDS
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            raise BadRequest(400, "body phải là JSON") from None
        if not isinstance(body, dict):
            raise BadRequest(400, "JSON phải là object")
        text = str(body.get("text") or "").strip()
        return text, parse_wait(body.get("wait"), WAIT_SECONDS)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?")[0] in ("/health", "/"):
            self._reply(200, "ok")
            return
        self._reply(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?")[0] != "/siri/say":
            self._reply(404, "not found")
            return
        if not self._authed():
            return
        try:
            raw = self._read_body()
            text, wait_s = self._parse(raw)
        except BadRequest as bad:
            self._reply_json(bad.code, {"status": "error", "text": bad.message}, close=True)
            return
        except Exception as exc:  # noqa: BLE001
            log(f"đọc request lỗi: {type(exc).__name__}: {exc}")
            self._reply_json(400, {"status": "error", "text": "request không đọc được"}, close=True)
            return
        if not text:
            self._reply_result("empty", "I didn't get any command.")
            return
        if not _slots.acquire(blocking=False):
            self._reply_json(503, {"status": "error",
                                   "text": "Too many requests in flight, try again shortly."})
            return
        try:
            self._handle(text, wait_s)
        finally:
            _slots.release()

    def _handle(self, text: str, wait_s: float) -> None:
        req_id = secrets.token_hex(8)
        started = time.time()
        try:
            status = forward(text, req_id)
        except UpstreamUnreachable as exc:
            log(f"ERROR không tới được gateway nào ({', '.join(upstream_urls()) or 'không có địa chỉ'}): {exc}")
            self._reply_json(502, {"status": "error", "text": "I couldn't reach Ultron just now.",
                                   "reason": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            log(f"ERROR lỗi forward: {type(exc).__name__}: {exc}")
            self._reply_json(502, {"status": "error", "text": "I couldn't reach Ultron just now.",
                                   "reason": f"{type(exc).__name__}: {exc}"})
            return
        answer = wait_outbox(req_id, started, started + wait_s)
        waited = round(time.time() - started, 1)
        log(f"fwd={status} req={req_id} len(text)={len(text)} "
            f"wait={waited}s answer={'yes' if answer else 'timeout'}")
        log_history(text, answer or TIMEOUT_MSG)
        if answer:
            self._reply_result("ok", answer, waited_s=waited, echo=text)
            return
        self._reply_result("timeout", TIMEOUT_MSG, waited_s=waited, echo=text)


def parse_wait(value, default: float) -> float:
    """`wait` an toàn: rác/âm/NaN ⇒ 400; quá MAX_WAIT ⇒ kẹp về MAX_WAIT."""
    if value is None or value == "":
        return default
    try:
        wait = float(value)
    except (TypeError, ValueError):
        raise BadRequest(400, "wait phải là số giây") from None
    if math.isnan(wait) or math.isinf(wait) or wait <= 0:
        raise BadRequest(400, "wait phải là số dương")
    return min(wait, MAX_WAIT)


def main() -> int:
    try:
        srv = ThreadingHTTPServer((LOCAL_HOST, PORT), Handler)
    except OSError as exc:
        log(f"không bind được {LOCAL_HOST}:{PORT} — {exc}")
        return 1
    try:
        route_secret()
    except Exception as exc:  # noqa: BLE001 — chạy tiếp: secret có thể được thêm sau, forward sẽ báo lỗi
        log(f"CẢNH BÁO chưa đọc được secret route {ROUTE} ({type(exc).__name__}: {exc})")
    threading.Thread(target=tailnet_watchdog, name="tailnet-watchdog", daemon=True).start()
    log(f"nghe tại http://{LOCAL_HOST}:{PORT}/siri/say → gateway 127.0.0.1:{GATEWAY_PORT} "
        f"(fallback IP tailnet); listener tailnet: watchdog thử mỗi {TAILNET_RETRY_SECONDS:.0f}s")
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
