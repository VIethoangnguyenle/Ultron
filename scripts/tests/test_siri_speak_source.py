#!/usr/bin/env python3
"""Kiểm cờ nguồn + luật loa của siri_speak.py — chạy lại được, không đụng cổng :9444 thật.

    /home/zane/.hermes/hermes-agent/venv/bin/python tests/test_siri_speak_source.py

Cách dựng: chạy MỘT bản siri_speak.py riêng với HOME tạm (token/outbox/secret riêng), một
"gateway" giả nhận forward rồi ghi outbox, và một thư mục PATH tạm chứa edge-tts/ffmpeg/
paplay/ffplay GIẢ — mọi lệnh audio chạm vào đều để lại dấu vết trong một file. Nhờ vậy câu
"nguồn phone KHÔNG phát loa" kiểm được bằng chứng cứ: file dấu vết không hề sinh ra.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "siri_speak.py"
PYTHON = "/home/zane/.hermes/hermes-agent/venv/bin/python"
TOKEN = "test-client-token"
SECRET = "test-route-secret"
ANSWER_VI = "Đã xong việc rồi anh nhé."
SPEAK_WAIT = 8.0          # chờ tối đa thread nền phát xong
QUIET_WAIT = 4.0          # chờ để CHẮC CHẮN nguồn phone không phát gì

failures: list[str] = []
checks = 0


def check(ok: bool, name: str, detail: str = "") -> None:
    global checks
    checks += 1
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(f"{name} [{detail}]")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --- gateway giả: nhận forward, ghi outbox cho đúng req_id -----------------------------------

class FakeGateway:
    def __init__(self, outbox: Path):
        self.outbox = outbox
        self.payloads: list[dict] = []
        self.answer = ANSWER_VI
        self.port = free_port()
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # im lặng
                pass

            def do_POST(self):  # noqa: N802
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception:
                    payload = {"_unparseable": raw.decode("utf-8", "replace")}
                outer.payloads.append(payload)
                outer.outbox.write_text(json.dumps(
                    {"text": outer.answer, "req_id": payload.get("req_id", ""),
                     "ts": time.time()}), encoding="utf-8")
                body = b'{"status":"accepted"}'
                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.srv = ThreadingHTTPServer(("127.0.0.1", self.port), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()


# --- PATH giả: mọi lệnh audio đều để lại dấu vết ---------------------------------------------

SHIM_RECORD = '#!/bin/bash\nprintf "%s" "{name}" >> "{trace}"\nfor a in "$@"; do printf " %s" "$a" >> "{trace}"; done\nprintf "\\n" >> "{trace}"\n'
SHIM_MAKE_MEDIA = 'out=""\nprev=""\nfor a in "$@"; do\n  [ "$prev" = "--write-media" ] && out="$a"\n  prev="$a"\ndone\n[ -n "$out" ] && printf FAKEMP3 > "$out"\n'
SHIM_MAKE_LAST = 'for a in "$@"; do last="$a"; done\nprintf FAKEWAV > "$last"\n'


def make_shims(bindir: Path, trace: Path) -> None:
    bodies = {"edge-tts": SHIM_MAKE_MEDIA, "ffmpeg": SHIM_MAKE_LAST, "paplay": "", "ffplay": ""}
    for name, extra in bodies.items():
        path = bindir / name
        path.write_text(SHIM_RECORD.format(name=name, trace=trace) + extra + "exit 0\n")
        path.chmod(0o755)


# --- client -----------------------------------------------------------------------------------

def call(port: int, path: str = "/siri/say", body: dict | None = None, token: str = TOKEN,
         headers: dict | None = None, raw: bytes | None = None, timeout: float = 30.0):
    data = raw if raw is not None else json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "X-Gitlab-Token": token, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def wait_for(predicate, limit: float) -> bool:
    end = time.time() + limit
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.2)
    return False


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="siri-speak-test-"))
    home = tmp / "home"
    state = home / ".hermes" / "state"
    state.mkdir(parents=True)
    (state / "siri_token.txt").write_text(TOKEN + "\n")
    (home / ".hermes" / "webhook_subscriptions.json").write_text(json.dumps(
        {"siri": {"secret": SECRET}}))
    outbox = state / "siri_outbox.json"
    trace = tmp / "audio-trace.txt"
    bindir = tmp / "bin"
    bindir.mkdir()
    make_shims(bindir, trace)

    gw = FakeGateway(outbox)
    port = free_port()
    logfile = tmp / "server.log"
    env = {**os.environ,
           "HOME": str(home),
           "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
           "SIRI_SPEAK_PORT": str(port),
           "SIRI_GATEWAY_PORT": str(gw.port)}
    log_fh = open(logfile, "wb")
    proc = subprocess.Popen([PYTHON, str(SCRIPT)], env=env, stdout=log_fh, stderr=log_fh)
    try:
        ready = wait_for(lambda: _health(port), 15.0)
        if not ready:
            print("KHÔNG dựng được cổng test:\n" + logfile.read_text(errors="replace"))
            return 2
        print(f"\ncổng test :{port} → gateway giả :{gw.port}, PATH giả {bindir}\n")
        run_checks(port, gw, trace, logfile, outbox)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_fh.close()
        gw.stop()

    print(f"\n{checks - len(failures)}/{checks} PASS")
    for line in failures:
        print(f"  FAIL: {line}")
    print(f"(log cổng test: {logfile})")
    return 1 if failures else 0


def _health(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def run_checks(port: int, gw: FakeGateway, trace: Path, logfile: Path, outbox: Path) -> None:
    # === a. ba cách gửi cờ + mặc định + giá trị lạ ===========================================
    print("a. nhận cờ nguồn")
    for name, kwargs in (
            ("query  ?source=desktop", {"path": "/siri/say?source=desktop", "body": {"text": "q"}}),
            ("JSON   \"source\"", {"body": {"text": "j", "source": "desktop"}}),
            ("header X-Ultron-Source", {"body": {"text": "h"},
                                        "headers": {"X-Ultron-Source": "DeskTop "}})):
        code, body = call(port, **kwargs)
        got = json.loads(body)
        check(code == 200 and got.get("source") == "desktop", f"{name} ⇒ source=desktop",
              f"{code} {got.get('source')!r}")
        wait_for(lambda: trace.exists(), SPEAK_WAIT)
        trace.unlink(missing_ok=True)

    code, body = call(port, body={"text": "không cờ"})
    check(json.loads(body).get("source") == "phone", "thiếu cờ ⇒ phone", body[:80])

    code, body = call(port, body={"text": "cờ lạ", "source": "tivi"})
    check(json.loads(body).get("source") == "phone", "giá trị lạ ⇒ phone", body[:80])
    check("nguồn lạ" in logfile.read_text(errors="replace"), "giá trị lạ ⇒ có 1 dòng log")

    code, body = call(port, body={"text": "x", "wait": "rác"})
    check(code == 400, "wait rác vẫn 400 như cũ", str(code))
    code, body = call(port, body={"text": "x", "wait": 3, "source": "desktop"})
    check(code == 200, "wait hợp lệ + cờ ⇒ vẫn 200", str(code))
    wait_for(lambda: trace.exists(), SPEAK_WAIT)
    trace.unlink(missing_ok=True)

    # === 2. cờ có đi lên gateway không ========================================================
    print("\n2. forward mang theo source")
    sent = gw.payloads[-1]
    check(sent.get("source") == "desktop" and sent.get("text") == "x" and bool(sent.get("req_id")),
          "payload forward = text + req_id + source", json.dumps(sent, ensure_ascii=False)[:120])
    phone_sent = [p for p in gw.payloads if p.get("source") == "phone"]
    check(bool(phone_sent), "lượt không cờ forward source=phone")

    # === b. BẰNG CHỨNG: phone KHÔNG phát, desktop CÓ phát =====================================
    print("\nb. chứng minh chỉ desktop mới chạm tới lệnh audio")
    trace.unlink(missing_ok=True)
    code, body = call(port, body={"text": "lượt điện thoại"})
    check(code == 200 and json.loads(body)["status"] == "ok", "lượt phone trả lời bình thường")
    quiet = not wait_for(lambda: trace.exists(), QUIET_WAIT)
    check(quiet, f"phone: KHÔNG có dấu vết audio sau {QUIET_WAIT:.0f}s",
          "" if quiet else trace.read_text(errors="replace")[:200])

    code, body = call(port, path="/siri/say?source=desktop", body={"text": "lượt desktop"})
    check(wait_for(lambda: trace.exists(), SPEAK_WAIT), "desktop: CÓ dấu vết audio")
    marks = trace.read_text(errors="replace") if trace.exists() else ""
    check("edge-tts" in marks, "desktop: gọi edge-tts", marks.splitlines()[:1])
    check("paplay" in marks, "desktop: gọi paplay", [ln[:60] for ln in marks.splitlines()])
    check("vi-VN-NamMinhNeural" in marks, "câu trả lời có dấu ⇒ giọng vi-VN-NamMinhNeural")

    # giọng Anh cho câu không dấu
    gw.answer = "All done, boss."
    trace.unlink(missing_ok=True)
    call(port, body={"text": "english turn", "source": "desktop"})
    wait_for(lambda: trace.exists(), SPEAK_WAIT)
    marks = trace.read_text(errors="replace") if trace.exists() else ""
    check("en-US" in marks, "câu không dấu ⇒ giọng en-US", marks[:120])
    gw.answer = ANSWER_VI

    # === c. bảo mật cũ không vỡ ==============================================================
    print("\nc. bảo mật cũ")
    code, _ = call(port, body={"text": "x"}, token="sai-token")
    check(code == 401, "không đúng token ⇒ 401", str(code))
    code, _ = call(port, path="/siri/say?source=desktop", body={"text": "x"}, token="")
    check(code == 401, "token rỗng ⇒ 401 (cờ nguồn không mở đường vòng)", str(code))
    code, _ = call(port, path="/../../etc/passwd", body={"text": "x"})
    check(code == 404, "path traversal ⇒ 404", str(code))
    code, _ = call(port, path="/siri/say/../../etc/passwd", body={"text": "x"})
    check(code == 404, "traversal dưới /siri/say ⇒ 404", str(code))
    big = json.dumps({"text": "x" * 9000}).encode()
    code, _ = call(port, raw=big)
    check(code == 413, "body > 8KB ⇒ 413", str(code))
    code, _ = call(port, raw=b"khong-phai-json")
    check(code == 400, "body không phải JSON ⇒ 400", str(code))

    print("\nc2. trường lạ không lọt vào câu lệnh")
    trace.unlink(missing_ok=True)
    evil = "$(touch /tmp/siri-speak-pwn)"
    call(port, body={"text": "injection", "source": "desktop", "voice": evil,
                     "cmd": "; rm -rf /tmp/nothing", "player": "/bin/sh"})
    wait_for(lambda: trace.exists(), SPEAK_WAIT)
    marks = trace.read_text(errors="replace") if trace.exists() else ""
    check(evil not in marks and "rm -rf" not in marks and "/bin/sh" not in marks,
          "field lạ trong body KHÔNG xuất hiện trong lệnh audio", marks[:160])
    check(not Path("/tmp/siri-speak-pwn").exists(), "không có lệnh nào bị shell diễn giải")
    evil_src = "desktop; touch /tmp/siri-speak-pwn2"
    _, body = call(port, body={"text": "injection2", "source": evil_src})
    check(json.loads(body).get("source") == "phone", "source rác ⇒ phone (không thành lệnh)")
    check(not Path("/tmp/siri-speak-pwn2").exists(), "source rác không sinh tiến trình")


if __name__ == "__main__":
    raise SystemExit(main())
