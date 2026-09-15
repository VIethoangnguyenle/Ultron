import asyncio, json
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
KEY=(Path.home()/".hermes/state/ba_mcp/hoang.key").read_text().strip()
URL="http://127.0.0.1:9450/mcp"
OK=[]; BAD=[]
def chk(cond, name, ev=""):
    (OK if cond else BAD).append(name)
    print(("[PASS] " if cond else "[FAIL] ")+name+(f" — {ev}" if ev else ""))

async def call(s, tool, args):
    r = await s.call_tool(tool, args)
    txt = "".join(getattr(c,"text","") for c in r.content)
    try: return json.loads(txt)
    except Exception: return {"_isError": getattr(r,"isError",None), "_raw": txt[:160]}

async def main():
    async with streamablehttp_client(URL, headers={"x-api-key":KEY}) as (r,w,_):
        async with ClientSession(r,w) as s:
            await s.initialize()
            tl = await s.list_tools()
            names = [t.name for t in getattr(tl, "tools", [])]
            chk(len(names)==16 and "get_db_dictionary" in names, "16 tool, ten khong doi", f"{len(names)} tool")

            # 1) phan trang bang DUNG ten cong quang cao
            p1 = await call(s,"get_db_dictionary",{"project":"vietbank-sme","keyword":"AD_","limit":5})
            d1=p1.get("data") or {}; m1=p1.get("meta") or {}
            n1=[t["name"] for t in (d1.get("tables") or [])]
            adv = m1.get("next_offset", m1.get("next_cursor"))
            hint = json.dumps(p1.get("hints"), ensure_ascii=False)
            chk(adv is not None and d1.get("shown")==len(n1)==5, "trang 1: shown==len==limit", f"shown={d1.get('shown')} len={len(n1)} limit=5")
            chk(adv is not None, "co con tro cho trang sau", f"next={adv!r}")
            p2 = await call(s,"get_db_dictionary",{"project":"vietbank-sme","keyword":"AD_","limit":5,"offset":adv})
            d2=p2.get("data") or {}; n2=[t["name"] for t in (d2.get("tables") or [])]
            chk(set(n1).isdisjoint(set(n2)) and len(n2)>0, "trang 2 KHAC trang 1 (khong trung)", f"p2={n2[:3]}")
            p3 = await call(s,"get_db_dictionary",{"project":"vietbank-sme","keyword":"AD_","limit":5,"cursor":adv})
            d3=p3.get("data") or {}; n3=[t["name"] for t in (d3.get("tables") or [])]
            chk(p3.get("ok") is False or (n3 and set(n3).isdisjoint(set(n1))),
                "ten 'cursor' hoac chay dung, hoac bao loi ro (khong im lang tra trang 1)",
                f"ok={p3.get('ok')} err={(p3.get('error') or {}).get('code') if isinstance(p3.get('error'),dict) else p3.get('error')}")

            # 2) di het bang ten chuan
            seen=set(n1); cur=adv; rounds=1
            while cur is not None and rounds < 25:
                p = await call(s,"get_db_dictionary",{"project":"vietbank-sme","keyword":"AD_","limit":5,"offset":cur})
                d=p.get("data") or {}; m=p.get("meta") or {}
                ns=[t["name"] for t in (d.get("tables") or [])]
                if set(ns) & seen:
                    chk(False, "khong trung khi di het", f"trung o luot {rounds+1}: {sorted(set(ns)&seen)[:3]}"); break
                seen.update(ns); cur=m.get("next_offset"); rounds+=1
            total=(d.get("total") if isinstance(d,dict) else None)
            chk(len(seen)==total, "di het: hop == total, khong thieu", f"{len(seen)}/{total} bang qua {rounds} luot")

            # 3) tham so rac / sai ten phai BAO LOI, khong tra du lieu
            for nm, args in [("offset am",{"offset":-1}), ("offset chu",{"offset":"x"}),
                             ("offset vuot bien",{"offset":99999}), ("limit 0",{"limit":0}),
                             ("ten la zzz_nonsense",{"zzz_nonsense":99}), ("go nham limt",{"limt":10})]:
                base={"project":"vietbank-sme","keyword":"AD_","limit":5}; base.update(args)
                res=await call(s,"get_db_dictionary",base)
                err=res.get("error"); code=err.get("code") if isinstance(err,dict) else None
                chk(res.get("ok") is False and code is not None, f"tham so rac [{nm}] -> bao loi ro", f"ok={res.get('ok')} code={code}")
asyncio.run(main())
print(f"\n=== {len(OK)} PASS / {len(BAD)} FAIL ===")
if BAD: print("FAIL:", BAD)
