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
