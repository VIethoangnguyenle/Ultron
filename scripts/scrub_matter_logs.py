#!/usr/bin/env python3
"""Xoá dấu vết log của MỘT việc cụ thể trên hệ thống (mặc định: vụ Tailscale/Siri/gateway).

Khác `tailscale_teardown.py`: script kia là luật hằng ngày; cái này là lượt dọn theo yêu cầu,
quét rộng hơn (log Hermes, cron, process-results, bash history) nhưng vẫn theo danh sách
marker + danh sách bảo vệ tường minh.

    scrub_matter_logs.py [--apply]        # mặc định dry-run, chỉ in ra sẽ làm gì

Nguyên tắc:
- Chỉ xoá DÒNG chứa marker trong file log; file mà toàn bộ dòng đều là marker ⇒ xoá file.
- KHÔNG đụng: script, skill, tài liệu, config/route, credential (xem PROTECTED).
- File .db (sqlite) ⇒ xoá DÒNG dữ liệu chứa marker trong các bảng text.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

HOME = Path.home()
MARKERS = [
    "tailscale", "Tailscale", "tailscaled",
    "vbsme-log-gw",
    "100.120.110.26", "100.96.114.93", "100.82.132.36",
    "tskey-",
    "siri-speak", "siri_speak",
    "git.vnpay.vn", "console-cmc-test-rke03",
]

ROOTS = [
    HOME / ".hermes" / "logs",
    HOME / ".hermes" / "cron",
]
TMP_PATTERNS = ["*.log", "*.txt", "*.json", "*.md", "*.out", "*.err"]
# KHÔNG đụng: công cụ + tài liệu + config + credential
PROTECTED_NAMES = {
    "webhook_subscriptions.json", "config.yaml", "state.db", "siri_token.txt",
    "tailscale_authkey.txt", "tailnet_ip.txt", "schedules.yaml", "a2a_agents.json",
    "people.json", "ultron_spaces.json", "SOUL.md", "USER.md", "MEMORY.md",
}
SKIP_DIR_PARTS = {
    "skills", "scripts", "memories", "hermes-agent",
    "ultron_logfetch", "vbsme-log-1209", "claude-1001",
}
TEXT_SUFFIXES = {".log", ".txt", ".json", ".jsonl", ".md", ".out", ".err"}
SCAN_MAX_BYTES = 5_000_000
SKIP_DIRS = [HOME / ".hermes" / "scripts", HOME / ".hermes" / "skills",
             HOME / ".hermes" / "memories", HOME / ".hermes" / "profiles"]


def protected(path: Path) -> bool:
    if path.name in PROTECTED_NAMES:
        return True
    if any(part in SKIP_DIR_PARTS for part in path.parts):
        return True
    return any(str(path).startswith(str(d)) for d in SKIP_DIRS)


def candidates() -> list[Path]:
    out: list[Path] = []
    for root in ROOTS:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file() and not protected(p):
                out.append(p)
    tmp = Path("/tmp")
    for pat in TMP_PATTERNS:
        for p in sorted(tmp.glob(pat)):
            if p.is_file() and not protected(p):
                out.append(p)
    bh = HOME / ".bash_history"
    if bh.is_file() and not protected(bh):
        out.append(bh)
    return out


def scrub_file(path: Path, apply: bool) -> tuple[str, int]:
    # Log xoay vòng đặt tên `agent.log.1` ⇒ suffix là ".1" chứ không phải ".log":
    # nhận theo tên chứa ".log." để không bỏ sót bản cũ.
    if (path.suffix.lower() not in TEXT_SUFFIXES
            and ".log." not in path.name
            and path.name != ".bash_history"):
        return ("skip", 0)
    try:
        if path.stat().st_size > SCAN_MAX_BYTES:
            return ("skip-size", 0)
        text = path.read_text(errors="replace")
    except Exception:
        return ("unreadable", 0)
    lines = text.splitlines()
    hits = [ln for ln in lines if any(m in ln for m in MARKERS)]
    if not hits:
        return ("clean", 0)
    # File cache kết quả tool (process-results): dính dấu vết ⇒ xoá cả file,
    # cắt 1 dòng trong JSON blob sẽ hỏng cấu trúc mà chẳng giữ được gì.
    if "process-results" in str(path):
        if apply:
            try:
                path.unlink()
            except Exception as exc:  # noqa: BLE001
                return (f"DELETE-FAIL {exc}", len(hits))
        return ("deleted", len(hits))
    keep = [ln for ln in lines if not any(m in ln for m in MARKERS)]
    if not [ln for ln in keep if ln.strip()]:
        if apply:
            try:
                path.unlink()
            except Exception as exc:  # noqa: BLE001
                return (f"DELETE-FAIL {exc}", len(hits))
        return ("deleted", len(hits))
    if apply:
        try:
            path.write_text("\n".join(keep) + ("\n" if text.endswith("\n") else ""))
        except Exception as exc:  # noqa: BLE001
            return (f"SCRUB-FAIL {exc}", len(hits))
    return ("scrubbed", len(hits))


def scrub_db(path: Path, apply: bool) -> tuple[str, int]:
    """sqlite: xoá dòng có marker trong cột text của mọi bảng."""
    try:
        con = sqlite3.connect(str(path))
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        tables = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        removed = 0
        for t in tables:
            cols = [r[1] for r in cur.execute(f'PRAGMA table_info("{t}")').fetchall()]
            for c in cols:
                where = " OR ".join([f'"{c}" LIKE ?'] * len(MARKERS))
                try:
                    n = cur.execute(
                        f'SELECT COUNT(*) FROM "{t}" WHERE {where}',
                        [f"%{m}%" for m in MARKERS]).fetchone()[0]
                except Exception:
                    continue
                if n:
                    removed += n
                    if apply:
                        cur.execute(f'DELETE FROM "{t}" WHERE {where}',
                                    [f"%{m}%" for m in MARKERS])
        if apply and removed:
            con.commit()
            cur.execute("VACUUM")
        con.close()
        return ("db-rows" if removed else "clean", removed)
    except Exception as exc:  # noqa: BLE001
        return (f"DB-FAIL {exc}", 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="thực thi (mặc định chỉ dry-run)")
    args = ap.parse_args()
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== scrub dấu vết ({mode}) — {len(MARKERS)} marker: {', '.join(MARKERS[:6])} ...")
    n_files = n_lines = n_del = n_db = 0
    for p in candidates():
        if p.suffix.lower() == ".db":
            status, cnt = scrub_db(p, args.apply)
            if cnt:
                n_db += cnt
                print(f"  [{status}] {p} — {cnt} dòng")
            continue
        status, cnt = scrub_file(p, args.apply)
        if status == "clean":
            continue
        n_files += 1
        n_lines += cnt
        if status == "deleted":
            n_del += 1
        print(f"  [{status}] {p} — {cnt} dòng")
    print(f"=== tổng: {n_files} file ({n_del} xoá hẳn, {n_lines} dòng) + {n_db} dòng DB")
    if not args.apply:
        print("=== (dry-run) chạy lại với --apply để thực thi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
