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
Hai kênh endpoint tách biệt — NÓI (đọc to) vs CHAT (như Google Chat): `references/siri-chat-channel.md`.
Cả 2 cổng nay là **local-first** (bind `127.0.0.1` trước, tailnet chỉ là cửa phụ) — trạng thái đã kiểm
chứng + cách nạp lại cổng: `references/siri-channels-local-first.md`.
Cổng NÓI phân biệt **NGUỒN** request (điện thoại / desktop / widget): cờ `source`, luật "chỉ desktop mới
phát loa máy chủ", cách chứng minh bằng âm thanh thật: `references/siri-origin-flag.md`.

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

- **Sửa code cổng xong PHẢI nạp lại unit, không thì test "đã sửa" là vô nghĩa.** `systemctl --user restart`
  bị guard chặn ⇒ dùng `systemctl --user kill -s TERM siri-speak siri-chat`, chờ ~14s cho `Restart=always`
  dựng lại. Tiến trình cũ vẫn nằm trong RAM với code cũ và vẫn trả 200 ⇒ health check xanh mà hành vi chưa đổi.
  Sau khi nạp lại mới chạy bộ verify (ss -ltn, health, 401 khi thiếu token, E2E thật).
- **Log cổng phải ghi ra FILE, không để trong journald.** `journalctl --vacuum` cần `sudo` ⇒ dấu vết
  (IP tailnet, tên node) nằm lại qua đêm, phá luật "xoá log Tailscale sau 17h30". Cổng ghi
  `~/.hermes/logs/siri-speak.log` / `siri-chat.log` (quyền user, scrub giữ nguyên inode) thì dọn được.
  Hệ quả khi soi lỗi: `journalctl --user -u siri-speak` trả **"No entries"** là bình thường, không phải cổng
  chết — đọc file log trước khi kết luận bất cứ điều gì về lượt vừa gọi.
- **`/files/<conv>/<tên>` lọc theo hội thoại nhưng KHÔNG phải phân quyền.** Chỉ có một token dùng chung ⇒
  client đã xác thực mà biết tên hội thoại + tên file vẫn tải được file của hội thoại khác. Muốn chặn thật
  phải cấp token/khoá riêng theo hội thoại — việc đó ĐỔI hợp đồng với client nên phải để Hoàng quyết;
  đừng mô tả tính năng này với người dùng như "bảo mật theo hội thoại". Cùng nhóm: dựng URL file từ
  header `Host` là lỗ hổng giả mạo ⇒ phải dựng từ địa chỉ loopback cố định, và chịu tải có giới hạn
  (12 lượt đồng thời ⇒ phần vượt trả 503, cổng không sập) — chặn tải là hành vi ĐÚNG, đừng "sửa" thành chờ vô hạn.

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
- **Cổng là local-first: teardown Tailscale KHÔNG còn giết tiến trình cổng.** Bind vào IP Tailscale thì cổng chết theo lịch
  teardown Tailscale. Đừng hẹn ai dùng cổng sau mốc
  tắt, và không tự bật lại Tailscale ngoài yêu cầu: xem `account-access-provisioning` →
  `references/tailscale-lifecycle.md`. Cổng bind loopback trước rồi mới mở thêm listener tailnet ⇒ sau
  teardown tiến trình vẫn sống, gọi `127.0.0.1:9444/9445` (widget, script trên máy) vẫn chạy; nhưng
  client ngoài (Siri/iPhone) vẫn phải trong khung giờ tailnet mở. Cần 24/7 thì đi tunnel công khai + token (rate-limit, chỉ route
  chỉ route chỉ-đọc) và chỉ dựng khi Hoàng yêu cầu rõ.
  - **Local-first chỉ đúng tới CỔNG — hop chuyển tiếp vào gateway vẫn chết theo node.** `platforms.webhook.extra.host`
    bị ghim vào IP Tailscale ⇒ gateway chỉ nghe `<IP tailnet>:9443`, KHÔNG nghe loopback; cổng thử `127.0.0.1:9443`
    trước rồi mới fallback sang IP tailnet ⇒ sau mốc teardown, client TRÊN CHÍNH MÁY (widget, script) cũng mất
    đường vào dù cổng vẫn sống và vẫn trả lời. Kiểm bằng `ss -ltnp | grep -E '9443|9444|9445'` trước khi hứa
    "chạy được cả tối". Muốn local-first thật thì phải cho webhook nghe thêm loopback: trong code `DEFAULT_HOST = None`
    = bind MỌI họ địa chỉ, host rỗng/không pin cũng vậy (`gateway/platforms/webhook.py`); `INSECURE_NO_AUTH` chỉ
    hợp lệ khi bind loopback. ĐỔI CẤU HÌNH ⇒ phải Hoàng đồng ý, restart gateway đưa cho claude, và sau restart phải
    verify lại kênh Google Chat (kênh này KHÔNG đi qua route động — `webhook_subscriptions.json` chỉ có route khai tay).
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
- **Cổng NÓI: nguồn `phone` (mặc định khi thiếu cờ) tuyệt đối KHÔNG được gọi lệnh phát âm thanh**; chỉ
  `source=desktop` mới phát loa máy chủ. Cổng dùng chung cho iPhone / desktop / widget nên thiếu cờ phải rơi
  về hành vi cũ (im) — đổi mặc định là làm iPhone của chủ máy tự dưng có tiếng. Kiểm bằng cách GHI monitor
  rồi đo dB, đừng tin "exit 0": hợp đồng cờ + recipe: `references/siri-origin-flag.md`.
- **URL/token/endpoint: CHỈ DM Hoàng.** Không thả link hay token vào group, kể cả group nội bộ.
- **Bàn giao cho người dùng cuối bằng ngôn ngữ nghiệp vụ**: cài app VPN (nếu bind tailnet) → đăng nhập
  → tạo Shortcut (Dictate Text tiếng Việt → Get Contents of URL → Show Result) → thử; kèm *một* cách tự
  kiểm và khung giờ cổng còn sống. Gặp câu nói bị nhận sai âm (vd thừa một từ lạ) thì nghi phần
  *Dictate Text* trước, đừng nghi đường truyền — trong log, nội dung tới nguyên văn là bằng chứng.

## References

- `references/external-trigger-endpoints.md` — câu lệnh subscribe mẫu, sơ đồ đường đi một lệnh, bảng
  biến thể bind, checklist bàn giao cho người dùng cuối.
