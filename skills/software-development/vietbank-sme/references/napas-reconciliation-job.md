# Job đối soát lệnh treo Napas 247 (auto reconciliation)

Trả lời nhanh "job quét lệnh nào", "sao lệnh này job không nhặt". Giá trị cấu hình đọc sống từ
`VBSMEONL.AD_CONFIG`, đừng nhớ theo trí nhớ.

## 1. Job nhặt những lệnh nào

- **Trạng thái:** chờ tra soát = timeout + pending.
- **Loại lệnh:** 2 loại chuyển tiền nhanh 247 — qua số tài khoản + qua số thẻ. Không loại nào khác.
- **Bắt buộc lệnh đã có mã tham chiếu đối tác (Napas TRN).**
- **Ngày tạo lệnh** phải nằm trong vòng `scan_days` ngày gần nhất.
- **Không lọc theo doanh nghiệp** → quét toàn hệ thống, kết quả lẫn lệnh của DN khác.

## 2. Vì sao chỉ Napas 2.0 — kiểm CẢ HAI lớp, đừng chỉ đọc filter

1. **Lớp filter:** lệnh phải có mã TRN — mã này chỉ sinh ra từ bước truy vấn Napas 2.0 (bước check
   tên người thụ hưởng). Không có TRN = không phải V2 = không vào job.
2. **Lớp trạng thái (dễ bỏ sót):** luồng Napas 1.0 **không có tra soát** — mọi lỗi hạch toán, kể cả
   treo/timeout, đều bị ghi đè thành "thất bại" ngay, nên lệnh V1 không bao giờ nằm ở trạng thái chờ
   tra soát. Job không thể gặp chúng dù filter có nhắc V2 hay không.

⇒ **Bài học chung:** câu "job X có nhặt loại lệnh Y không" phải xem cả logic **ghi đè trạng thái**
(quyết định lệnh có thể tồn tại ở trạng thái đó hay không) — chỉ đọc điều kiện filter là chưa đủ.

## 3. Khung giờ & nhịp chạy

- Cấu hình trong `AD_CONFIG` theo nhóm `financial.transaction.napas_v2.reconciliation.*`:
  `start_time`, `end_time`, `scan_days`.
- Ngoài khung `[start, end)` job **bỏ qua hoàn toàn** (chỉ log skip, không quét).
- `start >= end` ⇒ job tự skip (không hỗ trợ khung qua đêm).
- Đổi config là đổi hành vi job ngay → đọc giá trị hiện tại trước khi khẳng định "job chạy lúc nào".

## 4. Sau khi nhặt được lệnh

- Job **chỉ quét và đẩy từng lệnh** sang Kafka — job không tự gọi bank.
- Luồng tiêu thụ hỏi lại trạng thái với Napas theo mã TRN, rồi:
  - thành công → cập nhật lệnh sang thành công;
  - thất bại → đẩy sang luồng **hoàn tiền**;
  - vẫn pending → giữ nguyên, vòng quét sau nhặt lại (chừng nào còn trong `scan_days`).

## 5. Pitfall khi test / khi trả lời tester

- Lệnh treo quá `scan_days` ngày **không còn được nhặt** → test lệnh cũ rồi ngồi đợi job là vô nghĩa.
- Ngoài khung giờ job skip **im lặng** → đừng kết luận job lỗi.
- Job không lọc theo DN → soi theo mã giao dịch/trace, đừng soi theo doanh nghiệp.
- Danh sách lệnh chờ tra soát: trạng thái 5/6 (chi tiết status + query mẫu ở skill `vbsme-db-lookup`).
