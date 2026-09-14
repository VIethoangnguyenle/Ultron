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

## 4. Kết quả A/B grep vs UA (đo thật 2026-09-15, 3 câu trace × 2 cách, session CLI riêng)
| Câu hỏi | grep: token / lượt | UA: token / lượt | Kết luận |
|---|---|---|---|
| Luồng chi lương (bước+path+mã lỗi) | 1,03M / 23 | 1,22M / 21 | UA **tốn hơn**: mã lỗi nằm trong hằng số code, graph chỉ có 2 mã |
| Validate tên thụ hưởng Napas | 0,50M / 11 | 0,24M / 6 | UA **-52%** |
| Sửa hạn mức gói → ảnh hưởng gì | 0,56M / 13 | 0,46M / 9 | UA **-18%** |
| **Tổng** | **2,09M** | **1,92M** | **-8%** (không phải 50-70% như ước lượng) |
Thời gian: UA nhanh hơn ~30-40% (q2: 29s vs 57s).

**Vì sao chênh ít:** agent vẫn đi lang thang (q1 UA 21 lượt) và **MCP có overhead riêng**: mỗi tool MCP
phải `tool_describe` schema rồi `tool_call` (q1 UA: 8 lần tool_describe + 2 skill_view). Muốn UA tiết kiệm
thật thì phải **ép recipe ngắn 3-5 lượt** (overview → flow detail → node source), không cho roam.

**Chất lượng theo loại câu hỏi:**
- Luồng nghiệp vụ: UA thắng về *cấu trúc* (thứ tự bước, trạng thái, cross-domain); grep thắng về *danh mục mã lỗi*.
- Định vị thành phần: hoà, UA thêm chi tiết (action code V1/V2, cache).
- Ảnh hưởng: tương đương độ phủ.
- ⚠️ **Path API trong graph CÓ SAI** (graph ghi `/transfer/payroll/init-internal`, code thật
  `/transfer/payroll/internal/init`; tương tự `validate-internal` vs `/internal/validate`) ⇒ path + mã lỗi
  **bắt buộc chốt lại bằng code theo ref**, không chép từ graph.

## 4b. Vòng 2 — ÉP RECIPE NGẮN (cùng câu Q1 chi lương, 2026-09-15)
| Cách | token | lượt tool | Chất lượng |
|---|---|---|---|
| grep thuần (mốc vòng 1) | 1.026.483 | 23 | đủ path + mã lỗi 700xxx/701xxx |
| UA **ép recipe** (flow_detail → domain_detail → node_source ×2) | **155.930** | 5 | khung 4 chặng đủ, nhưng path theo graph **bị sai dạng** (`/validate-internal`, `/init-internal`) và chỉ 2 mã lỗi dạng tên |
| **LAI** (3 lượt UA lấy khung + 3 lượt grep/read chốt) | **204.636** | 6 | path ĐÚNG (`/internal/validate`, `/internal/init`) + mã lỗi 700xxx đầy đủ + khung nghiệp vụ |

⇒ **Quy tắc chuẩn = LAI**: 2-3 lượt UA lấy khung + tối đa 3 lượt code để chốt path/mã lỗi. Tiết kiệm
**~80% token** so với grep thuần mà chất lượng cao hơn hẳn.
Vòng 1 chỉ −8% vì agent roam (21 lượt) + overhead `tool_describe`/`skill_view`/`memory_save` — cấm mấy thứ đó
khi trace. Kết luận: **cách ép recipe quan trọng hơn việc chọn tool nào**.

## 4c. Vòng 3 — đủ 4 loại câu hỏi (2026-09-15)
| Loại câu | grep thuần | LAI (UA khung + code chốt) | UA-only ép ngắn | Kết luận |
|---|---|---|---|---|
| Q1 luồng chi lương (+path, mã lỗi) | 1.026.483 / 23 | 204.636 / 6 | 155.930 / 5 (path sai) | LAI −80% |
| Q2 định vị thành phần + phụ thuộc | 504.769 / 11 | 250.199 / 7 | — | −50%, chất lượng cao hơn |
| Q3 ảnh hưởng khi sửa hạn mức | 562.652 / 13 | 346.372 / 8 | — | −38% |
| Q4 kiến trúc (layer + luồng tổng) | **grep không làm được** | — | 186.996 / 6 | UA độc quyền (get_layer_info/get_tour) |

⇒ Chốt: **câu nghiệp vụ/định vị/ảnh hưởng → dùng LAI**; **câu kiến trúc → UA-only**. Tiết kiệm thực đo
38-80% (trung bình ~55%). Cảnh báo: agent vẫn có thể vượt hạn mức lượt (Q2 dùng 13 lượt tool) ⇒ khi tự
trace phải tự giữ recipe; và **path API giữa các nguồn còn lệch nhau** (Q2: `nonfinancial/validate-bene/napas`
vs `bank/validate-bene/napas`) ⇒ luôn chốt path bằng annotation controller thật.

## 5. Bảo trì graph sau mỗi lần build (bài học 2026-09-14)

- Lượt `/understand` mới **GHI ĐÈ `domain-graph.json` bằng node type `module`** (rác: kiểu
  `domain:common-CHANGELOG.md`) ⇒ **mất toàn bộ domain nghiệp vụ** (36 domain/152 flow/480 step nằm ở
  `domain-graph.json.master`). Sau mọi lần build phải: `cp .ua/domain-graph.json.master .ua/domain-graph.json`
  (và giữ bản modules cũ để đối chiếu). Kiểm bằng `get_domain_overview` — rỗng hoặc ra "module" là hỏng.
- Trước khi build: backup `.ua/` (thao tác rẻ, đã cứu cả buổi 2026-09-14) và đảm bảo `meta.json` có key
  `analyzedAt` (analyzer chỉ ghi `lastAnalyzedAt`, MCP đọc `analyzedAt`).
- Nguồn nhánh: omni `dev-sit`, ekyc `dev`, dvnh-common tag theo `common_version` của dev-sit.
- Nghiệm thu: nodes/edges > ngưỡng, summary thật, `get_graph_metadata` health HEALTHY, `get_domain_overview`
  ra 36 domain — thiếu 1 cái là chưa xong.
