# Bảng nguồn theo từng mục audit

Mọi lệnh dưới đây đã chạy thật trên máy này (Linux, profile `default`, `HERMES_HOME=~/.hermes`).
Mẹo chung: đổ ra file trong `~/audit-<ngày>/` rồi đọc lại, vì output dài hay bị elide khi đi qua pipe.

## 1. Danh tính / profile / model

| Cần biết | Nguồn quyết định | Lệnh |
|---|---|---|
| profile đang chạy, model, provider, terminal backend, số skill/cron | `hermes dump` (⚠ thiếu platform/MCP) | `hermes dump` |
| phiên bản agent + upstream hash | `hermes --version` | |
| biến môi trường phiên | `printenv \| grep '^HERMES'` | |
| profile khác trên máy | `ls -la $HERMES_HOME/profiles` (không tồn tại = chỉ có default) | `hermes gateway list` cũng liệt kê profile |
| model/provider/base_url/api_mode | `config.yaml` mục `model:` + `custom_providers:` (kèm `context_length`) | đọc bằng python `enumerate` để có số dòng |
| fallback | không có key `fallback` ⇒ `hermes fallback list` → "No fallback providers configured." | |
| API key của provider | `config.yaml` (dạng `${ENV_VAR}`) + `.env` | chỉ ghi TÊN biến, không in giá trị |

## 2. Toolset

| Cần biết | Nguồn | Lệnh |
|---|---|---|
| bật/tắt theo platform | `hermes tools list --platform <cli\|google_chat\|…>` | mặc định là `cli` nếu không truyền |
| toolset nào do plugin đăng ký | `plugins/platforms/<x>/tools.py` (`ctx.register_tool(name, toolset=…)`) | |
| vì sao "disabled" | `hermes-agent/toolsets.py` — bundle mặc định; các toolset ghi *"opt-in, not in default toolset"* | KHÔNG có key config nào liệt kê tool tắt |
| tool MCP đã đăng ký & số server | `logs/agent.log` dòng `MCP server '<x>' (…): registered N tool(s)` và `MCP: registered N tool(s) from M server(s)` | `grep -iE 'mcp' logs/agent.log \| tail` |
| tool bị loại của một server | `config.yaml` mục `mcp_servers.<tên>` (vd danh sách `excluded`) | |
| toolset của route webhook | `webhook_subscriptions.json` → key `toolsets` từng route | |

## 3. System prompt

Bản prompt thật **không có file**: nó nằm trong bảng `system_prompts` của `$HERMES_HOME/state.db`
(`hash` PRIMARY KEY, `prompt`; KHÔNG có cột thời gian ⇒ bản mới nhất = `order by rowid desc limit 1`).

```python
import sqlite3
con = sqlite3.connect("file:/home/zane/.hermes/state.db?mode=ro", uri=True)
h, p = con.execute("select hash, prompt from system_prompts order by rowid desc limit 1").fetchone()
print(len(p))
```

Dựng bản đồ khối: dò marker rồi in `offset | độ dài | tên khối`. Bộ marker dùng được:

| Marker | Khối |
|---|---|
| `# SOUL.md` (đầu prompt) | persona, nguồn `$HERMES_HOME/SOUL.md` (đối chiếu số ký tự với file để biết có bị cắt không) |
| `You run on Hermes Agent` | câu neo identity |
| `Finishing the job`, `Parallel tool calls`, `Skill Safety Rule`, `Mid-turn user steering`, `Tool-use enforcement`, `Execution discipline` | 6 khối guidance sinh từ `agent/prompt_builder.py` |
| `You are on <Platform>` / `MEDIA:/absolute/path` | ghi chú platform (giới hạn markdown, cỡ tin, cách gửi file) |
| `## Skills` | chỉ mục skill (tên + mô tả); snapshot ở `$HERMES_HOME/.skills_prompt_snapshot.json` |
| `MEMORY (your personal notes)` | banner + `memories/MEMORY.md` |
| `USER PROFILE (who the user is)` | banner + `memories/USER.md`, kèm khối `<memory-context>` của agentmemory |
| `Hermes runtime environment` | khối runtime (host, home, cwd) |

Code để tính: `p.find(marker)` cho từng marker, sắp theo offset, độ dài = hiệu hai offset liên tiếp.
Skill **không** auto-load: `hermes config get skills` → `auto_load: []` (chỉ mục skill mới vào prompt).

## 4. Bộ nhớ

| Cần biết | Nguồn |
|---|---|
| provider + cờ inject | `hermes config get memory`; `hermes memory status` (liệt kê provider plugin) |
| built-in | `$HERMES_HOME/memories/MEMORY.md`, `memories/USER.md` — đếm ký tự + đếm entry bằng cách tách dấu `§` |
| số bản ghi provider ngoài | MCP `memory_diagnose` (memories/lessons/warn/fail) và `memory_profile(project=…)` (session/observation) |
| server + kho dữ liệu | env `AGENTMEMORY_URL`; `ps` → `iii --config ~/.local/share/agentmemory/iii-config.yaml`; `ss -ltnp` → cổng HTTP; kho kv file-based ở `~/.local/share/agentmemory/state_store.db/` (THƯ MỤC shard `mem:*.bin`) |
| cơ chế ghi | tự bắt observation trong lúc làm việc + tool `memory`/`memory_save`/`memory_lesson_save`; `nudge_interval` trong config |

## 5. Skills

| Cần biết | Nguồn |
|---|---|
| tổng số | `find $HERMES_HOME/skills -name SKILL.md \| wc -l` (khớp dòng `skills:` của `hermes dump`) |
| bundled hay tạo tại máy | `$HERMES_HOME/skills/.bundled_manifest` (dòng `tên:hash`) — chỉ dùng để phân loại, hash không phải md5 của SKILL.md |
| ai tạo + lúc nào | `$HERMES_HOME/skills/.curator_ledger.jsonl` — đếm `event` (`create`/`patch`/`write_file`) và `actor` (`agent`/`curator`), lấy `ts` của event `create` |
| mức sử dụng | `$HERMES_HOME/skills/.usage.json` |

## 6. Đa agent / Kanban

| Cần biết | Nguồn |
|---|---|
| board + số task | `hermes kanban boards list`, `hermes kanban stats`, `hermes kanban diag`; `sqlite3 kanban.db "select count(*) from tasks"` |
| profile trên board | `hermes kanban assignees` |
| cờ dispatch | `hermes config get kanban` (`dispatch_in_gateway`, `auto_decompose`, `max_in_progress`, `orchestrator_profile`, `default_assignee`, `dispatch_interval_seconds`, …) |
| gateway sống? | `systemctl --user list-units --type=service --all \| grep hermes`; `hermes gateway list`; `$HERMES_HOME/gateway_state.json` (`gateway_state`, `active_agents`, `platforms.<x>.state`) |
| dispatcher sống? | `logs/gateway.log`: dòng `kanban dispatcher: holding singleton dispatcher lock`, `kanban.max_in_progress unset; using memory-derived default max_in_progress=N`, `embedded in gateway (interval=…)` |
| dấu hiệu bất thường | `kanban dispatcher: reaped N zombie worker(s)` lặp đều đặn dù board rỗng |

## 7. Kết nối

| Cần biết | Nguồn |
|---|---|
| platform đã cấu hình | `config.yaml` mục `platforms:` (kèm `enabled`, port, host); `.env` các key `GOOGLE_CHAT_*` (chỉ in tên) |
| platform đang connected | `gateway_state.json` → `platforms.<x>.state` + `updated_at` (nguồn thật, KHÔNG dùng `hermes dump`) |
| webhook route | `hermes webhook list` (URL, profile, deliver) + `webhook_subscriptions.json` (toolset từng route) |
| cron | `hermes cron list --all` (job disabled/completed còn sót), `hermes cron status`, `hermes cron doctor` (job lỗi + stderr) |
| lịch nội bộ | `venv/bin/python $HERMES_HOME/scripts/daily_dispatch.py --list` (id · giờ · bật · điều kiện) |
| hooks / plugin | `hermes hooks list`; `hermes plugins list --plain --no-bundled` |
| cổng đang mở | `ss -ltnp` (đối chiếu port MCP/webhook; chú ý service bind `0.0.0.0` là rủi ro) |

## 8. Sandbox / quyền

| Cần biết | Nguồn |
|---|---|
| backend terminal + hạn mức | `config.yaml` mục `terminal:` (backend, cwd, timeout, container_*, lifetime) + `.env` (`TERMINAL_*`) |
| cổng duyệt | `config.yaml` `approvals.mode` + code `tools/approval.py` (mode `off` ⇒ auto-approve) |
| quyền thực tế của tiến trình | `id` (nhóm `docker`/`lxd` ⇒ tương đương root), `sudo -n true` (có NOPASSWD hay không), `docker ps` |
| allowlist lệnh | `config.yaml` `command_allowlist` |

## Ghi chú chung

- `state.db` chứa `sessions` / `messages` / `system_prompts` và phình theo thời gian ⇒ luôn mở read-only URI.
- Số liệu dùng lại về sau phải kèm mốc thời gian; kiểm lại bằng đúng lệnh trong bảng này thay vì chép số cũ.
