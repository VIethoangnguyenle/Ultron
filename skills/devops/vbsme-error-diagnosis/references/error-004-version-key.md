# Nhóm lỗi `004xxx` — phiên bản ứng dụng & khoá mặc định (key default)

Tra nhanh: `SELECT VI_CONTENT, EN_CONTENT, DESCRIPTION FROM VBSMEONL.AD_MESSAGE WHERE CODE IN ('004001','004002','004003','004004','004005')`.

| Mã | Constant (nội bộ) | Nội dung | Nghĩa |
|---|---|---|---|
| `004001` | INVALID_APP_VERSION | Phiên bản ứng dụng không được hỗ trợ… | version không có trong bảng quản lý phiên bản |
| `004002` | FORCE_UPDATE_APP | Ứng dụng đã có phiên bản mới trên chợ… | bắt buộc/khuyến nghị cập nhật |
| `004003` | FORCE_UPDATE_APP_SERVICE | Vui lòng cập nhật ứng dụng để dùng tính năng này | force theo dịch vụ |
| `004004` | UNKNOWN_ERROR | Lỗi chưa xác định với phiên bản hiện tại | nhánh mặc định khi bước kiểm tra version ném lỗi khác |
| `004005` | NOT_SUPPORT_KEY_ID | **Thiết bị không hợp lệ**… | DESCRIPTION trong AD_MESSAGE: *Key sử dụng cho phiên bản không đúng* |

## Cơ chế 004005 (đã trace source — KHÔNG đưa tên class/file ra group)

1. Mỗi bản app **theo OS** được gán 1 **khoá mặc định**: `OMNI_APP_VERSION.KEYDEFAULT` (cột KEY_NAME=version, KEYDEFAULT=khoá).
2. Mốc *miễn kiểm tra khoá* theo OS nằm ở `AD_CONFIG`: `auth.last_version_not_check_key_android` / `..._ios` (SIT = `0.0.1` ⇒ thực tế **mọi bản đang test đều bị kiểm tra**).
3. Khi **login app**, hệ thống lấy OS + appVersion của thiết bị + keyId của phiên (`UserDetails.keyId`) rồi đối chiếu với khoá mặc định của bản app đó. Lệch / không tìm thấy ⇒ ném lỗi, và **mọi exception ở bước này đều bị map về `004005`** (nên 004005 là mã "hứng" chung của bước kiểm tra khoá, không chỉ 1 tình huống).
4. Bước này chạy ở: đăng nhập app thường, đăng nhập/kích hoạt **thiết bị mới**, và cả khi kiểm tra phiên (`ValidateSession`) ⇒ 004005 có thể xuất hiện ở nhiều API, không riêng `/app/auth/login`.
5. Đây là chặn ở **đầu luồng** — trước khi kiểm mật khẩu/OTP, nên khách không sai tài khoản vẫn bị.

## Checklist trả cho tester

1. Bản app đang cài có **số version nằm trong danh sách phiên bản của môi trường** không (`SELECT VERSION_NAME, OS, VERSION_NUMBER, KEYDEFAULT, STATUS FROM VBSMEONL.OMNI_APP_VERSION`). Thiếu version ⇒ thường là 004001.
2. **Khoá của bản build phải khớp khoá mặc định đã cấu hình** cho version đó — nguyên nhân phổ biến nhất: **cài đè / giữ dữ liệu app từ bản build khác** (khoá cũ còn sót) hoặc dùng build của môi trường khác.
3. Build mới vừa phát hành: phải **bổ sung dòng version + khoá mặc định** cho môi trường trước, nếu không login vẫn lỗi.
4. Vừa sửa cấu hình version/khoá ⇒ cần **nạp lại cache / restart service** mới có hiệu lực.

## Mã dài trong message

Message trả ra app có dạng `... (03004005) (<requestId>)`: số trong ngoặc **không có trong AD_MESSAGE** — mã nghiệp vụ cần tra là `004005`, đuôi còn lại là `requestId` để lấy log. Khi SIT không có log tập trung ⇒ chỉ giải thích + checklist; UAT/LIVE ⇒ lấy log theo `requestId`.
