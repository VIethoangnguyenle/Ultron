#!/usr/bin/env python3
"""Tắt & dọn Tailscale gateway (node log UAT/LIVE) — chạy theo lịch trong schedules.yaml.

Vì sao: node `ultron` (tên cũ `vbsme-log-gw`) mở đường riêng cho tester ở nhà đọc log + cổng Siri bridge.
Hoàng chốt 2026-09-12: **mọi kết nối Tailscale phải tắt sau 17h30** và **phải xoá log
Tailscale trên hệ thống** — không để lại dấu vết đường vào nào qua đêm.

    tailscale_teardown.py [--dry-run] [--no-notify]

Dọn gì:
  1. `tailscale down` node (GIỮ danh tính: state volume để lại ⇒ mở lại đúng node, đúng IP,
     không phải tạo node mới — bài học 2026-09-12: logout + xoá state ⇒ mất node, IP đổi,
     phải sửa config/cổng Siri/Shortcut mỗi lần)
  2. stop + rm container (xoá luôn log json của container)
  3. GIỮ volume `tailscale-state` (đó là danh tính node, không phải log — xoá là mất node)
  4. xoá file log có TÊN chứa "tailscale" (trừ script/skill — đó là công cụ, không phải log)
  5. SCRUB mọi dòng có dấu vết tailscale trong log chung (gateway.log, agent.log, *.txt/*.json
     ở ~/.hermes + /tmp). File mà sau khi scrub không còn dòng nào → xoá hẳn.

An toàn: không đụng container/service nào khác (vd `omni-sme-proxy`). Chạy lại nhiều lần vô hại.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CONTAINER = "tailscale"
VOLUME = "tailscale-state"
SPEAK_UNIT = "siri-speak"  # cổng "nói" cho Siri — cũng chết khi tailnet tắt
CHAT_UNIT = "siri-chat"    # cổng "chat" qua endpoint (client ngoài) — bind IP tailnet nên chết theo
DM_SPACE = "spaces/AAQAZxc2km8"  # DM riêng của Hoàng
NOTIFY_SCRIPT = Path.home() / ".hermes" / "scripts" / "gchat_send_text.py"
VENV_PY = Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python"

# Nơi có thể còn log/dấu vết. KHÔNG quét ~/.hermes/scripts và ~/.hermes/skills
# (script/skill là công cụ để bật lại — xoá là tự bắn vào chân).
SCAN_ROOTS = [
    Path("/tmp"),
    Path.home() / ".hermes",
    Path.home() / ".hermes" / "reports",
    Path.home() / ".hermes" / "logs",
    Path.home() / ".hermes" / "state",
]
SKIP_PREFIXES = [
    str(Path.home() / ".hermes" / "scripts"),
    str(Path.home() / ".hermes" / "skills"),
]
# Dấu vết cần xoá: IP node, tên node, tên phần mềm. (Không quét .yaml/.md — config & tài liệu
# bật lại phải giữ, nếu không thì hôm sau không dựng lại được.)
def _tailnet_ip_markers() -> list:
    """IP node hiện tại — node tạo lại là IP đổi, nên đọc từ state thay vì chỉ gắn cứng."""
    try:
        ip = (Path.home() / ".hermes" / "state" / "tailnet_ip.txt").read_text().strip()
    except Exception:
        ip = ""
    return [ip] if ip else []


MARKERS = tuple(_tailnet_ip_markers() + ["100.120.110.26", "vbsme-log-gw", "tailscale", "Tailscale",
                                         "tailscaled", "tskey-"])
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


def _candidates() -> list[Path]:
    """File log/dấu vết đáng soi (bỏ script, skill, file không phải text-log)."""
    out: list[Path] = []
    seen: set[str] = set()
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*")):
            real = str(path)
            if real in seen or not path.is_file():
                continue
            if path.suffix.lower() not in SCAN_SUFFIXES and ".log." not in path.name:
                continue  # log xoay vòng tên `agent.log.1` — suffix là ".1"
            if path.name in PROTECTED_NAMES:
                continue
            if any(real.startswith(pref) for pref in SKIP_PREFIXES):
                continue
            try:
                if path.stat().st_size > SCAN_MAX_BYTES:
                    continue
            except OSError:
                continue
            seen.add(real)
            out.append(path)
    return out


def purge_traces(dry_run: bool) -> dict[str, list[str]]:
    """Xoá/scrub dấu vết tailscale. Trả {'deleted': [...], 'scrubbed': ['file (N dòng)']}."""
    deleted: list[str] = []
    scrubbed: list[str] = []

    for path in _candidates():
        try:
            text = path.read_text(errors="replace")
        except Exception:  # noqa: BLE001
            continue
        lines = text.splitlines()
        hits = [ln for ln in lines if any(m in ln for m in MARKERS)]
        if not hits:
            continue
        keep = [ln for ln in lines if not any(m in ln for m in MARKERS)]
        if not [ln for ln in keep if ln.strip()]:
            deleted.append(f"{path} ({len(hits)} dòng, toàn bộ là dấu vết)")
            if not dry_run:
                try:
                    path.unlink()
                except Exception as exc:  # noqa: BLE001
                    deleted[-1] += f" LỖI: {exc}"
            continue
        scrubbed.append(f"{path} ({len(hits)}/{len(lines)} dòng)")
        if not dry_run:
            try:
                path.write_text("\n".join(keep) + ("\n" if text.endswith("\n") else ""))
            except Exception as exc:  # noqa: BLE001
                scrubbed[-1] += f" LỖI: {exc}"
    return {"deleted": deleted, "scrubbed": scrubbed}


def notify(text: str) -> None:
    if not NOTIFY_SCRIPT.exists():
        return
    py = str(VENV_PY) if VENV_PY.exists() else sys.executable
    code, out = sh([py, str(NOTIFY_SCRIPT), "--space", DM_SPACE, "--text", text], timeout=60)
    log = "đã gửi DM" if code == 0 else f"gửi DM lỗi (exit {code}: {out[:120]})"
    print(f"[notify] {log}")


def stop_speak_bridge() -> None:
    """Cổng Siri (bind IP tailnet) không thể sống khi tailnet chết — stop hẳn để khỏi crash-loop."""
    for unit in (SPEAK_UNIT, CHAT_UNIT):
        code, out = sh(["systemctl", "--user", "stop", unit], timeout=30)
        print(f"→ đã stop cổng {unit}" if code == 0
              else f"→ cổng {unit}: bỏ qua ({out[:100] or 'không chạy'})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] Tailscale teardown — container={CONTAINER} volume={VOLUME}")

    had_container = container_exists()
    if not had_container:
        print("→ container không tồn tại (đã tắt trước đó)")

    log_lines = 0
    if had_container:
        code, out = sh(["docker", "logs", CONTAINER])
        log_lines = len(out.splitlines()) if code == 0 else 0

    traces = purge_traces(args.dry_run)

    if args.dry_run:
        code, out = sh(["docker", "ps", "-a", "--filter", f"name={CONTAINER}",
                        "--format", "{{.Names}} | {{.Status}}"])
        print(f"→ DRY-RUN: sẽ down node (giữ state) + stop/rm container {CONTAINER}; volume {VOLUME} GIỮ LẠI")
        print(f"   hiện trạng: {out or '(không đọc được)'}")
        print(f"   log container sẽ mất cùng container: {log_lines} dòng")
        print(f"   file xoá hẳn ({len(traces['deleted'])}):")
        for f in traces["deleted"] or ["(không có)"]:
            print(f"     - {f}")
        print(f"   → sẽ stop cổng Siri ({SPEAK_UNIT}) + cổng chat ({CHAT_UNIT}) vì chúng bind IP tailnet")
        print(f"   file scrub dòng dấu vết ({len(traces['scrubbed'])}):")
        for f in traces["scrubbed"] or ["(không có)"]:
            print(f"     - {f}")
        return 0

    stop_speak_bridge()
    if had_container:
        code, out = sh(["docker", "exec", CONTAINER, "tailscale", "down"], timeout=45)
        print(f"→ down node (giữ danh tính/IP): {'OK' if code == 0 else f'bỏ qua (exit {code}: {out[:120]})'}")

        code, out = sh(["docker", "stop", CONTAINER], timeout=90)
        if code != 0:
            print(f"LỖI: không stop được container → {out[:200]}")
            return 1
        print("→ đã stop container")

        code, out = sh(["docker", "rm", CONTAINER], timeout=60)
        print("→ đã xoá container (kèm log)" if code == 0
              else f"cảnh báo: xoá container lỗi ({out[:120]})")

        # Cầu nối ra tailnet (git.vnpay.vn :9445 / console :9446) KHÔNG cần tắt riêng:
        # nó nằm ngay trong nginx của Hoàng (omni-sme-proxy) và chỉ allow dải CGNAT
        # 100.64.0.0/10 ⇒ Tailscale down là tự nhiên không ai vào được nữa.

        # GIỮ volume state: đó là danh tính node (machine key + IP), không phải log.
        # Xoá nó ⇒ lần mở sau phải tạo node mới ⇒ IP mới ⇒ sửa config + cổng Siri + Shortcut.
        code_v, out_v = sh(["docker", "volume", "ls", "--filter", f"name={VOLUME}", "--format", "{{.Name}}"], timeout=30)
        if code_v == 0 and VOLUME in out_v.split():
            print(f"→ giữ volume {VOLUME} (danh tính node — cố ý KHÔNG xoá)")

    if not args.no_notify:
        lines = [f"🔒 Đã tắt Tailscale theo luật 17h30 (log đã xoá):"]
        lines.append(f"• Node vbsme-log-gw: down + xoá container (state GIỮ để tái dùng đúng node/IP)" if had_container
                     else "• Node: trước đó đã tắt")
        lines.append(f"• Log container: {log_lines} dòng đã xoá")
        lines.append(f"• File log xoá hẳn: {len(traces['deleted'])}"
                     + (f" ({', '.join(Path(d).name for d in traces['deleted'][:4])})"
                        if traces["deleted"] else ""))
        lines.append(f"• Dòng dấu vết scrub trong log chung: {len(traces['scrubbed'])} file")
        lines.append("• Cổng Siri (siri-speak :9444) + cổng chat (:9445): đã stop — muốn dùng lại thì bảo em bật lại")
        lines.append("Không còn đường vào nào từ ngoài. Cần mở lại thì nhắn em ạ.")
        notify("\n".join(lines))

    print("XONG.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
