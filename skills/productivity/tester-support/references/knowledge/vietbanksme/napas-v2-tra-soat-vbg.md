# NAPAS 2.0 — nút "Cập nhật lại trạng thái" và mã VBG0408400

Kiến thức nội bộ, đã kiểm chứng bằng log UAT 12/09/2026 (2 GD của tester: 016255144595006 và 016255144595007).
Trả lời tester bằng ngôn ngữ nghiệp vụ.

## Vì sao GD nằm ở "chờ tra soát"
- Lúc KH xác nhận lệnh, hệ thống gọi sang lõi để chuyển tiền. Lõi không phản hồi trong ~0,5s
  (đo thực tế 527–540 ms) → lỗi timeout nội bộ 998000 → mã 500069 `NAPAS_V2_TRANSFER_TIMEOUT`
  → GD chuyển sang *chờ tra soát*, chưa có kết quả cuối.

## Nút "Cập nhật lại trạng thái" làm gì
- Gọi lõi nghiệp vụ tra cứu trạng thái giao dịch NAPAS với 2 tham số: **mã tham chiếu (TRN)**
  và **thời điểm xác nhận**.
- Lõi trả `000 SUCCESSFULL` (responseCode 00, có mã giao dịch lõi) → chốt GD **thành công**.
- Lõi trả `400 No record found for TRN: <trn>` → hệ thống **không có căn cứ chốt**, giữ nguyên
  trạng thái chờ và trả mã **VBG0408400** cho app.
- Job đối soát nền gặp đúng lỗi này → log `Error processing reconciliation: ErrorCode:VBG0408400`
  rồi **không cập nhật gì**; GD vẫn treo và job lặp lại mỗi 30 phút.

## Mã 02VBG0408400
- Cấu trúc: `VBG` + `04` (khối giao dịch) + `08` (nghiệp vụ tra cứu trạng thái NAPAS) + `400` (mã lỗi cổng/lõi trả về).
- Nghĩa nghiệp vụ: **lõi/đối tác không có bản ghi nào cho mã tham chiếu của GD đó**.
- App hiển thị "Hệ thống đang bảo trì. Vui lòng thử lại sau! (02VBG0408400)" — đây là **câu mặc định**
  khi mã lỗi chưa có nội dung riêng trong bảng thông điệp, KHÔNG phải hệ thống bảo trì thật.
- Muốn biết vì sao lõi không có bản ghi → phải xem log phía cổng/lõi Vietbank (phía SME không có log đó).
- **Quy tắc (Hoàng chốt 12/09/2026): mọi mã lỗi bắt đầu bằng `VBG` là lỗi của CORE BANK.** Khi kết
  luận lỗi VBG, luôn trích nguyên đoạn log `CALL_REST` gọi sang bank (URL + body request + response
  bank trả về) để Hoàng xem — bằng chứng phía bank.

## Log mẫu UAT 12/09/2026
| Mã GD | Mã tham chiếu | Xác nhận | Bấm cập nhật | Lõi trả về | Kết quả |
|---|---|---|---|---|---|
| 016255144595006 | 6255VNTTA2FF4HVY | 14:36:24 (timeout) | 14:39:15 | 400 No record found | Báo lỗi VBG0408400, GD vẫn chờ |
| 016255144595007 | 6255VNTTA2FF4HVA | 14:36:13 (timeout) | 14:39:44 | 000 SUCCESSFULL + coreRef | Cập nhật thành công |

Trong ngày còn nhiều lệnh khác dính `No record found` (VD TRN `6255VNTTA2FF4HKE`) ⇒ UAT tồn
nhiều GD treo chờ tra soát mà tra soát không tự giải quyết được.

## Điểm nên báo dev xác nhận (KHÔNG tự cam kết sửa)
1. Mã VBG0408400 thiếu nội dung thông báo → app hiện câu "bảo trì" gây hiểu nhầm; nên có thông điệp riêng
   kiểu "không tìm thấy giao dịch tại lõi".
2. Thời gian chờ gọi lõi ở bước xác nhận rất ngắn (~0,5s) → dễ đẩy GD sang chờ tra soát dù lõi vẫn xử lý.
