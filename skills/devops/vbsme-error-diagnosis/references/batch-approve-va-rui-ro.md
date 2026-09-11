# Duyệt hàng loạt (batch approve) — luồng xử lý & mã lỗi

## Luồng
1. Maker tạo lệnh → lệnh ở trạng thái chờ duyệt cấp tiếp theo (active trans req).
2. Checker vào danh sách lệnh chờ duyệt (dùng CHUNG cho duyệt đơn lẻ và duyệt hàng loạt — không có danh sách riêng).
3. Bấm duyệt hàng loạt → hệ thống **khởi tạo phiên duyệt gộp**: tạo 1 lệnh gộp (tham chiếu) gắn danh sách lệnh con + trả về phương thức xác thực
 → checker xác thực (Facepay + Soft OTP) → hoàn tất, lệnh con mới đổi trạng thái.
   * Nếu bỏ dở ở bước xác thực: lệnh con VẪN là "chờ duyệt" ⇒ vẫn hiển thị trong danh sách. Không phải lỗi.

## Ràng buộc rủi ro (quan trọng khi tester hỏi "vẫn còn hiển thị")
- Lệnh có **mã cảnh báo tài khoản thụ hưởng** (dữ liệu rủi ro) KHÔNG được duyệt hàng loạt → báo lỗi mã `501012`.
- Ràng buộc chỉ kiểm tra **tại thời điểm bấm duyệt** (bước khởi tạo), KHÔNG lọc/ẩn lệnh khỏi danh sách chờ duyệt.
  ⇒ Lệnh có data rủi ro vẫn HIỂN THỊ trong chức năng duyệt hàng loạt; chỉ bị chặn khi thao tác.
- Bằng chứng để phân biệt "có rủi ro" vs "không": nếu khởi tạo duyệt hàng loạt trả về thành công thì các lệnh đó KHÔNG có cảnh báo rủi ro
  (nếu có đã bị chặn `501012`).

## Mã lỗi hay gặp

```
501012  Không cho phép duyệt hàng loạt lệnh có cảnh báo TK thụ hưởng
500037  Tài khoản chưa đăng ký Soft OTP cho giao dịch (chặn khởi tạo duyệt hàng loạt trên web/IB)
500067  Điểm rủi ro Napas chặn ở bước tạo lệnh
500068  Điểm rủi ro Napas chặn khi làm mới tham chiếu ở bước duyệt
```

## Dữ liệu rủi ro
- Điểm rủi ro Napas (risk score / rule code) + hành động (không làm gì / cảnh báo / chặn) được trả về ở bước tạo lệnh;
  mã cảnh báo TK thụ hưởng lưu trên lệnh là nguồn để chặn duyệt hàng loạt.
- Luật rủi ro có thể được cập nhật lại (reload config) trong lúc test → nếu lệnh tạo TRƯỚC lúc luật hiệu lực thì không có data rủi ro.
