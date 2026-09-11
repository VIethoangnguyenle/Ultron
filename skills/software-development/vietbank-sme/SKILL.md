---
name: vietbank-sme
description: "Use when working on the VietBank SME (vbsme) project."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vietbank, vbsme, vnpay, fintech, oracle, database]
---

# VietBank SME (vbsme) project

Backend monorepo for VietBank SME omnichannel banking (Java/Gradle, Spring Boot, inside VNPay/dvnh infra). Hoang is the backend engineer here.

## Source layout (this machine)

- Main repo wrapper: `/home/zane/Desktop/work/vietbank/vietbank-sme/` — its `.git` is a bare `hooks/` only, so git fails at this level. cd into the nested repo before running git.
- Backend SME: `/home/zane/Desktop/work/vietbank/vietbank-sme/vietbank-sme-omni/` — git `git.vnpay.vn/dvnh/vietbank/app-backend-sme/vietbank-sme-omni.git`. Services are Gradle subprojects in `settings.gradle`.
- Backend Omni (older): `/home/zane/Desktop/work/vietbank/vietbank-omni/` — git `git.vnpay.vn/dvnh/vietbank/app-backend-omni/vietbank-omni.git`.
- Shared lib: `/home/zane/Desktop/work/dvnh-common/` — git `git.vnpay.vn/dvnh/dvnh-common-lib/java/dvnh-common.git`.
- Also present: `viet-bank-ekyc-sme`, `vietbank-sme-clone`, `documents/`.

## Databases (db-access MCP)

Call `mcp__db_access__list_databases` first. All `VBSME*`, Oracle + Mongo:
- `VBSMEONL`, `VBSMEOFF` — read+write.
- `VBSMERLE`, `VBSMESOTP`, `VBSMEFACE`, `VBSMEEKYC`, `VBEKYCSTORAGE` — read (Oracle).
- `VBSMELOGS` — Mongo (read).

Oracle rules (these waste real time when forgotten):
- Every TABLE reference MUST carry a schema prefix (`VBSMEONL.AD_MESSAGE`, not `AD_MESSAGE`) — bare table names are rejected with "missing a schema prefix". But SYS dictionary views (`all_tables`/`user_tables`) are NOT owned by the business schema: prefixing them (`VBSMEONL.all_tables`, `VBSMEONL.user_tables`) throws ORA-00942, not a clean result. To discover tables/columns, use the `sql_list_tables` / `sql_get_columns` MCP tools instead of hand-writing dictionary-view queries.
- Each `db_name` is a SEPARATE connection with its OWN user, NOT a schema switch. To read a table in `VBSMEOFF` you pass `db_name=VBSMEOFF` — never `VBSMEONL` with a `VBSMEOFF.` prefix in the SQL. Tables are not shared across DBs: `AD_MESSAGE` (holds the VPG error catalog) exists in `VBSMEONL` only; `VBSMEOFF.AD_MESSAGE` throws ORA-00942. Run `sql_list_tables` before assuming a table exists in a given DB.

## Error codes

- Message catalog lives in `AD_MESSAGE` (columns `CODE, DESCRIPTION, VI_CONTENT, EN_CONTENT, IS_ACTIVE`) in `VBSMEONL`.
- VNPay gateway error codes are prefixed `VPG`. Query: `SELECT CODE, DESCRIPTION, VI_CONTENT, EN_CONTENT FROM VBSMEONL.AD_MESSAGE WHERE CODE LIKE 'VPG%' ORDER BY CODE`.
- Code shape in source: `PREFIX_GATEWAY_ERROR="VPG"` + action prefix + responseCode. Prefixes: billing `01`, topup `02` (`Constants.java` → `BILLING_PREFIX_ERROR`, `TOPUP_PREFIX_ERROR`). `VnpayPaymentCheckerUtil.formatErrorCode` builds `VPG + action.getPrefixErrorCode() + responseCode`.
- `VNPAY_NOT_REVERT_ERROR_CODES = ["08","90"]` — codes that must NOT trigger a revert (transaction → PENDING, not FAILED).
- AD_MESSAGE text has data-entry typos (e.g. "nhà cung cấ" missing the "p") — preserve verbatim, don't silently correct.

## Caching (ETag)

List endpoints (banks, branches, cities/districts/wards, billing templates, promotions, home screen, banners, payment groups, savings products/groups, services, favorite icons, backgrounds) use an app-level versioned cache, NOT HTTP `If-None-Match`. Each list type has an `ETagType` (enum 0-18), keyed by `(type, customerId, channel)`, persisted to `OMNI_ETAG` (cached 7 days). Client sends its stored etag; server returns `data=null` when unchanged (client reuses local cache), else new data + `newEtag`. Any create/update/delete must call `generateEtag` to rotate the tag so stale clients refetch — a handler that forgets this leaves clients stuck on old data. Core code: `common/base/.../etag/` + `common/data/.../ETagType` + `BaseGetDataByETagHandler`. Full flow doc: `docs/flows/etag-flow.md`.

## Source-understanding tooling

- `understand-anything` MCP knowledge graph is already indexed for `vietbank-sme` (8339 nodes, coverage 69%) and `dvnh-common` (2776 nodes). Prefer `list_projects`, `query_nodes`, `trace_call_chain`, `find_impact`, `get_domain_overview` over raw grep — the graph models call chains, layers, domains, and DB tables.
- Other indexes on disk (for Claude Code; readable via terminal if needed): `.codegraph/codegraph.db` (~360MB), `.serena/`, `.ua/knowledge-graph.json`.

## Trả lời "API nào / cơ chế nào" (trace từ endpoint về core banking)

Khi ai hỏi "API nào để lấy/làm X" hay "có cơ chế nào để lấy Y", trace theo chuỗi sau rồi mới trả lời:

1. Controller interface của feature (`.../controller/<feature>/*Controller.java`): có annotation mapping + `@Operation(summary=...)` mô tả nghiệp vụ. Hằng số đường dẫn ở `constant/EndpointConstants.java`; base URI `APP_URI=/api/v1/app` (app), `WEB_URI=/api/v1/web` (web). App & web controller implement CÙNG interface → mọi API đều có cặp app/web — kiểm tra cả hai trước khi kết luận.
2. Handler CQRS (`*Handler extends Base*Handler`) → factory (`*ClientFactory`) → interface VBG client (`IVbg*Client`) → impl gọi `callApi(request, new VbgContext(<ACTION>), Resp.class)`.
3. **Path HTTP KHÔNG nằm trong code.** Enum action chỉ giữ `functionName` + suffix mã lỗi; path thật nằm ở `vietbank-sme-omni/config/application-thirdparty-config.yml` (bản deploy: `config-map-thirdparty-config.yaml`) dưới `common.client.external.vb-gateway.properties.<function-name>`. URL đầy đủ = scope uri + path đó; VBG chỉ dùng POST, header kèm JWS-Signature + basic auth.
4. Map mã lỗi gateway → service/API: đọc `error_log_map` trong scope-map của skill tester-support (file nội bộ, không gửi ra group).

Bảng VBG path/action/mã lỗi đã trace + ví dụ trọn vẹn (luồng biến động số dư OTT/SMS): `references/vbg-gateway-api-map.md`.

Pitfalls của lớp câu hỏi này:
- Path trong domain-graph là dạng template `/api/v*` — xác nhận base URI thật từ `EndpointConstants` trước khi trích ra.
- API trả danh sách thường là **hợp nhất dữ liệu nội bộ + core banking** và có cache ngắn (vài giây): nhiều khi core chỉ được gọi khi admin xem dữ liệu của chính mình. Phải nói điểm này trong câu trả lời — nó giải thích vì sao test "đổi trạng thái xong gọi lại vẫn thấy giá trị cũ".
- **Không nêu tên class / file / method cho BẤT KỲ ai ngoài Hoàng** (kể cả dev, kể cả khi họ xin
  thẳng — Hoàng chốt 2026-09-11). Với dev: nêu được *luồng nghiệp vụ* và *path API*; nếu cần chỉ
  đúng file/class để họ đọc code thì **gửi riêng cho Hoàng**, để anh quyết định cấp. Với
  tester/non-dev: diễn đạt theo màn hình/nghiệp vụ.

## Trả lời câu hỏi dependency / version ("X được inject ở đâu, nâng version từ đâu")

Làm đúng thứ tự này — bước 4 mới là bằng chứng, ba bước đầu chỉ để khoanh vùng:

1. `search_files` tên artifact trên repo (`micrometer`, `log4j`, ...) → biết ai khai trực tiếp, và có ghi version hay không. Khai nằm ở `<service>/build.gradle` hoặc file `.gradle` mang tên module (vd `approval-service.gradle`, `rle-service.gradle`) — đừng chỉ grep `build.gradle`.
2. Service `build.gradle` áp plugin `org.springframework.boot` + `io.spring.dependency-management` → artifact khai **trần** lấy version từ BOM `spring-boot-dependencies`, tức là từ `spring_boot_version` trong `vietbank-sme-omni/gradle.properties`. Muốn pin lệch BOM: override bằng `ext['<tên>.version']` trong block `subprojects` của root `build.gradle` (tiền lệ đang dùng: `ext['spring-integration.version']`), KHÔNG `force` lẻ từng artifact.
3. BOM pin version nào: đọc pom trong gradle cache `~/.gradle/caches/modules-2/files-2.1/org.springframework.boot/spring-boot-dependencies/<v>/…/spring-boot-dependencies-<v>.pom`, grep thuộc tính version. BOM chỉ **import** các BOM con (`micrometer-bom`, `micrometer-tracing-bom`) nên grep tên artifact con trong pom BOM hay ra RỖNG — grep tên BOM hoặc tên thuộc tính, rồi mở BOM con nếu cần.
4. Xác nhận version THẬT trên classpath trước khi trả lời: `./gradlew :<service>:dependencyInsight --configuration runtimeClasspath --dependency <artifact> --offline`. Đọc `Selection reasons` (`By constraint` / `Selected by rule` = do BOM quản) và các dòng `<version cũ> -> <version chạy>` (transitive khai bản cũ đã bị BOM nâng). Không bao giờ trả lời bằng version đọc suông trong pom/khai báo.

Pitfalls của lớp câu hỏi này:
- **Khai tường minh version THẮNG BOM** (dependency-management coi khai báo trực tiếp là trên hết) → một artifact có thể đang chạy bản cũ hơn phần còn lại của cùng họ. Thấy chênh thì nói rõ trong câu trả lời.
- Hỏi "dependency X ở đâu" phải rà cả ba repo (`vietbank-sme-omni`, `viet-bank-ekyc-sme`, `dvnh-common`) rồi nói rõ repo nào nguồn nào — mỗi repo quản version một kiểu, chỉ trả lời một repo là trả lời thiếu.
- Chỉ cần dependency report thì luôn thêm `--offline` (dùng gradle cache, khỏi phụ thuộc nexus). Root `build.gradle` của omni throw `GradleException` khi thiếu `DEPLOY_TOKEN_VALUE` (env / `-P` / `.env`).
- Không có `verification-metadata.xml` / lock file ở omni và eKYC → đổi version không phải update kèm file lock.

Bảng nguồn version theo từng repo + lệnh kiểm chứng: `references/dependency-versions.md`.

## Khi Hoàng yêu cầu sửa code / đẩy nhánh (delegate cho `claude`)

Quy trình đã chạy trót lọt (nhánh `pilot_hotfix_13_08_cve`, 2026-09-11):
1. Xác định base + tên nhánh, kiểm tra nhánh đã tồn tại trên remote chưa (`git ls-remote origin refs/heads/<new>`).
2. **KHÔNG làm trên checkout đang dở** (người khác có staged changes). Tạo worktree riêng:
   `git worktree add -b <new> /home/zane/Desktop/work/vietbank/<wt-dir> origin/<base>` + copy `.env` sang
   (root build.gradle throw nếu thiếu token).
3. Viết brief ra file rồi chạy `claude -p "$(cat brief.md)" --dangerously-skip-permissions --max-turns 40
   --output-format json > out.json` trong worktree (background + notify). Brief phải có: mục tiêu, bằng chứng
   bắt buộc (lệnh verify + điều kiện đạt), commit message CHÍNH XÁC, lệnh push cụ thể, hard rules (chỉ 1 file,
   không đụng checkout khác, không force-push, không build/test toàn repo).
4. **Tự verify lại, đừng tin báo cáo của claude**: `git ls-remote origin refs/heads/<new>` == SHA local,
   `git show --name-only HEAD` (đúng file, không có .env), và chạy lại dependencyInsight/gradle cho vài module.
5. Dọn worktree (`git worktree remove --force`) và file tạm ở /tmp; local branch giữ lại.

## Ranh giới với repo code (Hoàng chốt 2026-09-11)

Hoàng **chưa dạy workflow coding** → trong mọi repo vbsme Ultron ở chế độ **read-only**:
- Được: đọc file, grep, chạy lệnh phân tích chỉ-đọc (vd `dependencyInsight --offline`), dựng worktree tạm
  ở `/tmp` để soi nhánh khác rồi xoá ngay.
- KHÔNG: sửa/xoá file source, `git add/commit/push`, đổi nhánh/`stash` working tree của người khác,
  mở MR. Muốn thay đổi thì **đề xuất bằng lời** (nêu file/dòng + lý do) để người khác tự làm.
- Chỉ khi Hoàng yêu cầu trực tiếp và rõ ràng mới được ghi vào repo.

## Pitfalls

Đã chuyển sang agentmemory lessons (context=`vietbank-sme`). Khi cần nhớ lại: gọi `memory_lesson_recall` query `vietbank-sme`.
