# 2 cổng Siri: local-first (verified 2026-09-13)

- Mỗi cổng bind `127.0.0.1:<port>` NGAY khi khởi động; khi node Tailscale sống thì mở THÊM listener trên IP tailnet cùng port (watchdog dò lại ~25s). Không có tailnet ⇒ cổng vẫn sống.
- Port: `9444` speak (`siri-speak`), `9445` chat (`siri-chat`); đổi qua env `SIRI_SPEAK_PORT` / `SIRI_CHAT_PORT`.
- Forward: thử `http://127.0.0.1:9443/webhooks/<route>` trước, chỉ khi refused/unreachable mới rơi về IP tailnet. **Cổng local-first KHÔNG có nghĩa là đường vào cũng local-first** — xem mục dưới.
- Nạp lại sau khi sửa code: `systemctl --user kill -s TERM siri-speak siri-chat` rồi chờ ~14s (guard chặn `restart`).
- Kiểm chứng đạt: `ss -ltnp | grep -E ':(9444|9445)'` thấy CẢ 2 địa chỉ; `curl 127.0.0.1:9444/health` = 200; POST không token = 401.
- Teardown 17:30 chỉ tắt node + xoá dấu vết tailscale — KHÔNG còn stop 2 cổng (chúng phải sống tiếp ở local).
- Bằng chứng độc lập với Google Chat: PID + uptime tiến trình `hermes-gateway` KHÔNG đổi sau khi sửa/nạp 2 cổng.
- E2E chuẩn: `/chat` → câu trả lời tiếng Việt đầy đủ (~5s); `/siri/say` → 1 câu tiếng Anh (~6s).

## Bẫy đã đo: hop forward vào gateway phụ thuộc tailnet
- Cấu hình hiện tại ghim `platforms.webhook.extra.host = <IP tailnet>` + `port: 9443` ⇒ `ss -ltnp` chỉ thấy
  `100.82.xxx.xxx:9443`, KHÔNG có `127.0.0.1:9443`. Vì vậy lần thử đầu của cổng luôn `Connection refused`, và
  mọi lượt thật đều đi qua IP tailnet — log cổng ghi đúng chuỗi "127.0.0.1:9443 không nhận (Connection refused)
  — thử địa chỉ kế tiếp".
- Hệ quả: sau mốc teardown, client trên chính máy (widget, script) cũng mất đường vào dù cổng còn sống ⇒ đừng hứa
  "dùng được cả tối" khi chưa kiểm `ss -ltnp`.
- Hai lựa chọn (đều là ĐỔI CẤU HÌNH ⇒ Hoàng quyết, restart gateway đưa claude, sau restart verify lại kênh Chat):
  (a) bind thêm loopback bằng cách bỏ ghim host — trong `gateway/platforms/webhook.py` `DEFAULT_HOST = None`
  nghĩa là bind mọi họ địa chỉ (host rỗng/không pin cũng vậy), đánh đổi là cửa nghe trên mọi interface;
  (b) để nguyên ⇒ chỉ dùng được trong khung giờ node bật.
- `INSECURE_NO_AUTH` (secret test không xác thực) chỉ được phép khi host là loopback — đừng dùng nó như cách
  "mở nhanh" khi đang pin IP tailnet, adapter từ chối khởi động.
