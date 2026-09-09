#!/usr/bin/env python3
"""Merge multiple understand-domain outputs into one domain-graph.json.
Usage: python merge_domain_graphs.py <output.json> <part1.json> [part2.json ...]
Deduplicates nodes by id and edges by (source,target,type)."""
import json, sys

def main():
    out = sys.argv[1]
    parts = sys.argv[2:]
    nodes, edges = [], []
    seen_n, seen_e = set(), set()
    meta = None
    for p in parts:
        d = json.load(open(p, encoding="utf-8"))
        if meta is None:
            meta = {k: v for k, v in d.items() if k not in ("nodes", "edges")}
        for n in d["nodes"]:
            if n["id"] not in seen_n:
                seen_n.add(n["id"]); nodes.append(n)
        for e in d["edges"]:
            k = (e["source"], e["target"], e.get("type"))
            if k not in seen_e:
                seen_e.add(k); edges.append(e)
    meta["nodes"] = nodes
    meta["edges"] = edges
    json.dump(meta, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    doms = sum(1 for n in nodes if n["type"] == "domain")
    fl = sum(1 for n in nodes if n["type"] == "flow")
    st = sum(1 for n in nodes if n["type"] == "step")
    print(f"merged -> {out}: {doms} domains, {fl} flows, {st} steps, {len(edges)} edges")

if __name__ == "__main__":
    main()
