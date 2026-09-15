# Mapping "gói" phát hành ↔ Jira ↔ thư mục migration (vbsme)

Khi ai đó hỏi "tính năng nào thuộc gói X", tra theo bảng này trước khi đoán:

| Gói (cách gọi trong Jira) | Jira VSONB | Thư mục migration | Nội dung chính |
|---|---|---|---|
| 3.1.3 — đợt 1 | Task cha `VSONB-4818`; sub-task: BO `VSONB-4819`, Server `VSONB-4820`, Android `VSONB-4821`, iOS `VSONB-4822`, UAT `VSONB-4864` (QR + CR ẩn trường), `VSONB-4865` (Napas 2.0 + BO danh sách STH kho chung), `VSONB-4866` (CK bằng danh bạ + QR), `VSONB-4823` (user soạn được huỷ/copy lệnh), `VSONB-4922` (checklist smoketest trước khi lên gói) | `vietbank-sme-omni/migrations/goi-3.1-napas2.0/` | Napas 2.0 (truy vấn TK thụ hưởng, chuyển tiền, tra cứu trạng thái, risk score, rollout theo cấu hình), huỷ lệnh ở bước khởi tạo, export uỷ nhiệm chi nhiều GD / GD con lô-lương, tạo mã QR cho TK, app 1.1.0 |

Ghi chú tra cứu:
- Jira **không** dùng `fixVersion` cho các gói này — version của project VSONB chỉ có `GĐ 1`, `GĐ 2`, `GĐ 3`. Muốn tìm theo gói: JQL `project = VSONB AND (summary ~ "3.1.3" OR labels = "3.1.3")` hoặc `parent = <task cha>`.
- Thư mục migration của gói là nguồn liệt kê tính năng đáng tin nhất (changelog.md): `goi-3.1`, `goi-3.1.1`, `goi-3.1-integration`, `goi-3.1-napas2.0`, `goi-3.4`.
- Tên thư mục KHÔNG trùng số gói (vd gói 3.1.3 nằm ở `goi-3.1-napas2.0`) → đừng suy ra gói từ tên thư mục.
- Repo snapshot tại máy này **không có git history** (thư mục `.git` trống, chỉ có `hooks/`) ⇒ không tra được "nhánh nào sửa gì"; muốn biết thay đổi phải đọc code + changelog + Jira.

## Gói 3.1.3 có đụng luồng Citad không? (đã soát 2026-09-15)

Không đụng lõi Citad: `grep -ri citad migrations/goi-3.1-napas2.0/` = **0 kết quả**. Các tính năng 3.1.3 chạm Citad chỉ ở tầng lệnh và tầng xuất chứng từ:
- Huỷ lệnh ở bước khởi tạo (áp cho mọi GD tài chính, gồm Citad `00205`; lỗi `501013` / `501014`).
- Export uỷ nhiệm chi cho GD con của lô/lương (dòng Citad `00207` / `01202` nằm trong phạm vi; lỗi `700015` / `700016`).
- Luồng QR – danh bạ thụ hưởng (lệnh chuyển tiền sinh từ QR; Citad có cờ `isQr`), mã QR `211004` / `211005`.
- CR ẩn trường người soạn/duyệt + ý kiến phê duyệt (màn phê duyệt lệnh), app version 1.1.0.
- **KHÔNG** áp Citad: tra soát GD chờ xử lý (chỉ Napas 2.0), risk score thụ hưởng, đối soát tự động GD treo.
