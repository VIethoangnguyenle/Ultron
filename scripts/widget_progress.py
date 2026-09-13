#!/usr/bin/env python3
"""Báo tiến độ công việc nền của widget Ultron vào DM Hoàng — mỗi 15 phút, chỉ khi có thay đổi.

Vì sao có: mấy việc widget chạy nền bằng `claude -p` mất 20-40 phút một lượt. Không có gì báo
thì Hoàng phải tự đi ngó `ps` với `git log`. Script này gom đúng 4 thứ đáng nhìn (việc đang
chạy, commit mới nhất, artifact mới nhất, tải máy) thành một tin ngắn.

Im lặng là mặc định: không đổi gì so với lần gửi trước thì không gửi. Ba lượt liên tiếp không
có việc nào chạy thì báo đúng một câu "xong rồi, chờ việc tiếp" rồi câm hẳn cho tới khi có việc
mới — để không biến thành cái máy spam mỗi 15 phút.

    widget_progress.py              # tick thật: gửi nếu có thay đổi
    widget_progress.py --dry-run    # chỉ in nội dung, không gửi, không ghi state
    widget_progress.py --force      # gửi bất kể chữ ký (bỏ qua cả đêm im lặng)

Nguồn dữ liệu — đọc thật, thiếu thì ghi "không rõ", không suy đoán:
  /proc/<pid>          tiến trình `claude -p` đang chạy + thời gian chạy
  /tmp/jarvis_*_spec.txt   spec của tiến trình đó -> tên việc
  git log              commit mới nhất của ultron-widget
  screenshots/, /tmp/jarvis_widget_*.log   artifact mới nhất
  /proc/loadavg, free -h   tải máy

State  ~/.hermes/state/widget_progress.json     Đích đến  DM Hoàng (cố định, xem SPACE)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HOME = Path.home()
SPACE = "spaces/0dniIqAAAAE"          # DM Hoàng — CỐ ĐỊNH, không nhận từ tham số (luật: không gửi nhầm group)
SENDER = HOME / ".hermes" / "scripts" / "gchat_send_text.py"
STATE = HOME / ".hermes" / "state" / "widget_progress.json"
WIDGET = HOME / "ultron-widget"
SHOTS = WIDGET / "screenshots"
LOG_GLOB = "jarvis_widget_*.log"

QUIET_FROM, QUIET_TO = 22, 6           # 22:00-06:00 im lặng, trừ khi có lỗi
IDLE_ROUNDS_BEFORE_QUIET = 3
ROUND_MINUTES = 5                      # phút chạy làm tròn 5' cho chữ ký
SEND_TIMEOUT_S = 25
CMD_TIMEOUT_S = 10

SPEC_RE = re.compile(r"/tmp/jarvis_[A-Za-z0-9_]+_spec\.txt")

# Dấu hiệu lỗi đủ mạnh để phá vỡ đêm im lặng. Cố ý hẹp: log tiếng Việt đầy chữ "lỗi" trong
# văn cảnh bình thường, bắt rộng là đêm nào cũng bị đánh thức.
ERROR_MARKERS = (
    "Traceback (most recent call last)",
    "PREFLIGHT FAIL",
)
EXIT_FAIL_RE = re.compile(r"EXIT=(?!0\b)\d+")

# Che secret trước khi bất cứ thứ gì từ log đi vào tin nhắn.
REDACT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"ghp_[A-Za-z0-9]{8,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{10,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)\b(token|secret|password|api[_-]?key)\b\s*[:=]\s*\S+"),
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),
]


def redact(text: str) -> str:
    for pat in REDACT_PATTERNS:
        text = pat.sub("[đã che]", text)
    return text


def run(cmd: list, timeout: int = CMD_TIMEOUT_S) -> str:
    """Chạy lệnh đọc dữ liệu. Lỗi gì cũng trả chuỗi rỗng — không có dữ liệu thì ghi "không rõ"."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return ""
    return (proc.stdout or "").strip() if proc.returncode == 0 else ""


# ---------------------------------------------------------------- tiến trình claude

def _cmdline(pid: int) -> list:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except Exception:
        return []
    return [p for p in raw.decode("utf-8", "replace").split("\0") if p]


def _ppid(pid: int) -> int:
    """PPID từ /proc/<pid>/stat. Lấy sau dấu ')' vì comm có thể chứa khoảng trắng."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
        return int(stat[stat.rindex(")") + 2:].split()[1])
    except Exception:
        return 0


def _elapsed_seconds(pid: int) -> int:
    """Giây kể từ lúc tiến trình khởi động (btime + starttime/HZ)."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
        starttime = int(stat[stat.rindex(")") + 2:].split()[19])
        hz = os.sysconf("SC_CLK_TCK")
        btime = 0
        for line in Path("/proc/stat").read_text(encoding="utf-8").splitlines():
            if line.startswith("btime "):
                btime = int(line.split()[1])
                break
        if not btime:
            return -1
        return max(0, int(time.time() - (btime + starttime / hz)))
    except Exception:
        return -1


def _spec_label(path: Path) -> str:
    """Tên việc suy từ 1-2 dòng đầu của spec."""
    try:
        lines = [l.strip() for l in path.read_text(encoding="utf-8", errors="replace").splitlines()[:4]]
    except Exception:
        return path.stem.replace("jarvis_", "").replace("_spec", "")
    for line in lines:
        if not line:
            continue
        line = re.sub(r"^Nhiệm vụ\s*:\s*", "", line).strip(" .")
        line = line.split(". ")[0]
        return (line[:70] + "…") if len(line) > 70 else line
    return path.stem.replace("jarvis_", "").replace("_spec", "")


def _find_spec(pid: int, argv: list) -> Path | None:
    """Tìm spec của một tiến trình claude, theo 3 nấc chắc chắn giảm dần.

    Launcher gọi `claude -p "$(cat /tmp/jarvis_X_spec.txt)"` nên argv của chính claude chứa
    NỘI DUNG spec chứ không phải đường dẫn — đường dẫn nằm ở cmdline của tiến trình bash cha.
    """
    joined = " ".join(argv)
    match = SPEC_RE.search(joined)                                  # 1. argv của chính nó
    if match and Path(match.group(0)).exists():
        return Path(match.group(0))

    cur, seen = pid, 0                                              # 2. cmdline tổ tiên
    while cur > 1 and seen < 6:
        match = SPEC_RE.search(" ".join(_cmdline(cur)))
        if match and Path(match.group(0)).exists():
            return Path(match.group(0))
        cur, seen = _ppid(cur), seen + 1

    prompt = ""                                                     # 3. khớp nội dung prompt
    if "-p" in argv:
        idx = argv.index("-p")
        if idx + 1 < len(argv):
            prompt = argv[idx + 1].strip()
    if len(prompt) < 40:
        return None
    head = " ".join(prompt.split())[:80]
    for spec in sorted(Path("/tmp").glob("jarvis_*_spec.txt")):
        try:
            body = " ".join(spec.read_text(encoding="utf-8", errors="replace").split())[:80]
        except Exception:
            continue
        if body and body == head:
            return spec
    return None


def running_jobs() -> list:
    """Các tiến trình `claude -p` đang chạy -> [{pid, minutes, label}].

    Chỉ lấy tiến trình mà argv[0] LÀ claude; bỏ lớp bọc `timeout 2400 claude -p ...` để một
    việc không bị đếm thành hai.
    """
    jobs = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        argv = _cmdline(pid)
        if len(argv) < 2 or os.path.basename(argv[0]) != "claude" or "-p" not in argv:
            continue
        secs = _elapsed_seconds(pid)
        spec = _find_spec(pid, argv)
        jobs.append({
            "pid": pid,
            "minutes": secs // 60 if secs >= 0 else -1,
            "label": _spec_label(spec) if spec else "không rõ",
        })
    return sorted(jobs, key=lambda j: j["pid"])


# ---------------------------------------------------------------- git / artifact / máy

def git_head() -> tuple:
    """-> (hash, tiêu đề) của commit mới nhất; ("không rõ", "") nếu không đọc được."""
    out = run(["git", "-C", str(WIDGET), "log", "--oneline", "-3"])
    if not out:
        return "không rõ", ""
    first = out.splitlines()[0].strip()
    parts = first.split(" ", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _newest(paths: list) -> tuple:
    best, best_mt = None, -1.0
    for p in paths:
        try:
            mt = p.stat().st_mtime
        except Exception:
            continue
        if mt > best_mt:
            best, best_mt = p, mt
    return best, best_mt


def newest_artifact() -> str:
    """Ảnh chụp mới nhất hoặc log jarvis mới nhất — cái nào mới hơn thì lấy."""
    shots = [p for p in SHOTS.glob("*") if p.is_file()] if SHOTS.is_dir() else []
    logs = [p for p in Path("/tmp").glob(LOG_GLOB) if p.is_file() and p.stat().st_size > 0]
    path, mt = _newest(shots + logs)
    if not path:
        return "không rõ"
    return f"{path.name} ({datetime.fromtimestamp(mt).strftime('%H:%M')})"


def log_tails() -> list:
    """6 dòng cuối của mỗi log jarvis widget còn nội dung — dùng để dò lỗi. Đã che secret."""
    tails = []
    for path in sorted(Path("/tmp").glob(LOG_GLOB)):
        try:
            if not path.is_file() or path.stat().st_size == 0:
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-6:]
        except Exception:
            continue
        tails.append((path.name, redact("\n".join(lines))))
    return tails


def has_error(tails: list) -> bool:
    for _name, body in tails:
        if EXIT_FAIL_RE.search(body) or any(m in body for m in ERROR_MARKERS):
            return True
    return False


def machine() -> str:
    try:
        load1 = Path("/proc/loadavg").read_text(encoding="utf-8").split()[0]
    except Exception:
        load1 = "không rõ"
    cores = os.cpu_count() or "?"

    free_txt, ram = run(["free", "-h"]), "không rõ"
    for line in free_txt.splitlines():
        if not line.startswith("Mem:"):
            continue
        cols = line.split()
        ram = cols[6] if len(cols) >= 7 else (cols[3] if len(cols) >= 4 else "không rõ")
        break
    return f"load {load1}/{cores} · RAM trống {ram}"


# ---------------------------------------------------------------- tin nhắn / chữ ký

def build(jobs: list, head: tuple, artifact: str) -> str:
    if jobs:
        shown = []
        for job in jobs[:2]:
            mins = f"{job['minutes']} phút" if job["minutes"] >= 0 else "không rõ bao lâu"
            shown.append(f"{job['label']} — {mins}")
        work = "; ".join(shown) + (f" (+{len(jobs) - 2} việc nữa)" if len(jobs) > 2 else "")
    else:
        work = "không có việc nào chạy"

    commit = f"{head[0]} {head[1]}".strip() or "không rõ"
    return (
        "⏱ Tiến độ widget (tự động 15'):\n"
        f"• Đang chạy: {work}\n"
        f"• Commit mới nhất: {commit}\n"
        f"• Mới nhất: {artifact}\n"
        f"• Máy: {machine()}"
    )


def signature(jobs: list, head: tuple, artifact: str) -> dict:
    """Chữ ký so sánh với LẦN GỬI TRƯỚC. Phút chạy làm tròn 5' để nhịp đập của đồng hồ
    không tự nó thành 'thay đổi', nhưng việc chạy lâu vẫn được báo tiến triển."""
    return {
        "git": head[0],
        "artifact": artifact.split(" (")[0],
        "pids": [j["pid"] for j in jobs],
        "mins": [(j["minutes"] // ROUND_MINUTES) * ROUND_MINUTES if j["minutes"] >= 0 else -1
                 for j in jobs],
    }


def load_state() -> dict:
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE)


def send(text: str) -> tuple:
    """Gọi gchat_send_text.py. -> (ok, chi tiết). Không bao giờ ném ra ngoài."""
    if not SENDER.exists():
        return False, f"thiếu {SENDER}"
    cmd = [sys.executable, str(SENDER), "--space", SPACE, "--text", text]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=SEND_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return False, f"gchat_send_text.py quá {SEND_TIMEOUT_S}s không xong"
    except Exception as exc:
        return False, f"không chạy được gchat_send_text.py: {exc}"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "(không có output)").strip()
        return False, f"exit {proc.returncode}: {redact(detail)[:300]}"
    return True, (proc.stdout or "").strip()


# ---------------------------------------------------------------- quyết định

def main() -> int:
    ap = argparse.ArgumentParser(description="Báo tiến độ widget vào DM Hoàng (chỉ khi có thay đổi).")
    ap.add_argument("--dry-run", action="store_true", help="chỉ in nội dung, không gửi, không ghi state")
    ap.add_argument("--force", action="store_true", help="gửi bất kể chữ ký và bất kể đêm im lặng")
    a = ap.parse_args()

    jobs = running_jobs()
    head = git_head()
    artifact = newest_artifact()
    tails = log_tails()
    sig = signature(jobs, head, artifact)

    state = load_state()
    changed = state.get("signature") != sig
    running = bool(jobs)
    quiet = bool(state.get("quiet"))
    idle_rounds = int(state.get("idle_rounds") or 0)

    if running or changed:          # có việc mới / có tiến triển -> cờ quiet tự bị xoá
        quiet, idle_rounds = False, 0
    else:
        idle_rounds += 1

    idle_notice = (not running) and (not changed) and idle_rounds >= IDLE_ROUNDS_BEFORE_QUIET
    text = ("Em xong phần này rồi, đang chờ việc tiếp ạ." if idle_notice
            else build(jobs, head, artifact))

    now = datetime.now()
    night = now.hour >= QUIET_FROM or now.hour < QUIET_TO
    errored = has_error(tails)

    if a.force:
        reason = "--force"
    elif quiet:
        reason = None
    elif idle_notice:
        reason = "3 lượt không có việc nào chạy"
    elif changed:
        reason = "có thay đổi"
    else:
        reason = None

    if reason and night and not (errored or a.force):
        print(f"[{now:%H:%M}] đêm im lặng ({QUIET_FROM:02d}:00-{QUIET_TO:02d}:00), không gửi "
              f"(lẽ ra gửi: {reason}). Không có dấu hiệu lỗi.")
        reason = None

    if a.dry_run:
        print(f"[dry-run] -> {SPACE} | {'SẼ GỬI: ' + reason if reason else 'IM LẶNG (không đổi)'}")
        print("-" * 60)
        print(text)
        return 0

    if not reason:
        state.update({"idle_rounds": idle_rounds, "quiet": quiet})
        save_state(state)
        return 0

    ok, detail = send(text)
    if not ok:
        print(f"LỖI gửi tin tiến độ: {detail}")
        state.update({"idle_rounds": idle_rounds, "quiet": quiet,
                      "last_error": detail[:300], "last_error_at": now.isoformat(timespec="seconds")})
        save_state(state)
        return 1

    if idle_notice:
        quiet = True                # đã báo xong việc -> câm cho tới khi có việc mới
    state.update({
        "signature": sig,
        "sent_at": now.isoformat(timespec="seconds"),
        "idle_rounds": idle_rounds,
        "quiet": quiet,
        "last_error": None,
    })
    save_state(state)
    print(f"[{now:%H:%M}] đã gửi ({reason}) -> {SPACE} {detail}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:        # không bao giờ chết im lặng
        print(f"LỖI widget_progress.py: {exc}")
        raise SystemExit(2)
