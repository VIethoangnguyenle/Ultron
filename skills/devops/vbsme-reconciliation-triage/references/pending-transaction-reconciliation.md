# Lớp việc: giao dịch 247 treo "Chờ xử lý" — đọc job đối soát NAPAS

## Đường đi giao dịch 247 (từ duyệt cuối trở đi)

1. Tạo lệnh (init) → chờ duyệt → duyệt cấp → **duyệt cuối**: xác thực OTP/Facepay → gọi lõi chuyển tiền.
2. **TRN** (mã tham chiếu NAPAS) có thời gian sống = `financial.transaction.napas_v2.trn.ttl_hours`. Hết hạn khi mở/duyệt lệnh → log ghi `Napas V2 TRN expired, re-inquiry for fresh napasRef` → hệ thống **cấp TRN mới**. Vì vậy TRN trong log duyệt cuối khác TRN lúc tạo lệnh — **không phải lỗi**, đừng báo nhầm.
3. Tại bước gọi lõi, nếu lõi **không phản hồi** trong `financial.transaction.timeout.napas_transfer` (ms): bước CALL_REST có `response: null` → lỗi **998000** → khách thấy **500069** ("Giao dịch đang chờ xử lý… liên hệ tổng đài") → giao dịch về trạng thái **Chờ xử lý**. Lõi trả mã **68** (nhóm quá thời gian / chưa có kết quả) → lỗi **VBG040768** → treo tương tự.
4. Khách tự kiểm tra lại giao dịch chờ xử lý trên app → hệ thống hỏi lõi theo TRN, kết quả y hệt lượt đối soát. Đây **không phải** cơ chế chốt trạng thái, chỉ là tra cứu.

## Đọc kết quả job đối soát ở đâu (worker-service)

Mỗi giao dịch được đối soát = 1 container trong log `worker-service` (`sme-worker-<pod>.log`), `requestId` dạng `NapasRecon-<traceNo>`, Kafka topic `transaction.napas_reconciliation.process_item`. Chuỗi bước: `Processing reconciliation: traceNo=<trace>, refThirdParty=<TRN>` → CALL_REST sang lõi (`ibft/transactionStatus`) → 3 kết cục:

| Kết cục trong log | Nghĩa nghiệp vụ | Trạng thái giao dịch |
|---|---|---|
| `Reconciled ... → TRANSACTION_SUCCESS` | Lõi xác nhận thành công | Cập nhật **thành công** |
| `Reconciled ... → TRANSACTION_PENDING` | Lõi có bản ghi nhưng chưa có kết quả cuối | Giữ chờ, quét lại lượt sau (bình thường) |
| `Error processing reconciliation: ErrorCode:VBG0408400` | Lõi trả **"No record found for TRN"** | **Treo vô thời hạn** — không có căn cứ chốt |

- **Thống kê theo CẢ LƯỢT chạy**, không chỉ giao dịch được hỏi: đếm theo `requestId`/timestamp của lượt, phân loại 3 nhóm trên rồi mới trả lời "phạm vi ảnh hưởng". Lỗi kiểu này thường đến **theo đợt** (lõi không phản hồi trong vài phút → hàng chục giao dịch cùng treo).
- Job chạy định kỳ theo `financial.transaction.napas_v2.reconciliation.start_time`/`end_time` (UAT thấy mỗi 30 phút), và **chỉ quét giao dịch treo trong `financial.transaction.napas_v2.reconciliation.scan_days` ngày gần nhất**. Quá cửa sổ đó mà lõi vẫn chưa có kết quả → giao dịch **không còn được quét** → treo tới khi xử lý tay. Đây là câu trả lời chuẩn cho "sao job không tự đổi trạng thái".

## Cách dựng timeline của 1 giao dịch (đủ để viết báo cáo)

Từ log, gom theo trace/TRN: tạo lệnh (init) → duyệt (approval-service) → duyệt cuối + cấp lại TRN → gọi lõi (napas-service, kèm `response: null` hoặc mã lỗi lõi) → mã khách thấy (500069) → các lượt đối soát (worker-service, 10:00 & 10:30…) → thao tác khách trên app. Mỗi mốc lấy đúng timestamp trong log, đừng suy diễn.

## Việc cần xác minh tiếp (đưa vào báo cáo, không tự kết luận)

- Phía **lõi/NAPAS**: vì sao không có bản ghi TRN cho các yêu cầu chuyển tiền đã gửi trong đợt (khả năng request không tới được/không được ghi nhận lúc lõi treo).
- Có cần **ngưỡng xử lý** (số lần tra soát / số giờ) để chuyển giao dịch treo sang "cần xử lý thủ công" thay vì treo im lặng — nêu để BA/dev xem xét, không tự quyết.
- Dữ liệu test UAT đang treo: đề nghị xử lý/dọn riêng nếu cần test lại luồng.
