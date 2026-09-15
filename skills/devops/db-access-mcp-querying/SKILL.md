---
name: db-access-mcp-querying
description: "Use when querying DBs via the db-access MCP tools."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [db-access, mcp, oracle, mongodb, sql, query, diagnosis]
    related_skills: [vbsme-db-lookup, tester-support]
---

# Querying databases through the db-access MCP tools

Cách query đúng và nhanh qua `mcp__db_access__*` — áp cho mọi dự án dùng tool này
(VBSME và các dự án sau). Quy trình ghi DB (chỉ SIT, preview→token→xác nhận) nằm ở SOUL.md;
skill này lo phần **query sao cho ra kết quả đúng ngay lần đầu**.

## Bộ tool

| Việc | Tool |
|---|---|
| Xem DB được phép truy cập + quyền | `list_databases` |
| Liệt kê bảng / cột / khoá | `sql_list_tables`, `sql_get_columns`, `sql_get_constraints` |
| Đọc dữ liệu (SELECT) | `sql_read` |
| Ghi (INSERT/UPDATE/DELETE) | `sql_write` (2 bước, có `confirmation_token`). ⚠️ Bước preview **KHÔNG validate SQL**: câu sai hẳn tên cột vẫn trả `success: PREVIEW` + `shadow_preview: []` ⇒ "preview OK" KHÔNG chứng minh cú pháp/tên cột đúng. Muốn chắc, đối chiếu tên cột/bảng bằng `SYS.USER_TAB_COLUMNS` (hoặc `sql_get_columns`) trước khi tin script. |
| Script SQL | `sql_execute_script` — **không dùng cho DDL**, xem SOUL.md |
| Mongo | `mongo_list_collections`, `mongo_get_schema`, `mongo_read`, `mongo_write` |

## Quyền truy cập: theo SOURCE (apiKey), không phải theo connection

- Cổng là MCP HTTP ở `127.0.0.1:8443/mcp`, chạy bằng **user unit** `mcp-db-tools`,
  config `~/Desktop/tools/mcp/Db-Access/config.yaml` (block `databases:` = connection thật,
  block `sources:` = apiKey + `access:` db → `[read|write]`).
- Host trong `databases:` là `127.0.0.1:<port>` **qua SSH tunnel** (user unit `mcp-db-tunnel`) ⇒ lỗi
  `NJS-503 / ECONNREFUSED 127.0.0.1:<port>` là lỗi TẦNG TUNNEL/MẠNG, khác hẳn lỗi thiếu quyền — xem
  bảng phân biệt 3 lớp lỗi trong `references/db-access-gateway-access-model.md` trước khi đi xin quyền.
- `list_databases` CHỈ trả về DB mà **key đang dùng** được cấp ⇒ thấy ít DB không có nghĩa cổng
  thiếu connection.
- `Database '<X>' not found or access denied` = key của mình chưa được cấp `<X>`. Đọc block
  `sources:` trong config trước khi kết luận "chưa khai báo" — connection của DB đó có thể đã có sẵn
  cho source khác.
- Thêm DB cho một source: **không tự sửa** `config.yaml` của Db-Access, **không tự restart**
  `mcp-db-tools` (kể cả user unit không cần sudo) ⇒ xin Hoàng cho phép → chạy
  `python3 ~/.hermes/scripts/claude_mcp_preflight.py` → giao Jarvis sửa (backup + diff + giữ đúng
  read/write).
- **DB cần mở chưa có entry connection: kiểm TỒN TẠI trước khi xin thông tin kết nối.** Nhiều DB của
  cùng một dự án nằm chung **một Oracle instance** (mỗi schema một user, cùng host/port/service).
  Từ connection của DB anh em trong cùng instance, chạy
  `SELECT COUNT(*) FROM SYS.ALL_USERS WHERE USERNAME='<SCHEMA_CAN_MO>'` — 1 = schema có thật ⇒ chỉ cần
  thêm entry **mirror đúng cấu trúc entry anh em** (cùng host/port/service, user/pass theo pattern
  biến môi trường hiện hành); không phải hỏi host/port. Chỉ hỏi Hoàng khi instance/credential khác hẳn.
  KHÔNG tự bịa host/user.

### Pitfall: session MCP đang mở giữ SNAPSHOT quyền cũ

Server TỰ hot-reload config (`fs.watchFile(CONFIG, {interval:1000})` → `dotenv.config({override})` +
reloadConfig) nên sửa config **không cần restart service** — NHƯNG session MCP đã mở giữ quyền chụp
lúc nó khởi tạo:

- Quyền mới chỉ có hiệu lực ở **session MCP MỚI**; phiên Hermes đang chạy vẫn thấy danh sách DB cũ
  ⇒ cần khởi động lại gateway (Ultron không tự restart gateway từ trong) hoặc mở session mới.
- Cần tra NGAY mà chưa restart: gọi thẳng cổng bằng key của source đã có quyền — dùng
  `scripts/mcp_direct_query.py` (đừng tự gõ tay JSON-RPC).
- Verify thay đổi quyền bằng chính key của mình (`list_databases`), đừng tin báo cáo "đã thêm quyền"
  của agent đã sửa.

## Luật query (mỗi luật là một lần mất thời gian thật)

1. **Mỗi `db_name` là MỘT connection/user riêng ⇒ không join chéo schema của DB khác.**
   `db_name=VBSMEFACE` mà SQL có `VBSMEONL.OMNI_CUSTOMER` → `ORA-01031`. Cách làm đúng:
   query từng DB riêng lấy khoá chung (CIF / trace / id / ngày), rồi ghép bằng script Python.
2. **Luôn prefix `SCHEMA.TABLE`** và truyền `db_name=<SCHEMA>` khớp với tiền tố đó.
3. **Khám phá cấu trúc trước khi query** — `sql_get_columns(db_name, table)` cho cột + comment.
   Với schema khác: `SELECT TABLE_NAME FROM SYS.ALL_TABLES WHERE OWNER='<SCHEMA>'`,
   `SELECT COLUMN_NAME FROM SYS.ALL_TAB_COLUMNS WHERE OWNER='<SCHEMA>' AND TABLE_NAME='<TABLE>'`.
4. **Kiểm kiểu dữ liệu trước khi so sánh số.** Cột "trông như số" nhưng là VARCHAR2 (vd cột `AMOUNT`
   của bảng request) → `AMOUNT > 0` lỗi `ORA-01722`; dùng `AMOUNT <> '0'`, hoặc lọc rỗng rồi `TO_NUMBER`.
5. **Cột trùng từ khoá Oracle (vd `LEVEL`) phải BỌC NHÁY KÉP** — `"LEVEL"`; để trần trong SELECT list → `ORA-01747`, để trần trong danh sách cột của INSERT → `ORA-01788`. Bọc nháy thì SELECT/INSERT đều chạy bình thường ⇒ **đừng bỏ cột** khi câu lệnh buộc phải đủ cột (vd `INSERT ... SELECT` để move bản ghi).
5b. **Không query được metadata hệ thống khi chưa prefix schema** — `SYS.ALL_TABLES`, `SYS.ALL_USERS`,
   `SYS.ALL_TAB_COLUMNS` mới chạy; viết trần `ALL_TABLES` bị chặn với lỗi "Rule Violation: Table ...
   is missing a schema prefix". Đây là công cụ hữu ích nhất để kiểm tồn tại schema/bảng/cột khi chưa có grant.
6. **Đừng kết luận từ một cột status số.** Enum trong source có thể khác dữ liệu môi trường đang chạy.
   Trình bày *giá trị thực + khác biệt giữa các bản ghi đối chứng*, đánh dấu chỗ chưa kiểm chứng.
7. **`ORA-00942` khi query chéo schema KHÔNG chứng minh bảng/schema không tồn tại** — thiếu quyền
   trên bảng của schema khác cũng trả về đúng mã 942 này. Muốn biết có thật hay không thì tra metadata
   `SYS.ALL_USERS` / `SYS.ALL_TABLES WHERE OWNER='<SCHEMA>'` (chạy được cả khi chưa có grant), rồi mới
   kết luận.
8. **Một dự án có thể có nhiều schema, và không phải schema nào cũng đủ bảng.** Trước khi nhận tra một
   loại dữ liệu (mã lỗi, nhật ký, giao dịch) cho một schema mới, liệt kê bảng của nó
   (`SYS.ALL_TABLES WHERE OWNER='<SCHEMA>'`) — bảng chuyên biệt (vd bảng mã lỗi) thường chỉ nằm ở
   schema ONL; nói "tra được" khi chưa kiểm dễ phải rút lại trước mặt tester.
9. **`sql_write` preview KHÔNG phải máy kiểm cú pháp.** Preview chỉ phân loại "đây là câu ghi" + liệt kê dòng
   sẽ đổi: một câu cố tình sai tên cột vẫn trả `success: PREVIEW` với `shadow_preview: []` (đã kiểm bằng câu
   đối chứng) ⇒ **`shadow_preview: []` nghĩa là "0 dòng / không rõ", KHÔNG phải "câu lệnh hợp lệ"**. Trước khi
   soạn hay gửi đi một câu UPDATE/INSERT, đối chiếu **từng bảng/cột** với catalog (`sql_get_columns`, hoặc 1 câu
   `SYS.ALL_TAB_COLUMNS`), và kiểm chứng câu SELECT tương ứng bằng `sql_read` trên DB test.

## Sửa trạng thái LỆCH giữa bảng nghiệp vụ và bảng yêu cầu duyệt

Yêu cầu kiểu *"các bản ghi bị mất đồng bộ, đưa trạng thái về huỷ giúp"* là **fix dữ liệu** — đừng đoán một
cột status, phải bám đúng luồng huỷ của app:

1. **Định nghĩa "lệch" bằng truy vấn, không bằng cảm giác.** Cha giữ trạng thái "chờ duyệt" nhưng khoá trỏ tới
   bảng yêu cầu đang mở không còn ở đó:
   `WHERE t.STATUS = <chờ duyệt> AND t.REQ_ID IS NOT NULL AND NOT EXISTS (SELECT 1 FROM <SCHEMA>.<ACTIVE_REQ> a WHERE a.ID = t.REQ_ID)`.
   Đếm riêng nhóm `REQ_ID IS NULL` (loại khác, đừng gộp vào cùng một UPDATE).
2. **Đọc luồng huỷ trong source để lấy ĐÚNG tập cột/bản ghi con phải đổi** (thường: cha → trạng thái đã huỷ,
   toàn bộ bản ghi con → đã huỷ, đôi khi cả giao dịch gốc + dòng phase). Chỉ đổi status của cha là tạo ra lệch thứ hai.
3. **Đo ảnh hưởng bằng chính câu SELECT đó trên DB test** (số dòng + vài dòng đầu): vừa là con số để trình người
   ra lệnh, vừa là cách duy nhất kiểm chứng câu lệnh chạy được (luật 9).
4. **DB đích không có entry trong `list_databases`** (UAT/LIVE) ⇒ sản phẩm giao đi là **file script**, không phải
   lệnh chạy: báo cáo trước → backup → update → kiểm chứng lại, mỗi bước COMMIT riêng. Phải nói rõ phần nào đã
   chạy thật ở môi trường nào, phần nào chưa từng chạy — không trình bày như đã kiểm chứng trên môi trường đích.
5. **Backup trước khi UPDATE và lấy danh sách ID của bước update TỪ chính bảng backup** — sau khi cha đổi trạng
   thái, tiêu chí "đang chờ duyệt" không tìm lại được chúng nữa. Số dòng update phải khớp số dòng backup (để còn
   cửa ROLLBACK nếu lệch).
6. **Bẫy cú pháp Oracle khi viết script cho người khác chạy:**
   - Không định danh alias ở vế trái `SET` — viết `SET STATUS = ...`, không `SET t.STATUS = ...`; alias chỉ để trong `WHERE`.
   - Tên bảng backup ≤ 30 ký tự (nối hậu tố ngày vào tên bảng gốc rất dễ vượt) ⇒ viết tắt tiền tố.
   - Để `COMMIT` là lệnh RIÊNG sau khối PL/SQL, sau khi đã in số dòng đã update.

## Bằng chứng từ sự VẮNG MẶT bản ghi (pattern dùng nhiều lần)

Muốn biết "hệ thống có thực sự gọi sang dịch vụ ngoài không?": tra bảng request/nhật ký của dịch vụ
đó theo đúng khoá + đúng ngày.

- **Bảng ghi cả lượt thất bại** (`IS_SUCCESS=0` + mã lỗi) ⇒ ngày lỗi trống bản ghi (mà ngày khác có)
  chứng minh **lượt gọi đó chưa từng xảy ra** ⇒ chỗ chặn nằm ở phía trước, không phải lỗi do dịch vụ
  ngoài trả về. Đây là kết luận mạnh, dùng được trong báo cáo.
- **Điều kiện hợp lệ:** bảng phải còn "sống" cho mốc thời gian đó. Kiểm `MAX(<cột thời gian>)` hoặc
  query vài ngày lân cận TRƯỚC khi nói "không có bản ghi" — bảng nhật ký ngừng cập nhật sẽ cho kết
  luận sai ("không gọi" trong khi thực tế là "bảng không ghi nữa").
- Bản ghi nhật ký ghi cả lượt fail thường có cột mã lỗi (`LIST_ERROR_CODE`, `ERROR_CODE`) — đọc cột
  đó trước khi kết luận bước nào hỏng.

## Chẩn đoán nhiều tầng dữ liệu (dữ liệu vs trạng thái bản sao)

Hệ thống thật hay có **cùng một sự thật được lưu ở 2–3 nơi**: dữ liệu gốc của dịch vụ chuyên trách,
bản sao/trạng thái trong hệ thống nghiệp vụ, và nhật ký gọi dịch vụ. Khi một luồng bị chặn:

1. Xác định tầng nào đang bị chất vấn (tầng kiểm điều kiện ≠ tầng chứa dữ liệu).
2. Query **tất cả** các tầng của đúng đối tượng (khoá chung) rồi **so với các bản ghi đối chứng**
   (cùng công ty / cùng cấp duyệt / cùng loại) — khác biệt giữa các đối tượng là manh mối rõ nhất.
3. Kiểm cả nhật ký đồng bộ giữa các tầng (trạng thái xác thực dân cư, cờ synced...) trước khi kết luận
   "dữ liệu còn hạn nên không thể lỗi".

## Move bản ghi giữa bảng gốc và bảng `_CANCEL` (sửa bản ghi kẹt)

Yêu cầu kiểu "bản ghi này bị kẹt, move nó xuống bảng CANCEL giúp" là **sửa dữ liệu thuần** —
nguồn sự thật nằm ở dữ liệu, không phải source code:

1. **Lấy mẫu từ bản ghi ĐỐI CHỨNG đã move xong; đừng đoán, đừng giao khảo sát source code.**
   Tìm bản ghi cùng CIF/cùng công ty đã nằm trong bảng `_CANCEL` → đọc trạng thái đích thật
   (giá trị status, có mang bản ghi con theo không, ID có giữ nguyên không). Mẫu thật nhanh và
   đúng hơn suy luận từ code; giao Jarvis khảo sát source cho việc này chỉ tốn thời gian.
2. **Bảng `_CANCEL` thường THIẾU vài cột so với bảng gốc** → `INSERT ... SELECT *` chết vì lệch số cột.
   Lấy danh sách cột gọn rồi tự tính phần giao:
   `SELECT TABLE_NAME, LISTAGG(COLUMN_NAME, ',') WITHIN GROUP (ORDER BY COLUMN_ID) AS COLS FROM SYS.ALL_TAB_COLUMNS WHERE OWNER='<SCHEMA>' AND TABLE_NAME IN (...) GROUP BY TABLE_NAME`.
3. **Rà mọi bảng có thể đang giữ bản ghi con**:
   `SELECT TABLE_NAME, COLUMN_NAME FROM SYS.ALL_TAB_COLUMNS WHERE OWNER='<SCHEMA>' AND COLUMN_NAME IN ('CUSTOMER_ID','USER_ID')`.
4. **Thứ tự bắt buộc: INSERT vào bảng `_CANCEL` trước → verify → mới DELETE ở bảng gốc.**
   Đứt giữa 2 bước thì còn bản sao (dọn lại được); làm ngược là mất dữ liệu thật.
5. **Preview/token theo TỪNG câu lệnh** (token dùng một lần): move 4 câu = 4 cặp preview/execute.
   Preview của INSERT trả `"Preview not available for this operation"` ⇒ **đo ảnh hưởng bằng preview
   của chính câu DELETE tương ứng** (nó liệt kê đúng các dòng sẽ mất) + `COUNT(*)` hai bên, rồi trình
   đúng số dòng đó cho người ra lệnh.
6. **Trình kế hoạch dạng bảng (bảng nào · việc gì · mấy dòng) + cảnh báo không hoàn tác + xin xác nhận rõ.**
   Nếu bản ghi lỗi có giá trị bất thường (vd status NULL) → hỏi **đúng 1 câu**: giữ nguyên hay set về
   giá trị chuẩn như mẫu; KHÔNG tự chọn thay người ra lệnh.

## Tham chiếu theo dự án

- `references/vbsme-cancel-record-move.md` — ca huỷ khách hàng kẹt ở VBSME: cặp bảng gốc ↔ `_CANCEL`,
  dấu hiệu nhận dạng bản ghi kẹt, cột bị thiếu, mẫu đối chứng.
- `templates/vbsme-move-customer-to-cancel.sql` — câu lệnh mẫu điền sẵn theo đúng thứ tự an toàn.
- `references/vbsme-collect-biometric-tables.md` — bảng + luồng chẩn đoán khi lệnh duyệt bị chặn vì
  "chưa / hết hạn thu thập sinh trắc" (SME ⋈ eKYC ⋈ FacePay).
- `references/vbsme-batch-payroll-status-sync.md` — VBSME: cặp bảng lô/lương ↔ bảng yêu cầu duyệt, giá trị
  trạng thái số, điều kiện "lệch", luồng huỷ thật của app và script dọn dữ liệu kèm theo.
- Dự án VBSME: bảng/cột đầy đủ + quy trình gửi SQL cho tester → skill `vbsme-db-lookup`.
- Cổng DB: source/quyền/snapshot + cách tra trực tiếp → `references/db-access-gateway-access-model.md`
  và `scripts/mcp_direct_query.py`.
