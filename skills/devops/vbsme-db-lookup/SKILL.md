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
   - **No running write queries yourself.** Verify correctness via metadata only (`sql_list_tables`,
     `sql_get_columns`, enum mapping), never `sql_write`/`sql_read` the statement as a trial.
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

## Reference docs

Full playbook (tables + status mapping + sample queries): `/home/zane/Desktop/work/vietbank/vietbank-sme/docs/tester-db-playbook.md`.
Auto-generated enum→DB mapping (51 enums with @Converter, ~250 constants): `/home/zane/Desktop/work/vietbank/vietbank-sme/docs/enum-db-mapping.md`. When a tester sees an unexplained numeric/string column, look the enum up here by name. Regenerate with a Python parse of `**/enumerate/*.java` files containing `@Converter` and `public enum`.
