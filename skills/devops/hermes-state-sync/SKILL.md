---
name: hermes-state-sync
description: "Sync Hermes agent state (memory/skills/cron) to git."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [git, sync, backup, portability, memory, skills, cron, restore, hermes]
---

# Hermes State Sync (Portable Agent)

Keep the user's Hermes personal state version-controlled in git so a new machine
can `git clone` + restore and the agent resumes with full context (memory,
skills, scripts, config, cron jobs). This is a standing setup, not a one-off:
keep the sync running automatically and the repo clean of secrets.

## What is portable vs what is secret / machine-specific

SYNC (non-secret, portable):
- `memories/` — `MEMORY.md` (agent notes) and `USER.md` (user profile)
- `skills/` — CUSTOM skills only (skip any name listed in
  `skills/.bundled_manifest`; bundled skills re-ship with the installer)
- `scripts/` — custom scripts referenced by cron jobs
- `cron/jobs.json` — scheduled-job definitions
- `SOUL.md` and `config.yaml` — config carries only `${ENV}` references, never values

NEVER SYNC (secrets or machine-specific):
- `.env` (API keys), `auth.json` (OAuth tokens), `state.db` + `-wal`/`-shm`
- `sessions/`, `logs/`, caches, gateway runtime files (`.sock`, `.pid`, `.lock`)
- `kanban.db`, `pairing/`, `platforms/`, `hooks/`, the `hermes-agent/` source tree

## Procedure

1. Repo layout: `sync.py` (mirrors the curated dirs into the repo), `sync.sh`
   (sync + commit + push), `restore.sh` (copies state back into `~/.hermes` on a
   new machine), plus a `.gitignore` safety net (`.env`, `auth.json`, `*.db*`,
   `*.sock`, `*.pid`, `*.lock`).
2. `sync.py` mirrors each dir by deleting stale entries in the repo copy first,
   then copying fresh — so deletions propagate, not just additions.
3. Filter two things out of every mirrored dir: transient files (`.lock`,
   `.tmp`, `.swp`, `~` — memory files always carry empty `.lock` siblings) and
   bundled skill names (via `.bundled_manifest`).
4. Push safely: `git pull --rebase origin main` before `git push`; never force.
5. Auto-sync: a `no_agent` cron job (hourly) runs a wrapper that calls `sync.sh`.
   Empty stdout = nothing pushed, so a quiet success sends nothing (watchdog
   pattern).

## Pitfalls

- A cron job's `script` is a FILENAME resolved under `~/.hermes/scripts/` at fire
  time — if the file is deleted the job fails on its next run with no error at
  edit time. Keep the script in place; if you rename it, update the job's
  `script` field in the same step.
- `shutil.copy2` raises `SameFileError` when src == dst — default the repo path
  to the script's own directory and read Hermes home from `$HERMES_HOME`, never
  derive one from the other's positional argv slot.
- Verify `config.yaml` before committing: grep for
  `api[_-]?key|secret|token|password` — matches should hit `${ENV}` references
  only, never literal values.
- Secrets are deliberately NOT synced. On a new machine, after `restore.sh` the
  user still runs `hermes setup` (or copies `.env`/`auth.json`) to restore
  credentials.
