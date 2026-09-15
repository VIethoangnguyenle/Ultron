#!/usr/bin/env python3
"""Tick cron store của profile "jira-runner".

Vì sao tồn tại: gateway đang chạy với `gateway.multiplex_profiles = false`, nên nó chỉ tick
cron store của profile "default". Job nằm trong store của profile "jira-runner" do đó không
bao giờ tự tới hạn. Script này là cầu nối: dispatcher (chạy trong profile default) gọi nó,
nó gọi `hermes -p jira-runner cron tick` để chạy mọi job tới hạn của profile kia rồi thoát.

Im lặng khi không có gì tới hạn, để dispatcher không ghi log rác mỗi slot.
"""
import subprocess
import sys

HERMES = "/home/zane/.local/bin/hermes"
# Cờ -p tự lo profile — KHÔNG truyền HERMES_HOME, tránh ghi đè cách CLI tự phân giải home.
CMD = [HERMES, "-p", "jira-runner", "cron", "tick"]
TIMEOUT_S = 900


def decode(chunk) -> str:
    """Output dở dang của TimeoutExpired: None / bytes / str -> str."""
    if chunk is None:
        return ""
    return chunk.decode("utf-8", "replace") if isinstance(chunk, bytes) else chunk


def fail(msg: str, code: int, output: str) -> int:
    """Một dòng lỗi ra stderr cho dispatcher, kèm output của lệnh con."""
    print(f"jira_runner_tick: {msg} (exit={code})", file=sys.stderr)
    if output.strip():
        print(output.rstrip(), file=sys.stderr)
    return code if code != 0 else 1


def main() -> int:
    try:
        proc = subprocess.run(CMD, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        # Timeout: subprocess.run đã kill process con. Output dở dang có thể None/bytes/str.
        return fail(f"quá {TIMEOUT_S}s không xong", 124, decode(exc.stdout) + decode(exc.stderr))
    except OSError as exc:
        return fail(f"không chạy được {HERMES}: {exc}", 127, "")

    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return fail("hermes cron tick lỗi", proc.returncode, output)

    # Thành công: chỉ in khi lệnh con thực sự có nói gì (có job chạy).
    if output.strip():
        print(output.rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
