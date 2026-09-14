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
| Ghi (INSERT/UPDATE/DELETE) | `sql_write` (2 bước, có `confirmation_token`) |
| Script SQL | `sql_execute_script` — **không dùng cho DDL**, xem SOUL.md |
| Mongo | `mongo_list_collections`, `mongo_get_schema`, `mongo_read`, `mongo_write` |

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
6. **Đừng kết luận từ một cột status số.** Enum trong source có thể khác dữ liệu môi trường đang chạy.
   Trình bày *giá trị thực + khác biệt giữa các bản ghi đối chứng*, đánh dấu chỗ chưa kiểm chứng.

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
- Dự án VBSME: bảng/cột đầy đủ + quy trình gửi SQL cho tester → skill `vbsme-db-lookup`.
