---
name: api-endpoint-discovery
description: Use when asked which API/endpoint does X.
version: 1.0.0
---

# Chốt endpoint theo nghiệp vụ ("API nào để làm X")

## Khi nào dùng
Dev/tester hỏi: "api nào để lấy X", "field filter tên gì", "client phải gọi API nào". Áp cho repo
nhiều module (vbsme: auth-service, approval-service, transaction-service, integration-service…).

Đích cuối của câu trả lời là **bảng endpoint + field**, không phải văn xuôi. Người hỏi là tester thì
bọc bảng trong code block; là dev thì được kèm path API (xem "Ranh giới" cuối bài).

## Recipe — chạy theo thứ tự, ĐỪNG đoán tên tiếng Anh

1. **Grep mô tả Swagger tiếng Việt.** Field/nghiệp vụ trong code được mô tả bằng tiếng Việt, nên từ khoá
   tiếng Anh hay trượt. Grep chính cách người dùng gọi nghiệp vụ:
   `git grep -n -i "người tạo lệnh" <ref> -- "*.java"`
   ⇒ ra `@Schema(description = "Id người tạo lệnh")` trên **request model** (chỗ khai filter thật) và
   response model. Đây là mỏ neo chắc nhất để vào đúng vùng code.
2. **Từ request model → controller.** `@PostMapping` khai ở **interface** controller, path gốc ở
   `@RequestMapping` của class impl (app và web tách riêng) ⇒ phải ghép lại mới ra full path. Path trong
   `EndpointConstants` là hằng số rời ghép nhiều mảnh ⇒ **grep full path ra 0 KHÔNG phải bằng chứng không
   tồn tại**.
3. **Chốt nguồn định danh.** Xem field nào lấy từ session (`BaseSessionRequest.currentCompany` /
   `currentCustomer`, thường có `@JsonIgnore`) và field nào client truyền trong body. Người hỏi kiểu
   "theo company" thường tưởng phải truyền `companyId` — nhiều endpoint **lấy công ty theo session, không
   nhận tham số**; nói rõ điểm này kẻo họ test sai.
4. **Đọc source theo REF, không theo working tree**: `git show <ref>:<path>`, `git grep … <ref>`. Working
   tree có thể đang ở nhánh feature khác ⇒ kết luận theo working tree là sai mốc.
5. **Kiểm tra biến thể**: cùng nghiệp vụ thường có 3 bản — `app`, `web`, và bản cho đối tác ở
   `integration-service` (ký checksum, tham số định danh nằm trong body). Liệt kê đủ rồi người hỏi tự chọn.
6. **Nếu không có API "chỉ lấy bản ghi có X"** (vd "chỉ người ĐÃ tạo lệnh") ⇒ nói thẳng là không có API
   riêng: query danh sách rồi distinct theo field id, đừng bịa endpoint.

## Trả lời
- Bảng `endpoint | định danh (session hay body) | trả về gì`, trong code block.
- Nêu mốc đã đọc (nhánh/ref) — tránh người đọc tin vào bản đã cũ.
- Ghi rõ field mà API *đầu cuối* nhận để ghép vào (vd filter danh sách lệnh nhận `createdCustomerId` = `id`
  trả về từ API danh sách người dùng).

## Pitfalls (đã trả giá thật)
- **Tìm endpoint bằng UA graph với từ khoá tiếng Anh ra nhiễu**: `query_nodes("maker list company")` trả về
  cả loạt module không liên quan. Graph để lấy **luồng/bước**; muốn chốt endpoint + field thì grep source.
  Keyword search chỉ hữu ích khi khớp đúng tên nghiệp vụ như trong code.
- **Full-path grep trả 0** không chứng minh endpoint không tồn tại (path ghép từ nhiều hằng số) — luôn dựng
  lại path từ interface controller + impl `@RequestMapping`.
- **Đừng lẫn "danh sách nhân viên công ty" với "người đã tạo lệnh"**: API nhóm đầu trả toàn bộ nhân viên
  theo công ty; nhóm sau phải suy ra từ danh sách bản ghi.
- Luôn nói mốc nhánh/ref trong câu trả lời (vbsme: `origin/dev-sit`).

## Ranh giới
- Group dự án: được kèm **path API** khi người hỏi là dev; **không** dán source, tên class/file/method,
  stack trace, không liệt kê file `.java`.
- Kết quả đã chốt cho vbsme (người dùng công ty, filter người tạo lệnh): `references/vbsme-company-users.md`.
