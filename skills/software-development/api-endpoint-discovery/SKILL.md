---
name: api-endpoint-discovery
description: "Use when asked which API/endpoint does X, or which address an env calls an external system at."
version: 1.0.0
---

# Chốt endpoint theo nghiệp vụ ("API nào để làm X")

## Khi nào dùng
Dev/tester hỏi: "api nào để lấy X", "field filter tên gì", "client phải gọi API nào". Áp cho repo
nhiều module (vbsme: auth-service, approval-service, transaction-service, integration-service…).

Đích cuối của câu trả lời là **bảng endpoint + field**, không phải văn xuôi. Người hỏi là tester thì
bọc bảng trong code block; là dev thì được kèm path API (xem "Ranh giới" cuối bài).

## Recipe — chạy theo thứ tự, ĐỪNG đoán tên tiếng Anh

0. **Tra thẻ nghiệp vụ trước, chỉ trace khi MISS.** `python3 ~/.hermes/scripts/bizcard.py find "<câu hỏi>"`
   (thẻ nằm ở `docs/knowledge/cards/`, mỗi thẻ có sẵn danh sách đường dẫn + bằng chứng + mã lỗi). Câu hỏi
   "API nào để làm X" hay đã có thẻ rồi — trace lại từ đầu là đốt thời gian vô ích.

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
   tree có thể đang ở nhánh feature khác ⇒ kết luận theo working tree là sai mốc. **Kiểm tra service có
   source trong checkout chưa** trước khi grep: `find <service> -name '*.java' | wc -l` — service chỉ nằm ở
   nhánh khác thì thư mục tại chỗ rỗng, grep ra 0 là do THIẾU SOURCE chứ không phải endpoint không tồn tại.
5. **Kiểm tra biến thể**: cùng nghiệp vụ thường có 3 bản — `app`, `web`, và bản cho đối tác ở
   `integration-service` (ký checksum, tham số định danh nằm trong body). Liệt kê đủ rồi người hỏi tự chọn.
6. **Nếu không có API "chỉ lấy bản ghi có X"** (vd "chỉ người ĐÃ tạo lệnh") ⇒ nói thẳng là không có API
   riêng: query danh sách rồi distinct theo field id, đừng bịa endpoint.

## Địa chỉ dịch vụ ngoài theo môi trường ("ở SIT đang gọi <đối tác> ở IP nào?")

Cùng họ câu hỏi "endpoint nào", nhưng đích là **hệ thống ngoài** (payment gateway, VB gateway, eKYC…)
chứ không phải API nội bộ ⇒ đi theo cây config, không grep controller.

1. **Source chỉ khai tên biến, không chứa giá trị.** `common.client.external.<đối tác>.uri` trong
   `config/application-thirdparty-config.yml` thường là `${ENV_VAR}` ⇒ grep source chỉ ra key, không ra IP.
2. **Giá trị theo môi trường nằm ở cây deploy**, không nằm trong repo app:
   `test-workload/vnp-ocp-svc/<app>/<cluster>/config-map-*thirdparty*.yaml` — configmap đã triển khai, URI điền cứng.
3. **Chốt cluster ↔ môi trường bằng host** trong file deploy cùng thư mục (vd `<app>-sit.vnpaytest.vn` = SIT).
   Không suy môi trường từ tên thư mục cluster.
4. **`.env` của repo app là cấu hình dev local** — trùng giá trị với SIT chỉ là tiện lợi, không phải bằng chứng
   cho môi trường đang được hỏi.
5. **Trả lời:** 1 bảng `MÔI TRƯỜNG | ĐÍCH GỌI RA` trong code block + 1 câu nêu nguồn (file deploy nào).
   Nếu có quyền `kubectl` vào cluster thì đọc configmap sống để xác nhận; không thì nói rõ kết luận lấy từ
   config trong repo (bản sao có thể cũ hơn cluster) — đừng trình bày như đã kiểm tra trên môi trường chạy.
6. **Đích gọi ra ≠ IP nguồn.** "IP gọi đối tác là bao nhiêu" hay bị hiểu hai chiều: đích trong config là địa
   chỉ mình gọi tới; IP mà đối tác thấy và phải whitelist (egress/NAT) **không** nằm trong config app. Trả lời
   theo nghĩa thứ nhất rồi nói rõ chiều còn lại phải lấy từ hạ tầng — đừng gộp thành một số.

## Chốt danh sách đường dẫn theo môi trường (bảng đăng ký SYS_MID)

Cùng họ câu hỏi "service này có những API nào": ngoài source, đọc **bảng đăng ký đường dẫn của chính
service trên môi trường** — `SYS_MID` trong DB của service (vbsme: `VBSMERLE` cho `rle-service`):

`SELECT ID, DESCRIPTION, SERVICE_NAME, IS_ACTIVE, IS_FINANCE, SECURITY_TYPE FROM <SCHEMA>.SYS_MID WHERE LOWER(ID) LIKE '%<service>%'`

`ID` = đường dẫn, `DESCRIPTION` = mô tả nghiệp vụ tiếng Việt. Đây là bằng chứng mạnh nhất cho câu "môi
trường đang có đường dẫn nào", đồng thời cho sẵn mô tả nghiệp vụ để trả lời người không đọc code. Đường
dẫn có trong source mà thiếu dòng `SYS_MID` (và `SYS_USER_ENDPOINT`) thì lời gọi bị chặn ngay ở bước kiểm
đường dẫn — nhớ nói điểm này khi người hỏi đang truy lỗi gọi API.

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
- **Thư mục service rỗng trong working tree KHÔNG có nghĩa service không có API**: vbsme `rle-service/` ở
  nhánh làm việc chỉ còn `build/`, source nằm ở nhánh khác (`origin/dev-sit`). Kết luận "không có endpoint"
  từ một lần grep trong thư mục rỗng là sai — kiểm `find <service> -name '*.java' | wc -l` trước, rồi grep
  theo ref (`git grep -n -i "<từ khoá>" origin/dev-sit -- "<service>/*"`).
- **Nhiều đường dẫn gần giống nhau**: khi một nghiệp vụ có 2 đường cùng nghĩa (vbsme: hoàn hạn mức có
  `revert-transaction` theo danh sách giao dịch và `refund-transaction` theo mã tra soát) thì liệt kê ĐỦ
  rồi phân biệt bằng mô tả đăng ký + handler tương ứng — trả lời "API hoàn là X" khi có hai đường là trả
  lời thiếu, người test sẽ chạy sai luồng.
- Luôn nói mốc nhánh/ref trong câu trả lời (vbsme: `origin/dev-sit`).
- **File config đối tác chứa cả `private-key`/`public-key`** ⇒ khi trích chỉ lấy đúng dòng `uri`; không dán
  cả block config, không đưa key sang group.
- **Đừng trộn đối tác giữa các dự án**: nhiều repo trong cùng workspace đều khai "payment gateway" (bản digital,
  terra-bff, teko-payment…) — chỉ trả lời cho dự án của group/người đang hỏi.

## Ranh giới
- Group dự án: được kèm **path API** khi người hỏi là dev; **không** dán source, tên class/file/method,
  stack trace, không liệt kê file `.java`.
- Kết quả đã chốt cho vbsme (người dùng công ty, filter người tạo lệnh): `references/vbsme-company-users.md`.
- Cây config theo môi trường + bảng đích gọi ra hệ thống ngoài đã chốt: `references/env-external-endpoints.md`.
