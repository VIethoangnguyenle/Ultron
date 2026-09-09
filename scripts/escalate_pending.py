#!/usr/bin/env python3
"""Ultron escalation forwarder -> Hoang's Google Chat home channel.

Scans ~/.hermes/escalations/*.json (markers the agent writes when it can't
answer a group question) and forwards each to Hoang's DM via `hermes send`.
A marker is deleted only after a successful send, so transient failures retry
on the next cron tick. Runs as a no_agent cron job; stdout goes to cron logs.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
ESCALATION_DIR = HERMES_HOME / "escalations"
HERMES_BIN = os.environ.get("HERMES_BIN") or shutil.which("hermes") or str(Path.home() / ".local/bin/hermes")
TARGET = os.environ.get("ULTON_ESCALATE_TARGET", "google_chat")
SUBJECT = "Ultron cần Hoàng confirm"


def _format(data: dict) -> str:
    who = data.get("from") or "Không rõ"
    space = data.get("space") or "Không rõ"
    question = (data.get("question") or "").strip() or "(không có nội dung)"
    reason = (data.get("reason") or "").strip()
    lines = [
        "⚠️ *Ultron cần Hoàng xử lý*",
        "",
        f"*Người hỏi:* {who}",
        f"*Trong group:* {space}",
        "",
        "*Câu hỏi:*",
        f"`{question}`",
    ]
    if reason:
        lines.append("")
        lines.append(f"*Vì sao không tự trả lời:* {reason}")
    return "\n".join(lines)


def _send(message: str):
    try:
        r = subprocess.run(
            [HERMES_BIN, "send", "--to", TARGET, "--subject", SUBJECT, message],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as exc:
        return False, f"subprocess error: {exc}", ""
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    return r.returncode == 0, out, err


def main() -> int:
    if not ESCALATION_DIR.is_dir():
        return 0
    markers = sorted(ESCALATION_DIR.glob("*.json"))
    if not markers:
        return 0
    failed = False
    for m in markers:
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[escalate] skip {m.name}: bad json ({exc})")
            continue
        ok, out, err = _send(_format(data))
        if ok:
            print(f"[escalate] delivered {m.name}")
            m.unlink(missing_ok=True)
        else:
            failed = True
            print(f"[escalate] FAILED {m.name}: {err or out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
