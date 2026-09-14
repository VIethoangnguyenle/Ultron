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

Tra cứu metadata/link khi cần: npmjs.com chặn `curl` (403) → dùng `curl https://registry.npmjs.org/@agentmemory%2Fmcp`
(trả `homepage`, `license`, `dist-tags`), hoặc GitHub API `api.github.com/repos/rohitg00/agentmemory` cho license + stars.

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

## "Rà bài học lỗi thời" — bài học có HẠN DÙNG (Hoàng chốt 2026-09-12)

Bài học trong store không phải chân lý vĩnh viễn. Bài nêu **version / nhánh / đường dẫn / ngưỡng /
môi trường** là loại dễ lỗi thời nhất; bài cũ SAI thì phải xoá hoặc viết lại, KHÔNG để đè nhau.

- Script: `~/.hermes/scripts/lesson_review.py` — **0 token**, đọc thẳng `mem%3Alessons.bin`, phân 4 nhóm:
  bài rác/thử nghiệm · bài nghi trùng (Jaccard từ >4 ký tự ≥ 0.6) · **tiền đề ĐÃ ĐỔI** · bài dễ lỗi thời (≥14 ngày).
- **Tiền đề đã đổi = tự kiểm chứng với thế giới thật, không phán đoán**: bài nói cơ chế approval → so
  `approvals.mode` trong config; bài cảnh báo token trong `.mcp.json` → grep xem còn token sống không;
  bài chứa đường dẫn → kiểm file còn tồn tại không.
- Nhịp: action `lesson-review` trong `~/.hermes/schedules.yaml` (Chủ nhật 09:00). Có phát hiện → ghi
  1 file escalation → cron forward về DM Hoàng. **Script CHỈ BÁO, không tự xoá** — xoá là quyết định
  của Ultron/Hoàng (`memory_lesson_delete`, soft-delete).
- Report: `~/.hermes/reports/lesson_review_<YYYY-MM-DD>.md`.
- Pitfalls: (a) store là **dict lồng dict** — loader phải bắt cả nhánh value là dict, không chỉ list;
  (b) phải **lọc `deleted: true`** nếu không sẽ đếm cả bài đã xoá; (c) probe theo TỪ KHOÁ dễ bắt oan —
  chữ "approval" từng khớp tên service `approval` trong bài micrometer ⇒ regex phải đòi cụm ngữ cảnh
  (`command_allowlist`, `approvals.mode`, "cơ chế approval"), không chỉ 1 từ.

## Modes & pitfalls

- ACTIVE config (this install): KEYLESS (no LLM key, no cloud) + `EMBEDDING_PROVIDER=local`
  set in `~/.agentmemory/.env`. Local embeddings use `@huggingface/transformers` +
  onnxruntime-node (native binaries already bundled, linux/x64 works). Semantic search
  is ON, fully on-device — verify with `config/flags` → `embeddingProvider: embeddings`.
  First embedding request downloads the model (~90MB) once; startup after restart is
  slower while the model loads. NO LLM provider is configured, so CONSOLIDATION/
  AUTO_COMPRESS/graph remain OFF (they need an LLM key).
- If vectors were disabled again: `EMBEDDING_PROVIDER` unset in `.env` → BM25 keyword
  only, semantic queries return zero.
- REST is open on localhost by default; set `AGENTMEMORY_SECRET` to require
  `Authorization: Bearer <secret>` on protected endpoints.
- Only 7 tools visible in the agent = MCP shim fell back to local because it could
  not reach the server → ensure the server is up and `AGENTMEMORY_URL` (default
  localhost:3111) is correct.
- `--data-dir <abs>` / `AGENTMEMORY_DATA_DIR` overrides storage; reuse the same value
  on every restart or you get a fresh store.

## Compliance note (fintech) — CURRENT STATE (Hoàng approved 2026-09-10)

Auto-capture is ON (deliberate, Hoàng-approved, local-only — no LLM, no cloud).
- `memory.provider: agentmemory` is set in config.yaml (additive — built-in MEMORY.md/
  USER.md still run unchanged).
- Plugin lives at `~/.hermes/plugins/agentmemory/` (`__init__.py` + `plugin.yaml`, from
  repo `integrations/hermes/`). It registers `AgentMemoryProvider` implementing the
  MemoryProvider ABC; `sync_turn` POSTs each turn (user[:500] + assistant[:2000]) to
  `/agentmemory/observe`, `on_memory_write` mirrors built-in writes, `on_session_end`
  closes the session. Every turn is now captured to the LOCAL store as an observation
  (episodic), NOT auto-distilled to fact (distill needs LLM, which is off).
- Verify: `hermes memory status` → agentmemory "available" + "← active"; sessions show
  up via `GET /agentmemory/sessions`. Restart gateway after enabling (`systemctl --user
  restart hermes-gateway`).
- TO REVERT: `hermes config set memory.provider ''` + `rm -rf ~/.hermes/plugins/agentmemory`
  + restart gateway.
