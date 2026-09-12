---
name: account-access-provisioning
description: "Use when Ultron needs access to Hoàng's accounts."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [OAuth, Google, Gmail, Credentials, Least-Privilege, Security]
    related_skills: [google-workspace, himalaya, claude-code]
---

# Cấp quyền tài khoản cho Ultron (OAuth, least privilege)

Dùng khi Hoàng yêu cầu Ultron đọc/làm việc trên một tài khoản của anh ấy — *"mày vào được gmail tao đúng k"*, *"cấp lại đi, anh muốn em quản lý email cho anh"*. Áp dụng cho Gmail/Calendar/Drive và mọi dịch vụ phải qua OAuth.

## Quy trình

1. **Trả lời "có đang vào được không" bằng MỘT LỜI GỌI THẬT, không bằng danh sách cấu hình.** Sự tồn tại của file token, `--check`, hay tool hiện `✔ Connected` đều KHÔNG chứng minh dùng được. Kiểm tra rồi gọi thử một API đọc thật (Gmail: `list_labels` / `getProfile`) → chỉ khi đó mới nói "vào được" hoặc "chưa".
2. **Phân loại dịch vụ + tài khoản TRƯỚC khi chọn công cụ.** Chỉ email ⇒ dùng đường IMAP/App Password (`himalaya`); email + Calendar/Drive ⇒ OAuth (`google-workspace`). Xác định tài khoản là *cá nhân* hay *Workspace công ty* — quyết định cả đường đi lẫn rủi ro (xem Pitfalls).
3. **Xin scope hẹp nhất đủ dùng, và nói cho Hoàng bằng ngôn ngữ nghiệp vụ.** Ví dụ Google: `setup.py --auth-url --services email --format json` ⇒ email = `gmail.readonly` + `gmail.send` + `gmail.modify`.
   - KHÔNG xin thêm Drive/Docs/Sheets/Calendar cho "chắc" — mỗi scope thừa là một quyền thừa.
   - Khi báo, dịch scope ra việc làm được: *"đọc mail + gửi mail + gắn nhãn/đánh dấu; KHÔNG xoá vĩnh viễn, KHÔNG Drive/Docs/Calendar"*.
4. **Vệ sinh secret khi cấp quyền.**
   - Chỉ *mã dùng-một-lần* (code trong URL redirect) được đi qua chat. Refresh token ở lại máy: `~/.hermes/google_token.json`, `chmod 600`, KHÔNG bao giờ in giá trị ra (kể cả cho Hoàng).
   - Chỉ xin App Password/long-lived secret qua chat khi không còn đường nào khác, và nhắc revoke/đổi lại sau khi xong.
   - Trước khi sửa file credential: backup, và không đưa giá trị secret vào báo cáo/log.
5. **Verify + báo cáo.** Sau khi exchange code: gọi thật lần nữa, ghi lại **tài khoản nào** đã kết nối (email/UID), rồi báo Hoàng: xin scope gì → nhận được gì → token nằm ở đâu → đã thử việc gì để chứng minh. Chưa có lời gọi thật trả dữ liệu thì chưa nói "xong".

## Pitfalls

- **`✔ Connected` ≠ dùng được.** Connector/first-party báo connected nhưng OAuth thiếu scope thì lời gọi thật trả `Insufficient scope` — server sống, quyền không đủ. Luôn test 1 lời gọi đọc trước khi hứa.
- **Không đẩy mail công việc/nhạy cảm qua connector cloud của bên thứ ba** (connector claude.ai, dịch vụ trung gian): dữ liệu đi qua hạ tầng của họ. Mail nội bộ ⇒ token local trên máy, hoặc IMAP/App Password.
- **Skill doc vs script lệch nhau: sửa script cho khớp doc, đừng tụt về default rộng.** Nếu SKILL.md ghi có cờ `--services` mà `scripts/setup.py` bản cài lại từ chối cờ đó, việc đúng là *implement cờ đó* (map service → scope, persist scope đã xin vào pending OAuth session để `--auth-code` dùng cùng bộ), KHÔNG phải chạy default `all` (xin 8 scope trong khi chỉ cần 3).
- **Tài khoản Workspace do admin quản lý:** admin có thể chặn restricted scope của Gmail (hoặc tắt App Password). Xác định trước phương án dự phòng (mail-only ⇒ `himalaya` + App Password) để không kẹt giữa đường; consent bị chặn thì báo thẳng, không đoán.
- **Code cấp quyền hết hạn trong vài phút** và chỉ dùng được một lần: hết hạn thì sinh URL mới, đừng thử lại code cũ. URL mới ⇒ pending session mới.
- **Đừng xác nhận "cấp xong" khi mới có URL.** Bước cuối là người dùng mở link, approve, dán code về — thiếu code thì việc còn dang dở, phải nói rõ là đang chờ.

## References

- `references/google-oauth-scope-sets.md` — bảng service → scope, lệnh setup, xử lý lỗi consent thường gặp.
