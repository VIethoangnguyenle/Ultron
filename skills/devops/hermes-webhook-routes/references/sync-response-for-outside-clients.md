# Đường đồng bộ cho client ngoài (Siri/Shortcuts) — trả câu trả lời trong HTTP response

## Vấn đề
`hermes webhook` trả về **ngay** `{"status":"accepted","route":...,"delivery_id":...}` (HTTP 202, ~1ms) rồi chạy Agent ở nền.
⇒ Client kiểu Siri/Shortcuts chỉ nhận `accepted`, KHÔNG có gì để đọc to.

Các đường KHÔNG dùng được (đã kiểm chứng trong source `gateway/platforms/webhook.py`):
- `send()` ­chỉ hỗ trợ `deliver` = `log` / `github_comment` / các platform chat đã biết. **Không có callback_url / response_url**.
- Session webhook bị **giới hạn tool** (~7: web, vision, clarify, tool_search/describe/call) ⇒ **không có `write_file`/terminal**.
  Đừng thiết kế "Agent ghi kết quả ra file rồi client đọc file" — Agent sẽ báo không có tool ghi file.
  (Cập nhật 2026-09-12: mở được bằng key tay `toolsets` của **từng route** — xem mục cuối file.)

## Cách chạy được: cổng "nói" đứng giữa (đã dựng: `~/.hermes/scripts/siri_speak.py`)
```
Shortcuts --POST--> ultron:9444/siri/say --> (forward) --> 100.82.132.36:9443/webhooks/siri
                     ^ dùng TÊN MagicDNS (ultron.tail5d68a5.ts.net), đừng dùng IP:
                       IP đổi mỗi lần dựng lại node, tên thì không.
                     bridge chờ câu trả lời, rồi trả JSON {"status","text","waited_s","echo"} trong response body
```
- Bridge tự đẩy lệnh sang route webhook rồi **poll FILE outbox** `~/.hermes/state/siri_outbox.json`
  (`{"text","ts"}`) cho tới khi Ultron ghi câu trả lời có `ts` ≥ lúc gửi lệnh; bridge **xoá file trước mỗi lượt**
  nên không bao giờ đọc nhầm câu trả lời cũ. KHÔNG dùng tin nhắn Chat làm kênh trả lời nữa
  (Hoàng chốt 2026-09-12: *"Không cần phải show các response của em với siri ở đây"*) ⇒ route để `deliver: "log"`,
  câu trả lời chỉ nằm trong file + gateway log, không hiện ở DM hay group.
- **Timeout 25s — trần là ngưỡng cắt của CLIENT, không phải của mình.** iOS/Siri tự cắt ở ~30s; đặt 50s thì
  câu trả lời lâu biến thành lỗi *"Request timed out"* ở phía người dùng dù cổng vẫn chạy. Quá 25s → trả ngay
  `TIMEOUT_MSG` ("Still working on it — ask me again in a moment."); câu trả lời muộn vẫn nằm trong file outbox,
  KHÔNG gửi lên Chat.
- Bảo mật: bind **IP Tailscale**, bắt buộc `X-Gitlab-Token`, chặn body > 8KB, không log token/nội dung lệnh.
- Service: `~/.config/systemd/user/siri-speak.service` (Restart=always). Nạp lại code = `systemctl --user kill -s TERM siri-speak`
  (KHÔNG dùng `restart` — guard Hermes chặn; `Restart=always` tự dựng lại, mất ~6s nên chờ ≥9s trước khi test).

## KÊNH TRẢ LỜI = FILE, KHÔNG PHẢI CHAT (bắt buộc — đã qua 3 đời kênh)
Đừng để route webhook deliver vào cùng space với chat thường: cả phiên webhook lẫn phiên chat đều là **cùng một bot**,
bridge sẽ nhặt nhầm câu trả lời của phiên chat (thật gặp: `waited_s=1.3`, `text` = câu trả lời chat đang gõ dở).
- (ĐÃ BỎ) "space outbox" riêng cho Siri → (ĐÃ BỎ) DM + nhãn `🎙` → (ĐANG DÙNG) **file outbox**
  `~/.hermes/state/siri_outbox.json` + route `deliver: "log"`: không dùng Chat API, không nhãn, không tin nhắn nào.


## Pitfall prompt template của webhook
`_TEMPLATE_KEY_RE = \{([a-zA-Z0-9_.]+)\}`, thay thế **mọi** lần xuất hiện.
⇒ Đừng viết placeholder vào câu rào kiểm tra ("nếu còn nguyên chuỗi {text} thì...") — nó bị thay bằng dữ liệu thật
và model tưởng dữ liệu trống. Câu rào phải mô tả bằng lời. Ngoặc JSON thật (`{"id": ...}`) thì không bị thay.

## Format trả về cho client (JSON — để bắt key)
```
HTTP 200  Content-Type: application/json; charset=utf-8
{"status": "ok"|"timeout"|"empty", "text": "<câu trả lời để đọc to>", "waited_s": 4.7, "echo": "<lệnh đã nhận>"}
```
- `text` LUÔN có (kể cả timeout) ⇒ client chỉ cần đọc `text`, không phải xử lý nhánh.
- `401` sai token · `502` không gửi được lệnh (`{"status":"error",...}`) · `?format=text` → trả text thô.

## Kiểm chứng (số thật)
Lệnh thoại ngắn → `POST /siri/say` → HTTP 200, `wait=16.8s`, `answer=yes`, text trả về = nội dung file
`~/.hermes/state/siri_outbox.json` (thời kênh-DM thì so với tin có nhãn 🎙 trong DM).
Từ 2026-09-12 v4.0: kênh là file outbox ⇒ kiểm chứng bằng `cat ~/.hermes/state/siri_outbox.json`
ngay sau khi gọi, đồng thời xác nhận DM/group **không** có tin mới.

## Chẩn đoán khi client báo timeout — thứ tự bắt buộc
```bash
journalctl --user -u siri-speak --since "-10min" --no-pager   # cổng ĐANG nhận gì (GET /health, POST /siri/say)
grep -E "route=siri|response ready" ~/.hermes/logs/gateway.log | tail -5
```
1. **Cổng không có dòng `POST /siri/say`** ⇒ lỗi phía client, KHÔNG phải cổng: địa chỉ còn IP cũ (node đã bị remove
   khỏi tailnet = hố đen), hoặc VPN trên máy chưa bật, hoặc sai cổng. Sửa cổng lúc này là vô ích.
2. Có `POST` mà không có event trên gateway ⇒ token/socket giữa cổng và gateway (xem `401` / `502`).
3. Có `POST` + gateway có `route=siri` nhưng client vẫn timeout ⇒ lỗi ngưỡng thời gian (mục Timeout phía trên).
4. Kiểm tra node đang có tên/IP gì, và node cũ còn sót trong tailnet không (Peer list) — node chết còn trong
   tailnet chính là nguồn của "IP cũ vẫn nằm trong Shortcut":
   `docker exec tailscale tailscale status --json` → `Self.DNSName`, `Self.TailscaleIPs`, `CurrentTailnet.MagicDNSSuffix`, `Peer`.

## Kênh Siri: tiếng Anh + lọc input + full năng lực (chốt 2026-09-12)
- Prompt route `siri`: **input và output TIẾNG ANH**; việc đụng tới group/chat (đăng tin, trả lời tester) vẫn tiếng Việt.
- **Lọc input trước khi làm việc**: dictation tiếng Anh hay méo ("Hey", "Dậy", "Hay u John") ⇒ hiểu sai thì hỏi lại
  xác nhận ngắn rồi DỪNG, tuyệt đối không đoán rồi làm bừa.
- **Full năng lực**: adapter webhook mặc định bó vào toolset `safe` (web/vision/image_gen ≈ 7 tool, không `write_file`/terminal).
  Mở bằng key tay `"toolsets": [...]` đặt **trong chính route** ở `webhook_subscriptions.json` — `toolsets_for_source()`
  đọc `route_config["toolsets"]`, nên chỉ route đó được mở (khác `platform_toolsets` là mở cho mọi route webhook).
  Đang set cho `siri`: web, search, vision, file, terminal, skills, memory, todo, code_execution, session_search, browser, cronjob.
- Verify không cần chạy thật: `obj = object.__new__(WebhookAdapter); obj._routes = <subs>;` rồi gọi
  `WebhookAdapter.toolsets_for_source(obj, src)` với `src.chat_id = "webhook:siri:x"` (route khác phải trả `None`).
- Câu chờ/lỗi trong `siri_speak.py` cũng phải tiếng Anh (`TIMEOUT_MSG`, nhánh `empty`) vì Siri đọc nguyên văn.

## Mở lại cổng sau teardown (node còn danh tính ⇒ KHÔNG phải approve lại)
Teardown hiện tại chỉ `tailscale down` + `docker rm` và **GIỮ volume** `tailscale-state` ⇒ node giữ nguyên danh tính
(đo thật: dựng lại ra đúng tên `ultron` + đúng IP cũ), không phải login/approve lại. Chỉ khi volume đã mất mới rơi vào nhánh "tạo node mới + IP đổi".
1. `docker run -d --name tailscale --net=host --cap-add=NET_ADMIN --cap-add=NET_RAW --device=/dev/net/tun -v tailscale-state:/var/lib/tailscale -e TS_STATE_DIR=/var/lib/tailscale -e TS_USERSPACE=false -e TS_AUTHKEY="$(cat ~/.hermes/state/tailscale_authkey.txt)" --restart unless-stopped tailscale/tailscale:latest`
   (thiếu `TS_STATE_DIR`/`TS_USERSPACE=false` ⇒ state nằm trong RAM, container restart loop; thiếu `TS_AUTHKEY` ⇒ phải approve bằng tay)
2. `docker exec -d tailscale sh -c 'tailscale up --hostname=ultron --accept-dns=false --timeout=60m > /tmp/tsup.log 2>&1'`
   (thiếu `--accept-dns=false` là bị từ chối: "requires mentioning all non-default flags").
3. URL `https://login.tailscale.com/a/...` nằm ở `/tmp/tsup.log` → **gửi DM Hoàng** bấm Approve (không lên group).
4. Sau khi approve: `systemctl --user start siri-speak` **và khởi động lại gateway** — socket `:9443` bind vào IP tailnet
   sẽ chết khi IP biến mất, phải bind lại (đường hợp lệ: để claude đọc `gw_restart.txt`, không tự restart từ trong gateway).
5. Verify: `/health` = `ok` · POST `/siri/say` → `text` tiếng Anh · DM nhận tin `🎙`.
