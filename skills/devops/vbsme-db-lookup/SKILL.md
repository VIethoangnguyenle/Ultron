---
name: vbsme-db-lookup
description: "Use when testers ask to inspect vbsme DB data/meaning."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vbsme, vietbank, oracle, database, tester, lookup]
    related_skills: [agy-orchestration]
---

# vbsme DB lookup (VietBank SME)

Help testers inspect transaction/customer data in the VietBank SME databases. Query via the `db-access` MCP tools (`mcp__db_access__sql_read`, `sql_get_columns`, `list_databases`).

## Databases (8)

| DB | Type | Purpose |
|---|---|---|
| `VBSMEONL` | Oracle | Main business data (210 tables) — transactions, customers |
| `VBSMEOFF` | Oracle | Archive/offline (21 tables) |
| `VBSMERLE` | Oracle | RLE trans_rule |
| `VBSMESOTP` | Oracle | Soft OTP |
| `VBSMEFACE` | Oracle | FacePay |
| `VBSMEEKYC` | Oracle | eKYC |
| `VBEKYCSTORAGE` | Oracle | eKYC storage |
| `VBSMELOGS` | Mongo | Centralized logs |

**Transactions/customers → `VBSMEONL` (tables `OMNI_*`).**

## Oracle rules (critical)

- **MUST prefix every table with its schema** in SQL: `SELECT ... FROM VBSMEONL.OMNI_CUSTOMER`. Querying without a schema is blocked.
- `db_name` in `sql_read` IS the connection/schema — to read schema X pass `db_name=X`, not another DB with `X.` in SQL. But the SQL still needs the `SCHEMA.TABLE` prefix (e.g. `VBSMEONL.OMNI_CUSTOMER`).
- Read-only on `VBSMERLE`, `VBSMESOTP`, `VBSMEFACE`, `VBSMEEKYC`, `VBEKYCSTORAGE`, `VBSMELOGS`. Read+write only on `VBSMEONL`, `VBSMEOFF`.
- Discover schema first with `sql_get_columns(db_name, table_name)` before querying — column names + comments are there.

## Table prefixes

- `AD_*` = catalog/config (AD_SERVICE, AD_MESSAGE error codes, AD_BENE_BANK)
- `BO_*` = back office
- `OMNI_*` = core business (OMNI_TRANSACTION, OMNI_CUSTOMER, OMNI_TRANSACTION_PHASE)
- Suffixes: `_TEMP` pending, `_CANCEL` cancelled, `_HIS`/`_HISTORY` history, `_BK` backup, `_MIGRATED` migrated

## Key status mapping (source: TransactionStatus.java / TransactionPhase.java)

`OMNI_TRANSACTION.STATUS` (integer):
0=INIT_REQUEST, 1=PENDING_APPROVED, 2=APPROVING, 3=TRANSACTION_SUCCESS, 4=TRANSACTION_FAILED, 5=TRANSACTION_TIMEOUT, 6=TRANSACTION_PENDING, 7=TRANSACTION_REJECTED, 8=INIT_REQUEST_FAILED, 9=TRANSACTION_REVERT_FAILED, 10=TRANSACTION_REVERT_TIMEOUT, 11=TRANSACTION_PENDING_PROCESS, 12=TRANSACTION_CANCELED, 14=CANCEL_TRANSACTION_FAILED (13 skipped).

`OMNI_TRANSACTION_PHASE` = child table logging each step (init→approve→hạch toán→hậu GD); join on transaction id. To answer "where is this txn stuck", read its latest phase.

`OMNI_CUSTOMER` key columns: USERNAME/USER_ALIAS, FULL_NAME, MOBILE_OTT (OTT notify phone), MOBILE_OTP, EMAIL, CIF_NO, ACCOUNT_NO, COMPANY_ID, REPRESENT (1=legal rep), IS_ADMIN (1=admin), STATUS, CHANNEL (0=SME, 1=migrate), SOTP_STATUS (0 inactive/1 active/2 pending/3 lock/4 cancelled), CARD_NUMBER, CARD_TYPE.

`OMNI_CUSTOMER.STATUS` = CustomerStatus: 0=NONE, 1=INIT, 2=PENDING_APPROVE_REGISTER, 3=ACTIVE_STANDBY, 4=ACTIVE, 5=LOCK, 6=PENDING_LOCK, 7=PENDING_UNLOCK, 8=AUTO_LOCK, 9=TEMP_LOCK, 10=PENDING_UPDATE, 11=PENDING_APPROVAL_RESET_PASSWORD, 12=PENDING_RESEND_USERNAME, 13=PENDING_CANCEL, 14=CANCEL.

## Hạn mức (limit) — "hạn mức lập lệnh"

Tester hay hỏi "kiểm tra hạn mức lập lệnh của user X theo loại dịch vụ Y ngày Z". Ba bảng liên quan (đã kiểm chứng trên SIT 2026-09-12):

| Bảng | Cấp | Khoá | Ý nghĩa cột |
|---|---|---|---|
| `AD_PACKAGE_SERVICE_TYPE_LIMIT` | Gói dịch vụ | PACKAGE_CODE + SERVICE_TYPE_CODE + CCY | `DAILY_CUS_TRANS_REQ_AMOUNT_LIMIT` = hạn mức lập lệnh tối đa của **nhân viên/ngày**; `DAILY_AMOUNT_LIMIT` = tổng tiền GD tối đa/ngày của DN theo loại dịch vụ |
| `OMNI_DAILY_TRANS_REQ_LIMIT` | Doanh nghiệp | COMPANY_ID + SERVICE_TYPE_CODE + CCY + PACKAGE_CODE | `AMOUNT`/`MAX_AMOUNT` = hạn mức lập lệnh theo ngày (snapshot sinh ra từ gói) |
| `OMNI_DAILY_CUS_TRANS_REQ_CHECK` | Nhân viên | CUSTOMER_ID + SERVICE_TYPE_CODE + CHECKED_DATE | `NUMBER_OF_TRANS_REQ` = số lệnh đã lập trong ngày; `AMOUNT` = số tiền đã lập trong ngày — dùng để đối chiếu với hạn mức |

- `OMNI_CUSTOMER.PACKAGE_CODE` thường NULL → gói lấy từ `OMNI_COMPANY.PACKAGE_CODE` của `CUSTOMER.COMPANY_ID`.
- Lọc cấu hình gói: `IS_ACTIVE = 1 AND STATUS = 1 AND CCY = 'VND'` (có thể tồn tại bản ghi cũ IS_ACTIVE=0 cùng khoá — nhớ lọc, không thì ra 2 dòng).
- `CHECKED_DATE` là kiểu DATE → lọc `TRUNC(CHECKED_DATE) = DATE 'YYYY-MM-DD'`.
- Bản ghi cấp doanh nghiệp cho một loại dịch vụ có thể **chưa tồn tại** (NULL) — khi đó nói rõ với tester là chưa khởi tạo, không kết luận lỗi.
- Mã loại dịch vụ (`AD_SERVICE_TYPE.CODE`): 001 Tài khoản, 002 Chuyển khoản, 003 Gửi tiền tiết kiệm, 004 Thanh toán hoá đơn.

Query mẫu (hạn mức lập lệnh + đã dùng + còn lại theo user/loại dịch vụ/ngày):

```sql
SELECT c.USERNAME AS "Tên đăng nhập", c.FULL_NAME AS "Nhân viên",
       co.VN_NAME AS "Doanh nghiệp", co.PACKAGE_CODE AS "Gói dịch vụ",
       st.CODE || ' - ' || st.VI_NAME AS "Loại dịch vụ",
       pkg.DAILY_CUS_TRANS_REQ_AMOUNT_LIMIT AS "Hạn mức lập lệnh ngày (nhân viên)",
       NVL(u.AMOUNT, 0) AS "Đã lập lệnh trong ngày",
       NVL(u.NUMBER_OF_TRANS_REQ, 0) AS "Số lệnh đã lập trong ngày",
       pkg.DAILY_CUS_TRANS_REQ_AMOUNT_LIMIT - NVL(u.AMOUNT, 0) AS "Hạn mức còn lại"
FROM VBSMEONL.OMNI_CUSTOMER c
JOIN VBSMEONL.OMNI_COMPANY co ON co.ID = c.COMPANY_ID
LEFT JOIN VBSMEONL.AD_SERVICE_TYPE st ON st.CODE = '002'
LEFT JOIN VBSMEONL.AD_PACKAGE_SERVICE_TYPE_LIMIT pkg
       ON pkg.PACKAGE_CODE = co.PACKAGE_CODE AND pkg.SERVICE_TYPE_CODE = '002'
      AND pkg.CCY = 'VND' AND pkg.IS_ACTIVE = 1 AND pkg.STATUS = 1
LEFT JOIN VBSMEONL.OMNI_DAILY_CUS_TRANS_REQ_CHECK u
       ON u.CUSTOMER_ID = c.ID AND u.SERVICE_TYPE_CODE = '002'
      AND TRUNC(u.CHECKED_DATE) = DATE '2026-09-12'
WHERE UPPER(c.USERNAME) = UPPER('facepay47');
```

## Kho STH (kho kết quả thu thập sinh trắc học) — `VBEKYCSTORAGE.SUCCESS_COLLECT`

Màn "Danh sách kho STH" (lọc CIF / số giấy tờ / tên KH / CN-PGD / kênh thu thập / dịch vụ / khoảng ngày) đọc từ `SUCCESS_COLLECT` — **khoá chính = `CIF`, mỗi CIF đúng 1 dòng** (lần thu thập sinh trắc học đang hiệu lực). Kiểm chứng SIT 2026-09-14.

| Cột | Ý nghĩa |
|---|---|
| `TYPE` / `ID_NUMBER` | loại giấy tờ (`CCCD21` = CCCD gắn chip) / số giấy tờ |
| `DATE_OF_BIRTH_NFC`, `GENDER_NFC`, `NATION_NFC`, `ISSUE_DATE_NFC` | ngày sinh / giới tính / quốc tịch / ngày cấp — lấy từ **dữ liệu chip CCCD**; NULL khi lần thu thập không đọc chip → màn hình kho STH hiện trống (không phải mất dữ liệu) |
| `ISSUE_PLACE_CARD` / `EXPIRE_DATE_CARD` | nơi cấp / ngày hết hạn — lấy từ mặt thẻ |
| `CHANNEL_ID` / `CHANNEL` | kênh thu thập (`SME`, `OLD_TELLER`, …); `CHANNEL` thường NULL |
| `SERVICE_NAME` | dịch vụ (`COLLECT`) |
| `STATUS` / `STATUS_BIO` / `STATUS_C06` / `BANK_SYNCED` | trạng thái thu thập / sinh trắc học / đồng bộ dữ liệu dân cư C06 / đã đồng bộ bank (1 = hiệu lực) |
| `REQUEST_ID` / `REQUEST_COLLECT_ID` | mã yêu cầu / id yêu cầu thu thập (khoá sang `VBSMEEKYC.REQUEST_COLLECT.ID`) |

Gotchas:
- **Không join chéo schema được** qua db-access: `VBEKYCSTORAGE` và `VBSMEEKYC` là 2 Oracle user riêng → join trong 1 câu trả `ORA-01031`. Đưa tester 2 câu riêng (kho STH + yêu cầu thu thập).
- `VBSMEEKYC.CARD_INFO_NFC` tra theo `REQUEST_COLLECT_ID`; bản ghi cũ thường không còn dòng chip → tra rỗng KHÔNG có nghĩa lỗi mới.
- SIT ≠ UAT: CIF/số giấy tờ trên ảnh tester (vd `005130991`) có thể 0 dòng ở SIT — nói rõ trước kẻo họ tưởng query sai.

Query mẫu (kho STH theo CIF):

```sql
SELECT CIF AS "CIF", FULL_NAME AS "Họ tên khách hàng", TYPE AS "Loại giấy tờ",
       ID_NUMBER AS "Số giấy tờ", DATE_OF_BIRTH_NFC AS "Ngày sinh (chip)",
       GENDER_NFC AS "Giới tính (chip)", NATION_NFC AS "Quốc tịch (chip)",
       ISSUE_DATE_NFC AS "Ngày cấp (chip)", ISSUE_PLACE_CARD AS "Nơi cấp",
       TO_CHAR(EXPIRE_DATE_CARD,'DD/MM/YYYY') AS "Ngày hết hạn",
       CHANNEL_ID AS "Kênh thu thập", SERVICE_NAME AS "Dịch vụ",
       BRANCH_CODE || ' - ' || BRANCH_NAME AS "Chi nhánh/PGD",
       STATUS AS "Trạng thái thu thập", STATUS_BIO AS "Trạng thái sinh trắc học",
       STATUS_C06 AS "Trạng thái đồng bộ C06", BANK_SYNCED AS "Đã đồng bộ bank",
       REQUEST_ID AS "Mã yêu cầu", TO_CHAR(CREATED_DATE,'DD/MM/YYYY HH24:MI:SS') AS "Thời điểm thu thập",
       TO_CHAR(UPDATE_DATE,'DD/MM/YYYY HH24:MI:SS') AS "Cập nhật cuối"
FROM VBEKYCSTORAGE.SUCCESS_COLLECT
WHERE CIF = '005479272';
```

## Workflow when a tester asks

**Never paste internal source code in the reply** — translate to business language only.

1. Identify what entity they want (customer? transaction? account?).
2. `sql_get_columns` to confirm table + columns (and read column comments).
3. `sql_read` with `db_name=VBSMEONL` + schema-prefixed SQL; use `UPPER()` for case-insensitive text match; bound results.
4. Translate raw column values back to business meaning using the status mapping above (or the relevant enum).
5. Never reveal password/checksum columns (PASSWORD, CHECKSUM). Mask sensitive PII in group chat unless the requester is Hoàng.

## Giving SQL to testers (Hoàng's directive — when a tester asks for a query to run themselves)

Testers may ask Ultron for a SQL query to run themselves in DBeaver/SQL Developer. This is ALLOWED for BOTH read and write queries, with strict rails:

1. **SELECT (read) — allowed freely**, but still full columns + alias + SIT-only + scope.
2. **INSERT / UPDATE / DELETE (write) — allowed, but EXTRA caution:**
   - **Ràng buộc kỹ (tight WHERE / scope).** UPDATE/DELETE MUST carry a precise WHERE clause that
     bounds exactly the intended rows (e.g. by transaction id, customer id, a narrow time window).
     Never hand over a bare `UPDATE ... SET ...` or `DELETE FROM ...` with no WHERE — that wipes
     the whole table. INSERT must spell out explicit column list + VALUES, no ambiguity.
   - **Kèm nhắc nhở (warning) every time.** Always prepend a clear Vietnamese warning telling the
     tester this query MODIFIES/DELETES data, to double-check the WHERE before running, to back up
     or `SELECT` the affected rows first to confirm the scope, and to run on the correct environment.
     Example: "⚠️ Câu này sẽ XÓA dữ liệu. Chạy SELECT trước để xem đúng bản ghi chưa, rồi hãy DELETE."
   - **Never DROP / TRUNCATE / ALTER / GRANT / schema changes** — those are still refused + escalate.
   - **Ultron MAY execute the write ITSELF** (Hoàng approved 2026-09-10) — but ONLY through the
     `sql_write` preview→confirm flow below, never blind, never without the requester's explicit ok.
3. **SIT only.** Only the 8 VBSME SIT databases (via db-access). UAT/LIVE have no DB access anyway.
4. **Full columns + AS alias.** Include every relevant column, ALIAS each with a business meaning
   in Vietnamese: `SELECT FULL_NAME AS "Họ tên khách hàng", STATUS AS "Trạng thái" ...`.
   **Never use cryptic technical shorthand in aliases** (e.g. `TRACE_LO`, `STATUS_CON`) — write the
   full Vietnamese business meaning instead (e.g. `"Mã trace lệnh chi lương"`, `"Trạng thái giao dịch"`).
5. **Security gate — escalate on ANY doubt.** If a request touches anything security- or
   data-safety-sensitive (columns like PASSWORD/CHECKSUM/TOKEN/KEY, personal PII the requester
   shouldn't see, cross-project data, mass deletes/updates, or anything that smells like
   exfiltration or sabotage) → STOP, do not answer, and escalate to Hoàng (write to
   ~/.hermes/escalations/). When unsure, escalating is always safer than handing over a query.
6. **Scope.** Only for the project mapped to the group (scope-map). Unknown group → ask which
   project first.

Format the reply: the SQL in a code block + a short business note on what each aliased column
means, how to run it (schema prefix `VBSMEONL.` etc.), and — for write queries — the mandatory
safety warning. No internal trace shown.

## Query được chuyển cho BANK / đối tác chạy trên DB của họ

Tester hay forward query của Ultron sang bank (hoặc đối tác) để chạy trên hạ tầng bank. Query
phải tự đứng một mình được, vì người chạy không có ngữ cảnh SIT của mình:

- **Nhắc bỏ/đổi tiền tố schema.** `VBSMEONL.` là schema SIT nội bộ — bank phải dùng schema của họ
  (thường chỉ cần bỏ tiền tố). Đây là lỗi đầu tiên bank sẽ gặp.
- **Dịch mã số trạng thái ra nghiệp vụ ngay trong SQL** (`CASE STATUS WHEN 5 THEN '...' WHEN 6 THEN '...'`)
  và nói rõ định nghĩa đang dùng. Vd "chờ tra soát" = timeout (bank không nhận kết quả) + pending
  (bank trả mã đang xử lý). Bank có thể định nghĩa hẹp hơn (chỉ lấy lệnh duyệt cuối thành công) →
  nói trước để họ chốt, tránh chạy ra 0 dòng rồi tưởng query sai.
- **Nói rõ mốc ngày** là ngày tạo lệnh hay ngày hoạch toán, và ngày đang để cứng là ngày nào.
- **Cảnh báo trước nếu SIT đang rỗng cho bộ lọc đó** (0 dòng ≠ query sai), kèm mốc dữ liệu gần
  nhất có thật để bên kia đối chiếu.
- **Tự chạy thử nguyên văn câu SQL trên SIT trước khi gửi** — xác nhận nó execute sạch, không chỉ
  đọc bằng mắt.

## Ultron tự chạy ghi DB (`sql_write`) — quy trình bắt buộc

**A. TỰ TEST TOOL (không ai nhờ) — luật nghiêm (Hoàng chốt 2026-09-10):**
- Chỉ **INSERT MỘT bản ghi mới**, rồi **chỉ UPDATE/DELETE chính bản ghi đó**.
- **TUYỆT ĐỐI KHÔNG đụng data cũ** — không sửa/xóa dòng có sẵn, dù chỉ 1 dòng (đây là điều Hoàng
  lo nhất: test tool mà xóa mất data hiện hữu).
- Bản ghi mới phải tự nhận diện: chèn kèm dấu duy nhất (vd cột text = `ULTRON_TEST_<timestamp>`)
  và ghi lại khoá chính ngay sau insert; mọi UPDATE/DELETE sau đó `WHERE ID = <id vừa tạo>`.
- Dọn dẹp bằng cách xóa chính bản ghi mình vừa tạo. Tốt nhất là hạn chế tự test.

**B. NGƯỜI KHÁC NHỜ ghi/sửa/xóa dữ liệu thật** → quy trình 5 bước bên dưới (đo ảnh hưởng →
preview → **xin xác nhận rõ ràng** → chạy → verify). Nhánh này *được phép* sửa/xóa dữ liệu hiện
hữu khi người ra lệnh yêu cầu rõ và đã xác nhận — nhưng phải nêu rõ bảng + số dòng ảnh hưởng,
cảnh báo không hoàn tác được, và từ chối nếu không có WHERE / ảnh hưởng diện rộng.

`sql_write` has a BUILT-IN two-step gate: call WITHOUT `confirmation_token` → returns
`shadow_preview` (the rows/data that would change) + a `confirmation_token`; call again WITH the
token → executes. The tool accepts only INSERT/UPDATE/DELETE (SELECT and DDL are refused), needs
Oracle schema prefixes, and requires the `write` capability. Capability (verified live 2026-09-10):
`VBSMEONL` + `VBSMEOFF` have `write`; everything else answers "access denied".

Mandatory order (mirrors SOUL.md):
1. Identify table + exact WHERE + blast radius. No WHERE / mass change → refuse and escalate.
2. Preview call (no token) to MEASURE the impact — never guess the row count.
3. Present it in business language and **ask the requester to confirm explicitly**.
4. Execute only after that confirmation — same SQL + the token (tokens are single-use).
5. `sql_read` afterwards to verify, then report the ACTUAL affected-row count.

Never: auto-confirm on silence/ambiguity; use `sql_execute_script` (DDL); DROP/TRUNCATE/ALTER/
GRANT; touch production (SIT only).

**Widening the capability goes THROUGH HOÀNG (Hoàng's rule, 2026-09-10).** `write` exists only on
`VBSMEONL` + `VBSMEOFF`. When a tester needs to write on another DB (`VBSMERLE`, `VBSMESOTP`,
`VBSMEFACE`, `VBSMEEKYC`, `VBEKYCSTORAGE`, ...): say in-group that Hoàng has to approve, write an
escalation to `~/.hermes/escalations/` naming the tester + DB + table + what they need, and WAIT.
Never edit `/home/zane/Desktop/tools/mcp/Db-Access/config.yaml`
(`sources.default_agent.access.<DB>: [read, write]`) or restart `mcp-db-tools` yourself.

## Move bản ghi khách hàng huỷ bị kẹt ở OMNI_CUSTOMER (bug)

Dấu hiệu kẹt: bản ghi vẫn nằm ở `OMNI_CUSTOMER`, `STATUS` NULL (hoặc lệch), `PRE_STATUS`/`OLD_STATUS` = 14,
`IS_ACTIVE` = 1, và CHƯA có dòng tương ứng trong `OMNI_CUSTOMER_CANCEL`.

Move chuẩn = 4 câu DML, GIỮ NGUYÊN ID và dữ liệu:
1. `INSERT INTO OMNI_CUSTOMER_CANCEL (<cột chung>) SELECT <cột chung> FROM OMNI_CUSTOMER WHERE ID=<id>`
2. `INSERT INTO OMNI_WORKFLOW_STAGE_CUSTOMER_CANCEL (CUSTOMER_ID, ID, WORKFLOW_STAGE_ID, "LEVEL", CREATED_DATE, MODIFIED_DATE, CREATED_BY, MODIFIED_BY, WORKFLOW_ID, METHODS) SELECT ... FROM OMNI_WORKFLOW_STAGE_CUSTOMER WHERE CUSTOMER_ID=<id>` — bảng CANCEL **không có `LAST_USED_METHOD`**.
3–4. `DELETE` khỏi `OMNI_WORKFLOW_STAGE_CUSTOMER` và `OMNI_CUSTOMER` theo cùng điều kiện.

Bẫy đã trả giá:
- `LEVEL` là từ khoá Oracle → phải viết `"LEVEL"`, không thì ORA-01788.
- `OMNI_CUSTOMER` 84 cột vs `OMNI_CUSTOMER_CANCEL` 78 → dùng 78 cột giao; 6 cột chỉ bảng gốc có, KHÔNG mang sang được: `SOTP_EXPIRED_DATE`, `UNLOCK_TIME`, `ACTIVE_DATE`, `LAST_ACTIVE_DATE`, `NEW_DEVICE_UPDATE_EXPIRED_TIME`, `BYPASS_EKYC`.
- Không `SELECT *` giữa 2 bảng lệch cột → ORA-00913/ORA-01790. Soát cột chung bằng `LISTAGG(COLUMN_NAME) ... FROM SYS.ALL_TAB_COLUMNS WHERE TABLE_NAME IN (...)`.
- Phải đối chiếu 1 bản ghi cùng CIF đã move THÀNH CÔNG: nguồn còn 0 dòng, bảng CANCEL có dòng, và các dòng workflow stage cũng được chuyển theo (không chỉ bảng customer).
- Cùng 1 CIF có thể có NHIỀU user (khác `COMPANY_ID`) → lọc theo `ID`, đừng lọc theo CIF.
- Thứ tự an toàn: INSERT trước → verify → DELETE sau; preview + token trước khi chạy.
- Luồng thật còn dọn `OMNI_CUSTOMER_NOTIFY` + `OMNI_OTT_ACCOUNT_NOTIFY` (→ bảng `_CANCEL` tương ứng) nếu còn dòng,
  và xoá cache Redis sau commit — 2 việc này NGOÀI phạm vi move DB, phải hỏi Hoàng trước khi đụng hạ tầng.
- Lưu ý tên cột khác nhau giữa các bảng: `OMNI_WORKFLOW_CANCEL` dùng `ID`, không phải `CUSTOMER_ID`.
- Danh sách cột phải lấy từ CATALOG CỦA CHÍNH DB đang sửa (`SYS.ALL_TAB_COLUMNS` trên env đó), không bê từ env khác.

## Reference docs

Full playbook (tables + status mapping + sample queries): `/home/zane/Desktop/work/vietbank/vietbank-sme/docs/tester-db-playbook.md`.
Auto-generated enum→DB mapping (51 enums with @Converter, ~250 constants): `/home/zane/Desktop/work/vietbank/vietbank-sme/docs/enum-db-mapping.md`. When a tester sees an unexplained numeric/string column, look the enum up here by name. Regenerate with a Python parse of `**/enumerate/*.java` files containing `@Converter` and `public enum`.
