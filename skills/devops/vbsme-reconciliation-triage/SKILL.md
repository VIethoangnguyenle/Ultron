---
name: vbsme-reconciliation-triage
description: "Use when a vbsme giao dịch treo chờ xử lý sau job đối soát."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vbsme, vietbank, reconciliation, napas, pending, log, tester]
    related_skills: [vbsme-error-diagnosis, tester-support, vbsme-db-lookup]
---

# vbsme — giao dịch treo "Chờ xử lý" / job đối soát không đổi trạng thái

Dùng khi tester hỏi kiểu: *"job chuyển tiền 247 chạy lúc HH:00 mà giao dịch <trace> vẫn chưa đổi trạng thái"*, *"giao dịch treo chờ xử lý"*, *"kiểm tra nguyên nhân"* cho một giao dịch 247, hoặc khách thấy mã **500069**.

Đây là quy trình riêng cho **trạng thái treo do đối soát**. Các nguồn chính vẫn là 2 skill nền (user-owned): `tester-support` (scope-map, quy tắc trả lời, báo cáo PDF) và `vbsme-error-diagnosis` (tra mã lỗi, trace journey). Chi tiết đầy đủ của lớp việc này: `references/pending-transaction-reconciliation.md`.

## Rule cốt lõi — trả lời đúng ngay, đừng để tester báo bug sai chỗ

Giao dịch 247 chỉ được **chốt trạng thái cuối** khi lõi trả **thành công** hoặc **thất bại**. Ba mắt xích:

1. Lõi **không phản hồi** ở bước duyệt cuối → khách thấy **500069 "Giao dịch đang chờ xử lý…"** → giao dịch về **Chờ xử lý** (chưa xác định kết quả).
2. Job đối soát hỏi lại lõi theo **TRN**. Lõi trả *"No record found for TRN"* → **không có căn cứ chốt** → job **giữ nguyên** trạng thái.
3. ⇒ "Trạng thái không đổi" là **hành vi đúng của hệ thống**, KHÔNG phải job lỗi/kẹt. Nói rõ điểm này trong câu trả lời.

Thêm 2 điều tester luôn cần biết: TRN có **thời gian sống** (`financial.transaction.napas_v2.trn.ttl_hours`) nên TRN lúc tạo lệnh khác TRN lúc duyệt cuối (**không phải lỗi**); và job chỉ quét giao dịch treo trong **`...napas_v2.reconciliation.scan_days` ngày** → quá cửa sổ đó giao dịch **không còn được quét nữa**, treo tới khi xử lý tay.

## Quy trình 5 bước

1. **Chốt mốc thời gian + mã định danh**: mã giao dịch (trace), user, môi trường (UAT), khoảng thời gian. Giao dịch NAPAS V2 có **TRN riêng** (kèm trong log) — thu thập cả hai mã để grep.
2. **Tải log về local rồi grep** (portal Apache autoindex, `curl -k`):
   - **Log THÁNG HIỆN TẠI nằm ngay ở thư mục service** (`<svc>/sme-<svc>-<pod>.log`); thư mục `<svc>/<YYYY-MM>/` chỉ chứa log **archive của tháng trước** → curl vào đó rỗng, đừng tưởng hết log.
   - Tên file trên index bị cắt bằng `..&gt;` ở phần text → **parse thuộc tính `href`**, đừng lấy text của link.
   - File vài MB, trộn nhiều ngày → tải về `/tmp/<thu-muc>/`, grep local (`grep -c` để đếm, `cut -c1-400`/`head` khi in cho khỏi tràn ngữ cảnh). Trace không thấy ở pod đang xem → tải nốt pod khác **trước khi** kết luận "log không có". Log chứa payload thô (số TK, CIF, tên KH) → **xoá `/tmp` sau khi xong**.
   - Service cần: `napas-service` (bước duyệt cuối / gọi lõi), `worker-service` (**job đối soát**), `approval-service` (danh sách chờ duyệt), `transfer-service`.
3. **Đọc container đối soát trong `worker-service`**: mỗi giao dịch là 1 container `requestId = NapasRecon-<traceNo>`. Đối chiếu 3 kết cục (bảng trong reference) để kết luận giao dịch **đã chốt** / **còn chờ phía NAPAS (bình thường)** / **lõi không có bản ghi (treo vô thời hạn)**.
4. **Thống kê CẢ LƯỢT chạy**, không chỉ giao dịch được hỏi → trả lời được "có phải riêng giao dịch của tôi không". Lỗi kiểu này thường đến **theo đợt** (lõi không phản hồi vài phút → hàng chục giao dịch treo cùng lúc).
5. **Báo cáo PDF** cho tester: timeline bảng + sequence diagram + danh sách giao dịch treo cùng đợt + "việc cần xác minh tiếp"; ngôn ngữ nghiệp vụ, **không** tên class/file/hằng số. Quy trình gửi file: `tester-support` (md2pdf + `gchat_send_file.py --space ... --thread ...`).

## Pitfalls

- **Mã `VBG*` (VBG0408400, VBG040768) không có trong source vbsme và không có trong bảng mã lỗi AD_MESSAGE** — sinh ở tầng lõi/gateway. Đừng grep repo tìm định nghĩa (mất thời gian, không ra) — diễn giải nghiệp vụ: *"lõi báo không có bản ghi"* / *"lõi chưa có kết quả xử lý"*.
- **Không lấy comment/hằng số trong source làm sự thật về mã lỗi** — message khách thấy tra ở bảng mã lỗi theo `error_code_source` của scope-map.
- **"Chờ xử lý" không phải bug job**: đừng viết "job lỗi", "job kẹt", "cần restart job". Viết theo cơ chế: lõi chưa trả kết quả → hệ thống không có căn cứ chốt.
- Đừng nhầm **tra cứu trạng thái phía app** (khách bấm kiểm tra lại trên app) với **job đối soát** — cùng hỏi lõi theo TRN nhưng app không phải cơ chế chốt trạng thái; đừng lấy mốc thời gian app để giải thích lý do treo.
- Cửa sổ quét của job là điểm mấu chốt khi giải thích "sao mãi không tự đổi" — luôn nêu, đừng chỉ nói "job chạy mỗi 30 phút".

## Verification

- Câu trả lời nêu được: (1) mốc thời gian nào lõi không phản hồi, (2) kết quả lượt đối soát gần nhất cho giao dịch đó, (3) phạm vi ảnh hưởng cả đợt, (4) vì sao không tự đổi trạng thái, (5) việc cần xác minh tiếp — và **không** có tên class/file/hằng số.
- File PDF đã gửi lên đúng space/thread (đọc lại message vừa gửi để chắc).
