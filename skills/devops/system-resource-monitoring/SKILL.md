---
name: system-resource-monitoring
description: "Monitor machine resources (CPU/RAM/processes)."
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
