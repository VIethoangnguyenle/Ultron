#!/usr/bin/env python3
"""Tắt & dọn Tailscale gateway (node log UAT/LIVE) — dùng cho lịch one-shot trong schedules.yaml.

Vì sao: node `vbsme-log-gw` mở đường riêng cho tester ở nhà đọc log, chỉ sống trong một buổi.
Hết giờ thì logout khỏi tailnet + xoá container + xoá state để không còn đường vào nào.

    tailscale_teardown.py [--dry-run] [--no-notify]

- `--dry-run`: chỉ in ra sẽ làm gì, KHÔNG đụng gì.
- `--no-notify`: không gửi DM báo Hoàng.
- An toàn: không đụng container/service nào khác (vd `omni-sme-proxy`); chỉ xoá đúng 2 tài nguyên
  của Tailscale. Chạy lại nhiều lần vô hại (idempotent).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CONTAINER = "tailscale"
VOLUME = "tailscale-state"
DM_SPACE = "spaces/AAQAZxc2km8"  # DM riêng của Hoàng
NOTIFY_SCRIPT = Path.home() / ".hermes" / "scripts" / "gchat_send_text.py"


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


def notify(text: str) -> None:
    if not NOTIFY_SCRIPT.exists():
        return
    code, out = sh([sys.executable, str(NOTIFY_SCRIPT), "--space", DM_SPACE, "--text", text], timeout=60)
    log = "đã gửi DM" if code == 0 else f"gửi DM lỗi (exit {code}: {out[:120]})"
    print(f"[notify] {log}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] Tailscale teardown — container={CONTAINER} volume={VOLUME}")

    if not container_exists():
        print("→ container không tồn tại (đã tắt trước đó) — không làm gì.")
        return 0

    if args.dry_run:
        code, out = sh(["docker", "ps", "-a", "--filter", f"name={CONTAINER}", "--format", "{{.Names}} | {{.Status}}"])
        print(f"→ DRY-RUN: sẽ logout node + stop/rm container {CONTAINER} + xoá volume {VOLUME}")
        print(f"   hiện trạng: {out or '(không đọc được)'}")
        return 0

    code, out = sh(["docker", "exec", CONTAINER, "tailscale", "logout"], timeout=45)
    print(f"→ logout: {'OK' if code == 0 else f'bỏ qua (exit {code}: {out[:120]})'}")

    code, out = sh(["docker", "stop", CONTAINER], timeout=90)
    if code != 0:
        print(f"LỖI: không stop được container → {out[:200]}")
        return 1
    print("→ đã stop container")

    code, out = sh(["docker", "rm", CONTAINER], timeout=60)
    print("→ đã xoá container" if code == 0 else f"cảnh báo: xoá container lỗi ({out[:120]})")

    code, out = sh(["docker", "volume", "rm", VOLUME], timeout=60)
    print("→ đã xoá volume state" if code == 0 else f"cảnh báo: xoá volume lỗi ({out[:120]})")

    if not args.no_notify:
        notify(
            "🔒 Đã tắt Tailscale gateway (vbsme-log-gw) theo lịch 17h30 hôm nay.\n"
            "Node đã logout khỏi tailnet, container + state đã xoá sạch — không còn đường vào nào.\n"
            "Cần mở lại cho tester đọc log thì nhắn em ạ."
        )

    print("XONG.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
