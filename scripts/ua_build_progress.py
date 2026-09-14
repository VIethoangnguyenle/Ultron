#!/usr/bin/env python3
"""Bao cao tien do build knowledge graph UA cho vietbank-sme.

CHI DOC: khong sua config, khong dung vao process agy, khong ghi file nao
ngoai mot file tam khi gui Google Chat.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime

WATCH_LOG = "/home/zane/.hermes/logs/ua_build_watch.log"
BUILD_LOG = "/tmp/ua_vbsme_build.log"
UA_DIR = "/home/zane/Desktop/work/vietbank/vietbank-sme/.ua"
STATUS_FILE = "/home/zane/.hermes/state/ua_build_status.txt"
GCHAT_SEND = "/home/zane/.hermes/scripts/gchat_send_text.py"

PROC_NAME = "agy.real"
BUILD_START_MARK = "Bat dau build UA"


def human_size(num_bytes):
    if num_bytes is None:
        return "?"
    unit = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for name in unit:
        if size < 1024 or name == unit[-1]:
            return "%.0f %s" % (size, name) if name == "B" else "%.1f %s" % (size, name)
        size /= 1024
    return "%.1f TB" % size


def human_duration(seconds):
    if seconds is None or seconds < 0:
        return "?"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return "%dh%02dm" % (hours, minutes)
    if minutes:
        return "%dm%02ds" % (minutes, secs)
    return "%ds" % secs


def file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def file_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def age_text(mtime):
    if mtime is None:
        return "không có"
    return "sửa %s trước" % human_duration(time.time() - mtime)


def dir_size(path):
    total = 0
    count = 0
    newest = None
    for root, _dirs, files in os.walk(path):
        for name in files:
            full = os.path.join(root, name)
            size = file_size(full)
            if size is None:
                continue
            total += size
            count += 1
            mtime = file_mtime(full)
            if mtime is not None and (newest is None or mtime > newest[1]):
                newest = (full, mtime, size)
    return total, count, newest


def read_tail_lines(path, limit=200):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read().splitlines()[-limit:]
    except OSError:
        return []


def last_stamped_line(lines):
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            return stripped
    for line in reversed(lines):
        if line.strip():
            return line.strip()
    return ""


def clock_ticks():
    try:
        return os.sysconf("SC_CLK_TCK")
    except (ValueError, OSError):
        return 100


def uptime_seconds():
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as handle:
            return float(handle.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def proc_elapsed(pid):
    """Thoi gian pid da chay, tinh tu /proc/<pid>/stat (chi doc)."""
    try:
        with open("/proc/%d/stat" % pid, "r", encoding="utf-8") as handle:
            raw = handle.read()
    except OSError:
        return None
    tail = raw.rsplit(")", 1)
    if len(tail) != 2:
        return None
    fields = tail[1].split()
    # sau ')' truong dau tien la state -> starttime la phan tu index 19
    if len(fields) < 20:
        return None
    try:
        start_ticks = float(fields[19])
    except ValueError:
        return None
    up = uptime_seconds()
    if up is None:
        return None
    return up - start_ticks / float(clock_ticks())


def find_agy_pids():
    try:
        done = subprocess.run(
            ["pgrep", "-x", PROC_NAME],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    pids = []
    for token in done.stdout.split():
        if token.isdigit():
            pids.append(int(token))
    return sorted(pids)


def read_status_file():
    if not os.path.isfile(STATUS_FILE):
        return None
    lines = read_tail_lines(STATUS_FILE, limit=20)
    return last_stamped_line(lines) or None


def describe_artifacts():
    """Tra ve (danh sach mo ta, co knowledge-graph.json chua)."""
    if not os.path.isdir(UA_DIR):
        return ["Thư mục .ua/: chưa tồn tại"], False
    parts = []
    kg_path = os.path.join(UA_DIR, "knowledge-graph.json")
    meta_path = os.path.join(UA_DIR, "meta.json")
    kg_size = file_size(kg_path)
    meta_size = file_size(meta_path)
    parts.append(
        "knowledge-graph.json: %s | meta.json: %s"
        % (
            human_size(kg_size) if kg_size is not None else "chưa có",
            human_size(meta_size) if meta_size is not None else "chưa có",
        )
    )
    inter = os.path.join(UA_DIR, "intermediate")
    if os.path.isdir(inter):
        total, count, newest = dir_size(inter)
        newest_txt = "chưa có file"
        if newest is not None:
            newest_txt = "mới nhất %s %s, %s" % (
                os.path.basename(newest[0]),
                human_size(newest[2]),
                age_text(newest[1]),
            )
        parts.append(
            "intermediate/: %s, %d file (%s)" % (human_size(total), count, newest_txt)
        )
    else:
        parts.append("intermediate/: chưa có")
    return parts, kg_size is not None


def build_report():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pids = find_agy_pids()
    watch_lines = read_tail_lines(WATCH_LOG)
    watch_last = last_stamped_line(watch_lines)
    build_lines = read_tail_lines(BUILD_LOG)
    build_last = last_stamped_line(build_lines)
    artifacts, has_graph = describe_artifacts()
    status_note = read_status_file()
    build_started = any(BUILD_START_MARK in line for line in watch_lines)

    running = bool(pids)
    if running:
        verdict = "ĐANG CHẠY"
        detail = "build còn tiến trình %s, chờ tiếp." % PROC_NAME
    elif has_graph:
        verdict = "XONG"
        detail = "đã có knowledge-graph.json, không còn tiến trình build."
    elif build_started:
        verdict = "LỖI-DỪNG"
        detail = "watcher đã khởi động build nhưng không còn tiến trình và chưa có graph."
    else:
        verdict = "LỖI-DỪNG"
        detail = "chưa thấy dấu hiệu build khởi động trong log watcher."

    lines = ["UA build vietbank-sme - %s" % now]

    if running:
        pid_desc = []
        for pid in pids:
            pid_desc.append("%d (%s)" % (pid, human_duration(proc_elapsed(pid))))
        lines.append("Tiến trình: %s đang chạy - pid %s" % (PROC_NAME, ", ".join(pid_desc)))
    else:
        lines.append("Tiến trình: không có %s nào đang chạy" % PROC_NAME)

    lines.append("Mốc cuối watcher: %s" % (watch_last or "(log trống)"))
    lines.append(
        "Log watcher: %s (%s) | Log build: %s (%s)"
        % (
            human_size(file_size(WATCH_LOG)),
            age_text(file_mtime(WATCH_LOG)),
            human_size(file_size(BUILD_LOG)),
            age_text(file_mtime(BUILD_LOG)),
        )
    )
    if build_last:
        lines.append("Mốc cuối log build: %s" % build_last[:180])
    lines.extend(artifacts)
    if status_note:
        lines.append("Status file: %s" % status_note[:180])
    lines.append("Kết luận: %s - %s" % (verdict, detail))
    return verdict, "\n".join(lines)


def send_to_chat(space, text):
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix="ua_build_progress_", delete=False, encoding="utf-8"
    )
    try:
        handle.write(text)
        handle.close()
        subprocess.run(
            [sys.executable, GCHAT_SEND, "--space", space, "--text-file", handle.name],
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print("Không gửi được Google Chat: %s" % exc, file=sys.stderr)
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Báo cáo tiến độ build graph UA (chỉ đọc, 0 token LLM)."
    )
    parser.add_argument("--send", action="store_true", help="gửi báo cáo qua Google Chat")
    parser.add_argument("--space", help="space id, vd spaces/AAAADv4ib6s (đi kèm --send)")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="không in/gửi gì khi build đã xong (dùng cho cron)",
    )
    args = parser.parse_args()

    if args.send and not args.space:
        parser.error("--send cần đi kèm --space <id>")

    verdict, report = build_report()

    if args.quiet and verdict == "XONG":
        return 0

    print(report)
    if args.send:
        send_to_chat(args.space, report)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # chi doc, khong bao gio de loi lam vo cron
        print("ua_build_progress lỗi: %s" % exc, file=sys.stderr)
        sys.exit(0)
