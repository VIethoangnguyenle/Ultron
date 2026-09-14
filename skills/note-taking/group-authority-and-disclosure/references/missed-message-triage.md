# Chẩn đoán "Ultron lơ tin nhắn" (missed-message triage)

Dùng khi một đồng nghiệp trong group tố Ultron "lơ tin nhắn", "không trả lời", "ngó lơ tôi".

## Nguyên tắc gốc

Chat app Google Chat chỉ nhận `MESSAGE` event cho (a) mọi tin trong DM với bot, (b) trong space nhiều
người: **chỉ tin @mention bot**. Không có toggle nào bật nhận tin không tag. Nên "bị lơ" thường =
tin không tag, hoặc bot không ở trong space, hoặc hàng đợi chậm — ba thứ này phải phân biệt bằng
bằng chứng, không đoán.

## B1 — Bot có nhận được tin chưa (nguồn sự thật)

```bash
awk '/^<YYYY-MM-DD>/' ~/.hermes/logs/gateway.log | grep "inbound message" \
  | sed -E 's/.*user=([^,]+),.*chat=([^ ]+) msg=.?(.{0,90}).*/\1 | \2 | \3/' | grep -i "<tên người>"
```

- Không có dòng nào ⇒ bot **chưa từng** nhận tin đó (adapter ghi log mọi inbound trước khi xử lý).
  Trong space nhóm, gần như chắc chắn là tin không tag → trả lời bằng cơ chế tag, KHÔNG nhận là bug.
- Có dòng ⇒ adapter đã nhận; kiểm hàng đợi: `grep "response ready" ~/.hermes/logs/gateway.log | tail`
  — `time=<giây>` lớn (hàng trăm giây) là vì gateway xử lý TUẦN TỰ: thread/session khác đang chạy thì
  tin mới phải xếp hàng.
- `chat=` trong dòng log cho biết space; so với `spaces/<id>` đang bị tố để chắc không lẫn space.

## B2 — Tin đó có thật trong space không

```bash
python3 ~/.hermes/scripts/gchat_dump.py --space spaces/XXX --limit 300 [--sender users/ID] [--grep "từ khoá"]
```

- Dùng user read token (`~/.hermes/google_chat_read_token.json`) ⇒ thấy được **cả tin không tag**
  (tin bot không thấy). Đây là dẫn chứng để nói "tin chị nằm ở đây nhưng không tag nên em mù".
- `--limit` lấy N tin MỚI NHẤT rồi mới lọc theo `--sender`/`--grep` ⇒ quét xa hơn thì tăng `--limit`,
  không phải đổi cách lọc.
- Quét nhiều space: `spaces().list(pageSize=...)` rồi mỗi space `messages().list(parent=...,
  filter='createTime > "<ISO>"')`, lọc theo `sender.name`; IN TỔNG KẾT (space + giờ + trích ~200 ký tự),
  KHÔNG in cả dump vào ngữ cảnh.

## B3 — Bot có ở trong space đó không

```python
from google.oauth2 import service_account
creds = service_account.Credentials.from_service_account_file(
    "/home/zane/.hermes/google-chat-sa.json",
    scopes=["https://www.googleapis.com/auth/chat.bot"])
svc.spaces().list(pageSize=200).execute()["spaces"]   # space bot tham gia, gồm DM với bot
```

- `spaces().list` chạy được bằng token SA. `spaces().messages().list` bằng SA trả 403
  `insufficient authentication scopes` (bot không đọc lịch sử — đúng thiết kế) ⇒ muốn đọc nội dung
  phải dùng user read token ở B2.
- Không thấy space DM nào giữa người đó và bot ⇒ loại giả thuyết "DM bot mà không được trả lời".

## B4 — Kết luận & câu trả lời

| Bằng chứng | Kết luận | Trả lời trong group |
|---|---|---|
| gateway.log không có inbound từ người đó | Tin không tag | Nói cơ chế: bot chỉ nhận tin có tag; xin tag lại, hỏi họ cần gì để làm ngay |
| Có inbound, `time=` ở "response ready" rất lớn | Chậm hàng đợi (gateway tuần tự) | Thừa nhận đang xếp hàng, xin lỗi nhẹ, trả lời luôn phần đang chờ |
| Người đó không ở space nào cùng bot | Bot không thấy được | Nói cần thêm bot vào space |

Giọng: người tố "lơ" thường đang dỗi-đùa; trả lời NGAY, ngắn, không đổ lỗi ngược, không hứa tính năng
mới. Tra hồ sơ trước (`python3 ~/.hermes/scripts/people.py show <users/id>`) để chọn giọng —
PM/leader/sếp thì ga-lăng, không cà khịa.

## Sau khi xử lý

Ghi 1 dòng vào hồ sơ người đó (`people.py note <users/id> "..."`) nếu học được điều bền vững
(vd họ đang chủ động thử năng lực Ultron, hay đòi phản hồi trong ~1 phút) để lần sau ứng xử đúng.
