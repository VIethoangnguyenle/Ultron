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
   - **KHÔNG nhận mật khẩu/token khi chính Hoàng gửi "cho tiện"** (mở khoá màn hình, chạy hộ lệnh…), kể cả kèm lời hứa "em báo nhận rồi anh xoá": tin nhắn chat đã nằm vĩnh viễn trong lịch sử máy chủ, xoá tin không xoá được bản lưu. Từ chối ngắn + đưa đường KHÔNG cần secret (anh tự mở khoá rồi em làm / render offscreen / chờ anh có mặt), và không lưu giá trị đó ở bất kỳ đâu.
   - Trước khi sửa file credential: backup, và không đưa giá trị secret vào báo cáo/log.
5. **Verify + báo cáo.** Sau khi exchange code: gọi thật lần nữa, ghi lại **tài khoản nào** đã kết nối (email/UID), rồi báo Hoàng: xin scope gì → nhận được gì → token nằm ở đâu → đã thử việc gì để chứng minh. Chưa có lời gọi thật trả dữ liệu thì chưa nói "xong".

## Pitfalls

- **`✔ Connected` ≠ dùng được.** Connector/first-party báo connected nhưng OAuth thiếu scope thì lời gọi thật trả `Insufficient scope` — server sống, quyền không đủ. Luôn test 1 lời gọi đọc trước khi hứa.
- **Không đẩy mail công việc/nhạy cảm qua connector cloud của bên thứ ba** (connector claude.ai, dịch vụ trung gian): dữ liệu đi qua hạ tầng của họ. Mail nội bộ ⇒ token local trên máy, hoặc IMAP/App Password.
- **Skill doc vs script lệch nhau: sửa script cho khớp doc, đừng tụt về default rộng.** Nếu SKILL.md ghi có cờ `--services` mà `scripts/setup.py` bản cài lại từ chối cờ đó, việc đúng là *implement cờ đó* (map service → scope, persist scope đã xin vào pending OAuth session để `--auth-code` dùng cùng bộ), KHÔNG phải chạy default `all` (xin 8 scope trong khi chỉ cần 3). **`google-workspace` là skill bundled ⇒ `scripts/setup.py` KHÔNG được `~/Ultron/sync.py` mirror: patch chỉ sống trên máy này và sẽ bị Hermes update ghi đè.** Giữ recipe trong `references/google-oauth-scope-sets.md` để áp lại, và sau mỗi lần nâng cấp kiểm bằng `$GSETUP --auth-url --services email` (phải KHÔNG báo `unrecognized arguments`).
- **Tài khoản Workspace do admin quản lý:** admin có thể chặn restricted scope của Gmail (hoặc tắt App Password). Xác định trước phương án dự phòng (mail-only ⇒ `himalaya` + App Password) để không kẹt giữa đường; consent bị chặn thì báo thẳng, không đoán.
- **Code cấp quyền hết hạn trong vài phút** và chỉ dùng được một lần: hết hạn thì sinh URL mới, đừng thử lại code cũ. URL mới ⇒ pending session mới.
- **Đừng xác nhận "cấp xong" khi mới có URL.** Bước cuối là người dùng mở link, approve, dán code về — thiếu code thì việc còn dang dở, phải nói rõ là đang chờ.
- **Consent OK + có `refresh_token` ≠ gọi được API.** Nếu GCP project chưa **bật API** thì lời gọi trả `403: Gmail API has not been used in project <id> or it is disabled`. Chỉ chủ project bật được: `console.developers.google.com/apis/api/gmail.googleapis.com/overview?project=<id>`. Bật xong **không cần cấp quyền lại** — token cũ chạy ngay (chờ ~30s cho Google lan truyền). Đây là bước hay bị bỏ sót nhất: token đúng, scope đúng, vẫn 403.
- **Filter tìm kiếm Gmail dễ ăn mất mail thật.** `-category:promotions/-category:social/-category:forums` ghép với các `-from:` làm mất gần hết mail người gửi (đo thật: 48 → 4 thư, mất cả mail dự án lẫn thư nhân sự). Muốn tin một filter thì **đếm A/B** (số thư khớp khi có và khi không có filter) rồi mới dùng, đừng đoán theo cảm giác. Filter khớp **0 thư** hoặc khớp **gần hết** đều là filter SAI — đo cả hai chiều (quá chặt / quá lỏng) trước khi chốt.

## Sau khi đã có quyền — vận hành hằng ngày

- **Helper Gmail local:** `~/.hermes/scripts/gmail.py` — `profile` · `counts` · `search "<query>" --max N` · `read <id>` · `send` · `modify`. Đếm số thư bằng **phân trang** (`_count`), KHÔNG dùng `resultSizeEstimate` của Gmail (bị cap, luôn trả ~201). Muốn biết tổng chưa đọc thì đọc `labels.get('INBOX').messagesUnread`.
- **Action gửi tin định kỳ thì để SCRIPT tự gửi** (`gchat_send_text.py --space ...`), stdout chỉ là log; im lặng khi không có gì mới; và verify bằng **đọc lại space** (`gchat_dump.py --space ... --limit 2`), không tin `exit=0`.
- **Ping mail QUAN TRỌNG (việc Hoàng cần — chốt 2026-09-12):** `~/.hermes/scripts/email_watch.py`, chạy bởi **cron riêng `ultron-email-watch` (10 phút/lần, `no_agent`, deliver `local`)** — ngoại lệ hợp lệ của luật "chỉ dùng schedules.yaml", vì dispatcher chỉ chạy **1 lần/ngày/action**, không theo dõi liên tục được.
  - 3 tầng: (1) **loại thẳng** mail bulk/invite/HR tự động/bản tin/bug-report digest; (2) **chấm điểm** — SỰ CỐ +3 > gửi thẳng cho anh +3 > người–tổ chức quan trọng +2 > cần phản hồi +1 > dự án +1; (3) **ngưỡng 4** ⇒ ping; mỗi thư ping **1 lần** (state `~/.hermes/state/email_watch_seen.json`, tự dọn sau 30 ngày).
  - Tinh chỉnh: `--explain` in điểm **mọi** thư (vì sao ping / vì sao bỏ) — soi bằng cái này TRƯỚC khi sửa ngưỡng/từ khoá; `--dry-run` in mà không gửi; `--reset-seen` xoá baseline; `--init-alerts-hours N` cho lần chạy đầu (mặc định 12h ⇒ KHÔNG dội bom backlog).
  - **Cái bẫy thật:** mail nhóm nội bộ VNPAY đi qua Google Groups nên **cũng có `List-Unsubscribe`** — dùng nó làm tín hiệu bulk sẽ loại sạch mail thật (đo thật: 45/48 thư bị loại oan). Chỉ coi là bulk khi người gửi **ngoài** domain `vnpay.vn`/`vietbank.vn`/`napas.com.vn`.
- **Bản tin toàn bộ mail (`email_digest.py`, 08:00):** đã **TẮT** (`enabled: false`) — Hoàng chốt chỉ cần ping mail quan trọng; giữ script vì bật lại chỉ là 1 dòng.
- **Bám đúng cái Hoàng xin, không tự thêm tiện ích.** Anh chốt *"chỉ cần tracking, có mail quan trọng thì ping"* ⇒ **TẮT** phần thừa (bản tin toàn bộ mail) thay vì để cả hai chạy song song, và nói rõ cách bật lại. Báo cáo kèm **số đo** (xét bao nhiêu thư → ping bao nhiêu → tần suất/tuần) để anh chỉnh độ nhạy bằng một câu.
- **Nội dung mail KHÔNG BAO GIỜ ra group** — chỉ DM Hoàng. Không ghi nội dung mail vào file nằm trong repo sync.
- **Trước khi thêm file mới vào `~/.hermes`,** kiểm `~/Ultron/sync.py` xem nó có bị mirror lên GitHub không: sync chỉ lấy `memories/ scripts/ SOUL.md config.yaml cron/ schedules.yaml skills/` ⇒ token (`google_token.json`, `google_client_secret.json`) không bị đẩy. Nhưng **kiểm lại mỗi lần thêm file**, đừng đoán.
- **File script trong `scripts/` thì CÓ bị đẩy lên GitHub** ⇒ script phải sạch secret (đọc token từ file, không nhúng giá trị).

## Hạ tầng dùng chung của Hoàng — luật cứng, áp cho MỌI lần đụng tới

- **`omni-sme-proxy` (nginx của Hoàng) đang phục vụ link log UAT/PILOT cho tester — không được làm hỏng.** Mọi thay đổi: backup config trước · sửa **ghi tại chỗ giữ inode** (tool ghi kiểu atomic/`patch` làm đổi inode ⇒ container vẫn đọc bản cũ mà `nginx -t` vẫn báo ok) · validate bằng container rác **cùng image** · rồi `nginx -s reload`. Không dựng nginx/container thứ hai khi anh đã có cái dùng được — hỏi trước.
- **"Xoá toàn bộ log hệ thống về việc X" = dọn dấu vết, và luôn dry-run trước.** Dùng `~/.hermes/scripts/scrub_matter_logs.py` (mặc định chỉ in ra; `--apply` mới xoá). Nói thẳng phần **không** với tới được (systemd journal, `/var/log` root-owned) kèm lệnh cho Hoàng — đừng im lặng cho rằng đã sạch.
- **Secret lộ trong log ⇒ scrub log xong vẫn phải khuyên revoke/regenerate credential.** Xoá dấu vết không làm key hết hiệu lực (auth key Tailscale, token webhook…).
- **Mở node Tailscale = mở HẾT cổng bind `0.0.0.0` của máy**, không riêng cổng mình định mở: container chạy
  `--net=host` nên IP tailnet chạm tới mọi socket host (SSH, redis, minio, nginx, MCP…) và ACL Tailscale mặc
  định **allow-all** trong tailnet. Mở node thì phải đo bằng `ss -tlnp`, tách "bind đích danh IP tailnet" (cố ý mở)
  vs "bind `0.0.0.0`" (lộ kèm), rồi nói rõ với Hoàng cái gì đang lộ — chi tiết ở `references/tailscale-lifecycle.md`.
- **Dịch vụ nội bộ login bằng SSO / trỏ về tên miền thật thì nginx proxy KHÔNG đủ** (callback quay về tên miền gốc) — đừng hứa, cũng đừng tự dựng lại route: đường đúng là subnet router.

## References

- `references/tailscale-lifecycle.md` — luật tắt hết Tailscale sau 17h30, dựng container, IP động, **dọn dấu vết log** (marker, log xoay vòng, phần cần root).
- `references/tailscale-reopen-procedure.md` — mở lại đầy đủ (node, cổng Siri, gateway) + bản đồ cổng + **bẫy bind-mount theo inode** khi sửa nginx của Hoàng.
- `references/google-oauth-scope-sets.md` — bảng service → scope, lệnh setup, xử lý lỗi consent thường gặp.
