# NAPAS 2.0 — mã risk của core, log rủi ro, và đối soát sau timeout

Kiến thức nội bộ (đã kiểm chứng bằng log UAT 09–12/09/2026). Trả lời tester bằng ngôn ngữ nghiệp vụ.

## Mã risk khi tạo lệnh

- Khi tra tên người hưởng qua core (NAPAS 2.0), core trả kèm **mã risk** — thực tế gặp `VB_RULE_0001`,
  `VB_RULE_0009`, `VB_RULE_0079`.
- **Mã risk LUÔN được lưu** vào thông tin lệnh ngay lúc tạo lệnh (cùng `napasRef`, `napasVersion=2`,
  `paymentCode`). ⇒ "tạo lệnh có lưu mã risk không" = **CÓ**.
- **Bản ghi log rủi ro riêng** (bảng NapasRiskTransaction) chỉ được tạo khi cấu hình
  `financial.transaction.napas_v2.check_risk_score.enable` = **BẬT** *và* mã risk có trong bảng cấu hình risk;
  khi đó cờ "đã kiểm tra risk" (`checkRiskScore`) = true.
  - Hành động cấu hình **STOP** → chặn ngay ở bước tạo lệnh.
  - **WARNING** → vẫn cho tạo lệnh nhưng ghi nội dung cảnh báo (vi/en) + tạo bản ghi log rủi ro.
  - Không có cấu hình cho mã đó → xử như nhánh tắt.
- Khi cấu hình **TẮT**: `checkRiskScore=false`, `riskAction=NO_ACTION` (**giá trị mặc định**, KHÔNG phải
  kết luận của core — đừng nói với tester rằng core xếp loại "không hành động"), không có bản ghi log rủi ro,
  và log có dòng `Napas Risk Score check is disabled. Risk Score: [<mã>]`.
- Hệ quả ở bước xác nhận: log ghi `NapasRiskTransactionModel not found for transactionId: <id>` ở mức
  **WARNING** rồi **vẫn chạy tiếp** — không làm giao dịch thất bại.
- Số liệu UAT 09–12/09/2026: 124 lần ghi nhận "kiểm tra risk đang tắt" (VB_RULE_0001: 99, VB_RULE_0079: 20,
  VB_RULE_0009: 5); 142 cảnh báo "không tìm thấy bản ghi rủi ro" thuộc **113 giao dịch**; 229 lượt có cờ
  kiểm tra risk = bật; cấu hình này được **nạp lại 24 lần** (đội test bật/tắt liên tục) ⇒ gặp lệnh có log
  rủi ro và lệnh không có là chuyện bình thường, phải xem **thời điểm tạo lệnh** mới kết luận được.

## Timeout khi xác nhận chuyển tiền NAPAS 2.0

- Mã lỗi **500069 = NAPAS_V2_TRANSFER_TIMEOUT**, log kèm `Client timeout. Error: Read timed out`,
  sự kiện `final_approved_failed`.
- Khác NAPAS 1.0: NAPAS 2.0 **không** đánh giao dịch thất bại mà giữ ở trạng thái **chờ tra soát**
  (nên tester thấy "giao dịch treo").
- Job đối soát NAPAS chạy định kỳ (thấy lúc **10:00**): gửi tra soát trạng thái sang core/NAPAS, nhận
  `responseCode = 00` → cập nhật lệnh sang **APPROVED**, ghi `coreRef` + `refThirdParty`.
  Log ở `worker-service` (topic `transaction.napas_reconciliation.*`), không phải napas-service.

## Ca mẫu đã tra (để đối chiếu)

`006254184594922` (txn 174345, 54.152, user daiviet3, người hưởng VikkiBank): tạo lệnh 11/09 18:01
(mã risk `VB_RULE_0079`, cờ kiểm tra risk **tắt**) → xác nhận 12/09 09:22 lỗi 500069 → 12/09 10:00:03
đối soát thành công, lệnh **APPROVED** (ref thứ ba `6255VNTTA2FF43E7`). Báo cáo cho tester:
`docs/qa/20260912-baocao-riskcore-006254184594922.md` (workspace vietbank-sme).
