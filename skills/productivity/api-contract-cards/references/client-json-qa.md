# Playbook: trả lời client về JSON request/response

## Câu hỏi client hay gặp -> lấy ở đâu

| Client hỏi | Trả lời bằng | Nguồn |
|---|---|---|
| "JSON request mẫu là gì?" | request tối thiểu + đầy đủ | `scripts/api_card.py --show <card>` |
| "Field nào bắt buộc, kiểu gì, độ dài?" | bảng field (tên · bắt buộc · kiểu · enum · ghi chú) | `request_fields` trong thẻ |
| "Response thành công trông thế nào?" | JSON mẫu (code `00`, `des`/`messageCode` rỗng) | thẻ / `--show` |
| "Mã lỗi X nghĩa gì, sửa sao?" | bảng CODE · nghĩa · nguyên nhân · cách xử lý | `errors` trong thẻ + `VBSMEONL.AD_MESSAGE` |
| "Request của tôi sai ở đâu?" | danh sách field sai + payload đã sửa | `--check-payload <card> payload.json` |
| "Luồng này gọi API nào theo thứ tự nào?" | chuỗi bước + dữ liệu truyền tay | thẻ cùng `flow`, `flow_step` |

## Khuôn trả lời (bám câu hỏi, không lan man)

1. Dòng đầu: `<METHOD> <path>` + version.
2. Code block JSON: request tối thiểu, rồi request đầy đủ.
3. Code block JSON: response thành công.
4. Nếu câu hỏi về lỗi: bảng mã lỗi trong code block (CODE · nghĩa · nguyên nhân · cách xử lý).
5. Nếu client dán payload: chỉ từng field sai + payload đã sửa.
6. Đóng bằng 1 dòng rào: "dữ liệu minh hoạ, theo version <x>; cần xác nhận lại khi lên version".

JSON phải dán được vào Postman/curl là chạy được. Không kèm tên class/file/method/hằng số, không kèm mục "vị trí triển khai".

## Ví dụ ngắn

Client: "cho mình xin JSON request login bên App"
-> trả tối thiểu `{"username":"namdx"}` + đầy đủ 19 field (copy từ `--show auth.login.app`), kèm note: App trả HTTP 200 cả khi lỗi, phải đọc `code` trong body.

Client: "mã 100008 là gì?"
-> "Tên đăng nhập hoặc mật khẩu không hợp lệ" — sai tài khoản/mật khẩu; kiểm tra lại thông tin, sai quá số lần sẽ tạm khoá tài khoản (lấy từ `errors` của thẻ, đối chiếu `VBSMEONL.AD_MESSAGE`).

## Thêm API mới (khi client hỏi API chưa có thẻ)

1. Khoanh vùng API: controller/DTO trong repo hoặc api-docs (springdoc) của service -> field, kiểu, enum.
2. Đối chiếu mã lỗi với `VBSMEONL.AD_MESSAGE` (SIT) — không tin bảng QA 100%.
3. Viết file thẻ JSON tự chứa vào `assets/cards/` (copy khuôn thẻ có sẵn, đổi `card_id`/`path`/field/errors).
4. `python3 scripts/api_card.py --out <dir>` -> phải 0 FAIL mới dùng thẻ để trả lời.
5. Nhắc lại bài học trace: đường dẫn client có thể có namespace miền (vd `nonfinancial`) khác khai báo nội bộ; grep full path trả 0 không phải bằng chứng không tồn tại.
