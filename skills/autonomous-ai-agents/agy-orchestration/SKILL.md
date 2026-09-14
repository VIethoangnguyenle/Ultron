---
name: agy-orchestration
description: "Use when orchestrating agy for Understand-Anything runs."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [agy, antigravity, gemini, understand-anything, domain-graph]
    related_skills: [claude-code]
---

# Orchestrating agy (Antigravity CLI)

Run `agy` for high-token source-code reasoning (domain-graph enrichment via Understand-Anything). Hoàng's rule: coding→claude, reasoning/UA→agy. **Tên gọi của Hoàng (2026-09-12): agy = *Matcha*** (claude = *Jarvis*) — nghe "Matcha đọc source/soi graph" nghĩa là chạy agy; luật ủy quyền không đổi: chỉ Hoàng nói trực tiếp mới kích hoạt.

## Three gotchas that WILL break a run

Đã chuyển sang agentmemory lessons (context=`agy-orchestration`). Khi cần nhớ lại: gọi `memory_lesson_recall` query `agy-orchestration`.

## CRITICAL: /understand-domain OVERWRITES domain-graph.json (does not merge)

Each `/understand-domain` run **replaces** `domain-graph.json` with ONLY the domains it analysed. Run several domains naively and the last run silently deletes the earlier domains.

Safe workflow — one domain at a time:
1. `cp .ua/domain-graph.json .ua/domain-graph.json.master` (keep the accumulated master).
2. Run agy for the NEXT domain (it writes a fresh `domain-graph.json`).
3. Merge: `python scripts/merge_domain_graphs.py .ua/domain-graph.json .ua/domain-graph.json.master .ua/domain-graph.json` — wait, order matters: pass the JUST-RUN output + the master, write back to a fresh file, then `cp` over `.ua/domain-graph.json`.
   Correct sequence: `python scripts/merge_domain_graphs.py .ua/_tmp.json .ua/domain-graph.json.master .ua/domain-graph.json && mv .ua/_tmp.json .ua/domain-graph.json && cp .ua/domain-graph.json .ua/domain-graph.json.master`.
4. Verify count went UP (python: count `type=='domain'` nodes). If it dropped, the merge order was wrong or the run overwrote without producing the expected domains — inspect before continuing.

Merge script lives in this skill: `scripts/merge_domain_graphs.py` (dedupe by node id + edge (source,target,type)).

## Working invocation

```bash
cd /home/zane/Desktop/work/vietbank/vietbank-sme && \
agy --add-dir /home/zane/Desktop/work/vietbank/vietbank-sme \
    --print-timeout 25m \
    --print "cd /home/zane/Desktop/work/vietbank/vietbank-sme && /understand-domain <tên nghiệp vụ> — dùng knowledge graph có sẵn trong .ua/ (qua MCP understand-anything), không rescan --full."
```

- Run in background (`background=true, notify=true`) — each domain takes several minutes.

### /understand (build the knowledge graph) → chạy bằng CLAUDE, không phải agy

`agy --print "/understand <path>"` **KHÔNG mở slash command**: print mode của agy không expand skill,
nó chỉ trả lời như chat bình thường rồi thoát (exit 0 trong <60s, không sinh `.ua/`). Dấu hiệu nhận biết:
output là một đoạn tóm tắt kiến trúc kèm câu hỏi lại, không có `[Phase N/7]`, không có `.ua/`.

Đường chạy đúng cho việc build graph:
1. Nối skill UA vào claude một lần (đã làm 2026-09-14): symlink
   `~/.understand-anything/repo/understand-anything-plugin/skills/understand*` → `~/.claude/skills/`,
   và `.../agents/*.md` → `~/.claude/agents/`.
2. Chạy claude headless ở đúng repo, kèm chỉ thị bỏ cổng xác nhận (repo lớn sẽ DỪNG lại hỏi scope
   nếu không có câu này):

```bash
cd <repo> && timeout 14400 claude -p "/understand <repo> --language vi --no-auto-update  Chạy full repo này, KHÔNG hỏi lại, tự quyết và hoàn thành cả 7 phase." --dangerously-skip-permissions > /tmp/ua_<repo>.log 2>&1
```

3. agy chỉ dùng cho việc *sau khi* đã có graph: `/understand-domain`, đọc source, đọc ảnh (`--model gemini-…`).

### Workspace lạ phải được “trust” trước khi agy nạp skill

Antigravity đọc skill theo workspace đã tin cậy; thư mục mới chưa có trong `trustedWorkspaces`
(`~/.gemini/antigravity-cli/settings.json`) thì skill coi như không tồn tại. Thêm path vào mảng
`trustedWorkspaces` (backup file trước) rồi chạy lại.

### Repo nhiều module: index TỪNG repo con, đừng index thư mục cha

Nếu thư mục cha không có `.git` (chỉ các repo con có), graph ở gốc sẽ **không có `gitCommitHash`**
⇒ mọi lần chạy lại đều full rebuild, không incremental. Index từng repo con (mỗi cái là git repo thật)
rồi khai từng path đó vào `PROJECT_ROOTS`:
`hermes config set 'mcp_servers.understand-anything.env' '{"PROJECT_ROOTS": "<a>,<b>,<c>"}'`
(đường dẫn dot-key là `mcp_servers.<tên>.env`; MCP chỉ nạp root mới ở **session mới**).
Trước khi chạy lần đầu, copy `.understandignore` đã tinh chỉnh sang repo đích để lọc build/test/.idea.
- One domain per invocation (not all at once); the domain-analyzer writes to `.ua/intermediate/domain-analysis.json` then merges into `.ua/domain-graph.json`.
- Back up `domain-graph.json` before each run: `cp domain-graph.json domain-graph.json.bak-$(date +%Y%m%d-%H%M%S)`.

## Đọc ảnh (image reading) — dùng agy, KHÔNG dùng claude

`auxiliary.vision` trên máy này không đáng tin: model đang cấu hình (`deepseek-v4-flash-vision-exp`)
có thể bị provider chặn (HTTP 403 "Model is blocked"). Khi cần ĐỌC ảnh → dùng agy với model
multimodal:

```bash
cd /tmp && timeout 240 agy --model gemini-3.8-flash-medium \
  --add-dir <thư-mục-chứa-ảnh> --print-timeout 3m --dangerously-skip-permissions \
  --print "Đọc ảnh <path tuyệt đối>. <câu hỏi>" >/tmp/agy_out.txt 2>/tmp/agy_err.txt
echo "exit=$?"; tail -c 1500 /tmp/agy_out.txt
```

- **PHẢI redirect ra file rồi đọc lại — ĐỪNG pipe qua `tail`/`head`.** Pipe làm agy nuốt sạch
  output (exit 0 nhưng rỗng), dễ tưởng là lỗi model.
- Model Gemini flash đọc ảnh tốt và nhanh hơn nhiều so với model mặc định (Claude Opus thinking,
  hay timeout 3 phút không ra gì). Danh sách: `agy models` (tên ngắn `gemini-3.8-flash-medium`).
- Ảnh trong cache của Hermes nằm ở `~/.hermes/cache/images/` → `--add-dir` đúng thư mục đó.
- Hoàng chốt (2026-09-10): đọc ảnh dùng **agy**, KHÔNG giao cho claude.

## Khi CẢ 2 account đều hết quota (hành vi thật của wrapper)

Wrapper print mode (`agy` → `agy.real` + guard) thử tối đa `MAX_RETRIES=2` lần: gặp pattern quota thì `hagy next --quiet` + chạy lại; **hết lượt thử thì nó `exit` và trả NGUYÊN văn lỗi quota** — không có đường lui thông minh nào. Nên gặp lỗi quota lần 2 ⇒ dừng, đừng chạy lại vô ích (mỗi lần thử vẫn tốn quota/CPU).

Khi đó làm theo thứ tự:
1. `hagy who` + `tail ~/.antigravity_sw/logs/rotation.log` để xác nhận đúng là hết quota (không đoán). `hagy status` báo quota API thường `403 Forbidden` ⇒ không đọc được số còn lại, chỉ biết qua lỗi thật.
2. **Chờ reset**: log thật cho thấy một account hết lúc 23:25 rồi dùng lại được trong vài giờ ⇒ cửa sổ ≈ vài giờ, KHÔNG hứa con số cụ thể.
3. **Thêm account**: `hagy add` (cần người dùng đăng nhập account mới).
4. **Đổi model rẻ hơn** (`flash`/`flash-high` thay Opus) — hạn mức có thể tách theo nhóm model (chưa đo được, đừng khẳng định).
5. **LUẬT (Hoàng chốt 2026-09-13): "Nếu Matcha không làm được, em phải làm đó" — Matcha cạn quota KHÔNG phải lý do dừng việc, cũng không bắt Hoàng chờ.** Đường Ultron tự làm:
   - đọc source / bản đồ nghiệp vụ: gọi thẳng MCP `understand-anything` (`list_projects`, `query_nodes`/`search_by_file_path`, `get_domain_overview`, `get_domain_flow_detail`, `trace_call_chain`, `get_node_source`) + `read_file`/`search_files`.
   - ảnh: `vision_analyze` trước; model vision bị chặn 403 → đưa ảnh cho Jarvis (claude) đọc. Quyết định 2026-09-10 "đọc ảnh dùng agy" là *ưu tiên*, KHÔNG phải lệnh cấm khi Matcha cạn.
   - việc nặng/dài: chia nhỏ làm từng phần, ghi kết quả ra file, không đợi quota.
6. Chỉ DM Hoàng khi cần anh *quyết định* (thêm account, đổi model, phạm vi việc) — không phải để báo "Matcha hết quota nên em không làm được". Job Matcha làm dở vẫn được hẹn chạy tiếp (schedules.yaml) để phần còn lại hoàn tất.

## Quota management

- Pool: 2 accounts — `lapnv@vnpay.vn` (#1, default) and `trungvt3@vnpay.vn` (#2). Config in `~/.antigravity_sw/hagy_config.json`, accounts in `~/.antigravity_sw/accounts.json`.
- Check current: `hagy who`. Rotate manually: `hagy next`. List: `hagy list`.
- The wrapper auto-rotates on quota-hit only in non-print interactive mode reliably; in print mode it rotates only if output matches quota patterns. Watch `~/.antigravity_sw/logs/rotation.log`.
- Kill stale hung agy processes (`ps -eo pid,etime,args | grep agy | grep -v grep`) before a long run — they hold quota.
- Default model = "Claude Opus 4.6 (Thinking)" (from hagy_config). Consider Gemini flash for cheap high-token runs; verify model name via `agy models` (short names like `gemini-3.8-flash-high`) vs wrapper display names ("Gemini 3.8 Flash (High)") — they differ.
