# Cổng NÓI (`:9444`) — cờ NGUỒN và luật "chỉ desktop mới phát loa máy"

## Hợp đồng với client
Gửi cờ nguồn theo 1 trong 3 cách (nhận cả 3 để client nào cũng gửi được):
```
POST /siri/say?source=desktop
{"text": "...", "source": "desktop"}
X-Ultron-Source: desktop
```
Giá trị `phone` | `desktop` (cắt khoảng trắng, không phân biệt hoa thường).
- **THIẾU cờ ⇒ `phone`**: giữ nguyên hành vi cũ (trả text cho client tự đọc), KHÔNG phát gì trên máy chủ.
- Giá trị lạ ⇒ coi như `phone` + 1 dòng log, KHÔNG trả lỗi (client cũ/mới lẫn lộn không được vỡ).
- Response trả kèm `"source"` để client biết cổng hiểu đúng nguồn.
- Payload forward lên route thêm field `source` (giữ nguyên `text` + `req_id`).

## Vì sao cần cờ
Một cổng dùng chung cho nhiều client: iPhone (Siri đọc tại chỗ), desktop (cần máy đọc to), widget trên máy
(tự TTS lấy). Không có cờ thì không cách nào biết lượt này phải phát loa hay im.

## Luật cứng
- Nguồn `phone` TUYỆT ĐỐI không được gọi bất kỳ lệnh phát âm thanh nào (edge-tts / paplay / ffplay / aplay).
- Nguồn `desktop` mới phát: TTS → file tạm → paplay/ffplay, chạy trong THREAD NỀN (không chặn response HTTP),
  có LOCK để hai lượt không phát chồng; lỗi TTS/thiếu loa chỉ ghi log, response vẫn trả bình thường.
- Chọn giọng theo nội dung câu trả lời: có dấu tiếng Việt ⇒ `vi-VN-NamMinhNeural`, còn lại ⇒ giọng Anh.
- **Unit systemd user KHÔNG có phiên âm thanh**: khi phát phải tự đặt `XDG_RUNTIME_DIR=/run/user/<uid>` và
  `PULSE_SERVER=unix:$XDG_RUNTIME_DIR/pulse/native`, nếu không lệnh "thành công" mà không ra tiếng.
- Widget trên máy tự đọc to ⇒ nó gọi cổng với `source=widget`; cổng coi giá trị lạ như `phone` (im). Nghiệm thu
  kèm: bản ghi chỉ được có MỘT đoạn tiếng (widget đọc), không phải hai.

## Kiểm chứng — phải là ÂM THANH THẬT, không tin exit code
```bash
MON=$(pactl list short sources | awk '/monitor/{print $2; exit}')
parec -d "$MON" --file-format=wav /tmp/rec.wav &          # bật TRƯỚC khi bắn request
T=$(cat ~/.hermes/state/siri_token.txt)
curl -s -H "X-Gitlab-Token: $T" -H 'Content-Type: application/json' \
     -X POST "http://127.0.0.1:9444/siri/say?source=desktop" -d '{"text":"..."}'
ffmpeg -i /tmp/rec.wav -af volumedetect -f null - 2>&1 | grep -E "mean_volume|max_volume"
```
- Im lặng ⇒ `mean/max ≈ -91.0 dB`; có tiếng thật ⇒ `max ≈ -25…-30 dB`.
- Chạy 2 lượt đối chứng (không cờ vs `?source=desktop`) trong CÙNG một phiên thu là bằng chứng mạnh nhất.
- Lớp nghiệm thu bổ sung (không cần loa): cắm script giả tên `paplay`/`ffplay` vào PATH ghi dấu vết ⇒ lượt
  `phone` KHÔNG được tạo file dấu vết, lượt `desktop` PHẢI có.
- Sau khi nạp lại cổng: `GET /health` = 200, thiếu token = 401, traversal = 404, và xác nhận gateway KHÔNG bị
  restart (`systemctl --user show -p ActiveEnterTimestamp --value hermes-gateway`).

## Bẫy đã dính
- `~/.hermes` KHÔNG phải repo git ⇒ claude không commit được ở đó; yêu cầu nó giữ `.bak-<mốc>` cạnh file gốc
  và ghi worklog thay vì cố `git commit`.
- Client trên máy dùng `127.0.0.1`; client ngoài dùng tên MagicDNS (IP tailnet đổi mỗi lần dựng lại node).
