# Prompt route `siri` (kênh thoại Hoàng → Ultron qua Tailscale)

Bản chuẩn. Bản ĐANG SỐNG là bản inline trong `~/.hermes/webhook_subscriptions.json` (key `siri.prompt`).
Route này để `deliver: "log"` — câu trả lời **KHÔNG** gửi lên Chat (không DM, không group), chỉ ghi
`gateway.log`; kênh thật để Siri đọc là **file outbox** mà prompt yêu cầu Ultron tự ghi.

Đăng ký lại (khi phải làm tay; sửa prompt thì sửa file này trước):

```bash
hermes webhook subscribe siri \
  --prompt "$(sed -n '/^```text$/,/^```$/p' <file này> | sed '1d;$d')" \
  --secret "$(cat ~/.hermes/state/siri_token.txt)" --deliver log
```

rồi **thêm tay** key `toolsets` (12 tool) vào `webhook_subscriptions.json` — CLI không được tự cấp tool.

**KHÔNG để prompt này ở `/tmp/*.txt`**: teardown Tailscale scrub mọi file `.txt/.log` chứa dấu vết
"tailscale" ⇒ prompt bị bôi trắng, cổng Siri hỏng. File `.md` trong skill là chỗ an toàn.

---

```text
Voice command from Hoang, sent via Siri on his iPhone (arrives over Tailscale). COMMAND (raw English dictation): {text}
---
You are speaking with Hoang BY VOICE. Your answer is read aloud by Siri.

DELIVERY - file only, NO chat message: as your LAST action write /home/zane/.hermes/state/siri_outbox.json with the write_file tool, content exactly {"text": "<your answer>", "ts": <epoch seconds now as number>}. Never post anything to Google Chat (no DM, no group) for this request - the file is the only channel. If the work takes longer than ~15 seconds, write a short interim line first ('On it - I will follow up.'), then overwrite the file with the real answer when it is ready.

ANSWER STYLE: plain English, meant to be SPOKEN - at most 2 short sentences, no markdown, no emoji, no lists, no file paths, no code.

If the dictation is garbled and you cannot tell what he wants: do NOT guess, do NOT start work - write text 'Sorry, I did not catch that - say it once more, please?'

LANGUAGE: the file is English. Anything you post to a chat/group while doing real work stays Vietnamese as usual.
```

Ghi chú:
- `{text}` phải xuất hiện ĐÚNG 1 lần (2 lần ⇒ prompt tự tham chiếu, session đi lạc ~75s).
- Ngoặc JSON thật trong prompt (`{"text": ...}`) KHÔNG bị template thay — chỉ `{name}` dạng key mới bị.
- Lệnh dài (>15s) ⇒ ghi tạm 1 câu interim trước, cổng trả câu đó cho Siri, bản cuối vẫn nằm trong file.
