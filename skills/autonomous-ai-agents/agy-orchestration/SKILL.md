---
name: agy-orchestration
description: "Use when orchestrating agy for Understand-Anything runs."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [agy, antigravity, gemini, understand-anything, domain-graph]
    related_skills: [claude-code]
---

# Orchestrating agy (Antigravity CLI)

Run `agy` for high-token source-code reasoning (domain-graph enrichment via Understand-Anything). Hoàng's rule: coding→claude, reasoning/UA→agy.

## Three gotchas that WILL break a run

Đã chuyển sang agentmemory lessons (context=`agy-orchestration`). Khi cần nhớ lại: gọi `memory_lesson_recall` query `agy-orchestration`.

## CRITICAL: /understand-domain OVERWRITES domain-graph.json (does not merge)

Each `/understand-domain` run **replaces** `domain-graph.json` with ONLY the domains it analysed. Run several domains naively and the last run silently deletes the earlier domains.

Safe workflow — one domain at a time:
1. `cp .ua/domain-graph.json .ua/domain-graph.json.master` (keep the accumulated master).
2. Run agy for the NEXT domain (it writes a fresh `domain-graph.json`).
3. Merge: `python scripts/merge_domain_graphs.py .ua/domain-graph.json .ua/domain-graph.json.master .ua/domain-graph.json` — wait, order matters: pass the JUST-RUN output + the master, write back to a fresh file, then `cp` over `.ua/domain-graph.json`.
   Correct sequence: `python scripts/merge_domain_graphs.py .ua/_tmp.json .ua/domain-graph.json.master .ua/domain-graph.json && mv .ua/_tmp.json .ua/domain-graph.json && cp .ua/domain-graph.json .ua/domain-graph.json.master`.
4. Verify count went UP (python: count `type=='domain'` nodes). If it dropped, the merge order was wrong or the run overwrote without producing the expected domains — inspect before continuing.

Merge script lives in this skill: `scripts/merge_domain_graphs.py` (dedupe by node id + edge (source,target,type)).

## Working invocation

```bash
cd /home/zane/Desktop/work/vietbank/vietbank-sme && \
agy --add-dir /home/zane/Desktop/work/vietbank/vietbank-sme \
    --print-timeout 25m \
    --print "cd /home/zane/Desktop/work/vietbank/vietbank-sme && /understand-domain <tên nghiệp vụ> — dùng knowledge graph có sẵn trong .ua/ (qua MCP understand-anything), không rescan --full."
```

- Run in background (`background=true, notify=true`) — each domain takes several minutes.
- One domain per invocation (not all at once); the domain-analyzer writes to `.ua/intermediate/domain-analysis.json` then merges into `.ua/domain-graph.json`.
- Back up `domain-graph.json` before each run: `cp domain-graph.json domain-graph.json.bak-$(date +%Y%m%d-%H%M%S)`.

## Quota management

- Pool: 2 accounts — `lapnv@vnpay.vn` (#1, default) and `trungvt3@vnpay.vn` (#2). Config in `~/.antigravity_sw/hagy_config.json`, accounts in `~/.antigravity_sw/accounts.json`.
- Check current: `hagy who`. Rotate manually: `hagy next`. List: `hagy list`.
- The wrapper auto-rotates on quota-hit only in non-print interactive mode reliably; in print mode it rotates only if output matches quota patterns. Watch `~/.antigravity_sw/logs/rotation.log`.
- Kill stale hung agy processes (`ps -eo pid,etime,args | grep agy | grep -v grep`) before a long run — they hold quota.
- Default model = "Claude Opus 4.6 (Thinking)" (from hagy_config). Consider Gemini flash for cheap high-token runs; verify model name via `agy models` (short names like `gemini-3.8-flash-high`) vs wrapper display names ("Gemini 3.8 Flash (High)") — they differ.
