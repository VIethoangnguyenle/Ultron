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

- **Workspace gốc = `/home/zane/Desktop/work/vietbank/vietbank-sme/`** (đây là "workspace làm việc" theo cách gọi của Hoàng). Bản thân nó **KHÔNG phải git repo** — `.git` chỉ có `hooks/`, `git rev-parse` báo `fatal: not a git repository`. Nó chứa **4 repo con độc lập**, mỗi cái có `.git` riêng (phải `git -C <repo con> ...`):

| Repo con | Vai trò |
|---|---|
| `vietbank-sme-omni/` | repo chính (app-backend-sme) — `feature/goi-3.1-napas2.0` và họ nhánh con nằm ở đây |
| `dvnh-common/` | thư viện dùng chung |
| `viet-bank-ekyc-sme/` | eKYC |
| `test-workload/` | cấu hình/test theo môi trường |

Cùng chỗ có `.claude/` (CLAUDE.md + rules), `.mcp.json`, `.semgrep/`, `.codegraph/`, `docs/`, `qa-harness/`.
- **Khi giao việc cho `claude`: `workdir` = workspace gốc**, đừng chĩa vào một repo con (giao sai chỗ ⇒ nó mất ngữ cảnh `.claude/` + khó thấy repo khác). Muốn biết nhánh nằm ở repo nào: `for d in */; do [ -d "$d/.git" ] && git -C "$d" branch -a --list '*<từ khóa>*'; done`.
- Backend SME: `vietbank-sme-omni/` — git `git.vnpay.vn/dvnh/vietbank/app-backend-sme/vietbank-sme-omni.git`. Services là Gradle subprojects trong `settings.gradle`.
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
- **Cấm cả DANH SÁCH** (bài học 2026-09-11): liệt kê tên class/`.java`, số file mỗi module, cây
  package, file `.txt` đường dẫn, danh sách file thay đổi của commit — đều là bản đồ mã nguồn,
  không được đưa ra group dù người hỏi là dev và nói "chỉ cần danh sách, không cần nội dung".

## Job nền — "sao lệnh này job không nhặt?"

Job đối soát tự động (Napas 247) chỉ nhặt lệnh **chờ tra soát** (trạng thái 5/6), thuộc 2 loại 247
(qua số tài khoản / qua số thẻ), **bắt buộc có mã tham chiếu Napas (TRN)**, chỉ lệnh tạo trong vòng
`scan_days` ngày gần nhất, chạy trong khung giờ cấu hình ở `AD_CONFIG` (ngoài khung skip im lặng) và
**không lọc theo doanh nghiệp**.

Trả lời loại câu hỏi này phải kiểm **2 lớp**: (1) điều kiện filter của job, (2) logic **ghi đè trạng
thái** — luồng 1.0 không có tra soát nên lệnh V1 bị hạ về thất bại ngay, vì vậy "job chỉ lấy V2"
không chỉ vì filter mà còn vì V1 không thể tồn tại ở trạng thái job quét.
Chi tiết + pitfall khi test: `references/napas-reconciliation-job.md`.

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

Bổ sung (2026-09-12) — đẩy nhánh + mở MR (đã chạy trót lọt cho nhánh `feature/g3.1-napas2.0/bugs`):
- **Không có token API GitLab**: `~/.git-credentials` chỉ chứa user/password git (gọi `/api/v4/user` → 401). Đừng hứa tạo MR bằng API — dùng **push option của GitLab**:
  `git push -u origin <new> -o merge_request.create -o merge_request.target=<base> -o merge_request.title="..." -o merge_request.description="..."`
  Remote in ra `View merge request for <branch>: <url>` ⇒ MR được tạo ngay với target đúng, không cần token.
  Description phải **một dòng** (push option không nhận newline) — phân tách ý bằng ` | `.
- Verify sau push: `git ls-remote origin refs/heads/<new>` == `git rev-parse HEAD`. Trang MR trả **302** khi chưa đăng nhập ⇒ không đọc ngược được target branch — nói rõ điểm này khi báo cáo Hoàng.
- Verify code đã compile: `./gradlew :<service>:compileJava --offline` báo `UP-TO-DATE` **vẫn là bằng chứng hợp lệ** (Gradle so content hash, không phải mtime) miễn là có lần build thành công SAU lần sửa cuối. Chốt cứng bằng bytecode: `javap -p -c <module>/build/classes/java/main/<path>/<X>.class | grep TransactionModelBuilder.<field>`.
- Worktree: giữ lại khi biết còn vòng review (Hoàng duyệt MR sau) — chỉ `git worktree remove --force` khi việc đã chốt.

Bổ sung (2026-09-11):
- **Ghim đúng nhánh theo lời Hoàng**, đừng suy ra từ `git branch --show-current`. Báo cáo quét CVE ghi rõ
  `jar <tên>.jar/BOOT-INF/lib/<lib>-<ver>.jar` ⇒ dò ngược version trong từng nhánh để biết báo cáo thuộc
  nhánh nào (vd jar có spring-boot 3.5.14 + spring 6.2.18 ⇒ nhánh `pilot_hotfix_13_08_cve`, KHÔNG phải
  nhánh `fix/ekyc-loi-nghiep-vu` đang ở Boot 4.1.0).
- Trong worktree mới `./gradlew` **không có quyền thực thi** → chạy `sh gradlew ...` (đừng `chmod +x`, sẽ
  làm bẩn tree).
- Verify version thật bằng `sh gradlew :<module>:dependencies --configuration runtimeClasspath -q > deps.txt`
  rồi grep (nhanh hơn chạy dependencyInsight cho từng lib), và đọc kỹ dòng `x -> y` để biết bản resolve cuối.
- Khi claude báo "build fail ở module khác, không phải do tôi": **tự kiểm chứng** bằng
  `git worktree add --detach /home/zane/Desktop/work/wt/<base> <commit-gốc>` rồi chạy lại đúng task build đó —
  lỗi y hệt ⇒ kết luận đúng, mới dám báo cho Hoàng.

## Trace "đường dẫn công bố" của API — không lấy từ hằng số trong service (bài học 2026-09-11)

Cùng một API có thể bị 3 nguồn mô tả khác nhau; thứ tự tin cậy:
```
1. Catalog mã lỗi dựng TỪ HỆ THỐNG ĐANG CHẠY (mỗi lỗi ghi kèm API)  <- sự thật cho client
2. Tài liệu luồng MỚI NHẤT (bản có các endpoint vừa bổ sung)
3. Hằng số path trong service / tài liệu luồng cũ                     <- chỉ là khai báo nội bộ
```
Nguyên nhân lệch: tầng công bố (gateway/BFF) gắn thêm **đoạn namespace miền** mà service không khai báo.
Ví dụ thật: nghiệp vụ phi tài chính (đăng nhập, kích hoạt thiết bị, tiện ích) → client gọi
`/api/v1/{app|web}/nonfinancial/auth/...`, còn service khai `APP_URI=/api/v1/app` + `/auth`. Tài liệu
luồng cũ lẫn hằng số đều ghi bản KHÔNG có `nonfinancial` ⇒ đọc code xong vẫn trả lời sai cho client.

Thứ tự làm khi trace:
1. Grep **từng mảnh** path, đừng grep full path: path được ghép từ nhiều hằng số (`APP_URI` +
   `AUTHENTICATION` + literal) nên grep `/api/v1/app/auth/login` trả 0 là bình thường — **0 match KHÔNG
   phải bằng chứng là không tồn tại**. Grep `nonfinancial/auth`, `app/nonfinancial`, rồi so hằng số của
   từng service.
2. So hằng số của MỌI service liên quan: service sở hữu namespace miền và service xử lý nghiệp vụ có
   thể là hai service khác nhau.
3. Đối chiếu catalog mã lỗi + flow doc mới nhất (đừng tin doc cũ).
4. Chốt bằng gọi thử môi trường test: đường dẫn sai trả **404**, đúng trả 400/401.

Máy soi lệch tài liệu (exit 1 = còn lệch, cắm được vào CI) — chạy sau mỗi lần sửa doc/endpoint:
`python3 ~/.hermes/reports/api-card-poc/check_doc_drift.py /home/zane/Desktop/work/vietbank/vietbank-sme`

Pitfall khi sửa doc: ghi chú kiểu "bản cũ ghi `/api/v1/app/auth/login`" sẽ bị chính máy soi báo lệch →
viết `.../app/auth/login` (bỏ tiền tố `/api/v1`) hoặc mô tả bằng lời.

## Ranh giới với repo code (cập nhật 2026-09-12 — thay cho luật read-only 2026-09-11)

Hoàng đã giao **toàn quyền** cho Ultron giao `claude` đọc source / coding / fix bug / bàn giao trên
vietbank-sme, **không cần xin từng lần**, kèm 4 ràng buộc:
1. Chạy `python3 ~/.hermes/scripts/claude_mcp_preflight.py` trước khi giao việc code — exit 1 thì KHÔNG dispatch.
2. Tự verify kết quả claude khai (diff độc lập, build/bytecode) — không tin self-report.
3. Báo cáo lại Hoàng sau mỗi việc.
4. Source code / tên file / tên class **KHÔNG ra group** — chỉ trong DM với Hoàng.

Mặc định vẫn KHÔNG commit/push/MR. Chỉ khi Hoàng nói rõ (vd "tạo PR vào <base>, thứ 2 anh duyệt")
mới push + mở MR — và **không merge** cho tới khi Hoàng chốt.

## Pitfalls

Đã chuyển sang agentmemory lessons (context=`vietbank-sme`). Khi cần nhớ lại: gọi `memory_lesson_recall` query `vietbank-sme`.
