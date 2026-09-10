---
name: agentmemory
description: "Use when managing the agentmemory memory server."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [memory, mcp, agentmemory, systemd]
    related_skills: [hermes-mcp-config, hermes-state-sync]
---

# agentmemory — persistent memory server for Hermes

agentmemory (npm `@agentmemory/agentmemory`, Apache-2.0, repo rohitg00/agentmemory)
is a local memory server that gives Hermes cross-session memory: 54 MCP tools
for save/recall/search/lessons/slots/audit/export. It runs on iii-engine v0.11.2.

## Architecture (two npm packages — do not confuse them)

- `@agentmemory/agentmemory` = the MEMORY SERVER. REST + MCP HTTP on 3111,
  streams 3112, viewer 3113, iii worker WebSocket 49134. Global binary installed
  at `/home/zane/.local/bin/agentmemory` (v0.9.29).
- `@agentmemory/mcp` = the MCP stdio SHIM Hermes launches (via mcp_servers config)
  to talk to the running server. It is NOT the server itself.

Server state (SQLite `state_store.db`, `iii-config.yaml`, `stream_store`) lives in
`~/.local/share/agentmemory` (Linux XDG data dir). Config + pinned iii binary under
`~/.agentmemory/` (`bin/`, `.env`, `backups/`). Both are LOCAL — do NOT git-sync
(binary + SQLite may hold sensitive data).

## How it runs (systemd user service)

Managed as systemd user service `agentmemory` (auto-start, linger already enabled):

```bash
systemctl --user status agentmemory   # check
systemctl --user restart agentmemory  # restart
journalctl --user -u agentmemory -n 50   # logs
```

Service file: `~/.config/systemd/user/agentmemory.service` (ExecStart = global
`agentmemory` binary, `CI=1`, `Restart=always`). CLI fallback if systemd is down:
`CI=1 npx -y @agentmemory/agentmemory@latest` (foreground) — but prefer systemd.

Health / verify: `curl -fsS localhost:3111/agentmemory/health` → `"status":"healthy"`.
Viewer: http://localhost:3113 .

## Hermes MCP integration

In `~/.hermes/config.yaml` (set via `hermes config set`):

```yaml
mcp_servers:
  agentmemory:
    command: npx
    args: ["-y", "@agentmemory/mcp"]
```

`hermes mcp test agentmemory` → should report 54 tools. MCP tools load at agent
STARTUP only — after adding/restarting, open a NEW session (or restart the gateway)
for the `memory_*` tools to appear. `hermes mcp test` proves the connection but does
NOT hot-load tools into the current session.

## Key tools (54 total; the useful core)

- memory_save / memory_recall / memory_smart_search — save + hybrid recall (BM25 in
  keyless mode; smart_search also fuses graph matches)
- memory_sessions / memory_timeline / memory_patterns — episodic history
- memory_lesson_save / memory_lesson_recall / memory_lesson_delete — lessons (≈ skills)
- memory_slot_* (list/get/create/append/replace/delete) — pinned/project/global slots
  (≈ memory + user-profile notes)
- memory_reflect / memory_consolidate — 4-tier consolidation + graph reflection
- memory_audit / memory_export / memory_snapshot_create — audit trail + git-versioned
  snapshot (snapshot aligns with the git-sync philosophy)
- memory_graph_query / memory_relations / memory_profile — knowledge graph + profile
- memory_diagnose / memory_heal — subsystem health + auto-fix

## Modes & pitfalls

- Default = KEYLESS: no API key, no cloud, vectors DISABLED. `memory_recall`/search
  uses BM25 keyword; semantic queries can return zero. This is the safe fintech mode.
- On-device semantic search: add `EMBEDDING_PROVIDER=local` to `~/.agentmemory/.env`,
  restart, first request downloads `Xenova/all-MiniLM-L6-v2`. The global npm install
  skipped native postinstall scripts (onnxruntime-node, sharp, protobufjs) — if
  local embeddings/vision are needed, reinstall with
  `npm install -g --allow-scripts=onnxruntime-node,sharp,protobufjs @agentmemory/agentmemory`.
- REST is open on localhost by default; set `AGENTMEMORY_SECRET` to require
  `Authorization: Bearer <secret>` on protected endpoints.
- Only 7 tools visible in the agent = MCP shim fell back to local because it could
  not reach the server → ensure the server is up and `AGENTMEMORY_URL` (default
  localhost:3111) is correct.
- `--data-dir <abs>` / `AGENTMEMORY_DATA_DIR` overrides storage; reuse the same value
  on every restart or you get a fresh store.

## Compliance note (fintech)

The DEEP integration is NOT enabled by default and must be a deliberate decision by
Hoàng: (1) `memory.provider: agentmemory` in config switches Hermes's native memory
backend; (2) copying `integrations/hermes` → `~/.hermes/plugins/agentmemory` installs
a 6-hook plugin that auto-captures EVERY turn + injects context pre-LLM. Both create
a second local copy of potentially sensitive conversation data — enable only after
explicit sign-off. Current state: MCP tools only (manual, no auto-capture).
