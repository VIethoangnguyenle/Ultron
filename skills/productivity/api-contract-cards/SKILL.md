---
name: api-contract-cards
description: Use when building client API Q&A cards, samples, mock.
---

# API Contract Cards (Q&A request/response cho client)

## Khi nào dùng
- Client/đối tác hỏi: field này bắt buộc không, JSON request mẫu là gì, response này nghĩa gì, mã lỗi X sửa sao, luồng login gồm bước nào.
- Cần dựng mẫu request/response, mock server, hoặc tài liệu luồng cho client.

## Ba mức câu hỏi phải phục vụ
```
MỨC 1 FIELD  "field này bắt buộc không, format gì?"   -> schema 1 API
MỨC 2 CASE   "mã lỗi này nghĩa gì, sửa sao?"          -> mã lỗi + mẫu response lỗi
MỨC 3 FLOW   "luồng login request/response là gì?"    -> chuỗi bước + dữ liệu truyền tay (client hỏi NHIỀU NHẤT)
```
Đơn vị nhỏ nhất = **thẻ API**: endpoint + headers + JSON request (tối thiểu + đầy đủ) + JSON response + mã lỗi + version.
Viết 1 lần cho mỗi API: luồng, mã lỗi, validator payload đều ăn chung từ thẻ đó.

## Nguồn dữ liệu THẬT (không bịa)
| Cần gì | Lấy ở đâu |
|---|---|
| endpoint + field + kiểu dữ liệu | api-docs (springdoc) của service, hoặc DTO trong repo |
| mã lỗi + thông báo tiếng Việt | bảng thông báo SIT `VBSMEONL.AD_MESSAGE` (cột `CODE`, `VI_CONTENT`, `EN_CONTENT`, `IS_ACTIVE`) |
| mã lỗi gắn với API nào | `docs/qa/2026-09-09-ma-loi-ad-message-tra-cuu-log.md` |
| module + tên hằng của mã lỗi | `docs/error-code-mapping.md` |
| luồng nghiệp vụ | `docs/flows/*.md` |

Đối chiếu mã lỗi bằng DB, đừng tin bảng QA 100%:
```sql
SELECT CODE, VI_CONTENT FROM VBSMEONL.AD_MESSAGE WHERE CODE IN ('100005','100008','100013')
```

## Quy trình dựng thẻ API / POC
1. Card JSON: endpoint, headers, request_fields, response_data_fields, errors, notes — mỗi field kèm `required`, `type`, `enum`, `example`, `note` tiếng Việt.
2. Sinh JSON Schema từ card -> sinh mẫu `request.min`, `request.full`, `response.success`, `response.error.<code>` (deterministic, không random: đổi version là diff ra ngay).
3. Validate mẫu bằng `jsonschema` (máy có sẵn 4.26). Mẫu sai schema = **chặn publish**, coi như test fail.
4. Mock server stdlib: trả đúng mẫu và **validate payload client gửi lên** -> chỉ đích danh field sai (tính năng "request của tôi sai ở đâu").
5. Tài liệu luồng cho client: sơ đồ tuần tự (mermaid) + bảng bước + thẻ JSON từng bước + "client phải làm gì" + bẫy; xuất PDF bằng `md2pdf.py`.

POC tham chiếu: `~/.hermes/reports/api-card-poc/` (thẻ auth, generator `build_poc.py`, `mock/mock_server.py`, PDF luồng đăng nhập, zip gửi khách).

## Pitfalls (đã trả giá thật)
- **Kênh App trả HTTP 200 kể cả khi lỗi**; kênh Web trả 400 cho lỗi đầu vào. Client phải đọc `success`/`code` trong body. Ghi rõ vào thẻ.
- **`data` trong response lỗi** có thể là map `field -> thông báo` hoặc `null`; ở môi trường thật chi tiết field có thể rỗng -> schema cho `"type": ["object","null"]`, client có thông báo dự phòng theo `code`.
- **Mã thành công = `00`**. Catalog lỗi KHÔNG có dòng mã thành công -> đừng tự đặt mã (đã từng đặt sai `000000`).
- **Đường dẫn phía client có namespace `nonfinancial`**: `/api/v1/{app|web}/nonfinancial/auth/...`, khác hằng số path trong service. Kiểm tra lại bằng flow doc + catalog QA trước khi đưa vào thẻ.
- **Thông báo lỗi có chỗ trống động**: `{hotline}`, `{maxLoginFailures}`, `{duration}` do hệ thống điền -> client hiển thị nguyên văn, không tự ghép câu.
- **Enum chép nguyên văn**: LoginType `PASSWORD|BIOMETRIC`, BiometricType `FACE|TOUCH`, DeviceOs `IOS|ANDROID|WEB|UNKNOWN`.
- **Tên field thiết bị viết tắt**: `DT` (hệ điều hành), `E`, `PS`, `PM` (tên máy), `VER` (phiên bản app), `OV` (phiên bản OS). Copy sai tên = bị coi như thiếu dữ liệu.
- **Python dict-literal eval hết value**: `{"enum": f["enum"][0], ...}[f["type"]]` nổ `KeyError` với field string -> dùng `if/elif`.

## Ranh giới bảo mật (BẮT BUỘC)
Thẻ API **được** chứa: endpoint, header, JSON request/response, mã lỗi, mô tả nghiệp vụ.
Thẻ API **KHÔNG** chứa: tên class/file/method/hằng số, stack trace, log thô, tên service nội bộ, mục "vị trí triển khai (dành cho dev)", cơ chế mã hoá, mô tả hệ thống chạy bên trong.
Luồng cho client chỉ giữ: gọi API nào theo thứ tự nào, mang dữ liệu gì sang bước sau, lỗi thì làm gì — chi tiết nội bộ phải cắt trước khi ra ngoài (1 người duyệt ~30 phút/flow).
Tài liệu gửi client ghi rõ: "dữ liệu minh hoạ", "trợ lý tra cứu, không thay kênh hỗ trợ chính thức".
