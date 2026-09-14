---
name: system-resource-monitoring
description: "Monitor machine resources (CPU/RAM/processes) and agent token spend."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [monitoring, psutil, cpu, memory, processes, cron, health-check, devops]
---

# System Resource Monitoring

Build scheduled checks that snapshot a machine's CPU/RAM/process state and flag
the processes worth a human's attention. The deliverable is a self-contained
script (re-runnable, no LLM needed to collect) plus a scheduler job that runs it
on a cadence.

## Procedure

1. Collect the snapshot in a standalone Python script using `psutil`. Put it
   under `~/.hermes/scripts/` so Hermes cron can reference it by name.
   `scripts/resource_snapshot.py` in this skill is a known-good starting point —
   copy and tune thresholds rather than rewriting from scratch.
2. Report three tiers: a system summary (load, cores, mem/swap, uptime, process
   and zombie counts), top-N by CPU and by RAM, and a heuristic-flag section.
3. Flag heuristically, do NOT judge. The script emits HIGH_CPU / HIGH_MEM /
   LONG_RUN_HEAVY flags from thresholds only. Deciding that a process is
   *unnecessary* (vs. legitimately busy) is a reasoning step — leave it to the
   agent. In a `no_agent` cron job you get flags, not a conclusion; if you want
   a verdict, keep the agent in the loop.
4. Wire it with Hermes cron: `no_agent=true` + `script=<name>.py` + `deliver`
   target + `schedule`. See the bundled `hermes-agent` skill's
   `references/background-systems.md` for the full cron/gateway knobs.

## Agent token spend audit

For "which thread/session/group burns the most tokens", answer from measured
numbers, never from the scheduled budget report alone:

1. All-time per session and per group → `sessions` table in
   `~/.hermes/state.db` (`input_tokens` is a running total per session;
   `chat_type='dm'` separates DMs, `chat_id` + `thread_id` group threads).
2. Per-day attribution → parse `~/.hermes/logs/agent.log*`: the
   `agent.conversation_loop: API call #N: ... in=<n> out=<n>` lines carry the
   real per-call input size plus a timestamp, so they place spend on the day it
   happened even for a session opened days earlier.
3. Rank by both axes the user asked about (per session AND per thread/group)
   plus today's numbers, then close with the lever rather than the ranking: a
   long-lived session re-sends its whole context each turn — ~90–165k tokens/turn
   once bloated vs ~25k for a fresh one — so the action item is "open a new
   session for that chat".
4. For "what mechanisms save tokens?" answer with the two-term model, not a
   feature list: spend ≈ (API calls × fixed per-call floor) + accumulated
   history. Measure the floor with `hermes prompt-size` (system prompt + tool
   schemas ≈ 25–30k per call), audit which knobs are actually ON (compression
   threshold, tool-result pruning, idle compaction, per-platform toolsets,
   `no_agent` cron jobs), then list what is still OFF and what each lever is
   worth. Never sell prompt caching as a saver before checking
   `cache_read_tokens` — here it reads ~0, so every turn pays full price.

Exact queries, the log parser, the lever audit and the report shape:
`references/token-accounting.md`.

## Context-compression audit ("nén ngữ cảnh có chạy không, chạy thế nào?")

When the question is about compaction itself — how often a session stops to
summarize, how much comes back, which layer is really running:

1. Count the passes from the log, never from config: the
   `context compression started/done` lines carry trigger tokens, tokens after,
   messages dropped and (from the line timestamps) the wall time of each pass.
   Use `~/.hermes/scripts/compact_stats.py` (`--hours | --since | --json |
   --send`) instead of hand-rolling regexes each time, and re-run it yourself
   plus spot-check two or three events against the raw lines before quoting its
   numbers.
2. Zero lines for a layer means "not proven to have run", NOT "cannot run".
   Read the gate before concluding: grep the symbol's call sites
   (`grep -rn "<symbol>" --include=*.py agent/`), then check for a knob whose
   value doubles as an accumulation / re-arm runway (it can land at most once
   per cycle), a sibling flag that force-disables the layer, a per-session
   counter reset by another layer, and whether the layer logs at all. For a
   silent layer the proof is a probe or a code read, never a grep for a line
   that does not exist.
3. Before judging any threshold, resolve TWO numbers: the model's declared
   window (ask the provider — `curl -s <gateway>/v1/models` → `max_input_tokens`)
   and whether `compression.threshold_tokens` (absolute) is set, because it caps
   the `threshold` ratio. An absolute 100k on a 1M-window model fires at 10% of
   the window — that arithmetic, not the layer wiring, is the usual cause of a
   compaction treadmill.
4. Price the pass in latency, not only tokens: one compaction is one auxiliary
   LLM call on the main provider unless the summarizer model is overridden
   (measured ~55 s of blocked turn time per pass). Switch the summarizer to a
   fast sibling model on the same gateway BEFORE proposing anything that adds a
   pass per turn.
5. Check `sessions.cache_read_tokens / input_tokens` before arguing about
   prompt-cache breaks — with cache hits near zero the breaks are cheap.

Standing rules for this class of work: a threshold change is a MONEY decision —
measure today's spend, then present threshold → est. tokens/turn → multiple of
current spend → fewer passes → reading accuracy as one table and let Hoàng pick;
never raise it quietly. Land all config-only, reversible levers in ONE batch with
a single gateway restart (`scripts/gw_restart.txt`), and keep code levers
(per-tool caps, file re-injection) behind an explicit go-ahead.

Log regexes, the pairing rule, the Claude↔Hermes layer mapping, the ranked lever
list (config vs code) and the threshold/spend table live in
`references/context-compression-audit.md`.

## Pitfalls

- `psutil.cpu_times()` (no args) returns a `scputimes` namedtuple, NOT a
  summable number. `sum(psutil.cpu_times())` raises `AttributeError: 'float'
  object has no attribute` — read `.user/.system/.idle/.iowait/.irq/.softirq/
  .steal` and add them yourself.
- A single per-process CPU read is meaningless. Measure real CPU% by sampling
  `Process.cpu_times()` twice separated by `time.sleep(~1.5)`, then
  `(proc_delta / total_delta) * cpu_count`. `total_delta` must be the busy-time
  delta across the SAME window (sum of all CPU time fields), not wall clock.
- Filter your own monitor process out of the report (`os.getpid()`) — sampling
  costs CPU, so the script itself shows up in the top-CPU list and pollutes it.
- Capture `info` dicts in the first sample and re-read `Process` objects in the
  second, wrapping every read in `except (NoSuchProcess, AccessDenied,
  ZombieProcess)` — processes churn between samples.
- Cron jobs do NOT fire unless the Hermes gateway is running. After creating a
  job, check `hermes gateway status`; if off, `hermes gateway install` enables
  a user service + systemd linger, then `hermes gateway start`.
- The cron `script` field is a filename resolved under `~/.hermes/scripts/` at
  fire time — deleting or renaming the script silently breaks the job on its
  next run. Keep the script file in place; if you rewrite it under a new name,
  update the job's `script` field in the same step.
- The scheduled token report under-counts the day: it filters sessions by
  `started_at` day, so a marathon session opened days earlier disappears from
  both the daily total and the top-N list — exactly the most expensive case
  (measured: report 62.4M vs 116M actually spent on the same day). Cross-check
  with the log parse before quoting any daily figure.
- `messages` rows are NOT API calls: one call can leave several assistant/tool
  rows (and compaction replays), so row counts overstate calls by ~4x. Count
  calls from `api_call_count` or the `API call #N` log lines instead.
- Report token findings in business terms (token totals, sessions, "open a new
  session") with the table wrapped in a code block: group chats contain
  colleagues, so no file paths, script names or DB identifiers in the message.
  Answer in the thread that asked and @mention the person who asked so they get
  notified.
- Prove a mechanism ran from its own log line, not from its config value — but
  first establish that the layer logs its passes. An absent line is proof of
  idleness only for a logging layer; for a silent one read the gate (call sites,
  sibling flag, re-arm runway) or run a probe. Declaring a knob "dead code" from
  a grep alone is how a retunable value gets misdiagnosed as needing a code fix.
- Compaction blocks inside the turn, so proposal order matters: switch the
  summarizer to a fast sibling model first, then consider enabling a pass that
  runs every N turns. Adding the pass while the summarizer is the slow main
  model makes every turn pay its latency.
