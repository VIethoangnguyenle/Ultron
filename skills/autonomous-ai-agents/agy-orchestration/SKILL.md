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

1. **`secretstorage` must be importable by the Python that runs the agy wrapper + `hagy`.**
   The wrapper (`~/.local/bin/agy`) calls `python3` for keyring sync + quota rotation; `hagy` does too. In the Hermes terminal, `python3` resolves to the Hermes venv (`~/.hermes/hermes-agent/venv/bin/python3`), which does NOT ship `secretstorage`. Symptom: every `agy`/`hagy` call prints `ModuleNotFoundError: No module named 'secretstorage'`, and `hagy who`/`hagy list` report "No accounts" — quota rotation silently dead.
   Fix: `~/.hermes/bin/uv pip install --python ~/.hermes/hermes-agent/venv/bin/python3 secretstorage` (also pulls jeepney). Verify with `hagy who` → should show an account, not "No accounts".

2. **agy's working directory is NOT the terminal `workdir` — it defaults to `$HOME`.**
   Symptom: agy reports "Không tìm thấy .ua/knowledge-graph.json" even though it exists, then falls back to a slow full scan and times out. Fix: pass `--add-dir /home/zane/Desktop/work/vietbank/vietbank-sme` AND tell agy in the prompt to `cd` into the project root first.

3. **Default `--print-timeout` is 5m — far too short for understand-domain.**
   Domain analysis is a heavy multi-turn task (reads many files / a ~17MB graph). Use `--print-timeout 25m` (Go duration, accepts `25m`/`1800s`).

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
