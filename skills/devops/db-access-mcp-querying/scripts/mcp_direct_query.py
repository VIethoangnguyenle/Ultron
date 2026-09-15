#!/usr/bin/env python3
"""Tra DB qua cổng MCP db-access bằng một SOURCE (apiKey) chỉ định.

Dùng khi session MCP của Hermes đang giữ snapshot quyền cũ (xem SKILL.md), hoặc để tự verify
quyền của một source mà không phải restart gateway.

    # xem các source + DB được cấp (không in key)
    python3 mcp_direct_query.py --sources

    # liệt kê DB mà một source thấy
    python3 mcp_direct_query.py --source default_agent --list

    # chạy SELECT
    python3 mcp_direct_query.py --source vietbank_omni --db VBDIGIONL \\
        --sql "SELECT CODE, VI_CONTENT FROM VBDIGIONL.AD_MESSAGE WHERE CODE='500050'"

KHÔNG in apiKey ra output. Chỉ đọc; muốn ghi thì dùng tool sql_write của Hermes theo quy trình SOUL.
"""
import argparse
import json
import os
import re
import sys
import urllib.request

DB_ACCESS_DIR = os.path.expanduser("~/Desktop/tools/mcp/Db-Access")
CONFIG = os.path.join(DB_ACCESS_DIR, "config.yaml")
ENV_FILE = os.path.join(DB_ACCESS_DIR, ".env")
URL = "http://127.0.0.1:8443/mcp"


def read_env():
    try:
        txt = open(ENV_FILE).read()
    except OSError as exc:
        sys.exit(f"khong doc duoc .env: {exc}")
    return dict(re.findall(r"^([A-Z_]+)=(.*)$", txt, re.M))


def read_sources():
    import yaml  # PyYAML co san trong venv Hermes

    cfg = yaml.safe_load(open(CONFIG))
    env = read_env()
    out = {}
    for name, spec in (cfg.get("sources") or {}).items():
        key = str(spec.get("apiKey", ""))
        m = re.fullmatch(r"\$\{([A-Z_]+)\}", key)
        out[name] = {
            "key": env.get(m.group(1), "") if m else key,
            "access": spec.get("access") or {},
        }
    return out, (cfg.get("databases") or {})


def post(body, key, sid=None):
    headers = {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "x-api-key": key,
    }
    if sid:
        headers["mcp-session-id"] = sid
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.headers.get("mcp-session-id"), resp.read().decode()


def unwrap(raw):
    """Response co the la JSON thuong hoac SSE (dong 'data: {...}')."""
    text = raw.strip()
    if text.startswith("event:") or "\ndata:" in text or text.startswith("data:"):
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
    return json.loads(text)


def call_tool(key, tool, arguments):
    sid, _ = post(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "ultron-direct", "version": "1.0"},
            },
        },
        key,
    )
    try:
        post({"jsonrpc": "2.0", "method": "notifications/initialized"}, key, sid)
    except Exception:
        pass  # mot so server khong bat buoc notification nay
    _, raw = post(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
        key,
        sid,
    )
    payload = unwrap(raw)
    result = payload.get("result") or payload
    if isinstance(result, dict) and result.get("content"):
        return result["content"][0].get("text", "")
    return json.dumps(payload, ensure_ascii=False)[:2000]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="default_agent", help="ten source trong config (mac dinh default_agent)")
    ap.add_argument("--sources", action="store_true", help="liet ke source + DB duoc cap")
    ap.add_argument("--list", action="store_true", help="goi list_databases cua source")
    ap.add_argument("--db", help="db_name cho sql_read")
    ap.add_argument("--sql", help="cau SELECT")
    args = ap.parse_args()

    sources, databases = read_sources()

    if args.sources:
        for name in sorted(sources):
            acc = sources[name]["access"]
            granted = ", ".join(f"{db}[{'+'.join(caps)}]" for db, caps in sorted(acc.items()))
            key_ok = "key OK" if sources[name]["key"] else "THIEU KEY trong .env"
            print(f"{name}: {key_ok}; databases block co entry: "
                  f"{sum(1 for db in acc if db in databases)}/{len(acc)}")
            print(f"    {granted}")
        return

    if args.source not in sources:
        sys.exit(f"source '{args.source}' khong co trong config. Co: {', '.join(sorted(sources))}")
    key = sources[args.source]["key"]
    if not key:
        sys.exit("key rong — kiem bien tuong ung trong .env")

    if args.list or not args.sql:
        print(call_tool(key, "list_databases", {}))
        return
    print(call_tool(key, "sql_read", {"db_name": args.db, "sql": args.sql}))


if __name__ == "__main__":
    main()
