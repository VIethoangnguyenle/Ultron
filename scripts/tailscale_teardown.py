#!/usr/bin/env python3
"""Tắt & dọn Tailscale gateway (node log UAT/LIVE) — chạy theo lịch trong schedules.yaml.

Vì sao: node `ultron` (tên cũ `vbsme-log-gw`) mở đường riêng cho tester ở nhà đọc log + cổng Siri bridge.
Hoàng chốt 2026-09-12: **mọi kết nối Tailscale phải tắt sau 17h30** và **phải xoá log
Tailscale trên hệ thống** — không để lại dấu vết đường vào nào qua đêm.

    tailscale_teardown.py [--dry-run] [--no-notify]

THỨ TỰ (quan trọng — sai thứ tự là scrub xong log lại có dòng mới):
  1. TẮT NODE trước: `tailscale down` (GIỮ danh tính: state volume để lại ⇒ mở lại đúng node,
     đúng IP — bài học 2026-09-12: logout + xoá state ⇒ mất node, IP đổi, phải sửa
     config/cổng Siri/Shortcut mỗi lần), rồi stop + rm container (xoá luôn log json container).
     GIỮ volume `tailscale-state` (đó là danh tính node, không phải log).
  2. Dọn nội dung chat tạm của kênh Siri: `state/siri_chat_outbox*`, `state/siri_chat_files/*`.
     GIỮ `state/siri_chat/*.jsonl` — đó là ngữ cảnh hội thoại, không phải dấu vết đường vào.
  3. SCRUB log SAU CÙNG: quét ĐỆ QUY, xoá dòng chứa dấu vết THẬT (IP tailnet / IP dải CGNAT
     100.64.0.0/10, tên node, `tskey-`). Scrub tại chỗ (giữ inode) để không mất dòng của tiến
     trình đang mở file, rồi đọc lại KIỂM CHỨNG là đã sạch.
  4. Kiểm 2 cổng Siri còn sống ở local rồi mới báo — không khẳng định suông.

KHÔNG đụng 2 cổng Siri (siri-speak :9444, siri-chat :9445): từ 2026-09-13 chúng nghe ở
127.0.0.1 nên là dịch vụ LOCAL, chạy 24/7. Socket phụ trên IP tailnet chết theo node là vô hại
và watchdog của chính cổng mở lại khi node lên — stop chúng chỉ làm mất kênh local.

An toàn: không đụng container/service nào khác (vd `omni-sme-proxy`). Chạy lại nhiều lần vô hại.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

CONTAINER = "tailscale"
VOLUME = "tailscale-state"
DM_SPACE = "spaces/AAQAZxc2km8"  # DM riêng của Hoàng
HERMES = Path.home() / ".hermes"
NOTIFY_SCRIPT = HERMES / "scripts" / "gchat_send_text.py"
VENV_PY = HERMES / "hermes-agent" / "venv" / "bin" / "python"

GATES = (("cổng nói", 9444), ("cổng chat", 9445))

# Nội dung chat TẠM của kênh Siri — xoá được, tạo lại mỗi lượt.
# CỐ Ý KHÔNG có state/siri_chat/*.jsonl: đó là ngữ cảnh hội thoại, xoá là Ultron mất trí nhớ.
SIRI_TEMP_GLOBS = [
    "state/siri_chat_outbox",          # thư mục outbox tách theo hội thoại → xoá nội dung
    "state/siri_chat_outbox*.json",    # file outbox 1-slot kiểu cũ + file .claim-* còn sót
    "state/siri_chat_files",           # file trả cho client → xoá nội dung
    "state/siri_outbox.claim-*.json",  # claim còn sót của kênh nói
]

# Nơi có thể còn log/dấu vết. KHÔNG quét ~/.hermes/scripts và ~/.hermes/skills
# (script/skill là công cụ để bật lại — xoá là tự bắn vào chân).
SCAN_ROOTS = [Path("/tmp"), HERMES]
SKIP_PREFIXES = [str(HERMES / "scripts"), str(HERMES / "skills")]
# Thư mục nặng & không phải log — không lội vào (quét đệ quy nên phải chặn từ gốc).
PRUNE_DIRS = {".git", "node_modules", "venv", "venvs", "node", "__pycache__",
              "sandboxes", "terminal-sessions", "models_dev_cache", "audio_cache",
              "image_cache", "attachments"}

# Dấu vết THẬT cần xoá. Cố ý KHÔNG có chuỗi chung "tailscale"/"Tailscale"/"tailscaled":
# chúng khớp cả dòng nói về công cụ, xoá là mất log không liên quan (bài học review 2026-09-13).
CGNAT_RE = re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b")
LITERAL_MARKERS = ["100.120.110.26", "vbsme-log-gw", "tskey-"]


def tailnet_ip_marker() -> list[str]:
    """IP node hiện tại — node tạo lại là IP đổi, nên đọc từ state thay vì chỉ gắn cứng."""
    try:
        ip = (HERMES / "state" / "tailnet_ip.txt").read_text().strip()
    except Exception:  # noqa: BLE001
        return []
    return [ip] if ip else []


def markers() -> list[str]:
    return tailnet_ip_marker() + LITERAL_MARKERS


def has_trace(line: str, literals: list[str]) -> bool:
    return any(m in line for m in literals) or bool(CGNAT_RE.search(line))


# CHỈ scrub file log. KHÔNG đụng .json/.yaml: `webhook_subscriptions.json` là định nghĩa route
# Siri, scrub vào là hỏng cổng (đã bắt được ở dry-run 2026-09-12) — config không phải log.
SCAN_SUFFIXES = {".log", ".txt", ".out", ".err"}
# Chốt an toàn cuối: dù có bị thêm vào danh sách quét cũng không bao giờ được đụng.
PROTECTED_NAMES = {"webhook_subscriptions.json", "config.yaml", "state.db", "siri_token.txt"}
SCAN_MAX_BYTES = 3_000_000


def sh(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    """Chạy lệnh, trả (exit_code, output gộp). Không bao giờ raise."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return 124, f"quá {timeout}s: {' '.join(cmd)}"
    except Exception as exc:  # noqa: BLE001
        return 1, f"lỗi chạy {' '.join(cmd)}: {exc}"


def container_exists() -> bool:
    code, out = sh(["docker", "ps", "-a", "--format", "{{.Names}}"])
    return code == 0 and CONTAINER in out.split()


# --- bước 1: tắt node ----------------------------------------------------------------------

def teardown_node() -> dict:
    """Down node (giữ danh tính) + stop + rm container. Trả kết quả THẬT của từng bước."""
    result = {"down": "", "stopped": False, "removed": False, "error": ""}
    code, out = sh(["docker", "exec", CONTAINER, "tailscale", "down"], timeout=45)
    result["down"] = "OK" if code == 0 else f"bỏ qua (exit {code}: {out[:120]})"
    print(f"→ down node (giữ danh tính/IP): {result['down']}")

    code, out = sh(["docker", "stop", CONTAINER], timeout=90)
    result["stopped"] = code == 0
    if code != 0:
        result["error"] = f"không stop được container: {out[:200]}"
        print(f"LỖI: {result['error']}")
        return result
    print("→ đã stop container")

    code, out = sh(["docker", "rm", CONTAINER], timeout=60)
    result["removed"] = code == 0
    print("→ đã xoá container (kèm log)" if code == 0
          else f"cảnh báo: xoá container lỗi ({out[:120]})")

    # Cầu nối ra tailnet (git.vnpay.vn :9445 / console :9446) KHÔNG cần tắt riêng:
    # nó nằm ngay trong nginx của Hoàng (omni-sme-proxy) và chỉ allow dải CGNAT
    # 100.64.0.0/10 ⇒ Tailscale down là tự nhiên không ai vào được nữa.

    # GIỮ volume state: đó là danh tính node (machine key + IP), không phải log.
    # Xoá nó ⇒ lần mở sau phải tạo node mới ⇒ IP mới ⇒ sửa config + cổng Siri + Shortcut.
    code_v, out_v = sh(["docker", "volume", "ls", "--filter", f"name={VOLUME}",
                        "--format", "{{.Name}}"], timeout=30)
    if code_v == 0 and VOLUME in out_v.split():
        print(f"→ giữ volume {VOLUME} (danh tính node — cố ý KHÔNG xoá)")
    return result


# --- bước 2: dọn chat tạm ------------------------------------------------------------------

def clean_siri_temp(dry_run: bool) -> list[str]:
    """Xoá nội dung chat tạm của kênh Siri (outbox + file trả client). Giữ ngữ cảnh hội thoại."""
    done: list[str] = []
    for pattern in SIRI_TEMP_GLOBS:
        for path in sorted(HERMES.glob(pattern)):
            if path.name in PROTECTED_NAMES:
                continue
            if path.is_dir():
                children = [c for c in sorted(path.iterdir())]
                if not children:
                    continue
                done.append(f"{path.relative_to(HERMES)}/ ({len(children)} mục)")
                if dry_run:
                    continue
                for child in children:
                    try:
                        shutil.rmtree(child) if child.is_dir() and not child.is_symlink() \
                            else child.unlink()
                    except Exception as exc:  # noqa: BLE001
                        done[-1] += f" LỖI {child.name}: {exc}"
                continue
            done.append(str(path.relative_to(HERMES)))
            if dry_run:
                continue
            try:
                path.unlink()
            except Exception as exc:  # noqa: BLE001
                done[-1] += f" LỖI: {exc}"
    return done


# --- bước 3: scrub log ---------------------------------------------------------------------

def candidates() -> list[Path]:
    """File log/dấu vết đáng soi — quét ĐỆ QUY (log nằm trong thư mục con vẫn phải xoá được)."""
    out: list[Path] = []
    seen: set[str] = set()
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames
                           if d not in PRUNE_DIRS
                           and not any(os.path.join(dirpath, d).startswith(p) for p in SKIP_PREFIXES)]
            if any(dirpath.startswith(p) for p in SKIP_PREFIXES):
                continue
            for name in sorted(filenames):
                path = Path(dirpath) / name
                real = str(path)
                if real in seen:
                    continue
                if path.suffix.lower() not in SCAN_SUFFIXES and ".log." not in name:
                    continue  # log xoay vòng tên `agent.log.1` — suffix là ".1"
                if name in PROTECTED_NAMES or path.is_symlink() or not path.is_file():
                    continue
                try:
                    if path.stat().st_size > SCAN_MAX_BYTES:
                        continue
                except OSError:
                    continue
                seen.add(real)
                out.append(path)
    return out


def open_by_other_process(path: Path) -> bool:
    """File đang được tiến trình khác mở? (quét /proc/*/fd của chính user — không cần sudo)

    Quan trọng vì log của 2 cổng Siri được systemd ghi liên tục: unlink/replace là mất dòng,
    nên file đang mở thì phải scrub TẠI CHỖ (giữ inode).
    """
    try:
        target = os.path.realpath(path)
    except OSError:
        return True
    me = str(os.getpid())
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit() and p != me]
    except OSError:
        return True                     # không kiểm được thì coi như đang mở (an toàn hơn)
    for pid in pids:
        fd_dir = f"/proc/{pid}/fd"
        try:
            for fd in os.listdir(fd_dir):
                try:
                    if os.readlink(f"{fd_dir}/{fd}") == target:
                        return True
                except OSError:
                    continue
        except OSError:
            continue
    return False


def scrub_in_place(path: Path, keep: list[str], trailing_nl: bool, literals: list[str]) -> str:
    """Ghi lại nội dung đã lọc mà GIỮ INODE (mở r+, truncate) rồi ĐỌC LẠI kiểm chứng.

    Giữ inode vì tiến trình đang ghi (systemd `append:`, python `open(...,"a")` — đều O_APPEND)
    vẫn nối vào đúng file, và O_APPEND luôn ghi ở cuối file thật nên không để lại lỗ NUL.
    Dùng os.replace/unlink ở đây thì tiến trình kia ghi tiếp vào inode đã mất → mất dòng.
    """
    body = ("\n".join(keep) + ("\n" if trailing_nl else "")) if keep else ""
    try:
        with open(path, "r+", encoding="utf-8", errors="replace", newline="") as fh:
            fh.seek(0)
            fh.write(body)
            fh.truncate()
            fh.flush()
            os.fsync(fh.fileno())
    except Exception as exc:  # noqa: BLE001
        return f"LỖI ghi: {exc}"
    try:
        left = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
                if has_trace(ln, literals)]
    except Exception as exc:  # noqa: BLE001
        return f"LỖI đọc lại: {exc}"
    return "đã kiểm chứng sạch" if not left else f"CÒN {len(left)} dòng dấu vết"


def scrub_log_traces(dry_run: bool) -> dict[str, list[str]]:
    """Xoá dòng có dấu vết tailnet trong log. Trả {'emptied': [...], 'scrubbed': [...]}."""
    emptied: list[str] = []
    scrubbed: list[str] = []
    literals = markers()

    for path in candidates():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        lines = text.splitlines()
        hits = [ln for ln in lines if has_trace(ln, literals)]
        if not hits:
            continue
        keep = [ln for ln in lines if not has_trace(ln, literals)]
        if not [ln for ln in keep if ln.strip()]:
            live = open_by_other_process(path)
            how = "làm rỗng (đang được tiến trình khác ghi — giữ inode)" if live else "xoá hẳn"
            emptied.append(f"{path} ({len(hits)} dòng, toàn bộ là dấu vết) → {how}")
            if dry_run:
                continue
            if live:
                emptied[-1] += f" — {scrub_in_place(path, [], text.endswith(chr(10)), literals)}"
                continue
            try:
                path.unlink()
            except Exception as exc:  # noqa: BLE001
                emptied[-1] += f" LỖI: {exc}"
            continue
        scrubbed.append(f"{path} ({len(hits)}/{len(lines)} dòng)")
        if dry_run:
            continue
        scrubbed[-1] += f" — {scrub_in_place(path, keep, text.endswith(chr(10)), literals)}"
    return {"emptied": emptied, "scrubbed": scrubbed}


# --- bước 4: kiểm 2 cổng còn sống ----------------------------------------------------------

def gate_health() -> list[str]:
    """Gọi /health của 2 cổng ở 127.0.0.1 — báo trạng thái THẬT, không khẳng định suông."""
    out = []
    for label, port in GATES:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
                body = resp.read(16).decode("utf-8", "replace").strip()
            out.append(f"{label} (:{port}) còn sống ở local" if resp.status == 200 and body == "ok"
                       else f"{label} (:{port}) trả lạ: {resp.status} {body!r}")
        except Exception as exc:  # noqa: BLE001
            out.append(f"{label} (:{port}) KHÔNG trả lời ({type(exc).__name__}) — cần nạp lại")
    return out


def notify(text: str) -> None:
    if not NOTIFY_SCRIPT.exists():
        return
    py = str(VENV_PY) if VENV_PY.exists() else sys.executable
    code, out = sh([py, str(NOTIFY_SCRIPT), "--space", DM_SPACE, "--text", text], timeout=60)
    log = "đã gửi DM" if code == 0 else f"gửi DM lỗi (exit {code}: {out[:120]})"
    print(f"[notify] {log}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] Tailscale teardown — container={CONTAINER} volume={VOLUME}")
    print("thứ tự: 1) tắt node  2) dọn chat tạm  3) scrub log  4) kiểm 2 cổng")

    had_container = container_exists()
    if not had_container:
        print("→ container không tồn tại (đã tắt trước đó)")

    log_lines = 0
    if had_container:
        code, out = sh(["docker", "logs", CONTAINER])
        log_lines = len(out.splitlines()) if code == 0 else 0

    if args.dry_run:
        code, out = sh(["docker", "ps", "-a", "--filter", f"name={CONTAINER}",
                        "--format", "{{.Names}} | {{.Status}}"])
        print("\n[1] NODE — sẽ down (giữ state) + stop/rm container "
              f"{CONTAINER}; volume {VOLUME} GIỮ LẠI")
        print(f"    hiện trạng: {out or '(không đọc được)'}")
        print(f"    log container sẽ mất cùng container: {log_lines} dòng")
        temp = clean_siri_temp(True)
        print(f"\n[2] CHAT TẠM — sẽ dọn ({len(temp)}); GIỮ state/siri_chat/*.jsonl (ngữ cảnh)")
        for f in temp or ["(không có)"]:
            print(f"    - {f}")
        traces = scrub_log_traces(True)
        print(f"\n[3] LOG — chạy SAU cùng để không bị ghi thêm dòng mới sau khi scrub")
        print(f"    file làm rỗng/xoá hẳn ({len(traces['emptied'])}):")
        for f in traces["emptied"] or ["(không có)"]:
            print(f"      - {f}")
        print(f"    file scrub dòng dấu vết ({len(traces['scrubbed'])}):")
        for f in traces["scrubbed"] or ["(không có)"]:
            print(f"      - {f}")
        print("\n[4] CỔNG SIRI — KHÔNG stop, chỉ kiểm /health:")
        for line in gate_health():
            print(f"    - {line}")
        return 0

    node = {"stopped": False, "removed": False, "error": "", "down": ""}
    if had_container:
        node = teardown_node()
        if node["error"]:
            return 1

    temp = clean_siri_temp(False)
    print(f"→ dọn chat tạm: {len(temp)} mục (giữ ngữ cảnh state/siri_chat/*.jsonl)")

    traces = scrub_log_traces(False)
    print(f"→ scrub log: {len(traces['scrubbed'])} file lọc dòng, "
          f"{len(traces['emptied'])} file rỗng/xoá")
    for line in traces["scrubbed"] + traces["emptied"]:
        if "LỖI" in line or "CÒN" in line:
            print(f"   ! {line}")

    health = gate_health()
    for line in health:
        print(f"→ {line}")

    if not args.no_notify:
        lines = ["🔒 Đã tắt Tailscale theo luật 17h30 (log đã xoá):"]
        if not had_container:
            lines.append("• Node: trước đó đã tắt")
        else:
            lines.append(f"• Node vbsme-log-gw: down={node['down']}, "
                         f"container {'đã stop' if node['stopped'] else 'CHƯA stop'}"
                         f"{' + đã xoá' if node['removed'] else ' (chưa xoá được)'} "
                         "— state GIỮ để tái dùng đúng node/IP")
            lines.append(f"• Log container: {log_lines} dòng đã mất cùng container")
        lines.append(f"• Chat tạm đã dọn: {len(temp)} mục (ngữ cảnh hội thoại giữ nguyên)")
        lines.append(f"• Log: {len(traces['scrubbed'])} file lọc dòng dấu vết, "
                     f"{len(traces['emptied'])} file rỗng/xoá hẳn")
        lines += [f"• {line}" for line in health]
        lines.append("Không còn đường vào nào TỪ NGOÀI; trong máy thì 2 cổng vẫn dùng bình thường.")
        notify("\n".join(lines))

    print("XONG.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
