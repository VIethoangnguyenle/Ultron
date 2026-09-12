# Google OAuth — bộ scope theo dịch vụ (least privilege)

`GSETUP="python3 ${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/setup.py"`

## Bảng service → scope

| `--services` | scope xin | làm được |
|---|---|---|
| `email` | gmail.readonly, gmail.send, gmail.modify | đọc, tìm, gửi, trả lời, gắn/bỏ nhãn, đánh dấu đọc, chuyển thùng rác |
| `calendar` | calendar | đọc/tạo/sửa event |
| `drive` | drive | đọc/ghi/xoá file (mặc định vào thùng rác) |
| `sheets` | spreadsheets | đọc/ghi spreadsheet |
| `docs` | documents | tạo/sửa Docs |
| `contacts` | contacts.readonly | đọc danh bạ |
| `all` | 8 scope ở trên | **default — chỉ dùng khi Hoàng nói cần full Workspace** |

`email` KHÔNG có quyền xoá vĩnh viễn và không đụng Drive — đúng mức cho "quản lý email".

## Lệnh

```bash
$GSETUP --check                                    # đã có token chưa
$GSETUP --client-secret /path/client_secret.json   # nạp OAuth client (Desktop app)
$GSETUP --auth-url --services email --format json  # in {"auth_url": ..., "scopes": [...]}
$GSETUP --auth-code "<URL hoặc code dán về>"        # exchange PKCE
$GSETUP --check-live                               # xác nhận bằng lời gọi thật
```

Dùng lại OAuth client sẵn có trên máy khi đã có (client Desktop đã dùng cho dịch vụ khác của cùng tài khoản) — đỡ cho Hoàng phải tạo project mới; nhưng phải bật API tương ứng trong GCP project đó.

## Cách user làm (gửi kèm URL)

1. Mở link → chọn đúng tài khoản muốn cấp.
2. Gặp màn "Google chưa xác minh ứng dụng" → Nâng cao → Tiếp tục (app ở trạng thái Testing, user phải nằm trong test users).
3. Browser nhảy sang `http://localhost:1/?code=...` và báo không mở được trang — **bình thường**; copy NGUYÊN URL trên thanh địa chỉ dán về.

## Lỗi thường gặp

| Triệu chứng | Nguyên nhân / xử lý |
|---|---|
| `Error 403: access_denied` | Account chưa nằm trong test users → thêm tại console `auth/audience` |
| `Insufficient scope` khi gọi tool | Token cấp thiếu scope (hoặc đang xài connector khác) → revoke rồi cấp lại đúng bộ scope |
| `Access Not Configured` | API chưa bật trong GCP project của client |
| Code hết hạn / đã dùng | Sinh `--auth-url` mới rồi làm lại từ bước mở link |
| Consent bị chặn bởi admin Workspace | Restricted scope không được allowlist → chuyển đường IMAP/App Password |

Token lưu `~/.hermes/google_token.json` (chmod 600), pending session `~/.hermes/google_oauth_pending.json`. Revoke: `$GSETUP --revoke`.
