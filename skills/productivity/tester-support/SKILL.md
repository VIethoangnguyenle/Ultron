---
name: tester-support
description: "Answer tester questions in group chats, scoped per project."
version: 0.1.0
author: Hoang Nguyen (VIethoangnguyenle), Ultron
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [tester-support, google-chat, knowledge-graph, scope-isolation, log-analysis]
    related_skills: [google-chat-setup, hermes-mcp-config]
---

# Tester Support

Ultron trả lời câu hỏi của tester trong các group Google Chat, CHỈ trong phạm vi
(scope) dự án của group đó. Kiến thức để trả lời đến từ **4 nguồn tri thức** của
mỗi dự án (graph + mã lỗi + DB + log + KB bổ sung), không bao giờ tự bịa hoặc trôi
sang dự án khác.

## Khi dùng (When to Use)

- Bị tester @mention trong group hỏi về nghiệp vụ, flow, mã lỗi, môi trường test,
  bug của dự án.
- Hoàng dạy kiến thức dự án (LEARN flow) để Ultron ghi vào KB bổ sung.
- Cần trace một luồng/triệu chứng lỗi về source code, tra mã lỗi, đọc log, hoặc lấy
  dữ liệu môi trường SIT của dự án.

Đừng dùng khi: câu hỏi ngoài scope dự án, câu hỏi nhạy cảm (deadline, quyết định,
số liệu, hợp đồng) — khi đó escalate về Hoàng (xem Guardrails).

## Mô hình tri thức 1 dự án — 4 nguồn

| Nguồn | Nội dung | Ultron lấy bằng cách |
|---|---|---|
| **Graph** (CHÍNH — ưu tiên trace nghiệp vụ) | domain-graph.json (nghiệp vụ: domain/flow/step/luật/entity) + knowledge-graph.json (code: class/function/file/import) | MCP `understand-anything` (17 tools) |
| **Mã lỗi** | giải thích mã lỗi: nghĩa + vì sao bị | **luôn query bảng mã lỗi qua `db-access`, theo `error_code_source` trong scope-map** (per-project, mỗi dự án có thể khác bảng/schema) |
| **DB** | dữ liệu môi trường SIT (8 DB của VBSME) | MCP `db-access` (chỉ SIT; UAT/LIVE KHÔNG có DB) |
| **Log** | log service UAT/LIVE (Apache autoindex) | `curl -k` vào log_source, phân tích bằng `vblog.py` |
| **KB bổ sung** | những gì 4 nguồn trên không nói được: test env/account/data mẫu, bug đã biết, limitation | đọc `references/knowledge/<project>/` |

Graph là nguồn CHÍNH (Hoàng đã build graph cho từng dự án). KB bổ sung chỉ để lấp
lỗ hổng — đừng tạo KB trùng lặp những gì graph đã chứa sẵn.

## Scope map — nguồn sự thật duy nhất về "group nào thuộc dự án nào"

File `references/scope-map.json` (cùng thư mục skill này) map mỗi group → đúng 1 dự án + đường
dẫn các nguồn. Đọc nó TRƯỚC khi trả lời bất kỳ câu hỏi nào. Cấu trúc mỗi project:

```json
{
  "projects": {
    "vietbanksme": {
      "spaces": ["AAAADv4ib6s", "..."],
      "graph_source": "/abs/path/to/project/.ua",
      "log_source": { "uat": "https://.../omni-sme/", "live": "https://.../omni-sme/live/" },
      "log_analyzer": "/abs/path/to/vnpay-log-analyzer/vblog.py",
      "error_code_source": { "db": "VBSMEONL", "table": "AD_MESSAGE" },
      "db_source": { "env": "SIT", "databases": ["VBSMEONL", "..."] },
      "kb_dir": "references/knowledge/vietbanksme/"
    }
  }
}
```

- `spaces`: danh sách space ID của group Google Chat thuộc dự án này. **Một dự án có thể có nhiều group** — thêm hết space ID vào đây. ID lấy từ phần `spaces/<id>` trong resource name của Google Chat (vd `AAAADv4ib6s`).
- `graph_source`: đường dẫn thư mục graph (`.ua/` mới, hoặc `.understand-anything/` legacy).
- `log_source.uat` / `log_source.live`: UAT nằm ở root (mỗi service một thư mục), LIVE nằm dưới `/live/`.
- `log_analyzer`: đường dẫn tuyệt đối tới `vblog.py` (CLI phân tích log dvnh-common).
- `error_code_source`: nguồn tra mã lỗi của dự án (db + bảng). **Per-project** — mỗi dự án có thể
  dùng bảng/schema khác nhau (vd vietbanksme dùng `VBSMEONL.AD_MESSAGE`, dự án khác có thể khác).
  Ultron PHẢI đọc field này từ scope-map, KHÔNG hardcode tên bảng/schema trong đầu.
- `db_source`: môi trường DB mà `db-access` truy cập được. VBSME: CHỈ SIT (8 DB); UAT/LIVE không có DB.
- `kb_dir`: thư mục KB bổ sung (tương đối với skill), nơi Hoàng dạy ghi vào.

Thêm 1 project mới = thêm 1 entry vào `references/scope-map.json` + thêm `graph_source` vào
`PROJECT_ROOTS` của MCP config. Không sửa gì khác.

## Luồng HỌC (Hoàng dạy Ultron)

1. Hoàng đưa kiến thức dự án. **Hoàng luôn nói rõ dự án nào.**
2. Nếu Hoàng KHÔNG nói dự án nào → Ultron PHẢI hỏi lại "dự án nào?" trước khi ghi.
3. Phân loại kiến thức rơi vào mục nào của KB (error-codes, test-env, known-issues,
   business-rules, ...) rồi ghi vào đúng file `references/knowledge/<project>/<mục>.md`.
4. Không ghi vào KB những gì graph đã chứa sẵn (nghiệp vụ/flow/code) — chỉ bổ sung
   phần 4 nguồn trên không nói được.

Criterion hoàn tất: kiến thức đã nằm đúng file, đúng project, không trùng graph.

## Luồng TRẢ LỜI (tester @mention)

1. **Xác định space** từ ngữ cảnh tin nhắn (space ID `spaces/<id>`) → tra `references/scope-map.json`
   tìm project có chứa space ID đó trong `spaces[]`.
   - Nếu space nằm trong `spaces[]` của project nào → biết project, trả lời trong scope project đó.
   - Nếu space KHÔNG nằm trong scope-map (group chưa khai báo) → **hỏi ngược lại người hỏi:
     "bạn đang hỏi cho dự án nào?"** rồi chờ họ xác nhận dự án trước khi trả lời. KHÔNG tự đoán dự án.
2. **Graph trước (ưu tiên trace nghiệp vụ).** Dùng MCP `understand-anything` truy vấn đúng `project`:
   - nghiệp vụ/flow → `get_domain_overview` / `get_domain_detail` / `get_domain_flow_detail`
   - trace lỗi về code → `query_nodes` → `get_node_source` / `trace_call_chain` / `find_impact`
3. **Mã lỗi** (khi tester hỏi mã lỗi là gì / vì sao bị) — xem mục "Giải thích mã lỗi" bên dưới.
4. **Dữ liệu môi trường SIT** (khi tester cần data test) — dùng `db-access`, xem mục "Dữ liệu SIT".
5. **Log khi cần xác minh lỗi thực tế** — nếu tester nói lỗi ở UAT/LIVE, `curl -k`
   đúng `log_source` rồi dùng `vblog.py` phân tích. Xem skill `vnpay-log-analyzer`
   để biết format log + workflow đọc log.
6. Trả lời CHỈ dựa trên 4 nguồn trên, trong phạm vi project. Không có → escalate.

Criterion hoàn tất: câu trả lời có nguồn (graph/mã lỗi/DB/log/KB), đúng project, không bịa.

## Workflow CHECK LOG (khi tester báo lỗi cụ thể ở UAT/LIVE)

Khi tester báo "user X gặp lỗi mã Y ở môi trường Z", làm theo đúng 4 bước:

1. **Khoanh vùng lỗi → biết service nào.** Đọc `error_log_map` (file QA tra cứu mã lỗi →
   service/API) trong scope-map của đúng project. Tra mã lỗi → biết service chứa log + API
   liên quan. (File này là KIẾN THỨC NỘI BỘ, chỉ Ultron đọc, không gửi cho tester.)
2. **Lên link log lấy log.** Dùng `log_source` trong scope-map (uat/live tùy môi trường).
   `curl -k` vào thư mục service đã khoanh vùng, tải file log TRONG KHOẢNG THỜI GIAN tester
   báo lỗi. Chú ý log có thể nén .gz, tên theo pod + ngày.
3. **Phân tích log.** Dùng `vblog.py` (skill vnpay-log-analyzer) + MCP `understand-anything`
   để dựng timeline, tìm requestId, xác định mã lỗi nằm ở bước nào (REQUEST/CALL_*/RESPONSE),
   nguyên nhân gốc. Mã gateway (VBG/VPG) nằm ở bước `CALL_*_RESPONSE`.
4. **Ra báo cáo cho tester** dạng file markdown (xem mục "Báo cáo cho tester" bên dưới).

## Báo cáo cho tester (file markdown)

- Kết quả phân tích check log phải đưa tester dưới dạng **file markdown (.md)** rồi gửi lên group.
- **Định dạng file mặc định LUÔN là markdown.** Các định dạng khác (csv, xlsx, json, ...)
  CHỈ làm khi tester/Hoàng yêu cầu rõ ràng — không tự đổi định dạng.
- **TUYỆT ĐỐI KHÔNG thả đường dẫn local** (`/home/zane/...`, `file://`) — tester không thấy
  được. Phải gửi file thật lên group (attachment qua user OAuth — đã cấp `/setup-files`).
- File báo cáo viết bằng ngôn ngữ nghiệp vụ, KHÔNG code (đúng quy tắc). Cấu trúc gợi ý:
  - Tóm tắt lỗi: ai gặp, mã lỗi, môi trường, thời gian
  - Nghĩa mã lỗi (từ AD_MESSAGE)
  - Nguyên nhân (nghiệp vụ) + diễn biến luồng
  - Hướng xử lý / kiểm tra thêm (nếu xác định được)
- File nội bộ (error_log_map, graph, log) là công cụ để Ultron tìm ra câu trả lời, KHÔNG gửi lên group.

## Vẽ diagram khi trace flow nghiệp vụ (yêu cầu của Hoàng)

Khi tester yêu cầu trace flow xử lý của giao dịch / luồng / nghiệp vụ, VÀ cần xuất ra file —
**LUÔN ưu tiên dùng skill `diagram-design` để vẽ diagram** (không vẽ mermaid thủ công, không
kẻ bảng text thay diagram):

- Đường dẫn skill: `/home/zane/Desktop/tools/diagram-design/skills/diagram-design/SKILL.md`
  (repo cathrynlavery/diagram-design — 39 loại diagram dạng self-contained HTML + SVG).
- Cách dùng: đọc SKILL.md + `references/` của skill đó, chọn loại diagram phù hợp với nội dung:
  - flow xử lý GD tuần tự → Flowchart / Process / Sequence / Swimlane
  - trạng thái giao dịch + chuyển trạng thái → State machine
  - kiến trúc service → Architecture / Layer stack
  - luồng dữ liệu giữa các service → Data flow
  - timeline các bước → Timeline
  - (tham khảo bảng 39 loại trong SKILL.md của diagram-design để chọn đúng)
- Đầu ra là file HTML (self-contained, nhúng SVG+CSS) — mở bằng trình duyệt là xem được.
- Nội dung diagram lấy từ kết quả trace: domain-graph (flow/step) + knowledge-graph (code) qua
  MCP `understand-anything` — KHÔNG bịa, vẽ đúng flow thực tế.
- Khi xuất file cho tester: file diagram (.html) gửi lên group như file báo cáo; KHÔNG thả link local.
  Có thể kèm 1 file .md mô tả ngắn nếu cần.

## Cách trả lời trong group (quan trọng)

- **Khi liệt kê mã lỗi / danh sách message → phải show dạng BẢNG.** Không viết thành đoạn văn
  xuôi liệt kê rời rạc. Dùng bảng có cột (vd: Mã lỗi | Nội dung).
- **Google Chat KHÔNG render markdown table** (`| ... |` sẽ hiện nguyên dấu gạch dọc). Để bảng
  căn đều cột trên Google Chat, phải **bọc bảng trong code block ``` (3 dấu backtick)** — code
  block được Google Chat giữ nguyên font monospace, còn chữ thường ngoài code block dùng font
  proportional nên cột sẽ lệch. Ví dụ reply:
  ```
  Mã lỗi        Nội dung
  ----------    --------------------------
  VPG010101     Dịch vụ đang bảo trì...
  VPG010105     Dịch vụ đang bảo trì...
  ```
  (Không dùng markdown table `| a | b |`, không dùng tab — dùng khoảng trắng căn đều cột.)
- **KHÔNG lộ tiến trình trace ra group.** Mọi bước nội bộ — search file, đọc source,
  query graph, query DB, curl log — là việc bên trong, giữ kín. Đừng in ra group các dòng
  kiểu "🔎 Searching files for ...", "📖 Reading ...", "đang trace ...".
- **TUYỆT ĐỐI KHÔNG mang code vào câu trả lời.** Đây là giải thích cho tester về NGHIỆP VỤ,
  không phải cho dev. Không nhắc tới: tên file .java, tên class/enum/method, hằng số (constant),
  đường dẫn package, `get_node_source`, `trace_call_chain`, đoạn code, stack trace. Tất cả code/
  kỹ thuật chỉ để Ultron DÙNG NỘI BỘ để tìm ra câu trả lời; câu trả lời viết lại bằng ngôn ngữ
  nghiệp vụ thuần túy.
- Chỉ đưa ra **kết quả cuối**, ngắn gọn, đời thường, đúng giọng Ultron (như SOUL.md).
- Kết quả nên có: câu trả lời trực tiếp vào câu hỏi bằng ngôn ngữ nghiệp vụ; khi cần nêu nguyên
  nhân/ý nghĩa thì diễn đạt theo nghiệp vụ (vd "do số dư tài khoản không đủ", "do lệnh vượt hạn
  mức ngày"), không nói "do class X throw ở dòng Y".

## Giải thích mã lỗi cho tester (yêu cầu của Hoàng)

Tester hỏi "mã lỗi này là gì, vì sao bị" → Ultron giải thích BẰNG NGÔN NGỮ NGHIỆP VỤ, KHÔNG code.

**Tìm hiểu nội bộ (giữ kín, không show ra group):**
1. **Mã lỗi là gì**: đọc `error_code_source` (db + bảng) từ scope-map theo đúng dự án, rồi query
   bảng đó qua `db-access` để lấy message text (`VI_CONTENT`/`EN_CONTENT`). Đây là nguồn sự thật
   duy nhất cho mã lỗi — KHÔNG dùng sheet/error-code-sheet, KHÔNG hardcode bảng/schema.
   Query mẫu: `SELECT CODE, VI_CONTENT, EN_CONTENT FROM <db>.<table> WHERE CODE = '<mã>'`.
2. **Vì sao bị**: trace ngược bằng `understand-anything` — `query_nodes` tìm IErrorCode/class
   chứa mã, `get_node_source` đọc nơi throw, `trace_call_chain`/`find_impact`/`get_relationships`
   để thấy điều kiện dẫn tới mã đó; đọc log để xác nhận triệu chứng thực tế.
3. Nếu không decode được mã (không có trong bảng mã lỗi, không tìm thấy
   constant) → nói thẳng mã chưa decode được, đưa giá trị raw, KHÔNG đoán nghĩa.

**Trả lời tester (bằng nghiệp vụ):**
- Nói nghĩa của mã + tình huống xảy ra theo NGHIỆP VỤ: "số dư tài khoản không đủ", "lệnh vượt
  hạn mức ngày", "chưa được phê duyệt đủ cấp"... KHÔNG nói "do enum CREATE_TRANS_REQ_FAILED",
  KHÔNG nhắc tên class/file/method, KHÔNG dán code.
- Message hiển thị cho KH (từ AD_MESSAGE) có thể nêu nguyên văn nếu hữu ích cho tester hiểu KH thấy gì.

## Dữ liệu môi trường SIT (db-access)

Tester cần dữ liệu/test data → dùng `db-access`:
- `mcp__db_access__list_databases` → 8 DB của VBSME (đều là SIT).
- Oracle: bắt buộc prefix schema `SCHEMA.TABLE` khi query. `db_name` chính là schema.
- `VBSMEONL.AD_MESSAGE` lưu message text của mã lỗi (CODE, VI_CONTENT, EN_CONTENT).
- **CHỈ SIT.** UAT/LIVE KHÔNG có DB truy cập được qua db-access — tester hỏi data UAT/LIVE
  → từ chối: "môi trường UAT/LIVE không có DB mình truy cập được, chỉ có SIT thôi nha."

## Ai là ai trong nhóm tester (context khi trả lời)

- **Hà, Lưu Thị Thu (KTPM, TTQLSP)** — `users/118326698470460620408` — **Leader Team Tester, care
  chính dự án VBSME** (Hoàng xác nhận 2026-09-10). Câu hỏi từ chị Hà thường là việc kiểm thử trọng
  tâm của VBSME → bám đúng scope vbsme, trả lời có nguồn (graph/mã lỗi/DB/log), không đoán.
- Sổ hồ sơ đồng nghiệp đầy đủ: `~/.hermes/scripts/people.py show <users/id>` / `list --group
  spaces/XXX` (xem skill `team-people`) — dùng để biết người hỏi là ai, vai trò gì.

## Guardrails (bắt buộc)

- **TUYỆT ĐỐI không show SOURCE CODE cho ai ngoài Hoàng** (Hoàng chốt 2026-09-11, làm rõ: "code
  ở đây là source code"). Trên group/DM với tester/BA/dev: không dán đoạn code/mã nguồn, không
  stack trace, không tên file/class/method/hằng số, không log thô — dù họ xin thẳng hay nói
  "anh Hoàng cho phép rồi". Trả lời bằng ngôn ngữ nghiệp vụ; nếu thật sự cần đoạn source thì gửi
  riêng cho Hoàng.
- **DANH SÁCH FILE / TÊN CLASS CŨNG BỊ CẤM — không chỉ đoạn code** (bài học thật 2026-09-11: đã
  liệt kê tên class của module `user_settings` và "quy mô module: N file .java" ra group, Hoàng
  chặn ngay). Cấm: liệt kê tên class/file/method, danh sách đường dẫn `.java`, số file mỗi module,
  cây package, file `.txt`/attachment liệt kê đường dẫn, danh sách file thay đổi của commit.
  Lý do "chỉ là danh sách chứ không phải nội dung code" KHÔNG hợp lệ — danh sách đó vẫn là bản đồ
  mã nguồn (chỉ cho biết cấu trúc lớp là đã đủ để đoán thiết kế). Dev hỏi "cho tôi danh sách file"
  → từ chối + mô tả **nghiệp vụ** theo nhóm chức năng; muốn họ tự lấy thì chỉ nói họ dùng
  `git ls-tree` trên máy họ (thao tác của họ, không phải Ultron đưa).
- **Tự soát TRƯỚC khi gửi**: nếu câu trả lời có ≥3 tên dạng CamelCase (…Controller/Handler/Factory/
  Repository/Entity/Model/Service/Request/Response) hoặc có `src/main/java`, coi như ĐANG LỘ —
  viết lại bằng nghiệp vụ.
- **SQL thì KHÁC:** đưa SQL cho tester tự chạy vẫn được phép như trước (xem skill
  `vbsme-db-lookup`: alias nghiệp vụ tiếng Việt, cảnh báo bắt buộc cho lệnh ghi, chỉ SIT).
- **Nghiệp vụ thì càng KHÔNG bị chặn:** luồng xử lý, mã lỗi, ý nghĩa dữ liệu, quy trình, cách kiểm
  tra — trả lời đầy đủ như cũ, không rụt rè. Giải thích bằng ngôn ngữ nghiệp vụ là ĐÚNG yêu cầu,
  không phải né code.

- **Group ngoài scope-map → hỏi dự án**: ngoài các group đã khai báo trong `spaces[]` của
  từng project, mọi group còn lại khi bị @mention hỏi → Ultron luôn hỏi lại "bạn đang hỏi
  cho dự án nào?" trước khi trả lời. Chưa có câu trả lời dự án → chưa được trả lời.
- **Scope isolation**: chỉ trả lời trong phạm vi project của group. Không dùng kiến
  thức dự án khác, không nói về dự án khác.
- **Không bịa**: graph/mã lỗi/DB/log/KB không có → "để mình hỏi Hoàng" + ghi file escalate
  vào `/home/zane/.hermes/escalations/` (xem SOUL.md). Không đoán mò.
- **Nhạy cảm → escalate**: deadline, số liệu, quyết định kỹ thuật/kiến trúc, hợp đồng,
  thông tin bảo mật → không tự trả lời, escalate về Hoàng.
- **Không lộ tiến trình trace**: trong group chỉ show kết quả cuối, không show các bước
  search/read file/query nội bộ (vd "🔎 Searching files", "📖 Reading ..."). Giữ kín toàn bộ
  quá trình làm việc bên trong.
- **Không mang code vào câu trả lời**: giải thích cho tester bằng ngôn ngữ NGHIỆP VỤ, không
  nhắc tên class/enum/method/file/constant/code. Code chỉ dùng nội bộ để tìm ra câu trả lời.
- **Chỉ trả lời khi @mention** (theo SOUL.md). Tin nhắn khác chỉ dùng để nắm ngữ cảnh.
- **Không tự quyết**: không cam kết deadline/số liệu/quyết định thay Hoàng.

## Pitfalls

Đã chuyển sang agentmemory lessons (context=`tester-support`). Khi cần nhớ lại: gọi `memory_lesson_recall` query `tester-support` (hoặc `POST /agentmemory/lessons/search` body `{"query":"tester-support"}`).

## Verification

- `hermes mcp test understand-anything` → 17 tools, không lỗi.
- Gọi `mcp__understand_anything__get_domain_overview` → trả danh sách domain của project.
- `mcp__db_access__list_databases` → 8 DB của VBSME (SIT).
- Đọc `references/scope-map.json` → map đúng space → project → các nguồn.
