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

## Nguồn thông tin "risk core" trên log (bổ sung 15/09/2026)

- Thông tin risk **xuất hiện sớm nhất ở khối tra cứu ngân hàng** (`bank-service`, `POST /api/v1/app/bank/validate-bene/napas`):
  gọi core `.../ibft/inquiryBenAccount` → `response.result` có `riskScore` (vd `VB_RULE_0001`), `trn`
  (= mã tham chiếu NAPAS, sau này là `napasRef`) và `paymentCode`. ⇒ Hỏi "core trả mã risk gì" thì
  tìm ở **bank-service**, không phải napas-service.
- `napas-service` giữ risk trong `metadata` của lệnh: `checkRiskScore`, `riskScore`, `riskAction`,
  `suspicious`, `enSuspiciousContent`/`viSuspiciousContent`, `napasRef`, `napasVersion`, `paymentCode`.
  ⚠️ `riskAction=NO_ACTION` là giá trị mặc định, KHÔNG phải kết luận của core; `suspicious=false` vẫn có
  thể đi kèm nội dung cảnh báo (người nhận thuộc danh sách nghi ngờ rủi ro).
- Cách kiểm chứng "có/không bản ghi rủi ro" **không cần DB** (UAT không có DB): bước xác nhận/duyệt nếu
  thiếu bản ghi rủi ro sẽ ghi cảnh báo `NapasRiskTransactionModel not found for transactionId: <id>`.
  Không thấy dòng này cho lệnh đang tra ⇒ lệnh đó CÓ bản ghi rủi ro.
- Bước **duyệt/từ chối cấp cuối KHÔNG gọi lại core/risk** — mã risk của lệnh vẫn là mã nhận lúc tạo lệnh.
  Sự kiện `transaction.batch_approved_success` / `transaction.batch_rejected_success` nằm ở
  **napas-service**, kèm stage *Soạn lệnh* / *Duyệt lệnh* + `note`. Phản hồi batch-confirm trả `code 00`
  **kể cả khi kết quả nghiệp vụ là TỪ CHỐI** ⇒ đừng đọc "mã 00" thành "duyệt thành công", phải xem
  `status` của từng stage.
- Khối duyệt (`approval-service`) **xoay vòng log theo pod** (chỉ giữ ~2 pod) ⇒ log ngày cũ thường đã
  mất; trace hành trình duyệt bằng log napas-service.
- Câu hỏi kiểu "… từ lúc tạo **đến duyệt thành công**" của tester có thể chỉ là *đến bước duyệt*: cứ dựng
  timeline thật, nói rõ kết cục thực tế (duyệt / từ chối), đừng mặc định là đã duyệt.

### Ca mẫu: lệnh 016256154595147 (UAT, 13/09/2026)

Tra tên người hưởng 15:29:48 (bank-service) → core trả `VB_RULE_0001` + `6256VNTTA2FF4NPR`; tạo lệnh
15:29:52→15:29:59 (transReqId 7025 / transId 174827; `checkRiskScore=TRUE`, có cảnh báo "danh sách nghi
ngờ rủi ro"); 15:31:34 khởi tạo duyệt cấp cuối (lô `016256154595149`) → 15:32:52 từ chối (note `tc`) →
15:32:58 xác thực Soft OTP → *Duyệt lệnh* = REJECTED, lệnh `TRANSACTION_REJECTED`.

### Ca mẫu lệnh ĐÃ duyệt thành công: 016257104595190 (UAT, 14/09/2026)

Tra tên người hưởng 10:19:34 (bank-service) → core trả `VB_RULE_0001` + `6257VNTTA2FFUYZF`; xác nhận tạo lệnh
10:19:46 (transId 174903, mã lệnh 7055, 87.870, `checkRiskScore=true`, có cảnh báo nghi ngờ rủi ro) →
*Duyệt lệnh* cấp 2 lúc 10:20:36 (ghi chú `ok`) → 10:20:39 xác thực Soft OTP (lô `016257104595191`) →
`TRANSACTION_SUCCESS`, `finalApproved=true`, `refThirdParty` khớp `napasRef` lúc tra tên.

⚠️ **Cờ `checkRiskScore` trên bản ghi tổng hợp SAU khi duyệt = `false`, dù lúc tạo/xác nhận = `true`** —
gặp ở CẢ 2 ca (147 và 190), còn `riskScore`/`riskAction`/cảnh báo thì giữ nguyên. Khi tester hỏi "risk core
có được lưu suốt hành trình không" thì phải nói rõ: **mã risk + cảnh báo giữ nguyên, riêng cờ kiểm tra risk
hiển thị lại là false ở bản ghi sau duyệt** — đừng hứa hẹn/hiểu sai thành "mất risk".

### Mẹo dựng "đến duyệt thành công"

Đủ 3 mốc là kết luận được duyệt thành công: (1) event `transaction.batch_approved_success`;
(2) trong payload có stage level 2 *Duyệt lệnh* = APPROVED + `finalApproved=true`; (3) `status=TRANSACTION_SUCCESS`
+ `refThirdParty` khớp `napasRef`/mã tra cứu NAPAS.
Xác nhận chéo: log `approval-service` có mục `POST:/api/v1/app/completed-trans-reqs` (danh sách lệnh hoàn
thành) — entry của lệnh hiện `status: APPROVED` kèm `refThirdParty` và cờ `suspicious`.

## Ca mẫu đã tra (để đối chiếu)

`006254184594922` (txn 174345, 54.152, user daiviet3, người hưởng VikkiBank): tạo lệnh 11/09 18:01
(mã risk `VB_RULE_0079`, cờ kiểm tra risk **tắt**) → xác nhận 12/09 09:22 lỗi 500069 → 12/09 10:00:03
đối soát thành công, lệnh **APPROVED** (ref thứ ba `6255VNTTA2FF43E7`). Báo cáo cho tester:
`docs/qa/20260912-baocao-riskcore-006254184594922.md` (workspace vietbank-sme).
