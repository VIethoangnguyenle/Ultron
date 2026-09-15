---
name: ua-source-trace
description: Use when tracing vbsme source (UA graph first).
---

# Trace source: graph lấy khung, code chốt chi tiết (Hoàng chốt 2026-09-15)

Áp cho mọi câu trace source ("API nào / cơ chế nào", luồng nghiệp vụ, ảnh hưởng, "đọc code hiểu luồng") trên
các repo vietbank/vbsme. Grep KHÔNG BAO GIỜ là bước tìm kiếm — chỉ là bước xác nhận.

## QUY TẮC CHÍNH (đo bằng A/B 2026-09-15)
| Loại câu hỏi | Cách làm | Tiết kiệm so với grep thuần |
|---|---|---|
| Luồng nghiệp vụ (bước + path + mã lỗi) | **LAI**: 2-3 lượt UA (`get_domain_flow_detail` → `get_domain_detail`) + ≤3 lượt grep/read để CHỐT path & mã lỗi | **−80%** |
| Định vị thành phần + phụ thuộc | **LAI** (`query_nodes` → `get_node_detail` → xác nhận bằng code) | −50% |
| Sửa X ảnh hưởng gì | **LAI** (`find_impact` + `get_domain_flow_detail`) | −38% |
| Kiến trúc / layer / luồng tổng | **UA-only** (`get_layer_info`, `get_tour`) — grep không làm được | chỉ UA làm được |

Số tuyệt đối (câu "chi lương"): grep 1.026.483 token / 23 lượt vs LAI 204.636 / 6 lượt.
Chi tiết 3 vòng đo: `references/ua-tool-playbook.md`.

**Chống "roam" (bắt buộc):** trong lúc trace, CẤM đọc skill, CẤM lưu memory, CẤM gọi `tool_describe` nhiều lần,
CẤM grep mò. Vòng A/B đầu chỉ −8% vì agent tự làm mấy việc đó (21 lượt); ép recipe mới ra −80%.

**Code CHỐT 2 thứ, không lấy từ graph:** path API (graph hay SAI: `/transfer/payroll/init-internal` vs code
thật `/transfer/payroll/internal/init`; `validate-internal` vs `/internal/validate`) và danh mục mã lỗi
(graph chỉ có vài mã; mã đầy đủ nằm trong hằng số code / `AD_MESSAGE`).

## Đọc code phải theo REF, không đọc bản đang checkout
`grep`/`read_file` đọc working tree = nhánh đang checkout. Đo 2026-09-14: `feature/goi-3.1-napas2.0` vs
`origin/dev-sit` (vietbank-sme-omni) lệch **1.119 file / +52.644 −6.552 dòng** ⇒ có thể kết luận "không có code"
trong khi code CÓ ở nhánh khác. Luật 3 lớp:
1. **Graph trước** — ảnh chụp theo commit (meta.json ghi commit từng repo), không phụ thuộc checkout.
2. **Grep theo ref** — `git -C <repo> grep -n "<pattern>" origin/dev-sit -- "*.java"`, `git -C <repo> show origin/dev-sit:<path>`:
   đúng nhánh mà không cần checkout. Nhánh nguồn: omni = `dev-sit`, ekyc = `dev`, dvnh-common = tag theo `common_version`.
3. **Nói rõ mốc** — mọi câu trả lời kèm "ở nhánh/commit nào".

## Phân công công cụ
- **Graph UA = của Ultron**, để GIẢI THÍCH NGHIỆP VỤ + PHÂN TÍCH (trả lời tester/dev, đánh giá ảnh hưởng).
- **Hoàng giao Jarvis (claude) SỬA CODE** ⇒ Jarvis dùng `codegraph`/`serena` của nó; Ultron không trace hộ,
  không đồng bộ hai bên.
- Graph là ảnh chụp theo commit ⇒ **không dùng nó để khẳng định "không có code"** cho nhánh khác.

## Giới hạn đã đo của graph (2026-09-14: 19.953 node / 48.017 edge / 9 layer)
- Edge chỉ **cấu trúc**: `imports`, `contains`, `exports`, `configures`, `implements`, `inherits`, `defines_schema`.
  **KHÔNG có edge `calls`** ⇒ `trace_call_chain` trả rỗng; đừng dùng nó rồi kết luận "không gọi gì".
  Chuỗi gọi hàm phải đi bằng domain flow + `find_entry_points` + đọc source theo ref.
- Domain graph (36 domain / 152 flow / 480 step) nằm ở `.ua/domain-graph.json`; bản tích luỹ là
  `.ua/domain-graph.json.master`. **Sau MỖI lần rebuild phải khôi phục `.master` đè lên `domain-graph.json`** —
  nếu không, `/understand` mới sẽ ghi đè bằng node rác type `module` (kiểu `domain:common-CHANGELOG.md`) và
  `get_domain_overview` trả rỗng.
- `meta.json` phải có khoá `analyzedAt` (analyzer chỉ ghi `lastAnalyzedAt`; MCP đọc `analyzedAt`) — thêm tay rồi
  nạp lại MCP mới hết `freshness: UNKNOWN`.
- Summary mức file/class thật; một số node `function` còn khuôn sáo ⇒ cần `get_node_source` để chắc.

Playbook đầy đủ (22 tool · 5 công thức · cấm kỵ · bảo trì · 3 vòng A/B): `references/ua-tool-playbook.md`.

## Recipe ngắn (dùng cái này, đừng roam)
1. `get_domain_overview` → chọn domain/flow đúng.
2. `get_domain_flow_detail(flow_name=...)` → entry point + các bước + node code + cross-domain.
3. `get_node_source` cho 1-2 node quan trọng (nếu cần chi tiết).
4. ≤3 lượt `grep`/`read_file` **theo ref** để chốt path API + mã lỗi.
5. Trả lời: khung nghiệp vụ + path đã xác minh + mã lỗi + nói rõ mốc (nhánh/commit).

## Honesty rules
- Câu trả lời rỗng từ graph KHÔNG phải bằng chứng code không tồn tại (coverage chưa 100%) ⇒ fallback source
  và **nói rõ đã fallback**.
- Path trong domain graph là template ⇒ xác nhận bằng annotation controller thật trước khi trích endpoint.

## Rebuild rule
Graph `vietbank-sme` luôn build từ: `vietbank-sme-omni` → nhánh **`dev-sit`**, eKYC (`viet-bank-ekyc-sme`) →
nhánh **`dev`**, `dvnh-common` → **tag khớp `common_version` trong `gradle.properties` của dev-sit** (đọc lại mỗi
lần; 2026-09-14 là `5.0.9` → tag `v5.0.9`). Build bằng **agy** (ưu tiên `claude-opus-4-6-thinking`), KHÔNG dùng
claude (claude = code only). Nghiệm thu: đếm nodes/edges, soi summary, `get_graph_metadata` health — **exit 0
KHÔNG có nghĩa là graph đủ** (đã có lần exit 0 nhưng 0 edge). Nhớ backup `.ua` và trả nhánh về nguyên trạng.

## Dọn dẹp sau rebuild (BẮT BUỘC — Hoàng yêu cầu 2026-09-15)
Một lượt rebuild để lại rác ở gốc workspace (đã có lần ~300MB: `.ua.good-*`, `.ua.degraded-*`,
`.ua/.trash-*`, `.ua/intermediate`, `.ua/tmp`, `.ua/*.bak-*`, và 8 file `.cjs` vặt). Luật:
1. Script vặt (convert / inject / patch JSON trung gian) viết vào `/tmp/ua-<ts>/` — **KHÔNG BAO GIỜ**
   đặt ở gốc workspace vietbank-sme; chạy xong là hết giá trị.
2. Chạy xong phải prune: xoá `.ua/tmp`, `.ua/intermediate`, mọi `.ua/.trash-*`, `.ua/*.bak-*`
   (trừ `.master`), `.ua/domain-graph.json.modules-*`; chỉ giữ **1** bản backup `.ua.backup-<ngày>`.
3. Giữ nguyên: `knowledge-graph.json`, `fingerprints.json`, `meta.json`, `domain-graph.json`,
   `domain-graph.json.master`, `config.json` — MCP đang đọc. Xoá nhầm `.master` = mất bản tích luỹ domain graph.
4. Trước khi xoá backup phải verify: `md5sum .ua/domain-graph.json .ua/domain-graph.json.master`
   phải trùng nhau, và 3 repo (omni/ekyc/dvnh-common) đã về đúng nhánh cũ.
5. Rác KHÔNG đến từ 1 lỗi mà **tích tụ theo lượt**: `.ua/.trash-*` là cơ chế chờ 7 ngày của pipeline
   (chỉ được dọn ở Phase 0 của một lượt `/understand` mới ⇒ lượt nào không chạy full thì nó nằm mãi),
   `.ua/*.bak-*` do chính mình backup mỗi lượt (giờ ghi ra `/tmp/ua-backup/`), `.ua.good-*`/`.ua.degraded-*`
   là bản sao an toàn mình tự tạo. ⇒ Prune NGAY sau mỗi lượt rebuild, không để qua ngày; và nhớ rác chỉ
   ~300MB, trong khi `build/` (gói build) chiếm ~35GB — đừng nhầm thủ phạm khi soi dung lượng.

## Disclosure
Trả lời bằng ngôn ngữ nghiệp vụ với mọi người ngoài Hoàng (không nêu class/file/method ngoài DM với Hoàng),
nhưng trace bên trong vẫn đủ chuỗi: endpoint → handler → client → core banking → bảng DB.
