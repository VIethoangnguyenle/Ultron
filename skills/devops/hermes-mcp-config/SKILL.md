---
name: hermes-mcp-config
description: "Use when connecting or fixing MCP servers in Hermes config."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [hermes, mcp, config, tools, secrets]
    related_skills: [hermes-agent, hermes-state-sync]
---

# Hermes MCP server configuration

Connect MCP servers to Hermes so their tools appear as `mcp_<server>_<tool>` in
every session. The authoritative config schema lives in the bundled `hermes-agent`
skill's `references/native-mcp.md` — load it when unsure of a key (`timeout`,
`connect_timeout`, `sampling`, OAuth). This skill carries the working command
workflow and this install's pitfalls; it does not restate the schema.

## Non-interactive config via `hermes config set` (preferred)

`hermes mcp add` is interactive (prompts for auth + tool selection), so it is
wrong for headless/scripted setup. Use `hermes config set` with dot-paths; a
JSON/YAML literal value is auto-coerced to a real dict/list.

```bash
hermes config set 'mcp_servers.<name>.url'     'http://127.0.0.1:8443/mcp'
hermes config set 'mcp_servers.<name>.headers' '{"x-api-key": "${MCP_<NAME>_API_KEY}"}'
hermes config set 'mcp_servers.<name>.command' 'uvx'
hermes config set 'mcp_servers.<name>.args'    '["--python=3.12", "mcp-atlassian"]'
hermes config set 'mcp_servers.<name>.env'     '{"CONFLUENCE_URL": "...", "CONFLUENCE_USERNAME": "..."}'
hermes config set 'mcp_servers.<name>.tools.exclude' '["tool_a", "tool_b"]'
hermes config unset mcp_servers.<name>   # remove a server
```

Claude-Desktop → Hermes mapping:
- `headers: {"x-api-key": "..."}` → `headers` (any header name works; the VALUE
goes in `.env` and is referenced as `${VAR}`).
- `command` + `args` + `env` → same keys (stdio transport).
- `disabledTools: [...]` → `tools.exclude: [...]` (blacklist). `tools.include` is a
whitelist; include wins over exclude. Leave both unset to register all tools.

## Secrets go in `.env`, never in config.yaml

config.yaml is committed to git (Ultron repo sync); `.env` is gitignored. Any
literal secret MUST live in `.env` and appear in config.yaml only as `${VAR}`
(see `hermes-state-sync` for the full sync rules).

```python
# run with the hermes venv python; imports from hermes_cli.config
save_env_value("MCP_<NAME>_API_KEY", "actual-secret")
```

A `.env` write via `save_env_value` can hit the terminal security gate and require
user approval — that is expected for `.env`, not a failure. `hermes config set`
writes to config.yaml without a gate (config carries no secret values).

## Verify before declaring success

```bash
hermes mcp list        # transport + tool count + enabled; "-N excluded" = tools.exclude applied
hermes mcp test <name> # actually connects + lists tools; confirms auth/headers resolve
```

`hermes config get mcp_servers` and `mcp list`/`test` REDACT secret-looking values
(`${MCP_...KEY}`) in display. To confirm the on-disk placeholder is intact, grep the
file (`grep MCP_DB_ACCESS_API_KEY ~/.hermes/config.yaml`) — never trust the display.

## Pitfalls

Đã chuyển sang agentmemory lessons (context=`hermes-mcp-config`). Khi cần nhớ lại: gọi `memory_lesson_recall` query `hermes-mcp-config`.
