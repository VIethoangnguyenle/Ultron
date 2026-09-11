---
name: api-contract-cards
description: Use when a client asks an API's JSON request/response. Generate verified samples.
---

# API Contract Cards (Q&A request/response cho client)

## Trọng tâm: JSON request / response

Client hỏi API thì thứ họ cần là **JSON request mẫu + JSON response mẫu + endpoint**, không phải văn xuôi.
Mọi câu trả lời phải bám 2 khối JSON đó; field/kiểu lấy từ hợp đồng thật.

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

## Sinh JSON request/response — script đã đóng gói (dùng luôn, đừng dựng lại)

```
scripts/api_card.py                       generator: the API -> JSON Schema + mẫu + validate
assets/cards/auth.login.app.json          thẻ đã kiểm chứng (App)
assets/cards/auth.login.web.json          thẻ đã kiểm chứng (Web)
assets/cards/auth.login_new_device.app.json
references/client-json-qa.md              playbook: câu hỏi client -> nguồn + khuôn trả lời
```

3 chế độ (chạy từ thư mục skill):
```
python3 scripts/api_card.py --out <dir>                    # sinh schema + mẫu + validate (exit 1 nếu FAIL)
python3 scripts/api_card.py --show auth.login.app          # in JSON mẫu để dán vào câu trả lời client
python3 scripts/api_card.py --check-payload <card> <file>  # soi payload client, chỉ đích danh field sai
```
Kiểm chứng cuối: **21/21 kiểm tra PASS, exit 0**; `--check-payload` bắt đúng sai enum / sai kiểu / field lạ.

Thẻ API **tự chứa** (cả `response_data_fields`) nên script không phụ thuộc file nào khác. Thêm API mới =
viết 1 file thẻ JSON vào `assets/cards/` rồi chạy lại. Script chỉ **sinh mẫu từ thẻ**, không phát minh field:
field/kiểu/enum/mã lỗi phải lấy từ hợp đồng thật.

## Quy trình dựng thẻ API / POC
1. Card JSON: endpoint, headers, request_fields, response_data_fields, errors, notes — mỗi field kèm `required`, `type`, `enum`, `example`, `note` tiếng Việt.
2. Sinh JSON Schema từ card -> sinh mẫu `request.min`, `request.full`, `response.success`, `response.error.<code>` (deterministic, không random: đổi version là diff ra ngay).
3. Validate mẫu bằng `jsonschema` (máy có sẵn 4.26). Mẫu sai schema = **chặn publish**, coi như test fail.
4. Mock server stdlib: trả đúng mẫu và **validate payload client gửi lên** -> chỉ đích danh field sai (tính năng "request của tôi sai ở đâu").
5. Tài liệu luồng cho client: sơ đồ tuần tự (mermaid) + bảng bước + thẻ JSON từng bước + "client phải làm gì" + bẫy; xuất PDF bằng `md2pdf.py`.

POC tham chiếu: `~/.hermes/reports/api-card-poc/` (thẻ auth, generator `build_poc.py`, `mock/mock_server.py`, `check_doc_drift.py`, PDF luồng đăng nhập, zip gửi khách).

6. **Cổng chặn lệch tài liệu**: `python3 check_doc_drift.py <repo>` so đường dẫn trong tài liệu/flow doc với registry; exit 1 khi lệch ⇒ gắn vào CI để tài liệu lệch hợp đồng là build đỏ. Sửa doc/thẻ xong phải chạy lại.

## Pitfalls (đã trả giá thật)
- **Kênh App trả HTTP 200 kể cả khi lỗi**; kênh Web trả 400 cho lỗi đầu vào. Client phải đọc `success`/`code` trong body. Ghi rõ vào thẻ.
- **`data` trong response lỗi** có thể là map `field -> thông báo` hoặc `null`; ở môi trường thật chi tiết field có thể rỗng -> schema cho `"type": ["object","null"]`, client có thông báo dự phòng theo `code`.
- **Mã thành công = `00`**. Catalog lỗi KHÔNG có dòng mã thành công -> đừng tự đặt mã (đã từng đặt sai `000000`).
- **Đường dẫn phía client có namespace miền**: `/api/v1/{app|web}/nonfinancial/auth/...`, khác hằng số path trong service (service khai `/api/v1/app` + `/auth`). Thứ tự tin cậy: catalog mã lỗi sinh từ hệ thống chạy > flow doc mới > hằng số/doc cũ. Grep full path trả 0 **KHÔNG** phải bằng chứng không tồn tại (path ghép từ nhiều hằng số). Chốt bằng curl: sai → 404. Máy soi lệch: `check_doc_drift.py`.
- **Tài liệu luồng cũ bị lệch đường dẫn** (đã gặp: doc đăng nhập thiếu `nonfinancial`) → sửa doc khi được phép, kèm ghi chú giải thích 2 tầng path; đừng chỉ sửa thẻ mà để doc cũ nằm đó.
- **Thông báo lỗi có chỗ trống động**: `{hotline}`, `{maxLoginFailures}`, `{duration}` do hệ thống điền -> client hiển thị nguyên văn, không tự ghép câu.
- **Enum chép nguyên văn**: LoginType `PASSWORD|BIOMETRIC`, BiometricType `FACE|TOUCH`, DeviceOs `IOS|ANDROID|WEB|UNKNOWN`.
- **Tên field thiết bị viết tắt**: `DT` (hệ điều hành), `E`, `PS`, `PM` (tên máy), `VER` (phiên bản app), `OV` (phiên bản OS). Copy sai tên = bị coi như thiếu dữ liệu.
- **Python dict-literal eval hết value**: `{"enum": f["enum"][0], ...}[f["type"]]` nổ `KeyError` với field string -> dùng `if/elif`.

## Ranh giới bảo mật (BẮT BUỘC)
Thẻ API **được** chứa: endpoint, header, JSON request/response, mã lỗi, mô tả nghiệp vụ.
Thẻ API **KHÔNG** chứa: tên class/file/method/hằng số, stack trace, log thô, tên service nội bộ, mục "vị trí triển khai (dành cho dev)", cơ chế mã hoá, mô tả hệ thống chạy bên trong.
Luồng cho client chỉ giữ: gọi API nào theo thứ tự nào, mang dữ liệu gì sang bước sau, lỗi thì làm gì — chi tiết nội bộ phải cắt trước khi ra ngoài (1 người duyệt ~30 phút/flow).
Tài liệu gửi client ghi rõ: "dữ liệu minh hoạ", "trợ lý tra cứu, không thay kênh hỗ trợ chính thức".
