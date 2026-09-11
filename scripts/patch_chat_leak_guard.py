#!/usr/bin/env python3
"""Vá 'chốt cứng chống lọt source' sang adapter Google Chat của máy Kitty.

Cùng code base Hermes → lấy nguyên khối chốt từ adapter máy này, chèn vào 3 điểm
tương ứng ở adapter máy kia (hằng số + send() + _send_file_reply), backup trước khi ghi.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

REMOTE = "nguyen@10.173.137.191"
REMOTE_FILE = ".hermes/hermes-agent/plugins/platforms/google_chat/adapter.py"
LOCAL_FILE = pathlib.Path.home() / ".hermes/hermes-agent/plugins/platforms/google_chat/adapter.py"

START = "# --- Chốt an toàn tầng GỬI TIN"
END = "_google_id_token_request: Any = None"


def sh(*args: str, stdin: str | None = None) -> str:
    res = subprocess.run(list(args), input=stdin, capture_output=True, text=True, timeout=90)
    if res.returncode != 0:
        print(f"LỖI {' '.join(args[:2])}: {res.stderr.strip()[:300]}")
        sys.exit(1)
    return res.stdout


local = LOCAL_FILE.read_text(encoding="utf-8")
block = local[local.index(START):local.index(END)]
assert block.strip() and "_LEAK_GUARD_ALLOW" in block, "không trích được khối chốt từ máy này"

remote_text = sh("ssh", "-o", "BatchMode=yes", REMOTE, f"cat {REMOTE_FILE}")
if "_LEAK_GUARD_ALLOW" in remote_text:
    print("Máy Kitty đã có chốt cứng rồi — bỏ qua.")
    sys.exit(0)

anchor_const = "_GOOGLE_ID_TOKEN_CERTS_TTL_SECONDS = 300\n"
assert remote_text.count(anchor_const) == 1, "anchor hằng số không khớp"

anchor_send = ("        thread_id = self._resolve_thread_id(reply_to, metadata, chat_id=chat_id)\n"
               "        self.pause_typing_for_chat(chat_id)")
assert remote_text.count(anchor_send) == 1, "anchor send() không khớp"

anchor_file = ("        mime_hint: Optional[str], override_filename: Optional[str] = None,\n"
               "    ) -> SendResult:\n"
               "        thread_id = self._resolve_thread_id(reply_to, kwargs.get(\"metadata\"), chat_id=chat_id)")
assert remote_text.count(anchor_file) == 1, "anchor _send_file_reply() không khớp"

new = remote_text.replace(anchor_const, anchor_const + "\n" + block)
new = new.replace(anchor_send, "        content = _leak_guard_text(chat_id, content)\n" + anchor_send)
new = new.replace(anchor_file, anchor_file.replace(
    "        thread_id = self._resolve_thread_id(reply_to, kwargs.get(\"metadata\"), chat_id=chat_id)",
    "        if chat_id not in _LEAK_GUARD_ALLOW:\n"
    "            suffix = _Path(override_filename or path).suffix.lower()\n"
    "            reason = (\"file-suffix:\" + suffix) if suffix in _LEAK_FILE_SUFFIXES else _leak_reason(caption or \"\")\n"
    "            if reason:\n"
    "                _leak_guard_record(chat_id, reason, f\"[file {path}] {caption or ''}\")\n"
    "                return await self.send(chat_id, _LEAK_SAFE_REPLY, reply_to=reply_to,\n"
    "                                       metadata=kwargs.get(\"metadata\"))\n"
    "        thread_id = self._resolve_thread_id(reply_to, kwargs.get(\"metadata\"), chat_id=chat_id)"))

sh("ssh", "-o", "BatchMode=yes", REMOTE, f"cp {REMOTE_FILE} {REMOTE_FILE}.bak-leakguard")
sh("ssh", "-o", "BatchMode=yes", REMOTE, f"cat > {REMOTE_FILE}", stdin=new)

check = sh("ssh", "-o", "BatchMode=yes", REMOTE,
           "cd ~/.hermes/hermes-agent && grep -c '_LEAK_GUARD_ALLOW' plugins/platforms/google_chat/adapter.py && "
           "venv/bin/python -m py_compile plugins/platforms/google_chat/adapter.py && echo COMPILE_OK")
print("Kitty:", check.strip())
