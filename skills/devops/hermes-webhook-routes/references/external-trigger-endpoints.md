# Endpoint ngoài gõ vào Ultron (`hermes webhook`) — recipe & biến thể

Chi tiết kèm SKILL.md. Chỉ cần đọc khi dựng/sửa một route.

## Dựng một route (đã dùng thật cho Siri bridge trên iPhone)

1. **Sinh secret tĩnh** 32 byte → `~/.hermes/state/<route>_token.txt`, `chmod 600`.
2. **Đăng ký route** — prompt mẫu cho route nhận lệnh thoại:
   ```bash
   hermes webhook subscribe <route> \
     --prompt "Lệnh thoại từ Siri (Hoàng gửi qua Tailscale). NỘI DUNG LỆNH: {text}
---
Đây là lệnh thoại NGẮN. Trả lời NGẮN GỌN 3-6 dòng, dễ đọc trên điện thoại: đã làm gì + kết quả.
Việc dài thì báo đang chạy và gửi kết quả sau.
KHÔNG dùng công cụ web/tìm kiếm/đọc URL cho lệnh thoại. Không tự bịa việc.
Nếu lệnh không rõ nghĩa hoặc chỉ là thử micro thì trả lời đúng 1 câu ngắn (vd 'đã nhận lệnh') rồi dừng.
CHỈ KHI phần NỘI DUNG LỆNH ở trên để trống thì trả lời 'chưa nhận được nội dung lệnh' rồi dừng." \
     --secret "$(cat ~/.hermes/state/<route>_token.txt)" \
     --deliver google_chat --deliver-chat-id "spaces/XXXX" \
     --description "Siri voice command bridge (Ultron, qua Tailscale)"
   ```
3. **Bind + port**: `hermes config set platforms.webhook.extra.host <IP>` → restart gateway. Sau restart:
   `ss -ltn | grep <port>` và `curl -s -o /dev/null -w '%{http_code}' http://<IP>:<port>/health` = 200.
4. **Gửi thử**: POST JSON `{"text": "..."}` + header `X-Gitlab-Token` → nhận
   `{"status":"accepted","route":"<route>"}` trong vài ms, rồi đọc lại DM xác nhận câu trả lời.

## Đường đi một lệnh & điều client nhìn thấy

```
iPhone Shortcuts (Dictate Text → Get Contents of URL)
  → POST http://<IP>:<port>/webhooks/<route>   (headers: X-Gitlab-Token, Content-Type)
  → gateway trả {"status":"accepted"} NGAY  ← client CHỈ thấy dòng này
  → agent chạy (vài giây tới vài chục giây)
  → câu trả lời gửi vào --deliver-chat-id
```

## Biến thể bind

| Bind | Ai vào được | Đánh đổi |
|---|---|---|
| IP tailnet của node gateway | Chỉ thiết bị trong tailnet | Chết theo lịch teardown hằng ngày; phải bật lại khi cần |
| Tunnel công khai + token | Cả Internet | Cần rate-limit + chỉ cho route lệnh chỉ-đọc; chỉ dựng khi Hoàng yêu cầu rõ |

## Checklist bàn giao cho người dùng cuối

- [ ] Nói rõ khung giờ cổng còn sống (bind tailnet ⇒ tắt theo lịch teardown).
- [ ] Việc họ phải làm: cài app VPN → đăng nhập → tạo Shortcut (Dictate Text tiếng Việt → Get Contents
      of URL: POST + 2 header + JSON field `text` → Show Result) → thử.
- [ ] Một cách tự kiểm: câu trả lời sẽ hiện ở DM nào, sau khoảng bao lâu.
- [ ] Cảnh báo nói rõ ràng, không nói khi Shortcuts còn đang thu (lỗi nhận âm hay gặp).
- [ ] URL + token: gửi DM, KHÔNG lên group.
