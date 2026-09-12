#!/usr/bin/env python3
"""Cong kiem tra MCP cua CLAUDE truoc khi giao viec coding / fix bug / ban giao vietbank-sme.

Ly do ton tai (Hoang chot 2026-09-12): Ultron la nguoi dieu phoi claude thay Hoang.
TRUOC KHI claude code, toan bo MCP cua no phai READY. Script nay la cong chan do.

Nguon su that (khong doan):
  1. <workspace>/.mcp.json            -> danh sach server + lenh/url
  2. <workspace>/.claude/settings.local.json -> enabledMcpjsonServers (server nao da duoc duyet)
  3. `claude mcp list` (health that)  -> trang thai song/chet/cho-duyet
  4. Voi server stdio: binary co trong PATH khong. Voi server http: cong co mo khong.

Cach dung:
  python3 claude_mcp_preflight.py              # kiem tra day du (goi ca claude mcp list)
  python3 claude_mcp_preflight.py --quick       # chi kiem binary + cong (nhanh, khong goi claude)
  python3 claude_mcp_preflight.py --fix         # tu sua cai sua duoc: cai lai codegraph, duyet ten
                                                # server trong settings.local.json, bat IDE cho MCP idea
  python3 claude_mcp_preflight.py --json        # in JSON de may doc

Exit code: 0 = tat ca MCP cua workspace READY | 1 = co cai chua ready (KHONG duoc giao claude code)
Ghi report: ~/.hermes/reports/claude_mcp_preflight_<YYYY-MM-DD>.md
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

WS_DEFAULT = Path("/home/zane/Desktop/work/vietbank/vietbank-sme")
REPORT_DIR = Path.home() / ".hermes" / "reports"
CODEGRAPH_PKG = "@colbymchenry/codegraph"
CODEGRAPH_PIN = "1.6.0"          # pin = khop phien ban da build index (.codegraph/codegraph.db)
IDEA_PORT = 64342
IDEA_BIN = "/snap/bin/intellij-idea-ultimate"
IDEA_LOG = "/tmp/idea-start.log"

OK, BAD, PEND = "✔", "✘", "⏸"


def load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ws_servers(ws: Path) -> dict:
    return load_json(ws / ".mcp.json").get("mcpServers", {}) or {}


def approved_names(ws: Path) -> list:
    s = load_json(ws / ".claude" / "settings.local.json")
    return list(s.get("enabledMcpjsonServers", []) or [])


def quick_checks(servers: dict) -> dict:
    """Kiem nhanh: binary (stdio) hoac cong (http). Tra {ten: (ok, ghi chu)}."""
    out = {}
    for name, cfg in servers.items():
        if cfg.get("type") == "stdio" or "command" in cfg:
            cmd = cfg.get("command", "")
            found = shutil.which(cmd)
            out[name] = (bool(found), f"binary: {found or 'KHONG thay trong PATH'}")
        else:
            url = cfg.get("url", "")
            m = re.match(r"https?://([^/:]+):(\d+)", url)
            if not m:
                out[name] = (None, f"url khong doc duoc: {url}")
                continue
            host, port = m.group(1), int(m.group(2))
            up = port_open("127.0.0.1" if host == "localhost" else host, port)
            out[name] = (up, f"cong {host}:{port} {'MO' if up else 'DONG'}")
    return out


def claude_list(ws: Path, timeout: int = 220) -> dict:
    """Chay `claude mcp list` — nguon su that ve health. Tra {ten: (status, raw)}."""
    try:
        r = subprocess.run(["claude", "mcp", "list"], cwd=str(ws), capture_output=True,
                           text=True, timeout=timeout)
        text = (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return {"__error__": ("timeout", f"claude mcp list qua {timeout}s")}
    except FileNotFoundError:
        return {"__error__": ("no-claude", "khong tim thay lenh `claude`")}
    res = {}
    for line in text.splitlines():
        m = re.match(r"^(?P<name>[^:]+):\s+(?P<rest>.*?)\s+-\s+(?P<st>[^\s].*)$", line.strip())
        if not m:
            continue
        name, st = m.group("name").strip(), m.group("st").strip()
        if st.startswith(OK):
            res[name] = ("connected", st)
        elif st.startswith(BAD):
            res[name] = ("failed", st)
        elif st.startswith(PEND):
            res[name] = ("pending", st)
        else:
            res[name] = ("other", st)
    return res


def backup(p: Path) -> Path:
    b = p.with_suffix(p.suffix + f".bak-{datetime.now():%Y%m%d-%H%M%S}")
    b.write_bytes(p.read_bytes())
    return b


def fix_codegraph() -> str:
    if shutil.which("codegraph"):
        return "codegraph: da co binary, khong can cai"
    r = subprocess.run(["npm", "i", "-g", f"{CODEGRAPH_PKG}@{CODEGRAPH_PIN}"],
                       capture_output=True, text=True, timeout=600)
    ok = shutil.which("codegraph") is not None
    return f"codegraph: cai lai {CODEGRAPH_PKG}@{CODEGRAPH_PIN} -> {'OK' if ok else 'THAT BAI'} ({r.stdout.strip()[-120:] or r.stderr.strip()[-120:]})"


def fix_approved(ws: Path, servers: dict) -> str:
    f = ws / ".claude" / "settings.local.json"
    d = load_json(f)
    cur = list(d.get("enabledMcpjsonServers", []) or [])
    add = [n for n in servers if n not in cur]
    if not add:
        return "duyet server: du roi"
    backup(f)
    d["enabledMcpjsonServers"] = cur + add
    f.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"duyet server: them {add} (da backup {f.name})"


def fix_idea(wait: int = 180) -> str:
    if port_open("127.0.0.1", IDEA_PORT):
        return f"idea: cong {IDEA_PORT} da mo, khong can bat IDE"
    if not Path(IDEA_BIN).exists():
        return f"idea: KHONG thay {IDEA_BIN} — bao Hoang"
    subprocess.Popen(
        ["setsid", "nohup", IDEA_BIN, str(WS_DEFAULT)],
        stdout=open(IDEA_LOG, "ab"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        cwd="/tmp", env={**__import__("os").environ, "DISPLAY": ":0"}, start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < wait:
        if port_open("127.0.0.1", IDEA_PORT, timeout=1):
            return f"idea: da bat IDE, cong {IDEA_PORT} mo sau {int(time.time()-t0)}s (log {IDEA_LOG})"
        time.sleep(3)
    return f"idea: bat IDE nhung cong {IDEA_PORT} KHONG mo sau {wait}s — xem {IDEA_LOG}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=str(WS_DEFAULT))
    ap.add_argument("--quick", action="store_true", help="chi kiem binary + cong, khong goi claude")
    ap.add_argument("--fix", action="store_true", help="tu sua cai sua duoc")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    ws = Path(a.workspace)
    servers = ws_servers(ws)
    if not servers:
        print(f"KHONG doc duoc mcpServers trong {ws}/.mcp.json"); return 1

    fixes = []
    if a.fix:
        fixes.append(fix_codegraph())
        fixes.append(fix_approved(ws, servers))
        if "idea" in servers:
            fixes.append(fix_idea())

    quick = quick_checks(servers)
    live = {} if a.quick else claude_list(ws)

    rows, bad = [], []
    for name in servers:
        st = live.get(name, ("?", "khong kiem tra (--quick)"))[0]
        st_txt = live.get(name, ("?", "chua kiem tra"))[1]
        ok_quick, note = quick.get(name, (None, ""))
        if a.quick:
            ready = bool(ok_quick)
        else:
            ready = (st == "connected") and (ok_quick is not False)
        rows.append({"server": name, "ready": ready, "state": st, "detail": f"{note} | {st_txt}"})
        if not ready:
            bad.append(name)

    if a.json:
        print(json.dumps({"workspace": str(ws), "ready": not bad, "servers": rows,
                          "fixes": fixes}, ensure_ascii=False, indent=2))
    else:
        print(f"=== MCP CUA CLAUDE — workspace {ws}")
        print(f"{'server':<12} {'ready':<6} {'trang thai':<11} chi tiet")
        for r in rows:
            print(f"{r['server']:<12} {('OK' if r['ready'] else 'CHUA'):<6} {r['state']:<11} {r['detail'][:110]}")
        extra = {k: v for k, v in live.items() if k not in servers and not k.startswith("__")}
        if extra:
            print("\n(claude.ai connectors — khong tinh vao cong chan):")
            for k, v in extra.items():
                print(f"  {k:<28} {v[1][:80]}")
        if fixes:
            print("\n=== DA TU SUA:")
            for f_ in fixes:
                print(f"  - {f_}")
        print("\nKET LUAN: " + ("READY — duoc phep giao claude code" if not bad
                               else f"CHUA READY ({', '.join(bad)}) — KHONG duoc giao claude code"))

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rep = REPORT_DIR / f"claude_mcp_preflight_{datetime.now():%Y-%m-%d}.md"
    lines = [f"# Cong MCP claude — {datetime.now():%Y-%m-%d %H:%M}", f"Workspace: `{ws}`", "",
             "| server | ready | trang thai | chi tiet |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['server']} | {'OK' if r['ready'] else 'CHUA'} | {r['state']} | {r['detail'][:160]} |")
    if fixes:
        lines += ["", "## Tu sua"] + [f"- {x}" for x in fixes]
    lines += ["", f"**Ket luan:** {'READY' if not bad else 'CHUA READY: ' + ', '.join(bad)}"]
    rep.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nreport: {rep}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
