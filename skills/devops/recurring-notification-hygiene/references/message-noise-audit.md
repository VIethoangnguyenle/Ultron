# Rà nguồn tin gây ồn trong một space

Mục tiêu: từ "group này nhiều tin quá" → danh sách chính xác nguồn nào đang gửi, tần suất nào,
nguồn nào do chạy tay. Chạy theo thứ tự dưới, không đoán.

## 1. Đếm tin thật trong space
```bash
python3 ~/.hermes/scripts/gchat_dump.py --space spaces/<ID> --limit 30
python3 ~/.hermes/scripts/gchat_dump.py --space spaces/<ID> --limit 30 --sender users/<bot-id>
```
Bản `--json` với `--limit` lớn hay bị cụt giữa chừng ⇒ dùng bản text rồi lọc bằng `cut -c1-70` / `sed`.
Timestamp trong dump là giờ **UTC** — cộng 7 giờ để so với `schedules.yaml` (09:00 local = 02:00 dump).

## 2. Liệt kê nguồn gửi định kỳ nhắm vào space đó
```bash
# cron job (LLM job) — xem deliver/destination
python3 - <<'EOF'
import json
jobs = json.load(open('/home/zane/.hermes/cron/jobs.json'))
jobs = jobs.get('jobs', jobs) if isinstance(jobs, dict) else jobs
for j in jobs:
    if not j.get('enabled', True):
        continue
    print(j.get('id'), '|', j.get('schedule'), '|', j.get('delivery') or j.get('deliver'))
EOF

# action thuần script (0 token)
python3 ~/.hermes/scripts/daily_dispatch.py --list
```
`--list` vẫn hiện cả action `enabled: false` — action tắt thì không phải nguồn ồn.
Script tự gọi gchat ngoài hai đường trên: tìm chỗ hard-code space đích trong `~/.hermes/scripts/`
(bám theo chuỗi `spaces/<ID>` hoặc `--send`).

## 3. Xem hôm nay nguồn nào đã bắn
```bash
grep -n "FIRED" ~/.hermes/cron/dispatch.log | tail -20
grep -n "<action-id>" ~/.hermes/cron/dispatch.log | tail -5
grep "<space-id>" ~/.hermes/cron/dispatch.log | cut -c1-160
```
Mỗi lần gửi thành công = 1 dòng `FIRED <id> -> '<10 ký tự đầu nội dung>'` ⇒ đếm số dòng `FIRED` trong
ngày là ra số tin đã gửi.

## 4. Tin lạ không có trong log ⇒ do chạy tay
Dấu hiệu: nội dung có trong space nhưng không có dòng `FIRED` tương ứng, hoặc cửa sổ thời gian của báo
cáo bắt đầu đúng lúc phiên đang chạy.
Kiểm: `ls -la ~/.hermes/scripts/<script>.py` (mtime = lúc vừa sửa) và lịch sử phiên vừa rồi.
Đây là lỗi quy trình test, không phải lỗi lịch — nhận đúng rồi siết lại: **không chạy bản có cờ gửi để
kiểm chứng**.

## 5. Chốt & sửa
- Bảng ngắn: nguồn → tần suất hiện tại → tần suất mới.
- Hạ tần suất trong `~/.hermes/schedules.yaml` (đổi `when`/`days`, hoặc cửa sổ `--hours` trong `args`),
giữ `until`, ghi 1 comment ngay cạnh nêu lý do + cách bật lại.
- Cron job thì đổi `delivery` sang `local`/DM thay vì xoá job nếu job còn giá trị khác.
- Xác nhận lại bằng `python3 ~/.hermes/scripts/daily_dispatch.py --list`.
