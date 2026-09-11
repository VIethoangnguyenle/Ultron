# Nguồn quản version dependency theo repo (vbsme)

Dùng khi ai hỏi "artifact X được inject ở đâu / nâng version từ đâu". Version nêu ở đây là
version đã kiểm chứng bằng `dependencyInsight` trên `runtimeClasspath`, không phải đọc pom suông.

## Bảng nguồn

```
Repo                        Nguồn quản version                  Override ở đâu
-------------------------   ---------------------------------   -----------------------------
vietbank-sme-omni           BOM spring-boot-dependencies,       ext['<tên>.version'] trong block
  (16 service)              qua spring_boot_version ở           subprojects của root build.gradle
                            gradle.properties                   (tiền lệ: spring-integration)
viet-bank-ekyc-sme          ext {} trong root build.gradle      sửa property trong ext đó
  (internal-service,        (version khai cứng từng artifact)   (/prometheus_version 1.14.1/)
   ekyc-appserver,
   facepay-service)
dvnh-common                 KHÔNG khai micrometer              —
  (monitor modules chỉ dùng Spring event + autoconfigure)
```

## vietbank-sme-omni (repo SME chính)

- 16 service khai **trần** `implementation 'io.micrometer:micrometer-registry-prometheus'` ngay dưới
  `implementation 'org.springframework.boot:spring-boot-starter-actuator'`: auth, payment, transfer,
  card, media, napas, worker, bank, soft-otp, rle, notification, onboard, sms-otp, integration,
  nonfinancial, approval.
- Không có `force` / `resolutionStrategy` nào cho micrometer trong toàn repo. Nguồn version duy nhất =
  `spring_boot_version` trong `vietbank-sme-omni/gradle.properties` (BOM `spring-boot-dependencies`
  import `micrometer-bom` + `micrometer-tracing-bom`, thuộc tính `<micrometer.version>`).
- Đường vào classpath gồm cả gián tiếp, không chỉ khai trực tiếp:
  `spring-boot-starter-actuator` → `spring-boot-starter-micrometer-metrics` → `micrometer-core`,
  `micrometer-observation`, `micrometer-commons`, `micrometer-jakarta9`; `spring-context` (Framework)
  và `spring-kafka` kéo `micrometer-observation`; `hibernate-platform` kéo `micrometer-core` bản cũ hơn
  — tất cả bị BOM nâng về cùng một version.
- Nâng cả bộ = sửa `spring_boot_version` (1 dòng, kéo theo mọi lib Spring quản). Nâng riêng họ
  micrometer = thêm `ext['micrometer.version']` vào block `subprojects` (đặt cạnh
  `ext['spring-integration.version']`). Đừng `force` lẻ từng artifact: core/observation/commons/
  jakarta9/registry phải cùng version, force lẻ là lệch ngay.

## CVE micrometer (đã fix thật, nhánh eKYC pilot_hotfix_13_08_cve)

CVE-2026-40984 (Micrometer HTTP server instrumentation DoS) — affected 1.15.0–1.15.11 (và
1.14.0–1.14.15, 1.13.x, ≤1.9.17). **Fixed OSS: 1.15.12** (1.16.6 / 1.17.x cũng được).
Nhánh eKYC Boot 3.5.14 trước fix resolve core/obs/commons/jakarta9 = 1.15.11 (dính CVE) còn
registry-prometheus 1.14.1 (pin tay) → fix = đưa cả họ về 1.15.12.

Cách fix ĐÃ KIỂM CHỨNG (chỉ sửa root `build.gradle`, +3/-1):
```
        prometheus_version = '1.15.12'          # trong block ext của subprojects
    ext['micrometer.version'] = '1.15.12'       # ngay sau block ext, CŨNG trong subprojects {}
```
`ext['micrometer.version']` **hoạt động thật** với Spring Boot Gradle plugin + io.spring.dependency-management:
root build.gradle chạy trước build.gradle của subproject nên placeholder BOM đã bị override trước khi
plugin được áp → dependencyInsight cho ra cả họ micrometer = 1.15.12 (mọi module). Đây là cách nâng
RIÊNG họ micrometer mà không đụng `spring_boot_version`.
Cách verify: `sh ./gradlew :<module>:dependencyInsight --configuration runtimeClasspath --dependency micrometer-core "
(online, KHÔNG --offline, vì version mới chưa nằm trong gradle cache; nexus artifact.vnpay.vn có 1.15.12).

## viet-bank-ekyc-sme — version micrometer PHỤ THUỘC NHÁNH

**Luôn hỏi/xác định đang nói nhánh nào trước khi trả lời.** Cùng repo nhưng mỗi nhánh một bộ
version, vì nhóm `micrometer-core/observation/commons/jakarta9` do BOM Spring Boot quyết còn
`micrometer-registry-prometheus` bị pin tay.

```
Nhánh                                   Spring Boot   core/obs/commons/jakarta9   registry-prometheus
-------------------------------------   -----------   ------------------------   -------------------
master                                  3.4.0         1.14.2                     1.14.1
dev, origin/feature/dev/chinhnd1/*      3.5.14        1.15.11                    1.14.1
origin/dev_sit, origin/cr/ekyc-…-sdk    3.5.9         1.15.7                     1.14.1
fix/ekyc-loi-nghiep-vu,
  feat/ekyc-chuan-hoa-nang-common       4.1.0         1.17.0                     1.14.1
```

- Nguồn pin registry: `prometheus_version` trong block `ext {}` của root `build.gradle`
  (dòng ~147 trên dev_sit, ~152 trên dev, ~155 trên nhánh 4.1.0). Giá trị **1.14.1 ở mọi nhánh**;
  lịch sử chỉ từng có 1.12.2 → 1.14.1 (`git log --all -p -S "prometheus_version" -- build.gradle`).
- Số module khai biến này: dev = 5 (`ekyc-appserver`, `facepay-service`, `internal-service`,
  `legacy-migration-job`, `teller-service`); nhánh 4.1.0 = 3 (bỏ 2 module sau). Không module nào khai
  version micrometer trực tiếp.
- Hệ quả cần cảnh báo: registry-prometheus 1.14.1 chạy cùng core 1.15.11 (dev) / 1.17.0 (nhánh 4.1.0)
  → cùng họ mà lệch minor. Nâng thì sửa `prometheus_version`, hoặc bỏ version để BOM quản cho đồng bộ.
- Muốn nâng nhóm theo BOM (core/observation/commons/jakarta9) mà không đụng Boot: thêm
  `ext['micrometer.version']` trong block `subprojects` của root `build.gradle` — **chưa có tiền lệ
  trong repo này**, phải thử + verify lại bằng `dependencyInsight` sau khi áp.
- `gradlew` trong checkout này không có quyền exec → chạy `sh ./gradlew …`.
- Bẫy nhận diện sai: chuỗi `1.15.11` trong repo/nhánh cũ chỉ là **byte-buddy 1.15.11** nằm trong jar
  đã build (vd `obfuscated/*.jar` commit trong lịch sử), KHÔNG phải micrometer.

## Lệnh kiểm chứng (chạy được, `--offline` dùng gradle cache)

```
cd <repo>
./gradlew :<service>:dependencyInsight --configuration runtimeClasspath --dependency <artifact> --offline
./gradlew :<service>:dependencies --configuration runtimeClasspath --offline | grep -i <artifact>
```

- `<service>` là tên Gradle subproject (vd `auth-service`, `internal-service`).
- Đọc `Selection reasons`: `By constraint` / `Selected by rule` = version do BOM/dependency-management
  quyết; dòng `A -> B` = có nhánh khai A nhưng resolve thành B.
- Tra version BOM trong cache: `~/.gradle/caches/modules-2/files-2.1/org.springframework.boot/spring-boot-dependencies/<v>/…/spring-boot-dependencies-<v>.pom`
  (grep `<micrometer.version>`); BOM con ở `…/io.micrometer/micrometer-bom/<v>/…micrometer-bom-<v>.pom`.
- Liệt kê version đã tải về máy: `ls -1 ~/.gradle/caches/modules-2/files-2.1/io.micrometer/*` (nhanh, nhưng
  chỉ là gợi ý — version đang dùng phải lấy từ `dependencyInsight`).

### Verify version của NHÁNH KHÁC mà không đụng working tree

Checkout của eKYC hay đang dở (staged/unstaged) → **tuyệt đối không `git checkout`/`stash`** làm xáo trộn.
Dùng worktree tạm, chỉ lấy file build (không cần source):

```
cd <repo>
git worktree add --no-checkout /tmp/ekyc-verify <branch>
cd /tmp/ekyc-verify
git checkout <branch> -- '*.gradle' gradle gradlew      # KHÔNG đưa gradle.properties vào pathspec nếu file không tồn tại (cả pathspec bị reject)
cp <repo>/.env /tmp/ekyc-verify/.env                    # root build.gradle throw nếu thiếu DEPLOY_TOKEN_VALUE
sh ./gradlew :<module>:dependencyInsight --configuration runtimeClasspath --dependency micrometer-core --offline
cd <repo> && git worktree remove --force /tmp/ekyc-verify    # dọn ngay, không prune (có thể có worktree của người khác)
```

Thiếu source không sao — `dependencyInsight` chỉ cần cấu hình, không compile.
