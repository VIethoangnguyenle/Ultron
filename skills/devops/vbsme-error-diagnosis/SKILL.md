---
name: vbsme-error-diagnosis
description: "Use when testers ask why an error occurred in vbsme."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vbsme, vietbank, error, diagnosis, root-cause, tester]
    related_skills: [vbsme-db-lookup, agy-orchestration]
---

# vbsme error diagnosis (VietBank SME)

When a tester asks "lỗi này vì sao bị?" / "error code X nghĩa là gì?", diagnose the root cause from the error-code knowledge base + source.

## Error code mechanism (CRITICAL)

A full business error code is **6 digits = `ModuleError.id` (3 digits) + `ordinal` (3 digits)**.

Example: `600002` → module `BILLING` (id=600) + ordinal `2` → `BillingError.BILLING_HAVE_NO_DEBT` ("hóa đơn không có nợ").

## Knowledge base files (auto-generated, read them)

- `/home/zane/Desktop/work/vietbank/vietbank-sme/docs/error-code-mapping.md` — 433 error codes: `Mã lỗi | Module | Ordinal | Enum | Hằng`. 13 module enums.
- `/home/zane/Desktop/work/vietbank/vietbank-sme/docs/enum-db-mapping.md` — 51 enums with @Converter.
- `/home/zane/Desktop/work/vietbank/vietbank-sme/docs/tester-db-playbook.md` — tables + status mapping.
- `VBSMEONL.AD_MESSAGE` (Oracle) — error message VI/EN content keyed by CODE (also holds the 44 `VPG*` gateway codes).

## Module → service/tầng (13 modules)

Auth(100-120,213), Common(KEY=1,MID=2,EKYC=3,APP_VERSION=4,APP_SERVER=200,INTERNAL_SERVICE=201,FACE_PAY_SERVICE=202), Ekyc(COLLECT=200), Sms(OTP=150), Bank(POS_HBK=210,DEFAULT_ACCOUNT=211), Nonfinancial(BRANCH=300...REGION=308), TransactionCommon(TRANSACTION=500,SAVINGS=605), Payment(BILLING=600), Transfer(BATCH=700,701), Integration(PARTNER=800), Risk(551,552), Rle(111-115).

## Log file format — how to extract (UAT/LIVE)

Full spec: `/home/zane/.claude/skills/vnpay-log-analyzer/reference/dvnh-log-format.md`. Read it before first extraction. Key points for locating data in a raw file:

- **Unit of analysis = `LogContainer`** (one per request): `requestId, sessionId, username, userId, path, httpMethod, processDuration, logs[]`. Each `logs[]` entry = one step with `logType, data, method, step, stepTime`.
- **Anchor lines identify the channel**: `Debugging for requestId: X, sessionId: Y` (HTTP) · `Debugging Grpc call for requestId:` (gRPC) · `Debugging for requestId: X, topic: T` (Kafka) · `Logging Breakdown Server` (never-popped).
- **Monitor record** = one JSON line per hop (NOT per request): `requestid, code, uri, processtime, service_name, source, user, ...`. `user` is an MD5 hash; real username is on the anchor line. Join by `requestid`.
- **Error code lives in `RESPONSE.data.code`** (inside container) and in the monitor `code`. Three mechanical error signals: `CALL_*_REQUEST` with no `_RESPONSE`; `RESPONSE.data.code` not in success set; an `EXCEPTION` step.
- **4 line formats** to recognize: `deploy-file` (leading `[appVer-buildDate]`), `repo-file`, `console` (ANSI), `bare-json` (Kafka `%message`).
- **Extract via `vblog.py`**: `vblog.py index <logfile...>` then `user <username>` / `session <id>` / `show <rid>` / `trace <rid>` / `errors` / `grep <text>`. Files may be `.gz`. Timestamps are 9-digit fractional seconds (truncate to 6 for Python).

## sessionId — reconstruct a customer's whole session

A customer's login session is identified by **`sessionId`** (in `BaseRequest` / `BaseSessionRequest`, validated by `UserSessionValidationInterceptor`). It tells you **everything the customer did in that one session**.

- **Source of session activity: Mongo `VBSMELOGS`** (collection for `LogModel`/`LogEntity`). Each log doc has: `sessionId`, `requestId`, `cifNo`, `username`, `customerId` (userId), `service`, `endPoint`/`endPointName`, `channel`, `responseCode`, `processDuration`, `ipRequest`, `deviceName`, `imei`, timestamps.
- To replay the session: query `VBSMELOGS` by `sessionId` (order by time) → you get the ordered list of endpoints the customer hit + each one's responseCode + duration. That IS the journey.
- `sessionId` is the natural join key between a user's log activity and their transactions. Combine with `requestId` (single request) and `trace_no` (single transaction) for full drill-down: session → requests → the failing transaction.
- If the asker gives only username/CIF, resolve to their recent `sessionId`(s) from `VBSMELOGS` first (or ask for the time window), then replay.

## Always confirm before tracing a transaction journey

When the question relates to a **transaction flow** — financial (500/501/600/700/701/210/211/605) OR non-financial (phi tài chính: approval, limit, permission, email...) — **ALWAYS ask first**: "Bạn có muốn tôi truy hành trình của giao dịch này không?" Do NOT auto-trace. Only after they confirm, gather trace_no/sessionId/time window and proceed.

## Trace output = a proper markdown report with diagram

When the requester confirms tracing, the deliverable is a **markdown file** (not a short chat reply), containing:
- a **sequence/flow diagram** (mermaid `sequenceDiagram` or `flowchart`) of the transaction's full journey — each service hop, each outbound call, each step, in order;
- **analysis**: timeline (what the user did → where it broke → why), the failing step's error code + decoded message + root cause, and what to check/fix;
- evidence links (requestId / trace_no / sessionId / timestamps) without dumping raw code.

Save to `vietbank-sme/docs/qa/<yyyymmdd>-trace-<trace_no-or-user>.md`, then post the diagram + summary into the chat (files may fall back to a host-path notice if `/setup-files` is not active).

When the question relates to a **transaction flow** — financial (500/501/600/700/701/210/211/605) OR non-financial (phi tài chính: approval, limit, permission, email...) — **ALWAYS ask first**: "Bạn có muốn tôi truy hành trình của giao dịch này không?" Do NOT auto-trace. Only after they confirm, gather trace_no/sessionId/time window and proceed.

## Tracing WITHOUT requestId (the common case)

Testers usually do NOT have a requestId. They ask to check by **username** or **CIF**. Handle that:

1. **Detect if it's a transaction error from the error code.** Transaction modules are the 6-digit codes whose `module_id` (first 3 digits) maps to a financial-transaction service: `500` (transaction — shared by approval/bank/napas/payment/transfer/worker), `501` (approval), `600` (billing), `700`/`701` (batch/payroll), `210`/`211` (POS/HBK), `605` (savings), `111`/`112` (RLE transaction). If the module_id is one of these → it's a transaction error.
2. **If transaction error → ask for `trace_no` (mã giao dịch).** `trace_no` is the key column in `OMNI_TRANSACTION` (also `REF_NO` / `REF_THIRD_PARTY` = reference to core bank / third party). trace the journey via trace_no.
3. **If not transaction / no trace_no → use username or CIF** to locate records: `OMNI_CUSTOMER` (USERNAME/USER_ALIAS/CIF_NO) → `OMNI_TRANSACTION` (USERNAME/CIF_NO) → get the transaction ids, then trace.
4. Once you have trace_no / transaction id / requestId, pull the log from the log portal and rebuild the journey (`vnpay-log-analyzer`).

Key trace columns in `OMNI_TRANSACTION`: `TRACE_NO`, `REF_NO`, `REF_THIRD_PARTY`, `RESPONSE_CODE`, `RESPONSE_MESSAGE`, `USERNAME`, `USER_ALIAS`, `CIF_NO`, `CUSTOMER_ID`, `TRANS_REQ_ID`, `STATUS`, `CHANNEL`, `TYPE`.

## Config-driven errors (AD_CONFIG)

Many behaviours are NOT in code — they read the `AD_CONFIG` table (key→value→description→is_active→status). When tracing and the code path reads a config flag/limit/rule (e.g. `auth.password.max_failures`, `system.password_rule`, `*.duration`, `*.warning_*`), the root cause is often a wrong/inactive config row, not a code bug.

- **Suspect config? Check it immediately** — do not stop at code. Query `VBSMEONL.AD_CONFIG` (or `VBSMERLE` for RLE) by `CODE`/prefix: `SELECT CODE, VALUE, DESCRIPTION, IS_ACTIVE, STATUS FROM VBSMEONL.AD_CONFIG WHERE CODE LIKE '<prefix>%' ORDER BY CODE`.
- Key signs the path is config-driven: `IConfigFactory` / `ConfigFactory.findByPrefix` / `findByIdAndActiveIsTrue`, `ReloadCacheFactoryConstants.CONFIG_FACTORY`, or a `ReloadConfig*` handler (config is cached + reloaded via Kafka topic `RELOAD_CONFIG_ACCESSIBILITY`).
- Check `IS_ACTIVE` (0 = disabled row) and `STATUS` (approval state) — an inactive/not-yet-confirmed row silently changes behaviour.
- Note: `AD_CONFIG` is cached per-service; a config change needs the reload event or a cache expiry to take effect.

## Hạn mức — loại nào kiểm ở BƯỚC NÀO (câu hỏi "sao không chặn ở bước soạn lệnh?")

Có **hai nhóm hạn mức theo ngày khác nhau**, kiểm ở hai bước khác nhau. Phân biệt đúng nhóm là mấu chốt:

| Nhóm | Ý nghĩa | Kiểm ở bước | Mã lỗi |
|---|---|---|---|
| **Hạn mức LẬP LỆNH tối đa/ngày** của loại dịch vụ | Tổng tiền các lệnh user **tạo ra** trong ngày | **Soạn lệnh / khởi tạo** (`init` chain — chỉ chạy khi `AD_SERVICE_TYPE.IS_INIT_LIMIT = 1`) | 500022 |
| Hạn mức min/max mỗi giao dịch (dịch vụ trong gói) | Số tiền 1 GD | Soạn lệnh | 500012 / 500013 |
| Tổng HM giao dịch/ngày của gói | Tổng hoạch toán cả ngày của gói | **Duyệt cuối** | 500011 |
| Tổng HM giao dịch/tháng của gói | Tổng hoạch toán cả tháng | **Duyệt cuối** | 500021 |
| HM giao dịch/ngày của loại dịch vụ | Tổng hoạch toán cả ngày theo loại dịch vụ | **Duyệt cuối** | 500028 |
| HM giao dịch/ngày của dịch vụ | Tổng hoạch toán cả ngày theo dịch vụ | **Duyệt cuối** | 500029 |

- Code chỉ kiểm hạn mức giao dịch (daily/monthly package/service/service-type) **duyệt cuối** — xem `DefaultConfirmFinancialTransactionHandler.validateBeforeConfirm` (chỉ chạy khi `ConfirmType.CONFIRM_FINAL_APPROVED_TRANSACTION`; comment trong code ghi rõ "CHỈ chạy ở duyệt cuối") và `final_approve/processor/ValidateTransactionLimitProcessor` → `ValidateFinalApproveFinancialTransactionLimitHandler`.
- Bước `init` (soạn lệnh) dùng `action/init/processor/ValidateTransactionLimitProcessor` — **chỉ** kiểm hạn mức lập lệnh tối đa/ngày (so với `OMNI_DAILY_CUS_TRANS_REQ_CHECK`, hoặc override công ty trong `OMNI_DAILY_TRANS_REQ_LIMIT`) + min/max mỗi GD. **Không** kiểm hạn mức giao dịch.
- Hệ quả thường bị báo nhầm là bug: user tạo (soạn) nhiều lệnh cộng dồn vượt hạn mức giao dịch/ngày vẫn OK, chỉ bị chặn (500028/500029) khi mở bước duyệt. Đây là **đúng luồng hiện tại**. Muốn chặn ngay ở bước soạn lệnh thì phải dùng hạn mức **lập lệnh** (500022) + bật `IS_INIT_LIMIT` cho loại dịch vụ — hoặc hỏi BA/dev nếu muốn đổi thiết kế.
- Bảng tra: `AD_PACKAGE_LIMIT` (gói), `AD_PACKAGE_SERVICE_TYPE_LIMIT` (`DAILY_AMOUNT_LIMIT` = HM giao dịch, `DAILY_CUS_TRANS_REQ_AMOUNT_LIMIT` = HM lập lệnh), `AD_PACKAGE_SERVICE_LIMIT` (dịch vụ), `AD_SERVICE_TYPE.IS_INIT_LIMIT`, `OMNI_DAILY_TRANS_REQ_LIMIT` (override theo công ty).

## Environment scope — log available only in UAT & LIVE

- **Log portal covers UAT and LIVE only** (`https://10.22.17.219:10443/omni-sme/`). There is **NO log for SIT**.
- **If a tester asks about an error in SIT** → do NOT try to trace logs (none exist). Instead: purely **explain the error code** (decoded message + meaning) and use **agy/UA or claude** to explain *when/why it occurs* (the trigger condition in the code path). No timeline, no log extraction.
- Only when the error is in UAT/LIVE do you trace the full journey (log → timeline → root cause → markdown report).

## Log access (environment UAT / LIVE)

- **Log portal (UAT + LIVE, project VBSME/OMNI-SME):** `https://10.22.17.219:10443/omni-sme/`
- Log analysis skill (decode format, rebuild timeline, trace to source): `/home/zane/.claude/skills/vnpay-log-analyzer/` (script `vblog.py index|show|trace|user|session ...`).
- Error→service/API mapping: `/home/zane/Desktop/work/vietbank/vietbank-sme/docs/qa/2026-09-09-ma-loi-ad-message-tra-cuu-log.md`.

## Log retention — monthly zip

Đã chuyển sang agentmemory lessons (context=`vbsme-error-diagnosis`). Ghi nhớ: UAT log được archive theo tháng, log cũ KHÔNG bị xóa — luôn kiểm tra month zip trước khi kết luận thiếu log. Khi cần nhớ lại: `memory_lesson_recall` query `vbsme-error-diagnosis`.

## Root-cause tracing (a user's full journey — NOT just the code name)

When someone asks "user X bị lỗi gì?", they want the **root cause of the customer's whole operation journey**, not just the error-code name.

1. **Pin environment + time window FIRST.** If the asker didn't give them, ASK BACK: which environment (SIT/UAT/PILOT/`cmc-test-rke03`...), and what time window (ngày + khung giờ). Do NOT trace without these — log volume is huge and cross-env traces are meaningless.
2. **Get the log** from the log-access link/route Hoàng provided, filtered by `requestId` (preferred) or username + time window.
3. **Analyse with `vnpay-log-analyzer`** (`/home/zane/.claude/skills/vnpay-log-analyzer/`): `vblog.py index` the log, `user <username>` / `session <id>` to rebuild the journey, `show <rid>` for the timeline, `trace <rid>` across services. Reconstruct the full step chain (REQUEST → outbound CALL_* → RESPONSE), find the first failing hop, not just the final error code.
4. **Confirm source of truth:** the failing step's error code → `AD_MESSAGE` (message) + source (via CodeGraph/Serena) → business root cause.
5. **Leverage UA + claude** for deep reasoning when the journey spans many services or the bug is subtle (Hoàng allows routing reasoning→agy/UA, coding→claude).
6. **Report the journey** in business language (no code): what the user did → where it broke → why → what to check.

## Diagnosis workflow (explain in business language — NEVER paste code)

**Golden rule: never show/dump internal source code to the tester/group.** Explain only in business terms + the trigger condition (when/why it happens). Reading the source is for YOUR understanding; the answer goes out as plain-language root cause.

1. **Parse the code.** If 6-digit: split `module_id = code[:3]`, `ordinal = code[3:]` (ordinal may be 2–3 digits; match by prefix). If `VPG*` → VNPay gateway error (look up AD_MESSAGE directly).
2. **Identify module + constant.** grep `error-code-mapping.md` for the module id → get `Enum + Hằng` (the constant name is usually self-describing, e.g. `BANK_NOT_FOUND`).
3. **Get the user-facing message.** `SELECT VI_CONTENT, EN_CONTENT, DESCRIPTION FROM VBSMEONL.AD_MESSAGE WHERE CODE = '<full_code>'` (also try with/without the module id as prefix).
4. **Find WHY it was thrown.** `search_files` for `throw new` referencing that constant (e.g. `BankError.BANK_NOT_FOUND` or the enum name) — read the surrounding condition (if/validate) to explain the trigger. This is the root cause.
5. **Explain in Vietnamese**: (a) lỗi này nghĩa là gì, (b) xảy ra khi nào (điều kiện trigger), (c) tester nên kiểm tra gì / dữ liệu gì.

## Tips

Đã chuyển sang agentmemory lessons (context=`vbsme-error-diagnosis`). Khi cần nhớ lại: gọi `memory_lesson_recall` query `vbsme-error-diagnosis`.
