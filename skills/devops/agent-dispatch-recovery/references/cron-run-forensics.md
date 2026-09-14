# Cron run forensics: which file/DB holds what

Use when the question is "did job X run at time Y, did it finish, where did it send, what did it say".
Everything lives under `~/.hermes/cron/`. Read with Python (`json`/`sqlite3`), never grep a binary.

## 1. `jobs.json` — current state of each job

Filter by `name`. Fields worth reading:

| Field | Meaning |
|---|---|
| `enabled`, `state`, `paused_reason` | still on, or paused and why |
| `schedule.expr` / `schedule_display` | schedule (e.g. `0 19 * * *` = daily 19:00) |
| `last_run_at`, `last_status` | most recent run + `ok`/error |
| `failure_streak`, `last_error`, `last_delivery_error` | failure / undelivered signals |
| `deliver`, `origin` | where output goes; `origin` = where the job was created |
| `next_run_at` | next fire — always quote it to the owner |
| `repeat.completed` | how many runs have happened |
| `last_dispatch.lateness_seconds`, `.kind` | seconds late vs the scheduled instant (`on_time`, ...) |
| `no_agent`, `script` | script-only job vs LLM job |

## 2. `executions.db` — per-attempt history

```python
import sqlite3
c = sqlite3.connect('/home/zane/.hermes/cron/executions.db').cursor()
c.execute("SELECT job_id,status,claimed_at,started_at,finished_at,error,"
          "delivery_outcome,scheduled_instant FROM executions "
          "WHERE job_id=? ORDER BY claimed_at DESC LIMIT 5", ('<job_id>',))
c.execute("SELECT job_id,error_sig,state,failure_type,first_seen_at,last_seen_at,closed_at,error "
          "FROM cron_incidents ORDER BY last_seen_at DESC LIMIT 10")
```

- `status`: `completed` / `running` / `failed`; `delivery_outcome`: `delivered` = actually sent.
- The table keeps only recent rows — a daily job showing one row does NOT mean it ran once; compare
  with `repeat.completed` before concluding.
- `cron_incidents` is the error ledger: `state='detected'` with `closed_at` null = still open.

## 3. `deliveries.db` — proof it left the system

Table `deliveries`: `execution_id`, `status` (`delivered`), `created_at`, `finished_at`, `error`.
Match `created_at` against the job's run time to prove the message was handed to the platform.

## 4. `output/<job_id>/` — verbatim report

One markdown file per run, `<date>_<time>.md`, containing `## Prompt` and `## Response`.
`## Response` is exactly what was sent to the owner — quote or re-post from this file instead of
reconstructing it from memory. Older run files stay on disk after later runs.

## Where job data is NOT

- `cron/usage_audit.jsonl` — per-run agent usage, no job names.
- the dispatcher log for `schedules.yaml` — that is the script dispatcher, not cron-job results.

## Answer shape

Real fire time + finish time + status + delivery target + one-line summary of the content + next run.
If the owner "never saw it", say plainly that the job delivered to a different channel and that you
have re-pointed it — do not leave them to go looking.
