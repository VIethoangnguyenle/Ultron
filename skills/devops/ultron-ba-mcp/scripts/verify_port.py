#!/usr/bin/env python3
"""Kiem chung DOC LAP cong Ultron BA MCP (15 ca).

Chay: cd /home/zane/Desktop/tools/mcp/Ultron-BA-MCP && .venv/bin/python \
        ~/.hermes/skills/devops/ultron-ba-mcp/scripts/verify_port.py
Exit != 0 neu co ca FAIL. Tu cap key tam (verify-scope, verify-rpm2) roi xoa; khong in key tho.
"""
import asyncio, json, subprocess, time
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ROOT = Path("/home/zane/Desktop/tools/mcp/Ultron-BA-MCP")
PY = str(ROOT / ".venv/bin/python")
URL = "http://127.0.0.1:9450/mcp"
HKEY = (Path.home() / ".hermes/state/ba_mcp/hoang.key").read_text().strip()
AUDIT = Path.home() / ".hermes/state/ba_mcp/audit.jsonl"

results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("[PASS] " if ok else "[FAIL] ") + name + (" — " + str(detail)[:220] if detail else ""))

def keyctl(*args):
    return subprocess.run([PY, "scripts/keys.py", *args], cwd=ROOT, capture_output=True, text=True).stdout

async def call(s, name, args):
    r = await s.call_tool(name, args)
    if r.isError:
        return {"__isError": True, "text": (r.content[0].text if r.content else "")[:200]}
    try:
        return json.loads(r.content[0].text)
    except Exception as e:
        return {"__bad": str(e)}

async def with_key(key, fn):
    async with streamablehttp_client(URL, headers={"x-api-key": key}) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await fn(s)

async def main():
    keyctl("remove", "--label", "verify-scope")
    keyctl("add", "--label", "verify-scope", "--projects", "vietbank-sme",
           "--default-project", "vietbank-sme", "--rpm", "300", "--out", "/tmp/vk.key")
    vk = Path("/tmp/vk.key").read_text().strip()

    async def hcheck(s):
        tl = await call(s, "tools/list", {}) if False else None
        return None

    # --- 1. ten tool khong doi
    async def f1(s):
        res = await s.list_tools()
        tools = getattr(res, "tools", None)
        if tools is None:
            tools = res[0] if isinstance(res, (tuple, list)) else res
        names = [getattr(t, "name", None) or (t[0] if isinstance(t, (tuple, list)) else None) for t in tools]
        return names
    names = await with_key(HKEY, f1)
    check("tools/list = 16 tool, khong doi ten", len(names) == 16 and "search" in names and "get_flow" in names,
          f"{len(names)} tool")

    # --- 2/3. chan theo key
    async def f_scope(s):
        a = await call(s, "search", {"query": "chi lương"})
        b = await call(s, "search", {"query": "chi lương", "project": "vietbank-digital"})
        c = await call(s, "search", {"query": "chi lương", "project": "*"})
        return a, b, c
    a, b, c = await with_key(vk, f_scope)
    check("key scoped + bo trong project -> dung default cua key",
          a.get("ok") and (a.get("meta") or {}).get("project") == "vietbank-sme"
          and (a.get("meta") or {}).get("project_source") == "key_default",
          f"project={(a.get('meta') or {}).get('project')} source={(a.get('meta') or {}).get('project_source')}")
    check("key scoped + project khac scope -> PROJECT_OUT_OF_SCOPE",
          (b.get("error") or {}).get("code") == "PROJECT_OUT_OF_SCOPE",
          f"code={(b.get('error') or {}).get('code')}")
    check("key scoped + project='*' -> thu hep ve scope",
          c.get("ok") and (c.get("meta") or {}).get("scope_applied") is True
          and (c.get("meta") or {}).get("project") == "vietbank-sme",
          f"scope_applied={(c.get('meta') or {}).get('scope_applied')}")

    # --- key * : bo trong project -> BAD_ARG
    d = await with_key(HKEY, lambda s: call(s, "search", {"query": "chi lương"}))
    check("key * + bo trong project -> BAD_ARG (khong doan)", (d.get("error") or {}).get("code") == "BAD_ARG",
          (d.get("error") or {}).get("message", "")[:80])

    # --- 4. khop mo trung thuc (loi nguy hiem nhat)
    async def f_fuzzy(s):
        return (await call(s, "get_flow", {"flow": "zzz khong ton tai xyz", "project": "vietbank-sme"}),
                await call(s, "get_flow", {"flow": "zzz khong ton tai xyz", "project": "vietbank-digital"}),
                await call(s, "get_flow", {"flow": "Tạo lệnh chi lương", "project": "vietbank-sme"}),
                await call(s, "explain_error_code", {"code": "999999999"}))
    q1, q2, q3, q4 = await with_key(HKEY, f_fuzzy)
    check("get_flow ten vo nghia (vbsme) -> NOT_FOUND", (q1.get("error") or {}).get("code") == "NOT_FOUND",
          json.dumps((q1.get("error") or {}).get("nearest"), ensure_ascii=False)[:120])
    check("get_flow ten vo nghia (digital) -> NOT_FOUND (truoc day tra bua)",
          (q2.get("error") or {}).get("code") == "NOT_FOUND")
    check("get_flow ten dung -> ok + match exact",
          q3.get("ok") and ((q3.get("data") or {}).get("match") or {}).get("kind") == "exact",
          f"match={(q3.get('data') or {}).get('match')}")
    check("explain_error_code ma khong ton tai -> NOT_FOUND",
          (q4.get("error") or {}).get("code") == "NOT_FOUND")

    # --- 5. tat dinh
    async def f_det(s):
        x = await call(s, "get_domain_overview", {"project": "vietbank-sme", "max_chars": 40000})
        y = await call(s, "get_domain_overview", {"project": "vietbank-sme", "max_chars": 40000})
        return json.dumps(x, ensure_ascii=False) == json.dumps(y, ensure_ascii=False), x
    same, x = await with_key(HKEY, f_det)
    check("tat dinh: 2 lan goi giong het", same)
    check("get_domain_overview tra du domain khi max_chars lon",
          len((x.get("data") or {}).get("domains") or []) == (x.get("data") or {}).get("total"),
          f"{len((x.get('data') or {}).get('domains') or [])}/{(x.get('data') or {}).get('total')}")

    # --- 6. cat theo max_chars
    t = await with_key(HKEY, lambda s: call(s, "get_domain_overview", {"project": "vietbank-sme", "max_chars": 1500}))
    check("max_chars nho -> truncated=true", (t.get("meta") or {}).get("truncated") is True)

    # --- 7. han muc (key 3 rpm)
    keyctl("remove", "--label", "verify-rpm2")
    keyctl("add", "--label", "verify-rpm2", "--projects", "*", "--rpm", "3", "--out", "/tmp/vk2.key")
    rk = Path("/tmp/vk2.key").read_text().strip()
    codes = []
    async def f_rl(s):
        import httpx
        async with httpx.AsyncClient() as cl:
            for _ in range(4):
                r = await cl.post(URL, headers={"x-api-key": rk, "content-type": "application/json",
                                   "accept": "application/json, text/event-stream"},
                                  json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
                codes.append(r.status_code)
    try:
        await with_key(rk, f_rl)
    except Exception as e:
        check("test han muc", False, f"loi client: {e}")
    check("han muc 3/phut -> luot 4 bi 429", codes[-1] == 429, codes)

    # --- 8. audit tang dung so luot
    before = sum(1 for _ in AUDIT.open()) if AUDIT.exists() else 0
    n = 0
    async def f_calls(s):
        nonlocal n
        for _ in range(5):
            await call(s, "server_info", {})
            n += 1
    await with_key(HKEY, f_calls)
    after = sum(1 for _ in AUDIT.open())
    check("audit ghi dung so luot goi", after - before == n, f"+{after-before} / {n} luot")

    # --- 9. khong lo key
    leaks = []
    async def f_leak(s):
        for name, args in [("server_info", {}), ("list_projects", {}),
                          ("get_knowledge_card", {"question": "chi lương", "project": "vietbank-sme"})]:
            res = await s.call_tool(name, args)
            txt = res.content[0].text if res.content else ""
            if HKEY in txt or vk in txt:
                leaks.append(name)
    await with_key(HKEY, f_leak)
    check("khong lo key tho trong cau tra loi", not leaks, leaks)

    for lbl in ("verify-scope", "verify-rpm2"):
        keyctl("remove", "--label", lbl)
    for f in ("/tmp/vk.key", "/tmp/vk2.key"):
        Path(f).unlink(missing_ok=True)

    ok = sum(1 for _, o, _ in results if o)
    print(f"\n=== TONG KET: {ok} PASS / {len(results) - ok} FAIL ===")
    return 0 if ok == len(results) else 1

raise SystemExit(asyncio.run(main()))
