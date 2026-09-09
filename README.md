# Ultron

Portable snapshot of my Hermes agent's personal state — memory, custom skills,
scripts, config, persona, and cron jobs — so switching machines is a
`git clone` + `restore.sh` away.

## What's synced (non-secret, portable)

| Path | What it is |
|---|---|
| `memories/` | `MEMORY.md` (my notes) + `USER.md` (who you are) |
| `skills/` | Custom skills only — bundled ones re-ship with the installer |
| `scripts/` | Custom scripts (e.g. `check_resources.py`) |
| `cron/jobs.json` | Scheduled job definitions |
| `SOUL.md` | Persona / behavior contract |
| `config.yaml` | Settings only — secrets are `${ENV}` references, never values |

## What's deliberately NOT synced

`.env`, `auth.json`, `state.db` (+ WAL/SHM), `sessions/`, `logs/`, caches,
gateway runtime files, `kanban.db`, `pairing/`, `platforms/`, `hooks/`, the
`hermes-agent/` source tree. These are either secrets or machine-specific.

## On a new machine

```bash
git clone git@github.com:VIethoangnguyenle/Ultron.git ~/Ultron
bash ~/Ultron/restore.sh        # copies state back into ~/.hermes
```

## Keeping it fresh

`sync.sh` runs automatically via a Hermes cron job (or run it by hand):

```bash
bash ~/Ultron/sync.sh
```
