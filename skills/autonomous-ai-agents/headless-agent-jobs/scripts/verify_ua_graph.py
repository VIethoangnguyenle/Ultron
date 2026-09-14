#!/usr/bin/env python3
"""Kiểm chứng graph Understand-Anything TRƯỚC khi báo 'xong'.

Dùng: python3 verify_ua_graph.py <.ua dir> [--samples 5]
In: số node/edge, analyzedFiles vs meta, layers/tour, phân bố type, tỉ lệ summary template, vài mẫu summary.
Exit 1 nếu thiếu graph, tỉ lệ template > 20%, hoặc tour < 5 điểm.

Vì sao cần: `ls .ua/knowledge-graph.json` không phải bằng chứng — agent headless có thể sinh graph đủ cấu
trúc nhưng mô tả là template rác và tour gần như rỗng.
"""
import json
import os
import random
import re
import sys

TEMPLATE = re.compile(
    r"cung cấp cấu trúc và phương thức cho"
    r"|chứa mã nguồn"
    r"|xử lý logic trong \S+\.java"
    r"|đảm nhiệm thực thi một xử lý cụ thể"
)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    d = sys.argv[1]
    samples = 5
    if "--samples" in sys.argv:
        samples = int(sys.argv[sys.argv.index("--samples") + 1])

    kg = os.path.join(d, "knowledge-graph.json")
    if not os.path.exists(kg):
        print(f"FAIL: không có {kg}")
        return 1
    with open(kg) as fh:
        j = json.load(fh)
    nodes = j.get("nodes", [])
    edges = j.get("edges", [])

    types = {}
    for n in nodes:
        types[n.get("type")] = types.get(n.get("type"), 0) + 1
    tpl = [n for n in nodes if TEMPLATE.search(str(n.get("summary", "")))]
    ratio = len(tpl) / max(len(nodes), 1)

    meta = {}
    mp = os.path.join(d, "meta.json")
    if os.path.exists(mp):
        with open(mp) as fh:
            meta = json.load(fh)

    tour = len(j.get("tour", []))
    print(f"file          : {kg} ({os.path.getsize(kg) / 1e6:.1f} MB)")
    print(f"nodes/edges   : {len(nodes)} / {len(edges)}")
    print(f"analyzedFiles : {meta.get('analyzedFiles', '?')}  commit={str(meta.get('gitCommitHash'))[:10]}")
    print(f"layers/tour   : {len(j.get('layers', []))} / {tour}")
    print(f"types         : {sorted(types.items(), key=lambda kv: -kv[1])[:9]}")
    print(f"summary rác   : {len(tpl)} ({ratio:.0%})")
    random.seed(0)
    if nodes:
        for n in random.sample(nodes, min(samples, len(nodes))):
            print(f"  - {n.get('type')} {n.get('name')} :: {str(n.get('summary'))[:120]}")

    if ratio > 0.2 or tour < 5:
        print("KET LUAN: CHUA DAT (nhieu summary template hoac tour qua it)")
        print("-> chay lai phase mo ta/tour theo tung module: templates/chunked_summary_loop.sh")
        return 1
    print("KET LUAN: DAT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
