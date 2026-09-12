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
| `Access Not Configured` / `API has not been used in project <id> or it is disabled` | API chưa bật trong GCP project của client → chủ project bật ở `console.developers.google.com/apis/api/<api>/overview?project=<id>`; **không cần cấp quyền lại**, chờ ~30s |
| `--check-live` báo lỗi sau khi chỉ xin scope `email` | `--check-live` thử cả Calendar/Drive — KHÔNG phải lỗi cấp quyền; xác nhận bằng lời gọi Gmail thật (`users.getProfile`) |
| Code hết hạn / đã dùng | Sinh `--auth-url` mới rồi làm lại từ bước mở link |
| Consent bị chặn bởi admin Workspace | Restricted scope không được allowlist → chuyển đường IMAP/App Password |

Token lưu `~/.hermes/google_token.json` (chmod 600), pending session `~/.hermes/google_oauth_pending.json`. Revoke: `$GSETUP --revoke`.

Sau khi exchange: mở token đọc khoá `scopes` — phải **đúng bằng** bộ đã xin (3 scope với `email`), có `refresh_token`, và file mode `600`. Lệch scope ⇒ cấp lại, đừng dùng tạm.

## Bản cài `setup.py` thiếu `--services` — recipe vá

`google-workspace` là skill **bundled** ⇒ `scripts/setup.py` KHÔNG được `~/Ultron/sync.py` mirror và sẽ bị Hermes update ghi đè. Kiểm tra nhanh: `$GSETUP --auth-url --services email` phải KHÔNG báo `unrecognized arguments`.

Bốn điểm cần sửa trong `scripts/setup.py`:

1. Thêm `SERVICE_SCOPES = {...}` (map như bảng trên), `REQUESTED_SCOPES = list(SCOPES)` (biến mutable toàn cục) và hàm `resolve_services(spec)` — nhận `"email,calendar"` hoặc `"all"`, tên sai thì `sys.exit(2)` kèm danh sách hợp lệ.
2. Thay mọi chỗ trong luồng auth đang dùng `SCOPES` bằng `REQUESTED_SCOPES` (dựng `auth_url`, check scope thiếu, exchange).
3. `_save_pending_auth` lưu thêm `"scopes": list(REQUESTED_SCOPES)`; `exchange_auth_code` đọc lại `pending["scopes"]` rồi gán `REQUESTED_SCOPES[:] = ...` ⇒ `--auth-code` không cần truyền lại `--services`.
4. `main()`: thêm `--services` và `--format {text,json}`; set `OUTPUT_FORMAT`, gọi `resolve_services` khi có `--auth-url`/`--auth-code`.

Gán qua slice (`REQUESTED_SCOPES[:] = ...`) để khỏi phải khai `global`; giữ default `all` cho tương thích
ngược, nhưng **luôn truyền `--services` khi cấp quyền mới**.
