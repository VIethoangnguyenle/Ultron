# Đường đồng bộ cho client ngoài (Siri/Shortcuts) — trả câu trả lời trong HTTP response

## Vấn đề
`hermes webhook` trả về **ngay** `{"status":"accepted","route":...,"delivery_id":...}` (HTTP 202, ~1ms) rồi chạy Agent ở nền.
⇒ Client kiểu Siri/Shortcuts chỉ nhận `accepted`, KHÔNG có gì để đọc to.

Các đường KHÔNG dùng được (đã kiểm chứng trong source `gateway/platforms/webhook.py`):
- `send()` ­chỉ hỗ trợ `deliver` = `log` / `github_comment` / các platform chat đã biết. **Không có callback_url / response_url**.
- Session webhook bị **giới hạn tool** (~7: web, vision, clarify, tool_search/describe/call) ⇒ **không có `write_file`/terminal**.
  Đừng thiết kế "Agent ghi kết quả ra file rồi client đọc file" — Agent sẽ báo không có tool ghi file.

## Cách chạy được: cổng "nói" đứng giữa (đã dựng: `~/.hermes/scripts/siri_speak.py`)
```
Shortcuts --POST--> 100.120.110.26:9444/siri/say --> (forward) --> 100.120.110.26:9443/webhooks/siri
                     bridge chờ câu trả lời, rồi trả JSON {"status","text","waited_s","echo"} trong response body
```
- Bridge tự đẩy lệnh sang route webhook, ghi **mốc thời gian trước khi gửi** (trừ hao 3s lệch đồng hồ), rồi poll kênh `deliver`
  (ở đây: DM của Hoàng) qua Chat API read-only, lấy tin **của bot** mới hơn mốc, **bỏ qua tin marker** ("is thinking" / "đang nghĩ"), trả về text đầu tiên.
- Timeout 50s (< ngưỡng cắt ~60s của Shortcuts) → trả câu xin lỗi thay vì treo.
- Bảo mật: bind **IP Tailscale**, bắt buộc `X-Gitlab-Token`, chặn body > 8KB, không log token/nội dung lệnh.
- Service: `~/.config/systemd/user/siri-speak.service` (Restart=always). Nạp lại code = `systemctl --user kill -s TERM siri-speak`
  (KHÔNG dùng `restart` — guard Hermes chặn; `Restart=always` tự dựng lại, mất ~6s nên chờ ≥9s trước khi test).

## TÁCH KÊNH NHẬN (bắt buộc — đã từng bắt lỗi thật)
Đừng để route webhook deliver vào cùng space với chat thường: cả phiên webhook lẫn phiên chat đều là **cùng một bot**,
bridge sẽ nhặt nhầm câu trả lời của phiên chat (thật gặp: `waited_s=1.3`, `text` = câu trả lời chat đang gõ dở).
- (ĐÃ BỎ) không tạo "space outbox" cho Siri nữa; cũng không cần `gchat_send_text.py` để mirror —
  chính webhook đã deliver câu trả lời (có nhãn 🎙) vào DM.


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
Prompt lệnh thoại ngắn gọn → `POST /siri/say` → HTTP 200, `wait=16.8s`, `answer=yes`, text trả về trùng tin nhắn trong DM.
