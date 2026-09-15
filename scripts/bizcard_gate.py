#!/usr/bin/env python3
"""Cổng thẻ nghiệp vụ chạy định kỳ — CHỈ nhắn DM Hoàng khi có việc.

Chạy `bizcard.py check --fetch --quiet` trên repo vietbank-sme rồi quyết định:

  - bizcard im lặng (stdout rỗng, mã thoát 0)  -> KHÔNG in gì, KHÔNG gửi gì, thoát 0.
  - bizcard có in ra (lệch cứng / commit nghi ngờ / cảnh báo fetch) -> DM Hoàng,
    nội dung là output nguyên văn của bizcard, không diễn giải lại, không cắt bớt.
  - bizcard hỏng (mã 2, quá hạn, mã lạ) -> DM một tin cảnh báo NGẮN, tối đa 1 tin
    mỗi ngày cho mỗi loại lỗi, để dispatcher tick 2 phút/lần không biến thành spam.

Chống lặp tin: dispatcher chạy 2 phút/lần, mà thẻ lệch thì lệch cho tới khi Hoàng
`bizcard.py stamp` lại — gửi mỗi tick là 700 tin/ngày cùng một nội dung. Nên tin báo
thẻ cũng chỉ gửi 1 lần/ngày cho mỗi NỘI DUNG khác nhau (so bằng sha256 của output):
nội dung đổi (thẻ khác lệch, thêm commit nghi ngờ) thì gửi lại ngay trong ngày, còn
y hệt thì im. Muốn gửi bằng được thì thêm `--force`.

Dùng:
    bizcard_gate.py                 # chạy thật (dispatcher gọi kiểu này)
    bizcard_gate.py --dry-run       # in ra sẽ gửi gì, không gửi, không ghi state
    bizcard_gate.py --force         # bỏ qua chống lặp trong ngày
    bizcard_gate.py --space spaces/XXX   # gửi sang space khác (dùng khi test)

Chỉ dùng thư viện chuẩn Python 3. Không sửa bizcard.py, không sửa file thẻ.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

HOME = Path.home()
BIZCARD = HOME / ".hermes" / "scripts" / "bizcard.py"
GCHAT_SEND = HOME / ".hermes" / "scripts" / "gchat_send_text.py"
STATE_PATH = HOME / ".hermes" / "state" / "bizcard_gate.json"

REPO_CWD = "/home/zane/Desktop/work/vietbank/vietbank-sme"
HOANG_DM = "spaces/0dniIqAAAAE"

CHECK_TIMEOUT = 180

# Google Chat cắt tin ở 4000 ký tự. Yêu cầu là KHÔNG cắt bớt số liệu, nên tin dài
# được chia thành nhiều tin thay vì bị xén.
CHUNK_LIMIT = 3800

EXIT_OK = 0
EXIT_FAIL = 1


# --------------------------------------------------------------------------- #
# Chạy bizcard
# --------------------------------------------------------------------------- #

def run_bizcard():
    """Trả về (kind, rc, stdout, stderr).

    kind: "ok" nếu bizcard chạy xong (dù mã 0 hay 1); "timeout" / "loi-cau-hinh" /
    "loi-chay" / "thieu-file" nếu là sự cố hệ thống.
    """
    if not BIZCARD.is_file():
        return "thieu-file", None, "", "Không thấy %s" % BIZCARD

    cmd = [sys.executable, str(BIZCARD), "check", "--fetch", "--quiet"]
    try:
        proc = subprocess.run(cmd, cwd=REPO_CWD, capture_output=True, text=True,
                              timeout=CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return "timeout", None, "", "bizcard.py check quá hạn %ds" % CHECK_TIMEOUT
    except OSError as exc:
        return "loi-chay", None, "", "Không chạy được bizcard.py: %s" % exc

    if proc.returncode == 2:
        return "loi-cau-hinh", 2, proc.stdout, proc.stderr
    if proc.returncode not in (0, 1):
        return "loi-chay", proc.returncode, proc.stdout, proc.stderr
    return "ok", proc.returncode, proc.stdout, proc.stderr


# --------------------------------------------------------------------------- #
# Dựng nội dung tin
# --------------------------------------------------------------------------- #

def today_str():
    return date.today().strftime("%d/%m/%Y")


def build_report(rc, stdout, stderr):
    """Tin báo thẻ — giữ nguyên văn output của bizcard."""
    lines = ["Thẻ nghiệp vụ cần rà — %s" % today_str()]
    if rc == 1:
        lines.append("CÓ THẺ LỆCH CỨNG: không dùng thẻ làm kết luận, phải verify lại.")
    lines.append("")
    lines.append(stdout.rstrip("\n"))
    if stderr.strip():
        lines.append("")
        lines.append("[stderr của bizcard.py]")
        lines.append(stderr.rstrip("\n"))
    return "\n".join(lines)


def build_alert(kind, rc, stderr):
    """Tin cảnh báo sự cố — ngắn, không dán cả trang log."""
    tail = stderr.strip().splitlines()[-5:]
    lines = [
        "Cổng thẻ nghiệp vụ lỗi — %s" % today_str(),
        "bizcard.py check không chạy được (%s%s). Cổng đang KHÔNG bảo vệ: coi như mọi thẻ chưa kiểm."
        % (kind, "" if rc is None else ", mã thoát %s" % rc),
    ]
    if tail:
        lines.append("")
        lines.extend(tail)
    lines.append("")
    lines.append("Kiểm tay: cd %s && python3 ~/.hermes/scripts/bizcard.py check --fetch" % REPO_CWD)
    return "\n".join(lines)


def split_message(text, limit=CHUNK_LIMIT):
    """Chia tin dài theo ranh giới dòng. Dòng đơn lẻ quá dài thì cắt cứng dòng đó."""
    chunks, current = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = line if not current else current + "\n" + line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
            continue
        current = candidate
    if current.strip():
        chunks.append(current)
    if not chunks:
        return [text]
    if len(chunks) == 1:
        return chunks
    total = len(chunks)
    return ["%s\n\n(phần %d/%d)" % (c, i, total) for i, c in enumerate(chunks, 1)]


# --------------------------------------------------------------------------- #
# State chống lặp
# --------------------------------------------------------------------------- #

def read_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, STATE_PATH)


def alert_already_sent(state, kind):
    return (state.get("last_alert_date") == date.today().isoformat()
            and state.get("last_alert_kind") == kind)


def report_already_sent(state, digest):
    return (state.get("last_report_date") == date.today().isoformat()
            and state.get("last_report_hash") == digest)


# --------------------------------------------------------------------------- #
# Gửi
# --------------------------------------------------------------------------- #

def send_chunks(space, chunks):
    """Gửi từng phần qua gchat_send_text.py. Trả về None nếu OK, hoặc chuỗi lỗi."""
    if not GCHAT_SEND.is_file():
        return "Không thấy %s" % GCHAT_SEND
    for i, chunk in enumerate(chunks, 1):
        fd, path = tempfile.mkstemp(prefix="bizcard_gate_", suffix=".txt", text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(chunk)
            proc = subprocess.run(
                [sys.executable, str(GCHAT_SEND), "--space", space, "--text-file", path],
                capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return "gửi phần %d lỗi: %s" % (i, exc)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if proc.returncode != 0:
            return "gửi phần %d lỗi (mã %d): %s" % (i, proc.returncode,
                                                    proc.stderr.strip() or proc.stdout.strip())
    return None


def deliver(args, space, message, state_update):
    chunks = split_message(message)
    if args.dry_run:
        print("[dry-run] sẽ gửi tới %s — %d tin" % (space, len(chunks)))
        for i, chunk in enumerate(chunks, 1):
            print("-" * 60 + (" tin %d/%d" % (i, len(chunks))))
            print(chunk)
        print("-" * 60)
        print("[dry-run] không gửi thật, không ghi state.")
        return EXIT_OK

    err = send_chunks(space, chunks)
    if err:
        print("LỖI: không gửi được tin cổng thẻ — %s" % err, file=sys.stderr)
        return EXIT_FAIL

    state = read_state()
    state.update(state_update)
    try:
        write_state(state)
    except OSError as exc:
        print("LỖI: gửi xong nhưng không ghi được state %s: %s" % (STATE_PATH, exc),
              file=sys.stderr)
        return EXIT_FAIL
    print("Đã gửi DM cổng thẻ tới %s (%d tin)." % (space, len(chunks)))
    return EXIT_OK


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser():
    parser = argparse.ArgumentParser(
        prog="bizcard_gate.py",
        description=("Chạy cổng kiểm hạn thẻ nghiệp vụ và CHỈ nhắn DM Hoàng khi có việc. "
                     "Thẻ sạch thì im lặng tuyệt đối (hợp với dispatcher tick 2 phút/lần)."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Hành vi:
  thẻ sạch                -> không in gì, không gửi gì, mã thoát 0
  có lệch / nghi ngờ      -> DM nguyên văn output của bizcard.py check
  bizcard lỗi (mã 2, quá hạn) -> DM cảnh báo ngắn, tối đa 1 tin/ngày mỗi loại lỗi

Chống lặp: state ~/.hermes/state/bizcard_gate.json giữ
  last_alert_date / last_alert_kind    (tin cảnh báo sự cố)
  last_report_date / last_report_hash  (tin báo thẻ — cùng nội dung thì chỉ gửi 1 lần/ngày)

Mã thoát:
  0  bình thường (im lặng, đã gửi, hoặc bị chặn vì đã gửi trong ngày)
  1  không gửi được tin / không ghi được state
""")
    parser.add_argument("--dry-run", action="store_true",
                        help="In ra sẽ gửi gì rồi dừng. Không gửi, không ghi state.")
    parser.add_argument("--force", action="store_true",
                        help="Bỏ qua chống lặp trong ngày, gửi lại dù nội dung y hệt.")
    parser.add_argument("--space", default=HOANG_DM,
                        help="Space nhận tin (mặc định DM Hoàng: %s)." % HOANG_DM)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    kind, rc, stdout, stderr = run_bizcard()
    today = date.today().isoformat()

    if kind != "ok":
        if not args.force and alert_already_sent(read_state(), kind):
            return EXIT_OK
        return deliver(args, args.space, build_alert(kind, rc, stderr),
                       {"last_alert_date": today, "last_alert_kind": kind})

    # bizcard chạy xong. Sạch = stdout rỗng và mã 0 -> im lặng tuyệt đối.
    if rc == 0 and not stdout.strip():
        if not stderr.strip():
            if args.dry_run:
                print("im lặng — mọi thẻ sạch, không gửi gì.")
            return EXIT_OK
        # Mã 0, không in gì, nhưng có stderr: bizcard vẫn chạy nhưng có gì đó không ổn.
        # Coi là sự cố hệ thống, chặn 1 tin/ngày như các loại lỗi khác.
        if not args.force and alert_already_sent(read_state(), "stderr-la"):
            return EXIT_OK
        return deliver(args, args.space, build_alert("stderr lạ khi thẻ sạch", rc, stderr),
                       {"last_alert_date": today, "last_alert_kind": "stderr-la"})

    message = build_report(rc, stdout, stderr)
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]
    if not args.force and report_already_sent(read_state(), digest):
        return EXIT_OK
    return deliver(args, args.space, message,
                   {"last_report_date": today, "last_report_hash": digest})


if __name__ == "__main__":
    sys.exit(main())
