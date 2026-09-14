# Playbook: dùng UA MCP để trace nghiệp vụ & node source (vietbank-sme)

Trạng thái graph 2026-09-14 (sau build bằng `claude-opus-4-6-thinking`):
19.953 node / 48.017 edge / 9 layer · domain: **36 domain · 152 flow · 480 step** ·health HEALTHY.

## 1. Bản đồ 22 tool (dùng cái nào khi nào)
| Nhóm | Tool | Dùng để |
|---|---|---|
| Khám phá | `list_projects`, `get_graph_metadata`, `get_graph_stats` | biết có graph gì, node/edge, commit mốc, có cũ không |
| Tra node | `query_nodes` (từ khoá), `search_by_file_path` (đường dẫn), `get_node_detail` | tìm node theo tên/file/thư mục |
| Đọc code node | `get_node_source` | lấy **đoạn source thật** của function/class/file (kèm số dòng) |
| Quan hệ | `get_relationships` (imports/contains/implements/extends), `find_path`, `get_class_hierarchy` | node này nối với ai, đường đi ngắn nhất giữa 2 node |
| Nghiệp vụ | `get_domain_overview` → `get_domain_detail` → `get_domain_flow_detail` | **trục chính để trace nghiệp vụ** |
| Ảnh hưởng | `find_impact` | đổi node này thì cái gì vỡ (blast radius) |
| Kiến trúc | `get_layer_info`, `get_tour`, `find_entry_points`, `get_domain_overview` | vào dự án, tầng, tour dẫn nhập |
| Ít dùng | `read_resource`, `list_resources`, `list_prompts`, `get_prompt` | công cụ phụ trợ của MCP |

## 2. 5 công thức trace (đã chạy thật)

**A. "Nghiệp vụ X chạy thế nào?" — công thức chính**
1. `get_domain_overview(project)` → danh sách 36 nghiệp vụ + flow + entity + tag (đọc để chọn đúng domain).
2. `get_domain_detail(domain_name)` → entity, business rule, danh sách flow.
3. `get_domain_flow_detail(flow_name)` → **entry point (HTTP path) + các bước có thứ tự + node code gắn từng bước + cross-domain interaction**.
4. `get_node_source(node_id)` cho 1-2 node chốt logic (đừng đọc hết cả flow).
5. Trả lời bằng ngôn ngữ nghiệp vụ; nếu người hỏi là dev thì kèm path API (không nêu class/file ngoài Hoàng).
Ví dụ thật: flow `Khởi tạo chuyển tiền Napas tới Tài khoản` → entry `POST /api/napas/init-accounts-transfer`,
6 bước (nhận request → gán narrative → validate thụ hưởng → risk score Napas V2 → build TransactionModel →
check hạn mức & tạo GD PENDING_APPROVED) + mã lỗi (`INVALID_NAPAS_BENE`, `NAPAS_V2_RISK_BLOCKED`,
`SENDER_ACCOUNT_IS_SAME_BENE_ACCOUNT`) + cross-domain (VBG hạch toán, Approval gRPC, Kafka đối soát).

**B. "Code nào làm việc Y?"** → `query_nodes(từ khoá)` (điểm khớp: tên 3x > summary 1.5x > tag) →
`get_node_detail` (layer/tag/complexity) → `get_node_source` để đọc đúng đoạn.

**C. "Sửa/đổi cái này ảnh hưởng gì?"** → `find_impact(node_id, max_depth)` + `get_relationships(direction=in)`
(imports/implements/inherits) → nhóm theo layer để trả lời.

**D. "File này thuộc nghiệp vụ nào?"** → `search_by_file_path(path_pattern)` → `get_node_detail` (layer) →
`get_domain_detail` khớp entity/flow để gắn ngữ cảnh nghiệp vụ.

**E. "API/path nào?"** → ưu tiên `get_domain_flow_detail` (field Entry Point). Nếu flow chưa có, dùng
`find_entry_points` + `search_by_file_path("controller")` rồi xác nhận hằng số đường dẫn **theo ref**
(`git show origin/dev-sit:<path>`) — path thật trong code nằm ở constant + file cấu hình thirdparty.

## 3. Cấm kỵ (đã kiểm chứng)
- `trace_call_chain` **vô dụng** ở dự án này: graph không có edge `calls` (chỉ imports/contains/exports/
  implements/inherits/configures/defines_schema) → nó trả "does not call any other functions". Muốn chuỗi gọi
  thì đi theo flow (mục A) rồi đọc source.
- Đừng tin `summary` mức `function` suông (một số còn câu khuôn sáo) → luôn `get_node_source` để chắc.
- Graph là ảnh chụp theo commit: **không** dùng để khẳng định "không có code" cho nhánh khác.
- Không grep working tree khi checkout có thể đang ở nhánh feature ⇒ grep theo ref (`git grep <ref>`) — xem
  mục "Đọc code phải theo REF" trong SKILL.md.

## 4. Bảo trì graph sau mỗi lần build (bài học 2026-09-14)
- Lượt `/understand` mới **GHI ĐÈ `domain-graph.json` bằng node type `module`** (rác: kiểu
  `domain:common-CHANGELOG.md`) ⇒ **mất toàn bộ domain nghiệp vụ** (36 domain/152 flow/480 step nằm ở
  `domain-graph.json.master`). Sau mọi lần build phải: `cp .ua/domain-graph.json.master .ua/domain-graph.json`
  (và giữ bản modules cũ để đối chiếu). Kiểm bằng `get_domain_overview` — rỗng hoặc ra "module" là hỏng.
- Trước khi build: backup `.ua/` (thao tác rẻ, đã cứu cả buổi 2026-09-14) và đảm bảo `meta.json` có key
  `analyzedAt` (analyzer chỉ ghi `lastAnalyzedAt`, MCP đọc `analyzedAt`).
- Nguồn nhánh: omni `dev-sit`, ekyc `dev`, dvnh-common tag theo `common_version` của dev-sit.
- Nghiệm thu: nodes/edges > ngưỡng, summary thật, `get_graph_metadata` health HEALTHY, `get_domain_overview`
  ra 36 domain — thiếu 1 cái là chưa xong.
