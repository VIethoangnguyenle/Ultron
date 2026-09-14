---
name: ua-source-trace
description: Use when tracing vbsme source (UA graph first).
---

# Trace source = graph first, source second (Hoàng chốt 2026-09-14)

Hoàng's rule: for any source-tracing question ("API nào / cơ chế nào", call chain, impact, "đọc code hiểu
luồng") in the vietbank/vbsme repos, **query the Understand-Anything (UA) MCP knowledge graph before
touching grep/read_file**. Grep is the *confirmation* step, never the search step.

## Đọc code phải theo REF, không đọc bản đang checkout (Hoàng nêu 2026-09-14)
Rủi ro thật: `grep`/`read_file` đọc working tree = nhánh đang checkout. Đo được 2026-09-14:
`feature/goi-3.1-napas2.0` vs `origin/dev-sit` của `vietbank-sme-omni` lệch **1.119 file / +52.644 −6.552 dòng`
⇒ trace bằng grep trong lúc checkout ở nhánh feature có thể kết luận "không có code" trong khi code CÓ (chỉ là
ở nhánh khác), hoặc trích nhầm logic cũ. Luật — 3 lớp:
1. **Graph trước**: graph UA là ảnh chụp theo commit đã build (meta.json ghi commit từng repo) ⇒ không phụ
   thuộc checkout. Đây là nguồn định vị chính.
2. **Grep theo ref**: `git -C <repo> grep -n "<pattern>" origin/dev-sit -- "*.java"` và
   `git -C <repo> show origin/dev-sit:<path>` — chạy đúng nhánh mà KHÔNG cần checkout, không đụng việc
   Hoàng đang làm. Nhánh nguồn: omni = `dev-sit`, ekyc = `dev`, dvnh-common = tag theo `common_version`.
3. **Nói rõ mốc**: mọi câu trả lời trace phải kèm "ở nhánh/commit nào" để người nghe biết bản đang xét.
Khi câu hỏi trace trên code MỚI (chưa có trong graph) ⇒ nói rõ là bằng chứng từ nhánh nào, và nếu
checkout không ở nhánh đó thì phải grep theo ref chứ đừng đọc file trong working tree.

## Phân công công cụ (Hoàng chốt 2026-09-14)
- **Graph UA = của Ultron, để GIẢI THÍCH NGHIỆP VỤ + PHÂN TÍCH** (trả lời tester/dev, hiểu luồng, đánh giá ảnh hưởng). Nguồn graph là nhánh **`dev-sit`** của `vietbank-sme-omni` (Hoàng: "dev-sit là nhánh đầy đủ code nhất"), `dev` cho eKYC, tag theo `common_version` cho `dvnh-common`.
- **Khi Hoàng giao Jarvis (claude) SỬA CODE**: Jarvis tự dùng `codegraph` / `serena` index của nó trong repo — phần đó Jarvis lo, Ultron KHÔNG cần trace/không cần lo nhánh cho nó, cũng không cần đồng bộ hai bên.
- Vì graph là ảnh chụp theo commit nên **đừng dùng nó để khẳng định "không có code"** cho một nhánh khác (feature, release...): nói rõ là đang xét mốc nào, cần bản khác thì grep theo ref.

## Giới hạn đã đo của graph (2026-09-14, 19.953 node / 48.017 edge)
- Edge chỉ có **cấu trúc**: `imports` 22.672 · `contains` 14.591 · `exports` 4.650 · `configures` 2.957 ·
  `implements` 1.515 · `inherits` 1.431 · `defines_schema` 201. **KHÔNG có edge `calls`** ⇒
  `trace_call_chain` trả về rỗng ("does not call any other functions"). Đừng dùng nó rồi kết luận "không gọi gì".
- Vì vậy: câu hỏi **nghiệp vụ/phân tích** ⇒ domain graph (`get_domain_overview`, `get_domain_detail`,
  `get_domain_flow_detail`) + summary node; câu hỏi **chuỗi gọi hàm/đường đi** ⇒ `find_entry_points` /
  `get_node_source` rồi đọc code **theo ref** (`git show <ref>:<path>`).
- `get_graph_metadata` có thể báo `health: HEALTHY` kèm cảnh báo `meta.json missing analyzedAt` — analyzer ghi
  khoá `lastAnalyzedAt`, server đọc `analyzedAt`; cần thì thêm key `analyzedAt` vào `.ua/meta.json` (và MCP
  phải được nạp lại mới thấy).
- Summary mức file/class thường là mô tả thật; một số node mức `function` còn câu khuôn sáo kiểu
  "Phương thức X xử lý logic trong X" ⇒ khi trả lời phải đọc `get_node_source` để chắc, đừng tin summary suông.

Playbook đầy đủ (22 tool + 5 công thức trace + bảo trì graph): `references/ua-tool-playbook.md`.

## Protocol (in order)
1. `mcp__understand_anything__list_projects` — which graph is loaded (`vietbank-sme`, `Vietbank Digital`).
2. Locate: `search_by_file_path` (known file) or `query_nodes` (known symbol/feature keyword).
3. Follow: `trace_call_chain`, `find_entry_points`, `find_impact`, `get_class_hierarchy`, `get_relationships`.
4. Get the code the graph points at: `get_node_source` / `get_node_detail` (prefer over opening the file).
5. Business flows: `get_domain_flow_detail(flow_name=...)` / `get_domain_detail` / `get_domain_overview`.
6. Only then, to confirm the exact branch/path: ONE targeted `read_file` slice or `grep` of the file(s) the graph named.

## Honesty rules
- Coverage of `vietbank-sme` was **69%** (5,179 files) on 2026-09-14 ⇒ **an empty graph answer is not proof
the code is missing.** Fall back to source and **say which path you used**.
- Check freshness via `get_graph_metadata`; it reports `status: UNKNOWN` because `meta.json` writes
`lastAnalyzedAt` while the server reads `analyzedAt` — say so when staleness matters.
- Domain-graph paths are templates (`/api/v*`): confirm the real base URI before quoting an endpoint.

## Why (evidence)
Logs on 2026-09-14 showed the graph was effectively never used (5 × `list_projects`, 1 × `query_nodes`)
while one thread burned **452 tool results for 39 questions** via grep chains. Every tool result is re-sent
with the whole context to a provider with **no prompt cache**, and the 12k-char tool-output cap makes those
dumps lossy too — so grep-first is less accurate AND far more expensive.

## Rebuild rule (refresh the graph)
`vietbank-sme` graph is always built from: `vietbank-sme-omni` → branch **`dev-sit`**, eKYC
(`viet-bank-ekyc-sme`) → branch **`dev`**, `dvnh-common` → the **tag matching `common_version` in
`vietbank-sme-omni`'s `dev-sit` `gradle.properties`** (re-read each time; 2026-09-14 was `5.0.9` → tag
`v5.0.9`). Build with **agy**, never claude (claude = code only). Write a restore script and put the working
copies back to their original branches when the build finishes.

## Disclosure
Answer in business language for anyone but Hoàng (no class/file/method names outside the DM with Hoàng),
while keeping the trace internally rigorous: endpoint → handler → client → core-banking path → DB table.
