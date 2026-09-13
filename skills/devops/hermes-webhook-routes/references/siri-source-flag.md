# Cờ NGUỒN cho cổng nói `:9444/siri/say` (làm 2026-09-13)

Chủ máy muốn: Siri từ **điện thoại** thì KHÔNG phát tiếng trên laptop; từ **desktop** thì laptop đọc to câu trả lời.

## Hợp đồng
| Nguồn | Cách gửi | Hành vi |
|---|---|---|
| phone | không gửi cờ (mặc định) | trả `text` cho client, **không phát loa** |
| desktop | `?source=desktop` / JSON `"source"` / header `X-Ultron-Source` | trả `text` **và phát loa laptop** (TTS nền, có lock) |
| giá trị lạ (vd `widget`) | như trên | coi như phone + ghi log `nguồn lạ '<x>'` |

Response luôn kèm `"source"` để client biết cổng hiểu đúng. Payload forward lên agent thêm field `source`.

## Bẫy đã gặp
- **Unit systemd user không có phiên âm thanh** ⇒ phải tự đặt `XDG_RUNTIME_DIR=/run/user/<uid>` + `PULSE_SERVER=unix:<XDG_RUNTIME_DIR>/pulse/native` khi phát, nếu không `paplay` im lặng mà vẫn exit 0.
- Phát trong THREAD NỀN: lỗi TTS/thiếu loa chỉ ghi log, response HTTP vẫn trả bình thường.
- Giọng theo ngôn ngữ câu trả lời (vi-VN khi có dấu tiếng Việt, còn lại en-US).

## Cách kiểm chứng (đừng tin exit code)
```bash
MON=$(pactl list short sources | awk '/monitor/{print $2; exit}')
parec -d "$MON" --file-format=wav /tmp/rec.wav &     # bắt đầu TRƯỚC khi gọi cổng
curl -s -X POST http://127.0.0.1:9444/siri/say?source=desktop \
  -H "X-Gitlab-Token: $(cat ~/.hermes/state/siri_token.txt)" \
  -H 'Content-Type: application/json' -d '{"text":"Reply with exactly: desktop speak check"}'
ffmpeg -i /tmp/rec.wav -af volumedetect -f null - 2>&1 | grep max_volume
```
Đo thật 2026-09-13: **phone ⇒ -91.0 dB (im tuyệt đối)**, **desktop ⇒ -29.0 dB (có tiếng)**.
Cách khác (đã kiểm): đặt script giả tên `paplay` vào PATH ghi dấu vết — phone KHÔNG tạo dấu vết, desktop CÓ.

## Chỗ giao nhau với widget
Widget gọi cùng cổng này **rồi tự đọc to**, nên nó gửi `source=widget` (cổng coi là phone = im) ⇒ không bị đọc 2 lần. Vẫn kiểm chứng lại bằng bản ghi monitor: chỉ MỘT đoạn có tiếng.

## Điểm yếu đã biết
Gateway `:9443` chỉ bind IP tailnet ⇒ sau teardown 17:30, cổng local không chuyển tiếp được vào gateway (widget/Siri tối không có trả lời). Cần chủ máy quyết trước khi đổi `platforms.webhook.extra.host`.
