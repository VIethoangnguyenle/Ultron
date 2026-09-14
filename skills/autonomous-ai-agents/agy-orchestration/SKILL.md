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

### Nhánh nguồn khi build graph (Hoàng chốt 2026-09-14)
Graph `vietbank-sme` **luôn** build từ: `vietbank-sme-omni` → nhánh **`dev-sit`**, repo eKYC
(`viet-bank-ekyc-sme`) → nhánh **`dev`**. KHÔNG build từ nhánh feature đang checkout
(`feature/goi-3.1-napas2.0`, `pilot_hotfix_13_08`, ...). `dvnh-common` → **tag khớp `common_version` trong `gradle.properties` của nhánh dev-sit** (`vietbank-sme-omni`);
ngày 2026-09-14 là `5.0.9` → tag `v5.0.9`. Đọc lại `origin/dev-sit:gradle.properties` mỗi lần build, KHÔNG
lấy nhánh `feature/kafka-module` đang checkout.
Trước khi build: fetch, kiểm nhánh dev-sit/dev có mới hơn không, và **trả lại đúng nhánh cũ sau khi xong**.

### /understand (build the knowledge graph) → chạy bằng **agy**. CLAUDE BỊ CẤM cho việc này

**LUẬT (Hoàng chốt 2026-09-14): "claude không tham gia reasoning này nhá, tốn token lắm".**
Mọi reasoning trên source — build knowledge graph, viết mô tả node, tour, domain — **chỉ dùng agy**.
Claude để dành cho việc CODE (luật chung); đừng "mượn" claude cho UA dù agy đang bận/cạn quota.

`agy --print "/understand <path>"` **KHÔNG mở slash command**: print mode không expand skill, nó chỉ trả lời
như chat rồi thoát (exit 0 trong <60s, không sinh `.ua/`; dấu hiệu: output là đoạn tóm tắt kiến trúc kèm câu
hỏi lại, không có `[Phase N/7]`). Cách chạy ĐÚNG — **bỏ slash command, bảo nó đọc file skill rồi tự chạy
pipeline bằng shell/node** (đã kiểm chứng: sinh được graph thật):

```bash
cd <repo> && timeout 20000 agy --model gemini-3.1-pro-high --effort high \
  --print-timeout 300m --dangerously-skip-permissions -p \
  "Đọc kỹ /home/zane/.agents/skills/understand/SKILL.md và thực thi TOÀN BỘ workflow cho repo <path> (đã có .ua/ dở → RESUME từ chỗ dở, KHÔNG làm lại). Ngôn ngữ output: vi. Dùng công cụ shell/node của bạn để chạy các script trong skill. KHÔNG hỏi lại, tự quyết mọi bước, hoàn thành cả 7 phase tới khi sinh ra .ua/knowledge-graph.json + .ua/meta.json." > /tmp/ua_<repo>.log 2>&1
```

- `--effort high` = mức reasoning; model phải thuộc nhóm `gemini-3.1-pro*` (chỉ nhóm này còn quota).
- Repo lớn: **1 lượt cho toàn bộ sẽ OOM-kill (exit 137)** ở phase sinh mô tả → chia theo module,
  mỗi lượt ≤ ~1.650 node, và bắt agent ghi file tạm rồi `rename` đè (không ghi trực tiếp vào graph).
- Pipeline move `.ua/tmp` + `.ua/intermediate` vào `.ua/.trash-*` sau khi xong — bình thường, KHÔNG phải lỗi.
- Sau khi có graph: `/understand-domain`, đọc source, đọc ảnh vẫn dùng agy (`--model gemini-…`).

### Workspace lạ phải được “trust” trước khi agy nạp skill

Antigravity đọc skill theo workspace đã tin cậy; thư mục mới chưa có trong `trustedWorkspaces`
(`~/.gemini/antigravity-cli/settings.json`) thì skill coi như không tồn tại. Thêm path vào mảng
`trustedWorkspaces` (backup file trước) rồi chạy lại.

### 1 graph cho cả bộ source — đặt ở thư mục CHA, cơ chế giống `vietbank-sme`

**LUẬT (Hoàng chốt 2026-09-14, thay hẳn cách "index từng repo con" trước đó):** graph UA của bộ
`vietbank-digital` **KHÔNG** để rải trong từng repo con (`vietbank-omni/.ua`, `viet-bank-omni-ekyc/.ua`) —
phải **gom tất cả source về 1 graph duy nhất, đặt ở bên ngoài** (ngoài các repo con), *cơ chế giống
`vietbank-sme`*:
- Thư mục cha (`vietbank-digital/`, chứa `vietbank-omni` + `viet-bank-omni-ekyc` + `dvnh-common`) là
  **PROJECT_ROOT**; graph ở `<cha>/.ua/knowledge-graph.json`.
- Mẫu `vietbank-sme` đang chạy đúng thế: repo cha **là git repo** (các repo con cũng là git), `.ua/` ở gốc cha,
  MỘT `knowledge-graph.json` (5.179 file) + `domain-graph.json`, `PROJECT_ROOTS` khai đúng 1 path cha.
- Thư mục cha **chưa có `.git` ⇒ `git init` + `.gitignore` (ignore `.ua/`) trước khi chạy** — không có git thì
  graph thiếu `gitCommitHash` và mọi lần chạy lại là full rebuild (không incremental).
- Phải chạy UA trên đúng PROJECT_ROOT cha: path node khi đó tính từ gốc cha, MCP/`get_node_source` mới
  resolve đúng file; graph merge tay từng repo con sẽ sai đường dẫn (`transaction/…` thay vì
  `vietbank-omni/transaction/…`).
- `PROJECT_ROOTS` nên trỏ **1 root cha** thay vì liệt kê từng repo con:
  `hermes config set 'mcp_servers.understand-anything.env' '{"PROJECT_ROOTS": "<cha>,<dự án khác>"}'`
  (MCP chỉ nạp root mới ở **session mới**).
- Copy `.understandignore` đã tinh chỉnh (lọc build/test/.idea/node_modules) sang thư mục cha trước khi chạy.
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

**LUẬT (Hoàng chốt 2026-09-14): hết quota 1 MODEL ⇒ thử các model KHÁC trước, chỉ `hagy next` (đổi ACCOUNT) khi mọi model đều hết.** Quota tách theo model chứ không phải theo account — nhảy account ngay là lãng phí.

Thang model để thử (lấy từ `agy models`, chỉ nhóm Gemini theo mặc định):
`gemini-3.1-pro-high` → `gemini-3.1-pro-low` → `gemini-3.8-flash-high` → `gemini-3.8-flash-medium` → `gemini-3.7-flash-high` → `gemini-3.7-flash-medium` → `gemini-3.6-flash-high`.
Cách probe: 1 prompt cực ngắn trước khi chạy lại job thật —
`timeout 90 agy --model <m> --print-timeout 1m --dangerously-skip-permissions -p "ok" >/tmp/probe.log 2>&1`
(exit 0 + có trả lời = model còn quota; gặp pattern quota = hết).
- **KHÔNG tự nhảy sang model Claude/GPT qua agy** (`claude-opus-4-6-thinking`, `claude-sonnet-4-6`, `gpt-oss-120b-medium`) khi chưa được Hoàng cho phép — luật "claude không tham gia reasoning" vẫn đứng; nhóm model đó để Hoàng quyết.
- Wrapper v1.3 (`~/.local/bin/agy`) hiện **nhảy account ngay** (`hagy next --quiet`) khi gặp pattern quota, không có bước thử model khác ⇒ bước "thử model khác" phải làm ở phía Ultron cho tới khi Hoàng duyệt sửa wrapper (sửa wrapper = việc code).

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
