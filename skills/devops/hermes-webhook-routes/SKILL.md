---
name: hermes-webhook-routes
description: "Use when an outside client must trigger Ultron by webhook."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, webhook, ingress, siri, shortcuts, tailscale, verification]
    related_skills: [google-chat-setup, account-access-provisioning, ultron-scheduled-actions]
---

# Endpoint cho client ngoài gõ vào Ultron (`hermes webhook`)

Dùng khi ai/cái gì **không phải Google Chat** cần ra lệnh hoặc bắn tín hiệu cho Ultron: Siri/Shortcuts
trên iPhone, CI, monitor, hệ thống ngoài, script trên máy khác. Hermes có sẵn kênh vào này
(`hermes webhook subscribe`) — không tự viết server HTTP, không cần app iOS.

Câu trả lời của Ultron vẫn đi về Chat (DM/group) qua adapter Google Chat; route chỉ là cửa VÀO.
Recipe chi tiết (iOS Shortcuts 4 bước, biến thể bind): `references/external-trigger-endpoints.md`.

## Quy trình

1. **Xác định client ký được HMAC không.** Không ký được (Shortcuts, curl tay) ⇒ dùng **secret tĩnh**,
   so qua header `X-Gitlab-Token`. Sinh token 32 byte → `~/.hermes/state/<route>_token.txt`, `chmod 600`,
   không bao giờ in giá trị ra (kể cả cho Hoàng), không để lọt repo sync.
2. **Đăng ký route** (prompt có ĐÚNG 1 thẻ dữ liệu):
   ```bash
   hermes webhook subscribe <route> \
     --prompt "<mô tả ngắn> {text}
---
<các rào: xem Pitfalls>" \
     --secret "$(cat ~/.hermes/state/<route>_token.txt)" \
     --deliver google_chat --deliver-chat-id "spaces/XXXX" --description "..."
   ```
   Subscribe lại cùng tên = cập nhật tại chỗ; kiểm secret cũ còn nguyên trong
   `~/.hermes/webhook_subscriptions.json` (file này có thể chứa secret ⇒ không dán ra group).
3. **Bind + port**: `hermes config set platforms.webhook.extra.host <IP>` → **restart gateway** (guard
   chặn tự restart từ trong gateway ⇒ đưa lệnh cho claude chạy `scripts/gw_restart.txt`). Kiểm sống:
   `curl -s -o /dev/null -w '%{http_code}' http://<IP>:<port>/health` → 200, và `ss -ltn | grep <port>`.
4. **Gửi thử + verify end-to-end** (mục Verify bên dưới) rồi mới báo Hoàng "xong".

## Verify — hai nguồn độc lập, không tin report tự khai

```bash
grep -E "\[webhook\] POST|inbound message: platform=webhook|response ready" ~/.hermes/logs/gateway.log | tail -5
~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/gchat_dump.py --space <DM> --limit 3
```

- `POST ... route=<tên> delivery=<id>` = tín hiệu ĐÃ tới; `inbound message: ... msg='...'` = nội dung nhận được.
- `prompt_len=` chỉ nhỉnh hơn prompt gốc khi field rỗng ⇒ dấu hiệu client chưa map biến.
- `response ready ... time= api_calls=` = thời gian + số lượt gọi công cụ ⇒ biết lượt đó có đi lạc không.
- Bước cuối luôn là **đọc lại chính space nhận tin** bằng `gchat_dump.py` — script tự khai "đã gửi" từng sai.
- Script đọc/gửi Chat phải chạy bằng **python của venv** (`~/.hermes/hermes-agent/venv/bin/python`);
  python3 hệ thống thiếu google libs.

## Pitfalls

- **Template thay thế MỌI lần xuất hiện của `{field}` — kể cả trong câu rào của chính mình.** Câu kiểm
  tra kiểu *"nếu payload còn nguyên thẻ `{text}` thì trả lời chưa nhận được"* bị thay luôn bằng dữ liệu
  thật ⇒ model đọc ra "payload trống" và trả lời SAI dù client gửi đủ (đã dính thật: một lệnh thoại
  tới đủ mà bị trả lời "chưa nhận được nội dung lệnh"). Prompt chỉ được có **đúng 1** thẻ; ca rỗng mô
  tả bằng lời ("nếu phần NỘI DUNG LỆNH để trống"); và kiểm bằng đếm trong config
  (`p.count('{text}') == 1`) chứ không tin mắt.
- **Route nhận LỆNH THOẠI phải chặn công cụ ngay trong prompt.** Prompt chỉ nói "thực hiện lệnh" là
  model đi lạc khi câu lệnh mơ hồ (đo thật: một câu thử micro ⇒ 74,9s, 10 lượt gọi, có lượt thử fetch
  `127.0.0.1` bị url_safety chặn, rồi trả lời úp mở *"nếu anh đang đọc dòng này..."* trong khi không gửi
  gì đi cả). Prompt đúng cần 3 vế: (1) *"đây là lệnh thoại NGẮN, KHÔNG dùng công cụ web/tìm kiếm/đọc
  URL"*; (2) *"lệnh không rõ nghĩa/thử micro ⇒ trả lời đúng 1 câu ngắn rồi dừng"*; (3) nhánh payload trống.
- **Lệnh qua webhook chỉ nên ĐỌC/TRA CỨU/BÁO CÁO.** Lệnh ghi/xoá/gửi hàng loạt, đổi cấu hình, hay việc
  không hoàn tác ⇒ bắt Hoàng xác nhận qua kênh khác, không nhận qua giọng nói mơ hồ. Cửa vào rộng =
  bề mặt tấn công rộng; token tĩnh là hàng rào DUY NHẤT nên giữ nó kín và phạm vi hẹp.
- **Client chỉ thấy `{"status":"accepted"}`.** `POST` trả về ngay (<5ms) rồi xử lý bất đồng bộ ⇒
  Shortcuts KHÔNG đọc được câu trả lời; câu trả lời về `--deliver-chat-id`. Muốn Siri đọc to phải dựng
  cơ chế chờ đồng bộ (đổi lại lệnh lâu bị Shortcuts cắt) — nói rõ đánh đổi này, đừng để người dùng
  tưởng Shortcuts sẽ hiện kết quả.
- **Bind vào IP Tailscale thì cổng chết theo lịch teardown Tailscale.** Đừng hẹn ai dùng cổng sau mốc
  tắt, và không tự bật lại Tailscale ngoài yêu cầu: xem `account-access-provisioning` →
  `references/tailscale-lifecycle.md`. Cần 24/7 thì đi tunnel công khai + token (rate-limit, chỉ route
  chỉ-đọc) và chỉ dựng khi Hoàng yêu cầu rõ.
- **Địa chỉ endpoint phải là TÊN MagicDNS, không phải IP tailnet.** IP đổi mỗi lần node được dựng lại,
  còn Shortcut/cấu hình giữ IP cũ thì request rơi vào hư không và client chỉ báo *"Request timed out"* —
  cổng KHÔNG hề nhận được gì. Lấy tên từ chính node chứ đừng đoán:
  `docker exec tailscale tailscale status --json` → `Self.DNSName` (kèm `CurrentTailnet.MagicDNSSuffix`);
  MagicDNS bật thì `http://<DNSName>:9444/<route>` sống qua mọi lần đổi IP.
- **Client báo timeout ⇒ soi journal cổng TRƯỚC, rồi mới nghi cổng.** Không thấy dòng `POST /siri/say`
  nghĩa là lỗi phía client (sai địa chỉ, hoặc VPN trên máy chưa bật) — sửa cổng lúc đó là vô ích.
  Cách để người dùng tự kiểm trong 30 giây: mở `http://<node>:9444/health` bằng Safari **trên chính thiết bị
  gọi lỗi** — `ok` = đường thông, timeout = VPN/DNS phía máy, còn POST tới mà trả `401` = sai token.
- **Thời gian chờ đồng bộ phải NGẮN HƠN ngưỡng cắt của client, không phải ngắn hơn giới hạn của mình.**
  iOS/Siri tự cắt ở ~30s ⇒ 25s là trần thực tế; đặt 50s thì câu trả lời lâu biến thành lỗi timeout ở phía
  người dùng dù cổng vẫn chạy bình thường. Quá 25s: trả ngay câu "đang xử lý, kết quả báo trong chat" rồi
  để phiên webhook đăng phần dài vào DM.
- **URL/token/endpoint: CHỈ DM Hoàng.** Không thả link hay token vào group, kể cả group nội bộ.
- **Bàn giao cho người dùng cuối bằng ngôn ngữ nghiệp vụ**: cài app VPN (nếu bind tailnet) → đăng nhập
  → tạo Shortcut (Dictate Text tiếng Việt → Get Contents of URL → Show Result) → thử; kèm *một* cách tự
  kiểm và khung giờ cổng còn sống. Gặp câu nói bị nhận sai âm (vd thừa một từ lạ) thì nghi phần
  *Dictate Text* trước, đừng nghi đường truyền — trong log, nội dung tới nguyên văn là bằng chứng.

## References

- `references/external-trigger-endpoints.md` — câu lệnh subscribe mẫu, sơ đồ đường đi một lệnh, bảng
  biến thể bind, checklist bàn giao cho người dùng cuối.
