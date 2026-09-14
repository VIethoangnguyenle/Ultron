---
name: agent-dispatch-recovery
description: "Use when a delegated job cannot run or never started."
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [delegation, cron, verification, quota, background-jobs]
    related_skills: [claude-code, ultron-scheduled-actions, system-resource-monitoring]
---

# Recovering a dispatched job that could not run

A delegated job (code work handed to a CLI agent, a long background command) can fail to run at all
while looking successful: the executor refuses because of a usage limit, or the shell wrapper exits
before the real process finishes. The job still has to get done — the workflow below is how.

## 1. Detect the block for what it is

- **Read the output, never just the exit code.** A CLI agent that hit its usage limit typically
  prints one line ("you have hit your session limit / quota exceeded, resets <time>") and exits **0**.
  Treating exit 0 as success means the deliverable silently never existed.
- A `nohup <cli> ... &` launcher returning immediately is **not** the job finishing. The "background
  process completed" style notification belongs to the wrapper. Confirm with the output file plus
  `pgrep -af <cli>` before believing anything ran.
- Distinguish "did not run" from "ran and failed": check the deliverable or its working tree before
  re-dispatching, so a partial run is not redone from scratch.

## 2. Do not swap the executor on your own

When the designated executor is unavailable (limit, login, service down), the default is **wait and
reschedule** — not "use the other agent so it finishes faster". Changing which agent does the work is
an owner decision: state the situation, the reset time, and the alternatives, then let the owner
choose. Meanwhile be explicit with them that the work has *not* started, so they never assume it is
running.

## 3. Reschedule against the reset time

If the work is not urgent, schedule a **one-shot** job a few minutes after the executor frees up
(usage limits state their reset time; do not guess it).

```
cronjob_manage action=create
  schedule:  "<ISO timestamp just after reset>"   # one-shot
  deliver:   "local"                              # the job sends its own report, avoid double posting
  failure_deliver: "<the chat the user reads>"    # failures must still surface
  enabled_toolsets: ["terminal"]                  # trim the fresh job's token floor
```

Prefer the project's own scheduler config over ad-hoc jobs where a purely script-driven task would
do; a job that needs reasoning belongs in a real scheduled LLM job.

The scheduled prompt must be **self-contained** (fresh session, no chat context):

1. path of a **task file** written before scheduling, holding the full spec;
2. the dispatch command, with the stop branch: *if the executor is still blocked, report that and
   STOP — do not do the work yourself*;
3. the **verification criteria with concrete expected numbers**;
4. the command that sends the report to the user.

Write long prompts to a file and pass `"$(cat <file>)"` — inlining multi-line prose into a one-line
shell command loses words to quoting (the command dies with a nonsense error) and cannot be audited
or re-run.

## 4. Verify independently, then report

- Measure the expected outcome **before** dispatching, put those numbers in the task file, and
  re-measure after. "The agent says it fixed it" is not evidence; a script that printed a plausible
  summary is not evidence either.
- Include one cheap device that would fail loudly on a wrong implementation (syntax/parse check, a
  dry-run mode, a count that must match).
- Bounded retry: at most one re-dispatch for the same defect; a second failure is reported to the
  owner with the measured numbers, not retried again.
- Report what changed, the before/after numbers, what is still open, and — when a reset was involved —
  that the job is now scheduled rather than running.

## Pitfalls

- Exit code 0 from a CLI agent means the process ended, not that the task succeeded. Read stdout.
- A wrapper/launcher exiting early fires success notifications for work still in flight; always probe
  the process and the output file.
- Re-dispatching without inspecting the working tree can duplicate or clobber a partial run.
- Scheduled jobs deliver their final message themselves: set the job to local delivery **or** have it
  send via script, never both, or the user gets the same report twice.
