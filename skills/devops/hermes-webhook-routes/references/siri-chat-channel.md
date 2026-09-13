# Hai kênh endpoint cho Siri: NÓI (speak) vs CHAT — và luật ĐỘC LẬP với Google Chat

Hoàng chốt 2026-09-13: *"tạo thêm giúp anh 1 kênh siri chat, mục đích cho 2 case speak và chat riêng biệt. Kênh chat thì y chang như google chat thôi, chỉ khác là có thể gọi qua endpoint"*; *"kênh chat và say cứ online ở local nhé, còn khi tailscale mở thì forward nó về domain ultron"*; *"2 kênh say và chat này độc lập vs google chat giúp anh nhé, tránh việc fix này lỗi cái khác"*.

## Kiến trúc

| Phần | NÓI (speak) | CHAT |
|---|---|---|
| Cổng | `~/.hermes/scripts/siri_speak.py` · port **9444** | `~/.hermes/scripts/siri_chat.py` · port **9445** |
| Unit | `siri-speak` (systemd user) | `siri-chat` (systemd user) |
| Route | `siri` trong `webhook_subscriptions.json` | `sirichat` |
| Kiểu trả lời | 1 câu văn nói, tiếng Anh | y Google Chat: đầy đủ, tiếng Việt, được trả file |
| Ngữ cảnh | `state/siri_outbox.json` + `siri_history.log` | `state/siri_chat_outbox*.json` + `state/siri_chat/<conv>.jsonl` |

Cả 2 cổng: `POST` kèm header `X-Gitlab-Token` (token ở `~/.hermes/state/siri_token.txt`), forward sang gateway `http://127.0.0.1:9443` (fallback IP tailnet) `/webhooks/<route>`, chờ file outbox rồi trả JSON. Route để `deliver: "log"` — câu trả lời cho Siri **không bao giờ đăng lên Google Chat**.

## Luật ĐỘC LẬP (bắt buộc khi sửa)

1. 2 cổng là **tiến trình riêng**, systemd unit riêng, file trạng thái riêng. Sửa/vá 1 kênh **không** được đụng kênh kia.
2. **Không đụng đường Google Chat**: không đổi `platforms.webhook.*`, không restart gateway, không sửa adapter Chat khi đang làm việc cho 2 cổng Siri. Muốn đổi gateway thì phải tách thành việc riêng, xin ý kiến chủ máy trước.
3. Trong `webhook_subscriptions.json` chỉ sửa đúng entry của kênh mình đang làm; **backup + validate JSON** trước/sau khi sửa (file này gateway đọc live, không cần restart — hỏng JSON là mất luôn route).
4. Cổng phải **local-first**: luôn listen `127.0.0.1:<port>`; thêm listener trên IP tailnet khi node đang mở (dò động: env `TAILNET_IP` → `state/tailnet_ip.txt` → `docker exec tailscale tailscale ip -4`), watchdog thử lại định kỳ và tự đổi khi IP đổi. Node tắt ⇒ cổng **không** chết, chỉ mất cửa tailnet.
5. Teardown 17:30 chỉ tắt *node* Tailscale + scrub log; **không** stop 2 cổng (chúng là dịch vụ local) — nhưng phải dọn nội dung chat tạm (outbox, file trả về) và đảm bảo log cổng không để lại IP tailnet qua đêm.

## Pitfalls đã gặp (đừng lặp lại)

- Outbox **một khe dùng chung** ⇒ 2 request song song đọc/xoá nhầm câu trả lời của nhau. Phải tách theo hội thoại + claim-on-read + `req_id` do cổng sinh (không tin field do LLM tự ghi).
- Bind fallback `127.0.0.1` khi gateway chỉ nghe trên IP tailnet ⇒ cổng "trông vẫn sống" mà forward bị refused (hỏng im lặng). Phải log ERROR rõ + trả `status="error"` kèm lý do.
- Token client **trùng** secret route webhook ⇒ lộ token ở điện thoại = gọi thẳng gateway với quyền `terminal`. Giữ token client nguyên (Shortcut không phải sửa), nhưng secret route phải là giá trị riêng do cổng đọc từ file webhook.
- `Restart=always` không cứu được khi IP tailnet đổi (tiến trình không crash, socket cũ vẫn mở) ⇒ phải có watchdog dò IP.
- Khi client cắt kết nối (Siri timeout ~30s), `wfile.write` phải bọc `try` để không đổ traceback vào journal.
