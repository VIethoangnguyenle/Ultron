---
name: hermes-runtime-audit
description: "Use when asked to audit Ultron's real runtime config."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [audit, runtime, config, evidence, self-inspection, hermes]
    related_skills: [internal-technical-docs, system-resource-monitoring, google-chat-setup, agentmemory]
---

# Audit runtime Hermes — khai báo "thực tế đang chạy" kèm nguồn

Class of work: Hoàng yêu cầu Ultron **tự kiểm tra và khai báo cơ chế vận hành thật của chính nó trên máy này**
— danh tính/profile · toolset · system prompt · bộ nhớ · skills · đa agent/kanban · kết nối · sandbox —
hoặc bất kỳ biến thể "đang chạy thật là gì, đừng nói theo tài liệu".

Khác hẳn `internal-technical-docs` (viết tài liệu giới thiệu cho người đọc): ở đây **người đọc là Hoàng, và
anh sẽ kiểm chứng từng dòng** ⇒ sản phẩm là bảng "giá trị thực tế ↔ nguồn", không phải văn mô tả.

## Luật bằng chứng (đứng trên mọi mục khác)

1. **Mọi khẳng định phải có nguồn**: `đường-dẫn:dòng` hoặc **lệnh đã chạy**. Không suy ra từ trí nhớ hay từ
docs Hermes. Thứ không xác minh được ⇒ ghi `KHÔNG XÁC MINH ĐƯỢC` **kèm cách đã thử** (grep/lệnh nào). Cấm đoán lấp chỗ trống.
2. **KHÔNG trích số dòng / tên key từ output đã bị cắt hoặc bị elide.** Output dài bị cắt âm thầm; viết tiếp
bằng trí nhớ sẽ sinh ra key/dòng **không tồn tại** — loại lỗi tệ nhất trong báo cáo kiểu này. Trước khi ghi
mỗi citation: in LẠI đúng khoảng dòng đó (`python3 -c` đọc file + `enumerate`) và chỉ trích khi đã thấy tận mắt.
3. **Ước lượng phải dán nhãn ước lượng** (`≈`, "chưa đo bằng tokenizer"). Số đo được và số suy ra không được trộn.
4. **Che secret, đừng dán giá trị**: secret nằm plaintext trong `config.yaml`/`.env` ⇒ chỉ ghi `đường-dẫn:dòng`
+ `(giá trị đã che)`. Trước khi gửi file, tự kiểm rò: `grep -c "<4-6 ký tự đầu của secret>" <file>` phải = 0.
5. **Đọc state sống bằng read-only**: mở `state.db` qua `file:state.db?mode=ro` — gateway đang chạy và giữ lock.
6. **Không tự sửa trong cùng lượt**: phát hiện config/doc lệch nhau thì **báo + hỏi** (vd một file ghi ngưỡng cũ
còn `config.yaml` đã đổi), đừng tự sửa SOUL.md/config khi Hoàng chưa OK.

## Quy trình (thứ tự này giữ được nguồn cho mọi mục)

1. **Chụp trạng thái thô trước khi viết**: mỗi lệnh đổ ra file trong một thư mục làm việc
(`mkdir -p ~/audit-<ngày>/`, `cmd > ~/audit-<ngày>/x.txt 2>&1`) ⇒ vừa có bằng chứng, vừa tránh output dài bị elide
(xem bẫy #2).
2. **Đi từng mục theo bảng nguồn** ở `references/inspection-sources.md` — mỗi mục có sẵn đúng lệnh + file
quyết định. Không tự nghĩ lệnh mới khi bảng đã có (`hermes <sub> --help` trước nếu phải tìm).
3. **Mục system prompt**: KHÔNG đọc được từ file — bản thật nằm trong bảng `system_prompts` của `state.db`.
Lấy bản mới nhất (`order by rowid desc limit 1`), rồi dựng bản đồ khối bằng cách dò marker và tính offset
(bảng marker trong references). Đây là bằng chứng duy nhất cho "prompt đang chứa gì, dài bao nhiêu".
4. **Đếm bằng tool, không nhẩm**: số skill (`find … -name SKILL.md | wc -l`), số memory/lesson (MCP
`memory_diagnose`), số tool MCP (`logs/agent.log` dòng "registered N tool(s) from M server(s)"), số cron
(`hermes cron list --all`), số action lịch (`daily_dispatch.py --list`).
5. **Cuối báo cáo** luôn có 3 mục: (a) **khác mặc định Hermes** (mỗi dòng 1 nguồn), (b) **rủi ro / sai lệch**
xếp theo mức nguy hiểm, (c) **KHÔNG XÁC MINH ĐƯỢC** + cách đã thử.
6. **Giao bài**: ghi `~/audit-<YYYY-MM-DD>.md`, gửi **file thật** vào đúng space/thread bằng
`scripts/gchat_send_file.py --space <spaces/…> --thread <spaces/…/threads/…> --text "<caption có tên file>"`;
tin chat chỉ là tóm tắt (mỗi mục 1 dòng + top rủi ro), KHÔNG dán cả tài liệu. Xác nhận file đã lên bằng
response có `attachment` (đừng tin mỗi exit code).

## Bẫy đã trả giá (đọc trước khi kết luận)

1. **`hermes dump` khai thiếu runtime**: in `platforms: none` và `mcp_servers: 0` trong khi gateway đã connected
và MCP đã đăng ký hàng trăm tool. ⇒ Cấm dùng `dump` để kết luận về kết nối; nguồn thật là `gateway_state.json`,
`logs/agent.log`, `hermes cron status`. Gặp lệch thì ghi lại như một sai lệch của dump.
2. **Output dài bị elide hoặc bị pipe cắt** ⇒ chỉ còn 1 dòng "…" trong kết quả. Đừng kết luận "lệnh lỗi/không có gì":
đổ ra file rồi `grep`/`sed -n` đúng khoảng cần đọc. (Một `read_file` toàn bộ config trả về đúng 1 dòng metadata —
đó là elide, không phải file rỗng.)
3. **"Toolset bị tắt" KHÔNG nằm trong config**: `config.yaml` không có danh sách tool tắt — trạng thái disabled đến từ
định nghĩa bundle trong `toolsets.py` (các toolset ghi "opt-in, not in default toolset"). Đừng đi tìm key config không tồn tại.
4. **`hermes tools list` mặc định là platform `cli`** ⇒ phải truyền `--platform <tên>`. Hai platform ra kết quả giống nhau
nghĩa là platform đó fallback về bundle mặc định, không phải "cấu hình riêng giống nhau". Tên bundle mà `toolsets.py`
không định nghĩa (vd `hermes-<platform>` lạ) là một sai lệch đáng báo, không phải lỗi của mình.
5. **`~/.local/share/agentmemory/state_store.db` là THƯ MỤC shard (kv file store), không phải SQLite** — `sqlite3`
báo "unable to open database file". Số memory/lesson lấy từ MCP `memory_diagnose` / `memory_profile` (gọi qua
`tool_search`→`tool_describe`→`tool_call`).
6. **`.bundled_manifest` là `tên:hash` nhưng hash KHÔNG phải md5 của SKILL.md** (đối chiếu 58/58 lệch) ⇒ chỉ dùng nó để
phân loại "có trong manifest hay không"; đừng kết luận "skill bundled đã bị sửa" từ hash lệch.
7. **Skill sinh tự động có sổ**: `.curator_ledger.jsonl` (mỗi dòng 1 event + actor) là nguồn để nói skill nào do
learning loop tạo và tạo lúc nào — đừng phán theo `mtime` (mtime chỉ là lần sửa cuối).
8. **Search rộng trong `~/.hermes` rất tốn ngữ cảnh** (cache json vài MB, và grep theo symbol có thể đổ cả một cây thư mục
vào transcript). Tìm có mục tiêu, ưu tiên đọc file cụ thể.
9. **`hermes plugins list` hiển thị MỌI plugin là "not enabled"** kể cả plugin đang hoạt động ở vai trò khác
(vd `agentmemory` chạy như memory provider). Đọc trạng thái plugin luôn kèm `hermes memory status` / `hermes tools list`
trước khi kết luận "không plugin nào chạy".

## Chất lượng báo cáo

- Giữ đúng **số mục và thứ tự** Hoàng yêu cầu trong đề bài; mỗi mục một bảng `mục | giá trị thực tế | nguồn`.
- Con số kèm **đơn vị và thời điểm** (vd `state.db 411 MB lúc 22:41`) vì mọi thứ sẽ lệch về sau.
- Rủi ro phải nói **cơ chế**, không chỉ hiện tượng: "`approvals.mode: off` + user thuộc group `docker` ⇒ tương đương
root và không còn cổng duyệt" (*vì sao* nguy hiểm), kèm dòng code/key làm bằng chứng.
- Kết chat bằng 1–2 đề nghị cụ thể (sửa số liệu lệch trong tài liệu, thêm việc vào lịch) — không hỏi dồn.

## References

- `references/inspection-sources.md` — bảng nguồn theo từng mục audit (lệnh đã kiểm + file/bảng quyết định),
bảng marker để dựng bản đồ khối system prompt, và đường dẫn kho agentmemory.
