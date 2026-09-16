#!/usr/bin/env python3
"""Tick cron store của profile "jira-runner".

Vì sao tồn tại: gateway đang chạy với `gateway.multiplex_profiles = false`, nên nó chỉ tick
cron store của profile "default". Job nằm trong store của profile "jira-runner" do đó không
bao giờ tự tới hạn. Script này là cầu nối: dispatcher (chạy trong profile default) gọi nó,
nó gọi `hermes -p jira-runner cron tick` để chạy mọi job tới hạn của profile kia rồi thoát.

Im lặng khi không có gì tới hạn, để dispatcher không ghi log rác mỗi slot.

Cờ `--check`: chế độ chỉ-đọc, kiểm ba điều kiện (cron doctor sạch, job đã chạy hôm nay,
lượt chạy cuối kết thúc bình thường). Không tick, không ghi gì. Im lặng khi mọi thứ ổn;
một dòng ra stderr + exit 1 khi có điều kiện hỏng.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERMES = "/home/zane/.local/bin/hermes"
# Cờ -p tự lo profile — KHÔNG truyền HERMES_HOME, tránh ghi đè cách CLI tự phân giải home.
CMD = [HERMES, "-p", "jira-runner", "cron", "tick"]
TIMEOUT_S = 900

# --- phần dùng riêng cho --check ---
DOCTOR_CMD = [HERMES, "-p", "jira-runner", "cron", "doctor"]
DOCTOR_TIMEOUT_S = 120
JOBS_PATH = Path("/home/zane/.hermes/profiles/jira-runner/cron/jobs.json")
LOGS_DIR = Path("/home/zane/.hermes/profiles/jira-runner/logs")
# agent.log đã xoay vòng thì dòng cần tìm rơi sang agent.log.1 — thử lần lượt.
LOG_NAMES = ("agent.log", "agent.log.1")
JOB_NAME = "jira-morning-reminder"
TURN_MARKER = "Turn ended: reason="
GOOD_REASON = "text_response"
REASON_RE = re.compile(r"reason=([^\s(]+)")
DETAIL_MAX = 300


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


def run_tick() -> int:
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


def squeeze(text: str) -> str:
    """Nén mọi khoảng trắng về một dấu cách và cắt ngắn, để chi tiết luôn nằm gọn một dòng."""
    return re.sub(r"\s+", " ", text).strip()[:DETAIL_MAX]


def check_fail(condition: str, detail: str) -> int:
    """Đúng MỘT dòng ra stderr rồi thoát 1 — dispatcher gửi thẳng dòng này đi."""
    print(f"jira_runner_check: {condition} — {detail}", file=sys.stderr)
    return 1


def check_doctor():
    """Điều kiện 1: `cron doctor` phải thoát 0. Trả None nếu sạch, ngược lại là chi tiết lỗi."""
    try:
        proc = subprocess.run(DOCTOR_CMD, capture_output=True, text=True, timeout=DOCTOR_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return f"qua {DOCTOR_TIMEOUT_S}s khong xong"
    except OSError as exc:
        return squeeze(f"khong chay duoc {HERMES}: {exc}")

    if proc.returncode == 0:
        return None
    # Doctor nói gì thì đưa nguyên vào chi tiết; im lặng thì còn mỗi exit code.
    return squeeze((proc.stdout or "") + (proc.stderr or "")) or f"exit={proc.returncode}"


def load_job():
    """Tìm job theo name trong jobs.json. Trả None nếu store không có job đó."""
    data = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    for job in data.get("jobs") or []:
        if job.get("name") == JOB_NAME:
            return job
    return None


def check_ran_today(job) -> str:
    """Điều kiện 2: last_run_at quy về giờ máy phải rơi đúng ngày hôm nay."""
    raw = job.get("last_run_at")
    if not raw:
        return "job chua co last_run_at"

    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return squeeze(f"last_run_at khong doc duoc: {raw}")

    # Mốc có offset (+07:00) -> astimezone() đổi về giờ máy rồi mới so ngày.
    ran = stamp.astimezone().date() if stamp.tzinfo else stamp.date()
    today = datetime.now().date()
    if ran == today:
        return None
    return f"lan chay cuoi {ran.isoformat()}, hom nay {today.isoformat()}"


def last_turn_line(path: Path, marker: str):
    """Dòng "Turn ended" CUỐI CÙNG của đúng job này trong một file log; None nếu không có."""
    if not path.is_file():
        return None

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    for line in reversed(lines):
        if TURN_MARKER in line and marker in line:
            return line
    return None


def check_last_turn(job_id: str) -> str:
    """Điều kiện 3: reason của lượt chạy cuối phải là text_response. Không thấy dòng nào -> fail."""
    marker = f"session=cron_{job_id}_"
    for name in LOG_NAMES:
        line = last_turn_line(LOGS_DIR / name, marker)
        if line is None:
            continue

        match = REASON_RE.search(line)
        reason = match.group(1) if match else "?"
        if reason == GOOD_REASON:
            return None
        return f"luot chay cuoi reason={reason}"

    # Fail-closed: không có bằng chứng tốt thì coi như hỏng, đừng im lặng cho qua.
    return "khong co bang chung luot chay tot"


def run_check() -> int:
    detail = check_doctor()
    if detail:
        return check_fail("cron doctor", detail)

    try:
        job = load_job()
    except (OSError, ValueError) as exc:
        return check_fail("job chay hom nay", squeeze(f"khong doc duoc {JOBS_PATH}: {exc}"))

    if job is None:
        return check_fail("job chay hom nay", "khong tim thay job")

    detail = check_ran_today(job)
    if detail:
        return check_fail("job chay hom nay", detail)

    # Id lấy từ chính job vừa tìm được, không hardcode.
    detail = check_last_turn(str(job.get("id") or ""))
    if detail:
        return check_fail("luot chay cuoi", detail)

    return 0


def main(argv) -> int:
    parser = argparse.ArgumentParser(
        prog="jira_runner_tick.py",
        description="Tick cron store cua profile jira-runner; --check de kiem tra chi-doc.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Kiem 3 dieu kien (doctor sach, job chay hom nay, luot cuoi ok), khong tick.",
    )
    args = parser.parse_args(argv)

    if args.check:
        return run_check()
    return run_tick()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
